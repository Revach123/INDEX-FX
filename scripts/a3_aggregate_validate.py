"""שלב א.3 - אגרגציה למסלול + אימות מול החשיפה בפועל שבקובץ המדיניות.

פלט:
  data/track_totals.csv         שווי נכסי כל מסלול (אלפי ש"ח) + דוח
  data/track_exposure.csv       לכל מסלול: מניות%, מט"ח% (ספוט + פורוורד), פירוק לפי צורת חשיפה
  data/track_index_form.csv     מסלול × מדד × צורת חשיפה (שווי, אלפי ש"ח)
  data/validation_vs_policy.csv מול הנתון בפועל בקובץ המדיניות (Revach/sharetracks_test/track_policy.json), הפער
קובץ המדיניות נקרא בלבד (לא משתנה). הנתיב עם --policy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


def track_totals(df: pd.DataFrame) -> pd.DataFrame:
    """שווי כולל = שווי הוגן / שיעור מסך הנכסים, חציון על השורות הגדולות (יציב מול עיגולים)."""
    d = df[(df.pct_total.abs() > 0.005) & df.fair_value_k.notna() & (df.form != "SWAP_OTHER")].copy()
    d["tot"] = d.fair_value_k / d.pct_total
    g = d.groupby(["legal_id", "track"])
    out = g.agg(total_k=("tot", "median"), n_ref=("tot", "size"), tot_min=("tot", "min"), tot_max=("tot", "max"),
                report_date=("report_date", "first"), system=("system", "first")).reset_index()
    out["total_spread"] = (out.tot_max - out.tot_min) / out.total_k.abs()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--policy", type=Path, required=True)
    a = ap.parse_args()
    df = pd.read_csv("data/positions_classified.csv.gz", low_memory=False)
    fw = pd.read_csv("data/fx_forward_legs.csv.gz", low_memory=False)
    tt = track_totals(df)
    tt.to_csv("data/track_totals.csv", index=False)
    key = ["legal_id", "track"]

    spot = df.groupby(key).agg(eq_k=("eq_value_k", "sum"), fx_spot_k=("fx_exposure_k", "sum")).reset_index()
    fwd = fw.groupby(key).fx_exposure_k.sum().rename("fx_fwd_k").reset_index()
    ex = tt.merge(spot, on=key, how="left").merge(fwd, on=key, how="left")
    ex["fx_fwd_k"] = ex.fx_fwd_k.fillna(0.0)
    ex["fx_net_k"] = ex.fx_spot_k + ex.fx_fwd_k
    for c in ("eq_k", "fx_spot_k", "fx_fwd_k", "fx_net_k"):
        ex[c.replace("_k", "_pct")] = 100 * ex[c] / ex.total_k
    ex.to_csv("data/track_exposure.csv", index=False)

    # מסלול × מדד × צורה
    ix = df[df.index_key.fillna("") != ""].groupby(key + ["form", "index_key", "index_label", "fx_route"]).agg(
        value_k=("fair_value_k", "sum"), n=("form", "size")).reset_index()
    ix.to_csv("data/track_index_form.csv.gz", index=False, compression="gzip")

    # אימות מול המדיניות
    pol = json.load(open(a.policy, encoding="utf-8"))["tracks"]
    rows = []
    for k, v in pol.items():
        legal, tn = k.split("|")
        act_eq = act_fx = None
        for asset in v.get("assets", []):
            if asset[0].startswith("מניות"):
                act_eq = asset[5]
            if asset[0].startswith("חשיפה למט"):
                act_fx = asset[5]
        rows.append({"legal_id": legal, "track": tn, "pol_fx_exp": (v.get("fx") or {}).get("exp"),
                     "act_eq_pct": act_eq, "act_fx_pct": act_fx, "name": v.get("name")})
    pv = pd.DataFrame(rows)
    ex["track"] = ex.track.astype(str).str.replace(r"\.0$", "", regex=True)
    ex["legal_id"] = ex.legal_id.astype(str)
    m = ex.merge(pv, on=["legal_id", "track"], how="inner")
    m["d_fx_net"] = m.fx_net_pct - m.act_fx_pct
    m["d_fx_spot"] = m.fx_spot_pct - m.act_fx_pct
    m["d_eq"] = m.eq_pct - m.act_eq_pct
    m.to_csv("data/validation_vs_policy.csv", index=False)
    mm = m.dropna(subset=["act_fx_pct"])
    print(f"מסלולים: {len(ex)} בדוחות, {len(pv)} במדיניות, {len(m)} חופפים, {len(mm)} עם fx בפועל")
    for col in ("d_fx_spot", "d_fx_net"):
        d = mm[col].dropna()
        print(f"{col}: MAE={d.abs().mean():.2f}pp  חציון|פער|={d.abs().median():.2f}  בתוך 3pp={100*(d.abs()<=3).mean():.0f}%  n={len(d)}")
    d = m.dropna(subset=["act_eq_pct"]).d_eq
    print(f"d_eq (מניות ללא נגזרים): MAE={d.abs().mean():.2f}pp חציון={d.abs().median():.2f} בתוך 3pp={100*(d.abs()<=3).mean():.0f}% n={len(d)}")


if __name__ == "__main__":
    main()
