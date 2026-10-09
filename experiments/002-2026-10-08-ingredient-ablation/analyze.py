"""Analysis of experiment 002 (T1.7): which smallpaint ingredients are necessary for the look?

Re-runs from the render cache, so every render must already exist (``jobs.py``). Writes
``results.json`` and the ``fig_*.png`` previews to the output directory, and prints the tables.
Deterministic: every test is an exact permutation test, so no random number is drawn.

``--jobs``, ``--reference`` and ``--out-dir`` exist to validate this script on a smaller subset
(a size-64 smoke run in a scratch cache). The defaults are the experiment.
"""

import argparse
from pathlib import Path

import numpy as np
from painterly_analysis import (
    DIFFUSE_REGION_IDS,
    ensemble,
    metrics,
    read_ppm,
    report,
    write_png,
)
from painterly_analysis.experiment import Job, load
from painterly_analysis.metrics import HIGHPASS_SIZE

EXP_DIR = Path(__file__).resolve().parent
EXPERIMENT = EXP_DIR.name
REPO_ROOT = EXP_DIR.parents[1]
DEFAULT_JOBS = EXP_DIR / "jobs.py"
DEFAULT_REFERENCE = REPO_ROOT / "tests" / "data" / "reference" / "smallpaint_painterly.ppm"

# Family-wise level of every decision (README, Hypothesis). Not the oracle option `alpha`.
SIGNIFICANCE = 0.01
ERODE_RADIUS = HIGHPASS_SIZE // 2
BACK_WALL_ID = 4  # SPEC §9: the back plane
LUMA = metrics.LUMA_REC709  # ITU-R BT.709 luma weights (definition)
LUMA_KEY = f"r{BACK_WALL_ID}.luma"  # derived here: Rec.709 luminance of the region-4 mean RGB
PATTERN_KEY = "all.pattern_corr"
TEXTURE_TAGS = ("structure_std", "pattern_corr", "lag1", "spectral_slope")
POSITIVE = "positive"
VARIANTS = (
    "ghost_none",
    "ghost_lights",
    "alpha_025",
    "alpha_05",
    "alpha_1",
    "u2_independent",
    "u2_base3",
    "per_path_start",
    "stop_at_emitter",
)
CONFIGURATIONS = (POSITIVE, *VARIANTS)
H1_VARIANTS = ("ghost_none", "alpha_1")
H2_VARIANTS = ("u2_independent", "u2_base3", "per_path_start")
ALPHA_LADDER = (POSITIVE, "alpha_025", "alpha_05", "alpha_1")
ALPHA_LADDER_VALUES = (0.0, 0.25, 0.5, 1.0)  # oracle option alpha of each rung (SPEC §4)
PREVIEW_FACTOR = 4  # quarter-size previews: block means over 4 x 4 pixels
GRID_LAYOUT = (
    (POSITIVE, "ghost_none", "ghost_lights", "alpha_025"),
    ("alpha_05", "alpha_1", "u2_independent", "u2_base3"),
    ("per_path_start", "stop_at_emitter", "reference", None),
)
# The previews in GRID_LAYOUT's row-major order, without the empty cell (the trailing None).
GRID_ORDER = tuple(name for row in GRID_LAYOUT for name in row if name is not None)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analysis of experiment 002 (T1.7).")
    parser.add_argument(
        "--jobs",
        type=Path,
        default=DEFAULT_JOBS,
        help="jobs file defining ENSEMBLES (default: this experiment's jobs.py)",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=DEFAULT_REFERENCE,
        help="reference PPM, at the size of the renders (default: the 400 px GUI reference)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=EXP_DIR,
        help="directory for results.json and the figures (default: this directory)",
    )
    return parser.parse_args(argv)


def _check_design(ensembles: dict[str, list[Job]]) -> None:
    """The card's design: each variant changes exactly one option of the positive control."""
    if set(ensembles) != set(CONFIGURATIONS):
        raise RuntimeError(f"ENSEMBLES must hold {CONFIGURATIONS}, got {sorted(ensembles)}")
    base = dict(ensembles[POSITIVE][0].options)
    for name in VARIANTS:
        options = dict(ensembles[name][0].options)
        changed = [k for k in sorted(set(base) | set(options)) if base.get(k) != options.get(k)]
        if len(changed) != 1:
            raise RuntimeError(f"{name} must change exactly one option, changes {changed}")
    for name, value in zip(ALPHA_LADDER, ALPHA_LADDER_VALUES, strict=True):
        if float(dict(ensembles[name][0].options).get("alpha", 0.0)) != value:
            raise RuntimeError(f"{name}: option alpha must be {value}")


