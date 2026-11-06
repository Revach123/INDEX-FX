"""עזרי קריאת Excel: python-calamine, בלי המרת טיפוסים (כמו Excel.Workbook(..., null, true))."""
import io
import re
import zipfile

from python_calamine import CalamineWorkbook

# תא בעמודה של שלוש אותיות (AAA ומעלה, 703+) - הדוחות משתמשים בעשרות עמודות בלבד. תאים
# בודדים בעמודה XFD (16,384) בכל שורה (513026484_gm_0126: 4 גיליונות A1:XFD15824) גורמים
# ל-calamine לבנות 16,384 עמודות לכל שורה - ~8GB לגיליון אחד וקריסת זיכרון.
_FAR_DIMENSION = re.compile(rb'<dimension ref="[A-Z]+\d+:[A-Z]{3}\d+"\s*/>')
_FAR_CELL = re.compile(rb'<c r="[A-Z]{3}\d+"[^>]*?(?:/>|>.*?</c>)', re.S)
_ANY_DIMENSION = re.compile(rb'<dimension ref="[^"]*"\s*/>')


def _trim_far_columns(path) -> io.BytesIO | None:
    """עותק בזיכרון של הקובץ בלי תאים מעמודה AAA והלאה, רק כשיש גיליון שמגיע אליהן."""
    with zipfile.ZipFile(path) as z:
        sheets = [n for n in z.namelist() if n.startswith("xl/worksheets/") and n.endswith(".xml")]
        wide = {n for n in sheets if _FAR_DIMENSION.search(z.open(n).read(4096))}
        if not wide:
            return None
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
            for item in z.infolist():
                data = z.read(item.filename)
                if item.filename in wide:
                    data = _ANY_DIMENSION.sub(b"", _FAR_CELL.sub(b"", data), count=1)
                out.writestr(item, data)
    buf.seek(0)
    return buf


def read_workbook_sheets(path) -> dict[str, list[list]]:
    """שם גיליון -> רשימת שורות (כל שורה = רשימת ערכים גולמיים, בלי המרה)."""
    return read_sheet_rows(path, lambda name: True)


def read_sheet_rows(path, want) -> dict[str, list[list]]:
    """כמו read_workbook_sheets, רק לגיליונות ש-want(שם) מחזיר עבורם True."""
    trimmed = _trim_far_columns(path)
    wb = CalamineWorkbook.from_filelike(trimmed) if trimmed else CalamineWorkbook.from_path(str(path))
    return {name: wb.get_sheet_by_name(name).to_python() for name in wb.sheet_names if want(name)}


def to_ratio(v) -> float | None:
    """שיעור/אחוז לערך יחסי (0.00093), בין אם המקור הוא מספר גולמי (כבר יחסי)
    או טקסט עם % (אז מחלקים ב-100). נמצא בפועל: ~14% מהשורות מגיעות כטקסט
    כמו "0.093%" במקום float גולמי - תלוי בקובץ המקור."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if s.endswith("%"):
        try:
            return float(s[:-1]) / 100
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def text_from(v) -> str | None:
    """Text.From-מקביל: מספרים שלמים בלי .0, שאר הערכים כטקסט (חתוכים מרווחים
    מובילים/סוגרים - נמצא בפועל תא עם "7222 " שמנע התאמה למפתח הרשמי הזהה
    בלעדיו, ר' bare_key_rows probe). None נשאר None."""
    if v is None:
        return None
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float):
        if v.is_integer():
            return str(int(v))
        return repr(v)
    return str(v).strip()
