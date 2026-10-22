// Wardrobe MERN backend. The ingest endpoint shells out to the local Python
// reference pipeline (zero-cost local inference); Mongo stores closet items,
// wear events, and review-sheet corrections.
import express from 'express';
import cors from 'cors';
import multer from 'multer';
import mongoose from 'mongoose';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
import crypto from 'node:crypto';
import { Item, WearEvent, Correction } from './models.js';
import { labelGarment, ollamaAvailable } from './vlm.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const PY = path.join(ROOT, '.venv', 'bin', 'python');
const UPLOADS = path.join(__dirname, 'uploads');
const CUTOUTS = path.join(__dirname, 'cutouts');
for (const d of [UPLOADS, CUTOUTS]) fs.mkdirSync(d, { recursive: true });

const MONGO_URL = process.env.MONGO_URL ?? 'mongodb://127.0.0.1:27017/wardrobe';
await mongoose.connect(MONGO_URL);
console.log('mongo connected:', MONGO_URL);

const app = express();
app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use('/cutouts', express.static(CUTOUTS));
app.use('/uploads', express.static(UPLOADS));

const upload = multer({ dest: UPLOADS, limits: { fileSize: 25 * 1024 * 1024 } });

// ---- persistent inference worker (models stay loaded between requests) ----
const WORKER_URL = 'http://127.0.0.1:5055';
let workerProc = null;
function startWorker() {
  workerProc = spawn(PY, ['-m', 'pipeline.serve'], { cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'] });
  workerProc.stdout.on('data', d => process.stdout.write(`[worker] ${d}`));
  workerProc.stderr.on('data', () => {});
  workerProc.on('exit', code => {
    console.error(`inference worker exited (${code}), restarting in 3s`);
    setTimeout(startWorker, 3000);
  });
}
startWorker();
process.on('exit', () => workerProc?.kill());

async function runPipeline(imgPath, outDir, closet) {
  // warm path: persistent worker
  try {
    const res = await fetch(`${WORKER_URL}/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image: imgPath, out: outDir, closet }),
    });
    if (res.ok) return res.json();
    throw new Error(`worker ${res.status}`);
  } catch (err) {
    if (err?.message?.startsWith('worker')) throw err;
    // cold fallback: worker not up yet — spawn a one-shot run
    return new Promise((resolve, reject) => {
      const closetPath = path.join(UPLOADS, `closet-${crypto.randomUUID()}.json`);
      fs.writeFileSync(closetPath, JSON.stringify(closet));
      const args = ['-m', 'pipeline.run', imgPath, '--out', outDir,
        '--clip', '--closet', closetPath, '--json-only'];
      const proc = spawn(PY, args, { cwd: ROOT });
      let stdout = '', stderr = '';
      proc.stdout.on('data', d => { stdout += d; });
      proc.stderr.on('data', d => { stderr += d; });
      proc.on('close', code => {
        fs.rmSync(closetPath, { force: true });
        if (code !== 0) return reject(new Error(stderr.slice(-800)));
        try { resolve(JSON.parse(stdout.split('@@RESULT@@')[1])[0]); }
        catch (e) { reject(e); }
      });
    });
  }
}

// ---- ingest: photo -> pipeline -> IngestResult (nothing committed yet) ----
app.post('/api/ingest', upload.single('photo'), async (req, res) => {
  if (!req.file) return res.status(400).json({ error: 'photo file required' });

  // give the upload its original extension so PIL recognizes it
  const ext = path.extname(req.file.originalname || '.jpg') || '.jpg';
  const imgPath = req.file.path + ext;
  fs.renameSync(req.file.path, imgPath);

  // pass the existing closet for on-pipeline dedup
  const closetDocs = await Item.find(
    { embedding: { $exists: true, $ne: [] } },
    { category: 1, embedding: 1, 'color.lab': 1 },
  ).lean();
  const closet = closetDocs.map(i => ({
    id: String(i._id), category: i.category,
    embedding: i.embedding, colorLab: i.color?.lab ?? [50, 0, 0],
  }));

  const outDir = path.join(CUTOUTS, crypto.randomUUID());
  fs.mkdirSync(outDir, { recursive: true });

  try {
    const result = await runPipeline(imgPath, outDir, closet);

    // attributes, name and description from the local multimodal LLM
    // (gemma3:4b via Ollama); CLIP labels + templates stay as the fallback
    if (await ollamaAvailable()) {
      for (const g of result.garments) {
        if (g.category === 'accessory') continue;
        try {
          await labelGarment(g, g.cutoutUri);
        } catch (e) {
          console.error('vlm fallback (clip labels):', e.message);
        }
      }
    }

    // rewrite local cutout paths to served URLs
    for (const g of result.garments) {
      g.cutoutUrl = '/cutouts/' + path.relative(CUTOUTS, g.cutoutUri);
      delete g.cutoutUri;
    }
    result.overlayUrl = result.overlay
      ? '/cutouts/' + path.relative(CUTOUTS, result.overlay) : null;
    delete result.overlay;
    result.sourceImageUrl = '/uploads/' + path.basename(imgPath);
    delete result.sourceImageUri;
    res.json(result);
  } catch (e) {
    console.error('pipeline failed:', e.message);
    res.status(500).json({ error: 'pipeline_failed', detail: e.message });
  }
});

// ---- commit: confirmed garments -> items + wear events, transactional ----
app.post('/api/commit', async (req, res) => {
  const { garments, wornAt } = req.body ?? {};
  if (!Array.isArray(garments) || garments.length === 0) {
    return res.status(400).json({ error: 'garments required' });
  }
  const outfitId = crypto.randomUUID();
  const when = wornAt ? new Date(wornAt) : new Date();

  // standalone-Mongo-friendly "transaction": build everything, insert,
  // roll back inserts on failure
  const createdItems = [];
  const createdWears = [];
  try {
    for (const g of garments) {
      if (g.action === 'log_wear' && g.existingItemId) {
        const w = await WearEvent.create({
          itemId: g.existingItemId, wornAt: when,
          source: 'selfie_ingest', outfitId,
        });
        createdWears.push(w);
      } else if (g.action === 'create') {
        const item = await Item.create({
          category: g.category,
          name: g.name, description: g.description,
          type: g.type, color: g.color, formality: g.formality,
          attributes: g.attributes ?? {},
          cutoutUrl: g.cutoutUrl, sourceImageUrl: g.sourceImageUrl,
          source: 'selfie',
          embedding: g.embedding ?? undefined,
        });
        createdItems.push(item);
        const w = await WearEvent.create({
          itemId: item._id, wornAt: when, source: 'selfie_ingest', outfitId,
        });
        createdWears.push(w);
      }
      // corrections logged for future fine-tuning (spec §11)
      for (const c of g.corrections ?? []) await Correction.create({ ...c });
    }
    res.json({
      outfitId,
      createdItems: createdItems.length,
      loggedWears: createdWears.length,
    });
  } catch (e) {
    await Item.deleteMany({ _id: { $in: createdItems.map(i => i._id) } });
    await WearEvent.deleteMany({ _id: { $in: createdWears.map(w => w._id) } });
    console.error('commit rolled back:', e);
    res.status(500).json({ error: 'commit_failed' });
  }
});

// ---- closet ----
app.get('/api/items', async (_req, res) => {
  const items = await Item.find({}, { embedding: 0 }).sort({ createdAt: -1 }).lean();
  const counts = await WearEvent.aggregate([
    { $group: { _id: '$itemId', n: { $sum: 1 }, last: { $max: '$wornAt' } } },
  ]);
  const byId = Object.fromEntries(counts.map(c => [String(c._id), c]));
  res.json(items.map(i => ({
    ...i,
    wearCount: byId[String(i._id)]?.n ?? 0,
    lastWorn: byId[String(i._id)]?.last ?? null,
  })));
});

app.get('/api/items/:id', async (req, res) => {
  const item = await Item.findById(req.params.id, { embedding: 0 }).lean();
  if (!item) return res.status(404).json({ error: 'not_found' });
  const wears = await WearEvent.find({ itemId: item._id }).sort({ wornAt: -1 }).lean();
  res.json({ ...item, wears });
});

app.delete('/api/items/:id', async (req, res) => {
  await Item.deleteOne({ _id: req.params.id });
  await WearEvent.deleteMany({ itemId: req.params.id });
  res.json({ ok: true });
});

app.get('/api/outfits', async (_req, res) => {
  const outfits = await WearEvent.aggregate([
    { $match: { outfitId: { $ne: null } } },
    { $group: { _id: '$outfitId', wornAt: { $max: '$wornAt' }, items: { $push: '$itemId' } } },
    { $sort: { wornAt: -1 } },
  ]);
  res.json(outfits);
});

const PORT = process.env.PORT ?? 5050;
app.listen(PORT, () => console.log(`wardrobe server on :${PORT}`));
