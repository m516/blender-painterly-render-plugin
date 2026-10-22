# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""File versioning for the ``PAINTERLY`` engine (filled by T4.2).

The stub registers no handler; the ``bpy.app.handlers.version_update`` hook that upgrades
``scene.painterly.data_version`` arrives with T4.2.
"""

from __future__ import annotations


def register() -> None:
    """Register the version handler (T4.2: append it to ``bpy.app.handlers.version_update``)."""


def unregister() -> None:
    """Undo :func:`register` (T4.2: remove the handler again)."""
