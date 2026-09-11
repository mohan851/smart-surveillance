"""
Authentication routes for Agent Eye.
- POST /auth/signup   public, no admin required (multi-tenant onboarding)
- POST /auth/login    username + password → JWT
- POST /auth/setup    first-admin bootstrap (only if users table is empty)
- GET  /auth/me       current user info
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.exc import IntegrityError
from datetime import datetime

from api.middleware import (
    hash_password, verify_password,
    create_token, get_current_user, require_admin
)
from database.db import session_scope, count_users
from database.models import User, UserSettings

router = APIRouter()


# ── Schemas ──────────────────────────────────────────────
class SignupRequest(BaseModel):
    username  : str            = Field(..., min_length=3, max_length=80)
    password  : str            = Field(..., min_length=6, max_length=128)
    email     : EmailStr | None = None
    full_name : str | None     = None
    company   : str | None     = None


class RegisterRequest(BaseModel):
    username : str
    password : str
    role     : str = "customer"


class TokenResponse(BaseModel):
    access_token : str
    token_type   : str = "bearer"
    user_id      : int
    username     : str
    role         : str


# ── Public signup (multi-tenant onboarding) ──────────────
@router.post("/signup", response_model=TokenResponse, tags=["Auth"])
def signup(req: SignupRequest):
    """A new customer signs themselves up. Returns a JWT to log in immediately."""
    with session_scope() as s:
        # username uniqueness
        if s.query(User).filter_by(username=req.username).first():
            raise HTTPException(status_code=400, detail="Username already taken")
        if req.email and s.query(User).filter_by(email=req.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")

        # First-ever signup becomes admin automatically (bootstrap)
        is_first = s.query(User).count() == 0
        role     = "admin" if is_first else "customer"

        user = User(
            username  = req.username,
            email     = req.email,
            password  = hash_password(req.password),
            role      = role,
            full_name = req.full_name,
            company   = req.company,
            created_at= datetime.utcnow(),
            is_active = True,
        )
        s.add(user)
        s.flush()  # get user.id

        # Auto-create empty settings row so /me/settings works immediately
        s.add(UserSettings(user_id=user.id))

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


# ── Admin-only: create sub-user ─────────────────────────
@router.post("/register")
def register(req: RegisterRequest, admin=Depends(require_admin)):
    with session_scope() as s:
        if s.query(User).filter_by(username=req.username).first():
            raise HTTPException(status_code=400, detail="Username already exists")
        u = User(
            username   = req.username,
            password   = hash_password(req.password),
            role       = req.role,
            created_at = datetime.utcnow(),
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
            username   = req.username,
            password   = hash_password(req.password),
            role       = "admin",
            created_at = datetime.utcnow(),
        )
        s.add(u)
        s.flush()
        s.add(UserSettings(user_id=u.id))
    return {"message": f"Admin '{req.username}' created successfully"}
