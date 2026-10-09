"""Analysis of experiment 006 (T1.13): which jitter unit makes the look independent of resolution?

Implements the Common definitions and H1 to H5 of ``README.md``, which is the specification.

Scale-equivariant parameters are functions of the rendered side ``s``: the high-pass sigma, the
region erosion and the structure lag are in pixels of that side, and the reference side is
``jobs.REFERENCE_SIDE`` (400).

Re-runs from the render cache, so every render must already exist (``jobs.py``). The exception is a
smoke run (``--scale`` above 1): it renders its own small jobs into ``$PAINTERLY_CACHE`` first, and
it must write to a scratch ``--out-dir``. Writes ``results.json``, one grid file per row of
``GRID_LAYOUT`` (``fig_grid_<row>.png``, six files) and ``fig_slag_profile.png``, and prints the
tables. A smoke run prefixes every printed line with ``SMOKE (code check only): ``. It is
deterministic: the tests are exact permutation tests, and the H3 bootstrap draws from
``numpy.random.default_rng(0)``.

Figure encodings (no text is drawn; the mapping is also in ``results.json`` under ``figures``):
- ``fig_grid_<row>.png``: three tiles, pair 0 of each configuration in its row of ``GRID_LAYOUT``,
  box-downsampled to 200 px (nearest upscale only at smoke scale). The rows are image-plane image
  chain, pixel image chain, image-plane row chain, pixel row chain, zero jitter image chain and zero
  jitter row chain. The 400 px member of the pixel rows is ``s400`` (or ``row_s400``), since both
  units coincide there.
- ``fig_slag_profile.png``: mean +- sd over pairs of the region-4 structure autocorrelation against
  the image-plane lag k/200 of the side (k = 1, 2, 3). Row 1 is ``slag.x``, row 2 is ``slag.y``.
  Columns are the native sides 200, 400 and 800. Series: solid blue image-plane image chain, dashed
  blue image-plane row chain, solid red pixel image chain, dashed red pixel row chain, solid green
  zero jitter image chain. Each panel has its own vertical scale within its row, shared by the
  three columns.
"""

import argparse
import hashlib
import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
from painterly_analysis import (
    DIFFUSE_REGION_IDS,
    OracleRender,
    ensemble,
    metrics,
    report,
    smallpaint_display,
    write_png,
)
from painterly_analysis.experiment import Job, load, run_jobs

EXP_DIR = Path(__file__).resolve().parent
EXPERIMENT = EXP_DIR.name
DEFAULT_JOBS = EXP_DIR / "jobs.py"
REPO_ROOT = EXP_DIR.parents[1]
# Earlier experiments whose seeds this one must not reuse with other options (the global seed rule).
EARLIER_JOBS = {
    "001": REPO_ROOT / "experiments" / "001-2026-10-08-oracle-reproduction" / "jobs.py",
    "002": REPO_ROOT / "experiments" / "002-2026-10-08-ingredient-ablation" / "jobs.py",
    "003": REPO_ROOT / "experiments" / "003-2026-10-08-lane-length" / "jobs.py",
    "004": REPO_ROOT / "experiments" / "004-2026-10-08-resolution-dependence" / "jobs.py",
}

PASSES = 64  # P of every configuration (jobs.py, README Method)
PAIRS = 8  # pairs per configuration in the experiment (jobs.py)
# Family-wise level of each hypothesis (README, Common definitions). It is not the oracle option
# `alpha`.
SIGNIFICANCE = 0.01
# The smallest native side. The structure lag is s // 200 px, so it is 1, 2 and 4 px at 200, 400 and
# 800 px.
LAG_UNIT_SIDE = 200
# 004's erosion radius at every side (004 analyze.py, ERODE_RADIUS). It is the control of H5.
FIXED_EROSION = metrics.HIGHPASS_SIZE // 2
SPECTRAL_F_MIN = 2  # lowest integer radius of the spectral band (README: f_min = 2)
# Highest radius of the spectral band, in cycles per image, at every full-scale side
# (README: f_max = 50).
SPECTRAL_F_MAX = 50
# radial_spectral_slope's default band is side // 4 (metrics.py). The band takes that value only
# where it is below SPECTRAL_F_MAX, which is only at smoke scale.
SPECTRAL_DEFAULT_DIVISOR = 4
# Sets only the Monte Carlo precision of the H3 intervals (README, H3). No decision depends on them.
BOOTSTRAP_RESAMPLES = 10_000
BOOTSTRAP_SEED = 0  # numpy.random.default_rng seed of the H3 bootstrap (README, H3)
CI_PERCENTILES = (2.5, 97.5)  # the 95% percentile interval (README, H3)
PROFILE_REGION = 4  # the back wall (README, Analysis)
PROFILE_LAGS = (1, 2, 3)  # image-plane lags k / LAG_UNIT_SIDE of the side (README, Analysis)
PREVIEW_SIDE = 200  # side in pixels of each grid tile (README, Analysis)
# Every grid file is at most 1 MB (README, Layout rules and amendment 2).
MAX_FIGURE_BYTES = 1_000_000
# Prefixed to every printed line of a smoke run (README, amendment 3).
SMOKE_PREFIX = "SMOKE (code check only): "
UNITS = ("image-plane", "pixel")

