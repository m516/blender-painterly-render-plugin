# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""``scene.painterly``: the integrator knobs, generated from the core's socket reflection.

Mirrors Cycles' ``intern/cycles/blender/addon/properties.py``, which writes its
``CyclesRenderSettings`` annotations by hand. Every knob of SPEC §8 is a ``PainterlyIntegrator``
socket, and ``_painterly.integrator_sockets()`` reports each socket's type, default, limits, UI
name, description and group (T3.13). This module builds the Blender properties from that report
when it is imported, so each default is written exactly once, in the core, and a Blender property
can never drift from the renderer's. Only the properties that are not engine knobs (``batch``,
``threads``, ``spiral_object``, ``reference_scene``, ``data_version``) are written by hand, each
with its reason.
"""

from __future__ import annotations

from typing import Any

import _painterly
import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
)

# Blender stores an int property as a C int, so a uint socket is clamped to this range; 2**31 - 1 is
# Blender's int32 maximum.
BLENDER_INT_MIN = -(2**31)
BLENDER_INT_MAX = 2**31 - 1

# The one per-name subtype override. ``spiral_rotation`` is an XYZ Euler rotation in radians, so
# Blender draws it as an angle triplet; every other vector socket takes the default subtype.
VECTOR_SUBTYPES = {"spiral_rotation": "EULER"}


def _int_property(socket: dict[str, Any]) -> Any:
    """An ``IntProperty`` for an ``int`` or ``uint`` socket, clamped to Blender's int32 range.

    A ``uint`` socket has no negative values, so its minimum is 0; a reflected limit that is
    tighter than Blender's own range wins, and a reflected limit outside it is clamped.
    """
    low = 0 if socket["type"] == "uint" else BLENDER_INT_MIN
    high = BLENDER_INT_MAX
    if socket["min"] is not None:
        low = max(low, int(socket["min"]))
    if socket["max"] is not None:
        high = min(high, int(socket["max"]))

    kwargs: dict[str, Any] = {
        "name": socket["ui_name"],
        "description": socket["description"],
        "default": int(socket["default"]),
        "min": low,
        "max": high,
    }
    for key in ("soft_min", "soft_max"):
        if socket[key] is not None:
            kwargs[key] = int(socket[key])
    return IntProperty(**kwargs)


def _float_property(socket: dict[str, Any]) -> Any:
    """A ``FloatProperty`` for a ``float`` socket, with the reflected limits and soft limits."""
    kwargs: dict[str, Any] = {
        "name": socket["ui_name"],
        "description": socket["description"],
        "default": float(socket["default"]),
    }
    for key in ("min", "max", "soft_min", "soft_max"):
        if socket[key] is not None:
            kwargs[key] = float(socket[key])
    return FloatProperty(**kwargs)


def _bool_property(socket: dict[str, Any]) -> Any:
    """A ``BoolProperty`` for a ``boolean`` socket."""
    return BoolProperty(
        name=socket["ui_name"],
        description=socket["description"],
        default=bool(socket["default"]),
    )


def _enum_property(socket: dict[str, Any]) -> Any:
    """An ``EnumProperty`` for an ``enum`` socket.

    The items are the socket's identifiers in socket order, and each item's label is the
    identifier with underscores as spaces, in title case (card T4.2).
    """
    items = tuple((item, item.replace("_", " ").title(), "") for item in socket["enum_items"])
    return EnumProperty(
        name=socket["ui_name"],
        description=socket["description"],
        items=items,
        default=socket["default"],
    )


def _vector_property(socket: dict[str, Any]) -> Any:
    """A ``FloatVectorProperty`` of size 3 for a ``vector`` socket."""
    kwargs: dict[str, Any] = {
        "name": socket["ui_name"],
        "description": socket["description"],
        "size": 3,
        "default": tuple(float(value) for value in socket["default"]),
    }
    subtype = VECTOR_SUBTYPES.get(socket["name"])
    if subtype is not None:
        kwargs["subtype"] = subtype
    return FloatVectorProperty(**kwargs)


# One builder per SocketInfo["type"] (the pyi's literal list).
PROPERTY_BUILDERS = {
    "boolean": _bool_property,
    "int": _int_property,
    "uint": _int_property,
    "float": _float_property,
    "enum": _enum_property,
    "vector": _vector_property,
}


def socket_annotations(sockets: list[dict[str, Any]]) -> dict[str, Any]:
    """One Blender property per socket, in socket order, as a class annotation dict."""
    return {socket["name"]: PROPERTY_BUILDERS[socket["type"]](socket) for socket in sockets}


def socket_groups(sockets: list[dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    """The socket names of each UI group (SocketInfo["group"]), in socket order."""
    grouped: dict[str, list[str]] = {}
    for socket in sockets:
        grouped.setdefault(socket["group"], []).append(socket["name"])
    return {group: tuple(names) for group, names in grouped.items()}


SOCKETS = _painterly.integrator_sockets()
SOCKET_NAMES = tuple(socket["name"] for socket in SOCKETS)
SOCKET_GROUPS = socket_groups(SOCKETS)
SOCKET_ANNOTATIONS = socket_annotations(SOCKETS)

# The properties that are not engine knobs. Each one is written here because the core has no socket
# for it:
HAND_WRITTEN_ANNOTATIONS = {
    # Passes per progress update; the output is identical for any batch (SPEC §3).
    "batch": IntProperty(
        name="Batch",
        description="Passes per progress update. The output is identical for any batch",
        default=1,
        min=1,
    ),
    # Render threads; 0 lets the core use one per hardware thread (SPEC §3).
    "threads": IntProperty(
        name="Threads",
        description="Render threads. 0 means one per hardware thread",
        default=0,
        min=0,
    ),
    # The object of spiral_frame = object (SPEC §1); a pointer, so no socket can carry it.
    "spiral_object": PointerProperty(
        type=bpy.types.Object,
        name="Spiral Object",
        description="Object whose rotation the spiral follows when Spiral Frame is Object",
    ),
    # Renders smallpaint's built-in GUI scene (SPEC §9) instead of the Blender scene; the scene
    # source is the add-on's choice, so it is not an integrator knob.
    "reference_scene": BoolProperty(
        name="Reference Scene",
        description="Render smallpaint's built-in GUI scene instead of the Blender scene "
        "(reference check)",
        default=False,
    ),
    # The saved-settings version that version_update.py upgrades on file load.
    "data_version": IntProperty(
        name="Data Version",
        description="Version of the saved Painterly settings, upgraded when a file is loaded",
        default=0,
        options={"HIDDEN"},
    ),
}

if set(SOCKET_ANNOTATIONS) & set(HAND_WRITTEN_ANNOTATIONS):
    raise RuntimeError(
        "properties: a hand-written property shadows an integrator socket: "
        f"{sorted(set(SOCKET_ANNOTATIONS) & set(HAND_WRITTEN_ANNOTATIONS))}"
    )


class PainterlyRenderSettings(bpy.types.PropertyGroup):
    """The ``scene.painterly`` property group: the generated sockets plus the add-on's own knobs."""

    __slots__ = ()
    __annotations__ = {**SOCKET_ANNOTATIONS, **HAND_WRITTEN_ANNOTATIONS}

    @classmethod
    def register(cls) -> None:
        """Attach the group to the scene as ``scene.painterly``.

        ``bpy.utils.register_class()`` calls this classmethod, as it does for Cycles'
        ``CyclesRenderSettings``.
        """
        bpy.types.Scene.painterly = PointerProperty(
            name="Painterly Render Settings",
            description="Painterly render settings",
            type=cls,
        )

    @classmethod
    def unregister(cls) -> None:
        """Remove ``scene.painterly``."""
        del bpy.types.Scene.painterly


classes = (PainterlyRenderSettings,)


def register() -> None:
    """Register the property group; its ``register()`` classmethod attaches it to the scene."""
    from bpy.utils import register_class

    register_class(PainterlyRenderSettings)


def unregister() -> None:
    """Undo :func:`register`; ``unregister_class()`` calls the class's ``unregister()`` first."""
    from bpy.utils import unregister_class

    unregister_class(PainterlyRenderSettings)
