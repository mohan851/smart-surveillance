import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from database.db import init_db
from api.routes import auth, cameras, detections, reports, demo

app = FastAPI(
    title       = "Smart Surveillance API",
    description = "AI-powered surveillance system",
    version     = "1.0.0"
)

# ── CORS ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Serve dashboard static files ─────────────────────────
app.mount("/static", StaticFiles(directory="dashboard"), name="static")

# ── Init database on startup ─────────────────────────────
@app.on_event("startup")
async def startup_event():
    init_db()
    print("🚀 Smart Surveillance API started")

# ── Routes ───────────────────────────────────────────────
app.include_router(auth.router,       prefix="/auth",       tags=["Auth"])
app.include_router(cameras.router,    prefix="/cameras",    tags=["Cameras"])
app.include_router(detections.router, prefix="/detections", tags=["Detections"])
app.include_router(reports.router,    prefix="/reports",    tags=["Reports"])
app.include_router(demo.router,       prefix="",            tags=["Demo"])

# ── Serve dashboard at root ───────────────────────────────
@app.get("/")
async def dashboard():
    # Cloud deploy serves the demo page; locally you can swap to index.html
    demo_path = "dashboard/demo.html"
    if os.path.exists(demo_path):
        return FileResponse(demo_path)
    return FileResponse("dashboard/index.html")

# ── Health check ─────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "running", "message": "Smart Surveillance API is live"}