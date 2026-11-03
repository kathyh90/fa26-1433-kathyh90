"""State data files: readers, linking to CCD, and the content review.

Imported by 07_build_state_outcomes.py for the readers. Each reader turns one
state source's raw files into one row per school x class with the state's own
school code (`code`), the graduating class (`class_year`, spring year), and the
published measures. A published bound (e.g. '>99', '<=1') is read as its
number and its direction is kept in a `<column>_bound` column ('>' or '<').

Run as a script, it is the content review: for each state (in mandate order)
and source it reports, per class, how the file's school rows link to CCD and
cover the panel (columns of the output defined in code/README.md):
  n_rows                   school rows in the file (district and state rows excluded)
  n_matched_ccd_same_year  rows whose state code matches a CCD school that year
  n_matched_ccd_overall    rows matched that year or by the same code in any year
  panel_schools            public schools in the analysis panel with grade-12 enrollment
  panel_covered            of those, how many have a row in the state file
  graduates                sum of the file's graduate count, where it has one
Nothing is saved to data/derived. Findings are recorded in docs/source-notes.md.

Usage (from the repository root):
    uv run --locked python code/state_files.py [STATES ...]   # review; writes
        output/tables/state_file_review.csv when run for all reviewed states
"""

import re
import sys
import tempfile
import zipfile

import duckdb
import openpyxl
import pandas as pd
from access_parser import AccessParser

from config import DERIVED, OUTPUT, RAW, STUDY_STATES
from matching import distinctive, normalize

REVIEW_OUT = OUTPUT / "tables" / "state_file_review.csv"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def sheet_rows(path, sheet=None):
    """Yield each row of a worksheet as a list of stripped strings ("" for empty)."""
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb[sheet] if sheet else wb.active
    for r in ws.iter_rows(values_only=True):
        yield ["" if c is None else str(c).strip() for c in r]


# A published bound instead of a value: '>99', '>=99', '>= 99', '≥99', '<1', '≤1'.
CENSORED = re.compile(r"^\s*(?:[<>]=?|[≤≥])\s*")


def value(cell):
    """Parse a published number: '~', 'NR', 'n/a', '' -> NaN; a bound such as '>99'
    or '<=1' -> the bound (its direction is given by bound()); '45.2%' -> 45.2."""
    s = CENSORED.sub("", str(cell).strip()).rstrip("%").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return float("nan")


def bound(cell):
    """Direction of a published bound: '>' for '>99', '>=99', '≥99'; '<' for '<1',
    '<=1', '≤1'; '' for an exact value or a code."""
    s = str(cell).strip()
    return ">" if s[:1] in (">", "≥") else "<" if s[:1] in ("<", "≤") else ""


def midpoint(v, b):
    """Deneault's coding of a bounded percent: above a bound -> halfway to 100
    ('>99' -> 99.5, '>95' -> 97.5); below a bound -> half of it ('<1' -> 0.5,
    '<5' -> 2.5); exact values unchanged. Works on Series (v numbers, b bounds)."""
    return v.where(b == "", ((v + 100) / 2).where(b == ">", v / 2))


def class_of(label):
    """Graduating class from a school-year label: '2015-2016' or '2015-16' -> 2016."""
    a, _ = re.search(r"(20\d\d)\s*-\s*(\d{2,4})", label).groups()
    return int(a) + 1


def ccd_codes():
    """CCD state school codes: one row per (state, class_year, code) with the NCES ID.
    The code is the last '-' segment of ST_SCHID, whose format varies by year."""
    return duckdb.sql(f"""
        select state, class_year, nces_id, school_id, name, st_schid, lea_name, gshi, city,
               regexp_extract(st_schid, '([^-]+)$', 1) as code
        from '{DERIVED / "ccd_school_panel.parquet"}'
    """).df()


def link(state, rows, ccd, aliases=None, normalize=None, ccd_key=None):
    """Attach school_id to state school rows: by state code in CCD the same class
    year, else by the code in CCD in any year (most recent), since states reuse a
    school's code while CCD's ST_SCHID can change (e.g. a charter changing LEA).
    aliases maps a state-file code to the code CCD uses for the same school;
    normalize (a function) rewrites codes on both sides to one form first;
    ccd_key (a function of the state's CCD rows returning one key per row)
    replaces the default CCD code (ST_SCHID's last segment), e.g. where that
    segment is not unique (Alabama) or the state file has names, not codes
    (Maryland).
    Adds `school_id` and `link` ('same_year', 'any_year', or '' if unmatched)."""
    c = ccd[ccd["state"] == state]
    if ccd_key:
        c = c.assign(code=list(ccd_key(c)))
    key = rows["code"].replace(aliases or {})
    if normalize:
        c = c.assign(code=c["code"].map(normalize))
        key = key.map(normalize)
    # A key shared by two CCD schools in the same year is ambiguous: no match.
    c = c.dropna(subset=["code"])
    c = c[~c.duplicated(["class_year", "code"], keep=False)]
    m = rows.assign(_key=key).merge(c[["class_year", "code", "school_id"]].rename(columns={"code": "_key"}),
                                     on=["class_year", "_key"], how="left", validate="m:1")
    latest = (c.dropna(subset=["code"]).sort_values("class_year")
              .drop_duplicates("code", keep="last").set_index("code")["school_id"])
    m["link"] = m["school_id"].notna().map({True: "same_year", False: ""})
    m["school_id"] = m["school_id"].fillna(m["_key"].map(latest))
    m.loc[(m["link"] == "") & m["school_id"].notna(), "link"] = "any_year"
    return m.drop(columns="_key")


# Name matching, for state files without a school number (NE CCPE, OK OSRHE).
# A state school -> CCD code, tried in order (first unique match wins): exact
# normalized name, then distinctive name words (spaces dropped: 'McCook' = 'MC
# COOK'), each within the area (district or county) in the same year, else any
# year; last, the area's only CCD high school, used only where the state file
# lists one school in that area and year.
NAME_STEPS = [("exact_same_year", ["exact", "class_year"]), ("exact_any_year", ["exact"]),
              ("words_same_year", ["words", "class_year"]), ("words_any_year", ["words"]),
              ("only_hs_same_year", ["class_year"]), ("only_hs_any_year", [])]


def name_keys(names):
    """(exact, words) match keys of school names."""
    exact = names.map(normalize)
    return exact, exact.map(lambda n: "".join(distinctive(n)))


ne_name_keys = name_keys   # name used by the Nebraska test


def name_codes(d, c, area):
    """CCD code of each state-file row d by NAME_STEPS, and the step that matched
    ('' if none; code missing). d and c (CCD rows) both have columns `area`,
    class_year, exact, words; c also has code. 'Any year' steps use the CCD year
    nearest the class, since CCD renumbers some schools (e.g. charters moving
    district) while the name stays."""
    one_school = d.groupby([area, "class_year"])[area].transform("size") == 1
    code, how = pd.Series(pd.NA, index=d.index, dtype=object), pd.Series("", index=d.index)
    c = c.rename(columns={"class_year": "ccd_year"})
    for step, keys in NAME_STEPS:
        by = [area] + [k for k in keys if k != "class_year"]
        left = d.loc[code.isna() & (one_school if step.startswith("only_hs") else True), by + ["class_year"]]
        m = left.dropna(subset=by).rename_axis("row").reset_index().merge(
            c[by + ["ccd_year", "code"]].drop_duplicates(), on=by)
        m["gap"] = (m["class_year"] - m["ccd_year"]).abs()
        if "class_year" in keys:
            m = m[m["gap"] == 0]
        m = m[m["gap"] == m.groupby("row")["gap"].transform("min")].drop_duplicates(["row", "code"])
        m = m[~m["row"].duplicated(keep=False)]           # unique code only
        code[m["row"].values], how[m["row"].values] = m["code"].values, step
    return code, how


def site_rows(path, sheets, site):
    """Rows of the given sheets that contain a school code (regex `site`) in their
    first six cells; yields (row, index of the code cell)."""
    for sh in sheets:
        for r in sheet_rows(path, sh):
            i = next((k for k, c in enumerate(r[:6]) if site.fullmatch(c)), None)
            if i is not None:
                yield r, i


