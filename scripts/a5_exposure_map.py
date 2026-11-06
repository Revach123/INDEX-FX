"""שלב א.5 - מפת צורות חשיפה: לכל מדד/מניה, באילו צורות מוחזקת ובאיזה היקף, ואיך זה משפיע על ערוץ המט"ח.

פלט: data/exposure_map_index.csv  (מדד × צורה: שווי הוגן ש"ח, מס' מסלולים, מס' חברות)
     data/exposure_map_stock.csv  (מניה בודדת: ישירה / דרך החלף / אופציה - אלפי ש"ח)
     data/exposure_map_form_summary.csv (צורה × מסלול מט"ח: סה"כ, מספר החזקות)
שווי הוגן בנגזרים = שווי השוק הנקי (לא נוציונל) - ר' deriv_notionals לנוציונל (מגבלה מתועדת ב-PLAN).
"""
import pandas as pd

df = pd.read_csv("data/positions_classified.csv.gz", low_memory=False)
df["value_k"] = df.fair_value_k
eqf = df[df.asset_class.eq("equity") | df.form.isin(["FUTURE", "OPTION"])].copy()
g = eqf.groupby(["index_key", "index_label", "form"]).agg(value_k=("value_k", "sum"), n_pos=("form", "size"),
        n_tracks=("track", lambda s: len(set(zip(eqf.loc[s.index, "legal_id"], s)))),
        n_cos=("legal_id", "nunique")).reset_index()
g.to_csv("data/exposure_map_index.csv", index=False)
piv = g.pivot_table(index=["index_key", "index_label"], columns="form", values="value_k", aggfunc="sum", fill_value=0.0)
piv["total_k"] = piv.sum(axis=1)
piv = piv[~piv.index.get_level_values(0).astype(str).str.startswith("stock:")].sort_values("total_k", ascending=False)
pd.set_option("display.width", 250, "display.max_columns", 30)
print((piv.head(22) / 1e6).round(2).to_string())

st = eqf[eqf.index_key.astype(str).str.startswith("stock:") | (eqf.form.str.startswith("SWAP_EQ") & eqf.index_key.eq("") )]
sw = df[df.form.isin(["SWAP_EQ_UNFUNDED", "SWAP_EQ_FUNDED"]) & df.index_key.astype(str).str.fullmatch(r"[A-Z0-9 ]+ ?(IT|US|LN|GY|FP)?", na=False)]
stock = pd.concat([eqf[eqf.form.isin(["STOCK_DIRECT", "WARRANT"])].assign(src="spot"), sw.assign(src="swap")])
sg = stock.groupby(["index_label", "form", "fx_ccy", "country"], dropna=False).agg(value_k=("value_k", "sum"), n_tracks=("track", "size")).reset_index()
sg = sg.sort_values("value_k", ascending=False)
sg.to_csv("data/exposure_map_stock.csv", index=False)
fs = df.groupby(["form", "fx_route"]).agg(value_k=("value_k", "sum"), n=("form", "size")).reset_index()
fs.to_csv("data/exposure_map_form_summary.csv", index=False)
print("\nצורה × מסלול מט\"ח (מיליארד ש\"ח):")
print(fs.assign(value_bn=(fs.value_k / 1e6).round(1)).drop(columns="value_k").to_string(index=False))
