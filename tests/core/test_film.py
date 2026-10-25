"""The film mapping of SPEC §8: radiance sums → the Combined pass (T4.3).

``film.py`` is pure numpy, so these tests need no ``bpy``. It is loaded by file path with
``importlib.util.spec_from_file_location``, as ``tests/core/scenes.py`` loads ``sync/reference.py``:
importing it through the package would run ``addon/__init__.py``, which imports ``bpy``.

No expected value is read back from ``film.py``: the five numbers of the sRGB EOTF below are IEC
61966-2-1's literals, the byte scale is SPEC §8's ``L/255``, and the row order is SPEC §0's. A
change to one of ``film.py``'s constants therefore fails a test.

The comparisons are exact wherever a closed form is exact. The one tolerance, on the sRGB EOTF's
inverse point, is ``rel=1e-12`` on an analytic identity: CLAUDE.md rule 2's float64 round-off
bound, justified at the assertion.
"""

import importlib.util
import math
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
_FILM_PATH = REPO_ROOT / "src" / "blender" / "addon" / "film.py"
_FILM_SPEC = importlib.util.spec_from_file_location("painterly_film", _FILM_PATH)
assert _FILM_SPEC is not None
assert _FILM_SPEC.loader is not None
film = importlib.util.module_from_spec(_FILM_SPEC)
_FILM_SPEC.loader.exec_module(film)

# The sRGB EOTF of IEC 61966-2-1:1999 (§5.2 and Annex A), as the standard gives it:
#
#   linear = x / 12.92                          for x <= 0.04045
#   linear = ((x + 0.055) / 1.055) ** 2.4       for x > 0.04045
#
# They are written out here so that these tests pin the standard, not ``film.py``'s own copy of it.
SRGB_JUNCTION = 0.04045
SRGB_LINEAR_SLOPE = 12.92
SRGB_OFFSET = 0.055
SRGB_SCALE = 1.055
SRGB_EXPONENT = 2.4

# SPEC §8: the byte scale of both output modes is 255 (``L/255``), and SPEC §7 maps a radiance sum
# to a byte as ``min((int)sum / s, 255)``, so a full byte is a sum of 255 × passes.
BYTE_MAX = 255.0
PASSES = 3
FULL_BYTE_SUM = PASSES * BYTE_MAX


def _sums(value: float, shape: tuple[int, int] = (2, 2)) -> np.ndarray:
    """An (H, W, 3) float64 sum buffer with every channel at ``value``."""
    return np.full((*shape, 3), value, dtype=np.float64)


def test_display_referred_maps_a_full_byte_sum_to_one_and_zero_to_zero() -> None:
    """sum = 255·passes is exactly white and sum 0 is exactly black (SPEC §8)."""
    white = film.display_referred(_sums(FULL_BYTE_SUM), PASSES)
    black = film.display_referred(_sums(0.0), PASSES)

    # srgb_to_linear(1.0) is exactly 1.0 in float64: (1 + 0.055) / 1.055 == 1.0 and 1.0**2.4 == 1.0.
    assert np.array_equal(white[..., :3], np.ones((2, 2, 3), dtype=np.float32))
    assert np.array_equal(black[..., :3], np.zeros((2, 2, 3), dtype=np.float32))


def test_display_referred_maps_half_a_byte_to_the_eotf_of_one_half() -> None:
    """A sum of 255·passes/2 is the mean radiance 0.5, so the pass holds the EOTF of 0.5.

    This is the test that pins the byte scale and the exponent: 0.5 · 255 · passes / passes / 255 is
    exactly 0.5 in float64 (382.5 / 3 = 127.5 and 127.5 / 255 = 0.5), so the expectation is
    ``((0.5 + 0.055) / 1.055) ** 2.4`` from IEC 61966-2-1, and the float32 cast is the only rounding
    on either side.
    """
    mapped = film.display_referred(_sums(0.5 * FULL_BYTE_SUM), PASSES)

    expected = np.float32(((0.5 + SRGB_OFFSET) / SRGB_SCALE) ** SRGB_EXPONENT)
    assert np.array_equal(mapped[..., :3], np.full((2, 2, 3), expected, dtype=np.float32))


def test_display_referred_uses_the_linear_segment_below_the_junction() -> None:
    """A mean radiance of 0.03125, below 0.04045, is ``0.03125 / 12.92`` (IEC 61966-2-1).

    0.03125 · 255 · passes is exactly 23.90625, and 23.90625 / 3 / 255 is exactly 0.03125, so the
    only rounding is the float32 cast of the output.
    """
    mapped = film.display_referred(_sums(0.03125 * FULL_BYTE_SUM), PASSES)

    expected = np.float32(0.03125 / SRGB_LINEAR_SLOPE)
    assert np.array_equal(mapped[..., :3], np.full((2, 2, 3), expected, dtype=np.float32))


def test_display_referred_is_monotonic() -> None:
    """A larger mean radiance never maps to a smaller value."""
    sums = np.linspace(0.0, 2 * FULL_BYTE_SUM, 257, dtype=np.float64)
    mapped = film.display_referred(sums[:, None, None] * np.ones(3), PASSES)[..., 0]
    # mapped is (257, 1): the sums run along axis 0, so the differences must too.
    assert mapped.shape == (257, 1)
    assert np.all(np.diff(mapped, axis=0) >= 0.0)
    # And the map is not flat between the two ends: a strictly larger sum in the linear segment
    # is strictly larger after the mapping.
    assert mapped[-1] > mapped[0]


