"""זרם מט"ח בפועל לכל מסלול ורבעון - מכמויות הניירות בדוחות, בלי מודל ובלי רגרסיה.

לכל זוג רבעונים עוקבים q0 -> q1 ולכל מסלול, כל הסכומים בש"ח לפי שער q1 (מנטרל שינוי שער):
  ני"ע במט"ח עם מספר נייר (מניות, אג"ח, קרנות סל/נאמנות, כתבי אופציה, מובנים), מפתח: גיליון+מספר נייר:
      קיים בשניהם:   זרם = שווי1 × (יחידות1 − יחידות0) / יחידות1        (שינוי כמות בלבד, במחיר q1)
      חדש ב-q1:      זרם = שווי1                                        (קנייה)
      נעלם ב-q1:     זרם = −שווי0 × שער1/שער0                           (מכירה, במחיר q0 - המחיר במכירה אינו מדווח)
  מזומן/פיקדונות במט"ח:      זרם = Δ יתרה במטבע × שער1        (כולל ריבית/דיבידנד שהתקבלו - מדווח בנפרד: income_note)
  הלוואות במט"ח:              זרם = Δ יתרה במטבע × שער1
  קרנות השקעה פרטיות במט"ח:  לפי יחידות אם מדווחות; אחרת Δ יתרה (מסומן pf_no_units - כולל שערוך)
  אחר (חייבים/זכאים במט"ח):  Δ יתרה, בנפרד
  פורוורדים:                  Δ נוציונל נטו לכל מטבע (רגליים לא-שקליות, עסקאות עקביות) × שער1
  החלפים/חוזים (רווח צבור):   Δ רווח צבור במט"ח - מדווח בנפרד (mtm_change); השערוך עצמו אינו מסחר
סכום הרכיבים = קנייה (+) / מכירה (−) נטו של מט"ח מול שקל באותו רבעון. קנייה של נייר זר ממזומן דולרי מתקזזת בתוך הסכום.
פלט: data/flows/track_fx_flows.csv.gz (מסלול-רבעון-רכיב), data/flows/quarter_totals.csv
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from a2_classify_exposure import classify, explode_fx_forwards  # noqa: E402

KEY = ["legal_id", "track"]
SEC_FORMS = ["STOCK_DIRECT", "BOND", "ETF", "MUTUAL_FUND", "WARRANT", "STRUCTURED"]


def load(q: str) -> pd.DataFrame:
    d = classify(pd.read_csv(f"data/history/positions_{q}.csv.gz", low_memory=False))
    d["track"] = pd.to_numeric(d.track, errors="coerce")
    d["units"] = pd.to_numeric(d.units, errors="coerce")
    d["sid"] = d.sec_id.astype(str)
    d["ccy_v"] = d.fair_value_k / d.fx_rate   # שווי במטבע (אלפים)
    return d


def flows(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    fx1 = b[b.fx_route == "direct_ccy"].groupby("fx_ccy").fx_rate.median()
    out = []

    # 1. ני"ע עם מספר נייר
    k = KEY + ["sheet", "sid"]
    sa = a[a.form.isin(SEC_FORMS) & (a.fx_route == "direct_ccy") & a.sec_id.notna()]
    sb = b[b.form.isin(SEC_FORMS) & (b.fx_route == "direct_ccy") & b.sec_id.notna()]
    ga = sa.groupby(k).agg(v0=("fair_value_k", "sum"), u0=("units", "sum"), fx0=("fx_rate", "median"), form=("form", "first"),
                           ccy=("fx_ccy", "first"))
    gb = sb.groupby(k).agg(v1=("fair_value_k", "sum"), u1=("units", "sum"), fx1=("fx_rate", "median"), form1=("form", "first"))
    m = ga.join(gb, how="outer")
    both = m.v0.notna() & m.v1.notna()
    flow = pd.Series(0.0, index=m.index)
    # מחיר ליחידה במטבע בכל רבעון; יחידות ניתנות להשוואה רק אם המחיר ליחידה זז פחות מפי 2 (אחרת מוסכמת "ערך נקוב" התחלפה)
    pu0 = (m.v0 / m.fx0) / m.u0.replace(0, np.nan)
    pu1 = (m.v1 / m.fx1) / m.u1.replace(0, np.nan)
    ratio = (pu1 / pu0).abs()
    ok_units = both & m.u1.abs().gt(0) & m.u0.notna() & m.u1.notna() & ratio.between(0.5, 2.0)
    flow[ok_units] = m.v1[ok_units] * (m.u1[ok_units] - m.u0[ok_units]) / m.u1[ok_units]
    unresolved = both & ~ok_units
    flow[unresolved] = np.nan
    m["unresolved_value"] = np.where(unresolved, m.v1, 0.0)
    new = m.v0.isna() & m.v1.notna()
    flow[new] = m.v1[new]
    gone = m.v0.notna() & m.v1.isna()
    flow[gone] = -m.v0[gone] * m.ccy[gone].map(fx1) / m.fx0[gone]   # מכירה: שווי q0 בשער המטבע של q1
    m["flow"] = flow
    m["case"] = np.select([ok_units, new, gone, unresolved], ["units", "new", "sold", "unresolved"], "other")
    m["form"] = m.form.fillna(m.form1)
    m["flow"] = m.flow.fillna(0.0)
    s = m.reset_index().groupby(KEY + ["form", "case"]).agg(flow=("flow", "sum"), unresolved_value=("unresolved_value", "sum")).reset_index()
    s["component"] = "securities:" + s.form + ":" + s.case
    out.append(s[KEY + ["component", "flow", "unresolved_value"]])

    # 2. פריטים בלי מספר נייר - Δ יתרה במטבע × שער1, לפי צורה ומטבע
    def bal(d, forms):
        x = d[d.form.isin(forms) & (d.fx_route == "direct_ccy")]
        return x.groupby(KEY + ["form", "fx_ccy"]).ccy_v.sum()
    for forms, lab in ((["CASH"], "cash"), (["LOAN"], "loans"), (["PRIVATE_FUND"], "private_funds"), (["OTHER", "REAL_ESTATE"], "other")):
        j = pd.concat([bal(a, forms).rename("c0"), bal(b, forms).rename("c1")], axis=1).fillna(0.0).reset_index()
        j["flow"] = (j.c1 - j.c0) * j.fx_ccy.map(fx1).fillna(1.0)
        j["component"] = lab
        out.append(j.groupby(KEY + ["component"]).flow.sum().reset_index())
    # 3. פורוורדים - Δ נוציונל נטו לכל מטבע
    fa, _ = explode_fx_forwards(a)
    fb, _ = explode_fx_forwards(b)
    na = (fa.nominal).groupby([fa.legal_id, pd.to_numeric(fa.track, errors="coerce"), fa.ccy]).sum().rename("n0")
    nb = (fb.nominal).groupby([fb.legal_id, pd.to_numeric(fb.track, errors="coerce"), fb.ccy]).sum().rename("n1")
    j = pd.concat([na, nb], axis=1).fillna(0.0)
    j.index = j.index.set_names(KEY + ["ccy"])
    j = j.reset_index()
    j["flow"] = (j.n1 - j.n0) * j.ccy.map(fx1).fillna(np.nan) / 1000.0
    j["component"] = "forwards"
    out.append(j.groupby(KEY + ["component"]).flow.sum().reset_index())
    # 4. רווח צבור בהחלפים/חוזים במט"ח - בנפרד
    def mtm(d):
        x = d[d.form.isin(["SWAP_EQ_UNFUNDED", "SWAP_EQ_FUNDED", "FUTURE"]) &
              ((d.leg1_ccy.fillna("ILS") != "ILS") | (d.leg2_ccy.fillna("ILS") != "ILS") | (d.ccy.fillna("ILS") != "ILS"))]
        return x.groupby(KEY).fair_value_k.sum()
    j = pd.concat([mtm(a).rename("m0"), mtm(b).rename("m1")], axis=1).fillna(0.0).reset_index()
    j["flow"] = j.m1 - j.m0
    j["component"] = "derivatives_mtm_change"
    out.append(j[KEY + ["component", "flow"]])
    r = pd.concat(out, ignore_index=True)
    return r


def main():
    qs = sorted(p.name.replace("positions_", "").replace(".csv.gz", "") for p in Path("data/history").glob("positions_*.csv.gz"))
    qs = [q for q in qs if q != "2026Q3"]   # 2026Q3 חלקי (מעט גופים)
    Path("data/flows").mkdir(parents=True, exist_ok=True)
    cache = {}
    res = []
    for q0, q1 in zip(qs[:-1], qs[1:]):
        a = cache.pop(q0) if q0 in cache else load(q0)
        b = load(q1)
        cache[q1] = b
        f = flows(a, b)
        f["q0"], f["q1"] = q0, q1
        # רק מסלולים שקיימים בשני הרבעונים
        keys = set(map(tuple, a[KEY].drop_duplicates().values)) & set(map(tuple, b[KEY].drop_duplicates().values))
        f = f[[(x, y) in keys for x, y in zip(f.legal_id, f.track)]]
        # גוף שבאחד הרבעונים מדווח פורוורדים בלי סימן (כיוון לא ידוע) - מוחרג מכל הרבעון הזה, לא מנחשים
        cov = pd.read_csv("data/flows/forward_coverage.csv")
        cov = cov[cov.q.isin([q0, q1])]
        bad = set(cov[cov.unsigned > 0.02 * cov.deals].legal_id)
        f["excluded_unsigned_forwards"] = f.legal_id.isin(bad)
        if bad:
            print(f"[e1] {q0}->{q1}: מוחרגים (פורוורד בלי סימן): {sorted(bad)}", flush=True)
        f = f[~f.excluded_unsigned_forwards]
        res.append(f)
        t = f.groupby(f.component.str.split(":").str[0]).flow.sum() / 1e6
        print(f"[e1] {q0}->{q1}: " + ", ".join(f"{k} {v:+.1f}" for k, v in t.items()) + " (מיליארד ש\"ח)", flush=True)
    r = pd.concat(res, ignore_index=True)
    r.to_csv("data/flows/track_fx_flows.csv.gz", index=False, compression="gzip")
    tot = r.assign(group=r.component.str.split(":").str[0]).pivot_table(index="q0", columns="group", values="flow", aggfunc="sum") / 1e6
    tot["total_ex_mtm"] = tot.drop(columns=["derivatives_mtm_change"], errors="ignore").sum(axis=1)
    tot["unresolved_securities_value"] = r.groupby("q0").unresolved_value.sum() / 1e6
    tot.round(2).to_csv("data/flows/quarter_totals.csv")
    print(tot.round(1).to_string())


if __name__ == "__main__":
    main()
