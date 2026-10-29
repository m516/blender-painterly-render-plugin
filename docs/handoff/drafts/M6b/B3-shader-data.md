# B3 — ShaderData from painterly hits, and the mesh's UVs
Milestone: M6b · Depends on: B1 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B3" (lines 137-159) and its section 1 decision 6
(lines 58-66), per that brief's section 4 (lines 303-324). Code facts are `docs/handoff/drafts/M6b/FACTS.md` §3,
re-read at this clone's HEAD in the files cited below.

## Goal
A painterly hit becomes a Cycles `ShaderData` that the vendored SVM can read, and the device scene carries the
Cycles arrays that the vendored node code reads it from (BRIEF.md:137-149).
- `painterly_svm_shader_setup(PainterlyGlobals kg, const PainterlyRay &ray, const PainterlyIntersection &isect,
  int cycles_shader, ShaderData *sd)` writes exactly the fields of `ShaderData`
  (`third_party/cycles/kernel/types.h:1019-1096`) that the vendored node and closure code reads, as Cycles'
  `shader_setup_from_ray` would (`shader_setup_from_ray` is upstream-only: `.cache/vendor` copy
  `intern/cycles/kernel/geom/shader_data.h:47-134`, not vendored — FACTS.md:340-343).
- It writes `ShaderData` through `kg->cycles` (`KernelGlobals`), the pointer B1's CONTRACT member adds
  (BRIEF.md:17-22). `PainterlyGlobalsCPU` itself holds no Cycles array, and the shim's `kernel_data_fetch` macro
  expands to `kg->name.fetch(index)` (`src/cycles/shim/kernel/device/cpu/globals.h:62`), which names the *free*
  identifier `kg`: inside this function `kg` is the `PainterlyGlobals` parameter, so the arrays are read through a
  local `const KernelGlobals cycles = kg->cycles;` with `cycles->name.fetch(index)` (or with a local named `kg`
  that shadows nothing — this card takes the first form).
- For a triangle hit, `sd->object` is the painterly object index, `sd->prim` the *global* triangle index
  (`mesh.tri_offset + isect.prim`), `type = PRIMITIVE_TRIANGLE`, and `u, v` in Cycles' barycentric convention.
  Step 2 derives that convention from the two vendored formulas: it is Embree's, unchanged.
- `PainterlyScene::device_update` fills Cycles' `objects`, `object_flag`, `tri_vindex`, `tri_verts`,
  `attributes_map`, `attributes_float2` (the active render UV map, corner element) and `attributes_float3`
  (Generated, vertex element) in Cycles' layout (T6.6:259-281), and `kernel_data.cam` from the painterly camera.
- `PainterlyScene::add_mesh` and CONTRACT `_painterly.pyi` `add_mesh` gain `corner_uvs: (T,3,2) float32 | None`
  and `generated: (V,3) float32 | None`.
- For an analytic sphere or plane there is no Cycles object or primitive: `object = OBJECT_NONE`,
  `prim = PRIM_NONE`, `type = PRIMITIVE_NONE`, `u = v = 0` (BRIEF.md:60-61). The nodes then compute what Cycles
  computes for such a point: object coordinates equal world coordinates (`object_inverse_position_transform_if_object`
  skips `OBJECT_NONE`, `third_party/cycles/kernel/geom/object.h:169-176`), and there are no attributes
  (`find_attribute` returns not-found for `OBJECT_NONE`, `third_party/cycles/kernel/geom/attribute.h:94-105`;
  `svm_node_attr_surface_eval` then falls back to the shading position for `ATTR_STD_GENERATED`,
  `third_party/cycles/kernel/svm/attribute.h:86-90`).

Nothing renders differently yet: no path calls the setup until B4, and the new arrays are read by no shipped code.
T3.16's bit-identical parity and T3.17's statistical test are the check that the device update changed nothing.

## Read first
- `CLAUDE.md` rules 1, 2 and 3; `AGENTS.md` "Expected values are evidence".
- `docs/handoff/drafts/M6b/BRIEF.md` lines 15-22 (decision 1), 58-66 (decision 6) and 137-159 (this card's
  mandate).
- The CONTRACT headers, read and never edited (`:4` is `CONTRACT: Opus-owned`): `src/painterly/kernel/globals.h`
  (`PainterlyGlobalsCPU` `:40-68`, `using PainterlyGlobals` `:70`, `PainterlyRay` `:72-76`, `PainterlyHitKind`
  `:78-82`, `PainterlyIntersection` `:84-91`) and `src/blender/_painterly.pyi` (`add_mesh` `:76-82`).
- B1's card, `docs/handoff/drafts/M6b/B1-kernel-globals.md`: step 2 (the private `KernelGlobalsCPU cycles_` and
  the `#include "kernel/globals.h"` in `device_scene.h`), step 3 (`cycles_.data.max_closures`), `## Interface`
  (`const KernelGlobalsCPU *PainterlyGlobalsCPU::cycles`, `const KernelGlobalsCPU &cycles_globals() const`) and
  Open for Opus 2 (B1 leaves it open whether the CONTRACT header *includes* `kernel/globals.h` or only forward
  declares `KernelGlobalsCPU`).
- The shim `src/cycles/shim/kernel/device/cpu/globals.h`: `kernel_array` `:31-45`, `KernelGlobalsCPU` `:49-57`,
  `using KernelGlobals` `:59`, the `kernel_data_*` macros `:62-65`, the `#error` `:24-26`.
- `third_party/cycles/kernel/types.h`: `OBJECT_NONE`/`PRIM_NONE` `:47-48`, `PRIMITIVE_NONE` `:686`,
  `PRIMITIVE_TRIANGLE`, `SHADER_MASK` `:493`, `differential` `:583-586`, `ShaderData` `:1019-1096` (its
  `__RAY_DIFFERENTIALS__` and `__DPDU__` members `:1059-1073`), `KernelCamera` `:1162-1249`, `KernelObject`
  `:1412-1460`, `AttributePrimitive` `:730-735`, `AttributeElement` `:737-762`, `AttributeStandard` `:766-805`,
  `AttributeMap` `:819-826`.
- `third_party/cycles/kernel/geom/triangle.h`: `triangle_interpolate` `:20-27` (the barycentric formula),
  `triangle_point_normal` `:65-96` (`w = 1 - u - v`, `P = w v0 + u v1 + v v2`), `triangle_attribute` `:293-334`
  (corner elements index `sd->prim * 3 + k` `:309-314`, vertex elements index `tri_vindex` `:303-308`).
- `third_party/cycles/kernel/geom/attribute.h`: `find_attr_offset` `:42-64` (the `ATTR_PRIM_TYPES` stride and the
  terminator), `find_attribute` `:66-112` (`prim == PRIM_NONE` `:80-84`, `OBJECT_NONE` `:99-101`),
  `attribute_data_fetch<float2>` `:125-130`, `attribute_data_fetch<float3>` `:132-141`,
  `attribute_data_fetch_3` `:217-241`.
- `third_party/cycles/kernel/geom/object.h`: `object_fetch_transform` `:33-41`, `object_get_transform` `:101-111`,
  `object_inverse_position_transform_if_object` `:169-176`, `object_inverse_normal_transform` `:180-203`.
- `third_party/cycles/kernel/svm/tex_coord.h`: `svm_texco_camera` `:77-89` (`cam.worldtocamera`,
  `camera_position`), `svm_node_tex_coord_eval` `:91-177` (`NODE_TEXCO_OBJECT` `:101-111`, `NODE_TEXCO_CAMERA`,
  `NODE_TEXCO_WINDOW` `:128-148` with `cam.width`/`cam.height`/`cam.worldtondc`), `svm_node_tex_coord` `:179-190`.
