# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The Blender-scene sync: Blender's ``depsgraph`` → the core ``Scene`` (M5).

Mirrors Cycles' ``intern/cycles/blender/sync.py``: one function builds a core scene from the
evaluated Blender scene, and the render loop of :mod:`session` calls it once per frame. The
reference scene does not need it — :mod:`sync.reference` builds that one — so until M5 syncs the
Blender scene, :func:`build_scene` raises ``NotImplementedError`` and the render loop turns the
exception into an ``engine.report``. T5.1, T5.2 and T5.3 fill this module in.
"""

from __future__ import annotations


def build_scene(depsgraph, settings, width: int, height: int):
    """Build the core ``Scene`` of the Blender scene that ``depsgraph`` holds.

    Args:
        depsgraph: Blender's evaluated dependency graph of the frame being rendered.
        settings: ``scene.painterly``, the add-on's render settings.
        width: the image width in pixels.
        height: the image height in pixels.

    Returns:
        A ``_painterly.Scene``.

    Raises:
        NotImplementedError: always, until M5 syncs the Blender scene.
    """
    raise NotImplementedError("Blender scene sync arrives in M5")
