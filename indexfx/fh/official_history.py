"""החשיפה למניות הרשמית לפי חודש, מ-data.gov.il (גמל-נט / פנסיה-נט / ביטוח-נט).

הנתון הרשמי שב-tracks (revach) הוא של החודש האחרון בלבד ("נכון לחודש", למשל
202608), בעוד שהדוחות הרבעוניים הם לסוף רבעון (202606). כדי להשוות לאותו
תאריך, מושכים את STOCK_MARKET_EXPOSURE לחודשי הדוחות עצמם. אותו מקור ואותו
מיפוי כמו revach/scripts/tracks/fetch_datagov.py: FUND_ID = מס' מסלול, לכל תחום.
"""
from __future__ import annotations

import json
import ssl

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

API = "https://data.gov.il/api/3/action/"
DOMAINS = {"גמל": "גמל-נט", "פנסיה": "פנסיה-נט", "ביטוח": "ביטוח-נט"}
PAGE = 32000

urllib3.disable_warnings()


class _LegacyTLSAdapter(HTTPAdapter):
    """data.gov.il דורש legacy renegotiation (כמו ב-revach)."""

    def init_poolmanager(self, *a, **k):
        c = create_urllib3_context()
        c.set_ciphers("DEFAULT@SECLEVEL=1")
        c.options |= getattr(ssl, "OP_LEGACY_SERVER_CONNECT", 0x4)
        c.load_default_certs()
        k["ssl_context"] = c
        return super().init_poolmanager(*a, **k)


def _session() -> requests.Session:
    s = requests.Session()
    s.mount("https://", _LegacyTLSAdapter())
    s.headers.update({"User-Agent": "Mozilla/5.0 maslulim-validate"})
    return s


def _api(s: requests.Session, action: str, **params) -> dict:
    j = s.get(API + action, params=params, timeout=120).json()
    if not j.get("success"):
        raise RuntimeError(f"data.gov.il {action}: {j.get('error')}")
    return j["result"]


def _resources(s: requests.Session, title: str) -> list[str]:
    res = _api(s, "package_search", q=title, rows=5)
    pkg = next((p for p in res["results"] if p.get("title") == title), res["results"][0])
    return [r["id"] for r in pkg["resources"]
            if r.get("datastore_active") and r.get("format", "").upper() == "CSV"
            and "שינויים" not in r.get("name", "")]


def _num(v) -> float | None:
    try:
        return float(str(v).replace("%", "").replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def fetch_stock_exposure(periods: set[str]) -> dict[tuple[str, str, str], float]:
    """(תחום, מס' מסלול, YYYYMM) -> חשיפה למניות (שבר), לחודשים המבוקשים בלבד."""
    return fetch_exposure(periods, "STOCK_MARKET_EXPOSURE")


def fetch_exposure(periods: set[str], field: str) -> dict[tuple[str, str, str], float]:
    """(תחום, מס' מסלול, YYYYMM) -> חשיפה (שבר מנכסי המסלול) לפי field: STOCK_MARKET_EXPOSURE /
    FOREIGN_CURRENCY_EXPOSURE / FOREIGN_EXPOSURE."""
    s = _session()
    out: dict[tuple[str, str, str], float] = {}
    for domain, title in DOMAINS.items():
        for rid in _resources(s, title):
            for period in sorted(periods):
                offset = 0
                while True:
                    try:
                        res = _api(s, "datastore_search", resource_id=rid, limit=PAGE, offset=offset,
                                   filters=json.dumps({"REPORT_PERIOD": int(period)}))
                    except RuntimeError:  # עמודה טקסטואלית
                        res = _api(s, "datastore_search", resource_id=rid, limit=PAGE, offset=offset,
                                   filters=json.dumps({"REPORT_PERIOD": str(period)}))
                    recs = res["records"]
                    for r in recs:
                        # החשיפה היא סכום, לא אחוז - כמו exposure_pct ב-revach
                        e, assets = _num(r.get(field)), _num(r.get("TOTAL_ASSETS"))
                        if r.get("FUND_ID") is not None and e is not None and assets:
                            out[(domain, str(int(float(r["FUND_ID"]))), period)] = e / assets
                    offset += len(recs)
                    if len(recs) < PAGE or offset >= res.get("total", 0):
                        break
    return out
