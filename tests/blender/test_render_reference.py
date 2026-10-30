"""The render loop end to end: the PAINTERLY engine's Render Result equals SPEC §8 (T4.3).

The engine renders SPEC §9 in reference mode (``reference_scene = True``), and the Render Result is
read back through a float32 OpenEXR file. The pixels must be exactly SPEC §8's mapping of a direct
``_painterly`` render of the same configuration (``core_sum``): it is the same core, so the two are
bit-identical. The EXR stores float32, which is exact, so there is no tolerance anywhere.

The expectation is built here, from SPEC §8's own formula and IEC 61966-2-1's own numbers, and
never through :mod:`painterly.film`: a defect in ``film.py`` must fail these tests. Four cases run
end to end, one for each branch the render loop takes:

- ``scene_linear`` at 100 % and frame 1 (the card's step 1);
- ``display_referred``, the other output mode (``session._write_result``'s else branch);
- a ``resolution_percentage`` below 100, which halves the image (``session.resolution``);
- ``seed_per_frame`` at a non-zero frame (``session.integrator_knobs``).

Row order is SPEC §0's: our row 0 is the top row and Blender's buffer row 0 is the bottom row, so
the expectation is reversed by hand.

Two further tests cover the two other paths of the render loop: a non-square image in reference
mode, which it reports an error for, and the Blender-scene sync, whose core scene it builds
through ``sync_camera``. Three more drive the poll loop's own decisions (a write skipped when the
pass count moves between the loop's two reads, a break that cancels the session, an error state
that becomes a report) with a scripted stand-in for the session, because a real render finishes
too quickly to force them.

The scene settings are restored after each test, because the ``addon`` fixture registers the
add-on once per session and every test shares ``bpy.context.scene``.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType, SimpleNamespace

import _painterly
import bpy
import numpy as np
import painterly.sync.reference as reference
import pytest

from painterly import sync

# The render of the card's step 1: a 48 px square image of SPEC §9, the lane chain with lanes of
# 16 px, 2 passes and the scene_linear output mode at exposure 1. 48 px is the parity tests' fast
# size (tests/core/test_oracle_parity.py), and 2 passes is enough for a non-zero sum in every pixel
# while keeping the test well under a second.
SIZE = 48
PASSES = 2
LANE_LENGTH = 16
EXPOSURE = 1.0

# SPEC §8's byte scale: ``L/255``, where L is the mean radiance over the completed passes and the
# core's ``combined()`` returns their sum.
BYTE_MAX = 255.0

# The sRGB EOTF of IEC 61966-2-1:1999 (§5.2 and Annex A), as the standard gives it. The
# expectation of the display_referred case is computed from these literals, not from ``film.py``.
SRGB_JUNCTION = 0.04045
SRGB_LINEAR_SLOPE = 12.92
SRGB_OFFSET = 0.055
SRGB_SCALE = 1.055
SRGB_EXPONENT = 2.4

# The two frames of the seed_per_frame case: SPEC §8 adds the frame number to ``seed`` when
# ``seed_per_frame`` is on, so the frame-7 render is the core's seed+7 render, not its seed render.
SEED = 3
FRAME = 7

# The resolution_percentage of the reduced case: 50 % of SIZE is 24 px, and Blender's own integer
# division of BKE_render_resolution gives the same 24.
PERCENTAGE = 50
REDUCED_SIZE = SIZE * PERCENTAGE // 100

# Blender 5.2's float32 OpenEXR setting. The card's `use_exr_half = False` was the 2.x name of this
# setting; 5.2 expresses it as the color depth, "32" being float32 and "16" half (R2: the current
# equivalent, named here).
EXR_COLOR_DEPTH = "32"

# The two error reports of the render loop, as the exceptions Blender raises from
# `bpy.ops.render.render()` when the engine reports them.
REFERENCE_NOT_SQUARE = "the reference scene needs a square image"


def _core_sum(size: int = SIZE, seed: int = 0) -> np.ndarray:
    """The (H, W, 3) radiance sums of a direct ``_painterly`` render of the same configuration.

    The scene is SPEC §9 with the reference knobs, as the render loop builds it in reference mode,
    and the two knobs of the card's step 1: the lane chain and 16-px lanes. ``size`` is the image
    side and ``seed`` the core's seed socket. The session runs with one thread and batch 1; SPEC §3
    makes the output bit-identical for any thread count and batch.
    """
    scene = _painterly.Scene()
    reference.build_smallpaint_scene(scene, size=size)
    scene.set_integrator(chain="lane", lane_length=LANE_LENGTH, seed=seed)

    session = _painterly.Session(scene, 1)
    session.start(PASSES, 1)
    assert session.wait() is True, "the core's render did not finish"
    return session.combined()


def _srgb_to_linear(values: np.ndarray) -> np.ndarray:
    """The sRGB EOTF of IEC 61966-2-1, written from the literals above, in float64."""
    return np.where(
        values <= SRGB_JUNCTION,
        values / SRGB_LINEAR_SLOPE,
        ((values + SRGB_OFFSET) / SRGB_SCALE) ** SRGB_EXPONENT,
    )


def _display_referred_expectation(sum_rgb: np.ndarray) -> np.ndarray:
    """SPEC §8's display_referred pass: ``srgb_to_linear(min(L/255, 1))``, float32, alpha 1."""
    mean = np.minimum(sum_rgb / PASSES / BYTE_MAX, 1.0)
    rgba = np.ones((*mean.shape[:2], 4), dtype=np.float32)
    rgba[..., :3] = _srgb_to_linear(mean)
    return rgba


