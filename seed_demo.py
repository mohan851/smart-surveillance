"""Seed 5 test agents + sample events into the live Agent Eye API.

Creates a new user 'demo' / 'demo1234' and registers 5 cameras covering
each type. Then pushes a handful of test detection events so the dashboard
has data to display.
"""
import os
import sys
import time
import base64
import requests

BASE = "https://smart-surveillance-production.up.railway.app"
USERNAME = "demo"
PASSWORD = "demo1234"
EMAIL    = "demo@agent-eye.test"


def pp(label, r):
    short = r.text[:120].replace("\n", " ")
    print(f"  {label:32s} HTTP {r.status_code}  {short}")


def main():
    s = requests.Session()
    # 1) Try to login first
    print("=" * 60)
    print("STEP 1: Login as demo user (signup if missing)")
    print("=" * 60)
    r = s.post(f"{BASE}/auth/login",
               data={"username": USERNAME, "password": PASSWORD},
               headers={"Content-Type": "application/x-www-form-urlencoded"})
    if r.status_code == 200:
        print(f"  demo exists — logged in")
    else:
        # Need to signup — skip email so we auto-verify
        r = s.post(f"{BASE}/auth/signup", json={
            "username": USERNAME, "password": PASSWORD,
            "full_name": "Demo User", "company": "Agent Eye Demo",
        })
        pp("signup", r)
        if r.status_code != 200:
            print("Signup failed; aborting.")
            sys.exit(1)
        # Now login to get the token
        r = s.post(f"{BASE}/auth/login",
                   data={"username": USERNAME, "password": PASSWORD},
                   headers={"Content-Type": "application/x-www-form-urlencoded"})
    pp("login", r)
    token = r.json()["access_token"]
    H = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    # 2) List current agents
    print()
    print("=" * 60)
    print("STEP 2: Current agents (before)")
    print("=" * 60)
    r = s.get(f"{BASE}/me/agents", headers=H)
    pp("list", r)
    print(f"  count: {len(r.json())}")

    # 3) Register 5 cameras
    print()
    print("=" * 60)
    print("STEP 3: Register 5 cameras")
    print("=" * 60)
    cameras = [
        {"camera_name": "Front Door",      "camera_type": "webcam", "camera_source": "0"},
        {"camera_name": "Backyard",       "camera_type": "rtsp",   "camera_source": "rtsp://admin:admin123@192.168.1.100:554/stream1"},
        {"camera_name": "Garage",         "camera_type": "webcam", "camera_source": "1"},
        {"camera_name": "Office Entry",   "camera_type": "http",   "camera_source": "http://192.168.1.50/video.mjpg"},
        {"camera_name": "Test Video",     "camera_type": "file",   "camera_source": "C:/videos/test_cctv.mp4"},
    ]
    for c in cameras:
        body = dict(c)
        body["machine_id"]  = f"seed-{c['camera_name'].lower().replace(' ', '-')}"
        body["machine_name"] = c["camera_name"]
        r = s.post(f"{BASE}/agent/register", json=body, headers=H)
        pp(f"register '{c['camera_name']}'", r)

    # 4) Enable cloud upload in settings (so the sample events will save snapshots)
    print()
    print("=" * 60)
    print("STEP 4: Enable cloud uploads + add 5-min retention")
    print("=" * 60)
    r = s.put(f"{BASE}/me/settings", json={
        "upload_snapshots":      True,
        "cloud_retention_days":  5,
        "alert_on_unknown":      True,
        "detection_cooldown":    10,
    }, headers=H)
    pp("settings", r)

    # 5) Push some sample detection events
    print()
    print("=" * 60)
    print("STEP 5: Push sample detection events")
    print("=" * 60)
    # Make a tiny 1x1 black JPEG to stand in for a real snapshot
    TINY_JPEG = base64.b64decode(
        b"/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAYEBQYFBAYGBQYHBwYIChAKCgkJChQODwwQFxQYGBcU"
        b"FhYaHSUfGhsjHBYWICwgIyYnKSopGR8tMC0oMCUoKSj/2wBDAQcHBwoIChMKChMoGhYaKCgoKCgoKCgoKCgo"
        b"KCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCgoKCj/wAARCAABAAEDASIAAhEBAxEB/8QAFQAB"
        b"AQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIQAxAAAAFlf//EABQQAQAAAAAA"
        b"AH//2gAMAwEAAhEDEQA/AL+AB//Z"
    )
    b64 = base64.b64encode(TINY_JPEG).decode("ascii")

    sample_events = [
        ("Front Door",     "Unknown",        87),
        ("Front Door",     "Mohan",          92),
        ("Backyard",       "Unknown",        76),
        ("Garage",         "Unknown",        81),
        ("Office Entry",   "Priya",          89),
        ("Front Door",     "Unknown",        78),
        ("Backyard",       "Unknown",        84),
        ("Garage",         "Mohan",          95),
        ("Test Video",     "Unknown",        72),
        ("Front Door",     "Unknown",        88),
    ]
    for cam, label, conf in sample_events:
        r = s.post(f"{BASE}/me/browser-event", json={
            "label": label,
            "confidence": conf,
            "snapshot_b64": b64,
            "camera_source": f"{cam.lower().replace(' ', '_')}:seeded",
        }, headers=H)
        pp(f"event {cam}/{label}", r)
        time.sleep(0.2)

    # 6) Final summary
    print()
    print("=" * 60)
    print("STEP 6: Final state")
    print("=" * 60)
    r = s.get(f"{BASE}/me/agents", headers=H); pp("agents", r)
    print(f"  agent count: {len(r.json())}")
    r = s.get(f"{BASE}/me/stats", headers=H); pp("stats", r)
    print(f"  stats: {r.json()}")
    r = s.get(f"{BASE}/me/snapshots/dates", headers=H); pp("snapshot dates", r)
    print(f"  snapshot dates: {r.json()}")

    print()
    print("=" * 60)
    print(f"DONE — login as '{USERNAME}' / '{PASSWORD}' on the live URL")
    print("=" * 60)


if __name__ == "__main__":
    main()
