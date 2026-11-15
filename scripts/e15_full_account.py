"""חשבון מקורות-ושימושים מלא לכל מסלול ורבעון - כל הנכסים (שקליים ודולריים), לא רק מט"ח.

שימושים (קנייה + / מכירה −, אלפי ש"ח, במחירי q1; שינוי כמות בלבד - שערוך לא נספר):
  eq_for      מניות/קרנות סל/נאמנות על מניות, נקובות במט"ח
  eq_for_ils  קרנות ישראליות (נקובות ש"ח) על מניות חו"ל
  eq_il       מניות וקרנות מניות בישראל (ש"ח)
  bond_fx / bond_ils   אג"ח, מק"מ, מובנים, קרנות אג"ח
  cash_fx / cash_ils   מזומן ופיקדונות (ללא בטחונות) - Δ יתרה
  coll_fx / coll_ils   בטחונות - Δ יתרה
  alt_fx / alt_ils     קרנות השקעה פרטיות, הלוואות, נדל"ן, אחר - Δ יתרה (כולל שערוך! מסומן)
מקורות (תזרים נכנס +):
  dep         הפקדות נטו (data.gov)
  eqd_settle  תזרים מהחלפים/חוזים על מניות חו"ל = שערוך (e1b) − Δ רווח צבור
  fwd_settle  תזרים מפורוורדים על מט"ח = רווח מתנועת השער (נוציונל q0 × Δשער) − Δ שווי הוגן של הפורוורדים
  oth_deriv   −Δ שווי הוגן של שאר הנגזרים (אופציות, חוזים על מדדי ישראל, החלפי ריבית) - לא משוערך, מסומן
חשיפה סינתטית: syn_trade = Δ חשיפת נגזרי מניות חו"ל פחות השערוך (הוספה/הקטנה של חוזים בפועל).
בדיקת זהות: Σ שימושים − Σ מקורות = הכנסות שוטפות (ריבית/דיבידנד) + שערוך ב-alt + שגיאה.  מדווח.
פלט: data/flows/full_account.csv.gz, data/results/full_account_quarterly.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from a2_classify_exposure import explode_fx_forwards, num  # noqa: E402
from e1_track_fx_flows import KEY, load  # noqa: E402

SEC = ["STOCK_DIRECT", "BOND", "ETF", "MUTUAL_FUND", "WARRANT", "STRUCTURED"]
BAL = ["CASH", "LOAN", "PRIVATE_FUND", "OTHER", "REAL_ESTATE"]
DER = ["FUTURE", "OPTION", "SWAP_EQ_UNFUNDED", "SWAP_EQ_FUNDED", "FX_FWD_UNFUNDED", "FX_FWD_FUNDED", "SWAP_RATE", "SWAP_OTHER"]


def prep(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["is_fx"] = d.fx_route.eq("direct_ccy")
    d["rate"] = np.where(d.is_fx, pd.to_numeric(d.fx_rate, errors="coerce"), 1.0)
    eqf = d.form.isin(["STOCK_DIRECT", "WARRANT", "ETF", "MUTUAL_FUND"]) & d.asset_class.eq("equity")
    sfx = np.where(d.is_fx, "_fx", "_ils")
    b = pd.Series("alt", index=d.index) + sfx
    b[d.form.isin(SEC)] = pd.Series("bond", index=d.index)[d.form.isin(SEC)] + pd.Series(sfx, index=d.index)[d.form.isin(SEC)]
    b[eqf & d.is_fx] = "eq_for"
    b[eqf & ~d.is_fx & d.form.isin(["ETF", "MUTUAL_FUND"]) & d.geo.eq("ABROAD")] = "eq_for_ils"
    b[eqf & ~d.is_fx & ~(d.form.isin(["ETF", "MUTUAL_FUND"]) & d.geo.eq("ABROAD"))] = "eq_il"
    cash = d.form.eq("CASH")
    coll = cash & d.main_attr.astype(str).str.contains("בטחונות")
    b[cash & ~coll] = pd.Series("cash", index=d.index)[cash & ~coll] + pd.Series(sfx, index=d.index)[cash & ~coll]
    b[coll] = pd.Series("coll", index=d.index)[coll] + pd.Series(sfx, index=d.index)[coll]
    d["bucket"] = b
    return d


USD = pd.read_csv("data/market/long_usdils.csv", parse_dates=["TIME_PERIOD"]).set_index("TIME_PERIOD").OBS_VALUE.sort_index()


def deals(d: pd.DataFrame) -> pd.DataFrame:
    """כל עסקת פורוורד: שתי הרגליים בש"ח לפי שער הדוח, שווי (סכום הרגליים), תאריך סיום. רק עסקאות עקביות וחתומות."""
    x = d[d.form.isin(["FX_FWD_UNFUNDED", "FX_FWD_FUNDED"])].copy()
    rates = d[d.ccy.astype(str).str.match(r"^[A-Z]{3}$") & num(d.fx_rate).gt(0)].groupby(["file", "ccy"]).fx_rate.apply(lambda v: num(v).median())
    for n in (1, 2):
        c = x[f"leg{n}_ccy"].astype(str).replace({"NIS": "ILS"})
        fb = pd.Series([1.0 if cc == "ILS" else rates.get((f, cc), np.nan) for f, cc in zip(x.file, c)], index=x.index)
        r = np.where((c == "JPY") & (fb > 0.5), fb / 100, fb)     # שער הדוח (ספוט) - אחיד בין הרבעונים
        x[f"c{n}"], x[f"n{n}"], x[f"v{n}"] = c, num(x[f"leg{n}_nominal"]), num(x[f"leg{n}_nominal"]) * r / 1000.0
    gap = (x.v1 + x.v2).abs() / np.maximum(x.v1.abs(), x.v2.abs()).replace(0, np.nan)
    ok = (gap.fillna(1.0) <= 0.5) & ~((np.sign(x.v1) == np.sign(x.v2)) & x.v1.ne(0) & x.v2.ne(0))
    x = x[ok]
    x["mtm"] = x.v1 + x.v2
    x["end"] = pd.to_datetime(x.swap_end, errors="coerce")
    return x


