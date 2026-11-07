"""חשיפה אמיתית לנגזרים: תיקון לבאג לפיו "שיעור מסך נכסי ההשקעה" שמדווח
בגיליונות "חוזים עתידיים" ו"לא סחיר נגזרים אחרים" (עסקאות החלף/פורוורד)
משקף רק את השווי ההוגן של המכשיר (מרווח/רווח-הפסד שוטף) - לא את החשיפה
הכלכלית שהוא יוצר. לחוזה עתידי אין עלות רכישה (leverage מובנה): השווי ההוגן
הוא רק הרווח/הפסד שנצבר, בעוד שהחוזה בפועל שולט בנכס בסיס ששווה פי כמה
וכמה. אותו הדבר לעסקת פורוורד/סוואפ: השווי ההוגן נטו הוא ההפרש הקטן בין
שתי הרגליים, לא הסכום (הנקוב) שכל רגל שלה חושפת.

מקור: לא חלק מ-Autopilot_Section1.m - הרחבה חדשה, לפי הנחיית המשתמש
("הנתונים הם שיעור מנכסים, לא חשיפה - בפרט בחוזים עתידיים ועסקאות החלף").

אישוש רגולטורי (לא רק היסק אמפירי): החוזר המאוחד, שער 5 חלק 4 פרק 3,
נספח 5.4.3.2 חלק ג' - "רשימת נכסים ברמת הנכס הבודד", סעיף 4.22 "לא סחיר
נגזרים אחרים", קובע במפורש שהעמודות "מספר נייר ערך", "מטבע", "ערך נקוב",
"שער", "שווי הוגן", "שיעור מנכסי אפיק ההשקעה" ו"שיעור מסך נכסי ההשקעה"
מדווחות "עבור כל רגל בנפרד" - כלומר "שיעור מסך נכסי ההשקעה" הוא באמת
לפי-רגל (לא לפי-עסקה), ו"ערך נקוב" מוגדר שם (בסעיף ההגדרות הכללי) כ"מספר
היחידות" (לא סכום נקוב במטבע) - בדיוק ההנחות שהקוד למטה בונה עליהן.
נספח 5.4.3.5 - "אופן חישוב חשיפות בדוחות חודשיים" - קובע כעיקרון כללי
לחישוב חשיפה בנגזרים ש"חישוב החשיפה יעשה... על פי... אקוויוולנט של נכס
הבסיס בחוזה" (ערך נקוב × שער נכס הבסיס), לא לפי השווי ההוגן המדווח - מאשש
את העיקרון המרכזי של המודול הזה (לא רק ניחוש סביר).

שיטה
----
1. שווי כולל נכסי מסלול (באלפי ש"ח): לא מדווח במפורש בגיליונות הפרטניים,
   אבל ניתן לגזור אותו מהיחס שמגדיר את "שיעור מסך נכסי ההשקעה" בכל שורה
   בכל גיליון (כולל נגזרים): pct = שווי_הוגן / שווי_כולל. לכל מסלול
   לוקחים את שווי_הוגן/pct מהשורה עם |שווי הוגן| הגדול ביותר (יציבה
   נומרית יותר משורות עם pct זעיר).

2. חוזים עתידיים: החשיפה הכלכלית = ערך נקוב (יחידות, עם סימן - קניה/מכירה)
   כפול שער נייר הערך (מחיר/רמת מדד) כפול שער חליפין. זו בדיוק אותה נוסחה
   ששווי מניה/אג"ח בדוחות האלה מחושב לפיה (ערך נקוב × שער [× שער חליפין]),
   רק שעבור חוזה עתידי היא נותנת את השווי שהחוזה *שולט* בו (notional) -
   לא את "השווי ההוגן" המדווח (מרג'ין+רווח/הפסד, קטן בהרבה כמעט תמיד).
   מגבלה מתועדת: אין בדוח "מכפיל חוזה" (למשל $50/נקודה ב-ES future) - אם
   "ערך נקוב" הוא מספר החוזים הגולמי בלי הכפלה במכפיל, החשיפה בפועל
   תת-מוערכת. אין בדוח, ואין במקור אחר בריפו, דרך לאמת מכפיל per-instrument.

   שתי תקלות עקביות נוספות שנמצאו בבדיקה בפועל על כל הארכיון (לא הודעה
   תיאורטית - כל אחת אומתה בנתונים אמיתיים):
   - JPY: חלק מהמגישים רושמים "שער חליפין" ליין לפי מוסכמת "יחס ל-100"
     (כמו שער בנק ישראל) במקום שער ליחידה - לא עקבי אפילו בתוך אותו מגיש
     (רוב השורות ~0.018, חלקן ~1.83 - פי 100 בדיוק). מזוהה ומתוקן לפי סף
     (שער אמיתי ליין תמיד נמוך בהרבה מ-1).
   - "התחייבות"-Index (רגל מימון סינתטית, למשל "09/2026 JPM ESU6 Index
     התחייבות"): "שער נייר הערך" קבוע בדיוק על 100 - מוסכמת ערך-נקוב-100
     (כמו אג"ח), לא רמת מדד גולמית. יחידות בסדר גודל של מיליונים עם המוסכמה
     הרגילה (יחידות × 100 × שער) מייצרות חשיפה מנופחת פי 100 - מזוהות לפי
     שער == 100.0 בדיוק ומטופלות כמו אג"ח (יחידות/100 × שער, לא יחידות×שער).

3. עסקאות החלף/פורוורד ("לא סחיר נגזרים אחרים"): כל עסקה מדווחת בשתי
   רגליים, כל אחת עם "ערך נקוב" ו"שער חליפין" משלה. החשיפה = ממוצע הערך
   המוחלט (בש"ח) של שתי הרגליים - בד"כ קרובות זו לזו (אותה עסקה, שתי
   יחידות מדידה); הממוצע מנטרל סטיות קטנות מתנודות שער/ריבית מאז שהעסקה
   ננעלה.

4. התוצאה מיועדת *להחליף* (לא להצטרף ל-) שתי הקטגוריות האלה בפלט של
   category_pct.build_category_pct - שאר הקטגוריות (מזומן, אג"ח, מניות,
   קרנות...) כבר משקפות שווי שוק אמיתי, אין בהן את הבאג.
"""

import math
from collections import Counter, defaultdict
import re
import statistics
from datetime import date, datetime

from .excel_io import to_ratio
from .sheet_source import PCT_COL
from .option_delta_pricing import quote_scale, resolve_option_delta, resolve_option_value
from .option_ticker_parse import (CONTRACT_MULTIPLIER, FUTURES_OPTION, MAOF_STOCK_OPTION_SHARES, is_call_option, parse_maof_expiry_month, parse_strike,
                                  parse_underlying)
from .futures_notional import FuturesResolver, build_rows as build_futures_rows
from .stock_quote import stock_quote
from .swap_index_pricing import (
    has_price_source, parse_deal_date, price_as_of as index_price_as_of, proxy_return, resolve_current_price,
)

FAIR_VALUE_COL = 'שווי הוגן (באלפי ש"ח)'
SWAP_NET_FAIR_VALUE_COL = 'שווי הוגן (נטו באלפי ש"ח)'

# תקרת סבירות לשורה בודדת: חשיפה נוציונלית שמשתמעת ליותר מ-300% משווי המסלול
# כולו ממכשיר נגזר *יחיד* אינה סבירה עבור מסלול פנסיוני מפוזר - ונצפה בפועל
# (למשל אג"ח סינתטית עם "ערך נקוב" במוסכמת שווי-נקוב-100, לא מספר חוזים גולמי,
# שנופלת על אותו שם עמודה כמו חוזה CME רגיל). בשורה כזו לא ניתן לסמוך על
# הנוסחה (מוסכמת היחידות/מחיר של השורה הזו כנראה שונה) - נופלים חזרה לערך
# שהדוח עצמו מדווח (שווי הוגן/שווי כולל) לשורה הספציפית הזו בלבד, כפי שהיה
# לפני התיקון - עדיף על תוצאה מנופחת שאי אפשר לסמוך עליה.
SANITY_CAP = 3.0

# תקרת מנוף לשורת swap: יחס נוציונל/שווי-הוגן-נטו מעל זה מסמן קנה מידה שגוי
# של "שער נכס הבסיס" (ר' _swap_exposure). חוזים עתידיים כבר לא משתמשים בה -
# הנוציונל שלהם לא נשען על המחיר המדווח (ר' futures_notional).
LEVERAGE_CAP = 120.0

FUTURES_CATEGORY = "חוזים עתידיים"
SWAP_CATEGORY = "לא סחיר נגזרים אחרים"
OPTIONS_LISTED_CATEGORY = "אופציות"
OPTIONS_OTC_CATEGORY = "לא סחיר אופציות"
OPTIONS_CATEGORIES = (OPTIONS_LISTED_CATEGORY, OPTIONS_OTC_CATEGORY)
DERIVATIVE_CATEGORIES = (FUTURES_CATEGORY, SWAP_CATEGORY, *OPTIONS_CATEGORIES)

FUT_UNITS_COL = "ערך נקוב (יחידות)"
FUT_FX_COL = "שער חליפין"
FUT_PRICE_COL = "שער נייר הערך"
FUT_CURRENCY_COL = "מטבע פעילות"
FUT_TICKER_COL = "מספר נייר ערך"
FUT_UNDERLYING_COL = "נכס בסיס"
_FUT_COLS = {"units": FUT_UNITS_COL, "price": FUT_PRICE_COL,
             "ticker": FUT_TICKER_COL, "currency": FUT_CURRENCY_COL}

# "נכס בסיס"/"סוג הנכס" (חוזים/סוואפים/אופציות בהתאמה) - אותו ערך מדויק
# בשלושת הגיליונות, נבדק בפועל מול דוח אמיתי (512065202_gm_0226.xlsx).
# משמש לבניית "אזור חשיפה למניות" בדשבורד (ר' main.py) - לבודד את החלק
# שמקורו בנכס-בסיס מניות/מדדי-מניות בלבד מתוך כל קטגוריית נגזר.
EQUITY_UNDERLYING = "מניות לרבות מדדי מניות"

# עמודות הפלט הנוספות ("אזור חשיפה למניות") - לא מחליפות את הקטגוריות
# הקיימות (FUTURES_CATEGORY/SWAP_CATEGORY/OPTIONS_*), רק מוסיפות פילוח
# לפי נכס-בסיס=מניות בלבד, לצורך תצוגה בדשבורד.
FUTURES_EQUITY_COLUMN = "חוזים עתידיים - מניות"
OPTIONS_EQUITY_COLUMN = "אופציות - מניות"

