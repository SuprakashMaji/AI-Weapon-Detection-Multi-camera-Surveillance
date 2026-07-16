import os

# Get the project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Models (absolute paths)
POSE_MODEL_PATH = os.path.join(PROJECT_ROOT, "models/yolo11s-pose.pt")
PERSON_MODEL_PATH = os.path.join(PROJECT_ROOT, "models/yolo11n.pt")
WEAPON_MODEL_PATH = os.path.join(PROJECT_ROOT, "models/rik_best_best.pt")

# Database
DATABASE_PATH = os.path.join(PROJECT_ROOT, "backend/reid/suspect_database.json")

# Logs
LOG_PATH = os.path.join(PROJECT_ROOT, "outputs/logs/evidence_log.json")

# Outputs
SUSPECT_FOLDER = os.path.join(PROJECT_ROOT, "outputs/suspects")
LIVE_FOLDER = os.path.join(PROJECT_ROOT, "outputs/live")
TEMP_FOLDER = os.path.join(PROJECT_ROOT, "outputs/temp")

# Activity counts captured *from inside the weapon-detection pipeline*
# (Sitting/Standing/Walking/Running per weapon camera). Kept separate from
# outputs/activity_status (used by the standalone Activity & Heatmap
# dashboard) so the two features never collide on the same filename.
WEAPON_ACTIVITY_STATUS_FOLDER = os.path.join(PROJECT_ROOT, "outputs/weapon_activity_status")

# Create folders automatically
os.makedirs(SUSPECT_FOLDER, exist_ok=True)
os.makedirs(LIVE_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs(WEAPON_ACTIVITY_STATUS_FOLDER, exist_ok=True)
os.makedirs(os.path.join(PROJECT_ROOT, "outputs/logs"), exist_ok=True)