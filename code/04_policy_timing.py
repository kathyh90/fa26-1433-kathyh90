"""Derive each state's (or Colorado school's) dose, reference, and post classes.

Inputs (entered by hand from statutes and agency reports; see docs/source-notes.md):
  data/policy/state_mandates.csv    one row per study state
  data/policy/co_grantee_schools.csv  Colorado's Fund My Future grantee high
                                      schools, the only Colorado schools covered
and data/derived/fsa_school_panel.parquet for the classes FSA data cover.

Timing rule (docs/project-design.md): e = 0 is the first covered class. The
reference class (e = -1) is the last class before it that is not a partial-
rollout class; the dose window is the two classes before the reference class,
again skipping partial-rollout classes. Post classes run from e = 0 to the last
covered class or the newest FSA class, whichever is earlier.

Colorado gets one row per grantee school (school_id = NCES ID); every other
state gets one statewide row (school_id missing).

Writes data/derived/policy_timing.parquet.

Usage (from the repository root):
    uv run --locked python code/04_policy_timing.py
"""

import duckdb
import pandas as pd

from config import DERIVED, ROOT

POLICY = ROOT / "data" / "policy"
STATES = POLICY / "state_mandates.csv"
CO_SCHOOLS = POLICY / "co_grantee_schools.csv"
FSA = DERIVED / "fsa_school_panel.parquet"
OUT = DERIVED / "policy_timing.parquet"
COVID = {2020, 2021}
ROLLOUT_2024 = {2024}   # class affected by the delayed 2024-25 FAFSA


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
    return {
        "reference_class": reference,
        "dose_class_1": dose1,
        "dose_class_2": dose2,
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


def main():
    states = pd.read_csv(STATES, dtype=str)
    co = pd.read_csv(CO_SCHOOLS, dtype=str)
    for d in (states, co):
        for c in ("first_covered_class", "partial_rollout_class", "last_covered_class"):
            if c in d:
                d[c] = pd.to_numeric(d[c]).astype("Int64")
    print(f"Read {len(states)} states and {len(co)} Colorado grantee schools")

    con = duckdb.connect()
    fsa_first, fsa_last = con.execute(
        f"SELECT min(class_year), max(class_year) FROM read_parquet('{FSA.as_posix()}')").fetchone()
    prelim = con.execute(f"SELECT max(class_year) FROM read_parquet('{FSA.as_posix()}') "
                         "WHERE kind = 'preliminary'").fetchone()[0]
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
    out.to_parquet(OUT, index=False)
    print(f"Wrote {OUT.name}: {len(out)} rows ({out['school_id'].notna().sum()} Colorado schools)")

    show = out.assign(
        dose=out["dose_class_1"].astype(str) + "-" + out["dose_class_2"].astype(str).str[-2:],
        post=out["post_first"].astype(str) + "-" + out["post_last"].astype(str),
        flags=out.apply(lambda r: ", ".join(f for f, on in [
            ("dose not in FSA", not r["dose_in_fsa"]), ("COVID in dose/ref", r["dose_or_reference_covid"]),
            ("2024 in dose/ref", r["dose_or_reference_2024"]), ("2024 in post", r["post_includes_2024"]),
            ("preliminary in dose/ref", r["dose_or_reference_preliminary"]),
            ("post incl. preliminary", r["post_includes_preliminary"])] if on), axis=1))
    show.loc[show["n_post_classes"] == 0, "post"] = "none yet"
    co_rows = show["school_id"].notna()
    print("\n" + show.loc[~co_rows, ["state", "first_covered_class", "dose", "reference_class", "post",
                                     "flags"]].to_string(index=False))
    print("\nColorado grantee schools:")
    print(show.loc[co_rows].groupby(["first_covered_class", "partial_rollout_class", "dose", "reference_class",
                                     "post", "flags"], dropna=False)["school_id"].count()
          .rename("schools").reset_index().to_string(index=False))


if __name__ == "__main__":
    main()
