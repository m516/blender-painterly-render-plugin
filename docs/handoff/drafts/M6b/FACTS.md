# M6b facts at d92f195 (input to the M6b drafts)

Gathered by a Sonnet reader for Opus on 2026-10-25, read-only, with file:line at MAIN `d92f195`. Facts only: the design is
`BRIEF.md`, and where this sheet and the brief disagree, the brief wins. Lines that cite `.tmp/` are the steward's
notes, which a worker cannot read; the sheet quotes what matters from them.


Facts only; nothing here is a design. Paths are relative to P (the project root) unless they start with `/`.
`H/` = `docs/handoff/drafts/M6a/` (the M6a cards live only there; BACKLOG.md:966 and :1024 point to it; no `docs/tasks/M6a`,
no `docs/tasks/M6b`). `.tmp/` = `P/.tmp/` (steward and queue notes).

State at HEAD. M6a T6.1-T6.8 landed (203c431, 7483c1f + fix d9efc3f, 398abc9, 5fcd69d, c02fab8, b9f72f4, e06f00a, bb41b02);
gate G2 ruled by d92f195. M4 T4.1-T4.3 landed (7fee256, b208118, 93ff499). **M4 T4.4 and M5 T5.1-T5.4 have not landed**:
`src/blender/addon/sync/` holds only `__init__.py` and `reference.py`, and `Makefile:32` has no `blender-it`, `extension`
or `reference-blend` target. M6b is "not drafted" (docs/handoff/README.md:33; drafts/STATUS.md:44; queue.md:88-89).

## 1. Plan and spec

### 1.1 docs/plan.md (M6 predates the M6a/M6b split; "Card IDs and contents in docs/tasks/ supersede these tables", :223)
- Owner decision: "Materials | Blender **shader node-graph evaluation**, Cycles-style." :15. Goal: "renders arbitrary Blender scenes" :8.
- Architecture: "an SVM shader VM and NodeType reflection" :55. Verbatim from Cycles: "90 node structs plus 14 trailing data
  structs. Of the 108 dispatch cases in `svm_eval_nodes`, 43 take only `(stack, node)`, 49 read `ShaderData`, 8 read
  `KernelGlobals`, and 8 are special" :59-61; "painterly uses Cycles' own `kernel/types.h` (`ShaderData`, `KernelData`) for
  shading" :62-63. "Blender's node mapping ... becomes Python data tables" :66.
- Layout hints: kernel "M6: svm/ (generated switch from verbatim SVM_CASE fragments) closure/painterly collector" :113-114;
  cycles/ "(M6) cycles_svm", shims "M6: scene/scene.h, kernel/device/cpu/globals.h" :119-121; add-on "(M6: sync/image.py,
  sync/shader/{flatten,node_table,export}.py)" :124. Rule: "node ports only *add* files" :141; "Every painterly constant is a
  reflected socket on `PainterlyIntegrator`" :142.
- Experiments: X-svm (M6) :200 "Vendored `graph/` + SVM with the shim works; hours per node port (gate G2)."; X-colour (M6) :201
  "Blender's bundled PyOpenColorIO sees Blender's config; Image.pixels semantics."
- M6 header :297: "(gate G2 = X-svm: if the `graph/` shim fails, keep Cycles names but write our own reduced reflection)".
  **G2 ruled pass** (experiments/011-2026-10-23-svm-probe/README.md:420-424): "M6b builds on `cycles_svm`, `cycles_scene` and
  `PainterlyShaderManager`"; the fallback "is not needed". :429-431: the gate covers the compiler of `make build` only; "MSVC and
  macOS arm64 first compile this code in CI".
- M6 rows :299-305 (superseded names): T6.2 `shader_graph` "contract by Opus"; T6.4 "`svm/closure_painterly.h` (Cycles closure
  categories → {diffuse, mirror, glass, emission, transparent}; selection with the §2 hash RNG)"; T6.5 Python
  `sync/shader/{flatten,node_table,export}.py` "(groups, reroutes, mutes; idname → Cycles type; socket renames Shader→Closure,
  Mix suffixes, `_001`→`2`; enum aliases)".
- The 12 node batches, plan.md:305: Value/RGB/Math/VectorMath; Mix/MapRange/Clamp; Invert/Gamma/BrightContrast/HSV;
  Separate/Combine Color & XYZ; ColorRamp/RGBCurves (sampled LUT); TexCoord/Mapping; Noise/WhiteNoise; Voronoi;
  Checker/Gradient/Wave/Magic/Brick; Image Texture (+ X-colour); Principled/Diffuse/Glossy/Glass/Refraction/Emission/Transparent;
  Mix/Add Shader/Background. "Checklist per node: vendor evaluator → copy `NODE_DEFINE` + `compile()` → `node_table.py` row →
  golden test."
- Acceptance (plan.md:305, verbatim): "Golden test per node: a generated `.blend` with an emission plane driven by the node,
  rendered by Cycles at 1 spp (pixel centre, Raw, EXR) vs Painterly with knobs `max_depth=1, emission_gain=1`, with no debug code
  paths; equal within Cycles' own float32 spread". `make blender-it` must "render node golden scenes against Cycles" :353.
- M7 depends on M6 :310. Card format :225-232 ("the **interface, verbatim** (Opus writes contract headers before dispatch ...)"
  :229); template docs/tasks/README.md:7-20.

### 1.2 Steward plan text on M6b (.tmp/steward/plan/plan_emit.py, plan_gen.py)
- plan_emit.py:170-176 "M6b: Node materials inside the painterly kernel". Done when: the "golden test of each node batch against
  Cycles (1 spp, pixel centre, Raw EXR) passes, for at least the six core batches of decision D4, and node-material parity holds
  on the reference scene; Opus's M6b review passes. Micah can render scenes with Principled, texture and image materials."
- D4 (plan_emit.py:262-268), decided: "Core six: Value/RGB/Math, Color Ramp/RGB Curves, Texture Coordinate/Mapping, Image
  Texture, the BSDFs, Mix/Add Shader/Background; the other six follow v1". In plan_gen.py:412-417 CORE = batches 1, 5, 6, 10, 11, 12.
- FOLLOWUPS.md:93-94 (.tmp/steward): batches 5, 6, 10, 11, 12 are ONE BACKLOG item drafted from batch 1's template.

### 1.3 docs/spec.md: normative sentences M6b implements or respects
Lobes and selection (SPEC §6):
- :190 "**Materials are lobe mixtures.** smallpaint's three material types become *lobes*"; :191-194 diffuse (weight `cl`), mirror
  and glass ("the weight tints the child radiance as `L += L_child * weight`"), `transparent` ("straight continuation, tinted").
