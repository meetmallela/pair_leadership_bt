# Pair Leadership Intraday Strategy

An intraday directional trading strategy on **NIFTY 50**, driven by leadership alignment between **Reliance Industries** and **HDFC Bank**, filtered by **India VIX regime**.

Fully backtested (2021–2026), analysed through Phase-2 options proxying, and currently running in **live paper trading** mode.

---

## Hypothesis

> When major index constituents (Reliance + HDFC Bank) align directionally with structural conviction, NIFTY follows — but only in specific time windows and volatility regimes.

---

## Strategy Rules (Phase-1.75 v2 — LOCKED)

| Parameter | Value |
|-----------|-------|
| Entry signal | Reliance AND HDFCBank both show BULLISH or BEARISH bias |
| Bias definition | Close > VWAP + structure break (3-candle high/low) + volume > 1.2× 20-period avg |
| Time windows | 11:00–11:30, 12:00–12:30, 13:00–13:30 IST |
| VIX gate (overnight) | Yesterday's VIX close ∈ [13, 20) AND rising vs day-before — checked once at startup |
| VIX gate (intraday) | Live WebSocket VIX at signal time must still be ∈ [13, 20) AND above yesterday's close |
| Max trades/day | 1 |
| Stop-loss | Fixed 20 NIFTY points from entry |
| Force exit | 14:45 IST |
| Instrument | NIFTY spot (backtest) / ATM CE or PE (paper trading, BS proxy) |

---

## Backtest Results (2021–2026, 1 lot)

### Spot (Phase-1.75 v2)

| Metric | Value |
|--------|-------|
| Trades | 135 |
| Win rate | 50% |
| Avg win | +9.30 pts |
| Avg loss | −6.63 pts |
| Expectancy | **+1.28 pts/trade** |
| Max drawdown | −71 pts |

### Options — BS Proxy (gross, 1 lot = 50 units)

| Metric | Value |
|--------|-------|
| Expectancy | +Rs 36/trade |
| Total P&L | +Rs 4,863 |
| Max drawdown | −Rs 1,769 |
| Ann. return | 7.7% (gross) |

### After Transaction Costs (Rs 60/lot round trip)

| Lots | Ann. Return | Break-even? |
|------|-------------|-------------|
| 1 | −5.2% | No |
| 3 | +0.6% | **Break-even** |
| 5 | +1.7% | Yes |
| 10 | +2.6% | Yes |

---

## Project Structure

```
pair_leadership_bt/
│
├── strategies/
│   ├── scenario3_phase1_bt_csv.py          # Baseline (no filters)
│   ├── scenario3_phase1_5_bt_csv.py        # Time filter only
│   ├── scenario3_phase1_75_bt_csv.py       # Time + VIX gate (v1)
│   └── scenario3_phase1_75_v2_bt_csv.py   # LOCKED v2 (VIX >= 13)
│
├── analysis/
│   ├── time_of_day_analysis.py             # Identified 11/12/13h windows
│   ├── vix_overlay_analysis.py             # Confirmed MEDIUM+RISING regime
│   ├── year_wise_analysis.py
│   ├── prepare_indiavix_daily.py
│   └── plot_phase1_75_equity.py
│
├── phase2/
│   ├── bs_proxy_backtest.py                # Black-Scholes option proxy
│   ├── phase2_full_analysis.py             # Equity curve, capital efficiency, payoff opt
│   ├── transaction_cost_analysis.py        # Cost impact (options vs futures)
│   ├── lot_scaling_analysis.py             # Break-even lot size
│   └── utils/option_resolver.py
│
├── ingestion/
│   ├── download_1m_data.py                 # Nifty / Reliance / HDFCBank 1-min OHLCV
│   └── download_indiavix_1m.py             # India VIX
│
├── paper_trading/                          # Live paper trading system
│   ├── main.py                             # Entry point
│   ├── config.py                           # Locked v2 constants
│   ├── live_feed.py                        # WebSocket + 1-min candle aggregation
│   ├── signal_engine.py                    # Overnight + intraday VIX gates, VWAP, get_bias()
│   ├── paper_trader.py                     # Virtual trade lifecycle + BS P&L
│   ├── db.py                               # SQLite paper_trades table
│   ├── notifier.py                         # Telegram alerts
│   ├── sync.py                             # EOD CSV export + git push
│   └── results/                            # Daily trade CSVs (auto-committed)
│       └── YYYY-MM-DD.csv
│
├── output/                                 # Backtest trade CSVs and summaries
├── data/raw/indiavix_daily.csv             # Daily VIX closes (in repo)
├── Scenario3_PairLeadership_Research.md    # Full research whitepaper
└── .gitignore
```

> **Note:** Large 1-min raw CSVs (`nifty_1m.csv`, `reliance_1m.csv`, `hdfcbank_1m.csv`, `indiavix_1m.csv`) are excluded from git. Regenerate them with `ingestion/download_1m_data.py`.

---

## Paper Trading

The system runs live against Zerodha Kite market data with no real orders placed.

**Daily flow:**

```
09:00  Refresh access token in kite_config.json
09:10  python paper_trading/main.py
       → Checks overnight VIX gate (yesterday's close)
       → Telegram: VIX status + gate decision
11:00–13:30  Signal detection loop (every minute)
       → Pair consensus (Reliance + HDFCBank same bias)
       → Intraday VIX gate (live WebSocket VIX re-checked at signal time)
       → Telegram on entry / exit
15:35  Daily Telegram summary
       → Results auto-exported to paper_trading/results/YYYY-MM-DD.csv
       → git commit + push to GitHub
```

**Live results:**
[paper_trading/results/](https://github.com/meetmallela/pair_leadership_bt/tree/master/paper_trading/results)

**Instrument tokens (Zerodha):**

| Instrument | Token |
|------------|-------|
| Nifty 50 | 256265 |
| Reliance | 738561 |
| HDFCBank | 341249 |
| India VIX | 264969 |

---

## Phase Evolution

| Phase | Trades | Expectancy | Status |
|-------|--------|------------|--------|
| Phase-1 (no filters) | 1,017 | −0.28 pts | Unprofitable |
| Phase-1.5 (time filter) | 251 | +0.36 pts | Marginal |
| Phase-1.75 v1 (time + VIX ≥ 12) | 172 | +0.92 pts | Good |
| **Phase-1.75 v2 (time + VIX ≥ 13)** | **135** | **+1.28 pts** | **LOCKED** |

---

## Key Findings

- **Signal edge is real** — non-random, structurally explained, validated across 5 years
- **2023 failure explained** — VIX 12–13 is a pseudo-MEDIUM zone with insufficient realized volatility; raising the floor to 13 fixed it
- **Futures unviable** — Rs 600/trade cost destroys the edge at this frequency (~27 trades/year)
- **Options viable at 3+ lots** — break-even at 3 lots (realistic cost model: fixed Rs 40 + Rs 20/lot)
- **Best year: 2024** (+3.71 pts expectancy) — worst: 2023 (−1.58 pts, now largely filtered)

---

## Go-Live Criteria

After 3–6 months of paper trading, move to live at **3 lots minimum** if:
- Out-of-sample win rate ≥ 45%
- Net expectancy (after Rs 100 cost at 3 lots) is positive

---

## Full Research Document

See [`Scenario3_PairLeadership_Research.md`](Scenario3_PairLeadership_Research.md) for the complete research whitepaper covering all phases, VIX analysis, transaction cost study, lot scaling, and paper trading setup.
