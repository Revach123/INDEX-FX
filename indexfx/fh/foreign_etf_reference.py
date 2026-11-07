"""חשיפה למניות/אג"ח לקרנות זרות שאינן ישראליות ואינן נסחרות ב-TASE: "נתוני
קרנות" (funds_reference.py) מכיל רק קרנות ישראליות + 40 קרנות חוץ נסחרות
ב-TASE (כולן ISIN אירי - אומת בפועל). קרן זרה שמוחזקת ישירות (למשל ETF
אמריקאית שנסחרת רק ב-NYSE/Nasdaq, לא חוצה-רשומה ב-TASE) לא מזוהה בכלל
ע"י funds.py._classify - נופלת ל"חוץ" (fund_number = ה-ISIN הגולמי, לא
מספר קרן) בלי שום סיווג מניות/אג"ח, ונעלמת מהחשיפה המחושבת (נמצא בפועל
בבדיקת validate_equity_exposure.py: מסלולים עם חשיפה רשמית ~100% למניות
דרך קרנות כאלה, מחושב 0%).

שני מאגרים ב-revach סוגרים את הפער, ללא צורך בשינוי ב-revach עצמו:

1. אוניברסיטת ETF אירופית/גלובלית (iShares/Amundi/Invesco/SPDR/Vanguard/
   XTrackers/JustETF ועוד, בעיקר אירית/לוקסמבורגית) - /api/etf-funds,
   מוגן באותו guard() כמו /api/tracks; X-Match-Key עוקף (כמו
   tracks_reference.py). סיווג קטגורי בלבד (asset_class).
2. ETF אמריקאיות רשומות ב-SEC (~4,400 קרנות, כנראה נגזר מדיווחי N-PORT) -
   data/ETF/SEC/etf_exposure.json, קובץ סטטי בריפו (לא endpoint) - נשלף
   דרך GitHub Contents API עם PAT, בדיוק כמו funds_reference.py. שיעורי
   חשיפה מדויקים (eqTotalPct/bondTotalPct) - עדיף על הסיווג הקטגורי.
"""
import os
import re

import requests

from .excel_io import to_ratio

ETF_FUNDS_URL = "https://revach.pages.dev/api/etf-funds"
MATCH_KEY_ENV = "REVACH_MATCH_KEY"

SEC_CONTENTS_URL = "https://api.github.com/repos/Revach123/revach/contents/data/ETF/SEC/etf_exposure.json"
SEC_NO_DATA = "NoData"  # assetClass של קרן שאין לה עדיין דוח N-PORT
TOKEN_ENV = "PAT"

FOREIGN_TYPE = "חוץ"
EQUITY_SIVEG = 'קרן מחקה - מניות בחו"ל'
BOND_SIVEG = 'קרן מחקה - אג"ח בחו"ל'
PLACEHOLDER_PCT = {"", "ריק במקור", "סוף מידע"}

BOND_ASSET_CLASSES = {"fixed income", "bond"}

# חלק מקוראי האוניברסיטה האירופית (Invesco, JustETF - כ-1,888/3,604 קרנות,
# יותר ממחצית!) אף פעם לא ממלאים asset_class (מגבלת המקור עצמו - לא שדה
# חסר במקרה). לפני שנותרים בלי סיווג, מנסים להסיק מניות/אג"ח משם הקרן +
# המדד - נבדק בפועל על כל ה-1,888: משתחזר סיווג בטוח ל-1,511 (80%), כשמה
# שנשאר לא-מסווג הוא כמעט אך ורק סחורות/מטבעות דיגיטליים/מזומן (לא ניתן,
# ולא כדאי, להכריע כמניות/אג"ח) - לא נבדק לקרנות אג"ח נסתרות שהוחמצו.
_EXCLUDE_NAME_TERMS = (
    "bitcoin", "ethereum", "crypto", "cardano", "solana", "physical gold", "physical silver",
    "digital asset", "commodity", "commodities", "agriculture", " etp", "etp ", "autocallable",
    "option", "overnight rate", "money market", "buffer", "carry", "livestock",
    "multi-strategy", "multi asset", "multi-asset", "infrastructure mlp",
)
_BOND_NAME_TERMS = (
    "bond", "treasury", "gilt", "sovereign", "credit", "coco", "contingent convertible",
    "floating rate note", "municipal", "govt", "government bond", "aggregate",
)


