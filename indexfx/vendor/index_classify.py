"""טבלת זיהוי מדדים (העתק מ-MASLULIM/scripts/funds_holdings/index_exposure.py שורות 46-337, ללא שינוי לוגי)."""
from __future__ import annotations

import re
from collections import defaultdict


# ── 1. קודים (טיקר בלומברג / שורש חוזה) -> טקסט שמסווג בהמשך ────────────────
# רק כשאין שם מלא (OpenFIGI בריצה, ר' resolve_names). מפרטי GICS של S&P
# (S5 + קבוצת תעשייה), Select Sector (IXx), MSCI, STOXX, Russell ושורשי חוזים.
_CODES = {
    # S&P 500 GICS - מגזר / קבוצת תעשייה
    "S5INFT": "S&P 500 INFORMATION TECHNOLOGY", "S5SFTW": "S&P 500 SOFTWARE & SERVICES",
    "S5TECH": "S&P 500 TECHNOLOGY HARDWARE", "S5SECO": "S&P 500 SEMICONDUCTORS",
    "S5COND": "S&P 500 CONSUMER DISCRETIONARY", "S5CONS": "S&P 500 CONSUMER STAPLES",
    "S5TELS": "S&P 500 COMMUNICATION SERVICES", "S5MEDA": "S&P 500 MEDIA",
    "S5HLTH": "S&P 500 HEALTH CARE", "S5FINL": "S&P 500 FINANCIALS", "S5BANKX": "S&P 500 BANKS",
    "S5INSU": "S&P 500 INSURANCE", "S5INDU": "S&P 500 INDUSTRIALS", "S5ENRS": "S&P 500 ENERGY",
    "S5UTIL": "S&P 500 UTILITIES", "S5MATR": "S&P 500 MATERIALS", "S5RLST": "S&P 500 REAL ESTATE",
    "S5RETL": "S&P 500 CONSUMER DISCRETIONARY RETAILING",
    # Select Sector (CME / S&P) - IXx, IXxTR
    "IXT": "TECHNOLOGY SELECT SECTOR", "IXC": "COMMUNICATION SERVICES SELECT SECTOR",
    "IXY": "CONSUMER DISCRETIONARY SELECT SECTOR", "IXR": "CONSUMER STAPLES SELECT SECTOR",
    "IXV": "HEALTH CARE SELECT SECTOR", "IXM": "FINANCIAL SELECT SECTOR", "IXI": "INDUSTRIAL SELECT SECTOR",
    "IXE": "ENERGY SELECT SECTOR", "IXU": "UTILITIES SELECT SECTOR", "IXB": "MATERIALS SELECT SECTOR",
    # מדדים רחבים
    "SPTR": "S&P 500", "SPXTR": "S&P 500", "SPX": "S&P 500", "SPXEWTR": "S&P 500 EQUAL WEIGHT",
    "XNDX": "NASDAQ 100", "NDX": "NASDAQ 100", "RTY": "RUSSELL 2000", "RIYCCTR": "RUSSELL 1000 CONSUMER DISCRETIONARY",
    "NDUEACWF": "MSCI ACWI", "M1WD": "MSCI ACWI", "NDUEEGF": "MSCI EMERGING MARKETS", "M1EF": "MSCI EMERGING MARKETS",
    "MXEF": "MSCI EMERGING MARKETS", "M1WO": "MSCI WORLD", "MXWO": "MSCI WORLD", "NDDUWI": "MSCI WORLD",
    "NDWUIT": "MSCI WORLD INFORMATION TECHNOLOGY", "M1WOMOM": "MSCI WORLD MOMENTUM",
    "SXXGR": "STOXX EUROPE 600", "SXXP": "STOXX EUROPE 600", "SX7GR": "EURO STOXX BANKS", "SX7E": "EURO STOXX BANKS",
    "SX5E": "EURO STOXX 50", "TPXDDVD": "TOPIX", "NDEUCHF": "MSCI CHINA", "M1CN": "MSCI CHINA",
    "MVSMHTR": "SEMICONDUCTOR", "SPXESUP": "S&P 500 ESG", "ICESEMIT": "ICE SEMICONDUCTOR", "MVPPHTR": "PHARMACEUTICAL",
    "GDDUWI": "MSCI WORLD", "NDDUNA": "MSCI NORTH AMERICA", "M1IN": "MSCI INDIA", "NDEUSIA": "MSCI INDIA",
    "M1CNA": "MSCI CHINA A", "SXXR": "STOXX EUROPE 600", "RU20INTR": "RUSSELL 2000", "AS51T": "ASX 200",
    "FTSEMIBN": "FTSE MIB ITALY", "HSI": "HANG SENG", "HSI1": "HANG SENG", "HXTCN": "S&P/TSX 60 CANADA",
    # שורשי חוזים עתידיים (futures_notional.CONTRACT_SPECS)
    "ES": "S&P 500", "ME": "S&P 500", "HWA": "S&P 500", "SLB": "S&P 500 ESG", "NQ": "NASDAQ 100", "HWB": "NASDAQ 100",
    "DM": "DOW JONES INDUSTRIAL", "RTS": "RUSSELL 2000", "FAW": "S&P MIDCAP 400", "XAS": "COMMUNICATION SERVICES SELECT SECTOR",
    "XAY": "CONSUMER DISCRETIONARY SELECT SECTOR", "SWO": "PHLX SEMICONDUCTOR", "NK": "NIKKEI 225", "NO": "NIKKEI 225",
    "NI": "NIKKEI 225", "TP": "TOPIX", "TMI": "TOPIX", "VG": "EURO STOXX 50", "GX": "DAX", "DFW": "DAX",
    "SXO": "STOXX EUROPE 600", "CA": "EURO STOXX BANKS", "SM": "SMI", "RBE": "MSCI EMERGING MARKETS",
    "MES": "MSCI EMERGING MARKETS", "MUR": "MSCI CHINA", "FPO": "MSCI TAIWAN", "JJY": "MSCI KOREA", "ZWP": "MSCI WORLD",
    "RVP": "MSCI WORLD", "ZTL": "MSCI ACWI", "WMW": "MSCI ACWI", "HRL": "MSCI WORLD ESG", "Z": "FTSE 100",
    "XP": "ASX 200", "PT": "TSX 60", "KS": "KOSPI 200", "HI": "HANG SENG", "HU": "HANG SENG", "JGS": "NIFTY 50",
    "TA125": "ת\"א 125", "TA35": "ת\"א 35", "TA90": "ת\"א 90", "TABANKS": "ת\"א בנקים",
}

