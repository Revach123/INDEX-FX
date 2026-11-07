"""מקור_גליונות: נרמול הגיליונות הרלוונטיים מכל קובץ, לרשומות מפוענחות.

מקור: Autopilot_Section1.m, שאילתת מקור_גליונות.
תוצאה: רשימת רשומות {Category, LegalId, מידע, Clean}, כאשר Clean היא
רשימת שורות (dict לכל שורה) - מקביל לטבלה המקוננת ב-PQ.
"""
import logging
from pathlib import Path

from .canon import TARGET_SHEETS, canon
from .excel_io import read_workbook_sheets, text_from
from .file_list import ReportFile

logger = logging.getLogger(__name__)

MAX_COLS = 63
SCAN_ROWS = 15
SCAN_COLS = 6
HEADER_MARKER = "מספר מסלול"
LAST_COL_MARKER = "שיעור מסך נכסי ההשקעה"
KEY_COL = "מספר מסלול"
PCT_COL = "שיעור מסך נכסי ההשקעה"
# אותה קבוצת עוגני-placeholder בדיוק כמו PLACEHOLDER_PCT ב-funds.py/funds_il.py/
# foreign_etf_reference.py/missing_foreign_funds.py - "סוף מידע" היה חסר כאן
# בלבד, מה שאפשר לשורת-שוליים (footer) לדלוף כרשומת-מידע אמיתית עם "מפתח"
# מזויף (למשל "513173393_סוף מידע" - נמצא בפועל, ר' bare_key_rows probe):
# הבדיקה על pct_val לא תפסה אותה כי "מספר מסלול" (KEY_COL) עצמו הוא הערך
# שהיה סוף-מידע, לא PCT_COL - ולכן גם KEY_COL נבדק מול אותה קבוצה עכשיו.
PLACEHOLDER_MARKERS = {"", "ריק במקור", "סוף מידע"}
EMPTY_PCT_MARKERS = PLACEHOLDER_MARKERS


def _promote_headers(rows: list[list]) -> tuple[list[str], list[list]]:
    """שורה 0 -> שמות עמודות (עם טיפול בכפילויות כמו PQ: name, name.1, name.2...).
    עמודה בלי שם -> "ColumnN" (N = מיקום 1-based), בהתאמה להתנהגות PQ."""
    header_row = rows[0]
    data_rows = rows[1:]
    names: list[str] = []
    seen: dict[str, int] = {}
    for i, raw in enumerate(header_row):
        base = text_from(raw)
        if base is None or base == "":
            base = f"Column{i + 1}"
        seen[base] = seen.get(base, 0) + 1
        names.append(base if seen[base] == 1 else f"{base}.{seen[base] - 1}")
    return names, data_rows


def _norm_sheet(data: list[list], legal_id: str) -> tuple[str, list[dict]]:
    """מחזיר (status, rows). status = "מידע" או "שגיאה".
    כשל -> רשומת שגיאה יחידה, לפי המבנה שהמשימה דרשה לשמר."""

    def err_row(reason: str) -> tuple[str, list[dict]]:
        return "שגיאה", [{"מפתח": f"{legal_id}_שגיאה", "סטטוס": "שגיאה", "סיבה": reason}]

    if not data:
        return err_row("גיליון ריק")

    ncols = len(data[0])
    safe_n = min(MAX_COLS, ncols)
    sheet = [row[:safe_n] for row in data]

    scan_n = min(SCAN_COLS, safe_n)
    scan_area = [row[:scan_n] for row in sheet[:SCAN_ROWS]]

    hdr_idx = -1
    for i, row in enumerate(scan_area):
        texts = [text_from(c) for c in row]
        if any(t is not None and HEADER_MARKER in t for t in texts):
            hdr_idx = i
            break

    if hdr_idx == -1:
        return err_row("לא נמצאה כותרת 'מספר מסלול'")

    hdr_row_full = sheet[hdr_idx]
    hdr_vals = [text_from(c) for c in hdr_row_full]
    last_idx = -1
    for i, v in enumerate(hdr_vals):
        if v == LAST_COL_MARKER:
            last_idx = i  # Occurrence.Last - ממשיכים לחפש, המופע האחרון מנצח
    keep_n = len(hdr_vals) if last_idx == -1 else last_idx + 1

    narrow = [row[:keep_n] for row in sheet]
    promoted_rows = narrow[hdr_idx:]  # כולל שורת הכותרת עצמה, כמו Table.Skip(narrow, hdrIdx)
    names, data_rows = _promote_headers(promoted_rows)

    keep_idx = [i for i, n in enumerate(names) if n != "" and not n.startswith("Column")]
    clean_names = [names[i] for i in keep_idx]

    has_key = KEY_COL in clean_names
    has_pct = PCT_COL in clean_names

    if not has_key:
        return err_row("אין עמודת 'מספר מסלול' אחרי קידום")

    out_rows = []
    for row in data_rows:
        rec = {clean_names[j]: row[keep_idx[j]] if keep_idx[j] < len(row) else None
               for j in range(len(keep_idx))}
        key_val = rec.get(KEY_COL)
        if key_val is None or key_val in PLACEHOLDER_MARKERS:
            continue
        if has_pct:
            pct_val = rec.get(PCT_COL)
            if pct_val is None or pct_val in EMPTY_PCT_MARKERS:
                continue
        rec["מפתח"] = f"{legal_id}_{text_from(key_val)}"
        rec["סטטוס"] = "מידע"
        out_rows.append(rec)

    return "מידע", out_rows  # גם 0 שורות = "מידע" (גיליון ריק לגיטימי)


def build_source(files: list[ReportFile]) -> list[dict]:
    """Open + Combine: לכל קובץ, לכל גיליון ברשימה הלבנה - רשומה אחת.
    Combined[i] = {"Category", "LegalId", "CompanyType", "מידע", "Clean": [rows...]}."""
    combined: list[dict] = []
    for f in files:
        legal_id = f.name.split("_", 1)[0]
        try:
            sheets = read_workbook_sheets(f.path)
        except Exception as e:  # קובץ פגום - לוג, לא מפיל את כל הריצה
            logger.error("כשל בפתיחת %s: %r", f.path, e)
            combined.append({
                "Category": "_קובץ", "LegalId": legal_id, "מידע": "שגיאה",
                "Clean": [{"מפתח": f"{legal_id}_שגיאה", "סטטוס": "שגיאה",
                           "סיבה": f"כשל בפתיחת הקובץ: {e!r}"}],
            })
            continue

        for name, data in sheets.items():
            if canon(name) not in TARGET_SHEETS:
                continue
            try:
                status, rows = _norm_sheet(data, legal_id)
            except Exception as e:
                logger.error("כשל בנרמול %s / %s: %r", f.path, name, e)
                status, rows = "שגיאה", [{"מפתח": f"{legal_id}_שגיאה", "סטטוס": "שגיאה",
                                          "סיבה": f"שגיאה: {e!r}"}]
            combined.append({
                "Category": canon(name), "LegalId": legal_id, "מידע": status, "Clean": rows,
                "ReportMonth": f.report_month, "CompanyType": f.company_type,
            })
    return combined
