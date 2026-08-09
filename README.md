# U.S. Macro / Equity Crash Alarm

A rule-based Python monitoring tool for tracking U.S. macroeconomic and market stress.

The goal of this project is **not** to predict an exact crash date or assign a false sense of precision to recession probabilities. Instead, it combines several public economic and market indicators into an interpretable risk dashboard that can be updated regularly as new data becomes available.

The model outputs one of four overall risk levels:

- **GREEN** — low current macro/market stress
- **YELLOW** — elevated risk; monitor the trend
- **ORANGE** — multiple independent warning signals are active
- **RED** — broad recession / market-stress conditions are converging

It also reports each underlying indicator separately so you can see *why* the model is becoming more or less cautious.

---
## Quick Start

Follow these steps after downloading or cloning the project.

### 1. Open the project folder in Terminal

If you downloaded the ZIP file, unzip it first. On macOS, if the folder is in Downloads:

```bash
cd ~/Downloads/us_macro_equity_crash_alarm

2. Install the required Python packages
pip install -r requirements.txt

If pip does not work, try:

python3 -m pip install -r requirements.txt
3. Set your FRED API key

The model downloads economic data from FRED, so you need a free FRED API key.

On macOS / Linux:

export FRED_API_KEY="YOUR_FRED_API_KEY"

On Windows PowerShell:

$env:FRED_API_KEY="YOUR_FRED_API_KEY"

Do not put your real API key inside macro_alarm.py or upload it to GitHub.

4. Run the model
python macro_alarm.py

On many Macs, use:

python3 macro_alarm.py

The program retrieves the latest available FRED data and prints an overall risk level:

GREEN
YELLOW
ORANGE
RED

It also shows the status and explanation for each individual economic or market indicator.

5. Check the generated snapshot

After a successful run, the program creates:

macro_alarm_snapshot.json

This file contains the current overall score and individual indicator results.


### 在 GitHub 上怎么加

进入你的 repository → 点击 `README.md` → 点击右上方的 **铅笔 Edit** 图标 → 找到：

```text
## What the Model Monitors

## What the Model Monitors

The current version uses nine indicators from FRED:

| Indicator | FRED Series | Purpose |
|---|---|---|
| Sahm Rule | `SAHMREALTIME` | Labor-market recession signal |
| High-Yield OAS | `BAMLH0A0HYM2` | Credit-market stress |
| Core PCE Price Index | `PCEPILFE` | Inflation / Fed policy constraint |
| 10Y Treasury Yield | `DGS10` | Long-rate and valuation pressure |
| 10Y–3M Treasury Spread | `T10Y3M` | Yield-curve cycle signal |
| Initial Jobless Claims | `ICSA` | Early labor-market deterioration |
| Industrial Production | `INDPRO` | Cyclical real-economy weakness |
| Real GDP | `GDPC1` | Broad growth confirmation |
| S&P 500 | `SP500` | Market drawdown confirmation |

The model computes derived measures such as:

- Core PCE year-over-year inflation
- Industrial Production year-over-year growth
- Real GDP annualized quarter-over-quarter growth
- S&P 500 trailing one-year drawdown
- Initial Claims relative to their recent 52-week low
- Yield-curve re-steepening after a prior inversion

---

## Why This Is a Rule-Based Model

Recessions and major equity crashes are rare events. That makes machine-learning approaches easy to overfit.

This project deliberately uses a transparent rule-based framework so that:

1. Every warning signal is explainable.
2. Thresholds can be adjusted and debated.
3. The model can be backtested against historical episodes.
4. Users can track changes in the *trend* rather than rely on one-point forecasts.

This is intended to behave more like a macroeconomic dashboard than a black-box trading system.

---

## Special "Fed-Constrained" Alarm

The model includes a special overlay for a regime in which economic conditions weaken while inflation remains elevated.

The overlay is triggered when:

- Core PCE inflation is **3% or higher**, and
- At least **two growth/credit indicators** are in YELLOW or RED territory.

The growth/credit indicators used for this check are:

- Sahm Rule
- High-Yield OAS
- Initial Jobless Claims
- Industrial Production
- Real GDP

This regime matters because the Federal Reserve may have less room to respond aggressively with rate cuts or QE if inflation is still too high.

When triggered, the program prints:

```text
*** SPECIAL ALARM: INFLATION + GROWTH/CREDIT STRESS ***
```

---

