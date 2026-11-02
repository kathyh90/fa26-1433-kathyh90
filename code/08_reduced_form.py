"""Reduced form by state: college enrollment on dose x post.

Merges the state college-going outcomes (state_outcomes.parquet, step 7) onto
the analysis panel (step 5) by state, class, and school_id, then for each state

    enroll_it = beta * dose_i * post_t + controls_it + school_i + class_t + error,

with the first stage's weights, screens, controls, and clustering (step 6,
06_first_stage.sample / estimate). enroll = pct_enrolled / 100, the state's
published enrollment rate as a share (`window` says which rate; see
07_build_state_outcomes.py). Louisiana also runs Deneault's specification with
her outcome, penroll.

Sample (DECISIONS 2026-11-01): the first-stage sample, limited to the window
classes in which the state has outcome data (Texas starts at class 2019;
California ends at 2023 and Indiana at 2024), keeping schools with the outcome
in every one of those classes. A state needs a pre and a post class left;
Oklahoma, New York, and New Jersey have no post-period outcome yet.

For comparison, the first stage is re-estimated on the same sample (fs_beta);
rf_fs_ratio = beta / fs_beta is the implied effect on enrollment per unit of
FAFSA completion (a Wald ratio, no standard error).

Writes data/derived/reduced_form_panel.parquet (panel + outcome columns) and
output/tables/reduced_form_by_state.csv.

Usage (from the repository root):
    uv run --locked python code/08_reduced_form.py
"""

import importlib.util

import duckdb
import pandas as pd

from config import DERIVED, OUTPUT, ROOT, STUDY_STATES

PANEL_OUT = DERIVED / "reduced_form_panel.parquet"
OUT = OUTPUT / "tables" / "reduced_form_by_state.csv"
OUTCOME_COLUMNS = {"window": "outcome_window", "pct_enrolled": "pct_enrolled", "graduates": "outcome_graduates",
                   "penroll": "penroll", "link": "outcome_link"}


def first_stage_module():
    """Step 6 as a module (its file name starts with a digit, so load it by path)."""
    spec = importlib.util.spec_from_file_location("first_stage", ROOT / "code" / "06_first_stage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def merge_outcomes():
    """Analysis panel left-joined to the state outcomes (one row per school x
    class on both sides); prints row counts and how many rows got an outcome."""
    panel = duckdb.sql(f"select * from '{DERIVED / 'analysis_panel.parquet'}'").df()
    out = duckdb.sql(f"select * from '{DERIVED / 'state_outcomes.parquet'}' where school_id is not null").df()
    out = out[["state", "class_year", "school_id", *OUTCOME_COLUMNS]].rename(columns=OUTCOME_COLUMNS)
    n0 = len(panel)
    d = panel.merge(out, on=["state", "class_year", "school_id"], how="left", validate="1:1")
    assert len(d) == n0
    d["enroll"] = d["pct_enrolled"] / 100
    print(f"Merged outcomes: panel {n0:,} rows -> {len(d):,} (left join, no rows added or dropped); "
          f"{d['enroll'].notna().sum():,} rows with an outcome. Outcome rows not in the panel "
          f"(private or non-FSA schools, other classes): {len(out) - d['outcome_window'].notna().sum():,} of {len(out):,}")
    return d


def outcome_sample(d, y):
    """Limit a first-stage sample to classes where the state has outcome y, keep
    schools with y in all of them; None if no pre or no post class is left."""
    have = set(d.loc[d[y].notna(), "class_year"])
    d = d[d["class_year"].isin(have)]
    d = d[d[y].notna().groupby(d["school_id"]).transform("all")]
    return d if d["post"].any() and (~d["post"]).any() and d["school_id"].nunique() >= 2 else None


def main():
    fs = first_stage_module()
    df = merge_outcomes()
    df.to_parquet(PANEL_OUT, index=False)
    df["enroll_k"] = df["enroll_total"].astype(float) / 1000
    df["enroll_k_sq"] = df["enroll_k"] ** 2
    for c in ["fcr", "dose", "weight", "enroll", "penroll", "share_frl"] + fs.BASE_CONTROLS:
        df[c] = df[c].astype(float)

    rows = []
    for st in [s for s in STUDY_STATES if s not in fs.EXCLUDE_STATES]:
        for spec, (screens, controls) in fs.SPECS.items():
            if spec == "deneault" and st != "LA":
                continue
            if spec == "main" and st in fs.NO_FRL_STATES:
                controls = fs.BASE_CONTROLS
            y = "penroll" if spec == "deneault" else "enroll"
            base = fs.sample(df[df["state"] == st], screens, controls)
            n_fs = base["school_id"].nunique()
            d = outcome_sample(base, y) if n_fs else None
            if d is None:
                print(f"  {st} {spec}: no pre and post classes with outcome data; skipped")
                continue
            rf = fs.estimate(d, controls, y=y)
            first = fs.estimate(d, controls)
            rows.append({"state": st, "spec": spec, "outcome": y, "window": d["outcome_window"].iloc[0],
                         "controls": "with_frl" if "share_frl" in controls else "no_frl",
                         **{k: rf[k] for k in ["beta", "se", "p", "n_obs", "n_schools", "classes"]},
                         "schools_first_stage_sample": n_fs, "mean_y_pre": rf[f"mean_{y}_pre"],
                         "mean_dose": rf["mean_dose"], "fs_beta": first["beta"], "fs_se": first["se"],
                         "rf_fs_ratio": rf["beta"] / first["beta"]})
            print(f"  {st} {spec}: {n_fs:,} first-stage schools -> {rf['n_schools']:,} with the outcome "
                  f"in classes {rf['classes']}")
    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    show = out.drop(columns=["controls"]).round({"beta": 3, "se": 3, "p": 4, "mean_y_pre": 3, "mean_dose": 3,
                                                 "fs_beta": 3, "fs_se": 3, "rf_fs_ratio": 3})
    print("\nReduced form by state (outcome as a share; Deneault LA: penroll)")
    print(show.to_string(index=False))
    print(f"\nWrote {PANEL_OUT.name} and {OUT.relative_to(OUTPUT.parent)}")


if __name__ == "__main__":
    main()
