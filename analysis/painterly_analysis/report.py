"""Helpers shared by the experiment analyses (T1.11).

Each ``experiments/NNN-*/analyze.py`` keeps its own decisions and figures. The statistics it would
otherwise copy, the Holm bookkeeping, the pair and preview helpers and the JSON writer live here, so
they are written and tested once.

Conventions. An ensemble is a list of per-pair metric dicts, one per pair of half renders, as
``ensemble_metrics`` returns them. ``alpha`` is a family-wise level, the significance of a decision.
It is not the oracle option of the same name. Every p-value is a permutation p-value from
``ensemble.permutation_pvalue``, so no distributional assumption is made.
"""

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np

from . import ensemble, metrics
from .experiment import Job, load
from .experiment import load_jobs_module as load_jobs_module  # re-exported (see experiment.py)
from .io import smallpaint_display


def _column(runs: Sequence[Mapping[str, float]], key: str) -> list[float]:
    return [run[key] for run in runs]


def _largest_abs(summary: Mapping[str, Mapping[str, Any]], field: str) -> dict[str, Any] | None:
    defined = [
        (abs(entry[field]), key) for key, entry in summary.items() if entry[field] is not None
    ]
    if not defined:
        return None
    value, key = max(defined)
    return {"key": key, "value": value}


