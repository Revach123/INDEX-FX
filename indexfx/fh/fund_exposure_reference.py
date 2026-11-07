"""החשיפה למניות שכל קרן ישראלית מדווחת (revach: data/funds_info/exposure.csv - "חשיפה למניות"
מדוח הקרן, כ-2,500 קרנות). משמש לקרנות שאינן מחקות מניות: קרן מניות אקטיבית (91%-99%),
אג"ח עם רכיב מניות (עד ~50%), גמישה, גידור, אגד קרנות, קרן הייטק - שעד עכשיו נספרו 0.
"""
from __future__ import annotations

import csv
import io
import os

import requests

EXPOSURE_CONTENTS_URL = "https://api.github.com/repos/Revach123/revach/contents/data/funds_info/exposure.csv"
TASE_SECURITIES_URL = "https://api.github.com/repos/Revach123/revach/contents/tase/securities.json"
TASE_STOCK_TYPE = "0101"  # securityFullTypeCode של מניה
TOKEN_ENV = "PAT"
FUND_COL = "מספר קרן"


def fund_number_key(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    try:
        return str(int(float(s)))
    except ValueError:
        return s or None


def parse_fund_exposure(text: str, word: str = "מניות") -> dict[str, float]:
    """מספר קרן -> שבר החשיפה בעמודה שכותרתה מכילה word ("מניות" / "מט"): 0.8005.
    כותרת העמודה מגיעה עם תווי כיווניות (U+202B...)."""
    reader = csv.DictReader(io.StringIO(text.lstrip("﻿")))
    eq_col = next((c for c in reader.fieldnames or [] if word in c), None)
    out: dict[str, float] = {}
    if eq_col is None:
        return out
    for row in reader:
        num = fund_number_key(row.get(FUND_COL))
        raw = str(row.get(eq_col) or "").replace("%", "").replace(",", "").strip()
        if not num or not raw:
            continue
        try:
            out[num] = float(raw) / 100
        except ValueError:
            continue
    return out


def _get_raw(url: str, session: requests.Session | None = None) -> str:
    token = (os.environ.get(TOKEN_ENV) or "").strip()
    if not token:
        raise RuntimeError(f"{TOKEN_ENV} לא מוגדר")
    s = session or requests.Session()
    r = s.get(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.raw"}, timeout=60)
    r.raise_for_status()
    return r.text


def tase_stock_isins(data: dict) -> set[str]:
    return {str(r.get("isin") or "").strip().upper() for r in data.get("securities") or []
            if str(r.get("securityFullTypeCode") or "") == TASE_STOCK_TYPE and r.get("isin")}


def fetch_tase_stocks(session: requests.Session | None = None) -> set[str]:
    """ISIN של מניות בבורסת ת"א (revach: tase/securities.json) - לזיהוי מניה שגוף דיווח בגיליון
    קרנות (KAMADA IL0010941198). כשל -> ריק."""
    import json
    try:
        out = tase_stock_isins(json.loads(_get_raw(TASE_SECURITIES_URL, session)))
    except Exception as e:
        print(f"[tase_stocks] לא זמין: {e}")
        return set()
    print(f"[tase_stocks] {len(out)} מניות בת\"א")
    return out


def fetch_fund_exposure(session: requests.Session | None = None) -> dict[str, float]:
    """כשל (אין PAT / רשת) -> {} והחישוב ממשיך כמו קודם (מחקות/ממונפות בלבד)."""
    try:
        out = parse_fund_exposure(_get_raw(EXPOSURE_CONTENTS_URL, session))
    except Exception as e:
        print(f"[fund_exposure] לא זמין: {e}")
        return {}
    print(f"[fund_exposure] חשיפה למניות מדווחת ל-{len(out)} קרנות ישראליות")
    return out

