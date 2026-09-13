"""
Dashboard data routes — all scoped to the current user.
- GET /me/stats              summary counts
- GET /me/detections         paginated list of events
- GET /me/agents             list this user's agents/cameras
- GET /me/agent-script/{id}  download Python script for one specific camera
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
                "camera_name":  a.camera_name or a.machine_name,
                "camera_type":  a.camera_type or "webcam",
                "camera_source":a.camera_source,
                "status":       a.status,
                "events_sent":  a.events_sent,
                "last_seen_at": a.last_seen_at.isoformat() if a.last_seen_at else None,
                "created_at":   a.created_at.isoformat() if a.created_at else None,
            })
        return out


@router.get("/agent-script/{agent_id}")
def download_agent_script(agent_id: int, current_user=Depends(get_current_user)):
    """Return the local agent Python file tailored to one specific camera."""
    with session_scope() as s:
        a = s.query(Agent).filter_by(id=agent_id, user_id=current_user["id"]).first()
        if not a:
            raise HTTPException(status_code=404, detail="Agent not found")
        token       = a.agent_token
        cam_type    = a.camera_type or "webcam"
        cam_source  = a.camera_source or "0"
        cam_name    = a.camera_name or a.machine_name or "camera"
        cam_user    = a.camera_user or ""
        cam_pass    = a.camera_pass or ""

    script = AGENT_SCRIPT_TEMPLATE.format(
        cloud_url    = "https://smart-surveillance-production.up.railway.app",
        agent_token  = token,
        username     = current_user["username"],
        camera_type  = cam_type,
        camera_source= cam_source,
        camera_name  = cam_name,
        camera_user  = cam_user,
        camera_pass  = cam_pass,
    )
    fname = f"agent_eye_{re.sub(r'[^a-z0-9]+', '_', cam_name.lower())}.py"
    return StreamingResponse(
        io.BytesIO(script.encode("utf-8")),
        media_type="text/x-python",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


# ── Agent script template (camera-aware) ─────────────────
import re

AGENT_SCRIPT_TEMPLATE = r'''#!/usr/bin/env python3
"""
Agent Eye — local agent for customer: {username}
Camera:     {camera_name}  ({camera_type})
Auto-generated. Do not share — it contains your agent token.

Quick start:
    pip install opencv-python requests
    python agent_eye_local.py
"""
import os, sys, time, uuid, platform, hashlib
from datetime import datetime
import requests, cv2

CLOUD_URL    = "{cloud_url}"
AGENT_TOKEN  = "{agent_token}"
CAMERA_TYPE  = "{camera_type}"     # webcam | rtsp | http | file
CAMERA_NAME  = "{camera_name}"
CAMERA_SOURCE= "{camera_source}"   # 0, rtsp://..., http://..., /path.mp4
CAMERA_USER  = "{camera_user}"
CAMERA_PASS  = "{camera_pass}"
HEARTBEAT_S  = 30
COOLDOWN_S   = 10

MACHINE_ID   = hashlib.sha256(platform.node().encode()).hexdigest()[:16]
MACHINE_NAME = platform.node()

_last_alert = {{}}


def post(path, payload):
    try:
        return requests.post(
            CLOUD_URL + path,
            json=payload,
            headers={{"X-Agent-Token": AGENT_TOKEN}},
            timeout=10,
        )
    except Exception as e:
        print("[cloud] post failed:", e)
        return None


def open_camera():
    """Open the configured camera source. Returns cv2.VideoCapture."""
    if CAMERA_TYPE == "webcam":
        idx = int(CAMERA_SOURCE) if CAMERA_SOURCE.isdigit() else 0
        return cv2.VideoCapture(idx)
    if CAMERA_TYPE == "rtsp":
        url = CAMERA_SOURCE
        if CAMERA_USER and CAMERA_PASS:
            # Inject credentials into RTSP URL if not already present
            if "@" not in url:
                from urllib.parse import urlparse, urlunparse
                p = urlparse(url)
                netloc = f"{{CAMERA_USER}}:{{CAMERA_PASS}}@{{p.hostname}}" + (f":{{p.port}}" if p.port else "")
                url = urlunparse(p._replace(netloc=netloc))
        # FFMPEG backend gives us RTSP/HTTP support; CAP_FFMPEG keeps it explicit
        return cv2.VideoCapture(url, cv2.CAP_FFMPEG)
    if CAMERA_TYPE == "http":
        return cv2.VideoCapture(CAMERA_SOURCE)
    if CAMERA_TYPE == "file":
        if not os.path.exists(CAMERA_SOURCE):
            print(f"ERROR: video file not found: {{CAMERA_SOURCE}}")
            sys.exit(1)
        return cv2.VideoCapture(CAMERA_SOURCE)
    print(f"ERROR: unknown camera_type {{CAMERA_TYPE}}")
    sys.exit(1)


def main():
    print(f"Agent Eye agent starting | machine={{MACHINE_NAME}} | camera={{CAMERA_NAME}} ({{CAMERA_TYPE}})")
    cap = open_camera()
    if not cap.isOpened():
        print(f"ERROR: cannot open camera '{{CAMERA_SOURCE}}'")
        sys.exit(1)
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    last_hb = 0
    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            if CAMERA_TYPE == "file":
                print("[file] end of video — looping")
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            time.sleep(1); continue
        frame_idx += 1
        # Run face detection every 3rd frame to save CPU
        if frame_idx % 3 != 0:
            if time.time() - last_hb > HEARTBEAT_S:
                post("/agent/heartbeat", {{"camera_source": f"{{CAMERA_TYPE}}:{{CAMERA_SOURCE}}"}})
                last_hb = time.time()
            time.sleep(0.05)
            continue
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            snap = os.path.join(
                "snapshots",
                f"{{datetime.utcnow():%Y%m%d_%H%M%S}}_{{uuid.uuid4().hex[:6]}}.jpg",
            )
            os.makedirs("snapshots", exist_ok=True)
            cv2.imwrite(snap, frame)
            now = time.time()
            if now - _last_alert.get("face", 0) > COOLDOWN_S:
                _last_alert["face"] = now
                post("/agent/event", {{
                    "label":         "Unknown",
                    "confidence":    0,
                    "snapshot_path": snap,
                    "camera_source": f"{{CAMERA_TYPE}}:{{CAMERA_SOURCE}}",
                    "timestamp":     datetime.utcnow().isoformat(),
                }})
                print(f"[detection] {{CAMERA_NAME}} face @ {{snap}}")
        if time.time() - last_hb > HEARTBEAT_S:
            post("/agent/heartbeat", {{"camera_source": f"{{CAMERA_TYPE}}:{{CAMERA_SOURCE}}"}})
            last_hb = time.time()
        time.sleep(0.05)


if __name__ == "__main__":
    main()
'''
