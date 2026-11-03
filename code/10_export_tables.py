"""Formatted results tables (HTML) for the paper draft, from the step 6, 8, and 9 CSVs.

Tables 1A and 1B: summary statistics of the first-stage and reduced-form samples by state (step 9).
Table 2: first stage by state (step 6).
Table 3: reduced form by state, with the first stage on the same sample (step 8).
Table 4: graduate-denominator specification vs. the baseline, same schools (step 8).

Coefficients show the standard error (clustered by school) below them in
parentheses; * p<0.10, ** p<0.05, *** p<0.01. The HTML uploads to Google Drive
as a Google Doc (Drive converts headings and tables to native formatting).

Writes output/tables/results_tables.html.

Usage (from the repository root):
    uv run --locked python code/10_export_tables.py
"""

import html

import pandas as pd

from config import OUTPUT, STUDY_STATES

TABLES = OUTPUT / "tables"
OUT = TABLES / "results_tables.html"
STATE_NAMES = {"LA": "Louisiana", "IL": "Illinois", "AL": "Alabama", "MD": "Maryland", "TX": "Texas",
               "CO": "Colorado", "CA": "California", "IN": "Indiana", "NH": "New Hampshire", "NE": "Nebraska",
               "OK": "Oklahoma", "NY": "New York", "NJ": "New Jersey", "CT": "Connecticut", "PA": "Pennsylvania"}
# Table 1 rows: variable -> (label, show SD). Indicators show the mean only.
SUMMARY_ROWS = {
    "enroll_total": ("Total enrollment", True), "enroll_g12": ("Grade 12 enrollment", True),
    "share_white": ("Share White", True), "share_black": ("Share Black", True),
    "share_hispanic": ("Share Hispanic", True), "share_asian": ("Share Asian", True),
    "share_frl": ("Share free/reduced-price lunch", True), "charter": ("Charter", False),
    "city": ("City", False), "suburb": ("Suburb", False), "town": ("Town", False), "rural": ("Rural", False),
    "pre_fcr": ("FAFSA completion rate (dose classes)", True), "dose": ("Dose (1 − completion)", True),
    "enroll": ("College enrollment rate", True),
}
# Outcome definitions (codebook, state_outcomes `window`), for the Table 3 notes.
WINDOWS = {
    "la_fall_oct31": "enrolled by Oct. 31 of the fall after graduation",
    "il_12m_sep30": "first enrolled by Sep. 30 of the year after graduation",
    "al_fall_public_instate": "enrolled the fall after graduation at an Alabama public college",
    "md_within_1yr": "enrolled within one year of graduation (MHEC + NSC)",
    "tx_fall_texas": "enrolled the fall after graduation at a Texas public or private college",
    "ca_12m_any": "enrolled at any U.S. college within 12 months",
    "in_year_after": "enrolled at any NSC college in the year after graduation",
    "nh_year_after": "enrolled at a 2- or 4-year college within the year after graduation",
    "ne_year_after": "on-time graduates enrolled at any NSC college June 1-May 31 after graduation",
}
STYLE = ("<style>body{font-family:Arial;font-size:10pt} table{border-collapse:collapse;font-size:8pt} "
         "td,th{border:1px solid #999;padding:2px 5px;text-align:center} td:first-child{text-align:left}"
         " p.note{font-size:8pt}</style>")


def stars(p):
    """Significance stars for a p-value."""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def coef(beta, se, p):
    """Coefficient with stars, and the standard error in parentheses on the next line."""
    return f"{beta:.3f}{stars(p)}<br>({se:.3f})"


def num(x, digits=2):
    """Number for a cell: thousands separator for counts, blank if missing."""
    if pd.isna(x):
        return ""
    return f"{x:,.0f}" if abs(x) >= 100 else f"{x:.{digits}f}"


def count(x):
    """A count (schools) as a whole number with a thousands separator."""
    return f"{int(x):,}"


def html_table(header, rows):
    """An HTML table from a header list and a list of row lists (cells may hold <br>)."""
    head = "".join(f"<th>{html.escape(h)}</th>" for h in header)
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tr>{head}</tr>{body}</table>"


def summary_table(file):
    """Table 1A/1B from a step-9 CSV: one column per state plus All; SD in
    parentheses under the mean."""
    t = pd.read_csv(TABLES / file)
    states = [s for s in STUDY_STATES if s in t.columns]
    get = lambda v, stat: t[(t["variable"] == v) & (t["stat"].fillna("") == stat)].iloc[0]
    rows = []
    for v, (label, sd) in SUMMARY_ROWS.items():
        m, s = get(v, "mean"), get(v, "sd")
        rows.append([label] + [num(m[c]) + (f"<br>({num(s[c])})" if sd and pd.notna(m[c]) else "")
                               for c in states + ["All"]])
    n = get("n_schools", "")
    rows.append(["Schools"] + [count(n[c]) for c in states + ["All"]])
    return html_table([""] + states + ["All"], rows)


