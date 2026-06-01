import requests
from datetime import datetime
from database.models import insert_alert

# ── Telegram config ──────────────────────────────────────
TELEGRAM_BOT_TOKEN = "8710850927:AAHDY5DmqlI10_X4xBIO1-m4eTUnMmSqZag"
TELEGRAM_CHAT_ID   = "5662811833"

def send_intruder_alert(detection_id, camera_id, snapshot_path, label="Unknown"):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    message   = (
        f"🚨 *INTRUDER ALERT!*\n\n"
        f"📷 Camera: {camera_id}\n"
        f"👤 Person: {label}\n"
        f"🕐 Entered at: {timestamp}\n\n"
        f"⚠️ Check your dashboard immediately!"
    )

    try:
        # ── Send photo with caption ───────────────────────
        photo_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
        
        with open(snapshot_path, "rb") as photo:
            response = requests.post(
                photo_url,
                data    = {
                    "chat_id"    : TELEGRAM_CHAT_ID,
                    "caption"    : message,
                    "parse_mode" : "Markdown"
                },
                files   = {"photo": photo},
                timeout = 10
            )

        if response.status_code == 200:
            insert_alert(detection_id, channel="telegram", status="sent")
            print(f"✅ Telegram alert sent with photo!")
        else:
            # ── If photo fails send text only ─────────────
            text_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            requests.post(text_url, json={
                "chat_id"    : TELEGRAM_CHAT_ID,
                "text"       : message,
                "parse_mode" : "Markdown"
            }, timeout=5)
            insert_alert(detection_id, channel="telegram", status="sent")
            print(f"✅ Telegram text alert sent!")

    except Exception as e:
        insert_alert(detection_id, channel="telegram", status="failed")
        print(f"❌ Telegram failed: {e}")