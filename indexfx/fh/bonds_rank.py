"""אג"ח/ני"ע: worst-case לכל מסלול, לפי היתר עסקה (HARAV_LEVIN) ועדה,
בדיוק לפי סדר העדיפות שהמשתמש קבע (סדר עולה - הכי גרוע ראשון):
"אג"ח לא מזוהה" < "אין" < "בעלות גוי" < "כללי" < "פרטי" < "עדה?" < "עדה".

מקור: לא חלק מ-Autopilot_Section1.m - הרחבה חדשה, לפי הנחיית המשתמש.

התאמה: מספר נייר ערך (ISIN, "סוג מספר נייר ערך"=="ISIN" כשהעמודה קיימת;
"איגרות חוב ממשלתיות" חסרה עמודת-סוג אך הערכים בפורמט ISIN גם שם) מול
bonds_heter_reference.py (isin -> heter_bucket/ada_status/asset_class).
קטגוריית "לא סחיר איגרות חוב מיועדות" מוחרגת - מזהה מספרי פנימי (לא
ISIN), אג"ח מיועדות/ערד שמונפקות ע"י המדינה (כמו אג"ח ממשלתי).

שינוי מכוון (לפי הנחיית המשתמש): היתר עסקה רלוונטי רק לאג"ח קונצרני/
ני"ע מסחריים - לא לאג"ח ממשלתי/מק"מ. נייר תואם עם heter_bucket ==
"לא רלוונטי" כבר מסומן ככה ע"י revach; בנוסף, מזהים ממשלתי/מק"מ גם
"ביד" (שם/ISIN, ר' _is_gov_or_makam) כי כ-9% מה-ISIN-ים בדוחות לא
נמצאים ב-bonds_heter.json בכלל (טרם נסרקו ב-revach) - בלעדי הבדיקה
הזו, אג"ח ממשלתי לא-ממופה היה מסומן "לא מזוהה" בטעות, במקום להיות
מוחרג לגמרי כמו כל אג"ח ממשלתי אחר. נייר "לא רלוונטי" - לא נכלל בכלל
בדירוג. לכל נייר אחר: הרמה היא הטובה מבין heter_bucket ו-ada_status.
"""
from .excel_io import text_from

BOND_CATEGORIES = {
    "איגרות חוב", "איגרות חוב ממשלתיות", "ניירות ערך מסחריים",
    "לא סחיר איגרות חוב", "לא סחיר איגרות חוב ממשלתיות",
    "לא סחיר ניירות ערך מסחריים",
}
SECNO_TYPE_COL = "סוג מספר נייר ערך"
SECNO_COL = "מספר נייר ערך"
SECNAME_COL = "שם נייר ערך"

UNIDENTIFIED = 'אג"ח לא מזוהה'
NOT_RELEVANT = "לא רלוונטי"
LEVELS = [UNIDENTIFIED, "אין", "בעלות גוי", "כללי", "פרטי", "עדה?", "עדה"]
_RANK = {level: i for i, level in enumerate(LEVELS)}

# אותם דפוסים כמו coarse_type() ב-revach/scripts/classify.py, מותאמים
# ל"שם נייר ערך" (יש לנו רק את השם, לא את security_type הרשמי מ-TASE).
GOV_ASSET_CLASSES = {'אג"ח ממשלתי', "מק\"מ"}
GOV_NAME_MARKERS = ("ממשלת", "מלוה קצר", "מלווה קצר", 'מק"מ')
MAKAM_ISIN_PREFIX = "IL008"


def _is_gov_or_makam(name: str | None, isin: str | None, asset_class: str | None = None) -> bool:
    if asset_class in GOV_ASSET_CLASSES:
        return True
    if isin and isin.startswith(MAKAM_ISIN_PREFIX):
        return True
    n = name or ""
    return any(marker in n for marker in GOV_NAME_MARKERS)


def _bond_level(entry: dict | None, name: str | None = None, isin: str | None = None) -> str | None:
    """None אם לא רלוונטי (אג"ח ממשלתי/מק"מ) - לא נכלל בכלל בדירוג."""
    if entry is not None:
        if entry.get("heter_bucket") == NOT_RELEVANT or _is_gov_or_makam(name, isin, entry.get("asset_class")):
            return None
        ada = entry.get("ada_status")
        rank = _RANK.get(entry.get("heter_bucket"), _RANK["אין"])
        if ada and _RANK.get(ada, -1) > rank:
            rank = _RANK[ada]
        return LEVELS[rank]
    if _is_gov_or_makam(name, isin):
        return None
    return UNIDENTIFIED


def build_bonds_rank(source: list[dict], bonds_heter_by_isin: dict[str, dict]) -> dict[str, dict]:
    """מפתח -> {"אג\"ח": רמה}. מסלול בלי שום אג"ח מזוהה (רלוונטי) - לא מופיע."""
    worst_rank: dict[str, int] = {}
    for rec in source:
        if rec["Category"] not in BOND_CATEGORIES or rec["מידע"] != "מידע":
            continue
        for row in rec["Clean"]:
            track = row.get("מספר מסלול")
            if track is None or track == "":
                continue
            type_val = row.get(SECNO_TYPE_COL)
            if type_val is not None and type_val != "ISIN":
                continue  # "פנימי"/"אחר"/ריק/וכו' - לא ISIN, לא ניתן להצליב
            isin = row.get(SECNO_COL)
            if not isin or not isinstance(isin, str) or not isin.startswith("IL"):
                continue

            entry = bonds_heter_by_isin.get(isin)
            level = _bond_level(entry, row.get(SECNAME_COL), isin)
            if level is None:
                continue  # לא רלוונטי (ממשלתי/מק"מ)

            key = f"{rec['LegalId']}_{text_from(track)}"
            rank = _RANK[level]
            cur = worst_rank.get(key)
            if cur is None or rank < cur:
                worst_rank[key] = rank

    return {key: {'אג"ח': LEVELS[rank]} for key, rank in worst_rank.items()}
