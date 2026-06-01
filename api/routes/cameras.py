from fastapi import APIRouter, Depends, HTTPException
from api.middleware import get_current_user, require_admin

router = APIRouter()

# ── In-memory camera state ───────────────────────────────
camera_states = {}

@router.get("/")
def get_cameras(current_user=Depends(get_current_user)):
    from config import CAMERA_IDS
    cameras = []
    for cam_id in CAMERA_IDS:
        cameras.append({
            "camera_id" : cam_id,
            "active"    : camera_states.get(cam_id, True)
        })
    return cameras

@router.post("/{camera_id}/on")
def turn_on(camera_id: int, admin=Depends(require_admin)):
    camera_states[camera_id] = True
    return {"camera_id": camera_id, "status": "on"}

@router.post("/{camera_id}/off")
def turn_off(camera_id: int, admin=Depends(require_admin)):
    camera_states[camera_id] = False
    return {"camera_id": camera_id, "status": "off"}

@router.get("/{camera_id}/status")
def get_status(camera_id: int, current_user=Depends(get_current_user)):
    return {
        "camera_id" : camera_id,
        "active"    : camera_states.get(camera_id, True)
    }