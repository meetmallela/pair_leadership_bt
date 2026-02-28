# ingestion/download_nifty_options_1m.py
"""
DOWNLOAD NIFTY OPTIONS (1-MIN) — PHASE-2A-B1 (ROBUST)

Purpose:
- Download required NIFTY weekly option data
- Strikes: ATM, ATM ± 1
- Based on Phase-1.75 trades
- Uses robust instrument resolver (expiry-tolerant)

Output:
 data/options/
   ├── NIFTY_<YYYY-MM-DD>_<STRIKE>_<CE/PE>_1m.csv
"""
#######################################################################
# ingestion/download_nifty_options_1m.py
"""
DOWNLOAD NIFTY OPTIONS (1-MIN) — PHASE-2A-B1 (ROBUST)
"""

import os
import json
import pandas as pd
from datetime import timedelta
from kiteconnect import KiteConnect
import sys

import sys
import os

# Adds the parent directory to the path so it can find 'phase2'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)


# Ensure this path is correct in your project structure
from phase2.utils.option_resolver import resolve_nifty_option

# ================= PATHS =================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
OPTIONS_DIR = os.path.join(BASE_DIR, "data", "options")
OUTPUT_TRADES = os.path.join(BASE_DIR, "output", "scenario3_phase1_75_trades.csv")
CONFIG_FILE = os.path.join(BASE_DIR, "kite_config.json")

os.makedirs(OPTIONS_DIR, exist_ok=True)

# ================= LOAD KITE =================

with open(CONFIG_FILE, "r") as f:
    cfg = json.load(f)

kite = KiteConnect(api_key=cfg["api_key"])
kite.set_access_token(cfg["access_token"])

# ================= LOAD TRADES =================

trades = pd.read_csv(
    OUTPUT_TRADES,
    parse_dates=["entry_time"]
)

if trades.empty:
    raise RuntimeError("Phase-1.75 trades file is empty")

print(f"Loaded {len(trades)} Phase-1.75 trades")

# ================= LOAD NIFTY SPOT =================

nifty = pd.read_csv(
    os.path.join(RAW_DIR, "nifty_1m.csv"),
    parse_dates=["timestamp"]
).set_index("timestamp")

# ================= LOAD INSTRUMENT MASTER =================

print("Loading Kite instrument master (NFO)...")
instruments = pd.DataFrame(kite.instruments("NFO"))

# ================= HELPERS =================

def atm_strike(price: float) -> int:
    return int(round(price / 50) * 50)


def nearest_weekly_expiry(trade_date):
    d = trade_date
    while d.weekday() != 3:  # Thursday
        d += timedelta(days=1)
    return d

# ================= DOWNLOAD LOOP =================

for i, trade in trades.iterrows():

    entry_ts = trade["entry_time"]
    trade_date = entry_ts.date()

    if entry_ts not in nifty.index:
        print(f"[SKIP] Spot data missing for {entry_ts}")
        continue

    spot_price = nifty.loc[entry_ts]["open"]
    atm = atm_strike(spot_price)
    expiry = nearest_weekly_expiry(trade_date)

    print(f"\nTrade {i+1}/{len(trades)} | {trade_date} | ATM {atm} | EXP {expiry}")

    for offset in [0, 50, -50]:
        strike = atm + offset

        for opt_type in ["CE", "PE"]:

            fname = f"NIFTY_{expiry}_{strike}_{opt_type}_1m.csv"
            fpath = os.path.join(OPTIONS_DIR, fname)

            if os.path.exists(fpath):
                print(f"  [EXISTS] {fname}")
                continue

        
            inst = resolve_nifty_option(
                
                instruments_df=instruments,
                trade_date=trade_date,
                expiry_date=expiry,
                strike=strike,
                option_type=opt_type,
                expiry_tolerance_days=1,
                debug=True
)

            if inst is None:
                print(f"  [SKIP] {strike} {opt_type} not resolved")
                continue

            token = int(inst["instrument_token"])
            symbol = inst["tradingsymbol"]

            # Historical data typically needs a wider range for safety
            start = trade_date - timedelta(days=1)
            end = trade_date + timedelta(days=1)

            print(f"  [DOWNLOAD] {symbol}")

            try:
                data = kite.historical_data(
                    token,
                    start,
                    end,
                    interval="minute"
                )
            except Exception as e:
                print(f"  [ERROR] Kite error: {e}")
                continue

            if not data:
                print(f"  [EMPTY] No data returned")
                continue

            df = pd.DataFrame(data)
            df.to_csv(fpath, index=False)
            print(f"  [SAVED] {fname} ({len(df)} rows)")

print("\n✅ Option data download complete")

#######################################################################