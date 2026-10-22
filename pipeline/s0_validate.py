"""S0 — input validation. Fail fast before any heavy model runs (spec §4 S0).

Also applies EXIF orientation: phone photos are stored rotated with an
orientation tag, and every downstream stage (pose, parsing, scanlines)
assumes upright pixels.
"""
import os
from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageOps

from .config import INGEST_CONFIG as CFG


@dataclass
class Person:
    # normalized [0..1] landmark coords, MediaPipe Pose indices
    landmarks: np.ndarray          # (33, 3) x, y, visibility
    bbox: tuple                    # (x0, y0, x1, y1) in pixels


@dataclass
class ValidatedInput:
    image: np.ndarray              # RGB uint8, EXIF-upright
    person: Optional[Person]
    person_count: int
    reject_reason: Optional[str]   # 'no_person' | 'too_blurry' | 'too_small' | 'stand_closer'
    blur_score: float


def load_upright_rgb(path: str) -> np.ndarray:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    return np.asarray(img.convert("RGB"))


def blur_score(rgb: np.ndarray) -> float:
    h, w = rgb.shape[:2]
    scale = 512 / max(h, w)
    small = cv2.resize(rgb, (max(1, int(w * scale)), max(1, int(h * scale))))
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def landmarks_bbox(lm: np.ndarray, w: int, h: int) -> tuple:
    vis = lm[lm[:, 2] > 0.3]
    if len(vis) == 0:
        vis = lm
    x0, y0 = vis[:, 0].min() * w, vis[:, 1].min() * h
    x1, y1 = vis[:, 0].max() * w, vis[:, 1].max() * h
    return (x0, y0, x1, y1)


_POSE = None


def detect_pose(rgb: np.ndarray, max_poses: int = 4):
    """Return (landmarks (33,3) of chosen person, num_poses) or (None, 0).

    Uses the MediaPipe Tasks PoseLandmarker (lite) — the same model the RN
    app ships. With multiple people, picks the pose whose bbox is largest
    and most centered (spec S0).
    """
    global _POSE
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision

    if _POSE is None:
        model_path = os.path.join(os.path.dirname(__file__), "..",
                                  "models", "pose_landmarker_lite.task")
        opts = vision.PoseLandmarkerOptions(
            base_options=mp_python.BaseOptions(
                model_asset_path=model_path,
                delegate=mp_python.BaseOptions.Delegate.CPU),
            num_poses=max_poses, running_mode=vision.RunningMode.IMAGE)
        _POSE = vision.PoseLandmarker.create_from_options(opts)

    mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    res = _POSE.detect(mp_img)
    if not res.pose_landmarks:
        return None, 0

    h, w = rgb.shape[:2]
    best, best_score = None, -1.0
    for lms in res.pose_landmarks:
        lm = np.array([[p.x, p.y, p.visibility] for p in lms])
        x0, y0, x1, y1 = landmarks_bbox(lm, w, h)
        area = (x1 - x0) * (y1 - y0) / (w * h)
        cx = ((x0 + x1) / 2 - w / 2) / w
        score = area - abs(cx)          # largest AND most centered
        if score > best_score:
            best, best_score = lm, score
    return best, len(res.pose_landmarks)


def validate(path: str) -> ValidatedInput:
    rgb = load_upright_rgb(path)
    h, w = rgb.shape[:2]

    if min(h, w) < CFG["minSourceSidePx"]:
        return ValidatedInput(rgb, None, 0, "too_small", 0.0)

    b = blur_score(rgb)
    if b < CFG["blurThreshold"]:
        return ValidatedInput(rgb, None, 0, "too_blurry", b)

    lm, n_poses = detect_pose(rgb)
    if lm is None:
        return ValidatedInput(rgb, None, 0, "no_person", b)

    bbox = landmarks_bbox(lm, w, h)
    person_h = bbox[3] - bbox[1]
    if person_h < CFG["minPersonHeightRatio"] * h:
        return ValidatedInput(rgb, None, n_poses, "stand_closer", b)

    return ValidatedInput(rgb, Person(lm, bbox), n_poses, None, b)
