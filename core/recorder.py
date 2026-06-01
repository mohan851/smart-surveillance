import cv2
import os
import threading
from datetime import datetime
from config import RECORDINGS_DIR, FRAME_WIDTH, FRAME_HEIGHT, FPS

class Recorder:
    def __init__(self, camera_id):
        self.camera_id  = camera_id
        self.writer     = None
        self.recording  = False
        self.lock       = threading.Lock()
        self.current_path = None

    def start_recording(self):
        timestamp  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        cam_folder = os.path.join(RECORDINGS_DIR, f"cam{self.camera_id}")
        os.makedirs(cam_folder, exist_ok=True)

        filename   = f"{timestamp}.mp4"
        self.current_path = os.path.join(cam_folder, filename)

        fourcc     = cv2.VideoWriter_fourcc(*"mp4v")
        self.writer = cv2.VideoWriter(
            self.current_path, fourcc, FPS,
            (FRAME_WIDTH, FRAME_HEIGHT)
        )
        self.recording = True
        print(f"🎥 Recording started: {self.current_path}")

    def write_frame(self, frame):
        if self.recording and self.writer:
            with self.lock:
                self.writer.write(frame)

    def stop_recording(self):
        if self.writer:
            with self.lock:
                self.writer.release()
                self.writer = None
        self.recording = False
        print(f"🛑 Recording saved: {self.current_path}")
        return self.current_path

    def save_clip(self, frames, label="detection"):
        """Save a short clip when intruder is detected"""
        timestamp  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        cam_folder = os.path.join(RECORDINGS_DIR, f"cam{self.camera_id}")
        os.makedirs(cam_folder, exist_ok=True)

        clip_path  = os.path.join(cam_folder, f"{label}_{timestamp}.mp4")
        fourcc     = cv2.VideoWriter_fourcc(*"mp4v")
        writer     = cv2.VideoWriter(
            clip_path, fourcc, FPS,
            (FRAME_WIDTH, FRAME_HEIGHT)
        )
        for frame in frames:
            writer.write(frame)
        writer.release()
        print(f"📹 Clip saved: {clip_path}")
        return clip_path