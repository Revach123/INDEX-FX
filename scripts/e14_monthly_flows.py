"""זרם מט"ח חודשי של המסלולים מנתוני data.gov (במקום רבעוני מהדוחות) - פי 3 תצפיות.

לכל מסלול וחודש (פאנל d5, 2024-03 -> 2026-08):
  שווי המט"ח בפועל בסוף החודש          = FX1 × A1                      (חשיפת מט"ח רשמית × נכסים)
  שווי המט"ח אילו לא נגעו בתיק (פסיבי)  = FXp × A0 × (1+R)              (FXp מ-d5: תשואות המדדים, שער הדולר, הרכב החשיפה)
  זרם (קנייה + / מכירה −)              = הפרש השניים (מיליוני ש"ח)
  מזה "השקעת כסף חדש באותו אחוז"       = FX0 × הפקדות נטו בחודש (כשיש)
מסלולים עם |זרם| > 10% מהנכסים בחודש (מיזוג/שינוי דיווח) מוחרגים ונספרים.
בדיקות: (1) סיכום לרבעונים מול בנק ישראל (מוסדיים) ומול המדידה מהדוחות (e9);
(2) זרם חודשי ~ S&P + ת"א-125 (+ הפקדות); (3) Δדולר ~ S&P + ת"א-125 + זרם (חלק ההשפעה שעובר דרך הזרם, bootstrap);
(4) פיגורים: זרם ~ S&P בחודש ובחודשיים הקודמים.
פלט: data/results/monthly_flows.csv, data/results/monthly_flow_tests.csv
"""
import numpy as np
import pandas as pd

p = pd.read_csv("data/results/policy_monthly_panel.csv.gz").sort_values(["track", "month"])
nx = p.groupby("track").shift(-1)
nxt = (pd.PeriodIndex(p.month, freq="M") + 1).astype(str)
p["D1"] = nx.NET_MONTHLY_DEPOSITS.where(nx.month == nxt)
p = p.dropna(subset=["FX", "FX1", "FXp", "TOTAL_ASSETS", "TOTAL_ASSETS1", "MONTHLY_YIELD1"])
R = p.MONTHLY_YIELD1 / 100
p["flow"] = p.FX1 * p.TOTAL_ASSETS1 - p.FXp * p.TOTAL_ASSETS * (1 + R)
p["dep_fx"] = p.FX * p.D1
p["rel"] = p.flow / p.TOTAL_ASSETS
bad = p.rel.abs() > 0.10
print(f"[e14] {len(p)} מסלול-חודש; מוחרגים (|זרם|>10% מהנכסים): {bad.sum()} ({p[bad].TOTAL_ASSETS.sum()/p.TOTAL_ASSETS.sum():.1%} מהנכסים)")
p = p[~bad]
p["fm"] = nxt[p.index] if False else (pd.PeriodIndex(p.month, freq="M") + 1)   # החודש שבו התרחש הזרם
m = p.groupby("fm").agg(flow_bn=("flow", "sum"), dep_fx_bn=("dep_fx", "sum"), assets_bn=("TOTAL_ASSETS", "sum"), tracks=("track", "nunique"))
m[["flow_bn", "dep_fx_bn", "assets_bn"]] /= 1e3

px = pd.read_csv("data/market/long_prices.csv", parse_dates=["Date"]).set_index("Date")
fx = pd.read_csv("data/market/long_usdils.csv", parse_dates=["TIME_PERIOD"]).set_index("TIME_PERIOD").OBS_VALUE
me = lambda s: s.dropna().resample("ME").last()  # noqa: E731
mk = pd.DataFrame({"sp": me(px["^GSPC"]).pct_change() * 100, "ta": me(px["^TA125.TA"]).pct_change() * 100, "fx": me(fx).pct_change() * 100})
mk.index = mk.index.to_period("M")
m = m.join(mk, how="left")
m["flow_pct"] = m.flow_bn / m.assets_bn * 100
m.round(3).to_csv("data/results/monthly_flows.csv")
pd.set_option("display.width", 220)
print(m.round(2).to_string())

rows = []
# (1) אימות: סכום רבעוני מול בנק ישראל ומול הדוחות
q = m.copy()
q["q"] = q.index.asfreq("Q")
full = q.groupby("q").flow_bn.agg(["sum", "size"])
full = full[full["size"] == 3]["sum"]
b = pd.read_csv("data/market/boi_inst_fx_q.csv", index_col=0)
b.index = pd.PeriodIndex(b.index.str.replace("-", ""), freq="Q")
fxq = fx.resample("QE").mean()
fxq.index = fxq.index.to_period("Q")
boi = b.IL_INST * fxq / 1e3
e9 = pd.read_csv("data/results/fx_flow_breakdown.csv", index_col=0)
e9.index = pd.PeriodIndex(e9.index, freq="Q") + 1
v = pd.DataFrame({"data.gov חודשי (סכום רבעוני)": full, "דוחות (e9)": e9["סה\"כ נטו"], "בנק ישראל": boi}).dropna()
print("\nאימות רבעוני (מיליארדי ש\"ח):\n", v.round(1).to_string())
for c in ("דוחות (e9)", "בנק ישראל"):
    rows.append({"מבחן": f"אימות: מתאם רבעוני data.gov מול {c}", "n": len(v), "ערך": v.iloc[:, 0].corr(v[c])})


