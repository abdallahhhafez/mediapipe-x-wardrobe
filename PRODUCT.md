# PRODUCT.md

## What this is
A personal wardrobe app ("outfit-ingest"). The user uploads a full-body
mirror selfie; on-device/local ML detects each garment, produces a white-
background catalog cutout, auto-fills attributes (type, color, formality,
bilingual name/description), and detects whether the garment already exists
in the closet — creating an item or logging a wear event. Nothing commits
until the user confirms in a review sheet.

## Users
One person cataloguing and tracking their own clothes, on their phone or
laptop, casually — usually right after taking a mirror selfie at home.
Bilingual: Arabic (RTL) and English are equal first-class locales.

## Register
product — the design serves the workflow (upload → review → closet).
The garment cutouts (white-background PNGs) are the hero content; the UI
stays quiet around them.

## Surfaces
- Upload view: photo picker + staged progress ("Finding your outfit" →
  "Identifying items" → "Checking your closet"), privacy note (photos never
  leave the device/machine).
- Review sheet: one editable card per detected garment; unknown fields are
  blank and highlighted, matched items show "Already in your closet — log a
  wear?"; accessories default unselected. CTA: "Add N items · Log M wears".
- Closet grid: cutout cards with color chip, wear count, selfie-source
  badge; item detail with wear history.

## Constraints
- All inference is local (Python pipeline via the Express API). Zero
  per-image cost. Design must surface the privacy angle.
- RTL correctness in Arabic is a ship gate, not a nice-to-have.
- Expected model accuracy is ~70–80% of fields; the UI is built around
  correction, not around trusting the model.

## Stack
MERN: MongoDB (closet items, wear events, corrections), Express API
(server/), React + Vite client (client/), Python reference pipeline
(pipeline/) as the local inference worker.
