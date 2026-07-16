# Sentinel — AI CCTV Threat & Crowd Intelligence

A weapon-detection + suspect re-identification + crowd activity/heatmap
surveillance system, with a showcase website and a live web dashboard.

This package wraps your **existing, working** detection code — nothing in
`backend/` or `web_backend/model.py` was rewritten. A new FastAPI layer
(`web_backend/server.py`) runs those pipelines as background workers and
exposes them to the browser.

## What's in here

```
project/
├── backend/                  ← your original weapon + Re-ID pipeline (unchanged)
│   ├── surveillance/camera_pipeline.py
│   ├── reid/reid_utils.py + suspect_database.json
│   ├── logging/evidence_logger.py
│   ├── camera_manager/
│   └── utils/config.py, constants.py
├── web_backend/
│   ├── server.py             ← NEW: FastAPI app, the only new backend code
│   ├── model.py               ← your activity + crowd heatmap models (unchanged)
│   └── camera.py
├── web_frontend/
│   ├── index.html             ← showcase / landing page
│   ├── dashboard.html         ← live functional dashboard
│   ├── app.js
│   └── style.css
├── models/                    ← put your .pt weight files here (see below)
├── outputs/                   ← live frames, suspect snapshots, evidence log, heatmaps
├── uploads/                   ← videos uploaded from the dashboard land here
└── requirements.txt
```

## 1. Install dependencies

```bash
python -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## 2. Add the model weight files

`models/rik_best_best.pt` (your trained weapon detector) is already included.
You still need to add these two standard Ultralytics models to `models/`:

- `yolo11s-pose.pt`
- `yolo11n.pt`

Easiest way — let Ultralytics download them once, then copy them in:

```bash
python -c "from ultralytics import YOLO; YOLO('yolo11s-pose.pt'); YOLO('yolo11n.pt')"
# then copy the downloaded files into the models/ folder
```

For the activity/heatmap pipeline (`web_backend/model.py`), the same
`yolo11s-pose.pt` is loaded by name and a `yolo11n.pt` is used for crowd
detection — Ultralytics will auto-download these the first time
`web_backend/model.py` runs, as long as your machine has internet access.

## 3. Run

**Always run this from the project root** (the folder this README is in) —
several existing modules use paths that are relative to the working
directory, and they're written to match.

```bash
uvicorn web_backend.server:app --reload --host 0.0.0.0 --port 8000
```

Then open:

- `http://localhost:8000/` — the showcase landing page
- `http://localhost:8000/dashboard.html` — the live dashboard

## 4. Using the dashboard

From the dashboard sidebar you can add:

- **Webcam** — enter the device index (usually `0`)
- **CCTV / RTSP** — paste the stream URL, e.g. `rtsp://192.168.1.10:554/stream1`
- **Uploaded video** — pick a recorded `.mp4`/`.avi` file from your computer

Both the weapon-detection pipeline and the activity/heatmap pipeline accept
any of these three source types, and you can run several sources of each at
once. Recorded video files loop automatically.

Suspects, evidence log entries, and stats update from your real
`backend/reid/suspect_database.json` and `outputs/logs/evidence_log.json` as
the pipeline runs. Both start empty in this package — they'll fill in as
soon as a weapon is detected on a running camera.

## 5. Before you submit

The landing page (`web_frontend/index.html`) has a few placeholders in the
footer marked in amber — `[Your Name]`, `[Your College / Department]`,
`[Guide / Supervisor Name]`, `[GitHub repo link]` — fill those in with your
own details before presenting.

The weapon-detector metrics shown on the landing page (mAP50 83.4%,
Precision 84.5%, 8,807 annotations, pistol/knife classes) were pulled
directly from your `model_train.ipynb` validation run — update them if you
retrain.
