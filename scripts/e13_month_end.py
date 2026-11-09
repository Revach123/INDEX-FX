"""מבחן תזמון: האם השקל זז בסוף החודש לפי כמה ש-S&P זז מתחילת החודש? (עדכון גידור במועדים קבועים, לא סנטימנט)

לכל חודש (10.2017 עד היום), לפי ימי השער היציג של בנק ישראל:
  חלון סוף חודש  = שינוי השער היציג מהיום ה-4 מהסוף עד היום האחרון (3 ימי מסחר)
  S&P מתחילת החודש = מסגירה אחרונה לפני החודש עד סגירה אחרונה לפני תחילת החלון (ידוע לפני החלון)
  בקרות: תנועת S&P ות"א-125 בתוך החלון (סנטימנט באותם ימים), ת"א-125 מתחילת החודש
  רגרסיה: Δדולר בחלון (%) = a + b·S&P מתחילת החודש + בקרות  (שגיאות עמידות HC1)
  גידור צפוי: b < 0 (עלייה ב-S&P -> מכירת דולר בסוף החודש -> דולר יורד)
ביקורת (פלסבו): אותו חלון באמצע החודש (ימים 8–11), עם S&P מתחילת החודש עד לפני החלון.
חזרה: 3 ימי המסחר הראשונים של החודש הבא.  תת-מדגם: סוף רבעון.
מחזורי מסחר (בנק ישראל, יומי): החלפים (swap) של תושבי ישראל שאינם בנקים - נפח החלון ביחס לחציון החודש, מול |S&P מתחילת החודש|.
פלט: data/results/month_end_test.csv
"""
import numpy as np
import pandas as pd

fx = pd.read_csv("data/market/long_usdils.csv", parse_dates=["TIME_PERIOD"]).set_index("TIME_PERIOD").OBS_VALUE.sort_index()
px = pd.read_csv("data/market/long_prices.csv", parse_dates=["Date"]).set_index("Date")
sp, ta = px["^GSPC"].dropna(), px["^TA125.TA"].dropna()
tv = pd.read_csv("data/market/boi_fx_turnover_daily.csv", parse_dates=["TIME_PERIOD"]).set_index("TIME_PERIOD")
swap = tv["WEB_TV_SWAP_IL_OTHR"]


def before(s, dt):
    """הסגירה האחרונה בתאריך מוקדם מ-dt (S&P נסגר אחרי קביעת השער היציג)."""
    x = s[s.index < dt]
    return x.iloc[-1] if len(x) else np.nan


rows = []
days = fx.index
months = days.to_period("M")
for m in months.unique()[1:-1]:
    dm = days[months == m]
    nxt = days[months == m + 1]
    if len(dm) < 15 or len(nxt) < 4:
        continue
    start = dm[0]
    for kind, i0, i1 in (("סוף חודש", -4, -1), ("אמצע חודש", 7, 10)):
        a, b = dm[i0], dm[i1]
        base = before(sp, start)
        r = {"month": str(m), "kind": kind, "q_end": m.month % 3 == 0,
             "fx_win": (fx[b] / fx[a] - 1) * 100,
             "sp_mtd": (before(sp, a) / base - 1) * 100,
             "ta_mtd": (before(ta, a) / before(ta, start) - 1) * 100,
             "sp_win": (before(sp, b) / before(sp, a) - 1) * 100,
             "ta_win": (before(ta, b + pd.Timedelta(days=1)) / before(ta, a + pd.Timedelta(days=1)) - 1) * 100}
        if kind == "סוף חודש":
            r["fx_next"] = (fx[nxt[3]] / fx[b] - 1) * 100
            r["sp_next"] = (before(sp, nxt[3]) / before(sp, b) - 1) * 100
        sw = swap[(swap.index >= dm[0]) & (swap.index <= dm[-1])]
        win = swap[(swap.index > a) & (swap.index <= b)]
        r["swap_ratio"] = win.mean() / sw.median() if len(win) and sw.median() > 0 else np.nan
        rows.append(r)
p = pd.DataFrame(rows).dropna(subset=["fx_win", "sp_mtd", "sp_win", "ta_win", "ta_mtd"])
p.to_csv("data/results/month_end_panel.csv", index=False)


