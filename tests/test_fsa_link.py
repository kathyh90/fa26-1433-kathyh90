"""Tests for code/02_link_fsa_codes.py: name normalization and the code crosswalk."""

import importlib.util
import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from config import ROOT  # noqa: E402

# The script name starts with a digit, so load it by path.
_spec = importlib.util.spec_from_file_location("link_fsa", ROOT / "code" / "02_link_fsa_codes.py")
link_fsa = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(link_fsa)

CODES = link_fsa.OUT
PANEL = link_fsa.PANEL
needs_codes = pytest.mark.skipif(not CODES.exists(), reason="run code/02_link_fsa_codes.py first")


def query(sql):
    """Run sql against the crosswalk (view c) and FSA panel (view p); return the first value."""
    con = duckdb.connect()
    con.execute(f"CREATE VIEW c AS SELECT * FROM read_parquet('{CODES.as_posix()}')")
    con.execute(f"CREATE VIEW p AS SELECT * FROM read_parquet('{PANEL.as_posix()}')")
    return con.execute(sql).fetchone()[0]


def test_normalize_spelling_variants():
    """Spelling variants seen in FSA files normalize to the same string."""
    n = link_fsa.normalize
    assert n("HOOVER HIGH SCH") == n("HOOVER HIGH SCHOOL")
    assert n("ST. AMANT") == n("ST AMANT") == n("SAINT AMANT")
    assert n("GATEWAY TECH H S") == n("GATEWAY TECHNOLOGY HIGH SCHOOL")
    assert n("AN-NOOR ACADEMY") == n("AN NOOR ACAD")
    assert n(None) is None


def test_normalize_keeps_words_apart():
    """Abbreviations expand only as whole words."""
    assert link_fsa.normalize("STANTON HS") == "STANTON HIGH SCHOOL"
    assert link_fsa.normalize("SCHOLARS ACAD") == "SCHOLARS ACADEMY"


@needs_codes
def test_one_row_per_panel_record():
    """The crosswalk has exactly one row for every FSA panel record."""
    assert query("SELECT count(*) FROM c") == query("SELECT count(*) FROM p")
    assert query("SELECT count(*) - count(DISTINCT (class_year, source_file, row_in_file)) FROM c") == 0


@needs_codes
def test_fsa_codes_are_kept():
    """Records that already carry a School Code keep it unchanged."""
    assert query("SELECT count(*) FROM c WHERE school_code IS NOT NULL "
                 "AND (link_tier <> 'fsa_code' OR code_linked <> school_code)") == 0


@needs_codes
def test_tiers_are_known_and_consistent():
    """Every record has a known tier, and only linked tiers carry a code."""
    assert query("SELECT count(*) FROM c WHERE link_tier NOT IN ('fsa_code', 'exact', 'normalized', "
                 "'name_only', 'ccd_exact', 'ccd_prefix', 'ccd_name_only', 'ccd_fuzzy', "
                 "'pss_exact', 'pss_prefix', 'pss_name_only', 'pss_fuzzy', 'other_year', "
                 "'ccd_relinked', 'ambiguous_resolved', "
                 "'name_only_rejected', 'ambiguous', 'unlinked')") == 0
    assert query("SELECT count(*) FROM c WHERE link_tier IN ('name_only_rejected', 'ambiguous', 'unlinked') "
                 "AND code_linked IS NOT NULL") == 0
    assert query("SELECT count(*) FROM c WHERE link_tier IN ('exact', 'normalized', 'name_only', "
                 "'ccd_exact', 'ccd_prefix', 'ccd_name_only', 'ccd_fuzzy', "
                 "'pss_exact', 'pss_prefix', 'pss_name_only', 'pss_fuzzy', 'other_year', "
                 "'ccd_relinked', 'ambiguous_resolved') "
                 "AND code_linked IS NULL") == 0


@needs_codes
def test_name_only_links_do_not_take_claimed_codes():
    """A name-only link never shares its class and code with an exact or normalized link."""
    assert query("""
        SELECT count(*) FROM c a JOIN c b USING (class_year, code_linked)
        WHERE a.link_tier = 'name_only' AND b.link_tier IN ('exact', 'normalized')
    """) == 0


