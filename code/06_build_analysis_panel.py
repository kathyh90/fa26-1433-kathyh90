"""Build the school x class analysis panel for the first stage, with sample flags.

Merges data/derived/fsa_school_panel.parquet (FAFSA completions),
ccd_school_panel.parquet (denominator, weights, controls, screens), and
policy_timing.parquet (event time, dose and reference classes). Following
Deneault (2023; her mergedata_aejep.do and main_aejep.do):

  fcr     = completed FAFSAs through June / seniors, capped at 1. The
            denominator here is CCD grade-12 enrollment (fall of the senior
            year); state graduate counts replace it later. "<5" completions
            are missing, as in Deneault.
  dose    = 1 - mean fcr over the two dose classes (both required)
  weight  = mean over pre-mandate classes of total enrollment / grades offered
  controls: shares white, Black, Hispanic, Asian; total enrollment and its
            square; FRL share (added). Deneault also controls for school ACT,
            which is not yet in the data.

No rows are dropped. Each sample screen is a column (f_*) so the sample rules
can be chosen and varied later; the script prints how many schools each state
keeps under Deneault's screens and under the project design's screens.

Colorado: only Fund My Future grantee schools have policy timing; other
Colorado schools are kept with treated = False and no event time.

Writes data/derived/analysis_panel.parquet (key: school_id, class_year).

Usage (from the repository root):
    uv run --locked python code/06_build_analysis_panel.py
"""

import duckdb
import numpy as np
import pandas as pd

from config import DERIVED, OUTPUT

FSA = DERIVED / "fsa_school_panel.parquet"
CCD = DERIVED / "ccd_school_panel.parquet"
TIMING = DERIVED / "policy_timing.parquet"
OUT = DERIVED / "analysis_panel.parquet"
SCREENS_TABLE = OUTPUT / "tables" / "sample_screens_by_state.csv"
STUDY_STATES = ["LA", "IL", "AL", "TX", "CO", "MD", "CA", "IN", "NH",
                "NE", "OK", "NY", "NJ", "CT", "PA"]
WINDOW = (-4, 1)   # Deneault's estimation window in event time (e = -4 ... +1)
VIRTUAL = {"yes", "full virtual", "exclusively virtual", "primarily virtual",
           "virtual with face to face options"}


def load():
    """FSA public schools joined to CCD and policy timing, with row counts."""
    con = duckdb.connect()
    fsa = con.execute(f"SELECT * FROM read_parquet('{FSA.as_posix()}')").df()
    n_all = len(fsa)
    fsa = fsa[fsa["sector"] == "public"]
    print(f"FSA school x class rows: {n_all:,}; public: {len(fsa):,} "
          f"(dropped {n_all - len(fsa):,} private and non-NCES rows; CCD covers public schools only)")
    ccd = con.execute(f"SELECT * FROM read_parquet('{CCD.as_posix()}')").df()
    ccd = ccd.drop(columns=["state", "name", "city"])
    df = fsa.merge(ccd, on=["school_id", "class_year"], how="left", indicator=True)
    print(f"  joined to CCD: {(df['_merge'] == 'both').sum():,} rows; no CCD row: "
          f"{(df['_merge'] == 'left_only').sum():,} (mostly the class of 2026, whose CCD year is not out)")
    df = df.drop(columns="_merge")

    timing = con.execute(f"SELECT * FROM read_parquet('{TIMING.as_posix()}')").df()
    statewide = timing[timing["school_id"].isna()].drop(columns="school_id")
    by_school = timing[timing["school_id"].notna()].drop(columns="state")
    df = pd.concat([
        df[df["state"] != "CO"].merge(statewide, on="state", how="left"),
        df[df["state"] == "CO"].merge(by_school, on="school_id", how="left"),
    ], ignore_index=True)
    df["treated"] = df["first_covered_class"].notna()
    return df


