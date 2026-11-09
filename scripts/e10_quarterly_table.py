"""טבלה רבעונית: תנועת השוק, שינוי בהחזקות המט"ח, וקנייה/מכירה של מט"ח לפי סיבה - מסלולים + קרנות מחקות, מול בנק ישראל.

כל הערכים מהנתונים שכבר נמשכו/חושבו (אין הנחות חדשות):
  שוק:   S&P 500, ת"א-125, ת"א-35 (סוף רבעון מול סוף רבעון, data/market/prices.csv), USD/ILS יציג (בנק ישראל)
  החזקות: חשיפת מט"ח רשמית של כל מסלולי הגמל/פנסיה/ביטוח (data.gov, FOREIGN_CURRENCY_EXPOSURE, מיליוני ש"ח), סוף רבעון
  קנייה/מכירה במסלולים: e9 (פירוק לפי מכשיר, מדוחות הנכסים הרבעוניים), + = קניית מט"ח נטו
  קרנות מחקות על חו"ל: b7 (חוזי אקדמה בפועל, דוח חודשי מלא) - בגלל תנועת המדד / בגלל הנפקות-פדיונות; זמין מ-5.2025
  בנק ישראל: WEB_TV_EX_IL_INST_Q - עסקאות מט"ח נטו של הגופים המוסדיים (מיליוני דולר) -> מיליארדי ש"ח בשער ממוצע ברבעון
הרבעון בטבלה = הרבעון שבו התרחשה התנועה (q0 של e9 + 1).
פלט: data/results/quarterly_table.csv, data/market/boi_inst_fx_q.csv
"""
import io
import urllib.request

import numpy as np
import pandas as pd

UA = {"User-Agent": "index-fx-research/0.1"}
BOI = "https://edge.boi.gov.il/FusionEdgeServer/sdmx/v2/data/dataflow/BOI.STATISTICS/DRV/1.0?startperiod=2018-01-01&format=csv"

# --- בנק ישראל: עסקאות מט"ח נטו לפי מגזר (רבעוני)
raw = urllib.request.urlopen(urllib.request.Request(BOI, headers=UA), timeout=600).read()
b = pd.read_csv(io.BytesIO(raw), low_memory=False)
b = b[(b.FREQ == "Q") & b.SERIES_CODE.str.startswith("WEB_TV_EX_")]
bw = b.pivot_table(index="TIME_PERIOD", columns="SERIES_CODE", values="OBS_VALUE")
bw.columns = [c.replace("WEB_TV_EX_", "").replace("_Q", "") for c in bw.columns]
bw.to_csv("data/market/boi_inst_fx_q.csv")
bw.index = pd.PeriodIndex(bw.index.str.replace("-", ""), freq="Q")

# --- שוק
px = pd.read_csv("data/market/prices.csv", parse_dates=["date"])
px = px.pivot_table(index="date", columns="symbol", values="close")
fx = pd.read_csv("data/market/boi_usdils.csv", parse_dates=["date"]).set_index("date").value
qe = lambda s: s.dropna().resample("QE").last()  # noqa: E731
mk = pd.DataFrame({"S&P 500 (%)": qe(px["^GSPC"]).pct_change() * 100,
                   "S&P 500 בשקלים (%)": (qe(px["^GSPC"]) * qe(fx)).pct_change() * 100,
                   "ת\"א-125 (%)": qe(px["^TA125.TA"]).pct_change() * 100,
                   "ת\"א-35 (%)": qe(px["TA35.TA"]).pct_change() * 100,
                   "דולר/שקל (%)": qe(fx).pct_change() * 100})
mk["הפרש S&P פחות ת\"א-125 (נק' אחוז)"] = mk["S&P 500 (%)"] - mk["ת\"א-125 (%)"]
mk["הפרש S&P בשקלים פחות ת\"א-125 (נק' אחוז)"] = mk["S&P 500 בשקלים (%)"] - mk["ת\"א-125 (%)"]
mk.index = mk.index.to_period("Q")
fx_avg = fx.resample("QE").mean()
fx_avg.index = fx_avg.index.to_period("Q")

# --- החזקות מט"ח רשמיות (data.gov), סוף רבעון
g = pd.read_csv("data/datagov/monthly.csv.gz", low_memory=False, usecols=["REPORT_PERIOD", "FOREIGN_CURRENCY_EXPOSURE", "TOTAL_ASSETS"])
g["m"] = pd.PeriodIndex(g.REPORT_PERIOD.astype(str), freq="M")
gm = g.groupby("m")[["FOREIGN_CURRENCY_EXPOSURE", "TOTAL_ASSETS"]].sum() / 1e3
gm = gm[gm.index.month % 3 == 0]
gm.index = gm.index.asfreq("Q")
hold = pd.DataFrame({"חשיפת מט\"ח רשמית, סוף רבעון": gm.FOREIGN_CURRENCY_EXPOSURE,
                     "שינוי בהחזקות מט\"ח": gm.FOREIGN_CURRENCY_EXPOSURE.diff()})

