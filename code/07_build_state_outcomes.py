"""Build the school x class college-going outcomes from the state data files.

Outcome for every state: `pct_enrolled`, the college enrollment rate as the
state publishes it; `window` records which one (definitions by state in
docs/source-notes.md):
  LA  la_fall_oct31  enrolled by Oct 31 of the fall after graduation
  IL  il_12m_sep30   first enrollment by Sep 30 of the year after graduation
                     (ISBE's 12-month rate; the 16-month rate is kept too)
  AL  al_fall_public_instate  enrolled the fall after graduation at an Alabama
                     PUBLIC college (ACHE; no private or out-of-state colleges)
  MD  md_within_1yr  enrolled (full- or part-time, any degree status) within one
                     year of graduation (MLDS; MHEC + NSC); the immediate
                     (full-time, degree-seeking, fall) and within-two-years rates are kept
  TX  tx_fall_texas  enrolled the fall after graduation at a Texas public or
                     private college (THECB; no out-of-state colleges); 'not
                     trackable' graduates count as not enrolled (the share of
                     trackable graduates is kept as pct_enrolled_trackable)
  CA  ca_12m_any     enrolled at any U.S. college within 12 months of completing
                     high school (CDE, NSC); denominator = high school
                     completers (graduates plus non-graduate completers)
  IN  in_year_after  enrolled at any college that participates in NSC in the
                     year after graduation (CHE); Indiana public enrollment kept
  NH  nh_year_after  % of graduates enrolling at a 2- or 4-year college within the
                     year after graduation (NH DOE iExplore, a published rate;
                     graduates = completers from iPlatform, enrolled estimated)
  NE  ne_year_after  enrolled at any NSC college between June 1 after graduation
                     and May 31 of the next year (CCPE); denominator = on-time
                     public graduates. NDE's rate (enrolled on October 15 of the
                     year after the first fall) is kept as pct_enrolled_nde_oct15
  OK  ok_year_after_instate  first-time enrollment at an Oklahoma public or
                     private college the fall after graduation or later in that
                     academic year (OSRHE; no out-of-state colleges); the fall-only
                     rate is kept, and out-of-state enrollment from class 2023
  NY  ny_16m_any     enrolled at any college (New York public or private, or out
                     of state) within 16 months of graduation (NYSED Report Card,
                     NSC-based); denominator = graduates of the calendar year
  NJ  nj_fall        enrolled at any college (NSC) in the fall after graduation;
                     denominator = graduates September-August; the published
                     range's lower bound (NSC-matched share); the 16-month rate
                     is kept (pct_enrolled_16m); rates only, no counts
Both are shares of all of the school's graduates that year. Breakdowns are
kept with names that say their base, since states differ:
  pct_of_enrolled_*  shares of enrollees (LA: 2-year, 4-year, in state)
  pct_of_grads_*     shares of all graduates (IL: public, private, 4-year,
                     2-year, trade/vocational; 12-month window. AL: 2-year,
                     4-year, both Alabama public)

Louisiana also gets Deneault's (2023) outcome for the replication:
  penroll = (% enrolled 1st fall / 100) x (cohort graduation rate / 100)
with bounded values coded as she codes them (state_files.midpoint: '>99' ->
99.5, '<1' -> 0.5, '>95' -> 97.5, '<5' -> 2.5). Published rate columns keep the
bound itself, with its direction in `<column>_bound`.

Steps per state (row counts printed before and after each):
  1. read the state files (state_files.py)
  2. drop duplicate school x class rows, keeping the most graduates (Deneault's rule)
  3. link to CCD by the state's school code (state_files.link)
  4. LA: add the graduation rate, merged by school_id and class (by the state
     code where a row did not link)
  5. set published percents above 100 to missing (publisher errors; printed)

Writes data/derived/state_outcomes.parquet (key: state, class_year, code).
States are added after their content review.

Usage (from the repository root):
    uv run --locked python code/07_build_state_outcomes.py
"""

