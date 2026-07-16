import os
import json
import cv2
import torch
import torchreid
import numpy as np

DATABASE_PATH = (
    "backend/reid/"
    "suspect_database.json"
)

# -----------------------------
# OSNET MODEL
# -----------------------------
model = torchreid.models.build_model(
    name="osnet_x1_0",
    num_classes=1000,
    pretrained=True
)

model.eval()

# -----------------------------
# LOAD DATABASE
# -----------------------------
if os.path.exists(
    DATABASE_PATH
):

    try:

        with open(
            DATABASE_PATH,
            "r"
        ) as f:

            database = json.load(f)

    except:

        database = {}

else:

    database = {}


# -----------------------------
# FEATURE EXTRACTION
# -----------------------------
def extract_embedding(
    image_path
):

    image = cv2.imread(
        image_path
    )

    if image is None:
        return None

    image = cv2.resize(
        image,
        (128, 256)
    )

    image = (
        image
        .astype(np.float32)
        / 255.0
    )

    image = torch.tensor(
        image
    ).permute(
        2,
        0,
        1
    ).unsqueeze(0)

    with torch.no_grad():

        embedding = model(
            image
        )

    return (
        embedding
        .cpu()
        .numpy()
        .flatten()
        .tolist()
    )


# -----------------------------
# SAVE SUSPECT
# -----------------------------
def save_suspect_to_database(
    suspect_id,
    image_path,
    weapon_type
):

    embedding = extract_embedding(
        image_path
    )

    if embedding is None:
        return

    database[
        str(suspect_id)
    ] = {

        "weapon":
        weapon_type,

        "snapshot":
        image_path,

        "embedding":
        embedding
    }

    with open(
        DATABASE_PATH,
        "w"
    ) as f:

        json.dump(
            database,
            f,
            indent=4
        )

    print(
        f"[DATABASE] "
        f"Saved suspect "
        f"{suspect_id}"
    )


# -----------------------------
# CLEAR DATABASE
# -----------------------------
def clear_database():

    database.clear()

    with open(
        DATABASE_PATH,
        "w"
    ) as f:

        json.dump(
            database,
            f,
            indent=4
        )

    print(
        "[DATABASE] Cleared all suspects"
    )


# -----------------------------
# SEARCH DATABASE
# -----------------------------
def search_database(
    image_path,
    threshold=0.75
):

    embedding = extract_embedding(
        image_path
    )

    if embedding is None:

        return (
            None,
            0
        )

    embedding = np.array(
        embedding
    )

    best_match = None
    best_score = 0

    for suspect_id, data in database.items():

        db_embedding = np.array(
            data[
                "embedding"
            ]
        )

        score = np.dot(
            embedding,
            db_embedding
        ) / (

            np.linalg.norm(
                embedding
            )
            *
            np.linalg.norm(
                db_embedding
            )
        )

        if score > best_score:

            best_score = score
            best_match = suspect_id

    if best_score >= threshold:

        return (
            best_match,
            float(best_score)
        )

    return (
        None,
        float(best_score)
    )