# --- מסלולים: קנייה/מכירה לפי סיבה (e9)
e9 = pd.read_csv("data/results/fx_flow_breakdown.csv", index_col=0)
e9.index = pd.PeriodIndex(e9.index, freq="Q") + 1
tr = pd.DataFrame({
    "מסלולים: סילוקי החלפים/עתידיים (תוצאת המדד)": e9["נגזרי מניות – סילוקים"],
    "מסלולים: בטחונות / margin call": e9["בטחונות במט\"ח"],
    "מסלולים: גידור – פורוורדים": e9["פורוורדים"],
    "מסלולים: קנייה/מכירה של ני\"ע בחו\"ל": e9["ני\"ע במט\"ח"],
    "מסלולים: מזומן ופיקדונות במט\"ח": e9["מזומן/פיקדונות במט\"ח (ללא בטחונות)"],
    "מסלולים: הלוואות/קרנות פרטיות/אחר": e9["הלוואות/קרנות פרטיות/אחר"],
})
tr["מסלולים: סה\"כ"] = tr.sum(axis=1)

# --- קרנות מחקות (b7), חודשי -> רבעוני
fm = pd.read_csv("data/funds/forwards_monthly.csv.gz", usecols=["report_month", "buy_mkt_bn", "buy_flows_bn", "buy_total_bn"])
fm["q"] = pd.PeriodIndex(fm.report_month.astype(str), freq="M").asfreq("Q")
months = fm.groupby("q").report_month.nunique()
fq = fm.groupby("q")[["buy_mkt_bn", "buy_flows_bn", "buy_total_bn"]].sum()
fq.columns = ["קרנות מחקות: בגלל תנועת המדד", "קרנות מחקות: בגלל הנפקות/פדיונות", "קרנות מחקות: סה\"כ"]
fq["קרנות מחקות: חודשים בנתון"] = months

t = mk.join(hold, how="left").join(tr, how="left").join(fq, how="left")
t["סה\"כ מסלולים + קרנות מחקות"] = t["מסלולים: סה\"כ"] + t["קרנות מחקות: סה\"כ"].fillna(0)
t["בנק ישראל: מוסדיים נטו (מיליארד ש\"ח)"] = bw["IL_INST"] * fx_avg / 1e3
# כל המגזרים בסדרת בנק ישראל (ריק אצל "בנק ישראל עצמו" = לא פורסם/לא התערב ברבעון)
# (עסקאות מט"ח נטו מול הבנקים, + = קניית מט"ח), מיליארדי ש"ח בשער ממוצע ברבעון
SECT = {"IL_BOI": "בנק ישראל עצמו", "IL_INST": "מוסדיים", "IL_HH": "משקי בית", "IL_FI": "גופים פיננסיים אחרים בארץ",
        "IL_LB": "בנקים מקומיים", "IL_REAL": "מגזר עסקי (יצואנים/יבואנים)", "NR_FI": "תושבי חוץ – פיננסיים",
        "NR_NFI": "תושבי חוץ – לא פיננסיים", "NR_OTHR": "תושבי חוץ – אחר"}
for k, lab in SECT.items():
    if k == "IL_INST":
        continue   # כבר בעמודה "בנק ישראל: מוסדיים נטו"
    t["בנק ישראל: " + lab] = bw[k] * fx_avg / 1e3
t["בנק ישראל: סה\"כ מגזרים"] = (bw[list(SECT)].sum(axis=1, min_count=1) * fx_avg / 1e3)
t = t.loc["2024Q2":"2026Q3"]
t.index = t.index.astype(str)
t.round(2).to_csv("data/results/quarterly_table.csv")
pd.set_option("display.width", 300, "display.max_columns", 40)
print(t.round(1).T.to_string())
ok = t.dropna(subset=["מסלולים: סה\"כ", "בנק ישראל: מוסדיים נטו (מיליארד ש\"ח)"])
print(f"\nמתאם מסלולים (מהדוחות) מול בנק ישראל: {ok['מסלולים: סה\"כ'].corr(ok['בנק ישראל: מוסדיים נטו (מיליארד ש\"ח)']):.2f}, n={len(ok)}")

# --- קובץ אקסל אחד מסודר: רבעון בשורה, עמודות מקובצות לפי נושא, + גיליון מקורות
from openpyxl import Workbook  # noqa: E402
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side  # noqa: E402
from openpyxl.utils import get_column_letter  # noqa: E402

