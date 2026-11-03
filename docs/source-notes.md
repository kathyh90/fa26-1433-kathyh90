# Source notes

One entry per source: where it came from, when it was downloaded, which release or version, and which filters or queries selected the files. Download times are UTC, taken from `data/raw/download_manifest.csv`, which also records each file's URL, size, SHA-256, and the server's Last-Modified header. File lists are defined in `code/sources.py`; run `python code/00_download_raw_data.py <GROUP>` to reproduce a group. Every file is checked against its type when downloaded (an HTML error page saved under a data extension counts as a failure); `--check` re-checks the files already on disk.

"Last-Modified" is the server's header, not necessarily the publisher's release date. Where a file states its own release or "data as of" date, that date takes precedence.

The Alabama, Texas, California, Indiana, Nebraska, Oklahoma, New York, Connecticut, and Pennsylvania sources were downloaded 2026-11-01 02:19 to 03:07 UTC (Indiana's archive files later that day). File lists are built in `code/sources.py` by `scraped()` (every link on the landing page(s) whose filename matches the pattern given there; each page saved as `_landing_page*.html`) or `listed()` (fixed URLs). Which measure each source supplies, its coverage, and its status are in `sources.CATALOG` / `output/tables/state_data_sources.csv`; the entries below record release, filters, and what the files contain. Mapping of publisher labels to graduating classes is to be checked file by file before cleaning.

States are listed in order of mandate adoption (`config.STUDY_STATES`), then national sources.

## College-going measures by state (content review)

One row per reviewed state; each state's section has the full definitions table and notes. Built from `code/state_files.py` (run as the review script), which writes the per-class link statistics to `output/tables/state_file_review.csv` (columns explained in the review section of `code/README.md`). "Linked" = share of the file's school rows matched to a CCD school by the state's school code; "covered" = share of the panel's public schools with grade-12 enrollment that have a row. Tip: in VS Code, Cmd+Shift+V shows this file rendered.

| State | Enrolled by                                    | Denominator                     | Source                | Classes   | Linked / covered               |
|-------|------------------------------------------------|---------------------------------|-----------------------|-----------|--------------------------------|
| LA    | Oct 31, 1st fall                               | All graduates that year         | NSC (+ BoR from 2018) | 2012-2024 | 97-100% / 98-99.7%             |
| IL    | Sep 30 next year (12 mo); Jan 31 (16 mo)       | All graduates that year         | NSC                   | 2013-2024 | 97-100% / 92-98%               |
| AL    | Fall after graduation, AL public colleges only | Public HS graduates (ALSDE)     | ACHE state data       | 2012-2024 | 96-100% / 99-100%              |
| MD    | Within one year (any); immediate = FT fall     | 12th-grade graduates            | MHEC + NSC (MLDS)     | 2008-2024 | 95-99% / 98-99.5%              |
| TX    | Fall after graduation, Texas colleges only     | All graduates (FY)              | THECB state data      | 2019-2024 | 100% / 85% (schools >25 grads) |
| CA    | Within 12 months of completion, any college    | HS completers (incl. GED/CHSPE) | NSC (CDE)             | 2015-2023 | 99.8-100% / 99%                |
| IN    | Year after graduation, any NSC college         | High school graduates           | NSC + CHE (CHEDSS)    | 2008-2024 | public: ~100% / 96-99.8%       |
| NH    | Within the year after graduation, 2-/4-yr      | Graduates (rate only)           | NH DOE iExplore       | 2016-2025 | 99-100% / 96-100%              |
| NE    | June 1-May 31 after graduation, any NSC college | On-time public graduates        | NSC + NDE (CCPE)      | 2008-2025 | 100% from 2015 / 99-100%       |
| OK    | Fall or later that academic year, OK colleges only | Public HS graduates (SDE list) | OSRHE state data      | 2013-2024 | 99-100% / 98-100%              |
| NY    | Within 16 months, any college (NSC)            | Graduates of the calendar year  | NYSED Report Card     | 2021-2024 | 100% / 98.7-99%                |
| NJ    | Fall after graduation, any NSC college; 16 mo  | Graduates Sep-Aug (rate only)   | NSC (NJDOE)           | 2019-2024 | 100% / 95-98%                  |

**Estimating graduates where a state publishes only a graduation rate (checked 2026-11-01 in Louisiana, which publishes both):** 4-year graduation rate × CCD grade-12 enrollment is a poor proxy for the graduate count. Across 2,436 Louisiana school-years (classes 2015-2024, schools with 10+ graduates and an exact rate) it averages 0.87 × actual graduates (middle 80%: 0.67-0.98) and is within 10% for only 37% of schools, because the rate's denominator is the 9th-grade cohort, which still includes students who left before grade 12, while grade-12 enrollment already excludes them. CCD grade-12 enrollment alone is closer (median 1.04 × actual graduates; middle 80%: 0.93-1.20). Rate × the published cohort count (e.g. EDFacts `cohort_num`) gives on-time graduates, which still misses 5th-year and later graduates.

## Louisiana (`LA`)

Publisher: Louisiana Department of Education (LDOE) data library. Files are saved to `data/raw/LA/<source_id>/`.

All LDOE links carry a `?sfvrsn=` version parameter, which is dropped; re-uploads are detected by SHA-256 instead. Scraped sources keep every link on the page whose filename matches the pattern shown (case-insensitive), deduplicated by filename. Each landing page is saved as `_landing_page.html` on every run as a record of what was listed.

### College enrollment and persistence (`ldoe_college_enrollment`)
- **URL:** landing page https://doe.louisiana.gov/data-and-reports/high-school-performance; files at `https://doe.louisiana.gov/docs/default-source/data-management/<file>`
- **Downloaded:** 2026-10-09 21:07 to 2026-10-10 00:39
- **Release:** report years 2011-2012 to 2023-2024 (22 files). Enrollment reports for every year; persistence files from 2015-2016. Last-Modified 2024-07-20 to 2025-11-25.
- **Filters:** hardcoded file list (`LA_FILES`). `2020-2021-college-enrollment-with-subgroups-(1).xlsx` is saved without the `-(1)`. Files before 2011-12 (posted as zips back to 1997) are excluded because they predate the study window.
- **Used for:** the main outcome. Enrollment rates above 95% are reported as ">95"; Deneault codes these as 97.5.

### ACT scores (`ldoe_act`)
- **URL:** https://doe.louisiana.gov/data-and-reports/high-school-performance
- **Downloaded:** 2026-10-10 00:09 to 00:39
- **Release:** 19 files: per-class files for 2014-2025; cumulative state/LEA/school summaries 2012-2017 through 2012-2025. Last-Modified 2024-07-20 to 2025-11-21.
- **Filters:** pattern `^(act-.*class-of-\d{4}|act-best-composite-scores-.*|\d{4}-\d{4}-state-lea-school-act-summary)\.xlsx$`
- **Caveat:** Deneault's class-of-2013 ACT file (`pre_act`) is no longer posted and is not in the Wayback Machine. The substitute is the class-of-2013 column of `2012-2017-state-lea-school-act-summary.xlsx`, which is marked "pre-data certification." Its class-of-2014 values match the per-class file for all 301 schools (checked 2026-10-09).

### Cohort graduation rates (`ldoe_grad_rates`)
- **URL:** https://doe.louisiana.gov/data-and-reports/high-school-performance
- **Downloaded:** 2026-10-10 00:09 to 00:39
- **Release:** 31 files covering cohorts 2014–2025: summary, subgroup and scholarship versions, plus cumulative 2005-2023/2024/2025 state and school-system summaries. Last-Modified 2024-07-20 to 2025-11-21. The 2022 and 2023 files were re-uploaded on 2025-11-03.
- **Filters:** pattern `^\d{4}.*(cohort-grad-rates|cohort-graduation).*\.xlsx$`
- **Caveat:** rates above 95% are reported as ">95".

### School performance scores (`ldoe_performance_scores`)
- **URL:** https://doe.louisiana.gov/data-and-reports/performance-scores
- **Downloaded:** 2026-10-10 00:09 to 00:39
- **Release:** 2013-2017 summary plus yearly files for 2014–2019 and 2021–2025 (12 files). No 2020 file is posted (COVID). Last-Modified 2024-07-20 to 2025-11-20.
- **Filters:** pattern `^\d{4}(-\d{4})?-school-performance-score(s|-summary)\.xlsx$`
- **Used for:** Deneault takes the 2014 and 2015 graduation rates from the 2015 and 2016 files.

### October 1 enrollment counts (`ldoe_oct_counts`)
- **URL:** https://doe.louisiana.gov/data-and-reports/enrollment-data
- **Downloaded:** 2026-10-10 00:09 to 00:40
- **Release:** October 2010 to October 2025 (16 files). 2010–2015 are `.xls`; 2016 onward are `.xlsx`. Last-Modified 2024-07-20 to 2026-06-24; the October 2024 file was re-uploaded on 2026-06-24.
- **Filters:** pattern `^oct-(20[1-9]\d)-multi-stats-\(total-by-site.*\.xlsx?$` (the "total by site" files only, not the other multi-stats breakdowns).
- **Used for:** grade-9 counts lagged three years (`cohort9`). These feed the sample screens, the TOPS denominator, and the new-student calculation.

### TOPS eligibility by school (`ldoe_tops`)
- **URL:** https://doe.louisiana.gov/data-and-reports/high-school-performance
- **Downloaded:** 2026-10-10 00:39 to 00:40
- **Release:** classes of 2012–2025 (14 PDFs). The class of 2023 file is named `tops-eligibles-by-school-and-parish-2023.pdf`. Last-Modified 2024-07-20 to 2025-08-12.
- **Filters:** pattern `^(class-of-\d{4}-tops-eligibility-by-school|tops-eligibles-by-school-and-parish-\d{4})\.pdf$`
- **Caveats:**
  - Published as PDF only; Deneault had Excel.
  - Each PDF has its own "data as of" date, so recipient counts for recent classes are incomplete.
  - These are TOPS eligibility and award counts, not TOPS application counts. The applications that satisfy the mandate in place of the FAFSA are not public (see `data/raw/README.md`).

### Content review (2026-11-01)

| Item                | Louisiana (`ldoe_college_enrollment`)                                                    |
|---------------------|------------------------------------------------------------------------------------------|
| Counted as enrolled | Started at any U.S. 2- or 4-year college (public or private, in or out of state)         |
| Window              | Enrollment start on or before Oct 31 of the fall after graduation (1st fall)             |
| Enrollment source   | NSC, classes 2012-2017; NSC + LA Board of Regents from class 2018                        |
| Denominator         | All high school graduates of that school year at the site (not a 4-year cohort)          |
| Class               | '2015-2016 High School Graduates' = class of 2016, fall 2016 enrollment                  |
| Breakdowns          | % 2-year, % 4-year, % in-state, as shares of enrollees (out-of-state = 100 - in-state)   |
| Other               | 2nd-fall rate (classes 2012-2013); enrollees by college (2013-2015); subgroups (2018 on) |
| Counts published    | Graduates yes; enrollees no (= graduates x rate)                                         |
| Suppression         | '<10' graduates and '~' rates; bounds such as '>99', '>=99', '<1'                        |
| School ID           | 6-character site code = last segment of CCD ST_SCHID                                     |
| Classes             | 2012-2024                                                                                |

**College enrollment (`ldoe_college_enrollment`), the outcome and the graduate count**
- **Files read:** `<year>-college-enrollment-report.xlsx` (classes 2012-2017) and `<year>-college-enrollment-with-subgroups.xlsx` (classes 2018-2024), sheet with school ("site") rows. The 2016-17 subgroup file, by-college sheets, and persistence files are not part of the main measure.
- **Class:** the file label "2015-2016 High School Graduates" is the **class of 2016**; enrollment is measured in fall 2016.
- **Numerator:** graduates with a college enrollment beginning on or before **October 31 of the fall after graduation** ("1st fall"). Every file states this criterion (e.g. "Enrollment Beginning Date <= 10/31/2016").
- **Source of enrollment:** National Student Clearinghouse (NSC: "more than 3,600 colleges and universities, enrolling 98% of all students in public and private U.S. institutions") for classes 2012-2017; **NSC and the Louisiana Board of Regents** from class 2018 on. The statewide rate shows no jump at the change (school-weighted: 57.8% class 2017, 57.4% class 2018).
- **Denominator:** "Total High School Graduates" of that school year at the site, from LDOE's student information system End-of-Year records with GraduateFlg = Y; from class 2019 also graduates with an official graduation date in the Student Transcript System; from class 2022 the system is called EdLink 360. It counts **all graduates that year**, not a 4-year cohort, so 5th-year graduates are included. Louisiana's school graduation-rate files (`ldoe_grad_rates`) give **rates only, no counts**, so this column is the only school-level graduate count.
- **Columns:** total graduates; % of graduates enrolled 1st fall; and, **of those enrolled**, % at 2-year colleges, % at 4-year colleges, % in state (out of state = 100 − in state; 2-year + 4-year = 100). **Enrollee counts are not published**; enrollees = graduates × rate (rates are rounded to whole percents in classes 2012-2016, one decimal later). Classes 2012-2013 also give enrollment by the 2nd fall. Classes 2013-2015 have a sheet of enrollees by high school by college (with 2- or 4-year). Subgroup sheets (sex, race, disability, English learner) from class 2018.
- **Suppression and censoring:** schools with fewer than 10 graduates show "<10" and "~" for every rate (14-29 schools a year). Shares near the ends are bounds written several ways (">99", "≥99", ">=99", ">= 99", "<1", "≤1"); almost all are the in-state share. The main rate is a bound for at most 9 schools a year (classes 2020-2023). Class 2012 rates are fractions (0.56), later ones percents.
- **School IDs:** the 6-character LDOE site code, e.g. `001005` (district 001, school 005); many charters have letters (`WBB001` Benjamin Franklin, `3A1001`). It equals the last segment of CCD `ST_SCHID` (`LA-001-001005`; CCD wrote `001005` in 2014-15 and `001-001005` in 2015-16). Matching by code in the same CCD year links 94-99% of rows; adding a match by the same code in any CCD year (New Orleans charters whose CCD code changes when they move between districts) links **97-100%**. Classes 2012-2014 predate the CCD panel (from 2015), so they link only by the any-year code.
- **Coverage of the panel:** 98-99.7% of the panel's Louisiana public schools with grade-12 enrollment have a row (e.g. class 2019: 317 of 319). The sum of school graduates is close to the statewide row (class 2024: 43,580 vs. 43,439).
- **Statewide trend (school-weighted rate):** 55.8% (2012), 57.8-59.3% (2013-2019), 53.6-53.9% (2020-2022, COVID), 56.0-56.5% (2023-2024).

**Comparison with Deneault (2023) code** (`cleaningenroll_aejep.do`, `cleaninggrad_aejep.do`, `cleaningccd_aejep.do`, `mergedata_aejep.do`; checked 2026-11-01)

| Item | Deneault | This project (review reader) |
|---|---|---|
| Files and classes | Same LDOE college enrollment files, classes 2013-2019 (label "2018-2019" = 2019); class 2013 dropped in the merge (pre-period 2014-2017) | Same files, same class mapping, classes 2012-2024 |
| Columns | `hs_grad`, `per_enroll`, `per_enroll_2`, `per_enroll_4`, `per_enroll_instate` (+ persistence and subgroup rates) | Same five columns |
| Enrollee count | `enroll = per_enroll × hs_grad` | Same (graduates × rate) |
| Suppressed | `<10` and `~` set to missing; school-years missing `per_enroll` or `hs_grad` dropped (99 obs.) | Same codes read as missing |
| Bounds | `>99` and `≥99` → 99.5; `<1` and `≤1` → 0.5; `=99` → 99; `≥99%` → 100 (in her code only, not her README) | Stored as the bound with its direction (`*_bound`); for `penroll`, coded at the midpoint of the bounded range, which reproduces her values (99.5, 0.5, 97.5, 2.5) and also covers the later forms `>=99`, `>= 99` (classes 2021 on) |
| Duplicates | Keeps the row with the most graduates per site and year | 12 duplicate rows, all exact repeats (class 2012: 5 schools listed twice; class 2015: Capitol High School twice), so either rule gives the same result |
| School link | LDOE site code to CCD's `ST_SCHID` last segment, taking the most recent year's code (2019, then earlier) | Same code, same year first, then any year (most recent) |
| Manual fix | Grambling State Univ. Laboratory High School: CCD code `323002` recoded to `031002` for 2014-2016 (also in the ACT file) | Same correction as an alias, `031002` → `323002` (`state_files.LA_ALIASES`); classes 2013-2016 now link |
| FAFSA denominator | `rate_comp = comp_jun / hs_grad`, capped at 1: **LDOE graduates, not CCD seniors** | CCD grade-12 enrollment (baseline by decision 2026-11-01); LDOE graduates would be the replication's denominator |
| College outcome | **`penroll = per_enroll × per_grad`** (fall enrollment rate × 4-year cohort graduation rate, roughly enrollees per cohort member); `per_enroll` is a secondary outcome | Both, in `state_outcomes.parquet`: `pct_enrolled` (the outcome in every state) and `penroll` (Louisiana replication), classes 2014-2024 |
| Graduation rate | Classes 2014-2015 from the next year's School Performance Score files, 2016-2019 from the school graduation summaries; `>95` → 97.5, `<5` → 2.5; divided by 100. She also recodes a few charter codes in the 2015 and 2017 files to match her enrollment file | Same files (`state_files.la_grad_rates`), classes 2014-2025; charter code changes handled by linking each file to CCD separately and merging on `school_id` |
| ACT | Seniors' best composite by site, classes 2013-2019; `~` missing; `pre_act` from class 2013 | Same files |

**ACT (`ldoe_act`)**: per-class files give each school's **seniors' best composite** (student count and average composite), "Includes all <year> Seniors' Best ACT score"; file `act-scores---class-of-2024.xlsx` = seniors of 2023-24 = class of 2024. Keyed by the same site code.

**Graduation rates (`ldoe_grad_rates`)**: 4-year cohort graduation rate by school (and credential rates), rates only, keyed by site code; ">95"-style bounds and "~"/"NR" codes as above.

## Illinois (`IL`)

### ISBE Report Card public data sets (`isbe_report_card`)
- **URL:** landing page https://www.isbe.net/Pages/Illinois-State-Report-Card-Data.aspx. 2015–2017 files are at `https://www.isbe.net/Documents/<file>`. Layouts and the 2018+ workbooks use `https://www.isbe.net/_layouts/Download.aspx?SourceUrl=/Documents/<file>`.
- **Downloaded:** 2026-10-09 21:07 to 2026-10-10 00:10
- **Release:** report card years 2015–2025 (29 files):
  - 2015–2017: semicolon-delimited text in zips (`rc15.zip`, `rc16.zip`, `rc17.zip`), plus separate assessment zips, layout workbooks and definition/glossary PDFs.
  - 2018–2025: one Excel workbook per year, plus a glossary PDF.
  - 2026: glossary only. The 2026 data set was not posted as of 2026-10-09.
  - Last-Modified for the 2015–2017 files is 2017-10-31.
- **Filters:** hardcoded list (`IL_FILES`). 2015–2017 need both the base zip and the assessment zip, since only the assessment zip has ACT results. The 2018 workbook is saved as `2018-Report-Card-Public-Data-Set.xlsx` because the publisher's name has no year. The 2023 and 2024 files are saved with a four-digit year.
- **Caveats:**
  - Illinois moved from the ACT to the SAT (taken in grade 11) starting in spring 2017. From 2018 the workbook has an SAT sheet.
  - The year label is ISBE's report card year. Its mapping to graduating class must be checked in the glossary before building the panel.
  - Requests are sent with an honest project User-Agent (`sources.HEADERS`); ISBE accepts plain requests as of 2026-11-01.

### Content review (2026-11-01)

| Item                | Illinois (`isbe_report_card`)                                                                                |
|---------------------|--------------------------------------------------------------------------------------------------------------|
| Counted as enrolled | First enrollment at any U.S. college in NSC after the graduation date (dual enrollment excluded)             |
| Window              | 12 months: first enrollment on or before Sep 30 of the following year; 16 months: by Jan 31, two years after |
| Enrollment source   | National Student Clearinghouse; graduates from ISBE's Student Information System                             |
| Denominator         | All students who graduated with a regular diploma that school year (not a 4-year cohort)                     |
| Class               | Report card year Y = class of Y-2 (e.g. 2024 report card = 2021-22 graduates = class of 2022)                |
| Breakdowns          | Report cards 2019 on: public, private, 4-year, 2-year, trade/vocational, as shares of all graduates          |
| Other               | # graduates enrolled in community college (classes 2017-2021); community college remediation                 |
| Counts published    | Rates only; no graduate or enrollee counts for this measure                                                  |
| Suppression         | Small schools left blank (classes 2013-2022) or '*' (class 2023)                                             |
| School ID           | 15-digit RCDTS; CCD ST_SCHID drops the 2-digit type code through 2022-23, full RCDTS after                   |
| Classes             | 2013-2024 (report cards 2015-2026)                                                                           |

- **2026 report card:** posted by ISBE by 2026-11-01 (`2026-RC-Public-Data-Set.xlsx`, added to `sources.IL_FILES`); it adds class 2024 (lag test at two years: +0.29). Class 2024 is the newest class with Illinois college enrollment data.
- **Files read:** report cards 2015-2017 (`rc15.zip`, `rc16.zip`, `rc17.zip`; semicolon-delimited, no header; column names from the layout workbooks `RC15-layout.xlsx` ..., one layout row per field) and 2018-2025 (`General` sheet of each public data set). School rows only (`Type` = School; 2025 has no `Type` column, so district rows are those with no school name).
- **Columns by year:** `% Graduates enrolled in ... within 12 months` and `... within 16 months` in every year; from the 2019 report card (class 2017) also the 12- and 16-month rates by public institution, private institution, four-year, two-year, and trade/vocational school; `# Graduates enrolled in Community College` in report cards 2019-2023 (classes 2017-2021). The breakdowns are **shares of all graduates**: 4-year + 2-year + trade = the total and public + private = the total (median difference 0.0 points; 86% and 93% of school rows within 0.3 points). Trade/vocational is 0 nearly everywhere.
- **Definition (ISBE, *Public Business Rules: 2026 Report Card Metrics*, pp. 84-86):** graduates of the school year two years before the report card year; "All students graduating during the school year ... are considered enrolled within 12 months if the enrollment month is on or before September 30th of the following year" (16 months: on or before January 31, two years after); 2-year, 4-year and less-than-2-year (trade/vocational) and public/private come from NSC's institution codes; enrollments that began before graduation (dual enrollment), lasted under 30 days, or have status leave/withdrawn/deceased are excluded; formula = enrolled ÷ "Total students who graduate from high school" × 100.
- **Class mapping (checked against the data):** the glossaries disagree: 2015 report card "SY 2012-13" graduates, 2016 and 2017 both "SY 2013-14", 2018-2021 "three years prior", 2022 on "two years prior" (the 2022 glossary notes it "updated the definition ... to indicate 'two years prior'"). Taken literally this would repeat class 2014 and skip class 2019. In the data, no two consecutive report cards repeat a class (at most 2% of schools have identical rates), and school-level changes in the 12-month rate between consecutive report cards correlate with changes in FAFSA completion (`analysis_panel.parquet`) only at a two-year lag: +0.23 to +0.47 for report cards 2018-2025 at lag 2, versus -0.03 to -0.20 at lag 3 and -0.23 to 0.00 at lag 1. So **report card Y = class of Y-2 in every year**, as the current business rules state; the "three years prior" wording is an error in the 2018-2021 glossaries.
- **Level shift at class 2016 (2018 report card):** the mean school 12-month rate jumps from 65.2 (class 2015) to 72.2 (class 2016), and the share of schools whose 12- and 16-month rates are equal rises from 12-14% to 38-49%. This looks like a change in how the windows were computed, not in enrollment. It precedes Illinois's first covered class (2021) but falls in the early pre-period.
- **Mean school 12-month rate by class:** 65.5 (2013), 64.6, 65.2, 72.2 (2016), 68.2, 64.2, 62.4, 57.6 (2020), 57.9, 59.3, 61.1 (2023); the 16-month rate is 0.5-4 points higher.
- **School IDs:** RCDTS = region (2), county (3), district (4), type (2), school (4). CCD's `ST_SCHID` last segment is the RCDTS **without the type digits** (13 digits) for 2014-15 to 2022-23 and the full 15-digit RCDTS from 2023-24; the 2025 report card writes RCDTS with dashes. `state_files.il_code` puts both into the 13-digit form. Linked: 97-100% of school rows (classes 2015-2023 same year: 88-96%, the rest by the same code in another CCD year).
- **Coverage of the panel:** 92-98% of the panel's Illinois public schools with grade-12 enrollment have a row (class 2019: 675 of 702). The 27 without a row in class 2019 are small (median 47 seniors vs. 108 overall): alternative and cooperative programs, small charters, night schools, and campuses that later merged (Rich East and Rich South).
- **Impossible value:** Brussels High School, class 2017 (2019 report card), is published at 111.8% for both the 12- and 16-month rates; `07_build_state_outcomes.py` sets rates above 100 to missing.
- **Graduate counts:** none for this measure. The report cards give the 4-year cohort graduation rate by school in every year and `High School 4-Year Cohort Graduates - Total` from the 2024 report card. That cohort is the **report card's own year** (the 2018 report card's 4-year rate matches EDFacts class 2018 at correlation 0.96, vs. 0.75 for class 2017), so the counts cover classes 2024-2026, overlapping the enrollment data only in class 2024. No earlier report card (2015-2023, incl. the `rc15`-`rc17` layouts) has a graduate count (checked 2026-11-02), and EDFacts suppressed Illinois's school-level ACGR for classes 2019-2021, so no source gives Illinois counts for its window (2017-2022). They are on-time cohort graduates, not all graduates (the enrollment denominator also counts 5th-year and other graduates), so rate × cohort graduates would undercount enrollees slightly.