def fwd_cash(a: pd.DataFrame, b: pd.DataFrame, fx0, fx1) -> pd.DataFrame:
    """תזרים סילוק של פורוורדים שהיו בספר ב-q0 והסתיימו עד q1: רגל שקלית + רגל מט"ח × שער ביום הסיום.
    דולר: שער יציג ביום הסיום (בנק ישראל). מטבע אחר: אינטרפולציה ליניארית בין שער q0 לשער q1 (מסומן)."""
    da, db = deals(a), deals(b)
    d0, d1 = pd.to_datetime(a.report_date.iloc[0]), pd.to_datetime(b.report_date.iloc[0])
    m = da[(da.end > d0) & (da.end <= d1)].copy()
    frac = ((m.end - d0).dt.days / max((d1 - d0).days, 1)).clip(0, 1)
    usd_at = pd.Series(USD.reindex(USD.index.union(m.end.dropna().unique())).ffill().reindex(m.end).values, index=m.index)
    cash = pd.Series(0.0, index=m.index)
    for n in (1, 2):
        c = m[f"c{n}"]
        r0, r1 = c.map(fx0), c.map(fx1)
        s = r0 + (r1 - r0) * frac
        s = np.where(c.eq("USD"), usd_at.fillna(pd.Series(s, index=m.index)), s)
        s = np.where(c.eq("ILS"), 1.0, s)
        cash += (m[f"n{n}"] * s / 1000.0).fillna(0.0)
    m["cash"] = cash
    out = pd.concat([m.groupby(KEY).cash.sum().rename("fwd_cash"), da.groupby(KEY).mtm.sum().rename("fwd_mtm0"),
                     db.groupby(KEY).mtm.sum().rename("fwd_mtm1"),
                     m.groupby(KEY).v1.apply(lambda v: v.abs().sum()).rename("fwd_matured_k")], axis=1)
    return out