def add_outcomes(df):
    """Completion rate, event time, post indicator, and treatment window."""
    df["denominator"] = df["enroll_g12"].astype("Float64")
    df["denominator_source"] = np.where(df["denominator"].notna(), "ccd_grade12", None)
    raw = df["completed_jun"].astype("Float64") / df["denominator"].where(df["denominator"] > 0)
    df["fcr_capped"] = raw > 1
    df["fcr"] = raw.clip(upper=1)
    df["e"] = (df["class_year"] - df["first_covered_class"]).astype("Int64")
    last = df["last_covered_class"].fillna(9999)
    df["post"] = (df["class_year"] >= df["first_covered_class"]) & (df["class_year"] <= last)
    df["post"] = df["post"].fillna(False).astype(bool)
    df["partial_rollout"] = (df["class_year"] == df["partial_rollout_class"]).fillna(False).astype(bool)
    df["after_repeal"] = (df["class_year"] > df["last_covered_class"]).fillna(False).astype(bool)
    return df


def add_school_measures(df):
    """Dose, weight, cohort, ratio, and controls; school-level ones are constant within school."""
    g = df.groupby("school_id")
    in_dose = (df["class_year"] == df["dose_class_1"]) | (df["class_year"] == df["dose_class_2"])
    dose_fcr = df["fcr"].where(in_dose)
    n_dose = dose_fcr.notna().groupby(df["school_id"]).transform("sum")
    df["pre_fcr"] = dose_fcr.groupby(df["school_id"]).transform("mean").where(n_dose == 2)
    df["dose"] = 1 - df["pre_fcr"]

    pre = df["class_year"] < df["first_covered_class"]
    per_grade = (df["enroll_total"].astype("Float64") / df["n_grades"].astype("Float64")).where(pre)
    df["weight"] = per_grade.groupby(df["school_id"]).transform("mean")

    # 9th-grade cohort of a class: grade-9 enrollment three years earlier.
    g9 = df[["school_id", "class_year", "enroll_g09"]].assign(class_year=lambda d: d["class_year"] + 3)
    df = df.merge(g9.rename(columns={"enroll_g09": "cohort9"}), on=["school_id", "class_year"], how="left")

    total = df["enroll_total"].astype("Float64")
    df["student_teacher_ratio"] = total / df["teachers_fte"].where(df["teachers_fte"] > 0)
    for race in ["white", "black", "hispanic", "asian"]:
        df[f"share_{race}"] = df[f"race_{race}"].astype("Float64") / total.where(total > 0)
    df["share_frl"] = (df["frl_total"].astype("Float64") / total.where(total > 0)).clip(upper=1)
    df["enroll_total_sq"] = total ** 2
    return df


def window_classes(df):
    """Classes each treated school's estimation window must contain.

    Event time WINDOW (e = -4 ... +1; to e = 0 when only one post class
    exists), limited to classes with a denominator (FSA from 2015; CCD grade 12
    through the newest CCD year) and to covered classes, skipping a
    partial-rollout class.
    """
    first_denominator = int(df.loc[df["denominator"].notna(), "class_year"].min())
    last_denominator = int(df.loc[df["denominator"].notna(), "class_year"].max())
    school = df.drop_duplicates("school_id").set_index("school_id")
    school = school[school["treated"]]
    out = {}
    lo, hi = WINDOW
    for sid, r in school.iterrows():
        first = int(r["first_covered_class"])
        upper = 0 if r["n_post_classes"] == 1 else hi
        last = min(first + upper, last_denominator,
                   int(r["last_covered_class"]) if pd.notna(r["last_covered_class"]) else 9999)
        start = max(first + lo, first_denominator)
        partial = r["partial_rollout_class"]
        out[sid] = [y for y in range(start, last + 1) if not (pd.notna(partial) and y == int(partial))]
    return out


