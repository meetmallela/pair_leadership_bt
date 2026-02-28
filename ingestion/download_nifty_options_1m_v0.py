# ingestion/download_nifty_options_1m.py
"""
Download 1-minute NIFTY options data from Zerodha Kite

Scope (Phase-2A):
- Only NIFTY weekly options
- Date range: derived from Phase-1.75 trades
- Strikes: ATM, ATM±1
- Stores CSVs locally for reuse (no repeated API hits)

Output structure:
 data/options/
   ├── NIFTY_<EXPIRY>_<STRIKE>_<CE/PE>_1m.csv

IMPORTANT:
- Respects Kite 60-day historical limit
- Resumable: skips files already downloaded
"""

import os
import json
import pandas as pd
from datetime import timedelta
from kiteconnect import KiteConnect

# ================= PATHS =================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, "data", "raw")
OPTIONS_DIR = os.path.join(BASE_DIR, "data", "options")
CONFIG_FILE = os.path.join(BASE_DIR, "kite_config.json")

os.makedirs(OPTIONS_DIR, exist_ok=True)

# ================= LOAD KITE =================

with open(CONFIG_FILE) as f:
    cfg = json.load(f)

kite = KiteConnect(api_key=cfg["api_key"])
kite.set_access_token(cfg["access_token"])

# ================= LOAD PHASE-1.75 TRADES =================

trades = pd.read_csv(
    os.path.join(BASE_DIR, "output", "scenario3_phase1_75_trades.csv"),
    parse_dates=["entry_time"]
)

# ================= NIFTY SPOT DATA =================

nifty = pd.read_csv(
    os.path.join(RAW_DIR, "nifty_1m.csv"),
    parse_dates=["timestamp"]
).set_index("timestamp")

# ================= HELPER FUNCTIONS =================

def atm_strike(price):
    return round(price / 50) * 50


def get_weekly_expiry(date):
    # Nearest Thursday >= date
    d = date
    while d.weekday() != 3:  # Thursday
        d += timedelta(days=1)
    return d


instruments = kite.instruments("NFO")
inst_df = pd.DataFrame(instruments)

# ================= DOWNLOAD LOOP =================

for _, trade in trades.iterrows():

    entry_ts = trade["entry_time"]
    spot_price = nifty.loc[entry_ts]["open"]
    atm = atm_strike(spot_price)
    expiry = get_weekly_expiry(entry_ts.date())

    for offset in [0, 50, -50]:
        strike = atm + offset

        for opt_type in ["CE", "PE"]:

            fname = f"NIFTY_{expiry}_{strike}_{opt_type}_1m.csv"
            fpath = os.path.join(OPTIONS_DIR, fname)

            if os.path.exists(fpath):
                continue

            inst = inst_df[
                (inst_df["name"] == "NIFTY") &
                (inst_df["expiry"] == expiry) &
                (inst_df["strike"] == strike) &
                (inst_df["instrument_type"] == opt_type)
            ]

            if inst.empty:
                continue

            token = int(inst.iloc[0]["instrument_token"])

            start = entry_ts.date() - timedelta(days=1)
            end = entry_ts.date() + timedelta(days=1)

            print(f"Downloading {fname}")

            data = kite.historical_data(
                token,
                start,
                end,
                interval="minute"
            )

            if not data:
                continue

            df = pd.DataFrame(data)
            df.to_csv(fpath, index=False)

print("Option data download complete")
