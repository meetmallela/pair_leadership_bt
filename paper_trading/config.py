# paper_trading/config.py
"""
Locked v2 strategy constants — identical to strategies/scenario3_phase1_75_v2_bt_csv.py.
Do NOT modify these without new out-of-sample data justification.
"""

import os

# ================= INSTRUMENT TOKENS =================
# Source: ingestion/download_1m_data.py (confirmed)

NIFTY_TOKEN    = 256265
RELIANCE_TOKEN = 738561
HDFCBANK_TOKEN = 341249
INDIAVIX_TOKEN = 264969

# ================= LOCKED v2 SIGNAL PARAMS =================

STRUCTURE_LOOKBACK   = 3
VOL_WINDOW           = 20
VOL_MULTIPLIER       = 1.2
STOP_LOSS_POINTS     = 20

# Time gates
TRADE_START          = "09:20"
TRADE_END            = "14:00"
FORCE_EXIT           = "14:45"
ALLOWED_TIME_BUCKETS = {"11:00", "12:00", "13:00"}
BUCKET_MINUTES       = 30

# VIX gate (v2: raised lower bound from 12 to 13)
MIN_VIX_VALUE        = 13.0
MAX_VIX_VALUE        = 20.0

# ================= BS PROXY (Phase-2 consistent) =================

LOT_SIZE             = 50        # historical NIFTY lot size (consistent with backtest)
RISK_FREE_RATE       = 0.065     # 6.5% India proxy
MIN_IV               = 0.05      # floor to prevent BS blowup near expiry

# ================= PATHS =================

_HERE            = os.path.dirname(os.path.abspath(__file__))
KITE_CONFIG_PATH = os.path.join(_HERE, "..", "kite_config.json")
DB_PATH          = os.path.join(_HERE, "paper_trades.db")
LOG_PATH         = os.path.join(_HERE, "paper_trading.log")

# Warmup: 1-min bars fetched at startup per instrument (for vol_avg and VWAP seeding)
WARMUP_CANDLES = 30
