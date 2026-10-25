"""The built _painterly implements the contract of src/blender/_painterly.pyi (T3.15), and does what
the contract says.

The checks come in two kinds, and each one says in its docstring which it is:

- the signature checks read the contract from the `.pyi` itself, so the two can never drift apart:
  the public names and their parameter names come from `ast`, and so do the default values, which
  are compared with the values the module reports through nanobind's `__nb_signature__`;
- the effect checks do not read the `.pyi` at all. `test_integrator_sockets_are_complete` reads the
  module's own reflection, and the effect tests render a tiny scene whose answer follows from the
  core's source, because a binding can keep its signature and still do the wrong thing.

The GIL tests at the end are the two mutation gaps of the T3.15 audit: a threshold derived from a
calibration of the same loop, never a hand-picked number, so that removing the release from
`Session.start` or from `Session.wait` alone makes its test fail.
"""

import ast
import math
import re
import sys
import threading
import time
from pathlib import Path

import _painterly
import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PYI = REPO_ROOT / "src" / "blender" / "_painterly.pyi"

# The placeholders that nanobind's __nb_signature__ writes in place of a default value: "= \\0",
# "= \\1", ... ("= \\=0" when the binding gave the default a text signature).
DEFAULT_PLACEHOLDER = re.compile(r"= \\=?(\d+)")


def _pyi_tree() -> ast.Module:
    return ast.parse(PYI.read_text(encoding="utf-8"))


def _is_typed_dict(node: ast.ClassDef) -> bool:
    """True for a TypedDict: the pyi's type-only classes are not objects of the module."""
    return any(
        (isinstance(base, ast.Name) and base.id == "TypedDict")
        or (isinstance(base, ast.Attribute) and base.attr == "TypedDict")
        for base in node.bases
    )


def _parameters(node: ast.FunctionDef) -> tuple[list[str], list[ast.expr | None], str | None]:
    """The parameter names in order, the defaults aligned with the last names, and **kwargs.

    The pyi's functions have no positional-only and no keyword-only parameters, so `args` is the
    whole list. `defaults[i]` belongs to `names[len(names) - len(defaults) + i]`.
    """
    arguments = node.args
    assert not arguments.posonlyargs and not arguments.kwonlyargs, node.name
    names = [argument.arg for argument in arguments.args]
    defaults: list[ast.expr | None] = [None] * (len(names) - len(arguments.defaults))
    defaults.extend(arguments.defaults)
    return names, defaults, arguments.kwarg.arg if arguments.kwarg else None


def _pyi_public_api() -> dict[str, tuple[list[str], list[ast.expr | None], str | None]]:
    """The pyi's public functions and methods: name -> (parameters, defaults, **kwargs name).

    TypedDicts and the two type aliases (`LobeKind`, `Lobe`) are excluded: they are types, not
    objects of the module.
    """
    api: dict[str, tuple[list[str], list[ast.expr | None], str | None]] = {}
    for node in _pyi_tree().body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            api[node.name] = _parameters(node)
        elif isinstance(node, ast.ClassDef) and not _is_typed_dict(node):
            for member in node.body:
                if isinstance(member, ast.FunctionDef) and (
                    not member.name.startswith("_") or member.name == "__init__"
                ):
                    api[f"{node.name}.{member.name}"] = _parameters(member)
    return api


def _runtime_signature(function: object) -> tuple[list[str], list[object], str | None]:
    """The parameter names, the default values and **kwargs of a nanobind function.

    nanobind exposes one entry per overload; every binding of this module has exactly one. The
    signature text marks each default with a placeholder that `DEFAULT_PLACEHOLDER` turns into a
    parseable name, so `ast` gives the parameter list; the default values come from the third
    element of the entry, which is what the default comparison below needs.
    """
    overloads = function.__nb_signature__
    assert len(overloads) == 1, function
    signature, _docstring, defaults = overloads[0]
    text = DEFAULT_PLACEHOLDER.sub("= __default__", signature)
    # The signature is "def name(params) -> ret"; the parameter list ends at the last ")" before
    # the return annotation.
    close = text.rindex(") -> ")
    tree = ast.parse(text[: close + 1] + ": ...")
    node = tree.body[0]
    names = [argument.arg for argument in node.args.args]
    kwarg = node.args.kwarg.arg if node.args.kwarg else None
    values = list(defaults) if defaults is not None else []
    # The placeholders and the reported values must agree, or a default would go unchecked.
    assert len(node.args.defaults) == len(values), (signature, defaults)
    return names, values, kwarg


def _resolve(api_name: str) -> object:
    """The module attribute the pyi name refers to: a function, or a class's method."""
    owner, _, member = api_name.partition(".")
    if not member:
        return getattr(_painterly, owner)
    return getattr(getattr(_painterly, owner), member)


def _defaults_match(pyi_default: ast.expr, runtime_default: object) -> bool:
    """The pyi's default expression against the value the module reports.

    Every default of the pyi is a literal (a number, a string, or a tuple of numbers), which
    `ast.literal_eval` reads without running any code. `pyi_default` is never None: the caller
    drops the parameters that have no default.
    """
    expected = ast.literal_eval(pyi_default)
    if isinstance(expected, tuple) and isinstance(runtime_default, tuple):
        return len(expected) == len(runtime_default) and all(
            left == right for left, right in zip(expected, runtime_default, strict=True)
        )
    return expected == runtime_default


def test_the_pyi_declares_the_public_api() -> None:
    """The parse finds the three functions and the two classes, so the checks below are real."""
    api = _pyi_public_api()
    assert {"version_info", "selftest", "integrator_sockets"} <= api.keys()
    assert {"Scene.__init__", "Scene.add_sphere", "Session.__init__", "Session.wait"} <= api.keys()
    assert "VersionInfo" not in api and "SocketInfo" not in api
    assert "LobeKind" not in api and "Lobe" not in api


def test_every_public_name_and_parameter_matches_the_pyi() -> None:
    """Every public function, class and method of the pyi exists with the same parameter names."""
    api = _pyi_public_api()
    for name, (pyi_names, _pyi_defaults, pyi_kwarg) in api.items():
        assert hasattr(_painterly, name.partition(".")[0]), name
        runtime_names, _runtime_defaults, runtime_kwarg = _runtime_signature(_resolve(name))
        assert runtime_names == pyi_names, name
        assert runtime_kwarg == pyi_kwarg, name


def test_every_public_default_matches_the_pyi() -> None:
    """Every default value of the pyi equals the value the module reports.

    Counting the defaults is not enough: the value itself is the contract (a changed `intersection`
    default of `add_sphere` changes what a sphere does), so each one is compared with the pyi's.
    """
    api = _pyi_public_api()
    for name, (pyi_names, pyi_defaults, _pyi_kwarg) in api.items():
        _runtime_names, runtime_defaults, _runtime_kwarg = _runtime_signature(_resolve(name))
        pyi_values = [default for default in pyi_defaults if default is not None]
        assert len(pyi_values) == len(runtime_defaults), name
        for pyi_default, runtime_default in zip(pyi_values, runtime_defaults, strict=True):
            assert _defaults_match(pyi_default, runtime_default), (
                name,
                ast.unparse(pyi_default),
                runtime_default,
            )
        assert len(pyi_names) >= len(pyi_values)


# --------------------------------------------------------------------------------------------------
# The bindings' effect: a tiny render whose answer follows from the core's source (TQ.3 F5)
# --------------------------------------------------------------------------------------------------
#
# The signature checks above cannot see a binding that keeps its signature and does the wrong thing:
# forwarding `set_camera_orthographic` to the perspective camera, swapping `add_sun`'s direction and
# its radiance, or writing a shifted row of `object_to_world` all pass them. Every test below
# renders a scene whose image follows in closed form from the core's own source, and the mutation
# named in the docstring makes that image differ. The images are 8 x 8, one pass, one thread.

#: The image side of the effect tests, in pixels. The answers below are closed forms, so the image
#: only has to be big enough to tell the shapes apart.
EFFECT_SIDE = 8


