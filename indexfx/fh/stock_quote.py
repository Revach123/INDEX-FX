"""טיקר בלומברג של מניה בודדת ("2330 TT", "V US", "TT2330") -> סימול Yahoo, מטבע הציטוט ומקדם.

"שער נכס הבסיס במועד ההתקשרות" של סוואפ על מניה נקוב במטבע הבורסה של המניה - לא בהכרח במטבע
הרגל (512065202_877 ב-0126: TSMC, רגל "USD" של 107.3 מיליון = 61,688.8 מניות × 1,740 - דולר
טייוואני; בשער הדולר 8.2% מהמסלול במקום 0.26%). קוד הבורסה (מוסכמת בלומברג) קובע את המטבע,
ודרכו גם מחיר המניה ליום הדוח מ-Yahoo.

בורסת ת"א (IT/IL) לא כאן: שם הרגליים בשקלים והמחיר מדווח לעתים באגורות ולעתים בשקלים.
"""
from __future__ import annotations

import re
from typing import NamedTuple

# קוד בורסה בבלומברג -> (מטבע הציטוט, סיומת Yahoo, מקדם ממחיר מצוטט למטבע)
_EXCHANGES: dict[str, tuple[str, str, float]] = {
    **{c: ("USD", "", 1.0) for c in ("US", "UW", "UN", "UQ", "UR", "UP", "UA", "UF", "UV")},
    "TT": ("TWD", ".TW", 1.0),
    "JT": ("JPY", ".T", 1.0), "JP": ("JPY", ".T", 1.0),
    "HK": ("HKD", ".HK", 1.0),
    "KS": ("KRW", ".KS", 1.0),
    "LN": ("GBP", ".L", 0.01),       # מצוטט בפני (GBp) - גם בבלומברג וגם ב-Yahoo
    "GY": ("EUR", ".DE", 1.0), "GR": ("EUR", ".DE", 1.0),
    "FP": ("EUR", ".PA", 1.0), "NA": ("EUR", ".AS", 1.0),
    "IM": ("EUR", ".MI", 1.0), "SM": ("EUR", ".MC", 1.0),
    "SW": ("CHF", ".SW", 1.0), "SE": ("CHF", ".SW", 1.0),
    "CN": ("CAD", ".TO", 1.0), "CT": ("CAD", ".TO", 1.0),
    "AU": ("AUD", ".AX", 1.0), "AT": ("AUD", ".AX", 1.0),
}
_SUFFIX_FORM = re.compile(r"^([A-Z0-9][A-Z0-9./-]{0,11})\s+([A-Z]{2})(?:\s+EQUITY)?$")
# קוד בורסה כקידומת לקוד מספרי ("TT2330" ב-512065202 מ-0126)
_PREFIX_FORM = re.compile(r"^(TT|JT|JP|HK|KS)(\d{3,6})$")


class StockQuote(NamedTuple):
    symbol: str      # סימול Yahoo
    currency: str
    factor: float    # מחיר מצוטט × factor = מחיר במטבע


def stock_quote(raw_ticker) -> StockQuote | None:
    t = re.sub(r"\s+", " ", str(raw_ticker or "").strip().upper())
    m = _SUFFIX_FORM.match(t)
    code, exch = (m.group(1), m.group(2)) if m else (None, None)
    if not m:
        m = _PREFIX_FORM.match(t)
        if m:
            exch, code = m.group(1), m.group(2)
    if exch not in _EXCHANGES:
        return None
    ccy, suffix, factor = _EXCHANGES[exch]
    if exch == "HK" and code.isdigit():
        code = code.zfill(4)
    return StockQuote(code.replace("/", "-") + suffix, ccy, factor)