import pandas as pd

from config import DERIVED
from state_files import (NJ_CCD_KEY, nj_postsecondary, ny_postsecondary, OK_CCD_KEY, ok_college_going, ne_ccpe_continuation, ne_college_going, nh_code, nh_postsecondary, in_college_going, ca_college_going, tx_thecb_enrollment, AL_CCD_KEY, LA_ALIASES, MD_ALIASES, MD_CCD_KEY, al_ache_enrollment, md_college_enrollment, ccd_codes, il_code, il_college_enrollment,
                         la_college_enrollment, la_grad_rates, link, midpoint)

OUT = DERIVED / "state_outcomes.parquet"
KEY = ["state", "class_year", "code"]


def dedupe(d, label):
    """Keep one row per class x code: the one with the most graduates (or the
    first if there is no graduate count). Prints the rows dropped."""
    n0 = len(d)
    if "graduates" in d:
        d = d.sort_values("graduates", ascending=False)
    d = d.drop_duplicates(["class_year", "code"])
    print(f"  {label}: {n0:,} rows -> {len(d):,} after dropping duplicate class x code rows "
          f"({n0 - len(d)} dropped; duplicates are repeated listings of one school)")
    return d


def linked(state, d, ccd, label, **options):
    """Dedupe, link to CCD, and print how the rows linked."""
    d = link(state, dedupe(d, label), ccd, **options)
    print(f"  linked to CCD: {(d['link'] == 'same_year').sum():,} same year, "
          f"{(d['link'] == 'any_year').sum():,} by code in another year, "
          f"{(d['link'] == '').sum():,} not linked (kept, school_id missing)")
    return d


def rename_with_bounds(d, names):
    """Rename value columns and their *_bound columns together."""
    return d.rename(columns={**names, **{f"{a}_bound": f"{b}_bound" for a, b in names.items()}})


def louisiana(ccd):
    """Louisiana, classes 2012-2024 (penroll for 2014-2024, where both the
    enrollment and the graduation-rate files exist)."""
    enroll = la_college_enrollment()
    print(f"  LA college enrollment: {len(enroll):,} school rows read, classes "
          f"{enroll['class_year'].min()}-{enroll['class_year'].max()}")
    enroll = linked("LA", enroll, ccd, "LA college enrollment", aliases=LA_ALIASES)

    grad = la_grad_rates()
    print(f"  LA graduation rates: {len(grad):,} school rows read, classes "
          f"{grad['class_year'].min()}-{grad['class_year'].max()}")
    grad = linked("LA", grad, ccd, "LA graduation rates", aliases=LA_ALIASES)
    # Merge on school_id where both sides linked; otherwise on the state code.
    for d in (enroll, grad):
        d["merge_key"] = d["school_id"].fillna("LA:" + d["code"])
    grad = grad.drop_duplicates(["class_year", "merge_key"])
    n0 = len(enroll)
    m = enroll.merge(grad[["class_year", "merge_key", "grad_rate", "grad_rate_bound"]],
                     on=["class_year", "merge_key"], how="left", validate="m:1")
    print(f"  merge with graduation rates: {n0:,} rows -> {len(m):,}; "
          f"{m['grad_rate'].notna().sum():,} have a graduation rate "
          f"(none for classes 2012-2013, which predate the graduation files used)")

    m["enrolled"] = m["graduates"] * m["pct_enrolled"] / 100
    m["penroll"] = (midpoint(m["pct_enrolled"], m["pct_enrolled_bound"]) / 100
                    * midpoint(m["grad_rate"], m["grad_rate_bound"]) / 100)
    m = rename_with_bounds(m, {"pct_2yr": "pct_of_enrolled_2yr", "pct_4yr": "pct_of_enrolled_4yr",
                               "pct_instate": "pct_of_enrolled_instate"})
    return m.assign(state="LA", window="la_fall_oct31").drop(columns="merge_key")


