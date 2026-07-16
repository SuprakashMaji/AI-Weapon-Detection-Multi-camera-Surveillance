"""
alert_manager.py

Real-time alert dispatch for Sentinel.

Two channels are supported, either or both can be enabled:
  - Telegram bot message (with the suspect snapshot attached)
  - Email (SMTP) with the snapshot attached

Both are optional and controlled purely by config/environment variables —
if nothing is configured, send_alert() just logs to the console and does
nothing else, so the rest of the app keeps working with zero setup.

Design notes:
  - Every alert is dispatched on a background thread (fire-and-forget) so
    a slow/failed network call to Telegram or an SMTP server can NEVER
    stall the video processing loop.
  - A small in-memory cooldown dict prevents the same suspect/camera pair
    from spamming an alert on every single check-frame (e.g. Re-ID runs
    every 10 frames — without a cooldown that's an alert every ~0.3s).
"""

import os
import smtplib
import threading
import time
from email.message import EmailMessage

import requests

from backend.utils.config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    SMTP_HOST,
    SMTP_PORT,
    SMTP_USER,
    SMTP_PASSWORD,
    ALERT_EMAIL_TO,
    ALERT_COOLDOWN_SECONDS,
)

# key -> last-sent unix timestamp, kept in memory (per process)
_last_sent = {}
_lock = threading.Lock()


def telegram_configured():
    return bool(TELEGRAM_BOT_TOKEN) and bool(TELEGRAM_CHAT_ID)


def email_configured():
    return bool(SMTP_HOST) and bool(SMTP_USER) and bool(SMTP_PASSWORD) and bool(ALERT_EMAIL_TO)


def alerts_configured():
    return telegram_configured() or email_configured()


def _send_telegram(message, image_path=None):
    base = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    try:
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as img:
                resp = requests.post(
                    f"{base}/sendPhoto",
                    data={"chat_id": TELEGRAM_CHAT_ID, "caption": message},
                    files={"photo": img},
                    timeout=10,
                )
        else:
            resp = requests.post(
                f"{base}/sendMessage",
                data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
                timeout=10,
            )

        if resp.status_code != 200:
            print(f"[ALERT] Telegram send failed ({resp.status_code}): {resp.text}")

    except Exception as e:
        print(f"[ALERT] Telegram error: {e}")


def _send_email(subject, message, image_path=None):
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = ALERT_EMAIL_TO
        msg.set_content(message)

        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as img:
                msg.add_attachment(
                    img.read(),
                    maintype="image",
                    subtype="jpeg",
                    filename=os.path.basename(image_path),
                )

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)

    except Exception as e:
        print(f"[ALERT] Email error: {e}")


def _dispatch(subject, message, image_path):
    if telegram_configured():
        _send_telegram(message, image_path)

    if email_configured():
        _send_email(subject, message, image_path)

    if not alerts_configured():
        # Nothing configured — this keeps the feature visible in the
        # console/logs during setup instead of failing silently.
        print(f"[ALERT] (no channel configured) {subject}: {message}")


def send_alert(subject, message, image_path=None, dedupe_key=None):
    """
    Fire an alert on a background thread.

    dedupe_key: an optional string identifying "this kind of alert for
    this suspect/camera". If the same key fired within
    ALERT_COOLDOWN_SECONDS, this call is skipped. Pass None to always send.
    """

    if dedupe_key is not None:
        now = time.time()
        with _lock:
            last = _last_sent.get(dedupe_key, 0)
            if now - last < ALERT_COOLDOWN_SECONDS:
                return
            _last_sent[dedupe_key] = now

    threading.Thread(
        target=_dispatch,
        args=(subject, message, image_path),
        daemon=True,
    ).start()
