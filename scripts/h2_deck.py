"""מצגת לקהל רחב (שלב א): deck/gidur/NN.png (16:9) + deck/gidur/gidur.pdf.  מעט טקסט, גרף אחד בכל שקף."""
import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
from PIL import Image

plt.rcParams["font.family"] = "DejaVu Sans"
plt.rcParams["axes.unicode_minus"] = False
OUT = Path("deck/gidur"); OUT.mkdir(parents=True, exist_ok=True)
C = {"שקלי": "#9AA9B8", "מט\"חי לא מגודר": "#E4572E", "מט\"חי מגודר": "#17A398", "מט\"חי גידור חלקי": "#F2B134", "משולב": "#8F7BC9"}
NAVY, GOLD, INK, MUTED = "#0D1B2A", "#C8A96E", "#1F2933", "#5F6B78"
FIG = (13.33, 7.5)
N = 12
SRC = "מקור: data.gov.il (8.2026), דוחות חודשיים לרשות ניירות ערך · חישוב: INDEX-FX"


def slide(n, title, sub=None, src=SRC):
    fig = plt.figure(figsize=FIG, dpi=150)
    fig.patch.set_facecolor("white")
    fig.text(0.96, 0.92, title, ha="right", va="top", fontsize=31, fontweight="bold", color=INK)
    if sub:
        fig.text(0.96, 0.815, sub, ha="right", va="top", fontsize=17, color=MUTED)
    fig.text(0.96, 0.03, src, ha="right", va="bottom", fontsize=10, color=MUTED)
    fig.text(0.04, 0.03, f"{n} / {N}", ha="left", va="bottom", fontsize=11, color=MUTED)
    fig.patches.append(Rectangle((0.96 - 0.06, 0.965), 0.06, 0.012, transform=fig.transFigure, color=GOLD))
    return fig


def save(fig, n):
    fig.savefig(OUT / f"{n:02d}.png"); plt.close(fig)


t = pd.read_csv("data/classification/tracks_classified.csv")
f = pd.read_csv("data/classification/funds_classified.csv")
TA, FA = t.A.sum(), f.A.sum()
wavg = lambda d, c: float(np.average(d[c], weights=d.A))  # noqa: E731
tk = lambda d: np.where(d["class"] == "שקלי", "שקלי", np.where(d["class"] == "משולב", "משולב", np.where(d.subclass == "לא מגודר", "מט\"חי לא מגודר", np.where(d.subclass == "מגודר", "מט\"חי מגודר", "מט\"חי גידור חלקי"))))  # noqa: E731
t["key"] = tk(t)
f["key"] = np.where(f["class"] == "שקלית", "שקלי", np.where(f["class"] == "משולבת", "משולב", np.where(f.hedge == "לא מגודרת", "מט\"חי לא מגודר", np.where(f.hedge == "מגודרת", "מט\"חי מגודר", "מט\"חי גידור חלקי"))))
gt, gf = t.groupby("key").A.sum(), f.groupby("key").A.sum()
nt, nf = t.groupby("key").size(), f.groupby("key").size()

