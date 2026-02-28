# phase2/bs_proxy_backtest.py
"""
Phase-2B: Black-Scholes Option Proxy Backtest

Purpose:
- Maps Phase-1.75 spot signals to option P&L using Black-Scholes pricing
- No real option price data needed — uses Nifty spot + India VIX as IV proxy
- Prices ATM CE (BULLISH) or ATM PE (BEARISH) at entry and exit
- Computes option P&L per trade and full aggregate metrics

Assumptions:
- Strike  : ATM (nearest 50)
- IV      : India VIX daily close / 100  (already annualized %)
- r       : 6.5% p.a. (India risk-free rate proxy)
- Lot size: 50 (NIFTY historical lot; change LOT_SIZE if needed)
- Expiry  : next Thursday (pre Oct-2024)  |  next Monday (post Oct-2024)
- T       : calendar days to expiry / 365  (floor: 1 day)
"""

import os
import numpy as np
import pandas as pd
from scipy.stats import norm
from datetime import date, timedelta

# ================= PATHS =================

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRADES_FILE = os.path.join(BASE_DIR, "output", "scenario3_phase1_75_trades.csv")
VIX_FILE    = os.path.join(BASE_DIR, "data", "raw", "indiavix_daily.csv")
OUTPUT_DIR  = os.path.join(BASE_DIR, "phase2", "output")

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ================= CONFIG =================

RISK_FREE_RATE     = 0.065   # 6.5% p.a.
LOT_SIZE           = 50      # NIFTY lot size (historical)
MIN_T              = 1 / 365 # 1 calendar day floor for T
MIN_IV             = 0.05    # 5% IV floor (prevents BS blowup on near-zero VIX)
EXPIRY_CHANGE_DATE = date(2024, 10, 21)  # Nifty switched from Thursday → Monday expiry

# ================= BLACK-SCHOLES =================

def bs_price(S, K, T, r, sigma, option_type):
    """
    Standard Black-Scholes European option price.

    Parameters
    ----------
    S           : float  — spot price
    K           : float  — strike price
    T           : float  — time to expiry in years
    r           : float  — risk-free rate p.a.
    sigma       : float  — implied volatility p.a.
    option_type : str    — 'CE' or 'PE'

    Returns
    -------
    float — option price (>= 0)
    """
    if T <= 0:
        return max(S - K, 0) if option_type == "CE" else max(K - S, 0)

    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)

    if option_type == "CE":
        price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

    return max(float(price), 0.0)

# ================= EXPIRY HELPER =================

def get_next_expiry(trade_date):
    """
    Returns the nearest upcoming weekly expiry date from trade_date.
    Pre Oct-2024  → Thursday (weekday 3)
    Post Oct-2024 → Monday   (weekday 0)
    """
    target_weekday = 0 if trade_date >= EXPIRY_CHANGE_DATE else 3
    for i in range(1, 8):
        d = trade_date + timedelta(days=i)
        if d.weekday() == target_weekday:
            return d
    return trade_date + timedelta(days=7)  # fallback

# ================= MAIN =================

