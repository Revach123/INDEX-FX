"""מחיר מדד עדכני (נכון לתאריך הדוח, לא לתאריך פתיחת העסקה) לעסקאות סוואפ על
מדדי מניות, דרך revach123/INDICES (ריפו נפרד שמושך מדי יום מחירי מדדים
מ-Yahoo Finance - ר' README שם). נמצא בבדיקה בפועל (לא הנחה): "שער נכס הבסיס
במועד ההתקשרות בעסקה" בגיליון "לא סחיר נגזרים אחרים" הוא, כפי ששמו מרמז,
מחיר *בפתיחת* העסקה - לחשיפה נכונה ליום הדוח צריך את מחיר המדד *נכון לאותו
יום*, לא את המחיר ההיסטורי הזה.

מקור הטיקר: עמודת "טיקר" באותו גיליון (סוג הנכס=="מניות לרבות מדדי מניות").
המיפוי טיקר-סוואפ -> index_id ב-INDICES (data/swap_ticker_map.csv) נבנה
מסריקה מלאה של הארכיון בפועל (ר' commit ב-INDICES) - לא כל טיקר ממופה:
חלק (בעיקר סלים קנייניים של גופ בנקאי בודד - Goldman/JPM/Citi/Merrill,
עם קידומת GS*/JP*/CGAS*/MLBL*) אין להם מקור נתונים ציבורי בעליל, ומסומנים
במפורש ככאלה (index_id ריק + סיבה) - לא "עדיין לא נבדק".

כשל רשת/מיפוי חסר -> None (לא זריקת חריגה) - הקוד הקורא נופל בחזרה
לשיטת "שער נכס הבסיס במועד ההתקשרות" הקיימת.

אזהרה קריטית (נמצאה בבדיקה בפועל - MAE הורע, לא רק "לא השתפר", אחרי מעבר
ל-ETF-ים): index_id ב-swap_ticker_map.csv (INDICES) חייב להיות טיקר ברמת
מדד (Yahoo instrumentType=="INDEX"), לא מחיר יחידת ETF - גם אם ה-ETF
"מצטבר"/Acc ועוקב TR נאמנה. הקוד כאן מציב את המחיר ישירות בנוסחת
units×price שמניחה קנה-מידה זהה לרמת המדד עצמו (למשל Nasdaq-100 ~25,000
נקודות) - מחיר יחידת ETF (למשל ~1,755$) הוא בקנה-מידה שרירותי לגמרי, לא
פרופורציונלי לרמת המדד, ומייצר חשיפה שגויה בסדרי גודל בלי שה-LEVERAGE_CAP
ב-derivatives_exposure.py בהכרח תופס זאת. ר' README ב-INDICES לפירוט.
"""
import csv
import io
import re
from datetime import date, datetime
from functools import lru_cache

import requests

RAW_BASE = "https://raw.githubusercontent.com/Revach123/INDICES/main"
TICKER_MAP_URL = f"{RAW_BASE}/data/swap_ticker_map.csv"
PRICE_URL_TMPL = f"{RAW_BASE}/data/prices/{{index_id}}.csv"
TIMEOUT = 20

_SUFFIX_INDEX_EQUITY = re.compile(r"\s+(INDEX|EQUITY)$")
_SUFFIX_TRAILING_NUMBER = re.compile(r"\s+[0-9][0-9.,]*$")


def normalize_ticker(raw: str | None) -> str | None:
    """אותה נרמול שהופעל בזמן בניית swap_ticker_map.csv - חובה להיות זהה,
    אחרת המפתח לא יתאים לטבלת המיפוי."""
    if not raw:
        return None
    t = str(raw).strip().upper().replace("_X000D_", " ").replace("\n", " ")
    t = re.sub(r"\s+", " ", t).strip()
    t = _SUFFIX_INDEX_EQUITY.sub("", t)
    t = _SUFFIX_TRAILING_NUMBER.sub("", t)
    return t or None


@lru_cache(maxsize=1)
def _load_ticker_map() -> dict[str, str]:
    r = requests.get(TICKER_MAP_URL, timeout=TIMEOUT)
    r.raise_for_status()
    out: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO(r.text)):
        index_id = (row.get("index_id") or "").strip()
        ticker = (row.get("swap_ticker") or "").strip().upper()
        if ticker and index_id:
            out[ticker] = index_id
    return out


@lru_cache(maxsize=64)
def _load_index_prices(index_id: str) -> tuple[tuple[date, float], ...]:
    r = requests.get(PRICE_URL_TMPL.format(index_id=index_id), timeout=TIMEOUT)
    r.raise_for_status()
    out = []
    for row in csv.DictReader(io.StringIO(r.text)):
        try:
            d = datetime.strptime(row["date"], "%Y-%m-%d").date()
            c = float(row["close"])
        except (ValueError, KeyError, TypeError):
            continue
        out.append((d, c))
    out.sort()
    return tuple(out)


YAHOO_PREFIX = "yahoo:"


def price_as_of(index_id: str, as_of: date) -> float | None:
    """מחיר הסגירה האחרון הידוע עד (וכולל) as_of. None אם אין מחיר במאגר
    לפני as_of, או שאין בכלל היסטוריה למדד הזה (רשת נכשלה/index_id שגוי).
    "yahoo:<סימול>" - מדד בלי סדרה ב-INDICES, מ-Yahoo (כמו בתמחור האופציות)."""
    if index_id.startswith(YAHOO_PREFIX):
        from .option_delta_pricing import price_as_of as single_price_as_of
        return single_price_as_of(index_id[len(YAHOO_PREFIX):], as_of)
    try:
        bars = _load_index_prices(index_id)
    except Exception:
        return None
    best = None
    for d, close in bars:
        if d > as_of:
            break
        best = close
    return best