def _render(scene: _painterly.Scene) -> tuple[np.ndarray, np.ndarray]:
    """One pass of `scene` on one thread: the (H, W, 3) sums and the (H, W) object ids."""
    session = _painterly.Session(scene, 1)
    session.start(1, 1)
    assert session.wait() is True, session.progress()
    assert session.progress()["state"] == "done", session.progress()
    return session.combined(), session.object_id()


def _raster_to_camera(side: int) -> np.ndarray:
    """A pinhole's row-major 4x4 raster_to_camera: x = 2 (col + 0.5) / side - 1 and z = -1.

    painterly_camera_raster_to_camera (painterly/kernel/camera/camera.h) applies the matrix to
    (raster_x, raster_y, 0, 1) and divides by w, so the image plane is z = -1 and the image spans
    x, y in [-1, 1]. That is the pinhole this file's camera checks assume.
    """
    matrix = np.zeros((4, 4), dtype=np.float64)
    matrix[0, 0] = 2.0 / side
    matrix[0, 3] = -1.0
    matrix[1, 1] = 2.0 / side
    matrix[1, 3] = -1.0
    matrix[2, 3] = -1.0
    matrix[3, 3] = 1.0
    return matrix


def _pixel_centres(side: int) -> tuple[np.ndarray, np.ndarray]:
    """The raster x and y of every pixel centre, (side, side) each: the first two rows of
    `_raster_to_camera(side)` applied to (col + 0.5, row + 0.5)."""
    axis = 2.0 * (np.arange(side) + 0.5) / side - 1.0
    return (
        np.broadcast_to(axis[None, :], (side, side)),
        np.broadcast_to(axis[:, None], (side, side)),
    )


def _sphere_scene(depth: float, radius: float) -> _painterly.Scene:
    """One exact sphere of `radius` at (0, 0, -depth) and no other geometry, jitter off."""
    scene = _painterly.Scene()
    material = scene.add_material([("diffuse", (0.5, 0.5, 0.5), 0.0)])
    scene.add_sphere((0.0, 0.0, -depth), radius, material, "exact", 0)
    scene.set_integrator(jitter=0.0)
    return scene


# The sphere of the two camera tests, in world units.
CAMERA_DEPTH = 1.5
CAMERA_RADIUS = 0.5


def _pinhole_hit_radius() -> float:
    """x^2 + y^2 of the perspective silhouette of the sphere on the plane z = -1.

    The pinhole's ray leaves the origin along d = (x, y, -1), so the distance of the centre
    c = (0, 0, -depth) from the ray's line is |c x d| / |d| = depth sqrt(x^2 + y^2) /
    sqrt(x^2 + y^2 + 1). A ray hits the sphere of radius r iff that distance is at most r, i.e.
    iff (x^2 + y^2) (depth^2 - r^2) <= r^2: a disk of radius r / sqrt(depth^2 - r^2).
    """
    return CAMERA_RADIUS**2 / (CAMERA_DEPTH**2 - CAMERA_RADIUS**2)


def test_set_camera_perspective_projects_through_the_camera_origin() -> None:
    """The perspective camera is a pinhole: a sphere's image is the disk of `_pinhole_hit_radius`.

    Mutation (TQ.3 F5): forwarding `set_camera_perspective` to the orthographic camera, which makes
    the sphere's image the disk of radius r = 0.25 instead of 0.125.
    """
    scene = _sphere_scene(CAMERA_DEPTH, CAMERA_RADIUS)
    scene.set_camera_perspective(
        EFFECT_SIDE,
        EFFECT_SIDE,
        _raster_to_camera(EFFECT_SIDE),
        np.eye(3, 4, dtype=np.float64),
        "horizontal",
    )
    _combined, object_id = _render(scene)
    xs, ys = _pixel_centres(EFFECT_SIDE)
    expected = xs**2 + ys**2 <= _pinhole_hit_radius()
    assert np.array_equal(object_id == 0, expected), object_id
    # The two cameras disagree on this sphere, which is what the mutation above would produce.
    orthographic = xs**2 + ys**2 <= CAMERA_RADIUS**2
    assert not np.array_equal(expected, orthographic)


def test_set_camera_perspective_uses_camera_to_world() -> None:
    """camera_to_world's translation moves the camera and the image with it.

    Mutation: ignoring camera_to_world, or applying it to directions only, so that the pinhole
    stays at the world origin. The sphere moves with the camera here, so the image must not change.
    """
    translation = np.array([0.5, -0.25, 1.5])
    camera_to_world = np.zeros((3, 4), dtype=np.float64)
    camera_to_world[:3, :3] = np.eye(3)
    camera_to_world[:, 3] = translation

    at_origin = _sphere_scene(CAMERA_DEPTH, CAMERA_RADIUS)
    at_origin.set_camera_perspective(
        EFFECT_SIDE,
        EFFECT_SIDE,
        _raster_to_camera(EFFECT_SIDE),
        np.eye(3, 4, dtype=np.float64),
        "horizontal",
    )
    moved = _painterly.Scene()
    material = moved.add_material([("diffuse", (0.5, 0.5, 0.5), 0.0)])
    moved.add_sphere(
        tuple(translation + np.array([0.0, 0.0, -CAMERA_DEPTH])),
        CAMERA_RADIUS,
        material,
        "exact",
        0,
    )
    moved.set_integrator(jitter=0.0)
    moved.set_camera_perspective(
        EFFECT_SIDE,
        EFFECT_SIDE,
        _raster_to_camera(EFFECT_SIDE),
        camera_to_world,
        "horizontal",
    )

    combined_at_origin, ids_at_origin = _render(at_origin)
    combined_moved, ids_moved = _render(moved)
    # Both images are the pinhole disk, so the sphere is visible in both.
    assert np.count_nonzero(ids_at_origin == 0) == np.count_nonzero(ids_moved == 0) > 0
    assert np.array_equal(ids_moved, ids_at_origin)
    assert np.array_equal(combined_moved, combined_at_origin)


def test_set_camera_orthographic_uses_parallel_rays() -> None:
    """The orthographic camera's rays are parallel, so a sphere's image is its own outline.

    Every ray starts at (x, y, 0) along -z (painterly/kernel/camera/camera.h), so a sphere of
    radius r at (0, 0, -depth) is hit iff x^2 + y^2 <= r^2, whatever the depth is. Mutation (TQ.3
    F5): forwarding `set_camera_orthographic` to the perspective camera, whose image is the smaller
    disk of `_pinhole_hit_radius` and does depend on the depth.
    """
    near, far = 2.0, 4.0
    images = []
    for depth in (near, far):
        scene = _sphere_scene(depth, CAMERA_RADIUS)
        scene.set_camera_orthographic(
            EFFECT_SIDE,
            EFFECT_SIDE,
            _raster_to_camera(EFFECT_SIDE),
            np.eye(3, 4, dtype=np.float64),
            "horizontal",
        )
        images.append(_render(scene))
    (combined_near, ids_near), (combined_far, ids_far) = images

    xs, ys = _pixel_centres(EFFECT_SIDE)
    expected = xs**2 + ys**2 <= CAMERA_RADIUS**2
    assert np.array_equal(ids_near == 0, expected), ids_near
    # Parallel rays: the same silhouette at both depths, and the same sums.
    assert np.array_equal(ids_far, ids_near)
    assert np.array_equal(combined_far, combined_near)
    # The perspective camera at these two depths gives two different images.
    perspective = []
    for depth in (near, far):
        scene = _sphere_scene(depth, CAMERA_RADIUS)
        scene.set_camera_perspective(
            EFFECT_SIDE,
            EFFECT_SIDE,
            _raster_to_camera(EFFECT_SIDE),
            np.eye(3, 4, dtype=np.float64),
            "horizontal",
        )
        perspective.append(_render(scene)[1])
    assert not np.array_equal(perspective[0], perspective[1])
    assert not np.array_equal(perspective[0], ids_near)


