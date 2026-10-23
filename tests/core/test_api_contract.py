"""The built _painterly implements exactly the contract of src/blender/_painterly.pyi (T3.15).

Every check here reads the contract from the `.pyi` itself, so the two can never drift apart:
the public names and their parameter names come from `ast`, and so do the default values, which
are compared with the values the module reports through nanobind's `__nb_signature__`.

The GIL tests at the end are the two mutation gaps of the T3.15 audit: a threshold derived from a
calibration of the same loop, never a hand-picked number, so that removing the release from
`Session.start` or from `Session.wait` alone makes its test fail.
"""

import ast
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


def _defaults_match(pyi_default: ast.expr | None, runtime_default: object) -> bool:
    """The pyi's default expression against the value the module reports.

    `None` in the pyi is Python's None; every other default is a literal (a number, a string, or a
    tuple of numbers), which `ast.literal_eval` reads without running any code.
    """
    if pyi_default is None:
        return runtime_default is None
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
    with pytest.raises(ValueError):
        scene.set_integrator(max_depth=0)


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


def test_the_python_scene_outlives_a_deleted_reference_through_its_session() -> None:
    """Session.__init__ is bound with keep_alive<1, 2>: the Scene lives as long as the Session."""
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


def test_start_releases_the_gil() -> None:
    """start()'s snapshot must not hold the GIL, so other Python threads keep running."""
    # 500 x 500 quads: 500 000 triangles, whose device_update takes a few hundred milliseconds.
    scene = _large_mesh_scene(500)
    session = _painterly.Session(scene, 1)
    counter = _BumpCounter()
    try:
        _calibration_seconds, calibrated = counter.measure(lambda: time.sleep(GIL_FREE_SECONDS))
        bound = _gil_held_bound(calibrated)
        assert bound > 0, calibrated

        elapsed, bumps = counter.measure(lambda: session.start(1, 1))
        session.wait()
        assert elapsed > 0.0
        assert bumps > bound, (bumps, bound, elapsed, calibrated)
    finally:
        counter.close()


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
