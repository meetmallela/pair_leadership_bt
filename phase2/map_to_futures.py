# phase2/map_to_futures.py
"""
Phase-2A Futures Mapper

Purpose:
- Translate validated Phase-1.75 spot trades into NIFTY Futures trades
- NO signal changes
- NO optimization
- Acts as the control / baseline instrument

Input:
- output/scenario3_phase1_75_trades.csv

Output:
- phase2/output/futures_trades.csv
"""

import pandas as pd
import os

# ================= PATHS =================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(BASE_DIR, "output", "scenario3_phase1_75_trades.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "phase2", "output")

os.makedirs(OUTPUT_DIR, exist_ok=True)

OUTPUT_FILE = os.path.join(OUTPUT_DIR, "futures_trades.csv")

# ================= CONFIG =================

FUTURES_LOT_SIZE = 50   # NIFTY lot size (update if needed)

# ================= LOAD TRADES =================

trades = pd.read_csv(
    INPUT_FILE,
    parse_dates=["entry_time", "exit_time"]
)

assert not trades.empty, "No Phase-1.75 trades found"

# ================= MAP TO FUTURES =================

fut_trades = trades.copy()
fut_trades["instrument"] = "NIFTY_FUT"
fut_trades["lot_size"] = FUTURES_LOT_SIZE

# Futures PnL = spot points × lot size
fut_trades["pnl"] = fut_trades["pnl_points"] * FUTURES_LOT_SIZE

# % return (approx) — margin-normalized placeholder
# NOTE: kept simple for Phase-2A
fut_trades["pnl_pct"] = fut_trades["pnl"] / (
    fut_trades["entry_price"] * FUTURES_LOT_SIZE
)

# ================= SELECT OUTPUT COLUMNS =================

fut_trades = fut_trades[[
    "date",
    "entry_time",
    "exit_time",
    "instrument",
    "direction",
    "entry_price",
    "exit_price",
    "pnl",
    "pnl_pct",
    "time_bucket",
    "vix_level",
    "vix_direction"
]]

# ================= SAVE =================

fut_trades.to_csv(OUTPUT_FILE, index=False)

print(f"Futures mapping complete: {OUTPUT_FILE}")
print(fut_trades.head())
