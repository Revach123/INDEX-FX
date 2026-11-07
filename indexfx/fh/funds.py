"""קרנות: כל שורות "קרנות נאמנות"/"קרנות סל" ממקור_גליונות, מסווגות ל-IL/נסחרת/חוץ.

מקור: Autopilot_Section1.m, שאילתת קרנות (לא קרנות (2) - זהה חוץ מ-isBare
שקיים כאן, ומבוטלת/לא בהיקף).
"""
from .excel_io import text_from

FUND_CATEGORIES = {"קרנות נאמנות", "קרנות סל"}
PLACEHOLDERS = {"ריק במקור", "סוף מידע"}
WS_CHARS = {" ", " ", "\t"}
NOMATCH = object()


def _remove_ws(t: str) -> str:
    for c in WS_CHARS:
        t = t.replace(c, "")
    return t


def _all_digits(t: str) -> bool:
    return t != "" and t.isdigit()


def _int64_from(t: str) -> int:
    """Int64.From: מוריד אפסים מובילים, מקבל גם ייצוג עשרוני נקי ("300.0")."""
    return int(float(t))


def _build_fund_map(isin_swap: list[dict]) -> dict[str, str]:
    """מספר קרן (מנורמל) -> ISIN. FundRows/FundKeyed/FundPairs/FundMap ב-M."""
    out: dict[str, str] = {}
    for row in isin_swap:
        num, isin = row.get("מספר קרן"), row.get("ISIN")
        if num is None or isin is None:
            continue
        t = _remove_ws(text_from(num))
        try:
            k = text_from(_int64_from(t))
        except ValueError:
            k = t.upper()
        out.setdefault(k, isin)  # Table.Distinct שומר את המופע הראשון
    return out


def _build_isin_set(isin_swap: list[dict]) -> set[str]:
    return {
        _remove_ws(text_from(row["ISIN"])).upper()
        for row in isin_swap
        if row.get("ISIN") is not None
    }


def _classify(sec_num_raw, fund_map: dict[str, str], isin_set: set[str]) -> tuple:
    raw = text_from(sec_num_raw).strip().upper()
    compact = _remove_ws(raw)

    is_il = (
        compact.startswith("IL")
        and len(compact) == 12
        and compact[2:4] == "00"
        and _all_digits(compact[2:])
    )
    is_bare = _all_digits(compact) and len(compact) <= 7
    num_key = compact[4:11] if is_il else (compact if is_bare else None)
    is_num = num_key is not None

    if is_num:
        key = _int64_from(num_key)
        key_txt = text_from(key)
    else:
        key = raw
        key_txt = compact

    hit = fund_map.get(key_txt, NOMATCH)
    is_match = hit is not NOMATCH

    fund_number = hit if is_match else key
    if is_num and is_match:
        sug = "נסחרת"
    elif is_num:
        sug = "IL"
    elif compact in isin_set:
        sug = "נסחרת"
    else:
        sug = "חוץ"
    return fund_number, sug


def build_funds(source: list[dict], isin_swap: list[dict]) -> list[dict]:
    fund_map = _build_fund_map(isin_swap)
    isin_set = _build_isin_set(isin_swap)

    out = []
    for rec in source:
        if rec["Category"] not in FUND_CATEGORIES or rec["מידע"] != "מידע":
            continue
        for row in rec["Clean"]:
            sec_num = row.get("מספר נייר ערך")
            if sec_num is None or sec_num == "" or text_from(sec_num).strip() in PLACEHOLDERS:
                continue
            fund_number, sug = _classify(sec_num, fund_map, isin_set)
            out.append({
                "מפתח": row.get("מפתח"),
                "שיעור מסך נכסי ההשקעה": row.get("שיעור מסך נכסי ההשקעה"),
                "מספר קרן": fund_number,
                "סוג": sug,
                "_row": row,  # שורת המקור - לשיוך ההחזקה למדד (index_exposure -> holdings_detail)
            })
    return out
