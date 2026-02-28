import pandas as pd

def add_vwap(df):
    tp = (df["high"] + df["low"] + df["close"]) / 3
    df["cum_vol"] = df["volume"].cumsum()
    df["cum_tp_vol"] = (tp * df["volume"]).cumsum()
    df["vwap"] = df["cum_tp_vol"] / df["cum_vol"]
    return df

def add_volume_avg(df, window=20):
    df["vol_avg"] = df["volume"].rolling(window).mean()
    return df