# ── 2. נושא (ענף / סגנון / מגמה) - (מזהה, תווית, אזור ברירת מחדל) ────────────
# לפי הסדר: ספציפי לפני כללי. אזור ברירת המחדל "us" לענפי GICS (Select Sector וכו').
_THEMES = [
    (r"URANIUM|NUCLEAR|אורניום|גרעינ", "nuclear", "אורניום ואנרגיה גרעינית", ""),
    (r"AEROSPACE|\bAERO\b|DEFEN[CS]E|\bDEF\b|ביטחוני", "defense", "ביטחוניות", "us"),
    (r"HEALTH|BIOTECH|PHARMA|LIFE\W?SCI|\bXLV\b|בריאות|ביוטק", "health", "בריאות", "us"),
    (r"SEMICONDUCTOR|SEMICON|\bMEMORY\b|\bSOX\b|PHLX|\bSMH\b|שבבים", "semis", "שבבים", "us"),
    (r"SOFTWARE|\bIGV\b|תוכנה", "software", "תוכנה ושירותים", "us"),
    (r"HARDWARE|חומרה", "hardware", "חומרה וציוד טכנולוגיים", "us"),
    (r"CLEAN\W?ENERGY|RENEWABLE|SOLAR|אנרגיה מתחדשת|אנרגיה נקייה", "clean_energy", "אנרגיה נקייה", ""),
    (r"\bWATER\b|מים", "water", "מים", ""),
    (r"CYBER|סייבר", "cyber", "סייבר", ""),
    (r"ROBOTIC|ARTIFICIAL|\bAI\b|AUTOMATION|רובוטיקה|בינה מלאכותית", "ai_robotics", "רובוטיקה ובינה מלאכותית", ""),
    (r"INFRASTRUCTURE|\bNFRA\b|\bINFR\b|SMART\W?GRID|תשתיות", "infrastructure", "תשתיות", ""),
    (r"ENVIRONMENT", "environment", "סביבה", ""),
    (r"INSURANCE|ביטוח", "insurance", "ביטוח", ""),
    (r"\bBANK|בנקים|\bKBW\b", "banks", "בנקים", ""),
    (r"REAL\W?ESTATE|\bREIT|נדל\"?ן", "real_estate", "נדל\"ן", ""),
    (r"CONSTRUCTION|HOMEBUILD|בנייה", "construction", "בנייה", ""),
    (r"TECHNOLO|DISRUPTIVE|QUANTUM|MAGNIFICENT|ביג טק|טק-|INFO\w*\W?TECH|INFORMATION\W?TECH|TECH\W?SEL|\bXLK\b|טכנולוגי|\bTECH\b|\bINF\b$", "tech",
     "טכנולוגיה", "us"),
    (r"COMMUNICATION|COMM\W?SERV|TELECOM|\bMEDIA\b|\bXLC\b|תקשורת", "comm", "תקשורת", "us"),
    (r"CONSUMER\W?D[EI]SC|D[EI]SCRETION|CONS\W?DISC|CYCLICAL|RETAIL|TRAVEL|LEISURE|\bXLY\b|שיקול דעת צרכני|צריכה מחזורית", "consdisc",
     "שיקול דעת צרכני", "us"),
    (r"STAPLES|\bXLP\b|צריכה בסיסית|מוצרי צריכה", "staples", "מוצרי צריכה בסיסיים", "us"),
    (r"FINANCIAL|FINTECH|\bFINX\b|CAPITAL\W?MARKETS|\bXLF\b|פיננס", "financials", "פיננסים", "us"),
    (r"INDUSTRIAL|INDUSTR\b|INDUS\b|TRANSPOR|MOBILITY|\bXLI\b|תעשי", "industrials", "תעשייה", "us"),
    (r"UTILIT", "utilities", "תשתיות ושירותים ציבוריים", "us"),
    (r"ENERGY|\bOIL\b|\bXLE\b|אנרגיה|נפט", "energy", "אנרגיה", "us"),
    (r"MATERIALS|METALS|MINING|MINERS|\bRESOURCES?\b|\bXLB\b|חומרי גלם|כרייה", "materials", "חומרי גלם", ""),
    # סגנון
    (r"EQUAL\W?WEIGHT|משקל שווה|שווה משקל", "equal_weight", "משקל שווה", ""),
    (r"\bESG\b|SUSTAIN|\bSUST\b|\bSRI\b|\bSDG\b|CLIMATE|PARIS|CIRCULAR|קיימות|^מעלה$", "esg", "ESG", ""),
    (r"DIVIDEN|\bDVD\b|\bDIV\b|דיבידנד|\bדיב\b", "dividend", "דיבידנד", ""),
    (r"MIN\W?VOL|LOW\W?VOL|תנודתיות נמוכה", "min_vol", "תנודתיות נמוכה", ""),
    (r"MOMENTUM|מומנטום", "momentum", "מומנטום", ""),
    (r"QUALITY|\bQLT\b|\bMOAT\b|איכות|רווחיות", "quality", "איכות", ""),
    (r"GROWTH|\bGWTH\b|צמיחה", "growth", "צמיחה", ""),
    (r"\bVALUE\b|ערך", "value", "ערך", ""),
    (r"SMALL\W?CAP|SMALLCAP|\bS\.CAP|\bSME\w*|קטנות", "small_cap", "חברות קטנות", ""),
    (r"MID\W?CAP|בינוניות", "mid_cap", "חברות בינוניות", ""),
]
THEMES = [(re.compile(p, re.IGNORECASE), i, lbl, reg) for p, i, lbl, reg in _THEMES]

