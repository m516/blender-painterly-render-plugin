"""Summarize the planning verdict runs: H1/H2-type (with C_jit) and H3-type (without, at 0.005)."""

import collections
import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from synth import MODELS, holm_count, verdict  # noqa: E402

CELL = {
    "supported": 1,
    "refuted_jitter_px": 2,
    "refuted_image": 3,
    "partially_supported": 4,
    "partially_refuted": 5,
    "inconclusive": 6,
}
PRED = {"white": 1, "white_drift": 1, "ar1": 1, "pix_gauss": 1, "jit_gauss": 2, "img_gauss": 3}

rows = collections.defaultdict(dict)
for f in glob.glob(str(HERE / "cover_*.jsonl")):
    for line in open(f):
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows[(d["contrast"], d["seed"])][d["model"]] = d

out = {}
for contrast in ("b", "a"):
    seeds = sorted(s for (c, s), v in rows.items() if c == contrast and len(v) == len(MODELS))
    counts = {}
    mech = {}
    for model in MODELS:
        c13 = collections.Counter()
        c3 = collections.Counter()
        m = 0
        for s in seeds:
            d = rows[(contrast, s)][model]
            c13[CELL[d["verdict"]]] += 1
            rp = holm_count(d["p_px"], 0.005)
            ri = holm_count(d["p_ip"], 0.005)
            c3[CELL[verdict(rp, ri, None, d["D_ci"], None)]] += 1
            m += d["mech_p"] <= 0.01
        counts[model] = {"H1H2": dict(sorted(c13.items())), "H3": dict(sorted(c3.items()))}
        mech[model] = m
    out[contrast] = {"seeds": len(seeds), "counts": counts, "mech_rejections": mech}
    print(f"contrast {contrast}: {len(seeds)} complete seeds")
    for model in MODELS:
        print(f"  {model:12s} H1/H2-type {counts[model]['H1H2']}  H3-type {counts[model]['H3']}  "
              f"H4 rejections {mech[model]}")
    OPPOSITE = {1: (2, 3, 5), 2: (1, 4), 3: (1, 4)}
    opp = 0
    same = 0
    hit = {}
    runs = 0
    for model, pred in PRED.items():
        for typ in ("H1H2", "H3"):
            if model == "jit_gauss" and typ == "H3":
                continue
            c = counts[model][typ]
            runs += sum(c.values())
            opp += sum(n for cell, n in c.items() if cell in OPPOSITE[pred])
            same += sum(n for cell, n in c.items() if cell not in OPPOSITE[pred] + (pred, 6))
            hit[f"{model}/{typ}"] = c.get(pred, 0)
    print(f"  opposite-direction verdicts {opp}, same-direction misreadings {same}, of {runs} runs")
    print(f"  predicted-cell counts {hit}")
    out[contrast]["opposite"] = opp
    out[contrast]["same_direction_misreadings"] = same
    out[contrast]["runs"] = runs
json.dump(out, open(HERE / "summary.json", "w"), indent=1)
