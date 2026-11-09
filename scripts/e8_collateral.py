"""בטחונות ו-margin call: כמה דולר נכנס/יוצא מהמסלולים כבטוחה לנגזרים, ואיך זה קשור לתנועת המדד.

מסלולים (דוחות רבעוניים): שורות שבהן "מאפיין עיקרי" = "בטחונות שוטפים" (גיליון מזומנים) / "בטחונות לא שוטפים" (פיקדונות),
לפי מטבע. חיובי = בטוחה שהמסלול הפקיד (נכס); שלילי = בטוחה שהתקבלה. שינוי ברבעון, בש"ח לפי שער q1 (מנטרל שינוי שער).
מקושר לשערוך נגזרי המניות על חו"ל באותו רבעון (e1b): רווח בנגזרים -> הצד הנגדי מחזיר/מפקיד בטוחה.
פלט: data/results/collateral_quarterly.csv (מצרפי לפי רבעון), data/flows/collateral_track.csv.gz (מסלול-רבעון)
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d3_rebalancing_history import wls_cluster  # noqa: E402

KEY = ["legal_id", "track"]
rows = []
for f in sorted(glob.glob("data/history/positions_*.csv.gz")):
    q = f.split("_")[-1].split(".")[0]
    if q == "2026Q3":
        continue
    d = pd.read_csv(f, low_memory=False, usecols=lambda c: c in ("legal_id", "track", "main_attr", "ccy", "fair_value_k", "fx_rate"))
    d = d[d.main_attr.astype(str).str.contains("בטחונות")].copy()
    d["fv"] = pd.to_numeric(d.fair_value_k, errors="coerce")
    d["rate"] = pd.to_numeric(d.fx_rate, errors="coerce")
    d["cur"] = np.where(d.ccy.astype(str).eq("ILS"), "ILS", d.ccy.astype(str))
    d["ccy_amt"] = np.where(d.cur == "ILS", d.fv, d.fv / d.rate)     # אלפים במטבע
    d["track"] = pd.to_numeric(d.track, errors="coerce")
    d["q"] = q
    rows.append(d.groupby(KEY + ["q", "cur"]).agg(fv=("fv", "sum"), amt=("ccy_amt", "sum"), rate=("rate", "median")).reset_index())
c = pd.concat(rows)
qs = sorted(c.q.unique())
out = []
for q0, q1 in zip(qs[:-1], qs[1:]):
    a, b = c[c.q == q0], c[c.q == q1]
    rate1 = b[b.cur != "ILS"].groupby("cur").rate.median()
    j = a.merge(b, on=KEY + ["cur"], how="outer", suffixes=("0", "1")).fillna({"amt0": 0, "amt1": 0})
    j["rate1"] = np.where(j.cur == "ILS", 1.0, j.cur.map(rate1))
    j["flow_k"] = (j.amt1 - j.amt0) * j.rate1                              # הפקדה (+) / שחרור (−) של בטוחה, בש"ח
    j["fx"] = j.cur != "ILS"
    t = j.groupby(KEY + ["fx"]).flow_k.sum().unstack("fx").fillna(0).rename(columns={True: "coll_fx_k", False: "coll_ils_k"}).reset_index()
    t["q0"] = q0
    out.append(t)
coll = pd.concat(out)
val = pd.read_csv("data/flows/derivative_valuation.csv.gz")
m = coll.merge(val[KEY + ["q0", "valuation_k"]], on=KEY + ["q0"], how="outer").fillna(0)
m.to_csv("data/flows/collateral_track.csv.gz", index=False, compression="gzip")
agg = m.groupby("q0")[["coll_fx_k", "coll_ils_k", "valuation_k"]].sum() / 1e6
agg.columns = ["בטוחה במט\"ח (מיליארד)", "בטוחה בש\"ח", "שערוך נגזרי מניות חו\"ל"]
agg.round(2).to_csv("data/results/collateral_quarterly.csv")
print(agg.round(2).to_string())
x, y = agg.iloc[:, 2], agg.iloc[:, 0]
bb = np.polyfit(x, y, 1)
print(f"מצרפי: Δבטוחה במט\"ח = {bb[0]:.2f} × שערוך ; מתאם {x.corr(y):.2f}")
# מסלול-רבעון: שבר מהנכסים
tot = pd.read_csv("data/flows/flow_panel.csv.gz")[KEY + ["q0", "total_k"]]
mm = m.merge(tot, on=KEY + ["q0"], how="inner")
mm = mm[mm.total_k > 0]
mm["y"], mm["v"] = mm.coll_fx_k / mm.total_k, mm.valuation_k / mm.total_k
mm = mm[mm.y.abs() < 0.10]
for wt in (True, False):
    b_, se = wls_cluster(mm.assign(FX1=mm.y, FX=0.0), ["v"], wt)
    print(f"מסלול-רבעון ({'משוקלל' if wt else 'לא משוקלל'}, n={len(mm)}): Δבטוחה במט\"ח = {b_[0]:.2f} (±{1.96*se[0]:.2f}) × שערוך")
