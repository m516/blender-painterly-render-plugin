# B7 — `sync/shader/flatten.py`: one graph out of Blender's node trees (drafted from BRIEF.md section 2, "B7")

Milestone: M6b · Depends on: M5 T5.4 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B7" (lines 212-219), per that brief's section 4 (lines
303-324) and the decisions of its section 1 that touch it (lines 15-80): decision 5 (:52-57) fixes the socket-name rule
this card hands to B8 by carrying Blender's `identifier` through, and decisions 8 (:75-77) and 9 (:78-79) bind its code
and its expected values. Code facts are `docs/handoff/drafts/M6b/FACTS.md` §3.12 and §5, re-read at this clone's HEAD in
every file cited below.
`BRIEF.md` gives B7 three scope bullets (:214-216); this card splits them into rules 1-5, and gives each rule, its
edge cases and every other rule of the module a fixture and an exact expected value.

## Goal
`src/blender/addon/sync/shader/flatten.py` turns a Blender shader node tree — a material's or the world's — into one
flat graph of real nodes and real links, the graph `sync/shader/export.py` (B8) then sends to `Scene.add_shader` (B6):

- **Rule 1: node groups are inlined, nested ones too** (BRIEF.md:214). A `ShaderNodeGroup` instance is replaced by the nodes of
  its tree, and each link into or out of the instance becomes a link to or from the node that the group's
  `NodeGroupInput` / `NodeGroupOutput` socket leads to or from.
- **Rule 2: reroutes are removed** (BRIEF.md:214): a `NodeReroute` carries its input straight to its output, so every link
  through it becomes one link that skips it.
- **Rule 3: a muted node passes through along Blender's internal links** (BRIEF.md:215): a muted node is replaced by its own
  `internal_links`, exactly as Cycles' `add_nodes_inlined` does with one proxy node per internal link
  (`docs/handoff/research/cycles_svm_report.md:648`, `add_nodes_inlined` at
  `intern/cycles/blender/shader.cpp:1353-1369`).
- **Rule 4: frames are ignored** (BRIEF.md:215): a `NodeFrame` is not a node of the graph, and its children are ordinary nodes.
- **Rule 5: closure, bundle and repeat zones raise `PainterlyUnsupportedNode` with the zone's name** (BRIEF.md:216, report R8 at
  `docs/handoff/research/cycles_svm_report.md:878-879`): Blender inlines those only in C++
  (`blender::nodes::inline_shader_node_tree`, `intern/cycles/blender/shader.cpp:1525-1545`), so a Python flattener must
  reject them rather than approximate them.

Nothing is exported, no Cycles type name is chosen and no socket is renamed: those are B8's (`BRIEF.md:221-227`). This
card's module is pure `bpy`, imports nothing from `_painterly`, and is not yet called by `sync/__init__.py` (B8 wires it,
`BRIEF.md:230`). It changes no render, so no image, no K and no parity test moves.

