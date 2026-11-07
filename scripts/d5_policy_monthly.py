"""בדיקה חודשית: איך הגופים מאזנים מט"ח ומניות מול המדיניות - על החשיפה הרשמית (data.gov.il, b6).

לכל מסלול וחודש t -> t+1 (2024-01 ->, כשיש פירוק רבעוני של צורת החזקה):
  FX_t, EQ_t      חשיפה רשמית למט"ח / למניות (שבר מהנכסים)
  R               תשואת המסלול בחודש (רשמי)
  w_phys, w_syn   חשיפה למניות חו"ל פיזית / סינתטית (מהפירוק הרבעוני האחרון שלפני t, a6/a7 בכל רבעון)
  r_fr            תשואת מניות חו"ל בדולר (S&P 500 TR לחלק ארה"ב, VEA/EEM לשאר), e - USD/ILS, r_il - ת"א 125
פסיבי (בלי מסחר):
  FXp = [FX_t·(1+e) + w_phys·r_fr·(1+e) + w_syn·(r_fr − i_usd·τ)] / (1+R)
  EQp = [(EQ_t − w_fr)·(1+r_il) + w_fr·(1+r_fr)·(1+e)] / (1+R),   w_fr = w_phys + w_syn
יעדים: מדיניות השנה (tracks_policy_long) - יעד/מינ'/מקס' למט"ח ולמניות.
מבחנים (אפקט קבוע לכל חודש, שגיאות מקובצות לפי מסלול):
  A. רכיבים: ΔFX = b_phys·(רווח פיזי) + b_syn·(רווח סינתטי) + b_den·(אפקט מכנה)      (b=1 נשאר, 0 קוזז)
  B. סגירת פער ליעד: X_{t+1} − Xp = b·(T − Xp)                                       (1=חזרה מלאה ליעד בחודש)
  C. טווח: X_{t+1} − Xp = b·(clip(Xp, min, max) − Xp)
פלט: data/results/policy_monthly.csv, data/results/policy_monthly_panel.csv.gz
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d3_rebalancing_history import INDICES, wls_cluster  # noqa: E402
from d4_policy_rules import policies, policy_at  # noqa: E402


def main():
    d = pd.read_csv("data/datagov/monthly.csv.gz", low_memory=False)
    for c in ("TOTAL_ASSETS", "STOCK_MARKET_EXPOSURE", "FOREIGN_CURRENCY_EXPOSURE", "MONTHLY_YIELD"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d.dropna(subset=["TOTAL_ASSETS"])
    d = d[d.TOTAL_ASSETS > 50]  # מיליוני ש"ח
    d["FX"] = d.FOREIGN_CURRENCY_EXPOSURE / d.TOTAL_ASSETS
    d["EQ"] = d.STOCK_MARKET_EXPOSURE / d.TOTAL_ASSETS
    d["month"] = pd.PeriodIndex(d.REPORT_PERIOD.astype(int).astype(str), freq="M")
    st = pd.read_csv("data/history/track_quarter_state.csv.gz")
    d["legal_id"] = d.FUND_ID.map(st.drop_duplicates(["legal_id", "track"]).groupby("track").legal_id.first())
    d = d.dropna(subset=["legal_id"]).rename(columns={"FUND_ID": "track"})
    d["legal_id"] = d.legal_id.astype(int)
    d["track"] = d.track.astype(float)
    st["track"] = st.track.astype(float)

    # פירוק רבעוני -> לכל חודש: הרבעון האחרון שהסתיים לפני תחילת החודש
    st["qend"] = pd.PeriodIndex(pd.to_datetime(st.report_date), freq="M")
    st["w_phys"], st["w_syn"] = st.u_phys_k / st.total_k, st.u_syn_k / st.total_k
    st["us_phys"] = (st.u_phys_us_k / st.u_phys_k).where(st.u_phys_k > 0, 0.8)
    st["us_syn"] = (st.u_syn_us_k / st.u_syn_k).where(st.u_syn_k > 0, 0.8)
    st = st.sort_values("qend")
    d = d.sort_values("month")
    d = pd.merge_asof(d.assign(m_ts=d.month.dt.to_timestamp()), st.assign(m_ts=st.qend.dt.to_timestamp())[
        ["legal_id", "track", "m_ts", "w_phys", "w_syn", "us_phys", "us_syn"]], on="m_ts", by=["legal_id", "track"],
        direction="backward", tolerance=pd.Timedelta(days=200))
    d = d.dropna(subset=["w_phys"])

    # שווקים: סוף חודש
    px = pd.read_csv("data/market/prices.csv", parse_dates=["date"]).pivot(index="date", columns="symbol", values="close")
    sptr = pd.read_csv(INDICES / "data/prices/sp500tr.csv", parse_dates=["date"]).set_index("date").close
    row = (1 + (0.8 * px["VEA"].pct_change() + 0.2 * px["EEM"].pct_change()).fillna(0)).cumprod()
    fx = pd.read_csv("data/market/boi_usdils.csv", parse_dates=["date"]).set_index("date").value
    me = lambda s: s.resample("ME").last()  # noqa: E731
    mk = pd.DataFrame({"us": me(sptr).pct_change(), "row": me(row).pct_change(), "il": me(px["^TA125.TA"]).pct_change(),
                       "e": me(fx).pct_change(), "i_usd": px["^IRX"].resample("ME").mean() / 100})
    mk.index = mk.index.to_period("M")

    # צמד חודשים עוקבים
    n = d[["legal_id", "track", "month", "FX", "EQ", "MONTHLY_YIELD", "TOTAL_ASSETS"]].copy()
    n["month"] = n.month - 1
    p = d.merge(n, on=["legal_id", "track", "month"], suffixes=("", "1"))
    p = p.join(mk.shift(-1).add_suffix("_n"), on="month")   # שוק בחודש הבא
    p = p.dropna(subset=["us_n", "e_n", "MONTHLY_YIELD1"])
    R = p.MONTHLY_YIELD1 / 100
    r_phys = p.us_phys * p.us_n + (1 - p.us_phys) * p.row_n
    r_syn = p.us_syn * p.us_n + (1 - p.us_syn) * p.row_n
    p["g_phys"] = p.w_phys * r_phys * (1 + p.e_n) / (1 + R)
    p["g_syn"] = p.w_syn * (r_syn - p.i_usd_n / 12) / (1 + R)
    p["g_den"] = p.FX * ((1 + p.e_n) / (1 + R) - 1)
    p["FXp"] = p.FX + p.g_phys + p.g_syn + p.g_den
    w_fr = p.w_phys + p.w_syn
    r_fr = (p.w_phys * r_phys + p.w_syn * r_syn) / w_fr.replace(0, np.nan)
    p["EQp"] = ((p.EQ - w_fr).clip(lower=0) * (1 + p.il_n) + w_fr * (1 + r_fr.fillna(0)) * (1 + p.e_n)) / (1 + R)

    # יעדי מדיניות של השנה
    pol = policies()
    parts = []
    for y, g in p.groupby(p.month.dt.year):
        pw = policy_at(pol, pd.Timestamp(f"{y}-12-31"))
        parts.append(g.merge(pw, on=["legal_id", "track"], how="left"))
    p = pd.concat(parts)
    for c in [c for c in p.columns if c.startswith(("expected_pct", "min_pct", "max_pct"))]:
        p[c] = p[c] / 100
    p["total_k"] = p.TOTAL_ASSETS
    p["q0"] = p.month.astype(str)
    p.to_csv("data/results/policy_monthly_panel.csv.gz", index=False, compression="gzip")
    print(f"[d5] {len(p):,} תצפיות מסלול-חודש, {p.groupby(['legal_id','track']).ngroups} מסלולים, {p.month.min()}→{p.month.max()}")

    rows = []
    trim = lambda x: x[(x.FX1 - x.FX).abs() < 0.05]  # noqa: E731
    for lab, s in (("כל התצפיות", p), ("ללא חריגים (|ΔFX|<5pp)", trim(p))):
        for wt in (True, False):
            b, se = wls_cluster(s, ["g_phys", "g_syn", "g_den"], wt)
            rows.append({"מבחן": "A רכיבי מט\"ח (נשאר)", "מדגם": lab, "שקלול": "נכסים" if wt else "ללא", "n": len(s),
                         "רווח פיזי": b[0], "se_p": se[0], "רווח סינתטי": b[1], "se_s": se[1], "מכנה": b[2], "se_d": se[2]})
    for comp, X, Xp, X1, T, lo, hi in (("מט\"ח", "FX", "FXp", "FX1", "expected_pct_fx", "min_pct_fx", "max_pct_fx"),
                                         ("מניות", "EQ", "EQp", "EQ1", "expected_pct_equity", "min_pct_equity", "max_pct_equity")):
        s = p.dropna(subset=[T, lo, hi, Xp, X1]).copy()
        s = s[(s[X1] - s[X]).abs() < 0.05]
        s["gap"] = s[T] - s[Xp]
        s["gap_band"] = s[Xp].clip(s[lo], s[hi]) - s[Xp]
        for rule, col in (("B סגירת פער ליעד", "gap"), ("C טווח", "gap_band")):
            for wt in (True, False):
                y = s.assign(FX1=s[X1] - s[Xp], FX=0.0)
                b, se = wls_cluster(y, [col], wt)
                rows.append({"מבחן": f"{rule} – {comp}", "מדגם": "ללא חריגים", "שקלול": "נכסים" if wt else "ללא", "n": len(s),
                             "b": b[0], "se": se[0], "פער ממוצע |pp|": 100 * np.average(s[col].abs(), weights=s.total_k),
                             "מחוץ לטווח %": 100 * np.average(s.gap_band.abs() > 1e-9, weights=s.total_k)})
    r = pd.DataFrame(rows).round(3)
    r.to_csv("data/results/policy_monthly.csv", index=False)
    pd.set_option("display.width", 260, "display.max_columns", 20)
    print(r.to_string(index=False))


if __name__ == "__main__":
    main()
