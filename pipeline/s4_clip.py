"""S4 (CLIP axes) — FashionCLIP attribute classification + dedup embedding.

The image encoder runs ONCE per garment on the cutout; the single embedding
is reused for every axis and for dedup (spec §4 S4). Text vectors come from
the precomputed prompt asset (fashion_prompts.v1.json) — at runtime on
device the text encoder never executes. Here we compute them lazily with
the same templates for parity.

Confidence gate: top-1 softmax < clipMinConfidence, or margin to top-2 <
clipMinMargin => 'unknown'. Do not guess.
"""
import numpy as np

from .config import INGEST_CONFIG as CFG

MODEL_ID = "patrickjohncyh/fashion-clip"
_MODEL = None
_PROCESSOR = None

# axis -> (prompt template, labels). Keep in sync with tools/export_models.py.
PROMPTS = {
    "top_type":       ("a photo of a {}, product photo on white background",
                       ["t-shirt", "polo", "shirt", "hoodie", "sweater", "tank top", "jersey", "sweatshirt"]),
    "bottom_type":    ("a photo of a pair of {}, product photo on white background",
                       ["jeans", "joggers", "chinos", "trousers", "shorts", "cargo pants", "leggings"]),
    "outerwear_type": ("a photo of a {}, an outer layer of clothing",
                       ["jacket", "denim jacket", "bomber jacket", "blazer", "coat", "puffer jacket", "cardigan", "windbreaker"]),
    "shoes_type":     ("a photo of a pair of {}",
                       ["sneakers", "boots", "sandals", "formal shoes", "loafers"]),
    "dress_type":     ("a photo of a {}, product photo on white background",
                       ["dress", "jumpsuit", "abaya", "kaftan"]),
    "neckline":       ("a photo of a shirt with a {}",
                       ["round neck", "v neck", "collar", "crew neck", "turtleneck", "hood"]),
    "pattern":        ("a photo of a garment with a {} pattern",
                       ["solid plain", "striped", "graphic print", "plaid", "floral", "colorblock"]),
}

# prompt wording != taxonomy value (ts/taxonomy.ts); map back after scoring
VALUE_MAP = {
    "solid plain": "solid", "graphic print": "graphic",
    "collar": "collared", "hood": "hooded", "v neck": "v_neck",
}

CATEGORY_TYPE_AXIS = {"top": "top_type", "bottom": "bottom_type",
                      "outerwear": "outerwear_type", "shoes": "shoes_type",
                      "dress": "dress_type"}

# sleeve constraints from pose prune impossible top types (spec S2: the
# single biggest accuracy win in the pipeline)
SLEEVE_EXCLUDES = {
    "short": {"hoodie", "sweater", "sweatshirt"},
    "sleeveless": {"hoodie", "sweater", "sweatshirt", "shirt", "polo", "t-shirt"},
}

_TEXT_CACHE = {}


def _lazy():
    global _MODEL, _PROCESSOR
    if _MODEL is None:
        from transformers import CLIPModel, CLIPProcessor
        _MODEL = CLIPModel.from_pretrained(MODEL_ID).eval()
        _PROCESSOR = CLIPProcessor.from_pretrained(MODEL_ID)
    return _MODEL, _PROCESSOR


def _as_tensor(out, model, kind):
    """transformers v5 returns an output object from get_*_features; v4 a tensor."""
    import torch
    if isinstance(out, torch.Tensor):
        return out
    for attr in ("image_embeds", "text_embeds"):
        if getattr(out, attr, None) is not None:
            return getattr(out, attr)
    proj = model.visual_projection if kind == "image" else model.text_projection
    p = out.pooler_output
    # some versions return already-projected features in pooler_output
    return proj(p) if p.shape[-1] == proj.in_features else p


def _logit_scale() -> float:
    model, _ = _lazy()
    try:
        return float(model.logit_scale.exp())
    except Exception:
        return 100.0


def _text_vectors(axis: str) -> np.ndarray:
    import torch
    if axis not in _TEXT_CACHE:
        model, proc = _lazy()
        tmpl, labels = PROMPTS[axis]
        inputs = proc(text=[tmpl.format(l) for l in labels],
                      return_tensors="pt", padding=True)
        with torch.no_grad():
            t = _as_tensor(model.get_text_features(**inputs), model, "text")
        t = t / t.norm(dim=-1, keepdim=True)
        _TEXT_CACHE[axis] = t.numpy()
    return _TEXT_CACHE[axis]


def embed_image(cutout_rgb: np.ndarray) -> np.ndarray:
    import torch
    model, proc = _lazy()
    inputs = proc(images=cutout_rgb, return_tensors="pt")
    with torch.no_grad():
        e = _as_tensor(model.get_image_features(**inputs), model, "image")
    e = e / e.norm(dim=-1, keepdim=True)
    return e[0].numpy().astype(np.float32)


def classify_axis(embedding: np.ndarray, axis: str,
                  exclude: set = frozenset()) -> dict:
    tmpl, labels = PROMPTS[axis]
    vecs = _text_vectors(axis)
    keep = [i for i, l in enumerate(labels) if l not in exclude]
    sims = vecs[keep] @ embedding
    # softmax at CLIP's learned logit scale (exp(logit_scale) ≈ 100),
    # over this category's candidate set only
    z = np.exp((sims - sims.max()) * _logit_scale())
    p = z / z.sum()
    order = np.argsort(-p)
    top1, top2 = p[order[0]], p[order[1]] if len(p) > 1 else 0.0
    label = labels[keep[order[0]]]
    value = VALUE_MAP.get(label, label.replace(" ", "_"))
    if top1 < CFG["clipMinConfidence"] or (top1 - top2) < CFG["clipMinMargin"]:
        return {"value": "unknown", "confidence": float(top1)}
    return {"value": value, "confidence": float(top1)}


def classify_garment(embedding: np.ndarray, category: str, sleeve: str = None) -> dict:
    """Return {type, pattern, neckline?} attribute dicts for one garment."""
    out = {}
    axis = CATEGORY_TYPE_AXIS.get(category)
    if axis:
        exclude = SLEEVE_EXCLUDES.get(sleeve, set()) if category == "top" else set()
        # never exclude everything
        if len(exclude) >= len(PROMPTS[axis][1]) - 1:
            exclude = set()
        out["type"] = classify_axis(embedding, axis, exclude)
    out["pattern"] = classify_axis(embedding, "pattern")
    if category == "top":
        out["neckline"] = classify_axis(embedding, "neckline")
    return out
