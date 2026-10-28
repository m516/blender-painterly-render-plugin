# B5 — The world shader on misses
Milestone: M6b · Depends on: B4 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B5" (lines 182-196) and its section 1 decisions 6 and 8
(lines 58-66 and 75-77), per that brief's section 4 (lines 303-324). Code facts are
`docs/handoff/drafts/M6b/FACTS.md` §3, re-read at this clone's HEAD in every file cited below.

## Goal
A ray that escapes the scene is shaded by Cycles' own SVM when the world carries a node graph, and by the constant
radiance when it does not:
- `KernelPainterlyBackground` (`src/painterly/kernel/types.h:152-156`) gains `int cycles_shader`, -1 meaning constant
  radiance (BRIEF.md:184). The kernel's field is written from the host scene by `PainterlyBackground::device_update`
  (`src/painterly/scene/background.cpp:25-31`), which already writes `radiance` and `num_suns`.
- `PainterlyScene::set_background_shader(int shader)` binds a graph added by B2's `add_shader` as the world, and -1
  unbinds it (BRIEF.md:185).
- On a miss with `cycles_shader >= 0`, `painterly_svm_background_setup` fills the `ShaderData` as Cycles'
  `shader_setup_from_background` does (upstream `intern/cycles/kernel/geom/shader_data.h:387-428`): `P = D` normalized,
  `N = Ng = wi = -D`, `OBJECT_NONE`/`PRIM_NONE`/`PRIMITIVE_NONE`, `u = v = 0`, `ray_length = FLT_MAX`, and zero `dPdu`,
  `dPdv`, `dP`, `dI`, `du`, `dv` (BRIEF.md:186-188). It evaluates with `painterly_svm_background_feature_mask`
  (`src/painterly/kernel/svm/collect.h:41-42`) and the radiance is the Background closure's weight (BRIEF.md:188-189).
