"""שלב א – תמונות למצגת (deck/stageA_*.png).  סגנון אחיד: 16:9, עברית מימין לשמאל, כותרת = הממצא."""
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False
C = {"שקלי": "#9AA9B8", "מט\"חי לא מגודר": "#E4572E", "מט\"חי מגודר": "#17A398", "מט\"חי גידור חלקי": "#F2B134",
     "משולב 1": "#C9BFE3", "משולב 2": "#9A86CC", "משולב 3": "#6A4FA8"}
INK, MUTED = "#1F2933", "#6B7785"
H = lambda s: str(s)  # matplotlib (raqm) מסדר עברית מימין לשמאל בעצמו; get_display הפך הכול פעמיים
FIG = (13.33, 7.5)


def frame(title, sub=None, src="מקור: data.gov.il (דוח 8.2026), דוחות הגופים המוסדיים; חישוב: INDEX-FX"):
    fig = plt.figure(figsize=FIG, dpi=150)
    fig.patch.set_facecolor("white")
    fig.text(0.97, 0.93, H(title), ha="right", va="top", fontsize=25, fontweight="bold", color=INK)
    if sub:
        fig.text(0.97, 0.855, H(sub), ha="right", va="top", fontsize=14, color=MUTED)
    fig.text(0.97, 0.025, H(src), ha="right", va="bottom", fontsize=9.5, color=MUTED)
    return fig


def legend_rows(fig, rows, x0=0.97, y0=0.70, dy=0.085):
    """שורת מקרא: ריבוע צבע + תווית + ערכים (מיושר לימין)."""
    for i, (col, lab, val) in enumerate(rows):
        y = y0 - i * dy
        fig.patches.append(plt.Rectangle((x0 - 0.016, y - 0.006), 0.016, 0.03, transform=fig.transFigure, color=col))
        fig.text(x0 - 0.024, y + 0.026, H(lab), ha="right", va="top", fontsize=14, color=INK, fontweight="bold")
        fig.text(x0 - 0.024, y - 0.002, H(val), ha="right", va="top", fontsize=12, color=MUTED)


def brand(s):
    for k, v in (("מנורה", "מנורה מבטחים"), ("מגדל", "מגדל"), ("הראל", "הראל"), ("כלל", "כלל"), ("הפניקס", "הפניקס"), ("מיטב", "מיטב"), ("מור", "מור"),
                 ("אלטשולר", "אלטשולר שחם"), ("אנליסט", "אנליסט"), ("איילון", "איילון"), ("הכשרה", "הכשרה"), ("אינפיניטי", "אינפיניטי"), ("ילין", "ילין לפידות")):
        if k in s:
            return v
    return "אחרות"


t = pd.read_csv("data/classification/tracks_classified.csv")
f = pd.read_csv("data/classification/funds_classified.csv")
TA = t.A.sum()


def tkey(r):
    if r["class"] == "שקלי":
        return "שקלי"
    if r["class"] == "מט\"חי":
        return {"לא מגודר": "מט\"חי לא מגודר", "מגודר": "מט\"חי מגודר", "גידור חלקי": "מט\"חי גידור חלקי"}[r.subclass]
    return {"חו\"ל עד 40%": "משולב 1", "חו\"ל 40%–60%": "משולב 2", "חו\"ל 60%–80%": "משולב 3"}[r.subclass]


t["key"] = t.apply(tkey, axis=1)
LABT = {"שקלי": "מסלולים שקליים", "מט\"חי לא מגודר": "מט\"חיים – לא מגודרים", "מט\"חי מגודר": "מט\"חיים – מגודרים", "מט\"חי גידור חלקי": "מט\"חיים – גידור חלקי",
        "משולב 1": "משולבים – חו\"ל עד 40%", "משולב 2": "משולבים – חו\"ל 40%–60%", "משולב 3": "משולבים – חו\"ל 60%–80%"}
ORD = ["שקלי", "משולב 1", "משולב 2", "משולב 3", "מט\"חי לא מגודר", "מט\"חי מגודר", "מט\"חי גידור חלקי"]
g = t.groupby("key").agg(n=("A", "size"), A=("A", "sum"))
mixA = g.loc[["משולב 1", "משולב 2", "משולב 3"], "A"].sum()
fxA = g.loc[["מט\"חי לא מגודר", "מט\"חי מגודר", "מט\"חי גידור חלקי"], "A"].sum()

