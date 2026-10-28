"""Build a school x year panel of NCES CCD characteristics for the 15 study states.

Reads, for each school year 2014-15 to 2024-25 in data/raw/US/nces_ccd_school/:
  029 Directory              name, district, type, charter, grade span, status
  129 School Characteristics virtual status, Title I, NSLP status
  052 Membership             enrollment total, grades 9-12, race/ethnicity
  033 Lunch                  free/reduced-price lunch, direct certification
  059 Staff                  teacher FTE
and the NCES EDGE school locale code from data/raw/US/nces_edge_locations/.

Files are streamed with the system `unzip -p` (several Membership zips use
Deflate64, which Python's zipfile cannot read), so data/raw is not changed.
Two Membership zips (2017-18, 2021-22) hold a further CSV zip inside; that
inner zip is copied to a temporary directory, which is deleted afterwards. Files through 2015-16 have one column per item
("wide"); from 2016-17 they have one row per category ("long"). CCD's negative
codes (-1 missing, -2 not applicable, -9 suppressed, ...) become missing.

Rows are schools open that year (CCD also lists a school in the year it
closes). class_year is the spring year of the school year, so grade-12
enrollment in class_year is the senior class of that graduating class.
school_id follows code/school_ids.py, so it matches fsa_school_panel.parquet.

Writes data/derived/ccd_school_panel.parquet (key: school_id, class_year).

Usage (from the repository root):
    uv run --locked python code/05_build_ccd_school_panel.py
"""

import io
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pandas as pd

from config import DERIVED, RAW
from school_ids import stable_ids

CCD_DIR = RAW / "US" / "nces_ccd_school"
EDGE_DIR = RAW / "US" / "nces_edge_locations"
OUT = DERIVED / "ccd_school_panel.parquet"
FIRST_YEAR, LAST_YEAR = 2015, 2025   # class years (spring of 2014-15 ... 2024-25)
STUDY_STATES = ["LA", "IL", "AL", "TX", "CO", "MD", "CA", "IN", "NH",
                "NE", "OK", "NY", "NJ", "CT", "PA"]
CHUNK = 500_000
RACES = {"AM": "american_indian", "AS": "asian", "HI": "hispanic", "BL": "black",
         "WH": "white", "HP": "pacific_islander", "TR": "two_or_more"}
RACE_LABELS = {"American Indian or Alaska Native": "AM", "Asian": "AS", "Hispanic/Latino": "HI",
               "Black or African American": "BL", "White": "WH",
               "Native Hawaiian or Other Pacific Islander": "HP", "Two or more races": "TR"}
GRADE_LABELS = {"Grade 9": "G09", "Grade 10": "G10", "Grade 11": "G11", "Grade 12": "G12"}
GRADE_NUM = {"PK": -1, "KG": 0, **{f"{g:02d}": g for g in range(1, 14)}}
OPEN_STATUSES = {"open", "new", "added", "changed boundary/agency", "reopened"}
# CCD renamed school types in 2016-17; map both versions to one label.
SCHOOL_TYPES = {
    "regular school": "regular", "special education school": "special_education",
    "vocational education school": "career_technical", "career and technical school": "career_technical",
    "alternative education school": "alternative", "alternative school": "alternative",
}


def member(folder, component, tmp=None):
    """Return (zip path, member name) for one CCD component of a school year.

    If the zip holds a CSV zip rather than a CSV (2017-18, 2021-22 Membership),
    the inner zip is copied into tmp, a temporary directory, and used instead.
    """
    zips = [p for p in folder.iterdir() if re.match(rf"ccd_sch_{component}_", p.name, re.I)]
    if len(zips) != 1:
        raise FileNotFoundError(f"expected one ccd_sch_{component} zip in {folder}, found {len(zips)}")
    with zipfile.ZipFile(zips[0]) as z:
        names = z.namelist()
    tables = [n for n in names if n.lower().endswith((".csv", ".txt"))]
    if tables:
        return zips[0], tables[0]
    inner = next(n for n in names if n.lower().endswith(".zip") and "csv" in n.lower())
    if tmp is None:
        return zips[0], inner
    target = Path(tmp) / Path(inner).name
    with open(target, "wb") as f:
        subprocess.run(["unzip", "-p", str(zips[0]), inner], stdout=f, check=True)
    with zipfile.ZipFile(target) as z:
        name = next(n for n in z.namelist() if n.lower().endswith((".csv", ".txt")))
    return target, name