def illinois(ccd):
    """Illinois, classes 2013-2024 (report cards 2015-2026): the 12-month rate is
    the outcome; rates only, so graduates and enrolled are missing."""
    d = il_college_enrollment()
    print(f"  IL report card postsecondary: {len(d):,} school rows read, classes "
          f"{d['class_year'].min()}-{d['class_year'].max()}")
    d = linked("IL", d, ccd, "IL report card", normalize=il_code)
    d = rename_with_bounds(d, {
        "pct_enrolled_12m": "pct_enrolled",
        "pct_12m_public": "pct_of_grads_public", "pct_12m_private": "pct_of_grads_private",
        "pct_12m_4yr": "pct_of_grads_4yr", "pct_12m_2yr": "pct_of_grads_2yr",
        "pct_12m_trade": "pct_of_grads_trade"})
    d["source_file"] = "report card " + d.pop("report_year").astype(str)
    keep = [c for c in d.columns if not c.startswith(("pct_16m_", "grad_rate_4yr", "cohort_graduates"))]
    return d[keep].assign(state="IL", window="il_12m_sep30")


def drop_impossible_rates(d):
    """Set published percents above 100 to missing (publisher errors), printing each."""
    for c in [c for c in d.columns if c.startswith("pct_") and not c.endswith("_bound")]:
        bad = d[c] > 100
        for _, r in d[bad].iterrows():
            print(f"  {r['state']} class {r['class_year']} {r['name']}: {c} = {r[c]} > 100 set to missing")
        d.loc[bad, c] = float("nan")
    return d


def alabama(ccd):
    """Alabama, classes 2012-2024: ACHE counts of graduates and of those enrolled
    at Alabama public 2- and 4-year colleges the fall after graduation."""
    d = al_ache_enrollment()
    print(f"  AL ACHE high school reports: {len(d):,} school rows read, classes "
          f"{d['class_year'].min()}-{d['class_year'].max()}")
    d = linked("AL", d, ccd, "AL ACHE reports", ccd_key=AL_CCD_KEY)
    d["pct_of_grads_2yr"] = 100 * d["enrolled_2yr"] / d["graduates"]
    d["pct_of_grads_4yr"] = 100 * d["enrolled_4yr"] / d["graduates"]
    for c in ("pct_enrolled", "pct_of_grads_2yr", "pct_of_grads_4yr"):
        d[f"{c}_bound"] = ""          # computed from counts, never a bound
    return d.assign(state="AL", window="al_fall_public_instate")


def maryland(ccd):
    """Maryland, classes 2008-2024: MLDS counts of graduates and enrollees. The
    outcome is within one year; the rate is enrolled / graduates from the counts
    (MLDS's own % is rounded to whole points)."""
    d = md_college_enrollment()
    print(f"  MD MLDS download: {len(d):,} school rows read, classes "
          f"{d['class_year'].min()}-{d['class_year'].max()}")
    d = linked("MD", d, ccd, "MD MLDS", ccd_key=MD_CCD_KEY, aliases=MD_ALIASES)
    for kind in ("1yr", "immediate", "2yr"):
        d[f"pct_{kind}"] = 100 * d[f"enrolled_{kind}"] / d["graduates"]
    # "within_2yr" (time), not "2yr", which elsewhere means 2-year colleges.
    d = d.rename(columns={"enrolled_1yr": "enrolled", "pct_1yr": "pct_enrolled",
                          "pct_immediate": "pct_enrolled_immediate",
                          "enrolled_2yr": "enrolled_within_2yr", "pct_2yr": "pct_enrolled_within_2yr"})
    for c in ("pct_enrolled", "pct_enrolled_immediate", "pct_enrolled_within_2yr"):
        d[f"{c}_bound"] = ""
    return d.drop(columns="district").assign(state="MD", window="md_within_1yr")