SWAP_LEGS = (
    {"units": "ערך נקוב (רגל 1)", "fx": "שער חליפין (רגל 1)", "currency": "מטבע פעילות (רגל 1)",
     "fair_value": "שווי הוגן במטבע הנסחר (רגל 1)"},
    {"units": "ערך נקוב (רגל 2)", "fx": "שער חליפין (רגל 2)", "currency": "מטבע פעילות (רגל 2)",
     "fair_value": "שווי הוגן במטבע הנסחר (רגל 2)"},
)
SWAP_UNDERLYING_PRICE_COL = "שער נכס הבסיס במועד ההתקשרות בעסקה"
SWAP_TICKER_COL = "טיקר"
SWAP_ASSET_TYPE_COL = "סוג הנכס"
SWAP_EQUITY_ASSET_TYPE = "מניות לרבות מדדי מניות"
# סוואפ על תעודת סל אמריקאית ("LQD US", "HYG US Equity"): הדוח מסווג "מניות לרבות מדדי מניות" גם כשהקרן
# היא קרן אג"ח (LQD - אג"ח קונצרני, HYG - תשואה גבוהה). שבר המניות של הקרן מ-SEC N-PORT (eqTotalPct);
# קרן שרובה לא מניות - הסוואפ אינו חשיפה למניות
_US_ETF_SWAP_TICKER = re.compile(r"^([A-Z]{1,5})\s+U[SNWQPARFV](?:\s+EQUITY)?$")
_ETF_EQUITY_BY_SYMBOL: dict[str, float] | None = None


def _etf_equity_by_symbol() -> dict[str, float]:
    global _ETF_EQUITY_BY_SYMBOL
    if _ETF_EQUITY_BY_SYMBOL is None:
        try:
            from .foreign_etf_reference import SEC_NO_DATA, fetch_sec_etf_exposure
            _ETF_EQUITY_BY_SYMBOL = {
                str(x["symbol"]).strip().upper(): (x.get("eqTotalPct") or 0.0) / 100
                for x in fetch_sec_etf_exposure() if x.get("symbol") and x.get("assetClass") != SEC_NO_DATA}
        except (Exception, SystemExit) as e:  # בלי PAT / רשת - כמו קודם (לפי סוג הנכס בדוח)
            print(f"[swaps] שברי מניות של תעודות סל (SEC) לא זמינים: {e}")
            _ETF_EQUITY_BY_SYMBOL = {}
    return _ETF_EQUITY_BY_SYMBOL


def swap_on_bond_etf(row: dict) -> bool:
    """סוואפ שנכס הבסיס שלו תעודת סל אמריקאית שרובה לא מניות (SEC N-PORT)."""
    m = _US_ETF_SWAP_TICKER.match(re.sub(r"\s+", " ", str(row.get(SWAP_TICKER_COL) or "")).strip().upper())
    if not m:
        return False
    frac = _etf_equity_by_symbol().get(m.group(1))
    return frac is not None and frac < 0.5
def is_equity_swap(row: dict) -> bool:
    """סוואפ על מניות: "סוג הנכס" = מניות, או "אחר" / ריק על טיקר של מדד מניות שיש לו מקור
    מחיר (INDICES / תעודת סל עוקבת - כולם מדדי מניות). 512065202_7867 ב-0425: IXYTR / IXCTR /
    MVSMHTR חלקן "מניות" וחלקן "אחר" באותו דוח. סוואפ על תעודת סל של אג"ח - לא."""
    if swap_on_bond_etf(row):
        return False
    kind = row.get(SWAP_ASSET_TYPE_COL)
    if kind == SWAP_EQUITY_ASSET_TYPE:
        return True
    return str(kind or "").strip() in ("", "אחר") and has_price_source(row.get(SWAP_TICKER_COL))


SWAP_MAIN_TYPE_COL = "מאפיין עיקרי"  # "Unfunded Swap"/"Funded Total Return/Equity Swap"/... - נבדק בפועל
SWAP_LABEL_COL = SWAP_MAIN_TYPE_COL
FUNDED_SWAP_CATEGORY = "החלף עם מימון (Funded)"
UNFUNDED_SWAP_CATEGORY = "החלף בלי מימון (Unfunded)"

# "Funded" מול "Unfunded" (מאפיין עיקרי) נראים כשני מבנים כלכליים שונים
# לגמרי: ב-"Unfunded Swap" (512065202 - הפריט שאומת במקור ב-46114a8), רגל 1
# היא כמות *יחידות גולמית* של נכס הבסיס (צריכה הכפלה בשער כדי להיות
# ברת-השוואה לרגל 2). ב-"Funded Total Return/Equity Swap" (513611509,
# Yelin Lapidot S&P 500 tracker), רגל 1 היא כבר נוציונל במטבע (בדיוק כמו
# רגל 2, לפני סימן) - בלי צורך בהכפלה כלל.
#
# אבל (תיקון-משנה חשוב, נמצא בבדיקה נוספת על 513173393/אלטשולר שחם):
# התווית "מאפיין עיקרי" לבדה *אינה מספיק אמינה* כדי להכריע איזו משתי
# הפרשנויות נכונה - "Unfunded Total Return/Equity Swap" (התווית הנפוצה
# ביותר בארכיון, 11,218 שורות!) יכולה להיות "רגל 1 כבר נוציונל" בדיוק
# כמו Funded אצל מגיש מסוים, בזמן שאצל מגישים אחרים תחת אותה תווית בדיוק
# רגל 1 באמת יחידות גולמיות (התבנית המקורית שאומתה). לכן ההחלטה בפועל
# היא לא לפי is_funded (התווית) אלא לפי used_priced - ההשוואה עצמה בין
# הפרשנויות מול רגל 2, ברמת השורה הבודדת (ר' קוד למטה) - is_funded נשאר
# רק לפילוח הדיאגנוסטי (funded_sums/unfunded_sums), לא לקביעת קנה-המידה.
#
# שני באגים נובעים מהחלת ההנחה "רגל 1 = יחידות גולמיות" על שורה שבה
# used_priced=False בפועל (רגל 1 כבר נוציונל):
# 1. leg1_live (תמחור-חי): מכפיל רגל 1 *שוב* במחיר המדד החי - הכפלה כפולה
#    שמייצרת מספר דמיוני (נבדק בפועל: ~1.5 מיליארד ש"ח על שורת swap עם
#    נוציונל אמיתי ~100 מיליון - פי ~15,000), שנופל אוטומטית ב-SANITY_CAP
#    חזרה ל-row_pct הזעיר.
# 2. LEVERAGE_CAP (יחס נוציונל/שווי-הוגן-נטו): רלוונטי רק כש-used_priced
#    (זו הדרך היחידה שקנה-המידה של "שער נכס הבסיס" נכנס לחישוב בכלל).
#    כש-used_priced=False, שווי הוגן קטן/כמעט-אפס ביחס לנוציונל הוא
#    לגיטימי (Reset תקופתי, או Unfunded-בלי-Reset שנמצא בפועל שגם יכול
#    לעבור דרך fv≈0) - לא סימן לקנה-מידה שגוי, כי הנוציונל כבר אומת ישירות
#    מול רגל 2 (ההשוואה למעלה). נבדק בפועל (513173393_14865): 5 שורות
#    used_priced=False, יחס נוציונל/fv נע 10.7x עד 1893.6x (כולן legitimate) -
#    נוציונל אמיתי מצטבר 41.2% מהמסלול, מחושב בפועל (לפני התיקון) רק 1.11%.
_FUNDED_SWAP_PREFIX = "funded"


def _is_funded_swap(main_type) -> bool:
    return str(main_type or "").strip().lower().startswith(_FUNDED_SWAP_PREFIX)
# שם העמודה עצמו (לפי החוזר: שער החליפין/נכס הבסיס לנגזרים לא סחירים מוצג
# "נכון למועד ההתקשרות בעסקה") מאשר שזהו מחיר נכס הבסיס *בפתיחת העסקה*, לא
# מחיר שוק עדכני - זה בדיוק ההסבר לכך שרגל1×מחיר זה שווה לרגל2 (שתי הרגליים
# נעולות לאותו נוציונל מקורי). מגבלה ידועה: לעסקת סוואפ ישנה שנפתחה הרבה
# לפני תאריך הדוח, החשיפה הכלכלית ה"חיה" (הנגזרת ממחיר השוק הנוכחי) עשויה
# לסטות מהנוציונל המקורי הזה ככל שהשוק זז מאז ההתקשרות - אין בדוח עמודת
# "מחיר נוכחי" נפרדת לרגל 1 כדי לתקן זאת.

# JPY: נמצא בבדיקה שחלק מהמגישים רושמים את שער החליפין לפי מוסכמת "יחס ל-100
# יין" (כמו שער בנק ישראל ליין) במקום שער ליחידה - אותו קובץ/מגיש לא עקבי:
# ברוב השורות 0.018-ish (נכון), בחלקן 1.83-ish (פי 100, שגוי). השער האמיתי
# ליין תמיד נמוך בהרבה מ-1 - כל ערך מעל הסף הוא ודאי המוסכמה השגויה.
JPY_100_THRESHOLD = 0.5

# כל מטבע זר (לא ILS) עם שער חליפין קרוב ל-1.0 הוא בהכרח פלייסהולדר שגוי -
# אין מטבע שנסחר קרוב ל-1:1 מול ש"ח (נמצא בפועל: USD/EUR ברגל 1 של חלק
# מהמגישים, כשהשער האמיתי מדווח בעמודה אחרת - "שער הנגזר במועד ההתקשרות
# בעסקה" - שלא תמיד קיימת/עקבית מספיק כדי לסמוך עליה). מטפלים בזה לא
# בתיקון (אין ערך אמין להציב), אלא בפסילת הרגל - ממוצעים רק את הרגליים
# התקינות, ובלי אף רגל תקינה נופלים לשווי ההוגן הנטו כמו כל מקרה גבולי.
FOREIGN_FX_PLACEHOLDER_TOL = 0.01

