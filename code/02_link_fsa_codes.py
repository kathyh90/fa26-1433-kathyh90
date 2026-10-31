"""Give pre-2021 FSA school records the School Code that FSA uses from 2021 on.

FSA files carry a School Code only from the Dec 2022 file on, i.e. for the
classes of 2021+: the NCES ID for public schools (12 characters) or the PSS ID
for private schools (8 characters). Earlier records have only name, city, and
state. This script links each earlier record to a code in tiers.

Against FSA's own coded records (2021+) of the same state:
  1. exact       same state, name, and city as a coded record
  2. normalized  same state and normalized name and city (case, punctuation,
                 common abbreviations such as SCH -> SCHOOL)
  3. name_only   same state and normalized name, different city

Then a check of those links against the directories for the class's senior
year (CCD for public, PSS for private schools; see below). FSA's codes describe
schools as they are in 2021+, so an old name can carry a code that belonged to
another school at the time (e.g. DOTHAN HIGH SCHOOL, AL: after a 2019 merger
the name moved to Northview's NCES ID):
  ccd_relinked        an FSA-tier code that the year's CCD lists under a
                      clearly different name is replaced by the CCD school
                      with the same name and city that year
  ambiguous_resolved  a name that fits several FSA codes is linked to the one
                      code present in that year's CCD or PSS

Then, for records still without a code, against a school directory for the
class's senior year: the NCES CCD (public schools; class of 2015 -> 2014-15)
and then the NCES Private School Survey (PSS; biennial, the waves starting two
years before through the class year). In each directory:
  4. <dir>_exact      same state and normalized name and city (physical or
                      mailing city)
  5. <dir>_prefix     same state and city; the FSA name is the start of the
                      directory name (older FSA files cut long names short)
  6. <dir>_name_only  same state and normalized name, different city
  7. <dir>_fuzzy      same state and city; after setting aside generic words
                      (HIGH, SCHOOL, CHARTER, ...) and the city's own name,
                      every remaining word of the shorter name appears in the
                      longer one (words of 5+ letters may differ slightly:
                      rapidfuzz ratio >= 80 and within 2 letters in length),
                      those words make up at least half
                      of the longer name's remaining letters, and only one
                      code passes
Directory schools are dropped only if their highest grade is known to be
below 12; missing or ungraded spans are kept.

Finally:
  8. other_year  same state and normalized name and city as records of other
                 pre-2021 classes that were linked (by any tier above) to
                 one single code

A key that leads to more than one code is not linked ("ambiguous"). From tier
3 on, a link is rejected if its code is already taken in that class by another
linked record, or if several records compete for it. Rejected and ambiguous
records keep the code(s) they were offered in candidate_code (codes joined by
"|"), with the tier that offered them in candidate_tier.

Reads data/derived/fsa_fafsa_hs.parquet; writes data/derived/fsa_school_codes.parquet
with one row per FSA record (key: class_year, source_file, row_in_file).

Usage (from the repository root):
    uv run --locked python code/02_link_fsa_codes.py
"""

import re
import zipfile
from functools import lru_cache

import duckdb
import pandas as pd

from config import DERIVED, RAW, STUDY_STATES
from matching import FUZZY_COVERAGE, fuzzy_coverage, normalize

PANEL = DERIVED / "fsa_fafsa_hs.parquet"
OUT = DERIVED / "fsa_school_codes.parquet"
CCD_DIR = RAW / "US" / "nces_ccd_school"
PSS_DIR = RAW / "US" / "nces_pss"
FSA_TIERS = ("exact", "normalized", "name_only")
DIR_STEPS = ("exact", "prefix", "name_only", "fuzzy")
CCD_TIERS = tuple(f"ccd_{s}" for s in DIR_STEPS)
PSS_TIERS = tuple(f"pss_{s}" for s in DIR_STEPS)
CHECK_TIERS = ("ccd_relinked", "ambiguous_resolved")
LINKED = ("fsa_code",) + FSA_TIERS + CHECK_TIERS + CCD_TIERS + PSS_TIERS + ("other_year",)
OPEN_TIERS = ["name_only_rejected", "ambiguous", "unlinked"]
MIN_PREFIX = 12        # shortest FSA name (characters, normalized) allowed to prefix-match