# ---- 1. דונאט מסלולים ----
fig = frame(f"{mixA/TA:.0%} מנכסי המסלולים משולבים; רק {fxA/TA:.1%} מט\"חיים טהורים",
            f"{TA:,.0f} מיליארד ש\"ח, {len(t):,} מסלולי גמל, פנסיה וביטוח – לפי סוג המסלול")
ax = fig.add_axes([0.10, 0.08, 0.46, 0.72])
vals = [g.loc[k, "A"] for k in ORD]
ax.pie(vals, colors=[C[k] for k in ORD], startangle=90, counterclock=False, wedgeprops=dict(width=0.38, edgecolor="white", linewidth=2))
ax.text(0, 0.08, f"{TA:,.0f}", ha="center", va="center", fontsize=34, fontweight="bold", color=INK)
ax.text(0, -0.14, H("מיליארד ש\"ח"), ha="center", va="center", fontsize=14, color=MUTED)
legend_rows(fig, [(C[k], LABT[k], f"{g.loc[k,'A']:,.0f} מיליארד ({g.loc[k,'A']/TA:.1%}) · {int(g.loc[k,'n'])} מסלולים") for k in ORD], y0=0.78, dy=0.095)
fig.savefig("deck/stageA_tracks_donut.png"); plt.close(fig)

# ---- 2. פיזור: חשיפה לחו"ל מול חשיפת מט"ח ----
fig = frame("המסלולים יוצרים אשכולות ברורים: שקלי, משולב, ומט\"חי", "כל עיגול = מסלול; גודל העיגול = נכסי המסלול")
ax = fig.add_axes([0.08, 0.12, 0.88, 0.68])
for k in ORD[::-1]:
    d = t[t.key == k]
    ax.scatter(d.fe * 100, d.fx * 100, s=np.sqrt(d.A) * 38, c=C[k], alpha=0.62, edgecolor="white", linewidth=0.5, label=H(LABT[k]), zorder=3)
ax.set_xlim(-3, 135); ax.set_ylim(-4, 112)
ax.set_xlabel(H("חשיפה לחו\"ל (% מהנכסים)"), fontsize=13, color=MUTED); ax.set_ylabel(H("חשיפת מט\"ח (% מהנכסים)"), fontsize=13, color=MUTED)
ax.grid(color="#E6EAEE", zorder=0); [ax.spines[s].set_visible(False) for s in ("top", "right")]
ax.tick_params(colors=MUTED)
ax.annotate(H("עוקבי S&P ומדדי מניות\nלא מגודרים"), (100, 99), (82, 82), fontsize=13, color=C["מט\"חי לא מגודר"], fontweight="bold", ha="right", arrowprops=dict(arrowstyle="-", color=C["מט\"חי לא מגודר"]))
ax.annotate(H("מט\"חיים מגודרים"), (97, 6), (93, 17), fontsize=13, color=C["מט\"חי מגודר"], fontweight="bold", ha="right", arrowprops=dict(arrowstyle="-", color=C["מט\"חי מגודר"]))
ax.annotate(H("מסלולים כלליים ותלויי גיל"), (48, 20), (46, 46), fontsize=13, color=C["משולב 3"], fontweight="bold", ha="right", arrowprops=dict(arrowstyle="-", color=C["משולב 3"]))
ax.annotate(H("שקליים"), (3, 2), (22, 5), fontsize=13, color="#5D6C7B", fontweight="bold", arrowprops=dict(arrowstyle="-", color="#5D6C7B"))
fig.text(0.97, 0.075, H("חשיפה מעל 100% = מינוף דרך נגזרים"), ha="right", fontsize=10.5, color=MUTED)
fig.savefig("deck/stageA_tracks_scatter.png"); plt.close(fig)

# ---- 3. לפי חברה ----
t["brand"] = t.company.map(brand)
top = t.groupby("brand").A.sum().sort_values(ascending=False)
top = top.drop("אחרות", errors="ignore").head(10).index.tolist()
fig = frame("בכל החברות הגדולות רוב הכסף במסלולים משולבים", "נכסים לפי חברה וסוג מסלול (מיליארדי ש\"ח)")
ax = fig.add_axes([0.10, 0.10, 0.82, 0.72])
left = np.zeros(len(top))
y = np.arange(len(top))[::-1]
for k in ORD:
    v = np.array([t[(t.brand == b) & (t.key == k)].A.sum() for b in top])
    ax.barh(y, v, left=left, color=C[k], label=H(LABT[k]), edgecolor="white", height=0.66)
    left += v
