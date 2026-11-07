"""פירוט החזקות מלא לכל מסלול: כל שורה מכל גיליון בדוח, עם החשיפה למניות של השורה
(מניה ישירה / חלק המניות של קרן / נוציונל נגזר) - אותו חישוב בדיוק כמו
validate_equity_exposure ו-index_exposure. לדף המסלול ב-revach (/track_holdings).

מבנה לכל מפתח:
  {"period": "YYYYMM", "cats": [שמות גיליונות], "cols": [...], "rows": [[...], ...],
   "summary": {"by_cat": {גיליון: %}, "equity": {רכיב: %}}}
שורה = רשימה (לא אובייקט - חיסכון של ~60% בנפח ב-D1), לפי HOLDING_COLS.
"""
import re
from collections import defaultdict

from .derivatives_exposure import (
    FUTURES_CATEGORY, OPTIONS_LISTED_CATEGORY, OPTIONS_OTC_CATEGORY, SWAP_CATEGORY,
    SWAP_EQUITY_ASSET_TYPE, _futures_exposure, _options_exposure, _swap_exposure, total_assets_by_key,
)
from .excel_io import text_from, to_ratio
from .funds import FUND_CATEGORIES, PLACEHOLDERS, _build_fund_map, _build_isin_set, _classify
from .foreign_etf_reference import _classify_by_report_name
from .index_exposure import (
    DIRECT_EQUITY_CATEGORIES, equity_row_index, foreign_fund_index, il_fund_equity, il_fund_indices, index_geo, is_local, misfiled_stock,
    report_month_by_key,
)
from .sheet_source import PCT_COL

# עמודות השורה: גיליון (אינדקס ל-cats), שם, מספר נייר, מנפיק, % מהנכסים, שווי (אלפי ש"ח),
# מטבע, מדינה, פרט (דירוג+פדיון לאג"ח / נכס בסיס לנגזר / סוג), חשיפה למניות, רכיב חשיפה,
# והשיוך למדד: [[מזהה מדד, חשיפה], ...] - מאותו חישוב בדיוק כמו פירוק החשיפה לפי מדד, וסיווג
# לשאר הנכסים (ר' _classify_row): cash / deposit / bond_gov_il / bond_corp_abroad... / commodity / digital /
# loan_member / loan_individual / loan_corp / loan_other / rates (ריבית ואשראי) /
# fx / private / realestate / alt / commit
HOLDING_COLS = ["cat", "name", "id", "issuer", "pct", "value", "ccy", "country", "info", "equity", "component", "idx", "cls"]

NAME_COLS = ("שם נייר ערך", "שם הלוואה", "שם קרן השקעה", "שם הבנק", "טיקר", "שם מנפיק", "מאפיין עיקרי")
ID_COLS = ("מספר נייר ערך", "מספר הלוואה", "מספר מזהה בנק", "מספר עסקה (רגל 1)")
VALUE_COLS = ('שווי הוגן (באלפי ש"ח)', 'שווי הנכסים באפיק (באלפי ש"ח)', 'שווי הוגן (נטו באלפי ש"ח)',
              'עלות מופחתת (באלפי ש"ח)', 'יתרת המחויבות לתקופת הדיווח (באלפי ש"ח)')
CCY_COLS = ("מטבע פעילות", "מטבע פעילות (רגל 1)")
INFO_COLS = ("נכס בסיס", "סוג הנכס", "מאפיין עיקרי", "ענף מסחר")


def _first(row: dict, cols) -> object:
    for c in cols:
        v = row.get(c)
        if v not in (None, "") and text_from(v).strip() not in PLACEHOLDERS:
            return v
    return None


def _round(v, nd):
    return round(v, nd) if isinstance(v, (int, float)) else None


