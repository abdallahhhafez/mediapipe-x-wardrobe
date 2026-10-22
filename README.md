# Wardrobe — mirror-selfie outfit ingestion (MERN + local ML)

A full-body mirror selfie goes in; per-garment white-background cutouts,
attributes, and dedup decisions come out — all inference local, zero
per-image cost. MERN app around the Python reference pipeline from the
`outfit-ingest` spec.

## Run

```bash
node server/index.js          # Express API :5050 (starts the inference worker :5055, needs local MongoDB)
npm --prefix client run dev   # React client :5173
```

Or via the Claude launch configs `api` and `web` (.claude/launch.json).
First ingest takes ~15 s (model load into the worker); warm ingests ~2 s
plus a few seconds per garment for LLM descriptions.

### Labelling

FashionCLIP scores a cutout against short prompts, and on real mirror
selfies it is wrong often enough to be visible in the closet — a striped
polo comes back as a tank top, white sneakers under warm light as olive
formal shoes. So when Ollama is running with `gemma3:4b` (multimodal), the
same cutout is shown to the local VLM under a **closed vocabulary** and its
answer becomes the label; CLIP's answer is kept beside it under
`attributes.*.clip` (server/vlm.js). Without Ollama, CLIP labels and the
pipeline's templates are used unchanged. Override with `OLLAMA_URL` /
`DESCRIBE_MODEL`.

Three things keep the VLM honest:

1. **Measured facts prune the vocabulary.** Pose says the bottom reached the
   ankle, so `shorts` is not on the menu (and the model is told where the
   garment fell on the body — the cutout is cropped, so only the pose knows).
   The parser already told Pants from Skirt on the full body, so a cropped
   wide leg cannot come back as a skirt.
2. **Color is named, then measured.** The model names the fabric color as a
   shop would; `s4_color.resolve_named` then moves that name along its own
   family toward the measured pixels — "black" on a washed-out photo becomes
   the charcoal or grey the pixels show. A large chroma gap means the pixels
   disagree about *hue*, not lightness — that is a lighting cast, and the
   name is left alone.
3. **The name is generated, not written.** `POST /relabel` on the worker runs
   the pipeline's own i18n tables over the confirmed attributes, so names
   stay bilingual and consistent. The description is written last, anchored
   to that name in both languages — otherwise a 4B model translates "hoodie"
   into كارديجان halfway through and the description contradicts its item.

### Cutout completeness

Three things keep garments whole rather than hole-punched:

1. **Occluders stay visible.** Arms, hands, bags, belts and scarves that lie
   inside the garment's convex hull are kept in the cutout. The hull is the
   test, so crossed arms across a torso are included while the same arm
   hanging beside a hip is not. Dedup embeddings are computed from a
   garment-only cutout so pose never changes item identity.
2. **Held objects are recovered geometrically.** A phone or watch carries no
   body-part label (the parser calls it background), but once the hand is in,
   it becomes a fully enclosed hole — any small enclosed hole is filled
   regardless of label.
3. **Pants and Skirt merge into one `bottom`.** ATR routinely splits a single
   lower garment across both labels; emitting two items punched each one's
   region out of the other.

When a gap is made mostly of *other garment* labels, that is a bad parse
rather than an occlusion (low-contrast outfits confuse the parser). Those
garments get a `unreliable_mask` warning and the review sheet flags them
instead of quietly adding a mangled cutout.

Diagnosing a bad cutout:

```bash
.venv/bin/python -m tools.diagnose_holes server/uploads/<photo>.jpeg
```

It reports what the parser actually put in each garment's gaps, which tells
you whether you are looking at occlusion, a label split, or a parse failure.

Refreshing existing closet items after a pipeline change (keeps wear history):

```bash
node tools/refresh_cutouts.mjs server/uploads/<photo>.jpeg
```

That re-runs everything — parse, attributes, labelling — and rewrites the
matched items' cutouts, names and descriptions. After a labelling-only
change, relabel from the cutouts already on disk instead (`--dry` first):

```bash
node tools/relabel_items.mjs --dry
```

## Layout

```
server/            Express API: /api/ingest, /api/commit, /api/items, /api/outfits
                   MongoDB models: Item, WearEvent, Correction
  vlm.js           local VLM labelling: attributes, name, description
client/            React (Vite): upload + staged progress, review sheet (RTL), closet grid
pipeline/serve.py  persistent local inference worker (models stay loaded)
                   POST /ingest, POST /relabel (naming for given attributes)
pipeline/          Python reference pipeline (Phase 1: S0–S3)
  config.py        every tunable threshold (mirrors ts/ingestConfig.ts)
  atr.py           ATR label map + region→garment mapping (the contract)
  s0_validate.py   EXIF orient, blur/size/person gates, pose (MediaPipe Tasks)
  s1_parse.py      SegFormer-ATR parsing + mask post-processing
  s2_garments.py   garment mapping, shoe merge, layer split, pose attributes
  s3_cutout.py     catalog-style white-bg cutout normalization
  run.py           CLI runner → cutouts + debug overlays + IngestResult JSON
ts/                RN-facing shared assets
  types.ts         data contracts (DetectedGarment, IngestResult, WearEvent…)
  taxonomy.ts      attribute taxonomy + formality lookup
  ingestConfig.ts  tunables (keep in sync with pipeline/config.py)
tools/
  export_models.py ONNX export + int8 quantization + text-prompt precompute
  refresh_cutouts.mjs  re-ingest photos, refresh matched items in place
  relabel_items.mjs    relabel items from the cutouts already stored
models/            downloaded model assets (pose_landmarker_lite.task)
LICENSES.md        license verification checklist — required before shipping
```

## Run the reference pipeline

```bash
.venv/bin/python -m pipeline.run path/to/selfie.jpg --out out/
```

Outputs to `out/`: one `*_<category>_<id>.png` cutout per garment, a
`*_overlay.jpg` debug visualization, and `ingest_results.json`.

## Status vs. spec build order (§13)

- [x] Phase 1 — parse + cutout (S0→S3): validated on real photos
- [x] Phase 2 — attributes (S4→S5): color k-means, FashionCLIP axes with
      confidence gate, formality lookup, bilingual templates
- [x] Phase 3 — dedup (S6): same photo re-ingested → all garments match
      (log-wear); different same-color outfit → no false merges
- [x] Phase 4 — review sheet + commit (S7→S8): in the MERN app; RTL verified
- [ ] Phase 5 — telemetry dashboards + 50-selfie eval set (Correction
      events are already stored on commit)

Dev tip: `http://localhost:5173/?demo=/cutouts/demo.json` opens the review
sheet from a saved IngestResult without re-running inference.

## Porting notes for React Native

- The RN app runs the int8 ONNX exports (`tools/export_models.py`) via
  `onnxruntime-react-native`; this Python pipeline defines expected behavior.
- Pose uses the same `pose_landmarker_lite.task` via the MediaPipe Tasks RN/native SDK.
- **Apply EXIF orientation before anything else** — phone photos are stored
  rotated; every stage assumes upright pixels.
- Models download on first use (~40 MB budget), versioned paths, excluded
  from cloud backup (spec §10).
