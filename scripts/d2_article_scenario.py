"""תרחיש המאמר על הנתונים האמיתיים: מדדי חו"ל +10%, ת"א +5%, אג"ח +5%.

מסלולים (a7 - פירוק מדויק) + קרנות מחקות לא מגודרות (b2 - שווי רשמי; b3 - התנהגות נמדדת).
פלט: data/results/article_scenario.csv + הדפסה. כל המספרים במיליארדי ש"ח (חיובי = קניית מט"ח).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from indexfx.model2 import P2, track_flows  # noqa: E402
from indexfx.vendor.index_classify import classify_index  # noqa: E402
from d1_article_claims import SPECIFIC  # noqa: E402

US_IDX = {"sp500", "sp500_esg", "sp500_top50", "nasdaq100", "russell2000", "dow30", "sp400", "region:us", "msci_usa"}
US_RX = re.compile(r"S&P|SPX|SPTR|NDX|XNDX|NASDAQ|נסד|נאסד|RUSSELL|RTY|DOW|ארה\"?ב|\bUS\b|USA|S5|IXT|IXC|IXY|IXV", re.I)


def is_us(text) -> bool:
    t = str(text or "")
    k = classify_index(t)[0]
    return k in US_IDX or k.endswith(":us") or bool(US_RX.search(t))


def build_inputs() -> pd.DataFrame:
    o = pd.read_csv("data/track_decomposition.csv")
    KEY = ["legal_id", "track"]
    # חלק ארה"ב בפיזי (מניות ישירות + קרנות זרות) לפי ההחזקות
    df = pd.read_csv("data/positions_classified.csv.gz", low_memory=False)
    df["track"] = pd.to_numeric(df.track, errors="coerce")
    ph = df[(df.form.isin(["STOCK_DIRECT", "WARRANT"]) & df.il_abroad.eq("חו\"ל")) |
            (df.form.isin(["ETF", "MUTUAL_FUND"]) & df.fx_route.eq("direct_ccy") & df.asset_class.eq("equity"))].copy()
    ph["us"] = ph.country.astype(str).str.contains("ארצות הברית|ארה") | np.array([is_us(f"{a} {b}") for a, b in zip(ph.index_label, ph.fund_class)])
    ph_us = (ph.fair_value_k * ph.us).groupby([ph.legal_id, ph.track]).sum() / ph.fair_value_k.groupby([ph.legal_id, ph.track]).sum()
    dx = pd.read_csv("data/deriv_exact.csv.gz", low_memory=False)
    dx["track"] = pd.to_numeric(dx.track, errors="coerce")
    dx = dx[(dx.equity == True) & ~(dx.country.eq("ישראל") | (dx.ccy.eq("ILS") & dx.leg2_ccy.fillna("ILS").eq("ILS")))].copy()  # noqa: E712
    dx["exp"] = dx.ratio * dx.total_k
    dx["us"] = [is_us(f"{a} {b} {c}") for a, b, c in zip(dx.ticker, dx.name, dx.root)]
    sy_us = (dx.exp * dx.us).groupby([dx.legal_id, dx.track]).sum() / dx.exp.groupby([dx.legal_id, dx.track]).sum()
    o = o.set_index(KEY)
    o["us_phys"] = ph_us.reindex(o.index).fillna(0.5)
    o["us_syn"] = sy_us.reindex(o.index).fillna(0.5)
    o = o.reset_index()
    f = lambda c: o[c].fillna(0) / 100  # noqa: E731
    phys = f("eq_fr_phys") + f("eq_fr_fund_foreign")
    syn = f("eq_fr_swap") + f("eq_fr_future") + (f("eq_fr_option") if "eq_fr_option" in o else 0)
    bonds = pd.read_csv("data/model_inputs.csv")[KEY + ["bond_il_pct", "bond_fx_pct"]]
    o = o.merge(bonds, on=KEY, how="left")
    t = pd.DataFrame({
        "legal_id": o.legal_id, "track": o.track, "name": o.name.fillna(""), "system": o.system, "total_k": o.total_k,
        "U_phys_us": phys * o.us_phys, "U_phys_row": phys * (1 - o.us_phys),
        "U_syn_us": syn * o.us_syn, "U_syn_row": syn * (1 - o.us_syn),
        "eqfr_ilf": f("eq_fr_fund_il"), "fx_ilf": f("fx_il_funds"),
        "E_il": f("eq_il_total"), "B_il": o.bond_il_pct.fillna(0) / 100, "B_fx": o.bond_fx_pct.fillna(0) / 100,
        "FX0": np.where(o.act_fx.notna(), o.act_fx / 100, o.fx_total / 100)})
    t["T"] = np.where(o.pol_fx.notna(), o.pol_fx / 100, t.FX0)
    t["general"] = (t.name != "") & ~t.name.str.contains(SPECIFIC)
    return t


def main():
    t = build_inputs()
    t.to_csv("data/model2_inputs.csv", index=False)
    funds = pd.read_csv("data/funds/funds.csv", dtype={"fund": str})
    fe = funds[funds.primary.eq("מניות בחו\"ל") & funds.mimic & funds.aum_m.notna()]
    unh_bn, hed_bn = fe[~fe.hedged].aum_m.sum() / 1e3, fe[fe.hedged].aum_m.sum() / 1e3
    sc = dict(r_us=0.10, r_row=0.10, r_il=0.05, dy_il=-1.0)  # אג"ח שקלי +5% (מח"מ 5)
    rows = []
    for lab, sub in (("מסלולים כלליים", t[t.general]), ("כל המסלולים", t)):
        for syn_usd in (True, False):
            o = track_flows(sub, **sc, p=P2(synthetic_usd=syn_usd, usdils=1.0))
            bn = lambda c: o[c].sum() / 1e3  # noqa: E731  (flow_usd_m עם usdils=1 = מיליוני ש"ח -> מיליארדים)
            rows.append({"קבוצה": lab, "הנחה": "רווח סינתטי בדולר (כפי שבדוחות)" if syn_usd else "רווח סינתטי בשקל (הנחת המאמר)",
                         "נכסים": sub.total_k.sum() / 1e6, "זרם נטו": bn("flow_usd_m"),
                         "מכירת רווח דולרי": bn("part_usd_gain_usd_m"), "קנייה בגלל גידול היעד": bn("part_target_growth_usd_m"),
                         "מתוכו רווח פיזי": -((sub.U_phys_us + sub.U_phys_row) * 0.10 * sub.total_k).sum() / 1e6,
                         "מתוכו רווח סינתטי": -((sub.U_syn_us + sub.U_syn_row) * 0.10 * sub.total_k).sum() / 1e6 if syn_usd else 0.0})
    # התנהגות נמדדת (d3, מדגם ללא חריגים, משוקלל לפי נכסים): איזה חלק מכל רכיב קוזז בפועל בתוך רבעון
    rt = Path("data/results/rebalancing_test.csv")
    if rt.exists():
        b = pd.read_csv(rt)
        b = b[b["מדגם"].str.contains("ללא חריגים") & b["שקלול"].eq("לפי נכסים")].iloc[0]
        for lab, sub in (("מסלולים כלליים", t[t.general]), ("כל המסלולים", t)):
            o = track_flows(sub, **sc, p=P2(usdils=1.0))
            gp = ((sub.U_phys_us + sub.U_phys_row) * 0.10 * sub.total_k).sum() / 1e6
            # ברבעון: הרווח הדולרי בהחלף/חוזה = תשואה פחות ריבית דולרית על הנוציונל (^IRX האחרון × רבעון)
            i_usd = pd.read_csv("data/market/prices.csv").query("symbol == '^IRX'").close.iloc[-1] / 100
            gs = ((sub.U_syn_us + sub.U_syn_row) * (0.10 - i_usd * 0.25) * sub.total_k).sum() / 1e6
            den = o.part_target_growth_usd_m.sum() / 1e3
            flow = -(1 - b["רווח פיזי – חלק שנשאר"]) * gp - (1 - b["רווח סינתטי – חלק שנשאר"]) * gs + (1 - b["אפקט מכנה – חלק שנשאר"]) * den
            rows.append({"קבוצה": lab, "הנחה": "איזון בפועל כפי שנמדד (רבעון, d3; סינתטי: תשואה פחות ריבית)", "נכסים": sub.total_k.sum() / 1e6, "זרם נטו": flow,
                         "מכירת רווח דולרי": -(1 - b["רווח פיזי – חלק שנשאר"]) * gp - (1 - b["רווח סינתטי – חלק שנשאר"]) * gs,
                         "קנייה בגלל גידול היעד": (1 - b["אפקט מכנה – חלק שנשאר"]) * den})
    # התנהגות חודשית נמדדת על החשיפה הרשמית (d5, ללא חריגים, משוקלל): שומרים על שיעור המט"ח הקיים (לא על היעד המוצהר)
    pm = Path("data/results/policy_monthly.csv")
    if pm.exists():
        m = pd.read_csv(pm)
        m = m[m["מבחן"].str.startswith("A") & m["מדגם"].str.contains("ללא חריגים") & m["שקלול"].eq("נכסים")].iloc[0]
        for lab, sub in (("מסלולים כלליים", t[t.general]), ("כל המסלולים", t)):
            o = track_flows(sub.assign(T=sub.FX0), **sc, p=P2(usdils=1.0))   # יעד = השיעור הקיים
            gp = ((sub.U_phys_us + sub.U_phys_row) * 0.10 * sub.total_k).sum() / 1e6
            gs = ((sub.U_syn_us + sub.U_syn_row) * 0.10 * sub.total_k).sum() / 1e6
            den = o.part_target_growth_usd_m.sum() / 1e3
            sell = -(1 - m["רווח פיזי"]) * gp - (1 - m["רווח סינתטי"]) * gs
            buy = (1 - m["מכנה"]) * den
            rows.append({"קבוצה": lab, "הנחה": "שמירת שיעור המט\"ח הקיים, כפי שנמדד בחודש (d5, רשמי)", "נכסים": sub.total_k.sum() / 1e6,
                         "זרם נטו": sell + buy, "מכירת רווח דולרי": sell, "קנייה בגלל גידול היעד": buy,
                         "מתוכו רווח פיזי": -(1 - m["רווח פיזי"]) * gp, "מתוכו רווח סינתטי": -(1 - m["רווח סינתטי"]) * gs})
    # κ נמדד על כל קרנות הסל המחקות על חו"ל (b3b, 130 לא מגודרות / 94 מגודרות), חלון 20 ימי הרכב ≈ חודש
    ha = pd.read_csv("data/funds/etf_hedge_all.csv")
    ha = ha[ha["חלון (ימים)"] == 20].set_index("קבוצה")["κ (קנייה מכל 1% עלייה)"]
    k_u, k_h = ha["לא מגודרת 4D"], ha["מגודרת 4A"]
    rows.append({"קבוצה": f"קרנות מחקות לא מגודרות (κ={k_u:.2f}, נמדד בחודש)", "הנחה": "b3b", "נכסים": unh_bn, "זרם נטו": k_u * 0.10 * unh_bn})
    rows.append({"קבוצה": "קרנות מחקות לא מגודרות (κ=1, המרה מלאה)", "הנחה": "גבול עליון", "נכסים": unh_bn, "זרם נטו": 0.10 * unh_bn})
    rows.append({"קבוצה": f"קרנות מחקות מגודרות (κ={k_h:.2f}, נמדד בחודש)", "הנחה": "b3b", "נכסים": hed_bn, "זרם נטו": k_h * 0.10 * hed_bn})
    r = pd.DataFrame(rows).round(2)
    r.to_csv("data/results/article_scenario.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 20)
    print("תרחיש: חו\"ל +10%, ת\"א +5%, אג\"ח שקלי +5% | מיליארדי ש\"ח, חיובי = קניית מט\"ח")
    print(r.to_string(index=False))


if __name__ == "__main__":
    main()