def run():
    # ----- Load trades -----
    trades = pd.read_csv(TRADES_FILE, parse_dates=["entry_time", "exit_time"])
    trades["date"] = pd.to_datetime(trades["date"]).dt.date
    print(f"Loaded {len(trades)} Phase-1.75 trades")

    # ----- Load VIX daily → dict for fast lookup -----
    vix_df = pd.read_csv(VIX_FILE, parse_dates=["date"])
    vix_df["date"] = vix_df["date"].dt.date
    vix_dict = dict(zip(vix_df["date"], vix_df["close"]))

    results = []

    for _, row in trades.iterrows():
        trade_date  = row["date"]
        entry_time  = row["entry_time"]
        exit_time   = row["exit_time"]
        entry_spot  = row["entry_price"]
        exit_spot   = row["exit_price"]
        direction   = row["direction"]
        pnl_points  = row["pnl_points"]

        option_type = "CE" if direction == "BULLISH" else "PE"

        # ATM strike
        strike = int(round(entry_spot / 50) * 50)

        # Expiry
        expiry = get_next_expiry(trade_date)

        # IV: VIX / 100, with floor
        vix_val = vix_dict.get(trade_date, 15.0)
        if vix_val <= 0:
            vix_val = 15.0
        sigma = max(vix_val / 100.0, MIN_IV)

        # Time to expiry for entry and exit
        entry_date = entry_time.date()
        exit_date  = exit_time.date()
        T_entry = max((expiry - entry_date).days / 365.0, MIN_T)
        T_exit  = max((expiry - exit_date).days  / 365.0, MIN_T)

        # BS prices at entry and exit
        entry_opt = bs_price(entry_spot, strike, T_entry, RISK_FREE_RATE, sigma, option_type)
        exit_opt  = bs_price(exit_spot,  strike, T_exit,  RISK_FREE_RATE, sigma, option_type)

        # P&L
        pnl_per_unit = exit_opt - entry_opt
        pnl_rupees   = pnl_per_unit * LOT_SIZE
        pnl_pct      = (pnl_per_unit / entry_opt * 100) if entry_opt > 0 else 0.0

        results.append({
            "date"              : trade_date,
            "entry_time"        : entry_time,
            "exit_time"         : exit_time,
            "direction"         : direction,
            "option_type"       : option_type,
            "entry_spot"        : entry_spot,
            "exit_spot"         : exit_spot,
            "strike"            : strike,
            "expiry"            : expiry,
            "days_to_expiry"    : (expiry - entry_date).days,
            "vix"               : round(vix_val, 2),
            "sigma_used"        : round(sigma, 4),
            "entry_option_px"   : round(entry_opt, 2),
            "exit_option_px"    : round(exit_opt, 2),
            "spot_pnl_points"   : pnl_points,
            "option_pnl_per_unit": round(pnl_per_unit, 2),
            "option_pnl_rupees" : round(pnl_rupees, 2),
            "option_pnl_pct"    : round(pnl_pct, 2),
        })

    df = pd.DataFrame(results)

    # ---- Overall summary ----
    wins   = df[df["option_pnl_rupees"] > 0]
    losses = df[df["option_pnl_rupees"] <= 0]
    equity = df["option_pnl_rupees"].cumsum()
    dd     = (equity - equity.cummax()).min()

    summary = {
        "total_trades"         : len(df),
        "win_rate_pct"         : round((df["option_pnl_rupees"] > 0).mean() * 100, 1),
        "avg_win_rs"           : round(wins["option_pnl_rupees"].mean(), 2)   if not wins.empty   else 0,
        "avg_loss_rs"          : round(losses["option_pnl_rupees"].mean(), 2) if not losses.empty else 0,
        "expectancy_per_trade" : round(df["option_pnl_rupees"].mean(), 2),
        "total_pnl_rupees"     : round(df["option_pnl_rupees"].sum(), 2),
        "max_drawdown_rupees"  : round(dd, 2),
        "lot_size"             : LOT_SIZE,
        "risk_free_rate"       : RISK_FREE_RATE,
    }

    # ---- Year-wise breakdown ----
    df["year"] = pd.to_datetime(df["date"]).dt.year
    year_summary = (
        df.groupby("year")
        .agg(
            trades       = ("option_pnl_rupees", "count"),
            win_rate_pct = ("option_pnl_rupees", lambda x: round((x > 0).mean() * 100, 1)),
            total_pnl    = ("option_pnl_rupees", lambda x: round(x.sum(), 2)),
            expectancy   = ("option_pnl_rupees", lambda x: round(x.mean(), 2)),
        )
        .reset_index()
    )

    # ---- Save ----
    out_trades  = os.path.join(OUTPUT_DIR, "bs_proxy_trades.csv")
    out_summary = os.path.join(OUTPUT_DIR, "bs_proxy_summary.csv")
    out_yearly  = os.path.join(OUTPUT_DIR, "bs_proxy_year_wise.csv")

    df.drop(columns=["year"]).to_csv(out_trades, index=False)
    pd.DataFrame([summary]).to_csv(out_summary, index=False)
    year_summary.to_csv(out_yearly, index=False)

    # ---- Print ----
    print("\n" + "=" * 55)
    print("  Phase-2B: Black-Scholes Option Proxy Backtest")
    print("=" * 55)
    print(f"  Lot size         : {LOT_SIZE}")
    print(f"  Risk-free rate   : {RISK_FREE_RATE*100:.1f}%")
    print(f"  IV proxy         : India VIX / 100")
    print(f"  Expiry logic     : Thursday (pre Oct-2024) / Monday (post Oct-2024)")
    print("-" * 55)
    for k, v in summary.items():
        if k in ("lot_size", "risk_free_rate"):
            continue
        print(f"  {k:<28}: {v}")
    print("-" * 55)
    print("\n  Year-wise breakdown:")
    print(year_summary.to_string(index=False))
    print("=" * 55)
    print(f"\n  Trades  : {out_trades}")
    print(f"  Summary : {out_summary}")
    print(f"  Yearly  : {out_yearly}")


if __name__ == "__main__":
    run()
