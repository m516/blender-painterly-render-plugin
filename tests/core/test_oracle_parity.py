"""Bit-exact parity between the native core and the smallpaint oracle (T3.16).

The core reproduces smallpaint's reference render bit for bit on analytic scenes. Every test here
renders the same scene twice: once with the native core (``_painterly``) and once with the
oracle binary of this build (``$PAINTERLY_BUILD_DIR/src/app/smallpaint_oracle``), and compares the
three outputs bitwise. There is no tolerance anywhere: a difference of one unit in the last place
is a defect to find, never a value to round (SPEC §2, the card's "If parity fails").

The oracle always runs with ``--halton exact``, because the incremental generator drifts past
2^23 draws (SPEC §2), and always with ``--threads 1``, so the reference is a single deterministic
sequence of samples.

The fast tests use a pairwise selection over the knob axes, so every value of every axis is
covered against every other value of every other axis, without rendering the full product. The
selection is fixed in ``DESIGN`` and checked by the first two tests of this file, so a later edit
of that table that breaks the coverage fails instead of quietly reducing it.
"""

import importlib.util
import os
from pathlib import Path
from typing import Any

import _painterly
import numpy as np
import pytest
from painterly_analysis import oracle as oracle_module

# pytest runs with --import-mode=importlib (pyproject.toml), which puts no test directory on
# sys.path, so "import scenes" would fail at collection. The module is therefore loaded by path.
REPO_ROOT = Path(__file__).resolve().parents[2]
_SCENES_PATH = Path(__file__).with_name("scenes.py")
_SCENES_SPEC = importlib.util.spec_from_file_location("scenes", _SCENES_PATH)
assert _SCENES_SPEC is not None
assert _SCENES_SPEC.loader is not None
scenes = importlib.util.module_from_spec(_SCENES_SPEC)
_SCENES_SPEC.loader.exec_module(scenes)

# The fast tests' image side in pixels and their number of passes. The reference image is 400 px
# with 50 passes; the fast tests use a small image so that the whole selection runs in seconds.
FAST_SIZE = 48
FAST_PASSES = 3
# The slow test's image side in pixels and its number of passes (the card's 400 px test).
SLOW_SIZE = 400
SLOW_PASSES = 8

# The knob axes of the fast tests and their levels. The chain is one axis with four levels: the
# card's chains "image", "row", "lane:16" and "lane:5".
CHAIN_LEVELS = ("image", "row", "lane:16", "lane:5")
GHOST_LEVELS = ("all", "lights", "none")
ALPHA_LEVELS = (0.0, 0.5)
U2_LEVELS = ("same", "independent")
CAE_LEVELS = (True, False)
SEED_LEVELS = (0, 7)

# The levels of every axis, as the design's coverage tests read them.
AXIS_LEVELS: dict[str, tuple[Any, ...]] = {
    "chain": CHAIN_LEVELS,
    "ghost": GHOST_LEVELS,
    "alpha": ALPHA_LEVELS,
    "u2": U2_LEVELS,
    "continue_after_emitter": CAE_LEVELS,
    "seed": SEED_LEVELS,
}

# The pairwise selection of the fast tests. Each entry is
# (chain, ghost, alpha, u2, continue_after_emitter, seed), with the chain written as the card
# writes it: "image", "row", "lane:16" or "lane:5".
#
# The selection was chosen by the rule of the card: it covers every value of every axis against
# every other value of every other axis (a pairwise covering array), and the runs of the chain
# "lane:16" and of the chain "image" each take every value of every axis. It is not the full
# product. The first two tests of this file check both properties.
DESIGN: tuple[tuple[Any, ...], ...] = (
    ("lane:5", "lights", 0.5, "same", True, 0),
    ("lane:16", "lights", 0.5, "independent", True, 7),
    ("lane:5", "none", 0.0, "same", False, 7),
    ("lane:16", "none", 0.0, "same", False, 0),
    ("lane:16", "all", 0.0, "independent", True, 7),
    ("row", "all", 0.0, "same", True, 7),
    ("image", "none", 0.5, "independent", False, 0),
    ("row", "lights", 0.5, "independent", False, 7),
    ("row", "none", 0.0, "independent", True, 0),
    ("image", "lights", 0.0, "same", False, 7),
    ("image", "all", 0.0, "independent", True, 0),
    ("lane:5", "all", 0.5, "independent", False, 7),
)

# The core renders of one design entry: (threads, batch). The output is bit-identical for any
# thread count and batch size (SPEC §3), so every one of them must equal the same oracle render.
CORE_CONFIGS: tuple[tuple[int, int], ...] = (
    (1, 1),
    (1, 2),
    (4, 1),
    (4, 2),
)


