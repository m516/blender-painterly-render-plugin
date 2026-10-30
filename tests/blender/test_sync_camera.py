"""The Blender-scene camera sync (T5.1): ``calc_matrix_camera`` → the core camera, and the spiral.

These tests need ``bpy`` (``make env-blender``), because the numbers they check are Blender's own:
``Object.calc_matrix_camera``'s projection matrix and ``Camera.view_frame``'s corner coordinates.
The pure math is covered without ``bpy`` in ``tests/core/test_camera_math.py``.

The two comparisons with a tolerance are Blender's float32 round-off, each with its bound derived
at the constant:

- the image frame's corners, computed once through the projection matrix and once by
  ``view_frame`` (the card's perspective steps 1–2 at the four outer frame corners);
- the spiral object's rotation, which must be orthonormal (SPEC §1).

Everything else is exact: which matrix entry each call received, which camera type was set, and
which fit string reached ``set_camera_*``.
"""

from __future__ import annotations

from types import ModuleType

import _painterly
import bpy
import numpy as np
import pytest

from painterly import sync

# The card's camera: an 18 mm lens on a 36 mm sensor, shifted 0.1 of the frame width, on a
# 320×240 render.
LENS_MM = 18.0
SENSOR_WIDTH_MM = 36.0
SHIFT_X = 0.1
WIDTH = 320
HEIGHT = 240

# A portrait render, for the sensor-fit cases: AUTO then fits the vertical side, which is the
# opposite of what it does for the landscape case above.
PORTRAIT_WIDTH = 240
PORTRAIT_HEIGHT = 320

# Blender's ``Camera.sensor_fit`` identifiers and ``Camera.type`` identifiers, as Blender spells
# them (``DNA_camera_types.h``); written out so a rename in the add-on fails these tests.
SENSOR_FIT_AUTO = "AUTO"
SENSOR_FIT_HORIZONTAL = "HORIZONTAL"
SENSOR_FIT_VERTICAL = "VERTICAL"
CAMERA_TYPE_PERSPECTIVE = "PERSP"
CAMERA_TYPE_ORTHOGRAPHIC = "ORTHO"
CAMERA_TYPE_PANORAMIC = "PANO"

# IEEE binary32 with round to nearest: u = 2^-24, a definition of the format (CLAUDE.md rule 2's
# float32 round-off).
FLOAT32_UNIT_ROUNDOFF = 2.0**-24
FLOAT64_UNIT_ROUNDOFF = 2.0**-53


def f32_gamma(n: int) -> float:
    """Higham's gamma(n) = n·u / (1 − n·u) for binary32: the relative error of n roundings."""
    return n * FLOAT32_UNIT_ROUNDOFF / (1.0 - n * FLOAT32_UNIT_ROUNDOFF)


def f64_gamma(n: int) -> float:
    """Higham's gamma(n) = n·u / (1 − n·u) for binary64: the relative error of n roundings."""
    return n * FLOAT64_UNIT_ROUNDOFF / (1.0 - n * FLOAT64_UNIT_ROUNDOFF)


# --- The corner bound ---------------------------------------------------------------------------
#
# Both sides of the corner comparison are the same quantity: the image frame's corner at unit
# depth in camera space. Blender computes it twice, in float32, from the same lens, sensor width,
# shift and pixel aspect: ``view_frame`` from the camera's viewplane, and ``calc_matrix_camera``'s
# projection matrix, which this test inverts in float64. Each value is a quotient of a numerator
# and a denominator built from at most VIEW_FRAME_ROUNDINGS = 8 float32 operations (the pixel
# aspect ratio, the shift offset, a viewplane edge, and the frame depth: at most two roundings
# each), so by Higham's quotient rule each corner coordinate carries at most
# 2·VIEW_FRAME_ROUNDINGS = 16 float32 roundings. The float64 composition adds at most
# COMPOSITION_ROUNDINGS = 32 roundings of 2^-53, three orders of magnitude below the float32 part.
VIEW_FRAME_ROUNDINGS = 8
COMPOSITION_ROUNDINGS = 32
CORNER_RTOL = f32_gamma(2 * VIEW_FRAME_ROUNDINGS) + f64_gamma(COMPOSITION_ROUNDINGS)