def _info(row: dict) -> str | None:
    parts = []
    rating = row.get("דירוג")
    if rating not in (None, "") and text_from(rating).strip() not in PLACEHOLDERS:
        parts.append(text_from(rating).strip())
    mat = row.get("מועד פדיון")
    if hasattr(mat, "strftime"):
        parts.append(mat.strftime("%m/%Y"))
    for c in INFO_COLS:
        v = row.get(c)
        if v not in (None, "") and text_from(v).strip() not in PLACEHOLDERS:
            parts.append(text_from(v).strip())
            break
    return " · ".join(parts) or None


# סיווג "שאר הנכסים" לדף המסלול
CASH_CATEGORY, DEPOSIT_CATEGORY = "מזומנים ושווי מזומנים", "פיקדונות מעל 3 חודשים"
GOV_BOND_CATEGORIES = {"איגרות חוב ממשלתיות", "לא סחיר איגרות חוב ממשלתיות", "לא סחיר איגרות חוב מיועדות"}
CORP_BOND_CATEGORIES = {"איגרות חוב", "לא סחיר איגרות חוב", "ניירות ערך מסחריים", "לא סחיר ניירות ערך מסחריים"}
FX_UNDERLYING = 'מט"ח'
# שאר הנכסים לפי גיליון: אשראי פרטי, השקעות פרטיות, נדל"ן, התחייבויות להשקעה (לא נכס - בלי %)
CATEGORY_CLASS = {"לא סחיר מוצרים מובנים": "rates", "מוצרים מובנים": "rates", "מסגרות אשראי": "rates",
                  "קרנות השקעה": "private", "זכויות מקרקעין": "realestate",
                  "יתרות התחייבות להשקעה": "commit"}
# הלוואות - לפי "מאפיין עיקרי" בדוח (loan_member / loan_individual / loan_corp / loan_other)
LOANS_CATEGORY = "הלוואות"
LOAN_KIND = {"עמית/מבוטח": "member", "יחיד שאינו עמית/מבוטח": "individual", "תאגיד": "corp"}
# נגזר (חוזה / סוואפ / אופציה) על ריבית ואג"ח או על המדד - "ריבית ואשראי"
RATES_UNDERLYINGS = {'ריבית ואג"ח', "מדד המחירים לצרכן"}
_ALT_FUND_NAME = re.compile(r"MACRO|FEEDER|HEDGE|LONG\W?SHORT|ABSOLUTE\W?RETURN|MULTI\W?STRAT", re.IGNORECASE)
_CREDIT_FUND_NAME = re.compile(r"\bP2P\b|PEER\W?TO\W?PEER|DIRECT\W?LENDING|PRIVATE\W?CREDIT|PRIVATE\W?DEBT", re.IGNORECASE)
# קרן כספית בחו"ל בלי סיווג/הרכב (State Street USD LIQ LVNAV, BlackRock ICS US Treasury, JP Morgan
# Liquidity) - אג"ח קצר, כמו כספית בארץ
_MONEY_FUND_NAME = re.compile(r"LIQUIDITY|\bLIQ\b|LVNAV|CNAV|MONEY\W?MARKET|\bMMF\b|\bICS\b|כספית", re.IGNORECASE)
_GOV_NAME = re.compile(r"TREASUR|\bGOVT?\b|GOVERNMENT|SOVEREIGN|\bT-?BILL|ממשל|מדינה|מק\"?מ", re.IGNORECASE)


def _bond_loc(row: dict) -> str:
    country = str(row.get("מדינה לפי חשיפה כלכלית") or "").strip()
    if country:
        return "il" if country == "ישראל" else "abroad"
    return "abroad" if 'חו"ל' in str(row.get('ישראל/חו"ל') or "") else "il"


