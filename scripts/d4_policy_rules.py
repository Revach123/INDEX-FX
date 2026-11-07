"""איך הגופים מאזנים לפי המדיניות? בדיקה מול יעדי המדיניות שהיו בתוקף בכל רבעון.

המדיניות (MASLULIM/policy/tracks_policy_long.csv, לפי שנה): יעד/מינימום/מקסימום למניות ולמט"ח, ומדד ייחוס למניות
(ממנו - חלק חו"ל ביעד המניות, לפי policy_benchmark.parse של Revach - קריאה בלבד).
לכל מסלול ורבעון (פאנל d3) - שני רכיבים, כל אחד בנפרד:
  מט"ח:        X0 = FX0, Xp = FXp (פסיבי - כל הרווח הזר בדולר), X1 = FX1 בפועל, T = יעד המט"ח, [lo,hi] = הטווח
  מניות חו"ל:   X0 = (פיזי+סינתטי)/נכסים, Xp = פסיבי (תשואת המדד, מטבע לפיזי, ומכנה), X1 בפועל,
               T = יעד המניות × חלק חו"ל במדד הייחוס
כללים מתחרים, וכמה מכל אחד מסביר את הנתונים:
  (1) "סגירת פער ליעד": X1 − Xp = a + b·(T − Xp)         b=1 חזרה מלאה ליעד, b=0 לא נוגעים (פסיבי)
  (2) "טווח": X1 − Xp = a + b·(clip(Xp,lo,hi) − Xp)      פעולה רק כשחורגים מהטווח
אפקט קבוע לכל מעבר רבעון; שגיאות מקובצות לפי מסלול. פלט: data/results/policy_rules.csv
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "/home/user/Revach/scripts/tracks")
from policy_benchmark import parse as parse_bench  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d3_rebalancing_history import wls_cluster  # noqa: E402

PATS = [re.compile(r"^(\d{3,6})$"), re.compile(r"^\d{9}-(\d{3,6})$"), re.compile(r"^\d{9}-\d{14,15}-(\d{3,6})-\d{3}$")]


def track_no(r):
    if pd.notna(r.track_no):
        try:
            return int(float(r.track_no))
        except ValueError:
            pass
    for p in PATS:
        m = p.match(str(r.track_code))
        if m:
            return int(m.group(1))
    return None


def fr_share(bench) -> float:
    parts = parse_bench(str(bench or "")) if isinstance(bench, str) and bench.strip() else []
    ws = [p for p in parts if p.get("w") is not None]
    if not parts:
        return np.nan
    if len(ws) == len(parts) and sum(p["w"] for p in ws) > 0:
        return sum(p["w"] for p in ws if not p["il"]) / sum(p["w"] for p in ws)
    if all(p["il"] for p in parts):
        return 0.0
    if not any(p["il"] for p in parts):
        return 1.0
    return np.nan


def policies() -> pd.DataFrame:
    d = pd.read_csv("/home/user/revach123/maslulim/policy/tracks_policy_long.csv", low_memory=False)
    d = d[d.asset_key.isin(["equity", "fx"])].copy()
    d["track"] = d.apply(track_no, axis=1)
    d = d.dropna(subset=["track", "expected_pct"])
    d["seen"] = pd.to_datetime(d.doc_first_seen, errors="coerce", utc=True).dt.tz_localize(None)
    return d


def policy_at(pol: pd.DataFrame, q_end: pd.Timestamp) -> pd.DataFrame:
    """מדיניות בתוקף בסוף הרבעון: שנת הרבעון; המסמך האחרון שנראה עד סוף הרבעון, אחרת הראשון של השנה."""
    y = pol[pol.year == q_end.year].copy()
    y["ok"] = y.seen.isna() | (y.seen <= q_end)
    y = y.sort_values(["ok", "seen"])
    y = y.groupby(["legal_id", "track", "asset_key"]).tail(1)
    w = y.pivot_table(index=["legal_id", "track"], columns="asset_key", values=["expected_pct", "min_pct", "max_pct"], aggfunc="first")
    w.columns = [f"{a}_{b}" for a, b in w.columns]
    bench = y[y.asset_key == "equity"].set_index(["legal_id", "track"]).benchmark
    w["fr_share"] = bench.reindex(w.index).map(fr_share)
    return w.reset_index()


def main():
    pol = policies()
    p = pd.read_csv("data/results/rebalancing_panel.csv")
    st = pd.read_csv("data/history/track_quarter_state.csv.gz")
    q1 = st[["legal_id", "track", "q", "u_phys_k", "u_syn_k"]].rename(columns={"q": "q1", "u_phys_k": "u_phys1", "u_syn_k": "u_syn1"})
    p = p.merge(q1, on=["legal_id", "track", "q1"], how="left")
    out = []
    for q, g in p.groupby("q0"):
        d0 = pd.Timestamp(g.report_date.iloc[0])
        pw = policy_at(pol, d0)
        out.append(g.merge(pw, on=["legal_id", "track"], how="inner"))
    p = pd.concat(out)
    # יחידות: אחוזים -> שבר
    for c in ("expected_pct_fx", "min_pct_fx", "max_pct_fx", "expected_pct_equity"):
        p[c] = p[c] / 100
    # מניות חו"ל: בפועל ופסיבי
    p["E0"] = (p.u_phys_k + p.u_syn_k) / p.total_k
    p["E1"] = (p.u_phys1 + p.u_syn1) / p.total_k1
    r_fr = np.where(p.u_phys_k + p.u_syn_k > 0, (p.g_phys + p.g_syn) / p.E0.replace(0, np.nan), 0)
    p["Ep"] = (p.u_phys_k * (1 + r_fr) * (1 + p.e) + p.u_syn_k * (1 + r_fr) * (1 + p.e)) / p.total_k / (1 + p.R1)
    p["TE"] = p.expected_pct_equity * p.fr_share
    p.to_csv("data/results/policy_panel.csv", index=False)

    rows = []
    for comp, X0, Xp, X1, T, lo, hi in (("מט\"ח", "FX", "FXp", "FX1", "expected_pct_fx", "min_pct_fx", "max_pct_fx"),
                                         ("מניות חו\"ל", "E0", "Ep", "E1", "TE", None, None)):
        d = p.dropna(subset=[X0, Xp, X1, T]).copy()
        d = d[(d[X1] - d[X0]).abs() < 0.10]
        d["gap"] = d[T] - d[Xp]
        rules = [("סגירת פער ליעד", "gap")]
        if lo:
            d = d.dropna(subset=[lo, hi])
            d["gap_band"] = d[Xp].clip(d[lo], d[hi]) - d[Xp]
            rules.append(("טווח (רק מחוץ ל-min/max)", "gap_band"))
        for lab, col in rules:
            for wt in (True, False):
                y = d.assign(FX1=d[X1] - d[Xp], FX=0.0)   # wls_cluster ממדל FX1-FX
                b, se = wls_cluster(y, [col], wt)
                rows.append({"רכיב": comp, "כלל": lab, "שקלול": "לפי נכסים" if wt else "ללא", "n": len(d),
                             "b (1=חזרה מלאה, 0=פסיבי)": b[0], "se": se[0],
                             "פער ממוצע ליעד |pp|": 100 * np.average(d[col].abs(), weights=d.total_k)})
    r = pd.DataFrame(rows).round(3)
    r.to_csv("data/results/policy_rules.csv", index=False)
    pd.set_option("display.width", 250)
    print(r.to_string(index=False))


if __name__ == "__main__":
    main()
