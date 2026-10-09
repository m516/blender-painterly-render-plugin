"""Analysis of experiment 003 (T1.8): how long must a chain be? The artist-mode lane length.

Re-runs from the render cache, so every render must already exist (``jobs.py``). Writes
``results.json`` and ``fig_grid.png`` to the output directory, and prints the tables. Deterministic:
every test is an exact permutation test, so no random number is drawn.

``--jobs``, ``--reference`` and ``--out-dir`` exist to validate this script on a smaller subset (a
size-64 smoke run in a scratch cache). The defaults are the experiment.
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
# Earlier experiments whose seeds this one must not reuse (the global seed rule). Block 0 is shared
# on purpose: the positive control ``image`` is experiment 001's ``img64``.
EARLIER_JOBS = (
    REPO_ROOT / "experiments" / "001-2026-10-08-oracle-reproduction" / "jobs.py",
    REPO_ROOT / "experiments" / "002-2026-10-08-ingredient-ablation" / "jobs.py",
)

# Family-wise level of every decision (README, Method). It is not the oracle option `alpha`.
SIGNIFICANCE = 0.01
PASSES = 64  # P of every configuration (jobs.py)
BLOCK = 16  # seeds per configuration: 8 pairs x 2 half renders (jobs.py)
ERODE_RADIUS = HIGHPASS_SIZE // 2
# The experiment's size in pixels (jobs.py SIZE). The cross-experiment seed check applies only at
# this size: a smoke run at another size has option sets that differ from experiments 001 and 002.
EXPERIMENT_SIZE = 400
IMAGE = "image"  # chain=image, the positive control
ROW = "row"  # chain=row
LANE_LENGTHS = (1, 2, 4, 8, 16, 32, 64, 128)  # L of chain=lane:L, ascending
LADDER = tuple(f"lane_{length}" for length in LANE_LENGTHS)
ADJACENT_STEPS = tuple(zip(LADDER[:-1], LADDER[1:], strict=True))  # (shorter, longer)
CONFIGURATIONS = (IMAGE, ROW, *LADDER)
PATTERN_KEY = "all.pattern_corr"
CURVE_KEYS = (PATTERN_KEY, "r4.structure_std", "r4.lag1.x", "r4.lag1.y")  # region 4 = back wall
# The card's deliverable resolution (a definition, not a tunable) for chains per pass.
TARGET_WIDTH = 1920
TARGET_HEIGHT = 1080
PREVIEW_FACTOR = 4  # quarter-size previews: block means over 4 x 4 pixels
GRID_LAYOUT = (
    (IMAGE, ROW, "lane_1", "lane_2"),
    ("lane_4", "lane_8", "lane_16", "lane_32"),
    ("lane_64", "lane_128", "reference", None),
)
# The previews in GRID_LAYOUT's row-major order, without the empty cell (the trailing None).
GRID_ORDER = tuple(name for row in GRID_LAYOUT for name in row if name is not None)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analysis of experiment 003 (T1.8).")
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


def _earlier_options() -> dict[int, dict]:
    """The option set of every seed of experiments 001 and 002, keyed by seed."""
    options: dict[int, dict] = {}
    for path in EARLIER_JOBS:
        for job in report.load_jobs_module(path).JOBS:
            seen = dict(job.options)
            if options.setdefault(job.seed, seen) != seen:
                raise RuntimeError(f"seed {job.seed} of {path.parent.name} has two option sets")
    return options


def _check_design(ensembles: dict[str, list[Job]], earlier: dict[int, dict]) -> tuple[int, int]:
    """The card's design, checked on the jobs. Returns ``(pairs, size)``.

    Every configuration has the same passes and size, its own option (``chain``), and one block of
    consecutive seeds. The positive control is block 0. No two configurations share a seed. A seed
    of experiment 001 or 002 may be reused only with an identical option set: block 0 (001's
    img64) and 002's per_path_start (block 17) are the reuses. At the experiment's size the rule is
    checked for every job. At another size (a smoke run) it is not, because the option sets differ.
    """
    if set(ensembles) != set(CONFIGURATIONS):
        raise RuntimeError(f"ENSEMBLES must hold {CONFIGURATIONS}, got {sorted(ensembles)}")
    size = int(dict(ensembles[IMAGE][0].options)["size"])
    pairs = len(ensembles[IMAGE]) // 2
    chains = {
        IMAGE: "image",
        ROW: "row",
        **{name: f"lane:{length}" for name, length in zip(LADDER, LANE_LENGTHS, strict=True)},
    }
    all_seeds: list[int] = []
    for name in CONFIGURATIONS:
        jobs = ensembles[name]
        if len(jobs) != 2 * pairs:
            raise RuntimeError(f"{name}: expected {2 * pairs} jobs, got {len(jobs)}")
        options = {"chain": chains[name], "passes": PASSES, "size": size}
        if any(dict(job.options) != options for job in jobs):
            raise RuntimeError(f"{name}: every job must have options {options}")
        seeds = [job.seed for job in jobs]
        base = seeds[0]
        if seeds != list(range(base, base + 2 * pairs)) or base % BLOCK:
            raise RuntimeError(
                f"{name}: seeds must be consecutive, starting at a multiple of {BLOCK}"
            )
        if name == IMAGE and base != 0:
            raise RuntimeError("image must be block 0, the positive control of experiment 001")
        if size == EXPERIMENT_SIZE:
            for job in jobs:
                if job.seed in earlier and earlier[job.seed] != dict(job.options):
                    raise RuntimeError(
                        f"{name}: seed {job.seed} is used by experiment 001 or 002 "
                        "with other options"
                    )
        all_seeds.extend(seeds)
    if len(set(all_seeds)) != len(all_seeds):
        raise RuntimeError("seeds are not unique across configurations")
    return pairs, size


def _h1(runs: dict[str, list[dict]]) -> dict:
    """H1: ``all.pattern_corr`` is non-decreasing in L, over the adjacent steps of the ladder."""
    # The ladder ascends in L, so each step is (shorter, longer) and the longer one is tested.
    ladder = report.adjacent_tests(runs, LADDER, PATTERN_KEY, SIGNIFICANCE)
    tests = ladder["steps"]
    if ladder["significant_decreases"]:
        decision = "refuted"
    elif ladder["powered"]:
        decision = "supported"
    else:
        decision = "inconclusive"
    effects = {name: t["effect"] for name, t in tests.items()}
    return {
        "metric": PATTERN_KEY,
        "tests": tests,
        "holm_rejected_decrease": ladder["holm_rejected_less"],
        "holm_rejected_increase": ladder["holm_rejected_greater"],
        "significant_decreases": ladder["significant_decreases"],
        "significant_increases": ladder["significant_increases"],
        "powered": ladder["powered"],
        "largest_abs_rel_diff": report.largest_abs_rel_diff(effects),
        "largest_abs_cohen_d": report.largest_abs_cohen_d(effects),
        "decision": decision,
    }


def _h2(runs: dict[str, list[dict]]) -> dict:
    """H2: L* exists. Each lane length is tested against row, with Holm across the whole ladder."""
    tests = {
        name: report.directional_pair_test(
            runs[name], runs[ROW], PATTERN_KEY, SIGNIFICANCE, labels=(name, ROW)
        )
        for name in LADDER
    }
    less = ensemble.holm({name: t["p_less"] for name, t in tests.items()}, SIGNIFICANCE)
    powered = all(t["min_attainable_p"] <= SIGNIFICANCE / len(LADDER) for t in tests.values())
    kept = [length for length, name in zip(LANE_LENGTHS, LADDER, strict=True) if not less[name]]
    lstar = kept[0] if kept else None
    if not powered:
        decision = "inconclusive"
    elif lstar is None:
        decision = "refuted"
    else:
        decision = "supported"
    return {
        "metric": PATTERN_KEY,
        "tests": tests,
        "holm_rejected_less": less,
        "powered": powered,
        "lstar": lstar,
        "decision": decision,
    }


def _family_test(runs: dict[str, list[dict]], family: list[str], a: str, b: str) -> dict:
    """``compare_ensembles`` of ``a`` against ``b`` on the diffuse family, with the power check.

    An underpowered comparison is not run through ``compare_ensembles``: it has no rejections,
    and its verdict can be neither "indistinguishable" nor "refuted" (``report.family_test``).
    """
    return {
        "comparison": f"{a} vs {b}",
        **report.family_test(runs[a], runs[b], family, SIGNIFICANCE),
    }


def _h3(runs: dict[str, list[dict]], family: list[str]) -> dict:
    """H3: ``chain=row`` is indistinguishable from ``chain=image`` on the diffuse family."""
    test = _family_test(runs, family, ROW, IMAGE)
    if not test["powered"]:
        decision = "inconclusive"
    elif test["rejected_keys"]:
        decision = "refuted"
    else:
        decision = "supported"
    return {"test": test, "decision": decision}


def _curve(runs: dict[str, list[dict]]) -> dict[str, dict]:
    """Effect of every configuration against row, on the H2 curve keys."""
    return {
        name: ensemble.effect_summary(runs[name], runs[ROW], CURVE_KEYS)
        for name in (IMAGE, *LADDER, ROW)
    }


def _chains_per_pass() -> dict[str, int]:
    """Independent chains per pass at 1920 x 1080 (SPEC §3).

    ``image`` is one chain. ``row`` is one chain per row, so ``H``. ``lane:L`` is one chain per
    (row, lane), with ``ceil(W / L)`` lanes in each row, so ``H * ceil(W / L)``.
    """
    chains = {IMAGE: 1, ROW: TARGET_HEIGHT}
    for name, length in zip(LADDER, LANE_LENGTHS, strict=True):
        chains[name] = TARGET_HEIGHT * ((TARGET_WIDTH + length - 1) // length)
    return chains


def _decision_table(h1: dict, h2: dict, h3: dict) -> list[dict]:
    rows: list[dict] = [
        {"hypothesis": "H1", "comparison": "adjacent steps", "outcome": h1["decision"]}
    ]
    for test in h1["tests"].values():
        rows.append(
            {
                "hypothesis": "H1",
                "comparison": test["comparison"],
                "key": test["key"],
                "p_value_less": test["p_less"],
                "p_value_greater": test["p_greater"],
                "min_attainable_p": test["min_attainable_p"],
            }
        )
    rows.append(
        {"hypothesis": "H2", "comparison": "L*", "lstar": h2["lstar"], "outcome": h2["decision"]}
    )
    for name, test in h2["tests"].items():
        rows.append(
            {
                "hypothesis": "H2",
                "comparison": test["comparison"],
                "key": test["key"],
                "p_value_less": test["p_less"],
                "holm_rejected_less": h2["holm_rejected_less"][name],
                "min_attainable_p": test["min_attainable_p"],
            }
        )
    family = h3["test"]
    rows.append(
        {
            "hypothesis": "H3",
            "comparison": family["comparison"],
            "key": f"diffuse family, {family['n_keys']} keys",
            "min_attainable_p": family["min_attainable_p"],
            "outcome": h3["decision"],
        }
    )
    return rows


def _fmt(value: float | None, spec: str = ".4g") -> str:
    return "n/a" if value is None else format(value, spec)


def _print_h1(block: dict) -> None:
    n_steps = len(block["tests"])
    print(f"H1 {block['metric']}, adjacent steps, Holm over {n_steps}: {block['decision']}")
    for name, test in block["tests"].items():
        effect = test["effect"]
        print(
            f"  {name}: diff={_fmt(effect['diff'])} rel={_fmt(effect['rel_diff'])} "
            f"d={_fmt(effect['cohen_d'])} p_less={test['p_less']:.6g} "
            f"p_greater={test['p_greater']:.6g} min_attainable_p={test['min_attainable_p']:.3g}"
        )
    print(f"  significant decreases: {block['significant_decreases']}")
    print(f"  significant increases: {block['significant_increases']}")


def _print_h2(block: dict) -> None:
    print(f"H2 L* = {block['lstar']} (smallest L not rejected vs row): {block['decision']}")
    for length, name in zip(LANE_LENGTHS, LADDER, strict=True):
        test = block["tests"][name]
        print(
            f"  L={length}: p_less={test['p_less']:.6g} "
            f"holm_rejected={block['holm_rejected_less'][name]} "
            f"min_attainable_p={test['min_attainable_p']:.3g}"
        )


def _print_curve(curve: dict[str, dict]) -> None:
    for key in CURVE_KEYS:
        print(f"curve {key} vs {ROW}: mean sd rel d")
        for name, summary in curve.items():
            s = summary[key]
            print(
                f"  {name:>9}: {s['mean_a']:.6g} {s['sd_a']:.4g} "
                f"rel={_fmt(s['rel_diff'])} d={_fmt(s['cohen_d'])}"
            )


def _print_h3(block: dict) -> None:
    test = block["test"]
    rejected = test["rejected_keys"]
    count = "underpowered (not run)" if rejected is None else f"rejected={len(rejected)}"
    largest = test["largest_abs_rel_diff"]
    cohen = test["largest_abs_cohen_d"]
    print(
        f"H3 {test['comparison']}: keys={test['n_keys']} {count} "
        f"min_attainable_p={test['min_attainable_p']:.3g} "
        f"threshold={test['holm_first_threshold']:.3g} "
        f"largest |rel|={_fmt(None if largest is None else largest['value'])} "
        f"({None if largest is None else largest['key']}) "
        f"largest |d|={_fmt(None if cohen is None else cohen['value'])} "
        f"({None if cohen is None else cohen['key']}) -> {block['decision']}"
    )


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    ensembles = report.load_jobs_module(args.jobs).ENSEMBLES
    pairs, size = _check_design(ensembles, _earlier_options())
    reference8 = read_ppm(args.reference)
    if reference8.shape != (size, size, 3):
        raise RuntimeError(f"reference must be {size} x {size} x 3, got {reference8.shape}")

    first = {name: load(jobs[0]) for name, jobs in ensembles.items()}
    pass_counts = {render.passes for render in first.values()}
    if pass_counts != {PASSES}:
        raise RuntimeError(
            f"configurations must all have passes={PASSES}, got {sorted(pass_counts)}"
        )
    object_id = first[IMAGE].object_id
    for name, render in first.items():
        if not np.array_equal(render.object_id, object_id):
            raise RuntimeError(f"object id of {name} differs from {IMAGE}")
    measure_map = report.diffuse_only(object_id, DIFFUSE_REGION_IDS)
    masks = metrics.region_masks(measure_map, ERODE_RADIUS)
    measured = [r for r in DIFFUSE_REGION_IDS if r in masks]
    absent = [r for r in DIFFUSE_REGION_IDS if r not in masks]

    raw = {
        name: report.ensemble_metrics(jobs, reference8, DIFFUSE_REGION_IDS, object_id=object_id)
        for name, jobs in ensembles.items()
    }
    keys = sorted(raw[IMAGE][0])
    for name, metric_runs in raw.items():
        if any(sorted(run) != keys for run in metric_runs):
            raise RuntimeError(f"metric keys of {name} differ")
    missing = [key for key in CURVE_KEYS if key not in keys]
    if missing:
        raise RuntimeError(f"keys not measured: {missing}")
    family = metrics.diffuse_key_family(keys)
    if not family:
        raise RuntimeError("the diffuse key family is empty")

    h1 = _h1(raw)
    h2 = _h2(raw)
    h3 = _h3(raw, family)
    curve = _curve(raw)
    chains = _chains_per_pass()

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    ab8 = {name: report.ab8_of_pair(jobs) for name, jobs in ensembles.items()}
    previews = {name: report.block_preview(img, PREVIEW_FACTOR) for name, img in ab8.items()}
    previews["reference"] = report.block_preview(reference8, PREVIEW_FACTOR)
    grid_name = "fig_grid.png"
    grid = report.mosaic({name: previews[name] for name in GRID_ORDER}, len(GRID_LAYOUT[0]))
    write_png(out_dir / grid_name, grid)
    figures = {grid_name: (out_dir / grid_name).stat().st_size}

    results = {
        "experiment": EXPERIMENT,
        "significance": SIGNIFICANCE,
        "size": size,
        "passes": PASSES,
        "pairs": pairs,
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
        "chains_per_pass_1920x1080": chains,
        "h1": h1,
        "h2": h2,
        "h3": h3,
        "curve": {"keys": list(CURVE_KEYS), "effect_summary": curve},
        "decision_table": _decision_table(h1, h2, h3),
        "grid": {
            "file": grid_name,
            "preview_px": int(previews[IMAGE].shape[0]),
            "layout": [list(row) for row in GRID_LAYOUT],
        },
        "figures": figures,
    }
    report.write_results_json(out_dir / "results.json", results)

    print(f"keys measured={len(keys)} diffuse family={len(family)}; passes={PASSES}; pairs={pairs}")
    print(f"measured regions {measured}, absent {absent}")
    _print_h1(h1)
    _print_h2(h2)
    _print_curve(curve)
    _print_h3(h3)
    print("chains per pass at 1920 x 1080: " + ", ".join(f"{k}={v}" for k, v in chains.items()))
    print(f"figures (bytes): {figures}")
    print(f"wrote {out_dir / 'results.json'}")


if __name__ == "__main__":
    main()