# ── 3. אזור ──────────────────────────────────────────────────────────────────
_REGIONS = [
    (r"ת\"?א|^תל\b|TEL\W?AVIV|ISRAEL|ישראל|^TA\d|^מעלה$", "il", "ישראל"),
    (r"INTERNATIONAL|\bINTERN\b|\bEAFE\b|\bEX\W?U\W?S\b|WORLD\W?EX\W?U|לא כולל ארה", "intl", "בינלאומי (לא כולל ארה\"ב)"),
    (r"EMERG|\bEMER\b|\bEMRG\b|\bEM\b|EMG\W?MKT|E\W?MKT|מתעוררים", "em", "שווקים מתעוררים"),
    (r"\bUK\b|UNITED\W?KINGDOM|BRITAIN|CHELVERTON|בריטניה", "uk", "בריטניה"),
    (r"ITALY|\bMIB\b|איטליה", "italy", "איטליה"),
    (r"GERMANY|\bMDAX\b|גרמניה", "germany", "גרמניה"),
    (r"POLAND|\bWIG\d*|פולין", "poland", "פולין"),
    (r"EUROPE|EURPOE|NORDIC|ERUOPE|EROPE|\bEURP\b|\bERP\b|\bEURO\b|\bEMU\b|STOXX|EURSTX|אירופה", "europe", "אירופה"),
    (r"EX\W*JAPAN|PACIFIC|FAR\W?EAST|ALL\W?COUNTRY\W?ASIA", "asia", "אסיה"),
    (r"JAPAN|\bJAPA?N?\b|\bJPN\b|\bJP\b(?!\W?MORGAN)|\bTPX|SAKUR|יפן|NIKKEI|TOPIX", "japan", "יפן"),
    (r"NETHERLANDS|\bAEX\b|הולנד", "netherlands", "הולנד"),
    (r"AUSTRALIA|\bAUST\b|אוסטרליה", "australia", "אוסטרליה"),
    (r"CHINA|CHAINA|HANG\W?SENG|סין", "china", "סין"),
    (r"BRAZIL|BOVESPA|ברזיל", "brazil", "ברזיל"),
    (r"MEXICO|מקסיקו", "mexico", "מקסיקו"),
    (r"LATIN|אמריקה הלטינית", "latam", "אמריקה הלטינית"),
    (r"INDIA|\bMSCI\W?IND\b|ASHOKA|הודו", "india", "הודו"),
    (r"ASIA|אסיה", "asia", "אסיה"),
    (r"\bU\.?S\.?A?\b|UNITED STATES|AMERICA|S\W?[&@]\W?P\b|S\W?[&@]\W?P\W?\d|RUSSELL|NASDA?Q|NASD\b|\bDOW\b|\bDJ\b|\bKBW\b|L/C|LRG\W?CAP|LARGE\W?CAP|"
     r"SELECT\W?SECTOR|ארה\"?ב", "us", "ארה\"ב"),
    (r"WORLD|WLRD|\bDW\b|GLOBAL|\bGLB\b|\bGBL\b|\bGLOB?\b|ACWI|ALL\W?COUNTRY|INTERNATIONAL|עולמי|גלובלי", "world", "עולמי"),
]
REGIONS = [(re.compile(p, re.IGNORECASE), i, lbl) for p, i, lbl in _REGIONS]
REGION_LABEL = {i: lbl for _, i, lbl in _REGIONS}
_REGION_BROAD = {"world": ("msci_world", "מדד עולמי"), "europe": ("europe", "אירופה"), "em": ("msci_em", "שווקים מתעוררים"),
                 "uk": ("ftse100", "FTSE 100"), "intl": ("acwi_ex_us", "מדד עולמי (לא כולל ארה\"ב)"),
                 "asia": ("asia", "אסיה"), "italy": ("italy", "איטליה"), "australia": ("australia", "אוסטרליה"),
                 "china": ("china", "סין"), "japan": ("japan", "יפן"), "india": ("india", "הודו")}

