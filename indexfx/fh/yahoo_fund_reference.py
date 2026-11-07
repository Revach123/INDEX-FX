"""חשיפת מניות/אג"ח לקרנות "חוץ" דרך נתוני Yahoo Finance (מקור Morningstar):
שכבה מבוססת-תוכן אמיתי (לא ניחוש ממילות מפתח בשם המקוצר בדוח) - Yahoo
מצרף ל-quoteSummary של קרן פילוח Morningstar אמיתי של אחוזי stock/bond/
cash/preferred/convertible בפועל בתיק הקרן (funds_data.asset_classes
בספריית yfinance). בעיקר סוגר את הפער לקרנות UCITS אירופיות (LU/IE/...)
שלא נתפסות בשום שכבה אחרת - לא במאגרי ETF ב-revach (foreign_etf_reference),
לא ב-SEC N-PORT (sec_nport_reference, מוגבל ל-ISIN אמריקאי).

שכבה שנייה, זולה יותר: quoteType של Yahoo עצמו (מתוך אותה תוצאת חיפוש -
בלי קריאת רשת נוספת) - "EQUITY" הוא סיווג Yahoo למניה/חברת השקעה סגורה
הנסחרת כמניה רגילה (למשל Pershing Square USA - נבדק בפועל, ר' probe:
quoteType="EQUITY", בשונה מ"MUTUALFUND" לקרנות פתוחות). זה שונה מהותית
מ-marketSector של OpenFIGI (שגם קרנות אג"ח מקבלות "Equity" שם, ר' תיעוד
ב-main.py/sec_nport_reference.py) - quoteType מבחין נכון בין סוגי המכשיר
בפועל, לא סתם "הנייר עצמו נסחר כמו מניה".

אומת אמפירית (ר' scripts/probe/openfigi_fields_probe.py, סבב 4) מול 4
קרנות עם סיווג ידוע: 4/4 כיוון נכון, כולל קרנות עם חשיפה ממונפת/נגזרים
שבהן הסכום חורג מ-100%/שלילי (UBAM Global High Yield: bond=221%, cash=
-121%; PIMCO GIS Global IG Credit: bond=207%, cash=-107%) - stock=0
בשתיהן, כך שהיחס stock/(stock+bond) עדיין נותן כיוון נכון וחד-משמעי.
מתעלם בכוונה מ-cash/preferred/convertible/other באותו אופן - עקבי עם
שאר השכבות שגם הן שברי מניות/אג"ח בינאריים בלבד.

שיטה (בלי מפתח API, בלי תשלום):
  1. ISIN -> סימול Yahoo: query2.finance.yahoo.com/v1/finance/search
     (חינמי, בלי מפתח, בלי sesssion/cookie).
  2. סימול -> yfinance.Ticker(symbol).funds_data.asset_classes - הספרייה
     מנהלת בעצמה session+cookie+crumb מול Yahoo (קריאה ישירה ל-quoteSummary
     עם requests רגיל נכשלת ב-401 "Invalid Crumb" בלעדיה, ר' probe סבב 2).

לא כל ISIN נמצא ב-Yahoo (למשל קרנות הודיות מסוימות - נבדק בפועל, ר'
probe) - כשלון/העדר תוצאה לכל ISIN מדולג בשקט, לא מפיל את כל הריצה.

הרצה עצמאית לבדיקה: python -m scripts.funds_holdings.yahoo_fund_reference
"""
import time

import requests

YAHOO_SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"
YAHOO_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MASLULIM-pension-mapping/1.0)"}
YAHOO_DELAY = 0.4


def _search_quote(isin: str, session: requests.Session) -> dict | None:
    try:
        r = session.get(
            YAHOO_SEARCH_URL,
            params={"q": isin, "quotesCount": 3, "newsCount": 0},
            headers=YAHOO_HEADERS, timeout=15,
        )
        r.raise_for_status()
        quotes = (r.json() or {}).get("quotes", [])
    except (requests.RequestException, ValueError):
        return None
    for q in quotes:
        if q.get("symbol"):
            return q
    return None


def build_isin_fractions_via_yahoo(missing_isins: list[str]) -> dict[str, dict[str, float]]:
    """ISIN חסר -> {"equity":.., "bond":..} דרך Yahoo/Morningstar asset_classes.
    מיועד לרוץ רק על מה שעדיין לא מסווג אחרי כל שאר השכבות (ר' main.py) -
    יקר יחסית (2 קריאות רשת לכל ISIN)."""
    out: dict[str, dict[str, float]] = {}
    if not missing_isins:
        return out
    try:
        import yfinance as yf
    except ImportError:
        print("[yahoo_fund] yfinance לא מותקן - מדלג")
        return out

    session = requests.Session()
    n_symbol = 0
    n_classified = 0
    n_via_quote_type = 0
    for isin in missing_isins:
        quote = _search_quote(isin, session)
        time.sleep(YAHOO_DELAY)
        if not quote:
            continue
        n_symbol += 1
        symbol = quote["symbol"]

        # quoteType="EQUITY" (מניה/חברת השקעה סגורה הנסחרת כמניה) - סיווג
        # ודאי בלי קריאת רשת נוספת, ר' תיעוד למעלה. "ETF"/"MUTUALFUND"
        # ממשיכים לשכבת asset_classes (לא ודאי-מניות סתם מ-quoteType).
        if quote.get("quoteType") == "EQUITY":
            out[isin] = {"equity": 1.0, "bond": 0.0, "stock": True}
            n_classified += 1
            n_via_quote_type += 1
            continue

        try:
            asset_classes = yf.Ticker(symbol).funds_data.asset_classes
        except Exception:
            asset_classes = None
        time.sleep(YAHOO_DELAY)
        if not asset_classes:
            continue
        stock = asset_classes.get("stockPosition") or 0.0
        bond = asset_classes.get("bondPosition") or 0.0
        total = stock + bond
        if total <= 0:
            continue
        out[isin] = {"equity": stock / total, "bond": bond / total}
        n_classified += 1
    print(f"[yahoo_fund] {n_symbol}/{len(missing_isins)} ISIN נפתרו לסימול Yahoo, "
          f"{n_classified}/{len(missing_isins)} סווגו בהצלחה "
          f"({n_via_quote_type} מהן ישירות מ-quoteType=EQUITY, השאר מ-asset_classes)")
    return out


if __name__ == "__main__":
    test_isins = ["LU0569863243", "IE00BMD7Z621"]  # UBAM HY, NB Global Flex Credit - שתי קרנות אג"ח ידועות
    result = build_isin_fractions_via_yahoo(test_isins)
    import json
    print(json.dumps(result, indent=2))
