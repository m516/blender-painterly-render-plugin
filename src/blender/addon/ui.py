# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Cycles-style panels for the ``PAINTERLY`` engine (filled by T4.2).

The stub registers no panel; the render-properties panels arrive with T4.2.
"""

from __future__ import annotations


def register() -> None:
    """Register the panels (T4.2: the ``RENDER_PT_painterly_*`` panels)."""


def unregister() -> None:
    """Undo :func:`register` (T4.2: unregister the panels, drop them from ``COMPAT_ENGINES``)."""
