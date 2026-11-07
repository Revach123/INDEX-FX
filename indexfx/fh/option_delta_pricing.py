"""חשיפה כלכלית אמיתית לאופציות: לפי נוסחת בלק-שולס עם דלתא, כפי שהרגולטור
דורש (אומת ב-9.28.2026 דרך תיעוד פומבי של רשות שוק ההון - "בעבור אופציות,
היתרה מחושבת על-פי מודל בלק אנד שולס"), לא לפי "שיעור מסך נכסי ההשקעה"
המדווח (שהוא שווי הוגן/פרמיה, לא חשיפה כלכלית - אותו סוג בעיה שתוקן קודם
לחוזים עתידיים/סוואפים ב-derivatives_exposure.py).

אזהרת קירוב חשובה: בלק-שולס דורש תנודתיות גלומה (implied volatility) של
האופציה הספציפית - לא זמינה בשום מקור חינמי לרוחב ~70 השמות שמופיעים
כנכס-בסיס באופציות ב-MASLULIM. במקום זאת, מוערכת **תנודתיות ריאליזד**
היסטורית (60 ימי מסחר, מ-revach123/INDICES/data/prices/singles) - קירוב
סביר אך *לא* implied vol אמיתי (אין פרמיית-סיכון-תנודתיות, פחות רגיש
לציפיות שוק עתידיות). התוצאה קירוב לדלתא האמיתית, לא דלתא מדויקת.

ריבית חסרת סיכון: קבוע קבוע (לא נמשך חי) - השפעתה על דלתא קטנה בהרבה
מהשפעת ה-moneyness/תנודתיות, ולא הצדיק תלות-נתונים נוספת בשלב הזה.
"""
import csv
import io
import math
from datetime import date, datetime
from functools import lru_cache

import requests

RAW_BASE = "https://raw.githubusercontent.com/Revach123/INDICES/main"
SINGLE_PRICE_URL_TMPL = f"{RAW_BASE}/data/prices/singles/{{symbol}}.csv"
TIMEOUT = 20

REALIZED_VOL_WINDOW_DAYS = 60
RISK_FREE_RATE = 0.04  # קירוב קבוע - ר' אזהרה בראש הקובץ
TRADING_DAYS_PER_YEAR = 252

# מקלף "SPXW"/"NDXP" (root של אופציות שבועיות) לנכס-הבסיס האמיתי שלהן
# ("^GSPC"/"^NDX") - הרוט עצמו אינו טיקר נסחר. ר' option_ticker_parse.py.
UNDERLYING_ALIAS = {
    "SPXW": "^GSPC",
    "NDXP": "^NDX",
    "NKY": "^N225",
    # אופציות על חוזי E-mini (option_ticker_parse.FUTURES_OPTION) - לפי המדד שנבחר מהמימוש
    "ES_FO": "^GSPC", "NQ_FO": "^NDX", "RTY_FO": "^RUT", "YM_FO": "^DJI",
}


# נכסי בסיס שהם מדד עם סדרה משלו ב-INDICES (data/prices/<id>.csv, אותו פורמט כמו
# singles) - אופציות מדד מעו"ף (ר' option_ticker_parse.MAOF_ABBREV_TICKER)
INDEX_SERIES = {"TA35": "ta35", "TA125": "ta125", "TA90": "ta90"}
INDEX_PRICE_URL_TMPL = f"{RAW_BASE}/data/prices/{{series}}.csv"


def quote_scale(symbol: str | None) -> float:
    """מכפיל ממחיר הסדרה למטבע הפעילות: ניירות ת"א ב-Yahoo (".TA") מצוטטים
    באגורות (LUMI.TA = 6652 = ₪66.52; אומת: יחידות × מחיר / 100 = השווי ההוגן
    בדוח). מחיר המימוש בדוחות באותן אגורות, כך שהדלתא לא מושפעת - רק הנוציונל."""
    return 0.01 if symbol and str(symbol).upper().endswith(".TA") else 1.0


def _safe_filename(symbol: str) -> str:
    import re
    return re.sub(r"[^A-Za-z0-9._-]", "_", symbol)


@lru_cache(maxsize=128)
def _load_price_history(symbol: str) -> tuple[tuple[date, float], ...]:
    symbol = UNDERLYING_ALIAS.get(symbol, symbol)
    if symbol in INDEX_SERIES:
        url = INDEX_PRICE_URL_TMPL.format(series=INDEX_SERIES[symbol])
    else:
        url = SINGLE_PRICE_URL_TMPL.format(symbol=_safe_filename(symbol))
    # כישלון (אין סדרה לסימול / רשת) נשמר במטמון כסדרה ריקה - אחרת כל שורת
    # אופציה על אותו סימול מנסה שוב (lru_cache לא שומר חריגות)
    try:
        r = requests.get(url, timeout=TIMEOUT)
        r.raise_for_status()
    except requests.RequestException:
        # סימול שאין לו סדרה ב-INDICES (הרשימה שם מתעדכנת ידנית) - ישירות מ-Yahoo, אותו מקור
        # ואותן מוסכמות (ניירות ת"א באגורות), כדי שטיקר חדש בדוחות יתומחר בלי עדכון ידני
        return () if symbol in INDEX_SERIES else _yahoo_history(symbol)
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


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
YAHOO_PERIOD1 = int(datetime(2023, 6, 1).timestamp())  # כמו fetch_single_names.py ב-INDICES


