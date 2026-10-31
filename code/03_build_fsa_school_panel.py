"""Collapse FSA records to one row per school and graduating class.

Inputs: data/derived/fsa_fafsa_hs.parquet (FSA counts per record) and
data/derived/fsa_school_codes.parquet (each record's linked code), plus the
CCD school directories for every year in data/raw/US/nces_ccd_school/.

Steps:
  1. Records without a linked code are added to a school when they are a
     second listing of it: their candidate_code is held by a linked record in
     the same class, same city, with a matching name (e.g. AGORA CYBER CHARTER
     SCHOOL and AGORA CYBER CS). Network-level records (names ending in
     SCHOOLS or containing NETWORK) are never added to a campus. All other
     records without a code are left out, with counts reported by reason.
  2. Each code gets a stable school_id. A public school's NCES ID changes when
     it moves to a new district (the first 7 digits are the district), but the
     last 5 digits, NCES's school number, usually stay. NCES IDs in the same
     state with the same school number are one school if CCD never lists them
     open in the same year and any of their names match (e.g. Granada Hills
     Charter, CA: 062271003050 -> 060220603050; KIPP Renaissance, LA,
     220004500953 -> 220019700953, later renamed Frederick A. Douglass High
     School). school_id is the most recent NCES ID.
     PSS IDs (private) and FSA-only codes are used as they are.
  3. Records are summed by school_id and class. A "<5" cell adds nothing to
     the sum and sets the matching *_lt5 flag, so a flagged sum is a lower
     bound (exact when the school has a single record, where it is missing).

Only the 15 study states are kept (STUDY_STATES); the earlier FSA files keep
every state, so never-adopting comparison states can be added back here.

Writes data/derived/fsa_school_panel.parquet (key: school_id, class_year).

Usage (from the repository root):
    uv run --locked python code/03_build_fsa_school_panel.py
"""

import duckdb
import pandas as pd

from config import DERIVED, STUDY_STATES
from matching import names_match, normalize, stable_ids

PANEL = DERIVED / "fsa_fafsa_hs.parquet"
CODES = DERIVED / "fsa_school_codes.parquet"
OUT = DERIVED / "fsa_school_panel.parquet"
OPEN_TIERS = ("name_only_rejected", "ambiguous", "unlinked")
COUNTS = ["submitted_jun", "completed_jun", "submitted_dec", "completed_dec"]
NETWORK = r"SCHOOLS$|\bNETWORK\b"


def load_records():
    """Return FSA records joined to their linked codes."""
    con = duckdb.connect()
    df = con.execute(f"""
        SELECT p.*, c.code_linked, c.link_tier, c.candidate_code, c.candidate_tier
        FROM read_parquet('{PANEL.as_posix()}') p
        JOIN read_parquet('{CODES.as_posix()}') c USING (class_year, source_file, row_in_file)
    """).df()
    df["name_norm"] = df["name"].map(normalize)
    df["city_norm"] = df["city"].map(normalize)
    return df


def absorb_duplicates(df):
    """Assign unlinked second listings of a school to that school's code."""
    df["code"] = df["code_linked"].where(~df["link_tier"].isin(OPEN_TIERS))
    df["assign_rule"] = df["link_tier"].where(df["code"].notna())
    single = (df["code"].isna() & df["candidate_code"].notna()
              & ~df["candidate_code"].str.contains("|", regex=False, na=False))
    holders = (df.loc[df["code"].notna(), ["class_year", "code", "name_norm", "city_norm"]]
               .rename(columns={"code": "candidate_code", "name_norm": "holder_name"}))
    cand = (df.loc[single, ["class_year", "candidate_code", "name_norm", "city_norm"]].reset_index()
            .merge(holders, on=["class_year", "candidate_code", "city_norm"]))
    cand = cand[~cand["name_norm"].str.contains(NETWORK, regex=True, na=False)]
    cand = cand[[names_match(a, b) for a, b in zip(cand["name_norm"], cand["holder_name"])]]
    idx = cand["index"].unique()
    df.loc[idx, "code"] = df.loc[idx, "candidate_code"]
    df.loc[idx, "assign_rule"] = "duplicate_listing"
    return len(idx)


def sector(code):
    """Classify a code: 12 characters = public (NCES), 'FN' = no NCES ID, else private (PSS)."""
    if len(code) == 12:
        return "public"
    return "no_nces_id" if "FN" in code else "private"


