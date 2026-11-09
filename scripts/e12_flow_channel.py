"""השלב הבא: האם המדד משפיע על השקל *דרך* זרם המט"ח של המוסדיים, או רק דרך סנטימנט משותף?

נתונים (רבעוני, 2018Q1–2026Q2, 34 רבעונים):
  זרמים: בנק ישראל WEB_TV_EX_*_Q - עסקאות מט"ח נטו לפי מגזר (מיליארדי דולר; + = קניית מט"ח)  [data/market/boi_inst_fx_q.csv]
  שוק:   S&P 500 ות"א-125 (Yahoo), USD/ILS יציג (בנק ישראל) - נשמרים ב-data/market/long_*.csv
שלבים:
  1. תגובת הזרם: INST = a + b1·S&P + b2·ת"א            (גידור צפוי: b1 < 0 - עליית S&P -> מכירת דולר)
  2. משוואה מקוצרת: Δדולר = a + c1·S&P + c2·ת"א
  3. עם הזרם:       Δדולר = a + c1'·S&P + c2'·ת"א + d·INST
     חלק ההשפעה של S&P שעובר דרך זרם המוסדיים = (c1 − c1') / c1, רווח סמך ב-bootstrap (5000 דגימות רבעונים).
  4. מי סופג: מתאם הזרם של כל מגזר עם זרם המוסדיים.
כל השלבים גם ללא 2020Q1 (קורונה - קניית דולר חריגה לכיסוי בטחונות).
אזהרה: זרם ושער נקבעים יחד; d הוא קשר נמדד, לא מכפיל סיבתי מוכח.
פלט: data/results/flow_channel.csv
"""
import io
import urllib.request

import numpy as np
import pandas as pd
import yfinance as yf

UA = {"User-Agent": "index-fx-research/0.1"}
START = "2017-10-01"
px = {}
for s in ("^GSPC", "^TA125.TA"):
    h = yf.Ticker(s).history(start=START, auto_adjust=False)
    h.index = h.index.tz_localize(None).normalize()
    px[s] = h.Close
px = pd.DataFrame(px)
px.to_csv("data/market/long_prices.csv")
u = "https://edge.boi.gov.il/FusionEdgeServer/sdmx/v2/data/dataflow/BOI.STATISTICS/EXR/1.0/RER_USD_ILS?startperiod=" + START + "&format=csv"
f = pd.read_csv(io.BytesIO(urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=120).read()))
fx = f.set_index(pd.to_datetime(f.TIME_PERIOD)).OBS_VALUE.astype(float).sort_index()
fx.to_csv("data/market/long_usdils.csv")

q = lambda s: s.dropna().resample("QE").last()  # noqa: E731
m = pd.DataFrame({"fx": q(fx).pct_change() * 100, "sp": q(px["^GSPC"]).pct_change() * 100, "ta": q(px["^TA125.TA"]).pct_change() * 100})
m.index = m.index.to_period("Q")
b = pd.read_csv("data/market/boi_inst_fx_q.csv", index_col=0)
b.index = pd.PeriodIndex(b.index.str.replace("-", ""), freq="Q")
d = m.join(b / 1000, how="inner").dropna(subset=["fx", "sp", "ta", "IL_INST"])


def ols(y, X):
    X = np.column_stack([np.ones(len(y))] + list(X))
    bb = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ bb
    se = np.sqrt(np.diag(e @ e / (len(y) - X.shape[1]) * np.linalg.inv(X.T @ X)))
    return bb, se, 1 - e @ e / ((y - y.mean()) ** 2).sum()


rows = []
rng = np.random.default_rng(0)
for lab, dd in (("כל הרבעונים", d), ("ללא 2020Q1", d.drop(pd.Period("2020Q1")))):
    y, sp, ta, inst = dd.fx.values, dd.sp.values, dd.ta.values, dd.IL_INST.values
    b1, s1, r1 = ols(inst, [sp, ta])
    b2, s2, r2 = ols(y, [sp, ta])
    b3, s3, r3 = ols(y, [sp, ta, inst])
    share = (b2[1] - b3[1]) / b2[1]
    bs = []
    for _ in range(5000):
        i = rng.integers(0, len(dd), len(dd))
        c = ols(y[i], [sp[i], ta[i]])[0][1]
        c2 = ols(y[i], [sp[i], ta[i], inst[i]])[0][1]
        bs.append((c - c2) / c)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    n = len(dd)
    rows += [
        {"מדגם": lab, "n": n, "משוואה": "1. זרם מוסדיים (מיליארד $) ~ מדדים", "מקדם S&P": b1[1], "±": 1.96 * s1[1], "מקדם ת\"א": b1[2], "± ": 1.96 * s1[2], "מקדם זרם": np.nan, "±  ": np.nan, "R²": r1},
        {"מדגם": lab, "n": n, "משוואה": "2. Δדולר (%) ~ מדדים", "מקדם S&P": b2[1], "±": 1.96 * s2[1], "מקדם ת\"א": b2[2], "± ": 1.96 * s2[2], "מקדם זרם": np.nan, "±  ": np.nan, "R²": r2},
        {"מדגם": lab, "n": n, "משוואה": "3. Δדולר (%) ~ מדדים + זרם מוסדיים", "מקדם S&P": b3[1], "±": 1.96 * s3[1], "מקדם ת\"א": b3[2], "± ": 1.96 * s3[2], "מקדם זרם": b3[3], "±  ": 1.96 * s3[3], "R²": r3},
        {"מדגם": lab, "n": n, "משוואה": f"חלק השפעת S&P שעובר דרך זרם המוסדיים: {share:.0%} (רס\"ב 95%: {lo:.0%} עד {hi:.0%})"},
    ]
out = pd.DataFrame(rows)
out.round(3).to_csv("data/results/flow_channel.csv", index=False)
pd.set_option("display.width", 250, "display.max_colwidth", 90)
print(out.round(3).to_string(index=False))
names = {"IL_HH": "משקי בית", "IL_FI": "פיננסיים בארץ", "IL_LB": "בנקים מקומיים", "IL_REAL": "מגזר עסקי",
         "NR_FI": "תושבי חוץ פיננסיים", "NR_NFI": "תושבי חוץ לא פיננסיים", "NR_OTHR": "תושבי חוץ אחר"}
print("\nמי סופג (מתאם עם זרם המוסדיים) | ממוצע רבעוני (מיליארד $) | מתאם עם Δדולר:")
for k, v in names.items():
    print(f"  {v:22s} {d[k].corr(d.IL_INST):+.2f} | {d[k].mean():+.2f} | {d[k].corr(d.fx):+.2f}")
print(f"  {'מוסדיים':22s}  —    | {d.IL_INST.mean():+.2f} | {d.IL_INST.corr(d.fx):+.2f}")
print("רבעונים:", d.index.min(), "→", d.index.max())