def test_display_referred_clips_above_white() -> None:
    """SPEC §8 clips the mean radiance at 1 before the transfer function."""
    above = film.display_referred(_sums(2 * FULL_BYTE_SUM), PASSES)
    assert np.array_equal(above[..., :3], np.ones((2, 2, 3), dtype=np.float32))


def test_scene_linear_is_the_byte_scale_times_the_exposure() -> None:
    """``L/255 · exposure``, with no transfer function (SPEC §8)."""
    assert np.array_equal(
        film.scene_linear(_sums(FULL_BYTE_SUM), PASSES, 1.0)[..., :3],
        np.ones((2, 2, 3), dtype=np.float32),
    )
    assert np.array_equal(
        film.scene_linear(_sums(FULL_BYTE_SUM), PASSES, 2.0)[..., :3],
        np.full((2, 2, 3), 2.0, dtype=np.float32),
    )
    assert np.array_equal(
        film.scene_linear(_sums(0.0), PASSES, 2.0)[..., :3],
        np.zeros((2, 2, 3), dtype=np.float32),
    )


def test_both_modes_are_opaque_float32_images() -> None:
    """The Combined pass of Blender's render result is (H, W, 4) float32 with alpha 1."""
    for rgba in (
        film.display_referred(_sums(0.5 * FULL_BYTE_SUM), PASSES),
        film.scene_linear(_sums(0.5 * FULL_BYTE_SUM), PASSES, 1.0),
    ):
        assert rgba.dtype == np.float32
        assert rgba.shape == (2, 2, 4)
        assert rgba.flags["C_CONTIGUOUS"]
        assert np.array_equal(rgba[..., 3], np.ones((2, 2), dtype=np.float32))


def test_to_blender_rows_flips_the_row_order() -> None:
    """SPEC §0: our row 0 is the top row, Blender's buffer row 0 is the bottom row.

    Every one of the 24 elements has its own value, so a flip of both axes or a reversed channel
    order changes the array and fails the comparison.
    """
    ours = np.array(
        [
            [[0.0, 1.0, 2.0, 3.0], [4.0, 5.0, 6.0, 7.0]],
            [[8.0, 9.0, 10.0, 11.0], [12.0, 13.0, 14.0, 15.0]],
            [[16.0, 17.0, 18.0, 19.0], [20.0, 21.0, 22.0, 23.0]],
        ],
        dtype=np.float32,
    )

    theirs = film.to_blender_rows(ours)

    expected = np.array(
        [
            [[16.0, 17.0, 18.0, 19.0], [20.0, 21.0, 22.0, 23.0]],
            [[8.0, 9.0, 10.0, 11.0], [12.0, 13.0, 14.0, 15.0]],
            [[0.0, 1.0, 2.0, 3.0], [4.0, 5.0, 6.0, 7.0]],
        ],
        dtype=np.float32,
    )
    assert np.array_equal(theirs, expected)
    assert theirs.dtype == np.float32
    assert theirs.flags["C_CONTIGUOUS"]


def test_srgb_to_linear_is_exact_at_the_ends_and_at_the_junction() -> None:
    """The EOTF's closed-form points, exactly, in float64 (IEC 61966-2-1)."""
    assert film.srgb_to_linear(0.0) == 0.0
    # (1 + 0.055) / 1.055 is exactly 1.0 in float64, so 1.0**2.4 is exactly 1.0.
    assert film.srgb_to_linear(1.0) == 1.0
    # 0.04045 is the junction itself, and the branch there is the linear one (x <= 0.04045).
    assert film.srgb_to_linear(SRGB_JUNCTION) == SRGB_JUNCTION / SRGB_LINEAR_SLOPE
    # The next float64 above the junction takes the power branch, whose value is written out here.
    above = np.nextafter(SRGB_JUNCTION, 1.0)
    assert film.srgb_to_linear(above) == ((above + SRGB_OFFSET) / SRGB_SCALE) ** SRGB_EXPONENT


def test_srgb_to_linear_inverts_the_encoding_at_half() -> None:
    """x = 1.055·0.5^(1/2.4) − 0.055 maps to 0.5, within float64 round-off.

    The encoded point is built from IEC 61966-2-1's literals, so the identity is the standard's
    inverse, and 0.5 is the standard's own value: an analytic identity evaluated in float64, for
    which CLAUDE.md rule 2 allows ``rel=1e-12``. The arithmetic is one division, one libm ``pow``,
    one multiply and one subtract to build x, then one add, one divide and a second ``pow`` in
    ``film``; each rounds to a few ulp (2^-53 ≈ 1.1e-16), so the result is within ~1e-15 relative
    of 0.5, seven orders of magnitude inside the bound.
    """
    encoded = SRGB_SCALE * 0.5 ** (1.0 / SRGB_EXPONENT) - SRGB_OFFSET
    decoded = film.srgb_to_linear(encoded)

    assert math.isclose(float(decoded), 0.5, rel_tol=1e-12)