# --- The orthonormality bound --------------------------------------------------------------------
#
# mathutils computes in float32, so each entry of ``matrix_world.to_quaternion().to_matrix()`` has
# relative error at most gamma_f32(QUATERNION_MATRIX_ROUNDINGS) = gamma_f32(8): normalising the
# quaternion and forming one matrix entry is at most eight float32 operations. One entry of
# R·Rᵀ is a sum of ORTHONORMALITY_TERMS = 3 such products, so its absolute error is at most
# 3·gamma_f32(8) = gamma_f32(24), the products and sums being exact in float64 apart from
# gamma_f64(3).
QUATERNION_MATRIX_ROUNDINGS = 8
ORTHONORMALITY_TERMS = 3
ORTHONORMAL_RTOL = f32_gamma(ORTHONORMALITY_TERMS * QUATERNION_MATRIX_ROUNDINGS) + f64_gamma(
    ORTHONORMALITY_TERMS
)

# The raster point of each outer frame corner, and the frame corner it must match: raster x grows
# right (camera +X) and raster y grows down from the top row (SPEC §0), so the raster point (0, 0)
# is the frame corner with the minimum x and the maximum y.
FRAME_CORNERS = {
    (0, 0): (-1, +1),
    (WIDTH, 0): (+1, +1),
    (0, HEIGHT): (-1, -1),
    (WIDTH, HEIGHT): (+1, -1),
}


class _RecordingScene:
    """A ``_painterly.Scene`` stand-in: it records the camera calls instead of building a scene."""

    def __init__(self) -> None:
        self.perspective: dict[str, object] | None = None
        self.orthographic: dict[str, object] | None = None
        self.spiral_object: np.ndarray | None = None

    def set_camera_perspective(self, width, height, raster_to_camera, camera_to_world, fit) -> None:
        self.perspective = {
            "width": width,
            "height": height,
            "raster_to_camera": raster_to_camera,
            "camera_to_world": camera_to_world,
            "fit": fit,
        }

    def set_camera_orthographic(
        self, width, height, raster_to_camera, camera_to_world, fit
    ) -> None:
        self.orthographic = {
            "width": width,
            "height": height,
            "raster_to_camera": raster_to_camera,
            "camera_to_world": camera_to_world,
            "fit": fit,
        }

    def set_spiral_object(self, rotation) -> None:
        # np.array(copy=True) keeps whatever memory order the caller passed, so a Fortran-ordered
        # matrix stays Fortran-ordered here, exactly as the binding would reject it.
        self.spiral_object = np.array(rotation, copy=True)


def camera_point(raster_to_camera: np.ndarray, raster_x: float, raster_y: float) -> np.ndarray:
    """T3.8's perspective steps 1–2: ``p = M · (x, y, 0, 1)``, ``Pc = p.xyz / p.w``.

    Args:
        raster_to_camera: the (4, 4) matrix ``set_camera_*`` received.
        raster_x: the raster x in pixels, growing right from the left edge.
        raster_y: the raster y in pixels, growing down from the top row (SPEC §0).

    Returns:
        The camera-space (3,) float64 point. For a perspective camera it lies on the image plane
        z = −1 already (the projection divides by the depth); for an orthographic camera its x
        and y do not depend on z at all.
    """
    p = raster_to_camera @ np.array([raster_x, raster_y, 0.0, 1.0], dtype=np.float64)
    return p[:3] / p[3]


def image_plane_point(raster_to_camera: np.ndarray, raster_x: float, raster_y: float) -> np.ndarray:
    """The perspective camera point of a raster point, scaled to the image plane z = −1.

    The projection divide puts a perspective camera's point at the near plane's depth, and every
    point of one raster ray is a positive multiple of the ray's direction, so dividing by ``-z``
    moves it to z = −1 without changing the ray. An orthographic camera has no such ray: its
    points' x and y are the frame's coordinates, not a direction, so this scaling is not for it.

    Args:
        raster_to_camera: the (4, 4) matrix ``set_camera_*`` received.
        raster_x: the raster x in pixels, growing right from the left edge.
        raster_y: the raster y in pixels, growing down from the top row (SPEC §0).

    Returns:
        The (3,) float64 camera-space point at z = −1.
    """
    point = camera_point(raster_to_camera, raster_x, raster_y)
    return point / -point[2]


