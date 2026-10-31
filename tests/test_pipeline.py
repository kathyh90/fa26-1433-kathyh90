"""Tests for the full pipeline, grouped by script: config, 01-07.

Tests that read a derived file are skipped until the script that writes it has run.
"""

import importlib.util
import sys
from pathlib import Path

import duckdb
import pandas as pd
import pytest

# Make code/ importable so tests can `import config` like the scripts do.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from config import DERIVED, OUTPUT, RAW, ROOT, STUDY_STATES  # noqa: E402


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


# --- code/config.py: shared paths -------------------------------------------

class TestConfig:
    def test_root_is_repo_root(self):
        """ROOT is the directory that holds pyproject.toml."""
        assert (ROOT / "pyproject.toml").is_file()

    def test_paths_are_inside_root(self):
        """RAW, DERIVED, and OUTPUT all live under ROOT."""
        for path in (RAW, DERIVED, OUTPUT):
            assert path.is_relative_to(ROOT)


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
