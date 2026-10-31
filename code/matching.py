"""School matching helpers shared by the FSA linking and panel scripts.

Name matching: normalize() and the strict fuzzy rule fuzzy_coverage().

Stable school IDs (stable_ids): a public school's NCES ID (12 digits) is its
district ID (7) plus NCES's school number (5). When a school moves to a new
district the ID changes but the school number usually stays. NCES IDs in the
same state with the same school number are treated as one school if CCD never
lists them open in the same year and any of their names match (e.g. Granada
Hills Charter, CA: 062271003050 -> 060220603050). The school_id is the most
recent NCES ID.
"""

import re
import zipfile

import pandas as pd
from rapidfuzz import fuzz

from config import RAW

CCD_DIR = RAW / "US" / "nces_ccd_school"

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


# --- Stable school IDs across NCES ID changes --------------------------------

def names_match(a, b):
    """True if two normalized names are equal or agree on distinctive words."""
    return a == b or fuzzy_coverage(a, b, None) >= FUZZY_COVERAGE


def read_ccd_ids():
    """Return every NCES ID in the CCD directories with its first/last open year and names.

    names_norm holds every normalized name the ID had while open (schools are
    renamed, e.g. KIPP Renaissance -> Frederick A. Douglass High School).
    """
    frames = []
    for folder in sorted(p for p in CCD_DIR.iterdir() if p.is_dir()):
        zips = sorted(folder.glob("ccd_sch_029_*.zip"))
        if len(zips) != 1:
            continue
        with zipfile.ZipFile(zips[0]) as z:
            member = next(n for n in z.namelist() if n.lower().endswith((".csv", ".txt")))
            with z.open(member) as f:
                d = pd.read_csv(f, sep="\t" if member.lower().endswith(".txt") else ",",
                                dtype=str, encoding="latin-1",
                                usecols=lambda c: c in {"NCESSCH", "SCH_NAME", "SY_STATUS_TEXT"})
        # Closed schools are still listed in the year they close; keep open years only.
        d = d[~d["SY_STATUS_TEXT"].fillna("").str.lower().str.startswith("closed")]
        d["year"] = int(folder.name[:4]) + 1   # spring year of the school year
        frames.append(d[["NCESSCH", "SCH_NAME", "year"]])
    d = pd.concat(frames)
    d["name_norm"] = d["SCH_NAME"].map(normalize)
    ids = (d.sort_values("year").groupby("NCESSCH")
           .agg(first=("year", "min"), last=("year", "max"), name=("SCH_NAME", "last"),
                names_norm=("name_norm", lambda s: set(s.dropna()))).reset_index())
    return ids


def stable_ids(codes):
    """Map each code to a school_id that survives NCES district moves."""
    school_id = {c: c for c in codes}
    ids = read_ccd_ids()
    ids = ids[ids["NCESSCH"].str.len() == 12]
    ids["fips"], ids["schnum"] = ids["NCESSCH"].str[:2], ids["NCESSCH"].str[7:]
    merged = 0
    for _, g in ids[ids.duplicated(["fips", "schnum"], keep=False)].groupby(["fips", "schnum"]):
        g = g.sort_values("first")
        chain = [g.iloc[0]]
        for _, row in g.iloc[1:].iterrows():
            prev = chain[-1]
            if row["first"] > prev["last"] and any(
                    names_match(a, b) for a in prev["names_norm"] for b in row["names_norm"]):
                chain.append(row)
            else:
                chain = [row]   # overlap or different school: start a new chain
            if len(chain) > 1:
                newest = chain[-1]["NCESSCH"]
                for r in chain:
                    if school_id.get(r["NCESSCH"], newest) != newest:
                        merged += 1
                    school_id[r["NCESSCH"]] = newest
    # Keep only codes that appear in FSA, resolving chains to their newest ID.
    out = {c: school_id.get(c, c) for c in codes}
    changed = sum(1 for c, s in out.items() if c != s)
    print(f"  NCES IDs linked to a newer ID of the same school: {changed:,} of {len(out):,} codes "
          f"({merged:,} ID pairs chained in CCD)")
    return out