def collapse(df):
    """Sum records by school_id and class; keep descriptors from the largest record."""
    for c in COUNTS:
        df[c + "_known"] = df[c].fillna(0)
    df["size"] = df["completed_jun"].fillna(0)
    top = df.sort_values("size", ascending=False).drop_duplicates(["school_id", "class_year"])
    agg = {c + "_known": "sum" for c in COUNTS}
    agg |= {c + "_lt5": "any" for c in COUNTS}
    agg |= {c: "count" for c in ["completed_jun"]}
    g = df.groupby(["school_id", "class_year"])
    out = g.agg(**{c: (c + "_known", "sum") for c in COUNTS},
                **{c + "_lt5": (c + "_lt5", "any") for c in COUNTS},
                **{c + "_n_known": (c, "count") for c in COUNTS},
                n_records=("row_in_file", "size"),
                codes=("code", lambda s: "|".join(sorted(set(s)))),
                assign_rules=("assign_rule", lambda s: "|".join(sorted(set(s))))).reset_index()
    # A sum with no known component is missing, not zero.
    for c in COUNTS:
        out[c] = out[c].astype("Int64").mask(out.pop(c + "_n_known") == 0)
    keep = ["school_id", "class_year", "state", "name", "city", "kind", "snapshot_date", "source_file"]
    out = out.merge(top[keep], on=["school_id", "class_year"])
    out["sector"] = out["school_id"].map(sector)
    cols = ["school_id", "class_year", "state", "name", "city", "sector", *COUNTS,
            *[c + "_lt5" for c in COUNTS], "n_records", "codes", "assign_rules",
            "kind", "snapshot_date", "source_file"]
    return out[cols].sort_values(["state", "school_id", "class_year"]).reset_index(drop=True)


def main():
    df = load_records()
    print(f"FSA records: {len(df):,}; completions through June: {df['completed_jun'].sum():,.0f}")
    n0, c0 = len(df), df["completed_jun"].sum()
    df = df[df["state"].isin(STUDY_STATES)].copy()
    print(f"  kept the 15 study states: {len(df):,} records, {df['completed_jun'].sum():,.0f} completions "
          f"(dropped {n0 - len(df):,} records, {c0 - df['completed_jun'].sum():,.0f} completions, in other states)")

    n_dup = absorb_duplicates(df)
    print(f"  second listings added to the school they duplicate: {n_dup:,}")
    dropped = df[df["code"].isna()]
    reasons = dropped.assign(reason=dropped["name_norm"].str.contains(NETWORK, regex=True, na=False)
                             .map({True: "network-level record", False: None})
                             .fillna(dropped["link_tier"]))
    summary = reasons.groupby("reason").agg(records=("name", "size"), completions=("completed_jun", "sum"))
    print(f"  records left out (no code): {len(dropped):,}; completions {dropped['completed_jun'].sum():,.0f}")
    print(summary.to_string())
    df = df[df["code"].notna()].copy()
    print(f"Records kept: {len(df):,}")

    mapping = stable_ids(sorted(df["code"].unique()))
    df["school_id"] = df["code"].map(mapping)
    out = collapse(df)

    dup = out.duplicated(["school_id", "class_year"]).sum()
    if dup:
        raise ValueError(f"{dup} duplicate (school_id, class_year) rows")
    lost = df["completed_jun"].sum() - out["completed_jun"].sum()
    if lost != 0:
        raise ValueError(f"completions changed in collapse by {lost}")
    out.to_parquet(OUT, index=False)
    print(f"\nWrote {OUT.name}: {len(out):,} school x class rows "
          f"({out['school_id'].nunique():,} schools) from {len(df):,} records")
    multi = out[out["n_records"] > 1]
    print(f"  rows built from several records: {len(multi):,}; "
          f"rows whose sum includes a '<5' cell: {(multi['completed_jun_lt5']).sum():,}")

    s = out
    print("\nSchools per class (all sectors), and public share")
    wide = s.pivot_table(index="state", columns="class_year", values="school_id", aggfunc="count")
    print(wide.reindex(STUDY_STATES).to_string())
    pub = s.groupby("state")["sector"].apply(lambda x: (x == "public").mean()).reindex(STUDY_STATES).round(3)
    print("\nShare of school x class rows that are public:")
    print(pub.to_string())


if __name__ == "__main__":
    main()
