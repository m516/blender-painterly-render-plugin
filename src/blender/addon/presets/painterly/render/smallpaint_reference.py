# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""The smallpaint reference configuration (SPEC §8, §9)."""

import bpy

# The smallpaint reference configuration (SPEC §8, §9): smallpaint's built-in GUI scene, driven by
# the image chain of smallpaint itself. The preset panel's `reset_cb` unsets every setting of
# `presets.PRESET_VALUES` before this file runs, so each knob this file does not name is at its
# generated default, which is the reference behaviour. The two `property_unset()` calls below keep
# that true when the file is run on its own, as `tests/blender/test_properties.py` does.
#
# The image size and the view settings are the user's, not the preset's: the reference scene needs a
# square image (SPEC §7, `session.py`), and SPEC §8's display mapping is what
# `PAINTERLY_OT_apply_display_settings` is for. The reference builder pins the smallpaint-unit knobs
# (gains, epsilon, frame) itself; see T4.3.
painterly = bpy.context.scene.painterly

painterly.chain = "image"
painterly.reference_scene = True

painterly.property_unset("output_mode")
painterly.property_unset("passes")