def frame_corner(view_frame, x_sign: int, y_sign: int) -> np.ndarray:
    """The ``view_frame`` corner with the given extreme x and y, scaled to z = −1.

    ``view_frame`` is in camera space, before the object transform, and its corners lie at one
    depth; scaling by ``-1/z`` puts them on the image plane z = −1, where ``camera_point`` puts
    its points. The corner is selected by position, not by list index: its x is the frame's
    minimum or maximum x, and its y likewise.

    Args:
        view_frame: ``Camera.view_frame(scene=...)``'s four (3,) corners.
        x_sign: +1 for the corner with the largest x, −1 for the smallest.
        y_sign: +1 for the largest y, −1 for the smallest.

    Returns:
        The (3,) float64 corner at z = −1.
    """
    corners = [np.array(corner, dtype=np.float64) / -corner[2] for corner in view_frame]
    target_x = max(corner[0] for corner in corners) if x_sign > 0 else min(c[0] for c in corners)
    target_y = max(corner[1] for corner in corners) if y_sign > 0 else min(c[1] for c in corners)
    matches = [corner for corner in corners if corner[0] == target_x and corner[1] == target_y]
    assert len(matches) == 1, f"{len(matches)} frame corners at ({target_x}, {target_y})"
    return matches[0]


def _depsgraph():
    """The evaluated dependency graph of the current frame, after any change to the scene."""
    bpy.context.view_layer.update()
    return bpy.context.evaluated_depsgraph_get()


@pytest.fixture()
def camera_scene(addon: ModuleType) -> dict[str, object]:
    """A fresh scene camera with the card's lens, sensor and shift, and the card's render size.

    The add-on fixture registers once per session and every test shares ``bpy.context.scene``, so
    the scene's state is restored afterwards and the camera is removed again.

    Returns:
        The camera ``Object``, the ``Camera`` data and the ``scene.painterly`` settings, keyed
        ``"object"``, ``"data"`` and ``"settings"``.
    """
    scene = bpy.context.scene
    render = scene.render
    settings = scene.painterly
    saved = {
        "camera": scene.camera,
        "resolution_x": render.resolution_x,
        "resolution_y": render.resolution_y,
        "resolution_percentage": render.resolution_percentage,
        "pixel_aspect_x": render.pixel_aspect_x,
        "pixel_aspect_y": render.pixel_aspect_y,
        "spiral_frame": settings.spiral_frame,
        "spiral_object": settings.spiral_object,
    }
    camera_data = bpy.data.cameras.new("T5.1 camera")
    camera_data.lens = LENS_MM
    camera_data.sensor_width = SENSOR_WIDTH_MM
    camera_data.shift_x = SHIFT_X
    camera_object = bpy.data.objects.new("T5.1 camera", camera_data)
    scene.collection.objects.link(camera_object)
    scene.camera = camera_object
    render.resolution_x = WIDTH
    render.resolution_y = HEIGHT
    render.resolution_percentage = 100
    render.pixel_aspect_x = 1.0
    render.pixel_aspect_y = 1.0
    settings.spiral_frame = "camera"
    settings.spiral_object = None
    try:
        yield {"object": camera_object, "data": camera_data, "settings": settings}
    finally:
        scene.camera = saved["camera"]
        render.resolution_x = saved["resolution_x"]
        render.resolution_y = saved["resolution_y"]
        render.resolution_percentage = saved["resolution_percentage"]
        render.pixel_aspect_x = saved["pixel_aspect_x"]
        render.pixel_aspect_y = saved["pixel_aspect_y"]
        settings.spiral_frame = saved["spiral_frame"]
        settings.spiral_object = saved["spiral_object"]
        bpy.data.objects.remove(camera_object)
        bpy.data.cameras.remove(camera_data)


def test_the_perspective_camera_reaches_the_core_as_the_card_says(camera_scene) -> None:
    """``sync_camera`` sets a perspective camera with float64 C-contiguous matrices and the fit."""
    scene = bpy.context.scene
    recorded = _RecordingScene()

    sync.sync_camera(recorded, _depsgraph(), camera_scene["settings"], WIDTH, HEIGHT)

    assert recorded.orthographic is None
    camera = recorded.perspective
    assert camera is not None
    assert camera["width"] == WIDTH
    assert camera["height"] == HEIGHT
    # ``set_camera_*`` takes no other dtype or layout (``_painterly.pyi``, T3.15).
    assert camera["raster_to_camera"].dtype == np.float64
    assert camera["raster_to_camera"].shape == (4, 4)
    assert camera["raster_to_camera"].flags["C_CONTIGUOUS"]
    assert camera["camera_to_world"].dtype == np.float64
    assert camera["camera_to_world"].shape == (4, 4)
    assert camera["camera_to_world"].flags["C_CONTIGUOUS"]
    # 320 px wide against 240 px high: AUTO fits the horizontal side (SPEC §7's F).
    assert camera["fit"] == "horizontal"
    # Translation and rotation only: the object has no scale here, so this is ``matrix_world``.
    assert np.array_equal(
        camera["camera_to_world"],
        np.array(scene.camera.matrix_world.normalized(), dtype=np.float64),
    )


