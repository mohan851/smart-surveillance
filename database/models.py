from database.db import get_connection

# ── Detections ───────────────────────────────────────────
def insert_detection(camera_id, type_, label, snapshot_path, clip_path):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO detections (camera_id, type, label, snapshot_path, clip_path)
        VALUES (?, ?, ?, ?, ?)
    """, (camera_id, type_, label, snapshot_path, clip_path))
    conn.commit()
    detection_id = cursor.lastrowid
    conn.close()
    return detection_id

def get_all_detections(limit=100):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM detections ORDER BY timestamp DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

# ── Alerts ───────────────────────────────────────────────
def insert_alert(detection_id, channel, status):
    conn = get_connection()
    conn.execute("""
        INSERT INTO alerts (detection_id, channel, status)
        VALUES (?, ?, ?)
    """, (detection_id, channel, status))
    conn.commit()
    conn.close()

# ── Known faces ──────────────────────────────────────────
def insert_known_face(name, image_path):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO known_faces (name, image_path)
        VALUES (?, ?)
    """, (name, image_path))
    conn.commit()
    conn.close()

def get_all_known_faces():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM known_faces").fetchall()
    conn.close()
    return [dict(r) for r in rows]