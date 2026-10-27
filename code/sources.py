"""Registry of raw data sources downloaded by 00_download_raw_data.py.

Each Source is one file. To add a state, write a function that returns its
list of Sources and register it in SOURCES at the bottom of this file.

Labels record the publisher's own year label (e.g. "2023-2024"). How that label
maps to a graduating class is NOT assumed here; verify it from each file's
documentation before constructing the panel.
"""

import re
from dataclasses import dataclass
from urllib.parse import urljoin

from http_utils import get_json, get_text


@dataclass(frozen=True)
class Source:
    state: str          # two-letter postal code, or "US" for national sources
    source_id: str      # subdirectory under data/raw/<state>/
    filename: str       # local filename
    url: str
    year_label: str     # publisher's label, verbatim
    kind: str           # "data", "layout", "docs", or "page" (HTML snapshot)
    optional: bool = False  # if True, a 404 is logged rather than treated as an error
    note: str = ""


# ---------------------------------------------------------------------------
# Louisiana: LDOE "High School Performance" data library
# Landing page: https://doe.louisiana.gov/data-and-reports/high-school-performance
# Files 1997-2011 are also posted as zips; omitted because they predate the
# study window. The "?sfvrsn=" version parameter on the site's links is not
# required and is dropped so URLs survive re-uploads; re-uploads are instead
# detected by the SHA-256 check in the download manifest.
# ---------------------------------------------------------------------------

LA_PAGE = "https://doe.louisiana.gov/data-and-reports/high-school-performance"
LA_BASE = "https://doe.louisiana.gov/docs/default-source/data-management/"

LA_FILES = [
    # (year label, publisher filename)
    ("2011-2012", "2011-2012-college-enrollment-report.xlsx"),
    ("2012-2013", "2012-2013-college-enrollment-report.xlsx"),
    ("2013-2014", "2013-2014-college-enrollment-report.xlsx"),
    ("2014-2015", "2014-2015-college-enrollment-report.xlsx"),
    ("2015-2016", "2015-2016-college-enrollment-report.xlsx"),
    ("2015-2016", "2015-2016-college-persistence-by-subgroup.xlsx"),
    ("2016-2017", "2016-2017-college-enrollment-report.xlsx"),
    ("2016-2017", "2016-2017-college-enrollment-by-subgroup.xlsx"),
    ("2016-2017", "2016-2017-college-persistence-with-subgroups.xlsx"),
    ("2017-2018", "2017-2018-college-enrollment-with-subgroups.xlsx"),
    ("2017-2018", "2017-2018-college-persistence-with-subgroups.xlsx"),
    ("2018-2019", "2018-2019-college-enrollment-with-subgroups.xlsx"),
    ("2018-2019", "2018-2019-college-persistence-with-subgroups.xlsx"),
    ("2019-2020", "2019-2020-college-enrollment-with-subgroups.xlsx"),
    ("2019-2020", "2019-2020-college-persistence-with-subgroups.xlsx"),
    ("2020-2021", "2020-2021-college-enrollment-with-subgroups-(1).xlsx"),
    ("2020-2021", "2020-2021-college-persistence-with-subgroups.xlsx"),
    ("2021-2022", "2021-2022-college-enrollment-with-subgroups.xlsx"),
    ("2021-2022", "2021-2022-college-persistence-with-subgroups.xlsx"),
    ("2022-2023", "2022-2023-college-enrollment-with-subgroups.xlsx"),
    ("2022-2023", "2022-2023-high-school-graduate-college-enrollment-persistence-with-subgroups.xlsx"),
    ("2023-2024", "2023-2024-college-enrollment-with-subgroups.xlsx"),
]


