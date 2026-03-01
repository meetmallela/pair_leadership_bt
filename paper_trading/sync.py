# paper_trading/sync.py
"""
End-of-day git sync.

At 15:35 IST, after the daily summary:
  1. Exports today's paper trades to results/YYYY-MM-DD.csv
  2. git add + commit + push to origin/master

This keeps a clean daily record in the GitHub repo so results are
visible without needing local DB access.
"""

import csv
import logging
import os
import subprocess
from datetime import date

_HERE        = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT   = os.path.join(_HERE, "..")
_RESULTS_DIR = os.path.join(_HERE, "results")


def _run(cmd, cwd=_REPO_ROOT):
    """Run a shell command, return (stdout, stderr, returncode)."""
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, shell=True
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def export_today_csv(conn, date_str):
    """
    Export all paper trades for date_str to results/YYYY-MM-DD.csv.
    Returns the file path, or None if no trades to export.
    """
    os.makedirs(_RESULTS_DIR, exist_ok=True)

    rows = conn.execute(
        "SELECT * FROM paper_trades WHERE date = ? ORDER BY trade_id",
        (date_str,)
    ).fetchall()

    if not rows:
        logging.info("[SYNC] No trades to export today.")
        return None

    cols = [d[0] for d in conn.execute(
        "SELECT * FROM paper_trades LIMIT 0"
    ).description]

    out_path = os.path.join(_RESULTS_DIR, f"{date_str}.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)

    logging.info(f"[SYNC] Exported {len(rows)} trade(s) to {out_path}")
    return out_path


def git_push(date_str, n_trades, pnl_pts, pnl_rs):
    """
    Stage results/YYYY-MM-DD.csv, commit, and push to origin/master.
    """
    csv_rel = f"paper_trading/results/{date_str}.csv"

    # Stage only the results file
    out, err, rc = _run(f'git add "{csv_rel}"')
    if rc != 0:
        logging.warning(f"[SYNC] git add failed: {err}")
        return

    # Check if there's actually something staged
    out, _, _ = _run("git diff --cached --name-only")
    if not out:
        logging.info("[SYNC] Nothing new to commit (no change in results).")
        return

    sign = "+" if pnl_pts >= 0 else ""
    msg  = (
        f"Paper trade result {date_str}: "
        f"{n_trades} trade(s) | {sign}{pnl_pts:.1f} pts | Rs {sign}{pnl_rs:,.0f}"
    )
    out, err, rc = _run(f'git commit -m "{msg}\n\nCo-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"')
    if rc != 0:
        logging.warning(f"[SYNC] git commit failed: {err}")
        return
    logging.info(f"[SYNC] Committed: {msg}")

    out, err, rc = _run("git push origin master")
    if rc != 0:
        logging.warning(f"[SYNC] git push failed: {err}")
    else:
        logging.info("[SYNC] Pushed to GitHub successfully.")


def eod_sync(conn):
    """
    Full end-of-day sync: export CSV → git commit → git push.
    Safe to call even on no-trade days.
    """
    date_str = date.today().isoformat()

    csv_path = export_today_csv(conn, date_str)
    if csv_path is None:
        logging.info(f"[SYNC] No trades on {date_str} — skipping git push.")
        return

    # Gather summary for commit message
    rows = conn.execute(
        "SELECT pnl_points, pnl_options_rs FROM paper_trades WHERE date=? AND status='CLOSED'",
        (date_str,)
    ).fetchall()
    n_trades = len(rows)
    pnl_pts  = sum(r[0] or 0 for r in rows)
    pnl_rs   = sum(r[1] or 0 for r in rows)

    git_push(date_str, n_trades, pnl_pts, pnl_rs)
