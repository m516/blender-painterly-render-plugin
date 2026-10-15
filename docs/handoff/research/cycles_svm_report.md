# Cycles SVM in Painterly (M6): technical research report

Source: Blender tag `v5.2.2`, commit `d13f752e3b9c4f8c261cda552b1021f8bcc0382c`, sparse clone of `intern/cycles`
(GitHub mirror, `--filter=blob:none`). All paths below are relative to `intern/cycles/` unless stated.
Line ranges are for that commit. Nothing was compiled or executed from the clone; all findings come from reading
text plus small text-scanning scripts kept in `scratchpad/tools/` (`inc_closure.py`, `nodes_index.py`,
`dispatch.py`, `emits.py`, `scan.sh`). Raw outputs are in `scratchpad/research/`
(`svm_scan.txt`, `nodes_index.json`, `m6_subset_closure.txt`, `closure_calls.txt`).

"Not checked" marks things outside this sparse clone or not verified: Blender DNA/RNA/node definitions under
`source/blender/`, `intern/atomic`, `intern/sky`.

---

## 0. Executive summary

1. **SVM in 5.2.2 is typed.** Each node is a plain struct in `kernel/svm/node_types.h`, read from the byte code with
   `svm_node_get<T>(kg, &offset)` (`kernel/svm/util.h:204-213`). The host writes it with
   `SVMCompiler::add_node(ShaderNode*, ShaderNodeType, const T&)` (`scene/svm.h:95-112`) using C++20 designated
   initializers. Dispatch is a **hand-written `switch`** in `svm_eval_nodes` (`kernel/svm/svm.h:101-622`), not
   generated code.
2. **The plan's "104 `SVMNode*` structs; each takes only the stack and a typed node" needs correcting.**
   - The 104 structs are 90 node-parameter structs plus 14 trailing `*Data` payload structs, e.g.
     `SVMNodeGlassBsdfData`, which follow `SVMNodeClosureBsdf`.
   - Of 108 dispatch cases, only **43** call an evaluator with `(stack, node)` alone. **49** read `ShaderData`,
     **8** read `KernelGlobals` but not `sd`, and 8 are closure-weight, jump or AOV special cases (§1.3).
3. **A verbatim `kernel/svm/svm.h` is not usable for painterly.**
   - `kernel/features.h:131` defines `__SHADER_RAYTRACE__` unconditionally on CPU, so `svm.h` includes `ao.h`,
     `bevel.h` and `raycast.h`. These pull in Cycles' BVH (`kernel/bvh/*`, 10 headers) and `IntegratorState`.
   - The plan's generated switch (T6.4) is therefore required, not just convenient.
   - Its include closure is 201 files / 49.4k lines. The M6 evaluator subset is **149 files / 36.9k lines**
     (§3.5, §4.6).
4. **Closures need no shim.**
   - `closure.h` writes closures into `sd->closure[]` through `kernel/closure/alloc.h`.
   - Emission and background accumulate in `sd->closure_emission_background`.
   - A painterly "closure collector" can be a **post-pass that reads `ShaderData` after evaluation** (§3.4).
   - The cost: `closure.h` hard-includes all 26 `kernel/closure/*.h` headers and calls 50 closure-library functions.
     Microfacet, sheen and principled setup read **BSDF lookup tables** (`kernel_data.tables.*` into
     `lookup_table`).
   - For Principled, those tables change the **weights** of lower layers (`closure.h:141, 174, 470`; the diffuse lobe uses the attenuated weight at 515-520). Painterly
     must therefore load `scene/shader.tables` (pure data, vendorable).
