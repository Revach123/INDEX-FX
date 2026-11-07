"""דוח קרנות "חוץ" (זרות, לא נסחרות ב-TASE) שלא מסווגות באף שכבה של הפייפליין
(foreign_fund_layers.build_foreign_fractions) - מדורג לפי משקל מצטבר
(סכום "שיעור מסך נכסי ההשקעה" על פני כל השורות/מסלולים בארכיון), כדי
לתעדף אילו קרנות/מנפיקים הכי משתלם להוסיף כמקור חדש.

הרצה: python -m scripts.funds_holdings.missing_foreign_funds [--reports-dir reports] [--top N]
"""
import argparse
from pathlib import Path

from .excel_io import to_ratio
from .file_list import get_file_list
from .foreign_etf_reference import _isin_key
from .foreign_fund_layers import build_foreign_fractions
from .funds import build_funds
from .funds_reference import build_funds_reference
from .isin_swap import build_isin_swap
from .sheet_source import build_source

PLACEHOLDER_PCT = {"", "ריק במקור", "סוף מידע"}


def find_missing(source: list[dict], funds: list[dict], fractions) -> dict[str, dict]:
    names: dict[str, str] = {}
    for rec in source:
        if rec["Category"] not in ("קרנות סל", "קרנות נאמנות"):
            continue
        for row in rec["Clean"]:
            secno = row.get("מספר נייר ערך")
            if secno and secno not in names:
                names[secno] = row.get("שם נייר ערך")

    missing: dict[str, dict] = {}
    for row in funds:
        if row["סוג"] != "חוץ":
            continue
        raw_pct = row.get("שיעור מסך נכסי ההשקעה")
        if isinstance(raw_pct, str) and raw_pct in PLACEHOLDER_PCT:
            continue
        pct = to_ratio(raw_pct)
        if pct is None:
            continue
        isin = _isin_key(row.get("מספר קרן"))
        if isin is None or isin in fractions:
            continue
        d = missing.setdefault(isin, {"total_pct": 0.0, "n_rows": 0, "tracks": set(), "name": names.get(isin)})
        d["total_pct"] += pct
        d["n_rows"] += 1
        d["tracks"].add(row["מפתח"])
    return missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports-dir", type=Path, default=Path("reports"))
    ap.add_argument("--top", type=int, default=60)
    args = ap.parse_args()

    files = get_file_list(args.reports_dir)
    source = build_source(files)

    funds_ref = build_funds_reference()
    isin_swap = build_isin_swap(funds_ref)
    funds = build_funds(source, isin_swap)

    # אותן שכבות בדיוק כמו main / validate (ETF, SEC, שמות, N-PORT, Yahoo, FT, OpenFIGI, מטמון,
    # סיווג הגוף בדוח) - הדוח מציג רק מה שבאמת לא מסווג בפייפליין
    fractions = build_foreign_fractions(source, funds, "missing")[0]

    missing = find_missing(source, funds, fractions)
    ranked = sorted(missing.items(), key=lambda kv: -kv[1]["total_pct"])
    print(f"[missing] {len(missing)} ISIN חוץ לא מזוהים")
    print()
    print(f"{'ISIN':<16}{'משקל מצטבר':>12}{'שורות':>8}{'מסלולים':>10}  שם")
    for isin, d in ranked[: args.top]:
        print(f"{isin:<16}{d['total_pct']*100:11.2f}%{d['n_rows']:8d}{len(d['tracks']):10d}  {d['name'] or ''}")


if __name__ == "__main__":
    main()
