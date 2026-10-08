"""Analysis of experiment 004 (T1.9): is the texture pixel-locked? Resolution and jitter units.

Re-runs from the render cache, so every render must already exist (``jobs.py``). Writes
``results.json`` and ``fig_grid.png`` to the output directory and prints the tables. Deterministic:
every test is an exact permutation test, and no random number is drawn.

``--pairs``, ``--scale``, ``--reference`` and ``--out-dir`` exist to validate this script on a
smaller subset in a scratch cache (``--pairs 2 --scale 2`` gives sizes 100, 200 and 400). The
defaults are the experiment.
"""

import argparse
import importlib.util
import json
import math
from pathlib import Path
from types import ModuleType

import jax
import jax.numpy as jnp
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
HIGHPASS_SIZE = 9  # metrics.measure default
ERODE_RADIUS = HIGHPASS_SIZE // 2  # metrics.measure default: half-width of the high-pass box
REFERENCE_SIZE = 400  # the native reference (GUI scene)
JITTER_TUNED = 1.0 / 1400.0  # s800_j1400 (jobs.py). The default 1/700 is not passed as an option.
PREVIEW_SIDE = 200  # side in pixels of each figure tile, whatever the render size

# Native size and seed block of each configuration (README, Method). The jobs must match them.
NATIVE_SIZE = {"s200": 200, "s400": 400, "s800": 800, "s800_j1400": 800}
SEED_BLOCK = {"s200": 28, "s400": 0, "s800": 29, "s800_j1400": 30}
POSITIVE = "s400"  # the positive control: experiment 001's img64
SIZE_PAIRS = (("s200", "s400"), ("s400", "s800"), ("s200", "s800"))  # H1a: every pair of sizes
JITTER_PAIR = ("s800", "s800_j1400")  # H2
DOWNSAMPLED = (
    "s800"  # H1b: box-downsampled 2 x 2 to the native size of POSITIVE, then compared with it
)
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
        help="divide every native size by this (default: 1, the experiment; smoke runs use 4)",
    )
    return parser.parse_args(argv)


def _load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"jobs_{path.parent.name}", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _expected_options(name: str, size: int) -> dict[str, object]:
    """The oracle options of a configuration (README, Method). The jitter default is not passed."""
    options: dict[str, object] = {"chain": "image", "passes": PASSES, "size": size}
    if name == "s800_j1400":
        options["jitter"] = JITTER_TUNED
    return options