def test_the_four_outer_frame_corners_match_view_frame(camera_scene) -> None:
    """The card's perspective steps 1–2 at the raster corners equal ``view_frame``'s corners.

    The raster points are the outer frame corners (no +0.5 pixel-centre offset) and the rays are
    unjittered, so each camera-space point, scaled to z = −1, is the matching ``view_frame``
    corner scaled to z = −1. Both sides are float32 computations in Blender, so the comparison
    uses CORNER_RTOL.
    """
    data = camera_scene["data"]
    recorded = _RecordingScene()
    sync.sync_camera(recorded, _depsgraph(), camera_scene["settings"], WIDTH, HEIGHT)
    raster_to_camera = recorded.perspective["raster_to_camera"]
    view_frame = data.view_frame(scene=bpy.context.scene)

    for (raster_x, raster_y), (x_sign, y_sign) in FRAME_CORNERS.items():
        ours = image_plane_point(raster_to_camera, raster_x, raster_y)
        theirs = frame_corner(view_frame, x_sign, y_sign)
        np.testing.assert_allclose(ours, theirs, rtol=CORNER_RTOL, atol=0.0)


def test_the_four_outer_frame_corners_match_view_frame_for_an_orthographic_camera(
    camera_scene,
) -> None:
    """The same corner comparison for an orthographic camera, whose x and y do not depend on z.

    An orthographic camera's camera-space point is the frame's own coordinate, so its x and y are
    compared as they are; its z is the near plane's depth, which no orthographic ray depends on.
    """
    camera_scene["data"].type = CAMERA_TYPE_ORTHOGRAPHIC
    recorded = _RecordingScene()

    sync.sync_camera(recorded, _depsgraph(), camera_scene["settings"], WIDTH, HEIGHT)

    assert recorded.perspective is None
    assert recorded.orthographic is not None
    raster_to_camera = recorded.orthographic["raster_to_camera"]
    view_frame = camera_scene["data"].view_frame(scene=bpy.context.scene)
    for (raster_x, raster_y), (x_sign, y_sign) in FRAME_CORNERS.items():
        ours = camera_point(raster_to_camera, raster_x, raster_y)
        theirs = frame_corner(view_frame, x_sign, y_sign)
        np.testing.assert_allclose(ours[:2], theirs[:2], rtol=CORNER_RTOL, atol=0.0)


def test_the_sensor_fit_of_each_mode_is_the_one_blender_projects_with(camera_scene) -> None:
    """``AUTO`` on a portrait image fits vertically: its matrix is the VERTICAL one, not HORIZONTAL.

    The expected fit strings are the card's rule for this image: 240 px wide against 320 px high,
    so ``AUTO`` fits the vertical side. The matrix check is Blender's own: ``calc_matrix_camera``
    produces the same projection for ``AUTO`` and for the side it fits, and a different one for
    the other side. ``sensor_height`` is set equal to ``sensor_width`` here, because Blender's
    ``AUTO`` always reads ``sensor_width`` whatever side it fits; with the two sensor dimensions
    equal, the sensor *size* no longer tells the fits apart and only the fitted side does.
    """
    render = bpy.context.scene.render
    render.resolution_x = PORTRAIT_WIDTH
    render.resolution_y = PORTRAIT_HEIGHT
    data = camera_scene["data"]
    settings = camera_scene["settings"]
    data.sensor_height = SENSOR_WIDTH_MM

    matrices: dict[str, np.ndarray] = {}
    fits: dict[str, str] = {}
    for sensor_fit in (SENSOR_FIT_AUTO, SENSOR_FIT_HORIZONTAL, SENSOR_FIT_VERTICAL):
        data.sensor_fit = sensor_fit
        recorded = _RecordingScene()
        sync.sync_camera(recorded, _depsgraph(), settings, PORTRAIT_WIDTH, PORTRAIT_HEIGHT)
        matrices[sensor_fit] = recorded.perspective["raster_to_camera"]
        fits[sensor_fit] = recorded.perspective["fit"]

    assert fits[SENSOR_FIT_AUTO] == "vertical"
    assert fits[SENSOR_FIT_HORIZONTAL] == "horizontal"
    assert fits[SENSOR_FIT_VERTICAL] == "vertical"
    assert np.array_equal(matrices[SENSOR_FIT_AUTO], matrices[SENSOR_FIT_VERTICAL])
    assert not np.array_equal(matrices[SENSOR_FIT_AUTO], matrices[SENSOR_FIT_HORIZONTAL])


