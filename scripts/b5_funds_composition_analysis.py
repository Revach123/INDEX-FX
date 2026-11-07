"""שלב ב.5 - קרנות נאמנות/סל: מאיפה מגיעה החשיפה למניות ולמט"ח, לפי הדוח החודשי המלא (b4) וטבלאות הרשות (isa_codes).

לכל קרן (הדוח האחרון):
  NAV        קוד 300 (שווי בשקלים)
  eq_rep     קוד 319 (% חשיפה למניות, רשמי)   fx_rep  קוד 320 (% חשיפה למט"ח, רשמי)
  חשיפה למניות לפי צורה = סכום "%חשיפה" של השורות בכל קבוצה (המפרט: חשיפת מניות בלבד, בלי מט"ח):
     phys_il / phys_fr      מניות וני"ע מנייתיים (טבלה A: 1,3,5,52,57) - לפי מטבע השורה (1=ש"ח)
     funds_il / funds_fr    קרנות (17,18,20,43,50,51) - לפי מטבע השורה
     deriv_il / deriv_fr    החלפי מניות 45, חוזים 33, אופציות 6,7,14,15 - לפי מטבע השורה
  מט"ח: spot = שווי השורות במטבע חוץ (לא נגזרים) / NAV; fwd = "%חשיפה" של חוזי אקדמה/חוזים/ספוט מט"ח (36,38,56)
  בקרה: סכום רכיבי המניות מול 319; סכום רכיבי המט"ח מול 320.
פלט: data/funds/composition_by_fund.csv, data/funds/composition_summary.csv, data/funds/swap_anchor_rates.csv
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indexfx.isa_codes import (ASSET, CCY, EQUITY_DERIV, EQUITY_FUNDS, EQUITY_PHYSICAL, FX_DERIV, SUMMARY,  # noqa: E402
                               parse_otc_name)


def num(s):
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.replace("%", "").str.strip(), errors="coerce")


def main(revach: Path):
    d = pd.read_csv("data/funds_composition/long.csv.gz", dtype=str)
    d["code"] = num(d["סוג נכס"])
    d["fund"] = num(d["מספר קרן"]).astype("Int64").astype(str)
    d["val"] = num(d["שווי בשקלים"])
    d["pct"] = num(d["%חשיפה"])
    d["ccy"] = num(d["מטבע"]).map(CCY).fillna("?")
    d["month"] = d.report_month
    # הדוח האחרון לכל קרן
    last = d.groupby("fund").month.transform("max")
    d = d[d.month == last]
    nav = d[d.code == 300].groupby("fund").val.sum()
    eq_rep = d[d.code == 319].groupby("fund").pct.sum()
    fx_rep = d[d.code == 320].groupby("fund").pct.sum()
    h = d[~d.code.isin(SUMMARY)].copy()
    h["foreign"] = h.ccy.ne("ILS")
    out = pd.DataFrame({"nav": nav, "eq_rep": eq_rep, "fx_rep": fx_rep})
    for lab, codes in (("phys", EQUITY_PHYSICAL), ("funds", EQUITY_FUNDS), ("deriv", EQUITY_DERIV)):
        x = h[h.code.isin(codes)]
        out[f"{lab}_il"] = x[~x.foreign].groupby("fund").pct.sum()
        out[f"{lab}_fr"] = x[x.foreign].groupby("fund").pct.sum()
    for c in ("swap", "future", "option"):
        codes = {"swap": {45}, "future": {33}, "option": {6, 7, 14, 15}}[c]
        out[f"deriv_{c}"] = h[h.code.isin(codes)].groupby("fund").pct.sum()
    spot = h[h.foreign & ~h.code.isin(EQUITY_DERIV | FX_DERIV)].groupby("fund").val.sum()
    out["fx_spot"] = 100 * spot / out.nav
    out["fx_fwd"] = h[h.code.isin(FX_DERIV)].groupby("fund").pct.sum()
    out["fx_deriv_mtm"] = 100 * h[h.foreign & h.code.isin(EQUITY_DERIV)].groupby("fund").val.sum() / out.nav
    out = out.fillna(0.0)
    out["eq_sum"] = out[[c for c in out.columns if c[:5] in ("phys_", "funds", "deriv") and c.split("_")[1] in ("il", "fr")]].sum(axis=1)
    out["fx_sum"] = out.fx_spot + out.fx_fwd + out.fx_deriv_mtm
    # סיווג קרן (Revach/data_for_site.json - קריאה בלבד)
    site = json.load(open(revach / "data_for_site.json", encoding="utf-8"))
    v = lambda r, k: (r.get(k) or {}).get("v", "")  # noqa: E731
    cl = pd.DataFrame([{"fund": v(r, "מספר קרן"), "name": v(r, "שם קרן"), "kind": v(r, "סוג"), "mimic": v(r, "קרן מחקה") != "",
                        "primary": v(r, "סיווג ראשי"), "hedged": v(r, "גידור מט\"ח") != ""} for r in site]).set_index("fund")
    out = out.join(cl, how="left")
    out.index.name = "fund"
    out.to_csv("data/funds/composition_by_fund.csv")
    ok = out[out.nav > 0]
    de, dx = (ok.eq_sum - ok.eq_rep).abs(), (ok.fx_sum - ok.fx_rep).abs()
    print(f"[b5] {len(ok)} קרנות; בקרה מול הרשמי: מניות |פער| חציון {de.median():.2f}pp, בתוך 2pp {100*(de<=2).mean():.0f}%; "
          f"מט\"ח חציון {dx.median():.2f}pp, בתוך 2pp {100*(dx<=2).mean():.0f}%")

    fe = ok[ok.primary.eq("מניות בחו\"ל")].copy()
    fe["mimic"], fe["hedged"] = fe.mimic.fillna(False).astype(bool), fe.hedged.fillna(False).astype(bool)
    fe["group"] = np.select([~fe.mimic, fe.mimic & ~fe.hedged, fe.mimic & fe.hedged],
                            ["אקטיבית (לא מחקה)", "מחקה לא מגודרת", "מחקה מגודרת"], "?")
    cols = ["eq_rep", "fx_rep", "phys_fr", "phys_il", "funds_fr", "funds_il", "deriv_swap", "deriv_future", "deriv_option",
            "fx_spot", "fx_fwd", "fx_deriv_mtm"]
    summ = fe.groupby("group").apply(lambda g: pd.Series({"n": len(g), "nav_bn": g.nav.sum() / 1e9} |
                                                         {c: np.average(g[c], weights=g.nav) for c in cols}), include_groups=False)
    summ["physical_share_of_equity_%"] = 100 * (summ.phys_fr + summ.phys_il) / summ.eq_rep
    summ.round(2).to_csv("data/funds/composition_summary.csv")
    pd.set_option("display.width", 250, "display.max_columns", 30)
    print("\nקרנות מניות חו\"ל – ממוצע משוקלל לפי שווי (% מהנכסים):")
    print(summ.round(1).T.to_string())

    # ריבית העוגן בהחלפי המניות (שם הנכס, נספח א') - שקלית או דולרית?
    sw = h[h.code == 45].copy()
    # היקף העסקה = "%חשיפה" הרשמי × שווי הקרן. (נבדק: "שווי במטבע מסחר" בפועל הוא הרווח הצבור בדולר, לא שווי העסקה;
    #  כמות × מחיר ה-Reset × שער נותן את אותו סדר גודל כמו %חשיפה, בהפרש תנועת המדד מאז ה-Reset)
    sw["notional"] = sw.pct / 100 * sw.fund.map(nav)
    sw["anchor"] = [(parse_otc_name(n) or {}).get("anchor_rate", "לא בפורמט") for n in sw["שם נכס"]]
    a = sw.groupby("anchor").agg(rows=("anchor", "size"), notional_bn=("notional", lambda s: s.sum() / 1e9)).sort_values("notional_bn", ascending=False)
    a.to_csv("data/funds/swap_anchor_rates.csv")
    print("\nהחלפי מניות בקרנות – ריבית העוגן (מהשם המקודד):")
    print(a.round(2).to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--revach", type=Path, required=True)
    main(ap.parse_args().revach)
