# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The engine facade of the Painterly add-on.

Mirrors Cycles' ``intern/cycles/blender/addon/engine.py``. ``PainterlyRender`` in ``__init__.py``
forwards every callback here, and this module is the only place that knows about the native module
``_painterly``. The render loop itself lives in :mod:`session`, so T4.3 fills that in without
touching this file.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from . import session

# The extension manifest is the one source of the add-on's version. `init()` refuses a native
# module whose PAINTERLY_VERSION differs from it, so a stale `_painterly` cannot be paired with
# this add-on silently.
MANIFEST_PATH = Path(__file__).with_name("blender_manifest.toml")


def manifest_version() -> str:
    """The ``version`` field of ``blender_manifest.toml``, for example ``"0.1.0"``."""
    with MANIFEST_PATH.open("rb") as handle:
        return tomllib.load(handle)["version"]


def init() -> None:
    """Import the native module and check that its version matches the manifest's.

    Raises:
        ImportError: if ``_painterly`` cannot be imported, or reports a different version.
    """
    import _painterly

    expected = manifest_version()
    found = _painterly.version_info()["version"]
    if found != expected:
        raise ImportError(
            f"Painterly: the native module _painterly is version {found}, but the add-on's "
            f"blender_manifest.toml declares {expected}. "
            "Build the module from this tree (`make build`)."
        )


def free(engine) -> None:
    """Release the render session of ``engine``, if it has one.

    The core's ``Session`` cancels its render and joins its thread when it is destroyed (T3.14),
    so dropping the reference is the release. ``__del__`` calls this on an engine that may never
    have rendered, which is why the attribute is read with ``getattr``.
    """
    if getattr(engine, "session", None) is not None:
        engine.session = None


def register_passes(engine, scene, view_layer) -> None:
    """Register the engine's render passes for ``scene`` and ``view_layer``.

    Only Blender's built-in ``Combined`` pass exists so far, and Blender adds that one for every
    render engine, so there is nothing to register. T4.3's output modes add their passes here
    through ``engine.register_pass``.
    """


def render(engine, depsgraph) -> None:
    """Render one frame; the loop itself is :func:`session.render` (T4.3 replaces that stub)."""
    session.render(engine, depsgraph)
