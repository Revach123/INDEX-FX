"""תרחיש המאמר לפי הזרמים בפועל (e2) - עם טווח טעות, ובדיקת התאמה מצרפית מול החשיפה הרשמית.

1. התאמה: לכל רבעון - Δ חשיפת מט"ח רשמית (data.gov) = שערוך (שער + רווח דולרי פיזי/סינתטי) + זרם נמדד (e1+e1b)?
2. תרחיש: זרם = b_phys·רווח פיזי + b_syn·רווח סינתטי + b_growth·(מט"ח × גידול התיק), במקדמי e2;
   טווח 95% לפי מטריצת השונות (שגיאות מקובצות לפי מסלול).
פלט: data/results/scenario_from_flows.csv, data/results/aggregate_reconciliation.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))

KEY = ["legal_id", "track"]


def wls_full(d, cols, weighted):
    y = d.y.values
    w = (d.total_k / d.total_k.mean()).values if weighted else np.ones(len(d))
    qs = sorted(d.q0.unique())
    X = np.column_stack([d[c].values for c in cols] + [(d.q0 == q).values.astype(float) for q in qs])
    Xw = X * w[:, None]
    A = np.linalg.inv(X.T @ Xw)
    b = A @ (Xw.T @ y)
    e = y - X @ b
    g = (d.legal_id.astype(str) + "_" + d.track.astype(str)).values
    S = np.zeros((X.shape[1],) * 2)
    for _, idx in pd.Series(np.arange(len(d))).groupby(g):
        sv = (X[idx.values] * (w[idx.values] * e[idx.values])[:, None]).sum(0)
        S += np.outer(sv, sv)
    k = len(cols)
    return b[:k], (A @ S @ A)[:k, :k]


def main():
    p = pd.read_csv("data/flows/flow_panel.csv.gz")
    t = pd.read_csv("data/model2_inputs.csv")
    cols = ["gain_phys", "gain_syn", "growth_fx"]
    rows = []
    for lab, d in (("כל התצפיות", p), ("ללא חריגים (|זרם|<10%)", p[p.y.abs() < 0.10])):
        for wt in (True, False):
            b, V = wls_full(d.dropna(subset=cols), cols, wt)
            for glab, s in (("מסלולים כלליים", t[t.general]), ("כל המסלולים", t)):
                A = s.total_k / 1e6
                Gp = ((s.U_phys_us + s.U_phys_row) * 0.10 * A).sum()
                Gs = ((s.U_syn_us + s.U_syn_row) * 0.10 * A).sum()
                dA = (s.U_phys_us + s.U_phys_row + s.U_syn_us + s.U_syn_row + s.eqfr_ilf) * 0.10 + s.E_il * 0.05 + s.B_il * 0.05
                Gg = (s.FX0 * dA * A).sum()
                x = np.array([Gp, Gs, Gg])
                est, se = float(x @ b), float(np.sqrt(x @ V @ x))
                rows.append({"מדגם": lab, "שקלול": "נכסים" if wt else "ללא", "קבוצה": glab,
                             "b_phys": b[0], "b_syn": b[1], "b_growth": b[2],
                             "זרם (מיליארד)": est, "טווח 95% מ-": est - 1.96 * se, "עד": est + 1.96 * se})
    r = pd.DataFrame(rows).round(2)
    r.to_csv("data/results/scenario_from_flows.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 20)
    print("תרחיש: חו\"ל +10%, ת\"א +5%, אג\"ח +5% - זרם מט\"ח של המסלולים לפי ההתנהגות בפועל (מיליארדי ש\"ח, + קנייה):")
    print(r.to_string(index=False))


if __name__ == "__main__":
    main()
