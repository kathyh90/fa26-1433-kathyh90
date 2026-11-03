"""Tests for the full pipeline, grouped by script: config, 01-07.

Tests that read a derived file are skipped until the script that writes it has run.
"""

import importlib.util
import re
import sys
from io import StringIO
from pathlib import Path

import duckdb
import pandas as pd
import pytest

# Make code/ importable so tests can `import config` like the scripts do.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from config import DERIVED, OUTPUT, RAW, ROOT, STUDY_STATES  # noqa: E402
import sources  # noqa: E402


def load(name, script):
    """Load a pipeline script as a module (script names start with a digit, so load by path)."""
    spec = importlib.util.spec_from_file_location(name, ROOT / "code" / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def needs(path, script):
    """Skip a test until `script` has written `path`."""
    return pytest.mark.skipif(not path.exists(), reason=f"run code/{script} first")


def sql_list(values):
    """Format values as a SQL list of string literals, e.g. ['a', 'b'] -> 'a', 'b'."""
    return ", ".join(f"'{v}'" for v in values)


def query(sql, **views):
    """Create one view per name=parquet path, run sql, and return the first value."""
    con = duckdb.connect()
    for name, path in views.items():
        con.execute(f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{path.as_posix()}')")
    return con.execute(sql).fetchone()[0]


clean_fsa = load("clean_fsa", "01_clean_fsa.py")
link_fsa = load("link_fsa", "02_link_fsa_codes.py")
school_panel = load("school_panel", "03_build_fsa_school_panel.py")
ccd_panel = load("ccd_panel", "04_build_ccd_school_panel.py")
analysis_panel = load("analysis_panel", "05_build_analysis_panel.py")
first_stage = load("first_stage", "06_first_stage.py")
state_outcomes = load("state_outcomes", "07_build_state_outcomes.py")
reduced_form = load("reduced_form", "08_reduced_form.py")
import state_files  # noqa: E402


# --- code/config.py: shared paths -------------------------------------------

class TestConfig:
    def test_root_is_repo_root(self):
        """ROOT is the directory that holds pyproject.toml."""
        assert (ROOT / "pyproject.toml").is_file()

    def test_paths_are_inside_root(self):
        """RAW, DERIVED, and OUTPUT all live under ROOT."""
        for path in (RAW, DERIVED, OUTPUT):
            assert path.is_relative_to(ROOT)


# --- code/sources.py: source-list helpers and the catalog (no network) -------

class TestSources:
    def test_year_label(self):
        """The first year or year range in a filename becomes the label."""
        assert sources.year_label("2012-2017-state-lea-school-act-summary.xlsx") == "2012-2017"
        assert sources.year_label("act-scores---class-of-2014.xlsx") == "2014"
        assert sources.year_label("24-25_gradrate.zip") == "24-25"
        assert sources.year_label("Agencies.csv") == ""

    def test_local_name(self):
        """Local names drop the query, unquote, and replace spaces."""
        url = "https://x.gov/docs/graduates%20public%20by%20school%202024-25.xlsx?language_id=1"
        assert sources.local_name(url) == "graduates_public_by_school_2024-25.xlsx"

    def test_page_links_filters_by_filename(self):
        """page_links keeps matching links once, made absolute, without the query."""
        html = ('<a href="/f/a-2019.xlsx?v=1">a</a> <a href="/f/a-2019.xlsx?v=2">dup</a>'
                '<a href="b.pdf">b</a> <a href="https://y.org/c-2020.xlsx">c</a>')
        assert sources.page_links("https://x.gov/p/", r"\.xlsx$", html=html) == [
            "https://x.gov/f/a-2019.xlsx", "https://y.org/c-2020.xlsx"]

    def test_colorado_patterns_keep_school_workbooks(self):
        """CO patterns (matched on served filenames) keep the school-level graduation and
        matriculation workbooks and skip trend, school-type, still-enrolled, and summary files."""
        grad = ["2018-2019_STATE-LEA-SCH_GraduationCompletion_DataReleaseWorkbook.xlsx",
                "2022-2023_GraduationandCompletion_CombinedRelease_PrivacyApplied.xlsx",
                "2023-2024_GraduationCompletionRates_StateDistrictSchool_PRIVACYAPPLIED.xlsx",
                "2024-2025_Graduation-CompletionRates_PRIVACY-APPLIED.xlsx"]
        skip = ["2024-2025_Graduation-Completion_State_Trends.xlsx",
                "2024-2025_Graduation-Completion_STATE_District-School-Types.xlsx",
                "2022-2023_GraduationCompletion_STATE_Summary.docx",
                "AYG_2025_4-year_StillEnrolledRates_PRIVACY-APPLIED.xlsx"]
        assert all(re.search(sources.CO_GRAD, n, re.I) for n in grad)
        assert not any(re.search(sources.CO_GRAD, n, re.I) for n in skip)
        assert re.search(sources.CO_MATRIC, "2023MatriculationRatesbyStateDistrictSchool.xlsx", re.I)
        assert re.search(sources.CO_MATRIC, "2025_Matriculation-StateDistrictSchool_forSBErelease.xlsx", re.I)

    def test_check_flags_changed_or_missing_manual_exports(self, tmp_path):
        """--check passes an unchanged manual export and flags one that changed or is missing."""
        download = load("download", "00_download_raw_data.py")
        f = tmp_path / "export.xlsx"
        f.write_bytes(b"PK\x03\x04original")
        row = {"kind": "data", "status": "manual", "sha256": download.sha256(f)}
        assert download.check_existing({str(f): row}) == []
        f.write_bytes(b"PK\x03\x04edited")
        assert download.check_existing({str(f): row})[0][1].startswith("manual export changed")
        f.unlink()
        assert download.check_existing({str(f): row})[0][1] == "manual export missing"

    def test_review_parsing_helpers(self):
        """State-file values: bounds become their bound and are flagged; codes become
        NaN; school-year labels give the spring class; LA site codes may be alphanumeric."""
        review = state_files
        assert [review.value(v) for v in [">99", ">= 99", "≤1", "45.2%", "1,234"]] == [99, 99, 1, 45.2, 1234]
        assert all(pd.isna(review.value(v)) for v in ["~", "NR", "n/a", ""])
        assert review.CENSORED.match(">= 99") and not review.CENSORED.match("99")
        assert review.class_of("2015-2016") == review.class_of("2015-16") == 2016
        assert all(review.LA_SITE.fullmatch(c) for c in ["001005", "WBB001", "3A1001"])
        assert not review.LA_SITE.fullmatch("Parish")

    def test_prune_drops_rows_of_deleted_files_only(self, tmp_path, monkeypatch):
        """--prune removes manifest rows whose file is gone, keeps present files and
        manual exports (a missing manual export is an error for --check instead)."""
        download = load("download", "00_download_raw_data.py")
        monkeypatch.setattr(download, "save_manifest", lambda rows: None)
        kept = tmp_path / "kept.xlsx"
        kept.write_bytes(b"PK\x03\x04x")
        manifest = {str(kept): {"status": "downloaded"}, str(tmp_path / "gone.xlsx"): {"status": "downloaded"},
                    str(tmp_path / "manual.xlsx"): {"status": "manual"}}
        download.prune(manifest)
        assert set(manifest) == {str(kept), str(tmp_path / "manual.xlsx")}

    def test_catalog_covers_every_study_state(self):
        """Every study state has at least one catalog row, and each row has every field."""
        assert set(STUDY_STATES) <= {row[0] for row in sources.CATALOG}
        assert all(len(row) == len(sources.CATALOG_FIELDS) for row in sources.CATALOG)

    def test_content_check_catches_error_pages(self, tmp_path):
        """The download check rejects HTML saved as data and accepts real signatures."""
        download = load("download", "00_download_raw_data.py")
        cases = {"a.xlsx": b"<!DOCTYPE html><html>", "b.txt": b"  <html><body>captcha",
                 "c.pdf": b"", "d.xlsx": b"PK\x03\x04rest", "e.csv": b"school,grads\n1,2",
                 "f.xls": b"\xd0\xcf\x11\xe0rest"}
        for name, head in cases.items():
            (tmp_path / name).write_bytes(head)
        bad = {n for n in cases if download.content_problem(tmp_path / n)}
        assert bad == {"a.xlsx", "b.txt", "c.pdf"}

    def test_catalog_source_ids_are_registered(self):
        """A catalog row marked scripted or partial names a source_id some group downloads
        (checked against the static parts of the registry to avoid network calls)."""
        registry = Path(sources.__file__).read_text()
        for state, _, _, source_id, _, _, status, _ in sources.CATALOG:
            if status in ("scripted", "partial"):
                assert source_id and f'"{source_id}"' in registry, (state, source_id)


# --- code/01_clean_fsa.py: parsing helpers and the derived FSA panel ---------

class TestCleanFsa:
    needs_panel = needs(clean_fsa.OUT, "01_clean_fsa.py")

    @staticmethod
    def q(sql):
        """Query the derived panel as view p."""
        return query(sql, p=clean_fsa.OUT)

    def test_parse_count(self):
        """Plain counts parse to int, "<5" is suppressed, blanks are missing."""
        assert clean_fsa.parse_count(" 17") == (17, False)
        assert clean_fsa.parse_count("<5") == (None, True)
        assert clean_fsa.parse_count(float("nan")) == (None, False)
        with pytest.raises(ValueError):
            clean_fsa.parse_count("n/a")

    def test_find_columns(self):
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
    def test_one_row_per_file_row_and_class(self):
        """Each row of a source file appears at most once per class."""
        assert self.q("SELECT count(*) - count(DISTINCT (class_year, source_file, row_in_file)) FROM p") == 0

    @needs_panel
    def test_each_class_from_one_file(self):
        """Every class comes from exactly one source file."""
        assert self.q("SELECT max(n) FROM (SELECT count(DISTINCT source_file) n FROM p GROUP BY class_year)") == 1

    @needs_panel
    def test_classes_are_contiguous_from_2015(self):
        """Classes run without gaps from 2015 to the newest."""
        years = [r[0] for r in duckdb.sql(
            f"SELECT DISTINCT class_year FROM read_parquet('{clean_fsa.OUT.as_posix()}') ORDER BY 1").fetchall()]
        assert years[0] == 2015
        assert years == list(range(years[0], years[-1] + 1))

    @needs_panel
    def test_final_class_comes_from_a_later_file(self):
        """Fixed counts for class Y come from a file dated after June of Y."""
        assert self.q("SELECT count(*) FROM p WHERE kind = 'final' "
                      "AND snapshot_date <= make_date(class_year, 6, 30)") == 0

    @needs_panel
    def test_only_newest_class_is_preliminary(self):
        """At most one class is preliminary, and it is the newest class."""
        assert self.q("SELECT count(DISTINCT class_year) FROM p WHERE kind = 'preliminary'") <= 1
        assert self.q("SELECT count(*) FROM p WHERE kind = 'preliminary' "
                      "AND class_year < (SELECT max(class_year) FROM p)") == 0

    @needs_panel
    def test_completed_never_exceeds_submitted(self):
        """Completed applications are a subset of submitted applications."""
        assert self.q("SELECT count(*) FROM p WHERE completed_jun > submitted_jun "
                      "OR completed_dec > submitted_dec") == 0

    @needs_panel
    def test_suppressed_cells_are_missing(self):
        """A "<5" flag always goes with a missing count."""
        assert self.q("SELECT count(*) FROM p WHERE completed_jun_lt5 AND completed_jun IS NOT NULL") == 0
        assert self.q("SELECT count(*) FROM p WHERE submitted_jun_lt5 AND submitted_jun IS NOT NULL") == 0

    @needs_panel
    def test_no_placeholder_school_codes(self):
        """All-zero placeholder codes have been set to missing."""
        assert self.q("SELECT count(*) FROM p WHERE regexp_full_match(school_code, '0+')") == 0


# --- code/02_link_fsa_codes.py: name normalization and the code crosswalk ----

class TestLinkFsa:
    needs_codes = needs(link_fsa.OUT, "02_link_fsa_codes.py")

    @staticmethod
    def q(sql):
        """Query the crosswalk (view c) and FSA panel (view p)."""
        return query(sql, c=link_fsa.OUT, p=link_fsa.PANEL)

    def test_normalize_spelling_variants(self):
        """Spelling variants seen in FSA files normalize to the same string."""
        n = link_fsa.normalize
        assert n("HOOVER HIGH SCH") == n("HOOVER HIGH SCHOOL")
        assert n("ST. AMANT") == n("ST AMANT") == n("SAINT AMANT")
        assert n("GATEWAY TECH H S") == n("GATEWAY TECHNOLOGY HIGH SCHOOL")
        assert n("AN-NOOR ACADEMY") == n("AN NOOR ACAD")
        assert n(None) is None

    def test_normalize_keeps_words_apart(self):
        """Abbreviations expand only as whole words."""
        assert link_fsa.normalize("STANTON HS") == "STANTON HIGH SCHOOL"
        assert link_fsa.normalize("SCHOLARS ACAD") == "SCHOLARS ACADEMY"

    @needs_codes
    def test_one_row_per_panel_record(self):
        """The crosswalk has exactly one row for every FSA panel record."""
        assert self.q("SELECT count(*) FROM c") == self.q("SELECT count(*) FROM p")
        assert self.q("SELECT count(*) - count(DISTINCT (class_year, source_file, row_in_file)) FROM c") == 0

    @needs_codes
    def test_fsa_codes_are_kept(self):
        """Records that already carry a School Code keep it unchanged."""
        assert self.q("SELECT count(*) FROM c WHERE school_code IS NOT NULL "
                      "AND (link_tier <> 'fsa_code' OR code_linked <> school_code)") == 0

    @needs_codes
    def test_tiers_are_known_and_consistent(self):
        """Every record has a known tier, and only linked tiers carry a code."""
        linked, open_tiers = sql_list(link_fsa.LINKED), sql_list(link_fsa.OPEN_TIERS)
        assert not set(link_fsa.LINKED) & set(link_fsa.OPEN_TIERS)
        assert self.q(f"SELECT count(*) FROM c WHERE link_tier NOT IN ({linked}, {open_tiers})") == 0
        assert self.q(f"SELECT count(*) FROM c WHERE link_tier IN ({open_tiers}) AND code_linked IS NOT NULL") == 0
        assert self.q(f"SELECT count(*) FROM c WHERE link_tier IN ({linked}) AND code_linked IS NULL") == 0

    @needs_codes
    def test_name_only_links_do_not_take_claimed_codes(self):
        """A name-only link never shares its class and code with an exact or normalized link."""
        assert self.q("""
            SELECT count(*) FROM c a JOIN c b USING (class_year, code_linked)
            WHERE a.link_tier = 'name_only' AND b.link_tier IN ('exact', 'normalized')
        """) == 0

    @needs_codes
    def test_ccd_links_only_before_fsa_codes(self):
        """CCD and other-year links are used only for classes before FSA's own codes start."""
        assert self.q("""
            SELECT count(*) FROM c
            WHERE link_tier IN ('ccd_exact', 'ccd_prefix', 'ccd_name_only', 'other_year')
              AND class_year >= (SELECT min(class_year) FROM c WHERE school_code IS NOT NULL)
        """) == 0

    @needs_codes
    def test_ccd_match_recorded(self):
        """Every CCD link records the CCD name it matched, and only CCD links do."""
        assert self.q("SELECT count(*) FROM c WHERE link_tier LIKE 'ccd_%' AND ccd_name IS NULL") == 0
        assert self.q("SELECT count(*) FROM c WHERE link_tier NOT LIKE 'ccd_%' AND ccd_name IS NOT NULL") == 0

    @needs_codes
    def test_late_tier_links_do_not_take_claimed_codes(self):
        """CCD and other-year links never share their class and code with an earlier-tier link."""
        assert self.q("""
            SELECT count(*) FROM c a JOIN c b USING (class_year, code_linked)
            WHERE a.link_tier IN ('ccd_exact', 'ccd_prefix', 'ccd_name_only', 'other_year')
              AND b.link_tier IN ('exact', 'normalized', 'name_only')
        """) == 0

    def test_fuzzy_accepts_network_prefixed_names(self):
        """A charter campus matches its CCD name with the network prefix added."""
        n = link_fsa.normalize
        assert link_fsa.fuzzy_coverage(n("PRITZKER COLLEGE PREP"), n("Noble St Chtr-Pritzker Col Prep"),
                                       n("CHICAGO")) >= link_fsa.FUZZY_COVERAGE

    def test_fuzzy_rejects_known_false_matches(self):
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
    def test_directory_links_use_matching_id_type(self):
        """CCD links carry 12-character NCES IDs and PSS links 8-character PSS IDs."""
        assert self.q("SELECT count(*) FROM c WHERE link_tier LIKE 'ccd_%' AND length(code_linked) <> 12") == 0
        assert self.q("SELECT count(*) FROM c WHERE link_tier LIKE 'pss_%' AND length(code_linked) <> 8") == 0

    @needs_codes
    def test_pss_match_recorded(self):
        """Every PSS link records the PSS name it matched, and only PSS links do."""
        assert self.q("SELECT count(*) FROM c WHERE link_tier LIKE 'pss_%' AND pss_name IS NULL") == 0
        assert self.q("SELECT count(*) FROM c WHERE link_tier NOT LIKE 'pss_%' AND pss_name IS NOT NULL") == 0

    @needs_codes
    def test_candidate_codes_only_on_open_records(self):
        """Offered codes are kept only for records that ended up without a code."""
        assert self.q("SELECT count(*) FROM c WHERE candidate_code IS NOT NULL "
                      f"AND link_tier NOT IN ({sql_list(link_fsa.OPEN_TIERS)})") == 0
        assert self.q("SELECT count(*) FROM c WHERE (candidate_code IS NULL) <> (candidate_tier IS NULL)") == 0


# --- code/03_build_fsa_school_panel.py: the school x class FSA panel ---------

class TestFsaSchoolPanel:
    needs_panel = needs(school_panel.OUT, "03_build_fsa_school_panel.py")

    @staticmethod
    def q(sql):
        """Query the school panel (view s) and FSA records (view p)."""
        return query(sql, s=school_panel.OUT, p=school_panel.PANEL)

    def test_sector_from_code_format(self):
        """Codes are classified by format: NCES (12), FSA-only (FN), PSS (8)."""
        assert school_panel.sector("220019700953") == "public"
        assert school_panel.sector("02FN00011") == "no_nces_id"
        assert school_panel.sector("A9101574") == "private"

    @needs_panel
    def test_one_row_per_school_and_class(self):
        """Each school appears at most once per class."""
        assert self.q("SELECT count(*) - count(DISTINCT (school_id, class_year)) FROM s") == 0

    @needs_panel
    def test_completions_kept_from_fsa(self):
        """The panel keeps nearly all of the study states' FSA completions and never adds any."""
        states = sql_list(STUDY_STATES)
        kept = self.q("SELECT sum(completed_jun) FROM s")
        total = self.q(f"SELECT sum(completed_jun) FROM p WHERE state IN ({states})")
        assert kept <= total
        # Records with no code (unlinked, ambiguous, network-level) are left out: ~0.2% of
        # completions as of 2026-10. Falling below 99% means linking got worse.
        assert kept / total > 0.99

    @needs_panel
    def test_completed_never_exceeds_submitted(self):
        """Summed completions never exceed summed submissions."""
        assert self.q("SELECT count(*) FROM s WHERE completed_jun > submitted_jun "
                      "OR completed_dec > submitted_dec") == 0

    @needs_panel
    def test_single_record_suppressed_cells_are_missing(self):
        """For a school with one record, a '<5' flag goes with a missing count."""
        assert self.q("SELECT count(*) FROM s WHERE n_records = 1 "
                      "AND completed_jun_lt5 AND completed_jun IS NOT NULL") == 0

    @needs_panel
    def test_network_records_not_added_to_campuses(self):
        """Network-level records (names ending in SCHOOLS) are never added as duplicate listings."""
        df = school_panel.load_records()
        school_panel.absorb_duplicates(df)
        added = df[df["assign_rule"] == "duplicate_listing"]
        assert not added["name_norm"].str.contains(school_panel.NETWORK, regex=True, na=False).any()

    @needs_panel
    def test_only_study_states(self):
        """The panel holds only the 15 study states."""
        states = sql_list(STUDY_STATES)
        assert self.q(f"SELECT count(*) FROM s WHERE state NOT IN ({states})") == 0

    @needs_panel
    def test_sector_matches_school_id(self):
        """Sector agrees with the school_id format in every row."""
        assert self.q("SELECT count(*) FROM s WHERE (length(school_id) = 12) <> (sector = 'public')") == 0


# --- code/05_build_analysis_panel.py: policy timing (dose, reference, post) --

class TestPolicyTiming:
    needs_timing = needs(analysis_panel.TIMING, "05_build_analysis_panel.py")

    def test_timing_without_partial_rollout(self):
        """Reference is the class before e = 0 and the dose is the two classes before that."""
        t = analysis_panel.timing(2018, pd.NA, 2024, 2015, 2026, 2026)
        assert (t["dose_class_1"], t["dose_class_2"], t["reference_class"]) == (2015, 2016, 2017)
        assert (t["post_first"], t["post_last"], t["n_post_classes"]) == (2018, 2024, 7)

    def test_timing_skips_partial_rollout_class(self):
        """A partial-rollout class is neither the reference nor part of the dose."""
        t = analysis_panel.timing(2024, 2023, pd.NA, 2015, 2026, 2026)
        assert (t["dose_class_1"], t["dose_class_2"], t["reference_class"]) == (2020, 2021, 2022)

    def test_policy_inputs_are_complete(self):
        """Every study state has one policy row with a first covered class."""
        states = pd.read_csv(analysis_panel.STATES, dtype=str)
        assert sorted(states["state"]) == sorted(STUDY_STATES)
        assert states["first_covered_class"].notna().all()
        co = pd.read_csv(analysis_panel.CO_SCHOOLS, dtype=str)
        assert co["nces_id"].str.fullmatch(r"\d{12}").all()
        assert co["first_covered_class"].notna().all()

    @needs_timing
    def test_one_row_per_unit(self):
        """One statewide row per state except Colorado, which has one row per grantee school."""
        t = pd.read_parquet(analysis_panel.TIMING)
        co = pd.read_csv(analysis_panel.CO_SCHOOLS, dtype=str)
        assert (t["state"] != "CO").sum() == len(set(STUDY_STATES) - {"CO"}) and t.loc[t["state"] != "CO", "school_id"].isna().all()
        assert sorted(t.loc[t["state"] == "CO", "school_id"]) == sorted(co["nces_id"])

    @needs_timing
    def test_dose_and_reference_precede_treatment(self):
        """Dose classes come before the reference class, which comes before e = 0."""
        t = pd.read_parquet(analysis_panel.TIMING)
        assert (t["dose_class_1"] < t["dose_class_2"]).all()
        assert (t["dose_class_2"] < t["reference_class"]).all()
        assert (t["reference_class"] < t["first_covered_class"]).all()


# --- code/04_build_ccd_school_panel.py: the school x year CCD panel ----------

class TestCcdSchoolPanel:
    needs_panel = needs(ccd_panel.OUT, "04_build_ccd_school_panel.py")

    @staticmethod
    def q(sql):
        """Query the CCD panel as view c."""
        return query(sql, c=ccd_panel.OUT)

    def test_grade_count(self):
        """Grade spans count both ends, with PK and KG as grades."""
        assert ccd_panel.grade_count("09", "12") == 4
        assert ccd_panel.grade_count("PK", "12") == 14
        assert ccd_panel.grade_count("KG", "05") == 6
        assert ccd_panel.grade_count("M", "12") is ccd_panel.pd.NA

    def test_negative_codes_become_missing(self):
        """CCD's negative codes (missing, not applicable, suppressed) are not counts."""
        s = ccd_panel.num(ccd_panel.pd.Series(["12", "-1", "-2", "-9", "0"]))
        assert s.isna().tolist() == [False, True, True, True, False]

    @needs_panel
    def test_one_row_per_school_and_year(self):
        """Each school appears at most once per class year."""
        assert self.q("SELECT count(*) - count(DISTINCT (school_id, class_year)) FROM c") == 0

    @needs_panel
    def test_only_study_states_and_years(self):
        """The panel holds the 15 study states and class years FIRST_YEAR-LAST_YEAR."""
        states = sql_list(STUDY_STATES)
        assert self.q(f"SELECT count(*) FROM c WHERE state NOT IN ({states})") == 0
        assert self.q("SELECT min(class_year) FROM c") == ccd_panel.FIRST_YEAR
        assert self.q("SELECT max(class_year) FROM c") == ccd_panel.LAST_YEAR

    @needs_panel
    def test_counts_are_consistent(self):
        """Grade 12 and race counts never exceed total enrollment; FRL parts never exceed the total."""
        assert self.q("SELECT count(*) FROM c WHERE enroll_g12 > enroll_total") == 0
        assert self.q("SELECT count(*) FROM c WHERE race_white + race_black + race_hispanic > enroll_total") == 0
        assert self.q("SELECT count(*) FROM c WHERE frl_free + frl_reduced > frl_total") == 0

    @needs_panel
    def test_school_types_standardized(self):
        """Every CCD school type maps to a standard label."""
        assert self.q("SELECT count(*) FROM c WHERE school_type IS NOT NULL AND school_type_std IS NULL") == 0


# --- code/05_build_analysis_panel.py: the first-stage analysis panel ---------

class TestAnalysisPanel:
    needs_panel = needs(analysis_panel.OUT, "05_build_analysis_panel.py")

    @staticmethod
    def q(sql):
        """Query the analysis panel as view a."""
        return query(sql, a=analysis_panel.OUT)

    @needs_panel
    def test_one_row_per_school_and_class(self):
        """Each school appears at most once per class."""
        assert self.q("SELECT count(*) - count(DISTINCT (school_id, class_year)) FROM a") == 0

    @needs_panel
    def test_fcr_between_zero_and_one(self):
        """The completion rate is capped at 1 and never negative."""
        assert self.q("SELECT count(*) FROM a WHERE fcr < 0 OR fcr > 1") == 0

    @needs_panel
    def test_dose_is_one_minus_mean_dose_fcr(self):
        """Dose equals 1 minus the mean completion rate over the two dose classes."""
        assert self.q("""
            WITH d AS (SELECT school_id, any_value(dose) AS dose,
                              avg(fcr) FILTER (WHERE class_year IN (dose_class_1, dose_class_2)) AS m
                       FROM a WHERE dose IS NOT NULL GROUP BY school_id)
            SELECT count(*) FROM d WHERE abs(dose - (1 - m)) > 1e-9
        """) == 0

    @needs_panel
    def test_louisiana_window_is_2015_to_2019(self):
        """Louisiana's estimation window is e = -3 ... +1, i.e. 2015-2019 (FSA starts in 2015)."""
        assert self.q("SELECT min(class_year) FROM a WHERE state = 'LA' AND in_window") == 2015
        assert self.q("SELECT max(class_year) FROM a WHERE state = 'LA' AND in_window") == 2019

    @needs_panel
    def test_balanced_schools_have_every_window_class(self):
        """A balanced school has a completion rate in every class its window needs."""
        assert self.q("""
            SELECT count(*) FROM (
                SELECT school_id, any_value(window_classes_needed) AS need,
                       count(*) FILTER (WHERE in_window AND fcr IS NOT NULL) AS have
                FROM a WHERE f_balanced GROUP BY school_id) WHERE have <> need
        """) == 0

    @needs_panel
    def test_post_only_for_treated_schools(self):
        """Untreated rows (non-grantee Colorado schools) are never post-mandate."""
        assert self.q("SELECT count(*) FROM a WHERE post AND NOT treated") == 0


# --- code/06_first_stage.py: first-stage sample and output -------------------

class TestSeniorShareScreen:
    def test_senior_heavy_rule(self):
        """Flagged only when the lowest grade is 9 or below and seniors exceed 75% of grades 9-12."""
        d = pd.DataFrame({"gslo": ["09", "11", "KG", "09", "09"],
                          "enroll_g09": [1, 0, 30, 25, 0], "enroll_g10": [0, 0, 30, 25, 0],
                          "enroll_g11": [2, 100, 30, 25, 0], "enroll_g12": [500, 100, 30, 25, 0]})
        assert analysis_panel.senior_heavy(d).tolist() == [True, False, False, False, False]


class TestFirstStage:
    needs_results = needs(first_stage.OUT, "06_first_stage.py")

    @staticmethod
    def toy_panel():
        """Two schools in the window; school B is missing a control in one class."""
        rows = []
        for sid in ("A", "B"):
            for y, post in ((2016, False), (2017, False), (2018, True)):
                rows.append({"school_id": sid, "class_year": y, "post": post, "treated": True,
                             "n_post_classes": 1, "in_window": True, "fcr": 0.5, "weight": 100.0,
                             "dose": 0.4, "x": 1.0, "f_ok": True})
        df = pd.DataFrame(rows)
        df.loc[(df["school_id"] == "B") & (df["class_year"] == 2017), "x"] = None
        return df

    def test_sample_drops_schools_with_any_missing_control(self):
        """A school missing a control in any window class is dropped entirely (Deneault)."""
        d = first_stage.sample(self.toy_panel(), ["f_ok"], ["x"])
        assert set(d["school_id"]) == {"A"} and len(d) == 3

    def test_colorado_left_out(self):
        """Colorado is excluded until its design is decided."""
        assert "CO" in first_stage.EXCLUDE_STATES

    @needs_results
    def test_results_cover_louisiana_specs(self):
        """Louisiana has the main, no-FRL, and Deneault-screen estimates."""
        out = pd.read_csv(first_stage.OUT)
        assert set(out.loc[out["state"] == "LA", "spec"]) == {"main", "no_frl", "deneault"}
        assert out["se"].gt(0).all() and "CO" not in set(out["state"])


# --- code/state_files.py, code/07_build_state_outcomes.py: state outcomes -----


class TestStateOutcomes:
    needs_outcomes = needs(state_outcomes.OUT, "07_build_state_outcomes.py")

    def test_bound_and_midpoint(self):
        """Bounds keep their direction; Deneault's coding puts them at the midpoint
        of the bounded range (>99 -> 99.5, <1 -> 0.5, >95 -> 97.5, <5 -> 2.5)."""
        cells = [">99", ">= 99", "≥95", "<1", "≤5", "57.3", "~"]
        assert [state_files.bound(c) for c in cells] == [">", ">", ">", "<", "<", "", ""]
        v = pd.Series([state_files.value(c) for c in cells])
        b = pd.Series([state_files.bound(c) for c in cells])
        assert state_files.midpoint(v, b).tolist()[:6] == [99.5, 99.5, 97.5, 0.5, 2.5, 57.3]

    def test_link_uses_same_year_then_any_year_then_alias(self):
        """A code matches CCD in the same year first, then the same code in another
        year; an alias maps a state code to the CCD code of the same school."""
        ccd = pd.DataFrame({"state": "LA", "class_year": [2016, 2018, 2018],
                            "code": ["111111", "222222", "333333"], "school_id": ["A", "B", "C"]})
        rows = pd.DataFrame({"class_year": [2016, 2017, 2017, 2017],
                             "code": ["111111", "222222", "999999", "444444"]})
        m = state_files.link("LA", rows, ccd, {"444444": "333333"})
        assert m["school_id"].tolist()[:2] == ["A", "B"] and pd.isna(m["school_id"][2])
        assert m["school_id"][3] == "C"
        assert m["link"].tolist() == ["same_year", "any_year", "", "any_year"]

    def test_illinois_codes_and_classes(self):
        """RCDTS (15 digits, with or without dashes) and CCD's 13-digit form agree;
        report card year Y holds the postsecondary enrollment of class Y-2."""
        assert state_files.il_code("010010010260001") == state_files.il_code("0100100100001") == "0100100100001"
        assert state_files.il_code("01-001-0010-26-0001") == "0100100100001"
        years = state_files.il_report_years()
        assert set(state_files.IL_CLASS_OF) == set(years) and years[0] == 2015
        assert years == list(range(2015, years[-1] + 1))      # no report card year missing
        assert all(state_files.IL_CLASS_OF[y] == y - 2 for y in years) and state_files.IL_CLASS_OF[2024] == 2022

    def test_new_hampshire_code(self):
        """CCD's 14-digit NH ID ends in the 5-digit school number used by NH DOE."""
        assert state_files.nh_code("NH-041-52504104128555") == state_files.nh_code("28555") == "28555"
        assert state_files.NH_CLASS_OF[2024] == 2024

    def test_alabama_key(self):
        """Alabama schools are keyed by system and school code (the school code alone
        repeats across systems); CCD 2014-15 has no system, so no key."""
        assert state_files.al_ccd_key("AL-101-0010") == state_files.al_ccd_key("101-0010") == "101-0010"
        assert state_files.al_ccd_key("0020") is None

    def test_maryland_name_keys(self):
        """Maryland's MLDS (system, name) and CCD (district, name) give one key; the
        SEED School maps from Baltimore City (MLDS) to its own district (CCD)."""
        assert state_files.md_school_key("Allegany", "Allegany High") == \
            state_files.md_school_key("Allegany County Public Schools", "ALLEGANY HIGH")
        assert state_files.md_district("Baltimore County Public Schools") == "BALTIMORE COUNTY"
        assert state_files.md_district("SEED School of Maryland") == "MARYLAND STATE"
        assert state_files.MD_ALIASES[state_files.md_school_key("Baltimore City", "The SEED School of Maryland")] == \
            state_files.md_school_key("SEED School of Maryland", "THE SEED SCHOOL OF MARYLAND")

    def test_texas_campus_rows_add_up(self):
        """THECB: enrolled + not found + not trackable = total graduates for every
        campus; campus IDs are 9 digits (leading zeros restored for 2024)."""
        d = state_files.tx_thecb_enrollment()
        assert (d["enrolled"] + d["not_found"] + d["not_trackable"] == d["graduates"]).all()
        assert d["code"].str.fullmatch(r"\d{9}").all() and not d.duplicated(["class_year", "code"]).any()

    def test_nebraska_ccpe_codes(self):
        """CCPE rows get the CCD code of the same school by district + name: an exact
        name wins over shared name words (Fremont Senior High vs. Fremont Learning
        Center, 2019), 'McCook' = 'MC COOK', and a district's only high school is
        used only where CCPE lists one school (not Cozad's alternative center)."""
        ccd = pd.DataFrame({"state": "NE", "class_year": 2019, "gshi": "12",
                            "code": ["270001001", "270001004", "730017001", "240011001"],
                            "name": ["FREMONT SENIOR HIGH SCHOOL", "FREMONT LEARNING CENTER",
                                     "MC COOK SENIOR HIGH SCHOOL", "COZAD HIGH SCHOOL"]})
        rows = pd.DataFrame({"class_year": 2019, "dist": ["270001", "730017", "240011", "240011"],
                             "School Name": ["Fremont Senior High School", "McCook Senior High School",
                                             "Cozad High School", "Cozad Alternative Ed Center"]})
        rows["exact"], rows["words"] = state_files.ne_name_keys(rows["School Name"])
        code, how = state_files.ne_ccpe_codes(rows, ccd)
        assert code.tolist() == ["270001001", "730017001", "240011001", "NAME:240011:Cozad Alternative Ed Center"]
        assert how.tolist() == ["exact_same_year", "words_same_year", "exact_same_year", ""]

    def test_oklahoma_key_and_names(self):
        """CCD's Oklahoma ST_SCHID forms give one county-district-site key; a CCD
        school renumbered later (charter moving district) matches an earlier class
        by the CCD year nearest it, and 'EDMOND MEMORIAL HS' matches district
        EDMOND's 'MEMORIAL HS' only through district + name."""
        assert {state_files.ok_ccd_key(x) for x in
                ["01-I025-705", "01-I025-01-I025-705", "OK-01-I025-01-I025-705"]} == {"01-I025-705"}
        c = pd.DataFrame({"cc": "55", "class_year": [2015, 2022], "code": ["55-E008-978", "55-E030-978"],
                          "name": "HARDING CHARTER PREPARATORY HS"})
        c["exact"], c["words"] = state_files.name_keys(c["name"])
        d = pd.DataFrame({"cc": "55", "class_year": [2013, 2024], "name": "HARDING CHARTER PREPARATORY HS"})
        d["exact"], d["words"] = state_files.name_keys(d["name"])
        assert state_files.name_codes(d, c, "cc")[0].tolist() == ["55-E008-978", "55-E030-978"]

    @needs_outcomes
    def test_oklahoma_outcomes(self):
        """Oklahoma, classes 2013-2024: school rows add up to each file's statewide
        graduates (class 2019: 45,014; 2024: 45,637); fall <= year <= graduates;
        out-of-state counts only from class 2023; no CCD school twice in a class."""
        d = pd.read_parquet(state_outcomes.OUT)
        ok = d[d["state"] == "OK"]
        assert set(ok["window"]) == {"ok_year_after_instate"} and ok["class_year"].min() == 2013
        grads = ok.groupby("class_year")["graduates"].sum()
        assert grads[2019] == 45014 and grads[2024] == 45637
        r = ok.dropna(subset=["enrolled"])      # 9 small schools, 2013-2015, have blank counts
        assert (r["enrolled_fall"] <= r["enrolled"]).all() and (r["enrolled"] <= r["graduates"]).all()
        assert set(ok.dropna(subset=["enrolled_outstate"])["class_year"]) == {2023, 2024}
        assert not ok.dropna(subset=["school_id"]).duplicated(["class_year", "school_id"]).any()
        assert ok["school_id"].notna().mean() > 0.99

    def test_new_jersey_key(self):
        """New Jersey CCD key = last two ST_SCHID segments (9-digit CDS); CCD
        2014-15's school-only code gives no key."""
        c = pd.DataFrame({"st_schid": ["NJ-010110-010", "010110-010", "010"]})
        k = state_files.NJ_CCD_KEY(c)
        assert k[:2].tolist() == ["010110010", "010110010"] and pd.isna(k[2])

    @needs_outcomes
    def test_new_jersey_outcomes(self):
        """New Jersey: fall rate classes 2019-2024 and 16-month 2018-2023 (lower
        bounds, 0-100); 9-digit CDS codes; every row links; graduates from the
        adjusted cohort graduation files (classes 2020-2025)."""
        d = pd.read_parquet(state_outcomes.OUT)
        nj = d[d["state"] == "NJ"]
        assert set(nj["window"]) == {"nj_fall"} and nj["code"].str.fullmatch(r"\d{9}").all()
        assert nj.dropna(subset=["pct_enrolled"])["class_year"].min() == 2019
        assert set(nj.dropna(subset=["pct_enrolled"])["class_year"]) >= set(range(2019, 2025))
        assert nj.dropna(subset=["pct_enrolled_16m"])["class_year"].min() == 2018
        assert nj[["pct_enrolled", "pct_enrolled_16m"]].stack().dropna().between(0, 100).all()
        assert nj["school_id"].notna().all()
        assert nj.loc[nj["class_year"] < 2020, "graduates"].isna().all()
        assert nj.loc[nj["class_year"].between(2020, 2025), "graduates"].notna().mean() > 0.95

    @pytest.mark.skipif(not state_files.NJ_ACGR.exists(), reason="run code/00_download_raw_data.py NJ first")
    def test_new_jersey_graduate_counts(self):
        """NJDOE adjusted cohort graduation files: one all-students school row per class
        and CDS code (no district 888 rows), classes 2020-2025, graduates <= cohort,
        and graduates / cohort reproduces the published rate."""
        g = state_files.nj_acgr_graduates()
        assert set(g["class_year"]) >= set(range(2020, 2026)) and not g.duplicated(["class_year", "code"]).any()
        assert g["code"].str.fullmatch(r"\d{9}").all() and not g["code"].str.endswith("888").any()
        both = g.dropna(subset=["graduates", "cohort_count", "grad_rate"])
        assert (both["graduates"] <= both["cohort_count"]).all()
        assert ((both["graduates"] / both["cohort_count"] * 100 - both["grad_rate"]).abs() < 0.1).all()

    @needs_outcomes
    def test_new_york_outcomes(self):
        """New York, classes 2021-2024: school rows only (12-digit BEDS codes, no
        state/county/district rows; class 2024 graduates 174,434); NY public +
        private + out of state = 2-year + 4-year = enrolled; every row links."""
        d = pd.read_parquet(state_outcomes.OUT)
        ny = d[d["state"] == "NY"]
        assert set(ny["window"]) == {"ny_16m_any"} and set(ny["class_year"]) >= {2021, 2022, 2023, 2024}
        assert ny["code"].str.fullmatch(r"\d{12}").all() and not ny["code"].str.endswith("0000").any()
        assert "111111111111" not in set(ny["code"])
        assert ny.loc[ny["class_year"] == 2024, "graduates"].sum() == 174434
        r = ny.dropna(subset=["enrolled"])
        parts = r[["enrolled_instate_public", "enrolled_instate_private", "enrolled_outstate"]].sum(axis=1)
        assert (parts == r["enrolled"]).all() and (r["enrolled_2yr"] + r["enrolled_4yr"] == r["enrolled"]).all()
        assert ny["school_id"].notna().all()

    @needs_outcomes
    def test_nebraska_outcomes(self):
        """Nebraska uses CCPE, classes 2008-2025 (class 2025 = first post class); every
        row from class 2015 links to CCD, no school twice in a class; rates are
        enrolled / on-time graduates; NDE's rate is kept for classes 2016-2023 only."""
        d = pd.read_parquet(state_outcomes.OUT)
        ne = d[d["state"] == "NE"]
        assert set(ne["window"]) == {"ne_year_after"}
        assert ne["class_year"].min() == 2008 and ne["class_year"].max() >= 2025
        assert ne.loc[ne["class_year"] >= 2015, "school_id"].notna().all()
        assert not ne.dropna(subset=["school_id"]).duplicated(["class_year", "school_id"]).any()
        r = ne.dropna(subset=["pct_enrolled"])
        assert ((100 * r["enrolled"] / r["graduates"] - r["pct_enrolled"]).abs() < 0.01).all()
        assert set(ne.dropna(subset=["pct_enrolled_nde_oct15"])["class_year"]) <= set(range(2016, 2024))

    @needs_outcomes
    def test_louisiana_outcomes(self):
        """One row per state x class x code; rates are percents; penroll is a share and
        exists from class 2014 (first graduation-rate year); Grambling Lab links 2013-2016."""
        d = pd.read_parquet(state_outcomes.OUT)
        la = d[d["state"] == "LA"]
        assert not d.duplicated(state_outcomes.KEY).any()
        assert la["class_year"].min() == 2012 and la["class_year"].max() >= 2024
        assert la["pct_enrolled"].dropna().between(0, 100).all()
        assert la["grad_rate"].dropna().between(0, 100).all()
        assert la["penroll"].dropna().between(0, 1).all()
        assert la.loc[la["class_year"] < 2014, "penroll"].isna().all()
        assert la.loc[la["class_year"] >= 2014, "penroll"].notna().mean() > 0.9
        il = d[d["state"] == "IL"]
        assert set(il["window"]) == {"il_12m_sep30"} and set(la["window"]) == {"la_fall_oct31"}
        assert il["class_year"].min() == 2013 and il["class_year"].max() >= 2024
        assert il["pct_enrolled"].dropna().between(0, 100).all()
        al = d[d["state"] == "AL"]
        assert set(al["window"]) == {"al_fall_public_instate"} and al["class_year"].min() == 2012
        assert (al["enrolled"] <= al["graduates"]).all() and al["school_id"].notna().mean() > 0.95
        md = d[d["state"] == "MD"]
        assert set(md["window"]) == {"md_within_1yr"} and md["class_year"].max() >= 2024
        assert md["pct_enrolled"].dropna().between(0, 100).all() and md["school_id"].notna().mean() > 0.95
        tx = d[d["state"] == "TX"]
        assert set(tx["window"]) == {"tx_fall_texas"} and tx["class_year"].min() == 2019
        assert (tx["pct_enrolled"] <= tx["pct_enrolled_trackable"]).all() and tx["school_id"].notna().all()
        ca = d[d["state"] == "CA"]
        assert set(ca["window"]) == {"ca_12m_any"} and ca["class_year"].min() == 2015
        assert not ca["code"].isin(["0000000", "0000001"]).any() and ca["school_id"].notna().mean() > 0.98
        ind = d[d["state"] == "IN"]
        assert set(ind["window"]) == {"in_year_after"} and ind["class_year"].min() == 2008
        assert not ind.loc[ind["school_id"].notna()].duplicated(["class_year", "school_id"]).any()
        nh = d[d["state"] == "NH"]
        assert set(nh["window"]) == {"nh_year_after"} and nh["class_year"].min() == 2016
        assert nh["school_id"].notna().mean() > 0.95 and nh["code"].str.fullmatch(r"\d{5}").all()
        ne = d[d["state"] == "NE"]
        assert set(ne["window"]) == {"ne_year_after"} and (ne["pct_enrolled"].dropna() >= 0).all()
        assert not ne.duplicated(["class_year", "code"]).any() and ne["school_id"].notna().mean() > 0.95
        gram = la[la["code"] == "031002"]
        assert gram["school_id"].notna().all() and set(gram["class_year"]) >= {2013, 2014, 2015, 2016}


# --- code/08_reduced_form.py: outcomes merged onto the panel, reduced form ----


class TestReducedForm:
    needs_rf = needs(reduced_form.OUT, "08_reduced_form.py")

    def test_outcome_sample_keeps_classes_with_data_and_balances(self):
        """Classes without any outcome are dropped; a school missing the outcome in a
        remaining class is dropped; no pre or no post class left -> None."""
        d = pd.DataFrame({"school_id": ["a"] * 3 + ["b"] * 3 + ["c"] * 3, "class_year": [2018, 2019, 2020] * 3,
                          "post": [False, False, True] * 3,
                          "enroll": [None, 0.5, 0.6, None, None, 0.7, None, 0.4, 0.5]})
        s = reduced_form.outcome_sample(d, "enroll")
        assert set(s["class_year"]) == {2019, 2020} and set(s["school_id"]) == {"a", "c"}
        assert reduced_form.outcome_sample(d[d["class_year"] < 2020], "enroll") is None

    @needs_rf
    def test_merge_is_one_to_one(self):
        """The merged panel has exactly the analysis panel's rows; enroll = pct / 100."""
        n = duckdb.sql(f"select count(*) from '{DERIVED / 'analysis_panel.parquet'}'").fetchone()[0]
        d = pd.read_parquet(reduced_form.PANEL_OUT, columns=["school_id", "class_year", "pct_enrolled", "enroll"])
        assert len(d) == n and not d.duplicated(["school_id", "class_year"]).any()
        r = d.dropna(subset=["enroll"])
        assert ((r["enroll"] - r["pct_enrolled"] / 100).abs() < 1e-12).all() and r["enroll"].between(0, 1).all()

    @staticmethod
    def covered_states(cols):
        """Rule for which states can be estimated, computed from the merged panel
        independently of step 8's sampling code: a state not excluded whose treated
        window rows have every column in `cols` in at least one pre-mandate and one
        post-mandate class. Grows by itself as new data arrive."""
        p = pd.read_parquet(reduced_form.PANEL_OUT, columns=["state", "treated", "in_window", "post", *cols])
        p = p[p["treated"] & p["in_window"] & p[cols].notna().all(axis=1)]
        both = p.groupby("state")["post"].agg(lambda x: x.any() and not x.all())
        return set(both[both].index) - set(first_stage.EXCLUDE_STATES)

    @needs_rf
    def test_states_with_post_outcomes_only(self):
        """Exactly the states whose outcome covers a pre and a post window class are
        estimated (excluded states never are); LA has Deneault's spec."""
        out = pd.read_csv(reduced_form.OUT)
        assert set(out["state"]) == self.covered_states(["enroll"])
        assert not set(out["state"]) & set(first_stage.EXCLUDE_STATES)
        la = out[(out["state"] == "LA") & (out["spec"] == "deneault")]
        assert len(la) == 1 and la["outcome"].iloc[0] == "penroll"
        assert (out["n_schools"] <= out["schools_first_stage_sample"]).all() and (out["se"] > 0).all()

    def test_attrition_splits_no_outcome_and_partial(self):
        """Counted only over classes with outcome data: a school with none is
        `no_outcome`, one missing some is `partial`, complete schools are not counted."""
        d = pd.DataFrame({"school_id": list("aabbcc"), "class_year": [2019, 2020] * 3,
                          "enroll": [0.5, 0.6, None, None, 0.4, None]})
        assert reduced_form.attrition(d, "enroll") == {"dropped_no_outcome": 1, "dropped_partial_outcome": 1}

    @needs_rf
    def test_attrition_accounts_for_every_dropped_school(self):
        """First-stage schools = reduced-form schools + the two dropped counts."""
        out = pd.read_csv(reduced_form.OUT)
        dropped = out["dropped_no_outcome"] + out["dropped_partial_outcome"]
        assert (out["schools_first_stage_sample"] - out["n_schools"] == dropped).all()

    def test_graduate_denominator_rules(self):
        """fcr = completions / graduates, capped at 1; dose needs both dose classes;
        window classes without any graduate count in the state leave the window."""
        d = pd.DataFrame({"state": "LA", "school_id": ["a"] * 4 + ["b"] * 4, "class_year": [2015, 2016, 2017, 2018] * 2,
                          "dose_class_1": 2015, "dose_class_2": 2016, "in_window": True,
                          "completed_jun": [40, 60, 50, 10, 30, 30, 20, 10],
                          "outcome_graduates": [80, 50, 100, None, 60, None, 40, None]})
        g = reduced_form.with_graduate_denominator(d).set_index(["school_id", "class_year"])
        assert g.loc[("a", 2015), "fcr"] == 0.5 and g.loc[("a", 2016), "fcr"] == 1.0  # 60/50 capped
        assert g.loc[("a", 2015), "dose"] == 0.25 and pd.isna(g.loc[("b", 2015), "dose"])  # b lacks 2016
        assert not g.loc[("a", 2018), "in_window"] and g.loc[("a", 2017), "in_window"]

    @needs_rf
    def test_graduate_denominator_outputs(self):
        """The graduate first stage runs exactly where graduate counts cover a pre and a
        post window class; its reduced form where the outcome does too; on schools
        within the baseline main sample; the check table covers those states."""
        out = pd.read_csv(reduced_form.OUT).set_index(["state", "spec"])
        grad = out.xs("grad_denom", level="spec")
        fs_states = self.covered_states(["outcome_graduates"])
        fsg = pd.read_csv(reduced_form.OUT_FS_GRAD)
        assert set(fsg["state"]) == fs_states and (fsg["se"] > 0).all()
        assert set(grad.index) == fs_states & self.covered_states(["outcome_graduates", "enroll"])
        assert (grad["schools_first_stage_sample"] <= out.xs("main", level="spec").loc[grad.index, "schools_first_stage_sample"]).all()
        chk = pd.read_csv(reduced_form.OUT_GRAD_CHECK)
        assert set(grad.index) <= set(chk["state"]) and chk["ratio"].between(0.5, 1.5).all()


# --- code/09_summary_stats.py: summary statistics of the reduced-form sample --


summary_stats = load("summary_stats", "09_summary_stats.py")


class TestSummaryStats:
    needs_ss = needs(summary_stats.OUT_RF_STATE, "09_summary_stats.py")

    def test_school_means_use_pre_classes_and_locale_codes(self):
        """Post classes are ignored; locale 1x = city, 4x = rural; missing locale stays missing."""
        d = pd.DataFrame({"state": "LA", "school_id": ["a", "a", "a", "b"], "post": [False, False, True, False],
                          "locale": ["11", "11", "41", None], "charter": [True, True, True, None]})
        for c in set(summary_stats.VARS) - set(summary_stats.LOCALES) - {"charter"}:
            d[c] = [1.0, 3.0, 100.0, 5.0]
        m = summary_stats.school_means(d).set_index("school_id")
        assert m.loc["a", "enroll"] == 2.0 and m.loc["a", "city"] == 1.0 and m.loc["a", "rural"] == 0.0
        assert m.loc["a", "charter"] == 1.0 and pd.isna(m.loc["b", "city"]) and pd.isna(m.loc["b", "charter"])

    @needs_ss
    def test_counts_match_reduced_form_main(self):
        """School counts by state equal the reduced form's main-spec n_schools, and
        the dose quartiles split the same schools into four near-equal groups."""
        rf = pd.read_csv(reduced_form.OUT).query("spec == 'main'").set_index("state")["n_schools"]
        s = pd.read_csv(summary_stats.OUT_RF_STATE).query("variable == 'n_schools'").drop(columns=["variable", "stat"])
        assert s[rf.index].iloc[0].astype(int).to_dict() == rf.to_dict() and s["All"].iloc[0] == rf.sum()
        q = pd.read_csv(summary_stats.OUT_RF_DOSE).query("variable == 'n_schools'")
        assert q["All"].iloc[0] == rf.sum() and q[["Q1", "Q2", "Q3", "Q4"]].iloc[0].between(0.24 * rf.sum(), 0.26 * rf.sum()).all()

    @needs_ss
    def test_first_stage_counts_match_first_stage_main(self):
        """First-stage-sample school counts by state equal the first stage's main-spec n_schools."""
        fs = pd.read_csv(first_stage.OUT).query("spec == 'main'").set_index("state")["n_schools"]
        s = pd.read_csv(summary_stats.OUT_FS_STATE).query("variable == 'n_schools'")
        assert s[fs.index].iloc[0].astype(int).to_dict() == fs.to_dict() and s["All"].iloc[0] == fs.sum()



# --- code/10_export_tables.py: formatted results tables -----------------------


export_tables = load("export_tables", "10_export_tables.py")


class TestExportTables:
    def test_cell_formats(self):
        """Stars at the 10/5/1% cutoffs, SE on the next line, counts as whole numbers."""
        assert [export_tables.stars(p) for p in [0.2, 0.09, 0.04, 0.009]] == ["", "*", "**", "***"]
        assert export_tables.coef(0.1234, 0.0456, 0.03) == "0.123**<br>(0.046)"
        assert export_tables.count(77.0) == "77" and export_tables.num(1234.4) == "1,234" and export_tables.num(float("nan")) == ""

    @needs(export_tables.OUT, "10_export_tables.py")
    def test_every_estimated_state_appears(self):
        """Each state in the first-stage and reduced-form CSVs has a row in Tables 2 and 3,
        and a column in Table 1A (first-stage sample) and 1B (reduced-form sample)."""
        html = export_tables.OUT.read_text(encoding="utf-8")
        tables = {h.split(".")[0]: pd.read_html(StringIO(t))[0]
                  for h, t in re.findall(r"<h2>(.*?)</h2>(<table>.*?</table>)", html)}
        t1a, t1, t2, t3 = (tables[k] for k in ["Table 1A", "Table 1B", "Table 2", "Table 3"])
        fs, rf = (pd.read_csv(export_tables.TABLES / f) for f in ["first_stage_by_state.csv", "reduced_form_by_state.csv"])
        names = export_tables.STATE_NAMES
        assert {names[s] for s in fs["state"]} <= set(t2["State"]) and {names[s] for s in rf["state"]} <= set(t3["State"])
        assert set(rf["state"]) <= set(t1.columns) and set(fs["state"]) <= set(t1a.columns)


# --- code/11_event_study.py: event study and pre-trend tests -------------------


event_study = load("event_study", "11_event_study.py")


class TestEventStudy:
    def test_regressor_names(self):
        """Event-time regressors are named by sign and distance: e = -3 -> es_m3, e = 0 -> es_p0."""
        assert [event_study.es_name(k) for k in [-3, 0, 2]] == ["es_m3", "es_p0", "es_p2"]

    def test_recovers_known_dynamics(self):
        """On simulated data with y = 0.2 * dose * post + noise-free FE, beta_k = 0 before e = 0 and 0.2 after."""
        rows = [{"school_id": f"s{i}", "class_year": 2018 + t, "e": t - 3, "dose": i / 10, "weight": 1.0, "x": (i * t) % 3,
                 "y": 0.1 * i + 0.01 * t + 0.2 * (i / 10) * (t >= 3)} for i in range(10) for t in range(6)]
        coefs, tests = event_study.event_study(pd.DataFrame(rows), ["x"], "y")
        b = coefs.set_index("e")["beta"]
        assert b[[-3, -2, -1]].abs().max() < 1e-8 and (b[[0, 1, 2]] - 0.2).abs().max() < 1e-8
        assert set(tests["test"]) == {"pre_all", "pre_no_dose"}

    @needs(event_study.OUT_COEF, "11_event_study.py")
    def test_outputs(self):
        """Every main (and graduate-denominator) first-stage state has a FAFSA event study; the reference class is 0 with
        no SE; pre_no_dose tests only classes at or before e = -4."""
        c, t = pd.read_csv(event_study.OUT_COEF), pd.read_csv(event_study.OUT_TEST)
        fs = set(pd.read_csv(first_stage.OUT).query("spec == 'main'")["state"])
        assert fs == set(c.query("spec == 'main' and outcome == 'fcr'")["state"])
        grad = set(pd.read_csv(reduced_form.OUT_FS_GRAD)["state"])
        assert grad == set(c.query("spec == 'grad_denom' and outcome == 'fcr'")["state"])
        ref = c[c["e"] == event_study.REF]
        assert (ref["beta"] == 0).all() and (ref["se"] == 0).all()
        assert len(ref) == c.groupby(["state", "spec", "outcome"]).ngroups
        e = t.query("test == 'pre_no_dose'")["classes"].dropna().str.split(",").explode().astype(int)
        assert (e <= -4).all()
