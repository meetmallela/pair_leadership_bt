# phase2/transaction_cost_analysis.py
"""
Transaction Cost Impact Analysis — Phase-1.75 v2

Applies real-world round-trip transaction costs to every trade and
compares gross vs net P&L for both instrument types.

Cost assumptions (round trip = 1 buy + 1 sell):
  Options (ATM CE/PE, 1 lot)  : Rs 60
  Futures (NIFTY FUT, 1 lot)  : Rs 600
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.stats import norm
from datetime import date, timedelta

# ================= PATHS =================

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V2_TRADES   = os.path.join(BASE_DIR, "output", "scenario3_phase1_75_v2_trades.csv")
BS_V2       = os.path.join(BASE_DIR, "phase2", "output", "v2", "bs_proxy_v2_trades.csv")
OUT_DIR     = os.path.join(BASE_DIR, "phase2", "output", "v2")
os.makedirs(OUT_DIR, exist_ok=True)

# ================= COST CONFIG =================

OPTIONS_COST_PER_TRADE = 60    # Rs round trip (buy + sell), 1 lot
FUTURES_COST_PER_TRADE = 600   # Rs round trip (buy + sell), 1 lot
LOT_SIZE               = 50    # NIFTY lot size

# ================= LOAD DATA =================

spot   = pd.read_csv(V2_TRADES, parse_dates=["entry_time", "exit_time", "date"])
bs     = pd.read_csv(BS_V2,     parse_dates=["entry_time", "exit_time"])

spot["year"] = pd.to_datetime(spot["date"]).dt.year
bs["year"]   = pd.to_datetime(bs["entry_time"]).dt.year

# ================= FUTURES P&L =================

spot["futures_pnl_gross"] = spot["pnl_points"] * LOT_SIZE
spot["futures_pnl_net"]   = spot["futures_pnl_gross"] - FUTURES_COST_PER_TRADE

# ================= OPTIONS P&L =================

bs["options_pnl_gross"] = bs["option_pnl_rupees"]
bs["options_pnl_net"]   = bs["option_pnl_rupees"] - OPTIONS_COST_PER_TRADE

# ================= MERGE =================

merged = pd.DataFrame({
    "date"               : spot["date"].values,
    "year"               : spot["year"].values,
    "entry_time"         : spot["entry_time"].values,
    "direction"          : spot["direction"].values,
    "spot_pnl_pts"       : spot["pnl_points"].values,
    "futures_gross_rs"   : spot["futures_pnl_gross"].values,
    "futures_net_rs"     : spot["futures_pnl_net"].values,
    "options_gross_rs"   : bs["options_pnl_gross"].values,
    "options_net_rs"     : bs["options_pnl_net"].values,
})

# ================= SUMMARY FUNCTION =================

def summarise(series, label):
    wins = series[series > 0]
    loss = series[series <= 0]
    eq   = series.cumsum()
    dd   = (eq - eq.cummax()).min()
    return {
        "instrument"     : label,
        "trades"         : len(series),
        "win_rate_pct"   : round((series > 0).mean() * 100, 1),
        "avg_win_rs"     : round(wins.mean(), 2) if not wins.empty else 0,
        "avg_loss_rs"    : round(loss.mean(), 2) if not loss.empty else 0,
        "expectancy_rs"  : round(series.mean(), 2),
        "total_pnl_rs"   : round(series.sum(), 2),
        "max_dd_rs"      : round(dd, 2),
    }

# ================= PRINT RESULTS =================

rows = [
    summarise(merged["futures_gross_rs"], "Futures GROSS"),
    summarise(merged["futures_net_rs"],   "Futures NET   (after Rs600/trade)"),
    summarise(merged["options_gross_rs"], "Options GROSS"),
    summarise(merged["options_net_rs"],   "Options NET   (after Rs60/trade)"),
]
summary_df = pd.DataFrame(rows)

print("\n" + "=" * 68)
print("  Transaction Cost Impact — Phase-1.75 v2 (135 trades, 1 lot)")
print("=" * 68)
print(f"  Options cost per trade (round trip): Rs {OPTIONS_COST_PER_TRADE}")
print(f"  Futures cost per trade (round trip): Rs {FUTURES_COST_PER_TRADE}")
print(f"  Lot size: {LOT_SIZE} units")
print("-" * 68)

for _, r in summary_df.iterrows():
    print(f"\n  [{r['instrument']}]")
    print(f"    Win rate    : {r['win_rate_pct']}%")
    print(f"    Avg win     : Rs {r['avg_win_rs']:,.2f}")
    print(f"    Avg loss    : Rs {r['avg_loss_rs']:,.2f}")
    print(f"    Expectancy  : Rs {r['expectancy_rs']:+,.2f} per trade")
    print(f"    Total P&L   : Rs {r['total_pnl_rs']:+,.2f}")
    print(f"    Max DD      : Rs {r['max_dd_rs']:,.2f}")

# Cost drag
opt_drag = OPTIONS_COST_PER_TRADE * len(merged)
fut_drag = FUTURES_COST_PER_TRADE * len(merged)
print(f"\n  Total cost drag over {len(merged)} trades:")
print(f"    Options : Rs {opt_drag:,}  ({opt_drag / merged['options_gross_rs'].sum() * 100:.1f}% of gross P&L)")
print(f"    Futures : Rs {fut_drag:,}  ({fut_drag / merged['futures_gross_rs'].sum() * 100:.1f}% of gross P&L)")
print("=" * 68)

# ================= YEAR-WISE NET P&L =================

print("\n  Year-wise NET P&L comparison:")
yr_rows = []
for yr, grp in merged.groupby("year"):
    yr_rows.append({
        "year"               : yr,
        "trades"             : len(grp),
        "futures_gross"      : round(grp["futures_gross_rs"].sum(), 0),
        "futures_net"        : round(grp["futures_net_rs"].sum(), 0),
        "options_gross"      : round(grp["options_gross_rs"].sum(), 0),
        "options_net"        : round(grp["options_net_rs"].sum(), 0),
    })

yr_df = pd.DataFrame(yr_rows)
print(yr_df.to_string(index=False))

# ================= SAVE =================

summary_df.to_csv(os.path.join(OUT_DIR, "transaction_cost_summary.csv"), index=False)
yr_df.to_csv(os.path.join(OUT_DIR, "transaction_cost_year_wise.csv"), index=False)
merged.to_csv(os.path.join(OUT_DIR, "transaction_cost_trades.csv"), index=False)

# ================= CHART =================

fig, axes = plt.subplots(1, 3, figsize=(16, 5))
fig.suptitle("Transaction Cost Impact — Phase-1.75 v2 (135 trades, 1 lot)\n"
             "Options: Rs60/trade  |  Futures: Rs600/trade",
             fontsize=13, fontweight="bold")

# --- Cumulative P&L curves (all 4 lines) ---
ed = pd.to_datetime(merged["entry_time"])
axes[0].plot(ed, merged["futures_gross_rs"].cumsum(), color="#FF9800", lw=2,    label="Futures GROSS")
axes[0].plot(ed, merged["futures_net_rs"].cumsum(),   color="#E65100", lw=2,    linestyle="--", label="Futures NET")
axes[0].plot(ed, merged["options_gross_rs"].cumsum(), color="#2196F3", lw=2,    label="Options GROSS")
axes[0].plot(ed, merged["options_net_rs"].cumsum(),   color="#0D47A1", lw=2,    linestyle="--", label="Options NET")
axes[0].axhline(0, color="gray", lw=0.8, linestyle=":")
axes[0].set_title("Cumulative P&L: Gross vs Net", fontsize=10)
axes[0].set_ylabel("Rs")
axes[0].legend(fontsize=8)
axes[0].grid(True, alpha=0.3)
axes[0].tick_params(axis="x", rotation=30)

# --- Year-wise net P&L bar chart ---
x = np.arange(len(yr_df))
w = 0.35
axes[1].bar(x - w/2, yr_df["options_net"], w, color="#2196F3", label="Options NET", edgecolor="white")
axes[1].bar(x + w/2, yr_df["futures_net"], w, color="#E65100", label="Futures NET", edgecolor="white")
axes[1].axhline(0, color="gray", lw=0.8)
axes[1].set_xticks(x)
axes[1].set_xticklabels(yr_df["year"].astype(str))
axes[1].set_title("Year-wise NET P&L", fontsize=10)
axes[1].set_ylabel("Rs")
axes[1].legend(fontsize=8)
axes[1].grid(True, alpha=0.3, axis="y")

# --- Gross vs Net total bar ---
labels  = ["Options\nGROSS", "Options\nNET", "Futures\nGROSS", "Futures\nNET"]
values  = [
    merged["options_gross_rs"].sum(),
    merged["options_net_rs"].sum(),
    merged["futures_gross_rs"].sum(),
    merged["futures_net_rs"].sum(),
]
colors  = ["#64B5F6", "#0D47A1", "#FFB74D", "#E65100"]
bars = axes[2].bar(labels, values, color=colors, edgecolor="white")
axes[2].axhline(0, color="gray", lw=0.8)
axes[2].set_title("Total P&L: Gross vs Net (5 years)", fontsize=10)
axes[2].set_ylabel("Rs")
axes[2].grid(True, alpha=0.3, axis="y")
for bar, val in zip(bars, values):
    axes[2].text(bar.get_x() + bar.get_width()/2,
                 val + (100 if val >= 0 else -300),
                 f"Rs{val:+,.0f}", ha="center", fontsize=8, fontweight="bold")

plt.tight_layout()
chart_path = os.path.join(OUT_DIR, "transaction_cost_analysis.png")
plt.savefig(chart_path, dpi=150, bbox_inches="tight")
plt.close()
print(f"\n  Chart saved: {chart_path}")
