import pandas as pd

TRADES_FILE = "../output/scenario3_phase1_5_trades.csv"
# Load trades
trades = pd.read_csv(
    TRADES_FILE,
    parse_dates=["entry_time", "exit_time"]
)

assert not trades.empty, "Trades file is empty"
trades["year"] = trades["entry_time"].dt.year
def year_metrics(df):
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

yearly_stats = (
    trades
    .groupby("year")
    .apply(year_metrics)
    .sort_index()
)

print(yearly_stats)

yearly_stats.to_csv("../output/year_wise_analysis.csv")
print("Saved year_wise_analysis.csv")
