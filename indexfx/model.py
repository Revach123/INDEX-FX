"""מנוע האיזון: שוק זז -> כמה מט"ח המסלולים צריכים לקנות/למכור כדי לחזור למדיניות.

כל המשקלים כשבר מנכסי המסלול לפני ההלם (A=1). זרם חיובי = קניית מט"ח (לחץ לייסוף הדולר), שלילי = מכירה.

מבנה התיק לפני ההלם (שבר מהנכסים):
  eqfx_us / eqfx_row   מניות ספוט חשופות מט"ח (מניה/קרן במטבע חוץ או קרן שקלית חשופה)
  eq_us / eq_row       כלל מניות ספוט זרות (כולל מנוטרלות מט"ח)
  eq_il                מניות ספוט ישראל
  dv_us / dv_row / dv_il  נגזרי מניות (החלף/חוזה) - שווים כספי: רווח/הפסד בש"ח, בלי חשיפת מט"ח
  bond_il / bond_fx    אג"ח שקלי / במטבע חוץ
  fx_spot, fx_fwd      חשיפת מט"ח ספוט / פורוורד (בסימן)
  T, lo, hi            יעד/מינימום/מקסימום למט"ח לפי המדיניות

הלם: r_us, r_row (תשואת מדד במטבע המקור, USD), r_il (ת"א), e (שינוי USD/ILS), dy_il, dy_fx (שינוי תשואה, נקודות אחוז).

מכניקה
------
 מניה/קרן במטבע חוץ: שווי בש"ח × (1+r)(1+e). מניה/קרן מנוטרלת: × (1+r) (המגדר מנטרל את e).
 נגזר מניות: רווח/הפסד = משקל × r בש"ח; אין חשיפת מט"ח (רק הפרש ריבית) - ולכן A גדל בלי שה-FX גדל.
 פורוורד: שווי נוציונל במט"ח × (1+e).
 A' = 1 + סך הרווחים. fx' = (FXספוט' + FXפורוורד') / A'.

כלל פעולה (mode):
  "continuous": נדרש לשנות חשיפה ב-λ × [(T·A' − FX') − (T − fx0)·1]  (רק המרכיב שנגרם מההלם)
  "band":       מסלול שחצה את הטווח [lo,hi] בעקבות ההלם חוזר ליעד T (λ=1 על הפער); מי שנשאר בטווח לא פועל.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Params:
    lam: float = 1.0            # שיעור ההתאמה שמתבצע באופק (0..1)
    mode: str = "continuous"    # continuous | band
    dur_il: float = 5.0         # מח"מ אג"ח שקלי
    dur_fx: float = 6.0         # מח"מ אג"ח מט"ח
    usdils: float = 3.19        # שער לתרגום ש"ח לדולר


def _col(df: pd.DataFrame, name: str) -> np.ndarray:
    return (df[name].to_numpy(dtype=float) / 100.0) if name in df else np.zeros(len(df))


def prepare(m: pd.DataFrame) -> pd.DataFrame:
    """משקלים כשברים + fx0 (נתון רשמי אם יש, אחרת מחושב) + יעד/טווח. מסלול בלי יעד מדיניות -> יעד = fx0 (אין כוח משיכה)."""
    d = m.copy()
    d = d[d.total_k.notna() & (d.total_k > 0)].copy()
    for c in ("eqfx_us", "eqfx_row", "eq_us", "eq_row", "eq_il", "dv_us", "dv_row", "dv_il", "bond_il", "bond_fx",
              "fx_spot", "fx_fwd", "fx_net"):
        d[c + "_w"] = _col(d, c + "_pct")
    fx0 = np.where(d.act_fx.notna(), d.act_fx / 100.0, d.fx_net_w)
    d["fx0"] = fx0
    d["T"] = np.where(d.pol_fx_exp.notna(), d.pol_fx_exp / 100.0, fx0)
    d["lo"] = np.where(d.pol_fx_min.notna(), d.pol_fx_min / 100.0, d["T"])
    d["hi"] = np.where(d.pol_fx_max.notna(), d.pol_fx_max / 100.0, d["T"])
    d["has_policy"] = d.pol_fx_exp.notna()
    return d


def shock_flows(d: pd.DataFrame, r_us=0.0, r_row=0.0, r_il=0.0, e=0.0, dy_il=0.0, dy_fx=0.0, p: Params = Params()) -> pd.DataFrame:
    """חישוב לכל מסלול. מחזיר עותק של d עם fx_new, A_new, flow_ils_k, flow_usd_m."""
    g = lambda c: d[c + "_w"].to_numpy()  # noqa: E731
    r_bil = -p.dur_il * dy_il / 100.0
    r_bfx = -p.dur_fx * dy_fx / 100.0
    fx_eq = g("eqfx_us") * (1 + r_us) * (1 + e) + g("eqfx_row") * (1 + r_row) * (1 + e)
    rest_fx = g("fx_spot") - g("eqfx_us") - g("eqfx_row") - g("bond_fx")
    fx_spot_new = fx_eq + g("bond_fx") * (1 + r_bfx) * (1 + e) + rest_fx * (1 + e)
    fx_fwd_new = g("fx_fwd") * (1 + e)
    gain = (
        (g("eqfx_us") * ((1 + r_us) * (1 + e) - 1) + g("eqfx_row") * ((1 + r_row) * (1 + e) - 1))
        + (g("eq_us") - g("eqfx_us")) * r_us + (g("eq_row") - g("eqfx_row")) * r_row
        + g("eq_il") * r_il
        + g("dv_us") * r_us + g("dv_row") * r_row + g("dv_il") * r_il
        + g("bond_il") * r_bil + g("bond_fx") * ((1 + r_bfx) * (1 + e) - 1)
        + rest_fx * e + g("fx_fwd") * e
    )
    A_new = 1.0 + gain
    fx_new = (fx_spot_new + fx_fwd_new) / A_new
    T, lo, hi, fx0 = d["T"].to_numpy(), d["lo"].to_numpy(), d["hi"].to_numpy(), d["fx0"].to_numpy()
    # מצב התחלתי: חשיפה רשמית (fx0) כנקודת מוצא; הדינמיקה מהרכב התיק. הפער ביניהם נשמר כקבוע ולא נספר כזרם.
    fx_model0 = g("fx_spot") + g("fx_fwd")
    fx_new_adj = fx_new + (fx0 - fx_model0) / A_new
    # כמה חשיפה "חסרה/עודפת" מול היעד, במונחי נכסים נוכחיים, ביחס למצב לפני ההלם
    gap_new = T * A_new - fx_new_adj * A_new
    gap_old = T - fx0
    incr = gap_new - gap_old
    if p.mode == "band":
        in_old = (fx0 >= lo) & (fx0 <= hi)
        out_new = (fx_new_adj < lo) | (fx_new_adj > hi)
        need = np.where(out_new & in_old, gap_new, np.where(out_new & ~in_old, incr, 0.0))
    else:
        need = incr
    flow = p.lam * need * d.total_k.to_numpy()   # אלפי ש"ח (נוכחי: A=total_k)
    out = d.copy()
    out["A_new"], out["fx_new"], out["flow_ils_k"] = A_new, fx_new_adj, flow
    out["flow_usd_m"] = flow * 1000.0 / p.usdils / 1e6
    return out


def total_flow_usd_m(d: pd.DataFrame, **kw) -> float:
    return float(shock_flows(d, **kw).flow_usd_m.sum())


def decompose(d: pd.DataFrame, r_us=0.0, r_row=0.0, r_il=0.0, e=0.0, dy_il=0.0, dy_fx=0.0, p: Params = Params()) -> dict:
    """תרומה לפי מקור הלם (כל אחד לבד) וחלוקה לפי ערוץ: החזקה ישירה / נגזר / אחר."""
    base = dict(r_us=r_us, r_row=r_row, r_il=r_il, e=e, dy_il=dy_il, dy_fx=dy_fx)
    res = {"total": total_flow_usd_m(d, p=p, **base)}
    for k, v in base.items():
        if v:
            res[f"only_{k}"] = total_flow_usd_m(d, p=p, **{k: v})
    return res
