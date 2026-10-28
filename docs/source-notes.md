# Source notes

One entry per source: where it came from, when it was downloaded, which release or version, and which filters or queries selected the files. Download times are UTC, taken from `data/raw/download_manifest.csv`, which also records each file's URL, size, SHA-256, and the server's Last-Modified header. File lists are defined in `code/sources.py`; run `python code/00_download_raw_data.py <GROUP>` to reproduce a group.

"Last-Modified" is the server's header, not necessarily the publisher's release date. Where a file states its own release or "data as of" date, that date takes precedence.

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
  - ISBE resets connections from clients without browser-like headers. `code/http_utils.py` sends them.

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
- **Caveats:** nj.gov also needs browser-like headers. The state's FAFSA mandate (P.L.2023, c.295) covers only the classes of 2025–2027.

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
