"""כיול: מקדם השפעה (אחוז שינוי USD/ILS לכל מיליארד $ זרם נדרש) מתוך הסדרות ההיסטוריות.

רגרסיה מרובה: Δ%USDILS(t) על זרם_גורם(t) ו-זרם_גורם(t-1) לכל גורם. השער של בנק ישראל נקבע בצהריים (שעון ישראל), לפני פתיחת ארה"ב -
לכן תגובה לשוק ארה"ב מופיעה בפיגור יום. הגורם הישראלי מתנהג שונה (משקיעים זרים) - מדווח ולא נכנס לכיול.
פלט: data/results/calibration.json
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd


def ols(y, X):
    X = np.column_stack([np.ones(len(y)), X])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    s2 = e @ e / (len(y) - X.shape[1])
    se = np.sqrt(np.diag(s2 * np.linalg.inv(X.T @ X)))
    return b, b / se, 1 - e @ e / ((y - y.mean()) @ (y - y.mean()))


out = {}
for f, name in (("D", "daily"), ("W", "weekly")):
    s = pd.read_csv(f"data/results/flows_{f}.csv", index_col=0, parse_dates=True)
    X = pd.DataFrame({f"{fac}_L{L}": s[f"flow_{fac}"].shift(L) for fac in ("us", "row", "il") for L in (0, 1)})
    z = pd.concat([s.usdils_chg, X], axis=1).dropna()
    b, t, r2 = ols(z.usdils_chg.values, z[X.columns].values)
    coef = {n: {"beta_pct_per_bn": float(bb * 1e5), "t": float(tt)} for n, bb, tt in zip(["const"] + list(X.columns), b, t)}
    # מקדם משותף ל-US+ROW בפיגור 1 (יומי) / פיגור 0-1 (שבועי): רגרסיה על הסכום
    comb = (z["us_L1"] + z["row_L1"]) if f == "D" else (z["us_L0"] + z["row_L0"] + z["row_L1"])
    bc, tc, _ = ols(z.usdils_chg.values, np.column_stack([comb, z["il_L0"], z["il_L1"]]))
    out[name] = {"n": int(len(z)), "r2": float(r2), "coef": coef,
                 "combined_us_row_beta_pct_per_bn": float(bc[1] * 1e5), "combined_t": float(tc[1])}
    print(name, f"n={len(z)} מקדם משותף US+ROW = {bc[1]*1e5:.3f}%/bn (t={tc[1]:.1f})")
Path("data/results/calibration.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
