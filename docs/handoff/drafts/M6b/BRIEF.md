# M6b brief: node materials inside the painterly kernel

Opus, 2026-10-25, plan row M6b.1. This brief fixes M6b's card list, the interface names and the acceptance of each card.
The draft cards (`docs/handoff/drafts/M6b/<id>-<slug>.md`, template `docs/tasks/README.md`) expand it. Where a draft
needs a decision this brief does not make, it says so in a section "Open for Opus" and does not decide it.

Inputs:
- gate G2 passed (experiment 011 Conclusion, `d92f195`): M6b builds on `cycles_svm`, `cycles_scene` and
  `PainterlyShaderManager`;
- the M6a cards' "For later cards" sections (`docs/handoff/drafts/M6a/T6.1`-`T6.8`);
- `docs/handoff/research/cycles_svm_report.md` §8;
- SPEC §2-§6 and §9;
- decision D4: v1 has the core six node batches, 1, 5, 6, 10, 11 and 12.

## 1. Decisions that bind every card

1. **Cycles globals beside painterly's.** `PainterlyGlobalsCPU` (CONTRACT `src/painterly/kernel/globals.h`) gains one
   member, `const KernelGlobalsCPU *cycles`.
   - `PainterlyDeviceScene` owns the `KernelGlobalsCPU` and every array it points to.
   - The kernel passes `kg->cycles` wherever Cycles code takes `KernelGlobals`.
   - The session's by-value snapshot of `globals()` copies only the pointer, which is valid while the device scene lives.
     The device scene is never updated during a render (session.cpp:54, :114).
2. **Who links what.** `painterly_kernel` links `cycles_svm`, which links `cycles_kernel`; `painterly_scene` links
   `cycles_scene`. Every target whose sources include a Cycles `kernel/` header therefore gets `cycles_kernel`'s
   definition set and its INTERFACE `-fno-strict-aliasing` (T6.1:80-85, T6.3:1559).
   - The first production consumer adds, in its own target, one function that returns the existing
     `painterly_kernel_layout_record()` (`src/test/cycles_kernel_layout_probe.h:46`), and one comparison in
     `test_cycles_kernel_layout.cpp` (T6.1:599-600).
   - `make audit` stays clean: no new exported symbol, no new dependency.
3. **A material is constant or a node material.** `KernelPainterlyMaterial::svm_offset` (CONTRACT
   `src/painterly/kernel/types.h:101-106`) becomes `int cycles_shader`: the Cycles shader id, `sd->shader`, or -1 for
   constant lobes, today's path. It is not an offset: the SVM starts at word
   `id * (1 + sizeof(SVMNodeShaderJump) / sizeof(uint))` of `svm_nodes` (`svm_eval_nodes_head.inc:13`;
   `shader_manager.h:181`, `:202`). The rename touches `device_scene.cpp:120` and the field's readers.
   - A node material's lobes and emission come from `painterly_svm_collect()` per hit.
   - A constant material is rendered exactly as today: its bits, K and images do not change. The parity tests T3.16 and
     T3.17 are the check.
4. **The Cycles host scene lives inside `PainterlyScene`,** as `std::unique_ptr<Scene> cycles_`: the shim `Scene`, with
   `shader_manager` a `PainterlyShaderManager`, its `shaders`, and (batch 10) its `image_manager`.
   - `PainterlyScene::device_update(PainterlyDeviceScene &) const` stays `const`. It runs the shader manager on
     `*cycles_`, because graph finalization and shader numbering are a cache that Cycles itself fills at the first
     device update.
   - The order is T6.7's: `device_update_pre`, `device_update_post`, `device_update_lookup_tables`, then
     `PainterlyShaderManager::bind_kernel_globals`, then the arrays the device scene binds itself. `bind_kernel_globals`
     copies the whole `KernelData` (`shader_manager.h:151`), so `kernel_data.max_closures` and `kernel_data.cam` are
     written after it.
   - Cycles compiles only referenced shaders (`compile_type.inc:69`): `add_node_material` and
     `set_background_shader` call `Shader::reference()`.
   - The shader manager writes into `Scene::dscene`, which `device_update_post` clears first (`shader_manager.h:166`).
     To keep the strong guarantee of `device_scene.cpp:94-97`, the update runs on a scratch `DeviceScene` and moves
     its arrays into the device scene at the existing commit point (`:289-303`).
5. **Socket names** are T6.4's rule (T6.4:1030-1043):
   - node types by Cycles type name;
   - links and linkable input defaults by UI name;
   - parameters by member name, with enums by `NodeEnum` name.
   The first production caller calls `painterly_cycles_shader_node_types()` once before its first `NodeType::find`
   (T6.4:861).
