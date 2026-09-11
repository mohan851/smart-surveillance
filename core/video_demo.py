"""
Video Demo Processor — lightweight YOLO-only pipeline for cloud deployment.

Unlike the live `Detector` class, this skips DeepFace (face recognition) so it
runs on Render's free tier without 100MB+ model downloads or large memory.
Good enough for a portfolio-piece demo: upload a video, get back annotated
footage with object detection bounding boxes.
"""

import cv2
import os
import tempfile
from collections import Counter
from ultralytics import YOLO

from config import YOLO_MODEL, YOLO_CONFIDENCE


class VideoDemoProcessor:
    def __init__(self):
        # YOLO model file is bundled in the repo (yolov8n.pt)
        self.model = YOLO(YOLO_MODEL)
        print(f"[demo] Loaded {YOLO_MODEL}")

    def process_video(
        self,
        input_path: str,
        output_path: str,
        max_frames: int = 300,
        sample_every: int = 1,
    ) -> dict:
        """
        Run YOLO over an uploaded video. Writes annotated MP4 to output_path.
        Returns a summary dict (frames, resolution, detection tallies, top objects).
        """
        cap = cv2.VideoCapture(input_path)
        if not cap.isOpened():
            raise ValueError(f"Could not open video: {input_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # mp4v is broadly supported
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))
        if not writer.isOpened():
            cap.release()
            raise RuntimeError("Could not open VideoWriter — codec issue")

        frame_idx = 0
        processed = 0
        tally: Counter = Counter()
        annotated_frames = []  # base64 jpgs for quick preview thumbnails

        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                # Optionally skip frames to speed up long videos
                if frame_idx % sample_every != 0:
                    frame_idx += 1
                    continue

                results = self.model(frame, conf=YOLO_CONFIDENCE, verbose=False)
                annotated = results[0].plot()  # YOLO built-in annotator

                # Tally class counts
                for box in results[0].boxes:
                    cls_name = self.model.names[int(box.cls)]
                    tally[cls_name] += 1

                # Overlay frame counter
                cv2.putText(
                    annotated,
                    f"Frame {frame_idx} | AgentEye Demo",
                    (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                )

                writer.write(annotated)
                processed += 1
                frame_idx += 1

                if processed >= max_frames:
                    break
        finally:
            cap.release()
            writer.release()

        return {
            "frames_processed": processed,
            "frames_sampled": frame_idx,
            "fps": round(fps, 2),
            "resolution": f"{width}x{height}",
            "duration_seconds": round(frame_idx / fps, 2) if fps else None,
            "detections": dict(tally.most_common()),
            "top_objects": tally.most_common(5),
            "unique_classes": len(tally),
        }


def make_temp_paths(uid: str, original_filename: str) -> tuple[str, str]:
    """Return (input_tmp, output_tmp) absolute paths scoped to /tmp."""
    tmp = tempfile.gettempdir()
    safe_name = os.path.basename(original_filename).replace(" ", "_")
    input_path = os.path.join(tmp, f"in_{uid}_{safe_name}")
    output_path = os.path.join(tmp, f"out_{uid}.mp4")
    return input_path, output_path