"""כשרות ברמת מסלול: הכי נמוך (הכי פחות מחמיר) מבין כל הקרנות במסלול.

שינוי מכוון (לפי הנחיית המשתמש): "בלי כשרות" היא רמה חמישית מפורשת,
הכי נמוכה ברשימה - קרן בלי שום תג כשרות (או שלא זוהתה בנתוני קרנות
בכלל, כמו קרנות "חוץ" שלא הצטלבו) סופרת כ"בלי כשרות", לא מדולגת.
"""
from .excel_io import text_from
from .funds_classification import FUND_KASHRUT_PRIORITY, fund_kashrut

NO_KASHRUT = "בלי כשרות"
LEVELS = FUND_KASHRUT_PRIORITY + [NO_KASHRUT]  # גלאט הון..הרב דביר, ואז בלי כשרות
_RANK = {level: i for i, level in enumerate(LEVELS)}  # 0 = הכי גבוה


def _fund_number_key(v) -> str | None:
    if v is None:
        return None
    try:
        return text_from(int(float(v)))
    except (TypeError, ValueError):
        return text_from(v)


def build_kashrut_by_num(funds_ref: list[dict]) -> dict[str, str]:
    """מספר קרן -> כשרות הכי גבוהה של אותה קרן (NO_KASHRUT אם אין תג)."""
    out = {}
    for r in funds_ref:
        k = _fund_number_key(r.get("מספר קרן"))
        if k is not None:
            out[k] = fund_kashrut(r) or NO_KASHRUT
    return out


def build_track_kashrut(funds: list[dict], kashrut_by_num: dict[str, str]) -> dict[str, str]:
    """מפתח -> הכשרות הכי נמוכה מבין כל הקרנות שהמסלול מחזיק.

    קרן שלא נמצאה כלל ב-נתוני קרנות (כמו "חוץ" לא-מזוהות) = NO_KASHRUT,
    לא מדולגת - זה בדיוק המקרה שהמשתמש ביקש לכלול.
    """
    worst: dict[str, str] = {}
    for row in funds:
        key = row.get("מפתח")
        if key is None:
            continue
        level = kashrut_by_num.get(_fund_number_key(row.get("מספר קרן")), NO_KASHRUT)
        cur = worst.get(key)
        if cur is None or _RANK[level] > _RANK[cur]:
            worst[key] = level
    return worst
