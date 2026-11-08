"""האם הגופים מבצעים את "הצורך"? בדיקה שלא דורשת לראות אף עסקה - רק את אחוז המט"ח הרשמי (data.gov, חודשי).

אם מבצעים את הצורך (שומרים אחוז מט"ח) - אחוז המט"ח הרשמי לא זז כשהשוק זז.
אם לא מבצעים - הוא זז כמו תיק שלא נגעו בו ("סחיפה פסיבית": תשואות המדדים × הרכב החשיפה הזרה, מהפאנל d5).
מבחן: ΔFX% בפועל = b × סחיפה פסיבית.  b≈1: לא מבצעים; b≈0: מבצעים במלואו.  (סחיפה אחת כוללת - בלי פירוק לרכיבים)
מצרפי: ממוצע משוקלל לפי נכסים לכל חודש (מנטרל רעש של מסלול בודד). פלט: data/results/official_fx_drift.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d3_rebalancing_history import wls_cluster  # noqa: E402

p = pd.read_csv("data/results/policy_monthly_panel.csv.gz")
p["drift"], p["dFX"] = p.FXp - p.FX, p.FX1 - p.FX
p = p.replace([np.inf, -np.inf], np.nan).dropna(subset=["drift", "dFX", "TOTAL_ASSETS"])
agg = p.groupby("month").apply(lambda g: pd.Series({"dFX": np.average(g.dFX, weights=g.TOTAL_ASSETS),
                                                   "drift": np.average(g.drift, weights=g.TOTAL_ASSETS),
                                                   "assets_bn": g.TOTAL_ASSETS.sum() / 1e3}), include_groups=False)
X = np.column_stack([np.ones(len(agg)), agg.drift])
b = np.linalg.lstsq(X, agg.dFX.values, rcond=None)[0]
e = agg.dFX.values - X @ b
se = np.sqrt(np.diag(e @ e / (len(agg) - 2) * np.linalg.inv(X.T @ X)))
print(f"מצרפי ({len(agg)} חודשים): ΔFX% = {b[1]:.2f} (±{1.96*se[1]:.2f}) × סחיפה {b[0]*100:+.2f}pp לחודש; מתאם {agg.drift.corr(agg.dFX):.2f}")
print(f"  => מקוזז בפועל כ-{1-b[1]:.0%} מהסחיפה (טווח {1-b[1]-1.96*se[1]:.0%} עד {1-b[1]+1.96*se[1]:.0%}); מגמה קבועה {b[0]*100:+.2f}pp לחודש")
rows = [{"רמה": "מצרפי חודשי", "b": b[1], "se": se[1], "n": len(agg), "מקוזז": 1 - b[1]}]
for lab, d in (("מסלול – כל התצפיות", p), ("מסלול – |סחיפה|<5pp", p[p.drift.abs() < 0.05])):
    for wt in (True, False):
        bb, ss = wls_cluster(d.assign(FX1=d.dFX, FX=0.0), ["drift"], wt)
        rows.append({"רמה": f"{lab} ({'נכסים' if wt else 'ללא'})", "b": bb[0], "se": ss[0], "n": len(d), "מקוזז": 1 - bb[0]})
r = pd.DataFrame(rows).round(3)
r.to_csv("data/results/official_fx_drift.csv", index=False)
(agg * [100, 100, 1]).round(2).to_csv("data/results/official_fx_drift_monthly.csv")
print(r.to_string(index=False))