def test_the_spiral_object_rotation_reaches_the_core_exactly(camera_scene) -> None:
    """``spiral_frame = object`` hands the object's orthonormalised rotation to the core.

    The expectation is Blender's own matrix: ``matrix_world.to_quaternion().to_matrix()``, which
    drops the scale. The rotation must also satisfy ``R·Rᵀ = I`` within float32 round-off (SPEC
    §1: the core never orthonormalises it), and it must be C-contiguous float64, which is what
    the real binding requires — so the recorded array is passed to ``_painterly.Scene`` here.
    """
    spiral_object = bpy.data.objects.new("T5.1 spiral", None)
    bpy.context.scene.collection.objects.link(spiral_object)
    try:
        spiral_object.rotation_euler = (0.3, -0.7, 1.1)
        spiral_object.location = (1.0, 2.0, -3.0)
        # A scale the rotation must not carry: 2 is a power of two, and the axes differ.
        spiral_object.scale = (2.0, 1.0, 0.5)
        settings = camera_scene["settings"]
        settings.spiral_frame = "object"
        settings.spiral_object = spiral_object
        bpy.context.view_layer.update()

        recorded = _RecordingScene()
        sync.sync_camera(recorded, _depsgraph(), settings, WIDTH, HEIGHT)

        expected = np.array(
            spiral_object.matrix_world.to_quaternion().to_matrix(), dtype=np.float64
        )
        assert recorded.spiral_object is not None
        assert np.array_equal(recorded.spiral_object, expected)
        assert recorded.spiral_object.dtype == np.float64
        assert recorded.spiral_object.shape == (3, 3)
        # The binding rejects anything but a C-contiguous float64 (4, 4)/(3, 3) array, so this
        # call is the check that the layout is right; it raises TypeError otherwise.
        _painterly.Scene().set_spiral_object(recorded.spiral_object)

        residual = recorded.spiral_object @ recorded.spiral_object.T - np.eye(3)
        np.testing.assert_allclose(residual, np.zeros((3, 3)), rtol=0.0, atol=ORTHONORMAL_RTOL)
    finally:
        camera_scene["settings"].spiral_object = None
        camera_scene["settings"].spiral_frame = "camera"
        bpy.data.objects.remove(spiral_object)


def test_the_spiral_object_frame_builds_a_real_core_scene(camera_scene) -> None:
    """``build_scene`` with ``spiral_frame = object`` reaches the core through the real binding."""
    spiral_object = bpy.data.objects.new("T5.1 spiral", None)
    bpy.context.scene.collection.objects.link(spiral_object)
    try:
        spiral_object.rotation_euler = (0.2, 0.4, -0.6)
        settings = camera_scene["settings"]
        settings.spiral_frame = "object"
        settings.spiral_object = spiral_object

        core_scene = sync.build_scene(_depsgraph(), settings, WIDTH, HEIGHT)

        assert isinstance(core_scene, _painterly.Scene)
    finally:
        settings.spiral_object = None
        settings.spiral_frame = "camera"
        bpy.data.objects.remove(spiral_object)


def test_a_missing_spiral_object_is_an_error_before_rendering(camera_scene) -> None:
    """``spiral_frame = object`` with no object cannot be made correct, so it raises."""
    settings = camera_scene["settings"]
    settings.spiral_frame = "object"
    settings.spiral_object = None

    with pytest.raises(ValueError, match="no spiral object is set"):
        sync.build_scene(_depsgraph(), settings, WIDTH, HEIGHT)


def test_a_panoramic_camera_is_not_supported(camera_scene) -> None:
    """The core has perspective and orthographic cameras only (SPEC §7), so PANO says so."""
    camera_scene["data"].type = CAMERA_TYPE_PANORAMIC

    with pytest.raises(NotImplementedError, match="panoramic"):
        sync.build_scene(_depsgraph(), camera_scene["settings"], WIDTH, HEIGHT)


def test_build_scene_returns_a_core_scene_with_the_camera_set(camera_scene) -> None:
    """The T4.3 stub is gone: ``build_scene`` builds a core scene and sets its camera."""
    core_scene = sync.build_scene(_depsgraph(), camera_scene["settings"], WIDTH, HEIGHT)

    assert isinstance(core_scene, _painterly.Scene)
    assert camera_scene["data"].type == CAMERA_TYPE_PERSPECTIVE


def test_the_addon_fixture_registered_the_package(addon: ModuleType) -> None:
    """The package is imported from ``src/blender/addon`` as ``painterly`` (conftest)."""
    assert sync is addon.sync
