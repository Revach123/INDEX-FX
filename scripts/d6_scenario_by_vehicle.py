"""תרחיש המאמר מפורק לפי צורת החזקה (החלף/חוזה מול פיזי), עם מקדמי איזון חודשיים נפרדים לכל קבוצת מסלולים לפי שיעור המט"ח.

למה בנפרד: במסלול עם ~100% מט"ח (למשל עוקב S&P) "שומרים את הרווח הדולרי של ההחלף" ו"ממירים ואז קונים דולר בפורוורד"
נותנים אותו אחוז מט"ח - המקדמים נאמדים שם על הקבוצה עצמה ולא מהממוצע של המסלולים הכלליים.
לכל רכיב: מכירה = −(1−b_רווח)·רווח דולרי;  קנייה = (1−b_מכנה)·שיעור המט"ח·גידול התיק מאותו רכיב.
תרחיש: חו"ל +10%, ת"א +5%, אג"ח שקלי +5% (כמו במאמר). פלט: data/results/article_scenario_by_vehicle.csv (מיליארדי ש"ח)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d3_rebalancing_history import wls_cluster  # noqa: E402

BINS = [(-1, 0.35, "עד 35%"), (0.35, 0.6, "35%-60%"), (0.6, 9, "מעל 60%")]
p = pd.read_csv("data/results/policy_monthly_panel.csv.gz")
p = p[(p.FX1 - p.FX).abs() < 0.05]
B = {}
for lo, hi, lab in BINS:
    b, se = wls_cluster(p[(p.FX > lo) & (p.FX <= hi)], ["g_phys", "g_syn", "g_den"], True)
    B[lab] = b
    print(f"{lab}: נשאר אחרי חודש - פיזי {b[0]:.2f}±{se[0]:.2f}, סינתטי {b[1]:.2f}±{se[1]:.2f}, מכנה {b[2]:.2f}±{se[2]:.2f}")
t = pd.read_csv("data/model2_inputs.csv")
rows = []
for lab, s in (("מסלולים כלליים", t[t.general]), ("כל המסלולים", t)):
    A = s.total_k / 1e6
    Gp = (s.U_phys_us + s.U_phys_row) * 0.10 * A
    Gs = (s.U_syn_us + s.U_syn_row) * 0.10 * A
    G_other = (s.eqfr_ilf * 0.10 + s.E_il * 0.05 + s.B_il * 0.05) * A
    grp = pd.cut(s.FX0, [-1, 0.35, 0.6, 9], labels=[x[2] for x in BINS])
    bp, bs, bd = (grp.map(lambda g, i=i: B[g][i]).astype(float) for i in range(3))
    out = {"קבוצה": lab}
    for part, G, bb in (("החלף/חוזה", Gs, bs), ("פיזי", Gp, bp)):
        out[f"{part}: מכירת הרווח הדולרי"] = -((1 - bb) * G).sum()
        out[f"{part}: קנייה כי התיק גדל"] = ((1 - bd) * s.FX0 * G).sum()
        out[f"{part}: נטו"] = out[f"{part}: מכירת הרווח הדולרי"] + out[f"{part}: קנייה כי התיק גדל"]
    out["קנייה בגלל עליית ת\"א ואג\"ח"] = ((1 - bd) * s.FX0 * G_other).sum()
    out["סה\"כ"] = out["החלף/חוזה: נטו"] + out["פיזי: נטו"] + out["קנייה בגלל עליית ת\"א ואג\"ח"]
    rows.append(out)
r = pd.DataFrame(rows).set_index("קבוצה").T.round(1)
r.to_csv("data/results/article_scenario_by_vehicle.csv")
print(r.to_string())