# ── 4. מדדים רחבים (בלי נושא) ─────────────────────────────────────────────────
_P = [
    (r"DOW\W?JONES\W?INDUSTRIAL|\bDJIA\b|\bINDU\b|דאו ג'ונס", "dow30", "דאו ג'ונס"),
    (r"S\W?P\W?500\W?EX\W?FINANC", "sp500", "S&P 500"),
    (r"S\W?P\W?500.{0,12}EX\W?TECH|EX\W?TECHNOLOG|לא כולל טכנולוגיה", "sp500_ex_tech", "S&P (לא כולל טכנולוגיה)"),
    (r"S\W?P\W?500.{0,25}EQUAL|S\W?P\W?500\W?שווה משקל|S\W?P\W?500\W?משקל שווה", "sp500_ew", "S&P 500 משקל שווה"),
    (r"S\W?P\W?500.{0,20}(ESG|SCORED|SRI|SUSTAIN|PARIS|CLIMATE)", "sp500_esg", "S&P 500 (ESG)"),
    (r"S\s?[&@+]\s?P\W?500|EMINI\W+S\W?P\b|S&P\W?500|\bSPY\b|\bVOO\b|\bIVV\b|\bCSPX\b|\bSP\W?500", "sp500", "S&P 500"),
    (r"NASDAQ\W?COMP", "nasdaq_comp", "נסדק קומפוזיט"),
    (r"NASDA?Q\W?100|NAS\W?100|\bNSDQ\b|\bQQQ\b|\bNAS1\b|נאסד\"?ק|נסד\"?ק", "nasdaq100", "נסדק"),
    (r"MSCI\W?USA?\b|MSCI\W?NORTH\W?AMERICA", "msci_usa", "MSCI USA"),
    (r"RUSSELL?\W?2000|\bIWM\b|ראסל 2000", "russell2000", "ראסל 2000"),
    (r"MIDCAP\W?400|MID\W?CAP\W?400|S\W?P\W?400", "sp400", "S&P 400"),
    (r"EX\W*JAPAN|PACIFIC|FAR\W?EAST|ALL\W?COUNTRY\W?ASIA", "asia", "אסיה"),
    (r"ACWI\W?EX|ALL\W?COUNTRY.{0,15}EX|WORLD\W?EX\W?U\W?S|EX\W?U\W?S\b|לא כולל ארה", "acwi_ex_us",
     "מדד עולמי (לא כולל ארה\"ב)"),
    (r"ACWI|AC\W?WORLD|ALL\W?COUNTRY(?!\W?ASIA)|ALL\W?WORLD|MSCI\W?ALL\b|עולמי.{0,20}כולל.{0,15}מתעוררים", "acwi", "מדד עולמי (כולל שווקים מתעוררים)"),
    (r"EMERG|\bEMER\b|\bEMRG\b|MSCI\W?EM\b|\bEM\b|EMG\W?MKT|E\W?MKT|מתעוררים", "msci_em", "שווקים מתעוררים"),
    (r"MSCI\W?WORLD|\bWORLD\W?INDEX|DEVELOPED|\bURTH\b|^מדד עולמי$|^עולמי$", "msci_world", "מדד עולמי"),
    (r"STOXX\W?(\w+\W?)?600|STX\W?(EUROPE\W?)?600|EURSTX\W?600|EUROPE\W?600|אירופה 600", "stoxx600", "אירופה 600"),
    (r"EURO\W?STOXX\W?50|STOXX\W?50|\bFESX\b|EURSTX\W?50|יורוסטוקס", "stoxx50", "יורוסטוקס 50"),
    (r"\bDAX\b", "dax", "DAX"),
    (r"FTSE\W?100", "ftse100", "FTSE 100"),
    (r"\bSMI\b", "smi", "SMI שווייץ"),
    (r"JPX\W?NIKKEI\W?400", "jpx400", "JPX-ניקיי 400"),
    (r"NIKKEI|ניקיי", "nikkei225", "ניקיי 225"),
    (r"TOPIX|טופיקס", "topix", "טופיקס"),
    (r"HANG\W?SENG|הנג סנג", "hangseng", "הנג סנג"),
    (r"KOREA|KOSPI|קוריאה", "korea", "קוריאה"),
    (r"TAIWAN|טייוואן", "taiwan", "טייוואן"),
    (r"INDIA|NIFTY|SENSEX|הודו", "india", "הודו"),
    (r"CHINA|CSI\W?300|סין", "china", "סין"),
    (r"JAPAN|יפן", "japan", "יפן"),
    (r"ASX\W?200|AUSTRALIA", "australia", "אוסטרליה"),
    (r"TSX|CANADA", "canada", "קנדה"),
    (r"(ת\"?א|TA)[\s-]*35\b|מעו\"?ף", "ta35", "ת\"א 35"),
    (r"(ת\"?א|TA)[\s-]*125\b", "ta125", "ת\"א 125"),
    (r"(ת\"?א|TA)[\s-]*90\b", "ta90", "ת\"א 90"),
    (r"EUROPE|EURO\W?ZONE|אירופה", "europe", "אירופה"),
]
INDEX_PATTERNS = [(re.compile(p, re.IGNORECASE), i, lbl) for p, i, lbl in _P]
_N_BEFORE_THEMES = 5  # דאו ג'ונס וגרסאות S&P 500 - לפני הנושאים ("Dow Jones Industrial" אינו ענף התעשייה)
_KNOWN_IDS = {i for _, i, _ in _P}