# CCD GSHI values that are a grade below 12; everything else (12, 13, missing,
# not applicable, ungraded, adult education) is kept.
CCD_BELOW_12 = {"PK", "KG", "01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11"}
# PSS HIGR recode: 17 = grade 12, 1 = all ungraded; 2-16 are prekindergarten
# through grade 11 (see the PSS codebooks).
PSS_BELOW_12 = {str(c) for c in range(2, 17)}


def _directory_frame(code, state, name, city1, city2):
    """Stack a directory's two city columns into one row per school and city."""
    d = pd.DataFrame({"code": code, "state": state, "dir_name": name, "c1": city1, "c2": city2})
    d = d.melt(id_vars=["code", "state", "dir_name"], value_vars=["c1", "c2"], value_name="dir_city")
    d = d.drop(columns="variable").dropna(subset=["dir_city"])
    for c in ["code", "state", "dir_name", "dir_city"]:
        d[c] = d[c].str.strip()
    d["name_norm"] = d["dir_name"].map(normalize)
    d["city_norm"] = d["dir_city"].map(normalize)
    return d.drop_duplicates(["code", "city_norm"])


@lru_cache(maxsize=None)
def read_ccd_directory(class_year):
    """Return CCD directory schools for the class's senior year (grade 12 not ruled out)."""
    folder = CCD_DIR / f"{class_year - 1}-{class_year}"
    zips = sorted(folder.glob("ccd_sch_029_*.zip"))
    if len(zips) != 1:
        raise FileNotFoundError(f"expected one CCD directory zip in {folder}, found {len(zips)}")
    with zipfile.ZipFile(zips[0]) as z:
        member = next(n for n in z.namelist() if n.lower().endswith((".csv", ".txt")))
        with z.open(member) as f:
            # 2014-15 is tab-delimited text; later years are CSV. State is
            # STABR through 2016-17 and ST after.
            d = pd.read_csv(f, sep="\t" if member.lower().endswith(".txt") else ",",
                            dtype=str, encoding="latin-1",
                            usecols=lambda c: c in {"NCESSCH", "SCH_NAME", "LCITY", "MCITY",
                                                    "STABR", "ST", "GSHI"})
    d = d.rename(columns={"STABR": "ST"})
    rows_read = len(d)
    d = d[~d["GSHI"].str.strip().isin(CCD_BELOW_12)]
    print(f"  CCD {folder.name}: {rows_read:,} schools read, {len(d):,} kept "
          f"(dropped {rows_read - len(d):,} with highest grade below 12)")
    return _directory_frame(d["NCESSCH"], d["ST"], d["SCH_NAME"], d["LCITY"], d["MCITY"])


@lru_cache(maxsize=None)
def read_pss(class_year):
    """Return PSS private schools from the waves starting class_year-2 to class_year.

    PSS is biennial, so this is the one or two waves around the senior year
    (e.g. class of 2015 -> 2013-14 and 2015-16). Grade 12 not ruled out.
    """
    frames, read, kept = [], 0, 0
    for start in range(class_year - 2, class_year + 1):
        path = PSS_DIR / f"pss{start % 100:02d}{(start + 1) % 100:02d}_pu_csv.zip"
        if not path.exists():
            continue
        with zipfile.ZipFile(path) as z:
            member = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            higr = f"HIGR{start + 1}"
            with z.open(member) as f:
                # Column names are lowercase in 2015-16 and uppercase otherwise.
                d = pd.read_csv(f, dtype=str, encoding="latin-1",
                                usecols=lambda c: c.upper() in {"PPIN", "PINST", "PCITY", "PL_CIT", "PSTABB", higr})
            d.columns = d.columns.str.upper()
        read += len(d)
        d = d[~d[higr].str.strip().isin(PSS_BELOW_12)]
        kept += len(d)
        frames.append(_directory_frame(d["PPIN"], d["PSTABB"], d["PINST"], d["PL_CIT"], d["PCITY"]))
    if not frames:
        raise FileNotFoundError(f"no PSS wave in {PSS_DIR} covers the class of {class_year}")
    print(f"  PSS for class of {class_year}: {read:,} school rows read, {kept:,} kept "
          f"(dropped {read - kept:,} with highest grade below 12)")
    return pd.concat(frames).drop_duplicates(["code", "city_norm", "name_norm"])


