"""Registry of raw data sources downloaded by 00_download_raw_data.py.

Each Source is one file. To add a state, write a function that returns its
list of Sources and register it in SOURCES at the bottom of this file. Most
publishers fit one of three shared helpers, so a state function is usually a
few lines:
  scraped()  every file on one or more landing pages whose name matches a pattern
  listed()   files whose URLs follow a fixed pattern (pages that block scripts)
  Source(..., fetch=...)  files that need a form post or an API call

CATALOG (bottom of the file) lists every state x measure the project needs,
with the publisher, the source_id that holds it, coverage, and whether it can
be downloaded by script; 00_download_raw_data.py writes it to
output/tables/state_data_sources.csv.

Labels record the publisher's own year label (e.g. "2023-2024"). How that label
maps to a graduating class is NOT assumed here; verify it from each file's
documentation before constructing the panel.

The HTTP helpers (open_url with retries, get_json, get_text) are defined here
too and used by 00_download_raw_data.py. Standard library only.
"""

import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace
from functools import partial
from html import unescape
from urllib.parse import unquote, urlencode, urljoin

from config import STATE_FIPS


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

# An honest project User-Agent (not a browser string). Some servers (LDOE, MLDS
# Center, CDE Colorado) refuse Python's default 'Python-urllib' agent, and
# studentaid.gov stalls on it; all accept this one (tested 2026-11-01).
HEADERS = {
    "User-Agent": "fa26-1433-research-downloader/1.0 (academic research)",
    "Accept": "*/*",
}
RETRIES = 3       # attempts per request before giving up on a network error
CHUNK = 1 << 20   # bytes read per block when streaming or hashing (1 MiB)


def session():
    """Return a URL opener that keeps cookies, for sites that need a session."""
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))


def open_url(url, data=None, opener=None, timeout=120, method=None):
    """Open url (POST if data is given; method overrides, e.g. "HEAD") with
    retries on network errors.

    HTTP errors are raised immediately. opener defaults to urllib's global one.
    """
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    for attempt in range(1, RETRIES + 1):
        try:
            return (opener.open(req, timeout=timeout) if opener
                    else urllib.request.urlopen(req, timeout=timeout))
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == RETRIES:
                raise
            print(f"    retry {attempt}/{RETRIES - 1} after {type(e).__name__}: {e}")
            # Back off longer after each failure (5 s, then 10 s).
            time.sleep(5 * attempt)


def get_json(url):
    """Fetch url and parse the response body as JSON."""
    with open_url(url) as r:
        return json.load(r)


def read_text(response):
    """Return a response body as text, using the server's charset (UTF-8 if none)."""
    return response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")


def get_text(url):
    """Fetch url and return the body as text."""
    with open_url(url) as r:
        return read_text(r)


@dataclass(frozen=True)
class Source:
    state: str          # two-letter postal code, or "US" for national sources
    source_id: str      # subdirectory under data/raw/<state>/
    filename: str       # local filename
    url: str            # file URL, or the page/API it comes from when fetch is set
    year_label: str     # publisher's label, verbatim
    kind: str           # "data", "layout", "docs", or "page" (HTML snapshot)
    optional: bool = False  # if True, a 404 is logged rather than treated as an error
    note: str = ""
    # Zero-argument function returning an open response, for files that need a
    # form post or a session; when None the file is a plain GET of url.
    fetch: object = field(default=None, compare=False, repr=False)
    # True for files the publisher blocks to scripts, exported by hand in a
    # browser (steps in note and docs/source-notes.md). The downloader never
    # fetches these; it records them in the manifest and checks their hash.
    manual: bool = False


# ---------------------------------------------------------------------------
# Shared helpers for building Source lists
# ---------------------------------------------------------------------------

def year_label(name):
    """Return the first year or year range in a filename (e.g. "2023-2024", "24-25"), or ""."""
    m = re.search(r"((?:19|20)\d{2}(?:-(?:19|20)?\d{2})?)", name) or re.search(r"(?<!\d)(\d{2}-\d{2})(?!\d)", name)
    return m[1] if m else ""


def local_name(url):
    """Local filename for a URL: its unquoted last path segment, spaces as underscores."""
    return unquote(url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]).replace(" ", "_")


def page_links(page, pattern, html=None):
    """Return the absolute URLs (query dropped, in page order) of links on page
    whose local filename matches the regex pattern."""
    html = get_text(page) if html is None else html
    seen = {}
    for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.I):
        url = urljoin(page, unescape(href.strip())).split("?")[0].split("#")[0]
        if re.search(pattern, local_name(url), re.I):
            seen.setdefault(url, None)
    return list(seen)


def snapshot(state, source_id, page, name="_landing_page.html"):
    """Source for an HTML snapshot of a landing page (refreshed on every run)."""
    return Source(state, source_id, name, page, "", "page")


def scraped(state, source_id, pages, pattern, note="", name=local_name, optional=False):
    """Sources for every file linked from pages whose filename matches pattern,
    plus a snapshot of each page. name(url) gives the local filename."""
    pages = [pages] if isinstance(pages, str) else pages
    out, seen = [], set()
    for i, page in enumerate(pages):
        out.append(snapshot(state, source_id, page,
                            "_landing_page.html" if len(pages) == 1 else f"_landing_page_{i + 1}.html"))
        for url in page_links(page, pattern):
            fname = name(url)
            if fname not in seen:
                seen.add(fname)
                out.append(Source(state, source_id, fname, url, year_label(fname), "data",
                                  optional=optional, note=note))
    return out


def listed(state, source_id, urls, page=None, note="", optional=False, name=local_name):
    """Sources for a fixed list of file URLs (used when the landing page blocks
    scripts or the file names follow a known pattern)."""
    out = [snapshot(state, source_id, page)] if page else []
    for url in urls:
        fname = name(url)
        out.append(Source(state, source_id, fname, url, year_label(fname), "data",
                          optional=optional, note=note))
    return out


def served_name(url):
    """Filename the server gives url (Content-Disposition, via a HEAD request),
    or the URL's own last segment if it gives none."""
    with open_url(url, method="HEAD") as r:
        m = re.search(r'filename="?([^";]+)"?', r.headers.get("Content-Disposition", ""))
    return m[1].strip().replace(" ", "_") if m else local_name(url)


