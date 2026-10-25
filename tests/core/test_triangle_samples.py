"""The triangle scene draws as many samples as the analytic scene (M3-FIX-T3.17c, R64 clause 1).

Under the ``image`` chain the triangle scene drew 0.06-0.07% fewer samples than the oracle in all
11 seed blocks of the steward's check (M3-FIX-T3.17a). The cause was in the mesh path: Embree
reports ``t`` as binary32 (``rtcore_ray.h``, ``RTCRay::tfar``), so the next ray's origin
``o + t d`` lay off the wall by up to ``|o + t d| 2^-24`` = 1.5e-6, and with ``ray_epsilon`` =
1e-4 a grazing diffuse bounce re-hit the wall it had just left whenever ``|n.d|`` < 1.5e-2. The
analytic scene has no such hit, so the quad scene drew one diffuse sample fewer there
(M3-FIX-T3.17c).

The fix is ``refine_triangle_t`` (``src/painterly/bvh/embree.cpp``): a hit's ``t`` is the
binary64 root of the reported triangle's plane through its world corners, with a guard that
rejects a root below the ray's near limit (a binary32 self-hit).

The decision is the card's (R64 clause 1), unchanged: at 400 px, P = 32, seed 1088 (block 68's
first) and one chain per pixel (``chain="lane"``, ``lane_length=1``), so both scenes start every
pixel from the same K0, ``ensemble.sign_flip_pvalue(differences, "two-sided")`` over the pixels
whose K differs must be at least ``ALPHA`` = 0.01; if no pixel differs, the test passes and says
so. Both scenes run with ``ghost="none"``, whose spheres are exact: no path leaves the box, so
every path meets the same geometry in both scenes and the comparison is like for like.

The ``ghost="all"`` numbers are reported, not asserted: its ghost spheres let a path leave the
box, and beyond the quads' rim a path meets an infinite plane in the analytic scene and nothing in
the quad scene (the extent sweep of M3-FIX-T3.17c: 14 of the 16 remaining differing pixels were
such a path, falling to 0 as ``plane_extent`` grows). The class of each differing pixel's first
parting needs the bounce at which the two paths part, which only a walk of both paths sees; the
doctest ``src/test/test_triangle_diagnostics.cpp`` ("the ghost-all K differences and where the two
paths first part") reports it at the same design.

The renders go into this clone's own git-ignored ``.cache`` directory: no render reaches another
checkout's cache (R7).
"""

import importlib.util
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

# R12: in a worker clone this project's own analysis package must be the one under test. The
# shared environment installs painterly_analysis editable from another checkout, so when
# PYTHONPATH does not name this clone's analysis directory the import resolves there instead and
# the clone's own copy is never loaded. The check command sets PYTHONPATH="$PWD/analysis" for
# that reason; this module makes the resolution correct either way.
_ANALYSIS_DIR = REPO_ROOT / "analysis"
if str(_ANALYSIS_DIR) in sys.path:
    sys.path.remove(str(_ANALYSIS_DIR))
sys.path.insert(0, str(_ANALYSIS_DIR))
for _stale in [name for name in sys.modules if name.split(".")[0] == "painterly_analysis"]:
    del sys.modules[_stale]

import _painterly  # noqa: E402
from painterly_analysis import ensemble  # noqa: E402

_SCENES_PATH = Path(__file__).with_name("scenes.py")
_SCENES_SPEC = importlib.util.spec_from_file_location("scenes", _SCENES_PATH)
assert _SCENES_SPEC is not None
assert _SCENES_SPEC.loader is not None
scenes = importlib.util.module_from_spec(_SCENES_SPEC)
_SCENES_SPEC.loader.exec_module(scenes)

# The card's design (R64 clause 1): 400 px, P = 32, seed 1088, one chain per pixel.
SIZE = 400
PASSES = 32
# Block 68's first seed: a block is 16 seeds and the base seed is 16 times the block index.
SEED = 1088
# One chain per pixel: the chain "lane" with a lane of one pixel, so every pixel starts from its
# own K0 in both scenes (SPEC §3).
LANE_LENGTH = 1
# The card's statistical level, ALPHA (R64). This is the statistical level, not the oracle's own
# --alpha knob, which is 0 (SPEC §4).
ALPHA = 0.01
# The number of threads of a render. One image-chain sequence is not used here (the chain is
# "lane"), so any count gives the same buffers; 4 is the machine's reservation (R10).
THREADS = 4


def _k_consumed(builder: Any, *, ghost: str) -> np.ndarray:
    """The per-pixel K consumption of one scene at the card's design.

    ``builder`` is one of ``scenes.build_smallpaint_scene`` and
    ``scenes.build_smallpaint_scene_triangles``, ``ghost`` the ghost policy of SPEC §5.
    """
    scene = _painterly.Scene()
    builder(scene, size=SIZE, ghost=ghost)
    scene.set_integrator(chain="lane", lane_length=LANE_LENGTH, seed=SEED)
    session = _painterly.Session(scene, THREADS)
    session.start(PASSES, 1)
    assert session.wait() is True, "the core's render did not finish"
    return session.k_consumed()