- `third_party/cycles/kernel/svm/attribute.h`: `svm_node_attr_init` `:21-44`,
  `svm_node_attr_surface_eval` `:67-155` (the `ATTR_STD_GENERATED` fallback `:86-90`, the `FLOAT2` branch
  `:101-122`), `svm_node_attr_surface` `:158-168`.
- `third_party/cycles/kernel/camera/camera.h`: `camera_position` `:531-535`, `camera_world_to_ndc` `:572-600`.
- `third_party/cycles/util/projection.h`: `ProjectionTransform` `:42-56`, `transform_perspective` `:70-78`,
  `make_projection` `:108-150`, `projection_identity` `:154-171`, `projection_inverse` `:207-224`,
  `operator*` `:225-238`.
- `third_party/cycles/util/transform.h`: `Transform` `:52-64`, `transform_point` `:79-96`,
  `make_transform` `:194-223`, `transform_scale` `:322-330`, `transform_translate` `:305-313`,
  `transform_inverse_impl` `:529-568`, `transform_inverse` `:572-584`.
- `third_party/cycles/util/types_float3.h:176-195` (`packed_float3`), `util/types_uint3.h:85` (`make_packed_uint3`),
  `util/types_spectrum.h:20` (`zero_spectrum`), `util/math_float3.h` (`zero_float3`, `normalize`).
- `third_party/cycles/kernel/features.h:141,145` (`__DPDU__` and `__RAY_DIFFERENTIALS__` are defined, so the
  `ShaderData` members of `types.h:1059-1073` exist), `kernel/util/differential.h:90-97` (`differential_zero`).
- The texture-coordinate compile: `third_party/cycles/fragments/scene/shader_nodes_cpp/member/TextureCoordinateNode.compile-SVMCompiler.inc`
  `:48-58` (Generated -> `NODE_ATTR`, `ATTR_STD_GENERATED`, `NODE_ATTR_OUTPUT_FLOAT3`), `:93-105` (UV -> `NODE_ATTR`,
  `ATTR_STD_UV`, `NODE_ATTR_OUTPUT_FLOAT3`), `:108-125` (Object -> `NODE_TEX_COORD`, `NODE_TEXCO_OBJECT`).
  Upstream: `.cache/vendor/blender-v5.2.2/intern/cycles/scene/shader_nodes.cpp:4076-4258`, `:4123-4134` and
  `:4168-4178`.