def resolved(state, source_id, pages, href, pattern, note="", optional=False):
    """Like scraped(), for sites whose links are opaque IDs: every link on pages
    whose URL matches the regex href is resolved to its served filename, and
    kept if that name matches pattern. Each page is snapshotted."""
    out, seen = [], set()
    for i, page in enumerate(pages):
        html = get_text(page)
        out.append(snapshot(state, source_id, page, f"_landing_page_{i + 1}.html"))
        for url in page_links(page, ".", html):
            if re.search(href, url) and url not in seen:
                seen.add(url)
                fname = served_name(url)
                if re.search(pattern, fname, re.I) and fname not in {s.filename for s in out}:
                    out.append(Source(state, source_id, fname, url, year_label(fname), "data",
                                      optional=optional, note=note))
    return out


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


def louisiana():
    """Return LDOE college-enrollment files plus the scraped ACT, graduation-rate,
    performance-score, TOPS, and October-count files, with landing-page snapshots."""
    sources = [snapshot("LA", "ldoe_college_enrollment", LA_PAGE)]
    for year, name in LA_FILES:
        sources.append(Source(
            "LA", "ldoe_college_enrollment",
            filename=name.replace("-(1)", ""),  # drop the publisher's re-upload suffix
            url=LA_BASE + name,
            year_label=year,
            kind="data",
        ))
    for source_id, page, pattern, note in LA_SCRAPED:
        sources += scraped("LA", source_id, LA_LIBRARY + page, pattern, note)
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

