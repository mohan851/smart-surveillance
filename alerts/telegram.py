"""
Telegram alert sender for Agent Eye.
Called by both /agent/event (Python script) and /me/browser-event (browser Live page).
Sends the snapshot photo + a caption with timestamp + label.
"""
import logging
import requests
from datetime import datetime

log = logging.getLogger("agent_eye.telegram")


def send_telegram_alert(
    bot_token: str,
    chat_id:   str,
    label:     str,
    camera:    str | None,
    timestamp: datetime | None,
    snapshot_bytes: bytes | None,
) -> tuple[bool, str]:
    """Send a snapshot to the user's Telegram chat.
    Returns (ok, message_or_error)."""

    if not bot_token or not chat_id:
        return False, "Telegram bot token or chat ID not configured"

    ts_str = (timestamp or datetime.utcnow()).strftime("%Y-%m-%d %H:%M:%S UTC")
    caption = (
        f"👁 *Agent Eye — {label} detected*\n"
        f"🕒 {ts_str}\n"
        f"📷 Camera: `{camera or 'unknown'}`"
    )

    try:
        if snapshot_bytes:
            # Photo with caption
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            files = {"photo": ("snapshot.jpg", snapshot_bytes, "image/jpeg")}
            data  = {"chat_id": chat_id, "caption": caption, "parse_mode": "Markdown"}
            r = requests.post(url, data=data, files=files, timeout=15)
        else:
            # Text-only alert (no snapshot uploaded)
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data  = {"chat_id": chat_id, "text": caption, "parse_mode": "Markdown"}
            r = requests.post(url, data=data, timeout=15)

        if r.ok:
            log.info("Telegram alert sent to chat %s", chat_id)
            return True, "sent"
        return False, f"Telegram API {r.status_code}: {r.text[:200]}"
    except Exception as e:
        log.error("Telegram send failed: %s", e)
        return False, str(e)