# ---------- 1. שער ----------
fig = plt.figure(figsize=FIG, dpi=150); fig.patch.set_facecolor(NAVY)
fig.text(0.94, 0.70, "מי קונה ומוכר דולר", ha="right", fontsize=54, fontweight="bold", color=GOLD)
fig.text(0.94, 0.58, "כשהמדד זז?", ha="right", fontsize=54, fontweight="bold", color=GOLD)
fig.text(0.94, 0.45, "האם קרנות הפנסיה, הגמל והנאמנות מזיזות את שער הדולר?", ha="right", fontsize=21, color="#F5F0E8")
fig.text(0.94, 0.36, "חלק א: מי המשקיעים, ואיך כל אחד מהם חשוף לחו\"ל", ha="right", fontsize=19, color="#C9D1DA")
fig.text(0.94, 0.10, "נובמבר 2026 · הון כשר", ha="right", fontsize=14, color="#9AA6B2")
ax = fig.add_axes([0.04, 0.15, 0.30, 0.68]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
for x, lab, col, up in ((0.2, "S&P 500", "#17A398", True), (0.8, "שער הדולר", "#E4572E", False)):
    ax.add_patch(FancyArrowPatch((x, 0.30 if up else 0.78), (x, 0.78 if up else 0.30), arrowstyle="-|>", mutation_scale=60, lw=10, color=col))
    ax.text(x, 0.10, lab, ha="center", fontsize=19, color="#F5F0E8", fontweight="bold")
ax.text(0.5, 0.95, "?", ha="center", va="center", fontsize=64, color=GOLD, fontweight="bold")
fig.savefig(OUT / "01.png"); plt.close(fig)


# ---------- 2. מה חוקרים ----------
fig = slide(2, "מה אנחנו בודקים", "כשהמדד האמריקאי זז, האם הגופים המוסדיים קונים או מוכרים דולרים, ומזיזים את השער?", src="INDEX-FX")
ax = fig.add_axes([0.04, 0.10, 0.92, 0.62]); ax.axis("off"); ax.set_xlim(0, 100); ax.set_ylim(0, 40)
boxes = [("המדד האמריקאי\nעולה או יורד", "#17A398"), ("שווי ההחזקות בחו\"ל\nשל המוסדיים משתנה", "#8F7BC9"), ("הם מאזנים\nאת החשיפה לדולר", "#F2B134"), ("קנייה או מכירה\nשל דולרים", "#E4572E"), ("שער הדולר\nבישראל זז?", NAVY)]
for i, (txt, c) in enumerate(boxes):
    x = 88 - i * 19
    ax.add_patch(FancyBboxPatch((x - 8, 14), 16, 14, boxstyle="round,pad=0.4,rounding_size=2", color=c))
    ax.text(x, 21, txt, ha="center", va="center", fontsize=15, fontweight="bold", color="white", linespacing=1.4)
    if i < 4: ax.annotate("", xy=(x - 10.2, 21), xytext=(x - 8.9, 21), arrowprops=dict(arrowstyle="-|>", lw=3, color=MUTED))
ax.text(50, 5, "כדי לענות צריך לדעת קודם מי המשקיעים ואיך כל אחד מהם חשוף לדולר", ha="center", va="center", fontsize=19, color=INK, fontweight="bold")
save(fig, 2)

# ---------- 3. הגרף המרכזי: כסף לפי סוג ----------
fig = slide(3, "כמה כסף יש בכל סוג", "חו\"ל מלא, שקלי ומשולב – ובתוך כל אחד: מגודר, לא מגודר וגידור חלקי (מיליארדי ש\"ח)")
def _hb(r): return "לא מגודר" if r >= 0.7 else ("מגודר" if r <= 0.3 else "גידור חלקי")
_t = t.assign(h=t.hedge_ratio.map(_hb))
_ccol = {"לא מגודר": C["מט\"חי לא מגודר"], "מגודר": C["מט\"חי מגודר"], "גידור חלקי": C["מט\"חי גידור חלקי"], "ללא פירוק": C["משולב"], "שקלי": C["שקלי"]}
_tk = (_t[_t["class"] == "שקלי"].A.sum(), _t[_t["class"] == "מט\"חי"].groupby("h").A.sum(), _t[_t["class"] == "משולב"].groupby("h").A.sum())
_fk = (f[f["class"] == "שקלית"].A.sum(), f[f["class"] == "מט\"חית"].groupby("hedge").A.sum().rename(index={"לא מגודרת": "לא מגודר", "מגודרת": "מגודר"}), pd.Series({"ללא פירוק": f[f["class"] == "משולבת"].A.sum()}))
for rect, (sv, fxs, mxs), name in (([0.53, 0.20, 0.43, 0.50], _tk, "מסלולים"), ([0.06, 0.20, 0.43, 0.50], _fk, "קרנות")):
    ax = fig.add_axes(rect); top = max(sv, fxs.sum(), mxs.max()); x = 0; ticks = []
    for g, items in (("0% חו\"ל", [("שקלי", sv)]), ("100% חו\"ל", [(k, fxs.get(k, 0)) for k in ["לא מגודר", "מגודר", "גידור חלקי"]]), ("משולב", list(mxs.items()))):
        st = x
        for k, v in items:
            ax.bar(-x, v, 0.9, color=_ccol[k]); ax.text(-x, v + top * 0.015, f"{v:,.0f}", ha="center", fontsize=14, fontweight="bold", color=INK)
            if len(items) > 1: ax.text(-x, -top * 0.03, k.replace("גידור חלקי", "חלקי"), ha="center", va="top", fontsize=10.5, color=INK)
            x += 1
        ticks.append((-(st + x - 1) / 2, g)); x += 1
    ax.set_xticks([a for a, _ in ticks]); ax.set_xticklabels([b for _, b in ticks], fontsize=14, fontweight="bold"); ax.tick_params(axis="x", pad=30, length=0)
    ax.set_title(name, fontsize=20, fontweight="bold", color=INK, pad=12); ax.spines[["top", "right"]].set_visible(False); ax.yaxis.grid(True, color="#EEF1F4"); ax.set_axisbelow(True); ax.set_ylim(0, top * 1.12)
fig.text(0.5, 0.075, "סיווג: חו\"ל מלא = 95% ומעלה (פנסיה מקיפה: 65% ומעלה) · שקלי = עד 5% · בקרנות משולבות אין נתון גידור", ha="center", fontsize=12, color=MUTED)
save(fig, 3)

# ---------- 4. השאלה: S&P מול הדולר ----------
p = pd.read_csv("data/market/long_prices.csv", parse_dates=["Date"]).set_index("Date")["^GSPC"]
fxs = pd.read_csv("data/market/long_usdils.csv", parse_dates=["TIME_PERIOD"]).set_index("TIME_PERIOD").OBS_VALUE
m = pd.DataFrame({"sp": p.loc["2022-01-03":].resample("ME").last(), "fx": fxs.loc["2022-01-03":].resample("ME").last()}).pct_change().dropna() * 100
corr = m.corr().iloc[0, 1]
opp = ((m.sp > 0) & (m.fx < 0)) | ((m.sp < 0) & (m.fx > 0))
fig = slide(4, "כשהמדד האמריקאי עולה, השקל נוטה להתחזק", f"כל נקודה = חודש (1.2022–10.2026). ב־{opp.sum()} מתוך {len(m)} חודשים המדד והדולר זזו בכיוונים הפוכים", src="מקור: Yahoo Finance, בנק ישראל · חישוב: INDEX-FX")
ax = fig.add_axes([0.10, 0.12, 0.84, 0.57])
ax.scatter(m.sp[~opp], m.fx[~opp], s=120, c="#9AA9B8", alpha=.85, edgecolor="white", zorder=3)
ax.scatter(m.sp[opp], m.fx[opp], s=120, c="#17A398", alpha=.85, edgecolor="white", zorder=3)
b = np.polyfit(m.sp, m.fx, 1); xs = np.array([m.sp.min() - 0.5, m.sp.max() + 0.5])
ax.plot(xs, b[0] * xs + b[1], color="#E4572E", lw=3, zorder=2)
ax.axhline(0, color="#C9D1DA", lw=1); ax.axvline(0, color="#C9D1DA", lw=1)
ax.set_xlabel("שינוי חודשי ב־S&P 500 (%)", fontsize=15, color=MUTED); ax.set_ylabel("שינוי חודשי בשער הדולר (%)", fontsize=15, color=MUTED)
ax.tick_params(colors=MUTED, labelsize=12); [ax.spines[s].set_visible(False) for s in ("top", "right")]; ax.grid(color="#EEF1F4", zorder=0)
ax.text(0.97, 0.06, "המדד עולה, הדולר יורד", transform=ax.transAxes, ha="right", fontsize=16, color="#17A398", fontweight="bold")
ax.text(0.03, 0.94, "המדד יורד, הדולר עולה", transform=ax.transAxes, ha="left", va="top", fontsize=16, color="#17A398", fontweight="bold")
ax.text(0.03, 0.06, f"מתאם \u200e{corr:.2f}", transform=ax.transAxes, ha="left", fontsize=22, color="#E4572E", fontweight="bold")
fig.text(0.96, 0.745, "השאלה: האם הגופים המוסדיים הם הסיבה?", ha="right", fontsize=20, color="#E4572E", fontweight="bold")
save(fig, 4)

# ---------- 3. כמה כסף ----------
fig = slide(5, f"בידי המוסדיים כמעט {(TA+FA)/1000:.1f} טריליון ש\"ח", "הגופים שמנהלים את החיסכון של הציבור: מסלולי פנסיה, גמל וביטוח, וקרנות נאמנות. שטח העיגול = סכום הכסף")
ax = fig.add_axes([0.04, 0.10, 0.92, 0.66]); ax.axis("off"); ax.set_aspect("equal"); ax.set_xlim(-10, 10); ax.set_ylim(-4.5, 4.5)
r1, r2 = np.sqrt(TA) / np.sqrt(TA) * 4.0, np.sqrt(FA / TA) * 4.0
ax.add_patch(Circle((4.6, 0), r1, color="#8F7BC9", alpha=.9)); ax.add_patch(Circle((-4.6, -4.0 + r2 + 0.3), r2, color="#17A398", alpha=.9))
# נתח הקרנות בתוך עיגול המסלולים (פוזיציות לפי נייר, דוחות רבעוניים 2026)
from matplotlib.patches import Wedge
_pos = pd.read_csv("data/positions_classified.csv.gz", usecols=["legal_id", "track", "report_date", "il_abroad", "form", "fair_value_k"], low_memory=False)
_tt = pd.read_csv("data/track_totals.csv"); _TT = _tt.total_k.sum()
_pf = _pos[_pos.form.isin(["ETF", "MUTUAL_FUND"])].merge(_tt[["legal_id", "track", "report_date"]], on=["legal_id", "track", "report_date"])
sh_il = _pf[_pf.il_abroad == "ישראל"].fair_value_k.sum() / _TT; sh_ab = _pf[_pf.il_abroad == "חו\"ל"].fair_value_k.sum() / _TT
CX = 4.6; a0 = 90.0; a1 = a0 + sh_il * 360; a2 = a1 + sh_ab * 360
ax.add_patch(Wedge((CX, 0), r1, a0, a1, color="#F2B134", ec="white", lw=2)); ax.add_patch(Wedge((CX, 0), r1, a1, a2, color="#5B4A9E", ec="white", lw=2))
ax.text(CX, -0.75, f"{TA:,.0f}", ha="center", va="center", fontsize=44, color="white", fontweight="bold")
ax.text(CX, -1.55, "מיליארד ש\"ח", ha="center", fontsize=17, color="white")
ax.text(CX, -2.3, f"{len(t):,} מסלולי פנסיה, גמל וביטוח", ha="center", fontsize=15, color="white")
ax.text(-4.6, -4.0 + r2 + 0.65, f"{FA:,.0f}", ha="center", va="center", fontsize=36, color="white", fontweight="bold")
ax.text(-4.6, -4.0 + r2 - 0.15, "מיליארד ש\"ח", ha="center", fontsize=15, color="white")
ax.text(-4.6, -4.0 + r2 - 0.85, f"{len(f):,} קרנות", ha="center", fontsize=14, color="white")
import math
def _pt(ang, rr): return CX + rr * math.cos(math.radians(ang)), rr * math.sin(math.radians(ang))
ax.annotate("", xy=_pt((a0 + a1) / 2, r1 * 0.8), xytext=(-0.9, 3.6), arrowprops=dict(arrowstyle="-", lw=2, color="#F2B134"))
ax.annotate("", xy=_pt((a1 + a2) / 2, r1 * 0.8), xytext=(-0.9, 2.4), arrowprops=dict(arrowstyle="-", lw=2, color="#5B4A9E"))
ax.text(-1.2, 3.6, f"{sh_il:.1%} בקרנות נאמנות וסל ישראליות", ha="right", va="center", fontsize=16, fontweight="bold", color="#C98A00")
ax.text(-1.2, 3.1, f"({sh_il*_TT/1e6:,.0f} מיליארד ש\"ח)", ha="right", va="center", fontsize=13, color=MUTED)
ax.text(-1.2, 2.4, f"{sh_ab:.1%} בקרנות וקרנות סל של חו\"ל", ha="right", va="center", fontsize=16, fontweight="bold", color="#5B4A9E")
ax.text(-1.2, 1.9, f"({sh_ab*_TT/1e6:,.0f} מיליארד ש\"ח)", ha="right", va="center", fontsize=13, color=MUTED)
fig.text(0.96, 0.095, "שיעור מנכסי המסלולים לפי דוחות ההחזקות (2026), לא כולל קרנות השקעה פרטיות. ההחזקות האלה יוצרות חפיפה עם סכום הקרנות", ha="right", fontsize=13, color=MUTED)
save(fig, 5)

# ---------- 4. מה זה חשיפה לדולר ----------
rows = [("מסלול שקלי", "שקלי", wavg(t[t.key == "שקלי"], "fx")), ("מסלול משולב (ארץ וחו\"ל)", "משולב", wavg(t[t.key == "משולב"], "fx")),
        ("מט\"חי מגודר", "מט\"חי מגודר", wavg(t[t.key == "מט\"חי מגודר"], "fx")), ("מט\"חי לא מגודר (כמו עוקב S&P)", "מט\"חי לא מגודר", wavg(t[t.key == "מט\"חי לא מגודר"], "fx"))]
fig = slide(6, "ככל שהמסלול חשוף יותר לדולר, כך שוויו זז יותר כשהדולר זז", "חשיפה לדולר = כמה מהכסף משתנה בשווי כשהשקל והדולר זזים. גידור = הגנה מפני השינוי הזה", src="מקור: data.gov.il (8.2026), ממוצע משוקלל לפי נכסים · חישוב: INDEX-FX")
ax = fig.add_axes([0.20, 0.08, 0.74, 0.62]); ax.set_xlim(0, 100); ax.set_ylim(-0.5, 3.75); ax.axis("off")
for i, (lab, key, v) in enumerate(rows[::-1]):
    y = i * 1.05
    ax.add_patch(Rectangle((0, y - 0.22), 100, 0.44, color="#EEF1F4")); ax.add_patch(Rectangle((100 - v * 100, y - 0.22), v * 100, 0.44, color=C[key]))
    if v > 0.5:
        ax.text(100 - v * 100 + 2, y, f"{v:.0%}", ha="left", va="center", fontsize=20, fontweight="bold", color="white")
    else:
        ax.text(100 - v * 100 - 1.5, y, f"{v:.0%}", ha="right", va="center", fontsize=20, fontweight="bold", color=INK)
    ax.text(100, y + 0.40, lab, ha="right", va="bottom", fontsize=16, color=INK, fontweight="bold")
    ax.text(-2, y, f"+{v*10:.1f}%", ha="right", va="center", fontsize=24, fontweight="bold", color=C[key])
fig.text(0.185, 0.73, "אם הדולר עולה 10%,\nשווי המסלול משתנה ב־", ha="right", va="center", fontsize=14, color=MUTED, linespacing=1.4)
save(fig, 6)

# ---------- 5. מסלולים: דונאט ----------
def donut(fig, vals, keys, labels, total, unit_n, x=0.04):
    ax = fig.add_axes([x, 0.07, 0.46, 0.72])
    ax.pie(vals, colors=[C[k] for k in keys], startangle=90, counterclock=False, wedgeprops=dict(width=0.38, edgecolor="white", linewidth=2))
    ax.text(0, 0.08, f"{total:,.0f}", ha="center", va="center", fontsize=40, fontweight="bold", color=INK); ax.text(0, -0.17, "מיליארד ש\"ח", ha="center", fontsize=16, color=MUTED)
    y = 0.66
    for k, lab, v, n_ in zip(keys, labels, vals, unit_n):
        fig.patches.append(Rectangle((0.945, y), 0.02, 0.038, transform=fig.transFigure, color=C[k]))
        fig.text(0.935, y + 0.045, lab, ha="right", va="top", fontsize=19, fontweight="bold", color=INK)
        fig.text(0.935, y + 0.004, f"{v/total:.1%} · {v:,.0f} מיליארד · {n_:,} {'מסלולים' if total == TA else 'קרנות'}", ha="right", va="top", fontsize=14, color=MUTED)
        y -= 0.115


order = ["שקלי", "משולב", "מט\"חי לא מגודר", "מט\"חי מגודר", "מט\"חי גידור חלקי"]
lab_t = {"שקלי": "שקליים", "משולב": "משולבים (ארץ וחו\"ל)", "מט\"חי לא מגודר": "מט\"חיים לא מגודרים", "מט\"חי מגודר": "מט\"חיים מגודרים", "מט\"חי גידור חלקי": "מט\"חיים בגידור חלקי"}
fxT = gt[[k for k in order if k.startswith("מט")]].sum()
fig = slide(7, f"{gt['משולב']/TA:.0%} מכספי המסלולים הם משולבים: חלק בארץ וחלק בחו\"ל", "פנסיה, גמל, השתלמות וביטוח – חלוקה לפי סוג המסלול")
donut(fig, [gt[k] for k in order], order, [lab_t[k] for k in order], TA, [nt[k] for k in order]); save(fig, 7)

# ---------- 6. מסלולים: פיזור ----------
fig = slide(8, "רוב המסלולים באמצע, ומעטים חשופים לגמרי לחו\"ל", "ציר אופקי: כמה מהכסף מושקע בחו\"ל · ציר אנכי: כמה חשוף לדולר · גודל העיגול = סכום הכסף")
ax = fig.add_axes([0.08, 0.15, 0.88, 0.58])
for k in ["שקלי", "משולב", "מט\"חי גידור חלקי", "מט\"חי מגודר", "מט\"חי לא מגודר"]:
    d = t[t.key == k]; ax.scatter(d.fe * 100, d.fx * 100, s=np.sqrt(d.A) * 40, c=C[k], alpha=.6, edgecolor="white", linewidth=.5, zorder=3)
ax.set_xlim(-3, 135); ax.set_ylim(-4, 112); ax.set_xlabel("חשיפה לחו\"ל (% מהכסף)", fontsize=15, color=MUTED); ax.set_ylabel("חשיפה לדולר (% מהכסף)", fontsize=15, color=MUTED)
ax.grid(color="#EEF1F4", zorder=0); [ax.spines[s].set_visible(False) for s in ("top", "right")]; ax.tick_params(colors=MUTED, labelsize=12)
for txt, xy, xyt, col in (("עוקבי S&P ומדדי מניות,\nלא מגודרים", (100, 99), (80, 84), C["מט\"חי לא מגודר"]), ("מט\"חיים מגודרים:\nבחו\"ל אבל בלי דולר", (97, 6), (122, 44), C["מט\"חי מגודר"]),
                          ("המסלולים הכלליים\nותלויי הגיל", (48, 20), (40, 48), "#6A4FA8"), ("שקליים", (3, 2), (14, 38), "#5D6C7B")):
    ax.annotate(txt, xy, xyt, fontsize=16, color=col, fontweight="bold", ha="right", arrowprops=dict(arrowstyle="-", color=col, lw=1.6))
save(fig, 8)

# ---------- 7. קרנות: דונאט ----------
orderf = ["שקלי", "משולב", "מט\"חי לא מגודר", "מט\"חי מגודר", "מט\"חי גידור חלקי"]
lab_f = {"שקלי": "קרנות שקליות", "משולב": "קרנות משולבות", "מט\"חי לא מגודר": "קרנות מט\"חיות לא מגודרות", "מט\"חי מגודר": "קרנות מט\"חיות מגודרות", "מט\"חי גידור חלקי": "קרנות מט\"חיות בגידור חלקי"}
fxF = gf[[k for k in orderf if k.startswith("מט")]].sum()
fig = slide(9, f"בקרנות המצב שונה: {fxF/FA:.0%} מהכסף מט\"חי", "קרנות נאמנות וקרנות סל – חלוקה לפי סוג הקרן", src="מקור: דוחות חודשיים לרשות ניירות ערך (מאיה), 8.2026 · חישוב: INDEX-FX")
donut(fig, [gf[k] for k in orderf], orderf, [lab_f[k] for k in orderf], FA, [nf[k] for k in orderf]); save(fig, 9)

# ---------- 8. קרנות מט"חיות: פירוק ----------
ff = f[f["class"] == "מט\"חית"]
fig = slide(10, "הקרנות המט\"חיות: בעיקר מניות בחו\"ל, ורוב הכסף לא מגודר", "שווי הקרנות המט\"חיות (מיליארדי ש\"ח), לפי סוג הנכס ולפי מבנה הקרן", src="מקור: דוחות חודשיים לרשות ניירות ערך (מאיה), 8.2026 · חישוב: INDEX-FX")
HK = [("לא מגודרת", "מט\"חי לא מגודר", "לא מגודרת"), ("מגודרת", "מט\"חי מגודר", "מגודרת"), ("גידור חלקי", "מט\"חי גידור חלקי", "גידור חלקי")]
for pos, col, cats, ttl in ((0.60, "asset_type", ["מניות בחו\"ל", "כספית מט\"חית", "אג\"ח בחו\"ל"], "לפי סוג נכס"), (0.14, "structure", ["קרן סל", "קרן מחקה", "אקטיבית"], "לפי מבנה הקרן")):
    ax = fig.add_axes([pos, 0.14, 0.30, 0.56]); left = np.zeros(len(cats)); y = np.arange(len(cats))[::-1]
    for hk, ck, lab in HK:
        v = np.array([ff[(ff[col] == c) & (ff.hedge == hk)].A.sum() for c in cats]); ax.barh(y, v, left=left, color=C[ck], edgecolor="white", height=0.62, label=lab); left += v
    for yi, tot in zip(y, left):
        ax.text(tot + 1.5, yi, f"{tot:,.0f}", va="center", fontsize=16, color=INK, fontweight="bold")
    ax.set_yticks(y); ax.set_yticklabels(cats, fontsize=16, color=INK); ax.set_title(ttl, fontsize=18, color=INK, loc="right", fontweight="bold", pad=14)
    [ax.spines[s].set_visible(False) for s in ("top", "right", "left")]; ax.tick_params(colors=MUTED, length=0); ax.set_xticks([]); ax.set_xlim(0, left.max() * 1.18)
    if col == "structure":
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.06), fontsize=15, frameon=False, ncol=3)
save(fig, 10)