5. **Painterly must use Cycles' own `ShaderData`, `ShaderClosure`, `KernelData` and `kernel/types.h`, verbatim.**
   - Vendored headers touch dozens of fields at compile time.
   - Plan T3.3 ("`kernel/types.h`, `globals.h` (KernelData {Camera, Film, Background, Painterly})…: contract written
     by Opus") is **incompatible** with vendored SVM if it means a painterly-owned `kernel/types.h`.
   - Recommended: vendor `kernel/types.h` verbatim. Keep painterly data in a separate struct next to `KernelData`
     inside a painterly `KernelGlobals` (§8, blocker B1).
6. **Host side is feasible with an include-shadowing shim layer plus function-anchored fragment extraction.**
   - Vendor verbatim, with shims: `graph/`, `scene/shader_graph.{h,cpp}`, `scene/constant_fold.{h,cpp}`,
     `scene/svm.h`, `scene/shader_nodes.h`.
   - Extract rather than compile whole: `scene/shader_nodes.cpp` (8424 lines) pulls in `ImageManager`,
     `LightManager`, `Film`, `Geometry`, attributes and `intern/sky`. `scene/svm.cpp` lines 33-155 (`SVMShaderManager`)
     pull in Device, TaskPool and LightManager.
   - Per-node fragments: `NODE_DEFINE` + member functions. Compiler fragment: `SVMCompiler`, lines 157-1281.
   - `scene/shader_graph.cpp` itself hard-references 13 node classes, which therefore form the mandatory "core node
     set" (§4.4).
7. **Blender sync is mostly portable to Python tables, with one gap.** 5.2 inlines groups with the C++-only
   `blender::nodes::inline_shader_node_tree` (`blender/shader.cpp:1525-1545`). The Python flattener must reimplement
   group, reroute and mute handling; the logic is still present in `add_nodes_inlined`, lines 1334-1523.
8. **SVM evaluation consumes no random numbers if `sd->lcg_state == 0` and images are untiled.** `lcg_state` is only
   read by tiled-image mip selection (`kernel/util/image_2d.h:102-108`) and the Huang hair BSDF. Noise, Voronoi and
   White Noise use only `util/hash.h` plus math, so the SVM never perturbs K (SPEC §2).

---

## 1. `kernel/svm/`: headers, node types, signatures, dispatch

### 1.1 Header → SVM node types (59 headers)

Line counts from `wc -l`. Node types come from parsing the `svm.h` switch and mapping each evaluator to its defining
header.

| Header | Lines | Node types evaluated / role |
|---|---:|---|
| `svm.h` | 624 | main loop `svm_eval_nodes`; inline cases `NODE_END`, `NODE_SHADER_JUMP`, `NODE_JUMP_IF_ZERO`, `NODE_JUMP_IF_ONE` |
| `types.h` | 579 | `SVMInputInt/Float/Float3`, stack constants, `ShaderNodeType` enum, all node enums, `ClosureType`, `CLOSURE_IS_*` |
| `node_types.h` | 1309 | 104 typed structs (90 node + 14 `*Data`) |
| `node_types_template.h` | 114 | X-macro list of node types (78 plain + 16 with `_DERIVATIVE`) |
| `util.h` | 269 | `stack_load*`, `stack_store*`, `svm_node_get<T>`, `svm_node_get_data_float4`, `dPdx/dPdy`, `shading_position<>`, `shading_incoming<>` |
| `closure.h` | 1528 | `NODE_CLOSURE_BSDF`, `_EMISSION`, `_BACKGROUND`, `_HOLDOUT`, `_SET_WEIGHT`, `_WEIGHT`, `_SET_NORMAL`, `_VOLUME`; `NODE_EMISSION_WEIGHT`, `NODE_MIX_CLOSURE`, `NODE_VOLUME_COEFFICIENTS`, `NODE_PRINCIPLED_VOLUME` |
| `value.h` | 30 | `NODE_VALUE_F(_DERIVATIVE)`, `NODE_VALUE_V(_DERIVATIVE)` |
| `math.h` (+`math_util.h` 282) | 47 | `NODE_MATH`, `NODE_VECTOR_MATH(_DERIVATIVE)` |
| `mix.h` (+`color_util.h` 409) | 83 | `NODE_MIX`, `NODE_MIX_COLOR`, `NODE_MIX_FLOAT`, `NODE_MIX_VECTOR`, `NODE_MIX_VECTOR_NON_UNIFORM` |
| `map_range.h` | 119 | `NODE_MAP_RANGE`, `NODE_VECTOR_MAP_RANGE` |
| `clamp.h` | 29 | `NODE_CLAMP` |
| `invert.h` | 32 | `NODE_INVERT` |
| `gamma.h` | 26 | `NODE_GAMMA` |
| `brightness.h` | 28 | `NODE_BRIGHTCONTRAST` |
| `hsv.h` | 47 | `NODE_HSV` |
| `sepcomb_color.h` | 48 | `NODE_SEPARATE_COLOR`, `NODE_COMBINE_COLOR` |
| `sepcomb_vector.h` | 65 | `NODE_SEPARATE_VECTOR(_DERIVATIVE)`, `NODE_COMBINE_VECTOR(_DERIVATIVE)` |
| `convert.h` | 72 | `NODE_CONVERT(_DERIVATIVE)` (auto-inserted type conversions; also `RGBToBWNode`) |
| `ramp.h` (+`ramp_util.h` 80) | 156 | `NODE_RGB_RAMP`, `NODE_CURVES`, `NODE_FLOAT_CURVE` |
| `mapping.h` (+`mapping_util.h` 38) | 54 | `NODE_MAPPING(_DERIVATIVE)`, `NODE_TEXTURE_MAPPING(_DERIVATIVE)`, `NODE_MIN_MAX` |
| `tex_coord.h` | 419 | `NODE_TEX_COORD(_DERIVATIVE)`, `NODE_NORMAL_MAP`, `NODE_TANGENT(_DERIVATIVE)` |
| `attribute.h` | 224 | `NODE_ATTR(_DERIVATIVE)` (TexCoord Generated/UV use it) |
| `geometry.h` | 248 | `NODE_GEOMETRY(_DERIVATIVE)`, `NODE_OBJECT_INFO`, `NODE_PARTICLE_INFO`, `NODE_HAIR_INFO`, `NODE_POINT_INFO` |
| `noisetex.h` (+`fractal_noise.h` 550, `noise.h` 761) | 336 | `NODE_TEX_NOISE` |
| `white_noise.h` | 67 | `NODE_TEX_WHITE_NOISE` |
| `voronoi.h` | 1203 | `NODE_TEX_VORONOI` |
| `gabor.h` | 362 | `NODE_TEX_GABOR` |
| `checker.h` | 46 | `NODE_TEX_CHECKER` |
| `gradient.h` | 75 | `NODE_TEX_GRADIENT` |
| `wave.h` | 109 | `NODE_TEX_WAVE` |
| `magic.h` | 119 | `NODE_TEX_MAGIC` |
| `brick.h` | 113 | `NODE_TEX_BRICK` |
| `image.h` | 207 | `NODE_TEX_IMAGE(_DERIVATIVE)`, `NODE_TEX_IMAGE_BOX(_DERIVATIVE)`, `NODE_TEX_ENVIRONMENT(_DERIVATIVE)` |
| `sky.h` | 265 | `NODE_TEX_SKY` |
| `radial_tiling.h` (+`radial_tiling_shared.h` 1183) | 65 | `NODE_RADIAL_TILING` |
| `normal.h` | 29 | `NODE_NORMAL` |
| `fresnel.h` | 65 | `NODE_FRESNEL`, `NODE_LAYER_WEIGHT` |
| `light_path.h` | 144 | `NODE_LIGHT_PATH`, `NODE_LIGHT_FALLOFF` |
| `camera.h` | 37 | `NODE_CAMERA` |
| `vector_rotate.h` | 65 | `NODE_VECTOR_ROTATE` |
| `vector_transform.h` | 123 | `NODE_VECTOR_TRANSFORM` |
| `vertex_color.h` | 96 | `NODE_VERTEX_COLOR(_DERIVATIVE)` |
| `wireframe.h` | 110 | `NODE_WIREFRAME` |
| `wavelength.h` | 36 | `NODE_WAVELENGTH` |
| `blackbody.h` | 35 | `NODE_BLACKBODY` |
| `ies.h` | 33 | `NODE_IES` |
| `scene_time.h` | 26 | `NODE_SCENE_TIME` |
| `bump.h` | 63 | `NODE_ENTER_BUMP_EVAL`, `NODE_LEAVE_BUMP_EVAL` |
| `displace.h` | 197 | `NODE_SET_BUMP`, `NODE_SET_DISPLACEMENT`, `NODE_DISPLACEMENT`, `NODE_VECTOR_DISPLACEMENT` |
| `aov.h` | 62 | `NODE_AOV_START`, `NODE_AOV_COLOR`, `NODE_AOV_VALUE` |
| `ao.h` | 138 | `NODE_AMBIENT_OCCLUSION` (inside `#ifdef __SHADER_RAYTRACE__`) |
| `bevel.h` | 330 | `NODE_BEVEL` (inside `#ifdef __SHADER_RAYTRACE__`) |
| `raycast.h` | 195 | `NODE_RAYCAST` (inside `#ifdef __SHADER_RAYTRACE__`) |

Enum size: `ShaderNodeType` (`types.h:50-56`) has 78 + 2×16 = 110 values including `NODE_NONE` and `NODE_PAD1`. That
leaves 108 dispatchable types, and the switch has 108 `SVM_CASE`s. `NODE_HAIR_INFO` and `NODE_POINT_INFO` sit
under `#if __HAIR__` / `__POINTCLOUD__`.

`node_types_template.h:12-14` notes that the enum order should match the switch order for GPU jump tables. This
affects performance only, not correctness.

### 1.2 Evaluator signature style

- The byte code is `kernel_data_fetch(svm_nodes, i)`, a flat `uint` array.
- Each node is `[uint type][sizeof(T)/4 words of struct T]` (`svm.cpp:434-438`, `svm.h:95-112`).
- Inputs are encoded per field:
  - `SVMInputFloat{uint bits}`: either a float constant or a stack offset NaN-boxed with
    `SVM_INPUT_STACK_OFFSET_MASK 0x7FC00000` (`types.h:26-37`).
  - `SVMInputFloat3`: three of those.
  - `SVMInputInt{value, offset}`.
  - `SVMStackOffset` (`uint8_t`); `SVM_STACK_INVALID = 255`.
- Stack: `float stack[SVM_STACK_SIZE]`, with `SVM_STACK_SIZE = 255` (`types.h:41`, `svm.h:109`).
- Typical evaluator: `ccl_device_noinline void svm_node_X(ccl_private float *stack, const ccl_global SVMNodeX &node)`.
- Templated on `float3`/`dual3` for derivative variants, e.g. `svm_node_mapping<float3|dual3>`.
- Variable-length nodes take `int offset` and return the new offset: ramps/curves (`ramp.h:95-154`, table inline in
  `svm_nodes`), `svm_node_tex_coord` (optional `PackedTransform`), `svm_node_tex_sky`, `svm_node_closure_bsdf`
  (trailing `*Data` struct), `svm_node_raycast`.
- Closure nodes also take `Spectrum closure_weight` (by value or pointer) and `PathRayVisibility` / `path_flag`.
- Some are templated on `node_feature_mask` (compile-time `IF_KERNEL_NODES_FEATURE`, `kernel/features.h:111-114`):
  `closure_bsdf<mask, ShaderType>`, `tex_voronoi<mask>`, `set_bump<mask>`, `light_path<mask>`,
  `radial_tiling<mask>`, `aov_*<mask>`.

### 1.3 Dispatch: `svm_eval_nodes` (`kernel/svm/svm.h:101-622`)

```cpp
template<uint node_feature_mask, ShaderType type, typename ConstIntegratorGenericState>
ccl_device void svm_eval_nodes(KernelGlobals kg, ConstIntegratorGenericState state, ccl_private ShaderData *sd,
                               ccl_global float *render_buffer, const PathRayVisibility path_visibility,
                               const uint32_t path_flag)
```

- Starts at the per-shader jump table: `offset = (sd->shader & SHADER_MASK) * (1 + sizeof(SVMNodeShaderJump)/4)`
  (line 112).
- Loops `while(true){ node_type = kernel_data_fetch(svm_nodes, offset++); switch(node_type) {...} }` (114-621).
- `SVM_CASE(n)` is a plain `case n:`. With `__KERNEL_USE_DATA_CONSTANTS__` it also skips unused nodes (lines 91-98).
- `NODE_SHADER_JUMP` picks surface, volume or displacement by template `type` (120-136).
- `NODE_JUMP_IF_ZERO/ONE` skip a mix-closure branch when the stack weight is ≤0 or ≥1 (177-192).
- `closure_weight` is a loop-local `Spectrum` (line 111), set by `NODE_CLOSURE_SET_WEIGHT/WEIGHT/EMISSION_WEIGHT`
  and consumed by the next closure node.

Argument shape per case, parsed from the switch (`scratchpad/tools/dispatch.py`):

| Shape | Count | Cases |
|---|---:|---|
| `(stack, node)` only | 43 | VALUE_F/V(+DERIV), MATH, VECTOR_MATH(+D), MIX, MIX_COLOR/FLOAT/VECTOR/VECTOR_NON_UNIFORM, MAP_RANGE, VECTOR_MAP_RANGE, CLAMP, INVERT, GAMMA, BRIGHTCONTRAST, HSV, SEPARATE/COMBINE_COLOR, SEPARATE/COMBINE_VECTOR(+D), MAPPING(+D), TEXTURE_MAPPING(+D), MIN_MAX, TEX_NOISE, TEX_VORONOI, TEX_GABOR, TEX_WAVE, TEX_MAGIC, TEX_CHECKER, TEX_BRICK, TEX_GRADIENT, TEX_WHITE_NOISE, NORMAL, VECTOR_ROTATE, RADIAL_TILING, MIX_CLOSURE |
| reads `sd` (with or without `kg`) | 49 | CLOSURE_BSDF, CLOSURE_EMISSION, CLOSURE_BACKGROUND, CLOSURE_HOLDOUT, CLOSURE_SET_NORMAL, GEOMETRY(+D), TEX_COORD(+D), ATTR(+D), VERTEX_COLOR(+D), TEX_IMAGE(+D), TEX_IMAGE_BOX(+D), TEX_ENVIRONMENT(+D), TEX_SKY, FRESNEL, LAYER_WEIGHT, LIGHT_PATH, LIGHT_FALLOFF, OBJECT/PARTICLE/HAIR/POINT_INFO, CAMERA, IES, TANGENT(+D), NORMAL_MAP, VECTOR_TRANSFORM, WIREFRAME, bump/displacement (6), volume (3), BEVEL, AO, RAYCAST, AOV_COLOR/VALUE |
| `kg`, no `sd` | 8 | CONVERT(+D) (`film.rgb_to_y`), RGB_RAMP, CURVES, FLOAT_CURVE (table in `svm_nodes`), WAVELENGTH, BLACKBODY (`film.*`), SCENE_TIME (`kernel_data.scene_time`) |
| special | 8 | END, SHADER_JUMP, JUMP_IF_ZERO/ONE, CLOSURE_SET_WEIGHT/CLOSURE_WEIGHT/EMISSION_WEIGHT (write `closure_weight`), AOV_START (`path_flag`, `render_buffer`) |

### 1.4 State beyond the stack

Per-header scan of `sd->…`, `kernel_data.…` and `kernel_data_fetch(…)`; full output in
`research/svm_scan.txt`. Fields reached through helpers (`util.h` `shading_position`, `geom/object.h`) were traced
by hand.

| Node (M6 list) | SVM node(s) emitted by `compile()` | `ShaderData` read at runtime (non-derivative variants) | Other kernel dependencies |
|---|---|---|---|
| Value / RGB | `NODE_VALUE_F` / `NODE_VALUE_V` (via `add_value_node`) | none | none |
| Math, VectorMath | `NODE_MATH`, `NODE_VECTOR_MATH` | none | none |
| Mix (legacy MixRGB), Mix float/vector/color | `NODE_MIX` (+`NODE_MIX_CLAMP` mode), `NODE_MIX_FLOAT/_VECTOR/_VECTOR_NON_UNIFORM/_COLOR` | none | `util/color.h` (HSV ops) |
| MapRange, Clamp | `NODE_MAP_RANGE`/`NODE_VECTOR_MAP_RANGE`; `NODE_CLAMP` (MapRange "Clamp" and Math "Use Clamp" are `expand()`ed into ClampNode, `shader_nodes.cpp:6630-6653`, `6924-6937`) | none | none |
| Invert, Gamma, BrightContrast, HSV | `NODE_INVERT`, `NODE_GAMMA`, `NODE_BRIGHTCONTRAST`, `NODE_HSV` | none | none |
| Separate/Combine Color, XYZ | `NODE_SEPARATE/COMBINE_COLOR`, `NODE_SEPARATE/COMBINE_VECTOR` | none | none |
| ColorRamp, RGBCurves | `NODE_RGB_RAMP`, `NODE_CURVES` (257-entry float4 table inline after the node, `shader_nodes.cpp:7546-7562`, `7307-7325`) | none | `svm_nodes` (inline table) |
| auto Convert, RGB to BW | `NODE_CONVERT` | none | `kernel_data.film.rgb_to_y` (`kernel/util/colorspace.h:34-37`) |
| Mapping | `NODE_MAPPING` | none | none |
| TexCoord: Generated | `NODE_ATTR(ATTR_STD_GENERATED)` (`shader_nodes.cpp:4076-4136`); background shader: `NODE_GEOMETRY(P)` | `object`, `type`, `prim`, `u`, `v`; fallback when attribute absent: `P`, `object`, `object_flag` (`attribute.h:86-90`) | `objects[].attribute_map_offset`, `attributes_map`, `attributes_float3`/`float2`, `tri_vindex`; `objects[].itfm` |
| TexCoord: UV | `NODE_ATTR(ATTR_STD_UV)` | `object`, `type`, `prim`, `u`, `v` | same attribute arrays |
| TexCoord: Normal / Object | `NODE_TEX_COORD(NORMAL/OBJECT[_WITH_TRANSFORM])` | `N` / `P`; `object`, `object_flag` (`ob_tfm_motion` if `SD_OBJECT_MOTION`) | `objects[].tfm/itfm` (`geom/object.h:33-41`, `170-197`) |
| TexCoord: Camera / Window | `NODE_TEX_COORD(CAMERA/WINDOW)` | `P`, `object`, `ray_P` (ortho background) | `kernel_data.cam.{worldtocamera,cameratoworld,worldtondc,type,width,height}` (`camera/camera.h:531-600`) |
| TexCoord: Reflection | `NODE_TEX_COORD(REFLECTION)`; background: `NODE_GEOMETRY(I)` | `wi`, `N`, `object` | none |
| Noise, WhiteNoise, Voronoi, Checker, Gradient, Wave, Magic, Brick | `NODE_TEX_*` (+`NODE_TEXTURE_MAPPING`/`NODE_MIN_MAX` from `TextureMapping::compile`, `shader_nodes.cpp:166-206`) | none (default Vector input is auto-linked to TexCoord Generated; see row above) | `util/hash.h`, `util/math*.h` only. Voronoi needs `KERNEL_FEATURE_NODE_VORONOI_EXTRA` in the mask (`voronoi.h:1151-1177`) |
| Image Texture | `NODE_TEX_IMAGE` / `NODE_TEX_IMAGE_BOX` | `N` (box only), `lcg_state` (tiled only) | `image_textures`, `image_info`, `image_texture_udims` (UDIM), tile-cache arrays, `kernel_data.image.mip_bias` (tiled only) (§6) |
| Diffuse | `NODE_CLOSURE_SET_WEIGHT`/`_WEIGHT` + `NODE_CLOSURE_BSDF` + `SVMNodeDiffuseBsdfData` | `N`, `flag`, closure bookkeeping; Oren–Nayar if roughness > 0: `wi` | none |
| Glossy | same + `SVMNodeGlossyBsdfData` | `N`, `wi`, `flag`, `Ng` and `type` (only if `SD_USE_BUMP_MAP_CORRECTION`, `bsdf_util.h:399-409`) | `kernel_data.integrator.caustics_reflective`; LUT `ggx_E`/`ggx_Eavg` only for multi-GGX |
| Glass | same + `SVMNodeGlassBsdfData` | `N`, `wi`, `flag` (`SD_BACKFACING` flips IOR), `Ng`, `type` | `caustics_reflective/refractive`; LUT `ggx_gen_schlick_ior_s` (always, sample weight), `ggx_glass_*` (multi-GGX) |
| Refraction | same + `SVMNodeRefractionBsdfData` | `N`, `wi`, `flag` | `caustics_refractive` |
| Principled | `NODE_CLOSURE_BSDF` + `SVMNodePrincipledBsdfData` (`shader_nodes.cpp:2822-2879`) | `N`, `wi`, `Ng`, `type`, `flag` | LUTs `ggx_gen_schlick_s/_ior_s`, `ggx_E/Eavg`, `ggx_glass_*`, `sheen_ltc`; `caustics_*`; thin-film table only if thickness > `THINFILM_THICKNESS_CUTOFF` |
| Emission | `NODE_CLOSURE_SET_WEIGHT` or `NODE_EMISSION_WEIGHT` + `NODE_CLOSURE_EMISSION` | `flag`; `object` (volume eval only) | none |
| Transparent | `NODE_CLOSURE_SET_WEIGHT` + `NODE_CLOSURE_BSDF` + `SVMNodeSimpleBsdfData` | `N`, `flag`, closure bookkeeping | `path_flag & PATH_RAY_TERMINATE` |
| Mix Shader | `NODE_MIX_CLOSURE` (from `MixClosureWeightNode`) + `NODE_JUMP_IF_ZERO/ONE` | none | none |
| Add Shader | nothing (weights pass through, `shader_graph.cpp:1101-1189`) | none | none |
| Background | `NODE_CLOSURE_SET_WEIGHT` or `NODE_EMISSION_WEIGHT` + `NODE_CLOSURE_BACKGROUND` | `flag` | none |

Other notable dependencies outside the M6 list:

- `light_path.h`: `path_flag`, `path_visibility`, `sd->ray_length`, and `IntegratorState` (ray depth etc.).
- `sky.h`: a sky texture image plus `kernel_data.background.use_sun_guiding`.
- `blackbody.h`: `kernel_data.film.rec709_to_*`.
- `wavelength.h`: `kernel_data.film.xyz_to_*`.
- `scene_time.h`: `kernel_data.scene_time`.
- `aov.h`: `render_buffer`.
- `ao.h`, `bevel.h`, `raycast.h`: BVH and `IntegratorState`.

---

## 2. `ShaderData` (`kernel/types.h:1019-1096`)

Fields in order:

- `float3 P, N, Ng, wi`
- `int type` (PrimitiveType), `int shader` (id | `ShaderFlag` bits such as `SHADER_SMOOTH_NORMAL`, `SHADER_MASK`,
  `types.h:479-494`)
- `int flag` (`ShaderDataFlag`, 897-978), `uint object_flag` (`ShaderDataObjectFlag`, 981-1017)
- `int num_closure, num_closure_left`
- `int prim`, `float u, v`, `int object`, `float time`, `float ray_length`
- under `__RAY_DIFFERENTIALS__`: `float dP, dI; differential du, dv`
- under `__DPDU__`: `float3 dPdu, dPdv`
- under `__OBJECT_MOTION__`: `Transform ob_tfm_motion, ob_itfm_motion`
- `float3 ray_P; float ray_dP; uint lcg_state; Spectrum closure_emission_background, closure_transparent_extinction`
- `ShaderClosure closure[MAX_CLOSURE]`

`MAX_CLOSURE` is 64 unless `__MAX_CLOSURE__` is defined (`types.h:829-833`). `ShaderClosure` is at 883-889: the
`SHADER_CLOSURE_BASE` fields `weight, type, sample_weight, N` plus `pad[sizeof(Spectrum)*2 + 4*sizeof(float)]`.

`__RAY_DIFFERENTIALS__` and `__DPDU__` are always defined on CPU (`features.h:141,145`). `__OBJECT_MOTION__` can be
removed with `__KERNEL_FEATURES__` (`features.h:173-216`).

**Compile-time vs runtime subset.** Vendored headers reference fields at compile time across all inline helpers,
including object/attribute/curve helpers that are never called. A reduced struct is therefore impossible without
patches. Painterly must use the vendored `ShaderData` verbatim. "Minimal subset" means fields that must hold
meaningful values at runtime; everything else can be zeroed.

Needed by every evaluation (the caller's duty, mirroring `surface_shader_eval`, `kernel/integrator/surface_shader.h:1247-1297`):

- `shader` (with `SHADER_MASK` bits), `flag` (initialise to `KernelShader.flags`; see `scene/shader.cpp:626-700`
  and the note below), `num_closure = 0`, `num_closure_left = max_closures`
- `closure_transparent_extinction = 0`, `closure_emission_background` (cleared via the `SD_EMISSION` flag logic,
  `emissive.h:16-38`), `lcg_state = 0`

`SD_USE_BUMP_MAP_CORRECTION` comes from `Shader::use_bump_map_correction` (`scene/shader.cpp:685-687`) and changes
glossy/glass `bsdf->N` (`bsdf_util.h:399-409`). Painterly must decide this knob explicitly, and the parity tests must
match Blender's material setting.

Per-node runtime subset for the requested list (from §1.4):

- **No `sd` field at all:** Value, RGB, Math, VectorMath, Mix (all), MapRange, Clamp, Invert, Gamma, BrightContrast,
  HSV, Separate/Combine Color/XYZ, ColorRamp, RGBCurves, Mapping, Noise, WhiteNoise, Voronoi, Checker, Gradient,
  Wave, Magic, Brick, Mix Shader, Add Shader. Their default `Vector` inputs carry `LINK_TEXTURE_GENERATED`, so
  `ShaderGraph::default_inputs` (`shader_graph.cpp:864-944`) auto-connects TexCoord Generated. In practice texture
  nodes therefore need the TexCoord fields.
- **TexCoord:** `P`, `N`, `wi`, `object`, `object_flag`, `type`, `prim`, `u`, `v`, `ray_P` (Window+ortho), plus
  `ob_tfm_motion` / `ob_itfm_motion` if `SD_OBJECT_MOTION`.
- **Image Texture:** `N` (box projection only). `lcg_state` matters only for tiled/mipmapped textures; leave it 0.
- **BSDFs** (Principled, Diffuse, Glossy, Glass, Refraction, Transparent): `N`, `wi`, `Ng`, `type`, `flag`
  (`SD_BACKFACING`, `SD_USE_BUMP_MAP_CORRECTION`), closure bookkeeping.
- **Emission:** `flag` (and `object` for volume eval only). **Background:** `flag`.
- **Derivative fields** (`du`, `dv`, `dPdu`, `dPdv`, `dI`, `dP`) are read only by `*_DERIVATIVE` variants. These are
  emitted only when a node `need_derivatives()`, which only `ImageSlotTextureNode` (texture cache with mipmaps,
  `shader_nodes.cpp:406-430`, `shader_nodes.h:96-100`) or bump graphs trigger (`svm.cpp:999-1034`,
  `shader_graph.cpp:946-1100`). With an image shim that reports `has_tiles_and_mipmaps = false` and no bump support,
  they can be zero.
- **Backfacing:** Cycles sets `SD_BACKFACING` and flips `N`, `Ng` (`kernel/geom/shader_data.h:113-125`). Glass and
  Refraction then store `bsdf->ior = 1/ior` (`closure.h:761, 816`).

---

## 3. Closures

### 3.1 Allocation (`kernel/closure/alloc.h`)

- `closure_alloc(sd, size, type, weight)` (11-32): takes `sd->closure[sd->num_closure++]` and decrements
  `num_closure_left`. Returns `nullptr` when `num_closure_left == 0`.
- `closure_alloc_extra(sd, size)` (34-53): takes `ceil(size/sizeof(ShaderClosure))` slots from the **end** of the
  array (Fresnel payloads). On failure it frees the previous closure.
- `closure_sample_weight` (55-74): clamps negative weights to 0. Returns `|avg(weight)|`, or 0 if below
  `CLOSURE_WEIGHT_CUTOFF = 1e-5f` (`svm/types.h:576`).
- `bsdf_alloc` (76-93): calls `closure_alloc` with `CLOSURE_NONE_ID` and sets `sample_weight`. The setup function
  then writes the type.
- `bsdf_alloc_maybe_emission` (96-118): with `PATH_RAY_EMISSION` it uses a stack temporary instead of a slot.
- `emissive.h`: `background_setup` (16-25) and `emission_setup` (29-38) only accumulate into
  `sd->closure_emission_background` and set `SD_EMISSION`. There is no closure slot.
- `bsdf_transparent.h:16-62`: accumulates `closure_transparent_extinction`, merges into one
  `CLOSURE_BSDF_TRANSPARENT_ID` slot, and sets `SD_BSDF|SD_TRANSPARENT`.

`ClosureType` enum: `kernel/svm/types.h:464-530`, with category macros `CLOSURE_IS_BSDF_DIFFUSE/GLOSSY/
TRANSMISSION/GLASS/REFRACTION/...` at 535-574. Labels: `ClosureLabel`, `kernel/types.h:329-343`.

### 3.2 Weight flow

1. **Host graph transform:** `ShaderGraph::transform_multi_closure` (`shader_graph.cpp:1101-1189`, called from
   `finalize`, 374-402).
   - It replaces Mix/Add Shader trees with `MixClosureWeightNode` (outputs `Weight1/2 = in·(1−fac)`, `in·fac`) and
     `MathNode` adds.
   - The result feeds each closure's hidden `SurfaceMixWeight` input (`SocketType::SVM_INTERNAL`).
2. **Host compile:** `SVMCompiler::generate_closure_node` (`svm.cpp:758-807`).
   - Assigns `mix_weight_offset` when the weight input is linked or ≠ 1.
   - `generate_multi_closure` (845-997) emits `NODE_JUMP_IF_ONE` / `NODE_JUMP_IF_ZERO` around each Mix branch, so
     zero-weight sub-trees are skipped at runtime.
3. **Color weight:** `BsdfNode::compile` (`shader_nodes.cpp:2189-2214`).
   - Emits `NODE_CLOSURE_WEIGHT` if Color is linked (stack offset), else `NODE_CLOSURE_SET_WEIGHT` with the constant
     RGB.
   - Then `add_bsdf_node(SVMNodeClosureBsdf{closure_type, mix_weight_offset}, Data)`.
4. **Kernel:** `svm_node_closure_set_weight/_weight/emission_weight` (`closure.h:1477-1497`) set `closure_weight`.
   - `svm_node_closure_bsdf` (215-1139) loads `mix_weight` (default 1). For most closures it uses
     `weight = closure_weight * mix_weight`.
   - **Exceptions:**
     - Glass (779-839): `weight = mix_weight`, with Color in `FresnelGeneralizedSchlick::{reflection,transmission}_tint`.
     - Metallic (560-652): `weight = mix_weight`, with Color in the Fresnel payload.
     - Principled (273-523): ignores `closure_weight` and builds its lobes with internal layering weights
       (`principled_bsdf_emission` 94-213, `closure_layering_weight`, `bsdf_albedo`).
     - Multi-GGX glossy: weight stays Color×mix, and energy is preserved through the LUT.
   - `svm_node_mix_closure` (1499-1515) writes `Weight1/2` to the stack.
5. **Emission:** `EmissionNode::compile` (`shader_nodes.cpp:3072-3099`).
   - Emits `NODE_EMISSION_WEIGHT` (color×strength from the stack) or `NODE_CLOSURE_SET_WEIGHT` (constant product),
     then `NODE_CLOSURE_EMISSION`.
   - `svm_node_closure_emission` (1406-1430) multiplies by `mix_weight` and calls `emission_setup`.
   - Background is identical, via `background_setup` (1432-1451).
   - Principled emission is inside `principled_bsdf_emission` (205-210), attenuated by coat and sheen.
   - Connecting a non-closure output to a closure input auto-inserts an `EmissionNode`
     (`shader_graph.cpp:258-289`, closure branch 271-284).

### 3.3 Coupling to `bsdf_*.h`

`closure.h` includes `kernel/closure/{alloc,bsdf,bsdf_util,bssrdf,emissive,volume}.h` unconditionally (lines 7-12).
`bsdf.h:8-22` includes 15 BSDF headers. In total `closure.h` calls **50 distinct closure-library functions** (list in
`research/closure_calls.txt`), e.g.:

- `bsdf_diffuse_setup`, `bsdf_oren_nayar_setup`, `bsdf_transparent_setup`
- `bsdf_microfacet_{ggx,beckmann}[_refraction|_glass]_setup`
- `bsdf_microfacet_setup_fresnel_{dielectric,conductor,constant,generalized_schlick,f82_tint}`
- `bsdf_sheen_setup`, `bsdf_thin_glass_setup`, `bsdf_albedo`, `closure_layering_weight`, `bssrdf_setup`, the
  `volume_*_setup` family

The Fresnel setup functions call `bsdf_microfacet_estimate_albedo` and `microfacet_ggx_preserve_energy`, which call
`lookup_table_read*` (`kernel/util/lookup_table.h`) at `kernel_data.tables.{ggx_E, ggx_Eavg, ggx_glass_*,
ggx_gen_schlick_s, ggx_gen_schlick_ior_s, sheen_ltc, thin_film_table}` (`bsdf_microfacet.h:963-1060`,
`bsdf_sheen.h:27`, `bsdf_util.h:499+`).

- Effect: they change `sample_weight`, `energy_scale`, and, through `closure_layering_weight` in Principled
  (`closure.h:141, 174, 470`, then the diffuse weight at 515-520), the `weight` of lower lobes.
- Data: host tables are `scene/shader.tables` (1802 lines, 9 `static const float` arrays, `shader.cpp:28, 716-724`),
  uploaded by `LookupTables::add_table` (`scene/tables.{h,cpp}`).
- If painterly leaves `lookup_table` empty, `kernel_array::fetch` asserts out of range (`cpu/globals.h:30-44`).
  In release builds that is an out-of-bounds read.

### 3.4 What a painterly closure collector needs

No hook is needed for compilation. Call the vendored evaluators, then read `sd`:

- **Lobe candidates:** `sd->closure[0 .. sd->num_closure)`; skip slots used as Fresnel extras (they are not counted
  in `num_closure`).
  - `type` → category via `CLOSURE_IS_BSDF_DIFFUSE` (diffuse, Oren-Nayar, translucent, sheen, toon-diffuse …),
    `CLOSURE_IS_BSDF_GLOSSY` (→ mirror), `CLOSURE_IS_GLASS` / `CLOSURE_IS_REFRACTION` (→ glass),
    `CLOSURE_BSDF_TRANSPARENT_ID` (→ transparent), `CLOSURE_IS_BSSRDF` (painterly policy needed).
  - `weight`, `sample_weight`, `N`.
  - For microfacet: cast to `MicrofacetBsdf` (`bsdf_microfacet.h:65-81`) to read `ior` (already inverted if
    `SD_BACKFACING`), `alpha_x/y`, `fresnel_type`, `fresnel`.
  - For Glass and Metallic the colour lives in the Fresnel payload: `FresnelGeneralizedSchlick::reflection_tint` /
    `transmission_tint`, or `FresnelF82Tint::f0` / `FresnelConductor` (`bsdf_microfacet.h:33-63`), **not** in
    `weight`.
- **Emission:** `sd->flag & SD_EMISSION` → `sd->closure_emission_background`.
- **Transparency:** `sd->closure_transparent_extinction` or the transparent slot.

Required inputs: `KernelGlobals` with `lookup_table` and `kernel_data.tables` filled;
`kernel_data.integrator.caustics_reflective = caustics_refractive = 1`, so the `__CAUSTICS_TRICKS__` filter (always
defined, `features.h:138`) never drops glossy/glass lobes; `node_feature_mask` ⊇ `BSDF | EMISSION | VORONOI_EXTRA`
(`features.h:20-30`); `path_flag = 0`.

Shadowing `kernel/closure/alloc.h` and `emissive.h` would also work, since the setup functions only need a
`ShaderClosure`-sized return slot. It is unnecessary and would have to keep `closure_alloc_extra` semantics.

### 3.5 Include closure

Text-level transitive closure, quoted includes resolved against `intern/cycles` then the including file's directory.
"no-optional" skips `#if` blocks mentioning OSL/GPU/Embree/path-guiding/`__SHADER_RAYTRACE__`.

| Entry | Files | Lines |
|---|---:|---:|
| `kernel/svm/svm.h`, every branch | 214 | 52,331 |
| `svm.h` CPU without OSL/GPU/Embree/guiding, **with** `__SHADER_RAYTRACE__` (as `features.h:131` forces) | 201 | 49,435 |
| `svm.h` without ao/bevel/raycast | 172 | 40,836 |
| `kernel/svm/closure.h` alone | 111 | 28,766 (26 `kernel/closure/*`) |
| M6 subset: 22 stack/texture headers + `tex_coord/attribute/geometry/image/closure.h` | 149 | 36,881 |
| 22 stack/texture headers only (value, math, mix, map_range, clamp, invert, gamma, brightness, hsv, sepcomb_*, ramp, mapping, noisetex, white_noise, voronoi, checker, gradient, wave, magic, brick, convert) | 92 | 20,671 |
| `kernel/types.h` alone | 48 | 11,932 |

M6-subset file list: `research/m6_subset_closure.txt`. Even the stack-only subset reaches `kernel/globals.h` →
`kernel/device/cpu/globals.h` → `kernel/util/profiler.h` → `util/profiling.h` → `util/thread.h` → `<tbb/spin_mutex.h>`
(`util/thread.h:23`). Unresolved quoted includes:

- `atomic_ops.h`: Blender `intern/atomic`, from `util/atomic.h:10`, reached through `kernel/util/image_2d.h:10`.
- `../../guardedalloc/MEM_guardedalloc.h`: only under `WITH_BLENDER_GUARDEDALLOC`.

---

## 4. Host side

### 4.1 `scene/shader_nodes.{h,cpp}` (1908 / 8424 lines)

- 97 `NODE_DEFINE`s plus `ConvertNode`, which uses its own registration (`shader_nodes.cpp:1924-1982`); 110 classes
  in the header.
- Per-class ranges for `NODE_DEFINE`, `compile(SVMCompiler&)`, `constant_fold`, `expand`, `simplify_settings`,
  `attributes` and the constructor are in `research/nodes_index.json`.
- Sockets: `SOCKET_IN_*(member, "UI Name", default[, flags])`. Links match the **UI name** (§5). Hidden
  `SurfaceMixWeight` sockets are `SVM_INTERNAL`.
- `TEXTURE_MAPPING_DEFINE` (47-79) adds `Translation, Rotation, Scale, Min, Max, Use Min Max, x/y/z_mapping, Type,
  Projection` to every `TextureNode`.

M6 node classes:

| Class (Cycles type name) | `NODE_DEFINE` | `compile(SVM)` | Inputs: "UI name" = default (output names) |
|---|---|---|---|
| ValueNode (`value`) | 5224-5232 | 5241-5244 (+fold 5236) | param `Value`=0 → out `Value` |
| ColorNode (`color`) | 5254-5262 | 5271-5278 | param `Value`=0 → out `Color` |
| MathNode (`math`) | 6863-6920 | 6970-6981 (expand 6924, fold 6939) | `Type` enum (41 names), `Use Clamp`=false, `Value1`=0.5, `Value2`=0.5, `Value3`=0 → `Value` |
| VectorMathNode (`vector_math`) | 6991-7042 | 7086-7099 | `Type` (30), `Vector1/2/3`=0, `Scale`=1 → `Value`, `Vector` |
| MixNode (`mix`, legacy MixRGB) | 5466-5501 | 5505-5530 | `Type` (19), `Use Clamp`, `Fac`=0.5, `Color1/2`=0 → `Color` |
| MixColorNode (`mix_color`) | 5565-5600 | 5604-5617 | `Type`, `Factor`=0.5, `A`,`B`=0, `Use Clamp Result`=false, `Use Clamp`=true → `Result` |
| MixFloatNode (`mix_float`) | 5656-5667 | 5671-5682 | `Factor`=0.5, `A`,`B`=0, `Use Clamp`=true → `Result` |
| MixVectorNode / NonUniform | 5710-5722 / 5765-5777 | 5726-5737 / 5781-5792 | `Factor` (float / vec 0.5), `A`,`B`, `Use Clamp` → `Result` |
| MapRangeNode (`map_range`) | 6604-6626 | 6664-6678 (expand 6630) | `Type` (linear/stepped/smoothstep/smootherstep), `Value`=1, `From Min`=0, `From Max`=1, `To Min`=0, `To Max`=1, `Steps`=4, `Clamp`=false → `Result` |
| VectorMapRangeNode | 6688-6710 | 6725-6740 | `Vector`, `From_Min_FLOAT3`, `From_Max_FLOAT3`, `To_Min_FLOAT3`, `To_Max_FLOAT3`, `Steps_FLOAT3`, `Use Clamp` → `Vector` |
| ClampNode (`clamp`) | 6751-6767 | 6783-6794 | `Type` (minmax/range), `Value`=1, `Min`=0, `Max`=1 → `Result` |
| InvertNode | 5418-5428 | 5448-5457 | `Fac`=1, `Color` → `Color` |
| GammaNode | 5921-5930 | 5954-5963 | `Color`, `Gamma`=1 → `Color` |
| BrightContrastNode (`brightness_contrast`) | 5972-5983 | 5994-6004 | `Color`, `Bright`=0, `Contrast`=0 → `Color` |
| HSVNode (`hsv`) | 6129-6142 | 6146-6158 | `Hue`=0.5, `Saturation`=1, `Value`=1, `Fac`=1, `Color` → `Color` |
| SeparateColorNode / CombineColorNode | 6013-6030 / 5817-5834 | 6048-6059 / 5845-5856 | `Type` (rgb/hsv/hsl); `Color` ↔ `Red`,`Green`,`Blue` |
| SeparateXYZNode / CombineXYZNode | 6069-6080 / 5866-5877 | 6096-6120 / 5888-5912 | `Vector` ↔ `X`,`Y`,`Z` |
| RGBRampNode (`rgb_ramp`) | 7501-7515 | 7546-7562 (fold 7519) | params `Ramp` (color array), `Ramp Alpha`, `Interpolate`=true; `Fac`=0 → `Color`, `Alpha` |
| RGBCurvesNode (`rgb_curves`) | 7352-7367 | 7376-7379 → `CurvesNode::compile` 7307-7325 | `Curves`, `Min X`=0, `Max X`=1, `Extrapolate`=true; `Fac`=0, `Color` → `Color` |
| TextureCoordinateNode (`texture_coordinate`) | 4026-4043 | 4076-4258 | `From Dupli`, `Use Transform`, `Object Transform` → `Generated, Normal, UV, Object, Camera, Window, Reflection` |
| MappingNode (`mapping`) | 1830-1849 | 1864-1876 (fold 1853) | `Type` (point/texture/vector/normal), `Vector`, `Location`, `Rotation`, `Scale`=1 → `Vector` |
| NoiseTextureNode | 1171-1208 | 1212-1238 | `Dimensions` (1D–4D, default 3), `Type` (5, default fBM), `Normalize`=true, `Vector` (LINK_TEXTURE_GENERATED), `W`, `Scale`=1, `Detail`=2, `Roughness`=0.5, `Lacunarity`=2, `Offset`=0, `Gain`=1, `Distortion`=0 → `Fac`, `Color` |
| WhiteNoiseTextureNode | 1492-1510 | 1514-1525 | `Dimensions`=3, `Vector` (**no** LINK_TEXTURE_GENERATED flag), `W` → `Value`, `Color` |
| VoronoiTextureNode | 1311-1358 | 1362-1391 | `Dimensions`, `Distance Metric`, `Feature`, `Normalize`=false, `Vector`, `W`, `Scale`=5, `Detail`=0, `Roughness`=0.5, `Lacunarity`=2, `Smoothness`=5, `Exponent`=0.5, `Randomness`=1 → `Distance, Color, Position, W, Radius` |
| CheckerTextureNode | 1672-1687 | 1691-1708 | `Vector`, `Color1`,`Color2`=0, `Scale`=1 → `Color`, `Fac` |
| GradientTextureNode | 1118-1140 | 1144-1159 | `Type` (7), `Vector` → `Color`, `Fac` |
| WaveTextureNode | 1535-1579 | 1583-1607 | `Type`, `Bands Direction`, `Rings Direction`, `Profile`, `Vector`, `Scale`=1, `Distortion`=0, `Detail`=2, `Detail Scale`=0, `Detail Roughness`=0.5, `Phase Offset`=0 → `Color`, `Fac` |
| MagicTextureNode | 1623-1639 | 1643-1660 | `Depth`=2, `Vector`, `Scale`=5, `Distortion`=1 → `Color`, `Fac` |
| BrickTextureNode | 1719-1746 | 1750-1777 | `Offset`=0.5, `Offset Frequency`=2, `Squash`=1, `Squash Frequency`=2, `Vector`, `Color1`,`Color2`,`Mortar`, `Scale`=5, `Mortar Size`=0.02, `Mortar Smooth`=0, `Bias`=0, `Brick Width`=0.5, `Row Height`=0.25 → `Color`, `Fac` |
| ImageTextureNode | 244-293 | 432-485 (`update_images` 406-430, `cull_tiles` 319-381) | `Filename`, `Colorspace`, `Alpha Type`, `Interpolation`, `Extension` (periodic/clamp/black/mirror), `Projection`, `Projection Blend`, `Tiles`, `Animated`, `Vector` (LINK_TEXTURE_UV) → `Color`, `Alpha` |
| PrincipledBsdfNode | 2627-2693 | 2822-2879 (simplify 2701-2745) | 31 inputs, e.g. `Base Color`, `Metallic`=0, `Roughness`=0.5, `IOR`=1.5, `Alpha`=1, `Transmission Weight`, `Coat *`, `Sheen *`, `Emission Color`=1, `Emission Strength`=0, … → `BSDF` |
| DiffuseBsdfNode | 2594-2606 | 2613-2619 | `Color`=0.8, `Normal`, `Roughness`=0 → `BSDF` |
| GlossyBsdfNode | 2327-2351 | 2384-2400 | `Color`=0.8, `Normal`, `Distribution` (beckmann/ggx/ashikhmin_shirley/multi_ggx), `Tangent`, `Roughness`=0.5, `Anisotropy`=0, `Rotation`=0 → `BSDF` |
| GlassBsdfNode | 2410-2433 | 2440-2452 | `Color`=0.8, `Normal`, `Distribution` (default ggx), `Roughness`=0, `IOR`=1.5, `Thin Film Thickness`=0, `Thin Film IOR`=1.33 → `BSDF` |
| RefractionBsdfNode | 2462-2482 | 2489-2498 | `Color`, `Normal`, `Roughness`=0, `IOR`=0.3 (Cycles' own default; Blender always sets it) → `BSDF` |
| EmissionNode | 3056-3068 | 3072-3099 (fold 3106) | `Color`=0.8, `Strength`=10 → `Emission` |
| TransparentBsdfNode | 2928-2938 | 2945-2948 | `Color`=1 → `BSDF` |
| MixClosureNode / AddClosureNode | 5331-5342 / 5289-5298 | (no-op; handled by `svm.cpp`) | `Fac`=0.5, `Closure1`, `Closure2` → `Closure` |
| MixClosureWeightNode | 5384-5395 | 5399-5409 | `Weight`=1, `Fac`=1 → `Weight1`, `Weight2` |
| BackgroundNode (`background_shader`) | 3118-3129 | 3133-3160 | `Color`=0.8, `Strength`=1 → `Background` |
| OutputNode (`output`) | 6559-6569 | 6576-6587 | `Surface`, `Volume`, `Displacement`, `Normal` |

Shared code used by node bodies:

- `TextureMapping` (81-234)
- `BsdfBaseNode` / `BsdfNode` (2167-2220)
- `static shader_bump_to_node_bump_offset` (3854-3866, used by TexCoord/Geometry/Attribute)
- `CurvesNode` (7280-7348)
- the `u_colorspace_*` ustrings (`util/colorspace.cpp:24-28`)

Includes of `shader_nodes.cpp` (5-41): `scene/{constant_fold,film,image,image_sky,integrator,light,mesh,osl,scene,
shader_nodes,svm}.h`, `sky_hosek.h`, `sky_nishita.h` (both Blender `intern/sky`, not checked),
`util/colorspace.h`, `kernel/closure/bsdf_microfacet.h`, `kernel/svm/{color_util,mapping_util,math_util,
ramp_util}.h`.

Uses of external managers across all nodes:

- `compiler.scene->image_manager` (image/environment/sky, 6 sites)
- `light_manager` (IES, 1462/1481)
- `scene->film->get_aov_offset` (6824)
- `scene->geometry` / `params` (`cull_tiles`)
- `folder.scene->shader_manager->linear_rgb_to_gray` (1901, 2034)
- `rec709_to_scene_linear` (6537)
- `SKY_*` precompute functions
- `OSLCompiler` (104 uses; every node has a `compile(OSLCompiler&)` body because it is pure virtual,
  `shader_graph.h:120`)

### 4.2 `scene/svm.{h,cpp}` (292 / 1281 lines)

- `SVMCompiler` public API (`svm.h:49-160`): `input_int/float/float3`, `input_float3_from_offset`, `input_link`,
  `output`, `add_node(type)`, `add_node<T>`, `add_value_node`, `add_bsdf_node<T>`, `add_node_data<T>`,
  `add_node_data_float4/float`, `stack_assign`, `stack_find_offset`, `stack_clear_offset`, `stack_link`,
  `attribute*`, `closure_mix_weight_offset`, `output_type`, and the `scene/progress/current_graph/current_node/
  background` members.
- Stack allocation (`svm.cpp:172-298`):
  - first-fit search over `users[255]` (`stack_find_offset`, 206-238)
  - size 1 for float/int, 3 for vectors, ×3 when a node needs derivatives (`stack_size`, 172-204)
  - unlinked inputs get a `NODE_VALUE_*` load (254-288)
  - `input_float`/`input_float3` NaN-box offsets or embed constants, filtering non-finite defaults (310-341)
- Scheduling: `generate_svm_nodes` (606-756) is a Sethi–Ullman ordering. `generate_node` (567-592) calls
  `node->compile`, then frees stack users. Closure tree: `generate_multi_closure` (845-997).
- `compile_type` (1036-1172) handles one shader type. `compile` (1174-1238) emits a local `NODE_SHADER_JUMP` header
  then bump/surface/volume/displacement sections, and calls `shader->estimate_emission()`.
- `SVMShaderManager::device_update_specific` (57-146) compiles all shaders on a `TaskPool`, then rebases the jump
  table into `dscene->svm_nodes`.
- `SVMCompiler(Scene*, Progress&)` writes node-usage flags to `scene->dscene.data.svm_usage` (`svm.cpp:169`).
  `attribute()` calls `scene->shader_manager->get_attribute_id` (536-550).
- Includes (5-27): `device/device.h`, `scene/{background,light,mesh,scene,shader,shader_graph,shader_nodes,stats,
  svm}.h`, `util/{log,map,math_float3,progress,queue,task}.h`.

### 4.3 `scene/shader_graph.{h,cpp}` (416 / 1302 lines) and `scene/constant_fold.{h,cpp}` (62 / 595)

- `ShaderGraph`: `create_node<T>()`, `create_node(const NodeType*)`, `connect` (248-298, auto-inserts
  `ConvertNode`/`EmissionNode`), `disconnect`, `relink`, `simplify(Scene*)` (362-372: `expand`, `default_inputs`,
  `clean`, `refine_bump_nodes`), `finalize(Scene*, bump, …)` (374-402), `remove_proxy_nodes` (459-531),
  `constant_fold` (533-590), `deduplicate_nodes` (600-677), `clean` (801-851), `default_inputs` (864-944),
  `transform_multi_closure` (1101-1189).
- `ShaderNode::input(const char*)` matches **`socket_type.ui_name`** (`shader_graph.cpp:93-135`).
  `NodeType::find_input(ustring)` matches the internal **`SocketType::name`** (`graph/node_type.cpp:186-206`).
- `Scene` usage in `shader_graph.cpp`: only `scene->shader_manager->use_osl()` (366). It passes `Scene*` to
  `ConstantFolder` and `simplify_settings`. `Shader` usage: `has_surface_link()`, `has_volume` (`attributes`, 151-170).
- `ConstantFolder` (`constant_fold.h:18-59`) depends only on `shader_graph.h` and `util/log.h`. Its `Scene*` is used
  only by node folds (ConvertNode, RGBToBW, Blackbody).
- Includes of `shader_graph.cpp`: `scene/{attribute,constant_fold,scene,shader,shader_nodes}.h`,
  `util/{algorithm,log,md5,queue}.h`.

### 4.4 Classes the vendored graph/compiler hard-reference (mandatory "core node set")

- `shader_graph.cpp`: `OutputNode` (`ShaderGraph::ShaderGraph`, 220-226), `ConvertNode` and `EmissionNode` (`connect`),
  `TextureCoordinateNode`, `GeometryNode`, `VectorTransformNode` (`default_inputs`), `MixClosureWeightNode` and
  `MathNode` (`transform_multi_closure`), `ColorNode` (`constant_fold`), `BumpNode`, `SetNormalNode`,
  `VectorMathNode` (bump), `AttributeNode` (703-729), `OSLNode` (793, declaration only).
- `svm.cpp`: `OutputAOVNode` (832).

These must be defined, i.e. extracted, even before any "node port" card.

### 4.5 `graph/` (reflection)

- `node.{h,cpp}` (235/910), `node_type.{h,cpp}` (441/304), `node_enum.h` (65); `node_xml.*` needs pugixml (skip).
- `NODE_DECLARE` / `NODE_DEFINE` (`node_type.h:150-176`) self-register through static initialisers
  (`NodeType::register_on_init`, `node_type.cpp:254-259`).
- Registry: `unordered_map<ustring, NodeType>` (227-231). This requires `std::hash<ustring>`.
- OIIO types used: only `ustring` and `string_view`. There is no `TypeDesc`/`ParamValue` in `graph/`,
  `shader_graph`, `svm.cpp` or `shader_nodes.cpp`.
  - `ustring` members used: `c_str()`, `string()`, `empty()`, `size()`/`length()`, `==`, `<`, and `std::hash`.
  - `ustring::concat` appears only in `blender/shader.cpp`.
- `node.cpp` needs `util/md5` (`Node::hash`, 578-620). `util/md5.cpp:11,319` needs `util/path.h`'s `path_fopen`, and
  `util/path.cpp` needs OIIO filesystem and zstd (`path.cpp:13-22`). Painterly needs a `util/path.h` shim.

### 4.6 Host include-closure sizes (same method as §3.5, CPU without OSL)

| Entry | Files | Lines | External headers |
|---|---:|---:|---|
| `graph/node.h` | 41 | 7,459 | OIIO paramlist/typedesc/ustring, tbb spin_mutex |
| `graph/node.cpp` | 54 | 11,035 | + OIIO string_view |
| `graph/node_type.cpp` | 53 | 10,323 | same |
| `scene/constant_fold.cpp` | 68 | 15,126 | same |
| `scene/shader_graph.h` | 65 | 14,300 | same |
| `scene/shader_graph.cpp` | 97 | 24,634 | + OIIO imageio (through `scene/image.h`), `atomic_ops.h` |
| `scene/svm.h` | 86 | 19,454 | same |
| `scene/svm.cpp` | 108 | 27,011 | + tbb parallel_* (`util/task.h` → `util/tbb.h`; `scene/geometry.h`) |
| `scene/shader_nodes.h` | 83 | 21,753 | OIIO imageio (needs complete `ImageHandle`, `ImageParams`) |
| `scene/shader_nodes.cpp` | 127 | 38,201 | + tbb, unresolved `sky_hosek.h`, `sky_nishita.h` |

### 4.7 What compiles in isolation, and with which shims

These shims shadow paths by putting `-I src` before `-I third_party/cycles`. They are listed by the path they
shadow.

| Vendored file | Verbatim? | Shims it needs |
|---|---|---|
| `graph/node*.{h,cpp}`, `node_enum.h` | yes | `util/param.h` (ustring), `util/thread.h` (no TBB; already planned in T3.2), `util/string.h` (OIIO `string_view` → `std::string_view`, same declarations as upstream so `util/string.cpp` still links), `util/path.h` (`path_fopen`); vendor `util/{md5,log,string,time,transform,guarded_allocator}.cpp` |
| `scene/shader_graph.{h,cpp}`, `scene/constant_fold.{h,cpp}` | yes | `scene/scene.h` (Scene with `shader_manager` → `use_osl()`), `scene/shader.h` (Shader with the fields in §4.2/4.3 and `estimate_emission`, `has_surface_link`; ShaderManager with `use_osl`, `get_attribute_id`, `linear_rgb_to_gray`, `rec709_to_scene_linear`, and the virtual `device_update_specific`/`device_free` signatures used by `svm.h:34-38`), `scene/attribute.h` (`AttributeRequestSet`, `Attribute::name_standard`/`standard_name`; the real `attribute.cpp` pulls hair/mesh/pointcloud), `scene/image.h` (`ImageHandle{empty, kernel_id, metadata, all_udim_tiled, ==}`, `ImageParams`, `ImageMetaData{has_tiles_and_mipmaps, is_compressible_as_srgb}`, `ImageManager{add_image, get_use_texture_cache, get_auto_texture_cache}`) |
| `scene/svm.h` | yes | as above, plus `util/array.h`, `util/string.h` |
| `scene/svm.cpp` | **choice** | Verbatim needs `device/device.h`, `scene/{background,light,mesh,stats}.h`, `util/{task,progress}.h` shims plus `Scene::{shaders, dscene{svm_nodes.alloc/free, data}, update_stats->svm.times.add_entry, light_manager->tag_update(…, LightManager::SHADER_COMPILED), background->get_shader}`. Otherwise extract `SVMCompiler` (157-1281). The plan's T6.3 says "ported"; extraction keeps it verbatim. |
| `scene/shader_nodes.h` | yes | `scene/image.h` shim (above) |
| `scene/shader_nodes.cpp` | **no** (whole file) | Whole-file needs shims for Film, LightManager, Geometry/Mesh, SunSky + `intern/sky`, OSLCompiler, ColorSpaceManager, Integrator. Recommend function-anchored extraction per node (§8). OSL bodies compile against a no-op `scene/osl.h` shim mirroring `osl.h:152-235` (upstream's own non-OSL stubs are `osl.cpp:1585-1651`). |
| `scene/shader.tables` | yes (data) | none |
| `util/colorspace.cpp` | no | Includes `util/image.h` → OIIO imageio (`colorspace.cpp:7`). Use a small painterly `ColorSpaceManager` shim; without OCIO, upstream `colorspace_is_data` returns false for "Non-Color" (`colorspace.cpp:203-205`), which would mis-set `NODE_IMAGE_ALPHA_UNASSOCIATE`. |

---

## 5. Blender-side sync (`blender/shader.cpp`, 1992 lines): mapping logic to port to Python

| Function | Lines | What to port |
|---|---|---|
| `validate_enum_value`, `get_image_interpolation/extension`, `get_image_alpha_type` | 79-111 | out-of-range → default (LINEAR / REPEAT / AUTO) |
| `blender_attribute_name_add_type` | 127-145 | Attribute node prefixes `"\x01object:"`, `"\x01instancer:"`, `"\x01layer:"` |
| `get_node_output_rgba/value/vector` | 177-199 | RGB/Value/Normal nodes read their **output socket** `default_value` |
| `convert_socket_type` | 201-221 | FLOAT→FLOAT; BOOLEAN, INT→INT; VECTOR; RGBA→COLOR; STRING; SHADER→CLOSURE; others UNDEFINED (skipped) |
| `set_default_value` | 223-275 | unlinked inputs: copy `default_value`; booleans → int 0/1; strings → absolute path |
| `get_tex_mapping` | 277-294 | `TexMapping.loc/rot/size/type/projx/y/z` → `tex_mapping.translation/rotation/scale/type/x_/y_/z_mapping` (min/max/use_minmax not synced) |
| `add_node` | 356-1201 | idname → Cycles class plus parameters (table below) |
| `node_use_modified_socket_name` | 1203-1210 | renames off only for OSL script nodes |
| `node_find_input_by_name` | 1212-1281 | input rename rules (below) |
| `node_find_output_by_name` | 1283-1323 | output rename rules (below) |
| `add_nodes_inlined` | 1334-1523 | mutes, reroutes, groups, links |
| `add_nodes` (inline step) | 1525-1545 | `blender::nodes::inline_shader_node_tree` (C++ only); Python must flatten itself |
| `sync_materials` fallback | 1697-1705 | no node tree → `DiffuseBsdf(color = mat.r,g,b)` → Surface |
| `sync_world` fallback | 1785-1800 | node tree used if present, else `Background(color = world.horr,g,b)` |
| ramp/curve sampling (`blender/util.h`) | 134-279 | `colorramp_to_array`: `RAMP_TABLE_SIZE+1 = 257` samples at `i/256` (`kernel/types.h:35`); `curvemapping_color_to_array`: range = min/max over curves, RGB curves composed with the combined curve `cm[3]`; `interpolate = (ipotype != CONSTANT)`; `extrapolate = CUMA_EXTEND_EXTRAPOLATE` |

**Socket matching**, in order. The lookup key is the Blender `socket.identifier`, matched against the Cycles
**UI name**.

Inputs:

1. Exact match.
2. If not found (non-OSL):
   - `startswith("Shader")` → replace with `"Closure"`.
   - For `ShaderNodeMix` only: suffix `Factor_Float`/`Factor_Vector` → `Factor`, and `A_Float|B_Float|A_Color|
     B_Color|A_Vector|B_Vector` → `A`/`B`.
   - Retry.
3. If still not found:
   - `_001`/`.001` → `2`, `_002`/`.002` → `3`, **else append `1`**.
   - Retry.
   - Examples: Math `Value` → `Value1`, `Value_001` → `Value2`; Mix Shader `Shader` → `Closure1`,
     `Shader_001` → `Closure2`.

Outputs:

- `"Shader"` → `"Closure"`.
- Mix: `Result_Float|_Color|_Vector` → `Result`.
- `FunctionNodeInputVector` `Vector` → `Color`.

Sockets with `!is_available()` are skipped (1461-1464, 1475-1478). Links are skipped if not `NODE_LINK_VALID`, if an
endpoint is unavailable, or if muted (1490-1497).

**Graph walk (`add_nodes_inlined`):**

- Muted nodes and reroutes become one same-type `ConvertNode` proxy per internal link (1353-1369).
- Groups get proxy `ConvertNode`s per input and output socket, keyed by identifier, then recurse (1370-1419).
- `NodeGroupInput` / `NodeGroupOutput` map to those proxies. Only the output with the `NODE_DO_OUTPUT` flag counts
  (1420-1446). Ordinary nodes: 1447-1487; links: 1490-1522.
- The output node is `ntreeShaderOutputNode(tree, SHD_OUTPUT_CYCLES)` (1349); the bpy equivalent is believed to be
  `node_tree.get_output_node('CYCLES')` (not checked in 5.2).
- Proxies are removed later by `ShaderGraph::remove_proxy_nodes`, called in `Shader::set_graph`
  (`scene/shader.cpp:283-312`).

**idname → Cycles class.** Lines are in `blender/shader.cpp`. "DNA field" is what C++ reads; the bpy/RNA names are
from general bpy knowledge and **not checked** against 5.2 makesrna.

| Blender idname | Cycles class | Parameters (C++ source → Cycles setter) |
|---|---|---|
| ShaderNodeValue / ShaderNodeRGB | ValueNode / ColorNode | output socket default (432-436 / 421-425) |
| ShaderNodeMath | MathNode | `custom1`→`NodeMathType` (direct cast), `custom2`→use_clamp (538-543) |
| ShaderNodeVectorMath | VectorMathNode | `custom1`→`NodeVectorMathType` (544-548) |
| ShaderNodeMixRGB | MixNode | `custom1`→`NodeMix`, `custom2 & SHD_MIXRGB_CLAMP` (461-466) |
| ShaderNodeMix | MixFloat / MixVector / MixVectorNonUniform / MixColor | `storage.data_type` (SOCK_VECTOR/SOCK_RGBA/else), `factor_mode`, `blend_type`, `clamp_factor`, `clamp_result` (467-493) |
| ShaderNodeMapRange | MapRange / VectorMapRange | `storage.data_type == CD_PROP_FLOAT3`, `interpolation_type`, `clamp` (518-532) |
| ShaderNodeClamp | ClampNode | `custom1` (533-537) |
| ShaderNodeInvert / Gamma / BrightContrast / HueSaturation | Invert / Gamma / BrightContrast / HSV | none (452-460, 512-514) |
| ShaderNodeSeparateColor / CombineColor | SeparateColor / CombineColor | `storage.mode` (494-505) |
| ShaderNodeSeparateXYZ / CombineXYZ | SeparateXYZ / CombineXYZ | none (506-511) |
| ShaderNodeRGBToBW | RGBToBWNode | none (515-517) |
| ShaderNodeValToRGB | RGBRampNode | ColorBand sampled to 257 entries (410-420) |
| ShaderNodeRGBCurve | RGBCurvesNode | CurveMapping sampled to 257 entries, min/max X, extrapolate (368-381) |
| ShaderNodeTexCoord | TextureCoordinateNode | `custom1`→from_dupli; `id` object → use_transform + ob_tfm = object_to_world (1084-1093) |
| ShaderNodeMapping | MappingNode | `custom1`→`NodeMappingType` (568-572) |
| ShaderNodeTexNoise | NoiseTextureNode | `storage.dimensions/type/normalize` + tex_mapping (1066-1074) |
| ShaderNodeTexWhiteNoise | WhiteNoiseTextureNode | `custom1`→dimensions (1129-1133) |
| ShaderNodeTexVoronoi | VoronoiTextureNode | `storage.dimensions/feature/distance/normalize` (1018-1028) |
| ShaderNodeTexChecker / TexGradient / TexWave / TexMagic / TexBrick | Checker / Gradient / Wave / Magic / Brick | storage fields + tex_mapping (1010-1065) |
| ShaderNodeTexImage | ImageTextureNode | `storage.interpolation/extension` (validated), `projection`, `projection_blend`, tex_mapping; image `colorspace_settings.name`, `alpha_mode`, tiles; builtin (packed/generated) → `BlenderImageLoader`, else file path (897-970) |
| ShaderNodeBsdfPrincipled | PrincipledBsdfNode | `custom1`: SHD_GLOSSY_GGX→GGX_GLASS_ID, MULTI_GGX→MULTI_GGX_GLASS_ID; `custom2`: subsurface method switch (726-752) |
| ShaderNodeBsdfDiffuse | DiffuseBsdfNode | none (597-599) |
| ShaderNodeBsdfAnisotropic (Glossy) | GlossyBsdfNode | `custom1` switch → BECKMANN / GGX / ASHIKHMIN_SHIRLEY / MULTI_GGX (645-663) |
| ShaderNodeBsdfGlass | GlassBsdfNode | `custom1` → BECKMANN_GLASS / GGX_GLASS / MULTI_GGX_GLASS (664-678) |
| ShaderNodeBsdfRefraction | RefractionBsdfNode | `custom1` → BECKMANN_REFRACTION / GGX_REFRACTION (679-690) |
| ShaderNodeEmission / BsdfTransparent / Background | Emission / Transparent / Background | none (773, 755, 591) |
| ShaderNodeMixShader / AddShader | MixClosure / AddClosure | none (582-584 / 579-581) |
| material/world output | `graph->output()` | (1451-1453) |

**Enum strategy for Python.**

- Most cases cast DNA ints directly to Cycles enums, e.g. `(NodeMathType)b_node.custom1`.
- bpy exposes RNA identifiers, and an RNA enum item's `.value` is the stored DNA int. Pass
  `node.bl_rna.properties[p].enum_items[node.p].value` for direct casts, and explicit tables for the switch-mapped
  ones (Glossy/Glass/Refraction/Principled distribution, Principled subsurface, Metallic, Sheen, Toon).
- Do **not** pass lowercased RNA strings to Cycles `NodeEnum`. They differ, e.g. image extension `REPEAT` vs NodeEnum
  `periodic`/`clamp`/`black`/`mirror` (`shader_nodes.cpp:244-293`), and Noise `fBM` casing.
- Numeric equality between DNA `SHD_*` / `NODE_*` constants and Cycles enums is **not checked** here
  (`DNA_node_types.h` is not in the clone). The golden test per node is the guard.

---

## 6. Images

- **Kernel path, verbatim:**
  - `svm_node_tex_image<float3>` (`kernel/svm/image.h:59-76`) → `svm_image_texture` (22-38) →
    `kernel_image_interp_with_udim` (`kernel/device/cpu/image.h:403-414`) → `kernel_image_udim_map`
    (`kernel/util/image_2d.h:17-46`; id ≥ 0 means direct) → `kernel_image_interp` (`cpu/image.h:328-401`).
  - If `KernelImageTexture.tile_descriptor_offset == UINT_MAX` (default `KERNEL_TILE_LOAD_NONE`,
    `util/types_image.h:120,149`), it samples `image_info[tex.image_info_id]` at
    `xy = (u·width, v·height)` (`cpu/image.h:357-366`).
  - `ImageInterpolator<TexT>` (`cpu/image.h:37-324`) implements closest, linear and cubic with extension
    repeat/extend/clip/mirror. `INTERPOLATION_SMART` falls to the cubic default branch (`cpu/image.h:313-323`).
  - After sampling: optional unassociate (`NODE_IMAGE_ALPHA_UNASSOCIATE`), then optional
    `color_srgb_to_linear_v4` (`NODE_IMAGE_COMPRESS_AS_SRGB`) (`image.h:25-35`).
- **Minimal CPU-only path:**
  - `kg->image_textures[i] = {image_info_id=i, tile_descriptor_offset=UINT_MAX, width, height, interpolation,
    extension}`.
  - `kg->image_info[i] = {data=(uint64_t)ptr, data_type, interpolation, extension, width, height}`.
  - `IMAGE_DATA_TYPE_FLOAT4` (0), `BYTE4` (1), `HALF4` (2) etc. are all supported by the `data_type` switch at `cpu/image.h:372-400`.
  - `image_load_requested_cpu` must exist as a member (it is referenced in `image_2d.h:163`) but is never called on
    this path.
  - Rows: index `y = v·height`, so row 0 is v = 0 (bottom). Blender `ImBuf`/`Image.pixels` are bottom-up
    (inferred; verify in X-colour).
- **Host colour and alpha** (what Cycles does, so painterly can reproduce it):
  - `ImageMetaData::finalize` (`util/image_metadata.cpp:123-182`):
    - `scene_linear` / `data` → as is.
    - `scene_linear_srgb` → keep 8-bit sRGB and set `is_compressible_as_srgb`. The kernel then interpolates in sRGB
      and linearises after.
    - Other colour spaces → byte/ushort promoted to **half** and converted with OCIO.
    - Alpha: unassociated sources are premultiplied on load (`image_metadata.cpp:498-509`).
  - `to_scene_linear` unpremultiplies, applies OCIO, re-premultiplies (`util/colorspace.cpp:470-530`).
  - Non-finite RGBA → 0 (`image_metadata.cpp:580-600`).
  - Builtin images (`blender/image.cpp:46-90`): float `ImBuf` → `scene_linear` (or `data`), else `BYTE4` with the
    image colour-space name and unassociated alpha.
- **OCIO dependency.** Painterly has none (plan), so Python must decide per image:
  - `is_data`
  - whether the colour space equals scene-linear or sRGB-on-scene-primaries (Cycles uses OCIO interop ids
    `lin_rec709_scene` / `srgb_rec709_scene`, `colorspace.cpp:829-863`)
  - and, for other spaces, pre-convert with Blender's PyOpenColorIO.
  - Exact 1-spp parity with Cycles requires matching the **storage type** too: sRGB bytes, then interpolate, then
    linearise in kernel; half rounding for converted bytes. Pre-linearised float4 would differ for linear/cubic
    interpolation. This belongs to X-colour.
- `kernel_data.film.{xyz_to_r/g/b, rgb_to_y, rec709_to_r/g/b, is_rec709}` (`kernel/data_template.h:67-76`) must be
  filled; Cycles does it in `ShaderManager::init_xyz_transforms` (`scene/shader.cpp:995-1023`).
  - Without OCIO, Cycles uses the Rec.709 XYZ matrix (`util/colorspace.cpp:687-702`) and
    `is_rec709 = true` (interop id `lin_rec709_scene`, line 862).
  - `rgb_to_y` is the Y row of the inverse (`shader.cpp:1018-1019`). This is a mathematical definition; cite it.

---

## 7. Random, noise and lookup tables

- `noise.h` includes only `util/{hash,math,types}.h`. `fractal_noise.h` includes `noise.h`. `voronoi.h`,
  `white_noise.h` and `gabor.h` include `util/hash.h` plus `node_types.h`/`util.h`.
- None of their evaluators take `kg` or read `kernel_data` (grep shows no `kg`/`KernelGlobals` in noise, fractal,
  noisetex, voronoi, white_noise, wave, magic, brick, checker, gradient).
- Header-level they still include `kernel/svm/util.h` → `kernel/globals.h`, so the `KernelGlobals` shim is needed to
  compile them.
- `brick.h:14` has its own integer hash. Wave uses `noise_fbm`.
- No LUTs for these. LUT and colour dependencies elsewhere:

| Node | Dependency |
|---|---|
| Blackbody | static `blackbody_table_r/g/b` (`kernel/tables.h:11-40`) + `kernel_data.film.rec709_to_*` |
| Wavelength | static `cie_color_match` (`tables.h:41`) + `film.xyz_to_*` |
| Sky | host-generated sky image through `kernel_image_interp` + Nishita/Preetham data inline + `kernel_data.background.use_sun_guiding` (`sky.h`); host needs `intern/sky` |
| BSDFs | `lookup_table` (§3.3) |
| Convert / RGB to BW | `film.rgb_to_y` |
| Image | §6 |

- RNG: `sd->lcg_state` is consumed only by tiled-image stochastic mip selection (`image_2d.h:102-108`) and
  `bsdf_principled_hair_huang.h`, plus bevel and intersection code that M6 does not use. Setting `lcg_state = 0`
  makes the SVM RNG-free, so SPEC §2's K counter is untouched.

---

## 8. Recommended staged plan, shims, risks

### 8.1 Mechanism

- Vendored files sit under `third_party/cycles/` at their upstream relative paths. Painterly shims shadow upstream
  paths through include order `-I src -I third_party/cycles`. Add `-I third_party` too, so a shim can wrap the real
  header as `#include "cycles/<path>"`; a same-named include would hit `#pragma once` on itself.
- Every vendored TU gets one global set of definitions:
  - `CCL_NAMESPACE_BEGIN=namespace painterly {` (already planned)
  - one fixed `__KERNEL_FEATURES__` mask
  - `WITH_EMBREE` **undefined**
  - one `__MAX_CLOSURE__`
- These definitions change `KernelData` and `ShaderData` layout (`kernel/types.h:11-16, 829-833`,
  `features.h:173-216`). Any mismatch between TUs is an ODR violation.
- Two extraction modes in `tools/vendor_sync.py`:
  - whole file, sha256 per file
  - function-anchored fragments for `shader_nodes.cpp`, `svm.cpp` and `svm.h` cases: extract
    `NODE_DEFINE(X)`, `X::X`, `X::compile(SVMCompiler&)`, `X::compile(OSLCompiler&)`, `X::constant_fold/expand/
    simplify_settings/attributes`, or `SVM_CASE(NODE_X)…break;` by brace or `break` matching, with a sha256 per
    fragment, generated into the build tree. This keeps code verbatim with no patches, and node ports only *add*
    manifest entries.

### 8.2 Stages (each stage is one or more cards)

1. **S0, ahead of M6 (affects M3 T3.2/T3.3).**
   - Vendor `kernel/types.h`, `kernel/features.h`, `kernel/data_template.h`, `kernel/data_arrays.h`,
     `kernel/svm/types.h`, `kernel/svm/node_types_template.h` verbatim.
   - Painterly `kernel/device/cpu/globals.h` shim: `kernel_array<T>`, one `KERNEL_DATA_ARRAY` X-macro over the
     vendored `data_arrays.h`, `KernelData data`, `KernelImageLoadRequestedCPU image_load_requested_cpu`, painterly's
     own `KernelPainterly painterly` beside `data` (not inside it), `using KernelGlobals = const …*`, and the four
     `kernel_data_*` macros (`cpu/globals.h:103-106`). No profiler, OSL or guiding.
   - Util shims: `util/thread.h`, `util/param.h`, `util/string.h`, `atomic_ops.h`. The util subset is the 53 headers
     in `m6_subset_closure.txt`.
2. **S1, stack-only evaluators (X-svm probe).**
   - Vendor `kernel/svm/{util,node_types,value,math,math_util,mix,color_util,map_range,clamp,invert,gamma,brightness,
     hsv,sepcomb_color,sepcomb_vector,convert,ramp,ramp_util,mapping,mapping_util}.h` and `kernel/tables.h`,
     `kernel/util/colorspace.h`. That is 92 files with the textures in S3.
   - Generated `src/kernel/svm/svm.h`: the switch built from verbatim `SVM_CASE` fragments of upstream
     `svm.h:117-616` plus the `NODE_END`/`SHADER_JUMP`/`JUMP_IF_*` cases.
   - Doctest: hand-encoded byte code using the structs.
3. **S2, graph core (T6.1/T6.2).**
   - Vendor `graph/node{,_type}.{h,cpp}`, `node_enum.h`, and `util/{md5,log,string,time,transform,guarded_allocator}
     .cpp`; shim `util/path.h`.
   - Then `scene/shader_graph.{h,cpp}`, `constant_fold.{h,cpp}`, `shader_nodes.h` with shims `scene/{scene,shader,
     attribute,image,osl}.h`.
   - Extract the core node set from §4.4 plus `TextureMapping`, `BsdfBaseNode`/`BsdfNode`, `CurvesNode` and
     `shader_bump_to_node_bump_offset`.
4. **S3, compiler (T6.3).**
   - Vendor `scene/svm.h`; extract `SVMCompiler` (`svm.cpp:157-1281`). The alternative is verbatim `svm.cpp` with
     the larger shim set in §4.7; X-svm should measure both.
   - Port the jump-table packing (`svm.cpp:95-133`) and `ShaderManager::device_update_pre/common` pieces
     (`shader.cpp:520-590, 612-748`) into painterly code.
5. **S4, textures.** Noise, White Noise, Voronoi, Checker, Gradient, Wave, Magic, Brick evaluators + node fragments.
   TexCoord needs `tex_coord.h`, `attribute.h`, `geometry.h` and therefore `kernel/geom/*` (10 files), `kernel/camera`,
   `kernel/bvh/util.h` → `kernel/integrator/state.h`. All verbatim. The painterly scene must then fill `objects`,
   `object_flag`, `attributes_map`, `attributes_float2/float3`, `tri_vindex` (and `tri_verts`/`tri_shader` for smooth
   normals) in Cycles layout.
6. **S5, closures.** Vendor `kernel/svm/closure.h` + all 26 `kernel/closure/*.h`, `kernel/util/lookup_table.h`,
   `scene/shader.tables`. Add the closure collector (§3.4) and LUT upload.
7. **S6, images.** `kernel/svm/image.h`, `kernel/image.h`, `kernel/device/cpu/image.h`, `kernel/util/image_2d.h`,
   `util/types_image.h`, `util/half.h`; the painterly `scene/image.h` shim and Python pixel export (X-colour).
8. **S7, Python sync.** `flatten.py` from `add_nodes_inlined`; `node_table.py` from `add_node` and helpers;
   `export.py` sockets per §5.

### 8.3 Risks and blockers

- **B1 (forces a design change, not a patch).** A painterly-owned `kernel/types.h` cannot replace Cycles'. The
  vendored headers need `ShaderData`, `ShaderClosure`, `SD_*`, `PATH_RAY_*`, `PRIMITIVE_*`, `AttributeDescriptor`,
  `KernelObject`, `KernelData` with `film`, `cam`, `integrator`, `tables`, `image`, `background`, `scene_time`,
  `svm_usage`, and more. Fix: T3.3 vendors it verbatim and puts painterly constants in a separate struct.
  Adding a member *inside* `KernelData` would require patching `data_template.h` or `types.h`.
- **B2.** `features.h` cannot undefine `__SHADER_RAYTRACE__`, `__CAUSTICS_TRICKS__`, `__RAY_DIFFERENTIALS__`,
  `__DPDU__` (lines 125-147). Handled without a patch: don't include `ao/bevel/raycast.h` (generated switch), and set
  `caustics_reflective = caustics_refractive = 1`.
- **B3.** `util/atomic.h:10` includes Blender's `atomic_ops.h` (outside `intern/cycles`). Either vendor
  `intern/atomic` (license and contents not checked) or provide a shim header. Nothing in the M6 subset was seen
  calling an atomic, but this is **not verified** for all of `util/`.
- **B4.** `util/thread.h:23` (TBB), `util/param.h:10-12`, `util/string.h:13` (OIIO) and `util/path.cpp` (OIIO,
  zstd) need shims. `util/colorspace.cpp` is not vendorable (includes `util/image.h` → OIIO).
- **R1, static registration.** `NODE_DEFINE` registers through static initialisers. If node TUs go into a static
  library, the linker may drop them. The generated registry must reference each `X::get_node_type()`, or the objects
  must be linked directly.
- **R2, compile-time breadth.** Even unused inline helpers (curve, point, volume, motion) must compile, so the
  `KernelGlobals` shim must declare **all** arrays in `data_arrays.h` and painterly's scene must use Cycles' layouts
  for whatever it fills. Hair, pointcloud, volume and object-motion code can be compiled out with
  `__KERNEL_FEATURES__`.
- **R3, socket naming.** Two name spaces: `ShaderNode::input()` uses `ui_name`, `NodeType::find_input()` uses the
  member name. The T6.2 contract must say which one the Python export uses. Blender sync uses `ui_name` for links and
  defaults, and typed setters (`set_math_type`…) for parameters.
- **R4, LUT-dependent weights.** Principled lower-layer weights depend on `lookup_table` (§3.3). A missing or wrong
  LUT gives silently wrong lobe weights, not a crash, in release builds.
- **R5, image parity.** Storage type (sRGB bytes, half) and alpha association change results at 1 spp (§6).
  Without OCIO, colour-space classification must come from Python.
- **R6, MSVC include search order.** MSVC also searches the directories of every currently open includer before
  `/I`. Shadowing works only while no relative `kernel/...` path exists under `src/kernel/svm/`. Add a build test,
  e.g. each shim `#define`s a marker and one TU `static_assert`s it.
- **R7, scale and churn.** M6 vendors about 150 kernel files (37k lines) plus host fragments. Upstream changes to
  the typed-SVM structs or `SVMCompiler` API are frequent (5.2 introduced this design); pinning plus fragment hashes
  catches drift.
- **R8, Blender 5.x shader-tree features.** Closure and bundle zones and repeat zones are handled only by
  `inline_shader_node_tree`. The Python flattener must reject or approximate them; behaviour **not checked**.
- **R9, plan text.** "104 `SVMNode*` structs; each takes only the stack and a typed node" (plan, Architecture)
  should be corrected (§0 item 2) so card authors don't assume a single evaluator signature. The generated switch
  should copy upstream `SVM_CASE` bodies rather than synthesise calls.

### 8.4 Not checked

- Blender RNA property and socket identifiers in 5.2 (`source/blender/makesrna`, `source/blender/nodes`) and DNA
  numeric enum values.
- `bpy` `ColorRamp.evaluate` / `CurveMapping.evaluate` availability in 5.2.
- `Image.pixels` semantics (colour space, alpha, row order).
- Default Glass/Glossy distribution in Blender 5.2's UI.
- `intern/atomic` and `intern/sky` contents and licenses.
- Whether the vendored files actually compile with the proposed shims; nothing was built.
- The plan's claim that candidates are byte-identical to standalone v5.2.0.
