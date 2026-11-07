"""סיווג מניות/אג"ח מדויק לקרנות "חוץ" אמריקאיות (ISIN מתחיל ב-US) שלא
נמצאו בשום שכבה קיימת (לא אוניברסיטת ETF אירופית, לא ETF SEC הקבוע
(data/ETF/SEC/etf_exposure.json ב-revach), לא סיווג-לפי-שם-קרן) - שכבה
אחרונה, יקרה יותר (קריאות רשת חיות ל-SEC EDGAR), ולכן מופעלת רק על
ה-ISIN-ים שעדיין חסרים אחרי כל שאר השכבות (ר' main.py).

שיטה (בלי מפתח API, בלי תשלום):
  1. ISIN -> טיקר: OpenFIGI (https://api.openfigi.com/v3/mapping),
     idType=ID_ISIN. ציבורי, חינמי, בלי מפתח (מוגבל ~25 בקשות/דקה -
     מספיק בהרבה לכמות הקרנות החסרות בפועל, ר' missing_foreign_funds.py).
  2. טיקר -> (cik, seriesId): data.sec.gov/files/company_tickers_mf.json -
     קובץ SEC רשמי, כל קרנות ה-Investment Company (מנוהלות/ETF) הרשומות
     כ-series/class. לא כולל UIT (SPY/QQQ מהדור הישן וכו') - אלה כבר
     מכוסות ידנית ב-KNOWN_MAJOR_EQUITY_ETFS.
  3. (cik, seriesId) -> primary_doc.xml של ה-N-PORT האחרון (data.sec.gov/
     submissions/CIK##########.json למציאת ההגשה, אח"כ
     sec.gov/Archives/edgar/data/{cik}/{accn}/primary_doc.xml).
  4. פירסום ה-XML: סכום pctVal לפי assetCat פיזי בלבד (EC/EP=מניות,
     DBT=אג"ח) - **לא כולל חשיפה סינתטית דרך נגזרים** (מגבלה מכוונת: פירוק
     נגזרים לפי סוג/כיוון מתוך ה-XML הבודד דורש פענוח מורכב וטרם אומת
     מול XML אמיתי - ר' derivatives_exposure.py לחישוב מלא בתוך הדוחות
     הפנסיוניים עצמם). מספיק לרוב הקרנות שנותרו לא מזוהות (קרנות אג"ח/
     מניות "רגילות" בעלות רכיב פיזי דומיננטי - לא קרנות ממונפות/הפוכות,
     שכבר מכוסות ב-eqTotalPct/bondTotalPct המדויק של data/ETF/SEC).

הרצה עצמאית לבדיקה: python -m scripts.funds_holdings.sec_nport_reference
"""
import gzip
import json
import ssl
import time
import xml.etree.ElementTree as ET
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import requests

CONTACT_EMAIL = "azzlevy@gmail.com"
SEC_USER_AGENT = f"MASLULIM Pension Fund Mapping {CONTACT_EMAIL}"

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
OPENFIGI_BATCH = 10
OPENFIGI_DELAY = 2.6  # ~25 בקשות/דקה בלי מפתח API

MF_TICKERS_URL = "https://www.sec.gov/files/company_tickers_mf.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
FILING_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accn_nodash}/primary_doc.xml"

SEC_RATE_DELAY = 0.15
SEC_MAX_RETRIES = 4
SEC_TIMEOUT = 30

EQUITY_ASSET_CATS = {"EC", "EP"}
BOND_ASSET_CATS = {"DBT"}

_SSL_CTX = ssl._create_unverified_context()


def _sec_get(url: str, as_json: bool = False):
    headers = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
    last_err = None
    for attempt in range(SEC_MAX_RETRIES):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=SEC_TIMEOUT, context=_SSL_CTX) as r:
                raw = r.read()
                if r.info().get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
            time.sleep(SEC_RATE_DELAY)
            return json.loads(raw) if as_json else raw
        except HTTPError as e:
            last_err = e
            if e.code == 404:
                return None
            time.sleep(1.5 * (attempt + 1))
        except (URLError, TimeoutError) as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    print(f"[sec_nport] נכשל אחרי {SEC_MAX_RETRIES} ניסיונות: {url} ({last_err})")
    return None