# ---------------------------------------------------------------------------
# Louisiana
# ---------------------------------------------------------------------------

# LDOE site codes: 6 characters, digits or (for many charters) letters plus
# digits, e.g. 001005, WBB001, 3A1001.
LA_SITE = re.compile(r"(?=.*\d)[0-9A-Z]{6}")
# State-file code -> CCD code for the same school. Grambling State Univ.
# Laboratory High School is 031002 in LDOE files for classes 2013-2016 but
# 323002 in CCD (Deneault makes the same correction in cleaningccd_aejep.do).
LA_ALIASES = {"031002": "323002"}
LA_PCT = ["pct_enrolled", "pct_2yr", "pct_4yr", "pct_instate"]


def la_college_enrollment():
    """LDOE college enrollment reports, classes 2012-2024: one row per site with
    total graduates and % enrolled 1st fall, % 2-year, % 4-year, % in-state (the
    last three are shares of enrollees), each with its bound direction. The
    class of 2012 file gives exact rates as fractions; they are scaled to percent."""
    folder = RAW / "LA" / "ldoe_college_enrollment"
    files = sorted(folder.glob("*college-enrollment-report.xlsx")) + \
        sorted(folder.glob("*college-enrollment-with-subgroups.xlsx"))
    out = []
    for f in files:
        wb = openpyxl.load_workbook(f, read_only=True)
        sheets = [s for s in wb.sheetnames
                  if not re.search(r"by College|Subgroup|State ?and ?(District|LEA)", s, re.I)]
        recs = []
        for r, i in site_rows(f, sheets, LA_SITE):
            cells = r[i + 2:i + 7]
            rec = {"class_year": class_of(r[0]), "code": r[i], "name": r[i + 1],
                   "graduates": value(cells[0]), "file": f.name}
            for col, c in zip(LA_PCT, cells[1:]):
                rec[col], rec[f"{col}_bound"] = value(c), bound(c)
            recs.append(rec)
        d = pd.DataFrame(recs)
        if d["pct_enrolled"].median() <= 1:
            # Class 2012: exact rates are fractions (0.56) but bounds are percents
            # ('>99%'), so only exact values are scaled.
            for c in LA_PCT:
                exact = d[f"{c}_bound"] == ""
                d.loc[exact, c] = d.loc[exact, c] * 100
        out.append(d)
    return pd.concat(out, ignore_index=True)


def la_grad_rates():
    """LDOE 4-year cohort graduation rate by site, classes 2014-2025 (percent, with
    bound direction). Classes 2016 on: sheet 'Graduation Rate <class>' of the
    school graduation summaries. Classes 2014-2015: column 'Cohort Graduation
    Rate (Actual)' of the next year's School Performance Score file (2015 file ->
    class 2014, 2016 file -> class 2015), as in Deneault's README."""
    sources = []
    for f in sorted((RAW / "LA" / "ldoe_grad_rates").glob("*.xlsx")):
        sheet = next((s for s in openpyxl.load_workbook(f, read_only=True).sheetnames
                      if re.fullmatch(r"Graduation Rate 20\d\d", s)), None)
        if sheet and not re.search(r"subgroup|scholarship|^2005-", f.name, re.I):
            sources.append((f, sheet, int(sheet[-4:])))
    for y in (2014, 2015):
        f = RAW / "LA" / "ldoe_performance_scores" / f"{y + 1}-school-performance-scores.xlsx"
        sources.append((f, f"{y + 1} School Performance Score", y))
    recs = []
    for f, sheet, y in sources:
        rows = list(sheet_rows(f, sheet))
        # The header row names both a code column and the rate (the title row
        # above it also says "Graduation Rates").
        head = next(r for r in rows if any(re.search(r"code", c, re.I) for c in r)
                    and any(re.search(r"graduation rate", c, re.I) for c in r))
        col = next(k for k, c in enumerate(head)
                   if re.search(r"graduation rate", c, re.I) and not re.search(r"index", c, re.I))
        for r, i in site_rows(f, [sheet], LA_SITE):
            if r[col]:
                recs.append({"class_year": y, "code": r[i], "grad_rate": value(r[col]),
                             "grad_rate_bound": bound(r[col]), "file": f.name})
    return pd.DataFrame(recs)


# ---------------------------------------------------------------------------
# Illinois
# ---------------------------------------------------------------------------

IL_DIR = RAW / "IL" / "isbe_report_card"


def il_code(c):
    """Illinois school code in one form: RCDTS (region 2, county 3, district 4,
    type 2, school 4 = 15 digits) without the 2-digit type, as CCD writes it for
    2014-15 to 2022-23 (13 digits); CCD gives the full RCDTS from 2023-24."""
    c = re.sub(r"\D", "", str(c))      # 2025 writes it with dashes: 01-009-2620-26-0002
    return c[:9] + c[11:] if len(c) == 15 else c


# Postsecondary columns: our name -> pattern matched against the report card
# header (2018 on) or layout field name (2015-2017).
IL_COLS = {
    "pct_enrolled_12m": r"within 12 months( - SCHOOL)?$",
    "pct_enrolled_16m": r"within 16 months( - SCHOOL)?$",
    "pct_12m_public": r"within 12 months - Pub",
    "pct_12m_private": r"within 12 months - Priv",
    "pct_12m_4yr": r"within 12 months - Four",
    "pct_12m_2yr": r"within 12 months - Two",
    "pct_12m_trade": r"within 12 months - Trade",
    "pct_16m_public": r"within 16 months - Pub",
    "pct_16m_private": r"within 16 months - Priv",
    "pct_16m_4yr": r"within 16 months - Four",
    "pct_16m_2yr": r"within 16 months - Two",
    "pct_16m_trade": r"within 16 months - Trade",
    "n_community_college": r"# Graduates enrolled in Community College",
    "grad_rate_4yr": r"(High School 4-Year Graduation Rate - Total|4.?YEAR GRAD.* RATE.*- SCHOOL)$",
    "cohort_graduates_4yr": r"High School 4-Year Cohort Graduates - Total",
}


def il_layout_fields(year):
    """Field names of the semicolon-delimited report card file for 2015-2017, in
    column order, from the layout workbook (one row per field)."""
    lay = next(IL_DIR.glob(f"RC{year % 100}*layout.xlsx"))
    ws = openpyxl.load_workbook(lay, read_only=True).worksheets[0]
    names = []
    for r in ws.iter_rows(values_only=True):
        cells = [c for c in r if c is not None]
        if cells and (isinstance(cells[0], (int, float)) or str(cells[0]).startswith("=A")):
            names.append(next((c.strip() for c in cells if isinstance(c, str) and re.search(r"[A-Z]{3}", c)
                               and not c.startswith("=")), ""))
    return names


def il_report_years():
    """Report card years on disk: rcYY.zip files (2015-2017) and yearly public data
    set workbooks (2018 on), so a newly downloaded year is picked up automatically."""
    zips = {2000 + int(m[1]) for p in IL_DIR.glob("rc*.zip") if (m := re.fullmatch(r"rc(\d\d)\.zip", p.name))}
    books = {int(p.name[:4]) for p in IL_DIR.glob("20*.xlsx") if re.search(r"Data-Set|Pub-Data", p.name)}
    return sorted(zips | books)


