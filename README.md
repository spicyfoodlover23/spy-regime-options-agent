# SPY Macro-Regime Options Agent
### Alpaca AI Trading Agents Hackathon 2026

An autonomous quantitative trading agent that detects macro market regimes using a machine learning ensemble and executes SPY options positions accordingly via Alpaca's Trading API and CLI.

---

## What It Does

Most trading agents react to price. This one reads the macro environment.

The agent asks one question before every trade:
**Is the market structurally Risk-On or Risk-Off right now?**

- **Risk-On (1)** → Buy SPY ATM Calls (7–14 DTE)
- **Risk-Off (0)** → Buy SPY ATM Puts (7–14 DTE)
- **No regime change** → Hold, preserve capital

---

## Architecture


**Stage 1 — Signal Generation (`live_signal.py`)**
Downloads daily SPY, VIX, and Treasury yield data. Calculates RSI, Bollinger Band Width, SMA-200, and yield spread features. An ML ensemble (Random Forest + SVM + Logistic Regression) outputs a binary regime signal written to `paper_trading_log.csv`.

**Stage 2 — Execution (`alpaca_agent.py`)**
Reads today's vs yesterday's regime signal. On regime change: closes existing position first, scans ATM SPY contracts in 7–14 DTE window, sizes position at 3% equity cap ($3,000 max), and submits market order via Alpaca SDK. CLI subprocess called every run for audit logging.

---

## ML Model Details

| Feature | Purpose |
|---|---|
| VIX (5-day avg) | Market fear gauge |
| Yield Spread (10Y-2Y) | Recession signal |
| RSI (14) | Momentum exhaustion |
| Bollinger Band Width | Volatility compression |
| Lagged Return 1 & 2 | Recent price momentum |

**Ensemble:** Random Forest + SVM (CalibratedClassifierCV) + Logistic Regression
**Voting:** Soft (probability-weighted)
**Training:** 10 years SPY daily data (2015–2023)
**Test periods:** 2016–2019, 2022, 2024–2026

---

## Backtest Results

| Period | Market Type | Strategy Return | SPY Return | Strategy Sharpe |
|---|---|---|---|---|
| 2016–2019 | Low-vol bull | +98.7% | +71.1% | 1.56 |
| 2022 | Inflation bear | +28.0% | -18.2% | 2.04 |
| 2024–2026 | Bull + VIX crash | +92.9% | +58.0% | 2.46 |

---

## Risk Management

- **Position sizing:** 3% equity cap ($3,000 max per trade on $100k account)
- **Sequence protection:** Always close existing position before opening new
- **Theta defense:** Auto-rolls positions when DTE ≤ 7 days
- **Contract selection:** ATM only, strictly 7–14 DTE window
- **CLI audit:** Alpaca CLI subprocess called on every execution run

---

## Forward Testing

Signal validated on 2+ months of live market data via Windows Task Scheduler before hackathon deployment. Daily signals logged to `paper_trading_log.csv` — regime calls cross-referenced against actual SPY performance.

---

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file with your Alpaca credentials
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
ALPACA_PAPER=true

# Run signal generator
python live_signal.py

# Run execution agent
python alpaca_agent.py
```

---

## Alpaca Infrastructure

- **Trading API:** Order submission, position management, account monitoring
- **Python SDK (alpaca-py):** Primary execution interface
- **CLI Integration:** `subprocess` calls to Alpaca CLI for audit logging on every run
- **Paper Environment:** All trading conducted in Alpaca paper account

---

## Project Structure

spy-regime-options-agent/
├── live_signal.py # ML signal generator (runs daily at 3pm)
├── alpaca_agent.py # Autonomous execution agent
├── gold_live_signal.py # Gold regime model (parallel system)
├── requirements.txt # Dependencies
└── README.md


---

*Built solo. From a laptop in Phnom Penh, Cambodia.*
*Alpaca AI Trading Agents Hackathon 2026*