def _scene_linear_expectation(sum_rgb: np.ndarray, exposure: float) -> np.ndarray:
    """SPEC §8's scene_linear pass: ``L/255 · exposure``, float32, alpha 1."""
    rgba = np.ones((*sum_rgb.shape[:2], 4), dtype=np.float32)
    rgba[..., :3] = sum_rgb / PASSES / BYTE_MAX * exposure
    return rgba


def _blender_rows(rgba: np.ndarray) -> np.ndarray:
    """SPEC §0's row flip, by hand: our row 0 is the top, Blender's buffer row 0 is the bottom."""
    return np.ascontiguousarray(rgba[::-1])


@pytest.fixture()
def scene_settings() -> dict[str, object]:
    """Set the add-on's render settings for these tests, and restore them afterwards.

    Returns:
        The saved values, keyed by attribute name, so that a test may change one of them.
    """
    scene = bpy.context.scene
    render = scene.render
    settings = scene.painterly
    saved = {
        "engine": render.engine,
        "resolution_x": render.resolution_x,
        "resolution_y": render.resolution_y,
        "resolution_percentage": render.resolution_percentage,
        "file_format": render.image_settings.file_format,
        "color_depth": render.image_settings.color_depth,
        "color_mode": render.image_settings.color_mode,
        "reference_scene": settings.reference_scene,
        "chain": settings.chain,
        "lane_length": settings.lane_length,
        "passes": settings.passes,
        "output_mode": settings.output_mode,
        "exposure": settings.exposure,
        "seed": settings.seed,
        "seed_per_frame": settings.seed_per_frame,
        "frame_current": scene.frame_current,
    }
    try:
        render.engine = "PAINTERLY"
        settings.reference_scene = True
        settings.chain = "lane"
        settings.lane_length = LANE_LENGTH
        settings.passes = PASSES
        settings.output_mode = "scene_linear"
        settings.exposure = EXPOSURE
        settings.seed = 0
        settings.seed_per_frame = False
        scene.frame_set(1)
        render.resolution_x = SIZE
        render.resolution_y = SIZE
        render.resolution_percentage = 100
        # A float32 OpenEXR is what makes the read-back exact; the file is written below.
        render.image_settings.file_format = "OPEN_EXR"
        render.image_settings.color_depth = EXR_COLOR_DEPTH
        render.image_settings.color_mode = "RGBA"
        yield saved
    finally:
        render.engine = saved["engine"]
        render.resolution_x = saved["resolution_x"]
        render.resolution_y = saved["resolution_y"]
        render.resolution_percentage = saved["resolution_percentage"]
        render.image_settings.file_format = saved["file_format"]
        render.image_settings.color_depth = saved["color_depth"]
        render.image_settings.color_mode = saved["color_mode"]
        settings.reference_scene = saved["reference_scene"]
        settings.chain = saved["chain"]
        settings.lane_length = saved["lane_length"]
        settings.passes = saved["passes"]
        settings.output_mode = saved["output_mode"]
        settings.exposure = saved["exposure"]
        settings.seed = saved["seed"]
        settings.seed_per_frame = saved["seed_per_frame"]
        scene.frame_set(saved["frame_current"])


