# N10 — Node batch 10: Image Texture (drafted from BRIEF.md section 2, "Node batches")

Milestone: M6b · Depends on: B3, B8, B9, B10 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "Node batches" (lines 274-293, batch 10 at `:280-281` and
`:288`), per that brief's section 4 (lines 303-324) and the decisions of its section 1 that touch it: decision 4
(`:38-51`, the Cycles host scene owns the image manager), decision 5 (`:52-57`, node types by Cycles type name, links
and linkable defaults by UI name, parameters by member name with enums by `NodeEnum` name), decision 6 (`:58-66`, the
`ShaderData` a painterly hit gets), decision 8 (`:75-77`, no new knob) and decision 9 (`:78-79`, every expected value is
an exact equality or a derived rule). Code facts are `docs/handoff/drafts/M6b/FACTS.md` §3.6 (`:245-251`, the image
manager), §3.13 (`:324-339`, batch 10's state at `:335-336`), §3.10 (`:291-301`, `PainterlyScene`), §3.7 (`:253-266`)
and §5 row R5, re-read at this clone's HEAD in every file cited below. The bpy facts are measured on this host with the
project's `bpy` 5.2.2 by the probe of step 1, quoted with its output.

`BRIEF.md:274-283` gives every node of the six core batches the same four bullets; this card turns each bullet into a
rule in `## Goal`, states for batch 10's node whether the bullet applies, and gives every expected value its
derivation. Its shape is batch 1's card (`docs/handoff/drafts/M6b/N1-batch-01-value-rgb-math.md`, the template
`BACKLOG.md:1062-1070` and FOLLOWUPS:93-94 name).

## Goal

Batch 10's node is exported, compiled and rendered through the whole M6b path, and it has a golden test against Cycles:

- **Rule 1: the node's evaluator is vendored, and this card adds nothing to `kernel/`** (BRIEF.md:276). For batch 10
  the bullet is already satisfied at HEAD: `NODE_TEX_IMAGE`, `NODE_TEX_IMAGE_DERIVATIVE`, `NODE_TEX_IMAGE_BOX`,
  `NODE_TEX_IMAGE_BOX_DERIVATIVE`, `NODE_TEX_ENVIRONMENT` and `NODE_TEX_ENVIRONMENT_DERIVATIVE` are vendored
  (`third_party/cycles/VENDORED.toml:4186-4231`), the switch lists all six (`src/cycles/svm_nodes.toml:114-119`) and
  the evaluator `kernel/svm/image.h` is vendored (`VENDORED.toml:1419-1420`) and included (`svm_nodes.toml:45`).
  `FACTS.md:335-336` says the same ("NODE_TEX_IMAGE*, NODE_TEX_ENVIRONMENT yes"). The rule is therefore a check, not a
  change: step 1's greps print the counts of step 1.
- **Rule 2: three host class fragments are missing, and this card extracts them** (BRIEF.md:277-281: "batch 10:
  `ImageSlotTextureNode`, `ImageTextureNode`, `EnvironmentTextureNode`, and the rest of the T6.8 list at `:839-851`
  that they need"). At HEAD none of the three has a fragment (`FACTS.md:335-336`: "ImageSlotTextureNode,
  ImageTextureNode, EnvironmentTextureNode missing (and `Scene::image_manager`)"). Step 1 counts 0 `VENDORED.toml`
  entries naming each. The classes' declarations come with `scene/shader_nodes.h` (`VENDORED.toml:835-836`:
  `ImageSlotTextureNode` at `third_party/cycles/scene/shader_nodes.h:81`, `ImageTextureNode` at `:105`,
  `EnvironmentTextureNode` at `:143`); what is missing is the out-of-line code, which is not one card's worth of
  vendoring and is why this card is **gated on T6.8's list**:
  - `ImageSlotTextureNode`'s two inline members are already in the header the tree vendored
    (`scene/shader_nodes.h:81-103`: the constructor sets `SHADER_SPECIAL_TYPE_IMAGE_SLOT`, `equals` compares the
    handle, `is_texture_node_and_needs_derivatives` calls `update_images`), so the class needs **no fragment** — only
    its subclasses' `update_images` do;
  - `ImageTextureNode`'s nine members (`scene/shader_nodes.cpp:295-531`): ctor `:295-299`, `clone` `:301-306`,
    `image_params` `:308-317`, `cull_tiles` `:319-381`, `attributes` `:383-396`, `shader_node_type` `:398-404`,
    `update_images` `:406-430`, `compile(SVMCompiler)` `:432-485`, `compile(OSLCompiler)` `:487-531`;
  - `EnvironmentTextureNode`'s eight members (`:574-674`): ctor, `clone`, `image_params`, `attributes`,
    `update_images`, the two `compile`s;
  - the rest of T6.8's `:839-851` list that they need, each a shim or a vendored member:
    `ImageHandle::metadata(Progress &)` with an `ImageMetaData` shim (`src/cycles/shim/scene/image.h:187-189` already
    has `PainterlyImageMetaData metadata(const ImageHandle &) const`, which is painterly's version of it),
    `ImageHandle::all_udim_tiled()`, the `tiles` overload of `add_image()`, `ImageParams::{animated, colorspace,
    frame}`, `ColorSpaceManager::colorspace_is_data()` and the `u_colorspace_*` names, and for `cull_tiles` the scene
    parameters, geometry and `UVMapNode` (`T6.8:839-851`).
  **This card does not decide what to do about that list**: `## Open for Opus` 1 records the two readings of
  `BRIEF.md:280-281` and the evidence, and step 3 is written for the narrower one — the node classes are extracted and
  the parts of T6.8's list that painterly's in-memory image manager already provides are used as they are, with the
  rest recorded as unsupported (step 3's last bullet).
- **Rule 3: `node_table.py` gains batch 10's one row** (BRIEF.md:282): `ShaderNodeTexImage` → `image_texture`. The
  trap of the batch is that **most of the node's parameters are not sockets at all**: `filename`, `colorspace`,
  `alpha_type`, `projection`, `interpolation`, `extension`, `projection_blend`, `animated`, `vector` and `tiles` are
  `NODE_SOCKET_API` members of `ImageTextureNode` (`scene/shader_nodes.h:124-140`), not `SOCKET_*` members of its
  `NodeType`, and Blender's node has no socket for any of them either (step 1's probe: one input, `Vector`). They are
  therefore the row's `parameters`, by member name, exactly as decision 5 says.
- **Rule 4: the node has a golden test that passes B9's rule** (BRIEF.md:283). One scene, added to B9's
  `GOLDEN_SCENES` (`B9-golden-harness.md:147`, `:241`): an emission plane whose Emission is driven by the node from a
  Texture Coordinate node (`BRIEF.md:239-246`), rendered by Cycles at 1 sample in Raw view as a float32 EXR and by
  painterly at `max_depth=1`, `emission_gain=1`, `jitter=0`, `output_mode="scene_linear"`
  (`B9-golden-harness.md:216-228`, `:261-268`), decided by B9's pre-registered rule (`B9-golden-harness.md:318-337`:
  `max |P - C| <= BAND`, `BAND = 2.0**-30`). This card contributes the scene and its exact exported list; it
  contributes no pixel expectation and no tolerance, because both sides of the comparison are renders and the rule is
  B9's (decision 9, `BRIEF.md:78-79`).
  B9's `## Open for Opus` 6 already names this batch as the one whose radiance range is much wider than the Texture
  Coordinate scene's (`B9-golden-harness.md:495-503`: "A later scene whose radiance range is much wider (an Image
  Texture's, batch 10) has a larger float32 spacing, so the same absolute band is looser for it"), so this card's
  scene keeps the image's values inside the range B9's band was measured on and `## Open for Opus` 2 records the
  choice.

