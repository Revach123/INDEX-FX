"""בדיקות יחידה למנוע האיזון - מקרים שמחושבים ביד."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indexfx.model import Params, prepare, shock_flows  # noqa: E402


def track(**kw):
    base = dict(total_k=1_000_000, eqfx_us_pct=0, eqfx_row_pct=0, eq_us_pct=0, eq_row_pct=0, eq_il_pct=0,
                dv_us_pct=0, dv_row_pct=0, dv_il_pct=0, bond_il_pct=0, bond_fx_pct=0, fx_spot_pct=0, fx_fwd_pct=0,
                fx_net_pct=0, act_fx=None, pol_fx_exp=None, pol_fx_min=None, pol_fx_max=None)
    base.update(kw)
    return pd.DataFrame([base])


def flow(df, **shock):
    return shock_flows(prepare(df), p=Params(usdils=1.0), **shock).flow_ils_k.iloc[0]


def test_direct_holder_sells_fx_when_index_up():
    # 50% ב-S&P ישיר (חשוף מט"ח), 50% שקלי; יעד מט"ח 50%. עלייה 10%: FX=0.55, A=1.05 -> נדרש 0.525 -> מכירה 0.025
    t = track(eqfx_us_pct=50, eq_us_pct=50, fx_spot_pct=50, fx_net_pct=50, pol_fx_exp=50, pol_fx_min=40, pol_fx_max=60)
    assert flow(t, r_us=0.10) == pytest.approx(-0.025 * 1_000_000, rel=1e-9)


def test_swap_holder_buys_fx_when_index_up():
    # 50% חשיפה ל-S&P דרך החלף (אין מט"ח), פורוורד קונה דולר 50%, יעד 50%. עלייה 10%: A=1.05, FX=0.5 -> נדרש 0.525 -> קנייה 0.025
    t = track(dv_us_pct=50, fx_fwd_pct=50, fx_net_pct=50, pol_fx_exp=50, pol_fx_min=40, pol_fx_max=60)
    assert flow(t, r_us=0.10) == pytest.approx(+0.025 * 1_000_000, rel=1e-9)


def test_no_foreign_exposure_no_flow():
    t = track(eq_il_pct=60, bond_il_pct=40, pol_fx_exp=0, pol_fx_min=0, pol_fx_max=5)
    assert flow(t, r_us=0.2) == pytest.approx(0.0)
    assert flow(t, r_il=0.2) == pytest.approx(0.0, abs=1e-6)


def test_domestic_rally_with_fx_target_forces_fx_purchase():
    # 50% ת"א, 50% פורוורד USD ארוך 20%, יעד 20%: ת"א +10% -> A=1.05; FX=0.2 -> נדרש 0.21 -> קנייה 0.01
    t = track(eq_il_pct=50, fx_spot_pct=0, fx_fwd_pct=20, fx_net_pct=20, pol_fx_exp=20, pol_fx_min=10, pol_fx_max=30)
    assert flow(t, r_il=0.10) == pytest.approx(0.01 * 1_000_000, rel=1e-9)


def test_band_mode_inside_band_no_action_and_crossing_trades_to_target():
    t = track(eqfx_us_pct=50, eq_us_pct=50, fx_spot_pct=50, fx_net_pct=50, pol_fx_exp=50, pol_fx_min=48, pol_fx_max=52)
    small = shock_flows(prepare(t), r_us=0.02, p=Params(mode="band", usdils=1.0)).flow_ils_k.iloc[0]
    assert small == 0.0   # FX'=0.51/1.01=0.505 בתוך הטווח
    big = shock_flows(prepare(t), r_us=0.10, p=Params(mode="band", usdils=1.0)).flow_ils_k.iloc[0]
    assert big == pytest.approx(-0.025 * 1_000_000, rel=1e-9)  # FX'=0.55/1.05=0.5238 -> חצה 0.52 -> חזרה ליעד


def test_fx_move_alone_on_unhedged_track():
    # 50% נכס במט"ח (ללא מדד), יעד 50%: דולר +10% -> FX=0.55, A=1.05 -> נדרש 0.525 -> מכירה 0.025
    t = track(fx_spot_pct=50, fx_net_pct=50, pol_fx_exp=50, pol_fx_min=40, pol_fx_max=60)
    assert flow(t, e=0.10) == pytest.approx(-0.025 * 1_000_000, rel=1e-9)


def test_no_shock_no_flow_even_if_official_differs_from_model():
    # הנתון הרשמי (55%) שונה מהרכב התיק (50%) - בלי הלם אין זרם
    t = track(eqfx_us_pct=50, eq_us_pct=50, fx_spot_pct=50, fx_net_pct=50, act_fx=55.0, pol_fx_exp=50, pol_fx_min=40, pol_fx_max=60)
    assert flow(t) == pytest.approx(0.0, abs=1e-9)
    assert shock_flows(prepare(t), p=Params(mode="band", usdils=1.0)).flow_ils_k.iloc[0] == 0.0
