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

## `<dataset>.parquet`

- **Produced by:** `code/<script>.py`
- **Unit of observation:**
- **Key (unique):**

| Variable | Type | Units | Definition | Source | Missing-value codes |
|---|---|---|---|---|---|
| | | | | | |