6. **ShaderData from painterly hits** is written by painterly code, not by vendoring `geom/shader_data.h`,
   `triangle_intersect.h` or `surface_shader.h`. It fills exactly the fields the vendored node and closure code reads, as
   Cycles' setup would. For an analytic sphere or plane there is no Cycles object or primitive:
   - `object = OBJECT_NONE`, `prim = PRIM_NONE`, `type = PRIMITIVE_NONE`, `u = v = 0`;
   - the nodes then compute what Cycles' code computes for such a point: object coordinates equal world coordinates, and
     there are no attributes.
   Painterly has no ray differentials: `dP`, `dI`, `du` and `dv` are zero, `time` is 0, and `ray_length` is `t * |d|`.
   The SVM draws no random number (`lcg_state = 0`), so K is untouched; only a chosen diffuse lobe draws from K (SPEC §2,
   §6).
7. **Per-hit lobes are sampled exactly as SPEC §6 says.** B4 changes `painterly_select_lobe` (closure/lobe.h:33-36,
   which takes `(kg, material, row, col, pass, depth)` today; callers `path.h:113`, `test_path.cpp:525-540`) to take
   the lobe array and its count instead of the material. Its arithmetic does not change. The constant path passes
   `kg->lobes + m.lobe_offset` and `m.num_lobes`; a node material passes the collector's `lobes` and `num_lobes`.
   - `two_sided` keeps its rule: diffuse, mirror and transparent lobes get the normal flipped to the ray, and glass gets
     the authored normal.
   - The collector's `sd->N` is the authored, unflipped normal, and `SD_BACKFACING` is clear (collect.h:11-23).
   - Closure normals (Bump, Normal Map) are outside v1: the lobes carry no normal.
8. **No new knob without a reason.** A painterly constant that M6b introduces is a reflected socket on
   `PainterlyIntegrator` (plan.md:142). Cycles' own values (feature masks, `max_closures = MAX_CLOSURE`) are definitions
   and cite their origin.
9. **Expected values are evidence, not targets** (AGENTS.md). Every acceptance below is an exact equality or a rule whose
   statistic is derived or measured from Cycles alone, never tuned on painterly's output.

## 2. Cards

Each card lists Create/Modify paths in its draft. "Needs" repeats the plan's dependencies. CONTRACT text is Opus's:
the draft quotes this brief's interface, and the approving review writes the contract header before dispatch
(plan.md:229).

### B1. Kernel globals and the build
- Scope: decision 1 and decision 2.
  - `PainterlyDeviceScene` gains a `KernelGlobalsCPU`, bound empty (zero shaders, zero objects): `kernel_data` has
    `max_closures = MAX_CLOSURE`, and every array has width 0.
  - Link `painterly_kernel` -> `cycles_svm` and `painterly_scene` -> `cycles_scene`.
  - Add the layout record for the new consumer.
- Interface: `const KernelGlobalsCPU *PainterlyGlobalsCPU::cycles` (CONTRACT `globals.h`), and
  `const KernelGlobalsCPU &PainterlyDeviceScene::cycles_globals() const`.
- Acceptance:
  - the queue's CHECK (`make check` with the R12 knobs) and `make audit` pass;
  - a doctest shows that a device-updated scene's `globals().cycles` points at the device scene's `KernelGlobalsCPU`
    with the bound widths;
  - the layout comparison passes;
  - the slow parity tests `tests/core/test_oracle_parity.py` and `test_triangle_path.py` pass unchanged.
- Needs: M6a T6.8.

### B2. The shader manager in `PainterlyScene::device_update`
- Scope: decision 4. `PainterlyScene::add_shader(std::unique_ptr<ShaderGraph>) -> int` returns a shader index.
  - `add_node_material(int shader) -> int` returns a material index.
  - The device update compiles every referenced shader, fills the jump table, `KernelShader` flags and the lookup
    tables, sets each node material's `cycles_shader` to its shader id, and binds them into `cycles_globals()`.
  - Constant materials keep `cycles_shader = -1`.
- Acceptance (doctests on scenes built in C++):
  - for a node material with one Diffuse BSDF of a dyadic colour, `cycles_shader` equals the shader id;
  - `svm_nodes[cycles_shader * jump_node_size]` is that shader's `NODE_SHADER_JUMP`;
  - `kernel_data.tables` points into the bound `lookup_table`;
  - two node materials share one jump table;
  - a device update that throws partway (the existing throw points of `device_scene.cpp`) leaves the previous device
    scene bit for bit unchanged, its Cycles arrays included (strong guarantee);
  - a scene of constant materials produces byte-identical painterly arrays to today's.
