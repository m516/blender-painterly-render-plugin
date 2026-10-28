# B4 — The SVM in `painterly_trace_pixel` (drafted from BRIEF.md section 2, "B4")
Milestone: M6b · Depends on: B1, B2, B3 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B4" (lines 161-180) and its section 1
decisions 3 and 7 (lines 30-37 and 67-74), per that brief's section 4 (lines 303-324). Code facts
are `docs/handoff/drafts/M6b/FACTS.md` §3, re-read at this clone's HEAD in every file cited below.

## Goal
A hit on a node material is shaded by Cycles' own SVM inside `painterly_trace_pixel`, and its lobes
and emission are sampled exactly as SPEC §6 samples a constant material's:
- `painterly_trace_pixel` (`src/painterly/kernel/integrator/path.h:64-65`) resolves the material of
  each hit through one new kernel function, `painterly_hit_material` (BRIEF.md:30-37 and :67-74):
  a constant material gives today's `kg->lobes + mat.lobe_offset` and `mat.num_lobes`, and a node
  material (`mat.cycles_shader >= 0`) gives
  `painterly_svm_shader_setup` → `svm_eval_nodes<painterly_svm_surface_feature_mask,
  SHADER_TYPE_SURFACE>(kg->cycles, nullptr, &sd, nullptr, PathRayVisibility(0), 0)` →
  `painterly_svm_collect`, i.e. the collector's lobe list, its count and its emission
  (BRIEF.md:163-166).
- The emission is the collector's emission times `emission_gain`, through the same
  `painterly_emission_term` a constant material uses (`path.h:47-52`), and a node material counts as
  an emitter for `continue_after_emitter` exactly as a constant material does (`path.h:54-58`,
  `:107-111`; BRIEF.md:166-167).
- `painterly_select_lobe` (`src/painterly/kernel/closure/lobe.h:33-39`) takes the lobe array and
  its count instead of the material. Its arithmetic, its RNG draw and its weight division do not
  change, so a one-lobe node material is still returned unchanged with `p = 1` and no draw
  (`lobe.h:29-32`, `:37-39`; BRIEF.md:67-70).
- One `ShaderData` (6480 B, `docs/handoff/drafts/M6b/FACTS.md:209`,
  `src/test/cycles_kernel_layout_probe.h:93`) and one `PainterlySvmMaterial`
  (`src/painterly/kernel/svm/collect.h:52-60`) live per `painterly_trace_pixel` call and are reused
  for every bounce of its iterative loop (`path.h:77-156`; BRIEF.md:168).
- The SVM draws no random number (`lcg_state = 0`, `collect.h:11-23`), so only a chosen diffuse lobe
  advances K, as today (`path.h:116-121`; SPEC §2, §6). K is therefore unchanged by this card for
  every constant material, and for a node material K depends only on which lobe kinds it collects.
- A constant material is rendered exactly as today: its bits, K and images do not change. T3.16's
  bit-identical parity and T3.17's triangle test are the check (BRIEF.md:36-37, :169-170).

