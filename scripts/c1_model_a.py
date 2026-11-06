"""מודל א - לפי שינוי יומי/שבועי/חודשי במדדים: כמה מט"ח המוסדיים צריכים לקנות/למכור, ובדיקת אחור מול USD/ILS בפועל.

פלט (data/results/):
  sensitivity.csv      זרם נדרש ($ מיליון) ל-1% עלייה בכל גורם, לפי מערכת (פנסיה/גמל/ביטוח) ובסה"כ + ערוץ (ישיר / נגזר)
  flows_{D,W,M}.csv    סדרת זרם נדרש לכל תקופה + שינוי USD/ILS בפועל
  backtest.csv         מתאם/רגרסיה בין הזרם לשינוי השער, לפי אופק ולפי פיגור
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indexfx.model import Params, prepare, shock_flows  # noqa: E402

OUT = Path("data/results")
ROW_W = {"VEA": 0.8, "EEM": 0.2}


def factor_returns() -> pd.DataFrame:
    p = pd.read_csv("data/market/prices.csv", parse_dates=["date"]).pivot(index="date", columns="symbol", values="close")
    f = pd.DataFrame(index=p.index)
    f["us"] = p["^GSPC"]
    f["row"] = (p[list(ROW_W)].pct_change().fillna(0) * pd.Series(ROW_W)).sum(axis=1).add(1).cumprod()
    f["il"] = p["^TA125.TA"]
    return f


def sensitivities(d: pd.DataFrame, p: Params) -> pd.DataFrame:
    rows = []
    d_direct = d.copy()
    for c in ("dv_us_w", "dv_row_w", "dv_il_w"):
        d_direct[c] = 0.0
    for sys_name, g in [("הכל", d)] + [(s, d[d.system == s]) for s in sorted(d.system.unique())]:
        gd = d_direct.loc[g.index]
        for k in ("r_us", "r_row", "r_il"):
            tot = shock_flows(g, **{k: 0.01}, p=p).flow_usd_m.sum()
            dire = shock_flows(gd, **{k: 0.01}, p=p).flow_usd_m.sum()
            rows.append({"system": sys_name, "factor": k, "total_usd_m": tot, "direct_usd_m": dire, "derivative_usd_m": tot - dire})
        rows.append({"system": sys_name, "factor": "e(+1% דולר)", "total_usd_m": shock_flows(g, e=0.01, p=p).flow_usd_m.sum(),
                     "direct_usd_m": np.nan, "derivative_usd_m": np.nan})
        rows.append({"system": sys_name, "factor": "dy_il(+0.1pp)", "total_usd_m": shock_flows(g, dy_il=0.1, p=p).flow_usd_m.sum(),
                     "direct_usd_m": np.nan, "derivative_usd_m": np.nan})
    return pd.DataFrame(rows)


def series_flows(d: pd.DataFrame, f: pd.DataFrame, fx: pd.Series, freq: str, p: Params) -> pd.DataFrame:
    # הזרם לינארי בהלם (במצב continuous) - מחשבים את הרגישות פעם אחת ומכפילים
    base = {k: shock_flows(d, **{k: 0.01}, p=p).flow_usd_m.sum() / 0.01 for k in ("r_us", "r_row", "r_il")}
    if freq == "D":
        px, fxs = f, fx
    else:
        rule = {"W": "W-FRI", "M": "ME"}[freq]
        px, fxs = f.resample(rule).last(), fx.resample(rule).last()
    r = px.pct_change()
    out = pd.DataFrame({"flow_usd_m": base["r_us"] * r.us + base["r_row"] * r.row + base["r_il"] * r.il,
                        "usdils_chg": fxs.pct_change()}).dropna(how="any")
    out["flow_us"], out["flow_row"], out["flow_il"] = base["r_us"] * r.us, base["r_row"] * r.row, base["r_il"] * r.il
    return out


def backtest(s: pd.DataFrame, lag: int) -> dict:
    x = s.flow_usd_m.shift(lag) if lag else s.flow_usd_m
    z = pd.concat([x, s.usdils_chg], axis=1).dropna()
    z.columns = ["flow", "chg"]
    if len(z) < 20:
        return {}
    b = np.polyfit(z.flow, z.chg, 1)
    n = len(z)
    corr = z.flow.corr(z.chg)
    return {"n": n, "corr": corr, "beta_pct_per_bn": b[0] * 1000 * 100, "t": corr * np.sqrt((n - 2) / (1 - corr**2))}


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    p = Params()
    m = pd.read_csv("data/model_inputs.csv")
    m["system"] = m.legal_id.map(pd.read_csv("data/track_totals.csv").drop_duplicates("legal_id").set_index("legal_id").system)
    d = prepare(m)
    s = sensitivities(d, p)
    s.to_csv(OUT / "sensitivity.csv", index=False)
    print("רגישות: זרם נדרש ($ מיליון) ל-1% עלייה (חיובי = קניית דולר):")
    print(s[s.system == "הכל"].round(1).to_string(index=False))
    f = factor_returns()
    fx = pd.read_csv("data/market/boi_usdils.csv", parse_dates=["date"]).set_index("date").value
    bt = []
    for freq in ("D", "W", "M"):
        sr = series_flows(d, f, fx.reindex(f.index).ffill(), freq, p)
        sr.to_csv(OUT / f"flows_{freq}.csv")
        for lag in (0, 1, 2):
            r = backtest(sr, lag)
            if r:
                bt.append({"freq": freq, "lag": lag, **r})
    bt = pd.DataFrame(bt)
    bt.to_csv(OUT / "backtest.csv", index=False)
    print("\nבדיקת אחור: מתאם בין זרם נדרש (במודל) לשינוי USD/ILS בפועל; beta באחוזי שער ל-1 מיליארד $")
    print(bt.round(3).to_string(index=False))