def largest_abs_rel_diff(summary: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    """The entry of an ``ensemble.effect_summary`` with the largest |relative difference|.

    Returns ``{"key": ..., "value": ...}``, or None when no entry has a defined ``rel_diff``. Ties
    go to the larger key name. Entries whose ``rel_diff`` is None (the mean of b is 0) are skipped.
    """
    return _largest_abs(summary, "rel_diff")


def largest_abs_cohen_d(summary: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    """The entry of an ``ensemble.effect_summary`` with the largest |Cohen's d|.

    Returns ``{"key": ..., "value": ...}``, or None when no entry has a defined ``cohen_d``. Ties go
    to the larger key name. Entries whose ``cohen_d`` is None (a pooled sd of 0) are skipped.
    """
    return _largest_abs(summary, "cohen_d")


def pair_test(
    a: list[dict], b: list[dict], key: str, alternative: str, alpha: float
) -> dict[str, Any]:
    """One metric key of ensemble ``a`` against ensemble ``b``, with one permutation test.

    ``alternative`` is "two-sided", "greater" or "less", as in ``ensemble.permutation_pvalue``.
    "less" asks whether ``a`` is lower than ``b``. The key is ``rejected`` when its p-value is at
    most ``alpha``. That decision is uncorrected: callers apply Holm across keys with
    ``ensemble.holm``.

    Returns ``{"key", "alternative", "p_value", "min_attainable_p", "rejected", "effect"}``.
    ``effect`` is the ``ensemble.effect_summary`` entry of the key.
    """
    x = _column(a, key)
    y = _column(b, key)
    p_value = ensemble.permutation_pvalue(x, y, alternative)
    return {
        "key": key,
        "alternative": alternative,
        "p_value": p_value,
        "min_attainable_p": ensemble.min_attainable_pvalue(len(x), len(y), alternative),
        "rejected": p_value <= alpha,
        "effect": ensemble.effect_summary(a, b, [key])[key],
    }


def directional_pair_test(
    a: list[dict],
    b: list[dict],
    key: str,
    alpha: float,
    *,
    labels: tuple[str, str] = ("a", "b"),
) -> dict[str, Any]:
    """One metric key of ensemble ``a`` against ``b``, with both one-sided permutation tests.

    ``p_less`` is the p-value of "a is lower than b" and ``p_greater`` that of "a is higher than b".
    Both are exact permutation p-values from ``pair_test``. ``min_attainable_p`` is the smallest
    p-value the "greater" test can return, ``ensemble.min_attainable_pvalue(n, m, "greater")``. For
    one-sided tests this equals the "less" minimum. ``effect`` is the ``ensemble.effect_summary``
    entry of the key. ``labels`` name the two ensembles, and ``comparison`` reads ``"<a> vs <b>"``.

    Returns ``{"comparison", "key", "p_less", "p_greater", "min_attainable_p", "effect"}``. Holm
    across keys or steps is the caller's (``ensemble.holm``).
    """
    less = pair_test(a, b, key, "less", alpha)
    greater = pair_test(a, b, key, "greater", alpha)
    return {
        "comparison": f"{labels[0]} vs {labels[1]}",
        "key": key,
        "p_less": less["p_value"],
        "p_greater": greater["p_value"],
        "min_attainable_p": greater["min_attainable_p"],
        "effect": less["effect"],
    }


def family_test(a: list[dict], b: list[dict], keys: Iterable[str], alpha: float) -> dict[str, Any]:
    """``ensemble.compare_ensembles`` of ``a`` against ``b`` on a key family, with the power check.

    The comparison is powered when its smallest attainable two-sided p-value is at most the first
    Holm threshold, ``alpha / len(keys)``. An underpowered comparison is not passed to
    ``compare_ensembles``, because it could reject nothing. Its ``rejected_keys`` is None, and its
    p-values are still reported. Holm is applied at ``alpha`` across ``keys``.

    Returns ``{"n_keys", "alpha", "min_attainable_p", "holm_first_threshold", "powered",
    "effect_summary", "largest_abs_rel_diff", "largest_abs_cohen_d", "pvalues", "rejected_keys"}``.
    The two largest effects are ``{"key", "value"}`` dicts, or None.
    """
    family = list(keys)
    if not family:
        raise ValueError("need at least one key")
    min_p = ensemble.min_attainable_pvalue(len(a), len(b), "two-sided")
    threshold = alpha / len(family)
    powered = min_p <= threshold
    summary = ensemble.effect_summary(a, b, family)
    record: dict[str, Any] = {
        "n_keys": len(family),
        "alpha": alpha,
        "min_attainable_p": min_p,
        "holm_first_threshold": threshold,
        "powered": powered,
        "effect_summary": summary,
        "largest_abs_rel_diff": largest_abs_rel_diff(summary),
        "largest_abs_cohen_d": largest_abs_cohen_d(summary),
    }
    if powered:
        comparison = ensemble.compare_ensembles(a, b, family, alpha)
        if comparison.min_attainable_p != min_p:
            raise RuntimeError("power formula is out of step with ensemble.compare_ensembles")
        record["pvalues"] = comparison.pvalues
        record["rejected_keys"] = [key for key in family if comparison.rejected[key]]
    else:
        record["pvalues"] = {
            key: ensemble.permutation_pvalue(_column(a, key), _column(b, key), "two-sided")
            for key in family
        }
        record["rejected_keys"] = None
    return record


def adjacent_tests(
    ensembles: Mapping[str, list[dict]], order: Sequence[str], key: str, alpha: float
) -> dict[str, Any]:
    """Adjacent steps of a monotone sequence of ensembles, on one metric key.

    ``order`` names the ensembles from low to high. Each step ``lo -> hi`` of consecutive names is
    tested as ``hi`` against ``lo`` with ``directional_pair_test``, which gives ``p_less`` (the
    p-value of "hi is lower") and ``p_greater`` ("hi is higher"). Holm (``ensemble.holm``) runs
    across the steps in each direction at ``alpha``.

    Returns ``{"key", "alpha", "steps", "holm_rejected_less", "holm_rejected_greater",
    "significant_decreases", "significant_increases", "powered"}``. Each entry of ``steps`` (named
    ``"lo->hi"``) is a ``directional_pair_test`` record with ``comparison`` ("hi vs lo"), ``key``,
    ``p_less``, ``p_greater``, ``min_attainable_p`` and ``effect``. ``powered`` is True when every
    step's smallest attainable p-value is at most ``alpha / (number of steps)``.
    """
    if len(order) < 2 or len(set(order)) != len(order):
        raise ValueError("order must name at least two distinct ensembles")
    steps: dict[str, dict[str, Any]] = {
        f"{lo}->{hi}": directional_pair_test(
            ensembles[hi], ensembles[lo], key, alpha, labels=(hi, lo)
        )
        for lo, hi in zip(order[:-1], order[1:], strict=True)
    }
    less_rejected = ensemble.holm({name: s["p_less"] for name, s in steps.items()}, alpha)
    greater_rejected = ensemble.holm({name: s["p_greater"] for name, s in steps.items()}, alpha)
    return {
        "key": key,
        "alpha": alpha,
        "steps": steps,
        "holm_rejected_less": less_rejected,
        "holm_rejected_greater": greater_rejected,
        "significant_decreases": [name for name in steps if less_rejected[name]],
        "significant_increases": [name for name in steps if greater_rejected[name]],
        "powered": all(s["min_attainable_p"] <= alpha / len(steps) for s in steps.values()),
    }


def _reject_non_finite(value: Any, where: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_non_finite(item, f"{where}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _reject_non_finite(item, f"{where}[{index}]")
    elif isinstance(value, (float, np.floating)) and not math.isfinite(value):
        raise ValueError(f"{where} is {float(value)}: a results file holds only finite numbers")


def write_results_json(path: Path, obj: Any) -> None:
    """Write ``obj`` to ``path`` as JSON, deterministically.

    Keys are sorted, the indent is two spaces, floats use Python's shortest round-trip repr, and the
    file ends with a newline. A NaN or an infinity anywhere raises ValueError before the file is
    written, so no results file holds a non-finite number. A caller that records an infinite value
    must encode it itself, as a string, for example.
    """
    _reject_non_finite(obj, "results")
    text = json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n"
    Path(path).write_text(text, encoding="utf-8")


def diffuse_only(object_id: np.ndarray, regions: Iterable[int]) -> np.ndarray:
    """``object_id`` with every id outside ``regions`` set to -1, so ``metrics.measure`` skips it.

    ``metrics.region_masks`` skips negative ids. The pixels set to -1 change no value of the kept
    regions, and the ``all.*`` keys use only the union of the kept masks. So only the named regions
    are measured. This is how experiments 002 to 004 exclude the light (id 9), which otherwise has
    no lag-1 pairs at 64 px and makes ``metrics.measure`` raise.
    """
    return np.where(np.isin(object_id, list(regions)), object_id, -1)


def ensemble_metrics(
    jobs: list[Job],
    reference8: np.ndarray,
    regions: Iterable[int] | None = None,
    object_id: np.ndarray | None = None,
) -> list[dict[str, float]]:
    """``metrics.measure`` for each consecutive pair of cached renders: an ensemble's metric dicts.

    ``jobs`` must all be rendered and form pairs (jobs 2k and 2k + 1). The two halves of a pair must
    have equal passes. ``regions`` restricts the measurement to those SPEC §9 ids through
    ``diffuse_only``. None measures every id. ``object_id`` is the id map that every render must
    share. When it is None, the first render's map is used. A render with another map raises
    ValueError, because one set of masks cannot serve it.
    """
    if not jobs or len(jobs) % 2 != 0:
        raise ValueError("jobs must form pairs: a non-zero, even number of jobs")
    measure_map: np.ndarray | None = None
    results: list[dict[str, float]] = []
    for first, second in zip(jobs[0::2], jobs[1::2], strict=True):
        a = load(first)
        b = load(second)
        if a.passes != b.passes:
            raise ValueError(f"pair {first.name!r}: passes differ ({a.passes} vs {b.passes})")
        for job, render in ((first, a), (second, b)):
            if object_id is None:
                object_id = render.object_id
            elif not np.array_equal(render.object_id, object_id):
                raise ValueError(f"{job.name!r} seed {job.seed}: object id differs from the others")
        if measure_map is None:
            measure_map = object_id if regions is None else diffuse_only(object_id, regions)
        results.append(metrics.measure(a.sum, b.sum, a.passes, reference8, measure_map))
    return results


def ab8_of_pair(jobs: Sequence[Job]) -> np.ndarray:
    """The display image of pair 0: its two half renders summed, at the sum of their passes.

    ``jobs[0]`` and ``jobs[1]`` form the pair. The result is ``smallpaint_display(sum_a + sum_b,
    passes_a + passes_b)``, uint8 display bytes (SPEC §7). The arithmetic is that of experiment
    002's ``_ab8``: the sums are added first, and only then mapped to display bytes.
    """
    first, second = load(jobs[0]), load(jobs[1])
    return smallpaint_display(
        np.asarray(first.sum) + np.asarray(second.sum), first.passes + second.passes
    )


def block_preview(img8: np.ndarray, factor: int) -> np.ndarray:
    """A preview of a display image: each ``factor`` x ``factor`` pixel block replaced by its mean.

    The mean of each block is taken per channel and rounded with ``np.round`` (half to even). An
    (H, W, 3) image gives a uint8 array of shape (H / factor, W / factor, 3). The image sides must
    be multiples of ``factor``, or ValueError is raised.
    """
    if factor < 1:
        raise ValueError("factor must be >= 1")
    h, w = img8.shape[:2]
    if h % factor or w % factor:
        raise ValueError(f"image side must be a multiple of {factor}, got {h} x {w}")
    blocks = img8.astype(np.float64).reshape(
        h // factor, factor, w // factor, factor, *img8.shape[2:]
    )
    return np.round(blocks.mean(axis=(1, 3))).astype(np.uint8)


def mosaic(previews: Mapping[str, np.ndarray], columns: int) -> np.ndarray:
    """A mosaic of equal-size previews, laid out row-major in the mapping's order.

    Preview ``i`` goes in row ``i // columns`` and column ``i % columns``. The last row is padded
    with black cells when the count is not a multiple of ``columns``. Every preview must have the
    same shape, or ValueError is raised. The result is uint8, with the grid size times the preview
    shape.
    """
    if columns < 1:
        raise ValueError("columns must be >= 1")
    tiles = list(previews.values())
    if not tiles:
        raise ValueError("need at least one preview")
    tile_shape = tiles[0].shape
    if any(tile.shape != tile_shape for tile in tiles):
        raise ValueError("every preview must have the same shape")
    tile_h, tile_w = tile_shape[:2]
    rows = (len(tiles) + columns - 1) // columns
    grid = np.zeros((rows * tile_h, columns * tile_w, *tile_shape[2:]), dtype=np.uint8)
    for index, tile in enumerate(tiles):
        row, col = divmod(index, columns)
        grid[row * tile_h : (row + 1) * tile_h, col * tile_w : (col + 1) * tile_w] = tile
    return grid