def first_stage_table():
    """Table 2: main and no-FRL first stage by state, with sample descriptors."""
    fs = pd.read_csv(TABLES / "first_stage_by_state.csv")
    rows = []
    for st in [s for s in STUDY_STATES if s in set(fs["state"])]:
        d = fs[fs["state"] == st].set_index("spec")
        m = d.loc["main"]
        rows.append([STATE_NAMES[st], coef(m.beta, m.se, m.p), coef(*d.loc["no_frl", ["beta", "se", "p"]]),
                     num(m.mean_fcr_pre), num(m.mean_dose), count(m.n_schools), m.classes])
        if "deneault" in d.index:
            r = d.loc["deneault"]
            rows.append([f"{STATE_NAMES[st]} (Deneault screens)", "", coef(r.beta, r.se, r.p),
                         num(r.mean_fcr_pre), num(r.mean_dose), count(r.n_schools), r.classes])
    return html_table(["State", "Main", "No FRL", "Pre-mandate completion", "Mean dose", "Schools", "Classes"], rows)


def reduced_form_table():
    """Table 3: reduced form (main, no-FRL), first stage on the same sample, ratio,
    and schools before and after requiring the outcome."""
    rf = pd.read_csv(TABLES / "reduced_form_by_state.csv")
    rows = []
    for st in [s for s in STUDY_STATES if s in set(rf["state"])]:
        d = rf[rf["state"] == st].set_index("spec")
        for spec in ["main", "deneault"]:
            if spec not in d.index:
                continue
            r = d.loc[spec]
            label = STATE_NAMES[st] if spec == "main" else \
                f"{STATE_NAMES[st]} (Deneault screens{', penroll' if r.outcome == 'penroll' else ''})"
            # Deneault's spec has no FRL control, so it sits in the no-FRL column (as in Table 2)
            main_cell, no_frl = ((coef(r.beta, r.se, r.p), coef(*d.loc["no_frl", ["beta", "se", "p"]]))
                                 if spec == "main" else ("", coef(r.beta, r.se, r.p)))
            rows.append([label, main_cell, no_frl,coef(r.fs_beta, r.fs_se, 1.0),  # no p in the CSV: no stars
                         f"{r.rf_fs_ratio:.2f}", num(r.mean_y_pre),
                         f"{r.schools_first_stage_sample:,} → {r.n_schools:,}", r.classes])
    table = html_table(["State", "Reduced form: main", "Reduced form: no FRL", "First stage, same sample",
                        "RF / FS", "Pre-mandate enrollment", "Schools (FS → RF)", "Classes"], rows)
    used = [w for w in WINDOWS if w in set(rf["window"])]
    by_state = {w: rf.loc[rf["window"] == w, "state"].iloc[0] for w in used}
    defs = "; ".join(f"{STATE_NAMES[by_state[w]]}: {WINDOWS[w]}" for w in used)
    return table, defs


def grad_table():
    """Table 4: first stage, reduced form, and ratio with the CCD grade-12 (baseline)
    and graduate denominators, each on its reduced-form sample (same schools)."""
    rf = pd.read_csv(TABLES / "reduced_form_by_state.csv")
    rows = []
    for st in [s for s in STUDY_STATES if s in set(rf.loc[rf["spec"] == "grad_denom", "state"])]:
        b, g = (rf[(rf["state"] == st) & (rf["spec"] == k)].iloc[0] for k in ["main", "grad_denom"])
        rows.append([STATE_NAMES[st], coef(b.fs_beta, b.fs_se, 1.0), coef(g.fs_beta, g.fs_se, 1.0),
                     f"{b.mean_dose:.2f} / {g.mean_dose:.2f}", coef(b.beta, b.se, b.p), coef(g.beta, g.se, g.p),
                     f"{b.rf_fs_ratio:.2f}", f"{g.rf_fs_ratio:.2f}", count(g.n_schools), g.classes])
    return html_table(["State", "First stage: grade 12", "First stage: graduates", "Mean dose (grade 12 / graduates)",
                       "Reduced form: grade 12", "Reduced form: graduates", "RF / FS: grade 12", "RF / FS: graduates",
                       "Schools", "Classes"], rows)


