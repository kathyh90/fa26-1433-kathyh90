"""Tests for code/07_first_stage.py: first-stage sample and output."""

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "code"))

from config import ROOT  # noqa: E402

# The script name starts with a digit, so load it by path.
_spec = importlib.util.spec_from_file_location("first_stage", ROOT / "code" / "07_first_stage.py")
first_stage = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(first_stage)

needs_results = pytest.mark.skipif(not first_stage.OUT.exists(), reason="run code/07_first_stage.py first")


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


def test_sample_drops_schools_with_any_missing_control():
    """A school missing a control in any window class is dropped entirely (Deneault)."""
    d = first_stage.sample(toy_panel(), ["f_ok"], ["x"])
    assert set(d["school_id"]) == {"A"} and len(d) == 3


def test_colorado_left_out():
    """Colorado is excluded until its design is decided."""
    assert "CO" in first_stage.EXCLUDE_STATES


@needs_results
def test_results_cover_louisiana_specs():
    """Louisiana has the main, no-FRL, and Deneault-screen estimates."""
    out = pd.read_csv(first_stage.OUT)
    assert set(out.loc[out["state"] == "LA", "spec"]) == {"main", "no_frl", "deneault"}
    assert out["se"].gt(0).all() and "CO" not in set(out["state"])
