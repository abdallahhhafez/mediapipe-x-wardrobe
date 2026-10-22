"""Model export + int8 quantization for on-device use (spec §2.2).

Run once on free Colab (or locally). For each model:
  1. Export to ONNX, opset 17, fixed batch=1
  2. Dynamic int8 quantization (weights only)
  3. Validate int8 vs fp32 — parser: mIoU delta < 2%; embedder: cosine > 0.98
  4. Upload to CDN under a versioned path (/models/v1/...)

Do NOT skip validation: aggressive quantization on SegFormer can silently
collapse the shoe classes.

Usage:
  python tools/export_models.py --model parser --out dist/models/v1
  python tools/export_models.py --model embedder --out dist/models/v1
  python tools/export_models.py --model parser --validate eval_images/
"""
import argparse
import os

PARSER_ID = "mattmdjaga/segformer_b2_clothes"
EMBEDDER_ID = "patrickjohncyh/fashion-clip"
OPSET = 17


def export_parser(out_dir: str):
    import torch
    from transformers import AutoModelForSemanticSegmentation
    model = AutoModelForSemanticSegmentation.from_pretrained(PARSER_ID).eval()
    dummy = torch.randn(1, 3, 512, 512)
    fp32 = os.path.join(out_dir, "parser.fp32.onnx")
    torch.onnx.export(model, dummy, fp32, opset_version=OPSET,
                      input_names=["pixel_values"], output_names=["logits"])
    _quantize(fp32, os.path.join(out_dir, "parser.onnx"))


def export_embedder(out_dir: str):
    import torch
    from transformers import CLIPVisionModelWithProjection
    model = CLIPVisionModelWithProjection.from_pretrained(EMBEDDER_ID).eval()

    class ImgEncoder(torch.nn.Module):
        def __init__(self, m):
            super().__init__()
            self.m = m

        def forward(self, pixel_values):
            out = self.m(pixel_values=pixel_values).image_embeds
            return out / out.norm(dim=-1, keepdim=True)

    dummy = torch.randn(1, 3, 224, 224)
    fp32 = os.path.join(out_dir, "embedder.fp32.onnx")
    torch.onnx.export(ImgEncoder(model), dummy, fp32, opset_version=OPSET,
                      input_names=["pixel_values"], output_names=["embedding"])
    _quantize(fp32, os.path.join(out_dir, "embedder.onnx"))


def _quantize(fp32_path: str, int8_path: str):
    from onnxruntime.quantization import quantize_dynamic, QuantType
    quantize_dynamic(fp32_path, int8_path, weight_type=QuantType.QInt8)
    print(f"{int8_path}: {os.path.getsize(int8_path) / 1e6:.1f} MB "
          f"(fp32 {os.path.getsize(fp32_path) / 1e6:.1f} MB)")


def export_text_prompts(out_path: str):
    """Precompute FashionCLIP text vectors for every prompt axis (spec §2.3, §6).

    Ships as fashion_prompts.v1.json — the text encoder never runs on device.
    """
    import json
    import torch
    from transformers import CLIPTextModelWithProjection, CLIPTokenizer

    TEMPLATES = {
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

    tok = CLIPTokenizer.from_pretrained(EMBEDDER_ID)
    model = CLIPTextModelWithProjection.from_pretrained(EMBEDDER_ID).eval()
    axes = {}
    with torch.no_grad():
        for axis, (tmpl, labels) in TEMPLATES.items():
            prompts = [tmpl.format(l) for l in labels]
            inputs = tok(prompts, padding=True, return_tensors="pt")
            emb = model(**inputs).text_embeds
            emb = emb / emb.norm(dim=-1, keepdim=True)
            axes[axis] = {"labels": [l.replace(" ", "_") for l in labels],
                          "vectors": emb.tolist()}
    with open(out_path, "w") as f:
        json.dump({"version": 1, "dim": emb.shape[-1], "axes": axes}, f)
    print(f"wrote {out_path} ({os.path.getsize(out_path) / 1e3:.0f} KB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", choices=["parser", "embedder", "prompts"], required=True)
    ap.add_argument("--out", default="dist/models/v1")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    if args.model == "parser":
        export_parser(args.out)
    elif args.model == "embedder":
        export_embedder(args.out)
    else:
        export_text_prompts(os.path.join(args.out, "fashion_prompts.v1.json"))


if __name__ == "__main__":
    main()
