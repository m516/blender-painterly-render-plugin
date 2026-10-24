"""The render loop end to end: the PAINTERLY engine's Render Result equals the core's film (T4.3).

The engine renders SPEC §9 in reference mode (``reference_scene = True``) with the ``scene_linear``
output mode, and the Render Result is read back through a float32 OpenEXR file. The pixels must be
exactly ``film.to_blender_rows(film.scene_linear(core_sum, passes, exposure))``, where ``core_sum``
is a direct ``_painterly`` render of the same configuration: it is the same core, so the two are
bit-identical. The EXR stores float32, which is exact, so there is no tolerance anywhere.

Two further tests cover the two paths on which the render loop reports an error instead of
rendering: a non-square image in reference mode, and the Blender-scene sync, which is the M5 stub.
Three more drive the poll loop's own decisions (a write skipped when the pass count moves between
the loop's two reads, a break that cancels the session, an error state that becomes a report) with
a scripted stand-in for the session, because a real render finishes too quickly to force them.

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

from painterly import film, sync

# The render of the card's step 1: a 48 px square image of SPEC §9, the lane chain with lanes of
# 16 px, 2 passes and the scene_linear output mode at exposure 1. 48 px is the parity tests' fast
# size (tests/core/test_oracle_parity.py), and 2 passes is enough for a non-zero sum in every pixel
# while keeping the test well under a second.
SIZE = 48
PASSES = 2
LANE_LENGTH = 16
EXPOSURE = 1.0

# Blender 5.2's float32 OpenEXR setting. The card's `use_exr_half = False` was the 2.x name of this
# setting; 5.2 expresses it as the color depth, "32" being float32 and "16" half (R2: the current
# equivalent, named here).
EXR_COLOR_DEPTH = "32"

# The two error reports of the render loop, as the exceptions Blender raises from
# `bpy.ops.render.render()` when the engine reports them.
REFERENCE_NOT_SQUARE = "the reference scene needs a square image"


def _core_sum() -> np.ndarray:
    """The (H, W, 3) radiance sums of a direct ``_painterly`` render of the same configuration.

    The scene is SPEC §9 with the reference knobs, as the render loop builds it in reference mode,
    and the two knobs of the card's step 1: the lane chain and 16-px lanes. The session runs with
    one thread and batch 1; SPEC §3 makes the output bit-identical for any thread count and batch.
    """
    scene = _painterly.Scene()
    reference.build_smallpaint_scene(scene, size=SIZE)
    scene.set_integrator(chain="lane", lane_length=LANE_LENGTH)

    session = _painterly.Session(scene, 1)
    session.start(PASSES, 1)
    assert session.wait() is True, "the core's render did not finish"
    return session.combined()


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
    }
    try:
        render.engine = "PAINTERLY"
        settings.reference_scene = True
        settings.chain = "lane"
        settings.lane_length = LANE_LENGTH
        settings.passes = PASSES
        settings.output_mode = "scene_linear"
        settings.exposure = EXPOSURE
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


def test_the_render_result_is_the_core_film_bit_for_bit(
    tmp_path: Path, scene_settings: dict[str, object], addon: ModuleType
) -> None:
    """The engine's Render Result equals ``to_blender_rows(scene_linear(core_sum, 2, 1))``."""
    rendered = _render_result_pixels(tmp_path, bpy.context.scene)
    expected = film.to_blender_rows(film.scene_linear(_core_sum(), PASSES, EXPOSURE))

    assert rendered.shape == (SIZE, SIZE, 4)
    assert rendered.dtype == np.float32
    # Exact equality: the same core rendered both sides, and the EXR round trip stores float32
    # unchanged. A difference of one ulp is a defect, not a rounding to allow for.
    assert np.array_equal(rendered, expected)


def test_a_non_square_reference_render_reports_an_error(
    scene_settings: dict[str, object], addon: ModuleType
) -> None:
    """Step 2: reference mode requires a square image, and says so instead of rendering."""
    scene = bpy.context.scene
    scene.render.resolution_y = SIZE // 2

    with pytest.raises(RuntimeError, match=REFERENCE_NOT_SQUARE):
        bpy.ops.render.render()


def test_the_blender_scene_path_reports_the_m5_stub(
    scene_settings: dict[str, object], addon: ModuleType
) -> None:
    """Step 2: the Blender-scene sync's NotImplementedError becomes an ``engine.report``."""
    scene = bpy.context.scene
    scene.painterly.reference_scene = False

    with pytest.raises(RuntimeError, match="Blender scene sync arrives in M5"):
        bpy.ops.render.render()

    # The message is the stub's own, so the two cannot drift apart.
    with pytest.raises(NotImplementedError, match="Blender scene sync arrives in M5"):
        sync.build_scene(None, None, SIZE, SIZE)


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