- Suns are added as today and everything is scaled by `emission_gain` (SPEC §6, `docs/spec.md:226`; B5 keeps
  `path.h:81-83`'s `painterly_emission_term`).
- A scene without a world shader is bit-identical to today: `cycles_shader < 0` starts the sum from today's
  `background.radiance` and runs today's sun loop, in the same order, and neither reads nor writes the `ShaderData`
  scratch (BRIEF.md:195). T3.16's parity test and T3.17's triangle test are the check, unchanged.

No knob is added (BRIEF.md:75-77): the world is a shader or a constant, and `emission_gain` already exists.

## Read first
- `CLAUDE.md` rules 1, 2 and 3; `AGENTS.md` "Expected values are evidence"; SPEC §2 (`docs/spec.md:51`: a miss never
  advances K) and §6 (`:169` "A miss returns the world/background radiance", `:226` the world and the `emission_gain`
  scale).
- `docs/handoff/drafts/M6b/BRIEF.md` lines 58-66 (decision 6, the ShaderData recipe), 75-77 (decision 8, no new knob),
  182-196 (this card's mandate) and 303-324 (how the cards are drafted).
- The CONTRACT header `src/painterly/kernel/types.h` (read it, never edit it: `:4` is `CONTRACT: Opus-owned`):
  `KernelPainterlyBackground` `:152-156`, `KernelPainterlyData` `:158-162`, `KernelPainterlyMaterial` `:101-106`.
- `src/painterly/kernel/light/background.h` in full (`:17-29`, the constant radiance and the suns loop) and its two
  callers `src/painterly/kernel/integrator/path.h:79-85` (the miss branch) and `src/test/test_path.cpp:466`, `:471`.
- `src/painterly/kernel/svm/collect.h`: the evaluation contract `:11-23`, the two masks `:34-48`,
  `painterly_svm_collect` `:165-211` and its emission expression `:170-174`.
- `src/painterly/kernel/svm/hit_material.h` (B4's; the same shape of setup-then-evaluate, and the per-call `ShaderData`
  this card's miss branch reuses), `src/painterly/kernel/svm/shader_data.h` (B3's).
- `third_party/cycles/fragments/kernel/svm/svm_h/span/svm_eval_nodes_head.inc:1-18`: the call shape, and
  `offset = (sd->shader & SHADER_MASK) * (1 + sizeof(SVMNodeShaderJump) / sizeof(uint))` at `:13`, which is why the
  setup must write `sd->shader`.
- `third_party/cycles/kernel/types.h`: `ShaderData` `:1030-1096` (`P` `:1021`, `N` `:1023`, `Ng` `:1025`, `wi` `:1027`,
  `type` `:1030`, `shader` `:1033`, `flag` `:1035`, `object_flag` `:1037`, `num_closure`/`num_closure_left`
  `:1040-1041`, `prim` `:1044`, `u`/`v` `:1048-1049`, `object` `:1051`, `time` `:1054`, `ray_length` `:1057`,
  `dP`/`dI`/`du`/`dv` `:1059-1067`, `dPdu`/`dPdv` `:1068-1073`, `ray_P` `:1082-1083`, `lcg_state` `:1087`,
  `closure_emission_background` `:1091`), `OBJECT_NONE`/`PRIM_NONE` `:47-48`, `PRIMITIVE_NONE` `:686`,
  `SD_EMISSION` `:903`, `SHADER_MASK` `:493`, `KernelShader` `:1665-1671`, `KernelData::max_closures` `:1370`,
  `differential` `:583-586`.
- `third_party/cycles/kernel/features.h:87-91` (the background mask's definition), `:141` (`__DPDU__`) and `:145`
  (`__RAY_DIFFERENTIALS__`, so both differential groups exist in this build).
- `third_party/cycles/kernel/closure/emissive.h:16-25` (`background_setup`: the summed weight and `SD_EMISSION`) and
  `third_party/cycles/kernel/svm/closure.h:1432-1451` (`svm_node_closure_background`, the mix weight),
  `:1477-1482` (`svm_node_closure_set_weight`), `:1491-1497` (`svm_node_emission_weight`).
- Upstream, at the vendored tag (v5.2.2; FACTS.md:340-343 lists it as not vendored):
  `intern/cycles/kernel/geom/shader_data.h:387-428` (`shader_setup_from_background`),
  `intern/cycles/kernel/integrator/surface_shader.h:1191-1197` (`surface_shader_background`),
  `:1249-1297` (`surface_shader_eval`, `num_closure`/`num_closure_left`/`closure_transparent_extinction` at
  `:1273-1275`), `intern/cycles/kernel/integrator/shade_background.h:40-91` (how Cycles calls the two).
- `third_party/cycles/fragments/scene/shader_nodes_cpp/node_define/BackgroundNode.inc` (the node's sockets),
  `.../member/BackgroundNode.compile-SVMCompiler.inc` (`:1-30`: the constant branch and the linked branch),
  `.../node_define/GradientTextureNode.inc:17` (Vector defaults to `LINK_TEXTURE_GENERATED`) and
  `third_party/cycles/kernel/svm/gradient.h:14-73` (`svm_gradient`, `saturatef` at `:65`),
  `third_party/cycles/scene/shader_graph.cpp:864-884` (`default_inputs` connects Texture Coordinate's Generated to
  such an input), `third_party/cycles/fragments/scene/shader_nodes_cpp/member/TextureCoordinateNode.compile-SVMCompiler.inc:8-21`
  (for `compiler.background`, Generated compiles to `NODE_GEOMETRY`/`NODE_GEOM_P`), and
  `third_party/cycles/kernel/svm/geometry.h:28-30` with `third_party/cycles/kernel/svm/util.h:238-249`
  (`NODE_GEOM_P` is `sd->P`).
- `src/painterly/scene/scene.h` (`:34-112`, `background` at `:41`, `set_background` `:89`), `src/painterly/scene/scene.cpp:139-142`,
  `src/painterly/scene/background.h:17-31`, `src/painterly/scene/background.cpp:25-31`,
  `src/painterly/scene/device_scene.cpp:92-304` (the strong guarantee `:94-97`, the background block `:258-259`, the
  commit `:289-303`), `src/painterly/scene/svm/shader_manager.h:48` (`background_shader`) and `:242`
  (`compiler.background = (shader == background_shader)`).
- `third_party/cycles/fragments/scene/svm_cpp/member/SVMCompiler.compile_type.inc:69` (`reference_count()`), which is
  what BRIEF.md:47-48 means by "Cycles compiles only referenced shaders".
- `src/painterly/util/math_double3.h:60-70` (`len`, `normalize` — reciprocal, then multiply: the direction this card
  passes to the setup is that exact value), `src/painterly/kernel/camera/camera.h:54-99`
  (`painterly_camera_generate_ray`), `src/painterly/kernel/film/write.h:13-20` (`painterly_film_accumulate`).
- `src/test/test_path_trace.cpp:37-105` (the render-on-a-pool helper and `bit_identical`), `src/test/bitwise.h:40-51`
  (`same_bits`, `same_vec`), `src/test/smallpaint_scene_fixture.h:100-148` (the knob block, `:146-147` the background
  fields), `src/test/test_cycles_svm_closures.cpp:44-138` (`make_scene`, `create_node_by_name`, `add_surface`,
  `evaluate` — the graph-building helpers this card's test copies).
- The parity tests this card must keep green unchanged: `tests/core/test_oracle_parity.py` and
  `tests/core/test_triangle_path.py`.

## Create
- `src/painterly/kernel/svm/background_shader.h`
- `src/test/test_svm_world.cpp`

## Modify
- `src/painterly/scene/background.h`: the host member `int cycles_shader = -1;` with its comment; the class comment.
- `src/painterly/scene/background.cpp`: `device_update` writes `background.cycles_shader = cycles_shader;`.
- `src/painterly/scene/scene.h`: the declaration of `set_background_shader` and its comment, beside `set_background`
  (`:88-89`).
- `src/painterly/scene/scene.cpp`: the definition, beside `set_background` (`:139-142`).
- `src/painterly/scene/device_scene.cpp`: one block before the shader manager's first step, the range check of the
  world's shader id and the write of the manager's `background_shader` (step 5); the include of
  `"painterly/scene/svm/shader_manager.h"` for the cast.
- `src/painterly/kernel/light/background.h`: include the new header; `painterly_background_radiance` takes the
  caller's `ShaderData` scratch and branches on `cycles_shader` (step 7).
- `src/painterly/kernel/integrator/path.h`: the miss branch (`:79-85`) passes the per-call `ShaderData` B4 added.
- `src/test/smallpaint_scene_fixture.h`: `data.background.cycles_shader = -1;` in `set_knobs` (`:146-147`).
- `src/test/test_path.cpp`: the two direct calls `:466` and `:471` pass a local `ShaderData`; their expected values do
  not move (step 10).
- `src/test/CMakeLists.txt`: `test_svm_world.cpp` in `painterly_tests` (step 11).

## Do not touch
- `src/painterly/kernel/types.h` (CONTRACT, `:4`): the `int cycles_shader` field is Opus's and arrives before dispatch
  (see `## Interface`). `src/painterly/kernel/globals.h` is B1's, `src/blender/_painterly.pyi` is B6's and B8's.
- `third_party/cycles/**` (vendored; `tools/vendor_sync.py` only) and `src/cycles/shim/**`. This card vendors nothing:
  the Background and Gradient evaluators are already vendored (`third_party/cycles/kernel/svm/closure.h:1432-1451`,
  `third_party/cycles/kernel/svm/gradient.h`), and `shader_setup_from_background` is written here, not vendored
  (BRIEF.md:58-60, decision 6).
- `src/painterly/kernel/svm/collect.h` (T6.7's), `src/painterly/kernel/svm/shader_data.h` (B3's),
  `src/painterly/kernel/svm/hit_material.h` and `src/painterly/kernel/closure/lobe.h` (B4's).
- `src/painterly/scene/svm/shader_manager.h` (B2 moves it into `painterly_scene`): this card reads its
  `background_shader` member (`:48`) and writes that member from `device_update`; it changes no line of the header.
- `src/test/test_scene.cpp`, `src/test/test_path_trace.cpp`, `src/test/test_session.cpp`: their expected values must
  not move. In particular `test_scene.cpp:863-864` (`ds.data.background.radiance`, `num_suns`) and `:898-960` (the
  strong guarantee) keep every value they have.
- `tests/core/test_oracle_parity.py`, `tests/core/test_triangle_path.py`: they must pass unchanged, so not one line of
  either may move.
- `Makefile`, `pyproject.toml`, `src/cycles/CMakeLists.txt`, `src/painterly/kernel/CMakeLists.txt`,
  `src/painterly/scene/CMakeLists.txt`: this card adds no library, no source file of a library and no flag.

## Interface
CONTRACT (Opus writes this before dispatch): `src/painterly/kernel/types.h`, one member of `KernelPainterlyBackground`,
exactly as BRIEF.md:184 gives it:

    int cycles_shader

"the Cycles shader id, -1 meaning constant radiance" (BRIEF.md:184). The struct's existing members carry no default
initialiser (`types.h:152-156`), so the field has none either: every producer writes it, which is what
`PainterlyBackground::device_update` does for every scene. The comment and the position in the struct are Opus's.

Not a CONTRACT: `src/painterly/scene/scene.h` gains

    /* The world shader: a shader index from add_shader, or -1 for the constant radiance of
     * set_background (SPEC §6; BRIEF.md:184-185). Throws std::invalid_argument for an index below
     * -1 or outside cycles_' shader list. The shader is referenced here, so Cycles compiles it
     * (SVMCompiler.compile_type.inc:69); device_update binds it as the shader manager's
     * background_shader. */
    void set_background_shader(int shader);

and `src/painterly/scene/background.h` gains

    /* The world shader's Cycles shader id, or -1 for the constant radiance above (SPEC §6). */
    int cycles_shader = -1;

`src/painterly/kernel/svm/background_shader.h` declares the two kernel functions this card adds. No other card
depends on more than these names:

    /* The ShaderData of a miss, as Cycles' shader_setup_from_background() fills it (upstream
     * intern/cycles/kernel/geom/shader_data.h:387-428; BRIEF.md:186-188). `dir` is the normalized
     * view direction: it is what P, N, Ng and wi are built from. */
    ccl_device_inline void painterly_svm_background_setup(PainterlyGlobals kg,
                                                          const double3 dir,
                                                          int cycles_shader,
                                                          ccl_private ShaderData *sd);

    /* The world's radiance along `dir`, before emission_gain, from the Background closures that one
     * evaluation with painterly_svm_background_feature_mask collects (BRIEF.md:188-189). */
    ccl_device_inline double3 painterly_svm_background_radiance(PainterlyGlobals kg,
                                                                const double3 dir,
                                                                int cycles_shader,
                                                                ccl_private ShaderData *sd);

and `painterly_background_radiance` (`src/painterly/kernel/light/background.h:17`) gains the scratch:

    ccl_device_inline double3 painterly_background_radiance(PainterlyGlobals kg,
                                                            const double3 d,
                                                            ccl_private ShaderData *sd);

The three callers are `path.h:81` and `test_path.cpp:466`, `:471`; the scratch is B4's per-call `ShaderData` at the
first and a local at the other two.

## Steps
1. Preconditions. Each must hold; otherwise stop, commit nothing and report what you saw.
   - B1 has landed. This prints `1`:
     ```
     grep -c 'KernelGlobalsCPU \*cycles' src/painterly/kernel/globals.h
     ```
   - B2 has landed. These print at least `1`, `1` and `1`:
     ```
     grep -c 'add_shader' src/painterly/scene/scene.h
     grep -c 'add_node_material' src/painterly/scene/scene.h
     grep -c 'Scene> cycles_' src/painterly/scene/scene.h
     ```
     The third is BRIEF.md:38's `std::unique_ptr<Scene> cycles_`. If B2 gave the member another name, use that name in
     steps 4 and 5 and say so in the answer; nothing else in the card depends on it.
   - B4 has landed: the per-call `ShaderData` this card's miss branch reuses. Each of these prints `1`:
     ```
     grep -c 'ShaderData sd;' src/painterly/kernel/integrator/path.h
     grep -c 'PainterlyHitMaterial painterly_hit_material(' src/painterly/kernel/svm/hit_material.h
     ```
   - The CONTRACT member of `## Interface` is present. This prints `1`:
     ```
     awk '/^struct KernelPainterlyBackground/,/^};/' src/painterly/kernel/types.h | grep -c 'int cycles_shader'
     ```
     If it prints `0`, the contract has not arrived: stop and report (CLAUDE.md rule 1; the member is Opus's).
   - The constant path this card must not change is still the two `L` statements it keeps. This prints `1` and `1`
     (`light/background.h:21` and `:25`):
     ```
     grep -c 'double3 L = background.radiance;' src/painterly/kernel/light/background.h
     grep -c 'L = L + sun.radiance;' src/painterly/kernel/light/background.h
     ```
2. `src/painterly/scene/background.h`: after `suns` (`:22`), the member of `## Interface`, and extend the class comment
   (`:6-8`) with the world shader it now names. `-1` is the default, so a scene that never calls
   `set_background_shader` keeps today's constant world (BRIEF.md:195).
3. `src/painterly/scene/background.cpp`, in `device_update` (`:25-31`), beside the two lines it already has:
   ```cpp
   background.cycles_shader = cycles_shader;
   ```
   This is the only writer of the kernel field: `KernelPainterlyData new_data{}` in
   `src/painterly/scene/device_scene.cpp:106` zero-initialises it, so a value of `0` would name shader 0 on every
   scene that never bound a world. Writing it here, from a member whose default is -1, is what makes "a scene without
   a world shader is unchanged" true rather than accidental.
4. `src/painterly/scene/scene.h` and `scene.cpp`: the declaration of `## Interface` beside `set_background` (`:88-89`)
   and its definition beside `scene.cpp:139-142`:
   ```cpp
   void PainterlyScene::set_background_shader(const int shader)
   {
     /* -1 is the constant radiance (BRIEF.md:184), so it is accepted and unbinds. An index is checked
      * here, where the caller chooses it; device_update checks it again, because `background` is a
      * public member and can be written directly. */
     if (shader < -1 || (shader >= 0 && size_t(shader) >= cycles_->shaders.size())) {
       throw std::invalid_argument("PainterlyScene::set_background_shader: shader index out of range");
     }
     /* BRIEF.md:47-48: Cycles compiles a shader only while it is referenced
      * (SVMCompiler.compile_type.inc:69). Binding the same shader twice must not count twice, and
      * nothing else tests the count than non-zero. */
     if (shader >= 0 && shader != background.cycles_shader) {
       cycles_->shaders[size_t(shader)]->reference();
     }
     background.cycles_shader = shader;
   }
   ```
   `cycles_` and the shader list are B2's (BRIEF.md:38-40); `unique_ptr_vector::operator[]` returns the `Shader *`
   (`third_party/cycles/util/unique_ptr_vector.h:27-30`) and `size()` is `:64-66`; `reference()` is
   `src/cycles/shim/scene/shader.h:150-153`.
   `PainterlyScene::clear()` (`scene.cpp:21-33`) needs no line: it assigns a fresh `PainterlyBackground`, whose
   `cycles_shader` is -1, and step 5's second half re-derives the manager's pointer at the next device update. The
   shader that was bound keeps its reference count, so it is still compiled; nothing reads it, and B2's device update
   is the only consumer of the count.
5. `src/painterly/scene/device_scene.cpp`: one block, placed immediately before B2's first shader-manager step
   (BRIEF.md:43-46) and therefore before anything reads the world, with the two halves in this order. The existing
   "Background and suns" block (`:258-259`) keeps its line unchanged.
   - First the range check, in the style of the three checks already there (`:128-130`, `:153-157`, `:185-187`), so a
     hand-set field throws before the commit and the strong guarantee (`:94-97`) holds:
     ```cpp
     /* The world's shader id, checked here as well as in set_background_shader: `background` is a
      * public member of PainterlyScene. A value below -1 or outside the shader list would make the
      * kernel fetch past `kg->cycles->shaders` (kernel_array::fetch, shim globals.h:32-36). The
      * `>= 0` is load-bearing: size_t(-1) is SIZE_MAX, so without it the default -1 of every scene
      * that never bound a world would throw here. */
     if (background.cycles_shader < -1 ||
         (background.cycles_shader >= 0 &&
          size_t(background.cycles_shader) >= cycles_->shaders.size())) {
       throw std::invalid_argument(
           "PainterlyScene::device_update: background shader index out of range");
     }
     ```
   - Then the one write of the manager's pointer, which the check above has already made safe:
     ```cpp
     /* The world shader the compiler tags as the background (shader_manager.h:48, :242), derived
      * from the scene's field at every update, so that a clear() or a re-bind cannot leave a stale
      * pointer behind. A nullptr means no shader is the background, which is Cycles' state before a
      * world exists. */
     static_cast<PainterlyShaderManager &>(*cycles_->shader_manager).background_shader =
         (background.cycles_shader >= 0) ? cycles_->shaders[size_t(background.cycles_shader)] : nullptr;
     ```
   - It must run before `device_update_post`, which is where `compiler.background` is read (`shader_manager.h:242`),
     and after the check, which is why the two are one block and not two.
   - The write is legal in this `const` member function because `cycles_` is a `std::unique_ptr<Scene>`: in a const
     member the pointer is const and `operator*` still returns a non-const `Scene &`. This is the same reason
     BRIEF.md:40-42 keeps `device_update` const while the shader manager fills `cycles_`'s cache.
   - `device_scene.cpp` needs one include for the cast, `"painterly/scene/svm/shader_manager.h"`, in the block at
     `:10-12`. B2 moves that header into `painterly_scene` (BRIEF.md:139-141), the library `device_scene.cpp` already
     belongs to (`src/painterly/scene/CMakeLists.txt:6-13`), so the include costs no new dependency; if B2's device
     update exposes the manager another way, use that and say so in the answer.
6. `src/painterly/kernel/svm/background_shader.h`:
   ```cpp
   /* SPDX-FileCopyrightText: 2026 The Painterly Authors
    * SPDX-License-Identifier: GPL-3.0-or-later */

   #pragma once

   /* The world shader on a miss (SPEC §6; card M6b B5). Cycles fills the ShaderData of a background ray in
    * shader_setup_from_background() and evaluates it with the surface mask of a background; this header
    * writes the same fields and runs the same evaluation through painterly's own ShaderData
    * (BRIEF.md:58-66, :186-189). */

   #include <cfloat> /* FLT_MAX, upstream geom/shader_data.h:406. */

   #include "svm_eval_nodes.h"

   #include "painterly/kernel/globals.h"
   #include "painterly/kernel/svm/collect.h"
   #include "painterly/kernel/types.h"

   #include "util/math_float3.h" /* The unary minus of -ray_D (upstream :399-401). */

   CCL_NAMESPACE_BEGIN

   /* See ## Interface. Every field is the one upstream geom/shader_data.h:387-428 writes; the fields it leaves
    * alone (num_closure, lcg_state, the closure array) are zero, as surface_shader_eval() leaves them
    * (upstream integrator/surface_shader.h:1273-1275) and as collect.h:11-23 requires. The caller's `sd` may
    * hold an earlier bounce's closures, so it is zeroed first: 6480 bytes, once per miss. */
   ccl_device_inline void painterly_svm_background_setup(PainterlyGlobals kg,
                                                         const double3 dir,
                                                         const int cycles_shader,
                                                         ccl_private ShaderData *sd)
   {
     *sd = ShaderData{};

     /* The direction as a float3. `dir` is the unit direction `painterly_background_radiance` computed
      * with normalize() (util/math_double3.h:67-70); the float3 is the precision upstream's setup
      * takes (a float3 ray_D). */
     const float3 d = make_float3(float(dir.x), float(dir.y), float(dir.z));

     sd->P = d;      /* :398: P = ray_D, already normalized by the caller */
     sd->N = -d;     /* :399 */
     sd->Ng = -d;    /* :400 */
     sd->wi = -d;    /* :401 */

     /* :402-403: the shader and its KernelShader flags. `shader` selects the jump word
      * (svm_eval_nodes_head.inc:13); the flags are the value shader_setup_from_ray() gives a surface hit
      * too (B3). `kg` is the painterly globals, so the Cycles globals are `kg->cycles`, and the shader
      * array is the one B2 bound there. */
     sd->shader = cycles_shader;
     sd->flag = kg->cycles->shaders.fetch(cycles_shader & SHADER_MASK).flags;

     sd->ray_length = FLT_MAX; /* :406 */

     sd->object = OBJECT_NONE;    /* :408 */
     sd->prim = PRIM_NONE;        /* :409 */
     sd->type = PRIMITIVE_NONE;   /* :410 */
     sd->u = 0.0f;                /* :411 */
     sd->v = 0.0f;                /* :412 */

     /* :414-418 (dPdu, dPdv) and :420-427 (dP, dI, du, dv) stay zero: painterly has no ray
      * differentials and no tangents (BRIEF.md:64, :188). `time` (:405) and `object_flag` (:404) are
      * zero for the same reason: painterly has no motion blur and no object. */
   }

   /* See ## Interface. The value is the summed weight of the Background closures, which is what
    * surface_shader_background() returns (upstream integrator/surface_shader.h:1191-1197) and the expression
    * painterly_svm_collect() uses for a material's emission (collect.h:170-174). */
   ccl_device_inline double3 painterly_svm_background_radiance(PainterlyGlobals kg,
                                                               const double3 dir,
                                                               const int cycles_shader,
                                                               ccl_private ShaderData *sd)
   {
     painterly_svm_background_setup(kg, dir, cycles_shader, sd);
     /* collect.h:17-18 and upstream surface_shader.h:1270-1274: the closure budget is
      * kernel_data.max_closures, written after the setup so it is the value this evaluation runs with. */
     sd->num_closure_left = int(kg->cycles->data.max_closures);
     svm_eval_nodes<painterly_svm_background_feature_mask, SHADER_TYPE_SURFACE>(
         kg->cycles, nullptr, sd, nullptr, PathRayVisibility(0), uint32_t(0));
     if ((sd->flag & SD_EMISSION) == 0) {
       return make_double3(0.0);
     }
     return make_double3(double(sd->closure_emission_background.x),
                         double(sd->closure_emission_background.y),
                         double(sd->closure_emission_background.z));
   }

   CCL_NAMESPACE_END
   ```
   - The mask is the brief's (`BRIEF.md:188-189`): `painterly_svm_background_feature_mask` is Cycles'
     `KERNEL_FEATURE_NODE_MASK_SURFACE_BACKGROUND` (`collect.h:41-42`, `kernel/features.h:87-91`), which has
     `EMISSION` and not `BSDF`. So a Background closure allocates its weight
     (`kernel/svm/closure.h:1432-1451` → `closure/emissive.h:16-25`), a BSDF on a world allocates nothing, and the
     radiance is zero for both a world with no emission and a miss with no world.
   - `svm_eval_nodes.h` is the generated header `cycles_svm` puts on the include path
     (`src/cycles/CMakeLists.txt:116-132`), reached through `painterly_kernel` → `cycles_svm` (B1). It is listed
     first, as `src/test/cycles_svm_test_support.h:75` lists it, because it brings its own includes.
   - The shader flags are read as `kg->cycles->shaders.fetch(...)` and not through `kernel_data_fetch(shaders, i)`:
     that macro is `(kg->name.fetch(index))` (`src/cycles/shim/kernel/device/cpu/globals.h:62`), and here `kg` is
     `PainterlyGlobals`, i.e. `const PainterlyGlobalsCPU *` (`src/painterly/kernel/globals.h:70`), which has no
     `shaders` member (`:40-68`). `kg->cycles` is the `KernelGlobalsCPU` that has it (B1).
   - No value is invented: the weight is a `float3` product computed on the host by Cycles' own compile
     (`BackgroundNode.compile-SVMCompiler.inc`, `svm_node_closure_set_weight`/`svm_node_emission_weight`,
     `kernel/svm/closure.h:1477-1482`, `:1491-1497`) and widened to double here, exactly as `collect.h:170-174` does.
7. `src/painterly/kernel/light/background.h`:
   - `#include "painterly/kernel/svm/background_shader.h"` after `globals.h` (`:9`), and the new parameter of
     `## Interface`; the comment above the function (`:14-16`) gains the world shader it now reads.
   - The body: `dir` and the suns loop keep every operation they have, in the same order; only the starting value is
     chosen:
     ```cpp
     const KernelPainterlyBackground &background = kg->data->background;
     const double3 dir = normalize(d);
     /* SPEC §6 (:226): the world is constant in M3-M5 and a node graph from M6. `cycles_shader < 0` is
      * today's line, and it neither reads nor writes `sd`. */
     double3 L = (background.cycles_shader >= 0) ?
                     painterly_svm_background_radiance(kg, dir, background.cycles_shader, sd) :
                     background.radiance;
     for (int i = 0; i < background.num_suns; i++) {
       const KernelPainterlySun &sun = kg->suns[i];
       if (dot(dir, sun.direction) >= sun.cos_half_angle) {
         L = L + sun.radiance;
       }
     }
     return L;
     ```
     `dir` is `normalize(d)` (`src/painterly/util/math_double3.h:67-70`), the same value the sun test uses, so the
     world is evaluated along the direction the suns are tested against. A scene with a constant world and suns keeps
     its bits: `L` starts from the same `background.radiance` and the additions are the same two lines.
8. `src/painterly/kernel/integrator/path.h:79-85`: the miss branch passes B4's per-call scratch,
   `painterly_background_radiance(kg, ray.d, &sd)`, and keeps `painterly_emission_term(background, p.emission_gain)`
   unchanged: the world is scaled by `emission_gain` like every emitter (SPEC §6, `docs/spec.md:226`). A miss draws no
   random number, so `k_consumed` is unchanged (SPEC §2, `docs/spec.md:51`).
9. `src/test/smallpaint_scene_fixture.h:146-147`: `data.background.cycles_shader = -1;` beside `radiance` and
   `num_suns`, with a comment naming this card. The fixture builds kernel data by hand (`:100-148`), so nothing else
   writes that field, and the zero `KernelPainterlyData data{}` at `:24` would otherwise name shader 0 on a globals
   struct whose `cycles` is null (`test_path.cpp:439-475` would then dereference it).
10. `src/test/test_path.cpp:466`, `:471`: a local `ShaderData sd{};` in the test case (beside `scratch`, `:447`) and
    `&sd` as the third argument. Nothing else in that case moves: `:455-457`, `:467-469` and `:472-474` keep their
    expected values, which is what "scenes without a world shader are unchanged" means at this level (BRIEF.md:195).
11. `src/test/CMakeLists.txt`: `target_sources(painterly_tests PRIVATE test_svm_world.cpp)` in a block of its own after
    `:98`, with a comment naming M6b B5. No `target_link_libraries` line: `:48-50` already links `cycles_util
    cycles_graph painterly_kernel painterly_bvh painterly_integrator painterly_scene painterly_session`, B1's
    `painterly_kernel` brings `cycles_svm` and `painterly_scene` brings `cycles_scene`.
12. `src/test/test_svm_world.cpp`: four doctests, the counts `## Acceptance` uses. It includes `"bitwise.h"`,
    `"cycles/shader_node_registry.h"`, `"painterly/integrator/path_trace.h"`,
    `"painterly/kernel/integrator/path.h"`, `"painterly/kernel/light/background.h"`,
    `"painterly/kernel/svm/background_shader.h"`, `"painterly/scene/device_scene.h"`,
    `"painterly/scene/scene.h"`, `"painterly/util/thread_pool.h"`, `"graph/node_type.h"`, `"scene/scene.h"`,
    `"scene/shader.h"`, `"scene/shader_graph.h"`, `"scene/shader_nodes.h"`, `"util/progress.h"`.
    - The helpers are copied into the file's unnamed namespace with their file:line:
      `make_scene`/`shader_manager`/`create_node_by_name`/`add_surface` (`test_cycles_svm_closures.cpp:47-107`) are
      not needed — B2's `PainterlyScene` API builds the graphs — but the graph calls are those helpers' calls:
      `NodeType::find(ustring(type))` then `graph.create_node(type)` (`:61-66`), `graph->connect(...)` and
      `graph->output()->input("Surface")` (`:100-107`). `painterly_cycles_shader_node_types()` runs once before the
      first `NodeType::find` (`test_cycles_svm_closures.cpp:49`; TQ.4 F11).
    - The render helper and `bit_identical` are copied from `test_path_trace.cpp:79-103` (`render_scene`,
      `bit_identical` over `combined` and `k_consumed`), because they live in that file's unnamed namespace and this
      card may not edit it. The copy takes a `PainterlyGlobalsCPU` and the width and height instead of
      `test_path_trace.cpp:79-92`'s `const Fixture &`, because this card's scenes are `PainterlyScene`s:
      `PainterlyPathTrace trace(kg, buffers, pool)` (`src/painterly/integrator/path_trace.h:28-30`) is all the
      helper needs.
    - **Case 1, `"painterly svm world: a Background node of a dyadic colour renders like set_background"`**
      (BRIEF.md:192). Two scenes, each with `set_camera_smallpaint(8, 8)`, no primitives at all (so every ray misses),
      and `integrator.set_emission_gain(2.0f)` (the default, `src/painterly/scene/integrator.cpp:67`, set explicitly so
      the test states it): A `scene.set_background(make_double3(0.5, 0.25, 0.125))`; B a Background node with Color
      `make_float3(0.5f, 0.25f, 0.125f)` and the node's Strength default 1.0, bound with
      `scene.set_background_shader(scene.add_shader(std::move(graph)))` and `CHECK(world == 0)`. Render both at 4
      passes on one thread and compare `combined` and `k_consumed` with `bit_identical`; then
      `CHECK(buffers_a.combined[0] != 0.0)` so a scene that renders nothing cannot pass.
      - Why it is exact: every colour is dyadic, so its float32 value is exact; `BackgroundNode::compile` with both
        inputs unlinked folds to `color * strength` on the host
        (`BackgroundNode.compile-SVMCompiler.inc`, `kernel/svm/closure.h:1477-1482`) and `rgb_to_spectrum` is the
        identity (`kernel/util/colorspace.h:39-42`), so `closure_emission_background` holds exactly
        `(0.5f, 0.25f, 0.125f)`; the widening at step 6 is exact, so the two worlds hold the same `double3`, and
        `painterly_emission_term` then applies the same `0.0 + (E * 2.0)` per channel to both (SPEC §6,
        `path.h:47-52`), so one pass gives `(1.0, 0.5, 0.25)` and the 4 passes sum to `(4.0, 2.0, 1.0)` through
        `painterly_film_accumulate` (`kernel/film/write.h:13-20`), on both sides in the same order. Those three sums
        are also what the test can check against the constant side without a render, so the `memcmp` is not the only
        assertion.
    - **Case 2, `"painterly svm world: a Gradient world equals the vendored evaluator on the same ShaderData"`**
      (BRIEF.md:193-194). One scene, `set_camera_smallpaint(8, 8)`, two shaders: first a Diffuse BSDF graph through
      `scene.add_node_material(scene.add_shader(...))`, then a Gradient Texture whose Color output feeds a Background
      node's Color, whose Background output is the graph's Surface. Bind the second with `set_background_shader` and
      `CHECK(world == 1)`: the world is shader 1, not 0, so a setup that forgets `sd->shader` cannot pass.
      - The Gradient's Vector input is left unlinked: `GradientTextureNode.inc:17` gives it
        `LINK_TEXTURE_GENERATED`, and `ShaderGraph::default_inputs` connects Texture Coordinate's Generated to it
        (`scene/shader_graph.cpp:878-884`). With `compiler.background` true, Generated compiles to
        `NODE_GEOMETRY`/`NODE_GEOM_P` (`TextureCoordinateNode.compile-SVMCompiler.inc:8-21`), i.e. `sd->P`
        (`kernel/svm/geometry.h:28-30`, `kernel/svm/util.h:238-249`), so the gradient is a function of the direction
        and nothing folds on the host.
      - The 64 directions are the 64 unjittered primary rays of that camera,
        `painterly_camera_generate_ray(kg, row, col, 0, false)` for `row, col` in `[0, 8)`
        (`src/painterly/kernel/camera/camera.h:54-99`; SPEC §7): 8 × 8 = 64, derived, not a table.
      - `kg` is the device-updated scene's globals, `const PainterlyGlobalsCPU globals = ds.globals();` after
        `scene.device_update(ds)` (`src/painterly/scene/device_scene.h:43-45`), which is what compiles both shaders and
        binds them into `globals.cycles`; `const PainterlyGlobals kg = &globals;` is the pointer the kernel functions
        take (`src/painterly/kernel/globals.h:70`), exactly as `test_cycles_svm_closures.cpp:133-134` builds it.
      - For each direction: (a) painterly's value, `painterly_svm_background_radiance(kg, dir, 1, &sd)` with `dir` the
        normalized ray direction, where `sd` is deliberately dirtied first (`num_closure = MAX_CLOSURE`,
        `flag = SD_EMISSION`, `closure_emission_background = make_float3(7.0f)`, `shader = 0`), so a setup that does
        not zero its output fails; (b) the reference, written out in the test from upstream
        `geom/shader_data.h:387-428` on a fresh `ShaderData sd2{}`, then
        `sd2.num_closure_left = int(globals.cycles->data.max_closures)` and
        `svm_eval_nodes<painterly_svm_background_feature_mask, SHADER_TYPE_SURFACE>(kg->cycles, nullptr, &sd2, nullptr,
        PathRayVisibility(0), uint32_t(0))`, then the same `SD_EMISSION`/`closure_emission_background` reading widened
        to `double3`; (c) `CHECK(same_vec(a, b))` (`bitwise.h:48-51`), and the twelve setup fields compared with
        `same_bits`/`same_vec` against the reference's `sd2` (`P`, `N`, `Ng`, `wi`, `ray_length`, `u`, `v`, `object`,
        `prim`, `type`, `shader`, `flag`) — "the same ShaderData" of BRIEF.md:193.
      - Then `CHECK` that the 64 values hold at least two distinct `double3`s, so a world that folded on the host or
        ignored the direction fails instead of passing vacuously. That count is derived, not assumed: the gradient's
        `Fac` is `saturatef(P.x)` (`kernel/svm/gradient.h:14-26`, `:65`; `saturatef` is `clamp(a, 0, 1)`,
        `util/math_base.h:400-418`, `:371-374`), and for this camera
        `cam_point.x = ((2·row − 8) / 8) · tan(fovx)` (`kernel/camera/camera.h:69-77`) is strictly increasing in `row`,
        negative for rows 0-3 and 0 at row 4; the direction is that point normalized (`:87`), and for a fixed `col`
        the map `x ↦ x / √(x² + c)` with `c = cam_point.y² + 1 > 0` is strictly increasing on `x > 0`, so rows 5, 6, 7
        give three distinct positive `P.x`, each below 1 because the length is at least 1. `Fac` is therefore 0 on
        rows 0-4 and three distinct values in (0, 1) on rows 5-7: at least four distinct `double3` radiances,
        whatever the last bit of `tan(fovx)` is.
      - The file's header comment states, as `test_path_trace.cpp:4-11` does, that every comparison is exact and that
        no tolerance appears.
    - **Case 3, `"painterly svm world: a scene without a world shader keeps the constant radiance"`** (BRIEF.md:195).
      - `PainterlyScene scene;` with one plane and `set_background(make_double3(1.0, 2.0, 3.0))`, never
        `set_background_shader`: `device_update(ds)` then `CHECK(ds.data.background.cycles_shader == -1)`. The value
        comes from `PainterlyBackground::cycles_shader`'s default through `device_update` (steps 2-3), not from the
        zeroed `KernelPainterlyData`.
      - `set_background_shader(-1)` after binding a world returns the field to -1: `CHECK` it after a second
        `device_update`.
      - The constant branch neither reads nor writes the scratch: copy the dirtied `sd` (`num_closure = MAX_CLOSURE`,
        `flag = SD_EMISSION`, `closure_emission_background = make_float3(7.0f)`), call
        `painterly_background_radiance(kg, make_double3(0.0, 0.0, -1.0), &sd)` with `kg = &ds.globals()` held in a
        local (`ds.globals()` returns by value, `device_scene.h:43-45`), `CHECK(same_vec(..., make_double3(1.0, 2.0,
        3.0)))` (the value `test_path.cpp:471-474` derives for the same direction) and
        `CHECK(std::memcmp(&sd, &before, sizeof(sd)) == 0)`.
    - **Case 4, `"painterly svm world: an out-of-range world shader is rejected before the commit"`**: a scene that
      has been device-updated once, then `scene.background.cycles_shader = 99;` (the field is public, which is why
      step 5 checks it), then `CHECK_THROWS_AS(scene.device_update(ds), std::invalid_argument)` and
      `CHECK(std::memcmp(&ds.data, &before_data, sizeof(before_data)) == 0)` with the array sizes unchanged — the
      strong guarantee of `device_scene.cpp:94-97`, in the form `test_scene.cpp:918-946` uses.
13. `make format`, then every acceptance command.

## Acceptance
Run every command from the repository root; the queue translates them with BACKLOG.md's table (`make check` → `CHECK`,
`build/dev` → `build/q`, `.venv/bin/<tool>` → `MAIN/.venv/bin/<tool>`, `python -I` → `PYTHONPATH="$PWD/analysis" … -P -s`).
1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and the audit's
   `RESULT: PASS` line.
2. `make audit` prints `RESULT: PASS`: no new exported symbol (the two new kernel functions are `ccl_device`, i.e.
   static on the CPU, `third_party/cycles/util/defines.h:25`) and no new dependency (this card adds no library;
   `cycles_svm` is INTERFACE and header-only, `src/cycles/CMakeLists.txt:128-132`).
3. `build/dev/src/test/painterly_tests --test-case='painterly svm world: *'` exits 0 and prints
   `test cases: 4 | 4 passed | 0 failed` — the four `TEST_CASE`s of step 12, and no others, because the filter is
   `painterly svm world: ` followed by a wildcard and each of the four names begins with exactly that prefix:
   1. `painterly svm world: a Background node of a dyadic colour renders like set_background`
   2. `painterly svm world: a Gradient world equals the vendored evaluator on the same ShaderData`
   3. `painterly svm world: a scene without a world shader keeps the constant radiance`
   4. `painterly svm world: an out-of-range world shader is rejected before the commit`
4. `build/dev/src/test/painterly_tests --test-case='painterly background: *'` exits 0 and prints
   `test cases: 2 | 2 passed | 0 failed`: the two `TEST_CASE`s whose names begin `painterly background: ` and no
   others (`grep -rn '"painterly background: ' src/test/` prints exactly these two lines):
   1. `test_path.cpp:439-475`, "a miss gives background * gain, plus each sun whose disk holds the direction" — the
      miss path through `painterly_trace_pixel`, with the new third argument and every expected value (`:455-457`,
      `:467-469`, `:472-474`) unchanged;
   2. `test_scene.cpp:1098`, "add_sun normalizes the direction and stores cos(angle/2)" — the host `add_sun` and
      `device_update`, unchanged; it builds its own `KernelPainterlyBackground kernel{}` (`:1106`), so its checks do
      not read the new field.
   With acceptance 3's case 3, this is BRIEF.md:195's "scenes without a world shader are unchanged" at the doctest
   level.
5. `build/dev/src/test/painterly_tests --test-case='kernel data survives a byte copy'` exits 0 and prints
   `test cases: 1 | 1 passed | 0 failed`: `KernelPainterlyBackground` and `KernelPainterlyData` are still standard-layout
   and trivially copyable with the new `int` (`test_kernel_headers.cpp:39-42`, `:58-75`).
6. `.venv/bin/python -m pytest -q -m slow tests/core/test_oracle_parity.py tests/core/test_triangle_path.py` prints
   `2 passed, 53 deselected`: the two slow parity tests, unchanged. The counts are the files' own:
   `test_oracle_parity.py` holds three unparametrized tests (`:125`, `:138`, `:162`), the 12 `DESIGN` entries
   (`:74-87`) × the 4 `CORE_CONFIGS` (`:91-96`) = 48 parametrized items, and one slow test (`:366-367`), so 52 items;
   `test_triangle_path.py` holds `:156`, `:183` and the slow `:272-273`, so 3. 52 + 3 = 55 items, of which 2 are
   `slow`, so the `-m slow` run selects 2 and reports `55 - 2 = 53` deselected.
7. `git status --porcelain` lists only the two Create paths and the ten Modify paths above.

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- `background.cycles_shader > 0` instead of `>= 0` in `painterly_background_radiance` → acceptance 3 fails: case 1's
  world is shader 0 and silently falls back to the constant radiance 0.
- drop `sd->shader = cycles_shader` from the setup → acceptance 3 fails on case 2: the world is shader 1 and would run
  shader 0's program.
- pass `d` instead of `dir` to the setup, or set `sd->P = -d` → acceptance 3 fails on case 2 (the gradient reads `P.x`).
- drop `*sd = ShaderData{}` → acceptance 3 fails on case 2, whose scratch is dirtied with `SD_EMISSION` and
  `num_closure`.
- return `background.radiance` instead of the evaluated weight → acceptance 3 fails on case 1 (0 against 1.0).
- leave `background.cycles_shader = cycles_shader;` out of `PainterlyBackground::device_update` → acceptance 3 fails on
  case 2: the zeroed `KernelPainterlyData` names shader 0, which is the Diffuse BSDF graph.
- drop `data.background.cycles_shader = -1;` from the fixture → acceptance 4 fails: the miss path dereferences a null
  `kg->cycles`.
- drop the `>= 0` from the `device_update` check of step 5 → acceptance 1, 3 and 4 fail: `size_t(-1)` is `SIZE_MAX`,
  so every scene that never bound a world throws, which is the defect this line exists to prevent.

Report: the doctest and pytest counts, the audit line, and every mutation you ran with its first failing check.

## Commit
`B5: the world shader on misses`

## Open for Opus
1. **The brief's line range for `shader_setup_from_background` is one line group short.** BRIEF.md:187 cites
   "upstream `geom/shader_data.h:398-426`"; at the vendored tag the function is
   `intern/cycles/kernel/geom/shader_data.h:387-428` — the signature is `:387-392`, `sd->P = ray_D` is `:398`, and the
   body ends at `:427` with the closing brace at `:428`. R2's current equivalent: this card cites `:387-428` and the
   individual lines it writes (`:395`, `:398-406`, `:408-412`, `:414-418`, `:420-427`), and changes no step.
2. **The brief's field list omits two fields the evaluation needs.** BRIEF.md:186-188 lists `P`, `N`, `Ng`, `wi`, the
   three NONE/zero fields, `ray_length` and the six differentials; it does not list `sd->shader` or `sd->flag`, which
   upstream writes at `:402-403`. `sd->shader` is not optional: `svm_eval_nodes` computes its first offset from it
   (`svm_eval_nodes_head.inc:13`), so without it the world would run shader 0's program. This card writes both, as
   upstream does, and case 2's two-shader scene makes a missing `shader` observable. If Opus prefers `flag` to stay B3's
   (B4's Open item 2(b) makes the same choice for a surface hit), the line goes and case 2 still passes, because a
   Background closure reads `sd->flag` only for its own `SD_EMISSION` bit (`closure/emissive.h:16-25`).
3. **`sd->ray_P` stays zero.** Upstream `:395` writes the ray origin there, and the brief's list does not mention it.
   `painterly_background_radiance` sees only the direction (`light/background.h:17`), so this card leaves `ray_P` at
   `ShaderData{}`'s zero. It is read by Texture Coordinate's Window output for an orthographic camera
   (`kernel/svm/tex_coord.h:128-135`), which no v1 world graph uses (the core six batches have no Window output). If
   Opus wants it, the options are (a) leave it zero (this card) and add the ray origin when a node needs it; (b) give
   `painterly_background_radiance` the `PainterlyRay` instead of the direction, which changes the signature at
   `path.h:81` and `test_path.cpp:466`, `:471` and writes `ray_P = make_float3(ray.o)`. This card takes (a).
4. **Who writes the shader manager's `background_shader`.** Cycles sets it from the scene's Background node
   (`scene/svm.cpp:49`), which the shim `Scene` does not have (`src/cycles/shim/scene/scene.h:45-63`). This card derives
   it in `device_update` from `background.cycles_shader` (step 5), so it is one writer and a `clear()` cannot leave a
   stale pointer; the alternative is for `set_background_shader` to write it, which is one line fewer but leaves the
   pointer stale after `clear()` resets the field (`scene.cpp:21-33`). The choice changes no observable behaviour today,
   because `clear()` is the only reset and the next device update follows it.
5. **Suns on top of a world shader.** BRIEF.md:190 says "Suns are added as today", so this card adds a sun's radiance to
   the world graph's radiance in the same loop and the same order (`light/background.h:22-27`). The other reading — a
   world graph replaces the suns, because a Cycles world graph would carry its own sun disk — would delete the loop's
   contribution whenever `cycles_shader >= 0` and would change `tests/core/test_api_contract.py:370-403`'s
   `_sun_scene` semantics if that scene ever gained a world. This card takes the brief's reading.
6. **A world with a BSDF allocates nothing.** `painterly_svm_background_feature_mask` has `EMISSION` and not `BSDF`
   (`collect.h:41-42`), so the radiance of such a world is zero — Cycles' own behaviour: in
   `svm_node_closure_bsdf`'s dispatch (`kernel/svm/closure.h:239-270`), the `IF_KERNEL_NODES_FEATURE(BSDF)` branch
   (`:239-244`) is compiled out when the mask has no `BSDF`, so the emission-only `else` branch runs (`:245-267`), and
   it returns without allocating a closure for every type but Principled (`:246-249`); and
   `surface_shader_background` returns zero without `SD_EMISSION` (`integrator/surface_shader.h:1191-1197`). No check of
   this card distinguishes the two masks (a Principled BSDF on a world would allocate its emission through
   `principled_bsdf_emission`, `:264`, and that is outside v1). The card takes the brief's mask and names the untested
   consequence here rather than adding a test for a graph the sync cannot build yet.
7. **`set_background_shader` accepts -1.** BRIEF.md:184 gives -1 the meaning "constant radiance", so the setter treats
   it as a valid argument that unbinds, rather than as an error. The alternative — `set_background` being the only way
   back to a constant world — would make the pyi binding B8 adds (`set_background_shader(shader: int) -> None`) unable
   to express what the kernel field means. This card accepts -1 and rejects only values below -1 or outside the shader
   list.
