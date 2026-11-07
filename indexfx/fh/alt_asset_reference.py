"""סחורות ונכסים דיגיטליים בקרנות חו"ל - לתצוגה בדף המסלול (holdings_detail: cls "commodity" /
"digital"). קרנות ישראליות מסווגות לפי "סיווג ראשי" בהפניה של revach; לקרן חו"ל אין סיווג כזה,
ולכן ארבעה מקורות, לפי סדר האמינות - רק לקרן בלי הרכב מניות/אג"ח (זהב/ביטקוין/נפט הן לא אלה):

1. asset_class באוניברסיטת ה-ETF של revach ("Commodity" / "Digital Assets": iShares Physical
   Palladium ETC, iShares Bitcoin ETP).
2. רשימת הייחוס הקיימת של נאמנויות סחורה/קריפטו אמריקאיות (KNOWN_COMMODITY_CRYPTO_TRUSTS).
3. ISIN אמריקאי: קוד הענף (SIC) של המנפיק ב-SEC - נאמנויות סחורה וקריפטו (GLD, IAU, SLV, IBIT,
   USO) רשומות בקוד 6221 (Commodity Contracts Brokers & Dealers). ISIN -> טיקר (OpenFIGI) ->
   CIK (company_tickers.json) -> sic (submissions).
4. שם הקרן (השם המלא מ-OpenFIGI כשיש, אחרת השם בדוח): זהב/כסף/נפט/סחורות/ETC, ביטקוין/אתר/קריפטו -
   בלי כורים/מניות ("Gold Miners" היא קרן מניות).

סחורה מול דיגיטלי: לפי השם (ביטקוין/אתר/קריפטו -> דיגיטלי) או asset_class.
"""
from __future__ import annotations

import re

from .foreign_etf_reference import KNOWN_COMMODITY_CRYPTO_TRUSTS

COMMODITY_SIC = {"6221"}
COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

_DIGITAL = re.compile(r"BITCOIN|\bBTC\b|ETHER|\bETH\b|CRYPTO|SOLANA|\bXRP\b|DIGITAL\W?ASSET", re.IGNORECASE)
_COMMODITY = re.compile(
    r"\bGOLD\b|SILVER|PLATINUM|PALLADIUM|PRECIOUS\W?METAL|BULLION|COMMODIT|\bOIL\b|BRENT|\bWTI\b|CRUDE|"
    r"NATURAL\W?GAS|AGRICULTUR|\bETC\b|זהב|נפט|סחורות", re.IGNORECASE)
_NOT_ALT = re.compile(r"MINER|MINING|EQUITY|EQUITIES|STOCK|PRODUCER|EXPLOR|ROYALT|BLOCKCHAIN|COMPANIES|"
                      r"כורים|מניות", re.IGNORECASE)


def class_by_name(name: str | None) -> str | None:
    """"digital" / "commodity" / None לפי שם קרן."""
    text = str(name or "")
    if not text or _NOT_ALT.search(text):
        return None
    if _DIGITAL.search(text):
        return "digital"
    if _COMMODITY.search(text):
        return "commodity"
    return None


def _kind(name: str | None) -> str:
    return "digital" if _DIGITAL.search(str(name or "")) else "commodity"


def _sec_commodity_isins(us_isins: list[str]) -> set[str]:
    """ISIN אמריקאים שהמנפיק שלהם רשום ב-SEC בקוד ענף סחורות (6221)."""
    from .sec_nport_reference import SUBMISSIONS_URL, _sec_get, resolve_isin_to_ticker

    if not us_isins:
        return set()
    tickers = resolve_isin_to_ticker(us_isins)
    data = _sec_get(COMPANY_TICKERS_URL, as_json=True) or {}
    cik_by_ticker = {str(v.get("ticker", "")).upper(): int(v["cik_str"]) for v in data.values() if v.get("cik_str")}
    out = set()
    for isin, ticker in tickers.items():
        cik = cik_by_ticker.get(ticker)
        if cik is None:
            continue
        sub = _sec_get(SUBMISSIONS_URL.format(cik10=f"{cik:010d}"), as_json=True) or {}
        if str(sub.get("sic") or "") in COMMODITY_SIC:
            out.add(isin)
    return out


def build_alt_classes(candidates: dict[str, str], etf_universe: list[dict],
                      full_names: dict[str, str] | None = None, online: bool = True) -> dict[str, str]:
    """candidates: ISIN -> שם בדוח, לקרנות חו"ל בלי הרכב מניות/אג"ח. מחזיר ISIN -> "commodity"/"digital"."""
    full_names = full_names or {}
    universe = {}
    for rec in etf_universe:
        isin = str(rec.get("isin") or "").strip().upper()
        ac = str(rec.get("asset_class") or "").strip().lower()
        if isin and ac:
            universe[isin] = ac
    out: dict[str, str] = {}
    src = {"universe": 0, "known": 0, "sec": 0, "name": 0}
    for isin, name in candidates.items():
        ac = universe.get(isin, "")
        if "digital" in ac or "crypto" in ac:
            out[isin] = "digital"; src["universe"] += 1
        elif "commodit" in ac or "precious" in ac:
            out[isin] = "commodity"; src["universe"] += 1
        elif isin in KNOWN_COMMODITY_CRYPTO_TRUSTS:
            out[isin] = _kind(KNOWN_COMMODITY_CRYPTO_TRUSTS[isin] + " " + str(name)); src["known"] += 1
    if online:
        us = [i for i in candidates if i.startswith("US") and i not in out]
        try:
            for isin in _sec_commodity_isins(us):
                out[isin] = _kind(full_names.get(isin) or candidates[isin]); src["sec"] += 1
        except Exception as e:  # רשת
            print(f"[alt] SEC לא זמין (מדלג על קוד הענף): {e}")
    for isin, name in candidates.items():
        if isin not in out:
            cls = class_by_name(full_names.get(isin)) or class_by_name(name)
            if cls:
                out[isin] = cls; src["name"] += 1
    print(f"[alt] סחורות/נכסים דיגיטליים בקרנות חו\"ל: {len(out)} מתוך {len(candidates)} מועמדות - לפי מקור {src}")
    return out
