# B6 — The `_painterly` shader-graph API
Milestone: M6b · Depends on: B2, B4, T3.15 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B6" (lines 198-210) and its section 1 decisions 3, 5, 8
and 9 (lines 30-37, 52-57, 75-79), per that brief's section 4 (lines 303-324). Code facts are
`docs/handoff/drafts/M6b/FACTS.md` §3, re-read at this clone's HEAD in every file cited below. `Parallel-safe: no`
because B8 binds `Scene.set_background_shader` in the same two files (`## Open for Opus` 8).

## Goal
A Python caller can build a Cycles shader graph and give it to a material, and a graph built from Python renders
exactly as the same graph built in C++:
- `Scene.add_shader(nodes, links) -> int` creates the graph Cycles' own `add_node` creates from a Blender node tree
  (BRIEF.md:200-202): one `ShaderNode` per entry, found by Cycles type name (`NodeType::find`,
  `third_party/cycles/graph/node_type.cpp:282-289`), its parameters by member name with enums by `NodeEnum` name
  (`NodeType::find_input`, `:186-196`; `Node::set(const SocketType &, ustring)`, `graph/node.cpp:100-117`), its unlinked
  linkable inputs by UI name (`ShaderNode::input`, `scene/shader_graph.cpp:93-102`), then one `ShaderGraph::connect` per
  link (`:248`), with to-node -1 naming the graph's output node (`:243-246`).
- `Scene.add_node_material(shader) -> int` makes a material of that graph (BRIEF.md:203). The world's binding,
  `Scene.set_background_shader`, is B8's and is not in this card.
- A rejected call names what it could not find: an unknown type, parameter, socket or enum name raises `ValueError`
  naming it, a wrong value type raises `TypeError` (BRIEF.md:204-205), and a rejected `add_shader` adds no shader.
  Indices are dense from 0 (`src/blender/_painterly.pyi:7`), which is B2's `add_shader`/`add_node_material` returning
  `size() - 1` as `PainterlyScene::add_material` does (`scene/scene.cpp:35-44`).
- Nothing else changes: no kernel type, no scene API, no new knob. The two methods are the only new public names, and
  the graph is built by Cycles' own `graph/` code, so no node-table knowledge enters this card (B8 owns the Blender
  idname table).

## Read first
- `CLAUDE.md` rules 1, 2 and 3; `AGENTS.md` "Expected values are evidence"; `docs/architecture.md:57-70` (the
  bindings are a thin conversion layer; `PainterlyScene` is the only bridge).
- `docs/handoff/drafts/M6b/BRIEF.md` lines 198-210 (this card's mandate), 30-37 (a material is constant or a node
  material), 52-57 (socket names, and the one `painterly_cycles_shader_node_types()` call) and 75-79 (no new knob;
  expected values are evidence).
- The CONTRACT header `src/blender/_painterly.pyi` (read it, never edit it before dispatch: `:4` is
  `CONTRACT: Opus-owned`): `Scene` `:45`, `add_material` `:49-54`, `set_background` `:111`, `set_integrator`
  `:124-126`, and the dense-index sentence `:7`.
- `src/blender/python.cpp`: the conversion helpers this card reuses — `WrongTypeError` `:266`, `throw_wrong_type` `:273`,
  `throw_wrong_type_chained` `:286`, `as_real` `:301`, `as_integer` `:314`, `lobe_kind_from_python` `:534`,
  `double3_from_python` `:589`, `affine_3x4_from_python` `:624` — and the binding it extends: `bind_module` `:682`,
  `nb::class_<PainterlyScene>` `:694`, `add_material` `:697-720`, `set_integrator`'s name lookup `:909-926`. The file's
  anonymous namespace runs from `:80` to `:997`, and `NB_MODULE` is `:1001`.
- Cycles' graph, which this card drives and does not change: `third_party/cycles/graph/node_type.h` (`SocketType`
  `:28-102`, `NodeType` `:106-143`, `find_input`/`find_output` `:123-124`, `add`/`find` `:135-139`, `SOCKET_DEFINE`
  `:196-209`, the parameter macros `:211-259`, `SOCKET_IN_*` `:330-398`), `graph/node.h` (`Node::set` overloads
  `:96-104`), `graph/node_enum.h` (`NodeEnum` `:16-63`, `exists` `:29-32`), `graph/node.cpp:100-117` (why an enum name
  must be checked before it is set).