_BOND = re.compile(r"BOND|אג\"?ח|ALL-?BOND|תל\W?בונד|תל\W?גוב|מק\"?מ|TREASUR|IBOXX|CORP|\bGOV|\bAGG|"
                   r"אינדקס מדינה|מרווח|\bAA|צמוד|שקלי|\bTIPS\b|HIGH\W?YIELD|\bHY\b|FIXED|CREDIT|"
                   r"פיקדון|כספית|ריבית", re.IGNORECASE)
_HEBREW = re.compile(r"[\u0590-\u05FF]")
# קידומת טיקר בלומברג בשם הקרן ("ICLN US iShares Global Clean Energy", "IWM US - Ishares...") -
# הבורסה אינה אזור החשיפה
_TICKER_PREFIX = re.compile(r"^[A-Z0-9]{2,8}\s+(US|LN|FP|GY|GR|NA|ID|JP|LX|IM|SW|CN|HK|PW|SM|AU)\b\s*-?\s*(?=\S)(?!(EQUITY|INDEX)\s*$)")
_SUFFIX = re.compile(r"\s*-\s*(NTR|GTR|TR|PR|NET|GROSS)\s*$|\bINDEX\b|\bINDX\b", re.IGNORECASE)
_COMPOSITE = re.compile(r"([^,;]+?)\s*(\d+(?:\.\d+)?)\s*%")

