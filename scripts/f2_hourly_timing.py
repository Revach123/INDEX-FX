"""מבחן תזמון בנתונים שעתיים (Yahoo, 6.2024-11.2026): באיזו שעה ביממה השקל מגיב ל-S&P, ובהשוואה למטבעות אחרים באותו שעון.

לכל יום מסחר אמריקאי t (שני-חמישי, כדי שלא יהיה סוף שבוע באמצע):
  r_sp = שינוי חוזה S&P (ES) בין 13:00 ל-21:00 UTC (שעות המסחר בניו יורק)
  חלון 1 (אותן שעות, 13:00->21:00):       תגובה מיידית
  חלון 2 (21:00->05:00, לילה/אסיה):
  חלון 3 (05:00->13:00 למחרת, בוקר ישראל ואירופה - כשהגופים בישראל פועלים, לפני פתיחת ניו יורק)
לכל חלון: התחזקות המטבע (%) = a + b·r_sp + c·(שינוי ES באותו חלון).  b בחלונות 2-3 = תגובה *מושהית* לתנועת אתמול.
מוצג לשקל, לממוצע 17 מטבעות אחרים, ולשקל פחות הסל. גם: יורו/שקל.
T2 (סנטימנט): כל התגובה בחלון 1, והשקל כמו האחרים.  T1 (גידור למחרת): תגובה עודפת של השקל בחלון 3.
פלט: data/results/design_B2_hourly.csv
"""
import numpy as np
import pandas as pd

h = pd.read_csv("data/market/design/hourly_yahoo.csv", index_col=0, parse_dates=True).sort_index()
h = h.resample("1h").last().ffill(limit=3)
PEERS = [c for c in h.columns if c not in ("USDILS", "ES", "NQ", "EURILS")]
L = pd.DataFrame({c: (np.log(h[c]) if c.endswith("USD") else -np.log(h[c])) for c in PEERS})
L["ILS"] = -np.log(h.USDILS)
L["ILS_EUR"] = -np.log(h.EURILS)
L["ES"] = np.log(h.ES)
L["NQ"] = np.log(h.NQ)


def at(day, hour, add=0):
    return L.index.get_indexer([day + pd.Timedelta(days=add, hours=hour)])[0]


days = pd.date_range("2024-06-26", L.index.max().normalize() - pd.Timedelta(days=2), freq="D")
rows = []
for d in days:
    if d.dayofweek > 3:
        continue
    idx = [at(d, 13), at(d, 21), at(d, 5, 1), at(d, 13, 1)]
    if min(idx) < 0:
        continue
    v = L.iloc[idx]
    if v[["ILS", "ES"]].isna().any().any():
        continue
    r = {"day": d, "sp": (v.ES.iloc[1] - v.ES.iloc[0]) * 100, "nq_sp": ((v.NQ.iloc[1] - v.NQ.iloc[0]) - (v.ES.iloc[1] - v.ES.iloc[0])) * 100}
    for k, (i, j) in enumerate(((0, 1), (1, 2), (2, 3)), start=1):
        r[f"es{k}"] = (v.ES.iloc[j] - v.ES.iloc[i]) * 100
        r[f"ils{k}"] = (v.ILS.iloc[j] - v.ILS.iloc[i]) * 100
        r[f"ilseur{k}"] = (v.ILS_EUR.iloc[j] - v.ILS_EUR.iloc[i]) * 100
        r[f"bk{k}"] = (v[PEERS].iloc[j] - v[PEERS].iloc[i]).mean() * 100
        for c in PEERS:
            r[f"{c}{k}"] = (v[c].iloc[j] - v[c].iloc[i]) * 100
    rows.append(r)
p = pd.DataFrame(rows).dropna(subset=["sp", "ils1", "ils2", "ils3"])
p = p[p.sp.abs() > 0]


def ols(y, X):
    X = np.column_stack([np.ones(len(y))] + list(X))
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    n, k = X.shape
    A = np.linalg.inv(X.T @ X)
    V = A @ (X.T * e ** 2) @ X @ A * n / (n - k)
    return b, np.sqrt(np.diag(V))


out = []
for k, lab in ((1, "חלון 1: שעות המסחר בניו יורק (מיידי)"), (2, "חלון 2: לילה (21:00–05:00)"), (3, "חלון 3: בוקר ישראל למחרת (05:00–13:00)")):
    row = {"חלון": lab, "ימים": len(p)}
    for y, yl in ((f"ils{k}", "שקל מול דולר"), (f"bk{k}", "ממוצע 17 מטבעות"), (None, "שקל פחות הסל"), (f"ilseur{k}", "שקל מול יורו")):
        yy = (p[f"ils{k}"] - p[f"bk{k}"]).values if y is None else p[y].values
        X = [p.sp.values] if k == 1 else [p.sp.values, p[f"es{k}"].values]
        m = ~np.isnan(yy)
        b, se = ols(yy[m], [x[m] for x in X])
        row[yl], row[yl + " ±"] = b[1], 1.96 * se[1]
    # מיקום השקל בין המטבעות באותו חלון
    bs = []
    for c in PEERS:
        yy = p[f"{c}{k}"].values
        m = ~np.isnan(yy)
        X = [p.sp.values] if k == 1 else [p.sp.values, p[f"es{k}"].values]
        bs.append(ols(yy[m], [x[m] for x in X])[0][1])
    bs = np.array(bs)
    row["דירוג השקל בין 18"] = f"{1 + (bs > row['שקל מול דולר']).sum()}/18"
    row["טווח המטבעות האחרים"] = f"{bs.min():.3f} עד {bs.max():.3f}"
    out.append(row)
o = pd.DataFrame(out)
o.round(4).to_csv("data/results/design_B2_hourly.csv", index=False)
pd.set_option("display.width", 260, "display.max_columns", 30)
print(o.round(3).to_string(index=False))
# נאסד"ק מול S&P: האם השקל מגיב במיוחד לטכנולוגיה? (חלון 1+2+3 יחד: 13:00 -> 13:00 למחרת)
p["ils_all"] = p.ils1 + p.ils2 + p.ils3
p["bk_all"] = p.bk1 + p.bk2 + p.bk3
b, se = ols((p.ils_all - p.bk_all).values, [p.sp.values, p.nq_sp.values, (p.es2 + p.es3).values])
print(f"\nשקל פחות הסל, 24 שעות: S&P {b[1]:.3f} ±{1.96*se[1]:.3f} ; נאסד\"ק מעבר ל-S&P {b[2]:.3f} ±{1.96*se[2]:.3f}  (n={len(p)})")
b, se = ols(p.ils_all.values, [p.sp.values, (p.es2 + p.es3).values])
b2, se2 = ols(p.bk_all.values, [p.sp.values, (p.es2 + p.es3).values])
print(f"24 שעות: שקל {b[1]:.3f} ±{1.96*se[1]:.3f} ; סל {b2[1]:.3f} ±{1.96*se2[1]:.3f}")
print("תקופה:", p.day.min().date(), "→", p.day.max().date())
