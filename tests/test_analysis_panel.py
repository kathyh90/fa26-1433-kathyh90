"""Tests for code/06_build_analysis_panel.py: the first-stage analysis panel."""

import importlib.util
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from config import ROOT  # noqa: E402

# The script name starts with a digit, so load it by path.
_spec = importlib.util.spec_from_file_location("analysis_panel", ROOT / "code" / "06_build_analysis_panel.py")
analysis_panel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(analysis_panel)

OUT = analysis_panel.OUT
needs_panel = pytest.mark.skipif(not OUT.exists(), reason="run code/06_build_analysis_panel.py first")


def query(sql):
    """Run sql against the analysis panel (view a) and return the first value."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW a AS SELECT * FROM read_parquet('{OUT.as_posix()}')")
    return con.execute(sql).fetchone()[0]


@needs_panel
def test_one_row_per_school_and_class():
    """Each school appears at most once per class."""
    assert query("SELECT count(*) - count(DISTINCT (school_id, class_year)) FROM a") == 0


@needs_panel
def test_fcr_between_zero_and_one():
    """The completion rate is capped at 1 and never negative."""
    assert query("SELECT count(*) FROM a WHERE fcr < 0 OR fcr > 1") == 0


@needs_panel
def test_dose_is_one_minus_mean_dose_fcr():
    """Dose equals 1 minus the mean completion rate over the two dose classes."""
    assert query("""
        WITH d AS (SELECT school_id, any_value(dose) AS dose,
                          avg(fcr) FILTER (WHERE class_year IN (dose_class_1, dose_class_2)) AS m
                   FROM a WHERE dose IS NOT NULL GROUP BY school_id)
        SELECT count(*) FROM d WHERE abs(dose - (1 - m)) > 1e-9
    """) == 0


@needs_panel
def test_louisiana_window_is_2015_to_2019():
    """Louisiana's estimation window is e = -3 ... +1, i.e. 2015-2019 (FSA starts in 2015)."""
    assert query("SELECT min(class_year) FROM a WHERE state = 'LA' AND in_window") == 2015
    assert query("SELECT max(class_year) FROM a WHERE state = 'LA' AND in_window") == 2019


@needs_panel
def test_balanced_schools_have_every_window_class():
    """A balanced school has a completion rate in every class its window needs."""
    assert query("""
        SELECT count(*) FROM (
            SELECT school_id, any_value(window_classes_needed) AS need,
                   count(*) FILTER (WHERE in_window AND fcr IS NOT NULL) AS have
            FROM a WHERE f_balanced GROUP BY school_id) WHERE have <> need
    """) == 0


@needs_panel
def test_post_only_for_treated_schools():
    """Untreated rows (non-grantee Colorado schools) are never post-mandate."""
    assert query("SELECT count(*) FROM a WHERE post AND NOT treated") == 0
