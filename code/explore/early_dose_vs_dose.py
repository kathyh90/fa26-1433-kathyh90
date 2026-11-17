"""Exploratory: how well does a dose from the two newest clean classes before the
estimation window (e < -4; skipping 2020, 2021, 2024) track Deneault's dose
(e = -3, -2)? For each state's main first-stage schools: schools with both,
correlation, slope of dose on early dose (the IV first stage, unweighted), and
the share of schools in the same dose quartile under both.
Usage: uv run --locked python code/explore/early_dose_vs_dose.py"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # code/, for config
from config import ROOT, STUDY_STATES  # noqa: E402

spec = importlib.util.spec_from_file_location("rf", ROOT / "code" / "08_reduced_form.py")
rf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rf)
SKIP = {2020, 2021, 2024}

df = rf.prepare(rf.merge_outcomes())
rows = []
for st in [s for s in STUDY_STATES if s not in rf.fs.EXCLUDE_STATES]:
    base = rf.state_sample(df, st, "main")[0]
    if base.empty or not base["post"].any():   # no post-mandate classes yet (CT, PA)
        continue
    first = int(base["first_covered_class"].iloc[0])
    early = [y for y in range(first - 5, 2014, -1) if y not in SKIP][:2]   # newest clean classes before e = -4
    if len(early) < 2:
        rows.append({"state": st, "early_classes": "none (FSA starts 2015)"})
        continue
    d = df[df["school_id"].isin(base["school_id"]) & df["class_year"].isin(early)]
    n = d.groupby("school_id")["fcr"].agg(["mean", "count"])
    early_dose = (1 - n["mean"]).where(n["count"] == 2).dropna()
    s = base.drop_duplicates("school_id").set_index("school_id")["dose"].reindex(early_dose.index)
    q = lambda x: pd.qcut(x, 4, labels=False)
    rows.append({"state": st, "early_classes": f"{early[1]}, {early[0]}", "dose_classes": f"{first - 3}, {first - 2}",
                 "schools": len(base["school_id"].unique()), "with_early_dose": len(s),
                 "corr": round(s.corr(early_dose), 3), "slope": round(np.polyfit(early_dose, s, 1)[0], 3),
                 "same_quartile": round((q(s) == q(early_dose)).mean(), 3),
                 "mean_dose": round(s.mean(), 3), "mean_early_dose": round(early_dose.mean(), 3)})
print(pd.DataFrame(rows).to_string(index=False))
