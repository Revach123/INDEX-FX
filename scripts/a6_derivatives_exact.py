"""שלב א.6 - חשיפה מדויקת בנגזרים (החלפים, חוזים עתידיים, אופציות) לכל שורה, בקוד המאומת של MASLULIM.

הקוד הוא העתק של MASLULIM/scripts/funds_holdings (indexfx/fh/) - כולל ההכרעות שאומתו גוף-גוף מול הדוחות
(מוסכמות "ערך נקוב", רגל-יחידות × שער נכס הבסיס, עוגני עסקה, תקרות סבירות). שינוי יחיד: במקום להוריד את
סדרות המדדים מ-raw.githubusercontent.com, הן נקראות משכפול מקומי של Revach123/INDICES (אותם קבצים).
פנייה ל-Yahoo (אופציה על מניה בודדת בלי סדרה ב-INDICES) נחסמת -> הקוד עובר לחלופה שלו (שווי מדווח) ונספר.

פלט: data/deriv_exact.csv.gz - שורה לנגזר: key, category, ratio (חשיפה כשבר מנכסי המסלול), equity, ticker/root, row_pct (שווי הוגן כשבר)
הרצה: python scripts/a6_derivatives_exact.py --reports-dir <MASLULIM>/reports --indices-dir <INDICES>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RAW = "https://raw.githubusercontent.com/Revach123/INDICES/main/"
BLOCKED = {"n": 0}


class _Resp:
    def __init__(self, text, status=200):
        self.text, self.status_code = text, status

    def raise_for_status(self):
        if self.status_code != 200:
            raise requests.HTTPError(f"{self.status_code}")

    def json(self):
        import json
        return json.loads(self.text)


def install_local_indices(indices_dir: Path):
    def fake_get(url, *a, **kw):
        if url.startswith(RAW):
            p = indices_dir / url[len(RAW):]
            return _Resp(p.read_text(encoding="utf-8")) if p.exists() else _Resp("", 404)
        BLOCKED["n"] += 1
        raise requests.ConnectionError(f"offline: {url}")
    requests.get = fake_get  # כל המודולים קוראים requests.get דרך המודול


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports-dir", type=Path, required=True)
    ap.add_argument("--indices-dir", type=Path, required=True)
    ap.add_argument("--anchors-root", type=Path, default=None, help="שורש כל הדוחות לעוגני עסקה (ברירת מחדל: reports-dir)")
    ap.add_argument("--out", type=Path, default=Path("data/deriv_exact.csv.gz"))
    a = ap.parse_args()
    install_local_indices(a.indices_dir)
    from indexfx.fh import swap_deal_anchors
    swap_deal_anchors.REPORTS_ROOT = a.anchors_root or a.reports_dir
    swap_deal_anchors.CACHE = Path(".cache/swap_deal_anchors.json")
    from indexfx.fh import derivatives_exposure as dx
    from indexfx.fh.file_list import latest_per_company, list_files
    from indexfx.fh.sheet_source import build_source

    files = latest_per_company(list_files(a.reports_dir))
    src = [b for b in build_source(files) if b["Category"] in (dx.FUTURES_CATEGORY, dx.SWAP_CATEGORY,
                                                                 dx.OPTIONS_LISTED_CATEGORY, dx.OPTIONS_OTC_CATEGORY)
           or True]
    total = dx.total_assets_by_key(src)
    det_f, det_s, det_ol, det_oo = [], [], [], []
    dx._futures_exposure(src, total, det_f)
    dx._swap_exposure(src, total, det_s)
    dx._options_exposure(src, total, dx.OPTIONS_LISTED_CATEGORY, det_ol)
    dx._options_exposure(src, total, dx.OPTIONS_OTC_CATEGORY, det_oo)
    rows = []
    for cat, det in (("FUTURE", det_f), ("SWAP", det_s), ("OPTION_LISTED", det_ol), ("OPTION_OTC", det_oo)):
        for d in det:
            r = d["row"]
            rows.append({
                "key": d["key"], "legal_id": d["key"].split("_")[0], "track": d["key"].split("_", 1)[1],
                "category": cat, "ratio": d.get("ratio"), "row_pct": d.get("row_pct"), "equity": d.get("equity"),
                "root": d.get("root"), "ticker": d.get("ticker") or r.get("טיקר") or r.get("מספר נייר ערך"),
                "name": r.get("שם נייר ערך"), "asset_type": r.get("סוג הנכס"), "main_type": r.get("מאפיין עיקרי"),
                "underlying": r.get("נכס בסיס"), "ccy": r.get("מטבע פעילות") or r.get("מטבע פעילות (רגל 1)"),
                "leg2_ccy": r.get("מטבע פעילות (רגל 2)"), "country": r.get("מדינה לפי חשיפה כלכלית"),
                "total_k": total.get(d["key"]),
            })
    out = pd.DataFrame(rows)
    out.to_csv(a.out, index=False, compression="gzip")
    print(f"[a6] {len(out):,} שורות נגזרים; פניות רשת שנחסמו (Yahoo): {BLOCKED['n']}")
    print(out.groupby("category").agg(n=("key", "size"), sum_ratio=("ratio", "sum")).round(2))


if __name__ == "__main__":
    main()