def _counts(analytic: np.ndarray, quad: np.ndarray) -> tuple[int, int, int]:
    """The pixels that lose K, gain K and are equal (quad minus analytic)."""
    difference = quad.astype(np.int64) - analytic.astype(np.int64)
    return (
        int(np.count_nonzero(difference < 0)),
        int(np.count_nonzero(difference > 0)),
        int(np.count_nonzero(difference == 0)),
    )


@pytest.mark.slow
def test_the_triangle_scene_draws_as_many_samples_as_the_analytic_scene() -> None:
    """The sign-flip test of R64 clause 1, on ``ghost="none"``, and the ``ghost="all"`` report.

    The assertion is the card's: ``sign_flip_pvalue(differences, "two-sided") >= ALPHA`` over the
    pixels whose K differs, or no differing pixel at all. The ``ghost="all"`` numbers are printed,
    not asserted; the parting classes of its differing pixels need a walk of both paths and are
    reported by the doctest of ``src/test/test_triangle_diagnostics.cpp``.

    Measured at this clone's build of M3-FIX-T3.17c, with the card's command:

        $ PYTHONPATH="$PWD/analysis" PAINTERLY_BUILD_DIR="$PWD/build/q" \
            <venv>/bin/python -m pytest -q -m slow -s tests/core/test_triangle_samples.py
        ghost="none": 2 pixels lose K, 0 gain K, 159998 are equal (of 160000);
            K total analytic 95047046, quad 95047026
        ghost="none": sign-flip p (two-sided, n=2) = 0.5, ALPHA = 0.01
        ghost="all": 14 pixels lose K, 2 gain K, 159984 are equal (of 160000);
            K total analytic 83001163, quad 83001050
        ghost="all": sign-flip p (two-sided, n=16) = 0.001190185546875
        1 passed

    At HEAD, before the fix, the same command printed

        ghost="none": 5102 pixels lose K, 2510 gain K, 152388 are equal (of 160000);
            K total analytic 95047046, quad 95029216
        ghost="none": sign-flip p (two-sided, n=7612) = 9.99990000099999e-06, ALPHA = 0.01
        ghost="all": 25649 pixels lose K, 5142 gain K, 129209 are equal (of 160000);
            K total analytic 83001163, quad 82945048
        ghost="all": sign-flip p (two-sided, n=30791) = 9.99990000099999e-06
        1 failed

    so the test fails at HEAD and passes after the fix, as R64 clause 1 requires.
    """
    analytic_none = _k_consumed(scenes.build_smallpaint_scene, ghost="none")
    quad_none = _k_consumed(scenes.build_smallpaint_scene_triangles, ghost="none")

    lose, gain, equal = _counts(analytic_none, quad_none)
    differences = (quad_none.astype(np.int64) - analytic_none.astype(np.int64)).ravel()
    differing = differences != 0
    print(
        f'ghost="none": {lose} pixels lose K, {gain} gain K, {equal} are equal '
        f"(of {differences.size}); K total analytic {int(analytic_none.sum())}, "
        f"quad {int(quad_none.sum())}"
    )
    if np.any(differing):
        p_value = ensemble.sign_flip_pvalue(differences[differing], "two-sided")
        print(
            f'ghost="none": sign-flip p (two-sided, n={int(np.count_nonzero(differing))}) '
            f"= {p_value!r}, ALPHA = {ALPHA}"
        )
    else:
        p_value = None
        print('ghost="none": no pixel differs, so the sign-flip test passes by the card\'s rule')

    # The ghost="all" numbers: reported, never asserted (the card).
    analytic_all = _k_consumed(scenes.build_smallpaint_scene, ghost="all")
    quad_all = _k_consumed(scenes.build_smallpaint_scene_triangles, ghost="all")
    lose_all, gain_all, equal_all = _counts(analytic_all, quad_all)
    differences_all = (quad_all.astype(np.int64) - analytic_all.astype(np.int64)).ravel()
    differing_all = differences_all != 0
    print(
        f'ghost="all": {lose_all} pixels lose K, {gain_all} gain K, {equal_all} are equal '
        f"(of {differences_all.size}); K total analytic {int(analytic_all.sum())}, "
        f"quad {int(quad_all.sum())}"
    )
    if np.any(differing_all):
        p_all = ensemble.sign_flip_pvalue(differences_all[differing_all], "two-sided")
        print(
            f'ghost="all": sign-flip p (two-sided, n={int(np.count_nonzero(differing_all))}) '
            f"= {p_all!r}"
        )
    else:
        print('ghost="all": no pixel differs')

    if p_value is not None:
        assert p_value >= ALPHA, (
            f"the per-pixel K differences are not centred on zero: sign-flip p = {p_value!r} "
            f"< ALPHA = {ALPHA}, with {lose} pixels losing K and {gain} gaining it"
        )
