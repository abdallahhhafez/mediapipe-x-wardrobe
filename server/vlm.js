// Local vision-LLM labelling: attributes, name and description for one
// garment cutout (gemma3:4b via Ollama, multimodal + pipeline/serve.py).
//
// FashionCLIP scores a cutout against short prompts and, on real mirror
// selfies, confuses a striped polo with a tank top often enough that the
// closet reads wrong. The same cutout shown to a small local VLM under a
// closed vocabulary gets it right, so the VLM is the labeller and CLIP's
// answer is kept beside it (telemetry + fallback when Ollama is absent).
//
// Zero-cost local inference; every call degrades to the pipeline's own
// answer rather than failing an ingest.
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const OLLAMA_URL = process.env.OLLAMA_URL ?? 'http://127.0.0.1:11434';
const WORKER_URL = process.env.WORKER_URL ?? 'http://127.0.0.1:5055';
const MODEL = process.env.DESCRIBE_MODEL ?? 'gemma3:4b';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PALETTE = JSON.parse(fs.readFileSync(
  path.join(__dirname, '..', 'assets', 'color_palette.json'), 'utf8')).colors;
const COLORS = PALETTE.map(c => c.key);

// keep in sync with ts/taxonomy.ts and pipeline/s4_clip.py
const TYPES = {
  top: ['t-shirt', 'polo', 'shirt', 'hoodie', 'sweater', 'sweatshirt', 'tank_top', 'jersey'],
  bottom: ['jeans', 'joggers', 'chinos', 'trousers', 'shorts', 'cargo_pants', 'leggings', 'skirt'],
  outerwear: ['jacket', 'denim_jacket', 'bomber', 'blazer', 'coat', 'puffer', 'cardigan', 'windbreaker'],
  shoes: ['sneakers', 'boots', 'sandals', 'formal_shoes', 'loafers'],
  dress: ['dress', 'jumpsuit', 'abaya', 'kaftan'],
};
const PATTERNS = ['solid', 'striped', 'graphic', 'plaid', 'floral', 'colorblock'];
const SLEEVES = ['sleeveless', 'short', 'three_quarter', 'long'];
const NECKLINES = ['round_neck', 'v_neck', 'collared', 'crew_neck', 'turtleneck', 'hooded'];

// pose geometry is measured, not guessed — it prunes types the VLM cannot
// then hallucinate (same idea as SLEEVE_EXCLUDES in pipeline/s4_clip.py)
const LENGTH_EXCLUDES = {
  full_length: ['shorts'],
  shorts: ['trousers', 'jeans', 'chinos', 'joggers', 'leggings', 'cargo_pants'],
};

// ...and the cutout is cropped to the garment, so where it fell on the body
// is something only the pose knows. Tell the model.
const LENGTH_HINT = {
  shorts: 'On the wearer it ended above the knee.',
  cropped: 'On the wearer it ended between the knee and the calf.',
  full_length: 'On the wearer it reached the ankle.',
};

const HAS_SLEEVES = new Set(['top', 'outerwear', 'dress']);