- :196 "A material is a list of lobes plus an emission colour."
- :197 "Per hit, one lobe is chosen with probability `p_k = lum(w_k) / Σ_j lum(w_j)` using `rng_unit(seed, PURPOSE_CLOSURE, depth,
  row, col, pass)`." :198 "`lum` uses the Rec.709 luma weights." :199 "When all luminances are 0, the choice is uniform."
- :200 "The chosen lobe's weight is divided by `p_k`. With one lobe, `p = 1` and nothing changes." :201 "Selection never touches K."
  :202 "M6 evaluates Blender node graphs per hit into the same lobe list."
- :204-207 triangles: with `two_sided` (default true) "the diffuse, mirror and transparent lobes use that normal flipped to face the
  incoming ray. The glass lobe always gets the unflipped normal (as authored), because its `dot(N, d) > 0` test decides whether the
  ray leaves the medium."
Random numbers, K, chains and lanes (§2, §3):
- :51 "Only diffuse events advance K. Mirror, glass, emission, misses and depth termination never advance K." :64
  "`PURPOSE_CLOSURE = 3`: closure selection. (a,b,c) = (row, col, pass), depth = bounce depth." :53-60: stateless `rng_*`, always
  evaluated in double.
- :101 "A chain processes its pixels strictly in order, and each pixel's whole path finishes before the next pixel starts." :102-103
  "Lanes are independent of each other and of thread scheduling. Output is therefore bit-identical for any thread count or batch
  size." (Read together with :51 and :201: a node material that picks a diffuse lobe advances K by one draw; every other lobe, and the
  selection itself, leaves K alone.)
Path and light (§4-§6):
- :123 diffuse term "`L += (cost · (L_child · color)) · diffuse_gain`, in exactly this order"; :127-128 reference `color = cl`,
  `diffuse_gain = 0.1`; "**Blender values:** `color` = closure albedo (≈0…1) and `diffuse_gain = 1.0`".
- :168 "`if depth ≥ max_depth: return 0` *before* intersecting"; :169 "A miss returns the world/background radiance."; :170-171 "On a hit
  the path first adds emission, `L = 0 + (E·emission_gain)`"; :180-182 emitters are black diffuse surfaces that "keep bouncing with
  zero throughput and keep consuming K"; :183 "No Russian roulette, no next-event estimation, no MIS, no clamping, no adaptive
  sampling."; :187-188 backward evaluation "bit-identical with the oracle".
- Ghost spheres: :158 "Point and spot lights are ghost spheres with `r = shadow_soft_size`"; :161 "Ghost spheres are intersected by brute
  force outside any BVH"; :213 "lobe `diffuse` of weight 0 and emission `color · energy · emission_scale`"; :221 area lights are
  "emissive quads (no ghosting)".
- World: :226 "The world is evaluated on a miss (constant in M3–M5; a node graph from M6). Misses and suns are scaled by
  `emission_gain` like every emitter." Suns :222-225.
- Knobs: :287-291 (`diffuse_gain` 1.0 for Blender albedos, `emission_gain` 2, `max_depth` 20, `two_sided` true, `ray_epsilon`,
  `jitter` 1/1400 of the fitted side :248, `output_mode`, `exposure`).
- SPEC says nothing else about node materials, textures, images or colour spaces (grep of docs/spec.md for node, texture, world,
  svm, shader, graph, material: only :202, :226 and, for the miss, :169).

### 1.4 Other binding text
- docs/architecture.md:57-70 dependency direction: "`painterly/kernel/` never includes `painterly/scene/`"; integrator and scene "never
  include each other"; "`PainterlyScene::device_update()` is the only bridge"; the kernel's Embree call is the one exception.
  :52-55 why Cycles' own `kernel/types.h` is used. :88-94 determinism: bit-identical for any thread count; `-ffp-contract=off`.
- CONTRACT files (first lines `CONTRACT: Opus-owned`): `src/painterly/kernel/globals.h:4`, `src/painterly/kernel/types.h:4`,
  `src/blender/_painterly.pyi:4` (+ `util/math_double3.h`, `util/types_double3.h`). CLAUDE.md:25 "Never edit any file whose first lines
  contain `CONTRACT:`"; AGENTS.md:68-69 allows it only if "your card lists that exact file under Create/Modify".
- The M6a cards' acceptance style: sha256 lists of vendored files, doctest filters with stated counts (`.tmp/steward/plan/m6a-doctest-gates.md`
  "Gate form": `painterly_tests --test-case='<filter>' | grep -qE '^\[doctest\] test cases: +N \| +N passed \| +0 failed \|'`),
  pytest, `make check`. A BACKLOG item has `Card:`, `Depends on:`, `Outcome:`, `verify:` (BACKLOG.md:965-972, 1023-1031).

## 2. Notes for later cards (all "M6b wires ..." statements of T6.1-T6.8)
Tags: [globals] [device_update] [ShaderData] [trace_pixel] [world] [bindings] [flatten] [node table/export] [golden] [image export]
[parity] [build].
**T6.1-T6.3 (earlier hand-offs)**
- [globals] H/T6.1:379-380 "M6b decides how `PainterlyGlobalsCPU` holds a `KernelGlobalsCPU`; this shim names no painterly type." Later
  cards may rely on `KernelGlobalsCPU`, `KernelGlobals`, `kernel_array<T>`, the four macros and every `data_arrays.h` array.
- [build] H/T6.1:80-85 every target whose sources include a `kernel/` header must link `cycles_kernel`; "Nothing enforces this
  rule" (a non-default `PAINTERLY_MAX_CLOSURE` would give a second `ShaderData`: ODR). H/T6.3:434, T6.1:599-600: a library that
  compiles kernel headers "may add one function ... that returns `painterly_kernel_layout_record()`, plus one comparison in
  `test_cycles_kernel_layout.cpp`" ("M6b's first compiled consumer adds one").
- [build] H/T6.3:1559-1560 `-fno-strict-aliasing` is INTERFACE on `cycles_kernel`; "M6b's module will get it once it links
  `cycles_kernel`". H/T6.3:202 + 1554 `kernel/tables.h` puts five `inline constexpr` arrays in the global namespace: "for M6b's
  symbol audit". .tmp/steward/FOLLOWUPS.md:160-161: `shader_manager.h` type-puns through `reinterpret_cast` (now
  src/painterly/scene/svm/shader_manager.h:145, 204); "M6b's library must link it too".
- [trace_pixel] H/T6.2:542-552 the call shape: `svm_eval_nodes<node_feature_mask, type>(kg, state, sd, render_buffer,
  path_visibility, path_flag)`; "T6.3 and M6b call it as Cycles does".
**T6.4 (H/T6.4-shader-graph.md)**
- [bindings, device_update] :23-24 "Nothing in the painterly engine uses `cycles_scene` yet ... M6b wires both into `PainterlyScene` and
  the Blender sync."
- [node table/export, bindings] :123-124 + :1030-1043 "Socket naming (contract for T6.5 and M6b)": node type by Cycles type name
  (`NodeType::find(ustring(name))`); linkable input/output and unlinked default by UI name (`ShaderNode::input/output`,
  `ShaderGraph::connect`, `ShaderInput::set`); parameter by member name (`type->find_input(ustring(name))` then `Node::set`, enum by
  `NodeEnum` name). "M6b's Python export sends UI names for links and linkable defaults, and member names, with enum names, for
  parameters." A parameter has no `ShaderInput`, so `input("Type")` is `nullptr` (:1039).
- [bindings] :861 "Later cards and M6b call `painterly_cycles_shader_node_types()` once before their first `NodeType::find()`."
  (src/cycles/shader_node_registry.h:24; NODE_DEFINE registration lives in the generated `shader_nodes` unit.)
- [node table] :128 "A node port adds fragments and, if its code needs a further header, one `includes` entry" (src/cycles/
  fragment_units.toml). :191-192 "Later cards add classes the same way: `TextureMapping` and the texture nodes, `BsdfBaseNode`/`BsdfNode`
  and the closure nodes, `CurvesNode`, `OutputAOVNode`, ...".
- [build] :129-135 build-glue headers live in `src/cycles/` (first one `shader_node_registry.h`); "`docs/architecture.md` does not list
  this location yet. A later docs card adds it". :1045-1053: `SVMShaderManager` (`svm.cpp:33-153`) is never extracted; "No layout probe
  in `cycles_scene`".
**T6.5 (H/T6.5-svm-compiler.md)**
- [device_update] :26-27 as T6.4. :144-147 Decision 4: `PainterlyShaderManager` "is header-only and in no build target during M6a; M6b
  moves it into a library"; if `src/painterly/scene/CMakeLists.txt` exists "do not add the header to it: M6b does".
- [device_update] :1236-1242 "What later cards rely on": `background_shader`, `device_update_pre/post/free`; "M6b moves it into a library
  and calls it from `PainterlyScene::device_update()`". :1243-1248 the shim `Scene` (`shaders`, `shader_manager`, `dscene`),
  `DeviceScene` (`svm_nodes`, `shaders`, `data`), `Shader` members; the build check `cycles_svm_closure_headers_check`: "A later card
  that vendors more kernel headers adds its own check file and never edits this one."
- [golden] :163-168 Decision 6: `ShaderGraph::finalize` constant-folds, so a graph of constants becomes one constant emission and "Only
  the unfolded program makes the SVM itself evaluate Value and Math. A graph whose inputs vary per shading point compiles the same way
  in Cycles, because nothing folds."
- [node table] :1249-1259 manifests: "A card that adds the BSDF, background or mix-closure cases adds only their fragments and case
  lines"; `svm_nodes.toml` / `fragment_units.toml` are append-only; :1268-1270 another `util/time.cpp` function = one more fragment of unit
  `time`. :2052-2054 pass consequence of gate G2-svm.
**T6.6 (H/T6.6-svm-textures.md)**
- [golden] :131-132 "the per-node golden renders against Blender's Cycles are M6b's". [ShaderData, globals] :259-281 "Minimal
  KernelGlobalsCPU (TexCoord, Attribute, Geometry)": arrays `objects`, `object_flag`, `attributes_map`, `attributes_float3`,
  `attributes_float2`, `tri_vindex`, `data.cam`, "in Cycles' layout, so M6b's `PainterlyScene` can fill the same arrays the same way";
  `tri_verts`, `tri_shader`, `attributes_normal` are read only for smooth normals (SHADER_SMOOTH_NORMAL), :273-275.
- [trace_pixel] :170-173 Voronoi 2D/3D/4D need `KERNEL_FEATURE_NODE_VORONOI_EXTRA`: "M6b must evaluate with a mask that has it".
- [parity] :166-169 the SVM draws no random number (`lcg_state = 0`), so K is untouched. [tests] :546-547 reusable names:
  `PainterlySvmTestScene`, `painterly_svm_test_run_shader_data`. :611-621 "For later cards": 14 cases, 8 texture node types registered,
  `TextureMapping` reusable, `src/test/cycles_svm_test_scene.h` for doctests of nodes that read geometry.
**T6.7 (H/T6.7-svm-closures.md)**
- [trace_pixel, device_update] :33-34 "M6b wires `painterly_svm_collect()` into `painterly_trace_pixel`, `PainterlyScene` and the Blender
  sync." :144-149 "`PainterlyScene::device_update()` calls `device_update_pre()`, `device_update_post()` and
  `device_update_lookup_tables()`, in this order"; :1533-1536 then `PainterlyShaderManager::bind_kernel_globals(dscene, globals)`
  "and binds the other kernel arrays itself". [parity] :161-167 caustics flags forced true in `device_update_common`.
- [node table] :125-129 "Every other closure node class (Metallic, Sheen, Translucent, Toon, Subsurface Scattering, Hair, Ray Portal,
  Holdout, the volume nodes) is left to M6b's node ports"; BSDF classes "need only their own fragments"; Holdout/volume also need cases.
- [trace_pixel] :168-174 feature masks (`collect.h:39-42`). :175-208 closure policy table (Cycles category -> lobe kind); ":208 The
  policy is Opus's. Changing it needs an Opus decision." :209-217 evaluation contract (now the header comment of collect.h:11-23).
  :1540-1542 "`painterly_trace_pixel` copies `material.lobes` into the per-hit lobe list that it samples (SPEC §6); lobe selection,
  `emission_gain` and `two_sided` stay M6b's."
**T6.8 (H/T6.8-svm-images.md)**
- [image export, golden] :24 "Experiment X-colour ... gets its number when it runs, in M6b." :26-27 "M6b wires the image path into
  `painterly_trace_pixel`, `PainterlyScene` and the Blender sync." :119-127 `ImageTextureNode`/`EnvironmentTextureNode` host classes are
  NOT extracted: "M6b, which owns the Blender sync, extracts them". :146-147 "M6b's Python export decides both [class, converted
  pixels]; experiment X-colour tests how." :176-178 the one known deviation (unassociated alpha + converted class), left to X-colour
  H4(f) and M6b. :192-195 Cycles' `frac()` quirk is pinned, not corrected (parity with Blender).
- [globals] :836-838 bind `KernelGlobalsCPU::image_textures`/`image_info` to `get_image_textures()`/`get_image_info()` after the last
  `add_image()`; "Leave every other image array empty." :839-851 what M6b adds: `Scene::image_manager`; the two node-class fragments
  with `ImageHandle::metadata(Progress &)` + an `ImageMetaData` shim, `ImageHandle::all_udim_tiled()`, the `tiles` overload of
  `add_image()`, `ImageParams::{animated,colorspace,frame}`, `ColorSpaceManager::colorspace_is_data()`, `u_colorspace_*` names, and for
  `cull_tiles` scene parameters, geometry and `UVMapNode`; the Python pixel/class export.
- [image export] :1721-1732 X-colour is run by "the M6b card that adds the Python image export ... before it writes the export" in
  `experiments/NNN-<DATE>-colour/`, README text copied verbatim from :1734-1886. H1 (PyOpenColorIO loads Blender's config.ocio) :1768-1778;
  H2 (class of roles scene_linear/default_byte/data) :1779-1791; H3 (`Image.pixels` = bytes/255, floats exact, row 0 at bottom)
  :1792-1807; H4 (Cycles stores/samples as T6.8 predicts, unpacked and packed; configs a-e) :1808-1847; H4(f) alpha < 1 :1850-1859.
**Steward notes** .tmp/steward/landing/NEXT-LANDING.md:215 (same reinterpret_cast note); FOLLOWUPS.md:93-94 (batch drafting).

## 3. Current interfaces at HEAD

### 3.1 Painterly kernel data (CONTRACT headers)
- `src/painterly/kernel/globals.h:40-68` `struct PainterlyGlobalsCPU`: `data` (KernelPainterlyData*), `analytic/num_analytic`,
  `materials/num_materials`, `lobes/num_lobes` ("Constant lobes of all materials" :48), `suns`, `objects`, `meshes`, `tri_material`
  (:60), `tri_corner_normals` (:63), `const void *bvh` (:67). It holds no Cycles member (no `KernelGlobalsCPU`, no `KernelData`).
  `using PainterlyGlobals = const PainterlyGlobalsCPU *` :70. Comment :58-59 "The vertices are not here: only the BVH reads them".
- `types.h:90-94` `KernelPainterlyLobe {int kind; double3 weight; double ior;}`; `:49-55` `LOBE_DIFFUSE=1, LOBE_MIRROR=2, LOBE_GLASS=3,
  LOBE_TRANSPARENT=4`. `:101-106` `KernelPainterlyMaterial {lobe_offset, num_lobes, double3 emission, int svm_offset}` with
  ":105 -1: constant lobes. M6: an SVM program overrides lobes/emission per hit." `:152-156` `KernelPainterlyBackground {double3
  radiance; int num_suns}` ("M6: world shader"). `:158-162` `KernelPainterlyData {cam, integrator, background}`. `:108-122`
  `KernelPainterlyCamera` (double `raster_to_camera[16]`, `camera_to_world[12]`; no Cycles `KernelCamera`).
  `:164-168` `PainterlyPathResult {radiance, k_consumed}`. Per-hit lobes limit: `MAX_CLOSURE` (= `PAINTERLY_MAX_CLOSURE`, default 64,
  src/cycles/CMakeLists.txt:96-103).

### 3.2 Cycles globals shim (src/cycles/shim/kernel/device/cpu/globals.h)
- :31-45 `template<T> struct kernel_array {fetch(i), write(i,v), T *data; int width}`. :49-57 `struct KernelGlobalsCPU`: one
  `kernel_array<const T> name` per `KERNEL_DATA_ARRAY` of `kernel/data_arrays.h` (bvh_nodes ... objects, object_flag, tri_shader, tri_vindex,
  tri_verts, attributes_map/float/float2/float3/float4/uchar4/normal, lights, svm_nodes, shaders, lookup_table, image_textures,
  image_info ...), `KernelData data = {}` (:54), `KernelImageLoadRequestedCPU image_load_requested_cpu` (:56). :59 `using KernelGlobals =
  const KernelGlobalsCPU *`. :62-65 `kernel_data_fetch/write/array`, `kernel_data`. :19-26 `#error` without cycles_kernel's definition set.
