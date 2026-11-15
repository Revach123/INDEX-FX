"""בדיקה מחדש, מהתיאוריות: מה מזיז את השקל כש-S&P זז?  מבחנים שבהם התיאוריות חוזות דברים שונים.

תיאוריות:
  T1 גידור מוסדי:   S&P עולה -> המוסדיים מוכרים דולר -> השקל מתחזק. ייחודי לישראל, גדל עם החזקות המוסדיים בחו"ל.
  T2 סנטימנט עולמי: "risk-on" מחזק מטבעות סיכון כולם. לא ייחודי לישראל, מיידי.
  T4 חולשת דולר:    S&P עולה -> הדולר נחלש מול כולם. לא יופיע ביורו/שקל.
מבחנים (נתונים: Yahoo יומי 2005-2026 ל-18 מטבעות; בנק ישראל - שער יציג, החזקות מוסדיים במניות זרות, מחזורים):
  A. מול מטבעות אחרים: r_i = a + c·סל שאר המטבעות + b_i·S&P (שבועי). b_i = תגובה עודפת ל-S&P מעבר לסנטימנט המשותף.
     T2/T4: b_ILS≈0 ולא חריג בין המטבעות.  T1: b_ILS<0... בסימון "התחזקות" >0, חריג, וגדל עם החזקות המוסדיים (אינטראקציה).
  B. תזמון בתוך היממה: קטע א' = יציג(t) -> סגירת ניו יורק(t) [כולל את מסחר S&P]; קטע ב' = סגירת ניו יורק(t) -> יציג(t+1).
     T2: כל התגובה בקטע א'.  T1 (גידור למחרת שלא נצפה מראש): תגובה גם בקטע ב'.
  C. מחזורי מסחר: האם מחזור ההמרות של תושבי ישראל שאינם בנקים עולה ביום שאחרי תזוזה גדולה ב-S&P, יותר מזה של תושבי חוץ?
  D. השהיה: האם S&P של שבועות קודמים מנבא את השקל (התאמה הדרגתית של גידור)?  T2: לא.
  E. האם המוסדיים מוכרים מניות זרות אחרי עלייה (נתון בנק ישראל, 2005-2026, רבעוני)?
פלט: data/results/design_*.csv
"""
import numpy as np
import pandas as pd

Y = pd.read_csv("data/market/design/daily_yahoo.csv", index_col=0, parse_dates=True).sort_index()
PEERS = ["AUDUSD", "NZDUSD", "USDCAD", "USDSEK", "USDNOK", "USDKRW", "USDMXN", "USDPLN", "USDCZK", "USDHUF", "USDZAR", "USDSGD", "USDCLP", "USDTWD",
         "EURUSD", "GBPUSD", "USDCHF", "USDJPY"]


def appr(col):  # התחזקות המטבע המקומי מול הדולר (log)
    s = np.log(Y[col].where(Y[col] > 0))
    return s if col.endswith("USD") else -s


L = pd.DataFrame({c: appr(c) for c in PEERS + ["USDILS"]}).rename(columns={"USDILS": "ILS"})
L["SP"], L["TA"] = np.log(Y.SP), np.log(Y.TA)
W = L.resample("W-FRI").last().diff().mul(100)
W = W[(W.abs() < 15).all(axis=1) | W.isna().any(axis=1)]
cur = [c for c in L.columns if c not in ("SP", "TA")]


def ols(y, X, hac=0):
    X = np.column_stack([np.ones(len(y))] + list(X))
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    n, k = X.shape
    A = np.linalg.inv(X.T @ X)
    xe = X * e[:, None]
    S = xe.T @ xe
    for l in range(1, hac + 1):
        G = xe[l:].T @ xe[:-l]
        S += (1 - l / (hac + 1)) * (G + G.T)
    V = A @ S @ A * n / (n - k)
    return b, np.sqrt(np.diag(V)), 1 - e @ e / ((y - y.mean()) ** 2).sum()


