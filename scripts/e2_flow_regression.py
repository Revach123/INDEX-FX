"""מה מסביר את קניית/מכירת המט"ח בפועל של כל מסלול ברבעון (e1 + e1b) - בלי להסיק זרם מסחיפת חשיפה.

flow (שבר מהנכסים ב-q0) = Σ רכיבי e1 (ני"ע, מזומן, הלוואות, קרנות פרטיות, אחר, פורוורדים) + (Δ רווח צבור בנגזרים − שערוך e1b)
מסבירים (שבר מהנכסים ב-q0, מהפאנל d3 ומ-data.gov):
  gain_phys   רווח דולרי על החזקה פיזית בחו"ל ברבעון
  gain_syn    רווח דולרי על החלפים/חוזים (תשואה פחות ריבית)
  growth_fx   FX0 × תשואת המסלול (כמה מט"ח צריך להוסיף כדי לשמור על אותו אחוז כשהתיק גדל מתשואה)
  deposits_fx FX0 × הפקדות נטו ברבעון / נכסים (כסף חדש שמושקע לפי אותו אחוז)
אם שומרים על אחוז מט"ח קבוע: מקדמים ‎−1, ‎−1, ‎+1, ‎+1. אפקט קבוע לכל רבעון, שגיאות מקובצות לפי מסלול.
פלט: data/results/flow_regression.csv, data/flows/flow_panel.csv.gz
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d3_rebalancing_history import wls_cluster  # noqa: E402

KEY = ["legal_id", "track"]


def main():
    f = pd.read_csv("data/flows/track_fx_flows.csv.gz")
    f["group"] = f.component.str.split(":").str[0]
    trade = f[f.group != "derivatives_mtm_change"].groupby(KEY + ["q0"]).flow.sum().rename("flow_trade_k")
    mtm = f[f.group == "derivatives_mtm_change"].groupby(KEY + ["q0"]).flow.sum().rename("mtm_change_k")
    val = pd.read_csv("data/flows/derivative_valuation.csv.gz").set_index(KEY + ["q0"]).valuation_k
    j = pd.concat([trade, mtm], axis=1).join(val, how="left").fillna(0.0)
    j["flow_k"] = j.flow_trade_k + j.mtm_change_k - j.valuation_k
    j = j.reset_index()
    p = pd.read_csv("data/results/rebalancing_panel.csv")
    p = p.merge(j, on=KEY + ["q0"], how="inner")
    # הפקדות נטו ברבעון (data.gov, מיליוני ש"ח) - 3 החודשים שאחרי q0
    dg = pd.read_csv("data/datagov/monthly.csv.gz", low_memory=False)
    dg["dep"] = pd.to_numeric(dg.NET_MONTHLY_DEPOSITS, errors="coerce")
    dg["m"] = pd.PeriodIndex(dg.REPORT_PERIOD.astype(int).astype(str), freq="M")
    st = pd.read_csv("data/history/track_quarter_state.csv.gz").drop_duplicates(["legal_id", "track"])
    dg["legal_id"] = dg.FUND_ID.map(st.groupby("track").legal_id.first())
    dg = dg.dropna(subset=["legal_id"])
    dg["q"] = (dg.m - 1).dt.asfreq("Q").astype(str).str.replace("Q", "Q")   # חודש m שייך לרבעון שמתחיל אחרי q0
    qmap = {str(pd.Period(q, freq="Q")): q for q in p.q0.unique()}
    dg["q0"] = (dg.m - 3).dt.asfreq("Q").astype(str).map(lambda s: s.replace("Q", "Q"))
    dep = dg.groupby(["legal_id", "FUND_ID", "q0"]).dep.sum().rename("dep_m").reset_index().rename(columns={"FUND_ID": "track"})
    dep["legal_id"] = dep.legal_id.astype(int)
    dep["track"] = dep.track.astype(float)
    p = p.merge(dep, on=KEY + ["q0"], how="left")
    A = p.total_k   # אלפי ש"ח
    p["y"] = p.flow_k / A
    p["gain_phys"], p["gain_syn"] = p.g_phys, p.g_syn
    p["growth_fx"] = p.FX * p.R1
    p["deposits_fx"] = p.FX * (p.dep_m * 1000 / A)
    p["has_dep"] = p.dep_m.notna()
    p.to_csv("data/flows/flow_panel.csv.gz", index=False, compression="gzip")
    print(f"[e2] {len(p)} מסלול-רבעון; עם הפקדות מ-data.gov: {p.has_dep.mean():.0%}")
    rows = []
    for lab, d in (("כל התצפיות", p), ("ללא חריגים (|זרם|<10% מהנכסים)", p[p.y.abs() < 0.10])):
        for cols in (["gain_phys", "gain_syn", "growth_fx"], ["gain_phys", "gain_syn", "growth_fx", "deposits_fx"]):
            dd = d.dropna(subset=cols)
            for wt in (True, False):
                b, se = wls_cluster(dd.assign(FX1=dd.y, FX=0.0), cols, wt)
                r = {"מדגם": lab, "שקלול": "נכסים" if wt else "ללא", "n": len(dd), "עם הפקדות": "deposits_fx" in cols}
                for c, bb, ss in zip(cols, b, se):
                    r[c], r[c + "_se"] = round(bb, 3), round(ss, 3)
                rows.append(r)
    r = pd.DataFrame(rows)
    r.to_csv("data/results/flow_regression.csv", index=False)
    pd.set_option("display.width", 260, "display.max_columns", 20)
    print(r.to_string(index=False))


if __name__ == "__main__":
    main()