def il_report_card(year):
    """One report card year as a DataFrame: RCDTS code, name, record type, and the
    IL_COLS columns that year has (as published strings)."""
    if year <= 2017:
        names = il_layout_fields(year)
        z = next(IL_DIR.glob(f"rc{year % 100}.zip"))
        with zipfile.ZipFile(z) as zf:
            d = pd.read_csv(zf.open(zf.namelist()[0]), sep=";", header=None, dtype=str,
                            encoding="latin-1", usecols=range(len(names)))
        d.columns = names
        d = d.rename(columns={names[0]: "code", "SCHOOL NAME": "name"})
        # Field 1, SCHOOL TYPE CODE: 0 elementary, 1 middle, 2 high school, C charter;
        # district rows have a blank school name. Keep school rows.
        d["type"] = "School"
    else:
        f = next(p for p in IL_DIR.glob(f"{year}*.xlsx") if re.search(r"Data-Set|Pub-Data", p.name))
        d = pd.read_excel(f, sheet_name="General", dtype=str)
        d = d.rename(columns={"RCDTS": "code", "School Name": "name", "Type": "type"})
        if "type" not in d:      # 2025 has no Type column; districts have no school name
            d["type"] = d["name"].notna().map({True: "School", False: "District"})
    cols = {}
    for ours, pat in IL_COLS.items():
        hit = next((c for c in d.columns if isinstance(c, str) and re.search(pat, c.strip(), re.I)), None)
        if hit is not None:
            cols[hit] = ours
    d = d.rename(columns=cols)
    keep = ["code", "name", "type", *[c for c in IL_COLS if c in d]]
    return d[keep].assign(report_year=year)


def il_college_enrollment():
    """ISBE report card postsecondary enrollment by school, report card years
    2015-2026 (classes 2013-2024): % of graduates enrolled in a U.S. postsecondary institution within
    12 and 16 months (NSC), and from 2019 by public/private, 4-/2-year, and
    trade/vocational. class_year is set by IL_CLASS_OF (see source notes)."""
    out = []
    for y in IL_CLASS_OF:
        d = il_report_card(y)
        d = d[(d["type"].str.strip() == "School") & d["name"].notna()
              & d["pct_enrolled_12m"].fillna("").str.strip().ne("")]
        recs = d.assign(code=d["code"].str.strip(), name=d["name"].str.strip(),
                        class_year=IL_CLASS_OF[y])
        for c in [c for c in IL_COLS if c in recs]:
            raw = recs[c].fillna("")
            recs[c], recs[f"{c}_bound"] = raw.map(value), raw.map(bound)
        out.append(recs.drop(columns="type"))
    return pd.concat(out, ignore_index=True)


# Report card year -> graduating class of its postsecondary enrollment data:
# two years earlier (ISBE business rules: "The 2023-24 Report Card uses student
# graduate data from the 2021-22 school year"). The 2018-2021 glossaries say
# "three years prior", but school-level changes in enrollment track changes in
# FAFSA completion only at a two-year lag (docs/source-notes.md, Illinois).
IL_CLASS_OF = {y: y - 2 for y in il_report_years()}


# ---------------------------------------------------------------------------
# Alabama
# ---------------------------------------------------------------------------

AL_DIR = RAW / "AL"


def al_ccd_key(st_schid):
    """Alabama school key 'system-school' (3 + 4 digits) from CCD's ST_SCHID: a
    4-digit school code alone repeats across systems. CCD 2014-15 gives only the
    school code, so those rows get no key (they link by another year's code)."""
    parts = str(st_schid).split("-")
    return "-".join(parts[-2:]) if len(parts) >= 2 else None


def AL_CCD_KEY(c):
    """CCD key for link(): Alabama system-school code from each row's ST_SCHID."""
    return c["st_schid"].map(al_ccd_key)


def al_cohort_grad():
    """ALSDE 4-year cohort graduation by school ('All students' rows), classes
    2019-2025 (the exports for classes 2012-2018 contain only a header row).
    Federal and ALSDE rates, the adjusted cohort ('Total Students'), and federal
    and ALSDE graduate and completer counts; '~' is suppressed."""
    import xlrd
    recs = []
    for f in sorted((AL_DIR / "alsde_cohort_grad").glob("cohort4yr_class*.xls")):
        sh = xlrd.open_workbook(f).sheet_by_index(0)
        head = [str(c).strip() for c in sh.row_values(0)]
        for i in range(1, sh.nrows):
            r = dict(zip(head, [str(c).strip() for c in sh.row_values(i)]))
            if r["Sub Population"] != "All students" or r["School Code"] in ("", "0000"):
                continue
            recs.append({"class_year": int(float(r["Grad Year"])),
                         "code": f"{r['System Code']}-{r['School Code']}", "name": r["School Name"],
                         "grad_rate_federal": value(r["Federal Grad Rate"]),
                         "grad_rate_alsde": value(r["ALSDE Grad Rate"]),
                         "cohort": value(r["Total Students"]),
                         "graduates_federal": value(r["Federal Graduates"]),
                         "graduates_alsde": value(r["ALSDE Graduates"]),
                         "file": f.name})
    return pd.DataFrame(recs)


def al_ache_enrollment():
    """ACHE High School Graduate Reports, classes 2012-2024: each Alabama public high
    school's graduates (as reported by ALSDE) and how many enrolled in Alabama
    PUBLIC colleges in the fall after graduation, 2-year and 4-year (two rows per
    school; the code is on the 2-year row). The class comes from the title
    ('2022-2023 ALABAMA PUBLIC HIGH SCHOOL GRADUATES ... FALL 2023' = 2023). The
    7-digit ACHE code is system (3) + school (4), the same key as al_ccd_key."""
    import xlrd
    recs = []
    for f in sorted((AL_DIR / "ache_hs_reports").glob("ache_hs_basic_fall*.xls")):
        sh = xlrd.open_workbook(f, logfile=open("/dev/null", "w")).sheet_by_index(0)
        rows = [[str(c).strip() for c in sh.row_values(i)] for i in range(sh.nrows)]
        title = next(c for r in rows for c in r if "HIGH SCHOOL GRADUATES" in c.upper())
        cls = class_of(title)
        cur = None
        for r in rows:
            label = next((c for c in r if re.search(r"Enrolled in [24]YR Colleges", c)), None)
            if not label:
                continue
            nums = [value(c) for c in r if re.fullmatch(r"-?[\d.]+", c)]
            if "2YR" in label:
                code = f"{int(float(r[0])):07d}"
                cur = {"class_year": cls, "code": f"{code[:3]}-{code[3:]}",
                       "name": re.sub(r"\s*(High School\s*)?Enrolled in 2YR Colleges$", "", label).strip(),
                       "graduates": nums[1], "enrolled_2yr": nums[3], "file": f.name}
            elif cur is not None:
                cur["enrolled_4yr"] = nums[2]
                recs.append(cur)
                cur = None
    d = pd.DataFrame(recs)
    d["enrolled"] = d["enrolled_2yr"] + d["enrolled_4yr"]
    d["pct_enrolled"] = 100 * d["enrolled"] / d["graduates"]
    return d


# ---------------------------------------------------------------------------
# Maryland
# ---------------------------------------------------------------------------

MD_ZIP = RAW / "MD" / "mlds_hs_to_college"
# MLDS college enrollment types kept: name in the file -> our suffix.
MD_TYPES = {"Immediate": "immediate", "Within One Year": "1yr", "Within Two Years": "2yr"}
# MLDS name key -> CCD name key for the same school (names differ; checked by
# hand for class 2019, 2026-11-01). SEED is under Baltimore City in MLDS but is
# its own district in CCD.
MD_ALIASES = {
    "BALTIMORE CITY|HARBOR CITY": "BALTIMORE CITY|ACHIEVEMENT HARBOR CITY",
    "ALLEGANY|CAREER TECHNOLOGY": "ALLEGANY|CAREER TECHNICAL",
    "BALTIMORE CITY|MASONVILLE COVE": "BALTIMORE CITY|BENJAMIN FRANKLIN MASONVILLE COVE",
    "BALTIMORE CITY|SEED MARYLAND": "MARYLAND STATE|SEED MARYLAND",
    "BALTIMORE CITY|NACA FREEDOM DEMOCRACY II": "BALTIMORE CITY|N A C A FREEDOM DEMOCRACY II",
}


def md_district(name):
    """Maryland school system key: 'Allegany County Public Schools' (CCD) and
    'Allegany' (MLDS) -> 'ALLEGANY'; Baltimore City and Baltimore County keep
    their suffix; the SEED School (CCD) is MLDS's 'Maryland State'."""
    k = normalize(str(name).replace("Public Schools", "")) or ""
    if k == "SEED SCHOOL OF MARYLAND":
        return "MARYLAND STATE"
    return k[:-7] if k.endswith(" COUNTY") and k != "BALTIMORE COUNTY" else k


