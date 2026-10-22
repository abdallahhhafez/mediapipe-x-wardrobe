// Re-label closet items from their stored cutouts with the local VLM
// (server/vlm.js). Use after a labelling change: names, descriptions,
// type/pattern/formality are rewritten in place, wear history is untouched.
//
//   node tools/relabel_items.mjs            # every item
//   node tools/relabel_items.mjs --dry      # show what would change
//   node tools/relabel_items.mjs <itemId>…  # just these
//
// Needs Ollama (gemma3:4b) and the inference worker on :5055 — i.e. the
// API server running, or `.venv/bin/python -m pipeline.serve`.
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import mongoose from '../server/node_modules/mongoose/index.js';
import { labelGarment, ollamaAvailable } from '../server/vlm.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SERVER = path.join(__dirname, '..', 'server');

const args = process.argv.slice(2);
const dry = args.includes('--dry');
const ids = args.filter(a => !a.startsWith('--'));

if (!await ollamaAvailable()) {
  console.error('ollama/gemma3:4b unavailable — nothing to relabel with');
  process.exit(1);
}

await mongoose.connect(process.env.MONGO_URL ?? 'mongodb://127.0.0.1:27017/wardrobe');
const Item = mongoose.model('Item', new mongoose.Schema({}, { strict: false }));

const items = await Item.find(ids.length ? { _id: { $in: ids } } : {}).lean();
console.log(`${items.length} item(s)${dry ? ' (dry run)' : ''}`);

for (const item of items) {
  if (!item.cutoutUrl) {
    console.log(`  ${item.name?.en}: no cutout — skipped`);
    continue;
  }
  // the item's stored shape -> the shape the pipeline hands to the labeller
  const g = {
    tempId: String(item._id),
    category: item.category,
    attributes: {
      ...item.attributes,
      color: item.color
        ? { name: { en: item.color.en, ar: item.color.ar, key: item.color.key },
            hex: item.color.hex, lab: item.color.lab }
        : undefined,
    },
    generated: { name: item.name, description: item.description },
  };

  try {
    const labelled = await labelGarment(g, path.join(SERVER, item.cutoutUrl));
    if (!labelled) {
      console.log(`  ${item.name?.en}: no vocabulary for ${item.category} — skipped`);
      continue;
    }
  } catch (e) {
    console.log(`  ${item.name?.en}: failed (${e.message}) — left untouched`);
    continue;
  }

  const a = g.attributes;
  const update = {
    name: g.generated.name,
    description: g.generated.description,
    type: a.type.value,
    color: { key: a.color.name.key, en: a.color.name.en, ar: a.color.name.ar,
             hex: a.color.hex, lab: a.color.lab },
    formality: a.formality.value,
    attributes: {
      sleeve: a.sleeve, length: a.length, bottomKind: a.bottomKind,
      pattern: a.pattern.value, neckline: a.neckline?.value,
    },
  };
  console.log(`  ${item.name?.en} [${item.type ?? '—'}/${item.color?.key}]` +
    ` -> ${update.name.en} [${update.type}/${update.color.key}]`);
  if (!dry) await Item.updateOne({ _id: item._id }, { $set: update });
}

await mongoose.disconnect();
