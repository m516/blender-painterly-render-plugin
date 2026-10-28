# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The engine facade of the Painterly add-on.

Mirrors Cycles' ``intern/cycles/blender/addon/engine.py``. ``PainterlyRender`` in ``__init__.py``
forwards every callback here. This module owns the version check of the native module
``_painterly``; :mod:`session` and :mod:`properties` import the module for its renderer and its
socket reflection. The render loop itself lives in :mod:`session`.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

# The extension manifest is the one source of the add-on's version. The check below refuses a
# native module whose PAINTERLY_VERSION differs from it, so a stale `_painterly` cannot be paired
# with this add-on silently.
MANIFEST_PATH = Path(__file__).with_name("blender_manifest.toml")


def manifest_version() -> str:
    """The ``version`` field of ``blender_manifest.toml``, for example ``"0.1.0"``."""
    with MANIFEST_PATH.open("rb") as handle:
        return tomllib.load(handle)["version"]


def check_native_version() -> None:
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


# The check runs when this module is imported, which is before `from . import session` below and
# before `__init__.py` imports `properties`. Both use the native module at import time --
# `session` imports it and `properties` calls `_painterly.integrator_sockets()` -- so a stale
# module without those would otherwise fail with AttributeError instead of the ImportError that
# T4.1 promises. `init()` calls the same function again, for a caller that registers the add-on
# from a module that was already imported.
check_native_version()

from . import session  # noqa: E402 - the version check above must run before this import


def init() -> None:
    """Check again that the native module's version matches the manifest's.

    The check itself runs at import time (see above); this is the call that ``register()`` makes.

    Raises:
        ImportError: if ``_painterly`` cannot be imported, or reports a different version.
    """
    check_native_version()


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

    These are Blender's render passes, not the sample passes that the ``passes`` setting counts
    (SPEC §0:12); the name stays ``register_passes`` as in Cycles. Blender registers nothing for
    an engine that registers no pass, so the engine registers its one pass, ``Combined``, itself,
    as Cycles does (Cycles' ``intern/cycles/blender/addon/engine.py:184``, ``:275-277``): four
    channels, ``"RGBA"``, colour data.
    """
    engine.register_pass(scene, view_layer, session.COMBINED_PASS, 4, "RGBA", "COLOR")


def render(engine, depsgraph) -> None:
    """Render one frame; the loop itself is :func:`session.render`."""
    session.render(engine, depsgraph)
