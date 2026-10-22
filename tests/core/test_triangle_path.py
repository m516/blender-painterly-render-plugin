"""The triangle path is statistically indistinguishable from the oracle (T3.17).

Blender scenes are triangle meshes, and Embree intersects triangles in float32, so the triangle
scene of SPEC §9 cannot be bit-identical to the analytic one of T3.16. This file shows that the
difference is not visible in the look:

- the fast test compares the object-id maps of the analytic and the triangle scene at 64 px. The
  ids agree exactly on the interior pixels, those whose 3x3 neighbourhood in the analytic map
  holds a single id (T5.4's 3x3 criterion, applied here to every id, because both scenes keep the
  analytic spheres). The edge pixels legitimately differ: the unjittered rays of columns 16 and 48
  pass within a relative 4.4e-8 of the back wall's vertical edges
  (``tan((double)float(pi/4))`` = 1 + 4.4e-8, SPEC §7), which is below float32 resolution, and
  the same holds along the floor-wall edges and where the spheres meet the floor. Their number is
  reported, not asserted;
- the slow test compares the triangle scene with the oracle on an ensemble of 8 pairs at 400 px
  with P = 32 and the chain ``image``. The decision is the card's: ``compare_ensembles`` with
  ``alpha = 0.01`` on ``metrics.realization_free_key_family(metrics.diffuse_key_family(keys))``
  must reject nothing.

The realization-dependent keys (``pattern_corr`` and ``block_rmse``) measure agreement with the
oracle's particular sample sequence, and Embree's float32 hits shift the K consumption, so the
family leaves them out. The K consumption itself is reported, not asserted.

The oracle's renders go into the render cache of ``painterly_analysis``, under this clone's own
``.cache`` directory, which is git-ignored: no render ever reaches another checkout's cache (R7).
"""

import importlib.util
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import _painterly
import numpy as np
import pytest

# pytest runs with --import-mode=importlib (pyproject.toml), which puts no test directory on
# sys.path, so "import scenes" would fail at collection. The module is therefore loaded by path.
REPO_ROOT = Path(__file__).resolve().parents[2]

# R12: in a worker clone this project's own analysis package must be the one under test. The
# shared environment installs painterly_analysis editable from another checkout, so when
# PYTHONPATH does not name this clone's analysis directory the import resolves there instead and
# the clone's own copy is never loaded. The check command sets PYTHONPATH="$PWD/analysis" for
# that reason; this module makes the resolution correct either way, so the whole test session
# imports the clone's package. The stale copy is dropped from sys.modules as well, because an
# earlier test module may already have imported it.
_ANALYSIS_DIR = REPO_ROOT / "analysis"
if str(_ANALYSIS_DIR) in sys.path:
    sys.path.remove(str(_ANALYSIS_DIR))
sys.path.insert(0, str(_ANALYSIS_DIR))
for _stale in [name for name in sys.modules if name.split(".")[0] == "painterly_analysis"]:
    del sys.modules[_stale]

from painterly_analysis import DIFFUSE_REGION_IDS, ensemble, metrics, report  # noqa: E402
from painterly_analysis.experiment import Job, ensemble_jobs, load, run_jobs  # noqa: E402
from painterly_analysis.io import read_ppm  # noqa: E402

_SCENES_PATH = Path(__file__).with_name("scenes.py")
_SCENES_SPEC = importlib.util.spec_from_file_location("scenes", _SCENES_PATH)
assert _SCENES_SPEC is not None
assert _SCENES_SPEC.loader is not None
scenes = importlib.util.module_from_spec(_SCENES_SPEC)
_SCENES_SPEC.loader.exec_module(scenes)

# The fast test's image side in pixels. The object-id map is the object id of the unjittered
# primary hit (SPEC §9), so it does not depend on the number of passes.
FAST_SIZE = 64
FAST_PASSES = 1
# The slow test's design: 8 pairs of half renders at 400 px, P = 32 per half render, the chain
# "image" (the card's "Slow" bullet).
SLOW_SIZE = 400
SLOW_PASSES = 32
SLOW_PAIRS = 8
# The family-wise level of the decision (the card's "Slow" bullet: compare_ensembles alpha=0.01).
# This is the statistical level, not the oracle's own --alpha knob, which is 0 (SPEC §4).
ALPHA = 0.01
# The seed block of the ensemble. A block is 16 seeds, one per half render of the 8 pairs, and the
# base seed is 16 times the block index (the experiments' convention). Block 68 is the first free
# block after experiment 009's last block (67), so no seed is shared with an earlier experiment.
SEED_BLOCK = 68
SEEDS_PER_BLOCK = 16
BASE_SEED = SEEDS_PER_BLOCK * SEED_BLOCK
# The number of renders that run at the same time. The core's image chain is one sequence, so a
# render uses one thread of its own; the renders of the different half renders are independent.
WORKERS = 4
# The render cache of the oracle's renders: this clone's own git-ignored .cache directory.
CACHE_DIR = REPO_ROOT / ".cache" / "test-renders"
# The golden reference of SPEC §0, the reference image of the metrics.
REFERENCE_PPM = REPO_ROOT / "tests" / "data" / "reference" / "smallpaint_painterly.ppm"


