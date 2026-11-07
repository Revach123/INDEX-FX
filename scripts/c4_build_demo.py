"""בונה demo/index.html מחדש - מבוסס רק על מה שנמדד (מחליף את c3 ואת המודל שהניח חזרה ליעד מט"ח).

מוטמע בדף (מחושב כאן, מהנתונים):
  מסלולים (כלליים / כל המסלולים): בסיסי חשיפה מצרפיים במיליארדי ש"ח (model2_inputs.csv, דוח 30.6.2026):
     phys_us/phys_row (מניות חו"ל פיזיות), syn_us/syn_row (החלפים/חוזים), growth_* = Σ מט"ח × נכסים × משקל הרכיב
  מקדמי התגובה בפועל b ומטריצת השונות V (e2/e3: זרם מט"ח נמדד מהדוחות; ללא חריגים; משוקלל ולא משוקלל)
  קרנות מחקות: שווי (דוח חודשי רשמי) ו-κ חודשי (b3b, חוזי אקדמה בפועל)
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e3_scenario_from_flows import wls_full  # noqa: E402

p = pd.read_csv("data/flows/flow_panel.csv.gz")
d = p[p.y.abs() < 0.10].dropna(subset=["gain_phys", "gain_syn", "growth_fx"])
specs = {}
for key, wt in (("weighted", True), ("unweighted", False)):
    b, V = wls_full(d, ["gain_phys", "gain_syn", "growth_fx"], wt)
    specs[key] = {"b": [float(x) for x in b], "V": [[float(x) for x in r] for r in V], "n": int(len(d)),
                  "quarters": sorted(d.q0.unique().tolist())}
t = pd.read_csv("data/model2_inputs.csv")
groups = {}
for key, s in (("general", t[t.general]), ("all", t)):
    A = s.total_k / 1e6
    groups[key] = {
        "assets": float(A.sum()),
        "phys_us": float((s.U_phys_us * A).sum()), "phys_row": float((s.U_phys_row * A).sum()),
        "syn_us": float((s.U_syn_us * A).sum()), "syn_row": float((s.U_syn_row * A).sum()),
        "g_fr_us": float((s.FX0 * (s.U_phys_us + s.U_syn_us) * A).sum()),
        "g_fr_row": float((s.FX0 * (s.U_phys_row + s.U_syn_row) * A).sum()),
        "g_ilf": float((s.FX0 * s.eqfr_ilf * A).sum()),
        "g_il": float((s.FX0 * s.E_il * A).sum()), "g_bond": float((s.FX0 * s.B_il * A).sum()),
        "fx_avg": float((s.FX0 * A).sum() / A.sum()),
    }
f = pd.read_csv("data/funds/funds.csv", dtype={"fund": str})
fe = f[f.primary.eq("מניות בחו\"ל") & f.mimic & f.aum_m.notna()]
ha = pd.read_csv("data/funds/etf_hedge_all.csv")
k20 = ha[ha["חלון (ימים)"] == 20].set_index("קבוצה")
funds = {"unhedged_bn": float(fe[~fe.hedged].aum_m.sum() / 1e3), "hedged_bn": float(fe[fe.hedged].aum_m.sum() / 1e3),
         "k_unh": float(k20.loc["לא מגודרת 4D", "κ (קנייה מכל 1% עלייה)"]), "k_unh_se": float(k20.loc["לא מגודרת 4D", "se"]),
         "k_hed": float(k20.loc["מגודרת 4A", "κ (קנייה מכל 1% עלייה)"]), "k_hed_se": float(k20.loc["מגודרת 4A", "se"]),
         "n_unh": int(k20.loc["לא מגודרת 4D", "קרנות"]), "n_hed": int(k20.loc["מגודרת 4A", "קרנות"])}
data = {"specs": specs, "groups": groups, "funds": funds}
html = Path("demo/template.html").read_text(encoding="utf-8").replace("__DATA__", json.dumps(data, ensure_ascii=False))
Path("demo/index.html").write_text(html, encoding="utf-8")
print("[c4] demo/index.html:", json.dumps({k: round(v, 1) for k, v in groups["general"].items()}, ensure_ascii=False))
print("[c4] b weighted:", [round(x, 3) for x in specs["weighted"]["b"]], "unweighted:", [round(x, 3) for x in specs["unweighted"]["b"]])
print("[c4] funds:", {k: round(v, 2) if isinstance(v, float) else v for k, v in funds.items()})