def reg(d, y, xs):
    d = d.dropna(subset=[y] + xs)
    X = np.column_stack([np.ones(len(d))] + [d[x] for x in xs])
    Y = d[y].values
    b = np.linalg.lstsq(X, Y, rcond=None)[0]
    e = Y - X @ b
    n, k = X.shape
    A = np.linalg.inv(X.T @ X)
    V = A @ (X.T * e ** 2) @ X @ A * n / (n - k)
    return b, np.sqrt(np.diag(V)), n


out = []
tests = [
    ("סוף חודש", "fx_win", ["sp_mtd"], lambda d: d[d.kind == "סוף חודש"]),
    ("סוף חודש + בקרות", "fx_win", ["sp_mtd", "ta_mtd", "sp_win", "ta_win"], lambda d: d[d.kind == "סוף חודש"]),
    ("סוף רבעון + בקרות", "fx_win", ["sp_mtd", "ta_mtd", "sp_win", "ta_win"], lambda d: d[(d.kind == "סוף חודש") & d.q_end]),
    ("סוף חודש לא-רבעון + בקרות", "fx_win", ["sp_mtd", "ta_mtd", "sp_win", "ta_win"], lambda d: d[(d.kind == "סוף חודש") & ~d.q_end]),
    ("ביקורת: אמצע חודש + בקרות", "fx_win", ["sp_mtd", "ta_mtd", "sp_win", "ta_win"], lambda d: d[d.kind == "אמצע חודש"]),
    ("חזרה: 3 ימים ראשונים בחודש הבא", "fx_next", ["sp_mtd", "sp_next"], lambda d: d[d.kind == "סוף חודש"]),
]
for lab, y, xs, sel in tests:
    b, se, n = reg(sel(p), y, xs)
    out.append({"מבחן": lab, "n": n, "b (Δדולר % לכל 1% S&P מתחילת החודש)": b[1], "±95%": 1.96 * se[1],
                "t": b[1] / se[1], "b ת\"א מתחילת החודש": b[2] if len(b) > 2 and xs[1] == "ta_mtd" else np.nan})
# מחזורי החלפים: האם הנפח בסוף החודש גבוה יותר כש-S&P זז הרבה?
for kind in ("סוף חודש", "אמצע חודש"):
    d = p[p.kind == kind].dropna(subset=["swap_ratio"]).copy()
    d["abs_sp"] = d.sp_mtd.abs()
    b, se, n = reg(d, "swap_ratio", ["abs_sp"])
    out.append({"מבחן": f"נפח החלפים ({kind}) ביחס לחציון החודש ~ |S&P מתחילת החודש|", "n": n,
                "b (Δדולר % לכל 1% S&P מתחילת החודש)": b[1], "±95%": 1.96 * se[1], "t": b[1] / se[1],
                "b ת\"א מתחילת החודש": np.nan, "נפח ממוצע ביחס לחציון": d.swap_ratio.mean()})
o = pd.DataFrame(out)
o.round(4).to_csv("data/results/month_end_test.csv", index=False)
pd.set_option("display.width", 250)
print(o.round(3).to_string(index=False))
print("חודשים:", p.month.min(), "→", p.month.max())
# הפרש מובהק בין סוף חודש לאמצע חודש? (מאוחד, אינטראקציה, שגיאות מקובצות לפי חודש)
d = p.copy()
d["end"] = (d.kind == "סוף חודש").astype(float)
d["spxend"] = d.sp_mtd * d.end
xs = ["sp_mtd", "spxend", "end", "ta_mtd", "sp_win", "ta_win"]
X = np.column_stack([np.ones(len(d))] + [d[x] for x in xs])
Y = d.fx_win.values
bb = np.linalg.lstsq(X, Y, rcond=None)[0]
e = Y - X @ bb
A = np.linalg.inv(X.T @ X)
S = sum(np.outer(X[g].T @ e[g], X[g].T @ e[g]) for g in d.groupby("month").indices.values())
se = np.sqrt(np.diag(A @ S @ A))
print(f"תוספת סוף חודש מעבר לאמצע חודש: {bb[2]:.3f} ±{1.96*se[2]:.3f} (t={bb[2]/se[2]:.2f})")
o = pd.concat([o, pd.DataFrame([{"מבחן": "תוספת סוף חודש מעבר לאמצע חודש", "n": len(d), "b (Δדולר % לכל 1% S&P מתחילת החודש)": bb[2],
                                 "±95%": 1.96 * se[2], "t": bb[2] / se[2]}])])
o.round(4).to_csv("data/results/month_end_test.csv", index=False)
