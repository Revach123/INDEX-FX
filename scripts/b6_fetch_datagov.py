"""שלב ב.6 - סדרה חודשית רשמית לכל מסלול מ-data.gov.il (גמל-נט / פנסיה-נט / ביטוח-נט).

השדות שנשמרים (כל החודשים מ---from): מזהה מסלול וחברה, תקופה, נכסים, תשואה חודשית,
STOCK_MARKET_EXPOSURE (חשיפה למניות), FOREIGN_EXPOSURE (חשיפה לחו"ל), FOREIGN_CURRENCY_EXPOSURE (חשיפה למט"ח).
אותם מאגרים שבהם Revach/scripts/tracks/fetch_datagov.py משתמש; כאן עם אימות TLS רגיל ומזהה גלוי.
פלט: data/datagov/monthly.csv.gz (+ resources.json - מאילו קבצים נמשך)
הרצה: python scripts/b6_fetch_datagov.py [--from 202201]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd
import requests

API = "https://data.gov.il/api/3/action/"
UA = "INDEX-FX research (github.com/Revach123/INDEX-FX)"
DOMAINS = {"גמל": "גמל-נט", "פנסיה": "פנסיה-נט", "ביטוח": "ביטוח-נט"}
KEEP = ["FUND_ID", "FUND_NAME", "FUND_CLASSIFICATION", "PARENT_COMPANY_ID", "PARENT_COMPANY_NAME", "MANAGING_CORPORATION",
        "REPORT_PERIOD", "TOTAL_ASSETS", "MONTHLY_YIELD", "STOCK_MARKET_EXPOSURE", "FOREIGN_EXPOSURE",
        "FOREIGN_CURRENCY_EXPOSURE", "DEPOSITS", "WITHDRAWLS", "INTERNAL_TRANSFERS", "NET_MONTHLY_DEPOSITS"]
OUT = Path("data/datagov")
S = requests.Session()
S.headers.update({"User-Agent": UA})


def api(action, **params):
    r = S.get(API + action, params=params, timeout=180)
    r.raise_for_status()
    j = r.json()
    if not j.get("success"):
        raise RuntimeError(f"{action}: {j.get('error')}")
    return j["result"]


def resources(title: str) -> list[tuple[str, str]]:
    res = api("package_search", q=title, rows=10)
    pkg = next((p for p in res["results"] if p.get("title") == title), res["results"][0])
    return [(r["id"], r.get("name", "")) for r in pkg["resources"]
            if r.get("datastore_active") and r.get("format", "").upper() == "CSV" and "שינויים" not in r.get("name", "")]


def fetch(rid: str) -> list[dict]:
    out, offset, page = [], 0, 32000
    while True:
        res = api("datastore_search", resource_id=rid, limit=page, offset=offset)
        recs = res["records"]
        out.extend(recs)
        offset += len(recs)
        if len(recs) < page or offset >= res.get("total", 0):
            return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="frm", type=int, default=202201)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    rows, meta = [], []
    for domain, title in DOMAINS.items():
        for rid, name in resources(title):
            recs = fetch(rid)
            meta.append({"domain": domain, "resource_id": rid, "name": name, "rows": len(recs)})
            print(f"[b6] {domain} {name}: {len(recs):,}", flush=True)
            for r in recs:
                try:
                    per = int(str(r.get("REPORT_PERIOD", ""))[:6])
                except ValueError:
                    continue
                if per >= a.frm:
                    rows.append({"domain": domain, **{k: r.get(k) for k in KEEP}})
    df = pd.DataFrame(rows).drop_duplicates(["domain", "FUND_ID", "REPORT_PERIOD"], keep="last")
    df.to_csv(OUT / "monthly.csv.gz", index=False, compression="gzip")
    (OUT / "resources.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    print(f"[b6] {len(df):,} שורות, {df.FUND_ID.nunique()} מסלולים, {df.REPORT_PERIOD.min()}-{df.REPORT_PERIOD.max()}", flush=True)


if __name__ == "__main__":
    main()