# חוזה עתידי -> שורש כפי שהוא (^ES$ וכו' בטבלה), מלבד שורשים שמתנגשים במילים
_SINGLE_STOCK = re.compile(r"\b(EQUITY|UW|UN|US|UQ|LN|TT|JT|GY|FP|HK|CN|IT|SM|NA|SW|IL|KP|KS|JP)\s*$", re.IGNORECASE)
# "מדינה לפי חשיפה כלכלית" - איות שונה בין הגופים
_COUNTRY_ALIASES = {"טאיון": "טייוואן", "דרום קוראה": "דרום קוריאה", "(הממלכה המאוחדת (בריטניה": "בריטניה",
                    "הממלכה המאוחדת": "בריטניה", "צכיה": "צ'כיה", "צילה": "צ'ילה",
                    "Emerging Markets - Asia": "אסיה", "Developed Markets - Europe": "אירופה"}


def normalize_name(text) -> str:
    s = re.sub(r"[®™©℠]", "", str(text or ""))  # "State Street® SPDR® S&P® 500" - הסימן המסחרי שובר את הזיהוי של S&P 500
    s = re.sub(r"\s+", " ", s).strip()
    s = _SUFFIX.sub("", s).strip(" -")
    return _TICKER_PREFIX.sub("", s) or s


def _region(s: str) -> str | None:
    return next((i for rx, i, _ in REGIONS if rx.search(s)), None)


def classify_index(text, full_name: str | None = None) -> tuple[str, str]:
    """(מזהה, שם לתצוגה). סדר: שם מלא (אם נפתר, למשל מ-OpenFIGI) / קוד מוכר ->
    מדד רחב מיוחד (S&P 500 ESG/משקל שווה/ללא טכנולוגיה) -> נושא × אזור (ענף,
    סגנון או מגמה; "צמיחה עולמי", "טכנולוגיה ארה\"ב") -> מדד רחב -> אזור בלבד
    ("מניות ארה\"ב - אחר") -> השם המנורמל עצמו."""
    raw = normalize_name(text)
    code = re.sub(r"\s+(INDEX|IND|EQUITY)$", "", raw, flags=re.IGNORECASE).replace(" ", "").upper()
    code = re.sub(r"TR$", "", code) if code not in _CODES and code[:-2] in _CODES else code
    s = normalize_name(full_name) if full_name else _CODES.get(code, raw)
    if not s:
        return "לא מזוהה", "לא מזוהה"
    for rx, idx, label in INDEX_PATTERNS[:_N_BEFORE_THEMES]:
        if rx.search(s):
            return idx, label
    region = _region(s)
    for rx, theme, label, default_region in THEMES:
        if rx.search(s):
            # קרן זרה בלי אזור בשם (VANGUARD VALUE ETF, FIRST TRUST WATER ETF) - תעודת סל אמריקאית
            reg = region or default_region or ("" if _HEBREW.search(s) else "us")
            return (f"{theme}:{reg}" if reg else theme), (f"{label} {REGION_LABEL[reg]}" if reg else label)
    for rx, idx, label in INDEX_PATTERNS[_N_BEFORE_THEMES:]:
        if rx.search(s):
            return idx, label
    if region:
        # קרן שהמזהה היחיד שלה הוא אזור = המדד הרחב של האזור
        return _REGION_BROAD.get(region) or (f"region:{region}", f"מניות {REGION_LABEL[region]}")
    return s, s


