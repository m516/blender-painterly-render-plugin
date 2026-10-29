# N6 — Node batch 6: Texture Coordinate and Mapping (drafted from BRIEF.md section 2, "Node batches")

Milestone: M6b · Depends on: B3, B8, B9 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "Node batches" (lines 274-293, batch 6 at `:287`), per that
brief's section 4 (lines 303-324) and the decisions of its section 1 that touch it: decision 5 (`:52-57`, node types by
Cycles type name, links and linkable defaults by UI name, parameters by member name with enums by `NodeEnum` name),
decision 6 (`:58-66`, the `ShaderData` a painterly hit gets), decision 8 (`:75-77`, no new knob) and decision 9
(`:78-79`, every expected value is an exact equality or a derived rule). Code facts are
`docs/handoff/drafts/M6b/FACTS.md` §3.13 (`:324-339`, batch 6's state at `:333-334`), §3.9 (`:281-289`, the hit
records), §3.7 (`:253-266`, the build targets) and §6 gaps 4 and 5, re-read at this clone's HEAD in every file cited
below. The bpy facts are measured on this host with the project's `bpy` 5.2.2 by the probe of step 1, quoted with its
output.

`BRIEF.md:274-283` gives every node of the six core batches the same four bullets; this card turns each bullet into a
rule in `## Goal`, states for each of batch 6's two nodes whether the bullet applies, and gives every expected value
its derivation. Its shape is batch 1's card (`docs/handoff/drafts/M6b/N1-batch-01-value-rgb-math.md`, the template
`BACKLOG.md:1062-1070` and FOLLOWUPS:93-94 name).

## Goal

Batch 6's two nodes are exported, compiled and rendered through the whole M6b path, and each has a golden test against
Cycles:

- **Rule 1: the nodes' evaluators are vendored, and this card adds nothing to `kernel/`** (BRIEF.md:276). For batch 6
  the bullet is already satisfied at HEAD: `NODE_TEX_COORD` and `NODE_TEX_COORD_DERIVATIVE` are vendored
  (`third_party/cycles/VENDORED.toml:3067`, `:3076`), as are `NODE_MAPPING` and `NODE_MAPPING_DERIVATIVE` (`:1646`,
  `:1655`) and `NODE_TEXTURE_MAPPING` with its derivative (`:1628`, `:1637`); the switch lists all six
  (`src/cycles/svm_nodes.toml:66-69`, `:95-96`) and the evaluators `kernel/svm/tex_coord.h` and
  `kernel/svm/mapping.h` are vendored (`VENDORED.toml:1340`, `:771-772`) and included (`svm_nodes.toml:22`, `:40`).
  `FACTS.md:333-334` says the same ("NODE_TEX_COORD, NODE_MAPPING, NODE_TEXTURE_MAPPING yes"). The rule is therefore a
  check, not a change: step 1's greps print the counts of step 1.
- **Rule 2: the host class fragments are missing, and this card extracts one class and reuses another** (BRIEF.md:277-281:
  "batch 6: `MappingNode`"). At HEAD `MappingNode` has no fragment (`FACTS.md:334`: "MappingNode missing"): step 1
  counts 0 `VENDORED.toml` entries naming it. Its declaration is already vendored with `scene/shader_nodes.h`
  (`VENDORED.toml:835-836`, class at `third_party/cycles/scene/shader_nodes.h:413`); what is missing is the out-of-line
  code (step 3), added only through `tools/vendor_sync.py add-fragment` (R6). Batch 6's other node is the batch that is
  **already done**: `TextureCoordinateNode`'s five member fragments and its `node_define` are vendored
  (`VENDORED.toml:231-236`, `:3067`'s node's class at `:4026-4286` in the anchor list), because B8's three rows already
  use it (`B8-node-table-export.md:400-406`, the row and `_texture_coordinate_parameters`). So `FACTS.md:334`'s
  "TexCoord, Mapping: ... / MappingNode missing" is right, and this card adds no fragment for Texture Coordinate.
  The one further thing the batch needs is the `MappingNode`'s enum: its `Type` member is a `NodeEnum` of four names
  (`NODE_DEFINE(MappingNode)`, upstream `scene/shader_nodes.cpp:1830-1849`) whose Blender source is the node's
  `vector_type` RNA, not a socket (step 1's probe), so the row's getter maps it through B8's `enum_name`.
- **Rule 3: `node_table.py` gains batch 6's one new row, and Texture Coordinate's row is B8's** (BRIEF.md:282): the new
  row is `ShaderNodeMapping` → `mapping`; `ShaderNodeTexCoord` → `texture_coordinate` is B8's and this card changes no
  line of it (`B8-node-table-export.md:400-406`). The trap of the batch is that **`MappingNode`'s `Vector`, `Location`,
  `Rotation` and `Scale` are `SOCKET_IN_POINT`, not `SOCKET_IN_VECTOR`** (upstream `:1839-1842`), so B6's `POINT`
  parameter and linkable-input form is the one that carries them (`B6-shader-graph-api.md:217`), and Cycles'
  `TextureMapping::Type` has four names where Blender's `vector_type` has four identifiers in a different order
  (step 1's probe: `POINT`, `TEXTURE`, `VECTOR`, `NORMAL` against Cycles' `point`, `texture`, `vector`, `normal`).
- **Rule 4: each node has a golden test that passes B9's rule** (BRIEF.md:283). Two scenes, one per node, added to
  B9's `GOLDEN_SCENES` (`B9-golden-harness.md:147`, `:241`): an emission plane whose Emission is driven by the node from
  a Texture Coordinate node (`BRIEF.md:239-246`), rendered by Cycles at 1 sample in Raw view as a float32 EXR and by
  painterly at `max_depth=1`, `emission_gain=1`, `jitter=0`, `output_mode="scene_linear"`
  (`B9-golden-harness.md:216-228`, `:261-268`), decided by B9's pre-registered rule (`B9-golden-harness.md:318-337`:
  `max |P - C| <= BAND`, `BAND = 2.0**-30`). This card contributes the scenes and their exact exported lists; it
  contributes no pixel expectation and no tolerance, because both sides of the comparison are renders and the rule is
  B9's (decision 9, `BRIEF.md:78-79`).
  Batch 6 is the first batch whose nodes read **per-hit geometry**, so its scenes are also the first to need B3's
  `ShaderData` (`BRIEF.md:58-66`): `Texture Coordinate`'s `Generated` and `Object` outputs are `NODE_ATTR` and
  `NODE_TEX_COORD` evaluations over `sd->P`, `sd->N`, the object arrays and the `attributes_*` arrays, which is why this
  card's `Depends on:` names B3 and why `## Open for Opus` 3 records what the golden render can and cannot separate.

