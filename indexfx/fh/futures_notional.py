"""חשיפה נוציונלית לחוזים עתידיים: חוזים × רמת-המדד × מכפיל-החוזה × שער חליפין.

למה לא units × "שער נייר הערך" (כמו קודם): נבדק על כל 4,598 שורות החוזים על
מניות בקבצי 2026Q2 - שדה המחיר מדווח בכמה מוסכמות שונות, עקביות לכל גוף מדווח:
- רמת המדד כמות-שהיא (ESU6 = 7,548.25) - למשל 511880460, 513611509.
- רמת המדד ×100 ("אגורות"; ESU6 = 754,825) - למשל 514956465, 513173393, 512245812.
- רווח/הפסד לחוזה ×100, כך ש-שווי הוגן = יחידות × מחיר/100 × שער (מחיר שונה
  לכל מסלול, לעתים שלילי) - למשל 512267592, 512065202. כאן המחיר אינו רמה כלל.
- מחיר חסר (0.01) - למשל 520042177.
לעומת זאת "ערך נקוב (יחידות)" הוא מספר החוזים בכל המוסכמות (מאומת: סכום
החוזים לכל גוף יוצא מספר שלם, למשל 514956465: ES 9,557, NO 10,068), והמכפיל
הוא תכונה של החוזה בבורסה. לכן המחיר משמש רק לזיהוי המוסכמה ולבניית רמת
קונצנזוס לחוזה - הנוציונל עצמו לא נשען על המחיר של השורה.

זוג רגליים ממומן (רגל נכס + "... Index התחייבות" במחיר 100) - רגל ההתחייבות
היא מימון ולא חשיפה; החשיפה כולה ברגל הנכס (אומת: אצל 512244146 שווי הוגן
של רגל הנכס = חוזים × רמה × 50 × שער בדיוק).

מכפילים: רק כאלה שאומתו ממפרט הבורסה. שורש שאינו בטבלה, או שאין לו רמה
(אין מגיש שמצטט רמה ואין סדרת ייחוס ב-INDICES) - לא נפתר, והקורא סופר את
השווי ההוגן המדווח של השורה.

זיהוי החוזה, לפי הסדר: קוד בטיקר (בלומברג/פנימי) -> קוד בשם -> שם שנלמד
מגופים אחרים -> מספר נייר משותף (בורסת ת"א) -> שם חוזה ת"א -> התאמת רמת מחיר.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Callable

# שורש -> (מכפיל ליחידת מחיר, index_id ב-INDICES לעיגון רמה, או None).
# מקורות: מפרטי CME/CBOT, Eurex, ICE, JPX/OSE, SGX, ASX, Montréal, HKEX, KRX.
CONTRACT_SPECS: dict[str, tuple[float, str | None]] = {
    # CME
    "ES": (50, "sp500"),        # E-mini S&P 500
    "ME": (50, "sp500"),        # אותו חוזה בקוד פנימי של חלק מהמדווחים ("MINI S&P500 INDEX")
    "HWA": (5, "sp500"),        # Micro E-mini S&P 500
    "SLB": (500, "sp500_esg"),  # E-mini S&P 500 ESG = $500 × S&P 500 Scored & Screened (מפרט CME)
    "NQ": (20, "nasdaq100"),    # E-mini Nasdaq-100
    "HWB": (2, "nasdaq100"),    # Micro E-mini Nasdaq-100
    "M2K": (5, "russell2000"),  # Micro E-mini Russell 2000
    "MYM": (0.5, "dow30"),      # Micro E-mini Dow
    "RTY": (50, "russell2000"),  # E-mini Russell 2000
    "RTS": (50, "russell2000"),  # אותו חוזה בקוד פנימי ("RTY Index" / RTSZ5 - 513026484, 520023185)
    "NX": (5, "nikkei225"),     # CME Nikkei 225 Dollar ("NIKKEI 225 FU 12/25" NXZ5 - 512267592, 520004078)
    "DM": (5, "dow30"),         # E-mini Dow
    "FAW": (100, None),         # E-mini S&P MidCap 400
    "FA": (100, None),          # אותו חוזה בקוד בלומברג ("FAH6 INDEX" ב-513026484_gm_0425)
    "IXT": (100, None),         # E-mini Technology Select Sector (XAK)
    "XAS": (250, None),         # E-mini Communication Services Select Sector (XAZ) - $250 x index (מפרט CME, SER-8207R)
    "XAY": (100, None),         # E-mini Consumer Discretionary Select Sector
    "SWO": (25, "yahoo:^SOX"),  # E-mini PHLX Semiconductor Sector (SOX) - רמה מ-Yahoo כשאף גוף לא מצטט רמה
    # OSE / SGX
    "NK": (1000, "nikkei225"),  # Nikkei 225 (OSE, large)
    "NO": (100, "nikkei225"),   # Nikkei 225 mini (OSE)
    "NI": (500, "nikkei225"),   # Nikkei 225 (SGX, JPY)
    "TP": (10000, None),        # TOPIX (OSE)
    "TMI": (1000, None),        # mini-TOPIX (OSE)
    # Eurex
    "VG": (10, "stoxx50"),      # EURO STOXX 50
    "GX": (25, "dax"),          # DAX
    "DFW": (5, "dax"),          # Mini-DAX
    "MZS": (1, "dax"),          # Micro-DAX (Eurex FDXS, €1 לנקודה - "F 12/25 MICRO DAX" MZSZ5, 513621110)
    "CF": (10, None),           # CAC 40 (Euronext, €10 לנקודה - "INDEX CAC 40" CFV5, 513026484)
    "SXO": (50, None),          # STOXX Europe 600
    "CA": (50, None),           # EURO STOXX Banks
    "UL": (50, None),           # STOXX Europe 600 Technology (Eurex FSTY) - "ULZ5 Index" ב-512244146_gm_0325
    "SM": (10, "smi"),          # SMI
    # MSCI: קוד מוצר בבלומברג -> מכפיל, מתוך "Listed futures and options based on
    # MSCI indexes" (MSCI, Q2 2023). JJY (FMKR) הושק ב-2025 - ממפרט Eurex.
    "RBE": (50, None),          # Eurex EM USD price (FMEF, RBEA)
    "MUR": (50, None),          # Eurex China USD NTR (FMCH, MURA)
    "FPO": (100, None),         # Eurex Taiwan USD NTR (FMTW, FPOA)
    "JJY": (50, None),          # Eurex Korea USD NTR (FMKR)
    "ZWP": (10, None),          # Eurex World USD NTR (FMWO, ZWPA)
    # RVP/HRL - אף גוף לא מצטט רמה בכל הארכיון (512065202 מדווח רווח/הפסד) -> סדרת המדד של
    # MSCI ב-Yahoo (^<קוד MSCI>-USD-<וריאנט>): World price 990100, World ESG Screened NTR 721415
    "RVP": (10, "yahoo:^990100-USD-STRD"),   # Eurex World USD price (FMWP, RVPA)
    "ZTL": (100, None),         # Eurex ACWI USD NTR (FMAC, ZTLA)
    "HRL": (10, "yahoo:^721415-USD-NETR"),   # Eurex World ESG Screened USD NTR (FMSW, HRLA)
    "WMW": (200, None),         # ICE US ACWI USD NTR (MMW, WMWA)
    # ICE
    "Z": (10, "ftse100"),       # FTSE 100
    "MES": (50, None),          # ICE US MSCI EM USD price (MME, MESA)
    "G": (1000, None),          # Long Gilt (נקודת par)
    # אחרים
    "XP": (25, "asx200"),       # SPI 200 (ASX)
    "PT": (200, None),          # S&P/TSX 60 (Montréal)
    "KS": (250000, None),       # KOSPI 200 (KRX)
    "HI": (50, "hangseng"),     # Hang Seng
    "HU": (10, "hangseng"),     # Mini Hang Seng
    "JGS": (2, "nifty50"),      # GIFT Nifty (NSE IX), USD 2 לנקודה
    # בורסת ת"א - ₪50 לנקודת מדד (מפרט החוזה של הבורסה). אין להם קוד בלומברג
    # בדוחות - מזוהים לפי השם (tase_root) ולפי מספר נייר משותף בין הגופים.
    # אומת מול הרשמי: למשל 512065202_14267 - 73.5% בלי החוזה, 97.7% איתו, רשמי 98.6%.
    "TA125": (50, "ta125"),
    "TA35": (50, "ta35"),
    "TA90": (50, "ta90"),
    "TABANKS": (50, "ta_banks"),
    # אג"ח ארה"ב (CBOT) - מחיר בנקודות par, מכפיל לנקודה
    "TU": (2000, None), "FV": (1000, None), "TY": (1000, None),
    "UXY": (1000, None), "US": (1000, None), "WN": (1000, None),
    "CL": (1000, None),         # WTI Crude (1,000 חביות)
}
# חוזים שאינם על מניות. הסיווג לפי החוזה עצמו גובר על "נכס בסיס" שבדוח - נמצאו
# שני הכיוונים: UXY/TY מסווגים "מניות" (512065202, 514956465, 520030677,
# 520027251, 520028390) ו-NQ/VG/NO/SXO/MES מסווגים "אחר" (511880460, 510960586).
# חוזים בבורסות שונות על אותו מדד (קוד המדד מתוך חוברת MSCI) - חולקים רמה.
# למשל ZTL (Eurex) מוחזק רק אצל גופים שמדווחים רווח/הפסד במקום רמה, והרמה
# נלקחת מ-WMW (ICE) שמדווח ברמה אצל גופים אחרים.
SAME_INDEX = {"ZTL": "M1WD", "WMW": "M1WD", "MES": "MXEF", "RBE": "MXEF", "UL": "SX8P", "SX6TECH": "SX8P", "FA": "MID400", "FAW": "MID400"}

# חוזה Micro בשם ("NASD100 MICRO EMINDEC25", "SP500 MIC EMIN FUTDEC25" ב-510806870_gc_0325) שזוהה
# לפי המדד כחוזה הרגיל - עשירית ממנו (פי 10 בחשיפה: 47% במקום 4.7%, רשמי 24.1%)
MICRO_OF = {"ES": "HWA", "ME": "HWA", "NQ": "HWB", "RTY": "M2K", "DM": "MYM"}
_MICRO_NAME = re.compile(r"\bMICRO\b|\bMIC\b")

NON_EQUITY_ROOTS = frozenset({"G", "TU", "FV", "TY", "UXY", "US", "WN", "CL"})

MONTH_CODES = "FGHJKMNQUVXZ"
_SUFFIX = re.compile(r"[\s_]+(INDEX|COMDTY|EQUITY|CURNCY)$")
_BBG = re.compile(rf"^([A-Z0-9]{{1,5}}?)\s?([{MONTH_CODES}])(\d)$")
_INTERNAL = re.compile(rf"^([A-Z]{{1,5}}?)([{MONTH_CODES}])(\d)\d{{3,6}}$")
_GENERIC = re.compile(r"^([A-Z]{1,4})1$")
_IN_NAME = re.compile(rf"(?<![A-Z0-9])([A-Z]{{1,5}}?)\s?([{MONTH_CODES}])(\d)(?![0-9A-Z])")
_NAME_NOISE = re.compile(
    r"\b(\d{1,2}[/.]\d{1,2}([/.]\d{2,4})?|\d{1,2}/\d{2,4}|(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s?\d{2,4}"
    r"|FU|FUT|FUTR|FUTURE|FUTURES|INDEX|INDX|IDX|F)\b")

_TASE_NAMES = (
    ("TA125", re.compile(r'(TA|ת"?א)[\s-]*125|\bTL[1F]\b')),
    ("TA35", re.compile(r'\bT35\b|(TA|ת"?א)[\s-]*35\b')),
    ("TA90", re.compile(r'(TA|ת"?א)[\s-]*90\b|-90$')),
    ("TABANKS", re.compile(r'^BF\b|בנקים|BANKS')),
)
_ISIN_IL = re.compile(r"^IL0(\d{8})\d$")
_NAME_ROOTS = (
    (re.compile(r"\bFESX\b"), "VG"),                          # Eurex EURO STOXX 50
    (re.compile(r"\bEM(?:I)?NI\s+(?:NSDQ|NASDAQ)\b"), "NQ"),   # CME E-mini Nasdaq-100
    (re.compile(r"\bEMINI\s+S&P\b"), "ES"),                   # CME E-mini S&P 500
    (re.compile(r"\bOSE\s+TOPIX\b"), "TP"),                   # OSE TOPIX (large)
)
_STOXX600_SECTOR = re.compile(r"\bSTOXX\s*(?:EUROPE\s*)?600\s+([A-Z][A-Z&]{2,})")
STOXX600_SECTOR_MULTIPLIER = 50.0

LIABILITY_MARK = "התחייבות"
SCALES = (1.0, 100.0)
SCALE_TOL = 0.05        # מחיר/רמת-ייחוס בתוך 5% (בסיס חוזה מול מדד, הפרשי תאריכים)
LEVEL_TOL = 0.05
IDENTIFY_TOL = 0.02     # זיהוי לפי רמה - צר יותר (למשל MSCI Korea 3,093 מול Russell 3,046)
# חוזה שאין לו רמה (שורש לא מוכר / בלי מקור רמה), כשה"מחיר" בשורה הוא שווי חוזה אחד (מכפיל × רמת
# המדד): מחיר ÷ מכפיל סטנדרטי = רמה ידועה של מדד מניות באותו מטבע (מהדוחות / INDICES / Yahoo), עד 3%
# (הפרש בסיס עד הפקיעה) -> נוציונל = חוזים × מחיר. מיטב 2025Q3, זירה CBOE: "F-12/25 MSCI US" FJWZ5 ב-68,000
# (S&P 500 6,688 × 10) ו-"F-12/25 MSCI WO" OEYZ5 ב-49,500 (MSCI ACWI 984.8 × 50).
CONTRACT_VALUE_MULTS = (5.0, 10.0, 20.0, 25.0, 50.0, 100.0)
CONTRACT_VALUE_TOL = 0.03
# מדדי מניות נפוצים בלי חוזה בטבלה - רק לזיהוי שווי חוזה (Yahoo: רמת המחיר של MSCI)
EXTRA_VALUE_REFS = {"USD": ("yahoo:^892400-USD-STRD",)}   # MSCI ACWI price
MIN_SCALE_VOTES = 3
SCALE_MAJORITY = 0.8


def _num(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).strip().replace(",", ""))
    except ValueError:
        return None


def _year_ok(digit: str, report_date: date | None) -> bool:
    if report_date is None:
        return True
    y = report_date.year % 10
    return int(digit) in {y, (y + 1) % 10, (y + 2) % 10}


def parse_code(raw_ticker, name, report_date: date | None) -> tuple[str | None, str | None]:
    """(שורש, חודש+ספרת שנה) מתוך הטיקר, ואם אין - מתוך השם. (None, None) אם לא זוהה."""
    t = _SUFFIX.sub("", re.sub(r"\s+", " ", str(raw_ticker or "").strip().upper())).strip()
    if t.endswith(".0"):
        t = t[:-2]
    for rx in (_BBG, _INTERNAL):
        m = rx.match(t)
        if m and _year_ok(m.group(3), report_date):
            return m.group(1), m.group(2) + m.group(3)
    m = _GENERIC.match(t)
    if m:
        return m.group(1), None
    for m in _IN_NAME.finditer(str(name or "").upper()):
        if m.group(1) in CONTRACT_SPECS and _year_ok(m.group(3), report_date):
            return m.group(1), m.group(2) + m.group(3)
    # קוד החוזה כמילה הראשונה בשם, בלי קוד חודש ("XAY Cons Discret  Sep26")
    first = str(name or "").upper().split(maxsplit=1)
    if first and len(first[0]) >= 3 and first[0] in CONTRACT_SPECS:
        return first[0], None
    # שמות מלאים בלי קוד (511789190: "ERX-F FESX 25 Dec 0", "IMM EMNI NSDQ 26 Mar 0")
    up = str(name or "").upper()
    for rx, root in _NAME_ROOTS:
        if rx.search(up):
            return root, None
    # חוזה סקטור STOXX Europe 600 (Eurex, €50 לנקודה בכל הסקטורים) - שורש לכל סקטור, כי לכל
    # אחד רמה משלו ("STOXX 600 TECH    Jun26" ב-512244146_gm_0126: 138 חוזים × 787.8 × 50 =
    # 27.6% מהמסלול, ובלעדיו 69.5% מול 99.4% רשמי)
    m = _STOXX600_SECTOR.search(str(name or "").upper())
    if m:
        root = "SX6" + m.group(1)[:4]
        CONTRACT_SPECS.setdefault(root, (STOXX600_SECTOR_MULTIPLIER, None))
        return root, None
    return None, None


def tase_root(name) -> str | None:
    """חוזה של בורסת ת"א לפי השם (לשורות בשקלים בלבד)."""
    s = re.sub(r"\s+", " ", str(name or "").upper()).strip()
    return next((root for root, rx in _TASE_NAMES if rx.search(s)), None)


