"""שערוך הנגזרים על מניות חו"ל בין רבעונים - כדי להפריד בתנועת הרווח הצבור בין שערוך (לא מסחר) לבין מסחר/סילוק.

לכל שורת החלף/חוזה ב-q0 (חשיפה מדויקת a6, בש"ח): שערוך = חשיפה × תשואת נכס הבסיס q0->q1 × (שער$ q1 / שער$ q0)
                                                      − (בהחלף על מדד תשואה כוללת) חשיפה × ריבית דולרית × זמן
סדרת נכס הבסיס, לפי הסדר (ולכל שורה נרשם המקור):
  exact      - טיקר ההחלף ממופה ב-INDICES/swap_ticker_map.csv לסדרה קיימת, או שורש החוזה ב-CONTRACT_SPECS
  proxy:<id> - טבלת PROXY למטה (מדד קרוב מאותו מוצר/אזור; שקוף ונספר בנפרד)
  region     - אין התאמה: S&P 500 TR (ארה"ב) או ACWI (אחר) - נספר בנפרד
פלט: data/flows/derivative_valuation.csv.gz (מסלול-רבעון: שערוך, חלוקה לפי מקור)
"""
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from indexfx.fh.swap_index_pricing import normalize_ticker  # noqa: E402
from indexfx.vendor.futures_notional import CONTRACT_SPECS  # noqa: E402
from d2_article_scenario import is_us  # noqa: E402

IDX = Path("/home/user/revach123/indices/data/prices")
PROXY = {  # טיקר/שורש -> סדרה קרובה (תיעוד: אותו מדד-אם או אותו אזור)
    "NDUEACWF": "acwi_proxy", "M1WD": "msci_world_proxy", "NDDUWI": "msci_world_proxy", "MXWO": "msci_world_proxy",
    "NDUEEGF": "msci_em_proxy", "MXEF": "msci_em_proxy", "MES": "msci_em_proxy", "RBE": "msci_em_proxy",
    "MVSMHTR": "sp500_tech", "SOX": "sp500_tech", "IXTTR": "sp500_tech", "S5INFT": "sp500_tech",
    "IXMTR": "sp500_financials", "S5FINL": "sp500_financials", "IXVTR": "sp500_healthcare", "S5HLTH": "sp500_healthcare",
    "IXETR": "sp500_energy", "S5ENRS": "sp500_energy",
    "SX5T": "stoxx50_tr", "SX7GR": "stoxx50_tr", "SXXGR": "stoxx50_tr", "SXO": "stoxx50", "TP": "topix", "TMI": "topix",
    "2330 TT": "taiwan", "NDDUJN": "topix", "TPXDDVD": "topix", "XNDX": "nasdaq100_tr", "RU20INTR": "russell2000_tr",
}
TR_HINT = ("TR", "NTR", "GR", "XNDX", "SPTR", "NDUE", "NDDU", "M1", "RU20INTR")


def series():
    have = {f[:-4] for f in os.listdir(IDX) if f.endswith(".csv")}
    cache = {}

    def get(i):
        if i not in cache:
            cache[i] = pd.read_csv(IDX / f"{i}.csv", parse_dates=["date"]).set_index("date").close.sort_index()
        return cache[i]
    tmap = {}
    for r in csv.DictReader(open(IDX.parent / "swap_ticker_map.csv", encoding="utf-8")):
        i = (r.get("index_id") or "").strip()
        if i in have:
            tmap[(r.get("swap_ticker") or "").strip().upper()] = i
    return have, get, tmap


def resolve(row, have, tmap):
    if row.category == "FUTURE":
        root = str(row.root or "")
        spec = CONTRACT_SPECS.get(root, (None, None))[1]
        if spec in have:
            return spec, "exact"
        if root in PROXY:
            return PROXY[root], f"proxy:{PROXY[root]}"
    else:
        t = normalize_ticker(row.ticker) or ""
        if t in tmap:
            return tmap[t], "exact"
        if t in PROXY:
            return PROXY[t], f"proxy:{PROXY[t]}"
    return ("sp500tr" if is_us(f"{row.ticker} {row.name} {row.root}") else "acwi_proxy"), "region"


