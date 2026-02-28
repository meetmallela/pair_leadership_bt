import pandas as pd

# ================= FILE PATHS =================

TRADES_FILE = "../output/scenario3_phase1_5_trades.csv"
VIX_FILE = "../data/raw/indiavix_daily.csv"
OUTPUT_DIR = "../output"

# ================= LOAD TRADES =================

trades = pd.read_csv(
    TRADES_FILE,
    parse_dates=["entry_time", "exit_time"]
)

assert not trades.empty, "Trades file is empty"

trades["date"] = trades["entry_time"].dt.date

# ================= LOAD VIX =================

vix = pd.read_csv(
    VIX_FILE,
    parse_dates=["date"]
)

assert not vix.empty, "VIX file is empty"

vix["date"] = vix["date"].dt.date

# ================= VIX FEATURES =================

def vix_level_bucket(v):
    if v < 12:
        return "LOW"
    elif v < 20:
        return "MEDIUM"
    else:
        return "HIGH"

vix = vix.sort_values("date")
vix["vix_level"] = vix["close"].apply(vix_level_bucket)
vix["vix_change"] = vix["close"].diff()
vix["vix_direction"] = vix["vix_change"].apply(
    lambda x: "RISING" if x > 0 else "FALLING"
)

# ================= MERGE =================

trades = trades.merge(
    vix[["date", "close", "vix_level", "vix_direction"]],
    on="date",
    how="left"
)

trades.rename(columns={"close": "vix_close"}, inplace=True)

# Safety check
coverage = trades["vix_close"].notna().mean()
print(f"VIX merge coverage: {coverage:.2%}")
assert coverage > 0.95, "VIX merge issue — dates not aligning"

# ================= METRICS =================

def metrics(df):
    wins = df[df["pnl_points"] > 0]
    losses = df[df["pnl_points"] <= 0]

    equity = df["pnl_points"].cumsum()
    max_dd = (equity - equity.cummax()).min()

    return pd.Series({
        "trades": len(df),
        "win_rate": round((df["pnl_points"] > 0).mean(), 2),
        "avg_win": round(wins["pnl_points"].mean(), 2) if not wins.empty else 0,
        "avg_loss": round(losses["pnl_points"].mean(), 2) if not losses.empty else 0,
        "expectancy": round(df["pnl_points"].mean(), 2),
        "net_points": round(df["pnl_points"].sum(), 2),
        "max_drawdown": round(max_dd, 2)
    })

# ================= ANALYSIS =================

# --- By VIX LEVEL ---
vix_level_stats = (
    trades
    .groupby("vix_level")
    .apply(metrics)
)

print("\n=== PERFORMANCE BY VIX LEVEL ===")
print(vix_level_stats)

# --- By VIX DIRECTION ---
vix_dir_stats = (
    trades
    .groupby("vix_direction")
    .apply(metrics)
)

print("\n=== PERFORMANCE BY VIX DIRECTION ===")
print(vix_dir_stats)

# --- By VIX LEVEL + DIRECTION ---
vix_combo_stats = (
    trades
    .groupby(["vix_level", "vix_direction"])
    .apply(metrics)
)

print("\n=== PERFORMANCE BY VIX LEVEL + DIRECTION ===")
print(vix_combo_stats)

# ================= SAVE =================

vix_level_stats.to_csv(f"{OUTPUT_DIR}/vix_level_analysis.csv")
vix_dir_stats.to_csv(f"{OUTPUT_DIR}/vix_direction_analysis.csv")
vix_combo_stats.to_csv(f"{OUTPUT_DIR}/vix_combined_analysis.csv")

print("\nSaved VIX overlay analysis CSVs successfully")
