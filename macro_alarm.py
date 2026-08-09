#!/usr/bin/env python3
"""
US Macro / Equity Crash Alarm
-----------------------------
Rule-based monitoring dashboard using public FRED data.

What it does:
- Downloads the latest macro/market series from the FRED API.
- Computes a recession/market-stress score.
- Adds a "Fed constrained" overlay when inflation is high while growth/credit weaken.
- Prints GREEN / YELLOW / ORANGE / RED alerts.
- Writes a JSON snapshot for tracking over time.

Setup:
    pip install pandas requests
    export FRED_API_KEY="your_fred_api_key"

Run:
    python macro_alarm.py

Optional:
    python macro_alarm.py --json alarm_snapshot.json
"""

import argparse
import json
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, Tuple, List

import pandas as pd
import requests

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"


SERIES = {
    "sahm": "SAHMREALTIME",        # Real-time Sahm Rule
    "hy_oas": "BAMLH0A0HYM2",     # High-yield corporate OAS, %
    "core_pce": "PCEPILFE",        # Core PCE price index
    "curve_10y3m": "T10Y3M",       # 10Y - 3M Treasury spread, %
    "ust10y": "DGS10",             # 10Y Treasury yield, %
    "claims": "ICSA",              # Initial unemployment claims
    "indpro": "INDPRO",            # Industrial Production Index
    "real_gdp": "GDPC1",           # Real GDP
    "sp500": "SP500",              # S&P 500 price index
}


@dataclass
class Signal:
    name: str
    value: float
    status: str
    points: float
    max_points: float
    explanation: str


