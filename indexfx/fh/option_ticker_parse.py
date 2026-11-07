"""מזהה נכס-בסיס (טיקר) + כיוון (Call/Put) משדה "שם נייר ערך" בגיליונות
"אופציות"/"לא סחיר אופציות" - בשונה מסוואפים, אין עמודת "טיקר" נפרדת;
הזיהוי חייב לפרסר את השם עצמו. נמצאו בבדיקה בפועל (סריקת רבעון אחרון,
86 קבצים, 13,180 שורות אופציה על מניות) **לפחות 7 מוסכמות שם שונות** בין
מגישים שונים - לא פורמט אחיד.

כל דפוס (A-F) הוא חילוץ מכני חד-משמעי, לא ניחוש. השכבות היחידות שדורשות
אימות חיצוני (שמות חברות עבריות, קודי-מעוף) מוגבלות בכוונה לרשימה סגורה
שאומתה בפועל - שמות/קודים מלאים מול Yahoo Finance longName, וקודי-מעו"ף
הקצרים (בזן/ברס/פנק) מול ה-API הרשמי של הבורסה עצמה
(api.tase.co.il/api/derivatives/all, שדה AssetName - ר' revach123/INDICES
scripts/probe_tase_derivatives.py). קוד שלא הצליח לאמת (כמו קודי-2-3-
אותיות "BZ"/"MIG"/"PL" שמתנגשים עם טיקרים גלובליים אמיתיים לא-קשורים, או
"פרן" שלא נמצא כלל בסנאפשוט הנוכחי של הבורסה - כנראה אופציה שפקעה) נשאר
במפורש לא-ממופה - נופל בחזרה לשיטת שווי-הוגן הקיימת ב-derivatives_exposure.py,
לא מוצב בנוסחה עם קנה-מידה שגוי (אותו עיקרון שכבר יושם ב-swap_ticker_map.csv).

כיסוי בפועל (רבעון אחרון, לאחר כל השכבות כולל קודי-המעו"ף המאומתים):
מעל 73.9% משורות אופציה על מניות (המספר המדויק תלוי בכמות ה-בזן/ברס/פנק
בכל תקופה - לא נמדד מחדש אחרי ההוספה).
"""
import re

# Pattern A: "AMAT 17/07/26 C700" / "SPXW 31/07/26 P6700" -> ticker=AMAT/SPXW
# Pattern A2: "MU US 07/02/26 P1060" / "TSEM US 07/17/26 C130" -> ticker=MU/TSEM
PATTERN_A = re.compile(r"^([A-Z][A-Z0-9.]{0,6})\s+(?:US\s+)?\d{1,2}/\d{1,2}/\d{2,4}\s+[CP]")

# Pattern A3: "TEVA-US 18/09/26 C30" -> ticker=TEVA
PATTERN_A3 = re.compile(r"^([A-Z][A-Z0-9.]{0,6})-US\s+\d{1,2}/\d{1,2}/\d{2,4}\s+[CP]")

# Pattern B: "July 26 Puts on TSEM US" / "September 26 Calls on SEDG US" -> ticker=TSEM/SEDG
# also covers index names without "US" e.g. "July 26 Calls on SX5E"/"...on NDX"
PATTERN_B = re.compile(r"\bon\s+([A-Z][A-Z0-9.]{0,6})(?:\s+US)?\s*$", re.IGNORECASE)

# Pattern C: TASE MAOF code "C023000M608-כלל" / "P004170M607-35ת" -> hebrew suffix
# (optional stray Hebrew "ת" prefix seen on some filers' truncated rows)
PATTERN_C = re.compile(r"^ת?[CP][\d.]+M\d+-(.+)$")

