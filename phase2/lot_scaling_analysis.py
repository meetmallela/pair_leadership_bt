# phase2/lot_scaling_analysis.py
"""
Lot Scaling Analysis — Phase-1.75 v2

Tests options P&L across 1 to 10 lots to find the break-even
and viable lot sizes after transaction costs.

Cost assumption: Rs 60 per trade per lot (scales linearly)
  - STT, exchange charges, stamp duty scale with lots
  - Brokerage (flat Rs 20/order) is a minor component

Conservative capital per lot = max(entry_option_px * 50) + |max_DD_1lot|
  = ~Rs 13,586 per lot
"""

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ================= PATHS =================

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BS_V2     = os.path.join(BASE_DIR, "phase2", "output", "v2", "bs_proxy_v2_trades.csv")
OUT_DIR   = os.path.join(BASE_DIR, "phase2", "output", "v2")
os.makedirs(OUT_DIR, exist_ok=True)

# ================= CONFIG =================

LOT_SIZE              = 50     # units per lot
OPTIONS_COST_PER_LOT  = 60     # Rs per lot per round trip
CAPITAL_PER_LOT       = 13586  # conservative capital per lot (Rs)

LOTS_TO_TEST = [1, 2, 3, 4, 5, 7, 10]

# ================= LOAD =================

bs = pd.read_csv(BS_V2, parse_dates=["entry_time", "exit_time"])
bs["year"] = pd.to_datetime(bs["entry_time"]).dt.year

# ================= SCALING LOOP =================

results = []

for n in LOTS_TO_TEST:
    pnl_per_trade = bs["option_pnl_per_unit"] * LOT_SIZE * n  # gross per trade
    cost_per_trade = OPTIONS_COST_PER_LOT * n                  # cost per trade
    net_per_trade  = pnl_per_trade - cost_per_trade

    wins = net_per_trade[net_per_trade > 0]
    loss = net_per_trade[net_per_trade <= 0]
    eq   = net_per_trade.cumsum()
    dd   = (eq - eq.cummax()).min()

    capital_required = CAPITAL_PER_LOT * n
    years_span = (pd.to_datetime(bs.entry_time.max()) -
                  pd.to_datetime(bs.entry_time.min())).days / 365
    ann_return = (net_per_trade.sum() / capital_required) / years_span * 100

    results.append({
        "lots"             : n,
        "units"            : n * LOT_SIZE,
        "cost_per_trade_rs": cost_per_trade,
        "total_cost_rs"    : cost_per_trade * len(bs),
        "win_rate_pct"     : round((net_per_trade > 0).mean() * 100, 1),
        "avg_win_rs"       : round(wins.mean(), 2) if not wins.empty else 0,
        "avg_loss_rs"      : round(loss.mean(), 2) if not loss.empty else 0,
        "expectancy_rs"    : round(net_per_trade.mean(), 2),
        "total_pnl_rs"     : round(net_per_trade.sum(), 2),
        "max_dd_rs"        : round(dd, 2),
        "capital_reqd_rs"  : capital_required,
        "ann_return_pct"   : round(ann_return, 1),
    })

df = pd.DataFrame(results)

# ================= PRINT =================

print("\n" + "=" * 75)
print("  Lot Scaling Analysis — Phase-1.75 v2 Options (ATM CE/PE)")
print("  Cost: Rs 60 per lot per round trip (scales linearly)")
print("=" * 75)
print(f"\n  {'Lots':>4}  {'Units':>5}  {'Cost/Trd':>8}  {'Win%':>5}  "
      f"{'Expect':>8}  {'TotalPnL':>10}  {'MaxDD':>10}  {'Capital':>10}  {'Ann Ret':>8}")
print("  " + "-" * 70)

for _, r in df.iterrows():
    flag = ""
    if r["expectancy_rs"] > 0 and r["ann_return_pct"] >= 10:
        flag = " <-- VIABLE"
    elif r["expectancy_rs"] > 0:
        flag = " <-- BREAK-EVEN+"
    print(f"  {int(r['lots']):>4}  {int(r['units']):>5}  "
          f"Rs{int(r['cost_per_trade_rs']):>6}  {r['win_rate_pct']:>5}%  "
          f"Rs{r['expectancy_rs']:>+7.0f}  "
          f"Rs{r['total_pnl_rs']:>+9,.0f}  "
          f"Rs{r['max_dd_rs']:>9,.0f}  "
          f"Rs{r['capital_reqd_rs']:>9,.0f}  "
          f"{r['ann_return_pct']:>7.1f}%{flag}")

print("=" * 75)

# ================= YEAR-WISE FOR KEY LOT SIZES =================

