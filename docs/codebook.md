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
- **Unit of observation:** school × graduating class in the 15 study states (LA, IL, AL, MD, TX, CO, CA, IN, NH, NE, OK, NY, NJ, CT, PA), all sectors, classes 2015–2026.
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

Hand-entered from statutes and agency reports (sources in each row and in `docs/source-notes.md`); tracked in Git. Read by `code/05_build_analysis_panel.py`.

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

- **Produced by:** `code/05_build_analysis_panel.py`
- **Unit of observation:** treatment unit: one row per study state, except Colorado, which has one row per grantee school (25 rows).
- **Key (unique):** `state`, `school_id` (`school_id` missing for statewide rows)

| Variable | Type | Definition |
|---|---|---|
| `state`, `school_id`, `policy_type`, `first_covered_class`, `partial_rollout_class`, `last_covered_class` | — | From the policy inputs |
| `reference_class` | int | e = −1: last class before `first_covered_class` that is not a partial-rollout class |
| `dose_class_1`, `dose_class_2` | int | The two classes before `reference_class` (skipping partial-rollout classes); the dose is 1 − average FCR over them |
| `dose_clean_class_1`, `dose_clean_class_2` | int | The two newest classes before `reference_class` that are not partial-rollout, COVID (2020, 2021) or FAFSA-rollout (2024) classes; dose classes of the `clean_dose` spec |
| `dose_shifted` | bool | The clean dose classes differ from `dose_class_1/2` (AL, TX, MD, CA, IN, NH, CT, PA) |
| `post_first`, `post_last`, `n_post_classes` | Int64/int | Post-mandate classes with FSA data: e = 0 through the earlier of `last_covered_class` and the newest FSA class (missing / 0 if none yet) |
| `post_includes_preliminary` | bool | Post classes include FSA's preliminary (newest) class |
| `dose_in_fsa` | bool | Both dose classes are within the FSA data (class of 2015 on) |
| `dose_or_reference_covid` | bool | Dose or reference class is 2020 or 2021 |
| `dose_or_reference_2024` | bool | Dose or reference class is 2024 (delayed 2024-25 FAFSA) |
| `dose_or_reference_preliminary` | bool | Dose or reference class is FSA's preliminary class (CT, PA: reference 2026) |
| `post_includes_2024` | bool | Post classes include 2024 |

## `ccd_school_panel.parquet`

- **Produced by:** `code/04_build_ccd_school_panel.py`
- **Unit of observation:** public school × school year, 15 study states, school years 2014-15 to 2024-25. Only schools open that year (CCD statuses Open, New, Added, Changed Boundary/Agency, Reopened); closed, inactive, and future schools are dropped (856–1,300 per year).
- **Key (unique):** `school_id`, `class_year`
- **Sources:** CCD school files 029 (Directory), 129 (School Characteristics), 052 (Membership), 033 (Lunch), 059 (Staff); NCES EDGE school locale. CCD negative codes (−1 missing, −2 not applicable, −9 suppressed, ...) are missing.

| Variable | Type | Units | Definition | Source | Missing-value codes |
|---|---|---|---|---|---|
| `school_id` | string | — | Stable school ID (most recent NCES ID; `stable_ids` in `code/matching.py`); matches `fsa_school_panel.parquet` | derived | — |
| `nces_id` | string | — | NCES ID that year | 029 `NCESSCH` | — |
| `st_schid` | string | — | State's own school ID that year, as CCD reports it (e.g. `LA-001-001005`: state, state district code, state school code); links state data files to NCES IDs | 029 `ST_SCHID` | — |
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

## `ccd_grade9.parquet`

- **Produced by:** `code/04_build_ccd_school_panel.py` (`build_grade9`)
- **Unit of observation:** public school × school year, 15 study states, school years 2011-12 to 2024-25 (class years 2012–2025). Open schools only (universe-file `STATUS` 1, 3, 4, 5, 8 before 2014-15, the same statuses as the panel). Used only to form the 9th-grade cohort (`cohort9`) in step 5.
- **Key (unique):** `school_id`, `class_year`
- **Sources:** 2011-12 to 2013-14: CCD school universe files (`sc111a_supp`, `sc122a`, `sc132a`; column `G09`). 2014-15 on: `enroll_g09` of `ccd_school_panel.parquet`.