#: The suns of `test_add_sun_is_an_angular_disk_of_its_direction_and_radiance`: direction (toward
#: the sun, world space), angular diameter in radians, and radiance. The angles are chosen so that
#: no pixel's ray lies within 4e-3 of a cone edge, so the binary64 round-off of the closed form
#: below cannot move a pixel across the edge: the mask is a strict inequality with that margin.
SUNS = (
    ((0.0, 0.0, -1.0), 1.0, (1.0, 2.0, 3.0)),
    ((1.0, 0.0, -1.0), 0.6, (0.5, 0.25, 0.125)),
    ((0.0, 1.0, 0.0), 2.0, (0.125, 0.5, 2.0)),
)


def _sun_scene() -> _painterly.Scene:
    """An empty scene whose only light is SUNS, seen by a pinhole camera, emission gain 1."""
    scene = _painterly.Scene()
    scene.set_background((0.0, 0.0, 0.0))
    for direction, angle, radiance in SUNS:
        scene.add_sun(direction, angle, radiance)
    scene.set_integrator(jitter=0.0, emission_gain=1.0)
    scene.set_camera_perspective(
        EFFECT_SIDE,
        EFFECT_SIDE,
        _raster_to_camera(EFFECT_SIDE),
        np.eye(3, 4, dtype=np.float64),
        "horizontal",
    )
    return scene


def _sun_image(suns) -> np.ndarray:
    """The closed-form image of `_sun_scene`: every sun whose disk holds the ray's direction.

    painterly_background_radiance (painterly/kernel/light/background.h) adds a sun's radiance iff
    dot(normalize(d), direction) >= cos(angle / 2), in sun order, and the path's only vertex is the
    background term 0 + radiance * emission_gain (painterly/kernel/integrator/path.h), so with
    emission_gain = 1 the sum is exact. `suns` is a sequence of (direction, angle, radiance).
    """
    xs, ys = _pixel_centres(EFFECT_SIDE)
    points = np.stack([xs, ys, -np.ones_like(xs)], axis=-1)
    directions = points / np.linalg.norm(points, axis=-1, keepdims=True)
    image = np.zeros((EFFECT_SIDE, EFFECT_SIDE, 3), dtype=np.float64)
    for direction, angle, radiance in suns:
        axis = np.asarray(direction, dtype=np.float64)
        axis = axis / np.linalg.norm(axis)
        image += (directions @ axis >= np.cos(0.5 * angle))[..., None] * np.asarray(radiance)
    return image


def test_add_sun_is_an_angular_disk_of_its_direction_and_radiance() -> None:
    """add_sun's three arguments reach the kernel in their own roles, exactly.

    Mutation (TQ.3 F5): swapping `add_sun`'s direction and radiance in python.cpp, which lights a
    different set of pixels with a different colour (asserted at the end).
    """
    combined, _object_id = _render(_sun_scene())
    expected = _sun_image(SUNS)
    assert np.array_equal(combined, expected)
    # The image is not the trivial all-zero or all-lit one, so the check has content.
    lit = expected.max(axis=2) > 0
    assert 0 < np.count_nonzero(lit) < EFFECT_SIDE * EFFECT_SIDE
    # The mutation's image: direction and radiance exchanged.
    swapped = _sun_image([(radiance, angle, direction) for direction, angle, radiance in SUNS])
    assert not np.array_equal(swapped, expected)


#: The spiral object of `test_set_spiral_object_rotates_the_diffuse_bounce`, and the two closed-form
#: values its rows give. The scene below is one plane whose normal is (0, 0, 1) at z = -4, the
#: background 0.25 / 0.5 / 0.75, and the reference albedo 0.5; the first diffuse bounce draws
#: u1 = vdc(1) = 0.5 exactly (SPEC §2), so s = (cos(pi) r, sin(pi) r, 0.5) with r = sqrt(3) / 2,
#: and the bounce's cost is dot(N + F s, N) = 1 + (F s).z. Only the z entry of F's last row is
#: needed, which is why no trigonometric value enters the two expected numbers below.
SPIRAL_FLIP = np.diag([1.0, 1.0, -1.0])
#: The background and the emission gain the core starts with: 2.0 is the gain socket's default
#: (painterly/scene/integrator.cpp), not a tuning value.
SPIRAL_BACKGROUND = np.array([0.25, 0.5, 0.75])
EMISSION_GAIN = 2.0
#: The pixel's radiance per channel: background * emission_gain * cost * albedo, cost being
#: 1 + (F s).z, which is 1.5 for F = I and 0.5 for F = diag(1, 1, -1).
SPIRAL_IDENTITY_VALUE = SPIRAL_BACKGROUND * EMISSION_GAIN * 1.5 * 0.5
SPIRAL_FLIP_VALUE = SPIRAL_BACKGROUND * EMISSION_GAIN * 0.5 * 0.5
#: A cyclic permutation and its transpose. (F s).z is the third row of F against s, so it is s.x
#: for SPIRAL_CYCLE (its third row is (1, 0, 0)) and s.y for its transpose (third row (0, 1, 0)).
#: The two values are -sqrt(3)/2 and 0, which tells a written F from a written F^T.
SPIRAL_CYCLE = np.array([[0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]])
#: The spiral direction's x and y for the bounce above, bounded. s = (cos(phi) r, sin(phi) r, u1)
#: with u1 = 0.5 exactly, r = sqrt(1 - u1^2) = sqrt(3)/2 and phi = 2 * SMALLPAINT_PI * u1 =
#: SMALLPAINT_PI = 3.1415926536 (painterly/kernel/smallpaint.h:15). That differs from pi by
#: 3.6e-11, and libm's sin and cos are within a few units in the last place of the exact values, so
#: |sin(phi)| <= 3.7e-11 and |cos(phi) + 1| <= 3.7e-11: s.x = -0.866025... within 3.7e-11 and
#: |s.y| <= 3.7e-11. SPIRAL_DIRECTION_BOUND is that 3.7e-11 rounded up to 4e-11.
SPIRAL_DIRECTION_BOUND = 4e-11


def _spiral_scene() -> _painterly.Scene:
    """A 1 x 1 render of one plane, with the object spiral frame and the image chain.

    chain="image" starts K at 0 (SPEC §3), so the first diffuse bounce of the single pixel draws
    u1 = vdc(1) = 0.5; max_depth=2 ends the path after its second miss.
    """
    scene = _painterly.Scene()
    material = scene.add_material([("diffuse", (0.5, 0.5, 0.5), 0.0)])
    scene.add_plane((0.0, 0.0, 1.0), 4.0, material)
    scene.set_background(tuple(SPIRAL_BACKGROUND))
    scene.set_camera_smallpaint(1, 1)
    scene.set_integrator(chain="image", spiral_frame="object", max_depth=2)
    return scene


def test_set_spiral_object_rotates_the_diffuse_bounce() -> None:
    """set_spiral_object's matrix is the F of spiral_frame "object" (SPEC §1).

    The closed forms: with F = I the bounce's cost is 1.5 and the pixel is 0.375; with
    F = diag(1, 1, -1) it is 0.5 and the pixel is 0.125; with a cyclic permutation and its transpose
    the cost is 1 - sqrt(3)/2 and 1. Mutations (TQ.3 F5): ignoring the argument, transposing it
    (which swaps the last two images), and accepting spiral_frame "object" with no spiral object.
    """
    identity = _spiral_scene()
    identity.set_spiral_object(np.eye(3, dtype=np.float64))
    flipped = _spiral_scene()
    flipped.set_spiral_object(SPIRAL_FLIP)
    cycled = _spiral_scene()
    cycled.set_spiral_object(SPIRAL_CYCLE)
    transposed = _spiral_scene()
    transposed.set_spiral_object(np.ascontiguousarray(SPIRAL_CYCLE.T))

    combined_identity = _render(identity)[0]
    combined_flipped = _render(flipped)[0]
    assert np.array_equal(combined_identity, np.broadcast_to(SPIRAL_IDENTITY_VALUE, (1, 1, 3)))
    assert np.array_equal(combined_flipped, np.broadcast_to(SPIRAL_FLIP_VALUE, (1, 1, 3)))
    # The two cyclic matrices pick the spiral's two other coordinates: (F s).z is s.y for the
    # transpose, which is within SPIRAL_DIRECTION_BOUND of 0, and s.x for SPIRAL_CYCLE, which is
    # within SPIRAL_DIRECTION_BOUND of -sqrt(3)/2. The cost is 1 + (F s).z, so the two images are
    # closed forms whose bound is SPIRAL_DIRECTION_BOUND times the pixel's scale. A written F^T
    # gives the other image.
    scale = SPIRAL_BACKGROUND * EMISSION_GAIN * 0.5
    combined_cycled = _render(cycled)[0]
    combined_transposed = _render(transposed)[0]
    cycle_expected = scale * (1.0 - math.sqrt(3.0) / 2.0)
    transpose_expected = scale * (1.0 + 0.0)
    assert np.all(np.abs(combined_cycled - cycle_expected) <= scale * SPIRAL_DIRECTION_BOUND)
    assert np.all(
        np.abs(combined_transposed - transpose_expected) <= scale * SPIRAL_DIRECTION_BOUND
    )
    # And the three matrices give three different images, so the checks above are not all one.
    for first, second in (
        (combined_identity, combined_cycled),
        (combined_identity, combined_transposed),
        (combined_cycled, combined_transposed),
    ):
        assert not np.array_equal(first, second)

    # spiral_frame "object" without a spiral object is an error of the scene's device_update.
    unset = _spiral_scene()
    session = _painterly.Session(unset, 1)
    with pytest.raises(ValueError, match="no spiral object is set"):
        session.start(1, 1)