Nothing in the core changes: no kernel type, no scene API, no new knob (decision 8, `BRIEF.md:75-77`), so no image, no
K and no parity test of M3-M5 moves. B10 owns `Scene.add_image`, `Scene::image_manager` and the two kernel arrays
(`BRIEF.md:261-262`, `B10-image-export-x-colour.md:31-37`), and this card calls them.

Which of the four bullets applies, per node (FACTS.md:335-336 is the current state of the row; the file:line column is
this clone's HEAD):

| node | Blender idname | Cycles type | 1. vendor the evaluator | 2. host class fragments | 3. `node_table.py` row | 4. golden test |
|---|---|---|---|---|---|---|
| Image Texture | `ShaderNodeTexImage` | `image_texture` | nothing to do: `NODE_TEX_IMAGE`/`_BOX` at `VENDORED.toml:4186`, `:4204`, `svm_nodes.toml:114-117`; `kernel/svm/image.h` at `VENDORED.toml:1419-1420` | **extract** `ImageTextureNode` (nine members, `scene/shader_nodes.cpp:295-531`) and `ImageSlotTextureNode`'s subclasses' `update_images`; `ImageSlotTextureNode` itself is header-only (`scene/shader_nodes.h:81-103`) | **add** | **add** |

So of the four bullets, bullet 1 applies to no part of this batch (a check, step 1), bullet 2 applies to the class
fragments (step 3), and bullets 3 and 4 apply (steps 2, 5-7).

## Read first

- `CLAUDE.md` rules 1, 2 and 3 (scope; named knobs; PEP 8 with type hints and docstrings that state units);
  `AGENTS.md` "Expected values are evidence, not targets" and "Measured means reproducible".
- `docs/handoff/drafts/M6b/BRIEF.md` lines 274-293 (this card's mandate; `:280-281` and `:288` are batch 10), `:38-51`
  (decision 4, the host scene's image manager), `:58-66` (decision 6), `:237-255` (B9's harness and rule), `:52-57`
  (the socket-name rule), `:75-79` and `:295-301` (the open questions).
- `docs/handoff/drafts/M6b/FACTS.md` §3.6 (`:245-251`: `ImageParams`, `PainterlyImageColorSpace`,
  `PainterlyImagePixels`, `PainterlyImageMetaData`, `ImageHandle`, `ImageManager`), §3.13 (`:335-336`, batch 10's
  line), §3.10 (`:291-301`), §3.7 (`:253-266`, `cycles_scene` holds `shim/scene/image.cpp`) and §5 row R5
  (`:379`: "colour-space classification must come from Python").
- `docs/handoff/drafts/M6b/N1-batch-01-value-rgb-math.md`: the table of `## Goal` (`:70-75`), the rows literal
  (`:186-204`), the getters (`:209-225`), the export literals of `## Steps` 5 (`:540-567`), the guard test's new
  expected set (`:594-608`) and `## Acceptance` (`:612-634`).
- `docs/handoff/drafts/M6b/B10-image-export-x-colour.md`: the CONTRACT `add_image` (`:176-208`), the C++
  `Scene::image_manager` and `PainterlyScene::add_image` (`:210-222`), `sync/image.py`'s `classify_colorspace` and
  `export_image` (`:224-239`) and X-colour's rule that the export is written only after the experiment runs
  (`:15-18`).
- `docs/handoff/drafts/M6b/B8-node-table-export.md`: `NodeRow` and the six names `node_table.py` exports (`:172-201`),
  B8's three rows (`:390-407`), the socket ladders (`:422-457`), `export_graph` (`:485-509`), the row-vs-definition
  regexes (`:574-589`) and the guard test a batch card must change (`:595-598`).
- `docs/handoff/drafts/M6b/B6-shader-graph-api.md`: the two methods (`:96-109`), the nine parameter socket types and
  the `STRING` form (`:166-176`, `:216`), the `ENUM` form and its `NodeEnum::exists` check (`:220-221`), and the "no
  Python form" `ValueError` (`:221-222`).
- `docs/handoff/drafts/M6b/B9-golden-harness.md`: the harness's public names (`:135-151`), the scene `build`
  (`:216-244`), the rule (`:318-337`), the slow test (`:338-357`) and `## Open for Opus` 6 (`:495-503`, the per-scene
  band question this batch raises).
- Card T6.8's decisions in full: `docs/handoff/drafts/M6a/T6.8-svm-images.md:115-200` (decisions 1-6, including
  decision 1's sentence that "M6b, which owns the Blender sync, extracts them" at `:123-127`), `:836-851` (what M6b
  adds) and `:146-147` (the Python export decides class and pixels).
- `src/cycles/shim/scene/image.h`: `ImageParams` `:33-40`, `PainterlyImageColorSpace` `:46-77`,
  `PainterlyImagePixels` `:82-101`, `PainterlyImageMetaData` `:106-116`, `ImageHandle` `:122-151` and `ImageManager`
  `:162-216` (`add_image` `:175`, `metadata` `:189`, `get_image_textures` `:195`, `get_image_info` `:199`,
  `get_use_texture_cache` `:203-206`).
- `third_party/cycles/scene/shader_nodes.h:63-103` (`TextureNode`'s `tex_mapping` members and `ImageSlotTextureNode`)
  and `:105-160` (`ImageTextureNode`'s and `EnvironmentTextureNode`'s `NODE_SOCKET_API` lists) — the members step 2's
  getter reads.
- `third_party/cycles/kernel/svm/image.h:47-77` (`svm_node_tex_image_mapping`, `svm_node_tex_image`), `:79-176`
  (`svm_node_tex_image_box`) and `:178-207` (`svm_node_tex_environment_projection`,
  `svm_node_tex_environment`), the evaluator the compiled node reaches.
- `third_party/cycles/kernel/device/cpu/image.h:30-35` (`frac()`, the quirk T6.8 decision 6 pins) and
  `:341-366` (`kernel_image_interp`, the untiled path T6.8 decision 2 relies on).
- Upstream `intern/cycles/blender/shader.cpp`, read in the pinned checkout (never edited, not in this repo): the
  `ShaderNodeTexImage` case `:897-968` (`set_interpolation` `:904`, `set_extension` `:905`, `set_projection` `:906`,
  `set_projection_blend` `:907`, `get_tex_mapping` `:909`, `set_colorspace` `:914`, `set_animated` `:915`,
  `set_alpha_type` `:916`, the builtin-image `add_image` at `:928-963`) and `get_image_interpolation` `:93-99`,
  `get_image_extension` `:100-105`, `get_image_alpha_type` `:106-110`, `get_tex_mapping` `:277-297`.
- `tests/blender/conftest.py:22`, `:44-53` and `:62-73` (the add-on package and the `addon` fixture);
  `tests/blender_it/test_extension_it.py:53-64` (`_load_by_path`), `:76-101` (the skips) and `:149-154` (the isolated
  profile).
- `pyproject.toml:38-44` and `:48` (`testpaths`, `addopts`, the `slow` marker, ruff's `line-length` and
  `target-version`; `docs/handoff` is excluded from lint).
- The expected values of steps 1, 4 and 5: the probe quoted there, measured on this host with `bpy` 5.2.2.

## Create

- `tests/blender/test_sync_shader_batch_10.py`
- `tests/blender_it/golden_batch_10_scenes.py`
- `tests/blender_it/test_golden_batch_10.py`

`tests/blender_it/golden_batch_10_scenes.py` is a module, not a test: `--import-mode=importlib`
(`pyproject.toml:38-39`) collects only `test_*.py`, and the test file loads it by path with
`tests/blender_it/test_extension_it.py:53-64`'s `_load_by_path`.

## Modify

- `third_party/cycles/VENDORED.toml` and the new
  `third_party/cycles/fragments/scene/shader_nodes_cpp/{node_define,member}/Image*TextureNode*.inc` files of step 3 —
  **only** through `tools/vendor_sync.py`; a hand edit of `third_party/` is rejected by the auditor (R6).
- `src/blender/addon/sync/shader/node_table.py` (B8's file): batch 10's one row in `NODE_TABLE` (step 2), after B8's
  four and batch 1's four, and the module docstring's sentence about which rows exist updated to name this batch.
- `tests/blender/test_sync_shader_node_table.py` (B8's file): the guard test of
  `B8-node-table-export.md:595-598`, `test_the_table_has_only_the_rows_this_card_adds`, now expects nine idnames —
  B8's four plus batch 1's four plus this card's one (step 7).

## Do not touch

- `third_party/cycles/kernel/**`, `src/cycles/svm_nodes.toml`: rule 1 is satisfied at HEAD (step 1), and
  `third_party/` is `tools/vendor_sync.py`'s alone (R6).
- `src/painterly/**`: B10 owns `PainterlyScene::add_image` and the `image_manager` of the shim `Scene`
  (`BRIEF.md:261-262`, `B10-image-export-x-colour.md:31-37`), and B3 owns `painterly_svm_shader_setup` and the device
  scene's Cycles arrays. This card calls them and changes no line.
- `src/cycles/shim/scene/image.h`, `image.cpp`: T6.8's, and B10's `add_image` is built on them. A step that wanted to
  change the shim would mean T6.8's manager cannot serve a node, which is a `report_blocked`.
- `src/blender/addon/sync/image.py`: B10's. This card's scenes build their `bpy.data.images` in Blender's Python and
  call `export_image` (`B10-image-export-x-colour.md:231-233`); they change no line of it.
- `src/blender/addon/sync/shader/export.py`: B8's rule 4 is generic and this card's row is data only.
- B8's three rows, batch 1's four rows and the other batch cards' rows: not this card's.
- `src/blender/addon/sync/shader/flatten.py`, `src/blender/addon/sync/{__init__,material,world,geometry}.py`: B7's and
  B8's.
- `tests/blender_it/golden_scenes.py`, `golden_rule.py`, `render_golden.py`, `test_golden.py`: B9's. This card adds one
  module beside them and one `GOLDEN_SCENES` entry (`B9-golden-harness.md:241`).
- `tests/blender_it/test_extension_it.py` and `tests/blender_it/run_reference.py`: T4.4's.
- `Makefile`, `pyproject.toml`, `src/blender/CMakeLists.txt`, `src/test/CMakeLists.txt`: no new target, no new marker,
  no new C++ source.
- `NODE_TABLE` beyond this card's one row, and every other batch's golden scene.
- `docs/spec.md`, `docs/plan.md`, `CLAUDE.md`, `AGENTS.md`, `BACKLOG.md`, `docs/handoff/` beyond this card's own file.
- The X-colour experiment (`experiments/NNN-<DATE>-colour/`): B10's, and this card reads its Conclusion and writes
  none.

## Interface

Not a CONTRACT: this card adds no public name to `_painterly`, no Python API of the add-on and no C++ declaration. The
interfaces it uses are B8's (the row), B6's (the node tuple) and B10's (`Scene.add_image`).

**The one new row** (`src/blender/addon/sync/shader/node_table.py`, B8's `NodeRow`,
`B8-node-table-export.md:179-185`):

```python
NODE_TABLE: Final[Mapping[str, NodeRow]] = {
    # ... B8's four rows and batch 1's four, unchanged.
    # ImageTextureNode.inc:3-60. One linkable input, `Vector`, and two outputs. Every other member of
    # the node is a NODE_SOCKET_API parameter, not a socket (scene/shader_nodes.h:124-140): `filename`,
    # `colorspace`, `alpha_type`, `projection`, `interpolation`, `extension`, `projection_blend`,
    # `animated`, `vector`, `tiles`. Blender's node has the same one socket (step 1's probe).
    "ShaderNodeTexImage": NodeRow(
        "image_texture", ("Vector",), ("Color", "Alpha"), _image_texture_parameters),
}
```

The getter, which reads the node's `NODE_SOCKET_API` members from Blender's RNA:

```python
def _image_texture_parameters(node: bpy.types.Node) -> dict[str, object]:
    """Cycles' members of `ImageTextureNode` (scene/shader_nodes.h:124-140), by member name."""
    return {
        "filename": _image_filename(node.image),
        "colorspace": _image_colorspace(node.image),
        "alpha_type": _image_alpha_type(node.image),
        "projection": enum_name(node.projection),
        "interpolation": enum_name(node.interpolation),
        "extension": enum_name(node.extension),
        "projection_blend": float(node.projection_blend),
        "animated": False,
    }
```

- `_image_filename(image)` is `""` for an image Blender has no file for (`image is None` or `image.filepath == ""`);
  the row's own scene always has an image (step 5).
- `_image_colorspace(image)` and `_image_alpha_type(image)` are `sync/image.py`'s (`B10-image-export-x-colour.md:224-239`)
  in the sense that they read the same two properties, `image.colorspace_settings.name` and `image.alpha_mode`, and
  map them through the same tables: this card imports `classify_colorspace` from `sync.image` for the first and uses
  B10's alpha table for the second (`## Open for Opus` 3 names the alternative that B10 exports both).
- `animated` is `False`: Cycles' default (`ImageTextureNode.inc:53`) and Blender's for a single still image
  (`shader.cpp:915` sets it only for a movie or a sequence, and this card's scene uses a generated image).
- `vector` and `tiles` are not exported: `vector` is a `float3` member whose Blender source is the node's own `Vector`
  socket, which is a linkable input in Cycles too (`ImageTextureNode.inc:55`, `SOCKET_IN_POINT(vector, ...)`), and
  `tiles` is UDIM, which T6.8 decision 2 excludes ("Every handle is a single image (no UDIM)").

**What this card consumes from B10.** `Scene.add_image`'s CONTRACT declaration
(`B10-image-export-x-colour.md:176-208`), `sync/image.py`'s `classify_colorspace` and `export_image`
(`:224-239`), and `Scene::image_manager` (`:210-222`). B10's `## Open for Opus` 4 records that the `add_image`
signature is B10's proposal; if Opus changes it, only this card's step 5 call sites change and no expected value does.

**What this card consumes from B9.** `GOLDEN_SCENES: dict[str, Callable[[], bpy.types.Scene]]`
(`B9-golden-harness.md:147`), `build(**variant)` (`:144`), `render_golden.py`'s
`<out_dir>/{cycles.npy, painterly.npy, golden.json, <scene>.blend}` (`:166-177`) and `golden_rule.meets_rule` (`:163`).
This card adds one builder to its own module and one `GOLDEN_SCENES` entry; it calls no `assert_golden`, because B9's
drafted interface has no such function (`## Open for Opus` 4).

## Steps

1. Preconditions. Each must hold; otherwise stop, commit nothing and report what you saw.
   - B8 and batch 1 landed: this prints `1` for each.
     ```
     grep -c 'NODE_TABLE: Final' src/blender/addon/sync/shader/node_table.py
     grep -c 'def enum_name' src/blender/addon/sync/shader/node_table.py
     grep -c 'def export_graph' src/blender/addon/sync/shader/export.py
     grep -c 'def test_the_table_has_only_the_rows_this_card_adds' tests/blender/test_sync_shader_node_table.py
     ```
     and this prints `8`: B8's four idnames plus batch 1's four.
     ```
     grep -cE '"ShaderNode[A-Za-z]+": NodeRow\(' src/blender/addon/sync/shader/node_table.py   # 8
     ```
   - B10 landed: `add_image` is bound, the manager exists and the sync's image module is there. Each prints `1`.
     ```
     grep -c 'def add_image' src/blender/_painterly.pyi
     grep -c 'image_manager' src/cycles/shim/scene/scene.h
     grep -c 'def classify_colorspace' src/blender/addon/sync/image.py
     grep -c 'def export_image' src/blender/addon/sync/image.py
     ```
   - B3 landed: the hit's `ShaderData` exists, which is what `NODE_TEX_IMAGE` reads its `u`, `v` and `P` from. This
     prints `1`:
     ```
     grep -c 'painterly_svm_shader_setup' src/painterly/kernel/svm/shader_data.h
     ```
   - B9 landed, with the harness names of `## Interface`. Each prints `1`.
     ```
     grep -c 'GOLDEN_SCENES: dict' tests/blender_it/golden_scenes.py
     grep -c 'def meets_rule' tests/blender_it/golden_rule.py
     grep -c 'golden_rule' tests/blender_it/test_golden.py
     ```
   - Rule 1 holds — the six cases and the evaluator header are vendored. Each prints the number after it.
     ```
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_TEX_IMAGE"' third_party/cycles/VENDORED.toml               # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_TEX_IMAGE_DERIVATIVE"' third_party/cycles/VENDORED.toml    # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_TEX_IMAGE_BOX"' third_party/cycles/VENDORED.toml           # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_TEX_ENVIRONMENT"' third_party/cycles/VENDORED.toml         # 1
     grep -c 'dest = "kernel/svm/image.h"' third_party/cycles/VENDORED.toml                                     # 1
     grep -cE '^  "NODE_TEX_IMAGE",$|^  "NODE_TEX_IMAGE_BOX",$|^  "NODE_TEX_ENVIRONMENT",$' src/cycles/svm_nodes.toml   # 3
     ```
   - Rule 2 holds — the three classes have no fragment yet, so step 3 adds them. Each of these prints `0`:
     ```
     grep -c 'shader_nodes_cpp/member/ImageTextureNode\.' third_party/cycles/VENDORED.toml              # 0
     grep -c 'shader_nodes_cpp/member/EnvironmentTextureNode\.' third_party/cycles/VENDORED.toml        # 0
     grep -c 'shader_nodes_cpp/node_define/ImageTextureNode"' third_party/cycles/VENDORED.toml          # 0
     grep -c 'shader_nodes_cpp/node_define/EnvironmentTextureNode"' third_party/cycles/VENDORED.toml    # 0
     ```
     and these print `1` each, because the declarations are already vendored with `scene/shader_nodes.h`
     (`VENDORED.toml:835-836`):
     ```
     grep -c '^class ImageSlotTextureNode : public TextureNode' third_party/cycles/scene/shader_nodes.h   # 1
     grep -c '^class ImageTextureNode : public ImageSlotTextureNode' third_party/cycles/scene/shader_nodes.h  # 1
     grep -c '^class EnvironmentTextureNode : public ImageSlotTextureNode' third_party/cycles/scene/shader_nodes.h  # 1
     ```
   - The bpy facts rules 3 and 4 rest on. Save this probe as a file under `/tmp` and run it with
     `.venv/bin/python <file>`; it must print exactly the lines quoted after it (they are this card's measurement on
     bpy 5.2.2, and the row and the scene of steps 2 and 5 are derived from them):
     ```python
     import bpy

     mat = bpy.data.materials.new("probe")
     mat.use_nodes = True
     tree = mat.node_tree
     tree.nodes.clear()

     node = tree.nodes.new("ShaderNodeTexImage")
     print("teximage inputs ", [(s.identifier, s.type) for s in node.inputs])
     print("teximage outputs", [(s.identifier, s.type) for s in node.outputs])
     print("teximage defaults", [(s.identifier, tuple(s.default_value)) for s in node.inputs])
     print("teximage rna", sorted(p.identifier for p in node.bl_rna.properties
                                  if not p.is_readonly and p.identifier in (
                                      "image", "interpolation", "extension", "projection",
                                      "projection_blend")))
     print("teximage values", node.image, node.interpolation, node.extension, node.projection,
           node.projection_blend)
     print("interpolation items", [i.identifier for i in node.bl_rna.properties["interpolation"].enum_items])
     print("extension items", [i.identifier for i in node.bl_rna.properties["extension"].enum_items])
     print("projection items", [i.identifier for i in node.bl_rna.properties["projection"].enum_items])

     image = bpy.data.images.new("probe", 4, 4)
     node.image = image
     print("byte image: is_float", image.is_float, "alpha_mode", image.alpha_mode,
           "colorspace", image.colorspace_settings.name, "source", image.source,
           "filepath", repr(image.filepath), "pixels", len(image.pixels))
     image.pixels.foreach_set([0.125] * 64)
     print("byte image pixel 0", list(image.pixels)[0])

     floats = bpy.data.images.new("floats", 4, 4, float_buffer=True)
     floats.colorspace_settings.name = "sRGB"
     floats.pixels.foreach_set([0.125] * 64)
     print("float image: is_float", floats.is_float, "alpha_mode", floats.alpha_mode,
           "colorspace", floats.colorspace_settings.name, "pixel 0", list(floats.pixels)[0])
     print("alpha_mode items", [i.identifier for i in floats.bl_rna.properties["alpha_mode"].enum_items])

     env = tree.nodes.new("ShaderNodeTexEnvironment")
     print("texenv inputs ", [(s.identifier, s.type) for s in env.inputs])
     print("texenv outputs", [(s.identifier, s.type) for s in env.outputs])
     print("texenv values", env.interpolation, env.projection,
           [i.identifier for i in env.bl_rna.properties["projection"].enum_items])
     ```
     ```
     teximage inputs  [('Vector', 'VECTOR')]
     teximage outputs [('Color', 'RGBA'), ('Alpha', 'VALUE')]
     teximage defaults [('Vector', (0.0, 0.0, 0.0))]
     teximage rna ['extension', 'image', 'interpolation', 'projection', 'projection_blend']
     teximage values None Linear REPEAT FLAT 0.0
     interpolation items ['Linear', 'Closest', 'Cubic', 'Smart']
     extension items ['REPEAT', 'EXTEND', 'CLIP', 'MIRROR']
     projection items ['FLAT', 'BOX', 'SPHERE', 'TUBE']
     byte image: is_float False alpha_mode STRAIGHT colorspace sRGB source GENERATED filepath '' pixels 64
     byte image pixel 0 0.125490203499794
     float image: is_float True alpha_mode STRAIGHT colorspace sRGB pixel 0 0.125
     alpha_mode items ['STRAIGHT', 'PREMUL', 'CHANNEL_PACKED', 'NONE']
     texenv inputs  [('Vector', 'VECTOR')]
     texenv outputs [('Color', 'RGBA')]
     texenv values Linear EQUIRECTANGULAR ['EQUIRECTANGULAR', 'MIRROR_BALL']
     ```
     (bpy prints one `DeprecationWarning` about `use_nodes` on stderr; it is not part of the output above.)
     What each line fixes:
     - `ShaderNodeTexImage` has one linkable input, `Vector`, and two outputs, `Color` and `Alpha`, which are
       `ImageTextureNode.inc`'s `SOCKET_IN_POINT(vector, ...)` and `SOCKET_OUT_COLOR(color, ...)`/
       `SOCKET_OUT_FLOAT(alpha, ...)`.
     - the node's five settable RNA properties are `image`, `interpolation`, `extension`, `projection` and
       `projection_blend`, and Cycles has a member for each plus `filename`, `colorspace`, `alpha_type`, `animated`,
       `vector` and `tiles` (`scene/shader_nodes.h:124-140`). The five RNA names lowercase onto Cycles' enum names
       except `REPEAT`/`EXTEND`/`CLIP`/`MIRROR` and `FLAT`/`BOX`/`SPHERE`/`TUBE`, which are Cycles'
       `periodic`/`clamp`/`black`/`mirror` and `flat`/`box`/`sphere`/`tube` (`ImageTextureNode.inc:26-39`) — so the row
       needs four aliases per enum, which `ENUM_ALIASES` does not have (`## Open for Opus` 5).
     - `interpolation`'s identifiers are `Linear`, `Closest`, `Cubic` and `Smart` (mixed case) where Cycles' are
       `linear`, `closest`, `cubic`, `smart` (`ImageTextureNode.inc:19-24`), so `enum_name`'s `.lower()` is what maps
       them and no alias is needed for that enum.
     - a generated 4x4 image is a byte image (`is_float False`) whose colour space is `sRGB`, and a generated
       `float_buffer=True` image is a float image (`is_float True`) whose colour space is `Linear Rec.709` until it is
       set; both have `alpha_mode` `STRAIGHT`, `filepath` `''` and `4 * 4 * 4 = 64` floats in `pixels`. A byte image
       stores `0.125` as `0.125490203499794` (`round(0.125 * 255) = 32` bytes, read back as `32 / 255`), and a float
       image stores it exactly as `0.125`. Those facts are what step 5's scene and B10's export read, and they are why
       the scene uses a float image.
     - `Environment Texture` has the same one input, `Vector`, and **one** output in bpy 5.2.2, `Color`, where Cycles'
       own `NODE_DEFINE(EnvironmentTextureNode)` declares `SOCKET_OUT_COLOR(color, ...)` and
       `SOCKET_OUT_FLOAT(alpha, ...)` (upstream `intern/cycles/scene/shader_nodes.cpp:568-569`, in the pinned checkout;
       the class's fragments are not vendored, step 1): the alpha output is Blender's own difference, and it is one more
       reason this card adds no row for that node (`## Open for Opus` 7). Batch 10's other vendored evaluator
       (`NODE_TEX_ENVIRONMENT`) is reached by a row that would name `Color` alone.
2. `node_table.py`, the one new row of `## Interface`, transcribed from the vendored definition: `cycles_type` is
   `NodeType::add`'s first argument (`ImageTextureNode.inc:3`), `inputs`/`outputs` are the `SOCKET_IN_*`/`SOCKET_OUT_*`
   UI names in file order, and the parameters are the `NODE_SOCKET_API` members a caller sets
   (`scene/shader_nodes.h:124-140`). Measured, from step 1's probe and the file:
   ```
   ShaderNodeTexImage: 'image_texture', inputs=['Vector'], outputs=['Color', 'Alpha']
   ```
   - the row's `parameters` getter returns the eight members of `## Interface`. `vector` and `tiles` are excluded for
     the reasons given there.
   - `image_params` (`ImageTextureNode.image_params`, `scene/shader_nodes.cpp:308-317`) is what turns five of those
   members into `ImageParams`: `animated`, `interpolation`, `extension`, `alpha_type`, `colorspace`. This card's row
   exports all five by their member names, which is decision 5's rule; the conversion into an `ImageParams` is the
   node's own code once it is compiled (`ImageTextureNode::update_images`, `:406-430`).
   - The docstring states rule 3, the file the row comes from and that a row's `cycles_type` is a Cycles type name, not
     a Blender idname (decision 5, BRIEF.md:52-55), and the sentence about which rows exist now names batch 10's one
     beside B8's four and batch 1's four.
3. The class fragments, through `tools/vendor_sync.py` only (R6). The commands are `T6.7:2637-2643`'s shape, and the
   anchors are the ones `tools/vendor_sync.py list-anchors scene/shader_nodes.cpp` prints (the upstream line numbers
   in the table above are the same anchors' ranges):
   ```
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp node_define \
       ImageTextureNode EnvironmentTextureNode
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp member \
       ImageTextureNode::ImageTextureNode ImageTextureNode::clone ImageTextureNode::image_params \
       ImageTextureNode::attributes ImageTextureNode::shader_node_type ImageTextureNode::update_images \
       EnvironmentTextureNode::EnvironmentTextureNode EnvironmentTextureNode::clone \
       EnvironmentTextureNode::image_params EnvironmentTextureNode::attributes \
       EnvironmentTextureNode::update_images
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp member \
       ImageTextureNode::compile EnvironmentTextureNode::compile --params SVMCompiler
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp member \
       ImageTextureNode::compile EnvironmentTextureNode::compile --params OSLCompiler
   ```
   - Two `node_define` fragments and fifteen member fragments: `ImageTextureNode`'s nine (ctor, `clone`,
     `image_params`, `cull_tiles`, `attributes`, `shader_node_type`, `update_images` and the two `compile`s) and
     `EnvironmentTextureNode`'s eight, of which the two `compile`s need `--params` to be told apart. This prints the
     counts after the commands:
     ```
     grep -c 'shader_nodes_cpp/member/ImageTextureNode\.' third_party/cycles/VENDORED.toml        # 9
     grep -c 'shader_nodes_cpp/member/EnvironmentTextureNode\.' third_party/cycles/VENDORED.toml  # 8
     grep -c 'shader_nodes_cpp/node_define/ImageTextureNode"' third_party/cycles/VENDORED.toml    # 1
     grep -c 'shader_nodes_cpp/node_define/EnvironmentTextureNode"' third_party/cycles/VENDORED.toml  # 1
     ```
   - **What this card does not extract, and why the node still compiles.** `ImageTextureNode::update_images`
     (`:406-430`) and `cull_tiles` (`:319-381`) read `compiler.scene->image_manager`,
     `compiler.scene->params.background`, `compiler.scene->geometry`, `Geometry::get_used_shaders()` and `UVMapNode`
     (`T6.8:119-127`, `:839-851`). Painterly's shim `Scene` has `image_manager` after B10
     (`B10-image-export-x-colour.md:210-222`) but no `params` and no `geometry` (`FACTS.md:218`: "No `image_manager`,
     no geometry, no `params`"), so `update_images` and `cull_tiles` do not compile against the shim as it stands.
     The two ways out are `## Open for Opus` 1's: (a) this card vendors the fragments and adds the two shim members
     they need (`Scene::params` with `background`, and a `Scene::geometry` that is empty), which is a change to
     `src/cycles/shim/scene/scene.h`; or (b) this card vendors only the members the compile path needs and sets each
     node's `handle` from `Scene.add_image` before the device update, as Blender's own sync does for builtin images
     (`shader.cpp:928-963`, quoted at `T6.8:841-844`: "Blender's own sync sets `ImageSlotTextureNode::handle` directly
     for builtin images ... which painterly can do for every image with `add_image()` above"). Step 5 is written for
     (b), because it needs no shim change and it is what T6.8 recommends; the fragments of (a) that (b) does not need
     (`cull_tiles`, and `update_images`' cache branches) are not vendored, and the count above is (b)'s.
4. `tests/blender/test_sync_shader_batch_10.py`, five tests. `bpy` only, no Blender run, no `.blend` on disk outside
   `tmp_path`, and every expected value a literal compared with exact equality, so no tolerance appears.
   - `test_the_image_texture_row_is_the_vendored_node_definition`: parse `ImageTextureNode.inc` with B8's regexes
     (`SOCKET_IN_[A-Z0-9_]+\(\s*\w+\s*,\s*"([^"]+)"`, the `SOCKET_OUT_` form and `NodeType::add\("([a-z_]+)"`,
     `B8-node-table-export.md:574-589`) and compare with the row. Expected (step 2's table):
     ```
     ShaderNodeTexImage: 'image_texture', inputs=['Vector'], outputs=['Color', 'Alpha']
     ```
     The file declares more sockets the row does not name — the ten `SOCKET_STRING`/`SOCKET_ENUM`/`SOCKET_FLOAT`/
     `SOCKET_INT_ARRAY`/`SOCKET_BOOLEAN` parameters of `ImageTextureNode.inc:5-53` — and none matches the
     `SOCKET_IN_`/`SOCKET_OUT_` regexes, so the test asserts the filtered list and says so.
   - `test_the_image_texture_parameters_are_the_node_members`: on a fresh `ShaderNodeTexImage` the getter returns the
     eight members with `projection == "flat"`, `interpolation == "linear"`, `extension == "periodic"` (Cycles' names,
     `ImageTextureNode.inc:19-39`), `projection_blend == 0.0`, `animated is False`, and `filename == ""` because the
     node has no image; after `node.image = bpy.data.images.new("probe", 4, 4)` the last three become the image's own:
     a non-empty `colorspace` (Blender's `sRGB` mapped through `classify_colorspace`), `alpha_type == "unassociated"`
     (Blender's `STRAIGHT`), and `filename == ""` still, because a generated image has no file path (step 1's probe).
   - `test_the_image_texture_enums_are_cycles_node_enum_names`: the four `projection`, four `extension` and four
     `interpolation` identifiers map onto `ImageTextureNode.inc`'s names, with the four `ENUM_ALIASES` entries of
     `## Open for Opus` 5 and none for `interpolation`.
   - `test_the_image_texture_scene_exports_these_lists`: builds the scene with step 5's builder, writes it to
     `tmp_path` with `bpy.data.libraries.write`, loads it back with `bpy.data.libraries.load` and compares
     `export_graph(flatten_tree(tree))` with a literal. Measured, by running an implementation of steps 2 and 5 and
     B8's `export_graph` against bpy 5.2.2 (`## Open for Opus` 6):
     ```
     ([('texture_coordinate', {'from_dupli': False}, {}),
       ('image_texture',
        {'filename': '', 'colorspace': 'scene_linear_srgb', 'alpha_type': 'unassociated',
         'projection': 'flat', 'interpolation': 'linear', 'extension': 'periodic',
         'projection_blend': 0.0, 'animated': False},
        {}),
       ('emission', {}, {'Strength': 1.0})],
      [(0, 'UV', 1, 'Vector'), (1, 'Color', 2, 'Color'), (2, 'Emission', -1, 'Surface')])
     ```
     What the literal says: the node order is the tree's own (B7's walk, `B7-flatten.md:264-282`); `Vector` is linked
     from the Texture Coordinate's `UV` output, so no default is exported for it; the Emission's `Color` is linked, so
     only its `Strength` is; and `colorspace` is `scene_linear_srgb` because Blender's `sRGB` is that class
     (`B10-image-export-x-colour.md:176-177`'s four names).
   - `test_the_scene_adds_its_image_through_b10`: the builder calls `export_image(scene_core, image)` once per image and
     the node's `handle` is that image's, which the test checks through the manager's `metadata` (a 4x4 byte image with
     `is_compressible_as_srgb` true for `scene_linear_srgb`, `image.h:51-53`). This is the test that fails if step 5's
     `handle` assignment is missing.
5. `tests/blender_it/golden_batch_10_scenes.py`, the one scene (BRIEF.md:239-246). The builder makes one
   `bpy.data.materials` material whose tree is: `ShaderNodeOutputMaterial` `output`; `ShaderNodeTexCoord` `coords`;
   `ShaderNodeTexImage` `image`; `ShaderNodeEmission` `emit`; and the links `coords.UV → image.Vector`,
   `image.Color → emit.Color`, `emit.Emission → output.Surface`. The plane itself is B9's harness's
   (`B9-golden-harness.md:216-228`); this module supplies the material and the image.
   - The image is `bpy.data.images.new("golden", 4, 4, float_buffer=True)` — a float image, so its pixels are stored
     exactly (step 1's probe: `pixel 0 0.125`) where a byte image would store `0.125490203499794` — with its 64 floats
     set to a dyadic pattern that is the same in all three channels and monotone in `u`: the value at texel `(i, j)` is
     `(i + 1) / 8` for `i` in `0..3`, so the image holds `0.125`, `0.25`, `0.375` and `0.5` across each row. Each is
     exact in float32 (step 1's probe, `0.125` through `0.5`), and the interpolation between two of them is exact too
     (`(1 - t) * a + t * b` with `a` and `b` multiples of `1/8` and `t` a float32), which keeps the render inside the
     range B9's band was measured on (`## Open for Opus` 2).
   - `image.colorspace_settings.name` is set to `sRGB` explicitly, because a generated float image defaults to
     `Linear Rec.709` (step 1's probe) where a byte one defaults to `sRGB`. The export's class is then
     `scene_linear_srgb` (`B10-image-export-x-colour.md:176-177`) and Cycles applies the sRGB transfer function to the
     texels (`util/color.h`'s `color_srgb_to_linear_v4`, which the kernel applies after interpolation,
     `T6.8:1848-1849`). That is a real non-linear step in both engines and is why the scene is worth a golden test.
   - `image.pixels` is written through `foreach_set` and the image is left generated (`source GENERATED`, step 1's
     probe), so `export_image` reads it with `pixels.foreach_get()` as B10 specifies
     (`B10-image-export-x-colour.md:234-239`), and B10's `round(255 * p)` byte reconstruction does not apply: a float
     image exports its float32 bits.
   - The image is added to the scene before the device update, because the manager's kernel arrays move on a later
     `add_image` (`src/cycles/shim/scene/image.h:191-194`), and the node's `handle` is set from the returned index in
     the same place. `## Open for Opus` 1 records where that code lives.
   - Why not fold: `Vector` is linked from the Texture Coordinate node, so `ConstantFolder::all_inputs_constant` is
     false (`constant_fold.cpp:20-29`), and `ImageTextureNode` has no `constant_fold` member at all (step 3's fragment
     list has none), so the node is always compiled into the SVM. `emit.Color` is linked, so the plane's radiance is
     the image's colour.
6. `tests/blender_it/test_golden_batch_10.py`, one test, `@pytest.mark.slow` (CLAUDE.md rule 6; the harness renders
   twice):
   - `test_the_image_texture_node_matches_cycles`. It loads the builder from step 5's module with `_load_by_path`
     (`tests/blender_it/test_extension_it.py:53-64`), registers it under its name in `GOLDEN_SCENES`
     (`B9-golden-harness.md:241`), runs B9's `render_golden.py` as a subprocess with the isolated profile of
     `test_extension_it.py:149-154`, reads `cycles.npy`/`painterly.npy`/`golden.json`, and asserts
     `golden_rule.meets_rule(painterly, cycles)` with `max_abs_difference` in the failure message. The rule is B9's
     (`B9-golden-harness.md:318-337`) and this card states no tolerance, no band and no expected pixel value.
   - It skips with B9's own reason when its inputs are missing (`BLENDER` unset or no extension zip,
     `test_extension_it.py:76-101`), so `make blender-it` stays green on a machine without Blender.
7. `tests/blender/test_sync_shader_node_table.py`, B8's guard test
   (`test_the_table_has_only_the_rows_this_card_adds`, `B8-node-table-export.md:595-598`): its expected set grows from
   eight idnames to nine.
   ```
   set(NODE_TABLE) == {"ShaderNodeOutputMaterial", "ShaderNodeOutputWorld", "ShaderNodeEmission",
                       "ShaderNodeTexCoord", "ShaderNodeValue", "ShaderNodeRGB", "ShaderNodeMath",
                       "ShaderNodeVectorMath", "ShaderNodeTexImage"}
   ```
   Nine idnames and eight Cycles rows, because B8's two output nodes share one row (`output`) and every other row is one
   idname. Nothing else in that file changes: its ladder table, its enum test and its unknown-node test are B8's, and
   its expected `PainterlyUnknownNode` stays `ShaderNodeBsdfPrincipled` (batch 11's, BRIEF.md:289-290).
8. `.venv/bin/ruff format` on the three new files and the two modified Python ones, then `.venv/bin/ruff check .`,
   then every acceptance command.

## Acceptance

Run every command from the repository root; the queue translates them with BACKLOG.md's table (`make check` → `CHECK`,
`make test-blender` → the same target with `KNOBS`, `build/dev` → `build/q`, `.venv/bin/<tool>` →
`MAIN/.venv/bin/<tool>`, any Python command prefixed with `PYTHONPATH="$PWD/analysis"`).
1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and the audit's
   `RESULT: PASS` line. This card adds no C++ doctest and no binding, so the doctest counts and the exported symbols are
   B10's and must not move; the pytest count grows by step 4's five tests. `CHECK`'s `vendor-check` step is what proves
   step 3's manifest is consistent.
2. `make test-blender` exits 0. Report its last line.
3. `.venv/bin/python -m pytest tests/blender/test_sync_shader_batch_10.py -q` prints `5 passed`: step 4's five tests.
   The count is the number of test functions step 4 lists; if it prints another count, the card's count is wrong and
   that is a finding, not a tolerance.
4. `.venv/bin/python -m pytest tests/blender/test_sync_shader_node_table.py -q` prints `6 passed`. The count is B8's
   own (`B8-node-table-export.md:571-603`). This card changes only the guard's expected set (step 7), so the count must
   not move.
5. `make blender-it` exits 0. Report its last line, the collected and passed counts, and the one golden test's
   statistic as the harness prints it. This card states no count for the file set, because the total is B9's to fix and
   not this card's, and the test skips with B9's reason when its inputs are missing.
6. `git status --porcelain` lists only the three Create paths and the three Modify paths above.

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- export `projection` as `node.projection` without the alias → step 4's enum test fails (`'FLAT'` against `flat`) and
  `add_shader` raises B6's `ValueError` naming the enum;
- drop `colorspace` from the row's getter → Cycles' `Colorspace` default is `u_colorspace_auto`
  (`ImageTextureNode.inc:8`) and the golden render fails, because the image's sRGB transfer function is then not
  applied and every texel differs by the transfer curve, far above `BAND`;
- set the image's colour space to `Non-Color` → the export's class becomes `data`
  (`B10-image-export-x-colour.md:176-177`) and the render still matches, because both engines then skip the transfer
  function: this is the mutation that shows the scene's colour-space choice is real and not incidental;
- omit step 5's `handle` assignment → `ImageTextureNode::compile`'s `handle.empty()` branch runs
  (`ImageTextureNode.compile-SVMCompiler.inc`), which calls `image_manager->add_image(filename.string(), ...)` with an
  empty filename, so the render is black on the painterly side and the golden test fails with a difference of the whole
  image;
- forget step 7 → `make test-blender` fails B8's guard test with the one missing idname;
- drive the scene from a constant instead of the Texture Coordinate node → the graph folds to a constant emission and
  the golden test compares two folded constants.

Report: the doctest and pytest counts, the audit line, the golden statistic and every mutation you ran with its first
failing check.

## Commit

`N10: node batch 10: Image Texture — ImageTextureNode's fragments, one node_table row and its golden test`

## Open for Opus

1. **T6.8's `:839-851` list is larger than one node batch, and `BRIEF.md:280-281` reads both ways.** The brief says
   batch 10 extracts "`ImageSlotTextureNode`, `ImageTextureNode`, `EnvironmentTextureNode`, and the rest of the T6.8
   list at `:839-851` that they need". Read one way, that is a card that vendors `ImageHandle::metadata(Progress &)`
   with an `ImageMetaData` shim, `ImageHandle::all_udim_tiled()`, the `tiles` overload of `add_image()`,
   `ImageParams::{animated, colorspace, frame}`, `ColorSpaceManager::colorspace_is_data()`, the `u_colorspace_*` names,
   and for `cull_tiles` the scene parameters, geometry and `UVMapNode` — a second B10-sized card. Read the other way, it
   is "what the two classes need", and T6.8 itself says painterly may set `handle` directly for every image
   (`T6.8:841-844`, quoting `blender/shader.cpp:928-963`), which needs none of that. Evidence for the narrow reading:
   - painterly's `ImageManager::add_image` takes pixels, not a filename or a loader (`src/cycles/shim/scene/image.h:175`),
     so `ImageTextureNode::update_images`' `image_manager->add_image(filename.string(), ...)` call (`:406-430`) cannot
     work against it whatever else is vendored;
   - `ImageHandle::metadata` in painterly's shim takes no `Progress` (`image.h:187-189`) and
     `ColorSpaceManager::colorspace_is_data` does not exist in painterly at all (the class comes with OCIO, which
     `FACTS.md:379` records as "colour-space classification must come from Python");
   - `cull_tiles` reads `scene->params.background` and `scene->geometry`, and `FACTS.md:218` records the shim `Scene` as
     having neither.
   The options: (a) this card's — the node classes' compile-path fragments plus a `handle` set from
   `Scene.add_image` (step 3), with the rest of T6.8's list recorded as unsupported and the tile-culling path never
   running (which is what T6.8 decision 2 already guarantees: no image has tiles or mipmaps, `T6.8:130-140`); (b) a
   separate card that vendors the rest and grows the shim, before this one; (c) this card does (b) as well, which
   doubles it. (a) is what the steps implement and what T6.8's own "M6b, which owns the Blender sync, extracts them"
   (`T6.8:123-127`) suggests; Opus's decision changes step 3's command list and nothing else in this card.
2. **One band for every golden scene, and this scene's range.** B9's `## Open for Opus` 6 (`B9-golden-harness.md:495-503`)
   already names this batch: an image scene's radiance range is wider than the Texture Coordinate scene's, so the same
   absolute `BAND = 2.0**-30` is looser for it. This card keeps its image's values in `1/8 .. 1/2` so the scene stays
   inside the range B9 measured, and it states no band of its own. The options: (a) this card's; (b) a per-scene band
   measured by B9's `measure_levers.py` on this scene's own levers, which is B9's `## Open for Opus` 6's option (b) and
   needs a second `lever_set.json`. No expected value of this card depends on the choice: the scene, the export literal
   and the rule's form are the same.
3. **`colorspace` and `alpha_type` have no exporter yet.** B10's `sync/image.py` has `classify_colorspace` and
   `export_image` (`B10-image-export-x-colour.md:224-239`) but no public mapping from `Image.alpha_mode` to
   `ImageAlphaType`; this card's row needs both (step 2's getter). The options: (a) this card's — it imports
   `classify_colorspace` and repeats B10's alpha table (three lines), which is the smaller diff but duplicates a
   mapping; (b) B10 gains `alpha_type_of(image)` beside `classify_colorspace` and both this card and `export_image`
   call it, which needs one more line in B10's `## Interface` and makes one function the owner of the table; (c) the
   row reads `image.alpha_mode` itself and maps the four identifiers inline, which is the same duplication in a third
   place. (b) is the cleaner and is B10's call, not this draft's.
4. **B9's interface has no `assert_golden`.** B9's drafted card gives `GOLDEN_SCENES` (`B9-golden-harness.md:147`),
   `build(**variant)` (`:144`), `render_golden.py` (`:166-177`) and `golden_rule.meets_rule` (`:163`), and its slow
   test drives them (`:338-357`). Batch 1's card assumed one `assert_golden(scene, name, tmp_path)`
   (`N1-batch-01-value-rgb-math.md:243`, `:669-676`) because B9 was not drafted when it was written. This card follows
   B9 as drafted and writes its own test; batch 1's card, the template, should be reconciled with whichever is chosen.
5. **Two of the row's three enums need aliases `ENUM_ALIASES` does not have.** `ShaderNodeTexImage`'s `extension`
   identifiers are `REPEAT`, `EXTEND`, `CLIP`, `MIRROR` and Cycles' names are `periodic`, `clamp`, `black`, `mirror`
   (`ImageTextureNode.inc:26-31`); its `projection` identifiers are `FLAT`, `BOX`, `SPHERE`, `TUBE` and Cycles' are
   `flat`, `box`, `sphere`, `tube` (`:33-38`, where only `FLAT` matches the lowercase rule). The options: (a) four
   entries per enum in B8's `ENUM_ALIASES`, which is a shared table keyed by RNA identifier and would then hold eight
   entries of batch 10's beside batch 1's four — and `REPEAT`'s and `MIRROR`'s aliases would apply to every node that
   uses those identifiers; (b) each row's getter maps its own node's enums with a private table (this card's step 2,
   which is what the steps implement); (c) `ENUM_ALIASES` becomes per-node, `ENUM_ALIASES[idname]`, which changes B8's
   signature. (b) keeps B8's table as batch 1's and puts each node's aliases where its row is; Opus may prefer (c) for
   one place to look.
6. **The expected values' derivation.** `AGENTS.md` requires a script that produces a committed number to be committed
   next to its output, and this card's `allowedPaths` holds only this file, so the prototype that produced step 4's
   export literal is not in the diff. What the card does instead: step 1's probe is quoted with its output, and the
   literal follows mechanically from the scene step 5 spells out and B8's rules. If Opus prefers the prototype
   committed, it needs a path outside this card's `allowedPaths`, for example `docs/handoff/drafts/M6b/N10-derive.py`.
7. **`Environment Texture` is vendored and gets no row.** `NODE_TEX_ENVIRONMENT` is vendored (`step 1`) and
   `EnvironmentTextureNode` is one of the three classes `BRIEF.md:280` names, but no batch of the twelve
   (`plan.md:305` as quoted at `FACTS.md:39-43`) has an Environment Texture node, and an environment texture in
   painterly's world path is B5's (`BRIEF.md:182-190` evaluates the world's Background, not an environment image). The
   options: (a) this card's — the fragments are vendored (they are in step 3's list) and no row is added, so
   `PainterlyUnknownNode` reports `ShaderNodeTexEnvironment`; (b) a row is added here, which needs a scene that uses it
   and a decision about what it means on a surface (Cycles samples it by direction, not by UV, so the golden scene
   would need a second camera); (c) the class's fragments are not vendored, which leaves `BRIEF.md:280`'s list half
   done. (a) is what the steps implement; the fragments cost nothing and leave (b) to a later card.
8. **What this card does not decide.** Per `BRIEF.md:295-301`: light node graphs stay out of v1; whether a node
   material's emission is scaled by `emission_scale` is open, and this card passes no knob (decision 8); Bump, Normal
   Map and the Attribute node are out. UDIM (`tiles`) and the texture cache are out per T6.8 decisions 2
   (`T6.8:130-140`), so the row exports no `tiles` and `ImageManager::get_use_texture_cache()` is false
   (`src/cycles/shim/scene/image.h:203-206`). `Image Texture`'s `Box`, `Sphere` and `Tube` projections compile
   (`NODE_TEX_IMAGE_BOX` is vendored) but the card's scene uses `Flat`; a box-projection golden scene is a later card's.
