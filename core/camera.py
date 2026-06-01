import cv2
import threading
from config import CAMERA_IDS, FRAME_WIDTH, FRAME_HEIGHT, FPS

class CameraStream:
    def __init__(self, camera_id):
        self.camera_id = camera_id
        self.cap       = cv2.VideoCapture(camera_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH,  FRAME_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS,          FPS)
        self.frame  = None
        self.active = False
        self.lock   = threading.Lock()

    def start(self):
        self.active = True
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()
        print(f"✅ Camera {self.camera_id} started")

    def _read_loop(self):
        while self.active:
            ret, frame = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = frame

    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None

    def stop(self):
        self.active = False
        self.cap.release()
        print(f"🛑 Camera {self.camera_id} stopped")


class CameraManager:
    def __init__(self):
        self.cameras = {}

    def start_all(self):
        for cam_id in CAMERA_IDS:
            cam = CameraStream(cam_id)
            cam.start()
            self.cameras[cam_id] = cam

    def get_frame(self, camera_id):
        cam = self.cameras.get(camera_id)
        return cam.get_frame() if cam else None

    def stop_all(self):
        for cam in self.cameras.values():
            cam.stop()

    def stop_camera(self, camera_id):
        if camera_id in self.cameras:
            self.cameras[camera_id].stop()

    def start_camera(self, camera_id):
        if camera_id not in self.cameras:
            cam = CameraStream(camera_id)
            cam.start()
            self.cameras[camera_id] = cam