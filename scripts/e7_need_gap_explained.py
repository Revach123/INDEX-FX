"""למה הצורך (שמירת אחוז מט"ח קבוע) כמעט לא מבוצע? שלושה הסברים, נבדקים על החשיפה הרשמית החודשית (פאנל d5).
1. טווח המדיניות: כמה מהנכסים בתוך [מינ', מקס'] וכמה נדחפים החוצה ע"י תנועת השוק; "צורך לפי המדיניות" = רק החלק שחצה את הגבול.
2. פיגור: ΔFX מצרפי על סחיפה בחודש ובשלושת החודשים הקודמים.
3. מגמה: שינוי ממוצע באחוז המט"ח לפי שנה, מול הסחיפה הממוצעת.
פלט: data/results/need_gap_explained.json"""
import json

import numpy as np
import pandas as pd

p = pd.read_csv("data/results/policy_monthly_panel.csv.gz")
p["drift"], p["dFX"] = p.FXp - p.FX, p.FX1 - p.FX
p = p.replace([np.inf, -np.inf], np.nan).dropna(subset=["drift", "dFX", "TOTAL_ASSETS"])
out = {}
b = p.dropna(subset=["min_pct_fx", "max_pct_fx"])
A = b.TOTAL_ASSETS * 1e6
inside = (b.FX >= b.min_pct_fx) & (b.FX <= b.max_pct_fx)
cross = inside & ((b.FXp < b.min_pct_fx) | (b.FXp > b.max_pct_fx))
excess = (b.FXp - b.FXp.clip(b.min_pct_fx, b.max_pct_fx)).abs()
out["band"] = {"inside_share_assets": float(np.average(inside, weights=A)), "crossing_share_assets": float(np.average(cross, weights=A)),
               "avg_distance_to_bound_pp": float(np.average(np.minimum(b.FX - b.min_pct_fx, b.max_pct_fx - b.FX) * 100, weights=A)),
               "avg_monthly_drift_pp": float(np.average(b.drift.abs() * 100, weights=A)),
               "need_constant_bn": float((b.drift.abs() * A).sum() / 1e9), "need_policy_band_bn": float((excess * A)[cross].sum() / 1e9)}
agg = p.groupby("month").apply(lambda g: pd.Series({"dFX": np.average(g.dFX, weights=g.TOTAL_ASSETS),
                                                   "drift": np.average(g.drift, weights=g.TOTAL_ASSETS)}), include_groups=False)
for L in (1, 2, 3):
    agg[f"L{L}"] = agg.drift.shift(L)
z = agg.dropna()
X = np.column_stack([np.ones(len(z)), z.drift, z.L1, z.L2, z.L3])
bb = np.linalg.lstsq(X, z.dFX.values, rcond=None)[0]
e = z.dFX.values - X @ bb
se = np.sqrt(np.diag(e @ e / (len(z) - 5) * np.linalg.inv(X.T @ X)))
out["lags"] = {"coef_t..t-3": [float(x) for x in bb[1:]], "se": [float(x) for x in se[1:]], "cumulative_3m": float(bb[1:].sum()), "months": int(len(z))}
agg["y"] = agg.index.astype(str).str[:4]
out["trend_pp_per_month"] = {y: {"dFX": float(g.dFX.mean() * 100), "drift": float(g.drift.mean() * 100)} for y, g in agg.groupby("y")}
json.dump(out, open("data/results/need_gap_explained.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
