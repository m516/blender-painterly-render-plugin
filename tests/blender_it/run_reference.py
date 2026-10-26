# SPDX-FileCopyrightText: 2026 The Painterly Authors
# SPDX-License-Identifier: GPL-3.0-or-later
"""Render the reference scene through the installed Painterly extension, inside Blender (T4.4).

Run by ``tests/blender_it/test_extension_it.py`` as::

    <blender> -b --factory-startup --python-exit-code 1 --python run_reference.py -- <out_dir>

Steps:

1. Enable the extension ``bl_ext.user_default.painterly`` and check that ``PAINTERLY`` is the
   ``bl_idname`` of a registered ``bpy.types.RenderEngine`` subclass. ``--factory-startup`` does not
   read the user preferences in which ``extension install-file -e`` enabled the extension, so
   without this step the engine is not registered and ``scene.render.engine`` cannot name it.
2. Set the engine, the reference scene, the chain ``image``, a 64×64 image, 4 passes, the
   ``scene_linear`` output mode and exposure 1.
3. Render, and save the Render Result as a float32 OpenEXR, which round-trips float32 exactly.
4. Write the pixels (bottom-up float32, Blender's row order) to ``<out_dir>/blender.npy`` and the
   metadata to ``<out_dir>/blender.json``. The metadata includes ``jitter``, the integrator socket
   ``scene.painterly.jitter``, which is the value the render passes to the core: reference mode
   keeps the user's jitter (T4.3), and only the smallpaint-unit knobs are overwritten.

The EXR is read back with ``bpy.data.images.load``, because Blender's ``Render Result`` exposes no
pixel buffer to Python (``tests/blender/test_render_reference.py`` reads it the same way).
"""

import json
import sys
from pathlib import Path

import addon_utils
import bpy
import numpy as np

# The extension's module name once `extension install-file -r user_default` installed it: the
# user_default repository's extensions live in the `bl_ext.user_default` namespace.
EXTENSION_MODULE = "bl_ext.user_default.painterly"

# The engine id of the add-on (src/blender/addon/__init__.py, PainterlyRender.bl_idname).
ENGINE_ID = "PAINTERLY"

# The card's render configuration: a 64 px square image, 4 passes, the scene_linear output mode at
# exposure 1, and the image chain (the whole image is one chain).
SIZE = 64
PASSES = 4
EXPOSURE = 1.0
CHAIN = "image"

# Blender 5.2's float32 OpenEXR color depth; "32" is float32, "16" half
# (tests/blender/test_render_reference.py names the same setting).
EXR_COLOR_DEPTH = "32"


def registered_engine_ids() -> set[str]:
    """The ``bl_idname`` of every registered ``bpy.types.RenderEngine`` subclass.

    Blender 5.2.2's own ``HydraRenderEngine`` declares no ``bl_idname``, so the attribute is read
    with ``getattr``: ``cls.bl_idname`` raises ``AttributeError`` for it.
    """
    ids = set()
    for cls in bpy.types.RenderEngine.__subclasses__():
        bl_idname = getattr(cls, "bl_idname", None)
        if bl_idname is not None:
            ids.add(bl_idname)
    return ids


def enable_extension() -> None:
    """Enable the installed extension, then check that its engine is registered.

    Raises:
        RuntimeError: if the extension does not load, or ``PAINTERLY`` is not a registered engine.
    """
    module = addon_utils.enable(EXTENSION_MODULE, default_set=True)
    if module is None:
        raise RuntimeError(f"addon_utils.enable({EXTENSION_MODULE!r}) returned None")
    ids = registered_engine_ids()
    if ENGINE_ID not in ids:
        raise RuntimeError(
            f"the extension loaded, but {ENGINE_ID} is not a registered RenderEngine; the "
            f"registered ids are {sorted(ids)}"
        )


def configure(scene) -> None:
    """Set the render settings of the card's step 2 on ``scene``."""
    render = scene.render
    settings = scene.painterly
    render.engine = ENGINE_ID
    settings.reference_scene = True
    settings.chain = CHAIN
    settings.passes = PASSES
    settings.output_mode = "scene_linear"
    settings.exposure = EXPOSURE
    render.resolution_x = SIZE
    render.resolution_y = SIZE
    render.resolution_percentage = 100
    # The float32 OpenEXR is what makes the read-back exact.
    render.image_settings.file_format = "OPEN_EXR"
    render.image_settings.color_depth = EXR_COLOR_DEPTH
    render.image_settings.color_mode = "RGBA"


def render_pixels(out_dir: Path, scene) -> np.ndarray:
    """Render, save a float32 EXR, and return the pixels as (H, W, 4) float32, bottom row first."""
    bpy.ops.render.render()
    exr_path = out_dir / "render-result.exr"
    bpy.data.images["Render Result"].save_render(str(exr_path), scene=scene)
    image = bpy.data.images.load(str(exr_path))
    try:
        if tuple(image.size) != (SIZE, SIZE):
            raise RuntimeError(f"the render is {tuple(image.size)}, not {SIZE}x{SIZE}")
        pixels = np.empty(image.size[0] * image.size[1] * image.channels, dtype=np.float32)
        image.pixels.foreach_get(pixels)
        return pixels.reshape(image.size[1], image.size[0], image.channels)
    finally:
        bpy.data.images.remove(image)


def main(argv: list[str]) -> int:
    """Render into ``argv[0]``, the output directory."""
    if len(argv) != 1:
        raise SystemExit("run_reference.py: expected exactly one argument, the output directory")
    out_dir = Path(argv[0]).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    enable_extension()
    scene = bpy.context.scene
    configure(scene)
    pixels = render_pixels(out_dir, scene)

    np.save(out_dir / "blender.npy", pixels)
    meta = {
        "engine": scene.render.engine,
        "extension": EXTENSION_MODULE,
        "size": SIZE,
        "passes": PASSES,
        "chain": CHAIN,
        "output_mode": scene.painterly.output_mode,
        "exposure": scene.painterly.exposure,
        # The value the render passes to the core: reference mode keeps the user's jitter.
        "jitter": scene.painterly.jitter,
        "shape": list(pixels.shape),
        "dtype": str(pixels.dtype),
    }
    (out_dir / "blender.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    # `--python file -- a b c`: everything after the "--" is in sys.argv.
    arguments = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    sys.exit(main(arguments))
