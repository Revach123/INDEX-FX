import pandas as pd, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
plt.rcParams["font.family"]="DejaVu Sans"
t=pd.read_csv('data/classification/tracks_classified.csv');f=pd.read_csv('data/classification/funds_classified.csv')
def hb(r): return "לא מגודר" if r>=0.7 else ("מגודר" if r<=0.3 else "גידור חלקי")
t["h"]=t.hedge_ratio.map(hb)
col={"לא מגודר":"#E4572E","מגודר":"#17A398","גידור חלקי":"#F2B134","ללא פירוק":"#8F7BC9","שקלי":"#9AA9B8"}
def data(df,kind):
    if kind=="t":
        s=df[df["class"]=="שקלי"].A.sum(); fx=df[df["class"]=='מט"חי'].groupby("h").A.sum(); mx=df[df["class"]=="משולב"].groupby("h").A.sum()
    else:
        s=df[df["class"]=="שקלית"].A.sum(); fx=df[df["class"]=='מט"חית'].groupby("hedge").A.sum().rename(index={"לא מגודרת":"לא מגודר","מגודרת":"מגודר"}); mx=pd.Series({"ללא פירוק":df[df["class"]=="משולבת"].A.sum()})
    return s,fx,mx
fig,axs=plt.subplots(1,2,figsize=(20,9),dpi=100); fig.patch.set_facecolor("white")
for ax,(df,kind,name) in zip(axs[::-1],((t,"t","מסלולים (גמל, פנסיה, ביטוח)"),(f,"f","קרנות (נאמנות וסל)"))):
    s,fx,mx=data(df,kind); bars=[]; x=0; ticks=[]
    # RTL: first group at right -> plot x descending
    groups=[("0% חו\"ל\n(שקלי)",[("שקלי",s)]),("100% חו\"ל\n(מט\"חי)",[(k,fx.get(k,0)) for k in ["לא מגודר","מגודר","גידור חלקי"]]),("משולב\n(ארץ וחו\"ל)",[(k,v) for k,v in mx.items()])]
    for g,items in groups:
        start=x
        for k,v in items:
            ax.bar(-x,v,0.9,color=col[k]); ax.text(-x,v+max(s,fx.sum(),mx.sum())*0.015,f"{v:,.0f}",ha="center",fontsize=16,fontweight="bold",color="#1F2933")
            if g.startswith("100") or g.startswith("משולב") and kind=="t": ax.text(-x,-max(s,fx.sum(),mx.sum())*0.03,k,ha="center",va="top",fontsize=13,color="#1F2933",rotation=0)
            x+=1
        ticks.append((-(start+x-1)/2,g)); x+=1
    ax.set_xticks([a for a,_ in ticks]); ax.set_xticklabels([b for _,b in ticks],fontsize=17,fontweight="bold",pad=34) if False else ax.set_xticklabels([b for _,b in ticks],fontsize=17,fontweight="bold")
    ax.tick_params(axis="x",pad=38,length=0); ax.set_title(name,fontsize=24,fontweight="bold",color="#1F2933",pad=18)
    ax.set_ylabel("מיליארדי ש\"ח",fontsize=15,color="#5F6B78"); ax.spines[["top","right"]].set_visible(False); ax.yaxis.grid(True,color="#EEF1F4"); ax.set_axisbelow(True)
    ax.set_ylim(0,max(s,fx.sum(),mx.sum(),mx.max())*1.12)
fig.suptitle("כמה כסף יש בכל סוג: חו\"ל מלא, שקלי ומשולב, ובתוכם מגודר ולא מגודר",fontsize=26,fontweight="bold",color="#1F2933",x=0.5,y=0.99)
import matplotlib.patches as mp
fig.legend(handles=[mp.Patch(color=col[k],label=k) for k in ["שקלי","לא מגודר","מגודר","גידור חלקי","ללא פירוק"]],loc="lower center",bbox_to_anchor=(0.5,0.045),ncol=5,fontsize=15,frameon=False)
fig.text(0.5,0.012,"מקור: data.gov.il ורשות ניירות ערך (8.2026) · משולבים: מפוצלים לפי יחס גידור (מט\"ח מתוך חו\"ל); בקרנות משולבות אין נתון",ha="center",fontsize=11,color="#5F6B78")
fig.tight_layout(rect=[0,0.11,1,0.95]); fig.savefig("deck/gidur/cluster.png"); print(data(t,"t"),data(f,"f"))
