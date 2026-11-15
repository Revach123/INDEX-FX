"""שלב א: חלוקת המסלולים והקרנות לפי סוג.  פלט: data/classification/tracks_classified.csv, funds_classified.csv, stageA_summary.csv

מסלולים (data.gov, דוח חודשי 8.2026, כל מסלולי גמל/פנסיה/ביטוח):
  fe = חשיפה לחו"ל / נכסים (כולל נגזרים; יכול לעבור 100% כשיש מינוף)       fx = חשיפת מט"ח / נכסים
  שקלי:      fe < 10% וגם fx < 10%                             (לא משפיע)
  מט"חי:     fe >= 80%                                         (ריכוז בחו"ל: S&P, עוקב מדדי מניות וכד')
      לפי יחס גידור fx/fe:  לא מגודר >= 70% | מגודר <= 30% | חלקי בין לבין
  משולב:     כל השאר (ארץ + חו"ל), מחולק לפי רמת החשיפה לחו"ל לצורך מידע.
קרנות (funds.csv: דוח חודשי מלא + סיווג הרשות/הבורסה), רק קרנות עם שווי:
  מט"חית:    סיווג ראשי מניות בחו"ל / אג"ח בחו"ל / סחורות, או כספית מט"חית (חשיפת מט"ח >= 80%).
      גידור לפי חשיפת מט"ח בפועל: לא מגודרת >= 80% | מגודרת <= 20% | חלקית. תת-סוג: קרן מחקה / סל / פתוחה (אקטיבית).
  שקלית:     סיווג ראשי אג"ח בארץ, אג"ח בארץ משולבת, מניות בארץ, כספית שקלית (חשיפת מט"ח < 20%)
  משולבת:    כל השאר (גמישות, אגד קרנות, אסטרטגיות, גידור, מינוף, ועוד)
"""
import numpy as np
import pandas as pd

# ---------- מסלולים ----------
g = pd.read_csv("data/datagov/monthly.csv.gz", low_memory=False)
t = g[g.REPORT_PERIOD == 202608].copy()
for c in ("TOTAL_ASSETS", "FOREIGN_EXPOSURE", "FOREIGN_CURRENCY_EXPOSURE", "STOCK_MARKET_EXPOSURE"):
    t[c] = pd.to_numeric(t[c], errors="coerce")
n_all, a_all = len(t), t.TOTAL_ASSETS.sum() / 1e3
t = t[t.TOTAL_ASSETS > 0].dropna(subset=["FOREIGN_EXPOSURE", "FOREIGN_CURRENCY_EXPOSURE"]).copy()
t["A"] = t.TOTAL_ASSETS / 1e3                                  # מיליארדי ש"ח
t["fe"], t["fx"], t["eq"] = t.FOREIGN_EXPOSURE / t.TOTAL_ASSETS, t.FOREIGN_CURRENCY_EXPOSURE / t.TOTAL_ASSETS, t.STOCK_MARKET_EXPOSURE / t.TOTAL_ASSETS
t["hedge_ratio"] = (t.fx / t.fe.where(t.fe > 0.05)).clip(0, 1.5)
cls = np.where((t.fe < 0.10) & (t.fx < 0.10), "שקלי", np.where(t.fe >= 0.80, "מט\"חי", "משולב"))
sub = np.where(cls == "מט\"חי", np.where(t.hedge_ratio >= 0.70, "לא מגודר", np.where(t.hedge_ratio <= 0.30, "מגודר", "גידור חלקי")),
               np.where(cls == "משולב", np.where(t.fe < 0.40, "חו\"ל עד 40%", np.where(t.fe < 0.60, "חו\"ל 40%–60%", "חו\"ל 60%–80%")), "שקלי"))