# אופציות ("אופציות"/"לא סחיר אופציות"): לפי הרגולטור (אושר בבדיקה, לא
# הנחה - ר' חיפוש רשת 9.28.2026), החשיפה מחושבת לפי מודל בלק-שולס עם דלתא -
# לא לפי units×מחיר פשוט כמו חוזים עתידיים (ל"שער נייר הערך" באופציה יש
# משמעות אחרת: זו פרמיית האופציה עצמה, לא מחיר נכס הבסיס - אומת בפועל:
# units×שער/100×fx ≈ שווי הוגן בדיוק, מוסכמת אגורות).
# דלתא מחושבת ב-option_delta_pricing.py (תנודתיות ריאליזד כקירוב ל-IV,
# ר' אזהרה שם). טיקר נכס-הבסיס מזוהה מ-"שם נייר ערך" (option_ticker_parse,
# אין עמודת טיקר נפרדת כמו בסוואפים) - כשלא מזוהה, נופלים לשווי-הוגן.
OPT_NAME_COL = "שם נייר ערך"
OPT_UNDERLYING_COL = "נכס בסיס"
OPT_EQUITY_UNDERLYING = "מניות לרבות מדדי מניות"
# ערכי "נכס בסיס" שאינם מניות במפורש. ערך אחר / ריק / חופשי ("TEL AVIV STOCK EXCHANGE
# 35 IND", "ריק במקור") - מניות רק אם נכס הבסיס זוהה משם האופציה (ר' is_equity_option)
OPT_NON_EQUITY_UNDERLYINGS = {'ריבית ואג"ח', 'מט"ח', "סחורות", "מדדי סחורות"}
OPT_STRIKE_COL = "שער מימוש"
OPT_EXPIRY_COL = "תאריך פקיעה"
OPT_UNITS_COL = "ערך נקוב (יחידות)"
OPT_FX_COL = "שער חליפין"
OPT_CURRENCY_COL = "מטבע פעילות"
OPT_PRICE_COL = "שער נייר הערך"  # במעו"ף - לחוזה, באגורות


def _normalize_fx(currency, fx: float | None) -> float | None:
    if fx is None:
        return None
    if currency == "JPY" and fx > JPY_100_THRESHOLD:
        return fx / 100
    if currency and currency != "ILS" and abs(fx - 1.0) < FOREIGN_FX_PLACEHOLDER_TOL:
        return None
    return fx


FX_CONSENSUS_TOL = 0.2


def _consensus_fx(currency, fx_row: float | None, fx_market: float | None) -> float | None:
    """שער השורה, אלא אם הוא רחוק מהשער החציוני של אותו מטבע ליום הדוח (כל הגופים) ביותר
    מ-20% - אז החציוני (512267592_gc_0325: 0.022332 בכל שורות החוזים, גם בדולר ובאירו)."""
    fx = _normalize_fx(currency, fx_row)
    if fx_market and (fx is None or abs(fx / fx_market - 1) > FX_CONSENSUS_TOL):
        return fx_market
    return fx


def _num(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip().replace(",", ""))
    except ValueError:
        return None


def total_assets_by_key(source: list[dict]) -> dict[str, float]:
    """מפתח -> שווי כולל נכסי מסלול (באלפי ש"ח), נגזר מ-שווי הוגן/שיעור מסך
    נכסי ההשקעה של השורה עם |שווי הוגן| הגדול ביותר לאותו מסלול."""
    best: dict[str, tuple[float, float]] = {}
    for rec in source:
        if rec["מידע"] != "מידע":
            continue
        for row in rec["Clean"]:
            key = row.get("מפתח")
            if key is None:
                continue
            fv = _num(row.get(FAIR_VALUE_COL))
            pct = to_ratio(row.get(PCT_COL))
            if fv is None or not pct:
                continue
            total = fv / pct
            cur = best.get(key)
            if cur is None or abs(fv) > cur[0]:
                best[key] = (abs(fv), total)
    return {k: v[1] for k, v in best.items()}


FV_OVER_NOTIONAL = 1.5


def _futures_exposure(
    source: list[dict], total_assets: dict[str, float], detail: list | None = None
) -> tuple[dict[str, float], dict[str, float]]:
    """מחזיר (sums, equity_sums) - equity_sums הוא תת-קבוצה של sums, רק שורות
    עם נכס בסיס = מניות/מדדי-מניות (FUT_UNDERLYING_COL), לאזור החשיפה למניות.

    נוציונל = חוזים × רמת-המדד × מכפיל-החוזה × שער חליפין (ר' futures_notional:
    שדה "שער נייר הערך" מדווח בכמה מוסכמות שונות לפי גוף, ולכן אינו משמש
    כמחיר). שורה שלא זוהתה (שורש/מכפיל/רמה לא ידועים) נספרת לפי השווי ההוגן
    המדווח שלה - הערכת חסר מכוונת, במקום ניחוש קנה מידה של המחיר.

    הסיווג למניות לפי החוזה שזוהה (למשל UXY תמיד אג"ח, גם כשמסווג "מניות"
    בדוח); רק שורה שלא זוהתה נשענת על "נכס בסיס" שבדוח.

    תקרת-מסלול: סכום השורות למסלול מעל SANITY_CAP -> נפילה לסכום ה-PCT_COL
    המדווח (כמו ב-swap)."""
    pairs = build_futures_rows(source, FUTURES_CATEGORY, _FUT_COLS)
    fx_now = _current_fx_rates(source)
    rec_month = {id(r): rec.get("ReportMonth") for rec in source if rec["Category"] == FUTURES_CATEGORY
                 for r in rec["Clean"]}
    resolver = FuturesResolver([fr for _, fr in pairs], index_price_as_of)
    sums: dict[str, float] = {}
    equity_sums: dict[str, float] = {}
    row_pct_sums: dict[str, float] = {}
    equity_row_pct_sums: dict[str, float] = {}
    for row, fr in pairs:
        key = row.get("מפתח")
        total = total_assets.get(key)
        if not total:
            continue
        is_equity = resolver.is_equity(fr)
        if is_equity is None:
            is_equity = row.get(FUT_UNDERLYING_COL) == EQUITY_UNDERLYING
        row_pct = to_ratio(row.get(PCT_COL)) or 0.0
        row_pct_sums[key] = row_pct_sums.get(key, 0.0) + row_pct
        if is_equity:
            equity_row_pct_sums[key] = equity_row_pct_sums.get(key, 0.0) + row_pct
        notional = resolver.notional(fr)
        fx = 1.0 if fr.ccy == "ILS" else _consensus_fx(fr.ccy, _num(row.get(FUT_FX_COL)), fx_now.get((fr.ccy, rec_month.get(id(row)))))
        if notional is not None and fx is not None:
            line_ratio = notional * fx / 1000 / total
            # השווי ההוגן של חוזה עתידי הוא הנוציונל המלא או רווח/הפסד קטן ממנו בהרבה - לעולם לא גדול
            # ממנו. נוציונל מחושב קטן משמעותית מהשווי המדווח = רמה של מדד אחר (עגור "MSCI World Index
            # Jun26": שויך מהשם ל-RVP - World price ~4,000 - כשהחוזה הוא World NTR ~13,830; 11.9 מול
            # 41.1 מיליון ש"ח מדווחים) -> השווי המדווח. הראל (רווח/הפסד 1.8 מול נוציונל 164 מיליון) לא נוגע.
            # רק בשורה ששורשה נלמד מהשם (by_name - המחיר שלה לא התאים לרמה): כלל מדווח שווי גדול
            # מהנוציונל המחושב גם בחוזים שזוהו מהקוד, שם הרמה נכונה
            if fr.by_name and abs(row_pct) > FV_OVER_NOTIONAL * abs(line_ratio):
                line_ratio = row_pct
        else:
            line_ratio = row_pct
        sums[key] = sums.get(key, 0.0) + line_ratio
        if is_equity:
            equity_sums[key] = equity_sums.get(key, 0.0) + line_ratio
        if detail is not None:
            detail.append({"key": key, "root": fr.root, "row": row, "ratio": line_ratio,
                           "row_pct": row_pct, "equity": is_equity})
    capped = {
        key: val if abs(val) <= SANITY_CAP else row_pct_sums.get(key, 0.0)
        for key, val in sums.items()
    }
    equity_capped = {
        key: val if abs(val) <= SANITY_CAP else equity_row_pct_sums.get(key, 0.0)
        for key, val in equity_sums.items()
    }
    return capped, equity_capped


def _current_fx_rates(source: list[dict]) -> dict[tuple, float]:
    """(מטבע, תאריך דוח) -> שער חליפין נוכחי, חציון על שורות החוזים העתידיים
    (שם "שער חליפין" הוא השער ליום הדוח). בסוואפ השער שברגל הוא לעתים שער
    יום ההתקשרות (למשל 3.749 לדולר בעסקה מ-11.2024 ב-514956465)."""
    rates: dict[tuple, list[float]] = {}
    for rec in source:
        if rec["Category"] != FUTURES_CATEGORY or rec["מידע"] != "מידע":
            continue
        for row in rec["Clean"]:
            ccy = row.get(FUT_CURRENCY_COL)
            fx = _normalize_fx(ccy, _num(row.get(FUT_FX_COL)))
            if ccy and ccy != "ILS" and fx:
                rates.setdefault((ccy, rec.get("ReportMonth")), []).append(fx)
    return {k: statistics.median(v) for k, v in rates.items()}


def _leg_market_values(row: dict, report_date, fx_now: dict[tuple, float]) -> list[float]:
    """שווי השוק של כל רגל (באלפי ש"ח, בערך מוחלט) מתוך "שווי הוגן במטבע הנסחר
    (רגל X)" - באלפי יחידות מטבע (אומת: שווי הוגן נטו = רגל1 + רגל2, כפול שער
    נוכחי). ריק אם הגוף לא מדווח שווי לרגליים (512065202 מדווח 0 בשתיהן)."""
    out = []
    for leg in SWAP_LEGS:
        value = _num(row.get(leg["fair_value"]))
        ccy = row.get(leg["currency"])
        if not value:
            continue
        fx = 1.0 if ccy == "ILS" else fx_now.get((ccy, report_date)) or _normalize_fx(ccy, _num(row.get(leg["fx"])))
        if fx:
            out.append(abs(value) * fx)
    return out


def _index_leg_value(row: dict, report_date, fx_now: dict[tuple, float],
                     live_value: float | None = None) -> float | None:
    """סוואפ מניות שרגל אחת בשקלים ורגל אחת במט"ח: רגל המט"ח היא רגל המדד (שווי
    נוכחי), רגל השקל היא המימון - הנוציונל בשער יום העסקה. ממוצע של השתיים מחמיץ
    את תנועת המדד והמט"ח מאז העסקה (513173393_13820: XNDX, רגל דולר 5,935 אלף = 19.2%,
    רגל שקל 15,471 אלף = 16.8%; קרנות 52.5% + סוואפים לפי רגל המדד = 100.2% מול 100.1%
    רשמי). גם כשהרגליים באותו מטבע: רגל ששוויה = יחידות × מחיר המדד ליום הדוח (live_value,
    עד 5%) היא רגל המדד (513026484_13264: SPTR, רגל 1 = 39,146 = 2,333.72 × מחיר המדד,
    רגל 2 = נוציונל המימון 39,810 מיום ה-Reset). None אם אין זוג כזה."""
    legs = []
    for leg in SWAP_LEGS:
        value, ccy = _num(row.get(leg["fair_value"])), row.get(leg["currency"])
        if value:
            legs.append((ccy, value, leg))
    if live_value:
        for ccy, value, leg in legs:
            fx = 1.0 if ccy == "ILS" else fx_now.get((ccy, report_date)) or _normalize_fx(ccy, _num(row.get(leg["fx"])))
            if fx and abs(abs(value) * fx / live_value - 1) <= 0.05:
                return abs(value) * fx
    if len(legs) != 2 or [c == "ILS" for c, _, _ in legs].count(True) != 1:
        return None
    ccy, value, leg = next(x for x in legs if x[0] != "ILS")
    fx = fx_now.get((ccy, report_date)) or _normalize_fx(ccy, _num(row.get(leg["fx"])))
    return abs(value) * fx if fx else None


