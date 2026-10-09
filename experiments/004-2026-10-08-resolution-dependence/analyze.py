"""Analysis of experiment 004 (T1.9): is the texture pixel-locked? Resolution and jitter units.

Re-runs from the render cache, so every render must already exist (``jobs.py``). Writes
``results.json`` and ``fig_grid.png`` to the output directory and prints the tables. Deterministic:
every test is an exact permutation test, and no random number is drawn.

``--pairs``, ``--scale``, ``--reference`` and ``--out-dir`` exist to validate this script on a
smaller subset in a scratch cache. ``--pairs 2 --scale 4`` gives sizes 50, 100 and 200 (the smoke
run; region 2 erodes at 50 px, see README D6). ``--pairs 2 --scale 2`` gives sizes 100, 200 and 400,
where all six diffuse regions are measured at every size. The defaults are the experiment.
"""

import argparse
from collections.abc import Iterable
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
from painterly_analysis import (
    DIFFUSE_REGION_IDS,
    ensemble,
    metrics,
    read_ppm,
    report,
    smallpaint_display,
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
# on purpose: the positive control s400 is experiment 001's img64.
EARLIER_JOBS = (
    REPO_ROOT / "experiments" / "001-2026-10-08-oracle-reproduction" / "jobs.py",
    REPO_ROOT / "experiments" / "002-2026-10-08-ingredient-ablation" / "jobs.py",
    REPO_ROOT / "experiments" / "003-2026-10-08-lane-length" / "jobs.py",
)
IMG64 = "img64"  # experiment 001's name of the ensemble that s400 must reproduce at full scale

# Family-wise level of every decision (README, Method). It is not the oracle option `alpha`.
SIGNIFICANCE = 0.01
PASSES = 64  # P of every configuration (jobs.py)
PAIRS = 8  # pairs per configuration in the experiment (jobs.py)
BLOCK = 16  # seeds per configuration: 8 pairs x 2 half renders (jobs.py)
ERODE_RADIUS = HIGHPASS_SIZE // 2  # metrics.measure default: half-width of the high-pass box
REFERENCE_SIZE = 400  # the native reference (GUI scene)
PREVIEW_SIDE = 200  # side in pixels of each figure tile, whatever the render size

# Native size and seed block of each configuration (README, Method). The jobs must match them.
# The row_ configurations are the artist-mode chain (H1d). row_s400 is experiment 003's row.
NATIVE_SIZE = {
    "s200": 200,
    "s400": 400,
    "s800": 800,
    "s800_j1400": 800,
    "row_s200": 200,
    "row_s400": 400,
    "row_s800": 800,
}
SEED_BLOCK = {
    "s200": 28,
    "s400": 0,
    "s800": 29,
    "s800_j1400": 30,
    "row_s200": 31,
    "row_s400": 27,
    "row_s800": 32,
}
POSITIVE = "s400"  # the positive control: experiment 001's img64
SIZE_PAIRS = (("s200", "s400"), ("s400", "s800"), ("s200", "s800"))  # H1a: every pair of sizes
ROW_SIZE_PAIRS = (  # H1d: the same size pairs on the row chain
    ("row_s200", "row_s400"),
    ("row_s400", "row_s800"),
    ("row_s200", "row_s800"),
)
JITTER_PAIR = ("s800", "s800_j1400")  # H2
# H1b: box-downsampled 2 x 2 to the native size of POSITIVE, then compared with it.
DOWNSAMPLED = "s800"
FIG_LAYOUT = (
    ("s200", "s400", "s800"),
    ("s800_j1400", "downsampled", "reference"),
)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analysis of experiment 004 (T1.9).")
    parser.add_argument(
        "--jobs",
        type=Path,
        default=DEFAULT_JOBS,
        help="jobs file defining build_ensembles (default: this experiment's jobs.py)",
    )
    parser.add_argument(
        "--reference",
        type=Path,
        default=DEFAULT_REFERENCE,
        help=(
            "reference PPM, at the native size divided by --scale "
            "(default: the 400 px GUI reference)"
        ),
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=EXP_DIR,
        help="directory for results.json and the figure (default: this directory)",
    )
    parser.add_argument(
        "--pairs",
        type=int,
        default=PAIRS,
        help="pairs per configuration (default: the experiment's 8; smoke runs use 2)",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=1,
        help=(
            "divide every native size by this (default: 1, the experiment; smoke runs use 4, "
            "or 2 for sizes 100, 200 and 400)"
        ),
    )
    return parser.parse_args(argv)


def _expected_options(name: str, size: int, jitter: float) -> dict[str, object]:
    """The oracle options of a configuration (README, Method). The jitter default is not passed."""
    chain = "row" if name.startswith("row_") else "image"
    options: dict[str, object] = {"chain": chain, "passes": PASSES, "size": size}
    if name == "s800_j1400":
        options["jitter"] = jitter
    return options


def _check_design(
    ensembles: dict[str, list[Job]],
    pairs: int,
    scale: int,
    earlier_jobs: list[Job],
    jitter: float,
) -> None:
    """The README's design, checked on the jobs. Raises RuntimeError on any mismatch.

    Every configuration has its expected options, one block of consecutive seeds at its block, and
    no seed shared with another configuration. The positive control s400 is block 0. At full scale
    its options equal those of experiment 001's ``img64``, so its renders are the cached ones. At
    full scale a seed of experiments 001-003 may be reused only with an identical option set (the
    row_s400 reuse of experiment 003's row). At smoke scale (``scale > 1``) that check is not made,
    because the option sets differ from the earlier experiments by size.
    """
    if set(ensembles) != set(NATIVE_SIZE):
        raise RuntimeError(f"ENSEMBLES must hold {sorted(NATIVE_SIZE)}, got {sorted(ensembles)}")
    earlier: dict[int, dict] = {}
    for job in earlier_jobs:
        seen = dict(job.options)
        if earlier.setdefault(job.seed, seen) != seen:
            raise RuntimeError(f"seed {job.seed} of an earlier experiment has two option sets")
    img64_options = {job.options for job in earlier_jobs if job.name == IMG64}
    all_seeds: list[int] = []
    for name, native in NATIVE_SIZE.items():
        jobs = ensembles[name]
        options = _expected_options(name, native // scale, jitter)
        if len(jobs) != 2 * pairs:
            raise RuntimeError(f"{name}: expected {2 * pairs} jobs, got {len(jobs)}")
        if any(dict(job.options) != options for job in jobs):
            raise RuntimeError(f"{name}: every job must have options {options}")
        seeds = [job.seed for job in jobs]
        base = seeds[0]
        if seeds != list(range(base, base + 2 * pairs)) or base != BLOCK * SEED_BLOCK[name]:
            raise RuntimeError(
                f"{name}: seeds must be consecutive from {BLOCK * SEED_BLOCK[name]}, got {base}"
            )
        if name == POSITIVE and scale == 1 and {job.options for job in jobs} != img64_options:
            raise RuntimeError(f"{name}: options must equal experiment 001's {IMG64}")
        if scale == 1:
            for job in jobs:
                if job.seed in earlier and earlier[job.seed] != dict(job.options):
                    raise RuntimeError(
                        f"{name}: seed {job.seed} is used by an earlier experiment "
                        "with other options"
                    )
        all_seeds.extend(seeds)
    if len(set(all_seeds)) != len(all_seeds):
        raise RuntimeError("seeds are not unique across configurations")


def _masked_cov(x, y, mask) -> float:
    """Population covariance of x and y over the pixels where mask is true, each centred by its own
    masked mean."""
    n = int(jnp.sum(mask))
    if n == 0:
        raise ValueError("mask selects no pixels")
    mean_x = jnp.sum(jnp.where(mask, x, 0.0)) / n
    mean_y = jnp.sum(jnp.where(mask, y, 0.0)) / n
    dx = jnp.where(mask, x - mean_x, 0.0)
    dy = jnp.where(mask, y - mean_y, 0.0)
    return float(jnp.sum(dx * dy) / n)


def _noise_corrected_lag1(hp_a, hp_b, mask, axis: int) -> float:
    """Lag-1 autocorrelation of the structure shared by two independent half renders, dimensionless.

    The halves share the structure and have independent noise. The covariance of ``a[p]`` and
    ``b[p + 1]`` (one step along ``axis``, both pixels in mask) estimates the structure's lag-1
    covariance. The covariance of ``a`` and ``b`` over mask estimates the structure's variance.
    Their ratio is the structure's lag-1 autocorrelation, free of the noise-to-structure ratio.
    """
    a = jnp.asarray(hp_a, dtype=jnp.float64)
    b = jnp.asarray(hp_b, dtype=jnp.float64)
    m = jnp.asarray(mask, dtype=bool)
    if axis == 0:
        x, y, pair = a[:-1], b[1:], m[:-1] & m[1:]
    elif axis == 1:
        x, y, pair = a[:, :-1], b[:, 1:], m[:, :-1] & m[:, 1:]
    else:
        raise ValueError("axis must be 0 or 1")
    return _masked_cov(x, y, pair) / _masked_cov(a, b, m)


def _reference_free(
    sum_a, sum_b, passes: int, object_id: np.ndarray, regions: Iterable[int]
) -> dict[str, float]:
    """Reference-free look metrics of one pair of half renders, at the render's own size.

    The definitions are those of ``metrics.measure`` (display, high-pass, erosion, diffuse regions),
    without the reference, plus the noise-corrected lag-1 of the structure (``slag1``). Keys are
    ``r{id}.mean.{R,G,B}``, ``r{id}.structure_std``, ``r{id}.lag1.{x,y}``, ``r{id}.slag1.{x,y}``,
    ``r{id}.spectral_slope``, ``all.clip_fraction`` and ``all.spectral_slope``. ``object_id`` is the
    map whose ids select the masks, and ``regions`` are the ids measured.
    """
    a8 = smallpaint_display(sum_a, passes)
    b8 = smallpaint_display(sum_b, passes)
    ab8 = smallpaint_display(np.asarray(sum_a) + np.asarray(sum_b), 2 * passes)
    hp_a = metrics.highpass(metrics.luminance(a8), HIGHPASS_SIZE)
    hp_b = metrics.highpass(metrics.luminance(b8), HIGHPASS_SIZE)
    hp_ab = metrics.highpass(metrics.luminance(ab8), HIGHPASS_SIZE)
    masks = metrics.region_masks(report.diffuse_only(object_id, regions), ERODE_RADIUS)
    if not masks:
        raise ValueError("no diffuse region survives erosion")
    out: dict[str, float] = {}
    for region, mask in masks.items():
        prefix = f"r{region}"
        mean = metrics.region_mean_rgb(ab8, mask)
        for channel, name in enumerate("RGB"):
            out[f"{prefix}.mean.{name}"] = float(mean[channel])
        out[f"{prefix}.structure_std"] = float(metrics.structure_std(hp_a, hp_b, mask))
        out[f"{prefix}.lag1.x"] = float(metrics.lag1_autocorrelation(hp_ab, mask, axis=1))
        out[f"{prefix}.lag1.y"] = float(metrics.lag1_autocorrelation(hp_ab, mask, axis=0))
        out[f"{prefix}.slag1.x"] = _noise_corrected_lag1(hp_a, hp_b, mask, axis=1)
        out[f"{prefix}.slag1.y"] = _noise_corrected_lag1(hp_a, hp_b, mask, axis=0)
        out[f"{prefix}.spectral_slope"] = float(metrics.radial_spectral_slope(hp_ab, mask))
    union = jnp.any(jnp.stack(list(masks.values())), axis=0)
    out["all.clip_fraction"] = float(metrics.clip_fraction(ab8))
    out["all.spectral_slope"] = float(metrics.radial_spectral_slope(hp_ab, union))
    return out


def _reference_free_ensemble(
    jobs: list[Job], object_id: np.ndarray, regions: Iterable[int]
) -> list[dict[str, float]]:
    """``_reference_free`` for each consecutive pair of jobs, in order. Every render must share the
    configuration's object id map, which is checked here."""
    results: list[dict[str, float]] = []
    for first, second in zip(jobs[0::2], jobs[1::2], strict=True):
        a = load(first)
        b = load(second)
        for render in (a, b):
            if render.passes != PASSES:
                raise ValueError(f"{first.name!r}: passes must be {PASSES}, got {render.passes}")
            if not np.array_equal(render.object_id, object_id):
                raise ValueError(f"{first.name!r}: object id differs from its configuration's")
        results.append(_reference_free(a.sum, b.sum, PASSES, object_id, regions))
    return results


def _box_down(sum_: np.ndarray) -> np.ndarray:
    """2 x 2 box downsampling of a sum array: the mean of each 2 x 2 block of per-pixel sums.

    The mean keeps the units of a native sum (per pixel, summed over passes), so
    ``smallpaint_display`` applies unchanged.
    """
    s = np.asarray(sum_, dtype=np.float64)
    h, w, c = s.shape
    if h % 2 or w % 2:
        raise ValueError(f"side must be even to downsample by 2, got {h} x {w}")
    return s.reshape(h // 2, 2, w // 2, 2, c).mean(axis=(1, 3))


def _downsampled_ensemble(
    jobs: list[Job], ref8: np.ndarray, object_id: np.ndarray
) -> list[dict[str, float]]:
    """``metrics.measure`` for each pair after 2 x 2 box downsampling of the sums (README, Method).

    The reference and the object id map are at the native size of the comparison.
    """
    results: list[dict[str, float]] = []
    for first, second in zip(jobs[0::2], jobs[1::2], strict=True):
        a = load(first)
        b = load(second)
        if a.passes != b.passes:
            raise ValueError(f"pair {first.name!r}: passes differ")
        results.append(
            metrics.measure(_box_down(a.sum), _box_down(b.sum), a.passes, ref8, object_id)
        )
    return results


def _reference_free_downsampled(
    jobs: list[Job], object_id: np.ndarray, regions: Iterable[int]
) -> list[dict[str, float]]:
    """``_reference_free`` for each pair after 2 x 2 box downsampling of the sums (README, H1b).

    The masks come from ``object_id``, the native 400 px map, so both sides of H1b use the same
    regions. The object id of the 800 px renders was checked by ``_reference_free_ensemble``.
    """
    results: list[dict[str, float]] = []
    for first, second in zip(jobs[0::2], jobs[1::2], strict=True):
        a = load(first)
        b = load(second)
        if a.passes != PASSES or b.passes != PASSES:
            raise ValueError(f"pair {first.name!r}: passes must be {PASSES}")
        results.append(
            _reference_free(_box_down(a.sum), _box_down(b.sum), PASSES, object_id, regions)
        )
    return results


def _downsampled_ab8(jobs: list[Job]) -> np.ndarray:
    """``ab8`` of pair 0 with each half render box-downsampled 2 x 2 before the sum (H1b)."""
    first, second = load(jobs[0]), load(jobs[1])
    return smallpaint_display(
        _box_down(first.sum) + _box_down(second.sum), first.passes + second.passes
    )


def _family_test(
    x_runs: list[dict], y_runs: list[dict], family: list[str], alpha: float, label: str
) -> dict:
    """``compare_ensembles`` of two ensembles on a key family, with the power check.

    An underpowered comparison is not run through ``compare_ensembles`` (``report.family_test``).
    """
    return {"comparison": label, **report.family_test(x_runs, y_runs, family, alpha)}


def _size_comparisons(
    runs: dict[str, list[dict]], family: list[str], pairs: tuple[tuple[str, str], ...]
) -> dict:
    """The noise-corrected lag-1 keys compared across size pairs, at alpha = 0.01 / len(pairs).

    H1a uses ``SIZE_PAIRS`` (image chain). H1d uses ``ROW_SIZE_PAIRS`` (row chain). The decision is
    the same for both: refuted iff some key is rejected in some pair, supported iff no key is
    rejected and every pair is powered, otherwise inconclusive.
    """
    level = SIGNIFICANCE / len(pairs)
    tests = {
        f"{a} vs {b}": _family_test(runs[a], runs[b], family, level, f"{a} vs {b}")
        for a, b in pairs
    }
    rejected = {name: t["rejected_keys"] for name, t in tests.items() if t["rejected_keys"]}
    powered = all(t["powered"] for t in tests.values())
    if rejected:
        decision = "refuted"
    elif powered:
        decision = "supported"
    else:
        decision = "inconclusive"
    return {
        "family": family,
        "level_per_pair": level,
        "tests": tests,
        "rejected": rejected,
        "powered": powered,
        "decision": decision,
    }


def _h1b(down: list[dict], native: list[dict], family: list[str]) -> dict:
    """H1b, one-sided (the amendment before rendering, Opus M1 review 3).

    The 800 px ensemble, box-downsampled to 400 px, against native 400 px on the noise-corrected
    lag-1 keys. For each key, ``p_less`` is the p-value of "downsampled is lower" and ``p_greater``
    that of "downsampled is higher". Holm runs across the keys in each direction at SIGNIFICANCE.

    Supported (pixel-locked) iff at least one key is rejected "less" and none "greater". Refuted
    (world-locked) iff at least one key is rejected "greater" and none "less". Otherwise
    inconclusive. An underpowered comparison, whose smallest attainable one-sided p exceeds
    SIGNIFICANCE / len(family), is inconclusive.
    """
    p_less = {
        key: report.pair_test(down, native, key, "less", SIGNIFICANCE)["p_value"] for key in family
    }
    p_greater = {
        key: report.pair_test(down, native, key, "greater", SIGNIFICANCE)["p_value"]
        for key in family
    }
    holm_less = ensemble.holm(p_less, SIGNIFICANCE)
    holm_greater = ensemble.holm(p_greater, SIGNIFICANCE)
    threshold = SIGNIFICANCE / len(family)
    min_p = ensemble.min_attainable_pvalue(len(down), len(native), "less")
    powered = min_p <= threshold
    rejected_less = [key for key in family if holm_less[key]]
    rejected_greater = [key for key in family if holm_greater[key]]
    if not powered:
        decision = "inconclusive"
    elif rejected_less and not rejected_greater:
        decision = "supported"
    elif rejected_greater and not rejected_less:
        decision = "refuted"
    else:
        decision = "inconclusive"
    summary = ensemble.effect_summary(down, native, family)
    test = {
        "comparison": "downsampled 800 vs native 400",
        "n_keys": len(family),
        "alpha": SIGNIFICANCE,
        "min_attainable_p": min_p,
        "holm_first_threshold": threshold,
        "powered": powered,
        "p_less": p_less,
        "p_greater": p_greater,
        "holm_rejected_less": rejected_less,
        "holm_rejected_greater": rejected_greater,
        "effect_summary": summary,
        "largest_abs_rel_diff": report.largest_abs_rel_diff(summary),
        "largest_abs_cohen_d": report.largest_abs_cohen_d(summary),
    }
    return {"test": test, "decision": decision}


def _h2(runs: dict[str, list[dict]], family: list[str]) -> dict:
    """H2: jitter 1/700 and 1/1400 at 800 px are distinguishable on the lag-1 and structure keys."""
    a, b = JITTER_PAIR
    test = _family_test(runs[a], runs[b], family, SIGNIFICANCE, f"{a} vs {b}")
    if not test["powered"]:
        decision = "inconclusive"
    elif test["rejected_keys"]:
        decision = "supported"
    else:
        decision = "refuted"
    return {"test": test, "decision": decision}


def _h1(h1a: dict, h1b: dict) -> str:
    """H1 is supported iff H1a and H1b are both supported. It is refuted iff either is refuted."""
    decisions = (h1a["decision"], h1b["decision"])
    if "refuted" in decisions:
        return "refuted"
    if decisions == ("supported", "supported"):
        return "supported"
    return "inconclusive"


def _summary_table(runs: dict[str, list[dict]], keys: list[str]) -> dict[str, dict]:
    """Mean and sample sd of each key, per configuration."""
    table: dict[str, dict] = {}
    for name, metric_runs in runs.items():
        table[name] = {}
        for key in keys:
            values = np.asarray([run[key] for run in metric_runs], dtype=np.float64)
            table[name][key] = {
                "mean": float(np.mean(values)),
                "sd": float(np.std(values, ddof=1)),
            }
    return table


def _preview(img8: np.ndarray) -> np.ndarray:
    """A PREVIEW_SIDE x PREVIEW_SIDE tile of a display image, by JAX's antialiased linear resize."""
    x = jnp.asarray(img8, dtype=jnp.float64)
    y = jax.image.resize(x, (PREVIEW_SIDE, PREVIEW_SIDE, 3), method="linear")
    return np.asarray(jnp.clip(jnp.round(y), 0.0, 255.0)).astype(np.uint8)


def _fmt(value: float | None, spec: str = ".4g") -> str:
    return "n/a" if value is None else format(value, spec)


def _print_test(test: dict) -> None:
    rejected = test["rejected_keys"]
    count = "underpowered (not run)" if rejected is None else f"rejected={len(rejected)}"
    largest = test["largest_abs_rel_diff"]
    cohen = test["largest_abs_cohen_d"]
    print(
        f"  {test['comparison']}: keys={test['n_keys']} {count} "
        f"min_attainable_p={test['min_attainable_p']:.3g} "
        f"threshold={test['holm_first_threshold']:.3g} "
        f"largest |rel|={_fmt(None if largest is None else largest['value'])} "
        f"({None if largest is None else largest['key']}) "
        f"largest |d|={_fmt(None if cohen is None else cohen['value'])} "
        f"({None if cohen is None else cohen['key']})"
    )
    if rejected:
        print(f"    rejected keys: {rejected}")


def _print_h1b(test: dict) -> None:
    print(
        f"  {test['comparison']}: keys={test['n_keys']} "
        f"min_attainable_p={test['min_attainable_p']:.3g} "
        f"threshold={test['holm_first_threshold']:.3g} powered={test['powered']}"
    )
    print(f"    rejected less: {test['holm_rejected_less']}")
    print(f"    rejected greater: {test['holm_rejected_greater']}")


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.pairs < 1 or args.scale < 1:
        raise ValueError("--pairs and --scale must be >= 1")
    jobs_module = report.load_jobs_module(args.jobs)
    ensembles = jobs_module.build_ensembles(args.pairs, args.scale)
    earlier_jobs = [job for path in EARLIER_JOBS for job in report.load_jobs_module(path).JOBS]
    _check_design(ensembles, args.pairs, args.scale, earlier_jobs, jobs_module.JITTER_TUNED)

    native_ref = REFERENCE_SIZE // args.scale
    reference8 = read_ppm(args.reference)
    if reference8.shape != (native_ref, native_ref, 3):
        raise RuntimeError(
            f"reference must be {native_ref} x {native_ref} x 3, got {reference8.shape}"
        )

    object_ids = {name: load(jobs[0]).object_id for name, jobs in ensembles.items()}
    by_size: dict[int, list[str]] = {}
    for name, native in NATIVE_SIZE.items():
        by_size.setdefault(native, []).append(name)
    for names in by_size.values():
        for name in names[1:]:
            if not np.array_equal(object_ids[name], object_ids[names[0]]):
                raise RuntimeError(f"object id of {name} differs from {names[0]}")
    measured_by = {
        name: sorted(
            metrics.region_masks(report.diffuse_only(oid, DIFFUSE_REGION_IDS), ERODE_RADIUS)
        )
        for name, oid in object_ids.items()
    }
    if args.scale == 1:
        # The experiment: every configuration must measure the same regions, or the keys differ.
        measured = measured_by[POSITIVE]
        if any(regions != measured for regions in measured_by.values()):
            raise RuntimeError(
                f"measured diffuse regions differ between configurations: {measured_by}"
            )
    else:
        # Smoke scale only (README D6): erosion can remove a region at a small size, so the
        # comparisons use the regions measured in every configuration.
        measured = sorted(set.intersection(*(set(regions) for regions in measured_by.values())))
        if not measured:
            raise RuntimeError("no diffuse region is measured in every configuration")
    absent = sorted(set(DIFFUSE_REGION_IDS) - set().union(*measured_by.values()))
    dropped = sorted(set().union(*measured_by.values()) - set(measured))

    runs = {
        name: _reference_free_ensemble(ensembles[name], object_ids[name], measured)
        for name in NATIVE_SIZE
    }
    keys = sorted(runs[POSITIVE][0])
    for name, metric_runs in runs.items():
        if any(sorted(run) != keys for run in metric_runs):
            raise RuntimeError(f"reference-free keys of {name} differ")
    family = metrics.diffuse_key_family(keys)
    lag1_corr = [key for key in family if ".slag1." in key]
    lag1_raw = [key for key in family if ".lag1." in key]
    structure = [key for key in family if key.endswith(".structure_std")]
    if len(lag1_corr) != 2 * len(measured):
        raise RuntimeError(f"expected {2 * len(measured)} noise-corrected lag-1 keys")

    # H1b: the noise-corrected keys of the downsampled ensemble, against those of native 400 px.
    down_runs = _reference_free_downsampled(ensembles[DOWNSAMPLED], object_ids[POSITIVE], measured)
    if sorted(down_runs[0]) != keys:
        raise RuntimeError("reference-free keys of the downsampled ensemble differ")
    # Descriptive only (README D7): metrics.measure keys, noise-confounded, never tested.
    native = report.ensemble_metrics(
        ensembles[POSITIVE], reference8, measured, object_id=object_ids[POSITIVE]
    )
    down = _downsampled_ensemble(
        ensembles[DOWNSAMPLED], reference8, report.diffuse_only(object_ids[POSITIVE], measured)
    )
    ds_keys = sorted(native[0])
    if sorted(down[0]) != ds_keys:
        raise RuntimeError("keys of the downsampled and native ensembles differ")
    ds_family = [key for key in metrics.diffuse_key_family(ds_keys) if key != "all.block_rmse"]
    ds_effects = ensemble.effect_summary(down, native, ds_family)

    h1a = _size_comparisons(runs, lag1_corr, SIZE_PAIRS)
    h1d = _size_comparisons(runs, lag1_corr, ROW_SIZE_PAIRS)
    h1b = _h1b(down_runs, runs[POSITIVE], lag1_corr)
    h1 = {"decision": _h1(h1a, h1b), "H1a": h1a, "H1b": h1b}
    h2 = _h2(runs, lag1_raw + lag1_corr + structure)
    raw_lag1_effects = {
        f"{a} vs {b}": ensemble.effect_summary(runs[a], runs[b], lag1_raw) for a, b in SIZE_PAIRS
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    tiles = {name: _preview(report.ab8_of_pair(jobs)) for name, jobs in ensembles.items()}
    tiles["downsampled"] = _preview(_downsampled_ab8(ensembles[DOWNSAMPLED]))
    tiles["reference"] = _preview(reference8)
    grid_name = "fig_grid.png"
    grid = report.mosaic(
        {name: tiles[name] for row in FIG_LAYOUT for name in row}, len(FIG_LAYOUT[0])
    )
    write_png(out_dir / grid_name, grid)

    results = {
        "experiment": EXPERIMENT,
        "significance": SIGNIFICANCE,
        "pairs": args.pairs,
        "scale": args.scale,
        "passes": PASSES,
        "reference_size": native_ref,
        "highpass_size": HIGHPASS_SIZE,
        "erosion_radius": ERODE_RADIUS,
        "regions": {
            "diffuse_ids": list(DIFFUSE_REGION_IDS),
            "measured": measured,
            "absent": absent,
            "dropped_at_this_scale": dropped,
        },
        "object_id_values": {
            name: sorted(int(v) for v in np.unique(oid)) for name, oid in object_ids.items()
        },
        "configurations": {
            name: {
                "size": NATIVE_SIZE[name] // args.scale,
                "options": dict(jobs[0].options),
                "seeds": [job.seed for job in jobs],
            }
            for name, jobs in ensembles.items()
        },
        "key_families": {
            "reference_free": family,
            "downsample_verdict": lag1_corr,
            "downsample_descriptive": ds_family,
            "lag1_noise_corrected": lag1_corr,
            "lag1_raw": lag1_raw,
            "structure_std": structure,
        },
        "hypotheses": {"H1": h1, "H1d": h1d, "H2": h2},
        "raw_lag1_effects": raw_lag1_effects,
        "downsample_effects": ds_effects,
        "summary": _summary_table(runs, family),
        "grid": {
            "file": grid_name,
            "tile_px": PREVIEW_SIDE,
            "layout": [list(r) for r in FIG_LAYOUT],
        },
    }
    report.write_results_json(out_dir / "results.json", results)

    print(
        f"keys: reference-free={len(family)} downsample={len(ds_family)}; "
        f"pairs={args.pairs}; scale={args.scale}"
    )
    print(f"measured regions {measured}, absent {absent}, dropped at this scale {dropped}")
    print(
        "H1a noise-corrected lag-1 across sizes, "
        f"level {h1a['level_per_pair']:.4g} per pair: {h1a['decision']}"
    )
    for test in h1a["tests"].values():
        _print_test(test)
    print(
        "H1d row chain, noise-corrected lag-1 across sizes, "
        f"level {h1d['level_per_pair']:.4g} per pair: {h1d['decision']}"
    )
    for test in h1d["tests"].values():
        _print_test(test)
    print(f"H1b downsampled 800 vs native 400, one-sided: {h1b['decision']}")
    _print_h1b(h1b["test"])
    largest = report.largest_abs_rel_diff(ds_effects)
    print(
        "  descriptive, untested (noise-confounded, README D7): "
        f"largest |rel|={_fmt(None if largest is None else largest['value'])} "
        f"({None if largest is None else largest['key']})"
    )
    print(f"H1 {h1['decision']} (H1a and H1b; H1d is reported separately)")
    print(f"H2 jitter 1/700 vs 1/1400 at 800 px: {h2['decision']}")
    _print_test(h2["test"])
    print(f"wrote {out_dir / 'results.json'} and {out_dir / grid_name}")


if __name__ == "__main__":
    main()
