// Every tunable in one place (spec §8). Keep in sync with pipeline/config.py.

export const INGEST_CONFIG = {
  blurThreshold: 60,
  minPersonHeightRatio: 0.40,
  minComponentAreaRatio: 0.003,
  maskErodePx: 3,
  maskFeatherPx: 1,
  cutoutMarginPct: 0.08,
  maxDeskewDegrees: 25,
  occlusionOverlapRatio: 0.15,
  clipMinConfidence: 0.40,
  clipMinMargin: 0.10,
  colorRefineMaxChromaDelta: 12.0,
  layerSplitOuterDeltaE: 12,
  layerSplitCenterDeltaE: 25,
  layerSplitCenterWidthRange: [0.15, 0.50] as [number, number],
  layerSplitClipConfirm: 0.35,
  dedupSimilarity: 0.88,
  dedupColorDeltaE: 15,
} as const;