# Pattern G: אופציית מדד מעו"ף חודשית בשם מקוצר "C 4300 APR" / "P 4300 APR" (עגור) -
# מתחיל ישר ב-C/P ומחיר מימוש ברמת ת"א 35 (קודי מניות מעו"ף מתחילים בקוד: "BZ C 250 AUG").
# הזיהוי מאומת בחישוב עצמו: מימוש/מחיר המדד חייב להיות סביר (option_delta_pricing).
# קידומת "tl" אצל חלק מהגופים ("tlC 3100 NOV" ב-512065202_gm_0325; ברבעון שאחריו "C 3400 JAN 26 TL1")
# אופציה על חוזה E-mini (CME) בקוד בלומברג: שורש + חודש + ספרת שנה + C/P (+ ספרת שבוע) ומימוש -
# "ESH6P 6400", "QNAK6C 25000", "SCK6P 6000", "3EF6C 7000", "IMBWN6C2 7680" (513173393). נכס הבסיס
# (S&P / נאסד"ק / ראסל / דאו) נקבע לפי המימוש מול רמות המדדים ביום הדוח (derivatives_exposure)
PATTERN_FO = re.compile(r"^([0-9A-Z]{1,6}?)[FGHJKMNQUVXZ]\d([CP])\d?\s+\d+(?:\.\d+)?(?:\s+INDEX)?$", re.IGNORECASE)
PATTERN_FO_NAME = re.compile(r"(?:S&P\s*500|NASDAQ\s*100).*E-?MINI|E-?MINI.*(?:S&P|NASDAQ)", re.IGNORECASE)
FUTURES_OPTION = "IDX_FO"
# אופציה על מניה בת"א בפורמט בלומברג: "BEZQ IT C7.5 17.12.25" (512245812)
PATTERN_IT = re.compile(r"^([A-Z]{2,6})\s+IT\s+[CP]\d")
# ניקיי (OSE): "NKY 4 P51000" (513173393) - הפורמט עם תאריך מכוסה בדפוס A
PATTERN_NKY = re.compile(r"^NKY\s+\d{1,2}\s+[CP]\d")
# קידומת "b" אצל מגדל / כלל ("bC 3100 NOV", "BC 3400 JAN 26")
PATTERN_G = re.compile(r"^(?:ת|TL|B)?([CP])\s?(\d{3,5}(?:\.\d+)?)\s+(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\b", re.IGNORECASE)
# מחיר מימוש מתוך קוד מעו"ף "C004160M607-35ת" (כשעמודת שער המימוש ריקה / 0)
_MAOF_STRIKE = re.compile(r"^ת?[CP]0*(\d+(?:\.\d+)?)M\d")
# חודש פקיעה מתוך קוד מעו"ף: M<ספרת שנה><חודש> - "M607" = 07/2026
_MAOF_EXPIRY = re.compile(r"^ת?[CP][\d.]+M(\d)(\d{2})")

# Pattern D: "SPXW PUT 6700" / "TEVA CALL 30" / "CALL AMAT 710" / "PUT TSEM 220" /
#            "C EWY 260" / "put EWY 180" -> ticker adjacent to CALL/PUT/C/P keyword.
# Source rows are truncated by the filer (cut off mid-string) - only look at
# the ticker token itself, which is unaffected by the truncation.
PATTERN_D1 = re.compile(r"^([A-Z][A-Z0-9.]{1,6})\s+(?:CALL|PUT|C|P)\s+\d", re.IGNORECASE)
PATTERN_D2 = re.compile(r"^(?:CALL|PUT|C|P)\s+([A-Z][A-Z0-9.]{1,6})\s+\d", re.IGNORECASE)

# Pattern E: "GLBE P 25 20/11/26" / "ORA C115 17/07/26" -> ticker=GLBE/ORA
PATTERN_E = re.compile(r"^([A-Z][A-Z0-9.]{1,6})\s+[CP]\s?\d")

# Pattern F: "BNP C92 17/07/26" / "CEG C 330 20/11/26" -> ticker=BNP/CEG
PATTERN_F = re.compile(r"^([A-Z]{2,5})\s+[CP]\d")

# קודי אבחון-קצר עבריים ידועים כלא-חד-משמעיים (למשל "bzC 780.00 JUL 2026",
# "BZ C 250 AUG", "MIG P 600 AUG", "PL C 2200 AUG", "DSC 2900 AUG26") -
# מתנגשים עם טיקרים גלובליים אמיתיים לא-קשורים (BZ=Kosmos Energy, PL=Planet
# Labs) ואין מקור מאומת למה כל קוד מייצג אצל כל מגיש. חסום מהדפוסים
# הכלליים במפורש - לא להסיר בלי מיפוי מאומת לכל קוד.
_AMBIGUOUS_SHORT_CODES = {"BZ", "LM", "DS", "MIG", "PL"}