- Measured sizes at T6.1 (GCC 13.3): ShaderData 6480 B, KernelData 2576, ShaderClosure 96, KernelGlobalsCPU 3456 (H/T6.1:88).
- `KernelData` members the vendored SVM/closure code reads (grep of kernel/{svm,closure,geom,camera,util}): `cam.*` (type, worldtocamera,
  cameratoworld, worldtondc, width, height ...), `integrator.caustics_reflective/refractive`, `tables.*` (ggx, sheen_ltc, thin_film),
  `film.{rgb_to_y, xyz_to_*, rec709_to_*, is_rec709}`, `image.mip_bias`. `max_closures` is written by no shipped code (tests set it:
  src/test/test_cycles_kernel_types.cpp:63); collect.h:17-18 says `num_closure_left` = `kernel_data.max_closures`.

### 3.3 Shim Scene / DeviceScene / Shader / ShaderManager (src/cycles/shim/scene/)
- scene.h:31-38 `DeviceScene {array<int> svm_nodes; array<KernelShader> shaders; array<float> lookup_table; KernelData data}` (host
  arrays). :45-63 `Scene {unique_ptr<LookupTables> lookup_tables; unique_ptr_vector<Shader> shaders; unique_ptr<ShaderManager>
  shader_manager; DeviceScene dscene; ~Scene() calls shader_manager->device_free}`. No `image_manager`, no geometry, no `params`.