# סוואפ מניות עם שווי רגליים: אם ממוצע הרגליים קטן מ-20% מיחידות × מחיר המדד העדכני,
# הרגליים הן שינוי שווי (MTM) ולא הנוציונל. יחידות × מחיר מתקבל רק עד 1.5 מנכסי המסלול
# (514956465_15249: יחידות 291,700 = פי 130 מהרגליים - שם הרגליים הן הנוציונל).
MTM_LEG_SHARE = 0.2
LIVE_SWAP_MAX_RATIO = 1.5


SWAP_DEAL_DATE_COL = "מועד ההתקשרות בעסקה"

# רגליים שקולות זו לזו (רגל המדד מול רגל המימון, עד 20% הפרש) הן הנוציונל עצמו, לא שינוי
# שווי - אז "ערך נקוב" שמתומחר פי LEGS_NOTIONAL_FACTOR ומעלה מהרגליים אינו יחידות מדד
# (514956465_12532 ב-0126: SPTR, 183,190 "יחידות", רגליים 19,632 / 19,246 אלף דולר = 107
# דולר ליחידה; יחידות × מחיר המדד = 137% מהמסלול). שינוי שווי (MTM) נראה אחרת: רגליים
# שונות מאוד זו מזו (514956465_9452: 354 / 1,930), ויחידות אמיתיות עם רגליים שקולות
# מתומחרות עד פי ~10 מהן (512237744_9898: 62.67 יחידות × 14,660 = רגל 2 של 918,813 דולר).
LEGS_CONSISTENT = 0.8
LEGS_NOTIONAL_FACTOR = 20.0


def _legs_are_notional(row: dict, legs_ratio: float, live_ratio: float) -> bool:
    raw = [abs(_num(row.get(f"שווי הוגן במטבע הנסחר (רגל {n})")) or 0.0) for n in (1, 2)]
    if not min(raw):
        return False
    return min(raw) / max(raw) >= LEGS_CONSISTENT and live_ratio >= LEGS_NOTIONAL_FACTOR * legs_ratio


# מחיר עסקה מגולגל שרחוק מחציון עוגני הגוף (מגולגלים אף הם) יותר מפי ANCHOR_TOL - התאריך שלו לא
# שייך למחיר: 512065202 מדווח לעתים מחיר איפוס עם מועד העסקה המקורי (7867 ב-0126: MVSMHTR 16,327.32
# "מ-23/06/2025", אותו מחיר כמו בעסקאות מ-12/2025; מגולגל 9 חודשים ב-SMH = 23,900 ו-25% מהמסלול,
# בחציון העוגנים ~16,000; רשמי: 6.96%+ -> 0.6%-). בגלגול תקין העוגנים מסכימים עד כדי סטיית תעודת הסל
ANCHOR_TOL = 1.3


def _direct_price(row: dict, report_date) -> float | None:
    """מחיר ליום הדוח ממקור ישיר: סדרת המדד ב-INDICES, או מחיר המניה (stock_quote, במטבע
    הבורסה שלה). None אם אין."""
    price, _ = resolve_current_price(row.get(SWAP_TICKER_COL), report_date)
    if price is not None:
        return price
    stock = stock_quote(row.get(SWAP_TICKER_COL))
    if stock and report_date:
        from .option_delta_pricing import price_as_of as single_price_as_of
        p = single_price_as_of(stock.symbol, report_date)
        if p:
            return p * stock.factor
    return None


def _current_index_price(row: dict, report_date) -> float | None:
    """מחיר המדד ליום הדוח: מקור ישיר (_direct_price), ואם אין - מחיר העסקה × תשואת תעודת
    הסל העוקבת מיום העסקה (swap_index_pricing.proxy_return)."""
    price = _direct_price(row, report_date)
    if price is not None:
        return price
    from .swap_deal_anchors import anchored_price
    deal_price = _num(row.get(SWAP_UNDERLYING_PRICE_COL))
    deal_date = parse_deal_date(row.get(SWAP_DEAL_DATE_COL))
    ratio = proxy_return(row.get(SWAP_TICKER_COL), deal_date, report_date) if deal_price and deal_price > 0 else None
    from_deal = deal_price * ratio if ratio else None
    # עוגן ממחירי העסקה של אותו גוף בכל הדוחות (swap_deal_anchors): כשאין מחיר עסקה בשורה, או
    # כשהוא רחוק מהעוגן (ANCHOR_TOL; 512065202_15352 ב-0425: NDWUIT "מחיר עסקה" 3.3059 = שער הדולר)
    anchored = anchored_price(str(row.get("מפתח") or "").split("_")[0], row.get(SWAP_TICKER_COL),
                              deal_date, report_date)
    if anchored and (from_deal is None or not 1 / ANCHOR_TOL <= from_deal / anchored <= ANCHOR_TOL):
        return anchored
    return from_deal


def _legs_reconcile(row: dict, report_date, fx_now: dict) -> bool:
    """שווי הרגליים (בסימן, בשקלים) מסתכם לשווי ההוגן נטו של השורה (עד 15% מהרגל הגדולה).
    כך בכל הגופים (אלפי שורות לגוף, 0126 ו-0226), חוץ משורות שבהן "שווי הרגל" הוא בעצם
    "ערך נקוב" / 1000 (512065202 ב-0126: 0.07 / 0.07- מול נטו 214.7-) - שם הרגליים אינן שווי."""
    vals = []
    for leg in SWAP_LEGS:
        v, ccy = _num(row.get(leg["fair_value"])), row.get(leg["currency"])
        fx = 1.0 if ccy == "ILS" else fx_now.get((ccy, report_date)) or _normalize_fx(ccy, _num(row.get(leg["fx"])))
        if v and fx:
            vals.append(v * fx)
    net = _num(row.get(SWAP_NET_FAIR_VALUE_COL))
    if net is None and len(vals) == 1:
        # רגל אחת בלבד, ונטו ריק: העתק של "ערך נקוב" / 1000 הוא מילוי (512065202_15352 ב-0425:
        # NDWUIT, 23,715.5 ש"ח -> 23.716, רגל הדולר "ריק במקור")
        v, u = next((_num(row.get(leg["fair_value"])), _num(row.get(leg["units"]))) for leg in SWAP_LEGS
                    if _num(row.get(leg["fair_value"])))
        return not (u and abs(abs(v) / (abs(u) / 1000) - 1) <= 0.0005)
    if len(vals) != 2:
        return True
    if net is None:
        # בלי נטו לבדיקה: רגליים שהן בדיוק "ערך נקוב" / 1000 בשתיהן הן מילוי, לא שווי
        # (512065202 ב-0325: IXCTR 21,422.806 / 6,479.978- -> 21.423 / 6.48-, נטו ריק)
        # רק ברגליים בשני מטבעות (שקל / מט"ח): באותו מטבע זה גם סוואפ קטן שה"ערך נקוב" שלו
        # הוא סכום בשקלים (513173393_13211 ב-0325: ת"א 90, 24,261.63- ש"ח, רגליים 24.35 / 24.37)
        # באותו מטבע רק העתק מדויק בשתי הרגליים (512065202_769 ב-0425: ת"א 125, 300 / 300-,
        # רגליים 0.3 / 0.3-; שם הסוואפ הקטן של 13211 הרגליים 24.353 / 24.371 - שווי אמיתי)
        ccys = {row.get(leg["currency"]) for leg in SWAP_LEGS}
        legs = [(_num(row.get(leg["fair_value"])), _num(row.get(leg["units"]))) for leg in SWAP_LEGS]
        tol = 0.005 if "ILS" in ccys and len(ccys) == 2 else 0.0005 if len(ccys) == 1 else None
        return not (tol is not None
                    and all(v and u and abs(abs(v) / (abs(u) / 1000) - 1) <= tol for v, u in legs))
    return abs(sum(vals) - net) <= max(0.15 * max(abs(x) for x in vals), 0.5)


def _ccy_to_ils(ccy: str | None, report_date, fx_now: dict) -> float | None:
    """שער מטבע לשקל ליום הדוח: מהחוזים העתידיים, ואם המטבע לא שם (דולר טייוואני) - דרך הדולר
    ושער המטבע לדולר מ-Yahoo ("TWD=X" = יחידות מטבע לדולר)."""
    if ccy == "ILS":
        return 1.0
    fx = fx_now.get((ccy, report_date))
    if fx or not ccy or not report_date:
        return fx
    usd = fx_now.get(("USD", report_date))
    if not usd:
        return None
    from .option_delta_pricing import price_as_of as single_price_as_of
    per_usd = single_price_as_of(f"{ccy}=X", report_date)
    return usd / per_usd if per_usd else None


_CCY_CODE = re.compile(r"^[A-Z]{3}$")
# טיקר סוואפ -> מטבע המדד (המטבע הלא-שקלי הנפוץ בשורות שלו), לרגל שהמטבע שלה "ריק במקור"
_TICKER_CCY: dict[str, str] = {}


def _ticker_currencies(source: list[dict]) -> dict[str, str]:
    votes: dict[str, Counter] = defaultdict(Counter)
    for rec in source:
        if rec["Category"] != SWAP_CATEGORY or rec["מידע"] != "מידע":
            continue
        for row in rec["Clean"]:
            t = str(row.get(SWAP_TICKER_COL) or "").strip().upper()
            for leg in SWAP_LEGS:
                c = str(row.get(leg["currency"]) or "").strip().upper()
                if t and _CCY_CODE.match(c) and c != "ILS":
                    votes[t][c] += 1
    return {t: c.most_common(1)[0][0] for t, c in votes.items()}


def _swap_ccys(row: dict) -> tuple[str | None, str | None]:
    """מטבעות שתי הרגליים; מטבע לא תקין ("ריק במקור") ברגל אחת לצד רגל שקלית - מטבע הטיקר
    בשאר השורות (512065202_15361 ב-0425: NDWUIT, רגל שקלית ורגל "ריק במקור" -> דולר)."""
    out = []
    for leg in SWAP_LEGS:
        c = str(row.get(leg["currency"]) or "").strip().upper()
        out.append(c if _CCY_CODE.match(c) else None)
    if out.count("ILS") == 1 and None in out:
        t = str(row.get(SWAP_TICKER_COL) or "").strip().upper()
        out[out.index(None)] = _TICKER_CCY.get(t)
    return out[0], out[1]


