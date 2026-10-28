# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Presets of the Painterly engine.

Mirrors Cycles' ``intern/cycles/blender/addon/presets.py``: one ``AddPresetBase`` operator that
saves the render settings to ``presets/painterly/render/``, and one preset menu panel that lists
the presets found there. The shipped preset, ``presets/painterly/render/smallpaint_reference.py``,
is the reference configuration of SPEC §8.
"""

from __future__ import annotations

import os

import bpy
from bl_operators.presets import AddPresetBase
from bl_ui.utils import PresetPanel
from bpy.types import Operator, Panel

from . import properties

# The preset subdirectory, relative to a registered preset path (``presets/`` next to this file).
PRESET_SUBDIR = "painterly/render"

# This file's directory: ``bpy.utils.register_preset_path()`` wants the parent of ``presets/``.
PRESET_PATH = os.path.dirname(__file__)

# The settings a preset stores: every generated socket, plus the hand-written settings a preset can
# carry. ``spiral_object`` is left out because it is a pointer to a Blender object, which a preset
# cannot name portably, and ``data_version`` because it is the file's own bookkeeping, not a knob.
PRESET_VALUES = tuple(f"painterly.{name}" for name in properties.SOCKET_NAMES) + (
    "painterly.batch",
    "painterly.threads",
    "painterly.reference_scene",
)


class PAINTERLY_OT_render_preset_add(AddPresetBase, Operator):
    """Add a Painterly render preset"""

    bl_idname = "render.painterly_render_preset_add"
    bl_label = "Add Painterly Render Preset"
    preset_menu = "PAINTERLY_PT_render_presets"

    preset_defines = ["painterly = bpy.context.scene.painterly"]

    preset_values = list(PRESET_VALUES)

    preset_subdir = PRESET_SUBDIR


class PAINTERLY_PT_render_presets(PresetPanel, Panel):
    """The preset menu of the render properties header."""

    bl_label = "Painterly Presets"
    preset_subdir = PRESET_SUBDIR
    preset_add_operator = PAINTERLY_OT_render_preset_add.bl_idname
    # `PresetPanel.draw()` calls `Menu.draw_preset()`, which reads `preset_operator` to pick the
    # operator of each menu entry; without it the popover raises AttributeError. Cycles'
    # `CyclesPresetPanel` sets the same value.
    preset_operator = "script.execute_preset"

    @staticmethod
    def reset_cb(context, filepath) -> None:
        """Unset every preset setting before a preset file runs.

        Blender's ``script.execute_preset`` calls ``reset_cb(context, filepath)`` of the class that
        ``menu_idname`` names before it executes the file (Blender 5.2.2
        ``scripts/startup/bl_operators/presets.py:299``), so a preset that does not name a setting
        gives that setting its socket default instead of the value the user happened to have.
        ``_call_preset_cb`` (``presets.py:36-57``) passes the file path only to a callback of
        exactly two parameters, which is why the signature is fixed.

        Args:
            context: Blender's context; its scene holds the settings.
            filepath: the preset file about to run. Unused.
        """
        settings = context.scene.painterly
        for path in PRESET_VALUES:
            settings.property_unset(path.removeprefix("painterly."))


classes = (
    PAINTERLY_OT_render_preset_add,
    PAINTERLY_PT_render_presets,
)


def register() -> None:
    """Register the preset operator and menu, and the add-on's preset path."""
    from bpy.utils import register_class

    for cls in classes:
        register_class(cls)

    bpy.utils.register_preset_path(PRESET_PATH)


def unregister() -> None:
    """Undo :func:`register`."""
    from bpy.utils import unregister_class

    bpy.utils.unregister_preset_path(PRESET_PATH)

    for cls in classes:
        unregister_class(cls)