# The README's Method table, and amendment 1's row zero family:
# name -> (native side, chain, image-plane jitter, seed block).
TABLE: dict[str, tuple[int, str, Fraction, int]] = {
    "s200": (200, "image", Fraction(1, 700), 28),
    "s400": (400, "image", Fraction(1, 700), 0),
    "s800": (800, "image", Fraction(1, 700), 29),
    "s200_px": (200, "image", Fraction(1, 350), 33),
    "s800_px": (800, "image", Fraction(1, 1400), 30),
    "row_s200": (200, "row", Fraction(1, 700), 31),
    "row_s400": (400, "row", Fraction(1, 700), 27),
    "row_s800": (800, "row", Fraction(1, 700), 32),
    "row_s200_px": (200, "row", Fraction(1, 350), 34),
    "row_s800_px": (800, "row", Fraction(1, 1400), 35),
    "j0_s200": (200, "image", Fraction(0), 36),
    "j0_s400": (400, "image", Fraction(0), 37),
    "j0_s800": (800, "image", Fraction(0), 38),
    "row_j0_s200": (200, "row", Fraction(0), 39),
    "row_j0_s400": (400, "row", Fraction(0), 40),
    "row_j0_s800": (800, "row", Fraction(0), 41),
}
# The oracle's default image-plane jitter, 1/700 (smallpaint painterly.cpp:291-292). It is not
# passed.
REFERENCE_JITTER = Fraction(1, 700)
# Reused configurations: 006 name -> 004 name with the same option set and seeds (README, Method
# table).
REUSED_FROM_004 = {
    "s200": "s200",
    "s400": "s400",
    "s800": "s800",
    "s800_px": "s800_j1400",
    "row_s200": "row_s200",
    "row_s400": "row_s400",
    "row_s800": "row_s800",
}
# Reused from the earlier experiments with their own jobs (checked at full scale only).
REUSED_FROM_EARLIER = {"s400": ("001", "img64"), "row_s400": ("003", "row")}
# The configurations behind each Holm-tested decision (README, Hypothesis). H3 and H5 are
# effect-size decisions without p-values, so they are not listed. H4 is the row-chain zero family of
# amendment 1.
HYPOTHESIS_CONFIGURATIONS = {
    "H1-image": ("s200", "s400", "s800"),
    "H1-row": ("row_s200", "row_s400", "row_s800"),
    "H2-image": ("s200_px", "s400", "s800_px"),
    "H2-row": ("row_s200_px", "row_s400", "row_s800_px"),
    "H4": ("row_j0_s200", "row_j0_s400", "row_j0_s800"),
}
# The image-chain zero-jitter configurations, estimation only (amendment 1).
ZERO_IMAGE_CHAIN = ("j0_s200", "j0_s400", "j0_s800")
# The grid figures (README, amendment 2): (file stem, configurations of the row). Each row is one
# file, fig_grid_<stem>.png, of three tiles.
GRID_LAYOUT = (
    ("image_plane", ("s200", "s400", "s800")),
    ("pixel", ("s200_px", "s400", "s800_px")),
    ("row_image_plane", ("row_s200", "row_s400", "row_s800")),
    ("row_pixel", ("row_s200_px", "row_s400", "row_s800_px")),
    ("zero", ("j0_s200", "j0_s400", "j0_s800")),
    ("row_zero", ("row_j0_s200", "row_j0_s400", "row_j0_s800")),
)
# The sides of the jitter-footprint comparisons row_j0_sN vs row_sN (amendment 1).
FOOTPRINT_SIDES = (200, 400, 800)
# (label, RGB colour, dashed, {native side: configuration name}) of each series of
# fig_slag_profile.png.
PROFILE_SERIES = (
    ("image-plane, image chain", (31, 119, 180), False, {200: "s200", 400: "s400", 800: "s800"}),
    (
        "image-plane, row chain",
        (31, 119, 180),
        True,
        {200: "row_s200", 400: "row_s400", 800: "row_s800"},
    ),
    ("pixel, image chain", (214, 39, 40), False, {200: "s200_px", 400: "s400", 800: "s800_px"}),
    (
        "pixel, row chain",
        (214, 39, 40),
        True,
        {200: "row_s200_px", 400: "row_s400", 800: "row_s800_px"},
    ),
    (
        "zero jitter, image chain",
        (44, 160, 44),
        False,
        {200: "j0_s200", 400: "j0_s400", 800: "j0_s800"},
    ),
)
PROFILE_SIDES = (200, 400, 800)
# Drawing knobs of fig_slag_profile.png, in pixels. They affect only the picture.
PANEL_W = 180
PANEL_H = 150
CELL_W = 220
ROW_GAP = 40
LEFT_MARGIN = 20
TOP_MARGIN = 20
LEGEND_H = 50
TICK_PX = 4
CAP_HALF_PX = 4
MARKER_HALF_PX = 3
DASH_PERIOD_PX = 10
DASH_ON_PX = 6
LEGEND_SAMPLE_PX = 28
LEGEND_CELL_W = 130
# Horizontal offset of each series from its lag, in pixels, so the series at one lag do not overlap.
SERIES_OFFSET_PX = 5
AXIS_GREY = (120, 120, 120)
ZERO_GREY = (190, 190, 190)
X_RANGE = (0.5, 3.5)  # the lag index k on the horizontal axis
Y_PAD = 0.05  # fraction of each row's range added above and below the data


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analysis of experiment 006 (T1.13).")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=EXP_DIR,
        help="directory for results.json and the figures (default: this directory)",
    )
    parser.add_argument(
        "--pairs",
        type=int,
        default=PAIRS,
        help="pairs per configuration (default: the experiment's 8; the smoke run uses 2)",
    )
    parser.add_argument(
        "--scale",
        type=int,
        default=1,
        help="divide every native side by this (default: 1, the experiment; the smoke run uses 4)",
    )
    return parser.parse_args(argv)


# --------------------------------------------------------------------------------------------------
# Scale-equivariant parameters and the design check
# --------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SideParams:
    """The scale-equivariant parameters of one rendered side ``s`` (README, Common definitions)."""

    side: int
    sigma: float  # standard deviation of the Gaussian high-pass, px
    erosion: int  # erosion radius of the region masks, px
    lag: int  # structure lag of noise_corrected_lag, px
    spectral_f_max: int  # upper radius of the spectral band, cycles per image
    profile_lag: tuple[int, ...]  # lags of fig_slag_profile, one per PROFILE_LAGS entry, px


def _pixels(exact: Fraction, side: int, quantity: str, scale: int, notes: list[str]) -> int:
    """An exact scaled quantity as an integer number of pixels.

    At full scale it must already be an integer, or RuntimeError is raised. At smoke scale it is
    rounded to the nearest integer of at least 1, and the rounding is recorded in ``notes``
    (README, Commands).
    """
    if exact.denominator == 1:
        return exact.numerator
    if scale == 1:
        raise RuntimeError(f"{quantity} at side {side} is {exact} px, not an integer")
    value = max(1, round(exact))
    notes.append(f"smoke rounding: {quantity} at side {side} is {exact} px, used {value} px")
    return value


