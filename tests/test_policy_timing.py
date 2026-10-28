"""Tests for code/04_policy_timing.py: the dose, reference, and post classes."""

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from config import ROOT  # noqa: E402

# The script name starts with a digit, so load it by path.
_spec = importlib.util.spec_from_file_location("policy_timing", ROOT / "code" / "04_policy_timing.py")
policy_timing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(policy_timing)

needs_timing = pytest.mark.skipif(not policy_timing.OUT.exists(), reason="run code/04_policy_timing.py first")


def test_timing_without_partial_rollout():
    """Reference is the class before e = 0 and the dose is the two classes before that."""
    t = policy_timing.timing(2018, pd.NA, 2024, 2015, 2026, 2026)
    assert (t["dose_class_1"], t["dose_class_2"], t["reference_class"]) == (2015, 2016, 2017)
    assert (t["post_first"], t["post_last"], t["n_post_classes"]) == (2018, 2024, 7)


def test_timing_skips_partial_rollout_class():
    """A partial-rollout class is neither the reference nor part of the dose."""
    t = policy_timing.timing(2024, 2023, pd.NA, 2015, 2026, 2026)
    assert (t["dose_class_1"], t["dose_class_2"], t["reference_class"]) == (2020, 2021, 2022)


def test_policy_inputs_are_complete():
    """Every study state has one policy row with a first covered class."""
    states = pd.read_csv(policy_timing.STATES, dtype=str)
    assert sorted(states["state"]) == sorted(["LA", "IL", "AL", "TX", "CO", "MD", "CA", "IN", "NH",
                                              "NE", "OK", "NY", "NJ", "CT", "PA"])
    assert states["first_covered_class"].notna().all()
    co = pd.read_csv(policy_timing.CO_SCHOOLS, dtype=str)
    assert co["nces_id"].str.fullmatch(r"\d{12}").all()
    assert co["first_covered_class"].notna().all()


@needs_timing
def test_one_row_per_unit():
    """One statewide row per state except Colorado, which has one row per grantee school."""
    t = pd.read_parquet(policy_timing.OUT)
    co = pd.read_csv(policy_timing.CO_SCHOOLS, dtype=str)
    assert (t["state"] != "CO").sum() == 14 and t.loc[t["state"] != "CO", "school_id"].isna().all()
    assert sorted(t.loc[t["state"] == "CO", "school_id"]) == sorted(co["nces_id"])


@needs_timing
def test_dose_and_reference_precede_treatment():
    """Dose classes come before the reference class, which comes before e = 0."""
    t = pd.read_parquet(policy_timing.OUT)
    assert (t["dose_class_1"] < t["dose_class_2"]).all()
    assert (t["dose_class_2"] < t["reference_class"]).all()
    assert (t["reference_class"] < t["first_covered_class"]).all()