- Needs: B1.

### B3. ShaderData from painterly hits, and the mesh's UVs
- Scope: decision 6.
  - `painterly_svm_shader_setup(PainterlyGlobals kg, const PainterlyRay &ray, const PainterlyIntersection &isect, int
    cycles_shader, ShaderData *sd)` goes in `src/painterly/kernel/svm/shader_data.h`.
  - For triangles, `sd->object` is the painterly object index, `sd->prim` the global triangle index (mesh offset plus
    `isect.prim`), `type = PRIMITIVE_TRIANGLE`, and `u, v` in Cycles' barycentric convention. The draft derives that
    convention from vendored `geom/triangle.h` and shows how Embree's maps to it.
  - The device scene fills Cycles' `objects`, `object_flag`, `tri_vindex`, `tri_verts`, `attributes_map`,
    `attributes_float2` (UV, corner element) and `attributes_float3` (generated, vertex element), all in Cycles' layout
    (T6.6:259-281). It also fills `kernel_data.cam` from the painterly camera.
  - The mesh contract gains two optional arrays, in `PainterlyScene::add_mesh` and in CONTRACT `_painterly.pyi`
    `add_mesh`: `corner_uvs: (T,3,2) float32 | None`, the active render UV map, and `generated: (V,3) float32 | None`,
    Blender's texture-space coordinates.
- Acceptance:
  - per field, a doctest compares the setup with a derivation written in the test, in double precision from the
    mesh's own vertices, UVs and generated coordinates. `triangle_point_from_uv` is in upstream
    `geom/triangle_intersect.h`, which is not vendored (decision 6), so the test does not call it;
  - an analytic hit has the NONE values of decision 6;
  - a compiled Texture Coordinate graph evaluated through the SVM at triangle hits gives the derived UV and Generated
    (both compile to `NODE_ATTR`, `TextureCoordinateNode.compile-SVMCompiler.inc:50-54, 95-99`) and Object
    (`svm_node_tex_coord`) values;
  - `test_api_contract.py` passes with the new parameters.
- Needs: B1.

### B4. The SVM in `painterly_trace_pixel`
- Scope: decision 3 and decision 7.
  - A hit on a node material runs `painterly_svm_shader_setup`, then
    `svm_eval_nodes<painterly_svm_surface_feature_mask, SHADER_TYPE_SURFACE>(kg->cycles, nullptr, &sd, nullptr,
    PathRayVisibility(0), 0)`, then `painterly_svm_collect`.
  - Its lobes are sampled per SPEC §6. Its emission is the collector's emission times `emission_gain`, and it counts as
    an emitter for `continue_after_emitter` as a constant material does.
  - One `ShaderData` (6.5 kB) per `painterly_trace_pixel` call, reused for every bounce of its iterative loop.