# ---------- A. מול מטבעות אחרים ----------
H = pd.read_csv("data/market/design/boi_exs.csv")
H = H[H.SERIES_CODE == "DSH_INVS_6589_LE_T_IIPF"].set_index("TIME_PERIOD").OBS_VALUE / 1000.0   # מיליארדי דולר
H.index = pd.PeriodIndex(H.index.str.replace("-", ""), freq="Q")
PER = [("2006-2011", "2006", "2011"), ("2012-2017", "2012", "2017"), ("2018-2021", "2018", "2021"), ("2022-2026", "2022", "2026")]
rows = []
for lab, a, b_ in PER + [("2006-2026", "2006", "2026")]:
    w = W.loc[a:b_]
    res = {}
    for c in cur:
        others = [o for o in cur if o != c and o != "ILS"]
        d = pd.concat([w[c], w[others].mean(axis=1).rename("bk"), w.SP], axis=1).dropna()
        if len(d) < 60:
            continue
        b, se, r2 = ols(d[c].values, [d.bk.values, d.SP.values], hac=2)
        b0, se0, _ = ols(d[c].values, [d.SP.values], hac=2)
        res[c] = (b[2], se[2], b0[1], b[1], len(d))
    peers_b = np.array([v[0] for k, v in res.items() if k != "ILS"])
    bi = res["ILS"]
    hq = H[(H.index >= pd.Period(a + "Q1")) & (H.index <= pd.Period(b_ + "Q4"))].mean()
    rows.append({"תקופה": lab, "שבועות": bi[4], "בטא גולמית של השקל ל-S&P": bi[2], "בטא לסל המטבעות": bi[3], "תגובה עודפת של השקל ל-S&P": bi[0], "±95%": 1.96 * bi[1],
                 "ממוצע המטבעות האחרים": peers_b.mean(), "סטיית תקן בין המטבעות": peers_b.std(ddof=1),
                 "דירוג השקל (1=הכי גבוה) מתוך": f"{1 + (peers_b > bi[0]).sum()}/{len(peers_b) + 1}",
                 "החזקות מוסדיים במניות זרות (מיליארד $, ממוצע)": hq})
    if lab == "2022-2026":
        det = pd.DataFrame([{"מטבע": k, "תגובה עודפת ל-S&P": v[0], "±95%": 1.96 * v[1], "בטא גולמית": v[2]} for k, v in res.items()]).sort_values("תגובה עודפת ל-S&P", ascending=False)
        det.round(3).to_csv("data/results/design_A_currencies_2022_2026.csv", index=False)
A = pd.DataFrame(rows)
# אינטראקציה עם החזקות המוסדיים (מנה-תגובה): r_ILS = a + c·סל + b0·S&P + b1·S&P×H
w = W.loc["2006":].copy()
w["bk"] = w[[c for c in cur if c != "ILS"]].mean(axis=1)
hq = H.copy()
hq.index = hq.index.to_timestamp(how="end").normalize()
w["H"] = hq.reindex(w.index.union(hq.index)).sort_index().ffill().shift(1).reindex(w.index) / 100.0   # במאות מיליארדי דולר, בפיגור
d = w[["ILS", "bk", "SP", "H"]].dropna()
b, se, r2 = ols(d.ILS.values, [d.bk.values, d.SP.values, (d.SP * d.H).values, d.H.values], hac=2)
inter = {"b0 (H=0)": b[2], "b0 ±": 1.96 * se[2], "b1 לכל 100 מיליארד $": b[3], "b1 ±": 1.96 * se[3], "n": len(d)}
# פלסבו: אותה אינטראקציה לכל מטבע אחר
pl = []
for c in [x for x in cur if x != "ILS"]:
    others = [o for o in cur if o not in (c, "ILS")]
    dd = pd.concat([w[c], w[others].mean(axis=1).rename("bk"), w.SP, w.H], axis=1).dropna()
    bb, ss, _ = ols(dd[c].values, [dd.bk.values, dd.SP.values, (dd.SP * dd.H).values, dd.H.values], hac=2)
    pl.append(bb[3])
