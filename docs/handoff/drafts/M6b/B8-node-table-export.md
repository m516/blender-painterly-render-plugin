# B8 — `sync/shader/node_table.py` and `export.py` (drafted from BRIEF.md section 2, "B8")

Milestone: M6b · Depends on: B5, B6, B7 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B8" (lines 221-235), per that brief's section 4 (lines
303-324) and the decisions of its section 1 that touch it: decision 5 (:52-57) is the socket-name rule this card
implements, decision 8 (:75-77) forbids a new knob, and decision 9 (:78-79) makes every expected value below an exact
equality. Code facts are `docs/handoff/drafts/M6b/FACTS.md` §3.11 (the pyi and `python.cpp`), §3.12 (the add-on as it
is), §5 rows R3 and R8, and §6 gaps 2, 6 and 8 — re-read at this clone's HEAD in every file cited below. The bpy facts
are measured on this host with the project's `bpy` 5.2.2 by the probe in step 1, quoted with its output.
`BRIEF.md` gives B8 four scope bullets (:222-232); this card turns each into a numbered rule in `## Goal`, and gives
every rule, its edge cases and the table's machinery an exact expected value.

## Goal

`src/blender/addon/sync/shader/node_table.py` and `export.py` are the two modules that turn Blender's shader node trees
into the lists `Scene.add_shader` takes (B6), and `sync/__init__.py` exports every material and the world through them:

