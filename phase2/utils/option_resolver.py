import pandas as pd
from datetime import timedelta

def resolve_nifty_option(
    instruments_df: pd.DataFrame,
    trade_date,
    expiry_date,
    strike: int,
    option_type: str,
    expiry_tolerance_days: int = 1,
    debug: bool = False
):
    """
    Robust resolver for historical NIFTY options using Kite instrument master.

    Parameters
    ----------
    instruments_df : DataFrame
        Kite instrument dump (NFO)
    trade_date : date
        Trade date
    expiry_date : date
        Intended expiry date
    strike : int
        Option strike
    option_type : str
        'CE' or 'PE'
    expiry_tolerance_days : int
        Allowed mismatch in expiry (default ±1 day)
    debug : bool
        Print diagnostics

    Returns
    -------
    dict | None
        Instrument row as dict if found, else None
    """

    df = instruments_df.copy()

    # --- Step 1: NIFTY options only ---
    df = df[
        (df["exchange"] == "NFO") &
        (df["name"] == "NIFTY") &
        (df["segment"] == "NFO-OPT")
    ]

    if df.empty:
        if debug:
            print("❌ No NIFTY option instruments found")
        return None

    # --- Step 2: Strike filter ---
    df = df[df["strike"] == float(strike)]
    if df.empty:
        if debug:
            print(f"❌ No strike match for {strike}")
        return None

    # --- Step 3: Option type ---
    df = df[df["instrument_type"] == option_type]
    if df.empty:
        if debug:
            print(f"❌ No {option_type} contracts at strike {strike}")
        return None

    # --- Step 4: Expiry tolerance window ---
    expiry_date = pd.to_datetime(expiry_date).date()

    df["expiry_diff"] = df["expiry"].apply(
        lambda x: abs((x.date() - expiry_date).days)
    )

    df = df[df["expiry_diff"] <= expiry_tolerance_days]
    if df.empty:
        if debug:
            print(
                f"❌ No expiry within ±{expiry_tolerance_days} days "
                f"for strike {strike} {option_type}"
            )
        return None

    # --- Step 5: Prefer nearest expiry AFTER trade date ---
    df = df.sort_values(
        by=["expiry_diff", "expiry"],
        ascending=[True, True]
    )

    selected = df.iloc[0]

    if debug:
        print(
            f"✅ Resolved: {selected['tradingsymbol']} | "
            f"EXP {selected['expiry'].date()} | "
            f"STRIKE {strike} {option_type}"
        )

    return selected.to_dict()


# phase2/utils/option_resolver.py

from datetime import timedelta

def resolve_nifty_option(
    instruments_df,
    trade_date,
    expiry_date,
    strike,
    option_type,
    expiry_tolerance_days=1,
    debug=False
):
    """
    Robust NIFTY option resolver:
    - Handles weekly expiry mismatches
    - Handles holiday-shifted expiries
    - Avoids silent failures
    """

    df = instruments_df.copy()

    df = df[
        (df["name"] == "NIFTY") &
        (df["instrument_type"] == option_type) &
        (df["strike"] == float(strike))
    ]

    if df.empty:
        if debug:
            print(f"    [DEBUG] No strike match {strike} {option_type}")
        return None

    # Allow expiry tolerance (±1 day)
    for delta in range(-expiry_tolerance_days, expiry_tolerance_days + 1):
        candidate = expiry_date + timedelta(days=delta)

        match = df[df["expiry_date"] == candidate]
        if not match.empty:
            if debug:
                ts = match.iloc[0]["tradingsymbol"]
                print(f"    ✅ Resolved: {ts} (expiry {candidate})")
            return match.iloc[0]

    if debug:
        print(f"    ❌ Expiry not resolved for {strike} {option_type}")

    return None
