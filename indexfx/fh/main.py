"""בניית הטבלה הראשית: שורה למסלול (מפתח), נתוני tracks + כל הטורים שנוספו
גליון-גליון. גם שומר בנפרד את הרשימה המפורטת לכל מסלול (לפתיחה בלחיצה
על הטבלה הראשית בעתיד - לא נכנס לטבלה הראשית עצמה).

הרצה: python -m funds_holdings.main [--reports-dir reports] [--out-dir out]
"""
import argparse
import json
from pathlib import Path

from . import heter_iska as heter_iska_module
from .bonds_detail import build_bonds_detail
from .bonds_heter_reference import build_bonds_heter_by_isin
from .bonds_rank import build_bonds_rank
from .category_pct import build_category_pct
from .derivatives_exposure import (
    DERIVATIVE_CATEGORIES, FUNDED_SWAP_CATEGORY, UNFUNDED_SWAP_CATEGORY,
    build_derivatives_exposure, collect_unresolved_swap_tickers,
)
from .file_list import get_file_list
from .foreign_etf_reference import build_foreign_equity
from .fund_type_convention import add_counted_to_index, fund_type_pct, learn_counted_types, official_at_report
from .foreign_fund_layers import build_foreign_fractions
from .funds import build_funds
from .funds_detail import build_funds_detail
from .funds_il import build_funds_il, build_funds_il_kashrut
from .fund_exposure_reference import fetch_fund_exposure, fetch_tase_stocks
from .alt_asset_reference import build_alt_classes
from .holdings_detail import build_holdings_detail, report_unplaced_funds
from .funds_reference import build_funds_reference
from .index_exposure import (
    DIRECT_EQUITY_CATEGORIES,
    build_index_exposure, build_index_table, report_month_by_key, summarize as summarize_index,
)
from .interest import build_interest
from .isin_swap import build_isin_swap
from .kashrut_rank import NO_KASHRUT, build_kashrut_by_num, build_track_kashrut
from .sheet_source import build_source
from .track_pct_normalize import normalize_track_pct
from .tracks_reference import fetch_tracks, track_key


