"""Exploratory: graduates / CCD grade 12 by event time (dose x class, e = -1 omitted),
on the graduate-ratio test sample, to see whether a dose x post beta comes from a
dip in the dose classes (mechanical: dose is built from completions / grade 12)
or a post-mandate shift. Also prints NJ's ratio distribution.
Usage: uv run --locked python code/explore/graduate_ratio_event_time.py"""
import importlib.util
import sys

from pathlib import Path

import pyfixest as pf

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # code/, for config
from config import ROOT, STUDY_STATES  # noqa: E402

spec = importlib.util.spec_from_file_location("rf", ROOT / "code" / "08_reduced_form.py")
rf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rf)

TRIM = '--trim' in sys.argv
df = rf.prepare(rf.merge_outcomes())
df["grad_ratio"] = df["outcome_graduates"].astype(float) / df["enroll_g12"].astype(float).where(df["enroll_g12"] > 0)
for st in [s for s in STUDY_STATES if s not in rf.fs.EXCLUDE_STATES]:
    base, _, controls, _ = rf.state_sample(df, st, "main")
    d = rf.outcome_sample(base, "grad_ratio") if len(base) else None
    if d is None:
        continue
    if TRIM:   # drop schools with any ratio outside 0.5-1.5 (graduate and grade-12 counts disagree)
        d = d[d["grad_ratio"].between(0.5, 1.5).groupby(d["school_id"]).transform("all")].copy()
    e = (d["class_year"] - d["reference_class"] - 1).astype(int)   # reference class = e -1
    terms = []
    for k in sorted(set(e) - {-1}):
        d[f"e{k + 20}"] = d["dose"] * (e == k)
        terms.append(f"e{k + 20}")
    fit = pf.feols(f"grad_ratio ~ {' + '.join(terms)} + {' + '.join(controls)} | school_id + class_year",
                   data=d, weights="weight", vcov={"CRV1": "school_id"})
    out = "  ".join(f"{int(t[1:]) - 20}:{fit.coef()[t]:+.3f}{'*' if abs(fit.tstat()[t]) > 1.96 else ''}" for t in terms)
    print(f"{st} ({d.school_id.nunique()} schools): {out}")
