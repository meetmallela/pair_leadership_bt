# paper_trading/live_feed.py
"""
KiteTicker WebSocket + 1-minute candle aggregation for 3 instruments.

Kite WebSocket runs in its own internal thread (threaded=True).
Candle history is a plain list per instrument (max 200 candles).
Thread safety: list.append() and list.pop() are GIL-protected in CPython.
main.py reads candles via get_candles() only once per minute — no race condition risk.
"""

import logging
from datetime import datetime

import pytz
from kiteconnect import KiteTicker

from config import NIFTY_TOKEN, RELIANCE_TOKEN, HDFCBANK_TOKEN, INDIAVIX_TOKEN

IST = pytz.timezone("Asia/Kolkata")
TOKENS     = [NIFTY_TOKEN, RELIANCE_TOKEN, HDFCBANK_TOKEN]
ALL_TOKENS = TOKENS + [INDIAVIX_TOKEN]


class LiveFeed:

    def __init__(self, api_key, access_token):
        self.candle_history = {t: [] for t in TOKENS}
        self.current        = {}      # token → in-progress candle dict
        self.latest_vix     = None   # last known live VIX price

        self.kws = KiteTicker(api_key, access_token)
        self.kws.on_connect      = self._on_connect
        self.kws.on_ticks        = self._on_ticks
        self.kws.on_error        = self._on_error
        self.kws.on_close        = self._on_close
        self.kws.on_reconnect    = self._on_reconnect
        self.kws.on_noreconnect  = self._on_noreconnect

    def start(self):
        """Start WebSocket in background thread. Non-blocking."""
        self.kws.connect(threaded=True)
        logging.info("[FEED] WebSocket connecting...")

    def stop(self):
        self.kws.close()

    def seed_warmup(self, token, candles):
        """Pre-load historical candles fetched at startup."""
        self.candle_history[token].extend(candles[-200:])
        logging.info(f"[FEED] Seeded {len(candles)} warmup candles for token {token}")

    def get_candles(self, token):
        """Return a copy of completed candle history for one instrument."""
        return list(self.candle_history[token])

    def get_latest_vix(self):
        """Return the most recent live VIX price, or None if not yet received."""
        return self.latest_vix

    # ---------- WebSocket callbacks ----------

    def _on_connect(self, ws, _):
        ws.subscribe(ALL_TOKENS)
        ws.set_mode(ws.MODE_QUOTE, TOKENS)
        ws.set_mode(ws.MODE_LTP, [INDIAVIX_TOKEN])   # price only for VIX
        logging.info(f"[FEED] Subscribed to equity {TOKENS} (QUOTE) + VIX {INDIAVIX_TOKEN} (LTP)")

    def _on_ticks(self, ws, ticks):
        now_min = datetime.now(IST).replace(second=0, microsecond=0)

        for tick in ticks:
            token  = tick.get("instrument_token")

            # VIX — just store latest price, no candle aggregation needed
            if token == INDIAVIX_TOKEN:
                self.latest_vix = tick.get("last_price")
                continue

            if token not in self.candle_history:
                continue

            price  = tick.get("last_price", 0)
            volume = tick.get("volume_traded", 0)

            c = self.current.get(token)

            if c is None or c["ts"] != now_min:
                # Previous 1-min candle has closed
                if c is not None:
                    hist = self.candle_history[token]
                    hist.append(c)
                    if len(hist) > 200:
                        hist.pop(0)

                # Open a new 1-min candle
                self.current[token] = {
                    "ts":         now_min,
                    "open":       price,
                    "high":       price,
                    "low":        price,
                    "close":      price,
                    "volume":     0,
                    "_start_vol": volume,   # cumulative volume at candle start
                }
            else:
                c["high"]   = max(c["high"], price)
                c["low"]    = min(c["low"],  price)
                c["close"]  = price
                # volume_traded is cumulative for the session; delta gives per-candle volume
                c["volume"] = max(0, volume - c["_start_vol"])

    def _on_error(self, ws, code, reason):
        logging.error(f"[FEED] WebSocket error {code}: {reason}")

    def _on_close(self, ws, code, reason):
        logging.warning(f"[FEED] WebSocket closed {code}: {reason}")

    def _on_reconnect(self, ws, attempts):
        logging.info(f"[FEED] Reconnecting (attempt {attempts})...")

    def _on_noreconnect(self, ws):
        logging.error("[FEED] WebSocket max reconnect attempts reached — feed stopped")
