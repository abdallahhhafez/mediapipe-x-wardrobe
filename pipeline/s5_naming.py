"""S5 — template-based bilingual name & description generation (spec §4 S5).

No LLM call. Arabic puts the noun first with adjectives after — never reuse
the English word order.
"""
import hashlib

TYPE_I18N = {
    "t-shirt": {"en": "t-shirt", "ar": "تيشيرت"},
    "polo": {"en": "polo shirt", "ar": "بولو"},
    "shirt": {"en": "shirt", "ar": "قميص"},
    "hoodie": {"en": "hoodie", "ar": "هودي"},
    "sweater": {"en": "sweater", "ar": "سويتر"},
    "sweatshirt": {"en": "sweatshirt", "ar": "سويت شيرت"},
    "tank_top": {"en": "tank top", "ar": "تانك توب"},
    "jersey": {"en": "jersey", "ar": "جيرسي"},
    "jeans": {"en": "jeans", "ar": "جينز"},
    "joggers": {"en": "joggers", "ar": "بنطلون رياضي"},
    "chinos": {"en": "chinos", "ar": "بنطلون تشينو"},
    "trousers": {"en": "trousers", "ar": "بنطلون كلاسيك"},
    "shorts": {"en": "shorts", "ar": "شورت"},
    "cargo_pants": {"en": "cargo pants", "ar": "بنطلون كارجو"},
    "leggings": {"en": "leggings", "ar": "ليجنز"},
    "skirt": {"en": "skirt", "ar": "جيبة"},
    "jacket": {"en": "jacket", "ar": "جاكيت"},
    "denim_jacket": {"en": "denim jacket", "ar": "جاكيت جينز"},
    "bomber": {"en": "bomber jacket", "ar": "جاكيت بومبر"},
    "blazer": {"en": "blazer", "ar": "بليزر"},
    "coat": {"en": "coat", "ar": "بالطو"},
    "puffer": {"en": "puffer jacket", "ar": "جاكيت منفوخ"},
    "cardigan": {"en": "cardigan", "ar": "كارديجان"},
    "windbreaker": {"en": "windbreaker", "ar": "جاكيت واقي من الرياح"},
    "sneakers": {"en": "sneakers", "ar": "سنيكرز"},
    "boots": {"en": "boots", "ar": "بوت"},
    "sandals": {"en": "sandals", "ar": "صندل"},
    "formal_shoes": {"en": "formal shoes", "ar": "حذاء كلاسيك"},
    "loafers": {"en": "loafers", "ar": "لوفرز"},
    "dress": {"en": "dress", "ar": "فستان"},
    "jumpsuit": {"en": "jumpsuit", "ar": "جمبسوت"},
    "abaya": {"en": "abaya", "ar": "عباية"},
    "kaftan": {"en": "kaftan", "ar": "قفطان"},
    # category fallbacks when type is unknown
    "top": {"en": "top", "ar": "قطعة علوية"},
    "bottom": {"en": "bottoms", "ar": "بنطلون"},
    "outerwear": {"en": "outer layer", "ar": "جاكيت"},
    "shoes": {"en": "shoes", "ar": "حذاء"},
    "accessory": {"en": "accessory", "ar": "إكسسوار"},
}

PATTERN_I18N = {
    "striped": {"en": "striped", "ar": "مقلّم"},
    "graphic": {"en": "graphic-print", "ar": "مطبوع"},
    "plaid": {"en": "plaid", "ar": "كاروهات"},
    "floral": {"en": "floral", "ar": "مورّد"},
    "colorblock": {"en": "colorblock", "ar": "بألوان متباينة"},
}

NECKLINE_I18N = {
    "round_neck": {"en": "round neck", "ar": "برقبة دائرية"},
    "v_neck": {"en": "V-neck", "ar": "برقبة سبعة"},
    "collared": {"en": "collared", "ar": "بياقة"},
    "crew_neck": {"en": "crew neck", "ar": "برقبة مستديرة"},
    "turtleneck": {"en": "turtleneck", "ar": "برقبة عالية"},
    "hooded": {"en": "hooded", "ar": "بغطاء رأس"},
}

# a polo is collared and a hoodie is hooded by definition — saying it twice
# is how you get "Cream hooded hoodie"
REDUNDANT_NECKLINE = {"hoodie": "hooded", "polo": "collared", "shirt": "collared"}

