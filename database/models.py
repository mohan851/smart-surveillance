"""
Multi-tenant database models for Agent Eye.
Uses SQLAlchemy 2.0 declarative style. Works on both PostgreSQL (cloud) and SQLite (local dev).

Schema design:
- Every business table carries a `user_id` foreign key for tenant isolation.
- A query like `Detections.user_id == current_user.id` ensures one customer
  can never read or overwrite another customer's data.
- `agents` table lets a user register multiple PCs / cameras under one account.
"""
from __future__ import annotations
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Index, LargeBinary
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


# ── users ─────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    username      = Column(String(80),  unique=True, nullable=False, index=True)
    email         = Column(String(120), unique=True, nullable=True)
    password      = Column(String(255), nullable=False)            # bcrypt hash
    role          = Column(String(20),  nullable=False, default="customer")
    full_name     = Column(String(120), nullable=True)
    company       = Column(String(120), nullable=True)
    is_verified   = Column(Boolean,     default=False)
    verify_code   = Column(String(8),   nullable=True)             # 6-digit OTP
    verify_expires= Column(DateTime,    nullable=True)
    created_at    = Column(DateTime,    default=datetime.utcnow)
    last_login_at = Column(DateTime,    nullable=True)
    is_active     = Column(Boolean,     default=True)

    settings = relationship("UserSettings", uselist=False, back_populates="user",
                            cascade="all, delete-orphan")
    agents   = relationship("Agent",        back_populates="user",
                            cascade="all, delete-orphan")


# ── user_settings (1:1 with user) ─────────────────────────
class UserSettings(Base):
    __tablename__ = "user_settings"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    user_id             = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                                 unique=True, nullable=False)
    telegram_bot_token  = Column(String(120), nullable=True)
    telegram_chat_id    = Column(String(40),  nullable=True)
    camera_source       = Column(String(255), nullable=True)  # 0, rtsp://..., http://...
    alert_on_unknown    = Column(Boolean, default=True)
    alert_on_known      = Column(Boolean, default=False)
    snapshot_dir        = Column(String(255), default="snapshots")
    detection_cooldown  = Column(Integer, default=10)         # seconds between alerts
    upload_snapshots    = Column(Boolean, default=False)      # privacy: off by default
    cloud_retention_days= Column(Integer, default=30)         # auto-delete cloud snapshots older than N days
    updated_at          = Column(DateTime, default=datetime.utcnow,
                                 onupdate=datetime.utcnow)

    user = relationship("User", back_populates="settings")


# ── agents (1 user → N agents; e.g. multiple PCs / cameras) ─
class Agent(Base):
    __tablename__ = "agents"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    user_id        = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                            nullable=False, index=True)
    agent_token    = Column(String(80), unique=True, nullable=False, index=True)
    machine_id     = Column(String(120), nullable=False)
    machine_name   = Column(String(120), nullable=True)
    camera_name    = Column(String(120), nullable=True)
    camera_type    = Column(String(20),  default="webcam")  # webcam|rtsp|http|file
    camera_source  = Column(String(255), nullable=True)
    camera_user    = Column(String(120), nullable=True)
    camera_pass    = Column(String(255), nullable=True)
    last_seen_at   = Column(DateTime, nullable=True)
    last_ip        = Column(String(64),  nullable=True)
    status         = Column(String(20),  default="offline")  # online|offline|error
    events_sent    = Column(Integer,     default=0)
    created_at     = Column(DateTime,     default=datetime.utcnow)

    user = relationship("User", back_populates="agents")
    detections = relationship("Detection", back_populates="agent",
                              cascade="all, delete-orphan")


# ── detections (events pushed by the agent) ───────────────
class Detection(Base):
    __tablename__ = "detections"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    user_id       = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    agent_id      = Column(Integer, ForeignKey("agents.id", ondelete="SET NULL"),
                           nullable=True)
    label         = Column(String(80),   nullable=False)         # "Unknown" or "Mohan"
    confidence    = Column(Integer,      default=0)              # 0-100
    snapshot_path = Column(String(255),  nullable=True)           # local path on customer PC
    snapshot_data = Column(LargeBinary,  nullable=True)           # JPEG bytes if cloud-uploaded
    camera_source = Column(String(255),  nullable=True)
    timestamp     = Column(DateTime,     default=datetime.utcnow, index=True)

    agent = relationship("Agent", back_populates="detections")
    alert = relationship("Alert", back_populates="detection", uselist=False,
                         cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_detections_user_ts", "user_id", "timestamp"),
    )


# ── alerts (delivery record for each detection) ───────────
class Alert(Base):
    __tablename__ = "alerts"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    user_id       = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    detection_id  = Column(Integer, ForeignKey("detections.id", ondelete="CASCADE"),
                           unique=True, nullable=False)
    channel       = Column(String(20),  nullable=False)         # telegram|email|none
    status        = Column(String(20),  nullable=False)         # sent|failed|skipped
    error_message = Column(Text,        nullable=True)
    timestamp     = Column(DateTime,    default=datetime.utcnow)

    detection = relationship("Detection", back_populates="alert")


# ── known_faces (per-tenant) ──────────────────────────────
class KnownFace(Base):
    __tablename__ = "known_faces"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    name       = Column(String(80),  nullable=False)
    image_path = Column(String(255), nullable=False)
    added_at   = Column(DateTime,    default=datetime.utcnow)

    __table_args__ = (
        Index("uq_known_user_name", "user_id", "name", unique=True),
    )
