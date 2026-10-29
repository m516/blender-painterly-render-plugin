# N12 — Node batch 12: Mix Shader, Add Shader and Background (drafted from BRIEF.md section 2, "Node batches")

Milestone: M6b · Depends on: B5, B8, B9 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "Node batches" (lines 274-293, batch 12 at `:291`), per that
brief's section 4 (lines 303-324) and the decisions of its section 1 that touch it: decision 5 (`:52-57`, node types by
Cycles type name, links and linkable defaults by UI name, parameters by member name with enums by `NodeEnum` name),
decision 7 (`:67-74`, per-hit lobes sampled as SPEC §6 says), decision 8 (`:75-77`, no new knob) and decision 9
(`:78-79`, every expected value is an exact equality or a derived rule). Code facts are
`docs/handoff/drafts/M6b/FACTS.md` §3.13 (`:324-339`, batch 12's state at `:336-337`), §3.5 (`:236-243`, the collector),
§3.8 (`:268-279`, the miss branch and the world), §3.4 (`:223-234`, `PainterlyShaderManager`) and §3.10 (`:291-301`,
`PainterlyScene`), re-read at this clone's HEAD in every file cited below. The bpy facts are measured on this host with
the project's `bpy` 5.2.2 by the probe of step 1, quoted with its output, and the three export literals of step 4 by the
prototype of step 1's second half.

`BRIEF.md:274-283` gives every node of the six core batches the same four bullets; this card turns each bullet into a
rule in `## Goal`, states for each of batch 12's three nodes whether the bullet applies, and gives every expected value
its derivation. Its shape is batch 1's card (`docs/handoff/drafts/M6b/N1-batch-01-value-rgb-math.md`, the template
`BACKLOG.md:1062-1070` and FOLLOWUPS:93-94 name) and batch 11's (`N11-batch-11-bsdfs.md`), the batch whose nodes are also
closures.

## Goal

Batch 12's three nodes are exported, compiled and rendered through the whole M6b path, and each has a golden test against
Cycles:

- **Rule 1: the nodes' evaluators are vendored, and this card adds nothing to `kernel/`** (BRIEF.md:276). For batch 12
  the bullet is already satisfied at HEAD: `NODE_MIX_CLOSURE` (`third_party/cycles/VENDORED.toml:3589`),
  `NODE_CLOSURE_BACKGROUND` (`:3571`), `NODE_CLOSURE_WEIGHT` (`:3580`), `NODE_CLOSURE_SET_WEIGHT` (`:2887`) and
  `NODE_CLOSURE_EMISSION` (`:2878`) are vendored, the switch lists the first four (`src/cycles/svm_nodes.toml:109-112`)
  and the evaluator `kernel/svm/closure.h` is vendored (`VENDORED.toml:1212`) and included (`svm_nodes.toml:30`).
  `FACTS.md:336-337` says the same ("12 Mix/Add Shader, Background: yes"). The rule is therefore a check, not a change:
  step 1's greps print the counts of step 1, and this card writes no line of `kernel/`.
- **Rule 2: the host class fragments are present, and this card adds none** (BRIEF.md:277-281). `FACTS.md:336-337` says
  "present", and step 1 counts the `VENDORED.toml` entries: `MixClosureNode` 4 members + its `node_define`,
  `AddClosureNode` 4 + 1 and `BackgroundNode` 4 + 1, plus `MixClosureWeightNode`'s 3 + 1, the node
  `ShaderGraph::transform_multi_closure` inserts to compute a Mix Shader's two weights
  (`scene/shader_graph.cpp:1111-1134`). Batch 12 is therefore a **check**, like batch 1 and batch 11: no `third_party/`
  line and no `fragment_units.toml` entry. The three bullets `BRIEF.md:277-281` names as missing are batch 5's, 6's and
  10's classes, and no class of this batch is on that list.
