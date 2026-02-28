import pandas as pd
import os

# ================= PATHS =================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ================= CONFIG =================

STRUCTURE_LOOKBACK = 3
VOL_WINDOW = 20
VOL_MULTIPLIER = 1.2

STOP_LOSS_POINTS = 20

TRADE_START = "09:20"
TRADE_END = "14:00"
FORCE_EXIT = "14:45"

# -------- TIME GATE --------
ALLOWED_TIME_BUCKETS = {"11:00", "12:00", "13:00"}
BUCKET_MINUTES = 30

# -------- VIX GATE --------
ALLOWED_VIX_LEVEL = "MEDIUM"
ALLOWED_VIX_DIRECTION = "RISING"
MIN_VIX_VALUE = 13.0    # v2: tightened lower bound (was 12)

# ================= DATA LOAD =================

def load_symbol(symbol):
    df = pd.read_csv(
        os.path.join(DATA_DIR, f"{symbol}_1m.csv"),
        parse_dates=["timestamp"]
    )
    df.set_index("timestamp", inplace=True)
    return df

def load_vix_with_features():
    df = pd.read_csv(
        os.path.join(DATA_DIR, "indiavix_daily.csv"),
        parse_dates=["date"]
    )

    df["date"] = df["date"].dt.date
    df = df.sort_values("date")

    # ---- VIX LEVEL ----
    def vix_level(v):
        if v < 12:
            return "LOW"
        elif v < 20:
            return "MEDIUM"
        else:
            return "HIGH"

    df["vix_close"] = df["close"]
    df["vix_level"] = df["close"].apply(vix_level)

    # ---- VIX DIRECTION ----
    df["vix_change"] = df["close"].diff()
    df["vix_direction"] = df["vix_change"].apply(
        lambda x: "RISING" if x > 0 else "FALLING"
    )

    return df[["date", "vix_close", "vix_level", "vix_direction"]]

# ================= INDICATORS =================

def add_indicators(df):
    df = df.copy()
    df["tp"] = (df["high"] + df["low"] + df["close"]) / 3
    df["vol_avg"] = df["volume"].rolling(VOL_WINDOW).mean()
    return df

def compute_daily_vwap(df):
    df = df.copy()
    df["vwap"] = (
        df.groupby(df.index.date)
          .apply(lambda x: (x["tp"] * x["volume"]).cumsum() / x["volume"].cumsum())
          .reset_index(level=0, drop=True)
    )
    return df

# ================= BIAS LOGIC =================

def get_bias(df, idx):
    if idx < STRUCTURE_LOOKBACK:
        return "NEUTRAL"

    row = df.iloc[idx]
    prev = df.iloc[idx-STRUCTURE_LOOKBACK:idx]

    if (
        row["close"] > row["vwap"]
        and row["close"] > prev["high"].max()
        and row["volume"] > VOL_MULTIPLIER * row["vol_avg"]
    ):
        return "BULLISH"

    if (
        row["close"] < row["vwap"]
        and row["close"] < prev["low"].min()
        and row["volume"] > VOL_MULTIPLIER * row["vol_avg"]
    ):
        return "BEARISH"

    return "NEUTRAL"

# ================= BACKTEST =================

