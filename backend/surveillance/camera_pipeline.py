import os
import json
import cv2
import numpy as np
from datetime import datetime
from ultralytics import YOLO

from backend.utils.constants import *
from backend.utils.config import *

from backend.reid.reid_utils import (
    save_suspect_to_database,
    search_database
)

from backend.logging.evidence_logger import (
    log_weapon_detection,
    log_reid_match
)

# Activity classification (Sitting / Standing / Walking / Running) reused
# from the standalone Activity & Heatmap feature so the weapon-detection
# feed can show a live headcount-by-activity mini dashboard too.
from web_backend.model import ActivityModel

# How often (in frames) the activity model runs. Matches the weapon-model
# cadence below so the two heavy models don't both run on every frame.
ACTIVITY_CHECK_INTERVAL = 3

# --------------------------------
# LOAD MODELS
# --------------------------------

# pose_model = YOLO(
#     POSE_MODEL_PATH
# )

# person_model = YOLO(
#     PERSON_MODEL_PATH
# )

# weapon_model = YOLO(
#     WEAPON_MODEL_PATH
# )


# --------------------------------
# CAMERA PIPELINE
# --------------------------------

def process_camera(
    video_path,
    camera_name,
    stop_event
):

    print(
        f"Starting {camera_name}"
    )

    pose_model = YOLO(
        POSE_MODEL_PATH
    )

    # person_model = YOLO(
    #     PERSON_MODEL_PATH
    # )

    weapon_model = YOLO(
        WEAPON_MODEL_PATH
    )

    cap = cv2.VideoCapture(
        video_path
    )

    if not cap.isOpened():

        print(
            f"Cannot open {camera_name}"
        )

        return

    # -------------------------
    # ACTIVITY MODEL (Sitting / Standing / Walking / Running)
    # -------------------------
    # Separate model instance from the pose-tracking one above — this one
    # classifies activity per person instead of locating wrists for the
    # weapon-hand association.

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    activity_model = ActivityModel(
        model_name=POSE_MODEL_PATH,
        fps=fps
    )

    activity_status_path = (
        f"{WEAPON_ACTIVITY_STATUS_FOLDER}/"
        f"{camera_name}.json"
    )

    # -------------------------
    # CAMERA STATES
    # -------------------------

    saved_suspects = set()

    confirmed_suspects = set()

    logged_matches = set()

    # track_id -> (matched_suspect_id, score)
    # Once a track is Re-ID matched to an existing suspect, this keeps
    # that label/box red on every later frame, instead of only on the
    # 1-in-10 frames where the Re-ID check actually runs.
    matched_status = {}

    # -------------------------
    # FRAME LOOP
    # -------------------------

    frame_count = 0
    while not stop_event.is_set():
        frame_count += 1
        ret, frame = cap.read()

        if not ret:

            cap.set(
                cv2.CAP_PROP_POS_FRAMES,
                0
            )

            continue

        display_frame = frame.copy()

        # =========================
        # POSE TRACKING
        # =========================

        pose_results = pose_model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            conf=0.4,
            verbose=False
        )

        pose_result = pose_results[0]

        persons = []

        if (
            pose_result.boxes.id is not None
            and
            pose_result.keypoints is not None
        ):

            track_ids = (
                pose_result.boxes.id
                .cpu()
                .numpy()
                .astype(int)
            )

            boxes = (
                pose_result.boxes.xyxy
                .cpu()
                .numpy()
            )

            keypoints = (
                pose_result.keypoints.xy
                .cpu()
                .numpy()
            )

            for box, track_id, kpts in zip(
                boxes,
                track_ids,
                keypoints
            ):

                x1, y1, x2, y2 = (
                    box.astype(int)
                )

                lw = tuple(
                    map(
                        int,
                        kpts[LEFT_WRIST]
                    )
                )

                rw = tuple(
                    map(
                        int,
                        kpts[RIGHT_WRIST]
                    )
                )

                persons.append({

                    "id": track_id,

                    "box": (
                        x1,
                        y1,
                        x2,
                        y2
                    ),

                    "lw": lw,

                    "rw": rw
                })

        # =========================
        # WEAPON DETECTION
        # =========================

        if frame_count % 3 == 0:

            weapon_results = weapon_model.predict(
                frame,
                conf=0.6,
                verbose=False
            )

        else:

            weapon_results = []

        suspect_weapons = {}

        for result in weapon_results:

            boxes = result.boxes

            for box in boxes:

                cls = int(
                    box.cls[0]
                )

                class_name = (
                    weapon_model.names[cls]
                )

                x1, y1, x2, y2 = (
                    box.xyxy[0]
                    .cpu()
                    .numpy()
                    .astype(int)
                )

                center_x = (
                    x1 + x2
                ) // 2

                center_y = (
                    y1 + y2
                ) // 2

                weapon_center = (
                    center_x,
                    center_y
                )

                # Draw weapon box

                cv2.rectangle(
                    display_frame,
                    (x1, y1),
                    (x2, y2),
                    YELLOW,
                    2
                )

                cv2.putText(
                    display_frame,
                    class_name,
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    YELLOW,
                    2
                )

                # ---------------------
                # Find nearest wrist
                # ---------------------

                min_distance = 999999

                owner_id = None

                for person in persons:

                    lw = person["lw"]
                    rw = person["rw"]

                    d1 = np.linalg.norm(
                        np.array(
                            weapon_center
                        )
                        -
                        np.array(lw)
                    )

                    d2 = np.linalg.norm(
                        np.array(
                            weapon_center
                        )
                        -
                        np.array(rw)
                    )

                    d = min(
                        d1,
                        d2
                    )

                    if d < min_distance:

                        min_distance = d

                        owner_id = (
                            person["id"]
                        )

                # ---------------------
                # Mark suspect
                # ---------------------

                if (
                    owner_id is not None
                    and
                    min_distance
                    < DISTANCE_THRESHOLD
                ):

                    confirmed_suspects.add(
                        owner_id
                    )

                    suspect_weapons[
                        owner_id
                    ] = class_name

        # =========================
        # PROCESS EVERY PERSON
        # =========================

        for person in persons:

            x1, y1, x2, y2 = (
                person["box"]
            )

            person_id = (
                person["id"]
            )

            color = GREEN

            label = (
                f"ID:{person_id}"
            )

            # ---------------------
            # Armed suspect
            # ---------------------

            if (
                person_id
                in
                confirmed_suspects
            ):

                color = RED

                label = (
                    f"SUSPECT "
                    f"{person_id}"
                )

                # -----------------
                # Save snapshot once
                # -----------------

                if (
                    person_id
                    not in
                    saved_suspects
                ):

                    crop = frame[
                        max(
                            0,
                            y1
                        ):
                        max(
                            0,
                            y2
                        ),

                        max(
                            0,
                            x1
                        ):
                        max(
                            0,
                            x2
                        )
                    ]

                    if crop.size != 0:

                        timestamp = (
                            datetime
                            .now()
                            .strftime(
                                "%Y%m%d_%H%M%S"
                            )
                        )

                        filename = (
                            f"{SUSPECT_FOLDER}/"
                            f"suspect_"
                            f"{person_id}_"
                            f"{timestamp}.jpg"
                        )

                        cv2.imwrite(
                            filename,
                            crop
                        )

                        # ---------------------
                        # Don't create a duplicate suspect
                        # ---------------------
                        # Before adding a brand-new entry to the global
                        # suspect database, check whether this person is
                        # already a known suspect (e.g. flagged earlier
                        # on this camera, or on a different camera).
                        # Without this check, every newly armed track id
                        # creates a new suspect record even if it's the
                        # same physical person seen before.

                        existing_id, existing_score = (
                            search_database(
                                filename,
                                threshold=
                                MATCH_THRESHOLD
                            )
                        )

                        if existing_id is not None:

                            # Already known — log as a Re-ID match
                            # instead of creating a duplicate suspect.

                            try:
                                os.remove(filename)
                            except OSError:
                                pass

                            matched_status[person_id] = (
                                existing_id,
                                existing_score
                            )

                            unique_match = (
                                f"{camera_name}_"
                                f"{existing_id}"
                            )

                            if unique_match not in logged_matches:

                                log_reid_match(
                                    existing_id,
                                    existing_score,
                                    camera_name
                                )

                                logged_matches.add(
                                    unique_match
                                )

                        else:

                            # Genuinely new suspect — create the entry.

                            save_suspect_to_database(
                                suspect_id=(
                                    f"{person_id}_"
                                    f"{timestamp}"
                                ),
                                image_path=filename,
                                weapon_type=
                                suspect_weapons.get(
                                    person_id,
                                    "unknown"
                                )
                            )

                            log_weapon_detection(
                                person_id,
                                suspect_weapons.get(
                                    person_id,
                                    "unknown"
                                ),
                                camera_name
                            )

                        saved_suspects.add(
                            person_id
                        )

            # ---------------------
            # Previously Re-ID matched (sticky)
            # ---------------------
            # If this track isn't currently armed in THIS frame but was
            # already Re-ID matched to a known suspect on an earlier
            # check-frame, keep showing it as a match instead of
            # flickering back to a plain green "ID:x" box.

            elif person_id in matched_status:

                match_id, match_score = matched_status[person_id]

                color = RED

                label = (
                    f"SUSPECT "
                    f"{match_score:.2f}"
                )

            # =====================
            # ReID Search
            # =====================

            crop = frame[
                max(0, y1):
                max(0, y2),

                max(0, x1):
                max(0, x2)
            ]

            if (
                crop.size != 0
                and
                frame_count % 10 == 0
            ):

                temp_file = (
                    f"{TEMP_FOLDER}/"
                    f"temp_"
                    f"{camera_name}.jpg"
                )

                cv2.imwrite(
                    temp_file,
                    crop
                )

                match_id, score = (
                    search_database(
                        temp_file,
                        threshold=
                        MATCH_THRESHOLD
                    )
                )

                if (
                    match_id
                    is not None
                ):

                    color = RED

                    label = (
                        f"SUSPECT "
                        f"{score:.2f}"
                    )

                    # Remember this match so later frames (where the
                    # 1-in-10 Re-ID check doesn't run) still show it.
                    matched_status[person_id] = (
                        match_id,
                        score
                    )

                    unique_match = (
                        f"{camera_name}_"
                        f"{match_id}"
                    )

                    if (
                        unique_match
                        not in
                        logged_matches
                    ):

                        log_reid_match(
                            match_id,
                            score,
                            camera_name
                        )

                        logged_matches.add(
                            unique_match
                        )

            # =====================
            # Draw Person
            # =====================

            cv2.rectangle(
                display_frame,
                (x1, y1),
                (x2, y2),
                color,
                2
            )

            cv2.putText(
                display_frame,
                label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2
            )

            # Draw wrists

            cv2.circle(
                display_frame,
                person["lw"],
                5,
                BLUE,
                -1
            )

            cv2.circle(
                display_frame,
                person["rw"],
                5,
                RED,
                -1
            )

        # =========================
        # ACTIVITY DETECTION (Sitting / Standing / Walking / Running)
        # =========================
        # Runs on the same cadence as weapon detection so the extra pose
        # pass doesn't add cost on every single frame. Counts are written
        # to a small JSON file the dashboard polls — never allowed to
        # crash the weapon pipeline if it fails for any reason.

        if frame_count % ACTIVITY_CHECK_INTERVAL == 0:

            try:

                _, activity_counts = (
                    activity_model.process_frame(
                        frame.copy()
                    )
                )

                with open(
                    activity_status_path,
                    "w"
                ) as f:

                    json.dump(
                        {
                            "counts": activity_counts,
                            "frame": frame_count
                        },
                        f
                    )

            except Exception as e:

                print(
                    f"[{camera_name}] "
                    f"activity detection error: {e}"
                )

        # =========================
        # Save frame for dashboard
        # =========================

        live_frame = (
            f"{LIVE_FOLDER}/"
            f"{camera_name}.jpg"
        )

        if frame_count % 3 == 0:

            cv2.imwrite(
                live_frame,
                display_frame
            )

        # =========================
        # Display window
        # =========================

        # cv2.imshow(
        #     camera_name,
        #     display_frame
        # )

        # if (
        #     cv2.waitKey(1)
        #     & 0xFF
        #     ==
        #     ord("q")
        # ):
        #     break

    # =============================
    # Cleanup
    # =============================

    cap.release()

    temp_file = (
        f"{TEMP_FOLDER}/"
        f"temp_{camera_name}.jpg"
    )

    if os.path.exists(
        temp_file
    ):
        os.remove(
            temp_file
        )

    # cv2.destroyWindow(
    #     camera_name
    # )


'''
Frame
│
├── Pose Tracking
│
├── Weapon Detection
│
├── Weapon-Hand Association
│
├── Save Snapshot
│
├── Save OSNet Embedding
│
├── ReID Search
│
├── Draw Results
│
├── Evidence Logging
│
├── Save Live Frame
│
└── Display Frame'''