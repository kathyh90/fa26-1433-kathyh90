"""First-stage regressions by state: FAFSA completion on dose x post.

Deneault (2023), main_aejep.do:
    areg rate_comp trt controls y_* [aw = wt], absorb(sitecode) vce(cluster sitecode)
with trt = (1 - pre-period completion rate) x post. Here, for each state:

    fcr_it = beta * dose_i * post_t + controls_it + school_i + class_t + error,
    weighted by `weight`, standard errors clustered by school (CRV1).

Sample (decided 2026-10-27, docs/DECISIONS.md): treated public schools with
post-mandate classes, in the estimation window (`in_window`), passing the
screens, with complete controls in every window class (Deneault drops schools
missing any key variable). "<5" completions are missing; fcr is capped at 1.
The denominator is CCD grade-12 enrollment until state graduate counts are
added, so these estimates are preliminary.

Specifications:
  main         project-design screens (regular or career/technical, not virtual,
               ...); controls: race shares, enrollment and its square (per
               1,000), FRL share
  no_frl       as main without the FRL share (Deneault's controls minus ACT)
  clean_dose   as main, but dose from the two newest classes before the reference
               class that are not 2020, 2021 (COVID) or 2024 (FAFSA rollout); only
               in states whose dose classes this moves (AL, TX, CA, IN, NH)
  deneault     Deneault's screens (drops only special education; keeps
               alternative and virtual schools) and controls (minus ACT), every
               state; vs. no_frl it differs only in the screens (robustness)
  common_window  as main on the common window e = -3 ... 0 in every state
               (in_window_common, its own balance and senior-share screens); the
               main input to the cross-state pooling (DECISIONS 2026-11-15)

Colorado (design undecided) and Maryland (no FAFSA requirement) are left out
(EXCLUDE_STATES). In states listed in NO_FRL_STATES, main drops the FRL share
because a window class has no FRL data (Illinois reported none to CCD for
2020-21, its first covered class); the `controls` column of the output records which set was used.

Writes output/tables/first_stage_by_state.csv.

Usage (from the repository root):
    uv run --locked python code/06_first_stage.py
"""

import duckdb
import pandas as pd
import pyfixest as pf

from config import DERIVED, OUTPUT, STUDY_STATES

PANEL = DERIVED / "analysis_panel.parquet"
OUT = OUTPUT / "tables" / "first_stage_by_state.csv"
# Left out of every estimate: CO until its covered-vs-uncovered design is decided;
# MD has no FAFSA requirement (county boards must only encourage and assist;
# Md. Code Educ. § 7-212). Remove a state here to put it back.
EXCLUDE_STATES = {"CO", "MD"}
# Main spec without FRL where a window class lacks FRL data. Revisit IL with
# FRL from the Illinois Report Card (state data, step 4).
NO_FRL_STATES = {"IL"}
DESIGN_SCREENS = ["f_in_ccd", "f_regular_cte", "f_not_virtual", "f_senior_share_ok", "f_ratio_ok",
                  "f_dose_ok", "f_balanced"]
DENEAULT_SCREENS = ["f_in_ccd", "f_not_special_ed", "f_cohort9_positive", "f_ratio_ok",
                    "f_dose_ok", "f_balanced"]
BASE_CONTROLS = ["share_white", "share_black", "share_hispanic", "share_asian", "enroll_k", "enroll_k_sq"]
CLEAN_SCREENS = [("f_dose_clean_ok" if f == "f_dose_ok" else f) for f in DESIGN_SCREENS]
COMMON_SCREENS = [(f + "_common" if f in ("f_balanced", "f_senior_share_ok") else f) for f in DESIGN_SCREENS]
SPECS = {
    "main": (DESIGN_SCREENS, BASE_CONTROLS + ["share_frl"]),
    "no_frl": (DESIGN_SCREENS, BASE_CONTROLS),
    "deneault": (DENEAULT_SCREENS, BASE_CONTROLS),
    "clean_dose": (CLEAN_SCREENS, BASE_CONTROLS + ["share_frl"]),
    "common_window": (COMMON_SCREENS, BASE_CONTROLS + ["share_frl"]),
}
FRL_SPECS = {"main", "clean_dose", "common_window"}   # specs whose controls include the FRL share