def test_scene_clear_restores_the_scene_of_a_new_scene() -> None:
    """Scene.clear() empties every list, resets the integrator, the camera and the spiral object.

    Mutation: a clear() that forgets one of them. The cleared scene's integrator must equal a new
    scene's; its material and object id counters must restart at 0; its camera must be back to the
    empty 0 x 0 default, so a render publishes the empty buffers; and the spiral object must be
    gone, so spiral_frame "object" fails again.
    """
    scene = _painterly.Scene()
    material = scene.add_material([("diffuse", (0.5, 0.5, 0.5), 0.0)])
    assert material == 0
    scene.add_plane((0.0, 0.0, 1.0), 4.0, material, 5)
    scene.set_background((0.25, 0.5, 0.75))
    scene.set_camera_smallpaint(EFFECT_SIDE, EFFECT_SIDE)
    scene.set_integrator(chain="lane", lane_length=3)
    scene.set_spiral_object(SPIRAL_FLIP)
    combined, object_id = _render(scene)
    assert np.all(object_id == 5)
    assert np.all(combined != 0.0)

    scene.clear()
    assert scene.get_integrator() == _painterly.Scene().get_integrator()
    # The material list is empty: the next material is 0 again.
    assert scene.add_material([("diffuse", (0.5, 0.5, 0.5), 0.0)]) == 0
    # The object id counter restarted: an object added with the automatic id gets 0, though the
    # plane above had the requested id 5, which had left the counter at 6.
    scene.set_camera_smallpaint(EFFECT_SIDE, EFFECT_SIDE)
    scene.add_plane((0.0, 0.0, 1.0), 4.0, 0)
    _combined, object_id = _render(scene)
    assert np.all(object_id == 0), object_id
    # The camera is the empty default: a 0 x 0 image, so the buffers are empty.
    scene.clear()
    session = _painterly.Session(scene, 1)
    session.start(1, 1)
    assert session.wait() is True, session.progress()
    assert session.combined().shape == (0, 0, 3)
    assert session.k_consumed().shape == (0, 0)
    # The spiral object is gone: the frame is back to the identity of a scene that has none, so
    # spiral_frame "object" has nothing to rotate by.
    scene.set_integrator(spiral_frame="object")
    session = _painterly.Session(scene, 1)
    with pytest.raises(ValueError, match="no spiral object is set"):
        session.start(1, 1)


#: The spot of `test_add_sphere_spot_scales_the_emission_inside_the_cone`: a cone of half-angle
#: acos(0.9) around +z. The sphere below is exact and seen by the orthographic camera, so a pixel's
#: hit point is (x, y, -2 + sqrt(r_s^2 - x^2 - y^2)) and its normal is
#: (x, y, sqrt(r_s^2 - x^2 - y^2)) / r_s: its z entry is sqrt(r_s^2 - x^2 - y^2) / r_s.
SPOT_RADIUS = 0.5
SPOT_COS_HALF_ANGLE = 0.9


def _spot_scene(spot) -> _painterly.Scene:
    """One exact sphere of an emissive material, seen by the orthographic camera, jitter off."""
    scene = _painterly.Scene()
    material = scene.add_material([("diffuse", (0.5, 0.5, 0.5), 0.0)], emission=(1.0, 1.0, 1.0))
    scene.add_sphere((0.0, 0.0, -2.0), SPOT_RADIUS, material, "exact", 0, spot)
    scene.set_integrator(continue_after_emitter=False, jitter=0.0)
    scene.set_camera_orthographic(
        EFFECT_SIDE,
        EFFECT_SIDE,
        _raster_to_camera(EFFECT_SIDE),
        np.eye(3, 4, dtype=np.float64),
        "horizontal",
    )
    return scene


def test_add_sphere_spot_scales_the_emission_inside_the_cone() -> None:
    """add_sphere(spot=...) reaches the kernel as the cone of the ghost sphere (SPEC §5).

    The sphere's emission is 1 and emission_gain is 2, so a lit pixel is 2 * attenuation, exactly
    2.0 outside the cone edge and 0.0 beyond it. Mutations (TQ.3 F5): dropping the spot, passing
    the axis where the cone half-angle goes (or its cosine where the axis goes), and ignoring the
    blend. The image is (0.25 * x^2 + y^2) <= SPOT_RADIUS^2: the sphere's outline, whose four
    inner pixels see a normal z of sqrt(0.25 - 0.03125) / 0.5 = 0.935, above 0.9, and whose eight
    outer ones see sqrt(0.25 - 0.15625) / 0.5 = 0.612, below it.
    """
    xs, ys = _pixel_centres(EFFECT_SIDE)
    radii_squared = xs**2 + ys**2
    on_sphere = radii_squared <= SPOT_RADIUS**2
    normal_z = np.sqrt(np.maximum(SPOT_RADIUS**2 - radii_squared, 0.0)) / SPOT_RADIUS
    inside = on_sphere & (normal_z > SPOT_COS_HALF_ANGLE)
    assert 0 < np.count_nonzero(inside) < np.count_nonzero(on_sphere)

    unspotted = _render(_spot_scene(None))[0]
    assert np.array_equal(unspotted.max(axis=2) > 0, on_sphere)
    assert np.all(unspotted[on_sphere] == 2.0)

    hard_edge = _render(_spot_scene(((0.0, 0.0, 1.0), SPOT_COS_HALF_ANGLE, 0.0)))[0]
    assert np.array_equal(hard_edge.max(axis=2) > 0, inside)
    assert np.all(hard_edge[inside] == 2.0)

    # The axis is the cone's direction: -z puts the whole sphere outside it.
    opposite = _render(_spot_scene(((0.0, 0.0, -1.0), SPOT_COS_HALF_ANGLE, 0.0)))[0]
    assert np.all(opposite == 0.0)

    # blend = 1 fades the cone over its whole width: the same pixels, dimmer, and each strictly
    # between 0 and the unspotted 2.0. No tolerance: the four are compared with each other, and
    # the fade's exact value is the kernel's smoothstep, which this test does not re-derive.
    faded = _render(_spot_scene(((0.0, 0.0, 1.0), SPOT_COS_HALF_ANGLE, 1.0)))[0]
    assert np.array_equal(faded.max(axis=2) > 0, inside)
    faded_values = faded[inside]
    assert np.all(faded_values > 0.0) and np.all(faded_values < 2.0)
    assert np.all(faded_values == faded_values[0])


