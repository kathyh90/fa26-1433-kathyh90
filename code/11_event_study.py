"""Event study by state: dose x event-time effects and pre-trend tests.

Deneault's dosage DiD replaces the single D_s x Post_t with one interaction per
class (project-design.md, "Event study"). For each state and outcome y:

    y_it = sum_{k != -1} beta_k * dose_i * 1[e_it = k] + controls_it + school_i + class_t + error,

with the main specification's controls, weights, and school-clustered SEs (steps
6 and 8). e = -1 (the reference class) is omitted, so beta_k is the gap in y
between a school with dose 1 and one with dose 0 in class k, relative to that gap
in the reference class. Under parallel trends, beta_k = 0 for every k < -1.

Sample: the schools in the state's main first-stage sample (steps 6/8,
`state_sample`), over **all** their classes with the outcome and complete
controls, not just the estimation window (project-design.md: "The event study
uses all available years"), so the panel is unbalanced outside the window;
n_schools per class is reported. Partial-rollout and post-repeal classes
(Louisiana after 2024) are left out. y = fcr (first stage) or enroll (reduced
form). States whose outcome has no class other than e = -1 are skipped; states
with no post-period outcome yet (OK, NY, NJ enrollment) get pre-period
coefficients only.

Specifications (`spec`):
  main         FAFSA completion = completions / CCD grade-12 enrollment (step 5)
  grad_denom   completions / the state's graduate count, with dose recomputed from
               it (step 8 `with_graduate_denominator`), on the schools of step 8's
               graduate-denominator sample (`grad_sample`). Classes without a
               graduate count drop out (TX before e = -3, NJ before e = -5); IL has
               no counts, and NY and OK none after the mandate, so their samples are
               empty. Same controls, weights, and enrollment outcome as main.

Pre-trend tests (school-clustered Wald F, df = (q, clusters - 1)):
  pre_all       beta_k = 0 for all k <= -2
  pre_no_dose   beta_k = 0 for all k <= -4, leaving out the dose classes (e = -3, -2).
                For y = fcr, beta_-3 and beta_-2 are mechanically negative: dose is
                1 - mean fcr in those classes, so noise in them reverts by e = -1.
                pre_no_dose is the clean parallel-trends test for the first stage.

Writes output/tables/event_study_by_state.csv (one row per state, outcome, and
class), output/tables/event_study_pretrends.csv (one row per state, outcome, and
test), and output/figures/event_study_{fcr,enroll}.png (both specs overlaid).

Usage (from the repository root):
    uv run --locked python code/11_event_study.py
"""

import importlib.util

import matplotlib
import numpy as np
import pandas as pd
import pyfixest as pf
from scipy import stats

from config import OUTPUT, ROOT, STUDY_STATES

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT_COEF = OUTPUT / "tables" / "event_study_by_state.csv"
OUT_TEST = OUTPUT / "tables" / "event_study_pretrends.csv"
FIGURES = OUTPUT / "figures"
REF = -1          # omitted event time (reference class)
DOSE_E = {-3, -2}  # dose classes
OUTCOMES = {"fcr": "FAFSA completion rate", "enroll": "College enrollment rate"}
SPECS = {"main": ("CCD grade-12 denominator", "#2a78d6"), "grad_denom": ("Graduate denominator", "#eb6834")}
COLOR = {"text": "#0b0b0b", "muted": "#52514e", "grid": "#e4e3df", "surface": "#fcfcfb"}


