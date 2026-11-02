# Decisions

Record consequential choices about data, samples, variables, and methods. Newest first.

## 2026-11-01: Reduced-form sample and outcome

- **Decision:** (user request: merge outcomes for the reduced form) `code/08_reduced_form.py` left-joins `state_outcomes.parquet` onto `analysis_panel.parquet` by state, class, and `school_id` and estimates, for each state, `enroll ~ dose × post + controls | school + class` with the first stage's weights, screens, controls, specifications, and school-clustered errors. `enroll` = the state's published rate (`pct_enrolled`) / 100; Louisiana's `deneault` spec uses `penroll`. Sample: the first-stage sample limited to the window classes in which the state has outcome data, keeping schools with the outcome in every one of those classes (balanced); a state needs a pre and a post class. The first stage is re-estimated on the same sample and the ratio reported.
- **Alternatives considered:** requiring the full first-stage window (rejected: drops Texas, whose outcome starts at class 2019, and California and Indiana, whose newest outcome class is one short of the window); an unbalanced outcome panel (rejected for now: Deneault uses a balanced sample).
- **Reason:** Same design as the first stage, so the two are comparable school for school.
- **Affects:** new script and outputs (`reduced_form_panel.parquet`, `reduced_form_by_state.csv`); `06_first_stage.sample` / `estimate` take the outcome column as an argument (default `fcr`; first-stage output unchanged). Windows: TX 2019-2023, CA 2019-2023 (one post class), IN 2020-2024 (one post class); OK, NY, NJ skipped (no post-period outcome); NE drops schools with any suppressed class (195 to 147 in `main`). Outcomes differ across states (`window`), so coefficients are comparable within a state, not in level across states.
- **Related issue:**

## 2026-11-01: Downloads use an honest User-Agent, not a browser string

- **Decision:** (user request) `sources.HEADERS` now sends `fa26-1433-research-downloader/1.0 (academic research)` instead of a Chrome User-Agent with browser Accept-Language/Connection headers.
- **Alternatives considered:** keeping the browser string (rejected: it impersonates a browser to get past server checks); Python's default agent (rejected: LDOE, the MLDS Center and CDE Colorado return 403 to 'Python-urllib', and studentaid.gov times out).
- **Reason:** Tested 2026-11-01 with one 1 KB request per host (23 hosts): with the default agent, 19 hosts work, `doe.louisiana.gov`, `mldscenter.maryland.gov` and `ed.cde.state.co.us` return 403, and `studentaid.gov` times out; with the honest agent all 23 work. ISBE and nj.gov, the original reasons for the browser headers, accept plain requests. A full `--dry-run` (all landing pages and API listings) completes without errors.
- **Affects:** `code/sources.py`, source notes. Files already downloaded are unchanged.
- **Related issue:**

## 2026-11-01: New Jersey outcome is NJDOE's fall college enrollment rate

- **Decision:** New Jersey's outcome is NJDOE's % of graduates enrolled at any college in the fall after graduation, by school, classes 2019-2024, from the postsecondary trend files on the SPR Additional Data page (new source `NJ/njdoe_postsecondary`, scraped by filename pattern); the published range's lower bound (the NSC-matched share) is the rate (`window` = `nj_fall`). The 16-month rate (classes 2018-2023) is kept as `pct_enrolled_16m`.
- **Alternatives considered:** the 16-month rate (rejected as the main outcome: it covers the reference class 2024 and the first post class 2025 one year later); the upper bound (lower bound ÷ 0.97, adds nothing); the SPR database sheets (no postsecondary data from 2023-24).
- **Reason:** The fall rate is the only New Jersey measure that covers the reference class now and will cover class 2025 in the next release.
- **Affects:** `07_build_state_outcomes.py`, `state_files.nj_postsecondary`, `sources.new_jersey`, codebook, source notes. New Jersey has **no post-period outcome data** until the 2024-25 trend file is posted. Rates only (no counts).
- **Related issue:**

## 2026-11-01: New York outcome is NYSED's 16-month college enrollment; Access databases read with access-parser

- **Decision:** New York's outcome is the NYSED Report Card's count of graduates (calendar-year class) enrolled at any college within 16 months of graduation, ÷ graduates, classes 2021-2024 (`window` = `ny_16m_any`); the total is the sum of the six college-type counts, which are kept as `enrolled_instate_public`, `enrolled_instate_private`, `enrolled_outstate`, `enrolled_2yr`, `enrolled_4yr`. The Access databases are read in Python with the `access-parser` package (`uv add access-parser`) from a temporary extract.
- **Alternatives considered:** `mdbtools` (rejected: a system install outside `uv`, so not one-click); the 2016-2017 Report Cards' planned college enrollment (rejected: plans, not enrollment).
- **Reason:** The only school-level college enrollment measure NYSED publishes; it covers all colleges (in and out of state).
- **Affects:** `07_build_state_outcomes.py`, `state_files.ny_postsecondary`, `pyproject.toml` / `uv.lock`, codebook, source notes. New York has **no post-period outcome data** until Report Card 2026 (expected around August 2027). Reading the three databases adds about a minute to the build.
- **Related issue:**

## 2026-11-01: Oklahoma outcome is OSRHE's in-state college-going rate in the year after graduation

