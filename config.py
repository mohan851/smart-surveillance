import os

# ── Database ────────────────────────────────────────────
# Supabase PostgreSQL (persistent cloud DB — survives Railway restarts).
# Set DATABASE_URL env var on Railway to override the hard-coded URL below.
# Using the Supabase Connection Pooler (port 6543) — more reliable than
# direct :5432 because it survives idle disconnects and is reachable
# from restrictive networks. Password URL-encoded for special chars.
SUPABASE_DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.hbaovhrochduxafdedzc:Mohan%24123%21%40%23@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres"
)
# Direct fallback (port 5432). Use this if you ever switch to a long-lived
# server pool. Not used by default because Railway can idle out :5432.
SUPABASE_DIRECT_URL = os.getenv(
    "DATABASE_DIRECT_URL",
    "postgresql://postgres:Mohan%24123%21%40%23@db.hbaovhrochduxafdedzc.supabase.co:5432/postgres"
)
# Use SQLite for local dev (no Supabase needed) OR when env flag is set
USE_SQLITE      = os.getenv("USE_SQLITE", "").lower() in ("1", "true", "yes")

# ── Base paths ──────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
# Cloud servers have ephemeral filesystem — keep runtime artifacts in /tmp.
_USE_TMP = os.getenv("USE_TMP_STORAGE", "").lower() in ("1", "true", "yes") or os.path.exists("/opt/render")
_STORAGE_ROOT = "/tmp" if _USE_TMP else BASE_DIR

RECORDINGS_DIR  = os.path.join(_STORAGE_ROOT, "recordings")
SNAPSHOTS_DIR   = os.path.join(_STORAGE_ROOT, "snapshots")
KNOWN_FACES_DIR = os.path.join(_STORAGE_ROOT, "known_faces")
SQLITE_PATH     = os.path.join(_STORAGE_ROOT, "database", "surveillance.db")

# ── Camera settings ──────────────────────────────────────
CAMERA_IDS = [0]          # 0 = default webcam, add 1,2.. for more cameras
FRAME_WIDTH  = 640
FRAME_HEIGHT = 480
FPS          = 20

# ── Detection settings ───────────────────────────────────
FACE_RECOGNITION_TOLERANCE = 0.5   # lower = stricter match
YOLO_MODEL                 = "yolov8n.pt"
YOLO_CONFIDENCE            = 0.5
MOTION_SENSITIVITY         = 500   # minimum pixel area to trigger motion

# ── Recording settings ───────────────────────────────────
RECORDING_SEGMENT_MINUTES = 30     # split recordings every 30 mins
SAVE_CLIP_ON_DETECTION    = True   # save short clip when intruder detected

# ── n8n alert settings ───────────────────────────────────
N8N_WEBHOOK_URL = "http://localhost:5678/webhook-test/intruder-alert"
# http://localhost:5678/webhook/intruder-alert

# ── API / Auth settings ──────────────────────────────────
SECRET_KEY        = "change-this-to-a-random-secret"
ALGORITHM         = "HS256"
TOKEN_EXPIRE_MINS = 60

# ── Auto-create directories ──────────────────────────────
for _dir in [RECORDINGS_DIR, SNAPSHOTS_DIR, KNOWN_FACES_DIR]:
    os.makedirs(_dir, exist_ok=True)