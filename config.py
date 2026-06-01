import os

# ── Base paths ──────────────────────────────────────────
BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
RECORDINGS_DIR  = os.path.join(BASE_DIR, "recordings")
SNAPSHOTS_DIR   = os.path.join(BASE_DIR, "snapshots")
KNOWN_FACES_DIR = os.path.join(BASE_DIR, "known_faces")
DB_PATH         = os.path.join(BASE_DIR, "database", "surveillance.db")

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