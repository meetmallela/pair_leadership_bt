# paper_trading/paper_trader.py
"""
Virtual trade lifecycle manager.

on_minute_close() is called by main.py every minute with fresh candle history.
It:
  1. Filters today's candles
  2. Checks the time bucket gate
  3. Evaluates entry (pair consensus) if no trade is open
  4. Evaluates exit (SL / bias lost / force exit) if a trade is open

All trade records are written to SQLite via db.py helpers.
Telegram alerts sent via notifier.py.
"""

import logging
from datetime import date, datetime, timedelta
from math import exp, log, sqrt

import pytz
from scipy.stats import norm

from config import (
    ALLOWED_TIME_BUCKETS, BUCKET_MINUTES, FORCE_EXIT, LOT_SIZE,
    MIN_IV, RISK_FREE_RATE, STOP_LOSS_POINTS, TRADE_END,
    NIFTY_TOKEN, RELIANCE_TOKEN, HDFCBANK_TOKEN,
)
from db import close_trade, get_all_closed_trades, get_today_trades, insert_open_trade
from signal_engine import get_bias

IST = pytz.timezone("Asia/Kolkata")

# Nifty switched from Thursday to Monday expiry on this date
EXPIRY_CHANGE_DATE = date(2024, 10, 21)


# ================= BS PROXY =================

def bs_price(S, K, T, r, sigma, option_type):
    """Black-Scholes price. Same formula as phase2/bs_proxy_backtest.py."""
    T     = max(T, 1 / 365)
    sigma = max(sigma, MIN_IV)
    d1    = (log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * sqrt(T))
    d2    = d1 - sigma * sqrt(T)
    if option_type == "CE":
        return S * norm.cdf(d1) - K * exp(-r * T) * norm.cdf(d2)
    return K * exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def get_next_expiry(trade_date):
    """Next Monday (post Oct-2024) or Thursday (pre Oct-2024) expiry."""
    target_weekday = 0 if trade_date >= EXPIRY_CHANGE_DATE else 3  # 0=Mon, 3=Thu
    d = trade_date + timedelta(days=1)
    while d.weekday() != target_weekday:
        d += timedelta(days=1)
    return d


def _option_bs(nifty_price, trade_date, vix_close, option_type):
    """Compute BS proxy option price for ATM strike."""
    atm_strike = round(nifty_price / 50) * 50
    expiry     = get_next_expiry(trade_date)
    T          = (expiry - trade_date).days / 365
    sigma      = vix_close / 100
    price      = bs_price(nifty_price, atm_strike, T, RISK_FREE_RATE, sigma, option_type)
    return atm_strike, price


# ================= TIME BUCKET =================

