def summary(trades):
    return {
        "total_trades": len(trades),
        "win_rate": (trades.pnl > 0).mean(),
        "avg_win": trades[trades.pnl > 0].pnl.mean(),
        "avg_loss": trades[trades.pnl <= 0].pnl.mean(),
        "expectancy": trades.pnl.mean(),
        "max_dd": trades.pnl.cumsum().min()
    }