def taken_or_contested(df, cand, ok):
    """Flag candidate links whose (class, code) is already linked or contested.

    cand holds candidate rows (index = df rows) with class_year, code, and
    name_city; ok marks rows with a unique candidate code.
    """
    linked = df[df["link_tier"].isin(LINKED)]
    taken = set(zip(linked["class_year"], linked["code_linked"]))
    competing = cand[ok].groupby(["class_year", "code"])["name_city"].nunique() > 1
    competing = set(competing[competing].index)
    return ok & pd.Series([(y, c) in taken or (y, c) in competing
                           for y, c in zip(cand["class_year"], cand["code"])], index=cand.index)


def directory_candidates(recs, directory, step):
    """Return (record, directory school) candidate pairs for one matching step."""
    if step == "exact":
        return recs.merge(directory, on=["state", "name_norm", "city_norm"])
    if step == "name_only":
        return recs.merge(directory.drop(columns="city_norm"), on=["state", "name_norm"])
    m = recs.merge(directory, on=["state", "city_norm"], suffixes=("", "_dir"))
    if step == "prefix":
        m = m[m["name_norm"].str.len() >= MIN_PREFIX]
        return m[[d.startswith(f) for d, f in zip(m["name_norm_dir"], m["name_norm"])]]
    # fuzzy: keep same-city pairs whose distinctive words agree; the caller
    # links a record only if a single code remains.
    cov = [fuzzy_coverage(f, d, c) for f, d, c in zip(m["name_norm"], m["name_norm_dir"], m["city_norm"])]
    return m[pd.Series(cov, index=m.index) >= FUZZY_COVERAGE]


def note_candidate(df, idx, codes, tier):
    """Record the code(s) offered to records that were not linked, keeping the first offer."""
    idx = pd.Index(idx)
    if len(idx) == 0:
        return
    fresh = idx[df.loc[idx, "candidate_code"].isna()]
    df.loc[fresh, "candidate_code"] = pd.Series(codes, index=idx).loc[fresh]
    df.loc[fresh, "candidate_tier"] = tier


def check_against_year_directory(df):
    """Correct FSA-tier links using the directories of each class's senior year.

    Relinks a public-school code that the year's CCD lists under a clearly
    different name, when the FSA name and city match another CCD school that
    year; and resolves ambiguous records whose candidate codes include exactly
    one code present in that year's CCD or PSS.
    """
    first_coded = df.loc[df["school_code"].notna(), "class_year"].min()
    relinked = resolved = rejected = 0
    for year in sorted(df.loc[df["class_year"] < first_coded, "class_year"].unique()):
        ccd, pss = read_ccd_directory(year), read_pss(year)
        names = pd.concat([ccd, pss]).groupby("code")["name_norm"].agg(set)
        in_year = df["class_year"] == year

        # 1. FSA-tier public codes whose name that year is a different school.
        rows = df.index[in_year & df["link_tier"].isin(FSA_TIERS) & (df["code_linked"].str.len() == 12)]
        disagree = [i for i in rows if df.at[i, "code_linked"] in names.index and not any(
            n == df.at[i, "name_norm"] or fuzzy_coverage(df.at[i, "name_norm"], n, df.at[i, "city_norm"]) >= FUZZY_COVERAGE
            for n in names[df.at[i, "code_linked"]])]
        if disagree:
            recs = df.loc[disagree, ["state", "name_norm", "city_norm", "name", "city"]].rename_axis("rid").reset_index()
            m = recs.merge(ccd, on=["state", "name_norm", "city_norm"])
            n_codes = m.groupby("rid")["code"].nunique()
            best = m.drop_duplicates("rid").set_index("rid")
            best = best[(n_codes.reindex(best.index) == 1) & (best["code"] != df.loc[best.index, "code_linked"])]
            cand = pd.DataFrame({"class_year": year, "code": best["code"],
                                 "name_city": best["name"].fillna("") + "|" + best["city"].fillna("")})
            ok = pd.Series(True, index=cand.index)
            bad = taken_or_contested(df, cand, ok)
            idx = cand.index[~bad]
            df.loc[idx, "code_linked"] = cand.loc[idx, "code"]
            df.loc[idx, "link_tier"] = "ccd_relinked"
            df.loc[idx, "ccd_name"] = best.loc[idx, "dir_name"]
            df.loc[idx, "ccd_city"] = best.loc[idx, "dir_city"]
            relinked += len(idx)
            rejected += int(bad.sum())

        # 2. Ambiguous records with exactly one candidate code in that year's directories.
        rows = df.index[in_year & (df["link_tier"] == "ambiguous") & df["candidate_code"].notna()]
        present = {i: [c for c in df.at[i, "candidate_code"].split("|") if c in names.index] for i in rows}
        single = {i: c[0] for i, c in present.items() if len(c) == 1}
        if single:
            cand = pd.DataFrame({"class_year": year, "code": pd.Series(single)})
            cand["name_city"] = df.loc[cand.index, "name"].fillna("") + "|" + df.loc[cand.index, "city"].fillna("")
            bad = taken_or_contested(df, cand, pd.Series(True, index=cand.index))
            idx = cand.index[~bad]
            df.loc[idx, "code_linked"] = cand.loc[idx, "code"]
            df.loc[idx, "link_tier"] = "ambiguous_resolved"
            resolved += len(idx)
            rejected += int(bad.sum())
    print(f"  ccd_relinked: {relinked:,}; ambiguous_resolved: {resolved:,}; "
          f"rejected (new code taken or contested): {rejected:,}")


