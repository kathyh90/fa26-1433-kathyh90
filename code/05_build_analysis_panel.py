"""Build the school x class analysis panel for the first stage, with sample flags.

Merges data/derived/fsa_school_panel.parquet (FAFSA completions),
ccd_school_panel.parquet (denominator, weights, controls, screens), and each
state's policy timing (event time, dose and reference classes). Following
Deneault (2023; her mergedata_aejep.do and main_aejep.do):

  fcr     = completed FAFSAs through June / seniors, capped at 1. The
            denominator here is CCD grade-12 enrollment (fall of the senior
            year); state graduate counts replace it later. "<5" completions
            are missing, as in Deneault.
  dose    = 1 - mean fcr over the two dose classes (both required)
  dose_clean = the same over the two newest classes before the reference class
            that are not COVID (2020, 2021) or FAFSA-rollout (2024) classes;
            equals dose where the dose classes are already clean (robustness,
            spec clean_dose in step 6)
  weight  = mean over pre-mandate classes of total enrollment / grades offered
  cohort9 = grade-9 enrollment three years earlier (ccd_grade9.parquet, CCD
            from 2011-12, so from the class of 2015 on)
  controls: shares white, Black, Hispanic, Asian; total enrollment and its
            square; FRL share (added). Deneault also controls for school ACT,
            which is not yet in the data.

No rows are dropped. Each sample screen is a column (f_*) so the sample rules
can be chosen and varied later; the script prints how many schools each state
keeps under Deneault's screens and under the project design's screens.

Policy timing comes from hand-entered inputs (sources in docs/source-notes.md):
  data/policy/state_mandates.csv      one row per study state
  data/policy/co_grantee_schools.csv  Colorado's Fund My Future grantee high
                                      schools, the only Colorado schools covered
Timing rule (docs/project-design.md): e = 0 is the first covered class. The
reference class (e = -1) is the last class before it that is not a partial-
rollout class; the dose window is the two classes before the reference class,
again skipping partial-rollout classes. Post classes run from e = 0 to the last
covered class or the newest FSA class, whichever is earlier. Colorado gets one
timing row per grantee school; other Colorado schools are kept with
treated = False and no event time. Every other state gets one statewide row.

Writes data/derived/policy_timing.parquet (one row per state or Colorado
school) and data/derived/analysis_panel.parquet (key: school_id, class_year).

Usage (from the repository root):
    uv run --locked python code/05_build_analysis_panel.py
"""

import duckdb
import numpy as np
import pandas as pd

from config import DERIVED, OUTPUT, ROOT, STUDY_STATES

POLICY = ROOT / "data" / "policy"
STATES = POLICY / "state_mandates.csv"
CO_SCHOOLS = POLICY / "co_grantee_schools.csv"
FSA = DERIVED / "fsa_school_panel.parquet"
CCD = DERIVED / "ccd_school_panel.parquet"
GRADE9 = DERIVED / "ccd_grade9.parquet"   # grade-9 counts, class years 2012 on (step 4)
TIMING = DERIVED / "policy_timing.parquet"
OUT = DERIVED / "analysis_panel.parquet"
COVID = {2020, 2021}
ROLLOUT_2024 = {2024}   # class affected by the delayed 2024-25 FAFSA
SCREENS_TABLE = OUTPUT / "tables" / "sample_screens_by_state.csv"
WINDOW = (-4, 1)   # Deneault's estimation window in event time (e = -4 ... +1)
# Common window for pooling across states (DECISIONS 2026-11-15): every state can supply
# e = -3 ... 0 (Louisiana's FSA data start at e = -3), so the pre-period baseline and post
# class are the same in event time everywhere. Flags with suffix _common (spec common_window).
WINDOWS = {"": WINDOW, "_common": (-3, 0)}
SENIOR_SHARE_MAX = 0.75   # seniors / grades 9-12 above this, in a school offering grade 9: not a graduating class
VIRTUAL = {"yes", "full virtual", "exclusively virtual", "primarily virtual",
           "virtual with face to face options"}


# --- Policy timing -----------------------------------------------------------

def classes_before(year, n, skip):
    """Return the n classes before year, newest first, skipping classes in skip."""
    out, y = [], year - 1
    while len(out) < n:
        if y not in skip:
            out.append(y)
        y -= 1
    return out


