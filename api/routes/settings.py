"""
Per-user settings routes (Telegram bot, chat ID, camera source, alert rules).
Every customer has exactly one row in user_settings, auto-created on signup.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import NoResultFound

from api.middleware import get_current_user
from database.db import session_scope
from database.models import UserSettings

router = APIRouter(prefix="/me/settings", tags=["Settings"])


class SettingsIn(BaseModel):
    telegram_bot_token : str | None = None
    telegram_chat_id   : str | None = None
    camera_source      : str | None = None
    alert_on_unknown   : bool | None = None
    alert_on_known     : bool | None = None
    snapshot_dir       : str | None = None
    detection_cooldown : int | None = None


def _to_dict(row: UserSettings | None) -> dict:
    if not row:
        return {}
    return {
        "telegram_bot_token": row.telegram_bot_token,
        "telegram_chat_id":   row.telegram_chat_id,
        "camera_source":      row.camera_source,
        "alert_on_unknown":   row.alert_on_unknown,
        "alert_on_known":     row.alert_on_known,
        "snapshot_dir":       row.snapshot_dir,
        "detection_cooldown": row.detection_cooldown,
        "updated_at":         row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("")
def get_my_settings(current_user=Depends(get_current_user)):
    with session_scope() as s:
        row = s.query(UserSettings).filter_by(user_id=current_user["id"]).first()
        if not row:
            # Should never happen (auto-created on signup) but be defensive
            row = UserSettings(user_id=current_user["id"])
            s.add(row)
            s.flush()
            s.expunge(row)
        return _to_dict(row)


@router.put("")
def update_my_settings(payload: SettingsIn, current_user=Depends(get_current_user)):
    with session_scope() as s:
        row = s.query(UserSettings).filter_by(user_id=current_user["id"]).first()
        if not row:
            row = UserSettings(user_id=current_user["id"])
            s.add(row)

        # Only update fields the caller actually sent (avoid wiping with None)
        data = payload.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(row, k, v)

        s.flush()
        s.expunge(row)
        return _to_dict(row)


@router.post("/test-telegram")
def test_telegram(current_user=Depends(get_current_user)):
    """Send a test message to the customer's Telegram to confirm wiring."""
    import requests
    with session_scope() as s:
        row = s.query(UserSettings).filter_by(user_id=current_user["id"]).first()
        if not row or not row.telegram_bot_token or not row.telegram_chat_id:
            raise HTTPException(
                status_code=400,
                detail="Telegram bot token and chat ID not configured yet"
            )
        token  = row.telegram_bot_token
        chat   = row.telegram_chat_id
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": "Agent Eye test alert — your bot is connected!"},
            timeout=10,
        )
        if r.ok:
            return {"ok": True, "message": "Test message sent"}
        return {"ok": False, "error": r.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Telegram error: {e}")
