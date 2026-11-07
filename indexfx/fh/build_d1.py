"""ממיר out/master.json, out/funds_detail.json, out/bonds_detail.json, out/index_exposure.json
ו-out/holdings_detail.json ל-master.sql/funds_detail.sql/bonds_detail.sql/index_exposure.sql/
holdings_detail.sql עבור wrangler d1 execute.
מקביל ל-build_d1.py/build_d1_tracks.py ב-revach.

DB: maslulim_autopilot (binding AUTOPILOT ב-Pages).
טבלת master: עמודת מפתח (PRIMARY KEY) + כמה עמודות לאינדוקס/סינון + data
  (JSON מלא של השורה - כל שאר השדות, כולל אלה שמשתנים בין ריצות כמו עמודות
  "קרן מחקה - X"). טבלאות funds_detail/bonds_detail: מפתח (לא ייחודי - ר'
  ROW_ITEM_LIMIT) + data (JSON array של חלק מרשימת הקרנות/האג"ח למסלול).

  שינוי מכוון: מסלול מוסדי גדול יכול להחזיק מאות אג"ח שונות בפועל (נבדק
  מול נתונים אמיתיים - עד ~800 ניירות למסלול) - JSON כזה חורג מתקרת
  אורך-סטייטמנט של D1 (~100KB, SQLITE_TOOBIG). לכן: מסלול שרשימתו גדולה
  מדי מפוצל למספר שורות פיזיות (אותו מפתח חוזר, כל שורה = חלק מהרשימה) -
  ה-API ב-revach מאחד אותן חזרה. מפתח כבר לא PRIMARY KEY (לא ייחודי).

הרצה: python -m funds_holdings.build_d1 --out-dir out
"""
import argparse
import base64
import gzip
import json
from pathlib import Path

MAX_BYTES = 80000  # תקרת D1 לסטייטמנט (~100KB), עם מרווח ביטחון
ROW_ITEM_LIMIT = 60000  # תקרת JSON לערך data בודד (שורה אחת), עם מרווח ביטחון גדול יותר

MASTER_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS master (\n"
    "  מפתח TEXT PRIMARY KEY,\n"
    "  ח_פ_חברה TEXT,\n"
    "  מספר_מסלול TEXT,\n"
    "  שם_חברה TEXT,\n"
    "  תחום TEXT,\n"
    "  כשרות TEXT,\n"
    "  data TEXT\n"
    ");\n"
    "CREATE INDEX IF NOT EXISTS idx_master_chp ON master(ח_פ_חברה);\n"
    "CREATE INDEX IF NOT EXISTS idx_master_domain ON master(תחום);\n"
)

INDEX_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS index_exposure (\n"
    "  מפתח TEXT PRIMARY KEY,\n"
    "  שם_חברה TEXT,\n"
    "  data TEXT\n"
    ");\n"
)


def detail_schema(table: str) -> str:
    return (
        f"CREATE TABLE IF NOT EXISTS {table} (\n"
        "  מפתח TEXT,\n"
        "  data TEXT\n"
        ");\n"
        f"CREATE INDEX IF NOT EXISTS idx_{table}_key ON {table}(מפתח);\n"
    )


def sql_str(s):
    if s is None:
        return "NULL"
    return "'" + str(s).replace("'", "''") + "'"


def write_batched(out_path: Path, table: str, schema: str, col_names: list[str], rows: list[tuple]):
    cols_clause = "(" + ",".join(col_names) + ")"
    header = f"INSERT INTO {table} {cols_clause} VALUES\n"

    with open(out_path, "w", encoding="utf-8") as out:
        out.write(schema)
        out.write(f"DELETE FROM {table};\n")

        batch = []
        batch_bytes = len(header.encode("utf-8"))

        def flush():
            nonlocal batch, batch_bytes
            if not batch:
                return
            out.write(header + ",\n".join(batch) + ";\n")
            batch = []
            batch_bytes = len(header.encode("utf-8"))

        written = 0
        for row in rows:
            tup = "(" + ",".join(row) + ")"
            tb = len(tup.encode("utf-8")) + 2
            if batch and batch_bytes + tb > MAX_BYTES:
                flush()
            batch.append(tup)
            batch_bytes += tb
            written += 1
        flush()
    return written


def build_master_sql(master: list[dict], out_path: Path) -> int:
    col_names = ["מפתח", "ח_פ_חברה", "מספר_מסלול", "שם_חברה", "תחום", "כשרות", "data"]
    rows = []
    for rec in master:
        key = rec.get("מפתח")
        if key is None:
            continue
        data_json = json.dumps(rec, ensure_ascii=False, separators=(",", ":"))
        rows.append((
            sql_str(key),
            sql_str(rec.get("ח.פ. חברה")),
            sql_str(rec.get("מס' מסלול")),
            sql_str(rec.get("שם החברה")),
            sql_str(rec.get("תחום")),
            sql_str(rec.get("כשרות")),
            sql_str(data_json),
        ))
    return write_batched(out_path, "master", MASTER_SCHEMA, col_names, rows)


