"""The pure camera math of T5.1: raster → camera space, and Blender's sensor fit.

``sync/camera_math.py`` has no ``bpy`` and no package-relative import, so these tests need no
Blender. It is loaded by file path with ``importlib.util.spec_from_file_location``, as
``tests/core/test_film.py`` loads ``film.py``: importing it through the package would run
``addon/__init__.py`` and ``sync/__init__.py``, which import ``bpy``.

No expected value is read back from ``camera_math.py``. The projection matrices below are built
analytically — the standard off-centre perspective matrix of a pinhole — and the expected corner
directions and principal point are derived from the pinhole's own geometry in the comments. So a
change to the module's NDC table, its y direction or its aspect rule fails a test.

The one tolerance is float64 round-off, with its bound derived below.
"""

import importlib.util
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
_CAMERA_MATH_PATH = REPO_ROOT / "src" / "blender" / "addon" / "sync" / "camera_math.py"
_CAMERA_MATH_SPEC = importlib.util.spec_from_file_location(
    "painterly_camera_math", _CAMERA_MATH_PATH
)
assert _CAMERA_MATH_SPEC is not None
assert _CAMERA_MATH_SPEC.loader is not None
camera_math = importlib.util.module_from_spec(_CAMERA_MATH_SPEC)
_CAMERA_MATH_SPEC.loader.exec_module(camera_math)

# IEEE binary64 with round to nearest: the unit round-off u = 2^-53, a definition of the format.
FLOAT64_UNIT_ROUNDOFF = 2.0**-53


def f64_gamma(n: int) -> float:
    """Higham's gamma(n) = n·u / (1 − n·u) for binary64, the relative error of n roundings."""
    return n * FLOAT64_UNIT_ROUNDOFF / (1.0 - n * FLOAT64_UNIT_ROUNDOFF)


# The roundings of the arithmetic under test, on the longest dependency chain of one matrix entry:
# np.linalg.inv of a 4x4 (LU with partial pivoting: at most 4 divisions and 12 multiply-adds per
# column, so at most 16 roundings), the product with the raster → NDC table (1), the matrix-vector
# product (4 products and 3 sums, 7), and the divide by w (1). 32 over-counts that chain, so
# gamma(32) bounds the relative error of every returned coordinate.
COMPOSITION_ROUNDINGS = 32
ROUNDOFF_BOUND = f64_gamma(COMPOSITION_ROUNDINGS)

# The largest |coordinate| of the cases below: the non-square case's corner y is 2 (the image's
# half-height in camera units at the 90° FOV's 2-unit window). An absolute bound for a value of
# that size is the relative bound times this scale.
COORDINATE_SCALE = 2.0

# The images and windows of the analytic cases. The window is the camera-space rectangle the image
# covers at the near plane, so a 90° horizontal and vertical FOV is the square [-1, 1]² at
# near = 1.
SQUARE_SIDE = 400
SQUARE_NEAR = 1.0
FAR = 100.0
NON_SQUARE_WIDTH = 400
NON_SQUARE_HEIGHT = 200
NON_SQUARE_HALF_HEIGHT = 2.0

# Blender's ``Camera.sensor_fit`` identifiers and the core's two fit names, written out here so
# that these tests pin Blender's spelling, not ``camera_math.py``'s copy of it.
SENSOR_FIT_AUTO = "AUTO"
SENSOR_FIT_HORIZONTAL = "HORIZONTAL"
SENSOR_FIT_VERTICAL = "VERTICAL"


def perspective_projection(
    x_min: float, x_max: float, y_min: float, y_max: float, near: float, far: float
) -> np.ndarray:
    """The off-centre perspective matrix of a pinhole, built analytically.

    A camera-space point ``(x, y, z)`` with ``z = -depth`` projects to

        ndc_x = (2·near·x/(x_max − x_min) + (x_max + x_min)·z/(x_max − x_min)) / (−z)

    and likewise in y, which is the first and second row below with ``w = −z``; the third and
    fourth rows are the depth range and the ``w = −z`` that makes the divide the perspective one.
    The window is ``[x_min, x_max] × [y_min, y_max]`` at depth ``near``, so the image's outer
    corners are the window's corners.

    Args:
        x_min: the window's left edge in camera space.
        x_max: the window's right edge in camera space.
        y_min: the window's bottom edge in camera space.
        y_max: the window's top edge in camera space.
        near: the window's depth in front of the camera, positive.
        far: the far plane's depth, positive and larger than ``near``.

    Returns:
        The (4, 4) float64 projection matrix, camera space → clip space.
    """
    return np.array(
        [
            [2.0 * near / (x_max - x_min), 0.0, (x_max + x_min) / (x_max - x_min), 0.0],
            [0.0, 2.0 * near / (y_max - y_min), (y_max + y_min) / (y_max - y_min), 0.0],
            [0.0, 0.0, -(far + near) / (far - near), -2.0 * far * near / (far - near)],
            [0.0, 0.0, -1.0, 0.0],
        ],
        dtype=np.float64,
    )


