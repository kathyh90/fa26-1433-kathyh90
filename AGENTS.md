# AGENTS.md

**Project:** TODO: one-line description of the research question.

## Folder layout

```
README.md         Setup, data access, run command, expected outputs
AGENTS.md         Rules for coding agents (this file)
pyproject.toml    Python dependencies (managed by uv)
uv.lock           Exact locked versions; commit with pyproject.toml
.python-version   Pinned Python version
run.sh            Full rebuild from saved inputs
code/             Scripts; code/config.py defines all shared paths
data/raw/         Unchanged source files (not in Git)
data/derived/     Generated analysis data (not in Git)
docs/             Source notes, codebook, decisions, progress log
output/           Generated tables, figures, and checks
paper/            Paper source files and rendered drafts
tests/            pytest tests
```

## Rules

- Run everything from the repository root with `uv run --locked`.
- Add packages only with `uv add PACKAGE`; never edit `uv.lock` by hand or use `pip install`.
- Paths come from `code/config.py` (`ROOT`, `RAW`, `DERIVED`, `OUTPUT`). No absolute or machine-specific paths.
- Never edit, move, or delete anything in `data/raw/`.
- All transformations live in scripts. No manual edits to data or generated output.
- Store tables as Parquet in `data/derived/` and query them with DuckDB.
- Report row counts before and after every merge and filter, with the reason for any dropped rows.
- Never modify tests to make them pass. Fix the code, or explain why the test is wrong and ask.
- Update `docs/codebook.md` whenever variables are added, removed, or redefined.
- Record consequential decisions in `docs/DECISIONS.md`.

## Commands

- Tests: `uv run --locked pytest -q`
- Full rebuild: `bash run.sh`
