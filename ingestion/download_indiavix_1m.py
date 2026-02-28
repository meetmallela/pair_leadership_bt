import pandas as pd
from datetime import datetime, timedelta
from kiteconnect import KiteConnect
import os
import time
import json
import sys

# ================= CONFIG =================

INTERVAL = "minute"

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
CONFIG_PATH = os.path.join(BASE_DIR, "kite_config.json")

os.makedirs(DATA_DIR, exist_ok=True)

# INDIA VIX token (stable across Kite)
INDIAVIX_TOKEN = 264969

START_DATE = datetime(2021, 1, 1)
END_DATE   = datetime(2026, 1, 31)

MAX_DAYS_PER_CALL = 60
API_SLEEP_SECONDS = 0.4

# ================= LOAD KITE CONFIG =================

def load_kite_config(path):
    if not os.path.exists(path):
        print(f"❌ kite_config.json not found at {path}")
        sys.exit(1)

    with open(path, "r") as f:
        cfg = json.load(f)

    if not cfg.get("api_key") or not cfg.get("access_token"):
        print("❌ api_key or access_token missing in kite_config.json")
        sys.exit(1)

    return cfg["api_key"], cfg["access_token"]

# ================= INGESTION =================

def download_indiavix(kite):
    file_path = os.path.join(DATA_DIR, "indiavix_1m.csv")

    # -------- Resume logic --------
    if os.path.exists(file_path):
        df_existing = pd.read_csv(file_path, parse_dates=["timestamp"])
        df_existing["timestamp"] = df_existing["timestamp"].dt.tz_localize(None)

        last_ts = df_existing["timestamp"].max().to_pydatetime()
        start = last_ts + timedelta(minutes=1)

        print(f"INDIA VIX: resuming from {start}")
    else:
        df_existing = None
        start = START_DATE
        print(f"INDIA VIX: starting fresh from {start}")

    if start >= END_DATE:
        print("INDIA VIX: already fully downloaded")
        return

    all_data = []

    # -------- Batched download --------
    while start < END_DATE:
        end = min(start + timedelta(days=MAX_DAYS_PER_CALL), END_DATE)

        print(f"INDIA VIX: downloading {start.date()} → {end.date()}")

        data = kite.historical_data(
            instrument_token=INDIAVIX_TOKEN,
            from_date=start,
            to_date=end,
            interval=INTERVAL
        )

        if data:
            all_data.extend(data)

        start = end + timedelta(minutes=1)
        time.sleep(API_SLEEP_SECONDS)

    if not all_data:
        print("INDIA VIX: no new data fetched")
        return

    # -------- Normalize & save --------
    df_new = pd.DataFrame(all_data)
    df_new["timestamp"] = pd.to_datetime(df_new["date"]).dt.tz_localize(None)

    df_new = df_new[["timestamp", "open", "high", "low", "close", "volume"]]

    if df_existing is not None:
        df = pd.concat([df_existing, df_new], ignore_index=True)
    else:
        df = df_new

    df = (
        df.drop_duplicates(subset="timestamp")
          .sort_values("timestamp")
          .reset_index(drop=True)
    )

    df.to_csv(file_path, index=False)
    print(f"INDIA VIX: saved {len(df)} rows to {file_path}")

# ================= MAIN =================

def main():
    api_key, access_token = load_kite_config(CONFIG_PATH)

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)

    print("✅ Kite connection initialized for INDIA VIX")
    download_indiavix(kite)
    print("✅ INDIA VIX 1-minute ingestion completed")

if __name__ == "__main__":
    main()