Nothing else moves: the bounces, the backward evaluation, the miss path (B5's) and the analytic
normals are untouched.

## Read first
- `CLAUDE.md` rules 1, 2 and 3; `AGENTS.md` "Expected values are evidence"; SPEC §2 (K, chains),
  §6 (lobes, selection, emitters, emission) — `docs/spec.md:51`, `:64`, `:101-103`, `:190-207`.
- `docs/handoff/drafts/M6b/BRIEF.md` lines 30-37 (decision 3), 67-74 (decision 7) and 161-180 (this
  card's mandate); `docs/handoff/drafts/M6b/FACTS.md` §3.4, §3.5, §3.8, §3.9, §3.13.
- `src/painterly/kernel/integrator/path.h` in full: the signature `:64-65`, the forward loop
  `:77-156` with `ray.o = P` at `:95`, the material block `:97-113`, the bounce switch `:115-152`,
  the backward evaluation `:158-176`, the result `:178`.
- `src/painterly/kernel/closure/lobe.h:29-79` (the signature `:33-36`, the one-lobe shortcut
  `:37-39`, the total `:43-46`, the RNG draw `:48-50`, the uniform branch `:54-59`, the weighted
  branch `:60-75`, the weight division `:77`).
- `src/painterly/kernel/svm/collect.h` in full: the evaluation contract `:11-23`, the two feature
  masks `:34-48`, `PainterlySvmMaterial` `:52-60`, `painterly_svm_collect` `:165-211` and its
  zero-closure fallback `:205-210`.
- `src/painterly/kernel/types.h`: `KernelPainterlyLobe` `:90-94`, `KernelPainterlyMaterial`
  `:101-106` (the `cycles_shader` field, B2's rename of `svm_offset`), `KernelPainterlyIntegrator`
  `:126-142`. `MAX_CLOSURE` is Cycles': `third_party/cycles/kernel/types.h:829-833`, i.e.
  `__MAX_CLOSURE__`, which `cycles_kernel` defines (`src/cycles/CMakeLists.txt:103`) and B1 moves to
  `cycles_util` (`docs/audits/TQ.4.md:45`).
- `src/cycles/shim/kernel/device/cpu/globals.h:31-45` (`kernel_array`), `:49-57`
  (`KernelGlobalsCPU`, including `data`), `:59` (`using KernelGlobals`), `:24-26` (the `#error` that
  B1's link rule satisfies).
- `third_party/cycles/kernel/types.h`: `ShaderData` `:1030-1096` (`type` `:1030`, `shader` `:1033`,
  `flag` `:1035`, `num_closure`/`num_closure_left` `:1040-1041`, `prim` `:1044`, `u`/`v`
  `:1048-1049`, `object` `:1051`, `lcg_state` `:1087`, `closure_emission_background` `:1091`,
  `closure[MAX_CLOSURE]` `:1095`), the `ShaderDataFlag` bits `:897-978` (`SD_BACKFACING` `:901`,
  `SD_EMISSION` `:903`), the `ShaderFlag` bits and `SHADER_MASK` `:479-494`, `KernelShader`
  `:1665-1671`, `KernelData::max_closures` `:1370`.
- `third_party/cycles/fragments/kernel/svm/svm_h/span/svm_eval_nodes_head.inc:1-18`: the signature
  and `offset = (sd->shader & SHADER_MASK) * (1 + sizeof(SVMNodeShaderJump) / sizeof(uint))` at
  `:13` — the jump-table word `sd->shader` selects. `src/painterly/scene/svm/shader_manager.h:181`
  (`jump_node_size`) and `:202` (`base = shader->id * jump_node_size`) are the writer's side.
- `src/test/test_cycles_svm_closures.cpp`: the helpers `make_scene` `:47-53`, `shader_manager`
  `:55-58`, `create_node_by_name` `:61-66`, `set_enum` `:70-75`, `add_surface` `:100-107`, the
  evaluation `evaluate()` `:121-138`, `describe()` `:153-185`; and the six per-lobe-kind doctests
  whose expected values this card reuses: Diffuse `:359-384`, Glossy `:417-453`, Glass and
  Refraction `:455-498`, Transparent `:500-514`, Emission and Background `:516-549`, Mix and Add
  Shader `:551-617`.
- `src/test/cycles_svm_test_support.h:313-330` (`painterly_svm_test_shader_data`, and why
  `lcg_state = 0` draws nothing); `src/test/bitwise.h:42-50` (`same_bits`, scalars and `double3`s).
- `src/test/test_path.cpp:502-550` (the lobe-selection doctest and its three call sites `:525`,
  `:533`, `:540`) and `src/test/test_triangle_diagnostics.cpp:359-362` (the third caller).
- `src/test/test_path_trace.cpp:79-103` (render a scene on a pool, `bit_identical` over `combined`
  and `k_consumed`) and `src/test/test_session.cpp:186-228` (`render_directly`,
  `check_buffers_equal`) — the pattern this card's image comparison follows, copied rather than
  changed (`test_session.cpp` is not this card's file).
- `src/blender/addon/sync/reference.py:46-57` (`REFERENCE_SCENE`, the SPEC §9 table this card's test
  geometry copies) and `:130-140` (the add order, which is what makes the object ids the list
  positions).
- `third_party/cycles/kernel/closure/alloc.h:55-93` (`closure_sample_weight`, `bsdf_alloc`) and
  `:95-118` (`bsdf_alloc_maybe_emission`), with
  `third_party/cycles/kernel/closure/bsdf_transparent.h:16-26` (a weight below
  `CLOSURE_WEIGHT_CUTOFF` allocates no closure), `third_party/cycles/kernel/closure/emissive.h:16-38`
  (`emission_setup`), `third_party/cycles/kernel/svm/closure.h:1499-1515` (`svm_node_mix_closure`),
  `:779-838` (GGX glass) and `:737-777` (refraction).
- `third_party/cycles/kernel/svm/checker.h:14-44`, `third_party/cycles/kernel/svm/tex_coord.h:101-112`
  (Object coordinates), `third_party/cycles/kernel/geom/object.h:170-176`
  (`object_inverse_position_transform_if_object`), `third_party/cycles/kernel/svm/util.h:238-249`
  (`shading_position` returns `sd->P`) — the per-hit material of the per-hit test.
- `src/cycles/CMakeLists.txt:101-103` (`cycles_kernel`), `:128-132` (`cycles_svm`, the generated
  `svm_eval_nodes.h` and its include directory) and `src/painterly/kernel/CMakeLists.txt:7-8` (B1
  adds `cycles_svm` there); `src/test/CMakeLists.txt:31-51` and `:94-98` (where a test source is
  registered).
- The two parity tests this card must keep green unchanged: `tests/core/test_oracle_parity.py`
  (`DESIGN` `:74-87`, `CORE_CONFIGS` `:91-96`, the fast test `:320-363`, the slow test `:366-396`)
  and `tests/core/test_triangle_path.py` (`:156`, `:183`, the slow test `:272-...`).

## Create
- `src/painterly/kernel/svm/hit_material.h`
- `src/test/test_svm_path.cpp`

## Modify
- `src/painterly/kernel/closure/lobe.h`: `painterly_select_lobe` takes `(const KernelPainterlyLobe
  *lobes, int num_lobes)` instead of `(const KernelPainterlyMaterial &m)`; the body and the comment
  follow (step 2).
- `src/painterly/kernel/integrator/path.h`: include `svm/hit_material.h`; one `ShaderData` and one
  `PainterlySvmMaterial` local per call; the material block resolves the hit's lobes and emission
  through `painterly_hit_material`; the lobe selection call and the emitter test follow (step 3).
- `src/test/test_path.cpp`: the three `painterly_select_lobe` call sites `:525`, `:533`, `:540` pass
  the lobe array and its count; the fixtures `:513-515` keep their values (step 6). The two
  `glass_material.svm_offset = -1` / `emitter_material.svm_offset = -1` lines at `:194` and `:200`
  are in this file, so if B2's rename left them behind this card writes `cycles_shader = -1` there
  as part of the same edit — a mechanical rename inside a file it already changes, not a decision
  (BRIEF.md:34 lists this file's readers among the rename's sites).
- `src/test/test_triangle_diagnostics.cpp`: the call site `:361-362` passes the hit material's lobe
  array and count instead of the material (step 7).
- `src/test/CMakeLists.txt`: `test_svm_path.cpp` in `painterly_tests` (step 5).

## Do not touch
- `src/painterly/kernel/types.h` (CONTRACT, `:4`): the `svm_offset` → `cycles_shader` rename is B2's
  (BRIEF.md:30-34, and B2's scope writes the field by its new name). This card only reads the field.
  `src/painterly/kernel/globals.h` (CONTRACT) is B1's, `src/blender/_painterly.pyi` (CONTRACT) is
  B6's.
- `third_party/cycles/**` (vendored; `tools/vendor_sync.py` only) and `src/cycles/shim/**`. This card
  vendors nothing: every evaluator it calls is already vendored (BRIEF.md:274-276,
  `src/cycles/svm_nodes.toml`).
- `src/painterly/kernel/svm/collect.h` (T6.7's; its contract is what this card keeps, not what it
  changes), `src/painterly/scene/svm/shader_manager.h` (B2 moves it into `painterly_scene`),
  `src/painterly/scene/device_scene.cpp` (B2), `src/painterly/kernel/svm/shader_data.h` (B3's file).
- `src/test/smallpaint_scene_fixture.h` and `src/test/test_scene.cpp`: they read the field B2
  renames (`smallpaint_scene_fixture.h:167`, `test_scene.cpp:470`), and B2's rename updates them
  (step 1's precondition). `src/test/test_path.cpp:194` and `:200` read it too, but that file is
  this card's, so its two lines are this card's to rename (step 6).
- `src/test/test_session.cpp`, `src/test/test_path_trace.cpp`: the pattern this card's test copies.
  Neither file changes, so T3.12's and T3.14's tests keep their exact expected values.
- `tests/core/test_oracle_parity.py`, `tests/core/test_triangle_path.py`: they must pass unchanged,
  so not one line of either may move.
- `src/cycles/CMakeLists.txt`, `src/painterly/kernel/CMakeLists.txt`, `src/painterly/integrator/`,
  `Makefile`, `pyproject.toml`: B4 adds no library and no flag (step 5 says why the link line
  already carries what the new headers need).

## Interface
No CONTRACT change. This card reads two CONTRACT declarations as B1 and B2 leave them, and adds one
kernel function of its own.

CONTRACT (B1 writes this before dispatch, BRIEF.md:104-105): `PainterlyGlobalsCPU::cycles`, the
`const KernelGlobalsCPU *` the SVM is evaluated with.

CONTRACT (B2 writes this before dispatch, BRIEF.md:30-34): `KernelPainterlyMaterial::cycles_shader`,
`int`, the Cycles shader id `sd->shader`, or -1 for a constant material. It is not an offset: the
program starts at word `cycles_shader * (1 + sizeof(SVMNodeShaderJump) / sizeof(uint))` of
`svm_nodes` (`svm_eval_nodes_head.inc:13`; `shader_manager.h:181`, `:202`).

B3 provides, and this card calls:

    painterly_svm_shader_setup(PainterlyGlobals kg, const PainterlyRay &ray,
                               const PainterlyIntersection &isect, int cycles_shader,
                               ShaderData *sd)

`src/painterly/kernel/svm/shader_data.h` (BRIEF.md:139-140). It writes every `ShaderData` field the
vendored node and closure code reads, as Cycles' `shader_setup_from_ray` would (BRIEF.md:58-64).

The SVM call, exactly as the brief gives it (BRIEF.md:163-165):

    svm_eval_nodes<painterly_svm_surface_feature_mask, SHADER_TYPE_SURFACE>(
        kg->cycles, nullptr, &sd, nullptr, PathRayVisibility(0), 0)

then `painterly_svm_collect(&sd, &material)` (`collect.h:165-166`; BRIEF.md:165). In
`painterly_hit_material` the brief's `sd` and `material` are the caller's `*sd` and `*svm`, so the
two calls read `sd` and `svm` (step 4); `PathRayVisibility(0)` is `uint32_t(0)`
(`third_party/cycles/kernel/types.h:183`) and the brief's `0` for `path_flag` is the same type
(`svm_eval_nodes_head.inc:3-8`).

This card's own new names, which no other card depends on:

    /* src/painterly/kernel/closure/lobe.h */
    ccl_device_inline KernelPainterlyLobe painterly_select_lobe(PainterlyGlobals kg,
                                                               const KernelPainterlyLobe *lobes,
                                                               int num_lobes,
                                                               int row, int col, int pass,
                                                               int depth)

    /* src/painterly/kernel/svm/hit_material.h */
    struct PainterlyHitMaterial {
      const KernelPainterlyLobe *lobes;
      int num_lobes;   /* >= 1 */
      double3 emission; /* Before emission_gain (SPEC §6). */
    };
    ccl_device_inline PainterlyHitMaterial painterly_hit_material(
        PainterlyGlobals kg, const PainterlyRay &ray, const PainterlyIntersection &isect,
        const KernelPainterlyMaterial &material, ccl_private ShaderData *sd,
        ccl_private PainterlySvmMaterial *svm)

`painterly_hit_material` is the only entry point the per-hit test can observe the path's own
resolution through; `## Open for Opus` item 1 names the alternative.

Two cross-card agreements this card depends on, both B3's to keep (BRIEF.md:58-64 and :139-157):
- the ray: `painterly_svm_shader_setup` is called with the ray as `painterly_trace_pixel` holds it
  after `path.h:95` — `ray.o` is the hit point `P` and `ray.d` the incoming direction — and reads `P`
  from `ray.o` (`shading_position()` returns `sd->P`,
  `third_party/cycles/kernel/svm/util.h:238-249`). If B3's draft computes
  `P = ray.o + ray.d * isect.t` instead, the two cards disagree and B3 must be the one to change,
  because `path.h:95` also sets the origin the bounces start from;
- `sd->flag`: B3 sets it from the shader's `KernelShader`, as upstream `shader_setup_from_ray` does
  (`sd->flag = kernel_data_fetch(shaders, (sd->shader & SHADER_MASK)).flags`,
  `intern/cycles/kernel/geom/shader_data.h:113`, a file FACTS.md:340-343 lists as not vendored),
  which is what `collect.h:17-20` requires.
  B4 does not write it: one writer. No test of this card can distinguish the value — the six
  lobe-kind cases, the zero-closure case and the checker case all shade surfaces whose closures read
  `SD_BACKFACING` only, and B3's setup leaves it clear (`collect.h:18-20`) — so the assignment is
  B3's acceptance, not B4's.

`## Open for Opus` item 2 names both.

## Steps
1. Preconditions. Each must hold; otherwise stop, commit nothing and report what you saw.
   - B1 has landed. This prints `1`:
     ```
     grep -c 'KernelGlobalsCPU \*cycles' src/painterly/kernel/globals.h
     ```
   - B2 has landed, including the CONTRACT rename (BRIEF.md:30-34). This prints `1`, and this prints
     `0`:
     ```
     grep -c 'int cycles_shader' src/painterly/kernel/types.h
     grep -c 'svm_offset' src/painterly/kernel/types.h
     ```
     If the second prints a non-zero count, the rename has not arrived: stop and report. The field is
     Opus's (CLAUDE.md rule 1). This prints the only two remaining readers, `test_path.cpp:194` and
     `:200`, which are this card's file and which step 6 renames (B2 owns the others, BRIEF.md:34; a
     line in `device_scene.cpp` or `smallpaint_scene_fixture.h` here means B2 is incomplete and the
     tree does not compile, which is B2's to fix, not this card's):
     ```
     grep -rn 'svm_offset' src/ | grep -v 'kernel/types.h'
     ```
   - B2's scene API exists (BRIEF.md:115-116). Each of these prints a count of at least `1`:
     ```
     grep -c 'add_shader' src/painterly/scene/scene.h
     grep -c 'add_node_material' src/painterly/scene/scene.h
     ```
     If either prints `0`, B2 has not landed: stop and report.
   - B3 has landed. This prints `1`:
     ```
     grep -c 'painterly_svm_shader_setup' src/painterly/kernel/svm/shader_data.h
     ```
   - Every caller of `painterly_select_lobe` is one this card edits. This prints `6` lines: the
     declaration in `lobe.h:33`, the call in `path.h:113`, the three in `test_path.cpp:525`, `:533`,
     `:540`, and the one in `test_triangle_diagnostics.cpp:361`:
     ```
     grep -rn 'painterly_select_lobe' src/painterly src/test
     ```
     `test_triangle_diagnostics.cpp` is a caller the brief does not list (BRIEF.md:68-69 names
     `path.h:113` and `test_path.cpp:525-540`); it is edited here because the signature changes.
   - The zero-closure fallback the zero-closure test rests on is at `collect.h:205-210`. This
     prints `1`:
     ```
     grep -c 'material->num_lobes == 0' src/painterly/kernel/svm/collect.h
     ```
2. `src/painterly/kernel/closure/lobe.h`: replace the signature `:33-36` with the one under
   `## Interface` and delete the line that reads the material, `:36`
   (`const KernelPainterlyLobe *lobes = kg->lobes + m.lobe_offset;`). `num_lobes` replaces
   `m.num_lobes` at `:37`, `:44`, `:56`, `:58`, `:64`, `:66`, `:74`. Nothing else in the function
   changes: the total `:43-46`, the draw `:48-50`, the uniform branch `:54-59`, the weighted branch
   `:60-75` and the division `:77` are today's arithmetic, so a constant material's chosen lobe is
   bit-identical (BRIEF.md:69-70). Update the comment `:29-32` to say whose lobes it takes and that
   `kg` is read only for `kg->data->integrator.seed` (`:48`).
3. `src/painterly/kernel/integrator/path.h`:
   - `#include "painterly/kernel/svm/hit_material.h"` after `:19` (`closure/lobe.h`).
   - In `painterly_trace_pixel`, before the loop (`:73`), two locals that the whole call reuses:
     ```cpp
     /* B4: one ShaderData and one collector result per call, reused for every bounce (BRIEF.md:168).
      * The SVM writes the closures into sd, and the collector reads that same object in place: a
      * microfacet closure's Fresnel payload is a pointer into sd->closure (collect.h:21-23).
      * Neither is initialised here: painterly_hit_material overwrites both before anything reads
      * them, and a constant material never reads them at all, so a constant scene pays no
      * per-pixel zeroing of 6480 + sizeof(PainterlySvmMaterial) bytes. */
     ShaderData sd;
     PainterlySvmMaterial svm;
     ```
     The frame grows by `sizeof(ShaderData)` (6480 B, `src/test/cycles_kernel_layout_probe.h:93`)
     plus `sizeof(PainterlySvmMaterial)` (`collect.h:52-60`: `MAX_CLOSURE` lobes, a count, an
     emission and a drop count), which is the "one ShaderData per `painterly_trace_pixel` call"
     BRIEF.md:168 asks for. A per-*thread* scratch instead would be smaller but would break SPEC
     §3's independence: `painterly_trace_pixel` takes no worker index (`path.h:64-65`).
     If the build's `-Wall -Wextra` (`cmake/painterly_warnings.cmake:29`) reports
     `-Wmaybe-uninitialized` here, write `ShaderData sd{};` and `PainterlySvmMaterial svm{};`, drop
     the comment's "Neither is initialised here" sentence, and say so in the answer; nothing else
     changes, and a constant scene then pays one zeroing per pixel per pass.
   - Replace the material block `:97-113` with the resolution, keeping the emission arithmetic and
     the emitter test exactly where they are:
     ```cpp
     const int material_index = triangle ? painterly_triangle_material(kg, isect) : prim->material;
     const KernelPainterlyMaterial &mat = kg->materials[material_index];
     /* B4: the lobes and the emission of this hit, constant or from the SVM (BRIEF.md:163-166).
      * `ray` is the ray after :95: ray.o is the hit point P, ray.d the incoming direction. */
     const PainterlyHitMaterial hit = painterly_hit_material(kg, ray, isect, mat, &sd, &svm);

     /* Emission. A spot ghost sphere scales it by the cone falloff at its normal (SPEC §5). The
      * attenuation is applied to whichever emission the hit has; a light is a ghost sphere with a
      * constant material (BRIEF.md:297-298), so both readings coincide on every scene the sync
      * builds. */
     double3 E = hit.emission;
     if (prim != nullptr && prim->spot.enabled) {
       E = E * painterly_spot_attenuation(prim->spot, N);
     }
     const double3 e_term = painterly_emission_term(E, p.emission_gain);

     if (!p.continue_after_emitter && painterly_is_emitter(hit.emission)) {
       /* The emitter absorbs the path (SPEC §6, knob continue_after_emitter). */
       scratch[n++] = PainterlyPathVertex{VERTEX_END, e_term, 0.0, black};
       break;
     }

     const KernelPainterlyLobe lobe = painterly_select_lobe(
         kg, hit.lobes, hit.num_lobes, row, col, pass, depth);
     ```
     - The emitter test reads `hit.emission`, the emission before the spot attenuation, which is
       exactly today's `mat.emission` (`:107`) on the constant path. It must not read `E`: a spot
       ghost's attenuation can scale an emitter's emission to exactly 0, and then `E`'s test would
       end the path where today it continues, which would change a constant scene's bits.
     - The bounces below `:115-152` are unchanged, and so is the normal each lobe gets: `N` is
       already the normal flipped to the ray when `two_sided` (`:90-94`) and the glass lobe already
       asks for the unflipped one (`:128-130`), which is decision 7's rule (BRIEF.md:71-73). The
       SVM's `sd->N` is the authored, unflipped normal (`collect.h:11-23`) and is not used for a
       bounce.
   - `painterly_trace_pixel` stays `ccl_device` and non-recursive; the two locals are the only
     addition to its frame.
4. `src/painterly/kernel/svm/hit_material.h`:
   ```cpp
   /* SPDX-FileCopyrightText: 2026 The Painterly Authors
    * SPDX-License-Identifier: GPL-3.0-or-later */

   #pragma once

   /* The material of one hit, as painterly_trace_pixel samples it (SPEC §6; card M6b B4). A constant
    * material gives its flattened lobes; a node material gives the closure collector's lobes and
    * emission, from one SVM evaluation at the hit (painterly/kernel/svm/collect.h, "Contract"). */

   #include "svm_eval_nodes.h"

   #include "painterly/kernel/globals.h"
   #include "painterly/kernel/svm/collect.h"
   #include "painterly/kernel/svm/shader_data.h"
   #include "painterly/kernel/types.h"

   CCL_NAMESPACE_BEGIN

   /* The lobes of one hit, and its emission before emission_gain (SPEC §6). lobes points into
    * kg->lobes for a constant material and into `svm` for a node material, so both must outlive the
    * use. */
   struct PainterlyHitMaterial {
     const KernelPainterlyLobe *lobes;
     int num_lobes;    /* >= 1 */
     double3 emission; /* Before emission_gain (SPEC §6). */
   };

   /* B4 (BRIEF.md:161-168). For a constant material (material.cycles_shader < 0) this is
    * kg->lobes + material.lobe_offset, material.num_lobes and material.emission, which is exactly
    * what painterly_trace_pixel read before this card, so its output cannot change. For a node
    * material it evaluates the shader at the hit and collects:
    *   painterly_svm_shader_setup -> svm_eval_nodes<surface mask> -> painterly_svm_collect.
    * `sd` and `svm` are the caller's scratch, one per painterly_trace_pixel call and reused for
    * every bounce. They are overwritten here on every node-material hit and are not read before
    * that, so no bounce can see an earlier hit's closures. The evaluation follows collect.h's
    * contract: surface mask, SHADER_TYPE_SURFACE, path_visibility 0, path_flag 0, num_closure 0,
    * num_closure_left kernel_data.max_closures, lcg_state 0. The SVM draws no random number, so K
    * is untouched (SPEC §2, §6; BRIEF.md:65-66). */
   ccl_device_inline PainterlyHitMaterial painterly_hit_material(
       PainterlyGlobals kg,
       const PainterlyRay &ray,
       const PainterlyIntersection &isect,
       const KernelPainterlyMaterial &material,
       ccl_private ShaderData *sd,
       ccl_private PainterlySvmMaterial *svm)
   {
     if (material.cycles_shader < 0) {
       return PainterlyHitMaterial{
           kg->lobes + material.lobe_offset, material.num_lobes, material.emission};
     }

     /* Zero first, so nothing of the previous hit survives: ShaderData is 6480 B and holds the
      * closure array (third_party/cycles/kernel/types.h:1095). */
     *sd = ShaderData{};
     painterly_svm_shader_setup(kg, ray, isect, material.cycles_shader, sd);
     /* collect.h:17-18: the closure budget is kernel_data.max_closures, which B1 sets to
      * MAX_CLOSURE and B2's device update writes (BRIEF.md:123-126). Written after the setup, so
      * it is the value this evaluation runs with whatever the setup left there; `max_closures` is
      * `uint` and the field is `int`, and MAX_CLOSURE is a small count, so the cast is exact. */
     sd->num_closure_left = int(kg->cycles->data.max_closures);
     svm_eval_nodes<painterly_svm_surface_feature_mask, SHADER_TYPE_SURFACE>(
         kg->cycles, nullptr, sd, nullptr, PathRayVisibility(0), uint32_t(0));
     painterly_svm_collect(sd, svm);
     return PainterlyHitMaterial{svm->lobes, svm->num_lobes, svm->emission};
   }

   CCL_NAMESPACE_END
   ```
   - `svm_eval_nodes.h` is the generated header `cycles_svm` puts on the include path
     (`src/cycles/CMakeLists.txt:116-132`), reached through `painterly_kernel` → `cycles_svm` (B1,
     BRIEF.md:23-29). It is listed first, as `cycles_svm_test_support.h:75` lists it, because it
     brings in its own `includes` list (`src/cycles/svm_nodes.toml:8-...`, which starts with
     `kernel/globals.h` and `kernel/types.h`), so the kernel headers it needs are complete before
     the painterly ones are read.
   - `PainterlySvmMaterial` is `collect.h:52-60`: `lobes[MAX_CLOSURE]`, `num_lobes`, `emission`,
     `num_dropped`. `num_dropped` is not read here; the collector's zero-closure fallback
     (`collect.h:205-210`) already gives one black diffuse lobe, so `num_lobes >= 1` always holds
     and `painterly_select_lobe` keeps its `num_lobes == 1` shortcut.
   - No value is invented: the emission is the collector's `double3` (two exact float-to-double
     conversions per channel, `collect.h:170-174`) and the weights are `painterly_svm_lobe_weight`'s
     exact double products (`collect.h:145-152`).
5. `src/test/CMakeLists.txt`: `target_sources(painterly_tests PRIVATE test_svm_path.cpp)` in a block
   of its own after `:98`, with a comment naming M6b B4. No `target_link_libraries` line: `:49-50`
   already links `cycles_util cycles_graph painterly_kernel painterly_bvh painterly_integrator
   painterly_scene painterly_session`, and B1's `painterly_kernel` brings `cycles_svm`;
   `painterly_scene` brings `cycles_scene` (B1). No other CMake file changes: `path.h` is a header
   of the INTERFACE target, so `painterly_integrator` and `_painterly` get the new includes from
   `painterly_kernel` with no new library on any link line.
6. `src/test/test_path.cpp`, the three call sites: `:525`, `:533` and `:540` become
   ```cpp
   painterly_select_lobe(&kg, lobes.data() + single.lobe_offset, single.num_lobes, row, col, 0, 0)
   ```
   and the same for `zero_and_mirror` and `equal_pair`. The fixtures `:513-515` keep their values
   (`KernelPainterlyMaterial` still carries `lobe_offset`, `num_lobes`, `emission` and the shader
   field), so the test's expected values do not move. Lines `:194` and `:200` carry the field B2
   renames: write `cycles_shader = -1` if they still read `svm_offset = -1`, and nothing else in
   the file's expectations changes.
7. `src/test/test_triangle_diagnostics.cpp:361-362`:
   ```cpp
   const KernelPainterlyMaterial &hit_material = kg->materials[material];
   const KernelPainterlyLobe chosen = painterly_select_lobe(kg,
                                                            kg->lobes + hit_material.lobe_offset,
                                                            hit_material.num_lobes,
                                                            row,
                                                            col,
                                                            pass,
                                                            depth);
   ```
   The local is named `hit_material` and not `material`, because `material` is the index above it.
8. The reference geometry, one helper in `test_svm_path.cpp`'s unnamed namespace (not a header: only
   this file needs it). It is SPEC §9 built through `PainterlyScene`, with the geometry, the object
   order and the ghost policy of `src/blender/addon/sync/reference.py:46-57` and `:125-140`:
   ```cpp
   /* The SPEC §9 reference scene, through PainterlyScene (card M6b B4). The geometry, the object
    * order and the ghost policy are src/blender/addon/sync/reference.py:46-57 and :125-140; the
    * materials are the caller's, one per row of that table, so a test puts its own material on one
    * object and a constant one on the rest. Object ids are the list positions. */
   void build_reference_geometry(PainterlyScene &scene,
                                 const int size,
                                 const std::vector<int> &materials);
   ```
   - `materials` holds one material index per row of `REFERENCE_SCENE` (`reference.py:46-57`), in
     that order, so the caller decides which object carries the tested material.
   - The spheres are ghosts (`SPHERE_GHOST`, `src/painterly/kernel/types.h:58-59`, which is
     `reference.py:125-128`'s `"all"`), the six planes are planes, in table order; the camera is
     `scene.set_camera_smallpaint(size, size)` (`reference.py:140-141`), and the integrator sockets
     are the reference's (`reference.py:63-83`, `:142-143`): `max_depth` 20, `diffuse_gain`
     `float(0.1)`, `emission_gain` 2, `ray_epsilon` `float(1e-4)`, the smallpaint spiral frame; the
     sockets not named keep their defaults (`continue_after_emitter` true, `jitter` the reference
     value). Object 2, the left diffuse sphere, is the one the caller's material goes on
     (`reference.py:49`).
   - The helper and the rest of the file's support live in the unnamed namespace that
     `src/test/test_path_trace.cpp:37-105` uses, so nothing it defines has external linkage.
9. `src/test/test_svm_path.cpp`: eight doctests, the counts `## Acceptance` uses. It includes
   `"bitwise.h"`, `"painterly/kernel/integrator/path.h"`,
   `"painterly/kernel/svm/hit_material.h"`, `"painterly/integrator/path_trace.h"`,
   `"painterly/scene/device_scene.h"`, `"painterly/scene/scene.h"`, `"painterly/util/thread_pool.h"`,
   `"cycles/shader_node_registry.h"`, `"graph/node_type.h"`, `"scene/scene.h"`,
   `"scene/shader.h"`, `"scene/shader_graph.h"`, `"scene/shader_nodes.h"`,
   `"util/progress.h"`.
   - `#include <vector>` joins the standard block for the material indices.
   - The helpers are T6.7's, copied into the file's unnamed namespace with their file:line:
     `make_scene` `:47-53`,
     `shader_manager` `:55-58`, `create_node_by_name` `:61-66`, `set_enum` `:70-75`,
     `add_surface` `:100-107`, and `describe()` `:153-185` (which prints every double with `%.17g`,
     so two descriptions are equal iff the bits are).
   - **The six lobe-kind cases (BRIEF.md's acceptance item (2), :171-174).** One helper builds two scenes with
     the same geometry — `build_reference_geometry` at 100 px (`WIDTH = HEIGHT = 100`,
     `PASSES = 4`) with every object on a constant material except object 2, the left diffuse sphere
     (`reference.py:49`), which carries the tested material — and renders both through
     `PainterlyPathTrace` on one thread, exactly as `test_path_trace.cpp:79-92` does. Scene A's
     object 2 is `scene.add_material({constant lobe}, emission)`; scene B's is
     `scene.add_node_material(scene.add_shader(std::move(graph)))` — B2's C++ signatures
     (BRIEF.md:115-116), with the graph built by T6.7's helpers (`make_unique<ShaderGraph>()`,
     `create_node_by_name`, `graph->connect`, then `graph->output()->input("Surface")` as
     `add_surface` does at `test_cycles_svm_closures.cpp:100-107`). The comparison is
     `memcmp` over `combined` and over `k_consumed` — a helper copied from
     `test_path_trace.cpp:94-103` (`bit_identical`), because `bitwise.h:42-50` compares scalars and
     `double3`s, not vectors — and the test also checks the render is not trivially black
     (`combined` holds a non-zero value), so a scene that renders nothing cannot pass. The six cases, each with its derivation:

     | case | node material | constant equivalent | why the lobe is exactly this |
     |---|---|---|---|
     | diffuse | Diffuse BSDF, Color (0.5, 0.25, 0.125) | one diffuse lobe, weight (0.5, 0.25, 0.125) | weight = Color × mix weight 1 (T6.7 doctest `test_cycles_svm_closures.cpp:371-374`) |
     | mirror | Glossy BSDF, distribution `ggx`, Color (0.5, 0.25, 0.125) | one mirror lobe, weight (0.5, 0.25, 0.125) | GGX has no Fresnel payload, so the mirror lobe is Color (`test_cycles_svm_closures.cpp:436-442`) |
     | glass | Glass BSDF, distribution `ggx`, Color (0.5, 0.25, 1.0), IOR 1.45 | one glass lobe, weight (0.5, 0.25, 1.0), ior `double(1.45f)` | weight = mix weight 1 × the transmission tint, which is Color; the ior is `double(bsdf->ior)` and the closure's ior is the float socket widened (`test_cycles_svm_closures.cpp:475-483`, `collect.h:191-195`) |
     | transparent | Transparent BSDF, Color (0.5, 0.5, 0.25) | one transparent lobe, weight (0.5, 0.5, 0.25) | `test_cycles_svm_closures.cpp:509-513` |
     | emission | Emission, Color (0.25, 0.5, 1.0), Strength 4 | one diffuse lobe, weight 0, emission (1.0, 2.0, 4.0) | emission = Color × Strength and no closure gives a lobe (`test_cycles_svm_closures.cpp:536-542`) |
     | mix | Mix Shader, Fac 0.5, of Diffuse (0.5, 0.25, 0.125) and Glossy `ggx` (0.25, 0.5, 0.125) | two lobes in that order: diffuse (0.25, 0.125, 0.0625), mirror (0.125, 0.25, 0.0625) | `svm_node_mix_closure` gives Closure1 `1 - 0.5` and Closure2 `0.5` (`third_party/cycles/kernel/svm/closure.h:1499-1515`), and the collector keeps closure order (`test_cycles_svm_closures.cpp:601-608`) |

     - Every colour is dyadic, so its float32 value is exact and `double(float)` is the literal:
       0.5, 0.25, 0.125 and 0.0625 are powers of two. The products of the mix case
       (0.5 × 0.5, 0.5 × 0.25, 0.5 × 0.125) are dyadic too, so both sides hold the same bits and no
       tolerance appears.
     - The constant material's lobe order is the collector's closure order, because
       `painterly_select_lobe`'s cumulative sums run in lobe order (`lobe.h:43-46`, `:64-75`): a
       reordered pair would choose a different lobe at the same draw and the images would differ.
     - The test names the six cases as six test cases, one per lobe kind, all prefixed
       `painterly svm path: ` (the filter of acceptance command 3).
     - One case sets a knob, on both scenes so the two renders differ only in the material: the
       emission case sets `scene.integrator.set_continue_after_emitter(false)`
       (`src/painterly/scene/integrator.h:66`), because the default `true` would make the path
       continue on both sides and the emitter rule untested. No case touches `two_sided` (default
       true, `src/painterly/scene/integrator.cpp:73`): the reference geometry is analytic spheres
       and planes, and only a triangle hit reads it (`path.h:90-94`).
     - The emission case also checks the premise its constant side rests on: the material
       `add_node_material` returned has a zero constant emission, so the constant scene's emission
       really is the graph's and not a leftover — `CHECK(same_bits(mat.emission.x, 0.0))` and the
       same for `y` and `z` (`bitwise.h:42`); `## Open for Opus` item 8.
   - **The zero-closure case (BRIEF.md's acceptance item (3), :175).** A Transparent BSDF whose Color is
     (0, 0, 0): `bsdf_transparent_setup` allocates nothing below `CLOSURE_WEIGHT_CUTOFF`
     (`third_party/cycles/kernel/closure/bsdf_transparent.h:16-26`), so `sd->num_closure` is 0 and
     `painterly_svm_collect` gives one black diffuse lobe (`collect.h:205-210`). Its constant
     equivalent is `add_material({diffuse lobe, weight (0, 0, 0)}, black)`, and the test compares the
     two renders bit for bit, K included: a black diffuse lobe still selects LOBE_DIFFUSE and still
     draws from K (`path.h:116-121`), so the same K is the assertion that the fallback lobe really is
     the lobe the path samples. The test first checks the premise, by running the
     setup-eval-collect sequence that the per-hit case below spells out (its item 2) on the primary
     hit of the middle pixel:
     `CHECK(svm2.num_lobes == 1)`, `CHECK(svm2.lobes[0].kind == LOBE_DIFFUSE)` and
     `CHECK(svm2.lobes[0].weight.x == 0.0)`, `CHECK(svm2.lobes[0].weight.y == 0.0)` and
     `CHECK(svm2.lobes[0].weight.z == 0.0)`.
   - **The per-hit case (BRIEF.md's acceptance item (4), :176-179).** A Diffuse BSDF whose Color comes from a
     Checker Texture of Texture Coordinate's Object output, built in C++ from registered nodes
     (`create_node_by_name`: `"texture_coordinate"`, `"checker_texture"`, `"diffuse_bsdf"` — the
     names `NodeType::add` registers, `TextureCoordinateNode.inc:3`, `CheckerTextureNode.inc:3`,
     `DiffuseBsdfNode.inc:3`), with Color1 (0.5, 0.25, 0.125), Color2 (0.25, 0.125, 0.0625) and
     Scale 2, on object 2 of the same 100 px scene. `painterly_cycles_shader_node_types()` runs once
     before the first `NodeType::find` (`test_cycles_svm_closures.cpp:47-53`; TQ.4 F11).
     - The graph: `tex_coord->output("Object")` → `checker->input("Vector")`,
       `checker->output("Color")` → `diffuse->input("Color")`, `diffuse->output("BSDF")` →
       `graph->output()->input("Surface")`. `checker->input("Vector")` has no default link once it is
       connected, so nothing folds on the host (T6.5:163-168).
     - The cells: `svm_checker` floors `co * scale` and takes the parity of the three indices
       (`third_party/cycles/kernel/svm/checker.h:14-26`), so with Scale 2 the cells are 0.5 wide in
       world space. Object coordinates equal world coordinates for a painterly hit (BRIEF.md:61-63),
       because there is no Cycles object (`sd->object == OBJECT_NONE`,
       `third_party/cycles/kernel/geom/object.h:170-176`), so the checker varies over the sphere's
       1.2-unit diameter.
     - The pixels: walk rows and columns in row-major order, intersect the pass-0 jittered primary
       ray (`painterly_camera_generate_ray(kg, row, col, 0, true)`) and collect every pixel whose
       hit's material index is the node material's. Let `n` be that count and
       `stride = n / 16`; the 16 are the entries `0, stride, 2 * stride, …, 15 * stride`, so they
       spread over the sphere instead of clustering at its top edge. `REQUIRE(n >= 16)` and
       `REQUIRE(stride >= 1)` first. For each of the 16:
     1. the path's own resolution: `painterly_hit_material(kg, ray, isect, mat, &sd, &svm)` with the
        ray as `path.h:95` leaves it (`ray.o = P`), and the `PainterlySvmMaterial` it filled;
     2. the independent reference: `sd2 = ShaderData{}`, `painterly_svm_shader_setup(kg, ray, isect,
        mat.cycles_shader, &sd2)`, `sd2.num_closure_left = int(kg->cycles->data.max_closures)`,
        `svm_eval_nodes<painterly_svm_surface_feature_mask, SHADER_TYPE_SURFACE>(kg->cycles, nullptr,
        &sd2, nullptr, PathRayVisibility(0), uint32_t(0))`, `painterly_svm_collect(&sd2, &svm2)`,
        and that collector's `PainterlySvmMaterial`;
     3. `CHECK(describe(path_svm) == describe(ref_svm))`, where each side is a `PainterlySvmMaterial`
        holding that call's lobes, count, emission and `num_dropped`.
     The test then `CHECK`s that the 16 descriptions hold at least two distinct values, so a checker
     that folded on the host (`docs/handoff/drafts/M6a/T6.5-svm-compiler.md:163-168`) would fail
     instead of passing vacuously. What this proves and what it cannot is stated in the file's header comment:
     it catches a wrong shader id, a wrong mask, a stale `num_closure`/`num_closure_left`, a missing
     `ShaderData` reset and a path that samples the constant lobes; it cannot catch an error inside
     `painterly_svm_shader_setup` itself, which is B3's.
   - The file's header comment states, as `test_path_trace.cpp:4-12` does, that every comparison is
     exact (`memcmp`, so -0.0 and +0.0 differ) and that no tolerance appears.
   - `describe()` comes in two forms: the lobe list `:153-176`, and the `PainterlySvmMaterial`
     overload `:178-185`, which copies the lobes into a vector and passes `emission` and
     `num_dropped` on. The per-hit case calls the second on both sides, so it compares `num_dropped`
     too; the copy is of a plain struct, and the Fresnel payload the collector read lives in `sd`,
     not in the lobe list, so nothing is lost.
10. `make format`, then every acceptance command.

## Acceptance
Run every command from the repository root; the queue translates them with BACKLOG.md's table
(`make check` → `CHECK`, `build/dev` → `build/q`, `.venv/bin/<tool>` → `MAIN/.venv/bin/<tool>`,
`python -I` → `PYTHONPATH="$PWD/analysis" … -P -s`).
1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and
   the audit's `RESULT: PASS` line.
2. `make audit` prints `RESULT: PASS`: no new exported symbol (the SVM is `ccl_device`, i.e. static on
   the CPU, `src/test/cycles_svm_test_support.h:19-26`) and no new dependency (B4 adds no library;
   `cycles_svm` is INTERFACE and header-only, `src/cycles/CMakeLists.txt:128-132`).
3. `build/dev/src/test/painterly_tests --test-case='painterly svm path: *'` exits 0 and prints
   `test cases: 8 | 8 passed | 0 failed` — the six lobe-kind cases, the zero-closure case and the
   per-hit case of step 9. Report its duration: the brief fixes 100 px and 4 passes (BRIEF.md:174),
   so the count of paths is 100 × 100 × 4 per scene and 2 scenes per lobe-kind case.
4. `build/dev/src/test/painterly_tests --test-case='painterly lobe selection*'` exits 0 and prints
   `test cases: 1 | 1 passed | 0 failed`: `test_path.cpp:502-550` with the new signature, its
   expected weights unchanged.
5. `build/dev/src/test/painterly_tests --test-case='painterly scene: the quad scene*'` exits 0 and
   prints `test cases: 1 | 1 passed | 0 failed`: `test_triangle_diagnostics.cpp:498` with its
   call site updated, its per-bounce comparison unchanged.
6. `build/dev/src/test/painterly_tests --test-case='cycles svm closures*'` exits 0 and prints
   `test cases: 12 | 12 passed | 0 failed`: T6.7's twelve cases, whose expected lobe lists this
   card's table reuses, still pass unchanged.
7. `build/dev/src/test/painterly_tests --test-case='painterly lane scheduler*'` exits 0 and prints
   `test cases: 6 | 6 passed | 0 failed` — T3.12's determinism tests. The six are the `TEST_CASE`s
   whose name begins with `painterly lane scheduler`: `test_path_trace.cpp:107`, `:205`, `:224`,
   `:244`, `:266` and `:310` (`:137` is `painterly thread pool` and `:341` `painterly scene
   intersect`, so the filter leaves both out). The number is the count of the cases the filter
   names, and the run must print it; if it prints another count, the card's count is wrong and that
   is a finding, not a tolerance.
8. `.venv/bin/python -m pytest -q -m slow tests/core/test_oracle_parity.py
   tests/core/test_triangle_path.py` prints `2 passed, 53 deselected`: the two slow tests,
   unchanged (the brief's acceptance item (1), BRIEF.md:169-170). The counts are the files' own:
   `test_oracle_parity.py` holds three unparametrized tests (`:125`, `:138`, `:162`), the 12
   `DESIGN` entries (`:74-87`) × the 4 `CORE_CONFIGS` (`:91-96`) = 48 parametrized items, and one
   slow test (`:366-367`), so 52 items; `test_triangle_path.py` holds `:156`, `:183` and the slow
   `:272-273`, so 3. 52 + 3 = 55 items, of which 2 are `slow`.
9. `git status --porcelain` lists only the two Create paths and the five Modify paths above.

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- in `painterly_hit_material`, return `material.emission` for a node material instead of
  `svm->emission` → acceptance command 3 fails on the emission case;
- drop `*sd = ShaderData{}` → acceptance command 3 fails on the mix case (the previous hit's
  closures stay in `sd->closure` and `num_closure` keeps growing), and its per-hit case fails;
- pass `material.cycles_shader + 1` to the setup → acceptance command 3 fails on every case whose
  scene holds a second shader, and the per-hit case fails on the jump word;
- use `painterly_svm_background_feature_mask` instead of the surface mask → acceptance command 3
  fails on the diffuse case (`NODE_CLOSURE_BSDF` allocates no BSDF under the background mask,
  `docs/handoff/drafts/M6a/T6.7-svm-closures.md:173-174`);
- make the path sample `kg->lobes + mat.lobe_offset` even when `cycles_shader >= 0` → acceptance
  command 3 fails on all six lobe-kind cases, and its per-hit case fails its "two descriptions
  differ" check because every hit then gives the same lobe list;
- in `lobe.h`, divide the chosen weight by `1.0` instead of `p` (`lobe.h:77`) → acceptance command
  4 fails: the two equal lobes of `test_path.cpp:539-545` get weight 1 instead of 2;
- test `painterly_is_emitter(mat.emission)` instead of `painterly_is_emitter(hit.emission)` →
  acceptance command 3 fails on the emission case, provided the material `add_node_material`
  returns has a zero constant emission: then the node scene's path continues while the constant
  scene's ends (that case sets `continue_after_emitter` false). The case checks that premise first
  — `CHECK(same_bits(mat.emission.x, 0.0))` and the same for `y` and `z`, `bitwise.h:42` — so the
  mutation cannot pass by accident; if B2 gives the material a non-zero constant emission, that
  check fails and the case reports the value. `## Open for Opus` item 8.
- test `painterly_is_emitter(E)` (the spot-attenuated emission) → no check of this card sees it: no
  case here puts a node material on a spot ghost, and no reference-scene spot attenuation reaches
  exactly 0. The code reads `hit.emission`, as today's `:107` reads `mat.emission`, and step 3's
  comment says why. A test for it needs a spot ghost, which is `test_path.cpp:376`'s subject and
  outside this card.

Report: the doctest counts of acceptance commands 3-7, the pytest counts of command 8, the audit
line, the duration of command 3, and every mutation you ran with its first failing check.

## Commit
`B4: the SVM in painterly_trace_pixel`

## Open for Opus
1. **How the per-hit test observes the path.** The brief asks that "the lobe list the path samples equals
   the collector's output for the vendored SVM run directly on a ShaderData that
   `painterly_svm_shader_setup` gives for that hit" (BRIEF.md:176-179). `painterly_trace_pixel` has
   no hook, so this card factors the path's per-hit resolution into `painterly_hit_material`
   (`src/painterly/kernel/svm/hit_material.h`) and the test calls that function and compares it with
   its own independent setup-eval-collect sequence. Options: (a) keep it (this card); (b) a
   test-only hook like `painterly_svm_trace()` (`src/test/cycles_svm_test_support.h:42-72`), which
   cannot work here because that header redefines `kernel_data_fetch` for the whole translation unit
   and the path is production code; (c) compare two renders only, which loses the per-hit assertion
   the brief asks for. This card takes (a).
2. **Two fields of `painterly_svm_shader_setup` that B4 relies on.** (a) `P`: the setup is called at
   `path.h:95-113`, where `ray.o` is already the hit point and `ray.d` the incoming direction, and
   this card assumes it reads `P` from `ray.o`. If B3's draft computes `P = ray.o + ray.d *
   isect.t`, the setup would get `P + d t`; one of the two cards must name the convention, and B4
   cannot fix it alone, because `path.h:95` also sets the origin the bounces start from. (b) `flag`:
   this card does not write it, because B3's setup is what Cycles' `shader_setup_from_ray` writes
   (upstream `geom/shader_data.h:113`, FACTS.md:340-343) and no test here observes it. If Opus prefers B4 to write it — the collector's
   contract names it (`collect.h:17-20`) and B4 owns the evaluation — the line goes right after the
   setup call in `painterly_hit_material` and is idempotent with B3's own assignment.
3. **The `cycles_shader` rename is B2's.** BRIEF.md:30-34 describes the rename of
   `KernelPainterlyMaterial::svm_offset`, and B2's scope (BRIEF.md:118-119) writes the field by its
   new name, so this card treats the rename as landed by B2 and only reads it (step 1's
   precondition). If Opus prefers the rename here, B4 must add one step for the CONTRACT file and for
   `device_scene.cpp:120`, `src/test/smallpaint_scene_fixture.h:167`, `src/test/test_path.cpp:194`,
   `:200` and `src/test/test_scene.cpp:470`.
4. **Spot attenuation on a node material.** Step 3 applies `painterly_spot_attenuation` to whichever
   emission the hit has. A spot ghost sphere is a light, and lights keep constant emission in v1
   (BRIEF.md:297-298), so no scene the sync builds has a node material on a spot ghost. If Opus
   prefers the attenuation to stay inside the constant branch, it becomes
   `if (mat.cycles_shader < 0 && prim != nullptr && prim->spot.enabled)` and no test changes.
5. **The brief's caller list is one short.** BRIEF.md:68-69 names `path.h:113` and
   `test_path.cpp:525-540` as the callers of `painterly_select_lobe`;
   `src/test/test_triangle_diagnostics.cpp:361` is a third. Step 1's `grep` lists every caller and
   step 7 edits the third, which is the current equivalent of the brief's instruction.
6. **The six lobe-kind cases are heavy.** BRIEF.md:174 fixes the reference scene's geometry at
   100 px and 4 passes, so each case renders 100 × 100 × 4 paths twice, at `max_depth` 20. Six such
   cases plus the zero-closure and per-hit ones may exceed the ~10 s that CLAUDE.md rule 6 uses as
   the mark for `@pytest.mark.slow`; doctests have no such marker, and `painterly_tests` has no
   slow/fast split (`src/test/CMakeLists.txt:65` registers one ctest test). This card keeps the
   brief's numbers and reports the duration (acceptance command 3). If Opus wants the suite
   shorter, the options are a smaller side for the six image comparisons — which would need a
   brief amendment, since the brief fixes 100 px — or a second ctest test that excludes them.
7. **A second copy of the reference scene in the tests.** `src/test/test_session.cpp:123-164` builds
   the SPEC §9 reference through `PainterlyScene` (materials, geometry, camera and three knobs), and
   step 8's `build_reference_geometry` builds the same geometry with the caller's materials, because
   B4 needs a scene whose material it controls and may not edit T3.14's test file. The two copies
   differ in what they own: `test_session.cpp`'s also builds the ten materials and sets three
   sockets, this one takes the materials. A later card could fold both into one header and delete
   one copy; this card leaves `test_session.cpp` untouched on purpose.
8. **What `add_node_material` puts in the material's constant fields.** BRIEF.md:116-119 says the
   device update "sets each node material's `cycles_shader` to its shader id" and that "constant
   materials keep `cycles_shader = -1`", and says nothing about the lobes and the emission of the
   material a node material returns. This card reads them as the constant path's only: a node
   material's lobes and emission come from the SVM per hit (BRIEF.md:35), so its `lobe_offset`,
   `num_lobes` and `emission` are never read by `painterly_trace_pixel`. Two of this card's checks
   observe that reading: acceptance command 3's emission case (its premise, see the mutation list)
   and the mix case. If Opus would rather B2 fill them with the graph's folded value, this card
   still passes, but the emission case's premise check reports the value instead of asserting zero,
   and the case then needs a second difference (the `num_lobes` of the collected material) to fail
   on. Please state which it is, in B2's card.
