# paper_trading/db.py
"""
SQLite setup and CRUD helpers for the paper_trades table.
"""

import sqlite3
import logging

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS paper_trades (
    trade_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    date            TEXT,
    entry_time      TEXT,
    direction       TEXT,
    nifty_entry     REAL,
    option_type     TEXT,
    atm_strike      REAL,
    option_entry_px REAL,
    stop_loss       REAL,
    time_bucket     TEXT,
    vix_close       REAL,
    vix_level       TEXT,
    vix_direction   TEXT,
    exit_time       TEXT,
    nifty_exit      REAL,
    option_exit_px  REAL,
    exit_reason     TEXT,
    pnl_points      REAL,
    pnl_options_rs  REAL,
    status          TEXT DEFAULT 'OPEN'
)
"""


def init_db(path):
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute(CREATE_TABLE_SQL)
    conn.commit()
    logging.info(f"[DB] Initialized: {path}")
    return conn


def insert_open_trade(conn, row):
    """
    Insert a new OPEN paper trade.
    row: dict with keys matching all non-exit columns.
    Returns the new trade_id.
    """
    sql = """
    INSERT INTO paper_trades
        (date, entry_time, direction, nifty_entry, option_type, atm_strike,
         option_entry_px, stop_loss, time_bucket, vix_close, vix_level, vix_direction, status)
    VALUES
        (:date, :entry_time, :direction, :nifty_entry, :option_type, :atm_strike,
         :option_entry_px, :stop_loss, :time_bucket, :vix_close, :vix_level, :vix_direction, 'OPEN')
    """
    cur = conn.execute(sql, row)
    conn.commit()
    return cur.lastrowid


def close_trade(conn, trade_id, exit_fields):
    """
    Update an existing OPEN trade with exit information.
    exit_fields: dict with exit_time, nifty_exit, option_exit_px,
                 exit_reason, pnl_points, pnl_options_rs.
    """
    sql = """
    UPDATE paper_trades
    SET exit_time      = :exit_time,
        nifty_exit     = :nifty_exit,
        option_exit_px = :option_exit_px,
        exit_reason    = :exit_reason,
        pnl_points     = :pnl_points,
        pnl_options_rs = :pnl_options_rs,
        status         = 'CLOSED'
    WHERE trade_id = :trade_id
    """
    conn.execute(sql, {**exit_fields, "trade_id": trade_id})
    conn.commit()


def get_today_trades(conn, date_str):
    """Return all paper trades for a given date string (YYYY-MM-DD)."""
    cur = conn.execute(
        "SELECT * FROM paper_trades WHERE date = ? ORDER BY trade_id",
        (date_str,)
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_all_closed_trades(conn):
    """Return all CLOSED trades for cumulative P&L calculation."""
    cur = conn.execute(
        "SELECT pnl_points, pnl_options_rs FROM paper_trades WHERE status = 'CLOSED'"
    )
    return cur.fetchall()
