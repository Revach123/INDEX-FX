"""שלב ב.4 - הרכב הנכסים המלא של כל קרן נאמנות/סל, מהדוח החודשי ב-Maya (קובץ TXT1).

הדוח החודשי שכל מנהל קרנות מגיש מכיל, לכל קרן, שורה לכל "סוג נכס" (קוד רשות ניירות ערך) עם שווי בשקלים ו-% חשיפה.
Revach (exposure.py, לדף funds) שומר ממנו 6 קודים בלבד; כאן נשמר הכל, בלי סינון, כדי למפות פיזי מול נגזרים
בקרנות האקטיביות.

זרימה (אותם endpoints שבהם exposure.py משתמש):
  1. POST /api/v1/reports/mutual-funds  (freeText="דוח חודשי") - רשימת הדוחות בחלון התאריכים, עם דפדוף
  2. לכל דוח שעוד לא נשמר: GET /api/v1/reports/{id}/attachments/file?attachmentType=TXT1
פלט (data/funds_composition/):
  raw/<YYYYMM>/<report_id>.csv.gz   הקובץ כפי שהתקבל (כל העמודות)
  manifest.csv                      report_id, company, report_month, rows, funds, fetched_at, status
  long.csv.gz                       כל השורות מכל הדוחות, עמודות מנורמלות + report_id
הרצה: python scripts/b4_fetch_funds_composition.py [--months 2] [--max-reports N]
הקריאות מזדהות בכנות (User-Agent של הפרויקט); כשל נרשם ב-manifest ולא מפיל את שאר הדוחות.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = "https://maya.tase.co.il"
LIST_URL = BASE + "/api/v1/reports/mutual-funds"
REPORT_URL = BASE + "/api/v1/reports/{id}/attachments/file?attachmentType=TXT1"
UA = "INDEX-FX research (github.com/Revach123/INDEX-FX; monthly fund reports)"
HEADERS = {"accept": "application/json, text/plain, */*", "accept-language": "he-IL",
           "content-type": "application/json", "x-maya-with": "allow", "user-agent": UA}
OUT = Path("data/funds_composition")
HEB_MONTHS = {"ינואר": 1, "פברואר": 2, "מרץ": 3, "מרס": 3, "אפריל": 4, "מאי": 5, "יוני": 6, "יולי": 7,
              "אוגוסט": 8, "ספטמבר": 9, "אוקטובר": 10, "נובמבר": 11, "דצמבר": 12}
MARKS = "‏‎‪‫‬‭‮ "


def clean(s) -> str:
    s = "" if s is None else str(s)
    for m in MARKS:
        s = s.replace(m, "")
    return s.strip()


def month_of(title: str) -> str:
    y = m = 0
    for p in clean(title).replace("-", " ").split():
        if p.isdigit() and len(p) == 4:
            y = int(p)
        elif p in HEB_MONTHS:
            m = HEB_MONTHS[p]
    return f"{y:04d}{m:02d}" if y and m else "000000"


def req(s: requests.Session, method: str, url: str, what: str, **kw) -> requests.Response:
    last = None
    for attempt, wait in enumerate((2, 4, 8, 16, 30, None), 1):
        try:
            r = s.request(method, url, timeout=60, **kw)
            _ = r.content
            if r.status_code in (429, 500, 502, 503, 504) and wait:
                raise RuntimeError(f"HTTP {r.status_code}")
            return r
        except Exception as e:  # noqa: BLE001
            last = e
            if wait is None:
                break
            print(f"  ⚠ {what}: נסיון {attempt} נכשל ({e}); ממתין {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"{what}: {last}")


def list_reports(s: requests.Session, months: int) -> list[dict]:
    now = datetime.now(timezone.utc)
    frm = (now.date().replace(day=1) - timedelta(days=31 * months)).isoformat() + "T22:00:00.000Z"
    to = now.date().isoformat() + "T22:00:00.000Z"
    out, seen = [], set()
    for page in range(1, 200):
        body = {"pageNumber": page, "fromDate": frm, "toDate": to, "noMeetings": False, "isSingle": False,
                "isIntendToTaseMember": False, "by": "company", "freeText": "דוח חודשי", "limit": 30, "offset": (page - 1) * 30}
        r = req(s, "POST", LIST_URL, f"רשימה עמוד {page}", headers=HEADERS, data=json.dumps(body))
        if r.status_code != 200:
            raise RuntimeError(f"רשימה עמוד {page}: HTTP {r.status_code} {r.text[:300]}")
        data = r.json() or []
        new = 0
        for rep in data:
            rid = rep.get("id")
            if rid in seen:
                continue
            seen.add(rid)
            new += 1
            out.append({"report_id": rid, "title": rep.get("title") or "",
                        "company": "; ".join((c.get("name") or "").strip() for c in rep.get("companies") or []),
                        "report_month": month_of(rep.get("title") or "")})
        if not data or new == 0:
            break
        time.sleep(0.3)
    return out


def fetch_txt1(s: requests.Session, rid) -> bytes:
    h = {k: v for k, v in HEADERS.items() if k != "content-type"}
    r = req(s, "GET", REPORT_URL.format(id=rid), f"דוח {rid}", headers=h)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code} {r.text[:200]!r}")
    return r.content


def parse(raw: bytes) -> pd.DataFrame:
    text = raw.decode("utf-8-sig", errors="replace")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return pd.DataFrame()
    hdr = [clean(h) for h in rows[0]]
    df = pd.DataFrame([r + [""] * (len(hdr) - len(r)) for r in rows[1:]], columns=hdr).map(clean)
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=2, help="חלון הדוחות לאחור (חודשים)")
    ap.add_argument("--max-reports", type=int, default=0, help="הגבלה לבדיקה (0 = הכל)")
    a = ap.parse_args()
    (OUT / "raw").mkdir(parents=True, exist_ok=True)
    man_p = OUT / "manifest.csv"
    man = pd.read_csv(man_p, dtype=str) if man_p.exists() else pd.DataFrame(columns=["report_id", "status"])
    done = set(man[man.status == "ok"].report_id.astype(str))
    s = requests.Session()
    reps = list_reports(s, a.months)
    print(f"[b4] {len(reps)} דוחות חודשיים בחלון של {a.months} חודשים; כבר נשמרו {len(done)}", flush=True)
    todo = [r for r in reps if str(r["report_id"]) not in done]
    if a.max_reports:
        todo = todo[: a.max_reports]
    new_rows = []
    for i, r in enumerate(todo, 1):
        rec = dict(r, fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
        try:
            raw = fetch_txt1(s, r["report_id"])
            df = parse(raw)
            p = OUT / "raw" / r["report_month"] / f"{r['report_id']}.csv.gz"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(gzip.compress(raw))
            fund_col = next((c for c in df.columns if "מספר קרן" in c), None)
            rec.update(status="ok", rows=len(df), funds=df[fund_col].nunique() if fund_col else 0, columns="|".join(df.columns))
        except Exception as e:  # noqa: BLE001
            rec.update(status="error", error=str(e)[:300])
        new_rows.append(rec)
        print(f"  [{i}/{len(todo)}] {r['report_id']} {r['company'][:40]} {r['report_month']}: {rec['status']} {rec.get('rows', '')}", flush=True)
        time.sleep(0.3)
    man = pd.concat([man[~man.report_id.astype(str).isin({str(x['report_id']) for x in new_rows})], pd.DataFrame(new_rows)])
    man.to_csv(man_p, index=False)
    # טבלה ארוכה מכל הקבצים שנשמרו
    parts = []
    for p in sorted((OUT / "raw").glob("*/*.csv.gz")):
        df = parse(gzip.decompress(p.read_bytes()))
        if df.empty:
            continue
        df.insert(0, "report_id", p.stem.replace(".csv", ""))
        df.insert(1, "report_month", p.parent.name)
        parts.append(df)
    if parts:
        long = pd.concat(parts, ignore_index=True)
        long.to_csv(OUT / "long.csv.gz", index=False, compression="gzip")
        print(f"[b4] long.csv.gz: {len(long):,} שורות, {len(parts)} דוחות", flush=True)
    ok = sum(1 for x in new_rows if x["status"] == "ok")
    print(f"[b4] נמשכו {ok}/{len(new_rows)} דוחות חדשים", flush=True)
    if new_rows and ok == 0:
        sys.exit("[b4] אף דוח לא נמשך - ר' manifest.csv")


if __name__ == "__main__":
    main()
