# N5 — Node batch 5: Color Ramp and RGB Curves (drafted from BRIEF.md section 2, "Node batches")

Milestone: M6b · Depends on: B8, B9, B6 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "Node batches" (lines 274-293, batch 5 at `:286`), per that
brief's section 4 (lines 303-324) and the decisions of its section 1 that touch it: decision 5 (`:52-57`, node types by
Cycles type name, links and linkable defaults by UI name, parameters by member name with enums by `NodeEnum` name),
decision 8 (`:75-77`, no new knob) and decision 9 (`:78-79`, every expected value is an exact equality or a derived
rule). Code facts are `docs/handoff/drafts/M6b/FACTS.md` §3.13 (`:324-339`, batch 5's state at `:332-333`), §3.5 (the
collector), §3.7 (`:253-266`, the build targets) and §6 gap 8, re-read at this clone's HEAD in every file cited below.
The bpy facts are measured on this host with the project's `bpy` 5.2.2 by the probe of step 1, quoted with its output.

`BRIEF.md:274-283` gives every node of the six core batches the same four bullets; this card turns each bullet into a
rule in `## Goal`, states for each of batch 5's two nodes whether the bullet applies, and gives every expected value
its derivation. Its shape is batch 1's card (`docs/handoff/drafts/M6b/N1-batch-01-value-rgb-math.md`, the template
`BACKLOG.md:1062-1070` and FOLLOWUPS:93-94 name).

## Goal

Batch 5's two nodes are exported, compiled and rendered through the whole M6b path, and each has a golden test against
Cycles:

- **Rule 1: the nodes' evaluators are vendored, and this card adds nothing to `kernel/`** (BRIEF.md:276). For batch 5
  the bullet is already satisfied at HEAD: the kernel cases `NODE_RGB_RAMP` (`third_party/cycles/VENDORED.toml:1601`),
  `NODE_CURVES` (`:1673`) and `NODE_FLOAT_CURVE` (`:1781`) are vendored, the switch lists them
  (`src/cycles/svm_nodes.toml:63`, `:71`, `:83`), and the evaluator headers `kernel/svm/ramp.h` and
  `kernel/svm/ramp_util.h` are vendored whole (`VENDORED.toml:755-756`, `:763-764`) and included by the SVM
  (`svm_nodes.toml:25`). `FACTS.md:332-333` says the same ("`NODE_RGB_RAMP`, `NODE_CURVES`, `NODE_FLOAT_CURVE` yes
  (`ramp_util.h` vendored for `RGBRampNode::constant_fold`, H/T6.3:157-159)"). The rule is therefore a check, not a
  change: step 1's greps print the counts of step 1, and this card writes no line of `kernel/`.
- **Rule 2: the host class fragments are missing and this card extracts them** (BRIEF.md:277-281, which names exactly
  this batch: "batch 5: `RGBRampNode`, `CurvesNode`, `RGBCurvesNode`"). At HEAD none of the three has a fragment
  (`FACTS.md:333`: "RGBRampNode, CurvesNode, RGBCurvesNode missing"): step 1 counts 0 `VENDORED.toml` entries naming
  each. The classes' *declarations* are already vendored, because `scene/shader_nodes.h` is vendored whole
  (`VENDORED.toml:835-836`): `CurvesNode` at `third_party/cycles/scene/shader_nodes.h:1613`, `RGBCurvesNode` at
  `:1636`, `RGBRampNode` at `:1661`. What is missing is the out-of-line code: fifteen member fragments of
  `scene/shader_nodes.cpp` and two `node_define` fragments (step 3), added only through `tools/vendor_sync.py
  add-fragment` (R6, `T6.2:57`), plus one `includes` entry in `src/cycles/fragment_units.toml` (`:8-31`) because
  `RGBRampNode::constant_fold` and `CurvesNode::constant_fold` call `rgb_ramp_lookup()` of
  `kernel/svm/ramp_util.h`, which upstream includes at `scene/shader_nodes.cpp:37` and the generated unit does not.
- **Rule 3: `node_table.py` gains batch 5's two rows** (BRIEF.md:282): `ShaderNodeValToRGB` → `rgb_ramp` and
  `ShaderNodeRGBCurve` → `rgb_curves`, each with the Cycles UI names of its linkable inputs and outputs and the getter
  for its parameters by member name (B8's `NodeRow`, `B8-node-table-export.md:179-201`). The trap of the batch is that
  **the curve is a table, and Cycles stores it as a parameter socket, not as a linkable input**: `Ramp`/`Ramp Alpha`
  and `Curves` are `SOCKET_COLOR_ARRAY`/`SOCKET_FLOAT_ARRAY` members (`RGBRampNode.inc:5-6`, `RGBCurvesNode.inc:5`),
  so they belong in the node tuple's *parameters* dict by member name (decision 5, `BRIEF.md:52-55`), and B6's binding
  must gain the two array value forms (step 5). A Color Ramp without its table compiles to nothing:
  `RGBRampNode::compile` returns before emitting a node when `ramp.size() == 0 || ramp.size() != ramp_alpha.size()`
  (`RGBRampNode.compile-SVMCompiler.inc`), which would leave the `Color` output unassigned.
- **Rule 4: each node has a golden test that passes B9's rule** (BRIEF.md:283). Two scenes, one per node, added to
  B9's `GOLDEN_SCENES` (`B9-golden-harness.md:147`, `:241`): an emission plane whose Emission is driven by the node from
  a Texture Coordinate node (`BRIEF.md:239-246`), rendered by Cycles at 1 sample in Raw view as a float32 EXR and by
  painterly at `max_depth=1`, `emission_gain=1`, `jitter=0`, `output_mode="scene_linear"`
  (`B9-golden-harness.md:216-228`, `:261-268`), decided by B9's pre-registered rule
  (`B9-golden-harness.md:318-337`: `max |P - C| <= BAND`, `BAND = 2.0**-30`). This card contributes the scenes and
  their exact exported lists; it contributes no pixel expectation and no tolerance, because both sides of the
  comparison are renders and the rule is B9's (decision 9, `BRIEF.md:78-79`).
  What a Color Ramp or RGB Curves scene can prove is narrower than for a texture node, and honestly so: both nodes read
  a host LUT that Blender fills from its own `ColorBand`/`CurveMapping` (`blender/shader.cpp:410-420`, `:368-380`), so
  the golden render proves the LUT the export hands to Cycles is the LUT Blender's own Cycles gets — which is the whole
  content of `BRIEF.md:286`'s "the curve LUT is sampled as Cycles samples it". `## Open for Opus` 4 records that this
  makes the LUT export, not the node's arithmetic, the thing under test, and names the doctest that would cover the
  evaluator.

Nothing in the core changes: no kernel type, no scene API, no new knob (decision 8, `BRIEF.md:75-77`), so no image, no
K and no parity test of M3-M5 moves. The build-level changes are rule 2's `includes` entry and the two array value
forms B6's binding gains.

Which of the four bullets applies, per node (FACTS.md:332-333 is the current state of both rows; the file:line column is
this clone's HEAD):

| node | Blender idname | Cycles type | 1. vendor the evaluator | 2. host class fragments | 3. `node_table.py` row | 4. golden test |
|---|---|---|---|---|---|---|
| Color Ramp | `ShaderNodeValToRGB` | `rgb_ramp` | nothing to do: `NODE_RGB_RAMP` at `VENDORED.toml:1601`, `svm_nodes.toml:63`; `kernel/svm/ramp.h` at `VENDORED.toml:755-756`, `ramp_util.h` at `:763-764` | **extract** `RGBRampNode`: definition `node_define/RGBRampNode.inc` (upstream `:7501-7515`), members ctor `:7517`, `constant_fold` `:7519-7544`, `compile(SVMCompiler)` `:7546-7562`, `compile(OSLCompiler)` `:7564-7575` | **add** | **add** |
| RGB Curves | `ShaderNodeRGBCurve` | `rgb_curves` | nothing to do: `NODE_CURVES` at `VENDORED.toml:1673`, `svm_nodes.toml:71`; `kernel/svm/ramp.h:114-134` | **extract** `CurvesNode` (ctor `:7280`, `constant_fold` `:7282-7305`, `compile(SVMCompiler, ShaderInput*, ShaderOutput*)` `:7307-7325`, `compile(OSLCompiler, const char*)` `:7327-7338`, the two `assert(0)` overloads `:7340-7348`) and `RGBCurvesNode` (definition `node_define/RGBCurvesNode.inc`, upstream `:7352-7367`; ctor `:7369`, `constant_fold` `:7371-7374`, `compile(SVMCompiler)` `:7376-7379`, `compile(OSLCompiler)` `:7381-7384`) | **add** | **add** |

So of the four bullets, bullet 1 applies to neither node (a check, step 1), bullet 2 applies to both (step 3), and
bullets 3 and 4 apply to both (steps 4-8).

## Read first

- `CLAUDE.md` rules 1, 2 and 3 (scope; named knobs; PEP 8 with type hints and docstrings that state units);
  `AGENTS.md` "Expected values are evidence, not targets" and "Measured means reproducible".
- `docs/handoff/drafts/M6b/BRIEF.md` lines 274-293 (this card's mandate; `:286` is batch 5's two nodes), `:237-255`
  (B9, the harness and the pre-registered rule this card's golden tests use), `:52-57` (the socket-name rule), `:75-79`
  (no new knob; expected values are evidence) and `:295-301` (the open questions this card must not decide).
- `docs/handoff/drafts/M6b/FACTS.md` §3.13 (`:324-339`, batch 5's line `:332-333`), §3.5 (`:236-243`, the collector that
  turns the compiled closures into painterly's lobes), §3.7 (`:253-266`, `cycles_scene` and the generated units) and §6
  gap 8 (the missing host classes).
- `docs/handoff/drafts/M6b/N1-batch-01-value-rgb-math.md`: the table of `## Goal` (`:70-75`), the rows literal
  (`:186-204`), the getters (`:209-225`), the export literals of `## Steps` 5 (`:540-567`), the guard test's new
  expected set (`:594-608`) and `## Acceptance` (`:612-634`). This card is that one with batch 5's facts.
- `docs/handoff/drafts/M6b/B8-node-table-export.md`: `NodeRow` and the six names `node_table.py` exports (`:172-201`),
  the three rows B8 writes (`:390-407`), the socket ladders (`:422-457`), the four `ENUM_ALIASES` (`:458-468`),
  `export_graph` (`:485-509`), the row-vs-definition test's regexes (`:574-589`) and the guard test a batch card must
  change (`:595-598`).
- `docs/handoff/drafts/M6b/B6-shader-graph-api.md`: the two methods (`:96-109`), the nine parameter socket types, the
  sentence that anything else has no Python form (`:160-176`, `:221-222`) and the `TRANSFORM` value form (`:217-219`),
  which is the shape this card's two array forms copy.
- `docs/handoff/drafts/M6b/B9-golden-harness.md`: the harness's public names (`:135-151`, `GOLDEN_SCENES` at `:147`),
  the scene `build` (`:216-244`), the rule (`:318-337`) and the slow test that drives it (`:338-357`).
- The vendored definitions whose rows this card transcribes, each read in full:
  `third_party/cycles/fragments/scene/shader_nodes_cpp/node_define/RGBRampNode.inc` (`rgb_ramp`; parameters `Ramp`
  `:5`, `Ramp Alpha` `:6`, `Interpolate` `:7`; input `Fac` `:9`; outputs `Color` `:11`, `Alpha` `:12`) and
  `RGBCurvesNode.inc` (`rgb_curves`; parameters `Curves` `:5`, `Min X` `:6`, `Max X` `:7`, `Extrapolate` `:8`; inputs
  `Fac` `:10`, `Color` `:11`; output `Color` `:13`).
- The vendored member fragments that make the two nodes the code Cycles compiles:
  `third_party/cycles/fragments/scene/shader_nodes_cpp/member/RGBRampNode.constant_fold.inc` (the
  `ramp.size() != ramp_alpha.size()` guard, the `clamp(fac, 0, 1) * (ramp.size() - 1)` index and the
  `rgb_ramp_lookup`/`float_ramp_lookup` calls), `RGBRampNode.compile-SVMCompiler.inc` (`NODE_RGB_RAMP` with
  `table_size`, `fac`, `interpolate`, the two output offsets, then one `float4` per entry),
  `CurvesNode.constant_fold.inc` (the `interp(value, result, fac)` result and the `fac == 0` bypass),
  `CurvesNode.compile-SVMCompiler.inc` (`NODE_CURVES` with `min_x`, `max_x`, `table_size`, `extrapolate`),
  `RGBCurvesNode.compile-SVMCompiler.inc` (the `Color` input and output) and the two `assert(0)` overloads.
- `third_party/cycles/kernel/svm/ramp.h:95-111` (`svm_node_rgb_ramp`), `:114-134` (`svm_node_curves`: the
  `(color - min_x) / range_x` relative position and `interp(value, result, fac)`) and
  `third_party/cycles/kernel/svm/ramp_util.h:14-40` (`rgb_ramp_lookup`: `f = clamp(f, 0, 1) * (table_size - 1)`, the
  integer index and `t`, then `(1 - t) * a + t * b`).
- `third_party/cycles/kernel/types.h:35` (`#define RAMP_TABLE_SIZE 256`), the constant that fixes the LUT's length.
- `third_party/cycles/graph/node_type.h:262-274` (`SOCKET_*_ARRAY`, `SocketType::FLOAT_ARRAY` and `COLOR_ARRAY`, no
  `LINKABLE` flag) and `third_party/cycles/graph/node.cpp:144-160` (`Node::set(const SocketType &, array<float> &)` and
  `array<packed_float3> &`), the two setters step 5 calls.
- Upstream `intern/cycles/blender/shader.cpp`, read in the pinned checkout (never edited, not in this repo): the
  `ShaderNodeRGBCurve` case `:368-380` (`curvemapping_color_to_array(mapping, curves, RAMP_TABLE_SIZE, true)`,
  `curvemapping_minmax(mapping, 4, &min_x, &max_x)`, `extrapolate` from `CUMA_EXTEND_EXTRAPOLATE`) and the
  `ShaderNodeValToRGB` case `:410-420` (`colorramp_to_array(...)`, `interpolate = ipotype != COLBAND_INTERP_CONSTANT`);
  `blender/util.h:134-150` (`colorramp_to_array`: `full_size = size + 1`, `BKE_colorband_evaluate(ramp, i / size)`) and
  `:218-284` (`curvemapping_color_to_array`: `t = min_x + i / size * range_x`, `R(G(B(I(t))))` for `rgb_curve`).
- `tests/blender/conftest.py:22` (`ADDON_DIR`), `:44-53` (the add-on is loaded as the package `painterly`) and
  `:62-73` (the `addon` fixture); `tests/blender_it/test_extension_it.py:53-64` (`_load_by_path`), `:76-101` (the
  `BLENDER` and zip skips) and `:149-154` (the isolated profile).
- `src/cycles/fragment_units.toml:6-31` (the `shader_nodes` unit's `includes`, with `kernel/closure/bsdf_microfacet.h`
  and `kernel/svm/math_util.h` at `:25-26` and no `kernel/svm/ramp_util.h`).
- `pyproject.toml:38-44` (`testpaths`, `addopts`, the `slow` marker, ruff `line-length = 100`,
  `target-version = "py312"`) and `:48` (`extend-exclude` covers `docs/handoff`, so this draft is not linted).
- The expected values of steps 1, 4 and 6: the probe quoted there, measured on this host with `bpy` 5.2.2.

## Create

- `tests/blender/test_sync_shader_batch_05.py`
- `tests/blender_it/golden_batch_05_scenes.py`
- `tests/blender_it/test_golden_batch_05.py`

`tests/blender_it/golden_batch_05_scenes.py` is a module, not a test: `--import-mode=importlib`
(`pyproject.toml:38-39`) collects only `test_*.py`, and the test file loads it by path with
`tests/blender_it/test_extension_it.py:53-64`'s `_load_by_path`.

## Modify

- `src/cycles/fragment_units.toml`: one entry in `[unit.shader_nodes]`'s `includes` (`:8-31`),
  `"kernel/svm/ramp_util.h"`, after the existing `"kernel/svm/math_util.h"` (`:26`), with the comment of step 3.
- `third_party/cycles/VENDORED.toml` and the seventeen new `third_party/cycles/fragments/scene/shader_nodes_cpp/**`
  `.inc` files of step 3 — **only** through `tools/vendor_sync.py`; a hand edit of `third_party/` is rejected by the
  auditor (R6).
- `src/blender/_painterly.pyi` (CONTRACT, `:4`): the two array value forms of `## Interface` (step 5), as comment lines
  on `add_shader`, which keeps its signature.
- `src/blender/python.cpp`: the two new cases in `set_parameter_from_python` (step 5), in B6's helper
  (`B6-shader-graph-api.md:186-222`).
- `src/blender/addon/sync/shader/node_table.py` (B8's file): batch 5's two rows in `NODE_TABLE` (step 4), after B8's
  four and batch 1's four, and the module docstring's sentence about which rows exist updated to name this batch.
- `tests/blender/test_sync_shader_node_table.py` (B8's file): the guard test of
  `B8-node-table-export.md:595-598`, `test_the_table_has_only_the_rows_this_card_adds`, now expects ten idnames — B8's
  four plus batch 1's four plus this card's two (step 8).

## Do not touch

- `third_party/cycles/kernel/**`, `src/cycles/svm_nodes.toml`: rule 1 is satisfied at HEAD (step 1), and
  `third_party/` is `tools/vendor_sync.py`'s alone (R6). A batch-5 step that wanted to vendor a kernel header would mean
  `FACTS.md:332-333` is wrong, which is a `report_blocked`, not a change.
- `src/painterly/**`: nothing in the core is batch 5's. `painterly_svm_collect` (batch 4's caller), the device update
  (B2) and the trace loop (B4) already evaluate any compiled graph; a node batch adds no kernel code (BRIEF.md:274-283
  names four bullets and none of them is C++).
- `src/blender/addon/sync/shader/export.py`: B8's rule 4 is generic — a row is data and `export_graph` reads it
  (`B8-node-table-export.md:485-509`) — and this card's tables travel in the parameters dict a row's getter returns, so
  `export.py` changes no line. A batch card that had to change `export.py` would mean B8's machinery is not row-driven.
- `src/blender/addon/sync/shader/flatten.py`, `src/blender/addon/sync/{__init__,material,world,geometry}.py`: B7's and
  B8's. The scenes of this card are built in Blender's Python and written to `tmp_path`; they go through no scene sync.
- `tests/blender_it/golden_scenes.py`, `golden_rule.py`, `render_golden.py`, `test_golden.py`: B9's. This card adds one
  module beside them and two `GOLDEN_SCENES` entries, which is what `B9-golden-harness.md:241` allows a batch card.
- `tests/blender_it/test_extension_it.py` and `tests/blender_it/run_reference.py`: T4.4's.
- `Makefile`, `pyproject.toml`, `src/blender/CMakeLists.txt`, `src/test/CMakeLists.txt`: no new target, no new marker,
  no new C++ source. B9 owns `make blender-it` and `tests/blender_it/`.
- `NODE_TABLE` beyond this card's two rows, and every other batch's golden scene: batch 1's, 6's, 10's, 11's and 12's
  rows and scenes are this item's other four cards, and the six non-core batches' are the items D4 defers.
- `docs/spec.md`, `docs/plan.md`, `CLAUDE.md`, `AGENTS.md`, `BACKLOG.md`, `docs/handoff/` beyond this card's own file.

## Interface

CONTRACT (Opus writes this before dispatch): `src/blender/_painterly.pyi`, `class Scene`'s `add_shader`
(`:49-54`'s comment block, which B6 rewrites). The signature does not change; the two sentences that do are this
card's proposal for the text Opus owns:

    # A parameter's value is a bool, an int, a float, a 3-sequence of reals (COLOR, VECTOR, POINT),
    # three or four rows of four reals (TRANSFORM), a str, or, for the two array parameter types of
    # Cycles' node definitions, a sequence of those scalar values: a sequence of floats for
    # FLOAT_ARRAY and a sequence of 3-sequences for COLOR_ARRAY (RGBRampNode.inc:5-6,
    # RGBCurvesNode.inc:5). A table parameter is passed by member name, like every other parameter.
    def add_shader(
        self,
        nodes: list[tuple[str, dict[str, object], dict[str, object]]],
        links: list[tuple[int, str, int, str]],
    ) -> int: ...

Not a CONTRACT: the two conversions themselves, in `python.cpp`'s anonymous namespace beside B6's
`set_parameter_from_python` (`B6-shader-graph-api.md:186-222`):

```cpp
/* The value of one array parameter (B6's scan found no array type, B6-shader-graph-api.md:166-172;
 * these two nodes' tables are SOCKET_COLOR_ARRAY and SOCKET_FLOAT_ARRAY members). A sequence of
 * reals for FLOAT_ARRAY, a sequence of 3-sequences for COLOR_ARRAY; anything else raises TypeError
 * through throw_wrong_type. */
void set_array_parameter_from_python(ShaderNode &node, const SocketType &socket, nb::handle value,
                                     const std::string &what);
```

**The two rows** (`src/blender/addon/sync/shader/node_table.py`, B8's `NodeRow`,
`B8-node-table-export.md:179-185`):

```python
NODE_TABLE: Final[Mapping[str, NodeRow]] = {
    # ... B8's four rows and batch 1's four, unchanged.
    # RGBRampNode.inc:3-12. `Ramp` and `Ramp Alpha` are COLOR_ARRAY and FLOAT_ARRAY parameters and
    # `Interpolate` a boolean one; Blender's Color Ramp has one linkable input, `Fac`, and two
    # outputs. A Color Ramp without its table emits no SVM node (RGBRampNode.compile-SVMCompiler.inc).
    "ShaderNodeValToRGB": NodeRow(
        "rgb_ramp", ("Fac",), ("Color", "Alpha"), _color_ramp_parameters),
    # RGBCurvesNode.inc:3-13. `Curves` is a COLOR_ARRAY parameter; `Min X`, `Max X` and `Extrapolate`
    # are scalars. `Fac` and `Color` are the two linkable inputs. The base class CurvesNode declares no
    # socket of its own (scene/shader_nodes.h:1613-1634), so this row is the node's whole surface.
    "ShaderNodeRGBCurve": NodeRow(
        "rgb_curves", ("Fac", "Color"), ("Color",), _rgb_curves_parameters),
}
```

The two getters, each returning every parameter of its node including the table:

```python
# The table's length: RAMP_TABLE_SIZE + 1 samples (kernel/types.h:35, blender/util.h:139-140).
RAMP_SAMPLES = 257

def _color_ramp_parameters(node: bpy.types.Node) -> dict[str, object]:
    """Cycles' `interpolate`, `Ramp` and `Ramp Alpha`: the ramp's 257 samples at i/256 (unitless)."""
    ramp = node.color_ramp
    samples = [ramp.evaluate(i / (RAMP_SAMPLES - 1)) for i in range(RAMP_SAMPLES)]
    return {
        "interpolate": ramp.interpolation != "CONSTANT",
        "Ramp": tuple(tuple(float(channel) for channel in sample[:3]) for sample in samples),
        "Ramp Alpha": tuple(float(sample[3]) for sample in samples),
    }

def _rgb_curves_parameters(node: bpy.types.Node) -> dict[str, object]:
    """Cycles' `Curves`, `min_x`, `max_x` and `extrapolate`: the curve's 257 samples (unitless)."""
    mapping = node.mapping
    min_x, max_x = _curve_range(mapping)
    samples = [
        tuple(
            float(mapping.evaluate(mapping.curves[channel], mapping.evaluate(mapping.curves[3], t)))
            for channel in range(3)
        )
        for t in (min_x + i / (RAMP_SAMPLES - 1) * (max_x - min_x) for i in range(RAMP_SAMPLES))
    ]
    return {
        "Curves": tuple(samples),
        "min_x": min_x,
        "max_x": max_x,
        "extrapolate": mapping.extend == "EXTRAPOLATED",
    }
```

`_curve_range(mapping)` is `curvemapping_minmax(mapping, 4, ...)` (`blender/util.h:161-175`,
`blender/shader.cpp:376-377`): the smallest first point x and the largest last point x over all four curves.

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
     A different number means the table is not the one steps 4 and 8 assume: read it and report what is there.
   - B6 landed, with the helper step 5 extends. Each prints `1`.
     ```
     grep -c 'set_parameter_from_python' src/blender/python.cpp
     grep -c 'def add_shader' src/blender/_painterly.pyi
     ```
   - B9 landed, with the harness names of `## Interface`. Each prints `1`.
     ```
     grep -c 'GOLDEN_SCENES: dict' tests/blender_it/golden_scenes.py
     grep -c 'def meets_rule' tests/blender_it/golden_rule.py
     grep -c 'golden_rule' tests/blender_it/test_golden.py
     ```
   - Rule 1 holds — the three cases and the two evaluator headers are vendored. Each prints the number after it.
     ```
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_RGB_RAMP"' third_party/cycles/VENDORED.toml       # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_CURVES"' third_party/cycles/VENDORED.toml         # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_FLOAT_CURVE"' third_party/cycles/VENDORED.toml    # 1
     grep -c 'dest = "kernel/svm/ramp.h"' third_party/cycles/VENDORED.toml                             # 1
     grep -c 'dest = "kernel/svm/ramp_util.h"' third_party/cycles/VENDORED.toml                        # 1
     grep -cE '^  "NODE_RGB_RAMP",$|^  "NODE_CURVES",$|^  "NODE_FLOAT_CURVE",$' src/cycles/svm_nodes.toml   # 3
     ```
   - Rule 2 holds — the three classes have no fragment yet, so step 3 adds them. Each of these prints `0`:
     ```
     grep -c 'shader_nodes_cpp/member/RGBRampNode\.' third_party/cycles/VENDORED.toml                  # 0
     grep -c 'shader_nodes_cpp/member/CurvesNode\.' third_party/cycles/VENDORED.toml                   # 0
     grep -c 'shader_nodes_cpp/member/RGBCurvesNode\.' third_party/cycles/VENDORED.toml                # 0
     ```
     and these print `1` each, because the declarations are already vendored with `scene/shader_nodes.h`
     (`VENDORED.toml:835-836`):
     ```
     grep -c '^class RGBRampNode : public ShaderNode' third_party/cycles/scene/shader_nodes.h            # 1
     grep -c '^class CurvesNode : public ShaderNode' third_party/cycles/scene/shader_nodes.h             # 1
     grep -c '^class RGBCurvesNode : public CurvesNode' third_party/cycles/scene/shader_nodes.h          # 1
     ```
   - The generated `shader_nodes` unit does not yet include `ramp_util.h`, so step 3 adds it. This prints `0`:
     ```
     grep -c 'kernel/svm/ramp_util.h' src/cycles/fragment_units.toml                                    # 0
     ```
   - The bpy facts rules 3 and 4 rest on. Save this probe as a file under `/tmp` and run it with
     `.venv/bin/python <file>`; it must print exactly the lines quoted after it (they are this card's measurement on
     bpy 5.2.2, and the rows, the LUTs and the two scenes of steps 4-7 are derived from them):
     ```python
     import bpy

     mat = bpy.data.materials.new("probe")
     mat.use_nodes = True
     tree = mat.node_tree
     tree.nodes.clear()

     ramp = tree.nodes.new("ShaderNodeValToRGB")
     print("ramp inputs ", [(s.identifier, s.type) for s in ramp.inputs],
           "outputs", [(s.identifier, s.type) for s in ramp.outputs])
     print("ramp fac default", ramp.inputs["Fac"].default_value)
     print("ramp elements", [(e.position, tuple(e.color)) for e in ramp.color_ramp.elements],
           "interpolation", ramp.color_ramp.interpolation, "hue", ramp.color_ramp.hue_interpolation)
     lut = [tuple(ramp.color_ramp.evaluate(i / 256.0)) for i in range(257)]
     print("ramp lut len", len(lut), "first", lut[0], "last", lut[256])
     print("ramp lut at 64, 128, 192", lut[64], lut[128], lut[192])
     print("ramp lut is exactly i/256", all(lut[i][:3] == (i / 256.0,) * 3 for i in range(257)))

     curves = tree.nodes.new("ShaderNodeRGBCurve")
     mapping = curves.mapping
     print("curves inputs ", [(s.identifier, s.type) for s in curves.inputs],
           "outputs", [(s.identifier, s.type) for s in curves.outputs])
     print("curves fac default", curves.inputs["Fac"].default_value,
           "color default", tuple(curves.inputs["Color"].default_value))
     print("mapping: curves", len(mapping.curves), "extend", mapping.extend,
           "use_clip", mapping.use_clip, "clip", mapping.clip_min_x, mapping.clip_max_x)
     print("mapping points", [[(p.location[0], p.location[1]) for p in c.points] for c in mapping.curves])
     print("identity curve at 0,64,128,192,256",
           [mapping.evaluate(mapping.curves[0], i / 256.0) for i in (0, 64, 128, 192, 256)])
     print("identity curve is exactly i/256",
           all(mapping.evaluate(mapping.curves[0], i / 256.0) == i / 256.0 for i in range(257)))
     mapping.curves[0].points.new(0.5, 0.25)
     mapping.update()
     print("3-point curve at 0,64,128,192,256",
           [mapping.evaluate(mapping.curves[0], i / 256.0) for i in (0, 64, 128, 192, 256)])
     print("interpolation items",
           [i.identifier for i in ramp.color_ramp.bl_rna.properties["interpolation"].enum_items])
     print("extend items", [i.identifier for i in mapping.bl_rna.properties["extend"].enum_items])
     ```
     ```
     ramp inputs  [('Fac', 'VALUE')] outputs [('Color', 'RGBA'), ('Alpha', 'VALUE')]
     ramp fac default 0.5
     ramp elements [(0.0, (0.0, 0.0, 0.0, 1.0)), (1.0, (1.0, 1.0, 1.0, 1.0))] interpolation LINEAR hue NEAR
     ramp lut len 257 first (0.0, 0.0, 0.0, 1.0) last (1.0, 1.0, 1.0, 1.0)
     ramp lut at 64, 128, 192 (0.25, 0.25, 0.25, 1.0) (0.5, 0.5, 0.5, 1.0) (0.75, 0.75, 0.75, 1.0)
     ramp lut is exactly i/256 True
     curves inputs  [('Fac', 'VALUE'), ('Color', 'RGBA')] outputs [('Color', 'RGBA')]
     curves fac default 1.0 color default (1.0, 1.0, 1.0, 1.0)
     mapping: curves 4 extend EXTRAPOLATED use_clip True clip 0.0 1.0
     mapping points [[(0.0, 0.0), (1.0, 1.0)], [(0.0, 0.0), (1.0, 1.0)], [(0.0, 0.0), (1.0, 1.0)], [(0.0, 0.0), (1.0, 1.0)]]
     identity curve at 0,64,128,192,256 [0.0, 0.25, 0.5, 0.75, 1.0]
     identity curve is exactly i/256 False
     3-point curve at 0,64,128,192,256 [0.0, 0.08782973140478134, 0.25, 0.5255768299102783, 1.0000001192092896]
     interpolation items ['EASE', 'CARDINAL', 'LINEAR', 'B_SPLINE', 'CONSTANT']
     extend items ['HORIZONTAL', 'EXTRAPOLATED']
     ```
     (bpy prints one `DeprecationWarning` about `use_nodes` on stderr; it is not part of the output above.)
     What each line fixes:
     - both nodes have a linkable `Fac` and no other value input beyond `RGB Curves`' `Color`, so each row's `inputs`
       is the list above and nothing else; `Color Ramp`'s two outputs are `Color` and `Alpha`
       (`RGBRampNode.inc:11-12`) and `RGB Curves`' one is `Color` (`RGBCurvesNode.inc:13`).
     - the ramp's default is the identity and its LUT is **exactly** `i/256` at all 257 samples
       (`ramp lut is exactly i/256 True`), which is `colorramp_to_array`'s `BKE_colorband_evaluate(ramp, float(i) /
       float(size))` at `size = RAMP_TABLE_SIZE = 256` (`blender/util.h:139-148`, `kernel/types.h:35`): the sample
       positions are the 257 endpoints of 256 equal intervals, not 256 midpoints.
     - `Fac`'s Blender default is `0.5` where Cycles' is `0.0f` (`RGBRampNode.inc:9`); `RGB Curves`' `Fac` default is
       `1.0` where Cycles' is `0.0f` (`RGBCurvesNode.inc:10`), and its `Color` default is Blender's white where Cycles'
       is `zero_float3()` (`:11`). The export carries Blender's values, as batch 1's card derives for `Emission`
       (`N1-batch-01-value-rgb-math.md:571-578`).
     - the identity curve is **not** bitwise `i/256` at every sample (`identity curve is exactly i/256 False`) although
       the five quoted samples are, so the curve LUT's expected values are the ones `CurveMapping.evaluate` returns and
       never a hand-written ramp: step 4 compares all 257 samples against that call.
     - the 3-point curve's samples are the measurement step 4 pins: `0.0`, `0.08782973140478134`, `0.25`,
       `0.5255768299102783`, `1.0000001192092896` at `i` = 0, 64, 128, 192, 256.
     - `interpolation` has five identifiers and Cycles has one boolean (`interpolate`, `RGBRampNode.inc:7`), so the
       getter maps exactly one of them, `CONSTANT`, to `False`; the other four interpolate.
     - `extend` has two identifiers and Cycles has one boolean (`extrapolate`, `RGBCurvesNode.inc:8`), so the getter
       maps `EXTRAPOLATED` to `True` and `HORIZONTAL` to `False`, which is upstream's own test
       (`shader.cpp:378-379`: `(mapping.flag & CUMA_EXTEND_EXTRAPOLATE) != 0`).
2. `node_table.py`, the two rows of `## Interface`, transcribed from the vendored definitions: `cycles_type` is
   `NodeType::add`'s first argument (`RGBRampNode.inc:3`, `RGBCurvesNode.inc:3`), `inputs`/`outputs` are the
   `SOCKET_IN_*`/`SOCKET_OUT_*` UI names in file order, and the parameters are the `SOCKET_*` (non-`IN`/`OUT`) members
   a caller sets. Measured, from step 1's probe and the two files:
   ```
   ShaderNodeValToRGB:   'rgb_ramp',   inputs=['Fac'],          outputs=['Color', 'Alpha']
   ShaderNodeRGBCurve:   'rgb_curves', inputs=['Fac', 'Color'], outputs=['Color']
   ```
   - `ShaderNodeValToRGB`'s parameters are `interpolate` (`RGBRampNode.inc:7`), `Ramp` (`:5`) and `Ramp Alpha`
     (`:6`); the last two are `SOCKET_COLOR_ARRAY`/`SOCKET_FLOAT_ARRAY` members (`graph/node_type.h:267-274`), which
     carry no `LINKABLE` flag, so they are parameters by decision 5 and not linkable inputs.
   - `ShaderNodeRGBCurve`'s parameters are `Curves` (`RGBCurvesNode.inc:5`), `min_x` (`:6`), `max_x` (`:7`) and
     `extrapolate` (`:8`). `CurvesNode`'s own members (`scene/shader_nodes.h:1613-1634`) are the base class's, not the
     node's: `CurvesNode::compile(SVMCompiler &)` and its OSL twin `assert(0)` (`:7340-7348`), which is why the row
     names no parameter of the base class.
   - The docstring states rule 3, the file each row comes from and that a row's `cycles_type` is a Cycles type name, not
     a Blender idname (decision 5, BRIEF.md:52-55), and the sentence about which rows exist now names batch 5's two
     beside B8's four and batch 1's four.
3. The three host classes' fragments, through `tools/vendor_sync.py` only (R6). The commands are `T6.7:2637-2643`'s
   shape, and the anchors are the ones `tools/vendor_sync.py list-anchors scene/shader_nodes.cpp` prints (the upstream
   line numbers in the table above are the same anchors' ranges):
   ```
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp node_define RGBRampNode RGBCurvesNode
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp member \
       RGBRampNode::RGBRampNode RGBRampNode::constant_fold \
       RGBCurvesNode::RGBCurvesNode RGBCurvesNode::constant_fold \
       CurvesNode::CurvesNode CurvesNode::constant_fold
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp member \
       RGBRampNode::compile RGBCurvesNode::compile --params SVMCompiler
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp member \
       RGBRampNode::compile RGBCurvesNode::compile --params OSLCompiler
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp member \
       CurvesNode::compile --params 'SVMCompiler &compiler, ShaderInput *value_in, ShaderOutput *value_out'
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp member \
       CurvesNode::compile --params 'OSLCompiler &compiler, const char *name'
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp member CurvesNode::compile \
       --params 'SVMCompiler &'
   .venv/bin/python -I tools/vendor_sync.py add-fragment scene/shader_nodes.cpp member CurvesNode::compile \
       --params 'OSLCompiler &'
   ```
   - Two `node_define` fragments and fifteen member fragments: `RGBRampNode`'s five (`RGBRampNode.inc` plus ctor,
     `constant_fold` and the two `compile`s), `RGBCurvesNode`'s five, and `CurvesNode`'s five, of which the two
     `assert(0)` overloads need the bare `--params` form to be told apart from the two real ones. This prints the
     counts after the commands:
     ```
     grep -c 'shader_nodes_cpp/member/RGBRampNode\.' third_party/cycles/VENDORED.toml        # 5
     grep -c 'shader_nodes_cpp/member/RGBCurvesNode\.' third_party/cycles/VENDORED.toml      # 5
     grep -c 'shader_nodes_cpp/member/CurvesNode\.' third_party/cycles/VENDORED.toml         # 5
     grep -c 'shader_nodes_cpp/node_define/RGBRampNode"' third_party/cycles/VENDORED.toml    # 1
     grep -c 'shader_nodes_cpp/node_define/RGBCurvesNode"' third_party/cycles/VENDORED.toml  # 1
     ```
     `CurvesNode`'s count is five and not four because the class has two further `compile` overloads that only
     `assert(0)`; both are vendored because the generated unit compiles every fragment of the file in upstream order,
     and a fragment left out would shift the unit's text.
   - The `includes` entry: `src/cycles/fragment_units.toml`'s `[unit.shader_nodes]` (`:8-31`) gains
     `"kernel/svm/ramp_util.h"`, because `RGBRampNode::constant_fold` and `CurvesNode::constant_fold` call
     `rgb_ramp_lookup` while upstream reaches it at `scene/shader_nodes.cpp:37`. Without it the unit does not compile,
     which is what `tools/gen_fragment_units.py`'s unit check reports.
   - `third_party/cycles/VENDORED.toml` and the new `.inc` files are `vendor_sync`'s output; `make vendor-check`
     (`CHECK`'s last step) proves the tree still matches the manifest.
4. `tests/blender/test_sync_shader_batch_05.py`, six tests. `bpy` only, no Blender run, no `.blend` on disk outside
   `tmp_path`, and every expected value a literal or a call to Blender's own `evaluate`, compared with exact equality,
   so no tolerance appears.
   - `test_the_two_rows_are_the_vendored_node_definitions`: parse the two `.inc` files with B8's regexes
     (`SOCKET_IN_[A-Z0-9_]+\(\s*\w+\s*,\s*"([^"]+)"`, the `SOCKET_OUT_` form and `NodeType::add\("([a-z_]+)"`,
     `B8-node-table-export.md:574-589`) and compare each with the row. Expected (step 2's table):
     ```
     ShaderNodeValToRGB: 'rgb_ramp', inputs=['Fac'], outputs=['Color', 'Alpha']
     ShaderNodeRGBCurve: 'rgb_curves', inputs=['Fac', 'Color'], outputs=['Color']
     ```
     The two files declare more sockets than the rows name — `SOCKET_COLOR_ARRAY(ramp, ...)`,
     `SOCKET_FLOAT_ARRAY(ramp_alpha, ...)`, `SOCKET_BOOLEAN(interpolate, ...)`, `SOCKET_COLOR_ARRAY(curves, ...)`,
     `SOCKET_FLOAT(min_x, ...)`, `SOCKET_FLOAT(max_x, ...)`, `SOCKET_BOOLEAN(extrapolate, ...)` — and none of them
     matches the `SOCKET_IN_`/`SOCKET_OUT_` regexes, so the test asserts the filtered list and says so: those are the
     parameters, and step 2's getters are what cover them.
   - `test_the_color_ramp_table_is_cycles_ramp_table`: `_color_ramp_parameters` on a fresh `ShaderNodeValToRGB`
     returns `Ramp` of 257 entries equal to `(i / 256.0,) * 3` and `Ramp Alpha` of 257 entries equal to `1.0`
     (step 1's `ramp lut is exactly i/256 True`). With one element added at position 0.5 and colour
     `(0.25, 0.5, 0.75)`, `Ramp[128] == (0.25, 0.5, 0.75)` and `Ramp[64] == (0.125, 0.25, 0.375)` (measured), the
     linear interpolation `rgb_ramp_lookup`'s `(1 - t) * a + t * b` also gives (`ramp_util.h:36-38`).
   - `test_the_rgb_curves_table_is_curvemapping_color_to_array`: `_rgb_curves_parameters`' `Curves` has 257 entries,
     each equal to `(mapping.evaluate(mapping.curves[c], mapping.evaluate(mapping.curves[3], t)) for c in range(3))`
     at `t = min_x + i / 256 * (max_x - min_x)`, for every `i`; with the default curves `t == i / 256` and the five
     samples at `i` = 0, 64, 128, 192, 256 are `0.0`, `0.25`, `0.5`, `0.75`, `1.0`; with a point at `(0.5, 0.25)` on
     the first curve they are step 1's `0.0`, `0.08782973140478134`, `0.25`, `0.5255768299102783`,
     `1.0000001192092896` — after `mapping.update()`, which the getter's own `evaluate` calls need and which the test
     calls explicitly, because a point added without it changes no sample. `min_x` and `max_x` are all four curves'
     range: a point moved on the *green* curve widens them, which the test asserts
     (`curvemapping_minmax(mapping, 4, ...)`, `blender/shader.cpp:376-377`).
   - `test_the_scalar_parameters_are_cycles_members`: `_color_ramp_parameters`' `interpolate` is `True` for a fresh
     ramp and `False` after `color_ramp.interpolation = "CONSTANT"`; `_rgb_curves_parameters`' `min_x`, `max_x` and
     `extrapolate` are `0.0`, `1.0` and `True` for a fresh mapping and `False` for `extrapolate` after
     `mapping.extend = "HORIZONTAL"`.
   - the two export tests, one per scene: `test_the_color_ramp_scene_exports_these_lists` and
     `test_the_rgb_curves_scene_exports_these_lists`. Each builds its scene with step 6's builder, writes it to
     `tmp_path` with `bpy.data.libraries.write`, loads it back with `bpy.data.libraries.load` (a reloaded `.blend` keeps
     every socket identifier, `B8-node-table-export.md:388-389`) and compares `export_graph(flatten_tree(tree))` with a
     literal. The table parameters are compared by length and by their measured first and middle entries, because the
     full 257-entry literal is the LUT test's job above; everything else is compared exactly. Measured, by running an
     implementation of steps 2-6 and B8's `export_graph` against bpy 5.2.2 (`## Open for Opus` 3):
     ```
     color_ramp_scene:
       ([('texture_coordinate', {'from_dupli': False}, {}),
         ('rgb_ramp', {'interpolate': True, 'Ramp': 257, 'Ramp Alpha': 257}, {}),
         ('emission', {}, {'Strength': 1.0})],
        [(0, 'Generated', 1, 'Fac'), (1, 'Color', 2, 'Color'), (2, 'Emission', -1, 'Surface')])
       Ramp[0] == (0.0, 0.0, 0.0), Ramp[128] == (0.25, 0.5, 0.75), Ramp[256] == (1.0, 1.0, 1.0)
     rgb_curves_scene:
       ([('texture_coordinate', {'from_dupli': False}, {}),
         ('rgb_curves', {'Curves': 257, 'min_x': 0.0, 'max_x': 1.0, 'extrapolate': True},
          {'Color': (1.0, 1.0, 1.0)}),
         ('emission', {}, {'Strength': 1.0})],
        [(0, 'Generated', 1, 'Fac'), (1, 'Color', 2, 'Color'), (2, 'Emission', -1, 'Surface')])
       Curves[0] == (0.0, 0.0, 0.0), Curves[128] == (0.25, 0.5, 0.5),
       Curves[256] == (1.0000001192092896, 1.0, 1.0)
     ```
     What each literal says:
     - the node order is the tree's own order, which the walk of `B7-flatten.md:264-282` keeps: `coords` first, then
       the batch-5 node, then `emit`, and `output` is not a node (B8's rule 4, `B8-node-table-export.md:490-495`).
     - each scene links the node's colour output into `emit.Color`, so the Emission's `Color` is linked and only its
       `Strength` is exported (Blender's `1.0`; Cycles' own default is `10.0`, `EmissionNode.inc:6`), and the last
       link is `emit.Emission → output.Surface`.
     - `rgb_curves_scene` links `coords.Generated` into `Fac` and leaves `Color` at Blender's white, so `Color` is
       exported as a default and `Fac` is not: the curve is then `R(G(B(I(t))))` of white, which is the identity
       curve's value in all three channels, and the node's output is `interp(white, result, 1.0)` = the curve's value
       (`CurvesNode.constant_fold.inc`, `svm_node_curves`' `interp(value, result, fac)`, `kernel/svm/ramp.h:129`). A
       `Color` default of white is what makes the scene a test of the curve alone.
     - the `Ramp`/`Curves` numbers in the literals are the tuple lengths, not the values: the values are pinned by the
       two LUT tests above, which compare all 257 entries with Blender's own `evaluate` and with the measured samples.
5. `python.cpp`, the two array value forms (B6's helper `set_parameter_from_python`,
   `B6-shader-graph-api.md:186-222`). `## Interface` gives the declaration; the dispatch gains two cases beside the
   nine B6 lists:
   - `FLOAT_ARRAY`: a sequence of reals (not a `str`, not a 3-sequence of 3-sequences), each through
     `as_real(value, what)` (`python.cpp:301`), into `array<float>`, then
     `node.set(socket, values)` (`third_party/cycles/graph/node.cpp:144-148`).
   - `COLOR_ARRAY`: a sequence of 3-sequences of reals, each converted as B6's `COLOR` case converts one
     (`make_float3(float(x), float(y), float(z))`), into `array<packed_float3>`, then `node.set(socket, values)`
     (`node.cpp:156-160`).
   - a wrong shape raises `TypeError` through `throw_wrong_type` (`python.cpp:273`), as every other parameter type
     does; a `CLOSURE`, `VECTOR_ARRAY` or `POINT2_ARRAY` value still falls to B6's "no Python form" `ValueError`
     (`B6-shader-graph-api.md:221-222`), because no committed node definition of the six core batches has one.
   - `test_api_contract.py` compares the pyi with the built module by names, parameter names and defaults
     (`FACTS.md:310`), and `add_shader`'s signature does not change, so its 31 tests must stay at 31.
6. `tests/blender_it/golden_batch_05_scenes.py`, the two scenes (BRIEF.md:239-246). Each builder makes one
   `bpy.data.materials` material whose tree is: `ShaderNodeOutputMaterial` `output`; `ShaderNodeTexCoord` `coords`;
   the batch-5 node; `ShaderNodeEmission` `emit`; and the links that make the node drive the emission. The plane
   itself is B9's harness's (`B9-golden-harness.md:216-228`); this module supplies the material.
   - `color_ramp_scene`: `ShaderNodeValToRGB` `ramp`, its default identity ramp replaced by three elements —
     `(0.0, (0.0, 0.0, 0.0))`, `(0.5, (0.25, 0.5, 0.75))`, `(1.0, (1.0, 1.0, 1.0))`, interpolation `LINEAR` — and
     `coords.Generated → ramp.Fac`, `ramp.Color → emit.Color`, `emit.Emission → output.Surface`. Why not fold: `Fac` is
     linked from the Texture Coordinate node, so `ConstantFolder::all_inputs_constant` is false
     (`constant_fold.cpp:20-29`) and `RGBRampNode::constant_fold`'s `folder.all_inputs_constant()` guard keeps the node
     in the SVM. `emit.Color` is linked, so the Emission's own default is not used and the plane's radiance is the
     ramp's colour.
   - `rgb_curves_scene`: `ShaderNodeRGBCurve` `curves` with the mapping's first curve given a third point at
     `(0.5, 0.25)` — and `curves.mapping.update()` called right after it, because `CurveMapping.evaluate` reads the
     mapping's cached table and a point added without the update changes no sample (measured: the five samples stay
     `0.0`, `0.25`, `0.5`, `0.75`, `1.0` until the update and become step 1's values after it) — and the other three
     curves left at their identity, and `coords.Generated → curves.Fac`,
     `curves.Color → emit.Color`, `emit.Emission → output.Surface`. Why not fold: `Fac` is linked, so
     `CurvesNode::constant_fold`'s first branch (`folder.all_inputs_constant()`) does not run, and its second
     (`!input("Fac")->link && fac == 0.0f`, `CurvesNode.constant_fold.inc`) cannot fire because `Fac` is linked and
     Blender's default is `1.0` (step 1's probe).
   - Each builder returns the material, so the harness can write it and step 4's export test can read it. The two
     scenes are the two nodes' golden scenes, one per node, and no scene drives two batch-5 nodes: a failing scene then
     names one row.
7. `tests/blender_it/test_golden_batch_05.py`, two tests, one per scene, each `@pytest.mark.slow` (CLAUDE.md rule 6;
   the harness renders twice per scene):
   - `test_the_color_ramp_node_matches_cycles` and `test_the_rgb_curves_node_matches_cycles`. Each loads its builder
     from step 6's module with `_load_by_path` (`tests/blender_it/test_extension_it.py:53-64`), registers it under its
     name in `GOLDEN_SCENES` (`B9-golden-harness.md:241`), runs B9's `render_golden.py` as a subprocess with the
     isolated profile of `test_extension_it.py:149-154`, reads `cycles.npy`/`painterly.npy`/`golden.json`, and asserts
     `golden_rule.meets_rule(painterly, cycles)` with `max_abs_difference` in the failure message. The rule is B9's
     (`B9-golden-harness.md:318-337`) and this card states no tolerance, no band and no expected pixel value.
   - Each test skips with B9's own reason when its inputs are missing (`BLENDER` unset or no extension zip,
     `test_extension_it.py:76-101`), so `make blender-it` stays green on a machine without Blender.
8. `tests/blender/test_sync_shader_node_table.py`, B8's guard test
   (`test_the_table_has_only_the_rows_this_card_adds`, `B8-node-table-export.md:595-598`): its expected set grows from
   eight idnames to ten.
   ```
   set(NODE_TABLE) == {"ShaderNodeOutputMaterial", "ShaderNodeOutputWorld", "ShaderNodeEmission",
                       "ShaderNodeTexCoord", "ShaderNodeValue", "ShaderNodeRGB", "ShaderNodeMath",
                       "ShaderNodeVectorMath", "ShaderNodeValToRGB", "ShaderNodeRGBCurve"}
   ```
   Ten idnames and nine Cycles rows, because B8's two output nodes share one row (`output`) and every other row is one
   idname. Nothing else in that file changes: its ladder table, its enum test and its unknown-node test are B8's, and
   its expected `PainterlyUnknownNode` stays `ShaderNodeBsdfPrincipled` (batch 11's, BRIEF.md:289-290).
9. `.venv/bin/ruff format` on the three new files and the two modified Python ones, then `.venv/bin/ruff check .`,
   then every acceptance command.

## Acceptance

Run every command from the repository root; the queue translates them with BACKLOG.md's table (`make check` → `CHECK`,
`make test-blender` → the same target with `KNOBS`, `build/dev` → `build/q`, `.venv/bin/<tool>` →
`MAIN/.venv/bin/<tool>`, any Python command prefixed with `PYTHONPATH="$PWD/analysis"`).
1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and the audit's
   `RESULT: PASS` line. This card adds no C++ doctest, so the doctest counts are the previous card's and must not move;
   the pytest count grows by step 4's six tests. `CHECK`'s `vendor-check` step is what proves step 3's manifest is
   consistent, and its `test_api_contract.py` run is what proves step 5 kept `add_shader`'s signature.
2. `make audit` prints `RESULT: PASS`: the two conversions live in `python.cpp`'s anonymous namespace, so the module
   exports `PyInit__painterly` alone and links no new library (`exports.map:1`).
3. `make test-blender` exits 0. Report its last line.
4. `.venv/bin/python -m pytest tests/blender/test_sync_shader_batch_05.py -q` prints `6 passed`: step 4's
   `1 + 1 + 1 + 1 + 2 = 6`. The count is the number of test functions step 4 lists; if it prints another count, the
   card's count is wrong and that is a finding, not a tolerance.
5. `.venv/bin/python -m pytest tests/blender/test_sync_shader_node_table.py -q` prints `6 passed`. The count is B8's
   own (`B8-node-table-export.md:571-603`): the row-vs-definition test, the two ladder tests, the enum test, the guard
   test and the unknown-idname test are `1 + 2 + 1 + 1 + 1 = 6`. This card changes only the guard's expected set
   (step 8), so the count must not move; if it prints another count, a test arrived or vanished in that file.
6. `make blender-it` exits 0. Report its last line, the collected and passed counts, and the two golden tests'
   statistics as the harness prints them. This card states no count for the file set, because the total is B9's to fix
   and not this card's, and each test skips with B9's reason when its inputs are missing.
7. `git status --porcelain` lists only the three Create paths and the six Modify paths above.

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- drop the `kernel/svm/ramp_util.h` include from `src/cycles/fragment_units.toml` → the `shader_nodes` unit does not
  compile and `make build` fails on `rgb_ramp_lookup` being undeclared in `RGBRampNode::constant_fold`'s fragment;
- export `interpolate` as `color_ramp.interpolation == "LINEAR"` instead of `!= "CONSTANT"` → step 4's parameter test
  fails on the `EASE`/`B_SPLINE`/`CARDINAL` cases, which interpolate in Cycles (`shader.cpp:418-419` maps only
  `COLBAND_INTERP_CONSTANT` to `false`);
- read `min_x`/`max_x` from `mapping.curves[0].points` instead of all four curves → step 4's curve test fails on the
  green-curve case;
- build the ramp's LUT at 256 midpoints (`(i + 0.5) / 256`) instead of at `i / 256` → step 4's ramp test fails on
  `Ramp[0]` (`0.00390625` instead of `0.0`), and `colorramp_to_array`'s `float(i) / float(size)`
  (`blender/util.h:146`) is the rule;
- map `extend == "EXTRAPOLATED"` to `False` → step 4's parameter test fails on the default case, where Cycles'
  `extrapolate` default is `true` (`RGBCurvesNode.inc:8`);
- forget step 5's `FLOAT_ARRAY` case → `add_shader` raises B6's `ValueError` naming `Ramp Alpha`, so both golden tests
  of step 7 fail at the export, before any render;
- forget step 8 → `make test-blender` fails B8's guard test with the two missing idnames;
- drive either scene from a constant instead of the Texture Coordinate node → `all_inputs_constant` is true and the
  graph folds to a constant emission, so step 7 compares two folded constants and proves nothing about the node.

Report: the doctest and pytest counts, the audit line, the two golden statistics and every mutation you ran with its
first failing check.

## Commit

`N5: node batch 5: Color Ramp and RGB Curves — host fragments, two node_table rows and their golden tests`

## Open for Opus

1. **The LUT has no value form in B6's binding, and every option touches B6.** Cycles stores both tables as
   `SOCKET_*_ARRAY` members (`RGBRampNode.inc:5-6`, `RGBCurvesNode.inc:5`) and B6's parameter dispatch covers nine
   scalar socket types only (`B6-shader-graph-api.md:166-176`, `:221-222`), so `add_shader` cannot carry a table today;
   and a Color Ramp without its table emits no SVM node (`RGBRampNode.compile-SVMCompiler.inc`), so the batch cannot
   land without one of these. The options:
   - (a) this card's: two array value forms in `set_parameter_from_python`, the table passed as an ordinary parameter
     by member name — no tuple shape changes, no row of another card's changes, one CONTRACT comment block on
     `add_shader` and one helper in `python.cpp`;
   - (b) a separate `Scene.add_table(shader: int, node: int, table: list[tuple[float, ...]]) -> None`, which keeps the
     parameters dict scalar-only but adds a method to the CONTRACT and a second pass over the graph;
   - (c) the node tuple grows a fourth element (the shape batch 1's draft assumes nowhere but which a table would
     force), which changes every existing 3-tuple literal in B8's and batch 1's export tests.
   (a) is the smallest and is what the steps implement; it does need B6 to have landed first, which is why this card's
   `Depends on:` names B6 as well as B8 and B9. No expected value of this card depends on the choice: the LUTs of step 4
   are `node_table.py`'s, and the two golden tests compare renders.
2. **B9's interface has no `assert_golden`.** B9's drafted card gives `GOLDEN_SCENES` (`B9-golden-harness.md:147`),
   `build(**variant)` (`:144`), `render_golden.py` (`:166-177`) and `golden_rule.meets_rule` (`:163`), and its slow
   test drives them (`:338-357`). Batch 1's card assumed one `assert_golden(scene, name, tmp_path)`
   (`N1-batch-01-value-rgb-math.md:243`, `:669-676`) because B9 was not drafted when it was written. This card follows
   B9 as drafted and writes its own two tests; the alternatives are (a) B9 gains the wrapper and every batch card calls
   it, or (b) each batch card writes its own test as this one does. Batch 1's card, the template, should be reconciled
   with whichever is chosen.
3. **The expected values' derivation.** `AGENTS.md` requires a script that produces a committed number to be committed
   next to its output, and this card's `allowedPaths` holds only this file, so the prototype that produced step 4's two
   export literals and the LUT samples is not in the diff. What the card does instead: step 1's probe is quoted with
   its output, and each literal follows mechanically from a scene step 6 spells out and B8's rules. If Opus prefers the
   prototype committed, it needs a path outside this card's `allowedPaths`, for example
   `docs/handoff/drafts/M6b/N5-derive.py`, as batch 1's `## Open for Opus` 2 asks for its own.
4. **What a ramp golden scene can prove.** Both nodes compute their output from a host LUT that Blender fills
   (`blender/shader.cpp:410-420`, `:368-380`), so a render comparison between Blender's Cycles and painterly's SVM
   compares the same LUT fed to two implementations of the same evaluator — it pins the export, not Cycles'
   arithmetic. That is exactly `BRIEF.md:286`'s "the curve LUT is sampled as Cycles samples it", so the card keeps the
   scenes; the complement is a C++ doctest that runs `svm_node_rgb_ramp` on a hand-built three-entry table and compares
   the interpolation at dyadic `fac` values with the polynomial written out, which tests the evaluator and not the
   export. Only the first is in this card's scope; Opus may want the second as a case in
   `src/test/test_cycles_svm_stack_nodes.cpp` (T6.3's file, which already dispatches the stack and table nodes).
5. **`Parallel-safe: no`, against the plan's row.** `FACTS.md:362` records the plan's row as
   `"Node batch i of 12: <name> (node-table rows and golden tests; parallel-safe)"`, but every batch card edits the
   same literal in B8's guard test (`B8-node-table-export.md:595-598`, this card's step 8). The options are batch 1's
   `## Open for Opus` 3's: keep `no` (this card) and run the batches in sequence, or replace the guard with a
   per-batch subset assertion plus a per-batch count.
6. **What this card does not decide.** Per `BRIEF.md:295-301`: light node graphs stay out of v1; whether a node
   material's emission is scaled by `emission_scale` is open, and this card passes no knob (decision 8); Bump, Normal
   Map and the Attribute node are out. `CurvesNode`'s siblings `VectorCurvesNode` and `FloatCurveNode` are vendored in
   the same file and are in none of the twelve batches (`plan.md:305` as quoted at `FACTS.md:39-43`), so this card adds
   no row for them and `PainterlyUnknownNode` reports them; `NODE_FLOAT_CURVE` is vendored (step 1) and stays
   unexercised by a node until a later batch needs it.
