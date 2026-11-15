"""מה עושים עם כל שקל שנכנס? ניתוח מקורות-ושימושים ברמת מסלול-רבעון (על החשבון המלא e15).

מדגם "חשבון סגור": מסלול-רבעון שיש לו הפקדות מ-data.gov, והזהות (Σ שימושים − Σ מקורות) נסגרת עד 3% מהנכסים.
מבחן א - הקצאה: כל שימוש (שבר מהנכסים) = Σ b·מקור + אפקט רבעון.  b = כמה מכל שקל של המקור הולך לשימוש הזה.
          סכום ה-b על פני כל השימושים ≈ 1 (כי החשבון סגור).  שגיאות מקובצות לפי מסלול.
מבחן ב - חשיפות: שינוי אקטיבי בחשיפה (לא שערוך) מול הרווחים:
   מניות חו"ל: eq_for + eq_for_ils + syn_trade   (קניית מניות/קרנות + הוספת חוזים)
   מט"ח:        Σ שימושים במט"ח + Δ פורוורדים − תזרים ההחלפים   (= קנייה/מכירה נטו של מט"ח, כמו e9)
פלט: data/results/cash_allocation.csv, data/results/exposure_response.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d3_rebalancing_history import wls_cluster  # noqa: E402

USES = ["eq_for", "eq_for_ils", "eq_il", "bond_fx", "bond_ils", "cash_fx", "cash_ils", "coll_fx", "coll_ils", "alt_fx", "alt_ils"]
LAB = {"eq_for": "מניות/קרנות מניות במט\"ח", "eq_for_ils": "קרנות ישראליות על מניות חו\"ל", "eq_il": "מניות בישראל",
       "bond_fx": "אג\"ח במט\"ח", "bond_ils": "אג\"ח ומק\"מ בש\"ח", "cash_fx": "מזומן במט\"ח", "cash_ils": "מזומן בש\"ח",
       "coll_fx": "בטחונות במט\"ח", "coll_ils": "בטחונות בש\"ח", "alt_fx": "קרנות פרטיות/הלוואות/אחר במט\"ח",
       "alt_ils": "קרנות פרטיות/הלוואות/אחר בש\"ח"}
SRC = ["dep", "eqd_settle", "fwd_settle"]
SLAB = {"dep": "הפקדות נטו", "eqd_settle": "תזרים מהחלפים/חוזים על מניות חו\"ל", "fwd_settle": "תזרים מפורוורדים"}

r = pd.read_csv("data/flows/full_account.csv.gz")
for c in USES:
    if c not in r:
        r[c] = 0.0
r = r[r.A0 > 0].copy()
r["uses"] = r[USES].sum(axis=1)
r["sources"] = r[SRC + ["oth_deriv"]].sum(axis=1, min_count=4)
r["res"] = (r.uses - r.sources) / r.A0
n_all, A_all = len(r), r.A0.sum()
c = r[r.dep.notna() & r.res.abs().lt(0.03)].copy()
print(f"[e16] מסלול-רבעון: {n_all}; עם הפקדות: {r.dep.notna().sum()} ; חשבון סגור (|שארית|<3%): {len(c)} = {c.A0.sum()/A_all:.0%} מהנכסים")
print(f"      שארית חציונית במדגם הסגור: {c.res.median()*100:.2f}% מהנכסים לרבעון (הכנסות שוטפות)")
c["total_k"] = c.A0
for s in SRC:
    c["x_" + s] = c[s] / c.A0
X = ["x_" + s for s in SRC]
rows = []
for wt in (True, False):
    tot = np.zeros(len(SRC))
    for u in USES:
        b, se = wls_cluster(c.assign(FX1=c[u] / c.A0, FX=0.0), X, wt)
        tot += b
        rows.append({"שימוש": LAB[u], "שקלול": "נכסים" if wt else "ללא", "n": len(c),
                     **{SLAB[s]: round(b[i], 3) for i, s in enumerate(SRC)}, **{SLAB[s] + " ±": round(1.96 * se[i], 3) for i, s in enumerate(SRC)}})
    rows.append({"שימוש": "סה\"כ (אמור להיות ≈1)", "שקלול": "נכסים" if wt else "ללא", "n": len(c), **{SLAB[s]: round(tot[i], 3) for i, s in enumerate(SRC)}})
    for grp, us in (("סה\"כ נכסים במט\"ח", ["eq_for", "bond_fx", "cash_fx", "coll_fx", "alt_fx"]), ("סה\"כ נכסים בש\"ח", ["eq_for_ils", "eq_il", "bond_ils", "cash_ils", "coll_ils", "alt_ils"])):
        b, se = wls_cluster(c.assign(FX1=c[us].sum(axis=1) / c.A0, FX=0.0), X, wt)
        rows.append({"שימוש": grp, "שקלול": "נכסים" if wt else "ללא", "n": len(c),
                     **{SLAB[s]: round(b[i], 3) for i, s in enumerate(SRC)}, **{SLAB[s] + " ±": round(1.96 * se[i], 3) for i, s in enumerate(SRC)}})
    # פעולות שאינן שימוש במזומן: שינוי הפורוורדים והחוזים
    for y, lab in (("fwd_trade", "Δ פורוורדים (− = מכירת דולר עתידית נוספת)"), ("syn_trade", "Δ חוזים על מניות חו\"ל (חשיפה)")):
        d = c[(c[y] / c.A0).abs() < 0.10]
        if y == "syn_trade":
            d = d[~d.q1.isin(["2024Q2", "2024Q3"])]
        b, se = wls_cluster(d.assign(FX1=d[y] / d.A0, FX=0.0), X, wt)
        rows.append({"שימוש": lab, "שקלול": "נכסים" if wt else "ללא", "n": len(d),
                     **{SLAB[s]: round(b[i], 3) for i, s in enumerate(SRC)}, **{SLAB[s] + " ±": round(1.96 * se[i], 3) for i, s in enumerate(SRC)}})
a = pd.DataFrame(rows)
a.to_csv("data/results/cash_allocation.csv", index=False)
pd.set_option("display.width", 250, "display.max_colwidth", 60)
print(a[a["שקלול"] == "נכסים"].drop(columns=["שקלול"]).to_string(index=False))
print(a[a["שקלול"] == "ללא"].drop(columns=["שקלול"]).to_string(index=False))

# מבחן ב - תגובת החשיפות לרווחים (במדגם הסגור שיש לו גם רווחי הפאנל)
e = c.dropna(subset=["gain_phys", "gain_syn"]).copy()
e["fx_net"] = e[["eq_for", "bond_fx", "cash_fx", "coll_fx", "alt_fx"]].sum(axis=1) + e.fwd_trade - e.eqd_settle
e["eqf_trade"] = e.eq_for + e.eq_for_ils + e.syn_trade
e["x_dep"] = e.dep / e.A0
e["x_fwdpnl"] = e.fwd_pnl / e.A0
XS = ["gain_phys", "gain_syn", "x_fwdpnl", "x_dep"]
XL = ["רווח על מניות חו\"ל שנקנו", "רווח על חוזים", "רווח על פורוורדים (שקל התחזק)", "הפקדות נטו"]
rows = []
for y, lab, flt in (("fx_net", "קנייה/מכירה נטו של מט\"ח", None), ("eqf_trade", "שינוי אקטיבי בחשיפה למניות חו\"ל", ["2024Q2", "2024Q3"]),
                    ("eq_for", "מזה: קניית מניות חו\"ל", None), ("syn_trade", "מזה: הוספת חוזים", ["2024Q2", "2024Q3"]), ("fwd_trade", "Δ פורוורדים", None)):
    d = e[(e[y] / e.A0).abs() < 0.10]
    if flt:
        d = d[~d.q1.isin(flt)]
    for wt in (True, False):
        b, se = wls_cluster(d.assign(FX1=d[y] / d.A0, FX=0.0), XS, wt)
        rows.append({"תוצאה": lab, "שקלול": "נכסים" if wt else "ללא", "n": len(d), **{XL[i]: round(b[i], 3) for i in range(4)},
                     **{XL[i] + " ±": round(1.96 * se[i], 3) for i in range(4)}})
x = pd.DataFrame(rows)
x.to_csv("data/results/exposure_response.csv", index=False)
print(x.to_string(index=False))

# מבחן ג - עמידות: אותן תגובות עם בקרה לגודל ספר הנגזרים של המסלול (פורוורדים/נכסים, חוזים/נכסים).
# בלי הבקרה, מסלול עם ספר גדול גם מרוויח יותר וגם (בתקופה הזו) הגדיל גידור - והמקדם מערבב את השניים.
c["fx_assets"] = c[["eq_for", "bond_fx", "cash_fx", "coll_fx", "alt_fx"]].sum(axis=1)
c["fx_net"] = c.fx_assets + c.fwd_trade - c.eqd_settle
c["eqf_trade"] = c.eq_for + c.eq_for_ils + c.syn_trade
c["x_val"], c["x_fpnl"] = c.valuation_k / c.A0, c.fwd_pnl / c.A0
c["b_fwd"], c["b_syn"] = c.fwd_not0 / c.A0, c.syn0.fillna(0.0) / c.A0
XR = ["x_dep", "x_val", "x_fpnl", "b_fwd", "b_syn"]
XRL = ["הפקדות נטו", "רווח על חוזי מניות חו\"ל", "רווח על פורוורדים", "(בקרה) ספר פורוורדים", "(בקרה) ספר חוזים"]
rows = []
for y, lab, flt in (("fx_net", "קנייה/מכירה נטו של מט\"ח", None), ("fx_assets", "קניית נכסים במט\"ח", None), ("fwd_trade", "Δ פורוורדים", None),
                    ("syn_trade", "Δ חוזים על מניות חו\"ל", ["2024Q2", "2024Q3"]), ("eq_for", "קניית מניות חו\"ל (נכס)", None),
                    ("eqf_trade", "שינוי אקטיבי כולל בחשיפה למניות חו\"ל", ["2024Q2", "2024Q3"])):
    d = c[(c[y] / c.A0).abs() < 0.10]
    if flt:
        d = d[~d.q1.isin(flt)]
    for wt in (True, False):
        b, se = wls_cluster(d.assign(FX1=d[y] / d.A0, FX=0.0), XR, wt)
        rows.append({"תוצאה": lab, "שקלול": "נכסים" if wt else "ללא", "n": len(d), **{XRL[i]: round(b[i], 3) for i in range(5)},
                     **{XRL[i] + " ±": round(1.96 * se[i], 3) for i in range(3)}})
rb = pd.DataFrame(rows)
rb.to_csv("data/results/robust_responses.csv", index=False)
print("\n--- עם בקרה לגודל הספר ---")
print(rb.to_string(index=False))

# כמה זה אמור להשפיע: תרחיש S&P +10% ברבעון, על בסיס כל המסלולים בדוח 30.6.2026 (מיליארדי ש"ח)
st = pd.read_csv("data/history/track_quarter_state.csv.gz")
s = st[st.q == "2026Q2"]
syn, phys, A = s.u_syn_k.sum() / 1e6, s.u_phys_k.sum() / 1e6, s.total_k.sum() / 1e6
g = lambda lab, col: rb[(rb["תוצאה"] == lab)][[col, col + " ±"]].values  # noqa: E731
gain_syn = syn * 0.09          # 10% פחות ~1% ריבית דולרית לרבעון
sc = []
for lab in ("קנייה/מכירה נטו של מט\"ח", "Δ חוזים על מניות חו\"ל", "קניית מניות חו\"ל (נכס)", "Δ פורוורדים"):
    (bw, sw), (bu, su) = g(lab, "רווח על חוזי מניות חו\"ל")
    sc.append({"תוצאה": lab, "משוקלל": bw * gain_syn, "משוקלל ±": sw * gain_syn, "ללא שקלול": bu * gain_syn, "ללא שקלול ±": su * gain_syn})
fk = pd.read_csv("data/funds/forwards_monthly_kappa.csv")
fk = fk[(fk["סוג"] == "הכל") & (fk["גידור"] == "לא מגודרת")].iloc[0]
funds = fk["κ (קנייה מכל 1% עלייה)"] * 10 / 100 * fk["שווי אחרון (מיליארד)"]
tv = pd.read_csv("data/market/boi_fx_turnover_daily.csv", parse_dates=["TIME_PERIOD"]).set_index("TIME_PERIOD")
conv = tv.loc["2025-07-01":"2026-06-30", "WEB_TV_CONV_IL"]
fxr = pd.read_csv("data/market/long_usdils.csv", parse_dates=["TIME_PERIOD"]).set_index("TIME_PERIOD").OBS_VALUE.loc["2026-04-01":"2026-06-30"].mean()
qturn = conv.mean() * 62 / 1000 * fxr     # מחזור המרות של תושבי ישראל ברבעון, מיליארדי ש"ח
scd = pd.DataFrame(sc).round(1)
scd.to_csv("data/results/scenario_full_account.csv", index=False)
print(f"\nתרחיש S&P +10% ברבעון. בסיס 30.6.2026: נכסים {A:.0f}, חוזים על מניות חו\"ל {syn:.0f}, מניות חו\"ל פיזיות {phys:.0f} (מיליארד ש\"ח); רווח על החוזים {gain_syn:.0f}")
print(scd.to_string(index=False))
print(f"קרנות מחקות לא מגודרות: קנייה {funds:+.1f}")
print(f"מחזור המרות מט\"ח של תושבי ישראל (בנק ישראל, 7.2025–6.2026): {conv.mean():.0f} מיליון $ ביום ≈ {qturn:.0f} מיליארד ש\"ח ברבעון")
