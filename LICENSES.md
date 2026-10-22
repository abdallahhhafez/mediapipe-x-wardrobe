# Model licenses — MUST be verified before shipping (spec §2.4)

| Model | Source | License (verify on model card at ship time) | Commercial use | Verified by / date |
|---|---|---|---|---|
| SegFormer B2 clothes (ATR) | `mattmdjaga/segformer_b2_clothes` | MIT (per HF model card — re-check) | ☐ pending | — |
| MediaPipe Pose Landmarker (lite) | Google AI Edge | Apache 2.0 | ☐ pending | — |
| FashionCLIP | `patrickjohncyh/fashion-clip` | MIT (per HF model card — re-check; base CLIP weights from OpenAI, MIT) | ☐ pending | — |

Notes:
- **MobileCLIP (Apple)** is NOT used — its ML research license may restrict
  commercial use. If FashionCLIP is ever replaced, use OpenCLIP ViT-B/32
  (laion2b) — permissive, slightly worse fashion vocabulary.
- Do not ship until every row is checked and dated.
