"""פירוק קנייה/מכירה נטו של נכסים דולריים לכל רבעון, כולל בטחונות ו-margin call - ומה מגיב לתנועת המדד.

רכיבים (מיליארדי ש"ח, + = קניית מט"ח נטו), מ-e1/e1b/e8:
  ני"ע במט"ח (קנייה/מכירה בפועל) | מזומן ופיקדונות במט"ח ללא בטחונות | בטחונות במט"ח (הפקדה/שחרור)
  הלוואות, קרנות פרטיות, אחר | פורוורדים (Δ נוציונל) | נגזרי מניות: Δ רווח צבור − שערוך (סילוקים)
לכל רכיב: מקדם מול שערוך נגזרי המניות ומול הרווח הדולרי הפיזי באותו רבעון (מסלול-רבעון, אפקט קבוע לרבעון).
פלט: data/results/fx_flow_breakdown.csv (לפי רבעון), data/results/fx_flow_breakdown_response.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d3_rebalancing_history import wls_cluster  # noqa: E402

KEY = ["legal_id", "track", "q0"]
f = pd.read_csv("data/flows/track_fx_flows.csv.gz")
f["g"] = f.component.str.split(":").str[0]
w = f.pivot_table(index=KEY, columns="g", values="flow", aggfunc="sum").fillna(0)
coll = pd.read_csv("data/flows/collateral_track.csv.gz").set_index(KEY)
w = w.join(coll[["coll_fx_k", "valuation_k"]], how="left").fillna(0)
w["cash_ex_coll"] = w.cash - w.coll_fx_k
w["deriv_settle"] = w.get("derivatives_mtm_change", 0) - w.valuation_k
w["other_all"] = w[["loans", "private_funds", "other"]].sum(axis=1)
comp = {"securities": "ני\"ע במט\"ח", "cash_ex_coll": "מזומן/פיקדונות במט\"ח (ללא בטחונות)", "coll_fx_k": "בטחונות במט\"ח",
        "other_all": "הלוואות/קרנות פרטיות/אחר", "forwards": "פורוורדים", "deriv_settle": "נגזרי מניות – סילוקים"}
w["total"] = w[list(comp)].sum(axis=1)
q = w.groupby(level="q0")[list(comp) + ["total", "valuation_k"]].sum() / 1e6
q = q.rename(columns={**comp, "total": "סה\"כ נטו", "valuation_k": "(שערוך נגזרים)"})
q.round(2).to_csv("data/results/fx_flow_breakdown.csv")
pd.set_option("display.width", 260, "display.max_columns", 20)
print(q.round(1).to_string())
p = pd.read_csv("data/flows/flow_panel.csv.gz").set_index(KEY)[["total_k", "g_phys"]]
w = w.join(p, how="inner")
w = w[w.total_k > 0]
w["v"], w["gp"] = w.valuation_k / w.total_k, w.g_phys
rows = []
for c, lab in list(comp.items()) + [("total", "סה\"כ נטו")]:
    d = w.assign(y=w[c] / w.total_k)
    d = d[d.y.abs() < 0.10].reset_index()
    for wt in (True, False):
        b, se = wls_cluster(d.assign(FX1=d.y, FX=0.0), ["v", "gp"], wt)
        rows.append({"רכיב": lab, "שקלול": "נכסים" if wt else "ללא", "n": len(d),
                     "מול שערוך נגזרים": round(b[0], 3), "se": round(se[0], 3), "מול רווח פיזי": round(b[1], 3), "se.1": round(se[1], 3)})
r = pd.DataFrame(rows)
r.to_csv("data/results/fx_flow_breakdown_response.csv", index=False)
print(r[r["שקלול"] == "נכסים"].to_string(index=False))
