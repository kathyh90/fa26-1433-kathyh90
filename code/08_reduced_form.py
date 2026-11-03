"""Reduced form by state: college enrollment on dose x post.

Merges the state college-going outcomes (state_outcomes.parquet, step 7) onto
the analysis panel (step 5) by state, class, and school_id, then for each state

    enroll_it = beta * dose_i * post_t + controls_it + school_i + class_t + error,

with the first stage's weights, screens, controls, and clustering (step 6,
06_first_stage.sample / estimate). enroll = pct_enrolled / 100, the state's
published enrollment rate as a share (`window` says which rate; see
07_build_state_outcomes.py). The deneault spec (Deneault's screens, every state)
uses enroll, except in Louisiana, where it uses her outcome, penroll (replication).

Sample (DECISIONS 2026-11-01): the first-stage sample, limited to the window
classes in which the state has outcome data (Texas starts at class 2019;
California ends at 2023 and Indiana at 2024), keeping schools with the outcome
in every one of those classes. A state needs a pre and a post class left;
Oklahoma, New York, and New Jersey have no post-period outcome yet.

For comparison, the first stage is re-estimated on the same sample (fs_beta);
rf_fs_ratio = beta / fs_beta is the implied effect on enrollment per unit of
FAFSA completion (a Wald ratio, no standard error). dropped_no_outcome and
dropped_partial_outcome count the first-stage schools left out by the outcome
requirement (see `attrition`).

Graduate-denominator specification (`grad_denom`, DECISIONS 2026-11-02): as
`main`, but FAFSA completion = completions / the state's graduate count of the
class (`outcome_graduates`, the same count as the outcome's denominator)
instead of CCD grade-12 enrollment, with dose recomputed from it by the step-5
rules (`with_graduate_denominator`). The sample stays within the baseline
screens (incl. f_balanced), limited to window classes with graduate counts,
keeping schools with a count in each, and only schools in the baseline main
first-stage sample, so the two differ only by the denominator (`grad_sample`). Its first stage on that sample, before
requiring the outcome, is written to first_stage_grad_by_state.csv. States
without graduate counts (Illinois) or without counts for the dose or post
classes (New York, Oklahoma) are skipped; New Jersey (4-year cohort graduates
from its graduation-rate files) has the first stage but no reduced form until
its class-2025 outcome is released. graduate_denominator_check.csv
compares the graduate count with CCD grade-12 enrollment by state and class, to
check that each state's count is consistent over time.

Writes data/derived/reduced_form_panel.parquet (panel + outcome columns) and
output/tables/reduced_form_by_state.csv, first_stage_grad_by_state.csv, and
graduate_denominator_check.csv.

Usage (from the repository root):
    uv run --locked python code/08_reduced_form.py
"""

import importlib.util

import duckdb
import pandas as pd

from config import DERIVED, OUTPUT, ROOT, STUDY_STATES

PANEL_OUT = DERIVED / "reduced_form_panel.parquet"
OUT = OUTPUT / "tables" / "reduced_form_by_state.csv"
OUT_FS_GRAD = OUTPUT / "tables" / "first_stage_grad_by_state.csv"
OUT_GRAD_CHECK = OUTPUT / "tables" / "graduate_denominator_check.csv"
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


def attrition(base, y):
    """First-stage schools left out of the reduced form, in the window classes
    that have outcome data: no outcome in any of them (unlinked or never
    published), or missing in some (mostly suppressed small cells)."""
    b = base[base["class_year"].isin(set(base.loc[base[y].notna(), "class_year"]))]
    got = b[y].notna().groupby(b["school_id"]).agg(["sum", "size"])
    return {"dropped_no_outcome": int((got["sum"] == 0).sum()),
            "dropped_partial_outcome": int(((got["sum"] > 0) & (got["sum"] < got["size"])).sum())}


def prepare(df):
    """Add the enrollment controls (per 1,000 and squared) and cast analysis columns to float."""
    df["enroll_k"] = df["enroll_total"].astype(float) / 1000
    df["enroll_k_sq"] = df["enroll_k"] ** 2
    for c in ["fcr", "dose", "weight", "enroll", "penroll", "share_frl"] + fs.BASE_CONTROLS:
        df[c] = df[c].astype(float)
    return df


def state_sample(df, st, spec):
    """One state's first-stage sample for a spec and its reduced-form sample (None
    if no pre and post outcome classes); returns (base, sample, controls, y)."""
    screens, controls = fs.SPECS[spec]
    if spec == "main" and st in fs.NO_FRL_STATES:
        controls = fs.BASE_CONTROLS
    y = "penroll" if spec == "deneault" and st == "LA" else "enroll"
    base = fs.sample(df[df["state"] == st], screens, controls)
    return base, (outcome_sample(base, y) if len(base) else None), controls, y


def with_graduate_denominator(df):
    """Copy of the merged panel with fcr, pre_fcr, dose, and f_dose_ok recomputed on
    the state's graduate count instead of CCD grade-12 enrollment (step-5 rules:
    fcr capped at 1; dose = 1 - mean fcr over the two dose classes, both required).
    Window classes in which the state has no graduate count leave the window."""
    g = df.copy()
    grads = g["outcome_graduates"].astype(float)
    raw = g["completed_jun"].astype(float) / grads.where(grads > 0)
    g["fcr_capped"] = raw > 1
    g["fcr"] = raw.clip(upper=1)
    in_dose = (g["class_year"] == g["dose_class_1"]) | (g["class_year"] == g["dose_class_2"])
    dose_fcr = g["fcr"].where(in_dose)
    n_dose = dose_fcr.notna().groupby(g["school_id"]).transform("sum")
    g["pre_fcr"] = dose_fcr.groupby(g["school_id"]).transform("mean").where(n_dose == 2)
    g["dose"] = 1 - g["pre_fcr"]
    g["f_dose_ok"] = g["pre_fcr"].notna()
    have = g[g["fcr"].notna()].groupby("state")["class_year"].agg(set)
    g["in_window"] &= pd.Series([y in have.get(s, set()) for s, y in zip(g["state"], g["class_year"])], index=g.index)
    return g


