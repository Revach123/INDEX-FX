"""התאמה מצרפית לכל רבעון: Δ חשיפת מט"ח רשמית (data.gov) מול שערוך + זרם נמדד (e1+e1b) - על אותם מסלולים.
שערוך = חשיפת מט"ח ב-q0 × שינוי USD/ILS + רווח דולרי פיזי וסינתטי (פאנל d3). פלט: data/results/aggregate_reconciliation.csv"""
import pandas as pd

p = pd.read_csv("data/flows/flow_panel.csv.gz")
dg = pd.read_csv("data/datagov/monthly.csv.gz", low_memory=False)
dg["FCE"] = pd.to_numeric(dg.FOREIGN_CURRENCY_EXPOSURE, errors="coerce") * 1000
dg["m"] = pd.PeriodIndex(dg.REPORT_PERIOD.astype(int).astype(str), freq="M")
st = pd.read_csv("data/history/track_quarter_state.csv.gz").drop_duplicates(["legal_id", "track"])
dg["legal_id"] = dg.FUND_ID.map(st.groupby("track").legal_id.first())
dg = dg.dropna(subset=["legal_id"])
dg["legal_id"], dg["track"] = dg.legal_id.astype(int), dg.FUND_ID.astype(float)
rows = []
for q0, g in p.groupby("q0"):
    m0 = pd.Period(pd.Timestamp(g.report_date.iloc[0]), freq="M")
    a = dg[dg.m == m0].set_index(["legal_id", "track"])
    b = dg[dg.m == m0 + 3].set_index(["legal_id", "track"])
    gg = g.set_index(["legal_id", "track"])
    k = gg.index.intersection(a.index).intersection(b.index)
    gg = gg.loc[k]
    f0, f1 = a.loc[k, "FCE"], b.loc[k, "FCE"]
    val = f0 * gg.e + (gg.g_phys + gg.g_syn) * gg.total_k * (1 + gg.R1)
    rows.append({"q0": q0, "מסלולים": len(k), "מט\"ח רשמי q0": f0.sum() / 1e6, "מט\"ח מחושב q0": (gg.FX * gg.total_k).sum() / 1e6,
                 "Δ מט\"ח רשמי": (f1 - f0).sum() / 1e6, "שערוך": val.sum() / 1e6, "זרם משתמע (רשמי−שערוך)": (f1 - f0 - val).sum() / 1e6,
                 "זרם נמדד מהדוחות": gg.flow_k.sum() / 1e6, "r_us": gg.r_us.iloc[0], "e": gg.e.iloc[0]})
r = pd.DataFrame(rows).round(2)
r.to_csv("data/results/aggregate_reconciliation.csv", index=False)
print(r.to_string(index=False))
print("מתאם בין זרם משתמע לזרם נמדד:", round(r["זרם משתמע (רשמי−שערוך)"].corr(r["זרם נמדד מהדוחות"]), 2))
