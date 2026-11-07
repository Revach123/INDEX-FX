"""רשימה מלאה לכל מסלול: כל אג"ח/ני"ע שהמסלול מחזיק (מקטגוריות
BOND_CATEGORIES), עם רמת היתר-עסקה/עדה ואחוז השקעה - לפתיחה בלחיצה על
שורת הטבלה הראשית, באותו דפוס כמו funds_detail.py.

בניגוד ל-bonds_rank.py (שממוצע רק ניירות עם ISIN מזוהה), כאן מוצגות
*כל* השורות מהקטגוריות - כולל ניירות עם מספור פנימי/לא-ISIN, לתמונה
מלאה של ההחזקות (רמה = None כשלא ניתן לסווג).
"""
from .bonds_rank import BOND_CATEGORIES, SECNAME_COL, SECNO_COL, SECNO_TYPE_COL, _bond_level
from .excel_io import text_from, to_ratio


def build_bonds_detail(source: list[dict], bonds_heter_by_isin: dict[str, dict]) -> dict[str, list[dict]]:
    """מפתח -> רשימת ניירות: {ISIN, שם נייר, חברה מנפיקה, אחוז השקעה, רמה}."""
    out: dict[str, list[dict]] = {}
    for rec in source:
        if rec["Category"] not in BOND_CATEGORIES or rec["מידע"] != "מידע":
            continue
        for row in rec["Clean"]:
            track = row.get("מספר מסלול")
            if track is None or track == "":
                continue
            key = f"{rec['LegalId']}_{text_from(track)}"

            type_val = row.get(SECNO_TYPE_COL)
            isin = row.get(SECNO_COL)
            is_isin = (type_val is None or type_val == "ISIN") and isinstance(isin, str) and isin.startswith("IL")

            entry = bonds_heter_by_isin.get(isin) if is_isin else None
            level = _bond_level(entry, row.get(SECNAME_COL), isin) if is_isin else None

            out.setdefault(key, []).append({
                "ISIN": isin if is_isin else None,
                "שם נייר": row.get(SECNAME_COL),
                "חברה מנפיקה": entry.get("issuer_name") if entry else None,
                "אחוז השקעה": to_ratio(row.get("שיעור מסך נכסי ההשקעה")),
                "רמה": level,
            })
    return out
