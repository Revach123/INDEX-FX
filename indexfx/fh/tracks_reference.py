"""נתוני מסלולים (tracks): נשלף חי מ-revach.pages.dev/api/tracks.

אין קובץ JSON מחויב ל-git ב-revach (כמו data_for_site.json של הקרנות) - טבלת
tracks_info.tracks ב-D1 נבנית מחדש בכל ריצה של tracks.yml ולא נשמרת כקובץ.
לכן: קוראים מה-API החי, עם המפתח הפנימי X-Match-Key שעוקף את הגנת ה-Origin
ורף הקצב (guard.js, functions/api/_shared/guard.js) - בדיוק כמו שהמנגנון כבר
נועד לשמש צינורות מהימנים אחרים (functions/api/match.js).

דרוש: משתנה סביבה REVACH_MATCH_KEY - **אותו ערך** שמוגדר כ-MATCH_KEY בסביבת
ה-Cloudflare Pages של revach. זה שלב ידני חד-פעמי: להעתיק את הערך לסוד חדש
בשם REVACH_MATCH_KEY ב-Settings -> Secrets של MASLULIM.

שדות מאומתים בקוד המקור (scripts/tracks/build_tracks.py ב-revach, שורות
417-422, 553-554): "ח.פ. חברה" (COMPANY_LEGAL_ID) ו-"מס' מסלול" (track_number)
קיימים בכל רשומה - זה מה שמאפשר לבנות את ה"מפתח" (legalId_מספרמסלול) שלנו.
שאר שמות השדות בפלט בפועל טרם אומתו מול נתונים חיים (הסביבה הנוכחית חסומה
מגישה לאינטרנט חיצוני) - לבדוק מול הרצה אמיתית לפני שממשיכים לבנות עליהם.
"""
import os

import requests

TRACKS_URL = "https://revach.pages.dev/api/tracks"
MATCH_KEY_ENV = "REVACH_MATCH_KEY"

LEGAL_ID_FIELD = "ח.פ. חברה"
TRACK_NUMBER_FIELD = "מס' מסלול"


def _text_from(v) -> str | None:
    """כמו text_from ב-excel_io.py (לא משותף - המקור כאן API חי, לא Excel) -
    כולל אותו strip() על מרווחים מובילים/סוגרים, כדי שמפתח מ-tracks_reference
    יתאים בוודאות למפתח המקביל שנבנה מקובצי הדוחות (ר' excel_io.text_from)."""
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def fetch_tracks(session: requests.Session | None = None) -> list[dict]:
    key = (os.environ.get(MATCH_KEY_ENV) or "").strip()
    if not key:
        raise SystemExit(f"[tracks_reference] משתנה הסביבה {MATCH_KEY_ENV} לא מוגדר")
    s = session or requests.Session()
    r = s.get(TRACKS_URL, headers={"X-Match-Key": key, "Accept": "application/json"}, timeout=60)
    r.raise_for_status()
    return r.json()


def track_key(rec: dict) -> str | None:
    """מפתח = ח.פ. חברה + "_" + מס' מסלול, כדי להתאים ל"מפתח" של מקור_גליונות."""
    legal = _text_from(rec.get(LEGAL_ID_FIELD))
    num = _text_from(rec.get(TRACK_NUMBER_FIELD))
    if not legal or num is None:
        return None
    return f"{legal}_{num}"


def build_tracks_by_key(session: requests.Session | None = None) -> dict[str, dict]:
    recs = fetch_tracks(session)
    out = {}
    for rec in recs:
        k = track_key(rec)
        if k is None:
            continue
        out[k] = rec
    return out


if __name__ == "__main__":
    import json

    data = fetch_tracks()
    print(f"[tracks_reference] {len(data)} מסלולים")
    if data:
        print("שדות (רשומה ראשונה):", sorted(data[0].keys()))
        print("--- 2 רשומות לדוגמה ---")
        for rec in data[:2]:
            print(json.dumps(rec, ensure_ascii=False, indent=2))
        sample_key = track_key(data[0])
        print(f"--- מפתח לדוגמה: {sample_key} ---")
        with_key = sum(1 for r in data if track_key(r) is not None)
        print(f"רשומות עם מפתח תקין: {with_key}/{len(data)}")
