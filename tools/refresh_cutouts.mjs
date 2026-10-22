// Re-run ingest on source photos and refresh the cutouts and labels of the
// closet items they match. Use after a pipeline change so existing items pick
// up better masks, names and descriptions without losing wear history.
//
// This is the full path — parse, attributes, VLM labelling. To relabel from
// the cutouts you already have (no re-parse), use tools/relabel_items.mjs.
//
//   node tools/refresh_cutouts.mjs server/uploads/<photo> [...]
import fs from 'node:fs';
import path from 'node:path';
import mongoose from '../server/node_modules/mongoose/index.js';

const API = process.env.API ?? 'http://127.0.0.1:5050';

await mongoose.connect('mongodb://127.0.0.1:27017/wardrobe');
const Item = mongoose.model('Item', new mongoose.Schema({}, { strict: false }));

for (const file of process.argv.slice(2)) {
  const fd = new FormData();
  fd.append('photo', new Blob([fs.readFileSync(file)]), path.basename(file));
  const res = await fetch(`${API}/api/ingest`, { method: 'POST', body: fd });
  if (!res.ok) {
    console.log(`${path.basename(file)}: ingest failed (${res.status})`);
    continue;
  }
  const result = await res.json();
  for (const g of result.garments) {
    if (!g.match) {
      console.log(`  ${g.category}: no match — left untouched`);
      continue;
    }
    const a = g.attributes ?? {};
    await Item.updateOne({ _id: g.match.existingItemId }, {
      $set: {
        cutoutUrl: g.cutoutUrl,
        sourceImageUrl: result.sourceImageUrl,
        name: g.generated.name,
        description: g.generated.description,
        type: a.type?.value,
        color: a.color ? {
          key: a.color.name.key, en: a.color.name.en, ar: a.color.name.ar,
          hex: a.color.hex, lab: a.color.lab,
        } : undefined,
        formality: a.formality?.value,
        attributes: {
          sleeve: a.sleeve, length: a.length, bottomKind: a.bottomKind,
          pattern: a.pattern?.value, neckline: a.neckline?.value,
        },
        'quality.warnings': g.quality.warnings,
      },
    });
    console.log(`  ${g.category}: ${g.generated.name.en} ` +
      `(sim ${g.match.similarity.toFixed(3)})` +
      (g.quality.warnings.length ? ` warnings=${g.quality.warnings}` : ''));
  }
}

await mongoose.disconnect();
