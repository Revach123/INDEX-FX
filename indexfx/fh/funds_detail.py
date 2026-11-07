"""רשימה מלאה לכל מסלול: כל קרן שהמסלול מחזיק, עם כשרות/סיווג/אחוז/נכס בסיס.

לפתיחה בלחיצה על שורת הטבלה הראשית (לפי בקשת המשתמש) - לא מוצג בטבלה
הראשית עצמה.
"""
from .excel_io import to_ratio
from .funds_classification import fund_kashrut, fund_siveg
from .kashrut_rank import NO_KASHRUT, _fund_number_key


def build_funds_detail(funds: list[dict], funds_ref: list[dict]) -> dict[str, list[dict]]:
    """מפתח -> רשימת קרנות: {מספר קרן, סוג, אחוז השקעה, כשרות, סיווג, נכס בסיס}."""
    ref_by_num = {}
    for r in funds_ref:
        k = _fund_number_key(r.get("מספר קרן"))
        if k is not None:
            ref_by_num[k] = r

    out: dict[str, list[dict]] = {}
    for row in funds:
        key = row.get("מפתח")
        if key is None:
            continue
        num_key = _fund_number_key(row.get("מספר קרן"))
        ref = ref_by_num.get(num_key)
        out.setdefault(key, []).append({
            "מספר קרן": row.get("מספר קרן"),
            "סוג": row["סוג"],
            "אחוז השקעה": to_ratio(row.get("שיעור מסך נכסי ההשקעה")),
            "כשרות": (fund_kashrut(ref) or NO_KASHRUT) if ref else NO_KASHRUT,
            "סיווג": fund_siveg(ref) if ref else None,
            "נכס בסיס": ref.get("נכס בסיס") if ref else None,
        })
    return out