| Variable | Type | Units | Definition | Source | Missing-value codes |
|---|---|---|---|---|---|
| `school_id` | string | — | As in `ccd_school_panel.parquet` (`stable_ids`; ID chains are built from 2014-15 on, so a school whose NCES ID changed before 2014-15 keeps its old ID in the early years) | derived | — |
| `class_year` | int | year | Spring year of the school year | derived | — |
| `enroll_g09` | Int64 | students | Grade-9 enrollment (fall count) | universe `G09`; 052 | CCD negative codes missing; schools without grade 9 are missing (early years) or 0/missing (later years) |

## `analysis_panel.parquet`

- **Produced by:** `code/05_build_analysis_panel.py`
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
| `pre_fcr_clean`, `dose_clean` | Float64 | The same over `dose_clean_class_1/2` (robustness spec `clean_dose`); equal to `pre_fcr`, `dose` where `dose_shifted` is false |
| `weight` | Float64 | Mean over pre-mandate classes of `enroll_total / n_grades` (Deneault's weight) |
| `cohort9` | Int64 | The class's 9th-grade cohort: grade-9 enrollment three years earlier, from `ccd_grade9.parquet` (from the class of 2015 on; redefined 2026-11-08, previously from 2018 on and only for schools in the FSA panel three years earlier) |
| `student_teacher_ratio` | Float64 | `enroll_total / teachers_fte` |
| `share_white`, `share_black`, `share_hispanic`, `share_asian`, `share_frl` | Float64 | Shares of total enrollment (FRL capped at 1) |
| `enroll_total_sq` | Float64 | Total enrollment squared (Deneault control) |
| `in_window` | bool | Class is in the estimation window: e = −4 … +1 (to 0 if only one post class), limited to classes with a denominator (2015–2025) and covered classes, excluding a partial-rollout class |
| `window_classes_needed` | int | Number of window classes the school should have |
| `f_in_ccd` | bool | School is in CCD in some year |
| `f_not_special_ed` | bool | Never a special-education school (Deneault's screen) |
| `f_regular_cte` | bool | Always a regular or career/technical school (main screen from 2026-11-02: drops special-ed and alternative) |
| `f_not_virtual` | bool | Never fully or primarily virtual |
| `f_senior_share_ok` | bool | No estimation-window class in which the lowest grade is 9 or below and grade-12 enrollment is more than 75% of grades 9-12 (data-quality screen, main spec; `SENIOR_SHARE_MAX`) |
| `f_cohort9_positive` | bool | No class with a 9th-grade cohort of 0 (Deneault; cohorts observed from the class of 2015 on). Used only in the `deneault` spec since 2026-11-02 |
| `f_ratio_ok` | bool | Student/teacher ratio never below 5 and not above 100 in every year (Deneault) |
| `f_dose_ok` | bool | Both dose classes have `fcr` |
| `f_dose_clean_ok` | bool | Both clean dose classes have `fcr` (replaces `f_dose_ok` in `clean_dose`) |
| `f_balanced` | bool | `fcr` observed in every window class |
| `in_window_common`, `window_classes_needed_common`, `f_senior_share_ok_common`, `f_balanced_common` | bool, int, bool, bool | The same four columns for the common window e = −3 … 0 in every state (`WINDOWS` in step 5; same data limits and partial-rollout rule), used by spec `common_window`, the cross-state pooling input (DECISIONS 2026-11-15) |

Deneault's controls also include school ACT, which is not yet in the data.

## Output tables (`output/tables/`)

- `sample_screens_by_state.csv` (from `code/05_build_analysis_panel.py`): treated public schools with post-mandate classes in each state, and how many remain after each screen in design order (cumulative), plus the number passing Deneault's screens.
- `first_stage_by_state.csv` (from `code/06_first_stage.py`): one row per state and specification (`main`, `no_frl`, `deneault`: Deneault's screens with the no-FRL controls, every state; vs. `no_frl` it differs only in the screens; `clean_dose`: main with `dose_clean`, only where `dose_shifted`; `common_window`: main on the common window e = −3 … 0 in every state (`in_window_common`, `f_balanced_common`, `f_senior_share_ok_common`), the input to the cross-state pooling; also in `reduced_form_by_state.csv` and the event-study files), `controls` (`with_frl` or `no_frl`; Illinois's main uses `no_frl`): `beta` (coefficient on dose × post), `se` (clustered by school), `p`, `n_obs`, `n_schools`, `classes` (window), `mean_fcr_pre` (weighted mean completion rate before the mandate), `mean_dose`.
- `reduced_form_by_state.csv` (from `code/08_reduced_form.py`): one row per state and specification, as the first stage, for states with pre and post outcome classes: `outcome` (`enroll` = `pct_enrolled` / 100; `penroll` for Louisiana's `deneault` spec; other states' `deneault` rows use `enroll`), `window` (which enrollment rate), `beta`, `se`, `p`, `n_obs`, `n_schools`, `classes` (window classes with outcome data), `schools_first_stage_sample` (schools before requiring the outcome), `mean_y_pre` (weighted pre-mandate mean outcome), `mean_dose`, `fs_beta` / `fs_se` (first stage re-estimated on the same sample), `rf_fs_ratio` (`beta / fs_beta`, enrollment change per unit of FAFSA completion; no standard error), `dropped_no_outcome` / `dropped_partial_outcome` (first-stage schools left out because, in the window classes with outcome data, they have no outcome at all — unlinked or never published — or miss it in some classes, mostly suppressed small cells; `schools_first_stage_sample − n_schools` = their sum).
- `reduced_form_by_state.csv` also has rows with `spec = grad_denom` (graduate-denominator specification, DECISIONS 2026-11-02): FAFSA completion (and dose) = completions ÷ the state's graduate count (`outcome_graduates`) instead of CCD grade-12 enrollment, on the baseline main sample's schools; `schools_first_stage_sample` is the graduate-denominator first-stage sample; `fs_beta` is its first stage on the reduced-form sample; `mean_dose` is the graduate-based dose.
- `first_stage_grad_by_state.csv` (from `code/08_reduced_form.py`): the graduate-denominator first stage on each state's sample before requiring the outcome; columns as `first_stage_by_state.csv` (`mean_fcr_pre` and `mean_dose` per graduate).
- `graduate_denominator_check.csv` (from `code/08_reduced_form.py`): one row per state × class over treated public schools with both counts: `schools`, `graduates`, `ccd_grade12`, `ratio` (graduates ÷ grade-12 enrollment, sums), `median_school_ratio`, `schools_ratio_outside_half_to_1_5`. A break in `ratio` within a state would flag a change in how graduates are counted.
- `graduate_ratio_dose_test.csv` (from `code/08_reduced_form.py`): one row per state × `spec` for states with graduate counts in a pre and a post window class: main specification with outcome `grad_ratio` = state graduate count ÷ CCD grade-12 enrollment on dose × post (baseline dose, controls, weights, FE, clustering), on the main first-stage sample limited to classes with counts and schools with a count in each. `spec` = `main` or `main_trimmed` (schools with any ratio outside 0.5–1.5 dropped). Columns `beta`, `se`, `p`, `n_obs`, `n_schools`, `classes`, `mean_ratio_pre` (weighted pre-mandate mean), `mean_dose`. Tests whether the graduate count responds to the mandate by dose.
- `summary_stats_rf_by_state.csv` and `summary_stats_rf_by_dose_quartile.csv` (from `code/09_summary_stats.py`): school characteristics of each state's `main` reduced-form sample. `summary_stats_fs_by_state.csv` and `summary_stats_fs_by_dose_quartile.csv`: the same for the `main` first-stage sample (12 states; school counts equal `first_stage_by_state.csv` `n_schools`; `enroll` averaged over the schools and classes that have it). Each school is first averaged over its pre-mandate sample classes; the tables give the **unweighted mean and SD across schools** (`stat` = `mean`, `sd`; `n_schools` row), one column per state (or per dose quartile) plus `All`. Shares describe the average school, not the state's students (e.g. `share_black` = mean of school Black shares). Variables: `enroll_total`, `enroll_g12`, `share_white/black/hispanic/asian/frl` (CCD, as in the panel), `charter` (0/1; blank where CCD reports none, e.g. Nebraska), `city`/`suburb`/`town`/`rural` (0/1 from the first digit of NCES `locale`), `pre_fcr`, `dose`, `enroll` (pre-mandate college enrollment rate). Dose quartiles `Q1` (lowest dose, highest pre-mandate completion) to `Q4` are cut within each state, then pooled.
- `results_tables.html` (from `code/10_export_tables.py`): Tables 1A (first-stage sample), 1B (reduced-form sample), 2, 3, and 4 (graduate denominator vs. baseline) for the paper, formatted from the three CSVs above (no new variables): coefficients with school-clustered SEs in parentheses and stars (* p<0.10, ** p<0.05, *** p<0.01; none on the same-sample first stage, whose p-value is not saved), and notes defining each state's outcome.
- `event_study_by_state.csv` (from `code/11_event_study.py`): one row per state, spec, outcome, and event time: `spec` (`main`: CCD grade-12 denominator; `grad_denom`: completions ÷ state graduate count, dose recomputed, on step 8's graduate-denominator schools; both use `enroll` for the enrollment outcome), `outcome` (`fcr` FAFSA completion, CCD grade-12 denominator; `enroll` college enrollment rate as a share), `e` (event time; `e = -1` is the omitted reference class, stored as `beta = se = 0`), `beta` (coefficient on dose × 1[e]: gap in the outcome between dose 1 and dose 0, relative to that gap at e = −1), `se` (school-clustered), `ci_lo` / `ci_hi` (95%, t with clusters − 1 df), `class_year`, `n_schools` (schools with the outcome in that class; panel unbalanced outside the estimation window), `post` (e ≥ 0), `n_obs`, `n_schools_total`. Sample: the state's main first-stage schools over all their classes, minus partial-rollout and post-repeal classes.
- `event_study_pretrends.csv` (from `code/11_event_study.py`): one row per state, spec, outcome, and test: `test` (`pre_all`: all β_k = 0 for k ≤ −2; `pre_no_dose`: k ≤ −2 except the spec's dose classes, whose FAFSA coefficients are mechanically negative; k ≤ −4 for `main` and `grad_denom`, other classes for `clean_dose`), `n_coefs`, `F` (cluster-robust Wald F), `p` (F with (n_coefs, clusters − 1) df), `classes` (event times tested), `n_obs`, `n_schools_total`. Blank `F`/`p` when no class is tested (e.g. Louisiana: FSA starts at e = −3).
- `pooling_hyper.csv` (from `code/12_aggregation.R`): Bayesian hierarchical pooling (Meager 2019; baggr's Rubin model) of each state's `main` `beta` and `se`, one row per `input_spec` (step-6/8 spec pooled: `common_window`, the main analysis, every prior; `main`, Deneault's window that differs across states, `main` prior only, window sensitivity) × `outcome` (`fafsa_completion` from `first_stage_by_state.csv`, `college_enrollment` from `reduced_form_by_state.csv`), `model`, `prior`, and `parameter`. Model: beta_hat_k ~ N(beta_k, se_k²), beta_k ~ N(mu + delta·no_diploma_k, sigma_beta²). `model` = `no_covariate` (delta = 0) or `covariate` (`no_diploma` = 1 when `state_mandates.csv` `graduation_consequence` is `none`: CA, NY, PA). `prior` (scale s = 1 for FAFSA completion, 0.5 for college enrollment): `main` (weakly informative: mu ~ N(0, s²), delta ~ N(0, (0.5s)²), sigma_beta ~ Half-Normal(0, 0.5s)); `flat_uniform` (flat mu and delta, sigma_beta ~ Uniform(0, 1); BDA3 default); `half_cauchy_05` (main priors on mu and delta, sigma_beta ~ half-Cauchy(0, 0.05), favoring similar states). sigma_beta is bounded at 1 in every prior (grid). `parameter`: `mu` (hypermean: pooled average effect; in `covariate`, for diploma-withheld states), `sigma_beta` (hyper-SD: SD of true state effects), `delta` (covariate coefficient: difference for no-diploma states), `new_state` (posterior predictive effect in a new diploma-withheld state), `predict_CT` / `predict_PA` (posterior predictive with each state's covariate; out-of-sample test). Columns `n_states`, `mean`, `sd`, `q025`, `q975` (95% interval), `p_gt0` (posterior probability > 0). 20,000 exact draws (sigma_beta on a grid), seed fixed. baggr's vignette writes the hypermean as τ, the hyper-SD as σ_τ, and the covariate coefficient as β.
- `pooling_states.csv` (from `code/12_aggregation.R`): one row per outcome × (`input_spec` = `common_window`) × `model` (`no_covariate`, `covariate`; main prior) × state: `no_diploma` (covariate, 1 = no diploma consequence), `beta`, `se` (state estimate), `center_mean`, `center_q025`, `center_q975` (posterior mean and 95% interval of the state's center: mu, or mu + delta·no_diploma_k in `covariate`), `beta_k_mean`, `beta_k_q025`, `beta_k_q975` (posterior of the state's true effect after partial pooling toward its center), `omega_k` (Meager's pooling factor, her eq. 6: se_k² ÷ (sigma_beta² + se_k²) at the model's posterior mean of sigma_beta²; the weight on the center in E[beta_k]; 0 = keeps its own estimate, 1 = fully pooled), `omega_bar` (average of `omega_k` over the outcome's states), `lambda_gp` (Gelman & Pardoe 2006 generalized pooling factor, Meager eq. 8: 1 − var_k(E[eps_k]) ÷ E[var_k(eps_k)], eps_k = beta_k − center_k, from posterior draws). `omega_bar` and `lambda_gp` repeat within an outcome × model.
- `pooling_loo.csv` (from `code/12_aggregation.R`): leave-one-state-out check, `input_spec` = `common_window`; one row per outcome × `dropped` state: its `beta`, `se`; `mu_mean`, `sigma_beta_mean` without it; `pred_mean`, `pred_q025`, `pred_q975` (posterior predictive for a new state); `inside_95` (whether the dropped state's `beta` lies in the predictive interval).
- `output/figures/pooling_forest.png` (from `code/12_aggregation.R`): covariate model, `common_window` input, main prior. Per outcome, each state's estimate with 95% CI (open) and its pooled effect with 95% interval (filled), colored by diploma group (blue: withheld; orange: no diploma); below, each group's center (mu; mu + delta) with 95% interval (diamond, thick bar).
- `pooling_baggr_check.csv` (from `code/13_baggr_check.R`, optional): one row per `outcome` × `model` × `parameter` (as `pooling_hyper.csv`, `common_window` input and `main` prior only): `exact_mean`, `exact_q025`, `exact_q975` (from `pooling_hyper.csv`), `baggr_mean`, `baggr_q025`, `baggr_q975` (baggr 0.8.2 Rubin model, 4 chains × 40,000 iterations, the same main priors: `prior_hypermean = normal(0, s)`, `prior_beta = normal(0, 0.5s)`, `prior_hypersd = normal(0, 0.5s)`, half-normal because baggr bounds it at 0), `max_rhat` (largest Stan R-hat in the fit), `match` (TRUE if the means differ by < 0.1 and both 95% bounds by < 0.2 posterior SDs of the exact result).
- `output/pooling_summary.md` and `output/pooling_summary.html` (from `code/14_pooling_report.R`): plain-language summary of the pooling (model, notation, what pooling does, priors, results, pooling metrics, prior sensitivity, leave-one-out, baggr check, caveats), with every number read from the pooling CSVs above. Equations and symbols are LaTeX: GitHub and VS Code render them in the `.md`; the `.html` (forest plot embedded) renders them with KaTeX 0.16.9 from cdnjs, so it needs internet access to show formatted math. Regenerated by `run.sh`; not edited by hand.

## `<dataset>.parquet`

- **Produced by:** `code/<script>.py`
- **Unit of observation:**
- **Key (unique):**

| Variable | Type | Units | Definition | Source | Missing-value codes |
|---|---|---|---|---|---|
| | | | | | |


## `data/derived/state_outcomes.parquet`

Built by `code/07_build_state_outcomes.py`. One row per school × class in each state's college-going file (Louisiana, Illinois, Alabama, Maryland, Texas, California, Indiana, New Hampshire, Nebraska, Oklahoma, New York, New Jersey so far).

- **Key (unique):** `state`, `class_year`, `code`
- **Rates** are percents as published. A published bound (e.g. `>99`) is stored as its number, with its direction in the matching `*_bound` column (`>` lower bound, `<` upper bound, empty if exact).
- **Breakdown names say their base:** `pct_of_enrolled_*` are shares of enrollees (LA); `pct_of_grads_*` are shares of all graduates (IL, AL). They are not comparable across states.

| Variable | Type | Units | Definition | Source | Missing |
|---|---|---|---|---|---|
| `state` | string | — | Two-letter state code | — | — |
| `class_year` | int | year | Graduating class (spring year). LA: file label "2015-2016 High School Graduates" = 2016. IL: report card year − 2 | state file | — |
| `code` | string | — | State's school code: LA 6-character LDOE site code; IL 15-digit RCDTS (as written in the file); NE 9-digit county + district + school code of the CCD school matched by district and name (`NAME:<district>:<school>` if none); OK CCD county-district-site key (`01-I025-705`) of the school matched by county and name (`NAME:<county>:<school>` if none); NY 12-digit BEDS code (`ENTITY_CD`); NJ 9-digit county-district-school (CDS) code | state file | — |
| `name` | string | — | School name in the state file | state file | — |
| `school_id` | string | — | Stable school ID (as in the panels), via the state code in CCD `st_schid`: same year, else same code in any year; LA alias `031002` → `323002` (Grambling Lab); IL codes compared without the 2-digit type code | derived | not linked (LA 84, IL 53 rows, mostly small or alternative sites) |
| `link` | string | — | `same_year`, `any_year`, or empty (not linked) | derived | — |
| `window` | string | — | Which enrollment rate `pct_enrolled` is: `la_fall_oct31` (enrollment start by Oct 31 of the fall after graduation), `il_12m_sep30` (first enrollment by Sep 30 of the year after graduation), `al_fall_public_instate` (enrolled the fall after graduation at an Alabama public college; no private or out-of-state colleges), `md_within_1yr` (enrolled full- or part-time, any degree status, within one year of graduation; MHEC + NSC), `tx_fall_texas` (enrolled the fall after graduation at a Texas public or private college; THECB; 'not trackable' graduates count as not enrolled), `ca_12m_any` (enrolled at any U.S. college within 12 months of completing high school; CDE, NSC), `in_year_after` (enrolled at any NSC-participating college in the year after graduation; CHE), `nh_year_after` (% of graduates enrolling at a 2- or 4-year college within the year after graduation; NH DOE iExplore; a published rate), `ne_year_after` (on-time public graduates enrolled at any NSC college between June 1 after graduation and May 31 of the next year; CCPE), `ok_year_after_instate` (first-time enrollment at an Oklahoma public or private college in the fall after graduation or later that academic year; OSRHE; no out-of-state colleges), `ny_16m_any` (enrolled at any college, New York or out of state, within 16 months of graduation; NYSED Report Card), `nj_fall` (enrolled at any NSC college in the fall after graduation; NJDOE; lower bound of the published range) | derived | — |
| `graduates` | float | students | High school graduates that school year (all graduates, not a 4-year cohort) | LA "Total HS Graduates"; AL ACHE "High School Graduates" (from ALSDE); MD MLDS "High School Graduates"; TX THECB "Total high school graduates"; CA CDE "High School Completers" (graduates plus non-graduate completers: CHSPE, GED, adult-education diploma); IN CHE "HSGrads"; NH iPlatform total completers (Completers By Status By School); NE CCPE "# On Time HS Grads" (on-time, 4 years or less, public graduates only); OK OSRHE "Number of Graduates" (public high schools; class 2013 on-time only); NY NYSED `TOTAL_GRAD_COUNT` (graduates of the calendar year); **NJ** NJDOE adjusted cohort graduation files "Graduated" (4-year cohort graduates with a state-endorsed diploma, classes 2020-2025; **a 4-year cohort, unlike the other states**, and not the outcome rate's denominator, which is all graduates of the year) | IL (not published); NJ `*`/`N` and classes before 2020; LA `<10`; MD `*`; TX schools with 25 or fewer graduates are not listed |
| `pct_enrolled` | float | percent | **The outcome:** % of the school's graduates enrolled in college in `window` (any U.S. 2- or 4-year college; LA: NSC, + Board of Regents from 2018; IL: NSC) | state file | suppressed |
| `pct_enrolled_bound` | string | — | Bound direction of `pct_enrolled` | state file | — |
| `enrolled` | float | students | LA, NH: `graduates × pct_enrolled / 100` (estimated); AL: published count (2-year + 4-year); MD: published within-one-year count; others: published counts | derived (LA), ACHE (AL), MLDS (MD) | IL; LA if either is missing; MD `*` |
| `enrolled_immediate`, `pct_enrolled_immediate`, `enrolled_within_2yr`, `pct_enrolled_within_2yr` | float | students, percent | **MD:** immediate (full-time, degree-seeking, fall) and within-two-years enrollment counts and rates (÷ graduates). Not to be confused with `enrolled_2yr` (AL: enrolled at 2-year colleges) | MLDS | MD `*`; within two years not yet reported for class 2024; other states |
| `enrolled_2yr`, `enrolled_4yr` | float | students | **AL:** graduates enrolled at Alabama public 2-year / 4-year colleges that fall | ACHE | LA, IL |
| `pct_of_enrolled_2yr`, `pct_of_enrolled_4yr`, `pct_of_enrolled_instate` (+ `_bound`) | float | percent | **LA:** of enrollees, % at 2-year, at 4-year, in state | LA file | suppressed; IL |
| `grad_rate`, `grad_rate_bound` | float, string | percent | **LA:** 4-year cohort graduation rate (classes 2014-2015 from the next year's School Performance Score file, 2016 on from the school graduation summaries). **NJ:** 4-year adjusted cohort graduation rate, state calculation (NJDOE ACGR files, classes 2020-2025) | LA files; NJ `njdoe_acgr` | not published; IL |
| `cohort_count` | float | students | **NJ:** 4-year adjusted cohort count (denominator of `grad_rate`) | NJ `njdoe_acgr` | other states; NJ `*`/`N`, classes before 2020 |
| `penroll` | float | share | **LA only (replication):** Deneault's outcome, `(pct_enrolled/100) × (grad_rate/100)` with bounds at the midpoint of the bounded range (`>99` → 99.5, `<1` → 0.5, `>95` → 97.5, `<5` → 2.5) | derived | classes 2012-2013; either input missing; IL |
| `pct_enrolled_16m` (+ `_bound`) | float | percent | **IL:** % of graduates with a first enrollment by Jan 31, two years after graduation (16-month rate). **NJ:** % of graduates enrolled at any point within 16 months of graduation (lower bound of the published range) | IL report card; NJDOE | suppressed; NJ classes 2024 on (not yet published); other states |
| `pct_of_grads_public`, `pct_of_grads_private`, `pct_of_grads_4yr`, `pct_of_grads_2yr`, `pct_of_grads_trade` (+ `_bound`) | float | percent | **IL:** % of all graduates enrolled within 12 months at a public, private, 4-year, 2-year, or trade/vocational (less-than-2-year) institution; 4-year + 2-year + trade = public + private = `pct_enrolled`. **AL:** `pct_of_grads_2yr`, `pct_of_grads_4yr` = Alabama public 2-/4-year enrollees ÷ graduates | IL report card; AL derived from ACHE counts | IL classes before 2017; suppressed; LA |
| `n_community_college` (+ `_bound`) | float | students | **IL:** number of graduates enrolled in community college | IL report card | outside classes 2017-2021; LA |
| `source_file` | string | — | LA: raw file the row was read from; IL: `report card <year>` | — | — |
| `not_found`, `not_trackable` | float | students | **TX:** graduates with a standard ID not found in Texas colleges that fall; graduates with a non-standard ID that cannot be matched (enrolled + not found + not trackable = graduates) | THECB | other states |
| `pct_enrolled_trackable` | float | percent | **TX:** enrolled ÷ (graduates − not trackable) × 100 (robustness version of the outcome) | derived | other states |
| `enrolled_instate`, `enrolled_outstate`, `enrolled_uc`, `enrolled_csu`, `enrolled_ccc`, `enrolled_instate_private`, `enrolled_outstate_4yr`, `enrolled_outstate_2yr` | float | students | **CA:** completers enrolled within 12 months in California / out of state; at UC, CSU, California community colleges, in-state private colleges; out-of-state 4-year and 2-year (in-state + out-of-state = enrolled; UC + CSU + CCC + private = in-state) | CDE | `*` (10 or fewer); other states |
| `enrolled_in_public` | float | students | **IN:** graduates enrolled at an Indiana public college | CHE | `DS`/`NULL`/`***` (suppressed); other states |
| `pct_enrolled_nde_oct15` | float | percent | **NE:** NDE's college-going % (enrolled on October 15 of the year after the first fall; previous Nebraska outcome), merged by class and code | NDE NEP | outside classes 2016-2023; suppressed (`*`, -1); other states |
| `ccpe_match` | string | — | **NE:** how the CCPE school was matched to a CCD code: `exact_same_year`, `exact_any_year`, `words_same_year`, `words_any_year`, `only_hs_same_year`, `only_hs_any_year`, or empty (not matched: 73 rows, classes 2008-2014, schools closed or merged before CCD 2014-15) | derived | other states |
| `enrolled_fall`, `pct_enrolled_fall` (+ `_bound`) | float | students, percent | **OK:** graduates entering an Oklahoma college directly in the fall after graduation, and % of graduates | OSRHE | other states |
| `first_time_any_class` | float | students | **OK:** first-time students that academic year from the school, from any graduating class (direct and delayed) | OSRHE | other states |
| `enrolled_outstate`, `pct_of_grads_outstate` (+ `_bound`) | float | students, percent | **OK:** graduates entering an out-of-state college for the first time during the following academic year, and % of graduates | OSRHE | classes before 2023; `.`; other states |
| `county` | string | — | **OK:** county in the OSRHE file | OSRHE | other states |
| `act_code` | string | — | **OK:** ACT high school code in the OSRHE file (not a state code) | OSRHE | classes from 2019; other states |
| `name_match` | string | — | **OK:** how the school was matched to CCD (steps as `ccpe_match`); empty if not matched (22 rows) | derived | other states |
| `enrolled_instate_public`, `enrolled_instate_private`, `enrolled_outstate`, `enrolled_2yr`, `enrolled_4yr` | float | students | **NY:** graduates enrolled within 16 months at a New York public, New York private, or out-of-state college; at a 2-year (incl. less than 2-year) or 4-year college (public + private + out of state = 2-year + 4-year = `enrolled`). Same names as AL (`enrolled_2yr`, `enrolled_4yr`: Alabama public colleges only), CA and OK (`enrolled_instate_private`, `enrolled_outstate`); compare across states with care | NYSED Report Card | `s` (suppressed); other states unless listed |

## `data/derived/reduced_form_panel.parquet`

- **Produced by:** `code/08_reduced_form.py`
- **Unit of observation:** as `analysis_panel.parquet` (school × class); every panel column is kept.
- **Key (unique):** `school_id`, `class_year`
- **Merge:** left join of `state_outcomes.parquet` (linked rows only) on `state`, `class_year`, `school_id` (one to one); no panel rows added or dropped.

| Variable | Type | Units | Definition | Source | Missing-value codes |
|---|---|---|---|---|---|
| `outcome_window` | string | — | `window` of the state outcome (which enrollment rate) | `state_outcomes` | no outcome for the school and class |
| `pct_enrolled` | float | percent | The state's published college enrollment rate (`state_outcomes.pct_enrolled`) | `state_outcomes` | no outcome; suppressed |
| `enroll` | float | share | `pct_enrolled / 100`, the reduced-form outcome | derived | as `pct_enrolled` |
| `outcome_graduates` | float | students | `state_outcomes.graduates` (state graduate count where published; NJ: 4-year cohort graduates) | `state_outcomes` | not published (IL); no row |
| `penroll` | float | share | **LA:** Deneault's outcome (see `state_outcomes`) | `state_outcomes` | other states; LA classes before 2014 |
| `outcome_link` | string | — | How the outcome row linked to CCD (`same_year`, `any_year`) | `state_outcomes` | no outcome |