## Read first
- `CLAUDE.md` rules 1, 2 and 3 (scope; named knobs; PEP 8, type hints, docstrings); `AGENTS.md` "Expected values are
  evidence, not targets"; `docs/architecture.md:15-16` (the add-on tree, which already has `sync/ ... shader/`) and
  `docs/plan.md:66` ("Blender's node mapping (`intern/cycles/blender/shader.cpp`, Apache-2.0) becomes Python data
  tables"), with `docs/plan.md:124` naming this module.
- `docs/handoff/drafts/M6b/BRIEF.md` lines 212-219 (this card's mandate), :221-232 (B8, the only consumer of the
  interface below), :295-301 (the open questions this card must not decide) and :303-324 (how this card was drafted).
- `docs/handoff/drafts/M6b/FACTS.md` §3.12 (`src/blender/addon/` as it is: `sync/__init__.py` and `sync/reference.py`
  only, no `sync/shader/`), §5 row R8 and §6 gap 6 (M5 sync absent; B7 needs M5.T5.4).
- `docs/handoff/research/cycles_svm_report.md` §5: the `add_nodes_inlined` row `:614`, the "Graph walk
  (`add_nodes_inlined`)" bullets `:646-655` ("Muted nodes and reroutes become one same-type `ConvertNode` proxy per
  internal link", "Groups get proxy `ConvertNode`s per input and output socket, keyed by identifier, then recurse",
  "`NodeGroupInput` / `NodeGroupOutput` map to those proxies. Only the output with the `NODE_DO_OUTPUT` flag counts",
  "The output node is `ntreeShaderOutputNode(tree, SHD_OUTPUT_CYCLES)` ... the bpy equivalent is believed to be
  `node_tree.get_output_node('CYCLES')` (not checked in 5.2)") and R8 `:878-879`.
- Upstream `intern/cycles/blender/shader.cpp`, read in the pinned checkout (never edited, and not in this repo):
  `add_nodes_inlined` `:1334-1523` — the output node `:1349`, muted and rerouted nodes `:1353-1369`, groups
  `:1370-1419`, `NodeGroupInput` `:1420-1430`, `NodeGroupOutput` `:1431-1446`, ordinary nodes `:1447-1487`, links
  `:1490-1522` — and `add_nodes` `:1525-1545`, which is the C++-only inlining step (`inline_params.target_engine_ =
  SHD_OUTPUT_CYCLES` `:1538`).
- `src/blender/addon/sync/__init__.py` (the whole file: the M5 stub `build_scene` `:15-30`, which B8 replaces and this
  card does not touch) and `src/blender/addon/sync/reference.py:1-20` (the module docstring: the package is `bpy`-free
  where it can be, and `sync/` is where Blender data becomes core data).
- `tests/blender/conftest.py:36-59`: the add-on is imported from `src/blender/addon` as the package `painterly`, with
  `submodule_search_locations=[ADDON_DIR]`, so a test imports `painterly.sync.shader.flatten`; `HAS_BPY`
  (`:32-33`) skips the whole directory when `bpy` is absent, so no test here needs its own skip.
- `tests/blender/test_sync_*` naming: T5.2 and T5.3 create `tests/blender/test_sync_geometry.py` and
  `tests/blender/test_sync_lights_materials.py` (`docs/tasks/M5/T5.2-sync-geometry.md:39`,
  `docs/tasks/M5/T5.3-sync-lights-world-materials.md:47`), so this card's file is
  `tests/blender/test_sync_shader_flatten.py`.
- `Makefile:73-74` (`test-blender` runs `pytest tests/blender -q` after `build`), `pyproject.toml` (`[tool.ruff]`
  `line-length = 100`, `target-version = "py312"`; `[tool.pytest.ini_options]` `testpaths` includes `tests`).
- The bpy facts of steps 3-5, measured on this host with the project's `bpy` 5.2.2 by the probe in step 1.

## Create
- `src/blender/addon/sync/shader/__init__.py`
- `src/blender/addon/sync/shader/flatten.py`
- `tests/blender/test_sync_shader_flatten.py`

## Modify
None. This card adds a package and its test and changes no existing file: `sync/__init__.py` still raises the M5 stub
(`:15-30`) and B8 replaces it (`BRIEF.md:230`). `Makefile`, `pyproject.toml` and `tests/blender/conftest.py` already
cover a new module under `src/blender/addon/` and a new `tests/blender/test_*.py` (conftest imports the whole add-on
package by path, `tests/blender/conftest.py:48-56`; `test-blender` collects the directory, `Makefile:74`).

## Do not touch
- `src/blender/addon/sync/__init__.py`, `src/blender/addon/sync/reference.py`: B8 wires the sync; the reference scene is
  M3's and has no node tree.
- `src/blender/addon/sync/material.py`, `sync/world.py`, `sync/geometry.py`, `sync/light.py`: M5 T5.2-T5.4's files, and
  not present at this clone's HEAD. This card neither creates nor reads them.
- `src/blender/_painterly.pyi` (CONTRACT, `:4`), `src/blender/python.cpp`, `src/painterly/**`, `src/cycles/**`,
  `third_party/**`: this card calls no core function and vendors nothing (B6 and B8 own the bindings).
- `tests/blender/test_render_reference.py`, `tests/blender/test_properties.py`, `tests/blender/test_registration.py`,
  `tests/blender/test_ui_surface.py`, `tests/blender/conftest.py`: T4.3's and T4.2's tests, whose exact expected values
  stay as they are.
- `tests/blender_it/**`, `tools/**`, `Makefile`, `pyproject.toml`: no harness, no target and no lint setting changes
  (`BRIEF.md:237-255`: B9 owns the harness).

## Interface
No CONTRACT change. The names below are the module's public surface and B8 imports them; everything else in
`flatten.py` is `_`-prefixed and private.

`src/blender/addon/sync/shader/flatten.py`:

    # The to-node of a link into the tree's Cycles output node (the output node is not a graph node).
    OUTPUT_NODE: Final = -1

    class PainterlyUnsupportedNode(Exception):
        """A node tree the painterly export cannot represent (BRIEF.md:216, report R8)."""
        def __init__(self, node_name: str, zone: str) -> None: ...
        node_name: str   # the Blender node's name, as bpy.types.Node.name gives it
        zone: str        # "closure", "bundle", "repeat" or "group"

    @dataclass(frozen=True)
    class FlatNode:
        idname: str          # bpy.types.Node.bl_idname, e.g. "ShaderNodeMath"
        name: str            # the Blender node name, qualified by its group instances (step 3)
        node: bpy.types.Node # the live Blender node, for B8's parameter and default export

    @dataclass(frozen=True)
    class FlatLink:
        from_node: int   # index into FlattenedTree.nodes
        from_socket: str # bpy.types.NodeSocket.identifier of the output
        to_node: int     # index into FlattenedTree.nodes, or OUTPUT_NODE
        to_socket: str   # bpy.types.NodeSocket.identifier of the input

    @dataclass(frozen=True)
    class FlattenedTree:
        nodes: tuple[FlatNode, ...]
        links: tuple[FlatLink, ...]
        output_idname: str  # "ShaderNodeOutputMaterial" or "ShaderNodeOutputWorld"

    def zone_of(node: bpy.types.Node) -> str | None: ...
    def flatten_tree(tree: bpy.types.NodeTree) -> FlattenedTree: ...

The block is a declaration, not a runnable file: `Final` comes from `typing`, `dataclass` from `dataclasses`, and `bpy` is
imported at module level for the hints.

The socket names are Blender's `identifier`, not its UI name: `identifier` is what Blender's own internal links and group
proxies are keyed by (`intern/cycles/blender/shader.cpp:1389`, `:1404`, `:1423`, `:1436`), and it is the only name that is
unique within a node. Turning `identifier` into Cycles' UI name is B8's (`BRIEF.md:223-224`).

`flatten_tree` raises `PainterlyUnsupportedNode` for a zone (rule 5, step 4) and `ValueError` for a tree whose
`get_output_node("CYCLES")` is `None` (step 3).

## Steps
1. Preconditions. Each must hold; otherwise stop, commit nothing and report what you saw.
   - M5 T5.4 has landed (BRIEF.md:219). This prints a directory:
     ```
     ls -d src/blender/addon/sync
     ```
   - `sync/shader/` does not exist yet, so this prints nothing and exits 1:
     ```
     ls src/blender/addon/sync/shader
     ```
     If it exists, B7 has landed already or another card created it: stop and report.
   - `bpy` is importable and is 5.2.2 (`pyproject.toml`'s `blender` group):
     ```
     .venv/bin/python -c "import bpy; print(bpy.app.version_string)"
     ```
     prints `5.2.2 LTS`.
   - The bpy facts this card's rules rest on. Save this probe as a file under `/tmp` and run it with
     `.venv/bin/python <file>`; it must print exactly the lines quoted after it (they are this card's measurement on bpy
     5.2.2, and every rule in steps 3-5 is derived from them):
     ```python
     import bpy

     material = bpy.data.materials.new("probe")
     material.use_nodes = True
     tree = material.node_tree
     tree.nodes.clear()
     print("output node after nodes.clear():", tree.get_output_node("CYCLES"))
     output = tree.nodes.new("ShaderNodeOutputMaterial")
     print("material output:", output.bl_idname, output.type, "is_active_output =", output.is_active_output)
     math = tree.nodes.new("ShaderNodeMath")
     print("ShaderNodeMath inputs:", [(s.identifier, s.is_unavailable) for s in math.inputs])
     math.mute = True
     print("muted ShaderNodeMath internal_links:",
           [(link.from_socket.identifier, link.to_socket.identifier) for link in math.internal_links])
     math.mute = False
     reroute = tree.nodes.new("NodeReroute")
     print("reroute:", reroute.type,
           [(link.from_socket.identifier, link.to_socket.identifier) for link in reroute.internal_links])
     frame = tree.nodes.new("NodeFrame")
     print("frame:", frame.type, "sockets:", len(frame.inputs), len(frame.outputs))
     group = bpy.data.node_groups.new("probe group", "ShaderNodeTree")
     group.interface.new_socket("Fac", in_out="INPUT", socket_type="NodeSocketFloat")
     group.interface.new_socket("Col", in_out="OUTPUT", socket_type="NodeSocketColor")
     group_in = group.nodes.new("NodeGroupInput")
     group_out = group.nodes.new("NodeGroupOutput")
     instance = tree.nodes.new("ShaderNodeGroup")
     instance.node_tree = group
     print("group tree get_output_node:", group.get_output_node("CYCLES"))
     print("NodeGroupInput outputs:", [s.identifier for s in group_in.outputs])
     print("NodeGroupOutput inputs:", [s.identifier for s in group_out.inputs],
           "is_active_output =", group_out.is_active_output)
     print("group instance:", instance.type, "inputs:", [s.identifier for s in instance.inputs],
           "outputs:", [s.identifier for s in instance.outputs])
     instance.mute = True
     print("muted group instance internal_links:",
           [(link.from_socket.identifier, link.to_socket.identifier) for link in instance.internal_links])
     instance.mute = False
     creatable = 0
     zones = []
     for attribute in dir(bpy.types):
         node_type = getattr(bpy.types, attribute)
         try:
             if not issubclass(node_type, bpy.types.Node):
                 continue
         except TypeError:
             continue
         try:
             node = tree.nodes.new(node_type.bl_rna.identifier)
         except Exception:
             continue
         creatable += 1
         sockets = (*node.inputs, *node.outputs)
         if (node.type.startswith("REPEAT") or hasattr(node, "paired_output")
                 or any(s.type in ("BUNDLE", "CLOSURE") for s in sockets)):
             zones.append((node_type.bl_rna.identifier, node.type))
         tree.nodes.remove(node)
     print("node types a shader tree accepts:", creatable)
     print("of those, zone node types:", len(zones))
     for name, node_type in zones:
         print("   ", name, node_type)
     ```
     ```
     output node after nodes.clear(): None
     material output: ShaderNodeOutputMaterial OUTPUT_MATERIAL is_active_output = True
     ShaderNodeMath inputs: [('Value', False), ('Value_001', False), ('Value_002', True)]
     muted ShaderNodeMath internal_links: [('Value', 'Value')]
     reroute: REROUTE [('Input', 'Output')]
     frame: FRAME sockets: 0 0
     group tree get_output_node: None
     NodeGroupInput outputs: ['Socket_0', '__extend__']
     NodeGroupOutput inputs: ['Socket_1', '__extend__'] is_active_output = True
     group instance: GROUP inputs: ['Socket_0'] outputs: ['Socket_1']
     muted group instance internal_links: [('Socket_0', 'Socket_1')]
     node types a shader tree accepts: 118
     of those, zone node types: 8
         GeometryNodeRepeatInput REPEAT_INPUT
         GeometryNodeRepeatOutput REPEAT_OUTPUT
         NodeClosureInput NodeClosureInput
         NodeClosureOutput NodeClosureOutput
         NodeCombineBundle NodeCombineBundle
         NodeEvaluateClosure NodeEvaluateClosure
         NodeJoinBundle NodeJoinBundle
         NodeSeparateBundle NodeSeparateBundle
     ```
     What each line fixes:
     - a material tree's Cycles output node is `ShaderNodeOutputMaterial`, its `type` is `OUTPUT_MATERIAL`, and
       `is_active_output` marks the one `get_output_node("CYCLES")` returns — so step 3 skips exactly one node of the top
       tree and step 5 takes `output.bl_idname` as `output_idname`;
     - a group tree's `get_output_node("CYCLES")` is `None`, so a group's output node is its `NodeGroupOutput` with
       `is_active_output` (step 3), never `get_output_node`;
     - a muted node's `internal_links` pair an input with an output by `identifier` — one link for `ShaderNodeMath`, one
       for `NodeReroute`, and one per (input, output) pair for a group instance, which is why steps 3 and 5 resolve sockets
       by `identifier` and not by position;
     - a `NodeFrame` has no sockets, so ignoring it can drop no link;
     - exactly 8 of the 118 node types a shader tree accepts are zones, and the predicate that finds them is the one
       step 4 uses: `type.startswith("REPEAT")`, a `paired_output` property, or a `BUNDLE`/`CLOSURE` socket.
2. `src/blender/addon/sync/shader/__init__.py`: the package docstring (one paragraph: this package turns Blender node
   trees into the core's shader graphs; `flatten.py` is B7's, `node_table.py` and `export.py` are B8's, `BRIEF.md:212-232`)
   and `from __future__ import annotations`. No re-exports: B8 imports `painterly.sync.shader.flatten` by module, so the
   package's `__init__` must not import `flatten`, which imports `bpy`, into a `bpy`-free caller.
3. `src/blender/addon/sync/shader/flatten.py`, the module docstring and the walk. Rules 1 to 4 (BRIEF.md:214-215):
   - `flatten_tree(tree)`: `output = tree.get_output_node("CYCLES")`; `None` raises
     `ValueError(f"{tree.name!r} has no Cycles output node")`. Build a `_Frame` for `tree` with `output_node = output`,
     walk it (below) into `nodes`, then collect links for every frame in the order the frames were created (the top tree
     first, then each group's tree as the walk reaches its instance), and return `FlattenedTree(tuple(nodes),
     tuple(links), output.bl_idname)`.
   - `_Frame` is a private class holding `tree`, `parent`, `instance` (the `ShaderNodeGroup` in the parent tree, `None`
     for the top tree), `children` (a `dict` from a group instance node to its `_Frame` or `None`), `input_node`,
     `output_node` and `index` (a `dict` from a Blender node to its index in `nodes`).
   - The walk of one frame iterates `frame.tree.nodes` in Blender's own order and, for each node:
     - `node == frame.output_node` → skip (the output node is not a graph node, `shader.cpp:1349`);
     - `zone_of(node)` is not `None` → raise (rule 5, step 4);
     - `bl_idname == "NodeFrame"` → skip (rule 4, BRIEF.md:215);
     - `bl_idname == "NodeGroupInput"` → keep it as `frame.input_node` if that is still `None`, and add no node (rule 1);
     - `bl_idname == "NodeGroupOutput"` → if `frame.parent is not None and node.is_active_output`, make it
       `frame.output_node`; add no node (rule 1; a top tree's output node is `get_output_node`, and a second
       `NodeGroupOutput`-like node in a material tree is not the Cycles output);
     - `node.mute or node.type == "REROUTE"` → add no node; the node is resolved through `internal_links` when a link
       reaches it (rule 3, BRIEF.md:214-215);
     - `node.type == "GROUP"` → create the child `_Frame` for `node.node_tree` (or `None` when the instance has no tree),
       append it to the frame list, recurse, record it in `frame.children`, and add no node (rule 1, BRIEF.md:214);
     - otherwise append `FlatNode(node.bl_idname, _qualified_name(frame, node), node)` and record its index.
   - `_qualified_name(frame, node)` returns `node.name` for a node of the top tree, and otherwise the instance names from
     the top down, joined by `/`, then `node.name`: a node `math` inside a group instance `inner` inside an instance
     `outer` is `outer/inner/math`. `## Open for Opus` item 1 names this choice and its alternative.
4. `flatten.py`, the zone rule (rule 5, BRIEF.md:216, report R8). `zone_of(node)` returns:
   - `"repeat"` when `node.type.startswith("REPEAT")` (bpy registers `GeometryNodeRepeatInput` as `REPEAT_INPUT` and
     `GeometryNodeRepeatOutput` as `REPEAT_OUTPUT`, step 1's probe);
   - `"bundle"` when any of `(*node.inputs, *node.outputs)` has `type == "BUNDLE"` (`NodeCombineBundle`,
     `NodeSeparateBundle`, `NodeJoinBundle`);
   - `"closure"` when `node` has a `paired_output` property or any socket has `type == "CLOSURE"` (`NodeClosureInput`,
     `NodeClosureOutput`, `NodeEvaluateClosure`);
   - `None` otherwise.
   `PainterlyUnsupportedNode(node.name, zone)` is raised with the message
   `f"{node.name}: the {zone} zone is not supported"` and keeps `node_name` and `zone` as attributes, so B8 can name the
   node in its fallback warning (`BRIEF.md:230-231`). The exception is raised before the node is looked at any further,
   so a zone anywhere in a tree — the top tree or any group — fails the whole `flatten_tree` call. `"group"` is the one
   other `zone` value, for the case in step 5's last bullet.
   The predicate is deliberately the one step 1's probe printed: it classifies exactly the 8 zone node types of bpy 5.2.2
   and none of the other 110 a shader tree accepts, which is what the test of step 8 checks.
5. `flatten.py`, the link rules (BRIEF.md:214-215; `intern/cycles/blender/shader.cpp:1490-1522`). For each link of each
   frame's `tree.links`, in frame order:
   - skip the link when `not link.is_valid`, when `link.is_muted`, or when `link.from_socket.is_unavailable` or
     `link.to_socket.is_unavailable` (`shader.cpp:1494-1497`; the report's `:643-644`);
   - the two group boundary nodes are never graph nodes (step 3), so a link whose from-node is a `NodeGroupInput` or whose
     to-node is a `NodeGroupOutput` resolves to no graph node and is dropped by the last bullet below; the boundary is
     resolved from the other side instead;
   - resolve the source: `_source(frame, link.from_socket)` returns the real `(frame, socket)` behind an output socket.
     For a muted node or a `NodeReroute` it takes the `internal_links` entry whose `to_socket` is this socket and resolves
     that link's `from_socket` in the same frame; for a group instance it takes the child frame's `output_node` input whose
     `identifier` equals this socket's, and resolves that input in the child frame. `_source_of_input(frame, socket)` is
     the mirror: the `tree.links` entry whose `to_socket` is `socket`, skipped by the same `is_valid`/`is_muted`/
     `is_unavailable` test, then `_source` on its `from_socket`. Both return `None` when nothing resolves.
   - resolve the targets the same way in the other direction: `_targets(frame, socket, out)` appends `None` when the
     socket is the top tree's output node (that is a link to `OUTPUT_NODE`), follows the instance's own output socket into
     the parent frame when the socket is a child frame's output node, follows `internal_links` through a muted node or a
     reroute, and follows the child frame's `input_node` output when the socket belongs to a group instance;
     `_consumers(frame, socket, out)` is the mirror over `tree.links`. `_targets` and `_consumers` recurse into each
     other, so a chain of reroutes, muted nodes and group boundaries resolves to the real sockets at both ends.
   - append one `FlatLink(index_of_source_node, source_socket.identifier, index_of_target_node_or_OUTPUT_NODE,
     target_socket.identifier)` per resolved target whose node is a graph node of its frame, and nothing when either end
     does not resolve to one (an unsupported node on the far side, a link into an unavailable socket, or a group instance
     whose tree is `None`).
   - drop duplicate `FlatLink`s, keeping the first: two Blender links that resolve to the same pair of real sockets (a
     reroute and its neighbour, or a muted node between them) are one link of the flat graph.
   - a group instance whose `node_tree` is an ancestor of itself cannot be built in bpy — assigning a tree to a node of
     that same tree leaves `node_tree` as `None` (measured: `bpy` 5.2.2, `node.node_tree = its own tree` reads back
     `None`) — so the `"group"` value of step 4 is a guard with no reachable case in 5.2.2. Keep it: the walk must not
     recurse forever if a later Blender allows it.
6. `flatten.py`, the module-level constants and the docstring's statement of the rules:
   - `OUTPUT_NODE: Final = -1` (`## Interface`), with the comment that `-1` is B6's own sentinel for the graph's output
     (`BRIEF.md:201-202`), so B8 passes `FlatLink.to_node` straight through;
   - `SKIPPED_NODE_TYPES: Final = frozenset({"NodeFrame", "NodeGroupInput", "NodeGroupOutput"})` and
     `ZONE_SOCKET_TYPES: Final = frozenset({"BUNDLE", "CLOSURE"})`, each with the rule it serves; no other module-level
     value: this card has no tunable and adds no knob (BRIEF.md:75-77, CLAUDE.md rule 2).
   - the docstring states rules 1 to 5 with their sources (`BRIEF.md:214-216`, report `:646-655`, R8 `:878-879`), and
     says that the flat graph is in walk order (the top tree's nodes first) and that a link's `to_node` of `-1` is the
     tree's Cycles output node.
7. `src/blender/addon/sync/shader/flatten.py` type hints and style: `from __future__ import annotations`; `bpy` imported
   at module level (`bpy.types.Node`, `bpy.types.NodeTree` in the hints); the private `_Frame` class and the `_`-prefixed
   helpers; docstrings on every public name, with the units and conventions the interface names. `ruff format` and
   `ruff check` clean.
8. `tests/blender/test_sync_shader_flatten.py`: 17 tests, one per rule and one per edge case, each building its own tree
   in a fresh `bpy.data.materials.new(...)` (or `bpy.data.worlds.new(...)`) with `use_nodes = True` and `tree.nodes.clear()`, naming
   every node it creates with `node.name = "<name>"`, and comparing the flattened graph with an expected value written
   as a literal. The comparison is exact equality of
   `([(node.idname, node.name) for node in tree.nodes], sorted(links))`, where a link is
   `(from_node, from_socket, to_node, to_socket)`: the node indices are positions in the list, so the expected value pins
   the walk order, the socket identifiers and the `-1` sentinel at once, and no tolerance appears anywhere.
   Every expected value below was produced by running an implementation of steps 3-6 against bpy 5.2.2, in this card's
   own scratch prototype (not committed; `## Open for Opus` item 2). Each test builds exactly the fixture quoted with it.
   - `test_a_plain_tree_flattens_to_its_own_nodes_and_links`. Fixture: `ShaderNodeOutputMaterial` `output`,
     `ShaderNodeTexCoord` `coords`, `ShaderNodeMath` `scale`, `ShaderNodeBsdfDiffuse` `bsdf`;
     `coords.Object → scale.Value`, `scale.Value → bsdf.Color`, `bsdf.BSDF → output.Surface`. Expected:
     ```
     ([('ShaderNodeTexCoord', 'coords'), ('ShaderNodeMath', 'scale'), ('ShaderNodeBsdfDiffuse', 'bsdf')],
      [(0, 'Object', 1, 'Value'), (1, 'Value', 2, 'Color'), (2, 'BSDF', -1, 'Surface')])
     ```
     `output` is not a node (step 3's first bullet) and its `Surface` input is the `-1` sentinel.
   - `test_a_reroute_is_removed`. Fixture: the plain tree, with the `coords.Object → scale.Value` link replaced by
     `coords.Object → hop.Input` and `hop.Output → scale.Value`, where `hop` is a `NodeReroute`. Expected: the plain
     tree's value above, unchanged — the reroute contributes no node and its two links become one
     (`coords.Object → scale.Value`).
   - `test_a_muted_node_passes_through_its_internal_links`. Fixture: the plain tree with `scale.mute = True`. Expected:
     ```
     ([('ShaderNodeTexCoord', 'coords'), ('ShaderNodeBsdfDiffuse', 'bsdf')],
      [(0, 'Object', 1, 'Color'), (1, 'BSDF', -1, 'Surface')])
     ```
     `scale` is not a node; `coords.Object` reaches `bsdf.Color` through the muted node's one internal link
     (`Value → Value`, step 1's probe), and `scale`'s third input is unavailable so nothing else exists to lose.
   - `test_frames_are_ignored`. Fixture: the plain tree with `frame = tree.nodes.new("NodeFrame")`, `scale.parent =
     frame` and `bsdf.parent = frame`. Expected: the plain tree's value above — a frame has no sockets and adds no node
     and no link.
   - `test_a_group_is_inlined`. Fixture: group `shade` with interface sockets `Fac` (input, `NodeSocketFloat`) and
     `Value` (output, `NodeSocketFloat`), holding `NodeGroupInput`, `NodeGroupOutput` and `ShaderNodeMath` `math`
     (`NodeGroupInput.0 → math.0`, `math.0 → NodeGroupOutput.0`). The tree: `output`, a `ShaderNodeGroup` `shade` with
     `node_tree = shade`, `coords`, `bsdf`; `coords.Object → shade.0`, `shade.0 → bsdf.Color`,
     `bsdf.BSDF → output.Surface`. Expected:
     ```
     ([('ShaderNodeMath', 'shade/math'), ('ShaderNodeTexCoord', 'coords'), ('ShaderNodeBsdfDiffuse', 'bsdf')],
      [(0, 'Value', 2, 'Color'), (1, 'Object', 0, 'Value'), (2, 'BSDF', -1, 'Surface')])
     ```
     The instance and both boundary nodes are gone, the group's one node is at index 0 because the walk reaches the
     child frame as it reaches the instance, and the two links cross the boundary in both directions.
   - `test_nested_groups_are_inlined`. Fixture: group `inner` as `shade` above with its math node named `math`, group
     `outer` holding `NodeGroupInput`, `NodeGroupOutput` and a `ShaderNodeGroup` `inner` with `node_tree = inner`, and the
     tree holding `output`, a `ShaderNodeGroup` `outer`, `coords` and `bsdf`, linked as in the previous case. Expected:
     ```
     ([('ShaderNodeMath', 'outer/inner/math'), ('ShaderNodeTexCoord', 'coords'), ('ShaderNodeBsdfDiffuse', 'bsdf')],
      [(0, 'Value', 2, 'Color'), (1, 'Object', 0, 'Value'), (2, 'BSDF', -1, 'Surface')])
     ```
     The links are the previous case's; only the qualified name grows by one instance, which is what makes two copies of
     one tree distinguishable (`## Open for Opus` item 1).
   - `test_a_muted_group_passes_through_its_internal_links`. Fixture: the group case with `shade.mute = True`. Expected:
     ```
     ([('ShaderNodeTexCoord', 'coords'), ('ShaderNodeBsdfDiffuse', 'bsdf')],
      [(0, 'Object', 1, 'Color'), (1, 'BSDF', -1, 'Surface')])
     ```
     A muted instance is resolved like a muted node, through its one internal link `Socket_0 → Socket_1` (step 1's
     probe), and its tree is not walked at all.
   - `test_two_instances_of_one_group_are_two_copies`. Fixture: `output`, a `ShaderNodeGroup` `first` and a
     `ShaderNodeGroup` `second`, both with `node_tree = shade`, and `ShaderNodeEmission` `emit`; `first.0 → emit.Color`,
     `emit.Emission → output.Surface`. Expected:
     ```
     ([('ShaderNodeMath', 'first/math'), ('ShaderNodeMath', 'second/math'), ('ShaderNodeEmission', 'emit')],
      [(0, 'Value', 2, 'Color'), (2, 'Emission', -1, 'Surface')])
     ```
     One tree, two inlined copies, in instance order; `second` is unlinked and its copy is still a node (Cycles adds
     every node and lets the optimizer drop it, `shader.cpp:1447-1487`).
   - `test_one_output_feeds_two_inputs`. Fixture: `output`, `coords`, `ShaderNodeMath` `a`, `ShaderNodeMath` `b`, a
     `ShaderNodeMix` `mix` with `data_type = "RGBA"` and `ShaderNodeEmission` `emit`; `coords.Object → a.0`,
     `coords.Object → b.0`, `a.0 → mix.A_Color`, `b.0 → mix.B_Color`, `mix.Result_Color → emit.Color`,
     `emit.Emission → output.Surface`. Expected:
     ```
     ([('ShaderNodeTexCoord', 'coords'), ('ShaderNodeMath', 'a'), ('ShaderNodeMath', 'b'),
       ('ShaderNodeMix', 'mix'), ('ShaderNodeEmission', 'emit')],
      [(0, 'Object', 1, 'Value'), (0, 'Object', 2, 'Value'), (1, 'Value', 3, 'A_Color'),
       (2, 'Value', 3, 'B_Color'), (3, 'Result_Color', 4, 'Color'), (4, 'Emission', -1, 'Surface')])
     ```
     Two links leave one socket, so the flat graph is not a function: `_consumers` returns both targets.
   - `test_an_invalid_link_is_skipped`. Fixture: `output`, `coords`, `ShaderNodeMath` `value`, a `ShaderNodeMix` `mix`
     built with `data_type = "FLOAT"` and `ShaderNodeEmission` `emit`; `coords.Object → value.0`, then the link
     `value.Value → mix.A_Float` (found by `identifier`, because a Mix's `inputs` index by type), then
     `mix.Result_Float → emit.Color`, `emit.Emission → output.Surface`; then `mix.data_type = "RGBA"`, which makes the two
     links to and from `mix` invalid (`switch.is_valid` is `False` and `a_float.is_unavailable` is `True`; measured,
     `## Open for Opus` item 3). Expected:
     ```
     ([('ShaderNodeTexCoord', 'coords'), ('ShaderNodeMath', 'value'), ('ShaderNodeMix', 'mix'),
       ('ShaderNodeEmission', 'emit')],
      [(0, 'Object', 1, 'Value'), (3, 'Emission', -1, 'Surface')])
     ```
     The test first asserts the premise — `CHECK(switch.is_valid is False)` and
     `CHECK(a_float.is_unavailable is True)` — so it cannot pass vacuously on a bpy that keeps the link valid.
   - `test_a_muted_link_is_skipped`. Fixture: `output`, `coords`, `bsdf`, with
     `coords.Normal → bsdf.Normal` muted (`link.is_muted = True`) and `bsdf.BSDF → output.Surface`. Expected:
     ```
     ([('ShaderNodeTexCoord', 'coords'), ('ShaderNodeBsdfDiffuse', 'bsdf')], [(1, 'BSDF', -1, 'Surface')])
     ```
     The test asserts `CHECK(muted.is_valid is True)` and `CHECK(muted.is_muted is True)` first: the link is valid and
     muted, so it is the mute rule and not the validity rule that drops it.
   - `test_a_closure_zone_raises`, `test_a_bundle_zone_raises`, `test_a_repeat_zone_raises`: a tree holding `output` and
     one zone node named `zone` — `NodeClosureInput`, `NodeCombineBundle`, `GeometryNodeRepeatInput`. Each test asserts
     `pytest.raises(PainterlyUnsupportedNode)` and then, on the captured exception, `str(error)`,
     `error.node_name` and `error.zone`:
     ```
     ('zone: the closure zone is not supported', 'zone', 'closure')
     ('zone: the bundle zone is not supported', 'zone', 'bundle')
     ('zone: the repeat zone is not supported', 'zone', 'repeat')
     ```
   - `test_a_tree_without_a_cycles_output_raises`. Fixture: a tree holding only a `ShaderNodeBsdfDiffuse` `bsdf`
     (`nodes.clear()` leaves no output node, step 1's probe). Expected: `ValueError` whose `str` is
     `"'Shader Nodetree' has no Cycles output node"` — the tree's `name` is Blender's default for a material's tree.
   - `test_a_world_tree_flattens_to_its_background`. Fixture: `bpy.data.worlds.new("world")` with `use_nodes = True` and
     `nodes.clear()`, a `ShaderNodeOutputWorld`, and a `ShaderNodeBackground` `background` with
     `background.Background → output.Surface`. Expected:
     ```
     ('ShaderNodeOutputWorld',
      ([('ShaderNodeBackground', 'background')], [(0, 'Background', -1, 'Surface')]))
     ```
     This is the value `FlattenedTree.output_idname` carries, so B8 can tell a material tree from the world's
     (`BRIEF.md:230`).
   - `test_the_zone_node_types_are_the_ones_bpy_registers`. The guard on step 4's predicate: walk every `bpy.types`
     subclass of `bpy.types.Node`, try `tree.nodes.new(...)` for it, and collect those for which `zone_of` is not `None`.
     Expected: exactly the 8 pairs of step 1's probe output
     (`GeometryNodeRepeatInput`/`repeat`, `GeometryNodeRepeatOutput`/`repeat`, `NodeClosureInput`/`closure`,
     `NodeClosureOutput`/`closure`, `NodeCombineBundle`/`bundle`, `NodeEvaluateClosure`/`closure`,
     `NodeJoinBundle`/`bundle`, `NodeSeparateBundle`/`bundle`), compared as a `set` against a literal — so a bpy that
     renames one, or a predicate that widens and catches an ordinary node, fails here instead of in B8's export.
   - Every test's tree is built inside the test (no module-level `bpy.data` state), so the tests do not depend on
     order; nothing is rendered and nothing is written to disk.
9. `.venv/bin/ruff format src/blender/addon/sync/shader tests/blender/test_sync_shader_flatten.py` and
   `.venv/bin/ruff check .`, then every acceptance command.

## Acceptance
Run every command from the repository root; the queue translates them with BACKLOG.md's table (`make check` → `CHECK`,
`make test-blender` → the same target with `KNOBS`, `build/dev` → `build/q`, `.venv/bin/<tool>` → `MAIN/.venv/bin/<tool>`,
any Python command prefixed with `PYTHONPATH="$PWD/analysis"`).
1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and the audit's
   `RESULT: PASS` line. This card adds no C++, so the doctest counts are T-fix-TQ5a's and must not move.
2. `make test-blender` exits 0. Report its last line.
3. `.venv/bin/python -m pytest tests/blender/test_sync_shader_flatten.py -q` prints `17 passed` — the 17 tests step 8
   names: the plain tree, rule 1 four times (group, nested, two instances, muted group), rules 2, 3 and 4 once each,
   rule 5 three times, the fan-out, the two link rules, the missing output, the world tree and the zone-table guard —
   `1 + 4 + 1 + 1 + 1 + 3 + 1 + 2 + 1 + 1 + 1 = 17`. The count is the number of test names step 8 lists, and the run must
   print it; if it prints another count, the card's count is wrong and that is a finding, not a tolerance. Report its
   duration: the `bpy` import dominates and is about 0.6 s (`## Open for Opus` item 4).
4. `.venv/bin/python -m pytest tests/blender -q` prints 17 more passing tests than it did before this card, and no
   failure: T4.2's and T4.3's Blender tests are unchanged and keep their exact expected values.
5. `git diff --stat` prints nothing: this card modifies no existing file (`## Modify` is None), so T4.2's and T4.3's
   expected values and the M5 files B8 will edit are untouched.
6. `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .` are clean (the two `lint` lines of `CHECK`).
7. `git status --porcelain` lists only the three Create paths of this card.

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- stop skipping the output node → acceptance command 3 fails on the plain case, whose node list would gain
  `('ShaderNodeOutputMaterial', 'output')` at index 0 and whose links would renumber;
- keep the reroute as a node → acceptance command 3 fails on the reroute case only;
- ignore `internal_links` for a muted node → acceptance command 3 fails on the muted and muted-group cases, whose node
  lists lose `scale` but whose links lose `coords.Object → bsdf.Color`;
- resolve a group's sockets by position instead of `identifier` → acceptance command 3 fails on the group case as soon as
  the group's interface has two sockets in a different order (add a second socket to the fixture and the mutation shows
  it), and on the nested case;
- return `tree.get_output_node("CYCLES").bl_idname` for a group's output node → acceptance command 3 fails on the group,
  nested and muted-group cases, because `get_output_node("CYCLES")` is `None` in a group tree (step 1's probe);
- drop the duplicate-`FlatLink` filter → acceptance command 3 fails on the reroute and muted cases, whose link lists
  gain a second copy of the bypassed link;
- widen `zone_of` to `node.type.startswith("Node")` → acceptance command 3 fails on every non-zone case and on the
  zone-table guard;
- narrow `zone_of` to `node.type.startswith("REPEAT")` → acceptance command 3 fails on the closure and bundle cases;
- return `node.name` instead of `_qualified_name(...)` → acceptance command 3 fails on the group, nested and two-instance
  cases.

Report: the pytest counts of acceptance commands 1-4, the audit line, and every mutation you ran with its first failing
check.

## Commit
`B7: sync/shader/flatten.py: groups inlined, reroutes removed, mutes passed through, zones rejected`

## Open for Opus
1. **A node's `name` is qualified by its group instances.** A group inlined twice puts two copies of one tree's nodes
   into one graph, and the copies share their Blender names (step 8's two-instance case). This card writes
   `instance/…/node.name`, which makes the copies distinguishable and lets B8's fallback warning name the node it fell
   back on (`BRIEF.md:230-231`). The alternative is `node.name` alone: shorter, and enough for B6's `add_shader`, whose
   node list is indexed (`BRIEF.md:200-202`), but then a warning about the second copy says only `math`. This card takes
   the qualified name; no other card's interface changes either way, and step 8's expected values are the only place the
   choice shows.
2. **The expected values' derivation.** `AGENTS.md` requires a script that produces a committed number to be committed
   next to its output, and this card's `allowedPaths` holds only this file, so the prototype that produced step 8's
   expected values is not in the diff. What the card does instead: every bpy fact the rules rest on is step 1's probe,
   quoted with its output, and every expected value follows mechanically from a fixture the card spells out and the five
   numbered rules. The acceptance test is what pins them, and a wrong value fails it — it cannot be adjusted to the code
   (`AGENTS.md`, "Expected values are evidence"). If Opus prefers the prototype committed, it needs a path outside this
   card's `allowedPaths`, for example `docs/handoff/drafts/M6b/B7-derive.py`.
3. **Two bpy facts this card measured and relies on.** (a) `mix.data_type = "RGBA"` after a link to `A_Float` leaves
   `link.is_valid` `False` and `A_Float.is_unavailable` `True` — the premise of the invalid-link test; both are asserted
   before the comparison. (b) Assigning a node tree to a node inside that same tree leaves `node_tree` `None`, so bpy 5.2.2
   cannot build a recursive group; step 5 keeps the `"group"` guard for a later Blender that can. Neither is in
   `docs/handoff/research/cycles_svm_report.md`'s "Not checked" list (`:884-892`), which predates this measurement; a docs
   card may want to add them.
4. **No `slow` marker.** Step 8's 17 tests build small trees in memory; the only cost is `bpy`'s import, about 0.6 s, and
   `tests/blender` imports it once per process (`tests/blender/conftest.py:59`). So the file needs no
   `@pytest.mark.slow` (CLAUDE.md rule 6). Acceptance command 3 reports the duration, and if it exceeds about 10 s the
   card's fixtures are too big and that is a finding.
5. **What this card does not decide.** Per `BRIEF.md:295-301`: what an unsupported *node* (as opposed to a zone) does is
   B8's (it falls back to M5's constant mapping with one warning, `BRIEF.md:230-231`); whether a `ShaderNodeCustomGroup`
   is supported is open — bpy 5.2.2 refuses to create one in a shader tree (`Error: Node type ShaderNodeCustomGroup
   undefined`), so no fixture can show it, and step 3 treats it as an ordinary node if a future bpy creates it; and
   `node_use_modified_socket_name` (report `:611`) is OSL-only, so this card has no rule for it.
