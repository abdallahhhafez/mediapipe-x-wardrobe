"""S4 (color axis) — deterministic dominant-color extraction (spec §4 S4).

No model: masked pixels -> LAB -> filter shadows/highlights -> k-means(3)
-> dominant cluster -> nearest palette color by CIEDE2000.

`resolve_named` is the other direction: a color *name* somebody else picked
(the VLM labeller) refined against the measured pixels, so "black" on a
washed-out photo can become the charcoal/grey the pixels actually show
without letting a warm indoor cast rename a cream tee to khaki.
"""
import json
import os

import cv2
import numpy as np

from .config import INGEST_CONFIG as CFG

_PALETTE = None

# Palette keys that sit on the same perceptual ramp. Refinement only ever
# moves a color within its own family (light/dark), never across hues.
COLOR_FAMILIES = [
    ["black", "charcoal", "grey", "white", "cream"],
    ["cream", "beige", "tan", "brown", "dark_brown", "khaki"],
    ["navy", "blue", "denim", "light_blue"],
    ["green", "olive"],
    ["burgundy", "red", "pink"],
    ["orange", "mustard", "yellow"],
    ["purple"],
    ["teal"],
]


def _palette():
    global _PALETTE
    if _PALETTE is None:
        p = os.path.join(os.path.dirname(__file__), "..", "assets", "color_palette.json")
        with open(p) as f:
            _PALETTE = json.load(f)["colors"]
    return _PALETTE


def palette_entry(key: str) -> dict:
    for c in _palette():
        if c["key"] == key:
            return c
    return None


def _family(key: str) -> list:
    return [k for fam in COLOR_FAMILIES if key in fam for k in fam]


def resolve_named(key: str, measured_lab) -> dict:
    """Palette entry for `key`, nudged along its family by the measured LAB.

    A labeller names the color it *sees*; the pixels know how light it is.
    Candidates are limited to the same family and to a similar chroma, so a
    grey read as "black" is corrected while a genuinely chromatic garment
    keeps the name it was given.
    """
    named = palette_entry(key)
    if named is None or measured_lab is None:
        return named
    lab = np.asarray(measured_lab, np.float32)
    chroma = float(np.hypot(lab[1], lab[2]))
    best, best_de = named, ciede2000(lab, np.array(named["lab"], np.float32))
    for k in _family(key):
        c = palette_entry(k)
        c_chroma = float(np.hypot(c["lab"][1], c["lab"][2]))
        # a big chroma gap means the pixels disagree about the *hue*, not the
        # lightness — that is a lighting cast, so leave the name alone
        if abs(c_chroma - chroma) > CFG["colorRefineMaxChromaDelta"]:
            continue
        de = ciede2000(lab, np.array(c["lab"], np.float32))
        if de < best_de:
            best, best_de = c, de
    return best


def _to_lab(rgb_px: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(rgb_px.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_RGB2LAB)
    lab = lab.reshape(-1, 3).astype(np.float32)
    lab[:, 0] *= 100.0 / 255.0
    lab[:, 1] -= 128.0
    lab[:, 2] -= 128.0
    return lab


def ciede2000(lab1, lab2) -> float:
    """CIEDE2000 color difference (sufficiently complete implementation)."""
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cb = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cb ** 7 / (Cb ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp = L2 - L1
    dCp = C2p - C1p
    dh = h2p - h1p
    if C1p * C2p == 0:
        dhp = 0.0
    elif abs(dh) <= 180:
        dhp = dh
    elif dh > 180:
        dhp = dh - 360
    else:
        dhp = dh + 360
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dhp) / 2)
    Lbp = (L1 + L2) / 2
    Cbp = (C1p + C2p) / 2
    if C1p * C2p == 0:
        hbp = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hbp = (h1p + h2p) / 2
    elif h1p + h2p < 360:
        hbp = (h1p + h2p + 360) / 2
    else:
        hbp = (h1p + h2p - 360) / 2
    T = (1 - 0.17 * np.cos(np.radians(hbp - 30)) + 0.24 * np.cos(np.radians(2 * hbp))
         + 0.32 * np.cos(np.radians(3 * hbp + 6)) - 0.20 * np.cos(np.radians(4 * hbp - 63)))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc = 1 + 0.045 * Cbp
    Sh = 1 + 0.015 * Cbp * T
    dTheta = 30 * np.exp(-(((hbp - 275) / 25) ** 2))
    Rc = 2 * np.sqrt(Cbp ** 7 / (Cbp ** 7 + 25 ** 7))
    Rt = -Rc * np.sin(np.radians(2 * dTheta))
    return float(np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2
                         + Rt * (dCp / Sc) * (dHp / Sh)))


def extract_color(rgb: np.ndarray, mask: np.ndarray, erode_px: int = 3) -> dict:
    m = cv2.erode(mask.astype(np.uint8),
                  cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * erode_px + 1,) * 2))
    px = rgb[m > 0]
    if len(px) < 50:
        px = rgb[mask > 0]
    if len(px) > 20000:
        px = px[np.random.RandomState(0).choice(len(px), 20000, replace=False)]

    lab = _to_lab(px)
    chroma = np.hypot(lab[:, 1], lab[:, 2])
    keep = (lab[:, 0] >= 15) & ~((lab[:, 0] > 92) & (chroma < 8))
    lab_f = lab[keep] if keep.sum() > 100 else lab

    k = min(3, len(lab_f))
    _, labels, centers = cv2.kmeans(
        lab_f.astype(np.float32), k, None,
        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.5),
        3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=k)
    order = np.argsort(-counts)
    dom = centers[order[0]]

    multicolor = False
    if k > 1 and counts[order[1]] > 0.30 * counts.sum():
        if ciede2000(dom, centers[order[1]]) > 30:
            multicolor = True

    best, best_de = None, 1e9
    for c in _palette():
        de = ciede2000(dom, np.array(c["lab"], np.float32))
        if de < best_de:
            best, best_de = c, de

    # hex of the actual dominant cluster (for UI chips)
    lab_img = dom.copy()
    lab_img[0] *= 255.0 / 100.0
    lab_img[1] += 128.0
    lab_img[2] += 128.0
    rgb_dom = cv2.cvtColor(lab_img.reshape(1, 1, 3).astype(np.uint8),
                           cv2.COLOR_LAB2RGB).flatten()

    return {
        "name": {"en": best["en"], "ar": best["ar"], "key": best["key"]},
        "hex": "#{:02x}{:02x}{:02x}".format(*rgb_dom),
        "lab": [round(float(x), 1) for x in dom],
        "confidence": float(max(0.0, 1.0 - best_de / 40.0)),
        "multicolor": multicolor,
    }
