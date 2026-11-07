"""בדיקת הטענות הכמותיות במאמר מול הנתונים (מסלולי פנסיה/גמל/ביטוח + קרנות).

סיווג "מסלול כללי/תלוי גיל": שם המסלול (מקובץ המדיניות) בלי אף מילת מפתח של מסלול ייעודי (SPECIFIC).
הכלל שקוף ונשמר; הסכום מול סך הכל מדווח, ומודפסים המסלולים הגדולים בכל צד לבקרה.
פלט: data/results/claims_tracks.csv, claims_general_by_company.csv
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

SPECIFIC = re.compile(r"S&P|s&p|500|מניות|אג\"?ח|אגח|הלכה|כספי|שקלי|עוקב|קיימות|מדד|סחיר|ESG|אשראי|ממשלתי|נאסד|נסד|חו\"?ל|שריעה|"
                      r"מובטח|דולר|פאסיב|מחקה|הלכתי|תשואה|נדל|ריבית|טכנולוג|סקטור|אמריק|ארה\"?ב|עולמי|גלובלי|הלכ", re.I)


def wavg(x, w):
    if x is None:
        return 0.0
    m = x.notna() & w.notna()
    return float(np.average(x[m], weights=w[m])) if m.any() else np.nan


def main():
    o = pd.read_csv("data/track_decomposition.csv")
    o["name"] = o.name.fillna("")
    o["general"] = (o.name != "") & ~o.name.str.contains(SPECIFIC)
    o["aum_bn"] = o.total_k / 1e6
    Path("data/results").mkdir(parents=True, exist_ok=True)
    print(f"סך נכסי כל המסלולים בדוחות: {o.aum_bn.sum():,.0f} מיליארד ש\"ח ({len(o)} מסלולים); "
          f"עם שם מדיניות: {o[o.name!=''].aum_bn.sum():,.0f}")
    g = o[o.general]
    print(f"מסלולים כלליים/תלויי גיל: {g.aum_bn.sum():,.0f} מיליארד ש\"ח ({len(g)} מסלולים)")
    print("  הגדולים:", "; ".join(g.nlargest(6, "total_k").name.str[:30]))
    print("  הגדולים שסווגו ייעודיים:", "; ".join(o[~o.general & (o.name != "")].nlargest(6, "total_k").name.str[:30]))

    rows = []
    for lab, d in (("כלליים", g), ("כל המסלולים", o)):
        w = d.total_k
        r = {"קבוצה": lab, "נכסים (מיליארד)": d.aum_bn.sum(),
             "מניות רשמי %": wavg(d.act_eq, w), "מט\"ח רשמי %": wavg(d.act_fx, w),
             "מניות מחושב %": wavg(d.eq_total, w), "מט\"ח מחושב %": wavg(d.fx_total, w),
             "מניות ארץ %": wavg(d.eq_il_total, w), "מניות חו\"ל %": wavg(d.eq_fr_total, w),
             "חו\"ל: מניות ישירות %": wavg(d.eq_fr_phys, w), "חו\"ל: קרנות זרות %": wavg(d.eq_fr_fund_foreign, w),
             "חו\"ל: קרנות ישראליות %": wavg(d.eq_fr_fund_il, w), "חו\"ל: החלפים %": wavg(d.get("eq_fr_swap"), w),
             "חו\"ל: חוזים %": wavg(d.get("eq_fr_future"), w), "חו\"ל: אופציות %": wavg(d.get("eq_fr_option"), w),
             "מט\"ח: ספוט ישיר %": wavg(d.fx_spot_direct, w), "מט\"ח: דרך קרנות ישראליות %": wavg(d.fx_il_funds, w),
             "מט\"ח: פורוורדים %": wavg(d.fx_forwards, w), "מט\"ח: רווח צבור בנגזרים %": wavg(d.fx_deriv_mtm, w)}
        rows.append(r)
    t = pd.DataFrame(rows).set_index("קבוצה").T.round(2)
    t.to_csv("data/results/claims_tracks.csv")
    print(t.to_string())
    # טווח החזקה פיזית בחו"ל לפי חברה (כלליים)
    g = g.assign(phys=g.eq_fr_phys + g.eq_fr_fund_foreign)
    byco = g.groupby("legal_id").apply(lambda d: pd.Series({
        "aum_bn": d.aum_bn.sum(), "eq_fr": wavg(d.eq_fr_total, d.total_k), "stocks_direct": wavg(d.eq_fr_phys, d.total_k),
        "foreign_funds": wavg(d.eq_fr_fund_foreign, d.total_k), "phys_total": wavg(d.phys, d.total_k),
        "swaps": wavg(d.get("eq_fr_swap"), d.total_k), "futures": wavg(d.get("eq_fr_future"), d.total_k),
        "il_funds": wavg(d.eq_fr_fund_il, d.total_k), "fx": wavg(d.act_fx, d.total_k)}), include_groups=False)
    byco = byco.sort_values("aum_bn", ascending=False).round(1)
    byco.to_csv("data/results/claims_general_by_company.csv")
    print("\nכלליים לפי חברה (אחוז מהנכסים):")
    print(byco.head(15).to_string())


if __name__ == "__main__":
    main()