# ---------- 9. סיכום ----------
fig = slide(11, "הכסף שחשוף לדולר מרוכז בקרנות; המסלולים משולבים", "חלוקת הכסף לפי סוג (100% = כל הכסף בקבוצה)")
ax = fig.add_axes([0.14, 0.20, 0.80, 0.46]); ax.axis("off"); ax.set_xlim(-26, 100); ax.set_ylim(-0.6, 1.6)
for yi, (lab, g, tot) in enumerate((("קרנות", gf, FA), ("מסלולים", gt, TA))):
    x = 0
    for k in orderf:
        w = g.get(k, 0) / tot * 100; ax.barh(yi, w, left=x, color=C[k], edgecolor="white", height=0.55)
        if w > 6: ax.text(x + w / 2, yi, f"{w:.0f}%", ha="center", va="center", fontsize=22, fontweight="bold", color="white" if k != "שקלי" else INK)
        x += w
    ax.text(-1.5, yi, f"{lab}\n{tot:,.0f} מיליארד", ha="right", va="center", fontsize=18, fontweight="bold", color=INK)
for i, k in enumerate(orderf):
    x0 = 0.94 - i * 0.185
    fig.patches.append(Rectangle((x0 - 0.016, 0.115), 0.016, 0.03, transform=fig.transFigure, color=C[k])); fig.text(x0 - 0.023, 0.16, {"שקלי": "שקליים", "משולב": "משולבים", "מט\"חי לא מגודר": "מט\"חיים\nלא מגודרים", "מט\"חי מגודר": "מט\"חיים\nמגודרים", "מט\"חי גידור חלקי": "גידור חלקי"}[k], ha="right", va="top", fontsize=14, color=INK)
