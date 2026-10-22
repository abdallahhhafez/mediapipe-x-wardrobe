"""Diagnostic: what is actually inside the holes/notches of a garment mask?

Reports, per garment, the ATR label composition of pixels that the cutout
currently drops but that sit inside the garment's convex hull. Tells us
whether the gaps are arms, bags, phones (background), etc.

  python -m tools.diagnose_holes <image> [<image> ...]
"""
import sys

import cv2
import numpy as np

from pipeline import s0_validate, s1_parse, s2_garments
from pipeline.atr import ATR_NAMES
from pipeline.config import INGEST_CONFIG as CFG


def main(paths):
    for path in paths:
        print(f"\n=== {path}")
        v = s0_validate.validate(path)
        if v.reject_reason:
            print("  rejected:", v.reject_reason)
            continue
        rgb = v.image
        label_map = s1_parse.parse(rgb)
        px0, py0, px1, py1 = v.person.bbox
        area = max(1.0, (px1 - px0) * (py1 - py0))
        clean = lambda m: s1_parse.clean_class_mask(m, area)
        garments = s2_garments.extract_garments(rgb, label_map, v.person, clean)

        for g in garments:
            if g.category == "accessory":
                continue
            m = g.mask.astype(np.uint8)
            hull = np.zeros_like(m)
            cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cnts:
                continue
            cv2.fillConvexPoly(hull, cv2.convexHull(np.vstack(cnts)), 1)
            gap = (hull & ~m).astype(bool)
            if gap.sum() == 0:
                print(f"  {g.category}: no gaps")
                continue
            labels, counts = np.unique(label_map[gap], return_counts=True)
            order = np.argsort(-counts)
            total = counts.sum()
            comp = ", ".join(
                f"{ATR_NAMES.get(int(labels[i]), labels[i])}={counts[i]/total:.0%}"
                for i in order[:5])
            print(f"  {g.category}: gap={gap.sum()/m.sum():.0%} of garment | {comp}")


if __name__ == "__main__":
    main(sys.argv[1:])