# The ACT, graduation-rate, performance-score, and October enrollment-count
# files below are the inputs Deneault's replication package uses (see its
# README) for ACT controls, the cohort graduation rate in her outcome, and the
# grade-9 counts used to screen schools. There are too many irregularly named
# files to list by hand, so they are read from LDOE's library pages and
# filtered by filename pattern.
LA_LIBRARY = "https://doe.louisiana.gov/data-and-reports/"
LA_SCRAPED = [
    # (source_id, library page, filename pattern, note)
    ("ldoe_act", "high-school-performance",
     r"^(act-.*class-of-\d{4}|act-best-composite-scores-.*|\d{4}-\d{4}-state-lea-school-act-summary)\.xlsx$",
     "School-level ACT composite averages by graduating class. Deneault's pre_act "
     "(class of 2013) file is no longer posted; the class-of-2013 column of "
     "2012-2017-state-lea-school-act-summary.xlsx is the substitute (marked "
     "pre-data certification; its class-of-2014 values match the per-class file "
     "for all 301 schools, checked 2026-10-09)"),
    ("ldoe_grad_rates", "high-school-performance",
     r"^\d{4}.*(cohort-grad-rates|cohort-graduation).*\.xlsx$",
     "Cohort graduation rates; values above 95 percent are reported as '>95'"),
    ("ldoe_performance_scores", "performance-scores",
     r"^\d{4}(-\d{4})?-school-performance-score(s|-summary)\.xlsx$",
     "Deneault takes 2014 and 2015 graduation rates from the 2015 and 2016 files"),
    ("ldoe_tops", "high-school-performance",
     r"^(class-of-\d{4}-tops-eligibility-by-school|tops-eligibles-by-school-and-parish-\d{4})\.pdf$",
     "TOPS (state merit aid) students processed, eligible, and recipients by high school, "
     "PDF only (Deneault had Excel). Each file has its own 'data as of' date, so recipient "
     "counts for recent classes are incomplete; the class of 2023 file is named differently"),
    ("ldoe_oct_counts", "enrollment-data",
     r"^oct-(20[1-9]\d)-multi-stats-\(total-by-site.*\.xlsx?$",
     "October 1 counts by site and grade; grade 9 counts lagged 3 years give the 9th-grade cohort"),
]


def _library_files(page, pattern):
    """Return (filename, url) for spreadsheet links on an LDOE library page."""
    html = get_text(LA_LIBRARY + page)
    seen = {}
    for href in re.findall(r'href="([^"]+\.(?:xlsx|xls|zip|pdf)[^"]*)"', html, re.I):
        url = href.split("?")[0]
        if url.startswith("/"):
            url = "https://doe.louisiana.gov" + url
        name = url.rsplit("/", 1)[-1]
        if re.match(pattern, name, re.I) and name not in seen:
            seen[name] = url
    return sorted(seen.items())


def louisiana():
    """Return LDOE college-enrollment files plus the scraped ACT, graduation-rate,
    performance-score, TOPS, and October-count files, with landing-page snapshots."""
    sources = [Source("LA", "ldoe_college_enrollment", "_landing_page.html",
                      LA_PAGE, "", "page")]
    for year, name in LA_FILES:
        sources.append(Source(
            "LA", "ldoe_college_enrollment",
            filename=name.replace("-(1)", ""),  # drop the publisher's re-upload suffix
            url=LA_BASE + name,
            year_label=year,
            kind="data",
        ))
    for source_id, page, pattern, note in LA_SCRAPED:
        sources.append(Source("LA", source_id, "_landing_page.html",
                              LA_LIBRARY + page, "", "page"))
        for name, url in _library_files(page, pattern):
            # Take the first year (or year range) in the filename as the label.
            year = re.search(r"(\d{4}(?:-\d{4})?)", name)
            sources.append(Source("LA", source_id, name, url,
                                  year[1] if year else "", "data", note=note))
    return sources


# ---------------------------------------------------------------------------
# Illinois: ISBE Report Card Data Library
# Landing page: https://www.isbe.net/Pages/Illinois-State-Report-Card-Data.aspx
# 2015-2017 are zipped, semicolon-delimited text with a separate layout file;
# 2018+ are single Excel workbooks. For 2015-2017 both the base zip and the
# "with assessment" zip are pulled; only the latter has ACT results. From 2018
# the workbook has an SAT sheet (Illinois moved from the ACT to the SAT, taken
# in grade 11, starting spring 2017). The 2026 public data set was not yet posted as of
# 2026-10-09 (only the glossary).
# ---------------------------------------------------------------------------

IL_PAGE = "https://www.isbe.net/Pages/Illinois-State-Report-Card-Data.aspx"
IL_DL = "https://www.isbe.net/_layouts/Download.aspx?SourceUrl=/Documents/"
IL_DOC = "https://www.isbe.net/Documents/"