def _openfigi_lookup(isins: list[str], session: requests.Session | None = None) -> dict[str, dict]:
    """ISIN -> רשומת הנתונים הראשונה שהחזיר OpenFIGI (dict גולמי). משותף לכל
    הפונקציות שמבוססות על OpenFIGI (טיקר, שם מלא) כדי לא לכפול את לוגיקת
    ה-batching/retry. מדלג בשקט על ISIN-ים שלא נמצאו (לא כל ISIN ציבורי
    ממופה שם)."""
    s = session or requests.Session()
    out: dict[str, dict] = {}
    for i in range(0, len(isins), OPENFIGI_BATCH):
        batch = isins[i : i + OPENFIGI_BATCH]
        jobs = [{"idType": "ID_ISIN", "idValue": isin} for isin in batch]
        try:
            r = s.post(OPENFIGI_URL, json=jobs, timeout=30,
                        headers={"Content-Type": "application/json"})
            r.raise_for_status()
            results = r.json()
        except (requests.RequestException, ValueError) as e:
            print(f"[sec_nport] OpenFIGI נכשל על אצווה ({len(batch)} ISIN): {e}")
            time.sleep(OPENFIGI_DELAY)
            continue
        for isin, res in zip(batch, results):
            data = res.get("data") if isinstance(res, dict) else None
            if data:
                out[isin] = data[0]
        time.sleep(OPENFIGI_DELAY)
    return out


def resolve_index_tickers(tickers: list[str], session: requests.Session | None = None) -> dict[str, str]:
    """טיקר מדד בלומברג (למשל S5SFTW, RIYCCTR) -> שם המדד המלא, דרך OpenFIGI
    (marketSecDes=Index). משמש את index_exposure לזיהוי המדד שמאחורי סוואפ.
    טיקר שלא נמצא (סל מותאם של בנק) - לא מוחזר."""
    s = session or requests.Session()
    out: dict[str, str] = {}
    tickers = [t for t in dict.fromkeys(tickers) if t]
    for i in range(0, len(tickers), OPENFIGI_BATCH):
        batch = tickers[i : i + OPENFIGI_BATCH]
        jobs = [{"idType": "TICKER", "idValue": t, "marketSecDes": "Index"} for t in batch]
        try:
            r = s.post(OPENFIGI_URL, json=jobs, timeout=30, headers={"Content-Type": "application/json"})
            r.raise_for_status()
            results = r.json()
        except (requests.RequestException, ValueError) as e:
            print(f"[sec_nport] OpenFIGI (מדדים) נכשל על אצווה ({len(batch)}): {e}")
            time.sleep(OPENFIGI_DELAY)
            continue
        for t, res in zip(batch, results):
            data = res.get("data") if isinstance(res, dict) else None
            if data and data[0].get("name"):
                out[t] = data[0]["name"].strip()
        time.sleep(OPENFIGI_DELAY)
    return out


def resolve_isin_to_ticker(isins: list[str], session: requests.Session | None = None) -> dict[str, str]:
    """ISIN (US בלבד) -> טיקר, דרך OpenFIGI."""
    us_isins = [i for i in isins if i and i.startswith("US")]
    figi = _openfigi_lookup(us_isins, session)
    return {isin: d["ticker"].strip().upper() for isin, d in figi.items() if d.get("ticker")}


def resolve_isin_to_name(isins: list[str], session: requests.Session | None = None) -> dict[str, str]:
    """ISIN (כל מדינה) -> שם מלא לא-קצוץ, דרך OpenFIGI - מיועד לפתור את
    בעיית הקיצוץ בשם הנייר כפי שהוא מדווח בדוח הפנסיוני עצמו (ר'
    classify_from_report_names/classify_via_full_names ב-
    foreign_etf_reference.py): קרן זרה רבות ניתנות לזיהוי ודאי מהשם המלא/
    הרשמי אבל לא מהשם המקוצר-אוטומטית שמופיע בדוח (למשל "POLAR CAPITAL-GLB
    TECH" בלי "-nology"). לא מוגבל ל-US - OpenFIGI מכסה גם קרנות/ETF
    אירופיות/אסייתיות רבות (לא בהכרח כל קרן מנוהלת לא-נסחרת)."""
    figi = _openfigi_lookup([i for i in isins if i], session)
    return {isin: d["name"].strip() for isin, d in figi.items() if d.get("name")}


def fetch_mf_ticker_map() -> dict[str, tuple[int, str]]:
    """טיקר (upper) -> (cik, seriesId), מתוך קובץ SEC הרשמי של כל קרנות
    ה-Investment Company הרשומות (מנוהלות/ETF, לא UIT)."""
    data = _sec_get(MF_TICKERS_URL, as_json=True)
    if not data:
        return {}
    fields = data.get("fields", [])
    idx = {f: fields.index(f) for f in ("cik", "seriesId", "symbol") if f in fields}
    if len(idx) < 3:
        return {}
    out: dict[str, tuple[int, str]] = {}
    for row in data.get("data", []):
        try:
            cik = int(row[idx["cik"]])
            series_id = row[idx["seriesId"]]
            symbol = str(row[idx["symbol"]]).strip().upper()
        except (IndexError, TypeError, ValueError):
            continue
        if symbol and symbol not in out:
            out[symbol] = (cik, series_id)
    return out