@needs_codes
def test_ccd_links_only_before_fsa_codes():
    """CCD and other-year links are used only for classes before FSA's own codes start."""
    assert query("""
        SELECT count(*) FROM c
        WHERE link_tier IN ('ccd_exact', 'ccd_prefix', 'ccd_name_only', 'other_year')
          AND class_year >= (SELECT min(class_year) FROM c WHERE school_code IS NOT NULL)
    """) == 0


@needs_codes
def test_ccd_match_recorded():
    """Every CCD link records the CCD name it matched, and only CCD links do."""
    assert query("SELECT count(*) FROM c WHERE link_tier LIKE 'ccd_%' AND ccd_name IS NULL") == 0
    assert query("SELECT count(*) FROM c WHERE link_tier NOT LIKE 'ccd_%' AND ccd_name IS NOT NULL") == 0


@needs_codes
def test_late_tier_links_do_not_take_claimed_codes():
    """CCD and other-year links never share their class and code with an earlier-tier link."""
    assert query("""
        SELECT count(*) FROM c a JOIN c b USING (class_year, code_linked)
        WHERE a.link_tier IN ('ccd_exact', 'ccd_prefix', 'ccd_name_only', 'other_year')
          AND b.link_tier IN ('exact', 'normalized', 'name_only')
    """) == 0


def test_fuzzy_accepts_network_prefixed_names():
    """A charter campus matches its CCD name with the network prefix added."""
    n = link_fsa.normalize
    assert link_fsa.fuzzy_coverage(n("PRITZKER COLLEGE PREP"), n("Noble St Chtr-Pritzker Col Prep"),
                                   n("CHICAGO")) >= link_fsa.FUZZY_COVERAGE


def test_fuzzy_rejects_known_false_matches():
    """Names sharing only a city name, generic words, or a look-alike word do not match."""
    n, cov = link_fsa.normalize, link_fsa.fuzzy_coverage
    cases = [
        ("LAFAYETTE CHRISTIAN ACADEMY", "UPPER LAFAYETTE ACADEMY", "LAFAYETTE"),
        ("MARION ACADEMY", "Francis Marion School", "MARION"),
        ("CENTRAL HIGH SCHOOL - WEST CAMPUS", "Central High East Campus", "FRESNO"),
        ("SNELL COMMUNITY SCHOOL", "County Community", "SAN JOSE"),
        ("VALLEY CHRISTIAN HIGH SCHOOL", "MIDVALLEY ACADEMY - BROWNSVILLE CHARTER H S", "BROWNSVILLE"),
    ]
    for fsa, directory, city in cases:
        assert cov(n(fsa), n(directory), n(city)) < link_fsa.FUZZY_COVERAGE, fsa


@needs_codes
def test_directory_links_use_matching_id_type():
    """CCD links carry 12-character NCES IDs and PSS links 8-character PSS IDs."""
    assert query("SELECT count(*) FROM c WHERE link_tier LIKE 'ccd_%' AND length(code_linked) <> 12") == 0
    assert query("SELECT count(*) FROM c WHERE link_tier LIKE 'pss_%' AND length(code_linked) <> 8") == 0


@needs_codes
def test_pss_match_recorded():
    """Every PSS link records the PSS name it matched, and only PSS links do."""
    assert query("SELECT count(*) FROM c WHERE link_tier LIKE 'pss_%' AND pss_name IS NULL") == 0
    assert query("SELECT count(*) FROM c WHERE link_tier NOT LIKE 'pss_%' AND pss_name IS NOT NULL") == 0


@needs_codes
def test_candidate_codes_only_on_open_records():
    """Offered codes are kept only for records that ended up without a code."""
    assert query("SELECT count(*) FROM c WHERE candidate_code IS NOT NULL "
                 "AND link_tier NOT IN ('name_only_rejected', 'ambiguous', 'unlinked')") == 0
    assert query("SELECT count(*) FROM c WHERE (candidate_code IS NULL) <> (candidate_tier IS NULL)") == 0

