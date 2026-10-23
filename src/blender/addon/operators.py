# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Operators of the Painterly engine.

Mirrors Cycles' ``intern/cycles/blender/addon/operators.py``. So far there is one operator: the
one that sets up the colour management that the display-referred output mode needs (SPEC §8).
"""

from __future__ import annotations

from bpy.types import Operator

# The colour-management state that the display-referred output mode of SPEC §8 assumes: the
# Standard view transform, no look, no extra exposure or gamma, and dither 0 so that an 8-bit
# write is the byte that smallpaint would have written (up to rounding).
DISPLAY_SETTINGS = {
    "view_transform": "Standard",
    "look": "None",
    "exposure": 0.0,
    "gamma": 1.0,
}


def display_settings_of(scene) -> dict[str, object]:
    """The current values of the settings :data:`DISPLAY_SETTINGS` names, plus the dither.

    Args:
        scene: the scene to read.

    Returns:
        A dict from setting name to its current value; ``dither_intensity`` comes from
        ``scene.render``, the others from ``scene.view_settings``.
    """
    settings = {name: getattr(scene.view_settings, name) for name in DISPLAY_SETTINGS}
    settings["dither_intensity"] = scene.render.dither_intensity
    return settings


class PAINTERLY_OT_apply_display_settings(Operator):
    """Use smallpaint display settings"""

    bl_idname = "render.painterly_apply_display_settings"
    bl_label = "Use smallpaint display settings"
    bl_description = (
        "Set the Standard view transform, no look, exposure 0, gamma 1 and dither 0, which is "
        "what the Display Referred output mode reproduces smallpaint's bytes with"
    )
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        scene = context.scene
        changed = []
        for name, value in DISPLAY_SETTINGS.items():
            if getattr(scene.view_settings, name) != value:
                setattr(scene.view_settings, name, value)
                changed.append(name)
        if scene.render.dither_intensity != 0.0:
            scene.render.dither_intensity = 0.0
            changed.append("dither_intensity")

        if not changed:
            self.report({"INFO"}, "Painterly: the display settings already match smallpaint")
        else:
            self.report(
                {"INFO"},
                "Painterly: set " + ", ".join(changed) + " for smallpaint's display settings",
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