- Acceptance (exact):
  - (1) T3.16's bit-identical parity passes, and T3.17's slow statistical test passes as before.
  - (2) For each lobe kind, a node material equivalent to a constant material renders the same image bit for bit, with
    the same per-pixel K. Diffuse BSDF, sharp Glossy (mirror lobe), sharp Glass, Transparent BSDF, Emission, and a Mix
    Shader of two of them at factor 0.5 each map to a constant material per the closure policy (T6.7:175-208), with
    dyadic colours so float32 is exact. Use the reference scene's geometry at 100 px and 4 passes.
  - (3) A material with zero closures behaves as a black diffuse lobe (collect.h:205-210).
  - (4) A material whose inputs vary per hit, so nothing folds on the host (for example a Diffuse BSDF whose Color is a
    Checker Texture of Texture Coordinate's Object output, built in C++ from registered nodes): at the first hit of
    each of 16 fixed pixels, the lobe list the path samples equals the collector's output for the vendored SVM run
    directly on a ShaderData that `painterly_svm_shader_setup` gives for that hit.
- Needs: B2, B3.

### B5. The world shader on misses
- Scope:
  - `KernelPainterlyBackground` (CONTRACT `types.h:152-156`) gains `int cycles_shader`, -1 meaning constant radiance.
  - `PainterlyScene::set_background_shader(int shader)`.
  - On a miss with `cycles_shader >= 0`, painterly sets up the background ShaderData as Cycles'
    `shader_setup_from_background` does (upstream `geom/shader_data.h:398-426`): `P = D` normalized, `N = Ng = wi = -D`,
    NONE object, prim and type, `u = v = 0`, `ray_length = FLT_MAX`, zero `dPdu`, `dPdv`, `dP`, `dI`, `du`, `dv`. It
    evaluates with `painterly_svm_background_feature_mask`, and the radiance is the Background closure's weight.
  - Suns are added as today, and everything is scaled by `emission_gain` (SPEC §6, `spec.md:222-226`).
- Acceptance:
  - a Background node of a dyadic constant colour renders bit for bit like `set_background` of that colour;
  - a direction-dependent world (Gradient Texture into Background) equals the vendored evaluator called on the same
    ShaderData, for 64 fixed directions;
  - scenes without a world shader are unchanged.
- Needs: B4.

### B6. The `_painterly` shader-graph API
- Scope: CONTRACT `_painterly.pyi` and `python.cpp`.
  - `Scene.add_shader(nodes: list[tuple[str, dict[str, object], dict[str, object]]], links: list[tuple[int, str, int,
    str]]) -> int`. Each node is (Cycles type name, parameters by member name, linkable input defaults by UI name). Each
    link is (from node, output UI name, to node, input UI name); to-node -1 is the graph's output.
  - `Scene.add_node_material(shader: int) -> int` and `Scene.set_background_shader(shader: int) -> None`.
  - An unknown type, parameter, socket or enum name raises `ValueError` naming it, and a wrong value type raises
    `TypeError`. Indices are dense from 0 (pyi:7).
- Acceptance:
  - a graph built from Python renders bit for bit like the same graph built in C++;
  - each error case raises with the name;
  - `test_api_contract.py` covers the new names, parameters and defaults.
- Needs: B2, B5 (it binds `set_background_shader`), M3 T3.15.

### B7. `sync/shader/flatten.py`
- Scope: from Cycles' `add_nodes_inlined` (`blender/shader.cpp`; report §5).
  - Node groups are inlined, nested ones too; reroutes are removed.
  - A muted node passes through along Blender's internal links; frames are ignored.
  - Closure, bundle and repeat zones raise `PainterlyUnsupportedNode` with the zone's name (report R8).
- Acceptance: `make test-blender` cases on generated node trees, one per rule, compared with the expected flattened
  list of nodes and links.
- Needs: M5 T5.4 (the sync it plugs into).

### B8. `sync/shader/node_table.py` and `export.py`
- Scope:
  - The table maps Blender idname to Cycles type, with socket renames (Shader -> Closure, Mix suffixes, `_001` -> `2`)
    and enum aliases, for the nodes of the core six batches only. B8 adds the machinery and the rows the harness of B9
    needs: Material Output, Emission and Texture Coordinate. The batch cards add every other row, and batches 6 and 11
    give these three their golden tests.
  - Export turns a flattened tree into B6's lists.
  - The scene sync exports each material and the world. An unsupported node makes that material fall back to M5's
    constant mapping (T5.3), with one warning that names the node. M5's `SyncStats` (T5.2:9-11) has no warning field;
    B8 adds one, `warnings: list[str]`.
- Acceptance: `make test-blender` cases on generated `.blend`s, giving the exact export lists for fixtures and the
  fallback warning.
- Needs: B6, B7.

### B9. The golden-test harness
- Scope: `tests/blender_it/` and `make blender-it` (plan.md:353).
  - For each node, a generated `.blend` of an emission plane driven by the node, and an orthographic camera at pixel
    centres.
  - Cycles renders at 1 spp, Raw view, EXR float32, with the smallest filter width.
  - Painterly renders with `max_depth=1`, `emission_gain=1`, `jitter=0` and `output_mode="scene_linear"`, and no debug
    path. Its EXR holds `L/255 * exposure` (SPEC §8, `spec.md:277-279`), so the harness compares in painterly's output
    space: it applies that film transform to Cycles' values with the same float operations, in the same order.
  - A node whose inputs are all constants folds on the host (T6.5:163-168), so each golden scene drives the node from
    TexCoord or Geometry, and the SVM evaluates it per pixel.
- The comparison rule is pre-registered in the card as an experiment (X-golden, the next free number at run time).
  - "Cycles' own float32 spread" is measured from Cycles renders alone, between renders that differ only at float32
    level: for example the same plane with its object transform kept and baked into the vertices, and seeds that move
    the sample inside the smallest filter.
  - The card derives a per-pixel decision rule from that measurement, and Opus approves it at card approval. No
    tolerance is hand-picked, and the rule is never fitted to painterly's output.
- Acceptance: the experiment's README is pre-registered. The harness renders one scene in both engines, an Emission
  of Texture Coordinate's Generated output (B8's rows), and that scene meets the rule.
- Needs: B8, B5.

