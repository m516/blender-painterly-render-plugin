"""The reference scene of SPEC §9 and the smallpaint-unit knobs, in the core's Scene API (T3.16).

This module is the single source of the reference configuration. The core's integrator knobs and
the oracle's command-line options are derived from the same values, so the two renders of a
parity test differ only in what the card says they differ in.

The scene is SPEC §9, smallpaint's GUI scene: the same ten objects, in the same order, with the
same colours, emissions and materials. The object ids are the list positions, as SPEC §9
requires.

The knobs are the smallpaint units, not the Blender ones: `diffuse_gain` is 0.1 (smallpaint
multiplies a diffuse bounce by 0.1) and the colours are smallpaint's 0…12 albedos, so the render
is the reference look and not a Blender albedo render.
"""

import numpy as np
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


def oracle_float(value: object) -> float:
    """The float32 value of a core float socket, widened to double.

    A float socket stores its float32 value (T3.15), so the oracle must get the same number: the
    float32 value, widened. The command line prints it with ``repr``, which round-trips a double
    exactly.
    """
    return float(np.float32(value))


_REFERENCE_KNOBS = apply_reference_knobs()

#: The oracle's options for the reference knobs, plus ``--halton exact``. SPEC §2: a bit-parity
#: test always runs the oracle with the exact generator, because the incremental one drifts past
#: 2^23 draws.
ORACLE_EXACT_KNOBS: dict[str, object] = {
    "diffuse_gain": oracle_float(_REFERENCE_KNOBS["diffuse_gain"]),
    "emission_gain": oracle_float(_REFERENCE_KNOBS["emission_gain"]),
    "ray_epsilon": oracle_float(_REFERENCE_KNOBS["ray_epsilon"]),
    "max_depth": _REFERENCE_KNOBS["max_depth"],
    "halton": "exact",
}


def _material(scene: Scene, kind: str, colour: tuple[float, float, float], ior: float) -> int:
    """The material of one SPEC §9 object, and its index.

    smallpaint ignores ``cl`` for a mirror and a glass sphere, and a unit tint reproduces its
    "add the child radiance unchanged" exactly (SPEC §6), so those two get the unit weight.
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
    """
    if ghost not in GHOST_POLICIES:
        raise ValueError(f"ghost must be one of {GHOST_POLICIES}, not {ghost!r}")
    # SPEC §5: the ghost policy is per sphere. Under "all" every sphere is a ghost, under
    # "lights" only the emissive one is, and under "none" no sphere is.
    sphere_intersection = "ghost" if ghost == "all" else "exact"
    light_intersection = "ghost" if ghost in ("all", "lights") else "exact"

    for object_id, (kind, geometry, values, colour, material_kind) in enumerate(REFERENCE_SCENE):
        material = _material(scene, material_kind, colour, ior)
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


#: The default half-size of a plane's quad, in smallpaint units. Any value large enough that the
#: quads cover the box's visible faces works; the box spans at most 6 units (z from -5.5 to 0.5,
#: SPEC §9), so 50 covers every face with a wide margin.
PLANE_EXTENT = 50.0


def _plane_quad(normal: tuple[float, float, float], offset: float, extent: float) -> np.ndarray:
    """The four corners of the quad of one SPEC §9 plane, as a (4, 3) float64 array.

    The plane is ``n.p + d = 0``, so its foot point (the point of the plane nearest the origin) is
    ``-d * n``. The quad is centred there and spans ``+-extent`` along two orthonormal in-plane
    axes.

    The corners are ordered counter-clockwise as seen from the side that ``n`` points to, so that
    Embree's geometric normal ``(v1 - v0) x (v2 - v0)`` has the direction and sign of ``n``
    (``painterly/bvh/embree.h``, T3.21). With no corner normals the shading normal is
    ``normalize(Ng)``, so the quad shades exactly like smallpaint's plane.

    The in-plane axes are built from the world axis least aligned with ``n``, so that for the
    scene's axis-aligned normals both axes and every corner are exact in float32: the quad then
    lies in the analytic plane without any rounding of its own.
    """
    n = np.asarray(normal, dtype=np.float64)
    # The foot point of the plane n.p + d = 0 is the point of the plane nearest the origin.
    centre = -offset * n / float(np.dot(n, n))
    helper = np.zeros(3, dtype=np.float64)
    helper[int(np.argmin(np.abs(n)))] = 1.0
    u = np.cross(helper, n)
    u = u / np.linalg.norm(u)
    v = np.cross(n, u)
    corners = np.array(
        [
            centre - extent * u - extent * v,
            centre + extent * u - extent * v,
            centre + extent * u + extent * v,
            centre - extent * u + extent * v,
        ]
    )
    return corners


def build_smallpaint_scene_triangles(
    scene: Scene,
    *,
    size: int,
    plane_extent: float = PLANE_EXTENT,
    ghost: str = "all",
    ior: float = 1.5,
) -> None:
    """Build SPEC §9 in ``scene`` with every plane replaced by one quad mesh (T3.17).

    Same as ``build_smallpaint_scene``, except that the six planes become triangle meshes: one
    quad of two triangles per plane, with no corner normals. The spheres stay analytic, so both
    scenes keep the same objects and the same object ids (the SPEC §9 list positions).

    ``size`` is the image side in pixels, ``plane_extent`` the half-size of a quad in smallpaint
    units (see ``PLANE_EXTENT``), ``ghost`` the ghost policy of SPEC §5 and ``ior`` the index of
    refraction of the glass sphere, dimensionless.

    The integrator socket ``two_sided`` is set to False, so the quad keeps smallpaint's plane
    normal semantics: the shading normal is the plane's own normal, not one flipped towards the
    incoming ray.
    """
    if ghost not in GHOST_POLICIES:
        raise ValueError(f"ghost must be one of {GHOST_POLICIES}, not {ghost!r}")
    sphere_intersection = "ghost" if ghost == "all" else "exact"
    light_intersection = "ghost" if ghost in ("all", "lights") else "exact"

    identity = np.eye(4, dtype=np.float32)
    for object_id, (kind, geometry, values, colour, material_kind) in enumerate(REFERENCE_SCENE):
        material = _material(scene, material_kind, colour, ior)
        if kind == "sphere":
            centre, (radius,) = geometry, values
            intersection = light_intersection if material_kind == "light" else sphere_intersection
            scene.add_sphere(centre, radius, material, intersection, object_id)
        else:
            normal, (offset,) = geometry, values
            corners = _plane_quad(normal, offset, plane_extent)
            vertices = np.ascontiguousarray(corners, dtype=np.float32)
            # Two triangles of the quad, in the order of _plane_quad's corners.
            triangles = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.uint32)
            tri_material = np.array([material, material], dtype=np.int32)
            mesh = scene.add_mesh(vertices, triangles, tri_material, None)
            scene.add_object(mesh, identity, object_id)

    # SPEC §7: the smallpaint camera of the reference image.
    scene.set_camera_smallpaint(size, size)
    # The reference knobs, and no other knob: every socket not in the dict keeps its default.
    # two_sided = False keeps the quads' plane normal semantics (the card's normal orientation).
    scene.set_integrator(**apply_reference_knobs(), two_sided=False)


def oracle_jitter(scene: Scene) -> float:
    """The oracle's ``--jitter`` value for ``scene``, in image-plane units.

    SPEC §7: the integrator socket ``jitter`` is a fraction of the fitted image side, and the
    smallpaint camera uses twice that, in image-plane units. The value is the float32 of the
    socket, widened, so the oracle and the core displace their rays by the same amount.
    """
    return 2 * float(np.float32(scene.get_integrator()["jitter"]))
