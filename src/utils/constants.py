from typing import Dict

LINEAGE_COLOR_MAP: Dict[str, str] = {
    "SATIVA": "#E74C3C",
    "INDICA": "#8E44AD",
    "HYBRID": "#27AE60",
    "HYBRID/SATIVA": "#E74C3C",
    "HYBRID/INDICA": "#8E44AD",
    "CBD": "#F1C40F",
    "MIXED": "#2C3E50",
    "PARAPHERNALIA": "#FF69B4",
}

TYPE_OVERRIDES: Dict[str, str] = {
    "all-in-one": "vape cartridge",
    "rosin": "concentrate",
    "mini buds": "flower",
    "bud": "flower",
    "pre-roll": "pre-roll",
}

WORD_WEIGHT = 5
SCALE_FACTOR = 1.0