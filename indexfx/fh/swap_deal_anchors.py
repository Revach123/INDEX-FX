"""רמת מדד לסוואפ בלי מחיר עסקה ובלי סדרת מדד: עוגן ממחירי העסקה בכל ארכיון הדוחות.

"שער נכס הבסיס במועד ההתקשרות בעסקה" הוא רמת המדד ביום העסקה - עובדה היסטורית שלא
משתנה בין דוחות. גוף שמדווח אותה ברבעון אחד ולא באחר (512065202_7867 ב-0325: IXCTR / IXYTR
/ S5TECH / MVSMHTR, מחיר עסקה 0; באותן עסקאות ב-0126: IXCTR 830.21 מ-19/09/2025) - הרמה
נלקחת מהעוגן של אותו גוף (אותו קנה מידה של ציטוט), הקרוב ביותר בזמן, ומגולגלת ליום
הדוח בתשואת תעודת הסל העוקבת (swap_index_pricing.proxy_return).

נקרא רק גיליון "לא סחיר נגזרים אחרים" מכל הקבצים (~2.5 דקות ל-838 קבצים), פעם אחת לריצה
ורק כשיש שורה שצריכה עוגן; התוצאה נשמרת ב-.cache לפי רשימת הקבצים וגודלם.
"""
from __future__ import annotations

import json
import statistics
from datetime import date
from pathlib import Path

from .canon import canon
from .excel_io import read_sheet_rows
from .sheet_source import _norm_sheet

REPORTS_ROOT = Path("reports")
CACHE = Path(".cache") / "swap_deal_anchors.json"
SWAP_SHEET = "לא סחיר נגזרים אחרים"
TICKER_COL = "טיקר"
PRICE_COL = "שער נכס הבסיס במועד ההתקשרות בעסקה"
DATE_COL = "מועד ההתקשרות בעסקה"

_ANCHORS: dict[str, list[tuple[date, float]]] | None = None


def _files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file() and p.suffix.lower() == ".xlsx")


def _build(root: Path) -> dict[str, list[tuple[str, float]]]:
    from .swap_index_pricing import normalize_ticker, parse_deal_date
    out: dict[str, set] = {}
    for p in _files(root):
        legal_id = p.name.split("_", 1)[0]
        try:
            sheets = read_sheet_rows(p, lambda name: canon(name) == SWAP_SHEET)
        except Exception:
            continue
        for data in sheets.values():
            try:
                status, rows = _norm_sheet(data, legal_id)
            except Exception:
                continue
            if status != "מידע":
                continue
            for r in rows:
                t, price, d = normalize_ticker(r.get(TICKER_COL)), r.get(PRICE_COL), parse_deal_date(r.get(DATE_COL))
                if t and isinstance(price, (int, float)) and price > 0 and d:
                    out.setdefault(f"{legal_id}|{t}", set()).add((d.isoformat(), float(price)))
    return {k: sorted(v) for k, v in out.items()}


def _load() -> dict[str, list[tuple[date, float]]]:
    global _ANCHORS
    if _ANCHORS is None:
        root = REPORTS_ROOT
        sig = [[p.name, p.stat().st_size] for p in _files(root)] if root.exists() else []
        raw = None
        try:
            cached = json.loads(CACHE.read_text(encoding="utf-8"))
            if cached.get("sig") == sig:
                raw = cached["anchors"]
        except (OSError, ValueError, KeyError):
            pass
        if raw is None:
            raw = _build(root) if sig else {}
            try:
                CACHE.parent.mkdir(parents=True, exist_ok=True)
                CACHE.write_text(json.dumps({"sig": sig, "anchors": raw}, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
            print(f"[swap_anchors] {len(raw)} צמדי גוף/טיקר עם מחיר עסקה מ-{len(sig)} קבצים")
        _ANCHORS = {k: [(date.fromisoformat(d), p) for d, p in v] for k, v in raw.items()}
    return _ANCHORS


def _etf_ratio(ticker: str, d0: date, d1: date) -> float | None:
    """מחיר תעודת הסל העוקבת ב-d1 / ב-d0 - בכל סדר תאריכים (עוגן מדוח מאוחר מגולגל אחורה)."""
    from .option_delta_pricing import price_as_of as etf_price_as_of
    from .swap_index_pricing import PROXY_ETF, price_as_of
    etf = PROXY_ETF.get(ticker)
    for proxy in (etf if isinstance(etf, tuple) else (etf,)) if etf else ():
        get = (lambda d, x=proxy[6:]: price_as_of(x, d)) if proxy.startswith("index:") else \
              (lambda d, x=proxy: etf_price_as_of(x, d))
        p0, p1 = get(d0), get(d1)
        if p0 and p1:
            return p1 / p0
    return None


def anchored_price(legal_id: str, raw_ticker, deal_date: date | None, report_date: date | None) -> float | None:
    """רמת המדד ליום הדוח מעוגני אותו גוף (אותו קנה מידה של ציטוט) - גם מדוח מאוחר יותר
    (512065202 NDWUIT: מחיר עסקה רק מ-05/2026, לדוחות 2025) - כל עוגן × יחס מחירי תעודת הסל
    העוקבת בין יומו ליום הדוח. None אם אין."""
    from .swap_index_pricing import normalize_ticker
    t = normalize_ticker(raw_ticker)
    if not t or not report_date:
        return None
    # כל העוגנים מגולגלים ליום הדוח, והחציון - עמיד לעוגן שגוי (512065202 NDWUIT: 3.3059 - שער
    # הדולר בעמודת מחיר העסקה - לצד 1,195.6 באותו יום)
    levels = []
    for d, p in _load().get(f"{legal_id}|{t}", []):
        ratio = _etf_ratio(t, d, report_date)
        if ratio:
            levels.append(p * ratio)
    return statistics.median(levels) if levels else None
