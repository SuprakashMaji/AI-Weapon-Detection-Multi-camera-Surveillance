"""
web_backend/server.py
----------------------
FastAPI server that powers the Sentinel web dashboard.

It does NOT reimplement any computer-vision logic. It simply wraps the
existing, working pipelines:

  - backend/surveillance/camera_pipeline.py   -> weapon detection + Re-ID
  - web_backend/model.py (ActivityModel, CrowdGroupModel) -> activity + heatmap

...as background threads, and exposes their outputs (live frames, suspect
database, evidence log, activity counts) over HTTP so a browser-based
dashboard can show them. Each "source" can be a webcam index (0, 1, ...),
an RTSP/HTTP CCTV stream URL, or an uploaded video file.

Run with:
    uvicorn web_backend.server:app --reload --port 8000
"""

import json
import os
import shutil
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path

import cv2
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.surveillance.camera_pipeline import process_camera  # noqa: E402
from backend.reid.reid_utils import clear_database  # noqa: E402
from backend.utils.config import (  # noqa: E402
    LIVE_FOLDER,
    SUSPECT_FOLDER,
    LOG_PATH,
    DATABASE_PATH,
    POSE_MODEL_PATH,
    PERSON_MODEL_PATH,
    WEAPON_ACTIVITY_STATUS_FOLDER,
)

from web_backend.model import ActivityModel, CrowdGroupModel  # noqa: E402

# --------------------------------------------------------------------------
# App + folders
# --------------------------------------------------------------------------

