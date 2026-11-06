"""בונה demo/index.html - מודל ב': קלט ידני (ריבית, מדדים בחו"ל/בארץ, שער) -> זרם מט"ח נדרש והשפעה על USD/ILS.
המנוע ב-JS זהה ל-indexfx/model.py (מאומת ב-tests/check_demo_parity.py). הנתונים מוטמעים (אין שרת, אין קריאות רשת)."""
import json
from pathlib import Path

import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from indexfx.model import prepare  # noqa: E402

m = pd.read_csv("data/model_inputs.csv")
tt = pd.read_csv("data/track_totals.csv").drop_duplicates("legal_id").set_index("legal_id")
m["system"] = m.legal_id.map(tt.system)
d = prepare(m)
SYS = {"gm": "גמל", "pn": "פנסיה", "in": "ביטוח"}
cols = ["eqfx_us_w", "eqfx_row_w", "eq_us_w", "eq_row_w", "eq_il_w", "dv_us_w", "dv_row_w", "dv_il_w", "bond_il_w", "bond_fx_w",
        "fx_spot_w", "fx_fwd_w", "fx0", "T", "lo", "hi"]
rows = []
for _, r in d.iterrows():
    name = r.pol_name if isinstance(r.pol_name, str) else f"{r.legal_id}/{int(r.track) if pd.notna(r.track) else ''}"
    rows.append([name[:60], SYS.get(r.system, r.system), round(float(r.total_k), 1)] + [round(float(r[c]), 5) for c in cols])
cal = json.load(open("data/results/calibration.json"))
beta = round((cal["daily"]["combined_us_row_beta_pct_per_bn"] + cal["weekly"]["combined_us_row_beta_pct_per_bn"]) / 2, 3)
html = Path("demo/template.html").read_text(encoding="utf-8")
html = html.replace("__DATA__", json.dumps({"cols": ["name", "sys", "total_k"] + cols, "rows": rows}, ensure_ascii=False, separators=(",", ":")))
html = html.replace("__BETA__", str(beta))
Path("demo/index.html").write_text(html, encoding="utf-8")
print(f"[c3] demo/index.html: {len(rows)} מסלולים, β={beta}%/bn, {len(html)//1024}KB")
