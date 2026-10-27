"""Build a school x graduating-class panel of FAFSA completions from the FSA files.

Reads every FSA "FAFSA Completion by High School" archive in
data/raw/US/fsa_fafsa_completion/ and writes data/derived/fsa_fafsa_hs.parquet,
one row per FSA school record per graduating class, for all states.

Which column is which class (see docs/source-notes.md):
  - Each file has fixed prior-cycle columns headed "Applications Submitted Jun
    YYYY" / "Complete Jun YYYY" and "... Dec YYYY". These are the 9- and
    15-month counts for the class of YYYY. They are revised slightly between
    files, so each class is taken from the newest file that carries it (the
    Dec 31 file of YYYY+1, or the newest June file for the latest class).
  - The current-cycle column "... Jun30 YYYY" in a June 30 file is a running
    count for the class of YYYY. It is used only for a class that has no fixed
    columns in any file yet, and is flagged as preliminary.
Counts below 5 are published as "<5"; they are stored as missing with a flag,
not imputed.

Usage (from the repository root):
    uv run --locked python code/01_clean_fsa.py
"""

import re

import duckdb
import pandas as pd

from config import DERIVED, RAW

FSA_DIR = RAW / "US" / "fsa_fafsa_completion"
OUT = DERIVED / "fsa_fafsa_hs.parquet"
SHEET = "School Level Data"
HEADER_ROW = 3  # rows 0-2 are the title, cycle labels, and date labels
STUDY_STATES = ["LA", "IL", "AL", "TX", "CO", "MD", "CA", "IN", "NH",
                "NE", "OK", "NY", "NJ", "CT", "PA"]

# Header names, e.g. "Applications\nComplete\nJun  2018" or "...Jun30  2026".
# "Jun"/"Dec" with no day are the fixed prior-cycle columns; "Jun30" is the
# current-cycle running count in a June 30 file.
COUNT_COL = re.compile(r"Applications\s+(Submitted|Complete)\s+(Jun|Dec|Jun30|Dec31)\s+(\d{4})")


def parse_count(value):
    """Return (count, suppressed) for one published cell: "<5" is suppressed."""
    if pd.isna(value):
        return None, False
    text = str(value).strip()
    if text == "<5":
        return None, True
    if not text.isdigit():
        raise ValueError(f"unexpected FSA count value: {value!r}")
    return int(text), False


def find_columns(columns):
    """Map each count column header to (measure, period, year).

    measure is "submitted" or "completed"; period is "jun"/"dec" (fixed
    prior-cycle) or "jun30"/"dec31" (current-cycle running count).
    """
    found = {}
    for col in columns:
        m = COUNT_COL.fullmatch(re.sub(r"\s+", " ", str(col)).strip())
        if m:
            measure = "submitted" if m[1] == "Submitted" else "completed"
            found[col] = (measure, m[2].lower(), int(m[3]))
    return found


def read_file(path):
    """Read one FSA file and return its rows as (class, measure set) records.

    Returns a DataFrame with one row per school record and class found in the
    file: the fixed prior-cycle class (kind "final") and, in a June 30 file,
    the current-cycle class (kind "preliminary").
    """
    snapshot = pd.Timestamp(re.search(r"(\d{4}-\d{2}-\d{2})", path.name)[1])
    df = pd.read_excel(path, sheet_name=SHEET, header=HEADER_ROW, dtype=str)
    cols = find_columns(df.columns)
    school_code = df["School Code"] if "School Code" in df.columns else pd.Series(pd.NA, index=df.index)
    school_code = school_code.str.strip()
    # All-zero codes ("000", "000000000000") are placeholders shared by
    # hundreds of schools, not IDs; treat them as missing.
    school_code = school_code.mask(school_code.str.fullmatch(r"0+", na=False))
    base = pd.DataFrame({
        "school_code": school_code,
        "name": df["Name"].str.strip(),
        "city": df["City"].str.strip(),
        "state": df["State"].str.strip(),
        "row_in_file": range(len(df)),
    })

    # Group the count columns into classes: fixed columns by their year, plus
    # the current-cycle Jun30 column of a June file (Dec31 columns are running
    # counts already covered by later fixed columns, so they are not used).
    groups = {}
    for col, (measure, period, year) in cols.items():
        if period in ("jun", "dec"):
            groups.setdefault((year, "final"), {})[f"{measure}_{period}"] = col
        elif period == "jun30" and snapshot.month == 6 and year == snapshot.year:
            groups.setdefault((year, "preliminary"), {})[f"{measure}_jun"] = col

    out = []
    for (year, kind), measures in groups.items():
        part = base.copy()
        part["class_year"] = year
        part["kind"] = kind
        for name in ["submitted_jun", "completed_jun", "submitted_dec", "completed_dec"]:
            parsed = (df[measures[name]].map(parse_count) if name in measures
                      else pd.Series([(None, False)] * len(df), index=df.index))
            part[name] = pd.array([p[0] for p in parsed], dtype="Int64")
            part[name + "_lt5"] = [p[1] for p in parsed]
        out.append(part)
    result = pd.concat(out, ignore_index=True)
    result["snapshot_date"] = snapshot
    result["source_file"] = path.name
    return result