def timing(first, partial, last, fsa_first, fsa_last, fsa_prelim):
    """Return the timing fields for one unit (state or school)."""
    skip = {partial} if pd.notna(partial) else set()
    reference, dose2, dose1 = classes_before(first, 3, skip)
    post_last = min(last, fsa_last) if pd.notna(last) else fsa_last
    post = list(range(first, post_last + 1)) if post_last >= first else []
    pre = [dose1, dose2, reference]
    clean2, clean1 = classes_before(reference, 2, skip | COVID | ROLLOUT_2024)
    return {
        "reference_class": reference,
        "dose_class_1": dose1,
        "dose_class_2": dose2,
        "dose_clean_class_1": clean1,
        "dose_clean_class_2": clean2,
        "dose_shifted": (clean1, clean2) != (dose1, dose2),
        "post_first": post[0] if post else pd.NA,
        "post_last": post[-1] if post else pd.NA,
        "n_post_classes": len(post),
        "post_includes_preliminary": fsa_prelim in post,
        "dose_or_reference_preliminary": fsa_prelim in pre,
        "dose_in_fsa": dose1 >= fsa_first,
        "dose_or_reference_covid": bool(COVID & set(pre)),
        "dose_or_reference_2024": bool(ROLLOUT_2024 & set(pre)),
        "post_includes_2024": 2024 in post,
    }


def policy_timing(fsa):
    """Return (and write) the timing fields for each state, or Colorado grantee school."""
    states = pd.read_csv(STATES, dtype=str)
    co = pd.read_csv(CO_SCHOOLS, dtype=str)
    for d in (states, co):
        for c in ("first_covered_class", "partial_rollout_class", "last_covered_class"):
            if c in d:
                d[c] = pd.to_numeric(d[c]).astype("Int64")
    print(f"Read {len(states)} states and {len(co)} Colorado grantee schools")

    fsa_first, fsa_last = int(fsa["class_year"].min()), int(fsa["class_year"].max())
    prelim = int(fsa.loc[fsa["kind"] == "preliminary", "class_year"].max())
    print(f"FSA classes {fsa_first}-{fsa_last} (class of {prelim} preliminary)")

    rows = []
    for _, s in states.iterrows():
        units = ([(r["nces_id"], r["first_covered_class"], r["partial_rollout_class"]) for _, r in co.iterrows()]
                 if s["state"] == "CO" else [(pd.NA, s["first_covered_class"], s["partial_rollout_class"])])
        for school_id, first, partial in units:
            rows.append({"state": s["state"], "school_id": school_id, "policy_type": s["policy_type"],
                         "first_covered_class": first, "partial_rollout_class": partial,
                         "last_covered_class": s["last_covered_class"],
                         **timing(first, partial, s["last_covered_class"], fsa_first, fsa_last, prelim)})
    out = pd.DataFrame(rows)
    for c in ("post_first", "post_last"):
        out[c] = out[c].astype("Int64")
    out.to_parquet(TIMING, index=False)
    print(f"Wrote {TIMING.name}: {len(out)} rows ({out['school_id'].notna().sum()} Colorado schools)")

    show = out.assign(
        dose=out["dose_class_1"].astype(str) + "-" + out["dose_class_2"].astype(str).str[-2:],
        dose_clean=out["dose_clean_class_1"].astype(str) + "," + out["dose_clean_class_2"].astype(str).str[-2:],
        post=out["post_first"].astype(str) + "-" + out["post_last"].astype(str),
        flags=out.apply(lambda r: ", ".join(f for f, on in [
            ("dose not in FSA", not r["dose_in_fsa"]), ("COVID in dose/ref", r["dose_or_reference_covid"]),
            ("2024 in dose/ref", r["dose_or_reference_2024"]), ("2024 in post", r["post_includes_2024"]),
            ("preliminary in dose/ref", r["dose_or_reference_preliminary"]),
            ("post incl. preliminary", r["post_includes_preliminary"])] if on), axis=1))
    show.loc[show["n_post_classes"] == 0, "post"] = "none yet"
    co_rows = show["school_id"].notna()
    print("\n" + show.loc[~co_rows, ["state", "first_covered_class", "dose", "dose_clean", "reference_class",
                                     "post", "flags"]].to_string(index=False))
    print("\nColorado grantee schools:")
    print(show.loc[co_rows].groupby(["first_covered_class", "partial_rollout_class", "dose", "reference_class",
                                     "post", "flags"], dropna=False)["school_id"].count()
          .rename("schools").reset_index().to_string(index=False))
    # Read back through DuckDB so column types match the other panels (nullable ints as floats).
    return duckdb.connect().execute(f"SELECT * FROM read_parquet('{TIMING.as_posix()}')").df()