## Default Thresholds

These are heuristic thresholds for the first version of the model. They are not economic laws and should eventually be validated through historical backtesting.

### Sahm Rule

- `< 0.30` → GREEN
- `0.30–0.49` → YELLOW
- `>= 0.50` → RED

### High-Yield OAS

- `< 4%` → GREEN
- `4–6%` → YELLOW
- `>= 6%` → RED

### Core PCE Inflation

- `< 3%` → GREEN
- `3–4%` → YELLOW
- `>= 4%` → RED

### 10-Year Treasury Yield

- `< 5%` → GREEN
- `5–5.5%` → YELLOW
- `>= 5.5%` → RED

### Initial Jobless Claims

The model compares the latest 4-week average with the lowest 4-week average during the previous 52 weeks.

- `< 15% above the low` → GREEN
- `15–30% above the low` → YELLOW
- `>= 30% above the low` → RED

### Industrial Production YoY

- `>= 0%` → GREEN
- `0% to -2%` → YELLOW
- `<= -2%` → RED

### Real GDP QoQ Annualized

- `>= 1%` → GREEN
- `0–1%` → YELLOW
- `< 0%` → RED

### S&P 500 Drawdown

- Better than `-10%` → GREEN
- `-10% to -20%` → YELLOW
- `<= -20%` → RED

The S&P 500 signal has a relatively low weight because market drawdown is more of a confirmation signal than a leading macro indicator.

---

## Yield-Curve Logic

The model does not use the simplistic rule:

> "Yield curve inverted = crash."

Instead, it checks whether the 10Y–3M Treasury spread was deeply inverted during the previous 24 months and whether it has subsequently re-steepened.

This is designed to capture a late-cycle pattern in which the curve becomes positive again after a meaningful inversion.

Current logic:

- Deep inversion (`<= -0.50%`) → YELLOW
- Positive again after prior deep inversion → YELLOW
- Re-steepened to `>= +0.75%` after prior deep inversion → RED

This signal should be interpreted together with labor and credit indicators, not by itself.

---

## Scoring

Each indicator contributes points to an overall score.

Current maximum weights:

| Signal | Max Points |
|---|---:|
| Sahm Rule | 2.0 |
| High-Yield OAS | 2.0 |
| Core PCE | 1.5 |
| Initial Claims | 1.5 |
| 10Y Treasury | 1.0 |
| 10Y–3M Curve | 1.0 |
| Industrial Production | 1.0 |
| Real GDP | 1.0 |
| S&P 500 Drawdown | 0.5 |

The Fed-constrained overlay can add another **1.5 points**.

Overall color thresholds are based on the percentage of the maximum score:

- `< 20%` → GREEN
- `20–40%` → YELLOW
- `40–60%` → ORANGE
- `>= 60%` → RED

These thresholds should be treated as a starting framework for future calibration.

---

## Installation

Python 3.9+ is recommended.

Install the required packages:

```bash
pip install pandas requests
```

---

## FRED API Key

The script downloads economic data from the Federal Reserve Bank of St. Louis FRED API.

You need a free FRED API key.

After obtaining one, set it as an environment variable.

### macOS / Linux

```bash
export FRED_API_KEY="YOUR_FRED_API_KEY"
```

### Windows PowerShell

```powershell
$env:FRED_API_KEY="YOUR_FRED_API_KEY"
```

---

## Running the Model

Run:

```bash
python macro_alarm.py
```

Example output:

```text
========================================================================
 U.S. MACRO / EQUITY CRASH ALARM
========================================================================
 Overall: YELLOW   Score: 3.25/13.00
 Fed-constrained overlay: NO
 Growth/credit stress signals: 2
------------------------------------------------------------------------
GREEN  | Sahm Rule                    |     0.15 | 0.00/2.00
GREEN  | High-Yield OAS               |     3.10 | 0.00/2.00
YELLOW | Core PCE YoY                 |     3.40 | 0.75/1.50
GREEN  | 10Y Treasury                 |     4.60 | 0.00/1.00
YELLOW | 10Y-3M Curve                 |     0.45 | 0.50/1.00
YELLOW | Initial Claims vs 52w Low    |    18.40 | 0.75/1.50
GREEN  | Industrial Production YoY    |     1.20 | 0.00/1.00
GREEN  | Real GDP QoQ Ann.            |     2.10 | 0.00/1.00
GREEN  | S&P 500 Drawdown             |    -4.20 | 0.00/0.50
```