def texas(ccd):
    """Texas, classes 2019-2024: THECB counts for high schools with more than 25
    graduates. Denominator: all graduates (decision 2026-11-01); the share of
    trackable graduates (excluding non-standard IDs) is the robustness version."""
    d = tx_thecb_enrollment()
    print(f"  TX THECB: {len(d):,} school rows read, classes {d['class_year'].min()}-{d['class_year'].max()}")
    d = linked("TX", d, ccd, "TX THECB")
    d["pct_enrolled"] = 100 * d["enrolled"] / d["graduates"]
    d["pct_enrolled_trackable"] = 100 * d["enrolled"] / (d["graduates"] - d["not_trackable"])
    for c in ("pct_enrolled", "pct_enrolled_trackable"):
        d[f"{c}_bound"] = ""
    return d.assign(state="TX", window="tx_fall_texas")


def california(ccd):
    """California, classes 2015-2023: CDE counts of high school completers and of
    those enrolled at any U.S. college within 12 months, with in-state /
    out-of-state and UC / CSU / community college / private splits."""
    d = ca_college_going()
    print(f"  CA CDE college-going: {len(d):,} school rows read, classes "
          f"{d['class_year'].min()}-{d['class_year'].max()}")
    d = linked("CA", d, ccd, "CA CDE")
    d["pct_enrolled"] = 100 * d["enrolled"] / d["graduates"]
    d["pct_enrolled_bound"] = ""
    return d.assign(state="CA", window="ca_12m_any")


def indiana(ccd):
    """Indiana, classes 2008-2024: CHE counts of high school graduates and of those
    enrolled at any NSC college (and at Indiana public colleges). CHE also lists
    private high schools; those do not link to the public CCD panel."""
    d = in_college_going()
    print(f"  IN CHE college-going: {len(d):,} school rows read, classes "
          f"{d['class_year'].min()}-{d['class_year'].max()}")
    d = linked("IN", d, ccd, "IN CHE")
    d["pct_enrolled"] = 100 * d["enrolled"] / d["graduates"]
    d["pct_enrolled_bound"] = ""
    return d.assign(state="IN", window="in_year_after")


def new_hampshire(ccd):
    """New Hampshire, classes 2016-2025: iExplore's published rate by high school;
    graduates are the iPlatform completers of the same class, and enrolled is
    rate x graduates (an estimate: NH publishes no enrollee counts)."""
    d = nh_postsecondary()
    print(f"  NH iExplore: {len(d):,} high school rows read, classes {d['class_year'].min()}-{d['class_year'].max()}")
    d = linked("NH", d, ccd, "NH iExplore", normalize=nh_code)
    d["enrolled"] = d["graduates"] * d["pct_enrolled"] / 100
    return d.assign(state="NH", window="nh_year_after")


def nebraska(ccd):
    """Nebraska, classes 2008-2025 (one post-period class, 2025): CCPE counts of
    on-time graduates and of those enrolled within the year after graduation.
    NDE's published rate (classes 2016-2023, a later enrollment date) is merged
    on by class and school code as pct_enrolled_nde_oct15."""
    d = ne_ccpe_continuation()
    print(f"  NE CCPE continuation: {len(d):,} school rows read, classes {d['class_year'].min()}-{d['class_year'].max()} "
          f"({(d['ccpe_match'] == '').sum()} rows without a CCD code: schools closed or merged before CCD 2014-15, classes 2008-2014)")
    d = linked("NE", d, ccd, "NE CCPE")
    nde = dedupe(ne_college_going(), "NE NEP")[["class_year", "code", "pct_enrolled"]]
    n0 = len(d)
    d = d.merge(nde.rename(columns={"pct_enrolled": "pct_enrolled_nde_oct15"}), on=["class_year", "code"],
                how="left", validate="1:1")
    print(f"  NE NEP rate merged: {n0:,} rows -> {len(d):,}; {d['pct_enrolled_nde_oct15'].notna().sum():,} with an NDE rate "
          f"(NDE has {len(nde):,} school rows; NDE covers classes 2016-2023 only)")
    return d.assign(state="NE", window="ne_year_after")


