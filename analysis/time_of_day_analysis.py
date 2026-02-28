import pandas as pd
import numpy as np

# -------- CONFIG --------
TRADES_FILE = "../output/scenario3_phase1_trades.csv"

# Time bucket size: 30 or 60 minutes
BUCKET_MINUTES = 30

# -------- LOAD DATA --------
trades = pd.read_csv(TRADES_FILE, parse_dates=["entry_time", "exit_time"])

# Safety check
assert not trades.empty, "Trades file is empty"

# Entry hour and minute
trades["entry_hour"] = trades["entry_time"].dt.hour
trades["entry_minute"] = trades["entry_time"].dt.minute

# Convert to minute-of-day
trades["minute_of_day"] = trades["entry_hour"] * 60 + trades["entry_minute"]

# Create time buckets
bucket_size = BUCKET_MINUTES
trades["time_bucket_start"] = (
    (trades["minute_of_day"] // bucket_size) * bucket_size
)

# Human-readable bucket label
trades["time_bucket"] = trades["time_bucket_start"].apply(
    lambda x: f"{x//60:02d}:{x%60:02d}"
)


def bucket_metrics(df):
    wins = df[df["pnl_points"] > 0]
    losses = df[df["pnl_points"] <= 0]

    return pd.Series({
        "trades": len(df),
        "win_rate": round((df["pnl_points"] > 0).mean(), 2),
        "avg_win": round(wins["pnl_points"].mean(), 2) if not wins.empty else 0,
        "avg_loss": round(losses["pnl_points"].mean(), 2) if not losses.empty else 0,
        "expectancy": round(df["pnl_points"].mean(), 2),
        "net_points": round(df["pnl_points"].sum(), 2)
    })
time_bucket_stats = (
    trades
    .groupby("time_bucket")
    .apply(bucket_metrics)
    .sort_index()
)

print(time_bucket_stats)
time_bucket_stats.to_csv(
    "../output/time_of_day_analysis.csv"
)

print("Saved time_of_day_analysis.csv")