def _find_latest_nport_xml(cik: int, series_id: str) -> bytes | None:
    cik10 = str(cik).zfill(10)
    sub = _sec_get(SUBMISSIONS_URL.format(cik10=cik10), as_json=True)
    if not sub:
        return None
    recent = sub.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accns = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])
    for form, accn, doc in zip(forms, accns, docs):
        if form not in ("NPORT-P", "NPORT-P/A"):
            continue
        accn_nodash = accn.replace("-", "")
        xml = _sec_get(FILING_URL.format(cik=cik, accn_nodash=accn_nodash))
        if xml is None:
            continue
        if series_id.encode() in xml:
            return xml
    return None


def _localname(tag: str) -> str:
    return tag.split("}")[-1]


def _parse_physical_pct(xml_bytes: bytes) -> tuple[float, float] | None:
    """sum(pctVal) לפי assetCat פיזי בלבד (EC/EP->equity, DBT->bond),
    רק לשורות invstOrSec שאינן נגזר (בלי derivativeInfo)."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    equity_pct = 0.0
    bond_pct = 0.0
    for el in root.iter():
        if _localname(el.tag) != "invstOrSec":
            continue
        asset_cat = None
        pct_val = 0.0
        is_deriv = False
        for child in el.iter():
            cln = _localname(child.tag)
            if cln == "assetCat" and child.text:
                asset_cat = child.text.strip()
            elif cln == "pctVal" and child.text:
                try:
                    pct_val = float(child.text)
                except ValueError:
                    pct_val = 0.0
            elif cln == "derivativeInfo":
                is_deriv = True
        if is_deriv:
            continue
        if asset_cat in EQUITY_ASSET_CATS:
            equity_pct += pct_val
        elif asset_cat in BOND_ASSET_CATS:
            bond_pct += pct_val
    return equity_pct, bond_pct


def build_isin_fractions_via_nport(missing_isins: list[str]) -> dict[str, dict[str, float]]:
    """שכבה אחרונה ויקרה: ISIN חסר (US בלבד) -> {"equity":.., "bond":..},
    דרך OpenFIGI + N-PORT חי. רצה רק על ISIN-ים שעדיין לא מסווגים אחרי כל
    שאר השכבות ב-main.py (ר' תיעוד בראש הקובץ). כשלונות רשת/פענוח מדולגים
    בשקט לכל קרן בנפרד - לא מפילים את כל הריצה."""
    out: dict[str, dict[str, float]] = {}
    us_missing = [i for i in missing_isins if i and i.startswith("US")]
    if not us_missing:
        return out

    print(f"[sec_nport] {len(us_missing)} ISIN אמריקאים חסרים - מנסה OpenFIGI+N-PORT חי")
    isin_to_ticker = resolve_isin_to_ticker(us_missing)
    print(f"[sec_nport] {len(isin_to_ticker)}/{len(us_missing)} נפתרו לטיקר דרך OpenFIGI")
    if not isin_to_ticker:
        return out

    ticker_map = fetch_mf_ticker_map()
    print(f"[sec_nport] {len(ticker_map)} טיקרים במאגר SEC company_tickers_mf")

    n_found = 0
    for isin, ticker in isin_to_ticker.items():
        cik_series = ticker_map.get(ticker)
        if cik_series is None:
            continue
        cik, series_id = cik_series
        xml = _find_latest_nport_xml(cik, series_id)
        if xml is None:
            continue
        parsed = _parse_physical_pct(xml)
        if parsed is None:
            continue
        equity_pct, bond_pct = parsed
        if equity_pct <= 0 and bond_pct <= 0:
            continue
        out[isin] = {"equity": equity_pct / 100, "bond": bond_pct / 100}
        n_found += 1
    print(f"[sec_nport] {n_found}/{len(us_missing)} ISIN סווגו בהצלחה דרך N-PORT חי")
    return out


if __name__ == "__main__":
    test_isins = ["US78462F1030"]  # SPY - UIT, צפוי לא להימצא ב-company_tickers_mf
    result = build_isin_fractions_via_nport(test_isins)
    print(json.dumps(result, indent=2))