def _classify_by_name(name, benchmark_index) -> str | None:
    """'equity'/'bond'/None לפי מילות מפתח בשם הקרן/המדד - רק כשיש סימן
    סביר (לא ניחוש בברירת מחדל לגמרי חופשי): לא סחורה/קריפטו/מזומן/מובנה,
    ואז אג"ח לפי מילת-מפתח מפורשת, אחרת מניות (רוב ETF שאינו סחורה/אג"ח/
    קריפטו הוא מניות - סקטוריאלי/תמטי/פקטורי/אזורי)."""
    text = f"{name or ''} {benchmark_index or ''}".lower()
    if any(t in text for t in _EXCLUDE_NAME_TERMS):
        return None
    if any(t in text for t in _BOND_NAME_TERMS):
        return "bond"
    if "ucits etf" in text or "etf " in text or text.strip().endswith("etf"):
        return "equity"
    return None


def fetch_etf_universe(session: requests.Session | None = None) -> list[dict]:
    key = (os.environ.get(MATCH_KEY_ENV) or "").strip()
    if not key:
        raise SystemExit(f"[foreign_etf] משתנה הסביבה {MATCH_KEY_ENV} לא מוגדר")
    s = session or requests.Session()
    r = s.get(ETF_FUNDS_URL, headers={"X-Match-Key": key}, timeout=60)
    r.raise_for_status()
    return r.json()


def fetch_sec_etf_exposure(session: requests.Session | None = None) -> list[dict]:
    token = (os.environ.get(TOKEN_ENV) or "").strip()
    if not token:
        raise SystemExit(f"[foreign_etf] משתנה הסביבה {TOKEN_ENV} לא מוגדר")
    s = session or requests.Session()
    r = s.get(SEC_CONTENTS_URL, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw",
    }, timeout=60)
    r.raise_for_status()
    return r.json()


