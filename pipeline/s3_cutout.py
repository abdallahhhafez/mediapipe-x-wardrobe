"""S3 — cutout normalization: catalog-style white-background PNG (spec §4 S3)."""
import numpy as np
import cv2

from .config import INGEST_CONFIG as CFG
from .s2_garments import LM, _px


def torso_angle_deg(landmarks, w, h, use_hips=False) -> float:
    if use_hips:
        # bottoms: rotate the hip-midpoint -> ankle-midpoint axis to vertical.
        # (The raw hip vector tilts on a relaxed stance and over-rotates.)
        hip = (_px(landmarks[LM["L_HIP"]], w, h) + _px(landmarks[LM["R_HIP"]], w, h)) / 2
        ank = (_px(landmarks[LM["L_ANKLE"]], w, h) + _px(landmarks[LM["R_ANKLE"]], w, h)) / 2
        dx, dy = (ank - hip)
        ang = np.degrees(np.arctan2(dx, dy))   # 0 when perfectly vertical
        return float(np.clip(-ang, -CFG["maxDeskewDegrees"], CFG["maxDeskewDegrees"]))
    a = _px(landmarks[LM["L_SHOULDER"]], w, h)
    b = _px(landmarks[LM["R_SHOULDER"]], w, h)
    dx, dy = (b - a)
    ang = np.degrees(np.arctan2(dy, dx))
    # shoulders should be horizontal: rotate by -ang (mod 180, pick nearest)
    if ang > 90: ang -= 180
    if ang < -90: ang += 180
    return float(np.clip(ang, -CFG["maxDeskewDegrees"], CFG["maxDeskewDegrees"]))


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    ff = mask.copy()
    hh, ww = mask.shape
    ffmask = np.zeros((hh + 2, ww + 2), np.uint8)
    cv2.floodFill(ff, ffmask, (0, 0), 1)
    return (mask | (ff == 0)).astype(np.uint8)


def hull_gap(mask: np.ndarray) -> np.ndarray:
    """Boolean mask of what the garment's convex hull covers but the mask doesn't."""
    m = mask.astype(np.uint8)
    hull = np.zeros_like(m)
    cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if cnts:
        cv2.fillConvexPoly(hull, cv2.convexHull(np.vstack(cnts)), 1)
    return (hull & ~m).astype(bool)


def make_cutout(rgb: np.ndarray, mask: np.ndarray, landmarks, category: str,
                occluder: np.ndarray = None) -> np.ndarray:
    """Return cutoutSizePx² RGB uint8 composited on pure white.

    occluder: mask of body parts (arms/hands) that may cover the garment.
    Where an occluder sits inside the garment silhouette we keep it in the
    cutout — a hand over a shirt looks natural; a hand-shaped hole doesn't.
    """
    h, w = rgb.shape[:2]

    mask = mask.astype(np.uint8)
    if not mask.any():
        return np.full((CFG["cutoutSizePx"],) * 2 + (3,), 255, np.uint8)

    if occluder is not None and occluder.any():
        # An occluder counts only where it lies inside the garment's convex
        # hull: crossed arms across a torso are in; the same arm hanging
        # beside the hip is out. The hull also spans a garment that the arms
        # severed into disjoint pieces, so those rejoin.
        hull = np.zeros_like(mask)
        cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if cnts:
            cv2.fillConvexPoly(hull, cv2.convexHull(np.vstack(cnts)), 1)
        mask = mask | (occluder.astype(np.uint8) & hull)

        # Objects held against the garment (phone, watch) carry no body-part
        # label, but once the hand is in they end up fully enclosed — fill
        # any small enclosed hole regardless of what the parser called it.
        holes = _fill_holes(mask) & ~mask
        n, labels, stats, _ = cv2.connectedComponentsWithStats(holes, connectivity=8)
        limit = 0.06 * mask.sum()
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] <= limit:
                mask[labels == i] = 1

    if category == "shoes":
        # one shoes item, but the cutout shows only the larger shoe (spec S2)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(
            mask.astype(np.uint8), connectivity=8)
        if n > 2:
            biggest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
            mask = (labels == biggest).astype(np.uint8)

    # drop specks left detached from the garment — fingertips clipped by the
    # hull, stray parser noise — so the cutout is not orbited by fragments
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n > 2:
        areas = stats[1:, cv2.CC_STAT_AREA]
        keep = 1 + np.nonzero(areas >= 0.05 * areas.max())[0]
        mask = np.isin(labels, keep).astype(np.uint8)

    # 1-2. alpha from mask, erode then feather (kill background halo)
    m = mask.astype(np.uint8)
    er = CFG["maskErodePx"]
    if er > 0:
        m = cv2.erode(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * er + 1, 2 * er + 1)))
    alpha = m.astype(np.float32)
    fe = CFG["maskFeatherPx"]
    if fe > 0:
        alpha = cv2.GaussianBlur(alpha, (0, 0), fe)

    # 3. deskew around mask centroid
    angle = torso_angle_deg(landmarks, w, h, use_hips=category in ("bottom", "shoes"))
    ys, xs = np.nonzero(m)
    if len(xs) == 0:
        return np.full((CFG["cutoutSizePx"], CFG["cutoutSizePx"], 3), 255, np.uint8)
    cx, cy = float(xs.mean()), float(ys.mean())
    M = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    rgb_r = cv2.warpAffine(rgb, M, (w, h), flags=cv2.INTER_LINEAR,
                           borderMode=cv2.BORDER_REPLICATE)
    alpha_r = cv2.warpAffine(alpha, M, (w, h), flags=cv2.INTER_LINEAR)

    # 4. trim to content + pad to square with margin
    ys, xs = np.nonzero(alpha_r > 0.05)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    crop = rgb_r[y0:y1 + 1, x0:x1 + 1].astype(np.float32)
    a = alpha_r[y0:y1 + 1, x0:x1 + 1][..., None]

    # 6. normalize exposure on garment pixels only: auto-levels at 1/99 pct
    inside = crop[a[..., 0] > 0.5]
    if len(inside) > 100:
        lo, hi = np.percentile(inside, 1), np.percentile(inside, 99)
        # cap the gain: dark garments would otherwise get noise-stretched
        # into washed-out grey (a black tee is supposed to stay black)
        gain = min(255.0 / max(1.0, hi - lo), 1.5)
        if hi - lo > 20 and gain > 1.02:
            crop = np.clip((crop - lo) * gain, 0, 255)

    # 5. composite on pure white
    comp = crop * a + 255.0 * (1.0 - a)
    ch, cw = comp.shape[:2]
    side = int(max(ch, cw) * (1 + 2 * CFG["cutoutMarginPct"]))
    canvas = np.full((side, side, 3), 255.0, np.float32)
    oy, ox = (side - ch) // 2, (side - cw) // 2
    canvas[oy:oy + ch, ox:ox + cw] = comp

    # 7. resize to final
    out = cv2.resize(canvas, (CFG["cutoutSizePx"], CFG["cutoutSizePx"]),
                     interpolation=cv2.INTER_AREA)
    return out.astype(np.uint8)
