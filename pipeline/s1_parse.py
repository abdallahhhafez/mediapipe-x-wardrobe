"""S1 — human parsing with SegFormer fine-tuned on ATR (spec §4 S1).

Reference implementation runs the HF PyTorch checkpoint; the RN app runs the
int8 ONNX export of the same model (tools/export_models.py), so logits and
post-processing here define the expected behavior of the on-device path.
"""
import numpy as np
import cv2

from .config import INGEST_CONFIG as CFG

_MODEL = None
_PROCESSOR = None
MODEL_ID = "mattmdjaga/segformer_b2_clothes"


def _lazy_model():
    global _MODEL, _PROCESSOR
    if _MODEL is None:
        from transformers import SegformerImageProcessor, AutoModelForSemanticSegmentation
        _PROCESSOR = SegformerImageProcessor.from_pretrained(MODEL_ID)
        _MODEL = AutoModelForSemanticSegmentation.from_pretrained(MODEL_ID)
        _MODEL.eval()
    return _PROCESSOR, _MODEL


def parse(rgb: np.ndarray) -> np.ndarray:
    """Return per-pixel ATR label map at source resolution (uint8 HxW)."""
    import torch
    processor, model = _lazy_model()
    h, w = rgb.shape[:2]
    inputs = processor(images=rgb, return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits          # (1, 18, H/4, W/4)
    up = torch.nn.functional.interpolate(
        logits, size=(h, w), mode="bilinear", align_corners=False)
    return up.argmax(dim=1)[0].numpy().astype(np.uint8)


def clean_class_mask(mask: np.ndarray, person_bbox_area: float) -> np.ndarray:
    """Per-class post-processing: drop tiny components, close gaps, fill holes."""
    mask = mask.astype(np.uint8)

    # connected components; drop < minComponentAreaRatio of person bbox area
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    min_area = CFG["minComponentAreaRatio"] * person_bbox_area
    keep = np.zeros_like(mask)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= min_area:
            keep[labels == i] = 1

    # morphological close (zipper/button gaps)
    k = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (CFG["morphCloseKernel"], CFG["morphCloseKernel"]))
    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, k)

    # hole fill — but only SMALL holes (buttons, zippers, print gaps).
    # Large enclosed regions (background between the legs, arm gaps) are
    # real background; filling them puts room pixels inside the cutout.
    ff = keep.copy()
    hh, ww = keep.shape
    ffmask = np.zeros((hh + 2, ww + 2), np.uint8)
    cv2.floodFill(ff, ffmask, (0, 0), 1)
    holes = (ff == 0).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(holes, connectivity=8)
    max_hole = 0.02 * max(1, int(keep.sum()))
    small_holes = np.zeros_like(holes)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] <= max_hole:
            small_holes[labels == i] = 1
    return (keep | small_holes).astype(np.uint8)