def _single_id_neighbourhood(object_id: np.ndarray) -> np.ndarray:
    """The pixels whose 3x3 neighbourhood holds a single id (T5.4's 3x3 criterion).

    A pixel counts only when its whole 3x3 window lies inside the image, so that every pixel of
    the window is compared: a border pixel has no full 3x3 neighbourhood and is not interior. The
    result is a boolean array of the image's shape.
    """
    height, width = object_id.shape
    uniform = np.ones((height, width), dtype=bool)
    rows = np.arange(height)
    cols = np.arange(width)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            shifted_rows = rows + dy
            shifted_cols = cols + dx
            valid = ((shifted_rows >= 0) & (shifted_rows < height))[:, None] & (
                (shifted_cols >= 0) & (shifted_cols < width)
            )[None, :]
            neighbour = object_id[
                np.ix_(
                    np.clip(shifted_rows, 0, height - 1),
                    np.clip(shifted_cols, 0, width - 1),
                )
            ]
            uniform &= (neighbour == object_id) & valid
    return uniform


def test_the_analysis_package_under_test_is_this_clones_own() -> None:
    """The ``painterly_analysis`` package is the clone's own, not another checkout's.

    R12: in a worker clone the shared environment installs ``painterly_analysis`` editable from
    another checkout, so an import that does not name this clone's ``analysis`` directory resolves
    there. The check command sets ``PYTHONPATH="$PWD/analysis"`` for that reason; the module
    header makes the resolution correct either way. This test pins that outcome, so a later edit
    that drops the header fails here instead of silently testing another checkout's code.
    """
    import painterly_analysis

    package_dir = Path(painterly_analysis.__file__).resolve().parent
    assert package_dir == (REPO_ROOT / "analysis" / "painterly_analysis").resolve(), (
        f"painterly_analysis comes from {package_dir}, not from this clone's analysis directory"
    )


def _object_ids(builder: Any, size: int) -> np.ndarray:
    """The object-id map of a scene of ``builder``, at ``size`` px."""
    scene = _painterly.Scene()
    builder(scene, size=size)
    session = _painterly.Session(scene, 1)
    session.start(FAST_PASSES, 1)
    assert session.wait() is True, "the core's render did not finish"
    return session.object_id()


def test_the_triangle_scene_keeps_the_object_ids_on_the_interior_pixels() -> None:
    """The triangle scene's object ids equal the analytic ones on the interior pixels.

    The edge pixels differ, because Embree's float32 hits cannot resolve the edges of the box
    (SPEC §7's 4.4e-8). Their number is reported, not asserted.
    """
    analytic = _object_ids(scenes.build_smallpaint_scene, FAST_SIZE)
    triangle = _object_ids(scenes.build_smallpaint_scene_triangles, FAST_SIZE)

    interior = _single_id_neighbourhood(analytic)
    assert np.array_equal(triangle[interior], analytic[interior]), (
        f"{int(np.count_nonzero(triangle[interior] != analytic[interior]))} interior pixels of "
        f"{int(np.count_nonzero(interior))} carry a different object id"
    )

    differing = int(np.count_nonzero(analytic != triangle))
    edge_differing = int(np.count_nonzero((analytic != triangle) & ~interior))
    print(
        f"object ids: {int(interior.sum())} interior pixels agree, "
        f"{differing} pixels differ in total, {edge_differing} of them on the edges"
    )


def _oracle_jobs(jitter: float) -> list[Job]:
    """The oracle's jobs of the slow test: 16 half renders, one per seed.

    The options are the reference knobs of ``scenes.ORACLE_EXACT_KNOBS`` (the oracle's exact
    Halton generator, as T3.16's parity test uses), the chain "image" and the size and the passes
    of the card. The oracle's thread count is set by the harness, one per job.
    """
    return ensemble_jobs(
        "triangle_path_oracle",
        SLOW_PAIRS,
        base_seed=BASE_SEED,
        size=SLOW_SIZE,
        passes=SLOW_PASSES,
        chain="image",
        ghost="all",
        # The oracle's --alpha knob is the SPEC §4 normalization blend, 0 (not the statistical
        # level ALPHA above).
        alpha=0.0,
        u2="same",
        continue_after_emitter=True,
        jitter=jitter,
        **scenes.ORACLE_EXACT_KNOBS,
    )


def _core_half_render(seed: int) -> tuple[np.ndarray, np.ndarray]:
    """One half render of the triangle scene: its sum and its K consumption.

    The render is of the triangle scene of SPEC §9 with the chain "image" and the given seed.
    The sum is the core's ``combined`` buffer, the same quantity the oracle writes as ``sum``.
    """
    scene = _painterly.Scene()
    scenes.build_smallpaint_scene_triangles(scene, size=SLOW_SIZE)
    scene.set_integrator(chain="image", seed=seed)
    session = _painterly.Session(scene, 1)
    session.start(SLOW_PASSES, 1)
    assert session.wait() is True, "the core's render did not finish"
    return session.combined(), session.k_consumed()