def square_projection() -> np.ndarray:
    """The 90° projection of the square case: the window [-1, 1]² at depth 1.

    Returns:
        The (4, 4) float64 projection matrix of :func:`perspective_projection`.
    """
    return perspective_projection(
        -SQUARE_NEAR, SQUARE_NEAR, -SQUARE_NEAR, SQUARE_NEAR, SQUARE_NEAR, FAR
    )


def camera_point(matrix: np.ndarray, raster_x: float, raster_y: float) -> np.ndarray:
    """T3.8's perspective steps 1–2: ``p = matrix · (x, y, 0, 1)``, ``Pc = p.xyz / p.w``.

    Args:
        matrix: the (4, 4) raster → camera matrix.
        raster_x: the raster x in pixels.
        raster_y: the raster y in pixels, growing down from the top row (SPEC §0).

    Returns:
        The camera-space (3,) float64 point.
    """
    p = matrix @ np.array([raster_x, raster_y, 0.0, 1.0], dtype=np.float64)
    return p[:3] / p[3]


def at_unit_depth(point: np.ndarray) -> np.ndarray:
    """A camera-space point scaled so that its z is −1: the image-plane direction of its ray."""
    return point / -point[2]


def assert_within_roundoff(actual: np.ndarray, expected: np.ndarray) -> None:
    """Compare two camera-space values with the derived float64 bound.

    The values are O(COORDINATE_SCALE), so the absolute bound is the relative one times that
    scale; the relative part covers the values themselves.
    """
    np.testing.assert_allclose(
        actual, expected, rtol=ROUNDOFF_BOUND, atol=ROUNDOFF_BOUND * COORDINATE_SCALE
    )


def test_the_matrix_is_a_float64_c_contiguous_4x4() -> None:
    """``set_camera_*`` takes no other dtype or layout, so the composed matrix must be float64 C."""
    matrix = camera_math.raster_to_camera(
        square_projection(),
        SQUARE_SIDE,
        SQUARE_SIDE,
    )

    assert matrix.dtype == np.float64
    assert matrix.shape == (4, 4)
    assert matrix.flags["C_CONTIGUOUS"]


def test_the_centre_raster_point_maps_to_the_viewing_direction() -> None:
    """The image centre is on the camera axis: (200, 200) of a 400 px square maps to (0, 0, −1).

    The window is the square [−1, 1]² at depth 1, so the ray through the image's centre is the
    camera axis, and its image-plane point is (0, 0, −1) (SPEC §7: camera −Z is the view
    direction).
    """
    matrix = camera_math.raster_to_camera(
        square_projection(),
        SQUARE_SIDE,
        SQUARE_SIDE,
    )

    centre = at_unit_depth(camera_point(matrix, SQUARE_SIDE / 2, SQUARE_SIDE / 2))

    assert_within_roundoff(centre, np.array([0.0, 0.0, -1.0]))


def test_the_outer_frame_corners_map_to_the_window_corners() -> None:
    """Raster (0, 0), (w, 0), (0, h) and (w, h) are the window's corners, y flipped (SPEC §0).

    Raster x grows right (camera +X) and raster y grows down (camera −Y), so the top-left corner
    (0, 0) is the window's (−1, +1) corner at unit depth. No pixel-centre offset is added: these
    are the outer frame corners.
    """
    matrix = camera_math.raster_to_camera(
        square_projection(),
        SQUARE_SIDE,
        SQUARE_SIDE,
    )

    expected = {
        (0, 0): (-1.0, 1.0),
        (SQUARE_SIDE, 0): (1.0, 1.0),
        (0, SQUARE_SIDE): (-1.0, -1.0),
        (SQUARE_SIDE, SQUARE_SIDE): (1.0, -1.0),
    }
    for (raster_x, raster_y), (window_x, window_y) in expected.items():
        corner = at_unit_depth(camera_point(matrix, raster_x, raster_y))
        assert_within_roundoff(corner, np.array([window_x, window_y, -1.0]))


def test_a_non_square_image_maps_its_own_window() -> None:
    """A 400×200 image of the window [−1, 1] × [−2, 2] has the window's corners, not a square's.

    This is the case that pins the two axes' separate scales: swapping width and height, or
    scaling y by 2/width, changes these corners.
    """
    matrix = camera_math.raster_to_camera(
        perspective_projection(
            -SQUARE_NEAR,
            SQUARE_NEAR,
            -NON_SQUARE_HALF_HEIGHT,
            NON_SQUARE_HALF_HEIGHT,
            SQUARE_NEAR,
            FAR,
        ),
        NON_SQUARE_WIDTH,
        NON_SQUARE_HEIGHT,
    )

    expected = {
        (0, 0): (-1.0, NON_SQUARE_HALF_HEIGHT),
        (NON_SQUARE_WIDTH, 0): (1.0, NON_SQUARE_HALF_HEIGHT),
        (0, NON_SQUARE_HEIGHT): (-1.0, -NON_SQUARE_HALF_HEIGHT),
        (NON_SQUARE_WIDTH, NON_SQUARE_HEIGHT): (1.0, -NON_SQUARE_HALF_HEIGHT),
    }
    for (raster_x, raster_y), (window_x, window_y) in expected.items():
        corner = at_unit_depth(camera_point(matrix, raster_x, raster_y))
        assert_within_roundoff(corner, np.array([window_x, window_y, -1.0]))


