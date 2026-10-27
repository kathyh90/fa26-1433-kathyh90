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

## `<dataset>.parquet`

- **Produced by:** `code/<script>.py`
- **Unit of observation:**
- **Key (unique):**

| Variable | Type | Units | Definition | Source | Missing-value codes |
|---|---|---|---|---|---|
| | | | | | |