def _render_result_pixels(tmp_path: Path, scene) -> np.ndarray:
    """Render, then read the Render Result back as a (H, W, 4) float32 array, bottom row first.

    Blender's ``Render Result`` exposes no pixel buffer to Python, so it is saved as a float32
    OpenEXR and loaded again. The file stores float32, so the round trip is exact.
    """
    bpy.ops.render.render()
    result_path = tmp_path / "render-result.exr"
    bpy.data.images["Render Result"].save_render(str(result_path), scene=scene)
    image = bpy.data.images.load(str(result_path))
    try:
        pixels = np.empty(image.size[0] * image.size[1] * image.channels, dtype=np.float32)
        image.pixels.foreach_get(pixels)
        return pixels.reshape(image.size[1], image.size[0], image.channels)
    finally:
        bpy.data.images.remove(image)


def _assert_is_the_expectation(rendered: np.ndarray, expected: np.ndarray, size: int) -> None:
    """Check the Render Result against a hand-built SPEC §8 expectation, bit for bit."""
    assert rendered.shape == (size, size, 4)
    assert rendered.dtype == np.float32
    # Exact equality: the same core rendered both sides, and the EXR round trip stores float32
    # unchanged. A difference of one ulp is a defect, not a rounding to allow for.
    assert np.array_equal(rendered, expected)


def test_the_render_result_is_scene_linear_of_the_core_sums(
    tmp_path: Path, scene_settings: dict[str, object], addon: ModuleType
) -> None:
    """The card's step 1: scene_linear at exposure 1, against SPEC §8 built by hand."""
    rendered = _render_result_pixels(tmp_path, bpy.context.scene)
    expected = _blender_rows(_scene_linear_expectation(_core_sum(), EXPOSURE))

    _assert_is_the_expectation(rendered, expected, SIZE)


def test_the_render_result_is_display_referred_of_the_core_sums(
    tmp_path: Path, scene_settings: dict[str, object], addon: ModuleType
) -> None:
    """The display_referred branch: ``srgb_to_linear(min(L/255, 1))``, SPEC §8's default mode."""
    bpy.context.scene.painterly.output_mode = "display_referred"

    rendered = _render_result_pixels(tmp_path, bpy.context.scene)
    expected = _blender_rows(_display_referred_expectation(_core_sum()))

    # The mode must be visible in the pixels: the transfer function is not the identity here.
    scene_linear = _blender_rows(_scene_linear_expectation(_core_sum(), EXPOSURE))
    assert not np.array_equal(expected, scene_linear)
    _assert_is_the_expectation(rendered, expected, SIZE)


