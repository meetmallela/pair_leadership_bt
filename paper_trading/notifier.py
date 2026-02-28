# paper_trading/notifier.py
"""
Telegram notification helper.
Fire-and-forget: never raises, logs failures as warnings.
"""

import logging
import requests


def send(bot_token, chat_id, message):
    """Send a Telegram message. Safe to call from any thread."""
    if not bot_token or not chat_id:
        logging.warning("[TELEGRAM] bot_token or chat_id not configured — skipping")
        return
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        resp = requests.post(
            url,
            data={"chat_id": chat_id, "text": message},
            timeout=5
        )
        if not resp.ok:
            logging.warning(f"[TELEGRAM] HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logging.warning(f"[TELEGRAM] Failed: {e}")