def _mirrored_units(row: dict, report_date, fx_now: dict) -> float | None:
    """"ערך נקוב" זהה בשתי הרגליים - באותו מטבע, או רגל שקלית ורגל במט"ח עד כדי השער (ש"ח =
    מט"ח × שער, עד 3%): זו כמות יחידות המדד (בשקלים), לא סכום (512065202_13246 ב-0126: SPTR,
    1,436.76 ש"ח / 453.95- דולר = 3.165; באותה עסקה ב-0226: 1,393.47 יחידות × מחיר המדד = 3.5%,
    כמו הרשמי. 512065202_769 ב-0126: ת"א 125, 300 / 300-, במחיר העסקה 764.6 אלף ש"ח). None
    אם אין תבנית כזו."""
    leg1_col, leg2_col = SWAP_LEGS
    ccy1, ccy2 = _swap_ccys(row)
    if ccy1 and ccy1 == ccy2:
        u1, u2 = _num(row.get(leg1_col["units"])), _num(row.get(leg2_col["units"]))
        if u1 and u2 is None:
            # רגל אחת עם "ערך נקוב" והשנייה ריקה (512065202_15361 ב-0126: NDWUIT, 1,650.39 / "ריק
            # במקור") - כמות; מחיר לא סביר (סכום ולא כמות) נפסל ב-LIVE_SWAP_MAX_RATIO
            return u1
        return u1 if u1 and u2 and abs(abs(u1 / u2) - 1) <= 0.001 else None
    if not ccy1 or not ccy2 or (ccy1 == "ILS") == (ccy2 == "ILS"):
        return None
    ils_leg, fx_leg = (leg1_col, leg2_col) if ccy1 == "ILS" else (leg2_col, leg1_col)
    u_ils, u_fx = _num(row.get(ils_leg["units"])), _num(row.get(fx_leg["units"]))
    if u_ils and u_fx is None:
        return u_ils  # רגל המט"ח בלי "ערך נקוב" ("ריק במקור") - הכמות ברגל השקלית
    if u_ils and u_fx and abs(abs(u_ils / u_fx) - 1) <= 0.001 and not _CCY_CODE.match(
            str(row.get(fx_leg["currency"]) or "").strip().upper()):
        return u_ils  # העתק של הכמות ברגל בלי מטבע (512065202_15350 ב-0425: NDWUIT 5,257.38 / 5,257.38)
    ccy = ccy2 if ccy1 == "ILS" else ccy1
    fx = fx_now.get((ccy, report_date)) or _normalize_fx(ccy, _num(row.get(fx_leg["fx"])))
    if not u_ils or not u_fx or not fx or abs(abs(u_ils / u_fx) / fx - 1) > 0.03:
        return None
    return u_ils


def _live_swap_ratio(row: dict, report_date, fx_now: dict, total: float) -> float | None:
    """|יחידות| × מחיר המדד ליום הדוח (swap_index_pricing, רק טיקר ממופה) × שער
    מטבע המדד / נכסי המסלול. None אם אין מחיר / יחידות, או שהתוצאה לא סבירה לשורה."""
    leg1_col, leg2_col = SWAP_LEGS
    # רק סדרת מדד ישירה - לא פרוקסי: כאן קנה המידה של היחידות לא מאומת מול רגל 2
    # (פרוקסי ב-512267592: יחידות בקנה מידה אחר -> 200%+ למסלול). ביחידות שמשתקפות בין
    # הרגליים (_mirrored_units) היחידות מאומתות - שם גם מחיר העסקה × תשואת תעודת הסל העוקבת
    mirrored = _mirrored_units(row, report_date, fx_now)
    price = (_current_index_price(row, report_date) if mirrored
             else resolve_current_price(row.get(SWAP_TICKER_COL), report_date)[0])
    if price is None:
        return None
    ccy1, ccy2 = _swap_ccys(row)
    ccy = ccy1 if ccy1 != "ILS" or not ccy2 else ccy2
    if mirrored and ccy == "ILS":
        # כמות יחידות של מדד במט"ח בשתי רגליים שקליות - מטבע המדד מהשורות האחרות של הטיקר
        # (512065202_15352 ב-0126: NDWUIT, 22,816.9 / 22,816.9 ש"ח - בלי שער הדולר 6% במקום 19%)
        ccy = _TICKER_CCY.get(str(row.get(SWAP_TICKER_COL) or "").strip().upper(), "ILS")
    stock = stock_quote(row.get(SWAP_TICKER_COL)) if mirrored else None
    if stock and stock.currency != "ILS":
        ccy = stock.currency  # מחיר מניה במטבע הבורסה שלה, לא במטבע הרגל (512065202 "2330 TT")
    units = mirrored or (_num(row.get(leg1_col["units"])) if ccy1 != "ILS" or not ccy2
                         else _num(row.get(leg2_col["units"])))
    if not units:
        return None
    # "ערך נקוב" שהוא כבר סכום במטבע (513611509_1038: 67,191.68 דולר, רגליים 66.8 / 67.2
    # אלף) - שווי רגל ≈ יחידות / 1000 - אינו יחידות מדד; לא מתמחרים אותו. כל הרגליים
    # המדווחות צריכות להתאים - רגל MTM קטנה יכולה ליפול במקרה ליד יחידות/1000
    # (514956465_12536: 17,955 יחידות SPTR, רגל 2 = 25.7 - שורה של 6.3% מהמסלול
    # נשארה בשווי הרגליים, 0.01%).
    leg_fvs = [_num(row.get(f"שווי הוגן במטבע הנסחר (רגל {n})")) for n in (1, 2)]
    leg_fvs = [v for v in leg_fvs if v]
    if not mirrored and leg_fvs and all(0.8 <= abs(v) / (abs(units) / 1000) <= 1.25 for v in leg_fvs):
        return None
    fx = 1.0 if ccy == "ILS" else (fx_now.get((ccy, report_date)) or (
        _normalize_fx(ccy, _num(row.get((leg1_col if ccy == ccy1 else leg2_col)["fx"]))) if ccy in (ccy1, ccy2)
        else _ccy_to_ils(ccy, report_date, fx_now)))
    if fx is None:
        return None
    ratio = abs(units) * price * fx / 1000 / total
    return ratio if ratio <= LIVE_SWAP_MAX_RATIO else None


def _offsetting_rows(source: list[dict]) -> set[int]:
    """id של שורות סוואפ שמתקזזות בזוגות: באותו מסלול, אותו טיקר ומחיר עסקה, "ערך נקוב" (רגל 1)
    זהה בסימן הפוך - עסקה שנסגרה בעסקה הפוכה (513026484_13465 ב-0425: SPTR 7,648.38 / 7,648.38-
    במחיר 15,199.655, ושלושה זוגות נוספים - בלי קיזוז 138% במקום ~80%). לא תלוי במוסכמת הסימן של
    הגוף: רק זוגות מדויקים."""
    groups: dict[tuple, dict[int, list[int]]] = defaultdict(lambda: {1: [], -1: []})
    for rec in source:
        if rec["Category"] != SWAP_CATEGORY or rec["מידע"] != "מידע":
            continue
        for row in rec["Clean"]:
            u = _num(row.get(SWAP_LEGS[0]["units"]))
            if not u:
                continue
            k = (row.get("מפתח"), str(row.get(SWAP_TICKER_COL) or "").strip().upper(),
                 _num(row.get(SWAP_UNDERLYING_PRICE_COL)), round(abs(u), 6))
            groups[k][1 if u > 0 else -1].append(id(row))
    out: set[int] = set()
    for g in groups.values():
        n = min(len(g[1]), len(g[-1]))
        out.update(g[1][:n] + g[-1][:n])
    return out


