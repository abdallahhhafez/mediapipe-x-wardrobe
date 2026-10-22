"""S2 — region → garment mapping, layer splitting, geometric attributes (spec §4 S2)."""
import uuid
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

from .atr import ATR, GARMENT_SOURCES
from .config import INGEST_CONFIG as CFG

# MediaPipe Pose landmark indices
LM = {"L_SHOULDER": 11, "R_SHOULDER": 12, "L_ELBOW": 13, "R_ELBOW": 14,
      "L_WRIST": 15, "R_WRIST": 16, "L_HIP": 23, "R_HIP": 24,
      "L_KNEE": 25, "R_KNEE": 26, "L_ANKLE": 27, "R_ANKLE": 28}


@dataclass
class Garment:
    temp_id: str
    category: str
    source_regions: list
    mask: np.ndarray                      # uint8 HxW, full-res
    bbox: tuple                           # x0, y0, x1, y1
    attributes: dict = field(default_factory=dict)
    quality: dict = field(default_factory=lambda: {
        "occluded": False, "maskAreaRatio": 0.0, "blurScore": 0.0, "warnings": []})


def _bbox_of(mask: np.ndarray) -> Optional[tuple]:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


def _px(lm_row, w, h):
    return np.array([lm_row[0] * w, lm_row[1] * h])


def _rgb_to_lab(px: np.ndarray) -> np.ndarray:
    """px: (N,3) uint8 RGB -> (N,3) float LAB (CIE, L in 0..100)."""
    lab = cv2.cvtColor(px.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2LAB)
    lab = lab.reshape(-1, 3).astype(np.float32)
    lab[:, 0] *= 100.0 / 255.0
    lab[:, 1] -= 128.0
    lab[:, 2] -= 128.0
    return lab


def _delta_e(a: np.ndarray, b: np.ndarray) -> float:
    # CIE76 is enough for the split heuristic; CIEDE2000 lives in s4 color.
    return float(np.linalg.norm(a - b))