def link_to_directory(df, source, reader):
    """Match records still without a code to a school directory, step by step.

    source is "ccd" or "pss"; reader(class_year) returns that directory for
    the class. Matched names and cities are stored in <source>_name/_city.
    """
    for c in (f"{source}_name", f"{source}_city"):
        if c not in df.columns:
            df[c] = pd.Series(pd.NA, index=df.index, dtype="string")
    tiers = tuple(f"{source}_{s}" for s in DIR_STEPS)
    counts = {t: 0 for t in tiers} | {"rejected": 0}
    # Only classes before FSA's own codes start; later records without a code
    # carry FSA's all-zero placeholder and are mostly not directory schools.
    first_coded = df.loc[df["school_code"].notna(), "class_year"].min()
    years = df.loc[df["link_tier"].isin(OPEN_TIERS) & (df["class_year"] < first_coded), "class_year"]
    for year in sorted(years.unique()):
        directory = reader(year)
        for step, tier in zip(DIR_STEPS, tiers):
            todo = df.index[(df["class_year"] == year) & df["link_tier"].isin(OPEN_TIERS)]
            recs = (df.loc[todo, ["state", "name_norm", "city_norm", "name", "city"]]
                    .rename_axis("rid").reset_index())
            m = directory_candidates(recs, directory, step)
            n_codes = m.groupby("rid")["code"].nunique()
            best = m.drop_duplicates("rid").set_index("rid")
            cand = pd.DataFrame({
                "class_year": year,
                "code": best["code"],
                "name_city": best["name"].fillna("") + "|" + best["city"].fillna(""),
            })
            ok = (n_codes == 1).reindex(cand.index, fill_value=False)
            bad = taken_or_contested(df, cand, ok)
            note_candidate(df, bad[bad].index, cand.loc[bad[bad].index, "code"], tier)
            several = m.groupby("rid")["code"].agg(lambda c: "|".join(sorted(set(c))))
            several = several[n_codes.reindex(several.index) > 1]
            note_candidate(df, several.index, several, tier)
            ok &= ~bad
            idx = ok[ok].index
            df.loc[idx, "code_linked"] = cand.loc[idx, "code"]
            df.loc[idx, "link_tier"] = tier
            df.loc[idx, f"{source}_name"] = best.loc[idx, "dir_name"]
            df.loc[idx, f"{source}_city"] = best.loc[idx, "dir_city"]
            counts[tier] += len(idx)
            counts["rejected"] += int(bad.sum())
    print("  " + "; ".join(f"{k}: {v:,}" for k, v in counts.items())
          + " (rejected = code already taken or contested in that class)")


