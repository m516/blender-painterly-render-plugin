"""Fast contract tests for ``smallpaint_oracle`` (T1.3).

They pin determinism, thread invariance, exact Halton equivalence below the 2^23 period, K
accounting, the SPEC §9 scene geometry, the alpha and ghost knobs, and the default values of the
gain, epsilon and depth knobs. Renders are 64 pixels square unless a test says otherwise. Arrays
are compared for exact equality, so no tolerance is used anywhere in this file.
"""

import numpy as np
import pytest
from painterly_analysis import ensemble, smallpaint_display

SIZE = 64
# SPEC §2: the incremental Halton generator is exact for K below 2^23 and drifts from K = 2^23 on.
HALTON_PERIOD = 2**23
THREAD_CHAINS = ("row", "lane:16", "lane:5", "omp-restart:4", "pixel-major-omp:3")
# Lane lengths at or above the width (64). INT_MAX would overflow an unclamped lane count.
LANE_COVERING_ROW = ("lane:64", "lane:128", "lane:2147483647")
# Option sets that exercise the other knobs. Each render is SIZE pixels square with 2 passes unless
# the set says otherwise.
SMOKE_OPTIONS = (
    {"scene": "standalone", "size": 48, "passes": 2},
    {"ghost": "lights"},
    {"u2": "base3"},
    {"u2": "independent"},
    {"continue_after_emitter": False},
    {"chain": "pixel-major"},
)
SMOKE_IDS = (
    "standalone",
    "ghost-lights",
    "u2-base3",
    "u2-independent",
    "no-continue",
    "pixel-major",
)
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
    # Size 400, SPEC §9 scene, camera with tan((double)float(PI/4)) ≈ 1 (SPEC §7).
    # Pixel (row 200, col 200) has cam = (0, 0, -1). It looks straight down -z and hits the back
    # plane, object 4 (z = -5.5).
    # The light centre (-1.9, 0, -3) lies on the ray through cam = (-1.9/3, 0, -1), since
    # (-1.9, 0, -3) / 3 = (-1.9/3, 0, -1). So cam.x = -1.9/3.
    # From cam.x = (2 row - w)/w with w = 400, row = (1 - 1.9/3) * 200 ≈ 73.3.
    # Row 73 therefore sees the light, object 9.
    render = oracle.run_oracle(tmp_path / "geometry", size=400, passes=1)
    assert render.object_id[200, 200] == 4
    assert render.object_id[73, 200] == 9


@pytest.mark.parametrize("lane", LANE_COVERING_ROW)
def test_lane_covering_row_equals_row(oracle, tmp_path, lane: str) -> None:
    # A lane of length L >= width is one lane per row, which is the row chain (SPEC §3).
    row = oracle.run_oracle(tmp_path / "row", size=SIZE, passes=2, chain="row")
    covering = oracle.run_oracle(tmp_path / "lane", size=SIZE, passes=2, chain=lane)
    assert np.array_equal(row.sum, covering.sum)
    assert np.array_equal(row.k_consumed, covering.k_consumed)


def test_pixel_major_omp_one_equals_pixel_major(oracle, tmp_path) -> None:
    # One virtual thread walks every row in order, which is the non-OpenMP pixel-major chain.
    plain = oracle.run_oracle(tmp_path / "plain", size=SIZE, passes=2, chain="pixel-major")
    one_thread = oracle.run_oracle(
        tmp_path / "one-thread", size=SIZE, passes=2, chain="pixel-major-omp:1"
    )
    assert np.array_equal(plain.sum, one_thread.sum)
    assert np.array_equal(plain.k_consumed, one_thread.k_consumed)


def test_omp_restart_one_equals_image_for_one_pass(oracle, tmp_path) -> None:
    # With one thread and one pass, the restart at each pass start is the image chain's start.
    image_one = oracle.run_oracle(tmp_path / "image-1", size=SIZE, passes=1, chain="image")
    restart_one = oracle.run_oracle(
        tmp_path / "restart-1", size=SIZE, passes=1, chain="omp-restart:1"
    )
    assert np.array_equal(image_one.sum, restart_one.sum)
    # With two passes, the restart resets K to 0 before pass 2, while the image chain does not.
    image_two = oracle.run_oracle(tmp_path / "image-2", size=SIZE, passes=2, chain="image")
    restart_two = oracle.run_oracle(
        tmp_path / "restart-2", size=SIZE, passes=2, chain="omp-restart:1"
    )
    assert not np.array_equal(image_two.sum, restart_two.sum)


def test_alpha_default_is_zero_and_hook_is_live(oracle, tmp_path) -> None:
    default = oracle.run_oracle(tmp_path / "default", size=SIZE, passes=2)
    alpha_zero = oracle.run_oracle(tmp_path / "alpha-zero", size=SIZE, passes=2, alpha=0)
    alpha_one = oracle.run_oracle(tmp_path / "alpha-one", size=SIZE, passes=2, alpha=1)
    assert default.meta["alpha"] == 0
    assert np.array_equal(default.sum, alpha_zero.sum)
    assert not np.array_equal(default.sum, alpha_one.sum)


def test_new_knobs_default_identity(oracle, tmp_path) -> None:
    # The defaults are the smallpaint literals: diffuse_gain 0.1 (smallpaint_painterly.cpp:209-211),
    # emission_gain 2 (:200), ray_epsilon 1e-4 (:39) and max_depth 20 (:190). Passing them
    # explicitly must give the same sum.npy bytes as omitting them. The values travel as the
    # decimal text Python prints, which strtod reads back to the same double.
    oracle.run_oracle(tmp_path / "omitted", size=SIZE, passes=2, seed=7)
    oracle.run_oracle(
        tmp_path / "explicit",
        size=SIZE,
        passes=2,
        seed=7,
        diffuse_gain=0.1,
        emission_gain=2,
        ray_epsilon=1e-4,
        max_depth=20,
    )
    omitted = (tmp_path / "omitted" / "sum.npy").read_bytes()
    explicit = (tmp_path / "explicit" / "sum.npy").read_bytes()
    assert omitted == explicit


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


@pytest.mark.parametrize("options", SMOKE_OPTIONS, ids=SMOKE_IDS)
def test_smoke_knob_renders_with_consistent_k(oracle, tmp_path, options) -> None:
    # run_oracle raises RuntimeError on a non-zero exit, so a render that succeeds has exit 0.
    render = oracle.run_oracle(tmp_path / "smoke", **{"size": SIZE, "passes": 2, **options})
    assert np.all(np.isfinite(render.sum))
    assert render.meta["total_k_consumed"] == int(render.k_consumed.sum())