GROUPS = [
    ("תנועת השוק (%)", [("S&P 500 (%)", "S&P 500"), ("S&P 500 בשקלים (%)", "S&P 500 בשקלים"), ("ת\"א-125 (%)", "ת\"א-125"),
                        ("ת\"א-35 (%)", "ת\"א-35"), ("דולר/שקל (%)", "דולר/שקל"),
                        ("הפרש S&P פחות ת\"א-125 (נק' אחוז)", "הפרש S&P פחות ת\"א-125"),
                        ("הפרש S&P בשקלים פחות ת\"א-125 (נק' אחוז)", "הפרש S&P בשקלים פחות ת\"א-125")]),
    ("החזקות מט\"ח – מסלולים (מיליארד ש\"ח)", [("חשיפת מט\"ח רשמית, סוף רבעון", "חשיפה, סוף רבעון"), ("שינוי בהחזקות מט\"ח", "שינוי ברבעון")]),
    ("מסלולים: קנייה(+)/מכירה(−) של מט\"ח לפי סיבה (מיליארד ש\"ח)",
     [(c, c.replace("מסלולים: ", "")) for c in t.columns if c.startswith("מסלולים:")]),
    ("קרנות מחקות על חו\"ל: קנייה(+)/מכירה(−) בחוזי אקדמה (מיליארד ש\"ח)",
     [(c, c.replace("קרנות מחקות: ", "")) for c in t.columns if c.startswith("קרנות מחקות:")]),
    ("סה\"כ", [("סה\"כ מסלולים + קרנות מחקות", "מסלולים + קרנות מחקות")]),
    ("בנק ישראל: עסקאות מט\"ח נטו לפי מגזר (מיליארד ש\"ח)",
     [("בנק ישראל: מוסדיים נטו (מיליארד ש\"ח)", "מוסדיים")] +
     [(c, c.replace("בנק ישראל: ", "")) for c in t.columns if c.startswith("בנק ישראל: ") and "מוסדיים" not in c]),
]
wb = Workbook()
ws = wb.active
ws.title = "טבלה רבעונית"
ws.sheet_view.rightToLeft = True
hdr = Font(bold=True, color="FFFFFF")
fills = ["1F4E78", "375623", "7F6000", "833C0B", "404040", "203864"]
thin = Side(style="thin", color="BFBFBF")
ws.cell(1, 1, "רבעון").font = Font(bold=True)
ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=1)
col = 2
for gi, (gname, cols) in enumerate(GROUPS):
    ws.cell(1, col, gname)
    ws.merge_cells(start_row=1, start_column=col, end_row=1, end_column=col + len(cols) - 1)
    for k, (src, lab) in enumerate(cols):
        for r in (1, 2):
            c = ws.cell(r, col + k)
            c.fill = PatternFill("solid", fgColor=fills[gi])
            c.font = hdr
            c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            c.border = Border(left=thin, right=thin, top=thin, bottom=thin)
        ws.cell(2, col + k, lab)
        for i, (q, row) in enumerate(t.iterrows()):
            v = row[src]
            cell = ws.cell(3 + i, col + k, None if pd.isna(v) else round(float(v), 2))
            cell.number_format = "0" if "חודשים" in lab else "+0.0;-0.0;0.0"
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
    col += len(cols)
for i, q in enumerate(t.index):
    ws.cell(3 + i, 1, q).font = Font(bold=True)
ws.row_dimensions[1].height = 42
ws.row_dimensions[2].height = 58
ws.column_dimensions["A"].width = 10
for c in range(2, col):
    ws.column_dimensions[get_column_letter(c)].width = 13
ws.freeze_panes = "B3"
notes = wb.create_sheet("מקורות והערות")
notes.sheet_view.rightToLeft = True
for i, line in enumerate([
    "כל הסכומים במיליארדי ש\"ח; + = קניית מט\"ח נטו, − = מכירה. הרבעון = הרבעון שבו התרחשה התנועה. תא ריק = אין נתון.",
    "הפרש S&P פחות ת\"א-125: בנקודות אחוז (תשואת S&P פחות תשואת ת\"א-125 באותו רבעון); בגרסה בשקלים – S&P כולל שינוי שער הדולר.",
    "מדדים: סוף רבעון מול סוף רבעון (Yahoo Finance). דולר/שקל: שער יציג, בנק ישראל.",
    "החזקות מט\"ח: חשיפת מט\"ח רשמית של כל מסלולי הגמל, הפנסיה והביטוח (data.gov, FOREIGN_CURRENCY_EXPOSURE).",
    "מסלולים לפי סיבה: מדוחות רשימת הנכסים הרבעוניים (ברמת הנכס הבודד), לפי מכשיר; שערוך מנוטרל.",
    "סילוקי החלפים/עתידיים: רווח/הפסד שהתקבל/שולם בדולר ועבר לסעיפי מזומן/ני\"ע/בטחונות – העברה בין סעיפים, לא עסקה בשוק המט\"ח. העסקה בשוק = הסה\"כ.",
    "קרנות מחקות: חוזי אקדמה בפועל מהדוח החודשי המלא לרשות ני\"ע (קוד 38), כל הקרנות המחקות על מניות בחו\"ל; עמודת 'חודשים בנתון' מציינת רבעון חלקי.",
    "בנק ישראל: סדרות WEB_TV_EX_*_Q (עסקאות מט\"ח נטו לפי מגזר, מיליוני דולר), מומר לש\"ח בשער ממוצע ברבעון. סך כל המגזרים ≈ 0 (שוק סגור).",
    "המדידה מהדוחות (מסלולים) מול נתון בנק ישראל למוסדיים: מתאם 0.85; הפער ברמה (בנק ישראל שלילי יותר) עדיין לא מוסבר.",
]):
    notes.cell(1 + i, 1, line)
notes.column_dimensions["A"].width = 160
wb.save("data/results/quarterly_table.xlsx")
print("[e10] data/results/quarterly_table.xlsx")
