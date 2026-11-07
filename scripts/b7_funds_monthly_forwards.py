"""קניית דולר בפועל בחוזי אקדמה - כל הקרנות המחקות על מניות בחו"ל (סל + מחקות פתוחות), חודש מול חודש, מהדוח החודשי המלא.

לכל קרן וחודש (הדוח האחרון לאותו חודש), לפי מפרט הרשות:
  NAV = קוד 300 (שווי בשקלים), יחידות = קוד 301 (כמות)  ->  שווי ליחידה; R = תשואת הקרן בחודש
  w   = Σ כמות × שער המטבע של חוזי אקדמה (קוד 38) מול שקל / NAV   (מהכמות - עמודת %חשיפה חסרה אצל חלק מהמנהלים)
  e   = שינוי USD/ILS (בנק ישראל, סוף חודש)
קנייה בגלל תנועת השוק (שבר מנכסי החודש הקודם): buy_mkt = w_t·(1+R)/(1+e) − w_{t−1}
קנייה בגלל הנפקות/פדיונות:                       buy_flows = w_t · (NAV_t − NAV_{t−1}·(1+R)) / NAV_{t−1} / (1+e)
סה"כ קנייה בפועל (מיליארדי ש"ח, בשער t):          (w_t·NAV_t − w_{t−1}·NAV_{t−1}·(1+e))
תשואת המדד מתוך הקרן: לא מגודרת r = (1+R)/(1+e) − 1; מגודרת r = R.
רגרסיה buy_mkt = a + κ·r, לכל קבוצה (סל / מחקה פתוחה; לא מגודרת / מגודרת); שגיאות מקובצות לפי קרן.
פלט: data/funds/forwards_monthly.csv.gz, data/funds/forwards_monthly_kappa.csv, data/funds/forwards_monthly_totals.csv
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def num(s):
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.replace("%", "").str.strip(), errors="coerce")


def main(revach: Path):
    parts = []
    for f in sorted(Path("data/funds_composition/long").glob("*.csv.gz")):
        x = pd.read_csv(f, dtype=str, usecols=lambda c: c in ("report_id", "report_month", "מספר קרן", "סוג נכס", "כמות", "שווי בשקלים",
                                                             "%חשיפה", "שער המטבע", "TICKER", "מטבע"))
        x["code"] = num(x["סוג נכס"])
        x = x[x.code.isin([300, 301, 38])]
        parts.append(x)
    d = pd.concat(parts, ignore_index=True)
    d["fund"] = num(d["מספר קרן"]).astype("Int64").astype(str)
    d["rid"] = num(d.report_id)
    d["val"], d["qty"], d["pct"] = num(d["שווי בשקלים"]), num(d["כמות"]), num(d["%חשיפה"])
    d["rate"] = num(d["שער המטבע"])
    tk = d["TICKER"].astype(str).str.upper().str.replace(r"[^A-Z]", "", regex=True)
    # "שער המטבע" ריק אצל חלק מהמנהלים בחלק מהחודשים: השער של אותו מטבע בשורות אחרות באותו דוח; אחרת - שער יציג
    # בנק ישראל לדולר בסוף החודש (לצמד USDILS בלבד)
    d["ccy_code"] = num(d["מטבע"])
    rep_rate = d[d.rate.gt(0)].groupby(["rid", "ccy_code"]).rate.median()
    fb = pd.Series([rep_rate.get((r, c), np.nan) for r, c in zip(d.rid, d.ccy_code)], index=d.index)
    boi = pd.read_csv("data/market/boi_usdils.csv", parse_dates=["date"]).set_index("date").value.resample("ME").last()
    boi.index = boi.index.to_period("M").astype(str).str.replace("-", "")
    usd_fb = np.where(tk.str.startswith("USD") & tk.str.endswith("ILS"), d.report_month.map(boi), np.nan)
    d["rate_src"] = np.where(d.rate.gt(0), "row", np.where(fb.notna(), "report", np.where(~np.isnan(usd_fb), "boi", "none")))
    d["rate"] = d.rate.where(d.rate.gt(0), fb).fillna(pd.Series(usd_fb, index=d.index))
    # חוזה אקדמה (מפרט, נספח א'): "כמות" = כמות המטבע הראשי, חיובי = קנייה; "שער המטבע" = שער המטבע הראשי בש"ח.
    # רק צמדים מול שקל (XXXILS) משנים חשיפה מול השקל; צמד בין שני מטבעות חוץ - ניטרלי, לא נספר.
    d["fx_ils"] = np.where((d.code == 38) & tk.str.endswith("ILS") & ~tk.str.startswith("ILS"), d.qty * d.rate, 0.0)
    d["fx_other_pair"] = (d.code == 38) & ~tk.str.endswith("ILS")
    # הדוח האחרון (מזהה הגבוה) לכל קרן וחודש
    last = d.groupby(["fund", "report_month"]).rid.transform("max")
    d = d[d.rid == last]
    g = d.groupby(["fund", "report_month"])
    m = pd.DataFrame({"nav": d[d.code == 300].groupby(["fund", "report_month"]).val.sum(),
                      "units": d[d.code == 301].groupby(["fund", "report_month"]).qty.sum(),
                      "fwd_ils": d[d.code == 38].groupby(["fund", "report_month"]).fx_ils.sum(),
                      "w_pct": d[d.code == 38].groupby(["fund", "report_month"]).pct.sum() / 100}).reset_index()
    m["w"] = m.fwd_ils / m.nav   # מהכמות - לא תלוי בעמודת %חשיפה (שחסרה אצל חלק מהמנהלים בחלק מהחודשים)
    m["w"] = m.w.fillna(0.0)
    m = m[m.nav > 0]
    m["ppu"] = m.nav / m.units.replace(0, np.nan)
    site = json.load(open(revach / "data_for_site.json", encoding="utf-8"))
    v = lambda r, k: (r.get(k) or {}).get("v", "")  # noqa: E731
    cl = pd.DataFrame([{"fund": v(r, "מספר קרן"), "kind": v(r, "סוג"), "hedged": v(r, "גידור מט\"ח") != ""}
                       for r in site if v(r, "סיווג ראשי") == "מניות בחו\"ל" and v(r, "קרן מחקה") != ""])
    m = m.merge(cl, on="fund", how="inner")
    fx = pd.read_csv("data/market/boi_usdils.csv", parse_dates=["date"]).set_index("date").value.resample("ME").last()
    fx.index = fx.index.to_period("M").astype(str).str.replace("-", "")
    m = m.sort_values(["fund", "report_month"])
    m["prev_month"] = (pd.PeriodIndex(m.report_month, freq="M") - 1).astype(str).str.replace("-", "")
    p = m.merge(m[["fund", "report_month", "nav", "w", "ppu"]].rename(columns={"report_month": "prev_month", "nav": "nav0", "w": "w0", "ppu": "ppu0"}),
                on=["fund", "prev_month"], how="inner")
    p["e"] = p.report_month.map(fx) / p.prev_month.map(fx) - 1
    p["R"] = p.ppu / p.ppu0 - 1
    p = p.dropna(subset=["R", "e"])
    p = p[p.R.abs() < 0.5]   # שינוי יחידות (פיצול) - מוחרג ונספר
    p["r"] = np.where(p.hedged, p.R, (1 + p.R) / (1 + p.e) - 1)
    p["buy_mkt"] = p.w * (1 + p.R) / (1 + p.e) - p.w0
    p["buy_flows"] = p.w * (p.nav - p.nav0 * (1 + p.R)) / p.nav0 / (1 + p.e)
    p["buy_total_bn"] = (p.w * p.nav - p.w0 * p.nav0 * (1 + p.e)) / 1e9
    p["buy_mkt_bn"] = p.buy_mkt * p.nav0 * (1 + p.e) / 1e9
    p["buy_flows_bn"] = p.buy_flows * p.nav0 * (1 + p.e) / 1e9
    p["kind2"] = np.where(p.kind.eq("קרן סל"), "קרן סל", "מחקה פתוחה")
    p.to_csv("data/funds/forwards_monthly.csv.gz", index=False, compression="gzip")
    print(f"[b7] {p.fund.nunique()} קרנות, {len(p)} קרן-חודש, {p.report_month.min()}→{p.report_month.max()}")

    rows = []
    for (kind, hed), gg in list(p.groupby(["kind2", "hedged"])) + [(("הכל", False), p[~p.hedged]), (("הכל", True), p[p.hedged])]:
        gg = gg[gg.buy_mkt.abs() < 0.5]
        X = np.column_stack([np.ones(len(gg)), gg.r])
        A = np.linalg.inv(X.T @ X)
        b = A @ X.T @ gg.buy_mkt.values
        e = gg.buy_mkt.values - X @ b
        S = np.zeros((2, 2))
        for _, idx in pd.Series(np.arange(len(gg))).groupby(gg.fund.values):
            sv = (X[idx.values] * e[idx.values][:, None]).sum(0)
            S += np.outer(sv, sv)
        se = np.sqrt(np.diag(A @ S @ A))
        rows.append({"סוג": kind, "גידור": "מגודרת" if hed else "לא מגודרת", "קרנות": gg.fund.nunique(), "קרן-חודש": len(gg),
                     "שווי אחרון (מיליארד)": gg.groupby("fund").nav.last().sum() / 1e9, "חוזה אקדמה ממוצע": gg.w.mean(),
                     "κ (קנייה מכל 1% עלייה)": b[1], "se": se[1]})
    r = pd.DataFrame(rows).round(3)
    r.to_csv("data/funds/forwards_monthly_kappa.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 20)
    print(r.to_string(index=False))
    tot = p.groupby(["report_month", "hedged"]).agg(total=("buy_total_bn", "sum"), mkt=("buy_mkt_bn", "sum"), flows=("buy_flows_bn", "sum"),
                                                    r=("r", "median")).unstack("hedged").round(2)
    tot.to_csv("data/funds/forwards_monthly_totals.csv")
    print(tot.to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--revach", type=Path, required=True)
    main(ap.parse_args().revach)