def spec_panel(df, spec):
    """The panel as the spec uses it: clean_dose swaps in dose_clean (dose classes
    moved off the COVID and 2024 classes); common_window swaps in the common
    window (e = -3 ... 0); other specs return df unchanged."""
    if spec == "clean_dose":
        return df.assign(dose=df["dose_clean"], pre_fcr=df["pre_fcr_clean"])
    if spec == "common_window":
        return df.assign(in_window=df["in_window_common"])
    return df


def spec_controls(spec, state):
    """The spec's controls, without the FRL share in NO_FRL_STATES."""
    controls = SPECS[spec][1]
    return BASE_CONTROLS if spec in FRL_SPECS and state in NO_FRL_STATES else controls


def runs(df_state, spec):
    """clean_dose runs only in states whose dose classes it moves (elsewhere it equals main)."""
    return spec != "clean_dose" or bool(df_state["dose_shifted"].any())


def sample(df, screens, controls, y="fcr"):
    """Window rows of schools passing the screens with complete controls and
    outcome y in every window class."""
    d = df[df["treated"] & (df["n_post_classes"] > 0) & df["in_window"] & df[screens].all(axis=1)]
    complete = d[controls + [y, "weight"]].notna().all(axis=1).groupby(d["school_id"]).transform("all")
    return d[complete].copy()


def estimate(d, controls, y="fcr"):
    """Fit y on dose x post (first stage for y = fcr; reduced form in step 8) on
    one state's sample; return beta, SE, and sample sizes."""
    d = d.assign(trt=d["dose"] * d["post"].astype(float))
    fml = f"{y} ~ trt + " + " + ".join(controls) + " | school_id + class_year"
    fit = pf.feols(fml, data=d, weights="weight", vcov={"CRV1": "school_id"})
    pre = d[~d["post"]]
    return {
        "beta": fit.coef()["trt"], "se": fit.se()["trt"], "p": fit.pvalue()["trt"],
        "n_obs": int(fit._N), "n_schools": d["school_id"].nunique(),
        "classes": f"{d['class_year'].min()}-{d['class_year'].max()}",
        f"mean_{y}_pre": (pre[y] * pre["weight"]).sum() / pre["weight"].sum(),
        "mean_dose": d.drop_duplicates("school_id")["dose"].mean(),
    }


def main():
    df = duckdb.connect().execute(f"SELECT * FROM read_parquet('{PANEL.as_posix()}')").df()
    df["enroll_k"] = df["enroll_total"].astype(float) / 1000
    df["enroll_k_sq"] = df["enroll_k"] ** 2
    for c in ["fcr", "dose", "dose_clean", "pre_fcr_clean", "weight"] + BASE_CONTROLS + ["share_frl"]:
        df[c] = df[c].astype(float)
    print(f"Analysis panel: {len(df):,} rows; states left out: {sorted(EXCLUDE_STATES)}")

    rows = []
    states = [s for s in STUDY_STATES if s in set(df.loc[df["treated"] & (df["n_post_classes"] > 0), "state"])]
    for st in states:
        if st in EXCLUDE_STATES:
            continue
        for spec, (screens, _) in SPECS.items():
            if not runs(df[df["state"] == st], spec):
                continue
            controls = spec_controls(spec, st)
            d = sample(spec_panel(df[df["state"] == st], spec), screens, controls)
            if d["school_id"].nunique() < 2 or not d["post"].any():
                print(f"  {st} {spec}: too few schools or no post classes; skipped")
                continue
            rows.append({"state": st, "spec": spec,
                         "controls": "with_frl" if "share_frl" in controls else "no_frl",
                         **estimate(d, controls)})
    out = pd.DataFrame(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False)

    show = out.copy()
    for c in ["beta", "se", "mean_fcr_pre", "mean_dose"]:
        show[c] = show[c].round(3)
    show["p"] = show["p"].round(4)
    print("\nFirst stage by state (preliminary: CCD grade-12 denominator; Deneault LA: 0.421)")
    print(show.to_string(index=False))
    print(f"\nWrote {OUT.relative_to(OUTPUT.parent)}")


if __name__ == "__main__":
    main()