# מדד בלי סדרה משלו ב-INDICES -> תעודת הסל שעוקבת אחריו (רק *יחס* התשואה שלה בין יום
# העסקה ליום הדוח משמש - לא רמת המחיר שלה, ר' האזהרה בראש הקובץ). נתוני ייחוס: מה
# כל קרן עוקבת (IXC/XLC, IXY/XLY, IXT/XLK - Select Sector SPDR; MVIS US Listed
# Semiconductor 25 / SMH; S&P 500 Software & Services ~ IGV, קירוב).
# ערך "index:<id>" = סדרה ב-INDICES (data/prices/<id>.csv, למשל topix = 1306.T); רשימה =
# הראשון שיש לו מחירים. MSCI World Momentum ~ IWMO.L (iShares Edge MSCI World Momentum,
# MTUM כגיבוי); MSCI World IT ~ IXN; S&P 500 IT ~ XLK; TOPIX TR ~ topix; MSCI EM / ACWI ~
# סדרות הפרוקסי ב-INDICES.
PROXY_ETF = {
    "IXCTR": "XLC", "IXC": "XLC", "IXYTR": "XLY", "IXY": "XLY", "IXTTR": "XLK", "IXT": "XLK",
    "MVSMHTR": "SMH", "MVSMH": "SMH", "S5SFTW": "IGV",
    "S5TECH": "XLK", "S5INFT": "XLK", "NDWUIT": "IXN", "M1WOMOM": ("IWMO.L", "MTUM"),
    "TPXDDVD": "index:topix", "TPX": "index:topix",
    "NDUEEGF": "index:msci_em_proxy", "M1EF": "index:msci_em_proxy",
    "NDUEACWF": "index:acwi_proxy", "M1WD": "index:acwi_proxy",
    # STOXX Europe 600 (GR) ~ EXSA.DE; STOXX Europe 600 Banks (GR) ~ EXV1.DE (iShares, Xetra);
    # S&P/ASX 200 TR ~ asx200; MVIS US Listed Pharmaceutical 25 TR ~ PPH
    "SXXGR": "EXSA.DE", "SXXR": "EXSA.DE", "SXXP": "EXSA.DE", "SX7GR": "EXV1.DE", "SX7R": "EXV1.DE",
    "SX7P": "EXV1.DE", "AS51T": "index:asx200", "AS51": "index:asx200", "MVPPHTR": "PPH",
}
def has_price_source(raw_ticker: str | None) -> bool:
    """לטיקר יש מקור מחיר ליום הדוח: סדרה ב-INDICES או תעודת סל עוקבת."""
    key = normalize_ticker(raw_ticker)
    if not key:
        return False
    try:
        tmap = _load_ticker_map()
    except Exception:
        tmap = {}
    return bool(tmap.get(key) or tmap.get(key.replace("-", "")) or PROXY_ETF.get(key))
_EXCEL_EPOCH = date(1899, 12, 30)


def parse_deal_date(v) -> date | None:
    """"מועד ההתקשרות בעסקה" כפי שמופיע בדוחות: date / datetime, "29/09/2025", או
    מספר סידורי של Excel ("46297.0" = 2026-10-02 לפי ספירת Excel)."""
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    try:
        n = float(s)
    except ValueError:
        return None
    if 30000 <= n <= 60000:
        from datetime import timedelta
        return _EXCEL_EPOCH + timedelta(days=int(n))
    return None


def proxy_return(raw_ticker: str | None, deal_date: date | None, report_date: date | None) -> float | None:
    """תשואת תעודת הסל העוקבת אחרי המדד מיום העסקה ליום הדוח (מחיר[דוח] / מחיר[עסקה]).
    None אם אין פרוקסי / תאריך / מחיר."""
    key = normalize_ticker(raw_ticker)
    etf = PROXY_ETF.get(key or "")
    if not etf or not deal_date or not report_date:
        return None
    if deal_date > report_date and deal_date.day <= 12:
        # יום/חודש הפוכים ב-Excel ("10/02/2026" = 10 בפברואר נקרא 2 באוקטובר - 46297)
        try:
            deal_date = date(deal_date.year, deal_date.day, deal_date.month)
        except ValueError:
            return None
    if deal_date > report_date:
        return None
    from .option_delta_pricing import price_as_of as etf_price_as_of
    for proxy in (etf if isinstance(etf, tuple) else (etf,)):
        if proxy.startswith("index:"):
            p0, p1 = price_as_of(proxy[6:], deal_date), price_as_of(proxy[6:], report_date)
        else:
            p0, p1 = etf_price_as_of(proxy, deal_date), etf_price_as_of(proxy, report_date)
        if p0 and p1:
            return p1 / p0
    return None


def resolve_current_price(raw_ticker: str | None, report_date: date | None) -> tuple[float | None, str | None]:
    """(מחיר מדד עדכני נכון ל-report_date, index_id שנמצא) - (None, None) אם
    הטיקר לא ממופה, אין תאריך דוח, או שכשלה גישת הרשת. לא זורק."""
    if not report_date:
        return None, None
    key = normalize_ticker(raw_ticker)
    if not key:
        return None, None
    try:
        tmap = _load_ticker_map()
        index_id = tmap.get(key) or tmap.get(key.replace("-", ""))  # "TA-125 INDEX" = TA125
    except Exception:
        return None, None
    if not index_id:
        return None, None
    return price_as_of(index_id, report_date), index_id
