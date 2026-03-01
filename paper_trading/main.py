# paper_trading/main.py
"""
Pair Leadership Paper Trading System — Phase-1.75 v2 (LOCKED)

Usage:
    cd pair_leadership_bt/paper_trading
    python main.py

Prerequisites:
    - Update ../kite_config.json with today's access_token before running
    - kiteconnect, pandas, scipy, pytz must be installed

The script runs until 15:35 IST, then sends a daily summary and exits.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta

import pytz
from kiteconnect import KiteConnect

# Ensure imports resolve from this directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    DB_PATH, HDFCBANK_TOKEN, KITE_CONFIG_PATH, LOG_PATH,
    NIFTY_TOKEN, RELIANCE_TOKEN, TRADE_START, WARMUP_CANDLES,
)
from db import init_db
from live_feed import LiveFeed
from notifier import send as telegram_send
from paper_trader import PaperTrader
from signal_engine import check_vix_gate
from sync import eod_sync

IST = pytz.timezone("Asia/Kolkata")

# ================= LOGGING =================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)


# ================= HELPERS =================

def load_config():
    if not os.path.exists(KITE_CONFIG_PATH):
        logging.error(f"kite_config.json not found at: {KITE_CONFIG_PATH}")
        sys.exit(1)
    with open(KITE_CONFIG_PATH, "r") as f:
        return json.load(f)


def fetch_warmup_candles(kite, token, n=WARMUP_CANDLES):
    """Fetch the last n 1-min candles via historical data API."""
    now   = datetime.now(IST)
    start = now - timedelta(hours=2)
    try:
        bars = kite.historical_data(
            instrument_token=token,
            from_date=start.replace(tzinfo=None),
            to_date=now.replace(tzinfo=None),
            interval="minute"
        )
        return [
            {
                "ts":     b["date"].replace(tzinfo=None) if hasattr(b["date"], "tzinfo") else b["date"],
                "open":   b["open"],
                "high":   b["high"],
                "low":    b["low"],
                "close":  b["close"],
                "volume": b["volume"],
            }
            for b in bars[-n:]
        ]
    except Exception as e:
        logging.warning(f"[WARMUP] Token {token}: {e}")
        return []


# ================= MAIN ASYNC LOOP =================

async def run(kite, config, gate_ok, vix_close, vix_level, vix_direction):
    conn   = init_db(DB_PATH)
    feed   = LiveFeed(config["api_key"], config["access_token"])
    trader = PaperTrader(conn, config, vix_close, vix_level, vix_direction, gate_ok)

    # Warmup candle seeding
    logging.info("[WARMUP] Fetching historical candles for vol_avg and VWAP seeding...")
    for token in [NIFTY_TOKEN, RELIANCE_TOKEN, HDFCBANK_TOKEN]:
        candles = fetch_warmup_candles(kite, token)
        feed.seed_warmup(token, candles)

    # Start WebSocket
    feed.start()
    logging.info("[MAIN] WebSocket started. Entering minute loop...")

    last_minute = None

    while True:
        now     = datetime.now(IST)
        cur_min = now.strftime("%H:%M")

        if cur_min != last_minute:
            last_minute = cur_min
            logging.debug(f"[TICK] {cur_min}")

            # Process signal every minute during trading hours
            if TRADE_START <= cur_min <= "15:30":
                nifty_h = feed.get_candles(NIFTY_TOKEN)
                rel_h   = feed.get_candles(RELIANCE_TOKEN)
                hdfc_h  = feed.get_candles(HDFCBANK_TOKEN)

                if nifty_h and rel_h and hdfc_h:
                    trader.on_minute_close(cur_min, nifty_h, rel_h, hdfc_h)
                else:
                    logging.debug("[MAIN] Waiting for candle data from all 3 instruments...")

            # End of day
            if cur_min == "15:35":
                trader.send_daily_summary()
                logging.info("[MAIN] Exporting results and pushing to GitHub...")
                eod_sync(conn)
                logging.info("[MAIN] Market closed. Shutting down.")
                feed.stop()
                break

        await asyncio.sleep(5)


# ================= ENTRY POINT =================

def main():
    config = load_config()

    api_key      = config.get("api_key")
    access_token = config.get("access_token")
    bot_token    = config.get("bot_token", "")
    chat_id      = config.get("chat_id", "")

    if not api_key or not access_token:
        logging.error("api_key or access_token missing in kite_config.json")
        sys.exit(1)

    kite = KiteConnect(api_key=api_key)
    kite.set_access_token(access_token)
    logging.info("[MAIN] Kite connection initialized")

    # VIX gate — checked once at startup
    gate_ok, vix_close, vix_level, vix_direction = check_vix_gate(kite)

    vix_str = f"{vix_close:.1f}" if vix_close else "N/A"
    startup_msg = (
        f"Pair Leadership Paper Trader Started\n"
        f"VIX: {vix_str} | {vix_level} | {vix_direction}\n"
        f"{'Trades ALLOWED today' if gate_ok else 'NO TRADES today (VIX gate fail)'}"
    )
    logging.info(f"[VIX] {startup_msg}")
    telegram_send(bot_token, chat_id, startup_msg)

    asyncio.run(run(kite, config, gate_ok, vix_close, vix_level, vix_direction))


if __name__ == "__main__":
    main()
