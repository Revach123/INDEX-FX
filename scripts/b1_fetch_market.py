"""שלב ב.1 - משיכת נתוני שוק יומיים.

מקורות:
  - Yahoo Finance דרך ספריית yfinance (שימוש רגיל, בלי עקיפות): מדדים, ETF עולמיים, USD/ILS.
  - בנק ישראל (edge.boi.gov.il, SDMX): שער יציג USD/ILS וריבית בנק ישראל.
פלט (data/market/):
  prices.csv       date,symbol,close   (סגירה יומית)
  boi_usdils.csv   date,value
  boi_rate.csv     date,value
בדיקות איכות מודפסות: כמות ימים, חורים, שינוי יומי קיצוני.
הרצה: python scripts/b1_fetch_market.py [--start 2022-01-01]
"""
from __future__ import annotations

import argparse
import io
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf

UA = "index-fx-research/0.1 (github.com/Revach123/INDEX-FX)"
OUT = Path("data/market")

# גורם: US / ROW / IL / FX
SYMBOLS = {
    "^GSPC": "US", "^NDX": "US", "^RUT": "US", "^DJI": "US", "^SOX": "US",
    "^STOXX50E": "ROW", "^GDAXI": "ROW", "^FTSE": "ROW", "^N225": "ROW", "^HSI": "ROW",
    "ACWI": "ROW", "URTH": "ROW", "EEM": "ROW", "VEA": "ROW",
    "^TA125.TA": "IL", "TA35.TA": "IL", "^TA90.TA": "IL",
    "ILS=X": "FX",
    "^IRX": "RATE",   # תשואת אג"ח ממשלת ארה"ב 13 שבועות (%) - קירוב לרגל הריבית הדולרית בהחלף
}
BOI = "https://edge.boi.gov.il/FusionEdgeServer/sdmx/v2/data/dataflow/BOI.STATISTICS/{flow}?startperiod={start}&format=csv"


def fetch_yahoo(start: str) -> pd.DataFrame:
    rows = []
    for sym in SYMBOLS:
        try:
            h = yf.Ticker(sym).history(start=start, auto_adjust=False)
        except Exception as e:  # noqa: BLE001
            print(f"[b1] {sym}: כשל {e!r}")
            continue
        if h.empty:
            print(f"[b1] {sym}: אין נתונים")
            continue
        s = h["Close"].copy()
        s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
        rows.append(pd.DataFrame({"date": s.index, "symbol": sym, "close": s.values}))
    return pd.concat(rows, ignore_index=True)


def fetch_boi(flow: str, start: str) -> pd.DataFrame:
    r = requests.get(BOI.format(flow=flow, start=start), headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    d = pd.read_csv(io.StringIO(r.text))
    return d[["TIME_PERIOD", "OBS_VALUE"]].rename(columns={"TIME_PERIOD": "date", "OBS_VALUE": "value"})


def quality(prices: pd.DataFrame):
    print("[b1] בקרת איכות:")
    for sym, g in prices.groupby("symbol"):
        g = g.sort_values("date")
        ret = g.close.pct_change()
        gaps = g.date.diff().dt.days.max()
        print(f"  {sym:10s} n={len(g):5d} {g.date.min().date()}→{g.date.max().date()} פער מקס'={gaps:.0f}י' "
              f"שינוי יומי קיצוני={ret.abs().max():.1%} אפסים/שליליים={(g.close <= 0).sum()}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2022-01-01")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    p = fetch_yahoo(a.start)
    p.to_csv(OUT / "prices.csv", index=False)
    quality(p)
    fetch_boi("EXR/1.0/RER_USD_ILS", a.start).to_csv(OUT / "boi_usdils.csv", index=False)
    r = fetch_boi("BR/1.0", a.start)
    r.to_csv(OUT / "boi_rate.csv", index=False)
    print("[b1] BoI שער:", len(pd.read_csv(OUT / "boi_usdils.csv")), "ימים; ריבית:", len(r))