def run_backtest(nifty, reliance, hdfc, vix):
    trades = []

    for day, day_df in nifty.groupby(nifty.index.date):

        # ---------- VIX DAY GATE ----------
        vix_row = vix[vix["date"] == day]
        if vix_row.empty:
            continue

        if (
            vix_row.iloc[0]["vix_level"] != ALLOWED_VIX_LEVEL
            or vix_row.iloc[0]["vix_direction"] != ALLOWED_VIX_DIRECTION
            or vix_row.iloc[0]["vix_close"] < MIN_VIX_VALUE
        ):
            continue
        # ---------------------------------

        traded_today = False
        in_trade = False
        trade = {}

        for ts in day_df.index:
            time_str = ts.strftime("%H:%M")
            if time_str < TRADE_START:
                continue

            # ---------- TIME BUCKET GATE ----------
            minute_of_day = ts.hour * 60 + ts.minute
            bucket_start = (minute_of_day // BUCKET_MINUTES) * BUCKET_MINUTES
            bucket_label = f"{bucket_start//60:02d}:{bucket_start%60:02d}"

            if bucket_label not in ALLOWED_TIME_BUCKETS:
                continue
            # --------------------------------------

            idx = nifty.index.get_loc(ts)

            rel_bias = get_bias(reliance, idx)
            hdfc_bias = get_bias(hdfc, idx)

            pair_bias = (
                rel_bias
                if rel_bias == hdfc_bias and rel_bias != "NEUTRAL"
                else None
            )

            # ---------- ENTRY ----------
            if (
                not in_trade
                and not traded_today
                and pair_bias
                and time_str <= TRADE_END
            ):
                entry_price = nifty.iloc[idx + 1]["open"]
                sl = (
                    entry_price - STOP_LOSS_POINTS
                    if pair_bias == "BULLISH"
                    else entry_price + STOP_LOSS_POINTS
                )

                trade = {
                    "date": day,
                    "entry_time": nifty.index[idx + 1],
                    "direction": pair_bias,
                    "entry_price": entry_price,
                    "stop_loss": sl,
                    "time_bucket": bucket_label,
                    "vix_level": vix_row.iloc[0]["vix_level"],
                    "vix_direction": vix_row.iloc[0]["vix_direction"]
                }

                in_trade = True
                traded_today = True
                continue

            # ---------- EXIT ----------
            if in_trade:
                price = nifty.loc[ts]["close"]

                sl_hit = (
                    price <= trade["stop_loss"]
                    if trade["direction"] == "BULLISH"
                    else price >= trade["stop_loss"]
                )

                bias_lost = not (
                    rel_bias == hdfc_bias == trade["direction"]
                )

                time_exit = time_str >= FORCE_EXIT

                if sl_hit or bias_lost or time_exit:
                    trade["exit_time"] = ts
                    trade["exit_price"] = price
                    trade["pnl_points"] = (
                        price - trade["entry_price"]
                        if trade["direction"] == "BULLISH"
                        else trade["entry_price"] - price
                    )
                    trades.append(trade)
                    in_trade = False

    return pd.DataFrame(trades)

# ================= METRICS =================

def generate_summary(trades):
    if trades.empty:
        return {}

    equity = trades.pnl_points.cumsum()

    return {
        "total_trades": len(trades),
        "win_rate": round((trades.pnl_points > 0).mean(), 2),
        "avg_win": round(trades[trades.pnl_points > 0].pnl_points.mean(), 2),
        "avg_loss": round(trades[trades.pnl_points <= 0].pnl_points.mean(), 2),
        "expectancy": round(trades.pnl_points.mean(), 2),
        "max_drawdown": round((equity - equity.cummax()).min(), 2)
    }

# ================= MAIN =================

def main():
    print("Running Phase-1.75 v2 backtest (Time + VIX >= 13 gated)...")

    nifty = load_symbol("nifty")
    reliance = load_symbol("reliance")
    hdfc = load_symbol("hdfcbank")
    vix = load_vix_with_features()

    # ----- Align timestamps -----
    common_index = nifty.index.intersection(reliance.index).intersection(hdfc.index)
    nifty = nifty.loc[common_index]
    reliance = reliance.loc[common_index]
    hdfc = hdfc.loc[common_index]

    nifty = compute_daily_vwap(add_indicators(nifty))
    reliance = compute_daily_vwap(add_indicators(reliance))
    hdfc = compute_daily_vwap(add_indicators(hdfc))

    trades = run_backtest(nifty, reliance, hdfc, vix)
    summary = generate_summary(trades)

    trades.to_csv(
        os.path.join(OUTPUT_DIR, "scenario3_phase1_75_v2_trades.csv"),
        index=False
    )

    pd.DataFrame([summary]).to_csv(
        os.path.join(OUTPUT_DIR, "scenario3_phase1_75_v2_summary.csv"),
        index=False
    )

    print("Phase-1.75 v2 backtest completed (VIX >= 13)")
    print(summary)

if __name__ == "__main__":
    main()
