# Code

Run every script from the repository root with `uv run --locked python code/<script>.py`, or rebuild everything with `bash run.sh`. Paths and the list of study states (`STUDY_STATES`) come from `config.py`. Each script's docstring has the full details.

## Pipeline (first stage)

| Step | Script | Reads | Writes | What it does |
|---|---|---|---|---|
| 0 | `00_download_raw_data.py [GROUPS]` | `sources.py` | `data/raw/`, `data/raw/download_manifest.csv` | Downloads the raw files and records their URLs and hashes. Not part of `run.sh`. |
| 1 | `01_clean_fsa.py` | FSA FAFSA completion archives | `data/derived/fsa_fafsa_hs.parquet` | One row per FSA record × class (2015–2026, all states). "<5" cells are missing with `*_lt5` flags. |
| 2 | `02_link_fsa_codes.py` | step 1, CCD and PSS directories | `fsa_school_codes.parquet` | Links pre-2021 FSA records (no school code) to NCES/PSS codes in tiers: exact, normalized, name only, year check, CCD/PSS exact/prefix/fuzzy, other year. |
| 3 | `03_build_fsa_school_panel.py` | steps 1–2, CCD directories | `fsa_school_panel.parquet` | Sums duplicate listings, gives each school a stable `school_id` across NCES ID changes, keeps the 15 study states. |
| 4 | `04_build_ccd_school_panel.py` | CCD files (directory, school characteristics, membership, lunch, staff), EDGE locale | `ccd_school_panel.parquet` | School × class characteristics for 2014-15 to 2024-25: grade-12 and total enrollment, race, FRL, teachers, school type, virtual status, locale. |
| 5 | `05_build_analysis_panel.py` | steps 3–4, `data/policy/state_mandates.csv`, `data/policy/co_grantee_schools.csv` | `policy_timing.parquet`, `analysis_panel.parquet`, `output/tables/sample_screens_by_state.csv` | First derives each state's policy timing: first covered class, reference class (e = −1), the two dose classes, post classes, and COVID / 2024 / preliminary flags. Then builds the public-school panel: completion rate (`fcr` = completions / grade-12 enrollment, capped at 1), dose, weight, controls, and the `f_*` screen flags. No rows are dropped. |
| 6 | `06_first_stage.py` | step 5 | `output/tables/first_stage_by_state.csv` | Estimates `fcr ~ dose×post + controls \| school + class` by state, weighted, clustered by school. Specs: `main`, `no_frl`, `deneault` (LA only). Colorado is excluded for now; Illinois's main spec has no FRL control. |

## Helper modules (imported, not run)

| Module | Used by | Contents |
|---|---|---|
| `config.py` | all | `ROOT`, `RAW`, `DERIVED`, `OUTPUT`, `STUDY_STATES` |
| `sources.py` | step 0 | Registry of raw files by group (`LA`, `IL`, `NJ`, `FSA`, `CCD`, `ACGR`, `EDGE`, `PSS`), plus the HTTP helpers (retries, browser-like headers) |
| `matching.py` | steps 2–4 | Name normalization and the strict fuzzy-match rule; `stable_ids`: one ID per school across NCES district moves |

## Notes

- The completion-rate denominator is CCD grade-12 enrollment, so the estimates from step 6 are preliminary until state graduate counts are added.
- The sample rules and control choices are recorded in `docs/DECISIONS.md`; variables are defined in `docs/codebook.md`.
- Tests for every step are in `tests/test_pipeline.py` (`uv run --locked pytest -q`).
