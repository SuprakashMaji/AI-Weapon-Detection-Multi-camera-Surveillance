import threading

from backend.camera_manager.camera_worker import (
    camera_worker
)


def start_camera_threads(
    cameras,
    stop_event
):
    """
    cameras = {
        "Camera_A": "video1.mp4",
        "Camera_B": "video2.mp4"
    }
    """

    threads = []

    # Create threads
    for camera_name, video_path in cameras.items():

        thread = threading.Thread(
            target=camera_worker,
            args=(
                video_path,
                camera_name,
                stop_event
            ),
            daemon=True
        )

        threads.append(
            thread
        )

    # Start threads
    for thread in threads:

        thread.start()

    # Wait for completion
    for thread in threads:

        thread.join()