def _with_luma(run: dict) -> dict:
    """``run`` plus ``r4.luma``: the mean luminance of the back wall, Rec.709 of its mean RGB."""
    red, green, blue = (run[f"r{BACK_WALL_ID}.mean.{c}"] for c in "RGB")
    return {**run, LUMA_KEY: LUMA[0] * red + LUMA[1] * green + LUMA[2] * blue}


def _h1(runs: dict[str, list[dict]]) -> dict:
    tests = {
        v: report.directional_pair_test(
            runs[v], runs[POSITIVE], LUMA_KEY, SIGNIFICANCE, labels=(v, POSITIVE)
        )
        for v in H1_VARIANTS
    }
    if all(t["p_less"] <= SIGNIFICANCE for t in tests.values()):
        decision = "supported"
    elif any(t["p_greater"] <= SIGNIFICANCE for t in tests.values()):
        decision = "refuted"
    else:
        decision = "inconclusive"
    return {"metric": LUMA_KEY, "tests": tests, "decision": decision}


def _holm_decision(tests: dict[str, dict]) -> dict:
    """Holm over one-sided tests of the same key: supported if all 'less' are rejected."""
    less = ensemble.holm({name: t["p_less"] for name, t in tests.items()}, SIGNIFICANCE)
    greater = ensemble.holm({name: t["p_greater"] for name, t in tests.items()}, SIGNIFICANCE)
    if all(less.values()):
        decision = "supported"
    elif any(greater.values()):
        decision = "refuted"
    else:
        decision = "inconclusive"
    return {"holm_rejected_less": less, "holm_rejected_greater": greater, "decision": decision}


def _h2(runs: dict[str, list[dict]]) -> dict:
    tests = {
        v: report.directional_pair_test(
            runs[v], runs[POSITIVE], PATTERN_KEY, SIGNIFICANCE, labels=(v, POSITIVE)
        )
        for v in H2_VARIANTS
    }
    return {"metric": PATTERN_KEY, "tests": tests, **_holm_decision(tests)}


def _h3(runs: dict[str, list[dict]]) -> dict:
    # Each step lo -> hi tests that the higher alpha has the lower back-wall luminance.
    ladder = report.adjacent_tests(runs, ALPHA_LADDER, LUMA_KEY, SIGNIFICANCE)
    return {"metric": LUMA_KEY, "tests": ladder["steps"], **_holm_decision(ladder["steps"])}


def _family_test(runs: dict[str, list[dict]], family: list[str], a: str, b: str) -> dict:
    """``compare_ensembles`` of ``a`` against ``b`` on the diffuse family, with the power check.

    An underpowered comparison is not run through ``compare_ensembles``: it has no rejections,
    and its verdict can be neither "indistinguishable" nor "refuted" (``report.family_test``).
    """
    return {
        "comparison": f"{a} vs {b}",
        **report.family_test(runs[a], runs[b], family, SIGNIFICANCE),
    }


def _h4(runs: dict[str, list[dict]], family: list[str]) -> dict:
    test = _family_test(runs, family, "stop_at_emitter", POSITIVE)
    rejected = test["rejected_keys"] or []
    mean_hit = [key for key in rejected if ".mean." in key]
    texture_hit = [key for key in rejected if any(tag in key for tag in TEXTURE_TAGS)]
    if mean_hit and texture_hit:
        decision = "supported"
    elif test["powered"] and not rejected:
        decision = "refuted"
    else:
        decision = "inconclusive"
    return {
        "test": test,
        "distinguishable": bool(rejected),
        "rejected_mean_keys": mean_hit,
        "rejected_texture_keys": texture_hit,
        "decision": decision,
    }


