# analysis/day_level_report_phase1_75.py
"""
Day-level diagnostic report for Scenario-3 (Phase-1 logic, Phase-1.75 gates)

For EACH trading day, this script:
- Tags VIX regime (level + direction)
- Determines whether trading was ALLOWED that day (based on VIX + time windows)
- Simulates NIFTY SPOT trade using Phase-1 rules
- Produces daily P&L (points)

Output:
- output/day_level_report_phase1_75.csv

This is a DIAGNOSTIC / EXPLAINABILITY report, not a new backtest.
"""

import pandas as pd
import os

# ================= PATHS =================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ================= CONFIG =================

ALLOWED_TIME_BUCKETS = {"11:00", "12:00", "13:00"}
BUCKET_MINUTES = 30

ALLOWED_VIX_LEVEL = "MEDIUM"
ALLOWED_VIX_DIRECTION = "RISING"

STOP_LOSS_POINTS = 20

# ================= LOAD DATA =================

def load_symbol(symbol):
    df = pd.read_csv(
        os.path.join(DATA_DIR, f"{symbol}_1m.csv"),
        parse_dates=["timestamp"]
    )
    df.set_index("timestamp", inplace=True)
    return df

nifty = load_symbol("nifty")
reliance = load_symbol("reliance")
hdfc = load_symbol("hdfcbank")

# Align timestamps
common_index = nifty.index.intersection(reliance.index).intersection(hdfc.index)
nifty = nifty.loc[common_index]
reliance = reliance.loc[common_index]
hdfc = hdfc.loc[common_index]

# ================= VIX =================

vix = pd.read_csv(
    os.path.join(DATA_DIR, "indiavix_daily.csv"),
    parse_dates=["date"]
)
vix["date"] = vix["date"].dt.date
vix = vix.sort_values("date")

# VIX features

def vix_level(v):
    if v < 12:
        return "LOW"
    elif v < 20:
        return "MEDIUM"
    else:
        return "HIGH"

vix["vix_level"] = vix["close"].apply(vix_level)
vix["vix_change"] = vix["close"].diff()
vix["vix_direction"] = vix["vix_change"].apply(
    lambda x: "RISING" if x > 0 else "FALLING"
)

vix = vix[["date", "vix_level", "vix_direction"]]

# ================= INDICATORS =================

def add_indicators(df):
    df = df.copy()
    df["tp"] = (df["high"] + df["low"] + df["close"]) / 3
    df["vol_avg"] = df["volume"].rolling(20).mean()
    return df


def compute_daily_vwap(df):
    df = df.copy()
    df["vwap"] = (
        df.groupby(df.index.date)
          .apply(lambda x: (x["tp"] * x["volume"]).cumsum() / x["volume"].cumsum())
          .reset_index(level=0, drop=True)
    )
    return df

nifty = compute_daily_vwap(add_indicators(nifty))
reliance = compute_daily_vwap(add_indicators(reliance))
hdfc = compute_daily_vwap(add_indicators(hdfc))

# ================= BIAS =================

def get_bias(df, idx):
    if idx < 3:
        return "NEUTRAL"

    row = df.iloc[idx]
    prev = df.iloc[idx-3:idx]

    if (
        row["close"] > row["vwap"]
        and row["close"] > prev["high"].max()
        and row["volume"] > 1.2 * row["vol_avg"]
    ):
        return "BULLISH"

    if (
        row["close"] < row["vwap"]
        and row["close"] < prev["low"].min()
        and row["volume"] > 1.2 * row["vol_avg"]
    ):
        return "BEARISH"

    return "NEUTRAL"

# ================= DAY-LEVEL LOOP =================

day_rows = []

for day, day_df in nifty.groupby(nifty.index.date):

    row = {
        "date": day,
        "trade_allowed": False,
        "vix_level": None,
        "vix_direction": None,
        "time_window_used": None,
        "direction": None,
        "entry_price": None,
        "exit_price": None,
        "pnl_points": 0.0,
        "comment": ""
    }

    vix_row = vix[vix["date"] == day]
    if vix_row.empty:
        row["comment"] = "No VIX data"
        day_rows.append(row)
        continue

    row["vix_level"] = vix_row.iloc[0]["vix_level"]
    row["vix_direction"] = vix_row.iloc[0]["vix_direction"]

    # VIX gate
    if not (
        row["vix_level"] == ALLOWED_VIX_LEVEL
        and row["vix_direction"] == ALLOWED_VIX_DIRECTION
    ):
        row["comment"] = "VIX gate blocked"
        day_rows.append(row)
        continue

    traded = False

    for ts in day_df.index:
        minute_of_day = ts.hour * 60 + ts.minute
        bucket_start = (minute_of_day // BUCKET_MINUTES) * BUCKET_MINUTES
        bucket_label = f"{bucket_start//60:02d}:{bucket_start%60:02d}"

        if bucket_label not in ALLOWED_TIME_BUCKETS:
            continue

        idx = nifty.index.get_loc(ts)
        rel_bias = get_bias(reliance, idx)
        hdfc_bias = get_bias(hdfc, idx)

        if rel_bias == hdfc_bias and rel_bias != "NEUTRAL":
            entry = nifty.iloc[idx + 1]["open"]
            sl = entry - STOP_LOSS_POINTS if rel_bias == "BULLISH" else entry + STOP_LOSS_POINTS

            # simulate exit (simplified: exit on bias loss or EOD)
            for ts2 in day_df.index[idx + 1:]:
                price = nifty.loc[ts2]["close"]
                if (
                    (rel_bias == "BULLISH" and price <= sl)
                    or (rel_bias == "BEARISH" and price >= sl)
                ):
                    exit_price = price
                    break
            else:
                exit_price = day_df.iloc[-1]["close"]

            pnl = exit_price - entry if rel_bias == "BULLISH" else entry - exit_price

            row.update({
                "trade_allowed": True,
                "time_window_used": bucket_label,
                "direction": rel_bias,
                "entry_price": entry,
                "exit_price": exit_price,
                "pnl_points": round(pnl, 2),
                "comment": "Trade taken"
            })

            traded = True
            break

    if not traded:
        row["comment"] = "No valid leadership signal"

    day_rows.append(row)

# ================= SAVE =================

df_days = pd.DataFrame(day_rows)
output_file = os.path.join(OUTPUT_DIR, "day_level_report_phase1_75.csv")
df_days.to_csv(output_file, index=False)

print(f"Day-level report saved to: {output_file}")
print(df_days.head())
