"""Markdown rows of the planning verdict counts (summary.json)."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent
s = json.load(open(HERE / "summary.json"))
PRED = {"white": "1", "white_drift": "1", "ar1": "1", "pix_gauss": "1", "jit_gauss": "2", "img_gauss": "3", "mix": "none"}
def cells(c):
    return ", ".join(f"{k}: {v}" for k, v in sorted(c.items(), key=lambda kv: int(kv[0])))
print("| model | predicted cell | (200, 400), H1/H2-type | (200, 400), H3-type | (400, 800), H1/H2-type | (400, 800), H3-type | H4 rejections |")
print("|---|---|---|---|---|---|---|")
for m in PRED:
    b, a = s["b"]["counts"][m], s["a"]["counts"][m]
    h3b = "n/a" if m == "jit_gauss" else cells(b["H3"])
    h3a = "n/a" if m == "jit_gauss" else cells(a["H3"])
    mech = s["b"]["mech_rejections"][m] + s["a"]["mech_rejections"][m]
    n = s["b"]["seeds"] + s["a"]["seeds"]
    print(f"| `{m}` | {PRED[m]} | {cells(b['H1H2'])} | {h3b} | {cells(a['H1H2'])} | {h3a} | {mech} of {n} |")
for c in ("b", "a"):
    print(c, "seeds", s[c]["seeds"], "runs", s[c]["runs"], "opposite", s[c]["opposite"], "same", s[c]["same_direction_misreadings"])
