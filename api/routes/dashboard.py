"""
Dashboard data routes — all scoped to the current user.
- GET /me/stats           summary counts
- GET /me/detections      paginated list of events
- GET /me/agents          list this user's agents
- GET /me/agent-script    returns the downloadable local agent script
                         with the customer's token pre-baked
"""
import io
import platform
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func

from api.middleware import get_current_user
from database.db import session_scope
from database.models import Detection, Alert, Agent, UserSettings
from api.routes.agent_api import _list_user_detections

router = APIRouter(prefix="/me", tags=["Dashboard"])


@router.get("/stats")
def my_stats(current_user=Depends(get_current_user)):
    """Summary numbers for the dashboard header cards."""
    uid = current_user["id"]
    with session_scope() as s:
        total    = s.query(func.count(Detection.id)).filter_by(user_id=uid).scalar() or 0
        today    = s.query(func.count(Detection.id)).filter(
                       Detection.user_id == uid,
                       Detection.timestamp >= datetime.utcnow() - timedelta(hours=24)
                   ).scalar() or 0
        unknown  = s.query(func.count(Detection.id)).filter_by(
                       user_id=uid, label="Unknown").scalar() or 0
        agents_n = s.query(func.count(Agent.id)).filter_by(user_id=uid).scalar() or 0
        alerts_n = s.query(func.count(Alert.id)).filter_by(user_id=uid, status="sent").scalar() or 0

        # detections per day for last 7 days
        week = []
        for d in range(6, -1, -1):
            day_start = datetime.utcnow() - timedelta(days=d)
            day_start = day_start.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end   = day_start + timedelta(days=1)
            c = s.query(func.count(Detection.id)).filter(
                Detection.user_id == uid,
                Detection.timestamp >= day_start,
                Detection.timestamp <  day_end
            ).scalar() or 0
            week.append({"date": day_start.strftime("%Y-%m-%d"), "count": c})

        return {
            "total_detections":  total,
            "today_detections":  today,
            "unknown_detections":unknown,
            "active_agents":     agents_n,
            "alerts_sent":       alerts_n,
            "last_7_days":       week,
        }


@router.get("/detections")
def my_detections(limit: int = 100, current_user=Depends(get_current_user)):
    return _list_user_detections(current_user["id"], limit=limit)


@router.get("/agents")
def my_agents(current_user=Depends(get_current_user)):
    with session_scope() as s:
        rows = s.query(Agent).filter_by(user_id=current_user["id"]) \
                             .order_by(desc(Agent.created_at)).all()
        out = []
        for a in rows:
            out.append({
                "id":           a.id,
                "machine_id":   a.machine_id,
                "machine_name": a.machine_name,
                "camera_source":a.camera_source,
                "status":       a.status,
                "events_sent":  a.events_sent,
                "last_seen_at": a.last_seen_at.isoformat() if a.last_seen_at else None,
                "created_at":   a.created_at.isoformat() if a.created_at else None,
            })
        return out


@router.get("/agent-script")
def download_agent_script(current_user=Depends(get_current_user)):
    """Return the local agent Python file with the user's token pre-filled."""
    # We need at least one agent token to inject. Pick the most recent one.
    with session_scope() as s:
        a = s.query(Agent).filter_by(user_id=current_user["id"]) \
                          .order_by(desc(Agent.created_at)).first()
        token = a.agent_token if a else ""
    script = AGENT_SCRIPT_TEMPLATE.format(
        cloud_url   = "https://smart-surveillance-production.up.railway.app",
        agent_token = token,
        username    = current_user["username"],
    )
    return StreamingResponse(
        io.BytesIO(script.encode("utf-8")),
        media_type="text/x-python",
        headers={"Content-Disposition": 'attachment; filename="agent_eye_local.py"'},
    )


# ── The agent script template (downloaded by customers) ─
AGENT_SCRIPT_TEMPLATE = r'''#!/usr/bin/env python3
"""
Agent Eye — local agent for customer: {username}
This file was auto-generated. Do not share it — it contains your agent token.

Quick start:
    pip install opencv-python requests
    python agent_eye_local.py
"""
import os, sys, time, json, uuid, platform, hashlib
from datetime import datetime
import requests, cv2

CLOUD_URL    = "{cloud_url}"
AGENT_TOKEN  = "{agent_token}"
MACHINE_ID   = hashlib.sha256(platform.node().encode()).hexdigest()[:16]
MACHINE_NAME = platform.node()
HEARTBEAT_S  = 30
COOLDOWN_S   = 10   # min seconds between alerts for the same label

_last_alert = {{}}  # label -> timestamp

def post(path, payload):
    try:
        return requests.post(CLOUD_URL + path, json=payload,
                             headers={{"X-Agent-Token": AGENT_TOKEN}}, timeout=10)
    except Exception as e:
        print("[cloud] post failed:", e)
        return None

def main():
    print(f"Agent Eye local agent starting (machine={{MACHINE_NAME}})")
    # Open default webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: cannot open webcam. Check camera permissions.")
        sys.exit(1)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    last_hb = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            time.sleep(1); continue
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            # Privacy: snapshot saved LOCALLY, only path+label sent to cloud
            snap = os.path.join("snapshots", f"{{datetime.utcnow():%Y%m%d_%H%M%S}}_{{uuid.uuid4().hex[:6]}}.jpg")
            os.makedirs("snapshots", exist_ok=True)
            cv2.imwrite(snap, frame)
            now = time.time()
            if now - _last_alert.get("face", 0) > COOLDOWN_S:
                _last_alert["face"] = now
                post("/agent/event", {{
                    "label":         "Unknown",
                    "confidence":    0,
                    "snapshot_path": snap,
                    "camera_source": "webcam:0",
                    "timestamp":     datetime.utcnow().isoformat(),
                }})
                print("[detection] face @", snap)
        if time.time() - last_hb > HEARTBEAT_S:
            post("/agent/heartbeat", {{"camera_source": "webcam:0"}})
            last_hb = time.time()
        time.sleep(0.1)

if __name__ == "__main__":
    main()
'''
