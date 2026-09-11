"""
Database engine + session factory + init for Agent Eye.
- Cloud  → PostgreSQL (Supabase) via the connection pooler.
- Local  → SQLite (file-based, no install).
The choice is made by USE_SQLITE env var or auto-fallback if Supabase is unreachable.
"""
from __future__ import annotations
import os
import logging
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker, scoped_session

from config import SUPABASE_DB_URL, SQLITE_PATH, USE_SQLITE
from database.models import Base

log = logging.getLogger("agent_eye.db")


# ── Engine selection ─────────────────────────────────────
def _make_engine():
    """Pick Postgres (cloud) or SQLite (local) and return an engine."""
    if USE_SQLITE:
        log.info("DB: SQLite (USE_SQLITE env flag set)")
        return _sqlite_engine()

    # Try Postgres first
    try:
        engine = create_engine(
            SUPABASE_DB_URL,
            pool_pre_ping=True,         # auto-reconnect on stale conn
            pool_recycle=300,           # recycle every 5 min (Supabase idle = 6 min)
            pool_size=5,
            max_overflow=10,
            future=True,
        )
        with engine.connect() as c:
            c.execute(__import__("sqlalchemy").text("SELECT 1"))
        log.info("DB: PostgreSQL (Supabase) connected")
        return engine
    except Exception as e:
        log.warning("DB: Postgres unreachable (%s) — falling back to SQLite", e)
        return _sqlite_engine()


def _sqlite_engine():
    os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
    engine = create_engine(
        f"sqlite:///{SQLITE_PATH}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    return engine


engine = _make_engine()
SessionLocal = scoped_session(
    sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
)


# ── Public helpers ────────────────────────────────────────
def init_db() -> None:
    """Create all tables if missing. Safe to call on every startup."""
    Base.metadata.create_all(bind=engine)
    log.info("✅ Database schema ready")


def get_session():
    """Return a SQLAlchemy session. Caller must close() it."""
    return SessionLocal()


@contextmanager
def session_scope():
    """Context manager that auto-commits on success, rolls back on error."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


# ── Convenience queries used by routes ───────────────────
def get_user_by_username(username: str):
    with session_scope() as s:
        return s.query(__import__("database.models", fromlist=["User"]).User) \
                .filter_by(username=username).first()


def get_user_by_id(user_id: int):
    from database.models import User
    with session_scope() as s:
        return s.query(User).filter_by(id=user_id).first()


def count_users() -> int:
    from database.models import User
    with session_scope() as s:
        return s.query(User).count()


# ── Stand-alone init (run as `python -m database.db`) ─────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("DB ready at", SUPABASE_DB_URL if not USE_SQLITE else SQLITE_PATH)
