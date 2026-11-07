"""סטטוס היתר עסקה, ממערכת HARAV_LEVIN (business-registry).

מקור: /api/lists?type=companies-all (ציבורי, ללא אימות, ללא הגבלת Origin) -
בדיוק כמו revach/scripts/funds_info/heter_iska.py. דינמי בכל הרצה - לא
נשמר בקובץ קבוע, כי הסטטוס יכול להשתנות (בניגוד לרשימת הבנקים עצמה).
"""
import requests

API_URL = "https://harav-levin.pages.dev/api/lists?type=companies-all"

STATUS_NONE = "אין"
STATUS_PRIVATE = "פרטי"
STATUS_GENERAL = "כללי"

HALACHA_PLACEHOLDER = "מסלול הלכה"


def _legal_id_str(v):
    s = str(v if v is not None else "").strip()
    if not s:
        return ""
    try:
        return str(int(float(s)))
    except ValueError:
        return s


def build(verbose=True) -> dict[str, str]:
    """מחזיר dict: {ח.פ: 'כללי'}. חברה שלא ברשימה - לא מופיעה (ברירת מחדל 'אין')."""
    try:
        r = requests.get(API_URL, timeout=30, verify=False)
        r.raise_for_status()
        payload = r.json()
    except Exception as e:
        if verbose:
            print("אזהרה | היתר עסקה (HARAV_LEVIN) נכשל: %s: %s" % (type(e).__name__, str(e)[:120]))
        return {}

    if not payload.get("ok"):
        if verbose:
            print("אזהרה | היתר עסקה (HARAV_LEVIN) — תשובה לא תקינה: %s" % payload.get("error"))
        return {}

    result = {}
    for row in payload.get("rows", []):
        chp = _legal_id_str(row.get("chp_number"))
        if not chp:
            continue
        permit = (row.get("permit_name") or "").strip()
        registrar = (row.get("registrar_name") or "").strip()
        if permit == HALACHA_PLACEHOLDER or registrar == HALACHA_PLACEHOLDER:
            continue
        result[chp] = STATUS_GENERAL

    if verbose:
        print("היתר עסקה (HARAV_LEVIN) | חברות: %d" % len(result))
    return result
