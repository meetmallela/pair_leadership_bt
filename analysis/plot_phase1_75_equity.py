import pandas as pd
import matplotlib.pyplot as plt

# ================= CONFIG =================

TRADES_FILE = "../output/scenario3_phase1_75_trades.csv"

# ================= LOAD TRADES =================

trades = pd.read_csv(
    TRADES_FILE,
    parse_dates=["entry_time", "exit_time"]
)

assert not trades.empty, "Trades file is empty"

# Sort chronologically
trades = trades.sort_values("exit_time").reset_index(drop=True)

# ================= EQUITY CURVE =================

trades["cum_pnl"] = trades["pnl_points"].cumsum()

# ================= PLOT =================

plt.figure()
plt.plot(trades["exit_time"], trades["cum_pnl"])
plt.xlabel("Date")
plt.ylabel("Cumulative PnL (Points)")
plt.title("Phase-1.75 Equity Curve (Time + VIX Gated)")
plt.grid(True)

plt.show()