def fred_series(series_id: str, api_key: str, observation_start="2020-01-01") -> pd.Series:
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": observation_start,
        "sort_order": "asc",
    }
    r = requests.get(FRED_URL, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()["observations"]

    idx, vals = [], []
    for row in data:
        if row["value"] == ".":
            continue
        idx.append(pd.to_datetime(row["date"]))
        vals.append(float(row["value"]))

    s = pd.Series(vals, index=pd.DatetimeIndex(idx), name=series_id).sort_index()
    return s


def latest(s: pd.Series) -> float:
    return float(s.dropna().iloc[-1])


def pct_change_yoy(s: pd.Series) -> float:
    """Year-over-year percent change using date-aware monthly/quarterly series."""
    s = s.dropna()
    last_date = s.index[-1]
    target = last_date - pd.DateOffset(years=1)
    old = s.loc[:target]
    if old.empty:
        raise ValueError("Not enough history for YoY calculation.")
    old_val = float(old.iloc[-1])
    new_val = float(s.iloc[-1])
    return (new_val / old_val - 1.0) * 100.0


def annualized_qoq(s: pd.Series) -> float:
    """Annualized quarter-over-quarter growth rate for quarterly level series."""
    s = s.dropna()
    if len(s) < 2:
        raise ValueError("Not enough quarterly history.")
    return ((float(s.iloc[-1]) / float(s.iloc[-2])) ** 4 - 1.0) * 100.0


def trailing_drawdown(s: pd.Series, window=252) -> float:
    s = s.dropna()
    window_data = s.iloc[-window:] if len(s) >= window else s
    high = float(window_data.max())
    cur = float(window_data.iloc[-1])
    return (cur / high - 1.0) * 100.0


def score_sahm(v: float) -> Signal:
    if v >= 0.50:
        return Signal("Sahm Rule", v, "RED", 2.0, 2.0,
                      ">= 0.50: recession-start signal is triggered.")
    if v >= 0.30:
        return Signal("Sahm Rule", v, "YELLOW", 1.0, 2.0,
                      "0.30-0.49: labor deterioration deserves close monitoring.")
    return Signal("Sahm Rule", v, "GREEN", 0.0, 2.0,
                  "< 0.30: no Sahm labor-market alarm.")


def score_hy_oas(v: float) -> Signal:
    if v >= 6.0:
        return Signal("High-Yield OAS", v, "RED", 2.0, 2.0,
                      ">= 6%: severe credit stress.")
    if v >= 4.0:
        return Signal("High-Yield OAS", v, "YELLOW", 1.0, 2.0,
                      "4-6%: credit conditions are meaningfully tightening.")
    return Signal("High-Yield OAS", v, "GREEN", 0.0, 2.0,
                  "< 4%: credit market is not signaling broad stress.")


def score_core_pce(v: float) -> Signal:
    if v >= 4.0:
        return Signal("Core PCE YoY", v, "RED", 1.5, 1.5,
                      ">= 4%: inflation strongly constrains Fed easing.")
    if v >= 3.0:
        return Signal("Core PCE YoY", v, "YELLOW", 0.75, 1.5,
                      "3-4%: inflation remains above a comfortable range.")
    return Signal("Core PCE YoY", v, "GREEN", 0.0, 1.5,
                  "< 3%: inflation is less restrictive for Fed policy.")


def score_10y(v: float) -> Signal:
    if v >= 5.5:
        return Signal("10Y Treasury", v, "RED", 1.0, 1.0,
                      ">= 5.5%: high discount-rate / refinancing pressure.")
    if v >= 5.0:
        return Signal("10Y Treasury", v, "YELLOW", 0.5, 1.0,
                      "5-5.5%: elevated valuation and financing pressure.")
    return Signal("10Y Treasury", v, "GREEN", 0.0, 1.0,
                  "< 5%: no standalone long-rate alarm.")


def score_curve(s: pd.Series) -> Signal:
    s = s.dropna()
    v = float(s.iloc[-1])
    recent = s.loc[s.index >= s.index[-1] - pd.DateOffset(months=24)]
    prior_inversion = float(recent.min()) <= -0.50

    if prior_inversion and v >= 0.75:
        return Signal("10Y-3M Curve", v, "RED", 1.0, 1.0,
                      "Curve re-steepened sharply after a deep inversion; historically this can occur near late-cycle weakening.")
    if prior_inversion and v > 0:
        return Signal("10Y-3M Curve", v, "YELLOW", 0.5, 1.0,
                      "Curve is positive after a prior deep inversion; watch labor and credit confirmation.")
    if v <= -0.50:
        return Signal("10Y-3M Curve", v, "YELLOW", 0.5, 1.0,
                      "Deep inversion: medium-term recession warning, not a timing signal.")
    return Signal("10Y-3M Curve", v, "GREEN", 0.0, 1.0,
                  "No strong inversion/re-steepening alarm.")


def score_claims(s: pd.Series) -> Signal:
    s = s.dropna()
    # 4-week mean compared with the lowest 4-week mean during the last 52 weeks.
    avg4 = s.rolling(4).mean().dropna()
    recent52 = avg4.iloc[-52:] if len(avg4) >= 52 else avg4
    cur = float(avg4.iloc[-1])
    low = float(recent52.min())
    pct_above_low = (cur / low - 1.0) * 100.0

    if pct_above_low >= 30:
        return Signal("Initial Claims vs 52w Low", pct_above_low, "RED", 1.5, 1.5,
                      "4-week claims average is >=30% above its 52-week low.")
    if pct_above_low >= 15:
        return Signal("Initial Claims vs 52w Low", pct_above_low, "YELLOW", 0.75, 1.5,
                      "Claims are 15-30% above the 52-week low.")
    return Signal("Initial Claims vs 52w Low", pct_above_low, "GREEN", 0.0, 1.5,
                  "Claims remain within 15% of their 52-week low.")


def score_indpro(v: float) -> Signal:
    if v <= -2.0:
        return Signal("Industrial Production YoY", v, "RED", 1.0, 1.0,
                      "<= -2%: broad cyclical production weakness.")
    if v < 0:
        return Signal("Industrial Production YoY", v, "YELLOW", 0.5, 1.0,
                      "Negative YoY industrial production.")
    return Signal("Industrial Production YoY", v, "GREEN", 0.0, 1.0,
                  "Industrial production is positive YoY.")


def score_gdp(v: float) -> Signal:
    if v < 0:
        return Signal("Real GDP QoQ Ann.", v, "RED", 1.0, 1.0,
                      "Negative annualized quarterly real GDP growth.")
    if v < 1.0:
        return Signal("Real GDP QoQ Ann.", v, "YELLOW", 0.5, 1.0,
                      "0-1% annualized growth: weak but not recession confirmation.")
    return Signal("Real GDP QoQ Ann.", v, "GREEN", 0.0, 1.0,
                  "Real GDP growth is above 1% annualized.")


def score_sp500(v: float) -> Signal:
    # This is confirmation, not a leading indicator, so weight is small.
    if v <= -20:
        return Signal("S&P 500 Drawdown", v, "RED", 0.5, 0.5,
                      "<= -20%: market damage already confirms a bear market.")
    if v <= -10:
        return Signal("S&P 500 Drawdown", v, "YELLOW", 0.25, 0.5,
                      "-10% to -20%: correction underway.")
    return Signal("S&P 500 Drawdown", v, "GREEN", 0.0, 0.5,
                  "Less than a 10% drawdown from the trailing one-year high.")


def overall_label(score: float, max_score: float) -> str:
    ratio = score / max_score
    if ratio >= 0.60:
        return "RED"
    if ratio >= 0.40:
        return "ORANGE"
    if ratio >= 0.20:
        return "YELLOW"
    return "GREEN"


def run_model(api_key: str):
    data = {name: fred_series(sid, api_key) for name, sid in SERIES.items()}

    core_pce_yoy = pct_change_yoy(data["core_pce"])
    indpro_yoy = pct_change_yoy(data["indpro"])
    gdp_qoq_ann = annualized_qoq(data["real_gdp"])
    sp_drawdown = trailing_drawdown(data["sp500"])

    signals: List[Signal] = [
        score_sahm(latest(data["sahm"])),
        score_hy_oas(latest(data["hy_oas"])),
        score_core_pce(core_pce_yoy),
        score_10y(latest(data["ust10y"])),
        score_curve(data["curve_10y3m"]),
        score_claims(data["claims"]),
        score_indpro(indpro_yoy),
        score_gdp(gdp_qoq_ann),
        score_sp500(sp_drawdown),
    ]

    base_score = sum(x.points for x in signals)
    max_score = sum(x.max_points for x in signals)

    # Fed-constrained overlay:
    # If inflation >=3% AND at least two growth/credit signals are yellow/red,
    # the Fed may have less room to cut aggressively during weakness.
    stress_names = {
        "Sahm Rule", "High-Yield OAS", "Initial Claims vs 52w Low",
        "Industrial Production YoY", "Real GDP QoQ Ann."
    }
    growth_stress_count = sum(
        1 for x in signals
        if x.name in stress_names and x.status in {"YELLOW", "RED"}
    )
    fed_constrained = core_pce_yoy >= 3.0 and growth_stress_count >= 2

    overlay = 1.5 if fed_constrained else 0.0
    score = base_score + overlay
    max_total = max_score + 1.5
    label = overall_label(score, max_total)

    return label, score, max_total, fed_constrained, growth_stress_count, signals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", default="macro_alarm_snapshot.json",
                        help="Output JSON filename.")
    args = parser.parse_args()

    api_key = os.getenv("FRED_API_KEY")
    if not api_key:
        raise SystemExit(
            "Missing FRED_API_KEY. Create a free FRED API key and set:\n"
            '  export FRED_API_KEY="YOUR_KEY"\n'
        )

    label, score, max_total, fed_constrained, growth_stress_count, signals = run_model(api_key)

    print("\n" + "=" * 72)
    print(" U.S. MACRO / EQUITY CRASH ALARM")
    print("=" * 72)
    print(f" Overall: {label}   Score: {score:.2f}/{max_total:.2f}")
    print(f" Fed-constrained overlay: {'YES' if fed_constrained else 'NO'}")
    print(f" Growth/credit stress signals: {growth_stress_count}")
    print("-" * 72)

    for s in signals:
        print(f"{s.status:6} | {s.name:28} | {s.value:8.2f} | "
              f"{s.points:.2f}/{s.max_points:.2f}")
        print(f"       {s.explanation}")

    if fed_constrained:
        print("\n*** SPECIAL ALARM: INFLATION + GROWTH/CREDIT STRESS ***")
        print("Inflation is >=3% while at least two growth/credit indicators are")
        print("deteriorating. This is the regime in which Fed easing may be constrained.")

    print("\nInterpretation:")
    print(" GREEN  = low current macro/market stress")
    print(" YELLOW = elevated risk; monitor trend")
    print(" ORANGE = multiple independent warnings")
    print(" RED    = broad stress / recession-crash conditions are converging")
    print("\nThis is a monitoring model, not a probability forecast or trading signal.")

    payload = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "overall": label,
        "score": round(score, 3),
        "max_score": max_total,
        "fed_constrained": fed_constrained,
        "growth_credit_stress_count": growth_stress_count,
        "signals": [asdict(x) for x in signals],
    }

    with open(args.json, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"\nSaved snapshot: {args.json}")


if __name__ == "__main__":
    main()
