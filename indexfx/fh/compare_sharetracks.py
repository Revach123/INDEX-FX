"""השוואה: הרכב המסלולים הידני ב-/sharetracks מול הפירוק האוטומטי לפי מדד.

שורה ב-sharetracks_data = (מוצר, חברה, סוג מסלול) + רשימת מדדים ואחוזים (ידני).
מסלולים מ-out/index_exposure.json מקובצים לאותו מפתח בדיוק כמו בדף
(product = "סוג קרן", company = "שם החברה", SUBTYPE_MAP על "סוג מסלול"),
ושמות המדדים הידניים מתורגמים לאותו אוצר מדדים (index_exposure.classify_index).
ההשוואה היא בחלקים מתוך החשיפה למניות (הידני מסתכם ל-100% מהמניות).

הרצה: python -m scripts.funds_holdings.compare_sharetracks --out-dir out
"""
from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

import requests

from .index_exposure import classify_index

SHARETRACKS_URL = "https://revach.pages.dev/api/sharetracks"
MATCH_KEY_ENV = "REVACH_MATCH_KEY"
SUBTYPE_MAP = {  # כמו sharetracks/index.html
    "עוקב מדד s&p 500": "sp500", "עוקב מדדי מניות": "mdadim", "מניות סחיר": "sachir",
    "קיימות": "kiyamut", "הלכה": "halacha", "עוקב מדדים - גמיש": "gamiš", "עוקב מדדים גמיש": "gamiš",
}


def _pct(v) -> float | None:
    try:
        return float(str(v).replace("%", "").strip()) / 100
    except (TypeError, ValueError):
        return None


def fetch_sharetracks() -> list[dict]:
    key = (os.environ.get(MATCH_KEY_ENV) or "").strip()
    r = requests.get(SHARETRACKS_URL, headers={"X-Match-Key": key, "Accept": "application/json"}, timeout=60)
    r.raise_for_status()
    return r.json()


def manual_shares(indices: list[dict]) -> dict[str, tuple[str, float]]:
    out: dict[str, list] = {}
    for i in indices or []:
        idx, label = classify_index(i.get("n"))
        p = _pct(i.get("p"))
        if p is None:
            continue
        cur = out.setdefault(idx, [i.get("n"), 0.0])
        cur[1] += p
    return {k: (v[0], v[1]) for k, v in out.items()}


def auto_shares(tracks: list[dict]) -> tuple[dict[str, tuple[str, float]], float]:
    """ממוצע (לפי מסלול) של חלק כל מדד מתוך החשיפה למניות של המסלול."""
    acc: dict[str, list] = {}
    eq = []
    for t in tracks:
        tot = t.get("equity_total") or 0.0
        eq.append(tot)
        if tot <= 0:
            continue
        for e in t["indices"]:
            cur = acc.setdefault(e["id"], [e["label"], 0.0])
            cur[1] += e["pct"] / tot / len(tracks)
    return {k: (v[0], v[1]) for k, v in acc.items()}, (sum(eq) / len(eq) if eq else 0.0)


def auto_local(tracks: list[dict]) -> tuple[float | None, str, str]:
    """ממוצע (לפי מסלול) של חלק המניות בארץ מתוך החשיפה למניות ("il" לכל מדד),
    ו-3 המדדים המובילים בארץ / בחו"ל."""
    shares, loc, frn = [], defaultdict(float), defaultdict(float)
    for t in tracks:
        tot = t.get("equity_total") or 0.0
        if tot <= 0:
            continue
        shares.append(sum(e["pct"] for e in t["indices"] if e.get("il")) / tot)
        for e in t["indices"]:
            (loc if e.get("il") else frn)[e["label"]] += e["pct"] / tot / len(tracks)
    top = lambda d: ", ".join(n for n, _ in sorted(d.items(), key=lambda x: -x[1])[:3])
    return (sum(shares) / len(shares) if shares else None), top(loc), top(frn)


def _match(row: dict, groups, by_num, child) -> list[dict]:
    """אותה התאמה כמו בדף: ביטוח לפי מספר מסלול, חיסכון לכל ילד לפי חברה (המסלולים
    הכשרים), השאר לפי (מוצר, חברה, סוג מסלול)."""
    d = row.get("data") or {}
    if row.get("product") == "פוליסות חסכון":
        return by_num.get(str(d.get("track_number") or "").strip(), [])
    if row.get("product") == "חיסכון לכל ילד":
        return child.get(row.get("company"), [])
    return groups.get((row.get("product"), row.get("company"), row.get("subtype")), [])