# --- Analysis panel ----------------------------------------------------------

def load():
    """FSA public schools joined to CCD and policy timing, with row counts."""
    con = duckdb.connect()
    fsa = con.execute(f"SELECT * FROM read_parquet('{FSA.as_posix()}')").df()
    policy = policy_timing(fsa)
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

    statewide = policy[policy["school_id"].isna()].drop(columns="school_id")
    by_school = policy[policy["school_id"].notna()].drop(columns="state")
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


def pre_fcr_over(df, c1, c2):
    """Each school's mean fcr over the classes in columns c1 and c2 (both required, else missing)."""
    in_dose = (df["class_year"] == df[c1]) | (df["class_year"] == df[c2])
    dose_fcr = df["fcr"].where(in_dose)
    n_dose = dose_fcr.notna().groupby(df["school_id"]).transform("sum")
    return dose_fcr.groupby(df["school_id"]).transform("mean").where(n_dose == 2)


def add_school_measures(df):
    """Dose, weight, cohort, ratio, and controls; school-level ones are constant within school."""
    df["pre_fcr"] = pre_fcr_over(df, "dose_class_1", "dose_class_2")
    df["dose"] = 1 - df["pre_fcr"]
    df["pre_fcr_clean"] = pre_fcr_over(df, "dose_clean_class_1", "dose_clean_class_2")
    df["dose_clean"] = 1 - df["pre_fcr_clean"]

    pre = df["class_year"] < df["first_covered_class"]
    per_grade = (df["enroll_total"].astype("Float64") / df["n_grades"].astype("Float64")).where(pre)
    df["weight"] = per_grade.groupby(df["school_id"]).transform("mean")

    # 9th-grade cohort of a class: grade-9 enrollment three years earlier, from all
    # CCD years (not only classes in the FSA panel), so cohorts exist from 2015 on.
    g9 = duckdb.sql(f"SELECT school_id, class_year + 3 AS class_year, enroll_g09 AS cohort9 "
                    f"FROM read_parquet('{GRADE9.as_posix()}')").df()
    n0 = len(df)
    df = df.merge(g9, on=["school_id", "class_year"], how="left", validate="m:1")
    assert len(df) == n0
    has = df["cohort9"].notna().groupby(df["class_year"]).mean()
    print(f"  9th-grade cohort merged: {n0:,} rows (none added or dropped); share with a cohort by class: "
          + ", ".join(f"{y}: {s:.2f}" for y, s in has.items()))

    total = df["enroll_total"].astype("Float64")
    df["student_teacher_ratio"] = total / df["teachers_fte"].where(df["teachers_fte"] > 0)
    for race in ["white", "black", "hispanic", "asian"]:
        df[f"share_{race}"] = df[f"race_{race}"].astype("Float64") / total.where(total > 0)
    df["share_frl"] = (df["frl_total"].astype("Float64") / total.where(total > 0)).clip(upper=1)
    df["enroll_total_sq"] = total ** 2
    return df


def window_classes(df, window=WINDOW):
    """Classes each treated school's estimation window must contain.

    Event time `window` (default WINDOW, e = -4 ... +1; to e = 0 when only one
    post class exists), limited to classes with a denominator (FSA from 2015;
    CCD grade 12 through the newest CCD year) and to covered classes, skipping a
    partial-rollout class.
    """
    first_denominator = int(df.loc[df["denominator"].notna(), "class_year"].min())
    last_denominator = int(df.loc[df["denominator"].notna(), "class_year"].max())
    school = df.drop_duplicates("school_id").set_index("school_id")
    school = school[school["treated"]]
    out = {}
    lo, hi = window
    for sid, r in school.iterrows():
        first = int(r["first_covered_class"])
        upper = 0 if r["n_post_classes"] == 1 else hi
        last = min(first + upper, last_denominator,
                   int(r["last_covered_class"]) if pd.notna(r["last_covered_class"]) else 9999)
        start = max(first + lo, first_denominator)
        partial = r["partial_rollout_class"]
        out[sid] = [y for y in range(start, last + 1) if not (pd.notna(partial) and y == int(partial))]
    return out


