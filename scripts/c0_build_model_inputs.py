"""בניית קלט המודל: שורה למסלול עם משקלי נכסים לפי גורם שוק + מדיניות.

גורמים: US (ארה"ב), ROW (שאר העולם), IL (ישראל).
משקלים (שבר מנכסי המסלול):
  eq_us/eq_row/eq_il        מניות ספוט (מניה ישירה, קרן, קרן נאמנות) - חשופות למט"ח אם נקובות/חשופות
  eq_fx_us/eq_fx_row        החלק מתוכן שחשוף למט"ח (לא מנוטרל)
  dv_us/dv_row/dv_il        נגזרי מניות (החלף/חוזה/אופציה) - לא חשופים למט"ח. מוערך כשארית:
                            החשיפה למניות בפועל (מקובץ המדיניות) פחות מניות ספוט, ומחולק לפי נוציונל יחסי של ההחלפים.
  bond_il / bond_fx         אג"ח (שקלי / במטבע חוץ)
  fx_spot / fx_fwd / fx_net חשיפת מט"ח (ספוט / פורוורד / נטו)
  pol_fx_exp/min/max        יעד, מינימום ומקסימום למט"ח לפי המדיניות המוצהרת (אחוזים)
  act_fx/act_eq             חשיפה בפועל לפי הנתון הרשמי (אחוזים; לבקרה ולגיבוי)
כל המשקלים באחוזים מנכסי המסלול.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

US_IDX = {"sp500", "sp500_esg", "sp500_top50", "nasdaq100", "russell2000", "dow30", "sp400", "tech", "semis", "software",
          "hardware", "consdisc", "comm", "region:us"}
US_RX = re.compile(r"S&P|נסדק|nasdaq|ארה\"?ב|russell|רסל|דאו|dow jones|\bUS\b|USA|VANGUARD (?:TOTAL|S&P)", re.I)


def factor_of(index_key, label, geo, country, il_abroad) -> str:
    if il_abroad == "ישראל" or geo == "IL" or str(index_key).startswith("region:il") or str(index_key).startswith("ta"):
        return "IL"
    k, l, c = str(index_key), str(label), str(country)
    if k in US_IDX or US_RX.search(l) or "ארצות הברית" in c or "ארה" in c:
        return "US"
    return "ROW"


def main(policy_path: Path):
    df = pd.read_csv("data/positions_classified.csv.gz", low_memory=False)
    tt = pd.read_csv("data/track_totals.csv")
    ex = pd.read_csv("data/track_exposure.csv")
    key = ["legal_id", "track"]

    # ── ספוט מניות לפי גורם ──
    eq = df[(df.eq_value_k != 0)].copy()
    eq["factor"] = [factor_of(a, b, c, d, e) for a, b, c, d, e in
                    zip(eq.index_key, eq.index_label, eq.geo, eq.country, eq.il_abroad)]
    # מניה ישירה: גורם לפי מדינה (index_key=stock:..)
    eq["fx_exp"] = eq.fx_route.isin(["direct_ccy", "embedded_unhedged"])
    piv = eq.pivot_table(index=key, columns="factor", values="eq_value_k", aggfunc="sum", fill_value=0.0)
    piv.columns = [f"eq_{c.lower()}_k" for c in piv.columns]
    pfx = eq[eq.fx_exp].pivot_table(index=key, columns="factor", values="eq_value_k", aggfunc="sum", fill_value=0.0)
    pfx.columns = [f"eqfx_{c.lower()}_k" for c in pfx.columns]
    # ── אג"ח ──
    b = df[(df.asset_class == "bond") & (df.form == "BOND") & df.fair_value_k.notna()]
    bd = b.assign(kind=np.where(b.fx_route == "direct_ccy", "bond_fx_k", "bond_il_k")).pivot_table(
        index=key, columns="kind", values="fair_value_k", aggfunc="sum", fill_value=0.0)
    # ── נגזרי מניות: חלוקה יחסית לפי גורם ──
    dn = pd.read_csv("data/deriv_notionals.csv.gz", low_memory=False)
    dn = dn[(dn.asset_class == "equity")].copy()
    dn["factor"] = [factor_of(a, b, g, "", "") for a, b, g in zip(dn.index_key, dn.index_label, dn.geo)]
    dn["w"] = dn.notional_k.abs().where(dn.resolved & (dn.form.str.startswith("SWAP")), 0.0)
    dsh = dn.pivot_table(index=key, columns="factor", values="w", aggfunc="sum", fill_value=0.0)
    for c in ("US", "ROW", "IL"):
        if c not in dsh:
            dsh[c] = 0.0
    dsh = dsh[["US", "ROW", "IL"]]
    dsh = dsh.div(dsh.sum(axis=1).replace(0, np.nan), axis=0)
    dsh.columns = [f"dvsh_{c.lower()}" for c in dsh.columns]

    m = tt.merge(ex[key + ["eq_k", "fx_spot_k", "fx_fwd_k", "fx_net_k"]], on=key, how="left")
    for part in (piv, pfx, bd, dsh):
        m = m.merge(part.reset_index(), on=key, how="left")
    for c in m.columns:
        if c.endswith("_k") and c not in ("total_k",):
            m[c] = m[c].fillna(0.0)
    for c in list(m.columns):
        if c.endswith("_k") and c != "total_k":
            m[c[:-2] + "_pct"] = 100 * m[c] / m.total_k
    # ── מדיניות ──
    pol = json.load(open(policy_path, encoding="utf-8"))["tracks"]
    rows = []
    for k, v in pol.items():
        legal, tn = k.split("|")
        r = {"legal_id": int(legal), "track": float(tn) if tn.replace(".", "").isdigit() else np.nan,
             "pol_name": v.get("name"), "pol_eq_exp": v.get("exp"), "pol_eq_min": v.get("min"), "pol_eq_max": v.get("max"),
             "pol_fx_exp": (v.get("fx") or {}).get("exp"), "pol_fx_min": (v.get("fx") or {}).get("min"),
             "pol_fx_max": (v.get("fx") or {}).get("max"), "pol_bench": v.get("bench"), "policy_date": v.get("effective")}
        for a in v.get("assets", []):
            if a[0].startswith("מניות"):
                r["act_eq"] = a[5]
            if a[0].startswith("חשיפה למט"):
                r["act_fx"] = a[5]
        rows.append(r)
    pv = pd.DataFrame(rows)
    m["track"] = pd.to_numeric(m.track, errors="coerce")
    m = m.merge(pv, on=key, how="left")
    # ── נגזרי מניות כשארית מהחשיפה הרשמית ──
    spot_eq = m[["eq_us_pct", "eq_row_pct", "eq_il_pct"]].sum(axis=1, min_count=1)
    resid = (m.act_eq - spot_eq).clip(lower=0)
    m["dv_total_pct"] = resid.where(m.act_eq.notna(), 0.0).fillna(0.0)
    sh = m[["dvsh_us", "dvsh_row", "dvsh_il"]].fillna(0.0)
    has_sh = sh.sum(axis=1) > 0
    # בלי החלפים מזוהים: מחלקים לפי חלוקת הספוט
    spot_tot = m[["eq_us_pct", "eq_row_pct", "eq_il_pct"]].sum(axis=1).replace(0, np.nan)
    for f in ("us", "row", "il"):
        fall = (m[f"eq_{f}_pct"] / spot_tot).fillna(0.0)
        m[f"dv_{f}_pct"] = m.dv_total_pct * np.where(has_sh, sh[f"dvsh_{f}"], fall)
    m["dv_source"] = np.where(m.act_eq.isna(), "none", np.where(has_sh, "swap_notional_shares", "spot_shares"))
    m = m.drop(columns=[c for c in m.columns if c.startswith("dvsh_")])
    out = Path("data/model_inputs.csv")
    m.to_csv(out, index=False)
    ok = m.dropna(subset=["total_k"])
    print(f"[c0] {len(ok)} מסלולים; עם מדיניות fx: {int(ok.pol_fx_exp.notna().sum())}; עם נתון רשמי: {int(ok.act_fx.notna().sum())}")
    print("[c0] סכום נכסים (טריליון ש\"ח):", round(ok.total_k.sum() / 1e9, 2))
    for f in ("us", "row", "il"):
        print(f"  מניות {f.upper()}: ספוט {ok[f'eq_{f}_k'].sum()/1e9:.3f} טר' | נגזרים (שארית) {(ok[f'dv_{f}_pct']*ok.total_k/100).sum()/1e9:.3f} טר'")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