def test_a_resolution_percentage_below_100_renders_that_smaller_image(
    tmp_path: Path, scene_settings: dict[str, object], addon: ModuleType
) -> None:
    """``session.resolution``: 50 % of 48 px is the 24 px render, and nothing else changes."""
    bpy.context.scene.render.resolution_percentage = PERCENTAGE

    rendered = _render_result_pixels(tmp_path, bpy.context.scene)
    expected = _blender_rows(_scene_linear_expectation(_core_sum(size=REDUCED_SIZE), EXPOSURE))

    _assert_is_the_expectation(rendered, expected, REDUCED_SIZE)


def test_seed_per_frame_at_a_non_zero_frame_renders_the_seed_plus_the_frame(
    tmp_path: Path, scene_settings: dict[str, object], addon: ModuleType
) -> None:
    """SPEC §8: ``seed_per_frame`` adds the frame number to ``seed`` before the core render."""
    scene = bpy.context.scene
    scene.painterly.seed = SEED
    scene.painterly.seed_per_frame = True
    scene.frame_set(FRAME)

    rendered = _render_result_pixels(tmp_path, scene)
    expected = _blender_rows(_scene_linear_expectation(_core_sum(seed=SEED + FRAME), EXPOSURE))

    # The case is only meaningful if the seed moves the pixels: the frame's seed and the
    # configured seed render differently, so an ignored seed_per_frame fails above.
    assert not np.array_equal(_core_sum(seed=SEED), _core_sum(seed=SEED + FRAME))
    _assert_is_the_expectation(rendered, expected, SIZE)


def test_a_non_square_reference_render_reports_an_error(
    scene_settings: dict[str, object], addon: ModuleType
) -> None:
    """Step 2: reference mode requires a square image, and says so instead of rendering."""
    scene = bpy.context.scene
    scene.render.resolution_y = SIZE // 2

    with pytest.raises(RuntimeError, match=REFERENCE_NOT_SQUARE):
        bpy.ops.render.render()