def build_master_table(
    reports_dir: Path, tracks: list[dict]
) -> tuple[list[dict], dict[str, list[dict]], dict[str, list[dict]], list[dict]]:
    files = get_file_list(reports_dir)
    source = build_source(files)

    # חלק מהחברות מדווחות "שיעור מסך נכסי ההשקעה" כ-% מכל נכסי הקובץ (כל
    # המסלולים יחד), לא % מהמסלול עצמו - ר' תיעוד ב-track_pct_normalize.py.
    rescaled = normalize_track_pct(source)
    print(f"[main] {len(rescaled)} מסלולים נורמלו (שיעור מסך נכסי ההשקעה לא הסתכם ל-100%)")

    funds_ref = build_funds_reference()
    print(f"[main] {len(funds_ref)} קרנות מ-נתוני קרנות (revach)")
    isin_swap = build_isin_swap(funds_ref)

    funds = build_funds(source, isin_swap)
    print(f"[main] {len(funds)} שורות קרנות (מקור_גליונות)")

    heter_by_chp = heter_iska_module.build()
    interest = build_interest(source, heter_by_chp=heter_by_chp)
    category_pct = build_category_pct(source)

    # "שיעור מסך נכסי ההשקעה" בדוחות עבור חוזים עתידיים ועסקאות החלף הוא
    # שיעור השווי ההוגן (מרווח/רווח-הפסד שוטף), לא שיעור החשיפה הכלכלית
    # שהמכשירים האלה יוצרים (leverage). מחליפים את שתי הקטגוריות האלה
    # בחשיפה אמיתית (notional) - שאר הקטגוריות נשארות כשווי-שוק, נכון כבר.
    # מלבד ארבע הקטגוריות עצמן (שמוחלפות), derivatives_exposure מחזיר גם
    # עמודות "אזור חשיפה למניות" חדשות (חוזים/אופציות - נכס-בסיס מניות
    # בלבד, סוואפים על מניות מפוצל Funded/Unfunded) - אלה תמיד מצטרפות
    # (אין להן ערך קודם ב-category_pct), לכן d.update ולא לולאת-סינון.
    derivatives_exposure = build_derivatives_exposure(source)
    for key, cols in derivatives_exposure.items():
        category_pct.setdefault(key, {}).update(cols)

    # "מניות (ישיר)" - סכום מניות מבכ"ל + לא סחיר + כתבי אופציה (קטגוריות מקור נפרדות,
    # ר' category_pct.py), לאזור החשיפה למניות בדשבורד - חשיפה ישירה
    # למניות בודדות/פרטיות, לא דרך קרן/נגזר.
    for key, cols in category_pct.items():
        direct = sum(cols.get(c, 0.0) for c in DIRECT_EQUITY_CATEGORIES)
        if direct:
            cols["מניות (ישיר)"] = direct

    # שקיפות: פילוח SWAP_CATEGORY בין Funded/Unfunded (ר' הערת _swap_exposure
    # ב-derivatives_exposure.py) - דיאגנוסטי בלבד, לא נכנס ל-category_pct
    # (לא ישתתף בחישובי שווי-כולל אחרים שסוכמים את כל category_pct).
    swap_breakdown_cols = {}
    for key, cols in derivatives_exposure.items():
        if FUNDED_SWAP_CATEGORY in cols or UNFUNDED_SWAP_CATEGORY in cols:
            swap_breakdown_cols[key] = {
                FUNDED_SWAP_CATEGORY: cols.get(FUNDED_SWAP_CATEGORY, 0.0),
                UNFUNDED_SWAP_CATEGORY: cols.get(UNFUNDED_SWAP_CATEGORY, 0.0),
            }

    # טיקרים של סוואפ-מדד שלא נמצא להם מקור מחיר עדכני (revach123/INDICES) -
    # לא נכנס לחישוב עצמו (שם נופלים בחזרה למחיר-בפתיחת-העסקה), אלא לדגל
    # "לטיפול" בדשבורד - כדי שאפשר יהיה לעקוב מתי מתווסף מקור לטיקר חדש.
    unresolved_swap_tickers = collect_unresolved_swap_tickers(source)
    print(f"[main] {len(unresolved_swap_tickers)} מסלולים עם טיקר סוואפ-מדד לא ממופה")

    il_sums = build_funds_il(funds, funds_ref)

    # קרנות "חוץ" (לא ישראליות, לא נסחרות ב-TASE - funds_ref לא מזהה אותן
    # בכלל) - מזוהות/מסווגות למניות/אג"ח דרך שני מאגרי ETF זרים ב-revach
    # (אוניברסיטת ETF אירופית + חשיפת ETF אמריקאיות לפי SEC) שלא ממופים
    # כרגע דרך funds_reference.py. מצטרף לאותן עמודות "קרן מחקה - ..." -
    # אין חפיפה עם il_sums (כל שורת קרן מסווגת בדיוק ל-IL/נסחרת/חוץ אחת).
    isin_fractions, etf_universe, sec_exposure, official_names = build_foreign_fractions(source, funds, "main")

    for key, cols in build_foreign_equity(funds, isin_fractions).items():
        d = il_sums.setdefault(key, {})
        for siveg, pct in cols.items():
            d[siveg] = d.get(siveg, 0.0) + pct

    # פירוק החשיפה למניות לפי מדד (ר' index_exposure.py) - אותם רכיבים בדיוק
    # כמו validate_equity_exposure, כל רכיב לפי המדד שמאחוריו.
    index_trace: dict = {}
    fund_exposure, tase_stocks = fetch_fund_exposure(), fetch_tase_stocks()
    index_exp = build_index_exposure(source, funds, funds_ref, isin_fractions, resolve_online=True,
                                     trace=index_trace, fund_exposure=fund_exposure, tase_stocks=tase_stocks,
                                     official_names=official_names)
    # קרנות השקעה שהחברה סופרת כמניות בדיווח הרשמי (ר' fund_type_convention) - נלמד לכל
    # חברה מול "חשיפה למניות" ב-tracks, ומתווסף לפירוק כמדד נפרד
    conventions = learn_counted_types({k: v["total"] for k, v in index_exp.items()},
                                      official_at_report(tracks, track_key, report_month_by_key(source)),
                                      fund_type_pct(source))
    added = add_counted_to_index(index_exp, source, conventions, index_trace)
    print(f"[main] קרנות השקעה שנספרות כמניות: {len(conventions)} חברות ({added} שורות): "
          + "; ".join(f"{co}: {', '.join(t)}" for co, t in sorted(conventions.items())))
    tracks_by_key = {k: t for t in tracks if (k := track_key(t))}
    index_table = build_index_table(index_exp, tracks_by_key, report_month_by_key(source))
    print(f"[main] {len(index_table)} מסלולים עם פירוק חשיפה לפי מדד")
    print(summarize_index(index_table))

    kashrut_by_num = build_kashrut_by_num(funds_ref)
    il_kashrut = build_funds_il_kashrut(funds, funds_ref, kashrut_by_num)
    track_kashrut = build_track_kashrut(funds, kashrut_by_num)
    funds_detail = build_funds_detail(funds, funds_ref)

    bonds_heter_by_isin = build_bonds_heter_by_isin()
    print(f"[main] {len(bonds_heter_by_isin)} ניירות מ-bonds_heter (revach)")
    bonds_rank = build_bonds_rank(source, bonds_heter_by_isin)
    bonds_detail = build_bonds_detail(source, bonds_heter_by_isin)
    # סחורות / נכסים דיגיטליים בקרנות חו"ל בלי הרכב מניות/אג"ח (ר' alt_asset_reference.py)
    report_names: dict[str, str] = {}
    for rec in source:
        if rec["Category"] in ("קרנות נאמנות", "קרנות סל"):
            for r in rec["Clean"]:
                isin = str(r.get("מספר נייר ערך") or "").strip().upper()
                name = str(r.get("שם נייר ערך") or "").strip()
                if isin and len(name) > len(report_names.get(isin, "")):
                    report_names[isin] = name
    alt_candidates = {}
    for f in funds:
        isin = str(f.get("מספר קרן") or "").strip().upper()
        frac = isin_fractions.get(isin) or {}
        if f["סוג"] == "חוץ" and isin and not frac.get("equity") and not frac.get("bond"):
            alt_candidates[isin] = report_names.get(isin, "")
    try:
        from .sec_nport_reference import resolve_isin_to_name
        alt_full_names = resolve_isin_to_name(sorted(alt_candidates))
    except Exception as e:
        print(f"[alt] OpenFIGI לא זמין (שמות מלאים): {e}")
        alt_full_names = {}
    for isin in alt_candidates:
        if isin in official_names:
            alt_full_names.setdefault(isin, official_names[isin])
    alt_classes = build_alt_classes(alt_candidates, etf_universe, alt_full_names)
    holdings_detail = build_holdings_detail(source, isin_swap, funds_ref, isin_fractions, index_trace, alt_classes,
                                            official_names, fund_exposure, tase_stocks)
    print(report_unplaced_funds(holdings_detail))

    rows: dict[str, dict] = {}
    for t in tracks:
        key = track_key(t)
        if key is None:
            continue
        rows[key] = dict(t)
        rows[key]["מפתח"] = key

    def row_for(key: str) -> dict:
        return rows.setdefault(key, {"מפתח": key})

    for key, cols in interest.items():
        row_for(key).update(cols)

    for key, cols in bonds_rank.items():
        row_for(key).update(cols)

    for key, cat_sums in category_pct.items():
        row_for(key).update(cat_sums)

    for key, siveg_sums in il_sums.items():
        row_for(key).update(siveg_sums)

    # כשרות לכל עמודת אחוז-סיווג בנפרד (מוצג בפרונט מתחת לאחוז) - מפתח
    # מסומן בסיומת " |כשרות" כדי לא להתנגש עם מפתח האחוז (siveg) עצמו.
    for key, siveg_kashrut in il_kashrut.items():
        row = row_for(key)
        for siveg, level in siveg_kashrut.items():
            row[f"{siveg} |כשרות"] = level

    for key, level in track_kashrut.items():
        row_for(key)["כשרות"] = level

    for key, tickers in unresolved_swap_tickers.items():
        row_for(key)["סוואפ_מדד_לטיפול"] = sorted(tickers)

    for key, cols in swap_breakdown_cols.items():
        row_for(key).update(cols)

    # שקיפות: "שיעור מסך נכסי ההשקעה" של המסלול הזה לא הסתכם ל-100% בדוח
    # המקורי, ותוקן במכפיל - ר' track_pct_normalize.py.
    for key, scale in rescaled.items():
        row_for(key)["מכפיל_נורמליזציה"] = round(scale, 2)

    # מסלול בלי שום נתוני החזקות בדוחות (לא ב-funds בכלל) = "בלי כשרות",
    # לא "לא ידוע" - אותו עיקרון כמו קרן שלא זוהתה (kashrut_rank.py).
    for row in rows.values():
        row.setdefault("כשרות", NO_KASHRUT)

    return list(rows.values()), funds_detail, bonds_detail, index_table, holdings_detail


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports-dir", type=Path, default=Path("reports"))
    ap.add_argument("--out-dir", type=Path, default=Path("out"))
    args = ap.parse_args()

    tracks = fetch_tracks()
    print(f"[main] {len(tracks)} מסלולים מ-tracks")

    master, funds_detail, bonds_detail, index_table, holdings_detail = build_master_table(args.reports_dir, tracks)
    print(f"[main] {len(master)} שורות בטבלה הראשית")
    print(f"[main] {len(funds_detail)} מסלולים עם רשימת קרנות מפורטת")
    print(f"[main] {len(bonds_detail)} מסלולים עם רשימת אג\"ח מפורטת")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    with open(args.out_dir / "master.json", "w", encoding="utf-8") as f:
        json.dump(master, f, ensure_ascii=False, indent=2)
    with open(args.out_dir / "funds_detail.json", "w", encoding="utf-8") as f:
        json.dump(funds_detail, f, ensure_ascii=False, indent=2)
    with open(args.out_dir / "bonds_detail.json", "w", encoding="utf-8") as f:
        json.dump(bonds_detail, f, ensure_ascii=False, indent=2)
    with open(args.out_dir / "index_exposure.json", "w", encoding="utf-8") as f:
        json.dump(index_table, f, ensure_ascii=False, separators=(",", ":"))
    with open(args.out_dir / "holdings_detail.json", "w", encoding="utf-8") as f:
        json.dump(holdings_detail, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[main] {len(holdings_detail)} מסלולים עם פירוט החזקות מלא -> {args.out_dir}/holdings_detail.json")
    print(f"[main] נשמר -> {args.out_dir}/master.json, {args.out_dir}/funds_detail.json, "
          f"{args.out_dir}/bonds_detail.json, {args.out_dir}/index_exposure.json")


if __name__ == "__main__":
    main()
