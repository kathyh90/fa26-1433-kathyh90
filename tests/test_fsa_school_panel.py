"""Tests for code/03_build_fsa_school_panel.py: the school x class FSA panel."""

import importlib.util
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from config import ROOT  # noqa: E402

# The script name starts with a digit, so load it by path.
_spec = importlib.util.spec_from_file_location("school_panel", ROOT / "code" / "03_build_fsa_school_panel.py")
school_panel = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(school_panel)

OUT = school_panel.OUT
needs_panel = pytest.mark.skipif(not OUT.exists(), reason="run code/03_build_fsa_school_panel.py first")


def query(sql):
    """Run sql against the school panel (view s) and FSA records (view p); return the first value."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{OUT.as_posix()}')")
    con.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{school_panel.PANEL.as_posix()}')")
    return con.execute(sql).fetchone()[0]


def test_sector_from_code_format():
    """Codes are classified by format: NCES (12), FSA-only (FN), PSS (8)."""
    assert school_panel.sector("220019700953") == "public"
    assert school_panel.sector("02FN00011") == "no_nces_id"
    assert school_panel.sector("A9101574") == "private"


@needs_panel
def test_one_row_per_school_and_class():
    """Each school appears at most once per class."""
    assert query("SELECT count(*) - count(DISTINCT (school_id, class_year)) FROM s") == 0


@needs_panel
def test_completions_kept_from_fsa():
    """The panel keeps nearly all of the study states' FSA completions and never adds any."""
    states = ", ".join(f"'{s}'" for s in school_panel.STUDY_STATES)
    kept = query("SELECT sum(completed_jun) FROM s")
    total = query(f"SELECT sum(completed_jun) FROM p WHERE state IN ({states})")
    assert kept <= total
    assert kept / total > 0.99


@needs_panel
def test_completed_never_exceeds_submitted():
    """Summed completions never exceed summed submissions."""
    assert query("SELECT count(*) FROM s WHERE completed_jun > submitted_jun "
                 "OR completed_dec > submitted_dec") == 0


@needs_panel
def test_single_record_suppressed_cells_are_missing():
    """For a school with one record, a '<5' flag goes with a missing count."""
    assert query("SELECT count(*) FROM s WHERE n_records = 1 "
                 "AND completed_jun_lt5 AND completed_jun IS NOT NULL") == 0


@needs_panel
def test_network_records_not_added_to_campuses():
    """Network-level records (names ending in SCHOOLS) are never added as duplicate listings."""
    df = school_panel.load_records()
    school_panel.absorb_duplicates(df)
    added = df[df["assign_rule"] == "duplicate_listing"]
    assert not added["name_norm"].str.contains(school_panel.NETWORK, regex=True, na=False).any()


@needs_panel
def test_only_study_states():
    """The panel holds only the 15 study states."""
    states = ", ".join(f"'{s}'" for s in school_panel.STUDY_STATES)
    assert query(f"SELECT count(*) FROM s WHERE state NOT IN ({states})") == 0


@needs_panel
def test_sector_matches_school_id():
    """Sector agrees with the school_id format in every row."""
    assert query("SELECT count(*) FROM s WHERE (length(school_id) = 12) <> (sector = 'public')") == 0
