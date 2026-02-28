# phase2/phase2_full_analysis.py
"""
Phase-2 Full Analysis — Three parts in sequence

Part 1: Equity Curve
    - Cumulative option P&L over time (₹)
    - Spot P&L overlaid (scaled to ₹ for comparison)
    - Year-boundary markers
    - Drawdown subplot

Part 2: Capital Efficiency
    - Capital at risk per trade = entry_option_px × lot_size (premium paid)
    - Conservative capital = max(per-trade premium) + |max_drawdown|
    - Return on capital (total, annualized, year-wise)
    - Trades per year and avg capital deployed

Part 3: Payoff Optimization
    - Re-price each trade across 5 strike offsets:
      -100 (ITM), -50, 0 (ATM baseline), +50, +100 (OTM)
      Positive offset = OTM direction for each option type
    - Compare: total P&L, win rate, avg win, avg loss, expectancy, max DD
    - Output table + bar chart
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")           # non-interactive backend (saves to file)
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.stats import norm
from datetime import date, timedelta

# ================= PATHS =================

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRADES_CSV = os.path.join(BASE_DIR, "phase2", "output", "bs_proxy_trades.csv")
VIX_CSV    = os.path.join(BASE_DIR, "data", "raw", "indiavix_daily.csv")
OUT_DIR    = os.path.join(BASE_DIR, "phase2", "output")
os.makedirs(OUT_DIR, exist_ok=True)

# ================= SHARED CONFIG =================

LOT_SIZE           = 50
RISK_FREE_RATE     = 0.065
MIN_T              = 1 / 365
MIN_IV             = 0.05
EXPIRY_CHANGE_DATE = date(2024, 10, 21)

# ================= BLACK-SCHOLES =================

def bs_price(S, K, T, r, sigma, option_type):
    if T <= 0:
        return max(S - K, 0) if option_type == "CE" else max(K - S, 0)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == "CE":
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return max(float(price), 0.0)

def get_next_expiry(trade_date):
    target_weekday = 0 if trade_date >= EXPIRY_CHANGE_DATE else 3
    for i in range(1, 8):
        d = trade_date + timedelta(days=i)
        if d.weekday() == target_weekday:
            return d
    return trade_date + timedelta(days=7)

# ================= LOAD DATA =================

trades = pd.read_csv(TRADES_CSV, parse_dates=["entry_time", "exit_time", "date"])
trades["date"] = pd.to_datetime(trades["date"]).dt.date
trades["year"] = pd.to_datetime(trades["date"]).dt.year

vix_df = pd.read_csv(VIX_CSV, parse_dates=["date"])
vix_df["date"] = vix_df["date"].dt.date
vix_dict = dict(zip(vix_df["date"], vix_df["close"]))

print(f"Loaded {len(trades)} trades  |  Years: {trades['year'].min()}–{trades['year'].max()}")

# ================================================================
# PART 1: EQUITY CURVE
# ================================================================

print("\n" + "=" * 55)
print("  PART 1: Equity Curve")
print("=" * 55)

trades["cum_pnl"]       = trades["option_pnl_rupees"].cumsum()
trades["cum_spot_rs"]   = (trades["spot_pnl_points"] * LOT_SIZE).cumsum()
trades["peak"]          = trades["cum_pnl"].cummax()
trades["drawdown"]      = trades["cum_pnl"] - trades["peak"]

max_dd      = trades["drawdown"].min()
total_pnl   = trades["cum_pnl"].iloc[-1]
total_spot  = trades["cum_spot_rs"].iloc[-1]

print(f"  Option total P&L : Rs {total_pnl:+,.2f}")
print(f"  Spot   total P&L : Rs {total_spot:+,.2f}  (scaled, for comparison)")
print(f"  Max drawdown     : Rs {max_dd:,.2f}")

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 9),
                                gridspec_kw={"height_ratios": [3, 1]},
                                sharex=True)
fig.suptitle("Phase-2B: Equity Curve — BS Option Proxy vs Spot (scaled)\n"
             "ATM CE/PE  |  1 lot  |  India VIX as IV  |  2021-2026",
             fontsize=13, fontweight="bold")

entry_dates = pd.to_datetime(trades["entry_time"])

# Equity curves
ax1.plot(entry_dates, trades["cum_pnl"],     color="#2196F3", lw=2,   label="Option P&L (Rs)")
ax1.plot(entry_dates, trades["cum_spot_rs"], color="#FF9800", lw=1.5, linestyle="--",
         alpha=0.7, label=f"Spot P&L scaled (pts x {LOT_SIZE})")
ax1.axhline(0, color="gray", lw=0.8, linestyle=":")
ax1.fill_between(entry_dates, trades["cum_pnl"], 0,
                 where=trades["cum_pnl"] >= 0, alpha=0.08, color="#2196F3")
ax1.fill_between(entry_dates, trades["cum_pnl"], 0,
                 where=trades["cum_pnl"] < 0,  alpha=0.08, color="#F44336")

# Year boundary lines
for yr in range(trades["year"].min() + 1, trades["year"].max() + 1):
    first_in_year = trades[trades["year"] == yr]
    if not first_in_year.empty:
        xval = pd.to_datetime(first_in_year["entry_time"].iloc[0])
        ax1.axvline(xval, color="gray", lw=0.7, linestyle=":")
        ax1.text(xval, ax1.get_ylim()[0] if ax1.get_ylim()[0] != 0 else -200,
                 str(yr), fontsize=8, color="gray", ha="left")

ax1.set_ylabel("Cumulative P&L (Rs)", fontsize=10)
ax1.legend(fontsize=9)
ax1.set_title(f"Total option P&L: Rs {total_pnl:+,.0f}  |  "
              f"Total spot P&L: Rs {total_spot:+,.0f}  |  "
              f"Max DD: Rs {max_dd:,.0f}", fontsize=9)
ax1.grid(True, alpha=0.3)

# Drawdown subplot
ax2.fill_between(entry_dates, trades["drawdown"], 0, color="#F44336", alpha=0.5)
ax2.axhline(0, color="gray", lw=0.8)
ax2.set_ylabel("Drawdown (Rs)", fontsize=10)
ax2.set_xlabel("Trade date", fontsize=10)
ax2.grid(True, alpha=0.3)
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
plt.xticks(rotation=30)

plt.tight_layout()
eq_path = os.path.join(OUT_DIR, "equity_curve.png")
plt.savefig(eq_path, dpi=150, bbox_inches="tight")
plt.close()
print(f"  Saved: {eq_path}")

# ================================================================
# PART 2: CAPITAL EFFICIENCY
# ================================================================

print("\n" + "=" * 55)
print("  PART 2: Capital Efficiency")
print("=" * 55)

trades["capital_per_trade"] = trades["entry_option_px"] * LOT_SIZE

max_capital      = trades["capital_per_trade"].max()
avg_capital      = trades["capital_per_trade"].mean()
# Conservative allocation: worst-case premium + absorb max drawdown
conservative_cap = max_capital + abs(max_dd)

# Annualized return
years_span = (pd.to_datetime(trades["entry_time"].max()) -
              pd.to_datetime(trades["entry_time"].min())).days / 365
ann_return_pct   = (total_pnl / conservative_cap) / years_span * 100

# Year-wise capital efficiency
year_eff = []
for yr, grp in trades.groupby("year"):
    yr_pnl     = grp["option_pnl_rupees"].sum()
    yr_cap     = grp["capital_per_trade"].max()   # peak premium that year
    yr_ret_pct = (yr_pnl / yr_cap * 100) if yr_cap > 0 else 0
    yr_eq      = grp["option_pnl_rupees"].cumsum()
    yr_dd      = (yr_eq - yr_eq.cummax()).min()
    year_eff.append({
        "year"          : yr,
        "trades"        : len(grp),
        "total_pnl_rs"  : round(yr_pnl, 2),
        "peak_premium_rs": round(yr_cap, 2),
        "return_on_cap_pct": round(yr_ret_pct, 1),
        "max_dd_rs"     : round(yr_dd, 2),
    })

eff_df = pd.DataFrame(year_eff)

print(f"  Avg premium per trade    : Rs {avg_capital:,.0f}")
print(f"  Max premium (single trd) : Rs {max_capital:,.0f}")
print(f"  Conservative capital     : Rs {conservative_cap:,.0f}  "
      f"(max premium + |max DD|)")
print(f"  Total P&L over {years_span:.1f} yrs    : Rs {total_pnl:+,.2f}")
print(f"  Annualized return        : {ann_return_pct:.1f}%  (on conservative capital)")
print(f"\n  Year-wise return on capital (peak premium that year):")
print(eff_df.to_string(index=False))

eff_df.to_csv(os.path.join(OUT_DIR, "capital_efficiency.csv"), index=False)

# Capital efficiency bar chart
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
fig.suptitle("Phase-2B: Capital Efficiency  |  1 lot ATM option",
             fontsize=13, fontweight="bold")

colors = ["#4CAF50" if v >= 0 else "#F44336" for v in eff_df["total_pnl_rs"]]
axes[0].bar(eff_df["year"].astype(str), eff_df["total_pnl_rs"], color=colors, edgecolor="white")
axes[0].axhline(0, color="gray", lw=0.8)
axes[0].set_title("Annual P&L (Rs)", fontsize=10)
axes[0].set_ylabel("Rs")
axes[0].grid(True, alpha=0.3, axis="y")
for i, (y, v) in enumerate(zip(eff_df["year"], eff_df["total_pnl_rs"])):
    axes[0].text(i, v + (50 if v >= 0 else -120), f"Rs{v:+,.0f}", ha="center", fontsize=8)

colors2 = ["#4CAF50" if v >= 0 else "#F44336" for v in eff_df["return_on_cap_pct"]]
axes[1].bar(eff_df["year"].astype(str), eff_df["return_on_cap_pct"], color=colors2, edgecolor="white")
axes[1].axhline(0, color="gray", lw=0.8)
axes[1].set_title("Return on Peak Capital (%)", fontsize=10)
axes[1].set_ylabel("%")
axes[1].grid(True, alpha=0.3, axis="y")
for i, (y, v) in enumerate(zip(eff_df["year"], eff_df["return_on_cap_pct"])):
    axes[1].text(i, v + (0.5 if v >= 0 else -2), f"{v:+.1f}%", ha="center", fontsize=8)

plt.tight_layout()
cap_path = os.path.join(OUT_DIR, "capital_efficiency.png")
plt.savefig(cap_path, dpi=150, bbox_inches="tight")
plt.close()
print(f"  Saved: {cap_path}")

# ================================================================
# PART 3: PAYOFF OPTIMIZATION — STRIKE OFFSETS
# ================================================================

print("\n" + "=" * 55)
print("  PART 3: Payoff Optimization (Strike Offsets)")
print("=" * 55)

OFFSETS = [-100, -50, 0, 50, 100]  # positive = OTM for each option type

def reprice_at_offset(trades_df, offset):
    """
    Re-price every trade at ATM + offset (OTM direction).
    For CE (BULLISH): strike = atm + offset  (positive = higher strike = OTM)
    For PE (BEARISH): strike = atm - offset  (positive = lower strike = OTM)
    """
    rows = []
    for _, row in trades_df.iterrows():
        trade_date  = row["date"]
        entry_spot  = row["entry_spot"]
        exit_spot   = row["exit_spot"]
        option_type = row["option_type"]
        entry_time  = row["entry_time"]
        exit_time   = row["exit_time"]

        atm = int(round(entry_spot / 50) * 50)
        if option_type == "CE":
            strike = atm + offset
        else:
            strike = atm - offset

        strike = max(strike, 50)   # floor at 50 (can't have negative strike)

        vix_val = vix_dict.get(trade_date, 15.0)
        sigma   = max(vix_val / 100.0, MIN_IV)

        expiry  = get_next_expiry(trade_date)
        T_entry = max((expiry - entry_time.date()).days / 365.0, MIN_T)
        T_exit  = max((expiry - exit_time.date()).days  / 365.0, MIN_T)

        entry_opt = bs_price(entry_spot, strike, T_entry, RISK_FREE_RATE, sigma, option_type)
        exit_opt  = bs_price(exit_spot,  strike, T_exit,  RISK_FREE_RATE, sigma, option_type)

        pnl_per_unit = exit_opt - entry_opt
        pnl_rupees   = pnl_per_unit * LOT_SIZE

        rows.append({
            "entry_option_px" : round(entry_opt, 2),
            "pnl_rupees"      : round(pnl_rupees, 2),
        })
    return pd.DataFrame(rows)

opt_results = []
for off in OFFSETS:
    label = f"ATM{off:+d}" if off != 0 else "ATM (baseline)"
    repriced = reprice_at_offset(trades, off)

    pnl  = repriced["pnl_rupees"]
    wins = pnl[pnl > 0]
    lss  = pnl[pnl <= 0]
    eq   = pnl.cumsum()
    dd   = (eq - eq.cummax()).min()
    avg_prem = repriced["entry_option_px"].mean()

    opt_results.append({
        "strike_offset" : off,
        "label"         : label,
        "avg_premium_rs": round(avg_prem, 2),
        "win_rate_pct"  : round((pnl > 0).mean() * 100, 1),
        "avg_win_rs"    : round(wins.mean(), 2) if not wins.empty else 0,
        "avg_loss_rs"   : round(lss.mean(), 2)  if not lss.empty  else 0,
        "expectancy_rs" : round(pnl.mean(), 2),
        "total_pnl_rs"  : round(pnl.sum(), 2),
        "max_dd_rs"     : round(dd, 2),
    })

opt_df = pd.DataFrame(opt_results)
print(opt_df.to_string(index=False))
opt_df.to_csv(os.path.join(OUT_DIR, "payoff_optimization.csv"), index=False)

# Payoff optimization chart
fig, axes = plt.subplots(1, 3, figsize=(16, 5))
fig.suptitle("Phase-2B: Payoff Optimization — Strike Offset Comparison\n"
             "Positive offset = OTM  |  Negative = ITM  |  1 lot",
             fontsize=13, fontweight="bold")

labels = opt_df["label"].str.replace(" (baseline)", "", regex=False)
colors_pnl = ["#4CAF50" if v >= 0 else "#F44336" for v in opt_df["total_pnl_rs"]]

# Total P&L
axes[0].bar(labels, opt_df["total_pnl_rs"], color=colors_pnl, edgecolor="white")
axes[0].axhline(0, color="gray", lw=0.8)
axes[0].set_title("Total P&L (Rs)", fontsize=10)
axes[0].set_ylabel("Rs")
axes[0].grid(True, alpha=0.3, axis="y")
for i, v in enumerate(opt_df["total_pnl_rs"]):
    axes[0].text(i, v + (50 if v >= 0 else -150), f"Rs{v:+,.0f}", ha="center", fontsize=7.5)
plt.setp(axes[0].xaxis.get_majorticklabels(), rotation=30)

# Expectancy
colors_exp = ["#4CAF50" if v >= 0 else "#F44336" for v in opt_df["expectancy_rs"]]
axes[1].bar(labels, opt_df["expectancy_rs"], color=colors_exp, edgecolor="white")
axes[1].axhline(0, color="gray", lw=0.8)
axes[1].set_title("Expectancy per Trade (Rs)", fontsize=10)
axes[1].set_ylabel("Rs")
axes[1].grid(True, alpha=0.3, axis="y")
for i, v in enumerate(opt_df["expectancy_rs"]):
    axes[1].text(i, v + (1 if v >= 0 else -5), f"Rs{v:+.0f}", ha="center", fontsize=7.5)
plt.setp(axes[1].xaxis.get_majorticklabels(), rotation=30)

# Max Drawdown (show as positive for readability)
axes[2].bar(labels, opt_df["max_dd_rs"].abs(), color="#FF9800", edgecolor="white")
axes[2].set_title("Max Drawdown (Rs, lower = better)", fontsize=10)
axes[2].set_ylabel("Rs")
axes[2].grid(True, alpha=0.3, axis="y")
for i, v in enumerate(opt_df["max_dd_rs"]):
    axes[2].text(i, abs(v) + 20, f"Rs{v:,.0f}", ha="center", fontsize=7.5)
plt.setp(axes[2].xaxis.get_majorticklabels(), rotation=30)

plt.tight_layout()
opt_path = os.path.join(OUT_DIR, "payoff_optimization.png")
plt.savefig(opt_path, dpi=150, bbox_inches="tight")
plt.close()
print(f"  Saved: {opt_path}")

# ================= FINAL SUMMARY =================

print("\n" + "=" * 55)
print("  ALL THREE ANALYSES COMPLETE")
print("=" * 55)
print(f"  equity_curve.png         : {os.path.join(OUT_DIR, 'equity_curve.png')}")
print(f"  capital_efficiency.png   : {os.path.join(OUT_DIR, 'capital_efficiency.png')}")
print(f"  capital_efficiency.csv   : {os.path.join(OUT_DIR, 'capital_efficiency.csv')}")
print(f"  payoff_optimization.png  : {os.path.join(OUT_DIR, 'payoff_optimization.png')}")
print(f"  payoff_optimization.csv  : {os.path.join(OUT_DIR, 'payoff_optimization.csv')}")