def graduate_check(df):
    """Graduate count vs. CCD grade-12 enrollment by state and class, over treated
    public schools with both: a break in the ratio flags a change in how the state
    counts graduates (statewide shifts are absorbed by class FE; school-level ones are not)."""
    d = df[df["treated"] & df["outcome_graduates"].notna() & (df["enroll_g12"] > 0)]
    r = d["outcome_graduates"] / d["enroll_g12"]
    t = d.assign(r=r, off=(r < 0.5) | (r > 1.5)).groupby(["state", "class_year"]).agg(
        schools=("school_id", "size"), graduates=("outcome_graduates", "sum"), ccd_grade12=("enroll_g12", "sum"),
        median_school_ratio=("r", "median"), schools_ratio_outside_half_to_1_5=("off", "sum")).reset_index()
    t.insert(5, "ratio", t["graduates"] / t["ccd_grade12"])
    order = {s: i for i, s in enumerate(STUDY_STATES)}
    return t.sort_values(["state", "class_year"], key=lambda c: c.map(order) if c.name == "state" else c).round(4)


def grad_sample(df, g, st):
    """state_sample for grad_denom: main spec on the graduate-denominator panel g,
    limited to schools in the state's baseline main first-stage sample."""
    keep = set(state_sample(df, st, "main")[0]["school_id"])
    return state_sample(g[(g["state"] == st) & g["school_id"].isin(keep)], st, "main")


def first_stage_grad(df, g):
    """First stage with the graduate denominator on each state's main-spec sample
    (before requiring the outcome), with the baseline sample size for comparison."""
    rows = []
    for st in [s for s in STUDY_STATES if s not in fs.EXCLUDE_STATES]:
        base, _, controls, _ = grad_sample(df, g, st)
        if base["school_id"].nunique() < 2 or not base["post"].any() or base["post"].all():
            print(f"  {st} grad_denom first stage: no graduate counts for the dose, pre, or post classes; skipped")
            continue
        rows.append({"state": st, "spec": "grad_denom",
                     "controls": "with_frl" if "share_frl" in controls else "no_frl", **fs.estimate(base, controls)})
    return pd.DataFrame(rows)


fs = first_stage_module()


def main():
    df = merge_outcomes()
    df.to_parquet(PANEL_OUT, index=False)
    df = prepare(df)
    g = with_graduate_denominator(df)
    check = graduate_check(df)
    check.to_csv(OUT_GRAD_CHECK, index=False)
    print("\nGraduates / CCD grade 12 by class (treated public schools with both)")
    print(check.pivot(index="class_year", columns="state", values="ratio").round(3).to_string())
    print(f"Graduate-denominator fcr: {g['fcr'].notna().sum():,} rows; capped at 1: {int(g['fcr_capped'].sum()):,}")

    fs_grad = first_stage_grad(df, g)
    fs_grad.to_csv(OUT_FS_GRAD, index=False)

    rows = []
    for st in [s for s in STUDY_STATES if s not in fs.EXCLUDE_STATES]:
        for spec in [*fs.SPECS, "grad_denom"]:
            # grad_denom = main spec on the panel with the graduate denominator
            base, d, controls, y = grad_sample(df, g, st) if spec == "grad_denom" else state_sample(df, st, spec)
            n_fs = base["school_id"].nunique()
            if d is None:
                print(f"  {st} {spec}: no pre and post classes with outcome data; skipped")
                continue
            rf = fs.estimate(d, controls, y=y)
            first = fs.estimate(d, controls)
            rows.append({"state": st, "spec": spec, "outcome": y, "window": d["outcome_window"].iloc[0],
                         "controls": "with_frl" if "share_frl" in controls else "no_frl",
                         **{k: rf[k] for k in ["beta", "se", "p", "n_obs", "n_schools", "classes"]},
                         "schools_first_stage_sample": n_fs, **attrition(base, y), "mean_y_pre": rf[f"mean_{y}_pre"],
                         "mean_dose": rf["mean_dose"], "fs_beta": first["beta"], "fs_se": first["se"],
                         "rf_fs_ratio": rf["beta"] / first["beta"]})
            drop = rows[-1]
            print(f"  {st} {spec}: {n_fs:,} first-stage schools -> {rf['n_schools']:,} with the outcome "
                  f"in classes {rf['classes']} (dropped: {drop['dropped_no_outcome']} with no outcome, "
                  f"{drop['dropped_partial_outcome']} missing it in some classes)")
    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)
    show = out.drop(columns=["controls"]).round({"beta": 3, "se": 3, "p": 4, "mean_y_pre": 3, "mean_dose": 3,
                                                 "fs_beta": 3, "fs_se": 3, "rf_fs_ratio": 3})
    print("\nReduced form by state (outcome as a share; Deneault LA: penroll)")
    print(show.to_string(index=False))
    print("\nFirst stage with the graduate denominator (main spec sample before requiring the outcome)")
    print(fs_grad.round(3).to_string(index=False))
    print(f"\nWrote {PANEL_OUT.name}, {OUT.relative_to(OUTPUT.parent)}, {OUT_FS_GRAD.relative_to(OUTPUT.parent)}, "
          f"{OUT_GRAD_CHECK.relative_to(OUTPUT.parent)}")


if __name__ == "__main__":
    main()
