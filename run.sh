#!/usr/bin/env bash
# Rebuild all derived data from the saved raw files in data/raw/.
# Raw files are fetched separately with code/00_download_raw_data.py (see README).
set -euo pipefail
cd "$(dirname "$0")"

uv run --locked python code/01_clean_fsa.py   # FSA FAFSA completion -> data/derived/fsa_fafsa_hs.parquet
uv run --locked python code/02_link_fsa_codes.py   # pre-2021 FSA records -> School Code, data/derived/fsa_school_codes.parquet
uv run --locked pytest -q