# The 2015-2017 assessment zips (ACT, PARCC) are no longer downloaded
# (test scores are not a control, DECISIONS 2026-11-01).
IL_FILES = [
    # (report card year, kind, url, local filename)
    ("2015", "data",   IL_DOC + "rc15.zip",                              "rc15.zip"),
    ("2015", "layout", IL_DL + "RC15-layout.xlsx",                       "RC15-layout.xlsx"),
    ("2015", "docs",   IL_DOC + "rc15-definition.pdf",                   "rc15-definition.pdf"),
    ("2016", "data",   IL_DOC + "rc16.zip",                              "rc16.zip"),
    ("2016", "layout", IL_DL + "RC16-layout.xlsx",                       "RC16-layout.xlsx"),
    ("2016", "docs",   IL_DOC + "rc16-definition.pdf",                   "rc16-definition.pdf"),
    ("2017", "data",   IL_DOC + "rc17.zip",                              "rc17.zip"),
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
    ("2026", "data",   IL_DL + "2026-RC-Public-Data-Set.xlsx",           "2026-RC-Public-Data-Set.xlsx"),
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
# Alabama
# ALSDE Cohort Graduation Rate app (cohort.alsde.edu): an ASP.NET/DevExpress
# page. Each 4-year cohort is exported to XLS by posting the page's form with
# the cohort type (4) and base year (grad year - 3); the base-year list comes
# from the page's combo-box callback. One school row per subgroup with
# Total Students (cohort), Federal Graduates, rates, completers, dropouts;
# suppressed counts are "~" (the rate and cohort are usually still given).
# School codes are ALSDE system-school codes (crosswalk via CCD ST_SCHID).
# ACHE posts only its newest college-going summary (PDF, NSC data, by high
# school) at a fixed URL; earlier years are no longer on ache.edu.
# ACHE High School Graduate Reports (data.ache.edu/Rpt_HighSchool, ASP.NET):
# each Alabama public high school's graduates (from ALSDE) and how many enrolled
# in Alabama PUBLIC colleges that term, split 2-year / 4-year. One "Basic"
# Excel export per fall term (fall Y = class Y), fetched by posting the form.
# ---------------------------------------------------------------------------

ALSDE_URL = "https://cohort.alsde.edu/CohortSnapshotsGradRate"
ALSDE_P = "ctl00$ContentBody_CohortPublic$"
ACHE_CGR = "https://archive.ache.edu/RESEARCH/College-Going-Rate.pdf"
ACHE_HS = "https://data.ache.edu/Rpt_HighSchool"
ACHE_FIRST_CLASS = 2012


def _aspnet_form(html):
    """Return an ASP.NET page's hidden __* fields (view state etc.) as a dict."""
    return dict(re.findall(r'<input type="hidden" name="(__[A-Z]+)" id="[^"]*" value="([^"]*)"', html))


def _alsde_post(fields):
    """Load the ALSDE page in a new session, post fields with the 4-year cohort
    selected, and return the open response."""
    op = session()
    with open_url(ALSDE_URL, opener=op) as r:
        form = _aspnet_form(read_text(r))
    form.update({ALSDE_P + "txtApplicationViewKey_Cohort4Year": "Cohort",
                 "ContentBody_CohortPublic_ddlCohortType_VI": "4",
                 ALSDE_P + "ddlCohortType": "4-Year Cohort", **fields})
    return open_url(ALSDE_URL, data=urlencode(form).encode(), opener=op)


def _alsde_export(base):
    """Open the XLS export of the 4-year cohort with the given base year."""
    return _alsde_post({"ContentBody_CohortPublic_ddlCohortBaseYear_VI": base,
                        ALSDE_P + "ddlCohortBaseYear": base,
                        "__EVENTTARGET": ALSDE_P + "cbpnlCohortSnapshotsGradRate$btnCohortSnapshotsGradRateXlsExport"})


def _ache_hs_export(term):
    """Open ACHE's Basic High School Excel report for one term (value from the
    page's term list, e.g. '20241' = fall 2023), posting the form in a session."""
    op = session()
    with open_url(ACHE_HS, opener=op) as r:
        form = _aspnet_form(read_text(r))
    button = "ctl00$MainContent$imgHSBasic_EXCEL"
    form.update({"ctl00$MainContent$ddlHSYrs": term, f"{button}.x": "10", f"{button}.y": "10"})
    return open_url(ACHE_HS, data=urlencode(form).encode(), opener=op)


def ache_fall_terms():
    """Fall terms on ACHE's report page as {class: term value}: option 'FA23'
    (value 20241) is fall 2023, the class of 2023's first fall."""
    terms = re.findall(r'<option value="(\d{4}1)">FA(\d\d)</option>', get_text(ACHE_HS))
    return {2000 + int(yy): v for v, yy in terms if 2000 + int(yy) >= ACHE_FIRST_CLASS}


def alabama():
    """Return one ALSDE cohort export per graduating class and ACHE's newest
    college-going summary."""
    with _alsde_post({"__CALLBACKID": ALSDE_P + "ddlCohortBaseYear",
                      "__CALLBACKPARAM": "c0:LECC|0;;LBCRI|4;0:-2;"}) as r:
        bases = re.findall(r"'value':'(\d{4})','texts':\['[^']*','(\d{4}) - (\d{4})'", read_text(r))
    sources = [snapshot("AL", "alsde_cohort_grad", ALSDE_URL)]
    for base, _, grad in bases:
        sources.append(Source("AL", "alsde_cohort_grad", f"cohort4yr_class{grad}.xls", ALSDE_URL,
                              grad, "data", note=f"4-year cohort, base year {base}",
                              fetch=partial(_alsde_export, base)))
    sources.append(Source("AL", "ache_college_going", "College-Going-Rate_latest.pdf", ACHE_CGR, "", "data",
                          note="newest class only; the file at this URL is replaced each year"))
    sources.append(snapshot("AL", "ache_hs_reports", ACHE_HS))
    for cls, term in sorted(ache_fall_terms().items()):
        sources.append(Source("AL", "ache_hs_reports", f"ache_hs_basic_fall{cls}.xls", ACHE_HS, str(cls), "data",
                              note=f"class {cls} graduates enrolled in Alabama public colleges, fall {cls} (term {term})",
                              fetch=partial(_ache_hs_export, term)))
    return sources


# ---------------------------------------------------------------------------
# Maryland: MLDS Center "Maryland Public High School Graduates: College and
# Workforce Outcomes" data download (aggregate, suppressed; zip with one
# workbook and data notes). The zip is linked from the Dashboards page; its
# name carries the publication year, so it is found by pattern. The MSDE
# Report Card is not used (its download service rejects scripted requests).
# ---------------------------------------------------------------------------

MLDS_PAGE = "https://mldscenter.maryland.gov/Dashboards.html"


def maryland():
    """Return the MLDS Center high-school-to-college data download (zip)."""
    return scraped("MD", "mlds_hs_to_college", MLDS_PAGE, r"^HighSchoolToCollegeDashboard\d{4}DataDownload\.zip$",
                   note="college enrollment (immediate, within 1/2 years, complete) by school x cohort; data notes PDF inside")


# ---------------------------------------------------------------------------
# Texas
# TEA four-year graduation campus files (one page per class) and SAT/ACT
# campus files (one search page for older classes, a page per class from
# 2018). THECB "High School Graduates Enrolled in Higher Education by Campus"
# (fall after graduation; Texas institutions only): the report URL is the
# workbook itself; only fall 2019 on is in the current report center.
# ---------------------------------------------------------------------------

TEA_AR = "https://tea.texas.gov/data-reports/school-performance/accountability-research/"
TX_CLASSES = range(2014, 2025)
THECB = ("https://reportcenter.highered.texas.gov/reports/data/"
         "high-school-graduates-enrolled-in-higher-education-by-campus-fall-{}-xls/")


def texas():
    """Return TEA graduation campus files and THECB college enrollment by campus.
    (TEA SAT/ACT files are no longer downloaded: test scores are not a control,
    DECISIONS 2026-11-01.)"""
    grad_pages = [f"{TEA_AR}completion-graduation-and-dropout/four-year-graduation-and-dropout-data-class-{y}"
                  for y in TX_CLASSES]
    def grad_name(url):
        # File names vary by year (campus-data-download-4yr-2022-1.xlsx,
        # Campus_Data_Download_4yr_2018_v2.xlsx, .../2015/campus_data_download_4yr).
        return f"campus_4yr_class{re.findall(r'20\d\d', url)[-1]}.xlsx"
    # The class-of-2015 page links to an extensionless URL that returns 404
    # (checked 2026-10-31), so links without a file extension are optional.
    grad = [replace(s, optional=s.kind == "data" and not re.search(r"\.\w+$", s.url))
            for s in scraped("TX", "tea_grad", grad_pages, r"^campus.data.download.4yr", name=grad_name)]
    return (grad
            + listed("TX", "thecb_hs_enrolled", [THECB.format(y) for y in range(2019, 2025)],
                     name=lambda u: f"hsgrads_enrolled_by_campus_fall{year_label(u)}.xlsx",
                     note="Texas public and independent institutions only"))


# ---------------------------------------------------------------------------
# Colorado: CDE graduation/completion workbooks and matriculation rates
# CDE's file links are opaque (/fs/resource-manager/view/<id>), so files are
# named and selected by the filename the server sends (resolved()).
# Graduation: one state/district/school workbook per class, 2018-19 (class of
# 2019) to 2024-25, on the current page and its archive (earlier classes come
# from EDFacts ACGR, classes 2011-2020). Matriculation (college enrollment of
# graduates, CDHE-validated): one state/district/school workbook per class,
# 2019-2025, on the accountability data-files page and its prior-years page.
# ---------------------------------------------------------------------------

CO_SITE = "https://ed.cde.state.co.us/"
CO_GRAD_PAGES = [CO_SITE + "cdereval/graduation-completion-statistics",
                 CO_SITE + "cdereval/graduation-completion-statistics/data-insights-resources-archives"]
CO_MATRIC_PAGES = [CO_SITE + "accountability/data-tools/data-files",
                   CO_SITE + "accountability/performance-framework-flat-files-from-prior-years"]
CO_FILE = r"/fs/resource-manager/view/"
# School-level graduation workbooks only (not the trend, school-type, or
# still-enrolled files).
CO_GRAD = r"^\d{4}-\d{4}_(?=.*Grad)(?=.*(LEA-SCH|StateDistrictSchool|CombinedRelease|Rates_PRIVACY))"
CO_MATRIC = r"^\d{4}_?Matriculation.*\.xlsx$"


def colorado():
    """Return CDE school-level graduation/completion and matriculation workbooks."""
    return (resolved("CO", "cde_grad", CO_GRAD_PAGES, CO_FILE, CO_GRAD)
            + resolved("CO", "cde_matriculation", CO_MATRIC_PAGES, CO_FILE, CO_MATRIC,
                       note="college enrollment of graduates; CDHE-validated"))


# ---------------------------------------------------------------------------
# California: CDE downloadable files
# CDE's www pages sit behind a bot check (Radware), so file URLs are listed
# here; the files themselves are served from www3.cde.ca.gov without it.
# ACGR files (acgrYY = class 20YY; "Regular HS Diploma Graduates (Count)" and
# CohortStudents by school) carry version suffixes when revised, so names are
# taken from the ACGR page as of 2026-10-31. College-going (12-month) files:
# cgr12moYY = completers of 20YY (NSC plus CA systems).
# ---------------------------------------------------------------------------

CDE_DL = "https://www3.cde.ca.gov/demo-downloads/"
CA_ACGR = ["acgr17", "acgr18", "acgr19", "acgr20", "acgr21", "acgr22-v3", "acgr23-v2",
           "acgr24", "acgr25", "acgr26"]


def california():
    """Return CDE ACGR and 12-month college-going rate files."""
    return (listed("CA", "cde_acgr", [f"{CDE_DL}acgr/{n}.txt" for n in CA_ACGR],
                   name=lambda u: f"acgr_class20{re.search(r'acgr(\d\d)', u)[1]}.txt",
                   note="file structure: https://www.cde.ca.gov/ds/ad/fsacgr.asp")
            + listed("CA", "cde_cgr12", [f"{CDE_DL}cgr/cgr12mo{y}.txt" for y in range(15, 25)],
                     name=lambda u: f"cgr12mo_class20{re.search(r'mo(\d\d)', u)[1]}.txt", optional=True,
                     note="file structure: https://www.cde.ca.gov/ds/ad/fscgr12.asp; newest year optional"))


# ---------------------------------------------------------------------------
# Indiana
# CHE College Readiness / College-Going datasets (one workbook per cohort,
# school level; prior cohorts 2008-2016 in one file). IDOE Data Center:
# federal/state graduation-rate workbooks, school enrollment by grade and by
# ethnicity/FRL (2006-2026), and grade-11 SAT by school (the state's
# school-day SAT, taken by all juniors). The Data Center lists only the newest
# files; earlier ones (graduation rates 2014-2024, SAT 2023-2025) are on the
# Data Reports Archive page, scraped with the same filename pattern.
# ---------------------------------------------------------------------------

IN_CHE = "https://www.in.gov/che/college-going-reports/"
IN_DOE = "https://www.in.gov/doe/it/data-center-and-reports/"
IN_ARCHIVE = IN_DOE + "data-reports-archive/"
# Graduation-rate workbooks (not the 5-year rate) on both pages; the 2006-26
# enrollment workbooks from the Data Center only (the archive re-links them).
# Grade-11 SAT files are no longer downloaded (DECISIONS 2026-11-01).
IN_DOE_FILES = r"^\d{4}.*(?<!year-)grad(uation)?-?rate.*\.xlsx$"
IN_ENROLL = r"^school-enrollment-(grade|ethnicity).*2006-26.*\.xlsx$"


def indiana():
    """Return CHE college-going datasets and IDOE graduation, enrollment, and SAT files."""
    return (scraped("IN", "che_college_going", IN_CHE, r"College-(Going|Readiness)-Dataset.*\.xlsx$")
            + scraped("IN", "idoe_data_center", IN_DOE, f"{IN_DOE_FILES}|{IN_ENROLL}")
            + scraped("IN", "idoe_archive", IN_ARCHIVE, IN_DOE_FILES))


# ---------------------------------------------------------------------------
# New Hampshire: NH DOE iPlatform public reports (manual exports)
# my.doe.nh.gov returns 403 to scripted requests, so these are exported by hand
# in a browser and only registered here (manual=True). Each report runs one
# school year at a time (2012-2025); exported 2026-11-01 with Export > Excel.
# Files are named by the class year read from the report title inside each
# file ("2023 - 2024 ..." -> class 2024).
# iExplore (Tableau dashboard on jwt.nh.gov): the Post-secondary Enrollment
# Rate indicator by school, exported with Download > crosstab (Excel); each
# export holds the selected year and the two before it, so four exports cover
# 2016-2025. Files are named by the year columns in their header.
# ---------------------------------------------------------------------------

NH_REPORT = ("https://my.doe.nh.gov/iplatform/Report/Report?path=%2FBDMQ%2FiPlatform%20Reports%2F"
             "Performance%20Data%2FDropouts%20and%20Completers%2F{}&name={}&categoryName="
             "Dropouts%20and%20Completers&categoryId=23")
# source_id -> (iPlatform report name, local file prefix, what it holds)
NH_REPORTS = {
    "manual/iplatform_cohort_counts": ("Cohort Counts By School", "cohort_counts_by_school",
                                       "4-year cohort, graduates, graduation rate, dropouts by school"),
    "manual/iplatform_completers_status": ("Completers By Status By School", "completers_by_status_by_school",
                                           "completers by post-graduation status (% 4-year, <4-year college, ...)"),
}
NH_CLASSES = range(2012, 2026)
NH_IEXPLORE = ("https://jwt.nh.gov/?src_route=/iExplore/Explore-Dashboard&toolbar=Hidden"
               "&Width=1300px&Height=1600px")
NH_IEXPLORE_SPANS = ["2016-2016", "2017-2019", "2020-2022", "2023-2025"]


def new_hampshire():
    """Return the hand-exported iPlatform report files (one per report x class) and
    iExplore postsecondary-enrollment exports (one per three-year span)."""
    out = []
    for source_id, (report, prefix, what) in NH_REPORTS.items():
        url = NH_REPORT.format(*[report.replace(" ", "%20")] * 2)
        out += [Source("NH", source_id, f"{prefix}_class{y}.xlsx", url, str(y), "data", manual=True,
                       note=f"{what}; manual export: School Year {y}, Run Report, Export > Excel")
                for y in NH_CLASSES]
    out += [Source("NH", "manual/iexplore_postsecondary", f"postsecondary_enrollment_rate_{span}.xlsx",
                   NH_IEXPLORE, span, "data", manual=True,
                   note=("% enrolling in a 2- or 4-year institution within the year after graduation, by school; "
                         f"manual export: Download, Indicator Post-secondary Enrollment Rate, School, Year "
                         f"{span[-4:]}, crosstab Excel"))
            for span in NH_IEXPLORE_SPANS]
    return out


# ---------------------------------------------------------------------------
# Nebraska: NDE Nebraska Education Profile data downloads (2015-16 on)
# The NEP site is an Angular app; its file list and files come from the JSON
# API below. Kept: cohort graduation, college-going rate, ACT, membership,
# FRL, teachers, and the agency (school) list.
# CCPE college continuation workbook: the file behind the DOWNLOAD button of
# ccpe.nebraska.gov/college-continuation-rates (Tableau dashboard).
# ---------------------------------------------------------------------------

NE_API = "https://nepdata.education.ne.gov/api/v1/"
NE_KEEP = r"^(Agencies|Cohort|CollegeGoingRate|Membership|FreeReducedLunch|Teachers?_)"   # no ACT_ files
NE_CCPE = "https://ccpe.nebraska.gov/college-continuation-rates"
NE_CCPE_FILE = "https://ccpe.nebraska.gov/sites/default/files/FL_CollegeGoing.xlsx"


def nebraska():
    """Return NEP data files (one per measure and school year) listed by the NEP API."""
    sources = [Source("NE", "nde_nep", "_data_downloads.json", NE_API + "data/downloads", "", "page")]
    for year in get_json(NE_API + "data/downloads"):
        for f in year["files"]:
            if re.match(NE_KEEP, f["fileName"]):
                url = NE_API + "data/downloads/data-file?" + urlencode(
                    {"dataYear": year["dataYear"], "fileName": f["fileName"]})
                sources.append(Source("NE", "nde_nep", f["fileName"], url, year["dataYear"], "data",
                                      note=f["displayName"]))
    sources.append(Source("NE", "ccpe_continuation", "FL_CollegeGoing.xlsx", NE_CCPE_FILE, "2008-2025", "data",
                          note="on-time public HS graduates continuing to college by the following spring (NSC)"))
    return sources


# ---------------------------------------------------------------------------
# Oklahoma: OSRHE High School Indicators Project
# College-going rates (graduates and first-time in-state college entrants by
# high school site), mean ACT by site, and freshman GPA/remediation. Files for
# 2018 on are on the indicators page; 2012-2017 each have their own page.
# ---------------------------------------------------------------------------

OK_SITE = "https://okhighered.org/"
OK_PAGES = ["studies-reports/indicators/", "studies-reports/preparation/",
            "?p=3351", "?p=3353", "?p=3355", "?p=3357", "?p=3359", "?p=3361"]


def oklahoma():
    """Return OSRHE college-going-rate workbooks by high school (mean-ACT files are
    no longer downloaded, DECISIONS 2026-11-01)."""
    return scraped("OK", "osrhe_hs_indicators", [OK_SITE + p for p in OK_PAGES],
                   r"College-Going.*\.xlsx?$",
                   note="in-state public and private colleges; graduate counts by site")


# ---------------------------------------------------------------------------
# New York: NYSED data downloads (data.nysed.gov)
# Graduation Rate Database (cohort counts and graduates by school), Report
# Card Database (includes postsecondary enrollment from the class of 2022),
# and Enrollment Database. File names repeat across years, so the local name
# is prefixed with the year folder.
# ---------------------------------------------------------------------------

NY_PAGE = "https://data.nysed.gov/downloads.php"


def new_york():
    """Return NYSED graduation-rate, report-card, and enrollment databases."""
    def name(url):
        folder, base = url.split("/")[-2:]
        return f"{folder}_{local_name(base)}"
    return scraped("NY", "nysed_downloads", NY_PAGE, r"^(gradrate|SRC|enrollment).*\.zip$", name=name,
                   note="Access databases inside zips")


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
# Postsecondary enrollment trend files (from 2023-24 no longer in the SPR database).
NJ_ADDDATA = "https://www.nj.gov/education/spr/adddata"
# 4-year adjusted cohort graduation rates with school cohort and graduate counts,
# one file per cohort (by student group; cohorts 2020 on match the pattern).
NJ_ACGR_PAGE = f"{NJ_ADDDATA}/acgr.shtml"
NJ_ACGR_PATTERN = r"^Cohort20\d\d_4YearAdjustedCohortGraduationRates(andCounts)?byStudentGroup\.xlsx$"


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
    return (sources
            + scraped("NJ", "njdoe_postsecondary", NJ_ADDDATA, r"Postsecondary.*\.xlsx$",
                      note="fall and 16-month college enrollment rates by school, five classes per file")
            + scraped("NJ", "njdoe_acgr", NJ_ACGR_PAGE, NJ_ACGR_PATTERN,
                      note="4-year ACGR by school and student group, with cohort and graduated counts"))


# ---------------------------------------------------------------------------
# Connecticut: data.ct.gov (Socrata), CSDE and P20 WIN
# College enrollment by high school (P20 WIN: NSC-based enrollment, credit
# attainment, remediation) and the Next Generation Accountability System
# (school indicators including graduation and SAT). Socrata serves each
# dataset as CSV at a fixed URL.
# ---------------------------------------------------------------------------

CT_DATASETS = {"m3ib-yiy7": "college_enrollment_by_school.csv",
               "h28j-iix5": "next_generation_accountability.csv"}


def connecticut():
    """Return Connecticut's college-enrollment and accountability datasets as CSV."""
    return [Source("CT", "ct_open_data", name,
                   f"https://data.ct.gov/api/views/{key}/rows.csv?accessType=DOWNLOAD", "", "data",
                   note=f"https://data.ct.gov/d/{key}") for key, name in CT_DATASETS.items()]


# ---------------------------------------------------------------------------
# Pennsylvania: PDE high school graduation
# 4-year cohort graduation rates by school and "Graduates Public by School"
# (graduates by school with post-graduate plans), 2012-13 on.
# ---------------------------------------------------------------------------

PA_PAGE = "https://www.pa.gov/agencies/education/data-and-reporting/high-school-graduation"


def pennsylvania():
    """Return PDE 4-year cohort graduation rates and graduates by school."""
    return scraped("PA", "pde_graduation", PA_PAGE, r"4-year_cohort_grad.*\.xlsx$|^graduates_.*by.*school.*\.xlsx$")


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
# ED Data Express Data Library: school-level 4-year ACGR (FS150/DG695) and
# cohort count (FS151/DG696). Only school year 2020-21 (class 2021) is posted
# as a file; later school years exist only in the Data Download Tool, which
# answers scripts with a bot challenge (manual).
# Library: https://eddataexpress.ed.gov/download/data-library
EDE_ACGR_FILES = ["https://eddataexpress.ed.gov/sites/default/files/data_download/EID_9092/"
                  "SY2021_FS150_FS151_DG695_DG696_SCH_data_files.zip"]


def acgr_school():
    """Return Urban Institute's yearly school-level EDFacts graduation-rate CSVs."""
    sources = [Source("US", "edfacts_acgr_urban", "_endpoints.json",
                      "https://educationdata.urban.org/api/v1/api-endpoints/", "", "page")]
    for y in ACGR_YEARS:
        sources.append(Source("US", "edfacts_acgr_urban", f"schools_edfacts_grad_rates_{y}.csv",
                              ACGR_URL.format(y), str(y), "data",
                              note="Urban Institute republication of EDFacts ACGR"))
    return sources + listed("US", "edfacts_acgr_ede", EDE_ACGR_FILES,
                            note="ED Data Express Data Library: school 4-year ACGR and cohort, SY 2020-21 (class 2021)")


# ---------------------------------------------------------------------------
# ASSESS: EDFacts high school proficiency by school (Urban republication)
# Baseline school-ability measure for the robustness check (DECISIONS
# 2026-11-01): share proficient in reading and math on each state's high
# school test (Urban grade_edfacts 9), all students, keyed by NCES school ID.
# The bulk CSVs (~600 MB/year, all grades and subgroups) are skipped; the API
# filtered to one state and the high school grade fits in one page (Texas
# 2016: 2,152 rows), saved as JSON per state x year. Proficiency is reported
# as ranges (pct_prof_low/high/midpt; negative codes = suppressed). Urban
# year Y = school year Y-(Y+1). Available 2009-2018 and 2020; 2014-2018
# covers every state's pre-policy years.
# Docs: https://educationdata.urban.org/documentation/schools.html#edfacts_assessments
# ---------------------------------------------------------------------------

ASSESS_API = "https://educationdata.urban.org/api/v1/schools/edfacts/assessments/{}/grade-9/"
ASSESS_YEARS = range(2014, 2019)


def edfacts_assessments():
    """Return one Urban EDFacts high school assessment JSON per study state x year."""
    return [Source("US", "edfacts_assess_urban", f"hs_assess_{st}_{y}.json",
                   ASSESS_API.format(y) + "?" + urlencode({"fips": fips, "limit": 10000}),
                   str(y), "data", note="Urban Institute republication of EDFacts assessments")
            for st, fips in STATE_FIPS.items() for y in ASSESS_YEARS]


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


# ---------------------------------------------------------------------------
# PSS: NCES Private School Universe Survey, public-use files (national)
# Landing page: https://nces.ed.gov/surveys/pss/pssdata.asp
# Biennial; one row per private school with its PSS ID (PPIN), name, city,
# state, and grade span. FSA's 8-character School Codes for private schools
# (from the class of 2021 on) are PSS IDs, so these files link pre-2021 FSA
# private-school records the way CCD links public ones. CSV releases start
# with 2013-14, which also covers the class of 2015's senior year. The
# 2017-18 to 2023-24 "Frame Data" CSVs listed on the page are sampling frames,
# not the survey files, and are not downloaded.
# ---------------------------------------------------------------------------

PSS_PAGE = "https://nces.ed.gov/surveys/pss/pssdata.asp"
PSS_BASE = "https://nces.ed.gov/surveys/pss/"
PSS_YEARS = [2013, 2015, 2017, 2019, 2021, 2023]  # first year of each wave


def pss_private_schools():
    """Return each PSS wave's public-use CSV zip and codebook, plus a page snapshot."""
    sources = [Source("US", "nces_pss", "_landing_page.html", PSS_PAGE, "", "page")]
    for y in PSS_YEARS:
        label = f"{y}-{y + 1}"
        yy = f"{y % 100:02d}{(y + 1) % 100:02d}"
        sources.append(Source("US", "nces_pss", f"pss{yy}_pu_csv.zip",
                              f"{PSS_BASE}zip/pss{yy}_pu_csv.zip", label, "data"))
        sources.append(Source("US", "nces_pss", f"codebook{y}_{(y + 1) % 100:02d}.pdf",
                              f"{PSS_BASE}pdf/codebook{y}_{(y + 1) % 100:02d}.pdf", label, "docs"))
    return sources


# ---------------------------------------------------------------------------
# Federal: CRDC (counselors, English learners), EDGE School Neighborhood
# Poverty Estimates, IPEDS institution directory (college locations)
# ---------------------------------------------------------------------------

CRDC_YEARS = ["2013-14", "2015-16", "2017-18", "2020-21", "2021-22"]
EDGE_SNP = "https://nces.ed.gov/programs/edge/Economic/NeighborhoodPoverty"
IPEDS_YEARS = range(2014, 2025)


def federal_extras():
    """Return CRDC school files, EDGE neighborhood poverty files, and IPEDS HD files."""
    return (listed("US", "crdc", [f"https://civilrightsdata.ed.gov/assets/ocr/docs/{y}-crdc-data.zip"
                                  for y in CRDC_YEARS])
            + scraped("US", "edge_neighborhood_poverty", EDGE_SNP, r"^EDGE_SIDE.*PUBSCHS\d{4}\.zip$")
            + listed("US", "ipeds_hd", [f"https://nces.ed.gov/ipeds/datacenter/data/HD{y}.zip"
                                        for y in IPEDS_YEARS], optional=True,
                     note="institution directory with latitude/longitude, sector, level"))


# ---------------------------------------------------------------------------
# Catalog: every state x measure in docs/state-data-requirements.md, where it
# comes from, and whether it is downloaded by script. Measures:
#   graduates (FCR denominator), grad_rate (ACGR / cohort), cohort9 (grade-9
#   or adjusted cohort count), act_sat, college_enroll, enrollment_race, frl,
#   teachers (student/teacher ratio), counselors_el, poverty, college_location.
# status: scripted (in SOURCES), partial (scripted, some classes missing),
#   dropped (was downloaded, no longer needed; removed from SOURCES, files
#   left on disk), manual (publisher blocks scripts; exported by hand, registered with
#   manual=True and hash-checked), blocked (publisher blocks scripted access,
#   nothing obtained yet), deferred (state left out for now), not_found (no
#   school-level public source found yet).
# ---------------------------------------------------------------------------

CATALOG_FIELDS = ["state", "measure", "publisher", "source_id", "classes", "access", "status", "note"]
CATALOG = [
    # Federal sources used for every state
    ("US", "enrollment_race; cohort9; teachers; frl; school_type", "NCES CCD", "nces_ccd_school",
     "2011-12 to 2025-26 school years", "NCES file API", "scripted", "grade-9 counts lagged 3 years give the cohort"),
    ("US", "grad_rate; cohort9", "EDFacts via Urban Institute", "edfacts_acgr_urban", "classes 2011-2020",
     "CSV", "partial", "ranges for privacy; nothing after class 2020"),
    ("US", "grad_rate; cohort9", "EDFacts via ED Data Express (Data Library)", "edfacts_acgr_ede", "class 2021",
     "direct file", "scripted", "school level; classes 2022 on only in the Data Download Tool (bot check; manual)"),
    ("US", "act_sat", "EDFacts via Urban Institute", "edfacts_assess_urban", "2014-15 to 2018-19 school years",
     "JSON API", "scripted", "high school % proficient (reading, math); baseline ability for the robustness check"),
    ("US", "locale", "NCES EDGE", "nces_edge_locations", "2014-15 on", "zip", "scripted", ""),
    ("US", "poverty", "NCES EDGE School Neighborhood Poverty", "edge_neighborhood_poverty", "2015-16 to 2021-22",
     "zip", "scripted", ""),
    ("US", "counselors_el", "ED Office for Civil Rights CRDC", "crdc", "2013-14, 2015-16, 2017-18, 2020-21, 2021-22",
     "zip", "scripted", "biennial"),
    ("US", "college_location", "NCES IPEDS HD", "ipeds_hd", "2014-2024", "zip", "scripted", ""),
    # Louisiana
    ("LA", "grad_rate", "LDOE", "ldoe_grad_rates", "2014-2025", "page scrape", "scripted", "rates only, no counts"),
    ("LA", "act_sat", "LDOE", "ldoe_act", "2013-2025", "page scrape", "scripted", "universal ACT"),
    ("LA", "graduates; college_enroll", "LDOE", "ldoe_college_enrollment", "2012-2024", "listed", "scripted",
     "NSC (+ Board of Regents from 2018); enrolled by Oct 31 of 1st fall / all graduates that year"),
    ("LA", "cohort9", "LDOE October counts", "ldoe_oct_counts", "2010-2025", "page scrape", "scripted", ""),
    # Illinois
    ("IL", "college_enroll", "ISBE Report Card (NSC)", "isbe_report_card", "classes 2013-2024", "listed", "scripted",
     "12 and 16 months; report card year Y = class Y-2; rates only"),
    ("IL", "grad_rate; act_sat; frl", "ISBE Report Card", "isbe_report_card",
     "report cards 2015-2026", "listed", "scripted", "ACT to 2016, SAT from 2017; low-income share; cohort graduate counts from 2024"),
    # Alabama
    ("AL", "graduates; grad_rate", "ALSDE Cohort Graduation Rate app", "alsde_cohort_grad", "2019-2025",
     "form post", "partial", "exports for classes 2012-2018 are header-only; federal graduate counts often '~', cohort x rate reproduces them"),
    ("AL", "college_enroll", "ACHE", "ache_college_going", "class 2025 only", "PDF", "partial",
     "earlier ACHE files 404 after site change; ALSDE 2017-18 report and PARCA dashboard not yet scripted; class 2023 never published"),
    ("AL", "graduates; college_enroll", "ACHE High School Graduate Reports", "ache_hs_reports", "classes 2012-2024",
     "form post", "scripted", "fall enrollment in Alabama PUBLIC colleges only (2-year, 4-year); graduates from ALSDE"),
    ("AL", "act_sat", "ALSDE", "", "", "", "not_found", "use EDFacts proficiency or CCD-era files"),
    # Maryland
    ("MD", "graduates; college_enroll", "MLDS Center (MHEC + NSC)", "mlds_hs_to_college", "classes 2008-2024", "page scrape",
     "scripted", "school names only (no codes); immediate = full-time degree-seeking fall; within one year = any enrollment"),
    ("MD", "grad_rate; act_sat", "MSDE Report Card", "", "", "", "blocked",
     "download service rejects scripted requests; not needed for the outcome"),
    # Texas
    ("TX", "graduates; grad_rate", "TEA", "tea_grad", "2016-2024", "page scrape", "partial",
     "class 2015 link is dead (404); class 2014 page has no campus file"),
    ("TX", "act_sat", "TEA", "tea_sat_act", "2011-2024", "page scrape", "dropped", "not a control; no longer downloaded"),
    ("TX", "graduates; college_enroll", "THECB", "thecb_hs_enrolled", "classes 2019-2024", "listed", "partial",
     "Texas public and private colleges, fall after graduation; schools >25 graduates; fall 2015-2018 not in the report center"),
    # Colorado
    ("CO", "graduates; grad_rate", "CDE", "cde_grad", "2019-2025", "page scrape (served names)", "scripted",
     "classes 2015-2018 from EDFacts ACGR; analysis deferred"),
    ("CO", "college_enroll", "CDE (CDHE-validated)", "cde_matriculation", "2019-2025", "page scrape (served names)",
     "scripted", "earlier classes only in CDHE report PDFs"),
    ("CO", "act_sat", "CDE", "", "", "", "not_found", "SAT/PSAT files on the data-files page are growth (MGP), not scores; not needed (DECISIONS 2026-11-01)"),
    # California
    ("CA", "graduates; grad_rate", "CDE", "cde_acgr", "2017-2026", "listed", "partial",
     "classes 2015-2016 use an older cohort file not yet located"),
    ("CA", "graduates; college_enroll", "CDE", "cde_cgr12", "classes 2015-2023", "listed", "scripted",
     "12-month, any college (NSC); denominator = completers incl. GED/CHSPE; class 2024 not yet posted"),
    ("CA", "act_sat", "CDE", "", "", "", "not_found", "CDE stopped SAT/ACT files; use EDFacts proficiency"),
    # Indiana
    ("IN", "graduates; college_enroll", "Indiana CHE", "che_college_going", "classes 2008-2024", "page scrape", "scripted",
     "any NSC college, year after graduation; public and private high schools; IDs only in the 2024 file"),
    ("IN", "grad_rate", "IDOE", "idoe_data_center; idoe_archive", "2014-2025", "page scrape", "scripted",
     "older years on the Data Reports Archive page"),
    ("IN", "enrollment_race; frl", "IDOE", "idoe_data_center", "enrollment 2006-2026", "page scrape", "scripted", ""),
    ("IN", "act_sat", "IDOE", "idoe_data_center; idoe_archive", "SAT 2022-2026", "page scrape", "dropped",
     "grade-11 SAT; not a control; no longer downloaded"),
    # New Hampshire
    ("NH", "graduates; grad_rate", "NH DOE iPlatform (Cohort Counts By School)", "manual/iplatform_cohort_counts",
     "2012-2025", "manual browser export", "manual", "site returns 403 to scripts; one report per year"),
    ("NH", "college_enroll", "NH DOE iExplore (Post-secondary Enrollment Rate)", "manual/iexplore_postsecondary",
     "2016-2025", "manual browser export", "manual", "rates only; dashboard year Y = class Y (checked)"),
    ("NH", "college_enroll", "NH DOE iPlatform (Completers By Status By School)", "manual/iplatform_completers_status",
     "2012-2025", "manual browser export", "manual", "secondary: reported post-graduation plans, not enrollment"),
    ("NH", "act_sat", "NH DOE", "", "", "", "not_found", "not needed (DECISIONS 2026-11-01)"),
    # Nebraska
    ("NE", "graduates; grad_rate; college_enroll; enrollment_race; frl; teachers", "NDE NEP",
     "nde_nep", "2015-16 to 2024-25", "JSON API", "scripted", ""),
    ("NE", "act_sat", "NDE NEP", "nde_nep", "2016-17 to 2024-25", "JSON API", "dropped", "ACT files not a control; no longer downloaded"),
    ("NE", "college_enroll", "CCPE college continuation", "ccpe_continuation", "2007-08 to 2024-25",
     "direct file (dashboard DOWNLOAD button)", "scripted", ""),
    # Oklahoma
    ("OK", "act_sat", "OSRHE High School Indicators", "osrhe_hs_indicators", "2018-2024", "page scrape", "dropped",
     "mean ACT; not a control; no longer downloaded"),
    ("OK", "graduates; college_enroll", "OSRHE High School Indicators", "osrhe_hs_indicators",
     "2009-2024", "page scrape", "partial", "in-state colleges only (out-of-state from class 2023); no school number; read from class 2013"),
    ("OK", "grad_rate", "OSDE", "", "", "", "not_found", ""),
    # New York
    ("NY", "graduates; grad_rate; college_enroll; enrollment_race", "NYSED", "nysed_downloads",
     "per data.nysed.gov", "page scrape", "scripted",
     "postsecondary enrollment (16 months) for classes 2021-2024, in Report Cards 2022-2025 (Access)"),
    # New Jersey
    ("NJ", "grad_rate; act_sat; college_enroll", "NJDOE School Performance Reports", "njdoe_spr",
     "2015-16 to 2024-25", "listed", "scripted", "no graduate counts here (cohort profile is %); counts are in njdoe_acgr"),
    ("NJ", "college_enroll", "NJDOE SPR Additional Data (postsecondary trends)", "njdoe_postsecondary",
     "fall: classes 2019-2024; 16-month: 2018-2023", "page scrape", "scripted",
     "rates only (NSC-matched share, published as a range); SPR database has none from 2023-24"),
    ("NJ", "graduates; grad_rate", "NJDOE SPR Additional Data (adjusted cohort graduation rates)", "njdoe_acgr",
     "cohorts 2020-2025", "page scrape", "scripted", "4-year cohort graduates (state calculation) and cohort counts by school; FAFSA graduate denominator"),
    # Connecticut
    ("CT", "college_enroll", "P20 WIN (data.ct.gov)", "ct_open_data", "per dataset", "Socrata CSV", "scripted", ""),
    ("CT", "grad_rate; act_sat", "CSDE (data.ct.gov)", "ct_open_data", "per dataset", "Socrata CSV", "scripted",
     "accountability indicators; graduate counts are on EdSight (not scripted)"),
    # Pennsylvania
    ("PA", "graduates; grad_rate", "PDE", "pde_graduation", "2012-13 to 2024-25", "page scrape", "scripted",
     "graduates file has post-graduate plans"),
    ("PA", "college_enroll", "PDE / Future Ready PA", "", "", "", "not_found", ""),
]


# Download groups: command-line name -> function returning that group's Sources.
SOURCES = {
    "LA": louisiana,
    "IL": illinois,
    "AL": alabama,
    "MD": maryland,
    "TX": texas,
    "CO": colorado,
    "CA": california,
    "IN": indiana,
    "NH": new_hampshire,
    "NE": nebraska,
    "OK": oklahoma,
    "NY": new_york,
    "NJ": new_jersey,
    "CT": connecticut,
    "PA": pennsylvania,
    "FSA": fsa_fafsa_completion,
    "CCD": ccd_school,
    "ACGR": acgr_school,
    "ASSESS": edfacts_assessments,
    "EDGE": edge_school_locations,
    "PSS": pss_private_schools,
    "FED": federal_extras,
}