---

## JSON Output

Every run also saves a machine-readable snapshot.

Default filename:

```text
macro_alarm_snapshot.json
```

You can specify another filename:

```bash
python macro_alarm.py --json 2026_Q3.json
```

The JSON contains:

- Generation timestamp
- Overall risk level
- Total score
- Maximum score
- Fed-constrained status
- Number of growth/credit stress signals
- Full details for every indicator

This makes it easy to store historical results and build a time-series dashboard later.

---

## Recommended Update Frequency

Although GDP is quarterly, most indicators update more frequently.

A practical schedule would be:

- **Monthly:** run the full model
- **After each GDP release:** run it again
- **During periods of stress:** monitor credit spreads and claims more frequently

Data frequencies differ:

- High-Yield OAS → daily
- Treasury yields → daily
- Initial Claims → weekly
- Sahm Rule / labor data → monthly
- Core PCE → monthly
- Industrial Production → monthly
- GDP → quarterly
- S&P 500 → daily

The value of the model is not just the current score. The **direction of the score over time** is often more informative.

Example:

```text
2026 Q3   GREEN
2026 Q4   YELLOW
2027 Q1   YELLOW
2027 Q2   ORANGE
2027 Q3   RED
```

A sustained deterioration is more meaningful than a single one-off signal.

---

## Important Limitation: Data Revisions

Many economic series are revised after their initial release.

A naive historical backtest using today's revised data can introduce look-ahead bias because it may use information that investors did not actually have at the time.

For serious historical validation, the next version should use **ALFRED vintage data** so that each historical test uses only the values that were available on that date.

This is especially important for:

- GDP
- Employment data
- Industrial Production
- Inflation data

---

## Suggested V2 Improvements

The current script is a first-generation monitoring model.

Useful next steps include:

### 1. Historical Risk-Score Database

Append every run to a CSV or SQLite database:

```text
date,score,risk_level,sahm,hy_oas,core_pce,...
```

Then plot the risk score over time.

### 2. Historical Backtest

Evaluate how the model behaved around:

- 2000–2002 dot-com bust
- 2007–2009 Global Financial Crisis
- 2020 COVID crash
- 2022 inflation / rate shock

Questions to measure:

- How early did the model move from GREEN to YELLOW?
- When did it become ORANGE or RED?
- How many false alarms occurred?
- Which indicators added the most value?

### 3. Threshold Calibration

Instead of relying entirely on manually selected thresholds, estimate thresholds using historical recession and drawdown data.

### 4. Probability Layer

After sufficient historical calibration, convert the rule score into a rough empirical probability such as:

```text
12-month recession risk
12-month >20% equity drawdown risk
```

This should only be added after careful out-of-sample testing.

### 5. Market Valuation Layer

Possible additions:

- S&P 500 forward P/E
- Equity risk premium
- CAPE
- Market capitalization / GDP
- Earnings-revision breadth

### 6. Financial-Stress Layer

Possible additions:

- Investment-grade credit spreads
- Bank lending standards
- Financial Conditions Index
- TED / funding spreads
- Commercial real-estate stress
- Bank loan growth

### 7. Fiscal-Risk Layer

Possible additions:

- Federal deficit / GDP
- Net interest / federal revenue
- Treasury issuance
- Debt held by public / GDP
- Term premium

This would help distinguish an ordinary recession from a fiscal / inflation / bond-market stress regime.

---

## What This Model Is Not

This project is **not**:

- A guaranteed recession predictor
- A market-timing system
- A trading algorithm
- Investment advice
- A substitute for portfolio diversification or risk management

A RED signal does not mean stocks must fall immediately.

A GREEN signal does not mean markets cannot decline.

Unexpected events such as geopolitical shocks, pandemics, policy errors, bank failures, or market-structure events can cause rapid losses before macroeconomic data reacts.

The best use of the tool is as a **systematic monitoring framework** that forces the user to evaluate multiple independent indicators rather than rely on headlines or intuition.

---

## Files

Main program:

```text
macro_alarm.py
```

Default output:

```text
macro_alarm_snapshot.json
```

---

## Disclaimer

This software is for educational and research purposes only.

Nothing in this project should be interpreted as financial, investment, tax, or legal advice. Historical relationships between economic indicators and market outcomes may change, and no model can reliably predict future market crashes.
