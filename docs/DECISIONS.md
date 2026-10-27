# Decisions

Record consequential choices about data, samples, variables, and methods. Newest first.

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
