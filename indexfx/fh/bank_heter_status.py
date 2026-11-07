"""כלי דיבאג חד-פעמי: מדפיס לכל בנק ב-bank_reference.csv (עם ח.פ מוכר)
את סטטוס היתר העסקה שלו כרגע (HARAV_LEVIN, חי) - כדי לענות על "אילו בנקים
נכנסים תחת 'ריבית בלי הת"ע'".

הרצה: python -m scripts.funds_holdings.bank_heter_status
"""
from . import heter_iska as heter_iska_module
from .bank_names import load_bank_reference
from .heter_iska import STATUS_NONE


def main():
    bank_ref = load_bank_reference()
    heter_by_chp = heter_iska_module.build()

    with_heter = []
    without_heter = []
    for name, entry in bank_ref.items():
        chp = entry["ח.פ"]
        if not chp:
            continue  # זר/TBD - לא "ריבית בלי הת"ע", אלא "בנק זר"/"בנק לא ידוע"
        status = heter_by_chp.get(chp, STATUS_NONE)
        (with_heter if status != STATUS_NONE else without_heter).append((name, chp))

    print(f"\n=== הת\"ע (יש היתר עסקה) - {len(with_heter)} בנקים ===")
    for name, chp in sorted(with_heter):
        print(f"  {name}  (ח.פ {chp})")

    print(f"\n=== ריבית בלי הת\"ע (יש ח.פ מוכר, אין היתר עסקה כרגע) - {len(without_heter)} בנקים ===")
    for name, chp in sorted(without_heter):
        print(f"  {name}  (ח.פ {chp})")


if __name__ == "__main__":
    main()