def test_the_blender_scene_path_builds_the_core_scene_through_sync_camera(
    scene_settings: dict[str, object], addon: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Step 2: the Blender-scene path syncs the camera instead of reporting the M5 stub.

    ``sync_camera`` is wrapped so that the core scene and the depsgraph it receives are visible
    here, and the render then runs for real: the camera of the Blender scene must reach the core
    scene, and the render must finish instead of reporting an error. The depsgraph is only valid
    during the render, so the wrapper records what it reads from it there and the test compares
    that record afterwards.
    """
    scene = bpy.context.scene
    scene.painterly.reference_scene = False
    sync_camera = sync.sync_camera
    recorded: list[tuple[object, bool, int, int]] = []

    def recording_sync_camera(scene_core, depsgraph, settings, width, height) -> None:
        recorded.append((scene_core, depsgraph.scene is scene, width, height))
        sync_camera(scene_core, depsgraph, settings, width, height)

    monkeypatch.setattr(sync, "sync_camera", recording_sync_camera)

    # A render that reaches the stub would raise RuntimeError with the stub's message; the render
    # loop reports an engine error as an exception, so a plain call is the check that it is gone.
    bpy.ops.render.render()

    assert len(recorded) == 1
    core_scene, same_scene, width, height = recorded[0]
    assert isinstance(core_scene, _painterly.Scene)
    assert same_scene
    assert (width, height) == (SIZE, SIZE)


# --- Steps 6-8: the poll loop, with a stand-in session and engine -----------------------------
#
# The real render finishes its passes too quickly to force the loop's two races (a batch that
# finishes between the two ``progress`` reads, a cancel, an error), so these tests drive
# ``session.render`` with a scripted stand-in for ``_painterly.Session``. The film mapping and the
# real session are covered by the tests above; here only the loop's own decisions are.


class _Rect:
    """The ``Combined`` pass's ``rect``: it records what ``foreach_set`` was given."""

    def __init__(self) -> None:
        self.written: list[np.ndarray] = []

    def foreach_set(self, values: np.ndarray) -> None:
        self.written.append(np.array(values, dtype=np.float32))


class _Result:
    """A render result whose one layer holds the one ``Combined`` pass."""

    def __init__(self) -> None:
        self.rect = _Rect()
        combined = session_module().COMBINED_PASS
        self.layers = [SimpleNamespace(passes={combined: SimpleNamespace(rect=self.rect)})]


def session_module():
    """The add-on's ``session`` module, imported as ``painterly.session`` by the package."""
    import painterly.session as module

    return module


class _FakeEngine:
    """A ``RenderEngine`` stand-in: records every callback, answers ``test_break`` from a script.

    Attributes:
        reports: every ``(type, message)`` of ``report``.
        stats: every ``info`` string of ``update_stats``.
        progress_values: every ``progress`` value of ``update_progress``.
        session: the ``Session`` the loop attached to it.
    """

    def __init__(self, breaks: list[bool] | None = None) -> None:
        self.breaks = list(breaks or [])
        self.reports: list[tuple[set[str], str]] = []
        self.stats: list[str] = []
        self.progress_values: list[float] = []
        self.ended: list[bool] = []
        self.session = None
        self.result = _Result()

    def report(self, types: set[str], message: str) -> None:
        self.reports.append((types, message))

    def begin_result(self, x, y, w, h, layer: str = "") -> _Result:
        self.result_size = (w, h)
        return self.result

    def update_result(self, result: _Result) -> None:
        self.updated = True

    def update_progress(self, value: float) -> None:
        self.progress_values.append(value)

    def update_stats(self, stats: str, info: str) -> None:
        self.stats.append(info)

    def test_break(self, do_break: bool = False) -> bool:
        return self.breaks.pop(0) if self.breaks else False

    def end_result(self, result: _Result, cancel: bool = False, **kwargs) -> None:
        self.ended.append(cancel)


class _FakeSession:
    """A ``Session`` stand-in: its ``progress`` and ``wait`` follow a script.

    Each ``progress()`` call pops the next entry of ``reports`` and repeats the last one once the
    script is exhausted, so one poll of the loop (state, p0, p1) reads three entries. ``wait``
    likewise pops ``finishes``.

    Attributes:
        timeouts: every ``timeout`` of ``wait``.
        cancelled: whether ``cancel()`` was called.
    """

    def __init__(
        self,
        reports: list[dict[str, object]],
        sums: np.ndarray,
        finishes: list[bool] | None = None,
    ) -> None:
        self.reports = list(reports)
        self.finishes = list(finishes or [True])
        self.sums = sums
        self.timeouts: list[float] = []
        self.cancelled = False
        self.started: tuple[int, int] | None = None

    def start(self, passes: int, batch: int) -> None:
        self.started = (passes, batch)

    def wait(self, timeout: float | None = None) -> bool:
        self.timeouts.append(timeout)
        return self.finishes.pop(0) if len(self.finishes) > 1 else self.finishes[0]

    def cancel(self) -> None:
        self.cancelled = True

    def progress(self) -> dict[str, object]:
        entry = self.reports.pop(0) if len(self.reports) > 1 else self.reports[0]
        return dict(entry)

    def combined(self) -> np.ndarray:
        return self.sums


def _progress(state: str, passes_done: int, error: str = "") -> dict[str, object]:
    """One ``progress()`` report, in the pyi's shape."""
    return {
        "state": state,
        "passes_done": passes_done,
        "passes_total": PASSES,
        "elapsed": 0.0,
        "error": error,
    }


class _FakeScene:
    """A core ``Scene`` stand-in that records its integrator knobs."""

    def __init__(self) -> None:
        self.knobs: dict[str, object] = {}

    def set_integrator(self, **knobs: object) -> None:
        self.knobs.update(knobs)


def _fake_painterly(fake_session: _FakeSession, core_scene: _FakeScene):
    """A stand-in for the ``_painterly`` module, with the three names ``session.render`` uses."""
    sockets = [
        {"name": "passes", "type": "int"},
        {"name": "seed", "type": "uint"},
        {"name": "seed_per_frame", "type": "boolean"},
        {"name": "spiral_rotation", "type": "vector"},
    ]

    class _Module:
        @staticmethod
        def integrator_sockets() -> list[dict[str, object]]:
            return sockets

        @staticmethod
        def Scene() -> _FakeScene:
            return core_scene

        @staticmethod
        def Session(scene: _FakeScene, threads: int) -> _FakeSession:
            return fake_session

    return _Module


@pytest.fixture()
def fake_loop(monkeypatch: pytest.MonkeyPatch, scene_settings: dict[str, object]):
    """``session.render`` wired to stand-ins, with the Blender scene as its settings source.

    Returns:
        A function ``(reports, sums, breaks, finishes) -> (engine, session)`` that runs the loop.
    """

    def run(
        reports: list[dict[str, object]],
        sums: np.ndarray,
        breaks: list[bool] | None = None,
        finishes: list[bool] | None = None,
    ):
        module = session_module()
        fake_session = _FakeSession(reports, sums, finishes)
        core_scene = _FakeScene()
        monkeypatch.setattr(module, "_painterly", _fake_painterly(fake_session, core_scene))
        monkeypatch.setattr(module.sync, "build_scene", lambda *args: core_scene)

        engine = _FakeEngine(breaks)
        scene = bpy.context.scene
        scene.painterly.reference_scene = False

        class _ViewLayer:
            name = "ViewLayer"

        class _Depsgraph:
            pass

        depsgraph = _Depsgraph()
        depsgraph.scene = scene
        depsgraph.view_layer = _ViewLayer()

        module.render(engine, depsgraph)
        return engine, fake_session

    return run


def test_a_write_is_skipped_when_the_pass_count_moves_between_the_two_reads(fake_loop) -> None:
    """Step 6: ``p0 != p1`` skips the write, and the next poll writes the newer passes."""
    sums = np.ones((SIZE, SIZE, 3), dtype=np.float64)
    reports = [
        # Poll 1: passes_done moves from 1 to 2 between the two reads, so nothing is written.
        _progress("rendering", 1),
        _progress("rendering", 1),
        _progress("rendering", 2),
        # Poll 2: the render is done, and both reads agree on 2.
        _progress("done", 2),
        _progress("done", 2),
        _progress("done", 2),
        # The final write reads the same 2.
        _progress("done", 2),
    ]
    engine, fake_session = fake_loop(reports, sums, finishes=[False, True])

    # The skipped poll wrote no stats; the second poll reported pass 2 of 2.
    assert engine.stats == [f"Pass {PASSES}/{PASSES}"]
    assert engine.progress_values == [1.0]
    # One write in the loop and one final write, both of the completed passes.
    assert len(engine.result.rect.written) == 2
    assert engine.ended == [False]
    poll_seconds = session_module().POLL_SECONDS
    assert fake_session.timeouts == [poll_seconds, poll_seconds]


def test_an_error_state_becomes_an_error_report(fake_loop) -> None:
    """Step 8: the session's error message is reported and the result is ended."""
    sums = np.zeros((SIZE, SIZE, 3), dtype=np.float64)
    engine, _ = fake_loop([_progress("error", 0, error="the device scene is invalid")], sums)

    assert engine.reports == [({"ERROR"}, "Painterly: the device scene is invalid")]
    assert engine.ended == [False]
    assert engine.result.rect.written == []


def test_a_break_cancels_the_session(fake_loop) -> None:
    """Step 6: ``test_break()`` cancels the session; no finished pass means no write."""
    sums = np.zeros((SIZE, SIZE, 3), dtype=np.float64)
    engine, fake_session = fake_loop([_progress("rendering", 0)], sums, breaks=[True])

    assert fake_session.cancelled
    assert engine.result.rect.written == []
    assert engine.ended == [False]