- shader.h:66-161 `Shader` (not a Node; `graph`, `set_graph(unique_ptr<ShaderGraph>&&)` :133, `reference()` :150, `id`, `has_*` flags,
  `estimate_emission()` empty :129). :169-228 `ShaderManager` (virtual `device_free` :178, `device_update_lookup_tables(DeviceScene*,
  Scene*)` :192, protected pure-virtual `device_update_specific` :224, `rgb_to_y` :205).

### 3.4 PainterlyShaderManager (src/painterly/scene/svm/shader_manager.h, header-only, `final : public ShaderManager`)
- :48 `const Shader *background_shader`; :52-120 `device_update_pre(Device*, DeviceScene*, Scene*, Progress&)` (numbers shaders, runs
  `ShaderGraph::finalize`, sets `has_*`); :124 `device_update_post(...)` calls `device_update_specific` :156 (compiles each shader with
  `SVMCompiler` :170-173, packs the jump table :181-218) and `device_update_common` :252-354 (`KernelShader::flags`, `caustics_*` = true
  :346-347, `film.rgb_to_y` :353);
  :131 `device_free(...)`; :143-152 `static bind_kernel_globals(const DeviceScene&, KernelGlobalsCPU&)` copies `svm_nodes`, `shaders`,
  `lookup_table` and `data` (KernelData by value) only. Caller order (T6.7): pre, post, `device_update_lookup_tables`, bind.
