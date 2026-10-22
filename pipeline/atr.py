"""ATR label map and region → garment mapping (spec §S1/S2). This is the contract."""

ATR = {
    "BACKGROUND": 0, "HAT": 1, "HAIR": 2, "SUNGLASSES": 3,
    "UPPER_CLOTHES": 4, "SKIRT": 5, "PANTS": 6, "DRESS": 7,
    "BELT": 8, "LEFT_SHOE": 9, "RIGHT_SHOE": 10, "FACE": 11,
    "LEFT_LEG": 12, "RIGHT_LEG": 13, "LEFT_ARM": 14, "RIGHT_ARM": 15,
    "BAG": 16, "SCARF": 17,
}

ATR_NAMES = {v: k for k, v in ATR.items()}

# category -> list of ATR label groups. Each group becomes at most ONE garment.
# Shoes: both labels in one group => merged into a single `shoes` item (never two).
GARMENT_SOURCES = [
    ("top",       [ATR["UPPER_CLOTHES"]]),          # subject to layer splitting
    # Pants and Skirt merge into ONE bottom: ATR routinely splits a single
    # lower garment (wide shorts, culottes) across both labels, and emitting
    # two items punches each one's region out of the other.
    ("bottom",    [ATR["PANTS"], ATR["SKIRT"]]),
    ("dress",     [ATR["DRESS"]]),
    ("shoes",     [ATR["LEFT_SHOE"], ATR["RIGHT_SHOE"]]),
    ("accessory", [ATR["HAT"]]),
    ("accessory", [ATR["SUNGLASSES"]]),
    ("accessory", [ATR["BAG"]]),
    ("accessory", [ATR["SCARF"]]),
    # BELT (8): ignored in v1
]

SKIN_LABELS = [ATR["LEFT_ARM"], ATR["RIGHT_ARM"], ATR["FACE"],
               ATR["LEFT_LEG"], ATR["RIGHT_LEG"]]

# Things that sit ON a garment and should stay visible in its cutout rather
# than leave a hole. Deliberately excludes other garment labels (adding those
# would paste a chunk of trousers into a shirt) and bare legs.
OCCLUDER_LABELS = [ATR["LEFT_ARM"], ATR["RIGHT_ARM"], ATR["BAG"],
                   ATR["BELT"], ATR["SCARF"]]

# Labels that mean "a different garment" — a large gap made of these signals
# a bad parse, not an occlusion.
OTHER_GARMENT_LABELS = [ATR["UPPER_CLOTHES"], ATR["PANTS"], ATR["SKIRT"],
                        ATR["DRESS"], ATR["LEFT_SHOE"], ATR["RIGHT_SHOE"]]
