import json
import threading


from backend.camera_manager.thread_manager import (
    start_camera_threads
)

# --------------------------------
# CAMERA CONFIGURATION
# --------------------------------

CAMERAS = {

    "Camera_A":
    "test_videos/test16.mp4",

    "Camera_B":
    "test_videos/test16.2.mp4",

    "Camera_C":
    "test_videos/test6.mp4",

    # Optional
    # "Camera_D":
    # "test_videos/test18.mp4"
}

# --------------------------------
# START SYSTEM
# --------------------------------

def process_all_cameras(
        stop_event
):

    # Clear suspect database
    with open(
        "backend/reid/suspect_database.json",
        "w"
    ) as f:

        json.dump(
            {},
            f,
            indent=4
        )

    # Clear evidence logs
    with open(
        "outputs/logs/evidence_log.json",
        "w"
    ) as f:

        json.dump(
            [],
            f,
            indent=4
        )

    print(
        "\nStarting Multi-Camera System...\n"
    )

    start_camera_threads(
        CAMERAS,
        stop_event
    )

    print(
        "\nAll camera threads finished."
    )


if __name__ == "__main__":

    stop_event = threading.Event()

    process_all_cameras(
        stop_event
    )