- Reference usage: src/test/test_cycles_svm_closures.cpp:47-143 (`make_scene` with `PainterlyShaderManager`, `add_shader`, `compile`,
  `evaluate`: `svm_eval_nodes<painterly_svm_surface_feature_mask, SHADER_TYPE_SURFACE>(kg, nullptr, &sd, nullptr, PathRayVisibility(0),
  uint32_t(0))` then `painterly_svm_collect`; `sd.flag = dscene.shaders[id].flags` :128; `sd.type = PRIMITIVE_TRIANGLE`).
  src/test/cycles_svm_test_support.h:317-329 `painterly_svm_test_shader_data`: `lcg_state = 0`, `num_closure = 0`,
  `num_closure_left = MAX_CLOSURE`.

### 3.5 Closure collector (src/painterly/kernel/svm/collect.h)
- :39-42 `painterly_svm_surface_feature_mask` (= `KERNEL_FEATURE_NODE_MASK_SURFACE & ~KERNEL_FEATURE_NODE_RAYTRACE`),
  `painterly_svm_background_feature_mask`. :52-60 `struct PainterlySvmMaterial {KernelPainterlyLobe lobes[MAX_CLOSURE]; int num_lobes; double3
  emission; int num_dropped}`. :76 `painterly_svm_lobe_kind(ClosureType, int*)`; :107 `painterly_svm_reflection_color(const MicrofacetBsdf*)`;
  :133 `painterly_svm_transmission_color`; :147 `painterly_svm_lobe_weight`; :165 `painterly_svm_collect(const ShaderData*, PainterlySvmMaterial*)`
  ("reads ShaderData only: no kernel array, no random number" :8-9; zero lobes -> one `LOBE_DIFFUSE` of weight 0 :205-210).
