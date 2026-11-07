"""נתוני קרנות: נשלף מ-data_for_site.json ב-revach (private repo), דרך ה-GitHub
Contents API עם PAT לקריאה בלבד - בדיוק כמו התבנית המתועדת ב-README של
MASLULIM ל-manifest.csv.

דרוש: משתנה סביבה PAT - fine-grained personal access token עם הרשאת
Contents: Read בלבד על revach123/revach, מוגדר כ-secret בשם PAT ב-Settings
של MASLULIM.

מקור: revach/scripts/funds_info/build_funds.py - הרשומה המלאה כוללת את
כל 43 השדות (COLUMNS שם), בפורמט {"v": ערך, "c": ""} לכל שדה. כאן שולפים
רק את מה שצריך ל"קרנות"/"קרנות IL": מספר קרן, ISIN, סוג, קרן מחקה,
גלאט הון, עדה חרדית, תשואה כהלכה, הרב דביר, סיווג ראשי.
"""
import base64
import csv
import os

from pathlib import Path

import requests

CONTENTS_URL = "https://api.github.com/repos/Revach123/revach/contents/data_for_site.json"
TOKEN_ENV = "PAT"

FIELDS = [
    "מספר קרן", "ISIN", "סוג", "קרן מחקה",
    "גלאט הון", "עדה חרדית", "תשואה כהלכה", "הרב דביר",
    "סיווג ראשי", "נכס בסיס",
    # שם מעודכן ומנהל הקרן - לתצוגה (holdings_detail): הגופים מדווחים לפעמים שם ישן
    # ("SOURCE S&P 500 UCITS ETF" במקום Invesco S&P 500 UCITS ETF, IE00B3YCGJ38)
    "שם קרן", "מנהל קרן", "סיווג משני",
]


def _cell(rec: dict, key: str):
    """{"v": "...", "c": ""} -> "..." (או None אם ריק, כמו Excel)."""
    c = rec.get(key)
    if not isinstance(c, dict):
        return None
    v = c.get("v")
    return v if v not in (None, "") else None


def fetch_raw(session: requests.Session | None = None) -> list[dict]:
    token = (os.environ.get(TOKEN_ENV) or "").strip()
    if not token:
        raise SystemExit(f"[funds_reference] משתנה הסביבה {TOKEN_ENV} לא מוגדר")
    s = session or requests.Session()
    r = s.get(CONTENTS_URL, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw",
    }, timeout=60)
    r.raise_for_status()
    return r.json()


MERGERS_PATH = Path(__file__).with_name("fund_mergers.csv")


def load_fund_mergers(path: Path = MERGERS_PATH) -> dict[str, str]:
    """מספר קרן ישן -> מספר הקרן שאליה מוזגה ("0" = נסגרה בלי ממשיכה)."""
    try:
        with path.open(encoding="utf-8") as f:
            return {r["old_fund"].strip(): r["new_fund"].strip() for r in csv.DictReader(f)}
    except OSError:
        return {}


def add_merged_aliases(records: list[dict], mergers: dict[str, str]) -> int:
    """רשומה לכל מספר קרן ישן שמוזג, עם נתוני הקרן הממשיכה (גם בשרשרת: ישן -> ביניים -> חדש) -
    כך שדוח שמדווח מספר ישן מתמפה לקרן הנוכחית בכל מקום שמשתמש ברשימת הקרנות."""
    by_num = {str(r.get("מספר קרן")): r for r in records if r.get("מספר קרן")}
    added = 0
    for old in mergers:
        if old in by_num:
            continue
        new, seen = mergers[old], {old}
        while new in mergers and new not in by_num and new not in seen:
            seen.add(new)
            new = mergers[new]
        target = by_num.get(new)
        if target:
            records.append({**target, "מספר קרן": old, "ISIN": None})
            added += 1
    return added


def build_funds_reference(session: requests.Session | None = None) -> list[dict]:
    """רשימת רשומות, רק השדות הרלוונטיים, {v} בלבד (בלי {v,c}), ועוד רשומת כינוי לכל קרן ישנה
    שמוזגה לקרן קיימת (fund_mergers.csv)."""
    raw = fetch_raw(session)
    out = []
    for rec in raw:
        out.append({f: _cell(rec, f) for f in FIELDS})
    added = add_merged_aliases(out, load_fund_mergers())
    print(f"[funds_reference] {added} מספרי קרן ישנים שמוזגו מופו לקרן הממשיכה")
    return out


if __name__ == "__main__":
    data = build_funds_reference()
    print(f"[funds_reference] {len(data)} קרנות")
    if data:
        print("דוגמה:", data[0])