fig.text(0.96, 0.725, f"חשופים לדולר באופן מלא: מסלולים {fxT/TA:.1%} · קרנות {fxF/FA:.0%}", ha="right", fontsize=20, fontweight="bold", color="#E4572E")
save(fig, 11)

# ---------- 10. מה הלאה ----------
fig = slide(12, "מה הלאה: מי באמת מוכר וקונה דולר כשהמדד עולה", "המחקר בארבעה שלבים. כאן סיימנו את הראשון", src="INDEX-FX")
ax = fig.add_axes([0.04, 0.12, 0.92, 0.60]); ax.axis("off"); ax.set_xlim(0, 100); ax.set_ylim(0, 36.7)
steps = [("א", "מי המשקיעים", "מסלולים וקרנות,\nלפי חשיפה לחו\"ל ולדולר", True), ("ב", "מה בתוך החשיפה", "מניות, אג\"ח, החלפים,\nחוזים וקרנות", False),
         ("ג", "אילו קרנות במסלולים", "מה המסלולים מחזיקים,\nומה יקנו וימכרו", False), ("ד", "מה קורה כשהמדד עולה", "קנייה ומכירה של דולר,\nלכל סוג וסך הכול", False)]
ax.plot([10, 90], [24, 24], color="#C9D1DA", lw=4, zorder=1)
for i, (ch, head, body, done) in enumerate(steps):
    x = 88 - i * 25.3
    ax.add_patch(Circle((x, 24), 4.0, color=GOLD if done else "white", ec=GOLD, lw=4, zorder=3)); ax.text(x, 24, ch, ha="center", va="center", fontsize=34, fontweight="bold", color=NAVY if done else GOLD, zorder=4)
    ax.text(x, 14.5, head, ha="center", va="center", fontsize=19, fontweight="bold", color=INK); ax.text(x, 8, body, ha="center", va="center", fontsize=14.5, color=MUTED, linespacing=1.5)
    if done: ax.text(x, 31, "הושלם", ha="center", fontsize=16, fontweight="bold", color="#17A398")
save(fig, 12)

ims = [Image.open(OUT / f"{i:02d}.png").convert("RGB") for i in range(1, N + 1)]
ims[0].save(OUT / "gidur.pdf", save_all=True, append_images=ims[1:], resolution=150.0)
print("ok", N, os.path.getsize(OUT / "gidur.pdf") // 1000, "KB")
