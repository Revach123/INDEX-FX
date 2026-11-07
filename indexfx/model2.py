"""מודל v2 - מבוסס פירוק מדויק לפי צורת השקעה (a7) והתנהגות קרנות שנמדדה (b3).

מסלול (שברים מהנכסים לפני ההלם):
  U_us, U_row   חשיפה למניות חו"ל שהרווח עליה נצבר בדולר:
                מניות ישירות + קרנות זרות (נקובות מט"ח) + החלפים (רגליים בדולר - נבדק: 204+32 מיליארד ש"ח מתוך כ-250)
                + חוזים עתידיים (מרווח בדולר).
  syn_il_fx     שיעור חשיפת המניות-בחו"ל שבאה דרך קרנות ישראליות (הקרן עצמה מנהלת את המט"ח שלה, לפי fx_pct שלה)
  E_il          מניות ישראל (רווח בשקלים)
  B_il, B_fx    אג"ח שקלי / מט"ח
  FX0           חשיפת מט"ח רשמית; T יעד מדיניות
הלם: r_us, r_row, r_il (תשואות), e (שינוי USD/ILS), dy_il, dy_fx.
FX אחרי הלם, לפני פעולה: FX0·(1+e) + (U_us·r_us + U_row·r_row)(1+e) + fx_il_funds·r_fr(1+e) + B_fx·rb_fx(1+e)
A' = 1 + סך הרווחים.  זרם המסלול (קניית מט"ח) = λ·[T·A' − FX'] − λ·(T − FX0)   (רק מה שנגרם מההלם).

הנחת "רווח סינתטי בשקלים" (כפי שהמאמר מניח) זמינה כ-synthetic_usd=False - לשם השוואה בלבד.

קרנות לא מגודרות (קהל, לא מסלולים): זרם = κ · r · AUM, κ נמדד (b3: 0.67 בחלון 10 ימים; ארוך טווח ≤1).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class P2:
    lam: float = 1.0
    synthetic_usd: bool = True   # נבדק בנתונים: True
    dur_il: float = 5.0
    dur_fx: float = 6.0
    usdils: float = 3.19
    kappa_unhedged: float = 0.67  # b3, חלון 10 ימים


def track_flows(t: pd.DataFrame, r_us=0.0, r_row=0.0, r_il=0.0, e=0.0, dy_il=0.0, dy_fx=0.0, p: P2 = P2()) -> pd.DataFrame:
    """t: עמודות (שברים): U_phys_us, U_phys_row, U_syn_us, U_syn_row, fx_ilf (מט"ח דרך קרנות ישראליות), eqfr_ilf,
    E_il, B_il, B_fx, FX0, T, total_k."""
    rb_il, rb_fx = -p.dur_il * dy_il / 100, -p.dur_fx * dy_fx / 100
    phys_gain = t.U_phys_us * r_us + t.U_phys_row * r_row
    syn_gain = t.U_syn_us * r_us + t.U_syn_row * r_row
    r_fr = np.where((t.U_phys_us + t.U_syn_us + t.U_phys_row + t.U_syn_row) > 0,
                    (t.U_phys_us + t.U_syn_us) * r_us + (t.U_phys_row + t.U_syn_row) * r_row, 0.0)
    r_fr = r_fr / np.maximum(t.U_phys_us + t.U_syn_us + t.U_phys_row + t.U_syn_row, 1e-12)
    ilf_gain = t.eqfr_ilf * r_fr
    gain = phys_gain + syn_gain + ilf_gain + t.E_il * r_il + t.B_il * rb_il + t.B_fx * rb_fx * (1 + e) + t.FX0 * e
    A1 = 1 + gain
    usd_auto = phys_gain + (syn_gain if p.synthetic_usd else 0.0) + t.fx_ilf * r_fr + t.B_fx * rb_fx
    FX1 = (t.FX0 + usd_auto) * (1 + e)
    need = (t["T"] * A1 - FX1) - (t["T"] - t.FX0)
    out = t.copy()
    out["A1"], out["FX1"] = A1, FX1
    out["flow_k"] = p.lam * need * t.total_k
    out["flow_usd_m"] = out.flow_k * 1000 / p.usdils / 1e6
    # פירוק: (1) רווח דולרי שעולה מעל היעד; (2) הגדלת היעד כי הנכסים גדלו
    out["part_usd_gain_usd_m"] = -p.lam * usd_auto * t.total_k * 1000 / p.usdils / 1e6
    out["part_target_growth_usd_m"] = p.lam * t["T"] * (A1 - 1) * t.total_k * 1000 / p.usdils / 1e6
    return out


def unhedged_funds_flow_usd_m(aum_bn_ils: float, r: float, p: P2 = P2()) -> float:
    return p.kappa_unhedged * r * aum_bn_ils * 1e9 / p.usdils / 1e6
