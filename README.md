# INDEX-FX

חקר ההשפעה של שינויי מדדים (חו"ל/ארץ) וריבית על שער USD/ILS, דרך איזוני מדיניות של גופים מוסדיים.
תכנית מלאה: [PLAN.md](PLAN.md).

## הרצה (שלב א)
```bash
pip install pandas python-calamine
python scripts/a1_extract_positions.py --reports-dir <MASLULIM>/reports --out data/positions.csv.gz   # ~2 דק'
python scripts/a2_classify_exposure.py          # צורת חשיפה לכל החזקה
python scripts/a3_aggregate_validate.py --policy <Revach>/sharetracks_test/track_policy.json
```
קוד קריאת הדוחות ב-`indexfx/vendor/` הועתק מ-MASLULIM (`scripts/funds_holdings`); טבלת זיהוי המדדים מ-`index_exposure.py`.

## תוצרים (data/)
- `positions_classified.csv.gz` – כל החזקה עם `form` (צורת חשיפה), `index_key`, `fx_route`, `fx_exposure_k`.
- `fx_forward_legs.csv.gz` – רגלי פורוורד מט"ח בסימן (חיובי = ארוך מט"ח); `fx_forward_anomalies.csv.gz` – עסקאות שהוחרגו (רגליים לא מתאזנות).
- `track_exposure.csv` – לכל מסלול: מניות%, מט"ח% (ספוט + פורוורד).
- `validation_vs_policy.csv` – פער מול החשיפה בפועל שבקובץ המדיניות.
