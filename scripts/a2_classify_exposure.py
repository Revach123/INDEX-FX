"""שלב א.2 - מיפוי צורת החשיפה לכל החזקה.

קלט: data/positions.csv.gz (a1).  פלט: data/positions_classified.csv.gz

לכל שורה:
  form        צורת החשיפה (ר' FORMS)
  asset_class equity / bond / fx / rate / commodity / cash / other
  geo         IL / ABROAD / UNKNOWN (לפי הדיווח; לנגזרים - לפי המדד)
  index_key   המדד/הנכס שמאחורי החשיפה (ת"א 125, sp500...) או שם המניה
  fx_route    איך המט"ח נכנס לשורה (ר' FX_ROUTES)
  fx_ccy      מטבע החשיפה הכלכלית
  fx_exposure_k  חשיפת מט"ח כלכלית, אלפי ש"ח, בסימן (חיובי = ארוך מט"ח). לא מוכפל בנוציונל של חוזה/אופציה (נשאר pending).
  eq_value_k  שווי הוגן של חשיפה מנייתית (לצורך פירוק לפי מדד) - בנגזרים: pending עד חישוב נוציונל.

הכלל המרכזי (כפי שהוגדר בפרויקט): חשיפה דרך מניה/קרן במט"ח חשופה במלואה למט"ח; חשיפה דרך החלף/חוזה אינה חשופה
(רק הפרש ריבית מול תשואה), וחוזה מט"ח (פורוורד) הוא פוזיציית מט"ח נקייה, בסימן.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indexfx.vendor.index_classify import classify_index  # noqa: E402

FORMS = {
    "STOCK_DIRECT": "מניה ישירה",
    "WARRANT": "כתב אופציה",
    "ETF": "קרן סל (נסחרת)",
    "MUTUAL_FUND": "קרן נאמנות",
    "PRIVATE_FUND": "קרן השקעה (לא סחירה)",
    "OPTION": "אופציה",
    "FUTURE": "חוזה עתידי",
    "SWAP_EQ_UNFUNDED": "החלף מדד/מניה (לא ממומן)",
    "SWAP_EQ_FUNDED": "החלף מדד/מניה (ממומן)",
    "FX_FWD_UNFUNDED": "פורוורד מט\"ח (לא ממומן)",
    "FX_FWD_FUNDED": "פורוורד מט\"ח (ממומן)",
    "SWAP_RATE": "החלף ריבית",
    "SWAP_OTHER": "החלף אחר (מדד מחירים, repo ועוד)",
    "STRUCTURED": "מוצר מובנה",
    "BOND": "אג\"ח / ני\"ע מסחרי",
    "CASH": "מזומן/פיקדון",
    "LOAN": "הלוואה/אשראי",
    "REAL_ESTATE": "נדל\"ן",
    "OTHER": "אחר",
}
FX_ROUTES = {
    "direct_ccy": "נקוב במטבע חוץ - חשוף במלואו",
    "embedded_unhedged": "נקוב בש\"ח אך הנכס זר ולא מגודר - חשוף במלואו",
    "hedged": "קרן מנוטרלת/מגודרת מט\"ח - לא חשוף",
    "none": "ש\"ח / ישראל - לא חשוף",
    "swap_carry": "החלף/חוזה על מדד - אין חשיפת מט\"ח, רק הפרש ריבית",
    "fx_forward": "פוזיציית מט\"ח בסימן (פורוורד)",
    "pending": "נגזר סחיר - נוציונל יחושב בשלב א.5",
}

SHEET_FORM = {
    "מניות מבכ ויהש": "STOCK_DIRECT", "לא סחיר מניות מבכ ויהש": "STOCK_DIRECT",
    "כתבי אופציה": "WARRANT", "לא סחיר כתבי אופציה": "WARRANT",
    "קרנות סל": "ETF", "קרנות נאמנות": "MUTUAL_FUND", "קרנות השקעה": "PRIVATE_FUND",
    "אופציות": "OPTION", "לא סחיר אופציות": "OPTION", "חוזים עתידיים": "FUTURE",
    "מוצרים מובנים": "STRUCTURED", "לא סחיר מוצרים מובנים": "STRUCTURED",
    "איגרות חוב": "BOND", "איגרות חוב ממשלתיות": "BOND", "ניירות ערך מסחריים": "BOND",
    "לא סחיר איגרות חוב": "BOND", "לא סחיר איגרות חוב ממשלתיות": "BOND",
    "לא סחיר איגרות חוב מיועדות": "BOND", "לא סחיר ניירות ערך מסחריים": "BOND",
    "מזומנים ושווי מזומנים": "CASH", "פיקדונות מעל 3 חודשים": "CASH",
    "הלוואות": "LOAN", "מסגרות אשראי": "LOAN", "אפיק השקעה מובטח תשואה": "LOAN",
    "זכויות מקרקעין": "REAL_ESTATE", "השקעה בחברות מוחזקות": "OTHER", "נכסים אחרים": "OTHER",
    "יתרות התחייבות להשקעה": "OTHER",
}
FOREIGN_CCY_OK = re.compile(r"^[A-Z]{3}$")
HEDGED = re.compile(r"מנוטרל|מגודר|hedg|\bhdg\b|\bchf\s*hedged|\b(?:eur|gbp|usd)\s*h\b", re.I)
UNHEDGED_TAG = re.compile(r"חשופת מט")
LEVERAGE = re.compile(r"מינוף|ממונף|הפוך|short|inverse|ultra|\b[23]x\b|x[23]\b|\b-?[123]x\b|leveraged", re.I)
IL_INDEX_NAMES = [  # "125 מניות בארץ - ..." -> מזהה ת"א
    (re.compile(r"^\s*125\s+מניות בארץ|ת\"?א\W*125|tel\W*aviv\W*125", re.I), "ta125", "ת\"א 125"),
    (re.compile(r"^\s*35\s+מניות בארץ|ת\"?א\W*35\b|tel\W*aviv\W*35\b", re.I), "ta35", "ת\"א 35"),
    (re.compile(r"^\s*90\s+מניות בארץ|ת\"?א\W*90|tel\W*aviv\W*90", re.I), "ta90", "ת\"א 90"),
    (re.compile(r"^\s*100\s+מניות בארץ|ת\"?א\W*100\b", re.I), "ta100", "ת\"א 100"),
]
FUND_ASSET = re.compile(r"(מניות|אג\"?ח|bond|fixed income|equity|currency|סחורות|commodit|money market|כספי)", re.I)


def num(s) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def idx_of(text) -> tuple[str, str]:
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return ("", "")
    t = str(text)
    for rx, k, l in IL_INDEX_NAMES:
        if rx.search(t):
            return (k, l)
    return classify_index(t)


def fund_asset_class(fund_class: str, name: str) -> str:
    s = f"{fund_class or ''} {name or ''}".lower()
    if re.search(r"currency funds|מט\"ח\W*(כספי)?\W*$", s):
        return "fx"
    if re.search(r"אג\"?ח|bond|fixed income|תל\W?בונד|תל\W?גוב|money market|כספי|מק\"מ", s):
        return "bond"
    if re.search(r"סחורות|commodit|זהב|gold|silver", s):
        return "commodity"
    if re.search(r"מניות|equity|index funds|s&p|nasdaq|msci|stoxx|ftse|dax", s):
        return "equity"
    return "other"


def classify(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["fair_value_k"] = num(df["fair_value_k"]).fillna(num(df["swap_net_fv_k"]))
    df["pct_total"] = num(df["pct_total"])
    df["fx_rate"] = num(df["fx_rate"])
    df["form"] = df["sheet"].map(SHEET_FORM)
    # נגזרים ("לא סחיר נגזרים אחרים") לפי סוג העסקה
    sw = df["sheet"] == "לא סחיר נגזרים אחרים"
    ma = df.loc[sw, "main_attr"].astype(str)
    at = df.loc[sw, "swap_asset_type"].astype(str)
    sw_form = pd.Series("SWAP_OTHER", index=ma.index)
    funded = ma.str.startswith("Funded")
    sw_form[ma.str.contains("Forward") & at.str.startswith("מט")] = "FX_FWD_UNFUNDED"
    sw_form[(ma.str.contains("Forward") & at.str.startswith("מט")) & funded] = "FX_FWD_FUNDED"
    eq = ma.str.contains("Equity|Total Return", regex=True) | at.str.startswith("מניות")
    sw_form[eq & ~sw_form.str.startswith("FX_FWD")] = "SWAP_EQ_UNFUNDED"
    sw_form[eq & funded & ~sw_form.str.startswith("FX_FWD")] = "SWAP_EQ_FUNDED"
    sw_form[ma.str.contains("Interest Rate") & ~eq] = "SWAP_RATE"
    df.loc[sw, "form"] = sw_form
    df["form"] = df["form"].fillna("OTHER")

    # ── מטבע/מדד/סוג נכס ─────────────────────────────────────────────
    name = df["name"].fillna("").astype(str)
    df["index_key"] = ""
    df["index_label"] = ""
    df["asset_class"] = "other"
    df["geo"] = df["il_abroad"].map({"ישראל": "IL", "חו\"ל": "ABROAD"}).fillna("UNKNOWN")
    ccy = df["ccy"].astype(str)
    foreign = ccy.str.match(FOREIGN_CCY_OK) & (ccy != "ILS")

    # מניות: המדד = המניה עצמה (ISIN/שם); הנכס הוא מניה
    m = df.form.isin(["STOCK_DIRECT", "WARRANT"])
    df.loc[m, "asset_class"] = "equity"
    df.loc[m, "index_key"] = "stock:" + df.loc[m, "sec_id"].astype(str)
    df.loc[m, "index_label"] = name[m]

    # קרנות
    f = df.form.isin(["ETF", "MUTUAL_FUND", "PRIVATE_FUND"])
    fc = df["fund_class"].fillna("").astype(str)
    src = (fc + " " + name).where(f)
    pairs = [idx_of(fc[i] + " | " + name[i]) if f[i] else ("", "") for i in df.index]
    df.loc[f, "index_key"] = [p[0] for p, ff in zip(pairs, f) if ff]
    df.loc[f, "index_label"] = [p[1] for p, ff in zip(pairs, f) if ff]
    df.loc[f, "asset_class"] = [fund_asset_class(a, b) for a, b in zip(fc[f], name[f])]
    df["hedged"] = False
    df.loc[f, "hedged"] = src[f].str.contains(HEDGED, na=False)
    df["leveraged"] = False
    df.loc[f, "leveraged"] = src[f].str.contains(LEVERAGE, na=False)

    # אג"ח/מזומן/הלוואות/נדל"ן
    df.loc[df.form.isin(["BOND", "STRUCTURED"]), "asset_class"] = "bond"
    df.loc[df.form == "CASH", "asset_class"] = "cash"
    df.loc[df.form.isin(["LOAN", "REAL_ESTATE"]), "asset_class"] = "other"

    # נגזרים סחירים
    ud = df["underlying"].astype(str)
    for form in ("FUTURE", "OPTION"):
        m = df.form == form
        pr = [idx_of(f"{a} {b}") for a, b in zip(name[m], ud[m])]
        df.loc[m, "index_key"] = [p[0] for p in pr]
        df.loc[m, "index_label"] = [p[1] for p in pr]
        cls = np.select([ud[m].str.contains("מניות"), ud[m].str.contains("ריבית|אג"), ud[m].str.contains("מט")],
                        ["equity", "rate", "fx"], default="other")
        df.loc[m, "asset_class"] = cls

    # החלפים
    m = df.form.isin(["SWAP_EQ_UNFUNDED", "SWAP_EQ_FUNDED"])
    pr = [idx_of(t) for t in df.loc[m, "swap_ticker"]]
    df.loc[m, "index_key"] = [p[0] for p in pr]
    df.loc[m, "index_label"] = [p[1] for p in pr]
    df.loc[m, "asset_class"] = "equity"
    m = df.form.isin(["FX_FWD_UNFUNDED", "FX_FWD_FUNDED"])
    df.loc[m, "asset_class"] = "fx"
    df.loc[m, "index_key"] = "fx:" + df.loc[m, "swap_ticker"].astype(str)
    df.loc[df.form == "SWAP_RATE", "asset_class"] = "rate"

    # ── מסלול המט"ח ─────────────────────────────────────────────────
    # עיקרון: נכס נקוב במטבע חוץ = חשיפה מלאה למטבע הנקוב (גידור ל-ש"ח, אם קיים, מופיע בנפרד בפורוורדים).
    # סימון "Hedged" בשם קרן זרה מתייחס לגידור למטבע הקרן ולא לשקל - לכן לא מבטל חשיפה.
    # רק קרן נקובה בש"ח נבחנת לפי סיווג הקרן: "מנוטרלת מט"ח" = מגודרת, "חשופת מט"ח" = חשופה.
    route = pd.Series("none", index=df.index)
    conf = pd.Series("rule", index=df.index)
    ccy_s = ccy.where(foreign, "ILS")
    df["fx_ccy"] = ccy_s
    spot = df.form.isin(["STOCK_DIRECT", "WARRANT", "ETF", "MUTUAL_FUND", "PRIVATE_FUND", "BOND", "STRUCTURED",
                         "CASH", "LOAN", "REAL_ESTATE", "OTHER"])
    route[spot & foreign] = "direct_ccy"
    il_fund = df.form.isin(["ETF", "MUTUAL_FUND"]) & ~foreign
    tag_hedged = fc.str.contains("מנוטרלת")
    tag_exposed = fc.str.contains("חשופת מט")
    route[il_fund & tag_hedged] = "hedged"
    route[il_fund & ~tag_hedged & tag_exposed] = "embedded_unhedged"
    untagged_foreign = il_fund & ~tag_hedged & ~tag_exposed & (df.geo == "ABROAD") & df.asset_class.isin(["equity", "bond", "commodity"])
    route[untagged_foreign] = np.where(df.hedged[untagged_foreign], "hedged", "embedded_unhedged")
    conf[untagged_foreign] = "inferred"
    route[df.form.isin(["SWAP_EQ_UNFUNDED", "SWAP_EQ_FUNDED", "SWAP_RATE", "SWAP_OTHER"])] = "swap_carry"
    route[df.form.isin(["FX_FWD_UNFUNDED", "FX_FWD_FUNDED"])] = "fx_forward"
    route[df.form.isin(["FUTURE", "OPTION"])] = "pending"
    df["fx_route"] = route
    df["fx_route_confidence"] = conf

    fv = df["fair_value_k"].fillna(0.0)
    df["fx_exposure_k"] = np.where(route.isin(["direct_ccy", "embedded_unhedged"]), fv, 0.0)
    # עסקאות מט"ח: פיצול רגליים (פרק נפרד ב-a3: explode_fx_forwards)
    df["eq_value_k"] = np.where((df.asset_class == "equity") & df.form.isin(
        ["STOCK_DIRECT", "WARRANT", "ETF", "MUTUAL_FUND", "PRIVATE_FUND"]), fv, 0.0)
    return df


def explode_fx_forwards(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """כל רגל לא-שקלית של פורוורד -> חשיפת מט"ח בסימן, אלפי ש"ח (נקוב × שער / 1000).

    בדיקת עקביות לכל עסקה: שווי שתי הרגליים (נקוב × שער) אמור להתאזן. עסקה שבה הפער > 50% מהרגל הגדולה
    (למשל רגל אחת באפס, או נקוב ביחידות שגויות) מוחרגת ומדווחת ב-anomalies - לא מנחשים איזו רגל נכונה.
    פער קטן (עד 50%) נובע מכך ש-נקוב הרגל השקלית נקבע בשער החוזה ולא בשער הספוט - תקין.
    """
    d = df[df.form.isin(["FX_FWD_UNFUNDED", "FX_FWD_FUNDED"])].copy()
    v1 = num(d["leg1_nominal"]) * num(d["leg1_fx"])
    v2 = num(d["leg2_nominal"]) * num(d["leg2_fx"])
    d["rel_gap"] = (v1 + v2).abs() / np.maximum(v1.abs(), v2.abs()).replace(0, np.nan)
    d["consistent"] = d["rel_gap"].fillna(1.0) <= 0.5
    anomalies = d[~d["consistent"]]
    legs = []
    for n in (1, 2):
        x = d[d["consistent"]][["legal_id", "system", "track", "form", "swap_ticker", "report_date"]].copy()
        x["leg"] = n
        x["ccy"] = d.loc[x.index, f"leg{n}_ccy"].astype(str)
        x["nominal"] = num(d.loc[x.index, f"leg{n}_nominal"])
        x["rate"] = num(d.loc[x.index, f"leg{n}_fx"])
        x["fx_exposure_k"] = x["nominal"] * x["rate"] / 1000.0
        legs.append(x)
    out = pd.concat(legs)
    out = out[(out.ccy != "ILS") & out.ccy.str.match(FOREIGN_CCY_OK) & out.fx_exposure_k.notna()]
    return out, anomalies


if __name__ == "__main__":
    src = Path("data/positions.csv.gz")
    df = classify(pd.read_csv(src, low_memory=False))
    df.to_csv("data/positions_classified.csv.gz", index=False, compression="gzip")
    fw, an = explode_fx_forwards(df)
    fw.to_csv("data/fx_forward_legs.csv.gz", index=False, compression="gzip")
    an.to_csv("data/fx_forward_anomalies.csv.gz", index=False, compression="gzip")
    print(f"[a2] {len(an):,} עסקאות פורוורד לא עקביות הוחרגו")
    print(f"[a2] {len(df):,} שורות מסווגות; {len(fw):,} רגלי פורוורד")
    print(df.groupby("form").agg(n=("form", "size"), fv_mil=("fair_value_k", lambda s: s.sum() / 1e3)).round(0))
    print(df.fx_route.value_counts())