- **Rule 3: `node_table.py` gains batch 12's three rows** (BRIEF.md:282): `ShaderNodeMixShader` → `mix_closure`,
  `ShaderNodeAddShader` → `add_closure` and `ShaderNodeBackground` → `background_shader`, each with the Cycles UI names
  of its linkable inputs and outputs and no parameter getter, because **no member of the three nodes is a parameter**:
  every one of them is a `SOCKET_*` member of its `NodeType` (`MixClosureNode.inc:5-9`, `AddClosureNode.inc:5-8`,
  `BackgroundNode.inc:5-10`). The traps of the batch:
  - `MixClosureNode`'s two closure inputs are `Closure1` and `Closure2` (`MixClosureNode.inc:6-7`), which Blender's
    `Shader` and `Shader_001` reach only through B8's input ladder (`Shader` → `Closure` → `Closure1`,
    `Shader_001` → `Closure_001` → `Closure2`, `B8-node-table-export.md:434-435`). `AddClosureNode`'s are the same two
    names, so the same ladder serves both rows;
  - the three nodes' outputs are `Closure` (`MixClosureNode.inc:9`, `AddClosureNode.inc:8`) and `Background`
    (`BackgroundNode.inc:10`), and Blender calls both outputs `Shader` and `Background`, which is the output ladder's
    `Shader` → `Closure` step (`B8-node-table-export.md:443`) and an exact match for `Background`;
  - `BackgroundNode` has a `SurfaceMixWeight` input that is `SVM_INTERNAL` (`BackgroundNode.inc:8`,
    `SocketType::SVM_INTERNAL`), which no caller sets and Blender has no socket for, and Blender's own `Weight` input is
    `is_unavailable` (step 1's probe) — so neither is named by the row;
  - this is the batch that gives B8's **world** path its first row: B8 wrote `export_world` and
    `Scene.set_background_shader` for the first caller and pinned a world whose only node is `ShaderNodeBackground` as an
    unknown node (B8's E7, `B8-node-table-export.md:657-660`, and E16, `:705-709`). Those two tests change here (step 8).
- **Rule 4: each node has a golden test** (BRIEF.md:283). Batch 12's nodes are two closure mixers and a world shader, so
  the tests are three:
  - `ShaderNodeMixShader` and `ShaderNodeAddShader`: two B9 scenes, one per node, in `tests/blender_it/`, because their
    output is a closure that an emission plane can carry: the plane's surface is the mixer, its two inputs are Emission
    nodes, and a Mix Shader's `Fac` is driven from Texture Coordinate, so the plane's radiance is the blend of the two
    emissions. Cycles renders it at 1 sample in Raw view as a float32 EXR and painterly at `max_depth=1`,
    `emission_gain=1`, `jitter=0`, `output_mode="scene_linear"` (BRIEF.md:239-244), decided by B9's pre-registered rule
    (`B9-golden-harness.md:318-337`: `max |P - C| <= BAND`, `BAND = 2.0**-30`).
  - `ShaderNodeBackground`: a doctest in a new `src/test/test_cycles_svm_batch_12.cpp`, because the node's meaning in
    painterly is the **world on a miss** (B5, `B5-world-shader.md:11-27`) and B9's harness's plane covers the whole frame
    (`ORTHO_SCALE = 2.0` is the plane's side, `B9-golden-harness.md:141`, `:217-221`), so no pixel of that harness can
    show a world. The case compiles a Background graph with a dyadic colour and strength, evaluates it on B5's miss path
    and compares `painterly_svm_background_radiance`'s three doubles with a literal, exactly as T6.7's closure cases
    compare lobes (`src/test/test_cycles_svm_closures.cpp:150-185`).
  `## Open for Opus` 1 records the alternative for the two mixers — lobe-list doctests as batch 11 has — and `## Open for
  Opus` 2 records why the Background node has no image.

Nothing in the core changes: no kernel type, no scene API, no new knob (decision 8, `BRIEF.md:75-77`), so no image, no K
and no parity test of M3-M5 moves. The C++ this card adds is one doctest source.

Which of the four bullets applies, per node (FACTS.md:336-337 is the current state of the three rows; the file:line
column is this clone's HEAD):

| node | Blender idname | Cycles type | 1. vendor the evaluator | 2. host class fragments | 3. `node_table.py` row | 4. golden test |
|---|---|---|---|---|---|---|
| Mix Shader | `ShaderNodeMixShader` | `mix_closure` | nothing to do: `NODE_MIX_CLOSURE` at `VENDORED.toml:3589`, `svm_nodes.toml:112`; `kernel/svm/closure.h` at `VENDORED.toml:1212` | nothing missing: `MixClosureNode`'s 4 members (`VENDORED.toml:3904`, `:3913`, `:4012`, `:4122`) + its `node_define` (`:3670`), and `MixClosureWeightNode`'s 3 + 1 (`:2468`, `:2182`, `:2032`, `:1889`; class at `scene/shader_nodes.h:1208`) | **add** | **add** (B9 scene) |
| Add Shader | `ShaderNodeAddShader` | `add_closure` | nothing to do: no case of its own; `AddClosureNode::compile` emits nothing (`AddClosureNode.compile-SVMCompiler.inc`) and the SVM compiler's `generate_multi_closure` handles the node | nothing missing: `AddClosureNode`'s 4 members (`VENDORED.toml:3886`, `:3895`, `:4022`, `:4112`) + its `node_define` (`:3661`) | **add** | **add** (B9 scene) |
| Background | `ShaderNodeBackground` | `background_shader` | nothing to do: `NODE_CLOSURE_BACKGROUND`, `NODE_CLOSURE_SET_WEIGHT` and `NODE_CLOSURE_EMISSION` at `VENDORED.toml:3571`, `:2887`, `:2878`; `kernel/svm/closure.h` at `:1212` | nothing missing: `BackgroundNode`'s 4 members (`VENDORED.toml:3868`, `:3877`, `:4012`, `:4102`) + its `node_define` (`:3652`) | **add** | **add** (doctest) |

So of the four bullets, bullets 1 and 2 apply to no node (checks, step 1), bullet 3 applies to all three (step 2) and
bullet 4 applies to all three (steps 3-7).

## Read first

- `CLAUDE.md` rules 1, 2 and 3 (scope; named knobs; PEP 8 with type hints and docstrings that state units);
  `AGENTS.md` "Expected values are evidence, not targets" and "Measured means reproducible".
- `docs/handoff/drafts/M6b/BRIEF.md` lines 274-293 (this card's mandate; `:291` is batch 12's three nodes), `:30-37`
  (decision 3, `cycles_shader` and the constant path), `:67-74` (decision 7, per-hit lobes), `:182-196` (B5, the world
  shader on misses), `:237-255` (B9's harness and rule), `:52-57` (the socket-name rule), `:75-79` and `:295-301` (the
  open questions this card must not decide).
- `docs/handoff/drafts/M6b/FACTS.md` §3.13 (`:324-339`, batch 12's line `:336-337`), §3.5 (`:236-243`: the collector,
  `PainterlySvmMaterial` and the zero-lobe rule), §3.8 (`:268-279`: `painterly_trace_pixel`, the miss branch
  `light/background.h:17` and "a miss returns the world/background radiance"), §3.4 (`:223-234`:
  `PainterlyShaderManager`'s `device_update_pre`/`post`/`bind_kernel_globals`) and §3.10 (`:291-301`: `PainterlyScene`'s
  `set_background` and `device_update`).
- `docs/spec.md:190-207` (SPEC §6: the lobe kinds, the selection rule, `two_sided`, and `:202` "M6 evaluates Blender node
  graphs per hit into the same lobe list"), `:51` ("Only diffuse events advance K"), `:169` ("A miss returns the
  world/background radiance") and `:226` (the world and `emission_gain`).
- `docs/handoff/drafts/M6b/B5-world-shader.md`: the Goal (`:9-27`: `KernelPainterlyBackground::cycles_shader`,
  `set_background_shader`, `painterly_svm_background_setup`, `painterly_svm_background_radiance` and the suns), the
  kernel declarations (`:153-171`) and its four doctests (`:427`). This card consumes its two names and changes no line.
- `docs/handoff/drafts/M6b/N1-batch-01-value-rgb-math.md`: the table of `## Goal` (`:70-75`), the rows literal
  (`:186-204`), the getters (`:209-225`), the export literals of `## Steps` 5 (`:540-567`), the guard test's new
  expected set (`:594-608`) and `## Acceptance` (`:612-634`).
- `docs/handoff/drafts/M6b/N11-batch-11-bsdfs.md`: the shape of a closure batch's card — the `## Goal` table (`:78-86`),
  the rows literal (`:184-207`) and the seven doctest cases (`:429-455`), which this card's C++ file copies the shape of.
- `docs/handoff/drafts/M6b/B8-node-table-export.md`: `NodeRow` and the six names `node_table.py` exports (`:172-201`),
  the three rows B8 writes (`:390-407`), the input ladder (`:422-431`, with `ShaderNodeMixShader`'s two closure rungs at
  `:434-435`) and the output ladder (`:441-447`, with `:443`'s `Shader` → `Closure`), the four `ENUM_ALIASES`
  (`:458-468`), `export_graph` (`:485-509`, the `is_unavailable` and `SHADER` skips at `:497-499`), `export_world`
  (`:511-512`), the row-vs-definition regexes (`:574-589`), the guard test a batch card must change (`:595-598`), E7
  (`:657-660`) and E16 (`:705-709`).
- `docs/handoff/drafts/M6b/B9-golden-harness.md`: the harness's public names (`:135-151`, `GOLDEN_SCENES` at `:147`),
  the scene `build` (`:216-244`), the rule (`:318-337`) and the slow test that drives it (`:338-357`).
- The vendored definitions whose rows this card transcribes, each read in full:
  `third_party/cycles/fragments/scene/shader_nodes_cpp/node_define/MixClosureNode.inc` (`mix_closure`; `Fac` `:5`,
  `Closure1` `:6`, `Closure2` `:7`, output `Closure` `:9`), `node_define/AddClosureNode.inc` (`add_closure`;
  `Closure1` `:5`, `Closure2` `:6`, output `Closure` `:8`) and `node_define/BackgroundNode.inc` (`background_shader`;
  `Color` `:5`, `Strength` `:6`, `SurfaceMixWeight` `:8`, output `Background` `:10`).
- The vendored member fragments that make the three nodes the code Cycles compiles:
  `member/MixClosureNode.constant_fold.inc` (the two bypasses: equal closure links, and `Fac` unlinked with
  `fac <= 0` or `fac >= 1`), `member/AddClosureNode.constant_fold.inc` (a missing `Closure1` or `Closure2` bypasses the
  other), `member/BackgroundNode.constant_fold.inc` (a black or zero-strength background is discarded) and the three
  `member/*.compile-SVMCompiler.inc` files — `MixClosureNode`'s and `AddClosureNode`'s are empty ("handled in the SVM
  compiler"), and `BackgroundNode`'s emits `NODE_EMISSION_WEIGHT` when `Color` or `Strength` is linked and
  `NODE_CLOSURE_SET_WEIGHT` of `color * strength` when neither is, then `NODE_CLOSURE_BACKGROUND`.
- `third_party/cycles/fragments/scene/shader_nodes_cpp/member/MixClosureWeightNode.compile-SVMCompiler.inc` (`NODE_MIX_CLOSURE`
  with `fac`, `in_weight_offset`, `weight1_offset`, `weight2_offset`) and `node_define/MixClosureWeightNode.inc`
  (`mix_closure_weight`: `Weight` `:5` default `1.0f`, `Fac` `:6` default `1.0f`, outputs `Weight1`/`Weight2` `:8-9`).
- `third_party/cycles/scene/shader_graph.cpp:1101-1191` (`transform_multi_closure`: the `MixClosureWeightNode` it inserts
  for a node with a `Fac` input, `:1111-1134`; and the `SurfaceMixWeight` / `VolumeMixWeight` arithmetic that gives an Add
  Shader's two closures weight `weight_value + 1.0f`, `:1150-1191`).
- `third_party/cycles/kernel/svm/closure.h:1499-1515` (`svm_node_mix_closure`: `saturatef(fac)`, `in_weight` default
  `1.0f`, `weight1 = in_weight * (1 - weight)`, `weight2 = in_weight * weight`), `:1432-1455`
  (`svm_node_closure_background`), `:1477-1483` (`svm_node_closure_set_weight`), `:1484-1489`
  (`svm_node_closure_weight`) and `:1491-1497` (`svm_node_emission_weight`, `color * strength`).
- `third_party/cycles/scene/shader_nodes.h:795-812` (`BackgroundNode`'s declaration: the three `NODE_SOCKET_API` members
  and `get_feature()`'s `KERNEL_FEATURE_NODE_EMISSION`), `:1186-1194` (`AddClosureNode`) and `:1196-1206`
  (`MixClosureNode`, whose only member is `NODE_SOCKET_API(float, fac)`).
- `src/painterly/kernel/svm/collect.h:39-48` (the two masks), `:52-60` (`PainterlySvmMaterial`), `:76-105`
  (`painterly_svm_lobe_kind`), `:165-215` (`painterly_svm_collect`: emission from `SD_EMISSION` at `:170-175`, the
  zero-lobe rule at `:205-210`) and its header comment `:11-23`.
- `src/painterly/kernel/light/background.h:17-29` (the constant radiance and the suns) and its miss caller
  `src/painterly/kernel/integrator/path.h:79-85`.
- `src/test/test_cycles_svm_closures.cpp:150-185` (`describe()`: one line per lobe, then `emission`, then `dropped`) and
  `src/test/cycles_svm_test_scene.h:101-119` (`PainterlySvmTestScene::surface`); `src/test/CMakeLists.txt:78-99` (where a
  new doctest source is added beside the existing `test_cycles_svm_*` blocks).
- Upstream `intern/cycles/blender/shader.cpp`, read in the pinned checkout (never edited, not in this repo): the three
  `add_node` cases — `ShaderNodeAddShader` `:579-581`, `ShaderNodeMixShader` `:582-584` and `ShaderNodeBackground`
  `:591-593` — and the socket ladders `:1212-1323` that B8 transcribes (`B8-node-table-export.md:422-457`).
- `tests/blender/conftest.py:22`, `:44-53` and `:62-73` (the add-on package and the `addon` fixture);
  `tests/blender_it/test_extension_it.py:53-64` (`_load_by_path`), `:76-101` (the skips) and `:149-154` (the isolated
  profile).
- `pyproject.toml:38-44` and `:48` (`testpaths`, `addopts`, the `slow` marker, ruff's `line-length` and
  `target-version`; `docs/handoff` is excluded from lint).
- The expected values of steps 1 and 4: the probe and the prototype quoted there, measured on this host with `bpy` 5.2.2.

## Create

- `tests/blender/test_sync_shader_batch_12.py`
- `tests/blender_it/golden_batch_12_scenes.py`
- `tests/blender_it/test_golden_batch_12.py`
- `src/test/test_cycles_svm_batch_12.cpp`

`tests/blender_it/golden_batch_12_scenes.py` is a module, not a test: `--import-mode=importlib`
(`pyproject.toml:38-39`) collects only `test_*.py`, and the test file loads it by path with
`tests/blender_it/test_extension_it.py:53-64`'s `_load_by_path`.

## Modify

- `src/blender/addon/sync/shader/node_table.py` (B8's file): batch 12's three rows in `NODE_TABLE` (step 2), after B8's
  four and batch 1's four, and the module docstring's sentence about which rows exist updated to name this batch.
- `tests/blender/test_sync_shader_node_table.py` (B8's file): the guard test of
  `B8-node-table-export.md:595-598`, `test_the_table_has_only_the_rows_this_card_adds`, now expects eleven idnames — B8's
  four plus batch 1's four plus this card's three (step 8).
- `tests/blender/test_sync_shader_export.py` (B8's file, its step 13's ten tests E1-E10) and
  `tests/blender/test_sync_node_materials.py` (B8's step 14's six tests E11-E16): E7, in the export file
  (`B8-node-table-export.md:657-660`), and E16, in the node-materials file (`:705-709`), the two tests whose fixture is a
  world whose only node is `ShaderNodeBackground` (step 8).
- `src/test/CMakeLists.txt`: one `target_sources(painterly_tests PRIVATE test_cycles_svm_batch_12.cpp)` line in a block
  of its own after the existing `test_cycles_svm_*` blocks (`:78-99`), with a comment naming this card.

## Do not touch

- `third_party/cycles/**`, `src/cycles/**`: rules 1 and 2 are satisfied at HEAD (step 1), and `third_party/` is
  `tools/vendor_sync.py`'s alone (R6). A batch-12 step that wanted to vendor or extract something would mean
  `FACTS.md:336-337` is wrong, which is a `report_blocked`, not a change.
- `src/painterly/**`: nothing in the core is batch 12's. `painterly_svm_collect` is T6.7's, `set_background_shader` and
  `painterly_svm_background_radiance` are B5's, the device update is B2's and the trace loop is B4's. A test that needed
  a change there would be proposing a core change, which is `## Open for Opus` 5's business.
- `src/blender/addon/sync/shader/export.py`: B8's rule 4 is generic — a row is data and `export_graph` reads it
  (`B8-node-table-export.md:485-512`), and this card's rows are data only.
- `src/blender/addon/sync/world.py`, `src/blender/addon/sync/__init__.py`, `src/blender/addon/sync/material.py`: B8's and
  M5's. The world's node path already calls `export_world` for any graph that exports (`B8-node-table-export.md:552-558`),
  so the Background row is what makes it run; no line of those files changes.
- `src/blender/addon/sync/shader/flatten.py`: B7's.
- B8's three rows and batch 1's four rows: not this card's.
- `tests/blender_it/golden_scenes.py`, `golden_rule.py`, `render_golden.py`, `test_golden.py`: B9's. This card adds one
  module beside them and two `GOLDEN_SCENES` entries (`B9-golden-harness.md:241`).
- `tests/blender_it/test_extension_it.py` and `tests/blender_it/run_reference.py`: T4.4's.
- `tests/core/test_api_contract.py`: it must pass unchanged, because this card adds no binding.
- `Makefile`, `pyproject.toml`, `src/blender/CMakeLists.txt`: no new target, no new marker, no new module source.
- `NODE_TABLE` beyond this card's three rows, and every other batch's golden test.
- `docs/spec.md`, `docs/plan.md`, `CLAUDE.md`, `AGENTS.md`, `BACKLOG.md`, `docs/handoff/` beyond this card's own file.

## Interface

Not a CONTRACT: this card adds no public name to `_painterly`, no Python API of the add-on and no C++ declaration. The
interfaces it uses are B8's (the row), B6's (the node tuple), B9's (the two scenes) and B5's (the world shader).

**The three rows** (`src/blender/addon/sync/shader/node_table.py`, B8's `NodeRow`,
`B8-node-table-export.md:179-185`):

```python
NODE_TABLE: Final[Mapping[str, NodeRow]] = {
    # ... B8's four rows and batch 1's four, unchanged.
    # MixClosureNode.inc:3-9. `Fac` is the only non-closure input; `Closure1` and `Closure2` are the two
    # closure sockets, which Blender's `Shader` and `Shader_001` reach through the input ladder
    # (Shader -> Closure -> Closure1, Shader_001 -> Closure_001 -> Closure2). No parameter: `fac` is a
    # socket (MixClosureNode.inc:5), not a member of the node's type alone.
    "ShaderNodeMixShader": NodeRow("mix_closure", ("Fac", "Closure1", "Closure2"), ("Closure",)),
    # AddClosureNode.inc:3-8. No `Fac`: an add has no factor, and its two closures carry the same names
    # as a mix's.
    "ShaderNodeAddShader": NodeRow("add_closure", ("Closure1", "Closure2"), ("Closure",)),
    # BackgroundNode.inc:3-10. `SurfaceMixWeight` is SVM_INTERNAL (:8) and Blender's own `Weight` input is
    # unavailable (step 1's probe), so the row names neither; the output is `Background`.
    "ShaderNodeBackground": NodeRow("background_shader", ("Color", "Strength"), ("Background",)),
}
```

The rows have no parameter getter: `NodeRow.parameters` stays `None`, because the three `NodeType`s' non-socket members
are none — `MixClosureNode`'s only `NODE_SOCKET_API` member is `fac`, whose socket is `Fac`
(`scene/shader_nodes.h:1205`), `AddClosureNode` declares no member (`:1186-1194`) and `BackgroundNode`'s three are
`color`, `strength` and `surface_mix_weight`, all three `SOCKET_IN_*` (`BackgroundNode.inc:5-8`,
`scene/shader_nodes.h:809-811`). Nothing of this batch needs `enum_name` either, so `ENUM_ALIASES` does not move.

**What this card consumes from B5** (`docs/handoff/drafts/M6b/B5-world-shader.md:153-171`), which the doctest of step 5
calls and changes no line of:

```cpp
/* The world's radiance along `dir`, before emission_gain, from the Background closures that one
 * evaluation with painterly_svm_background_feature_mask collects (BRIEF.md:188-189). */
ccl_device_inline double3 painterly_svm_background_radiance(PainterlyGlobals kg,
                                                            const double3 dir,
                                                            int cycles_shader,
                                                            ccl_private ShaderData *sd);
```

and `PainterlyScene::set_background_shader(int shader)`, which B8's `export_world` already calls
(`B8-node-table-export.md:511-512`).

**What this card consumes from B9.** `GOLDEN_SCENES: dict[str, Callable[[], bpy.types.Scene]]`
(`B9-golden-harness.md:147`), `build(**variant)` (`:144`), `render_golden.py`'s
`<out_dir>/{cycles.npy, painterly.npy, golden.json, <scene>.blend}` (`:166-177`) and `golden_rule.meets_rule` (`:163`).
This card adds two builders to its own module and two `GOLDEN_SCENES` entries; it calls no `assert_golden`, because B9's
drafted interface has no such function (`## Open for Opus` 3).

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
     A different number means the table is not the one steps 2 and 8 assume: read it and report what is there.
   - B8's world tests are the two this card changes. Each prints `1`.
     ```
     grep -c 'def test_the_background_node_has_no_row_in_this_card' tests/blender/test_sync_shader_export.py
     grep -c 'def test_a_world_with_an_unsupported_graph_falls_back_with_one_warning' tests/blender/test_sync_node_materials.py
     ```
   - B5 landed: the world's radiance function and the binding exist. Each prints `1`.
     ```
     grep -c 'painterly_svm_background_radiance' src/painterly/kernel/svm/background_shader.h
     grep -c 'set_background_shader' src/painterly/scene/scene.h
     grep -c 'set_background_shader' src/blender/_painterly.pyi
     ```
   - B9 landed, with the harness names of `## Interface`. Each prints `1`.
     ```
     grep -c 'GOLDEN_SCENES: dict' tests/blender_it/golden_scenes.py
     grep -c 'def meets_rule' tests/blender_it/golden_rule.py
     grep -c 'golden_rule' tests/blender_it/test_golden.py
     ```
   - Rule 1 holds — the five cases and the evaluator header are vendored. Each prints the number after it.
     ```
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_MIX_CLOSURE"' third_party/cycles/VENDORED.toml              # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_CLOSURE_BACKGROUND"' third_party/cycles/VENDORED.toml       # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_CLOSURE_WEIGHT"' third_party/cycles/VENDORED.toml           # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_CLOSURE_SET_WEIGHT"' third_party/cycles/VENDORED.toml       # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_CLOSURE_EMISSION"' third_party/cycles/VENDORED.toml         # 1
     grep -c 'dest = "kernel/svm/closure.h"' third_party/cycles/VENDORED.toml                                    # 1
     grep -cE '^  "NODE_CLOSURE_BSDF",$|^  "NODE_CLOSURE_BACKGROUND",$|^  "NODE_CLOSURE_WEIGHT",$|^  "NODE_MIX_CLOSURE",$' src/cycles/svm_nodes.toml   # 4
     ```
     `NODE_CLOSURE_SET_WEIGHT` and `NODE_CLOSURE_EMISSION` are the two cases `BackgroundNode::compile` emits besides
     `NODE_CLOSURE_BACKGROUND` (`BackgroundNode.compile-SVMCompiler.inc`); the switch's comment above the four lines at
     `svm_nodes.toml:108` names their origin.
   - Rule 2 holds — the three classes' fragments and `MixClosureWeightNode`'s are vendored. Each prints the count after
     it, `member` first and `node_define` second:
     ```
     for c in MixClosureNode AddClosureNode BackgroundNode MixClosureWeightNode; do
       printf '%-22s %s %s\n' "$c" \
         "$(grep -F "shader_nodes_cpp/member/$c." third_party/cycles/VENDORED.toml | wc -l)" \
         "$(grep -F "shader_nodes_cpp/node_define/$c\"" third_party/cycles/VENDORED.toml | wc -l)"
     done
     ```
     Measured at this HEAD:
     ```
     MixClosureNode         4 1
     AddClosureNode         4 1
     BackgroundNode         4 1
     MixClosureWeightNode   3 1
     ```
     and these print `1` each, because the declarations come with `scene/shader_nodes.h` (`VENDORED.toml:835-836`):
     ```
     grep -c '^class MixClosureNode : public ShaderNode' third_party/cycles/scene/shader_nodes.h             # 1
     grep -c '^class AddClosureNode : public ShaderNode' third_party/cycles/scene/shader_nodes.h             # 1
     grep -c '^class BackgroundNode : public ShaderNode' third_party/cycles/scene/shader_nodes.h             # 1
     grep -c '^class MixClosureWeightNode : public ShaderNode' third_party/cycles/scene/shader_nodes.h        # 1
     ```
   - The bpy facts rules 3 and 4 rest on. Save this probe as a file under `/tmp` and run it with
     `.venv/bin/python <file>`; it must print exactly the lines quoted after it (they are this card's measurement on
     bpy 5.2.2, and the rows and the three scenes of steps 2, 4 and 6 are derived from them):
     ```python
     import bpy

     mat = bpy.data.materials.new("probe")
     mat.use_nodes = True
     tree = mat.node_tree
     tree.nodes.clear()

     for idname in ("ShaderNodeMixShader", "ShaderNodeAddShader", "ShaderNodeBackground"):
         node = tree.nodes.new(idname)
         print(idname, "bl_idname", node.bl_idname)
         print("  inputs ", [(s.identifier, s.type, s.is_unavailable) for s in node.inputs])
         print("  outputs", [(s.identifier, s.type, s.is_unavailable) for s in node.outputs])
         print("  defaults", [(s.identifier,
                               None if s.type == "SHADER" else
                               (tuple(s.default_value) if hasattr(s.default_value, "__len__")
                                else s.default_value)) for s in node.inputs])

     world = bpy.data.worlds.new("probe-world")
     world.use_nodes = True
     print("world output node", world.node_tree.get_output_node("CYCLES").bl_idname)
     print("world default nodes", sorted((n.bl_idname, n.name) for n in world.node_tree.nodes))
     ```
     ```
     ShaderNodeMixShader bl_idname ShaderNodeMixShader
       inputs  [('Fac', 'VALUE', False), ('Shader', 'SHADER', False), ('Shader_001', 'SHADER', False)]
       outputs [('Shader', 'SHADER', False)]
       defaults [('Fac', 0.5), ('Shader', None), ('Shader_001', None)]
     ShaderNodeAddShader bl_idname ShaderNodeAddShader
       inputs  [('Shader', 'SHADER', False), ('Shader_001', 'SHADER', False)]
       outputs [('Shader', 'SHADER', False)]
       defaults [('Shader', None), ('Shader_001', None)]
     ShaderNodeBackground bl_idname ShaderNodeBackground
       inputs  [('Color', 'RGBA', False), ('Strength', 'VALUE', False), ('Weight', 'VALUE', True)]
       outputs [('Background', 'SHADER', False)]
       defaults [('Color', (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0)), ('Strength', 1.0), ('Weight', 0.0)]
     world output node ShaderNodeOutputWorld
     world default nodes [('ShaderNodeBackground', 'Background'), ('ShaderNodeOutputWorld', 'World Output')]
     ```
     (bpy prints one `DeprecationWarning` about `use_nodes` on stderr; it is not part of the output above.)
     What each line fixes:
     - `ShaderNodeMixShader`'s `Fac` is a float whose Blender default is `0.5`, which is Cycles' own default
     (`MixClosureNode.inc:5`, `0.5f`), so this is the one node of the batch whose two engines agree on a default;
       `ShaderNodeAddShader` has no `Fac` at all, matching `AddClosureNode.inc:3-8`.
     - both mixers' closure inputs are `Shader` and `Shader_001`, which the input ladder reaches as `Closure1` and
       `Closure2` (`B8-node-table-export.md:434-435`), and their output `Shader` is Cycles' `Closure` (`:443`).
     - `ShaderNodeBackground`'s `Color` default is Blender's `0.8` grey and Cycles' is `make_float3(0.8f, 0.8f, 0.8f)`
       (`BackgroundNode.inc:5`), so this is the second node of the batch whose default agrees; `Strength` is `1.0` in
       both (`:6`). Its `Weight` input is `is_unavailable`, Cycles' `SurfaceMixWeight` is `SVM_INTERNAL` (`:8`), and the
       row names neither.
     - a new world's node tree is Blender's default: `ShaderNodeOutputWorld` → `ShaderNodeBackground`, and
       `get_output_node("CYCLES")` returns the `ShaderNodeOutputWorld`, which is the graph's output for
       `export_graph` (`B8-node-table-export.md:643-647`, B8's E4).
2. `node_table.py`, the three rows of `## Interface`, transcribed from the vendored definitions: `cycles_type` is
   `NodeType::add`'s first argument (`MixClosureNode.inc:3`, `AddClosureNode.inc:3`, `BackgroundNode.inc:3`),
   `inputs`/`outputs` are the `SOCKET_IN_*`/`SOCKET_OUT_*` UI names in file order, and the parameters are the
   `SOCKET_*` (non-`IN`/`OUT`) members a caller sets — of which there are none, which is why all three rows leave
   `parameters` at its default `None` (`B8-node-table-export.md:181-185`). Measured, from step 1's probe and the three
   files:
   ```
   ShaderNodeMixShader:    'mix_closure',       inputs=['Fac', 'Closure1', 'Closure2'], outputs=['Closure']
   ShaderNodeAddShader:    'add_closure',       inputs=['Closure1', 'Closure2'],        outputs=['Closure']
   ShaderNodeBackground:   'background_shader', inputs=['Color', 'Strength'],           outputs=['Background']
   ```
   - `ShaderNodeMixShader`'s `Fac` is a socket (`SOCKET_IN_FLOAT(fac, "Fac", 0.5f)`, `MixClosureNode.inc:5`), not a
     member the row must set: the row's `inputs` names it and the export carries its default when it is unlinked
     (B8's `export_graph`, `:497-503`).
   - `ShaderNodeBackground`'s `SurfaceMixWeight` (`BackgroundNode.inc:8`) is declared with
     `SocketType::SVM_INTERNAL`, so it is not linkable and no caller sets it; B8's `export_graph` never sees it because
     Blender has no such socket (step 1's probe: three inputs, one of them unavailable).
   - The docstring states rule 3, the file each row comes from and that a row's `cycles_type` is a Cycles type name, not
     a Blender idname (decision 5, BRIEF.md:52-55), and the sentence about which rows exist now names batch 12's three
     beside B8's four and batch 1's four.
3. `tests/blender_it/golden_batch_12_scenes.py`, the two scenes (BRIEF.md:239-246). Each builder makes one
   `bpy.data.materials` material whose tree is: `ShaderNodeOutputMaterial` `output`; `ShaderNodeTexCoord` `coords`; two
   `ShaderNodeEmission` nodes `emit1` and `emit2`; the batch-12 node; and the links that make it the plane's surface.
   The plane and the camera are B9's harness's (`B9-golden-harness.md:216-228`); this module supplies the material.
   - `mix_shader_scene`: `ShaderNodeMixShader` `mix`; `emit1.Color = (0.25, 0.5, 0.75, 1.0)` and
     `emit2.Color = (0.5, 0.25, 0.125, 1.0)`, both `Strength` at Blender's `1.0`; `coords.Generated → emit1.Color`,
     `coords.Generated → mix.Fac`, `emit1.Emission → mix.Shader`, `emit2.Emission → mix.Shader_001`,
     `mix.Shader → output.Surface`. The plane's radiance is then `emit1.Color * (1 - fac) + emit2.Color * fac` with `fac`
     the Texture Coordinate's `Generated` channel, which is what `svm_node_mix_closure`'s
     `in_weight * (1 - weight)` / `in_weight * weight` (`kernel/svm/closure.h:1507-1514`) and
     `background_setup`'s sum (`kernel/closure/emissive.h:16-26`) give, and what Cycles computes for the same graph.
     Both colours are dyadic and each product is exact in float32, so the blend is exact and the scene stays inside the
     range B9's band was measured on.
   - `add_shader_scene`: `ShaderNodeAddShader` `add`; `emit2.Color = (0.25, 0.5, 0.75, 1.0)` and
     `coords.Generated → emit1.Color`, `emit1.Emission → add.Shader`, `emit2.Emission → add.Shader_001`,
     `add.Shader → output.Surface`. The plane's radiance is `Generated` + `(0.25, 0.5, 0.75)`: an add has no factor, and
     `ShaderGraph::transform_multi_closure` gives each of its closures the weight `1.0`
     (`scene/shader_graph.cpp:1183-1187`), so the two emissions simply sum.
   - Why neither folds: `ConstantFolder::all_inputs_constant` is false for both nodes, because each has a linked closure
     input (`constant_fold.cpp:20-29`); `MixClosureNode::constant_fold`'s two bypasses need equal closure links or an
     unlinked `Fac` of `0`/`1` (`MixClosureNode.constant_fold.inc`), and this scene links `Fac`; and
     `AddClosureNode::constant_fold` bypasses only a *missing* closure link (`AddClosureNode.constant_fold.inc`), which
     this scene does not have. Both nodes therefore reach the SVM.
   - Each builder returns the material, so the harness can write it and step 4's export test can read it. The two scenes
     are the two mixers' golden scenes, one per node, and neither drives the other: a failing scene names one row.
4. `tests/blender/test_sync_shader_batch_12.py`, six tests. `bpy` only, no Blender run, no `.blend` on disk outside
   `tmp_path`, and every expected value a literal compared with exact equality, so no tolerance appears.
   - `test_the_three_rows_are_the_vendored_node_definitions`: parse the three `.inc` files with B8's regexes
     (`SOCKET_IN_[A-Z0-9_]+\(\s*\w+\s*,\s*"([^"]+)"`, the `SOCKET_OUT_` form and `NodeType::add\("([a-z_]+)"`,
     `B8-node-table-export.md:574-589`) and compare each with the row. Expected (step 2's table):
     ```
     ShaderNodeMixShader:    'mix_closure',       inputs=['Fac', 'Closure1', 'Closure2'], outputs=['Closure']
     ShaderNodeAddShader:    'add_closure',       inputs=['Closure1', 'Closure2'],        outputs=['Closure']
     ShaderNodeBackground:   'background_shader', inputs=['Color', 'Strength'],           outputs=['Background']
     ```
     The three files declare sockets the rows do not name — `SOCKET_ENUM`/`SOCKET_BOOLEAN` members are absent from these
     three, but `BackgroundNode.inc:8` declares `SurfaceMixWeight` with `SocketType::SVM_INTERNAL`, which the
     `SOCKET_IN_`/`SOCKET_OUT_` regexes do match and which the row deliberately omits — so the test asserts the filtered
     list, drops the `SVM_INTERNAL` entries, and says why: an internal socket is the compiler's, not a caller's.
   - `test_the_mix_row_uses_the_closure_ladder`: `socket_name("ShaderNodeMixShader", "Shader", "in") == "Closure1"`,
     `socket_name("ShaderNodeMixShader", "Shader_001", "in") == "Closure2"`,
     `socket_name("ShaderNodeMixShader", "Shader", "out") == "Closure"`, and the same three for `ShaderNodeAddShader`;
     `socket_name("ShaderNodeBackground", "Background", "out") == "Background"` and
     `socket_name("ShaderNodeBackground", "Weight", "in") is None` (step 1's probe: the ladder's rungs for `Weight` are
     `('Weight', 'Weight1')` and the row names neither).
   - the three export tests, one per scene: `test_the_mix_shader_scene_exports_these_lists`,
     `test_the_add_shader_scene_exports_these_lists` and `test_the_background_world_exports_these_lists`. Each builds its
     scene with step 3's or step 6's builder, writes it to `tmp_path` with `bpy.data.libraries.write`, loads it back with
     `bpy.data.libraries.load` (a reloaded `.blend` keeps every socket identifier, `B8-node-table-export.md:388-389`) and
     compares `export_graph(flatten_tree(tree))` with a literal. Measured, by running an implementation of steps 2, 3 and
     6 and B8's `export_graph` against bpy 5.2.2 (`## Open for Opus` 4):
     ```
     mix_shader_scene:
       ([('texture_coordinate', {'from_dupli': False}, {}),
         ('emission', {}, {'Strength': 1.0}),
         ('emission', {}, {'Color': (0.5, 0.25, 0.125), 'Strength': 1.0}),
         ('mix_closure', {}, {})],
        [(0, 'Generated', 1, 'Color'), (0, 'Generated', 3, 'Fac'),
         (1, 'Emission', 3, 'Closure1'), (2, 'Emission', 3, 'Closure2'), (3, 'Closure', -1, 'Surface')])
     add_shader_scene:
       ([('texture_coordinate', {'from_dupli': False}, {}),
         ('emission', {}, {'Strength': 1.0}),
         ('emission', {}, {'Color': (0.25, 0.5, 0.75), 'Strength': 1.0}),
         ('add_closure', {}, {})],
        [(0, 'Generated', 1, 'Color'), (1, 'Emission', 3, 'Closure1'),
         (2, 'Emission', 3, 'Closure2'), (3, 'Closure', -1, 'Surface')])
     background_world:
       ([('background_shader', {}, {'Color': (0.125, 0.25, 0.5), 'Strength': 2.0})],
        [(0, 'Background', -1, 'Surface')])
     ```
     What each literal says:
     - the node order is the tree's own, which the walk of `B7-flatten.md:264-282` keeps: `coords` first, then the two
       emissions, then the mixer, and `output` is not a node (B8's rule 4, `B8-node-table-export.md:490-495`).
     - `mix_shader_scene`'s `Fac` is linked from `coords`, so no `Fac` default is exported; `emit1.Color` is linked too,
       which is why only its `Strength` appears and `emit2` carries both. The two `Generated` links share node 0, which
       is why they are two entries of the same source node.
     - `add_shader_scene`'s `add_closure` exports no defaults at all: its only inputs are closures, and B8's rule 4 skips
       every `SHADER` socket (`:497-499`).
     - `background_world` is a world's tree: `ShaderNodeOutputWorld` `output` is the graph's output
       (`flatten_tree(...).output_idname == "ShaderNodeOutputWorld"`, `B7-flatten.md:126`) and is not a node, so the
       world exports one node and one link, and `export_world` turns that into
       `set_background_shader(add_shader(*export_graph(tree)))` (`B8-node-table-export.md:511-512`).
   - `test_the_background_world_binds_the_world_shader`: the builder's world through B8's `export_world` against a fake
     scene core records `add_shader` with the literal above and then `set_background_shader(0)` — the same assertion
     shape as B8's E15 (`B8-node-table-export.md:702-704`), which now has a row behind it. This is the test that fails if
     step 2's `ShaderNodeBackground` row is missing, because `export_world` then raises `PainterlyUnknownNode` and
     `sync_world` falls back to `world.color`.
5. `src/test/test_cycles_svm_batch_12.cpp`, three cases, named `batch 12: the mix shader`, `batch 12: the add shader`
   and `batch 12: the background node`, so `-tc='batch 12:*'` selects exactly them. The file includes
   `cycles_svm_test_support.h`, `cycles_svm_test_scene.h`, `painterly/kernel/svm/collect.h` and `scene/shader_nodes.h`,
   plus `<string>` for `describe()` and B5's `painterly/kernel/svm/background_shader.h`.
   - The two mixers' cases build their graph in C++, as T6.7's cases do (`src/test/test_cycles_svm_closures.cpp:540-600`):
     `make_unique<ShaderGraph>()`, `create_node_by_name(*graph, "mix_closure")` (and `"add_closure"`), two
     `create_node_by_name(*graph, "diffuse_bsdf")` children with dyadic `Color`s, `add_surface` with the mixer's `Closure`
     output, `compile(*scene)`, evaluate at `PainterlySvmTestScene::surface(0, 0)` (`src/test/cycles_svm_test_scene.h:101-119`)
     with `svm_eval_nodes<painterly_svm_surface_feature_mask, SHADER_TYPE_SURFACE>` and collect with
     `painterly_svm_collect`, then compare `describe()` (`test_cycles_svm_closures.cpp:150-185`) with a literal.
     - `mix_closure`: `Fac` `0.5` (unlinked, so `MixClosureNode::constant_fold`'s `fac >= 1` bypass cannot fire and the
       graph keeps the node), `Closure1` ← a Diffuse BSDF of `Color` `(0.25, 0.5, 0.75)` and `Roughness` `0.0`,
       `Closure2` ← a Diffuse BSDF of `Color` `(0.5, 0.25, 0.125)` and `Roughness` `0.0`. Expected: two `diffuse` lobes,
       the first of weight `(0.125, 0.25, 0.375)` and the second of `(0.25, 0.125, 0.0625)`, then
       `emission 0 0 0` and `dropped 0`. The derivation: `MixClosureNode` has no `compile` of its own
       (`MixClosureNode.compile-SVMCompiler.inc`), so `ShaderGraph::transform_multi_closure` inserts a
       `MixClosureWeightNode` whose `Fac` is the node's unlinked `Fac` and whose `Weight` is unlinked at the root, and
       `svm_node_mix_closure` writes `in_weight * (1 - weight)` and `in_weight * weight` with `in_weight`'s default
       `1.0f` (`kernel/svm/closure.h:1499-1515`), i.e. `0.5` and `0.5`; each Diffuse BSDF's closure weight is its
       `Color` times that mix weight (`kernel/svm/closure.h:525-537`, the `Roughness` `0.0` branch at `:533-535`), and the collector's lobe weight is the
       closure weight (`collect.h:199-201`). Every factor is dyadic, so each product is exact in float32 and exact as
       the double `describe()` prints.
     - `add_closure`: the same two Diffuse BSDFs, `Closure1` and `Closure2` linked and no `Fac` input — the type has
       none (`AddClosureNode.inc:5-7`). Expected: the same two `diffuse` lobes at their **full** colours,
       `(0.25, 0.5, 0.75)` and `(0.5, 0.25, 0.125)`, then `emission 0 0 0` and `dropped 0`. The derivation: with no
       `Fac` input `transform_multi_closure` passes `weight_out` straight through, and at the root it is null, so each
       closure's `SurfaceMixWeight` is set to `weight_value + 1.0f` = `1.0` (`scene/shader_graph.cpp:1183-1187`).
     - The kinds are SPEC §6's and the policy's (`T6.7:175-208`: `CLOSURE_IS_BSDF_DIFFUSE` → a diffuse lobe of the closure
       weight), not this card's; the two cases write no new rule.
   - `batch 12: the background node` builds a graph whose only node is `create_node_by_name(*graph, "background_shader")`
     with `Color` `(0.125, 0.25, 0.5)` and `Strength` `2.0`, both unlinked, compiles it and calls
     `painterly_svm_background_radiance(kg, dir, shader_id, &sd)` for the three fixed directions
     `(0, 0, 1)`, `(0, 1, 0)` and `(1, 0, 0)` — a constant Background is direction-independent, so all three must be the
     same value. Expected: `(0.25, 0.5, 1.0)`, which is `BackgroundNode::compile`'s `color * strength`
     (`BackgroundNode.compile-SVMCompiler.inc`, the `else` branch an unlinked `Color` and `Strength` take) followed by
     `background_setup`'s `closure_emission_background += weight` (`kernel/closure/emissive.h:16-26`), and B5's radiance
     is that closure's weight (`B5-world-shader.md:16-20`). Both inputs are dyadic and `0.125 * 2` and `0.25 * 2` are
     exact in float32, so the three doubles are exact.
   - `src/test/CMakeLists.txt`: the one `target_sources` line of `## Modify`, which makes the three cases part of
     `painterly_tests`.
6. `tests/blender_it/test_golden_batch_12.py`, two tests, one per mixer scene, each `@pytest.mark.slow` (CLAUDE.md
   rule 6; the harness renders twice per scene):
   - `test_the_mix_shader_node_matches_cycles` and `test_the_add_shader_node_matches_cycles`. Each loads its builder from
     step 3's module with `_load_by_path` (`tests/blender_it/test_extension_it.py:53-64`), registers it under its name in
     `GOLDEN_SCENES` (`B9-golden-harness.md:241`), runs B9's `render_golden.py` as a subprocess with the isolated profile
     of `test_extension_it.py:149-154`, reads `cycles.npy`/`painterly.npy`/`golden.json`, and asserts
     `golden_rule.meets_rule(painterly, cycles)` with `max_abs_difference` in the failure message. The rule is B9's
     (`B9-golden-harness.md:318-337`) and this card states no tolerance, no band and no expected pixel value.
   - Each test skips with B9's own reason when its inputs are missing (`BLENDER` unset or no extension zip,
     `test_extension_it.py:76-101`), so `make blender-it` stays green on a machine without Blender.
7. `tests/blender_it/golden_batch_12_scenes.py`, the world the Background node's golden test reads: a
   `bpy.data.worlds.new("batch 12 world")` whose tree is `ShaderNodeOutputWorld` `output` and `ShaderNodeBackground`
   `background` with `Color = (0.125, 0.25, 0.5, 1.0)` and `Strength = 2.0`, and `background.Background → output.Surface`
   — the fixture of step 4's third export test and of the `background_world` literal above. It is a builder, not a
   `GOLDEN_SCENES` entry: B9's harness renders a material on a plane and has no world scene (`## Open for Opus` 2).
8. `tests/blender/test_sync_shader_node_table.py`, `tests/blender/test_sync_shader_export.py` and
   `tests/blender/test_sync_node_materials.py`, B8's three files.
   - The guard test (`test_the_table_has_only_the_rows_this_card_adds`, `B8-node-table-export.md:595-598`): its expected
     set grows from eight idnames to eleven.
     ```
     set(NODE_TABLE) == {"ShaderNodeOutputMaterial", "ShaderNodeOutputWorld", "ShaderNodeEmission",
                         "ShaderNodeTexCoord", "ShaderNodeValue", "ShaderNodeRGB", "ShaderNodeMath",
                         "ShaderNodeVectorMath", "ShaderNodeMixShader", "ShaderNodeAddShader",
                         "ShaderNodeBackground"}
     ```
     Eleven idnames and ten Cycles rows, because B8's two output nodes share one row (`output`) and every other row is
     one idname.
   - E7 (`test_the_background_node_has_no_row_in_this_card`, `B8-node-table-export.md:657-660`) is replaced, because
     its premise is gone: `ShaderNodeBackground` has a row now. Its successor is
     `test_the_sky_texture_node_has_no_row`, with the same world fixture and a `ShaderNodeTexSky` `sky` linked into the
     Background's `Color` — the node B8's own message was measured on. Expected: `PainterlyUnknownNode` with
     `str(error) == "sky: the node type ShaderNodeTexSky is not in the node table"`, `error.node_name == "sky"` and
     `error.idname == "ShaderNodeTexSky"` (measured: the table raises for that idname, step 1's second half). Sky Texture
     is in none of the twelve batches (`plan.md:305` as quoted at `FACTS.md:39-43`), so no later batch card changes it
     again.
   - E16 (`test_a_world_with_an_unsupported_graph_falls_back_with_one_warning`, `B8-node-table-export.md:705-709`, in
     `tests/blender/test_sync_node_materials.py`) keeps its name and its assertions and changes its fixture to E7's new
     sky world, a world named `evening` (the name B8's measured message uses, `:562`): no `set_background_shader` call, T5.3's constant world for the fake scene, and
     `stats.warnings == ["sky: the node type ShaderNodeTexSky is not in the node table; evening uses world.color"]`. The
     two worlds of B8's E4/E15 keep working and now go through a real row instead of a fallback, which is what
     `test_the_background_world_binds_the_world_shader` (step 4) pins.
   - Nothing else in the two files changes: their ladders, their enum test and their other fixtures are B8's.
9. `.venv/bin/ruff format` on the three new Python files and the three modified Python ones, `clang-format -i` on the new
   C++ file, then `.venv/bin/ruff check .`, then every acceptance command.

## Acceptance

Run every command from the repository root; the queue translates them with BACKLOG.md's table (`make check` → `CHECK`,
`make test-blender` → the same target with `KNOBS`, `build/dev` → `build/q`, `.venv/bin/<tool>` →
`MAIN/.venv/bin/<tool>`, any Python command prefixed with `PYTHONPATH="$PWD/analysis"`).
1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and the audit's
   `RESULT: PASS` line. This card adds three doctest cases and no binding, so the doctest case count grows by exactly
   three and the exported symbols do not move; the pytest count grows by step 4's six tests.
2. `make audit` prints `RESULT: PASS`: no new exported symbol (no binding, no new production source) and no new dependency
   (no CMake link line changes; the one `target_sources` line adds a source to the existing test target).
3. `build/dev/src/test/painterly_tests -tc='batch 12:*'` prints `test cases: 3 | 3 passed | 0 failed` and the assertion
   count step 5's three cases give. The count is the number of cases step 5 lists; if it prints another count, the card's
   count is wrong and that is a finding, not a tolerance.
4. `make test-blender` exits 0. Report its last line.
5. `.venv/bin/python -m pytest tests/blender/test_sync_shader_batch_12.py -q` prints `6 passed`: step 4's
   `1 + 1 + 3 + 1 = 6`.
6. `.venv/bin/python -m pytest tests/blender/test_sync_shader_node_table.py -q` prints `6 passed`,
   `.venv/bin/python -m pytest tests/blender/test_sync_shader_export.py -q` prints `10 passed` and
   `.venv/bin/python -m pytest tests/blender/test_sync_node_materials.py -q` prints `6 passed`. All three counts are
   B8's own (`B8-node-table-export.md:571-603`, `:610-676`, `:676-709`): step 8 changes one expected set, one fixture and
   one idname, and adds or removes no test, so no count moves. If any prints another count, a test arrived or vanished in
   that file.
7. `make blender-it` exits 0. Report its last line, the collected and passed counts, and the two golden tests' statistics
   as the harness prints them. This card states no count for the file set, because the total is B9's to fix and not this
   card's, and each test skips with B9's reason when its inputs are missing.
8. `git status --porcelain` lists only the four Create paths and the five Modify paths above.

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- name the Mix Shader's closure inputs `Shader` and `Shader_001` (Blender's identifiers) instead of `Closure1` and
  `Closure2` → step 4's row-vs-definition test fails on `ShaderNodeMixShader`, and every `Closure1`/`Closure2` link is
  dropped by B8's rule 4, so both golden tests of step 6 render a black plane;
- give `ShaderNodeAddShader` a `Fac` input → step 4's row-vs-definition test fails, because `AddClosureNode.inc` declares
  no such socket, and `add_shader` raises B6's `ValueError` naming it;
- name `Weight` in the Background row → step 4's ladder test fails (`socket_name(..., "Weight", "in")` returns
  `"Weight"` instead of `None`), and `export_graph` exports a default for a socket Blender marks unavailable and Cycles
  does not have, so `add_shader` raises B6's `ValueError`;
- export `ShaderNodeBackground`'s `SurfaceMixWeight` → step 4's row-vs-definition test fails unless the test's
  `SVM_INTERNAL` filter is what drops it, which is why the test filters on the flag rather than on the name;
- drop the `Background` row from step 2 → step 4's `test_the_background_world_binds_the_world_shader` fails with
  `PainterlyUnknownNode`, `make test-blender` fails the guard test with one missing idname, and `sync_world` falls back
  to `world.color` for every Background world, which B8's E15 then reports;
- forget step 8's E7/E16 change → `make test-blender` fails, because `ShaderNodeBackground` now has a row and B8's E7
  expects `PainterlyUnknownNode` for it;
- set `Fac` to `0.0` or `1.0` in the mix doctest of step 5 → `MixClosureNode::constant_fold`'s
  `folder.bypass_or_discard` fires (`MixClosureNode.constant_fold.inc`), the graph loses one closure, and the case's
  `describe()` literal (two lobes) no longer matches;
- drive either golden scene from a constant instead of the Texture Coordinate node → `all_inputs_constant` is true, the
  graph folds to a constant emission, and step 6 compares two folded constants and proves nothing about the node;
- change one weight in step 5's mix literal by one float32 ulp → step 3's `describe()` comparison fails and prints both
  lines, which is what makes the literals exact rather than approximate.

Report: the doctest case and assertion counts, the pytest counts, the audit line, the two golden statistics and every
mutation you ran with its first failing check.

## Commit

`N12: node batch 12: Mix Shader, Add Shader and Background — three node_table rows, the world's first row and their golden tests`

## Open for Opus

1. **The two mixers' golden test is an image; batch 11's is a lobe list.** `BRIEF.md:283` says each node's golden test
   "passes B9's rule", and `BRIEF.md:289-290` makes batch 11 the exception because "lobes are painterly's own". Batch 12's
   two mixers are closures too, so the same argument would put them in doctests; this card puts them in B9 scenes instead,
   because a Mix Shader's and an Add Shader's effect *is* visible in a render — the plane's radiance is the blend of the
   two emissions — so an image compares both engines' closure weighting rather than painterly's collector alone. The
   alternatives: (a) this card's, two B9 scenes; (b) two lobe-list doctests as batch 11's, which tests
   `painterly_svm_collect` and not the render path, and costs no render time; (c) both, which doubles the batch. No
   expected value of this card depends on the choice: the export literals of step 4 and the doctest literals of step 5 are
   the same, and only step 6's two files and acceptance 7's statistics change.
2. **The Background node's golden test is not an image, and B9's harness cannot make it one.** B9's `build` renders a
   plane of `ORTHO_SCALE = 2.0` — the plane's side (`B9-golden-harness.md:141`, `:217-221`) — so the plane covers every
   pixel and no world is visible; and painterly's Background node is the world on a miss (B5, `BRIEF.md:182-196`), not a
   surface. This card's golden test is therefore a C++ doctest on `painterly_svm_background_radiance` (step 5). The
   alternatives: (a) this card's; (b) a B9 scene whose camera looks past the plane (a smaller plane or a wider
   `ORTHO_SCALE`), which would need a new variant in B9's `build` and a new band measured on it; (c) a surface-mounted
   Background node, which Cycles renders as emission and painterly's collector also turns into `material.emission`, but
   which is not the node's meaning in painterly. (a) is what the steps implement and what B5's card already tests from
   the other side; Opus may prefer (b) if the world wants a pixel-level comparison against Cycles.
3. **B9's interface has no `assert_golden`.** B9's drafted card gives `GOLDEN_SCENES` (`B9-golden-harness.md:147`),
   `build(**variant)` (`:144`), `render_golden.py` (`:166-177`) and `golden_rule.meets_rule` (`:163`), and its slow test
   drives them (`:338-357`). Batch 1's card assumed one `assert_golden(scene, name, tmp_path)`
   (`N1-batch-01-value-rgb-math.md:243`, `:669-676`) because B9 was not drafted when it was written. This card follows B9
   as drafted and writes its own two tests; the alternatives are (a) B9 gains the wrapper and every batch card calls it,
   or (b) each batch card writes its own test as this one does. Batch 1's card, the template, should be reconciled with
   whichever is chosen.
4. **The expected values' derivation.** `AGENTS.md` requires a script that produces a committed number to be committed
   next to its output, and this card's `allowedPaths` holds only this file, so the prototype that produced step 4's three
   literals is not in the diff. What the card does instead: step 1's probe is quoted with its output, and each literal
   follows mechanically from a scene step 3 or step 7 spells out and B8's rules. If Opus prefers the prototype committed,
   it needs a path outside this card's `allowedPaths`, for example `docs/handoff/drafts/M6b/N12-derive.py`, as batch 1's
   `## Open for Opus` 2 asks for its own.
5. **`MixClosureWeightNode` is a fourth class of the batch, and it is a Cycles internal.** `ShaderGraph::transform_multi_closure`
   creates one `MixClosureWeightNode` per node with a `Fac` input (`scene/shader_graph.cpp:1111-1134`) and its
   `compile` emits `NODE_MIX_CLOSURE` (`MixClosureWeightNode.compile-SVMCompiler.inc`). Its fragments are vendored
   (step 1: 3 members and its `node_define`), and no `node_table.py` row can exist for it because Blender has no such
   node. The alternatives: (a) this card's — the fragments stay vendored and the class is exercised only through the Mix
   Shader's doctest and scene, which is what step 5's `mix_closure` case does; (b) a `test_cycles_svm_compiler.cpp` case
   that compiles a Mix Shader and asserts the inserted node's `NODE_MIX_CLOSURE` bytes, which would pin the weight
   arithmetic without rendering; (c) nothing, which leaves the class's `compile` covered only by the two cases above.
   (a) is what the steps implement; Opus may want (b) as a cheaper check of the same arithmetic.
6. **`Parallel-safe: no`, against the plan's row.** `FACTS.md:362` records the plan's row as
   `"Node batch i of 12: <name> (node-table rows and golden tests; parallel-safe)"`, but every batch card edits the same
   literal in B8's guard test (`B8-node-table-export.md:595-598`, this card's step 8) and this card also edits two of
   B8's export tests. The options are batch 1's `## Open for Opus` 3's: keep `no` (this card) and run the batches in
   sequence, or replace the guard with a per-batch subset assertion plus a per-batch count.
7. **What this card does not decide.** Per `BRIEF.md:295-301`: light node graphs stay out of v1, so no scene of this card
   drives a light; whether a node material's emission is scaled by `emission_scale` is open, and this card passes no knob
   (decision 8); Bump, Normal Map and the Attribute node are out. `MixClosureNode`'s sibling `MixClosureWeightNode` is
   covered by `## Open for Opus` 5; `ShaderNodeTexSky`, `ShaderNodeHoldout`, `ShaderNodeBsdfToon` and the volume nodes are
   not extracted (`FACTS.md:336-337`) and get no row, so `PainterlyUnknownNode` reports them, which is what step 8's E7
   successor pins for the Sky Texture.