def _chunk_items(items: list, limit: int) -> list[list]:
    """מפצל רשימת פריטים לצ'אנקים, כל אחד עם JSON מתחת ל-limit בייטים
    (הערכה - לא כולל תקורת מפריד הפסיקים המדויקת, יש מרווח ביטחון)."""
    chunks: list[list] = []
    current: list = []
    current_bytes = 2  # "[" + "]"
    for item in items:
        item_bytes = len(json.dumps(item, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + 1
        if current and current_bytes + item_bytes > limit:
            chunks.append(current)
            current = []
            current_bytes = 2
        current.append(item)
        current_bytes += item_bytes
    if current:
        chunks.append(current)
    return chunks or [[]]


def build_detail_sql(detail: dict[str, list], out_path: Path, table: str) -> int:
    col_names = ["מפתח", "data"]
    rows = []
    for key, items in detail.items():
        for chunk in _chunk_items(items, ROW_ITEM_LIMIT):
            data_json = json.dumps(chunk, ensure_ascii=False, separators=(",", ":"))
            rows.append((sql_str(key), sql_str(data_json)))
    return write_batched(out_path, table, detail_schema(table), col_names, rows)


HOLDINGS_SCHEMA = (
    "CREATE TABLE IF NOT EXISTS holdings_detail (\n"
    "  מפתח TEXT,\n"
    "  part INTEGER,\n"
    "  data TEXT\n"
    ");\n"
    "CREATE INDEX IF NOT EXISTS idx_holdings_detail_key ON holdings_detail(מפתח);\n"
)


def build_holdings_sql(holdings: dict[str, dict], out_path: Path) -> int:
    """פירוט החזקות מלא (holdings_detail.py): עד ~550KB JSON למסלול - נשמר כ-gzip+base64
    (~26MB לכל המסלולים במקום ~130MB), מפוצל לחלקים של ROW_ITEM_LIMIT לפי part.
    ה-API ב-revach מחבר את החלקים לפי הסדר ופותח את ה-gzip."""
    rows = []
    for key, payload in holdings.items():
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        b64 = base64.b64encode(gzip.compress(raw, 9)).decode("ascii")
        for part, i in enumerate(range(0, len(b64), ROW_ITEM_LIMIT)):
            rows.append((sql_str(key), str(part), sql_str(b64[i:i + ROW_ITEM_LIMIT])))
    return write_batched(out_path, "holdings_detail", HOLDINGS_SCHEMA, ["מפתח", "part", "data"], rows)


def build_index_sql(index_table: list[dict], out_path: Path) -> int:
    """פירוק החשיפה למניות לפי מדד (index_exposure.py) - שורה למסלול, עד ~9KB."""
    rows = [(sql_str(r["key"]), sql_str(r.get("company")),
             sql_str(json.dumps(r, ensure_ascii=False, separators=(",", ":"))))
            for r in index_table]
    return write_batched(out_path, "index_exposure", INDEX_SCHEMA, ["מפתח", "שם_חברה", "data"], rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, default=Path("out"))
    args = ap.parse_args()

    with open(args.out_dir / "master.json", encoding="utf-8") as f:
        master = json.load(f)
    with open(args.out_dir / "funds_detail.json", encoding="utf-8") as f:
        funds_detail = json.load(f)
    with open(args.out_dir / "bonds_detail.json", encoding="utf-8") as f:
        bonds_detail = json.load(f)

    with open(args.out_dir / "index_exposure.json", encoding="utf-8") as f:
        index_table = json.load(f)

    n1 = build_master_sql(master, args.out_dir / "master.sql")
    n2 = build_detail_sql(funds_detail, args.out_dir / "funds_detail.sql", "funds_detail")
    n3 = build_detail_sql(bonds_detail, args.out_dir / "bonds_detail.sql", "bonds_detail")
    print(f"[build_d1] master: {n1} שורות -> {args.out_dir}/master.sql")
    print(f"[build_d1] funds_detail: {n2} שורות -> {args.out_dir}/funds_detail.sql")
    print(f"[build_d1] bonds_detail: {n3} שורות -> {args.out_dir}/bonds_detail.sql")
    n4 = build_index_sql(index_table, args.out_dir / "index_exposure.sql")
    print(f"[build_d1] index_exposure: {n4} שורות -> {args.out_dir}/index_exposure.sql")
    holdings_path = args.out_dir / "holdings_detail.json"
    if holdings_path.exists():
        with open(holdings_path, encoding="utf-8") as f:
            holdings = json.load(f)
        n5 = build_holdings_sql(holdings, args.out_dir / "holdings_detail.sql")
        print(f"[build_d1] holdings_detail: {n5} שורות -> {args.out_dir}/holdings_detail.sql")


if __name__ == "__main__":
    main()
