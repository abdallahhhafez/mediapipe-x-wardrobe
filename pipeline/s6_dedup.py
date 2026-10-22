"""S6 — dedup against the existing closet (spec §4 S6).

Match => log a wear event instead of creating a duplicate item. Thresholds
are deliberately conservative: a false merge is worse than a false split
(wear history can't be cleanly un-merged).
"""
import numpy as np

from .config import INGEST_CONFIG as CFG
from .s4_color import ciede2000


def find_match(candidate_embedding: np.ndarray, candidate_lab, category: str,
               closet_items: list):
    """closet_items: [{id, category, embedding (np or list), colorLab, embedderVersion}].

    Returns {existingItemId, similarity, colorDeltaE} or None.
    Brute-force cosine is fine to ~2000 items (spec: don't index prematurely).
    """
    e = np.asarray(candidate_embedding, np.float32)
    e = e / (np.linalg.norm(e) + 1e-8)
    best = None
    for item in closet_items:
        if item["category"] != category:
            continue
        v = np.asarray(item["embedding"], np.float32)
        v = v / (np.linalg.norm(v) + 1e-8)
        sim = float(np.dot(e, v))
        if sim <= CFG["dedupSimilarity"]:
            continue
        de = ciede2000(np.asarray(candidate_lab, np.float32),
                       np.asarray(item["colorLab"], np.float32))
        if de >= CFG["dedupColorDeltaE"]:
            continue
        if best is None or sim > best["similarity"]:
            best = {"existingItemId": item["id"], "similarity": round(sim, 4),
                    "colorDeltaE": round(de, 1)}
    return best
