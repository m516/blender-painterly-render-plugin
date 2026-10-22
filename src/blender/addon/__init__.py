# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The Painterly render engine add-on.

Mirrors Cycles' ``intern/cycles/blender/addon/__init__.py``. Blender loads this package as the
extension ``painterly``. It registers one render engine, ``PAINTERLY``, whose callbacks forward to
the thin facade in :mod:`engine`, exactly as Cycles' ``CyclesRender`` forwards to its ``engine``.
"""

from __future__ import annotations

# Support 'reload' case: when Blender reloads the add-on the submodules are already imported, so
# they must be reloaded first, or the class below would keep the stale copies. Cycles' add-on does
# the same with one `if` per submodule.
if "bpy" in locals():
    import importlib

    for _name in ("engine", "version_update", "properties", "ui", "operators", "presets"):
        if _name in locals():
            importlib.reload(locals()[_name])

import bpy

from . import engine, version_update


class PainterlyRender(bpy.types.RenderEngine):
    """The ``PAINTERLY`` engine: Blender's callbacks, forwarded to the ``engine`` facade."""

    bl_idname = "PAINTERLY"
    bl_label = "Painterly"

    # Material previews need a preview session of their own; they arrive after the render loop
    # (T4.3) and the Blender-scene sync (M5).
    bl_use_preview = False
    # Material Preview shading uses EEVEE, as for Cycles (Cycles' add-on sets the same flag).
    bl_use_eevee_viewport = True
    # The standard Shader Editor and Principled BSDF are available, so no custom shading-node
    # system is needed.
    bl_use_shading_nodes_custom = False
    # bl_use_postprocess is deliberately unset: Blender's own default is what we want, because the
    # engine composites nothing itself.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session = None

    def __del__(self):
        engine.free(self)

    def render(self, depsgraph):
        engine.render(self, depsgraph)

    def update_render_passes(self, scene, view_layer):
        engine.register_passes(self, scene, view_layer)


classes = (PainterlyRender,)


def register() -> None:
    """Register the render engine and its properties, UI, operators, presets and version handler."""
    from bpy.utils import register_class

    from . import operators, presets, properties, ui

    engine.init()

    properties.register()
    ui.register()
    operators.register()
    presets.register()
    version_update.register()

    for cls in classes:
        register_class(cls)


def unregister() -> None:
    """Undo :func:`register`, in the reverse order."""
    from bpy.utils import unregister_class

    from . import operators, presets, properties, ui

    for cls in classes:
        unregister_class(cls)

    version_update.unregister()
    presets.unregister()
    operators.unregister()
    ui.unregister()
    properties.unregister()