def _swap_exposure(
    source: list[dict], total_assets: dict[str, float], detail: list | None = None
) -> tuple[dict[str, float], dict[str, float], dict[str, float], dict[str, dict[str, float]]]:
    """חשיפת שורה = ממוצע שווי השוק של שתי הרגליים ("שווי הוגן במטבע הנסחר
    (רגל X)" × שער נוכחי), כשהגוף מדווח אותו - כל הגופים חוץ מ-512065202
    (אומת: שווי הוגן נטו = רגל1 + רגל2 בדיוק). זה גודל החשיפה ליום הדוח,
    בלי תלות במוסכמת היחידות/המחיר של "ערך נקוב". למשל ב-514956465_15249
    סוואפ ממומן על SPTR: ערך נקוב 291,700 בשתי הרגליים (0.3% מהמסלול בחישוב
    הקודם), שווי רגל התשואה 37.6 מיליון דולר (42%). שורה בלי שווי רגליים
    נופלת לחישוב שלמטה (ערך נקוב × מחיר).

    נמצא בבדיקה בפועל (לא ניחוש): "ערך נקוב" (רגל 1) ו"ערך נקוב" (רגל 2)
    אינם תמיד באותה יחידת מידה. עבור "Unfunded Forward" (למשל פורוורד מט"ח)
    שתי הרגליים כבר סכום נקוב במטבע - קרובות זו לזו כצפוי. אבל עבור
    "Unfunded Swap" על מניות/מדדים (סוואפ תשואה-כוללת), רגל 1 היא כמות
    *יחידות גולמית* של נכס הבסיס (לא סכום נקוב), ורגל 2 היא כבר הסכום
    הנקוב הנכון. אומת ישירות מול reports/2026Q2/512065202_gm_0226.xlsx:
    על 542/542 שורות סוואפ-מניות, רגל1 × "שער נכס הבסיס במועד ההתקשרות
    בעסקה" (× שער חליפין רגל 1) שווה בדיוק לרגל 2 (עד כדי עיגול). לכן רגל 1
    צריכה הכפלה בשער נכס הבסיס כדי להיות ברת-השוואה לרגל 2 - לא נוסחת
    ה-units×fx הרגילה שמשמשת לכל שאר הקטגוריות. אין דגל מפורש בדוח שמבחין
    בין "Unfunded Swap" ל"Unfunded Forward", ולכן הבחירה אדפטיבית לכל שורה:
    בין הפרשנות הגולמית לפרשנות המוכפלת-במחיר לרגל 1, נבחרת זו שקרובה יותר
    לרגל 2 (שנמצא בפועל שהיא תמיד כבר תקינה).

    גם אחרי התיקון הזה, נמצא בפועל שחלק מהמגישים רושמים את "שער נכס הבסיס"
    בקנה מידה שגוי (למשל פי ~100, אותה תבנית תקלה כמו JPY/ערך-נקוב-100
    בחוזים עתידיים) - לא עקבי אפילו בתוך אותה קרן/טיקר. מטופל באותו עקרון
    LEVERAGE_CAP שכבר קיים לחוזים עתידיים: משווים את החשיפה הנוציונלית
    שהתקבלה לשווי ההוגן נטו שאותה שורה בדיוק מדווחת - יחס גבוה מדי מסמן קנה
    מידה לא אמין, ונופלים לערך המדווח (PCT_COL) לשורה הזו בלבד. תקרת
    ה-SANITY_CAP הקיימת (ברמת שורה) ותקרת מסלול נוספת (סכום מצטבר על פני כל
    שורות ה-swap במסלול) נשארות כרשת ביטחון אחרונה.

    שיפור: "שער נכס הבסיס במועד ההתקשרות בעסקה" הוא מחיר *בפתיחת* העסקה
    (ר' הערת המודול), לא מחיר עדכני - לחשיפה נכונה ליום הדוח משתמשים במקום
    זאת, כשאפשר, במחיר המדד החי נכון לתאריך הדוח (swap_index_pricing, דרך
    עמודת "טיקר" ומיפוי revach123/INDICES). כשהטיקר לא ממופה (בעיקר סלים
    קנייניים בנקאיים - ר' swap_ticker_map.csv שם) נופלים בחזרה לשיטת המחיר-
    בפתיחת-העסקה הקיימת. במקרה הזה leg2 (שקבוע לפי בנייה למחיר הפתיחה) כבר
    לא רלוונטי כעוגן לרגל 1 המתומחרת-חי - שתיהן מודדות דברים שונים בכוונה
    (נוציונל היסטורי מול חשיפה נוכחית) - לכן לא ממוצעים ביניהן.

    עדכון: leg1_live + LEVERAGE_CAP חלים *רק* כש-used_priced=True (רגל 1
    נבחרה בפועל, לפי ההשוואה מול רגל 2, כיחידות-גולמיות-הצריכות-מחיר) -
    *לא* לפי תווית Funded/Unfunded כמו שהיה קודם. נמצא בפועל שהתווית
    "מאפיין עיקרי" לבדה אינה אמינה: שורות "Unfunded Total Return/Equity
    Swap" (התווית הנפוצה ביותר בארכיון) יכולות להיות "רגל 1 כבר נוציונל"
    אצל מגיש מסוים (513173393/אלטשולר שחם) בדיוק כמו Funded, בעוד שאצל
    מגישים אחרים תחת אותה תווית בדיוק רגל 1 באמת יחידות גולמיות (כמו
    512065202 שאומת במקור) - ר' used_priced/is_funded למטה.

    מחזיר (notional_sums, funded_sums, unfunded_sums, equity_swaps) - הראשון
    הוא הסכום הכולל (המשמש להחלפת SWAP_CATEGORY, כמו קודם), השניים הבאים הם
    פילוח שקוף Funded/Unfunded (דיאגנוסטי בלבד, ר' build_derivatives_exposure),
    והאחרון הוא תת-קבוצה של notional_sums - רק שורות עם סוג הנכס=מניות,
    מפוצלות-שוב לפי הערך המדויק ב-"מאפיין עיקרי" (Funded/Unfunded X, כפי
    שמופיע בדוח בפועל), לאזור החשיפה למניות בדשבורד (ר' main.py)."""
    notional_sums: dict[str, float] = {}
    fv_sums: dict[str, float] = {}
    funded_sums: dict[str, float] = {}
    unfunded_sums: dict[str, float] = {}
    # equity_by_label: מפתח -> {"Unfunded Swap": שיעור, ...} - רק שורות עם
    # סוג הנכס = מניות, מפוצלות לפי הערך המדויק ב-SWAP_MAIN_TYPE_COL (Funded/
    # Unfunded X, כפי שמופיע בדוח בפועל - לא הנחה על אילו ערכים קיימים),
    # לאזור החשיפה למניות בדשבורד. שיעור-הוגן מקביל לכל bucket, לאותו
    # fallback-אם-קנה-המידה-לא-סביר כמו notional_sums הכולל.
    equity_by_label: dict[str, dict[str, float]] = {}
    equity_fv_by_label: dict[str, dict[str, float]] = {}
    leg1_col, leg2_col = SWAP_LEGS
    fx_now = _current_fx_rates(source)
    offset = _offsetting_rows(source)
    _TICKER_CCY.clear()
    _TICKER_CCY.update(_ticker_currencies(source))
    for rec in source:
        if rec["Category"] != SWAP_CATEGORY or rec["מידע"] != "מידע":
            continue
        report_date = rec.get("ReportMonth")
        for row in rec["Clean"]:
            key = row.get("מפתח")
            total = total_assets.get(key) if key is not None else None
            if not total:
                continue
            if id(row) in offset:
                # עסקה שנסגרה בעסקה הפוכה זהה - שתיהן יחד אפס חשיפה
                row_pct = to_ratio(row.get(PCT_COL)) or 0.0
                fv_sums[key] = fv_sums.get(key, 0.0) + row_pct
                if detail is not None:
                    detail.append({"key": key, "row": row, "ratio": 0.0, "row_pct": row_pct,
                                   "equity": is_equity_swap(row)})
                continue
            is_equity = is_equity_swap(row)
            label = row.get(SWAP_LABEL_COL)
            # ה-fallback (כשקנה המידה לא אמין) משתמש בעמודת האחוז כפי שהדוח
            # עצמו מדווח - נמצא בפועל מדויק יותר מ-fv/total_assets_by_key
            # (שהאומדן שלה לשווי הכולל לא תמיד מתאים בדיוק לאומדן הדוח עצמו
            # לכל שורה בנפרד).
            row_pct = to_ratio(row.get(PCT_COL)) or 0.0
            fv_sums[key] = fv_sums.get(key, 0.0) + row_pct
            if is_equity and label:
                d = equity_fv_by_label.setdefault(key, {})
                d[label] = d.get(label, 0.0) + row_pct
            # is_funded: תווית "מאפיין עיקרי" בלבד - שימושי לפילוח דיאגנוסטי
            # (funded_sums/unfunded_sums), אבל *לא* אמין להחלטת קנה-המידה
            # עצמה (ר' used_priced למטה) - נמצא בפועל (513173393/אלטשולר
            # שחם) ששורות המתויגות "Unfunded Total Return/Equity Swap" -
            # התווית הנפוצה ביותר בארכיון, לא רק ב-512065202 שאומת במקור -
            # יכולות להיות "רגל 1 כבר נוציונל" בדיוק כמו Funded, תלוי מגיש
            # ספציפי (לא עקבי בין מגישים תחת אותה תווית בדיוק).
            is_funded = _is_funded_swap(row.get(SWAP_MAIN_TYPE_COL))

            leg_values = raw_legs = _leg_market_values(row, report_date, fx_now)
            if leg_values and not _legs_reconcile(row, report_date, fx_now):
                leg_values = []  # "שווי" הרגליים לא מסתכם לנטו - לא שווי שוק
            # יחידות זהות בשתי הרגליים - רק כשאין שווי רגליים תקף (שורה רגילה לא משתנה)
            mirrored_units = _mirrored_units(row, report_date, fx_now) if is_equity and not leg_values else None
            mirrored = mirrored_units is not None
            live_ratio = (_live_swap_ratio(row, report_date, fx_now, total)
                          if is_equity and (leg_values or mirrored) else None)
            if (live_ratio is not None and leg_values and not mirrored
                    and _legs_are_notional(row, sum(leg_values) / len(leg_values) / total, live_ratio)):
                live_ratio = None
            if mirrored and live_ratio is None and raw_legs:
                # "ערך נקוב" זהה ברגליים שהוא סכום ולא כמות (יחידות × מחיר לא סביר) - הרגליים הן
                # הנוציונל גם כשהנטו כולל ריבית צבורה ולא מסתכם (511880460_963 ב-0425: SPTR, 26.9
                # מיליון דולר, רגליים 26,922 / 26,926- אלף)
                leg_values, mirrored = raw_legs, False
            if mirrored and live_ratio is not None:
                # יחידות שמשתקפות בשער בין הרגליים - הרגליים (אם יש) הן היחידות / 1000, לא שווי.
                # הסימן של היחידות בשקלים הוא כיוון העסקה (512065202_13246 ב-0126: עסקה אחת
                # של 1,077.57- מול עשר חיוביות; בסימן - 99.4% מול 99.5% רשמי, בערך מוחלט 104.7%)
                line_ratio = math.copysign(live_ratio, mirrored_units)
            elif leg_values and live_ratio is not None and sum(leg_values) / len(leg_values) / total < MTM_LEG_SHARE * live_ratio:
                # הרגליים הן רק שינוי השווי מאז הפתיחה / ה-Reset (514956465_9452: ±9,253.6
                # יחידות SPTR, רגליים 354 / 1,930 אלף דולר = 0.3%) - החשיפה היא יחידות × מחיר המדד
                line_ratio = live_ratio
            elif leg_values:
                # שווי השוק של הרגליים הוא גודל החשיפה הנוכחי - בלי מוסכמות יחידות/מחיר
                index_leg = (_index_leg_value(row, report_date, fx_now,
                                              live_ratio * total if live_ratio is not None else None)
                             if is_equity else None)
                line_ratio = (index_leg if index_leg is not None
                              else sum(leg_values) / len(leg_values)) / total
            else:
                units1 = _num(row.get(leg1_col["units"]))
                fx1 = _normalize_fx(row.get(leg1_col["currency"]), _num(row.get(leg1_col["fx"])))
                units2 = _num(row.get(leg2_col["units"]))
                fx2 = _normalize_fx(row.get(leg2_col["currency"]), _num(row.get(leg2_col["fx"])))
                price = _num(row.get(SWAP_UNDERLYING_PRICE_COL))
                # מחיר נכס הבסיס נקוב במטבע נכס הבסיס - הרגל שאינה בשקלים (512065202:
                # רגל 1 = יחידות בשקלים, רגל 2 = יחידות × מחיר בדולר), לא במטבע רגל 1.
                ccy1, ccy2 = row.get(leg1_col["currency"]), row.get(leg2_col["currency"])
                price_ccy = ccy2 if ccy1 == "ILS" and ccy2 else ccy1
                price_fx = (1.0 if price_ccy == "ILS" else fx_now.get((price_ccy, report_date))
                            or (fx2 if price_ccy == ccy2 else fx1))
                stock = stock_quote(row.get(SWAP_TICKER_COL)) if is_equity else None
                stock_fx = None
                stock_ccy = bool(stock and stock.currency not in ("ILS", price_ccy) and price is not None)
                if stock_ccy:
                    # מחיר העסקה של מניה נקוב במטבע הבורסה שלה; רגל "USD" שהיא יחידות × המחיר הזה
                    # היא סכום באותו מטבע (512065202_877 ב-0126: TT2330, 61,688.8 × 1,740 = 107.3
                    # מיליון "USD" - דולר טייוואני). בלי שער למטבע - אין תמחור (שווי השורה)
                    stock_fx = _ccy_to_ils(stock.currency, report_date, fx_now)
                    price, price_fx = price * stock.factor, (stock_fx or None)
                    if (stock_fx and units1 and units2 and fx2 is not None
                            and abs(abs(units2 / units1) / (price / stock.factor) - 1) <= 0.01):
                        fx2 = stock_fx * stock.factor

                leg2_val = abs(units2 * fx2) / 1000 if units2 is not None and fx2 is not None else None
                leg1_raw = abs(units1 * fx1) / 1000 if units1 is not None and fx1 is not None else None
                leg1_priced = (abs(units1 * price_fx * price) / 1000
                                if units1 is not None and price_fx is not None and price is not None else None)

                # used_priced: ההשוואה בפועל בין הפרשנויות (רגל1 גולמי מול רגל1
                # מוכפל-במחיר) ביחס לרגל2 - זו בדיקת-הסבירות ה*אמיתית* של קנה
                # המידה, ברמת השורה הבודדת, לא תלוית-תווית. True = רגל 1 הוא
                # באמת יחידות גולמיות (כמו 512065202 - התבנית שאומתה במקור).
                # False = רגל 1 כבר נוציונל (כמו Funded, וגם כמו חלק ניכר
                # מהשורות "Unfunded ..." בפועל - ר' הערה למעלה).
                used_priced = leg1_priced is not None and (
                    leg1_raw is None or leg2_val is None
                    or abs(leg1_priced - leg2_val) < abs(leg1_raw - leg2_val)
                )
                leg1_val = leg1_priced if used_priced else leg1_raw

                # leg1_live (תמחור-חי) מניח שרגל 1 היא יחידות גולמיות שצריך
                # לתמחר מחדש - תקף *רק* כשused_priced (לא is_funded - ר' הערה
                # למעלה): כשרגל 1 כבר נוציונל, תמחור חוזר יוצר מספר דמיוני
                # (נבדק בפועל: ~1.5 מיליארד ש"ח על שורה עם נוציונל אמיתי
                # ~100 מיליון - פי ~15,000).
                leg1_live = None
                if used_priced:
                    current_price = _current_index_price(row, report_date)
                    leg1_live = (abs(units1 * price_fx * current_price) / 1000
                                 if units1 is not None and price_fx is not None and current_price is not None else None)

                if leg1_live is not None:
                    candidates = [leg1_live]  # לא ממוצעים עם leg2 - ר' הערת הפונקציה
                elif stock_ccy and not stock_fx:
                    candidates = []
                else:
                    candidates = [v for v in (leg1_val, leg2_val) if v is not None]

                line_ratio = None
                if candidates:
                    notional_thousands = sum(candidates) / len(candidates)
                    line_ratio = notional_thousands / total

                    # LEVERAGE_CAP (יחס נוציונל/שווי-הוגן-נטו) רלוונטי *רק*
                    # כש-used_priced: זו הדרך היחידה שבה "שער נכס הבסיס" (מחיר
                    # מדד גולמי, קנה-מידה שרירותי לגמרי ביחס ל-fv) נכנס בכלל
                    # לחישוב הנוציונל, ולכן היחידה שבה טעות-קנה-מידה בשדה הזה
                    # עלולה להתגלגל לתוצאה. כש-used_priced=False, הנוציונל כבר
                    # אומת ישירות מול רגל 2 (ההשוואה למעלה) - וגם נמצא בפועל
                    # (513173393) ששורות used_priced=False יכולות לגיטימית
                    # להגיע ליחס נוציונל/fv עצום (עד פי ~1900) כש-fv נמצא במקרה
                    # קרוב לאפס (סוואפ Unfunded בלי Reset תקופתי - fv יכול לנוע
                    # דרך אפס בלי קשר לקנה-מידה) - לא סימן לתקלה שם.
                    # קנה המידה מאומת כשרגל 1 × מחיר בעסקה = רגל 2 (עד 5%) - אז שווי הוגן
                    # קרוב לאפס הוא עסקה חדשה (512065202_7867: IXCTR מ-23.6, נוציונל 41.8
                    # מיליון דולר, שווי 178- אלף), לא תקלת קנה מידה - לא מפעילים LEVERAGE_CAP
                    scale_confirmed = (leg1_priced is not None and leg2_val
                                       and abs(leg1_priced / leg2_val - 1) <= 0.05)
                    if used_priced and not scale_confirmed:
                        fv = _num(row.get(SWAP_NET_FAIR_VALUE_COL))
                        fv_ratio = (fv / total) if fv is not None else None
                        if fv_ratio is not None and abs(line_ratio) > LEVERAGE_CAP * abs(fv_ratio):
                            line_ratio = None  # קנה מידה לא סביר ביחס לשווי ההוגן של השורה עצמה
            if line_ratio is None or abs(line_ratio) > SANITY_CAP:
                line_ratio = row_pct
            notional_sums[key] = notional_sums.get(key, 0.0) + line_ratio
            if detail is not None:
                detail.append({"key": key, "row": row, "ratio": line_ratio,
                               "row_pct": row_pct, "equity": is_equity})
            if is_funded:
                funded_sums[key] = funded_sums.get(key, 0.0) + line_ratio
            else:
                unfunded_sums[key] = unfunded_sums.get(key, 0.0) + line_ratio
            if is_equity and label:
                d = equity_by_label.setdefault(key, {})
                d[label] = d.get(label, 0.0) + line_ratio

    capped = {
        key: val if abs(val) <= SANITY_CAP else fv_sums.get(key, 0.0)
        for key, val in notional_sums.items()
    }
    equity_swaps = {
        key: {
            label: val if abs(val) <= SANITY_CAP else equity_fv_by_label.get(key, {}).get(label, 0.0)
            for label, val in by_label.items()
        }
        for key, by_label in equity_by_label.items()
    }
    return capped, funded_sums, unfunded_sums, equity_swaps