def senior_heavy(df):
    """True for school-years whose lowest grade is 9 or below but whose seniors are
    more than SENIOR_SHARE_MAX of grades 9-12 (e.g. adult high schools that enroll
    mostly 12th graders). Schools that start at grade 10 or 11 are never flagged."""
    lo = df["gslo"].astype("string").str.strip().replace({"PK": "-1", "KG": "0"})
    lo = pd.to_numeric(lo, errors="coerce")
    grades = df[["enroll_g09", "enroll_g10", "enroll_g11", "enroll_g12"]].astype("Float64")
    share = grades["enroll_g12"] / grades.sum(axis=1, min_count=1).where(lambda s: s > 0)
    return ((lo <= 9) & (share > SENIOR_SHARE_MAX)).fillna(False).astype(bool)


def add_flags(df):
    """Sample screens as booleans (school-level screens are constant within school)."""
    by = df.groupby("school_id")
    df["f_in_ccd"] = by["enroll_total"].transform(lambda s: s.notna().any())
    df["f_not_special_ed"] = ~by["school_type_std"].transform(lambda s: (s == "special_education").any())
    # Main screen (DECISIONS 2026-11-02): career/technical schools are full-time high
    # schools with ordinary senior classes, so they stay; alternative schools do not.
    df["f_regular_cte"] = by["school_type_std"].transform(
        lambda s: s.dropna().isin(["regular", "career_technical"]).all() and s.notna().any())
    is_virtual = df["virtual"].fillna("").str.strip().str.lower().isin(VIRTUAL)
    df["f_not_virtual"] = ~is_virtual.groupby(df["school_id"]).transform("any")
    # Deneault drops schools whose 9th-grade cohort is ever 0 or missing; here
    # only 0 drops a school (cohorts exist from the class of 2015 on).
    has9 = df["cohort9"].notna()
    df["f_cohort9_positive"] = ~(has9 & (df["cohort9"] <= 0)).groupby(df["school_id"]).transform("any")
    r = df["student_teacher_ratio"]
    df["f_ratio_ok"] = (~(r < 5).groupby(df["school_id"]).transform("any")) & \
        (r.groupby(df["school_id"]).transform("min").fillna(0) <= 100)
    df["f_dose_ok"] = df["pre_fcr"].notna()
    df["f_dose_clean_ok"] = df["pre_fcr_clean"].notna()

    heavy = senior_heavy(df)
    for sfx, window in WINDOWS.items():   # Deneault's window (no suffix) and the common window
        classes = df["school_id"].map(window_classes(df, window))
        inw = pd.Series([isinstance(c, list) and y in c for c, y in zip(classes, df["class_year"])], index=df.index)
        need = classes.map(lambda c: len(c) if isinstance(c, list) else 0)
        have = (inw & df["fcr"].notna()).groupby(df["school_id"]).transform("sum")
        df["in_window" + sfx] = inw
        df["window_classes_needed" + sfx] = need
        # Data-quality screen (DECISIONS 2026-11-02): window classes whose enrollment cannot
        # describe a graduating class (years outside the window, e.g. a phase-out, do not count).
        df["f_senior_share_ok" + sfx] = ~(heavy & inw).groupby(df["school_id"]).transform("any")
        df["f_balanced" + sfx] = (need > 0) & (have == need)
    return df


def report(df):
    """Schools kept by state under Deneault's screens and the project design's screens."""
    school = df.drop_duplicates("school_id").set_index("school_id")
    school = school[school["treated"] & (school["n_post_classes"] > 0)]
    deneault = ["f_in_ccd", "f_not_special_ed", "f_cohort9_positive", "f_ratio_ok", "f_dose_ok", "f_balanced"]
    design = ["f_in_ccd", "f_regular_cte", "f_not_virtual", "f_senior_share_ok", "f_ratio_ok", "f_dose_ok", "f_balanced"]
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