def stream(folder, component, keep_cols, row_filter=None):
    """Read one CCD component via `unzip -p`, keeping study-state rows and keep_cols."""
    with tempfile.TemporaryDirectory() as tmp:
        return _stream(folder, component, keep_cols, row_filter, tmp)


def _stream(folder, component, keep_cols, row_filter, tmp):
    """Body of stream(); tmp holds any inner zip until reading is finished."""
    path, name = member(folder, component, tmp)
    proc = subprocess.Popen(["unzip", "-p", str(path), name], stdout=subprocess.PIPE)
    sep = "\t" if name.lower().endswith(".txt") else ","
    parts = []
    reader = pd.read_csv(proc.stdout, sep=sep, dtype=str, encoding="latin-1", chunksize=CHUNK,
                         usecols=lambda c: c.strip().upper() in keep_cols)
    for chunk in reader:
        chunk.columns = chunk.columns.str.strip().str.upper()
        chunk = chunk.rename(columns={"STABR": "ST"})
        chunk = chunk[chunk["ST"].isin(STUDY_STATES)]
        if row_filter is not None:
            chunk = chunk[row_filter(chunk)]
        parts.append(chunk)
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"unzip failed ({proc.returncode}) on {path.name}")
    return pd.concat(parts, ignore_index=True)


def num(s):
    """Convert a CCD count column to numbers, with CCD's negative codes as missing."""
    x = pd.to_numeric(s, errors="coerce")
    return x.mask(x < 0)


def read_directory(folder):
    """Directory (029) and school characteristics (129) for one year."""
    d = stream(folder, "029", {"NCESSCH", "SCH_NAME", "ST", "STABR", "LEAID", "LEA_NAME", "LCITY",
                               "SCH_TYPE_TEXT", "CHARTER_TEXT", "LEVEL", "GSLO", "GSHI",
                               "SY_STATUS_TEXT", "VIRTUAL"})
    c = stream(folder, "129", {"NCESSCH", "ST", "STABR", "VIRTUAL", "VIRTUAL_TEXT", "TITLEI_STATUS_TEXT",
                               "TITLEI_TEXT", "NSLP_STATUS_TEXT", "NSLPSTATUS_TEXT"})
    c = c.rename(columns={"TITLEI_TEXT": "TITLEI_STATUS_TEXT", "NSLPSTATUS_TEXT": "NSLP_STATUS_TEXT"})
    if "VIRTUAL_TEXT" in c:
        c = c.drop(columns="VIRTUAL", errors="ignore").rename(columns={"VIRTUAL_TEXT": "VIRTUAL"})
    if "VIRTUAL" in d and "VIRTUAL" in c:
        c = c.drop(columns="VIRTUAL")
    d = d.merge(c.drop(columns="ST"), on="NCESSCH", how="left")
    for col in ["VIRTUAL", "TITLEI_STATUS_TEXT", "NSLP_STATUS_TEXT"]:
        if col not in d:
            d[col] = pd.NA
    return d


def read_membership(folder):
    """Membership (052): total, grades 9-12, and race counts per school."""
    path, _ = member(folder, "052")
    if "_w_" in path.name.lower():   # wide: one column per item
        cols = {"NCESSCH", "ST", "STABR", "TOTAL", "MEMBER", "G09", "G10", "G11", "G12", *RACES}
        m = stream(folder, "052", cols)
        total = m["TOTAL"] if "TOTAL" in m else m["MEMBER"]
        out = pd.DataFrame({"NCESSCH": m["NCESSCH"], "enroll_total": num(total),
                            **{f"enroll_{g.lower()}": num(m[g]) for g in GRADE_LABELS.values()},
                            **{f"race_{RACES[r]}": num(m[r]) for r in RACES}})
        return out
    keep = {"Education Unit Total", "Subtotal 4 - By Grade",
            "Derived - Subtotal by Race/Ethnicity and Sex minus Adult Education Count"}
    m = stream(folder, "052", {"NCESSCH", "ST", "GRADE", "RACE_ETHNICITY", "SEX", "STUDENT_COUNT",
                               "TOTAL_INDICATOR"}, lambda c: c["TOTAL_INDICATOR"].isin(keep))
    m["n"] = num(m["STUDENT_COUNT"])
    total = m[m["TOTAL_INDICATOR"] == "Education Unit Total"].groupby("NCESSCH")["n"].sum(min_count=1)
    g = m[(m["TOTAL_INDICATOR"] == "Subtotal 4 - By Grade") & m["GRADE"].isin(GRADE_LABELS)]
    grades = g.assign(col=g["GRADE"].map(GRADE_LABELS).str.lower().radd("enroll_")) \
        .pivot_table(index="NCESSCH", columns="col", values="n", aggfunc="sum")
    r = m[m["TOTAL_INDICATOR"].str.startswith("Derived - Subtotal by Race") & m["RACE_ETHNICITY"].isin(RACE_LABELS)]
    races = r.assign(col=r["RACE_ETHNICITY"].map(RACE_LABELS).map(RACES).radd("race_")) \
        .pivot_table(index="NCESSCH", columns="col", values="n", aggfunc="sum")
    out = pd.concat([total.rename("enroll_total"), grades, races], axis=1).reset_index()
    for col in [f"enroll_{g.lower()}" for g in GRADE_LABELS.values()] + [f"race_{v}" for v in RACES.values()]:
        if col not in out:
            out[col] = pd.NA
    return out


