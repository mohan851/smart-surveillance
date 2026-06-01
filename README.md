# 🎯 AgentEye — Smart Surveillance System

A real-time AI-powered surveillance system built with YOLOv8, DeepFace, FastAPI, and n8n. Detects intruders, recognizes faces, records footage, sends instant alerts via Telegram, and provides a full admin dashboard.

---

## 🚀 Features

- 🔍 **Intruder Detection** — YOLOv8-based object detection with configurable confidence threshold
- 👤 **Face Recognition** — DeepFace-powered recognition against a known faces database
- 📷 **Multi-Camera Support** — Manage multiple camera feeds simultaneously
- 🎥 **Auto Recording** — Segments recordings every 30 minutes; saves clips on detection
- 📸 **Snapshot Capture** — Auto-saves snapshots when an intruder is detected
- 🚨 **Instant Alerts** — n8n webhook triggers Telegram alerts with snapshot attachment
- 📊 **Admin Dashboard** — View detections, manage cameras, download PDF reports
- 🔐 **JWT Auth** — Secure API with login, token-based access, and middleware protection
- 🗃️ **SQLite Database** — Lightweight local DB for storing detection logs

---

## 🗂️ Project Structure

```
smart-surveillance/
├── api/                  # FastAPI app
│   ├── main.py           # App entry point
│   ├── middleware.py     # Auth middleware
│   └── routes/           # auth, cameras, detections, reports
├── core/                 # Core logic
│   ├── camera.py         # Camera feed handler
│   ├── detector.py       # YOLOv8 + face detection
│   ├── recorder.py       # Video recording
│   └── motion_zones.py   # Motion zone logic
├── alerts/               # n8n webhook trigger
├── database/             # SQLite DB init & models
├── dashboard/            # Frontend dashboard
├── known_faces/          # Reference images for face recognition
├── recordings/           # Saved video clips
├── snapshots/            # Captured intruder snapshots
├── n8n/                  # n8n workflow configs
├── config.py             # All project settings
├── run_camera.py         # Standalone camera runner (no API)
├── requirements.txt      # Python dependencies
└── yolov8n.pt            # YOLOv8 nano model weights
```

---

## ⚙️ Setup & Installation

### 1. Clone the repo
```bash
git clone https://github.com/your-username/smart-surveillance.git
cd smart-surveillance
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure settings
Edit `config.py` to set your camera IDs, n8n webhook URL, detection thresholds, and secret key.

### 4. Run the FastAPI server
```bash
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Access the API
```
http://127.0.0.1:8000
http://127.0.0.1:8000/docs   ← Swagger UI
```

### 6. (Optional) Run standalone camera
```bash
python run_camera.py
```
Press `Q` to quit.

---

## 🔔 Alerts (n8n + Telegram)

1. Start n8n locally: `npx n8n`
2. Import the workflow from the `n8n/` folder
3. Set your Telegram bot token and chat ID in the workflow
4. Make sure the webhook URL in `config.py` matches your n8n webhook

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Detection | YOLOv8 (Ultralytics) |
| Face Recognition | DeepFace |
| Backend | FastAPI + Uvicorn |
| Database | SQLite |
| Alerts | n8n + Telegram |
| Auth | JWT (python-jose + passlib) |
| Video | OpenCV |
| Reports | ReportLab (PDF) |

---

## 👤 Author

Built by **Parth** — B.Tech CSE Final Year, BVRIT Narsapur