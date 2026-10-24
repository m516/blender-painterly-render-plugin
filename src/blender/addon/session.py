# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The render loop: session ↔ RenderResult (T4.3).

Mirrors Cycles' ``intern/cycles/blender/sync.py`` render entry point: one call builds the core
scene, sets the integrator knobs, starts a :class:`_painterly.Session`, and polls it while
writing the accumulated film into Blender's ``Combined`` render pass. ``engine.render`` forwards
here, so this module is the only place that knows the RenderEngine callbacks.

The loop never copies a pixel list: it maps the session's radiance sums with :mod:`film` and
writes the float32 array with ``rect.foreach_set``, which is Blender's memcpy path.

Reference mode renders SPEC §9 (:mod:`sync.reference`) instead of the Blender scene, which the
Blender-scene sync (:mod:`sync`) builds from M5 on.
"""

from __future__ import annotations

import _painterly
import numpy as np

from . import film, sync
from .sync import reference

# The poll timeout of the render loop, in seconds. It is the UI's responsiveness: Blender can only
# notice a cancel request (``engine.test_break()``) and redraw the Render Result between two
# waits, so a longer timeout would make an Esc take that long to react. It costs nothing when the
# render is fast: ``wait`` returns as soon as the session leaves the rendering state.
POLL_SECONDS = 0.1

# The layer and pass names Blender gives the engine's one result. ``begin_result`` with the view
# layer's name creates a layer of that name, and every render engine has the Combined pass.
COMBINED_PASS = "Combined"


def resolution(scene) -> tuple[int, int]:
    """The image size of ``scene`` in pixels.

    Args:
        scene: the Blender scene being rendered.

    Returns:
        ``(width, height)`` in pixels, from ``resolution_x``/``resolution_y`` times
        ``resolution_percentage`` over 100. The division is Blender's own: ``BKE_render_resolution``
        divides integers, so 7 px at 50 % is 3 px, not 4. ``engine.resolution_x``/``_y`` report the
        same values.
    """
    render = scene.render
    return (
        render.resolution_x * render.resolution_percentage // 100,
        render.resolution_y * render.resolution_percentage // 100,
    )


def integrator_knobs(settings, scene) -> dict[str, object]:
    """The integrator knobs of ``settings``, by socket name.

    Args:
        settings: ``scene.painterly``, the add-on's render settings.
        scene: the Blender scene, for its frame number when ``seed_per_frame`` is on.

    Returns:
        One entry per ``PainterlyIntegrator`` socket, read from the generated property of that
        name. A vector socket becomes a tuple, because ``set_integrator`` takes a 3-sequence and a
        ``FloatVectorProperty`` is not one (T3.15). SPEC §8: with ``seed_per_frame`` on, the
        add-on adds the frame number to ``seed``; the socket ``seed_per_frame`` itself is only a
        record of that choice, the core does not add anything.
    """
    knobs: dict[str, object] = {}
    for socket in _painterly.integrator_sockets():
        value = getattr(settings, socket["name"])
        knobs[socket["name"]] = tuple(value) if socket["type"] == "vector" else value
    if settings.seed_per_frame:
        knobs["seed"] = int(settings.seed) + int(scene.frame_current)
    return knobs


def _set_integrator(core_scene, settings, scene, *, reference_mode: bool) -> None:
    """Set every integrator socket of ``core_scene`` from ``settings``.

    The user's values go first; in reference mode :func:`sync.reference.apply_reference_knobs`
    overwrites the smallpaint-unit ones afterwards, so a reference render is the reference look
    whatever the user set. Every other knob keeps the user's value (SPEC §9).
    """
    knobs = integrator_knobs(settings, scene)
    if reference_mode:
        knobs.update(reference.apply_reference_knobs())
    core_scene.set_integrator(**knobs)


def _write_result(engine, result, settings, sums, passes_done: int) -> None:
    """Map ``sums`` to the Combined pass and hand the result to Blender.

    Args:
        engine: the ``bpy.types.RenderEngine`` instance.
        result: the render result of ``engine.begin_result``.
        settings: ``scene.painterly``, for the output mode and the exposure.
        sums: the (H, W, 3) float64 radiance sums of ``Session.combined()``.
        passes_done: the number of passes ``sums`` covers, at least 1.
    """
    if settings.output_mode == "scene_linear":
        rgba = film.scene_linear(sums, passes_done, settings.exposure)
    else:
        rgba = film.display_referred(sums, passes_done)
    rect = result.layers[0].passes[COMBINED_PASS].rect
    rect.foreach_set(np.ascontiguousarray(film.to_blender_rows(rgba), np.float32).ravel())
    engine.update_result(result)


def render(engine, depsgraph) -> None:
    """Render one frame into a Render Result.

    Args:
        engine: the ``bpy.types.RenderEngine`` instance that asked for the render.
        depsgraph: Blender's dependency graph of the frame being rendered.
    """
    scene = depsgraph.scene
    settings = scene.painterly
    width, height = resolution(scene)

    # The core scene: SPEC §9 in reference mode, the Blender scene otherwise (M5).
    if settings.reference_scene:
        if width != height:
            # SPEC §7: the smallpaint camera's GUI quirk (w scales the row term) is harmless only
            # for a square image, and build_smallpaint_scene takes one size.
            engine.report(
                {"ERROR"},
                f"Painterly: the reference scene needs a square image, but the render is "
                f"{width}x{height} px",
            )
            return
        core_scene = _painterly.Scene()
        reference.build_smallpaint_scene(core_scene, size=width)
    else:
        try:
            core_scene = sync.build_scene(depsgraph, settings, width, height)
        except NotImplementedError as exc:
            engine.report({"ERROR"}, f"Painterly: {exc}")
            return

    _set_integrator(core_scene, settings, scene, reference_mode=settings.reference_scene)

    total = settings.passes
    session = _painterly.Session(core_scene, settings.threads)
    # The engine keeps the session too, so that `engine.free()` drops it and its destructor
    # cancels the render even if this function is left early (T3.14). The local name keeps it
    # alive for the loop below, which is what "keep a reference to it" means here: a dropped
    # Session is destroyed, which cancels its render.
    engine.session = session
    session.start(total, settings.batch)

    result = engine.begin_result(0, 0, width, height, layer=depsgraph.view_layer.name)

    # The passes already in the Combined pass. The first write of a poll covers a strictly larger
    # number, and `passes_done` only grows.
    written = 0
    error = ""
    while True:
        finished = session.wait(POLL_SECONDS)
        if engine.test_break():
            session.cancel()

        progress = session.progress()
        if progress["state"] == "error":
            error = progress["error"]
            break

        if progress["passes_done"] > written:
            # T3.14 publishes passes_done together with the buffers, so equal reads mean the sums
            # cover exactly p0 passes. A batch that finished between the reads makes them differ;
            # that write is skipped and the next poll retries.
            p0 = session.progress()["passes_done"]
            sums = session.combined()
            p1 = session.progress()["passes_done"]
            if p0 == p1:
                _write_result(engine, result, settings, sums, p0)
                written = p0
                engine.update_progress(p0 / total)
                engine.update_stats("", f"Pass {p0}/{total}")

        if finished:
            break

    if error:
        engine.report({"ERROR"}, f"Painterly: {error}")
        engine.end_result(result)
        return

    # The final write. It is the same pixels the last increase wrote when the loop reached the end
    # of the render, and it is the write that catches a batch the loop skipped; after the session
    # stops, its buffers never change again, so the sums and the pass count agree. A render that
    # finished no pass at all (a cancel during the first batch) has no mean radiance to map, so
    # the pass keeps the zeros Blender gave it.
    final = session.progress()["passes_done"]
    if final >= 1:
        _write_result(engine, result, settings, session.combined(), final)
    engine.end_result(result)