# אומת (לא נוחש) מול Yahoo Finance longName - ר' revach123/INDICES
# scripts/probe_tase_stocks.py / probe_out_committed/tase_stocks.json.
# רק שמות שאומתו בפועל; דמרי/הכשרת הישוב/בזן/פז נכשלו באימות ולא נכללים.
HEBREW_NAME_TICKER = {
    "פועלים": "POLI.TA", "הפועלים": "POLI.TA",
    "לאומי": "LUMI.TA",
    "דיסקונט": "DSCT.TA",
    "מזרחי טפחות": "MZTF.TA",
    "בזק": "BEZQ.TA",
    "כלל": "CLIS.TA", "כלל ביטוח": "CLIS.TA", "כלל בטוח": "CLIS.TA",
    "פניקס": "PHOE.TA",
    "מנורה": "MMHD.TA",
    "מגדל": "MGDL.TA",
    "אנלייט": "ENLT.TA",
    "אפקון החזקות": "AFHL.TA",
}
# מהשם הארוך לקצר, כדי ש"כלל ביטוח" יתאים לפני התת-מחרוזת "כלל" הבודדת
_HEBREW_NAMES_BY_LEN = sorted(HEBREW_NAME_TICKER, key=len, reverse=True)

# קודי-קיצור מעו"ף (מחרוזות שונות מהשמות המלאים למעלה, למשל "דסק" לא
# "דיסקונט") - רק מה שאומת. בזן/ברס/פנק/פרן שנמצאו בארכיון לא נכללים:
# הניחוש ל-בזן (BAZN.TA) נכשל באימות, ולברס/פנק/פרן אין זיהוי מאומת.
MAOF_ABBREV_TICKER = {
    "כלל": "CLIS.TA",
    "בזק": "BEZQ.TA",
    "דסק": "DSCT.TA",
    # אומתו ישירות מול ה-API הרשמי של הבורסה (api.tase.co.il/api/derivatives/all,
    # שדה AssetName) - לא ניחוש: בזן=בתי זיקוק לנפט, ברס=הבורסה עצמה (!),
    # פנק=פניקס (אותה חברה כמו "פניקס" ב-HEBREW_NAME_TICKER, קוד-מעו"ף שונה).
    "בזן": "ORL.TA",
    "ברס": "TASE.TA",
    "פנק": "PHOE.TA",
    # אופציות מדד מעו"ף: "C004170M607-35ת" = call ת"א 35, מימוש 4170, פקיעה 07/2026.
    # אומת מול הנתונים: מחיר האופציה בדוח (באגורות) = פרמיית בלק-שולס על ת"א 35 × ₪50
    # לנקודה (48.8-49.1 בפועל), מנפיק "מסלקת מעו"ף", מדינת חשיפה ישראל. הגרסה
    # "תC004100M607-35" (ת' מובילה, בלי ת' בסוף) היא אותו נייר אצל מגישים אחרים.
    "35ת": "TA35", "35": "TA35",
    "125ת": "TA125", "125": "TA125",
    "90ת": "TA90", "90": "TA90",
}

# מכפיל חוזה (₪ לנקודת מדד) - "ערך נקוב (יחידות)" באופציות מעו"ף הוא מספר חוזים,
# לא יחידות נכס בסיס (שווי הוגן = יחידות × מחיר חוזה). לשאר הנכסים: 1.
CONTRACT_MULTIPLIER = {"TA35": 50.0, "TA125": 50.0, "TA90": 50.0,
                       # ניקיי 225 ב-OSE: ¥1,000 לנקודה; אופציות על חוזי E-mini - מכפיל החוזה
                       "NKY": 1000.0, "ES_FO": 50.0, "NQ_FO": 20.0, "RTY_FO": 50.0, "YM_FO": 5.0}
# אופציה על מניה בודדת במעו"ף (קוד "P028000M607-כלל"): שער האופציה בדוח הוא לחוזה, וגודל החוזה משתנה לפי
# מניה - כלל 100 מניות (פוט 280 כשהמניה ב-228.4: 514,700 אג' = (280-228.4) x 100), בזק 1,000 (פוט 8.00
# כשהמניה ב-7.027: 96,500 אג'). נלמד מהנתונים (derivatives_exposure._maof_contract_sizes); 100 כשאין שורה
# אמינה למניה. אופציה לא סחירה ("CALL001 לאומי") מדווחת ביחידות של מניות - בלי מכפיל.
MAOF_STOCK_OPTION_SHARES = 100.0

_CALL_WORD = re.compile(r"\bCALL", re.IGNORECASE)
_PUT_WORD = re.compile(r"\bPUT", re.IGNORECASE)
_CP_LETTER = re.compile(r"(?:^(?:ת|tl|TL|b|B)?|\s)([CP])\s?\d|\d\s?([CPcp])(?:\s|$)")