Nothing in the core changes: no kernel type, no scene API, no new knob (decision 8, `BRIEF.md:75-77`), so no image, no
K and no parity test of M3-M5 moves. The build-level change is rule 2's fragment extraction, which compiles
already-vendored code into the existing `shader_nodes` unit.

Which of the four bullets applies, per node (FACTS.md:333-334 is the current state of both rows; the file:line column is
this clone's HEAD):

| node | Blender idname | Cycles type | 1. vendor the evaluator | 2. host class fragments | 3. `node_table.py` row | 4. golden test |
|---|---|---|---|---|---|---|
| Texture Coordinate | `ShaderNodeTexCoord` | `texture_coordinate` | nothing to do: `NODE_TEX_COORD` at `VENDORED.toml:3067`, `svm_nodes.toml:95-96`; `kernel/svm/tex_coord.h` at `VENDORED.toml:1340` | nothing missing: `TextureCoordinateNode`'s five member fragments (`VENDORED.toml:231-236`) and its `node_define` (`:3070`'s entry; class at `scene/shader_nodes.h:4026-4043` upstream) | **B8's, unchanged** | **add** |
| Mapping | `ShaderNodeMapping` | `mapping` | nothing to do: `NODE_MAPPING` at `VENDORED.toml:1646`, `svm_nodes.toml:68`; `kernel/svm/mapping.h` at `VENDORED.toml:771-772` | **extract** `MappingNode`: definition `node_define/MappingNode.inc` (upstream `:1830-1849`), members ctor `:1851`, `constant_fold` `:1853-1862`, `compile(SVMCompiler)` `:1864-1876`, `compile(OSLCompiler)` `:1878-1882` | **add** | **add** |

So of the four bullets, bullet 1 applies to neither node (a check, step 1), bullet 2 applies to Mapping only (step 3),
bullet 3 applies to Mapping only (step 2), and bullet 4 applies to both (steps 5-7).

## Read first

- `CLAUDE.md` rules 1, 2 and 3 (scope; named knobs; PEP 8 with type hints and docstrings that state units);
  `AGENTS.md` "Expected values are evidence, not targets" and "Measured means reproducible".
