#!/usr/bin/env bash
# Rebuild all derived data from the saved raw files in data/raw/.
# Raw files are fetched separately with code/00_download_raw_data.py (see README).
set -euo pipefail
cd "$(dirname "$0")"

uv run --locked python code/01_clean_fsa.py   # FSA FAFSA completion -> data/derived/fsa_fafsa_hs.parquet
uv run --locked python code/02_link_fsa_codes.py   # pre-2021 FSA records -> School Code, data/derived/fsa_school_codes.parquet
uv run --locked python code/03_build_fsa_school_panel.py   # school x class FSA panel, data/derived/fsa_school_panel.parquet
uv run --locked python code/04_build_ccd_school_panel.py   # CCD school characteristics, data/derived/ccd_school_panel.parquet
uv run --locked python code/05_build_analysis_panel.py   # policy timing + first-stage analysis panel with sample flags, data/derived/policy_timing.parquet and analysis_panel.parquet
uv run --locked python code/06_first_stage.py   # first stage by state, output/tables/first_stage_by_state.csv
uv run --locked pytest -q