def account(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    fx0 = a[a.is_fx].groupby("fx_ccy").rate.median()
    fx1 = b[b.is_fx].groupby("fx_ccy").rate.median()
    out = []
    # ני"ע עם מספר נייר - שינוי כמות במחיר q1
    k = KEY + ["sheet", "sid"]
    sa = a[a.form.isin(SEC) & a.sec_id.notna()]
    sb = b[b.form.isin(SEC) & b.sec_id.notna()]
    ga = sa.groupby(k).agg(v0=("fair_value_k", "sum"), u0=("units", "sum"), r0=("rate", "median"), bucket=("bucket", "first"),
                           ccy=("fx_ccy", "first"), fxa=("is_fx", "first"))
    gb = sb.groupby(k).agg(v1=("fair_value_k", "sum"), u1=("units", "sum"), r1=("rate", "median"), bucket1=("bucket", "first"))
    m = ga.join(gb, how="outer")
    both = m.v0.notna() & m.v1.notna()
    pu0 = (m.v0 / m.r0) / m.u0.replace(0, np.nan)
    pu1 = (m.v1 / m.r1) / m.u1.replace(0, np.nan)
    ok = both & m.u1.abs().gt(0) & m.u0.notna() & (pu1 / pu0).abs().between(0.5, 2.0)
    flow = pd.Series(0.0, index=m.index)
    flow[ok] = m.v1[ok] * (m.u1[ok] - m.u0[ok]) / m.u1[ok]
    new = m.v0.isna() & m.v1.notna()
    flow[new] = m.v1[new]
    gone = m.v0.notna() & m.v1.isna()
    adj = np.where(m.fxa[gone].astype(bool), m.ccy[gone].map(fx1) / m.r0[gone], 1.0)
    flow[gone] = -m.v0[gone] * pd.Series(adj, index=m.index[gone]).fillna(1.0)
    m["flow"] = flow
    m["unres"] = np.where(both & ~ok, m.v1.abs(), 0.0)
    m["bucket"] = m.bucket1.fillna(m.bucket)
    s = m.reset_index().groupby(KEY + ["bucket"]).agg(flow=("flow", "sum"), unres=("unres", "sum")).reset_index()
    out.append(s)
    # יתרות (מזומן, בטחונות, הלוואות, קרנות פרטיות, אחר + ני"ע בלי מספר) - Δ יתרה במטבע × שער q1
    def bal(d):
        x = d[d.form.isin(BAL) | (d.form.isin(SEC) & d.sec_id.isna())]
        return (x.fair_value_k / x.rate).groupby([x.legal_id, x.track, x.bucket, x.fx_ccy]).sum()
    j = pd.concat([bal(a).rename("c0"), bal(b).rename("c1")], axis=1).fillna(0.0)
    j.index = j.index.set_names(KEY + ["bucket", "ccy"])
    j = j.reset_index()
    j["flow"] = (j.c1 - j.c0) * np.where(j.ccy.eq("ILS"), 1.0, j.ccy.map(fx1))
    j["flow"] = j.flow.fillna(0.0)
    j["unres"] = 0.0
    out.append(j.groupby(KEY + ["bucket"])[["flow", "unres"]].sum().reset_index())
    r = pd.concat(out).groupby(KEY + ["bucket"])[["flow", "unres"]].sum().reset_index()
    w = r.pivot_table(index=KEY, columns="bucket", values="flow", aggfunc="sum").fillna(0.0)
    w["unres_sec"] = r.groupby(KEY).unres.sum()
    # פורוורדים: רווח מתנועת השער על הנוציונל של q0, ושינוי השווי ההוגן
    fa, _ = explode_fx_forwards(a)
    fb, _ = explode_fx_forwards(b)
    ta, tb = pd.to_numeric(fa.track, errors="coerce"), pd.to_numeric(fb.track, errors="coerce")
    n0 = fa.nominal.groupby([fa.legal_id, ta, fa.ccy]).sum()
    n0.index = n0.index.set_names(KEY + ["ccy"])
    n0 = n0.reset_index(name="n0")
    n0["pnl"] = n0.n0 * (n0.ccy.map(fx1) - n0.ccy.map(fx0)) / 1000.0
    n0["fwd_not0"] = n0.n0 * n0.ccy.map(fx0) / 1000.0
    w = w.join(n0.groupby(KEY)[["pnl", "fwd_not0"]].sum().rename(columns={"pnl": "fwd_pnl"}), how="left")
    n1 = fb.nominal.groupby([fb.legal_id, tb, fb.ccy]).sum()
    n1.index = n1.index.set_names(KEY + ["ccy"])
    n1 = n1.reset_index(name="n1")
    n1["v"] = n1.n1 * n1.ccy.map(fx1) / 1000.0
    w = w.join(n1.groupby(KEY).v.sum().rename("fwd_not1_at1"), how="left")
    n0["v"] = n0.n0 * n0.ccy.map(fx1) / 1000.0
    w = w.join(n0.groupby(KEY).v.sum().rename("fwd_not0_at1"), how="left")
    w = w.join(fwd_cash(a, b, fx0, fx1), how="left")
    def fv(d, forms):
        x = d[d.form.isin(forms)]
        return x.groupby(KEY).fair_value_k.sum()
    FW = ["FX_FWD_UNFUNDED", "FX_FWD_FUNDED"]
    w = w.join((fv(b, FW).reindex(w.index).fillna(0) - fv(a, FW).reindex(w.index).fillna(0)).rename("fwd_dfv"))
    w = w.join((fv(b, DER).reindex(w.index).fillna(0) - fv(a, DER).reindex(w.index).fillna(0)).rename("der_dfv"))
    return w.fillna({c: 0.0 for c in w.columns if c not in ("fwd_cash",)}).reset_index()


def main():
    base = pd.read_csv("data/flows/track_fx_flows.csv.gz")
    keep = base[KEY + ["q0"]].drop_duplicates()
    mt = base[base.component == "derivatives_mtm_change"].groupby(KEY + ["q0"]).flow.sum().rename("eqd_dmtm").reset_index()
    val = pd.read_csv("data/flows/derivative_valuation.csv.gz")[KEY + ["q0", "valuation_k"]]
    st = pd.read_csv("data/history/track_quarter_state.csv.gz")
    qs = sorted(keep.q0.unique()) + ["2026Q2"]
    qs = sorted(set(qs))
    res, cache = [], {}
    for q0, q1 in zip(qs[:-1], qs[1:]):
        a = cache.pop(q0) if q0 in cache else prep(load(q0))
        b = prep(load(q1))
        cache[q1] = b
        w = account(a, b)
        w["q0"], w["q1"] = q0, q1
        w = w.merge(keep[keep.q0 == q0], on=KEY + ["q0"], how="inner")
        res.append(w)
        print(f"[e15] {q0}->{q1}: {len(w)} מסלולים", flush=True)
    r = pd.concat(res, ignore_index=True)
    r = r.merge(mt, on=KEY + ["q0"], how="left").merge(val, on=KEY + ["q0"], how="left").fillna({"eqd_dmtm": 0.0, "valuation_k": 0.0})
    s0 = st.rename(columns={"q": "q0", "u_syn_k": "syn0", "total_k": "A0", "u_phys_k": "phys0"})[KEY + ["q0", "syn0", "A0", "phys0"]]
    s1 = st.rename(columns={"q": "q1", "u_syn_k": "syn1", "total_k": "A1"})[KEY + ["q1", "syn1", "A1"]]
    r = r.merge(s0, on=KEY + ["q0"], how="left").merge(s1, on=KEY + ["q1"], how="left")
    fp = pd.read_csv("data/flows/flow_panel.csv.gz")[KEY + ["q0", "gain_phys", "gain_syn", "R1"]]
    r = r.merge(fp, on=KEY + ["q0"], how="left")
    # הפקדות נטו לכל המסלולים (data.gov): 3 החודשים שאחרי q0; מספר המסלול = FUND_ID
    dg = pd.read_csv("data/datagov/monthly.csv.gz", low_memory=False, usecols=["FUND_ID", "REPORT_PERIOD", "NET_MONTHLY_DEPOSITS", "MONTHLY_YIELD", "TOTAL_ASSETS"])
    dg["m"] = pd.PeriodIndex(dg.REPORT_PERIOD.astype(int).astype(str), freq="M")
    dg["q0"] = (dg.m - 3).dt.asfreq("Q").astype(str)
    dg["dep"] = pd.to_numeric(dg.NET_MONTHLY_DEPOSITS, errors="coerce") * 1000.0
    dd = dg.groupby(["FUND_ID", "q0"]).agg(dep=("dep", lambda v: v.sum(min_count=3)), dep_n=("dep", "count")).reset_index().rename(columns={"FUND_ID": "track"})
    dd["track"] = dd.track.astype(float)
    r = r.merge(dd, on=["track", "q0"], how="left")
    r["eqd_settle"] = r.valuation_k - r.eqd_dmtm
    r["fwd_settle"] = r.fwd_cash.fillna(0.0)
    r["fwd_settle_alt"] = r.fwd_pnl - (r.fwd_mtm1.fillna(0.0) - r.fwd_mtm0.fillna(0.0))   # אומדן חלופי: רווח על נוציונל q0 פחות Δ שווי
    r["oth_deriv"] = -(r.der_dfv - r.fwd_dfv - r.eqd_dmtm)
    r["syn_trade"] = r.syn1 - r.syn0 - r.valuation_k
    r["fwd_trade"] = r.fwd_not1_at1 - r.fwd_not0_at1
    r.to_csv("data/flows/full_account.csv.gz", index=False, compression="gzip")
    USES = ["eq_for", "eq_for_ils", "eq_il", "bond_fx", "bond_ils", "cash_fx", "cash_ils", "coll_fx", "coll_ils", "alt_fx", "alt_ils"]
    SRC = ["dep", "eqd_settle", "fwd_settle", "oth_deriv"]
    for c in USES:
        if c not in r:
            r[c] = 0.0
    q = r.groupby("q1")[USES + SRC + ["syn_trade", "fwd_trade", "valuation_k", "fwd_pnl", "fwd_settle_alt", "fwd_mtm0", "fwd_matured_k", "unres_sec", "A0"]].sum() / 1e6
    q["dep_coverage_A"] = r[r.dep.notna()].groupby("q1").A0.sum() / 1e6 / q.A0
    q["uses"] = q[USES].sum(axis=1)
    q["sources"] = q[SRC].sum(axis=1)
    q["residual"] = q.uses - q.sources
    q["residual_pct_A"] = q.residual / q.A0 * 100
    q.round(2).to_csv("data/results/full_account_quarterly.csv")
    pd.set_option("display.width", 260, "display.max_columns", 40)
    print(q.round(1).T.to_string())


if __name__ == "__main__":
    main()
