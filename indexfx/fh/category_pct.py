"""אחוז השקעה לפי סוג נכס (גליון): סכום 'שיעור מסך נכסי ההשקעה' לכל
(מסלול, קטגוריה), ישירות מ-מקור_גליונות - לא רק לקרנות.

מקור: Autopilot_Section1.m אינו כולל שאילתה כזו - זו הרחבה חדשה, לא חלק
מהעברה נאמנה. שתי קטגוריות (יתרות התחייבות להשקעה, מסגרות אשראי) הן
התחייבויות/מסגרות אשראי, לא נכסים מוחזקים - אין להן עמודת PCT_COL בדוחות
בכלל (אומת מול כל 88 קבצי הדוחות), ולכן לא מופיעות בתוצאה.
"""
from .excel_io import to_ratio
from .sheet_source import PCT_COL


def build_category_pct(source: list[dict]) -> dict[str, dict[str, float]]:
    """מפתח -> {קטגוריה: סכום שיעור מסך נכסי ההשקעה}."""
    sums: dict[str, dict[str, float]] = {}
    for rec in source:
        if rec["מידע"] != "מידע":
            continue
        cat = rec["Category"]
        for row in rec["Clean"]:
            key = row.get("מפתח")
            if key is None:
                continue
            pct = to_ratio(row.get(PCT_COL))
            if pct is None:
                continue  # אין PCT_COL בקטגוריה הזו, או ערך לא תקין
            d = sums.setdefault(key, {})
            d[cat] = d.get(cat, 0.0) + pct

    return sums
