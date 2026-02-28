import pandas as pd
from strategy import get_bias
from config import *

def run_backtest(nifty, rel, hdfc):
    trades = []
    in_trade = False

    for i in range(30, len(nifty)):
        ts = nifty.index[i]
        time = ts.strftime("%H:%M")

        if time < TRADE_START_TIME or time > FORCE_EXIT_TIME:
            continue

        rel_bias = get_bias(rel, i, STRUCTURE_LOOKBACK, VOLUME_MULTIPLIER)
        hdfc_bias = get_bias(hdfc, i, STRUCTURE_LOOKBACK, VOLUME_MULTIPLIER)

        pair_bias = None
        if rel_bias == hdfc_bias and rel_bias != "NEUTRAL":
            pair_bias = rel_bias

        if not in_trade and pair_bias and time <= TRADE_END_TIME:
            entry = nifty.iloc[i+1]["open"]
            direction = pair_bias
            sl = entry - STOP_LOSS_POINTS if direction == "BULLISH" else entry + STOP_LOSS_POINTS

            trade = {
                "entry_time": nifty.index[i+1],
                "direction": direction,
                "entry_price": entry,
                "stop_loss": sl
            }
            in_trade = True
            continue

        if in_trade:
            price = nifty.iloc[i]["close"]

            sl_hit = (
                price <= trade["stop_loss"] if trade["direction"] == "BULLISH"
                else price >= trade["stop_loss"]
            )

            bias_lost = not (
                rel_bias == hdfc_bias == trade["direction"]
            )

            time_exit = time >= FORCE_EXIT_TIME

            if sl_hit or bias_lost or time_exit:
                trade["exit_time"] = ts
                trade["exit_price"] = price
                trade["pnl"] = (
                    price - trade["entry_price"]
                    if trade["direction"] == "BULLISH"
                    else trade["entry_price"] - price
                )
                trades.append(trade)
                in_trade = False

    return pd.DataFrame(trades)
