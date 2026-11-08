"""שתי בדיקות לזרם הרבעוני הנמדד (e1/e1b):
1. החלפת מכשירים: האם שינוי בחוזי מט"ח מתקזז מול שינוי בנכסים במט"ח / בנגזרי מניות באותו מסלול-רבעון?
   (מתאם, ויחס "ברוטו על כל המכשירים / נטו")
2. "צורך" מול ביצוע: הצורך = כמה מט"ח נדרש לקנות (+) / למכור (−) כדי לשמור על אחוז המט"ח הקיים
   = FX0·(תשואת המסלול) − רווח דולרי (פיזי+סינתטי) − FX0·שינוי השער.  ביצוע = הזרם הנמדד על כל המכשירים.
פלט: data/results/need_vs_actual.csv (לפי רבעון) + הדפסה
"""
import numpy as np
import pandas as pd

KEY = ["legal_id", "track", "q0"]
f = pd.read_csv("data/flows/track_fx_flows.csv.gz")
f["g"] = f.component.str.split(":").str[0]
w = f.pivot_table(index=KEY, columns="g", values="flow", aggfunc="sum").fillna(0)
val = pd.read_csv("data/flows/derivative_valuation.csv.gz").set_index(KEY).valuation_k
w["deriv"] = w.get("derivatives_mtm_change", 0) - val.reindex(w.index).fillna(0)
w["spot"] = w[["securities", "cash", "loans", "private_funds", "other"]].sum(axis=1)
w["total"] = w.spot + w.forwards + w.deriv
p = pd.read_csv("data/flows/flow_panel.csv.gz").set_index(KEY)
w = w.join(p[["total_k", "FX", "g_phys", "g_syn", "R1", "e"]], how="inner")
A = w.total_k
for c in ("spot", "forwards", "deriv", "total"):
    w[c + "_a"] = w[c] / A
w = w[w.total_a.abs() < 0.10]
w["need_a"] = w.FX * w.R1 - (w.g_phys + w.g_syn) - w.FX * w.e
w["need"] = w.need_a * A
print(f"מסלול-רבעון: {len(w)}")
print(f"1. מתאם שינוי חוזי מט\"ח מול שינוי נכסים במט\"ח: {w.forwards_a.corr(w.spot_a):.2f}; מול נגזרי מניות: {w.forwards_a.corr(w.deriv_a):.2f}")
print(f"   ברוטו (Σ|ספוט|+|חוזים|+|נגזרים|) / נטו (|סה\"כ|): {(w.spot.abs()+w.forwards.abs()+w.deriv.abs()).sum()/w.total.abs().sum():.2f}")
q = w.groupby(level="q0")[["spot", "forwards", "deriv", "total", "need"]].sum() / 1e6
q["ביצוע/צורך"] = q.total / q.need
q.round(2).to_csv("data/results/need_vs_actual.csv")
print(q.round(1).to_string())
b = np.polyfit(w.need_a, w.total_a, 1)
print(f"2. ביצוע = {b[0]:.2f} × צורך (מסלול-רבעון); מתאם {w.need_a.corr(w.total_a):.2f}")