def oklahoma(ccd):
    """Oklahoma, classes 2013-2024 (no post-period class yet: the first covered
    class is 2025): OSRHE counts of public high school graduates and of those
    entering Oklahoma colleges in the following academic year; schools matched
    to CCD by county + name (state_files.ok_college_going)."""
    d = ok_college_going()
    print(f"  OK OSRHE college-going: {len(d):,} school rows read, classes {d['class_year'].min()}-{d['class_year'].max()} "
          f"({(d['name_match'] == '').sum()} rows not matched to a CCD school by name)")
    d = linked("OK", d, ccd, "OK OSRHE", ccd_key=OK_CCD_KEY)
    d["pct_of_grads_outstate"] = 100 * d["enrolled_outstate"] / d["graduates"]
    for c in ("pct_enrolled_fall", "pct_of_grads_outstate"):
        d[f"{c}_bound"] = ""          # computed from counts, never a bound
    return d.assign(state="OK", window="ok_year_after_instate")


def new_york(ccd):
    """New York, classes 2021-2024 (no post-period class yet: the first covered
    class is 2025): NYSED counts of graduates and of those enrolled at any college
    within 16 months, with New York public / private / out-of-state and 2- / 4-year
    counts. Read from the Report Card Access databases (about a minute)."""
    d = ny_postsecondary()
    print(f"  NY Report Card postsecondary: {len(d):,} school rows read, classes {d['class_year'].min()}-{d['class_year'].max()}")
    d = linked("NY", d, ccd, "NY Report Card")
    return d.assign(state="NY", window="ny_16m_any")


def new_jersey(ccd):
    """New Jersey, fall rate classes 2019-2024, 16-month rate 2018-2023 (no
    post-period class yet: class 2025 is expected in the next NJDOE trend file):
    NJDOE's published rates by school (no graduate or enrollee counts)."""
    d = nj_postsecondary()
    print(f"  NJ postsecondary trends: {len(d):,} school rows read, classes {d['class_year'].min()}-{d['class_year'].max()}")
    d = linked("NJ", d, ccd, "NJ postsecondary trends", ccd_key=NJ_CCD_KEY)
    return d.assign(state="NJ", window="nj_fall")


def main():
    ccd = ccd_codes()
    parts = []
    for name, build in [("Louisiana", louisiana), ("Illinois", illinois), ("Alabama", alabama),
                        ("Maryland", maryland), ("Texas", texas), ("California", california),
                        ("Indiana", indiana), ("New Hampshire", new_hampshire),
                        ("Nebraska", nebraska), ("Oklahoma", oklahoma),
                        ("New York", new_york), ("New Jersey", new_jersey)]:
        print(f"{name}:")
        parts.append(build(ccd))
    out = drop_impossible_rates(pd.concat(parts, ignore_index=True))
    if "file" in out:
        out["source_file"] = out["source_file"].fillna(out.pop("file"))
    first = ["state", "class_year", "code", "name", "school_id", "link", "window", "graduates",
             "pct_enrolled", "pct_enrolled_bound", "enrolled"]
    out = out[first + [c for c in out.columns if c not in first and c != "source_file"] + ["source_file"]]
    assert not out.duplicated(KEY).any()
    out.to_parquet(OUT, index=False)
    print(f"Wrote {OUT.name}: {len(out):,} rows")
    print(out.groupby(["state", "class_year"]).agg(
        schools=("code", "size"), linked=("school_id", "count"),
        mean_pct_enrolled=("pct_enrolled", "mean"), penroll_mean=("penroll", "mean")).round(3).to_string())


if __name__ == "__main__":
    main()
