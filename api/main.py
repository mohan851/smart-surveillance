"""
Agent Eye — FastAPI entry point (production-hardened).

Multi-tenant routes:
  /auth/...            auth, signup, login, me
  /me/settings/...     per-user config (Telegram, camera, alerts)
  /agent/...           local agent ↔ cloud (register, heartbeat, event)
  /me/...              dashboard data (stats, detections, agents, agent-script)
  /cameras/...         per-user camera/agent list
  /detections/...      per-user detection history + known faces
  /reports/...         per-user PDF export

Production hardening:
  - DB init runs in a background thread with a timeout.
    If Supabase is slow/down, the app still starts.
  - /health/live  — NEVER touches DB (Railway liveness probe)
  - /health       — touches DB (readiness probe; returns 503 if DB is down)
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging
import threading
from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from api.routes import auth, cameras, detections, reports, settings, agent_api, dashboard

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("agent_eye")


# ── DB init in background, with hard timeout ─────────────
_db_ready = threading.Event()
_db_error: str | None = None


def _safe_init_db():
    """Run init_db() in a worker thread. Never crashes the main process."""
    global _db_error
    try:
        from database.db import init_db
        init_db()
        log.info("Database schema ready")
    except Exception as e:
        _db_error = str(e)
        log.error("Database init FAILED: %s", e)
    finally:
        _db_ready.set()


app = FastAPI(
    title       = "Agent Eye API",
    description = "AI-powered multi-tenant smart surveillance",
    version     = "2.1.0",
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


# ── Init schema on startup (non-blocking, fault-tolerant) ─
@app.on_event("startup")
async def startup_event():
    log.info("Agent Eye API starting...")
    t = threading.Thread(target=_safe_init_db, daemon=True, name="db-init")
    t.start()
    # Wait up to 5s for DB; don't block forever if it's slow.
    _db_ready.wait(timeout=5.0)
    if _db_error:
        log.warning("DB not ready at startup — app will start anyway. Error: %s", _db_error)
    else:
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


# ── Health: liveness (NO DB) ─────────────────────────────
@app.get("/health/live")
async def health_live():
    """Railway pings this. MUST NOT touch the DB — always returns 200
    as long as the process is alive. If this fails, Railway kills the
    container and starts a new one."""
    return {"status": "alive"}


# ── Health: readiness (touches DB) ───────────────────────
@app.get("/health")
async def health():
    """Returns 200 with DB info if everything works.
    Returns 503 if DB is unreachable so Railway can flag it."""
    from database.db import engine
    db_kind = "postgresql" if "postgresql" in str(engine.url) else "sqlite"
    db_ok   = True
    db_msg  = "ok"
    try:
        from sqlalchemy import text
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception as e:
        db_ok  = False
        db_msg = str(e)[:200]
    payload = {
        "status":   "running" if db_ok else "degraded",
        "message":  "Agent Eye API is live",
        "version":  "2.1.0",
        "database": db_kind,
        "db_ok":    db_ok,
    }
    if not db_ok:
        payload["db_error"] = db_msg
        return Response(
            content=str(payload).replace("'", '"'),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            media_type="application/json",
        )
    return payload
