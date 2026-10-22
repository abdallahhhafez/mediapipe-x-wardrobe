// Data contracts for outfit-ingest (spec §3). Shared by pipeline + review sheet.

export type Category = 'top' | 'bottom' | 'outerwear' | 'shoes' | 'dress' | 'accessory';
export type Confidence = number; // 0..1
export type ItemSource = 'selfie' | 'catalog' | 'manual';
export type Formality = 'formal' | 'smart_casual' | 'casual' | 'sport';

export interface DetectedGarment {
  tempId: string;
  category: Category;
  sourceRegions: number[];        // ATR label indices that produced this garment
  maskRle: string;                // RLE-encoded binary mask, full-res
  bbox: [number, number, number, number];
  cutoutUri: string;              // normalized white-bg PNG, local file
  embedding: Float32Array;        // 512-d, L2-normalized, FashionCLIP image encoder
  attributes: {
    type:      { value: string; confidence: Confidence };
    neckline?: { value: string; confidence: Confidence };
    sleeve?:   { value: string; confidence: Confidence };
    length?:   { value: string; confidence: Confidence };
    pattern:   { value: string; confidence: Confidence };
    color:     { name: string; hex: string; lab: [number, number, number]; confidence: Confidence };
    formality: { value: Formality };  // deterministic — no confidence
  };
  generated: {
    name:        { ar: string; en: string };
    description: { ar: string; en: string };
  };
  match: null | {
    existingItemId: string;
    similarity: number;
    colorDeltaE: number;
  };
  quality: {
    occluded: boolean;
    maskAreaRatio: number;
    blurScore: number;
    warnings: string[];
  };
}

export interface IngestResult {
  sourceImageUri: string;
  personCount: number;
  garments: DetectedGarment[];
  rejectReason?: 'no_person' | 'too_blurry' | 'too_small' | 'no_garments';
}

export interface WearEvent {
  id: string;
  itemId: string;
  wornAt: string;                 // ISO date, from image EXIF if present, else upload time
  source: 'selfie_ingest' | 'manual';
  outfitId?: string;              // groups all garments from one photo
}

export interface CorrectionEvent {
  field: 'category' | 'type' | 'color' | 'formality' | 'dedup';
  predicted: string;
  corrected: string;
  confidence: number;
  category: Category;
}