IL_FILES = [
    # (report card year, kind, url, local filename)
    ("2015", "data",   IL_DOC + "rc15.zip",                              "rc15.zip"),
    ("2015", "data",   IL_DOC + "rc15-assessment.zip",                   "rc15-assessment.zip"),
    ("2015", "layout", IL_DL + "RC15-layout.xlsx",                       "RC15-layout.xlsx"),
    ("2015", "docs",   IL_DOC + "rc15-definition.pdf",                   "rc15-definition.pdf"),
    ("2016", "data",   IL_DOC + "rc16.zip",                              "rc16.zip"),
    ("2016", "data",   IL_DOC + "rc16_assessment.zip",                   "rc16_assessment.zip"),
    ("2016", "layout", IL_DL + "RC16-layout.xlsx",                       "RC16-layout.xlsx"),
    ("2016", "docs",   IL_DOC + "rc16-definition.pdf",                   "rc16-definition.pdf"),
    ("2017", "data",   IL_DOC + "rc17.zip",                              "rc17.zip"),
    ("2017", "data",   IL_DOC + "rc17_assessment.zip",                   "rc17_assessment.zip"),
    ("2017", "layout", IL_DL + "RC17_layout.xlsx",                       "RC17_layout.xlsx"),
    ("2017", "docs",   IL_DOC + "2017_Report_Card_Glossary.pdf",         "2017_Report_Card_Glossary.pdf"),
    ("2018", "data",   IL_DL + "Report-Card-Public-Data-Set.xlsx",       "2018-Report-Card-Public-Data-Set.xlsx"),
    ("2018", "docs",   IL_DOC + "Report-Card-Glossary.pdf",              "2018-Report-Card-Glossary.pdf"),
    ("2019", "data",   IL_DL + "2019-Report-Card-Public-Data-Set.xlsx",  "2019-Report-Card-Public-Data-Set.xlsx"),
    ("2019", "docs",   IL_DOC + "2019-Report-Card-Glossary-Terms.pdf",   "2019-Report-Card-Glossary-Terms.pdf"),
    ("2020", "data",   IL_DL + "2020-Report-Card-Public-Data-Set.xlsx",  "2020-Report-Card-Public-Data-Set.xlsx"),
    ("2020", "docs",   IL_DOC + "2020-Glossary-of-Terms.pdf",            "2020-Glossary-of-Terms.pdf"),
    ("2021", "data",   IL_DL + "2021-RC-Pub-Data-Set.xlsx",              "2021-RC-Pub-Data-Set.xlsx"),
    ("2021", "docs",   IL_DOC + "2021-Report-Card-Glossary-Terms.pdf",   "2021-Report-Card-Glossary-Terms.pdf"),
    ("2022", "data",   IL_DL + "2022-Report-Card-Public-Data-Set.xlsx",  "2022-Report-Card-Public-Data-Set.xlsx"),
    ("2022", "docs",   IL_DOC + "2022-Glossary-of-Terms.pdf",            "2022-Glossary-of-Terms.pdf"),
    ("2023", "data",   IL_DL + "23-RC-Pub-Data-Set.xlsx",                "2023-RC-Pub-Data-Set.xlsx"),
    ("2023", "docs",   IL_DOC + "2023-RC-Glossary-Terms.pdf",            "2023-RC-Glossary-Terms.pdf"),
    ("2024", "data",   IL_DL + "24-RC-Pub-Data-Set.xlsx",                "2024-RC-Pub-Data-Set.xlsx"),
    ("2024", "docs",   IL_DOC + "2024-RC-Glossary-Terms.pdf",            "2024-RC-Glossary-Terms.pdf"),
    ("2025", "data",   IL_DL + "2025-Report-Card-Public-Data-Set.xlsx",  "2025-Report-Card-Public-Data-Set.xlsx"),
    ("2025", "docs",   IL_DOC + "2025-Report-Card-Glossary-of-Terms.pdf", "2025-Report-Card-Glossary-of-Terms.pdf"),
    ("2026", "docs",   IL_DOC + "2026-RC-Glossary.pdf",                  "2026-RC-Glossary.pdf"),
]


def illinois():
    """Return the ISBE Report Card data, layout, and glossary files listed in IL_FILES."""
    sources = [Source("IL", "isbe_report_card", "_landing_page.html",
                      IL_PAGE, "", "page")]
    for year, kind, url, name in IL_FILES:
        sources.append(Source("IL", "isbe_report_card", name, url, year, kind))
    return sources


# ---------------------------------------------------------------------------
# New Jersey: NJDOE School Performance Reports databases
# Landing page: https://www.nj.gov/education/spr/download/
# File URLs follow the pattern built in the page's download.js. Years before
# 2015-2016 use a different archive layout and are not included yet.
# Reference guides for the newest year may not be posted at release; they are
# marked optional so a 404 does not stop the run.
# ---------------------------------------------------------------------------