for yi, b, tot in zip(y, top, left):
    ax.text(tot + 5, yi, f"{tot:,.0f}", va="center", fontsize=11, color=MUTED)
ax.set_yticks(y); ax.set_yticklabels([H(b) for b in top], fontsize=13, color=INK)
ax.legend(loc="lower right", fontsize=10.5, frameon=False, ncol=2)
[ax.spines[s].set_visible(False) for s in ("top", "right", "left")]; ax.tick_params(colors=MUTED, length=0); ax.grid(axis="x", color="#E6EAEE"); ax.set_axisbelow(True)
fig.savefig("deck/stageA_tracks_by_company.png"); plt.close(fig)

# ---- 4. קרנות ----
f["key"] = np.where(f["class"] == "שקלית", "שקלי", np.where(f["class"] == "משולבת", "משולב 2",
                   np.where(f.hedge == "לא מגודרת", "מט\"חי לא מגודר", np.where(f.hedge == "מגודרת", "מט\"חי מגודר", "מט\"חי גידור חלקי"))))
LABF = {"שקלי": "קרנות שקליות", "משולב 2": "קרנות משולבות (גמישות, אגד, מינוף ועוד)", "מט\"חי לא מגודר": "קרנות מט\"חיות – לא מגודרות",
        "מט\"חי מגודר": "קרנות מט\"חיות – מגודרות", "מט\"חי גידור חלקי": "קרנות מט\"חיות – גידור חלקי"}
ORDF = ["שקלי", "משולב 2", "מט\"חי לא מגודר", "מט\"חי מגודר", "מט\"חי גידור חלקי"]
gf = f.groupby("key").agg(n=("A", "size"), A=("A", "sum"))
FA = f.A.sum()
fxF = gf.loc[["מט\"חי לא מגודר", "מט\"חי מגודר", "מט\"חי גידור חלקי"], "A"].sum()
fig = frame(f"{fxF/FA:.0%} מנכסי הקרנות הן מט\"חיות – פי {fxF/FA/(fxA/TA):.1f} מהמסלולים",
            f"{FA:,.0f} מיליארד ש\"ח, {len(f):,} קרנות נאמנות וקרנות סל – לפי סוג הקרן", src="מקור: דוחות חודשיים לרשות ניירות ערך (מאיה), 8.2026; חישוב: INDEX-FX")
ax = fig.add_axes([0.10, 0.08, 0.46, 0.72])
ax.pie([gf.loc[k, "A"] for k in ORDF], colors=[C[k] for k in ORDF], startangle=90, counterclock=False, wedgeprops=dict(width=0.38, edgecolor="white", linewidth=2))
ax.text(0, 0.08, f"{FA:,.0f}", ha="center", va="center", fontsize=34, fontweight="bold", color=INK)
ax.text(0, -0.14, H("מיליארד ש\"ח"), ha="center", va="center", fontsize=14, color=MUTED)
legend_rows(fig, [(C[k], LABF[k], f"{gf.loc[k,'A']:,.0f} מיליארד ({gf.loc[k,'A']/FA:.1%}) · {int(gf.loc[k,'n']):,} קרנות") for k in ORDF], y0=0.78, dy=0.10)
fig.savefig("deck/stageA_funds_donut.png"); plt.close(fig)

# ---- 5. קרנות מט"חיות: לפי סוג נכס ולפי מבנה ----
ff = f[f["class"] == "מט\"חית"].copy()
fig = frame("מי הקרנות המט\"חיות: מניות בחו\"ל, בעיקר לא מגודרות וקרני סל", "שווי קרנות מט\"חיות (מיליארדי ש\"ח) – לפי סוג נכס ולפי מבנה הקרן; צבע = רמת גידור",
            src="מקור: דוחות חודשיים לרשות ניירות ערך (מאיה), 8.2026; חישוב: INDEX-FX")