- **Decision:** Oklahoma's outcome is OSRHE's count of public high school graduates entering an Oklahoma public or private college for the first time in the academic year after graduation (fall through spring), ÷ graduates, classes 2013-2024 (`window` = `ok_year_after_instate`). The fall-only rate is kept as `pct_enrolled_fall`, and out-of-state enrollment (classes 2023-2024 only) as `enrolled_outstate` / `pct_of_grads_outstate`. Classes 2009-2012 are not read. Schools are matched to CCD by county + name (`state_files.name_codes`, shared with Nebraska; any-year matches now use the CCD year nearest the class).
- **Alternatives considered:** the fall-only rate (kept); in- plus out-of-state enrollment (rejected: out-of-state is reported only from class 2023); classes 2009-2012 (rejected: enrollees were estimated by age from college records, and private high schools were included).
- **Reason:** The full-year rate is the closest to the other states' "within a year" windows; it is the only Oklahoma school-level college-going source.
- **Affects:** `07_build_state_outcomes.py`, `state_files.ok_college_going`, codebook, source notes. Oklahoma has **no post-period outcome data** until class 2025 is published (expected around May 2027). The reference class 2024 uses a broader enrollment definition than the dose classes (+5.2 points statewide), see source notes.
- **Related issue:**

## 2026-11-01: Nebraska outcome is CCPE's college continuation rate (classes 2008-2025)

- **Decision:** Nebraska's outcome is CCPE's college continuation rate by public high school: on-time (4 years or less) graduates enrolled at any NSC college between June 1 after graduation and May 31 of the next year, ÷ on-time graduates (NDE records), classes 2008-2025, from the published counts (`window` = `ne_year_after`). The workbook behind the dashboard's DOWNLOAD button (`FL_CollegeGoing.xlsx`) is a direct file, so it is scripted (`NE/ccpe_continuation`). The sheets have no school number, so schools are matched to CCD by county + district code and school name (`state_files.ne_ccpe_codes`: exact name, then distinctive name words, same year then any year, then the district's only CCD high school where CCPE lists one school there). NDE's rate (previous outcome) is kept as `pct_enrolled_nde_oct15`.
- **Alternatives considered:** keeping NDE's college-going rate (classes 2016-2023 only, no post-period class; enrollment on October 15 of the year after the first fall).
- **Reason:** CCPE covers class 2025, Nebraska's first post-mandate class, and the pre-period back to 2008; it publishes graduate and enrollee counts (NDE's graduates had to be estimated); its window (the year after graduation) is close to IN, NH, MD and CA. Classes 2016-2023 agree with NDE across schools (correlation 0.78-0.89), with NDE 3-10 points higher (its later date also counts students who start college in the second fall).
- **Affects:** `07_build_state_outcomes.py`, `state_files.ne_ccpe_continuation`, `sources.nebraska`, codebook, source notes. Nebraska now has one post-period class (2025). The denominator is on-time graduates only (later graduates are excluded). Supersedes the entry below.
- **Related issue:**

## 2026-11-01: (superseded) Nebraska outcome is NDE's college-going rate (pre-period only)

- **Decision:** Nebraska's outcome is NDE's college-going % by school (enrolled on October 15 of the year after the first fall), classes 2016-2023, each class from the newest file that holds it (`window` = `ne_oct15_second_fall`). Graduates are count / % × 100. Suppressed cells ('*' or -1) are missing.
- **Alternatives considered:** CCPE's college-continuation dashboard (by the following April; Tableau, not scripted). (Later found to be a direct file; see the entry above.)
- **Reason:** The school-level college-going source that NDE publishes for download.
- **Affects:** `07_build_state_outcomes.py`, `state_files.ne_college_going`. Nebraska has **no post-period outcome data** (first covered class 2025; newest class 2023), so it is out of the reduced form until class 2025 is published; the pre-period data can still be used for pre-trend checks.
- **Related issue:**

## 2026-11-01: New Hampshire outcome is the iExplore post-secondary enrollment rate