def md_school_key(district, name):
    """Name key within a school system: distinctive words of the normalized name
    (generic words such as HIGH and SCHOOL dropped)."""
    return md_district(district) + "|" + " ".join(distinctive(normalize(name)))


def MD_CCD_KEY(c):
    """CCD key for link(): Maryland school system + school name, for schools
    offering grade 12 only (MLDS lists high schools; 'Annapolis High' and
    'Annapolis Middle' would otherwise share a key)."""
    return [md_school_key(d, n) if str(g).strip() in ("12", "13") else None
            for d, n, g in zip(c["lea_name"], c["name"], c["gshi"])]


def md_college_enrollment():
    """MLDS Center download, all-students school rows, classes 2008-2024 ('2023-24'
    = 2024): high school graduates and, for each MD_TYPES enrollment type, the
    number and % of graduates enrolled. '*' (under 10 or complementary
    suppression) and '◊' (no graduates that year) are missing. Schools are named,
    not coded; `code` is md_school_key(system, name)."""
    zf = zipfile.ZipFile(next(MD_ZIP.glob("HighSchoolToCollegeDashboard*DataDownload.zip")))
    book = next(n for n in zf.namelist() if n.endswith(".xlsx"))
    d = pd.read_excel(zf.open(book), sheet_name=0, header=2, dtype=str, usecols=range(9))
    d.columns = [c.strip() for c in d.columns]
    d = d[(d["Grouping Level"] == "All Students") & (d["Sub-group"] == "School")
          & d["College Enrollment Type"].isin(MD_TYPES)]
    d = d.assign(class_year=d["Cohort Year"].map(class_of),
                 code=[md_school_key(a, b) for a, b in zip(d["Local School System"], d["School"])],
                 graduates=d["High School Graduates"].map(value),
                 enrolled=d["Enrollment"].map(value),
                 pct=100 * d["% of High School Graduates Enrolled"].map(value),
                 kind=d["College Enrollment Type"].map(MD_TYPES))
    # Rows marked '◊' had no graduates that year: not a school-year. Suppressed
    # ('*') rows stay, with missing enrollment.
    d = d[d["High School Graduates"].str.strip() != "◊"]
    keys = ["class_year", "code", "Local School System", "School"]
    wide = d.set_index(keys + ["kind"])[["enrolled", "pct"]].unstack("kind")
    wide.columns = [f"{v}_{k}" for v, k in wide.columns]
    grads = d.groupby(keys)["graduates"].first()
    out = wide.join(grads).reset_index()
    return out.rename(columns={"Local School System": "district", "School": "name"}).assign(file=book)


# ---------------------------------------------------------------------------
# Texas
# ---------------------------------------------------------------------------

TX_THECB = RAW / "TX" / "thecb_hs_enrolled"
TX_NOT_ENROLLED = {"Not found", "Not trackable", "Total high school graduates"}


def tx_thecb_enrollment():
    """THECB 'Texas High School Graduates From FY <Y> Enrolled in Texas Public or
    Independent Higher Education Fall <Y>', classes 2019-2024, high schools with
    more than 25 graduates: total graduates, enrolled (sum of the institution
    rows, including 'Other' rows that pool institutions with < 5 students),
    'Not found' (standard ID, not enrolled in Texas that fall) and 'Not trackable'
    (non-standard ID, cannot be matched). The 2021 and 2024 titles say 'Public'
    only, but private colleges (Baylor, TCU, SMU, ...) are listed in every year.
    `code` is the 9-digit TEA campus ID (the 2024 file drops leading zeros)."""
    recs = {}
    for f in sorted(TX_THECB.glob("hsgrads_enrolled_by_campus_fall*.xlsx")):
        cls = int(re.search(r"fall(\d{4})", f.name)[1])
        for r in sheet_rows(f):
            if len(r) < 6 or not re.fullmatch(r"\d{6,9}", r[3]) or not r[5].replace(",", "").isdigit():
                continue
            key = (cls, r[3].zfill(9))
            rec = recs.setdefault(key, {"class_year": cls, "code": key[1], "name": r[2], "graduates": 0.0,
                                        "enrolled": 0.0, "not_found": 0.0, "not_trackable": 0.0, "file": f.name})
            n, label = float(r[5].replace(",", "")), r[4]
            col = {"Total high school graduates": "graduates", "Not found": "not_found",
                   "Not trackable": "not_trackable"}.get(label, "enrolled")
            rec[col] += n
    return pd.DataFrame(recs.values())


# ---------------------------------------------------------------------------
# California
# ---------------------------------------------------------------------------

CA_CGR = RAW / "CA" / "cde_cgr12"
# CDE column -> our name (counts; the rate is recomputed from them).
CA_COLS = {
    "High School Completers": "graduates",
    "Enrolled In College - Total (12 Months)": "enrolled",
    "Enrolled In-State (12 Months)": "enrolled_instate",
    "Enrolled Out-of-State (12 Months)": "enrolled_outstate",
    "Enrolled UC (12 Months)": "enrolled_uc",
    "Enrolled CSU (12 Months)": "enrolled_csu",
    "Enrolled CCC (12 Months)": "enrolled_ccc",
    "Enrolled In-State Private (2 and 4 Year) (12 Months)": "enrolled_instate_private",
    "Enrolled Out-of-State 4-Year College (Public/Private) (12 Months)": "enrolled_outstate_4yr",
    "Enrolled Out-of-State 2-Year College (Public/Private) (12 Months)": "enrolled_outstate_2yr",
}


def ca_college_going():
    """CDE 12-month college-going rate files, classes 2015-2023 ('2018-19' = 2019):
    school rows for all students (ReportingCategory TA) and all completers
    (CompleterType TA). High school completers (graduates plus non-graduate
    completers) and their enrollment at any U.S. college within 12 months (NSC),
    with in-state/out-of-state and UC/CSU/community college/private splits.
    Files through class 2020 repeat each school under 'All' charter and
    alternative-status combinations; the row with the school's actual status is
    kept (the only row in later files). '*' (10 or fewer) is missing."""
    out = []
    for f in sorted(CA_CGR.glob("cgr12mo_class*.txt")):
        # Files 2015-2017 start with a UTF-8 byte-order mark.
        d = pd.read_csv(f, sep="\t", dtype=str, encoding="utf-8-sig", encoding_errors="replace")
        status = [c for c in d.columns if c in ("CharterSchool", "AlternativeSchoolAccountabilityStatus", "DASS")]
        d = d[(d["AggregateLevel"] == "S") & (d["ReportingCategory"] == "TA") & (d["CompleterType"] == "TA")]
        d = d[~d[status].apply(lambda c: c.str.strip().eq("All")).any(axis=1)]
        # Placeholder codes, not schools: 0000000 'District Office', 0000001
        # 'Nonpublic, Nonsectarian Schools' (one per district).
        d = d[~d["SchoolCode"].str.strip().isin(["0000000", "0000001"])]
        rec = d.assign(class_year=d["AcademicYear"].map(class_of), code=d["SchoolCode"].str.strip(),
                       name=d["SchoolName"].str.strip(), file=f.name)
        for col, ours in CA_COLS.items():
            rec[ours] = rec[col].map(value)
        out.append(rec[["class_year", "code", "name", *CA_COLS.values(), "file"]])
    return pd.concat(out, ignore_index=True)


# ---------------------------------------------------------------------------
# Indiana
# ---------------------------------------------------------------------------

IN_CHE = RAW / "IN" / "che_college_going"
# Column names vary by file year -> one name.
IN_RENAME = {"GeoType": "LocationType", "HSGradN": "graduates", "HSGradsN": "graduates", "HSGrads": "graduates",
             "EnrCollegeN": "enrolled", "EnrINPubCollegeN": "enrolled_in_public"}


def in_name_city_key(name, city):
    """Indiana fallback key: distinctive words of the school name + the city."""
    return " ".join(distinctive(normalize(name))) + "|" + (normalize(city) or "")


