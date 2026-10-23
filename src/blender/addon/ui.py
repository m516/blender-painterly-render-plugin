# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The Painterly panels of the render properties.

Mirrors Cycles' ``intern/cycles/blender/addon/ui.py``: one ``ButtonsPanel`` mixin that polls for
the engine, one panel per integrator socket group (the groups that
``_painterly.integrator_sockets()`` reports), each drawing the generated properties of its group in
socket order, and ``get_panels()``, which lends ``PAINTERLY`` Blender's own render panels.
"""

from __future__ import annotations

import bpy

from . import properties


class PainterlyButtonsPanel:
    """The base of every Painterly panel: the render properties, shown only for our engine."""

    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    COMPAT_ENGINES = {"PAINTERLY"}

    @classmethod
    def poll(cls, context):
        return context.engine in cls.COMPAT_ENGINES


def draw_socket_group(layout, settings, group: str) -> None:
    """Draw the generated properties of one socket group, in socket order.

    Args:
        layout: the panel's layout.
        settings: the ``scene.painterly`` property group.
        group: the group name, one of ``properties.SOCKET_GROUPS``.
    """
    for name in properties.SOCKET_GROUPS[group]:
        layout.prop(settings, name)


class RENDER_PT_painterly_sampling(PainterlyButtonsPanel, bpy.types.Panel):
    """The sampling knobs: chain, lane length, seed and the pass count."""

    bl_label = "Sampling"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        settings = context.scene.painterly

        draw_socket_group(layout, settings, "Sampling")
        layout.prop(settings, "batch")
        layout.prop(settings, "threads")


class RENDER_PT_painterly_brush(PainterlyButtonsPanel, bpy.types.Panel):
    """The brush knobs: the spiral frame and the second-dimension mode."""

    bl_label = "Brush"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        settings = context.scene.painterly

        draw_socket_group(layout, settings, "Brush")
        layout.prop(settings, "spiral_object")


class RENDER_PT_painterly_path(PainterlyButtonsPanel, bpy.types.Panel):
    """The path knobs: bounces, gains, epsilon and sidedness."""

    bl_label = "Path"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True

        draw_socket_group(layout, context.scene.painterly, "Path")


class RENDER_PT_painterly_lights(PainterlyButtonsPanel, bpy.types.Panel):
    """The light knobs: emission scale and ghost lights."""

    bl_label = "Lights"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True

        draw_socket_group(layout, context.scene.painterly, "Lights")


class RENDER_PT_painterly_film(PainterlyButtonsPanel, bpy.types.Panel):
    """The film knobs: output mode, exposure and jitter, plus the reference-scene switch."""

    bl_label = "Film"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        settings = context.scene.painterly

        draw_socket_group(layout, settings, "Film")
        layout.prop(settings, "reference_scene")


classes = (
    RENDER_PT_painterly_sampling,
    RENDER_PT_painterly_brush,
    RENDER_PT_painterly_path,
    RENDER_PT_painterly_lights,
    RENDER_PT_painterly_film,
)

# Blender's render panels that Painterly does not use, so it does not lend them to our engine.
EXCLUDE_PANELS = {
    # Simplify is Cycles' viewport/render simplification (subdivision and culling thresholds); the
    # Painterly core has no simplification stage, so the panel would offer settings that do
    # nothing.
    "RENDER_PT_simplify",
}


# SPDX-FileCopyrightText: 2011-2022 Blender Foundation
# SPDX-License-Identifier: Apache-2.0
#
# Copied from Blender v5.2.2 `intern/cycles/blender/addon/ui.py` (Apache-2.0, Blender Foundation),
# with Cycles' exclude set replaced by ours above; see THIRD_PARTY_NOTICES.md.
def get_panels():
    """The Blender panels that are shown for the Painterly engine as well.

    Cycles lends its engine every built-in panel that lists ``BLENDER_RENDER``, except the ones it
    replaces with its own. Painterly has no replacements yet, so it excludes only the panels it
    cannot honour (:data:`EXCLUDE_PANELS`).
    """
    panels = []
    for panel in bpy.types.Panel.__subclasses__():
        # Upstream's two nested `if`s, merged into one for ruff (SIM102); the conditions are
        # unchanged.
        if (
            hasattr(panel, "COMPAT_ENGINES")
            and "BLENDER_RENDER" in panel.COMPAT_ENGINES
            and panel.__name__ not in EXCLUDE_PANELS
        ):
            panels.append(panel)

    return panels


def register() -> None:
    """Register the panels, then lend Painterly the built-in render panels."""
    from bpy.utils import register_class

    for panel in get_panels():
        panel.COMPAT_ENGINES.add("PAINTERLY")

    for cls in classes:
        register_class(cls)


def unregister() -> None:
    """Undo :func:`register`."""
    from bpy.utils import unregister_class

    for cls in classes:
        unregister_class(cls)

    for panel in get_panels():
        if "PAINTERLY" in panel.COMPAT_ENGINES:
            panel.COMPAT_ENGINES.remove("PAINTERLY")
