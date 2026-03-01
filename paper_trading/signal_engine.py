# paper_trading/signal_engine.py
"""
Signal logic — exact port of strategies/scenario3_phase1_75_v2_bt_csv.py.
Functions: check_vix_gate(), compute_running_vwap(), get_bias()

Do NOT change these without updating the research document.
"""

import logging
from datetime import date, timedelta

import pandas as pd

from config import (
    INDIAVIX_TOKEN, MIN_VIX_VALUE, MAX_VIX_VALUE,
    STRUCTURE_LOOKBACK, VOL_WINDOW, VOL_MULTIPLIER,
)


# ================= VIX GATE =================

def check_vix_gate(kite):
    """
    Fetches last 7 calendar days of daily VIX data.
    Uses yesterday's close for level and direction (realistic — known before market opens).

    Returns: (gate_ok: bool, vix_close: float, vix_level: str, vix_direction: str)
    """
    today = date.today()
    try:
        data = kite.historical_data(
            instrument_token=INDIAVIX_TOKEN,
            from_date=today - timedelta(days=7),
            to_date=today,
            interval="day"
        )
    except Exception as e:
        logging.error(f"[VIX] Failed to fetch VIX data: {e}")
        return False, None, "UNKNOWN", "UNKNOWN"

    data = sorted(data, key=lambda x: x["date"])
    trading_days = [d for d in data if d["date"].date() < today]

    if len(trading_days) < 2:
        logging.warning("[VIX] Insufficient historical VIX data")
        return False, None, "UNKNOWN", "UNKNOWN"

    yesterday    = trading_days[-1]["close"]
    day_before   = trading_days[-2]["close"]

    vix_direction = "RISING" if yesterday > day_before else "FALLING"

    if yesterday < MIN_VIX_VALUE:
        vix_level = "LOW"
    elif yesterday < MAX_VIX_VALUE:
        vix_level = "MEDIUM"
    else:
        vix_level = "HIGH"

    gate_ok = (vix_level == "MEDIUM" and vix_direction == "RISING")

    logging.info(
        f"[VIX] yesterday={yesterday:.2f}  day_before={day_before:.2f}  "
        f"level={vix_level}  direction={vix_direction}  gate={'OK' if gate_ok else 'FAIL'}"
    )
    return gate_ok, yesterday, vix_level, vix_direction


def check_intraday_vix_gate(live_vix, yesterday_close):
    """
    Intraday VIX gate — checked at the moment a signal fires.

    Two conditions must hold:
      1. Live VIX is still within the MEDIUM band [MIN_VIX_VALUE, MAX_VIX_VALUE)
         — catches intraday collapses (< 13) or panic spikes (> 20)
      2. Live VIX is above yesterday's close
         — confirms the RISING direction is still intact during the session

    Returns: (gate_ok: bool, reason: str)
    """
    if live_vix is None:
        return False, "Live VIX not yet received from WebSocket"

    if live_vix < MIN_VIX_VALUE:
        return False, f"Live VIX {live_vix:.2f} collapsed below floor {MIN_VIX_VALUE}"

    if live_vix >= MAX_VIX_VALUE:
        return False, f"Live VIX {live_vix:.2f} spiked above ceiling {MAX_VIX_VALUE}"

    if yesterday_close and live_vix <= yesterday_close:
        return False, f"Live VIX {live_vix:.2f} not rising vs yesterday {yesterday_close:.2f}"

    return True, f"Live VIX {live_vix:.2f} MEDIUM RISING vs yesterday {yesterday_close:.2f}"


# ================= INDICATORS =================

def compute_running_vwap(candles):
    """
    Computes VWAP from the first candle in the list (assumes caller passes today-only candles).
    Returns a list of floats, same length as candles.
    """
    cum_vol   = 0
    cum_tpvol = 0
    result    = []
    for c in candles:
        tp         = (c["high"] + c["low"] + c["close"]) / 3
        cum_vol   += c["volume"]
        cum_tpvol += tp * c["volume"]
        result.append(cum_tpvol / cum_vol if cum_vol > 0 else c["close"])
    return result


# ================= BIAS LOGIC =================

def get_bias(candles):
    """
    Returns BULLISH | BEARISH | NEUTRAL.

    Conditions (all must hold for BULLISH):
      - close > VWAP (intraday anchor)
      - close > max high of previous STRUCTURE_LOOKBACK candles (structure break)
      - volume > VOL_MULTIPLIER × rolling VOL_WINDOW-period mean volume

    Symmetric for BEARISH.

    Requires at least STRUCTURE_LOOKBACK + 1 candles with a valid vol_avg.
    """
    if len(candles) < STRUCTURE_LOOKBACK + 1:
        return "NEUTRAL"

    vwaps    = compute_running_vwap(candles)
    vols     = [c["volume"] for c in candles]
    vol_avgs = pd.Series(vols).rolling(VOL_WINDOW).mean().tolist()

    cur     = candles[-1]
    prev    = candles[-STRUCTURE_LOOKBACK - 1:-1]
    vwap    = vwaps[-1]
    vol_avg = vol_avgs[-1]

    if vol_avg is None or pd.isna(vol_avg) or vol_avg == 0:
        return "NEUTRAL"

    if (
        cur["close"] > vwap
        and cur["close"] > max(p["high"] for p in prev)
        and cur["volume"] > VOL_MULTIPLIER * vol_avg
    ):
        return "BULLISH"

    if (
        cur["close"] < vwap
        and cur["close"] < min(p["low"] for p in prev)
        and cur["volume"] > VOL_MULTIPLIER * vol_avg
    ):
        return "BEARISH"

    return "NEUTRAL"
