from kiteconnect import KiteConnect
import pandas as pd

def fetch_ohlcv(kite, instrument_token, start, end):
    data = kite.historical_data(
        instrument_token,
        start,
        end,
        interval="minute"
    )
    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["date"])
    df.set_index("timestamp", inplace=True)
    return df[["open","high","low","close","volume"]]