def _print_table(
    triangle_runs: list[dict[str, float]],
    oracle_runs: list[dict[str, float]],
    comparison: ensemble.Comparison,
    keys: list[str],
) -> None:
    """The table of the comparison: the two ensembles' means, the effect and the p-value."""
    effects = ensemble.effect_summary(triangle_runs, oracle_runs, keys)
    print(
        f"{'key':<22}{'mean tri':>12}{'sd tri':>10}{'mean oracle':>13}{'sd oracle':>11}"
        f"{'rel diff':>12}{'cohen d':>11}{'p':>10}  rejected"
    )
    for key in keys:
        effect = effects[key]
        rel_diff = effect["rel_diff"]
        cohen_d = effect["cohen_d"]
        print(
            f"{key:<22}"
            f"{effect['mean_a']:>12.6g}{effect['sd_a']:>10.4g}"
            f"{effect['mean_b']:>13.6g}{effect['sd_b']:>11.4g}"
            f"{('n/a' if rel_diff is None else format(rel_diff, '.4g')):>12}"
            f"{('n/a' if cohen_d is None else format(cohen_d, '.4g')):>11}"
            f"{comparison.pvalues[key]:>10.4g}  {comparison.rejected[key]}"
        )


@pytest.mark.slow
def test_the_triangle_scene_is_indistinguishable_from_the_oracle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The triangle scene and the oracle are indistinguishable on the realization-free family.

    The decision is the card's: ``compare_ensembles`` at ``alpha = 0.01`` on
    ``metrics.realization_free_key_family(metrics.diffuse_key_family(keys))`` must reject
    nothing. The table is printed, and the K consumption is reported.
    """
    # The oracle's renders go into this clone's own cache (R7).
    monkeypatch.setenv("PAINTERLY_CACHE", str(CACHE_DIR))

    reference8 = read_ppm(REFERENCE_PPM)

    # The oracle's half renders. The jitter is the core's, so both displace their rays by the
    # same amount (SPEC §7).
    triangle_scene = _painterly.Scene()
    scenes.build_smallpaint_scene_triangles(triangle_scene, size=SLOW_SIZE)
    jobs = _oracle_jobs(scenes.oracle_jitter(triangle_scene))
    run_jobs(jobs, workers=WORKERS)

    # The masks are the oracle's object-id map: both ensembles are measured on the same pixels,
    # so the comparison sees the shading, not a difference of masks.
    oracle_object_id = load(jobs[0]).object_id
    measure_map = report.diffuse_only(oracle_object_id, DIFFUSE_REGION_IDS)

    oracle_runs = report.ensemble_metrics(
        jobs, reference8, regions=DIFFUSE_REGION_IDS, object_id=oracle_object_id
    )

    # The triangle scene's half renders, and their metrics on the same masks. The half renders
    # are independent of each other, so they run in parallel.
    seeds = [job.seed for job in jobs]
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        half_renders = list(pool.map(_core_half_render, seeds))

    triangle_runs = []
    for index in range(0, len(half_renders), 2):
        sum_a, k_a = half_renders[index]
        sum_b, _k_b = half_renders[index + 1]
        triangle_runs.append(metrics.measure(sum_a, sum_b, SLOW_PASSES, reference8, measure_map))

    keys = metrics.realization_free_key_family(metrics.diffuse_key_family(oracle_runs[0]))
    comparison = ensemble.compare_ensembles(triangle_runs, oracle_runs, keys, alpha=ALPHA)
    _print_table(triangle_runs, oracle_runs, comparison, keys)

    # The K consumption: Embree's float32 hits shift the sample sequence, so the counts differ.
    # The number is reported, never asserted (the card).
    equal_pixels = 0
    core_total = 0
    oracle_total = 0
    for index in range(0, len(half_renders), 2):
        k_a = half_renders[index][1]
        k_b = half_renders[index + 1][1]
        core_total += int(k_a.sum()) + int(k_b.sum())
        for k_core, job in ((k_a, jobs[index]), (k_b, jobs[index + 1])):
            equal_pixels += int(np.count_nonzero(k_core == load(job).k_consumed))
            oracle_total += int(load(job).k_consumed.sum())
    total_pixels = SLOW_SIZE * SLOW_SIZE * len(half_renders)
    print(
        f"k_consumed equals the oracle's on {equal_pixels} of {total_pixels} pixels; "
        f"the triangle scene draws {core_total} times, the oracle {oracle_total}"
    )

    assert comparison.indistinguishable, (
        f"{[key for key in keys if comparison.rejected[key]]} differ between the triangle scene "
        f"and the oracle at alpha={ALPHA}"
    )
