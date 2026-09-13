"""
Dashboard data routes — all scoped to the current user.
- GET /me/stats              summary counts
- GET /me/detections         paginated list of events
- GET /me/agents             list this user's agents/cameras
- GET /me/agent-script/{id}  download Python script for one specific camera
- GET /me/snapshots/dates    list of dates with photo counts
- GET /me/snapshots?date=…   list snapshots for one date
- GET /me/snapshots/{id}/image  serve the JPEG bytes for inline view
"""
import io
import platform
from datetime import datetime, timedelta
from collections import OrderedDict
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
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
import os, sys, time, uuid, platform, hashlib, base64
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

MACHINE_ID   = hashlib.sha256(platform.node().encode()).hexdigest()[:16]
MACHINE_NAME = platform.node()

# Pulled from /agent/config on startup
UPLOAD_SNAPSHOTS   = False
TELEGRAM_ENABLED   = False
SNAPSHOT_DIR       = "snapshots"
COOLDOWN_S         = 10

_last_alert = {{}}


def post(path, payload):
    try:
        return requests.post(
            CLOUD_URL + path,
            json=payload,
            headers={{"X-Agent-Token": AGENT_TOKEN}},
            timeout=15,
        )
    except Exception as e:
        print("[cloud] post failed:", e)
        return None


def get_config():
    """Fetch runtime config from the cloud (upload_snapshots, cooldown, etc.)."""
    try:
        r = requests.get(
            CLOUD_URL + "/agent/config",
            headers={{"X-Agent-Token": AGENT_TOKEN}},
            timeout=10,
        )
        if r.ok:
            return r.json()
    except Exception as e:
        print("[cloud] config fetch failed (using defaults):", e)
    return {{}}


def open_camera():
    """Open the configured camera source. Returns cv2.VideoCapture."""
    if CAMERA_TYPE == "webcam":
        idx = int(CAMERA_SOURCE) if CAMERA_SOURCE.isdigit() else 0
        return cv2.VideoCapture(idx)
    if CAMERA_TYPE == "rtsp":
        url = CAMERA_SOURCE
        if CAMERA_USER and CAMERA_PASS and "@" not in url:
            from urllib.parse import urlparse, urlunparse
            p = urlparse(url)
            netloc = f"{{CAMERA_USER}}:{{CAMERA_PASS}}@{{p.hostname}}" + (f":{{p.port}}" if p.port else "")
            url = urlunparse(p._replace(netloc=netloc))
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
    global UPLOAD_SNAPSHOTS, TELEGRAM_ENABLED, SNAPSHOT_DIR, COOLDOWN_S
    print(f"Agent Eye agent starting | machine={{MACHINE_NAME}} | camera={{CAMERA_NAME}} ({{CAMERA_TYPE}})")

    # Pull latest config from the cloud
    cfg = get_config()
    UPLOAD_SNAPSHOTS = cfg.get("upload_snapshots", False)
    TELEGRAM_ENABLED = cfg.get("telegram_enabled", False)
    SNAPSHOT_DIR     = cfg.get("snapshot_dir", "snapshots")
    COOLDOWN_S       = cfg.get("detection_cooldown", 10)
    print(f"[config] upload_snapshots={{UPLOAD_SNAPSHOTS}} telegram={{TELEGRAM_ENABLED}} cooldown={{COOLDOWN_S}}s")

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
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0); continue
            time.sleep(1); continue
        frame_idx += 1
        if frame_idx % 3 != 0:
            if time.time() - last_hb > HEARTBEAT_S:
                post("/agent/heartbeat", {{"camera_source": f"{{CAMERA_TYPE}}:{{CAMERA_SOURCE}}"}})
                last_hb = time.time()
            time.sleep(0.05); continue
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            snap_path = os.path.join(
                SNAPSHOT_DIR,
                f"{{datetime.utcnow():%Y%m%d_%H%M%S}}_{{uuid.uuid4().hex[:6]}}.jpg",
            )
            os.makedirs(SNAPSHOT_DIR, exist_ok=True)
            cv2.imwrite(snap_path, frame)

            payload = {{
                "label":         "Unknown",
                "confidence":    0,
                "snapshot_path": snap_path,
                "camera_source": f"{{CAMERA_TYPE}}:{{CAMERA_SOURCE}}",
                "timestamp":     datetime.utcnow().isoformat(),
            }}

            # Opt-in: also send the JPEG bytes to the cloud (base64)
            if UPLOAD_SNAPSHOTS:
                try:
                    with open(snap_path, "rb") as fh:
                        payload["snapshot_b64"] = base64.b64encode(fh.read()).decode("ascii")
                except Exception as e:
                    print("[upload] failed to read snapshot:", e)

            now = time.time()
            if now - _last_alert.get("face", 0) > COOLDOWN_S:
                _last_alert["face"] = now
                resp = post("/agent/event", payload)
                tag = "+cloud" if UPLOAD_SNAPSHOTS else "local-only"
                print(f"[detection] {{CAMERA_NAME}} face @ {{snap_path}} ({{tag}})")
        if time.time() - last_hb > HEARTBEAT_S:
            post("/agent/heartbeat", {{"camera_source": f"{{CAMERA_TYPE}}:{{CAMERA_SOURCE}}"}})
            last_hb = time.time()
        time.sleep(0.05)