def _design_id(entry: tuple[Any, ...]) -> str:
    """A readable pytest id for one design entry."""
    chain, ghost, alpha, u2, cae, seed = entry
    return f"{chain}-{ghost}-alpha{alpha}-u2{u2}-cae{int(cae)}-seed{seed}"


def _levels(entry: tuple[Any, ...]) -> dict[str, Any]:
    """The axis name -> level mapping of one design entry."""
    chain, ghost, alpha, u2, cae, seed = entry
    return {
        "chain": chain,
        "ghost": ghost,
        "alpha": alpha,
        "u2": u2,
        "continue_after_emitter": cae,
        "seed": seed,
    }


def _core_chain(chain: str) -> tuple[str, int]:
    """The core's chain socket and lane length for a chain of the design."""
    if chain.startswith("lane:"):
        return "lane", int(chain.split(":", 1)[1])
    return chain, 16


def test_the_selection_covers_every_pair_of_axes() -> None:
    """The selection is a pairwise covering array: every pair of levels of two axes occurs."""
    for first in AXIS_LEVELS:
        for second in AXIS_LEVELS:
            if first >= second:
                continue
            seen = {(_levels(entry)[first], _levels(entry)[second]) for entry in DESIGN}
            expected = len(AXIS_LEVELS[first]) * len(AXIS_LEVELS[second])
            assert len(seen) == expected, (
                f"the selection covers {len(seen)} of the {expected} pairs of {first} and {second}"
            )


def test_the_selection_covers_every_axis_of_both_reference_chains() -> None:
    """The runs of chain "lane:16" and of chain "image" each take every value of every axis."""
    for chain in ("lane:16", "image"):
        entries = tuple(entry for entry in DESIGN if entry[0] == chain)
        assert entries, f"the selection has no run of the chain {chain}"
        for name, levels in AXIS_LEVELS.items():
            if name == "chain":
                continue
            seen = {_levels(entry)[name] for entry in entries}
            assert seen == set(levels), (
                f"the chain {chain} does not cover every value of {name}: {sorted(map(str, seen))}"
            )


def test_the_oracle_is_the_binary_of_this_build() -> None:
    """The oracle under test is the one this build made, not another tree's.

    The parity claim is about this build's core against this build's oracle, so the oracle
    binary must be the one in the build directory the tests import the core from. A stale or
    foreign oracle (for example the experiments' oracle of another checkout) would compare two
    different programs.
    """
    binary = oracle_module.oracle_binary()
    assert binary.is_file(), f"the oracle binary {binary} does not exist; run `make build` first"
    build_dir = Path(os.environ.get("PAINTERLY_BUILD_DIR", "build/dev"))
    if not build_dir.is_absolute():
        build_dir = REPO_ROOT / build_dir
    assert binary == build_dir / "src" / "app" / "smallpaint_oracle", (
        f"the oracle binary {binary} is not the one of the build directory {build_dir}"
    )


def _oracle_options(
    *,
    size: int,
    passes: int,
    chain: str,
    ghost: str,
    alpha: float,
    u2: str,
    continue_after_emitter: bool,
    seed: int,
    jitter: float,
) -> dict[str, Any]:
    """The oracle's options for one parity test.

    The reference knobs come from scenes.ORACLE_EXACT_KNOBS, so the oracle and the core get the
    same numbers. The float values are the float32 values of the core's float sockets, widened,
    so the oracle's command line carries them exactly.
    """
    return {
        "size": size,
        "passes": passes,
        "chain": chain,
        "seed": seed,
        "ghost": ghost,
        "alpha": scenes.oracle_float(alpha),
        "u2": u2,
        "continue_after_emitter": continue_after_emitter,
        "jitter": jitter,
        # The oracle renders on one thread, so the reference is one deterministic sequence.
        "threads": 1,
        **scenes.ORACLE_EXACT_KNOBS,
    }


def _first_mismatch(core: np.ndarray, oracle: np.ndarray) -> str:
    """A description of the first difference between two arrays of the same shape."""
    differing = np.argwhere(core != oracle)
    if differing.size == 0:
        # The values are equal but the bits differ (a signed zero, or a NaN payload): the first
        # element whose bits differ is the place to report.
        core_bytes = np.ascontiguousarray(core).reshape(-1).view(np.uint8)
        oracle_bytes = np.ascontiguousarray(oracle).reshape(-1).view(np.uint8)
        item = core.dtype.itemsize
        element = int(
            np.argwhere(
                (core_bytes.reshape(-1, item) != oracle_bytes.reshape(-1, item)).any(axis=1)
            )[0][0]
        )
        return (
            f"element {element} of the buffer (the values are equal, the bit patterns are not): "
            f"the core has {core.reshape(-1)[element]!r}, the oracle has "
            f"{oracle.reshape(-1)[element]!r}"
        )
    index = tuple(int(part) for part in differing[0])
    place = ", ".join(f"index {axis} {value}" for axis, value in enumerate(index))
    return f"{place}: the core has {core[index]!r}, the oracle has {oracle[index]!r}"


