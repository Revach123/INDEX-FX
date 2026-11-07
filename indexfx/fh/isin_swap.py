"""החלפה ISIN איריות: שורות נתוני קרנות עם "IE" ב-ISIN, {ISIN, מספר קרן} בלבד.

מקור: Autopilot_Section1.m, שאילתת החלפה ISIN איריות.
"""


def build_isin_swap(funds_ref: list[dict]) -> list[dict]:
    return [
        {"ISIN": r["ISIN"], "מספר קרן": r["מספר קרן"]}
        for r in funds_ref
        if r.get("ISIN") and "IE" in r["ISIN"]
    ]