### B10. Image export and experiment X-colour
- Scope: X-colour as T6.8 pre-registered it (T6.8:1721-1886), run before the export is written.
  - Then `sync/image.py` exports `Image.pixels`, the colour-space class and alpha association into
    `Scene.add_image(...)` as experiment X-colour's results decide.
  - B10 owns `add_image`: `Scene::image_manager` in the shim `Scene`, `PainterlyScene::add_image(const
    PainterlyImagePixels &, const ImageParams &) -> int`, and `Scene.add_image` in CONTRACT `_painterly.pyi`.
- Acceptance: X-colour's decision rules are evaluated, and the Conclusion is left for Opus. The export round-trip tests
  are derived from X-colour's measured semantics.
- Needs: B9. Batch 10 needs B10.

### B11. Node-material parity on the reference scene
- Scope: the reference `.blend` of T5.4 with node materials (Principled, Diffuse, Emission) against the oracle ensemble,
  through the SVM path.
- Acceptance: T5.4's statistical test from `analysis/painterly_analysis/ensemble.py`, unchanged, passes. Its band is
  the ensemble's own, never re-derived from the new path's output.
- Needs: batches 11 and 12, M5 T5.4.

### Node batches (the core six; batch 1's card is the template the others follow)
Per node:
- vendor its evaluator (already done for every core node: `src/cycles/svm_nodes.toml` and `VENDORED.toml` at HEAD);
- extract its host class fragments where they are missing:
  - batch 5: `RGBRampNode`, `CurvesNode`, `RGBCurvesNode`;
  - batch 6: `MappingNode`;
  - batch 10: `ImageSlotTextureNode`, `ImageTextureNode`, `EnvironmentTextureNode`, and the rest of the T6.8 list at
    :839-851 that they need (B10 has added `Scene::image_manager` and `add_image`);
- add its `node_table.py` rows;
- add its golden test, which passes B9's rule.
The batches:
- N1: Value, RGB, Math, Vector Math.
- N5: Color Ramp, RGB Curves; the curve LUT is sampled as Cycles samples it.
- N6: Texture Coordinate, Mapping.
- N10: Image Texture (after B10).
- N11: Principled, Diffuse, Glossy, Glass, Refraction, Emission and Transparent BSDFs. Their golden test is the closure
  policy's lobe list at a hit, not an image, because lobes are painterly's own.
- N12: Mix Shader, Add Shader, Background.
Batches 5, 6, 10, 11 and 12 are drafted in one task from batch 1's template (FOLLOWUPS:93-94). The other six batches
follow v1 (D4).

## 3. Open questions that are not decided here

- Light node graphs (emission node trees on lights) are outside v1: lights stay ghost spheres with constant emission
  (SPEC §5).
- Whether a node material's emission is scaled by `emission_scale` (T5.3:37 applies it to lights only). Until Opus
  rules, node-material emission is not scaled.
- Per-lobe normals (Bump, Normal Map) and the Attribute node are outside v1.

## 4. How the cards are drafted

DeepSeek drafts each card from this brief, in one queue task per card, except one task for batches 5, 6, 10, 11 and 12.
Opus's review panel then checks the drafts, and Opus approves them (plan rows M6b.rvA-rvC, M6b.19).
- Output: `docs/handoff/drafts/M6b/<id>-<slug>.md`, in the template of `docs/tasks/README.md` ("Card template"). The
  first line is `# <id> — <title>`; then `Milestone: M6b · Depends on: <ids> · Parallel-safe: yes|no`; then the
  sections `## Goal`, `## Read first`, `## Create`, `## Modify`, `## Do not touch`, `## Interface`, `## Steps`,
  `## Acceptance`, `## Commit`, and a last section `## Open for Opus` (write "None." if there is nothing).
- The brief's text for the card is the mandate. Copy its interface names and its CONTRACT text exactly. A CONTRACT
  change is shown under `## Interface` as "CONTRACT (Opus writes this before dispatch):", followed by the exact
  declaration and its comment.
- Read the code before writing a step: `FACTS.md` (this directory) gives the current interfaces with file:line, and the
  M6a cards (`docs/handoff/drafts/M6a/`) show the style: exact paths, numbered steps, and an acceptance of exact
  commands with expected outputs (doctest filters with the counts the card's own cases give, pytest files, and the
  queue's CHECK).
- Every expected value in the card is derived in the card: from SPEC, from upstream code with file:line, or by a script
  whose command and output the card quotes. A count is the count of the cases the card itself specifies. Never put an
  estimate in a card.
- Do not decide what this brief leaves open; put it under `## Open for Opus`, with the options and what each would
  change. Where this brief is wrong about the code (a name, a line, a signature), say so there, with the evidence, and
  write the step for the code as it is.
- Write only your card's file. Run no build and no test: a draft changes no code.
