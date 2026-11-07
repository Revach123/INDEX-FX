"""האם הגופים מאזנים את חשיפת המט"ח חזרה ליעד? בדיקה על כל הדוחות הרבעוניים (2024Q1 ->).

לכל מסלול ושני רבעונים עוקבים q0 -> q1:
  FX0, FX1        חשיפת מט"ח נטו בפועל (ספוט במט"ח + פורוורדים בסימן), כשבר מהנכסים - מהדוחות
  U_phys, U_syn   חשיפה למניות חו"ל ב-q0: פיזי (מניות/קרנות במט"ח) / סינתטי (החלפים וחוזים, a6)
  r_fr            תשואת מניות חו"ל בדולר ברבעון (תמהיל ארה"ב/שאר העולם של המסלול)
  e               שינוי USD/ILS (בנק ישראל) ברבעון
  R               תשואת המסלול בפועל ברבעון (MASLULIM/returns/monthly_totals.csv)
"פסיבי" (בלי שום מסחר במט"ח):  FXp = [FX0 + (U_phys + U_syn)·r_fr]·(1+e) / (1+R)
רגרסיה: (FX1 − FX0) = a + β·(FXp − FX0).  β≈0: איזון מלא ליעד; β≈1: לא מאזנים (החשיפה זזה עם השוק).
גרסה נוספת: רק הפיזי נחשב רווח דולרי (הנחת המאמר) - FXp_article. איזו מהשתיים מסבירה טוב יותר את מה שקרה בפועל.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from a2_classify_exposure import classify, explode_fx_forwards  # noqa: E402
from a3_aggregate_validate import track_totals  # noqa: E402
from d2_article_scenario import is_us  # noqa: E402

KEY = ["legal_id", "track"]


def quarter_state(q: str) -> pd.DataFrame:
    df = classify(pd.read_csv(f"data/history/positions_{q}.csv.gz", low_memory=False))
    df["track"] = pd.to_numeric(df.track, errors="coerce")
    tt = track_totals(df)
    tt["track"] = pd.to_numeric(tt.track, errors="coerce")
    fw, _ = explode_fx_forwards(df)
    fw["track"] = pd.to_numeric(fw.track, errors="coerce")
    spot = df.groupby(KEY).fx_exposure_k.sum().rename("fx_spot_k")
    fwd = fw.groupby(KEY).fx_exposure_k.sum().rename("fx_fwd_k")
    ph = df[((df.form.isin(["STOCK_DIRECT", "WARRANT"]) & df.il_abroad.eq("חו\"ל")) |
             (df.form.isin(["ETF", "MUTUAL_FUND"]) & df.asset_class.eq("equity"))) & df.fx_route.isin(["direct_ccy", "embedded_unhedged"])].copy()
    ph["us"] = ph.country.astype(str).str.contains("ארצות הברית|ארה").values | np.array([is_us(f"{a} {b}") for a, b in zip(ph.index_label, ph.fund_class)])
    phys = ph.groupby(KEY).fair_value_k.sum().rename("u_phys_k")
    phys_us = (ph.fair_value_k * ph.us).groupby([ph.legal_id, ph.track]).sum().rename("u_phys_us_k")
    out = tt.set_index(KEY)[["total_k", "report_date", "system"]].join([spot, fwd, phys, phys_us])
    p = Path(f"data/history/deriv_{q}.csv.gz")
    if p.exists():
        dx = pd.read_csv(p, low_memory=False)
        dx["legal_id"] = dx.legal_id.astype(int)
        dx["track"] = pd.to_numeric(dx.track, errors="coerce")
        dx = dx[(dx.equity == True) & ~(dx.country.eq("ישראל") | (dx.ccy.eq("ILS") & dx.leg2_ccy.fillna("ILS").eq("ILS")))].copy()  # noqa: E712
        dx["exp_k"] = dx.ratio * dx.total_k
        dx["us"] = [is_us(f"{a} {b} {c}") for a, b, c in zip(dx.ticker, dx.name, dx.root)]
        out = out.join(dx.groupby(KEY).exp_k.sum().rename("u_syn_k"))
        out = out.join((dx.exp_k * dx.us).groupby([dx.legal_id, dx.track]).sum().rename("u_syn_us_k"))
    out = out.fillna({"fx_spot_k": 0, "fx_fwd_k": 0, "u_phys_k": 0, "u_phys_us_k": 0, "u_syn_k": 0, "u_syn_us_k": 0})
    out["FX"] = (out.fx_spot_k + out.fx_fwd_k) / out.total_k
    out["q"] = q
    return out.reset_index()


def main():
    qs = sorted(p.stem.replace("positions_", "") for p in Path("data/history").glob("positions_*.csv.gz"))
    st = pd.concat([quarter_state(q) for q in qs])
    st.to_csv("data/history/track_quarter_state.csv.gz", index=False, compression="gzip")
    px = pd.read_csv("data/market/prices.csv", parse_dates=["date"]).pivot(index="date", columns="symbol", values="close")
    row = 0.8 * px["VEA"].pct_change() + 0.2 * px["EEM"].pct_change()
    rowlvl = (1 + row.fillna(0)).cumprod()
    fx = pd.read_csv("data/market/boi_usdils.csv", parse_dates=["date"]).set_index("date").value
    mr = pd.read_csv("/home/user/revach123/maslulim/returns/monthly_totals.csv")
    mr["ym"] = pd.PeriodIndex(mr.ym, freq="M")
    rows = []
    for q0, q1 in zip(qs[:-1], qs[1:]):
        a = st[st.q == q0].set_index(KEY)
        b = st[st.q == q1].set_index(KEY)
        j = a.join(b[["FX", "report_date", "total_k"]], rsuffix="1", how="inner")
        d0, d1 = pd.Timestamp(j.report_date.iloc[0]), pd.Timestamp(j.report_date1.iloc[0])
        r_us = px["^GSPC"].asof(d1) / px["^GSPC"].asof(d0) - 1
        r_row = rowlvl.asof(d1) / rowlvl.asof(d0) - 1
        e = fx.asof(d1) / fx.asof(d0) - 1
        months = pd.period_range(d0.to_period("M") + 1, d1.to_period("M"), freq="M")
        R = (mr[mr.ym.isin(months)].assign(g=lambda x: 1 + x.total / 100)
             .groupby(["legal_id", "track_no"]).g.prod().rename("R1") - 1)
        R.index = R.index.set_names(KEY)
        R = R[mr[mr.ym.isin(months)].groupby(["legal_id", "track_no"]).size().reindex(R.index).values == len(months)]
        j = j.join(R, how="inner")
        u = j.u_phys_k + j.u_syn_k
        r_phys = np.where(j.u_phys_k > 0, (j.u_phys_us_k * r_us + (j.u_phys_k - j.u_phys_us_k) * r_row) / j.u_phys_k.replace(0, np.nan), 0)
        r_syn = np.where(j.u_syn_k > 0, (j.u_syn_us_k * r_us + (j.u_syn_k - j.u_syn_us_k) * r_row) / j.u_syn_k.replace(0, np.nan), 0)
        g_phys = j.u_phys_k / j.total_k * np.nan_to_num(r_phys)
        g_syn = j.u_syn_k / j.total_k * np.nan_to_num(r_syn)
        j["FXp"] = (j.FX + g_phys + g_syn) * (1 + e) / (1 + j.R1)
        j["FXp_article"] = (j.FX + g_phys) * (1 + e) / (1 + j.R1)
        j["q0"], j["q1"], j["r_us"], j["r_row"], j["e"] = q0, q1, r_us, r_row, e
        rows.append(j.reset_index())
    p = pd.concat(rows)
    p = p[(p.total_k > 1e5) & p.FX.between(-0.2, 1.5) & p.FX1.between(-0.2, 1.5) & (p.total_k1 / p.total_k).between(0.5, 2)]
    p.to_csv("data/results/rebalancing_panel.csv", index=False)
    print(f"[d3] {len(p)} תצפיות מסלול-רבעון, {p.q0.nunique()} מעברים, {p.groupby(KEY).ngroups} מסלולים")
    res = []
    for lab, col in (("כל הרווח הזר בדולר (מהדוחות)", "FXp"), ("רק הפיזי בדולר (הנחת המאמר)", "FXp_article")):
        x = (p[col] - p.FX).values
        y = (p.FX1 - p.FX).values
        w = p.total_k.values
        # אפקט קבוע לכל מעבר רבעון (שינויי יעד שנתיים, אירועים) - משתני דמה לכל מעבר
        X = np.column_stack([np.ones_like(x), x] + [(p.q0 == q).values.astype(float) for q in sorted(p.q0.unique())[1:]])
        W = np.sqrt(w)
        b = np.linalg.lstsq(X * W[:, None], y * W, rcond=None)[0]
        res_ = (y - X @ b)
        s2 = np.sum(w * res_**2) / (w.sum() * (len(y) - X.shape[1]) / len(y))
        cov = s2 * np.linalg.inv((X * w[:, None]).T @ X)
        res.append({"מדד הסחיפה": lab, "β (0=איזון מלא, 1=אין איזון)": b[1], "t (מול 0)": b[1] / np.sqrt(cov[1, 1]),
                    "t (מול 1)": (b[1] - 1) / np.sqrt(cov[1, 1]),
                    "R²": 1 - np.sum(w * res_**2) / np.sum(w * (y - np.average(y, weights=w))**2),
                    "סחיפה פסיבית ממוצעת |pp|": np.average(np.abs(x), weights=w) * 100,
                    "שינוי בפועל ממוצע |pp|": np.average(np.abs(y), weights=w) * 100})
    r = pd.DataFrame(res).round(3)
    r.to_csv("data/results/rebalancing_test.csv", index=False)
    print(r.to_string(index=False))
    q = p.groupby("q0").apply(lambda d: pd.Series({"r_us": d.r_us.iloc[0], "e": d.e.iloc[0],
                                                     "סחיפה פסיבית (משוקלל, pp)": np.average(d.FXp - d.FX, weights=d.total_k) * 100,
                                                     "שינוי בפועל (משוקלל, pp)": np.average(d.FX1 - d.FX, weights=d.total_k) * 100}), include_groups=False).round(2)
    q.to_csv("data/results/rebalancing_by_quarter.csv")
    print(q.to_string())


if __name__ == "__main__":
    main()
