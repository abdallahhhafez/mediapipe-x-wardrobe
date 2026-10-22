"""S4 (formality) — deterministic lookup + modifiers, no model (spec §4 S4)."""

FORMALITY_BASE = {
    "t-shirt": "casual", "tank_top": "casual", "jersey": "sport",
    "polo": "smart_casual", "shirt": "smart_casual", "sweater": "smart_casual",
    "sweatshirt": "casual", "hoodie": "casual", "blazer": "formal",
    "suit_jacket": "formal", "jeans": "casual", "joggers": "casual",
    "shorts": "casual", "chinos": "smart_casual", "trousers": "formal",
    "cargo_pants": "casual", "leggings": "sport", "skirt": "smart_casual",
    "jacket": "smart_casual", "denim_jacket": "casual", "bomber": "casual",
    "coat": "smart_casual", "puffer": "casual", "cardigan": "smart_casual",
    "windbreaker": "sport", "sneakers": "casual", "boots": "smart_casual",
    "sandals": "casual", "derby": "formal", "formal_shoes": "formal",
    "loafers": "smart_casual", "dress": "smart_casual", "jumpsuit": "casual",
    "abaya": "smart_casual", "kaftan": "smart_casual",
}

LEVELS = ["formal", "smart_casual", "casual", "sport"]  # downgrade moves right


def formality(garment_type: str, pattern: str = None, distressed: bool = False) -> str:
    base = FORMALITY_BASE.get(garment_type, "casual")
    i = LEVELS.index(base)
    if pattern == "graphic":
        i += 1
    if pattern == "plaid" and garment_type != "shirt":
        i += 1
    if distressed:
        i += 1
    return LEVELS[min(i, len(LEVELS) - 1)]