def parse_hebrew_company_name(name: str) -> str | None:
    for heb in _HEBREW_NAMES_BY_LEN:
        if heb in name:
            return HEBREW_NAME_TICKER[heb]
    return None


def is_call_option(name: str) -> bool | None:
    """True=call, False=put, None=לא ניתן לקבוע (משאיר לא-ממופה)."""
    m = PATTERN_FO.match(name.strip())
    if m:
        return m.group(2).upper() == "C"
    if _CALL_WORD.search(name):
        return True
    if _PUT_WORD.search(name):
        return False
    m = _CP_LETTER.search(name)
    if m:
        letter = (m.group(1) or m.group(2)).upper()
        return letter == "C"
    return None


def parse_strike(name: str) -> float | None:
    """מחיר מימוש מהשם, לאופציות מעו"ף ("C004160M607-35ת" -> 4160, "C 4300 APR" -> 4300)."""
    name = str(name or "").strip()
    m = _MAOF_STRIKE.match(name) or PATTERN_G.match(name)
    if not m:
        return None
    try:
        return float(m.group(1) if m.re is _MAOF_STRIKE else m.group(2))
    except ValueError:
        return None


def parse_maof_expiry_month(name: str, near_year: int) -> tuple[int, int] | None:
    """(שנה, חודש) מקוד מעו"ף ("C004160M607-35ת" -> (2026, 7)); ספרת השנה מתורגמת
    לשנה הקרובה ביותר ל-near_year (שנת הדוח)."""
    m = _MAOF_EXPIRY.match(str(name or "").strip())
    if not m:
        return None
    digit, month = int(m.group(1)), int(m.group(2))
    if not 1 <= month <= 12:
        return None
    year = min((y for y in range(near_year - 5, near_year + 6) if y % 10 == digit), key=lambda y: abs(y - near_year))
    return year, month


def parse_underlying(name: str) -> tuple[str | None, str | None]:
    """(טיקר, שם-הדפוס) או (None, None) אם לא זוהה. רק דפוסי-טיקר לטיניים
    נבדקים ישירות - מחרוזת עם תוכן עברי עוברת לשכבת שמות-חברה/מעו"ף
    הנפרדת (בכוונה, כדי לשמור על חד-משמעיות)."""
    name = name.strip()
    if re.search(r"[֐-׿]", name) and not PATTERN_C.match(name):
        ticker = parse_hebrew_company_name(name)
        if ticker:
            return ticker, "H_hebrew_company_name"
        return None, None  # שם עברי לא-מאומת - נשאר לא-ממופה, לא ניחוש
    if PATTERN_G.match(name):
        return "TA35", "G_maof_index_month"
    if PATTERN_FO.match(name) or PATTERN_FO_NAME.search(name):
        return FUTURES_OPTION, "FO_emini_option"
    m = PATTERN_IT.match(name)
    if m:
        return m.group(1) + ".TA", "IT_tase_stock"
    if PATTERN_NKY.match(name):
        return "NKY", "NKY_ose"
    for pattern, label, group_upper in (
        (PATTERN_A3, "A3_ticker_dash_us_date", False),
        (PATTERN_A, "A_us_slash_date", False),
        (PATTERN_B, "B_us_on_ticker", True),
        (PATTERN_C, "C_tase_maof_code", False),
        (PATTERN_D1, "D1_ticker_call_put", True),
        (PATTERN_D2, "D2_call_put_ticker", True),
        (PATTERN_E, "E_ticker_cp_strike", False),
        (PATTERN_F, "F_ticker_cp_glued", False),
    ):
        m = pattern.match(name) if pattern is not PATTERN_B else pattern.search(name)
        if not m:
            continue
        ticker = m.group(1).strip()
        if pattern is PATTERN_C:
            # מדד: ה-ת' לפני או אחרי המספר ("35ת" / "ת35" - C004280M604-ת35 ב-512267592_gm_0126)
            bare = ticker.replace("ת", "")
            resolved = MAOF_ABBREV_TICKER.get(ticker) or (MAOF_ABBREV_TICKER.get(bare) if bare.isdigit() else None)
            return (resolved, label) if resolved else (None, None)
        if group_upper:
            ticker = ticker.upper()
        if ticker.upper() in _AMBIGUOUS_SHORT_CODES:
            return None, None  # קוד לא-חד-משמעי ידוע - לא ממפים, לא מנחשים
        return ticker, label
    return None, None