async function chat({ image, prompt, format, temperature, timeout }) {
  const res = await fetch(`${OLLAMA_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: MODEL,
      stream: false,
      format,
      options: { temperature },
      messages: [{ role: 'user', content: prompt, images: [image] }],
    }),
    signal: AbortSignal.timeout(timeout),
  });
  if (!res.ok) throw new Error(`ollama ${res.status}`);
  const data = await res.json();
  return JSON.parse(data.message?.content ?? '{}');
}

export async function ollamaAvailable() {
  try {
    const res = await fetch(`${OLLAMA_URL}/api/tags`, { signal: AbortSignal.timeout(1500) });
    if (!res.ok) return false;
    const { models } = await res.json();
    return models?.some(m => m.name === MODEL || m.name.startsWith(MODEL + ':'));
  } catch {
    return false;
  }
}

/**
 * Read the attributes of one garment off its cutout. `length` (pose) and
 * `bottomKind` (parser) are measured facts; they narrow the vocabulary.
 * Returns null for categories with no vocabulary (accessories).
 */
export async function classifyGarment(cutoutPath, { category, length, bottomKind } = {}) {
  // the parser already told Pants from Skirt on the full body (s2_garments);
  // a cropped cutout of a wide leg cannot
  const excluded = [...(LENGTH_EXCLUDES[length] ?? []),
                    ...(bottomKind === 'pants' ? ['skirt'] : [])];
  const types = (TYPES[category] ?? []).filter(t => !excluded.includes(t));
  if (types.length === 0) return null;

  const properties = {
    type: { type: 'string', enum: types },
    color: { type: 'string', enum: COLORS },
    pattern: { type: 'string', enum: PATTERNS },
  };
  if (HAS_SLEEVES.has(category)) {
    properties.sleeve = { type: 'string', enum: SLEEVES };
    properties.neckline = { type: 'string', enum: NECKLINES };
  }

  const attrs = await chat({
    image: fs.readFileSync(cutoutPath).toString('base64'),
    prompt:
      `This is a product cutout of a single ${category} garment on a white ` +
      `background. Identify what the garment actually is. Judge only the ` +
      `garment itself: ignore the white background and any hand, arm or ` +
      `body part still in the frame. Name the color of the garment fabric ` +
      `as it would be described in a shop, not the shade the lighting gives ` +
      `it. ` + (LENGTH_HINT[length] ?? '') +
      ` Pick the closest option for every field.`,
    format: { type: 'object', properties, required: Object.keys(properties) },
    temperature: 0,
    timeout: 60000,
  });

  if (!types.includes(attrs.type) || !COLORS.includes(attrs.color)) {
    throw new Error('bad vlm labels');
  }
  return attrs;
}

/**
 * Bilingual product-style description of a garment already identified.
 * `name` is the generated bilingual name: handing the model the Arabic
 * wording too stops a 4B translating "hoodie" into كارديجان halfway
 * through, which is how a description ends up contradicting its own item.
 */
export async function describeGarment(cutoutPath, { name, ...meta }) {
  const known = Object.entries(meta)
    .filter(([, v]) => v && v !== 'unknown')
    .map(([k, v]) => `${k}: ${String(v).replace(/_/g, ' ')}`)
    .join(', ');

  const parsed = await chat({
    image: fs.readFileSync(cutoutPath).toString('base64'),
    prompt:
      `This is a cutout of one garment from a personal wardrobe app. ` +
      `It has already been identified as — ${known}. Keep to that ` +
      `identification and do not contradict it` +
      (name ? `: call it "${name.en}" in English and "${name.ar}" in ` +
              `Arabic, using those exact words for the garment. ` : `. `) +
      `Write a short, natural ` +
      `product-style description of THIS garment: 1-2 sentences, warm and ` +
      `simple, mentioning what it pairs well with or what occasions it ` +
      `suits. Write sentences — do not open by restating the name, and do ` +
      `not mention the background, the cutout, image quality, or ` +
      `any person/body parts. Return JSON with "en" (English) and "ar" (the ` +
      `same description in natural Modern Standard Arabic, not a literal ` +
      `translation).`,
    format: {
      type: 'object',
      properties: { en: { type: 'string' }, ar: { type: 'string' } },
      required: ['en', 'ar'],
    },
    temperature: 0.4,
    timeout: 60000,
  });
  if (!parsed.en || !parsed.ar) throw new Error('bad llm output');
  return { en: parsed.en.trim(), ar: parsed.ar.trim() };
}

/** Bilingual name + formality for the attributes, from the pipeline's
 *  i18n tables (pipeline/serve.py POST /relabel) — no model involved. */
async function relabelWithWorker(payload) {
  const res = await fetch(`${WORKER_URL}/relabel`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`worker ${res.status}`);
  return res.json();
}

/**
 * Label one garment in place: VLM attributes overwrite CLIP's, the worker
 * renames it, and the description is rewritten from the result. CLIP's own
 * answer stays under `attributes.*.clip` so review-sheet corrections can
 * still be attributed to the model that made them.
 * Returns false when the category has no vocabulary to label against.
 */
export async function labelGarment(g, cutoutPath) {
  const attrs = await classifyGarment(cutoutPath, {
    category: g.category,
    length: g.attributes?.length,
    bottomKind: g.attributes?.bottomKind,
  });
  if (!attrs) return false;

  const a = g.attributes ?? (g.attributes = {});
  a.type = { value: attrs.type, source: 'vlm', clip: a.type ?? null };
  a.pattern = { value: attrs.pattern, source: 'vlm', clip: a.pattern ?? null };
  if (attrs.neckline) {
    a.neckline = { value: attrs.neckline, source: 'vlm', clip: a.neckline ?? null };
  }
  if (attrs.sleeve) {
    // pose measures the sleeve through whatever the arms are doing; the
    // VLM just looks at the garment. Keep both.
    if (a.sleeve) a.sleevePose = a.sleeve;
    a.sleeve = attrs.sleeve;
  }

  const named = await relabelWithWorker({
    category: g.category, type: attrs.type, pattern: attrs.pattern,
    sleeve: attrs.sleeve, neckline: attrs.neckline,
    color: attrs.color, lab: a.color?.lab, tempId: g.tempId,
  });
  a.color = { ...a.color, name: named.color.name, hex: named.color.hex,
              measuredName: a.color?.name ?? null };
  a.formality = { value: named.formality };
  g.generated = { ...g.generated, name: named.name,
                  description: named.description, labelSource: 'vlm' };

  // the description is written last so it can only agree with the name
  g.generated.description = await describeGarment(cutoutPath, {
    name: named.name,
    type: attrs.type, color: named.color.name.en, pattern: attrs.pattern,
    sleeve: attrs.sleeve, neckline: attrs.neckline,
    formality: named.formality,
  });
  g.generated.descriptionSource = 'llm';
  return true;
}