def compare_local(share_rows: list[dict], index_table: list[dict]) -> list[dict]:
    """"מניות בארץ" הידני (local_pct / pct_il, local_idx, foreign_idx) מול החלק
    האוטומטי של המניות בארץ ומדדיו."""
    groups, by_num, child = _index_groups(index_table)
    out = []
    for row in share_rows:
        d = row.get("data") or {}
        man = _pct(d.get("local_pct") or d.get("pct_il"))
        if man is None and not d.get("local_idx") and not d.get("foreign_idx"):
            continue
        tracks = _match(row, groups, by_num, child)
        auto, loc, frn = auto_local(tracks)
        out.append({"product": row.get("product"), "company": row.get("company"), "subtype": row.get("subtype"),
                    "tracks": [t["key"] for t in tracks], "manual_local": man, "auto_local": auto,
                    "manual_local_idx": d.get("local_idx") or "", "manual_foreign_idx": d.get("foreign_idx") or "",
                    "mode": d.get("mode") or "", "auto_local_idx": loc, "auto_foreign_idx": frn})
    return out


def _index_groups(index_table: list[dict]):
    groups: dict[tuple, list[dict]] = defaultdict(list)
    by_num: dict[str, list[dict]] = defaultdict(list)  # ביטוח: לפי מספר מסלול, כמו insuranceCompByNum בדף
    child: dict[str, list[dict]] = defaultdict(list)   # חיסכון לכל ילד: לפי חברה, רק מסלולים כשרים
    for t in index_table:
        if t.get("product") in ("ביטוח", "ביטוח (ישן)"):
            by_num[str(t.get("track_number") or t["key"].split("_")[1]).strip()].append(t)
        if t.get("product") == "חסכון לכל ילד" and t.get("kosher") == "יש":
            child[t.get("company")].append(t)
        sub = SUBTYPE_MAP.get(str(t.get("track_type") or "").strip().lower())
        if sub:
            groups[(t.get("product"), t.get("company"), sub)].append(t)
    return groups, by_num, child


def compare(share_rows: list[dict], index_table: list[dict]) -> list[dict]:
    groups, by_num, child = _index_groups(index_table)
    out = []
    for row in share_rows:
        indices = (row.get("data") or {}).get("indices")
        if not isinstance(indices, list) or not indices:
            continue
        key = (row.get("product"), row.get("company"), row.get("subtype"))
        tracks = _match(row, groups, by_num, child)
        man = manual_shares(indices)
        if not man:  # שורה בלי אחוזים (רק שמות) - אין מה להשוות
            continue
        auto, eq = auto_shares(tracks)
        ids = set(man) | set(auto)
        overlap = sum(min(man.get(i, ("", 0))[1], auto.get(i, ("", 0))[1]) for i in ids)
        out.append({
            "product": key[0], "company": key[1], "subtype": key[2],
            "tracks": [t["key"] for t in tracks], "equity_total": eq,
            "overlap": overlap if tracks else None,
            "manual": sorted(((v[0], v[1], i) for i, v in man.items()), key=lambda x: -x[1]),
            "auto": sorted(((v[0], v[1], i) for i, v in auto.items()), key=lambda x: -x[1]),
        })
    return out