def _h5(runs: dict[str, list[dict]], family: list[str]) -> dict:
    test = _family_test(runs, family, "ghost_lights", POSITIVE)
    if not test["powered"]:
        verdict = "underpowered"
    elif test["rejected_keys"]:
        verdict = "distinguishable"
    else:
        verdict = "indistinguishable"
    ratio_keys = [PATTERN_KEY, *(key for key in family if ".mean." in key)]
    ratios = {}
    for key in ratio_keys:
        s = test["effect_summary"][key]
        ratios[key] = s["mean_a"] / s["mean_b"] if s["mean_b"] != 0 else None
    return {"test": test, "verdict": verdict, "ratio_ghost_lights_over_positive": ratios}


def _k_summary(ensembles: dict[str, list[Job]]) -> dict[str, dict]:
    """K draws per pixel per pass of each render (mean over pixels of k_consumed / P)."""
    summary = {}
    for name, jobs in ensembles.items():
        per_render = []
        for job in jobs:
            render = load(job)
            per_render.append(float(np.mean(render.k_consumed)) / render.passes)
        summary[name] = {
            "mean": float(np.mean(per_render)),
            "sd": float(np.std(per_render, ddof=1)),
            "renders": len(per_render),
        }
    return summary


def _decision_table(h1: dict, h2: dict, h3: dict, h4: dict, h5: dict) -> list[dict]:
    rows = []
    for hypothesis, block in (("H1", h1), ("H2", h2), ("H3", h3)):
        for test in block["tests"].values():
            rows.append(
                {
                    "hypothesis": hypothesis,
                    "comparison": test["comparison"],
                    "key": test["key"],
                    "p_value_less": test["p_less"],
                    "p_value_greater": test["p_greater"],
                    "min_attainable_p": test["min_attainable_p"],
                }
            )
        rows.append(
            {"hypothesis": hypothesis, "comparison": "overall", "outcome": block["decision"]}
        )
    rows.append(
        {
            "hypothesis": "H4",
            "comparison": h4["test"]["comparison"],
            "key": f"diffuse family, {h4['test']['n_keys']} keys",
            "min_attainable_p": h4["test"]["min_attainable_p"],
            "outcome": h4["decision"],
        }
    )
    rows.append(
        {
            "hypothesis": "H5",
            "comparison": h5["test"]["comparison"],
            "key": f"diffuse family, {h5['test']['n_keys']} keys",
            "min_attainable_p": h5["test"]["min_attainable_p"],
            "outcome": h5["verdict"],
        }
    )
    return rows


def _print_tests(title: str, block: dict) -> None:
    print(f"{title}: {block['decision']}")
    for name, test in block["tests"].items():
        print(
            f"  {name}: p_less={test['p_less']:.6g} p_greater={test['p_greater']:.6g} "
            f"min_attainable_p={test['min_attainable_p']:.3g}"
        )


def _print_family(title: str, test: dict, verdict: str) -> None:
    rejected = test["rejected_keys"]
    count = "underpowered (not run)" if rejected is None else f"rejected={len(rejected)}"
    rel = test["largest_abs_rel_diff"]
    cohen = test["largest_abs_cohen_d"]
    print(
        f"{title} {test['comparison']}: keys={test['n_keys']} {count} "
        f"min_attainable_p={test['min_attainable_p']:.3g} "
        f"threshold={test['holm_first_threshold']:.3g} "
        f"largest |rel|={_fmt_largest(rel)} largest |d|={_fmt_largest(cohen)} -> {verdict}"
    )