- **Decision:** New Hampshire's outcome is NH DOE's iExplore Post-secondary Enrollment Rate by high school (2- or 4-year enrollment within the year after graduation), classes 2016-2025, with dashboard year Y = class Y (`state_files.NH_CLASS_OF`, checked against the same class's reported plans and FAFSA completion). Graduates are the iPlatform completers of the same class; `enrolled` = rate × graduates is an estimate (`window` = `nh_year_after`).
- **Alternatives considered:** Completers By Status (reported post-graduation plans, kept as a secondary measure in the raw files); year Y = class Y-1 (rejected by both checks).
- **Reason:** The only New Hampshire source of measured college enrollment by school.
- **Affects:** `07_build_state_outcomes.py`, `state_files.nh_*`, codebook. Rates only (no published counts); class 2024 (the only post-period class) shows a large drop (47.9% vs. 56.5% for class 2023).
- **Related issue:**

## 2026-11-01: Indiana outcome is CHE's college-going rate

- **Decision:** Indiana's outcome is CHE's college-going rate: graduates enrolled at any college that participates in NSC ÷ high school graduates, by high school, classes 2008-2024 (`window` = `in_year_after`), from the published counts. Schools are linked by the 2024 file's IDOE school numbers (applied to every year by exact name), else by name + city in CCD with safeguards against shared keys.
- **Alternatives considered:** Indiana public enrollment only (`enrolled_in_public`, kept); linking by name alone (rejected: 27 Indiana grade-12 schools share a name key, and private schools would take public schools' IDs).
- **Reason:** Counts all colleges, published as counts for every class needed.
- **Affects:** `07_build_state_outcomes.py`, `state_files.in_college_going`, codebook. The time window is not stated in the data notes; one post-period class (2024) until the 2025 cohort is posted.
- **Related issue:**

## 2026-11-01: California outcome is CDE's 12-month college-going rate

- **Decision:** California's outcome is CDE's 12-month college-going rate: completers enrolled at any U.S. college within 12 months (NSC) ÷ high school completers, all students, by school, classes 2015-2023 (`window` = `ca_12m_any`), from the published counts.
- **Alternatives considered (user chose to keep completers):** a graduates-only denominator to match the other states. Non-graduate completers (GED, CHSPE, adult-education diploma) are 0.1-0.4% of completers, and where graduates = completers − non-graduate completers can be computed exactly the graduates-only rate is 0.1-0.3 points higher (class 2019: 60.62% vs. 60.40%). But the non-graduate count is suppressed (10 or fewer) in 480-760 schools a year (about 30%), and summing the two diploma types (`AGY` + `AGN`) loses even more schools. Subtracting non-graduate completers where published (suppressed counts as 0) was also possible; not used.
- **Reason:** California publishes one college-going measure; it counts all colleges and any enrollment within 12 months, like Illinois and Maryland.
- **Affects:** `07_build_state_outcomes.py`, `state_files.ca_college_going`, codebook. Only one post-period class (2023) until class 2024 is posted. FERPA-blocked records (about 11%) count as not enrolled.
- **Related issue:**

## 2026-11-01: Texas outcome uses all graduates; SAT/ACT files dropped from the download

- **Decision:** (user) (1) Texas's outcome is THECB's fall enrollment at Texas public or private colleges ÷ **all** high school graduates, counting 'not trackable' graduates (non-standard IDs, 5-9% of graduates) as not enrolled (`window` = `tx_fall_texas`); the share of trackable graduates is kept as `pct_enrolled_trackable` for a robustness check. (2) SAT/ACT files that are not used are removed from `sources.py` (Texas `tea_sat_act`, Indiana grade-11 SAT, Oklahoma mean ACT, Nebraska `ACT_*`, Illinois 2015-2017 assessment zips; catalog status `dropped`). Louisiana's ACT (replication) and the EDFacts proficiency files (robustness) stay. Files already on disk are not deleted by script (AGENTS.md); the user deletes them by hand, then `00_download_raw_data.py --prune` removes their manifest rows.
- **Alternatives considered:** Excluding not-trackable graduates from the Texas denominator (kept as the robustness version); keeping the SAT/ACT downloads (rejected: not used, about 380 MB).
- **Reason:** Unmatched students count as not enrolled in the other states too; test scores are not a control (DECISIONS 2026-11-01).
- **Affects:** `07_build_state_outcomes.py`, `sources.py`, `00_download_raw_data.py` (`--prune`), catalog, codebook.
- **Related issue:**

## 2026-11-01: Maryland outcome is MLDS college enrollment within one year

- **Decision:** (user) Maryland's outcome is the MLDS Center's **Within One Year** college enrollment (full- or part-time, degree- or non-degree-seeking, within one year of graduation; MHEC for Maryland institutions, NSC for out-of-state and other private colleges), classes 2008-2024, as enrolled ÷ graduates from the published counts (`window` = `md_within_1yr`). The Immediate rate (full-time, degree-seeking, fall) and the two-year rate are kept as `pct_enrolled_immediate` and `pct_enrolled_within_2yr`. Data from the MLDS download zip (scripted); schools are matched to CCD by school system and name, with five hand aliases (`state_files.MD_ALIASES`).
- **Alternatives considered:** Immediate enrollment (stricter than any other state's measure; dips in classes 2013 and 2015; more suppression); the MSDE Report Card (rejects scripted requests).
- **Reason:** Counts all colleges and any enrollment within 12 months, like Illinois's 12-month rate; smooth over time; class 2024 included.
- **Affects:** `07_build_state_outcomes.py`, `state_files.md_college_enrollment`, codebook. MHEC collected only fall enrollment from 2008-09 to 2012-13, which may slightly undercount classes 2009-2013.
- **Related issue:**

## 2026-11-01: Alabama outcome is ACHE in-state public fall enrollment

- **Decision:** (user) Alabama's college-going outcome is the share of each public high school's graduates enrolled at an **Alabama public** 2- or 4-year college in the fall after graduation, from ACHE's High School Graduate Reports (classes 2012-2024; `window` = `al_fall_public_instate`). Counts of graduates and enrollees are kept.
- **Alternatives considered:** PARCA's all-college (NSC) rates by school (dashboard downloads disabled; no class 2023; not scriptable); ACHE's NSC college-going PDFs (only class 2025 online); combining sources by year (rejected: the definition would change within the panel).
- **Reason:** The only Alabama source that covers every needed class (dose 2019-2020, reference 2021, post 2022-2024) with one definition, published as counts, and downloadable by script.
- **Affects:** `07_build_state_outcomes.py`, `state_files.al_ache_enrollment`. Limitations are listed in `docs/source-notes.md` (Alabama): it excludes private and out-of-state colleges (about one-fifth of enrollment), so substitution could bias the effect in either direction, and it is narrower than Louisiana's and Illinois's outcomes.
- **Related issue:**

## 2026-11-01: Illinois outcome is the 12-month enrollment rate

- **Decision:** (user) Illinois's college-going outcome (`pct_enrolled` in `state_outcomes.parquet`) is ISBE's **12-month** rate (first enrollment by Sep 30 of the year after graduation); the 16-month rate is kept as `pct_enrolled_16m`.
- **Alternatives considered:** The 16-month rate (by Jan 31, two years after graduation).
- **Reason:** Closest to Louisiana's first-fall measure; the 16-month rate is a robustness check.
- **Affects:** `07_build_state_outcomes.py` (`window` = `il_12m_sep30`). Breakdown columns are named by their base (`pct_of_grads_*` for Illinois, `pct_of_enrolled_*` for Louisiana), since the two states use different bases.
- **Related issue:**

## 2026-11-01: Illinois report card year Y reports the postsecondary enrollment of class Y-2

- **Decision:** Illinois's postsecondary enrollment in report card year Y is assigned to the **class of Y-2** for every report card year 2015-2026 (classes 2013-2024), `state_files.IL_CLASS_OF`. Illinois school codes are compared in a 13-digit form (RCDTS without the 2-digit type code; `state_files.il_code`).
- **Alternatives considered:** Following each year's glossary literally (2015: class 2013; 2016 and 2017: class 2014; 2018-2021: "three years prior"; 2022 on: "two years prior"), which would repeat class 2014 and skip class 2019.
- **Reason:** ISBE's current business rules give the two-year rule with an example (2023-24 report card = 2021-22 graduates). In the data, consecutive report cards never repeat a class, and school-level changes in the enrollment rate correlate with changes in FAFSA completion at a two-year lag (+0.23 to +0.47, report cards 2018-2026) but not at three years (-0.03 to -0.20). The 2022 glossary's note that it "updated the definition ... to indicate 'two years prior'" fits a corrected wording, not a changed method.
- **Affects:** `state_files.py` (Illinois reader), the future Illinois outcome in `07_build_state_outcomes.py`. The 12-month measure has a level shift at class 2016 (2018 report card), documented in `docs/source-notes.md`.
- **Related issue:**

## 2026-11-01: College-going outcome: published enrollment rate; Louisiana adds Deneault's penroll

- **Decision:** (user) The college-going outcome for every state is the **enrollment rate as the state publishes it** (definitions by state in `docs/source-notes.md`). For Louisiana, to replicate Deneault (2023), the outcome also includes her **`penroll` = (fall enrollment rate) × (4-year cohort graduation rate)**, with bounded values coded her way (`>99` → 99.5, `<1` → 0.5, `>95` → 97.5, `<5` → 2.5; `state_files.midpoint`). Published bounds are kept as numbers with their direction in `*_bound` columns, so the coding for other states can be chosen later. Built in the new step `07_build_state_outcomes.py` (`data/derived/state_outcomes.parquet`), with readers in `state_files.py` shared with the content review.
- **Alternatives considered:** `penroll` for every state (rejected: not every state is known to publish cohort graduation rates or 9th-grade cohort counts); bounds at the bound itself for Louisiana (rejected for the replication: Deneault codes them at the midpoint).
- **Reason:** One outcome definable in every state, plus an exact replication of the paper's outcome in Louisiana.
- **Affects:** `07_build_state_outcomes.py`, `state_files.py`, `run.sh`, codebook. Louisiana's graduation rates for classes 2014-2015 come from the next year's School Performance Score files, as in Deneault's README. Bound coding for the other states is still open. The bound coding is in Deneault's code (`cleaningenroll_aejep.do`, `cleaninggrad_aejep.do`), not in her README; the paper text is not in the repository, so whether it states the rule is unchecked.
- **Related issue:**

## 2026-11-01: Link state files by state school code; CCD grade-12 enrollment stays the baseline denominator

- **Decision:** (user) (1) State data files are linked to the panel by the state's own school code: CCD's `ST_SCHID` (now kept as `st_schid` in `ccd_school_panel.parquet`), last "-" segment, matched in the same class year, else the same code in any CCD year (most recent). (2) The FAFSA completion denominator stays **CCD grade-12 enrollment** as the baseline specification. State high school graduate counts are a possible second specification, to be decided only after the content review shows whether every state has them; no change for now.
- **Alternatives considered:** Matching state files by school name (kept only as a fallback for files without codes, e.g. New Hampshire's Cohort Counts By School); replacing the CCD denominator with Louisiana's graduate counts now (rejected: the user wants one denominator defined the same way in every state as the baseline).
- **Reason:** CCD writes the state code three ways across years (`001005`, `001-001005`, `LA-001-001005` for Louisiana) but its last segment is the state's code, and states keep a school's code when CCD's changes (e.g. New Orleans charters moving between districts). In Louisiana this links 97-100% of school rows and covers 98-99.7% of panel schools.
- **Affects:** `04_build_ccd_school_panel.py` (new column `st_schid`; estimates unchanged), `state_files.py` (`link()`), the future cleaning step for state files.
- **Related issue:**

## 2026-11-01: New Hampshire data by manual browser export

- **Decision:** (user request) Export New Hampshire's iPlatform reports Cohort Counts By School and Completers By Status By School, classes 2012-2025, and the iExplore Post-secondary Enrollment Rate by school, 2016-2025, by hand in the user's Chrome, and register the 32 files as manual sources (`Source.manual`). The iExplore rate (enrollment in a 2- or 4-year institution within the year after graduation) is New Hampshire's college-going measure; Completers By Status (reported plans) is kept as a secondary measure only. The downloader never fetches manual sources; it records their hashes in the manifest, reports any missing file with its export steps, and `--check` flags any that changed. ED Data Express school-level graduation files were also attempted the same way but the site's download tool failed with server errors; not obtained.
- **Alternatives considered:** Browser-style scripted requests to my.doe.nh.gov (rejected: the site returns 403 to scripts, and getting around that would defeat the publisher's block); a data request to NH DOE (slower; still possible if a verified college-enrollment measure is needed); federal EDFacts only (graduation through class 2020 only, and no college-going measure).
- **Reason:** These reports are New Hampshire's only school-level source of graduate counts after class 2020 and of college-going. A documented, hash-checked manual step keeps the rebuild reproducible except for this one step.
- **Affects:** `data/raw/NH/manual/`, `sources.new_hampshire()`, `00_download_raw_data.py` (manual handling, `--check`), the catalog (`manual` status). The project is no longer fully one-command for New Hampshire; confirm with the instructor that a documented manual step is acceptable. The iExplore rate has no counts and its year-to-class mapping is still to be verified.
- **Related issue:**

## 2026-11-01: Colorado sources scripted; Maryland and New Hampshire pending

- **Decision:** (user request) Script Colorado now, though its analysis stays deferred: CDE school-level graduation/completion workbooks (classes 2019-2025) and matriculation workbooks (classes 2019-2025, graduates and college enrollees by school). Classes 2015-2018 graduation come from EDFacts ACGR. CDE links are opaque IDs, so a new builder `resolved()` names and selects files by the server's Content-Disposition filename (one HEAD request per link). Maryland (MLDS Center dashboard) and New Hampshire (iPlatform) are not scripted yet.
- **Alternatives considered:** Naming CDE files by link text (rejected: archive links repeat the same text across years). Sending browser-style requests to the Maryland Report Card and New Hampshire sites, which reject scripts with 403/500 (rejected: that would get around the publishers' blocks on automated access).
- **Reason:** One-command rebuild; Colorado's files are posted openly. Colorado's matriculation files give both the graduate count (DN) and college enrollment (NM), so no separate graduate file is needed for those classes.
- **Affects:** `data/raw/CO/`, `sources.CATALOG`. Open: how to get Maryland's MLDS per-school 2023-24 exports (needs a headless browser, since the dashboard builds its reports with JavaScript) and New Hampshire's iPlatform exports (site blocks scripts).
- **Related issue:**

## 2026-11-01: ACT/SAT is not a control in the main specification

- **Decision:** (user agreed) The main first-stage and reduced-form specification in every state uses race shares, total enrollment, enrollment squared, and FRL, with **no ACT/SAT control**. (1) The Louisiana replication adds LDOE's school mean ACT composite by graduating class (`LA/ldoe_act`, 2012-2025, already downloaded), and is reported with and without it, to match Deneault's `act` control. (2) School ability enters only as a robustness check: a pre-policy baseline measure interacted with class fixed effects, which allows high- and low-ability schools to trend differently. (3) The baseline measure common to all states is EDFacts high school % proficient in reading and math by school (Urban republication, school years 2014-15 to 2018-19, new group `ASSESS`), averaged over each state's pre-policy years.
- **Alternatives considered:** A state test-score control in every state (rejected: coverage and meaning differ by state. Indiana reports % at the SAT benchmark for classes 2023-2027 only, Oklahoma reports mean ACT from 2018, California stopped after 2022, Alabama's was not found, and several states switched between ACT and SAT or began universal testing in the window, so the control would change the sample more than the estimate). A yearly EDFacts proficiency control (rejected: Urban's school data end in 2018-19 except 2020).
- **Reason:** School fixed effects absorb stable ability differences; within-school year-to-year changes in test scores are small and mostly noise. A graduating-cohort best score (e.g. ACT after retakes) may itself respond to the mandate, which makes it a bad control. The relevant worry, that high-dose (low baseline completion) schools are lower-achieving and trend differently, is tested directly by baseline ability × class FE. Changes in a state's test show up as statewide shifts that class FE absorb, because the model is estimated state by state.
- **Affects:** `06_first_stage.py` and the reduced form (no change to the main controls yet; the replication ACT and the robustness check still need to be built); `data/raw/US/edfacts_assess_urban/`; `config.STATE_FIPS`. ACT/SAT files already downloaded for other states stay in `data/raw/`, unused.
- **Related issue:**

## 2026-11-01: Indiana graduation rates and SAT from the IDOE archive

- **Decision:** (user request) Also scrape IDOE's Data Reports Archive (`idoe_archive`) with the same filename pattern as the Data Center, adding graduation-rate workbooks for classes 2014-2024 and grade-11 SAT school files for test years 2022-2025. Map SAT test year Y to the class of Y+1, as the files' own notes say.
- **Alternatives considered:** Treating the SAT as a grade-12 measure of the same class year (rejected: it would mismatch the class by one year).
- **Reason:** Fills the Indiana graduation-rate gap (it was 2023 and 2025 only). Indiana's SAT is a universal junior test, so unlike a self-selected senior or graduate-cohort score, it covers all juniors on one sitting and is fixed before senior-year FAFSA outreach.
- **Affects:** `data/raw/IN/idoe_archive/`, the catalog. SAT covers only classes 2023-2027 (the FAFSA requirement starts with the class of 2024) and reports % at benchmark, not mean scores, so it cannot serve as a panel-wide control like Deneault's average ACT.
- **Related issue:**

## 2026-10-31: State data sources (graduates, graduation rates, ACT/SAT, college enrollment)

- **Decision:** (user request) Download each state's school-level graduates, graduation rates, ACT/SAT, and college enrollment from the state education agency or higher-education agency, with every file fetched by `code/00_download_raw_data.py` (one-click). New groups: `AL`, `TX`, `CA`, `IN`, `OK`, `NE`, `NY`, `PA`, `CT`, and `FED` (CRDC, EDGE neighborhood poverty, IPEDS directory). Student/teacher ratio, grade-9 cohort, race shares, and FRL come from CCD for every state (already downloaded); state files are kept where they add graduate counts or fill CCD gaps. `sources.py` builds most groups with two shared helpers (`scraped`, `listed`); Alabama's form-based app and Nebraska's API use a `fetch` function on the Source. `sources.CATALOG` records every state x measure with its status and is written to `output/tables/state_data_sources.csv`. Each downloaded file must match its type (binary signature for .xlsx/.zip/.xls/.pdf; no HTML page for .csv/.txt/.json) or it counts as a failed download; `--check` re-checks files already downloaded.
- **Alternatives considered:** Manual exports for dashboards (rejected: the project must rebuild with one command); third-party compilations such as PARCA or Urban where the state publishes the data itself (used only for EDFacts ACGR, which ed.gov blocks).
- **Reason:** Graduate counts are Deneault's FCR denominator, and college enrollment is the reduced-form outcome; both must come from state sources.
- **Affects:** `data/raw/<state>/` and the manifest. Not yet scripted: Maryland (Report Card download API rejects scripted requests) and New Hampshire (site returns 403 to scripts); Colorado is deferred with its analysis. Gaps are listed in the catalog (e.g. Texas college enrollment before fall 2019, California ACGR before 2017, Alabama college-going before the newest class).
- **Related issue:**

## 2026-10-31: Fewer code files

- **Decision:** (user request) `school_ids.py` merged into `matching.py` (removing a duplicate `names_match` in `03_build_fsa_school_panel.py`); `http_utils.py` merged into `sources.py`; `04_policy_timing.py` folded into the analysis-panel script, which still writes `policy_timing.parquet`. Scripts renumbered: `04_build_ccd_school_panel.py`, `05_build_analysis_panel.py`, `06_first_stage.py`.
- **Alternatives considered:** Merging steps 1–3 or the analysis panel with the first stage (kept separate: each writes a Parquet file that is checked on its own, and the analysis panel will also feed the event study and reduced form).
- **Reason:** Fewer files to read; the merged helpers and timing step were small and had one or two users each.
- **Affects:** File names only; outputs unchanged. Test references to the renamed scripts were updated (assertions unchanged).
- **Related issue:**

## 2026-10-27: First-stage sample, controls, and specification

- **Decision:** (user decisions 2026-10-27) Main sample: treated public schools with post-mandate classes, in the estimation window (e = −4 … +1, or to e = 0 with one post class; for the 2025 states the window ends at 2025 because CCD grade-12 counts for 2026 are not yet released), passing the project-design screens (always a regular school, never fully/primarily virtual, Deneault's 9th-grade cohort and student/teacher-ratio screens, both dose classes observed, balanced over the window), with complete controls in every window class. Louisiana is also run with Deneault's screens (special education dropped instead of the regular-school screen) for comparison with her estimate. "<5" completions are missing (as Deneault); the completion rate is capped at 1 (as Deneault). Controls: shares white, Black, Hispanic, Asian; total enrollment and its square; free/reduced-lunch share (added to Deneault's controls; a version without it is also reported). Deneault's school ACT control is not yet available. Colorado is left out (`EXCLUDE_STATES` in `code/06_first_stage.py`) until its covered-vs-uncovered design is decided. Model: `fcr ~ dose × post + controls | school + class`, weighted by Deneault's weight, standard errors clustered by school (CRV1, pyfixest).
- **Alternatives considered:** Deneault's screens everywhere (keeps more alternative schools in CA and TX); imputing "<5" (kept as a later sensitivity check); no cap.
- **Reason:** Follow Deneault's specification as closely as the data allow, with the project design's stricter school screens.
- **Affects:** All first-stage estimates (`output/tables/first_stage_by_state.csv`). Estimates are preliminary: CCD grade-12 enrollment is the denominator until state graduate counts are added. Illinois reported no FRL to CCD for 2020-21 (its first covered class), so Illinois's main specification omits the FRL share (`NO_FRL_STATES`; user decision 2026-10-27). To revisit: add FRL from the Illinois Report Card when state data are added (step 4) and restore Illinois's FRL control.
- **Related issue:**

## 2026-10-27: CCD school panel

- **Decision:** `code/04_build_ccd_school_panel.py` builds one row per open public school and school year (2014-15 to 2024-25) in the 15 study states from CCD Directory, School Characteristics, Membership, Lunch, and Staff files plus EDGE locale, keyed by the same `school_id` as the FSA panel (ID-chaining code moved to `stable_ids` in `code/matching.py`). Files are streamed with the system `unzip -p` because several Membership zips use Deflate64; the two nested Membership zips (2017-18, 2021-22) are copied to a temporary directory that is deleted afterwards. `data/raw/` is never changed. Closed, inactive, and future schools are dropped each year (they would otherwise duplicate a school whose ID just changed). No sample restrictions beyond that; school-type screens come later.
- **Alternatives considered:** Extracting the zips into `data/raw/` (rejected: raw files must stay unchanged); a Python Deflate64 package (unnecessary given `unzip`).
- **Reason:** Provides the grade-12 fallback denominator, Deneault's weight inputs (enrollment, grades offered), sample screens (school type, charter, virtual), and controls (race, FRL, teachers, locale) for every study state.
- **Affects:** Analysis panel and first stage. Direct certification exists only from 2016-17 and is often unreported; Title I is not published from 2022-23.
- **Related issue:**

## 2026-10-27: Policy timing table

- **Decision:** Policy dates are entered by hand in `data/policy/state_mandates.csv` (from the user's state audit, EdTrust's Feb 2025 scan of universal FAFSA policies, statutes, and PDE for Pennsylvania) and `data/policy/co_grantee_schools.csv` (CDHE Fund My Future reports). `code/05_build_analysis_panel.py` derives each unit's reference class (e = −1) and dose window (e = −3, −2), skipping partial-rollout classes, and its post classes. Louisiana's last covered class is 2024 (BESE repealed the requirement in March 2024 starting with the class of 2025). Colorado is treated school by school: 11 grantee high schools, first covered class 2023 (fall 2022 launch) or 2024 (fall 2023 launch); Westminster's two schools launched in spring 2023, so 2023 is a partial-rollout class and 2024 their first covered class.
- **Alternatives considered:** Colorado first covered class 2022 (EdTrust; rejected because CDHE reports no grantee program before fall 2022); treating Westminster's class of 2023 as covered (kept as a sensitivity check).
- **Reason:** Derived timing must be reproducible from documented inputs, and match the design's rule (dose e = −3, −2; reference e = −1; partial-rollout classes excluded).
- **Affects:** Dose, reference, and post classes in every state. Flags: the COVID classes fall in the dose or reference window for IL, AL, TX, MD, CA, IN, NH, and all Colorado schools; the class of 2024 is the reference class for NE, OK, NY, NJ and a dose class for CT and PA; CT and PA's reference class (2026) is FSA's preliminary class. Colorado's design differs from the others (covered vs. uncovered schools rather than dose within all-covered schools) and needs its own decision before estimation. CHSC GES and Aspire Online first appear in FSA in 2023, so they have no dose classes.
- **Related issue:**

## 2026-10-27: School-level FSA panel and stable school IDs

- **Decision:** `code/03_build_fsa_school_panel.py` sums FSA records by a stable `school_id` and class. Public schools whose NCES ID changed (new district) are joined when the IDs share state and 5-digit NCES school number, are never open in CCD in the same year, and any of their CCD names match; `school_id` is the newest ID. Unlinked second listings of a school (same class, city, candidate code, matching name) are added to it; network-level records are not. A "<5" cell adds nothing to a sum and sets a flag. Only the 15 study states are kept (user decision, 2026-10-27); `fsa_fafsa_hs.parquet` and `fsa_school_codes.parquet` still cover every state, so never-adopting comparison states (for the planned triple difference and placebo runs) can be added back by changing `STUDY_STATES` in the script. All sectors are kept.
- **Alternatives considered:** Using NCES IDs as they are (splits schools like Granada Hills Charter, CA, and KIPP Renaissance / Frederick A. Douglass, LA, across IDs); using CCD's state school ID (its format changes in 2016-17); dropping private/charter schools here (deferred to the analysis panel, where CCD and PSS identify them).
- **Reason:** The first stage needs one continuous series per school across the dose, reference, and post classes. 514 FSA codes are joined to a newer ID of the same school.
- **Affects:** All school-level analysis. Comparing every name an ID has had (not just its latest) was needed to join renamed schools.
- **Related issue:**

## 2026-10-27: Link pre-2021 FSA records to FSA's own School Codes before using CCD

- **Decision:** `code/02_link_fsa_codes.py` gives each FSA record from the classes of 2015–2020 the School Code that FSA attaches to the same school from 2021 on. Matching runs in tiers: exact state+name+city, then normalized name+city, then normalized name within the state. A name-only link is rejected when its code is already taken in that class by a better link or is contested. Keys that lead to several codes are not linked. The CCD directory is used only for records still unlinked.
- **Alternatives considered:** Matching every pre-2021 record directly to the CCD directory by name and city; accepting all name-only links.
- **Reason:** FSA spells a school's name the same way across years far more often than FSA and CCD agree. Exact matching alone links 71–94% of 2015–2020 records in the study states. Accepting all name-only links produced false matches between schools with common names in different cities (e.g. ST PAUL LUTHERAN HIGH SCHOOL, Concordia vs. Farmington MO), so those are now rejected (520 records).
- **Affects:** NCES matching for the classes of 2015–2020. FSA-to-FSA linking alone covers 89–96% of records and 93–98% of completions in the study states.
- **Update (same day):** records still without a code are matched in the same script to the CCD directory for the class's senior year (grade-12 schools only: exact normalized name and city, then FSA name as prefix of the CCD name in the same city, then unique name in the state), and finally to the code that the same name and city got in another pre-2021 class. The same taken-or-contested rejection applies. After this, 97.3–99.8% of 2015–2020 completions in the study states are linked. What remains unlinked is mixed, not mostly private. A check on 2026-10-27 of the 4,334 unlinked 2015–2020 records in the study states (75,425 completions) found: 38% of those completions are ambiguous or rejected matches; 16% have private-sounding names and no CCD match (CCD covers public schools only); 6% are CCD schools excluded by the grade-12 filter (highest grade missing, not applicable, or below 12); and 39% have no CCD match and generic names. That last group includes public charter and online schools whose FSA and CCD names differ (e.g. Noble Street campuses such as Pritzker College Prep in Chicago, EPIC One on One Charter in OK, Agora Cyber Charter in PA), network-level records (Noble Street Charter Schools, Chicago), and private online schools (Penn Foster HS). Possible next steps: relax the grade filter, add fuzzy name matching within city, and link private schools to the NCES Private School Survey.
- **Update 2 (same day):** all three were done. (1) The directory grade filter now drops only schools whose highest grade is known to be below 12. (2) A fuzzy step was added within the same state and city: after removing generic words and the city's own name, every word of the shorter name must appear in the longer one (5+ letter words may be slightly misspelled if of similar length), covering at least half of the longer name's distinctive letters, with a single passing code. A first, looser version (rapidfuzz token-set/token-sort scores) produced false matches such as LAFAYETTE CHRISTIAN ACADEMY → UPPER LAFAYETTE ACADEMY and CENTRAL HIGH WEST CAMPUS → EAST CAMPUS; these are now tests. (3) The NCES Private School Survey (biennial, 2013-14 to 2023-24) was added to `sources.py` and downloaded; its PPIN is the 8-character code FSA uses for private schools, and the same four steps are run against it after CCD. Result: 98.3% (IL) to 99.98% (NH) of 2015–2020 completions in the study states are linked; 0.4–5.2% of records remain unlinked, ambiguous, or rejected. Fuzzy links cover 0.12% of completions. Known remaining gaps: network-level records (Noble Street Charter Schools, Chicago, 2016–2020), campus names too short to fuzzy-match (UIC College Prep), and a school listed twice in one year under two spellings, where the second listing is rejected because the first took the code (e.g. AGORA CYBER CHARTER SCHOOL vs AGORA CYBER CS, PA).
- **Update 3 (same day):** FSA-to-FSA links are now checked against each class's senior-year CCD/PSS before directory matching. Reason: FSA's 2021+ codes describe current schools, so old names can inherit another school's code (Dothan High School, AL, was linked for 2015–2019 to Northview's ID, which the merged school took in 2019; Northview then could not be linked). 23 records are relinked (`ccd_relinked`) and 2,823 ambiguous records are resolved to the only candidate code present that year (`ambiguous_resolved`; 98.6% of these carry the same or a matching name that year, the rest are mostly renamed schools). Rejected and ambiguous records now keep the code(s) they were offered (`candidate_code`, `candidate_tier`), so the school-panel step can decide whether to add duplicate listings into the school they duplicate.
- **Related issue:**

## 2026-10-27: FSA panel construction (suppression, placeholders, source file per class)

- **Decision:** In `fsa_fafsa_hs.parquet`, "<5" counts are stored as missing with a `*_lt5` flag and not imputed. All-zero school codes are set to missing. Each class is taken from the newest file with its fixed prior-cycle columns; the newest class uses the June 30 running count, flagged `preliminary`. Rows are kept for all states and territories, and nothing is dropped at this stage.
- **Alternatives considered:** Imputing "<5" as 0, 2.5 or 4 (deferred to the analysis step, where the choice can be varied as a sensitivity); keeping only the 15 study states (never-adopting states are needed for the triple difference).
- **Reason:** Keep the derived file a faithful reshaping of the source, and make imputation and sample choices explicit later.
- **Affects:** `code/01_clean_fsa.py`; FCR numerator; later NCES matching (multi-site virtual schools share one school code across cities).
- **Related issue:**

## 2026-10-27: Download December FSA FAFSA-completion snapshots, plus the newest June

- **Decision:** `code/sources.py` downloads the FSA high-school archives dated December 31 (2016–2025) and the newest June 30 archive. A class's FCR numerator will come from the fixed prior-cycle "Through June" column in a later December file. "(18 year olds)" files are excluded so every file uses the age-19 cutoff.
- **Alternatives considered:** All monthly snapshots (original behavior, 132 files); June 30 snapshots only (adopted and then reversed the same day).
- **Reason:** Deneault's `cleaningFAFSA_aejep.do` takes the classes of 2015–2018 from the prior-cycle "Through June" column of the Dec 31 2016–2019 files, and uses the June 30 2020 file only for the newest classes (labelled "prelim"). The prior-cycle columns are FSA's fixed 9-month counts for the finished cycle, while a June 30 snapshot is a running count. The December files also carry the 15-month ("Through December") count. The Dec 31 file of year Y+1 holds the class of Y (Dec 2016 → class of 2015, Dec 2025 → class of 2024, checked from header rows). The newest June file (June 30 2026) holds the class of 2025 in its fixed prior-cycle column and a preliminary count for the class of 2026.
- **Affects:** `code/sources.py` (`fsa_fafsa_completion`); FCR construction. The size of the gap between June 30 snapshot and final counts has not been measured.
- **Related issue:**

## YYYY-MM-DD: <short title>

- **Decision:**
- **Alternatives considered:**
- **Reason:**
- **Affects:** <scripts, variables, or results>
- **Related issue:**
