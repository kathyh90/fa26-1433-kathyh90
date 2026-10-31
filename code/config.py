"""Shared project paths. Scripts in code/ import from here: `from config import RAW`."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repository root (parent of code/)
RAW = ROOT / "data" / "raw"           # unchanged source files; never edited by scripts
DERIVED = ROOT / "data" / "derived"   # generated analysis tables (Parquet)
OUTPUT = ROOT / "output"              # generated tables, figures, and checks

# The 15 states with a FAFSA graduation requirement (two-letter postal codes).
STUDY_STATES = ["LA", "IL", "AL", "TX", "CO", "MD", "CA", "IN", "NH",
                "NE", "OK", "NY", "NJ", "CT", "PA"]
