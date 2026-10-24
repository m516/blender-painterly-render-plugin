# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The built-in reference scene of SPEC §9 and the smallpaint-unit knobs.

This module is the single source of the reference configuration, and it is ``bpy``-free: the
render loop builds the scene from it in reference mode, and the parity tests load it by file path
(``tests/core/scenes.py`` re-exports :func:`build_smallpaint_scene` and
:func:`apply_reference_knobs`, so the M3 tests keep passing unchanged). Importing it through the
package would run ``addon/__init__.py``, which imports ``bpy``, so a caller outside Blender loads
it with ``importlib.util.spec_from_file_location``.

The core's integrator knobs and the oracle's command-line options are derived from the same
values, so the two renders of a parity test differ only in what the card says they differ in.

The scene is SPEC §9, smallpaint's GUI scene: the same ten objects, in the same order, with the
same colours, emissions and materials. The object ids are the list positions, as SPEC §9
requires.

The knobs are the smallpaint units, not the Blender ones: ``diffuse_gain`` is 0.1 (smallpaint
multiplies a diffuse bounce by 0.1) and the colours are smallpaint's 0…12 albedos, so the render
is the reference look and not a Blender albedo render.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from _painterly import Scene

# SPEC §9: the light's emission. It is smallpaint's emission, in smallpaint's units.
LIGHT_EMISSION = (120.0, 120.0, 120.0)

# SPEC §9: the glass sphere's index of refraction, dimensionless (the GUI default).
GLASS_IOR = 1.5

# SPEC §9, the GUI scene, in list order. Each row is
#
#   (kind, geometry, colour, material kind)
#
# where "kind" is "sphere" or "plane", "geometry" is the centre and the radius of a sphere or the
# normal and the offset d of a plane (SPEC §9: n.p + d = 0), "colour" is smallpaint's cl, and
# "material kind" is "diffuse", "mirror", "glass" or "light". The list position is the object id.
REFERENCE_SCENE: tuple[tuple[str, tuple[float, ...], tuple[float, ...], str], ...] = (
    ("sphere", (1.45, -0.75, -4.4), (1.05,), (4.0, 8.0, 4.0), "mirror"),
    ("sphere", (2.05, 2.0, -3.7), (0.5,), (10.0, 10.0, 1.0), "glass"),
    ("sphere", (1.95, -1.75, -3.1), (0.6,), (4.0, 4.0, 12.0), "diffuse"),
    ("plane", (-1.0, 0.0, 0.0), (2.5,), (6.0, 6.0, 6.0), "diffuse"),
    ("plane", (0.0, 0.0, 1.0), (5.5,), (6.0, 6.0, 6.0), "diffuse"),
    ("plane", (0.0, 1.0, 0.0), (2.75,), (10.0, 2.0, 2.0), "diffuse"),
    ("plane", (0.0, -1.0, 0.0), (2.75,), (2.0, 10.0, 2.0), "diffuse"),
    ("plane", (1.0, 0.0, 0.0), (3.0,), (6.0, 6.0, 6.0), "diffuse"),
    ("plane", (0.0, 0.0, -1.0), (0.5,), (6.0, 6.0, 6.0), "diffuse"),
    ("sphere", (-1.9, 0.0, -3.0), (0.5,), (0.0, 0.0, 0.0), "light"),
)

# The ghost policies of SPEC §5, as the oracle's --ghost names them.
GHOST_POLICIES = ("all", "lights", "none")


def apply_reference_knobs() -> dict[str, object]:
    """The smallpaint-unit integrator knobs, as ``Scene.set_integrator`` takes them.

    The values are the ones the reference render uses, each with the smallpaint line it comes
    from. A float socket stores its float32 value (T3.15), so the float32 scalars below are the
    exact values the core uses.

    Returns a fresh dict on every call, so a caller may change it without changing the module.
    """
    return {
        # smallpaint multiplies the diffuse bounce by 0.1 (smallpaint_painterly.cpp:209-211).
        "diffuse_gain": np.float32(0.1),
        # smallpaint multiplies every emission by 2 (smallpaint_painterly.cpp:200).
        "emission_gain": 2,
        # smallpaint's eps, the self-intersection offset along d (smallpaint_painterly.cpp:39).
        "ray_epsilon": np.float32(1e-4),
        # smallpaint stops a path at depth 20 (smallpaint_painterly.cpp:190).
        "max_depth": 20,
        # SPEC §1: a reference scene is authored in smallpaint coordinates, so F = I.
        "spiral_frame": "smallpaint",
    }


def material_of(scene: Scene, kind: str, colour: tuple[float, float, float], ior: float) -> int:
    """The material of one SPEC §9 object, and its index.

    smallpaint ignores ``cl`` for a mirror and a glass sphere, and a unit tint reproduces its
    "add the child radiance unchanged" exactly (SPEC §6), so those two get the unit weight.

    It is public because the triangle variant of the scene, which only the tests need and which
    therefore lives in ``tests/core/scenes.py`` (T3.17), builds the same materials.
    """
    if kind == "mirror":
        return scene.add_material(lobes=[("mirror", (1.0, 1.0, 1.0), 0.0)])
    if kind == "glass":
        return scene.add_material(lobes=[("glass", (1.0, 1.0, 1.0), ior)])
    if kind == "light":
        # SPEC §6: the emitter is a surface, a black diffuse sphere that the path keeps bouncing
        # on.
        return scene.add_material(
            lobes=[("diffuse", (0.0, 0.0, 0.0), 0.0)], emission=LIGHT_EMISSION
        )
    return scene.add_material(lobes=[("diffuse", colour, 0.0)])


def build_smallpaint_scene(
    scene: Scene, *, size: int, ghost: str = "all", ior: float = 1.5
) -> None:
    """Build SPEC §9 in ``scene``, a ``_painterly.Scene``.

    ``size`` is the image side in pixels; the reference image is square, so the camera is
    ``set_camera_smallpaint(size, size)``. ``ghost`` is the ghost policy of SPEC §5: "all" makes
    every sphere a ghost sphere, "lights" makes only the emissive one a ghost, and "none" makes
    every sphere exact. ``ior`` is the index of refraction of the glass sphere, dimensionless.

    The objects are added in SPEC §9 order, and their object ids are their list positions.

    There is no ``jitter`` parameter: the integrator socket ``jitter`` (a fraction of the fitted
    image side, SPEC §7) supplies it, and its default is the reference value.
    """
    if ghost not in GHOST_POLICIES:
        raise ValueError(f"ghost must be one of {GHOST_POLICIES}, not {ghost!r}")
    # SPEC §5: the ghost policy is per sphere. Under "all" every sphere is a ghost, under
    # "lights" only the emissive one is, and under "none" no sphere is.
    sphere_intersection = "ghost" if ghost == "all" else "exact"
    light_intersection = "ghost" if ghost in ("all", "lights") else "exact"

    for object_id, (kind, geometry, values, colour, material_kind) in enumerate(REFERENCE_SCENE):
        material = material_of(scene, material_kind, colour, ior)
        if kind == "sphere":
            centre, (radius,) = geometry, values
            intersection = light_intersection if material_kind == "light" else sphere_intersection
            scene.add_sphere(centre, radius, material, intersection, object_id)
        else:
            normal, (offset,) = geometry, values
            scene.add_plane(normal, offset, material, object_id)

    # SPEC §7: the smallpaint camera of the reference image.
    scene.set_camera_smallpaint(size, size)
    # The reference knobs, and no other knob: every socket not in the dict keeps its default.
    scene.set_integrator(**apply_reference_knobs())
