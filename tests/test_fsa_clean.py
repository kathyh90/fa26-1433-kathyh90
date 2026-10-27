"""Tests for code/01_clean_fsa.py: parsing helpers and the derived FSA panel."""

import importlib.util
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from config import ROOT  # noqa: E402

# The script name starts with a digit, so load it by path.
_spec = importlib.util.spec_from_file_location("clean_fsa", ROOT / "code" / "01_clean_fsa.py")
clean_fsa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(clean_fsa)

PANEL = clean_fsa.OUT
needs_panel = pytest.mark.skipif(not PANEL.exists(), reason="run code/01_clean_fsa.py first")


def query(sql):
    """Run sql against the derived panel (as view p) and return the first value."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{PANEL.as_posix()}')")
    return con.execute(sql).fetchone()[0]


def test_parse_count():
    """Plain counts parse to int, "<5" is suppressed, blanks are missing."""
    assert clean_fsa.parse_count(" 17") == (17, False)
    assert clean_fsa.parse_count("<5") == (None, True)
    assert clean_fsa.parse_count(float("nan")) == (None, False)
    with pytest.raises(ValueError):
        clean_fsa.parse_count("n/a")


def test_find_columns():
    """Fixed and running-count headers are told apart by their period label."""
    cols = clean_fsa.find_columns([
        "Name",
        "Applications\nComplete\nJun  2018",
        "Applications\nSubmitted\nDec  2018",
        "Applications\nComplete\nJun30  2026",
        "Applications\nSubmitted\nDec31  2019",
    ])
    assert sorted(cols.values()) == [
        ("completed", "jun", 2018), ("completed", "jun30", 2026),
        ("submitted", "dec", 2018), ("submitted", "dec31", 2019),
    ]


@needs_panel
def test_one_row_per_file_row_and_class():
    """Each row of a source file appears at most once per class."""
    assert query("SELECT count(*) - count(DISTINCT (class_year, source_file, row_in_file)) FROM p") == 0


@needs_panel
def test_each_class_from_one_file():
    """Every class comes from exactly one source file."""
    assert query("SELECT max(n) FROM (SELECT count(DISTINCT source_file) n FROM p GROUP BY class_year)") == 1


@needs_panel
def test_classes_are_contiguous_from_2015():
    """Classes run without gaps from 2015 to the newest."""
    years = [r[0] for r in duckdb.sql(
        f"SELECT DISTINCT class_year FROM read_parquet('{PANEL.as_posix()}') ORDER BY 1").fetchall()]
    assert years[0] == 2015
    assert years == list(range(years[0], years[-1] + 1))


@needs_panel
def test_final_class_comes_from_a_later_file():
    """Fixed counts for class Y come from a file dated after June of Y."""
    assert query("SELECT count(*) FROM p WHERE kind = 'final' "
                 "AND snapshot_date <= make_date(class_year, 6, 30)") == 0


@needs_panel
def test_only_newest_class_is_preliminary():
    """At most one class is preliminary, and it is the newest class."""
    assert query("SELECT count(DISTINCT class_year) FROM p WHERE kind = 'preliminary'") <= 1
    assert query("SELECT count(*) FROM p WHERE kind = 'preliminary' "
                 "AND class_year < (SELECT max(class_year) FROM p)") == 0


@needs_panel
def test_completed_never_exceeds_submitted():
    """Completed applications are a subset of submitted applications."""
    assert query("SELECT count(*) FROM p WHERE completed_jun > submitted_jun "
                 "OR completed_dec > submitted_dec") == 0


@needs_panel
def test_suppressed_cells_are_missing():
    """A "<5" flag always goes with a missing count."""
    assert query("SELECT count(*) FROM p WHERE completed_jun_lt5 AND completed_jun IS NOT NULL") == 0
    assert query("SELECT count(*) FROM p WHERE submitted_jun_lt5 AND submitted_jun IS NOT NULL") == 0


@needs_panel
def test_no_placeholder_school_codes():
    """All-zero placeholder codes have been set to missing."""
    assert query("SELECT count(*) FROM p WHERE regexp_full_match(school_code, '0+')") == 0
