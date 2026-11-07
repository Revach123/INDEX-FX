"""התאמת שם_הבנק (טקסט חופשי בדוחות) לרשומה ב-bank_reference.csv.

לא לפי "מספר מזהה בנק" - הוכח לא אמין גלובלית (אותו קוד מייצג בנקים
שונים בדוחות שונים). ההתאמה כאן היא alias map מפורש, שנבנה מתוך כל
81 הכתיבים השונים שנמצאו בפועל ב-88 קבצי הדוחות (לא ניחוש/פאזי-מאצ'ינג
כללי, כדי לא ליצור התאמות שגויות).
"""
import csv
from pathlib import Path

CSV_PATH = Path(__file__).parent / "bank_reference.csv"

FOREIGN_MARKER = "__FOREIGN__"

# כתיב אמיתי מהדוחות -> שם_בנק קנוני (חייב להופיע בדיוק כך ב-bank_reference.csv,
# או FOREIGN_MARKER לבנקים/ברוקרים זרים ללא ח.פ ישראלי).
ALIASES: dict[str, str] = {
    # בנק לאומי
    'בנק לאומי לישראל בע"מ': 'בנק לאומי לישראל בע"מ',
    'בנק לאומי': 'בנק לאומי לישראל בע"מ',
    'לאומי': 'בנק לאומי לישראל בע"מ',
    'בנק לאומי למשכנתאות בע"מ': 'בנק לאומי לישראל בע"מ',
    'בנק לאומי למשכנתאות': 'בנק לאומי לישראל בע"מ',
    # בנק הפועלים
    'בנק הפועלים בע"מ': 'בנק הפועלים בע"מ',
    'בנק הפועלים': 'בנק הפועלים בע"מ',
    "בנק הפועלים בע''מ": 'בנק הפועלים בע"מ',
    'הפועלים': 'בנק הפועלים בע"מ',
    'בנק הפועלים משכן': 'בנק הפועלים בע"מ',
    'הבנק למסחר משכן': 'בנק הפועלים בע"מ',
    # מזרחי טפחות
    'בנק מזרחי': 'בנק המזרחי-טפחות בע"מ',
    'בנק מזרחי טפחות בע"מ': 'בנק המזרחי-טפחות בע"מ',
    'מזרחי': 'בנק המזרחי-טפחות בע"מ',
    'מזרחי טפחות': 'בנק המזרחי-טפחות בע"מ',
    'בנק המזרחי המאוחד בע"מ': 'בנק המזרחי-טפחות בע"מ',
    'מזרחי טפחות חברה להנפקות בע"מ': 'מזרחי טפחות חברה להנפקות בע"מ',  # ישות נפרדת
    # דיסקונט
    'בנק דיסקונט לישראל בע"מ': 'בנק דיסקונט לישראל בע"מ',
    'בנק דיסקונט': 'בנק דיסקונט לישראל בע"מ',
    'דיסקונט': 'בנק דיסקונט לישראל בע"מ',
    'בנק דיסקונט לישראל בעמ': 'בנק דיסקונט לישראל בע"מ',
    'בנק מרכנתיל דיסקונט בע"מ': 'בנק מרכנתיל דיסקונט בע"מ',
    # הבינלאומי הראשון (כולל יובנק ואוצר החייל שמוזגו לתוכו)
    'הבנק הבינלאומי הראשון לישראל בע"מ': 'הבנק הבינלאומי הראשון לישראל בע"מ',
    'בנק הבינלאומי': 'הבנק הבינלאומי הראשון לישראל בע"מ',
    'הבנק הבינלאומי': 'הבנק הבינלאומי הראשון לישראל בע"מ',
    'בנק בינלאומי': 'הבנק הבינלאומי הראשון לישראל בע"מ',
    'הבינלאומי': 'הבנק הבינלאומי הראשון לישראל בע"מ',
    'בנק הבינלאומי הראשון לישראל': 'הבנק הבינלאומי הראשון לישראל בע"מ',
    'הבינלאומי ( לשעבר יובנק)': 'הבנק הבינלאומי הראשון לישראל בע"מ',
    'בנק U בנק': 'הבנק הבינלאומי הראשון לישראל בע"מ',
    'בנק יו-בנק בע"מ': 'הבנק הבינלאומי הראשון לישראל בע"מ',
    'יובנק': 'הבנק הבינלאומי הראשון לישראל בע"מ',
    'יו-בנק': 'הבנק הבינלאומי הראשון לישראל בע"מ',
    'יובנק בע"מ': 'הבנק הבינלאומי הראשון לישראל בע"מ',
    'אוצר החייל': 'הבנק הבינלאומי הראשון לישראל בע"מ',
    # שאר הבנקים הישראליים
    'בנק ירושלים': 'בנק ירושלים בע"מ',
    'בנק ירושלים בע"מ': 'בנק ירושלים בע"מ',
    'גמול פועלים סהר': 'פועלים סהר בע"מ',
    'פועלים סהר': 'פועלים סהר בע"מ',
    'הפועלים סהר': 'פועלים סהר בע"מ',
    'נשואה': 'אקסלנס נשואה שירותי בורסה בע"מ',
    'איגוד': 'בנק איגוד לישראל בע"מ',
    'בנ איגוד': 'בנק איגוד לישראל בע"מ',
    # זרים (ללא ח.פ ישראלי - אין מושג היתר עסקה)
    'סיטיבנק': FOREIGN_MARKER, 'Bny Mellon': FOREIGN_MARKER, 'JPM': FOREIGN_MARKER,
    'CITI_GlobalCustody': FOREIGN_MARKER, 'CITI FXPB': FOREIGN_MARKER,
    'JPMORGAN CHASE BANK': FOREIGN_MARKER, 'HSBC': FOREIGN_MARKER,
    'JPMorgan Chase Bank NA London Branch': FOREIGN_MARKER, 'CITI': FOREIGN_MARKER,
    'JP Morgan': FOREIGN_MARKER, 'CITIBANK': FOREIGN_MARKER, 'Goldman': FOREIGN_MARKER,
    'J.P. MORGAN': FOREIGN_MARKER, 'Goldman Sachs': FOREIGN_MARKER,
    'JP MORGAN': FOREIGN_MARKER, 'Citibank, NA': FOREIGN_MARKER,
    'Goldman Sachs Group Inc': FOREIGN_MARKER, 'GOLDMAN SACHS': FOREIGN_MARKER,
    'JPM SE': FOREIGN_MARKER, 'Signature Bank/New York NY': FOREIGN_MARKER,
    'Valley National Bank': FOREIGN_MARKER, 'Alpha bank': FOREIGN_MARKER,
    'UBS Switzerland AG': FOREIGN_MARKER, 'First Republic Bank': FOREIGN_MARKER,
    'BNY': FOREIGN_MARKER, 'Valley National Bancorp': FOREIGN_MARKER,
    'Barclays Bank Plc New York': FOREIGN_MARKER,
    'J.P.Morgan Chase Bank N.A. New York': FOREIGN_MARKER,
    'Deutsche Bank AG.': FOREIGN_MARKER, 'Citibank New York': FOREIGN_MARKER,
    'ubs': FOREIGN_MARKER, 'J.P. MORGAN Securities PLC': FOREIGN_MARKER,
    # לא בנקים (edge cases) - לא מותאמים בכלל
    'קופה קטנה': None, 'חיצוני': None, '': None, 'ריק במקור': None, 'סוף מידע': None,
}


