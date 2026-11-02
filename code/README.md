# Code

Run every script from the repository root with `uv run --locked python code/<script>.py`, or rebuild everything with `bash run.sh`. Paths and the list of study states (`STUDY_STATES`) come from `config.py`. Each script's docstring has the full details.

## Pipeline (first stage)

| Step | Script | Reads | Writes | What it does |
|---|---|---|---|---|
| 0 | `00_download_raw_data.py [GROUPS]` | `sources.py` | `data/raw/`, `data/raw/download_manifest.csv`, `output/tables/state_data_sources.csv` | Downloads the raw files, records their URLs and hashes, and writes the source catalog (state x measure, publisher, coverage, status). Not part of `run.sh`. `--check` re-checks files on disk (and manual exports' hashes); `--prune` drops manifest rows for files deleted by hand. |
| 1 | `01_clean_fsa.py` | FSA FAFSA completion archives | `data/derived/fsa_fafsa_hs.parquet` | One row per FSA record × class (2015–2026, all states). "<5" cells are missing with `*_lt5` flags. |
| 2 | `02_link_fsa_codes.py` | step 1, CCD and PSS directories | `fsa_school_codes.parquet` | Links pre-2021 FSA records (no school code) to NCES/PSS codes in tiers: exact, normalized, name only, year check, CCD/PSS exact/prefix/fuzzy, other year. |
| 3 | `03_build_fsa_school_panel.py` | steps 1–2, CCD directories | `fsa_school_panel.parquet` | Sums duplicate listings, gives each school a stable `school_id` across NCES ID changes, keeps the 15 study states. |
| 4 | `04_build_ccd_school_panel.py` | CCD files (directory, school characteristics, membership, lunch, staff), EDGE locale | `ccd_school_panel.parquet` | School × class characteristics for 2014-15 to 2024-25: grade-12 and total enrollment, race, FRL, teachers, school type, virtual status, locale. |
| 5 | `05_build_analysis_panel.py` | steps 3–4, `data/policy/state_mandates.csv`, `data/policy/co_grantee_schools.csv` | `policy_timing.parquet`, `analysis_panel.parquet`, `output/tables/sample_screens_by_state.csv` | First derives each state's policy timing: first covered class, reference class (e = −1), the two dose classes, post classes, and COVID / 2024 / preliminary flags. Then builds the public-school panel: completion rate (`fcr` = completions / grade-12 enrollment, capped at 1), dose, weight, controls, and the `f_*` screen flags. No rows are dropped. |
| 6 | `06_first_stage.py` | step 5 | `output/tables/first_stage_by_state.csv` | Estimates `fcr ~ dose×post + controls \| school + class` by state, weighted, clustered by school. Specs: `main`, `no_frl`, `deneault` (LA only). Colorado is excluded for now; Illinois's main spec has no FRL control. |

## Review (not part of `run.sh`)

| Script | Reads | Writes | What it does |
|---|---|---|---|
| `state_files.py [STATES]` | state files in `data/raw/`, `ccd_school_panel.parquet`, `analysis_panel.parquet` | `output/tables/state_file_review.csv` | Content review before cleaning: one reader per state source turns the raw files into school rows; reports per class how many rows link to CCD by the state's school code and how many panel schools are covered. Findings are in `docs/source-notes.md`. |

Columns of `state_file_review.csv` (one row per state × source × class):

| Column | Meaning |
|---|---|
| `n_rows` | School rows the reader found in the state's file for that class (district and state total rows left out) |
| `n_matched_ccd_same_year` | Of those, rows whose state school code matches a CCD school's code (`st_schid`, last segment) in the same class year |
| `n_matched_ccd_overall` | Rows matched in the same year or, failing that, by the same code in any CCD year (most recent) |
| `panel_schools` | Public schools in `analysis_panel.parquet` with grade-12 enrollment that class (the schools the first stage can use) |
| `panel_covered` | Of `panel_schools`, how many have a row in the state file |
| `graduates` | Sum of the file's graduate count over its school rows (blank if the file has no count) |

## Outcomes

| Step | Script | Reads | Writes | What it does |
|---|---|---|---|---|
| 7 | `07_build_state_outcomes.py` | state files in `data/raw/` (via `state_files.py`), `ccd_school_panel.parquet` | `data/derived/state_outcomes.parquet` | School × class college-going outcomes from the state files, linked to CCD by the state's school code. Every state: the published enrollment rate. Louisiana also: Deneault's `penroll` = enrollment rate × cohort graduation rate (bounds coded her way). |
| 8 | `08_reduced_form.py` | `analysis_panel.parquet`, `state_outcomes.parquet` (uses `06_first_stage.py`'s `sample`/`estimate`) | `data/derived/reduced_form_panel.parquet`, `output/tables/reduced_form_by_state.csv` | Merges the outcomes onto the panel (left join, one to one) and estimates the reduced form by state: enrollment rate on dose × post with the first stage's screens, controls, weights and clustering, on window classes that have outcome data; also the first stage on the same sample and their ratio. |

## Helper modules (imported, not run)

| Module | Used by | Contents |
|---|---|---|
| `config.py` | all | `ROOT`, `RAW`, `DERIVED`, `OUTPUT`, `STUDY_STATES`, `STATE_FIPS` |
| `sources.py` | step 0 | Registry of raw files by group (states `LA`, `IL`, `AL`, `TX`, `CO`, `CA`, `IN`, `NH`, `NE`, `OK`, `NY`, `NJ`, `CT`, `PA`; national `FSA`, `CCD`, `ACGR`, `ASSESS`, `EDGE`, `PSS`, `FED`), the source `CATALOG`, the HTTP helpers (retries, sessions, form posts), and the shared builders `scraped()` (files linked from landing pages, by filename pattern), `resolved()` (opaque links, by the filename the server sends), and `listed()` (fixed URL lists) |
| `state_files.py` | step 7 (also run as the review script, above) | Readers that turn each state's raw files into school rows (`la_college_enrollment`, `la_grad_rates`, ...), value parsing (`value`, `bound`, Deneault's `midpoint`), and `link` (state school code to CCD, same year then any year, with per-state code aliases) |
| `matching.py` | steps 2–4 | Name normalization and the strict fuzzy-match rule; `stable_ids`: one ID per school across NCES district moves |

## Notes

- The completion-rate denominator is CCD grade-12 enrollment, so the estimates from step 6 are preliminary until state graduate counts are added.
- The sample rules and control choices are recorded in `docs/DECISIONS.md`; variables are defined in `docs/codebook.md`.
- Tests for every step are in `tests/test_pipeline.py` (`uv run --locked pytest -q`).