def security_id(raw_ticker) -> str | None:
    """מספר נייר בבורסת ת"א מתוך ISIN ישראלי או מספר נייר גולמי ('86528221.0')."""
    t = str(raw_ticker or "").strip().upper()
    if t.endswith(".0"):
        t = t[:-2]
    m = _ISIN_IL.match(t)
    if m:
        return m.group(1).lstrip("0")
    return t.lstrip("0") if t.isdigit() and 7 <= len(t) <= 9 else None


def normalize_name(name) -> str:
    s = str(name or "").upper().replace("_", " ")
    s = _IN_NAME.sub(" ", s)
    s = _NAME_NOISE.sub(" ", s)
    s = re.sub(r"[^0-9A-Z&א-ת]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def is_liability_leg(row: dict, price: float | None, units: float | None) -> bool:
    if LIABILITY_MARK in str(row.get("שם נייר ערך") or ""):
        return True
    return price is not None and price == 100.0 and units is not None and abs(units) >= 1e5


@dataclass
class FuturesRow:
    legal_id: str
    root: str | None
    month: str | None
    name: str
    ccy: str | None
    units: float | None
    price: float | None
    report_date: date | None
    liability: bool
    security: str | None = None
    by_name: bool = False       # השורש נלמד משם זהה אצל גוף אחר (לא קוד בשורה עצמה)


class FuturesResolver:
    """נבנה פעם אחת מכל שורות החוזים (כל הגופים), ומחשב נוציונל לכל שורה."""

    def __init__(self, rows: list[FuturesRow], ref_level: Callable[[str, date], float | None]):
        self._ref_level = ref_level
        self.rows = rows
        self._learn_name_map()
        self._learn_filer_scales()
        self._build_levels()
        self._recheck_by_name()
        self._identify_remaining()
        for r in self.rows:
            if r.root in MICRO_OF and _MICRO_NAME.search(str(r.name).upper()):
                r.root = MICRO_OF[r.root]

    # --- זיהוי --------------------------------------------------------
    def _learn_name_map(self):
        votes: dict[str, Counter] = defaultdict(Counter)
        voters: dict[str, set] = defaultdict(set)
        for r in self.rows:
            if r.root in CONTRACT_SPECS:
                nm = normalize_name(r.name)
                if nm:
                    votes[nm][r.root] += 1
                    voters[nm].add(r.legal_id)
        self.name_map = {nm: c.most_common(1)[0][0] for nm, c in votes.items() if len(c) == 1}
        for r in self.rows:
            if r.root not in CONTRACT_SPECS:
                nm = normalize_name(r.name)
                root = self.name_map.get(nm)
                if root:
                    r.root = root
                    r.by_name = r.legal_id not in voters[nm]
        # אותו מספר נייר אצל גופים שונים = אותו חוזה (למשל "FM607-1תא" = "TLF JUL2026 TA 125")
        by_sec: dict[str, Counter] = defaultdict(Counter)
        for r in self.rows:
            if r.security and r.root in CONTRACT_SPECS:
                by_sec[r.security][r.root] += 1
        for r in self.rows:
            c = by_sec.get(r.security)
            if r.root not in CONTRACT_SPECS and c and len(c) == 1:
                r.root = next(iter(c))
        cc: dict[str, Counter] = defaultdict(Counter)
        for r in self.rows:
            if r.root in CONTRACT_SPECS and r.ccy:
                cc[r.root][r.ccy] += 1
        self.root_ccy = {k: c.most_common(1)[0][0] for k, c in cc.items()}
        self.root_count = Counter(r.root for r in self.rows if r.root in CONTRACT_SPECS)

    @staticmethod
    def _index_of(root: str) -> str:
        """מזהה נכס הבסיס לקונצנזוס הרמה: סדרת INDICES, קוד מדד MSCI, או השורש עצמו."""
        return CONTRACT_SPECS[root][1] or SAME_INDEX.get(root) or root

    def _ref(self, root: str, d: date | None) -> float | None:
        idx = CONTRACT_SPECS.get(root, (None, None))[1]
        if not idx or d is None:
            return None
        try:
            return self._ref_level(idx, d)
        except Exception:
            return None

    def _learn_filer_scales(self):
        votes: dict[str, Counter] = defaultdict(Counter)
        for r in self.rows:
            if r.root not in CONTRACT_SPECS or not r.price or r.liability:
                continue
            ref = self._ref(r.root, r.report_date)
            if not ref:
                continue
            q = r.price / ref
            hit = next((s for s in SCALES if abs(q / s - 1) < SCALE_TOL), None)
            votes[r.legal_id][hit] += 1
        self.filer_scale: dict[str, float] = {}
        for lid, c in votes.items():
            n = sum(c.values())
            s, k = c.most_common(1)[0]
            if s is not None and k >= MIN_SCALE_VOTES and k / n >= SCALE_MAJORITY:
                self.filer_scale[lid] = s

    def _build_levels(self):
        cands: dict[tuple, list[float]] = defaultdict(list)
        roots_of: dict[str, str] = {}
        for r in self.rows:
            s = self.filer_scale.get(r.legal_id)
            if r.root not in CONTRACT_SPECS or not s or not r.price or r.price <= 0 or r.liability or r.by_name:
                continue
            lvl = r.price / s
            idx = self._index_of(r.root)
            cands[(idx, r.month, r.report_date)].append(lvl)
            cands[(idx, None, r.report_date)].append(lvl)
            roots_of[idx] = r.root
        self.levels: dict[tuple, float] = {}
        for key, vals in cands.items():
            ref = self._ref(roots_of[key[0]], key[2])
            anchor = ref if ref else statistics.median(vals)
            good = [v for v in vals if abs(v / anchor - 1) < LEVEL_TOL]
            if good:
                self.levels[key] = statistics.median(good)

    def level(self, root: str, month: str | None, d: date | None) -> float | None:
        idx = self._index_of(root)
        return (self.levels.get((idx, month, d)) or self.levels.get((idx, None, d))
                or self._ref(root, d))

    def _fits(self, r: FuturesRow, root: str) -> bool:
        scales = [self.filer_scale[r.legal_id]] if r.legal_id in self.filer_scale else list(SCALES)
        lvl = self.level(root, None, r.report_date)
        return bool(lvl) and any(abs(r.price / s / lvl - 1) < IDENTIFY_TOL for s in scales)

    def _recheck_by_name(self):
        """שם כללי שנלמד מגוף אחר ("MSCI WORLD" - RVPU6 של 512065202, מחיר העולמי) לא מכריע מול
        מחיר שהוא רמה של חוזה אחר באותו מטבע (512244146 "MSCI World Index Sep26" ב-1,571,200 = רמת
        ZWP ×100): השורה עוברת לחוזה שהרמה שלו מתאימה, ורק אז תורמת לרמות."""
        moved = False
        for r in self.rows:
            if not r.by_name or r.liability or not r.price or r.price <= 0:
                continue
            if not self._fits(r, r.root):
                matches = {root for root in CONTRACT_SPECS
                           if self.root_ccy.get(root) == r.ccy and self._fits(r, root)}
                if len({self._index_of(m) for m in matches}) == 1:
                    r.root = max(matches, key=lambda m: self.root_count.get(m, 0))
                    moved = True
                elif matches or self.level(r.root, None, r.report_date):
                    continue
            r.by_name = False
            moved = True
        if moved:
            self._build_levels()

    def _identify_remaining(self):
        """שורות בלי קוד ובלי שם מוכר: זיהוי לפי רמת המחיר מול רמות ידועות באותו מטבע."""
        for r in self.rows:
            if r.root is not None or r.liability or not r.price or r.price <= 0:
                continue
            scales = [self.filer_scale[r.legal_id]] if r.legal_id in self.filer_scale else list(SCALES)
            matches = set()
            for root in CONTRACT_SPECS:
                if self.root_ccy.get(root) != r.ccy:
                    continue
                lvl = self.level(root, None, r.report_date)
                if lvl and any(abs(r.price / s / lvl - 1) < IDENTIFY_TOL for s in scales):
                    matches.add(root)
            if not matches:
                continue
            mults = {CONTRACT_SPECS[m][0] for m in matches}
            if len(mults) > 1:
                if "MICRO" in str(r.name).upper():
                    small = min(mults)
                    matches = {m for m in matches if CONTRACT_SPECS[m][0] == small}
                else:
                    matches = {max(matches, key=lambda m: self.root_count.get(m, 0))}
            r.root = sorted(matches)[0]

    # --- חישוב --------------------------------------------------------
    @staticmethod
    def is_equity(r: FuturesRow) -> bool | None:
        """האם החוזה על מניות, לפי החוזה שזוהה. None - לא זוהה (הקורא נופל לסיווג בדוח)."""
        if r.root not in CONTRACT_SPECS:
            return None
        return r.root not in NON_EQUITY_ROOTS

    def contract_value_match(self, r: FuturesRow) -> list[str]:
        """מדדי המניות (באותו מטבע) שהמחיר בשורה הוא שווי חוזה אחד שלהם: מחיר ÷ מכפיל סטנדרטי = הרמה
        שלהם בתאריך הדוח (ר' CONTRACT_VALUE_MULTS). ריק - המחיר אינו שווי חוזה מזוהה."""
        if not r.price or r.price <= 0 or r.report_date is None or r.ccy in (None, "ILS"):
            return []
        cands: dict[str, float] = {}
        for root in CONTRACT_SPECS:
            if root in NON_EQUITY_ROOTS or self.root_ccy.get(root) != r.ccy:
                continue
            lvl = self.level(root, None, r.report_date)
            if lvl:
                cands[self._index_of(root)] = lvl
        for ref in EXTRA_VALUE_REFS.get(r.ccy, ()):
            try:
                lvl = self._ref_level(ref, r.report_date)
            except Exception:
                lvl = None
            if lvl:
                cands[ref] = lvl
        return [idx for idx, lvl in cands.items()
                if any(abs(r.price / m / lvl - 1) < CONTRACT_VALUE_TOL for m in CONTRACT_VALUE_MULTS)]

    def notional(self, r: FuturesRow) -> float | None:
        """נוציונל במטבע החוזה (חתום לפי כיוון הפוזיציה). 0.0 לרגל התחייבות. None - לא נפתר."""
        if r.liability:
            return 0.0
        if r.units is None:
            return None
        if r.root in CONTRACT_SPECS:
            lvl = self.level(r.root, r.month, r.report_date)
            if lvl:
                return r.units * lvl * CONTRACT_SPECS[r.root][0]
        # קוד חוזה שאינו בטבלה (ולכן בלי מכפיל ורמה): המחיר בשורה כשווי חוזה אחד של מדד מניות מוכר.
        # לא לשורש מוכר בלי רמה (SWO/TWT כש-Yahoo נכשל) - שם המחיר הוא רמה, וההתאמה מקרית
        if r.root not in CONTRACT_SPECS and self.contract_value_match(r):
            return r.units * r.price
        return None


def build_rows(source: list[dict], category: str, cols: dict) -> list[tuple[dict, FuturesRow]]:
    out = []
    for rec in source:
        if rec["Category"] != category or rec["מידע"] != "מידע":
            continue
        d = rec.get("ReportMonth")
        for row in rec["Clean"]:
            key = row.get("מפתח")
            if key is None:
                continue
            price = _num(row.get(cols["price"]))
            units = _num(row.get(cols["units"]))
            root, month = parse_code(row.get(cols["ticker"]), row.get("שם נייר ערך"), d)
            ccy = row.get(cols["currency"])
            if root is None and ccy == "ILS":
                root = tase_root(row.get("שם נייר ערך"))
            out.append((row, FuturesRow(
                legal_id=str(key).split("_")[0], root=root, month=month,
                name=str(row.get("שם נייר ערך") or ""), ccy=ccy,
                units=units, price=price, report_date=d,
                liability=is_liability_leg(row, price, units),
                security=security_id(row.get(cols["ticker"])))))
    _fix_units_by_fair_value(out, cols["ticker"])
    return out


FV_COL = 'שווי הוגן (באלפי ש"ח)'
UNITS_MIN_ROWS, UNITS_AGREE, UNITS_OUTLIER = 3, 0.6, 30


def _fix_units_by_fair_value(rows: list[tuple[dict, FuturesRow]], ticker_col: str) -> None:
    """כמות חוזים שסותרת את השווי ההוגן של השורה: באותו גוף, חוזה ותאריך דוח השווי לחוזה אחיד (אותו
    מחיר), כך שכשרוב השורות (60%+) מסכימות - שורה שהשווי שלה לחוזה רחוק פי 30+ מהחציון מקבלת כמות
    מהשווי. (איילון 46011, NQU6: 2.84 חוזים מול שווי 0.48 אלף ש"ח - 0.017 חוזים לפי השווי; במסלול
    האח 46012 0.6 חוזים בשווי 80 אלף ש"ח.)"""
    groups: dict[tuple, list[int]] = defaultdict(list)
    for i, (row, r) in enumerate(rows):
        fv = _num(row.get(FV_COL))
        contract = str(row.get(ticker_col) or "").strip().upper() or r.name
        if r.units and fv and contract:
            groups[(r.legal_id, contract, r.report_date)].append(i)
    for idx in groups.values():
        if len(idx) < UNITS_MIN_ROWS:
            continue
        per = {i: abs(_num(rows[i][0].get(FV_COL)) / rows[i][1].units) for i in idx}
        med = statistics.median(per.values())
        if not med or sum(med / 2 <= q <= med * 2 for q in per.values()) / len(per) < UNITS_AGREE:
            continue
        for i, q in per.items():
            # רק הקטנה: שווי לחוזה זעיר מול העמיתים = כמות מנופחת. שווי לחוזה גדול לא מוכיח כמות
            # גדולה - השווי הוא רווח/הפסד מצטבר שתלוי במועד הכניסה (513026484_8765 ב-0425: 0.43-
            # חוזי ES בשווי 1.05 אלף ש"ח "תוקנו" ל-19.1- חוזים = 148%- מהמסלול)
            if q / med < 1 / UNITS_OUTLIER:
                row, r = rows[i]
                units = abs(_num(row.get(FV_COL))) / med * (1 if r.units > 0 else -1)
                rows[i] = (row, FuturesRow(**{**r.__dict__, "units": units}))
