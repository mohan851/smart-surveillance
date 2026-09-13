"""
Routes the local Agent script calls. Authenticated with a per-agent token
(separate from the user JWT) so the customer can have many PCs running agents
under one account.

- POST /agent/register        user logs in once, gets an agent token for this PC
- POST /agent/heartbeat       agent says "I'm alive" every 30s
- POST /agent/event           agent pushes a detection event (label, ts, optional snapshot path)
- GET  /agent/download        customer downloads the agent script with their token pre-baked
"""
import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy import desc

from database.db import session_scope
from database.models import Agent, Detection, Alert, UserSettings
from api.middleware import get_current_user

router = APIRouter(prefix="/agent", tags=["Agent"])


# ── Agent-auth dependency ────────────────────────────────
def get_agent(x_agent_token: str = Header(...)) -> dict:
    """Resolve an agent from the X-Agent-Token header. 404 if unknown."""
    with session_scope() as s:
        a = s.query(Agent).filter_by(agent_token=x_agent_token).first()
        if not a:
            raise HTTPException(status_code=401, detail="Unknown agent token")
        s.expunge(a)
        return {
            "id":          a.id,
            "user_id":     a.user_id,
            "machine_id":  a.machine_id,
            "machine_name":a.machine_name,
        }


# ── Schemas ──────────────────────────────────────────────
class RegisterAgent(BaseModel):
    machine_id   : str
    machine_name : str | None = None
    camera_name  : str | None = None                # human label: "Front Door"
    camera_type  : str = "webcam"                   # webcam | rtsp | http | file
    camera_source: str | None = None                # 0, rtsp://..., http://..., /path.mp4
    camera_user  : str | None = None                # optional auth for IP cameras
    camera_pass  : str | None = None


class Heartbeat(BaseModel):
    camera_source: str | None = None


class EventIn(BaseModel):
    label         : str
    confidence    : int = 0
    snapshot_path : str | None = None
    snapshot_b64  : str | None = None            # base64-encoded JPEG (if cloud upload on)
    camera_source : str | None = None
    timestamp     : str | None = None            # ISO-8601, else now()


# ── Register: customer runs this from dashboard, gets token back
@router.post("/register")
def register_agent(payload: RegisterAgent, current_user=Depends(get_current_user)):
    # Validate camera_type
    valid_types = {"webcam", "rtsp", "http", "file"}
    if payload.camera_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"camera_type must be one of {sorted(valid_types)}",
        )

    # Build a human-readable camera label for display
    cam_label = payload.camera_name or (
        f"Webcam #{payload.camera_source}" if payload.camera_type == "webcam"
        else payload.camera_source
    )

    with session_scope() as s:
        existing = s.query(Agent).filter_by(
            user_id=current_user["id"], machine_id=payload.machine_id
        ).first()
        if existing:
            existing.last_seen_at  = datetime.utcnow()
            existing.status        = "online"
            existing.camera_source = payload.camera_source
            existing.machine_name  = payload.machine_name or existing.machine_name
            s.flush()
            s.expunge(existing)
            return {
                "agent_token": existing.agent_token,
                "agent_id":    existing.id,
                "message":     "Existing agent re-registered",
            }
        token = secrets.token_urlsafe(32)
        a = Agent(
            user_id       = current_user["id"],
            agent_token   = token,
            machine_id    = payload.machine_id,
            machine_name  = payload.machine_name or cam_label,
            camera_source = payload.camera_source,
            status        = "online",
            last_seen_at  = datetime.utcnow(),
            created_at    = datetime.utcnow(),
        )
        s.add(a)
        s.flush()
        s.expunge(a)
        return {
            "agent_token": a.agent_token,
            "agent_id":    a.id,
            "message":     "Agent registered. Save the token — it won't be shown again.",
            "camera_type": payload.camera_type,
            "camera_name": cam_label,
        }


