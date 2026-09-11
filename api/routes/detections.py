"""
Detection list / known-faces / reports — all scoped to the current user.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from typing import Optional

from api.middleware import get_current_user
from database.db import session_scope
from database.models import Detection, Alert, KnownFace
from api.routes.agent_api import _list_user_detections

router = APIRouter(prefix="/detections", tags=["Detections"])


@router.get("")
def list_detections(limit: int = 100, label: Optional[str] = None,
                    current_user=Depends(get_current_user)):
    uid = current_user["id"]
    with session_scope() as s:
        q = s.query(Detection).filter_by(user_id=uid)
        if label:
            q = q.filter(Detection.label == label)
        rows = q.order_by(desc(Detection.timestamp)).limit(limit).all()
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


@router.get("/known-faces")
def list_known_faces(current_user=Depends(get_current_user)):
    uid = current_user["id"]
    with session_scope() as s:
        rows = s.query(KnownFace).filter_by(user_id=uid).all()
        return [{
            "id":         r.id,
            "name":       r.name,
            "image_path": r.image_path,
            "added_at":   r.added_at.isoformat() if r.added_at else None,
        } for r in rows]


@router.post("/known-faces")
def add_known_face(name: str, image_path: str, current_user=Depends(get_current_user)):
    uid = current_user["id"]
    with session_scope() as s:
        existing = s.query(KnownFace).filter_by(user_id=uid, name=name).first()
        if existing:
            existing.image_path = image_path
            return {"message": f"Updated '{name}'"}
        kf = KnownFace(user_id=uid, name=name, image_path=image_path)
        s.add(kf)
        return {"message": f"Added known face '{name}'"}


@router.delete("/known-faces/{face_id}")
def delete_known_face(face_id: int, current_user=Depends(get_current_user)):
    uid = current_user["id"]
    with session_scope() as s:
        kf = s.query(KnownFace).filter_by(id=face_id, user_id=uid).first()
        if not kf:
            raise HTTPException(status_code=404, detail="Not found")
        s.delete(kf)
        return {"message": "Removed"}
