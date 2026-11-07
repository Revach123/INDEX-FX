"""שלב ב.2 - קרנות סל ונאמנות: איך מושגת החשיפה לחו"ל (פיזי / החלף / חוזה) ומה החשיפה למט"ח.

מקורות (Revach, קריאה בלבד):
  data/funds_info/exposure.csv   דוח חודשי רשמי לכל קרן (Maya): שווי נכסים (מיליון ש"ח), חשיפה למניות %, חשיפה למט"ח %
  data_for_site.json             סיווג: סוג (סל/מחקה/פתוחה), סיווג ראשי, גידור מט"ח, דירוג חשיפה (4D/4A...)
  funds-classified/YYYY/MM/*.json  הרכב יומי לקרנות סל (רשימת החזקות עם סיווג ראשי ומשקל)
פלט:
  data/funds/funds.csv            קרן: סיווג + נתונים רשמיים + משקלי הרכב לפי סוג נכס (יום אחרון)
  data/funds/summary_*.csv        סיכומים לבדיקת טענות
"""
from __future__ import annotations

import argparse
import glob
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

TYPES = {  # סיווג_ראשי בהרכב -> קבוצה
    "עסקת החלף": "swap", "חוזה עתידי": "future", "חוזה אקדמה": "fx_forward", "נייר זר": "foreign_security",
    "מניה": "il_stock", "קרן סל במניות": "etf_equity", "קרן סל באגח": "etf_bond", "יחידת השתתפות": "fund_unit",
    "מק\"מ": "il_bills", "אג\"ח ממשלתי": "il_gov_bond", "אג\"ח קונצרני": "il_corp_bond", "תעודות חוב": "il_notes",
    "פיקדון בבנק": "deposit", "ספוט מט\"ח": "fx_spot", "בטחונות": "collateral", "אופציה": "option",
}


def pct(s) -> float | None:
    try:
        return float(str(s).replace("%", "").replace("כ-", "").replace(",", "").strip())
    except ValueError:
        return None


def latest_holdings(revach: Path) -> tuple[pd.DataFrame, str]:
    files = sorted(glob.glob(str(revach / "funds-classified/*/*/*.json")))
    d = json.load(open(files[-1], encoding="utf-8"))
    rows = []
    for f in d["funds"]:
        if not f.get("holdings"):
            continue
        w = defaultdict(float)
        for h in f["holdings"]:
            w[TYPES.get(h.get("סיווג_ראשי"), "other")] += pct(h.get("weight")) or 0.0
        rows.append({"fund": str(f["nrnum"]), "holdings_date": f.get("as_of_date") or f.get("price_date"),
                     "tracks_index": f.get("tracks_index"), **{f"w_{k}": v for k, v in w.items()}})
    return pd.DataFrame(rows), d.get("data_date") or Path(files[-1]).stem


def main(revach: Path):
    out = Path("data/funds")
    out.mkdir(parents=True, exist_ok=True)
    ex = pd.read_csv(revach / "data/funds_info/exposure.csv", dtype=str)
    ex = ex.rename(columns=lambda c: c.replace("‫", "").replace("‬", "").replace("‏", "").strip())
    ex = ex.rename(columns={"מספר קרן": "fund", "שווי נכסי הקרן": "aum_m", "תאריך דוח": "report_date"})
    eqc = [c for c in ex.columns if "מניות" in c][0]
    fxc = [c for c in ex.columns if "מט" in c][0]
    ex["eq_pct"], ex["fx_pct"], ex["aum_m"] = ex[eqc].map(pct), ex[fxc].map(pct), ex.aum_m.map(pct)
    site = json.load(open(revach / "data_for_site.json", encoding="utf-8"))
    v = lambda r, k: (r.get(k) or {}).get("v", "")  # noqa: E731
    cl = pd.DataFrame([{"fund": v(r, "מספר קרן"), "name": v(r, "שם קרן"), "kind": v(r, "סוג"), "mimic": v(r, "קרן מחקה") != "",
                        "primary": v(r, "סיווג ראשי"), "secondary": v(r, "סיווג משני"), "hedged": v(r, "גידור מט\"ח") != "",
                        "exp_code": v(r, "חשיפה"), "underlying": v(r, "נכס בסיס"), "manager": v(r, "מנהל קרן")} for r in site])
    h, hdate = latest_holdings(revach)
    df = cl.merge(ex[["fund", "aum_m", "eq_pct", "fx_pct", "report_date"]], on="fund", how="left").merge(h, on="fund", how="left")
    wcols = [c for c in df.columns if c.startswith("w_")]
    df["has_holdings"] = df[wcols].notna().any(axis=1)
    df[wcols] = df[wcols].fillna(0.0)
    df.to_csv(out / "funds.csv", index=False)
    print(f"[b2] {len(df)} קרנות; עם דוח חודשי: {df.aum_m.notna().sum()}; עם הרכב יומי ({hdate}): {df.has_holdings.sum()}")

    # ── קבוצות לבדיקה ──
    fe = df[df.primary.eq("מניות בחו\"ל") & df.aum_m.notna()].copy()
    fe["group"] = np.select([fe.mimic & ~fe.hedged, fe.mimic & fe.hedged], ["מחקה לא מגודרת", "מחקה מגודרת"], "אקטיבית")
    g = fe.groupby(["group", "kind"]).agg(n=("fund", "size"), aum_bn=("aum_m", lambda s: s.sum() / 1e3),
                                          fx_pct_w=("fx_pct", lambda s: np.average(s.fillna(0), weights=fe.loc[s.index, "aum_m"])),
                                          eq_pct_w=("eq_pct", lambda s: np.average(s.fillna(0), weights=fe.loc[s.index, "aum_m"]))).round(2)
    g.to_csv(out / "summary_foreign_equity_funds.csv")
    print("\nמניות בחו\"ל – לפי קבוצה וסוג (שווי במיליארד ש\"ח, חשיפות ממוצעות משוקללות לפי שווי, מהדוח הרשמי):")
    print(g.to_string())
    # הרכב בקרנות סל (יש הרכב יומי)
    hh = fe[fe.has_holdings & fe.mimic]
    comp = hh.groupby("group").apply(lambda x: pd.Series({c[2:]: np.average(x[c], weights=x.aum_m) for c in wcols} |
                                                         {"n": len(x), "aum_bn": x.aum_m.sum() / 1e3})).T.round(1)
    comp.to_csv(out / "summary_etf_composition.csv")
    print("\nקרנות סל מחקות על מניות בחו\"ל – הרכב ממוצע משוקלל (% מהנכסים):")
    print(comp.to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--revach", type=Path, required=True)
    main(ap.parse_args().revach)
