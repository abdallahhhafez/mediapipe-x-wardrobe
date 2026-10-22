"""Single source of truth for every tunable threshold (spec §8).

Mirrors ts/ingestConfig.ts — keep the two in sync. Do not scatter magic
numbers anywhere else in the pipeline.
"""

INGEST_CONFIG = {
    # S0 — input validation
    "blurThreshold": 60,            # variance of Laplacian on 512px downscale
    "minSourceSidePx": 512,
    "minPersonHeightRatio": 0.40,

    # S1 — parsing post-process
    "parseInputSize": 512,
    "minComponentAreaRatio": 0.003,  # of person bbox area
    "morphCloseKernel": 5,

    # S3 — cutout normalization
    "maskErodePx": 3,
    "maskFeatherPx": 1,
    "cutoutMarginPct": 0.08,
    "maxDeskewDegrees": 25,
    "cutoutSizePx": 1024,
    "occlusionOverlapRatio": 0.15,

    # S2 — layer splitting (open jacket over shirt)
    "layerSplitOuterDeltaE": 12,
    "layerSplitCenterDeltaE": 25,
    "layerSplitCenterWidthRange": [0.15, 0.50],
    "layerSplitClipConfirm": 0.35,   # Phase 2: CLIP cross-check gate

    # S4 — attribute confidence gates (Phase 2)
    "clipMinConfidence": 0.40,
    "clipMinMargin": 0.10,
    # how far a labelled color may be refined toward the measured pixels:
    # same family, and only while the chroma stays this close (CIELAB C*)
    "colorRefineMaxChromaDelta": 12.0,

    # S6 — dedup (Phase 3)
    "dedupSimilarity": 0.88,
    "dedupColorDeltaE": 15,
}