def _time_bucket(time_str):
    """Return the 30-min bucket label for a HH:MM string."""
    h, m       = int(time_str[:2]), int(time_str[3:])
    mins       = h * 60 + m
    bucket_min = (mins // BUCKET_MINUTES) * BUCKET_MINUTES
    return f"{bucket_min // 60:02d}:{bucket_min % 60:02d}"


# ================= PAPER TRADER =================

class PaperTrader:

    def __init__(self, conn, config, vix_close, vix_level, vix_direction, gate_ok):
        self.conn          = conn
        self.bot_token     = config.get("bot_token", "")
        self.chat_id       = config.get("chat_id", "")
        self.vix_close     = vix_close
        self.vix_level     = vix_level
        self.vix_direction = vix_direction
        self.gate_ok       = gate_ok

        self.trade        = None   # currently open virtual trade dict
        self.traded_today = False

    # ---------- Public interface ----------

    def on_minute_close(self, time_str, nifty_candles, rel_candles, hdfc_candles):
        """
        Called by main.py every minute with the full candle histories.
        Applies today-filter, time gate, then entry/exit logic.
        """
        if not self.gate_ok:
            return

        today_str = date.today().isoformat()

        nifty_today = [c for c in nifty_candles if str(c["ts"])[:10] == today_str]
        rel_today   = [c for c in rel_candles   if str(c["ts"])[:10] == today_str]
        hdfc_today  = [c for c in hdfc_candles  if str(c["ts"])[:10] == today_str]

        if not nifty_today or not rel_today or not hdfc_today:
            return

        bucket = _time_bucket(time_str)
        rel_bias  = get_bias(rel_today)
        hdfc_bias = get_bias(hdfc_today)

        # --- EXIT (checked every minute regardless of bucket) ---
        if self.trade is not None:
            nifty_close = nifty_today[-1]["close"]
            self._check_exit(time_str, nifty_close, rel_bias, hdfc_bias, today_str)

        # --- ENTRY (only in allowed time buckets) ---
        if (
            self.trade is None
            and not self.traded_today
            and bucket in ALLOWED_TIME_BUCKETS
            and time_str <= TRADE_END
        ):
            pair_bias = (
                rel_bias
                if rel_bias == hdfc_bias and rel_bias != "NEUTRAL"
                else None
            )
            if pair_bias:
                nifty_close = nifty_today[-1]["close"]
                self._open_trade(time_str, today_str, nifty_close, pair_bias, bucket)

    def send_daily_summary(self):
        """Send end-of-day Telegram summary."""
        today_str = date.today().isoformat()
        today_trades = get_today_trades(self.conn, today_str)
        all_closed   = get_all_closed_trades(self.conn)

        today_pts = sum(t["pnl_points"]      or 0 for t in today_trades if t["status"] == "CLOSED")
        today_rs  = sum(t["pnl_options_rs"]  or 0 for t in today_trades if t["status"] == "CLOSED")
        cum_pts   = sum(r[0] or 0 for r in all_closed)
        cum_rs    = sum(r[1] or 0 for r in all_closed)
        n_trades  = len([t for t in today_trades if t["status"] == "CLOSED"])

        msg = (
            f"Day Summary — {today_str}\n"
            f"Trades: {n_trades} | Pts: {today_pts:+.1f} | Rs: {today_rs:+,.0f}\n"
            f"Cumulative: {cum_pts:+.1f} pts | Rs {cum_rs:+,.0f}"
        )
        logging.info(f"[SUMMARY] {msg}")
        self._notify(msg)

    # ---------- Internal helpers ----------

    def _open_trade(self, time_str, today_str, nifty_price, direction, bucket):
        option_type = "CE" if direction == "BULLISH" else "PE"
        sl          = (
            nifty_price - STOP_LOSS_POINTS if direction == "BULLISH"
            else nifty_price + STOP_LOSS_POINTS
        )
        atm_strike, option_px = _option_bs(
            nifty_price, date.today(), self.vix_close, option_type
        )

        row = {
            "date":            today_str,
            "entry_time":      f"{today_str} {time_str}",
            "direction":       direction,
            "nifty_entry":     round(nifty_price, 2),
            "option_type":     option_type,
            "atm_strike":      atm_strike,
            "option_entry_px": round(option_px, 2),
            "stop_loss":       round(sl, 2),
            "time_bucket":     bucket,
            "vix_close":       self.vix_close,
            "vix_level":       self.vix_level,
            "vix_direction":   self.vix_direction,
        }
        trade_id = insert_open_trade(self.conn, row)

        self.trade = {**row, "trade_id": trade_id}
        self.traded_today = True

        msg = (
            f"PAPER TRADE: {direction}\n"
            f"Nifty: {nifty_price:,.1f} | {option_type} {atm_strike:,.0f}\n"
            f"SL: {sl:,.1f} | Option entry: Rs {option_px:,.0f} (BS proxy)\n"
            f"Time bucket: {bucket} | VIX: {self.vix_close:.1f}"
        )
        logging.info(f"[ENTRY] {msg}")
        self._notify(msg)

    def _check_exit(self, time_str, nifty_close, rel_bias, hdfc_bias, today_str):
        t   = self.trade
        sl  = t["stop_loss"]
        dir = t["direction"]

        sl_hit     = (nifty_close <= sl) if dir == "BULLISH" else (nifty_close >= sl)
        bias_lost  = not (rel_bias == hdfc_bias == dir)
        force_exit = time_str >= FORCE_EXIT

        if not (sl_hit or bias_lost or force_exit):
            return

        exit_reason = "SL_HIT" if sl_hit else ("FORCE_EXIT" if force_exit else "BIAS_LOST")
        self._close_trade(time_str, today_str, nifty_close, exit_reason)

    def _close_trade(self, time_str, today_str, nifty_exit, exit_reason):
        t = self.trade
        direction = t["direction"]

        pnl_points = (
            nifty_exit - t["nifty_entry"]
            if direction == "BULLISH"
            else t["nifty_entry"] - nifty_exit
        )

        option_type = t["option_type"]
        expiry      = get_next_expiry(date.today())
        T_exit      = (expiry - date.today()).days / 365
        option_exit_px = bs_price(
            nifty_exit, t["atm_strike"], T_exit,
            RISK_FREE_RATE, self.vix_close / 100, option_type
        )
        pnl_options_rs = (option_exit_px - t["option_entry_px"]) * LOT_SIZE - 60  # Rs 60 cost

        exit_fields = {
            "exit_time":      f"{today_str} {time_str}",
            "nifty_exit":     round(nifty_exit, 2),
            "option_exit_px": round(option_exit_px, 2),
            "exit_reason":    exit_reason,
            "pnl_points":     round(pnl_points, 2),
            "pnl_options_rs": round(pnl_options_rs, 2),
        }
        close_trade(self.conn, t["trade_id"], exit_fields)

        pnl_sign  = "+" if pnl_points >= 0 else ""
        rs_sign   = "+" if pnl_options_rs >= 0 else ""
        msg = (
            f"EXIT [{exit_reason}]\n"
            f"Nifty: {nifty_exit:,.1f} ({pnl_sign}{pnl_points:.1f} pts)\n"
            f"Option P&L: Rs {rs_sign}{pnl_options_rs:,.0f} (net after cost)\n"
            f"Time: {time_str}"
        )
        logging.info(f"[EXIT] {msg}")
        self._notify(msg)

        self.trade = None

    def _notify(self, msg):
        import notifier
        notifier.send(self.bot_token, self.chat_id, msg)
