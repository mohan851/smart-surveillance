import cv2
import numpy as np

class MotionZone:
    def __init__(self, camera_id, zones=None):
        self.camera_id        = camera_id
        self.zones            = zones or []
        self.bg_subtractor    = cv2.createBackgroundSubtractorMOG2(
                                    history=500,
                                    varThreshold=50,
                                    detectShadows=True
                                )

    def set_zones(self, zones):
        """
        zones = list of polygons
        each zone = list of (x, y) points
        example: [[(100,100), (400,100), (400,300), (100,300)]]
        """
        self.zones = zones
        print(f"✅ Camera {self.camera_id} — {len(zones)} motion zone(s) set")

    def _point_in_zone(self, point, zone):
        zone_array = np.array(zone, dtype=np.int32)
        result     = cv2.pointPolygonTest(zone_array, point, False)
        return result >= 0

    def _motion_in_zones(self, motion_mask):
        if not self.zones:
            return True   # no zones defined = watch whole frame

        contours, _ = cv2.findContours(
            motion_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        for contour in contours:
            if cv2.contourArea(contour) < 500:
                continue
            M  = cv2.moments(contour)
            if M["m00"] == 0:
                continue
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            for zone in self.zones:
                if self._point_in_zone((cx, cy), zone):
                    return True
        return False

    def detect_motion(self, frame):
        motion_mask    = self.bg_subtractor.apply(frame)
        _, motion_mask = cv2.threshold(motion_mask, 200, 255, cv2.THRESH_BINARY)
        motion_mask    = cv2.dilate(motion_mask, None, iterations=2)
        motion_detected = self._motion_in_zones(motion_mask)
        return motion_detected, motion_mask

    def draw_zones(self, frame):
        for zone in self.zones:
            pts = np.array(zone, dtype=np.int32)
            cv2.polylines(frame, [pts], isClosed=True,
                          color=(0, 255, 255), thickness=2)
        return frame