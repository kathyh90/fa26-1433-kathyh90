"""Summary statistics of the high schools in the first-stage and reduced-form samples.

Samples (main specification, step 8 `state_sample`): the first-stage sample
(every state with a first stage) and the reduced-form sample (the first-stage
sample limited to window classes with outcome data and schools with the outcome
in all of them; fewer states and schools). Each school is described by its means over its pre-mandate
sample classes, so every statistic is a mean (or SD) **across schools,
unweighted**: e.g. share_black = 0.40 means the average school's student body
is 40% Black, not that 40% of the state's students in these schools are Black.

Writes, for each sample (rows: variable x stat (mean, sd), plus n_schools):
  output/tables/summary_stats_{fs,rf}_by_state.csv          one column per state, and All
  output/tables/summary_stats_{fs,rf}_by_dose_quartile.csv  dose quartiles set within
      each state, then pooled across states (as Deneault's table by dose);
      Q4 = highest dose = lowest pre-mandate FAFSA completion
  (`_fs` = first-stage sample, `_rf` = reduced-form sample). In the
  first-stage sample, `enroll` (college enrollment) is averaged over the
  schools and classes that have it.

Usage (from the repository root):
    uv run --locked python code/09_summary_stats.py
"""

import importlib.util

import pandas as pd

from config import DERIVED, OUTPUT, ROOT, STUDY_STATES

TABLES = OUTPUT / "tables"
OUT_RF_STATE = TABLES / "summary_stats_rf_by_state.csv"   # reduced-form sample
OUT_RF_DOSE = TABLES / "summary_stats_rf_by_dose_quartile.csv"
OUT_FS_STATE = TABLES / "summary_stats_fs_by_state.csv"   # first-stage sample
OUT_FS_DOSE = TABLES / "summary_stats_fs_by_dose_quartile.csv"
SAMPLES = {"first-stage": (0, OUT_FS_STATE, OUT_FS_DOSE),   # index into state_sample's (base, sample, ...)
           "reduced-form": (1, OUT_RF_STATE, OUT_RF_DOSE)}
LOCALES = {"city": "1", "suburb": "2", "town": "3", "rural": "4"}  # first digit of NCES locale
VARS = ["enroll_total", "enroll_g12", "share_white", "share_black", "share_hispanic", "share_asian",
        "share_frl", "charter", *LOCALES, "pre_fcr", "dose", "enroll"]


def load_reduced_form():
    """Step 8 as a module (its file name starts with a digit, so load it by path)."""
    spec = importlib.util.spec_from_file_location("reduced_form", ROOT / "code" / "08_reduced_form.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def school_means(d):
    """One row per school: means of VARS over its pre-mandate classes. Locale and
    charter are 0/1 (missing stays missing); pre_fcr and dose are fixed per school."""
    pre = d[~d["post"]].copy()
    for name, digit in LOCALES.items():
        pre[name] = pre["locale"].astype("string").str[0].eq(digit).astype("Float64")
    pre["charter"] = pre["charter"].astype("Float64")
    return pre.groupby(["state", "school_id"])[VARS].mean().astype(float).reset_index()


def describe(sch, by):
    """Mean and SD of each variable by group, plus all schools, and school counts."""
    groups = list(sch.groupby(by, observed=True)) + [("All", sch)]
    t = pd.DataFrame({k: pd.concat({"mean": g[VARS].mean(), "sd": g[VARS].std()}) for k, g in groups})
    t = t.swaplevel().reindex(pd.MultiIndex.from_product([VARS, ["mean", "sd"]]))
    t.loc[("n_schools", ""), :] = [len(g) for _, g in groups]
    return t.rename_axis(["variable", "stat"]).reset_index().round(4)


def write_tables(d, label, out_state, out_dose):
    """School means of one sample, described by state and by within-state dose
    quartile; writes both CSVs and prints the means."""
    sch = school_means(d)
    sch["dose_quartile"] = sch.groupby("state")["dose"].transform(
        lambda x: pd.qcut(x, 4, labels=["Q1", "Q2", "Q3", "Q4"])).astype(str)
    print(f"\n=== {label} sample (main): {len(sch):,} schools in {sch['state'].nunique()} states ===")
    by_state = describe(sch.assign(state=pd.Categorical(sch["state"], STUDY_STATES)), "state")
    by_dose = describe(sch, "dose_quartile")
    by_state.to_csv(out_state, index=False)
    by_dose.to_csv(out_dose, index=False)
    for name, t in [("state", by_state), ("within-state dose quartile", by_dose)]:
        print(f"\nPre-mandate school means by {name} (unweighted, means only)")
        print(t[t["stat"] != "sd"].drop(columns="stat").round(2).to_string(index=False))
    print(f"Wrote {out_state.relative_to(ROOT)} and {out_dose.relative_to(ROOT)}")


def main():
    rf = load_reduced_form()
    df = rf.prepare(pd.read_parquet(DERIVED / "reduced_form_panel.parquet"))
    TABLES.mkdir(parents=True, exist_ok=True)
    states = [s for s in STUDY_STATES if s not in rf.fs.EXCLUDE_STATES]
    for label, (i, out_state, out_dose) in SAMPLES.items():
        parts = [rf.state_sample(df, st, "main")[i] for st in states]
        write_tables(pd.concat([d for d in parts if d is not None and len(d)]), label, out_state, out_dose)

if __name__ == "__main__":
    main()
