"""Phase 1 runner: photo -> garment cutouts + debug overlay + IngestResult JSON.

Usage:
  python -m pipeline.run <image> [<image> ...] --out out/
"""
import argparse
import json
import os
import time

import cv2
import numpy as np

from . import (s0_validate, s1_parse, s2_garments, s3_cutout, s4_color,
               s4_formality, s5_naming, s6_dedup)

OVERLAY_COLORS = {
    "top": (66, 133, 244), "bottom": (52, 168, 83), "outerwear": (156, 39, 176),
    "shoes": (244, 180, 0), "dress": (234, 67, 53), "accessory": (0, 172, 193),
}


def process(path: str, out_dir: str, use_clip: bool = False,
            closet: list = None) -> dict:
    name = os.path.splitext(os.path.basename(path))[0]
    t0 = time.time()

    v = s0_validate.validate(path)
    if v.reject_reason:
        return {"sourceImageUri": path, "personCount": v.person_count,
                "garments": [], "rejectReason": v.reject_reason,
                "blurScore": round(v.blur_score, 1)}

    rgb = v.image
    h, w = rgb.shape[:2]
    t1 = time.time()

    # portrait/seated shots slip past S0 when the upper body fills the frame;
    # warn so the review sheet can suggest a full-body retake
    warnings = []
    lms = v.person.landmarks
    if all(lms[i][2] < 0.3 for i in (27, 28)):   # both ankles invisible
        warnings.append("not_full_body")

    label_map = s1_parse.parse(rgb)
    t2 = time.time()

    px0, py0, px1, py1 = v.person.bbox
    person_area = max(1.0, (px1 - px0) * (py1 - py0))
    clean = lambda m: s1_parse.clean_class_mask(m, person_area)
    garments = s2_garments.extract_garments(rgb, label_map, v.person, clean)
    t3 = time.time()

    # arms, hands, bags, belts covering a garment stay visible in its cutout
    from .atr import OCCLUDER_LABELS, OTHER_GARMENT_LABELS
    occluder = np.isin(label_map, OCCLUDER_LABELS).astype(np.uint8)
    other_garment = np.isin(label_map, OTHER_GARMENT_LABELS)

    overlay = rgb.copy()
    result_garments = []
    for g in garments:
        occ = occluder & ~np.isin(label_map, g.source_regions)
        cutout = s3_cutout.make_cutout(rgb, g.mask, v.person.landmarks,
                                       g.category, occluder=occ)
        # embeddings must stay pose-invariant: embed the garment-only cutout,
        # even though the displayed cutout keeps occluding arms visible
        embed_input = cutout if not occ.any() else \
            s3_cutout.make_cutout(rgb, g.mask, v.person.landmarks, g.category)

        # a gap made of OTHER garment labels means the parser confused two
        # garments (low-contrast outfits) — that is a bad mask, not occlusion
        gap = s3_cutout.hull_gap(g.mask)
        if gap.sum() > 0.15 * g.mask.sum() and \
                other_garment[gap].sum() > 0.5 * gap.sum():
            g.quality["warnings"].append("unreliable_mask")
        cut_path = os.path.join(out_dir, f"{name}_{g.category}_{g.temp_id}.png")
        cv2.imwrite(cut_path, cv2.cvtColor(cutout, cv2.COLOR_RGB2BGR))

        color = OVERLAY_COLORS.get(g.category, (128, 128, 128))
        overlay[g.mask > 0] = (0.55 * overlay[g.mask > 0] + 0.45 * np.array(color)).astype(np.uint8)
        x0, y0, x1, y1 = g.bbox
        cv2.rectangle(overlay, (x0, y0), (x1, y1), color, 3)
        cv2.putText(overlay, g.category, (x0, max(30, y0 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, color, 3)

        col = s4_color.extract_color(rgb, g.mask)
        g.attributes["color"] = col

        embedding, match = None, None
        if use_clip and g.category != "accessory":
            from . import s4_clip
            embedding = s4_clip.embed_image(embed_input)
            clip_attrs = s4_clip.classify_garment(
                embedding, g.category, g.attributes.get("sleeve"))
            g.attributes.update(clip_attrs)
            if closet:
                match = s6_dedup.find_match(embedding, col["lab"],
                                            g.category, closet)

        type_val = (g.attributes.get("type") or {}).get("value")
        pattern_val = (g.attributes.get("pattern") or {}).get("value")
        g.attributes["formality"] = {"value": s4_formality.formality(
            type_val or "", pattern_val)}

        neckline_val = (g.attributes.get("neckline") or {}).get("value")
        gen = s5_naming.generate(
            garment_type=type_val if type_val and type_val != "unknown" else g.category,
            category=g.category, color=col,
            neckline=neckline_val,
            sleeve=g.attributes.get("sleeve"),
            pattern=pattern_val if pattern_val != "solid" else None,
            formality=g.attributes["formality"]["value"],
            temp_id=g.temp_id)

        result_garments.append({
            "tempId": g.temp_id, "category": g.category,
            "sourceRegions": g.source_regions, "bbox": list(g.bbox),
            "cutoutUri": cut_path, "attributes": g.attributes,
            "generated": gen, "match": match,
            "embedding": embedding.tolist() if embedding is not None else None,
            "quality": g.quality,
        })
    t4 = time.time()

    ov_path = os.path.join(out_dir, f"{name}_overlay.jpg")
    cv2.imwrite(ov_path, cv2.cvtColor(
        cv2.resize(overlay, (w // 3, h // 3)), cv2.COLOR_RGB2BGR))

    return {
        "sourceImageUri": path, "personCount": v.person_count,
        "warnings": warnings,
        "garments": result_garments, "overlay": ov_path,
        "blurScore": round(v.blur_score, 1),
        "timingsMs": {"validate": int((t1 - t0) * 1000), "parse": int((t2 - t1) * 1000),
                      "garments": int((t3 - t2) * 1000), "cutouts": int((t4 - t3) * 1000)},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+")
    ap.add_argument("--out", default="out")
    ap.add_argument("--clip", action="store_true",
                    help="run FashionCLIP attributes + embedding + dedup")
    ap.add_argument("--closet", default=None,
                    help="JSON file with existing items [{id,category,embedding,colorLab}]")
    ap.add_argument("--json-only", action="store_true",
                    help="print only the final JSON (for the API server)")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    closet = None
    if args.closet:
        with open(args.closet) as f:
            closet = json.load(f)

    results = []
    for p in args.images:
        r = process(p, args.out, use_clip=args.clip, closet=closet)
        results.append(r)
        if not args.json_only:
            print(json.dumps({k: v for k, v in r.items() if k != "garments"}, indent=None))
            for g in r["garments"]:
                print(f"  {g['category']:<10} attrs={g['attributes']} "
                      f"occluded={g['quality']['occluded']} area={g['quality']['maskAreaRatio']:.3f}")
    with open(os.path.join(args.out, "ingest_results.json"), "w") as f:
        json.dump(results, f, indent=2)
    if args.json_only:
        print("@@RESULT@@")
        print(json.dumps(results))


if __name__ == "__main__":
    main()
