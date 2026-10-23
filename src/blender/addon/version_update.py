# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""File versioning of the Painterly settings.

Mirrors Cycles' ``intern/cycles/blender/addon/version_update.py``: a ``@persistent`` handler on
``bpy.app.handlers.version_update`` that runs after a file is loaded and upgrades
``scene.painterly.data_version`` to :data:`CURRENT_DATA_VERSION`.
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent

# The settings version this add-on writes. Bump it, and add a step to `upgrade()`, whenever a
# saved `scene.painterly` needs converting; a file saved by a newer add-on keeps its version.
CURRENT_DATA_VERSION = 1


def upgrade(settings, from_version: int) -> None:
    """Upgrade ``settings`` from ``from_version`` to :data:`CURRENT_DATA_VERSION`.

    The documented hook for later versions: each step is one ``if from_version < n:`` block that
    converts what changed in version ``n``. There is no step yet, because version 1 is the first.

    Args:
        settings: the loaded ``scene.painterly`` property group.
        from_version: the ``data_version`` the file was saved with.
    """
    del settings, from_version


@persistent
def do_versions(scene) -> None:
    """Bring ``scene.painterly.data_version`` up to :data:`CURRENT_DATA_VERSION` after a load.

    Args:
        scene: the scene whose Painterly settings are upgraded.
    """
    settings = getattr(scene, "painterly", None)
    if settings is None:
        return

    from_version = settings.data_version
    if from_version < CURRENT_DATA_VERSION:
        upgrade(settings, from_version)
        settings.data_version = CURRENT_DATA_VERSION


def register() -> None:
    """Append the handler to ``bpy.app.handlers.version_update``."""
    handlers = bpy.app.handlers.version_update
    if do_versions not in handlers:
        handlers.append(do_versions)


def unregister() -> None:
    """Remove the handler again."""
    handlers = bpy.app.handlers.version_update
    if do_versions in handlers:
        handlers.remove(do_versions)
