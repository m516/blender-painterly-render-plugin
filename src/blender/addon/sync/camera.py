# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Blender's scene camera → the core camera (T5.1, SPEC §7).

Mirrors Cycles' ``intern/cycles/blender/camera.cpp``: Blender's camera object is turned into the
core's camera by two matrices and a sensor fit.

- ``calc_matrix_camera`` gives ``P``, the camera-space → clip-space projection. The raster →
  camera matrix the core takes is :func:`sync.camera_math.raster_to_camera`'s composition of
  ``inverse(P)`` with the raster → NDC map, so the core's kernel computes the same image-plane
  point Blender's own renderer would.
- ``matrix_world.normalized()`` gives the camera's rotation and translation in world space, with
  its scale divided out.

The core adds the integrator's ``jitter`` socket (a fraction of the fitted image side, SPEC §7)
itself, so this module passes no jitter; it passes the fitted side as ``fit``.

The spiral frame of SPEC §1 is the core's too: it is computed from the integrator's
``spiral_frame``/``spiral_rotation`` sockets and the camera. ``spiral_frame == "object"`` needs
the object's rotation, which is the one thing the add-on must hand over, so
:func:`sync_camera` calls ``set_spiral_object`` with it.

The pure math lives in :mod:`sync.camera_math`, which has no ``bpy``; this module needs it.
"""

from __future__ import annotations

import numpy as np

from . import camera_math

# The integrator socket value that makes the core read the object's rotation (SPEC §1).
SPIRAL_FRAME_OBJECT = "object"

# Blender's ``Camera.type`` identifiers this sync supports (Blender v5.2.2, ``DNA_camera_types.h``).
CAMERA_TYPE_PERSPECTIVE = "PERSP"
CAMERA_TYPE_ORTHOGRAPHIC = "ORTHO"


def _evaluated_camera(depsgraph):
    """The scene camera of the frame ``depsgraph`` holds, as evaluated by it.

    Args:
        depsgraph: Blender's evaluated dependency graph of the frame being rendered.

    Returns:
        The evaluated camera ``Object``.

    Raises:
        ValueError: if the scene has no camera.
    """
    camera_object = depsgraph.scene.camera
    if camera_object is None:
        raise ValueError("Painterly: the scene has no camera; add one before rendering")
    return camera_object.evaluated_get(depsgraph)


def _camera_matrices(camera_object, depsgraph, render, width: int, height: int):
    """Blender's two camera matrices, as the float64 C-contiguous arrays the core takes.

    Args:
        camera_object: the evaluated camera ``Object``.
        depsgraph: Blender's evaluated dependency graph, which ``calc_matrix_camera`` reads.
        render: ``scene.render``, for the pixel aspect ratios.
        width: the image width in pixels.
        height: the image height in pixels.

    Returns:
        ``(raster_to_camera, camera_to_world)``: the (4, 4) raster → camera matrix of
        :func:`sync.camera_math.raster_to_camera`, and the (4, 4) world transform of the camera
        with its scale divided out. Both are C-contiguous float64: ``set_camera_*`` accepts no
        other layout or dtype (``_painterly.pyi``).
    """
    projection = np.array(
        camera_object.calc_matrix_camera(
            depsgraph,
            x=width,
            y=height,
            scale_x=render.pixel_aspect_x,
            scale_y=render.pixel_aspect_y,
        ),
        dtype=np.float64,
    )
    # Blender hands matrices out in Fortran order, and the binding requires C order.
    camera_to_world = np.ascontiguousarray(
        np.array(camera_object.matrix_world.normalized(), dtype=np.float64)
    )
    return camera_math.raster_to_camera(projection, width, height), camera_to_world


def spiral_object_rotation(settings) -> np.ndarray:
    """The rotation ``R_obj`` of the spiral object (SPEC §1).

    Args:
        settings: ``scene.painterly``, the add-on's render settings.

    Returns:
        The (3, 3) C-contiguous float64 rotation of ``settings.spiral_object``'s world matrix,
        orthonormalised the way Blender does it: from the matrix's quaternion, so a scaled object
        still gives a rotation. The core never orthonormalises it (``scene.h``).

    Raises:
        ValueError: if no spiral object is set, which is a render that cannot be made correct.
    """
    spiral_object = settings.spiral_object
    if spiral_object is None:
        raise ValueError(
            "Painterly: spiral_frame is 'object' but no spiral object is set; "
            "choose an object in the Spiral Object field"
        )
    # mathutils' to_matrix() hands the 3x3 out in Fortran order; the binding requires C order.
    return np.ascontiguousarray(
        np.array(spiral_object.matrix_world.to_quaternion().to_matrix(), dtype=np.float64)
    )


def sync_camera(scene_core, depsgraph, settings, width: int, height: int) -> None:
    """Set the core scene's camera, and the spiral object's rotation when it is needed.

    Args:
        scene_core: the ``_painterly.Scene`` being built.
        depsgraph: Blender's evaluated dependency graph of the frame being rendered.
        settings: ``scene.painterly``, the add-on's render settings.
        width: the image width in pixels.
        height: the image height in pixels.

    Raises:
        NotImplementedError: for a panoramic camera, which the core has no camera type for.
        ValueError: if the scene has no camera, or ``spiral_frame`` is ``"object"`` with no
            spiral object set.
    """
    render = depsgraph.scene.render
    camera_object = _evaluated_camera(depsgraph)
    raster_to_camera, camera_to_world = _camera_matrices(
        camera_object, depsgraph, render, width, height
    )
    fit = camera_math.camera_fit(
        camera_object.data.sensor_fit,
        width,
        height,
        render.pixel_aspect_x,
        render.pixel_aspect_y,
    )

    camera_type = camera_object.data.type
    if camera_type == CAMERA_TYPE_PERSPECTIVE:
        scene_core.set_camera_perspective(width, height, raster_to_camera, camera_to_world, fit=fit)
    elif camera_type == CAMERA_TYPE_ORTHOGRAPHIC:
        scene_core.set_camera_orthographic(
            width, height, raster_to_camera, camera_to_world, fit=fit
        )
    elif camera_type == "PANO":
        raise NotImplementedError(
            "Painterly: panoramic cameras are not supported; the core has perspective and "
            "orthographic cameras only (SPEC §7)"
        )
    else:
        raise NotImplementedError(
            f"Painterly: camera type {camera_type!r} is not supported; the core has perspective "
            "and orthographic cameras only (SPEC §7)"
        )

    # SPEC §1: the core computes the spiral frame from the integrator sockets and the camera; the
    # object's rotation is the one input it cannot see.
    if settings.spiral_frame == SPIRAL_FRAME_OBJECT:
        scene_core.set_spiral_object(spiral_object_rotation(settings))
