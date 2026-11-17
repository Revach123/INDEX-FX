"""PDF לשלב א: עמוד פתיחה (הגדרות), 6 התמונות, ועמוד החלטות. פלט: deck/stageA.pdf"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

plt.rcParams["font.family"] = "DejaVu Sans"
H = lambda s: str(s)  # matplotlib (raqm) מסדר עברית מימין לשמאל בעצמו; get_display הפך הכול פעמיים
INK, MUTED = "#1F2933", "#6B7785"


def text_page(path, title, blocks, sub=None):
    fig = plt.figure(figsize=(13.33, 7.5), dpi=150)
    fig.text(0.97, 0.93, H(title), ha="right", va="top", fontsize=26, fontweight="bold", color=INK)
    if sub:
        fig.text(0.97, 0.855, H(sub), ha="right", va="top", fontsize=15, color=MUTED)
    y = 0.77
    for head, lines in blocks:
        fig.text(0.97, y, H(head), ha="right", va="top", fontsize=17, fontweight="bold", color="#E4572E")
        y -= 0.052
        for ln in lines:
            fig.text(0.95, y, H("• " + ln), ha="right", va="top", fontsize=14, color=INK)
            y -= 0.042
        y -= 0.022
    fig.text(0.97, 0.025, H("INDEX-FX · 15.11.2026"), ha="right", va="bottom", fontsize=9.5, color=MUTED)
    fig.savefig(path); plt.close(fig)


text_page("deck/_p0.png", "שלב א: חלוקת המסלולים והקרנות לפי סוג", [
    ("מסלולים – 2,995 מיליארד ש\"ח, 1,240 מסלולי גמל, פנסיה וביטוח (8.2026)", [
        "שקליים: חשיפה לחו\"ל ולמט\"ח מתחת ל-10%",
        "מט\"חיים: חשיפה לחו\"ל 80% ומעלה (עוקבי S&P ומדדי מניות)",
        "משולבים: כל השאר (ארץ וחו\"ל), מחולקים לפי רמת החשיפה לחו\"ל"]),
    ("גידור במסלולים מט\"חיים (חשיפת מט\"ח חלקי חשיפה לחו\"ל)", [
        "לא מגודר: 70% ומעלה   |   מגודר: עד 30%   |   גידור חלקי: בין לבין"]),
    ("קרנות – 846 מיליארד ש\"ח, 2,506 קרנות נאמנות וסל (8.2026)", [
        "מט\"חיות: מניות בחו\"ל, אג\"ח בחו\"ל, סחורות, כספית מט\"חית",
        "שקליות: אג\"ח, מניות וכספית בארץ",
        "משולבות: גמישות, אגד קרנות, מינוף ועוד",
        "גידור לפי חשיפת מט\"ח בפועל: לא מגודרת 80% ומעלה | מגודרת עד 20%"]),
    ("מקורות", ["data.gov.il (חשיפה רשמית של מסלולים), דוחות חודשיים לרשות ניירות ערך (קרנות)"]),
], sub="מצגת: מי קונה ומוכר דולר כשהמדד זז")
text_page("deck/_p7.png", "החלטות לאישור לפני שלב ב'", [
    ("1. רף \"מט\"חי\" במסלולים", [
        "ברירת מחדל 80%: 229 מסלולים, 166 מיליארד",
        "ברף 75%: 245 מסלולים (244 מיליארד)   |   ברף 90%: 216 מסלולים (136 מיליארד)"]),
    ("2. הקבוצה המשולבת (92% מהנכסים)", [
        "כרגע: שלוש רמות לפי חשיפה לחו\"ל (עד 40%, 40%–60%, 60%–80%)",
        "אפשרות: חלוקה לפי סוג מסלול (כללי, מניות, תלוי גיל)"]),
    ("3. כספית מט\"חית (28 מיליארד)", [
        "כרגע: קרן מט\"חית לא מגודרת   |   אפשרות: להעביר למשולבות"]),
    ("השלבים הבאים", [
        "ב: פירוק החשיפה לחו\"ל לפי סוג נכס",
        "ג: מיפוי הקרנות שהמסלולים מחזיקים",
        "ד: השפעת עליית המדד לכל תת-סוג, וסיכום גלובלי"]),
], sub="נדרש אישור לפני שממשיכים")
order = ["deck/_p0.png", "deck/stageA_summary.png", "deck/stageA_tracks_donut.png", "deck/stageA_tracks_scatter.png", "deck/stageA_tracks_by_company.png",
         "deck/stageA_funds_donut.png", "deck/stageA_funds_foreign_breakdown.png", "deck/_p7.png"]
im = [Image.open(p).convert("RGB") for p in order]
im[0].save("deck/stageA.pdf", save_all=True, append_images=im[1:], resolution=150.0)
print("pages", len(im))

import os
for _p in ("deck/_p0.png", "deck/_p7.png"):
    os.remove(_p)
