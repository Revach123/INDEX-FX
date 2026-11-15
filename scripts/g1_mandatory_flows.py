"""הזרמים המחויבים: מה כללי המדיניות ומבנה המוצרים *מחייבים* בקנייה/מכירה של מט"ח אחרי זעזוע בשוק - חישוב מכני, לא אומדן.

בסיס: כל המסלולים בדוח 30.6.2026 (model2_inputs + מדיניות 2026 + נגזרים a6 + יתרות דולר נזילות), וכל קרנות המניות בחו"ל (דוח חודשי).
זעזוע: r = מדדי חו"ל (במטבע), s = ת"א, e = דולר/שקל.

מסלול (כל הגדלים כשבר מהנכסים A0; P = מניות חו"ל פיזיות, S = חשיפה בהחלפים/חוזים, X0 = חשיפת מט"ח כוללת):
  נכסים אחרי:        A1 = A0·[1 + P·((1+r)(1+e)−1) + S·r·(1+e) + (X0−P)·e + E_il·s + eqfr_ilf·r]
  חשיפת מט"ח פסיבית:  X1 = X0·(1+e) + (P+S)·r·(1+e)        (רווח על נכס דולרי ועל חוזה דולרי נצבר בדולר)
  חשיפת מניות פסיבית: Q1 = E_il·(1+s) + (P+S)·(1+r)(1+e) + eqfr_ilf·(1+r)
  מחויב לפי המדיניות = חריגה מהרצועה בלבד:  מכירה = max(0, X1/A1 − מקס')·A1 ; קנייה = max(0, מינ' − X1/A1)·A1,
     פחות אותה חריגה לפני הזעזוע (כדי לבודד את מה שהזעזוע עצמו מחייב).  "חזרה מלאה ליעד" מוצגת כגבול עליון, לא כחובה.
  אותו חישוב לשיעור המניות (מה חייבים להקטין/להגדיל בחשיפה למניות - בני"ע או בחוזים).
  Margin: בירידה, הפסד על חוזים/החלפים דולריים = S_usd·|r|. אם גדול מהדולרים הנזילים של המסלול (מזומן + בטחונות במט"ח) - ההפרש חייב להיקנות.
קרנות (מבנה המוצר):
  מגודרת:    חשיפת מט"ח 0 -> כל רווח דולרי על המדד חייב להימכר (ע"י הקרן בפורוורד או ע"י הבנק שמולה): −r × חשיפה למניות × שווי.
  לא מגודרת: חשיפת מט"ח = שווי הקרן -> הרווח נצבר בדולר; אין קנייה/מכירה נטו. ברוטו: הגדלת הפורוורד r × שווי מול מכירת הדולרים שהתקבלו בסילוק.
פלט: data/results/mandatory_flows.csv, mandatory_flows_detail.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d4_policy_rules import policies, policy_at  # noqa: E402
from e1_track_fx_flows import load  # noqa: E402
from e15_full_account import prep  # noqa: E402

KEY = ["legal_id", "track"]
t = pd.read_csv("data/model2_inputs.csv")
pol = policy_at(policies(), pd.Timestamp("2026-06-30"))
t = t.merge(pol, on=KEY, how="left")
# חוזים/החלפים על מניות חו"ל שהרווח בהם נצבר במט"ח, לפי סוג (a6)
d = pd.read_csv("data/history/deriv_2026Q2.csv.gz", low_memory=False)
d = d[(d.equity == True) & ~d.country.astype(str).str.contains("ישראל")]  # noqa: E712
d["exp_k"] = d.ratio * d.total_k
fut = d[d.category == "FUTURE"].groupby(KEY).exp_k.sum().rename("fut_k")
swp = d[d.category == "SWAP"].groupby(KEY).exp_k.sum().rename("swp_k")
t = t.merge(fut, on=KEY, how="left").merge(swp, on=KEY, how="left").fillna({"fut_k": 0.0, "swp_k": 0.0})
# דולרים נזילים: מזומן/פיקדונות ובטחונות במט"ח
p = prep(load("2026Q2"))
liq = p[p.bucket.isin(["cash_fx", "coll_fx"])].groupby(KEY + ["bucket"]).fair_value_k.sum().unstack().fillna(0.0)
t = t.merge(liq.reset_index(), on=KEY, how="left").fillna({"cash_fx": 0.0, "coll_fx": 0.0})

A0 = t.total_k / 1e6                                   # מיליארדי ש"ח
P, S, X0 = t.U_phys_us + t.U_phys_row, t.U_syn_us + t.U_syn_row, t.FX0
has = t.max_pct_fx.notna() & t.min_pct_fx.notna()
print(f"[g1] מסלולים: {len(t)}, נכסים {A0.sum():.0f} מיליארד; עם רצועת מט\"ח במדיניות: {has.sum()} ({A0[has].sum()/A0.sum():.0%} מהנכסים)")
print(f"     מניות חו\"ל פיזיות {(P*A0).sum():.0f}; חוזים/החלפים {(S*A0).sum():.0f} (מזה חוזים עתידיים {t.fut_k.sum()/1e6:.0f}, החלפים {t.swp_k.sum()/1e6:.0f}); חשיפת מט\"ח {(X0*A0).sum():.0f}")
print(f"     דולרים נזילים: מזומן {t.cash_fx.sum()/1e6:.0f}, בטחונות {t.coll_fx.sum()/1e6:.0f}")


def band_need(x, lo, hi):
    return np.where(x > hi, hi - x, np.where(x < lo, lo - x, 0.0))    # + קנייה, − מכירה (שבר מהנכסים)


def scenario(r, s, e):
    a1 = 1 + P * ((1 + r) * (1 + e) - 1) + S * r * (1 + e) + (X0 - P) * e + t.E_il * s + t.eqfr_ilf * r
    x1 = (X0 * (1 + e) + (P + S) * r * (1 + e)) / a1
    q0 = t.E_il + P + S + t.eqfr_ilf
    q1 = (t.E_il * (1 + s) + (P + S) * (1 + r) * (1 + e) + t.eqfr_ilf * (1 + r)) / a1
    A1 = A0 * a1
    out = {}
    lo, hi, tg = t.min_pct_fx / 100, t.max_pct_fx / 100, t.expected_pct_fx / 100
    need = (band_need(x1, lo, hi) * A1 - band_need(X0, lo, hi) * A0)
    out["מט\"ח – מחויב לפי הרצועה"] = np.nansum(np.where(has, need, 0.0))
    out["  מזה מכירה"] = np.nansum(np.where(has & (need < 0), need, 0.0))
    out["  מזה קנייה"] = np.nansum(np.where(has & (need > 0), need, 0.0))
    out["  מסלולים שחייבים לפעול"] = int((has & (np.abs(need) > 1e-9)).sum())
    full = ((tg - x1) * A1 - (tg - X0) * A0)
    out["מט\"ח – גבול עליון (חזרה מלאה ליעד)"] = np.nansum(np.where(tg.notna(), full, 0.0))
    out["  אילו שמרו על אחוז קבוע (כל המסלולים)"] = ((X0 - x1) * A1).sum()
    hq = t.max_pct_equity.notna() & t.min_pct_equity.notna()
    lo, hi = t.min_pct_equity / 100, t.max_pct_equity / 100
    needq = band_need(q1, lo, hi) * A1 - band_need(q0, lo, hi) * A0
    out["מניות – מחויב לפי הרצועה (שינוי חשיפה)"] = np.nansum(np.where(hq, needq, 0.0))
    out["  מסלולים שחייבים לפעול (מניות)"] = int((hq & (np.abs(needq) > 1e-9)).sum())
    out["רווח/הפסד דולרי: מניות פיזיות"] = (P * r * (1 + e) * A0).sum()
    out["רווח/הפסד דולרי: חוזים והחלפים"] = (S * r * (1 + e) * A0).sum()
    # margin: הפסד על חוזים דולריים מול דולרים נזילים (רק בירידה)
    if r < 0:
        loss_f = t.fut_k / 1e6 * (-r)
        loss_all = (t.fut_k + t.swp_k) / 1e6 * (-r)
        liqd = (t.cash_fx + t.coll_fx) / 1e6
        out["Margin: הפסד על חוזים עתידיים (תשלום יומי בדולר)"] = loss_f.sum()
        out["  מזה מעבר לדולרים הנזילים (חייב להיקנות)"] = np.maximum(0, loss_f - liqd).sum()
        out["Margin: הפסד על חוזים + החלפים"] = loss_all.sum()
        out["  מזה מעבר לדולרים הנזילים"] = np.maximum(0, loss_all - liqd).sum()
    return out


f = pd.read_csv("data/funds/funds.csv", dtype={"fund": str})
f = f[f.primary.eq("מניות בחו\"ל") & f.aum_m.notna()]
hed = f[f.hedged.astype(str).isin(["True", "true", "1"]) | (f.hedged == True)]  # noqa: E712
unh = f.drop(hed.index)
H = (hed.aum_m * hed.eq_pct.fillna(100) / 100).sum() / 1e3
Um = (unh[unh.mimic == True].aum_m).sum() / 1e3  # noqa: E712
print(f"     קרנות מניות חו\"ל: מגודרות {hed.aum_m.sum()/1e3:.1f} מיליארד (חשיפה למניות {H:.1f}); לא מגודרות מחקות {Um:.1f}; לא מגודרות אקטיביות {unh[unh.mimic != True].aum_m.sum()/1e3:.1f}")  # noqa: E712

SC = [("S&P +10%", .10, 0, 0), ("S&P +10%, דולר −2%", .10, 0, -.02), ("S&P +10%, ת\"א +5%, דולר −2%", .10, .05, -.02),
      ("S&P −10%", -.10, 0, 0), ("S&P −10%, דולר +2%", -.10, 0, .02), ("S&P −20%, דולר +5%", -.20, -.10, .05), ("S&P +1%", .01, 0, 0)]
res = {}
for lab, r, s, e in SC:
    o = scenario(r, s, e)
    o["קרנות מגודרות – מכירה/קנייה מחויבת (קרן או בנק)"] = -r * H * (1 + 0)
    o["קרנות לא מגודרות – נטו"] = 0.0
    o["  ברוטו: הגדלת פורוורד מול מכירת דולר מהסילוק"] = r * Um
    o["סה\"כ מחויב (רצועות המסלולים + קרנות מגודרות)"] = o["מט\"ח – מחויב לפי הרצועה"] + o["קרנות מגודרות – מכירה/קנייה מחויבת (קרן או בנק)"]
    res[lab] = o
R = pd.DataFrame(res)
R.to_csv("data/results/mandatory_flows.csv")
pd.set_option("display.width", 280, "display.max_columns", 20, "display.float_format", lambda v: f"{v:,.1f}")
print(R.to_string())
