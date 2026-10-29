# B10 — Image export and experiment X-colour (drafted from BRIEF.md section 2, "B10")

Milestone: M6b · Depends on: B9 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B10" (lines 257-265), per that brief's section 4
(lines 303-324) and the decisions of its section 1 that touch it: decision 4 (:38-39, the Cycles host scene owns the
image manager) and decision 9 (:78-79, every expected value is an exact equality). Code facts are
`docs/handoff/drafts/M6b/FACTS.md` §3.6 (the image manager), §3.10 (`PainterlyScene` and the device update), §3.11 (the
pyi and `python.cpp`), §3.7 (build targets) and §5 row R5, re-read at this clone's HEAD in every file cited below. The
bpy and PyOpenColorIO facts are measured on this host with the project's `bpy` 5.2.2 and with Blender 5.2.2's own
Python by the probes in step 1, quoted with their output.

`BRIEF.md` gives B10 two jobs in this order: run experiment X-colour as card T6.8 pre-registered it, then write the
image export that X-colour's results decide (BRIEF.md:258-260). The card therefore stops after X-colour's `Results`
if a hypothesis is refuted: the export's colour-space class is what H2 measures, and writing the export first would
be deciding the experiment's outcome by hand (`## Open for Opus` 1).

## Goal

Experiment X-colour has run and its decision rules are evaluated, and the Blender sync can hand an image to the core:

- **X-colour runs first, as pre-registered** (BRIEF.md:258; T6.8:1721-1732). The card creates
  `experiments/NNN-<DATE>-colour/` with `README.md`, `classify.py`, `probe_blender.py`, `run.sh` and `results.json`
  (T6.8:1864), copies T6.8's three README sections into it verbatim before running anything (T6.8:1729), runs it in
  Blender 5.2.2, and records `H1`-`H4` with their observables and `supported` flags (T6.8:1877-1882). The Conclusion is
  a DRAFT and the row in `experiments/README.md` has status `draft` (T6.8:1883-1885; R7).
- **`sync/image.py` exports an image datablock**: `Image.pixels`, its colour-space class and its alpha association,
  turned into `Scene.add_image`'s arguments (BRIEF.md:259-260). The class is a Python port of Cycles'
  `detect_known_colorspace()` (upstream `util/colorspace.cpp:281-383`), because painterly has no OCIO and X-colour
  decides whether Blender's bundled PyOpenColorIO can supply the configuration (H1, T6.8:1768-1778).
- **B10 owns `add_image`** (BRIEF.md:261-262), the three pieces the brief names:
  - `Scene::image_manager` in the shim `Scene` (`src/cycles/shim/scene/scene.h`), which FACTS.md:218 records as absent
    ("No `image_manager`, no geometry, no `params`");
  - `PainterlyScene::add_image(const PainterlyImagePixels &, const ImageParams &) -> int`;
  - `Scene.add_image` in CONTRACT `src/blender/_painterly.pyi`, with its binding in `src/blender/python.cpp`.
  It also binds the manager's two kernel arrays (`image_textures`, `image_info`) into the Cycles globals at the device
  update, because the manager is B10's and T6.8:836-838 requires the binding "after the last `add_image()`"
  (`## Open for Opus` 2).
- **The round-trip tests are derived from X-colour's measured semantics** (BRIEF.md:263-264): a byte image exports
  the file's bytes exactly, a float image its float32 bits, and the alpha type is Blender's `Image.alpha_mode` mapped
  through the cast Cycles itself uses (`blender/shader.cpp:106-110`).

B10 adds no knob (decision 8, BRIEF.md:75-77): `add_image`'s defaults are Cycles' own `ImageParams` defaults
(`src/cycles/shim/scene/image.h:33-40`), and nothing in the kernel changes, so no image, no K and no parity test moves.

## Read first

- `CLAUDE.md` rules 1, 2, 3, 5 and 6 (scope; named knobs; PEP 8 with type hints and units; `python -I` for untrusted
  inputs; deterministic tests, `slow` above about 10 s); `AGENTS.md` "Expected values are evidence, not targets" and
  "Pre-registered experiments"; `CLAUDE.md:108` (experiments are numbered and dated in the order they run).
- `docs/handoff/drafts/M6b/BRIEF.md` lines 257-265 (this card's mandate), :38-39 (decision 4: the host scene owns the
  image manager), :75-79 (no new knob; expected values are evidence), :280-281 and :288 (batch 10 is the first caller
  of `add_image` and of `sync/image.py`), :295-301 (the open questions this card must not decide).
- `docs/handoff/drafts/M6b/FACTS.md` §3.6 (`src/cycles/shim/scene/image.h` with its four classes and the CONVERTED
  contract), §3.7 (`cycles_scene` holds `shim/scene/image.cpp`), §3.10 (`device_scene.cpp:92-304`, the strong guarantee
  and the commit), §3.11 (`_painterly.pyi` and `python.cpp`), §5 row R5 ("colour-space classification must come from
  Python"), §6 gap 9 (X-colour's number is unassigned).
- Card T6.8's pre-registration in full: `docs/handoff/drafts/M6a/T6.8-svm-images.md:1721-1732` (who runs X-colour, and
  the substitution rule at :1730-1731), `:1734-1886` (the README text to copy verbatim: title, Background, Hypothesis
  H1-H4, the measurements, Method steps 1-5), `:836-838` (bind `image_textures`/`image_info` after the last
  `add_image()`), `:839-851` (what M6b adds to sample images, `Scene::image_manager` first), `:24` and `:119-127` and
  `:146-147` (the two host classes and the Python export are M6b's), `:176-178` (H4(f)'s known deviation).
- The image manager this card binds, read in full: `src/cycles/shim/scene/image.h` — `ImageParams` `:33-40`,
  `PainterlyImageColorSpace` `:46-77` (the CONVERTED caller contract is `:57-75`), `PainterlyImagePixels` `:82-101`
  (row 0 at `v = 0`, `:95-98`), `PainterlyImageMetaData` `:106-116`, `ImageHandle` `:122-151` (`kernel_id()` `:132-135`),
  `ImageManager` `:162-216` (`add_image` `:175`, `metadata` `:189`, `get_image_textures` `:195-198`,
  `get_image_info` `:199-202`, "Not thread safe" `:160-161`).
- `src/cycles/shim/scene/image.cpp`: `conform_pixels` `:104-115` (associate, then ignore, then zero the non-finite
  pixels, in that order), `invalid_pixels_reason` `:119-141` (what makes an image missing), `add_image` `:149-254` —
  `ImageMetaData::finalize()` `:173-197` (the storage type, `is_compressible_as_srgb`, `is_unassociated_alpha`),
  the storage switch `:204-227` (a CONVERTED byte source becomes `HALF4` `:210-220`), `KernelImageTexture`/`KernelImageInfo`
  `:229-245`, the handle `:247-254` — and `metadata()` `:256-263`.
- `src/cycles/shim/scene/scene.h` (the shim `Scene`, which this card gives its `image_manager`): `DeviceScene` `:31-38`,
  `Scene` `:45-63` (`lookup_tables` `:47`, `shaders` `:49`, `shader_manager` `:50`, `dscene` `:51`, `~Scene` `:57-62`).
- `src/cycles/shim/kernel/device/cpu/globals.h`: `kernel_array` `:31-45`, `KernelGlobalsCPU` `:49-57` (`data` `:54`),
  `KernelGlobals` `:59`, `kernel_data_fetch` `:62`.