# ── Heartbeat (called every ~30s by the agent) ───────────
@router.post("/heartbeat")
def heartbeat(payload: Heartbeat, agent=Depends(get_agent)):
    with session_scope() as s:
        a = s.query(Agent).filter_by(id=agent["id"]).first()
        a.last_seen_at  = datetime.utcnow()
        a.status        = "online"
        if payload.camera_source:
            a.camera_source = payload.camera_source
        return {"ok": True}


# ── Push detection event from agent to cloud ─────────────
@router.post("/event")
def push_event(payload: EventIn, agent=Depends(get_agent)):
    """The local agent calls this whenever it spots a face. The cloud only
    stores metadata — photos stay on the customer PC (privacy by design).
    If the user opted in to cloud uploads, snapshot_b64 is also stored."""
    import base64

    with session_scope() as s:
        settings = s.query(UserSettings).filter_by(user_id=agent["user_id"]).first()

        ts = datetime.utcnow()
        if payload.timestamp:
            try:
                ts = datetime.fromisoformat(payload.timestamp.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                pass

        # Only accept snapshot bytes if the user has opted in
        snap_bytes = None
        if payload.snapshot_b64 and settings and settings.upload_snapshots:
            try:
                snap_bytes = base64.b64decode(payload.snapshot_b64)
                # Safety cap: 5 MB per image — refuse anything bigger
                if len(snap_bytes) > 5 * 1024 * 1024:
                    snap_bytes = None
            except Exception:
                snap_bytes = None

        d = Detection(
            user_id       = agent["user_id"],
            agent_id      = agent["id"],
            label         = payload.label,
            confidence    = payload.confidence,
            snapshot_path = payload.snapshot_path,
            snapshot_data = snap_bytes,
            camera_source = payload.camera_source,
            timestamp     = ts,
        )
        s.add(d)
        s.flush()

        # Decide alert channel
        channel = "telegram" if settings and settings.telegram_bot_token else "none"
        if settings:
            if payload.label.lower() == "unknown" and not settings.alert_on_unknown:
                channel = "none"
            if payload.label.lower() != "unknown" and not settings.alert_on_known:
                channel = "none"

        s.add(Alert(
            user_id      = agent["user_id"],
            detection_id = d.id,
            channel      = channel,
            status       = "queued",
            timestamp    = ts,
        ))

        a = s.query(Agent).filter_by(id=agent["id"]).first()
        a.events_sent  = (a.events_sent or 0) + 1
        a.last_seen_at = datetime.utcnow()

        return {
            "ok":            True,
            "detection_id":  d.id,
            "alert_channel": channel,
            "snapshot_saved": snap_bytes is not None,
        }


# ── Config endpoint (called by agent on startup) ──────────
@router.get("/config")
def agent_config(agent=Depends(get_agent)):
    """Agent calls this on startup to learn its current config
    (upload_snapshots, telegram_enabled, snapshot_dir, cooldown)."""
    with session_scope() as s:
        settings = s.query(UserSettings).filter_by(user_id=agent["user_id"]).first()
        if not settings:
            return {
                "upload_snapshots":  False,
                "telegram_enabled":   False,
                "snapshot_dir":       "snapshots",
                "detection_cooldown": 10,
            }
        return {
            "upload_snapshots":   bool(settings.upload_snapshots),
            "telegram_enabled":   bool(settings.telegram_bot_token and settings.telegram_chat_id),
            "snapshot_dir":       settings.snapshot_dir or "snapshots",
            "detection_cooldown": settings.detection_cooldown or 10,
        }


# ── List my detections (dashboard reads this) ────────────
def _list_user_detections(user_id: int, limit: int = 50):
    with session_scope() as s:
        rows = s.query(Detection).filter_by(user_id=user_id) \
                                  .order_by(desc(Detection.timestamp)) \
                                  .limit(limit).all()
        out = []
        for r in rows:
            out.append({
                "id":            r.id,
                "label":         r.label,
                "confidence":    r.confidence,
                "snapshot_path": r.snapshot_path,
                "camera_source": r.camera_source,
                "timestamp":     r.timestamp.isoformat() if r.timestamp else None,
            })
        return out
