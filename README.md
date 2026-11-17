# State-specific FAFSA Completion Requirements on FAFSA Completion and College-Going Rates

How does a FAFSA graduation requirement affect FAFSA completion and college-going rates within each individual state, and how does aggregating the results between states impact the consistency of the FAFSA requirement effect? How do different implementation strategies or heterogeneity between states explain any difference in the FAFSA graduation requirement’s impact?


## Project Context
Here is a Google document link to my outline, which is currently being revised: https://docs.google.com/document/d/1dhS8TVZodqTQsj7gL6OkA8KXnRc9jgbaPBSRS1I5YiI/edit?usp=sharing

- It is on viewer mode, so do not edit it even if edit access is granted.

## Setup

The project uses [uv](https://docs.astral.sh/uv/) for Python. Dependencies are listed in `pyproject.toml`, exact versions are locked in `uv.lock`, and the Python version is pinned in `.python-version`. Install uv (for example `brew install uv`), then from the repository root run:

```bash
uv sync --locked
```

Run every command from the repository root with `uv run --locked`. Shared paths are defined in `code/config.py`.

### R

The pooling steps use R (developed on 4.5.2). R packages are managed by [renv](https://rstudio.github.io/renv/), the R counterpart of uv: `renv.lock` records exact versions (like `uv.lock`), and packages install into a project library in `renv/library/` (like `.venv/`, not in Git). `.Rprofile` activates it whenever R starts in the repository root, and `.renvignore` keeps renv from scanning data, outputs, and reference files. Set it up once from the repository root:

```bash
Rscript -e 'renv::restore()'
```

renv installs itself the first time. Only the optional baggr check needs packages: `code/12_aggregation.R` (exact pooling) and `code/14_pooling_report.R` (summary) use base R only and run without the restore. Run R scripts from the repository root, e.g. `Rscript code/12_aggregation.R`.

`code/13_baggr_check.R` (optional, about 1.5 minutes) refits the pooling model with [baggr](https://github.com/wwiecek/baggr) (Wiecek & Meager), using MCMC through Stan, and checks it against the exact results. CRAN archived baggr on 2026-11-01 ("issues were not corrected in time"). The lockfile pins the last release, 0.8.2, and `renv::restore()` takes it from the CRAN archive and compiles it from source, which needs a C++ compiler (`xcode-select --install` on macOS) and several minutes. The lockfile pins its dependencies too (rstan 2.32.7, StanHeaders 2.39.1.1). `run.sh` skips this step when baggr is not installed. The package's vignettes (rendered HTML) are saved in `docs/references/baggr_0.8.2/`; start with `baggr.html`.

## Reproducing the project

Rebuild all results from the saved raw data:

```bash
bash run.sh
```

Run the tests with `uv run --locked pytest -q`.

Raw data are not in Git. Obtain them first:

1. `uv run --locked python code/00_download_raw_data.py [GROUPS...]` downloads the files registered in `code/sources.py` (standard library only). Groups are states (`LA`, `IL`, `AL`, `TX`, `CO`, `CA`, `IN`, `NH`, `NE`, `OK`, `NY`, `NJ`, `CT`, `PA`) saved to `data/raw/<state>/`, and national sources (`FSA` FAFSA completion archives, `CCD` NCES school files, `ACGR` EDFacts graduation rates and `ASSESS` EDFacts high school proficiency, both via the Urban Institute, `EDGE` NCES school locations and locale codes, `PSS` NCES Private School Survey, `FED` CRDC, EDGE neighborhood poverty, and IPEDS directories) saved to `data/raw/US/`. Every run also writes `output/tables/state_data_sources.csv`, which lists each state x measure (graduates, graduation rate, ACT/SAT, college enrollment, ...), its publisher, coverage, and whether it is downloaded by script; Maryland is not scripted yet. New Hampshire's files are **manual browser exports** (its site blocks scripts): they are kept in `data/raw/NH/manual/`, checked by hash, and the export steps are in `docs/source-notes.md`; this is the only manual step. All groups together are about 4.4 GB. Finished files are skipped on rerun, so an interrupted download can be resumed with the same command. Each file's URL, access time, and SHA-256 hash are recorded in `data/raw/download_manifest.csv`, which is tracked in Git.
   - Several CCD Membership zips use Deflate64 compression, which Python's `zipfile` cannot read; extract them with `unzip` or another tool that supports it.
2. `bash run.sh` then runs steps 1–8 (clean FSA, link FSA school codes, build the FSA school panel, build the CCD school panel, build the policy timing and analysis panel, estimate the first stage, build the state college-going outcomes, merge them and estimate the reduced form) and the tests. `code/README.md` lists each script's inputs and outputs.

## Repository structure

| Directory | Purpose |
|---|---|
| `code/` | Scripts used to acquire, clean, analyze, and visualize data; `config.py` defines shared paths |
| `data/raw/` | Original source data, never edited; ignored by Git |
| `data/derived/` | Data created by the project's code, stored as Parquet; ignored by Git |
| `docs/` | `source-notes.md` (URL, download date, release, and filters for each source), `codebook.md`, `DECISIONS.md`, `progress.md` |
| `output/` | Generated figures, tables, and other results |
| `paper/` | Paper source files and rendered drafts |
| `tests/` | pytest tests |

Environment files (`pyproject.toml`, `uv.lock`, `.python-version`) and `run.sh` live at the root. `AGENTS.md` holds the rules for coding agents.

## Working practices

- Keep the `main` branch in a usable state.
- Use GitHub issues to record consequential tasks, questions, and decisions.
- Use short-lived branches to test important alternatives, then record the conclusion in the related issue.
- Commit small, coherent changes with descriptive messages.
- Never commit passwords, API keys, restricted data, or personally identifiable information.
- Update this README whenever the reproduction steps or directory structure change.