def link_from_other_years(df):
    """Link records to the code their same-named, same-city records got in other classes."""
    first_coded = df.loc[df["school_code"].notna(), "class_year"].min()
    keys = ["state", "name_norm", "city_norm"]
    pre = df[df["class_year"] < first_coded].dropna(subset=keys)
    donors = pre[pre["link_tier"].isin(FSA_TIERS + CHECK_TIERS + CCD_TIERS + PSS_TIERS)]
    lookup = donors.groupby(keys)["code_linked"].agg(n_codes="nunique", code="first").reset_index()
    todo = pre[pre["link_tier"].isin(OPEN_TIERS)]
    cand = todo[keys + ["class_year"]].merge(lookup, on=keys, how="left")
    cand.index = todo.index
    cand["name_city"] = todo["name"].fillna("") + "|" + todo["city"].fillna("")
    ok = cand["n_codes"] == 1
    bad = taken_or_contested(df, cand, ok)
    note_candidate(df, bad[bad].index, cand.loc[bad[bad].index, "code"], "other_year")
    ok &= ~bad
    idx = ok[ok].index
    df.loc[idx, "code_linked"] = cand.loc[idx, "code"]
    df.loc[idx, "link_tier"] = "other_year"
    print(f"  other_year: linked {len(idx):,} of {len(todo):,} remaining records; rejected {int(bad.sum()):,}")