pl = np.array(pl)
inter["פלסבו: b1 במטבעות אחרים - ממוצע"] = pl.mean()
inter["פלסבו: סטיית תקן"] = pl.std(ddof=1)
inter["דירוג b1 של השקל"] = f"{1 + (pl > b[3]).sum()}/{len(pl) + 1}"
A.round(3).to_csv("data/results/design_A_peers.csv", index=False)
pd.set_option("display.width", 250, "display.max_columns", 30)
print("=== A. מול מטבעות אחרים (שבועי; + = המטבע מתחזק כש-S&P עולה, מעבר לסל) ===")
print(A.round(3).to_string(index=False))
print("אינטראקציה עם החזקות המוסדיים:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in inter.items()})

# ---------- B. תזמון בתוך היממה ----------
def boi(c):
    x = pd.read_csv(f"data/market/design/boi_{c}.csv", parse_dates=["TIME_PERIOD"]).set_index("TIME_PERIOD").OBS_VALUE.astype(float).sort_index()
    return x
rowsB = []
for pair, bser, ycol in (("דולר/שקל", boi("USD"), "USDILS"), ("יורו/שקל", boi("EUR"), "EURILS")):
    t = pd.DataFrame({"boi": bser})
    t["yc"] = Y[ycol].reindex(t.index)
    t["boi_next"] = t.boi.shift(-1)
    t["gap"] = (t.index.to_series().shift(-1) - t.index.to_series()).dt.days
    sp = np.log(Y.SP.dropna()).diff().mul(100)
    t["sp"] = sp.reindex(t.index)          # תשואת S&P ביום t (נסגר אחרי היציג של t)
    t["segA"] = np.log(t.yc / t.boi) * 100          # יציג(t) -> סגירת ניו יורק(t)
    t["segB"] = np.log(t.boi_next / t.yc) * 100     # סגירת ניו יורק(t) -> יציג(t+1)
    t["tot"] = np.log(t.boi_next / t.boi) * 100
    t = t.dropna()
    t = t[(t.gap <= 4) & (t.segA.abs() < 4) & (t.segB.abs() < 4)]
    for lab, a, b_ in PER + [("2006-2026", "2006", "2026")]:
        d = t.loc[a:b_]
        out = {"צמד": pair, "תקופה": lab, "ימים": len(d)}
        for seg, sl in (("segA", "קטע א' (בזמן מסחר S&P)"), ("segB", "קטע ב' (לילה + בוקר ישראל)"), ("tot", "סה\"כ יציג ליציג")):
            b, se, _ = ols(d[seg].values, [d.sp.values])
            out[sl], out[sl + " ±"] = b[1], 1.96 * se[1]
        rowsB.append(out)
B = pd.DataFrame(rowsB)
B.round(4).to_csv("data/results/design_B_timing.csv", index=False)
print("\n=== B. תזמון: שינוי השער (%) לכל 1% ב-S&P של אותו יום (− = השקל מתחזק) ===")
print(B.round(3).to_string(index=False))

# ---------- C. מחזורי מסחר ----------
T = pd.read_csv("data/market/design/boi_turnover_daily_all.csv", index_col=0, parse_dates=True).sort_index()
usd = boi("USD")
sp_abs = sp.abs()
rowsC = []
for col, lab in (("WEB_TV_CONV_IL_OTHR", "המרות – תושבי ישראל שאינם בנקים"), ("WEB_TV_CONV_NR", "המרות – תושבי חוץ"),
                 ("WEB_TV_SWAP_IL_OTHR", "החלפי מט\"ח – תושבי ישראל שאינם בנקים"), ("WEB_TV_SWAP_NR", "החלפי מט\"ח – תושבי חוץ")):
    v = T[col].where(T[col] > 0)
    y = np.log(v / v.rolling(60, min_periods=30).median().shift(1))
    d = pd.DataFrame({"y": y})
    spd = sp_abs.reindex(sp_abs.index.union(d.index)).sort_index()
    d["sp_prev"] = sp_abs.shift(0).reindex(d.index.union(sp_abs.index)).sort_index().ffill().shift(1).reindex(d.index)   # |S&P| של יום המסחר האמריקאי האחרון שלפני t
    d["fx_abs"] = (np.log(usd).diff().abs() * 100).reindex(d.index)
    d["y1"] = d.y.shift(1)
    for lab2, a, b_ in (("2012-2017", "2012", "2017"), ("2018-2026", "2018", "2026")):
        dd = d.loc[a:b_].dropna()
        b, se, _ = ols(dd.y.values, [dd.sp_prev.values, dd.fx_abs.values, dd.y1.values], hac=5)
        rowsC.append({"סדרה": lab, "תקופה": lab2, "ימים": len(dd), "עליית מחזור (%) לכל 1% תזוזה ב-S&P ביום הקודם": b[1] * 100, "±95%": 1.96 * se[1] * 100,
                      "לכל 1% תזוזה בשער באותו יום": b[2] * 100})
C = pd.DataFrame(rowsC)
C.round(2).to_csv("data/results/design_C_turnover.csv", index=False)
print("\n=== C. מחזורים ===")
print(C.round(2).to_string(index=False))

# ---------- D. השהיה ----------
rowsD = []
w = W.copy()
w["bk"] = w[[c for c in cur if c != "ILS"]].mean(axis=1)
for k in range(1, 5):
    w[f"sp_l{k}"] = w.SP.shift(k)
for lab, a, b_ in PER + [("2006-2026", "2006", "2026")]:
    d = w.loc[a:b_, ["ILS", "bk", "SP"] + [f"sp_l{k}" for k in range(1, 5)]].dropna()
    b, se, _ = ols(d.ILS.values, [d.bk.values, d.SP.values] + [d[f"sp_l{k}"].values for k in range(1, 5)], hac=4)
    cum = b[3:7].sum()
    X = np.column_stack([np.ones(len(d)), d.bk, d.SP] + [d[f"sp_l{k}"] for k in range(1, 5)])
    rowsD.append({"תקופה": lab, "שבועות": len(d), "אותו שבוע": b[2], "±": 1.96 * se[2], "שבוע קודם": b[3], "± ": 1.96 * se[3],
                  "סכום 4 שבועות קודמים": cum, "±  ": 1.96 * np.sqrt((se[3:7] ** 2).sum())})
D = pd.DataFrame(rowsD)
D.round(4).to_csv("data/results/design_D_lags.csv", index=False)
print("\n=== D. השהיה: התחזקות השקל (%) לכל 1% ב-S&P, מעבר לסל המטבעות ===")
print(D.round(3).to_string(index=False))

# ---------- E. האם המוסדיים מוכרים מניות זרות אחרי עלייה ----------
X = pd.read_csv("data/market/design/boi_exs.csv")
g = X.pivot_table(index="TIME_PERIOD", columns="SERIES_CODE", values="OBS_VALUE")
g.index = pd.PeriodIndex(g.index.str.replace("-", ""), freq="Q")
q = pd.DataFrame({"flow": g["DSH_INVS_6589_T_T_IIPF"], "hold": g["DSH_INVS_6589_LE_T_IIPF"]})
spq = np.log(Y.SP.dropna()).resample("QE").last().diff().mul(100)
spq.index = spq.index.to_period("Q")
q["sp"], q["sp1"] = spq, spq.shift(1)
q["y"] = q.flow / q.hold.shift(1) * 100
rowsE = []
for lab, a, b_ in (("2006-2015", "2006Q1", "2015Q4"), ("2016-2026", "2016Q1", "2026Q4"), ("2006-2026", "2006Q1", "2026Q4")):
    d = q.loc[a:b_].dropna()
    b, se, r2 = ols(d.y.values, [d.sp.values, d.sp1.values], hac=2)
    rowsE.append({"תקופה": lab, "רבעונים": len(d), "קנייה נטו (% מההחזקות) לכל 1% S&P באותו רבעון": b[1], "±": 1.96 * se[1], "רבעון קודם": b[2], "± ": 1.96 * se[2],
                  "קנייה ממוצעת לרבעון (% מההחזקות)": d.y.mean(), "החזקות בסוף התקופה (מיליארד $)": d.hold.iloc[-1] / 1000})
E_ = pd.DataFrame(rowsE)
E_.round(3).to_csv("data/results/design_E_foreign_equity_flows.csv", index=False)
print("\n=== E. קניית מניות זרות ע\"י המוסדיים (בנק ישראל) ===")
print(E_.round(3).to_string(index=False))
pd.Series(inter).to_csv("data/results/design_A_interaction.csv")

# ---------- D2. פלסבו להשהיה: אותו מבחן לכל מטבע (האם רק השקל "נגרר" אחרי S&P של השבוע הקודם?) ----------
rowsP = []
for lab, a, b_ in PER:
    w2 = W.loc[a:b_]
    res = {}
    for c in cur:
        others = [o for o in cur if o not in (c, "ILS")]
        d = pd.concat([w2[c], w2[others].mean(axis=1).rename("bk"), w2.SP, w2.SP.shift(1).rename("l1")], axis=1).dropna()
        if len(d) < 60:
            continue
        b, se, _ = ols(d[c].values, [d.bk.values, d.SP.values, d.l1.values], hac=4)
        res[c] = (b[3], se[3])
    pb = np.array([v[0] for k, v in res.items() if k != "ILS"])
    rowsP.append({"תקופה": lab, "שקל: מקדם S&P של שבוע קודם": res["ILS"][0], "±": 1.96 * res["ILS"][1], "ממוצע האחרים": pb.mean(), "סטיית תקן בין האחרים": pb.std(ddof=1),
                  "מקסימום אצל האחרים": pb.max(), "דירוג השקל": f"{1 + (pb > res['ILS'][0]).sum()}/{len(pb) + 1}"})
P = pd.DataFrame(rowsP)
P.round(4).to_csv("data/results/design_D2_lag_placebo.csv", index=False)
print("\n=== D2. פלסבו להשהיה ===")
print(P.round(3).to_string(index=False))
print(pd.read_csv("data/results/design_A_currencies_2022_2026.csv").head(6).to_string(index=False))
