"""קרנות IL: פיבוט אחוז השקעה לפי סיווג (קרן מחקה - סיווג ראשי), לכל מסלול.

מקור: Autopilot_Section1.m, שאילתת קרנות IL.

תקלה שנמצאה בפועל (לא ניחוש - ר' user report על IE00B3YCGJ38, Invesco S&P
500 UCITS ETF): funds.py._classify מייצר שלוש קטגוריות (IL/נסחרת/חוץ), אבל
עד לתיקון הזה רק IL טופל כאן ורק חוץ טופל ב-foreign_etf_reference.py -
"נסחרת" (ISIN זר שגם רשום עם מספר-קרן ישראלי ב"נתוני קרנות"/MAYA, ר' תיעוד
sug ב-funds.py) לא טופל בשום מקום, נופל בשקט מהחישוב לגמרי. מטופל כאן עכשיו
זהה ל-IL, רק שההצלבה עם funds_ref היא לפי ISIN (ה"מספר קרן" ששורת "נסחרת"
מחזיקה בפועל הוא ה-ISIN הגולמי עצמו, לא מספר קרן ישראלי - ר' funds.py) ולא
לפי מספר קרן."""
from .excel_io import text_from, to_ratio
from .funds_classification import fund_siveg
from .kashrut_rank import NO_KASHRUT, _RANK

PLACEHOLDER_PCT = {"", "ריק במקור", "סוף מידע"}
_IL_OR_TRADED = ("IL", "נסחרת")


def _fund_number_key(v) -> str | None:
    """מנרמל מספר קרן ל-int-כמחרוזת, כדי להצליב בין קרנות (int) לנתוני קרנות (str)."""
    if v is None:
        return None
    try:
        return text_from(int(float(v)))
    except (TypeError, ValueError):
        return text_from(v)


