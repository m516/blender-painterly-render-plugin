"""Registering the add-on makes ``PAINTERLY`` a render engine that a scene can select."""

from __future__ import annotations

from types import ModuleType

import bpy


def registered_engine_ids() -> set[str]:
    """The ``bl_idname`` of every registered ``bpy.types.RenderEngine`` subclass.

    Blender's own ``HydraRenderEngine`` declares no ``bl_idname``, so the attribute is read with
    ``getattr``.
    """
    ids = set()
    for cls in bpy.types.RenderEngine.__subclasses__():
        bl_idname = getattr(cls, "bl_idname", None)
        if bl_idname is not None:
            ids.add(bl_idname)
    return ids


def test_engine_is_registered(addon: ModuleType) -> None:
    assert "PAINTERLY" in registered_engine_ids()


def test_the_registered_engine_is_the_addons_class(addon: ModuleType) -> None:
    assert addon.PainterlyRender.bl_idname == "PAINTERLY"
    assert addon.PainterlyRender in bpy.types.RenderEngine.__subclasses__()


def test_a_scene_can_select_the_engine(addon: ModuleType) -> None:
    """``scene.render.engine`` is an enum of the registered engines, so this proves registration."""
    scene = bpy.context.scene
    previous = scene.render.engine
    try:
        scene.render.engine = "PAINTERLY"
        assert scene.render.engine == "PAINTERLY"
    finally:
        scene.render.engine = previous
