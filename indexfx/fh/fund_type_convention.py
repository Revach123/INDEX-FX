"""קרנות השקעה שהחברה סופרת בחשיפה למניות הרשמית - מוסכמה לכל חברה, נלמדת מהנתונים.

רוב הגופים לא סופרים קרנות השקעה (פרייבט אקוויטי, קרנות גידור) ב-STOCK_MARKET_EXPOSURE,
וחלקם כן - כל אחד לפי סוג הקרן ("מאפיין עיקרי" בגיליון קרנות השקעה):
  510142789_233 (בל"ד): פרייבט אקוויטי 5.85%, פער -5.69 -> 0.16 כשנספר.
  520032269 (6 מסלולים): קרנות גידור, סכום |פער| 3.97 -> 0.15.
  512267592 / 513173393 / 512065202 ועוד: לא סופרים - הוספה מנפחת את הפער פי 5-10.
לכן לא כלל גלובלי: לכל חברה בוחרים את קבוצת הסוגים (עד MAX_TYPES) שממזערת את סכום
הפערים מול הנתון הרשמי על כל מסלוליה, ומקבלים אותה רק בשיפור ברור (MIN_GAIN, MAX_RATIO).
חברה בלי קרנות השקעה, או שהסוגים שלה לא משפרים - נשארת בלי (ברירת המחדל)."""
from __future__ import annotations

import itertools
from collections import defaultdict

from .excel_io import to_ratio
from .sheet_source import PCT_COL

INVEST_FUND_MARK = "קרנות השקעה"  # "קרנות השקעה" / "לא סחיר קרנות השקעה"
TYPE_COL = "מאפיין עיקרי"
# סוגים שיש בהם רכיב מניות; קרנות חוב / נדל"ן לא נבחנות
CANDIDATE_TYPES = ("פרייבט אקוויטי", "קרן גידור (Hedge Fund)", "קרן השקעה אחרת", "קרן אנרגיה ותשתיות")
MAX_TYPES = 2
MIN_GAIN = 0.01        # שיפור מינימלי בסכום |פער| (נק' אחוז), כפול שורש מספר המסלולים
MAX_RATIO = 0.6        # הסכום אחרי <= 60% מהסכום לפני
# תקרה לפער של מסלול בודד בלמידה - מסלול עם תקלת דיווח (514956465_15882: +24) לא חוסם
# את ההחלטה לשאר מסלולי החברה
ERR_CAP = 0.05


def fund_type_pct(source: list[dict]) -> dict[str, dict[str, float]]:
    """מפתח -> {סוג קרן השקעה: שיעור מנכסי המסלול}."""
    out: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for rec in source:
        if INVEST_FUND_MARK not in rec["Category"] or rec["מידע"] != "מידע":
            continue
        for row in rec["Clean"]:
            key, pct = row.get("מפתח"), to_ratio(row.get(PCT_COL))
            kind = str(row.get(TYPE_COL) or "").strip()
            if key and pct and kind in CANDIDATE_TYPES:
                out[key][kind] += pct
    return {k: dict(v) for k, v in out.items()}


def learn_counted_types(model: dict[str, float], official: dict[str, float],
                        type_pct: dict[str, dict[str, float]]) -> dict[str, tuple[str, ...]]:
    """חברה -> סוגי קרנות ההשקעה שהיא סופרת כמניות. model / official: מפתח -> חשיפה (שבר)."""
    by_co: dict[str, list[tuple[float, dict[str, float]]]] = defaultdict(list)
    for key, off in official.items():
        if key in model and off is not None:
            by_co[key.split("_")[0]].append((model[key] - off, type_pct.get(key, {})))
    out = {}
    for co, rows in by_co.items():
        present = [t for t in CANDIDATE_TYPES if any(d.get(t) for _, d in rows)]
        if not present:
            continue
        # רק מסלולים שמחזיקים קרן מהסוגים האלה - בשאר אין מה להשתנות (520042581: 3 מתוך 10)
        rows = [(e, d) for e, d in rows if any(d.get(t) for t in present)]
        base = sum(min(ERR_CAP, abs(e)) for e, _ in rows)
        best, best_types = base, ()
        for n in range(1, MAX_TYPES + 1):
            for types in itertools.combinations(present, n):
                s = sum(min(ERR_CAP, abs(e + sum(d.get(t, 0.0) for t in types))) for e, d in rows)
                if s < best:
                    best, best_types = s, types
        if best_types and base - best >= MIN_GAIN * len(rows) ** 0.5 and best <= MAX_RATIO * base:
            out[co] = best_types
    return out


