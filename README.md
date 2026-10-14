# Research project title

Replace this text with a one-sentence description of the research question.

## Reproducing the project

Document the software requirements and the single command needed to reproduce the analysis. Until the project has a one-command workflow, list the scripts in the exact order they should be run.

1. `python code/00_download_raw_data.py [GROUPS...]` downloads the files registered in `code/sources.py` (standard library only). Groups are states (`LA`, `IL`, `NJ`) saved to `data/raw/<state>/`, and national sources (`FSA` FAFSA completion archives, `CCD` NCES school files, `ACGR` EDFacts graduation rates via the Urban Institute, `EDGE` NCES school locations and locale codes) saved to `data/raw/US/`. All groups together are about 4.4 GB. Finished files are skipped on rerun, so an interrupted download can be resumed with the same command. Each file's URL, access time, and SHA-256 hash are recorded in `data/raw/download_manifest.csv`, which is tracked in Git.
   - Several CCD Membership zips use Deflate64 compression, which Python's `zipfile` cannot read; extract them with `unzip` or another tool that supports it.

## Repository structure

| Directory | Purpose |
|---|---|
| `code/` | Scripts used to acquire, clean, analyze, and visualize data |
| `data/raw/` | Original source data; ignored by Git unless explicitly allowed |
| `docs/` | Project notes, including `source-notes.md` (URL, download date, release, and filters for each data source) |
| `data/derived/` | Data created by the project's code; ignored by Git unless explicitly allowed |
| `output/` | Generated figures, tables, and other results |
| `paper/` | Paper source files and rendered drafts |

## Working practices

- Keep the `main` branch in a usable state.
- Use GitHub issues to record consequential tasks, questions, and decisions.
- Use short-lived branches to test important alternatives, then record the conclusion in the related issue.
- Commit small, coherent changes with descriptive messages.
- Never commit passwords, API keys, restricted data, or personally identifiable information.
- Update this README whenever the reproduction steps or directory structure change.