def main():
    rf_table, defs = reduced_form_table()
    rf = pd.read_csv(TABLES / "reduced_form_by_state.csv").query("spec == 'main'")
    drops = "; ".join(f"{STATE_NAMES[r.state]} {r.dropped_no_outcome} with no outcome, "
                      f"{r.dropped_partial_outcome} missing some classes"
                      for r in rf.itertuples() if r.dropped_no_outcome + r.dropped_partial_outcome)
    parts = [
        "<h1>Results tables</h1>",
        "<h2>Table 1A. Characteristics of sample high schools, by state: first-stage sample</h2>",
        summary_table("summary_stats_fs_by_state.csv"),
        "<h2>Table 1B. Characteristics of sample high schools, by state: reduced-form sample</h2>",
        summary_table("summary_stats_rf_by_state.csv"),
        "<p class='note'>Notes: Public high schools in each state's main-specification sample: Table 1A the "
        "first-stage sample (Table 2), Table 1B the reduced-form sample (Table 3: window classes with outcome data, "
        "schools with the outcome in all of them). Each school is averaged over its pre-mandate sample classes; "
        "cells are unweighted means across schools, standard deviations in parentheses (indicators show means only). "
        "Shares describe the average school, not the state's students. In Table 1A the college enrollment rate is "
        "averaged over the schools and classes that have it. Locale from the NCES locale code. Charter is blank where "
        "CCD reports no charter status. Sources: CCD, FSA FAFSA completion files, state college-going reports.</p>",
        "<h2>Table 2. First stage: FAFSA completion on dose × post, by state</h2>", first_stage_table(),
        "<p class='note'>Notes: Each cell is the coefficient on dose × post from a separate regression of the FAFSA "
        "completion rate (completions ÷ CCD grade-12 enrollment, capped at 1) with school and class fixed effects, "
        "weighted by pre-mandate students per grade; standard errors clustered by school in parentheses. Controls: "
        "race shares, enrollment and its square, and (main) the free/reduced-price lunch share; Illinois's main "
        "specification omits it because CCD has no FRL data for its first covered class. Dose = 1 − mean completion "
        "in the two dose classes. Sample: regular and career/technical public high schools, never virtual, "
        "with no window class in which seniors exceed 75% of grades 9-12 (main and no FRL); the Deneault-screens rows drop only special-education schools, keeping alternative "
        "and virtual schools, with the no-FRL controls. Colorado is excluded. Preliminary: grade-12 enrollment denominator. "
        "* p&lt;0.10, ** p&lt;0.05, *** p&lt;0.01.</p>",
        "<h2>Table 3. Reduced form: college enrollment on dose × post, by state</h2>", rf_table,
        "<p class='note'>Notes: As Table 2, with the state's college enrollment rate (share of graduates) as the "
        "outcome, on the first-stage sample limited to window classes with outcome data and schools with the "
        "outcome in every one of them. The first stage is re-estimated on the same sample (main specification; standard "
        "error only, no stars), and RF / FS is the ratio of the two coefficients (no standard error). Oklahoma, New York, and New Jersey have "
        "no post-mandate outcome yet; Connecticut and Pennsylvania outcomes are not built; Colorado is excluded. "
        f"Outcomes differ by state, so coefficients compare within a state, not across states: {defs}. "
        f"Schools dropped by the outcome requirement (main): {drops}. "
        "* p&lt;0.10, ** p&lt;0.05, *** p&lt;0.01.</p>",
        "<h2>Table 4. Graduate denominator: FAFSA completion per graduate instead of per grade-12 student</h2>",
        grad_table(),
        "<p class='note'>Notes: Main specification of Tables 2 and 3 on each state's reduced-form sample, with FAFSA "
        "completion (and so dose) measured two ways: completions ÷ CCD grade-12 enrollment (fall of senior year; "
        "baseline) and completions ÷ the state's graduate count of the class, the same count as the college "
        "enrollment rate's denominator (capped at 1). Both columns use the same schools and classes. The reduced-form "
        "outcome is the same; its coefficient changes only through dose. Illinois publishes no school graduate "
        "counts and New York and Oklahoma have none for the post-mandate classes; New Jersey's graduate first stage "
        "(4-year cohort graduates) is in first_stage_grad_by_state.csv until its post-mandate outcome is released. Graduate counts are consistent within "
        "each state over the window (graduates ÷ grade-12 enrollment: output/tables/graduate_denominator_check.csv). "
        "First-stage cells show standard errors only. * p&lt;0.10, ** p&lt;0.05, *** p&lt;0.01.</p>",
    ]
    OUT.write_text(f"<html><head><meta charset='utf-8'>{STYLE}</head><body>{''.join(parts)}</body></html>",
                   encoding="utf-8")
    print(f"Wrote {OUT.relative_to(OUTPUT.parent)}")


if __name__ == "__main__":
    main()