def _isin_key(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip().upper()
    return s or None


def isin_checksum_ok(isin: str) -> bool:
    """ספרת הביקורת של ISIN (Luhn על הספרות, אותיות A=10..Z=35)."""
    s = str(isin or "").strip().upper()
    if len(s) != 12 or not s[:2].isalpha() or not s[-1].isdigit() or not s.isalnum():
        return False
    digits = "".join(str(int(c, 36)) for c in s[:-1])
    total = 0
    for k, ch in enumerate(reversed(digits)):
        n = int(ch) * (2 if k % 2 == 0 else 1)
        total += n // 10 + n % 10
    return (10 - total % 10) % 10 == int(s[-1])


def repair_isin_typos(funds: list[dict], isin_fractions: dict[str, dict[str, float]]) -> dict[str, str]:
    """ISIN של קרן חו"ל שנכשל בספרת הביקורת ולא מסווג (טעות הקלדה של הגוף בקידומת המדינה:
    UC4642886380): אם אותו גוף עם קידומת מדינה אחרת עובר את הבדיקה ומסווג - מקבל את סיווגו.
    מחזיר שגוי -> מתוקן."""
    prefixes = sorted({k[:2] for k in isin_fractions if len(k) == 12 and k[:2].isalpha()})
    out: dict[str, str] = {}
    for f in funds:
        if f["סוג"] != FOREIGN_TYPE:
            continue
        bad = _isin_key(f.get("מספר קרן"))
        if not bad or bad in isin_fractions or bad in out or len(bad) != 12 or isin_checksum_ok(bad):
            continue
        hits = [c for p in prefixes if (c := p + bad[2:]) in isin_fractions and isin_checksum_ok(c)]
        if len(hits) == 1:
            out[bad] = hits[0]
            isin_fractions[bad] = isin_fractions[hits[0]]
    return out


# עוגנים ידניים: מותר רק כשאין שום דרך לבנות פייפליין דינמי שיעבוד (מגבלה
# מבנית קבועה, לא "תקלת איסוף" זמנית) *וגם* כשאין שום אי-ודאות בסיווג -
# חייב להישאר נכון לשנים קדימה בלי תחזוקה. לא כולל קרן שרק נכשלה להיתפס
# ע"י classify_from_report_names/classify_via_openfigi_names/SEC N-PORT
# בגלל קיצוץ בשם או מגבלת כיסוי נקודתית - אלה שייכים בתיקון השכבה
# הדינמית עצמה (מילת-מפתח רחבה יותר וכו'), לא כאן.
#
# SPY/QQQ/DIA/MDY: Unit Investment Trust (לא קרן '40 Act רגילה) - מבנה
# משפטי שאינו מגיש N-PORT בכלל, לפי חוק (מגבלה קבועה, לא ניתנת לפתרון
# בשום פייפליין דינמי מבוסס-N-PORT). מדדי מניות רחבים ומתועדים בפומבי
# (S&P 500/Nasdaq-100/Dow/MidCap 400) - אין אי-ודאות בסיווג.
KNOWN_MAJOR_EQUITY_ETFS = {
    "US78462F1030": "SPY - SPDR S&P 500 ETF Trust (UIT)",
    "US46090E1038": "QQQ - Invesco QQQ Trust, Nasdaq-100 (UIT)",
    "US78467X1090": "DIA - SPDR Dow Jones Industrial Average ETF Trust (UIT)",
    "US78467Y1073": "MDY - SPDR S&P MidCap 400 ETF Trust (UIT)",
    # ISIN היסטורי של אותה קרן QQQ בדיוק, מלפני שינוי השם מ-"PowerShares"
    # ל-"Invesco QQQ" - עובדת-זהות (alias), לא סיווג: אין שום פייפליין
    # (כולל SEC N-PORT) שיכול לגלות שני ISIN שונים = אותו נייר בלי מאגר
    # CUSIP-history בתשלום, וזו עובדה קבועה שלא משתנה למפרע.
    "US73935A1043": "Invesco QQQ Trust - CUSIP היסטורי (PowerShares)",
}

# קרנות השקעה סגורות (closed-end) הגרנזיות בניהול Bill Ackman - Guernsey
# אינה בתחום השיפוט של SEC, לכן לא תוגש N-PORT בשום נסיבות (מגבלה מבנית
# קבועה). מנדט מוצהר: תיק מרוכז ב-long equity - אין אי-ודאות בסיווג.
KNOWN_EQUITY_FUNDS_OTHER = {
    "GG00BPFJTF46": "Pershing Square Holdings Ltd (Guernsey, LSE:PSH)",
}

# קרנות/נאמנויות סחורה פיזית וקריפטו (grantor trust, לא '40 Act) - לא
# מגישות N-PORT בשום נסיבות (מגבלה מבנית קבועה, כמו UIT), ולא מניות/אג"ח
# בכלל (אין אי-ודאות: זהב/כסף/פלטינה/ביטקוין/את'ריום פיזיים, לא ניירות
# ערך). מסומנות 0/0 במפורש - "מזוהה כסחורה/קריפטו", לא "לא ידוע" - במקום
# להיבדק שוב בכל שכבה בלי תוחלת (SEC N-PORT/Yahoo כבר נכשלים עליהן תמיד
# מאותה סיבה מבנית, נבדק בפועל).
KNOWN_COMMODITY_CRYPTO_TRUSTS = {
    "US78463V1070": "SPDR Gold Shares (Gold Trust)",
    "US4642852044": "iShares Gold Trust",
    "US46428Q1094": "iShares Silver Trust",
    "US0032601066": "abrdn Physical Platinum Shares ETF",
    "US46438F1012": "iShares Bitcoin Trust ETF",
    "US46438R1059": "iShares Ethereum Trust ETF",
    "US92864M4006": "2x Ether ETF (Ether Strategy, leveraged crypto)",
}

# קרנות אג"ח בודדות, מזוהות ומתועדות בפומבי, שהשם המקוצר/המלא שמגיע
# מ-OpenFIGI קטוע מכדי לתפוס במילת-מפתח כללית בלי סיכון false-positive
# (ר' תיעוד _classify_by_report_name) - לא הנחה על טווח-מוצר, ISIN בודד
# מתועד. "Amundi Planet Emerging Green One" - קרן אג"ח ירוקות ב-EM (יוזמת
# IFC/Amundi מתועדת בפומבי). "Stone Harbor Emerging Markets Corporate
# Debt" - קרן אג"ח קונצרני EM, שמו של מנהל ההשקעות (Stone Harbor) הוא
# מתמחה הכנסה קבועה בלבד.
KNOWN_BOND_FUNDS_OTHER = {
    "LU1688575437": "Amundi Planet Emerging Green One",
    "IE00B3RGB191": "Stone Harbor Emerging Markets Corporate Debt",
}


def build_isin_fractions(etf_universe: list[dict], sec_exposure: list[dict]) -> dict[str, dict[str, float]]:
    """ISIN (מנורמל) -> {"equity": שבר 0..1, "bond": שבר 0..1}. SEC (שיעורים
    מדויקים) דורס את האוניברסיטה האירופית (סיווג קטגורי בלבד: Equity->1.0,
    Fixed Income/Bond->0.0, שאר הסיווגים [Multi Asset/Commodity/...] מדולגים -
    לא ניתן להסיק מהם שבר מניות/אג"ח בינארי אמין)."""
    out: dict[str, dict[str, float]] = {
        isin: {"equity": 1.0, "bond": 0.0}
        for isin in (*KNOWN_MAJOR_EQUITY_ETFS, *KNOWN_EQUITY_FUNDS_OTHER)
    }
    out.update({isin: {"equity": 0.0, "bond": 0.0} for isin in KNOWN_COMMODITY_CRYPTO_TRUSTS})
    out.update({isin: {"equity": 0.0, "bond": 1.0} for isin in KNOWN_BOND_FUNDS_OTHER})
    for rec in etf_universe:
        isin = _isin_key(rec.get("isin"))
        if isin is None:
            continue
        ac = (rec.get("asset_class") or "").strip().lower()
        if ac == "equity":
            out[isin] = {"equity": 1.0, "bond": 0.0}
        elif ac in BOND_ASSET_CLASSES:
            out[isin] = {"equity": 0.0, "bond": 1.0}
        else:
            by_name = _classify_by_name(rec.get("name"), rec.get("benchmark_index"))
            if by_name == "equity":
                out[isin] = {"equity": 1.0, "bond": 0.0}
            elif by_name == "bond":
                out[isin] = {"equity": 0.0, "bond": 1.0}

    for rec in sec_exposure:
        isin = _isin_key(rec.get("isin"))
        if isin is None:
            continue
        eq, bd = rec.get("eqTotalPct"), rec.get("bondTotalPct")
        if eq is None and bd is None:
            continue
        # קרן בלי דוח N-PORT (assetClass "NoData" - קרן חדשה, SMHC/NASA): ה-0/0 בטבלה הוא היעדר
        # נתון, לא הרכב - לא נרשם, כדי שהשכבות הבאות (שם בדוח, N-PORT חי, Yahoo) יסווגו אותה
        if str(rec.get("assetClass") or "") == SEC_NO_DATA:
            continue
        out[isin] = {"equity": (eq or 0.0) / 100, "bond": (bd or 0.0) / 100}
        if (rec.get("eqSynthPct") or 0) > 0:
            out[isin]["synth"] = rec["eqSynthPct"] / 100  # מניות דרך נגזרים (סוואפ) - האג"ח הן בטוחה
    return out


US_SECURITIES_URL = "https://api.github.com/repos/Revach123/revach/contents/data/securities_us/us_securities.json"


def fetch_us_security_names(session: requests.Session | None = None) -> dict[str, str]:
    """ISIN -> שם הנייר הרשמי מרשימת ניירות ארה"ב של revach (security_name: "Corgi Lithography &
    Semiconductor Photonics ETF" ל-EUV, שאין לה עדיין דוח SEC ולא נמצאת באוניברסיטת ה-ETF)."""
    token = (os.environ.get(TOKEN_ENV) or "").strip()
    if not token:
        return {}
    try:
        s = session or requests.Session()
        r = s.get(US_SECURITIES_URL, headers={"Authorization": f"Bearer {token}",
                                              "Accept": "application/vnd.github.raw"}, timeout=120)
        r.raise_for_status()
        rows = (r.json() or {}).get("securities") or []
    except Exception as e:
        print(f"[foreign_etf] ניירות ארה\"ב (revach) לא זמינים: {e}")
        return {}
    return {isin: str(x["security_name"]).strip() for x in rows
            if (isin := _isin_key(x.get("isin"))) and x.get("security_name")}


def official_fund_names(etf_universe: list[dict], sec_exposure: list[dict],
                        us_names: dict[str, str] | None = None) -> dict[str, str]:
    """ISIN -> שם הקרן הרשמי (אוניברסיטת ה-ETF / SEC). הגופים מדווחים לעיתים שם קטוע או שגוי
    (US92206C7719 מדווח "MARKET VECTORS GOLD MINERS" והוא Vanguard Mortgage-Backed Securities ETF)."""
    out: dict[str, str] = dict(us_names or {})
    for rec in (*sec_exposure, *etf_universe):
        isin = _isin_key(rec.get("isin"))
        name = str(rec.get("name") or "").strip()
        if isin and name:
            out[isin] = name
    return out


# שכבת מוצא-אחרון: קרנות "חוץ" שלא נמצאו בשום מאגר חיצוני (לא אירופה, לא SEC,
# לא עוגן ידני) - מנסים להסיק מניות/אג"ח מהשם עצמו כפי שהוא מדווח בדוח
# הפנסיוני (row["שם נייר ערך"], לא שם רשמי מלא - לרוב מקוצר/מקוצר-אוטומטית
# ע"י מערכת המשמורת, למשל "PIMCO HIGH YIELD BO"/"NEU BER GL SE FL RT").
# שמרני בהרבה מ-_classify_by_name: *לא* ברירת-מחדל-למניות סתם על כל "ETF" -
# שם מקוצר/לא רשמי נותן פחות ודאות, ולכן נדרש מונח מובהק (אג"ח או מניות)
# ולא רק העדר מונח-אג"ח. מדולג (לא מסווג) כשאין מונח מובהק משני הצדדים.
_REPORT_NAME_BOND_TERMS = (
    "bond", "treasury", "gilt", "sovereign", "high yiel", "senior loan", "sen.sec",
    "sen sec", "senior sec", "corp debt", "floating rate", "credit", "govt",
    "gov bnd", "agg bnd", "municipal", "debenture", "clo income", "debt",
    "fallen angel", "short dur", "senior lo", "liq. corp", "hi yld", "inv gr cred",
    "mortgage-backed", "mortgage backed",
    # מנפיקים/טווחי-מוצר שכל הקרנות בהם הן הכנסה קבועה בלבד תמיד - עובדה
    # יציבה על המותג/הטווח (לא ניחוש על קרן ספציפית, ולא ISIN-ים בודדים):
    # "bluebay" (RBC BlueBay Asset Management - אך ורק אג"ח/קרדיט); "pimco
    # gis" (PIMCO Global Investors Series - טווח ה-UCITS של PIMCO שהוא אך
    # ורק אג"ח, בשונה מקרנות PIMCO אחרות).
    "bluebay", "pimco gis",
)
_REPORT_NAME_EQUITY_TERMS = (
    "equity", "eqy", "growth", "value", "dividend", "dvd", "biotech", "technology",
    "tech", "thematic", "rotation", "water", "agtech", "food innovat", "momentum",
    "quality", "factor", "equal weight", "msci", "s&p", "sp 500", "russell", "nasdaq",
    "topix", "nikkei", "stoxx", "ftse", "mid cap", "midcap", "small cap", "life scie",
    "discretionary", "discret", "meme", "uranium", "index fund", "index equity",
    "energy solutions", "resource", "defense",
    # "HOLDRs Trust" - מבנה grantor-trust ישן (כמו UIT) שמחזיק סל מניות סקטור
    # יחיד בלבד (Merrill Lynch, שהופסקו ב-2011 אך עדיין נסחרים/מדווחים) -
    # עובדה מבנית קבועה, לא ניחוש. "Select Sector SPDR" - 11 קרנות הסקטור
    # הקבועות של SPDR (S&P 500 לפי סקטור) - כולן מניות, עובדה קבועה על
    # טווח המוצר (לא ניחוש על קרן ספציפית).
    "holdrs", "sector spdr", "healthcare op", "mkt eq", "sml cap",
    # חברות קטנות ("Smaller Companies" / "SM.CIE" / "SML CO") ו-NSDQ (קיצור Nasdaq) - קרנות מניות
    "smaller", "sm.cie", "sml co", "nsdq", "equities",
)

# קרנות כספיות/מזומן (money-market) - לא מניות ולא אג"ח, תורמות 0 לשני
# הסיווגים (לא "לא ידוע"). "LVNAV" (Low Volatility NAV) הוא מונח רגולטורי
# מפורש למבנה קרן כספית לפי חוק ה-MMF האירופי - אין אי-ודאות. חלק
# מהשורות האלה מגיעות עם "ISIN" שאינו ISIN אמיתי בכלל (קוד פנימי בתחילית
# X9X9 - נבדק בפועל מול OpenFIGI: "Invalid idValue format") ולכן לא יזוהו
# בשום שכבה אחרת.
_REPORT_NAME_CASH_TERMS = ("liquidity", "lvnav", "money market", "money mkt", "cp liq")


def _classify_by_report_name(name: str | None) -> str | None:
    if not name:
        return None
    text = name.lower()
    if any(t in text for t in _REPORT_NAME_CASH_TERMS):
        return "cash"
    if any(t in text for t in _REPORT_NAME_BOND_TERMS):
        return "bond"
    if any(t in text for t in _REPORT_NAME_EQUITY_TERMS):
        return "equity"
    return None


_NOT_EQUITY_FUND = re.compile(r"MACRO|FEEDER|HEDGE|LONG\W?SHORT|ABSOLUTE|P2P|PEER|LENDING|INCOME FUND|"
                              r"INSURANCE|LIFE\b|SICAV ACC", re.IGNORECASE)


def _sector_equity_by_name(name: str | None) -> str | None:
    """"equity" כשהשם ממופה לענף/סגנון ע"י מסווג המדדים (index_exposure.classify_index):
    VanEck China Semiconductor, SPDR Europe Industrials, Gold Miners (חומרי גלם) - קרנות מניות
    שה-_classify_by_report_name המחמיר לא תופס (אין "equity"/"tech" בשם). לא לפי אזור בלבד
    ("LION III EUR"), ולא סחורה/קריפטו/גידור/אשראי."""
    if not name or _NOT_EQUITY_FUND.search(str(name)):
        return None
    from .alt_asset_reference import class_by_name
    from .index_exposure import _THEME_IDS, classify_index
    if class_by_name(name):
        return None
    idx = classify_index(name)[0]
    head = idx.partition(":")[0]
    if head in _THEME_IDS:
        return "equity"
    return None


def classify_from_report_names(source: list[dict]) -> dict[str, dict[str, float]]:
    """ISIN -> {"equity":.., "bond":..} לפי "שם נייר ערך" כפי שמדווח בגיליונות
    'קרנות סל'/'קרנות נאמנות' עצמם - מיועד כשכבת מוצא-אחרון (ר' תיעוד למעלה),
    לא כתחליף למאגרים החיצוניים. קרן כספית (ר' _REPORT_NAME_CASH_TERMS) או
    קוד פנימי שאינו ISIN אמיתי (תחילית X9X9) מסווגים כ-0/0 (לא תורמים לאף
    סיווג) - "מזוהה כמזומן", לא "לא ידוע"."""
    out: dict[str, dict[str, float]] = {}
    for rec in source:
        if rec["Category"] not in ("קרנות סל", "קרנות נאמנות") or rec["מידע"] != "מידע":
            continue
        for row in rec["Clean"]:
            isin = _isin_key(row.get("מספר נייר ערך"))
            if isin is None or isin in out:
                continue
            if isin.startswith("X9X9"):
                out[isin] = {"equity": 0.0, "bond": 0.0}
                continue
            # "שם מנפיק" מחזיק לעיתים את שם הקרן המלא ("CT Lux Japan Equities") ולעיתים את המנהל
            # ("State Street Bank") - ממנו רק המונחים המובהקים, לא ענף לפי שם
            cls = (_classify_by_report_name(row.get("שם נייר ערך")) or _sector_equity_by_name(row.get("שם נייר ערך"))
                   or _classify_by_report_name(row.get("שם מנפיק")))
            if cls == "equity":
                out[isin] = {"equity": 1.0, "bond": 0.0}
            elif cls == "bond":
                out[isin] = {"equity": 0.0, "bond": 1.0}
            elif cls == "cash":
                out[isin] = {"equity": 0.0, "bond": 0.0}
    return out


def classify_via_openfigi_names(missing_isins: list[str]) -> dict[str, dict[str, float]]:
    """שכבה אחרונה, יקרה (קריאות רשת חיות ל-OpenFIGI): לכל ISIN "חוץ" שעדיין
    לא מסווג בשום שכבה אחרת (כולל classify_from_report_names), מנסה לפתור
    את השם המלא/הרשמי הלא-קצוץ (ר' sec_nport_reference.resolve_isin_to_name)
    ולסווג אותו לפי אותה שיטת מילות-מפתח בדיוק - מגלה קרנות שה-classify_
    from_report_names לא תפס כי השם *כפי שמדווח בדוח הפנסיוני* קצוץ יותר
    מדי (למשל "POLAR CAPITAL-GLB TECH" בלי "-nology", "NB GLB FLEX CRE" בלי
    "-dit"), אבל השם הרשמי המלא מ-OpenFIGI כן מכיל מונח מזהה ברור. לא מוגבל
    ל-ISIN אמריקאי - OpenFIGI מכסה גם קרנות אירופיות/אסייתיות רבות. כשלון
    רשת מדולג בשקט (רשימה ריקה) - לא כתובה ל-sec_nport_reference עצמו כדי
    לא ליצור תלות מעגלית בין שני המודולים."""
    if not missing_isins:
        return {}
    from .sec_nport_reference import _openfigi_lookup

    figi = _openfigi_lookup([i for i in missing_isins if i])
    names = {isin: d["name"].strip() for isin, d in figi.items() if d.get("name")}
    print(f"[openfigi_names] {len(names)}/{len(missing_isins)} ISIN נפתרו לשם מלא דרך OpenFIGI")
    out: dict[str, dict[str, float]] = {}
    for isin, d in figi.items():
        # מניה שגוף דיווח בגיליון קרנות (DISCO CORP JP3046680009) - סוג הנייר ב-OpenFIGI
        if STOCK_FIGI_TYPES & {d.get("securityType"), d.get("securityType2")}:
            out[isin] = {"equity": 1.0, "bond": 0.0, "stock": True}
    for isin, full_name in names.items():
        if isin in out:
            continue
        cls = _classify_by_report_name(full_name)
        if cls == "equity":
            out[isin] = {"equity": 1.0, "bond": 0.0}
        elif cls == "bond":
            out[isin] = {"equity": 0.0, "bond": 1.0}
    print(f"[openfigi_names] {len(out)}/{len(missing_isins)} ISIN סווגו בהצלחה")
    return out


STOCK_FIGI_TYPES = {"Common Stock", "ADR", "GDR", "REIT"}


def classify_from_registry_names(missing_isins: list[str], official_names: dict[str, str]) -> dict[str, dict[str, float]]:
    """קרן שלא סווגה, לפי שמה הרשמי במאגרים (SEC / אוניברסיטת ה-ETF / ניירות ארה"ב של revach) - שם
    מלא ונקי, לכן גם ענף לפי שם ("Corgi Lithography & Semiconductor Photonics ETF" -> מניות)."""
    out: dict[str, dict[str, float]] = {}
    for isin in missing_isins:
        name = official_names.get(isin)
        cls = _classify_by_report_name(name) or _sector_equity_by_name(name)
        if cls == "equity":
            out[isin] = {"equity": 1.0, "bond": 0.0}
        elif cls == "bond":
            out[isin] = {"equity": 0.0, "bond": 1.0}
        elif cls == "cash":
            out[isin] = {"equity": 0.0, "bond": 0.0}
    return out


def collect_unclassified_foreign_isins(funds: list[dict], isin_fractions: dict[str, dict[str, float]]) -> list[str]:
    """ISIN-ים ייחודיים של קרנות "חוץ" (מפתח שלהן הוא ISIN, ר' funds.py._classify)
    שעדיין לא מסווגים באף שכבה קיימת - מיועד להזנה לשכבה האחרונה, היקרה
    (sec_nport_reference.py: OpenFIGI + N-PORT חי; yahoo_fund_reference.py),
    כדי להריץ אותה רק על מה שבאמת חסר. קרנות "נסחרת" מסווגות ישירות דרך
    funds_il.py (סיווג MAYA מדויק לפי ISIN), לא דרך השכבה הזו."""
    out: set[str] = set()
    for row in funds:
        if row["סוג"] != FOREIGN_TYPE:
            continue
        isin = _isin_key(row.get("מספר קרן"))
        if isin and isin not in isin_fractions:
            out.add(isin)
    return list(out)


def _build_equity_by_type(
    funds: list[dict], isin_fractions: dict[str, dict[str, float]],
    fund_type: str, equity_label: str, bond_label: str,
) -> dict[str, dict[str, float]]:
    sums: dict[str, dict[str, float]] = {}
    for row in funds:
        if row["סוג"] != fund_type:
            continue
        raw_pct = row.get("שיעור מסך נכסי ההשקעה")
        if isinstance(raw_pct, str) and raw_pct in PLACEHOLDER_PCT:
            continue
        pct = to_ratio(raw_pct)
        if pct is None:
            continue
        frac = isin_fractions.get(_isin_key(row.get("מספר קרן")))
        if frac is None:
            continue
        key = row["מפתח"]
        d = sums.setdefault(key, {})
        if frac["equity"]:
            d[equity_label] = d.get(equity_label, 0.0) + pct * frac["equity"]
        if frac["bond"]:
            d[bond_label] = d.get(bond_label, 0.0) + pct * frac["bond"]
    return sums


# קרן ממונפת (ULTRA / 2X / 3X / LEVERAGED / BULL) - שבר מניות מעל 1 אמיתי (TQQQ = 3.0)
_LEVERAGED_NAME = re.compile(r"ULTRA|\b[23]X\b|LEVERAG|\bBULL\b|DAILY\s+\d", re.IGNORECASE)
MAX_UNLEVERED_EQUITY = 1.05


def sanitize_fractions(isin_fractions: dict[str, dict[str, float]], source: list[dict]) -> list[str]:
    """שבר מניות מעל 1 בקרן לא ממונפת הוא שגיאת מקור (US4642867729, iShares MSCI South
    Korea: equity=13.07 משכבות ה-CI - 26% משקל מצטבר במסלולים, 11 נק' בכל מסלול
    "כללי" של מיטב). מנרמל: מניות ואג"ח מחולקים בסכומם (אג"ח שלילי נחשב 0) כך שמניות
    <= 1. קרן ממונפת (לפי השם בדוח) נשארת כמו שהיא. מחזיר את ה-ISIN שתוקנו."""
    names: dict[str, str] = {}
    for rec in source:
        if rec.get("Category") in ("קרנות נאמנות", "קרנות סל"):
            for r in rec["Clean"]:
                isin = str(r.get("מספר נייר ערך") or "").strip().upper()
                n = str(r.get("שם נייר ערך") or "")
                if isin and len(n) > len(names.get(isin, "")):
                    names[isin] = n
    fixed = []
    for isin, frac in isin_fractions.items():
        eq = frac.get("equity") or 0.0
        if eq <= MAX_UNLEVERED_EQUITY or _LEVERAGED_NAME.search(names.get(isin, "")):
            continue
        if frac.get("synth"):
            # מניות פיזיות + דרך סוואפ >= 100% (MAGS: 43% + 66%, אג"ח 53%): האג"ח הן בטוחה לסוואפ
            isin_fractions[isin] = {**frac, "equity": 1.0, "bond": 0.0}
            fixed.append(isin)
            continue
        bond = max(frac.get("bond") or 0.0, 0.0)
        total = eq + bond
        isin_fractions[isin] = {**frac, "equity": eq / total, "bond": bond / total}
        fixed.append(isin)
    return fixed


def build_foreign_equity(funds: list[dict], isin_fractions: dict[str, dict[str, float]]) -> dict[str, dict[str, float]]:
    """מפתח -> {"קרן מחקה - מניות בחו\"ל": ..., "קרן מחקה - אג\"ח בחו\"ל": ...},
    לשורות "חוץ" בלבד (לא ישראליות, לא נסחרות ב-TASE - 'מספר קרן' הוא ה-ISIN
    הגולמי, ר' funds.py._classify) שמזוהות באחד משני המאגרים. לא נוגע בקרנות
    IL/נסחרת - אלה כבר מטופלות ע"י funds_il.py (סיווג MAYA מדויק, לא הסקה
    מ-isin_fractions), בלי חפיפה אפשרית (כל שורה מסווגת לדיוק אחד מ-IL/
    נסחרת/חוץ)."""
    return _build_equity_by_type(funds, isin_fractions, FOREIGN_TYPE, EQUITY_SIVEG, BOND_SIVEG)