def add_flags(df):
    """Sample screens as booleans (school-level screens are constant within school)."""
    by = df.groupby("school_id")
    df["f_in_ccd"] = by["enroll_total"].transform(lambda s: s.notna().any())
    df["f_not_special_ed"] = ~by["school_type_std"].transform(lambda s: (s == "special_education").any())
    df["f_regular"] = by["school_type_std"].transform(lambda s: s.dropna().eq("regular").all() and s.notna().any())
    is_virtual = df["virtual"].fillna("").str.strip().str.lower().isin(VIRTUAL)
    df["f_not_virtual"] = ~is_virtual.groupby(df["school_id"]).transform("any")
    # Deneault drops schools whose 9th-grade cohort is ever 0 or missing; CCD
    # grade 9 starts in 2014-15, so only cohorts from the class of 2018 exist.
    has9 = df["cohort9"].notna()
    df["f_cohort9_positive"] = ~(has9 & (df["cohort9"] <= 0)).groupby(df["school_id"]).transform("any")
    r = df["student_teacher_ratio"]
    df["f_ratio_ok"] = (~(r < 5).groupby(df["school_id"]).transform("any")) & \
        (r.groupby(df["school_id"]).transform("min").fillna(0) <= 100)
    df["f_dose_ok"] = df["pre_fcr"].notna()

    classes = df["school_id"].map(window_classes(df))
    df["in_window"] = [isinstance(c, list) and y in c for c, y in zip(classes, df["class_year"])]
    need = classes.map(lambda c: len(c) if isinstance(c, list) else 0)
    have = (df["in_window"] & df["fcr"].notna()).groupby(df["school_id"]).transform("sum")
    df["window_classes_needed"] = need
    df["f_balanced"] = (need > 0) & (have == need)
    return df


def report(df):
    """Schools kept by state under Deneault's screens and the project design's screens."""
    school = df.drop_duplicates("school_id").set_index("school_id")
    school = school[school["treated"] & (school["n_post_classes"] > 0)]
    deneault = ["f_in_ccd", "f_not_special_ed", "f_cohort9_positive", "f_ratio_ok", "f_dose_ok", "f_balanced"]
    design = ["f_in_ccd", "f_regular", "f_not_virtual", "f_cohort9_positive", "f_ratio_ok", "f_dose_ok", "f_balanced"]
    rows = []
    for st, g in school.groupby("state"):
        row = {"state": st, "treated public schools": len(g)}
        keep = pd.Series(True, index=g.index)
        for f in design:
            keep &= g[f]
            row[f.removeprefix("f_")] = int(keep.sum())
        row["Deneault screens"] = int(g[deneault].all(axis=1).sum())
        rows.append(row)
    out = pd.DataFrame(rows).set_index("state").reindex([s for s in STUDY_STATES if s in school["state"].unique()])
    print("\nSchools with post-mandate classes kept after each screen (design order, cumulative),")
    print("and under Deneault's screens (no regular/virtual screen; special ed dropped):")
    print(out.to_string())
    SCREENS_TABLE.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(SCREENS_TABLE)
    print(f"Wrote {SCREENS_TABLE.relative_to(OUTPUT.parent)}")


def main():
    df = load()
    df = add_outcomes(df)
    df = add_school_measures(df)
    df = add_flags(df)
    if df.duplicated(["school_id", "class_year"]).any():
        raise ValueError("duplicate (school_id, class_year) rows")
    df = df.sort_values(["state", "school_id", "class_year"]).reset_index(drop=True)
    df.to_parquet(OUT, index=False)
    print(f"\nWrote {OUT.name}: {len(df):,} school x class rows, {df['school_id'].nunique():,} public schools")
    print(f"  fcr available: {df['fcr'].notna().sum():,} rows; capped at 1: {int(df['fcr_capped'].sum()):,}; "
          f"completions suppressed (<5): {int(df['completed_jun_lt5'].sum()):,}")
    report(df)


if __name__ == "__main__":
    main()
