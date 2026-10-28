# Codebook

One entry per analysis dataset in `data/derived/`. Record variable definitions, units, missing-value codes, and observation keys.

## `fsa_fafsa_hs.parquet`

- **Produced by:** `code/01_clean_fsa.py`
- **Unit of observation:** FSA school record × graduating class, all states and territories. Records are not yet matched to NCES IDs. Multi-site virtual schools appear once per city under one school code.
- **Key (unique):** `class_year`, `source_file`, `row_in_file`
- **Source per class:** the newest file with the fixed prior-cycle columns for that class (Dec 31 of the next year; the newest June 30 file for the latest finished class). The newest class, which has no fixed columns yet, comes from the June 30 running count and has `kind = "preliminary"`.

| Variable | Type | Units | Definition | Source | Missing-value codes |
|---|---|---|---|---|---|
| `school_code` | string | — | FSA School Code: 12 characters = NCES public school ID; 8 = NCES private school (PSS) ID; 9 with "FN" = no NCES ID. In files from Dec 2022 on (classes 2021+). | FSA "School Code" | Null before class 2021, or when FSA gives an all-zero placeholder |
| `name` | string | — | School name as published, whitespace trimmed | FSA "Name" | Null for 6 records |
| `city` | string | — | School city | FSA "City" | Null for some territory and foreign records |
| `state` | string | — | Two-letter state, territory, or military code | FSA "State" | — |
| `row_in_file` | int | — | Row number within the source file (0-based, after the header) | derived | — |
| `class_year` | int | year | Graduating class (spring of that year), from the year in the column header | derived | — |
| `kind` | string | — | `final` = FSA's fixed prior-cycle columns; `preliminary` = June 30 running count for the current cycle | derived | — |
| `submitted_jun` | Int64 | applications | FAFSAs submitted by students at the school through June 30 of `class_year` | "Applications Submitted Jun YYYY" (or "Jun30 YYYY" if preliminary) | Null if suppressed (<5) |
| `completed_jun` | Int64 | applications | FAFSAs completed through June 30 of `class_year`; the FCR numerator | "Applications Complete Jun YYYY" (or "Jun30 YYYY" if preliminary) | Null if suppressed (<5) |
| `submitted_dec` | Int64 | applications | FAFSAs submitted through December 31 of `class_year` (15-month count) | "Applications Submitted Dec YYYY" | Null if suppressed, or if `kind = "preliminary"` |
| `completed_dec` | Int64 | applications | FAFSAs completed through December 31 of `class_year` | "Applications Complete Dec YYYY" | Null if suppressed, or if `kind = "preliminary"` |
| `*_lt5` | bool | — | True if the matching count was published as "<5" | derived | — |
| `snapshot_date` | date | — | "As of" date of the source file | file name | — |
| `source_file` | string | — | Local file name in `data/raw/US/fsa_fafsa_completion/` | — | — |

Known quirks (reported by the script, not corrected): in about 2,000 records the December count is below the June count, by about 1.4 applications on average, which reflects FSA revisions. A dozen state+name+city combinations repeat within a class.

## `fsa_school_codes.parquet`

- **Produced by:** `code/02_link_fsa_codes.py`
- **Unit of observation:** FSA school record × graduating class (same rows as `fsa_fafsa_hs.parquet`; join on the key).
- **Key (unique):** `class_year`, `source_file`, `row_in_file`
- **Purpose:** gives records from before the class of 2021, which have no School Code, a code: first the code FSA uses for the same school from 2021 on; then, for records still without one, the NCES ID from the CCD school directory of the class's senior year (public schools), then the PSS ID from the Private School Survey waves around that year (private schools); finally the code the same name and city received in another pre-2021 class. Codes are FSA's own format: 12-character NCES IDs for public schools, 8-character PSS IDs for private schools.