KEY_LOTS = [1, 3, 5, 10]
print("\n  Year-wise NET P&L by lot size:")
print(f"\n  {'Year':>4}", end="")
for n in KEY_LOTS:
    print(f"  {'%d lot' % n:>10}", end="")
print()
print("  " + "-" * (6 + 12 * len(KEY_LOTS)))

for yr, grp in bs.groupby("year"):
    print(f"  {yr:>4}", end="")
    for n in KEY_LOTS:
        net = (grp["option_pnl_per_unit"] * LOT_SIZE * n - OPTIONS_COST_PER_LOT * n).sum()
        print(f"  Rs{net:>+8,.0f}", end="")
    print()

print()

# Break-even point
be = df[df["expectancy_rs"] > 0].iloc[0] if not df[df["expectancy_rs"] > 0].empty else None
if be is not None:
    print(f"  Break-even lots: {int(be['lots'])} lot(s)  "
          f"(expectancy Rs{be['expectancy_rs']:+.0f}/trade, "
          f"total P&L Rs{be['total_pnl_rs']:+,.0f})")
print()

# ================= SAVE CSV =================

df.to_csv(os.path.join(OUT_DIR, "lot_scaling_summary.csv"), index=False)

# ================= CHART =================

fig, axes = plt.subplots(1, 3, figsize=(16, 5))
fig.suptitle("Lot Scaling Analysis — Phase-1.75 v2 Options (ATM CE/PE)\n"
             "Rs 60 transaction cost per lot per round trip",
             fontsize=13, fontweight="bold")

# --- Expectancy by lots ---
colors_exp = ["#4CAF50" if v > 0 else "#F44336" for v in df["expectancy_rs"]]
axes[0].bar(df["lots"].astype(str), df["expectancy_rs"], color=colors_exp, edgecolor="white")
axes[0].axhline(0, color="gray", lw=1)
axes[0].set_title("Net Expectancy per Trade (Rs)", fontsize=10)
axes[0].set_xlabel("Lots")
axes[0].set_ylabel("Rs")
axes[0].grid(True, alpha=0.3, axis="y")
for i, (lot, val) in enumerate(zip(df["lots"], df["expectancy_rs"])):
    axes[0].text(i, val + (5 if val >= 0 else -15),
                 f"Rs{val:+.0f}", ha="center", fontsize=8, fontweight="bold")

# --- Total P&L by lots ---
colors_pnl = ["#4CAF50" if v > 0 else "#F44336" for v in df["total_pnl_rs"]]
axes[1].bar(df["lots"].astype(str), df["total_pnl_rs"], color=colors_pnl, edgecolor="white")
axes[1].axhline(0, color="gray", lw=1)
axes[1].set_title("Total NET P&L — 5 Years (Rs)", fontsize=10)
axes[1].set_xlabel("Lots")
axes[1].set_ylabel("Rs")
axes[1].grid(True, alpha=0.3, axis="y")
for i, (lot, val) in enumerate(zip(df["lots"], df["total_pnl_rs"])):
    axes[1].text(i, val + (200 if val >= 0 else -1500),
                 f"Rs{val:+,.0f}", ha="center", fontsize=7.5, fontweight="bold")

# --- Annualized Return vs Capital ---
ax_r = axes[2]
ax_dd = ax_r.twinx()
colors_ret = ["#4CAF50" if v > 0 else "#F44336" for v in df["ann_return_pct"]]
bars = ax_r.bar(df["lots"].astype(str), df["ann_return_pct"],
                color=colors_ret, edgecolor="white", alpha=0.8, label="Ann. Return %")
ax_dd.plot(df["lots"].astype(str), df["max_dd_rs"].abs(),
           color="#F44336", marker="o", lw=2, label="Max DD (Rs)")
ax_r.axhline(0, color="gray", lw=1)
ax_r.set_title("Ann. Return % vs Max Drawdown (Rs)", fontsize=10)
ax_r.set_xlabel("Lots")
ax_r.set_ylabel("Annualized Return %")
ax_dd.set_ylabel("Max Drawdown Rs (lower = worse)")
ax_r.grid(True, alpha=0.3, axis="y")
lines1, lbl1 = ax_r.get_legend_handles_labels()
lines2, lbl2 = ax_dd.get_legend_handles_labels()
ax_r.legend(lines1 + lines2, lbl1 + lbl2, fontsize=8, loc="upper left")

plt.tight_layout()
chart_path = os.path.join(OUT_DIR, "lot_scaling_analysis.png")
plt.savefig(chart_path, dpi=150, bbox_inches="tight")
plt.close()
print(f"  Chart saved: {chart_path}")
print(f"  CSV saved  : {os.path.join(OUT_DIR, 'lot_scaling_summary.csv')}")
