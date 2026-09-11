"""
JWT auth + role-based access for Agent Eye.
Uses SQLAlchemy session under the hood; works on both Postgres and SQLite.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import Optional

from config import SECRET_KEY, ALGORITHM, TOKEN_EXPIRE_MINS
from database.db import session_scope
from database.models import User

# ── Password hashing ─────────────────────────────────────
pwd_context   = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> str:
    if not pwd_context.verify(plain, hashed):
        return False
    return True


# ── JWT tokens ───────────────────────────────────────────
def create_token(data: dict, expires_minutes: Optional[int] = None) -> str:
    payload = data.copy()
    expire  = datetime.utcnow() + timedelta(
        minutes=expires_minutes or TOKEN_EXPIRE_MINS
    )
    payload.update({"exp": expire})
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


# ── Get current user (always filter by id from JWT) ───────
def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    payload  = decode_token(token)
    user_id  = payload.get("uid")
    username = payload.get("sub")

    if not user_id and not username:
        raise HTTPException(status_code=401, detail="Invalid token")

    with session_scope() as s:
        if user_id:
            user = s.query(User).filter_by(id=int(user_id)).first()
        else:
            user = s.query(User).filter_by(username=username).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        # Detach so caller can read attributes after session closes
        s.expunge(user)
        return {
            "id":         user.id,
            "username":   user.username,
            "email":      user.email,
            "role":       user.role,
            "full_name":  user.full_name,
            "company":    user.company,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        }


# ── Role check ───────────────────────────────────────────
def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
