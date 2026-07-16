import json
import os
from datetime import datetime

LOG_PATH = "outputs/logs/evidence_log.json"


def load_logs():

    if not os.path.exists(LOG_PATH):

        return []

    try:

        with open(LOG_PATH, "r") as f:
            return json.load(f)

    except:

        return []


def save_logs(logs):

    with open(LOG_PATH, "w") as f:

        json.dump(
            logs,
            f,
            indent=4
        )


def add_event(event):

    logs = load_logs()

    logs.append(event)

    save_logs(logs)


def log_weapon_detection(
    suspect_id,
    weapon,
    camera
):

    event = {

        "event":
        "WEAPON_DETECTED",

        "suspect_id":
        str(suspect_id),

        "weapon":
        weapon,

        "camera":
        camera,

        "timestamp":
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    }

    add_event(event)

    print(
        f"[LOG] Weapon detected: "
        f"{suspect_id}"
    )


def log_reid_match(
    suspect_id,
    similarity,
    camera
):

    event = {

        "event":
        "REIDENTIFIED",

        "suspect_id":
        str(suspect_id),

        "camera":
        camera,

        "similarity":
        float(similarity),

        "timestamp":
        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    }

    add_event(event)

    print(
        f"[LOG] ReID Match: "
        f"{suspect_id}"
    )