def main():
    files = sorted(FSA_DIR.glob("fafsa_hs_*.xls*"))
    print(f"Reading {len(files)} FSA files from {FSA_DIR.relative_to(RAW.parent.parent)}")
    frames = []
    for path in files:
        df = read_file(path)
        classes = ", ".join(f"{y} ({k})" for y, k in
                            df[["class_year", "kind"]].drop_duplicates().itertuples(index=False))
        print(f"  {path.name}: {df['row_in_file'].nunique():,} school rows; classes {classes}")
        frames.append(df)
    allrows = pd.concat(frames, ignore_index=True)
    print(f"\nRows across files (school x class x file): {len(allrows):,}")

    # Keep one source per class: the newest file with fixed columns for it;
    # a preliminary count only where no file has fixed columns yet.
    src = (allrows[["class_year", "kind", "snapshot_date"]].drop_duplicates()
           .assign(rank=lambda d: d["kind"].map({"final": 0, "preliminary": 1}))
           .sort_values(["class_year", "rank", "snapshot_date"], ascending=[True, True, False])
           .drop_duplicates("class_year"))
    panel = allrows.merge(src[["class_year", "kind", "snapshot_date"]],
                          on=["class_year", "kind", "snapshot_date"])
    print(f"After keeping one source file per class: {len(panel):,} rows "
          f"(dropped {len(allrows) - len(panel):,} rows for classes also in a newer file)")
    for r in src.sort_values("class_year").itertuples(index=False):
        print(f"  class of {r.class_year}: {r.kind:<11} from {r.snapshot_date.date()}")

    panel = panel.sort_values(["class_year", "state", "name", "city", "row_in_file"]).reset_index(drop=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(OUT, index=False)
    print(f"\nWrote {OUT.relative_to(DERIVED.parent.parent)}: {len(panel):,} rows")

    # Checks, reported but not enforced; nothing is dropped here.
    con = duckdb.connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{OUT.as_posix()}')")
    print("\nChecks (all states):")
    for label, sql in [
        ("completed > submitted (through June)",
         "SELECT count(*) FROM p WHERE completed_jun > submitted_jun"),
        ("completed > submitted (through December)",
         "SELECT count(*) FROM p WHERE completed_dec > submitted_dec"),
        ("December count < June count (completed)",
         "SELECT count(*) FROM p WHERE completed_dec < completed_jun"),
        ("missing school name", "SELECT count(*) FROM p WHERE name IS NULL"),
        ("duplicate state+name+city within a class",
         "SELECT coalesce(sum(n - 1), 0) FROM (SELECT count(*) n FROM p "
         "GROUP BY class_year, state, name, city HAVING n > 1)"),
        ("duplicate school code within a class",
         "SELECT coalesce(sum(n - 1), 0) FROM (SELECT count(*) n FROM p WHERE school_code IS NOT NULL "
         "GROUP BY class_year, school_code HAVING n > 1)"),
    ]:
        print(f"  {label}: {con.execute(sql).fetchone()[0]:,}")

    states = ", ".join(f"'{s}'" for s in STUDY_STATES)
    print("\nStudy states: school records by class (share of completed_jun suppressed as <5)")
    summary = con.execute(f"""
        SELECT state, class_year, count(*) AS n,
               round(avg(completed_jun_lt5::INT), 3) AS lt5_share
        FROM p WHERE state IN ({states})
        GROUP BY state, class_year
    """).df()
    wide = summary.pivot(index="state", columns="class_year", values="n").reindex(STUDY_STATES)
    print(wide.to_string())
    lt5 = summary.groupby("state")["lt5_share"].mean().reindex(STUDY_STATES).round(3)
    print("\nMean share suppressed (<5), completed through June:")
    print(lt5.to_string())


if __name__ == "__main__":
    main()
