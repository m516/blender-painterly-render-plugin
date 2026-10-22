# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Properties generated from the core's socket reflection (filled by T4.2).

The stub registers nothing; ``scene.painterly`` and its generated sockets arrive with T4.2.
"""

from __future__ import annotations


def register() -> None:
    """Register the property groups (T4.2: ``PainterlyRenderSettings`` as ``scene.painterly``)."""


def unregister() -> None:
    """Undo :func:`register` (T4.2: remove ``bpy.types.Scene.painterly``)."""