def test_add_object_applies_a_non_identity_object_to_world() -> None:
    """add_object's object_to_world maps the mesh's object space to world space, row by row.

    The quad spans (0, 0, 0) to (1, 1, 0) and the transform translates it by (0.25, -0.5, -1), so
    the orthographic camera sees it on the pixel centres with x in [0.25, 1.25] and y in
    [-0.5, 0.5], exactly: the quad's corners, its edges and the pixel centres are all dyadic.
    Mutation (TQ.3 F5): a shifted row in `object_to_world_from_python`, which moves the quad.
    """
    scene = _painterly.Scene()
    scene.add_material([("diffuse", (0.5, 0.5, 0.5), 0.0)])
    quad = np.array(
        [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [1.0, 1.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32
    )
    triangles = np.array([[0, 1, 2], [0, 2, 3]], dtype=np.uint32)
    mesh = scene.add_mesh(quad, triangles, np.zeros(2, dtype=np.int32))
    object_to_world = np.array(
        [[1.0, 0.0, 0.0, 0.25], [0.0, 1.0, 0.0, -0.5], [0.0, 0.0, 1.0, -1.0]], dtype=np.float32
    )
    assert scene.add_object(mesh, object_to_world, 7) == 0
    scene.set_integrator(jitter=0.0)
    scene.set_camera_orthographic(
        EFFECT_SIDE,
        EFFECT_SIDE,
        _raster_to_camera(EFFECT_SIDE),
        np.eye(3, 4, dtype=np.float64),
        "horizontal",
    )
    _combined, object_id = _render(scene)
    xs, ys = _pixel_centres(EFFECT_SIDE)
    expected = (xs >= 0.25) & (xs <= 1.25) & (ys >= -0.5) & (ys <= 0.5)
    assert np.array_equal(object_id == 7, expected), object_id
    assert 0 < np.count_nonzero(expected) < EFFECT_SIDE * EFFECT_SIDE
    # The identity transform of the same mesh sees a different part of the image, so the check
    # above really reads object_to_world.
    identity_scene = _painterly.Scene()
    identity_scene.add_material([("diffuse", (0.5, 0.5, 0.5), 0.0)])
    identity_mesh = identity_scene.add_mesh(quad, triangles, np.zeros(2, dtype=np.int32))
    identity_scene.add_object(identity_mesh, np.eye(3, 4, dtype=np.float32), 7)
    identity_scene.set_integrator(jitter=0.0)
    identity_scene.set_camera_orthographic(
        EFFECT_SIDE,
        EFFECT_SIDE,
        _raster_to_camera(EFFECT_SIDE),
        np.eye(3, 4, dtype=np.float64),
        "horizontal",
    )
    _identity_combined, identity_ids = _render(identity_scene)
    assert not np.array_equal(identity_ids, object_id)


def test_integrator_sockets_are_complete() -> None:
    """Every entry has every SocketInfo key, in socket order, with the pyi's types and items."""
    keys = {
        "name",
        "type",
        "default",
        "enum_items",
        "min",
        "max",
        "soft_min",
        "soft_max",
        "ui_name",
        "description",
        "group",
    }
    groups = {"Sampling", "Brush", "Path", "Lights", "Film"}
    sockets = _painterly.integrator_sockets()
    assert len(sockets) == 21
    names = [socket["name"] for socket in sockets]
    assert names == [
        "chain",
        "lane_length",
        "seed",
        "seed_per_frame",
        "passes",
        "spiral_frame",
        "spiral_rotation",
        "u2_mode",
        "k0_phase_lock_bits",
        "alpha",
        "max_depth",
        "diffuse_gain",
        "emission_gain",
        "continue_after_emitter",
        "ray_epsilon",
        "two_sided",
        "emission_scale",
        "ghost_lights",
        "output_mode",
        "exposure",
        "jitter",
    ]
    by_name = {socket["name"]: socket for socket in sockets}
    for socket in sockets:
        assert set(socket) == keys, socket["name"]
        assert socket["type"] in {"boolean", "int", "uint", "float", "enum", "vector"}
        assert socket["group"] in groups
        assert isinstance(socket["ui_name"], str) and socket["ui_name"]
        assert isinstance(socket["description"], str) and socket["description"]
        for limit in ("min", "max", "soft_min", "soft_max"):
            assert socket[limit] is None or isinstance(socket[limit], float), (
                socket["name"],
                limit,
            )
        if socket["type"] != "enum":
            assert socket["enum_items"] == [], socket["name"]
        for item in socket["enum_items"]:
            assert isinstance(item, str)

    # The enum items are the C++ value order (D16), and the default is one of them.
    assert by_name["chain"]["enum_items"] == ["image", "row", "lane"]
    assert by_name["chain"]["default"] == "row"
    assert by_name["u2_mode"]["enum_items"] == ["same", "independent"]
    assert by_name["u2_mode"]["default"] == "same"
    assert by_name["spiral_frame"]["enum_items"] == ["camera", "world", "object", "smallpaint"]
    assert by_name["spiral_frame"]["default"] == "camera"
    assert by_name["output_mode"]["enum_items"] == ["display_referred", "scene_linear"]
    assert by_name["output_mode"]["default"] == "display_referred"

    # The other socket types and their defaults, as painterly/scene/integrator.cpp sets them.
    assert by_name["lane_length"]["type"] == "int" and by_name["lane_length"]["default"] == 16
    assert by_name["seed"]["type"] == "uint" and by_name["seed"]["default"] == 0
    assert by_name["seed_per_frame"]["type"] == "boolean"
    assert by_name["seed_per_frame"]["default"] is False
    assert by_name["continue_after_emitter"]["default"] is True
    assert by_name["spiral_rotation"]["type"] == "vector"
    assert by_name["spiral_rotation"]["default"] == (0.0, 0.0, 0.0)
    assert by_name["max_depth"]["default"] == 20
    assert by_name["k0_phase_lock_bits"]["default"] == 0
    assert by_name["jitter"]["default"] == float(np.float32(1.0 / 1400.0))


def test_a_float_socket_accepts_numpy_float32_a_float_and_an_int() -> None:
    """A float socket takes any real number and stores its float32 value (the pyi's contract)."""
    scene = _painterly.Scene()
    expected = float(np.float32(0.1))
    scene.set_integrator(alpha=np.float32(0.1))
    assert scene.get_integrator()["alpha"] == expected
    scene.set_integrator(alpha=0.1)
    assert scene.get_integrator()["alpha"] == expected
    scene.set_integrator(alpha=2)
    assert scene.get_integrator()["alpha"] == 2.0


def test_set_integrator_round_trips_every_socket() -> None:
    """Every socket's value comes back from get_integrator, converted by its type."""
    scene = _painterly.Scene()
    scene.set_integrator(
        chain="lane",
        lane_length=3,
        seed=7,
        seed_per_frame=True,
        passes=12,
        spiral_frame="world",
        spiral_rotation=(0.25, -0.5, 1.0),
        u2_mode="independent",
        k0_phase_lock_bits=22,
        alpha=0.5,
        max_depth=1,
        diffuse_gain=0.25,
        emission_gain=4.0,
        continue_after_emitter=False,
        ray_epsilon=0.0,
        two_sided=False,
        emission_scale=2.0,
        ghost_lights=False,
        output_mode="scene_linear",
        exposure=0.5,
        jitter=0.0,
    )
    values = scene.get_integrator()
    assert values["chain"] == "lane"
    assert values["lane_length"] == 3
    assert values["seed"] == 7
    assert values["seed_per_frame"] is True
    assert values["passes"] == 12
    assert values["spiral_frame"] == "world"
    assert values["spiral_rotation"] == (0.25, -0.5, 1.0)
    assert values["u2_mode"] == "independent"
    assert values["k0_phase_lock_bits"] == 22
    assert values["alpha"] == 0.5
    assert values["max_depth"] == 1
    assert values["diffuse_gain"] == 0.25
    assert values["emission_gain"] == 4.0
    assert values["continue_after_emitter"] is False
    assert values["ray_epsilon"] == 0.0
    assert values["two_sided"] is False
    assert values["emission_scale"] == 2.0
    assert values["ghost_lights"] is False
    assert values["output_mode"] == "scene_linear"
    assert values["exposure"] == 0.5
    assert values["jitter"] == 0.0


def test_set_integrator_rejects_unknown_names_and_wrong_types() -> None:
    """An unknown name, a wrong type and an unknown enum identifier all raise ValueError.

    The exception is ValueError for the wrong types too, never TypeError: card T3.15 line 24 and
    src/blender/_painterly.pyi:125 (Opus ruling R44, 2026-10-22).
    """
    scene = _painterly.Scene()
    with pytest.raises(ValueError):
        scene.set_integrator(no_such_socket=1)
    with pytest.raises(ValueError):
        scene.set_integrator(chain="no_such_chain")
    with pytest.raises(ValueError):
        scene.set_integrator(chain=1)
    with pytest.raises(ValueError):
        scene.set_integrator(lane_length="16")
    with pytest.raises(ValueError):
        scene.set_integrator(two_sided=1)
    with pytest.raises(ValueError):
        scene.set_integrator(alpha="0.5")
    with pytest.raises(ValueError):
        scene.set_integrator(spiral_rotation=(0.0, 0.0))


def test_a_rejected_set_integrator_call_sets_nothing() -> None:
    """Every knob is converted before any is stored, so a raising call changes no socket.

    The good knob comes first in each call, so a conversion applied knob by knob would have stored
    it before the bad knob raised (M3-FIX-T3.15a, Do: "Look up and convert every knob before
    setting any, so a call that raises changes nothing").
    """
    scene = _painterly.Scene()
    before = scene.get_integrator()
    with pytest.raises(ValueError):
        scene.set_integrator(lane_length=3, max_depth=0)
    assert scene.get_integrator() == before
    with pytest.raises(ValueError):
        scene.set_integrator(alpha=0.25, two_sided=1)
    assert scene.get_integrator() == before


def test_set_integrator_rejects_the_kernel_preconditions() -> None:
    """lane_length < 1, k0_phase_lock_bits outside 0…22 and max_depth < 1 raise ValueError."""
    scene = _painterly.Scene()
    with pytest.raises(ValueError):
        scene.set_integrator(lane_length=0)
    with pytest.raises(ValueError):
        scene.set_integrator(k0_phase_lock_bits=23)
    # Negative, not only above the top of the range (TQ.3 F17).
    with pytest.raises(ValueError):
        scene.set_integrator(k0_phase_lock_bits=-1)
    with pytest.raises(ValueError):
        scene.set_integrator(max_depth=0)


def test_set_integrator_rejects_the_three_wrong_types_of_the_audit() -> None:
    """A bool for an int socket, a string in a vector, and a negative phase lock (TQ.3 F17).

    Each site had no test: a bool is not an int, a vector's entries go through `as_real`, and the
    phase lock's lower bound was unchecked. The messages are the bindings' own, so a reworded one
    fails here too.
    """
    scene = _painterly.Scene()
    with pytest.raises(ValueError, match=r"lane_length must be an int, not a bool"):
        scene.set_integrator(lane_length=True)
    with pytest.raises(ValueError, match=r"spiral_rotation must be a real number"):
        scene.set_integrator(spiral_rotation=(0, 0, "a"))
    with pytest.raises(ValueError, match=r"k0_phase_lock_bits must be in 0…22"):
        scene.set_integrator(k0_phase_lock_bits=-1)


class _FloatRaises:
    """An object whose __float__ raises, as a user's own type might (TQ.3 F18)."""

    def __float__(self) -> float:
        raise ArithmeticError("no float for you")


class _IndexRaises:
    """An object whose __index__ raises, for the int sockets (TQ.3 F18)."""

    def __index__(self) -> int:
        raise ArithmeticError("no index for you")


def test_a_rejected_conversion_keeps_the_python_exception_as_its_cause() -> None:
    """A wrong-type ValueError keeps the original Python exception as __cause__ (TQ.3 F18).

    The bindings report their own message, which is unchanged, and chain the exception the
    conversion really raised onto it, as `raise ... from ...` does. A bare PyErr_Clear() discarded
    it: alpha=10**400 said only "must be a real number", and a user's failing __float__ vanished.
    """
    scene = _painterly.Scene()

    with pytest.raises(ValueError) as too_large:
        scene.set_integrator(alpha=10**400)
    assert str(too_large.value) == "set_integrator: alpha must be a real number"
    assert isinstance(too_large.value.__cause__, OverflowError), too_large.value.__cause__
    assert too_large.value.__cause__ is too_large.value.__context__

    with pytest.raises(ValueError) as float_raises:
        scene.set_integrator(alpha=_FloatRaises())
    assert str(float_raises.value) == "set_integrator: alpha must be a real number"
    assert isinstance(float_raises.value.__cause__, ArithmeticError)
    assert str(float_raises.value.__cause__) == "no float for you"

    with pytest.raises(ValueError) as index_raises:
        scene.set_integrator(lane_length=_IndexRaises())
    assert str(index_raises.value) == "set_integrator: lane_length must be an int"
    assert isinstance(index_raises.value.__cause__, ArithmeticError)
    assert str(index_raises.value.__cause__) == "no index for you"

    with pytest.raises(ValueError) as int_too_large:
        scene.set_integrator(lane_length=10**400)
    assert str(int_too_large.value) == "set_integrator: lane_length is out of range"
    assert isinstance(int_too_large.value.__cause__, OverflowError)

    # A Scene method that takes a real keeps TypeError, with the cause of the same conversion.
    with pytest.raises(TypeError) as plane:
        scene.add_plane((0.0, 0.0, 1.0), _FloatRaises(), 0)
    assert str(plane.value) == "Scene.add_plane: d must be a real number"
    assert isinstance(plane.value.__cause__, ArithmeticError)

    # A rejected knob still stores nothing, cause or not.
    before = scene.get_integrator()
    with pytest.raises(ValueError):
        scene.set_integrator(alpha=_FloatRaises())
    assert scene.get_integrator() == before


def test_the_k0_phase_lock_message_names_the_range_of_the_kernel() -> None:
    """The message's range is built from PAINTERLY_K0_BITS, not written out beside it (TQ.3 F17).

    The upper bound the module reports for the socket is the same 22, so the message, the check and
    the UI limit cannot drift apart. painterly/kernel/sample/sampler.h:22 defines
    PAINTERLY_K0_BITS = 22.
    """
    sockets = {socket["name"]: socket for socket in _painterly.integrator_sockets()}
    top = int(sockets["k0_phase_lock_bits"]["max"])
    assert top == 22
    scene = _painterly.Scene()
    with pytest.raises(ValueError) as raised:
        scene.set_integrator(k0_phase_lock_bits=top + 1)
    assert str(raised.value) == f"set_integrator: k0_phase_lock_bits must be in 0…{top}"


def _triangle_scene() -> tuple[_painterly.Scene, int]:
    """One triangle in the plane z = 0 and a diffuse material, as the mesh tests need them."""
    scene = _painterly.Scene()
    material = scene.add_material([("diffuse", (0.5, 0.5, 0.5), 0.0)])
    return scene, material


VERTICES = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
TRIANGLES = np.array([[0, 1, 2]], dtype=np.uint32)
TRI_MATERIAL = np.array([0], dtype=np.int32)


def test_add_mesh_accepts_the_contract_arrays() -> None:
    """The stated dtypes and shapes are accepted, with and without corner normals."""
    scene, _material = _triangle_scene()
    assert scene.add_mesh(VERTICES, TRIANGLES, TRI_MATERIAL) == 0
    corner_normals = np.zeros((1, 3, 3), dtype=np.float32)
    assert scene.add_mesh(VERTICES, TRIANGLES, TRI_MATERIAL, corner_normals) == 1


def test_add_mesh_rejects_wrong_dtypes() -> None:
    """Every array of add_mesh must have its exact dtype: there is no silent conversion."""
    scene, _material = _triangle_scene()
    with pytest.raises(TypeError):
        scene.add_mesh(VERTICES.astype(np.float64), TRIANGLES, TRI_MATERIAL)
    with pytest.raises(TypeError):
        scene.add_mesh(VERTICES, TRIANGLES.astype(np.int32), TRI_MATERIAL)
    with pytest.raises(TypeError):
        scene.add_mesh(VERTICES, TRIANGLES, TRI_MATERIAL.astype(np.int64))
    with pytest.raises(TypeError):
        scene.add_mesh(VERTICES, TRIANGLES, TRI_MATERIAL, np.zeros((1, 3, 3), dtype=np.float64))


def test_add_mesh_rejects_wrong_shapes_and_non_contiguous_arrays() -> None:
    """A wrong rank, a wrong extent or a non-C-contiguous array raises TypeError."""
    scene, _material = _triangle_scene()
    with pytest.raises(TypeError):
        scene.add_mesh(VERTICES.ravel(), TRIANGLES, TRI_MATERIAL)
    with pytest.raises(TypeError):
        scene.add_mesh(VERTICES, TRIANGLES.reshape(1, 3, 1), TRI_MATERIAL)
    with pytest.raises(TypeError):
        scene.add_mesh(VERTICES, TRIANGLES, np.zeros(2, dtype=np.int32))
    with pytest.raises(TypeError):
        scene.add_mesh(VERTICES, TRIANGLES, TRI_MATERIAL, np.zeros((1, 3, 1), dtype=np.float32))
    # A C-contiguous array is required: every second column of a (4, 8) matrix has the right shape
    # and dtype but is not C-contiguous.
    strided = np.zeros((4, 8), dtype=np.float64)[:, ::2]
    assert not strided.flags["C_CONTIGUOUS"]
    with pytest.raises(TypeError):
        scene.set_camera_perspective(4, 4, strided, np.eye(3, 4), "horizontal")
    # And the dtype is part of the contract too: a float32 raster_to_camera is rejected.
    with pytest.raises(TypeError):
        scene.set_camera_perspective(4, 4, np.zeros((4, 4), dtype=np.float32), np.eye(3, 4), "x")


def test_add_object_accepts_a_3x4_and_a_4x4_transform() -> None:
    """object_to_world is float32 (3, 4) or (4, 4), row-major."""
    scene, _material = _triangle_scene()
    mesh = scene.add_mesh(VERTICES, TRIANGLES, TRI_MATERIAL)
    assert scene.add_object(mesh, np.eye(3, 4, dtype=np.float32)) == 0
    assert scene.add_object(mesh, np.eye(4, 4, dtype=np.float32)) == 1
    with pytest.raises(TypeError):
        scene.add_object(mesh, np.eye(3, 4, dtype=np.float64))
    with pytest.raises(TypeError):
        scene.add_object(mesh, np.eye(3, 3, dtype=np.float32))


def test_a_session_holds_a_reference_to_its_scene() -> None:
    """Session.__init__ is bound with keep_alive<1, 2>, and the reference count shows it.

    The behavioural check below would also pass on a dangling pointer, which is undefined behaviour
    and happens to read a freed but untouched Scene (TQ.3 F23). This one is deterministic:
    `sys.getrefcount` of the Scene is one higher while a Session exists, and back to its own value
    once the Session is gone. `sys.getrefcount` adds its own argument's reference, the same in both
    calls, so only the difference is asserted.
    """
    scene = _painterly.Scene()
    alone = sys.getrefcount(scene)
    session = _painterly.Session(scene, 1)
    held = sys.getrefcount(scene)
    assert held - alone == 1, (alone, held)
    del session
    assert sys.getrefcount(scene) == alone


def test_the_python_scene_outlives_a_deleted_reference_through_its_session() -> None:
    """The Scene a Session was built from lives as long as the Session, through keep_alive<1, 2>."""
    scene = _painterly.Scene()
    material = scene.add_material([("diffuse", (0.5, 0.5, 0.5), 0.0)])
    scene.add_plane((0.0, 0.0, 1.0), 5.0, material)
    scene.set_background((0.25, 0.5, 0.75))
    scene.set_camera_smallpaint(4, 4)
    session = _painterly.Session(scene, 1)
    del scene
    # The Session still holds the PainterlyScene the Python Scene owned.
    session.start(2)
    assert session.wait() is True
    assert session.progress()["state"] == "done"


def test_buffers_are_fresh_numpy_copies() -> None:
    """combined(), k_consumed() and object_id() have the pyi's dtype and shape, and never alias."""
    scene = _painterly.Scene()
    material = scene.add_material([("diffuse", (0.5, 0.5, 0.5), 0.0)])
    scene.add_plane((0.0, 0.0, 1.0), 5.0, material)
    scene.set_background((0.25, 0.5, 0.75))
    scene.set_camera_smallpaint(5, 3)
    session = _painterly.Session(scene, 1)
    session.start(3, 2)
    assert session.wait() is True

    combined = session.combined()
    assert combined.dtype == np.float64
    assert combined.shape == (3, 5, 3)
    k_consumed = session.k_consumed()
    assert k_consumed.dtype == np.uint64
    assert k_consumed.shape == (3, 5)
    object_id = session.object_id()
    assert object_id.dtype == np.int32
    assert object_id.shape == (3, 5)
    # The plane is the only object, so every pixel's unjittered primary hit is its object_id 0.
    assert np.all(object_id == 0)
    assert np.all(k_consumed == 3)

    # A copy: writing to it does not change what the next call returns.
    before = combined.copy()
    combined[:] = -1.0
    assert np.array_equal(session.combined(), before)


def test_progress_reports_the_pyi_keys() -> None:
    """progress() has the pyi's five keys and the D13 state strings."""
    scene = _painterly.Scene()
    material = scene.add_material([("diffuse", (0.5, 0.5, 0.5), 0.0)])
    scene.add_plane((0.0, 0.0, 1.0), 5.0, material)
    scene.set_camera_smallpaint(2, 2)
    session = _painterly.Session(scene, 1)
    idle = session.progress()
    assert set(idle) == {"state", "passes_done", "passes_total", "elapsed", "error"}
    assert idle["state"] == "idle"
    assert idle["passes_total"] == 0
    assert idle["error"] == ""
    session.start(4, 2)
    assert session.wait() is True
    done = session.progress()
    assert done["state"] == "done"
    assert done["passes_done"] == 4
    assert done["passes_total"] == 4
    assert done["elapsed"] >= 0.0


def test_a_cancelled_session_reports_cancelled_with_its_last_batch() -> None:
    """cancel() ends the render as 'cancelled' and the buffers hold the last finished batch."""
    scene = _painterly.Scene()
    material = scene.add_material([("diffuse", (0.5, 0.5, 0.5), 0.0)])
    scene.add_plane((0.0, 0.0, 1.0), 5.0, material)
    scene.set_background((0.25, 0.5, 0.75))
    scene.set_camera_smallpaint(4, 4)
    session = _painterly.Session(scene, 1)
    # Before the first start() the published buffers are empty and the state is 'idle'.
    assert session.combined().shape == (0, 0, 3)
    assert session.k_consumed().shape == (0, 0)
    assert session.object_id().shape == (0, 0)
    session.start(100000, 1)
    session.cancel()
    assert session.wait() is True
    report = session.progress()
    assert report["state"] == "cancelled"
    assert report["error"] == ""
    assert report["elapsed"] >= 0.0
    # Whatever the last finished batch was, the three buffers agree with it.
    combined = session.combined()
    assert combined.shape == (4, 4, 3)
    assert session.k_consumed().shape == (4, 4)
    assert np.all(session.k_consumed() == report["passes_done"])
    if report["passes_done"] == 0:
        # No batch was published before the cancel: the buffers are still the reset state, whose
        # object ids are the pyi's miss value -1 (painterly/kernel/integrator/path.h).
        assert np.all(session.object_id() == -1)
    else:
        # The plane is the only object and covers the image, so every pixel hit it.
        assert np.all(session.object_id() == 0)


# --------------------------------------------------------------------------------------------------
# The GIL: Session.start and Session.wait release it (T3.15, and the two mutation gaps of the audit)
# --------------------------------------------------------------------------------------------------
#
# The measurement is one Python thread that counts how many times it observes a flag set by the main
# thread. While the main thread holds the GIL, that thread cannot run; while it is released, the
# thread runs at the interpreter's own speed.
#
# The threshold is derived, never chosen. The counter is calibrated in a window of GIL_FREE_SECONDS
# during which the main thread only sleeps (`time.sleep` releases the GIL), which gives `calibrated`
# bumps. With the GIL held for a whole C++ call, the counter thread can only run in the hand-offs at
# the call's entry and at its exit, and at most one `sys.getswitchinterval()` of work per hand-off
# (CPython switches threads at that interval). The bound is therefore
#
#     GIL_HELD_HANDOFFS * (calibrated / GIL_FREE_SECONDS) * sys.getswitchinterval()
#
# bumps, a quantity of the measurement itself: no number here is tuned to the machine.

GIL_FREE_SECONDS = 0.5
# Two hand-offs: one when the call starts, one when it returns and the main thread next switches.
GIL_HELD_HANDOFFS = 2


class _BumpCounter:
    """A daemon thread that counts the times it observes `flag`, for the GIL measurements."""

    def __init__(self) -> None:
        self.flag = False
        self.bumps = 0
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop:
            if self.flag:
                self.bumps += 1

    def measure(self, operation) -> tuple[float, int]:
        """Runs `operation` with the flag set and returns its seconds and the bumps it allowed."""
        self.bumps = 0
        self.flag = True
        try:
            start = time.perf_counter()
            operation()
            elapsed = time.perf_counter() - start
        finally:
            self.flag = False
        return elapsed, self.bumps

    def close(self) -> None:
        self._stop = True
        self._thread.join()


def _gil_held_bound(calibrated: int) -> int:
    """The most bumps a GIL-held C++ call can allow, derived from the calibration (see above)."""
    rate = calibrated / GIL_FREE_SECONDS
    return int(GIL_HELD_HANDOFFS * rate * sys.getswitchinterval())


def _large_mesh_scene(n: int) -> _painterly.Scene:
    """A scene with an n x n quad grid (2 n^2 triangles), so that start()'s snapshot takes a while.

    The grid is built with numpy's own vectorized indexing, so the Python side stays short and the
    measured window is the snapshot in the core.
    """
    axis = np.arange(n + 1, dtype=np.float32)
    xs, ys = np.meshgrid(axis, axis, indexing="ij")
    vertices = np.stack([xs.ravel(), ys.ravel(), np.zeros((n + 1) ** 2, dtype=np.float32)], axis=1)
    i = np.arange(n, dtype=np.uint32)[:, None]
    j = np.arange(n, dtype=np.uint32)[None, :]
    a = (i * (n + 1) + j).ravel()
    b = a + 1
    c = a + (n + 1)
    d = c + 1
    triangles = np.empty((2 * n * n, 3), dtype=np.uint32)
    triangles[0::2] = np.stack([a, b, d], axis=1)
    triangles[1::2] = np.stack([a, d, c], axis=1)

    scene = _painterly.Scene()
    material = scene.add_material([("diffuse", (0.5, 0.5, 0.5), 0.0)])
    mesh = scene.add_mesh(vertices, triangles, np.zeros(2 * n * n, dtype=np.int32))
    scene.add_object(mesh, np.eye(3, 4, dtype=np.float32))
    scene.set_background((0.1, 0.1, 0.1))
    scene.set_camera_smallpaint(8, 8)
    del material
    return scene


def _snapshot_seconds(n: int) -> tuple[float, int, int, int]:
    """One start() of `_large_mesh_scene(n)`: its seconds, bumps, the bound, and the calibration.

    The whole measurement is here, so that `test_start_releases_the_gil` can size its mesh without
    measuring twice. The session is one thread and one pass; the wait() afterwards is outside the
    measured window, because the mesh is small enough to finish at once.
    """
    session = _painterly.Session(_large_mesh_scene(n), 1)
    counter = _BumpCounter()
    try:
        _calibration_seconds, calibrated = counter.measure(lambda: time.sleep(GIL_FREE_SECONDS))
        bound = _gil_held_bound(calibrated)
        assert bound > 0, calibrated
        elapsed, bumps = counter.measure(lambda: session.start(1, 1))
    finally:
        counter.close()
    assert session.wait() is True, session.progress()
    return elapsed, bumps, bound, calibrated


# The mesh of test_start_releases_the_gil is sized by measurement, not by a hand-picked triangle
# count (TQ.3 F23): the side of the quad grid doubles until the measured start() is long enough for
# the comparison with the bound to mean something, which is what makes the test independent of the
# machine's speed.
#
# How long is long enough: while the GIL is released the counter's running time is at least
# GIL_RELEASE_SHARE_FLOOR times the window (the queue reserves four CPUs, R10, and the render's own
# thread takes one of them), and the bound charges at most GIL_HELD_HANDOFFS switch intervals of
# running. Requiring the released window's running time to be GIL_RELEASE_MARGIN times the bound
# gives
#
#     GIL_RELEASE_MARGIN * GIL_HELD_HANDOFFS * sys.getswitchinterval() / GIL_RELEASE_SHARE_FLOOR
#
# seconds: 4 * 2 * 0.005 / 0.25 = 0.16 s with CPython's default switch interval. A shorter window
# is not evidence either way, because the counter's share of it is dominated by the hand-offs.
GIL_RELEASE_SHARE_FLOOR = 0.25
GIL_RELEASE_MARGIN = 4
#: The side of the first grid tried, 2 * 32^2 triangles: a few milliseconds, so a machine that
#: needs no growth pays almost nothing.
GIL_MESH_START_SIDE = 32
#: The most growth steps, each a doubling of the side: 2^6 * 32 = 2048 quads per side, 8 million
#: triangles, which no machine's device_update finishes inside 0.16 s.
GIL_MESH_MAX_DOUBLINGS = 6


def _gil_window_seconds() -> float:
    """The shortest window whose released running time is GIL_RELEASE_MARGIN times the bound."""
    return (
        GIL_RELEASE_MARGIN * GIL_HELD_HANDOFFS * sys.getswitchinterval() / GIL_RELEASE_SHARE_FLOOR
    )


def test_start_releases_the_gil() -> None:
    """start()'s snapshot must not hold the GIL, so other Python threads keep running.

    The scene is sized by measurement, not by a hand-picked triangle count (TQ.3 F23): a mesh whose
    start() is too short cannot show anything either way, so the side doubles until `elapsed`
    reaches `_gil_window_seconds()` (derived above), and only then are the bumps compared with the
    bound. On a fast machine the mesh grows; on a slow one it does not. The cost is at most one
    start() per step, and the last measurement is the one asserted.
    """
    hand_off_seconds = _gil_window_seconds()
    side = GIL_MESH_START_SIDE
    elapsed, bumps, bound, calibrated = _snapshot_seconds(side)
    for _step in range(GIL_MESH_MAX_DOUBLINGS):
        if elapsed >= hand_off_seconds:
            break
        side *= 2
        elapsed, bumps, bound, calibrated = _snapshot_seconds(side)
    assert elapsed >= hand_off_seconds, (side, elapsed, hand_off_seconds)
    assert bumps > bound, (side, bumps, bound, elapsed, calibrated)


def test_wait_releases_the_gil() -> None:
    """wait() must not hold the GIL for the whole render, so other Python threads keep running.

    This is the mutation gap of the T3.15 audit: with `nb::gil_scoped_release` removed from the
    `Session.wait` binding alone, the counter thread gets no window at all and this test fails.
    """
    # A 32 x 32 render of many passes, far longer than the timeout the test waits for.
    scene = _painterly.Scene()
    material = scene.add_material([("diffuse", (0.5, 0.5, 0.5), 0.0)])
    scene.add_plane((0.0, 0.0, 1.0), 5.0, material)
    scene.set_background((0.25, 0.5, 0.75))
    scene.set_camera_smallpaint(32, 32)
    session = _painterly.Session(scene, 1)
    counter = _BumpCounter()
    try:
        _calibration_seconds, calibrated = counter.measure(lambda: time.sleep(GIL_FREE_SECONDS))
        bound = _gil_held_bound(calibrated)
        assert bound > 0, calibrated

        session.start(50000, 100)
        try:
            elapsed, bumps = counter.measure(lambda: session.wait(GIL_FREE_SECONDS))
            # The render outlasts the timeout, so this wait really waited for its whole window.
            assert session.progress()["state"] == "rendering", session.progress()
            assert elapsed >= GIL_FREE_SECONDS
            assert bumps > bound, (bumps, bound, elapsed, calibrated)
        finally:
            session.cancel()
            assert session.wait() is True
    finally:
        counter.close()