# how a neckline reads mid-sentence ("with a collar"), vs. as a name
# adjective ("collared shirt")
NECKLINE_PHRASE = {
    "round_neck": "round neck", "v_neck": "V-neck", "collared": "collar",
    "crew_neck": "crew neck", "turtleneck": "turtleneck", "hooded": "hood",
}

FORMALITY_PHRASE = {
    "casual": {"en": "everyday casual wear", "ar": "الإطلالات اليومية الكاجوال"},
    "smart_casual": {"en": "smart-casual occasions", "ar": "الإطلالات الأنيقة غير الرسمية"},
    "formal": {"en": "formal occasions", "ar": "المناسبات الرسمية"},
    "sport": {"en": "workouts and sports", "ar": "الرياضة والتمارين"},
}

SLEEVE_PHRASE = {
    "sleeveless": {"en": "Sleeveless", "ar": "بدون أكمام"},
    "short": {"en": "Short-sleeved", "ar": "بأكمام قصيرة"},
    "three_quarter": {"en": "Three-quarter sleeves", "ar": "بأكمام ثلاثة أرباع"},
    "long": {"en": "Long-sleeved", "ar": "بأكمام طويلة"},
}


def _t(table, key, lang):
    e = table.get(key)
    return e[lang] if e else ""


def _lam(noun_ar: str) -> str:
    """Arabic لـ + definite noun: لـ + الإطلالات -> للإطلالات."""
    return "لل" + noun_ar[2:] if noun_ar.startswith("ال") else "لـ" + noun_ar


def generate(garment_type: str, category: str, color: dict,
             neckline: str = None, sleeve: str = None, pattern: str = None,
             formality: str = "casual", temp_id: str = "") -> dict:
    t_key = garment_type if garment_type in TYPE_I18N else category
    type_en, type_ar = _t(TYPE_I18N, t_key, "en"), _t(TYPE_I18N, t_key, "ar")
    col_en, col_ar = color["name"]["en"].lower(), color["name"]["ar"]
    if REDUNDANT_NECKLINE.get(garment_type) == neckline:
        neckline = None
    neck_en, neck_ar = _t(NECKLINE_I18N, neckline, "en"), _t(NECKLINE_I18N, neckline, "ar")
    pat_en, pat_ar = _t(PATTERN_I18N, pattern, "en"), _t(PATTERN_I18N, pattern, "ar")

    # one adjective beyond the color, or names run to four words: the
    # pattern is what you actually see across the room, so it wins
    detail_en, detail_ar = (pat_en, pat_ar) if pat_en else (neck_en, neck_ar)

    # EN: {Color} {pattern|neckline} {type} — AR: {type} {color} {pattern|neckline}
    name_en = " ".join(x for x in [col_en.capitalize(), detail_en, type_en] if x)
    name_ar = " ".join(x for x in [type_ar, col_ar, detail_ar] if x)

    form_en = FORMALITY_PHRASE[formality]["en"]
    form_ar = FORMALITY_PHRASE[formality]["ar"]
    sleeve_en = _t(SLEEVE_PHRASE, sleeve, "en")
    sleeve_ar = _t(SLEEVE_PHRASE, sleeve, "ar")

    desc_en = " ".join(x for x in [col_en, pat_en, type_en] if x)
    desc_ar = " ".join(x for x in [type_ar, col_ar, pat_ar] if x)

    variants_en = [
        f"Simple and comfortable {desc_en}"
        + (f" with a {NECKLINE_PHRASE[neckline]}" if neckline in NECKLINE_PHRASE else "")
        + f", perfect for {form_en}.",
        f"A versatile {desc_en}. "
        + (f"{sleeve_en} and easy to pair." if sleeve_en else "Easy to pair."),
        f"{desc_en.capitalize()} that works well for {form_en}.",
    ]
    variants_ar = [
        f"{desc_ar} بسيط ومريح، مثالي {_lam(form_ar)}.",
        f"{desc_ar} عملي وسهل التنسيق"
        + (f"، {sleeve_ar}." if sleeve_ar else "."),
        f"{desc_ar} مناسب {_lam(form_ar)}.",
    ]
    idx = int(hashlib.md5(temp_id.encode()).hexdigest(), 16) % len(variants_en)

    return {
        "name": {"en": name_en, "ar": name_ar},
        "description": {"en": variants_en[idx], "ar": variants_ar[idx]},
    }