- `third_party/cycles/scene/shader_graph.h` (`ShaderIO` `:66-89`, `ShaderInput` `:97-120`, `ShaderNode` `:145-154`,
  `ShaderGraph` `:335-350`, `nodes` `:337`, `output()` `:346`, `connect` `:348`, `create_node(const NodeType *)`
  `:383-390`) and `scene/shader_graph.cpp` (`create_inputs_outputs` `:80-91`, `input`/`output` `:93-135`, the
  constructor's `OutputNode` `:220-226`, `output()` `:243-246`, `connect` `:248-256`).
- `third_party/cycles/util/transform.h:52-65` (`Transform`: three `float4` rows) and `:194-223` (`make_transform`'s
  twelve floats), the only value type of the nine parameters that is not a number, a string or a `float3`.
- The node definitions this card's two tests build: `third_party/cycles/fragments/scene/shader_nodes_cpp/node_define/`
  `MathNode.inc` (`:8` `multiply`, `:47` `math_type`, `:49` `use_clamp`, `:51-52` `Value1`/`Value2`, `:55` `Value`),
  `EmissionNode.inc` (`:5` `Color`, `:6` `Strength`, `:10` `Emission`) and `OutputNode.inc` (`:5` `Surface`).
- `src/painterly/scene/scene.h` (`add_material` `:52`, `device_update` `:103`) and `scene/scene.cpp:21-33` (`clear`),
  read only: B2 adds `add_shader` and `add_node_material` to that class.
- The collector, which gives the lobes and emission a node material renders with:
  `src/painterly/kernel/svm/collect.h:165-211`, and its zero-closure fallback `:205-210`.
- The three test files this card's new tests follow: `src/test/test_session.cpp:186-207` (`render_directly`, the render
  loop a `PainterlyScene` needs) and `:209-228` (`check_buffers_equal`), `src/test/test_path_trace.cpp:95-103`
  (`bit_identical`), and `src/test/test_cycles_svm_closures.cpp:47-107` (`make_scene`, `shader_manager`,
  `create_node_by_name`, `add_surface`) and `tests/core/test_api_contract.py:65-82,141,151` (the generic pyi checks that cover the
  new names without an edit).
