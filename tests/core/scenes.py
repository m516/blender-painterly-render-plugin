"""The reference scene of SPEC §9 and the smallpaint-unit knobs, for the parity tests (T3.16).

The scene and the knobs are the add-on's: ``build_smallpaint_scene`` and
``apply_reference_knobs`` live in ``src/blender/addon/sync/reference.py`` (T4.3), which is
``bpy``-free, and this module re-exports them so that the M3 tests keep using the same names.
The module is loaded by file path with ``importlib.util.spec_from_file_location``, because
importing it through the package would run ``addon/__init__.py`` and ``addon/sync/__init__.py``,
which import ``bpy``.

What stays here is the part that only the tests need: the oracle's options derived from the same
knobs, and the triangle variant of the scene (T3.17), which turns every plane into a quad mesh.

The core's integrator knobs and the oracle's command-line options are derived from the same
values, so the two renders of a parity test differ only in what the card says they differ in.

The scene is SPEC §9, smallpaint's GUI scene: the same ten objects, in the same order, with the
same colours, emissions and materials. The object ids are the list positions, as SPEC §9
requires.

The knobs are the smallpaint units, not the Blender ones: ``diffuse_gain`` is 0.1 (smallpaint
multiplies a diffuse bounce by 0.1) and the colours are smallpaint's 0…12 albedos, so the render
is the reference look and not a Blender albedo render.
"""

import importlib.util
from pathlib import Path

import numpy as np
from _painterly import Scene

REPO_ROOT = Path(__file__).resolve().parents[2]
_REFERENCE_PATH = REPO_ROOT / "src" / "blender" / "addon" / "sync" / "reference.py"
_REFERENCE_SPEC = importlib.util.spec_from_file_location("painterly_reference", _REFERENCE_PATH)
assert _REFERENCE_SPEC is not None
assert _REFERENCE_SPEC.loader is not None
reference = importlib.util.module_from_spec(_REFERENCE_SPEC)
_REFERENCE_SPEC.loader.exec_module(reference)

# Re-exported, so that a caller sees one module for the reference configuration: the two
# functions the M3 tests use, and the constants that describe the scene.
apply_reference_knobs = reference.apply_reference_knobs
build_smallpaint_scene = reference.build_smallpaint_scene

# SPEC §9: the light's emission. It is smallpaint's emission, in smallpaint's units.
LIGHT_EMISSION = reference.LIGHT_EMISSION

# SPEC §9: the glass sphere's index of refraction, dimensionless (the GUI default).
GLASS_IOR = reference.GLASS_IOR

# SPEC §9, the GUI scene, in list order; see ``reference.REFERENCE_SCENE`` for the row format.
REFERENCE_SCENE = reference.REFERENCE_SCENE

# The ghost policies of SPEC §5, as the oracle's --ghost names them.
GHOST_POLICIES = reference.GHOST_POLICIES


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
        material = reference.material_of(scene, material_kind, colour, ior)
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