NJ_PAGE = "https://www.nj.gov/education/spr/download/"
NJ_BASE = "https://www.nj.gov/education/sprreports/download/"
NJ_YEARS = [f"{y}-{y + 1}" for y in range(2015, 2025)]  # 2015-2016 ... 2024-2025


def new_jersey():
    """Return the NJDOE School Performance Report school-detail database, its layout
    file, and its (optional) reference documents for each year in NJ_YEARS."""
    sources = [Source("NJ", "njdoe_spr", "_landing_page.html", NJ_PAGE, "", "page")]
    for year in NJ_YEARS:
        for name, kind in [("Database_SchoolDetail.xlsx", "data"),
                           ("Database_SchoolLayout.xlsx", "layout")]:
            sources.append(Source(
                "NJ", "njdoe_spr", f"{year}_{name}",
                f"{NJ_BASE}DataFiles/{year}/{name}", year, kind,
            ))
        for name in ["ReferenceGuide.pdf", "DataPrivacyRules.pdf", "FAQs.pdf"]:
            sources.append(Source(
                "NJ", "njdoe_spr", f"{year}_{name}",
                f"{NJ_BASE}Documents/{year}/{name}", year, "docs", optional=True,
            ))
    return sources


# ---------------------------------------------------------------------------
# FSA: FAFSA Completion by High School (national)
# Landing page: https://studentaid.gov/data-center/student/application-volume/fafsa-completion-high-school
# The page is a JavaScript app; its content (including every archive link) is
# served as JSON from the same path with ".json" appended. Each archive is a
# national snapshot "as of" a month-end date covering the application cycles
# open at that time. Archive filenames are inconsistent, so local files are
# renamed from the page's date label; the publisher's filename is kept in the
# manifest note. In a few cases the filename date differs from the label
# (e.g. label "June 30, 2019", file HS_ARCHIVE06282019.xls).
# Per the page: files labeled "(18 year olds)" (Apr-Jun 2017) use the earlier
# age cutoff (no older than 18); all others use no older than 19.
# Only the December 31 snapshots and the newest June 30 snapshot are
# downloaded. Following Deneault's cleaningFAFSA_aejep.do, a class's FCR
# numerator (completions through June) is taken from the fixed prior-cycle
# "Through June" column of a later December file, not from the preliminary
# June 30 snapshot; those files also carry the prior cycle's "Through December"
# column. The Dec 31 file of year Y+1 holds the class of Y ("Through June Y"),
# so Dec 2016 is the class of 2015. The newest June file covers the two classes
# with no such December file yet: the previous class in its prior-cycle column
# and the current class (preliminary). "(18 year olds)" files (Apr-Jun 2017) are skipped so every
# file uses the age-19 cutoff. The filter is on the page's date label, not the
# publisher filename, since the two sometimes disagree.
# The current per-state files (LA.xls, ...) are overwritten every two weeks
# and are not downloaded; the month-end archives are the stable record.
# ---------------------------------------------------------------------------

FSA_ROOT = "https://studentaid.gov"
FSA_PAGE = FSA_ROOT + "/data-center/student/application-volume/fafsa-completion-high-school"
FSA_DOCS = {
    "_landing_page.json": FSA_PAGE + ".json",
    "_data_details.json": FSA_ROOT + "/data-center/student/application-volume/fafsa-completion-data.json",
    "_faq.json": FSA_ROOT + "/data-center/student/application-volume/faq.json",
}
MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def _anchors(node):
    """Yield every {"widgetType": "anchor"} dict in the page JSON."""
    if isinstance(node, dict):
        if node.get("widgetType") == "anchor":
            yield node
        for v in node.values():
            yield from _anchors(v)
    elif isinstance(node, list):
        for v in node:
            yield from _anchors(v)


