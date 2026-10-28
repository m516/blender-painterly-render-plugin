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

from . import operators, presets, properties


class PainterlyButtonsPanel:
    """The base of every Painterly panel: the render properties, shown only for our engine."""

    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"
    COMPAT_ENGINES = {"PAINTERLY"}

    @classmethod
    def poll(cls, context):
        return context.engine in cls.COMPAT_ENGINES


def effective_spiral_frame(settings) -> str:
    """The spiral frame the core will use, which reference mode pins to ``smallpaint``.

    Args:
        settings: the ``scene.painterly`` property group.

    Returns:
        The value of ``spiral_frame``, or ``"smallpaint"`` while ``reference_scene`` is on: the
        reference scene is authored in smallpaint coordinates, so ``apply_reference_knobs()``
        overwrites the knob (``sync/reference.py:72-83``, SPEC §1).
    """
    return "smallpaint" if settings.reference_scene else settings.spiral_frame


def _reference_scene_off(settings) -> bool:
    """Whether the knob is one that reference mode overwrites (``session.py:78-89``)."""
    return not settings.reference_scene


# One activity table, by property name: a property whose entry returns False is drawn inactive,
# because its value has no effect in the current mode. A property that is not in the table is
# always active.
ACTIVITY = {
    # Reference mode overwrites these five from `apply_reference_knobs()`
    # (`session.py:78-89`, `sync/reference.py:72-83`), so the user's value is not what is rendered.
    "diffuse_gain": _reference_scene_off,
    "emission_gain": _reference_scene_off,
    "ray_epsilon": _reference_scene_off,
    "max_depth": _reference_scene_off,
    "spiral_frame": _reference_scene_off,
    # Lane Length is read only by the lane chain (`src/painterly/scene/integrator.cpp:135`,
    # SPEC §8:287).
    "lane_length": lambda settings: settings.chain == "lane",
    # The phase lock applies to the row and lane chains only (SPEC §3,
    # `src/painterly/scene/integrator.cpp:206`).
    "k0_phase_lock_bits": lambda settings: settings.chain in ("row", "lane"),
    # Exposure scales scene-linear output only (`src/painterly/scene/integrator.cpp:313`).
    "exposure": lambda settings: settings.output_mode == "scene_linear",
    # The smallpaint spiral frame ignores the extra rotation (`src/painterly/scene/integrator.cpp`,
    # the `spiral_rotation` tooltip; SPEC §1).
    "spiral_rotation": lambda settings: effective_spiral_frame(settings) != "smallpaint",
    # Spiral Object is the object of spiral_frame = object (SPEC §1, `properties.py:167`).
    "spiral_object": lambda settings: effective_spiral_frame(settings) == "object",
}


def property_active(settings, name: str) -> bool:
    """Whether the knob ``name`` affects the current render.

    Args:
        settings: the ``scene.painterly`` property group.
        name: the property name.

    Returns:
        The entry of :data:`ACTIVITY` for ``name``, or True for a name that is not in the table.
    """
    rule = ACTIVITY.get(name)
    return True if rule is None else rule(settings)


def draw_property(layout, settings, name: str) -> None:
    """Draw one property of ``settings`` in a sub-layout that is inactive when it has no effect.

    Args:
        layout: the panel's layout.
        settings: the ``scene.painterly`` property group.
        name: the property name.
    """
    sub = layout.column()
    sub.active = property_active(settings, name)
    sub.prop(settings, name)


def draw_socket_group(layout, settings, group: str) -> None:
    """Draw the generated properties of one socket group, in socket order.

    Args:
        layout: the panel's layout.
        settings: the ``scene.painterly`` property group.
        group: the group name, one of ``properties.SOCKET_GROUPS``.
    """
    for name in properties.SOCKET_GROUPS[group]:
        draw_property(layout, settings, name)


class RENDER_PT_painterly_sampling(PainterlyButtonsPanel, bpy.types.Panel):
    """The sampling knobs: chain, lane length, seed and the pass count."""

    bl_label = "Sampling"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        settings = context.scene.painterly

        draw_socket_group(layout, settings, "Sampling")
        draw_property(layout, settings, "batch")
        draw_property(layout, settings, "threads")


class RENDER_PT_painterly_brush(PainterlyButtonsPanel, bpy.types.Panel):
    """The brush knobs: the spiral frame and the second-dimension mode."""

    bl_label = "Brush"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        settings = context.scene.painterly

        draw_socket_group(layout, settings, "Brush")
        draw_property(layout, settings, "spiral_object")


class RENDER_PT_painterly_path(PainterlyButtonsPanel, bpy.types.Panel):
    """The path knobs: bounces, gains, epsilon and sidedness."""

    bl_label = "Path"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        draw_socket_group(layout, context.scene.painterly, "Path")


class RENDER_PT_painterly_lights(PainterlyButtonsPanel, bpy.types.Panel):
    """The light knobs: emission scale and ghost lights."""

    bl_label = "Lights"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        draw_socket_group(layout, context.scene.painterly, "Lights")


class RENDER_PT_painterly_film(PainterlyButtonsPanel, bpy.types.Panel):
    """The film knobs: output mode, exposure and jitter, plus the reference-scene switch."""

    bl_label = "Film"

    def draw_header_preset(self, context):
        presets.PAINTERLY_PT_render_presets.draw_panel_header(self.layout)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        scene = context.scene
        settings = scene.painterly

        draw_socket_group(layout, settings, "Film")
        draw_property(layout, settings, "reference_scene")

        # The display-referred mode reproduces smallpaint only under the display settings of
        # SPEC §8, and the engine never sets them itself, so the panel offers the operator and
        # warns while the settings differ. The warning and the operator call the same comparison,
        # so the row cannot disagree with the button.
        if settings.output_mode == "display_referred" and operators.differing_display_settings(
            scene
        ):
            row = layout.row()
            row.alert = True
            row.label(
                text="Display settings differ from smallpaint's: the image will not match its bytes"
            )
        layout.separator()
        layout.operator(operators.PAINTERLY_OT_apply_display_settings.bl_idname)


classes = (
    RENDER_PT_painterly_sampling,
    RENDER_PT_painterly_brush,
    RENDER_PT_painterly_path,
    RENDER_PT_painterly_lights,
    RENDER_PT_painterly_film,
)

# Blender's render panels that Painterly does not use, so it does not lend them to our engine.
EXCLUDE_PANELS = {
    # Decision: Painterly has no simplification stage, so Blender's generic Simplify panel (Max
    # Subdivision, Max Child Particles, Volume Resolution, Normals; Blender 5.2.2
    # `scripts/startup/bl_ui/properties_render.py:1079-1140`) is not lent to our engine.
    "RENDER_PT_simplify",
    # Decision: the engine declares no previews (`__init__.py`: `bl_use_preview = False`), so
    # Blender's Preview panel of the Light tab (Blender 5.2.2
    # `scripts/startup/bl_ui/properties_data_light.py:45-54`) could not fill it; Cycles excludes it
    # too (Cycles' `intern/cycles/blender/addon/ui.py:2557`). Remove this entry when material
    # previews exist.
    "DATA_PT_preview",
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