def collect_unresolved_swap_tickers(source: list[dict]) -> dict[str, set[str]]:
    """מפתח -> סט טיקרים של סוואפ-מדד (סוג הנכס == מניות לרבות מדדי מניות) שאין להם מקור
    מחיר ליום הדוח: לא סדרה ב-INDICES (swap_ticker_map.csv) ולא תעודת סל עוקבת (PROXY_ETF) - סלים
    קנייניים בנקאיים (GS*/JPM*/CGAS*/MLBL*), מניות בודדות, או טיקר חדש. מיועד לדגל "לטיפול" בדשבורד - לא משפיע על חישוב החשיפה עצמו."""
    from .swap_index_pricing import has_price_source, normalize_ticker

    out: dict[str, set[str]] = {}
    for rec in source:
        if rec["Category"] != SWAP_CATEGORY or rec["מידע"] != "מידע":
            continue
        for row in rec["Clean"]:
            if not is_equity_swap(row):
                continue
            key = row.get("מפתח")
            raw_ticker = row.get(SWAP_TICKER_COL)
            if key is None or not normalize_ticker(raw_ticker) or has_price_source(raw_ticker):
                continue
            out.setdefault(key, set()).add(str(raw_ticker).strip())
    return out


def _as_date(v) -> date | None:
    """תאריך פקיעה כפי שמופיע בדוחות: datetime / date (openpyxl) או מחרוזת
    ("26/04/2026", "24/07/2026", "2026-07-24")."""
    if hasattr(v, "date"):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def is_equity_option(row: dict) -> bool:
    """אופציה על מניות: "נכס בסיס" = מניות, או ערך לא סטנדרטי / ריק כשנכס הבסיס
    זוהה משם האופציה כמדד מניות / מניה (C004160M607-35ת -> ת"א 35). אופציות
    פרויקט ("קיקר", "PowerGen Option") לא מזוהות ונשארות מחוץ לחשיפה למניות."""
    v = row.get(OPT_UNDERLYING_COL)
    if v == OPT_EQUITY_UNDERLYING:
        return True
    if v in OPT_NON_EQUITY_UNDERLYINGS:
        return False
    name = row.get(OPT_NAME_COL)
    return bool(name) and parse_underlying(str(name))[0] is not None


def _option_expiry(row: dict, name, report_date) -> date | None:
    """תאריך הפקיעה; כשהשם הוא קוד מעו"ף (M607 = 07/2026) והעמודה ריקה או
    סותרת אותו (נצפה 2046-03-31 כערך ברירת מחדל) - החודש מהקוד (ה-24 בחודש;
    הדלתא כמעט לא רגישה ליום)."""
    expiry = _as_date(row.get(OPT_EXPIRY_COL))
    ym = parse_maof_expiry_month(str(name), report_date.year) if name and report_date else None
    if ym and (expiry is None or (expiry.year, expiry.month) != ym):
        return date(ym[0], ym[1], 24)
    return expiry


MAOF_PATTERN = "C_tase_maof_code"
MAOF_SIZES = (1.0, 10.0, 100.0, 1000.0, 10000.0)
MAOF_MIN_VALUE_SHARE = 0.02  # שורה אמינה ללימוד גודל החוזה: ערך האופציה 2%+ ממחיר המניה (לא שער מינימום)


def _maof_contract_sizes(source: list[dict]) -> dict[str, float]:
    """טיקר מניה -> מניות לחוזה מעו"ף: שער האופציה לחוזה / מחיר B&S למניה, מעוגל לחזקת 10, חציון על
    השורות האמינות של אותה מניה (בכל הגופים)."""
    ratios: dict[str, list[float]] = {}
    for rec in source:
        if rec["Category"] not in OPTIONS_CATEGORIES or rec["מידע"] != "מידע":
            continue
        report_date = rec.get("ReportMonth")
        for row in rec["Clean"]:
            name = row.get(OPT_NAME_COL)
            if not name:
                continue
            ticker, pattern = parse_underlying(str(name))
            if pattern != MAOF_PATTERN or ticker in CONTRACT_MULTIPLIER:
                continue
            is_call = is_call_option(str(name))
            strike = _num(row.get(OPT_STRIKE_COL))
            if not strike or strike <= 0:
                strike = parse_strike(str(name))
            px = _num(row.get(OPT_PRICE_COL))
            if is_call is None or not strike or not px or px <= 0:
                continue
            value, spot = resolve_option_value(ticker, strike, _option_expiry(row, name, report_date),
                                               report_date, is_call)
            if value and spot and value >= MAOF_MIN_VALUE_SHARE * spot:
                ratios.setdefault(ticker, []).append(px / value)
    out = {}
    for ticker, rs in ratios.items():
        med = statistics.median(rs)
        out[ticker] = min(MAOF_SIZES, key=lambda m: abs(math.log10(med / m)))
    return out