- Upstream, read-only under `.cache/vendor/blender-v5.2.2/intern/cycles/`: `scene/geometry_attributes.cpp:90-133`
  (the map entry and its `ATTR_PRIM_TYPES` stride), `:144-275` (the map layout: `(attr_count + 1) * ATTR_PRIM_TYPES`
  per geometry, then the terminator), `:298-543` (the attribute tables; `:417-421` the global-primitive
  correction `offset -= 3 * mesh->prim_offset` for corner elements), `scene/object.cpp:1080-1147` (the object's
  `attribute_map_offset` falls back to the geometry's, `:1088-1091`; `tfm`/`itfm` at `:575`, `:585`),
  `scene/mesh.cpp:905-914` (`pack_triangles`), `scene/shader_nodes.cpp` as above.
- `src/painterly/scene/`: `scene.h` (`add_mesh` `:65-70`), `scene.cpp` (`add_mesh` `:82-94`), `mesh.h` and
  `mesh.cpp` (`validate`), `device_scene.h` `:23-67` (`globals()` `:45`, `bind_globals()` `:55-58`),
  `device_scene.cpp` (`bind_globals` `:68-85`, `device_update` `:92-304`, the strong guarantee `:94-97`, the commit
  `:289-303`, the comment that says the device scene keeps no vertex array `:142-143`), `camera.h` `:46-74` and
  `camera.cpp` (`set_smallpaint` `:8-22` with `raster_to_camera` zero `:13-15`, `device_update` `:43-64`),
  `object.h:16-21`.
- `src/painterly/kernel/`: `geom/triangle.h:15-63` (`painterly_triangle_material`, the shading normal),
  `geom/analytic.h:100-107` (`painterly_analytic_normal`), `svm/collect.h:11-23` (the evaluation contract this
  setup must satisfy: `num_closure` 0, `num_closure_left` = `kernel_data.max_closures`, `lcg_state` 0,
  `SD_BACKFACING` clear), `integrator/path.h:64-65` (the signature) and `:89-100` (how a hit is turned into `P`, `N` and the material
  today),
  `camera/camera.h:30-40` (`painterly_camera_raster_to_camera`), `:57-88`
  (`painterly_camera_smallpaint_ray`; the smallpaint camera's `raster_to_camera` is unused).
- `src/test/`: `cycles_svm_test_scene.h:32-131` (the T6.6 minimal scene: the arrays, the terminator, the
  `attribute_map_offset` layout), `cycles_svm_test_support.h:313-329` (`painterly_svm_test_shader_data`),
  `test_cycles_svm_closures.cpp:47-143` (`make_scene`, `compile`, `evaluate` — the pattern the TexCoord test
  follows), `test_cycles_svm_textures.cpp:329-392` (TexCoord expectations of the T6.6 scene),
  `test_scene.cpp` (`add_mesh` call sites `:227`, `:418`, `:570`, `:572`, `:576`, `:579`, `:586`, `:614`, `:628`;
  the mesh-validation case `:564-606`), `test_triangle_diagnostics.cpp:202` (`add_mesh`).
- `src/blender/python.cpp`: `add_mesh` `:776-823` (the four arrays and their `nb::arg`s), `cast_array` and
  `object_to_world_from_python` in the same file.
- `tests/core/test_api_contract.py`: `_pyi_public_api` `:65-82`, `_runtime_signature` `:84-110`, the two signature
  tests `:141-168`, `test_add_mesh_accepts_the_contract_arrays` `:975-981`,
  `test_add_mesh_rejects_wrong_dtypes` `:983-994`,
  `test_add_mesh_rejects_wrong_shapes_and_non_contiguous_arrays` `:996-1016`; `tests/core/scenes.py:162` (a
  positional `None` for `corner_normals` that the new defaults keep valid).
- `src/test/CMakeLists.txt`: `painterly_tests` `:31-51`, the T6.1 block `:67-77`, the T6.6 block `:90-92`, the T6.8 block `:97-99`.
- The two parity tests this card must keep green unchanged: `tests/core/test_oracle_parity.py` and
  `tests/core/test_triangle_path.py`.

## Create
- `src/painterly/kernel/svm/shader_data.h`
- `src/test/test_svm_shader_data.cpp`
- `src/test/test_svm_tex_coord_hits.cpp`

## Modify
- `src/painterly/scene/mesh.h`, `src/painterly/scene/mesh.cpp`: the two optional arrays and their validation.
- `src/painterly/scene/scene.h`, `src/painterly/scene/scene.cpp`: `add_mesh`'s two new parameters.
- `src/painterly/scene/device_scene.h`: the Cycles arrays, their binding and the comment.
- `src/painterly/scene/device_scene.cpp`: build and commit them; extend `bind_globals`; write `cycles_.data.cam`;
  correct the "the device scene keeps no vertex array" comment (`:142-143`).
- `src/painterly/scene/camera.h`, `src/painterly/scene/camera.cpp`: `PainterlyCamera::device_update_cycles`.
- `src/test/CMakeLists.txt`: the two test sources in `painterly_tests`.
- `src/blender/python.cpp`: `add_mesh`'s two new optional arrays.
- `src/test/test_scene.cpp`: the nine `add_mesh` call sites.
- `src/test/test_triangle_diagnostics.cpp`: its one `add_mesh` call site (`:202`).
- `tests/core/test_api_contract.py`: one new test for the two arrays.

## Do not touch
- `src/painterly/kernel/globals.h`, `src/painterly/kernel/types.h`, `src/blender/_painterly.pyi`,
  `src/painterly/util/math_double3.h`, `src/painterly/util/types_double3.h`: CONTRACT files (`:4`). The `cycles`
  member is B1's and arrives before dispatch; the `add_mesh` parameters are Opus's and are quoted under
  `## Interface`. If the pyi has not been written when this card runs, stop and report (CLAUDE.md rule 1).
- `third_party/cycles/**` (vendored; `tools/vendor_sync.py` only) and `src/cycles/shim/**`. Decision 6: this card
  writes `ShaderData` itself and does not vendor `geom/shader_data.h`, `geom/triangle_intersect.h` or
  `integrator/surface_shader.h`.
- `src/test/cycles_svm_test_scene.h`, `src/test/cycles_svm_test_support.h`, `src/test/cycles_kernel_layout_probe.*`:
  T6.3 and T6.6's helpers, used as they are.
- `src/painterly/scene/svm/shader_manager.h`, `src/cycles/CMakeLists.txt`, `src/painterly/kernel/CMakeLists.txt`,
  `src/painterly/scene/CMakeLists.txt`, `src/painterly/bvh/**`: B1's build work.
- `tests/core/test_oracle_parity.py`, `tests/core/test_triangle_path.py`, `tests/core/scenes.py`: they must pass
  unchanged.
- `docs/architecture.md`, `Makefile`, `pyproject.toml`, `.github/workflows/**`.

## Interface
CONTRACT (Opus writes this before dispatch): `src/blender/_painterly.pyi`'s `add_mesh` gains two parameters after
`corner_normals`, exactly as BRIEF.md:147-149 gives them:

```
        corner_uvs: npt.NDArray[np.float32] | None = None,  # (T, 3, 2) the active render UV map
        generated: npt.NDArray[np.float32] | None = None,  # (V, 3) Blender's texture-space coordinates
```

with the comment on the method saying that `corner_uvs` is one UV pair per triangle corner and `generated` one
position per vertex, both object space, and that a mesh without them has no UV and no Generated attribute. The
defaults are `None` so that `tests/core/scenes.py:162` and the existing calls in `test_api_contract.py` (`:978`,
`:980`, `:987`, `:989`, `:991`, `:993`, `:1000`, `:1002`, `:1004`, `:1006`, `:1021`, `:1229`, and the two in
`tests/core/test_api_contract.py:638`, `:660` through `scenes.py`) keep their meaning. `python.cpp` must bind them in the same card (`tests/core/test_api_contract.py:141-168` compares the
pyi's names, defaults and order with the module's).

Not CONTRACT, and new names no other card depends on:

```cpp
/* painterly/kernel/svm/shader_data.h */
ccl_device void painterly_svm_shader_setup(PainterlyGlobals kg,
                                           const PainterlyRay &ray,
                                           const PainterlyIntersection &isect,
                                           int cycles_shader,
                                           ccl_private ShaderData *sd);
```

```cpp
/* painterly/scene/scene.h: the two optional arrays, in the order of the pyi. */
  int add_mesh(const std::vector<float> &vertices,
               const std::vector<uint32_t> &triangles,
               const std::vector<int> &tri_material,
               const std::vector<float> &corner_normals,
               const std::vector<float> &corner_uvs,
               const std::vector<float> &generated);
```

```cpp
/* painterly/scene/camera.h: the Cycles camera the vendored TexCoord node reads (decision 6).
 * KernelCamera is forward-declared in the header and defined by kernel/types.h in camera.cpp. */
  void device_update_cycles(KernelCamera &cam) const;
```

The C++ `add_mesh` takes the two arrays as required parameters (no default arguments) so that every caller states
what it passes; that is why the nine `test_scene.cpp` sites and the one in `test_triangle_diagnostics.cpp` are in
`## Modify`.

## Steps
1. Preconditions. Each must hold; otherwise stop, commit nothing and report what you saw.
   - B1 has landed: this prints `1` (the CONTRACT member of decision 1).
     ```
     grep -c 'KernelGlobalsCPU \*cycles' src/painterly/kernel/globals.h
     ```
   - B1's `cycles_` member and its `kernel/globals.h` include are in the device scene: this prints `2`.
     ```
     grep -cE 'KernelGlobalsCPU cycles_|#include "kernel/globals.h"' src/painterly/scene/device_scene.h
     ```
     The second line matters twice over: `std::vector<KernelObject>` and `std::vector<AttributeMap>` are complete
     types only with the shim's `kernel/globals.h`, and B1's `## Interface` leaves it open whether the CONTRACT
     header includes that shim header or only forward declares `KernelGlobalsCPU` (`B1-kernel-globals.md:110-116`).
     This card therefore includes `kernel/globals.h` from `device_scene.h` itself if B1's line is absent, and from
     `shader_data.h` unconditionally (step 2): neither file may rely on the CONTRACT header's choice.
   - The CONTRACT pyi parameters of `## Interface` are present: this prints `2`.
     ```
     grep -cE '^ *corner_uvs:|^ *generated:' src/blender/_painterly.pyi
     ```
     If it prints fewer than `2`, the contract has not arrived (or has arrived in part): stop and report.
   - The `add_mesh` call sites this card edits: `grep -c 'add_mesh' src/test/test_scene.cpp` prints `9` and
     `grep -c 'add_mesh' src/test/test_triangle_diagnostics.cpp` prints `1`.
   - The layout facts the card relies on: `grep -c 'ATTR_PRIM_TYPES' third_party/cycles/kernel/types.h` prints
     `1` (the enum's last entry, `:734`), and
     `grep -c 'p = (1 - u - v) v0 + u v1 + v v2' src/painterly/bvh/embree.h` prints `1`.
2. `src/painterly/kernel/svm/shader_data.h` (SPDX header; includes: `kernel/globals.h`, `kernel/types.h`,
   `kernel/util/differential.h` for `differential_zero`, then `painterly/kernel/geom/analytic.h`,
   `painterly/kernel/geom/triangle.h`, `painterly/kernel/globals.h`, `painterly/util/math_double3.h`).
   The barycentric convention first, because the rest of the function depends on it: both sides interpolate with
   the *same* three corners in the same order, so Embree's `(u, v)` is Cycles' `(u, v)` unchanged.
   - Embree/painterly: "the barycentrics of Embree's convention: p = (1 - u - v) v0 + u v1 + v v2"
     (`src/painterly/bvh/embree.h:13`), with the corners in index order (`:15-18`).
   - Cycles: `triangle_interpolate(u, v, f0, f1, f2)` returns `(1.0f - u - v) * f0 + u * f1 + v * f2`
     (`third_party/cycles/kernel/geom/triangle.h:23-27`), and `triangle_point_normal` computes
     `P = w * v0 + u * v1 + v * v2` with `w = 1.0f - u - v` (`:82-84`). So `f0` is corner 0, `f1` corner 1,
     `f2` corner 2, and Cycles' `u`/`v` are the weights of corners 1 and 2 — exactly Embree's. No swap, no
     `1 - u - v` re-assignment: `sd->u = isect.u; sd->v = isect.v`.
   - The same formula governs the corner attributes: `triangle_attribute` reads corner `sd->prim * 3 + k` with
     `f[k]` and interpolates with `(sd->u, sd->v)` (`:293-334`, `:309-314`), so a UV pair stored at corner
     `3 * global_prim + k` is interpolated with the weight Embree gave that corner.

   Then the function. `ccl_private` is empty on CPU (`third_party/cycles/util/defines.h:67`); it stays on the
   parameter as Cycles writes it. `-normalize(ray.d)` does **not** compile: `double3` has binary `+`, `-`, `*`, `/`
   and `normalize`/`len`/`dot`/`cross`, and no unary minus (`src/painterly/util/math_double3.h:23-70`), so the
   negated direction is written `normalize(ray.d) * -1.0`. The arrays are read as `cycles->name.fetch(index)`
   because the shim macro would expand to `kg->...` with `kg` = `PainterlyGlobals` (see `## Goal`).
   ```cpp
   /* The ShaderData of one painterly hit (BRIEF.md section 1, decision 6): exactly the fields the vendored
    * node and closure code reads, as shader_setup_from_ray() fills them (upstream
    * kernel/geom/shader_data.h:47-134, which is not vendored). Cycles arrays are read through kg->cycles
    * (decision 1). */
   ccl_device void painterly_svm_shader_setup(PainterlyGlobals kg,
                                              const PainterlyRay &ray,
                                              const PainterlyIntersection &isect,
                                              const int cycles_shader,
                                              ccl_private ShaderData *sd)
   {
     const KernelGlobals cycles = kg->cycles;

     /* surface_shader_eval()'s preparation (kernel/svm/collect.h:11-23): the shader, its flags, no closure
      * yet, Cycles' closure budget, no random number, no emission. */
     sd->shader = cycles_shader;
     sd->flag = cycles->shaders.fetch(cycles_shader & SHADER_MASK).flags;
     sd->lcg_state = 0;
     sd->num_closure = 0;
     sd->num_closure_left = cycles->data.max_closures;
     sd->closure_emission_background = zero_spectrum();
     sd->closure_transparent_extinction = zero_spectrum();

     /* Painterly has no ray differentials and no motion blur (decision 6). */
     sd->time = 0.0f;
     sd->ray_P = zero_float3();
     sd->ray_dP = 0.0f;
   #ifdef __RAY_DIFFERENTIALS__
     sd->dP = 0.0f;
     sd->dI = 0.0f;
     sd->du = differential_zero();
     sd->dv = differential_zero();
   #endif
   #ifdef __DPDU__
     sd->dPdu = zero_float3();
     sd->dPdv = zero_float3();
   #endif

     /* The hit point, the incoming direction (unit length) and the length of the ray (t * |d|, decision 6). */
     const double3 P = ray.o + ray.d * isect.t;
     sd->P = make_float3(P);
     sd->wi = make_float3(normalize(ray.d) * -1.0);
     sd->ray_length = float(isect.t * len(ray.d));

     if (isect.kind == HIT_TRIANGLE) {
       const KernelPainterlyMesh &mesh = kg->meshes[kg->objects[isect.index].mesh];
       sd->object = isect.index;
       /* Global triangle index: every corner attribute is addressed with it (triangle.h:309-314), and the
        * attribute map stores the offset corrected for it (upstream geometry_attributes.cpp:417-421). */
       sd->prim = mesh.tri_offset + isect.prim;
       sd->type = PRIMITIVE_TRIANGLE;
       sd->object_flag = cycles->object_flag.fetch(sd->object);
       sd->u = isect.u;
       sd->v = isect.v;
       /* The authored normal, unflipped: SD_BACKFACING stays clear, so the glass lobe sees the IOR Cycles
        * inverts on back faces (collect.h:17-23, SPEC §6). */
       const double3 N = painterly_triangle_shading_normal(kg, isect, ray, false);
       sd->N = make_float3(N);
       sd->Ng = make_float3(N);
     }
     else {
       /* Decision 6: an analytic sphere or plane has no Cycles object or primitive. */
       sd->object = OBJECT_NONE;
       sd->prim = PRIM_NONE;
       sd->type = PRIMITIVE_NONE;
       sd->object_flag = 0;
       sd->u = 0.0f;
       sd->v = 0.0f;
       const double3 N = painterly_analytic_normal(kg->analytic[isect.index], P);
       sd->N = make_float3(N);
       sd->Ng = make_float3(N);
     }
   }
   ```
   - `painterly_triangle_shading_normal(kg, isect, ray, false)` is the *unflipped* authored normal
     (`src/painterly/kernel/geom/triangle.h:23-63`); `sd->N = sd->Ng` because a painterly mesh's corner normals
     are a refinement of the same surface and B4's lobes carry no normal (BRIEF.md:73-74). Cycles would smooth
     `sd->N` only with `SHADER_SMOOTH_NORMAL` (`shader_setup_from_ray`, upstream `:105-112`), which v1 does not set.
   - `cycles_shader` is the material's `cycles_shader` (BRIEF.md:30-34); `SHADER_MASK` (`types.h:493`) is Cycles'
     own masking of the flag bits, exactly as `shader_setup_from_ray` does it (`:113`).
3. `src/painterly/scene/mesh.h`: after `corner_normals`, two fields with their comments, and `mesh.cpp`'s
   `validate()` gains two shape checks:
   ```cpp
     /* PAINTERLY_TRIANGLE_CORNERS * 2 floats per triangle (u0, v0, u1, v1, u2, v2), the active render UV map,
      * object space, or empty for a mesh without UVs. */
     std::vector<float> corner_uvs;
     /* PAINTERLY_POINT_FLOATS floats (x, y, z) per vertex, Blender's Generated texture coordinates, object
      * space, or empty for a mesh without them. */
     std::vector<float> generated;
   ```
   ```cpp
     if (!corner_uvs.empty() &&
         corner_uvs.size() != num_tris * size_t(PAINTERLY_TRIANGLE_CORNERS) * 2)
     {
       throw std::invalid_argument("PainterlyMesh: corner_uvs must have 6 floats per triangle");
     }
     if (!generated.empty() && generated.size() != size_t(num_verts) * size_t(PAINTERLY_POINT_FLOATS)) {
       throw std::invalid_argument("PainterlyMesh: generated must have 3 floats per vertex");
     }
   ```
   `num_verts` is the local `uint32_t(num_vertices())` the function already computes (`mesh.cpp:26`), so the
   `generated` check goes after that line and the `corner_uvs` check next to the `corner_normals` one
   (`mesh.cpp:20-25`).
   Each array is independent: a mesh may have UVs and no Generated, or the other way round (the attribute map of
   step 7 is built per mesh from what is present).
4. `src/painterly/scene/scene.h` and `scene.cpp`: `add_mesh` gains `const std::vector<float> &corner_uvs` and
   `const std::vector<float> &generated` after `corner_normals`, copies them into the `PainterlyMesh` beside the
   other three arrays (`scene.cpp:88-91`) and validates as it does today (`:92`); the function is `scene.cpp:82-95`. The doc comment
   (`scene.h:65-66`) gains one line: the two optional arrays, and that a mesh without them has no UV and no
   Generated attribute.
5. `src/painterly/scene/camera.h` and `camera.cpp`: `void device_update_cycles(KernelCamera &cam) const`, the
   Cycles camera of decision 6, filled from the painterly camera (`KernelPainterlyCamera`, `types.h:108-122`).
   `camera.h` gains only a forward declaration, `struct KernelCamera;`, beside its `CCL_NAMESPACE_BEGIN` — the
   header is included by `scene.h` and `session.h`, so it must not drag Cycles' `kernel/types.h`
   (`:1162-1249`) into every consumer, and a reference parameter needs no definition (the same choice B1's
   `## Interface` makes for `KernelGlobalsCPU`). `camera.cpp` gains `#include "kernel/types.h"`,
   `#include "util/projection.h"` and `#include "util/transform.h"`. Those are Cycles `kernel/` headers, so the
   target needs the one definition set: `painterly_scene` gets it through `painterly_kernel` → `cycles_svm` →
   `cycles_kernel` and `cycles_util` (B1 steps 5-7), which is why this card depends on B1. Only the shim
   `kernel/device/cpu/globals.h` `#error`s without `__MAX_CLOSURE__` (`:24-26`), and `kernel/types.h` does not
   include it.
   - `cam.type`, `cam.width`, `cam.height`: `CAMERA_PERSPECTIVE` for `PAINTERLY_CAMERA_PERSPECTIVE`,
     `CAMERA_ORTHOGRAPHIC` for `PAINTERLY_CAMERA_ORTHOGRAPHIC`, `CAMERA_PERSPECTIVE` for
     `PAINTERLY_CAMERA_SMALLPAINT` (`types.h:539`, `types.h:40-45`). Width and height are `float` in `KernelCamera`
     (`types.h:1217`) and `int` in the painterly camera: `float(cam.width)`.
   - `cam.cameratoworld`: `make_transform` of the twelve `camera_to_world` entries (`transform.h:194-223`), each
     `float(double)`. `cam.worldtocamera = transform_inverse(cam.cameratoworld)` (`transform.h:572-584`), which is
     what upstream does (`scene/camera.cpp:284`).
   - `cam.rastertocamera` and `cam.worldtondc`: `make_projection` of the sixteen `raster_to_camera` entries, each
     `float(double)` (`projection.h:108-150`), and
     ```cpp
     /* The Window output is the raster point's ndc: x = 2 col / W - 1, y = 2 row / H - 1, z = 0
      * (kernel/camera/camera.h:572-600 applies cam.worldtondc to the world point). The camera-space image
      * plane is z = -1 (painterly/kernel/camera/camera.h:73-77), so the chain is
      *   ndc <- raster <- image plane (u, v) <- camera space <- world.
      * raster_to_ndc: the definition above. plane_divide: (x, y, z, 1) -> (x / -z, y / -z, 0, 1).
      * plane_to_raster: the inverse of the raster -> (x, y) map, i.e. of the 3x3 homogeneous matrix whose rows
      * are raster_to_camera's rows x, y and w, in double (cofactor form), cast to float. */
     ```
     and `cam.worldtondc = raster_to_ndc * plane_to_raster * plane_divide * worldtocamera` with `operator*`
     (`projection.h:225-238`). This is the composition Cycles arrives at from `screentondc * cameratoscreen *
     worldtocamera` (`scene/camera.cpp:276-287`); painterly has no fov/nearclip, so the raster_to_camera matrix is
     the source of truth instead of a re-derived projection.
   - The smallpaint camera's `raster_to_camera` is all zero by construction (`camera.cpp:13-15`, and
     `camera.h:55-57`: "raster_to_camera stays zero, because the smallpaint ray is built from row, col and the
     image size alone"). So
     `cam.rastertocamera` and `cam.worldtondc` stay zero for it; `cam.type`, `cam.width`, `cam.height`,
     `cam.cameratoworld` and `cam.worldtocamera` are filled. Open for Opus 3 names the options.
6. `src/painterly/scene/device_scene.h`: the seven Cycles arrays, each a `std::vector` beside the painterly ones
   (`:33-41`), with the comment that they are Cycles' layout and that `device_update` builds them from the meshes
   and objects; and `bind_globals()`'s comment (`:55-58`) gains the Cycles arrays:
   ```cpp
     /* Cycles' triangle and attribute arrays (BRIEF.md section 1, decision 6; T6.6:259-281): the layout the
      * vendored triangle, attribute and texture-coordinate code reads through kg->cycles. */
     std::vector<KernelObject> cycles_objects;
     std::vector<uint> cycles_object_flag;
     std::vector<packed_uint3> cycles_tri_vindex;
     std::vector<packed_float3> cycles_tri_verts;
     std::vector<AttributeMap> cycles_attributes_map;
     std::vector<float2> cycles_attributes_float2;
     std::vector<packed_float3> cycles_attributes_float3;
   ```
   `packed_uint3`, `packed_float3`, `float2`, `KernelObject` and `AttributeMap` are `kernel/types.h`'s
   (`:36-37` of `data_arrays.h`, `types.h:819-826`, `types.h:1412-1460`); they are complete through B1's
   `#include "kernel/globals.h"` (step 1).
7. `src/painterly/scene/device_scene.cpp`. Build every Cycles array in a local, like the painterly ones, so the
   strong guarantee (`:94-97`) covers them; commit them with the rest (`:289-303`); then point `cycles_` at them in
   `bind_globals()` (`:68-85`). The writes go through B1's *non-const* member, `ds.cycles_`, which
   `friend class PainterlyScene` (`device_scene.h:51`) reaches: `globals().cycles` is
   `const KernelGlobalsCPU *` (BRIEF.md:18), so `globals_.cycles->data = ...` would not compile. The
   `KernelCamera` is a local `KernelCamera new_cycles_cam{}` assigned to `cycles_.data.cam` at the commit — a POD
   copy that cannot throw. Nothing else of `cycles_.data` is touched:
   `max_closures` is B1's constructor (`B1-kernel-globals.md` step 3) and B2's `device_update_common`
   (BRIEF.md:123-126).
   ```cpp
   /* --- Cycles' triangle and attribute arrays (decision 6). One vertex block per mesh, in mesh order, so
    * objects[].position_offset is the mesh's first vertex; one corner block per mesh for the UVs, and one
    * vertex block per mesh for Generated. The vertices also go to Embree, which copies them (T3.21, D35):
    * tri_verts is the copy Cycles' triangle code reads, and this is the array D35 said the device scene would
    * not keep. --- */
   std::vector<packed_float3> new_cycles_tri_verts;
   std::vector<packed_uint3> new_cycles_tri_vindex;
   std::vector<float2> new_cycles_attributes_float2;
   std::vector<packed_float3> new_cycles_attributes_float3;
   std::vector<AttributeMap> new_cycles_attributes_map;
   std::vector<KernelObject> new_cycles_objects;
   std::vector<uint> new_cycles_object_flag;
   ```
   - Per mesh, in the loop that already walks the meshes (`:151-179`). At the top of the iteration, before any
     append: `vertex_offset = new_cycles_tri_verts.size()`,
     `corner_offset = new_cycles_attributes_float2.size()`, and `tri_offset`, the running triangle count the loop
     already keeps (`:150`, `:178`); then
     `new_mesh_map_offsets.push_back(uint32_t(new_cycles_attributes_map.size()))` and
     `new_mesh_vertex_offsets.push_back(int(vertex_offset))`, two locals of type `std::vector<uint32_t>` and
     `std::vector<int>` that the object loop reads below (both are pushed before the mesh's own map entries, so
     the offsets are this mesh's). Then append the vertices as
     `packed_float3(make_float3(x, y, z))`, the indices as `make_packed_uint3(v0, v1, v2)`
     (`util/types_uint3.h:85`), the UV pairs as `make_float2(u, v)`, and the generated coordinates as
     `packed_float3`. Then emit the mesh's attribute map:
     ```cpp
     /* Upstream's map (scene/geometry_attributes.cpp:144-275): per geometry (attr_count + 1) *
      * ATTR_PRIM_TYPES entries, one pair per attribute (the second slot is the subdivision copy, zero) and a
      * terminator pair {ATTR_STD_NONE, element 0} that ends the search (kernel/geom/attribute.h:42-64). The
      * offsets are the ones the kernel reads: a corner element is indexed by the *global* triangle, so its
      * offset carries upstream's correction -3 * tri_offset (geometry_attributes.cpp:417-421); a vertex
      * element is indexed by the mesh-local vertex, so its offset is the mesh's first vertex. */
     if (!mesh.generated.empty()) {
       new_cycles_attributes_map.push_back(
           AttributeMap{uint64_t(ATTR_STD_GENERATED), int(vertex_offset),
                        uint16_t(ATTR_ELEMENT_VERTEX), uint8_t(NODE_ATTR_FLOAT3), 0});
       new_cycles_attributes_map.push_back(AttributeMap{});
     }
     if (!mesh.corner_uvs.empty()) {
       new_cycles_attributes_map.push_back(
           AttributeMap{uint64_t(ATTR_STD_UV), int(corner_offset) - 3 * tri_offset,
                        uint16_t(ATTR_ELEMENT_CORNER), uint8_t(NODE_ATTR_FLOAT2), 0});
       new_cycles_attributes_map.push_back(AttributeMap{});
     }
     new_cycles_attributes_map.push_back(AttributeMap{});
     new_cycles_attributes_map.push_back(AttributeMap{});
     ```
     `AttributeMap{}` is `{id 0 = ATTR_STD_NONE, offset 0, element 0, type 0}` — the terminator upstream writes
     with `element = false` (`geometry_attributes.cpp:122-133`). The id is the standard's own value, because
     `ShaderManager::get_attribute_id(AttributeStandard)` returns `(uint64_t)std` (`src/cycles/shim/scene/shader.cpp:96-99`).
     The corner offset is `corner_offset - 3 * tri_offset`, upstream's own correction
     (`geometry_attributes.cpp:417-421`): the kernel indexes a corner attribute with the *global* triangle
     (`kernel/geom/triangle.h:309-314`), so the stored offset has to give `corner_offset + 3 * local_prim` when
     the global index is added. The stored value can be negative (a mesh before this one with no UVs
     contributes nothing to `attributes_float2`), which is fine: it is an `int` and only the sum is read.
   - Per object, in the loop that already walks the objects (`:184-205`): the `KernelObject` fields the vendored
     code reads. `tfm`/`itfm` from the painterly `object_to_world` (`object.h:18-19`), as upstream
     (`scene/object.cpp:575,585`); `attribute_map_offset` = `new_mesh_map_offsets[size_t(object.mesh)]`
     (upstream falls back to the geometry's, `scene/object.cpp:1088-1091`); `position_offset` =
     `new_mesh_vertex_offsets[size_t(object.mesh)]`, the mesh's first vertex (`triangle.h:33-37`);
     `normal_offset = ATTR_STD_NOT_FOUND` (smooth normals are outside v1, BRIEF.md:73-74); `numverts` and
     `numprims`; `dupli_generated`/`dupli_uv` stay zero, which is what the Dupli outputs read
     (`kernel/svm/tex_coord.h:153-159`). `new_cycles_object_flag.push_back(0)`: painterly objects are instances
     with an `object_to_world`, so neither `SD_OBJECT_TRANSFORM_APPLIED` nor `SD_OBJECT_NEGATIVE_SCALE` is set
     (`kernel/geom/object.h:180-203`, `:218-221`), and Cycles' instance path then maps object space to world with
     `itfm`.
   - `new_cycles_cam`: `camera.device_update_cycles(new_cycles_cam)` next to `camera.device_update(new_data.cam,
     ...)` (`:209`).
   - Commit, after the existing ones and before `ds.bind_globals()` (`:303`):
     ```cpp
     ds.cycles_objects = std::move(new_cycles_objects);
     ds.cycles_object_flag = std::move(new_cycles_object_flag);
     ds.cycles_tri_vindex = std::move(new_cycles_tri_vindex);
     ds.cycles_tri_verts = std::move(new_cycles_tri_verts);
     ds.cycles_attributes_map = std::move(new_cycles_attributes_map);
     ds.cycles_attributes_float2 = std::move(new_cycles_attributes_float2);
     ds.cycles_attributes_float3 = std::move(new_cycles_attributes_float3);
     ds.cycles_.data.cam = new_cycles_cam;
     ```
     `ds.cycles_` is reachable because `PainterlyDeviceScene` already declares `friend class PainterlyScene`
     (`device_scene.h:51`).
   - `bind_globals()` (`:68-85`), after the painterly lines, one `cycles_.name.data = array_or_null(...)` and
     `cycles_.name.width = int(...)` per array (the same `array_or_null` helper, `:60-63`). An empty array is a
     null pointer with width 0, which is what `KernelGlobalsCPU`'s `kernel_array` defaults are
     (`src/cycles/shim/kernel/device/cpu/globals.h:31-45`).
   - The comment at `:142-143` ("the device scene keeps no vertex array (T3.21, D35)") is now false: replace it
     with the reason `tri_verts` exists (Cycles' triangle and attribute code reads positions) and say that D35's
     rule still holds for the *painterly* kernel arrays, which keep no vertices.
8. `src/test/test_svm_shader_data.cpp`: four doctest cases, `## Acceptance` counts. Include `cycles_svm_test_scene.h`
   only if a case needs it — these four do not: they build a `PainterlyScene`, call `device_update`, and read
   `ds.cycles_globals()`. The mesh of case 1: a quad in object space with vertices `(0,0,0) (1,0,0) (0,1,0)
   (1,1,0)`, triangles `(0,1,2)` and `(3,1,2)`, one material, one object with `object_to_world` = translate
   `(1, 2, 4)` (dyadic, so every product below is exact), and `isect = {t, HIT_TRIANGLE, index 0, prim 1, u =
   0.25f, v = 0.5f, Ng}`.
   - Case "painterly svm shader data: a triangle hit carries the mesh's own data": every field of step 2. The
     derivation is written in the test: `P = ray.o + ray.d * t` in double, `P_float = make_float3(P)`,
     `w0 = 1 - u - v` from the `float` barycentrics widened to double as `painterly_triangle_shading_normal` does
     (`geom/triangle.h:46-52`), `Ng` from `cross(v1 - v0, v2 - v0)` in double over the world vertices,
     `N = normalize` of the interpolated corner normal mapped by `painterly_normal_matrix`
     (`util/math_double3.h:127-161`). The comparison is exact because it repeats the same double operations in the
     same order; the dyadic closed forms (`P`, `u`, `v`, `object`, `prim`, `ray_length` for the unit `wi`) are
     additionally checked as literals. Also checked: `shader`, `flag` = `KernelShader::flags` of the shader,
     `num_closure == 0`, `num_closure_left == MAX_CLOSURE`, `lcg_state == 0`, `time == 0`, the zero
     `dP/dI/du/dv/dPdu/dPdv`, `closure_emission_background == zero_spectrum()`, `object_flag == 0`, and
     `SD_BACKFACING` clear.
   - Case "painterly svm shader data: an analytic hit has the NONE values": a sphere and a plane, `isect.kind =
     HIT_ANALYTIC`, `index` the primitive: `object == OBJECT_NONE`, `prim == PRIM_NONE`, `type == PRIMITIVE_NONE`,
     `u == 0`, `v == 0`, `N == Ng == make_float3(painterly_analytic_normal(...))`, `P`, `wi` and `ray_length` as
     above.
   - Case "painterly svm shader data: the device scene fills Cycles' arrays": a scene of two meshes (the quad, and
     a one-triangle mesh) instanced by two objects, the second mesh with UVs and Generated, the first without.
     Checked: `cycles_globals().objects.width == 2`; each object's `position_offset` is its mesh's first vertex;
     `tri_vindex[global]` equals the mesh's indices; `tri_verts[position_offset + i]` equals the mesh's vertex
     `i`; `attributes_map` holds, for the mesh with both arrays, `{ATTR_STD_GENERATED, offset, VERTEX,
     NODE_ATTR_FLOAT3}` then `{ATTR_STD_UV, offset, CORNER, NODE_ATTR_FLOAT2}` then the terminator pair, and for
     the mesh without them only the terminator pair; `attributes_float2[desc.offset + 3 * global_prim + k]` is
     corner `k`'s UV pair and `attributes_float3[desc.offset + v]` is vertex `v`'s generated coordinate — the
     indices the vendored code computes (`kernel/geom/triangle.h:303-314`, `:293-334`); and the cam fields of
     step 5. An empty scene leaves every one of the seven arrays at width 0 and a null pointer.
   - Case "painterly svm shader data: add_mesh validates the two optional arrays": a wrong number of UV floats, a
     wrong number of generated floats, and the accepted forms (UV only, Generated only, both, neither) with the
     indices `add_mesh` returns.
9. `src/test/test_svm_tex_coord_hits.cpp`: two doctest cases, the same `make_scene`/`compile`/`evaluate` pattern as
   `test_cycles_svm_closures.cpp:47-143` (`cycles_svm_test_support.h` must precede every `kernel/svm/` header, as
   its comment says). A `TextureCoordinateNode` whose Generated, UV and Object outputs are each linked to an
   `Emission` node's Color in three separate graphs (each compiled, each evaluated at the same hit), and the value
   read from `sd.closure_emission_background` after `svm_eval_nodes`. Three facts make that value the node's output:
   the TexCoord outputs are `POINT` and `Emission`'s Color is `COLOR`
   (`.cache/vendor/.../scene/shader_nodes.cpp:4034-4040`, `:3060`), a conversion whose `convert_type()` is
   `NODE_CONVERT_NONE` (`:2087-2103`) compiles to `compiler.stack_link` with no byte code
   (`:2124-2130`); `Emission`'s Strength is set to `1.0f` in the test (its default is `10.0f`, `:3061`); and
   `emission_setup` stores that weight in `closure_emission_background` (`third_party/cycles/kernel/closure/emissive.h:29-38`,
   reached from `kernel/svm/closure.h:1406-1430`).
   - Case "painterly svm texture coordinate: UV, Generated and Object of a triangle hit": the graph of the compile
     fragment (`TextureCoordinateNode.compile-SVMCompiler.inc:48-58` for Generated, `:93-105` for UV — both
     `NODE_ATTR` — and `:108-125` for Object, `NODE_TEX_COORD`), evaluated on the `ShaderData` that
     `painterly_svm_shader_setup` writes for two hits (a triangle of the first mesh and one of the second, so the
     corner-UV correction of step 7 is exercised). Expected values derived in the test, in float32 by repeating
     Cycles' operations in the same order: UV = `triangle_interpolate(u, v, uv[3p+0], uv[3p+1], uv[3p+2])`
     (`kernel/geom/triangle.h:23-27`, `:322-330`), Generated = the same interpolation over `tri_vindex`'s vertices
     (`:303-308`), Object = `P` mapped by the object's `itfm` (`kernel/geom/object.h:169-176`,
     `kernel/svm/tex_coord.h:101-111`) — with the dyadic mesh and the dyadic translation, every product is exact.
   - Case "painterly svm texture coordinate: an analytic hit has no attributes": at a plane hit, UV is
     `(0, 0, 0)` (not found, `svm_node_attr_surface_eval`'s `float2` branch is skipped, `:147-154`),
     Generated is the shading position (the fallback at `:86-90`, with no object transform because `object ==
     OBJECT_NONE`), and Object is the shading position too (`:101-111`).
10. `src/test/CMakeLists.txt`: `target_sources(painterly_tests PRIVATE test_svm_shader_data.cpp
    test_svm_tex_coord_hits.cpp)` in a new block with a comment naming this card, after the T6.8 block (`:97-99`).
    Both files need `painterly_scene` and `cycles_scene`/`cycles_svm`, which `painterly_tests` already links
    (`:48-50`, `:92`, `:99`); `test_svm_tex_coord_hits.cpp` includes `scene/shader_nodes.h` through
    `painterly/scene/svm/shader_manager.h`, so it needs `ccl=painterly`, which B1 step 9 adds PRIVATE to
    `painterly_tests`.
11. `src/blender/python.cpp`, `add_mesh` (`:776-823`): two more `nb::object` parameters after `corner_normals`,
    each converted with `cast_array<float>` and checked like `corner_normals` is (`:798-810`), then passed on:
    ```cpp
            std::vector<float> corner_uv_values;
            if (!corner_uvs.is_none()) {
              const auto uv_array = cast_array<float>(corner_uvs, "Scene.add_mesh: corner_uvs");
              if (uv_array.ndim() != 3 || uv_array.shape(0) != triangle_array.shape(0) ||
                  uv_array.shape(1) != PAINTERLY_TRIANGLE_CORNERS || uv_array.shape(2) != 2)
              {
                throw nb::type_error("Scene.add_mesh: corner_uvs must have shape (T, 3, 2)");
              }
              corner_uv_values.assign(uv_array.data(), uv_array.data() + uv_array.size());
            }
    ```
    and the same for `generated` with `(V, 3)`, `vertex_array.shape(0)` and `PAINTERLY_POINT_FLOATS`; `nb::arg`
    for both with `nb::none()`, in the pyi's order.
12. The ten C++ `add_mesh` call sites: `src/test/test_scene.cpp` `:227`, `:418`, `:570`, `:572`, `:576`, `:579`,
    `:586`, `:614`, `:628` and `src/test/test_triangle_diagnostics.cpp:202` pass `{}` for `corner_uvs` and `{}`
    for `generated`. Nothing else in either file changes; `test_scene.cpp`'s mesh-validation case (`:564-611`)
    keeps its five `CHECK_THROWS_AS` unchanged.
13. `tests/core/test_api_contract.py`: one new test after `test_add_mesh_accepts_the_contract_arrays` (`:975-981`),
    `test_add_mesh_accepts_and_rejects_the_uv_and_generated_arrays`: `add_mesh(VERTICES, TRIANGLES, TRI_MATERIAL,
    None, uvs, generated)` returns 0 with `uvs = np.zeros((1, 3, 2), np.float32)` and
    `generated = np.zeros((3, 3), np.float32)`; each of `uvs.astype(np.float64)`, a `(1, 3)` UV array, a `(1, 2,
    2)` UV array, `generated.astype(np.float64)` and a `(4, 3)` generated array raises `TypeError`. The module's
    names and defaults are already compared with the pyi by `:141-168`, so this test adds only the shapes and the
    dtypes.
14. `make format`, then every acceptance command.

## Acceptance
Run every command from the repository root; the queue translates them with BACKLOG.md's table (`make check` →
`CHECK`, `build/dev` → `build/q`, `.venv/bin/<tool>` → `MAIN/.venv/bin/<tool>`, `python -I` → `PYTHONPATH="$PWD/analysis" … -P -s`).
1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and the audit's
   `RESULT: PASS` line.
2. `make audit` prints `RESULT: PASS`: `painterly_svm_shader_setup` is a `ccl_device` function (static on CPU,
   `util/defines.h:25-27`) and `device_update_cycles` is a member of a `painterly_scene` class, so the module's
   exports do not change.
3. `build/dev/src/test/painterly_tests --test-case='painterly svm shader data*'` exits 0 and prints
   `test cases: 4 | 4 passed | 0 failed` — the four cases of step 8.
4. `build/dev/src/test/painterly_tests --test-case='painterly svm texture coordinate*'` exits 0 and prints
   `test cases: 2 | 2 passed | 0 failed` — the two cases of step 9.
5. `build/dev/src/test/painterly_tests --test-case='painterly scene: device_update*'` exits 0 and prints
   `test cases: 3 | 3 passed | 0 failed`: the three cases of `test_scene.cpp` (`:438` `flattens the materials and
   the meshes`, `:802` `fills the camera, the integrator and the background`, `:898` `keeps the device scene on
   every throwing path`), unchanged, so the painterly arrays and the strong
   guarantee still hold with the Cycles arrays beside them.
6. `.venv/bin/python -m pytest -q tests/core/test_api_contract.py` prints `32 passed`: the file's 31 test
   functions (`grep -c '^def test_' tests/core/test_api_contract.py` prints `31`, and the file has no
   `parametrize`, so 31 items) plus the one of step 13.
7. `.venv/bin/python -m pytest -q -m slow tests/core/test_oracle_parity.py tests/core/test_triangle_path.py` prints
   `2 passed, 53 deselected`: the two slow tests, unchanged. The counts are the files' own:
   `test_oracle_parity.py` holds 3 unparametrized tests (`:125`, `:138`, `:162`), the 12 `DESIGN` entries
   (`:74-87`) × the 4 `CORE_CONFIGS` (`:91-96`) = 48 parametrized items, and 1 slow test (`:366-367`), so 52
   items; `test_triangle_path.py` holds `:156`, `:183` and the slow `:272-273`, so 3. 52 + 3 = 55 items, of which 2
   are `slow`, so the `-m slow` run selects 2 and reports `55 - 2 = 53` deselected.
8. `git status --porcelain` lists only the three Create paths and the ten Modify bullets above (thirteen files).

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- `sd->prim = isect.prim` (mesh-local) instead of the global index → acceptance 3 and 4 fail (the UV of the
  second mesh's triangle reads the wrong corners);
- swap `sd->u` and `sd->v` → acceptance 3 fails on the closed-form `u`/`v` and on the interpolated corner normal;
- `sd->wi = make_float3(ray.d)` without the normalize and the sign → acceptance 3 fails;
- `sd->num_closure_left = 0` → acceptance 3 fails (the collector's contract, `collect.h:17-18`);
- `sd->object = 0` in the analytic branch → acceptance 3's analytic case fails;
- drop `position_offset` from `KernelObject` (leave it 0) → acceptance 3 fails on the second mesh's
  `tri_verts`, and acceptance 4 fails on Generated;
- drop the `- 3 * tri_offset` correction of the corner UV offset → acceptance 4 fails on the second
  mesh's triangle;
- write the terminator pair with `element = 1` instead of 0 → `find_attr_offset` chains past the end of the mesh's
  map (`kernel/geom/attribute.h:49-61`) and acceptance 3 and 4 fail;
- omit `cam.worldtondc`'s `plane_divide` factor → acceptance 3's camera check fails;
- remove the new `validate()` checks → acceptance 3's validation case fails;
- drop `corner_uvs` from the `python.cpp` signature → acceptance 6 fails in
  `test_every_public_name_and_parameter_matches_the_pyi`.

Report: the doctest counts of acceptances 3-5, the pytest counts of 6 and 7, the audit line, and every mutation you
ran with its first failing check.

## Commit
`B3: ShaderData from painterly hits, and the mesh's UVs`

## Open for Opus
1. **`tri_verts` contradicts D35's "the device scene keeps no vertex array".** The comment at
   `device_scene.cpp:142-143` states it and cites T3.21/D35. Decision 6's list (BRIEF.md:144-146) needs the
   positions, because the vendored triangle and attribute code reads them from `tri_verts`
   (`kernel/geom/triangle.h:33-37`, `:303-308`). This card keeps the painterly arrays as they are (they still hold
   no vertices) and adds Cycles' copy, and says so in the corrected comment. The options: (a) keep this (one
   `packed_float3` copy per vertex beside Embree's); (b) let the kernel read positions from the BVH's copy through
   an accessor, which is a new painterly API and touches `painterly/bvh/`; (c) drop corner normals from the
   generated path and read positions only when a node needs them, which cannot work because the attribute map is
   built before the shader is known. This card takes (a).
2. **Two attributes, one array.** `attributes_float2` holds only the active render UV map and `attributes_float3`
   only Generated, because those are the two the core six batches read (decision 6, T6.6:259-281). Any further
   attribute (Vertex Color, a second UV map, an image's own UV) is a later card's: the layout above generalises by
   appending to the same two vectors and emitting one more map pair per attribute.
3. **The smallpaint camera has no Cycles camera.** Its `raster_to_camera` is zero by construction
   (`camera.cpp:13-15`), so `Window` and `Camera` have no meaning on a smallpaint-camera scene: this card leaves
   `cam.rastertocamera` and `cam.worldtondc` zero there (both read as `(0, 0, 0)`), fills the rest, and the golden
   tests (B9) use a perspective or orthographic camera. The options: (a) keep the zero matrices; (b) write the
   smallpaint camera's own raster_to_camera from `painterly_camera_smallpaint_ray`'s expression
   (`painterly/kernel/camera/camera.h:57-88`), which makes `Window` the pixel's ndc but needs `tan(fovx)` in float
   and cannot be compared exactly against the double ray code. This card takes (a).
4. **`ShaderData::N` is the hit's shading normal, never a smoothed one.** Without corner normals
   `sd->N = sd->Ng`; with corner
   normals, `painterly_triangle_shading_normal(kg, isect, ray, false)` gives the interpolated one, and `sd->N` is
   set to the same value. Cycles would keep `sd->N` smooth only under `SHADER_SMOOTH_NORMAL` (upstream
   `kernel/geom/shader_data.h:105-112`), which B2 does not set. A later card that sets that flag must also fill
   `attributes_normal`, which decision 6 does not list.
5. **`object_flag` is always zero.** Painterly objects are instances with an `object_to_world`, so Cycles' instance
   path (`kernel/geom/object.h:180-203`) is the right one and `SD_OBJECT_TRANSFORM_APPLIED` must stay clear. The
   array is therefore filled with zeros, one per object, and read by the setup — the same value Cycles would have.
   If a later card lets a painterly object carry pre-applied vertices, the flag becomes meaningful.
6. **The camera's float matrices.** `KernelCamera` holds floats and the painterly camera doubles, so
   `device_update_cycles` rounds. The doctest of step 8 compares the fields against the same `float(double)`
   rounding, and the Window chain against the closed form at 64 pixel centres of an orthographic camera with dyadic
   entries (measured while this card was written: 0 mismatches of 64; the same check on a perspective camera's
   image-plane point: 0 of 64; on a perspective hit point, 36 of 64 differ in the last bit, because the ray
   direction's `z` is not exactly -1 after the float32 normalize, so no exact claim is made for `Window` on a
   perspective camera). If Opus wants `Window` exact on perspective cameras too, the chain has to be evaluated in
   double, which `KernelCamera` cannot hold.