def is_bond_name(text) -> bool:
    return bool(_BOND.search(str(text or "")))


def split_composite(text) -> list[tuple[str, float]]:
    """'All-Bond כללי 70%, ת"א 125 30%' -> [('All-Bond כללי', .7), ('ת"א 125', .3)]."""
    parts = [(m.group(1).strip(" ,;"), float(m.group(2)) / 100) for m in _COMPOSITE.finditer(str(text or ""))]
    return parts if parts and abs(sum(w for _, w in parts) - 1) < 0.02 else [(str(text or ""), 1.0)]


def _equity_parts(underlying) -> list[tuple[str, float]]:
    """חלקי המניות של "נכס בסיס" (משקלים מנורמלים ל-1). בלי חלק מנייתי - כל השם."""
    parts = split_composite(underlying)
    eq = [(n, w) for n, w in parts if not is_bond_name(n)]
    total = sum(w for _, w in eq)
    return [(n, w / total) for n, w in eq] if total else [(str(underlying or ""), 1.0)]


class _Acc:
    def __init__(self):
        self.pct: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.label: dict[str, str] = {}
        self.src: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
        # id(שורת המקור) -> [(מדד, חשיפה)] - לשיוך כל החזקה למדד שלה (holdings_detail)
        self.rows: dict[int, list[tuple[str, float]]] = defaultdict(list)

    def add(self, key, idx, label, value, source, ref=None):
        if not value:
            return
        self.pct[key][idx] += value
        self.label.setdefault(idx, label)
        self.src[key][idx][source] += value
        if ref is not None:
            self.rows[id(ref)].append((idx, value))


def _country_label(country) -> tuple[str, str]:
    c = re.sub(r"\s+", " ", str(country or "")).strip() or "לא ידוע"
    c = _COUNTRY_ALIASES.get(c, c)
    return f"stocks:{c}", f"מניות {c}"


_THEME_IDS = {t for _, t, _, _ in _THEMES}
# מדד רחב של מדינה/אזור יחיד (ר' _REGION_BROAD) - אותה השקעה כמו מניות המדינה
_BROAD_GEO = {"europe": "europe", "asia": "asia", "italy": "italy", "australia": "australia",
              "china": "china", "japan": "japan", "india": "india"}
# מדד בעל שם של מדינה/אזור יחיד - גם הוא מניות אותה מדינה (בכפתור המדינה, בשמו אם הוא לבד)
_NAMED_GEO = {"dax": "גרמניה", "ftse100": "בריטניה", "smi": "שווייץ", "jpx400": "יפן", "nikkei225": "יפן",
              "topix": "יפן", "hangseng": "סין", "korea": "דרום קוריאה", "taiwan": "טייוואן", "canada": "קנדה",
              "stoxx600": "אירופה", "stoxx50": "אירופה"}
_NOT_A_GEO = {"גלובלי", "עולמי", "לא ידוע", ""}


def index_geo(idx: str) -> tuple[str, str] | None:
    """(מדינה/אזור בעברית, סוג) של מזהה מדד: "sector" - ענף/סגנון במדינה ("banks:europe"),
    "stocks" - מניות המדינה (ישירות / קרן אזורית / סל מותאם / מדד רחב של המדינה).
    "index" - מדד בעל שם של מדינה אחת (DAX, ניקיי 225). None - מדד רב-מדינתי (S&P 500 נחשב
    כאן ארה"ב דרך המיתוג בדף) או בלי מדינה. לקיבוץ בדף המסלול."""
    head, _, tail = idx.partition(":")
    out = None
    if head in _THEME_IDS and tail in REGION_LABEL:
        out = REGION_LABEL[tail], "sector"
    elif head in ("stocks", "basket") and tail:
        out = tail, "stocks"
    elif head == "region" and tail in REGION_LABEL:
        out = REGION_LABEL[tail], "stocks"
    elif not tail and idx in _BROAD_GEO:
        out = REGION_LABEL[_BROAD_GEO[idx]], "stocks"
    elif not tail and idx in _NAMED_GEO:
        out = _NAMED_GEO[idx], "index"
    return out if out and out[0] not in _NOT_A_GEO else None

