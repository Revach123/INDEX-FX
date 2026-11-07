"""מודל v2 על הדוגמה מהמאמר: מניות חו"ל 30% (פיזי 8%), מניות ארץ 20%, אג"ח 50%, מט"ח 19%.
הלם: חו"ל +10%, ארץ +5%, אג"ח +5% (המאמר מניח 5% על כל תיק האג"ח - כאן כ-dy שקולה)."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indexfx.model2 import P2, track_flows  # noqa: E402


def ex():
    return pd.DataFrame([dict(U_phys_us=0.08, U_phys_row=0.0, U_syn_us=0.22, U_syn_row=0.0, fx_ilf=0.0, eqfr_ilf=0.0,
                              E_il=0.20, B_il=0.50, B_fx=0.0, FX0=0.19, T=0.19, total_k=1.0)])


def test_article_example_synthetic_gain_in_usd():
    # dy_il=-1 עם מח"מ 5 -> אג"ח +5%. A' = 1 + 0.03 + 0.01 + 0.025 = 1.065
    o = track_flows(ex(), r_us=0.10, r_il=0.05, dy_il=-1.0, p=P2(usdils=1.0))
    assert o.A1.iloc[0] == pytest.approx(1.065)
    assert o.FX1.iloc[0] == pytest.approx(0.22)              # 19% + 10%×30% (כל הרווח הזר בדולר)
    assert o.flow_k.iloc[0] == pytest.approx(0.19 * 1.065 - 0.22)   # -1.765% מהנכסים = מכירה


def test_article_example_if_synthetic_gain_were_shekel():
    o = track_flows(ex(), r_us=0.10, r_il=0.05, dy_il=-1.0, p=P2(usdils=1.0, synthetic_usd=False))
    assert o.FX1.iloc[0] == pytest.approx(0.198)             # רק הפיזי 8%×10%
    assert o.flow_k.iloc[0] == pytest.approx(0.19 * 1.065 - 0.198)  # +0.44% = קנייה


def test_no_shock_no_flow():
    assert track_flows(ex()).flow_k.iloc[0] == pytest.approx(0.0)


def test_swap_gain_is_return_minus_usd_interest():
    # 30% סינתטי בלבד, 10% עלייה ברבעון, ריבית דולרית 4%: הרווח הדולרי = 30% × (10% − 1%) = 2.7%
    d = ex().assign(U_phys_us=0.0, U_syn_us=0.30, E_il=0.0, B_il=0.70)
    o = track_flows(d, r_us=0.10, p=P2(usdils=1.0, usd_rate=0.04, horizon_years=0.25))
    assert o.FX1.iloc[0] == pytest.approx(0.19 + 0.30 * 0.09)
