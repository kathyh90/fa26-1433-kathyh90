"""School-name matching helpers shared by the FSA linking and panel scripts."""

import re

import pandas as pd
from rapidfuzz import fuzz

FUZZY_COVERAGE = 0.5   # shared words' share of the longer name's distinctive letters
FUZZY_WORD = 80        # rapidfuzz ratio for two 5+ letter words to count as the same
FUZZY_MIN_CHARS = 4    # names with fewer distinctive letters are not fuzzy-matched

# Whole-word abbreviations expanded before comparing names. Both sides are
# normalized the same way, so an ambiguous one (ST = SAINT or STREET) is safe.
ABBREVIATIONS = {
    "SCH": "SCHOOL", "SCHL": "SCHOOL", "HS": "HIGH SCHOOL", "H S": "HIGH SCHOOL",
    "ACAD": "ACADEMY", "ACA": "ACADEMY", "ST": "SAINT", "MT": "MOUNT",
    "JR": "JUNIOR", "SR": "SENIOR", "CTR": "CENTER", "PREP": "PREPARATORY",
    "CHR": "CHRISTIAN", "INTL": "INTERNATIONAL", "CHTR": "CHARTER",
    "TECH": "TECHNOLOGY", "VOC": "VOCATIONAL", "CO": "COUNTY",
}
_ABBREV = re.compile(r"\b(" + "|".join(sorted(map(re.escape, ABBREVIATIONS), key=len, reverse=True)) + r")\b")

# Words too common in school names to identify a school; set aside for fuzzy
# matching only.
GENERIC = {
    "THE", "OF", "AND", "AT", "FOR", "IN", "HIGH", "SCHOOL", "SCHOOLS", "SENIOR",
    "JUNIOR", "MIDDLE", "SECONDARY", "CHARTER", "ACADEMY", "PREPARATORY",
    "COLLEGE", "EARLY", "CENTER", "CAMPUS", "PUBLIC", "CHRISTIAN", "CATHOLIC",
    "SAINT", "COUNTY", "DISTRICT", "PROGRAM", "INC", "COMMUNITY", "EDUCATION",
    "LEARNING",
}

def normalize(text):
    """Uppercase, drop punctuation, expand common abbreviations, collapse spaces."""
    if text is None or pd.isna(text):
        return None
    text = str(text).upper().replace("&", " AND ")
    text = re.sub(r"[^A-Z0-9 ]", " ", text)   # punctuation becomes a space
    text = re.sub(r"\s+", " ", text).strip()
    text = _ABBREV.sub(lambda m: ABBREVIATIONS[m[1]], text)
    return re.sub(r"\s+", " ", text).strip() or None


def distinctive(name_norm, city_norm=None):
    """Return a normalized name's words minus generic words and the city's words."""
    if not isinstance(name_norm, str):
        return []
    drop = GENERIC | set(city_norm.split() if isinstance(city_norm, str) else [])
    return [w for w in name_norm.split() if w not in drop]


def fuzzy_coverage(a, b, city_norm):
    """Return how fully two names agree on distinctive words (0 = no match).

    Every distinctive word of the shorter name must appear in the longer one
    (5+ letter words may differ slightly). The result is the shorter name's
    distinctive letters as a share of the longer name's.
    """
    wa, wb = distinctive(a, city_norm), distinctive(b, city_norm)
    la, lb = sum(map(len, wa)), sum(map(len, wb))
    if min(la, lb) < FUZZY_MIN_CHARS:
        return 0.0
    short, long_ = (wa, wb) if la <= lb else (wb, wa)
    for w in short:
        if w in long_:
            continue
        # A near-spelling must be of similar length, so VALLEY is not MIDVALLEY.
        if len(w) >= 5 and any(len(u) >= 5 and abs(len(u) - len(w)) <= 2 and fuzz.ratio(w, u) >= FUZZY_WORD
                               for u in long_):
            continue
        return 0.0
    return min(la, lb) / max(la, lb)
