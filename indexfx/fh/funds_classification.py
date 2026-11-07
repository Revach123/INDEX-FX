"""נגזרות מ"נתוני קרנות": כשרות לכל קרן (לרמת הקרן הבודדת), וסיווג משולב.

מקור: Autopilot_Section1.m, שאילתת נתוני קרנות (Added Conditional Column1,
Merged Columns). "Custom"/"Custom.1" שם לא נצרכו בהמשך אז לא הוצגו -
"Custom.1" (שרשרת הכשרות) בדיוק מה שדרוש עכשיו לרמת הקרן הבודדת.

שינוי מכוון: המשתמש הוסיף רמה חמישית מפורשת "בלי כשרות" (הכי נמוכה),
לרמת המסלול - ר' kashrut_rank.py.
"""

# סדר עדיפות לרמת קרן בודדת (מ-M: אם יש כמה תגים, גלאט הון גובר).
FUND_KASHRUT_PRIORITY = ["גלאט הון", "עדה חרדית", "תשואה כהלכה", "הרב דביר"]


def fund_kashrut(fund_ref: dict) -> str | None:
    """הכי גבוה (Custom.1 מ-M): גלאט הון > עדה חרדית > תשואה כהלכה > הרב דביר > None."""
    for level, field in zip(FUND_KASHRUT_PRIORITY, ["גלאט הון", "עדה חרדית", "תשואה כהלכה", "הרב דביר"]):
        if fund_ref.get(field) is not None:
            return level
    return None


def fund_siveg(fund_ref: dict) -> str:
    """סיווג = קרן מחקה & " - " & סיווג ראשי (Merged Columns ב-M)."""
    machka = fund_ref.get("קרן מחקה") or ""
    rashi = fund_ref.get("סיווג ראשי") or ""
    return f"{machka} - {rashi}"


# קרן ממונפת / בחסר ("סיווג ראשי" + "סיווג משני" בנתוני קרנות): מכפיל החשיפה לנכס הבסיס
# (ת"א 35 פי 3 -> 3, "בחסר" -> -1). "ממונפות בסיכון גבוה"/"ממונפות אחר" - בלי מכפיל מפורש.
LEVERAGE_FACTOR = {
    ("מינוף", "פי 3"): 3.0, ("מינוף", "פי 2"): 2.0,
    ("מינוף בחסר", "בחסר"): -1.0, ("מינוף בחסר", "בחסר פי 2"): -2.0,
}


def leverage_factor(fund_ref: dict) -> float | None:
    main = str(fund_ref.get("סיווג ראשי") or "").strip()
    sub = str(fund_ref.get("סיווג משני") or "").strip()
    return LEVERAGE_FACTOR.get((main, sub))

