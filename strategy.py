def get_bias(df, idx, lookback, vol_mult):
    row = df.iloc[idx]

    if idx < lookback:
        return "NEUTRAL"

    prev = df.iloc[idx-lookback:idx]

    bullish = (
        row["close"] > row["vwap"] and
        row["close"] > prev["high"].max() and
        row["volume"] > vol_mult * row["vol_avg"]
    )

    bearish = (
        row["close"] < row["vwap"] and
        row["close"] < prev["low"].min() and
        row["volume"] > vol_mult * row["vol_avg"]
    )

    if bullish:
        return "BULLISH"
    if bearish:
        return "BEARISH"
    return "NEUTRAL"
