"""The film mapping of SPEC §8: radiance sums → the Combined pass (T4.3).

``film.py`` is pure numpy, so these tests need no ``bpy``. It is loaded by file path with
``importlib.util.spec_from_file_location``, as ``tests/core/scenes.py`` loads ``sync/reference.py``:
importing it through the package would run ``addon/__init__.py``, which imports ``bpy``.

The comparisons are exact wherever a closed form is exact. The one tolerance, on the sRGB EOTF's
inverse point, is float64 round-off with its bound derived at the assertion.
"""

import importlib.util
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
_FILM_PATH = REPO_ROOT / "src" / "blender" / "addon" / "film.py"
_FILM_SPEC = importlib.util.spec_from_file_location("painterly_film", _FILM_PATH)
assert _FILM_SPEC is not None
assert _FILM_SPEC.loader is not None
film = importlib.util.module_from_spec(_FILM_SPEC)
_FILM_SPEC.loader.exec_module(film)

# The pass counts the tests map, and the byte scale of SPEC §8 (`L/255`). The card's hand value
# "sum 255·passes" is the full-byte sum of this module: PASSES * film.BYTE_MAX.
PASSES = 3
FULL_BYTE_SUM = PASSES * film.BYTE_MAX


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


def test_display_referred_is_monotonic() -> None:
    """A larger mean radiance never maps to a smaller value."""
    sums = np.linspace(0.0, 2 * FULL_BYTE_SUM, 257, dtype=np.float64)
    mapped = film.display_referred(sums[:, None, None] * np.ones(3), PASSES)[..., 0]
    assert np.all(np.diff(mapped) >= 0.0)
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
    """SPEC §0: our row 0 is the top row, Blender's buffer row 0 is the bottom row."""
    ours = np.zeros((3, 2, 4), dtype=np.float32)
    ours[0] = 0.25
    ours[1] = 0.5
    ours[2] = 0.75

    theirs = film.to_blender_rows(ours)

    expected = np.concatenate([ours[2:3], ours[1:2], ours[0:1]])
    assert np.array_equal(theirs, expected)
    assert theirs.dtype == np.float32
    assert theirs.flags["C_CONTIGUOUS"]


def test_srgb_to_linear_is_exact_at_the_ends_and_at_the_junction() -> None:
    """The EOTF's closed-form points, exactly, in float64 (IEC 61966-2-1)."""
    assert film.srgb_to_linear(0.0) == 0.0
    # (1 + 0.055) / 1.055 is exactly 1.0 in float64, so 1.0**2.4 is exactly 1.0.
    assert film.srgb_to_linear(1.0) == 1.0
    # 0.04045 is the junction itself, and the branch there is the linear one (x <= 0.04045).
    assert film.srgb_to_linear(film.SRGB_JUNCTION) == film.SRGB_JUNCTION / film.SRGB_LINEAR_SLOPE


def test_srgb_to_linear_inverts_the_encoding_at_half() -> None:
    """x = 1.055·0.5^(1/2.4) − 0.055 maps to 0.5, within float64 round-off.

    The bound is derived from the arithmetic, not measured: x is built from 0.5 by one division
    (the reciprocal 1/2.4), one libm ``pow``, one multiply and one subtract, and the forward map
    then does one add, one divide and a second ``pow``. Each of those seven elementary operations
    rounds to at most 1 ulp of its own result (0.5 ulp for +, −, ·, /; IEEE-754 recommends ≤ 1 ulp
    for ``pow``), and first-order relative errors add, so the result's relative error is at most
    7·2^-53. The result is 0.5, so |y − 0.5| ≤ 7·2^-53·0.5 = 3.89e-16.
    """
    encoded = film.SRGB_SCALE * 0.5 ** (1.0 / film.SRGB_EXPONENT) - film.SRGB_OFFSET
    decoded = film.srgb_to_linear(encoded)

    bound = 7 * 2.0**-53 * 0.5
    assert abs(decoded - 0.5) <= bound