def load_bank_reference() -> dict[str, dict]:
    """שם_בנק -> {ח.פ, הערה}."""
    out = {}
    with open(CSV_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["שם_בנק"]] = {"ח.פ": row["ח.פ"] or None, "הערה": row.get("הערה") or ""}
    return out


def resolve_bank(name: str | None, bank_ref: dict[str, dict]) -> str | None:
    """שם בנק כפי שמופיע בדוח -> ח.פ, או None אם זר/לא ידוע/אין ח.פ מאושר."""
    if not name:
        return None
    canon = ALIASES.get(name)
    if canon is None or canon == FOREIGN_MARKER:
        return None
    entry = bank_ref.get(canon)
    if not entry:
        return None
    return entry["ח.פ"]


# בדיקת בנק לרמת שורה בודדת (לשימוש ב-interest.py): מזהה גם "זר" וגם
# "לא ידוע" בנפרד מ"יש ח.פ אבל אין היתר" - 4 מצבים שונים, לא רק שניים.
BANK_UNKNOWN = "unknown"
BANK_FOREIGN = "foreign"
BANK_NO_HETER = "no_heter"
BANK_HETER = "heter"


def classify_bank_row(name: str | None, bank_ref: dict[str, dict], heter_by_chp: dict[str, str]) -> str:
    from .heter_iska import STATUS_NONE  # יבוא מקומי - נמנע מעגל יבוא בזמן טעינה

    if not name:
        return BANK_UNKNOWN
    canon = ALIASES.get(name)
    if canon is None:
        return BANK_UNKNOWN  # שם לא מזוהה כלל (לא ב-ALIASES)
    if canon == FOREIGN_MARKER:
        return BANK_FOREIGN
    entry = bank_ref.get(canon)
    chp = entry["ח.פ"] if entry else None
    if not chp:
        return BANK_UNKNOWN  # בנק ישראלי מזוהה בשם, אבל אין לו ח.פ מאושר (TBD)
    return BANK_HETER if heter_by_chp.get(chp, STATUS_NONE) != STATUS_NONE else BANK_NO_HETER