## Alabama (`AL`)

### ALSDE cohort graduation rates (`alsde_cohort_grad`)
- **URL:** https://cohort.alsde.edu/CohortSnapshotsGradRate (ASP.NET form; no file links)
- **Release:** 4-year cohorts, classes 2012-2025 (14 XLS exports, 11 MB). No Last-Modified header (generated on request).
- **Filters:** for each base year in the page's base-year list, the form is posted with cohort type 4 and the "Export to XLS" button. Saved as `cohort4yr_class<grad year>.xls`.
- **Caveat:** many school graduate counts are "~" (suppressed); the rate (two decimals) and Total Students are given. School codes are ALSDE system-school codes.

### ACHE college-going rate (`ache_college_going`)
- **URL:** https://archive.ache.edu/RESEARCH/College-Going-Rate.pdf (Last-Modified 2026-07-31)
- **Release:** newest class only (2024-25 graduates, NSC data); the URL is overwritten each year. Earlier years are no longer on ache.edu.

### Content review (2026-11-01)

| Item                 | Alabama                                                                                            |
|----------------------|----------------------------------------------------------------------------------------------------|
| College-going source | ACHE 'Summary of <year> Alabama Public High School Graduates' (PDF, NSC data)                      |
| Counted as enrolled  | Enrolled at a 2- or 4-year college, Alabama public/private or out of state, per NSC                |
| Window               | Summer term after graduation through the following spring (class 2025: SU2025-SP2026)              |
| Denominator          | Public high school graduates of that school year ('HS Grads')                                      |
| Breakdowns           | Counts by 2-year/4-year x AL public, AL private, out of state; % 2-yr, % 4-yr, % AL (of graduates) |
| Counts published     | Yes: enrolled, not enrolled, and graduates by school                                               |
| Classes on hand      | 2025 only (the URL is overwritten each year); earlier classes not yet located                      |
| Graduation source    | ALSDE cohort app: adjusted cohort, federal/ALSDE graduates and rates, classes 2019-2025            |
| School ID            | System (3) + school (4) code; CCD ST_SCHID last two segments                                       |

