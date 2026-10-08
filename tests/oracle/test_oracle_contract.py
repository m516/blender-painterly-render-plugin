"""Fast contract tests for ``smallpaint_oracle`` (T1.3).

They pin determinism, thread invariance, exact Halton equivalence below the 2^23 period, K
accounting, the SPEC §9 scene geometry, and the alpha and ghost knobs. Renders are 64 pixels
square unless a test says otherwise. Arrays are compared for exact equality, so no tolerance is
used anywhere in this file.
"""

import numpy as np
import pytest
from painterly_analysis import ensemble, smallpaint_display

SIZE = 64
# SPEC §2: the incremental Halton generator is exact for K below 2^23 and drifts from K = 2^23 on.
HALTON_PERIOD = 2**23
THREAD_CHAINS = ("row", "lane:16", "lane:5", "omp-restart:4", "pixel-major-omp:3")
GHOST_PASSES = 4
# Seeds 0..GHOST_SEEDS-1 render ghost=all and the next GHOST_SEEDS render ghost=none, so the two
# groups are independent.
GHOST_SEEDS = 8


def test_deterministic(oracle, tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    oracle.run_oracle(first, size=SIZE, passes=2, seed=7)
    oracle.run_oracle(second, size=SIZE, passes=2, seed=7)
    for name in ("sum.npy", "k_consumed.npy"):
        assert (first / name).read_bytes() == (second / name).read_bytes()


@pytest.mark.parametrize("chain", THREAD_CHAINS)
def test_thread_invariance(oracle, tmp_path, chain: str) -> None:
    one = oracle.run_oracle(tmp_path / "one", size=SIZE, passes=2, chain=chain, threads=1)
    four = oracle.run_oracle(tmp_path / "four", size=SIZE, passes=2, chain=chain, threads=4)
    assert np.array_equal(one.sum, four.sum)
    assert np.array_equal(one.k_consumed, four.k_consumed)


def test_halton_exact_equals_incremental_below_period(oracle, tmp_path) -> None:
    exact = oracle.run_oracle(
        tmp_path / "exact", size=SIZE, passes=2, chain="image", halton="exact"
    )
    incremental = oracle.run_oracle(
        tmp_path / "incremental", size=SIZE, passes=2, chain="image", halton="incremental"
    )
    # Both assertions keep the render below the period, where the two generators are bit-identical.
    assert exact.meta["total_k_consumed"] < HALTON_PERIOD
    assert incremental.meta["total_k_consumed"] < HALTON_PERIOD
    assert np.array_equal(exact.sum, incremental.sum)
    assert np.array_equal(exact.k_consumed, incremental.k_consumed)


def test_total_k_matches_k_consumed(oracle, tmp_path) -> None:
    render = oracle.run_oracle(tmp_path / "k", size=SIZE, passes=2, chain="image")
    assert render.meta["total_k_consumed"] == int(render.k_consumed.sum())


def test_object_id_geometry(oracle, tmp_path) -> None:
    # Size 400, SPEC §9 scene, SPEC §7 camera with tan(pi/4) = 1.
    # Pixel (row 200, col 200) has cam = (0, 0, -1). It looks straight down -z and hits the back
    # plane, object 4 (z = -5.5).
    # The light centre (-1.9, 0, -3) lies on the ray through cam = (-1.9/3, 0, -1), since
    # (-1.9, 0, -3) / 3 = (-1.9/3, 0, -1). So cam.x = -1.9/3.
    # From cam.x = (2 row - w)/w with w = 400, row = (1 - 1.9/3) * 200 ≈ 73.3.
    # Row 73 therefore sees the light, object 9.
    render = oracle.run_oracle(tmp_path / "geometry", size=400, passes=1)
    assert render.object_id[200, 200] == 4
    assert render.object_id[73, 200] == 9


def test_alpha_zero_is_identity(oracle, tmp_path) -> None:
    default = oracle.run_oracle(tmp_path / "default", size=SIZE, passes=2)
    alpha_zero = oracle.run_oracle(tmp_path / "alpha-zero", size=SIZE, passes=2, alpha=0)
    assert np.array_equal(default.sum, alpha_zero.sum)


def test_ghost_none_darkens(oracle, tmp_path) -> None:
    jobs = []
    for seed in range(2 * GHOST_SEEDS):
        ghost = "all" if seed < GHOST_SEEDS else "none"
        options = {"size": SIZE, "passes": GHOST_PASSES, "seed": seed, "ghost": ghost}
        jobs.append((tmp_path / f"ghost-{ghost}-{seed}", options))
    renders = oracle.run_many(jobs)
    image_means = [float(np.mean(smallpaint_display(r.sum, r.passes))) for r in renders]
    ghost_all = image_means[:GHOST_SEEDS]
    ghost_none = image_means[GHOST_SEEDS:]
    # Claim: the mean with ghost=all is greater than the mean with ghost=none. separated() uses the
    # ensemble module's default alpha, and no threshold is chosen here.
    assert ensemble.separated(ghost_all, ghost_none, "greater")