def _fmt_largest(largest: dict | None) -> str:
    if largest is None:
        return "n/a"
    return f"{largest['value']:.4g} ({largest['key']})"


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    ensembles = report.load_jobs_module(args.jobs).ENSEMBLES
    _check_design(ensembles)
    reference8 = read_ppm(args.reference)

    first = {name: load(jobs[0]) for name, jobs in ensembles.items()}
    pass_counts = {render.passes for render in first.values()}
    if len(pass_counts) != 1:
        raise RuntimeError(f"configurations differ in passes: {sorted(pass_counts)}")
    passes = pass_counts.pop()
    object_id = first[POSITIVE].object_id
    for name, render in first.items():
        if not np.array_equal(render.object_id, object_id):
            raise RuntimeError(f"object id of {name} differs from {POSITIVE}")
    masks = metrics.region_masks(object_id, ERODE_RADIUS)
    measured = [r for r in DIFFUSE_REGION_IDS if r in masks]
    absent = [r for r in DIFFUSE_REGION_IDS if r not in masks]

    raw = {
        name: report.ensemble_metrics(jobs, reference8, DIFFUSE_REGION_IDS, object_id=object_id)
        for name, jobs in ensembles.items()
    }
    keys = sorted(raw[POSITIVE][0])
    for name, metric_runs in raw.items():
        if any(sorted(run) != keys for run in metric_runs):
            raise RuntimeError(f"metric keys of {name} differ")
    family = metrics.diffuse_key_family(keys)
    if not family:
        raise RuntimeError("the diffuse key family is empty")
    runs = {name: [_with_luma(run) for run in metric_runs] for name, metric_runs in raw.items()}
    table_keys = [*family, LUMA_KEY]

    h1 = _h1(runs)
    h2 = _h2(runs)
    h3 = _h3(runs)
    h4 = _h4(runs, family)
    h5 = _h5(runs, family)
    effects = {v: ensemble.effect_summary(runs[v], runs[POSITIVE], table_keys) for v in VARIANTS}
    effect_size_table = {
        v: {key: effects[v][key]["cohen_d"] for key in table_keys} for v in VARIANTS
    }
    k_summary = _k_summary(ensembles)

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    ab8 = {name: report.ab8_of_pair(jobs) for name, jobs in ensembles.items()}
    for name in CONFIGURATIONS:
        write_png(out_dir / f"fig_{name}.png", ab8[name])
    previews = {name: report.block_preview(img, PREVIEW_FACTOR) for name, img in ab8.items()}
    previews["reference"] = report.block_preview(reference8, PREVIEW_FACTOR)
    grid_name = "fig_grid.png"
    grid = report.mosaic({name: previews[name] for name in GRID_ORDER}, len(GRID_LAYOUT[0]))
    write_png(out_dir / grid_name, grid)
    figures = {
        f"fig_{name}.png": (out_dir / f"fig_{name}.png").stat().st_size for name in CONFIGURATIONS
    }
    figures[grid_name] = (out_dir / grid_name).stat().st_size

    results = {
        "experiment": EXPERIMENT,
        "significance": SIGNIFICANCE,
        "size": int(object_id.shape[0]),
        "passes": passes,
        "pairs": len(ensembles[POSITIVE]) // 2,
        "highpass_size": HIGHPASS_SIZE,
        "erosion_radius": ERODE_RADIUS,
        "regions": {
            "diffuse_ids": list(DIFFUSE_REGION_IDS),
            "measured": measured,
            "absent": absent,
        },
        "object_id_values": sorted(int(v) for v in np.unique(object_id)),
        "metric_keys": {"measured": len(keys), "diffuse_family": len(family), "family": family},
        "configurations": {
            name: {"options": dict(jobs[0].options), "seeds": [job.seed for job in jobs]}
            for name, jobs in ensembles.items()
        },
        "k_consumed_per_pixel_per_pass": k_summary,
        "h1": h1,
        "h2": h2,
        "h3": h3,
        "h4": h4,
        "h5": h5,
        "effect_size_table": effect_size_table,
        "effect_summary": effects,
        "decision_table": _decision_table(h1, h2, h3, h4, h5),
        "grid": {
            "file": grid_name,
            "preview_px": int(previews[POSITIVE].shape[0]),
            "layout": [list(row) for row in GRID_LAYOUT],
        },
        "figures": figures,
    }
    report.write_results_json(out_dir / "results.json", results)

    print(f"keys measured={len(keys)} diffuse family={len(family)}; passes={passes}")
    print(f"measured regions {measured}, absent {absent}")
    _print_tests("H1 r4.luma, separated less", h1)
    _print_tests("H2 all.pattern_corr, Holm over three", h2)
    _print_tests("H3 r4.luma ladder, Holm over three", h3)
    _print_family("H4", h4["test"], h4["decision"])
    _print_family("H5", h5["test"], h5["verdict"])
    for key, value in h5["ratio_ghost_lights_over_positive"].items():
        print(f"  H5 ratio {key}: {value}")
    print(
        "K draws per pixel per pass: "
        + ", ".join(f"{name}={stats['mean']:.4f}" for name, stats in k_summary.items())
    )
    print(f"figures (bytes): {figures}")
    print(f"wrote {out_dir / 'results.json'}")


if __name__ == "__main__":
    main()
