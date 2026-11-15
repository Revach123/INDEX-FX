"""איזון מלא מול המציאות, רבעון אחרי רבעון, אחרי הורדת המגמה.

לכל רבעון 2024Q2-2026Q2:
  צורך = מה שהמסלולים היו קונים/מוכרים במט"ח אילו כל אחד חזר בדיוק לאחוז המט"ח שהיה לו בתחילת הרבעון:
         (FX0 − FX פסיבי) × נכסים בסוף הרבעון, מפאנל המסלולים (flow_panel), מוגדל ליחס הנכסים של כל המסלולים (data.gov).
  בפועל = (א) עסקאות המט"ח נטו של המוסדיים לפי בנק ישראל, (ב) המדידה מדוחות הנכסים (e9).
  מודל: בפועל = מגמה קבועה + b × צורך.   b = איזה חלק מהאיזון המלא בוצע באותו רבעון; המגמה = מה שנמכר/נקנה בלי קשר לשוק.
פלט: data/results/full_balance_history.csv
"""
import numpy as np
import pandas as pd

p = pd.read_csv("data/flows/flow_panel.csv.gz")
p["need_k"] = (p.FX - p.FXp) * p.total_k1
g = p.groupby("q0").agg(need=("need_k", "sum"), A=("total_k", "sum")) / 1e6
dg = pd.read_csv("data/datagov/monthly.csv.gz", low_memory=False, usecols=["REPORT_PERIOD", "TOTAL_ASSETS"])
dg["q"] = pd.PeriodIndex(dg.REPORT_PERIOD.astype(str), freq="M")
tot = dg.groupby("q").TOTAL_ASSETS.sum() / 1e3
tot = tot[tot.index.month % 3 == 0]
tot.index = tot.index.asfreq("Q").astype(str)
g["A_all"] = tot.reindex(g.index)
g["need_all"] = g.need * g.A_all / g.A
g.index = (pd.PeriodIndex(g.index, freq="Q") + 1).astype(str)
t = pd.read_csv("data/results/quarterly_table.csv", index_col=0)
out = pd.DataFrame({"S&P (%)": t["S&P 500 (%)"], "ת\"א-125 (%)": t["ת\"א-125 (%)"], "דולר (%)": t["דולר/שקל (%)"],
                    "צורך לפי איזון מלא (כל המסלולים)": g.need_all, "בפועל – בנק ישראל (מוסדיים)": t["בנק ישראל: מוסדיים נטו (מיליארד ש\"ח)"],
                    "בפועל – מדוחות המסלולים": t["מסלולים: סה\"כ"]}).dropna()
print(f"כיסוי הפאנל: {(g.A/g.A_all).mean():.0%} מנכסי המסלולים בממוצע")


def fit(y, x):
    X = np.column_stack([np.ones(len(x)), x])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    se = np.sqrt(np.diag(e @ e / (len(y) - 2) * np.linalg.inv(X.T @ X)))
    return b, se, 1 - e @ e / ((y - y.mean()) ** 2).sum()


res = []
for c in ("בפועל – בנק ישראל (מוסדיים)", "בפועל – מדוחות המסלולים"):
    b, se, r2 = fit(out[c].values, out["צורך לפי איזון מלא (כל המסלולים)"].values)
    out[c + " פחות המגמה"] = out[c] - b[0]
    res.append({"סדרה": c, "מגמה קבועה (מיליארד ש\"ח לרבעון)": b[0], "±": 1.96 * se[0], "חלק מהאיזון המלא שבוצע (b)": b[1], "± ": 1.96 * se[1], "R²": r2,
                "מתאם": np.corrcoef(out[c], out["צורך לפי איזון מלא (כל המסלולים)"])[0, 1]})
out.round(1).to_csv("data/results/full_balance_history.csv")
pd.set_option("display.width", 250)
print(out.round(1).to_string())
print(pd.DataFrame(res).round(2).to_string(index=False))
print("סכום 9 רבעונים:", out.sum().round(0).to_dict())
