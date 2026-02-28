import pandas as pd
import os

# ================= PATHS =================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_FILE = os.path.join(BASE_DIR, "data", "raw", "indiavix_1m.csv")
OUTPUT_FILE = os.path.join(BASE_DIR, "data", "raw", "indiavix_daily.csv")

# ================= LOAD =================

df = pd.read_csv(INPUT_FILE, parse_dates=["timestamp"])
df.set_index("timestamp", inplace=True)

assert not df.empty, "INDIA VIX 1-minute file is empty"

# ================= DAILY AGGREGATION =================
# Standard OHLC aggregation per trading day

daily = pd.DataFrame()
daily["open"] = df["open"].resample("1D").first()
daily["high"] = df["high"].resample("1D").max()
daily["low"] = df["low"].resample("1D").min()
daily["close"] = df["close"].resample("1D").last()

daily = daily.dropna().reset_index()
daily.rename(columns={"timestamp": "date"}, inplace=True)

# ================= SAVE =================

daily.to_csv(OUTPUT_FILE, index=False)

print(f"✅ Saved daily INDIA VIX to: {OUTPUT_FILE}")
print(f"Total days: {len(daily)}")
