# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operators of the Painterly engine.

Mirrors Cycles' ``intern/cycles/blender/addon/operators.py``. So far there is one operator: the
one that sets up the colour management that the display-referred output mode needs (SPEC §8).
"""

from __future__ import annotations

from typing import NamedTuple

from bpy.types import Operator


class DisplaySetting(NamedTuple):
    """One setting of smallpaint's display mapping.

    Attributes:
        owner: the attribute of ``bpy.types.Scene`` that holds the setting.
        name: the RNA name of the setting.
        value: the value that reproduces smallpaint's displayed bytes.
    """

    owner: str
    name: str
    value: object


# The colour-management state that the display-referred output mode of SPEC §8 assumes: the sRGB
# display device with the Standard view transform, no look, no extra exposure or gamma, no Curves
# and no White Balance, and dither 0 so that an 8-bit write is the byte that smallpaint would have
# written (up to rounding).
#
# `display_device` is on `scene.display_settings`, the others on `scene.view_settings`, and the
# dither on `scene.render` (Blender 5.2.2 `scripts/startup/bl_ui/properties_render.py:74`, `:172`,
# `:209`). With the Standard view transform, the sRGB display applies IEC 61966-2-1's compound
# encoding (`datafiles/colormanagement/config.ocio:59-60`, `:132-145`); Display P3 has a Standard
# view of its own (`:69-70`), a different display colour space, so it is not the same bytes.
# Curves and White Balance change the displayed pixels.
DISPLAY_SETTINGS = (
    DisplaySetting("view_settings", "view_transform", "Standard"),
    DisplaySetting("view_settings", "look", "None"),
    DisplaySetting("view_settings", "exposure", 0.0),
    DisplaySetting("view_settings", "gamma", 1.0),
    DisplaySetting("render", "dither_intensity", 0.0),
    DisplaySetting("display_settings", "display_device", "sRGB"),
    DisplaySetting("view_settings", "use_curve_mapping", False),
    DisplaySetting("view_settings", "use_white_balance", False),
)


def differing_display_settings(scene) -> tuple[DisplaySetting, ...]:
    """The entries of :data:`DISPLAY_SETTINGS` whose current value differs from its target.

    The operator and the Film panel's warning row both call this, so the row cannot disagree with
    the button about whether a setting differs.

    Args:
        scene: the scene to read.

    Returns:
        The differing entries, in :data:`DISPLAY_SETTINGS` order.
    """
    return tuple(
        entry
        for entry in DISPLAY_SETTINGS
        if getattr(getattr(scene, entry.owner), entry.name) != entry.value
    )


class PAINTERLY_OT_apply_display_settings(Operator):
    """Use smallpaint display settings"""

    bl_idname = "render.painterly_apply_display_settings"
    bl_label = "Use smallpaint display settings"
    bl_description = (
        "Set the Standard view transform, no look, exposure 0, gamma 1 and dither 0, on the sRGB "
        "display, without Curves or White Balance, which is what the Display Referred output mode "
        "reproduces smallpaint's bytes with"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        differing = differing_display_settings(scene)
        for entry in differing:
            setattr(getattr(scene, entry.owner), entry.name, entry.value)

        if not differing:
            self.report({"INFO"}, "Painterly: the display settings already match smallpaint")
        else:
            self.report(
                {"INFO"},
                "Painterly: set "
                + ", ".join(entry.name for entry in differing)
                + " for smallpaint's display settings",
            )
        return {"FINISHED"}


classes = (PAINTERLY_OT_apply_display_settings,)


def register() -> None:
    """Register the operators."""
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)


def unregister() -> None:
    """Undo :func:`register`."""
    from bpy.utils import unregister_class

    for cls in classes:
        unregister_class(cls)
