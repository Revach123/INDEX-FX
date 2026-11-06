"""FileList: הקובץ האחרון לכל CompanyType (LegalId_SystemName).

מקור: Autopilot_Section1.m, שאילתת FileList.
במקור: Folder.Files על תיקייה שטוחה במחשב המשתמש. אצלנו: reports/<year>Q<quarter>/
ב-repo MASLULIM (README.md), אז סורקים רקורסיבית על כל תת-התיקיות.
"""
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class ReportFile:
    name: str            # שם הקובץ בלי הנתיב, למשל "511789190_pn_0226.xlsx"
    path: Path           # נתיב מלא
    company_type: str    # "570009852_gm" (Parts[0] & "_" & Parts[1])
    sort_key: int         # YY*10 + QQ, מהחלק האחרון של השם - להשוואת "העדכני ביותר"
    report_month: date | None  # היום האחרון של רבעון הדיווח (ר' _report_month)


def _stem_parts(filename: str) -> list[str]:
    stem = filename.rsplit(".", 1)[0]
    return stem.split("_")


def _sort_key(last_part: str) -> int:
    """Number.From(Text.End(Last, 2)) * 10 + Number.From(Text.Start(Last, 2))."""
    yy = int(last_part[-2:])
    qq = int(last_part[:2])
    return yy * 10 + qq


def _report_month(last_part: str) -> date | None:
    """QQYY (למשל '0226' = רבעון 2 2026) -> היום האחרון של הרבעון (30.6.2026).

    הסיומת היא רבעון, לא חודש: קיימות רק 01-04, תיקיות reports/2026Q2 וכו',
    וחוזי המדד בקבצים תואמים (0124->ESM4, 0224->ESU4, 0324->ESZ4, 0424->ESH5),
    וכך גם המחיר: ESU6 ב-0226 = 7,548.25 מול S&P 500 = 7,499 ב-30.6.2026
    (6,879 ב-27.2.2026)."""
    try:
        qq = int(last_part[:2])
        yy = int(last_part[-2:])
        if not 1 <= qq <= 4:
            return None
        mm = qq * 3
        return date(2000 + yy, mm, monthrange(2000 + yy, mm)[1])
    except (ValueError, IndexError):
        return None


def list_files(reports_dir: Path) -> list[ReportFile]:
    """כל קבצי ה-xlsx תחת reports_dir, עם CompanyType ו-SortKey."""
    out = []
    # סיומת בלי תלות באותיות גדולות/קטנות (520023094_pn_0126.XLSX)
    for p in sorted(x for x in reports_dir.rglob("*") if x.is_file() and x.suffix.lower() == ".xlsx"):
        parts = _stem_parts(p.name)
        if len(parts) < 2:
            continue  # שם שלא תואם לתבנית הצפויה - לא ניתן לסווג, מדולג
        company_type = f"{parts[0]}_{parts[1]}"
        last = parts[-1]
        try:
            sort_key = _sort_key(last)
        except (ValueError, IndexError):
            continue  # לא ניתן לחשב SortKey - מדולג (ראה TODO בהערת המודול)
        out.append(ReportFile(name=p.name, path=p, company_type=company_type, sort_key=sort_key,
                               report_month=_report_month(last)))
    return out


def latest_per_company(files: list[ReportFile]) -> list[ReportFile]:
    """Table.Group by CompanyType, שומר רק את השורה עם ה-SortKey המקסימלי."""
    best: dict[str, ReportFile] = {}
    for f in files:
        cur = best.get(f.company_type)
        if cur is None or f.sort_key > cur.sort_key:
            best[f.company_type] = f
    return list(best.values())


def get_file_list(reports_dir: Path) -> list[ReportFile]:
    return latest_per_company(list_files(reports_dir))