if __name__ == "__main__":
    main()
'''


# ══════════════════════════════════════════════
# Cloud-uploaded snapshots — date-grouped viewer
# ══════════════════════════════════════════════

@router.get("/snapshots/dates")
def snapshots_dates(current_user=Depends(get_current_user)):
    """List dates that have at least one cloud-uploaded snapshot,
    with the count per date. Powers the date-folders in the dashboard."""
    uid = current_user["id"]
    with session_scope() as s:
        rows = (
            s.query(Detection.timestamp, Detection.id)
             .filter(Detection.user_id == uid, Detection.snapshot_data.isnot(None))
             .order_by(desc(Detection.timestamp))
             .all()
        )
    # Group by date (UTC)
    by_date = OrderedDict()
    for ts, _id in rows:
        key = ts.strftime("%Y-%m-%d")
        by_date[key] = by_date.get(key, 0) + 1
    return [{"date": d, "count": c} for d, c in by_date.items()]


@router.get("/snapshots")
def snapshots_for_date(date: str = Query(..., description="YYYY-MM-DD"),
                       current_user=Depends(get_current_user)):
    """List all cloud snapshots for one date. Returns metadata + thumbnail URLs."""
    try:
        day_start = datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    day_end = day_start + timedelta(days=1)
    uid = current_user["id"]
    with session_scope() as s:
        rows = (
            s.query(Detection)
             .filter(Detection.user_id == uid,
                     Detection.snapshot_data.isnot(None),
                     Detection.timestamp >= day_start,
                     Detection.timestamp <  day_end)
             .order_by(desc(Detection.timestamp))
             .all()
        )
        out = []
        for r in rows:
            out.append({
                "id":         r.id,
                "label":      r.label,
                "timestamp":  r.timestamp.isoformat() if r.timestamp else None,
                "has_image":  r.snapshot_data is not None,
                "image_url":  f"/me/snapshots/{r.id}/image" if r.snapshot_data else None,
                "camera":     r.camera_source or "—",
            })
        return out


@router.get("/snapshots/{snap_id}/image")
def snapshot_image(snap_id: int, current_user=Depends(get_current_user)):
    """Serve the raw JPEG bytes for inline display in the dashboard."""
    with session_scope() as s:
        r = s.query(Detection).filter_by(id=snap_id, user_id=current_user["id"]).first()
        if not r or not r.snapshot_data:
            raise HTTPException(status_code=404, detail="Snapshot not found")
        return Response(
            content=bytes(r.snapshot_data),
            media_type="image/jpeg",
            headers={"Cache-Control": "private, max-age=3600"},
        )


# ── Browser-side detection event (JWT auth, not agent token) ──
class BrowserEventIn(BaseModel):
    label         : str = "Unknown"
    confidence    : int = 0
    snapshot_b64  : str | None = None
    camera_source : str | None = None
    timestamp     : str | None = None


@router.post("/browser-event")
def browser_event(payload: BrowserEventIn, current_user=Depends(get_current_user)):
    """Called by the Live Detection page in the browser.
    JWT-authenticated (no agent_token needed) so the logged-in user can
    push detection events directly from the dashboard."""
    import base64
    with session_scope() as s:
        settings = s.query(UserSettings).filter_by(user_id=current_user["id"]).first()

        snap_bytes = None
        if payload.snapshot_b64 and settings and settings.upload_snapshots:
            try:
                snap_bytes = base64.b64decode(payload.snapshot_b64)
                if len(snap_bytes) > 5 * 1024 * 1024:
                    snap_bytes = None
            except Exception:
                snap_bytes = None

        d = Detection(
            user_id       = current_user["id"],
            agent_id      = None,
            label         = payload.label,
            confidence    = payload.confidence,
            snapshot_path = None,
            snapshot_data = snap_bytes,
            camera_source = payload.camera_source or "browser",
            timestamp     = datetime.utcnow(),
        )
        s.add(d)
        s.flush()

        channel = "telegram" if settings and settings.telegram_bot_token else "none"
        if settings:
            if payload.label.lower() == "unknown" and not settings.alert_on_unknown:
                channel = "none"
            if payload.label.lower() != "unknown" and not settings.alert_on_known:
                channel = "none"
        s.add(Alert(
            user_id      = current_user["id"],
            detection_id = d.id,
            channel      = channel,
            status       = "queued",
            timestamp    = datetime.utcnow(),
        ))

        return {
            "ok":            True,
            "detection_id":  d.id,
            "alert_channel": channel,
            "snapshot_saved": snap_bytes is not None,
        }