def main():
    con = duckdb.connect()
    df = con.execute(f"SELECT class_year, source_file, row_in_file, school_code, name, city, state "
                     f"FROM read_parquet('{PANEL.as_posix()}')").df()
    print(f"FSA records read: {len(df):,} ({df['school_code'].notna().sum():,} with a School Code)")
    df["name_norm"] = df["name"].map(normalize)
    df["city_norm"] = df["city"].map(normalize)

    # Lookup tables from coded records: each key -> its distinct codes.
    coded = df[df["school_code"].notna()]
    tiers = [
        ("exact", ["state", "name", "city"]),
        ("normalized", ["state", "name_norm", "city_norm"]),
        ("name_only", ["state", "name_norm"]),
    ]
    df["code_linked"] = df["school_code"]
    df["link_tier"] = df["school_code"].notna().map({True: "fsa_code", False: None})
    df["n_candidate_codes"] = pd.array([pd.NA] * len(df), dtype="Int64")
    for c in ["candidate_code", "candidate_tier", "ccd_name", "ccd_city", "pss_name", "pss_city"]:
        df[c] = pd.Series(pd.NA, index=df.index, dtype="string")

    for tier, keys in tiers:
        lookup = (coded.dropna(subset=keys).groupby(keys)["school_code"]
                  .agg(n_codes="nunique", code="first",
                       codes=lambda c: "|".join(sorted(set(c)))).reset_index())
        todo = df["link_tier"].isna()
        cand = df.loc[todo, keys].merge(lookup, on=keys, how="left")
        cand.index = df.index[todo]
        unique = cand["n_codes"] == 1
        if tier == "name_only":
            # Common names (e.g. ST PAUL LUTHERAN HIGH SCHOOL) recur in other
            # cities. Reject a name-only link if the code is already taken in
            # that class by an exact/normalized link, or if several different
            # name+city records compete for it in the same class.
            cand["class_year"] = df.loc[todo, "class_year"]
            cand["name_city"] = df.loc[todo, "name"].fillna("") + "|" + df.loc[todo, "city"].fillna("")
            conflict = taken_or_contested(df, cand, unique)
            df.loc[conflict[conflict].index, "link_tier"] = "name_only_rejected"
            note_candidate(df, conflict[conflict].index, cand.loc[conflict, "code"], tier)
            print(f"  tier name_only : rejected {conflict.sum():,} links whose code is taken or contested in that class")
            unique &= ~conflict
        df.loc[unique[unique].index, "code_linked"] = cand.loc[unique, "code"]
        df.loc[unique[unique].index, "link_tier"] = tier
        df.loc[cand.index[cand["n_codes"] > 0], "n_candidate_codes"] = cand.loc[cand["n_codes"] > 0, "n_codes"].astype("Int64")
        multi = cand["n_codes"] > 1
        note_candidate(df, cand.index[multi], cand.loc[multi, "codes"], tier)
        print(f"  tier {tier:<10}: linked {unique.sum():,} of {todo.sum():,} uncoded records; "
              f"{(cand['n_codes'] > 1).sum():,} ambiguous (key has several codes)")

    still = df["link_tier"].isna()
    df.loc[still & (df["n_candidate_codes"] > 1), "link_tier"] = "ambiguous"
    df.loc[df["link_tier"].isna(), "link_tier"] = "unlinked"

    print("\nChecking FSA-tier links against each class's senior-year CCD/PSS:")
    check_against_year_directory(df)
    print("\nMatching records still without a code to the CCD directory (public schools):")
    link_to_directory(df, "ccd", read_ccd_directory)
    print("\nMatching records still without a code to the PSS (private schools):")
    link_to_directory(df, "pss", read_pss)
    print("\nMatching remaining records to codes their names got in other classes:")
    link_from_other_years(df)

    # Candidate codes are kept only for records that ended up without a code.
    linked_now = df["link_tier"].isin(LINKED)
    df.loc[linked_now, ["candidate_code", "candidate_tier"]] = pd.NA

    out = df[["class_year", "source_file", "row_in_file", "state", "name", "city",
              "school_code", "code_linked", "link_tier", "n_candidate_codes",
              "candidate_code", "candidate_tier", "ccd_name", "ccd_city", "pss_name", "pss_city"]]
    out.to_parquet(OUT, index=False)
    print(f"\nWrote {OUT.name}: {len(out):,} rows (one per FSA record; nothing dropped)")

    # Summary for the study states, pre-2021 classes, weighted by completions.
    con.execute(f"CREATE VIEW c AS SELECT * FROM read_parquet('{OUT.as_posix()}')")
    con.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{PANEL.as_posix()}')")
    states = ", ".join(f"'{s}'" for s in STUDY_STATES)
    summary = con.execute(f"""
        SELECT c.state, c.link_tier, count(*) AS records, sum(coalesce(p.completed_jun, 0)) AS completions
        FROM c JOIN p USING (class_year, source_file, row_in_file)
        WHERE c.state IN ({states}) AND c.class_year <= 2020
        GROUP BY ALL
    """).df()
    recs = summary.pivot_table(index="state", columns="link_tier", values="records", fill_value=0)
    recs = recs.reindex(STUDY_STATES)
    recs = recs[[t for t in LINKED + ("name_only_rejected", "ambiguous", "unlinked") if t in recs.columns]]
    shares = recs.div(recs.sum(axis=1), axis=0).round(3)
    comp = summary.pivot_table(index="state", columns="link_tier", values="completions", fill_value=0).reindex(STUDY_STATES)
    linked_comp = comp.drop(columns=["unlinked", "ambiguous", "name_only_rejected"], errors="ignore").sum(axis=1) / comp.sum(axis=1)
    shares["completions_linked"] = linked_comp.round(3)
    print("\nStudy states, classes 2015-2020: share of records by tier, and share of completions linked")
    print(shares.drop(columns="fsa_code", errors="ignore").to_string())

    # A linked code shared by several name+city records in one class is fine
    # when FSA itself codes those records alike from 2021 on (multi-site and
    # renamed schools); otherwise it points to a bad link.
    shared = con.execute("""
        WITH g AS (
            SELECT class_year, code_linked, name, city FROM c
            WHERE link_tier IN ('exact', 'normalized', 'name_only')),
        multi AS (
            SELECT class_year, code_linked FROM g GROUP BY ALL HAVING count(DISTINCT (name, city)) > 1),
        post AS (
            SELECT DISTINCT school_code AS code_linked, name, city FROM c WHERE link_tier = 'fsa_code')
        SELECT count(*) AS pairs, count(*) FILTER (WHERE NOT mirrored) AS not_in_fsa_coding
        FROM (SELECT m.class_year, m.code_linked, bool_and(p.name IS NOT NULL) AS mirrored
              FROM multi m JOIN g USING (class_year, code_linked)
              LEFT JOIN post p USING (code_linked, name, city) GROUP BY ALL)
    """).fetchone()
    print(f"\n(class, linked code) pairs shared by several name+city records: {shared[0]:,}; "
          f"of these, not mirrored in FSA's own 2021+ coding: {shared[1]:,}")


if __name__ == "__main__":
    main()
