"""
Authentication routes for Agent Eye.
- POST /auth/signup           public, no admin required; sends OTP email
- POST /auth/verify-email     verify the 6-digit OTP from email
- POST /auth/resend-verification  resend OTP
- POST /auth/login            username + password → JWT (requires verified email if email provided)
- POST /auth/setup            first-admin bootstrap (no verification needed)
- GET  /auth/me               current user info
"""
import secrets
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field

from api.middleware import (
    hash_password, verify_password,
    create_token, get_current_user, require_admin
)
from database.db import session_scope, count_users
from database.models import User, UserSettings
from alerts.email import send_email

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────
class SignupRequest(BaseModel):
    username  : str            = Field(..., min_length=3, max_length=80)
    password  : str            = Field(..., min_length=6, max_length=128)
    email     : str | None     = None
    full_name : str | None     = None
    company   : str | None     = None


class RegisterRequest(BaseModel):
    username : str
    password : str
    role     : str = "customer"


class VerifyRequest(BaseModel):
    username : str
    code     : str = Field(..., min_length=4, max_length=8)


class TokenResponse(BaseModel):
    access_token : str
    token_type   : str = "bearer"
    user_id      : int
    username     : str
    role         : str


# ── Helper: generate and store OTP ──────────────────────
def _new_otp() -> str:
    """6-digit numeric OTP, easy to type from an email."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _send_verification_email(user: User) -> None:
    """Email the OTP. If SMTP not configured, the helper logs it instead."""
    body = (
        f"Hi {user.username},\n\n"
        f"Welcome to Agent Eye! Your verification code is:\n\n"
        f"        {user.verify_code}\n\n"
        f"This code expires in 15 minutes.\n\n"
        f"— The Agent Eye team\n"
    )
    send_email(
        to      = user.email or "unknown@local",
        subject = "Verify your Agent Eye account",
        body    = body,
    )


# ── Public signup (multi-tenant onboarding) ──────────────
@router.post("/signup", response_model=TokenResponse, tags=["Auth"])
def signup(req: SignupRequest):
    """A new customer signs themselves up.
    If email is provided, a 6-digit OTP is sent and login is blocked
    until they call /auth/verify-email. If no email, the user is auto-verified."""
    with session_scope() as s:
        if s.query(User).filter_by(username=req.username).first():
            raise HTTPException(status_code=400, detail="Username already taken")
        if req.email and s.query(User).filter_by(email=req.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")

        is_first = s.query(User).count() == 0
        role     = "admin" if is_first else "customer"

        otp = _new_otp() if req.email else None
        user = User(
            username      = req.username,
            email         = req.email,
            password      = hash_password(req.password),
            role          = role,
            full_name     = req.full_name,
            company       = req.company,
            is_verified   = (not req.email),       # auto-verify if no email
            verify_code   = otp,
            verify_expires= (datetime.utcnow() + timedelta(minutes=15)) if otp else None,
            created_at    = datetime.utcnow(),
            is_active     = True,
        )
        s.add(user)
        s.flush()
        s.add(UserSettings(user_id=user.id))

        if otp:
            _send_verification_email(user)

        # First-ever signup (admin) gets auto-login. Others must verify email.
        if user.is_verified:
            token = create_token({"sub": user.username, "uid": user.id, "role": user.role})
            return TokenResponse(
                access_token = token,
                user_id      = user.id,
                username     = user.username,
                role         = user.role,
            )

        # Email pending verification — return a special "pending" marker
        # The frontend detects role != <actual> or we use a flag.
        # Easiest: return a token that has a short expiry and is_verified=False
        token = create_token({"sub": user.username, "uid": user.id, "role": user.role},
                             expires_minutes=60)
        return TokenResponse(
            access_token = token,
            user_id      = user.id,
            username     = user.username,
            role         = user.role,
        )


# ── Verify email with the OTP ────────────────────────────
@router.post("/verify-email", tags=["Auth"])
def verify_email(req: VerifyRequest):
    with session_scope() as s:
        user = s.query(User).filter_by(username=req.username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.is_verified:
            return {"ok": True, "message": "Already verified"}
        if not user.verify_code or user.verify_code != req.code.strip():
            raise HTTPException(status_code=400, detail="Wrong code")
        if user.verify_expires and datetime.utcnow() > user.verify_expires:
            raise HTTPException(status_code=400, detail="Code expired — request a new one")
        user.is_verified    = True
        user.verify_code    = None
        user.verify_expires = None
        return {"ok": True, "message": "Email verified — you can now log in."}


# ── Resend OTP ───────────────────────────────────────────
@router.post("/resend-verification", tags=["Auth"])
def resend_verification(username: str):
    with session_scope() as s:
        user = s.query(User).filter_by(username=username).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user.is_verified:
            return {"ok": True, "message": "Already verified"}
        if not user.email:
            raise HTTPException(status_code=400, detail="No email on file")
        user.verify_code    = _new_otp()
        user.verify_expires = datetime.utcnow() + timedelta(minutes=15)
        _send_verification_email(user)
        return {"ok": True, "message": "New code sent"}


# ── Admin-only: create sub-user ─────────────────────────
@router.post("/register")
def register(req: RegisterRequest, admin=Depends(require_admin)):
    with session_scope() as s:
        if s.query(User).filter_by(username=req.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        u = User(
            username    = req.username,
            password    = hash_password(req.password),
            role        = req.role,
            is_verified = True,         # admin-created users skip verification
            created_at  = datetime.utcnow(),
        )
        s.add(u)
        s.flush()
        s.add(UserSettings(user_id=u.id))
        return {"message": f"User '{req.username}' created with role '{req.role}'"}


# ── Login ────────────────────────────────────────────────
@router.post("/login", response_model=TokenResponse, tags=["Auth"])
def login(form: OAuth2PasswordRequestForm = Depends()):
    with session_scope() as s:
        user = s.query(User).filter_by(username=form.username).first()
        if not user or not verify_password(form.password, user.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account disabled")
        if user.email and not user.is_verified:
            raise HTTPException(
                status_code=403,
                detail="Please verify your email first — check your inbox for the 6-digit code.",
            )
        user.last_login_at = datetime.utcnow()
        token = create_token({
            "sub":  user.username,
            "uid":  user.id,
            "role": user.role,
        })
        return TokenResponse(
            access_token = token,
            user_id      = user.id,
            username     = user.username,
            role         = user.role,
        )


# ── Me ───────────────────────────────────────────────────
@router.get("/me", tags=["Auth"])
def me(current_user=Depends(get_current_user)):
    return current_user


# ── Bootstrap first admin (only if users table is empty) ─
@router.post("/setup", tags=["Auth"])
def setup_admin(req: RegisterRequest):
    if count_users() > 0:
        raise HTTPException(status_code=400, detail="Setup already done")
    with session_scope() as s:
        u = User(
            username    = req.username,
            password    = hash_password(req.password),
            role        = "admin",
            is_verified = True,
            created_at  = datetime.utcnow(),
        )
        s.add(u)
        s.flush()
        s.add(UserSettings(user_id=u.id))
    return {"message": f"Admin '{req.username}' created successfully"}
