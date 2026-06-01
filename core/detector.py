import cv2
import os
from datetime import datetime
from deepface import DeepFace
from ultralytics import YOLO
from config import (
    KNOWN_FACES_DIR, SNAPSHOTS_DIR,
    YOLO_MODEL, YOLO_CONFIDENCE
)
from database.models import insert_detection

class Detector:
    def __init__(self):
        self.yolo_model     = YOLO(YOLO_MODEL)
        self.known_faces    = self._load_known_faces()
        print(f"✅ Loaded {len(self.known_faces)} known faces: {list(self.known_faces.keys())}")

    def _load_known_faces(self):
        faces = {}
        for filename in os.listdir(KNOWN_FACES_DIR):
            if filename.lower().endswith((".jpg", ".jpeg", ".png")):
                name = os.path.splitext(filename)[0]
                path = os.path.join(KNOWN_FACES_DIR, filename)
                faces[name] = path
        return faces

    def reload_known_faces(self):
        self.known_faces = self._load_known_faces()
        print(f"🔄 Reloaded {len(self.known_faces)} known faces")

    def save_snapshot(self, frame, label):
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename  = f"{label}_{timestamp}.jpg"
        path      = os.path.join(SNAPSHOTS_DIR, filename)
        cv2.imwrite(path, frame)
        return path

    def _is_known_face(self, frame):
        temp_path = os.path.join(SNAPSHOTS_DIR, "_temp_check.jpg")
        cv2.imwrite(temp_path, frame)
        for name, known_path in self.known_faces.items():
            try:
                result = DeepFace.verify(
                    img1_path = temp_path,
                    img2_path = known_path,
                    enforce_detection = False
                )
                if result["verified"]:
                    return name
            except Exception:
                continue
        return None

    def detect(self, frame, camera_id):
        results = []

        # ── Face detection ───────────────────────────────
        try:
            faces = DeepFace.extract_faces(
                img_path          = frame,
                enforce_detection = False
            )
            for face in faces:
                region     = face["facial_area"]
                x, y, w, h = region["x"], region["y"], region["w"], region["h"]
                face_crop  = frame[y:y+h, x:x+w]

                name        = self._is_known_face(face_crop)
                is_intruder = name is None
                label       = name if name else "Unknown"
                color       = (0, 0, 255) if is_intruder else (0, 255, 0)

                cv2.rectangle(frame, (x, y), (x+w, y+h), color, 2)
                cv2.putText(frame, label, (x, y - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                if is_intruder:
                    snapshot_path = self.save_snapshot(frame, "intruder")
                    detection_id  = insert_detection(
                        camera_id     = camera_id,
                        type_         = "intruder",
                        label         = label,
                        snapshot_path = snapshot_path,
                        clip_path     = None
                    )
                    results.append({
                        "type"         : "intruder",
                        "label"        : label,
                        "detection_id" : detection_id,
                        "snapshot"     : snapshot_path
                    })
        except Exception as e:
            print(f"⚠️ Face detection error: {e}")

        # ── YOLO object detection ─────────────────────────
        # yolo_results = self.yolo_model(frame, conf=YOLO_CONFIDENCE, verbose=False)
        yolo_results = self.yolo_model(frame, conf=YOLO_CONFIDENCE, verbose=False)
        for result in yolo_results:
            for box in result.boxes:
                cls_name     = self.yolo_model.names[int(box.cls)]
                x1,y1,x2,y2 = map(int, box.xyxy[0])
                cv2.rectangle(frame, (x1,y1), (x2,y2), (255,165,0), 2)
                cv2.putText(frame, cls_name, (x1, y1-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,165,0), 2)

        return frame, results