def try_layer_split(rgb, upper_mask, landmarks, w, h):
    """Detect open jacket over a shirt via the symmetric three-band color
    pattern across torso scanlines. Returns (outer_mask, center_mask) or None.
    """
    ls, rs = _px(landmarks[LM["L_SHOULDER"]], w, h), _px(landmarks[LM["R_SHOULDER"]], w, h)
    lh, rh = _px(landmarks[LM["L_HIP"]], w, h), _px(landmarks[LM["R_HIP"]], w, h)
    y0 = max(0, int(min(ls[1], rs[1])))
    y1 = min(h - 1, int(max(lh[1], rh[1])))
    if y1 <= y0:
        return None

    votes, boundaries = 0, []
    rows = range(y0, y1, max(1, (y1 - y0) // 24))
    for y in rows:
        xs = np.nonzero(upper_mask[y])[0]
        if len(xs) < 30:
            continue
        row = rgb[y, xs]
        lab = _rgb_to_lab(row)
        n = len(xs)
        third = n // 3
        left, center, right = lab[:third], lab[third:2 * third], lab[2 * third:]
        lm_, cm_, rm_ = left.mean(0), center.mean(0), right.mean(0)
        outer_de = _delta_e(lm_, rm_)
        center_de = min(_delta_e(cm_, lm_), _delta_e(cm_, rm_))
        if outer_de < CFG["layerSplitOuterDeltaE"] and center_de > CFG["layerSplitCenterDeltaE"]:
            # locate actual center band edges: pixels closer to center color
            d_center = np.linalg.norm(lab - cm_, axis=1)
            d_outer = np.minimum(np.linalg.norm(lab - lm_, axis=1),
                                 np.linalg.norm(lab - rm_, axis=1))
            is_center = d_center < d_outer
            frac = is_center.mean()
            lo, hi = CFG["layerSplitCenterWidthRange"]
            if lo <= frac <= hi:
                votes += 1
                idx = np.nonzero(is_center)[0]
                boundaries.append((y, xs[idx[0]], xs[idx[-1]]))
    if votes < max(4, len(boundaries)):
        pass
    if votes < 6 or len(boundaries) < 6:
        return None

    center_mask = np.zeros_like(upper_mask)
    for y, xl, xr in boundaries:
        center_mask[y, xl:xr + 1] = 1
    center_mask = cv2.dilate(center_mask, np.ones((9, 9), np.uint8))
    center_mask &= upper_mask
    outer_mask = upper_mask & (1 - center_mask)
    if center_mask.sum() < 500 or outer_mask.sum() < 500:
        return None
    return outer_mask.astype(np.uint8), center_mask.astype(np.uint8)


def sleeve_from_pose(upper_mask, landmarks, w, h) -> str:
    """Lowest garment point along the arm axis vs elbow/wrist (spec S2 table)."""
    results = []
    for side in ("L", "R"):
        sh = _px(landmarks[LM[f"{side}_SHOULDER"]], w, h)
        el = _px(landmarks[LM[f"{side}_ELBOW"]], w, h)
        wr = _px(landmarks[LM[f"{side}_WRIST"]], w, h)
        if landmarks[LM[f"{side}_ELBOW"]][2] < 0.3:
            continue
        # walk from shoulder toward wrist; find how far the mask extends
        axis = wr - sh
        L = np.linalg.norm(axis)
        if L < 1:
            continue
        axis /= L
        t_elbow = np.dot(el - sh, axis) / L
        covered = 0.0
        for t in np.linspace(0.05, 1.0, 40):
            p = sh + axis * t * L
            x, y = int(p[0]), int(p[1])
            r = max(3, int(L * 0.04))
            x0, x1 = max(0, x - r), min(w, x + r + 1)
            y0, y1 = max(0, y - r), min(h, y + r + 1)
            if x1 > x0 and y1 > y0 and upper_mask[y0:y1, x0:x1].any():
                covered = t
        if covered < 0.12:
            results.append("sleeveless")
        elif covered < t_elbow - 0.05:
            results.append("short")
        elif covered < 0.90:
            results.append("three_quarter")
        else:
            results.append("long")
    if not results:
        return "unknown"
    # prefer the longer estimate (occluded arm reads short)
    order = ["sleeveless", "short", "three_quarter", "long"]
    return max(results, key=order.index)


def bottom_length_from_pose(mask, landmarks, w, h, dress=False) -> str:
    ys = np.nonzero(mask.any(axis=1))[0]
    if len(ys) == 0:
        return "unknown"
    lowest = ys.max()
    knees = [landmarks[LM["L_KNEE"]], landmarks[LM["R_KNEE"]]]
    ankles = [landmarks[LM["L_ANKLE"]], landmarks[LM["R_ANKLE"]]]
    knee_y = np.mean([k[1] for k in knees if k[2] > 0.3] or [np.nan]) * h
    ankle_y = np.mean([a[1] for a in ankles if a[2] > 0.3] or [np.nan]) * h
    if np.isnan(knee_y):
        return "unknown"
    calf_y = knee_y + (ankle_y - knee_y) * 0.5 if not np.isnan(ankle_y) else knee_y * 1.15
    if dress:
        if lowest < knee_y: return "mini"
        if lowest < calf_y: return "midi"
        return "maxi"
    if lowest < knee_y: return "shorts"
    if lowest < calf_y: return "cropped"
    return "full_length"


def extract_garments(rgb, label_map, person, clean_fn) -> list:
    """Map cleaned ATR regions to Garment objects. clean_fn(mask)->mask."""
    h, w = rgb.shape[:2]
    lm = person.landmarks
    px0, py0, px1, py1 = person.bbox
    person_area = max(1.0, (px1 - px0) * (py1 - py0))
    garments = []

    for category, labels in GARMENT_SOURCES:
        mask = np.isin(label_map, labels).astype(np.uint8)
        if mask.sum() == 0:
            continue
        mask = clean_fn(mask)
        if mask.sum() < CFG["minComponentAreaRatio"] * person_area:
            continue
        bbox = _bbox_of(mask)
        if bbox is None:
            continue

        if category == "top":
            split = try_layer_split(rgb, mask, lm, w, h)
            if split is not None:
                outer, center = split
                for cat, m in (("outerwear", outer), ("top", center)):
                    bb = _bbox_of(m)
                    if bb is None:
                        continue
                    g = Garment(str(uuid.uuid4())[:8], cat, labels, m, bb)
                    g.quality["warnings"].append("layer_split_heuristic")
                    garments.append(g)
                continue

        g = Garment(str(uuid.uuid4())[:8], category, labels, mask, bbox)
        garments.append(g)

    # geometric attributes + occlusion flags
    arm_mask = np.isin(label_map, [ATR["LEFT_ARM"], ATR["RIGHT_ARM"]]).astype(np.uint8)
    for g in garments:
        g.quality["maskAreaRatio"] = float(g.mask.sum() / person_area)
        if g.category in ("top", "outerwear"):
            # occlusion: skin/arm pixels inside the garment's convex hull
            # (crossed arms carve a hole in the mask — border dilation misses it)
            hull = np.zeros_like(g.mask)
            cnts, _ = cv2.findContours(g.mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if cnts:
                cv2.fillConvexPoly(hull, cv2.convexHull(np.vstack(cnts)), 1)
            overlap = (hull & arm_mask).sum() / max(1, g.mask.sum())
            if overlap > CFG["occlusionOverlapRatio"]:
                g.quality["occluded"] = True
                g.quality["warnings"].append("partially_hidden")
                # arm-axis walk is unreliable when arms cover the torso
                g.attributes["sleeve"] = "unknown"
            else:
                g.attributes["sleeve"] = sleeve_from_pose(g.mask, lm, w, h)
        elif g.category == "bottom":
            g.attributes["length"] = bottom_length_from_pose(g.mask, lm, w, h)
            # Pants and Skirt were merged into one bottom; keep which of the
            # two the parser actually saw, so labelling downstream does not
            # have to guess "trousers or skirt?" from a cropped cutout
            inside = g.mask > 0
            pants = int((label_map[inside] == ATR["PANTS"]).sum())
            skirt = int((label_map[inside] == ATR["SKIRT"]).sum())
            if max(pants, skirt) > 0:
                g.attributes["bottomKind"] = "skirt" if skirt > pants else "pants"
        elif g.category == "dress":
            g.attributes["length"] = bottom_length_from_pose(g.mask, lm, w, h, dress=True)
    return garments