**Graduation (`alsde_cohort_grad`)**
- **Files:** `cohort4yr_class<Y>.xls`, one ALSDE export per graduating class. **Classes 2012-2018 are empty**: each file has only the header row (10,752 bytes), although the download succeeded and passed the content check (a valid .xls). Classes 2019-2025 have data (5,700-6,400 rows: state, system, and school rows by subgroup).
- **Columns:** base year (9th-grade entry), grad year (= class), system and school code and name, subgroup, Federal Grad Rate, ALSDE Grad Rate (two decimals), Total Students (the adjusted 4-year cohort), Federal Graduates, Federal Completers, ALSDE Graduates, ALSDE Completers. The review keeps the "All students" rows of schools (school code not `0000`).
- **Suppression:** federal graduate counts are `~` for 1,708 of 2,705 school-years (60-70% a year; median cohort 71 vs. 196 where shown). Rates and cohorts are published for nearly all schools (cohort missing for 78 rows, rate for none). **Cohort × federal rate / 100, rounded, reproduces every published federal graduate count (997 of 997)**, so on-time cohort graduates can be computed for 1,630 suppressed rows. They are on-time 4-year cohort graduates, not all graduates.
- **School IDs:** the 4-digit school code repeats across systems (about 1,500 CCD schools share about 300 codes), so the key is `system-school` (e.g. `101-0010`), the last two segments of CCD's `ST_SCHID` (`AL-101-0010`; CCD 2014-15 gives only the school code). `state_files.al_ccd_key`. Linked: 99% of school rows; **every** panel school with grade-12 enrollment has a row in classes 2019-2025.
- **Coverage vs. policy timing:** Alabama's first covered class is 2022; dose classes 2019-2020; reference class 2021. The graduation files cover all of these. Classes 2015-2018 are in EDFacts (Urban) if needed.