_FO_CANDIDATES = ("ES_FO", "NQ_FO", "RTY_FO", "YM_FO")


def _futures_option_underlying(strike: float | None, report_date) -> str | None:
    """נכס הבסיס של אופציה על חוזה E-mini לפי המימוש: המדד שהמימוש הכי קרוב לרמתו ביום הדוח
    (עד פי 1.6 לכל כיוון). S&P ~6-7K, נאסד"ק-100 ~21-31K, ראסל ~2.5K, דאו ~45K - טווחים נפרדים."""
    from .option_delta_pricing import UNDERLYING_ALIAS, price_as_of as spot_as_of
    if not strike or not report_date:
        return None
    best = None
    for cand in _FO_CANDIDATES:
        spot = spot_as_of(UNDERLYING_ALIAS[cand], report_date)
        if spot:
            dist = abs(math.log(strike / spot))
            if dist <= math.log(1.6) and (best is None or dist < best[0]):
                best = (dist, cand)
    return best[1] if best else None


def _option_key(row: dict, legal_id: str) -> tuple | None:
    name = row.get(OPT_NAME_COL)
    if not name:
        return None
    ticker, _ = parse_underlying(str(name))
    strike = _num(row.get(OPT_STRIKE_COL)) or parse_strike(str(name))
    if not ticker or not strike:
        return None
    return legal_id, ticker, strike, str(row.get(OPT_EXPIRY_COL) or "")


def _mislabeled_call_put(source: list[dict], category: str) -> set[int]:
    """id של שורות אופציה שהשם שלהן אומר קול והמחיר אומר פוט (או להפך): לאותו גוף, נכס בסיס,
    מימוש ופקיעה יש מחיר אחד לקול ואחד לפוט בכל המסלולים. שורה שהמחיר שלה רחוק 20%+ מחציון
    הסוג שלה וקרוב עד 5% לחציון הסוג השני - מהסוג השני (512065202_14267 ב-0325: "tlC 3100 NOV"
    פעמיים, במחיר 10,016 ובמחיר 1,484 = מחיר "tlP 3100 NOV" במסלולים האחים - קול ופוט שקוזזו)."""
    prices: dict[tuple, dict[bool, list[float]]] = defaultdict(lambda: {True: [], False: []})
    rows = []
    for rec in source:
        if rec["Category"] != category or rec["מידע"] != "מידע":
            continue
        legal_id = str(rec.get("LegalId") or "")
        for row in rec["Clean"]:
            k = _option_key(row, legal_id)
            price = _num(row.get(OPT_PRICE_COL))
            is_call = is_call_option(str(row.get(OPT_NAME_COL) or ""))
            if k is None or not price or price <= 0 or is_call is None:
                continue
            prices[k][is_call].append(price)
            rows.append((id(row), k, is_call, price))
    out = set()
    for rid, k, is_call, price in rows:
        own, other = prices[k][is_call], prices[k][not is_call]
        if not other:
            continue
        own_med, other_med = statistics.median(own), statistics.median(other)
        if abs(price / own_med - 1) > 0.2 and abs(price / other_med - 1) <= 0.05:
            out.add(rid)
    return out


def _options_exposure(
    source: list[dict], total_assets: dict[str, float], category: str, detail: list | None = None
) -> tuple[dict[str, float], dict[str, float]]:
    """דלתא×נוציונל לקטגוריית אופציה אחת (listed/OTC בנפרד - שם השדה
    ה"מפתח" תמיד "Category" של הגיליון, לא משנה איזה). רק שורות נכס-בסיס
    מניות (OPT_EQUITY_UNDERLYING) - מט"ח/ריבית/אחר נשארים בשיטה הישנה,
    מחוץ להיקף (לא אופציות על מניות, לא חלק מהתיקון הזה). מחזיר גם
    equity_sums - תת-קבוצה של sums, רק שורות מניות - לאזור החשיפה למניות
    בדשבורד (ר' main.py). detail (אופציונלי): שורת מניות אחת לכל שורה, עם
    אותה חשיפה ונכס הבסיס שזוהה (לפירוק לפי מדד, index_exposure)."""
    sums: dict[str, float] = {}
    equity_sums: dict[str, float] = {}
    maof_sizes = _maof_contract_sizes(source)
    flipped = _mislabeled_call_put(source, category)
    for rec in source:
        if rec["Category"] != category or rec["מידע"] != "מידע":
            continue
        report_date = rec.get("ReportMonth")
        for row in rec["Clean"]:
            key = row.get("מפתח")
            total = total_assets.get(key) if key is not None else None
            if not total:
                continue
            row_pct = to_ratio(row.get(PCT_COL)) or 0.0

            if not is_equity_option(row):
                sums[key] = sums.get(key, 0.0) + row_pct
                continue

            name = row.get(OPT_NAME_COL)
            ticker, pattern = parse_underlying(str(name)) if name else (None, None)
            is_call = is_call_option(str(name)) if name else None
            if is_call is not None and id(row) in flipped:
                is_call = not is_call
            strike = _num(row.get(OPT_STRIKE_COL))
            if not strike or strike <= 0:  # עמודה ריקה / 0 - מהשם ("C004160M607-35ת")
                strike = parse_strike(str(name)) if name else None
            if ticker == FUTURES_OPTION:
                ticker = _futures_option_underlying(strike, report_date)
            expiry = _option_expiry(row, name, report_date)
            units = _num(row.get(OPT_UNITS_COL))
            fx = _normalize_fx(row.get(OPT_CURRENCY_COL), _num(row.get(OPT_FX_COL)))

            line_ratio = None
            fv = _num(row.get(FAIR_VALUE_COL))
            fv_ratio = (fv / total) if fv is not None else None
            if ticker is not None and is_call is not None and units is not None and fx is not None:
                delta, spot = resolve_option_delta(ticker, strike, expiry, report_date, is_call)
                if delta is not None and spot is not None:
                    mult = CONTRACT_MULTIPLIER.get(ticker) or (
                        maof_sizes.get(ticker, MAOF_STOCK_OPTION_SHARES) if pattern == MAOF_PATTERN else 1.0)
                    notional_thousands = units * mult * delta * spot * quote_scale(ticker) * fx / 1000
                    line_ratio = notional_thousands / total
                    if fv_ratio is not None and abs(line_ratio) > LEVERAGE_CAP * abs(fv_ratio):
                        line_ratio = None
            if line_ratio is None or abs(line_ratio) > SANITY_CAP:
                line_ratio = row_pct
            # קול לונג: החשיפה (דלתא × נכס הבסיס) לעולם לא קטנה משווי האופציה (C <= S·N(d1)). קול
            # "ממומן" שדווח בשווי נכס הבסיס המלא (הפניקס "עסקת CALL לאומי": שווי = יחידות × שער המניה,
            # דלתא B&S 0.46) - החשיפה היא השווי
            if is_call and units and units > 0 and fv_ratio is not None and 0 < line_ratio < fv_ratio <= SANITY_CAP:
                line_ratio = fv_ratio
            sums[key] = sums.get(key, 0.0) + line_ratio
            equity_sums[key] = equity_sums.get(key, 0.0) + line_ratio
            if detail is not None:
                detail.append({"key": key, "row": row, "ratio": line_ratio, "ticker": ticker})
    return sums, equity_sums


def build_derivatives_exposure(source: list[dict]) -> dict[str, dict[str, float]]:
    """מפתח -> {קטגוריה: שיעור חשיפה אמיתי}, לארבע הקטגוריות (חוזים עתידיים,
    לא סחיר נגזרים אחרים, אופציות, לא סחיר אופציות) - מיועד להחליף את
    הערכים המבוססי-שווי-הוגן שמחשב category_pct.build_category_pct לאותן
    קטגוריות בדיוק - ולא לגעת בשאר הקטגוריות.

    בנוסף (לא מחליף כלום, רק מצטרף): שתי קטגוריות דיאגנוסטיות (FUNDED_
    SWAP_CATEGORY/UNFUNDED_SWAP_CATEGORY) - פילוח שקוף של SWAP_CATEGORY בין
    שני מבני הסוואפ (ר' הערת _swap_exposure); ועמודות "אזור חשיפה למניות" -
    נכס-בסיס=מניות בלבד לחוזים/אופציות (FUTURES_EQUITY_COLUMN/
    OPTIONS_EQUITY_COLUMN), ופיצול Funded/Unfunded לסוואפים-על-מניות (לפי
    SWAP_MAIN_TYPE_COL בפועל בדוח) - עמודות "לא סחיר נגזרים אחרים - מניות
    (<תווית>)"."""
    total_assets = total_assets_by_key(source)
    futures, futures_equity = _futures_exposure(source, total_assets)
    swaps, funded_swaps, unfunded_swaps, swaps_equity_by_label = _swap_exposure(source, total_assets)
    options_listed, options_listed_equity = _options_exposure(source, total_assets, OPTIONS_LISTED_CATEGORY)
    options_otc, options_otc_equity = _options_exposure(source, total_assets, OPTIONS_OTC_CATEGORY)

    out: dict[str, dict[str, float]] = {}
    for key, val in futures.items():
        out.setdefault(key, {})[FUTURES_CATEGORY] = val
    for key, val in swaps.items():
        out.setdefault(key, {})[SWAP_CATEGORY] = val
    for key, val in funded_swaps.items():
        out.setdefault(key, {})[FUNDED_SWAP_CATEGORY] = val
    for key, val in unfunded_swaps.items():
        out.setdefault(key, {})[UNFUNDED_SWAP_CATEGORY] = val
    for key, val in options_listed.items():
        out.setdefault(key, {})[OPTIONS_LISTED_CATEGORY] = val
    for key, val in options_otc.items():
        out.setdefault(key, {})[OPTIONS_OTC_CATEGORY] = val

    for key, val in futures_equity.items():
        out.setdefault(key, {})[FUTURES_EQUITY_COLUMN] = val
    for key, by_label in swaps_equity_by_label.items():
        d = out.setdefault(key, {})
        for label, val in by_label.items():
            d[f"{SWAP_CATEGORY} - מניות ({label})"] = val
    for key, val in options_listed_equity.items():
        out.setdefault(key, {})[OPTIONS_EQUITY_COLUMN] = out.setdefault(key, {}).get(OPTIONS_EQUITY_COLUMN, 0.0) + val
    for key, val in options_otc_equity.items():
        out.setdefault(key, {})[OPTIONS_EQUITY_COLUMN] = out.setdefault(key, {}).get(OPTIONS_EQUITY_COLUMN, 0.0) + val
    return out