- `src/painterly/scene/scene.h` (`:34-42` the members, `:88-92` `set_background`/`add_sun`, `:99-103` `device_update`),
  `src/painterly/scene/scene.cpp` (`:21-33` `clear`, `:139-142` `set_background`, `:145-158` `add_sun`/`set_spiral_object`),
  `src/painterly/scene/device_scene.cpp` (`:68-86` `bind_globals`, `:87-90` `globals`, `:92-97` the strong guarantee,
  `:289-303` the commit), `src/painterly/scene/svm/shader_manager.h` (`:48` `background_shader`, `:143-152`
  `bind_kernel_globals`), `src/painterly/scene/CMakeLists.txt:6-13` (the library `device_scene.cpp` belongs to).
- CONTRACT header `src/blender/_painterly.pyi` (read it, never edit it before dispatch: `:4` is
  `CONTRACT: Opus-owned`): `:7` (indices are dense from 0), `:41-43` (`LobeKind`, `Lobe`), `:45-47` (`class Scene`),
  `:49-54` (`add_material`), `:76-82` (`add_mesh`, the array-argument style this card copies), `:111` (`set_background`),
  `:124-126` (`set_integrator`/`get_integrator`).
- `src/blender/python.cpp`: `cast_array` `:506-517`, `matrix_from_python` `:519-533`, `lobe_kind_from_python`
  `:534-553` (the string-to-enum pattern with a `nb::value_error`), `sphere_intersection_from_python` `:556-568`, `double3_from_python` `:589-599`, `bind_module`
  `:682`, `nb::class_<PainterlyScene>` `:694`, `add_material` `:697-720`, `add_mesh` `:777-800`, `set_background`
  `:884-889`, `NB_MODULE` `:1001-1003`.
- The tests this card extends or must keep unchanged: `tests/core/test_api_contract.py` (`_pyi_public_api` `:65-82`,
  `test_every_public_name_and_parameter_matches_the_pyi` `:141`, `test_every_public_default_matches_the_pyi` `:151`;
  31 `test_` functions, none parametrized), `tests/conftest.py:19-28` (`PAINTERLY_BUILD_DIR`), `tests/blender/conftest.py`
  `:21-33` (`ADDON_DIR`, `MODULE_DIR`, `HAS_BPY`), `:44-56` (the add-on loaded as the package `painterly`, so a test
  imports `painterly.sync.image`), `:62-73` (the `addon` fixture).
