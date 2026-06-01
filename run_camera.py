import cv2
import sys
import os
from datetime import datetime
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database.db import init_db
from database.models import insert_detection
from alerts.n8n_trigger import send_intruder_alert

init_db()

# ── Open camera ──────────────────────────────────────────
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

# ── Face detector ─────────────────────────────────────────
face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)

print("✅ Camera started — press Q to quit")

frame_count    = 0
face_cooldowns = {}  # tracks cooldown per face position

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_count += 1

    if frame_count % 15 == 0:
        gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5)

        # ── Process each face separately ─────────────────
        for i, (x, y, w, h) in enumerate(faces):
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
            cv2.putText(frame, f"Intruder {i+1}!", (x, y-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

            face_key = f"face_{i}"

            if face_cooldowns.get(face_key, 0) == 0:
                timestamp     = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                snapshot_path = os.path.join(
                    "snapshots", f"intruder_{i+1}_{timestamp}.jpg"
                )
                cv2.imwrite(snapshot_path, frame)

                detection_id = insert_detection(
                    camera_id     = 0,
                    type_         = "intruder",
                    label         = f"Unknown Person {i+1}",
                    snapshot_path = snapshot_path,
                    clip_path     = None
                )
                send_intruder_alert(
                    detection_id  = detection_id,
                    camera_id     = 0,
                    snapshot_path = snapshot_path,
                    label         = f"Unknown Person {i+1}"
                )
                print(f"🚨 Intruder {i+1} detected! Alert sent!")
                face_cooldowns[face_key] = 150

        # ── Decrease all cooldowns ────────────────────────
        for key in list(face_cooldowns.keys()):
            if face_cooldowns[key] > 0:
                face_cooldowns[key] -= 1

        # ── Show face count on screen ─────────────────────
        cv2.putText(frame, f"Faces detected: {len(faces)}", (10, 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

    cv2.imshow("Smart Surveillance", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("✅ Camera stopped!")