def ols(y, X):
    X = np.column_stack([np.ones(len(y))] + list(X))
    bb = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ bb
    n, k = X.shape
    A = np.linalg.inv(X.T @ X)
    V = A @ (X.T * e ** 2) @ X @ A * n / (n - k)
    return bb, np.sqrt(np.diag(V)), 1 - e @ e / ((y - y.mean()) ** 2).sum()


d = m.dropna(subset=["sp", "ta", "fx", "flow_bn"])
y = d.flow_bn.values
bb, se, r2 = ols(y, [d.sp, d.ta])
rows += [{"מבחן": "זרם חודשי (מיליארד ש\"ח) ~ S&P (לכל 1%)", "n": len(d), "ערך": bb[1], "±95%": 1.96 * se[1], "R²": r2},
         {"מבחן": "זרם חודשי (מיליארד ש\"ח) ~ ת\"א-125 (לכל 1%)", "n": len(d), "ערך": bb[2], "±95%": 1.96 * se[2], "R²": r2}]
dd = d.dropna(subset=["dep_fx_bn"])
bb, se, r2 = ols(dd.flow_bn.values, [dd.sp, dd.ta, dd.dep_fx_bn])
rows.append({"מבחן": "זרם ~ הפקדות × אחוז מט\"ח (1 = כל הכסף החדש מושקע באותו אחוז)", "n": len(dd), "ערך": bb[3], "±95%": 1.96 * se[3], "R²": r2})
bb, se, r2 = ols(d.flow_pct.values, [d.sp, d.ta])
rows += [{"מבחן": "זרם (% מהנכסים) ~ S&P", "n": len(d), "ערך": bb[1], "±95%": 1.96 * se[1], "R²": r2},
         {"מבחן": "זרם (% מהנכסים) ~ ת\"א-125", "n": len(d), "ערך": bb[2], "±95%": 1.96 * se[2], "R²": r2}]
# (3) ערוץ הזרם
fxv, sp, ta, fl = d.fx.values, d.sp.values, d.ta.values, d.flow_bn.values
c2, s2, r22 = ols(fxv, [sp, ta])
c3, s3, r23 = ols(fxv, [sp, ta, fl])
rng = np.random.default_rng(0)
bs = []
for _ in range(5000):
    i = rng.integers(0, len(d), len(d))
    a = ols(fxv[i], [sp[i], ta[i]])[0][1]
    bs.append((a - ols(fxv[i], [sp[i], ta[i], fl[i]])[0][1]) / a)
lo, hi = np.percentile(bs, [2.5, 97.5])
rows += [{"מבחן": "Δדולר (%) ~ S&P (בלי הזרם)", "n": len(d), "ערך": c2[1], "±95%": 1.96 * s2[1], "R²": r22},
         {"מבחן": "Δדולר (%) ~ S&P (עם הזרם)", "n": len(d), "ערך": c3[1], "±95%": 1.96 * s3[1], "R²": r23},
         {"מבחן": "Δדולר (%) ~ זרם (לכל מיליארד ש\"ח)", "n": len(d), "ערך": c3[3], "±95%": 1.96 * s3[3], "R²": r23},
         {"מבחן": f"חלק השפעת S&P על השער שעובר דרך הזרם (רס\"ב {lo:.0%} עד {hi:.0%})", "n": len(d), "ערך": (c2[1] - c3[1]) / c2[1]}]
# (4) פיגורים
L = d.copy()
L["sp1"], L["sp2"] = mk.sp.shift(1).reindex(L.index), mk.sp.shift(2).reindex(L.index)
L = L.dropna(subset=["sp1", "sp2"])
bb, se, r2 = ols(L.flow_bn.values, [L.sp, L.sp1, L.sp2, L.ta])
for k, lab in ((1, "באותו חודש"), (2, "חודש קודם"), (3, "לפני חודשיים")):
    rows.append({"מבחן": f"זרם ~ S&P {lab}", "n": len(L), "ערך": bb[k], "±95%": 1.96 * se[k], "R²": r2})
o = pd.DataFrame(rows)
o.round(4).to_csv("data/results/monthly_flow_tests.csv", index=False)
print("\n", o.round(3).to_string(index=False))
