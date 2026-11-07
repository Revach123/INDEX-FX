"""קניית/מכירת דולר בחוזי אקדמה כשהמדד עולה - כל קרנות הסל המחקות על מניות בחו"ל (לא רק S&P/נאסד"ק).

כמו b3, אבל תשואת המדד נגזרת ממחיר הקרן עצמה (בלי למפות כל קרן למדד):
  לא מגודרת (חשופה למט"ח): r_idx = (1+R_ils)/(1+e) − 1      מגודרת: r_idx = R_ils
קנייה נטו של דולר בחוזים, כשבר מהנכסים: buy = w_fwd(t1)·(1+R)/(1+e) − w_fwd(t0)
רגרסיה buy = a + κ·r_idx בחלונות של 5/10/20 ימי הרכב, לכל קבוצה. שגיאות מקובצות לפי קרן.
מקורות (Revach, קריאה בלבד): funds-classified (הרכב יומי ומחיר), data_for_site.json (סיווג), exposure.csv (שווי).
פלט: data/funds/etf_hedge_all.csv
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd


def pct(s):
    try:
        return float(str(s).replace("%", "").replace(",", ""))
    except ValueError:
        return None


def main(revach: Path):
    site = json.load(open(revach / "data_for_site.json", encoding="utf-8"))
    v = lambda r, k: (r.get(k) or {}).get("v", "")  # noqa: E731
    cl = {v(r, "מספר קרן"): {"hedged": v(r, "גידור מט\"ח") != ""} for r in site
          if v(r, "סיווג ראשי") == "מניות בחו\"ל" and v(r, "קרן מחקה") != ""}
    H, P = [], []
    for f in sorted(glob.glob(str(revach / "funds-classified/*/*/*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        for x in d["funds"]:
            n = x.get("nrnum")
            if n not in cl:
                continue
            if x.get("last_price") and x.get("price_date"):
                P.append({"fund": n, "date": x["price_date"], "price": pct(x["last_price"])})
            if x.get("holdings"):
                w = sum(pct(h.get("weight")) or 0 for h in x["holdings"] if h.get("סיווג_ראשי") == "חוזה אקדמה")
                H.append({"fund": n, "date": x.get("as_of_date") or x.get("price_date"), "w_fwd": w / 100})
    h = pd.DataFrame(H).drop_duplicates(["fund", "date"])
    p = pd.DataFrame(P).drop_duplicates(["fund", "date"])
    for x in (h, p):
        x["date"] = pd.to_datetime(x.date, format="%d/%m/%Y")
    fx = pd.read_csv("data/market/boi_usdils.csv", parse_dates=["date"]).set_index("date").value
    ex = pd.read_csv(revach / "data/funds_info/exposure.csv", dtype=str)
    aum = dict(zip(ex.iloc[:, 0], pd.to_numeric(ex.iloc[:, 1], errors="coerce")))
    rows = []
    for k in (5, 10, 20):
        for fund, g in h.sort_values("date").groupby("fund"):
            pr = p[p.fund == fund].set_index("date").price.sort_index()
            g = g.reset_index(drop=True)
            hedged = cl[fund]["hedged"]
            for i in range(k, len(g), k):
                d0, d1 = g.date[i - k], g.date[i]
                if d0 not in pr.index or d1 not in pr.index:
                    continue
                R = pr[d1] / pr[d0] - 1
                e = fx.asof(d1) / fx.asof(d0) - 1
                r = R if hedged else (1 + R) / (1 + e) - 1
                rows.append({"k": k, "fund": fund, "hedged": hedged, "r": r, "e": e,
                             "buy": g.w_fwd[i] * (1 + R) / (1 + e) - g.w_fwd[i - k], "w_fwd": g.w_fwd[i - k],
                             "aum_m": aum.get(fund, np.nan)})
    df = pd.DataFrame(rows)
    df = df[df.buy.abs() < 0.5]
    out = []
    for (k, hed), g in df.groupby(["k", "hedged"]):
        X = np.column_stack([np.ones(len(g)), g.r])
        b = np.linalg.lstsq(X, g.buy.values, rcond=None)[0]
        e = g.buy.values - X @ b
        A = np.linalg.inv(X.T @ X)
        S = np.zeros((2, 2))
        for _, idx in pd.Series(np.arange(len(g))).groupby(g.fund.values):
            sv = (X[idx.values] * e[idx.values][:, None]).sum(0)
            S += np.outer(sv, sv)
        se = np.sqrt(np.diag(A @ S @ A))
        out.append({"חלון (ימים)": k, "קבוצה": "מגודרת 4A" if hed else "לא מגודרת 4D", "קרנות": g.fund.nunique(), "n": len(g),
                    "κ (קנייה מכל 1% עלייה)": b[1], "se": se[1], "משקל חוזה אקדמה ממוצע": g.w_fwd.mean()})
    r = pd.DataFrame(out).round(3)
    r.to_csv("data/funds/etf_hedge_all.csv", index=False)
    print(r.to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--revach", type=Path, required=True)
    main(ap.parse_args().revach)
