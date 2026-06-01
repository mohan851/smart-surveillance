from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from api.middleware import (
    hash_password, verify_password,
    create_token, get_current_user, require_admin
)
from database.db import get_connection

router = APIRouter()

# ── Schemas ──────────────────────────────────────────────
class RegisterRequest(BaseModel):
    username : str
    password : str
    role     : str = "viewer"

# ── Register ─────────────────────────────────────────────
@router.post("/register")
def register(req: RegisterRequest, admin=Depends(require_admin)):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (req.username, hash_password(req.password), req.role)
        )
        conn.commit()
        return {"message": f"User '{req.username}' created with role '{req.role}'"}
    except Exception:
        raise HTTPException(status_code=400, detail="Username already exists")
    finally:
        conn.close()

# ── Login ────────────────────────────────────────────────
@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends()):
    conn = get_connection()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?", (form.username,)
    ).fetchone()
    conn.close()

    if not user or not verify_password(form.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_token({"sub": user["username"], "role": user["role"]})
    return {"access_token": token, "token_type": "bearer"}

# ── Me ───────────────────────────────────────────────────
@router.get("/me")
def me(current_user=Depends(get_current_user)):
    return {
        "username" : current_user["username"],
        "role"     : current_user["role"],
        "created_at": current_user["created_at"]
    }

# ── Create first admin (only if no users exist) ──────────
@router.post("/setup")
def setup_admin(req: RegisterRequest):
    conn  = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count > 0:
        conn.close()
        raise HTTPException(status_code=400, detail="Setup already done")
    conn.execute(
        "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
        (req.username, hash_password(req.password), "admin")
    )
    conn.commit()
    conn.close()
    return {"message": f"Admin '{req.username}' created successfully"}