def main():
    have, get, tmap = series()
    px = pd.read_csv("data/market/prices.csv", parse_dates=["date"]).pivot(index="date", columns="symbol", values="close")
    irx = px["^IRX"].dropna() / 100
    fx = pd.read_csv("data/market/boi_usdils.csv", parse_dates=["date"]).set_index("date").value
    qs = sorted(p.name.replace("deriv_", "").replace(".csv.gz", "") for p in Path("data/history").glob("deriv_*.csv.gz"))
    qs = [q for q in qs if q != "2026Q3"]
    st = pd.read_csv("data/history/track_quarter_state.csv.gz")[["q", "report_date"]].drop_duplicates("q").set_index("q").report_date
    out = []
    for q0, q1 in zip(qs[:-1], qs[1:]):
        d0, d1 = pd.Timestamp(st[q0]), pd.Timestamp(st[q1])
        dx = pd.read_csv(f"data/history/deriv_{q0}.csv.gz", low_memory=False)
        dx = dx[(dx.equity == True) & ~(dx.country.eq("ישראל") | (dx.ccy.eq("ILS") & dx.leg2_ccy.fillna("ILS").eq("ILS")))].copy()  # noqa: E712
        dx = dx[dx.category.isin(["SWAP", "FUTURE"])]
        dx["exp_k"] = dx.ratio * dx.total_k
        res = [resolve(r, have, tmap) for r in dx.itertuples()]
        dx["series"], dx["source"] = [x[0] for x in res], [x[1] for x in res]
        # בדיקת תקינות סדרה בתקופה: שינוי יומי מעל 25% = שבר בסדרה (למשל החלפת יחידות) -> סדרה חלופית מאותו שוק
        FALLBACK = {"topix": "nikkei225"}
        def valid(i):
            s = get(i)
            w = s[(s.index > d0 - pd.Timedelta(days=5)) & (s.index <= d1)]
            return len(w) > 5 and w.pct_change().abs().max() < 0.25
        for i in list(dx.series.unique()):
            if not valid(i):
                alt = FALLBACK.get(i) or ("sp500tr" if i.startswith(("sp500", "nasdaq", "russell", "dow")) else "acwi_proxy")
                m = dx.series.eq(i)
                dx.loc[m, "source"] = f"proxy:{alt}(סדרה {i} שבורה)"
                dx.loc[m, "series"] = alt
                print(f"[e1b] {q0}->{q1}: סדרה {i} שבורה בתקופה -> {alt}", flush=True)
        ret = {i: get(i).asof(d1) / get(i).asof(d0) - 1 for i in dx.series.unique()}
        dx["r"] = dx.series.map(ret)
        tau = (d1 - d0).days / 365.0
        i_usd = irx[(irx.index > d0) & (irx.index <= d1)].mean()
        tr = dx.category.eq("SWAP") & (dx.series.str.contains("tr|proxy") | dx.ticker.astype(str).str.upper().str.contains("|".join(TR_HINT)))
        dx["val_k"] = dx.exp_k * (dx.r - np.where(tr, i_usd * tau, 0.0)) * (fx.asof(d1) / fx.asof(d0))
        dx["legal_id"] = dx.legal_id.astype(int)
        dx["track"] = pd.to_numeric(dx.track, errors="coerce")
        g = dx.groupby(["legal_id", "track"])
        o = g.val_k.sum().rename("valuation_k").to_frame()
        for src in ("exact", "region"):
            o[f"exp_{src}_k"] = dx[dx.source.eq(src)].groupby(["legal_id", "track"]).exp_k.sum()
        o["exp_proxy_k"] = dx[dx.source.str.startswith("proxy")].groupby(["legal_id", "track"]).exp_k.sum()
        o = o.fillna(0.0).reset_index()
        o["q0"], o["q1"] = q0, q1
        out.append(o)
        tot = dx.exp_k.sum()
        print(f"[e1b] {q0}->{q1}: שערוך {dx.val_k.sum()/1e6:+.1f} מיליארד; מקור החשיפה: מדויק {dx[dx.source.eq('exact')].exp_k.sum()/tot:.0%}, "
              f"קרוב {dx[dx.source.str.startswith('proxy')].exp_k.sum()/tot:.0%}, אזורי {dx[dx.source.eq('region')].exp_k.sum()/tot:.0%}", flush=True)
    pd.concat(out).to_csv("data/flows/derivative_valuation.csv.gz", index=False, compression="gzip")


if __name__ == "__main__":
    main()
