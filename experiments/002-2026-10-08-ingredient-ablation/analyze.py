"""Analysis of experiment 002 (T1.7): which smallpaint ingredients are necessary for the look?

Re-runs from the render cache, so every render must already exist (``jobs.py``). Writes
``results.json`` and the ``fig_*.png`` previews to the output directory, and prints the tables.
Deterministic: every test is an exact permutation test, so no random number is drawn.

``--jobs``, ``--reference`` and ``--out-dir`` exist to validate this script on a smaller subset
(a size-64 smoke run in a scratch cache). The defaults are the experiment.
"""

import argparse
import importlib.util
import json
import math
from pathlib import Path

import numpy as np
from painterly_analysis import (
    DIFFUSE_REGION_IDS,
    ensemble,
    metrics,
    read_ppm,
    smallpaint_display,
    write_png,
)
from painterly_analysis.experiment import Job, load, measure_ensemble

EXP_DIR = Path(__file__).resolve().parent
EXPERIMENT = EXP_DIR.name
REPO_ROOT = EXP_DIR.parents[1]
DEFAULT_JOBS = EXP_DIR / "jobs.py"
DEFAULT_REFERENCE = REPO_ROOT / "tests" / "data" / "reference" / "smallpaint_painterly.ppm"

# Family-wise level of every decision (README, Hypothesis). Not the oracle option `alpha`.
SIGNIFICANCE = 0.01
HIGHPASS_SIZE = 9  # metrics.measure default; the erosion radius is HIGHPASS_SIZE // 2
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


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("experiment_002_jobs", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def _min_attainable_p(n: int, m: int, alternative: str) -> float:
    """Smallest p-value that ``ensemble.permutation_pvalue`` can return for sizes n and m.

    Mirrors ``ensemble._min_attainable_pvalue`` (two-sided, where a mirror split counts when
    n == m) and gives the one-sided minimum ``1 / C(n + m, n)``.
    """
    splits = math.comb(n + m, n)
    if splits > ensemble.PERMUTATION_MAX_EXACT:
        return 1 / (ensemble.PERMUTATION_RESAMPLES + 1)
    if alternative == "two-sided" and n == m:
        return 2 / splits
    return 1 / splits


def _column(runs: list[dict], key: str) -> list[float]:
    return [run[key] for run in runs]


def _with_luma(run: dict) -> dict:
    """``run`` plus ``r4.luma``: the mean luminance of the back wall, Rec.709 of its mean RGB."""
    red, green, blue = (run[f"r{BACK_WALL_ID}.mean.{c}"] for c in "RGB")
    return {**run, LUMA_KEY: LUMA[0] * red + LUMA[1] * green + LUMA[2] * blue}


def _largest_rel(summary: dict) -> dict | None:
    """The key with the largest |relative difference|, ties broken by key name."""
    defined = [(abs(s["rel_diff"]), key) for key, s in summary.items() if s["rel_diff"] is not None]
    if not defined:
        return None
    value, key = max(defined)
    return {"key": key, "value": value}


def _pair_test(runs: dict[str, list[dict]], key: str, a: str, b: str) -> dict:
    """One key of ``a`` against ``b``: one-sided permutation p-values in both directions.

    ``p_less`` is ``ensemble.separated(a, b, "less")`` at the significance level.
    """
    x, y = _column(runs[a], key), _column(runs[b], key)
    return {
        "comparison": f"{a} vs {b}",
        "key": key,
        "p_less": ensemble.permutation_pvalue(x, y, "less"),
        "p_greater": ensemble.permutation_pvalue(x, y, "greater"),
        "min_attainable_p": _min_attainable_p(len(x), len(y), "less"),
        "effect": ensemble.effect_summary(runs[a], runs[b], [key])[key],
    }


def _h1(runs: dict[str, list[dict]]) -> dict:
    tests = {v: _pair_test(runs, LUMA_KEY, v, POSITIVE) for v in H1_VARIANTS}
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
    tests = {v: _pair_test(runs, PATTERN_KEY, v, POSITIVE) for v in H2_VARIANTS}
    return {"metric": PATTERN_KEY, "tests": tests, **_holm_decision(tests)}


def _h3(runs: dict[str, list[dict]]) -> dict:
    steps = zip(ALPHA_LADDER[:-1], ALPHA_LADDER[1:], strict=True)
    # Each step tests that the higher alpha has the lower back-wall luminance.
    tests = {f"{lo}->{hi}": _pair_test(runs, LUMA_KEY, hi, lo) for lo, hi in steps}
    return {"metric": LUMA_KEY, "tests": tests, **_holm_decision(tests)}


def _family_test(runs: dict[str, list[dict]], family: list[str], a: str, b: str) -> dict:
    """``compare_ensembles`` of ``a`` against ``b`` on the diffuse family, with the power check.

    A comparison is powered when its smallest attainable p is at most the first Holm threshold.
    An underpowered comparison is not run through ``compare_ensembles``: it has no rejections,
    and its verdict can be neither "indistinguishable" nor "refuted".
    """
    x_runs, y_runs = runs[a], runs[b]
    min_p = _min_attainable_p(len(x_runs), len(y_runs), "two-sided")
    threshold = SIGNIFICANCE / len(family)
    powered = min_p <= threshold
    summary = ensemble.effect_summary(x_runs, y_runs, family)
    record = {
        "comparison": f"{a} vs {b}",
        "n_keys": len(family),
        "min_attainable_p": min_p,
        "holm_first_threshold": threshold,
        "powered": powered,
        "effect_summary": summary,
        "largest_abs_rel_diff": _largest_rel(summary),
    }
    if powered:
        comparison = ensemble.compare_ensembles(x_runs, y_runs, family, SIGNIFICANCE)
        if comparison.min_attainable_p != min_p:
            raise RuntimeError("power formula is out of step with ensemble.compare_ensembles")
        record["pvalues"] = comparison.pvalues
        record["rejected_keys"] = [key for key in family if comparison.rejected[key]]
    else:
        record["pvalues"] = {
            key: ensemble.permutation_pvalue(
                _column(x_runs, key), _column(y_runs, key), "two-sided"
            )
            for key in family
        }
        record["rejected_keys"] = None
    return record


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


def _ab8(jobs: list[Job]) -> np.ndarray:
    """``ab8`` of pair 0: the display image of the two half renders summed, at 2 * passes."""
    first, second = load(jobs[0]), load(jobs[1])
    return smallpaint_display(
        np.asarray(first.sum) + np.asarray(second.sum), first.passes + second.passes
    )


def _quarter(img8: np.ndarray) -> np.ndarray:
    """Quarter-size preview: the mean over PREVIEW_FACTOR x PREVIEW_FACTOR blocks, rounded."""
    h, w = img8.shape[:2]
    if h % PREVIEW_FACTOR or w % PREVIEW_FACTOR:
        raise ValueError(f"image side must be a multiple of {PREVIEW_FACTOR}, got {h} x {w}")
    blocks = img8.astype(np.float64).reshape(
        h // PREVIEW_FACTOR, PREVIEW_FACTOR, w // PREVIEW_FACTOR, PREVIEW_FACTOR, 3
    )
    return np.round(blocks.mean(axis=(1, 3))).astype(np.uint8)


def _grid(previews: dict[str, np.ndarray]) -> np.ndarray:
    """Mosaic of the previews in GRID_LAYOUT (row-major). Empty cells stay black."""
    tile = next(iter(previews.values())).shape[0]
    rows, cols = len(GRID_LAYOUT), len(GRID_LAYOUT[0])
    mosaic = np.zeros((rows * tile, cols * tile, 3), dtype=np.uint8)
    for r, row in enumerate(GRID_LAYOUT):
        for c, name in enumerate(row):
            if name is not None:
                mosaic[r * tile : (r + 1) * tile, c * tile : (c + 1) * tile] = previews[name]
    return mosaic


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


def _json_safe(value):
    """JSON has no infinity or NaN. NaN is an error and is never written."""
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and math.isnan(value):
        raise RuntimeError("NaN in results")
    return value


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
    print(
        f"{title} {test['comparison']}: keys={test['n_keys']} {count} "
        f"min_attainable_p={test['min_attainable_p']:.3g} "
        f"threshold={test['holm_first_threshold']:.3g} -> {verdict}"
    )


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    ensembles = _load_module(args.jobs).ENSEMBLES
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

    raw = {name: measure_ensemble(jobs, reference8, object_id) for name, jobs in ensembles.items()}
    keys = sorted(raw[POSITIVE][0])
    for name, metric_runs in raw.items():
        if any(sorted(run) != keys for run in metric_runs):
            raise RuntimeError(f"metric keys of {name} differ")
    family = metrics.DIFFUSE_KEY_FAMILY(keys)
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
    ab8 = {name: _ab8(jobs) for name, jobs in ensembles.items()}
    for name in CONFIGURATIONS:
        write_png(out_dir / f"fig_{name}.png", ab8[name])
    previews = {name: _quarter(img) for name, img in ab8.items()}
    previews["reference"] = _quarter(reference8)
    grid_name = "fig_grid.png"
    write_png(out_dir / grid_name, _grid(previews))
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
        "metric_keys": {"all": len(keys), "diffuse_family": len(family), "family": family},
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
    text = json.dumps(_json_safe(results), indent=2, sort_keys=True) + "\n"
    if "NaN" in text:
        raise RuntimeError("NaN in results.json")
    (out_dir / "results.json").write_text(text, encoding="utf-8")

    print(f"keys all={len(keys)} diffuse family={len(family)}; passes={passes}")
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
