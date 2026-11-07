"""הדמו (demo/index.html) מול החישוב ב-Python (e3) - אותו תרחיש, ריבית 0 (כמו ב-e3). נכשל בפער > 0.01 מיליארד."""
import json, re, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from e3_scenario_from_flows import wls_full

html = Path("demo/index.html").read_text(encoding="utf-8")
script = re.search(r"<script>(.*)</script>", html, re.S).group(1).split("function render")[0]
Path("/tmp/parity2.js").write_text(script + "\nconsole.log(JSON.stringify(calc(JSON.parse(process.argv[2]))));")
p = pd.read_csv("data/flows/flow_panel.csv.gz"); d = p[p.y.abs() < 0.10].dropna(subset=["gain_phys", "gain_syn", "growth_fx"])
t = pd.read_csv("data/model2_inputs.csv")
worst = 0
for grp, s in (("general", t[t.general]), ("all", t)):
    for spec, wt in (("weighted", True), ("unweighted", False)):
        b, V = wls_full(d, ["gain_phys", "gain_syn", "growth_fx"], wt)
        A = s.total_k / 1e6
        x = np.array([((s.U_phys_us + s.U_phys_row) * 0.10 * A).sum(), ((s.U_syn_us + s.U_syn_row) * 0.10 * A).sum(),
                      (s.FX0 * ((s.U_phys_us + s.U_phys_row + s.U_syn_us + s.U_syn_row + s.eqfr_ilf) * 0.10 + s.E_il * 0.05 + s.B_il * 0.05) * A).sum()])
        py = float(x @ b)
        js = json.loads(subprocess.check_output(["node", "/tmp/parity2.js", json.dumps(
            {"us": .1, "row": .1, "il": .05, "b": .05, "i": 0, "h": 3, "grp": grp, "spec": spec})]))["est"]
        worst = max(worst, abs(py - js))
        print(f"{grp:8s} {spec:10s} python={py:8.3f} js={js:8.3f}")
assert worst < 0.01, worst
print("PARITY OK")
