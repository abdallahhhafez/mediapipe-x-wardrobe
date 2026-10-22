import mongoose from 'mongoose';

const { Schema } = mongoose;

const ItemSchema = new Schema({
  category: { type: String, required: true },          // top|bottom|outerwear|shoes|dress|accessory
  name: { ar: String, en: String },
  description: { ar: String, en: String },
  type: String,
  color: {
    key: String, en: String, ar: String,
    hex: String, lab: [Number],
  },
  formality: String,
  attributes: Schema.Types.Mixed,                      // sleeve, length, pattern, neckline...
  cutoutUrl: String,                                   // served from /cutouts
  sourceImageUrl: String,                              // the photo it came from
  source: { type: String, enum: ['selfie', 'catalog', 'manual'], default: 'selfie' },
  embedding: { type: [Number], default: undefined },   // 512-d FashionCLIP
  embedderVersion: { type: String, default: 'fashion-clip-v1' },
  createdAt: { type: Date, default: Date.now },
});

const WearEventSchema = new Schema({
  itemId: { type: Schema.Types.ObjectId, ref: 'Item', required: true },
  wornAt: { type: Date, required: true },
  source: { type: String, enum: ['selfie_ingest', 'manual'], default: 'selfie_ingest' },
  outfitId: String,                                    // groups garments from one photo
});

const CorrectionSchema = new Schema({
  field: String,                                       // category|type|color|formality|dedup
  predicted: String,
  corrected: String,
  confidence: Number,
  category: String,
  createdAt: { type: Date, default: Date.now },
});

export const Item = mongoose.model('Item', ItemSchema);
export const WearEvent = mongoose.model('WearEvent', WearEventSchema);
export const Correction = mongoose.model('Correction', CorrectionSchema);