def read_lunch(folder):
    """Lunch (033): free, reduced-price, total FRL, and direct certification counts."""
    path, _ = member(folder, "033")
    if "_w_" in path.name.lower():
        m = stream(folder, "033", {"NCESSCH", "ST", "STABR", "TOTFRL", "FRELCH", "REDLCH"})
        return pd.DataFrame({"NCESSCH": m["NCESSCH"], "frl_free": num(m["FRELCH"]),
                             "frl_reduced": num(m["REDLCH"]), "frl_total": num(m["TOTFRL"]),
                             "direct_cert": pd.NA})
    m = stream(folder, "033", {"NCESSCH", "ST", "DATA_GROUP", "LUNCH_PROGRAM", "STUDENT_COUNT", "TOTAL_INDICATOR"})
    m["n"] = num(m["STUDENT_COUNT"])
    pick = {
        "frl_free": (m["LUNCH_PROGRAM"] == "Free lunch qualified"),
        "frl_reduced": (m["LUNCH_PROGRAM"] == "Reduced-price lunch qualified"),
        "frl_total": (m["DATA_GROUP"].str.startswith("Free and Reduced")
                      & (m["TOTAL_INDICATOR"] == "Education Unit Total")),
        "direct_cert": (m["DATA_GROUP"] == "Direct Certification"),
    }
    out = pd.concat([m[mask].groupby("NCESSCH")["n"].sum(min_count=1).rename(k) for k, mask in pick.items()],
                    axis=1)
    return out.reset_index()


def read_staff(folder):
    """Staff (059): teacher FTE."""
    path, _ = member(folder, "059")
    if "_w_" in path.name.lower():
        m = stream(folder, "059", {"NCESSCH", "ST", "STABR", "FTE"})
        return pd.DataFrame({"NCESSCH": m["NCESSCH"], "teachers_fte": num(m["FTE"])})
    m = stream(folder, "059", {"NCESSCH", "ST", "TEACHERS", "TOTAL_INDICATOR"},
               lambda c: c["TOTAL_INDICATOR"] == "Education Unit Total")
    return m.assign(teachers_fte=num(m["TEACHERS"]))[["NCESSCH", "teachers_fte"]]


def read_locale(class_year):
    """EDGE urban-centric locale code (2 digits) by NCES ID for one school year."""
    yy = f"{(class_year - 1) % 100:02d}{class_year % 100:02d}"
    if class_year == 2015:
        with zipfile.ZipFile(EDGE_DIR / "EDGE_GEOIDS_201415_PUBLIC_SCHOOL_csv.zip") as z:
            d = pd.read_csv(z.open("EDGE_GEOIDS_201415_PUBLIC_SCHOOL.csv"), dtype=str,
                            encoding="latin-1", usecols=["NCESSCH", "LOCALE"])
    else:
        path = EDGE_DIR / f"EDGE_GEOCODE_PUBLICSCH_{yy}.zip"
        if not path.exists():
            return pd.DataFrame(columns=["NCESSCH", "locale"])
        with zipfile.ZipFile(path) as z:
            name = next(n for n in z.namelist() if n.lower().endswith(".sas7bdat"))
            d = pd.read_sas(io.BytesIO(z.read(name)), format="sas7bdat", encoding="latin-1")
        d.columns = d.columns.str.upper()
        # 2015-16 names the column LOCALE15; later years LOCALE.
        d = d.rename(columns={c: "LOCALE" for c in d.columns if re.fullmatch(r"LOCALE\d*", c)})
        d = d[["NCESSCH", "LOCALE"]].astype(str)
    return d.rename(columns={"LOCALE": "locale"}).assign(locale=lambda x: x["locale"].str.strip().str[:2])