def _classify_row(cat: str, row: dict, name, fund_ref: dict | None, fund_frac: dict | None,
                  alt_class: str | None = None) -> str | None:
    """מזומן/פיקדון, אג"ח (ממשלתי/קונצרני × בארץ/בחו"ל - כולל קרנות אג"ח וכספיות), סחורות, נכסים דיגיטליים,
    גידור מט"ח."""
    if cat == LOANS_CATEGORY:
        return "loan_" + LOAN_KIND.get(str(row.get("מאפיין עיקרי") or "").strip(), "other")
    if cat in CATEGORY_CLASS:
        # מוצר מובנה על מניות - לא אשראי
        if CATEGORY_CLASS[cat] == "rates" and "מניות" in str(row.get("נכס בסיס") or ""):
            return None
        return CATEGORY_CLASS[cat]
    if cat == CASH_CATEGORY:
        return "cash"
    if cat == DEPOSIT_CATEGORY:
        return "deposit"
    if cat in GOV_BOND_CATEGORIES:
        return "bond_gov_" + _bond_loc(row)
    if cat in CORP_BOND_CATEGORIES:
        return "bond_corp_" + _bond_loc(row)
    if cat in FUND_CATEGORIES:
        if fund_ref:
            main = str(fund_ref.get("סיווג ראשי") or "")
            sub = str(fund_ref.get("סיווג משני") or "")
            if main.startswith("קרן כספית"):
                # קרן כספית = אג"ח קצר (מק"מ / ממשלתי קצר; "עם קונצרני" - גם קונצרני)
                return "bond_corp_il" if "קונצרני" in sub else "bond_gov_il"
            if main.startswith("סחורות"):
                return "commodity"  # זהב/כסף/נפט/מדד סחורות
            if main.startswith("נכסים דיגיטליים"):
                return "digital"  # ביטקוין/אתריום
            if main.startswith(("גידור", "גמישות")):
                return "alt"  # קרנות גידור / גמישות
            if main.startswith('אג"ח'):
                kind = "gov" if ("מדינה" in sub or "ממשל" in sub) else "corp"
                return f"bond_{kind}_" + ("abroad" if 'חו"ל' in main else "il")
            return None
        if alt_class:
            return alt_class  # סחורות / נכסים דיגיטליים (alt_asset_reference)
        if not (fund_frac or {}).get("equity"):
            if _CREDIT_FUND_NAME.search(str(name or "")):
                return "rates"  # קרן אשראי: P2P / הלוואות ישירות
            if _ALT_FUND_NAME.search(str(name or "")):
                return "alt"  # קרן גידור / מאקרו / feeder
        frac = fund_frac or {}
        if (frac.get("bond") or 0) >= 0.5 and (frac.get("equity") or 0) < 0.5:
            return ("bond_gov_" if _GOV_NAME.search(str(name or "")) else "bond_corp_") + "abroad"
        if not frac.get("equity") and _classify_by_report_name(str(name or "")) == "bond":
            # אג"ח לפי השם (הרשמי): Mortgage-Backed / Bond / Treasury - ההרכב בטבלת SEC 0/0
            return ("bond_gov_" if _GOV_NAME.search(str(name or "")) else "bond_corp_") + "abroad"
        if not frac.get("equity") and _MONEY_FUND_NAME.search(str(name or "")):
            return ("bond_gov_" if _GOV_NAME.search(str(name or "")) else "bond_corp_") + _bond_loc(row)
        return None
    for col in ("נכס בסיס", "סוג הנכס"):
        if row.get(col) == FX_UNDERLYING:
            return "fx"
        if str(row.get(col) or "").strip() in RATES_UNDERLYINGS:
            return "rates"
    return None


FUND_KIND_LABEL = {"IL": "קרן ישראלית", "נסחרת": "נסחרת בת\"א", "חוץ": "קרן חו\"ל"}


def _fund_lookup(row: dict, fund_map, isin_set, ref_by_num, ref_by_isin) -> tuple[str | None, dict | None]:
    """(סוג: IL / נסחרת / חוץ, רשומת הקרן בהפניה של revach אם יש) - כמו build_funds."""
    sec_num = row.get("מספר נייר ערך")
    if sec_num is None or sec_num == "" or text_from(sec_num).strip() in PLACEHOLDERS:
        return None, None
    fund_number, sug = _classify(sec_num, fund_map, isin_set)
    num = str(fund_number or "").strip()
    ref = ref_by_num.get(num) or ref_by_isin.get(num.upper())
    if ref is None:
        ref = ref_by_isin.get(text_from(sec_num).strip().upper())
    return sug, ref


