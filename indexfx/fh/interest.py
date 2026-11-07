"""ריבית: האם למסלול יש חשיפה לריבית ממזומן/פיקדונות, ובאיזו רמת סיכון.

מקור: Autopilot_Section1.m, שאילתת ריבית.
שינויים מכוונים (לפי הנחיית המשתמש):
  1. שתי העמודות המקוריות (ריבית ממזומן / ריבית מפקדונות) מאוחדות
     לבדיקה אחת "יש ריבית" (ממזומן ו/או מפקדונות, לא משנה מאיזה).
  2. עמודה אחת "ריבית" עם ערך מבין 4 רמות (סדר עולה, הכי גרוע ראשון):
     "ריבית בלי הת"ע" < "בנק לא ידוע" < "בנק זר" < "הת"ע" (הכי טוב).
     לכל מסלול נבחר הערך הכי גרוע מבין כל שורות הריבית שלו.
     אם אין למסלול שום שורת ריבית - העמודה נשארת ריקה (המפתח לא מופיע).
"""
import logging

from .bank_names import ALIASES as _KNOWN_NAMES
from .bank_names import (
    BANK_FOREIGN,
    BANK_HETER,
    BANK_NO_HETER,
    BANK_UNKNOWN,
    classify_bank_row,
    load_bank_reference,
)
from .excel_io import text_from
from . import heter_iska as heter_iska_module

logger = logging.getLogger(__name__)

CASH_CATEGORY = "מזומנים ושווי מזומנים"
DEPOSITS_CATEGORY = "פיקדונות מעל 3 חודשים"
INTEREST_CATEGORIES = {CASH_CATEGORY, DEPOSITS_CATEGORY}

INTEREST_COL = "ריבית"

# סדר עולה - הכי גרוע ראשון, הכי טוב אחרון (לפי הנחיית המשתמש).
LEVELS = ['ריבית בלי הת"ע', "בנק לא ידוע", "בנק זר", 'הת"ע']
_RANK = {level: i for i, level in enumerate(LEVELS)}
_LEVEL_BY_CLASS = {
    BANK_NO_HETER: 'ריבית בלי הת"ע',
    BANK_UNKNOWN: "בנק לא ידוע",
    BANK_FOREIGN: "בנק זר",
    BANK_HETER: 'הת"ע',
}


def _rate_num(v):
    """try Number.From(...) otherwise null."""
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build_interest(source: list[dict], heter_by_chp: dict[str, str] | None = None) -> dict[str, dict]:
    """מפתח -> {INTEREST_COL: level}. מפתח בלי חשיפה לריבית - לא מופיע כלל.

    heter_by_chp: תוצאת heter_iska.build() (ניתנת כפרמטר כדי לאפשר בדיקה
    עם מוק, בלי לפגוע ב-API החי בכל הרצה של הפייפליין - נשלף פעם אחת).
    """
    if heter_by_chp is None:
        heter_by_chp = heter_iska_module.build()
    bank_ref = load_bank_reference()

    unmatched_names: set[str] = set()
    worst_rank: dict[str, int] = {}

    for rec in source:
        if rec["Category"] not in INTEREST_CATEGORIES or rec["מידע"] != "מידע":
            continue
        legal_id = rec["LegalId"]
        for row in rec["Clean"]:
            track = row.get("מספר מסלול")
            if track is None or track == "":
                continue
            rate = _rate_num(row.get("שיעור ריבית"))
            if rate is None or rate == 0:
                continue  # אין ריבית בפועל בשורה הזו - לא רלוונטי

            key = f"{legal_id}_{text_from(track)}"
            bank_name = row.get("שם הבנק")
            cls = classify_bank_row(bank_name, bank_ref, heter_by_chp)
            rank = _RANK[_LEVEL_BY_CLASS[cls]]

            if bank_name and bank_name not in _KNOWN_NAMES:
                unmatched_names.add(bank_name)

            prev = worst_rank.get(key)
            if prev is None or rank < prev:
                worst_rank[key] = rank

    if unmatched_names:
        logger.warning("שמות בנק לא מזוהים (לא ב-ALIASES): %s", sorted(unmatched_names))

    return {key: {INTEREST_COL: LEVELS[rank]} for key, rank in worst_rank.items()}