HK = [("לא מגודרת", "מט\"חי לא מגודר", "לא מגודרות"), ("מגודרת", "מט\"חי מגודר", "מגודרות"), ("גידור חלקי", "מט\"חי גידור חלקי", "גידור חלקי")]
for pos, col, cats, ttl in ((0.66, "asset_type", ["מניות בחו\"ל", "כספית מט\"חית", "אג\"ח בחו\"ל", "סחורות"], "לפי סוג נכס"), (0.20, "structure", ["קרן סל", "קרן מחקה", "אקטיבית"], "לפי מבנה")):
    ax = fig.add_axes([pos, 0.12, 0.28, 0.62])
    left = np.zeros(len(cats)); y = np.arange(len(cats))[::-1]
    for hk, ck, lab in HK:
        v = np.array([ff[(ff[col] == c) & (ff.hedge == hk)].A.sum() for c in cats])
        ax.barh(y, v, left=left, color=C[ck], edgecolor="white", height=0.62, label=H(lab))
        left += v
    for yi, tot in zip(y, left):
        ax.text(tot + 1.5, yi, f"{tot:,.0f}", va="center", fontsize=12, color=MUTED)
    ax.set_yticks(y); ax.set_yticklabels([H(c) for c in cats], fontsize=13, color=INK); ax.set_title(H(ttl), fontsize=15, color=INK, loc="right", fontweight="bold")
    [ax.spines[s].set_visible(False) for s in ("top", "right", "left")]; ax.tick_params(colors=MUTED, length=0); ax.grid(axis="x", color="#E6EAEE"); ax.set_axisbelow(True)
    ax.set_xlim(0, left.max() * 1.15)
    if pos == 0.20:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.08), fontsize=12, frameon=False, ncol=3)
fig.savefig("deck/stageA_funds_foreign_breakdown.png"); plt.close(fig)

# ---- 6. סיכום: מסלולים מול קרנות ----
fig = frame("סיכום שלב א: הכסף המט\"חי הטהור מרוכז בקרנות, והמסלולים משולבים",
            "חלוקת הנכסים לפי סוג – מסלולים מול קרנות (100% = כל הנכסים בקבוצה)")
ax = fig.add_axes([0.10, 0.22, 0.84, 0.50])
rows = [("קרנות", [(k, gf.loc[k, "A"] / FA) for k in ORDF], FA), ("מסלולים", [(k, g.loc[k, "A"] / TA) for k in ORD], TA)]
for yi, (lab, parts, tot) in enumerate(rows):
    x = 0
    for k, w in parts:
        ax.barh(yi, w * 100, left=x, color=C[k], edgecolor="white", height=0.55)
        if w > 0.045:
            ax.text(x + w * 50, yi, f"{w:.0%}", ha="center", va="center", color="white" if k not in ("שקלי", "משולב 1") else INK, fontsize=15, fontweight="bold")
        x += w * 100
    ax.text(-1.5, yi, H(f"{lab}\n{tot:,.0f} מיליארד"), ha="right", va="center", fontsize=15, color=INK, fontweight="bold")
ax.set_xlim(-30, 100); ax.set_ylim(-0.5, 1.5); ax.axis("off")
used = [("שקלי", "שקליים"), ("משולב 2", "משולבים"), ("מט\"חי לא מגודר", "מט\"חיים לא מגודרים"), ("מט\"חי מגודר", "מט\"חיים מגודרים"), ("מט\"חי גידור חלקי", "מט\"חיים גידור חלקי")]
x0 = 0.95
for k, lab in used:
    fig.patches.append(plt.Rectangle((x0 - 0.014, 0.12), 0.014, 0.025, transform=fig.transFigure, color=C[k]))
    fig.text(x0 - 0.02, 0.145, H(lab), ha="right", va="top", fontsize=12.5, color=INK)
    x0 -= 0.02 + 0.115 + (0.03 if len(lab) > 12 else 0)
fig.text(0.95, 0.80, H(f"מט\"חיים (כל שלוש רמות הגידור):  מסלולים {fxA/TA:.1%} ({fxA:,.0f} מיליארד)   |   קרנות {fxF/FA:.1%} ({fxF:,.0f} מיליארד)"), ha="right", fontsize=15, color=INK, fontweight="bold")
fig.savefig("deck/stageA_summary.png"); plt.close(fig)
print("ok", g.round(1).to_dict("index"))