t["class"], t["subclass"] = cls, sub
t["company"] = t.PARENT_COMPANY_NAME.fillna(t.MANAGING_CORPORATION).astype(str).str.strip()
t = t.rename(columns={"FUND_ID": "track_id", "FUND_NAME": "name", "domain": "type"})
t[["track_id", "name", "company", "type", "A", "fe", "fx", "eq", "hedge_ratio", "class", "subclass"]].round(4).to_csv("data/classification/tracks_classified.csv", index=False)
print(f"[א] מסלולים: {n_all} בדוח, {len(t)} עם נתוני חשיפה = {t.A.sum()/a_all:.1%} מהנכסים ({t.A.sum():,.0f} מיליארד)")
s = t.groupby(["class", "subclass"]).agg(מסלולים=("A", "size"), נכסים=("A", "sum"), חשיפה_לחו_ל=("fe", lambda v: np.average(v, weights=t.loc[v.index, "A"])),
                                         חשיפת_מט_ח=("fx", lambda v: np.average(v, weights=t.loc[v.index, "A"]))).reset_index()
s["share"] = s.נכסים / s.נכסים.sum()
s.insert(0, "מקור", "מסלולים")
print(s.round(3).to_string(index=False))
for thr in (0.75, 0.80, 0.90):
    m = (t.fe >= thr)
    print(f"   רגישות: חשיפה לחו\"ל >= {thr:.0%}: {m.sum()} מסלולים, {t.A[m].sum():,.0f} מיליארד")

# ---------- קרנות ----------
f = pd.read_csv("data/funds/funds.csv", dtype={"fund": str})
f = f[f.aum_m.notna() & (f.aum_m > 0)].copy()
f["A"] = f.aum_m / 1e3
f["fx"] = f.fx_pct.clip(lower=0, upper=105)
money_fx = f.primary.eq("קרן כספית") & (f.fx >= 80)
foreign = f.primary.isin(["מניות בחו\"ל", "אג\"ח בחו\"ל", "סחורות"]) | money_fx
local = f.primary.isin(["אג\"ח בארץ", "אג\"ח בארץ משולבת", "מניות בארץ", "קרן כספית"]) & ~money_fx & (f.fx.fillna(0) < 20)
f["class"] = np.where(foreign, "מט\"חית", np.where(local, "שקלית", "משולבת"))
hed_flag = f.hedged.astype(str).isin(["True", "true", "1"])
fxv = f.fx.where(f.fx.notna(), np.where(hed_flag, 0.0, 100.0))
f["hedge"] = np.where(f["class"] != "מט\"חית", "", np.where(fxv >= 80, "לא מגודרת", np.where(fxv <= 20, "מגודרת", "גידור חלקי")))
f["asset_type"] = np.where(money_fx, "כספית מט\"חית", f.primary)
f["structure"] = np.where(f.mimic.astype(str).isin(["True", "true", "1"]), np.where(f.kind.eq("קרן סל"), "קרן סל", "קרן מחקה"),
                          np.where(f.kind.eq("קרן סל"), "קרן סל", "אקטיבית"))
f["subclass"] = np.where(f["class"] == "מט\"חית", f.hedge, np.where(f["class"] == "שקלית", "שקלית", f.primary))
f.rename(columns={"fund": "fund_id"})[["fund_id", "name", "manager", "kind", "primary", "secondary", "mimic", "structure", "asset_type", "A", "eq_pct", "fx", "class", "hedge", "subclass"]].round(4).to_csv(
    "data/classification/funds_classified.csv", index=False)
print(f"\n[א] קרנות: {len(f)} עם שווי, {f.A.sum():,.0f} מיליארד")
sf = f.groupby(["class", "subclass"]).agg(קרנות=("A", "size"), שווי=("A", "sum")).reset_index()
sf["share"] = sf.שווי / sf.שווי.sum()
print(sf.round(3).to_string(index=False))
print(f[f["class"] == "מט\"חית"].groupby(["hedge", "structure"]).agg(קרנות=("A", "size"), שווי=("A", "sum")).round(1).to_string())
out = pd.concat([s.rename(columns={"נכסים": "שווי"}), sf.assign(מקור="קרנות").rename(columns={"קרנות": "מסלולים"})], ignore_index=True)
out.round(4).to_csv("data/classification/stageA_summary.csv", index=False)
