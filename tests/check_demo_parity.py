"""השוואת המנוע ב-JS (demo/index.html) למנוע ב-Python על כמה תרחישים. נכשל אם סה"כ שונה ביותר מ-1e-4 יחסי או שורה ביותר מ-0.05 מיליון $."""
import json, re, subprocess, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indexfx.model import Params, prepare, shock_flows

html = Path("demo/index.html").read_text(encoding="utf-8")
script = re.search(r"<script>(.*)</script>", html, re.S).group(1)
script = script.split("const $=id=>")[0]            # רק הנתונים והמנוע
node = script + """
const inp=JSON.parse(process.argv[2]);const z=process.argv[3]==='1';
const out=run(inp,z).map(x=>x.flow);console.log(JSON.stringify(out));
"""
Path("/tmp/parity.js").write_text(node)

m = pd.read_csv("data/model_inputs.csv")
m["system"] = m.legal_id.map(pd.read_csv("data/track_totals.csv").drop_duplicates("legal_id").set_index("legal_id").system)
d = prepare(m)
# סדר השורות בדמו = סדר prepare
cases = [dict(rus=.01, rrow=0, ril=0, e=0, dyil=0, dyfx=0, mode="continuous", lam=1),
         dict(rus=.05, rrow=-.03, ril=.02, e=.01, dyil=.25, dyfx=.1, mode="continuous", lam=.5),
         dict(rus=-.08, rrow=-.05, ril=-.06, e=-.02, dyil=-.2, dyfx=0, mode="band", lam=1),
         dict(rus=.02, rrow=.01, ril=0, e=0, dyil=0, dyfx=0, mode="band", lam=1)]
worst = 0
for c in cases:
    for zero in (0, 1):
        dd = d.copy()
        if zero:
            for k in ("dv_us_w", "dv_row_w", "dv_il_w"): dd[k] = 0.0
        p = Params(lam=c["lam"], mode=c["mode"], usdils=3.19, dur_il=5, dur_fx=6)
        py = shock_flows(dd, r_us=c["rus"], r_row=c["rrow"], r_il=c["ril"], e=c["e"], dy_il=c["dyil"], dy_fx=c["dyfx"], p=p).flow_usd_m.to_numpy()
        # JS מקבל dyil כשינוי תשואה בנק' אחוז; מודל Python מקבל אותו ב-dy_il (אותו יחידה) - ללא המרה
        js = json.loads(subprocess.check_output(["node", "/tmp/parity.js", json.dumps({**c, "spot": 3.19, "dil": 5, "dfx": 6}), str(zero)]))
        diff = max(abs(a - b) for a, b in zip(py, js))
        worst = max(worst, diff)
        assert abs(py.sum() - sum(js)) <= 1e-4 * max(1.0, abs(py.sum())), (py.sum(), sum(js))
        print(f"{c['mode']:10s} zero_dv={zero} סה\"כ py={py.sum():10.3f} js={sum(js):10.3f} פער מקס'={diff:.2e}")
assert len(py) == len(js)
assert worst < 0.05, worst   # עיגול הנתונים המוטמעים (5 ספרות) -> פער של אלפי $ לכל היותר
print("PARITY OK")