def load_step8():
    """Step 8 as a module (file name starts with a digit, so load it by path)."""
    spec = importlib.util.spec_from_file_location("reduced_form", ROOT / "code" / "08_reduced_form.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def es_name(k):
    """Regressor name for event time k (e.g. es_m3, es_p0)."""
    return f"es_{'m' if k < 0 else 'p'}{abs(k)}"


def es_sample(df, schools, controls, y):
    """All classes of the given schools with y, controls, and weight present,
    excluding partial-rollout and post-repeal classes; prints rows dropped."""
    d = df[df["school_id"].isin(schools)]
    n0 = len(d)
    d = d[~d["partial_rollout"] & ~d["after_repeal"]]
    n1 = len(d)
    d = d[d[[y, "dose", "weight", *controls]].notna().all(axis=1)].copy()
    print(f"    {y}: {n0:,} rows of {len(schools):,} sample schools -> {n1:,} without partial-rollout/"
          f"post-repeal classes -> {len(d):,} with outcome and controls")
    return d


def wald(fit, names, n_clusters):
    """Cluster-robust Wald F test that the named coefficients are all zero."""
    if not names:
        return np.nan, np.nan
    b = fit.coef()[names].to_numpy()
    idx = [list(fit.coef().index).index(n) for n in names]
    v = fit._vcov[np.ix_(idx, idx)]
    f = float(b @ np.linalg.solve(v, b)) / len(names)
    return f, float(stats.f.sf(f, len(names), n_clusters - 1))


def event_study(d, controls, y):
    """Fit the event study on one state's sample; returns (coefficient rows, test rows)."""
    ks = sorted(k for k in d["e"].dropna().unique() if k != REF)
    if REF not in set(d["e"]) or not ks:
        return None
    for k in ks:
        d[es_name(k)] = d["dose"] * (d["e"] == k)
    fml = f"{y} ~ " + " + ".join([es_name(k) for k in ks] + controls) + " | school_id + class_year"
    fit = pf.feols(fml, data=d, weights="weight", vcov={"CRV1": "school_id"})
    g = d["school_id"].nunique()
    crit = stats.t.ppf(0.975, g - 1)
    by_e = d.groupby("e").agg(class_year=("class_year", "first"), n_schools=("school_id", "nunique"))
    coefs = [{"e": REF, "beta": 0.0, "se": 0.0}] + [
        {"e": k, "beta": fit.coef()[es_name(k)], "se": fit.se()[es_name(k)]} for k in ks]
    coefs = pd.DataFrame(coefs).merge(by_e, left_on="e", right_index=True).sort_values("e")
    coefs["ci_lo"] = coefs["beta"] - crit * coefs["se"]
    coefs["ci_hi"] = coefs["beta"] + crit * coefs["se"]
    coefs["post"] = coefs["e"] >= 0
    tests = []
    for test, keep in {"pre_all": lambda k: k <= -2, "pre_no_dose": lambda k: k <= -4}.items():
        names = [es_name(k) for k in ks if keep(k)]
        f, p = wald(fit, names, g)
        tests.append({"test": test, "n_coefs": len(names), "F": f, "p": p,
                      "classes": ",".join(str(int(k)) for k in ks if keep(k))})
    meta = {"n_obs": int(fit._N), "n_schools_total": g}
    return coefs.assign(**meta), pd.DataFrame(tests).assign(**meta)


def plot(coef, y):
    """Small multiples, one panel per state: beta_k with 95% CIs by event time."""
    states = [s for s in STUDY_STATES if s in set(coef.loc[coef["outcome"] == y, "state"])]
    ncol = 4
    nrow = -(-len(states) // ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.2 * ncol, 2.6 * nrow), squeeze=False, facecolor=COLOR["surface"])
    for ax, st in zip(axes.flat, states):
        c = coef[(coef["outcome"] == y) & (coef["state"] == st)]
        ax.set_facecolor(COLOR["surface"])
        ax.axhline(0, color=COLOR["muted"], lw=0.8)
        ax.axvline(-0.5, color=COLOR["muted"], lw=0.8, ls=":")
        ax.axvspan(-3.5, -1.5, color=COLOR["grid"], lw=0)   # dose classes
        for i, (spec, (label, color)) in enumerate(SPECS.items()):
            cs = c[c["spec"] == spec]
            x = cs["e"] + (i - 0.5) * 0.24   # side by side so the CIs don't overlap
            ax.vlines(x, cs["ci_lo"], cs["ci_hi"], color=color, lw=2)
            ax.plot(x, cs["beta"], "o-", color=color, lw=2, ms=5, mec=COLOR["surface"], mew=1.5, label=label)
        ax.set_title(st, fontsize=10, color=COLOR["text"], loc="left")
        ax.tick_params(labelsize=8, colors=COLOR["muted"])
        for side in ["top", "right"]:
            ax.spines[side].set_visible(False)
        for side in ["left", "bottom"]:
            ax.spines[side].set_color(COLOR["grid"])
    for ax in axes.flat[len(states):]:
        ax.set_visible(False)
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=2, frameon=False, fontsize=9, labelcolor=COLOR["text"])
    fig.supxlabel("Event time (e = 0: first covered class; e = -1 omitted)", fontsize=9, color=COLOR["text"])
    fig.supylabel(f"Coefficient on dose x class: {OUTCOMES[y]}", fontsize=9, color=COLOR["text"])
    fig.suptitle(f"Event study: {OUTCOMES[y]} (95% CI; shaded: dose classes)", fontsize=11,
                 color=COLOR["text"], x=0.01, ha="left")
    fig.tight_layout()
    FIGURES.mkdir(parents=True, exist_ok=True)
    path = FIGURES / f"event_study_{y}.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


rf = load_step8()


def main():
    df = rf.prepare(rf.merge_outcomes())
    g = rf.with_graduate_denominator(df)
    coef_rows, test_rows = [], []
    for st, spec in [(s, sp) for s in STUDY_STATES if s not in rf.fs.EXCLUDE_STATES for sp in SPECS]:
        panel = g if spec == "grad_denom" else df
        base, _, controls, _ = rf.grad_sample(df, g, st) if spec == "grad_denom" else rf.state_sample(df, st, "main")
        if base["school_id"].nunique() < 2 or not base["post"].any() or base["post"].all():
            print(f"  {st} {spec}: no first-stage sample (no counts or no pre and post classes); skipped")
            continue
        schools = set(base["school_id"])
        print(f"  {st} {spec}: {len(schools):,} first-stage schools")
        for y in OUTCOMES:
            d = es_sample(panel[panel["state"] == st], schools, controls, y)
            res = event_study(d, controls, y) if len(d) else None
            if res is None:
                print(f"    {y}: no class besides the reference class; skipped")
                continue
            for rows, part in zip([coef_rows, test_rows], res):
                rows.append(part.assign(state=st, spec=spec, outcome=y))
    coef = pd.concat(coef_rows, ignore_index=True)
    tests = pd.concat(test_rows, ignore_index=True)
    lead = ["state", "spec", "outcome"]
    coef = coef[lead + [c for c in coef if c not in lead]]
    tests = tests[lead + [c for c in tests if c not in lead]]
    coef.to_csv(OUT_COEF, index=False)
    tests.to_csv(OUT_TEST, index=False)
    paths = [plot(coef, y) for y in OUTCOMES]

    wide = tests.pivot_table(index=["state", "outcome"], columns=["test", "spec"], values="p", sort=False)
    print("\nPre-trend tests (p-values; pre_no_dose excludes e = -3, -2)")
    print(wide.round(3).to_string())
    print(f"\nWrote {OUT_COEF.relative_to(ROOT)}, {OUT_TEST.relative_to(ROOT)}, "
          + ", ".join(str(p.relative_to(ROOT)) for p in paths))


if __name__ == "__main__":
    main()
