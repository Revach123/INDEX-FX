"""שלב א.7 - פירוק מדויק לכל מסלול: מאיפה מגיעה החשיפה למניות (ארץ/חו"ל) ולמט"ח, לפי צורת ההשקעה.

כל הרכיבים כשבר מנכסי המסלול, מהדוח הרבעוני האחרון:
 מניות:
   eq_il_phys          מניות ישראליות שמוחזקות ישירות (שווי הוגן)
   eq_fr_phys          מניות זרות שמוחזקות ישירות
   eq_fr_fund_foreign  קרנות/תעודות סל זרות (נקובות במט"ח) על מניות - החזקה במטבע חוץ
   eq_il_fund / eq_fr_fund_il   קרנות ישראליות (סל/נאמנות) × שיעור החשיפה למניות הרשמי של הקרן (Maya); לפי סיווג (ארץ/חו"ל)
   eq_*_swap / eq_*_future / eq_*_option   נגזרים - חשיפה מחושבת בקוד המאומת (a6), ארץ/חו"ל לפי מטבע/מדינה
 מט"ח:
   fx_spot_direct      כל נכס נקוב במטבע חוץ (מניות, אג"ח, מזומן, קרנות זרות, הלוואות...)
   fx_il_funds         קרנות ישראליות × שיעור החשיפה למט"ח הרשמי של הקרן
   fx_forwards         פורוורדים/החלפי מט"ח - רגליים לא-שקליות בסימן (a2)
   fx_deriv_mtm        שווי הוגן נטו של החלפי מניות וחוזים במטבע חוץ (הרווח הצבור שטרם הומר - "ההפרש")
פלט: data/track_decomposition.csv ; אימות מול הנתון הרשמי (מניות/מט"ח) מודפס ונשמר.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

KEY = ["legal_id", "track"]


def main(policy_path: Path):
    df = pd.read_csv("data/positions_classified.csv.gz", low_memory=False, dtype={"sec_id": str})
    df["track"] = pd.to_numeric(df.track, errors="coerce")
    tt = pd.read_csv("data/track_totals.csv")
    tt["track"] = pd.to_numeric(tt.track, errors="coerce")
    tot = tt.set_index(KEY).total_k

    funds = pd.read_csv("data/funds/funds.csv", dtype={"fund": str})
    fref = funds.set_index("fund")[["eq_pct", "fx_pct", "primary", "mimic", "hedged"]]

    parts = {}

    def add(name, s):
        parts[name] = s.groupby([s.index.get_level_values(0), s.index.get_level_values(1)]).sum() if isinstance(s.index, pd.MultiIndex) else s

    fv = df.set_index(KEY).fair_value_k.fillna(0.0)
    is_abroad = df.il_abroad.eq("חו\"ל").values
    stock = df.form.isin(["STOCK_DIRECT", "WARRANT"]).values
    add("eq_il_phys", fv[stock & ~is_abroad])
    add("eq_fr_phys", fv[stock & is_abroad])

    fundrow = df.form.isin(["ETF", "MUTUAL_FUND"]).values
    fnum = df.sec_id.str.extract(r"^IL00(\d+)\d$")[0].str.lstrip("0")
    il_fund = fundrow & fnum.isin(fref.index).values
    foreign_ccy = (df.fx_route == "direct_ccy").values
    eqcls = (df.asset_class == "equity").values
    add("eq_fr_fund_foreign", fv[fundrow & ~il_fund & foreign_ccy & eqcls])
    ref = fref.reindex(fnum[il_fund].values)
    ilf = df[il_fund].copy()
    ilf["eq_w"] = ref.eq_pct.fillna(0).values / 100.0
    ilf["fx_w"] = ref.fx_pct.fillna(0).values / 100.0
    ilf["foreign_eq"] = ref.primary.eq("מניות בחו\"ל").values
    ilv = ilf.set_index(KEY).fair_value_k.fillna(0.0)
    add("eq_fr_fund_il", (ilv * ilf.eq_w.values)[ilf.foreign_eq.values])
    add("eq_il_fund", (ilv * ilf.eq_w.values)[~ilf.foreign_eq.values])
    add("fx_il_funds", ilv * ilf.fx_w.values)
    # מט"ח ספוט: כל מה שנקוב במט"ח, חוץ מקרנות ישראליות (נספרו לפי הדוח שלהן) ונגזרים
    spot_forms = ~df.form.isin(["FUTURE", "OPTION", "SWAP_EQ_UNFUNDED", "SWAP_EQ_FUNDED", "SWAP_RATE", "SWAP_OTHER",
                                "FX_FWD_UNFUNDED", "FX_FWD_FUNDED"]).values
    add("fx_spot_direct", fv[spot_forms & foreign_ccy & ~il_fund])
    fw = pd.read_csv("data/fx_forward_legs.csv.gz")
    fw["track"] = pd.to_numeric(fw.track, errors="coerce")
    parts["fx_forwards"] = fw.groupby(KEY).fx_exposure_k.sum()
    # רווח צבור על החלפי/חוזי מניות במט"ח
    dmtm = df.form.isin(["SWAP_EQ_UNFUNDED", "SWAP_EQ_FUNDED", "FUTURE"]).values & \
        ((df.leg2_ccy.fillna("ILS") != "ILS") | (df.leg1_ccy.fillna("ILS") != "ILS") | (df.ccy.fillna("ILS") != "ILS")).values
    add("fx_deriv_mtm", fv[dmtm])

    # נגזרים מדויקים (a6): ratio = שבר מהנכסים
    dx = pd.read_csv("data/deriv_exact.csv.gz", low_memory=False)
    dx["track"] = pd.to_numeric(dx.track, errors="coerce")
    dx = dx[dx.equity == True].copy()  # noqa: E712
    il = (dx.ccy.eq("ILS") & dx.leg2_ccy.fillna("ILS").eq("ILS")) | dx.country.eq("ישראל")
    dx["side"] = np.where(il, "il", "fr")
    dx["cat"] = dx.category.str.replace("OPTION_LISTED", "option").str.replace("OPTION_OTC", "option").str.lower()
    dx["exp_k"] = dx.ratio * dx.total_k   # חשיפה בש"ח (אלפים) - יחס a6 × סך הנכסים שלפיו חושב
    for (side, cat), g in dx.groupby(["side", "cat"]):
        parts[f"eq_{side}_{cat}"] = g.groupby(KEY).exp_k.sum()

    out = pd.DataFrame(index=tot.index)
    out["total_k"] = tot
    for k, s in parts.items():
        s.index = s.index.set_names(KEY)
        if k.endswith("_ratio"):
            out[k.replace("_ratio", "")] = s.reindex(out.index).fillna(0.0) * 100
        else:
            out[k] = s.reindex(out.index).fillna(0.0) / out.total_k * 100
    out = out.fillna(0.0).reset_index()
    eqc = [c for c in out.columns if c.startswith("eq_")]
    out["eq_total"] = out[eqc].sum(axis=1)
    out["eq_fr_total"] = out[[c for c in eqc if c.startswith("eq_fr")]].sum(axis=1)
    out["eq_il_total"] = out[[c for c in eqc if c.startswith("eq_il")]].sum(axis=1)
    out["eq_fr_physical"] = out.eq_fr_phys + out.eq_fr_fund_foreign
    out["fx_total"] = out[["fx_spot_direct", "fx_il_funds", "fx_forwards", "fx_deriv_mtm"]].sum(axis=1)

    pol = json.load(open(policy_path, encoding="utf-8"))["tracks"]
    rows = []
    for k, v in pol.items():
        legal, tn = k.split("|")
        r = {"legal_id": int(legal), "track": pd.to_numeric(tn, errors="coerce"), "name": v.get("name"),
             "pol_eq": v.get("exp"), "pol_fx": (v.get("fx") or {}).get("exp"), "bench": v.get("bench"), "parts": v.get("parts")}
        for a in v.get("assets", []):
            if a[0].startswith("מניות"):
                r["act_eq"] = a[5]
            if a[0].startswith("חשיפה למט"):
                r["act_fx"] = a[5]
        rows.append(r)
    out = out.merge(pd.DataFrame(rows), on=KEY, how="left")
    out = out.merge(tt[KEY + ["system", "report_date"]], on=KEY, how="left")
    out.to_csv("data/track_decomposition.csv", index=False)

    for col, act in (("eq_total", "act_eq"), ("fx_total", "act_fx")):
        m = out.dropna(subset=[act])
        d = m[col] - m[act]
        w = m.total_k
        print(f"{col} מול {act}: n={len(m)}  MAE={d.abs().mean():.2f}  חציון={d.abs().median():.2f}  בתוך 2pp={100*(d.abs()<=2).mean():.0f}%  "
              f"בתוך 5pp={100*(d.abs()<=5).mean():.0f}%  MAE משוקלל-נכסים={np.average(d.abs(), weights=w):.2f}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