- `docs/handoff/drafts/M6b/B4-svm-trace-pixel.md` (the card that puts the SVM in `painterly_trace_pixel`, and the lobe
  table at its step 9 whose derivations this card's expected emission reuses).

## Create
- `src/test/test_shader_api.cpp`
- `tests/core/test_shader_graph_api.py`

## Modify
- `src/blender/_painterly.pyi` (CONTRACT, `:4`): the two methods of `## Interface`, in `class Scene` after
  `add_material` (`:50-54`), and the `M6 adds add_shader` note at `:49` reworded to what now exists.
- `src/blender/python.cpp`: the two bindings on the `Scene` class (`:694`), and the conversion helpers they need in the
  anonymous namespace beside `lobe_kind_from_python` (`:534`).
- `src/test/CMakeLists.txt`: `test_shader_api.cpp` in `painterly_tests` (step 5's last bullet).

## Do not touch
- `src/painterly/scene/scene.h`, `src/painterly/scene/scene.cpp`: `PainterlyScene::add_shader(std::unique_ptr<ShaderGraph>)`
  and `add_node_material(int)` are B2's (BRIEF.md:115-116); this card calls them.
- `src/painterly/kernel/globals.h` (B1's CONTRACT), `src/painterly/kernel/types.h` (B2's CONTRACT `cycles_shader`,
  BRIEF.md:30-37), `src/painterly/kernel/svm/shader_data.h` (B3's), `src/painterly/kernel/integrator/path.h` (B4's).
- `src/blender/addon/**`: `sync/shader/node_table.py` and `export.py` are B8's, and they are the only place a Blender
  idname becomes a Cycles type name (BRIEF.md:221-227). This card knows no Blender idname.
- `third_party/cycles/**` (vendored; `tools/vendor_sync.py` only) and `src/cycles/shim/**`.
- `tests/core/test_api_contract.py`: it must pass unchanged. Its two generic tests read the pyi itself, so they cover the
  new names, parameters and defaults without an edit (see `## Acceptance` 5).
- `tests/core/test_oracle_parity.py`, `tests/core/test_triangle_path.py`: unchanged.
- `src/blender/CMakeLists.txt` (no new module source), `Makefile`, `pyproject.toml`, `src/cycles/CMakeLists.txt`.

## Interface
CONTRACT (Opus writes this before dispatch): `src/blender/_painterly.pyi`, `class Scene`, exactly the declarations the
brief gives at BRIEF.md:200-203, with the brief's two sentences as comments:

    # --- materials: lobe mixtures (SPEC §6), and SVM node graphs. ---
    def add_material(...) -> int: ...        # unchanged (:50-54)
    # One node is (Cycles type name, parameters by member name, linkable input defaults by UI name).
    # One link is (from node, output UI name, to node, input UI name); to-node -1 is the graph's output.
    # Unknown type, parameter, socket or enum names raise ValueError naming them; a wrong value type raises
    # TypeError. Returns the shader index.
    def add_shader(
        self,
        nodes: list[tuple[str, dict[str, object], dict[str, object]]],
        links: list[tuple[int, str, int, str]],
    ) -> int: ...
    # A material whose lobes and emission come from `shader` (BRIEF.md:35). Returns the material index.
    def add_node_material(self, shader: int) -> int: ...

The world's binding is B8's: `Scene.set_background_shader(shader: int) -> None` is not this card's (BRIEF.md:203,
:228-229).

Not a CONTRACT: nothing. The conversion helpers stay in `python.cpp`'s anonymous namespace (`:80-997`), so the module
grows two methods and no exported symbol: `exports.map:1` still exports `PyInit__painterly` alone.

The C++ side is B2's, and this card calls it as B2 writes it (BRIEF.md:115-116):

    int PainterlyScene::add_shader(std::unique_ptr<ShaderGraph> graph);   // shader index, dense from 0
    int PainterlyScene::add_node_material(int shader);                    // material index, dense from 0

## Steps
1. Preconditions. Each must hold; otherwise stop, commit nothing and report what you saw.
   - B1 landed, including its `std::call_once` call: this prints `1`.
     ```
     grep -c 'painterly_cycles_shader_node_types' src/blender/python.cpp
     ```
     If it prints `0`, the registry call of BRIEF.md:56-57 has not arrived and this card's first `NodeType::find` would
     race the vendored getter (`graph/node_type.h:157-176`); B1 step 12 is that call, and this card does not add a
     second one.
   - B2 landed: this prints `1` for each, and the CONTRACT field is renamed.
     ```
     grep -c 'add_shader' src/painterly/scene/scene.h
     grep -c 'add_node_material' src/painterly/scene/scene.h
     grep -c 'int cycles_shader' src/painterly/kernel/types.h
     ```
   - B4 landed, because the acceptance renders a node material and only B4's `painterly_hit_material` evaluates one
     (`src/painterly/kernel/svm/hit_material.h`): this prints `1`.
     ```
     grep -c 'painterly_svm_shader_setup' src/painterly/kernel/svm/shader_data.h
     grep -c 'painterly_hit_material' src/painterly/kernel/integrator/path.h
     ```
   - The two methods are not bound yet. Each of these prints `0`:
     ```
     grep -c 'add_shader' src/blender/python.cpp
     grep -c 'add_node_material' src/blender/_painterly.pyi
     ```
   - The value types the binding must convert are the ones the vendored node definitions use, and there are exactly
     nine parameter types, eight linkable-input types and six output types. This script prints the three lines quoted below:
     ```
     PYTHONPATH="$PWD/analysis" .venv/bin/python -P -s - <<'PY'
     import re, pathlib, collections
     root = pathlib.Path("third_party/cycles/fragments")
     inp = re.compile(r'SOCKET_IN_(BOOLEAN|INT|UINT|UINT64|FLOAT|COLOR|VECTOR|POINT|NORMAL|POINT2|STRING|ENUM|TRANSFORM|NODE|CLOSURE)\s*\(')
     out = re.compile(r'SOCKET_OUT_(BOOLEAN|INT|UINT|UINT64|FLOAT|COLOR|VECTOR|POINT|NORMAL|POINT2|STRING|ENUM|TRANSFORM|NODE|CLOSURE)\s*\(')
     par = re.compile(r'SOCKET_(BOOLEAN|INT|UINT|UINT64|FLOAT|COLOR|VECTOR|POINT|NORMAL|POINT2|STRING|ENUM|TRANSFORM|NODE)\s*\(')
     i, o, p = collections.Counter(), collections.Counter(), collections.Counter()
     for f in sorted(root.rglob("*.inc")):
         t = f.read_text()
         i.update(inp.findall(t)); o.update(out.findall(t)); p.update(par.findall(t))
     print("linkable inputs:", dict(sorted(i.items())))
     print("outputs:", dict(sorted(o.items())))
     print("parameters:", dict(sorted(p.items())))
     PY
     ```
     ```
     linkable inputs: {'BOOLEAN': 1, 'CLOSURE': 6, 'COLOR': 17, 'FLOAT': 91, 'INT': 1, 'NORMAL': 9, 'POINT': 8, 'VECTOR': 8}
     outputs: {'CLOSURE': 10, 'COLOR': 10, 'FLOAT': 21, 'NORMAL': 7, 'POINT': 8, 'VECTOR': 4}
     parameters: {'BOOLEAN': 8, 'COLOR': 1, 'ENUM': 27, 'FLOAT': 3, 'INT': 3, 'POINT': 1, 'STRING': 1, 'TRANSFORM': 1, 'VECTOR': 4}
     ```
     The scan covers `third_party/cycles/fragments/**/*.inc`, which is where the committed node definitions live
     (`VENDORED.toml`'s `fragment` entries, e.g. `scene/shader_nodes_cpp/node_define/MathNode` at `:1880-1886`).
     Consequences this card implements: the parameters a caller may set are the nine types of the third line; the
     linkable inputs are the eight of the first line, of which `CLOSURE` has no value form (`SOCKET_IN_CLOSURE`
     registers `default_value = nullptr`, `graph/node_type.h:389-398`) and is supplied by a link only, so seven take a
     value; the outputs a link may read are the six of the second line. `UINT`, `UINT64`, `POINT2` and `NODE` appear in
     neither the parameter nor the linkable-input line, so the binding rejects them as an unsupported socket type
     rather than guessing a conversion.
2. `src/blender/_painterly.pyi`: the two declarations of `## Interface` after `add_material` (`:50-54`), and reword `:49`
   from "M6 adds add_shader (SVM node graphs)" to "… and `add_shader` (SVM node graphs)". No other line of the file
   changes: `set_integrator`, `get_integrator` and `set_background` keep their text.
3. `src/blender/python.cpp`, the conversion helpers, in the anonymous namespace beside `lobe_kind_from_python`
   (`:534`). Each raises through the existing helpers, so a message reads like the other Scene methods' messages.
   ```cpp
   /* The value of one node parameter (BRIEF.md:52-55: a parameter is a socket without a ShaderInput, set by member
    * name, an enum by its NodeEnum name). The nine socket types are the ones the committed node definitions use
    * (step 1's scan); anything else is a socket this API has no Python form for. */
   void set_parameter_from_python(ShaderNode &node, const SocketType &socket, nb::handle value,
                                  const std::string &what);

   /* The value of one unlinked linkable input, by UI name (BRIEF.md:54). */
   void set_linkable_input_from_python(ShaderNode &node, const std::string &ui_name, nb::handle value,
                                       const std::string &what);

   /* The graph of one `Scene.add_shader` call: `nodes` and `links` exactly as the pyi describes them
    * (BRIEF.md:200-202). Throws before anything is added to the scene, so a rejected call adds no shader. */
   std::unique_ptr<ShaderGraph> shader_graph_from_python(nb::handle nodes, nb::handle links);
   ```
   - `set_parameter_from_python` dispatches on `socket.type`:
     - `BOOLEAN`: `PyBool_Check(value.ptr())` first — a bool is not an int here, as `as_integer` already rules
       (`python.cpp:318-320`) — and a non-bool raises `TypeError` through `throw_wrong_type` (`:273`). The check is
       explicit because `nb::cast<bool>` would raise nanobind's `cast_error`, which is `std::bad_cast`
       (`nanobind/include/nanobind/nb_error.h:95`) and which the default translator turns into `RuntimeError`, not
       `TypeError` (`nanobind/src/nb_internals.cpp:155-174`). Then `node.set(socket, value.ptr() == Py_True)`
       (`graph/node.h:96`).
     - `INT`: `node.set(socket, int(as_integer(value, what)))` (`node.h:97`, `python.cpp:314`).
     - `FLOAT`: `node.set(socket, float(as_real(value, what)))` (`node.h:100`, `python.cpp:301`). The socket stores its
       float32 value, as `set_integrator` does (`python.cpp:408-411`).
     - `COLOR`, `VECTOR`, `POINT`: a 3-sequence of reals through the same conversion `double3_from_python` uses
       (`python.cpp:589-598`), as `make_float3(float(x), float(y), float(z))`, then `node.set(socket, value)`
       (`node.h:102`; `is_socket_float3` at `node.cpp:39-43` is the debug assert, and all three are float3 sockets).
     - `STRING`: `PyUnicode_Check(value.ptr())` first, for the reason above, else `TypeError`; then
       `node.set(socket, ustring(nb::cast<std::string>(value)))` (`node.h:104`).
     - `ENUM`: the value must be a string that `socket.enum_values->exists(ustring(name))` accepts
       (`graph/node_enum.h:29-32`); otherwise raise `ValueError` naming it *before* the set, because
       `Node::set(const SocketType &, ustring)` calls `assert(0)` for an unknown name (`graph/node.cpp:105-113`) and
       sets nothing in a release build. Then `node.set(socket, ustring(name))`, which stores the `NodeEnum` value.
     - `TRANSFORM`: three or four rows of four reals, row-major, through `make_transform`
       (`util/transform.h:194-223`); `Transform` is three `float4` rows (`:52-65`), so a 4x4's last row is ignored and
       a 3x4 is the same twelve numbers. This is this card's choice of a Python form for a Transform parameter, because
       the brief fixes no form (see `## Open for Opus` 3).
     - anything else: `ValueError` "<what>: socket type <SocketType::type_name> has no Python form"
       (`SocketType::type_name`, `graph/node_type.cpp:104-128`), the same shape as `set_integrator`'s unsupported-type
       case (`python.cpp:436-437`).
   - `set_linkable_input_from_python` finds the input by UI name with `node.input(ustring(ui_name))`
     (`scene/shader_graph.cpp:115-124`); `nullptr` → `ValueError` naming the input and its node. It then sets through
     `node.set(input->socket_type, …)` (`graph/node.h:96-104`), which is what `ShaderInput::set` does
     (`scene/shader_graph.h:105-116`), for the same nine types minus `ENUM` and `TRANSFORM`; a `CLOSURE` input raises
     `ValueError` naming it and saying a closure comes from a link.
   - `shader_graph_from_python`:
     1. `nodes` must be a sequence; for each entry a 3-sequence of (type name, parameters dict, defaults dict), else
        `TypeError`. The type name is a string, `NodeType::find(ustring(name))` (`graph/node_type.cpp:282-289`); a null
        type → `ValueError` naming it. `graph->create_node(type)` (`scene/shader_graph.h:383-390`).
     2. the parameters dict: each key by `type->find_input(ustring(key))` (`graph/node_type.cpp:186-196`); a null
        socket, or one whose `flags & SocketType::LINKABLE` is set (`graph/node_type.h:64`), → `ValueError` naming it —
        a linkable input belongs in the third element, and a parameter has no `ShaderInput` (T6.4, "Socket naming").
     3. the defaults dict: each key by `node->input(ustring(key))`; a null input → `ValueError` naming it.
     4. `links`: a 4-sequence of (from node, output UI name, to node, input UI name); the from node must index the nodes
        created in 1, the to node is -1 for `graph->output()` (`scene/shader_graph.cpp:243-246`) or an index; either out
        of range → `ValueError` naming the index. `from->output(ustring(name))` and `to->input(ustring(name))`
        (`:93-135`) must be non-null, else `ValueError` naming the socket and its node. Then
        `graph->connect(from_out, to_in)` (`:248`), which inserts Cycles' own conversion node when the two types differ
        (`:258-298`) — the same conversion `add_node`'s graph gets in Cycles, so a caller may link a float to a colour.
   - A duplicate link is not an error: `ShaderGraph::connect` logs a warning and keeps the first link
     (`scene/shader_graph.cpp:253-256`), and this card keeps Cycles' behaviour (see `## Open for Opus` 4).
4. `src/blender/python.cpp`, the two bindings on the `Scene` class, after `add_material` (`:699-720`):
   ```cpp
   .def(
       "add_shader",
       [](PainterlyScene &self, nb::object nodes, nb::object links) {
         /* The whole graph is built and validated before the scene sees it, so a rejected call adds no shader
          * (BRIEF.md:204-205, and the dense indices of pyi:7). */
         return self.add_shader(shader_graph_from_python(nodes, links));
       },
       nb::arg("nodes"),
       nb::arg("links"))
   .def(
       "add_node_material",
       [](PainterlyScene &self, const int shader) { return self.add_node_material(shader); },
       nb::arg("shader"))
   ```
   - `nb::object` for the two list arguments, as `add_material` takes `nb::object lobes` (`:699-700`): the pyi types
     them, the binding validates them, and `test_api_contract`'s signature check reads only the parameter names and
     defaults (`tests/core/test_api_contract.py:141-168`).
   - A shader index out of range is B2's error. If B2 throws `std::invalid_argument`, nanobind maps it to `ValueError`
     (`nanobind/src/nb_internals.cpp:162-163`, the default exception translator), which is what the pyi's
     "unknown … names raise ValueError" family of messages reads like.
5. `src/test/test_shader_api.cpp`, the three doctests `## Acceptance` 3 counts. Its header comment says what it is: the
   C++ half of BRIEF.md:207, the graph Cycles' own API builds, so that the Python half in
   `tests/core/test_shader_graph_api.py` has a reference that is not itself Python.
   ```cpp
   /* SPDX-FileCopyrightText: 2026 The Painterly Authors
    * SPDX-License-Identifier: GPL-3.0-or-later */

   // Card M6b B6: the graph the shader-graph API builds, built here in C++ with Cycles' own calls
   // (BRIEF.md:207). Every comparison is exact: two renders are compared with memcmp, so -0.0 and +0.0
   // differ, and no tolerance appears. The Python test of tests/core/test_shader_graph_api.py compares
   // the graph it builds through Scene.add_shader with the same constant equivalent, so the two tests
   // together are BRIEF.md:207's "renders bit for bit like the same graph built in C++".
   ```
   - The file's unnamed namespace holds the helpers of `test_cycles_svm_closures.cpp` that it needs, copied with their
     file:line: `make_scene` `:47-53`, `shader_manager` `:55-58`, `create_node_by_name` `:61-66`, `add_surface`
     `:100-107`, `parameter` (`test_cycles_shader_graph.cpp:37-42`), the render loop of `test_session.cpp:186-207`, and
     `bit_identical` (`test_path_trace.cpp:95-103`). `painterly_cycles_shader_node_types()` runs once
     before the first `NodeType::find` (`test_cycles_svm_closures.cpp:47-53`; TQ.4 F11).
   - **The scene of all three cases.** One `PainterlyScene`, `set_camera_smallpaint(SIDE, SIDE)` with
     `SIDE = 8`, and one plane `add_plane(make_double3(0.0, 0.0, 1.0), 4.0, material, -1)`, i.e. z = -4, the plane
     `tests/core/test_api_contract.py:459` uses. The smallpaint camera's rays leave the origin and reach z = -4 at every
     pixel (`kernel/camera/camera.h:57-88`, `:92-99`), so every pixel of both renders shades the material. The integrator
     keeps its defaults, so both sides run the same knobs and the comparison differs only in the material.
   - **The graph, built in C++** (the reference of BRIEF.md:207):
     ```cpp
     unique_ptr<ShaderGraph> graph = make_unique<ShaderGraph>();
     ShaderNode *math = create_node_by_name(*graph, "math");
     ShaderNode *emission = create_node_by_name(*graph, "emission");
     math->set(parameter(math, "math_type"), ustring("multiply"));
     math->set(parameter(math, "use_clamp"), false);
     math->input("Value1")->set(0.5f);
     math->input("Value2")->set(0.5f);
     emission->input("Color")->set(make_float3(1.0f));
     graph->connect(math->output("Value"), emission->input("Strength"));
     graph->connect(emission->output("Emission"), graph->output()->input("Surface"));
     ```
     `"math"` and `"emission"` are the `NodeType::add` names of `MathNode.inc:3` and `EmissionNode.inc:3`; `"Value1"`,
     `"Value2"`, `"Value"`, `"Color"`, `"Strength"`, `"Emission"` and `"Surface"` are the UI names of
     `MathNode.inc:51-55`, `EmissionNode.inc:5-10` and `OutputNode.inc:5`; `"math_type"` and `"use_clamp"` are the
     member names of `MathNode.inc:47-49`. `create_node_by_name` takes a `ShaderGraph &`
     (`test_cycles_svm_closures.cpp:61-66`) and `add_shader` a `unique_ptr` (B4 step 9's call shape), hence the
     `unique_ptr`. The graph goes to the scene as B2's two calls take it:
     `const int shader = scene.add_shader(std::move(graph));` then `const int material =
     scene.add_node_material(shader)`, and the constant side is a second `PainterlyScene` whose only plane carries
     `add_material({lobe}, make_double3(0.25))`.
   - **Its constant equivalent, derived.** Emission's colour (1, 1, 1) times its Strength, which the Math node's
     `multiply` of 0.5 by 0.5 gives as 0.25; no closure reaches the collector, so it gives one `LOBE_DIFFUSE` of weight
     0 (`collect.h:205-210`). Every input is a constant, so `ShaderGraph::finalize` folds the graph on the host
     (`docs/handoff/drafts/M6a/T6.5-svm-compiler.md:163-168`); the folded program's emission is the same 0.25 and it
     still allocates no closure, so the derived values hold whether the collector reads a folded shader or an unfolded
     one, and the cases below do not depend on which. Both factors and the product are powers of two, so float32 holds
     them exactly and `double(float)` is the literal: the material is `add_material({lobe}, make_double3(0.25))` with
     `lobe = {LOBE_DIFFUSE, make_double3(0.0), 0.0}`. B4's lobe table derives the same two values for an Emission node
     (`B4-svm-trace-pixel.md` step 9, the "emission" row, from `test_cycles_svm_closures.cpp:536-542`).
   - **The three cases:**
     1. `"shader graph api: the C++ graph renders bit-identically to its constant equivalent"`: two `PainterlyScene`s,
        one on the node material and one on the constant equivalent, each rendered as `render_directly` does
        (`test_session.cpp:186-207`), then `CHECK(bit_identical(a, b))` (`test_path_trace.cpp:95-103`), which compares
        `combined` and `k_consumed` by `memcmp`. `REQUIRE` a non-zero sum first, so a scene that renders nothing cannot
        pass.
     2. `"shader graph api: the collector gives the derived lobe list and emission"`: `scene.device_update(ds)`, then
        the primary hit of pixel (row 4, col 4): `painterly_camera_generate_ray(kg, 4, 4, 0, true)`
        (`kernel/camera/camera.h:93`), `painterly_scene_intersect` (`kernel/bvh/bvh.h:26`), `ray.o = ray.o + ray.d *
        isect.t` as `path.h:89-95` does, and B4's `painterly_hit_material` (`kernel/svm/hit_material.h`) with
        `kg->materials[material]`. `CHECK` its `num_lobes == 1`, `lobes[0].kind == LOBE_DIFFUSE`, `lobes[0].weight.x ==
        0.0` and the same for `y` and `z`, and `emission.x == 0.25` and the same for `y` and `z`.
     3. `"shader graph api: the graph holds the names the API passes"`: on the `ShaderGraph` step 5 built,
        `CHECK(math->type == NodeType::find(ustring("math")))`, the two parameter values through the typed getters
        (`static_cast<const MathNode *>(math)->get_math_type() == NODE_MATH_MULTIPLY` and `get_use_clamp()` is false),
        and that each link is the one the UI names name (`emission->input("Strength")->link == math->output("Value")`,
        `graph.output()->input("Surface")->link == emission->output("Emission")`).
   - `src/test/CMakeLists.txt`: `target_sources(painterly_tests PRIVATE test_shader_api.cpp)` in a block after the T6.8
     one (`:97-99`), with a comment naming M6b B6. No `target_link_libraries`: `:49-50` already links `cycles_svm`,
     `cycles_scene`, `painterly_scene` and `painterly_integrator`, which this file's includes need.
6. `tests/core/test_shader_graph_api.py`, the fifteen tests `## Acceptance` 4 counts, in the style of
   `tests/core/test_api_contract.py`: a docstring that names each test's mutation, exact comparisons only, and no
   hand-picked tolerance. It imports `_painterly` and `numpy` and nothing else; `tests/conftest.py:31-34` puts the built
   module on `sys.path`.
   - The scene helper: `_painterly.Scene()`, `set_camera_smallpaint(SIDE, SIDE)` with `SIDE = 8`, one plane
     `add_plane((0.0, 0.0, 1.0), 4.0, material, -1)`, and `_render` as `test_api_contract.py:186-192` writes it. The
     graph lists are the same nodes and links as step 5's C++ graph:
     ```python
     NODES = [
         ("math", {"math_type": "multiply", "use_clamp": False}, {"Value1": 0.5, "Value2": 0.5}),
         ("emission", {}, {"Color": (1.0, 1.0, 1.0)}),
     ]
     LINKS = [(0, "Value", 1, "Strength"), (1, "Emission", -1, "Surface")]
     ```
   - `test_a_python_graph_renders_bit_identically_to_its_constant_equivalent`: the render of
     `add_node_material(add_shader(NODES, LINKS))` against the render of the constant material of step 5
     (`add_material([("diffuse", (0.0, 0.0, 0.0), 0.0)], emission=(0.25, 0.25, 0.25))`), compared with
     `np.array_equal` on `combined` and `k_consumed` and with the same non-zero premise.
   - `test_add_shader_returns_dense_indices` and `test_add_node_material_returns_dense_indices`: three calls each, and
     the returns are `[0, 1, 2]` — `pyi:7`'s "dense, starting at 0", which is B2's `size() - 1`.
   - The eleven rejection tests, each with the exception it must raise:
     - `test_an_unknown_node_type_raises_value_error_naming_it`: `"diffuse"`, a Blender idname and not a Cycles type
       name (B8's table maps it); the message contains `diffuse`.
     - `test_an_unknown_parameter_raises_value_error_naming_it`: `{"Type": "multiply"}` on the math node — `"Type"` is
       the UI name of a parameter, and `NodeType::find_input` matches member names only (`node_type.cpp:186-196`); the
       message contains `Type`.
     - `test_a_linkable_input_in_the_parameters_raises_value_error_naming_it`: `{"Value1": 0.5}` in the parameters;
       the message contains `Value1`.
     - `test_an_unknown_linkable_input_raises_value_error_naming_it`: `{"value1": 0.5}` in the defaults — the member
       name, not the UI name; the message contains `value1`.
     - `test_an_unknown_enum_name_raises_value_error_naming_it`: `{"math_type": "multiplied"}`; the message contains
       `multiplied`.
     - `test_a_wrong_parameter_type_raises_type_error`: `{"use_clamp": "yes"}`; `TypeError`.
     - `test_a_wrong_linkable_default_type_raises_type_error`: `{"Value1": "half"}`; `TypeError`.
     - `test_an_unknown_output_in_a_link_raises_value_error_naming_it`: `(0, "value", 1, "Strength")`; the message
       contains `value`.
     - `test_an_unknown_input_in_a_link_raises_value_error_naming_it`: `(0, "Value", 1, "strength")`; the message
       contains `strength`.
     - `test_a_link_index_out_of_range_raises_value_error_naming_it`: `(0, "Value", 2, "Strength")`; the message
       contains `2`.
     - `test_a_malformed_node_or_link_raises_type_error`: a node that is a 2-tuple, and a link that is a 3-tuple;
       `TypeError` for each.
     - `test_a_rejected_add_shader_adds_no_shader`: after each of the rejections above, the next accepted
       `add_shader(NODES, LINKS)` still returns 0, so the failed call added nothing.
   - That is 2 index tests + 1 render test + 11 rejection tests + the no-shader-after-rejection test = 15, and
     `## Acceptance` 4 states the same count.
   - Every expected value is derived above (step 5's dyadic emission and the collector's zero-closure fallback) or is a
     name read out of `third_party/cycles/fragments/**/*.inc` (step 1's scan and step 5's citations). No tolerance
     appears: the render comparison is `np.array_equal`, which is exact for the float64 sums the core writes
     (`integrator/buffers.h:21-22`).
7. `make format`, then every acceptance command.

## Acceptance
Run every command from the repository root; the queue translates them with BACKLOG.md's table (`make check` → `CHECK`,
`build/dev` → `build/q`, `.venv/bin/<tool>` → `MAIN/.venv/bin/<tool>`, `python -I` → `PYTHONPATH="$PWD/analysis" … -P -s`).
1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and the audit's
   `RESULT: PASS` line.
2. `make audit` prints `RESULT: PASS`: no new exported symbol (the helpers are in `python.cpp`'s anonymous namespace,
   `:80-997`, and `exports.map:1` still exports `PyInit__painterly` alone) and no new dependency (no CMake file adds a
   library).
3. `build/dev/src/test/painterly_tests --test-case='shader graph api*'` exits 0 and prints
   `test cases: 3 | 3 passed | 0 failed` — the three cases of step 5.
4. `.venv/bin/python -m pytest -q tests/core/test_shader_graph_api.py` prints `15 passed` — the fifteen tests of step 6.
5. `.venv/bin/python -m pytest -q tests/core/test_api_contract.py` prints `31 passed`: the file unchanged, as
   BRIEF.md:209 asks. The coverage is the file's own: `_pyi_public_api()` (`:65-82`) walks the pyi's public names, so
   `Scene.add_shader` and `Scene.add_node_material` are in it as soon as the pyi declares them, and
   `test_every_public_name_and_parameter_matches_the_pyi` (`:141`) and `test_every_public_default_matches_the_pyi`
   (`:151`) then compare their parameter names and defaults with the module's. Neither has a default, so the second test
   compares nothing for them and passes. The count `31` is the file's: 31 `test_` functions, none parametrized (a
   `ast` walk of the file counts 31).
6. `.venv/bin/python -m pytest -q -m slow tests/core/test_oracle_parity.py tests/core/test_triangle_path.py` prints
   `2 passed, 53 deselected`: the two slow tests, unchanged. The counts are the files' own:
   `test_oracle_parity.py` holds five `test_` functions (`:125`, `:138`, `:162`, `:320`, `:367`), of which `:320` is
   parametrized by 12 `DESIGN` entries × 4 `CORE_CONFIGS` = 48 items, so 4 + 48 = 52 items; `test_triangle_path.py`
   holds three (`:156`, `:183`, `:273`), so 3. 52 + 3 = 55 items, one `@pytest.mark.slow` in each file, so the `-m slow`
   run selects 2 and reports `55 - 2 = 53` deselected.
7. `git status --porcelain` lists only the two Create paths and the three Modify paths above.

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- in `shader_graph_from_python`, skip the `ENUM` existence check → `test_an_unknown_enum_name_raises_value_error_naming_it`
  fails in a release build (nothing is set and no exception is raised) and `painterly_tests` aborts in a debug one
  (`graph/node.cpp:111`);
- find a parameter with `node->input(ustring(key))` instead of `type->find_input` → the same test fails, because a
  parameter has no `ShaderInput` and the key is then reported as an unknown socket;
- find a linkable default with `type->find_input` instead of `node->input` → `{"value1": 0.5}` is accepted (the member
  name matches) and `test_an_unknown_linkable_input_raises_value_error_naming_it` fails;
- call `self.add_shader(...)` before the graph is validated → `test_a_rejected_add_shader_adds_no_shader` fails;
- map to-node `-1` to node 0 instead of `graph->output()` → `test_an_unknown_input_in_a_link_raises_value_error_naming_it`
  still passes, but the render test fails, because `Surface` does not exist on a Math node;
- make the constant equivalent `emission=(0.5, 0.5, 0.5)` → the render test fails on `combined`;
- make `add_node_material` return `shader` instead of the material index (B2's) → the dense-index test fails.

Report: the doctest and pytest counts, the audit line, and every mutation you ran with its first failing check.

## Commit
`B6: the _painterly shader-graph API`

## Open for Opus
1. **The brief's `Needs: B2, M3 T3.15` omits B4.** BRIEF.md:210 names B2 and T3.15, but the acceptance's first item,
   "a graph built from Python renders bit for bit like the same graph built in C++" (BRIEF.md:207), renders a node
   material, and only B4's `painterly_hit_material` evaluates one
   (`src/painterly/kernel/integrator/path.h`, B4 step 3): until B4 lands, a node material's `cycles_shader` is set by
   B2's device update and nothing reads it, so both sides of the comparison render the material's constant fields and
   the test would pass vacuously. This card's header therefore says `Depends on: B2, B4, T3.15` and step 1 checks B4.
   The options: (a) keep it (this card); (b) keep the brief's order and replace the render test with a comparison of the
   two materials' collector output only, which loses the "renders" of BRIEF.md:207 and duplicates B4's own acceptance;
   (c) run B6 before B4 and let the render test fail until B4 lands, which the queue's dependency rule does not allow.
2. **How the brief's one render sentence is split across two languages.** BRIEF.md:207 asks for one comparison between a
   Python-built and a C++-built graph. This card cannot make it in one process: `painterly_tests` is C++ and has no
   Python, and a Python test cannot call Cycles' `create_node`/`connect` (they are not in the module's API, and this card
   adds no API for them). So the sentence is proved transitively, by two exact comparisons against the same derived
   constant material: the C++ doctest (step 5, case 1) and the Python test (step 6). The options: (a) keep it (this
   card); (b) have the doctest write its render to a file in the build directory and the pytest compare against it,
   which makes the pytest depend on `ctest` having run first — `make test` runs `test-cpp` before `test-py`
   (`Makefile:66`), so it would work but would silently compare against a stale file when run alone; (c) add a C++ graph
   builder to the module's API, which widens the pyi beyond BRIEF.md:200-203. This card takes (a).
3. **The Python form of a `Transform` parameter.** The brief types a parameter's value `object` (BRIEF.md:200) and the
   vendored definitions use `SOCKET_TRANSFORM` once (step 1's scan: `TextureCoordinateNode.ob_tfm`,
   `TextureCoordinateNode.inc:7`). This card takes a row-major nested sequence of three or four rows of four reals and
   builds `make_transform`'s twelve floats (`util/transform.h:194-223`), ignoring a 4x4's fourth row. The options:
   (a) keep it; (b) accept only 3x4, as `add_object` does for a 3x4-or-4x4 transform (`pyi:83-88`,
   `python.cpp:624-642`), which would reject a caller's `matrix_world`; (c) refuse `TRANSFORM` parameters with a
   `ValueError`, which makes a Texture Coordinate node with a transform unreachable from Python until a later card. No
   test of this card sets one, so all three pass.
4. **A duplicate link.** `ShaderGraph::connect` keeps the first link and logs a warning
   (`scene/shader_graph.cpp:253-256`), and this card keeps Cycles' behaviour rather than raising. The options: (a) keep
   it; (b) raise `ValueError` naming the input, which makes a duplicate link an error the caller sees — Cycles' own
   graph, and Blender's, tolerate it, so a Blender sync that emits a duplicate would then fail the export (B8's caller).
   This card takes (a) and no test covers it.
5. **`clear()` and the shader list.** `PainterlyScene::clear()` empties the materials, the geometry, the camera, the
   background and the integrator (`scene/scene.cpp:21-33`), and the pyi's `clear` comment promises every list. B2's scope
   (BRIEF.md:114-136) does not say whether the shader list it adds is cleared too. This card's
   `test_add_shader_returns_dense_indices` does not call `clear()`, so it does not depend on the answer; a caller would.
   The options: (a) B2 clears the shaders in `clear()`; (b) a later card adds it; (c) this card adds the two lines to
   `scene.cpp`, which is outside its brief's scope. Please state which, in B2's card.
6. **What `add_node_material` puts in the material's constant fields.** B4's `## Open for Opus` 8 asks the same question
   from the path's side: this card's render test only needs the node material's lobes and emission to come from the SVM
   at the hit, and it never reads the material's constant lobes. If Opus has B2 fill them with the graph's folded value,
   this card's tests still pass and B4's emission premise check reports the value instead of asserting zero.
7. **The value forms the brief leaves to the card.** BRIEF.md:200-202 gives the two lists' tuple shapes and says each
   node is "(Cycles type name, parameters by member name, linkable input defaults by UI name)"; it does not say what a
   `dict[str, object]` value may be. Step 1's scan settles that from the code: the nine parameter types and the seven
   value-taking linkable types the committed node definitions use, a `float3` for `COLOR`/`VECTOR`/`POINT` (three reals),
   a `str` for `STRING`, a `bool` for `BOOLEAN`, and a `Transform` as in `## Open for Opus` 3. If Opus wants a narrower
   or a wider set — for example accepting an `int` where a `FLOAT` is expected, which `as_real` already does — only step
   3's dispatch and the eleven rejection tests move; the pyi's `object` type does not. BRIEF.md:204-205 says a wrong value
   type raises `TypeError`, and the enum-name case is a `ValueError` because it is a name, not a type; step 3 and step 6
   state both, and the enum case is the one the brief's "an unknown … enum name raises ValueError" names explicitly.
8. **Parallel-safe: no.** B8 binds `Scene.set_background_shader` in the same two files this card changes
   (BRIEF.md:228-229: "CONTRACT `_painterly.pyi`, `python.cpp`"), so the two cards cannot run at the same time. This card
   is written to be merged first: its two methods go after `add_material` (`pyi:50-54`, `python.cpp:697-720`), and B8's
   goes after them.