- Contract comment :11-23: path_visibility 0, path_flag 0; `num_closure_left` = max_closures; `SD_BACKFACING` clear ("the glass lobe decides
  inside and outside itself (SPEC §6), so its IOR must be the authored one that Cycles inverts on back faces"); read the live `ShaderData`.

### 3.6 Image manager (src/cycles/shim/scene/image.h; image.cpp is in `cycles_scene`)
- :33-40 `ImageParams {interpolation, extension, alpha_type; operator== default}`. :46-77 `enum PainterlyImageColorSpace {SCENE_LINEAR=0,
  SCENE_LINEAR_SRGB=1, DATA=2, CONVERTED=3}` (comment :57-75 is the caller's contract for CONVERTED). :82-101 `PainterlyImagePixels {width,
  height, source_type, colorspace, is_unassociated_alpha, vector<uchar4> bytes, vector<float4> floats}` (row 0 at v = 0, :95-98).
  :106-116 `PainterlyImageMetaData`. :122-151 `ImageHandle {empty(), kernel_id(), get_manager()}`. :162-216 `ImageManager {add_image(const
  PainterlyImagePixels&, const ImageParams&) -> ImageHandle :175; metadata(handle) :189; get_image_textures() :195; get_image_info() :199;
  get_use_texture_cache() false}`; "Not thread safe: painterly adds images from one thread, before rendering" :160-161.

### 3.7 Build targets
- src/cycles/CMakeLists.txt: `cycles_util` STATIC :9-16 (PUBLIC `CCL_NAMESPACE_BEGIN=namespace painterly {` :30-32; include order shim, vendored
  SYSTEM, src :25-27); `cycles_graph` STATIC :79-83; `cycles_kernel` INTERFACE :101-103 (links cycles_util, `__MAX_CLOSURE__`; INTERFACE
  `-fno-strict-aliasing` :146-148); `cycles_shim_markers` OBJECT :107; `cycles_svm` INTERFACE :128-132 (generated `svm_eval_nodes.h` via
  `tools/gen_svm_switch.py`, needs `find_package(Python 3.12 ... Interpreter)` :114; links cycles_kernel); `cycles_svm_headers_check` :137 and
  `cycles_svm_closure_headers_check` :201 (OBJECT, in ALL); `cycles_scene` STATIC :170-176 (+:196, :219, :236, :240; sources constant_fold.cpp,
  shader_graph.cpp, shim/scene/{attribute,shader,image}.cpp, generated units shader_nodes, svm, time, transform, tables; PUBLIC links
  cycles_graph cycles_kernel; PUBLIC `ccl=painterly` :179).
- Painterly: `painterly_kernel` INTERFACE (kernel/CMakeLists.txt:7-8, links painterly_bvh, cycles_util); `painterly_scene` STATIC
  (scene/CMakeLists.txt:6-13: integrator, camera, background, mesh, scene, device_scene .cpp; PUBLIC cycles_graph painterly_kernel painterly_bvh);
  `painterly_integrator` (links painterly_util painterly_kernel); `painterly_session` (links painterly_integrator painterly_scene); `_painterly`
  (blender/CMakeLists.txt:12,18: python.cpp, selftest.cpp; PRIVATE painterly_session painterly_kernel painterly_embree; exports.map).
- **No production target links `cycles_kernel`, `cycles_svm` or `cycles_scene`**; only `painterly_tests` (src/test/CMakeLists.txt:77-99) and the
  OBJECT checks. src/CMakeLists.txt:2-5 builds cycles/ and painterly/ for MODULE or TESTS.

### 3.8 painterly_trace_pixel and where materials, BSDFs and lights are evaluated (src/painterly/kernel/)
- integrator/path.h:64-65 `PainterlyPathResult painterly_trace_pixel(PainterlyGlobals kg, int row, int col, int pass, uint64_t *K,
  PainterlyPathVertex *scratch)`; called from integrator/path_trace.cpp:142 and :188 (`kg_` is a `const PainterlyGlobalsCPU *` taken from a
  local copy of `device_scene_.globals()`, session.cpp:114, path_trace.cpp:55-58).
- Material: `kg->materials[material_index]` (path.h:97-98; index from `painterly_triangle_material`, geom/triangle.h:16, or `prim->material`).
  Emission `mat.emission` (+ `painterly_spot_attenuation` for spot ghosts, light/spot.h:35) -> `painterly_emission_term` (path.h:101-105).
  Lobe: `painterly_select_lobe(kg, mat, row, col, pass, depth)` path.h:113; closure/lobe.h:33-79 reads `kg->lobes + m.lobe_offset` (:36), returns
  `lobes[0]` unchanged for one lobe (:37-39), else rng `PURPOSE_CLOSURE` (:49-50), weight / p (:77). Bounces: closure/bounce.h:28
  `painterly_diffuse_bounce`, :70 mirror, :82 glass; `LOBE_TRANSPARENT` keeps `ray.d` (path.h:141-144).
- Lights: no light sampling. Lights are analytic ghost spheres with emissive materials. Miss: `painterly_background_radiance(kg, ray.d)`
  (light/background.h:17: constant `radiance` + suns), path.h:81-83, scaled by `emission_gain`.
- Backward evaluation path.h:161-176; `PAINTERLY_OBJECT_ID_MISS` :184; `painterly_primary_object_id` :189.

### 3.9 Hit records
- globals.h:73-91 `PainterlyRay {double3 o, d}` (d unnormalized, t parametric); `PainterlyIntersection {double t; int kind (HIT_NONE/
  HIT_ANALYTIC/HIT_TRIANGLE); int index (analytic index, or object index for a triangle); int prim (triangle index within its mesh);
  float u, v (Embree barycentrics); double3 Ng (unnormalized world geometric normal)}`.
- kernel/bvh/bvh.h:26 `painterly_scene_intersect`: triangles via `painterly_embree_intersect_closest(bvh, ray, eps, inf, &isect)`
  (bvh/embree.h:84), then analytic primitives in list order; an analytic hit sets only `t`, `kind`, `index` (bvh.h:24-25). P is computed as
  `ray.o + ray.d * isect.t` (path.h:89); there is no stored P, UV or global primitive id. Normals: geom/triangle.h:32
  `painterly_triangle_shading_normal(kg, isect, ray, two_sided)` (corner normals or `Ng`, flipped when two_sided), geom/analytic.h:100
  `painterly_analytic_normal`. `KernelPainterlyAnalytic` types.h:79-87; `KernelPainterlyObject` globals.h:25-32; `KernelPainterlyMesh` :34-38.

### 3.10 PainterlyScene and the device update
- scene/scene.h:34-112 `PainterlyScene {vector<PainterlyMaterial> materials; analytic; meshes; objects; camera; background; integrator}`;
  `add_material(lobes, emission)` :52 (`PainterlyMaterial {vector<KernelPainterlyLobe> lobes; double3 emission}`, material.h:17-47);
  `add_mesh(vertices, triangles, tri_material, corner_normals)` :67; `add_object` :73; `set_background(radiance)` :89; `add_sun` :92;
  `void device_update(PainterlyDeviceScene &ds) const` :103 (the only bridge).
- scene/device_scene.cpp:92-304: builds every array in locals, then commits ("strong guarantee" :94-97, commit :289-303); flattens lobes
  :113-123 with `svm_offset = -1` (:120); `PainterlyDeviceScene` (device_scene.h:23-67) owns `std::vector` arrays (:34-41) and `globals()` :45
  (a `PainterlyGlobalsCPU` by value), `bind_globals()` :58, the Embree scene. Nothing in the host scene stores a ShaderGraph, Shader,
  `Scene` (Cycles shim) or ImageManager.
- Session: session.cpp:54 `scene_->device_update(device_scene_)` on the caller thread; `PainterlySession(const PainterlyScene&, int)`
  (session.h:66) holds a `const PainterlyScene *` (:109); `render()` snapshots `device_scene_.globals()` (session.cpp:114).

### 3.11 _painterly bindings (material and scene API)
- src/blender/_painterly.pyi (CONTRACT :4): `:41-43 LobeKind = Literal["diffuse","mirror","glass","transparent"]; Lobe = tuple[LobeKind,
  tuple[float,float,float], float]`; `:49 "# --- materials: lobe mixtures (SPEC §6). M6 adds add_shader (SVM node graphs). ---"`; `:50-54
  add_material(self, lobes: list[Lobe], emission=(0,0,0)) -> int`; `:76-82 add_mesh(vertices (V,3) f32, triangles (T,3) u32, tri_material
  (T,) i32, corner_normals (T,3,3) f32 | None)` (no UV, no attributes); `:111 set_background(radiance)`; `:117-123 add_sun`; `:124-126 set_integrator`.
  Indices returned by add_* "are dense, starting at 0" :7.
- src/blender/python.cpp: `lobe_kind_from_python` :517-537; `nb::class_<PainterlyScene>(m, "Scene")` :678; `add_material` :681-704 (list of
  3-sequences -> `KernelPainterlyLobe`); `Session` :922. tests/core/test_api_contract.py:126-163 compares the pyi with the built module
  (names, parameter names, defaults), so a pyi change needs the binding change in the same card.

### 3.12 Add-on (src/blender/addon/)
- Modules: `__init__.py` (PainterlyRender), `engine.py` (facade; `init()` version check), `session.py` (render loop), `film.py`, `properties.py`
  (generated from `integrator_sockets()`; no `material.painterly`/`world.painterly` group yet), `ui.py`, `presets.py`, `operators.py`,
  `version_update.py`, `sync/__init__.py`, `sync/reference.py`.
- Today's sync: `sync/reference.py` builds SPEC §9 with `Scene.add_material` (`material_of` :86, `build_smallpaint_scene` :108) and
  `apply_reference_knobs` :63. `sync/__init__.py:15-30` `build_scene(depsgraph, settings, width, height)` raises
  `NotImplementedError("Blender scene sync arrives in M5")`; session.py:122-139 uses reference mode or `sync.build_scene`.
- M5 cards (not landed) specify `sync/material.py` `MaterialTable.material_index_of(material)` with constant mapping and "Linked inputs warn and use
  the default value until M6" (docs/tasks/M5/T5.3-sync-lights-world-materials.md:28-42; Principled -> diffuse/mirror/glass lobes), `sync/world.py`,
  `SyncStats`, `object_key` (T5.2). T5.4 (docs/tasks/M5/T5.4-reference-blend-parity.md) adds `tools/make_reference_scene.py`, `make reference-blend`.

### 3.13 What Cycles-side code exists per node batch (svm_nodes.toml: 32 includes, 66 cases; VENDORED.toml: 178 files, 301 fragments)
Registered NODE_DEFINE types (31): AddClosure, MixClosure, Attribute, Background, Brick, Bump, Checker, Clamp, Color, DiffuseBsdf, Emission, Geometry,
GlassBsdf, GlossyBsdf, Gradient, Magic, Math, MixClosureWeight, Noise, Output, Principled, RefractionBsdf, SetNormal, TextureCoordinate,
TransparentBsdf, Value, VectorMath, VectorTransform, Voronoi, Wave, WhiteNoise; plus ConvertNode (register_on_init), `BsdfBaseNode`, `BsdfNode`,
`TextureMapping`. Batch -> kernel cases vendored / host classes still without fragments:
1 Value, RGB, Math, VectorMath: cases yes / none missing. 2 Mix, MapRange, Clamp: cases yes (NODE_MIX*, NODE_MAP_RANGE, NODE_VECTOR_MAP_RANGE,
NODE_CLAMP) / MixNode, MixColorNode, MixFloatNode, MixVectorNode, MixVectorNonUniformNode, MapRangeNode, VectorMapRangeNode missing.
3 Invert, Gamma, BrightContrast, HSV: cases yes / all four classes missing. 4 Separate/Combine Color & XYZ: cases yes / SeparateColorNode,
CombineColorNode, SeparateXYZNode, CombineXYZNode missing. 5 ColorRamp, RGBCurves: NODE_RGB_RAMP, NODE_CURVES, NODE_FLOAT_CURVE yes
(`ramp_util.h` vendored for `RGBRampNode::constant_fold`, H/T6.3:157-159) / RGBRampNode, CurvesNode, RGBCurvesNode missing. 6 TexCoord,
Mapping: NODE_TEX_COORD, NODE_MAPPING, NODE_TEXTURE_MAPPING yes / MappingNode missing. 7-9 Noise, WhiteNoise, Voronoi, Checker, Gradient,
Wave, Magic, Brick: yes / yes. 10 Image Texture: NODE_TEX_IMAGE*, NODE_TEX_ENVIRONMENT yes / ImageSlotTextureNode, ImageTextureNode,
EnvironmentTextureNode missing (and `Scene::image_manager`). 11 BSDFs, Emission: yes / all seven present (Metallic, Sheen, Translucent,
Toon, SSS, Hair, Holdout, volumes not extracted). 12 Mix/Add Shader, Background: yes / present.
Reusable test helpers: src/test/cycles_svm_test_support.h (trace, `painterly_svm_test_shader_data`), cycles_svm_test_scene.h
(`PainterlySvmTestScene::bind/surface/background`, :32-131), cycles_scene_fixture.h, cycles_kernel_layout_probe.{h,cpp}.
Not vendored (absent from third_party/cycles; upstream copies under .cache/vendor/blender-v5.2.2/intern/cycles/kernel/): `geom/shader_data.h`
(`shader_setup_from_ray`, :47-134: sets `u, v, ray_length, type, object, object_flag, prim, wi`, calls `triangle_shader_setup`, then
`sd->flag = shaders[sd->shader & SHADER_MASK].flags`, backfacing flip), `geom/triangle_intersect.h` (`triangle_shader_setup` :168-190, reads
`tri_shader[sd->prim]` :170), `integrator/surface_shader.h` (`surface_shader_eval`, :1249; calls `svm_eval_nodes` :1285). Vendored:
`geom/{triangle,object,attribute,primitive}.h`. Parity tests that B4 must keep green: tests/core/test_oracle_parity.py (bit-identical,
analytic scenes, docs/tasks/M3/T3.16) and tests/core/test_triangle_path.py (T3.17).

## 4. The plan's M6b rows (.tmp/steward/plan/plan_gen.py:378-507; numeric ids from .tmp/steward/plan/ids-frozen.json in brackets)
INFRA list (:379-407), run rows `M6b.r.<Bn>` (mrow, :475-497), each "Bn: <text>". `needs` as coded:
| row [id] | title (INFRA text) | needs |
|---|---|---|
| M6b.brief [M6b.1] | Opus: the M6b brief (card list, interface names, acceptance per card) from the report section 8 and M6a's "for later cards" | M6a.G2 |
| r.B1 [20] | kernel globals: PainterlyGlobalsCPU holds Cycles' KernelData and arrays beside KernelPainterly; painterly/scene links cycles_scene, cycles_svm and cycles_kernel; the symbol audit stays clean | M6b.appr, M6a.T6.8 |
| r.B2 [21] | PainterlyScene::device_update() runs the shader manager: byte code, a shader per material slot, the BSDF lookup tables | r.B1 |
| r.B3 [22] | Cycles ShaderData from painterly hits (analytic spheres and planes, Embree triangles; normals, UVs and attributes in Cycles' layout) | r.B1 |
| r.B4 [23] | SVM in painterly_trace_pixel: the closure collector's lobes sampled per SPEC section 6, lobe choice by the section 2 hash, emission_gain; constant materials stay bit-identical (T3.16 parity still passes) (size 1-3 ids) | r.B2, r.B3 |
| r.B5 [24] | the world shader on misses (Background node graphs) | r.B4 |
| r.B6 [25] | bindings: the _painterly shader-graph API (create by Cycles type name, set by UI name, connect, assign to a material slot or the world) | r.B2, M3.T3.15 |
| r.B7 [26] | sync/shader/flatten.py: groups, reroutes and mutes; zones rejected with a message | M6b.appr, M5.T5.4 |
| r.B8 [27] | sync/shader/node_table.py and export.py: idname to Cycles type, socket renames, enum aliases; materials and the world exported by the scene sync | r.B6, r.B7 |
| r.B9 [28] | the golden-test harness: a generated .blend per node, Cycles at 1 spp (pixel centre, Raw, EXR) against Painterly (max_depth=1, emission_gain=1), with Cycles' own float32 spread measured first (size 1-3 ids) | r.B8, r.B5 |
| r.B10 [29] | image export from bpy (Image.pixels, colour space, alpha) and experiment X-colour, pre-registered in T6.8 (kind "experiment") | r.B9 |
| n.1..n.12 [30,54,55,56,31,32,57,58,59,33,34,35] | "Node batch i of 12: <name> (node-table rows and golden tests; parallel-safe)"; names = the 12 batches of plan.md:305 | r.B9; n.10 also r.B10; non-core (2,3,4,7,8,9) also M6b.appr2 |
| r.B11 [36] | node-material parity: the reference .blend with node materials against the oracle ensemble (T5.4's test through the SVM path) | n.11, n.12, M5.T5.4 |
| xcolour [60] | Opus: finalize the X-colour Conclusion | r.B10 |
| review [37] | Opus: M6b milestone review with a TQ audit | r.B11 + core n.1, 5, 6, 10, 11, 12 |
| FB/FN/FS [38,61,62] | review fix-ups (17 required cards; six other batches) | review |
Card-writing rows: `M6b.d.B1..B11` [2..12] "Draft card Bn" (need M6b.brief); `M6b.dn.1` [13] drafts batch 1 (the template); `M6b.dn.5` [14] drafts batches
5, 6, 10, 11, 12 in one task (dn.6/10/11/12 [15-18] are "merged"); `dn.2,3,4,7,8,9` [39-44] draft the other six; reviews `rvA/rvB/rvC`
[45-47] (B1-B11; six core batches; six other batches); `verify` [48]; `rev1..rev4` [49-52]; `appr` [19] ("Opus approves the 17 required M6b cards,
commits them to docs/tasks/M6b and adds their BACKLOG items"); `appr2` [53] (six other batches). Node batch card size is assumed like the M6a cards:
"1-3 ids" (plan_gen.py:34-35 `big6b`); .tmp/ds-queue/RULINGS.md:75-78 (R13): one task per large card, split only after a context-full exit or two failed rounds.

## 5. Risks that bind M6b (cycles_svm_report.md:843-882) and their state
| risk | text (short) | state at HEAD |
|---|---|---|
| R1 :858-860 | NODE_DEFINE registers through static initialisers; a static library may drop the node TUs; the registry must reference each `X::get_node_type()` | **Settled** by T6.4 (5fcd69d): generated `painterly_cycles_shader_node_types()` (src/cycles/shader_node_registry.h:24, tools/gen_fragment_units.py:36-50); doctests "the core node types are registered by name" (test_cycles_shader_graph.cpp:46), texture (test_cycles_texture_nodes.cpp:49), closure (test_cycles_svm_closures.cpp:261). **Open:** the first production caller must call it once before `NodeType::find` (H/T6.4:861) |
| R3 :865-867 | two socket name spaces (UI name vs member name); say which one the Python export uses | **Settled** by T6.4: "Socket naming" H/T6.4:1030-1043 and test `links use UI names; parameters use member names` (test_cycles_shader_graph.cpp:86). **Open:** the Python export implements it (B6, B8) |
| R4 :868-869 | Principled lower-layer weights depend on `lookup_table`; a missing or wrong LUT gives silently wrong weights | **Settled in C++** by T6.7 (e06f00a): `ShaderManager::device_update_lookup_tables` (shim shader.h:192), `bind_kernel_globals` sets `lookup_table` (shader_manager.h:149-150); tests "the lookup tables are uploaded where KernelTables points" (test_cycles_svm_closures.cpp:281), "Principled BSDF layers and the lookup tables" (:619). **Open:** `PainterlyScene::device_update` must call it after `device_update_post` and re-bind (no scene-level test) |
| R5 :870-871 | storage type and alpha association change 1-spp results; colour-space classification must come from Python | **Partly settled** by T6.8 (bb41b02): ImageManager reproduces upstream storage with explicit classes (image.h:46-77; 8 doctests, test_cycles_svm_images.cpp:202-705). **Open:** X-colour not run (no `experiments/*colour*`), no Python export, `Scene::image_manager`, image node classes; known H4(f) deviation (H/T6.8:176-178) |
| R6 :872-874 | MSVC searches includers' directories before `/I`; add a build test with shim markers | **Settled** by T6.1 (203c431): `PAINTERLY_SHIM_*` markers, src/cycles/shim_markers.cpp (OBJECT, in ALL, now covers the scene shims :48-56), tests/core/test_shims.py:99, :107. MSVC/macOS first compile in CI (experiment 011 README:429-431) |
| R8 :878-879 | closure/bundle/repeat zones only handled by C++ `inline_shader_node_tree`; flattener must reject or approximate; "behaviour not checked" | **Open.** No M6a card touched it; planned as B7 "zones rejected with a message" (plan_gen.py:394-395). No `sync/shader/` exists |
| B2 :850-852 | `features.h` cannot undefine `__SHADER_RAYTRACE__`, `__CAUSTICS_TRICKS__`, `__RAY_DIFFERENTIALS__`, `__DPDU__`; handled without a patch | **Settled** by T6.2 (7483c1f; generated switch has no ao/bevel/raycast cases, svm_nodes.toml) and T6.7 (`caustics_reflective/refractive = true`, shader_manager.h:346-347; mask without RAYTRACE, collect.h:39-40) |
Not asked: B1 (vendored types.h) settled by T6.1; B3 (atomic.h) by shim util/atomic.h (T6.8); R2 by T6.1 (all arrays declared); R9 (plan text) corrected at plan.md:59-61.

## 6. Gaps (what a card author needs and could not be found)
1. No M6b card text, brief or `docs/tasks/M6b` exists; `.tmp/steward/plan/plan_gen.py` rows are one-line titles. The three CONTRACT files M6b must change (`globals.h`,
   `types.h`, `_painterly.pyi`) need cards that list them (AGENTS.md:68-69).
2. SPEC is silent on node materials beyond :202 and :226: no rule for texture/image/colour semantics, UVs/attributes, how a world graph
   is evaluated (direction, relation to suns and `emission_gain`), whether node-material emission is scaled (T5.3 card :37 says `emission_scale` applies to lights only).
3. No policy for the Cycles `ShaderData` of an analytic hit (object, prim, type, shader id) or for the material index -> Cycles shader id
   (jump-table index `shader->id`, shader_manager.h:202) mapping; `PainterlyIntersection.prim` is mesh-local (globals.h:88), while Cycles indexes
   `tri_shader[sd->prim]` (triangle_intersect.h:170).
4. The mesh/binding contract has no UVs, attributes, `tri_shader`/`tri_vindex`/`tri_verts` arrays (pyi:76-82; globals.h:58-59); the kernel
   keeps no vertex array. `kernel_data.cam/film/integrator/max_closures` are filled by no production code (only rgb_to_y and caustics by the manager).
5. `shader_data.h`, `triangle_intersect.h`, `surface_shader.h` are not vendored (3.13); whether B3 vendors, fragments or writes the setup is open.
   The `ShaderData` fields that M6a tests set are P, N, Ng, wi, type, object, object_flag, prim, u, v (cycles_svm_test_scene.h:104-118), `flag`
   (test_cycles_svm_closures.cpp:128) and `num_closure`, `num_closure_left`, `lcg_state` (T6.7 Decision 6). Upstream's setup also writes `dPdu`/`dPdv`
   (`__DPDU__`, triangle_intersect.h:184-186), `time`, `ray_length` and `dP`, `dI`, `du`, `dv` (`__RAY_DIFFERENTIALS__`, shader_data.h:59, 67, 128-131).
   No M6a card or note says whether a painterly hit fills them.
6. M5 sync is absent (3.12): `MaterialTable`, `SyncStats`, `sync/world.py` exist only as card text; B7, B8, B11 need M5.T5.4. `make blender-it`,
   `reference-blend`, `tests/blender_it/`, `tools/make_reference_scene.py` do not exist. Blender 5.2 RNA identifiers, `get_output_node('CYCLES')`,
   `ColorRamp.evaluate`, `CurveMapping.evaluate`, `Image.pixels` semantics are "not checked" (report :886-889).
7. Golden harness: only plan.md:305 and B9's one-line text. Undefined: how Painterly hits the pixel centre (knob `jitter`, default 1/1400, spec.md:248,
   is not mentioned in plan.md:305), how "Cycles' own float32 spread" is measured, Cycles filter settings for 1 spp. `ShaderGraph::finalize`
   folds constant subgraphs on the host (H/T6.5:163-168), so a node whose inputs are all constants never reaches its SVM evaluator; plan.md:305
   does not say how the golden scenes vary the inputs. `rgb_to_y` is CPU-dependent and unpinned (.tmp/steward/landing/NEXT-LANDING.md:212-213).
8. Host classes missing for batches 2-6 and 10, and Metallic/Sheen/Translucent/Toon/SSS/Hair BSDFs (3.13); `NODE_*` for Holdout/volume cases are absent.
9. X-colour's experiment number is unassigned (highest is 011; M7-M9 cards also take "the next free number at run time", queue.md:95).
10. Report sections 1.1 and 4.1-4.7 are slated to be cut once M6b is drafted (DOC-MAP.md:93); I could not see CI results for M6a on MSVC/macOS.