**College-going, in-state public (`ache_hs_reports`)**
- **Source:** ACHE High School Graduate Reports, https://data.ache.edu/Rpt_HighSchool (ASP.NET form; scripted in `sources.alabama()`: one "Basic High School" Excel export per fall term, posted with the term value, e.g. `20241` = FA23). Terms go back to 2003; classes 2012-2024 are downloaded (`ache_hs_basic_fall<Y>.xls`).
- **Definition (report title):** "<Y-1>-<Y> Alabama Public High School Graduates (as reported by the Alabama State Department of Education) Enrolled in Alabama Public Colleges and Universities, Fall <Y>". So: **Alabama public 2- and 4-year institutions only** (no private, no out-of-state), enrolled in the fall term after graduation; the denominator is the school's graduates that year as reported by ALSDE. Class = Y.
- **Columns:** HS code (7 digits = system 3 + school 4, the same key as CCD; e.g. 0340020 = `034-0020` Abbeville HS), high school graduates, enrolled in multiple Alabama public colleges, enrolled in Alabama public colleges, remedial math / English / both / total, full-time, part-time; two rows per school (enrolled in 2-year colleges, enrolled in 4-year colleges). Statewide, enrolled 2-year + 4-year = total (class 2023: 9,501 + 11,566 = 21,067 of 48,611 graduates). Counts are published (no rates); some very small or special schools are removed "per ALSDE data size reporting guidelines" (listed in each file's note).
- **Statewide in-state public rate by class:** 52.3 (2012), 51.0, 51.1, 49.7, 48.0, 48.8, 46.8, 45.6 (2019), 41.6 (2020), 42.1, 42.6, 43.3 (2023), 41.6 (2024). For comparison, PARCA reports an all-college (NSC) rate of 58% for class 2019, so in-state public enrollment is roughly four-fifths of all enrollment.
- **Linked:** 96-100% of school rows (classes 2015-2024: 99-100%); 99-100% of panel schools with grade-12 enrollment have a row.
- **Graduate counts:** the reports give all graduates by school for classes 2012-2024 (from ALSDE), so Alabama has a graduate count for the secondary denominator.
- **School coverage vs. the all-college (NSC) report (checked 2026-11-01):** ACHE's in-state report lists 376 schools for class 2024; ACHE's NSC college-going PDF, the source of PARCA's dashboard, lists about 366 for class 2025. Matching names, almost every difference is a naming variant of the same school ("Ardmore Junior/Senior High School" vs. "Ardmore High School"). The few real differences are schools that opened or closed between the two classes, or small special schools ACHE removes under ALSDE reporting rules (e.g. Continuous Learning Center). So the in-state data does not cover fewer high schools; the difference is in which colleges count, not which schools.

**Limitations of Alabama's outcome (ACHE in-state public fall enrollment), recorded 2026-11-01**
1. **Only Alabama public colleges.** Graduates who enroll at an Alabama private college (e.g. Samford, Tuskegee, Spring Hill) or at any out-of-state college count as not enrolled. In-state public enrollment is roughly four-fifths of all enrollment (class 2019: 45.6% in-state public vs. 58% at any college, per PARCA's NSC-based figure).
2. **Substitution can bias the effect.** If the mandate (through more aid information or offers) moves students from Alabama public colleges to private or out-of-state colleges, the measured effect understates the true effect, and can even turn negative. If it mainly draws in students who would not have enrolled, who tend to enroll at in-state public 2-year colleges, the measure captures most of the effect. The direction of the bias is not known.
3. **The excluded share varies by school.** Schools near the state borders or in high-income areas send more graduates out of state or to private colleges. School fixed effects absorb stable differences, but not changes in those shares over time, and high- and low-dose schools may differ in them.
4. **Not comparable across states.** Louisiana and Illinois count any U.S. college in the National Student Clearinghouse; Alabama's outcome is narrower, so its estimate is on a different outcome and its level is lower. Estimates should be compared across states with this in mind, or the pooled analysis should allow a state-specific outcome definition.
5. **Fall term only.** Graduates who first enroll in spring or summer are missed (ACHE also reports spring and summer terms, not used). Louisiana also uses the fall (by Oct 31); Illinois uses 12 months.
6. **Different data system.** Enrollment comes from Alabama's public higher-education records matched by ACHE to ALSDE's graduate list, not from NSC; the matching method is not documented in the report.
7. **Small schools removed.** Some very small or special schools are dropped "per ALSDE data size reporting guidelines" (listed in each file's note); 37 school rows do not link to CCD.
8. **Reports are generated on request.** The files have no fixed release; a later download could differ (the manifest's hash check would flag it).
9. **Downward trend.** The statewide in-state public rate falls from 52% (class 2012) to 42% (class 2024), with a COVID drop in class 2020. Part of the decline could be students shifting to out-of-state or private colleges, which this measure cannot show. Class fixed effects absorb statewide shifts.
10. **Robustness check not available yet.** PARCA's all-college (NSC) rates by school are in a Tableau dashboard with data downloads disabled; class 2023 was never published. Options: ask PARCA or ACHE for the school-level files.

**College-going, all colleges (PARCA / ACHE NSC)**
- **PARCA dashboard** (https://public.tableau.com/app/profile/parca/viz/CollegeGoingComparisonsForAlabamaHighSchoolsClassof2024/AlabamaCollege-GoingRateComparisons): school-level NSC college-going rates from ACHE data, all colleges; class 2023 not published. Tableau Public answers scripted requests with an AWS WAF challenge (checked 2026-11-01), so it is not scripted; an export would be a manual browser step.

**College-going, all colleges, newest class (`ache_college_going`)**
- **What we have:** `College-Going-Rate_latest.pdf` = "Summary of 2024-2025 Alabama Public High School Graduates, Based on Enrollment Data from National Student Clearinghouse (SU2025 - SP2026)": 10 pages, by county and high school: enrolled at 2-year and 4-year colleges (Alabama public, Alabama private, out of state), total enrolled, not enrolled, HS graduates, % 2-year, % 4-year, % in Alabama. One class only (2025, a post-period class). The PDF's text layer splits many numbers into single digits (e.g. `8 81341`), so it needs table extraction by position, not plain text.
- **Earlier classes, not yet obtained:** ACHE's year-named copies (e.g. `https://www.ache.edu/wp-content/Research/College-Going-Rate-2023-2024.pdf`, found by web search) return 404 after a site change (checked 2026-11-01); an ALSDE copy titled "2017-2018 National Student Clearinghouse College Going Rate Report" (https://www.alabamaachieves.org/wp-content/uploads/2021/06/2017-2018-National-Student-Clearinghouse-College-Going-Rate-Report.pdf) reportedly holds 2015-16 graduates; PARCA's dashboard (https://parcalabama.org/college-going-rates-by-high-school/) shows school rates by class from ACHE data, and PARCA notes that class 2023 was not published. The Internet Archive's index was temporarily offline when checked.

## Maryland (`MD`)

Scripted 2026-11-01 (`sources.maryland()`): the MLDS Center's data download, a zip linked from https://mldscenter.maryland.gov/Dashboards.html (`HighSchoolToCollegeDashboard2025DataDownload.zip`: workbook "MD PublicHS Grads- College and Workforce Outcomes 2025.xlsx" and "High School to College Dashboard Notes for Click to Download 2025.pdf"). The dashboard's own "Click here" link points to `DataDownloads.html`, which now returns 404; the Dashboards page links the zip. The MSDE Report Card (reportcard.msde.maryland.gov) still rejects scripted requests and is not used.

### Content review (2026-11-01)

| Item              | Maryland (`mlds_hs_to_college`)                                                                                                                 |
|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------------|
| Source            | MLDS Center data download for the dashboard 'Maryland Public High School Graduates: College and Workforce Outcomes' (zip, published 2025-12-08) |
| Measures          | Immediate; Within One Year; Within Two Years; Complete; Non-Traditional (not mutually exclusive)                                                |
| Immediate         | Enrolled full-time in a degree-seeking program in the fall immediately after high school                                                        |
| Within One Year   | Enrolled full- or part-time, degree- or non-degree-seeking, within one year of graduation                                                       |
| Enrollment source | MHEC for Maryland public, community, and state-aided private colleges; NSC for out-of-state and other private colleges                          |
| Denominator       | 12th-grade graduates of the school (duplicate graduation records removed; certificates of completion omitted)                                   |
| Class             | Cohort year '2023-24' = class of 2024                                                                                                           |
| Counts published  | Yes: graduates and enrollees, plus the % (enrolled / graduates)                                                                                 |
| Breakdowns        | Subgroups (gender, race, FARMS, high school program); degree by 25 and wages for older cohorts                                                  |
| Suppression       | '*' under 10 or complementary (some rounding or perturbing); '◊' no graduates that year; '^' too soon                                           |
| School ID         | None: school system + school name, matched to CCD by name                                                                                       |
| Classes           | 2008-2024 (within two years: through 2023)                                                                                                      |

- **Definitions (data notes PDF):** "Immediate college enrollment is limited to high school graduates who enroll in college full-time in a degree-seeking program in the fall immediately following high school"; "Within One Year College Enrollment includes high school graduates who enroll in college either full-time or part-time as degree-seeking or non-degree seeking students within one year of high school graduation"; Within Two Years likewise (reported once two years have passed); Complete = any time after graduation (reported after three years); Non-Traditional = delayed degree-seeking enrollment until age 20 or first enrolled part-time. A graduate is counted in every category whose definition they meet.
- **Sources (notes):** Maryland community colleges, four-year public institutions, and state-aided independent institutions from MHEC; out-of-state colleges and in-state private colleges from NSC (participation optional, students can opt out). From 2008-09 to 2012-13 MHEC collected only fall-term enrollment, so some enrollees in those years may be missed (affects the within-one-year and later measures for classes 2009-2013).
- **Workbook:** sheet `2025CollegeEnrollment`, one row per enrollment type × subgroup × school system/school × cohort year (351,393 rows); columns: graduates, enrollment, % of graduates enrolled, degree by 25, wages at 25, living wage. The review keeps `Grouping Level` = All Students and `Sub-group` = School (system and statewide rows dropped).
- **Statewide (school sums):** within one year 67.1% (class 2008) to 70.1% (2014), 68.4% (2017-2019), 63.9% (2020), 64.0-65.2% (2021-2024); immediate 47.0-54.5% with dips in classes 2013 (47.0) and 2015 (46.3); within two years 71-74% to class 2019, 67.6-68.6% after. The published % agrees with enrolled ÷ graduates within 0.5 points.
- **Suppression:** about 225-236 school rows a year (rows marked `◊`, no graduates that year, are dropped). Within one year is suppressed (`*`) for 14-31 schools a year (class 2024: 17 of 226), immediate for slightly more (class 2024: 22); suppressed schools are kept with their graduates and a missing enrollment. School graduates sum to the statewide row (class 2024: 61,097 vs. 61,118).
- **Class 2023-24 is included** in this edition (workbook dated 2025-12-08): within one year 38,940 of 61,118 graduates (64%), immediate 30,282 (50%); within two years, complete, and non-traditional are `^` (too soon to report) for that class. An earlier edition ended at 2022-23.
- **School IDs and linking:** no codes; the key is school system + the distinctive words of the school name (`state_files.md_school_key`; generic words such as HIGH dropped). On the CCD side only schools whose highest grade is 12 are keyed, since "Annapolis High" and "Annapolis Middle" share a key otherwise; a key shared by two CCD schools in a year is left unmatched. Five name differences are fixed by hand (`state_files.MD_ALIASES`: Harbor City / Achievement Academy @ Harbor City; Center for Career & Technology vs. Technical Education; Masonville Cove / Benjamin Franklin HS at Masonville Cove; SEED School, listed under Baltimore City in MLDS but its own district in CCD; NACA vs. N.A.C.A.). Linked: 95-99% of school rows (classes 2015-2024: 97.5-99%). Covered: 98-99.5% of panel schools with grade-12 enrollment (class 2019: 220 of 221); the few without a row are small evening, alternative, or special-education programs.
- **Coverage vs. policy timing:** Maryland's first covered class is 2022 (dose classes 2019-2020, reference 2021); the data cover classes 2008-2024.

## Texas (`TX`)

### TEA graduation (`tea_grad`) and SAT/ACT (`tea_sat_act`); THECB college enrollment (`thecb_hs_enrolled`)
- **URL:** TEA class pages `.../completion-graduation-and-dropout/four-year-graduation-and-dropout-data-class-<Y>` (Y = 2014-2024) and `.../satact/sat-and-act-data-search-and-data-downloads` plus `.../satact/sat-and-act-data-class-<Y>` (2018-2024); THECB `https://reportcenter.highered.texas.gov/reports/data/high-school-graduates-enrolled-in-higher-education-by-campus-fall-<Y>-xls/` (the URL is the workbook).
- **Release:** campus four-year graduation files for classes 2016-2024 (saved as `campus_4yr_class<Y>.xlsx`; publisher names vary); SAT, ACT, and combined campus files for classes 2011-2024 (48 files); THECB campus files for fall 2019-2024.
- **Gaps:** the class-of-2015 campus link returns 404 and the class-of-2014 page has no campus file; THECB campus files before fall 2019 are not in the report center. THECB covers Texas institutions only.

### Content review (2026-11-01)

| Item                | Texas (`thecb_hs_enrolled`)                                                                                           |
|---------------------|-----------------------------------------------------------------------------------------------------------------------|
| Source              | THECB 'High School Graduates Enrolled in Higher Education by Campus', fall 2019-2024 (one workbook per fall)          |
| Counted as enrolled | Enrolled in a Texas public or independent (private) college or university in the fall term after graduation           |
| Not counted         | Out-of-state colleges; 'Not found' (standard ID, no Texas enrollment that fall); 'Not trackable' (non-standard ID)    |
| Denominator         | 'Total high school graduates' of the fiscal year (all graduates, not a cohort)                                        |
| Class               | 'Graduates From FY 2021 ... Fall 2021' = class of 2021                                                                |
| Counts              | Yes: graduates, enrollees by institution, not found, not trackable (enrolled + not found + not trackable = graduates) |
| Breakdowns          | By institution; small institutions pooled as 'Other Public/Independent 2-yr / 4-yr'                                   |
| Coverage            | High schools with more than 25 graduates only                                                                         |
| School ID           | 9-digit TEA campus ID = last segment of CCD ST_SCHID (2024 file drops leading zeros)                                  |
| Classes             | 2019-2024 (fall 2015-2018 not in THECB's report center)                                                               |

- **Scope is the same in every year:** the titles of the fall 2021 and fall 2024 workbooks say "Texas Public Higher Education" and their pooled rows say "Other Public ...", while the other years say "Public or Independent" and "Other Pub/Ind ...". Private institutions (Baylor, TCU, SMU, Rice, Trinity, Abilene Christian) are listed in every year with similar counts, and statewide enrollment shows no drop in 2021 or 2024, so the narrower titles are labeling only.
- **Statewide:** graduates 350,525 (class 2019) to 376,947 (2024); enrolled 48.6% of graduates (2019), 41.4% (2020, COVID), 41.4% (2021), 43.3%, 43.8%, 43.7% (2022-2024). As a share of trackable graduates: 51.4%, 45.0%, 45.1%, 47.1%, 47.8%, 47.8%.
- **Not trackable** graduates (non-standard ID numbers that cannot be matched) rise from 5.3% (2019) to 8.6% (2024) of graduates; they are counted in the denominator unless excluded. Their share varies by school.
- **Coverage of the panel:** 100% of school rows link to CCD (same year). About 85% of the panel's Texas schools with grade-12 enrollment have a row; the rest are below THECB's 25-graduate cutoff (class 2021: 273 schools, median 16 seniors, 96% with 30 or fewer), 1.3% of the panel's seniors.
- **TEA graduation files (`tea_grad`):** campus four-year cohort (`CAMP_ALLD`) and on-time graduates (`CAMP_ALLN_GRAD`) with rates, two rows per campus (`CALC_FOR_STATE_ACCT` Yes/No); counts are masked (`-`) in the class 2016 file and published by 2024. Not needed for the outcome; THECB's total graduates is the graduate count.
- **Coverage vs. policy timing:** Texas's first covered class is 2022 (dose classes 2019-2020, reference 2021). The enrollment data start at class 2019, so the outcome has only three pre-period classes (two in the dose window and one affected by COVID); earlier classes are not in THECB's report center (THECB's older reports, e.g. on the TPEIR site, are not yet located).

## Colorado (`CO`)

Downloaded 2026-11-01. The analysis of Colorado is still deferred. CDE's file links are opaque (`/fs/resource-manager/view/<id>`), so `resolved()` sends a HEAD request for each link on the pages below and selects and names files by the filename the server sends (Content-Disposition). Each page is saved as `_landing_page_<n>.html`.

### CDE graduation/completion workbooks (`cde_grad`)
- **URL:** https://ed.cde.state.co.us/cdereval/graduation-completion-statistics and its archive `.../data-insights-resources-archives`
- **Release:** state/district/school workbooks for 2018-19 to 2024-25 (7 files, classes 2019-2025). Earlier school-level workbooks are not posted online; classes 2015-2018 come from EDFacts ACGR (`edfacts_acgr_urban`, classes 2011-2020).
- **Filters:** served name matches `CO_GRAD` (school-level workbooks only; trend, school-type, summary, and still-enrolled files skipped).
- **Content (checked 2026-11-01, 2018-19 file):** sheets by district and school, for race/gender and for IPST (disability, English learner, ...) subgroups. Columns: county, organization code (CDE 4-digit district + school number), "Class Of" anticipated year of graduation, years after entering high school (4 = on time; 5-7 also given for earlier classes), final grad base, graduates total, graduation rate, completers total, completion rate.

### CDE matriculation rates (`cde_matriculation`)
- **URL:** https://ed.cde.state.co.us/accountability/data-tools/data-files and https://ed.cde.state.co.us/accountability/performance-framework-flat-files-from-prior-years
- **Release:** one workbook per graduation cohort 2019-2025 (7 files; the 2022-2024 files are dated by CDE August 2023-2025). Matriculation is CDE's accountability measure of graduates enrolling in postsecondary education, validated by CDHE.
- **Filters:** served name matches `CO_MATRIC`.
- **Content (checked 2026-11-01):** sheet `State_District_School Rates`: graduation cohort, reporting level, district and school number and name, category (ALL, 2 YEAR, 4 YEAR, CTE, MILITARY in 2025), **DN** (graduates), **NM** (matriculants), RATE. School rows cover only the file's own cohort. A summary sheet gives statewide rates back to 2014. Classes before 2019 at school level are only in CDHE's legislative report PDFs (not downloaded).
- **SAT:** the data-files page's PSAT/SAT files are growth percentiles (MGP), not scores; not downloaded (DECISIONS 2026-11-01).

## California (`CA`)

### CDE ACGR (`cde_acgr`) and 12-month college-going rate (`cde_cgr12`)
- **Note:** No SAT or ACT score after 2022 due to law.
- **URL:** `https://www3.cde.ca.gov/demo-downloads/acgr/<file>.txt` and `.../cgr/cgr12mo<YY>.txt`. CDE's www pages answer scripts with a bot check, so URLs are listed rather than scraped (names from the ACGR page as of 2026-10-31; revised files carry `-v2`/`-v3`).
- **Release:** ACGR classes 2017-2026 (Last-Modified 2019-02-27 to 2026-10-05); college-going classes 2015-2023 (2024 not posted yet, optional).
- **Gap:** ACGR for classes 2015-2016 uses an older cohort file not yet located.

### Content review (2026-11-01)

| Item                | California (`cde_cgr12`)                                                                                                                                      |
|---------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Counted as enrolled | Enrolled at any public or private, 2- or 4-year college, in or out of state, within 12 months of completing high school                                       |
| Enrollment source   | National Student Clearinghouse (student-level match); FERPA-blocked records (about 11% in CA, per NSC) count as not enrolled                                  |
| Denominator         | High school completers: regular-diploma graduates plus non-graduate completers (CHSPE, GED, adult-education diploma); special-education certificates excluded |
| Class               | AcademicYear '2018-19' = class of 2019 (completion between Aug 16 and Aug 15)                                                                                 |
| Counts              | Yes: completers, enrolled, not enrolled, and enrolled by destination                                                                                          |
| Breakdowns          | In-state / out-of-state; UC, CSU, community college, in-state private; out-of-state 4-year / 2-year; by completer type (a-g met or not) and student group     |
| Suppression         | '*' when the count is 10 or fewer                                                                                                                             |
| School ID           | 7-digit CDE school code = last segment of CCD ST_SCHID                                                                                                        |
| Classes             | 2015-2023 (class 2024 not yet posted)                                                                                                                         |

- **Definitions (CDE file structure page, https://www.cde.ca.gov/ds/ad/fscgr12.asp, read 2026-11-01):** "The total percentage of California public high school completers who enrolled in any public or private postsecondary institution (in-state or out-of-state) within 12 months of completing high school"; completers are "students who finished high school during the academic year's reporting period (8/16 of Year 1 to 8/15 of Year 2)", including graduates and non-graduate completers. Completer types: TA all, AGY graduates meeting a-g, AGN graduates not meeting a-g, NGC non-graduate completers.
- **Rows kept:** school rows (`AggregateLevel` S), all students (`ReportingCategory` TA), all completers (`CompleterType` TA). Files through class 2020 repeat each school under "All" charter and alternative-status combinations; every school also has one row with its actual status (the only row in later files), which is kept. Placeholder codes `0000000` (District Office) and `0000001` (Nonpublic, Nonsectarian Schools, one per district) are dropped. A few charter networks (Options for Youth, Opportunities for Learning) appear under more than one district with one school code; `07_build_state_outcomes.py` keeps the row with the most completers.
- **Files 2015-2017** start with a UTF-8 byte-order mark (read with `utf-8-sig`).
- **Checks:** in-state + out-of-state = enrolled for 99.8% of school rows; UC + CSU + community college + in-state private = in-state for all.
- **Statewide (school sums):** 64.6% (class 2015), 67.1, 65.3, 67.8, 65.0 (2019), 62.9 (2020), 62.4, 62.1, 65.8 (2023). Suppressed schools: 378-492 a year (small schools).
- **Linked:** 99.8-100% of school rows; covered: 99% of panel schools with grade-12 enrollment (class 2023: 2,195 of 2,212).
- **Coverage vs. policy timing:** California's first covered class is 2023 (dose classes 2020-2021, reference 2022). The college-going files end at class 2023, so the outcome has **one post-period class** until CDE posts class 2024 (the download script fetches it once it appears).

## Indiana (`IN`)

### CHE college-going (`che_college_going`), IDOE data center (`idoe_data_center`) and archive (`idoe_archive`)
- **URL:** https://www.in.gov/che/college-going-reports/, https://www.in.gov/doe/it/data-center-and-reports/, and the Data Reports Archive https://www.in.gov/doe/it/data-center-and-reports/data-reports-archive/ (both IDOE pages scraped with one filename pattern, `IN_DOE_FILES`).
- **Release:** college readiness / college-going datasets for cohorts 2008-2016 (one file) and 2017-2024; graduation-rate workbooks for classes 2014-2025 (federal and state rates from 2018; one file per year for 2014-2017; the 5-year rate is skipped); school enrollment by grade, gender, and ethnicity/FRL 2006-2026 (Data Center only; the archive's older vintages are skipped); grade-11 SAT by school for test years 2022-2026.
- **SAT (checked 2026-11-01):** the state's school-day SAT, given to all juniors each spring as Indiana's high school accountability test (from 2021-22). Each file's note says "all Graduation Cohort Y+1 SAT testers", so file `SAT-<Y>` is the **class of Y+1**: classes 2023-2027. School rows are keyed by `Corp ID` + `School ID` (IDOE 4-digit codes, not NCES). It reports counts below / approaching / at the College Board benchmark and % at benchmark for EBRW, Math, and both, with subgroup sheets; **no mean scores**; cells under 10 students are `***` (2025 on). The file name and data note differ by one year on purpose (test year vs. graduation cohort).
- **Content review (2026-11-01), college-going (`che_college_going`):**

| Item                | Indiana (`che_college_going`)                                                                                                                    |
|---------------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| Source              | CHE College Readiness / College-Going datasets: 2008-2016 in one file, then one file per cohort (2017-2024)                                      |
| Counted as enrolled | Enrolled at any college that participates in the National Student Clearinghouse ('EnrCollegeN')                                                  |
| Window              | Not stated in the data notes; CHE describes the rate as enrollment in the year after high school graduation                                      |
| Denominator         | High school graduates of that year ('HSGrads'), public and private high schools                                                                  |
| Class               | 'Cohort' = graduating class (e.g. the 2021 report / 2021 file = class 2019)                                                                      |
| Counts              | Yes: graduates, enrollees, Indiana public enrollees                                                                                              |
| Other information   | Indiana public enrollees; remediation, first-year GPA and credits (Indiana public enrollees only); breakouts by diploma type, race, income, etc. |
| Suppression         | 'NULL'/'***' (to 2022) or 'DS' (2023 on); 11-46 schools a year                                                                                   |
| School ID           | Names ('Name-City'); the 2024 file adds the IDOE school number (= CCD ST_SCHID last segment)                                                     |
| Classes             | 2008-2024                                                                                                                                        |

  - **Definitions (each file's notes):** "EnrCollegeN = number of students enrolling in any college provided that the college participates in the National Student Clearinghouse" and "EnrCollegeN/HSGradN = college going rate"; "EnrINPublicCollegeN = number of students enrolling in an Indiana public college". The notes do not state the window; CHE's reports describe the rate as enrollment in the year following graduation (secondary sources; the 2021 report's release says it covers "the graduating high school class of 2019"). Data source: CHEDSS (CHE's data system), with IDOE and NSC.
  - **Column names vary by year** (`GeoType`/`LocationType`; `HSGradN`/`HSGradsN`/`HSGrads`); the reader keeps `LocationType` = School and `Category` = Average.
  - **Linking:** names are "Name-City" in every year; only the 2024 file has the IDOE school number (`LocationId`). Each name gets the 2024 file's ID for that exact name; names without one fall back to CCD by name + city among Indiana grade-12 schools, using only keys that belong to one CCD school and one CHE name, and never an ID another name already has (the key drops generic words, so "Greenwood Christian Academy" and "Greenwood Community High School" in Greenwood share one; without these rules the private school took the public school's ID). About 80% of rows link; most unlinked rows are private, religious, or residential schools (CHE includes private high schools). Covered: 96-99.8% of panel schools with grade-12 enrollment (class 2024: 408 of 409). One class 2020 school row has no name and stays unlinked.
  - **Statewide (school sums), all high schools in the file:** 66.0% (class 2008), 63-66% through 2017, 61.2% (2018), 58.5% (2019), 53.4% (2020), 51.8-52.9% (2021-2024). **Public schools that link to CCD only:** 65.4% (2008), 61.9% (2017), 57.3% (2019), 52.1% (2020), 50.3-51.6% (2021-2024); the private schools' rate is 71-80%. Rates are per school, so private rows do not change any public school's rate; they drop out when the outcomes are merged with the public-school panel.
  - **Coverage vs. policy timing:** Indiana's first covered class is 2024 (dose classes 2021-2022, reference 2023); the newest file is the 2024 cohort, so there is one post-period class until the 2025 cohort is posted.
- **Superseded:** `idoe_data_center/2023-Indiana-Federal-Graduation-Rate.xlsx` was a hard-coded URL; it is identical (same SHA-256) to `idoe_archive/2023-indiana-federal-graduation-rate.xlsx`, which is now scripted. The old copy stays in `data/raw/` unused.

## New Hampshire (`NH`)

education.nh.gov and my.doe.nh.gov return HTTP 403 to scripted requests (2026-10-31), so the two iPlatform reports and the iExplore indicator below were **exported by hand in the user's Chrome** on 2026-11-01 (Claude in Chrome, at the user's request) and are registered in `sources.py` as manual sources (`new_hampshire()`, `manual=True`). `00_download_raw_data.py` never fetches them: it records each file in the manifest (status `manual`, SHA-256, export time) and reports any missing file with its export steps; `--check` flags a manual file whose hash changed. This is the project's one manual download step.

**To re-export a year:** open the report URL below, choose School Year *Y* (= class of *Y*), Run Report, then Export > Excel; save as `<prefix>_class<Y>.xlsx` in the folder named below. The class year in each filename was taken from the title inside the file ("2023 - 2024 ..." = class 2024), not from the menu choice.

### Content review (2026-11-01)

| Item                | New Hampshire (`manual/iexplore_postsecondary`)                                                                 |
|---------------------|-----------------------------------------------------------------------------------------------------------------|
| Counted as enrolled | Enrolled at a higher institution (2- or 4-year) after completing the high school diploma                        |
| Window              | Within the year following graduation (NH DOE glossary)                                                          |
| Denominator         | Graduates (the glossary's 'students ... completing their high school diploma'); not published as a count        |
| Class               | Dashboard year Y = class of Y (checked against reported plans and FAFSA changes)                                |
| Counts              | No: rates only (two decimals). Graduates taken from iPlatform Completers By Status; enrolled = rate x graduates |
| Breakdowns          | None in this export                                                                                             |
| Suppression         | '*N' (fewer than 11 students); 'NA'; '>90%' / '<10%' blurring (none seen in high school rows)                   |
| School ID           | 5-digit NH school number = last 5 digits of CCD ST_SCHID                                                        |
| Classes             | 2016-2025                                                                                                       |

- **Year mapping:** the dashboard does not say which class a year refers to. Two checks give the same answer, year Y = class Y: high school rates correlate 0.78 with the same class's reported college plans (Completers By Status: % entering 4-year + less-than-4-year), against 0.68-0.70 for the class before or after; and year-to-year changes in the rate correlate +0.48 with changes in FAFSA completion of the same class, -0.22 with the class before (`state_files.NH_CLASS_OF`).
- **Rows kept:** school level 'High School' (about 91-102 a year); elementary and middle schools are 'NA'. 40 cells are '*N' and 3 are blank ('%').
- **Graduate count:** total completers of the same class from Completers By Status By School (matched by school number; missing for 22 school-years). Whether NH counts non-diploma completers there is not documented in the report; enrollees (`enrolled`) are therefore an estimate.
- **Statewide (rate × completers):** 60.1-60.6% (classes 2016-2019), 57.7% (2020), 56.3-56.5% (2021-2023), **47.9% (2024)**, 52.5% (2025). Class 2024, New Hampshire's only post-period class, is also the class affected by the delayed 2024-25 FAFSA nationally; the drop needs a check against NSC national trends.
- **Linked:** 99-100% of rows; covered: 96-100% of panel high schools with grade-12 enrollment.
- **Coverage vs. policy timing:** first covered class 2024 (dose classes 2021-2022, reference 2023); outcome data 2016-2025.

### iPlatform Cohort Counts By School (`manual/iplatform_cohort_counts`)
- **URL:** https://my.doe.nh.gov/iplatform/Report/Report?path=%2FBDMQ%2FiPlatform%20Reports%2FPerformance%20Data%2FDropouts%20and%20Completers%2FCohort%20Counts%20By%20School&name=Cohort%20Counts%20By%20School&categoryName=Dropouts%20and%20Completers&categoryId=23 (report ID 30)
- **Release:** classes 2012-2025 (14 files, `cohort_counts_by_school_class<Y>.xlsx`). Class 2025 is marked "Type of Data: Preliminary".
- **Content (checked 2026-11-01):** one row per public high school: SAU #, district #, district name, school name, 4-year cohort count, graduated, graduation rate, early-exit non-graduates (earned HiSET, dropped out, total), dropout rate. Counts are exact (no suppression seen). **No school code**: rows link by district number and school name.

### iExplore Post-secondary Enrollment Rate (`manual/iexplore_postsecondary`), main college-going measure
- **URL:** https://jwt.nh.gov/?src_route=/iExplore/Explore-Dashboard&toolbar=Hidden&Width=1300px&Height=1600px (iExplore "Explore Indicators", a Tableau dashboard; found by the user). Exported 2026-11-01 in the user's Chrome: Download, then Indicator Name = Post-secondary Enrollment Rate, School / District = School, other filters (All), Year = *Y*, then Download > "*Download Explore" sheet > Excel. Each export holds year *Y* and the two years before it, so Years 2025, 2022, 2019, and 2016 give four files covering 2016-2025 (2016 is the first year offered). Saved as `postsecondary_enrollment_rate_<first>-<last>.xlsx`, named from the year columns in the file's header.
- **Definition (NH DOE Glossary of Terms, read 2026-11-01):** "Percent of Students enrolling in a Higher Institution (2 or 4 years) after immediately completing their high school diploma. College enrollment must be within the year following graduation." The data source (e.g. National Student Clearinghouse) is not stated.
- **Content (checked 2026-11-01):** crosstab with indicator, level (Elementary/Middle/High School), school type, region, **Entity ID** (NH school number, e.g. Bedford High School 28555), entity name, and one column per year holding the rate (e.g. Bedford High School 75.15% in 2025, 68.54% in 2024, 81.46% in 2023). Merged cells are blank and must be filled down; a school's years can appear on separate rows. **Rates only, no counts.** Exception codes: `NA` not available, `N/A` not applicable, `*N` suppressed (fewer than 11 students), `>90%` / `<10%` blurred for privacy, `*COVID` unavailable because of COVID.
- **To verify in the content review:** whether dashboard year *Y* is the class of *Y* or of *Y*−1 (the glossary does not say).
- **Not the user's file:** `~/Downloads/_Download Explore.xlsx` (2026-10-27, high schools only) is the user's own earlier download and was left in place.

### iPlatform Completers By Status By School (`manual/iplatform_completers_status`)
- **URL:** https://my.doe.nh.gov/iplatform/Report/Report?path=%2FBDMQ%2FiPlatform%20Reports%2FPerformance%20Data%2FDropouts%20and%20Completers%2FCompleters%20By%20Status%20By%20School&name=Completers%20By%20Status%20By%20School&categoryName=Dropouts%20and%20Completers&categoryId=23 (report ID 33)
- **Release:** classes 2012-2025 (14 files, `completers_by_status_by_school_class<Y>.xlsx`); public schools and public academies.
- **Content (checked 2026-11-01):** SAU, district, **school number** (NH state code, e.g. Bedford High School 28555), school name, total completers, and shares entering four-year colleges, entering less-than-four-year institutions, returning for post-graduate secondary study, employed, armed forces, unemployed, status unknown.
- **Caveat:** status is what schools report about completers' plans (intended/reported status), not measured enrollment, so it is not directly comparable with other states' college-enrollment measures. Kept as a secondary measure; the iExplore Post-secondary Enrollment Rate above is the main one.

### ED Data Express (federal graduation rates, school level), classes 2022 on not obtained
- **Tried 2026-11-01** in the user's browser: https://eddataexpress.ed.gov/download/data-builder/data-download-tool with file specs 150 and 151 (4-year ACGR and cohort count; each row has the rate in `Value` and the cohort in `Denominator`), level School. Adding a school-year filter returned server errors ("The website encountered an unexpected error" / "Oops, something went wrong") on every try; the site's banner warns that large selections fail. The Data Library page posts only state-level ACGR files. Scripted requests to the download tool get an AWS WAF challenge (HTTP 202), so it is not scripted.

## Nebraska (`NE`)

### CCPE college continuation rates (`ccpe_continuation`) — the outcome
- **URL:** https://ccpe.nebraska.gov/college-continuation-rates (Tableau Public dashboard `PublicHSCollegeContinuation/CollegeContinuationDashboard`); its DOWNLOAD button links to the file https://ccpe.nebraska.gov/sites/default/files/FL_CollegeGoing.xlsx (found 2026-11-01 from the browser download's source URL; the server answers a plain script request, so it is scripted).
- **Release:** page updated September 28, 2026; file last modified 2026-09-30; NSC match for class 2025 on August 24, 2026. One workbook: a NOTES and a DATA sheet per class (2007-08 to 2024-25), two 2005-06 tables, and a `Tableau Data` sheet (the same rows, no district code).

| Item                | Nebraska (`ccpe_continuation`, `yy-yy DATA` sheets)                                                    |
|---------------------|---------------------------------------------------------------------------------------------------------|
| Counted as enrolled | Enrolled at any NSC-participating college (NSC enrollments or graduations)                             |
| Window              | June 1 after graduation to May 31 of the next year (class 2025: 6/1/2025-5/31/2026)                     |
| Denominator         | On-time (4 years or less) graduates of Nebraska public high schools, from NDE records; no private schools |
| Class               | Sheet '24-25 DATA' = class 2025                                                                          |
| Counts              | On-time graduates, graduates who went to college, rate (share); the rate is rounded in some sheets, so `pct_enrolled` = enrolled ÷ graduates |
| Breakdowns          | None                                                                                                     |
| Suppression         | '*' in all three columns (fewer than 10 graduates); 903 of 4,877 rows                                   |
| School ID           | None. County name, district code (5-6 digits = county + district; classes 2008, 2010, 2011: district number only; class 2012: none), district and school names |
| Classes             | 2008-2025                                                                                                |

- **Linking:** each row's 6-digit county + district code is rebuilt (`state_files.ne_ccpe_district`: county number from the county name in other sheets; class 2012 by county + district name), then the school is matched to a CCD grade-12 school in that district by name (`ne_ccpe_codes`, steps in `NE_CCPE_STEPS`). Linked: 4,804 of 4,877 rows, 100% from class 2015 (the first CCD year in the panel); the 73 unlinked rows are classes 2008-2014 schools that closed or merged before 2014-15 (e.g. Cedar Rapids, Coleridge, Newcastle, Spalding, Dodge and Howells before Dodge-Howells). Covered: 99-100% of panel schools with grade-12 enrollment, classes 2015-2025. No CCD code is matched to two CCPE schools in a year.
- **Statewide:** school sums give 64-72% enrolled (69.6% class 2008, 72.4% 2010, 69.8% 2019, 63.6% 2024, 65.6% 2025; a decline from class 2020); the official state totals (`Tableau Data`) are slightly higher in graduates (class 2008: 20,036 vs. 19,534 in school rows) because suppressed schools are left out of the school rows.
- **Compared with NDE (classes 2016-2023, 1,777 school rows with both):** correlation across schools 0.78-0.89 by class; NDE's mean is 3-10 points higher (77.6 vs. 75.0 in 2016; 79.0 vs. 68.7 in 2023), and the gap widens after class 2019 (CCPE falls, NDE does not). NDE counts students enrolled on October 15 of the year after the first fall, so late starters count in NDE but not in CCPE; NDE's denominator is not published. NDE graduates (estimated) are about 3-7% above CCPE's on-time graduates, consistent with NDE counting all graduates.
- **Limitations:** on-time graduates only; a school is listed under its CCPE name, so name changes between years are matched separately each year.

### NDE Nebraska Education Profile (`nde_nep`) — kept as `pct_enrolled_nde_oct15`
- **URL:** API `https://nepdata.education.ne.gov/api/v1/data/downloads` (file list, saved as `_data_downloads.json`); files from `.../data/downloads/data-file?dataYear=<YYYYYYYY>&fileName=<file>`
- **Release:** school years 2015-16 to 2024-25 (72 files): Agencies, Cohort, CollegeGoingRate, ACT, Membership, FreeReducedLunch, Teachers.

### Content review (2026-11-01), college-going

| Item                | Nebraska (`nde_nep`, CollegeGoingRate files)                                                                    |
|---------------------|-----------------------------------------------------------------------------------------------------------------|
| Counted as enrolled | Enrolled in college on the file's CollegeEnrollmentDate                                                         |
| Window              | October 15 of the year after the first fall (class 2023: 10/15/2024), about 16 months after a spring graduation |
| Denominator         | High school graduates (not published; = count / % x 100)                                                        |
| Class               | HighSchoolGraduationYear '2022-2023' = class 2023                                                               |
| Counts              | College-going count and % published; graduates derived                                                          |
| Breakdowns          | Subgroups (race/ethnicity, gender, FRL, SPED, EL); no college type                                              |
| Suppression         | '*' (files from 2023-24) or -1 / -1.00 (earlier files); 31-46 schools a year                                    |
| School ID           | County (2) + district (4) + school (3) = CCD ST_SCHID                                                           |
| Classes             | 2016-2023 (class 2025, the first covered class, expected in the 2026-27 file)                                   |

- **Files:** `CollegeGoingRate_<YYYYYYYY>.csv`, 2017-18 to 2024-25; each repeats up to four earlier classes, and classes are revised between files (class 2019 statewide: 16,029 enrolled in the 2020-21 file, 16,088 in the 2024-25 file). The 2020-21 and 2021-22 files each carry two different sets of rows labeled "2018-2019". Each class is therefore taken whole from the newest file that holds it (class 2016 from 2020-21, 2017 from 2021-22, 2018 from 2023-24, 2019-2023 from 2024-25). Column names change in 2023-24 (`Type` -> `Level`, `College-Going Pct` -> `CollegeGoingPercent`, ...).
- **Definition:** no written definition was found in NDE's download list (`fileDescription` is empty); the measure is enrollment on `CollegeEnrollmentDate`. Nebraska's postsecondary commission (CCPE) uses a different, related measure (on-time graduates enrolled within the year after graduation; see above).
- **Statewide:** the official statewide row is 72-76% in every class (class 2016: 74.55%); school sums match (74.5%, 75.7, 76.0, 75.7, 73.4, 72.6, 72.7, 76.2 for classes 2016-2023).
- **Linked:** 100% of school rows; covered: 97-99% of panel schools with grade-12 enrollment.
- **No post-period data:** Nebraska's first covered class is 2025 (dose classes 2022-2023, reference 2024), and the newest NDE file ends at class 2023. This is why CCPE (which has class 2025) is the outcome.

## Oklahoma (`OK`)

### OSRHE High School Indicators (`osrhe_hs_indicators`)
- **URL:** https://okhighered.org/studies-reports/indicators/, `.../preparation/`, and the per-year pages `?p=3351` ... `?p=3361`
- **Release:** college-going rates by high school site for 2009-2024 and mean ACT by site for 2018-2024 (23 files; Last-Modified 2023-04-13 to 2026-08-06).
- **Gap:** mean ACT by site before 2018 is only in PDFs and a 2004-08 pivot file, not downloaded.

### Content review (2026-11-01), college-going

| Item                | Oklahoma (`osrhe_hs_indicators`, College-Going Rates workbooks)                                          |
|---------------------|-----------------------------------------------------------------------------------------------------------|
| Counted as enrolled | First-time entering student at an Oklahoma public or private college (OSRHE Unitized Data System); out-of-state colleges only from class 2023, in separate columns (NSC-style match by name and date of birth) |
| Window              | Outcome: anytime in the academic year after graduation (fall to spring); also published: directly in the fall after graduation |
| Denominator         | Graduates of Oklahoma public high schools on SDE's list (class 2013: on-time graduates only; from 2014: all graduates that year) |
| Class               | File `YYYY-...` = class YYYY (`2017-18-HSIR...` = class 2017; `2024-HSIP...` = the 2024-2025 report = class 2024). The 2018-19 file's column headers say "2017 graduates", a copy error: its title is 2018-2019 and its counts differ from the 2017-18 file |
| Counts              | Graduates; enrolled in the fall; enrolled during the year; first-time students from the school from any class; out-of-state (from 2023). Rates are recomputed from counts |
| Breakdowns          | Fall vs. full year; out of state (from class 2023); by district (separate sheet, not read) |
| Suppression         | None (schools with 1-2 graduates are listed); `.` = missing (out-of-state columns); 9 small schools (1-26 graduates, classes 2013-2015) have blank enrollment cells, kept as missing |
| School ID           | None. Classes 2013-2018 give ACT's high school code (not a state code); 2019 on, county and school name only |
| Classes             | 2009-2024 published; read from 2013 (earlier files estimate enrollees from 17-19-year-old first-time students, public and private high schools, per OSRHE's methodology note) |

- **Linking:** each school is matched to a CCD grade-12 school within its county by name (`state_files.ok_college_going`, shared steps `NAME_STEPS` / `name_codes`); the county number (first two digits of CCD `ST_SCHID`) is learned from names that occur once statewide. The CCD key is county-district-site (`ok_ccd_key`: `01-I025-705`). Two fixes for names: the city suffix after 'HS' in classes 2013-2018 is dropped ('CENTRAL HS - TULSA'), and CCD names are also tried with the district name in front ('EDMOND' + 'MEMORIAL HS'). 'Any year' matches use the CCD year nearest the class, since CCD renumbers charters (Harding Charter Prep, Santa Fe South). No CCD school is matched to two OSRHE rows in a class.
- **Linked:** 5,539 of 5,561 rows (98.9-100% by class); the 22 unlinked rows are elementary/intermediate sites with 1-2 graduates (class 2022), virtual charters (Oklahoma Virtual Charter Academy, Epic class 2013), Elmore City Senior HS 2013-2018, Northeast Academy 2013-2015, Santa Fe South Pathways 2017-2022 (CCD name truncated), KIPP OKC College Prep 2022. Covered: 98.7-100% of panel schools with grade-12 enrollment, classes 2015-2024.
- **Statewide (school sums = each file's total row):** % of graduates enrolled during the year: 51.6 (class 2013), 49.3 (2015), 46.2 (2018), 42.4 (2019), 37.2 (2021), 36.3 (2022), 37.0 (2023), 40.3 (2024). The fall rate is 1-2 points lower. Out of state: 6.7% (2023), 6.5% (2024).
- **Breaks:** (1) class 2014 adds graduates who took more than four years (+1,600 graduates). (2) Class 2019 has about 3,600 more graduates than class 2018 (41,375 to 45,014); no note explains it. (3) **Class 2024** (Oklahoma's reference class): OSRHE now also counts graduates enrolled in an Oklahoma college whose admission codes had left them out of the first-time cohort (+2,106 fall, +2,384 full-year students, about 5.2 points statewide); "expected to continue for future reports". Classes 2022-2023 (dose) are on the old definition. Class fixed effects absorb the statewide shift, but not school differences in how many students were added.
- **No post-period data yet:** Oklahoma's first covered class is 2025; reports are posted in May about two years after graduation (class 2023 in May 2025, class 2024 in May 2026), so class 2025 is expected around May 2027. OSRHE also has a SAS Visual Analytics dashboard of high school college-going rates (linked from https://okhighered.org/studies-reports/dashboards/, updated 2026-10-22); not checked for class 2025, not scriptable.
- **Limitations:** in-state colleges only (like Alabama), a definition break in the reference class, name-based linking.

## New York (`NY`)

### NYSED data downloads (`nysed_downloads`)
- **URL:** https://data.nysed.gov/downloads.php
- **Release:** Report Card (SRC), Graduation Rate, and Enrollment databases for every year listed (back to 1999-00; 55 zips, 5.1 GB). Local names are prefixed with the year folder because names repeat across years.

### Content review (2026-11-01), college-going

| Item                | New York (`nysed_downloads`, Report Card databases, table "Postsecondary Enrollment")                    |
|---------------------|-----------------------------------------------------------------------------------------------------------|
| Counted as enrolled | Enrolled at any postsecondary institution: New York public, New York private, or out of state; 2-year (incl. less than 2-year) or 4-year (NSC-based, per the NYSED Report Card) |
| Window              | Within 16 months of high school graduation                                                                |
| Denominator         | `TOTAL_GRAD_COUNT`: students who graduated during the calendar year (January 1-December 31)               |
| Class               | `MEMBERSHIP_DESC` 'Class of YYYY'. Report year Y (`SRC<Y>`, released in the summer after school year Y) holds classes Y-2 and Y-1 (SRC2022: class 2021 only); repeated classes are identical across reports |
| Counts              | Graduates and six enrollment counts (NY public / NY private / out of state × 2-year / 4-year), with percents; the total column is empty for classes 2021-2022, so the total is the sum of the six (equal to the published total in all 5,992 rows that have both) |
| Breakdowns          | College type (as above); subgroups (race, gender, disability, ELL, economic disadvantage, ...); only All Students is read |
| Suppression         | 's'; 8-11 schools a year with any count suppressed (their total is missing)                              |
| School ID           | `ENTITY_CD`, the 12-digit BEDS code = CCD ST_SCHID's last segment; state (`111111111111`), county / need-resource-capacity (`000000...`) and district (`...0000`) rows are dropped |
| Classes             | 2021-2024 (Report Cards 2022-2025). Earlier Report Cards (2016-2017) give only graduates' *planned* college enrollment (`NUM_2YR_COLLEGE`, `NUM_4YR_COLLEGE`), not used |

- **Files:** each Report Card zip holds the same database as `.mdb` and `.accdb` (1.6 GB for 2025). They are read with the `access-parser` package (pure Python, added with `uv add`): the `.accdb` is extracted to a temporary folder that is deleted afterwards; about 20 seconds per database. Only the newest report holding each class is read (SRC2025, SRC2024, SRC2023).
- **Linked:** 100% of school rows (5,081); covered: 98.7-99.0% of panel schools with grade-12 enrollment. The uncovered panel schools are special education schools and BOCES programs, NYC early-college (P-TECH) schools whose students graduate after grade 12, Dream Charter East Harlem, and Port Richmond HS in class 2024 only (listed for classes 2021-2023).
- **Statewide (school sums):** graduates 183,602 (2021), 179,766, 175,255, 174,434 (2024); enrolled within 16 months 69.6%, 71.0%, 73.1%, 73.4%. The state row (class 2023: 128,240 enrolled) exceeds the school sum (128,099) by the suppressed schools. Of graduates in class 2024: 44.6% New York public, 14.0% New York private, 14.7% out of state; 18.6% at 2-year colleges.
- **No post-period data yet:** New York's first covered class is 2025 (dose classes 2022-2023, reference 2024). Class 2025 will be in Report Card 2026 (16 months after June 2025 = October 2026), expected around August 2027 (SRC2025 was released August 2026).
- **Limitations:** only four classes (2021-2024), all pre-period; 16-month window (later than most states' 12 months, like Illinois' 16-month rate).

## New Jersey (`NJ`)

### NJDOE School Performance Reports databases (`njdoe_spr`)
- **URL:** landing page https://www.nj.gov/education/spr/download/
  - Data: `https://www.nj.gov/education/sprreports/dowxnload/DataFixles/<year>/<file>`
  - Documents: `https://www.nj.gov/education/sprreports/download/Documents/<year>/<file>`
  - This URL pattern comes from the page's `download.js`.
- **Downloaded:** 2026-10-09 21:09 to 23:31
- **Release:** school years 2015-2016 to 2024-2025 (46 files). Last-Modified 2025-08-12 to 2026-05-21.
- **Filters:**
  - For each year: `Database_SchoolDetail.xlsx` (data) and `Database_SchoolLayout.xlsx` (layout), saved with a `<year>_` prefix.
  - `ReferenceGuide.pdf`, `DataPrivacyRules.pdf` and `FAQs.pdf` are optional (a 404 is logged, not an error).
  - Not posted: 2015-2016 FAQs, and all three 2024-2025 documents.
  - Years before 2015-2016 use a different archive layout and are not included yet.
- **Caveats:** The state's FAFSA mandate (P.L.2023, c.295) covers only the classes of 2025–2027.
- **Graduate counts (checked 2026-11-02): none.** The `4YrGraduationCohortProfile` sheet (2019-2020 to 2023-2024; `GraduationCohortProfile` in 2024-2025) gives `Graduates`, `Continuing Students`, and `Non-Continuing Student` as **percentages** of the 4-year cohort (e.g. Atlantic City HS 2019-20: 79.4 / 4.8 / 15.8), not counts; the other graduation sheets are rates and targets. EDFacts school-level ACGR (cohort counts) covers New Jersey only to class 2021, before its dose classes (2022-2023). **But** NJDOE's separate ACGR page (https://www.nj.gov/education/spr/adddata/acgr.shtml, updated 05/01/2026; downloaded 2026-11-02 as `njdoe_acgr`, cohorts 2020-2025, read by `state_files.nj_acgr_graduates`) posts `Cohort<Y>_4YearAdjustedCohortGraduationRates[andCounts]byStudentGroup.xlsx` for each cohort, with school rows (county, district, school codes) and `Graduation Rate`, `Cohort Count`, `Graduated` (2025: `Adjusted Cohort Count`), state calculation (all state-endorsed diplomas); header row 6. Checked 2026-11-02 for cohorts 2021-2025: `Total`/`All Students` rows have numeric counts for about 95% of schools ('*' privacy, 'N' none). These are on-time 4-year cohort graduates, not all graduates of the year (the outcome's denominator).
- **Postsecondary enrollment:** the School Performance Report databases have postsecondary sheets through 2022-2023 only. The 2023-2024 sheets are empty (header row only) and 2024-2025 has none: per the 2023-2024 Reference Guide, NSC data "was not received ... in time", and NJDOE releases it separately on the SPR Additional Data page (below). The SPR databases are not used for the outcome.

### NJDOE postsecondary enrollment trends (`njdoe_postsecondary`) — the outcome
- **URL:** https://www.nj.gov/education/spr/adddata (saved as `_landing_page.html`); files matching `Postsecondary*.xlsx`: `Postsecondary_Enrollment_Rate_Trends_Fall_16month_Rates.xlsx` (dated 6/19/24, the 2022-23 release) and `2023_24_Postsecondary_Enrollment_Rates.xlsx` (dated 11/10/25; also class 2024 fall and class 2023 16-month by student group). A plain request works.

### Content review (2026-11-01), college-going

| Item                | New Jersey (`njdoe_postsecondary`, trend sheets)                                                          |
|---------------------|-----------------------------------------------------------------------------------------------------------|
| Counted as enrolled | Matched by NSC to enrollment at any postsecondary institution (U.S.)                                    |
| Window              | Outcome: as of the fall after graduation. Also: at any point within 16 months (`pct_enrolled_16m`)      |
| Denominator         | All high school graduates of the school year (September 1-August 31; NJ SMART), not a cohort            |
| Class               | Columns 'Fall Postsecondary Enrollment: Class of YYYY' / '16-month ...: Class of YYYY'; the 2023-24 release = fall class 2024 and 16-month class 2023 |
| Counts              | None: rates only, as a range 'L-U%'. L = NSC-matched share of graduates (kept as the rate); U = L / 0.97, an allowance for graduates NSC does not match (not kept) |
| Breakdowns          | 2-/4-year, public/private, in/out of state as shares of enrollees, by student group (latest class only, separate sheets; not read) |
| Suppression         | '*' (fewer than 10 graduates), 'N' (no graduates)                                                         |
| School ID           | CDS: county (2) + district (4) + school (3), 9 digits = CCD ST_SCHID's last two segments (`NJ-010110-010`) |
| Classes             | Fall 2019-2024, 16-month 2018-2023 (five classes per file; each class from the newest file; overlapping classes are identical) |

- **Linked:** 100% of school rows (2,890); covered: 94.9-98.4% of panel schools with grade-12 enrollment.
- **Statewide (state row, lower bound):** fall 72.8% (class 2019), 69.1, 69.1, 70.3, 69.8, 69.1% (2024); 16-month 78.3% (2018), 76.9, 74.3, 74.1, 75.1, 74.4% (2023).
- **No post-period data yet:** New Jersey's first covered class is 2025 (dose classes 2022-2023, reference 2024). Its fall rate should be in the next trend file (2024-25 release); the 2023-24 file was posted November 10, 2025, so the next one may come out around November 2026. The download step picks it up by filename pattern.
- **Limitations:** rates only (no graduate counts, so no weighting by graduates and no estimated counts); the 16-month rate lags the fall rate by a year.

## Connecticut (`CT`)

### data.ct.gov (`ct_open_data`)
- **URL:** https://data.ct.gov/d/m3ib-yiy7 (College Enrollment, Credit Attainment and Remediation of High School Graduates by School, P20 WIN) and https://data.ct.gov/d/h28j-iix5 (Next Generation Accountability System, CSDE), as CSV.

## Pennsylvania (`PA`)

### PDE graduation (`pde_graduation`)
- **URL:** https://www.pa.gov/agencies/education/data-and-reporting/high-school-graduation
- **Release:** 4-year cohort graduation rates and "Graduates Public by School" for 2010-11 to 2024-25 (30 files).

## National sources used for every state (`US`)

### FAFSA completion by high school (`fsa_fafsa_completion`)
- **URL:** https://studentaid.gov/data-center/student/application-volume/fafsa-completion-high-school. The page is a JavaScript app, so the file list is read from the same path with `.json` appended. The data-details and FAQ pages are also saved as JSON (`_data_details.json`, `_faq.json`).
- **Downloaded:** 2026-10-09 21:29 to 23:31; December files re-downloaded 2026-10-27.
- **Release:** monthly national "as of" snapshots, 2016-01-31 to 2026-09-30 (132 files).
  - Every file has Last-Modified 2026-10-08. That reflects the server re-stamping the files, not the release date, so the snapshot date in the label is the version that matters.
- **Filters:**
  - Every page link whose URL contains "ARCHIVE" and whose date label is December 31 (2016–2025), plus the newest June 30 file (currently 2026-06-30). Age-19 cutoff only; the "(18 year olds)" files are skipped.
  - Following Deneault's `cleaningFAFSA_aejep.do`, a class's FCR numerator comes from the fixed prior-cycle "Through June" column of a later file rather than the preliminary June 30 snapshot.
  - File-to-class mapping (checked from the header rows on 2026-10-27): the Dec 31 file of year Y+1 has prior-cycle columns "Through June Y" and "Through December Y", which are the class of Y. So Dec 2016 → class of 2015, ..., Dec 2025 → class of 2024. The June 30 2026 file has "Through June 2025" (class of 2025, fixed) and a current-cycle "Through June 30, 2026" column (class of 2026, preliminary). There is no Dec 2015 file; the archive starts in January 2016.
  - The prior-cycle columns are revised slightly between files. Checked 2026-10-27 for the class of 2025, June 30 2026 vs. Sept 30 2026 file (29,505 schools matched on code, name, city, state): "Through June" completions differ for 147 schools (0.5%), mostly by +1 (range −8 to +8; 6 decreases). In five of the study states: AL 0/555, IL 2/885, IN 5/538, LA 0/474, TX 18/2,420. The Dec 31 file of year Y+1 is the last file carrying class Y's columns, so it holds the latest revision; this is a reason to prefer it. The class of 2025 should be refreshed from the Dec 31 2026 file once posted.
  - The header's cycle labels (e.g. "2016/ 2017 Cycle" in the Dec 2016 file) don't line up cleanly with these classes; use the "Through June YYYY" dates to assign classes.
  - History: on 2026-10-27 the download was first narrowed to June files and the other 120 monthly files (and `fafsa_hs_2017-06-30_age18.xls`) were deleted with their manifest rows; the December files were then re-downloaded and the June 30 2016–2025 files deleted with their manifest rows, the same day.
  - Local filenames are built from the page's date label: `fafsa_hs_<YYYY-MM-DD>.<ext>`. The publisher's filename is kept in the manifest note.
  - Sometimes the filename date differs from the label (e.g., label "June 30, 2019", file `HS_ARCHIVE06282019.xls`).
  - The current per-state files (`LA.xls`, ...) are not downloaded because they are overwritten every two weeks.
- **Methodology changes:**
  - **Age cutoff:** the Apr–Jun 2017 files labeled "(18 year olds)" (previously saved as `_age18`; no longer downloaded) count applicants no older than 18. All other files use no older than 19.
  - **FAFSA opening date:** the FAFSA opened in January through the class of 2016 and on October 1 from the class of 2017 on. Earlier filing makes cumulative counts at a given date not comparable across that break.
  - **Matching:** from November 2022, files include a School Code (equal to the NCES school ID for public schools). Earlier files must be matched on school name and city. The NCES ID match was checked in the June 2023 file: IL 723, LA 334 and NJ 421 schools matched.
  - **Timing columns:** each file carries the prior cycle's fixed "Through June" and "Through December" columns.
  - **What is counted:** FAFSA only. Alternative state applications (Illinois Alternative Application, NJAFAA, TOPS application, CADAA, TASFA) are not included.
- **Deneault's files:** Dec 31 2016, 2017 and 2018; Dec 31 2019; Jun 30 2020.

### NCES Common Core of Data, school-level nonfiscal files (`nces_ccd_school`)
- **URL:** landing page https://nces.ed.gov/ccd/files.asp. The file list comes from the JSON API the page calls, https://nces.ed.gov/ccd/datatables/api/File/2/7/0/0/0/0 (Nonfiscal × School level, all years). The API response is saved as `_file_list.json`.
- **Downloaded:** 2026-10-09 21:32 to 23:31
- **Release:** school years 2011-2012 to 2025-2026 (167 files). The version is the current one listed for each year:

| School year | Version | Components |
|---|---|---|
| 2011-12 | v.1a | Combined file |
| 2012-13, 2013-14 | v.2a | Combined file |
| 2014-15 | v.1a | Directory, Membership, Staff, School Characteristics, Lunch Program Eligibility |
| 2015-16, 2016-17 | v.2a | same five |
| 2017-18 to 2023-24 | v.1a | same five |
| 2024-25 | v.2a | same five |
| 2025-26 | no version label (preliminary) | Directory only, as of 2026-10-09 |

- **Filters:**
  - Years from 2011-12 on (`CCD_FIRST_YEAR = 2011`), the earliest needed for lagged grade-9 counts for the class of 2015.
  - Current version only (`versionOrder == 0`).
  - Data files and documentation only. SAS duplicates and zipped documentation are skipped, keeping flat files and PDFs.
  - One undated API entry linking to the EDGE site is skipped.
  - Files are saved as `<year>/<publisher filename>`.
- **Caveats:**
  - Several Membership zips use Deflate64 compression, which Python's `zipfile` can't read. Extract them with `unzip`.
  - `ST_SCHID` (e.g., `LA-302-302006`) links state school codes to NCES IDs.
  - Locale (`ULOCAL`) is in the CCD files only through 2013-14; after that use EDGE.

### EDFacts four-year adjusted cohort graduation rates (`edfacts_acgr_urban`)
- **URL:** `https://educationdata.urban.org/csv/edfacts/schools_edfacts_grad_rates_<year>.csv`. The API endpoint list (https://educationdata.urban.org/api/v1/api-endpoints/) is saved as `_endpoints.json`. Documentation: https://educationdata.urban.org/documentation/schools.html#edfacts_grad_rates
- **Downloaded:** 2026-10-10 00:10
- **Release:** Urban years 2010–2019 (10 files). Last-Modified 2021-02-22 to 2023-05-01. Nothing later was posted as of 2026-10-09.
- **Filters:** none; the full national file for each year.
- **Source conflict:** this is a secondary source. The primary source is ED's EDFacts data files, but ed.gov blocks scripted downloads (an Azure firewall returns 403; checked 2026-10-09). Urban republishes the same EDFacts data, keyed by NCES school ID.
- **Year mapping:** Urban year Y is the graduating class of Y+1. Urban 2017 and 2018 matched LDOE's class-of-2018 and class-of-2019 school rates for 100% of about 230 linked Louisiana schools, versus about 35% for the adjacent class (checked 2026-10-09).
- **Caveat:** rates are reported as ranges for privacy (`grad_rate_low`, `grad_rate_high`, `grad_rate_midpt`).

### EDFacts four-year ACGR, class 2021, via ED Data Express (`edfacts_acgr_ede`)
- **URL:** https://eddataexpress.ed.gov/sites/default/files/data_download/EID_9092/SY2021_FS150_FS151_DG695_DG696_SCH_data_files.zip, listed in the Data Library (https://eddataexpress.ed.gov/download/data-library; filter File Spec 150, Level SCH). Primary source; a plain scripted request works (2026-11-01).
- **Release:** school year 2020-21 = class 2021 (as of 05/25/2022; file dated 2023-06-15). The zip holds the data CSV, a data-notes CSV, and a README. This is the only school-level ACGR file in the Data Library; the library lists LEA files for classes 2011-2021 and state files for 2011-2023, and none at school level after class 2021.
- **Contents:** 248,473 rows: one per school × subgroup ('All Students in School', race, economic disadvantage, disability, ...); `Value` = rate as text (exact '93%', ranges '90-94%', bounds '>=95%' / '<50%', 'S' suppressed), `Denominator` = cohort count, `NCES SCH ID` = 12-digit NCES school ID. All study states except Illinois have school rows (Texas 1,838 schools, New York 1,267, ...).
- **Illinois:** the data notes say ED suppressed Illinois's four-year ACGR "due to concerns with data quality" at LEA and school level for SY 2018-19 and at all levels for SY 2019-20 and 2020-21 (classes 2019-2021). Use ISBE's own rates for Illinois.
- **Later classes:** only in the Data Download Tool (manual; see Louisiana section above for the attempt and the bot check). Most study states publish their own ACGR files, already in the catalog (`grad_rate` rows); Maryland (MSDE report card blocks scripts) and Oklahoma (no state file found) have none.

### EDFacts high school assessments via Urban (`edfacts_assess_urban`)
- **URL:** `https://educationdata.urban.org/api/v1/schools/edfacts/assessments/<year>/grade-9/?fips=<FIPS>&limit=10000`, one JSON per study state × year (FIPS from `config.STATE_FIPS`). Docs: https://educationdata.urban.org/documentation/schools.html#edfacts_assessments
- **Release:** Urban years 2014-2018 (school years 2014-15 to 2018-19). Urban posts 2009-2018 and 2020 only. The bulk CSVs (~600 MB/year with all grades and subgroups) are not used.
- **Content:** Urban `grade_edfacts` 9 = the state's high school test; all-student rows (subgroup codes 99) keyed by `ncessch`; `read_/math_test_num_valid` and `pct_prof_low/high/midpt` (ranges for privacy; negative values are missing/suppressed codes). Each response must have `next = null` and `count` equal to the rows returned (one page).
- **Checked 2026-11-01:** 75 files, 59,503 school rows, every response complete in one page. **Maryland 2017 (2017-18) is empty**: Urban has no Maryland school or district assessment rows for that year at any grade, so Maryland's baseline uses 2014-2016 and 2018.
- **Use:** baseline school ability for the robustness check only (DECISIONS 2026-11-01). Secondary source (republication of ED's EDFacts files, which ed.gov blocks to scripts).

### NCES Private School Universe Survey (`nces_pss`)
- **URL:** https://nces.ed.gov/surveys/pss/pssdata.asp
- **Downloaded:** 2026-10-27, by `code/00_download_raw_data.py PSS`.
- **Release:** biennial public-use files, one row per private school: 2013-14, 2015-16, 2017-18, 2019-20, 2021-22, 2023-24 (CSV zip and codebook PDF for each).
- **Filters:** CSV releases only (earlier waves are SAS/SPSS only). The "Frame Data" CSVs for 2017-18 on are sampling frames, not survey files, and are not downloaded.
- **Use:** links pre-2021 FSA records of private schools to FSA's codes. `PPIN` is the 8-character code FSA uses for private schools from the class of 2021 on (4,162 of FSA's 5,981 distinct 8-character codes appear in the 2019-20 wave alone).
- **Caveats:** column names are lowercase in 2015-16 and uppercase otherwise. Highest grade is `HIGRyyyy` (yyyy = spring year), a recode: 1 = all ungraded, 2 = prekindergarten, ..., 17 = grade 12.

### NCES EDGE public school locations and locale codes (`nces_edge_locations`)
- **URL:** landing page https://nces.ed.gov/programs/edge/Geographic/SchoolLocations
  - Yearly files: `https://nces.ed.gov/programs/edge/data/EDGE_GEOCODE_PUBLICSCH_<yyyy>.zip`
  - 2014-15 file: https://nces.ed.gov/ccd/data/zip/EDGE_GEOIDS_201415_PUBLIC_SCHOOL_csv.zip
  - Technical documentation: https://nces.ed.gov/programs/edge/docs/EDGE_GEOCODE_PUBLIC_TECHDOC.pdf
- **Downloaded:** 2026-10-10 00:20 to 00:23
- **Release:** school years 2014-15 to 2024-25 (11 data files plus the 2014-15 documentation zip and the technical documentation). Last-Modified runs from 2016-10-04 (2014-15 documentation) to 2025-12-19 (2024-25). The technical documentation is dated 2026-01-07.
- **Filters:**
  - Yearly links are found on the landing page with the pattern `href="...EDGE_GEOCODE_PUBLICSCH_(\d{4})\.zip"`.
  - Links with a `~/data/` prefix are marked optional. 2025-26 is linked that way and returned 404 on 2026-10-09, apparently a placeholder for an unreleased file.
  - The 2014-15 file is listed under CCD rather than on this page, so it is added by hand.
- **Used for:** rural versus urban heterogeneity (urban-centric locale code). For 2011-12 to 2013-14, use `ULOCAL` from the CCD files.

### Federal extras: CRDC (`crdc`), EDGE neighborhood poverty (`edge_neighborhood_poverty`), IPEDS directory (`ipeds_hd`)
- **URL:** `https://civilrightsdata.ed.gov/assets/ocr/docs/<YYYY-YY>-crdc-data.zip`; https://nces.ed.gov/programs/edge/Economic/NeighborhoodPoverty (scraped); `https://nces.ed.gov/ipeds/datacenter/data/HD<YYYY>.zip`
- **Release:** CRDC 2013-14, 2015-16, 2017-18, 2020-21, 2021-22 (1.66 GB); school neighborhood poverty 2015-16 to 2021-22; IPEDS HD 2014-2024.

## Policy sources (`data/policy/`)

Entered by hand; each row cites its source.

- **EdTrust (2025), *A Scan of State Universal FAFSA Policies*** (Feb 2025): https://edtrust.org/wp-content/uploads/2025/02/Universal-FAFSA-Report-V4.pdf. Summary table (p. 9), opt-out wording (pp. 10–11), alternative applications (p. 13), state "Fast Facts" with each state's implementation class (pp. 15–38), statute citations (notes 20–37). Covers 14 states; not Pennsylvania. Its Colorado class of 2022 conflicts with CDHE (below).
- **User's state audit** (`docs/state_sources_audit.pdf`): EdTrust's summary table plus Pennsylvania, a timing table (first class, dose, reference, post), and state data sources.
- **Louisiana repeal:** NCAN, https://ncan.org/Web/News/Louisiana_Board_Rescinds_States_Universal_FAFSA_Policy.aspx; Louisiana Illuminator, 2024-03-06. BESE voted in March 2024 to remove the requirement starting with the class of 2025. The Bulletin 741 section is still to be checked.
- **Pennsylvania:** PDE, https://www.pa.gov/agencies/education/resources/student/empoweru/resources-for-institutions/campaigns/pa-fafsa-go/pa-fafsa-requirement (accessed 2026-10-27). Act 47 of 2025, 24 P.S. § 16-1617; classes of 2027 on; FAFSA or opt-out form required but graduation not affected; covers public, charter, cyber charter, CTC, and nonpublic schools.
- **Colorado Fund My Future (HB21-1330):** CDHE page https://cdhe.colorado.gov/fund-my-future (its text says "6 proposals" but lists 7 grantees) and CDHE-COSI Fund My Future annual reports 2021-22 to 2024-25 (https://highered.colorado.gov/publications/Reports/Legislative/1330/). The reports give the 11 high schools served and each grantee's program launch (fall 2022, spring 2023, fall 2023). Harrison High School appears in the 2024-25 report's list but not the 2023-24 one. NCES IDs were looked up in the CCD 2022-23 and 2024-25 directories (Colorado High School Charter's Osage campus by its address, 1175 Osage St).

## Replication package

### Deneault (2023), openICPSR project 161021 V1
- **URL:** https://www.openicpsr.org/openicpsr/project/161021/version/V1/view
- **Downloaded:** manually by the user, because openICPSR requires a login and blocks scripts (Cloudflare 403). The download date was not recorded; add it here.
- **Release:** V1, saved to `data/raw/replication/deneault_2023/` (`README Deneault Data.pdf`, `161021-V1/*.do`). It is git-ignored and not in the manifest.
- **Filters:** code and README only. The `Raw-Data` folder has not been added yet.

## Identified but not downloaded yet

These were found while surveying the other study states. They are not in `sources.py`, so they have no manifest record.

| State | Source | URL | Notes |
|---|---|---|---|
| CA | CSAC Race to Submit / Success dashboard service | https://webutil.csac.ca.gov/Dashboard/assets/services/SuccessDashboardService.svc/ | Methods: `GetSuccessDashboard_ConfigAsJSON`, `GetSuccessDashboard_HighSchoolsAsJSON` (CDS code and NCES ID), `GetSuccessDashboard_HighSchoolDataAsJSON`. Counts FAFSA and CADAA combined. Only 2025 and 2026, at the 06/30 and 09/02 deadlines. Older data rolls off, so snapshots need to be saved with the load date. |
| NE | NDE FAFSA Graduation Requirement Report (to the Legislature) | https://nebraskalegislature.gov/FloorDocs/109/PDF/Agencies/Education__Department_of/901_20251212-145201.pdf | Class of 2025 completed / opted out / not completed by school and district; small counts suppressed with `*`. |

Sources that need a data request are listed in `data/raw/README.md`.
