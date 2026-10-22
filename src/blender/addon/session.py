# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The render loop: session ↔ RenderResult (filled by T4.3).

Until T4.3 lands, rendering reports an error instead of producing an image. ``engine.render``
always calls :func:`render`, so T4.3 replaces this body and leaves ``engine.py`` untouched.
"""

from __future__ import annotations


def render(engine, depsgraph) -> None:
    """Report that rendering is not implemented yet.

    Args:
        engine: the ``bpy.types.RenderEngine`` instance that asked for the render.
        depsgraph: Blender's dependency graph of the frame being rendered (unused by the stub).
    """
    engine.report({"ERROR"}, "Painterly: rendering arrives in T4.3")