def _yahoo_history(symbol: str) -> tuple[tuple[date, float], ...]:
    import time
    try:
        r = requests.get(YAHOO_CHART_URL.format(symbol=symbol), timeout=TIMEOUT,
                         params={"period1": YAHOO_PERIOD1, "period2": int(time.time()), "interval": "1d"},
                         headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128.0 Safari/537.36"})
        r.raise_for_status()
        res = ((r.json().get("chart") or {}).get("result") or [None])[0] or {}
    except (requests.RequestException, ValueError):
        return ()
    closes = (((res.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []
    out = [(datetime.utcfromtimestamp(t).date(), float(c)) for t, c in zip(res.get("timestamp") or [], closes)
           if c is not None]
    return tuple(sorted(out))


def price_as_of(symbol: str, as_of: date) -> float | None:
    try:
        bars = _load_price_history(symbol)
    except Exception:
        return None
    best = None
    for d, close in bars:
        if d > as_of:
            break
        best = close
    return best


def realized_vol_as_of(symbol: str, as_of: date, window: int = REALIZED_VOL_WINDOW_DAYS) -> float | None:
    """תנודתיות שנתית מ-log returns של window ימי המסחר האחרונים *לפני* as_of
    (לא כולל as_of עצמו ואחריו - נמנע look-ahead bias)."""
    try:
        bars = _load_price_history(symbol)
    except Exception:
        return None
    closes = [c for d, c in bars if d < as_of]
    if len(closes) < window + 1:
        return None
    closes = closes[-(window + 1):]
    log_returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0]
    if len(log_returns) < window // 2:
        return None
    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    return math.sqrt(variance * TRADING_DAYS_PER_YEAR)


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def black_scholes_delta(spot: float, strike: float, years_to_expiry: float,
                         vol: float, is_call: bool, r: float = RISK_FREE_RATE) -> float | None:
    """דלתא (0..1 ל-call, -1..0 ל-put). None אם הקלטים לא תקינים (פקיעה
    עברה, תנודתיות/מחיר לא חיוביים)."""
    if spot is None or strike is None or vol is None:
        return None
    if spot <= 0 or strike <= 0 or vol <= 0 or years_to_expiry <= 0:
        return None
    d1 = (math.log(spot / strike) + (r + 0.5 * vol * vol) * years_to_expiry) / (vol * math.sqrt(years_to_expiry))
    n_d1 = _norm_cdf(d1)
    return n_d1 if is_call else n_d1 - 1.0


def black_scholes_price(spot: float, strike: float, years_to_expiry: float,
                        vol: float, is_call: bool, r: float = RISK_FREE_RATE) -> float | None:
    """מחיר B&S למניה אחת (באותן יחידות כמו spot/strike)."""
    if spot is None or strike is None or vol is None:
        return None
    if spot <= 0 or strike <= 0 or vol <= 0 or years_to_expiry <= 0:
        return None
    sq = vol * math.sqrt(years_to_expiry)
    d1 = (math.log(spot / strike) + (r + 0.5 * vol * vol) * years_to_expiry) / sq
    d2 = d1 - sq
    disc = strike * math.exp(-r * years_to_expiry)
    if is_call:
        return spot * _norm_cdf(d1) - disc * _norm_cdf(d2)
    return disc * _norm_cdf(-d2) - spot * _norm_cdf(-d1)


def resolve_option_value(ticker: str | None, strike: float | None, expiry: date | None,
                         report_date: date | None, is_call: bool) -> tuple[float | None, float | None]:
    """(מחיר B&S למניה, מחיר המניה) - אותם קלטים כמו resolve_option_delta."""
    if not ticker or strike is None or expiry is None or report_date is None:
        return None, None
    years = (expiry - report_date).days / 365.25
    spot = price_as_of(ticker, report_date) if years > 0 else None
    vol = realized_vol_as_of(ticker, report_date) if spot is not None else None
    if vol is None:
        return None, None
    return black_scholes_price(spot, strike, years, vol, is_call), spot


def resolve_option_delta(ticker: str | None, strike: float | None, expiry: date | None,
                          report_date: date | None, is_call: bool) -> tuple[float | None, float | None]:
    """(delta, current_spot_price) - None,None אם חסר טיקר/נתון או שהחישוב
    לא אמין. קורא ל-caller ליפול חזרה לשיטת שווי-הוגן הקיימת."""
    if not ticker or strike is None or expiry is None or report_date is None:
        return None, None
    years = (expiry - report_date).days / 365.25
    if years <= 0:
        return None, None
    spot = price_as_of(ticker, report_date)
    if spot is None:
        return None, None
    # אופציית מדד: מימוש רחוק מהמדד = זיהוי שגוי של נכס הבסיס (ר' PATTERN_G) - לא מחשבים
    if ticker in INDEX_SERIES and not (0.5 <= strike / spot <= 2.0):
        return None, None
    vol = realized_vol_as_of(ticker, report_date)
    if vol is None:
        return None, None
    delta = black_scholes_delta(spot, strike, years, vol, is_call)
    return delta, spot