def side_params(side: int, reference: int, scale: int, notes: list[str]) -> SideParams:
    """The parameters at rendered side ``side``, with reference side ``s0 = reference``.

    The README's Common definitions give ``sigma(s) = (9 / sqrt(12)) * s / s0``. The 9 / sqrt(12)
    is the standard deviation of a uniform box of width 9, the plan's 9-px box. Also
    ``erosion(s) = (9 // 2) * s // s0`` and ``lag(s) = s // 200``, which are asserted exact at full
    scale.
    """
    sigma = (metrics.HIGHPASS_SIZE / math.sqrt(12.0)) * side / reference
    erosion_numerator = (metrics.HIGHPASS_SIZE // 2) * side
    if scale == 1 and erosion_numerator % reference != 0:
        raise RuntimeError(f"erosion at side {side} is not an exact integer")
    if scale == 1 and side % LAG_UNIT_SIDE != 0:
        raise RuntimeError(f"lag at side {side} is not an exact integer")
    erosion = _pixels(Fraction(erosion_numerator, reference), side, "erosion", scale, notes)
    lag = _pixels(Fraction(side, LAG_UNIT_SIDE), side, "lag", scale, notes)
    profile_lag = tuple(
        _pixels(
            Fraction(k * side, LAG_UNIT_SIDE),
            side,
            f"profile lag {k}/{LAG_UNIT_SIDE}",
            scale,
            notes,
        )
        for k in PROFILE_LAGS
    )
    # side // SPECTRAL_DEFAULT_DIVISOR is the default upper radius of radial_spectral_slope, so the
    # band is valid at every size. At full scale it equals SPECTRAL_F_MAX at every native side.
    spectral_f_max = min(SPECTRAL_F_MAX, side // SPECTRAL_DEFAULT_DIVISOR)
    if scale == 1 and spectral_f_max != SPECTRAL_F_MAX:
        raise RuntimeError(f"spectral band at side {side} is not f_max = {SPECTRAL_F_MAX}")
    return SideParams(side, sigma, erosion, lag, spectral_f_max, profile_lag)


def _expected_options(name: str, scale: int) -> dict[str, object]:
    """The oracle options of a configuration: the chain, P and the side, and the jitter unless it
    is the default."""
    side, chain, jitter, _block = TABLE[name]
    options: dict[str, object] = {"chain": chain, "passes": PASSES, "size": side // scale}
    if jitter != REFERENCE_JITTER:
        options["jitter"] = float(jitter)
    return options


def _check_design_table(design: Mapping[str, tuple[int, Mapping[str, object], int]]) -> None:
    """``jobs.DESIGN`` must match the README's table: sides, seed blocks, chains and jitters."""
    if set(design) != set(TABLE):
        raise RuntimeError(f"jobs.DESIGN must hold {sorted(TABLE)}, got {sorted(design)}")
    for name, (side, extra, block) in design.items():
        t_side, t_chain, t_jitter, t_block = TABLE[name]
        chain = extra.get("chain", "image")
        jitter = float(extra.get("jitter", REFERENCE_JITTER))
        if (side, block, chain, jitter) != (t_side, t_block, t_chain, float(t_jitter)):
            raise RuntimeError(
                f"jobs.DESIGN[{name!r}] = {(side, dict(extra), block)} "
                "does not match the README table"
            )


def _check_design(
    ensembles: Mapping[str, list[Job]], seeds_per_config: int, pairs: int, scale: int
) -> None:
    """The README's design, checked on the jobs (Method table). Raises RuntimeError on any mismatch.

    Each configuration has its expected options and one block of consecutive seeds at its block. No
    seed is shared between configurations. A reused configuration has the option set and seeds of
    its source. At full scale the seeds shared with earlier experiments are exactly the reuses, each
    with an identical option set (``report.check_seed_reuse``).
    """
    if set(ensembles) != set(TABLE):
        raise RuntimeError(f"ENSEMBLES must hold {sorted(TABLE)}, got {sorted(ensembles)}")
    all_seeds: list[int] = []
    for name, (_side, _chain, _jitter, block) in TABLE.items():
        jobs = ensembles[name]
        options = _expected_options(name, scale)
        if len(jobs) != 2 * pairs or any(dict(job.options) != options for job in jobs):
            raise RuntimeError(f"{name}: expected {2 * pairs} jobs with options {options}")
        base = seeds_per_config * block
        seeds = [job.seed for job in jobs]
        if seeds != list(range(base, base + 2 * pairs)):
            raise RuntimeError(f"{name}: seeds must run from {base} (block {block}), got {seeds}")
        all_seeds.extend(seeds)
    if len(set(all_seeds)) != len(all_seeds):
        raise RuntimeError("seeds are not unique across configurations")

    if scale != 1:
        # A smoke run builds experiment 004 at its own size, so the 004 sources are compared with
        # that build here. check_seed_reuse reads the full-size jobs files, so it runs at full
        # scale only.
        source_004 = report.load_jobs_module(EARLIER_JOBS["004"]).build_ensembles(pairs, scale)
        for name, source_name in REUSED_FROM_004.items():
            mine = [(job.seed, job.options) for job in ensembles[name]]
            theirs = [(job.seed, job.options) for job in source_004[source_name]]
            if mine != theirs:
                raise RuntimeError(
                    f"{name}: seeds or options differ from experiment 004's {source_name}"
                )
        return
    # The reuses from experiment 004 and from 001 and 003 are declared together. Where a
    # configuration is in both (s400 and row_s400), the source in REUSED_FROM_EARLIER is checked.
    reused = {
        **{name: ("004", source) for name, source in REUSED_FROM_004.items()},
        **REUSED_FROM_EARLIER,
    }
    report.check_seed_reuse(ensembles, EARLIER_JOBS, reused)


# --------------------------------------------------------------------------------------------------
# Per-pair measurements
# --------------------------------------------------------------------------------------------------


def _masks(object_id: np.ndarray, radius: int) -> dict[int, Any]:
    """Eroded masks of the diffuse regions (SPEC section 9 ids 2-8). Empty masks are absent."""
    return metrics.region_masks(report.diffuse_only(object_id, DIFFUSE_REGION_IDS), radius)


def _put_means(out: dict[str, float], prefix: str, img8: np.ndarray, mask: Any) -> None:
    """The region mean of each channel of ``img8`` over ``mask`` (README, Estimation)."""
    mean = metrics.region_mean_rgb(img8, mask)
    for channel, name in enumerate("RGB"):
        out[f"{prefix}.mean.{name}"] = float(mean[channel])


def _pair_values(
    a: OracleRender,
    b: OracleRender,
    params: SideParams,
    measured: Sequence[int],
    masks: Mapping[int, Any],
    fixed_masks: Mapping[int, Any],
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """The metric values of one pair of half renders: (scaled, fixed, profile).

    ``scaled`` holds the texture family T and the estimation-only keys at the scaled erosion
    ``params.erosion``. ``fixed`` holds the region means at 004's fixed erosion (H5). ``profile``
    holds the region-4 structure autocorrelation of fig_slag_profile at ``params.profile_lag``. The
    halves are ``a`` and ``b``. The summed display ``ab8`` is used for the means and the spectral
    slope, as in experiment 004.
    """
    a8 = smallpaint_display(a.sum, PASSES)
    b8 = smallpaint_display(b.sum, PASSES)
    ab8 = smallpaint_display(np.asarray(a.sum) + np.asarray(b.sum), 2 * PASSES)
    hp_a = metrics.gaussian_highpass(metrics.luminance(a8), params.sigma)
    hp_b = metrics.gaussian_highpass(metrics.luminance(b8), params.sigma)
    hp_ab = metrics.gaussian_highpass(metrics.luminance(ab8), params.sigma)
    scaled: dict[str, float] = {}
    fixed: dict[str, float] = {}
    for region in measured:
        mask = masks[region]
        prefix = f"r{region}"
        scaled[f"{prefix}.structure_std"] = float(metrics.structure_std(hp_a, hp_b, mask))
        scaled[f"{prefix}.slag.x"] = float(
            metrics.noise_corrected_lag(hp_a, hp_b, mask, axis=1, lag=params.lag)
        )
        scaled[f"{prefix}.slag.y"] = float(
            metrics.noise_corrected_lag(hp_a, hp_b, mask, axis=0, lag=params.lag)
        )
        _put_means(scaled, prefix, ab8, mask)
        scaled[f"{prefix}.spectral_slope"] = float(
            metrics.radial_spectral_slope(
                hp_ab, mask, f_min=SPECTRAL_F_MIN, f_max=params.spectral_f_max
            )
        )
        _put_means(fixed, prefix, ab8, fixed_masks[region])
    profile: dict[str, float] = {}
    mask = masks[PROFILE_REGION]
    for k, lag in zip(PROFILE_LAGS, params.profile_lag, strict=True):
        profile[f"k{k}.x"] = float(metrics.noise_corrected_lag(hp_a, hp_b, mask, axis=1, lag=lag))
        profile[f"k{k}.y"] = float(metrics.noise_corrected_lag(hp_a, hp_b, mask, axis=0, lag=lag))
    return scaled, fixed, profile


def _measure_configuration(
    name: str,
    jobs: Sequence[Job],
    object_id: np.ndarray,
    params: SideParams,
    measured: Sequence[int],
) -> tuple[list[dict], list[dict], list[dict], list[str]]:
    """The per-pair (scaled, fixed, profile) values of one configuration, in pair order, and the
    SHA-256 digest of the sum array of every render (for the replicate check)."""
    masks = _masks(object_id, params.erosion)
    fixed_masks = _masks(object_id, FIXED_EROSION)
    if any(region not in masks or region not in fixed_masks for region in measured):
        raise RuntimeError(f"{name}: a measured region is empty after erosion")
    scaled_pairs: list[dict] = []
    fixed_pairs: list[dict] = []
    profile_pairs: list[dict] = []
    digests: list[str] = []
    for first, second in zip(jobs[0::2], jobs[1::2], strict=True):
        renders = (load(first), load(second))
        for job, render in zip((first, second), renders, strict=True):
            if render.passes != PASSES:
                raise RuntimeError(
                    f"{name}: passes must be {PASSES}, got {render.passes} (seed {job.seed})"
                )
            if not np.array_equal(render.object_id, object_id):
                raise RuntimeError(
                    f"{name}: object id of seed {job.seed} differs from the configuration's"
                )
            digests.append(hashlib.sha256(np.ascontiguousarray(render.sum)).hexdigest())
        scaled, fixed, profile = _pair_values(
            renders[0], renders[1], params, measured, masks, fixed_masks
        )
        scaled_pairs.append(scaled)
        fixed_pairs.append(fixed)
        profile_pairs.append(profile)
    return scaled_pairs, fixed_pairs, profile_pairs, digests


def _keys(measured: Sequence[int]) -> dict[str, list[str]]:
    """The key families of the measured regions (README, Common definitions)."""
    texture = [f"r{r}.{kind}" for r in measured for kind in ("structure_std", "slag.x", "slag.y")]
    means = [f"r{r}.mean.{c}" for r in measured for c in "RGB"]
    estimation = means + [f"r{r}.spectral_slope" for r in measured]
    return {"texture": texture, "estimation": estimation, "erosion_control": means}


# --------------------------------------------------------------------------------------------------
# Hypotheses
# --------------------------------------------------------------------------------------------------


def _effects(a: list[dict], b: list[dict], keys: Mapping[str, list[str]]) -> dict[str, Any]:
    """The effect summaries of ``a`` against ``b`` on the texture family T and the estimation-only
    keys (README, Estimation), with the largest effects over all of these keys and over the T keys
    alone. The T-only maxima are reported because near-zero spectral slopes dominate the all-key
    maxima (amendment 4)."""
    summary = {
        **ensemble.effect_summary(a, b, keys["texture"]),
        **ensemble.effect_summary(a, b, keys["estimation"]),
    }
    texture = {key: summary[key] for key in keys["texture"]}
    return {
        "effect_summary": summary,
        "largest_abs_rel_diff": report.largest_abs_rel_diff(summary),
        "largest_abs_cohen_d": report.largest_abs_cohen_d(summary),
        "largest_abs_rel_diff_texture": report.largest_abs_rel_diff(texture),
        "largest_abs_cohen_d_texture": report.largest_abs_cohen_d(texture),
    }


def _compare(
    runs: Mapping[str, list[dict]], a: str, b: str, alpha: float, keys: Mapping[str, list[str]]
) -> dict[str, Any]:
    """One comparison ``a`` vs ``b``: Holm on the texture family T with the power guard, plus the
    effect summaries (``_effects``) (README, Significance and Estimation)."""
    record = report.family_test(runs[a], runs[b], keys["texture"], alpha, labels=(a, b))
    record["holm_rejected"] = (
        None
        if record["rejected_keys"] is None
        else {key: key in record["rejected_keys"] for key in keys["texture"]}
    )
    record.update(_effects(runs[a], runs[b], keys))
    return record


def _no_difference(tests: Sequence[dict[str, Any]]) -> str:
    """H1 and H4: refuted iff some key is Holm-rejected in some comparison. Supported iff none is
    and every comparison is powered. Otherwise inconclusive, because an underpowered comparison
    cannot reject."""
    if any(test["rejected_keys"] for test in tests):
        return "refuted"
    if all(test["powered"] for test in tests):
        return "supported"
    return "inconclusive"


def _h1(runs, keys, prefix: str) -> dict[str, Any]:
    """H1 for one chain: the texture does not depend on resolution under image-plane jitter."""
    pairs = [
        (f"{prefix}s200", f"{prefix}s400"),
        (f"{prefix}s400", f"{prefix}s800"),
        (f"{prefix}s200", f"{prefix}s800"),
    ]
    level = SIGNIFICANCE / len(pairs)
    tests = [_compare(runs, a, b, level, keys) for a, b in pairs]
    return {"comparisons": tests, "decision": _no_difference(tests)}


def _h2(runs, keys, prefix: str) -> dict[str, Any]:
    """H2 for one chain: pixel jitter makes the texture depend on resolution. Each comparison is
    run at SIGNIFICANCE / 2."""
    pairs = [(f"{prefix}s200_px", f"{prefix}s400"), (f"{prefix}s800_px", f"{prefix}s400")]
    level = SIGNIFICANCE / len(pairs)
    tests = [_compare(runs, a, b, level, keys) for a, b in pairs]
    statuses = []
    for test in tests:
        if not test["powered"]:
            statuses.append("underpowered")
        elif test["rejected_keys"]:
            statuses.append("rejects")
        else:
            statuses.append("no rejection")
    if "underpowered" in statuses:
        decision = "inconclusive"
    elif all(status == "rejects" for status in statuses):
        decision = "supported"
    elif all(status == "no rejection" for status in statuses):
        decision = "refuted"
    else:
        decision = "partially supported"
    return {"comparisons": tests, "statuses": statuses, "decision": decision}


def _unit_pairs(prefix: str, unit: str) -> list[tuple[str, str]]:
    """The two adjacent size pairs of a jitter unit, in the README's order (H3)."""
    small = f"{prefix}s200" if unit == "image-plane" else f"{prefix}s200_px"
    large = f"{prefix}s800" if unit == "image-plane" else f"{prefix}s800_px"
    return [(small, f"{prefix}s400"), (f"{prefix}s400", large)]


def _delta(
    means: Mapping[str, np.ndarray],
    pairs: Sequence[tuple[str, str]],
    columns: np.ndarray | slice = slice(None),
) -> np.ndarray:
    """Delta of H3: the median over the selected texture keys (``columns``, all by default) and the
    two pairs of |rel_diff|, where rel_diff is ``(mean_a - mean_b) / |mean_b|`` as in
    ``ensemble.effect_summary``. Leading axes of ``means`` are kept."""
    rel = [
        np.abs((means[a][..., columns] - means[b][..., columns]) / np.abs(means[b][..., columns]))
        for a, b in pairs
    ]
    return np.median(np.concatenate(rel, axis=-1), axis=-1)


def _h3(runs, keys, prefix: str) -> dict[str, Any]:
    """H3: the jitter unit that makes the look resolution independent, on one chain (README, H3).

    The statistic Delta is computed per unit. Pairs are resampled within each configuration for the
    95% percentile intervals. The decision is made on the row chain only: supported iff
    Delta_image-plane < Delta_pixel.
    """
    texture = keys["texture"]
    structure_cols = np.array(
        [i for i, key in enumerate(texture) if key.endswith(".structure_std")]
    )
    slag_cols = np.array([i for i, key in enumerate(texture) if ".slag." in key])
    names = sorted({name for unit in UNITS for pair in _unit_pairs(prefix, unit) for name in pair})
    data = {
        name: np.asarray([[run[key] for key in texture] for run in runs[name]], dtype=np.float64)
        for name in names
    }
    point_means = {name: data[name].mean(axis=0) for name in names}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    draws = {
        name: rng.integers(0, data[name].shape[0], size=(BOOTSTRAP_RESAMPLES, data[name].shape[0]))
        for name in names
    }
    boot_means = {name: data[name][draws[name]].mean(axis=1) for name in names}
    units: dict[str, Any] = {}
    delta_by_class: dict[str, Any] = {}
    boot_delta: dict[str, np.ndarray] = {}
    for unit in UNITS:
        pairs = _unit_pairs(prefix, unit)
        boot_delta[unit] = _delta(boot_means, pairs)
        pair_medians = {
            f"{a} vs {b}": float(
                np.median(np.abs((point_means[a] - point_means[b]) / np.abs(point_means[b])))
            )
            for a, b in pairs
        }
        units[unit] = {
            "pairs": [f"{a} vs {b}" for a, b in pairs],
            "delta": float(_delta(point_means, pairs)),
            "delta_ci95": [float(v) for v in np.percentile(boot_delta[unit], CI_PERCENTILES)],
            "median_abs_rel_diff_per_pair": pair_medians,
        }
        delta_by_class[unit] = {
            "structure_std": float(_delta(point_means, pairs, structure_cols)),
            "slag": float(_delta(point_means, pairs, slag_cols)),
        }
    diff_boot = boot_delta["pixel"] - boot_delta["image-plane"]
    diff_point = units["pixel"]["delta"] - units["image-plane"]["delta"]
    ci = [float(v) for v in np.percentile(diff_boot, CI_PERCENTILES)]
    difference = {
        "pixel_minus_image_plane": diff_point,
        "ci95": ci,
        "ci_excludes_zero": bool(ci[0] > 0.0 or ci[1] < 0.0),
        "bootstrap_fraction_positive": float(np.mean(diff_boot > 0.0)),
    }
    # The image chain is reported without a decision (README, H3).
    decision = ("supported" if diff_point > 0.0 else "refuted") if prefix else None
    return {
        "chain": "row" if prefix else "image",
        "statistic": "median over the 18 texture keys and 2 size pairs of |rel_diff|",
        "units": units,
        "delta_by_class": delta_by_class,
        "difference": difference,
        "decision": decision,
    }


def _h4(runs, keys) -> dict[str, Any]:
    """H4: with zero jitter the texture still does not depend on resolution (mechanism).

    It uses the row-chain zero family of amendment 1, because the image chain with jitter 0 repeats
    one render.
    """
    s200, s400, s800 = HYPOTHESIS_CONFIGURATIONS["H4"]
    pairs = [(s200, s400), (s400, s800), (s200, s800)]
    level = SIGNIFICANCE / len(pairs)
    tests = [_compare(runs, a, b, level, keys) for a, b in pairs]
    return {"comparisons": tests, "decision": _no_difference(tests)}


def _zero_image_chain(
    jobs: Sequence[Job], object_id: np.ndarray, params: SideParams, measured: Sequence[int]
) -> dict[str, Any]:
    """The image-chain zero-jitter configuration (amendment 1), estimation only.

    ``distinct_renders`` counts the distinct ``sum`` arrays among the renders, compared with
    ``np.array_equal``. The metrics are those of the first render alone, with hp_a = hp_b: the two
    halves are that one render, so no noise is separated and no p-value is computed. The display of
    the summed pair is then that of 2 * sum at 2 * PASSES passes, which equals the display of sum at
    PASSES passes.
    """
    distinct: list[np.ndarray] = []
    for job in jobs:
        render = load(job)
        if render.passes != PASSES:
            raise RuntimeError(f"passes must be {PASSES}, got {render.passes} (seed {job.seed})")
        if not any(np.array_equal(render.sum, kept) for kept in distinct):
            distinct.append(render.sum)
    first = load(jobs[0])
    scaled, _fixed, _profile = _pair_values(
        first,
        first,
        params,
        measured,
        _masks(object_id, params.erosion),
        _masks(object_id, FIXED_EROSION),
    )
    return {
        "renders": len(jobs),
        "distinct_renders": len(distinct),
        "noise_separated": False,
        "first_render": scaled,
    }


def _jitter_footprint(
    runs: Mapping[str, list[dict]], keys: Mapping[str, list[str]]
) -> dict[str, Any]:
    """Estimation only, no verdict (amendment 1): row_j0_sN vs row_sN at N = 200, 400 and 800, the
    effect of the jitter footprint at a fixed chain and size."""
    return {
        str(side): {
            "comparison": f"row_j0_s{side} vs row_s{side}",
            **_effects(runs[f"row_j0_s{side}"], runs[f"row_s{side}"], keys),
        }
        for side in FOOTPRINT_SIDES
    }


def _h5(scaled_runs, fixed_runs, control_keys: Sequence[str]) -> dict[str, Any]:
    """H5: the scaled erosion, not the renderer, explains the region-mean trend.

    Supported iff for every region-mean key and both adjacent pairs, |rel_diff| with the scaled
    erosion is smaller than with the fixed erosion. There are no p-values (README, H5).
    """
    rows: list[dict[str, Any]] = []
    for a, b in (("s200", "s400"), ("s400", "s800")):
        scaled = ensemble.effect_summary(scaled_runs[a], scaled_runs[b], control_keys)
        fixed = ensemble.effect_summary(fixed_runs[a], fixed_runs[b], control_keys)
        for key in control_keys:
            rel_scaled = scaled[key]["rel_diff"]
            rel_fixed = fixed[key]["rel_diff"]
            if rel_scaled is None or rel_fixed is None:
                raise RuntimeError(f"H5: rel_diff of {key} is undefined")
            rows.append(
                {
                    "pair": f"{a} vs {b}",
                    "key": key,
                    "rel_diff_scaled": rel_scaled,
                    "rel_diff_fixed": rel_fixed,
                    "scaled_is_smaller": abs(rel_scaled) < abs(rel_fixed),
                }
            )
    failing = [f"{row['pair']} {row['key']}" for row in rows if not row["scaled_is_smaller"]]
    return {
        "rows": rows,
        "failing": failing,
        "decision": "refuted" if failing else "supported",
    }


# --------------------------------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------------------------------


def _preview(img8: np.ndarray) -> np.ndarray:
    """A PREVIEW_SIDE x PREVIEW_SIDE tile. A side that is a multiple of PREVIEW_SIDE is box-averaged
    to it, and a side that divides PREVIEW_SIDE is repeated (smoke scale only). Display only."""
    side = img8.shape[0]
    if side >= PREVIEW_SIDE and side % PREVIEW_SIDE == 0:
        return report.block_preview(img8, side // PREVIEW_SIDE)
    if side < PREVIEW_SIDE and PREVIEW_SIDE % side == 0:
        factor = PREVIEW_SIDE // side
        return np.repeat(np.repeat(img8, factor, axis=0), factor, axis=1)
    raise ValueError(f"cannot make a {PREVIEW_SIDE} px tile from side {side}")


def _paint(canvas: np.ndarray, xs: np.ndarray, ys: np.ndarray, color: tuple[int, int, int]) -> None:
    height, width = canvas.shape[:2]
    keep = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
    canvas[ys[keep], xs[keep]] = color


def _draw_line(
    canvas: np.ndarray,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    color: tuple[int, int, int],
    dashed: bool = False,
) -> None:
    """A 2-px line, sampled at one-pixel steps. A dashed line keeps DASH_ON_PX of every
    DASH_PERIOD_PX samples."""
    steps = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
    t = np.linspace(0.0, 1.0, steps)
    xs = np.rint(x0 + t * (x1 - x0)).astype(np.int64)
    ys = np.rint(y0 + t * (y1 - y0)).astype(np.int64)
    if dashed:
        keep = (np.arange(steps) % DASH_PERIOD_PX) < DASH_ON_PX
        xs, ys = xs[keep], ys[keep]
    for dx, dy in ((0, 0), (1, 0), (0, 1)):
        _paint(canvas, xs + dx, ys + dy, color)


def _map_x(k: float, left: float) -> float:
    lo, hi = X_RANGE
    return left + (k - lo) / (hi - lo) * PANEL_W


def _map_y(value: float, lo: float, hi: float, top: float) -> float:
    return top + (hi - value) / (hi - lo) * PANEL_H


def _draw_panel(
    canvas: np.ndarray,
    left: float,
    top: float,
    lo: float,
    hi: float,
    series: Sequence[tuple[tuple[int, int, int], bool, float, list[tuple[float, float, float]]]],
) -> None:
    """One panel: axes, a zero line when it is in range, and each series as mean +- sd points,
    joined by lines."""
    right, bottom = left + PANEL_W, top + PANEL_H
    _draw_line(canvas, left, top, left, bottom, AXIS_GREY)
    _draw_line(canvas, left, bottom, right, bottom, AXIS_GREY)
    for k in PROFILE_LAGS:
        x = _map_x(k, left)
        _draw_line(canvas, x, bottom, x, bottom + TICK_PX, AXIS_GREY)
    if lo < 0.0 < hi:
        zero = _map_y(0.0, lo, hi, top)
        _draw_line(canvas, left, zero, right, zero, ZERO_GREY, dashed=True)
    for color, dashed, offset, points in series:
        xs = [_map_x(k, left) + offset for k, _mean, _sd in points]
        ys = [_map_y(mean, lo, hi, top) for _k, mean, _sd in points]
        for (_k, mean, sd), x in zip(points, xs, strict=True):
            y_top = _map_y(mean + sd, lo, hi, top)
            y_bottom = _map_y(mean - sd, lo, hi, top)
            _draw_line(canvas, x, y_top, x, y_bottom, color)
            _draw_line(canvas, x - CAP_HALF_PX, y_top, x + CAP_HALF_PX, y_top, color)
            _draw_line(canvas, x - CAP_HALF_PX, y_bottom, x + CAP_HALF_PX, y_bottom, color)
        for x0, y0, x1, y1 in zip(xs, ys, xs[1:], ys[1:], strict=False):
            _draw_line(canvas, x0, y0, x1, y1, color, dashed)
        for x, y in zip(xs, ys, strict=True):
            square = np.arange(-MARKER_HALF_PX, MARKER_HALF_PX + 1)
            gx, gy = np.meshgrid(square + round(x), square + round(y))
            _paint(canvas, gx.ravel(), gy.ravel(), color)


def _profile_points(profile_runs: Sequence[dict], axis: str) -> list[tuple[float, float, float]]:
    """(k, mean, sd over pairs) of the profile at each lag index k, for one direction."""
    points: list[tuple[float, float, float]] = []
    for k in PROFILE_LAGS:
        values = np.asarray([run[f"k{k}.{axis}"] for run in profile_runs], dtype=np.float64)
        points.append((float(k), float(np.mean(values)), float(np.std(values, ddof=1))))
    return points


def _slag_profile_figure(profile: Mapping[str, list[dict]]) -> np.ndarray:
    """fig_slag_profile.png: the region-4 structure autocorrelation against the image-plane lag,
    for each direction (rows), native side (columns) and series (PROFILE_SERIES)."""
    width = LEFT_MARGIN + len(PROFILE_SIDES) * CELL_W
    height = TOP_MARGIN + 2 * (PANEL_H + ROW_GAP) + LEGEND_H
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    for row, axis in enumerate(("x", "y")):
        top = TOP_MARGIN + row * (PANEL_H + ROW_GAP)
        values = [
            point
            for _label, _color, _dashed, names in PROFILE_SERIES
            for side in PROFILE_SIDES
            for point in _profile_points(profile[names[side]], axis)
        ]
        lo = min(mean - sd for _k, mean, sd in values)
        hi = max(mean + sd for _k, mean, sd in values)
        span = hi - lo if hi > lo else 1.0
        lo, hi = lo - Y_PAD * span, hi + Y_PAD * span
        for col, side in enumerate(PROFILE_SIDES):
            left = LEFT_MARGIN + col * CELL_W
            series = []
            for index, (_label, color, dashed, names) in enumerate(PROFILE_SERIES):
                offset = (index - (len(PROFILE_SERIES) - 1) / 2) * SERIES_OFFSET_PX
                series.append((color, dashed, offset, _profile_points(profile[names[side]], axis)))
            _draw_panel(canvas, left, top, lo, hi, series)
    legend_y = TOP_MARGIN + 2 * (PANEL_H + ROW_GAP) + LEGEND_H // 2
    for index, (_label, color, dashed, _names) in enumerate(PROFILE_SERIES):
        x0 = LEFT_MARGIN + index * LEGEND_CELL_W
        _draw_line(canvas, x0, legend_y, x0 + LEGEND_SAMPLE_PX, legend_y, color, dashed)
    return canvas


# --------------------------------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------------------------------


def _largest_text(entry: Mapping[str, Any] | None) -> str:
    """A largest-effect entry (``{"key", "value"}``) as ``value (key)``, or ``n/a``."""
    return "n/a" if entry is None else f"{entry['value']:.4g} ({entry['key']})"


def _print_comparison(test: Mapping[str, Any], say: Callable[[str], None]) -> None:
    rejected = test["rejected_keys"]
    count = "underpowered (not run)" if rejected is None else f"rejected={len(rejected)}"
    say(
        f"  {test['comparison']}: alpha={test['alpha']:.4g} keys={test['n_keys']} {count} "
        f"min_attainable_p={test['min_attainable_p']:.3g} "
        f"threshold={test['holm_first_threshold']:.3g}"
    )
    say(
        f"    all keys: largest |rel|={_largest_text(test['largest_abs_rel_diff'])} "
        f"largest |d|={_largest_text(test['largest_abs_cohen_d'])}"
    )
    say(
        f"    texture keys: largest |rel|={_largest_text(test['largest_abs_rel_diff_texture'])} "
        f"largest |d|={_largest_text(test['largest_abs_cohen_d_texture'])}"
    )
    if rejected:
        say(f"    rejected keys: {rejected}")


def _print_h3(test: Mapping[str, Any], say: Callable[[str], None]) -> None:
    for unit, entry in test["units"].items():
        say(
            f"  {test['chain']} chain, {unit}: Delta={entry['delta']:.4g} "
            f"95% CI [{entry['delta_ci95'][0]:.4g}, {entry['delta_ci95'][1]:.4g}] "
            f"pairs {entry['pairs']}"
        )
    diff = test["difference"]
    say(
        f"  difference pixel - image-plane: {diff['pixel_minus_image_plane']:.4g} "
        f"95% CI [{diff['ci95'][0]:.4g}, {diff['ci95'][1]:.4g}] "
        f"excludes 0: {diff['ci_excludes_zero']} "
        f"bootstrap fraction > 0: {diff['bootstrap_fraction_positive']:.4g}"
    )


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.pairs < 1 or args.scale < 1:
        raise ValueError("--pairs and --scale must be >= 1")
    if args.scale > 1 and args.out_dir.resolve() == EXP_DIR:
        raise ValueError(
            "a smoke run (--scale above 1) must not write the committed outputs: pass --out-dir"
        )
    jobs_module = report.load_jobs_module(DEFAULT_JOBS)
    reference = int(jobs_module.REFERENCE_SIDE)
    ensembles = jobs_module.build_ensembles(args.pairs, args.scale)
    _check_design_table(jobs_module.DESIGN)
    _check_design(ensembles, int(jobs_module.BLOCK), args.pairs, args.scale)
    all_jobs = [job for name in TABLE for job in ensembles[name]]
    if args.scale > 1:
        status = run_jobs(all_jobs)
        if status.remaining:
            raise RuntimeError(f"smoke renders incomplete: {status.remaining} jobs remain")

    notes: list[str] = []
    params = {
        name: side_params(side // args.scale, reference, args.scale, notes)
        for name, (side, _chain, _jitter, _block) in TABLE.items()
    }
    object_ids = {name: load(jobs[0]).object_id for name, jobs in ensembles.items()}
    for name, (side, _chain, _jitter, _block) in TABLE.items():
        first = next(other for other, (other_side, *_rest) in TABLE.items() if other_side == side)
        if not np.array_equal(object_ids[name], object_ids[first]):
            raise RuntimeError(f"object id of {name} differs from {first} (same native side)")
    # A region is measured only if it survives both erosions, the scaled one and H5's fixed one,
    # in every configuration (README, Common definitions; H5 needs the fixed-erosion means too).
    nonempty = {
        name: set(_masks(object_ids[name], params[name].erosion))
        & set(_masks(object_ids[name], FIXED_EROSION))
        for name in TABLE
    }
    measured = sorted(set.intersection(*nonempty.values()))
    union = set().union(*nonempty.values())
    absent = sorted(set(DIFFUSE_REGION_IDS) - union)
    dropped = sorted(union - set(measured))
    if not measured or PROFILE_REGION not in measured:
        raise RuntimeError(
            f"the measured regions {measured} must include the profile region {PROFILE_REGION}"
        )
    keys = _keys(measured)

    scaled_runs: dict[str, list[dict]] = {}
    fixed_runs: dict[str, list[dict]] = {}
    profile_runs: dict[str, list[dict]] = {}
    digests: dict[str, list[str]] = {}
    for name in TABLE:
        scaled_runs[name], fixed_runs[name], profile_runs[name], digests[name] = (
            _measure_configuration(name, ensembles[name], object_ids[name], params[name], measured)
        )
    # Replicate check: the 2 * pairs renders of a configuration should be distinct. The oracle's
    # output depends on the seed only through the jitter, the U2 draw (--u2 independent) and the
    # lane K0 (lane and row chains). A zero-jitter image-chain configuration with the default
    # --u2 same therefore repeats one render. The check reports this; it does not stop the run.
    replicates = {
        name: {"renders": len(digest_list), "distinct": len(set(digest_list))}
        for name, digest_list in digests.items()
    }
    design_warnings = [
        f"{name}: {counts['distinct']} distinct renders among {counts['renders']}; the replicates "
        "are not independent, so pair tests on this configuration are degenerate"
        for name, counts in replicates.items()
        if counts["distinct"] < counts["renders"]
    ]
    # Every printed line of a smoke run is prefixed (amendment 3).
    prefix = SMOKE_PREFIX if args.scale > 1 else ""

    def say(line: str) -> None:
        print(f"{prefix}{line}")

    for warning in design_warnings:
        say(f"WARNING: {warning}")

    h1_image = _h1(scaled_runs, keys, "")
    h1_row = _h1(scaled_runs, keys, "row_")
    h2_image = _h2(scaled_runs, keys, "")
    h2_row = _h2(scaled_runs, keys, "row_")
    h3_image = _h3(scaled_runs, keys, "")
    h3_row = _h3(scaled_runs, keys, "row_")
    h4 = _h4(scaled_runs, keys)
    h5 = _h5(scaled_runs, fixed_runs, keys["erosion_control"])
    zero_image = {
        name: _zero_image_chain(ensembles[name], object_ids[name], params[name], measured)
        for name in ZERO_IMAGE_CHAIN
    }
    footprint = _jitter_footprint(scaled_runs, keys)
    decisions = {
        "H1-image": h1_image["decision"],
        "H1-row": h1_row["decision"],
        "H2-image": h2_image["decision"],
        "H2-row": h2_row["decision"],
        "H3": h3_row["decision"],
        "H4": h4["decision"],
        "H5": h5["decision"],
    }
    # A Holm-tested decision is not interpretable if one of its configurations has replicates that
    # repeat a render. The exact pair test then compares identical pairs, so the smallest attainable
    # p-value (README, Power) rejects every key whose two configurations differ at all. The decision
    # is still written as the README's rule defines it, and this flag marks it.
    degenerate = {name for name, c in replicates.items() if c["distinct"] < c["renders"]}
    not_interpretable = {
        hypothesis: sorted(set(names) & degenerate)
        for hypothesis, names in HYPOTHESIS_CONFIGURATIONS.items()
    }
    not_interpretable = {hyp: names for hyp, names in not_interpretable.items() if names}

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    tiles: dict[str, np.ndarray] = {}
    for _stem, names in GRID_LAYOUT:
        for name in names:
            if name not in tiles:
                tiles[name] = _preview(report.ab8_of_pair(ensembles[name]))
    grid_paths = [out_dir / f"fig_grid_{stem}.png" for stem, _names in GRID_LAYOUT]
    for path, (_stem, names) in zip(grid_paths, GRID_LAYOUT, strict=True):
        write_png(path, report.mosaic([tiles[name] for name in names], len(names)))
    profile_path = out_dir / "fig_slag_profile.png"
    write_png(profile_path, _slag_profile_figure(profile_runs))
    for path in (*grid_paths, profile_path):
        size = path.stat().st_size
        if size > MAX_FIGURE_BYTES:
            raise RuntimeError(f"{path.name} is {size} bytes, over the limit {MAX_FIGURE_BYTES}")
    grid_files = [
        {"file": path.name, "configurations": list(names)}
        for path, (_stem, names) in zip(grid_paths, GRID_LAYOUT, strict=True)
    ]

    results = {
        "experiment": EXPERIMENT,
        "significance": SIGNIFICANCE,
        "pairs": args.pairs,
        "scale": args.scale,
        "smoke": args.scale > 1,
        "passes": PASSES,
        "reference_side": reference,
        "highpass": {"kind": "gaussian", "size_reference_px": metrics.HIGHPASS_SIZE},
        "fixed_erosion_px": FIXED_EROSION,
        "lag_unit_side": LAG_UNIT_SIDE,
        "smoke_roundings": sorted(set(notes)),
        "replicates": replicates,
        "design_warnings": design_warnings,
        "parameters": {
            str(params[name].side): {
                "sigma_px": params[name].sigma,
                "erosion_px": params[name].erosion,
                "lag_px": params[name].lag,
                "profile_lag_px": list(params[name].profile_lag),
                "spectral_f_max": params[name].spectral_f_max,
            }
            for name in TABLE
        },
        "regions": {
            "diffuse_ids": list(DIFFUSE_REGION_IDS),
            "measured": measured,
            "absent": absent,
            "dropped_at_this_scale_or_erosion": dropped,
            "profile_region": PROFILE_REGION,
        },
        "object_id_values": {
            name: sorted(int(v) for v in np.unique(object_ids[name])) for name in TABLE
        },
        "configurations": {
            name: {
                "side": TABLE[name][0] // args.scale,
                "native_side": TABLE[name][0],
                "chain": TABLE[name][1],
                "jitter_image_plane": str(TABLE[name][2]),
                "options": {k: v for k, v in ensembles[name][0].options},
                "seeds": [job.seed for job in ensembles[name]],
            }
            for name in TABLE
        },
        "key_families": keys,
        "hypotheses": {
            "H1": {"image": h1_image, "row": h1_row},
            "H2": {"image": h2_image, "row": h2_row},
            "H3": {"image": h3_image, "row": h3_row},
            "H4": h4,
            "H5": h5,
        },
        "decisions": decisions,
        "decisions_not_interpretable": {
            hypothesis: {"configurations": names, "decision": decisions[hypothesis]}
            for hypothesis, names in not_interpretable.items()
        },
        "zero_image_chain": {
            "estimation_only": True,
            "noise_separated": False,
            "configurations": zero_image,
        },
        "jitter_footprint": {"estimation_only": True, "comparisons": footprint},
        "summary": report.summary_table(scaled_runs, keys["texture"] + keys["estimation"]),
        "summary_fixed_erosion": report.summary_table(fixed_runs, keys["erosion_control"]),
        "figures": {
            "fig_grid": {
                "tile_px": PREVIEW_SIDE,
                "tiles_per_file": len(GRID_LAYOUT[0][1]),
                "files": grid_files,
            },
            "fig_slag_profile": {
                "file": "fig_slag_profile.png",
                "rows": ["slag.x", "slag.y"],
                "columns_native_side": list(PROFILE_SIDES),
                "x": "lag index k, image-plane lag k/200 of the side",
                "series": [
                    {"label": label, "rgb": list(color), "dashed": dashed, "names": names}
                    for label, color, dashed, names in PROFILE_SERIES
                ],
            },
        },
    }
    report.write_results_json(out_dir / "results.json", results)

    say(f"pairs={args.pairs} scale={args.scale} sides={sorted({p.side for p in params.values()})}")
    for side in sorted({p.side for p in params.values()}):
        entry = next(p for p in params.values() if p.side == side)
        say(
            f"  side {entry.side}: sigma={entry.sigma:.6g} px erosion={entry.erosion} px "
            f"lag={entry.lag} px "
            f"profile lags={list(entry.profile_lag)} px spectral f_max={entry.spectral_f_max}"
        )
    for note in sorted(set(notes)):
        say(f"  {note}")
    say(f"measured regions {measured}, absent {absent}, dropped {dropped}")
    say(
        f"H1 image-plane (s200, s400, s800) at level {SIGNIFICANCE / 3:.4g}: {h1_image['decision']}"
    )
    for test in h1_image["comparisons"]:
        _print_comparison(test, say)
    say(f"H1 row chain at level {SIGNIFICANCE / 3:.4g}: {h1_row['decision']}")
    for test in h1_row["comparisons"]:
        _print_comparison(test, say)
    say(
        f"H2 image chain at level {SIGNIFICANCE / 2:.4g}: {h2_image['decision']} "
        f"{h2_image['statuses']}"
    )
    for test in h2_image["comparisons"]:
        _print_comparison(test, say)
    say(f"H2 row chain at level {SIGNIFICANCE / 2:.4g}: {h2_row['decision']} {h2_row['statuses']}")
    for test in h2_row["comparisons"]:
        _print_comparison(test, say)
    say("H3 (decision on the row chain):")
    _print_h3(h3_row, say)
    _print_h3(h3_image, say)
    say(f"H3 decision: {h3_row['decision']}")
    say(f"H4 zero jitter, row chain, at level {SIGNIFICANCE / 3:.4g}: {h4['decision']}")
    for test in h4["comparisons"]:
        _print_comparison(test, say)
    say(f"H5 erosion: {h5['decision']}; failing: {len(h5['failing'])} of {len(h5['rows'])}")
    for item in h5["failing"]:
        say(f"    fails: {item}")
    say(f"decisions (README rule): {decisions}")
    for hypothesis, names in not_interpretable.items():
        say(
            f"NOT INTERPRETABLE {hypothesis} ({decisions[hypothesis]} by the README rule): "
            f"configurations {names} have replicates that repeat a render (see the WARNING lines)"
        )
    for name in ZERO_IMAGE_CHAIN:
        entry = zero_image[name]
        say(
            f"zero jitter, image chain, {name} (estimation only): distinct renders "
            f"{entry['distinct_renders']} of {entry['renders']}; no noise is separated"
        )
    for side in FOOTPRINT_SIDES:
        entry = footprint[str(side)]
        say(
            f"jitter footprint {entry['comparison']} (estimation only): texture keys largest "
            f"|rel|={_largest_text(entry['largest_abs_rel_diff_texture'])} "
            f"|d|={_largest_text(entry['largest_abs_cohen_d_texture'])}"
        )
    say(
        f"wrote {out_dir / 'results.json'}, the grid files fig_grid_<row>.png and "
        f"{out_dir / 'fig_slag_profile.png'}"
    )


if __name__ == "__main__":
    main()
