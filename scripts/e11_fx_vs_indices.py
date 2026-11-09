"""קשר בין שינוי שער הדולר/שקל לבין: S&P 500 (דולרי), ת"א-125, וההפרש ביניהם (S&P דולרי פחות ת"א-125).

תדירויות: יומי, שבועי, חודשי, רבעוני (2022 עד היום; שער יציג בנק ישראל, מדדים מ-prices.csv).
מתאם פירסון + רווח סמך 95% (Fisher), ורגרסיה מרובה: Δדולר = a + b1·S&P + b2·ת"א-125 (שגיאות OLS).
יומי: השער היציג נקבע בצהרי יום המסחר בישראל, לפני פתיחת וול סטריט - לכן גם S&P של יום קודם.
פלט: data/results/fx_vs_indices.csv
"""
import numpy as np
import pandas as pd

px = pd.read_csv("data/market/prices.csv", parse_dates=["date"]).pivot_table(index="date", columns="symbol", values="close")
fx = pd.read_csv("data/market/boi_usdils.csv", parse_dates=["date"]).set_index("date").value
lv = pd.DataFrame({"fx": fx, "sp": px["^GSPC"], "ta": px["^TA125.TA"]})


def ci(r, n):
    z, s = np.arctanh(r), 1 / np.sqrt(n - 3)
    return np.tanh(z - 1.96 * s), np.tanh(z + 1.96 * s)


rows = []
for lab, rule in (("יומי", None), ("שבועי", "W-FRI"), ("חודשי", "ME"), ("רבעוני", "QE")):
    L = lv.ffill().dropna() if rule is None else lv.resample(rule).last().dropna()
    if rule is None:
        L = lv.dropna(subset=["fx", "ta"]).copy()
        L["sp"] = lv.sp.ffill().reindex(L.index)
    r = L.pct_change().dropna() * 100
    if rule is None:
        r["sp_prev"] = r.sp.shift(1)
    r["spread"] = r.sp - r.ta
    r = r.dropna()
    n = len(r)
    for x, xl in (("sp", "S&P דולרי"), ("ta", "ת\"א-125"), ("spread", "הפרש S&P דולרי פחות ת\"א-125")) + ((("sp_prev", "S&P דולרי של יום קודם"),) if rule is None else ()):
        c = r.fx.corr(r[x])
        lo, hi = ci(c, n)
        rows.append({"תדירות": lab, "משתנה": xl, "n": n, "מתאם": c, "רס\"ב 95% מ": lo, "רס\"ב 95% עד": hi})
    X = np.column_stack([np.ones(n), r.sp, r.ta])
    b, res, *_ = np.linalg.lstsq(X, r.fx.values, rcond=None)
    e = r.fx.values - X @ b
    se = np.sqrt(np.diag(e @ e / (n - 3) * np.linalg.inv(X.T @ X)))
    r2 = 1 - e @ e / ((r.fx - r.fx.mean()) ** 2).sum()
    rows.append({"תדירות": lab, "משתנה": f"רגרסיה מרובה: b(S&P)={b[1]:.3f}±{1.96*se[1]:.3f}, b(ת\"א)={b[2]:.3f}±{1.96*se[2]:.3f}, R²={r2:.2f}", "n": n})
out = pd.DataFrame(rows)
out.round(3).to_csv("data/results/fx_vs_indices.csv", index=False)
pd.set_option("display.width", 250, "display.max_colwidth", 120)
print(out.round(2).to_string(index=False))
print("תקופה:", lv.dropna().index.min().date(), "→", lv.dropna().index.max().date())
