# N1 — Node batch 1: Value, RGB, Math and Vector Math (the template for the other batches)

Milestone: M6b · Depends on: B8, B9 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "Node batches" (lines 274-293, batch 1 at `:285`), per that
brief's section 4 (lines 303-324) and the decisions of its section 1 that touch it: decision 5 (`:52-57`, node types by
Cycles type name, links and linkable defaults by UI name, parameters by member name with enums by `NodeEnum` name),
decision 8 (`:75-77`, no new knob) and decision 9 (`:78-79`, every expected value is an exact equality or a derived
rule). Code facts are `docs/handoff/drafts/M6b/FACTS.md` §3.13 (`:324-339`, what Cycles-side code exists per batch, with
batch 1's state at `:329`) and §3.7 (`:253-266`, the build targets), re-read at this clone's HEAD in every file cited
below. The bpy facts are measured on this host with the project's `bpy` 5.2.2 by the probe of step 1, quoted with
its output, and the four export literals of step 5 by the prototype of `## Open for Opus` 2.

`BRIEF.md:274-283` gives every node of the six core batches the same four bullets; this card turns each bullet into a
rule in `## Goal`, states for each of batch 1's four nodes whether the bullet applies, and gives every expected value
its derivation. This card is the template `DRAFT-M6b-N5` copies (`BACKLOG.md:1062-1070`, FOLLOWUPS:93-94 at
`FACTS.md:56`).

## Goal

Batch 1's four nodes are exported, compiled and rendered through the whole M6b path, and each has a golden test against
Cycles:

- **Rule 1: the node's evaluator is vendored, and this card adds nothing to `third_party/`** (BRIEF.md:276). For batch 1
  the bullet is already satisfied at HEAD: the four kernel cases `NODE_VALUE_F`, `NODE_VALUE_V`, `NODE_MATH` and
  `NODE_VECTOR_MATH` are in `src/cycles/svm_nodes.toml:55-62` and in `third_party/cycles/VENDORED.toml` at `:1529`,
  `:1547`, `:1574` and `:1583`, and the evaluator headers `kernel/svm/value.h` and `kernel/svm/math.h` are in
  `svm_nodes.toml:23,28` and `VENDORED.toml:643-652`. `FACTS.md:329` says the same ("1 Value, RGB, Math, VectorMath: cases yes / none missing").
  The rule is therefore a check, not a change: step 1's greps must print the counts of step 1, and this card writes no
  line of `src/cycles/` or `third_party/cycles/` (`third_party/` is `tools/vendor_sync.py`'s alone, R6).
- **Rule 2: the host class fragments are present, and this card adds none** (BRIEF.md:277-281). Batch 1's four host
  classes, `ValueNode`, `ColorNode`, `MathNode` and `VectorMathNode`, are extracted at HEAD (`FACTS.md:329`, "none
  missing"): the definition and every member fragment are vendored (step 1's count of `VENDORED.toml` entries, 4 + 4 +
  6 + 5). The three bullets BRIEF.md:277-281 names as missing — batch 5's `RGBRampNode`/`CurvesNode`/`RGBCurvesNode`,
  batch 6's `MappingNode`, batch 10's image classes — are not batch 1's, and no class of this batch is on that list.
- **Rule 3: `node_table.py` gains batch 1's four rows** (BRIEF.md:282): `ShaderNodeValue` → `value`, `ShaderNodeRGB` →
  `color`, `ShaderNodeMath` → `math`, `ShaderNodeVectorMath` → `vector_math`, each with the Cycles UI names of its
  linkable inputs and outputs and the getter for its parameters by member name (B8's `NodeRow`,
  `B8-node-table-export.md:179-201`). The two value nodes are the trap of the batch: Cycles reads their value from the
  node's **output** socket default (`blender/shader.cpp:177-185` for the colour, `:185-192` for the float, called at
  `:421-425` and `:432-436`), because in Cycles the value is a parameter (`SOCKET_FLOAT`, `ValueNode.inc:5`;
  `SOCKET_COLOR`, `ColorNode.inc:5`), while in Blender it is an output socket with no input. Math and Vector Math read
  their operation from Blender's `operation` RNA (Cycles' `SOCKET_ENUM(math_type, "Type", ...)`, `MathNode.inc:47`,
  `VectorMathNode.inc:41`) through B8's `enum_name`, and Math also reads `use_clamp` (Cycles' `SOCKET_BOOLEAN(use_clamp,
  "Use Clamp", false)`, `MathNode.inc:49`); Vector Math has no clamp (step 1's probe: `has use_clamp: False`).
- **Rule 4: each node has a golden test that passes B9's rule** (BRIEF.md:283). Four scenes, one per node, in
  `tests/blender_it/`: an emission plane whose Emission is driven by the node from a Texture Coordinate node
  (BRIEF.md:239-246), rendered by Cycles at 1 spp in Raw view as float32 EXR and by Painterly at `max_depth=1`,
  `emission_gain=1`, `jitter=0`, `output_mode="scene_linear"` (BRIEF.md:240-244), compared by the decision rule B9
  pre-registers (BRIEF.md:247-252). This card contributes the scenes and their exact exported lists; it contributes no
  pixel expectation and no tolerance, because both sides of the comparison are renders and the rule is B9's
  (BRIEF.md:247-252, decision 9 at `:78-79`).
  What a Value or RGB scene can prove is narrower than for Math and Vector Math, and honestly so: those two nodes have
  **no input socket** (step 1's probe), so `ConstantFolder::all_inputs_constant` is true for them
  (`constant_fold.cpp:20-29`) and `ValueNode::constant_fold`/`ColorNode::constant_fold` fold their value into the
  consumer's input on the host (`ValueNode.constant_fold.inc:1-4`, `ColorNode.constant_fold.inc:1-4`). Cycles does the
  same, so both engines carry the same constant, and `ColorNode::compile` then emits nothing because its output has no
  link left (`ColorNode.compile-SVMCompiler.inc:5-7`). The value reaches the SVM as the consumer's constant instead
  (`SVMCompiler::stack_assign`, `SVMCompiler.stack_assign-ShaderInput.inc:16-18`), which is what the node *is*: a
  number. The scene therefore pins the row's parameter and the folded value, not a per-pixel evaluation of the node,
  and `## Open for Opus` 5 records that limit.

Nothing in the core changes: no kernel type, no scene API, no new knob (decision 8, BRIEF.md:75-77), so no image, no K
and no parity test of M3-M5 moves. Rule 1's and rule 2's checks are what keeps that true: a batch card that had to
vendor or extract something would touch `src/cycles/` or `third_party/`, and this one does not.

Which of the four bullets applies, per node (FACTS.md:329 is the current state of all four rows; the file:line column is
this clone's HEAD):

| node | Blender idname | Cycles type | 1. vendor the evaluator | 2. host class fragments | 3. `node_table.py` row | 4. golden test |
|---|---|---|---|---|---|---|
| Value | `ShaderNodeValue` | `value` | nothing to do: `NODE_VALUE_F`/`NODE_VALUE_V` at `svm_nodes.toml:55-58`, `VENDORED.toml:1529-1564`; `kernel/svm/value.h` at `svm_nodes.toml:28`, `VENDORED.toml:643-644` | nothing missing: `ValueNode` definition `VENDORED.toml:1925`, `compile` `:2072`, ctor `:2522`, `constant_fold` `:2531`; class `scene/shader_nodes.h:1160-1171` | **add** | **add** |
| RGB | `ShaderNodeRGB` | `color` | nothing to do: `NODE_VALUE_V` (`ColorNode::compile` emits a value node, `ColorNode.compile-SVMCompiler.inc:6`), `VENDORED.toml:1547-1564` | nothing missing: `ColorNode` definition `VENDORED.toml:1853`, `compile` `:1982`, ctor `:2324`, `constant_fold` `:2333`; class `scene/shader_nodes.h:1173-1184` | **add** | **add** |
| Math | `ShaderNodeMath` | `math` | nothing to do: `NODE_MATH` at `svm_nodes.toml:60`, `VENDORED.toml:1574`; `kernel/svm/math.h` at `svm_nodes.toml:23`, `VENDORED.toml:651-652` | nothing missing: `MathNode` definition `VENDORED.toml:1880`, `compile` `:2022`, ctor `:2432`, `expand` `:2441`, `constant_fold` `:2450`, `is_linear_operation` `:2459`; class `scene/shader_nodes.h:1512-1524` | **add** | **add** |
| Vector Math | `ShaderNodeVectorMath` | `vector_math` | nothing to do: `NODE_VECTOR_MATH` at `svm_nodes.toml:61`, `VENDORED.toml:1583`; `kernel/svm/math.h` at `svm_nodes.toml:23`, `VENDORED.toml:651-652` | nothing missing: `VectorMathNode` definition `VENDORED.toml:1934`, `compile` `:2082`, ctor `:2540`, `constant_fold` `:2549`, `is_linear_operation` `:2558`; class `scene/shader_nodes.h:1538-1553` | **add** | **add** |

So of the four bullets, bullets 1 and 2 apply to no node of this batch (both are checks that print counts, step 1) and
bullets 3 and 4 apply to all four nodes (steps 2-6).

## Read first

- `CLAUDE.md` rules 1, 2 and 3 (scope; named knobs; PEP 8 with type hints and docstrings that state units);
  `AGENTS.md` "Expected values are evidence, not targets".
- `docs/handoff/drafts/M6b/BRIEF.md` lines 274-293 (this card's mandate; `:285` is batch 1's four nodes), `:237-255`
  (B9, the harness and the pre-registered rule this card's golden tests use), `:52-57` (the socket-name rule), `:75-79`
  (no new knob; expected values are evidence) and `:295-301` (the open questions this card must not decide).
- `docs/handoff/drafts/M6b/FACTS.md` §3.13 (`:324-339`: the 31 registered `NODE_DEFINE` types `:325-328`, batch 1's
  line `:329`, and `:330-337` for the classes the later batches still miss) and §3.7 (`:253-266`: no production target
  links `cycles_svm`, which is why this card changes no build file).
- `docs/handoff/drafts/M6b/B8-node-table-export.md`: `NodeRow` and the six names `node_table.py` exports (`:172-201`),
  the three rows B8 writes, which are the shape this card's four copy (`:390-407`), the socket ladders transcribed from
  `shader.cpp:1212-1323` (`:422-431`) with the table measured on bpy 5.2.2 (`:432-457`), the four `ENUM_ALIASES`
  (`:458-484`), `export_graph`'s default export (`:485-503`), the row-vs-definition test's regexes (`:574-589`) and the
  guard test a batch card must change (`:595-598`).
- `docs/handoff/drafts/M6b/B7-flatten.md:255-300` (the `FlattenedTree` walk order the golden scenes' node order
  follows) and `:110-129` (`FlatNode`, `FlatLink`, `FlattenedTree`, `flatten_tree`).
- The vendored definitions whose rows this card transcribes, each read in full:
  `third_party/cycles/fragments/scene/shader_nodes_cpp/node_define/ValueNode.inc` (`value`, parameter `Value` default
  `0.0f`, output `Value`), `ColorNode.inc` (`color`, parameter `Value` default `zero_float3()`, output `Color`),
  `MathNode.inc` (`math`: 41 `type_enum.insert` names `:6-46`, `Type` `:47`, `Use Clamp` `:49`, `Value1`/`Value2`/`Value3`
  `:51-53`, output `Value` `:55`) and `VectorMathNode.inc` (`vector_math`: 30 names `:6-40`, `Type` `:41`,
  `Vector1`/`Vector2`/`Vector3`/`Scale` `:43-46`, outputs `Value` and `Vector` `:48-49`).
- The vendored member fragments that make the four nodes' code the code Cycles compiles:
  `ValueNode.compile-SVMCompiler.inc`, `ValueNode.constant_fold.inc`, `ColorNode.compile-SVMCompiler.inc` (a value node
  only when the colour output has a link, `:5-7`), `MathNode.compile-SVMCompiler.inc` (three float inputs and one
  output), `MathNode.expand.inc` (`use_clamp` inserts a `ClampNode` of `minmax` 0..1, `:3-13`),
  `MathNode.constant_fold.inc`, `VectorMathNode.compile-SVMCompiler.inc` (three `float3` inputs, `Scale`, and the two
  output offsets) and `VectorMathNode.constant_fold.inc`.
- `third_party/cycles/kernel/svm/math.h:13-45` (`svm_node_math`, `svm_node_vector_math`), `kernel/svm/math_util.h:121-207`
  (`svm_math`'s 41 cases) and `kernel/svm/value.h:16-30` (`svm_node_value_f`, `svm_node_value_v`).
- `third_party/cycles/scene/shader_graph.cpp`: `simplify` `:362-372`, `finalize` `:374-402`, `constant_fold` `:533-589`
  and `clean` `:801-851` — why a graph of constants folds on the host and a graph driven by Texture Coordinate does not
  (BRIEF.md:245-246). `third_party/cycles/scene/constant_fold.cpp:20-29` (`all_inputs_constant`), `:445-501`
  (`fold_math`) and `:503-573` (`fold_vector_math`) are the rules a scene must not accidentally hit.
- Upstream `intern/cycles/blender/shader.cpp`, read in the pinned checkout (never edited, not in this repo):
  `get_node_output_rgba` `:177-185`, `get_node_output_value` `:185-192`, `set_default_value` `:223-275`, the
  `ShaderNodeRGB` case `:421-425`, the `ShaderNodeValue` case `:432-436`, the `ShaderNodeMath` case `:538-542`
  (`math_type` from `custom1`, `use_clamp` from `custom2`) and the `ShaderNodeVectorMath` case `:544-548` (`math_type`
  from `custom1`), plus the socket ladders `:1212-1323` that B8 transcribes (`B8-node-table-export.md:422-457`).
- `tests/blender_it/test_extension_it.py` (the harness style this card's golden test follows: `_load_by_path`
  `:53-64`, the `BLENDER` and zip skips `:76-101`, `_run` `:104-112`, the isolated profile `:149-154`) and
  `tests/blender_it/run_reference.py:1-40` (what a Blender-side script may assume). `Makefile:91-92`
  (`blender-it` runs `pytest tests/blender_it -m slow -q`) and `Makefile:73-74` (`test-blender` runs
  `pytest tests/blender -q`).
- `tests/blender/conftest.py:22` (`ADDON_DIR`), `:44-53` (the add-on is loaded as the package `painterly`, so a test
  imports `painterly.sync.shader.node_table`) and `:62-73` (the `addon` fixture).
- `pyproject.toml:38-44` (`testpaths`, `addopts`, the `slow` marker, ruff `line-length = 100`,
  `target-version = "py312"`) and `:48` (`extend-exclude` covers `docs/handoff`, so this draft is not linted).
- The expected values of steps 1, 2, 3, 6 and 7: the probes and the prototype quoted there, measured on this host with
  `bpy` 5.2.2.

## Create

- `tests/blender/test_sync_shader_batch_01.py`
- `tests/blender_it/golden_batch_01_scenes.py`
- `tests/blender_it/test_golden_batch_01.py`

`tests/blender_it/golden_batch_01_scenes.py` is a module, not a test: `--import-mode=importlib`
(`pyproject.toml:38-39`) collects only `test_*.py`, and both test files load it by path with
`tests/blender_it/test_extension_it.py:53-64`'s `_load_by_path`, which is how that file already loads
`tests/core/scenes.py` and `src/blender/addon/film.py` without running the add-on's `__init__.py`.

## Modify

- `src/blender/addon/sync/shader/node_table.py` (B8's file): batch 1's four rows in `NODE_TABLE` (step 2), in the order
  `ShaderNodeValue`, `ShaderNodeRGB`, `ShaderNodeMath`, `ShaderNodeVectorMath` after B8's four, and the module
  docstring's sentence about which rows exist updated to name this batch.
- `tests/blender/test_sync_shader_node_table.py` (B8's file): the guard test of
  `B8-node-table-export.md:595-598`, `test_the_table_has_only_the_rows_this_card_adds`, now expects eight idnames —
  B8's four plus this card's four (step 7). Nothing else in that file changes: its ladders, its enum test and its
  `PainterlyUnknownNode` test stay as they are, and `ShaderNodeBsdfPrincipled` is still the unknown node they use
  (batch 11's, BRIEF.md:289-290).

## Do not touch

- `third_party/cycles/**`, `src/cycles/**`: rule 1 and rule 2 are satisfied at HEAD (step 1), and `third_party/` is
  `tools/vendor_sync.py`'s alone (R6). A batch-1 step that wanted to vendor something would mean `FACTS.md:329` is
  wrong, which is a `report_blocked`, not a change.
- `src/painterly/**`: nothing in the core is batch 1's. `painterly_svm_collect` (batch 4's caller), the device update
  (B2) and the trace loop (B4) already evaluate any compiled graph; a node batch adds no kernel code (BRIEF.md:274-283
  names four bullets and none of them is C++).
- `src/blender/addon/sync/shader/export.py`: B8's rule 4 is generic — a row is data and `export_graph` reads it
  (`B8-node-table-export.md:485-503`), so a batch card that had to change `export.py` would mean B8's machinery is not
  row-driven.
- `src/blender/addon/sync/shader/flatten.py`, `src/blender/addon/sync/{__init__,material,world,geometry}.py`: B7's and
  B8's. The scenes of this card are built in Blender's Python and written to `tmp_path`; they go through no scene sync.
- `tests/blender_it/test_extension_it.py` and `tests/blender_it/run_reference.py`: T4.4's; B9's harness and this card's
  golden tests live beside them.
- `Makefile`, `pyproject.toml`, `src/blender/CMakeLists.txt`, `src/test/CMakeLists.txt`: no new target, no new marker,
  no new C++ source. B9 owns `make blender-it`'s definition and `tests/blender_it/`'s harness.
- `NODE_TABLE` beyond this card's four rows, and every other batch's golden scene: batch 5's, 6's, 10's, 11's and 12's
  rows and scenes are `DRAFT-M6b-N5`'s (BRIEF.md:286-292), and the six non-core batches' are the items D4 defers.
- `docs/spec.md`, `docs/plan.md`, `CLAUDE.md`, `AGENTS.md`, `BACKLOG.md`: normative or another agent's, and never a
  code card's. `docs/handoff/` too, except this card's own file, which is the fifth path of `## Create` and
  `## Modify` and the only doc a batch card writes: this card's whole diff is its three Create paths and its two
  Modify paths.

## Interface

Not a CONTRACT: this card adds no public name to `_painterly`, no Python API of the add-on and no C++ declaration. The
two interfaces it implements and consumes are B8's and B9's.

**The four rows** (`src/blender/addon/sync/shader/node_table.py`, B8's `NodeRow`,
`B8-node-table-export.md:179-185`):

```python
NODE_TABLE: Final[Mapping[str, NodeRow]] = {
    # ... B8's four rows (ShaderNodeOutputMaterial, ShaderNodeOutputWorld, ShaderNodeEmission,
    # ShaderNodeTexCoord), unchanged.
    # ValueNode.inc:3-6. `value` is a parameter (SOCKET_FLOAT), not a linkable input: Blender has no
    # input socket for it, and Cycles reads it from the node's output socket default
    # (blender/shader.cpp:185-192, :432-436).
    "ShaderNodeValue": NodeRow("value", (), ("Value",), _value_parameters),
    # ColorNode.inc:3-6. The same shape for the colour: SOCKET_COLOR `value`, output `Color`
    # (shader.cpp:177-185, :421-425).
    "ShaderNodeRGB": NodeRow("color", (), ("Color",), _color_parameters),
    # MathNode.inc:3-55. `math_type` is the `Type` enum and `use_clamp` the `Use Clamp` boolean; the
    # three inputs are floats and the one output a float.
    "ShaderNodeMath": NodeRow("math", ("Value1", "Value2", "Value3"), ("Value",), _math_parameters),
    # VectorMathNode.inc:3-49. No clamp: Cycles' definition has no such member (step 1's probe).
    "ShaderNodeVectorMath": NodeRow(
        "vector_math", ("Vector1", "Vector2", "Vector3", "Scale"), ("Value", "Vector"),
        _vector_math_parameters),
}
```

The four getters, each reading the RNA Cycles' own `add_node` reads:

```python
def _value_parameters(node: bpy.types.Node) -> dict[str, object]:
    """Cycles' `value` member (unitless): the float Blender stores on the node's Value output."""
    return {"value": float(node.outputs["Value"].default_value)}

def _color_parameters(node: bpy.types.Node) -> dict[str, object]:
    """Cycles' `value` member as a float3: the RGB of the node's Color output, alpha dropped."""
    return {"value": tuple(float(channel) for channel in node.outputs["Color"].default_value)[:3]}

def _math_parameters(node: bpy.types.Node) -> dict[str, object]:
    """Cycles' `math_type` (a NodeEnum name) and `use_clamp`."""
    return {"math_type": enum_name(node.operation), "use_clamp": bool(node.use_clamp)}

def _vector_math_parameters(node: bpy.types.Node) -> dict[str, object]:
    """Cycles' `math_type` (a NodeEnum name); Vector Math has no clamp."""
    return {"math_type": enum_name(node.operation)}
```

`enum_name` is B8's (`B8-node-table-export.md:458-468`), so `FRACT` becomes `fraction` and every other identifier
its own lowercase.

**What this card consumes from B9.** B9's card is not drafted yet (`docs/handoff/drafts/M6b/` holds B1, B4-B8 and B10),
so this card names what it needs and `## Open for Opus` 1 records that B9's own card is authoritative:

```python
# tests/blender_it/golden_batch_01_scenes.py
def value_scene() -> bpy.types.Material: ...
def rgb_scene() -> bpy.types.Material: ...
def math_scene() -> bpy.types.Material: ...
def vector_math_scene() -> bpy.types.Material: ...

# B9's harness, as this card calls it. One call per scene: it writes the scene's .blend into
# `tmp_path`, renders it in Cycles and in Painterly, applies B9's pre-registered rule and returns
# the measured statistic.
def assert_golden(scene: bpy.types.Material, name: str, tmp_path: Path) -> None: ...
```

The four scene builders are this card's (step 4). `assert_golden` is B9's; if B9 names it differently, only the four
call sites of step 6 change and no expected value of this card does (`## Open for Opus` 1).

## Steps

1. Preconditions. Each must hold; otherwise stop, commit nothing and report what you saw.
   - B8 landed: this prints `1` for each.
     ```
     grep -c 'NODE_TABLE: Final' src/blender/addon/sync/shader/node_table.py
     grep -c 'def enum_name' src/blender/addon/sync/shader/node_table.py
     grep -c 'def export_graph' src/blender/addon/sync/shader/export.py
     ```
     and this prints `4`: B8's four idnames, which are "four idnames, three Cycles rows, because the two output
     nodes share one row" (`B8-node-table-export.md:595-597`).
     ```
     grep -cE '"ShaderNode[A-Za-z]+": NodeRow\(' src/blender/addon/sync/shader/node_table.py   # 4
     ```
     A different number means B8's table is not the one steps 2 and 7 assume: read it and report what is there
     rather than adding a fifth row of B8's.
   - B8's guard test is still the one this card extends: this prints `1`.
     ```
     grep -c 'def test_the_table_has_only_the_rows_this_card_adds' tests/blender/test_sync_shader_node_table.py
     ```
   - B9 landed: this prints `1` (the harness module of `## Interface`, wherever B9 puts it under `tests/blender_it/`).
     ```
     grep -rl 'def assert_golden' tests/blender_it/ | wc -l
     ```
     If it prints `0`, B9 has not landed and this card's golden tests have nothing to call; stop and report, because
     `BRIEF.md:283` requires them to pass B9's rule and this card may not invent that rule (`## Open for Opus` 1).
   - Rule 1 holds — the evaluator cases and headers are vendored. Each prints the number after it.
     ```
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_VALUE_F"' third_party/cycles/VENDORED.toml          # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_VALUE_V"' third_party/cycles/VENDORED.toml          # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_MATH"' third_party/cycles/VENDORED.toml             # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_VECTOR_MATH"' third_party/cycles/VENDORED.toml      # 1
     grep -c 'dest = "kernel/svm/value.h"' third_party/cycles/VENDORED.toml                              # 1
     grep -c 'dest = "kernel/svm/math.h"' third_party/cycles/VENDORED.toml                               # 1
     grep -c '^  "NODE_VALUE_F",$\|^  "NODE_VALUE_V",$\|^  "NODE_MATH",$\|^  "NODE_VECTOR_MATH",$' src/cycles/svm_nodes.toml   # 4
     ```
     The four `NODE_*` names are also the four `SVM_CASE`s `third_party/cycles/kernel/svm/svm.h` dispatches to
     `svm_node_value_f`, `svm_node_value_v`, `svm_node_math` and `svm_node_vector_math` (`kernel/svm/value.h:16-30`,
     `kernel/svm/math.h:13-45`), which is what makes them evaluators rather than names.
   - Rule 2 holds — the four host classes' fragments are vendored. Each prints the number after it (the count of
     `VENDORED.toml` entries naming that class).
     ```
     grep -c 'name = "scene/shader_nodes_cpp/.*/ValueNode\.' third_party/cycles/VENDORED.toml        # 4
     grep -c 'name = "scene/shader_nodes_cpp/.*/ColorNode\.' third_party/cycles/VENDORED.toml        # 4
     grep -c 'name = "scene/shader_nodes_cpp/.*/MathNode\.' third_party/cycles/VENDORED.toml         # 6
     grep -c 'name = "scene/shader_nodes_cpp/.*/VectorMathNode\.' third_party/cycles/VENDORED.toml   # 5
     ```
     The trailing `\.` keeps each class's `node_define` line out of its count, so the number is that class's
     `member/` entries: `ValueNode`'s four at `VENDORED.toml:2072, 2222, 2522, 2531`; `ColorNode`'s four at
     `:1982, 2132, 2324, 2333`; `MathNode`'s six at `:2022, 2172, 2432, 2441, 2450, 2459`; `VectorMathNode`'s five at
     `:2082, 2232, 2540, 2549, 2558`. The four `node_define` entries are separate lines (`:1925, 1853, 1880, 1934`),
     and these print `1` each:
     ```
     grep -c 'name = "scene/shader_nodes_cpp/node_define/ValueNode"' third_party/cycles/VENDORED.toml        # 1
     grep -c 'name = "scene/shader_nodes_cpp/node_define/ColorNode"' third_party/cycles/VENDORED.toml        # 1
     grep -c 'name = "scene/shader_nodes_cpp/node_define/MathNode"' third_party/cycles/VENDORED.toml         # 1
     grep -c 'name = "scene/shader_nodes_cpp/node_define/VectorMathNode"' third_party/cycles/VENDORED.toml   # 1
     ```
   - The bpy facts rules 3 and 4 rest on. Save this probe as a file under `/tmp` and run it with
     `.venv/bin/python <file>`; it must print exactly the lines quoted after it (they are this card's measurement on
     bpy 5.2.2, and the rows, the ladders and the four scenes of steps 2-6 are derived from them):
     ```python
     import re

     import bpy

     NODE_DEFINE = "third_party/cycles/fragments/scene/shader_nodes_cpp/node_define"


     def node_enum(filename):
         text = open(f"{NODE_DEFINE}/{filename}", encoding="utf-8").read()
         return re.findall(r'type_enum\.insert\("([a-z_0-9]+)"', text)


     def rna_operations(idname):
         node = bpy.data.materials.new("probe").node_tree.nodes.new(idname)
         return [item.identifier for item in node.bl_rna.properties["operation"].enum_items]


     def input_candidates(identifier):
         name, ladder = identifier, [identifier]
         if name.startswith("Shader"):
             name = name.replace("Shader", "Closure", 1)
         ladder.append(name)
         if name.endswith(("_001", ".001")):
             name = name[:-4] + "2"
         elif name.endswith(("_002", ".002")):
             name = name[:-4] + "3"
         else:
             name += "1"
         ladder.append(name)
         return tuple(dict.fromkeys(ladder))


     tree = bpy.data.materials.new("probe").node_tree
     tree.nodes.clear()

     value = tree.nodes.new("ShaderNodeValue")
     value.outputs["Value"].default_value = 0.25
     print("value:", {"value": value.outputs["Value"].default_value},
           "| inputs:", [s.identifier for s in value.inputs])

     rgb = tree.nodes.new("ShaderNodeRGB")
     rgb.outputs["Color"].default_value = (0.25, 0.5, 0.75, 1.0)
     print("rgb:", {"value": tuple(rgb.outputs["Color"].default_value)},
           "| inputs:", [s.identifier for s in rgb.inputs])

     math = tree.nodes.new("ShaderNodeMath")
     math.operation = "MULTIPLY"
     print("math:", {"math_type": math.operation, "use_clamp": math.use_clamp})
     print("math FRACT ->", math.bl_rna.properties["operation"].enum_items["FRACT"].identifier,
           "| enum name", "fract")
     print("math input defaults:", [(s.identifier, s.default_value) for s in math.inputs])
     math.operation = "MULTIPLY_ADD"
     print("math MULTIPLY_ADD inputs:", [(s.identifier, s.is_unavailable) for s in math.inputs])
     math.operation = "ADD"
     vmath = tree.nodes.new("ShaderNodeVectorMath")
     vmath.operation = "DOT_PRODUCT"
     print("vector math:", {"math_type": vmath.operation}, "| has use_clamp:",
           "use_clamp" in dir(vmath))

     for node in (value, rgb, math, vmath):
         print("inputs ", node.bl_idname, [(s.identifier, s.is_unavailable) for s in node.inputs])
         print("outputs", node.bl_idname, [(s.identifier, s.is_unavailable) for s in node.outputs])

     for identifier in ("Value", "Value_001", "Value_002"):
         print("in ShaderNodeMath", identifier, input_candidates(identifier))
     for identifier in ("Vector", "Vector_001", "Vector_002", "Scale"):
         print("in ShaderNodeVectorMath", identifier, input_candidates(identifier))
     for identifier in ("Value", "Color"):
         print("out ladder", identifier, (identifier,))

     for idname, filename in (("ShaderNodeMath", "MathNode.inc"),
                              ("ShaderNodeVectorMath", "VectorMathNode.inc")):
         identifiers = rna_operations(idname)
         names = node_enum(filename)
         lowered = [identifier.lower() for identifier in identifiers]
         print(f"{idname}: RNA {len(identifiers)}, NodeEnum {len(names)}, lowercase alone "
               f"{len([name for name in lowered if name in names])}, "
               f"unmapped {[name for name in lowered if name not in names]}, "
               f"unused {[name for name in names if name not in lowered]}")
     ```
     ```
     value: {'value': 0.25} | inputs: []
     rgb: {'value': (0.25, 0.5, 0.75, 1.0)} | inputs: []
     math: {'math_type': 'MULTIPLY', 'use_clamp': False}
     math FRACT -> FRACT | enum name fract
     math input defaults: [('Value', 0.5), ('Value_001', 0.5), ('Value_002', 0.5)]
     math MULTIPLY_ADD inputs: [('Value', False), ('Value_001', False), ('Value_002', False)]
     vector math: {'math_type': 'DOT_PRODUCT'} | has use_clamp: False
     inputs  ShaderNodeValue []
     outputs ShaderNodeValue [('Value', False)]
     inputs  ShaderNodeRGB []
     outputs ShaderNodeRGB [('Color', False)]
     inputs  ShaderNodeMath [('Value', False), ('Value_001', False), ('Value_002', True)]
     outputs ShaderNodeMath [('Value', False)]
     inputs  ShaderNodeVectorMath [('Vector', False), ('Vector_001', False), ('Vector_002', True), ('Scale', True)]
     outputs ShaderNodeVectorMath [('Vector', True), ('Value', False)]
     in ShaderNodeMath Value ('Value', 'Value1')
     in ShaderNodeMath Value_001 ('Value_001', 'Value2')
     in ShaderNodeMath Value_002 ('Value_002', 'Value3')
     in ShaderNodeVectorMath Vector ('Vector', 'Vector1')
     in ShaderNodeVectorMath Vector_001 ('Vector_001', 'Vector2')
     in ShaderNodeVectorMath Vector_002 ('Vector_002', 'Vector3')
     in ShaderNodeVectorMath Scale ('Scale', 'Scale1')
     out ladder Value ('Value',)
     out ladder Color ('Color',)
     ShaderNodeMath: RNA 41, NodeEnum 41, lowercase alone 37, unmapped ['inverse_sqrt', 'smooth_min', 'smooth_max', 'fract'], unused ['fraction', 'inversesqrt', 'smoothmin', 'smoothmax']
     ShaderNodeVectorMath: RNA 30, NodeEnum 30, lowercase alone 30, unmapped [], unused []
     ```
     (bpy prints one `DeprecationWarning` about `use_nodes` on stderr; it is not part of the output above.)
     What each line fixes:
     - the two value nodes have **no input socket**, so their `NodeRow` has `inputs=()` and their getter reads an
       output default; `ShaderNodeValue`'s is a float and `ShaderNodeRGB`'s a 4-tuple whose first three entries are
       Cycles' `float3` (upstream `get_node_output_rgba` drops the alpha, `shader.cpp:177-185`).
     - `ShaderNodeMath`'s three inputs are `Value`, `Value_001`, `Value_002` and Cycles' names are `Value1`, `Value2`,
       `Value3`, so each row's name is reached by B8's ladder (`Value` → `Value1`, `Value_001` → `Value2`,
       `Value_002` → `Value3`) and never by the identifier itself. The same holds for Vector Math's
       `Vector`/`Vector_001`/`Vector_002` → `Vector1`/`Vector2`/`Vector3`; `Scale` is an exact match, and its ladder's
       second rung `Scale1` is what a row without `Scale` would fall to.
     - `ShaderNodeMath`'s third input is `is_unavailable` in the node's default operation `ADD` and available in
       `MULTIPLY_ADD`, so it is exported as a default only for the operations that use it. The probe prints both ends
       and then puts the operation back to `ADD`, which is why the loop's line below shows `Value_002` unavailable:
       `ADD` gives `[('Value', False), ('Value_001', False), ('Value_002', True)]` and `MULTIPLY_ADD` gives
       `[('Value', False), ('Value_001', False), ('Value_002', False)]`. The five operations that
       make it available are `MULTIPLY_ADD`, `COMPARE`, `SMOOTH_MIN`, `SMOOTH_MAX` and `WRAP`; the scene of step 4 uses
       `MULTIPLY_ADD`, which is why `math_scene`'s export carries `{'Value3': 0.5}` (step 5).
     - `ShaderNodeVectorMath`'s outputs are operation-dependent: in the default `ADD` both are available, and with
       `DOT_PRODUCT` the `Vector` output is `is_unavailable` while `Value` is the available one. A scene must link the
       available output of its operation; the row names both (`VectorMathNode.inc:48-49`).
     - Vector Math has no `use_clamp` in bpy (`has use_clamp: False`), matching `VectorMathNode.inc:3-49`, which
       declares no such member: its `NodeRow`'s getter sets `math_type` only.
     - bpy's RNA operation identifiers are upper case (`MULTIPLY`, `DOT_PRODUCT`, `FRACT`), and `enum_name`'s
       `ENUM_ALIASES` are keyed by exactly those (`B8-node-table-export.md:458-468`), so `enum_name(node.operation)`
       is the one call a row needs for its enum parameter.
2. `node_table.py`, the four rows of `## Interface`, transcribed from the vendored definitions: `cycles_type` is
   `NodeType::add`'s first argument (`ValueNode.inc:3`, `ColorNode.inc:3`, `MathNode.inc:3`, `VectorMathNode.inc:3`),
   `inputs`/`outputs` are the `SOCKET_IN_*`/`SOCKET_OUT_*` UI names in file order, and the parameters are the
   `SOCKET_*` (non-`IN`/`OUT`) members a caller sets. Measured, from step 1's probe and the four files:
   ```
   ShaderNodeValue:        'value',       inputs=[],                                          outputs=['Value']
   ShaderNodeRGB:          'color',       inputs=[],                                          outputs=['Color']
   ShaderNodeMath:         'math',        inputs=['Value1', 'Value2', 'Value3'],               outputs=['Value']
   ShaderNodeVectorMath:   'vector_math', inputs=['Vector1', 'Vector2', 'Vector3', 'Scale'],   outputs=['Value', 'Vector']
   ```
   - `ShaderNodeValue`'s and `ShaderNodeRGB`'s parameters are `value`: Cycles' member name for both (`ValueNode.inc:5`,
     `ColorNode.inc:5`), and B6's `Node::set` finds a parameter by member name (`B6-shader-graph-api.md:14-15`). The
     row's getter reads Blender's output socket, which is what Cycles' own `add_node` does
     (`shader.cpp:421-425`, `:432-436`).
   - `ShaderNodeMath`'s parameters are `math_type` (Cycles' `Type` enum, `MathNode.inc:47`) and `use_clamp` (Cycles'
     `Use Clamp`, `:49`). Blender's `operation` RNA is Cycles' `custom1` (`shader.cpp:538-542`) and its `use_clamp` is
     `custom2`, so the getter reads both and lowercases the enum through `enum_name`.
   - `ShaderNodeVectorMath`'s parameter is `math_type` only (`VectorMathNode.inc:41`); Blender's `operation` is
     `custom1` (`shader.cpp:544-548`) and there is no clamp.
   - The docstring states rule 3, the file each row comes from and that a row's `cycles_type` is a Cycles type name, not
     a Blender idname (decision 5, BRIEF.md:52-55), and the sentence about which rows exist now names batch 1's four
     beside B8's four.
3. `node_table.py`, the enum names the Math row's `math_type` can take. `enum_name` is B8's and needs no change; what
   this step checks is that batch 1 is exactly its four aliases' first user (B8's statement at
   `B8-node-table-export.md:470-471`: "the table exists for the batch cards (batch 1's Math and Vector Math are its
   first users)"). Step 1's two measured lines are the whole derivation:
   - `ShaderNodeMath` has 41 RNA identifiers and 41 `NodeEnum` names, and the lowercase rule alone maps 37 of them; the
     four it misses are `fract`, `inverse_sqrt`, `smooth_min` and `smooth_max`, whose `NodeEnum` names are `fraction`,
     `inversesqrt`, `smoothmin` and `smoothmax` (`MathNode.inc:33`, `:39`, `:44`, `:45`) — exactly B8's four
     `ENUM_ALIASES` keys, upper-cased (`B8-node-table-export.md:463-468`).
   - `ShaderNodeVectorMath` has 30 and needs no alias.
   No line of `ENUM_ALIASES` changes; step 5's enum test pins both lines, so a bpy or vendored change that adds an
   operation fails there instead of silently exporting a name Cycles' `NodeEnum::exists` rejects
   (`B6-shader-graph-api.md:20-21`).
4. `tests/blender_it/golden_batch_01_scenes.py`, the four scenes (BRIEF.md:239-246). Each builder makes one
   `bpy.data.materials` material whose tree is: `ShaderNodeOutputMaterial` `output`; `ShaderNodeTexCoord` `coords`;
   the batch-1 node; `ShaderNodeEmission` `emit`; and the four links that make the node drive the emission. The plane
   itself is B9's harness's (an emission plane and an orthographic camera at pixel centres, BRIEF.md:239-241); this
   module supplies the material, and `## Open for Opus` 1 records that.
   - `value_scene`: `ShaderNodeValue` `value` at `Value = 0.25`, `ShaderNodeMath` `math` of operation `MULTIPLY`;
     `coords.Generated → math.Value_001`, `value.Value → math.Value`, `math.Value → emit.Strength`,
     `emit.Emission → output.Surface`. Why not fold: `math.Value` is linked from the Texture Coordinate node, so
     `ConstantFolder::all_inputs_constant` is false (`constant_fold.cpp:20-29`) and `fold_math`'s `X * 1 == X` rule
     cannot fire (`:466-478`, and `Value1` is not 1). The Value node itself is constant, which is why it needs no
     driver of its own: the host folds it into the Math node's `Value1` (`ValueNode.constant_fold.inc:1-4`,
     `constant_fold.cpp:31-42`), both engines then carry the same `0.25` as the Math node's `Value1` default, and the
     Math node still runs in the SVM (`MathNode.constant_fold.inc:6-8` is the `else` branch a node with one linked
     input takes). That is the whole of what a Value scene can test (`## Goal`, rule 4).
   - `rgb_scene`: `ShaderNodeRGB` `rgb` at `Color = (0.25, 0.5, 0.75, 1.0)`, `ShaderNodeVectorMath` `vmath` of
     operation `MULTIPLY`; `rgb.Color → vmath.Vector`, `coords.Generated → vmath.Vector_001`,
     `vmath.Vector → emit.Color`, `emit.Emission → output.Surface`. The two ends of the multiplication are the
     emission's colour, so the plane's radiance is the product; `Vector2` is linked, so `fold_vector_math`'s zero rule
     cannot fire (`constant_fold.cpp:525-535`). The RGB node folds into `vmath.Vector1` the same way the Value node
     folds into the Math node's `Value1`, and `ColorNode::compile` emits nothing after that
     (`ColorNode.compile-SVMCompiler.inc:5-7`).
   - `math_scene`: `ShaderNodeMath` `math` of operation `MULTIPLY_ADD`; `coords.Generated → math.Value`,
     `coords.Generated → math.Value_001`, `math.Value → emit.Strength`, `emit.Emission → output.Surface`. This is the
     operation that uses all three inputs, so `Value3`'s default is exported (measured in step 5) and `svm_math`'s
     `MULTIPLY_ADD` case (`kernel/svm/math_util.h:200-201`, `a * b + c`) is the one evaluated.
   - `vector_math_scene`: `ShaderNodeVectorMath` `vmath` of operation `DOT_PRODUCT`; `coords.Generated → vmath.Vector`,
     `coords.Generated → vmath.Vector_001`, `vmath.Value → emit.Strength`, `emit.Emission → output.Surface`.
     `DOT_PRODUCT` is the operation whose `Value` output is available and whose `Vector` output is `is_unavailable`
     (step 1's probe), so the link is `vmath.outputs["Value"]`: a scene that linked `Vector` raises `KeyError` on
     bpy 5.2.2 (measured: `bpy_prop_collection[key]: key "Vector" not found`).
   Each builder returns the material, so the harness can write it and the export test can read it. The four scenes are
   the four nodes' golden scenes, one per node, and no scene drives two batch-1 nodes: a failing scene then names one
   row.
5. `tests/blender/test_sync_shader_batch_01.py`, six tests. `bpy` only, no Blender run, no `.blend` on disk outside
   `tmp_path`, and every expected value a literal compared with exact equality, so no tolerance appears.
   - `test_the_four_rows_are_the_vendored_node_definitions`: parse the four `.inc` files with B8's regexes
     (`SOCKET_IN_[A-Z0-9_]+\(\s*\w+\s*,\s*"([^"]+)"` and the `SOCKET_OUT_` form, `NodeType::add\("([a-z_]+)"`,
     `B8-node-table-export.md:574-589`) and compare each with the row. Expected (step 2's table):
     ```
     ShaderNodeValue: 'value', inputs=[], outputs=['Value']
     ShaderNodeRGB: 'color', inputs=[], outputs=['Color']
     ShaderNodeMath: 'math', inputs=['Value1', 'Value2', 'Value3'], outputs=['Value']
     ShaderNodeVectorMath: 'vector_math', inputs=['Vector1', 'Vector2', 'Vector3', 'Scale'], outputs=['Value', 'Vector']
     ```
     The four files declare more sockets than the rows name, and the test asserts the filtered list and says so:
     `MathNode.inc` also declares `SOCKET_ENUM(math_type, ...)` (`:47`) and `SOCKET_BOOLEAN(use_clamp, ...)` (`:49`),
     and `ValueNode.inc:5` and `ColorNode.inc:5` declare `SOCKET_FLOAT`/`SOCKET_COLOR`, none of which the
     `SOCKET_IN_`/`SOCKET_OUT_` regexes match; those are the parameters, and step 2's getters are what cover them. A
     vendored definition that gains or loses a *linkable* socket therefore fails here instead of silently changing what
     a caller may link (B8's `:584-589` makes the same point for its three rows).
   - `test_the_math_and_vector_math_enums_are_cycles_node_enum_names`: step 1's two measured lines, read the same way
     (the vendored `.inc` files against `bl_rna.properties["operation"].enum_items`), plus `enum_name("FRACT") ==
     "fraction"`, `enum_name("INVERSE_SQRT") == "inversesqrt"`, `enum_name("SMOOTH_MIN") == "smoothmin"`,
     `enum_name("SMOOTH_MAX") == "smoothmax"` and `enum_name("ADD") == "add"`.
   - the four export tests, one per scene, each named after its node: `test_the_value_scene_exports_these_lists`,
     `test_the_rgb_scene_exports_these_lists`, `test_the_math_scene_exports_these_lists` and
     `test_the_vector_math_scene_exports_these_lists`. Each builds its
     scene with step 4's builder, writes it to `tmp_path` with `bpy.data.libraries.write`, loads it back with
     `bpy.data.libraries.load` (a reloaded `.blend` keeps every socket identifier, `B8-node-table-export.md:388-389`),
     and compares `export_graph(flatten_tree(tree))` with a literal. The reload is part of the fixture for the same
     reason B8's step 13 gives (`:604-608`). Measured, by running an implementation of steps 2-4 and B8's
     `export_graph` against bpy 5.2.2 (`## Open for Opus` 2):
     ```
     value_scene:
       ([('texture_coordinate', {'from_dupli': False}, {}),
         ('value', {'value': 0.25}, {}),
         ('math', {'math_type': 'multiply', 'use_clamp': False}, {}),
         ('emission', {}, {'Color': (1.0, 1.0, 1.0)})],
        [(0, 'Generated', 2, 'Value2'), (1, 'Value', 2, 'Value1'),
         (2, 'Value', 3, 'Strength'), (3, 'Emission', -1, 'Surface')])
     rgb_scene:
       ([('texture_coordinate', {'from_dupli': False}, {}),
         ('color', {'value': (0.25, 0.5, 0.75)}, {}),
         ('vector_math', {'math_type': 'multiply'}, {}),
         ('emission', {}, {'Strength': 1.0})],
        [(1, 'Color', 2, 'Vector1'), (0, 'Generated', 2, 'Vector2'),
         (2, 'Vector', 3, 'Color'), (3, 'Emission', -1, 'Surface')])
     math_scene:
       ([('texture_coordinate', {'from_dupli': False}, {}),
         ('math', {'math_type': 'multiply_add', 'use_clamp': False}, {'Value3': 0.5}),
         ('emission', {}, {'Color': (1.0, 1.0, 1.0)})],
        [(0, 'Generated', 1, 'Value1'), (0, 'Generated', 1, 'Value2'),
         (1, 'Value', 2, 'Strength'), (2, 'Emission', -1, 'Surface')])
     vector_math_scene:
       ([('texture_coordinate', {'from_dupli': False}, {}),
         ('vector_math', {'math_type': 'dot_product'}, {}),
         ('emission', {}, {'Color': (1.0, 1.0, 1.0)})],
        [(0, 'Generated', 1, 'Vector1'), (0, 'Generated', 1, 'Vector2'),
         (1, 'Value', 2, 'Strength'), (2, 'Emission', -1, 'Surface')])
     ```
     What each literal says:
     - the node order is the tree's own order, which the walk of `B7-flatten.md:264-282` keeps: `coords` first, then
       the batch-1 node, then `emit`, and `output` is not a node (B8's rule 4, `B8-node-table-export.md:490-495`).
     - a linked input exports no default and an unlinked one does: `value_scene`'s emission exports `Color` (unlinked,
       Blender's white) and not `Strength` (linked); `rgb_scene`'s exports `Strength` (unlinked, Blender's `1.0`) and
       not `Color` (linked). Both are Blender's defaults, not Cycles' `0.8` grey and `10.0` (`EmissionNode.inc:5-6`),
       because the export carries the material's meaning (`B8-node-table-export.md:618-620`, `:668-669`).
     - `math_scene`'s `{'Value3': 0.5}` is Blender's default for the third Math input (step 1's probe:
       `math input defaults [('Value', 0.5), ('Value_001', 0.5), ('Value_002', 0.5)]`), where Cycles' own default is
       `0.0f` (`MathNode.inc:53`): the export carries Blender's value, and this is the one scene where a batch-1 default
       differs between the two engines.
     - `rgb_scene`'s `('color', {'value': (0.25, 0.5, 0.75)}, {})` is the RGBA socket's first three floats (B8's
       `_default_of`, `:500-503`), and its alpha `1.0` is dropped.
     - the link tuples carry Cycles' UI names on both ends, not Blender's identifiers: `Value_001` is `Value2`,
       `Vector_001` is `Vector2`, and `ShaderNodeVectorMath`'s `Vector` output is `Vector`.
6. `tests/blender_it/test_golden_batch_01.py`, four tests, one per scene, each `@pytest.mark.slow` (CLAUDE.md rule 6;
   the harness renders twice per scene):
   - `test_the_value_node_matches_cycles`, `test_the_rgb_node_matches_cycles`,
     `test_the_math_node_matches_cycles`, `test_the_vector_math_node_matches_cycles`. Each loads its builder from
     step 4's module with `_load_by_path` (the pattern of `tests/blender_it/test_extension_it.py:53-64`), calls B9's
     `assert_golden(scene, name, tmp_path)` and reports the statistic it prints in the failure message. The rule is
     B9's (`BRIEF.md:247-252`) and this card states no tolerance, no band and no expected pixel value: both sides of
     the comparison are renders, and the decision rule is pre-registered in B9's card as an experiment (BRIEF.md:247).
   - Each test skips with B9's own reason when its inputs are missing (`BLENDER` unset or no extension zip,
     `test_extension_it.py:76-101`), so `make blender-it` stays green on a machine without Blender, exactly as T4.4's
     test does.
7. `tests/blender/test_sync_shader_node_table.py`, B8's guard test
   (`test_the_table_has_only_the_rows_this_card_adds`, `B8-node-table-export.md:595-598`): its expected set grows from
   B8's four idnames to eight.
   ```
   set(NODE_TABLE) == {"ShaderNodeOutputMaterial", "ShaderNodeOutputWorld", "ShaderNodeEmission",
                       "ShaderNodeTexCoord", "ShaderNodeValue", "ShaderNodeRGB", "ShaderNodeMath",
                       "ShaderNodeVectorMath"}
   ```
   Eight idnames and seven Cycles rows, because B8's two output nodes share one row (`output`) and this card's four
   are one row each. Nothing else in that file changes: its ladder table, its enum test and its unknown-node test
   are B8's, and its expected `PainterlyUnknownNode` stays `ShaderNodeBsdfPrincipled` (batch 11's, BRIEF.md:289-290).
   The test keeps its name: B8 named it for its own card (`B8-node-table-export.md:595`), and B8's acceptance counts
   the file's six tests (`:725-728`), so renaming it would make this card and B8's acceptance disagree about which test
   exists. A rename to something like `test_the_table_has_the_rows_of_the_batch_cards` is `## Open for Opus` 3's
   business, because every later batch card edits the same literal and would edit the same name.
8. `.venv/bin/ruff format` on the three new files and the two modified ones, then `.venv/bin/ruff check .`, then every
   acceptance command.

## Acceptance

Run every command from the repository root; the queue translates them with BACKLOG.md's table (`make check` → `CHECK`,
`make test-blender` → the same target with `KNOBS`, `build/dev` → `build/q`, `.venv/bin/<tool>` →
`MAIN/.venv/bin/<tool>`, any Python command prefixed with `PYTHONPATH="$PWD/analysis"`).
1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and the audit's
   `RESULT: PASS` line. This card adds no C++ and no binding, so the doctest counts and the exported symbols are the
   previous card's and must not move.
2. `make test-blender` exits 0. Report its last line.
3. `.venv/bin/python -m pytest tests/blender/test_sync_shader_batch_01.py -q` prints `6 passed`: step 5's
   `1 + 1 + 4 = 6`. The count is the number of test functions step 5 lists, and the run must print it; if it prints
   another count, the card's count is wrong and that is a finding, not a tolerance.
4. `.venv/bin/python -m pytest tests/blender/test_sync_shader_node_table.py -q` prints `6 passed`. The count is B8's
   own, derived from its step 12's five bullets (`B8-node-table-export.md:571-603`): the row-vs-definition test, the
   two ladder tests in one bullet, the enum test, the guard test and the unknown-idname test are `1 + 2 + 1 + 1 + 1 =
   6`. This card changes only the guard's expected set (step 7), so the count must not move; if it prints another
   count, a test arrived or vanished in that file and that is a finding.
5. `make blender-it` exits 0. Report its last line, the collected and passed counts, and the four golden tests'
   statistics as the harness prints them. The four tests of step 6 are in that run beside T4.4's one
   (`tests/blender_it/test_extension_it.py:143`) and B9's own harness test; this card states no count for the file set,
   because the total is B9's to fix and not this card's, and each test skips with B9's reason when its inputs are
   missing (`BLENDER` unset, no extension zip), which is how T4.4's test already behaves (`:76-101`).
6. `git status --porcelain` lists only the three Create paths and the two Modify paths above.

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- read the Value node's parameter from `node.inputs` instead of `node.outputs["Value"]` → step 1's probe already
  shows the node has no input, so the getter raises bpy's `KeyError` (`bpy_prop_collection[key]: key "Value" not
  found`) and step 5's export test fails on `value_scene`; the golden test of step 6 fails too;
- export `ShaderNodeRGB`'s `value` as the 4-tuple → `rgb_scene` gains `{'value': (0.25, 0.5, 0.75, 1.0)}` and step 5
  fails on that one test;
- set `math_type` to `node.operation` without `enum_name` → `math_scene` gains `'math_type': 'MULTIPLY_ADD'` and
  `rgb_scene`'s Vector Math gains `'MULTIPLY'`, so two of step 5's four tests fail; the golden tests of step 6 fail
  earlier, at `add_shader`, with B6's `ValueError` naming the enum (`B6-shader-graph-api.md:20-21`);
- drop `use_clamp` from the Math row's getter → `math_scene` and `value_scene` lose `'use_clamp': False` and step 5
  fails on both;
- give the Vector Math row a `use_clamp` getter → step 5 fails on `vector_math_scene`, and step 1's probe shows why
  (`has use_clamp: False`);
- name the Math row's inputs `Value`, `Value_001`, `Value_002` (Blender's identifiers) instead of Cycles'
  `Value1`, `Value2`, `Value3` → step 5's row-vs-definition test fails on `ShaderNodeMath`, and every scene's
  `Value1`/`Value2` link is dropped by B8's rule 4;
- link `vmath.outputs["Vector"]` in `vector_math_scene` → the builder raises `KeyError` (step 4), which is the
  measured behaviour of `DOT_PRODUCT`'s unavailable output;
- drive a scene from a constant instead of the Texture Coordinate node → `ConstantFolder::all_inputs_constant` is true
  (`constant_fold.cpp:20-29`) and the graph folds to a constant emission, so step 6's golden test compares two folded
  constants and proves nothing about the node; B9's harness records the folding check it uses for this
  (BRIEF.md:245-246), and this card's scenes are written so that it cannot fire (step 4's "Why not fold" lines);
- forget step 7 → `make test-blender` fails B8's guard test with the four missing idnames.

Report: the doctest and pytest counts, the audit line, the four golden statistics and every mutation you ran with its
first failing check.

## Commit

`N1: node batch 1: Value, RGB, Math and Vector Math — four node_table rows and their golden tests`

## Open for Opus

1. **B9's harness interface.** B9's card is not drafted yet (`docs/handoff/drafts/M6b/` holds B1, B4-B8 and B10), so
   this card's step 6 calls `assert_golden(scene, name, tmp_path)` and puts the four scene builders in
   `tests/blender_it/golden_batch_01_scenes.py`, a file B9 does not own. The options: (a) keep it, with B9 naming its
   own harness and this card's four call sites adjusted at dispatch; (b) B9's card names the batch cards' entry point
   and their file layout, and this card imports it — the better order, but B9 is not drafted yet, so no draft can cite
   it; (c) this card builds and renders without B9, which would pre-register a second comparison rule and contradict
   BRIEF.md:247-252. No expected value of this card depends on the choice: the four export literals of step 5 are
   `export_graph`'s, which is B8's and does not render.
2. **The expected values' derivation.** `AGENTS.md` requires a script that produces a committed number to be committed
   next to its output, and this card's `allowedPaths` holds only this file, so the prototype that produced step 5's four
   literals is not in the diff. What the card does instead: step 1's probe is quoted with its output, and each literal
   follows mechanically from a scene step 4 spells out and B8's rules. The acceptance is what pins them, and a wrong
   value fails it. If Opus prefers the prototype committed, it needs a path outside this card's `allowedPaths`, for
   example `docs/handoff/drafts/M6b/N1-derive.py`, as `B8-node-table-export.md` `## Open for Opus` 1 asks for B8's.
3. **`Parallel-safe: no`, against the plan's row.** `FACTS.md:362` records the plan's row as
   `"Node batch i of 12: <name> (node-table rows and golden tests; parallel-safe)"`, but every batch card must edit the
   same literal in B8's guard test (`B8-node-table-export.md:595-598`, this card's step 7), so two batch cards cannot
   land in parallel without a conflict in `tests/blender/test_sync_shader_node_table.py`. The options: (a) keep `no`
   (this card), and the batches run in sequence; (b) B8's guard test is replaced by a per-batch expectation, for example
   `assert {"ShaderNodeValue", "ShaderNodeRGB", "ShaderNodeMath", "ShaderNodeVectorMath"} <= set(NODE_TABLE)` plus a
   count each batch card owns in its own file, which restores the plan's parallelism at the cost of one weaker guard
   (a row could then arrive without its golden test and only the count would catch it); (c) B8's guard moves to a set
   literal that every batch card extends, and the batch cards are ordered, which is (a) with a note. This card takes
   (a) because the guard is what makes "no row without its golden test" true.
4. **The `FunctionNodeInput*` nodes, which Cycles maps to batch 1's two classes.** `blender/shader.cpp:426-451` maps
   `FunctionNodeInputVector` to `ColorNode`, `FunctionNodeInputBool` to `ValueNode` and `FunctionNodeInputInt` to
   `ValueNode`; B8's output ladder already carries the `FunctionNodeInputVector` `Vector` → `Color` rename
   (`B8-node-table-export.md:428-430`), which is a rule with no row to use it. These nodes are in none of the twelve
   batches (`plan.md:305` as quoted at `FACTS.md:39-43`), so this card adds no row for them and the `PainterlyUnknownNode`
   path reports them (B8's rule 6). The options: (a) leave them out of v1 (this card), and a material whose tree holds
   one of the three falls back to M5's constant mapping with one warning (B8's rule 6); (b) add three rows to this
   card, each a second idname on `value`/`color` with a getter reading the node's own RNA
   (`node.vector`/`node.boolean`/`node.integer`), which widens batch 1 beyond BRIEF.md:285 and adds three golden
   scenes; (c) assign them to a later batch card. No acceptance check of this card depends on the choice except step 7's
   eight-idname set.
5. **A Value or RGB scene cannot exercise the SVM's `NODE_VALUE_F`/`NODE_VALUE_V` from the node.** Both nodes have
   no input socket (step 1's probe), so the host always folds them (`constant_fold.cpp:20-29`,
   `ValueNode.constant_fold.inc:1-4`, `ColorNode.constant_fold.inc:1-4`) and `ColorNode::compile`'s
   `if (!color_out->links.empty())` never fires for a folded node (`ColorNode.compile-SVMCompiler.inc:5-7`). The two
   cases are covered from the other side already: T6.3's `src/test/test_cycles_svm_stack_nodes.cpp` dispatches
   `NODE_VALUE_F`, `NODE_VALUE_V` and their derivative variants directly (`:373-410`, `:412-424`), and step 1 counts
   them in `VENDORED.toml`. So a Value scene's job is the row's parameter, and BRIEF.md:245-246's "drive the node from
   TexCoord" cannot apply to a node with no inputs. The options: (a) keep it (this card), with rule 4's honest scope;
   (b) add a scene whose consumer folds away so the `Value` node survives to compile — impossible, because the fold is
   unconditional; (c) drop the Value and RGB golden scenes and rely on the stack-node doctests, which loses the
   per-node coverage BRIEF.md:283 requires. This card takes (a).
6. **`use_clamp` inserts a `ClampNode`, which is batch 2's node.** `MathNode::expand` creates a `ClampNode` of
   `minmax` 0..1 when `use_clamp` is set and the output has a link (`MathNode.expand.inc:3-13`), and `ClampNode` is
   batch 2's (`BRIEF.md:286` names Color Ramp and RGB Curves for batch 5; `plan.md:305`'s batch 2 is
   Mix/MapRange/Clamp, `FACTS.md:39-43`). The class, its fragments and its kernel case are vendored already
   (`VENDORED.toml:1844-2315`, `svm_nodes.toml:82`), so a clamped Math node compiles and evaluates without batch 2 —
   but no golden scene of this card sets `use_clamp` (`MathNode.inc:49`'s default is `false` and all four scenes keep
   it), so the inserted clamp is untested until batch 2. The options: (a) keep it (this card), and batch 2's golden
   test is the clamp's first; (b) add a fifth scene here with `use_clamp = True`, which tests a node batch 1 does not
   own and makes batch 2's card weaker. This card takes (a).
7. **What this card does not decide.** Per `BRIEF.md:295-301`: light node graphs stay out of v1, so no scene of this
   card drives a light; whether a node material's emission is scaled by `emission_scale` is open, and this card passes
   no knob (decision 8, `BRIEF.md:75-77`); Bump, Normal Map and the Attribute node are out, so none of the four rows
   names a normal input. The golden scenes' emission uses Cycles' own `emission` node, which B8 already has a row for
   (`B8-node-table-export.md:400`), and this card changes no line of it.