def counted_fund_equity(type_pct: dict[str, dict[str, float]],
                        conventions: dict[str, tuple[str, ...]]) -> dict[str, float]:
    """מפתח -> שיעור קרנות ההשקעה שהחברה סופרת כמניות."""
    out = {}
    for key, d in type_pct.items():
        types = conventions.get(key.split("_")[0])
        if types:
            v = sum(d.get(t, 0.0) for t in types)
            if v:
                out[key] = v
    return out


_TYPE_IDS = {"פרייבט אקוויטי": "pe", "קרן גידור (Hedge Fund)": "hedge",
             "קרן השקעה אחרת": "other", "קרן אנרגיה ותשתיות": "infra"}
LOCATION_COL = 'ישראל/חו"ל'


def official_at_report(tracks: list[dict], track_key, report_month: dict[str, str]) -> dict[str, float]:
    """מפתח -> החשיפה הרשמית לחודש הדוח (data.gov.il, כמו ב-validate), ואם אין - האחרונה ב-tracks.
    הלמידה מול החודש האחרון (אוגוסט מול דוח יוני) רועשת - חודשיים של תנועה בשוק ובתיק."""
    out = official_from_tracks(tracks, track_key)
    try:
        from .official_history import fetch_stock_exposure
        hist = fetch_stock_exposure({m for m in report_month.values() if m})
    except Exception as e:  # רשת
        print(f"[fund_type] data.gov.il לא זמין - לפי הנתון האחרון ב-tracks: {e}")
        return out
    for t in tracks:
        key = track_key(t)
        if key is None:
            continue
        v = hist.get((str(t.get("תחום") or "").strip(), key.split("_", 1)[1], report_month.get(key, "")))
        if v is not None:
            out[key] = v
    return out


def official_from_tracks(tracks: list[dict], track_key) -> dict[str, float]:
    """מפתח -> "חשיפה למניות" הרשמית (שבר) מ-tracks - כמו ב-validate_equity_exposure."""
    out = {}
    for t in tracks:
        key = track_key(t)
        raw = t.get("חשיפה למניות") or t.get("STOCK_MARKET_EXPOSURE")
        if key is None or raw in (None, ""):
            continue
        v = to_ratio(raw) if isinstance(raw, str) else raw
        try:
            v = float(v)
        except (TypeError, ValueError):
            continue
        out[key] = v / (100 if abs(v) > 1.5 else 1)
    return out


def add_counted_to_index(index_exp: dict[str, dict], source: list[dict],
                         conventions: dict[str, tuple[str, ...]], trace: dict | None = None) -> int:
    """מוסיף לפירוק לפי מדד (index_exposure) את קרנות ההשקעה שהחברה סופרת כמניות, שורה
    שורה (כולל השיוך ב-trace לדף ההחזקות). מחזיר את מספר השורות שנוספו."""
    n = 0
    for rec in source:
        if INVEST_FUND_MARK not in rec["Category"] or rec["מידע"] != "מידע":
            continue
        for row in rec["Clean"]:
            key, pct = row.get("מפתח"), to_ratio(row.get(PCT_COL))
            kind = str(row.get(TYPE_COL) or "").strip()
            if not key or not pct or kind not in conventions.get(str(key).split("_")[0], ()):
                continue
            local = "ישראל" in str(row.get(LOCATION_COL) or "")
            idx = f"private:{_TYPE_IDS[kind]}" + (":il" if local else "")
            label = f"{kind}{' בישראל' if local else ''} (נספר כמניות בדיווח החברה)"
            exp = index_exp.setdefault(key, {"total": 0.0, "indices": {}})
            ent = exp["indices"].setdefault(idx, {"label": label, "pct": 0.0, "sources": {}})
            ent["pct"] += pct
            ent["sources"]["investment_funds"] = ent["sources"].get("investment_funds", 0.0) + pct
            exp["total"] += pct
            if trace is not None:
                trace.setdefault("rows", {}).setdefault(id(row), []).append((idx, pct))
                trace.setdefault("labels", {}).setdefault(idx, label)
            n += 1
    return n
