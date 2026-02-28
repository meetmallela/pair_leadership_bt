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

START_DATE = datetime(2021, 1, 1)
END_DATE   = datetime(2026, 1, 31)

SYMBOLS = {
    "nifty": 256265,        # NIFTY 50
    "reliance": 738561,
    "hdfcbank": 341249
}

MAX_DAYS_PER_CALL = 60
API_SLEEP_SECONDS = 0.4

os.makedirs(DATA_DIR, exist_ok=True)

# ================= KITE CONFIG =================

def load_kite_config(config_path):
    if not os.path.exists(config_path):
        print(f"❌ kite_config.json not found at: {config_path}")
        sys.exit(1)

    with open(config_path, "r") as f:
        cfg = json.load(f)

    api_key = cfg.get("api_key")
    access_token = cfg.get("access_token")

    if not api_key or not access_token:
        print("❌ api_key or access_token missing in kite_config.json")
        sys.exit(1)

    return api_key, access_token

# ================= INGESTION =================

def download_symbol(kite, symbol, token):
    file_path = os.path.join(DATA_DIR, f"{symbol}_1m.csv")

    # ---------- Resume logic ----------
    if os.path.exists(file_path):
        existing_df = pd.read_csv(file_path, parse_dates=["timestamp"])
        existing_df["timestamp"] = existing_df["timestamp"].dt.tz_localize(None)

        last_ts = existing_df["timestamp"].max().to_pydatetime()
        start = last_ts + timedelta(minutes=1)

        print(f"{symbol}: resuming from {start}")
    else:
        existing_df = None
        start = START_DATE
        print(f"{symbol}: starting fresh from {start}")

    if start >= END_DATE:
        print(f"{symbol}: already complete till {END_DATE.date()}")
        return

    all_data = []

    # ---------- Batched download ----------
    while start < END_DATE:
        end = min(start + timedelta(days=MAX_DAYS_PER_CALL), END_DATE)

        print(f"{symbol}: downloading {start.date()} → {end.date()}")

        data = kite.historical_data(
            instrument_token=token,
            from_date=start,
            to_date=end,
            interval=INTERVAL
        )

        if data:
            all_data.extend(data)

        start = end + timedelta(minutes=1)
        time.sleep(API_SLEEP_SECONDS)

    if not all_data:
        print(f"{symbol}: no new data fetched")
        return

    # ---------- Normalize & save ----------
    df_new = pd.DataFrame(all_data)
    df_new["timestamp"] = pd.to_datetime(df_new["date"]).dt.tz_localize(None)
    df_new = df_new[["timestamp", "open", "high", "low", "close", "volume"]]

    if existing_df is not None:
        df = pd.concat([existing_df, df_new], ignore_index=True)
    else:
        df = df_new

    df = (
        df.drop_duplicates(subset="timestamp")
          .sort_values("timestamp")
          .reset_index(drop=True)
    )

    df.to_csv(file_path, index=False)
    print(f"{symbol}: saved {len(df)} rows")

# ================= MAIN =================

def main():
    api_key, access_token = load_kite_config(CONFIG_PATH)

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)

    print("✅ Kite connection initialized")

    for symbol, token in SYMBOLS.items():
        print("=" * 60)
        download_symbol(kite, symbol, token)

    print("=" * 60)
    print("✅ 1-minute data ingestion completed successfully")

if __name__ == "__main__":
    main()