def _fund_equity_fraction(row: dict, fund_map, isin_set, ref_by_num, ref_by_isin, isin_fractions,
                          fund_exposure=None, tase_stocks=None) -> tuple[float, str]:
    """(שבר מניות, רכיב) לשורת קרן - כמו validate_equity_exposure: IL/נסחרת בסיווג
    מחקה-מניות = 1, חוץ = שבר המניות מהשכבות (ETF/SEC/Yahoo/OpenFIGI)."""
    sec_num = row.get("מספר נייר ערך")
    if sec_num is None or sec_num == "" or text_from(sec_num).strip() in PLACEHOLDERS:
        return 0.0, ""
    fund_number, sug = _classify(sec_num, fund_map, isin_set)
    num = str(fund_number or "").strip()
    if sug in ("IL", "נסחרת"):
        r = ref_by_num.get(num) or ref_by_isin.get(num.upper())
        if not r and misfiled_stock(row, tase_stocks):
            return 1.0, "direct"  # מניה בת"א שדווחה בגיליון קרנות
        frac = il_fund_equity(r, fund_exposure) if r else 0.0  # מחקה / ממונפת / חשיפה מדווחת
        return (frac, "funds_il") if frac else (0.0, "")
    frac = (isin_fractions.get(num.upper()) or {}).get("equity") or 0.0
    return float(frac), ("funds_foreign" if frac else "")


def _fund_index(row: dict, name, fund_map, isin_set, ref_by_num, ref_by_isin,
                official_names: dict[str, str], isin_fractions: dict[str, dict]) -> tuple[str, str] | None:
    """(מדד, שם) הראשי של קרן - כמו בפירוק לפי מדד: ישראלית לפי נכס הבסיס, חו"ל לפי השם."""
    sug, ref = _fund_lookup(row, fund_map, isin_set, ref_by_num, ref_by_isin)
    if ref:
        parts = il_fund_indices(ref)
        return parts[0][:2] if parts else None
    isin = text_from(row.get("מספר נייר ערך") or "").strip().upper()
    text = text_from(name).strip() if name is not None else ""
    return foreign_fund_index(isin_fractions.get(isin) or {}, text or isin, official_names.get(isin),
                              row.get("מדינה לפי חשיפה כלכלית"))


def _derivative_exposure(source: list[dict]) -> dict[int, tuple[float, bool, str]]:
    """id(שורה) -> (חשיפה כשבר מנכסי המסלול, האם מניות, רכיב)."""
    totals = total_assets_by_key(source)
    out: dict[int, tuple[float, bool, str]] = {}
    fut: list[dict] = []
    _futures_exposure(source, totals, fut)
    for d in fut:
        out[id(d["row"])] = (d["ratio"], bool(d["equity"]), "futures")
    sw: list[dict] = []
    _swap_exposure(source, totals, sw)
    for d in sw:
        out[id(d["row"])] = (d["ratio"], bool(d["equity"]), "swaps")
    for cat in (OPTIONS_LISTED_CATEGORY, OPTIONS_OTC_CATEGORY):
        opt: list[dict] = []
        _options_exposure(source, totals, cat, opt)
        for d in opt:
            out[id(d["row"])] = (d["ratio"], True, "options")
    return out


def _index_meta(idx: str, label: str) -> dict:
    meta = {"label": label, "il": is_local(idx)}
    geo = index_geo(idx)
    if geo:
        meta["geo"], meta["kind"] = geo
    return meta


