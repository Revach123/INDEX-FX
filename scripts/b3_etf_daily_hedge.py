"""שלב ב.3 - האם קרן סל לא מגודרת קונה דולר כשהמדד עולה? בדיקה מההרכב היומי בפועל.

לכל קרן סל מחקה על S&P 500 / נאסד"ק 100 (4D לא מגודרת, ו-4A מגודרת להשוואה), מתוך קבצי ההרכב היומיים
(Revach/funds-classified - ההרכב היומי עם סיווג, קריאה בלבד):
  w_fwd(t)  = משקל "חוזה אקדמה" (נוציונל דולר כאחוז מהנכסים)
  R(t)      = תשואת הקרן בש"ח בין שני ימי הרכב (לפי מחיר היחידה)
  e(t)      = שינוי USD/ILS (בנק ישראל) באותו פרק זמן
קנייה נטו של דולר בחוזים, כאחוז מהנכסים של יום קודם:
  buy(t) = w_fwd(t)·(1+R)/(1+e) − w_fwd(t−1)
(נוציונל הדולר ביום t ביחידות של נכסי יום t−1 בדולר, פחות הנוציונל הקודם.) תנועות יצירה/פדיון לא משנות את המשקל, ולכן לא נכנסות.
רגרסיה: buy(t) על תשואת המדד בדולר r(t) (ופיגור). השערה א (תשואת ההחלף בשקל): מקדם ≈ +1. השערה ב (בדולר): ≈ 0.
"""
from __future__ import annotations

import argparse
import glob
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd


def pct(s):
    try:
        return float(str(s).replace("%", "").replace(",", ""))
    except ValueError:
        return None


def load(revach: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    H, P = [], []
    for f in sorted(glob.glob(str(revach / "funds-classified/*/*/*.json"))):
        d = json.load(open(f, encoding="utf-8"))
        for x in d["funds"]:
            nm = x.get("name") or ""
            ti = x.get("tracks_index") or ""
            if not (("4D" in nm or "4A" in nm) and ("S&P 500" in ti or "Nasdaq 100" in ti or "נאסד" in ti or "NASDAQ 100" in ti.upper())):
                continue
            if any(k in ti for k in ("Equal", "Dividend", "Low Vol", "Top", "ESG", "Scored", "Growth", "Value")):
                continue
            if x.get("last_price") and x.get("price_date"):
                P.append({"fund": x["nrnum"], "date": x["price_date"], "price": pct(x["last_price"])})
            if x.get("holdings"):
                w = sum(pct(h.get("weight")) or 0 for h in x["holdings"] if h.get("סיווג_ראשי") == "חוזה אקדמה")
                sw = sum(pct(h.get("weight")) or 0 for h in x["holdings"] if h.get("סיווג_ראשי") == "עסקת החלף")
                fs = sum(pct(h.get("weight")) or 0 for h in x["holdings"] if h.get("סיווג_ראשי") == "ספוט מט\"ח")
                H.append({"fund": x["nrnum"], "name": nm, "index": "ndx" if ("100" in ti and "500" not in ti) else "spx",
                          "unhedged": "4D" in nm, "date": x.get("as_of_date") or x.get("price_date"),
                          "w_fwd": w, "w_swap": sw, "w_fxspot": fs})
    h = pd.DataFrame(H).drop_duplicates(["fund", "date"])
    p = pd.DataFrame(P).drop_duplicates(["fund", "date"])
    for x in (h, p):
        x["date"] = pd.to_datetime(x.date, format="%d/%m/%Y")
    return h, p


def main(revach: Path):
    h, p = load(revach)
    px = pd.read_csv("data/market/prices.csv", parse_dates=["date"]).pivot(index="date", columns="symbol", values="close")
    fx = pd.read_csv("data/market/boi_usdils.csv", parse_dates=["date"]).set_index("date").value
    rows = []
    for fund, g in h.sort_values("date").groupby("fund"):
        pr = p[p.fund == fund].set_index("date").price.sort_index()
        g = g.reset_index(drop=True)
        for i in range(1, len(g)):
            d0, d1 = g.date[i - 1], g.date[i]
            if (d1 - d0).days > 5 or d0 not in pr.index or d1 not in pr.index:
                continue
            R = pr[d1] / pr[d0] - 1
            e = fx.asof(d1) / fx.asof(d0) - 1
            idx = px["^NDX" if g["index"][i] == "ndx" else "^GSPC"]
            # תשואת המדד בסגירות ארה"ב שקדמו לכל אחד מימי ההרכב (ההרכב בישראל משקף את סגירת ניו יורק הקודמת)
            r_prev = idx.asof(d1 - pd.Timedelta(days=1)) / idx.asof(d0 - pd.Timedelta(days=1)) - 1
            r_same = idx.asof(d1) / idx.asof(d0) - 1
            w0, w1 = g.w_fwd[i - 1] / 100, g.w_fwd[i] / 100
            rows.append({"fund": fund, "name": g.name_[i] if "name_" in g else g["name"][i], "unhedged": g.unhedged[i],
                         "d0": d0, "d1": d1, "R": R, "e": e, "r_prev": r_prev, "r_same": r_same, "w0": w0, "w1": w1,
                         "buy": w1 * (1 + R) / (1 + e) - w0, "w_swap": g.w_swap[i] / 100})
    df = pd.DataFrame(rows)
    out = Path("data/funds")
    df.to_csv(out / "etf_daily_hedge.csv", index=False)
    print(f"[b3] {df.fund.nunique()} קרנות, {len(df)} תצפיות יומיות ({df.d1.min().date()}→{df.d1.max().date()})")
    res = []
    for unh, g in df.groupby("unhedged"):
        g = g.dropna(subset=["buy", "r_prev", "r_same"])
        g = g[g.buy.abs() < 0.5]  # החרגת קפיצות לא סבירות (שינוי מבנה); נספרות
        X = np.column_stack([np.ones(len(g)), g.r_prev, g.r_same])
        b = np.linalg.lstsq(X, g.buy.values, rcond=None)[0]
        e = g.buy.values - X @ b
        se = np.sqrt(np.diag(e @ e / (len(g) - 3) * np.linalg.inv(X.T @ X)))
        res.append({"group": "4D לא מגודרת" if unh else "4A מגודרת", "n": len(g), "funds": g.fund.nunique(),
                    "coef_r_prev": b[1], "t_prev": b[1] / se[1], "coef_r_same": b[2], "t_same": b[2] / se[2],
                    "avg_w_fwd": g.w1.mean(), "avg_w_swap": g.w_swap.mean()})
    r = pd.DataFrame(res).round(3)
    r.to_csv(out / "etf_daily_hedge_regression.csv", index=False)
    print(r.to_string(index=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--revach", type=Path, required=True)
    main(ap.parse_args().revach)
