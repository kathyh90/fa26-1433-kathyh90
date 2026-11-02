"""Shared project paths. Scripts in code/ import from here: `from config import RAW`."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repository root (parent of code/)
RAW = ROOT / "data" / "raw"           # unchanged source files; never edited by scripts
DERIVED = ROOT / "data" / "derived"   # generated analysis tables (Parquet)
OUTPUT = ROOT / "output"              # generated tables, figures, and checks

# The 15 states with a FAFSA graduation requirement (two-letter postal codes),
# in order of mandate adoption. Tables, source sections, and docs use this order.
STUDY_STATES = ["LA", "IL", "AL", "MD", "TX", "CO", "CA", "IN", "NH",
                "NE", "OK", "NY", "NJ", "CT", "PA"]

# State FIPS codes of the study states (for APIs keyed by FIPS).
STATE_FIPS = {"LA": 22, "IL": 17, "AL": 1, "MD": 24, "TX": 48, "CO": 8, "CA": 6, "IN": 18,
              "NH": 33, "NE": 31, "OK": 40, "NY": 36, "NJ": 34, "CT": 9, "PA": 42}
