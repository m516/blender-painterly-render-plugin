# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The Blender-scene sync: Blender's ``depsgraph`` → the core ``Scene`` (M5).

Mirrors Cycles' ``intern/cycles/blender/sync.py``: one function builds a core scene from the
evaluated Blender scene, and the render loop of :mod:`session` calls it once per frame. The
reference scene does not need it — :mod:`sync.reference` builds that one — so this is the
Blender-scene path only.

T5.1 builds the core scene and syncs its camera (:mod:`sync.camera`); T5.2 and T5.3 add their
calls here.
"""

from __future__ import annotations

import _painterly

from .camera import sync_camera


def build_scene(depsgraph, settings, width: int, height: int):
    """Build the core ``Scene`` of the Blender scene that ``depsgraph`` holds.

    Args:
        depsgraph: Blender's evaluated dependency graph of the frame being rendered.
        settings: ``scene.painterly``, the add-on's render settings.
        width: the image width in pixels.
        height: the image height in pixels.

    Returns:
        A ``_painterly.Scene`` with the frame's camera (and, from T5.2 on, its geometry).

    Raises:
        NotImplementedError: for a camera type the core has no equivalent for.
        ValueError: if the scene has no camera, or ``spiral_frame`` is ``"object"`` with no
            spiral object set.
    """
    scene_core = _painterly.Scene()
    sync_camera(scene_core, depsgraph, settings, width, height)
    return scene_core