def test_a_sensor_shift_moves_the_principal_point_by_its_fraction_of_the_width() -> None:
    """A shift of s moves the principal point s·width pixels, with s in units of the frame width.

    Blender's ``shift_x = s`` moves the camera's frame by s times its width along camera +X
    (``BKE_camera_view_frame``), so the window becomes ``[−1 + 2s, 1 + 2s]`` for the 90° FOV's
    2-unit frame. The camera axis then crosses the image where ``ndc_x = −1 + 2s``, i.e. at

        raster_x = (ndc_x + 1)·width/2 = s·width,

    counted from the left edge: the principal point is ``s·width`` pixels left of the centre.
    """
    shift = 0.1
    window_offset = 2.0 * SQUARE_NEAR * shift
    matrix = camera_math.raster_to_camera(
        perspective_projection(
            -SQUARE_NEAR + window_offset,
            SQUARE_NEAR + window_offset,
            -SQUARE_NEAR,
            SQUARE_NEAR,
            SQUARE_NEAR,
            FAR,
        ),
        SQUARE_SIDE,
        SQUARE_SIDE,
    )

    # The principal point: the raster point whose camera-space x is 0 at the image's middle row.
    # The map is affine in the raster point with w = 1 for this projection, so solve for x.
    middle_row = SQUARE_SIDE / 2
    principal_x = -(matrix[0, 1] * middle_row + matrix[0, 3]) / matrix[0, 0]
    expected_x = SQUARE_SIDE / 2 - shift * SQUARE_SIDE
    # The entries carry the derived float64 bound, and a raster coordinate is O(width), so the
    # bound in pixels is the relative bound times the width.
    np.testing.assert_allclose(
        principal_x, expected_x, rtol=ROUNDOFF_BOUND, atol=ROUNDOFF_BOUND * SQUARE_SIDE
    )

    # And the camera axis is exactly the ray of that raster point, at the image's middle row.
    axis = at_unit_depth(camera_point(matrix, principal_x, middle_row))
    assert_within_roundoff(axis, np.array([0.0, 0.0, -1.0]))


def test_the_camera_fit_of_each_sensor_fit_mode() -> None:
    """``AUTO`` fits the larger rendered side, and the two explicit modes name their side.

    Blender's rule (``source/blender/blenkernel/intern/camera.cc:334-337, 483``) compares the
    rendered sides, i.e. the pixel counts times the pixel aspects, and a tie goes to horizontal
    because the comparison is ``>=``.
    """
    landscape = (320, 240, 1.0, 1.0)
    portrait = (240, 320, 1.0, 1.0)
    anamorphic = (240, 320, 2.0, 1.0)

    # AUTO: the larger side wins. 320 px wide against 240 px high is horizontal, the transpose is
    # vertical, and 240 px × 2 against 320 px × 1 is horizontal again.
    assert camera_math.camera_fit(SENSOR_FIT_AUTO, *landscape) == "horizontal"
    assert camera_math.camera_fit(SENSOR_FIT_AUTO, *portrait) == "vertical"
    assert camera_math.camera_fit(SENSOR_FIT_AUTO, *anamorphic) == "horizontal"
    # A square image is a tie, which AUTO resolves to horizontal.
    assert camera_math.camera_fit(SENSOR_FIT_AUTO, 256, 256, 1.0, 1.0) == "horizontal"
    # HORIZONTAL and VERTICAL ignore the image: they name the side the FOV fits.
    for width, height, aspect_x, aspect_y in (landscape, portrait, anamorphic):
        assert camera_math.camera_fit(SENSOR_FIT_HORIZONTAL, width, height, aspect_x, aspect_y) == (
            "horizontal"
        )
        assert camera_math.camera_fit(SENSOR_FIT_VERTICAL, width, height, aspect_x, aspect_y) == (
            "vertical"
        )


def test_the_camera_fit_rejects_a_name_blender_does_not_have() -> None:
    """An unknown sensor fit is an error, not a silent horizontal."""
    try:
        camera_math.camera_fit("SQUARE", 320, 240, 1.0, 1.0)
    except ValueError as error:
        assert "SQUARE" in str(error)
    else:
        raise AssertionError("camera_fit accepted a sensor fit Blender does not have")
