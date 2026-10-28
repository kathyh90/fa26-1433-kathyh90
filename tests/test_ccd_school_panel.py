"""Tests for code/05_build_ccd_school_panel.py: the school x year CCD panel."""

import importlib.util
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from config import ROOT  # noqa: E402

# The script name starts with a digit, so load it by path.
_spec = importlib.util.spec_from_file_location("ccd_panel", ROOT / "code" / "05_build_ccd_school_panel.py")
ccd_panel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ccd_panel)

OUT = ccd_panel.OUT
needs_panel = pytest.mark.skipif(not OUT.exists(), reason="run code/05_build_ccd_school_panel.py first")


def query(sql):
    """Run sql against the CCD panel (view c) and return the first value."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW c AS SELECT * FROM read_parquet('{OUT.as_posix()}')")
    return con.execute(sql).fetchone()[0]


def test_grade_count():
    """Grade spans count both ends, with PK and KG as grades."""
    assert ccd_panel.grade_count("09", "12") == 4
    assert ccd_panel.grade_count("PK", "12") == 14
    assert ccd_panel.grade_count("KG", "05") == 6
    assert ccd_panel.grade_count("M", "12") is ccd_panel.pd.NA


def test_negative_codes_become_missing():
    """CCD's negative codes (missing, not applicable, suppressed) are not counts."""
    s = ccd_panel.num(ccd_panel.pd.Series(["12", "-1", "-2", "-9", "0"]))
    assert s.isna().tolist() == [False, True, True, True, False]


@needs_panel
def test_one_row_per_school_and_year():
    """Each school appears at most once per class year."""
    assert query("SELECT count(*) - count(DISTINCT (school_id, class_year)) FROM c") == 0


@needs_panel
def test_only_study_states_and_years():
    """The panel holds the 15 study states and class years 2015-2025."""
    states = ", ".join(f"'{s}'" for s in ccd_panel.STUDY_STATES)
    assert query(f"SELECT count(*) FROM c WHERE state NOT IN ({states})") == 0
    assert query("SELECT min(class_year) FROM c") == 2015
    assert query("SELECT max(class_year) FROM c") == 2025


@needs_panel
def test_counts_are_consistent():
    """Grade 12 and race counts never exceed total enrollment; FRL parts never exceed the total."""
    assert query("SELECT count(*) FROM c WHERE enroll_g12 > enroll_total") == 0
    assert query("SELECT count(*) FROM c WHERE race_white + race_black + race_hispanic > enroll_total") == 0
    assert query("SELECT count(*) FROM c WHERE frl_free + frl_reduced > frl_total + 1") == 0


@needs_panel
def test_school_types_standardized():
    """Every CCD school type maps to a standard label."""
    assert query("SELECT count(*) FROM c WHERE school_type IS NOT NULL AND school_type_std IS NULL") == 0
