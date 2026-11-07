"""שכבת סיווג לקרנות נאמנות זרות (UCITS) לפי ISIN - דף הקרן ב-FT (markets.ft.com, נתוני Morningstar):
חיפוש ISIN -> סימול ("LU1171460493:USD") -> עמוד הסיכום, שבו "Asset type": Non-UK stock / UK stock /
Non-UK bond / UK bond / Cash / Other באחוזים (Fullgoal China: מניות 87.74%, מזומן 12.26%). בלי פילוח -
לפי "Morningstar category" (China Equity -> מניות; Global/US Loan, ... Bond -> אג"ח).

מכסה קרנות שאינן ETF ושאינן אמריקאיות, שלא נמצאות באוניברסיטת ה-ETF / SEC ושה-Yahoo לא מחזיר להן פילוח.
חסום מחוץ ל-CI (proxy) - כשל רשת מדולג בשקט; התוצאות נשמרות במטמון שכבות הרשת (foreign_fund_layers).
"""
from __future__ import annotations

import re
import time

import requests

SEARCH_URL = "https://markets.ft.com/data/searchapi/searchsecurities"
SUMMARY_URL = "https://markets.ft.com/data/funds/tearsheet/summary"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
           "Accept-Language": "en-GB,en;q=0.9"}
DELAY = 0.5

_ASSET = re.compile(r"(Non-UK stock|UK stock|Non-UK bond|UK bond|Cash|Other)\s+(-?\d+(?:\.\d+)?)%")
_CATEGORY = re.compile(r"Morningstar category\s+(.+?)\s+IMA sector")
_EQUITY_CAT = re.compile(r"Equity|Equities|Stock", re.IGNORECASE)
_BOND_CAT = re.compile(r"Bond|Fixed Income|Loan|Credit|Money Market|Government", re.IGNORECASE)


def _text(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t)


def parse_summary(html: str) -> dict[str, float] | None:
    """{"equity", "bond"} (שבר מנכסי הקרן) מעמוד הסיכום, או None כשאין פילוח ואין קטגוריה ברורה."""
    t = _text(html)
    i = t.find("Asset type")
    if i >= 0:
        vals = {k: float(v) for k, v in _ASSET.findall(t[i:i + 600])}
        if vals:
            eq = vals.get("Non-UK stock", 0.0) + vals.get("UK stock", 0.0)
            bd = vals.get("Non-UK bond", 0.0) + vals.get("UK bond", 0.0)
            if eq or bd or vals.get("Cash"):
                return {"equity": eq / 100, "bond": bd / 100}
    m = _CATEGORY.search(t)
    cat = m.group(1).strip() if m else ""
    if cat and cat != "--":
        if _EQUITY_CAT.search(cat) and not _BOND_CAT.search(cat):
            return {"equity": 1.0, "bond": 0.0}
        if _BOND_CAT.search(cat) and not _EQUITY_CAT.search(cat):
            return {"equity": 0.0, "bond": 1.0}
    return None


def build_isin_fractions_via_ft(isins: list[str], session: requests.Session | None = None) -> dict[str, dict[str, float]]:
    s = session or requests.Session()
    s.headers.update(HEADERS)
    out: dict[str, dict[str, float]] = {}
    found = 0
    for isin in isins:
        try:
            r = s.get(SEARCH_URL, params={"query": isin}, timeout=30)
            secs = (r.json().get("data") or {}).get("security") or []
            sym = next((x["symbol"] for x in secs if str(x.get("symbol", "")).upper().startswith(isin.upper() + ":")), None)
            if not sym:
                continue
            found += 1
            time.sleep(DELAY)
            page = s.get(SUMMARY_URL, params={"s": sym}, timeout=30)
            frac = parse_summary(page.text) if page.ok else None
            if frac is not None:
                out[isin] = frac
        except (requests.RequestException, ValueError):
            continue
        finally:
            time.sleep(DELAY)
    print(f"[ft_fund] {found}/{len(isins)} ISIN נמצאו ב-FT, {len(out)} סווגו (פילוח נכסים / קטגוריית Morningstar)")
    return out