| Variable | Type | Units | Definition | Source | Missing-value codes |
|---|---|---|---|---|---|
| `class_year`, `source_file`, `row_in_file` | — | — | Key, as in `fsa_fafsa_hs.parquet` | — | — |
| `state`, `name`, `city` | string | — | As published by FSA | `fsa_fafsa_hs.parquet` | — |
| `school_code` | string | — | FSA's own School Code (classes 2021+) | `fsa_fafsa_hs.parquet` | Null before class 2021 |
| `code_linked` | string | — | `school_code` if present; otherwise the code linked from a 2021+ FSA record of the same school, the CCD NCES ID, or the PSS ID | derived | Null if not linked |
| `link_tier` | string | — | `fsa_code` (FSA's own code); `exact` (same state, name, city); `normalized` (same state and normalized name and city); `name_only` (same state and normalized name, different city); `name_only_rejected` (name-only candidate whose code was already taken by an exact/normalized link in that class, or contested by several records); `ccd_relinked` (an FSA-tier public code that the class's senior-year CCD lists under a clearly different name, replaced by the CCD school with the same name and city that year); `ambiguous_resolved` (a name+city that fits several FSA codes, linked to the only one present in that year's CCD or PSS); `ccd_exact` (CCD school, same state and normalized name and city, physical or mailing); `ccd_prefix` (CCD school in the same state and city whose normalized name starts with the FSA name, FSA name at least 12 characters); `ccd_name_only` (CCD school with the same normalized name in the state, different city); `ccd_fuzzy` (CCD school in the same state and city whose name agrees on distinctive words: after removing generic words and the city's own name, every word of the shorter name appears in the longer one, allowing slight misspellings of 5+ letter words of similar length, and these words make up at least half of the longer name's distinctive letters; only one code may pass); `pss_exact`, `pss_prefix`, `pss_name_only`, `pss_fuzzy` (the same four steps against the Private School Survey); `other_year` (same state and normalized name and city as linked records of other pre-2021 classes, all with one code); `ambiguous` (the key leads to several codes); `unlinked` (no match). CCD and PSS candidates exclude only schools whose highest grade is known to be below 12 (CCD `GSHI` PK–11; PSS `HIGR` 2–16); missing, not-applicable, and ungraded spans are kept. PSS waves used for class Y are those starting in Y−2 through Y (e.g. class of 2015: 2013-14 and 2015-16). Tiers `name_only` and later are rejected if the code is already taken in that class by another linked record or is contested. | derived | — |
| `n_candidate_codes` | Int64 | codes | Number of distinct codes the record's best-matching FSA key leads to | derived | Null if no FSA key matched |
| `ccd_name`, `ccd_city` | string | — | Name and city of the CCD school a `ccd_*` link matched, for checking | CCD directory (`ccd_sch_029_*`) | Null unless `link_tier` starts with `ccd_` |
| `candidate_code` | string | — | For records left `name_only_rejected`, `ambiguous`, or `unlinked`: the code(s) they were offered, several joined by `|` (first offer kept) | derived | Null if never offered a code, or if linked |
| `candidate_tier` | string | — | Tier that offered `candidate_code` | derived | Null with `candidate_code` |
| `pss_name`, `pss_city` | string | — | Name and city of the PSS school a `pss_*` link matched, for checking | PSS public-use file (`PINST`, `PL_CIT`/`PCITY`) | Null unless `link_tier` starts with `pss_` |

Normalization: uppercase; "&" → AND; punctuation removed; whole-word abbreviations expanded (SCH, SCHL → SCHOOL; HS, H S → HIGH SCHOOL; ACAD → ACADEMY; ST → SAINT; MT → MOUNT; and others listed in the script).

Known patterns (checked 2026-10-27): one code can cover several records in a class. These are multi-site or virtual schools listed once per city, or the same school listed twice in one file under two spellings (e.g. ST LOUIS / SAINT LOUIS). Counts for such records should be summed when collapsing to the code. Some schools' NCES IDs change over time (e.g. Granada Hills Charter, CA: 062271003050 in 2018, 060220603050 from 2021, apparently when it became its own district), so a code is not yet a stable school identifier across years. FSA's 2021+ codes describe schools as they are now, so an old name can carry another school's code; the year check (`ccd_relinked`, `ambiguous_resolved`) corrects this using each year's directory (e.g. Dothan High School, AL: 010123000445 through the class of 2019; after the 2019 merger with Northview the name uses Northview's ID 010123001501). About 1.4% of `ambiguous_resolved` links use a code whose name that year differs from FSA's, mostly renamed schools (e.g. Frederick A. Douglass HS = KIPP Renaissance, New Orleans). Fuzzy links (`ccd_fuzzy`, `pss_fuzzy`) are the least certain; in the study states they cover 0.09% and 0.03% of 2015–2020 completions.

## `fsa_school_panel.parquet`

- **Produced by:** `code/03_build_fsa_school_panel.py`
- **Unit of observation:** school × graduating class in the 15 study states (LA, IL, AL, TX, CO, MD, CA, IN, NH, NE, OK, NY, NJ, CT, PA), all sectors, classes 2015–2026.
- **Key (unique):** `school_id`, `class_year`
- **Built from:** `fsa_fafsa_hs.parquet` records with a code in `fsa_school_codes.parquet`, summed by school and class. Records in other states are left out here (the earlier FSA files keep every state). In the study states, records without a code are left out (2,111 records, 29,423 of 13.5 million completions: unlinked, ambiguous, rejected, and 30 network-level records). Unlinked second listings of a linked school (same class, city, candidate code, and matching name) are added to that school; network-level records (names ending in SCHOOLS or containing NETWORK) are not.

| Variable | Type | Units | Definition | Source | Missing-value codes |
|---|---|---|---|---|---|
| `school_id` | string | — | Stable school identifier: the most recent NCES ID for public schools (IDs in one state sharing NCES's 5-digit school number, never open in CCD in the same year, with matching names, are one school); the PSS ID for private schools; FSA's code otherwise | derived from FSA codes and CCD directories | — |
| `class_year` | int | year | Graduating class | `fsa_fafsa_hs.parquet` | — |
| `state`, `name`, `city` | string | — | From the school's largest FSA record that class | FSA | `city` null for some territory records |
| `sector` | string | — | `public` (12-character NCES ID), `private` (PSS ID), `no_nces_id` (FSA "FN" code) | derived | — |
| `submitted_jun`, `completed_jun`, `submitted_dec`, `completed_dec` | Int64 | applications | Sum over the school's records of the published counts (see `fsa_fafsa_hs.parquet`) | FSA | Null if every component is "<5" (or the column does not exist, e.g. December counts for a preliminary class) |
| `*_lt5` | bool | — | True if any component record's count was "<5". With one record the count is then null; with several, the sum is a lower bound | derived | — |
| `n_records` | int | records | FSA records summed into the row | derived | — |
| `codes` | string | — | Distinct linked codes of those records, joined by `|` | `fsa_school_codes.parquet` | — |
| `assign_rules` | string | — | Distinct `link_tier` values of those records, plus `duplicate_listing` for added second listings, joined by `|` | derived | — |
| `kind`, `snapshot_date`, `source_file` | — | — | As in `fsa_fafsa_hs.parquet` (from the largest record) | FSA | — |

Known gaps: a record whose name, once generic words and its own city are set aside, has no words left cannot be fuzzy-matched (e.g. GRANADA HILLS CHARTER HIGH SCHOOL, Granada Hills, class of 2019, is missing). Some multi-site charters (e.g. Inspire, Options for Youth in CA) are one `school_id` because CCD chains their IDs.

## Policy inputs: `data/policy/state_mandates.csv` and `data/policy/co_grantee_schools.csv`

Hand-entered from statutes and agency reports (sources in each row and in `docs/source-notes.md`); tracked in Git. Read by `code/04_policy_timing.py`.

`state_mandates.csv`, one row per study state:

| Variable | Definition |
|---|---|
| `state` | Two-letter code |
| `effective_school_year` | School year the policy took effect, as written in the source |
| `first_covered_class` | First graduating class covered (e = 0). Colorado: earliest grantee school (2023); school-level classes are in `co_grantee_schools.csv` |
| `partial_rollout_class` | A class only partly covered; excluded from the dose window and reference class |
| `last_covered_class` | Last covered class if the policy was repealed or sunsets (LA 2024, NH 2024, NJ 2027); blank if ongoing |
| `policy_type` | `graduation_requirement`, `lea_requirement` (CA, NY), `lea_support_duty` (MD), `grant_schools_only` (CO), `completion_requirement` (PA: required but graduation not affected) |
| `requirement_on` | Who the requirement binds (students, LEAs, grantee schools) |
| `graduation_consequence` | `diploma_withheld` or `none` |
| `adoption` | `statutory` or `regulatory` |
| `opt_out`, `waiver_by` | Whether an opt-out exists and who may sign or grant it |
| `alternative_application` | Application accepted in place of the FAFSA (e.g. TASFA, CADAA, TOPS online application) |
| `citation`, `source`, `notes` | Legal citation, source document and page, notes |

`co_grantee_schools.csv`, one row per Colorado Fund My Future grantee high school (11): `grantee`, `school_name`, `nces_id` (12-digit NCES ID, matching `school_id` in `fsa_school_panel.parquet`), `program_launch`, `first_covered_class`, `partial_rollout_class` (Westminster's two schools: program launched spring 2023, so 2023 is partial and 2024 is the first covered class), `source`, `notes`.

## `policy_timing.parquet`

- **Produced by:** `code/04_policy_timing.py`
- **Unit of observation:** treatment unit: one row per study state, except Colorado, which has one row per grantee school (25 rows).
- **Key (unique):** `state`, `school_id` (`school_id` missing for statewide rows)

| Variable | Type | Definition |
|---|---|---|
| `state`, `school_id`, `policy_type`, `first_covered_class`, `partial_rollout_class`, `last_covered_class` | — | From the policy inputs |
| `reference_class` | int | e = −1: last class before `first_covered_class` that is not a partial-rollout class |
| `dose_class_1`, `dose_class_2` | int | The two classes before `reference_class` (skipping partial-rollout classes); the dose is 1 − average FCR over them |
| `post_first`, `post_last`, `n_post_classes` | Int64/int | Post-mandate classes with FSA data: e = 0 through the earlier of `last_covered_class` and the newest FSA class (missing / 0 if none yet) |
| `post_includes_preliminary` | bool | Post classes include FSA's preliminary (newest) class |
| `dose_in_fsa` | bool | Both dose classes are within the FSA data (class of 2015 on) |
| `dose_or_reference_covid` | bool | Dose or reference class is 2020 or 2021 |
| `dose_or_reference_2024` | bool | Dose or reference class is 2024 (delayed 2024-25 FAFSA) |
| `dose_or_reference_preliminary` | bool | Dose or reference class is FSA's preliminary class (CT, PA: reference 2026) |
| `post_includes_2024` | bool | Post classes include 2024 |

## `ccd_school_panel.parquet`

- **Produced by:** `code/05_build_ccd_school_panel.py`
- **Unit of observation:** public school × school year, 15 study states, school years 2014-15 to 2024-25. Only schools open that year (CCD statuses Open, New, Added, Changed Boundary/Agency, Reopened); closed, inactive, and future schools are dropped (856–1,300 per year).
- **Key (unique):** `school_id`, `class_year`
- **Sources:** CCD school files 029 (Directory), 129 (School Characteristics), 052 (Membership), 033 (Lunch), 059 (Staff); NCES EDGE school locale. CCD negative codes (−1 missing, −2 not applicable, −9 suppressed, ...) are missing.

| Variable | Type | Units | Definition | Source | Missing-value codes |
|---|---|---|---|---|---|
| `school_id` | string | — | Stable school ID (most recent NCES ID; `code/school_ids.py`); matches `fsa_school_panel.parquet` | derived | — |
| `nces_id` | string | — | NCES ID that year | 029 `NCESSCH` | — |
| `class_year` | int | year | Spring year of the school year (2014-15 → 2015); grade-12 counts are that graduating class's seniors | derived | — |
| `state`, `name`, `lea_id`, `lea_name`, `city` | string | — | State, school name, district ID and name, physical city | 029 | — |
| `school_type` | string | — | CCD school type as published | 029 `SCH_TYPE_TEXT` | — |
| `school_type_std` | string | — | `regular`, `special_education`, `career_technical`, `alternative` (CCD renamed types in 2016-17) | derived | — |
| `charter` | bool | — | Charter school | 029 `CHARTER_TEXT` | Null if not applicable/missing |
| `virtual` | string | — | Virtual status as published (Yes/No through 2015-16; categories such as "Full virtual" later) | 029 `VIRTUAL` (2014-15, 2015-16); 129 `VIRTUAL_TEXT` (2016-17 on) | — |
| `level`, `gslo`, `gshi` | string | — | School level; lowest and highest grade offered | 029 | — |
| `n_grades` | Int64 | grades | Grades offered from `gslo` to `gshi`, PK and KG counted | derived | Null if a grade code is missing/ungraded |
| `title_i`, `nslp_status` | string | — | Title I status; National School Lunch Program status (incl. CEP) | 129 | `title_i` null from 2022-23 (no longer published) |
| `locale` | string | — | Urban-centric locale code (11–43) | EDGE (`LOCALE`; `LOCALE15` in 2015-16) | — |
| `enroll_total` | Int64 | students | Total enrollment | 052 (`TOTAL`/`MEMBER`; long files: Education Unit Total) | — |
| `enroll_g12` | Int64 | students | Grade-12 enrollment (fall count); the fallback FCR denominator where state graduate counts are missing | 052 | — |
| `enroll_g09`–`enroll_g11` | Int64 | students | Enrollment in grades 9–11 (fall count). Grade 9 lagged three years is a class's 9th-grade cohort (Deneault's school screen); grades 10–11 help check class sizes over time. Not denominators. | 052 | — |
| `race_american_indian`, `race_asian`, `race_hispanic`, `race_black`, `race_white`, `race_pacific_islander`, `race_two_or_more` | Int64 | students | Enrollment by race/ethnicity (long files: subtotal by race and sex minus adult education, summed over sex) | 052 | — |
| `frl_free`, `frl_reduced`, `frl_total` | Int64 | students | Free-lunch, reduced-price-lunch, and total FRL-eligible students | 033 | ~4% missing |
| `direct_cert` | Int64 | students | Directly certified students | 033 (2016-17 on) | Null before 2016-17 and where not reported (~73% of high-school rows) |
| `teachers_fte` | Float64 | FTE | Full-time-equivalent teachers | 059 (`FTE`; long files: `TEACHERS`) | ~5% missing |

Known breaks: Illinois's alternative and special-education schools stop reporting grade-12 students in 2020-21 (about 100 schools), and Connecticut stops listing about 150 alternative and special-education programs in 2016-17/2017-18; regular high schools are unaffected. Locale for 2014-15 comes from the 2014-15 EDGE geocode file listed under CCD.

## `analysis_panel.parquet`

- **Produced by:** `code/06_build_analysis_panel.py`
- **Unit of observation:** public school × graduating class in the 15 study states (FSA public rows joined to CCD and policy timing). No rows are dropped; sample screens are `f_*` columns.
- **Key (unique):** `school_id`, `class_year`
- **Follows:** Deneault (2023), `mergedata_aejep.do` and `main_aejep.do`.

Main variables (all FSA, CCD, and policy-timing columns are also carried):

| Variable | Type | Definition |
|---|---|---|
| `denominator`, `denominator_source` | Float64, string | Seniors: CCD grade-12 enrollment (`ccd_grade12`); to be replaced by state graduate counts where available. Missing for the class of 2026 (CCD 2025-26 membership not released) |
| `fcr`, `fcr_capped` | Float64, bool | `completed_jun / denominator`, capped at 1 (as Deneault); flag if the cap bound. Missing when completions are "<5" (as Deneault) or the denominator is missing/0 |
| `treated` | bool | Unit has policy timing (every school in 14 states; Colorado grantee schools only) |
| `e` | Int64 | Event time: `class_year − first_covered_class` |
| `post` | bool | Class covered: from `first_covered_class` through `last_covered_class` |
| `partial_rollout`, `after_repeal` | bool | Class is the unit's partial-rollout class; class is after the last covered class |
| `pre_fcr`, `dose` | Float64 | Mean `fcr` over the two dose classes (both required); `dose = 1 − pre_fcr` |
| `weight` | Float64 | Mean over pre-mandate classes of `enroll_total / n_grades` (Deneault's weight) |
| `cohort9` | Int64 | The class's 9th-grade cohort: grade-9 enrollment three years earlier (from the class of 2018 on, since CCD starts in 2014-15) |
| `student_teacher_ratio` | Float64 | `enroll_total / teachers_fte` |
| `share_white`, `share_black`, `share_hispanic`, `share_asian`, `share_frl` | Float64 | Shares of total enrollment (FRL capped at 1) |
| `enroll_total_sq` | Float64 | Total enrollment squared (Deneault control) |
| `in_window` | bool | Class is in the estimation window: e = −4 … +1 (to 0 if only one post class), limited to classes with a denominator (2015–2025) and covered classes, excluding a partial-rollout class |
| `window_classes_needed` | int | Number of window classes the school should have |
| `f_in_ccd` | bool | School is in CCD in some year |
| `f_not_special_ed` | bool | Never a special-education school (Deneault's screen) |
| `f_regular` | bool | Always a regular school (project design: drops special-ed, career/technical, alternative) |
| `f_not_virtual` | bool | Never fully or primarily virtual |
| `f_cohort9_positive` | bool | No class with a 9th-grade cohort of 0 (Deneault; only cohorts from 2018 on are observed) |
| `f_ratio_ok` | bool | Student/teacher ratio never below 5 and not above 100 in every year (Deneault) |
| `f_dose_ok` | bool | Both dose classes have `fcr` |
| `f_balanced` | bool | `fcr` observed in every window class |

Deneault's controls also include school ACT, which is not yet in the data.

## Output tables (`output/tables/`)

- `sample_screens_by_state.csv` (from `code/06_build_analysis_panel.py`): treated public schools with post-mandate classes in each state, and how many remain after each screen in design order (cumulative), plus the number passing Deneault's screens.
- `first_stage_by_state.csv` (from `code/07_first_stage.py`): one row per state and specification (`main`, `no_frl`, `deneault` for Louisiana), `controls` (`with_frl` or `no_frl`; Illinois's main uses `no_frl`): `beta` (coefficient on dose × post), `se` (clustered by school), `p`, `n_obs`, `n_schools`, `classes` (window), `mean_fcr_pre` (weighted mean completion rate before the mandate), `mean_dose`.

## `<dataset>.parquet`

- **Produced by:** `code/<script>.py`
- **Unit of observation:**
- **Key (unique):**

| Variable | Type | Units | Definition | Source | Missing-value codes |
|---|---|---|---|---|---|
| | | | | | |
