"""Counts of the round-2 planning runs (second review round) for the 007 README.

Reads r2_cover.jsonl, r2_h4_isotropic.jsonl and r2_sweep.jsonl (outputs of run_r2.py) and writes
summary_r2.json next to them. Cells are those of the README verdict table (1-7).

Reference realizations: run_contrast draws the 400 px reference first from the stream
[seed, model_index, 500], whatever the contrast, so seed k has one reference shared by both
contrasts. H4 and H5 are therefore counted over the 200 distinct references (seeds 0-199).
"""

import collections
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREDICTED = {  # model -> (reading, predicted cell, applies to the H3 type)
    "white": ("A", 1, True), "white_drift": ("A", 1, True), "ar1": ("A", 1, True),
    "pix_x": ("A", 1, True), "pix_gauss": ("A", 1, True), "ipjit_x": ("A'", 2, False),
    "jit_x": ("B", 3, False), "jit_gauss": ("B", 3, False), "img_x": ("C", 4, True),
    "img_gauss": ("C", 4, True), "mix_x": (None, None, True), "mix_gauss": (None, None, True),
}
SUPPORT_SIDE, REFUTE_SIDE = {1, 2, 5}, {3, 4, 6}
CONTRAST = {"a": "(400, 800)", "b": "(200, 400)"}


def load(name):
    return [json.loads(line) for line in open(HERE / name)]


def main():
    cover = load("r2_cover.jsonl")
    out = {"counts": {}, "runs": {}}
    opposite, same_dir, power = [], [], {}
    d_bound, djit_b, djit_ipjit = [], [], []
    for r in cover:
        reading, cell, h3 = PREDICTED[r["model"]]
        for typ in ("H12", "H3"):
            key = f"{r['model']}|{CONTRAST[r['c']]}|{typ}"
            out["counts"].setdefault(key, collections.Counter())[r[typ]] += 1
            if reading is None or (typ == "H3" and not h3):
                continue
            out["runs"][CONTRAST[r["c"]]] = out["runs"].get(CONTRAST[r["c"]], 0) + 1
            power.setdefault(key, [0, 0])
            power[key][0] += r[typ] == cell
            power[key][1] += 1
            wrong = REFUTE_SIDE if cell in SUPPORT_SIDE else SUPPORT_SIDE
            if r[typ] in wrong:
                opposite.append(key)
            elif r[typ] != cell and r[typ] != 7:
                same_dir.append(f"{key}: cell {r[typ]}")
        if reading is None:
            continue
        # D's bound nearest 0 on the predicted side (|d| units): A and A' predict D > 0.
        d_bound.append((r["D_ci"][0] if reading in ("A", "A'") else -r["D_ci"][1], r["model"], r["c"]))
        if reading == "B":
            djit_b.append((r["D_jit_ci"][0], r["model"], r["c"]))
        if reading == "A'":
            djit_ipjit.append((r["D_jit_ci"][1], r["model"], r["c"]))
    out["counts"] = {k: dict(sorted(v.items())) for k, v in out["counts"].items()}
    out["opposite_direction"] = {"count": len(opposite), "runs": out.pop("runs"), "where": opposite}
    out["same_direction"] = {"count": len(same_dir), "where": same_dir}
    out["power_lowest"] = sorted(
        ({"key": k, "hits": h, "runs": n, "fraction": h / n} for k, (h, n) in power.items()),
        key=lambda e: e["fraction"],
    )[:5]
    out["D_bound_nearest_0_min"] = min(d_bound)
    out["D_jit_lower_B_min"] = min(djit_b)
    out["D_jit_upper_ipjit_max"] = max(djit_ipjit)

    refs = [r for r in cover if r["c"] == "b"]  # seeds 0-199: every distinct reference once
    h5 = collections.Counter(r["model"] for r in refs if r["h5_p"] <= 0.01)
    h4_axis = collections.Counter(r["model"] for r in refs if r["h4_p"] <= 0.01)
    h4_iso = collections.Counter(r["model"] for r in load("r2_h4_isotropic.jsonl") if r["h4_2d_p"] <= 0.01)
    n_ref = collections.Counter(r["model"] for r in refs)
    out["H5_rejections"] = {m: f"{h5[m]} of {n_ref[m]}" for m in PREDICTED}
    out["H4_isotropic_rejections"] = {m: f"{h4_iso[m]} of {n_ref[m]}" for m in PREDICTED}
    out["H4_axis_filters_rejections"] = {m: f"{h4_axis[m]} of {n_ref[m]}" for m in PREDICTED}

    sweep = collections.defaultdict(collections.Counter)
    for r in load("r2_sweep.jsonl") + [r for r in cover if r["model"].startswith("mix")]:
        for typ in ("H12", "H3"):
            sweep[f"w={r['w']}|{r['model']}|{CONTRAST[r['c']]}|{typ}"][r[typ]] += 1
    out["mixture_sweep"] = {k: dict(sorted(v.items())) for k, v in sorted(sweep.items())}
    (HERE / "summary_r2.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