- **Rule 1: the table maps a Blender `bl_idname` to a Cycles type name, with the socket names Cycles uses**
  (BRIEF.md:223). `NODE_TABLE[idname]` gives the Cycles type name (`NodeType::add`'s name, e.g. `emission`), the Cycles
  UI names of its inputs and outputs, and the parameter getter that reads Blender's RNA for that node. The table holds
  rows for the core six batches only (BRIEF.md:223, decision D4 at BRIEF.md:13): a node outside them — a Mix node, a
  Noise texture, a Principled BSDF before batch 11 lands — has no row, and `export_graph` reports it
  (`PainterlyUnknownNode`, rule 6) rather than exporting it approximately.
- **Rule 2: the socket renames are Cycles' own ladder** (BRIEF.md:223, decision 5 at BRIEF.md:52-55): an exact match
  first, then `Shader…` → `Closure…` plus the Mix suffixes, then `_001`/`.001` → `2` and `_002`/`.002` → `3`, else the
  name gets a `1` appended. The outputs have their own ladder: `Shader` → `Closure`, the Mix `Result_*` → `Result`, and
  `FunctionNodeInputVector`'s `Vector` → `Color`. This is `node_find_input_by_name` / `node_find_output_by_name`
  (`intern/cycles/blender/shader.cpp:1212-1281`, `:1283-1323`; report §5 :620-644) transcribed as data.
- **Rule 3: the enum aliases are the four Math operations whose RNA identifier is not their `NodeEnum` name**
  (BRIEF.md:223), plus the identity rule that every other identifier is its own lowercase.
- **Rule 4: `export.py` turns B7's `FlattenedTree` into B6's two lists** (BRIEF.md:227): one
  `(Cycles type name, parameters by member name, linkable input defaults by UI name)` per node, and one
  `(from node, output UI name, to node, input UI name)` per link, with `-1` for the graph's output. A link whose socket
  has no name in the row is dropped, as Cycles drops a link whose endpoint it did not export
  (`shader.cpp:1510-1521`).
- **Rule 5: B8 binds `Scene.set_background_shader(shader: int) -> None`** (BRIEF.md:228-229) over B5's
  `PainterlyScene::set_background_shader`, because the world export is its first caller.
- **Rule 6: the scene sync exports each material and the world; an unsupported node makes that material fall back to
  M5's constant mapping with one warning naming the node** (BRIEF.md:230-232), and `SyncStats` gains
  `warnings: list[str]`.

B8 adds the machinery and exactly three rows: Material Output, Emission and Texture Coordinate (BRIEF.md:224-226). The
batch cards add every other row; batches 6 and 11 give these three their golden tests. Nothing in the core changes
except the one binding, so no image, no K and no parity test moves.

## Read first

- `CLAUDE.md` rules 1, 2 and 3 (scope; named knobs; PEP 8, type hints, docstrings that state units); `AGENTS.md`
  "Expected values are evidence, not targets".
- `docs/handoff/drafts/M6b/BRIEF.md` lines 221-235 (this card's mandate), :52-57 (socket names: node types by Cycles
  type name, links and linkable defaults by UI name, parameters by member name with enums by `NodeEnum` name),
  :75-79 (no new knob; expected values are evidence), :182-196 (B5, the world shader this card binds and feeds) and
  :295-301 (the open questions this card must not decide).
- `docs/handoff/drafts/M6b/FACTS.md` §3.11 (the pyi and `python.cpp` as they are), §3.12 (`sync/` holds only
  `__init__.py` and `reference.py`; M5's `material.py`, `world.py`, `geometry.py` and their `SyncStats` are card text
  only), §5 row R3 ("the Python export implements it (B6, B8)") and R8 (zones), §6 gaps 2, 6 and 8.
- The CONTRACT header `src/blender/_painterly.pyi` (read it, never edit it before dispatch: `:4` is
  `CONTRACT: Opus-owned`): `Scene` `:45`, `add_material` `:49-54`, `set_background` `:111`, `set_integrator` `:124-126`,
  and the dense-index sentence `:7`.
- `src/blender/python.cpp`: the binding this card extends and the helpers it reuses — `bind_module` `:682`,
  `nb::class_<PainterlyScene>` `:694`, `add_material` `:697-720`, `set_background` `:884-888`, `set_integrator`
  `:909-926`, `as_real` `:301`, `as_integer` `:314`, `double3_from_python` `:589`; the anonymous namespace runs
  `:80-997` and `NB_MODULE` is `:1001`.
- `src/blender/addon/sync/__init__.py` (the whole file: the M5 stub `build_scene` `:15-30` that M5 T5.1-T5.3 replace
  and this card's step 11 extends) and `src/blender/addon/session.py:121-139` (the one caller: reference mode or
  `sync.build_scene`, with `NotImplementedError` turned into an `engine.report`).
- `src/blender/addon/sync/reference.py:1-24` (the module docstring: the package is `bpy`-free where it can be) and
  `:86-108` (`material_of`, `build_smallpaint_scene`: the constant materials a fallback reuses).
- `docs/tasks/M5/T5.2-sync-geometry.md:9-17` (`SyncStats`' fields and `object_key`, defined in `sync/geometry.py`) and
  `:48-55` (`build_scene`'s `stats` out-parameter). `docs/tasks/M5/T5.3-sync-lights-world-materials.md:27-42`
  (`sync_world` and `MaterialTable`'s constant mapping, which the fallback calls; the Principled mapping and
  "Anything else → diffuse(0.8 grey), with a one-time warning naming the node" `:41`).
- `docs/handoff/drafts/M6b/B7-flatten.md`: the interface this card consumes — `OUTPUT_NODE: Final = -1` (`:100-101`),
  `PainterlyUnsupportedNode` `:103-107`, `FlatNode`/`FlatLink`/`FlattenedTree` `:109-126`, `flatten_tree` `:129`, and
  its step 8 for the style of a fixture's expected value.
- `docs/handoff/drafts/M6b/B6-shader-graph-api.md` `## Interface` (the two `add_shader`/`add_node_material`
  declarations this card calls) and its `## Open for Opus` 3 (the Python form of a `TRANSFORM` parameter: three or four
  rows of four reals, row-major), 7 (the nine value types) and 8 (why this card is `Parallel-safe: no`).
- The three vendored node definitions whose rows this card writes, each read in full:
  `third_party/cycles/fragments/scene/shader_nodes_cpp/node_define/OutputNode.inc` (`output`, inputs `Surface`,
  `Volume`, `Displacement`, `Normal`, no output), `EmissionNode.inc` (`emission`, inputs `Color` and `Strength` plus
  the two `SVM_INTERNAL` mix weights, output `Emission`) and `TextureCoordinateNode.inc` (`texture_coordinate`, no
  linkable input, parameters `from_dupli`/`use_transform`/`ob_tfm`, outputs `Generated`, `Normal`, `UV`, `Object`,
  `Camera`, `Window`, `Reflection`).
- `third_party/cycles/fragments/scene/shader_nodes_cpp/node_define/MathNode.inc:6-46` (the 41 `type_enum.insert`
  names) and `VectorMathNode.inc:6-40` (the 30), which step 12's alias test compares with bpy's RNA identifiers.
- Upstream `intern/cycles/blender/shader.cpp`, read in the pinned checkout (never edited, not in this repo):
  `add_node` `:356-1201` with no case for `ShaderNodeOutputMaterial` (the only `ShaderNodeOutput*` case is
  `ShaderNodeOutputAOV` `:1180`), `node_find_input_by_name` `:1212-1281`, `node_find_output_by_name` `:1283-1323`,
  `set_default_value` `:223-275`, the output node `:1451-1453`, the unavailable-socket skip `:1461-1478` and the link
  filter `:1490-1522`; `sync_materials`' fallback `:1697-1705` and `sync_world`'s `:1785-1800`.
  `intern/cycles/blender/util.h:351-369` (`get_transform`: Blender's column-major 4x4 → Cycles' three row-major rows).
- `docs/handoff/research/cycles_svm_report.md` §5: the socket-matching ladder `:620-644`, the `idname` → Cycles class
  table `:657-690` (`ShaderNodeTexCoord` at `:1084-1093`, `ShaderNodeEmission`/`BsdfTransparent`/`Background` at
  `:773`, `:755`, `:591`, `ShaderNodeMixShader`/`AddShader` at `:582-584`/`:579-581`), and "Enum strategy for Python"
  `:691-701`.
- `src/blender/_painterly.pyi`'s consumer, `tests/core/test_api_contract.py:65-82` (`_pyi_public_api`, which walks the
  pyi's public names, so the new method is covered without an edit), `:132-158` (the three signature tests) and
  `:168-200` (the effect tests' `_render`, the style this card's sync tests do not need).
- `tests/blender/conftest.py:22` (`ADDON_DIR`), `:32-33` (`HAS_BPY`, `collect_ignore_glob`), `:44-53` (the add-on is
  loaded as the package `painterly` with `submodule_search_locations=[ADDON_DIR]`, so a test imports
  `painterly.sync.shader.node_table`) and `:62-73` (the `addon` fixture).
- `Makefile:73-74` (`test-blender` runs `pytest tests/blender -q` after `build`), `pyproject.toml:38` (`testpaths`),
  `:40` (the `slow` marker) and `:43-44` (`[tool.ruff]` `line-length = 100`, `target-version = "py312"`).
- The bpy facts and the expected values of steps 1, 3, 5 and 10, measured on this host with `bpy` 5.2.2 by the probe
  and the fixture script in step 1.

## Create

- `src/blender/addon/sync/shader/node_table.py`
- `src/blender/addon/sync/shader/export.py`
- `tests/blender/test_sync_shader_node_table.py`
- `tests/blender/test_sync_shader_export.py`
- `tests/blender/test_sync_node_materials.py`

`src/blender/addon/sync/shader/__init__.py` is B7's (`B7-flatten.md` `## Create` `:71`), so this card adds no package
`__init__`.

## Modify

- `src/blender/_painterly.pyi` (CONTRACT, `:4`): `set_background_shader` of `## Interface`, after `set_background`
  (`:111`).
- `src/blender/python.cpp`: the one binding of `## Interface`, after `set_background`'s (`:884-888`).
- `src/blender/addon/sync/geometry.py` (M5 T5.2's file, which creates it): `SyncStats` (`T5.2:9-12`) gains
  `warnings: list[str] = field(default_factory=list)`.
- `src/blender/addon/sync/material.py` (M5 T5.3's file): `MaterialTable` gains the node path of step 9 — its
  constructor takes the stats, `material_index_of` tries `export_material` first, and an unsupported node falls back to
  T5.3's constant mapping with one warning.
- `src/blender/addon/sync/world.py` (M5 T5.3's file): `sync_world(scene_core, scene, stats)` tries the world's node
  graph first (step 10) and falls back to T5.3's constant world with one warning.
- `src/blender/addon/sync/__init__.py`: `build_scene` passes `stats` to `MaterialTable` and `sync_world` (step 11).

## Do not touch

- `src/blender/addon/sync/shader/flatten.py`: B7's module, which this card imports and does not change
  (`B7-flatten.md` `## Modify` is "None").
- `src/blender/addon/sync/shader/__init__.py`: B7's package docstring already names this card's two modules
  (`B7-flatten.md` step 2).
- `src/painterly/**`: `PainterlyScene::set_background_shader` and `KernelPainterlyBackground::cycles_shader` are B5's
  (BRIEF.md:184, :228-229); this card binds and calls them. `src/painterly/kernel/types.h` and
  `src/painterly/kernel/globals.h` are CONTRACTs of B1's and B2's.
- `src/cycles/**`, `third_party/cycles/**`: nothing is vendored here, and `third_party/` is `tools/vendor_sync.py`'s
  alone.
- `tests/blender/test_render_reference.py`: T4.3's test, whose stub-message case (`:290-302`) M5 T5.1's dispatch
  already replaces (ruling R81), so this card changes no expected value there.
- `tests/core/test_api_contract.py`: it must pass unchanged at its own 31 tests, because `_pyi_public_api` (`:65-82`)
  reads the pyi itself and `set_background_shader` has no default (`:151-158` then compares nothing for it).
- `src/blender/addon/session.py`: `build_scene` keeps its signature, so the render loop does not move (T5.1's
  `## Modify` `:53-56`).
- `tests/blender/test_properties.py`, `test_registration.py`, `test_ui_surface.py`, `tests/blender/conftest.py`: T4.2's
  and T4.3's tests and the fixture; the new test files need no conftest change (`:32-33`, `:44-53`).
- `Makefile`, `pyproject.toml`, `src/blender/CMakeLists.txt`: no new target, no new lint setting, no new module source.
  B9 owns the golden harness (BRIEF.md:237-255).
- `NODE_TABLE` beyond this card's three rows: every other row is a batch card's (BRIEF.md:224-226). A batch card adds
  a row and its golden test, and changes no line of `export.py`.

## Interface

CONTRACT (Opus writes this before dispatch): `src/blender/_painterly.pyi`, `class Scene`, after `set_background`
(`:111`), exactly the declaration the brief gives at BRIEF.md:228. The comment below is this draft's proposal for the
sentence Opus owns:

    # The world's node material: `shader` is a `Scene.add_shader` index whose graph is evaluated on a
    # miss instead of the constant radiance (BRIEF.md:182-190). -1 restores `set_background`.
    def set_background_shader(self, shader: int) -> None: ...

Not a CONTRACT: the C++ side is B5's, and this card calls it as B5 writes it (BRIEF.md:184):

    void PainterlyScene::set_background_shader(int shader);   // -1: the constant radiance

`src/blender/addon/sync/shader/node_table.py`, the table and its machinery. B8 imports all of it, the batch cards
import `NodeRow` and add rows, and `export.py` imports the rest:

    from typing import Final, Literal, Mapping

    # One row of the table (BRIEF.md:223): the Cycles type name, the Cycles UI names of the node's
    # linkable inputs and outputs, and the getter for its parameters by member name.
    @dataclass(frozen=True)
    class NodeRow:
        cycles_type: str                                    # NodeType::add's name, e.g. "emission"
        inputs: tuple[str, ...] = ()                        # Cycles UI names, in Cycles' order
        outputs: tuple[str, ...] = ()
        parameters: Callable[[bpy.types.Node], dict[str, object]] | None = None

    NODE_TABLE: Final[Mapping[str, NodeRow]]               # bpy.types.Node.bl_idname -> NodeRow

    # The four Math RNA identifiers whose Cycles NodeEnum name is not their lowercase (step 5).
    ENUM_ALIASES: Final[Mapping[str, str]]

    class PainterlyUnknownNode(Exception):
        """A node this table has no row for (BRIEF.md:230)."""
        def __init__(self, node_name: str, idname: str) -> None: ...
        node_name: str    # the Blender node's name, as bpy.types.Node.name gives it
        idname: str       # its bpy.types.Node.bl_idname

    def cycles_type(idname: str) -> str: ...
    def socket_name(idname: str, identifier: str, side: Literal["in", "out"]) -> str | None: ...
    def enum_name(identifier: str) -> str: ...
    def input_candidates(idname: str, identifier: str) -> tuple[str, ...]: ...
    def output_candidates(idname: str, identifier: str) -> tuple[str, ...]: ...

The block is a declaration, not a runnable file: `dataclass` comes from `dataclasses`, `Callable` from
`collections.abc`, and `bpy` is imported at module level for the hints (as B7's `flatten.py` does,
`B7-flatten.md:131-132`).

`src/blender/addon/sync/shader/export.py`:

    # B6's two lists (BRIEF.md:200-202): one node is (Cycles type name, parameters by member name,
    # linkable input defaults by UI name); one link is (from node, output UI name, to node, input UI
    # name), with to-node -1 for the graph's output.
    NodeSpec = tuple[str, dict[str, object], dict[str, object]]
    LinkSpec = tuple[int, str, int, str]

    def export_graph(tree: FlattenedTree) -> tuple[list[NodeSpec], list[LinkSpec]]: ...
    def export_material(scene_core: Scene, tree: FlattenedTree) -> int: ...
    def export_world(scene_core: Scene, tree: FlattenedTree) -> None: ...

`Scene` is `_painterly.Scene` and `FlattenedTree` is B7's (`B7-flatten.md:122-126`). `export_graph` raises
`PainterlyUnknownNode` for a node with no row and propagates B7's `PainterlyUnsupportedNode` for a zone.
`export_material` is `scene_core.add_node_material(scene_core.add_shader(*export_graph(tree)))` and returns the
material index; `export_world` is `scene_core.set_background_shader(scene_core.add_shader(*export_graph(tree)))`.

`src/blender/addon/sync/geometry.py` (Modify):

    @dataclass class SyncStats:
        ...                                                  # T5.2:10-12, unchanged
        warnings: list[str] = field(default_factory=list)     # BRIEF.md:231-232

`src/blender/addon/sync/material.py` (Modify) and `sync/world.py` (Modify):

    class MaterialTable:
        def __init__(self, scene_core: Scene, stats: SyncStats | None = None) -> None: ...
        def material_index_of(self, material: bpy.types.Material | None) -> int: ...   # T5.3:32

    def sync_world(scene_core: Scene, scene: bpy.types.Scene, stats: SyncStats) -> None: ...   # T5.3:27

`stats=None` keeps a table its own `warnings` list, so a caller of T5.3's one-argument `MaterialTable(scene_core)` still
works; `## Open for Opus` 2 names this choice.

## Steps

1. Preconditions. Each must hold; otherwise stop, commit nothing and report what you saw.
   - B5 landed: this prints `1`.
     ```
     grep -c 'set_background_shader' src/painterly/scene/scene.h
     ```
   - B6 landed: this prints `1` for each.
     ```
     grep -c 'add_shader' src/blender/_painterly.pyi
     grep -c 'add_node_material' src/blender/_painterly.pyi
     ```
   - B7 landed: this prints `1`.
     ```
     grep -c 'def flatten_tree' src/blender/addon/sync/shader/flatten.py
     ```
   - The binding is not there yet: this prints `0`.
     ```
     grep -c 'set_background_shader' src/blender/_painterly.pyi
     ```
   - `bpy` is importable and is 5.2.2: this prints `5.2.2 LTS`.
     ```
     .venv/bin/python -c "import bpy; print(bpy.app.version_string)"
     ```
   - The bpy facts rules 1-4 rest on. Save this probe as a file under `/tmp` and run it with
     `.venv/bin/python <file>`; it must print exactly the lines quoted after it (they are this card's measurement on
     bpy 5.2.2, and the rows, the ladders and the fixtures of steps 2-6 and 12-14 are derived from them):
     ```python
     import bpy
     from mathutils import Matrix

     material = bpy.data.materials.new("probe")
     material.use_nodes = True
     tree = material.node_tree
     tree.nodes.clear()
     output = tree.nodes.new("ShaderNodeOutputMaterial")
     output.name = "output"
     print("material output:", output.bl_idname, output.type, "is_active_output =", output.is_active_output)
     print("material output inputs:",
           [(socket.identifier, socket.type, socket.is_unavailable) for socket in output.inputs])
     second = tree.nodes.new("ShaderNodeOutputMaterial")
     second.name = "second"
     print("a second output:", second.is_active_output,
           "| get_output_node:", tree.get_output_node("CYCLES").name)
     emission = tree.nodes.new("ShaderNodeEmission")
     emission.name = "emit"
     print("emission inputs:",
           [(socket.identifier, socket.type, socket.is_unavailable) for socket in emission.inputs])
     print("emission outputs:", [(socket.identifier, socket.type) for socket in emission.outputs])
     print("emission defaults: Color =", tuple(emission.inputs["Color"].default_value),
           "Strength =", emission.inputs["Strength"].default_value)
     coords = tree.nodes.new("ShaderNodeTexCoord")
     coords.name = "coords"
     print("texcoord inputs:", [socket.identifier for socket in coords.inputs])
     print("texcoord outputs:", [(socket.identifier, socket.type) for socket in coords.outputs])
     print("texcoord RNA properties:",
           sorted(p.identifier for p in coords.bl_rna.properties
                  if not p.is_readonly and p.identifier in ("object", "from_instancer")))
     math = tree.nodes.new("ShaderNodeMath")
     print("math inputs:", [(socket.identifier, socket.is_unavailable) for socket in math.inputs])
     print("math operations: RNA", len(math.bl_rna.properties["operation"].enum_items),
           "| first four:", [item.identifier
                             for item in math.bl_rna.properties["operation"].enum_items][:4])
     mix = tree.nodes.new("ShaderNodeMixShader")
     print("mix shader inputs:", [(socket.identifier, socket.type) for socket in mix.inputs])
     print("mix shader outputs:", [(socket.identifier, socket.type) for socket in mix.outputs])
     add = tree.nodes.new("ShaderNodeAddShader")
     print("add shader inputs:", [(socket.identifier, socket.type) for socket in add.inputs])
     plain = bpy.data.materials.new("plain")
     plain.use_nodes = False
     print("a material with use_nodes False still has a node tree:",
           plain.node_tree is not None, "| nodes:", len(plain.node_tree.nodes))

     marker = bpy.data.objects.new("marker", None)
     bpy.context.scene.collection.objects.link(marker)
     marker.matrix_world = Matrix.Translation((1.0, 2.0, 3.0))
     coords.object = marker
     print("texcoord.object:", coords.object.name,
           "| matrix_world rows:", [tuple(row) for row in coords.object.matrix_world])

     world = bpy.data.worlds.new("evening")
     world.use_nodes = True
     world_tree = world.node_tree
     world_tree.nodes.clear()
     world_output = world_tree.nodes.new("ShaderNodeOutputWorld")
     world_output.name = "output"
     background = world_tree.nodes.new("ShaderNodeBackground")
     background.name = "background"
     print("world output:", world_output.bl_idname, world_output.type,
           [(socket.identifier, socket.type) for socket in world_output.inputs])
     print("background inputs:", [(socket.identifier, socket.type, socket.is_unavailable)
                                  for socket in background.inputs])
     print("background defaults: Color =", tuple(background.inputs["Color"].default_value),
           "Strength =", background.inputs["Strength"].default_value)
     print("get_output_node CYCLES, world:", world_tree.get_output_node("CYCLES").name)

     bpy.data.libraries.write("/tmp/b8_probe.blend", {material, marker, world})
     with bpy.data.libraries.load("/tmp/b8_probe.blend") as (source, target):
         target.materials = source.materials
         target.objects = source.objects
         target.worlds = source.worlds
     loaded = target.materials[0]
     print("reloaded:", [(node.bl_idname, node.name) for node in loaded.node_tree.nodes])
     print("reloaded get_output_node:", loaded.node_tree.get_output_node("CYCLES").name,
           "| is_active_output =", loaded.node_tree.get_output_node("CYCLES").is_active_output)
     print("reloaded emission inputs:",
           [(socket.identifier, socket.is_unavailable)
            for socket in loaded.node_tree.nodes["emit"].inputs])
     ```
     ```
     material output: ShaderNodeOutputMaterial OUTPUT_MATERIAL is_active_output = True
     material output inputs: [('Surface', 'SHADER', False), ('Volume', 'SHADER', False), ('Displacement', 'VECTOR', False), ('Thickness', 'VALUE', False)]
     a second output: False | get_output_node: output
     emission inputs: [('Color', 'RGBA', False), ('Strength', 'VALUE', False), ('Weight', 'VALUE', True)]
     emission outputs: [('Emission', 'SHADER')]
     emission defaults: Color = (1.0, 1.0, 1.0, 1.0) Strength = 1.0
     texcoord inputs: []
     texcoord outputs: [('Generated', 'VECTOR'), ('Normal', 'VECTOR'), ('UV', 'VECTOR'), ('Object', 'VECTOR'), ('Camera', 'VECTOR'), ('Window', 'VECTOR'), ('Reflection', 'VECTOR')]
     texcoord RNA properties: ['from_instancer', 'object']
     math inputs: [('Value', False), ('Value_001', False), ('Value_002', True)]
     math operations: RNA 41 | first four: ['ADD', 'SUBTRACT', 'MULTIPLY', 'DIVIDE']
     mix shader inputs: [('Fac', 'VALUE'), ('Shader', 'SHADER'), ('Shader_001', 'SHADER')]
     mix shader outputs: [('Shader', 'SHADER')]
     add shader inputs: [('Shader', 'SHADER'), ('Shader_001', 'SHADER')]
     a material with use_nodes False still has a node tree: True | nodes: 2
     texcoord.object: marker | matrix_world rows: [(1.0, 0.0, 0.0, 1.0), (0.0, 1.0, 0.0, 2.0), (0.0, 0.0, 1.0, 3.0), (0.0, 0.0, 0.0, 1.0)]
     world output: ShaderNodeOutputWorld OUTPUT_WORLD [('Surface', 'SHADER'), ('Volume', 'SHADER')]
     background inputs: [('Color', 'RGBA', False), ('Strength', 'VALUE', False), ('Weight', 'VALUE', True)]
     background defaults: Color = (0.800000011920929, 0.800000011920929, 0.800000011920929, 1.0) Strength = 1.0
     get_output_node CYCLES, world: output
     reloaded: [('ShaderNodeOutputMaterial', 'output'), ('ShaderNodeOutputMaterial', 'second'), ('ShaderNodeEmission', 'emit'), ('ShaderNodeTexCoord', 'coords'), ('ShaderNodeMath', 'Math'), ('ShaderNodeMixShader', 'Mix Shader'), ('ShaderNodeAddShader', 'Add Shader')]
     reloaded get_output_node: output | is_active_output = True
     reloaded emission inputs: [('Color', False), ('Strength', False), ('Weight', True)]
     ```
     (bpy prints two `DeprecationWarning`s about `use_nodes` on stderr; they are not part of the output above.)
     What each line fixes:
     - `Emission`'s `Weight` and `Background`'s `Weight` are `is_unavailable`, so they are neither exported as defaults
       nor named by a row: Cycles' own `emission` row has `Color` and `Strength` and two `SVM_INTERNAL` mix weights,
       and no `Weight` (`EmissionNode.inc:5-8`). `add_nodes_inlined` skips an unavailable socket
       (`shader.cpp:1461-1464`), which is why step 6's default export skips them.
     - `ShaderNodeOutputMaterial` has a `Thickness` input that Cycles' `output` row does not name
       (`OutputNode.inc:5-8`), so a link into it has no Cycles name and is dropped (step 13, fixture E2).
     - A material's `use_nodes = False` still leaves a node tree with two nodes (Principled and Material Output), so
       `build_scene` needs no `node_tree is None` branch; a world's likewise.
     - `ShaderNodeTexCoord`'s bpy properties are `from_instancer` and `object`: there is no `custom1`, so the row's
       `from_dupli` parameter reads `node.from_instancer`, and `use_transform`/`ob_tfm` come from `node.object`
       (`shader.cpp:1084-1093`).
     - A reloaded `.blend` keeps every `identifier`, the `is_unavailable` flag and `get_output_node`, so the tests of
       step 13 can build a tree, write it, load it and still compare exact strings.
2. `src/blender/addon/sync/shader/node_table.py`, the three rows. Each row is the vendored definition transcribed:
   `cycles_type` is `NodeType::add`'s first argument, `inputs` and `outputs` are the `SOCKET_IN_*`/`SOCKET_OUT_*` UI
   names in file order, and the parameters are the `SOCKET_*` (non-`IN`/`OUT`) members a caller must set:
   ```python
   NODE_TABLE: Final[Mapping[str, NodeRow]] = {
       # third_party/cycles/fragments/.../OutputNode.inc:3-8. Both Blender output nodes are Cycles'
       # one graph output (BRIEF.md:224, shader.cpp:1451-1453).
       "ShaderNodeOutputMaterial": NodeRow("output", ("Surface", "Volume", "Displacement", "Normal")),
       "ShaderNodeOutputWorld": NodeRow("output", ("Surface", "Volume", "Displacement", "Normal")),
       # EmissionNode.inc:3-10. The two mix weights are SVM_INTERNAL, set by the compiler, not by a caller.
       "ShaderNodeEmission": NodeRow("emission", ("Color", "Strength"), ("Emission",)),
       # TextureCoordinateNode.inc:3-15. from_dupli, use_transform and ob_tfm are parameters: the node
       # has no linkable input.
       "ShaderNodeTexCoord": NodeRow(
           "texture_coordinate", (), ("Generated", "Normal", "UV", "Object", "Camera", "Window",
                                      "Reflection"), _texture_coordinate_parameters),
   }
   ```
   - `_texture_coordinate_parameters(node)` returns `{"from_dupli": node.from_instancer}` and, when
     `node.object is not None`, also `{"use_transform": True, "ob_tfm": <the 4x4>}` — the two lines
     `shader.cpp:1087-1091` writes. `<the 4x4>` is `tuple(tuple(float(value) for value in row) for row in
     node.object.matrix_world)`, i.e. four rows of four reals in the form B6's `TRANSFORM` parameter takes
     (`B6-shader-graph-api.md` `## Open for Opus` 3), because `get_transform` (`blender/util.h:351-369`) reads the same
     twelve numbers from Blender's column-major matrix. `matrix_world`'s last row is `(0, 0, 0, 1)` for an object
     without a parent (step 1's probe), and `get_transform` ignores it.
   - `NodeRow` is a `dataclass(frozen=True)` with `parameters: Callable[[bpy.types.Node], dict[str, object]] | None
     = None`. `NODE_TABLE` is a `Mapping` so a batch card's row is one entry in a literal, never a mutation.
   - `cycles_type(idname)` returns `NODE_TABLE[idname].cycles_type` and raises `PainterlyUnknownNode(idname, idname)`
     for an idname with no row; it is the one name a caller needs without a row in hand, and `export_graph` does not
     use it (it already has the row).
   - The docstring states rule 1, the file each row comes from, and that a row's `cycles_type` is a Cycles type name,
     not a Blender idname (decision 5, BRIEF.md:52-55).
3. `node_table.py`, the socket ladders (rule 2). `input_candidates(idname, identifier)` returns the names Cycles tries,
   in order, and it is the same ladder as `node_find_input_by_name` (`shader.cpp:1212-1281`): the identifier itself;
   then `Closure…` for an identifier that starts with `Shader`; then, for `ShaderNodeMix` only, `Factor_Float` and
   `Factor_Vector` → `Factor` and `A_Float`/`B_Float`/`A_Color`/`B_Color`/`A_Vector`/`B_Vector` → `A`/`B`; then
   `_001`/`.001` → `2` and `_002`/`.002` → `3`, else the name gets `1` appended. The later steps rename the name the
   earlier ones produced, which is what Cycles' sequential `string_replace` does — the difference is visible: `A_Color`
   ends as `A1`, not `A_Color1`. `output_candidates(idname, identifier)` is the shorter output ladder
   (`shader.cpp:1283-1323`): the identifier; `Shader` → `Closure`; the `ShaderNodeMix` `Result_Float`/`Result_Color`/
   `Result_Vector` → `Result`; `FunctionNodeInputVector`'s `Vector` → `Color`. Both are pure functions of the idname
   and the identifier, and they return a `tuple`, so a caller may log the whole ladder.
   Measured (this card's prototype, `bpy` 5.2.2; the same table is step 12's expected value):
   ```
   in  ShaderNodeMixShader Shader       ('Shader', 'Closure', 'Closure1')
   in  ShaderNodeMixShader Shader_001   ('Shader_001', 'Closure_001', 'Closure2')
   in  ShaderNodeMath      Value        ('Value', 'Value1')
   in  ShaderNodeMath      Value_001    ('Value_001', 'Value2')
   in  ShaderNodeMath      Value_002    ('Value_002', 'Value3')
   in  ShaderNodeMix       A_Color      ('A_Color', 'A', 'A1')
   in  ShaderNodeMix       Factor_Float ('Factor_Float', 'Factor', 'Factor1')
   in  ShaderNodeTexImage  Vector       ('Vector', 'Vector1')
   in  ShaderNodeOutputMaterial Surface ('Surface', 'Surface1')
   out ShaderNodeMixShader Shader       ('Shader', 'Closure')
   out ShaderNodeMix       Result_Color ('Result_Color', 'Result')
   out ShaderNodeMix       Result_Float ('Result_Float', 'Result')
   out ShaderNodeMix       Result_Vector('Result_Vector', 'Result')
   out FunctionNodeInputVector Vector   ('Vector', 'Color')
   out ShaderNodeMath      Value        ('Value',)
   ```
   The lines whose last step is the appended `1` are the ones a wrong implementation gets wrong: a `Mix` `A_Color` is
   `A` in Cycles and only falls through to `A1` when the row has no `A` (`MixColorNode`'s row will have one, so batch 2
   will shorten that ladder), and an output ladder has no `1` step at all — `ShaderNodeMath`'s `Value` output is
   `('Value',)` while its input of the same identifier is `('Value', 'Value1')`.
   `socket_name(idname, identifier, side)` returns the first candidate the row names, and `None` when none is:
   an identifier with no Cycles name is a dropped link or a dropped default, not an error. Both functions raise
   `PainterlyUnknownNode(idname, idname)` for an idname with no row — they have no node name, so `node_name` is the
   idname — while `export_graph` (step 6) passes the real `node.name`.
4. `node_table.py`, the enum aliases (rule 3). `enum_name(identifier)` is `ENUM_ALIASES.get(identifier,
   identifier.lower())`, with exactly four entries:
   ```python
   # The Math operations whose bpy RNA identifier is not their NodeEnum name (MathNode.inc:6-46 against
   # bpy 5.2.2's 41 identifiers; step 12's test pins both sides).
   ENUM_ALIASES: Final[Mapping[str, str]] = {
       "FRACT": "fraction",
       "INVERSE_SQRT": "inversesqrt",
       "SMOOTH_MAX": "smoothmax",
       "SMOOTH_MIN": "smoothmin",
   }
   ```
   No row of this card has an enum parameter, so no test of steps 2-4 calls `enum_name` on a row's value: the table
   exists for the batch cards (batch 1's Math and Vector Math are its first users), and step 12's enum test is what
   keeps it honest. The report's warning "Do not pass lowercased RNA strings to Cycles `NodeEnum`"
   (`cycles_svm_report.md:697-698`) holds for the families it names (image extension `REPEAT` against
   `periodic`/`clamp`/`black`/`mirror`); for the 71 Math and Vector Math operations the lowercase rule plus these four
   aliases maps every identifier, measured in step 5.
5. `node_table.py`, the enum guard's measurement, which step 12's enum test pins. This script reads the two vendored
   definitions and bpy's RNA and prints one line per node; it must print exactly these two lines (measured on bpy
   5.2.2; save it under `/tmp` and run it with `.venv/bin/python <file>`):
   ```
   ShaderNodeMath: RNA 41, NodeEnum 41, lowercase alone 37, aliases ['FRACT', 'INVERSE_SQRT', 'SMOOTH_MAX', 'SMOOTH_MIN'], unmapped [], unused []
   ShaderNodeVectorMath: RNA 30, NodeEnum 30, lowercase alone 30, aliases [], unmapped [], unused []
   ```
   So `ENUM_ALIASES` is exactly the four operations the lowercase rule misses, and `ShaderNodeVectorMath` needs no
   entry: the alias table cannot grow without a measurement that shows it must.
6. `src/blender/addon/sync/shader/export.py`, `export_graph` (rule 4). Input is B7's `FlattenedTree`
   (`B7-flatten.md:122-126`). For each `FlatNode` in order:
   - `row = NODE_TABLE.get(node.idname)`; `None` raises `PainterlyUnknownNode(node.name, node.idname)` — the
     message is `f"{node_name}: the node type {idname} is not in the node table"`, and `node_name`/`idname` are
     attributes (BRIEF.md:230-231 needs the name).
   - `row.cycles_type == "output"` → the node is not exported and its links are dropped. Cycles' `add_node` has no case
     for `ShaderNodeOutputMaterial` (the only `ShaderNodeOutput*` case is `ShaderNodeOutputAOV`,
     `shader.cpp:1180`), and `add_nodes_inlined` maps only *the* output node to `graph->output()`
     (`:1451-1453`); every other node gets `nullptr` from `add_node` (`:1196-1200`), and `:1510-1521` then drops its
     links ("either socket may be nullptr when the node was not exported"). A second output node is therefore not an
     error and not a node — fixture E6.
   - `parameters = {} if row.parameters is None else dict(row.parameters(node.node))`.
   - `defaults`: for each `socket` of `node.node.inputs`, skip it when `socket.is_unavailable` or `socket.is_linked`
     or `socket.type == "SHADER"` (`shader.cpp:1461-1464`; a closure has no value form, `B6-shader-graph-api.md`
     step 1), then `socket_name(row, node.idname, socket.identifier, "in")`; `None` → skip, else
     `defaults[name] = _default_of(socket)`. `_default_of` is Cycles' `set_default_value` (`shader.cpp:223-275`) as
     values: `VALUE` → `float`, `INT` → `int`, `BOOLEAN` → `bool`, `RGBA`/`VECTOR` → the first three floats as a
     3-tuple, `STRING` → `str`, anything else → `None` (skipped). A boolean becomes Cycles' `0`/`1` `INT`, which the
     `int` branch already gives, because B6's `BOOLEAN` and `INT` are one socket type.
   - Append `(row.cycles_type, parameters, defaults)` and record `index → len(nodes) - 1`, so a skipped node does not
     shift the exported indices.
   For each `FlatLink` in order: skip it when the from-node was not exported; resolve `from_name` with the from row's
   output ladder; for `to_node == OUTPUT_NODE` (`-1`, B7's `OUTPUT_NODE`) resolve `to_name` with the tree's
   `output_idname` row's input ladder and keep `-1`; for an exported to-node resolve with its row and its new index;
   for a skipped to-node drop the link. Append `(new_from, from_name, new_to, to_name)` when both names resolved.
   - The order of the returned lists is the flattened order, so the expected values below pin it.
   - `export_material` and `export_world` are the two three-line calls of `## Interface`; `export_material` returns
     `add_node_material`'s index, and `export_world` returns `None`.
7. `src/blender/_painterly.pyi` and `src/blender/python.cpp`, the world's binding (rule 5). In the pyi, the declaration
   of `## Interface` after `set_background` (`:111`) and no other line. In `python.cpp`, after `set_background`'s
   `.def` (`:884-888`):
   ```cpp
   .def(
       "set_background_shader",
       [](PainterlyScene &self, const int shader) { self.set_background_shader(shader); },
       nb::arg("shader"))
   ```
   `nb::object` is not needed: an `int` parameter converts as `add_material`'s and `add_node_material`'s do, and
   `set_background_shader` takes no default, so `test_api_contract.py:151-158` compares nothing for it. The lambda is
   inside `bind_module`'s anonymous namespace (`:80-997`), so the module exports no new symbol
   (`exports.map:1` still exports `PyInit__painterly` alone) and links no new library.
8. `src/blender/addon/sync/geometry.py`, `SyncStats.warnings` (rule 6): one field,
   `warnings: list[str] = field(default_factory=list)`, with the comment `# one entry per fallback (BRIEF.md:230-232)`.
   `dataclasses.field` is already imported by T5.2's `object_ids`.
9. `src/blender/addon/sync/material.py`, the node path (rule 6, first half). `MaterialTable.__init__(scene_core,
   stats=None)` keeps `self.stats` and, for `stats is None`, its own `self.warnings: list[str] = []`;
   `_warn(message)` appends to `self.stats.warnings` when there is a stats and to `self.warnings` otherwise.
   `material_index_of(material)` keeps T5.3's cache and adds one step before the constant mapping:
   - `tree = None if material is None else material.node_tree`; when `tree is None` or
     `tree.get_output_node("CYCLES")` is `None`, the constant mapping runs unchanged (T5.3:33-42).
   - otherwise `try: index = export_material(self.scene_core, flatten_tree(tree))` and cache it. Two exceptions are
     the fallback: B7's `PainterlyUnsupportedNode` (a zone, `B7-flatten.md:103-107`) and this card's
     `PainterlyUnknownNode` (no row). `except (PainterlyUnsupportedNode, PainterlyUnknownNode) as error: self._warn(
     f"{error}; {material.name} uses the constant mapping")` and then T5.3's constant mapping, cached the same way.
     Any other exception — B6's `ValueError` for a name Cycles does not have, say — is a defect in this card's table
     or in B6, not an unsupported node, and propagates rather than becoming a silent grey material.
   - one warning per material: the cache stores the fallback's index too, so a second `material_index_of` for the same
     material emits nothing (fixture E13).
   The two messages, each `f"{error}; {material.name} uses the constant mapping"` (measured from the two exception
   types; step 14's E12 and E14 pin them):
   ```
   'principled: the node type ShaderNodeBsdfPrincipled is not in the node table; principled material uses the constant mapping'
   'zone: the closure zone is not supported; zone material uses the constant mapping'
   ```
   The second string is B7's `PainterlyUnsupportedNode` message (`B7-flatten.md:294-295`) followed by this card's
   suffix, so the warning names the node either way (BRIEF.md:230-231). The suffix comes after the exception's
   message, not before, so a caller that matches on B7's text still finds it.
10. `src/blender/addon/sync/world.py`, the world's node path (rule 6, second half).
    `sync_world(scene_core, scene, stats)` keeps T5.3's body and gains one step before it:
    - `world = scene.world`; when it is `None`, `world.node_tree` is `None`, or
      `world.node_tree.get_output_node("CYCLES")` is `None`, T5.3's constant world runs unchanged (`world.color`, or a
      Background node's `color·strength`, T5.3:28-31).
    - otherwise `try: export_world(scene_core, flatten_tree(world.node_tree)); return` and, on the same two
      exceptions, `stats.warnings.append(f"{error}; {world.name} uses world.color")` and T5.3's constant world. A
      third exception propagates, as in step 9.
      Measured message for a Background world (`ShaderNodeBackground` is batch 12's row, `BRIEF.md:291`):
      ```
      'background: the node type ShaderNodeBackground is not in the node table; evening uses world.color'
      ```
      The `world.color` T5.3 falls back to is Blender's `(0.05000000074505806, 0.05000000074505806,
      0.05000000074505806)` for a new world (step 1's probe), so the fallback's radiance is not the node's colour: this
      card states that in the warning rather than pretending the two agree.
11. `src/blender/addon/sync/__init__.py`: `build_scene` passes `stats` to the two M5 entry points — the
    `MaterialTable(scene_core, stats)` construction and `sync_world(scene_core, scene, stats)` — and nothing else
    changes; the calls' order stays T5.2's and T5.3's (`sync_camera`, `sync_geometry`, `sync_lights`, `sync_world`).
    `session.py` is unchanged (T5.1's `## Modify` `:53-56`).
12. `tests/blender/test_sync_shader_node_table.py`, six tests. The table and the two ladders are pure data, so only
    the enum test needs `bpy` (for `bl_rna`'s `enum_items`); no test writes a `.blend`, and every expected value is a
    literal compared with exact equality, so no tolerance appears anywhere.
    - `test_the_rows_are_the_vendored_node_definitions`: parse the three `.inc` files with
      `SOCKET_IN_[A-Z0-9_]+\(\s*\w+\s*,\s*"([^"]+)"([^;]*);` (and the `SOCKET_OUT_` form) and
      `NodeType::add\("([a-z_]+)"`, and compare each with the row. Expected (measured: the row-vs-file check of this
      card's prototype):
      ```
      ShaderNodeOutputMaterial: 'output', inputs=['Surface', 'Volume', 'Displacement', 'Normal'], outputs=[]
      ShaderNodeOutputWorld: 'output', inputs=['Surface', 'Volume', 'Displacement', 'Normal'], outputs=[]
      ShaderNodeEmission: 'emission', inputs=['Color', 'Strength'], outputs=['Emission']
      ShaderNodeTexCoord: 'texture_coordinate', inputs=[], outputs=['Generated', 'Normal', 'UV', 'Object', 'Camera', 'Window', 'Reflection']
      ```
      The unfiltered file lists are longer: `EmissionNode.inc:7-8` also declares `SurfaceMixWeight` and
      `VolumeMixWeight` with `SocketType::SVM_INTERNAL`, which the compiler sets and no caller does, and which
      `add_nodes_inlined` never exports because Blender has no such socket. The test asserts both lists — the
      unfiltered one is `['Color', 'Strength', 'SurfaceMixWeight', 'VolumeMixWeight']` for `Emission` and `['Emission']`
      for its output — so a vendored definition that gains or loses a socket fails here instead of silently changing
      what a caller may link.
    - `test_the_input_socket_ladder_is_cycles_own` and `test_the_output_socket_ladder_is_cycles_own`: the two
      measured tables of step 3, compared as tuples against `input_candidates`/`output_candidates`.
    - `test_the_math_enum_aliases_cover_every_rna_identifier`: step 5's two measured lines, plus
      `ENUM_ALIASES == {"FRACT": "fraction", "INVERSE_SQRT": "inversesqrt", "SMOOTH_MAX": "smoothmax",
      "SMOOTH_MIN": "smoothmin"}` and `enum_name("ADD") == "add"`.
    - `test_the_table_has_only_the_rows_this_card_adds`: `set(NODE_TABLE) == {"ShaderNodeOutputMaterial",
      "ShaderNodeOutputWorld", "ShaderNodeEmission", "ShaderNodeTexCoord"}` — four idnames, three Cycles rows, because
      the two output nodes share one row (BRIEF.md:224-226). A batch card that adds a row must change this test, which
      is the guard that no row arrives without its golden test.
    - `test_an_unknown_idname_raises_with_its_name`: `cycles_type("ShaderNodeBsdfPrincipled")` and
      `socket_name("ShaderNodeBsdfPrincipled", "BSDF", "out")` each raise `PainterlyUnknownNode` whose `str` is
      `"ShaderNodeBsdfPrincipled: the node type ShaderNodeBsdfPrincipled is not in the node table"` and whose
      `node_name` and `idname` are both the idname; `socket_name("ShaderNodeEmission", "Weight", "in")` returns `None`
      (an identifier the row does not name is a dropped default, not an error).
13. `tests/blender/test_sync_shader_export.py`, ten tests, in the style of B7's step 8: each builds a tree, writes it
    to `tmp_path` with `bpy.data.libraries.write`, loads it back with `bpy.data.libraries.load`, and compares
    `export_graph(flatten_tree(tree))` with a literal. The round trip is part of the fixture because a reloaded `.blend`
    keeps every `identifier` (step 1's probe), and it is what makes the expected values a `.blend`'s rather than a
    live session's (BRIEF.md:233). Every expected value below was produced by running an implementation of steps 2-6
    against bpy 5.2.2 in this card's own scratch prototype (`## Open for Opus` 1).
    - E1 `test_the_emission_plane_exports_its_two_nodes_and_two_links`. Fixture: `ShaderNodeOutputMaterial` `output`,
      `ShaderNodeTexCoord` `coords`, `ShaderNodeEmission` `emit`; `coords.Generated → emit.Color`,
      `emit.Emission → output.Surface`. Expected:
      ```
      ([('texture_coordinate', {'from_dupli': False}, {}),
        ('emission', {}, {'Strength': 1.0})],
       [(0, 'Generated', 1, 'Color'), (1, 'Emission', -1, 'Surface')])
      ```
      `output` is not a node, `Generated` is a linkable input so its default is not exported, and `Strength`'s
      unlinked default is Blender's `1.0` (step 1's probe), where Cycles' own default is `10.0`
      (`EmissionNode.inc:6`): the export carries Blender's value, which is what the material means.
    - E2 `test_a_link_into_an_input_the_row_does_not_name_is_dropped`. Fixture: E1 plus
      `coords.Object → output.Thickness`. Expected: E1's value, unchanged — `Thickness` is a Blender socket that
      Cycles' `output` row does not name (`OutputNode.inc:5-8`), so the link has no Cycles name and
      `shader.cpp:1510-1521` drops it.
    - E3 `test_a_texture_coordinate_object_sets_use_transform_and_ob_tfm`. Fixture: E1, and a `bpy.data.objects.new(
      "marker", None)` at `matrix_world = Matrix.Translation((1.0, 2.0, 3.0))` assigned to `coords.object`, written and
      reloaded with the material. Expected node 0:
      ```
      ('texture_coordinate',
       {'from_dupli': False, 'use_transform': True,
        'ob_tfm': ((1.0, 0.0, 0.0, 1.0), (0.0, 1.0, 0.0, 2.0),
                   (0.0, 0.0, 1.0, 3.0), (0.0, 0.0, 0.0, 1.0))},
       {})
      ```
      The fixture links the reloaded object into `bpy.context.scene.collection` and calls
      `bpy.context.view_layer.update()` before exporting: without the update a reloaded object's `matrix_world` reads
      the identity (measured: `[(1.0, 0.0, 0.0, 0.0), …, (0.0, 0.0, 0.0, 1.0)]`), which would make the test pass on a
      wrong matrix.
    - E4 `test_the_world_output_is_the_graph_output`. Fixture: `bpy.data.worlds.new("emission world")`, a
      `ShaderNodeOutputWorld` `output`, a `ShaderNodeEmission` `emit` with `Color = (0.25, 0.5, 0.75, 1.0)` and
      `Strength = 2.0`, and `emit.Emission → output.Surface`. Expected:
      ```
      ([('emission', {}, {'Color': (0.25, 0.5, 0.75), 'Strength': 2.0})],
       [(0, 'Emission', -1, 'Surface')])
      ```
      and `flatten_tree(...).output_idname == "ShaderNodeOutputWorld"`, which is how `export_graph` names the graph's
      output for a world (`B7-flatten.md:126`). The RGBA socket's four floats become three (step 6's `_default_of`).
    - E5 `test_an_unknown_node_raises_with_its_name`. Fixture: `output`, a `ShaderNodeBsdfPrincipled` `principled`,
      `principled.BSDF → output.Surface`. Expected: `PainterlyUnknownNode` with
      `str(error) == "principled: the node type ShaderNodeBsdfPrincipled is not in the node table"`,
      `error.node_name == "principled"` and `error.idname == "ShaderNodeBsdfPrincipled"`. Principled is batch 11's row
      (BRIEF.md:289-290), so this is the state of the table until that card lands.
    - E6 `test_a_second_output_node_is_not_exported`. Fixture: E1 plus a second `ShaderNodeOutputMaterial` `second` and
      `emit.Emission → second.Surface`. Expected: E1's value, unchanged. `flatten_tree` does keep `second` (B7 skips
      only the tree's `get_output_node("CYCLES")`), so this test pins `export_graph`'s own rule and its two dropped
      links.
    - E7 `test_the_background_node_has_no_row_in_this_card`. Fixture: a world with `ShaderNodeOutputWorld` `output`, a
      `ShaderNodeBackground` `background` and `background.Background → output.Surface`. Expected:
      `PainterlyUnknownNode` with `str(error) == "background: the node type ShaderNodeBackground is not in the node
      table"`. Batch 12 adds the row (BRIEF.md:291), and this test is what that card must change.
    - E8 `test_an_empty_tree_exports_no_nodes`. Fixture: a tree whose only node is the `ShaderNodeOutputMaterial`
      `output`. Expected: `([], [])`.
    - E9 `test_unlinked_inputs_export_their_defaults`. Fixture: `output` and a `ShaderNodeEmission` `emit` with nothing
      linked. Expected:
      ```
      ([('emission', {}, {'Color': (1.0, 1.0, 1.0), 'Strength': 1.0})], [(0, 'Emission', -1, 'Surface')])
      ```
      Blender's `Color` default is white (`(1.0, 1.0, 1.0, 1.0)`, step 1's probe) and Cycles' is `0.8` grey
      (`EmissionNode.inc:5`): the test pins Blender's, which is what a Blender material means.
    - E10 `test_a_link_into_volume_survives`. Fixture: `output`, `emit`, `emit.Emission → output.Volume`. Expected:
      ```
      ([('emission', {}, {'Color': (1.0, 1.0, 1.0), 'Strength': 1.0})], [(0, 'Emission', -1, 'Volume')])
      ```
      `Volume` is in the `output` row (`OutputNode.inc:6`), so the link keeps its name and its `-1` to-node; that the
      volume path is not evaluated in v1 is B4's and B5's business, not the export's.
14. `tests/blender/test_sync_node_materials.py`, six tests, each passing a recording fake `scene_core` that logs every
    call and its arguments (`_painterly.Scene` has no getters, so T5.3's tests use the same device,
    `docs/tasks/M5/T5.3-sync-lights-world-materials.md:51`), and a `SyncStats()` from `sync.geometry`.
    - E11 `test_a_material_with_a_supported_graph_becomes_a_node_material`: E1's material through
      `MaterialTable(fake, stats).material_index_of(material)`. Expected: the fake's calls are
      `add_shader(nodes, links)` with E1's two lists, then `add_node_material(0)`, and the return is `0`.
    - E12 `test_an_unsupported_material_falls_back_to_the_constant_mapping_with_one_warning`: E5's material.
      Expected: the fake's call log has no `add_shader` and no `add_node_material`, exactly one `add_material`, and that
      call's arguments are **exactly** the ones a second table gives for the same material with the node path disabled
      (`monkeypatch.setattr(material_module, "export_material", _raise_unknown)`), i.e. the fallback is T5.3's constant
      mapping and this card adds no value of its own. Plus
      `stats.warnings == ["principled: the node type ShaderNodeBsdfPrincipled is not in the node table; principled
      material uses the constant mapping"]`.
      Why the comparison rather than a literal: T5.3's Principled mapping reads the node's *unlinked* inputs
      (`docs/tasks/M5/T5.3-sync-lights-world-materials.md:35-38`), so its answer is a float32 Blender default —
      `Base Color` reads `0.800000011920929`, not `0.8` (measured on bpy 5.2.2:
      `bpy.data.materials.new("p").node_tree.nodes.new("ShaderNodeBsdfPrincipled").inputs["Base Color"].default_value`)
      — and M5's implementation, not this card, decides whether the mapping's `0.8` literal or that float32 is used.
      Pinning either would move an expected value T5.3 owns (`AGENTS.md`, "Expected values are evidence").
    - E13 `test_the_warning_is_emitted_once_per_material`: two `material_index_of` calls for E12's material return the
      same index, leave one warning, and leave one `add_material` call — the cache holds the fallback too.
    - E14 `test_a_zone_in_a_material_tree_falls_back_with_the_zones_message`: a material whose tree holds `output` and
      a `NodeClosureInput` `zone`. Expected: E12's comparison against the constant path, and
      `stats.warnings == ["zone: the closure zone is not supported; zone material uses the constant mapping"]` —
      B7's message (`B7-flatten.md:294-295`) with this card's suffix. `NodeClosureInput` is one of the 8 zone node
      types bpy 5.2.2 registers in a shader tree (`B7-flatten.md` step 1's probe).
    - E15 `test_a_world_with_a_supported_graph_sets_the_background_shader`: E4's world through
      `sync_world(fake, scene, stats)`. Expected: `set_background_shader(0)` after `add_shader` with E4's lists, and
      `stats.warnings == []`.
    - E16 `test_a_world_with_an_unsupported_graph_falls_back_with_one_warning`: E7's world. Expected: no
      `set_background_shader` call, T5.3's constant world for the fake scene, and
      `stats.warnings == ["background: the node type ShaderNodeBackground is not in the node table; evening uses
      world.color"]`. The world's constant fallback is compared the same way E12's is: against a second
      `sync_world` call with the node path disabled, so T5.3's `world.color` mapping stays M5's.
15. `.venv/bin/ruff format` on the two new modules, the modified `sync/` modules and the three new test files, then
    `.venv/bin/ruff check .`, then every acceptance command.

## Acceptance

Run every command from the repository root; the queue translates them with BACKLOG.md's table (`make check` → `CHECK`,
`make test-blender` → the same target with `KNOBS`, `build/dev` → `build/q`, `.venv/bin/<tool>` →
`MAIN/.venv/bin/<tool>`, any Python command prefixed with `PYTHONPATH="$PWD/analysis"`).
1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and the audit's
   `RESULT: PASS` line. This card adds one binding and no doctest, so the doctest counts are T-fix-TQ5a's and must not
   move.
2. `make audit` prints `RESULT: PASS`: no new exported symbol (the binding's lambda is in `bind_module`'s anonymous
   namespace, `python.cpp:80-997`, and `exports.map:1` still exports `PyInit__painterly` alone) and no new dependency
   (no CMake file changes).
3. `make test-blender` exits 0. Report its last line.
4. `.venv/bin/python -m pytest tests/blender/test_sync_shader_node_table.py tests/blender/test_sync_shader_export.py
   tests/blender/test_sync_node_materials.py -q` prints `22 passed`: step 12's six, step 13's ten and step 14's six —
   `6 + 10 + 6 = 22`. The count is the number of test names steps 12-14 list, and the run must print it; if it prints
   another count, the card's count is wrong and that is a finding, not a tolerance. Report its duration: the `bpy`
   import dominates and is about 0.6 s (`B7-flatten.md` `## Open for Opus` 4), and the fixtures write small `.blend`s
   under `tmp_path`, so no test needs `@pytest.mark.slow` (CLAUDE.md rule 6) and if the run exceeds about 10 s the
   fixtures are too big and that is a finding.
5. `.venv/bin/python -m pytest -q tests/core/test_api_contract.py` prints `31 passed`: the file unchanged. The count is
   the file's own — 31 `test_` functions, none parametrized. `_pyi_public_api` (`:65-82`) walks the pyi's public names,
   so `Scene.set_background_shader` is in it as soon as the pyi declares it, and
   `test_every_public_name_and_parameter_matches_the_pyi` (`:141`) then compares its one parameter name with the
   module's; it has no default, so `test_every_public_default_matches_the_pyi` (`:151`) compares nothing for it.
6. `git status --porcelain` lists only the five Create paths and the six Modify paths above.

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- return only the identifier from `input_candidates` → step 12's input ladder test fails on `ShaderNodeMath`'s
  `Value`, whose ladder must be `('Value', 'Value1')` (no `.blend` fixture of this card needs the ladder, because the
  three rows' own socket names are exact matches: that is why the ladder is tested directly);
- apply the Mix suffix step to the name *after* the numbering step → `A_Color` becomes `A_Color1` and step 12's input
  ladder test fails on that one line;
- add the `1` suffix to the output ladder → step 12's output ladder test fails on `ShaderNodeMath`'s `Value`, whose
  ladder must stay `('Value',)`;
- export an `output`-row node instead of skipping it → E6 gains `('output', {}, {'Displacement': (0.0, 0.0, 0.0)})`
  at index 2 and its links renumber, so acceptance command 4 fails on E6 only;
- export a linked input's default anyway → E1's emission gains `'Color': (1.0, 1.0, 1.0)`, so acceptance command 4
  fails on E1 (E9 has no link, so it is unchanged — which is why E1 and E9 are two tests);
- keep a link whose socket has no name in the row → E2 gains `(0, 'Object', -1, 'Thickness')` and acceptance command 4
  fails on E2 only;
- fall back silently, with no warning → E12, E14 and E16 fail on `stats.warnings`;
- warn on every call instead of once → E13 fails on the second call;
- pass `world.color` through `set_background_shader(0)` instead of the constant `set_background` → E16 fails on the
  fake's call log;
- drop `ENUM_ALIASES` and lowercase everything → step 12's enum test fails with the four unmapped identifiers
  (`FRACT`, `INVERSE_SQRT`, `SMOOTH_MAX`, `SMOOTH_MIN`), which is step 5's `unmapped` list;
- bind `set_background_shader` to `set_background(0.0)` → acceptance command 5 still passes (the signature is the
  same) and no test of this card catches it: B5's own acceptance covers the call, which is why this card's E15/E16
  check the call log rather than the render.

Report: the doctest and pytest counts, the audit line, the three test files' duration, and every mutation you ran with
its first failing check.

## Commit

`B8: sync/shader/node_table.py and export.py: the idname table, the socket ladders and the material and world export`

## Open for Opus

1. **The expected values' derivation.** `AGENTS.md` requires a script that produces a committed number to be committed
   next to its output, and this card's `allowedPaths` holds only this file, so the prototype that produced steps 3, 5
   and 12-14's expected values is not in the diff. What the card does instead: every bpy fact the rules rest on is
   step 1's probe, quoted with its output, and every expected value follows mechanically from a fixture the card
   spells out and rules 1-6. The acceptance test is what pins them, and a wrong value fails it — it cannot be adjusted
   to the code (`AGENTS.md`, "Expected values are evidence"). If Opus prefers the prototype committed, it needs a path
   outside this card's `allowedPaths`, for example `docs/handoff/drafts/M6b/B8-derive.py`, as B7's `## Open for Opus` 2
   asks for B7's.
2. **Two M5 signatures this card fixes.** `BRIEF.md:230-232` says the scene sync exports each material and the world
   and adds `SyncStats.warnings`, which needs the stats at both entry points, and M5's cards name neither
   `MaterialTable`'s constructor (`T5.3:32`) nor `sync_world`'s parameters (`T5.3:27`) beyond `(scene_core, scene)`.
   This card takes `MaterialTable(scene_core, stats=None)` and `sync_world(scene_core, scene, stats)`. The options:
   (a) keep it, with `stats=None` preserving T5.3's one-argument call so a T5.3 test that constructs the table
   directly keeps working; (b) make `stats` required, which breaks such a test unless T5.3's card is amended; (c) give
   `sync_world` an out-parameter like `build_scene`'s (`T5.2:48-55`), which is one more shape for the same thing. No
   acceptance check of this card depends on the choice except E12/E15's call sites.
3. **A second output node is silently dropped.** Step 6 drops an `output`-row node and its links, which is what Cycles
   does (`shader.cpp:1180`, `:1196-1200`, `:1451-1453`, `:1510-1521`), so E6 expects E1's value unchanged. The
   alternative — a warning, since a user who linked into a second output node probably meant the first — would need a
   channel to `SyncStats` from `export_graph`, which is a pure function today. This card takes Cycles' behaviour and E6
   pins it.
4. **`Thickness` is a Blender socket Cycles' `output` row does not name.** `ShaderNodeOutputMaterial` has
   `Surface`, `Volume`, `Displacement` and `Thickness` (step 1's probe), and `OutputNode.inc:5-8` names the first three
   plus `Normal`, which Blender 5.2.2's output node does not have. E2 therefore drops a link into `Thickness` without a
   word. The options: (a) keep it (this card; the socket drives Blender's shadow-terminator offset, which painterly has
   no term for); (b) warn once, which needs item 3's channel. Opus may also want the mismatch recorded in
   `docs/handoff/research/cycles_svm_report.md`'s "Not checked" list, whose idname table (`:657-690`) does not mention
   either socket.
5. **`from_dupli` comes from `from_instancer`.** The report's table (`cycles_svm_report.md:1084-1093` row) says Cycles
   reads `b_node.custom1`; bpy 5.2.2 exposes no `custom1` on `ShaderNodeTexCoord` and calls the property
   `from_instancer` (step 1's probe). Step 2 reads `from_instancer` and E1/E3 pin `from_dupli: False`. If a later bpy
   renames it, step 12's probe-derived test is where it shows. Whether `from_dupli` should be set at all for a
   painterly hit is not this card's: B3 owns the `ShaderData` a node material sees.
6. **What this card does not decide.** Per `BRIEF.md:295-301`: light node graphs stay out of v1, so `sync_lights`
   keeps its constant emission and this card does not look at a light's tree; whether a node material's emission is
   scaled by `emission_scale` is open and this card passes no knob (decision 8, `BRIEF.md:75-77`); Bump and Normal Map
   are out, so the `output` row's `Normal` input is named but never fed by a Blender node. `ShaderNodeOutputAOV` and
   the other `ShaderNodeOutput*` nodes have no row and are not this card's — B6's `add_shader` has one output node, and
   an AOV has no painterly counterpart.
7. **The world's `-1` sentinel.** `BRIEF.md:184` gives `KernelPainterlyBackground::cycles_shader` `-1` for the
   constant radiance, and this card's pyi comment states the same for Python, but B5's card owns the behaviour. If B5
   chooses a different sentinel, only the pyi's comment and E15's expected call change; `export_world` always passes a
   real shader index, so no test of this card passes `-1`.
