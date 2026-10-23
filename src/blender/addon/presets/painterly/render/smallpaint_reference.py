import bpy

# The smallpaint reference configuration (SPEC §8, §9): smallpaint's built-in GUI scene, driven by
# the image chain of smallpaint itself. Every other knob keeps its generated default, which is the
# reference behaviour, so the two knobs a user may have changed are reset to those defaults with
# `property_unset()` instead of being pinned to whatever the file happened to hold. The reference
# builder pins the smallpaint-unit knobs (gains, epsilon, frame) itself; see T4.3.
painterly = bpy.context.scene.painterly

painterly.chain = "image"
painterly.reference_scene = True

painterly.property_unset("output_mode")
painterly.property_unset("passes")
