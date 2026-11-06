"""שלב א.4 - נוציונל נגזרים (חוזים עתידיים והחלפי מניות) ויחס כיסוי מט"ח.

חוזים: FuturesResolver (הועתק מ-MASLULIM) - נוציונל = חוזים × רמת מדד × מכפיל. בלי רמות חיצוניות (ref_level=None)
הרמה נלמדת מקונצנזוס המדווחים; שלב ב יוסיף רמות אמיתיות לאימות.
החלפי מניות/מדד: נוציונל = הרגל הגדולה בערכה (נקוב × שער), בסימן +1 (ארוך; החלפי מדד בגופים מוסדיים הם ארוכים).
אופציות: לא מחושבות כאן (דלתא) - נשארות 'pending' ומדווחות בכמות.

פלט: data/deriv_notionals.csv.gz (שורה לנגזר: form, index_key, notional_k בש"ח אלפים, fx_ccy)
      data/track_cover.csv      לכל מסלול: נוציונל נגזרי מניות זרות, פורוורד ארוך דולר, ויחס כיסוי
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indexfx.vendor.futures_notional import FuturesResolver, FuturesRow, is_liability_leg, parse_code, security_id, tase_root  # noqa: E402

num = lambda s: pd.to_numeric(s, errors="coerce")  # noqa: E731


def futures_notionals(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df.form == "FUTURE"].copy()
    d["rd"] = pd.to_datetime(d.report_date).dt.date
    rows = []
    for i, r in d.iterrows():
        price, units = num(pd.Series([r.price])).iloc[0], num(pd.Series([r.units])).iloc[0]
        price = None if pd.isna(price) else float(price)
        units = None if pd.isna(units) else float(units)
        root, month = parse_code(r.sec_id, r["name"], r.rd)
        if root is None and r.ccy == "ILS":
            root = tase_root(r["name"])
        liab = is_liability_leg({"שם נייר ערך": r["name"]}, price, units)
        rows.append((i, FuturesRow(legal_id=str(r.legal_id), root=root, month=month, name=str(r["name"] or ""),
                                   ccy=r.ccy if isinstance(r.ccy, str) else None, units=units, price=price,
                                   report_date=r.rd, liability=liab, security=security_id(r.sec_id))))
    res = FuturesResolver([x for _, x in rows], lambda idx, dt: None)
    out = []
    for i, fr in rows:
        n = res.notional(fr)
        eq = res.is_equity(fr)
        out.append({"idx": i, "root": fr.root, "notional_ccy": n, "is_equity": eq})
    o = pd.DataFrame(out).set_index("idx")
    d = d.join(o)
    fx = np.where(d.ccy == "ILS", 1.0, num(d.fx_rate))
    d["notional_k"] = d.notional_ccy * fx / 1000.0
    d["resolved"] = d.notional_ccy.notna()
    return d


def swap_notionals(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df.form.isin(["SWAP_EQ_UNFUNDED", "SWAP_EQ_FUNDED"])].copy()
    v1 = (num(d.leg1_nominal) * num(d.leg1_fx)).abs()
    v2 = (num(d.leg2_nominal) * num(d.leg2_fx)).abs()
    d["notional_k"] = np.fmax(v1, v2) / 1000.0
    d["resolved"] = d.notional_k.notna()
    return d


def main():
    df = pd.read_csv("data/positions_classified.csv.gz", low_memory=False)
    fu = futures_notionals(df)
    sw = swap_notionals(df)
    cols = ["legal_id", "track", "form", "index_key", "index_label", "asset_class", "geo", "fx_ccy", "ccy", "notional_k", "resolved", "name", "swap_ticker"]
    fu["geo"] = np.where(fu.ccy == "ILS", "IL", fu.geo)
    allx = pd.concat([fu.reindex(columns=cols), sw.reindex(columns=cols)])
    allx.to_csv("data/deriv_notionals.csv.gz", index=False, compression="gzip")
    print(f"[a4] חוזים: {len(fu):,} (נפתרו {fu.resolved.mean():.0%}); החלפי מניות: {len(sw):,} (נפתרו {sw.resolved.mean():.0%})")
    print("נוציונל חוזים מניות, מיליארד ש\"ח:", round(fu[(fu.is_equity == True)].notional_k.sum() / 1e6, 1))  # noqa: E712
    print("נוציונל החלפי מניות, מיליארד ש\"ח:", round(sw.notional_k.sum() / 1e6, 1))

    # יחס כיסוי: פורוורד ארוך USD / נוציונל מניות זרות בנגזרים
    fw = pd.read_csv("data/fx_forward_legs.csv.gz")
    usd_fw = fw[fw.ccy == "USD"].groupby(["legal_id", "track"]).fx_exposure_k.sum().rename("fwd_usd_k")
    foreign = allx[(allx.asset_class == "equity") & (allx.geo != "IL") & (allx.fx_ccy != "ILS")]
    nd = foreign.groupby(["legal_id", "track"]).notional_k.sum().rename("deriv_foreign_eq_k")
    cov = pd.concat([usd_fw, nd], axis=1).fillna(0.0).reset_index()
    tot = pd.read_csv("data/track_totals.csv")[["legal_id", "track", "total_k"]]
    cov = cov.merge(tot, on=["legal_id", "track"], how="left")
    cov["deriv_pct"] = 100 * cov.deriv_foreign_eq_k / cov.total_k
    cov["fwd_pct"] = 100 * cov.fwd_usd_k / cov.total_k
    cov["cover_ratio"] = cov.fwd_usd_k / cov.deriv_foreign_eq_k.replace(0, np.nan)
    cov.to_csv("data/track_cover.csv", index=False)
    big = cov[cov.deriv_pct.abs() > 5].dropna(subset=["cover_ratio"])
    print(f"מסלולים עם נגזרי מניות זרות >5% מהנכסים: {len(big)}; יחס כיסוי (פורוורד USD / נוציונל): "
          f"חציון={big.cover_ratio.median():.2f}, רבעון תחתון={big.cover_ratio.quantile(.25):.2f}, עליון={big.cover_ratio.quantile(.75):.2f}")


if __name__ == "__main__":
    main()
