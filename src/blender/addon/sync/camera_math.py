# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The pure-numpy half of the camera sync: raster → camera space and Blender's sensor fit (T5.1).

No ``bpy``, so the two functions are unit-testable without Blender
(``tests/core/test_camera_math.py`` loads this file by path). :mod:`sync.camera` composes them with
Blender's ``Object.calc_matrix_camera`` and ``Camera.view_frame``.

Conventions, both fixed by the project:

- Raster coordinates are ``(x, y)`` in pixels with the origin at the top-left corner of the image,
  ``x`` growing right and ``y`` growing down (SPEC §0; ``_painterly.pyi`` gives the core's buffers
  the same order). The outer frame corner is therefore ``(0, 0)`` at the top left and
  ``(width, height)`` at the bottom right, and a pixel's centre is at ``+0.5`` in each axis — the
  caller of :func:`raster_to_camera` adds that, this module does not.
- Camera space is Blender's (SPEC §7): +X right, +Y up, −Z along the viewing direction, so a
  raster point maps to a point whose ``z`` is negative.

``projection`` is Blender's ``Object.calc_matrix_camera`` matrix: it maps camera space to clip
space, and the projection divide by ``w`` gives normalised device coordinates (NDC) in
``[-1, 1]``. :func:`raster_to_camera` returns the composed raster → camera matrix, so that the
core's kernel (``src/painterly/kernel/camera/camera.h``, ``painterly_camera_raster_to_camera``)
computes ``p = raster_to_camera · (raster_x, raster_y, 0, 1)`` and ``Pc = p.xyz / p.w``.
"""

from __future__ import annotations

import numpy as np

# SPEC §0: the raster's origin is the top-left corner. In NDC x grows right from -1 to +1 and y
# grows up from -1 to +1, so raster x scales by +2/width and raster y by -2/height, with the
# offsets that put the image's outer corners at ±1. The third row carries the image plane's
# z = -1 and the fourth the homogeneous w = 1 (SPEC §7: the core's camera point is p.xyz / p.w).
NDC_FROM_RASTER = np.array(
    [
        [2.0, 0.0, 0.0, -1.0],
        [0.0, -2.0, 0.0, 1.0],
        [0.0, 0.0, 0.0, -1.0],
        [0.0, 0.0, 0.0, 1.0],
    ],
    dtype=np.float64,
)

# Blender's ``Camera.sensor_fit`` enum identifiers (Blender v5.2.2, ``DNA_camera_types.h``), and
# the two fit names the core's ``set_camera_*`` take (``_painterly.pyi``).
SENSOR_FIT_AUTO = "AUTO"
SENSOR_FIT_HORIZONTAL = "HORIZONTAL"
SENSOR_FIT_VERTICAL = "VERTICAL"

FIT_HORIZONTAL = "horizontal"
FIT_VERTICAL = "vertical"


def raster_to_camera(projection: np.ndarray, width: int, height: int) -> np.ndarray:
    """The composed raster → camera matrix of a perspective or orthographic camera.

    A raster point ``(x, y)`` becomes the NDC point ``(2x/width − 1, 1 − 2y/height, −1, 1)``, and
    the camera-space point is that NDC point through ``inverse(projection)``; the matrix returned
    here is the two steps composed, so one product per raster point suffices.

    Args:
        projection: Blender's ``calc_matrix_camera`` projection matrix, (4, 4) float, camera
            space → clip space. It may be any real dtype; it is read as float64.
        width: the image width in pixels, at least 1.
        height: the image height in pixels, at least 1.

    Returns:
        A C-contiguous (4, 4) float64 matrix, row-major: ``p = matrix · (x, y, 0, 1)``, and the
        camera-space point is ``p.xyz / p.w``.
    """
    matrix = np.asarray(projection, dtype=np.float64)
    if matrix.shape != (4, 4):
        raise ValueError(f"raster_to_camera: projection must be (4, 4), not {matrix.shape}")
    if width < 1 or height < 1:
        raise ValueError(f"raster_to_camera: the image must be at least 1x1, not {width}x{height}")

    # The raster → NDC scale depends on the image size; the rest of the table is a constant.
    ndc_from_raster = NDC_FROM_RASTER.copy()
    ndc_from_raster[0, 0] /= width
    ndc_from_raster[1, 1] /= height

    return np.ascontiguousarray(np.linalg.inv(matrix) @ ndc_from_raster)


def camera_fit(
    sensor_fit: str,
    width: int,
    height: int,
    pixel_aspect_x: float,
    pixel_aspect_y: float,
) -> str:
    """Blender's sensor fit, resolved to the image side the camera's field of view fits.

    This is the rule ``calc_matrix_camera`` applies (Blender v5.2.2
    ``source/blender/blenkernel/intern/camera.cc:334-337, 483``): ``AUTO`` fits the larger of the
    two *rendered* sides, where a side is its pixel count times its pixel aspect, and
    ``HORIZONTAL``/``VERTICAL`` name the side explicitly. So the result is the side that ``F`` —
    the fitted image side of SPEC §7, which the core's jitter is a fraction of — measures.

    Args:
        sensor_fit: Blender's ``Camera.sensor_fit`` identifier: ``"AUTO"``, ``"HORIZONTAL"`` or
            ``"VERTICAL"``.
        width: the image width in pixels.
        height: the image height in pixels.
        pixel_aspect_x: the pixel width in Blender units, ``RenderSettings.pixel_aspect_x``.
        pixel_aspect_y: the pixel height in Blender units, ``RenderSettings.pixel_aspect_y``.

    Returns:
        ``"horizontal"`` or ``"vertical"``, the fit names ``Scene.set_camera_*`` take.

    Raises:
        ValueError: if ``sensor_fit`` is not one of Blender's three identifiers.
    """
    if sensor_fit == SENSOR_FIT_HORIZONTAL:
        return FIT_HORIZONTAL
    if sensor_fit == SENSOR_FIT_VERTICAL:
        return FIT_VERTICAL
    if sensor_fit != SENSOR_FIT_AUTO:
        raise ValueError(
            f"camera_fit: unknown sensor_fit {sensor_fit!r}; expected one of "
            f"{(SENSOR_FIT_AUTO, SENSOR_FIT_HORIZONTAL, SENSOR_FIT_VERTICAL)}"
        )
    # AUTO: the larger rendered side wins, and a tie is horizontal (Blender's `>=`).
    if width * pixel_aspect_x >= height * pixel_aspect_y:
        return FIT_HORIZONTAL
    return FIT_VERTICAL
