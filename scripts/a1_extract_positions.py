"""שלב א.1 - חילוץ כל ההחזקות מהדוחות הרבעוניים (MASLULIM/reports) לטבלה אחת מנורמלת.

שורה אחת = החזקה אחת של מסלול. הדוח האחרון לכל חברה+מערכת (gm/pn/in).
לא מחשב חשיפה - רק מנרמל שמות עמודות. הסיווג בשלב א.2.

הרצה: python scripts/a1_extract_positions.py --reports-dir /path/MASLULIM/reports --out data/positions.csv.gz
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indexfx.vendor.canon import canon  # noqa: E402
from indexfx.vendor.file_list import latest_per_company, list_files  # noqa: E402
from indexfx.vendor.sheet_source import build_source  # noqa: E402

# שם עמודה בדוח -> שם אחיד. עמודות שלא קיימות בגיליון נשארות ריקות.
COLS = {
    "שם נייר ערך": "name", "מספר נייר ערך": "sec_id", "שם מנפיק": "issuer",
    "ישראל/חו\"ל": "il_abroad", "מדינה לפי חשיפה כלכלית": "country",
    "מטבע פעילות": "ccy", "שער חליפין": "fx_rate", "שער נייר הערך": "price",
    "ערך נקוב (יחידות)": "units", "שווי הוגן (באלפי ש\"ח)": "fair_value_k",
    "שיעור מסך נכסי ההשקעה": "pct_total", "נכס בסיס": "underlying",
    "נכס בסיס (כתב אופציה)": "underlying",
    "סיווג הקרן": "fund_class", "זירת מסחר": "venue", "מאפיין עיקרי": "main_attr",
    "סוג הנכס": "swap_asset_type", "טיקר": "swap_ticker",
    "פקטור מוביל": "swap_factor", "שווי הוגן (נטו באלפי ש\"ח)": "swap_net_fv_k",
    "מטבע פעילות (רגל 1)": "leg1_ccy", "מטבע פעילות (רגל 2)": "leg2_ccy",
    "ערך נקוב (רגל 1)": "leg1_nominal", "ערך נקוב (רגל 2)": "leg2_nominal",
    "שער חליפין (רגל 1)": "leg1_fx", "שער חליפין (רגל 2)": "leg2_fx",
    "שיעור ריבית עוגן": "swap_anchor_rate", "מועד סיום חוזי": "swap_end",
    "מועד ההתקשרות בעסקה": "swap_start", "תאריך פקיעה": "expiry", "שער מימוש": "strike",
    "סטאטוס סחירות": "tradability", "ענף מסחר": "sector",
}


def extract(reports_dir: Path, all_quarters: bool = False, sheets: set | None = None) -> pd.DataFrame:
    files = list_files(reports_dir) if all_quarters else latest_per_company(list_files(reports_dir))
    print(f"[a1] {len(files)} קבצים אחרונים לפי חברה+מערכת", file=sys.stderr)
    out = []
    for f in sorted(files, key=lambda x: x.name):
        for block in build_source([f]):
            if sheets and block["Category"] not in sheets:
                continue
            if block["מידע"] != "מידע":
                print(f"[a1] אזהרה: {f.name} / {block['Category']}: {block['Clean'][0].get('סיבה')}", file=sys.stderr)
                continue
            for r in block["Clean"]:
                rec = {"legal_id": block["LegalId"], "system": f.company_type.split("_")[1],
                       "report_date": f.report_month.isoformat() if f.report_month else None,
                       "file": f.name, "sheet": block["Category"], "track": r.get("מספר מסלול")}
                for src, dst in COLS.items():
                    if src in r and r[src] not in (None, ""):
                        rec[dst] = r[src]
                out.append(rec)
    return pd.DataFrame(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--all-quarters", action="store_true", help="כל הדוחות (לא רק האחרון לכל חברה)")
    a = ap.parse_args()
    df = extract(a.reports_dir, a.all_quarters)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(a.out, index=False, compression="gzip")
    print(f"[a1] {len(df):,} החזקות, {df.groupby(['legal_id','track']).ngroups} מסלולים -> {a.out}", file=sys.stderr)
