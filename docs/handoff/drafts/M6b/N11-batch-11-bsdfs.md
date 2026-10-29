# N11 — Node batch 11: Principled, Diffuse, Glossy, Glass, Refraction, Emission and Transparent BSDFs (drafted from BRIEF.md section 2, "Node batches")

Milestone: M6b · Depends on: B4, B8, B9 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "Node batches" (lines 274-293, batch 11 at `:289-290`), per
that brief's section 4 (lines 303-324) and the decisions of its section 1 that touch it: decision 5 (`:52-57`, node
types by Cycles type name, links and linkable defaults by UI name, parameters by member name with enums by `NodeEnum`
name), decision 7 (`:67-74`, per-hit lobes sampled exactly as SPEC §6 says), decision 8 (`:75-77`, no new knob) and
decision 9 (`:78-79`, every expected value is an exact equality or a derived rule). Code facts are
`docs/handoff/drafts/M6b/FACTS.md` §3.13 (`:324-339`, batch 11's state at `:336-337`), §3.5 (`:236-243`, the collector),
§3.4 (`:223-234`, `PainterlyShaderManager`) and §5 row R4 (`:378`, the Principled lookup tables), re-read at this
clone's HEAD in every file cited below. The bpy facts are measured on this host with the project's `bpy` 5.2.2 by the
probe of step 1, quoted with its output.

`BRIEF.md:274-283` gives every node of the six core batches the same four bullets, and `:289-290` gives batch 11 one
further sentence that changes bullet 4: "Their golden test is the closure policy's lobe list at a hit, not an image,
because lobes are painterly's own." This card turns each bullet into a rule in `## Goal` and states, for each of the
seven nodes, whether the bullet applies.

## Goal

Batch 11's seven BSDF nodes are exported and compiled through the whole M6b path, and each has a golden test of the
lobe list it produces at a hit:

- **Rule 1: the nodes' evaluators are vendored, and this card adds nothing to `kernel/`** (BRIEF.md:276). For batch 11
  the bullet is already satisfied at HEAD: `NODE_CLOSURE_BSDF`, `NODE_CLOSURE_BACKGROUND`, `NODE_CLOSURE_WEIGHT` and
  `NODE_MIX_CLOSURE` are vendored (`third_party/cycles/VENDORED.toml:3562-3598`), the switch lists them
  (`src/cycles/svm_nodes.toml:109-112`) and the evaluator `kernel/svm/closure.h` is vendored (`VENDORED.toml:1350`'s
  entry) and included (`svm_nodes.toml:30`). `FACTS.md:336-337` says the same ("11 BSDFs, Emission: yes"). The rule is
  therefore a check, not a change: step 1's greps print the counts of step 1.
- **Rule 2: the host class fragments are present, and this card adds none** (BRIEF.md:277-281). `FACTS.md:336-337` says
  "all seven present" and step 1 counts the `VENDORED.toml` entries: `DiffuseBsdfNode` 3 + its `node_define`,
  `GlossyBsdfNode` 6 + its `node_define`, `GlassBsdfNode` 3 + its `node_define`, `RefractionBsdfNode` 3 + its
  `node_define`, `PrincipledBsdfNode` 12 + its `node_define`, `TransparentBsdfNode` 3 + its `node_define`,
  `EmissionNode` 4 + its `node_define`, plus the two shared bases `BsdfBaseNode` (2 members) and `BsdfNode`
  (4 members), which the seven subclasses' `compile`s call. Batch 11 is therefore a **check**, like batch 1: no
  `third_party/` line and no `fragment_units.toml` entry. The three bullets BRIEF.md:277-281 names as missing are
  batch 5's, 6's and 10's classes, and no class of this batch is on that list.
- **Rule 3: `node_table.py` gains batch 11's seven rows** (BRIEF.md:282): `ShaderNodeBsdfPrincipled` → `principled_bsdf`,
  `ShaderNodeBsdfDiffuse` → `diffuse_bsdf`, `ShaderNodeBsdfGlossy` → `glossy_bsdf`, `ShaderNodeBsdfGlass` →
  `glass_bsdf`, `ShaderNodeBsdfRefraction` → `refraction_bsdf`, `ShaderNodeBsdfTransparent` → `transparent_bsdf` and
  `ShaderNodeEmission` → `emission`. The last is **B8's row already** (`B8-node-table-export.md:400`:
  `"ShaderNodeEmission": NodeRow("emission", ("Color", "Strength"), ("Emission",))`), so this card adds six and
  changes none of B8's. The traps of the batch:
  - `ShaderNodeBsdfGlossy`'s `bl_idname` is `ShaderNodeBsdfAnisotropic` (step 1's probe: `bl_idname=ShaderNodeBsdfAnisotropic`,
    `bl_label=Glossy BSDF`), which is the idname Cycles' own `add_node` tests (`blender/shader.cpp:645`). A row keyed by
    `ShaderNodeBsdfGlossy` would never fire, because `NODE_TABLE` is keyed by `bl_idname`
    (`B8-node-table-export.md:186`);
  - every one of the seven nodes has a **`Weight` input that is `is_unavailable`** (step 1's probe), which B8's
    `export_graph` skips (`B8-node-table-export.md:497-499`) and Cycles' `NodeType` does not have: it is Blender's
    closure-mix-weight UI, not a Cycles socket;
  - the three distribution enums (`Glossy`, `Glass`, `Refraction`) and Principled's two (`Distribution`,
    `Subsurface Method`) are RNA properties whose identifiers need aliases the lowercase rule misses (step 1's probe:
    `BECKMANN` → `beckmann` matches, but `MULTI_GGX` → `multi_ggx` matches too, while Principled's `RANDOM_WALK_SKIN`
    does not match Cycles' `random_walk_skin` only because of case) — step 4 pins each one;
  - `PrincipledBsdfNode` has **33 inputs** (step 1's probe), of which one is `Weight` (unavailable) and the rest are
    Cycles sockets; its `Normal`, `Tangent` and `Coat Normal` are `SOCKET_IN_NORMAL` and `SOCKET_IN_VECTOR`, so B6's
    `NORMAL` form is the one that carries them (`B6-shader-graph-api.md:211-213`).
- **Rule 4: each node has a golden test, and it is the closure policy's lobe list at a hit, not an image**
  (BRIEF.md:283, `:289-290`). Seven doctest cases in a new `src/test/test_cycles_svm_batch_11.cpp`, each of which
  builds the node's graph in C++, compiles it with `PainterlyShaderManager`, evaluates it through
  `svm_eval_nodes<painterly_svm_surface_feature_mask, SHADER_TYPE_SURFACE>`, collects with `painterly_svm_collect` and
  compares the lobe list, its count, the emission and `num_dropped` with a literal, exactly as T6.7's closure tests do
  (`src/test/test_cycles_svm_closures.cpp:150-185`'s `describe()`, `:560-600`'s mix/add cases). No image is rendered and
  no tolerance appears: every value is a float32 product of dyadic inputs, widened to double, so the comparison is
  `describe(a) == describe(b)` (`B4-svm-trace-pixel.md:570-584`). The policy these literals encode is Opus's
  (`T6.7:175-208`, "The policy is Opus's. Changing it needs an Opus decision"), and this card **reads** it: it states no
  new rule, and `## Open for Opus` 1 records what happens if the policy changes.
  `## Open for Opus` 2 records why the tests are C++ doctests rather than `tests/blender_it` scenes: B9's harness
  compares images (`B9-golden-harness.md:318-337`), and `BRIEF.md:289-290` says batch 11's golden test is not an image.

Nothing in the core changes: no kernel type, no scene API, no new knob (decision 8, `BRIEF.md:75-77`), so no image, no K
and no parity test of M3-M5 moves. Batch 11's only C++ is a test file.

Which of the four bullets applies, per node (FACTS.md:336-337 is the current state of the seven rows; the file:line
column is this clone's HEAD):

| node | Blender idname | Cycles type | 1. vendor the evaluator | 2. host class fragments | 3. `node_table.py` row | 4. golden test |
|---|---|---|---|---|---|---|
| Principled | `ShaderNodeBsdfPrincipled` | `principled_bsdf` | nothing to do: `NODE_CLOSURE_BSDF` at `VENDORED.toml:3562`, `svm_nodes.toml:109`; `kernel/svm/closure.h` at `VENDORED.toml:1350` | nothing missing: definition `node_define/PrincipledBsdfNode.inc`, 12 members (`VENDORED.toml:3769-3850`, `:3992`, `:4082`), `BsdfNode::compile` `:3922-3942`, `BsdfBaseNode` `:3679-3688` | **add** | **add** |
| Diffuse | `ShaderNodeBsdfDiffuse` | `diffuse_bsdf` | nothing to do | nothing missing: 3 members (`VENDORED.toml:3760`, `:3982`, `:4072`) | **add** | **add** |
| Glossy | `ShaderNodeBsdfAnisotropic` | `glossy_bsdf` | nothing to do | nothing missing: 6 members (`VENDORED.toml:3706-3733`, `:3952`, `:4042`) | **add** | **add** |
| Glass | `ShaderNodeBsdfGlass` | `glass_bsdf` | nothing to do | nothing missing: 3 members (`VENDORED.toml:3742`, `:3962`, `:4052`) | **add** | **add** |
| Refraction | `ShaderNodeBsdfRefraction` | `refraction_bsdf` | nothing to do | nothing missing: 3 members (`VENDORED.toml:3751`, `:3972`, `:4062`) | **add** | **add** |
| Emission | `ShaderNodeEmission` | `emission` | nothing to do | nothing missing: 4 members (`VENDORED.toml:2002`, `:2152`, `:2387`, `:2396`) | **B8's, unchanged** | **add** |
| Transparent | `ShaderNodeBsdfTransparent` | `transparent_bsdf` | nothing to do | nothing missing: 3 members (`VENDORED.toml:3859`, `:4002`, `:4092`) | **add** | **add** |

So of the four bullets, bullet 1 applies to no node (a check, step 1) and bullet 2 to no node (a check, step 1);
bullet 3 applies to six nodes (step 2) and bullet 4 to all seven (steps 5-6).

## Read first

- `CLAUDE.md` rules 1, 2 and 3 (scope; named knobs; PEP 8 with type hints and docstrings that state units);
  `AGENTS.md` "Expected values are evidence, not targets" and "Measured means reproducible".
- `docs/handoff/drafts/M6b/BRIEF.md` lines 274-293 (this card's mandate; `:289-290` is batch 11's seven nodes and the
  sentence that its golden test is a lobe list), `:30-37` (decision 3, `cycles_shader` and the constant path),
  `:67-74` (decision 7, per-hit lobes and `two_sided`), `:237-255` (B9's harness), `:52-57` (the socket-name rule),
  `:75-79` and `:295-301` (the open questions).
- `docs/handoff/drafts/M6b/FACTS.md` §3.13 (`:324-339`, batch 11's line `:336-337`), §3.5 (`:236-243`: the collector's
  five functions, `PainterlySvmMaterial`'s members and "zero lobes -> one `LOBE_DIFFUSE` of weight 0 :205-210"), §3.4
  (`:223-234`: `PainterlyShaderManager`'s `device_update_pre`/`post` and `bind_kernel_globals`) and §5 row R4 (`:378`,
  the Principled lookup tables and their state).
- `docs/spec.md:190-207` (SPEC §6: the four lobe kinds, the selection rule, `p`, "Selection never touches K", the
  `two_sided` flip, and `:202` "M6 evaluates Blender node graphs per hit into the same lobe list"),
  `:51` ("Only diffuse events advance K") and `:168-171` (emission first, `L = 0 + (E·emission_gain)`).
- `docs/handoff/drafts/M6b/N1-batch-01-value-rgb-math.md`: the table of `## Goal` (`:70-75`), the rows literal
  (`:186-204`), the getters (`:209-225`), the guard test's new expected set (`:594-608`) and `## Acceptance`
  (`:612-634`).
- `docs/handoff/drafts/M6b/B8-node-table-export.md`: `NodeRow` and the six names `node_table.py` exports (`:172-201`),
  B8's `ShaderNodeEmission` row (`:400`), the socket ladders (`:422-457`), the four `ENUM_ALIASES` (`:458-468`),
  `export_graph` (`:485-509`, the `is_unavailable` and `SHADER` skips at `:497-499`), the row-vs-definition regexes
  (`:574-589`) and the guard test a batch card must change (`:595-598`).
- `docs/handoff/drafts/M6b/B6-shader-graph-api.md`: the two methods (`:96-109`), the nine parameter types and the
  three float3 linkable forms (`:166-176`, `:211-213`), the `ENUM` form (`:220-221`) and the `NORMAL` note.
- `docs/handoff/drafts/M6b/B4-svm-trace-pixel.md`: the acceptance sentence that batch 11's lobe literals come from
  (`:169-179`), the `describe()` comparison (`:570-584`) and the "same lobe list at every hit" note (`:637`).
- `docs/handoff/drafts/M6a/T6.7-svm-closures.md:160-220`: the closure policy table (`:175-208`, Opus's, with the
  weight each category gets), the evaluation contract (`:209-217`) and decision 7's exactness argument
  (`T6.7:218-232`: dyadic inputs, the double products, the one table value recomputed by `reference_lookup_corner()`).
- `src/test/test_cycles_svm_closures.cpp:150-185` (`describe()`: one line per lobe, `emission`, `dropped`) and
  `:540-620` (the mix/add fixtures this card's cases copy the shape of), plus `src/test/cycles_svm_test_support.h:122-230`
  (`PainterlySvmTestProgram`) and `:313-348` (`painterly_svm_test_shader_data`, the node feature mask).
- `src/painterly/kernel/svm/collect.h:39-48` (the two masks), `:52-60` (`PainterlySvmMaterial`), `:76-105`
  (`painterly_svm_lobe_kind`), `:147-163` (the weight helpers) and `:165-215` (`painterly_svm_collect`, the zero-lobe
  rule at `:205-210`).
- The vendored definitions whose rows this card transcribes, each read in full:
  `third_party/cycles/fragments/scene/shader_nodes_cpp/node_define/{PrincipledBsdfNode,DiffuseBsdfNode,
  GlossyBsdfNode,GlassBsdfNode,RefractionBsdfNode,TransparentBsdfNode,EmissionNode}.inc`.
- Upstream `intern/cycles/blender/shader.cpp`, read in the pinned checkout (never edited, not in this repo): the seven
  `add_node` cases — `ShaderNodeBsdfAnisotropic` `:645-663`, `ShaderNodeBsdfGlass` `:664-678`,
  `ShaderNodeBsdfRefraction` `:679-690`, `ShaderNodeBsdfPrincipled` `:726-751` (the two enums from `custom1` and
  `custom2`), `ShaderNodeBsdfDiffuse` `:597-600`, `ShaderNodeBsdfTransparent` `:755-757`, `ShaderNodeEmission`
  `:773-776` — and the `set_default_value` table `:223-275` that B8's `_default_of` transcribes.
- `tests/blender/conftest.py:22`, `:44-53` and `:62-73`; `src/test/CMakeLists.txt:77-99` (where a new doctest source is
  added) and `:95`, `:98` (the two existing `test_cycles_svm_*` sources).
- `pyproject.toml:38-44` and `:48`.
- The expected values of steps 1, 3 and 4: the probe quoted there, measured on this host with `bpy` 5.2.2.

## Create

- `tests/blender/test_sync_shader_batch_11.py`
- `src/test/test_cycles_svm_batch_11.cpp`

## Modify

- `src/blender/addon/sync/shader/node_table.py` (B8's file): batch 11's six rows in `NODE_TABLE` (step 2), after B8's
  four and batch 1's four, and the module docstring's sentence about which rows exist updated to name this batch.
- `tests/blender/test_sync_shader_node_table.py` (B8's file): the guard test of
  `B8-node-table-export.md:595-598`, `test_the_table_has_only_the_rows_this_card_adds`, now expects fourteen idnames —
  B8's four plus batch 1's four plus this card's six (step 7) — and its `PainterlyUnknownNode` case must name a node no
  batch has any more (`## Open for Opus` 3).
- `src/test/CMakeLists.txt`: one `target_sources(painterly_tests PRIVATE test_cycles_svm_batch_11.cpp)` line beside the
  two existing `test_cycles_svm_*` lines (`:95`, `:98`).

## Do not touch

- `third_party/cycles/**`, `src/cycles/**`: rules 1 and 2 are satisfied at HEAD (step 1), and `third_party/` is
  `tools/vendor_sync.py`'s alone (R6). A batch-11 step that wanted to vendor or extract something would mean
  `FACTS.md:336-337` is wrong, which is a `report_blocked`, not a change.
- `src/painterly/**`: nothing in the core is batch 11's. `painterly_svm_collect` is T6.7's, the device update is B2's
  and the trace loop is B4's, and the closure policy the literals encode is Opus's (`T6.7:208`). A test that needed a
  change to `collect.h` would be proposing a policy change, which is `## Open for Opus` 1's business.
- `src/blender/addon/sync/shader/export.py`: B8's rule 4 is generic and this card's rows are data only.
- B8's `ShaderNodeEmission` row (`B8-node-table-export.md:400`): this card's golden test uses it and changes no line.
- `src/blender/addon/sync/shader/flatten.py`, `src/blender/addon/sync/{__init__,material,world,geometry}.py`: B7's and
  B8's.
- `tests/blender_it/**`: B9's harness, and `BRIEF.md:289-290` puts this batch's golden test in the lobe list, not in an
  image, so this card adds no `GOLDEN_SCENES` entry.
- `tests/core/test_api_contract.py`: it must pass unchanged at its own 31 tests, because this card adds no binding.
- `tests/blender_it/test_extension_it.py`, `tests/blender_it/run_reference.py`, `tests/blender/test_render_reference.py`,
  `tests/blender/conftest.py`, `tests/conftest.py`: T4.2's, T4.3's and T4.4's.
- `Makefile`, `pyproject.toml`, `src/blender/CMakeLists.txt`: no new target, no new marker, no new module source.
- `NODE_TABLE` beyond this card's six rows, and every other batch's golden test.
- `docs/spec.md`, `docs/plan.md`, `CLAUDE.md`, `AGENTS.md`, `BACKLOG.md`, `docs/handoff/` beyond this card's own file.

## Interface

Not a CONTRACT: this card adds no public name to `_painterly`, no Python API of the add-on and no C++ declaration. The
two interfaces it uses are B8's (the row) and B6's (the node tuple), and the C++ it adds is one doctest source.

**The six new rows** (`src/blender/addon/sync/shader/node_table.py`, B8's `NodeRow`,
`B8-node-table-export.md:179-185`):

```python
NODE_TABLE: Final[Mapping[str, NodeRow]] = {
    # ... B8's four rows and batch 1's four, unchanged. B8's ShaderNodeEmission row is batch 11's
    # seventh node and stays exactly as B8 wrote it (B8-node-table-export.md:400).
    # PrincipledBsdfNode.inc:3-67. 32 linkable inputs (33 Blender sockets, one of them `Weight`).
    "ShaderNodeBsdfPrincipled": NodeRow(
        "principled_bsdf", PRINCIPLED_INPUTS, ("BSDF",), _principled_parameters),
    # DiffuseBsdfNode.inc:3-13. `Color`, `Normal`, `Roughness`; Cycles' SurfaceMixWeight is SVM_INTERNAL.
    "ShaderNodeBsdfDiffuse": NodeRow("diffuse_bsdf", ("Color", "Normal", "Roughness"), ("BSDF",)),
    # GlossyBsdfNode.inc:3-25. The Blender idname is ShaderNodeBsdfAnisotropic (step 1's probe).
    "ShaderNodeBsdfAnisotropic": NodeRow(
        "glossy_bsdf", ("Color", "Normal", "Tangent", "Roughness", "Anisotropy", "Rotation"),
        ("BSDF",), _glossy_parameters),
    # GlassBsdfNode.inc:3-24.
    "ShaderNodeBsdfGlass": NodeRow(
        "glass_bsdf", ("Color", "Normal", "Roughness", "IOR", "Thin Film Thickness", "Thin Film IOR"),
        ("BSDF",), _glass_parameters),
    # RefractionBsdfNode.inc:3-21.
    "ShaderNodeBsdfRefraction": NodeRow(
        "refraction_bsdf", ("Color", "Normal", "Roughness", "IOR"), ("BSDF",), _refraction_parameters),
    # TransparentBsdfNode.inc:3-11.
    "ShaderNodeBsdfTransparent": NodeRow("transparent_bsdf", ("Color",), ("BSDF",)),
}
```

`PRINCIPLED_INPUTS` is the 32 UI names of `PrincipledBsdfNode.inc:21-60` in file order (`Base Color`, `Metallic`,
`Roughness`, `IOR`, `Alpha`, `Thin Wall`, `Normal`, `Diffuse Roughness`, `Subsurface Weight`, `Subsurface Radius`,
`Subsurface Scale`, `Subsurface IOR`, `Subsurface Anisotropy`, `Specular IOR Level`, `Specular Tint`, `Anisotropic`,
`Anisotropic Rotation`, `Tangent`, `Transmission Weight`, `Sheen Weight`, `Sheen Roughness`, `Sheen Tint`,
`Coat Weight`, `Coat Roughness`, `Coat IOR`, `Coat Tint`, `Coat Normal`, `Emission Color`, `Emission Strength`,
`Thin Film Thickness`, `Thin Film IOR` — 31 — plus the one the file order puts between them, `Weight`, which Cycles does
not have; step 2 counts them from the file and the row names exactly the 31).

The three getters:

```python
def _principled_parameters(node: bpy.types.Node) -> dict[str, object]:
    """Cycles' `distribution` and `subsurface_method` (PrincipledBsdfNode.inc:6-19), by NodeEnum name."""
    return {"distribution": _PRINCIPLED_DISTRIBUTION[node.distribution],
            "subsurface_method": _PRINCIPLED_SUBSURFACE[node.subsurface_method]}

def _glossy_parameters(node: bpy.types.Node) -> dict[str, object]:
    """Cycles' `distribution` (GlossyBsdfNode.inc:9-14), by NodeEnum name."""
    return {"distribution": _GLOSSY_DISTRIBUTION[node.distribution]}

def _glass_parameters(node: bpy.types.Node) -> dict[str, object]:
    """Cycles' `distribution` (GlassBsdfNode.inc:9-14), by NodeEnum name."""
    return {"distribution": _GLASS_DISTRIBUTION[node.distribution]}

def _refraction_parameters(node: bpy.types.Node) -> dict[str, object]:
    """Cycles' `distribution` (RefractionBsdfNode.inc:9-13), by NodeEnum name."""
    return {"distribution": _REFRACTION_DISTRIBUTION[node.distribution]}
```

The four tables are step 1's measurement, one entry per Blender identifier and one per Cycles name:

```python
# Blender's identifier -> Cycles' NodeEnum name. Step 1's probe prints both sides.
_PRINCIPLED_DISTRIBUTION = {"GGX": "ggx", "MULTI_GGX": "multi_ggx"}                      # :6-7
_PRINCIPLED_SUBSURFACE = {"BURLEY": "burley", "RANDOM_WALK": "random_walk",
                          "RANDOM_WALK_SKIN": "random_walk_skin",
                          "RANDOM_WALK_LEGACY": "random_walk_legacy"}                    # :12-15
_GLOSSY_DISTRIBUTION = {"BECKMANN": "beckmann", "GGX": "ggx",
                        "ASHIKHMIN_SHIRLEY": "ashikhmin_shirley", "MULTI_GGX": "multi_ggx"}  # :10-13
_GLASS_DISTRIBUTION = {"BECKMANN": "beckmann", "GGX": "ggx", "MULTI_GGX": "multi_ggx"}   # :10-12
_REFRACTION_DISTRIBUTION = {"BECKMANN": "beckmann", "GGX": "ggx"}                        # :10-11
```

They are per-row tables and not entries in B8's `ENUM_ALIASES` for the reason batch 10's card gives: `ENUM_ALIASES` is
keyed by RNA identifier alone (`B8-node-table-export.md:458-468`), and `GGX` and `BECKMANN` mean the same word in four
different nodes whose Cycles defaults differ (`GlossyBsdfNode.inc:14` defaults to `ggx`, `GlassBsdfNode.inc:14` to
`multi_ggx`, `RefractionBsdfNode.inc:13` to `ggx`). `## Open for Opus` 4 records the alternative.

**The doctest's interface** (`src/test/test_cycles_svm_batch_11.cpp`, one case per node):

```cpp
/* One case per batch-11 node: build the node's graph, compile it with PainterlyShaderManager, evaluate it
 * at a surface hit and compare the collector's lobe list, emission and num_dropped with a literal. The
 * helpers are T6.7's (src/test/test_cycles_svm_closures.cpp:150-185's describe()) and T6.6's scene
 * fixture (src/test/cycles_svm_test_scene.h). */
static void check_lobes(const char *node_type, const char *expected_description);
```

Each case's expected description is a `describe()` string: one `"<kind> <r> <g> <b> <ior>"` line per lobe, then
`"emission <r> <g> <b>"`, then `"dropped <n>"` (`test_cycles_svm_closures.cpp:150-185`), so a failing case prints both
sides and the difference is the failure.

## Steps

1. Preconditions. Each must hold; otherwise stop, commit nothing and report what you saw.
   - B4 landed: `painterly_trace_pixel` runs the SVM and the collector, which is what the golden cases' evaluation path
     mirrors. Each prints `1`.
     ```
     grep -c 'painterly_svm_collect' src/painterly/kernel/integrator/path.h
     grep -c 'svm_eval_nodes' src/painterly/kernel/integrator/path.h
     ```
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
   - Rule 1 holds — the four closure cases and the evaluator header are vendored. Each prints the number after it.
     ```
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_CLOSURE_BSDF"' third_party/cycles/VENDORED.toml         # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_CLOSURE_BACKGROUND"' third_party/cycles/VENDORED.toml   # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_CLOSURE_WEIGHT"' third_party/cycles/VENDORED.toml       # 1
     grep -c 'name = "kernel/svm/svm_h/svm_case/NODE_MIX_CLOSURE"' third_party/cycles/VENDORED.toml          # 1
     grep -c 'dest = "kernel/svm/closure.h"' third_party/cycles/VENDORED.toml                                # 1
     grep -cE '^  "NODE_CLOSURE_BSDF",$|^  "NODE_CLOSURE_BACKGROUND",$|^  "NODE_CLOSURE_WEIGHT",$|^  "NODE_MIX_CLOSURE",$' src/cycles/svm_nodes.toml   # 4
     ```
   - Rule 2 holds — the seven classes' fragments and the two shared bases are vendored. Each prints the count after it,
     and each is the number of `member/` entries plus its `node_define` line, so a class that lost a fragment fails
     here.
     ```
     for c in PrincipledBsdfNode DiffuseBsdfNode GlossyBsdfNode GlassBsdfNode RefractionBsdfNode \
              TransparentBsdfNode EmissionNode BsdfBaseNode BsdfNode; do
       printf '%-22s %s %s\n' "$c" \
         "$(grep -F "shader_nodes_cpp/member/$c." third_party/cycles/VENDORED.toml | wc -l)" \
         "$(grep -F "shader_nodes_cpp/node_define/$c\"" third_party/cycles/VENDORED.toml | wc -l)"
     done
     ```
     Measured at this HEAD, `member node_define` per class:
     ```
     PrincipledBsdfNode     12 1
     DiffuseBsdfNode        3 1
     GlossyBsdfNode         6 1
     GlassBsdfNode          3 1
     RefractionBsdfNode     3 1
     TransparentBsdfNode    3 1
     EmissionNode           4 1
     BsdfBaseNode           2 0
     BsdfNode               4 0
     ```
     `BsdfBaseNode` and `BsdfNode` have no `node_define` because they are not `NodeType`s: they are the two bases the
     seven subclasses' `compile`s call (`BsdfBaseNode::BsdfBaseNode`, `BsdfNode::compile`), and they are declared in
     `scene/shader_nodes.h`, which is vendored whole (`VENDORED.toml:835-836`).
   - The bpy facts rules 3 and 4 rest on. Save this probe as a file under `/tmp` and run it with
     `.venv/bin/python <file>`; it must print exactly the lines quoted after it (they are this card's measurement on
     bpy 5.2.2, and the rows and the doctest's literals of steps 2-6 are derived from them):
     ```python
     import bpy

     mat = bpy.data.materials.new("probe")
     mat.use_nodes = True
     tree = mat.node_tree
     tree.nodes.clear()

     NODES = ("ShaderNodeBsdfPrincipled", "ShaderNodeBsdfDiffuse", "ShaderNodeBsdfGlossy",
              "ShaderNodeBsdfGlass", "ShaderNodeBsdfRefraction", "ShaderNodeBsdfTransparent",
              "ShaderNodeEmission")
     for idname in NODES:
         node = tree.nodes.new(idname)
         print(idname, "bl_idname", node.bl_idname)
         print("  inputs ", [(s.identifier, s.type, s.is_unavailable) for s in node.inputs])
         print("  outputs", [(s.identifier, s.type, s.is_unavailable) for s in node.outputs])
         enums = sorted(p.identifier for p in node.bl_rna.properties
                        if not p.is_readonly and p.identifier in (
                            "distribution", "subsurface_method"))
         print("  enums  ", enums)
         for name in enums:
             print("   ", name, getattr(node, name),
                   [i.identifier for i in node.bl_rna.properties[name].enum_items])
     ```
     ```
     ShaderNodeBsdfPrincipled bl_idname ShaderNodeBsdfPrincipled
       inputs  [('Base Color', 'RGBA', False), ('Metallic', 'VALUE', False), ('Roughness', 'VALUE', False), ('IOR', 'VALUE', False), ('Alpha', 'VALUE', False), ('Thin Wall', 'BOOLEAN', False), ('Normal', 'VECTOR', False), ('Weight', 'VALUE', True), ('Diffuse Roughness', 'VALUE', False), ('Subsurface Weight', 'VALUE', False), ('Subsurface Radius', 'VECTOR', False), ('Subsurface Scale', 'VALUE', False), ('Subsurface IOR', 'VALUE', True), ('Subsurface Anisotropy', 'VALUE', False), ('Specular IOR Level', 'VALUE', False), ('Specular Tint', 'RGBA', False), ('Anisotropic', 'VALUE', False), ('Anisotropic Rotation', 'VALUE', False), ('Tangent', 'VECTOR', False), ('Transmission Weight', 'VALUE', False), ('Coat Weight', 'VALUE', False), ('Coat Roughness', 'VALUE', False), ('Coat IOR', 'VALUE', False), ('Coat Tint', 'RGBA', False), ('Coat Normal', 'VECTOR', False), ('Sheen Weight', 'VALUE', False), ('Sheen Roughness', 'VALUE', False), ('Sheen Tint', 'RGBA', False), ('Emission Color', 'RGBA', False), ('Emission Strength', 'VALUE', False), ('Thin Film Thickness', 'VALUE', False), ('Thin Film IOR', 'VALUE', False)]
       outputs [('BSDF', 'SHADER', False)]
       enums   ['distribution', 'subsurface_method']
         distribution MULTI_GGX ['GGX', 'MULTI_GGX']
         subsurface_method RANDOM_WALK ['BURLEY', 'RANDOM_WALK', 'RANDOM_WALK_SKIN', 'RANDOM_WALK_LEGACY']
     ShaderNodeBsdfDiffuse bl_idname ShaderNodeBsdfDiffuse
       inputs  [('Color', 'RGBA', False), ('Roughness', 'VALUE', False), ('Normal', 'VECTOR', False), ('Weight', 'VALUE', True)]
       outputs [('BSDF', 'SHADER', False)]
       enums   []
     ShaderNodeBsdfGlossy bl_idname ShaderNodeBsdfAnisotropic
       inputs  [('Color', 'RGBA', False), ('Roughness', 'VALUE', False), ('Anisotropy', 'VALUE', False), ('Rotation', 'VALUE', False), ('Normal', 'VECTOR', False), ('Tangent', 'VECTOR', False), ('Weight', 'VALUE', True)]
       outputs [('BSDF', 'SHADER', False)]
       enums   ['distribution']
         distribution MULTI_GGX ['BECKMANN', 'GGX', 'ASHIKHMIN_SHIRLEY', 'MULTI_GGX']
     ShaderNodeBsdfGlass bl_idname ShaderNodeBsdfGlass
       inputs  [('Color', 'RGBA', False), ('Roughness', 'VALUE', False), ('IOR', 'VALUE', False), ('Normal', 'VECTOR', False), ('Weight', 'VALUE', True), ('Thin Film Thickness', 'VALUE', False), ('Thin Film IOR', 'VALUE', False)]
       outputs [('BSDF', 'SHADER', False)]
       enums   ['distribution']
         distribution MULTI_GGX ['BECKMANN', 'GGX', 'MULTI_GGX']
     ShaderNodeBsdfRefraction bl_idname ShaderNodeBsdfRefraction
       inputs  [('Color', 'RGBA', False), ('Roughness', 'VALUE', False), ('IOR', 'VALUE', False), ('Normal', 'VECTOR', False), ('Weight', 'VALUE', True)]
       outputs [('BSDF', 'SHADER', False)]
       enums   ['distribution']
         distribution BECKMANN ['BECKMANN', 'GGX']
     ShaderNodeBsdfTransparent bl_idname ShaderNodeBsdfTransparent
       inputs  [('Color', 'RGBA', False), ('Weight', 'VALUE', True)]
       outputs [('BSDF', 'SHADER', False)]
       enums   []
     ShaderNodeEmission bl_idname ShaderNodeEmission
       inputs  [('Color', 'RGBA', False), ('Strength', 'VALUE', False), ('Weight', 'VALUE', True)]
       outputs [('Emission', 'SHADER', False)]
       enums   []
     ```
     (bpy prints one `DeprecationWarning` about `use_nodes` on stderr; it is not part of the output above.)
     What each line fixes:
     - **`ShaderNodeBsdfGlossy`'s `bl_idname` is `ShaderNodeBsdfAnisotropic`**, so the Glossy row is keyed by that
       string; a row keyed by `ShaderNodeBsdfGlossy` would never be found, because `NODE_TABLE` is keyed by `bl_idname`
       (`B8-node-table-export.md:186`). Cycles' own `add_node` tests the same string (`blender/shader.cpp:645`).
     - every node has a `Weight` input that is `is_unavailable` and that Cycles' definition does not have
       (`PrincipledBsdfNode.inc` has no `Weight`), so B8's `export_graph` skips it (`:497-499`) and no row names it.
     - `Principled` has 33 sockets and 31 of them are Cycles inputs; `Subsurface IOR` is `is_unavailable` in bpy 5.2.2
       (Blender's UI hides it for the non-subsurface methods), and B8's export skips it as well, so the row names it and
       the export carries its default only when it is available — the row is a data table and the skip is
       `export_graph`'s.
     - `Glossy`'s four inputs are `Color`, `Roughness`, `Anisotropy`, `Rotation` plus `Normal` and `Tangent`, and Cycles'
       definition names the same six (`GlossyBsdfNode.inc:5-20`); its order in bpy is `Color`, `Roughness`, `Anisotropy`,
       `Rotation`, `Normal`, `Tangent`, and the row's order is Cycles' (`Color`, `Normal`, `Tangent`, `Roughness`,
       `Anisotropy`, `Rotation`), which is what `B8-node-table-export.md:422-457`'s ladders resolve identifier by
       identifier.
     - `Glass`'s six inputs and `Refraction`'s four are Cycles' names in Cycles' order; `Transparent`'s one is `Color`.
     - the four distribution enums' identifiers and defaults are the four tables of `## Interface`, and
       `Refraction`'s Blender default is `BECKMANN` where Cycles' is `ggx` (`RefractionBsdfNode.inc:13`) — a difference
       the export carries, because it carries Blender's value (B8's rule, `B8-node-table-export.md:500-503`).
2. `node_table.py`, the six new rows of `## Interface`, transcribed from the vendored definitions: `cycles_type` is
   `NodeType::add`'s first argument (`PrincipledBsdfNode.inc:3` and the five others), `inputs`/`outputs` are the
   `SOCKET_IN_*`/`SOCKET_OUT_*` UI names in file order, and the parameters are the `SOCKET_ENUM` members a caller sets.
   Measured, from step 1's probe and the seven files:
   ```
   ShaderNodeBsdfPrincipled:   'principled_bsdf',   inputs=31 names,                                      outputs=['BSDF']
   ShaderNodeBsdfDiffuse:      'diffuse_bsdf',      inputs=['Color', 'Normal', 'Roughness'],              outputs=['BSDF']
   ShaderNodeBsdfAnisotropic:  'glossy_bsdf',       inputs=['Color', 'Normal', 'Tangent', 'Roughness', 'Anisotropy', 'Rotation'], outputs=['BSDF']
   ShaderNodeBsdfGlass:        'glass_bsdf',        inputs=['Color', 'Normal', 'Roughness', 'IOR', 'Thin Film Thickness', 'Thin Film IOR'], outputs=['BSDF']
   ShaderNodeBsdfRefraction:   'refraction_bsdf',   inputs=['Color', 'Normal', 'Roughness', 'IOR'],      outputs=['BSDF']
   ShaderNodeBsdfTransparent:  'transparent_bsdf',  inputs=['Color'],                                   outputs=['BSDF']
   ```
   - `Principled`'s 31 names are `PrincipledBsdfNode.inc:21-60` in file order, with `SOCKET_IN_INT(thin_wall, "Thin
     Wall", ...)` (`:27`) among them: B6's `INT` parameter type is what carries a `Thin Wall` default, and its socket in
     bpy is a `BOOLEAN` (step 1's probe), which B8's `_default_of` converts to Cycles' `0`/`1` `INT` because B6's
     `BOOLEAN` and `INT` are one socket type (`B8-node-table-export.md:500-503`).
   - each of the four distribution getters reads Blender's RNA and maps it through the tables of `## Interface`; the
     tables are literal and step 4 pins every entry.
   - the docstring states rule 3, the file each row comes from and that a row's `cycles_type` is a Cycles type name, not
     a Blender idname (decision 5, BRIEF.md:52-55), and the sentence about which rows exist now names batch 11's six
     beside B8's four and batch 1's four.
3. `src/test/test_cycles_svm_batch_11.cpp`, the seven cases. Each builds its node's graph in C++, as T6.7's cases do
   (`src/test/test_cycles_svm_closures.cpp:540-600`): `make_unique<ShaderGraph>()`, `create_node_by_name(*graph,
   "<cycles_type>")`, `set` the sockets it needs, `add_surface` with the node's closure output, `compile(*scene)`, then
   evaluate at `PainterlySvmTestScene::surface(0, 0)` (`src/test/cycles_svm_test_scene.h:101-119`) with
   `svm_eval_nodes<painterly_svm_surface_feature_mask, SHADER_TYPE_SURFACE>` and collect with
   `painterly_svm_collect`, and compare `describe()` (`test_cycles_svm_closures.cpp:150-185`) with a literal.
   - The inputs are dyadic, so every weight is exact: `Color` values are multiples of `1/8` or `1/4`, `Roughness` is
     `0.0` or `1.0` (which selects the smooth or the Oren-Nayar branch, `kernel/svm/closure.h:519-529`), `IOR` is
     `1.5`, `Anisotropy` and `Rotation` are `0.0`, and `Fac` (where a Mix Shader appears) is `0.5`. Every product is a
     float32 product of such values widened to double, which is exact (`T6.7:218-232`).
   - `Principled`'s one table-dependent value is its diffuse weight, `Base Color × (1 − F)`, which reads the GGX lookup
     table (`FACTS.md:378`, row R4). The case recomputes it with T6.7's `reference_lookup_corner()`
     (`src/test/test_cycles_svm_closures.cpp:186-…`, quoted at `T6.7:222-226`), repeating the float32 operations of
     `lookup_table_read_3D` at the corner a head-on view with `Roughness` 1 reads, so no tolerance appears. `T6.7:226`
     records that Opus checked the reference is sensitive: reading `table_ggx_gen_schlick_s` instead changes it.
   - Each case's literal is `describe()`'s text, so a failing case prints both sides. The seven cases' expected kinds
     are SPEC §6's, not this card's: Principled with `Metallic` 0 and `Transmission Weight` 0 gives a diffuse lobe
     (`CLOSURE_IS_BSDF_DIFFUSE`, `collect.h:76-105`), with `Metallic` 1 a mirror lobe (`CLOSURE_IS_BSDF_GLOSSY`), with
     `Transmission Weight` 1 a glass lobe carrying its `IOR` (`CLOSURE_IS_GLASS`); Diffuse a diffuse lobe; Glossy a
     mirror lobe; Glass a glass lobe; Refraction a glass lobe; Transparent a transparent lobe; Emission no lobe and an
     emission of `Color × Strength` (`kernel/closure/emissive.h:29-38`, `collect.h:170-175`). The weights are the
     policy's (`T6.7:175-208`) and this card writes no new one.
   - `src/test/CMakeLists.txt`: one line beside the two existing `test_cycles_svm_*` sources (`:95`, `:98`),
     `target_sources(painterly_tests PRIVATE test_cycles_svm_batch_11.cpp)`.
   - `## Open for Opus` 1 records that the literals encode Opus's policy and must be re-derived if it changes, and
     `## Open for Opus` 5 records that the file's seven cases are the batch's "golden test" in `BRIEF.md:289-290`'s
     sense.
4. `tests/blender/test_sync_shader_batch_11.py`, four tests. `bpy` only, no Blender run, and every expected value a
   literal compared with exact equality, so no tolerance appears.
   - `test_the_six_rows_are_the_vendored_node_definitions`: parse the six `.inc` files with B8's regexes
     (`SOCKET_IN_[A-Z0-9_]+\(\s*\w+\s*,\s*"([^"]+)"`, the `SOCKET_OUT_` form and `NodeType::add\("([a-z_]+)"`,
     `B8-node-table-export.md:574-589`) and compare each with the row. Expected: step 2's table. The files declare more
     sockets than the rows name (`SOCKET_ENUM(distribution, ...)`, `SOCKET_ENUM(subsurface_method, ...)` and the
     `SOCKET_*_ARRAY` members of the texture nodes), and the `SOCKET_IN_`/`SOCKET_OUT_` regexes do not match them, so
     the test asserts the filtered list and says so.
   - `test_the_glossy_row_is_keyed_by_the_blender_idname`: `NODE_TABLE["ShaderNodeBsdfAnisotropic"].cycles_type ==
     "glossy_bsdf"` and `"ShaderNodeBsdfGlossy" not in NODE_TABLE`, which is step 1's measurement
     (`bl_idname ShaderNodeBsdfAnisotropic`). This is the test that fails if the row is keyed by the UI name.
   - `test_the_four_distribution_enums_are_cycles_node_enum_names`: for each of the four nodes, every identifier of
     `bl_rna.properties["distribution" or "subsurface_method"].enum_items` maps onto the corresponding `.inc` file's
     `type_enum.insert("...")` names through the row's getter — five tables, fifteen entries in all — so a bpy that adds
     a distribution fails here instead of exporting a name Cycles' `NodeEnum::exists` rejects
     (`B6-shader-graph-api.md:220-221`).
   - `test_every_bsdf_row_omits_the_weight_socket`: every one of the seven idnames (B8's `ShaderNodeEmission`
     included) has a `Weight` input with `is_unavailable` true (step 1's probe) and no row names it, so
     `socket_name(idname, "Weight", "in")` returns `None` for each — an identifier the row does not name is a dropped
     default, not an error (`B8-node-table-export.md:454-457`).
5. `src/test/test_cycles_svm_batch_11.cpp`, the seven cases' bodies, with the literals step 3 derives. The file's
   includes are `cycles_svm_test_support.h`, `cycles_svm_test_scene.h`, `painterly/kernel/svm/collect.h` and
   `scene/shader_nodes.h`, plus `<string>` for `describe()`. Its seven cases are named
   `batch 11: the principled bsdf`, `batch 11: the diffuse bsdf`, `batch 11: the glossy bsdf`,
   `batch 11: the glass bsdf`, `batch 11: the refraction bsdf`, `batch 11: the emission node` and
   `batch 11: the transparent bsdf`, so `-tc='batch 11:*'` selects exactly them.
6. `src/test/CMakeLists.txt`: the one `target_sources` line of step 3.
7. `tests/blender/test_sync_shader_node_table.py`, B8's guard test
   (`test_the_table_has_only_the_rows_this_card_adds`, `B8-node-table-export.md:595-598`): its expected set grows from
   eight idnames to fourteen.
   ```
   set(NODE_TABLE) == {"ShaderNodeOutputMaterial", "ShaderNodeOutputWorld", "ShaderNodeEmission",
                       "ShaderNodeTexCoord", "ShaderNodeValue", "ShaderNodeRGB", "ShaderNodeMath",
                       "ShaderNodeVectorMath", "ShaderNodeBsdfPrincipled", "ShaderNodeBsdfDiffuse",
                       "ShaderNodeBsdfAnisotropic", "ShaderNodeBsdfGlass",
                       "ShaderNodeBsdfRefraction", "ShaderNodeBsdfTransparent"}
   ```
   Fourteen idnames and twelve Cycles rows, because B8's two output nodes share one row (`output`) and batch 11's seven
   nodes are six new rows plus B8's `emission`. B8's unknown-node case uses `ShaderNodeBsdfPrincipled`
   (`B8-node-table-export.md:600-602`), which is batch 11's, so it must name a node no batch has: `## Open for Opus` 3
   names the candidates and this card's step uses `ShaderNodeLightPath` (step 1's probe shows bpy 5.2.2 has it and no
   batch of `plan.md:305` names it).
8. `.venv/bin/ruff format` on the two new Python files and the two modified ones, `clang-format -i` on the new C++ file,
   then `.venv/bin/ruff check .`, then every acceptance command.

## Acceptance

Run every command from the repository root; the queue translates them with BACKLOG.md's table (`make check` → `CHECK`,
`make test-blender` → the same target with `KNOBS`, `build/dev` → `build/q`, `.venv/bin/<tool>` →
`MAIN/.venv/bin/<tool>`, any Python command prefixed with `PYTHONPATH="$PWD/analysis"`).
1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and the audit's
   `RESULT: PASS` line. This card adds seven doctest cases and no binding, so the doctest case count grows by exactly
   seven and the exported symbols do not move; the pytest count grows by step 4's four tests.
2. `make audit` prints `RESULT: PASS`: no new exported symbol (no binding, no new production source) and no new
   dependency (no CMake link line changes; the one `target_sources` line adds a source to the existing test target).
3. `build/dev/src/test/painterly_tests -tc='batch 11:*'` prints `test cases: 7 | 7 passed | 0 failed` and the assertion
   count step 5's seven cases give. The count is the number of cases step 5 lists; if it prints another count, the
   card's count is wrong and that is a finding, not a tolerance.
4. `make test-blender` exits 0. Report its last line.
5. `.venv/bin/python -m pytest tests/blender/test_sync_shader_batch_11.py -q` prints `4 passed`: step 4's four tests.
6. `.venv/bin/python -m pytest tests/blender/test_sync_shader_node_table.py -q` prints `6 passed`. The count is B8's
   own (`B8-node-table-export.md:571-603`). This card changes the guard's expected set and the unknown-node case's
   idname (step 7), so the count must not move.
7. `git status --porcelain` lists only the two Create paths and the three Modify paths above.

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- key the Glossy row by `"ShaderNodeBsdfGlossy"` → step 4's idname test fails, `make test-blender` fails B8's guard
  test (the idname is absent), and a scene with a Glossy node falls back to M5's constant mapping with a warning
  (B8's rule 6);
- name `Weight` in a row → step 4's `Weight` test fails, and `export_graph` exports a default Cycles' `NodeType` has no
  socket for, so `add_shader` raises B6's `ValueError` naming it;
- map Principled's `RANDOM_WALK_SKIN` with the plain lowercase rule → step 4's enum test fails (`random_walk_skin`
  against `random_walk_skin` is equal, so this mutation needs a different one: use `enum_name` alone on
  `MULTI_GGX`, which gives `multi_ggx` and is right, so the mutation that fails is to alias `BECKMANN` to `beckman`
  with one `n`, which makes `glass_bsdf`'s compile reject the enum at `add_shader`);
- change one weight in step 5's literals by one float32 ulp → step 3's `describe()` comparison fails and prints both
  lines, which is what makes the literals exact rather than approximate;
- forget step 6 → the seven cases are not compiled and `build/dev/src/test/painterly_tests` has no `batch 11` case, so
  acceptance 3 fails on the count;
- leave B8's unknown-node case on `ShaderNodeBsdfPrincipled` → `make test-blender` fails, because that idname is now in
  `NODE_TABLE` and raises no `PainterlyUnknownNode`.

Report: the doctest case and assertion counts, the pytest counts, the audit line, and every mutation you ran with its
first failing check.

## Commit

`N11: node batch 11: the seven BSDF nodes — six node_table rows and their lobe-list golden tests`

## Open for Opus

1. **The literals encode Opus's closure policy, so a policy change re-derives them.** `T6.7:175-208` is the table these
   seven cases' expected lobe kinds and weights come from, and `T6.7:208` says "The policy is Opus's. Changing it needs
   an Opus decision." This card writes no new rule: it derives each literal from the policy's row for the closure the
   node emits. The alternatives: (a) this card's, one case per node, each literal derived in the case's comment from the
   policy row it uses; (b) the cases call a shared helper that recomputes the expected weight from the policy's formula,
   which makes the policy executable in the test and would silently follow a policy change — weaker, because a wrong
   policy would then pass; (c) the cases live in `src/test/test_cycles_svm_closures.cpp` beside T6.7's, which is a file
   this card's `allowedPaths` would have to include and which T6.5's card says a later card never edits
   (`FACTS.md:143-144`: "A later card that vendors more kernel headers adds its own check file and never edits this
   one"). (a) is what the steps implement; Opus's decision changes step 5's literals and nothing else.
2. **`BRIEF.md:289-290` says the golden test is a lobe list, and B9's harness compares images.** B9's `GOLDEN_SCENES`
   and `golden_rule` (`B9-golden-harness.md:135-177`, `:318-337`) compare a render's pixels; a lobe list is not a pixel
   and no image can show it, which is what `BRIEF.md:289-290` says. So this card's golden tests are C++ doctests in
   `src/test/`, not `tests/blender_it` scenes, and they run in `make check` rather than `make blender-it`. The
   alternatives: (a) this card's; (b) an image test as well, which needs a node material whose lobes painterly can
   render and whose Cycles render is comparable — B4's acceptance 2 already does that for the constant-material
   equivalence (`B4-svm-trace-pixel.md:169-179`), so a second one here would duplicate it; (c) the lobe list is exported
   to Python through a debug binding, which `BRIEF.md:243-244`'s "no debug path" forbids. (a) is what the steps
   implement and what the brief asks for.
3. **B8's unknown-node test loses its node.** `B8-node-table-export.md:600-602` uses `ShaderNodeBsdfPrincipled` as the
   idname `PainterlyUnknownNode` is raised for, and batch 11 gives that node a row. Something must replace it. The
   candidates, each with what it costs: `ShaderNodeBsdfTranslucent`, `ShaderNodeBsdfToon`, `ShaderNodeBsdfSheen`,
   `ShaderNodeSubsurfaceScattering`, `ShaderNodeBsdfHair` and `ShaderNodeHoldout` are Cycles nodes painterly has no row
   for and `FACTS.md:336-337` lists as "not extracted", so they are honest unknowns for v1; `ShaderNodeLightPath` is a
   Cycles node with a `SHADER_SPECIAL_TYPE_LIGHT_PATH` special type (`scene/shader_graph.h:58`) that no batch of
   `plan.md:305` names. The options: (a) this card uses `ShaderNodeLightPath` (step 7), which is stable because no batch
   card can ever give it a row; (b) it uses `ShaderNodeBsdfToon`, which is a node a user can place and which M7 or a
   later milestone might support, so the test would then need changing again; (c) B8's test is rewritten to build its
   unknown node from a name that is not a Blender idname at all, which tests the table rather than a node. (a) is the
   one that never needs revisiting; the idname is one literal in one test, and Opus may prefer (b) for readability.
4. **Four distribution enums, and `ENUM_ALIASES` is keyed by identifier alone.** The five tables of `## Interface` are
   per-row, so the same word in two nodes can map differently and Cycles' four defaults
   (`GlossyBsdfNode.inc:14` `ggx`, `GlassBsdfNode.inc:14` `multi_ggx`, `RefractionBsdfNode.inc:13` `ggx`,
   `PrincipledBsdfNode.inc:9` `multi_ggx`) are each node's own. The alternatives: (a) this card's five tables; (b) eight
   entries in B8's `ENUM_ALIASES` (`B8-node-table-export.md:458-468`), which works today because every identifier's
   Cycles name is its lowercase — `MULTI_GGX` → `multi_ggx` and `RANDOM_WALK_SKIN` → `random_walk_skin` are exactly the
   lowercase rule — so the tables are redundant for these five and would only matter if a node's name diverged from its
   identifier's lowercase; (c) `enum_name` gains a per-idname form, which is B8's signature. Reading step 1's probe
   again: **every** identifier of the five enums lowercases onto its Cycles name, so (b) needs no aliases at all and the
   simplest correct row is `enum_name(node.distribution)` with no table. The tables of `## Interface` are therefore
   written as explicit maps for readability and auditability, and Opus may prefer the plain `enum_name` call; no
   expected value of this card depends on the choice, because step 4's enum test pins the mapping either way.
5. **The seven cases are doctests, so their "golden test" is a C++ assertion, not a scene.** `BRIEF.md:283` says each
   node has "a golden test, which passes B9's rule", and `:289-290` says batch 11's is a lobe list. The two sentences
   cannot both be read literally, and this card reads the second as the exception: the seven cases compare exact
   lobe lists and pass no statistical rule. The alternatives: (a) this card's; (b) B9's rule is extended with a
   lobe-list arm, so a batch card can register a "scene" that yields lobes rather than pixels — a bigger B9, and
   `B9-golden-harness.md` is already drafted; (c) both are done, which doubles the batch. (a) is what the steps
   implement; Opus may want (b) for uniformity across the six batches.
6. **`Parallel-safe: no`, against the plan's row.** `FACTS.md:362` records the plan's row as
   `"Node batch i of 12: <name> (node-table rows and golden tests; parallel-safe)"`, but every batch card edits the same
   literal in B8's guard test (`B8-node-table-export.md:595-598`, this card's step 7) and B8's unknown-node case
   (`:600-602`, `## Open for Opus` 3). The options are batch 1's `## Open for Opus` 3's.
7. **What this card does not decide.** Per `BRIEF.md:295-301`: light node graphs stay out of v1; whether a node
   material's emission is scaled by `emission_scale` is open, and this card passes no knob (decision 8); Bump, Normal
   Map and the Attribute node are out, so no row names a normal *input* that produces a per-lobe normal — the three
   `Normal` sockets are exported and Cycles' own evaluator reads them into the closure, but painterly's lobe list
   carries no normal (decision 7, `BRIEF.md:74`: "Closure normals (Bump, Normal Map) are outside v1: the lobes carry no
   normal"). Metallic, Sheen, Translucent, Toon, Subsurface Scattering, Hair, Ray Portal, Holdout and the volume nodes
   are not extracted (`FACTS.md:336-337`) and get no row, so `PainterlyUnknownNode` reports them; `NODE_CLOSURE_BSDF`
   covers them all if a later milestone extracts the classes.
