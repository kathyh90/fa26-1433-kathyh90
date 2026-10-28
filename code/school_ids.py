"""Stable school identifiers across NCES ID changes, shared by the panel scripts.

A public school's NCES ID (12 digits) is its district ID (7) plus NCES's school
number (5). When a school moves to a new district the ID changes but the school
number usually stays. NCES IDs in the same state with the same school number
are treated as one school if CCD never lists them open in the same year and any
of their names match (e.g. Granada Hills Charter, CA: 062271003050 ->
060220603050). The school_id is the most recent NCES ID.
"""

import zipfile

import pandas as pd

from config import RAW
from matching import FUZZY_COVERAGE, fuzzy_coverage, normalize

CCD_DIR = RAW / "US" / "nces_ccd_school"


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