app = FastAPI(title="Sentinel Surveillance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = PROJECT_ROOT / "uploads"
ACTIVITY_FOLDER = PROJECT_ROOT / "outputs" / "activity"
HEATMAP_FOLDER = PROJECT_ROOT / "outputs" / "heatmap"
ACTIVITY_STATUS_FOLDER = PROJECT_ROOT / "outputs" / "activity_status"

for folder in (UPLOAD_FOLDER, ACTIVITY_FOLDER, HEATMAP_FOLDER, ACTIVITY_STATUS_FOLDER):
    folder.mkdir(parents=True, exist_ok=True)

# In-memory registry of running background workers
weapon_sources: dict[str, dict] = {}
activity_sources: dict[str, dict] = {}

LOCK = threading.Lock()


def resolve_source(raw_source: str):
    """A source can be a webcam index ('0'), an RTSP/HTTP URL, or a file path."""
    if raw_source.isdigit():
        return int(raw_source)
    return raw_source


# --------------------------------------------------------------------------
# Video upload (used by both pipelines)
# --------------------------------------------------------------------------

@app.post("/api/upload-video")
async def upload_video(file: UploadFile = File(...)):
    ext = os.path.splitext(file.filename)[-1] or ".mp4"
    dest_name = f"{uuid.uuid4().hex}{ext}"
    dest_path = UPLOAD_FOLDER / dest_name

    with open(dest_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    return {"path": str(dest_path)}


# --------------------------------------------------------------------------
# WEAPON DETECTION + RE-ID  (reuses backend.surveillance.camera_pipeline)
# --------------------------------------------------------------------------

@app.post("/api/weapon-cameras/start")
def start_weapon_camera(name: str = Form(...), source: str = Form(...)):
    with LOCK:
        if name in weapon_sources:
            raise HTTPException(400, f"Camera '{name}' is already running")

        stop_event = threading.Event()
        target_source = resolve_source(source)

        thread = threading.Thread(
            target=process_camera,
            args=(target_source, name, stop_event),
            daemon=True,
        )
        weapon_sources[name] = {
            "thread": thread,
            "stop_event": stop_event,
            "source": source,
            "started_at": time.time(),
        }
        thread.start()

    return {"status": "started", "name": name}


@app.post("/api/weapon-cameras/stop")
def stop_weapon_camera(name: str = Form(...)):
    with LOCK:
        entry = weapon_sources.pop(name, None)

    if entry is None:
        raise HTTPException(404, f"Camera '{name}' is not running")

    entry["stop_event"].set()
    return {"status": "stopped", "name": name}


@app.get("/api/weapon-cameras")
def list_weapon_cameras():
    return [
        {"name": name, "source": data["source"], "started_at": data["started_at"]}
        for name, data in weapon_sources.items()
    ]


@app.get("/api/frame/{name}")
def get_weapon_frame(name: str):
    path = Path(LIVE_FOLDER) / f"{name}.jpg"
    if not path.exists():
        raise HTTPException(404, "No frame yet for this camera")
    return FileResponse(path, headers={"Cache-Control": "no-store"})


@app.get("/api/suspects")
def get_suspects():
    path = Path(DATABASE_PATH)
    if not path.exists():
        return {}

    try:
        with open(path, "r") as f:
            db = json.load(f)
    except Exception:
        return {}

    # Strip the (large) embedding vectors before sending to the browser
    cleaned = {}
    for suspect_id, data in db.items():
        cleaned[suspect_id] = {
            "weapon": data.get("weapon", "unknown"),
            "snapshot": data.get("snapshot", ""),
        }
    return cleaned


@app.get("/api/suspect-snapshot/{suspect_id}")
def get_suspect_snapshot(suspect_id: str):
    path = Path(DATABASE_PATH)
    if not path.exists():
        raise HTTPException(404)

    with open(path, "r") as f:
        db = json.load(f)

    data = db.get(suspect_id)
    if not data:
        raise HTTPException(404)

    snapshot_path = Path(data.get("snapshot", ""))
    if not snapshot_path.is_absolute():
        snapshot_path = PROJECT_ROOT / snapshot_path

    if not snapshot_path.exists():
        raise HTTPException(404, "Snapshot file missing")

    return FileResponse(snapshot_path)


@app.get("/api/weapon-activity-counts/{name}")
def get_weapon_activity_counts(name: str):
    """Sitting/Standing/Walking/Running counts captured *inside* the
    weapon-detection pipeline for camera `name` (see camera_pipeline.py).
    Distinct from /api/activity-counts/{name}, which belongs to the
    separate Activity & Heatmap dashboard."""
    path = Path(WEAPON_ACTIVITY_STATUS_FOLDER) / f"{name}.json"
    empty = {"counts": {"Sitting": 0, "Standing": 0, "Walking": 0, "Running": 0}}
    if not path.exists():
        return empty
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return empty


@app.get("/api/logs")
def get_logs():
    path = Path(LOG_PATH)
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return []


@app.get("/api/stats")
def get_stats():
    suspects = get_suspects()
    logs = get_logs()

    pistols = sum(1 for s in suspects.values() if s.get("weapon", "").lower() == "pistol")
    knives = sum(1 for s in suspects.values() if s.get("weapon", "").lower() == "knife")
    reid_matches = sum(1 for log in logs if log.get("event") == "REIDENTIFIED")

    scores = [
        log.get("similarity", 0) * 100
        for log in logs
        if log.get("event") == "REIDENTIFIED"
    ]
    avg_confidence = sum(scores) / len(scores) if scores else 0

    return {
        "total_suspects": len(suspects),
        "reid_matches": reid_matches,
        "evidence_logs": len(logs),
        "pistol_cases": pistols,
        "knife_cases": knives,
        "avg_confidence": round(avg_confidence, 2),
    }


# --------------------------------------------------------------------------
# ACTIVITY + CROWD HEATMAP  (reuses web_backend/model.py from final_model.zip)
# --------------------------------------------------------------------------

def activity_worker(source, name: str, stop_event: threading.Event):
    status_path = ACTIVITY_STATUS_FOLDER / f"{name}.json"

    # Let the dashboard know we've at least started trying, instead of
    # leaving it polling a file that doesn't exist yet for an unknown reason.
    with open(status_path, "w") as f:
        json.dump({"status": "starting"}, f)

    cap = cv2.VideoCapture(source)

    if not cap.isOpened():
        print(f"[activity_worker:{name}] ERROR: could not open source: {source}")
        with open(status_path, "w") as f:
            json.dump({"error": "Could not open source"}, f)
        return

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)

    try:
        activity_model = ActivityModel(model_name=POSE_MODEL_PATH, fps=fps)
        crowd_model = CrowdGroupModel(
            width=w, height=h, fps=fps, model_path=PERSON_MODEL_PATH
        )
    except Exception:
        print(f"[activity_worker:{name}] ERROR while loading models:")
        traceback.print_exc()
        with open(status_path, "w") as f:
            json.dump({"error": "Failed to load activity/heatmap models"}, f)
        cap.release()
        return

    activity_frame_path = ACTIVITY_FOLDER / f"{name}.jpg"
    heatmap_frame_path = HEATMAP_FOLDER / f"{name}.jpg"

    frame_count = 0
    is_file_source = isinstance(source, str) and os.path.exists(source)

    while not stop_event.is_set():
        ok, frame = cap.read()
        if not ok:
            if is_file_source:
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue
            print(f"[activity_worker:{name}] source stopped returning frames, stopping worker.")
            with open(status_path, "w") as f:
                json.dump({"error": "Source stopped returning frames"}, f)
            break

        frame_count += 1

        try:
            act_frame, counts = activity_model.process_frame(frame.copy())
            crowd_frame = crowd_model.process_frame(frame.copy())

            cv2.imwrite(str(activity_frame_path), act_frame)
            cv2.imwrite(str(heatmap_frame_path), crowd_frame)

            with open(status_path, "w") as f:
                json.dump({"counts": counts, "frame": frame_count}, f)
        except Exception:
            # Previously: an exception here killed the thread with no
            # output anywhere, so the dashboard just showed a permanently
            # broken image with no explanation. Now we log it and surface
            # it to the dashboard, then stop cleanly.
            print(f"[activity_worker:{name}] ERROR while processing frame {frame_count}:")
            traceback.print_exc()
            with open(status_path, "w") as f:
                json.dump({"error": f"Processing error on frame {frame_count} (see server console)"}, f)
            break

    cap.release()


@app.post("/api/activity/start")
def start_activity_source(name: str = Form(...), source: str = Form(...)):
    with LOCK:
        if name in activity_sources:
            raise HTTPException(400, f"Source '{name}' is already running")

        stop_event = threading.Event()
        target_source = resolve_source(source)

        thread = threading.Thread(
            target=activity_worker,
            args=(target_source, name, stop_event),
            daemon=True,
        )
        activity_sources[name] = {
            "thread": thread,
            "stop_event": stop_event,
            "source": source,
            "started_at": time.time(),
        }
        thread.start()

    return {"status": "started", "name": name}


@app.post("/api/activity/stop")
def stop_activity_source(name: str = Form(...)):
    with LOCK:
        entry = activity_sources.pop(name, None)

    if entry is None:
        raise HTTPException(404, f"Source '{name}' is not running")

    entry["stop_event"].set()
    return {"status": "stopped", "name": name}


@app.get("/api/activity")
def list_activity_sources():
    return [
        {"name": name, "source": data["source"], "started_at": data["started_at"]}
        for name, data in activity_sources.items()
    ]


@app.get("/api/activity-frame/{name}")
def get_activity_frame(name: str):
    path = ACTIVITY_FOLDER / f"{name}.jpg"
    if not path.exists():
        raise HTTPException(404, "No frame yet")
    return FileResponse(path, headers={"Cache-Control": "no-store"})


@app.get("/api/heatmap-frame/{name}")
def get_heatmap_frame(name: str):
    path = HEATMAP_FOLDER / f"{name}.jpg"
    if not path.exists():
        raise HTTPException(404, "No frame yet")
    return FileResponse(path, headers={"Cache-Control": "no-store"})


@app.get("/api/activity-counts/{name}")
def get_activity_counts(name: str):
    path = ACTIVITY_STATUS_FOLDER / f"{name}.json"
    if not path.exists():
        return {"counts": {"Sitting": 0, "Standing": 0, "Walking": 0, "Running": 0}}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {"counts": {"Sitting": 0, "Standing": 0, "Walking": 0, "Running": 0}}


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/reset-evidence")
def reset_evidence():
    """
    Manually wipe all suspects, evidence logs, and saved suspect
    snapshots. This does NOT happen automatically when a camera is
    stopped — evidence is meant to persist after a camera goes
    offline. Use this only between test runs / demos.
    """
    with LOCK:
        if weapon_sources or activity_sources:
            raise HTTPException(
                400,
                "Stop all running cameras/sources before clearing evidence."
            )

    clear_database()

    with open(LOG_PATH, "w") as f:
        json.dump([], f, indent=4)

    removed = 0
    suspect_dir = Path(SUSPECT_FOLDER)
    if suspect_dir.exists():
        for img in suspect_dir.glob("*.jpg"):
            try:
                img.unlink()
                removed += 1
            except OSError:
                pass

    return {"status": "cleared", "snapshots_removed": removed}


# --------------------------------------------------------------------------
# Static frontend (showcase site + dashboard)
# --------------------------------------------------------------------------

FRONTEND_DIR = PROJECT_ROOT / "web_frontend"
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")