def to_markdown(rows: list[dict], top: int = 8) -> str:
    lines = ["| מוצר | חברה | סוג | מסלולים | חפיפה | ידני (sharetracks) | אוטומטי (מהדוחות) |",
             "|---|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda r: (r["overlap"] is None, r["overlap"] or 0)):
        man = "<br>".join(f"{n} {p*100:.0f}%" for n, p, _ in r["manual"][:top])
        auto = "<br>".join(f"{n} {p*100:.0f}%" for n, p, _ in r["auto"][:top]) or "—"
        ov = "אין מסלול תואם" if r["overlap"] is None else f"{r['overlap']*100:.0f}%"
        lines.append(f"| {r['product']} | {r['company']} | {r['subtype']} | {len(r['tracks'])} | {ov} | {man} | {auto} |")
    return "\n".join(lines)


def local_markdown(rows: list[dict]) -> str:
    f = lambda v: "—" if v is None else f"{v*100:.0f}%"
    lines = ["| מוצר | חברה | סוג | מסלולים | בארץ ידני | בארץ אוטומטי | פער | בארץ ידני - מדדים | בארץ אוטומטי | חו\"ל ידני | חו\"ל אוטומטי |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    key = lambda r: -abs((r["auto_local"] or 0) - (r["manual_local"] or 0)) if None not in (r["auto_local"], r["manual_local"]) else 1
    for r in sorted(rows, key=key):
        gap = "—" if None in (r["auto_local"], r["manual_local"]) else f"{(r['auto_local'] - r['manual_local'])*100:+.0f}"
        cell = lambda s: str(s).replace("\n", " / ").replace("|", "/") or "—"
        lines.append(f"| {r['product']} | {r['company']} | {r['subtype']} | {len(r['tracks'])} | {f(r['manual_local'])} | "
                     f"{f(r['auto_local'])} | {gap} | {cell(r['manual_local_idx'])} | {cell(r['auto_local_idx'])} | "
                     f"{cell(r['manual_foreign_idx'])} | {cell(r['auto_foreign_idx'])} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path("out"))
    args = ap.parse_args()
    index_table = json.load(open(args.out_dir / "index_exposure.json", encoding="utf-8"))
    share_rows = fetch_sharetracks()
    rows = compare(share_rows, index_table)
    local = compare_local(share_rows, index_table)
    (args.out_dir / "sharetracks_compare.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    md = to_markdown(rows)
    lmd = local_markdown(local)
    (args.out_dir / "sharetracks_compare.md").write_text(md + "\n\n" + lmd, encoding="utf-8")
    (args.out_dir / "sharetracks_compare_local.json").write_text(json.dumps(local, ensure_ascii=False, indent=1),
                                                                 encoding="utf-8")
    matched = [r for r in rows if r["overlap"] is not None]
    print(f"[compare] {len(rows)} שורות הרכב ידני; {len(matched)} עם מסלול תואם; "
          f"חפיפה ממוצעת {sum(r['overlap'] for r in matched) / max(len(matched), 1) * 100:.0f}%")
    print(md)
    both = [r for r in local if None not in (r["manual_local"], r["auto_local"])]
    print(f"\n[compare] מניות בארץ: {len(local)} שורות ידניות; {len(both)} עם מסלול תואם; פער מוחלט ממוצע "
          f"{sum(abs(r['auto_local'] - r['manual_local']) for r in both) / max(len(both), 1) * 100:.1f} נק' אחוז")
    print(lmd)
    hd_path = args.out_dir / "holdings_detail.json"
    hd = json.load(open(hd_path, encoding="utf-8")) if hd_path.exists() else {}
    print(local_detail(both, index_table, hd))
    print(overlap_detail(matched, hd))


def holdings_lines(key: str, hd: dict, top: int = 10) -> list[str]:
    """ההחזקות הגדולות בחשיפה למניות של מסלול (holdings_detail): שם, רכיב, חשיפה והמדד ששויך."""
    d = hd.get(key) or {}
    cols, cats = d.get("cols") or [], d.get("cats") or []
    if not cols:
        return []
    ix = {c: i for i, c in enumerate(cols)}
    rows = [r for r in d.get("rows") or [] if r[ix["equity"]]]
    rows.sort(key=lambda r: -abs(r[ix["equity"]] or 0))
    out = []
    for r in rows[:top]:
        idx = ", ".join(f"{i} {v * 100:.1f}" for i, v in (r[ix["idx"]] or []))
        cat = cats[r[ix["cat"]]] if isinstance(r[ix["cat"]], int) and r[ix["cat"]] < len(cats) else r[ix["cat"]]
        out.append(f"[compare-hold] {key}   {r[ix['equity']] * 100:6.2f}  {cat} | {r[ix['name']]} | "
                   f"{r[ix['country']] or ''} | {r[ix['component']] or ''} -> {idx}")
    return out


def overlap_detail(rows: list[dict], hd: dict, max_overlap: float = 0.6) -> str:
    """שורות עם חפיפה נמוכה להרכב הידני - ההחזקות שמאחורי הפירוק האוטומטי, לבדיקת הסיווג."""
    lines = []
    for r in rows:
        if r["overlap"] is None or r["overlap"] >= max_overlap:
            continue
        for k in r["tracks"][:2]:
            lines += holdings_lines(k, hd)
    return "\n".join(lines)


def local_detail(rows: list[dict], index_table: list[dict], hd: dict | None = None, min_gap: float = 0.05) -> str:
    """פירוט לכל מסלול בשורה עם פער של 5 נק' ומעלה: החשיפה למניות, ממה מורכב החלק בארץ (מדד ומקור:
    מניות ישירות / קרנות / חוזים / אופציות / סוואפים) והמדדים בחו"ל - כדי להבחין בין שינוי אמיתי במסלול
    לבין סיווג שגוי שלנו."""
    by_key = {t["key"]: t for t in index_table}
    fmt = lambda v: f"{v * 100:.1f}"
    lines = []
    for r in sorted(rows, key=lambda r: -abs(r["auto_local"] - r["manual_local"])):
        if abs(r["auto_local"] - r["manual_local"]) < min_gap:
            continue
        for k in r["tracks"]:
            t = by_key.get(k) or {}
            tot = t.get("equity_total") or 0.0
            if tot <= 0:
                continue
            loc = [e for e in t["indices"] if e.get("il")]
            frn = [e for e in t["indices"] if not e.get("il")]
            part = lambda es: "; ".join(f"{e['label']} {fmt(e['pct'])} (" + ", ".join(
                f"{s} {fmt(v)}" for s, v in e["sources"].items()) + ")" for e in es[:5])
            lines.append(f"[compare-local] {r['company']} {r['product']} {k} דוח {t.get('report_month')} "
                         f"מניות {fmt(tot)} | בארץ {fmt(sum(e['pct'] for e in loc))}: {part(loc)} | "
                         f"חו\"ל {fmt(sum(e['pct'] for e in frn))}: {part(frn)}")
            if abs(r["auto_local"] - r["manual_local"]) >= 0.08:
                lines += holdings_lines(k, hd or {}, top=6)
    return "\n".join(lines)


if __name__ == "__main__":
    main()