def _bit_patterns(array: np.ndarray) -> bytes:
    """The bit pattern of every element of ``array``, as its bytes.

    The bytes are the array's own, in its own byte order, so the comparison does not depend on
    the endianness of the host. Two arrays of the same dtype with the same bits give the same
    bytes, which is what a bit-for-bit comparison of the two buffers needs.
    """
    return np.ascontiguousarray(array).tobytes()


def _assert_bit_equal(name: str, core: np.ndarray, oracle: np.ndarray) -> None:
    """The core's buffer and the oracle's buffer are equal, bit for bit.

    The comparison is the card's np.array_equal, plus the bit patterns: two buffers can hold the
    same numbers and different bits (a -0.0 against a 0.0), and a bit-for-bit parity test must
    see that as a difference.
    """
    assert core.shape == oracle.shape, (
        f"{name}: the core's shape {core.shape} differs from the oracle's {oracle.shape}"
    )
    if not np.array_equal(core, oracle):
        raise AssertionError(
            f"{name}: the core and the oracle differ at {_first_mismatch(core, oracle)}"
        )
    assert _bit_patterns(core) == _bit_patterns(oracle), (
        f"{name}: the core and the oracle hold the same numbers but different bit patterns, at "
        f"{_first_mismatch(core, oracle)}"
    )


@pytest.mark.parametrize(
    ("threads", "batch"),
    CORE_CONFIGS,
    ids=[f"threads{threads}-batch{batch}" for threads, batch in CORE_CONFIGS],
)
@pytest.mark.parametrize(
    ("chain", "ghost", "alpha", "u2", "continue_after_emitter", "seed"),
    DESIGN,
    ids=[_design_id(entry) for entry in DESIGN],
)
def test_the_core_matches_the_oracle_bit_for_bit(
    tmp_path: Path,
    chain: str,
    ghost: str,
    alpha: float,
    u2: str,
    continue_after_emitter: bool,
    seed: int,
    threads: int,
    batch: int,
) -> None:
    """One knob combination renders the same in the core and in the oracle, bit for bit."""
    core_chain, lane_length = _core_chain(chain)
    scene = _painterly.Scene()
    scenes.build_smallpaint_scene(scene, size=FAST_SIZE, ghost=ghost)
    scene.set_integrator(
        chain=core_chain,
        lane_length=lane_length,
        seed=seed,
        alpha=alpha,
        u2_mode=u2,
        continue_after_emitter=continue_after_emitter,
    )

    session = _painterly.Session(scene, threads)
    session.start(FAST_PASSES, batch)
    assert session.wait() is True, "the core's render did not finish"

    options = _oracle_options(
        size=FAST_SIZE,
        passes=FAST_PASSES,
        chain=chain,
        ghost=ghost,
        alpha=alpha,
        u2=u2,
        continue_after_emitter=continue_after_emitter,
        seed=seed,
        jitter=scenes.oracle_jitter(scene),
    )
    render = oracle_module.run_oracle(tmp_path, **options)

    _assert_bit_equal("combined", session.combined(), render.sum)
    _assert_bit_equal("k_consumed", session.k_consumed(), render.k_consumed)
    _assert_bit_equal("object_id", session.object_id(), render.object_id)


@pytest.mark.slow
def test_the_core_matches_the_oracle_bit_for_bit_at_400_pixels(tmp_path: Path) -> None:
    """The reference configuration at 400 px and 8 passes, the whole image chain.

    This is the card's slow test: the default reference config, so only the chain is set, and
    the oracle gets the reference knobs, ``--chain image`` and the jitter of the scene.
    """
    scene = _painterly.Scene()
    scenes.build_smallpaint_scene(scene, size=SLOW_SIZE)
    scene.set_integrator(chain="image")

    session = _painterly.Session(scene, 1)
    session.start(SLOW_PASSES, 1)
    assert session.wait() is True, "the core's render did not finish"

    options = _oracle_options(
        size=SLOW_SIZE,
        passes=SLOW_PASSES,
        chain="image",
        ghost="all",
        alpha=0.0,
        u2="same",
        continue_after_emitter=True,
        seed=0,
        jitter=scenes.oracle_jitter(scene),
    )
    render = oracle_module.run_oracle(tmp_path, **options)

    _assert_bit_equal("combined", session.combined(), render.sum)
    _assert_bit_equal("k_consumed", session.k_consumed(), render.k_consumed)
    _assert_bit_equal("object_id", session.object_id(), render.object_id)