def fsa_fafsa_completion():
    """Return the FSA documentation pages, each December 31 FAFSA-completion-by-
    high-school archive, and the newest June 30 archive (all age-19 cutoff), read
    from the landing page's JSON."""
    sources = [Source("US", "fsa_fafsa_completion", name, url, "", "page")
               for name, url in FSA_DOCS.items()]
    archives = []  # (month, date, label, href) for every age-19 archive
    for a in _anchors(get_json(FSA_DOCS["_landing_page.json"])):
        href, label = a.get("href") or "", a.get("value") or ""
        # Archive links are the only anchors with "ARCHIVE" in the URL.
        if "ARCHIVE" not in href.upper():
            continue
        # Labels look like "June 30, 2017" or "June 30, 2017 (18 year olds)";
        # one is misspelled ("Februrary"), so match on the first three letters.
        m = re.match(r"([A-Za-z]{3})[a-z]*\.? (\d{1,2}), (\d{4})", label)
        if not m:
            raise ValueError(f"unrecognized FSA archive label: {label!r} ({href})")
        if "18 year" in label:
            continue
        month = m[1].lower()
        archives.append((month, f"{m[3]}-{MONTHS[month]:02d}-{int(m[2]):02d}", label, href))

    # ISO dates sort chronologically, so max() is the newest June file.
    newest_june = max(date for month, date, _, _ in archives if month == "jun")
    for month, date, label, href in sorted(archives, key=lambda a: a[1]):
        if month != "dec" and date != newest_june:
            continue
        ext = href.rsplit(".", 1)[-1].lower()
        sources.append(Source(
            "US", "fsa_fafsa_completion",
            filename=f"fafsa_hs_{date}.{ext}",
            url=FSA_ROOT + href.replace(" ", "%20"),  # some filenames contain spaces
            year_label=date,
            kind="data",
            note=f"label: {label}; publisher file: {href.rsplit('/', 1)[-1]}",
        ))
    return sources


# ---------------------------------------------------------------------------
# CCD: NCES Common Core of Data, school-level nonfiscal files (national)
# Landing page: https://nces.ed.gov/ccd/files.asp
# The page lists files from a JSON API; the call below is the one the page
# makes for Nonfiscal (2) x School level (7), all years. For each school year
# only the current version (versionOrder 0) is kept, with flat files rather
# than SAS duplicates and PDF rather than zipped documentation. Through
# 2013-14 each year is one combined file; from 2014-15 it is split into
# Directory, Membership, Staff, School Characteristics, and Lunch Program
# Eligibility. Grade-9 counts lagged three years for the class of 2015 need
# 2011-12, so that is the first year pulled. The newest year may be
# preliminary and incomplete (2025-26 had only Directory as of 2026-10-09).
# ---------------------------------------------------------------------------

CCD_API = "https://nces.ed.gov/ccd/datatables/api/File/2/7/0/0/0/0"
CCD_FIRST_YEAR = 2011


def ccd_school():
    """Return the current-version CCD school-level nonfiscal data and documentation
    files for each school year from CCD_FIRST_YEAR on, read from the NCES file API."""
    sources = [Source("US", "nces_ccd_school", "_file_list.json", CCD_API, "", "page")]
    for year in get_json(CCD_API)["selectionGroupModels"]:
        # One undated entry links to the EDGE website rather than a file.
        if not year["schoolYear"]:
            continue
        start = int(year["schoolYear"][:4])
        if start < CCD_FIRST_YEAR:
            continue
        label = f"{start}-{start + 1}"
        for title in year["titleGroups"]:
            for element in title["elementGroups"]:
                # versionOrder 0 is the current release; others are superseded.
                if element["versionOrder"] != 0:
                    continue
                kind = {"Data File": "data", "Documentation": "docs"}.get(element["elementType"])
                if kind is None:
                    continue
                for component in element["componentGroups"]:
                    for f in component["files"]:
                        desc = f["description"]
                        if desc.startswith("SAS File") or "(ZIP)" in desc:
                            continue
                        # A few entries give site-relative URLs.
                        url = urljoin(CCD_API, f["fileURL"])
                        sources.append(Source(
                            "US", "nces_ccd_school",
                            filename=f"{label}/{url.rsplit('/', 1)[-1]}",
                            url=url,
                            year_label=label,
                            kind=kind,
                            note=f"{title['title']}; {(component['component'] or 'Combined file').strip()}; {desc}",
                        ))
    return sources


# ---------------------------------------------------------------------------
# ACGR: EDFacts school-level 4-year adjusted cohort graduation rates (national)
# The primary source is ED's EDFacts data files, but ed.gov blocks scripted
# downloads (403 from an Azure firewall, checked 2026-10-09). These files are
# Urban Institute's Education Data Portal republication of the same EDFacts
# data, keyed by NCES school ID. Secondary source: rates are reported as
# ranges for privacy (grad_rate_low/high/midpt), as in EDFacts. Available for
# Urban "year" 2010-2019; nothing later was posted as of 2026-10-09. Urban
# year Y is the graduating class of Y+1: Urban 2017 and 2018 rates matched
# LDOE's class-of-2018 and class-of-2019 school files for 100% of ~230 linked
# Louisiana schools (vs. ~35% for the adjacent class), checked 2026-10-09.
# Docs: https://educationdata.urban.org/documentation/schools.html#edfacts_grad_rates
# ---------------------------------------------------------------------------