def _check_design(
    ensembles: dict[str, list[Job]], pairs: int, scale: int, earlier: list[Job]
) -> None:
    """The README's design, checked on the jobs. Raises RuntimeError on any mismatch.

    Every configuration has its expected options, one block of consecutive seeds at its block, and
    no seed of experiments 001-003. The positive control s400 is block 0, and at full scale its
    options equal those of experiment 001's img64, so its renders are the cached ones.
    """
    if set(ensembles) != set(NATIVE_SIZE):
        raise RuntimeError(f"ENSEMBLES must hold {sorted(NATIVE_SIZE)}, got {sorted(ensembles)}")
    earlier_seeds = {job.seed for job in earlier}
    img64_options = {job.options for job in earlier if job.name == IMG64}
    all_seeds: list[int] = []
    for name, native in NATIVE_SIZE.items():
        jobs = ensembles[name]
        options = _expected_options(name, native // scale)
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
        if name == POSITIVE:
            if scale == 1 and {job.options for job in jobs} != img64_options:
                raise RuntimeError(f"{name}: options must equal experiment 001's {IMG64}")
        elif set(seeds) & earlier_seeds:
            raise RuntimeError(f"{name}: seeds overlap experiments 001-003")
        all_seeds.extend(seeds)
    if len(set(all_seeds)) != len(all_seeds):
        raise RuntimeError("seeds are not unique across configurations")


def _diffuse_only(object_id: np.ndarray) -> np.ndarray:
    """``object_id`` with every non-diffuse id set to -1, so that ``metrics.measure`` skips it.

    Only the diffuse regions are measured, as in experiments 002 and 003. The light (id 9) is
    excluded from every family.
    """
    return np.where(np.isin(object_id, DIFFUSE_REGION_IDS), object_id, -1)


def _min_attainable_p(n: int, m: int) -> float:
    """Smallest two-sided p-value that ``ensemble.permutation_pvalue`` can return for sizes n and m.

    Mirrors ``ensemble._min_attainable_pvalue``. When n == m, the mirror split is equally extreme,
    so the minimum is 2 / C(n + m, n).
    """
    splits = math.comb(n + m, n)
    if splits > ensemble.PERMUTATION_MAX_EXACT:
        return 1 / (ensemble.PERMUTATION_RESAMPLES + 1)
    return (2 if n == m else 1) / splits


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


def _reference_free(sum_a, sum_b, passes: int, object_id: np.ndarray) -> dict[str, float]:
    """Reference-free look metrics of one pair of half renders, at the render's own size.

    The definitions are those of ``metrics.measure`` (display, high-pass, erosion, diffuse regions),
    without the reference, plus the noise-corrected lag-1 of the structure (``slag1``). Keys are
    ``r{id}.mean.{R,G,B}``, ``r{id}.structure_std``, ``r{id}.lag1.{x,y}``, ``r{id}.slag1.{x,y}``,
    ``r{id}.spectral_slope``, ``all.clip_fraction`` and ``all.spectral_slope``.
    """
    a8 = smallpaint_display(sum_a, passes)
    b8 = smallpaint_display(sum_b, passes)
    ab8 = smallpaint_display(np.asarray(sum_a) + np.asarray(sum_b), 2 * passes)
    hp_a = metrics.highpass(metrics.luminance(a8), HIGHPASS_SIZE)
    hp_b = metrics.highpass(metrics.luminance(b8), HIGHPASS_SIZE)
    hp_ab = metrics.highpass(metrics.luminance(ab8), HIGHPASS_SIZE)
    masks = metrics.region_masks(_diffuse_only(object_id), ERODE_RADIUS)
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


def _reference_free_ensemble(jobs: list[Job], object_id: np.ndarray) -> list[dict[str, float]]:
    """``_reference_free`` for each consecutive pair of jobs, in order. Every render must share the
    configuration's object id map."""
    results: list[dict[str, float]] = []
    for first, second in zip(jobs[0::2], jobs[1::2], strict=True):
        a = load(first)
        b = load(second)
        for render in (a, b):
            if render.passes != PASSES:
                raise ValueError(f"{first.name!r}: passes must be {PASSES}, got {render.passes}")
            if not np.array_equal(render.object_id, object_id):
                raise ValueError(f"{first.name!r}: object id differs from its configuration's")
        results.append(_reference_free(a.sum, b.sum, PASSES, object_id))
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


def _ab8(jobs: list[Job]) -> np.ndarray:
    """``ab8`` of pair 0: the display image of the two half renders summed, at 2 * passes."""
    first, second = load(jobs[0]), load(jobs[1])
    return smallpaint_display(
        np.asarray(first.sum) + np.asarray(second.sum), first.passes + second.passes
    )


def _ab8_downsampled(jobs: list[Job]) -> np.ndarray:
    """``ab8`` of pair 0 after 2 x 2 box downsampling."""
    first, second = load(jobs[0]), load(jobs[1])
    return smallpaint_display(
        _box_down(first.sum) + _box_down(second.sum), first.passes + second.passes
    )


def _column(runs: list[dict], key: str) -> list[float]:
    return [run[key] for run in runs]


def _largest_rel(summary: dict) -> dict | None:
    """The key with the largest |relative difference|, ties broken by key name."""
    defined = [(abs(s["rel_diff"]), key) for key, s in summary.items() if s["rel_diff"] is not None]
    if not defined:
        return None
    value, key = max(defined)
    return {"key": key, "value": value}


def _family_test(
    x_runs: list[dict], y_runs: list[dict], family: list[str], alpha: float, label: str
) -> dict:
    """``compare_ensembles`` of two ensembles on a key family, with the power check.

    A comparison is powered when its smallest attainable p is at most the first Holm threshold,
    ``alpha / len(family)``. An underpowered comparison is not run through ``compare_ensembles``:
    it can neither reject nor be called indistinguishable.
    """
    min_p = _min_attainable_p(len(x_runs), len(y_runs))
    threshold = alpha / len(family)
    powered = min_p <= threshold
    summary = ensemble.effect_summary(x_runs, y_runs, family)
    record: dict = {
        "comparison": label,
        "n_keys": len(family),
        "alpha": alpha,
        "min_attainable_p": min_p,
        "holm_first_threshold": threshold,
        "powered": powered,
        "effect_summary": summary,
        "largest_abs_rel_diff": _largest_rel(summary),
    }
    if powered:
        comparison = ensemble.compare_ensembles(x_runs, y_runs, family, alpha)
        if comparison.min_attainable_p != min_p:
            raise RuntimeError("power formula is out of step with ensemble.compare_ensembles")
        record["pvalues"] = comparison.pvalues
        record["rejected_keys"] = [key for key in family if comparison.rejected[key]]
    else:
        record["pvalues"] = {
            key: ensemble.permutation_pvalue(_column(x_runs, key), _column(y_runs, key))
            for key in family
        }
        record["rejected_keys"] = None
    return record


def _h1a(runs: dict[str, list[dict]], family: list[str]) -> dict:
    """H1a: the noise-corrected lag-1 keys are indistinguishable across the three size pairs."""
    level = SIGNIFICANCE / len(SIZE_PAIRS)
    tests = {
        f"{a} vs {b}": _family_test(runs[a], runs[b], family, level, f"{a} vs {b}")
        for a, b in SIZE_PAIRS
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
    """H1b: the 800 px ensemble, box-downsampled to 400 px, is distinguishable from native 400."""
    test = _family_test(down, native, family, SIGNIFICANCE, "downsampled 800 vs native 400")
    if not test["powered"]:
        decision = "inconclusive"
    elif test["rejected_keys"]:
        decision = "supported"
    else:
        decision = "refuted"
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
            values = np.asarray(_column(metric_runs, key), dtype=np.float64)
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


def _grid(tiles: dict[str, np.ndarray]) -> np.ndarray:
    """Mosaic of the tiles in FIG_LAYOUT (row-major)."""
    rows, cols = len(FIG_LAYOUT), len(FIG_LAYOUT[0])
    mosaic = np.zeros((rows * PREVIEW_SIDE, cols * PREVIEW_SIDE, 3), dtype=np.uint8)
    for r, row in enumerate(FIG_LAYOUT):
        for c, name in enumerate(row):
            mosaic[
                r * PREVIEW_SIDE : (r + 1) * PREVIEW_SIDE, c * PREVIEW_SIDE : (c + 1) * PREVIEW_SIDE
            ] = tiles[name]
    return mosaic


def _json_safe(value):
    """JSON has no infinity or NaN. NaN is an error and is never written."""
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and math.isnan(value):
        raise RuntimeError("NaN in results")
    return value


def _fmt(value: float | None, spec: str = ".4g") -> str:
    return "n/a" if value is None else format(value, spec)


def _print_test(test: dict) -> None:
    rejected = test["rejected_keys"]
    count = "underpowered (not run)" if rejected is None else f"rejected={len(rejected)}"
    largest = test["largest_abs_rel_diff"]
    print(
        f"  {test['comparison']}: keys={test['n_keys']} {count} "
        f"min_attainable_p={test['min_attainable_p']:.3g} "
        f"threshold={test['holm_first_threshold']:.3g} "
        f"largest |rel|={_fmt(None if largest is None else largest['value'])} "
        f"({None if largest is None else largest['key']})"
    )
    if rejected:
        print(f"    rejected keys: {rejected}")


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.pairs < 1 or args.scale < 1:
        raise ValueError("--pairs and --scale must be >= 1")
    ensembles = _load_module(args.jobs).build_ensembles(args.pairs, args.scale)
    earlier: list[Job] = [job for path in EARLIER_JOBS for job in _load_module(path).JOBS]
    _check_design(ensembles, args.pairs, args.scale, earlier)

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
        name: sorted(metrics.region_masks(_diffuse_only(oid), ERODE_RADIUS))
        for name, oid in object_ids.items()
    }
    measured = measured_by[POSITIVE]
    if any(regions != measured for regions in measured_by.values()):
        raise RuntimeError(f"measured diffuse regions differ between configurations: {measured_by}")
    absent = sorted(set(DIFFUSE_REGION_IDS) - set(measured))
    measure_map = _diffuse_only(object_ids[POSITIVE])

    runs = {
        name: _reference_free_ensemble(ensembles[name], object_ids[name]) for name in NATIVE_SIZE
    }
    keys = sorted(runs[POSITIVE][0])
    for name, metric_runs in runs.items():
        if any(sorted(run) != keys for run in metric_runs):
            raise RuntimeError(f"reference-free keys of {name} differ")
    family = metrics.DIFFUSE_KEY_FAMILY(keys)
    lag1_corr = [key for key in family if ".slag1." in key]
    lag1_raw = [key for key in family if ".lag1." in key]
    structure = [key for key in family if key.endswith(".structure_std")]
    if len(lag1_corr) != 2 * len(measured):
        raise RuntimeError(f"expected {2 * len(measured)} noise-corrected lag-1 keys")

    native = measure_ensemble(ensembles[POSITIVE], reference8, measure_map)
    down = _downsampled_ensemble(ensembles[DOWNSAMPLED], reference8, measure_map)
    ds_keys = sorted(native[0])
    if sorted(down[0]) != ds_keys:
        raise RuntimeError("keys of the downsampled and native ensembles differ")
    ds_family = [key for key in metrics.DIFFUSE_KEY_FAMILY(ds_keys) if key != "all.block_rmse"]

    h1a = _h1a(runs, lag1_corr)
    h1b = _h1b(down, native, ds_family)
    h1 = {"decision": _h1(h1a, h1b), "H1a": h1a, "H1b": h1b}
    h2 = _h2(runs, lag1_raw + lag1_corr + structure)
    raw_lag1_effects = {
        f"{a} vs {b}": ensemble.effect_summary(runs[a], runs[b], lag1_raw) for a, b in SIZE_PAIRS
    }

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    tiles = {name: _preview(_ab8(jobs)) for name, jobs in ensembles.items()}
    tiles["downsampled"] = _preview(_ab8_downsampled(ensembles[DOWNSAMPLED]))
    tiles["reference"] = _preview(reference8)
    grid_name = "fig_grid.png"
    write_png(out_dir / grid_name, _grid(tiles))

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
            "downsample": ds_family,
            "lag1_noise_corrected": lag1_corr,
            "lag1_raw": lag1_raw,
            "structure_std": structure,
        },
        "hypotheses": {"H1": h1, "H2": h2},
        "raw_lag1_effects": raw_lag1_effects,
        "summary": _summary_table(runs, family),
        "grid": {
            "file": grid_name,
            "tile_px": PREVIEW_SIDE,
            "layout": [list(r) for r in FIG_LAYOUT],
        },
    }
    text = json.dumps(_json_safe(results), indent=2, sort_keys=True) + "\n"
    if "NaN" in text:
        raise RuntimeError("NaN in results.json")
    (out_dir / "results.json").write_text(text, encoding="utf-8")

    print(
        f"keys: reference-free={len(family)} downsample={len(ds_family)}; "
        f"pairs={args.pairs}; scale={args.scale}"
    )
    print(f"measured regions {measured}, absent {absent}")
    print(
        "H1a noise-corrected lag-1 across sizes, "
        f"level {h1a['level_per_pair']:.4g} per pair: {h1a['decision']}"
    )
    for test in h1a["tests"].values():
        _print_test(test)
    print(f"H1b downsampled 800 vs native 400: {h1b['decision']}")
    _print_test(h1b["test"])
    print(f"H1 {h1['decision']}")
    print(f"H2 jitter 1/700 vs 1/1400 at 800 px: {h2['decision']}")
    _print_test(h2["test"])
    print(f"wrote {out_dir / 'results.json'} and {out_dir / grid_name}")


if __name__ == "__main__":
    main()
