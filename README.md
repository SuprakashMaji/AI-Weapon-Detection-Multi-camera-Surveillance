<div align="center">

# 🛡️ SentinelVision

### AI-Powered Real-Time Multi-Camera Surveillance System
**Weapon Detection · Suspect Attribution · Cross-Camera Re-Identification**

Turn passive CCTV feeds into an intelligent security layer — detect weapons the instant they appear, pin them to the person holding them, and follow that suspect across every camera in your network.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![YOLO11](https://img.shields.io/badge/YOLO11-Ultralytics-00FFFF?style=for-the-badge&logo=yolo&logoColor=black)
![PyTorch](https://img.shields.io/badge/PyTorch-TorchReid-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

</div>

---

## ⚡ Why This Exists

CCTV cameras **record** — they don't **understand**. A guard watching a dozen screens will miss a knife or pistol in a crowd; footage usually only gets reviewed *after* something has already gone wrong.

SentinelVision closes that gap: it watches every feed continuously, flags a weapon the moment it appears, identifies exactly who is holding it, and keeps tracking that person even after they walk out of frame and into a different camera's view — no human ever has to be staring at the right screen at the right second.

---

## ✨ Key Features

| | |
|---|---|
| 🔫 **Real-Time Weapon Detection** | Custom YOLO11s model spots pistols and knives frame-by-frame |
| 🖐️ **Weapon–Person Attribution** | Pose-based wrist tracking pins the weapon to the exact suspect, not just "someone in frame" |
| 🎯 **Cross-Camera Re-ID** | OSNet appearance embeddings re-recognize a suspect the second they appear on any other camera |
| 🚨 **Instant Alerts** | Audible siren on weapon detection, soft tone on Re-ID match |
| 📊 **Live Dashboard** | Multi-feed grid view, suspect gallery, and a searchable evidence timeline |
| 🧍 **Activity & Crowd Analytics** | Pose-driven activity classification, group clustering, and live traffic heatmaps |
| 🗂️ **Automatic Evidence Trail** | Every event logged with timestamp, camera, weapon type, and match confidence |

---

## 🧠 How It Works

```
┌──────────────┐     ┌─────────────────┐     ┌───────────────────────────┐
│  CCTV / Cam  │ ──▶ │  Frame Extract  │ ──▶ │      AI Detection Layer    │
└──────────────┘     └─────────────────┘     │  YOLO11s  +  YOLO11s-Pose │
                                              └─────────────┬─────────────┘
                                                             ▼
                                        ┌────────────────────────────────────┐
                                        │      Suspect Detection Engine      │
                                        │  wrist–weapon distance matching    │
                                        │  ByteTrack ID persistence          │
                                        └─────────────────┬──────────────────┘
                                                           ▼
                                        ┌────────────────────────────────────┐
                                        │     Cross-Camera Re-ID Engine      │
                                        │   OSNet embedding + cosine sim     │
                                        └─────────────────┬──────────────────┘
                                                           ▼
                                        ┌────────────────────────────────────┐
                                        │      Alerts + Live Dashboard       │
                                        │  timeline · evidence · gallery     │
                                        └────────────────────────────────────┘
```

### 1. Weapon Detection & Person Attribution
- A custom-trained **YOLO11s** model (`weapon_best.pt`) detects **Pistol** and **Knife** classes every 3rd frame, keeping the feed fast without sacrificing accuracy.
- **ByteTrack** assigns persistent IDs to every person in view.
- Detections under **0.60 confidence** are dropped to keep false positives in check.
- **YOLO11s-Pose** exposes wrist keypoints for every tracked person.
- A weapon is attributed to the nearest wrist within a **90px threshold** — that person is flagged `SUSPECT`.
- Confirmed suspects are cropped and handed off to the Re-ID engine in real time.

### 2. Cross-Camera Suspect Re-Identification
- The suspect's crop is passed through an **OSNet** (TorchReid) network, producing a 512-dimension appearance embedding.
- That embedding is compared via **cosine similarity** against every suspect already logged, across every camera.
- A similarity score **≥ 0.75** triggers a `REIDENTIFIED` match — the same suspect, a new sighting — instead of a fresh, duplicate record.

### 3. Evidence Logging & Alerts
- Every `WEAPON_DETECTED` and `REIDENTIFIED` event is written to a structured, timestamped JSON evidence log — camera name, weapon type, and match confidence included.
- Weapon detections fire a 3-note siren; Re-ID matches fire a softer alert tone.

### 🧩 Bonus: Activity & Crowd Analytics
Running alongside the core threat pipeline:
- **Activity Classification** — Sitting / Standing / Walking / Running, from joint-angle pose analysis
- **Group Detection** — clusters people moving together via trajectory (Fréchet distance) similarity
- **Crowd Heatmaps** — accumulates position data into live congestion heatmaps

---

## 📈 Model Performance

Trained on a customized CCTV guns & knives dataset (8,807 annotated instances) for 60 epochs with heavy augmentation for angle, lighting, and occlusion variance.

<div align="center">

| Metric | Score |
|:---:|:---:|
| **mAP@50** | 🟢 83.4% |
| **Precision** | 🟢 84.5% |
| **Recall** | 🟡 75.9% |
| **mAP@50-95** | 🟡 48.4% |

</div>

---

## 🖥️ Dashboard Preview

The live dashboard ships with three views:

- **Live Feeds** — multi-camera grid with real-time bounding boxes and activity tags
- **Suspects** — gallery of flagged individuals with Re-ID confidence scores
- **Evidence Log** — full searchable event history (weapon type, camera, timestamp, similarity)

> Sample session: `1 suspect` · `2 Re-ID matches` · `3 evidence logs` · `85.45% avg. match confidence`

---

## 🛠️ Tech Stack

<div align="center">

| Layer | Stack |
|---|---|
| **Vision & Detection** | Ultralytics YOLO11 (detection + pose), OpenCV |
| **Re-Identification** | TorchReid, OSNet (`osnet_x1_0`), PyTorch |
| **Tracking** | ByteTrack-realtime |
| **Backend** | FastAPI, Uvicorn, multithreaded camera workers |
| **Data Layer** | NumPy, Pandas, SciPy, JSON-based evidence/suspect stores |
| **Frontend** | HTML5, CSS3, JavaScript |

</div>

---

## 🚀 Getting Started

```bash
# Clone the repository
git clone https://github.com/<your-username>/sentinelvision.git
cd sentinelvision

# Install dependencies
pip install -r requirements.txt

# Run the backend
uvicorn main:app --reload

# Open the dashboard
http://localhost:8000
```

> Add a camera source (webcam index or RTSP/video URL) directly from the dashboard's **Add Camera** panel to start monitoring.



<div align="center">

### Built to make surveillance intelligent, not just recorded.

</div>