- `docs/handoff/drafts/M6b/BRIEF.md` lines 274-293 (this card's mandate; `:287` is batch 6's two nodes), `:58-66`
  (decision 6, the `ShaderData` of an analytic or triangle hit and what `Texture Coordinate` reads from it), `:237-255`
  (B9's harness and rule), `:52-57` (the socket-name rule), `:75-79` and `:295-301` (the open questions).
- `docs/handoff/drafts/M6b/FACTS.md` §3.13 (`:324-339`, batch 6's line `:333-334`), §3.9 (`:281-289`: `PainterlyRay`,
  `PainterlyIntersection`, `painterly_triangle_shading_normal`, `painterly_analytic_normal`, and "there is no stored P,
  UV or global primitive id"), §3.7 (`:253-266`) and §6 gaps 4 and 5 (the missing UV/attribute arrays and the
  unvendored `shader_data.h`).
- `docs/handoff/drafts/M6b/N1-batch-01-value-rgb-math.md`: the table of `## Goal` (`:70-75`), the rows literal
  (`:186-204`), the getters (`:209-225`), the export literals of `## Steps` 5 (`:540-567`), the guard test's new
  expected set (`:594-608`) and `## Acceptance` (`:612-634`).
- `docs/handoff/drafts/M6b/B8-node-table-export.md`: `NodeRow` and the six names `node_table.py` exports (`:172-201`),
  B8's `ShaderNodeTexCoord` row and its getter (`:400-414`), the socket ladders (`:422-457`), the four `ENUM_ALIASES`
  (`:458-468`), `export_graph` (`:485-509`), the row-vs-definition regexes (`:574-589`) and the guard test a batch card
  must change (`:595-598`).
- `docs/handoff/drafts/M6b/B6-shader-graph-api.md`: the two methods (`:96-109`), the nine parameter socket types and
  the three float3 linkable forms `COLOR`, `VECTOR` and `POINT` (`:166-176`, `:211-213`), and the "no Python form"
  `ValueError` (`:221-222`).
- `docs/handoff/drafts/M6b/B9-golden-harness.md`: the harness's public names (`:135-151`, `GOLDEN_SCENES` at `:147`),
  the scene `build` (`:216-244`), the rule (`:318-337`) and the slow test that drives it (`:338-357`).
- `docs/handoff/drafts/M6b/B3-shader-data.md` if it is drafted at dispatch: it owns `painterly_svm_shader_setup`
  (`BRIEF.md:139-143`) and the `generated` array this card's `Generated` scene reads. This card calls none of its
  names; it only depends on them being filled.
- The vendored definitions whose rows this card transcribes, each read in full:
  `third_party/cycles/fragments/scene/shader_nodes_cpp/node_define/MappingNode.inc` (`mapping`; enum `Type` `:6-11`,
  inputs `Vector` `:13`, `Location` `:14`, `Rotation` `:15`, `Scale` `:16`, output `Vector` `:18`), and
  `node_define/TextureCoordinateNode.inc` (B8's row's source, unchanged).
- The vendored member fragments that make `MappingNode` the code Cycles compiles:
  `third_party/cycles/fragments/scene/shader_nodes_cpp/member/MappingNode.constant_fold.inc` (the
  `folder.all_inputs_constant()` branch that calls `svm_mapping`, and the `folder.fold_mapping(mapping_type)` else
  branch), `MappingNode.compile-SVMCompiler.inc` (`NODE_MAPPING` with `mapping_type` and the four float3 inputs) and
  `MappingNode.compile-OSLCompiler.inc`.
- `third_party/cycles/kernel/svm/mapping.h:16-40` (`svm_node_mapping`) and
  `third_party/cycles/kernel/svm/mapping_util.h:16-38` (`svm_mapping`'s four cases: `POINT` is
  `transform_direction(R, vector * scale) + location`, `TEXTURE` is `safe_divide(transform_direction_transposed(R,
  vector - location), scale)`, `VECTOR` is `transform_direction(R, vector * scale)`, `NORMAL` is
  `safe_normalize(transform_direction(R, safe_divide(vector, scale)))`).
- `third_party/cycles/kernel/svm/tex_coord.h:92-178` (`svm_node_tex_coord_eval`'s cases, `NODE_TEXCO_OBJECT` at
  `:102-115`, `NODE_TEXCO_NORMAL` at `:116-124`) and `:179-206` (`svm_node_tex_coord`, `svm_node_tex_coord_derivative`).
- `third_party/cycles/scene/constant_fold.cpp:573-593` (`ConstantFolder::fold_mapping`: the `is_zero(scale)` rule, the
  bypass when location and rotation are zero and scale is one, and the `NODE_MAPPING_TYPE_NORMAL` exception) — the rule
  a scene must not accidentally hit.
- `third_party/cycles/scene/shader_nodes.h:413-427` (`MappingNode`'s declaration: the `NODE_SOCKET_API` members and the
  two `compile` overrides) and `:63-88` (`TextureNode` and the `NODE_SOCKET_API_STRUCT_MEMBER` list of
  `tex_mapping.*`, which is how the texture nodes carry the same mapping).
- Upstream `intern/cycles/blender/shader.cpp`, read in the pinned checkout (never edited, not in this repo): the
  `ShaderNodeMapping` case `:568-571` (`mapping->set_mapping_type((NodeMappingType)b_node.custom1)`), and the
  `ShaderNodeTexCoord` case (`:1078-1093`) that B8 transcribes (`B8-node-table-export.md:385-387`).
- `tests/blender/conftest.py:22`, `:44-53` and `:62-73` (the add-on package and the `addon` fixture);
  `tests/blender_it/test_extension_it.py:53-64` (`_load_by_path`), `:76-101` (the skips) and `:149-154` (the isolated
  profile).
- `pyproject.toml:38-44` and `:48` (`testpaths`, `addopts`, the `slow` marker, ruff's `line-length` and
  `target-version`; `docs/handoff` is excluded from lint).
- The expected values of steps 1, 4 and 5: the probe quoted there, measured on this host with `bpy` 5.2.2.

## Create

- `tests/blender/test_sync_shader_batch_06.py`
- `tests/blender_it/golden_batch_06_scenes.py`
- `tests/blender_it/test_golden_batch_06.py`

`tests/blender_it/golden_batch_06_scenes.py` is a module, not a test: `--import-mode=importlib`
(`pyproject.toml:38-39`) collects only `test_*.py`, and the test file loads it by path with
`tests/blender_it/test_extension_it.py:53-64`'s `_load_by_path`.

## Modify

- `third_party/cycles/VENDORED.toml` and the five new
  `third_party/cycles/fragments/scene/shader_nodes_cpp/{node_define/MappingNode.inc,member/MappingNode.*.inc}` files of
  step 3 — **only** through `tools/vendor_sync.py`; a hand edit of `third_party/` is rejected by the auditor (R6).
- `src/blender/addon/sync/shader/node_table.py` (B8's file): batch 6's one new row in `NODE_TABLE` (step 2), after B8's
  four and batch 1's four, and the module docstring's sentence about which rows exist updated to name this batch.
- `tests/blender/test_sync_shader_node_table.py` (B8's file): the guard test of
  `B8-node-table-export.md:595-598`, `test_the_table_has_only_the_rows_this_card_adds`, now expects nine idnames —
  B8's four plus batch 1's four plus this card's one (step 8).

## Do not touch

- `third_party/cycles/kernel/**`, `src/cycles/svm_nodes.toml`, `src/cycles/fragment_units.toml`: rule 1 is satisfied at
  HEAD (step 1) and `MappingNode`'s fragments need no further header — `mapping_util.h` is already an include of the
  unit's file through `svm_nodes.toml`'s evaluator list, and `svm_mapping` is declared in `mapping_util.h:16`, which
  `scene/shader_nodes.cpp:35` includes upstream and which this card checks is reachable (step 3). If it is not,
  `report_blocked` rather than adding an include outside this card's list.
- `src/painterly/**`: nothing in the core is batch 6's. B3 owns `painterly_svm_shader_setup` and the device scene's
  Cycles arrays (`BRIEF.md:137-149`), and `painterly_trace_pixel` (B4) already evaluates any compiled graph.
- `src/blender/addon/sync/shader/export.py`: B8's rule 4 is generic — a row is data and `export_graph` reads it
  (`B8-node-table-export.md:485-509`), and this card's row is data only.
- B8's `ShaderNodeTexCoord` row and `_texture_coordinate_parameters` (`B8-node-table-export.md:400-414`): Texture
  Coordinate's row is B8's, and this card's golden test uses it without changing it.
- `src/blender/addon/sync/shader/flatten.py`, `src/blender/addon/sync/{__init__,material,world,geometry}.py`: B7's and
  B8's.
- `tests/blender_it/golden_scenes.py`, `golden_rule.py`, `render_golden.py`, `test_golden.py`: B9's. This card adds one
  module beside them and two `GOLDEN_SCENES` entries (`B9-golden-harness.md:241`).
- `tests/blender_it/test_extension_it.py` and `tests/blender_it/run_reference.py`: T4.4's.
- `Makefile`, `pyproject.toml`, `src/blender/CMakeLists.txt`, `src/test/CMakeLists.txt`: no new target, no new marker,
  no new C++ source.
- `NODE_TABLE` beyond this card's one row, and every other batch's golden scene.
- `docs/spec.md`, `docs/plan.md`, `CLAUDE.md`, `AGENTS.md`, `BACKLOG.md`, `docs/handoff/` beyond this card's own file.

## Interface

Not a CONTRACT: this card adds no public name to `_painterly`, no Python API of the add-on and no C++ declaration. The
two interfaces it uses are B8's (the row) and B6's (the node tuple).

**The one new row** (`src/blender/addon/sync/shader/node_table.py`, B8's `NodeRow`,
`B8-node-table-export.md:179-185`):

```python
NODE_TABLE: Final[Mapping[str, NodeRow]] = {
    # ... B8's four rows and batch 1's four, unchanged. B8's ShaderNodeTexCoord row is batch 6's other
    # node and stays exactly as B8 wrote it (B8-node-table-export.md:400-406).
    # MappingNode.inc:3-18. `Type` is the `NodeEnum` of :6-11; the four inputs are POINT sockets, so
    # B6's POINT form carries them, and the output is a POINT too. Blender's node has a `vector_type`
    # RNA and no enum socket (step 1's probe).
    "ShaderNodeMapping": NodeRow(
        "mapping", ("Vector", "Location", "Rotation", "Scale"), ("Vector",), _mapping_parameters),
}
```

The getter:

```python
def _mapping_parameters(node: bpy.types.Node) -> dict[str, object]:
    """Cycles' `mapping_type`: Blender's `vector_type` RNA as a `NodeEnum` name (MappingNode.inc:6-11)."""
    return {"mapping_type": enum_name(node.vector_type)}
```

`enum_name` is B8's (`B8-node-table-export.md:458-468`), so `POINT` becomes `point`, `TEXTURE` becomes `texture`,
`VECTOR` becomes `vector` and `NORMAL` becomes `normal` — the four names of `MappingNode.inc:7-10`, in Blender's own
order (step 1's probe). No `ENUM_ALIASES` entry is needed, because each identifier's lowercase is already its Cycles
name.

**What this card consumes from B9.** B9's card is drafted (`docs/handoff/drafts/M6b/B9-golden-harness.md`) and its
surface is `GOLDEN_SCENES: dict[str, Callable[[], bpy.types.Scene]]` (`:147`), `build(**variant)` (`:144`),
`render_golden.py`'s `<out_dir>/{cycles.npy, painterly.npy, golden.json, <scene>.blend}` (`:166-177`) and
`golden_rule.meets_rule` (`:163`). This card adds two builders to its own module and two `GOLDEN_SCENES` entries; it
calls no `assert_golden`, because B9's drafted interface has no such function (`## Open for Opus` 2).

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
   - B8's Texture Coordinate row is the one this card's Texture Coordinate scene uses. Each prints `1`.
     ```
     grep -c 'ShaderNodeTexCoord' src/blender/addon/sync/shader/node_table.py
     grep -c 'def _texture_coordinate_parameters' src/blender/addon/sync/shader/node_table.py
     ```
   - B3 landed: the `generated` array the `Generated` scene reads is filled. This prints `1`:
     ```
     grep -c 'painterly_svm_shader_setup' src/painterly/kernel/svm/shader_data.h
     ```
     and this prints `1` per array B3 fills (`BRIEF.md:144-146`):
     ```
     grep -c 'attributes_float3' src/painterly/scene/device_scene.cpp
     grep -c 'tri_vindex' src/painterly/scene/device_scene.cpp
     ```
   - B9 landed, with the harness names of `## Interface`. Each prints `1`.
     ```
     grep -c 'GOLDEN_SCENES: dict' tests/blender_it/golden_scenes.py
     grep -c 'def meets_rule' tests/blender_it/golden_rule.py
     grep -c 'golden_rule' tests/blender_it/test_golden.py
     ```
   - Rule 1 holds — the six cases and the two evaluator headers are vendored. Each prints the number after it.
     ```
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_TEX_COORD"' third_party/cycles/VENDORED.toml               # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_TEX_COORD_DERIVATIVE"' third_party/cycles/VENDORED.toml    # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_MAPPING"' third_party/cycles/VENDORED.toml                 # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_MAPPING_DERIVATIVE"' third_party/cycles/VENDORED.toml      # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_TEXTURE_MAPPING"' third_party/cycles/VENDORED.toml         # 1
     grep -c 'dest = "kernel/svm/tex_coord.h"' third_party/cycles/VENDORED.toml                                 # 1
     grep -c 'dest = "kernel/svm/mapping.h"' third_party/cycles/VENDORED.toml                                   # 1
     grep -c 'dest = "kernel/svm/mapping_util.h"' third_party/cycles/VENDORED.toml                              # 1
     ```
   - Rule 2 holds — `MappingNode` has no fragment yet and `TextureCoordinateNode` has all of its own. These print `0`:
     ```
     grep -c 'shader_nodes_cpp/member/MappingNode\.' third_party/cycles/VENDORED.toml                  # 0
     grep -c 'shader_nodes_cpp/node_define/MappingNode"' third_party/cycles/VENDORED.toml              # 0
     ```
     and these print `5` and `1`, because Texture Coordinate's fragments are already vendored:
     ```
     grep -c 'shader_nodes_cpp/member/TextureCoordinateNode\.' third_party/cycles/VENDORED.toml        # 5
     grep -c 'shader_nodes_cpp/node_define/TextureCoordinateNode"' third_party/cycles/VENDORED.toml    # 1
     ```
     and this prints `1`, because the declaration comes with `scene/shader_nodes.h` (`VENDORED.toml:835-836`):
     ```
     grep -c '^class MappingNode : public ShaderNode' third_party/cycles/scene/shader_nodes.h           # 1
     ```
   - `svm_mapping`'s header is already reachable from the generated unit, so step 3 adds no `includes` entry. This
     prints `1`:
     ```
     grep -c 'dest = "kernel/svm/mapping_util.h"' third_party/cycles/VENDORED.toml                     # 1
     ```
     and step 3's build is what proves the unit compiles; if it does not, that is a `report_blocked`, not an include
     this card may add (see `## Do not touch`).
   - The bpy facts rules 3 and 4 rest on. Save this probe as a file under `/tmp` and run it with
     `.venv/bin/python <file>`; it must print exactly the lines quoted after it (they are this card's measurement on
     bpy 5.2.2, and the row and the two scenes of steps 2, 5 and 6 are derived from them):
     ```python
     import bpy

     mat = bpy.data.materials.new("probe")
     mat.use_nodes = True
     tree = mat.node_tree
     tree.nodes.clear()

     mapping = tree.nodes.new("ShaderNodeMapping")
     print("mapping inputs ", [(s.identifier, s.type, s.is_unavailable) for s in mapping.inputs])
     print("mapping outputs", [(s.identifier, s.type, s.is_unavailable) for s in mapping.outputs])
     print("mapping defaults", [(s.identifier, tuple(s.default_value)) for s in mapping.inputs])
     print("mapping rna", sorted(p.identifier for p in mapping.bl_rna.properties
                                 if not p.is_readonly and p.identifier == "vector_type"))
     print("vector_type", mapping.vector_type,
           [i.identifier for i in mapping.bl_rna.properties["vector_type"].enum_items])
     for value in ("POINT", "TEXTURE", "VECTOR", "NORMAL"):
         mapping.vector_type = value
         print("vector_type", value, "->", value.lower())

     coords = tree.nodes.new("ShaderNodeTexCoord")
     print("texcoord outputs", [(s.identifier, s.type) for s in coords.outputs])
     ```
     ```
     mapping inputs  [('Vector', 'VECTOR', False), ('Location', 'VECTOR', False), ('Rotation', 'VECTOR', False), ('Scale', 'VECTOR', False)]
     mapping outputs [('Vector', 'VECTOR', False)]
     mapping defaults [('Vector', (0.0, 0.0, 0.0)), ('Location', (0.0, 0.0, 0.0)), ('Rotation', (0.0, 0.0, 0.0)), ('Scale', (1.0, 1.0, 1.0))]
     mapping rna ['vector_type']
     vector_type POINT ['POINT', 'TEXTURE', 'VECTOR', 'NORMAL']
     vector_type POINT -> point
     vector_type TEXTURE -> texture
     vector_type VECTOR -> vector
     vector_type NORMAL -> normal
     texcoord outputs [('Generated', 'VECTOR'), ('Normal', 'VECTOR'), ('UV', 'VECTOR'), ('Object', 'VECTOR'), ('Camera', 'VECTOR'), ('Window', 'VECTOR'), ('Reflection', 'VECTOR')]
     ```
     (bpy prints one `DeprecationWarning` about `use_nodes` on stderr; it is not part of the output above.)
     What each line fixes:
     - `MappingNode`'s four inputs are `Vector`, `Location`, `Rotation` and `Scale` and its one output `Vector`, in
       Cycles' order (`MappingNode.inc:13-18`); the four are `VECTOR` in bpy and `SOCKET_IN_POINT` in Cycles
       (`:13-16`), which is why the row's names are Cycles' UI names and B6's `POINT` form is the one that carries a
       value.
     - `Scale`'s Blender default is `(1.0, 1.0, 1.0)` and Cycles' is `one_float3()` (`MappingNode.inc:16`); `Location`
       and `Rotation` are zero in both (`:14-15`, `zero_float3()`), and `Vector`'s zero is Cycles' `zero_float3()`
       (`:13`). The export carries Blender's values, as batch 1's card derives for `Emission`
       (`N1-batch-01-value-rgb-math.md:571-578`).
     - the node's only settable RNA is `vector_type`, and its four identifiers lowercase exactly onto
       `MappingNode.inc:7-10`'s four `NodeEnum` names, so `enum_name(node.vector_type)` needs no alias and step 4
       pins the mapping.
     - `ShaderNodeTexCoord`'s seven outputs are B8's row's (`B8-node-table-export.md:403-406`), and the two this
       card's scenes use, `Generated` and `Object`, are both `VECTOR`.
2. `node_table.py`, the one new row of `## Interface`, transcribed from the vendored definition: `cycles_type` is
   `NodeType::add`'s first argument (`MappingNode.inc:3`), `inputs`/`outputs` are the `SOCKET_IN_*`/`SOCKET_OUT_*` UI
   names in file order, and the parameter is the `SOCKET_ENUM` member a caller sets. Measured, from step 1's probe and
   the file:
   ```
   ShaderNodeMapping: 'mapping', inputs=['Vector', 'Location', 'Rotation', 'Scale'], outputs=['Vector']
   ```
   - `MappingNode`'s parameter is `mapping_type` (`MappingNode.inc:6-11`), Cycles' `Type` enum, whose Blender source is
     `vector_type` (`shader.cpp:568-571` maps `b_node.custom1`, Blender's enum integer, to the same
     `NodeMappingType`). The getter lowercases it through B8's `enum_name`.
   - `MappingNode` has no other settable member: its declaration's `NODE_SOCKET_API` list is the enum alone
     (`scene/shader_nodes.h:413-427`), and its `constant_fold`/`compile` read the sockets, not further members.
   - The docstring states rule 3, the file the row comes from and that a row's `cycles_type` is a Cycles type name, not
     a Blender idname (decision 5, BRIEF.md:52-55), and the sentence about which rows exist now names batch 6's one
     beside B8's four and batch 1's four.
3. `MappingNode`'s fragments, through `tools/vendor_sync.py` only (R6). The commands are `T6.7:2637-2643`'s shape, and
   the anchors are the ones `tools/vendor_sync.py list-anchors scene/shader_nodes.cpp` prints (the upstream line
   numbers in the table above are the same anchors' ranges):
   ```
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp node_define MappingNode
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp member \
       MappingNode::MappingNode MappingNode::constant_fold
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp member MappingNode::compile \
       --params SVMCompiler
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp member MappingNode::compile \
       --params OSLCompiler
   ```
   - One `node_define` fragment and four member fragments. This prints the counts after the commands:
     ```
     grep -c 'shader_nodes_cpp/member/MappingNode\.' third_party/cycles/VENDORED.toml        # 4
     grep -c 'shader_nodes_cpp/node_define/MappingNode"' third_party/cycles/VENDORED.toml    # 1
     ```
   - No `includes` entry is needed: `MappingNode::constant_fold`'s `folder.fold_mapping(mapping_type)` is declared in
     `scene/constant_fold.h:59`, which `src/cycles/fragment_units.toml:12` already lists, and `MappingNode::compile`
     uses only `compiler.input_float3`/`compiler.output`. `svm_mapping` is `constant_fold.cpp`'s business, which is a
     whole vendored source (`src/cycles/CMakeLists.txt:171`), not a fragment.
   - `third_party/cycles/VENDORED.toml` and the new `.inc` files are `vendor_sync`'s output; `make vendor-check`
     (`CHECK`'s last step) proves the tree still matches the manifest.
4. `tests/blender/test_sync_shader_batch_06.py`, four tests. `bpy` only, no Blender run, no `.blend` on disk outside
   `tmp_path`, and every expected value a literal compared with exact equality, so no tolerance appears.
   - `test_the_mapping_row_is_the_vendored_node_definition`: parse `MappingNode.inc` with B8's regexes
     (`SOCKET_IN_[A-Z0-9_]+\(\s*\w+\s*,\s*"([^"]+)"`, the `SOCKET_OUT_` form and `NodeType::add\("([a-z_]+)"`,
     `B8-node-table-export.md:574-589`) and compare with the row. Expected (step 2's table):
     ```
     ShaderNodeMapping: 'mapping', inputs=['Vector', 'Location', 'Rotation', 'Scale'], outputs=['Vector']
     ```
     The file declares one further socket the row does not name, `SOCKET_ENUM(mapping_type, "Type", ...)`
     (`MappingNode.inc:6-11`), which the `SOCKET_IN_`/`SOCKET_OUT_` regexes do not match: that is the parameter, and
     step 2's getter is what covers it.
   - `test_the_mapping_type_is_a_cycles_node_enum_name`: step 1's four measured lines, as
     `[(value, enum_name(value)) for value in ("POINT", "TEXTURE", "VECTOR", "NORMAL")] ==
     [("POINT", "point"), ("TEXTURE", "texture"), ("VECTOR", "vector"), ("NORMAL", "normal")]`, plus the check that
     every identifier of `bl_rna.properties["vector_type"].enum_items` maps into `MappingNode.inc`'s four
     `type_enum.insert("...")` names — the same guard shape as batch 1's enum test
     (`N1-batch-01-value-rgb-math.md:528-531`), so a bpy that adds a projection fails here instead of exporting a name
     Cycles' `NodeEnum::exists` rejects.
   - the two export tests, one per scene: `test_the_texture_coordinate_scene_exports_these_lists` and
     `test_the_mapping_scene_exports_these_lists`. Each builds its scene with step 6's builder, writes it to `tmp_path`
     with `bpy.data.libraries.write`, loads it back with `bpy.data.libraries.load` (a reloaded `.blend` keeps every
     socket identifier, `B8-node-table-export.md:388-389`) and compares `export_graph(flatten_tree(tree))` with a
     literal. Measured, by running an implementation of steps 2-6 and B8's `export_graph` against bpy 5.2.2
     (`## Open for Opus` 3):
     ```
     texcoord_scene:
       ([('texture_coordinate', {'from_dupli': False}, {}),
         ('emission', {}, {'Strength': 1.0})],
        [(0, 'Generated', 1, 'Color'), (1, 'Emission', -1, 'Surface')])
     mapping_scene:
       ([('texture_coordinate', {'from_dupli': False}, {}),
         ('mapping', {'mapping_type': 'point'},
          {'Location': (0.5, 0.0, 0.0), 'Rotation': (0.0, 0.0, 0.0), 'Scale': (2.0, 2.0, 2.0)}),
         ('emission', {}, {'Strength': 1.0})],
        [(0, 'Object', 1, 'Vector'), (1, 'Vector', 2, 'Color'), (2, 'Emission', -1, 'Surface')])
     ```
     What each literal says:
     - the node order is the tree's own order, which the walk of `B7-flatten.md:264-282` keeps: `coords` first, then
       the batch-6 node, then `emit`, and `output` is not a node (B8's rule 4, `B8-node-table-export.md:490-495`).
     - `texcoord_scene`'s export is B8's own fixture E1 (`B8-node-table-export.md:626-640`) with its `Color` default
       gone, because this scene links `coords.Generated → emit.Color` where B8's fixture leaves the Emission's `Color`
       unlinked: this card's golden test is the first render of that graph. That is deliberate: batch 6's Texture Coordinate row is B8's, so
       the export needs no new literal and the golden test is what batch 6 adds for that node.
     - `mapping_scene` exports `Location`, `Rotation` and `Scale` because all three are unlinked, and not `Vector`
       (linked from `coords.Object`). `Rotation` is at Blender's zero default and is exported anyway: B8's
       `export_graph` exports every unlinked default a row names (`B8-node-table-export.md:497-503`), and Cycles'
       default is `zero_float3()` too (`MappingNode.inc:15`), so the two engines agree on it and the literal pins it.
     - the Emission's `Color` is linked in both scenes, so only its `Strength` is exported, at Blender's `1.0`
       (`EmissionNode.inc:6`'s Cycles default is `10.0`).
5. `tests/blender_it/golden_batch_06_scenes.py`, the two scenes (BRIEF.md:239-246). Each builder makes one
   `bpy.data.materials` material whose tree is: `ShaderNodeOutputMaterial` `output`; `ShaderNodeTexCoord` `coords`;
   the batch-6 node; `ShaderNodeEmission` `emit`; and the links that make the node drive the emission. The plane
   itself is B9's harness's (`B9-golden-harness.md:216-228`); this module supplies the material.
   - `texcoord_scene`: `coords.Generated → emit.Color`, `emit.Emission → output.Surface`, the Emission's `Strength` at
     its default `1.0`. This is B9's own scene (`B9-golden-harness.md:21-25`, `texcoord_generated`) and batch 6's
     Texture Coordinate golden test: B9 renders it as its harness check, and this card's test asserts the same rule on
     the same scene. `## Open for Opus` 4 records that the two are one scene.
   - `mapping_scene`: `ShaderNodeMapping` `mapping` with `Location = (0.5, 0.0, 0.0)` and `Scale = (2.0, 2.0, 2.0)`
     (both explicit, so the export carries them and the SVM's `NODE_MAPPING` case has a non-trivial transform), and
     `coords.Object → mapping.Vector`, `mapping.Vector → emit.Color`, `emit.Emission → output.Surface`. Why not fold:
     `Vector` is linked from the Texture Coordinate node, so `ConstantFolder::all_inputs_constant` is false
     (`constant_fold.cpp:20-29`) and `MappingNode::constant_fold`'s else branch calls
     `folder.fold_mapping(mapping_type)` (`MappingNode.constant_fold.inc`), whose bypass rule
     (`constant_fold.cpp:573-593`) needs location and rotation zero and scale one — and this scene's `Location` is
     `(0.5, 0, 0)` and `Scale` is `(2, 2, 2)`, so neither the `is_zero(scale_in)` branch nor the bypass can fire. The
     node therefore stays in the SVM and its `POINT` case (`mapping_util.h:24-25`) is the one evaluated.
   - Each builder returns the material, so the harness can write it and step 4's export test can read it.
6. `tests/blender_it/test_golden_batch_06.py`, two tests, one per scene, each `@pytest.mark.slow` (CLAUDE.md rule 6;
   the harness renders twice per scene):
   - `test_the_texture_coordinate_node_matches_cycles` and `test_the_mapping_node_matches_cycles`. Each loads its
     builder from step 5's module with `_load_by_path` (`tests/blender_it/test_extension_it.py:53-64`), registers it
     under its name in `GOLDEN_SCENES` (`B9-golden-harness.md:241`), runs B9's `render_golden.py` as a subprocess with
     the isolated profile of `test_extension_it.py:149-154`, reads `cycles.npy`/`painterly.npy`/`golden.json`, and
     asserts `golden_rule.meets_rule(painterly, cycles)` with `max_abs_difference` in the failure message. The rule is
     B9's (`B9-golden-harness.md:318-337`) and this card states no tolerance, no band and no expected pixel value.
   - Each test skips with B9's own reason when its inputs are missing (`BLENDER` unset or no extension zip,
     `test_extension_it.py:76-101`), so `make blender-it` stays green on a machine without Blender.
   - The `texcoord_scene` test also asserts `golden.json`'s two engine ids and its size, as B9's own harness test does
     (`B9-golden-harness.md:351-356`), so a scene that silently rendered with one engine fails here.
7. `tests/blender/test_sync_shader_node_table.py`, B8's guard test
   (`test_the_table_has_only_the_rows_this_card_adds`, `B8-node-table-export.md:595-598`): its expected set grows from
   eight idnames to nine.
   ```
   set(NODE_TABLE) == {"ShaderNodeOutputMaterial", "ShaderNodeOutputWorld", "ShaderNodeEmission",
                       "ShaderNodeTexCoord", "ShaderNodeValue", "ShaderNodeRGB", "ShaderNodeMath",
                       "ShaderNodeVectorMath", "ShaderNodeMapping"}
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
   the previous card's and must not move; the pytest count grows by step 4's four tests. `CHECK`'s `vendor-check` step
   is what proves step 3's manifest is consistent.
2. `make test-blender` exits 0. Report its last line.
3. `.venv/bin/python -m pytest tests/blender/test_sync_shader_batch_06.py -q` prints `4 passed`: step 4's
   `1 + 1 + 2 = 4`. The count is the number of test functions step 4 lists; if it prints another count, the card's
   count is wrong and that is a finding, not a tolerance.
4. `.venv/bin/python -m pytest tests/blender/test_sync_shader_node_table.py -q` prints `6 passed`. The count is B8's
   own (`B8-node-table-export.md:571-603`): the row-vs-definition test, the two ladder tests, the enum test, the guard
   test and the unknown-idname test are `1 + 2 + 1 + 1 + 1 = 6`. This card changes only the guard's expected set
   (step 7), so the count must not move; if it prints another count, a test arrived or vanished in that file.
5. `make blender-it` exits 0. Report its last line, the collected and passed counts, and the two golden tests'
   statistics as the harness prints them. This card states no count for the file set, because the total is B9's to fix
   and not this card's, and each test skips with B9's reason when its inputs are missing.
6. `git status --porcelain` lists only the three Create paths and the three Modify paths above.

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- name the Mapping row's inputs `Vector`, `Location`, `Rotation`, `Scale` as `SOCKET_IN_VECTOR`-style names without
  the POINT form → step 4's row-vs-definition test still passes (the names are Cycles'), but a golden render of
  `mapping_scene` fails at `add_shader` with B6's `ValueError`, because `MappingNode`'s four inputs are `POINT`
  sockets and B6's `POINT` form is the one that carries a value (`B6-shader-graph-api.md:211-213`);
- export `mapping_type` as `node.vector_type` without `enum_name` → step 4's enum test and `mapping_scene`'s literal
  both fail (`'mapping_type': 'POINT'`), and `add_shader` raises B6's `ValueError` naming the enum
  (`B6-shader-graph-api.md:221-222`);
- set the mapping scene's `Location` to zero and its `Scale` to one → `ConstantFolder::fold_mapping`'s bypass fires
  (`constant_fold.cpp:583-592`) and the graph folds, so the golden test compares two folded constants and proves
  nothing about the node;
- link `coords.Generated` instead of `coords.Object` in `mapping_scene` → the scene still renders, but it then reads the
  `attributes_float3` array B3 fills (`BRIEF.md:144-146`) rather than the object transform, and the two properties the
  scene is meant to test (`sd->P` and the `NODE_MAPPING` transform) are no longer separable; `## Open for Opus` 3
  records why the scene uses `Object`;
- forget step 7 → `make test-blender` fails B8's guard test with the one missing idname;
- drop `MappingNode::constant_fold` from step 3 → the unit does not define the symbol `MappingNode::constant_fold` that
  `scene/constant_fold.cpp`'s `ConstantFolder` calls for the node's type, and `make build` fails at link time.

Report: the doctest and pytest counts, the audit line, the two golden statistics and every mutation you ran with its
first failing check.

## Commit

`N6: node batch 6: Texture Coordinate and Mapping — MappingNode's fragments, one node_table row and two golden tests`

## Open for Opus

1. **Batch 6's Texture Coordinate needs no work, so the batch is really one node.** `FACTS.md:333-334`'s
   "TexCoord, Mapping: … / MappingNode missing" and B8's three rows (`B8-node-table-export.md:390-407`) mean that
   Texture Coordinate's row, its fragments and its export already exist; what batch 6 adds for it is its golden test,
   which B9's harness scene (`B9-golden-harness.md:21-25`, `texcoord_generated`) already renders. The options: (a) this
   card's, one golden test for the node beside B9's harness test, both on the same scene, which costs a second render
   of the same scene in `make blender-it`; (b) the Texture Coordinate test is dropped and B9's harness test counts as
   batch 6's, which saves a render but makes B9's card the owner of a node batch's acceptance; (c) the two are merged by
   giving B9's harness test a batch-6 name. (a) is the honest reading of `BRIEF.md:283` ("each has a golden test") and
   is what the steps implement; Opus may prefer (b) for the render time.
2. **B9's interface has no `assert_golden`.** B9's drafted card gives `GOLDEN_SCENES` (`B9-golden-harness.md:147`),
   `build(**variant)` (`:144`), `render_golden.py` (`:166-177`) and `golden_rule.meets_rule` (`:163`), and its slow
   test drives them (`:338-357`). Batch 1's card assumed one `assert_golden(scene, name, tmp_path)`
   (`N1-batch-01-value-rgb-math.md:243`, `:669-676`) because B9 was not drafted when it was written. This card follows
   B9 as drafted and writes its own two tests; the alternatives are (a) B9 gains the wrapper and every batch card calls
   it, or (b) each batch card writes its own test as this one does. Batch 1's card, the template, should be reconciled
   with whichever is chosen.
3. **The `mapping_scene` reads `sd->P` through `Object`, which B3 owns.** `Texture Coordinate`'s `Object` output is
   `NODE_TEXCO_OBJECT`: `shading_position<Float3Type>(sd)` then
   `object_inverse_position_transform_if_object(kg, sd, &data)` (`kernel/svm/tex_coord.h:102-115`), and for a painterly
   triangle hit `sd->object` is the painterly object index (decision 6, `BRIEF.md:61-63`) while the object's inverse
   transform is Cycles' `objects` array, which B3 fills (`BRIEF.md:144-146`). A render comparison therefore tests B3's
   array as much as the node. The alternatives: (a) this card's, `Object` into `Mapping`, which is the scene that
   exercises the `POINT` transform on a per-hit position; (b) `Generated` into `Mapping`, which reads
   `attributes_float3` instead and tests B3's other array; (c) two scenes, one per output, doubling the render cost.
   No expected value of this card depends on the choice: the export literal of step 4 and the golden rule are the same
   for all three.
4. **`texcoord_scene` is B9's own scene.** B9's harness check renders an Emission of Texture Coordinate's `Generated`
   output (`B9-golden-harness.md:21-25`), which is exactly batch 6's Texture Coordinate golden scene. The two tests
   therefore render the same scene twice in `make blender-it`. The alternatives are 1's; this card keeps the duplicate
   because `BRIEF.md:283` gives each node of a batch its own golden test, and because B9's test is the harness's own
   check of its rule rather than a node batch's acceptance.
5. **`Parallel-safe: no`, against the plan's row.** `FACTS.md:362` records the plan's row as
   `"Node batch i of 12: <name> (node-table rows and golden tests; parallel-safe)"`, but every batch card edits the
   same literal in B8's guard test (`B8-node-table-export.md:595-598`, this card's step 7). The options are batch 1's
   `## Open for Opus` 3's: keep `no` (this card) and run the batches in sequence, or replace the guard with a
   per-batch subset assertion.
6. **What this card does not decide.** Per `BRIEF.md:295-301`: light node graphs stay out of v1; whether a node
   material's emission is scaled by `emission_scale` is open, and this card passes no knob (decision 8); Bump, Normal
   Map and the Attribute node are out. `Texture Coordinate`'s `Normal`, `UV`, `Camera`, `Window` and `Reflection`
   outputs are B8's row's and this card's scenes do not drive them: `Normal` reads `sd->N` and the smooth-normal
   arrays (`tex_coord.h:116-124`), `UV` needs B3's `attributes_float2` (`BRIEF.md:144-146`), and `Camera`, `Window`
   and `Reflection` need `kernel_data.cam` and the ray differentials painterly does not carry (decision 6,
   `BRIEF.md:64`). A later batch's card that needs them is where their golden tests belong.
