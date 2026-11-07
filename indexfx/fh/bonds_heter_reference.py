"""אג"ח/ני"ע לפי היתר עסקה ועדה: נשלף מ-data/securities/bonds_heter.json
ב-revach (private repo), דרך GitHub Contents API עם PAT - אותה תבנית
כמו funds_reference.py.

מקור: revach/scripts/securities/build_bonds_heter_report.py - רשימה
ברמת-נייר של כל האג"ח (כל הסוגים), עם heter_bucket (סטטוס היתר עסקה
של המנפיק לפי HARAV_LEVIN) ו-ada_status (עדה/עדה?, לפי רשימת "עדה" -
ר' revach/scripts/securities/build_ada_bonds_registry.py).
"""
import os

import requests

CONTENTS_URL = "https://api.github.com/repos/Revach123/revach/contents/data/securities/bonds_heter.json"
TOKEN_ENV = "PAT"


def fetch_raw(session: requests.Session | None = None) -> dict:
    token = (os.environ.get(TOKEN_ENV) or "").strip()
    if not token:
        raise SystemExit(f"[bonds_heter_reference] משתנה הסביבה {TOKEN_ENV} לא מוגדר")
    s = session or requests.Session()
    r = s.get(CONTENTS_URL, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw",
    }, timeout=60)
    r.raise_for_status()
    return r.json()


def build_bonds_heter_by_isin(session: requests.Session | None = None) -> dict[str, dict]:
    """ISIN -> {heter_bucket, ada_status, security_name, issuer_name, asset_class}."""
    raw = fetch_raw(session)
    out = {}
    for row in raw.get("rows", []):
        isin = (row.get("isin") or "").strip()
        if not isin:
            continue
        out[isin] = {
            "heter_bucket": row.get("heter_bucket"),
            "ada_status": row.get("ada_status"),
            "security_name": row.get("security_name"),
            "issuer_name": row.get("issuer_name"),
            "asset_class": row.get("asset_class"),
        }
    return out


if __name__ == "__main__":
    data = build_bonds_heter_by_isin()
    print(f"[bonds_heter_reference] {len(data)} ניירות")
    if data:
        k = next(iter(data))
        print("דוגמה:", k, data[k])
