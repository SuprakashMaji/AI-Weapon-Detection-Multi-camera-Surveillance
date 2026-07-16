from backend.surveillance.camera_pipeline import (
    process_camera
)


def camera_worker(
    video_path,
    camera_name,
    stop_event
):
    """
    Worker function for one camera.
    Each thread runs this function.
    """

    process_camera(
        video_path,
        camera_name,
        stop_event
    )