- `src/test/CMakeLists.txt:46-62` (the `painterly_tests` sources) and `:97-99` (T6.8's block, the last one, which this
  card's block follows); `Makefile:73-74` (`test-blender`), `:110` (`check`); `pyproject.toml` `:38` (`testpaths`),
  `:40` (`slow`), `:43-44` (ruff `line-length = 100`).
- `experiments/README.md:6-20` (the index this card adds a row to), `:22-58` (how a run is invoked; `:27-29` **do not
  run `make oracle`**), `:60-64` (the five README sections).
- Upstream, read in the pinned checkout (`MAIN/.cache/vendor/blender-v5.2.2/intern/cycles/`, never edited, not in this
  repo): `blender/image.cpp:46-94` (`BlenderImageLoader::load_metadata`: `is_unassociated_alpha = !is_float` `:62`, the
  colour space `:77-91`), `:96-133` (`load_float_pixels`), `:135-167` (`load_half_pixels`, `float_to_half_image` `:152`),
  `:169-192` (`load_byte_pixels`); `blender/shader.cpp:106-110` (`get_image_alpha_type`: a cast of `b_image.alpha_mode`),
  `:895-968` (`ShaderNodeTexImage`: `set_colorspace` `:914`, `set_alpha_type` `:915`, the builtin-image `add_image`
  `:935-947`); `scene/shader_nodes.cpp:308-317` (`ImageTextureNode::image_params()`: interpolation, extension and alpha
  type come from the node); `scene/scene.h:166` (`unique_ptr<ImageManager> image_manager`); `util/colorspace.cpp:171-206`
  (`colorspace_is_data`), `:281-383` (`detect_known_colorspace`, the function `classify.py` ports), `:385-448`
  (`is_builtin_colorspace`: the 256-value scan, crosstalk `1e-5f` at `:412-419`, `compare_floats` at
  `util/math_base.h:780`), `util/color.h:63-69` (`color_srgb_to_linear`) and `:319-326`
  (`color_srgb_to_linear_sse2`, the linear segment H4(c) uses); `kernel/device/cpu/image.h:54-58` (a byte texel is
  `b * (1 / 255)`), `:341-366` (row 0 at `v = 0`, `:365`); `util/types_image.h:20` (`KERNEL_IMAGE_NONE`), `:23-29`
  (`InterpolationType`), `:38-50` (`ImageDataType`), `:60-68` (`ImageAlphaType`), `:79-91` (`ExtensionType`), `:93-107`
  (`KernelImageInfo`), `:145-...` (`KernelImageTexture`).
- The measured facts of step 1, quoted there with their output: the `Image.alpha_mode` enum values, `Image.pixels`'
  round trip for a byte and a float image, its row order against a PNG file, the roles of Blender's configuration, and
  that `PyOpenColorIO` is importable inside Blender 5.2.2 and not in the project venv.

## Create

- `src/blender/addon/sync/image.py`
- `src/test/test_scene_image.cpp`
- `tests/core/test_add_image.py`
- `tests/blender/test_sync_image.py`
- the experiment directory `experiments/NNN-<DATE>-colour/` with `README.md`, `classify.py`, `probe_blender.py`,
  `run.sh` and `results.json` (T6.8:1864). `NNN` and `<DATE>` are chosen at run time by `CLAUDE.md:108`'s rule —
  numbered and dated in the order they run, so the next free number and the day of the run — and the card writes them
  into `## Commit` and the answer. Its `out/` subdirectory is git-ignored (`experiments/**/out/`, `.gitignore:12`).

## Modify

- `src/cycles/shim/scene/scene.h`: `#include "scene/image.h"` and the `image_manager` member of `## Interface` in
  `class Scene`, with its comment (`:45-63`).
- `src/painterly/scene/scene.h`: `#include "scene/image.h"` beside B2's `"scene/scene.h"` include, and the declaration
  of `add_image` of `## Interface` after `add_material` (`:50-52`), with its comment.
- `src/painterly/scene/scene.cpp`: the definition, after `add_material` (`:35-...`).
- `src/painterly/scene/device_scene.cpp`: the image binding of step 6, in the block that binds the Cycles arrays.
- `src/blender/_painterly.pyi` (CONTRACT, `:4`): the two type aliases and `Scene.add_image` of `## Interface`, after
  `add_mesh` (`:76-82`).
- `src/blender/python.cpp`: the `add_image` binding of step 7, after `add_mesh`'s (`:777-800`), and the conversion
  helpers it needs in the anonymous namespace beside `cast_array` (`:506-517`).
- `src/test/CMakeLists.txt`: `test_scene_image.cpp` in `painterly_tests`, in a block of its own after T6.8's
  (`:97-99`).
- `experiments/README.md`: the X-colour row in the index table (`:8-20`), status `draft` (T6.8:1884-1885).

## Do not touch

- `third_party/cycles/**` (vendored; `tools/vendor_sync.py` only) and `src/cycles/shim/scene/image.h` /
  `src/cycles/shim/scene/image.cpp`: T6.8's image manager, which this card binds and calls. T6.8:833 says a later card
  "may add members" and "never change these" — this card adds none.
- `src/cycles/shim/kernel/device/cpu/globals.h`, `src/painterly/kernel/**`: B1's and B2's CONTRACTs and the kernel.
  Nothing in the kernel changes.
- `src/painterly/scene/svm/shader_manager.h` (B2's), `src/painterly/kernel/integrator/path.h` (B4's),
  `src/painterly/kernel/svm/**` (B3's, B4's and B5's).
- `src/blender/addon/sync/__init__.py`, `sync/material.py`, `sync/world.py`, `sync/shader/**`: B8's, B7's and M5
  T5.1-T5.3's. `sync/image.py` has no caller in B10: batch 10's Image Texture node export is its first one
  (BRIEF.md:280-281, :288), and B10 does not wire it into `build_scene` (`## Open for Opus` 3).
- `tests/core/test_api_contract.py`: it must pass unchanged at its own 31 tests, because `_pyi_public_api` (`:65-82`)
  reads the pyi itself, so the new names, parameters and defaults are covered without an edit.
- `tests/core/test_cycles_svm_images.py` and `src/test/test_cycles_svm_images.cpp`: T6.8's 8 doctests stay at 8 and at
  122 assertions.
- `tests/blender/test_render_reference.py`, `test_properties.py`, `test_registration.py`, `test_ui_surface.py`,
  `tests/blender/conftest.py`: T4.2's and T4.3's tests and the fixture; the new test file needs no conftest change.
- `tests/core/test_oracle_parity.py`, `tests/core/test_triangle_path.py`: unchanged.
- `Makefile`, `pyproject.toml`, `src/blender/CMakeLists.txt`, `src/cycles/CMakeLists.txt`,
  `src/painterly/scene/CMakeLists.txt`: no new target, no new source of a library (`cycles_scene` already compiles
  `shim/scene/image.cpp`, `src/cycles/CMakeLists.txt:236-240`), no new flag, no new lint setting.
- `docs/handoff/drafts/M6a/T6.8-svm-images.md` and `docs/handoff/drafts/M6b/BRIEF.md`: the pre-registration and the
  mandate are read, never edited.
- `make oracle`: never run (R7; `experiments/README.md:27-29`). X-colour renders through Blender's Cycles only, and its
  renders are 4 x 4 px, so it needs no oracle at all (T6.8:1812-1817).

## Interface

CONTRACT (Opus writes this before dispatch): `src/blender/_painterly.pyi`. The brief leaves the signature open
(`Scene.add_image(...)`, BRIEF.md:262), so the declaration below is this draft's proposal, in the style of `add_mesh`
(`:76-82`) and `LobeKind` (`:41-43`); `## Open for Opus` 4 names the alternative.

    ImageColorspace = Literal["scene_linear", "scene_linear_srgb", "data", "converted"]
    # (types_image.h:60-68, lowercased: the alpha type of ImageParams, not Blender's alpha_mode spelling.)
    ImageAlphaType = Literal["unassociated", "associated", "channel_packed", "ignore", "auto"]
    ImageInterpolation = Literal["linear", "closest", "cubic", "smart"]      # types_image.h:23-29
    ImageExtension = Literal["repeat", "extend", "clip", "mirror"]           # types_image.h:79-91

    class Scene:
        ...
        # --- images for shader graphs (BRIEF.md:259-262) ---
        # `pixels` is (H, W, 4): uint8 for a byte image, float32 for a float image, row 0 at v = 0, which
        # is Blender's `Image.pixels` order (image.h:95-98). `colorspace` is the class of the image's
        # colour space (image.h:46-77); "converted" needs `converted`, the (H, W, 4) float32 pixels
        # converted to scene linear by the caller (image.h:57-75). `alpha_type` is ImageParams'
        # (image.h:33-40). Returns the image's index into the kernel array image_textures, dense from 0.
        # Raises TypeError for a wrong dtype or shape, ValueError for an unknown name or for `converted`
        # missing or given where it does not belong.
        def add_image(
            self,
            pixels: npt.NDArray[np.uint8] | npt.NDArray[np.float32],
            colorspace: ImageColorspace = "scene_linear",
            alpha_type: ImageAlphaType = "auto",
            interpolation: ImageInterpolation = "linear",
            extension: ImageExtension = "clip",
            converted: npt.NDArray[np.float32] | None = None,
        ) -> int: ...

The two array defaults are Cycles' own `ImageParams` defaults (`INTERPOLATION_LINEAR`, `EXTENSION_CLIP`,
`IMAGE_ALPHA_AUTO`, `image.h:35-37`), not new knobs (BRIEF.md:75-77); batch 10 passes a node's values
(`scene/shader_nodes.cpp:308-317`) and needs no pyi change for it. The five `Literal` names are the C++ enumerators'
own words with their prefix dropped (`image.h:48-76`, `types_image.h:23-29`, `:61-65`, `:80-89`), so one word names one
concept in C++ and in Python.

Not a CONTRACT, the C++ side this card adds:

    /* The image manager of the Cycles host scene (BRIEF.md:261; upstream scene/scene.h:166). Every image the
     * caller adds lives here, and the kernel arrays image_textures and image_info point into it. */
    unique_ptr<ImageManager> image_manager = make_unique<ImageManager>();

    /* An image for the shader graphs (BRIEF.md:259-262). Returns the index into the kernel array
     * image_textures, which is dense from 0 because every call adds one image (image.cpp:247-254). The pixels
     * are stored and conformed as ImageManager::add_image() does (image.h:170-175). Add images before a
     * device update: the kernel arrays point into the manager's vectors, which a later add_image() may move
     * (image.h:191-194). */
    int add_image(const PainterlyImagePixels &pixels, const ImageParams &params);

`src/blender/addon/sync/image.py`, the export batch 10 calls. It is `bpy`-aware but keeps every Blender lookup in
`export_image`, so `classify_colorspace` is a pure function of a colour-space name and a configuration:

    ImageColorspace = Literal["scene_linear", "scene_linear_srgb", "data", "converted"]

    def classify_colorspace(colorspace: str) -> ImageColorspace:
        """The class of `colorspace` in Blender's own configuration (upstream util/colorspace.cpp:281-383)."""

    def export_image(scene_core: Scene, image: bpy.types.Image) -> int:
        """Add `image` to `scene_core` and return its index (Scene.add_image's)."""

`classify_colorspace` raises `RuntimeError` naming `PyOpenColorIO` when the module is not importable: painterly's core
has no OCIO, and inside Blender 5.2.2 it is present (step 1's probe). `export_image` reads the pixels with
`pixels.foreach_get()` into a float32 array, rebuilds a byte image's bytes as `round(255 * p)` (T6.8:1792-1797),
maps `image.alpha_mode` through the table of step 8, and calls
`scene_core.add_image(pixels, colorspace=..., alpha_type=..., converted=...)` with no other argument.

## Steps

1. Preconditions. Each must hold; otherwise stop, commit nothing and report what you saw.
   - B9 landed and B8's sync exists: these print `1` each.
     ```
     grep -c 'def export_material' src/blender/addon/sync/shader/export.py
     grep -c 'def build_scene' src/blender/addon/sync/__init__.py
     ```
   - `add_image` is not there yet: this prints `0`.
     ```
     grep -c 'add_image' src/blender/_painterly.pyi
     ```
   - The image manager is T6.8's and unchanged: this prints `1`, `1` and `1`. (The first pattern is anchored:
     `class ImageManager` alone also matches the forward declaration `image.h:26` and the friend declaration
     `:150`.)
     ```
     grep -c '^class ImageManager {' src/cycles/shim/scene/image.h
     grep -c 'ImageHandle add_image(const PainterlyImagePixels' src/cycles/shim/scene/image.h
     grep -c 'target_sources(cycles_scene PRIVATE shim/scene/image.cpp)' src/cycles/CMakeLists.txt
     ```
   - `bpy` is importable and is 5.2.2: this prints `5.2.2 LTS`.
     ```
     .venv/bin/python -c "import bpy; print(bpy.app.version_string)"
     ```
   - The bpy facts steps 8 and 11 rest on. Save this probe as a file under `/tmp` and run it with
     `.venv/bin/python <file>`; it must print exactly the lines quoted after it (this card's measurement on bpy 5.2.2;
     the alpha table, the row order and the byte round trip of step 11 are derived from it):
     ```python
     """The bpy facts B10's export rests on, on bpy 5.2.2."""
     import os
     import struct
     import tempfile
     import zlib

     import bpy
     import numpy as np

     print("VERSION", bpy.app.version_string)
     print("ALPHA_MODE", [(i.identifier, i.value) for i in
                          bpy.types.Image.bl_rna.properties["alpha_mode"].enum_items])

     # T6.8:1870-1871's 3x2 PNG: top scanline first in the file, bottom row first in Image.pixels.
     TOP = [(255, 0, 0, 255), (0, 128, 255, 128), (7, 10, 13, 0)]
     BOTTOM = [(1, 2, 3, 255), (64, 128, 192, 255), (250, 251, 252, 254)]
     scanlines = b"".join(b"\x00" + bytes(c for px in row for c in px) for row in (TOP, BOTTOM))
     def chunk(tag, data):
         return (struct.pack(">I", len(data)) + tag + data
                 + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF))
     png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 3, 2, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(scanlines)) + chunk(b"IEND", b""))
     path = os.path.join(tempfile.mkdtemp(), "fixture.png")
     with open(path, "wb") as handle:
         handle.write(png)
     image = bpy.data.images.load(path)
     pixels = np.empty(len(image.pixels), np.float32)
     image.pixels.foreach_get(pixels)
     back = np.rint(pixels.astype(np.float64) * 255.0).astype(np.uint8).reshape(2, 3, 4)
     print("PNG_LOAD", tuple(image.size), "is_float", image.is_float, "channels", image.channels,
           "colorspace", image.colorspace_settings.name)
     print("ROW0_IS_THE_BOTTOM_SCANLINE", back[0].tolist() == [list(px) for px in BOTTOM])
     print("CHANNELS_DIFFERING_FROM_THE_FILE", int((back != np.array([BOTTOM, TOP], np.uint8)).sum()))
     print("BYTE_PIXEL_128", float(pixels[5]),
           "== float32(128)/float32(255):", bool(pixels[5] == np.float32(128.0) / np.float32(255.0)),
           "| BYTE_PIXEL_64", float(pixels[4]),
           "== float32(64)/float32(255):", bool(pixels[4] == np.float32(64.0) / np.float32(255.0)))

     float_image = bpy.data.images.new("float", 1, 1, alpha=True, float_buffer=True)
     values = np.array([0.1, 1 / 3, 65504.0, 0.5], np.float32)
     float_image.pixels.foreach_set(values)
     round_trip = np.empty(4, np.float32)
     float_image.pixels.foreach_get(round_trip)
     print("FLOAT_ROUND_TRIP_EXACT", bool(np.array_equal(round_trip, values)),
           "is_float", float_image.is_float, "alpha_mode", float_image.alpha_mode)

     try:
         import PyOpenColorIO  # noqa: F401
     except ModuleNotFoundError as error:
         print("PYOPENCOLORIO_IN_THE_VENV", type(error).__name__, error)
     print("HAS_is_data", hasattr(bpy.types.ColorManagedInputColorspaceSettings.bl_rna.properties,
                                  "is_data"))
     ```
     ```
     VERSION 5.2.2 LTS
     ALPHA_MODE [('STRAIGHT', 0), ('PREMUL', 1), ('CHANNEL_PACKED', 2), ('NONE', 3)]
     PNG_LOAD (3, 2) is_float False channels 4 colorspace sRGB
     ROW0_IS_THE_BOTTOM_SCANLINE True
     CHANNELS_DIFFERING_FROM_THE_FILE 0
     BYTE_PIXEL_128 0.501960813999176 == float32(128)/float32(255): True | BYTE_PIXEL_64 0.250980406999588 == float32(64)/float32(255): True
     FLOAT_ROUND_TRIP_EXACT True is_float True alpha_mode STRAIGHT
     PYOPENCOLORIO_IN_THE_VENV ModuleNotFoundError No module named 'PyOpenColorIO'
     HAS_is_data False
     ```
     What each line fixes:
     - `ALPHA_MODE` is Blender's own enumeration, and `blender/shader.cpp:106-110` casts it straight to
       `ImageAlphaType`, whose enumerators are `UNASSOCIATED = 0, ASSOCIATED = 1, CHANNEL_PACKED = 2, IGNORE = 3,
       AUTO = 4` (`util/types_image.h:60-68`). So the export's table is `STRAIGHT` → `"unassociated"`, `PREMUL` →
       `"associated"`, `CHANNEL_PACKED` → `"channel_packed"`, `NONE` → `"ignore"`, and `"auto"` is never produced from
       an image datablock: it is `ImageParams`' default only.
     - `ROW0_IS_THE_BOTTOM_SCANLINE True` and `CHANNELS_DIFFERING_FROM_THE_FILE 0` are H3's observable (a) already
       exact for this file (T6.8:1798-1807): `Image.pixels` exposes Blender's byte buffer, so `round(255 * p)` gives
       the file's bytes for all 24 channels, and row 0 of `Image.pixels` is the PNG's bottom scanline.
     - The two byte pixels equal `float32(b) / float32(255)`, which is what `read(uchar4)` computes with a different
       float operation (`kernel/device/cpu/image.h:54-58`: `b * (1/255)`); the export rebuilds `b`, not this value.
     - `FLOAT_ROUND_TRIP_EXACT True` is H3(c) for a float buffer: `Image.pixels` gives back the float32 bits that were
       set, including `65504.0` (the largest half) and `1/3`.
     - `PYOPENCOLORIO_IN_THE_VENV` and `HAS_is_data False` are why the class must come from a port of Cycles'
       classification rather than from bpy's RNA, and why step 8's converted path can only run inside Blender.
   - Blender 5.2.2's own Python has PyOpenColorIO and Blender's configuration. Run this probe with the executable
     `tools/fetch_blender.py --print-path-only` names (BACKLOG's `BLENDER` knob points at the same install); it must
     print exactly these lines:
     ```python
     import os
     import bpy
     import PyOpenColorIO as ocio

     config_path = os.path.join(bpy.utils.resource_path("LOCAL"), "datafiles", "colormanagement",
                                "config.ocio")
     config = ocio.Config.CreateFromFile(config_path)
     names = [item.identifier for item in
              bpy.types.ColorManagedInputColorspaceSettings.bl_rna.properties["name"].enum_items]
     print("OCIO_VERSION", ocio.__version__)
     print("ENUM_IDENTIFIERS", len(names))
     print("MISSING_FROM_CONFIG", [name for name in names if config.getColorSpace(name) is None])
     for role in ("scene_linear", "default_byte", "data"):
         space = config.getRoleColorSpace(role)
         print("ROLE", role, repr(space), "isData",
               config.getColorSpace(space).isData() if space else None)
     ```
     ```
     OCIO_VERSION 2.5.0
     ENUM_IDENTIFIERS 63
     MISSING_FROM_CONFIG []
     ROLE scene_linear 'Linear Rec.709' isData False
     ROLE default_byte 'sRGB' isData False
     ROLE data 'Non-Color' isData True
     ```
     This is the instrument H1 and H2 measure (T6.8:1772-1791), not their verdict: the verdicts come from
     `results.json` in step 3, and the export's tests quote the three role names only.
2. The experiment directory, before anything runs (T6.8:1729: the README text is copied in "before it runs anything").
   - `NNN` is the next free number (highest is 011, `experiments/README.md:20`) and `<DATE>` the day of the run
     (`CLAUDE.md:108`). Create `experiments/NNN-<DATE>-colour/`.
   - `README.md`: lines 1736-1885 of `docs/handoff/drafts/M6a/T6.8-svm-images.md` — the fenced block's 150 lines —
     with `NNN` and `<DATE>` replaced, and nothing else changed. Then the two sections T6.8:1883-1885 describes:
     `## Results` (filled in step 3) and `## Conclusion`.
   - `classify.py`: a loader plus a table. It loads `src/blender/addon/sync/image.py` by file path with
     `importlib.util.spec_from_file_location`, the way `tests/core/scenes.py:32-33` loads `sync/reference.py`, and
     prints one line per enum identifier of H1(c) with `classify_colorspace`'s class, then one line per role of
     `("scene_linear", "default_byte", "data")`. It imports `bpy` and `PyOpenColorIO` through the module, so it must run
     inside Blender. This is the substitution `## Open for Opus` 5 records: T6.8:1781-1785 says "`classify.py` ports
     `detect_known_colorspace()` with OCIO, line by line", and the port lives in the production module instead, so the
     experiment measures the code the export uses rather than a copy of it.
   - `probe_blender.py`: H1, H2, H3, H4's control, H4's configurations (a)-(e) and H4(f), in the order T6.8:1875-1876
     gives, with the observables, the scene and the predictions of T6.8:1768-1859. It writes `results.json` with
     T6.8:1877-1882's keys — `registration`, `run_date`, `blender_version`, `ocio_version`, `H1`, `H2`, `H3`, `H4`,
     `measurements` — each `H` with its observables and its `supported` flag, every float as its decimal value next to
     its float32 bit pattern in hex (T6.8:1882), and `json.dumps(..., indent=2, sort_keys=True)`. Every generated file
     goes under the experiment's `out/` (T6.8:1867).
   - `run.sh`: the invocation of T6.8:1868-1869 with one change — the executable comes from `$BLENDER` when it is set,
     as experiment 005's `run.sh` does (`experiments/005-2026-10-08-native-coexistence/run.sh`, the `BLENDER="${BLENDER:-…}"`
     line), because a worker clone has no `.cache/blender/` and BACKLOG's `BLENDER` knob points at the prepared install:
     ```sh
     BLENDER="${BLENDER:-$("$VENV_PY" "$REPO/tools/fetch_blender.py" --print-path-only)}"
     "$BLENDER" -b --factory-startup --python-exit-code 1 --python probe_blender.py -- results.json
     ```
     Nothing here renders through `painterly_analysis` and nothing needs the oracle (T6.8:1732).
3. Run X-colour and record it.
   - `sh experiments/NNN-<DATE>-colour/run.sh`. It must exit 0. If Blender exits non-zero, stop, change nothing and
     report the log: a broken instrument is not a result.
   - Read `results.json` and report each hypothesis's `supported` value with its deciding numbers. **Do not** interpret
     them: the Conclusion's first line is `DRAFT (DeepSeek) — pending Opus review.` and it gives each hypothesis as
     supported or refuted with the deciding numbers (T6.8:1883-1884; AGENTS.md; R7). The frozen text names Haiku in that
     line (`## Open for Opus` 6).
   - `experiments/README.md`: one row in the index table (`:8-20`), in the same five columns as the others: the number,
     the date, `colour`, H1-H4's question in one sentence (T6.8:1736), status `draft`, and a Conclusion cell that says
     the Conclusion is a draft (T6.8:1884-1885).
   - **If any of H1-H4 is refuted or inconclusive, stop here.** The export's class mapping is H2's outcome and its
     converted-class rule is H4(f)'s (T6.8:1848-1859); writing the export anyway would decide a pre-registered question
     by hand. Commit nothing, and report the verdicts with `report_blocked` (`## Open for Opus` 1).
4. `src/cycles/shim/scene/scene.h`: `#include "scene/image.h"` after `"scene/tables.h"` (`:18`) and the `image_manager`
   member of `## Interface` after `shaders` (`:49`), with the comment. The member is declared with an initialiser like
   `lookup_tables` (`:47`), so `Scene` needs no constructor, and it is declared after `shader_manager` (`:50`) and before
   `dscene` (`:51`) — the order BRIEF.md:38-39 gives — so the manager outlives nothing that reads it and `~Scene`
   (`:57-62`) is unchanged: `shader_manager->device_free` touches no image.
5. `src/painterly/scene/scene.h` and `scene.cpp`: the declaration of `## Interface` after `add_material` (`:50-52`) and
   its definition after `add_material`'s:
   ```cpp
   int PainterlyScene::add_image(const PainterlyImagePixels &pixels, const ImageParams &params)
   {
     /* The Cycles host scene is B2's `cycles_` (BRIEF.md:38-39); its image manager is the one this card adds. Every
      * call adds a new image (image.h:170-175), so kernel_id() is the count of images so far: dense from 0, which the
      * pyi promises (pyi:7). Invalid pixels give a missing image whose kernel_id() is still assigned (image.cpp:164-172,
      * :247-254), so a caller's index stays dense. */
     return cycles_->image_manager->add_image(pixels, params).kernel_id();
   }
   ```
   `cycles_` is B2's member (BRIEF.md:38); if B2 gave it another name, use that name and say so in the answer.
   `image_manager` is the member step 4 adds to the shim `Scene`, and `ImageHandle::kernel_id()` is
   `image.h:132-135`. No exception is thrown here: `ImageManager::add_image` reports invalid pixels through the log and
   returns a missing image (`image.cpp:164-172`), which is what `add_image`'s comment promises.
6. `src/painterly/scene/device_scene.cpp`: bind the manager's two kernel arrays into the Cycles globals that B2 fills,
   after `PainterlyShaderManager::bind_kernel_globals` (`shader_manager.h:143-152` — "after the last `add_image()`",
   T6.8:836-838) and before the commit (`:289-303`), so the strong guarantee is untouched:
   ```cpp
   /* The image arrays of the host scene's manager (T6.8:836-838). Bound here and not in the manager, because
    * the globals are the device scene's: KernelImageInfo::data points into the manager's pixel storage, which
    * stays valid until the manager is destroyed (image.h:191-194), and every device update rebinds, so an
    * image added after a previous update is seen by the next one. Every other image array stays empty. */
   KernelGlobalsCPU &cycles = /* the KernelGlobalsCPU B2 binds the shader arrays into */;
   cycles.image_textures.data = cycles_->image_manager->get_image_textures().data();
   cycles.image_textures.width = int(cycles_->image_manager->get_image_textures().size());
   cycles.image_info.data = cycles_->image_manager->get_image_info().data();
   cycles.image_info.width = int(cycles_->image_manager->get_image_info().size());
   ```
   The `KernelGlobalsCPU &` is the one B2's step uses for `bind_kernel_globals`; B1's Interface names
   `PainterlyDeviceScene::cycles_globals()` for the const read, so take whichever accessor B2's device update writes
   through, and say in the answer which. `test_cycles_svm_images.cpp:71-78` (`bind_images`) is the same four
   assignments, on a test's own globals. `KernelGlobalsCPU`'s arrays are `kernel_array<const T>`
   (`src/cycles/shim/kernel/device/cpu/globals.h:31-45`, `:49-57`), so a `const vector<T> &`'s `data()` assigns
   directly.
7. `src/blender/_painterly.pyi` and `src/blender/python.cpp`: the CONTRACT text of `## Interface`, and the binding after
   `add_mesh`'s (`:777-800`):
   - `nb::arg("pixels")`, `nb::arg("colorspace") = "scene_linear"`, `nb::arg("alpha_type") = "auto"`,
     `nb::arg("interpolation") = "linear"`, `nb::arg("extension") = "clip"`, `nb::arg("converted") = nb::none()`.
   - `pixels` is read with `cast_array<uint8_t>` or `cast_array<float>` (`:506-517`), chosen by the array's dtype;
     the shape must be 3-dimensional with `shape(2) == 4`, and `converted`, when not none, must be a `float32`
     `(H, W, 4)` array of the same `H` and `W` — each a `nb::type_error` naming the argument and the expected dtype or
     shape, in `add_mesh`'s wording (`:781-796`).
   - `PainterlyImagePixels`: `width = shape(1)`, `height = shape(0)`, `source_type = IMAGE_DATA_TYPE_BYTE4` for a
     `uint8` array and `IMAGE_DATA_TYPE_FLOAT4` for a `float32` one, `colorspace` from the string,
     `is_unassociated_alpha = source_type == IMAGE_DATA_TYPE_BYTE4` (Blender's own rule, `blender/image.cpp:62`), and
     `bytes` (widened to `uchar4`, row-major) or `floats` (`float4`) filled from the array, row 0 first.
   - The CONVERTED class takes `converted`'s floats as `floats` and leaves `bytes` empty, which is what
     `invalid_pixels_reason` requires of a converted source (`image.cpp:128-135`); a byte source's
     `source_type` still says `BYTE4`, which is what makes the manager store half floats (`image.cpp:180-183`).
     `converted` given for any other class, or missing for `"converted"`, is a `nb::value_error` naming both.
   - `ImageParams`: `interpolation`, `extension` and `alpha_type` from their strings, each a `nb::value_error` naming an
     unknown value (the pattern of `lobe_kind_from_python`, `:534-553`).
   - The binding returns `self.add_image(pixels, params)`. Everything stays in `bind_module`'s anonymous namespace
     (`:80-997`), so the module grows one method and no exported symbol: `exports.map:1` still exports
     `PyInit__painterly` alone.
8. `src/blender/addon/sync/image.py`:
   - `classify_colorspace(colorspace)` ports `ColorSpaceManager::detect_known_colorspace()`
     (upstream `util/colorspace.cpp:281-383`) in the order that function runs:
     - the four builtin names of `u_colorspace_*` map to their classes (`:321-326`, `util/colorspace.h:15-21`);
     - `colorspace_is_data()` (`:171-206`) → `"data"`;
     - then `is_builtin_colorspace()` (`:385-448`): the 256-value scan, with the crosstalk bound `1e-5f` at `:412-419`,
       `compare_floats(a, b, 1e-6f, 64)` at `:420-438` (`util/math_base.h:780`) and `color_srgb_to_linear`
       (`util/color.h:63-69`) at `:440-442`, whose bound is `1e-4f`;
     - a colour space in none of the three classes is `"converted"`.
     The configuration is `PyOpenColorIO.Config.CreateFromFile(os.path.join(bpy.utils.resource_path("LOCAL"),
     "datafiles", "colormanagement", "config.ocio"))`, which is H1(b)'s observable (T6.8:1774-1775); when the import
     fails, raise `RuntimeError("sync.image: PyOpenColorIO is not importable; the image colour space needs Blender's "
     "own Python")`. The file's docstring states the units and conventions: the class is a storage decision
     (`image.h:46-77`), not a display transform.
   - `export_image(scene_core, image)`:
     - `pixels = np.empty(len(image.pixels), np.float32); image.pixels.foreach_get(pixels)` and
       `pixels.reshape(height, width, 4)`, which keeps Blender's row order (step 1's probe: row 0 is the bottom
       scanline), so no flip;
     - a byte image (`image.is_float` false, step 1's probe) exports `np.rint(pixels.astype(np.float64) * 255.0)` as
       `uint8` (T6.8:1792-1797: `Image.pixels` holds `b / 255`, so `round(255 * p)` is the file's byte);
     - a float image exports the `float32` array unchanged (H3(c): the bits round-trip);
     - `colorspace = classify_colorspace(image.colorspace_settings.name)`;
     - `alpha_type` from `image.alpha_mode` through step 1's four-entry table, with a comment citing
       `blender/shader.cpp:106-110` and `util/types_image.h:60-68`;
     - for `"converted"`, the pixels converted to scene linear by `PyOpenColorIO`'s default CPU processor from the
       image's colour space to the role `scene_linear`, applied to RGBA with the alpha rules of `image.h:57-75`, passed
       as `converted`; the source pixels are still the array above, so a byte source stays a byte source.
     - It returns `scene_core.add_image(...)`. `image.is_float` and `image.alpha_mode` are the only bpy reads; the
       module is `bpy`-aware at module level for its hints, as `sync/shader/node_table.py` is (B8's step 2).
9. `src/test/test_scene_image.cpp` and `src/test/CMakeLists.txt`: three doctests, the count `## Acceptance` uses. They
   include `"painterly/scene/device_scene.h"`, `"painterly/scene/scene.h"`, `"scene/image.h"`,
   `"scene/scene.h"` and `<doctest/doctest.h>`, and build `PainterlyScene`s directly (as `test_scene.cpp` does).
   - **Case 1, `"painterly image: add_image returns dense indices and the device update binds the two arrays"`**
     (BRIEF.md:261-262, T6.8:836-838). Two images — a 2 x 2 byte one and a 1 x 1 float one — added to a scene:
     `CHECK(scene.add_image(byte_pixels, params) == 0)`, `CHECK(scene.add_image(float_pixels, params) == 1)`; then
     `scene.device_update(ds)` and, on `ds.globals().cycles` (B1's pointer), `CHECK(image_textures.width == 2)`,
     `CHECK(image_info.width == 2)`, `CHECK(image_textures.fetch(1).image_info_id == 1)`,
     `CHECK(image_info.fetch(1).data_type == IMAGE_DATA_TYPE_FLOAT4)` and
     `CHECK(image_info.fetch(1).width == 1)`. Every value is read from `image.cpp:229-245`'s writes, not measured.
   - **Case 2, `"painterly image: the colour space and the source type decide the stored type"`**. Four images on one
     scene, then a device update, then `image_info.fetch(i).data_type`: a byte image of class `SCENE_LINEAR` →
     `IMAGE_DATA_TYPE_BYTE4` (`image.cpp:205-208`); a float image of class `SCENE_LINEAR` → `IMAGE_DATA_TYPE_FLOAT4`
     (`:220-224`); a byte image of class `SCENE_LINEAR_SRGB` → `IMAGE_DATA_TYPE_BYTE4` with
     `image_textures.fetch(i).interpolation`/`extension` equal to the params' (`:229-231`); a byte source of class
     `CONVERTED` given as floats → `IMAGE_DATA_TYPE_HALF4` (`:180-183`, `:210-220`). The four `data_type` values are
     the four enumerators `finalize()` selects, so no value is invented.
   - **Case 3, `"painterly image: invalid pixels give a missing image and keep the indices dense"`**
     (T6.8:83-84, `image.h:82-85`). One valid image, then one with `width = 0`, then one valid image:
     `CHECK(scene.add_image(...) == 0)`, `CHECK(scene.add_image(empty, params) == 1)`,
     `CHECK(scene.add_image(...) == 2)`; after the device update `CHECK(image_textures.width == 3)`,
     `CHECK(image_info.width == 2)` (the missing image pushes no info, `image.cpp:164-172`) and
     `CHECK(image_textures.fetch(1).image_info_id == KERNEL_IMAGE_NONE)` (`util/types_image.h:20`).
   `src/test/CMakeLists.txt`: a block after T6.8's (`:97-99`), `target_sources(painterly_tests PRIVATE
   test_scene_image.cpp)`. No `target_link_libraries` line: `:48-50` already links `painterly_scene`, which B1 gives
   `cycles_scene` (`src/painterly/scene/CMakeLists.txt:13`, BRIEF.md:23-24).
10. `tests/core/test_add_image.py`, six tests on the built module. The fixtures are `numpy` arrays; the counts are this
    card's, and the file's docstring cites `## Interface`.
    - `test_add_image_returns_dense_indices`: two `add_image` calls on one `Scene` return `0` then `1` (`pyi:7`).
    - `test_add_image_accepts_a_byte_and_a_float_array`: a `(2, 2, 4)` `uint8` array and a `(1, 1, 4)` `float32` array
      each return their index; a `(H, W, 4)` array with one row also works, so `H == 1` is not a special case.
    - `test_add_image_rejects_a_wrong_dtype`: a `float64` array raises `TypeError` whose message names `pixels` and
      the two dtypes (`cast_array`, `python.cpp:506-517`).
    - `test_add_image_rejects_a_wrong_shape`: `(2, 2, 3)`, `(4, 4)` and a non-contiguous slice each raise `TypeError`
      naming the expected shape.
    - `test_add_image_requires_converted_pixels_for_the_converted_class`: `colorspace="converted"` without `converted`
      raises `ValueError` naming both; `converted` with `colorspace="data"` raises the same; `converted` of the wrong
      dtype raises `TypeError`.
    - `test_add_image_rejects_unknown_enum_names`: an unknown colour space, alpha type, interpolation and extension
      each raise `ValueError` whose message contains the offending string.
11. `tests/blender/test_sync_image.py`, six tests. They import `painterly.sync.image` (the `addon` fixture,
    `tests/blender/conftest.py:62-73`) and pass a recording fake `scene_core` that logs every call and its arguments,
    as B8's tests do (B8's step 14). `classify_colorspace` is monkeypatched in the four tests that are about the
    plumbing, because `PyOpenColorIO` is not importable in the project venv (step 1's probe) and the classifier itself
    is X-colour's subject (step 2's `classify.py`).
    - `test_a_byte_image_exports_the_file_bytes`: the 3 x 2 PNG of T6.8:1870-1871, written by the test with `zlib` and
      `struct` as step 1's probe writes it, loaded with `bpy.data.images.load`; `classify_colorspace` monkeypatched to
      return `"scene_linear_srgb"`. Expected: one `add_image` call whose `pixels` is `uint8`, shape `(2, 3, 4)`, equal
      to
      ```
      [[[1, 2, 3, 255], [64, 128, 192, 255], [250, 251, 252, 254]],
       [[255, 0, 0, 255], [0, 128, 255, 128], [7, 10, 13, 0]]]
      ```
      (the bottom scanline first, step 1's `ROW0_IS_THE_BOTTOM_SCANLINE True` and `CHANNELS_DIFFERING_FROM_THE_FILE 0`),
      and `colorspace="scene_linear_srgb"`, `alpha_type="unassociated"` (a byte buffer, `blender/image.cpp:62`;
      `STRAIGHT` is `0`, step 1's `ALPHA_MODE`), `converted=None`.
    - `test_a_float_image_exports_its_float32_bits`: a 1 x 1 float image set to `(0.1, 1/3, 65504.0, 0.5)`; expected
      `pixels` dtype `float32`, shape `(1, 1, 4)`, bit-equal to those four values (H3(c), step 1's
      `FLOAT_ROUND_TRIP_EXACT True`), and `alpha_type="unassociated"`, because a new float image's `alpha_mode` is
      `STRAIGHT` (step 1's `FLOAT_ROUND_TRIP_EXACT` line prints it), which maps to `"unassociated"` — a float buffer's
      alpha association is decided by the alpha type alone, not by the buffer
      (`image.cpp:186-197`).
    - `test_the_alpha_type_is_the_images_alpha_mode`: four 1 x 1 byte images with `alpha_mode` set to `STRAIGHT`,
      `PREMUL`, `CHANNEL_PACKED` and `NONE`; expected `"unassociated"`, `"associated"`, `"channel_packed"`,
      `"ignore"` — the identity cast of `blender/shader.cpp:106-110` against `util/types_image.h:60-68`, whose
      enumerator values are step 1's `ALPHA_MODE` values.
    - `test_a_converted_class_image_passes_the_converted_floats`: `classify_colorspace` monkeypatched to `"converted"`
      and the module's processor accessor monkeypatched to a function returning `2 * c` per channel; expected: the
      call's `pixels` is the source array unchanged and `converted` is exactly `2 * source` in `float32`, so the
      converted pixels are a separate argument and the source type is not lost.
    - `test_the_classifier_needs_pyopencolorio_and_names_it`: the module's PyOpenColorIO accessor monkeypatched to
      raise `ModuleNotFoundError`; `classify_colorspace("sRGB")` raises `RuntimeError` whose message contains
      `PyOpenColorIO`.
    - `test_export_image_returns_the_index_add_image_returned`: the fake returns `7`; `export_image` returns `7`.
12. `experiments/README.md`: the row of step 3 is in the file, and nothing else in it moves.
13. `.venv/bin/ruff format` on `src/blender/addon/sync/image.py` and the two new test files, then
    `.venv/bin/ruff check .`, then every acceptance command.

## Acceptance

Run every command from the repository root; the queue translates them with BACKLOG.md's table (`make check` → `CHECK`,
`make test-blender` → the same target with `KNOBS`, `build/dev` → `build/q`, `.venv/bin/<tool>` → `MAIN/.venv/bin/<tool>`,
any Python command prefixed with `PYTHONPATH="$PWD/analysis"`, a card's `python -I` → `-P -s`, `$BLENDER` → BACKLOG's
`BLENDER` knob).

1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and the audit's
   `RESULT: PASS` line. This card adds three doctests and no library, so the doctest case count rises by exactly 3 and
   the audit's exported symbols do not change.
2. `build/dev/src/test/painterly_tests --test-case='painterly image: *'` exits 0 and prints
   `test cases: 3 | 3 passed | 0 failed`: the three `TEST_CASE`s of step 9 and no others, because each name begins with
   exactly `painterly image: `.
3. `build/dev/src/test/painterly_tests --test-case='cycles svm images:*'` exits 0 and prints
   `test cases: 8 | 8 passed | 0 failed`: T6.8's eight, unchanged (`src/test/test_cycles_svm_images.cpp` holds eight
   `TEST_CASE`s). The image manager this card binds is the one those doctests pin.
4. `.venv/bin/python -m pytest -q tests/core/test_add_image.py` prints `6 passed`: the six tests of step 10. The count
   is the number of tests the card lists; another count is a finding, not a tolerance.
5. `.venv/bin/python -m pytest -q tests/blender/test_sync_image.py` prints `6 passed`: the six tests of step 11. Report
   its duration: `bpy` dominates the import and the fixtures write one 3 x 2 PNG and a few 1 x 1 images, so no test
   needs `@pytest.mark.slow` (CLAUDE.md rule 6); if the run exceeds about 10 s, the fixtures are too big and that is a
   finding.
6. `.venv/bin/python -m pytest -q tests/core/test_api_contract.py` prints `31 passed`: the file unchanged. The count is
   the file's own — 31 `test_` functions, none parametrized. `_pyi_public_api` (`:65-82`) walks the pyi's public names,
   so `Scene.add_image` is in it as soon as the pyi declares it, and its five defaults are compared with the module's
   (`:151`).
7. `sh experiments/NNN-<DATE>-colour/run.sh` exits 0 and writes `experiments/NNN-<DATE>-colour/results.json`. Report
   `H1`-`H4`'s `supported` values with their deciding numbers, `blender_version` and `ocio_version`.
8. The README's first 150 lines are T6.8's text, verbatim. Write the two literal values step 2 chose in place of
   `NNN` and `<DATE>` in the command below (four substitutions: two in the path, two in the `sed`); it then prints
   nothing and exits 0. `1736,1885` is T6.8's fenced block, 150 lines, from its `# Experiment NNN: ...` line to its
   `with status draft.` line:
   ```
   diff <(head -n 150 experiments/NNN-<DATE>-colour/README.md) \
        <(sed -n '1736,1885p' docs/handoff/drafts/M6a/T6.8-svm-images.md \
          | sed -e 's/NNN/NNN/g' -e 's/<DATE>/<DATE>/g')
   ```
   If `sed` reports a shorter range, the card's line numbers are stale and the current equivalent is the block between
   the two fence lines of T6.8's "README text" section (R2); say which range you compared.
9. `experiments/README.md` holds one row for the run, in the index table's five columns. Write the row's number and
   date in place of `NNN` and `<DATE>`; this prints `1` (`experiments/README.md` holds no other row with the slug
   `colour`, its `## Index` table's other cells name their slugs differently):
   ```
   grep -c '^| NNN | <DATE> | colour |' experiments/README.md
   ```
10. `git status --porcelain` lists only the Create paths and the eight Modify paths above.

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- return the image's index in `PainterlyScene::images` instead of `kernel_id()` → acceptance 2 fails on case 3, whose
  missing image keeps its `image_textures` entry but pushes no `image_info`;
- skip the four binding assignments of step 6 → acceptance 2 fails on cases 1 and 2 (`image_textures.width` stays 0);
- bind `image_info` before `image_textures` and stop → acceptance 2 fails on case 1's `image_textures.width == 2`;
- store a CONVERTED byte source as `FLOAT4` by giving it `source_type = IMAGE_DATA_TYPE_FLOAT4` in step 7 →
  acceptance 2 fails on case 2's `IMAGE_DATA_TYPE_HALF4`;
- flip the rows in `export_image` (`np.flipud`) → acceptance 5 fails on `test_a_byte_image_exports_the_file_bytes`
  only, because that is the only fixture with more than one row;
- export `float32(b) / float32(255)` bytes as `round(255 * p)` of the wrong array (e.g. of `image.pixels` before
  `foreach_get`) → acceptance 5 fails on the same test;
- map `NONE` to `"channel_packed"` → acceptance 5 fails on the alpha table test;
- pass the converted pixels as `pixels` instead of `converted` → acceptance 5 fails on the converted test;
- raise `ImportError` instead of `RuntimeError` when PyOpenColorIO is missing → acceptance 5 fails on the classifier
  test;
- accept a `float64` array in step 7 → acceptance 4 fails on the dtype test;
- add the default `colorspace="scene_linear"` to the pyi but not to the binding → acceptance 6 fails on the default
  comparison (`:151`), which is the pyi-and-binding-in-one-card rule.

Report: the doctest and pytest counts, the audit line, the four `supported` values with their numbers, the two test
files' duration, and every mutation you ran with its first failing check.

## Commit

`B10: image export and experiment X-colour: Scene.add_image, sync/image.py and the pre-registered X-colour run`

## Open for Opus

1. **X-colour's verdict gates the export, and the card stops after `Results` if one is refuted.** BRIEF.md:258-260
   orders the run before the export, and the export's class mapping is H2's outcome (T6.8:1779-1791) while its
   converted-class rule is H4(f)'s (T6.8:1848-1859). Step 3 therefore stops with `report_blocked` on a refuted or
   inconclusive H1-H4, having written `README.md`, `classify.py`, `probe_blender.py`, `run.sh`, `results.json` and the
   index row and nothing else. The options: (a) keep it (this card); (b) let the export proceed with the class of every
   image forced to `"converted"` (correct only if H1 holds, since it needs OCIO), which is what a refuted H2 would
   force anyway; (c) split the card into "run X-colour" and "write the export", which is K3's split and needs a second
   BACKLOG item. Opus's call.
2. **The brief does not say who binds the image arrays, and this card binds them in B10's device update.** T6.8:836-838
   requires the binding "after the last `add_image()`"; BRIEF.md:261-262 gives B10 the manager and `add_image` but names
   no binding step, and BRIEF.md:43-46 puts "the arrays the device scene binds itself" after `bind_kernel_globals`.
   This card takes the binding because it owns the manager, and step 6's four assignments are the only code it adds to
   `device_scene.cpp`. The alternative is batch 10, which would then carry a step into a file B10 has already touched.
3. **`sync/image.py` has no caller in B10.** BRIEF.md:259-260 says it "exports ... into `Scene.add_image(...)`", and
   BRIEF.md:280-281 and :288 make batch 10's Image Texture the first node that needs an image. This card therefore does
   not wire `export_image` into `build_scene` (B8's) and tests it directly. The alternatives: (a) keep it (this card);
   (b) have B8's material export add every image its trees reference, which needs B8's file and a decision about which
   images a material's tree can reach — that is batch 10's question, not this card's.
4. **`Scene.add_image`'s Python signature.** The brief leaves it as `add_image(...)` (BRIEF.md:262). This card proposes
   `pixels` plus `colorspace`, `alpha_type`, `interpolation`, `extension` and a separate `converted` array
   (`## Interface`). The two reasons for the separate array are the manager's two contracts: a CONVERTED byte source
   must keep `source_type = BYTE4` to be stored as half floats (`image.cpp:180-183`), and a converted source must give
   `floats` and no `bytes` (`:128-135`) — one array cannot carry both the source type and the converted values. The
   alternatives: (a) keep it (this card); (b) an explicit `source_type` parameter next to one array, which lets a caller
   lie about the source type; (c) two methods, `add_image` and `add_image_converted`, which doubles the binding. The
   `interpolation` and `extension` parameters are batch 10's (`scene/shader_nodes.cpp:308-317`) and are declared here so
   that batch 10 changes no pyi line.
5. **`classify.py` is a loader, not a second port.** T6.8:1781-1785 says "`classify.py` ports
   `detect_known_colorspace()` with OCIO, line by line"; this card puts the port in the production module
   (`src/blender/addon/sync/image.py`) and makes `classify.py` load that module by file path, as `tests/core/scenes.py`
   loads `sync/reference.py` (`:32-33`), so the experiment measures the code the export uses. The frozen README text is
   copied verbatim and Results records the substitution. The alternatives: (a) keep it (this card); (b) two copies of
   the port plus a test that compares their tables, which is a second implementation to keep in step; (c) move the port
   into a package the experiment can import, which needs a path outside this card's `allowedPaths`.
6. **The Conclusion's first line.** T6.8:1883 says it "starts with `DRAFT (Haiku) — pending Opus review.`", and
   `AGENTS.md` requires a worker's Conclusion to start with `DRAFT (DeepSeek) — pending Opus review.`. This card writes
   the AGENTS.md line and records the difference in Results. If Opus wants T6.8's literal text, it is one line of
   `README.md`, and the frozen block is not edited either way.
7. **`run.sh` takes Blender from `$BLENDER`.** T6.8:1868-1869 names the executable through
   `tools/fetch_blender.py --print-path-only`, which in a worker clone resolves to a `.cache/blender/` that does not
   exist (fetching is host-only, R1). Step 2 keeps the command as the fallback and prefers `$BLENDER`, as experiment
   005's `run.sh` does. The alternative is to copy T6.8's line verbatim and report the run "host-only, not run", which
   would leave X-colour unrun and the export undecided.
8. **The experiment's number and date are chosen at run time** (`CLAUDE.md:108`; FACTS.md:408 records that X-colour's
   number is unassigned). This card writes `NNN` and `<DATE>` in its Create list, step 2 and acceptance 7-8, and the
   answer names the two values it used.
9. **`image.h`'s "may add members" is not used.** T6.8:833 allows a later card to add members to the manager's types and
   forbids changing the existing ones. This card adds none: `Scene::image_manager`, `PainterlyScene::add_image` and the
   Python method need no new member, so T6.8's eight doctests stay exactly as they are (acceptance 3).