def build_holdings_detail(source: list[dict], isin_swap: list[dict], funds_ref: list[dict],
                          isin_fractions: dict[str, dict], index_trace: dict | None = None,
                          alt_classes: dict[str, str] | None = None,
                          official_names: dict[str, str] | None = None,
                          fund_exposure: dict[str, float] | None = None,
                          tase_stocks: set[str] | None = None) -> dict[str, dict]:
    """index_trace: מ-build_index_exposure(trace=...) - שיוך כל שורה למדד/ים שלה.
    official_names: ISIN -> שם רשמי לקרן חו"ל (official_fund_names) - במקום השם שהגוף דיווח."""
    official_names = official_names or {}
    fund_map, isin_set = _build_fund_map(isin_swap), _build_isin_set(isin_swap)
    trace_rows = (index_trace or {}).get("rows", {})
    trace_labels = dict((index_trace or {}).get("labels", {}))
    used_idx: dict[str, set[str]] = defaultdict(set)
    ref_by_num = {str(r["מספר קרן"]): r for r in funds_ref if r.get("מספר קרן")}
    ref_by_isin = {str(r["ISIN"]).upper(): r for r in funds_ref if r.get("ISIN")}
    deriv = _derivative_exposure(source)
    period = report_month_by_key(source)

    cats_by_key: dict[str, list[str]] = defaultdict(list)
    rows_by_key: dict[str, list[list]] = defaultdict(list)
    by_cat: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    equity: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for rec in source:
        if rec["מידע"] != "מידע":
            continue
        cat = rec["Category"]
        for row in rec["Clean"]:
            key = row.get("מפתח")
            if key is None:
                continue
            pct = to_ratio(row.get(PCT_COL))
            value = _first(row, VALUE_COLS)
            value = value if isinstance(value, (int, float)) else None
            name = _first(row, NAME_COLS)
            if not pct and not value and name is None:
                continue  # שורת מילוי ריקה ("ריק במקור", מסגרת אשראי 0)

            eq, comp, frac = 0.0, "", 0.0
            if cat in DIRECT_EQUITY_CATEGORIES:
                eq, comp = (pct or 0.0), "direct"
            elif cat in FUND_CATEGORIES:
                frac, comp = _fund_equity_fraction(row, fund_map, isin_set, ref_by_num, ref_by_isin, isin_fractions,
                                                   fund_exposure, tase_stocks)
                eq = (pct or 0.0) * frac
            elif id(row) in deriv:
                ratio, is_eq, comp = deriv[id(row)]
                eq = ratio if is_eq else 0.0
                if not is_eq:
                    comp = comp + ":other"  # חשיפה (נוציונל) לא-מנייתית - מוצגת, לא נספרת

            idx_list = None
            parts = trace_rows.get(id(row))
            if parts:
                agg: dict[str, float] = defaultdict(float)
                for i, v in parts:
                    agg[i] += v
                idx_list = [[i, round(v, 6)] for i, v in sorted(agg.items(), key=lambda x: -abs(x[1]))]
                used_idx[key].update(agg)
                eq = sum(agg.values())  # אותה חשיפה כמו בפירוק לפי מדד
            else:
                # שורה מנייתית בלי חשיפה (מניה ב-0%, אופציה שפוקעת ביום הדוח) - שייכת למדד שלה
                # בחשיפה 0, לא לשאר הנכסים
                found = equity_row_index(cat, row)
                if not found and cat in FUND_CATEGORIES and frac:
                    # קרן מניות ב-0% (החזקה זניחה שעוגלה) - למדד שלה, לא ל"קרנות סל"
                    found = _fund_index(row, name, fund_map, isin_set, ref_by_num, ref_by_isin, official_names, isin_fractions)
                if found:
                    i, label = found
                    trace_labels.setdefault(i, label)
                    idx_list = [[i, 0.0]]
                    used_idx[key].add(i)

            cats = cats_by_key[key]
            if cat not in cats:
                cats.append(cat)
            issuer = row.get("שם מנפיק") or row.get("שם שותף כללי קרן השקעות")
            info = _info(row)
            fund_ref_row = None
            if cat in FUND_CATEGORIES:
                # קרן מזוהה בהפניה של revach: השם המעודכן ומנהל הקרן במקום מה שהגוף דיווח
                # (שם ישן / קטוע / בלומברג); השם שבדוח נשמר בפרטים
                sug, ref = _fund_lookup(row, fund_map, isin_set, ref_by_num, ref_by_isin)
                fund_ref_row = ref
                parts = [FUND_KIND_LABEL.get(sug, "")] if sug else []
                if not ref and misfiled_stock(row, tase_stocks):
                    parts = ['מניה בת"א (דווחה כקרן)']
                official = (ref or {}).get("שם קרן") or (
                    official_names.get(text_from(row.get("מספר נייר ערך") or "").strip().upper()) if sug == "חוץ" else None)
                if official:
                    reported = text_from(name).strip() if name is not None else ""
                    if reported and reported.upper() != str(official).strip().upper():
                        parts.append("בדוח: " + reported)
                    name = official
                if ref and ref.get("שם קרן"):
                    issuer = ref.get("מנהל קרן") or issuer
                if ref and ref.get("נכס בסיס"):
                    parts.append(str(ref["נכס בסיס"]))
                info = " · ".join(p for p in parts if p) or info
            rows_by_key[key].append([
                cats.index(cat),
                text_from(name).strip() if name is not None else None,
                text_from(_first(row, ID_COLS)).strip() if _first(row, ID_COLS) is not None else None,
                text_from(issuer).strip() if issuer not in (None, "") and issuer != name else None,
                _round(pct, 6),
                _round(value, 1),
                _first(row, CCY_COLS),
                row.get("מדינה לפי חשיפה כלכלית") or row.get('ישראל/חו"ל'),
                info,
                _round(eq, 6) if eq else (_round(deriv[id(row)][0], 6) if comp.endswith(":other") else None),
                comp or None,
                idx_list,
                _classify_row(cat, row, name, fund_ref_row,
                              isin_fractions.get(text_from(row.get("מספר נייר ערך") or "").strip().upper())
                              if cat in FUND_CATEGORIES else None,
                              (alt_classes or {}).get(text_from(row.get("מספר נייר ערך") or "").strip().upper())
                              if cat in FUND_CATEGORIES else None),
            ])
            if pct:
                by_cat[key][cat] += pct
            if eq and not comp.endswith(":other"):
                equity[key][comp] += eq

    out = {}
    for key, rows in rows_by_key.items():
        out[key] = {
            "period": period.get(key),
            "cats": cats_by_key[key],
            "cols": HOLDING_COLS,
            "rows": rows,
            "indices": {i: _index_meta(i, trace_labels.get(i, i)) for i in sorted(used_idx[key])},
            "summary": {
                "by_cat": {c: round(v, 6) for c, v in by_cat[key].items()},
                "equity": {c: round(v, 6) for c, v in equity[key].items()},
            },
        }
    return out