def grade_count(lo, hi):
    """Number of grades offered from GSLO to GSHI (PK counts as a grade)."""
    a, b = GRADE_NUM.get(str(lo).strip()), GRADE_NUM.get(str(hi).strip())
    return b - a + 1 if a is not None and b is not None and b >= a else pd.NA


def build_year(class_year):
    """All CCD components for one school year, one row per open school."""
    folder = CCD_DIR / f"{class_year - 1}-{class_year}"
    d = read_directory(folder)
    n0 = len(d)
    d = d[d["SY_STATUS_TEXT"].fillna("").str.strip().str.lower().isin(OPEN_STATUSES)]
    parts = [read_membership(folder), read_lunch(folder), read_staff(folder), read_locale(class_year)]
    for p in parts:
        d = d.merge(p, on="NCESSCH", how="left")
    print(f"  {folder.name}: {n0:,} schools listed, {len(d):,} open "
          f"(dropped {n0 - len(d):,} closed/inactive/future); "
          f"with enrollment {d['enroll_total'].notna().sum():,}, locale {d['locale'].notna().sum():,}")
    d["class_year"] = class_year
    return d


def main():
    print(f"CCD school years {FIRST_YEAR - 1}-{FIRST_YEAR} to {LAST_YEAR - 1}-{LAST_YEAR}, study states only")
    df = pd.concat([build_year(y) for y in range(FIRST_YEAR, LAST_YEAR + 1)], ignore_index=True)

    mapping = stable_ids(sorted(df["NCESSCH"].unique()))
    df["school_id"] = df["NCESSCH"].map(mapping)
    out = pd.DataFrame({
        "school_id": df["school_id"], "nces_id": df["NCESSCH"], "class_year": df["class_year"],
        "state": df["ST"], "name": df["SCH_NAME"], "lea_id": df["LEAID"], "lea_name": df["LEA_NAME"],
        "city": df["LCITY"], "school_type": df["SCH_TYPE_TEXT"],
        "school_type_std": df["SCH_TYPE_TEXT"].str.strip().str.lower().map(SCHOOL_TYPES),
        "charter": df["CHARTER_TEXT"].str.strip().str.lower().map({"yes": True, "no": False}),
        "virtual": df["VIRTUAL"], "level": df["LEVEL"], "gslo": df["GSLO"], "gshi": df["GSHI"],
        "n_grades": [grade_count(a, b) for a, b in zip(df["GSLO"], df["GSHI"])],
        "title_i": df["TITLEI_STATUS_TEXT"], "nslp_status": df["NSLP_STATUS_TEXT"], "locale": df["locale"],
        **{c: df[c] for c in df.columns if c.startswith(("enroll_", "race_", "frl_"))},
        "direct_cert": df["direct_cert"], "teachers_fte": df["teachers_fte"],
    })
    out["n_grades"] = out["n_grades"].astype("Int64")
    count_cols = [c for c in out.columns if c.startswith(("enroll_", "race_", "frl_"))] + ["direct_cert"]
    for c in count_cols:
        out[c] = pd.to_numeric(out[c]).astype("Int64")
    out["teachers_fte"] = pd.to_numeric(out["teachers_fte"]).astype("Float64")

    dup = out.duplicated(["school_id", "class_year"]).sum()
    if dup:
        raise ValueError(f"{dup} duplicate (school_id, class_year) rows")
    out = out.sort_values(["state", "school_id", "class_year"]).reset_index(drop=True)
    out.to_parquet(OUT, index=False)
    print(f"\nWrote {OUT.name}: {len(out):,} school x year rows, {out['school_id'].nunique():,} schools")

    hs = out[out["enroll_g12"] > 0]
    print("\nSchools with grade-12 enrollment, by state and class year:")
    print(hs.pivot_table(index="state", columns="class_year", values="school_id", aggfunc="count")
          .reindex(STUDY_STATES).to_string())
    print("\nShare missing among schools with grade-12 enrollment (all years):")
    miss = hs[["enroll_total", "race_white", "frl_total", "direct_cert", "teachers_fte", "locale",
               "virtual", "title_i"]].isna().mean().round(3)
    print(miss.to_string())


if __name__ == "__main__":
    main()
