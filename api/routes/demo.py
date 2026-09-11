"""
Demo routes — video upload + YOLO annotation pipeline for cloud deployment.

This is a portfolio-piece alternative to the live camera system, since cloud
servers don't have webcams. Users upload a short video, we run YOLO over it,
and return an annotated MP4 with detection stats.
"""

import os
import shutil
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse

from core.video_demo import VideoDemoProcessor, make_temp_paths

router = APIRouter(prefix="/demo", tags=["Demo"])

_processor: VideoDemoProcessor | None = None


def get_processor() -> VideoDemoProcessor:
    """Lazy singleton — YOLO loads slowly, share across requests."""
    global _processor
    if _processor is None:
        _processor = VideoDemoProcessor()
    return _processor


ALLOWED_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm"}
MAX_UPLOAD_MB = 50  # Render free tier — keep uploads reasonable


@router.get("/health")
def demo_health():
    return {"status": "ok", "service": "agent-eye-demo"}


@router.post("/analyze-video")
async def analyze_video(
    file: UploadFile = File(...),
    max_frames: int = Query(300, ge=10, le=2000),
    sample_every: int = Query(1, ge=1, le=10),
):
    """
    Upload a video, get back an annotated MP4 + detection summary.

    - max_frames: cap on processed frames (default 300, max 2000)
    - sample_every: process every Nth frame to speed up long videos
    """
    # ── Validate ────────────────────────────────────────
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported video format '{ext}'. Use one of: {sorted(ALLOWED_EXT)}",
        )

    uid = uuid.uuid4().hex[:10]
    input_path, output_path = make_temp_paths(uid, file.filename or "video.mp4")

    # ── Save upload to /tmp ─────────────────────────────
    try:
        with open(input_path, "wb") as out:
            shutil.copyfileobj(file.file, out)
        size_mb = os.path.getsize(input_path) / (1024 * 1024)
        if size_mb > MAX_UPLOAD_MB:
            os.remove(input_path)
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({size_mb:.1f} MB). Max is {MAX_UPLOAD_MB} MB.",
            )
    finally:
        await file.close()

    # ── Run YOLO ────────────────────────────────────────
    try:
        summary = get_processor().process_video(
            input_path,
            output_path,
            max_frames=max_frames,
            sample_every=sample_every,
        )
    except Exception as e:
        # Best-effort cleanup
        for p in (input_path, output_path):
            try:
                os.remove(p)
            except OSError:
                pass
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")

    # ── Cleanup input, keep output for download ─────────
    try:
        os.remove(input_path)
    except OSError:
        pass

    return {
        "message": "Video processed successfully",
        "job_id": uid,
        "summary": summary,
        "annotated_video_url": f"/demo/download/{uid}",
    }


@router.get("/download/{job_id}")
async def download_annotated(job_id: str):
    """Download the annotated MP4 produced by /demo/analyze-video."""
    # Recover the output path
    from core.video_demo import make_temp_paths
    _, output_path = make_temp_paths(job_id, "x.mp4")
    if not os.path.exists(output_path):
        raise HTTPException(status_code=404, detail="Result not found or expired")
    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename=f"agenteye_{job_id}.mp4",
    )