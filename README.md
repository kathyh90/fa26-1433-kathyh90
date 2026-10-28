# Research project title

Replace this text with a one-sentence description of the research question.

## Setup

The project uses [uv](https://docs.astral.sh/uv/) for Python. Dependencies are listed in `pyproject.toml`, exact versions are locked in `uv.lock`, and the Python version is pinned in `.python-version`. Install uv (for example `brew install uv`), then from the repository root run:

```bash
uv sync --locked
```

Run every command from the repository root with `uv run --locked`. Shared paths are defined in `code/config.py`.

## Reproducing the project

Rebuild all results from the saved raw data:

```bash
bash run.sh
```

Run the tests with `uv run --locked pytest -q`.

Raw data are not in Git. Obtain them first:

1. `uv run --locked python code/00_download_raw_data.py [GROUPS...]` downloads the files registered in `code/sources.py` (standard library only). Groups are states (`LA`, `IL`, `NJ`) saved to `data/raw/<state>/`, and national sources (`FSA` FAFSA completion archives, `CCD` NCES school files, `ACGR` EDFacts graduation rates via the Urban Institute, `EDGE` NCES school locations and locale codes, `PSS` NCES Private School Survey) saved to `data/raw/US/`. All groups together are about 4.4 GB. Finished files are skipped on rerun, so an interrupted download can be resumed with the same command. Each file's URL, access time, and SHA-256 hash are recorded in `data/raw/download_manifest.csv`, which is tracked in Git.
   - Several CCD Membership zips use Deflate64 compression, which Python's `zipfile` cannot read; extract them with `unzip` or another tool that supports it.
2. `bash run.sh` then builds the derived data: `code/01_clean_fsa.py` turns the FSA archives into `data/derived/fsa_fafsa_hs.parquet` (school × graduating class, classes of 2015 on).

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