def _isin_key(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip().upper()
    return s or None


def _siveg_lookup(row: dict, siveg_by_num: dict[str, str], siveg_by_isin: dict[str, str]) -> str | None:
    if row["סוג"] == "IL":
        return siveg_by_num.get(_fund_number_key(row.get("מספר קרן")))
    return siveg_by_isin.get(_isin_key(row.get("מספר קרן")))


def build_funds_il(funds: list[dict], funds_ref: list[dict]) -> dict[str, dict[str, float]]:
    """מפתח -> {סיווג: סכום שיעור}."""
    siveg_by_num: dict[str, str] = {}
    siveg_by_isin: dict[str, str] = {}
    for r in funds_ref:
        k = _fund_number_key(r.get("מספר קרן"))
        if k is not None:
            siveg_by_num[k] = fund_siveg(r)
        isin = _isin_key(r.get("ISIN"))
        if isin is not None:
            siveg_by_isin[isin] = fund_siveg(r)

    # קרן ממונפת/בחסר על מדד מניות: נספרת כקרן מחקה מניות (בארץ/בחו"ל) כפול המכפיל
    from .index_exposure import leveraged_equity
    lev_by_num: dict[str, tuple[float, bool]] = {}
    lev_by_isin: dict[str, tuple[float, bool]] = {}
    for r in funds_ref:
        lev = leveraged_equity(r)
        if not lev:
            continue
        k, isin = _fund_number_key(r.get("מספר קרן")), _isin_key(r.get("ISIN"))
        if k is not None:
            lev_by_num[k] = lev
        if isin is not None:
            lev_by_isin[isin] = lev

    sums: dict[str, dict[str, float]] = {}
    for row in funds:
        if row["סוג"] not in _IL_OR_TRADED:
            continue
        raw_pct = row.get("שיעור מסך נכסי ההשקעה")
        if isinstance(raw_pct, str) and raw_pct in PLACEHOLDER_PCT:
            continue
        pct = to_ratio(raw_pct)
        if pct is None:
            continue
        lev = (lev_by_num.get(_fund_number_key(row.get("מספר קרן"))) if row["סוג"] == "IL"
               else lev_by_isin.get(_isin_key(row.get("מספר קרן"))))
        if lev:
            factor, local = lev
            siveg, pct = ("קרן מחקה - מניות בארץ" if local else 'קרן מחקה - מניות בחו"ל'), pct * factor
        else:
            siveg = _siveg_lookup(row, siveg_by_num, siveg_by_isin)
        if siveg is None:
            continue
        key = row["מפתח"]
        d = sums.setdefault(key, {})
        d[siveg] = d.get(siveg, 0.0) + pct

    return sums


def build_funds_il_equity(funds: list[dict], funds_ref: list[dict],
                          fund_exposure: dict[str, float] | None = None,
                          tase_stocks: set[str] | None = None) -> dict[str, float]:
    """מפתח -> חשיפה למניות דרך קרנות ישראליות (IL/נסחרת): שיעור × il_fund_equity - מחקה 1,
    ממונפת פי המכפיל, כל קרן אחרת לפי החשיפה למניות שהיא מדווחת. אותו שבר כמו בפירוק לפי מדד."""
    from .index_exposure import il_fund_equity, misfiled_stock
    ref_by_num = {k: r for r in funds_ref if (k := _fund_number_key(r.get("מספר קרן"))) is not None}
    ref_by_isin = {k: r for r in funds_ref if (k := _isin_key(r.get("ISIN"))) is not None}
    out: dict[str, float] = {}
    for row in funds:
        if row["סוג"] not in _IL_OR_TRADED:
            continue
        raw_pct = row.get("שיעור מסך נכסי ההשקעה")
        if isinstance(raw_pct, str) and raw_pct in PLACEHOLDER_PCT:
            continue
        pct = to_ratio(raw_pct)
        if not pct:
            continue
        r = (ref_by_num.get(_fund_number_key(row.get("מספר קרן"))) if row["סוג"] == "IL"
             else ref_by_isin.get(_isin_key(row.get("מספר קרן"))))
        frac = (il_fund_equity(r, fund_exposure) if r
                else 1.0 if misfiled_stock(row.get("_row") or {}, tase_stocks) else 0.0)
        if frac:
            out[row["מפתח"]] = out.get(row["מפתח"], 0.0) + pct * frac
    return out


def build_funds_il_kashrut(
    funds: list[dict], funds_ref: list[dict], kashrut_by_num: dict[str, str]
) -> dict[str, dict[str, str]]:
    """מפתח -> {סיווג: כשרות הכי-גרועה מבין קרנות ה-IL מאותו סיווג באותו מסלול}.

    שינוי מכוון (לפי הנחיית המשתמש): פירוט כשרות לכל עמודת אחוז-סיווג
    בנפרד, לא רק הכי-גרוע הכולל למסלול (kashrut_rank.build_track_kashrut).
    אותה קבוצת שורות בדיוק כמו build_funds_il (סוג=IL/נסחרת, אחוז תקין,
    סיווג מזוהה) - כדי שהכשרות תתאים לאותן הקרנות שסוכמו לאחוז. "נסחרת"
    מוצלב לפי ISIN, לא מספר קרן (ר' הערת build_funds_il) - כולל כשרות
    (kashrut_by_num עצמו נשאר מספר-קרן-בלבד, נבנה כאן מקומית מקבילה
    לפי ISIN מאותו funds_ref, בלי לשנות את חתימת kashrut_rank.py).
    """
    siveg_by_num: dict[str, str] = {}
    siveg_by_isin: dict[str, str] = {}
    kashrut_by_isin: dict[str, str] = {}
    for r in funds_ref:
        k = _fund_number_key(r.get("מספר קרן"))
        if k is not None:
            siveg_by_num[k] = fund_siveg(r)
        isin = _isin_key(r.get("ISIN"))
        if isin is not None:
            siveg_by_isin[isin] = fund_siveg(r)
            if k is not None:
                kashrut_by_isin[isin] = kashrut_by_num.get(k, NO_KASHRUT)

    worst: dict[str, dict[str, str]] = {}
    for row in funds:
        if row["סוג"] not in _IL_OR_TRADED:
            continue
        raw_pct = row.get("שיעור מסך נכסי ההשקעה")
        if isinstance(raw_pct, str) and raw_pct in PLACEHOLDER_PCT:
            continue
        if to_ratio(raw_pct) is None:
            continue
        siveg = _siveg_lookup(row, siveg_by_num, siveg_by_isin)
        if siveg is None:
            continue
        if row["סוג"] == "IL":
            level = kashrut_by_num.get(_fund_number_key(row.get("מספר קרן")), NO_KASHRUT)
        else:
            level = kashrut_by_isin.get(_isin_key(row.get("מספר קרן")), NO_KASHRUT)
        key = row["מפתח"]
        d = worst.setdefault(key, {})
        cur = d.get(siveg)
        if cur is None or _RANK[level] > _RANK[cur]:
            d[siveg] = level

    return worst
