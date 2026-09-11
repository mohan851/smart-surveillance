"""
Agent Eye — FastAPI entry point.

Multi-tenant routes:
  /auth/...            auth, signup, login, me
  /me/settings/...     per-user config (Telegram, camera, alerts)
  /agent/...           local agent ↔ cloud (register, heartbeat, event)
  /me/...              dashboard data (stats, detections, agents, agent-script)
  /cameras/...         per-user camera/agent list
  /detections/...      per-user detection history + known faces
  /reports/...         per-user PDF export
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from database.db import init_db
from api.routes import auth, cameras, detections, reports, settings, agent_api, dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("agent_eye")

app = FastAPI(
    title       = "Agent Eye API",
    description = "AI-powered multi-tenant smart surveillance",
    version     = "2.0.0",
)

# ── CORS ─────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ── Static dashboard ─────────────────────────────────────
app.mount("/static", StaticFiles(directory="dashboard"), name="static")


# ── Init schema on startup ───────────────────────────────
@app.on_event("startup")
async def startup_event():
    init_db()
    log.info("Agent Eye API started")


# ── Routes ───────────────────────────────────────────────
app.include_router(auth.router,       prefix="/auth",       tags=["Auth"])
app.include_router(settings.router,                       tags=["Settings"])
app.include_router(agent_api.router,                      tags=["Agent"])
app.include_router(dashboard.router,                      tags=["Dashboard"])
app.include_router(cameras.router,                        tags=["Cameras"])
app.include_router(detections.router,                     tags=["Detections"])
app.include_router(reports.router,                        tags=["Reports"])


# ── Dashboard at root ────────────────────────────────────
@app.get("/")
async def dashboard():
    return FileResponse("dashboard/index.html")


# ── Health check ─────────────────────────────────────────
@app.get("/health")
async def health():
    from database.db import engine
    db_kind = "postgresql" if "postgresql" in str(engine.url) else "sqlite"
    return {
        "status": "running",
        "message": "Agent Eye API is live",
        "version": "2.0.0",
        "database": db_kind,
    }