ACGR_URL = "https://educationdata.urban.org/csv/edfacts/schools_edfacts_grad_rates_{}.csv"
ACGR_YEARS = range(2010, 2020)


def acgr_school():
    """Return Urban Institute's yearly school-level EDFacts graduation-rate CSVs."""
    sources = [Source("US", "edfacts_acgr_urban", "_endpoints.json",
                      "https://educationdata.urban.org/api/v1/api-endpoints/", "", "page")]
    for y in ACGR_YEARS:
        sources.append(Source("US", "edfacts_acgr_urban", f"schools_edfacts_grad_rates_{y}.csv",
                              ACGR_URL.format(y), str(y), "data",
                              note="Urban Institute republication of EDFacts ACGR"))
    return sources


# ---------------------------------------------------------------------------
# EDGE: NCES public school locations, including the urban-centric locale code
# Landing page: https://nces.ed.gov/programs/edge/Geographic/SchoolLocations
# Deneault splits results by rural vs. urban using this locale code. From
# 2014-15 on, locale is no longer in the CCD school files and is published
# here instead; for 2011-12 to 2013-14 it is the ULOCAL field of the CCD
# files above. The yearly files (2015-16 on) are read from the landing page,
# Its newest links use a "~/data/" prefix and returned 404 on 2026-10-09
# (apparently placeholders for unreleased files), so those are optional.
# The 2014-15 file is listed under CCD instead of on this page.
# ---------------------------------------------------------------------------

EDGE_PAGE = "https://nces.ed.gov/programs/edge/Geographic/SchoolLocations"
EDGE_DATA = "https://nces.ed.gov/programs/edge/data/"


def edge_school_locations():
    """Return the EDGE public school location files (2014-15 from CCD, 2015-16 on
    scraped from the landing page) and the technical documentation."""
    sources = [
        Source("US", "nces_edge_locations", "_landing_page.html", EDGE_PAGE, "", "page"),
        Source("US", "nces_edge_locations", "EDGE_GEOCODE_PUBLIC_TECHDOC.pdf",
               "https://nces.ed.gov/programs/edge/docs/EDGE_GEOCODE_PUBLIC_TECHDOC.pdf", "", "docs"),
        Source("US", "nces_edge_locations", "EDGE_GEOIDS_201415_PUBLIC_SCHOOL_csv.zip",
               "https://nces.ed.gov/ccd/data/zip/EDGE_GEOIDS_201415_PUBLIC_SCHOOL_csv.zip",
               "2014-2015", "data", note="Listed under CCD 2014-15 geographic data"),
        Source("US", "nces_edge_locations", "2017010_EDGE_GEOIDS_201415_160913_Documentation.zip",
               "https://nces.ed.gov/ccd/data/zip/2017010_EDGE_GEOIDS_201415_160913_Documentation.zip",
               "2014-2015", "docs"),
    ]
    # Map each two-year code (e.g. "1516") to the link's path prefix.
    links = {yy: prefix for prefix, yy in
             re.findall(r'href="([^"]*?)EDGE_GEOCODE_PUBLICSCH_(\d{4})\.zip"', get_text(EDGE_PAGE))}
    for yy, prefix in sorted(links.items()):
        label = f"20{yy[:2]}-20{yy[2:]}"
        placeholder = prefix.startswith("~")
        sources.append(Source("US", "nces_edge_locations", f"EDGE_GEOCODE_PUBLICSCH_{yy}.zip",
                              f"{EDGE_DATA}EDGE_GEOCODE_PUBLICSCH_{yy}.zip", label, "data",
                              optional=placeholder,
                              note="linked with ~/data/ prefix" if placeholder else ""))
    return sources


# Download groups: command-line name -> function returning that group's Sources.
SOURCES = {
    "LA": louisiana,
    "IL": illinois,
    "NJ": new_jersey,
    "FSA": fsa_fafsa_completion,
    "CCD": ccd_school,
    "ACGR": acgr_school,
    "EDGE": edge_school_locations,
}
