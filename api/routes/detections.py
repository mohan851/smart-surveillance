from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from api.middleware import get_current_user, require_admin
from database.models import get_all_detections, insert_known_face, get_all_known_faces
import os
import shutil
from fastapi import UploadFile, File, Form
from config import KNOWN_FACES_DIR, SNAPSHOTS_DIR

router = APIRouter()

# ── Get all detections ───────────────────────────────────
@router.get("/")
def get_detections(
    limit        : int = 100,
    current_user      = Depends(get_current_user)
):
    return get_all_detections(limit=limit)

# ── Get snapshot image ───────────────────────────────────
@router.get("/snapshot/{filename}")
def get_snapshot(filename: str):
    path = os.path.join(SNAPSHOTS_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(path)

# ── Get all known faces ──────────────────────────────────
@router.get("/known-faces")
def known_faces(current_user=Depends(get_current_user)):
    return get_all_known_faces()

# ── Register a new known face ────────────────────────────
@router.post("/known-faces")
async def register_face(
    name         : str        = Form(...),
    file         : UploadFile = File(...),
    admin                     = Depends(require_admin)
):
    ext      = os.path.splitext(file.filename)[1]
    filename = f"{name}{ext}"
    path     = os.path.join(KNOWN_FACES_DIR, filename)

    with open(path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    insert_known_face(name, path)
    return {"message": f"Face registered for '{name}'", "path": path}

# ── Delete a known face ──────────────────────────────────
@router.delete("/known-faces/{name}")
def delete_face(name: str, admin=Depends(require_admin)):
    conn = __import__('database.db', fromlist=['get_connection']).get_connection()
    row  = conn.execute(
        "SELECT image_path FROM known_faces WHERE name = ?", (name,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Face not found")
    if os.path.exists(row["image_path"]):
        os.remove(row["image_path"])
    conn.execute("DELETE FROM known_faces WHERE name = ?", (name,))
    conn.commit()
    conn.close()
    return {"message": f"Face '{name}' deleted"}