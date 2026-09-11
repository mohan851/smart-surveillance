"""
Camera = a registered Agent. Customer can see all their agents/cameras,
check online status, and view last-seen heartbeat.
"""
from fastapi import APIRouter, Depends
from sqlalchemy import desc

from api.middleware import get_current_user
from database.db import session_scope
from database.models import Agent, Detection

router = APIRouter(prefix="/cameras", tags=["Cameras"])


@router.get("")
def list_cameras(current_user=Depends(get_current_user)):
    """List all agents (= cameras) for the current user."""
    uid = current_user["id"]
    with session_scope() as s:
        rows = s.query(Agent).filter_by(user_id=uid) \
                             .order_by(desc(Agent.created_at)).all()
        out = []
        for a in rows:
            last_event = s.query(Detection).filter_by(agent_id=a.id) \
                                           .order_by(desc(Detection.timestamp)) \
                                           .first()
            out.append({
                "id":            a.id,
                "machine_id":    a.machine_id,
                "machine_name":  a.machine_name,
                "camera_source": a.camera_source,
                "status":        a.status,
                "events_sent":   a.events_sent,
                "last_seen_at":  a.last_seen_at.isoformat() if a.last_seen_at else None,
                "last_event_at": last_event.timestamp.isoformat() if last_event and last_event.timestamp else None,
            })
        return out


@router.get("/{camera_id}")
def get_camera(camera_id: int, current_user=Depends(get_current_user)):
    uid = current_user["id"]
    with session_scope() as s:
        a = s.query(Agent).filter_by(id=camera_id, user_id=uid).first()
        if not a:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Camera not found")
        return {
            "id":            a.id,
            "machine_id":    a.machine_id,
            "machine_name":  a.machine_name,
            "camera_source": a.camera_source,
            "status":        a.status,
            "events_sent":   a.events_sent,
            "last_seen_at":  a.last_seen_at.isoformat() if a.last_seen_at else None,
        }