def report_unplaced_funds(holdings: dict[str, dict], top: int = 25) -> str:
    """אבחון: שורות קרן (סל/נאמנות) בלי מדד ובלי סיווג - בדף הן נשארות תחת "קרנות סל"/"קרנות נאמנות"
    ולא במניות/אג"ח. מקובץ לפי סוג הקרן והסיבה, והגדולות (משקל מצטבר על פני המסלולים)."""
    from collections import Counter
    by_reason: Counter = Counter()
    by_fund: Counter = Counter()
    n_all = n_left = 0
    for h in holdings.values():
        C = {c: i for i, c in enumerate(h["cols"])}
        for r in h["rows"]:
            if h["cats"][r[C["cat"]]] not in FUND_CATEGORIES:
                continue
            n_all += 1
            if r[C["idx"]] or r[C["cls"]]:
                continue
            n_left += 1
            pct = r[C["pct"]] or 0.0
            reason = (r[C["info"]] or "").split(" · ")[0] or "ללא פרטים"
            by_reason[reason] += pct
            by_fund[(r[C["id"]], r[C["name"]], reason)] += pct
    lines = [f"[holdings] שורות קרן בלי מדד וסיווג: {n_left} מתוך {n_all}"]
    lines += [f"[holdings]   {v*100:8.2f}%  {k}" for k, v in by_reason.most_common(12)]
    lines += [f"[holdings]   {v*100:8.2f}%  {k[0]} | {k[1]} | {k[2]}" for k, v in by_fund.most_common(top)]
    return "\n".join(lines)