def in_college_going():
    """Indiana CHE college-going (College Readiness) datasets, classes 2008-2024 (the
    file's Cohort = graduating class): high school graduates, enrollees at any
    college that participates in NSC, and enrollees at Indiana public colleges, by
    high school ('Average' rows). Schools are named 'Name-City' in every file; only
    the 2024 file has an ID (IDOE school number, = CCD ST_SCHID's last segment).
    `code` is that ID: from the 2024 file's name -> ID pairs for every year, else
    by name + city in CCD (Indiana high schools, keys that are unique only).
    Unmatched schools keep 'NAME:<name-city>'. 'NULL', '***', 'DS' are missing."""
    frames = []
    for f in sorted(IN_CHE.glob("*.xlsx")):
        sheet = next(s for s in openpyxl.load_workbook(f, read_only=True).sheetnames if s.upper() == "DATA")
        d = pd.read_excel(f, sheet_name=sheet, dtype=str).rename(columns=IN_RENAME)
        d = d[(d["LocationType"].str.strip() == "School") & (d["Category"].str.strip() == "Average")]
        frames.append(d.assign(file=f.name))
    d = pd.concat(frames, ignore_index=True)
    # One school row in the class 2020 file has no name; it stays, unmatched.
    d["name"] = d["Location"].fillna("").str.strip()
    # 1. The 2024 file's IDs, by exact name.
    ids = d.dropna(subset=["LocationId"]).drop_duplicates("name").set_index("name")["LocationId"].str.strip().str.zfill(4)
    # 2. CCD name + city -> ID, for Indiana grade-12 schools, unique keys only.
    ccd = ccd_codes()
    c = ccd[(ccd["state"] == "IN") & ccd["gshi"].astype(str).str.strip().isin(["12", "13"])]
    c = c.assign(key=[in_name_city_key(n, t) for n, t in zip(c["name"], c["city"])]).drop_duplicates(["key", "code"])
    by_key = c[~c["key"].duplicated(keep=False)].set_index("key")["code"]
    # Fallback only for names without a 2024 ID, and only where the key belongs to
    # one CHE name and its CCD ID is not already another name's 2024 ID (the key
    # drops generic words, so 'Greenwood Christian Academy' and 'Greenwood
    # Community High School' in Greenwood share one).
    names = pd.Series(d["name"].unique())
    keys = names.map(lambda n: in_name_city_key(*(n.rsplit("-", 1) + [""])[:2]))
    one_name = ~keys.duplicated(keep=False)
    fallback = pd.Series(keys[one_name].map(by_key).values, index=names[one_name].values).dropna()
    fallback = fallback[~fallback.isin(set(ids))]
    d["code"] = d["name"].map(ids).fillna(d["name"].map(fallback)).fillna("NAME:" + d["name"])
    d["class_year"] = d["Cohort"].astype(int)
    for col in ("graduates", "enrolled", "enrolled_in_public"):
        d[col] = d[col].map(value)
    return d[["class_year", "code", "name", "graduates", "enrolled", "enrolled_in_public", "file"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# New Hampshire (manual exports, see sources.new_hampshire)
# ---------------------------------------------------------------------------

NH_MANUAL = RAW / "NH" / "manual"


def nh_code(c):
    """New Hampshire school number (5 digits). CCD's ST_SCHID last segment is a
    14-digit string ending in it (e.g. 52504104128555 -> 28555) through 2023-24,
    and the 5 digits alone from 2024-25."""
    c = re.sub(r"\D", "", str(c))
    return c[-5:] if c else c


def nh_iexplore_rates():
    """iExplore Post-secondary Enrollment Rate by school, dashboard years 2016-2025
    (crosstab exports, one column per year; merged cells blank). Long format:
    `year` (the dashboard's year), 5-digit Entity ID, name, school level, rate (%)
    with bound direction ('>90%' / '<10%' are blurred for privacy); 'NA', '*N'
    (fewer than 11 students), '*COVID' are missing. class_year is set from
    NH_CLASS_OF."""
    recs = []
    for f in sorted((NH_MANUAL / "iexplore_postsecondary").glob("postsecondary_enrollment_rate_*.xlsx")):
        rows = list(sheet_rows(f))
        head = rows[0]
        years = [(i, int(h)) for i, h in enumerate(head) if re.fullmatch(r"20\d\d", h)]
        level = ""
        for r in rows[1:]:
            level = r[3] or level
            if not re.fullmatch(r"\d{5}", r[6]):
                continue
            for i, y in years:
                if r[i]:
                    recs.append({"year": y, "code": r[6], "name": r[7], "level": level,
                                 "pct_enrolled": value(r[i]), "pct_enrolled_bound": bound(r[i]),
                                 "raw": r[i], "file": f.name})
    d = pd.DataFrame(recs).drop_duplicates(["year", "code", "raw"])
    return d.assign(class_year=d["year"].map(NH_CLASS_OF))


def nh_completers_status():
    """iPlatform Completers By Status By School, classes 2012-2025 (class from the
    title inside each file, as saved): school number, total completers, and the
    shares entering 4-year and less-than-4-year colleges (reported plans)."""
    recs = []
    for f in sorted((NH_MANUAL / "iplatform_completers_status").glob("completers_by_status_by_school_class*.xlsx")):
        cls = int(re.search(r"class(\d{4})", f.name)[1])
        for r in sheet_rows(f):
            cells = [c for c in r if c != ""]
            if len(cells) >= 13 and re.fullmatch(r"\d{5}", cells[4]):
                recs.append({"class_year": cls, "code": cells[4], "name": cells[5], "completers": value(cells[6]),
                             "pct_plan_4yr": 100 * value(cells[7]), "pct_plan_lt4yr": 100 * value(cells[8])})
    return pd.DataFrame(recs)


# iExplore dashboard year -> graduating class: the same year. Checked 2026-11-01:
# school rates correlate best with the same class's reported college plans
# (0.78 vs. 0.68-0.70 for adjacent classes) and their year-to-year changes track
# FAFSA completion changes of the same class (+0.48; -0.22 for the class before).
NH_CLASS_OF = {y: y for y in range(2016, 2026)}


def nh_postsecondary():
    """New Hampshire high schools' post-secondary enrollment rate by class (iExplore),
    with total completers from the iPlatform Completers By Status report of the same
    class (school number match), from which enrollees are estimated."""
    r = nh_iexplore_rates()
    r = r[r["level"] == "High School"].drop(columns=["year", "level", "raw"])
    c = nh_completers_status()[["class_year", "code", "completers"]]
    return r.merge(c, on=["class_year", "code"], how="left").rename(columns={"completers": "graduates"})


# ---------------------------------------------------------------------------
# Nebraska
# ---------------------------------------------------------------------------

NE_NEP = RAW / "NE" / "nde_nep"
# Two layouts: files 2017-18 to 2022-23 and files from 2023-24.
NE_RENAME = {"Type": "Level", "HS Graduation Year": "HighSchoolGraduationYear", "College Enrollment Date": "CollegeEnrollmentDate",
             "Agency Name": "Name", "Category": "SubgroupType", "Student Subgroup": "SubgroupDescription",
             "College-Going Count": "CollegeGoingCount", "College-Going Pct": "CollegeGoingPercent"}


def ne_college_going():
    """NDE Nebraska Education Profile college-going files, classes 2016-2023: school
    rows, all students. Each annual file repeats up to four earlier classes; each
    class comes whole from the newest file that holds it. Enrollment is measured on the file's
    CollegeEnrollmentDate (October 15 of the year after the first fall, about 16
    months after a spring graduation). Count and % are published; graduates are
    count / % x 100 (an estimate). `code` = county (2) + district (4) + school (3),
    as in CCD's ST_SCHID. Suppressed cells ('*', or -1 in files before 2023-24) are missing."""
    frames = []
    for f in sorted(NE_NEP.glob("CollegeGoingRate_*.csv")):
        d = pd.read_csv(f, dtype=str, encoding="utf-8-sig").rename(columns=lambda c: NE_RENAME.get(c.strip(), c.strip()))
        d = d[(d["Level"] == "SC") & d["SubgroupType"].str.upper().isin(["ALL STUDENTS"])]
        frames.append(d.assign(file=f.name))
    d = pd.concat(frames, ignore_index=True)
    grad = d["HighSchoolGraduationYear"].str.replace("-", "")
    d["class_year"] = grad.str[-4:].astype(int)
    d["code"] = d["County"].str.zfill(2) + d["District"].str.zfill(4) + d["School"].str.zfill(3)
    # Each class is taken whole from the newest file that holds it (classes are
    # revised between files, and the 2020-21 and 2021-22 files each carry two
    # different '2018-2019' sets of rows).
    newest = d.groupby("class_year")["file"].transform("max")
    d = d[d["file"] == newest]
    # Suppressed cells are '*' from 2023-24 and -1 / -1.00 in earlier files.
    d["enrolled"] = d["CollegeGoingCount"].map(value).where(lambda v: v >= 0)
    d["pct_enrolled"] = d["CollegeGoingPercent"].map(value).where(lambda v: v >= 0)
    d["pct_enrolled_bound"] = d["CollegeGoingPercent"].map(bound)
    d["graduates"] = 100 * d["enrolled"] / d["pct_enrolled"]
    d["enrollment_date"] = d["CollegeEnrollmentDate"]
    return d[["class_year", "code", "Name", "graduates", "enrolled", "pct_enrolled", "pct_enrolled_bound",
              "enrollment_date", "file"]].rename(columns={"Name": "name"}).reset_index(drop=True)


NE_CCPE = RAW / "NE" / "ccpe_continuation" / "FL_CollegeGoing.xlsx"
def ne_ccpe_district(d):
    """6-digit county (2) + district (4) code of each CCPE row. Most sheets give it
    (5-6 digits); classes 2008, 2010, 2011 give the district number only (the
    county number comes from the county name in the other sheets) and class 2012
    none (taken by county + district name from the other sheets, unique only)."""
    raw = d["District"].str.strip()
    full = raw.str.len() >= 5
    county = d["County Name"].str.strip().str.upper()
    cc = pd.Series(raw[full].str.zfill(6).str[:2].values, index=county[full].values)
    cc = cc[~cc.index.duplicated()]
    dist = raw.str.zfill(6).where(full, county.map(cc) + raw.str.zfill(4))
    by_name = pd.DataFrame({"county": county, "dname": d["District Name"].map(normalize), "dist": dist}).dropna()
    by_name = by_name.drop_duplicates().drop_duplicates(["county", "dname"], keep=False).set_index(["county", "dname"])["dist"]
    fill = pd.Series(list(zip(county, d["District Name"].map(normalize))), index=d.index).map(by_name)
    return dist.fillna(fill)


def ne_ccpe_codes(d, ccd):
    """CCD school code (9 digits) of each CCPE row, matched within its district
    (name_codes), and the step that matched ('' if none; those keep
    'NAME:<district>:<school name>')."""
    c = ccd[(ccd["state"] == "NE") & ccd["gshi"].astype(str).str.strip().isin(["12", "13"])]
    c = c.assign(dist=c["code"].str[:6])
    c["exact"], c["words"] = name_keys(c["name"])
    code, how = name_codes(d, c, "dist")
    return code.fillna("NAME:" + d["dist"].fillna("") + ":" + d["School Name"].str.strip()), how


def ne_ccpe_continuation():
    """CCPE college continuation rates, classes 2008-2025 (one sheet per class,
    'yy-yy DATA'): on-time (4 years or less) public high school graduates (NDE
    records) and those enrolled at any NSC college between June 1 after
    graduation and May 31 of the next year, by high school. '*' (fewer than 10
    graduates) is missing. Sheets name schools and districts but have no school
    number; `code` is the CCD code matched by ne_ccpe_codes."""
    sheets = [s for s in openpyxl.load_workbook(NE_CCPE, read_only=True).sheetnames if s.endswith(" DATA")]
    frames = []
    for sh in sheets:
        d = pd.read_excel(NE_CCPE, sheet_name=sh, header=2, dtype=str).rename(columns=lambda c: " ".join(str(c).split()))
        frames.append(d.assign(class_year=2000 + int(sh[3:5])))
    d = pd.concat(frames, ignore_index=True).dropna(subset=["School Name"])   # class 2012: no District column
    d["dist"] = ne_ccpe_district(d)
    d["exact"], d["words"] = name_keys(d["School Name"])
    d["code"], d["ccpe_match"] = ne_ccpe_codes(d, ccd_codes())
    d["graduates"] = d["# On Time HS Grads"].map(value)
    d["enrolled"] = d["# Grads Who Went to College"].map(value)
    # The published rate is rounded in some sheets (84.1 for 514 / 611); use the counts.
    d["pct_enrolled"] = 100 * d["enrolled"] / d["graduates"]
    d["pct_enrolled_bound"] = ""
    return d.rename(columns={"School Name": "name"})[
        ["class_year", "code", "name", "graduates", "enrolled", "pct_enrolled", "pct_enrolled_bound",
         "ccpe_match"]].assign(file=NE_CCPE.name).reset_index(drop=True)


# ---------------------------------------------------------------------------
# Oklahoma
# ---------------------------------------------------------------------------

OK_OSRHE = RAW / "OK" / "osrhe_hs_indicators"
OK_FIRST_CLASS = 2013   # earlier files estimate enrollees by age (OSRHE methodology note)
# Columns after "Number of Graduates" (same order in every file from class 2013;
# the two out-of-state columns from class 2023).
OK_COLUMNS = ["graduates", "enrolled_fall", "_pct_fall", "enrolled", "_pct_year", "first_time_any_class",
              "enrolled_outstate", "_pct_outstate"]
OK_LABELS = {"", "HIGH SCHOOL", "SITE", "SITE_NAME", "SITE NAME"}   # header cells in the name column


def ok_ccd_key(st_schid):
    """Oklahoma county (2) - district - site key from CCD ST_SCHID, whose form
    varies by year ('01-I025-705', '01-I025-01-I025-705', 'OK-01-I025-01-I025-705')."""
    return "-".join(str(st_schid).split("-")[-3:])


def OK_CCD_KEY(c):
    """link() key for Oklahoma CCD rows: county-district-site (ok_ccd_key)."""
    return c["st_schid"].map(ok_ccd_key)


def ok_sheet_rows(f):
    """School rows of one OSRHE college-going workbook (first sheet not 'By
    District'): county, ACT code (classes 2013-2018 only), name, and the
    OK_COLUMNS counts. The county is written on a county's first row only. In
    two files (classes 2019, 2020) the first school's numbers sit on the header
    row above its name; they are moved down to it."""
    sheet = next(s for s in openpyxl.load_workbook(f, read_only=True).sheetnames if "DISTRICT" not in s.upper())
    d = pd.read_excel(f, sheet_name=sheet, header=None, dtype=str).fillna("")
    d = d.apply(lambda col: col.str.split().str.join(" "))   # headers have line breaks
    hdr = d.index[d.apply(lambda r: r.str.contains(r"Number of .*Graduates", case=False).any(), axis=1)][0]
    g = int(d.loc[hdr].str.contains(r"Number of .*Graduates", case=False).idxmax())   # graduates column
    nums = list(range(g, min(g + len(OK_COLUMNS), d.shape[1])))
    name = d[g - 1].str.upper()
    has_nums = (d[nums] != "").any(axis=1)
    label_row = name.isin(OK_LABELS) & has_nums & (d.index > hdr)
    for i in d.index[label_row]:                 # numbers one row above the name
        if i + 1 in d.index and not has_nums[i + 1]:
            d.loc[i + 1, nums], d.loc[i, nums] = d.loc[i, nums].values, ""
    has_nums = (d[nums] != "").any(axis=1)
    school = (d.index > hdr) & ~name.isin(OK_LABELS) & ~name.str.contains("TOTAL") & has_nums
    county = d[0].where(d[0].ne("") & ~d[0].str.upper().str.startswith("COUNTY")).ffill()
    out = pd.DataFrame({"county": county.str.upper(), "name": d[g - 1],
                        "act_code": d[1] if g == 3 else ""})[school]
    for col, j in zip(OK_COLUMNS, nums):
        out[col] = d.loc[school, j].map(value)
    return out


def ok_college_going():
    """OSRHE High School Indicators college-going rates, classes 2013 on (file
    'YYYY-...' = class YYYY): graduates of Oklahoma public high schools (SDE list)
    and those entering an Oklahoma public or private college the fall after
    graduation and anytime in the following academic year (plus, from class 2023,
    out-of-state colleges, separately). '.' is missing. Files have no state school
    number (classes 2013-2018 give ACT's high school code), so `code` is the CCD
    county-district-site key (ok_ccd_key) matched by county + name (name_codes);
    unmatched rows keep 'NAME:<county>:<name>'."""
    frames = [ok_sheet_rows(f).assign(class_year=int(f.name[:4]), file=f.name)
              for f in sorted(OK_OSRHE.glob("*.xls*"))
              if re.search("college-going", f.name, re.I) and int(f.name[:4]) >= OK_FIRST_CLASS]
    d = pd.concat(frames, ignore_index=True)
    d = d.drop(columns=[c for c in d if c.startswith("_")])   # published percents (recomputed below)
    # Classes 2013-2018 add the city to some names ('CENTRAL HS - TULSA'); it is
    # dropped after 'HS' only ('DOVE SCIENCE ACADEMY - TULSA' is CCD's name).
    d["exact"], d["words"] = name_keys(d["name"].str.replace(r"(?<=\bHS)\s+-\s+[^-]+$", "", regex=True))
    c = ccd_codes()
    c = c[(c["state"] == "OK") & c["gshi"].astype(str).str.strip().isin(["12", "13"])]
    c = c.assign(code=OK_CCD_KEY(c))
    # Each CCD school also under district + name ('EDMOND' + 'MEMORIAL HS' =
    # OSRHE 'EDMOND MEMORIAL HS'); a key shared by two schools matches neither.
    c = pd.concat([c, c.assign(name=c["lea_name"] + " " + c["name"])], ignore_index=True)
    c["exact"], c["words"] = name_keys(c["name"])
    # County name -> CCD county number, from names that occur once statewide in both.
    once = c.drop_duplicates(["exact", "code"])
    once = once[~once["exact"].duplicated(keep=False)].set_index("exact")["code"].str[:2]
    pairs = pd.DataFrame({"county": d["county"], "cc": d["exact"].map(once)}).dropna()
    number = pairs.groupby("county")["cc"].agg(lambda x: x.mode()[0])
    assert not number.duplicated().any(), "two OSRHE counties map to one CCD county number"
    d["cc"], c["cc"] = d["county"].map(number), c["code"].str[:2]
    code, d["name_match"] = name_codes(d, c, "cc")
    d["code"] = code.fillna("NAME:" + d["county"] + ":" + d["name"])
    d["pct_enrolled"] = 100 * d["enrolled"] / d["graduates"]
    d["pct_enrolled_fall"] = 100 * d["enrolled_fall"] / d["graduates"]
    d["pct_enrolled_bound"] = ""
    return d.drop(columns=["exact", "words", "cc"]).reset_index(drop=True)



# ---------------------------------------------------------------------------
# New York
# ---------------------------------------------------------------------------

NY_NYSED = RAW / "NY" / "nysed_downloads"
NY_FIRST_REPORT = 2022   # first Report Card database with the Postsecondary Enrollment table
# Enrollment counts by college type -> outcome breakdowns (sums of two columns each).
NY_PARTS = {"enrolled_instate_public": ["NYS_PUB_2_YR_CNT", "NYS_PUB_4_YR_CNT"],
            "enrolled_instate_private": ["NYS_PVT_2_YR_CNT", "NYS_PVT_4_YR_CNT"],
            "enrolled_outstate": ["OUT_2_YR_CNT", "OUT_4_YR_CNT"],
            "enrolled_2yr": ["NYS_PUB_2_YR_CNT", "NYS_PVT_2_YR_CNT", "OUT_2_YR_CNT"],
            "enrolled_4yr": ["NYS_PUB_4_YR_CNT", "NYS_PVT_4_YR_CNT", "OUT_4_YR_CNT"]}


def ny_report_table(path, table):
    """One table of a NYSED Access database inside a zip (the .accdb copy), read
    from a temporary extract that is deleted afterwards (data/raw is not changed)."""
    with zipfile.ZipFile(path) as zf, tempfile.TemporaryDirectory() as tmp:
        member = next(n for n in zf.namelist() if n.endswith(".accdb"))
        zf.extract(member, tmp)
        return pd.DataFrame(AccessParser(f"{tmp}/{member}").parse_table(table)).astype(str)


def ny_postsecondary():
    """NYSED Report Card 'Postsecondary Enrollment' table, school rows, All
    Students: graduates of the calendar year (MEMBERSHIP_DESC 'Class of YYYY')
    and those enrolled at any college within 16 months of graduation, by New York
    public / private and out-of-state, 2- and 4-year. Report year Y (SRC<Y>)
    holds classes Y-2 and Y-1; each class is taken from the newest report that
    holds it. The total enrolled is the sum of the six counts (the total column
    is empty for classes 2021-2022; elsewhere it equals the sum). 's' (suppressed)
    is missing. `code` = ENTITY_CD, the 12-digit BEDS code (= CCD ST_SCHID's
    last segment)."""
    reports = sorted(((int(re.search(r"SRC(\d{4})", f.name)[1]), f) for f in NY_NYSED.glob("*_SRC20*.zip")
                      if int(re.search(r"SRC(\d{4})", f.name)[1]) >= NY_FIRST_REPORT), reverse=True)
    frames, have = [], set()
    for year, f in reports:
        if {year - 1, year - 2} <= have | set(range(NY_FIRST_REPORT - 1)):   # nothing new in this report
            continue
        t = ny_report_table(f, "Postsecondary Enrollment")
        t["class_year"] = t["MEMBERSHIP_DESC"].str.extract(r"(\d{4})")[0].astype(int)
        t = t[~t["class_year"].isin(have)]
        have |= set(t["class_year"])
        frames.append(t.assign(file=f.name))
    d = pd.concat(frames, ignore_index=True)
    # Not the state (111111111111), counties / need-resource groups (000000...), or districts (...0000).
    school = ((d["ENTITY_CD"] != "111111111111") & (d["ENTITY_CD"].str[:6] != "000000")
              & (d["ENTITY_CD"].str[-4:] != "0000"))
    d = d[school & (d["SUBGROUP_NAME"] == "All Students")].copy()
    for col in {c for cols in NY_PARTS.values() for c in cols} | {"TOTAL_GRAD_COUNT"}:
        d[col] = d[col].map(value)
    for out, cols in NY_PARTS.items():
        d[out] = d[cols].sum(axis=1, min_count=len(cols))
    d["enrolled"] = d[["enrolled_instate_public", "enrolled_instate_private", "enrolled_outstate"]].sum(axis=1, min_count=3)
    d = d.rename(columns={"ENTITY_CD": "code", "ENTITY_NAME": "name", "TOTAL_GRAD_COUNT": "graduates"})
    d["pct_enrolled"] = 100 * d["enrolled"] / d["graduates"]
    d["pct_enrolled_bound"] = ""
    return d[["class_year", "code", "name", "graduates", "enrolled", "pct_enrolled", "pct_enrolled_bound",
              *NY_PARTS, "file"]].reset_index(drop=True)


# ---------------------------------------------------------------------------
# New Jersey
# ---------------------------------------------------------------------------

NJ_POST = RAW / "NJ" / "njdoe_postsecondary"
NJ_WINDOWS = {"Fall": "pct_enrolled", "16-month": "pct_enrolled_16m"}   # column prefix -> outcome column


def NJ_CCD_KEY(c):
    """link() key for New Jersey CCD rows: 9-digit county-district-school (CDS)
    code from the last two ST_SCHID segments ('NJ-010110-010' -> '010110010');
    CCD 2014-15 has the school number only, so no key."""
    parts = c["st_schid"].astype(str).str.split("-")
    return parts.map(lambda x: x[-2] + x[-1] if len(x) >= 2 else None)


def nj_postsecondary():
    """NJDOE postsecondary enrollment trend files (SPR Additional Data), school
    rows: % of the year's high school graduates (September-August) enrolled at
    any NSC college in the fall after graduation (`pct_enrolled`) and within 16
    months (`pct_enrolled_16m`). Rates are published as a range 'L-U%'; L is the
    NSC-matched share of graduates (kept), U = L / 0.97 (an allowance for
    unmatched graduates; not kept). 'N' (no graduates) and '*' (fewer than 10)
    are missing. Each file has five classes per window; each class is taken from
    the newest file that holds it. No counts are published. `code` = CDS (9 digits)."""
    frames = []
    for f in sorted(NJ_POST.glob("*.xlsx")):
        sheet = next(s for s in openpyxl.load_workbook(f, read_only=True).sheetnames if "TREND" in s.upper())
        d = pd.read_excel(f, sheet_name=sheet, header=None, dtype=str)
        hdr = d.index[d[0].astype(str).str.startswith("CDS")][0]
        d.columns = [" ".join(str(c).split()) for c in d.loc[hdr]]
        d = d.loc[hdr + 1:]
        d = d[d["School District State"] == "School"]
        long = d.melt(id_vars=[d.columns[0], "School Name"], value_vars=[c for c in d if "Class of" in c],
                      var_name="column", value_name="cell")
        long["window"] = long["column"].str.extract(r"^(Fall|16-month)")[0].map(NJ_WINDOWS)
        long["class_year"] = long["column"].str.extract(r"Class of (\d{4})")[0].astype(int)
        frames.append(long.assign(file=f.name, newest=long["class_year"].max()))
    d = pd.concat(frames, ignore_index=True).rename(columns={frames[0].columns[0]: "code", "School Name": "name"})
    d = d[d["newest"] == d.groupby(["window", "class_year"])["newest"].transform("max")]
    d["value"] = d["cell"].str.extract(r"^\s*([\d.]+)")[0].astype(float)    # lower bound of 'L-U%'
    out = d.pivot_table(index=["class_year", "code"], columns="window", values="value", aggfunc="first")
    names = d.sort_values("newest").drop_duplicates(["class_year", "code"], keep="last").set_index(["class_year", "code"])
    out = out.join(names[["name", "file"]]).reset_index()
    out["pct_enrolled_bound"] = out["pct_enrolled_16m_bound"] = ""
    return out[["class_year", "code", "name", "pct_enrolled", "pct_enrolled_bound", "pct_enrolled_16m",
                "pct_enrolled_16m_bound", "file"]]


NJ_ACGR = RAW / "NJ" / "njdoe_acgr"


def nj_acgr_graduates():
    """NJDOE 4-year adjusted cohort graduation rate files, one per cohort (= class),
    school rows of the all-students group ('Total'; 'All Students' from cohort 2025):
    `graduates` = 4-year cohort graduates with a state-endorsed diploma (state
    calculation), `cohort_count` = adjusted cohort, `grad_rate` (percent). School
    code 888 marks district totals (dropped). '*' (privacy) and 'N' (none) are
    missing. `code` = CDS (county 2 + district 4 + school 3 digits), as in nj_postsecondary."""
    frames = []
    for f in sorted(NJ_ACGR.glob("Cohort*.xlsx")):
        d = pd.read_excel(f, header=None, dtype=str)
        hdr = d.index[d[0].astype(str).str.strip() == "County Code"][0]
        d.columns = [" ".join(str(c).split()) for c in d.loc[hdr]]
        d = d.loc[hdr + 1:]
        d = d[d["Student Group"].str.strip().isin(["Total", "All Students"])
              & d["School Code"].notna() & ~d["School Code"].isin(["888", "999"])]
        col = lambda key: next(c for c in d.columns if key in c)
        frames.append(pd.DataFrame({
            "class_year": int(re.search(r"Cohort(\d{4})", f.name)[1]),
            "code": d["County Code"].str.zfill(2) + d["District Code"].str.zfill(4) + d["School Code"].str.zfill(3),
            "name": d["School Name"],
            "graduates": pd.to_numeric(d["Graduated"], errors="coerce"),
            "cohort_count": pd.to_numeric(d[col("Cohort Count")], errors="coerce"),
            "grad_rate": pd.to_numeric(d[col("Graduation Rate")], errors="coerce"),
            "file": f.name}))
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Content review (run as a script)
# ---------------------------------------------------------------------------

def panel_schools():
    """Public schools the first stage uses: in the analysis panel with grade-12 enrollment."""
    return duckdb.sql(f"""
        select state, class_year, school_id, nces_id
        from '{DERIVED / "analysis_panel.parquet"}'
        where sector = 'public' and enroll_g12 > 0
    """).df()


def summarize(state, source, rows, ccd, panel):
    """Per-class match statistics for one source's school rows (DataFrame with
    class_year, code, and optionally graduates)."""
    m = link(state, rows, ccd, **LINK_OPTIONS.get(state, {}))
    out = []
    for y, g in m.groupby("class_year"):
        p = panel[(panel["state"] == state) & (panel["class_year"] == y)]
        out.append({
            "state": state, "source": source, "class_year": y, "n_rows": len(g),
            "n_matched_ccd_same_year": int((g["link"] == "same_year").sum()),
            "n_matched_ccd_overall": int(g["school_id"].notna().sum()),
            "panel_schools": len(p),
            "panel_covered": int(p["school_id"].isin(g["school_id"]).sum()),
            "graduates": g["graduates"].sum() if "graduates" in g else float("nan"),
        })
    return out


# One entry per state: source name -> reader returning school rows.
READERS = {
    "LA": {"ldoe_college_enrollment": la_college_enrollment, "ldoe_grad_rates": la_grad_rates},
    "IL": {"isbe_report_card": il_college_enrollment},
    "AL": {"alsde_cohort_grad": al_cohort_grad, "ache_hs_reports": al_ache_enrollment},
    "MD": {"mlds_hs_to_college": md_college_enrollment},
    "TX": {"thecb_hs_enrolled": tx_thecb_enrollment},
    "CA": {"cde_cgr12": ca_college_going},
    "IN": {"che_college_going": in_college_going},
    "NH": {"iexplore_postsecondary": nh_postsecondary},
    "NE": {"ccpe_continuation": ne_ccpe_continuation, "nde_nep": ne_college_going},
    "OK": {"osrhe_hs_indicators": ok_college_going},
    "NY": {"nysed_downloads": ny_postsecondary},
    "NJ": {"njdoe_postsecondary": nj_postsecondary, "njdoe_acgr": nj_acgr_graduates},
}
# Per-state options for link(): code aliases and code normalizers.
LINK_OPTIONS = {"LA": {"aliases": LA_ALIASES}, "IL": {"normalize": il_code}, "AL": {"ccd_key": AL_CCD_KEY},
                "MD": {"ccd_key": MD_CCD_KEY, "aliases": MD_ALIASES}, "NH": {"normalize": nh_code},
                "OK": {"ccd_key": OK_CCD_KEY}, "NJ": {"ccd_key": NJ_CCD_KEY}}


def main():
    states = [s.upper() for s in sys.argv[1:]] or [s for s in STUDY_STATES if s in READERS]
    ccd, panel = ccd_codes(), panel_schools()
    stats = []
    for st in states:
        for source, reader in READERS[st].items():
            rows = reader()
            print(f"[{st}] {source}: {len(rows):,} school rows, classes "
                  f"{rows['class_year'].min()}-{rows['class_year'].max()}")
            stats += summarize(st, source, rows, ccd, panel)
    t = pd.DataFrame(stats)
    print(t.to_string(index=False))
    if not sys.argv[1:]:
        REVIEW_OUT.parent.mkdir(parents=True, exist_ok=True)
        t.to_csv(REVIEW_OUT, index=False)
        print(f"Wrote {REVIEW_OUT.relative_to(REVIEW_OUT.parents[2])}")


if __name__ == "__main__":
    main()
