# Plan: "Painterly", a native, Cycles-shaped Blender render engine built from smallpaint's beautiful bug

## Context

- **Repo:** `m516/blender-painterly-render-plugin` is empty (branch `claude/clever-johnson-gnso1s`, no commits).
- **Input:** `Smallpaint.zip`, Károly Zsolnai-Fehér's teaching path tracer from the TU Wien Rendering course. The GUI port is by Michael Oppitz (2017–18). The code is MIT-licensed per the author's site (2020-02-26).
- **The bug:** the `smallpaint_painterly` variant renders a painterly look. The author's page describes the cause as "an incorrect usage of the Halton-series with correlating dimensions… spread throughout the screen with an equally wrong sampling function".
- **Goal:** an accelerated Blender extension that preserves the look, makes it controllable by artists, and renders arbitrary Blender scenes. Cycles is the code template.
- **Who does the work:** Haiku subagents, each working from a precise task card. Tests gate every task, and Opus reviews every milestone.

### Owner decisions (2026-10-08)
| Topic | Decision |
|---|---|
| Fidelity | Two modes. An exact **reference** mode is ground truth. A deterministic, parallel **artist** mode has knobs whose defaults match the reference. |
| Materials | Blender **shader node-graph evaluation**, Cycles-style. |
| Platforms | CPU-only for v1 (linux-x64, windows-x64, macos-arm64). GPU later. |
| Backend | **Native C++ like Cycles.** No JAX/Numba/GLSL compute backends. |
| Ghost spheres | **Point and spot lights.** Mesh ghosting is a research experiment. |
| Scope | Final render (F12 and animation) in v1. The interactive viewport comes later. |
| Review | Tests per task. **Opus** reviews each milestone, plus a code-quality audit every 12th task. |

## What makes the look

These findings come from research-phase ports run in memory. The port matches the shipped reference image (block-mean correlation 0.997). Experiment 1 re-confirms everything here with a compiled oracle.

1. **Spiral sampling.**
   - Both Halton dimensions are base 2 and advance in lockstep, so u1 = u2 = vdC(K).
   - `hemisphere(u,u)` is therefore a 1-D spiral around a fixed axis (smallpaint +z, which points toward the camera).
   - The bounce direction is `d = N + spiral(u)`. It is not rotated into N's frame and not normalized; `cost = d·N` lies in [0,2].
2. **Ghost spheres: the dominant light source.**
   - The sphere test assumes |d| = 1, i.e. it solves the quadratic with a = 1.
   - With |d| = L it hits a ghost sphere centred at `o + L²(c−o)` with radius `L·sqrt((L²−1)|o−c|² + r²)`. The light's cone grows to `acos(1/L)`, which is 60° at L = 2.
   - Normalizing d drops the back wall from 193 to 13 grey levels.
   - Triangles and planes are unaffected by |d|.
3. **Scan-line chaining.**
   - Each path's counter K starts where the previous pixel's path in the same row ended. Only diffuse hits advance K.
   - This produces a deterministic, converged texture: structure std ≈ 5 grey levels, red power spectrum, region-dependent orientation.
   - Pattern correlation with the reference, by chaining variant:
     - Row chain: 0.63.
     - Hashed 16-pixel lanes: 0.55.
     - Per-path random start: 0.11, which **breaks the look**.
   - Thread count is irrelevant. The shipped Linux binary had no OpenMP, so one stream ran over the whole image and all passes.
4. **Path model.**
   - Fixed depth 20, no Russian roulette, no next-event estimation (NEE) or MIS.
   - The light is a black diffuse object, so paths keep bouncing after hitting it and keep consuming K.
   - Emission ×2; diffuse weight = `cost·cl·0.1`; glass = Snell only, with total internal reflection (TIR) ending the path.
5. **Display.** Output is `min(int(sum)/s, 255)` raw bytes with no gamma. The texture appears only once converged (about 250+ spp).
6. **Reference images.**
   - The only numeric golden is `test_images/smallpaint_painterly.ppm` (400², GUI scene).
   - The website showcase cannot be reproduced from the published code; it becomes a qualitative preset.
   - `bvh.ppm` and `pssmlt.ppm` are copies of `fixed.ppm`.

## Architecture: a hybrid, Cycles-shaped native core (no Cycles fork)

The core is new C++20 that mirrors Cycles' layout and names: `util/ kernel/ bvh/ graph/ scene/ integrator/ session/ blender/ app/`, the `ccl_device` dialect, an SVM shader VM and NodeType reflection.

- **Copied verbatim from Cycles** (pinned to Blender v5.2.2 `intern/cycles`; all checked candidates are byte-identical to standalone v5.2.0):
  - `util/` math, hash, colour and transform headers.
  - The typed `kernel/svm/*` node evaluators: 90 node structs plus 14 trailing data structs. Of the 108 dispatch cases in
    `svm_eval_nodes`, 43 take only `(stack, node)`, 49 read `ShaderData`, 8 read `KernelGlobals`, and 8 are special. This
    corrects the plan's earlier "104 structs, stack only": M6 research, 2026-10-09. The generated switch therefore copies
    upstream `SVM_CASE` bodies verbatim, and painterly uses Cycles' own `kernel/types.h` (`ShaderData`, `KernelData`) for
    shading.
  - `graph/` reflection.
  - The node `compile()` bodies.
- **Ported from Blender's sync code:** Blender's node mapping (`intern/cycles/blender/shader.cpp`, Apache-2.0) becomes Python data tables.

**Why we do not fork Cycles:**
- **Hook sites.** About 15 places would each need a patch to defeat behaviour that silently changes K:
  - NEE/MIS;
  - Russian roulette;
  - Ng rejection;
  - the lamp-hit path continuing as a transparent bounce;
  - zero-pdf termination;
  - 2-D tiles cutting lanes;
  - adaptive sampling;
  - per-pixel stateless RNG.
  Correctness would then depend on invariants spread across files, which is a poor fit for Haiku.
- **Coexistence with Blender's own Cycles.**
  - Blender's macOS executable exports 5,720 `ccl::` symbols, so a fork would need a full rename.
  - It would also need OIIO, OCIO and TBB, which Blender already has in-process.
- **Upstream churn:** about 650 upstream commits per year to rebase against.
- **No GPU shortcut.** The lane-serial sampler conflicts with Cycles' GPU wavefront scheduler, so GPU support needs a new scheduler either way.
- **Escape hatch.** The Python sync emits Cycles node names and socket names, so a later fork would reuse the whole Python side.

**Isolation from Blender's own libraries:**
- Embree 4.4.1 is built **static**, with `EMBREE_API_NAMESPACE=painterly_embree` and INTERNAL tasking (no TBB).
- There is no OIIO, OCIO or TBB.
- Everything compiles with `CCL_NAMESPACE_BEGIN`→`namespace painterly {`, `-fvisibility=hidden` and a version script; only `PyInit__painterly` is exported.
- Builds target manylinux_2_28 (its devtoolset GCC) with a static libstdc++/libgcc, and MSVC with the static CRT (`/MT`), so the module never binds to Blender's C++ runtime.

**Distribution.**
- extensions.blender.org ToS §3.6 (Aug 2026) requires pure-Python source, so the extension is **self-hosted**: one cp312-abi3 wheel per platform, built with `--split-platforms`.
- Releases go out as GitHub Release assets, with an `index.json` remote repository published on GitHub Pages.
- Licence: GPL-3.0-or-later overall. Notices are kept for Apache-2.0 (Cycles, Embree), MIT (smallpaint) and BSD-3 (nanobind).

**Naming.**

| Item | Name |
|---|---|
| Extension id | `painterly` |
| Engine `bl_idname` | `PAINTERLY` |
| Native module | `_painterly` (like `_cycles`) |
| Wheel | `painterly-core` |
| Properties | `scene.painterly`, `light.painterly`, `material.painterly`, `world.painterly` (like `scene.cycles`) |

### Repository layout
```
CMakeLists.txt  pyproject.toml (scikit-build-core + nanobind; uv dependency-groups dev/analysis/blender)  Makefile  uv.lock
src/
  painterly/                 # OUR ENGINE, Cycles-shaped layers; no path here shadows a vendored header
    util/                    #   types_double3.h math_double3.h thread_pool.{h,cpp} (deterministic pool)
    kernel/                  #   header-only, ccl_device: types.h globals.h camera/ geom/ closure/ light/ sample/ integrator/ film/ bvh/
                             #   M6: svm/ (generated switch from verbatim SVM_CASE fragments) closure/painterly collector
    bvh/embree.{h,cpp}       #   static, namespaced Embree
    scene/                   #   PainterlyScene, PainterlyIntegrator (reflected knobs), camera, background, material, mesh, object, device_scene
    integrator/path_trace.{h,cpp}   # lane scheduler
    session/{session,buffers}.{h,cpp}
  cycles/                    # builds vendored Cycles into cycles_util, cycles_graph, (M6) cycles_svm …
    shim/                    #   headers/sources that shadow upstream Cycles paths (util/log.h, util/param.h, …; M6: scene/scene.h,
                             #   kernel/device/cpu/globals.h, …). A shimmed path is never also vendored.
  blender/python.cpp         # nanobind module _painterly
  blender/addon/             # THE EXTENSION (pure Python): blender_manifest.toml __init__.py engine.py properties.py ui.py presets.py operators.py version_update.py
                             #   sync/{depsgraph,camera,geometry,light,world,image}.py  sync/shader/{flatten,node_table,export}.py
  app/smallpaint_oracle.cpp  # reference CLI (like Cycles' src/app)
  test/                      # doctest unit tests (like Cycles' src/test)
third_party/cycles/ (vendored verbatim; VENDORED.toml path+sha256; patches/)   third_party/smallpaint/ (original sources, MIT)
analysis/painterly_analysis/ (JAX metric suite + oracle runner)   tests/ (pytest: core/, blender/, data/reference/, scenes/)
tools/ (vendor_sync.py, symbol_audit.py, gen_node_registry.py, make_reference_scene.py, fetch_blender.py)
experiments/  docs/{spec.md, architecture.md, tasks/, artist-guide.md}  .github/workflows/
```
- **Naming (2026-10-09).** Vendored Cycles shares the `painterly` namespace and the include path with our code. So every
  type under `src/painterly/` is prefixed `Painterly` or `KernelPainterly`, kernel functions are prefixed `painterly_`, and
  shims live only in `src/cycles/shim/`. Rationale and rules: `docs/architecture.md`, "Source layout and naming".
  A compile check of the old contracts against Cycles' `kernel/types.h` gave redefinition errors for `KernelData`,
  `KernelCamera`, `KernelBackground`, `KernelObject`, `Ray`, `CameraType` and `CAMERA_*`. The renamed contracts compile
  alongside it.

**Rules.**
- Vendored files are never hand-edited; changes go through `patches/` applied by `vendor_sync.py`.
- The node registry and kernel switch are **generated** from the directory contents, so node ports only *add* files and parallel tasks never conflict.
- Every painterly constant is a reflected socket on `PainterlyIntegrator` (`NODE_DEFINE`). Its default is the reference value, and the Blender properties are **generated from that reflection**, giving a single source of truth.

## Painterly specification (normative; becomes `docs/spec.md`; task cards cite it as §n)

**§1 Frame.**
- smallpaint (x, y, z) = (image down, image right, toward camera), which is Blender camera space (−Y, +X, +Z).
- The spiral frame is a knob (camera, world or object; default camera) with a phase/axis rotation.

**§2 Counter.**
- `u = bitrev23(K mod 2^23)·2^-23`, with K incremented before use. The 2^23 is the original generator's own period.
- u1 = u2 = u. Only diffuse events advance K.
- All other random choices (closure selection, jitter) use a stateless hash `rng(pixel, pass, depth, dim)`, so they never perturb K.

**§3 Chains.** The `chain` enum sets how far K is carried:
- `image`: one stream, continuous across pixels and passes, single-threaded. This is the exact Linux-build semantics and is the reference mode.
- `row`: per row, per pass.
- `lane`: L pixels per row, per pass (artist mode, default L = 16).

`K0 = hash(seed, lane, pass) mod 2^22`. Lanes are aligned in global coordinates, so output is bit-identical across thread counts.

**§4 Diffuse.**
- `d = N + spiral(u)`. The weight is `(d·N)·albedo·diffuse_gain`.
- The normalization blend `d·|d|^-α` (α default 0) is a continuous knob, not a toggle.

**§5 Ghost spheres.**
- Point and spot lights become spheres of radius `shadow_soft_size`, intersected with the a = 1 quadratic.
- t is parametric along the unnormalized d, and the normal is taken from the true centre.
- Ghosts get no BVH (the ghost radius is unbounded) and stay visible even at r = 0.
- Spot lights multiply their emission by Blender's cone falloff.
- The core also offers analytic painterly spheres for oracle-parity scenes; whether to expose them in Blender is decided by the mesh-ghosting experiment.

**§6 Path.**
- Fixed `max_depth` (20), no Russian roulette, no NEE, no MIS. An emitter hit adds `E·emission_gain`.
- Reference mode keeps bouncing at zero throughput, so K consumption stays exact.
- Glass in reference mode uses the unnormalized incoming d in Snell's law; TIR terminates the path.
- Area lights are emissive quads (no ghosting). Sun is an angular disk seen by escaping rays. The world shader is evaluated on a miss.

**§7 Output.** An enum knob:
- *Display-referred*: write `srgb_to_linear(min(L/255,1))`. With the Standard view transform and dither 0 this reproduces the original bytes up to rounding. A preset sets those values; the scene is never changed silently.
- *Scene-linear*: write `L/255·exposure`.

**§8 Knobs** (all defaults = reference): chain, lane length, seed, per-frame seed, spiral frame/phase/axis, u2 decorrelation blend, K0 phase lock (K0 ≡ 0 mod 2^q), α, diffuse gain, emission gain, `max_depth`, jitter amplitude, output mode, exposure, emission scale.

## Experiments programme

- **Location:** `experiments/NNN-YYYY-MM-DD-slug/`. Each `README.md` has five sections (Background, Hypothesis, Method, Results, Conclusion) and sits alongside its scripts, `results.json` and small PNGs. `experiments/README.md` is the index.
- **Numbering:** numbers and dates are assigned in the order experiments actually run.
- **Division of labour:** Haiku executes and drafts each experiment; Opus reviews the conclusion. The analysis code uses JAX in the uv venv.

| Label | Hypothesis | When |
|---|---|---|
| X-oracle | Research claims reproduce with the compiled oracle: reference match, `image` vs per-thread restart, transpose/frame mapping. | M1 |
| X-ablation | Each ingredient is necessary: spiral, chaining, ghosts, unnormalized weight, zero-throughput continuation. | M1 |
| X-lanes | Fidelity as a function of L (1…row) and K0 policy. Picks the artist default. | M1 |
| X-resolution | The texture is pixel-locked (400/800/1600). Decides lane and jitter units. | M1 |
| X-ghost-lights | How much of the look survives with only lights ghosted (spheres as meshes)? Sets the Blender parity target. | M1 |
| X-coexist | The isolated native module plus Blender's Cycles coexist in one process on all 3 OSes. | M2 |
| X-throughput | CPU rays/s on the reference scene and a 100k-triangle mesh; time for 1080p × 256 spp. | M3 |
| X-svm | Vendored `graph/` + SVM with the shim works; hours per node port (gate G2). | M6 |
| X-colour | Blender's bundled PyOpenColorIO sees Blender's config; Image.pixels semantics. | M6 |
| X-mesh-ghost | Candidate generalizations of ghosting to triangles (bounding-sphere proxy, L²-homothety about the ray origin, angular dilation by `acos(1/L)`, unnormalized SDF stepping), scored against analytic ghosts on sphere meshes. | M9 |
| X-open-scenes | Look outside the closed box: misses/world, mesh-only scenes, large scenes. | M9 |
| X-animation | Spiral frame and seed policy under camera motion (boiling vs stability). | M7 |

## Acceptance metrics

The JAX metric suite lives in `analysis/`. It computes on 3-pixel-eroded primary-hit region masks (the oracle and the core both emit object-id and K-consumption passes):
- region mean RGB;
- **structure std** = `sqrt(cov(hpA,hpB))`, using 9×9-box high-pass luminance from two independent half renders;
- pattern correlation vs the reference;
- 25-pixel block RMSE;
- clip fraction;
- lag-1 autocorrelation and spectral slope.

**Tests use no hand-set tolerances.**
- A candidate passes when every metric of (candidate vs reference) lies within the empirical range of (oracle seed *i* vs reference) over n seeds of the same configuration.
- Negative controls (per-path random start, normalized d, independent u2) must fall outside that range.
- Core-vs-oracle parity is exact: identical per-pixel K-consumption maps, with images equal up to float-vs-double error measured on the oracle itself.

## Milestones and Haiku task DAG

**Card format.** Each task is a card in `docs/tasks/Mx/Tx.y-slug.md`, written by Opus at the start of its milestone. A card contains:
- milestone and dependencies; whether it is parallel-safe;
- files to read first (with spec §);
- files to create; files that must not be edited;
- the **interface, verbatim** (Opus writes contract headers before dispatch, and Haiku fills in the bodies);
- for vendor tasks, the Cycles source URL and line range;
- acceptance command(s) (`make …`);
- the commit message.

**M0 Bootstrap**
| ID | Task | Deps | Acceptance |
|---|---|---|---|
| T0.1 | LICENSE (GPL-3+), README, `.gitignore`, `THIRD_PARTY_NOTICES.md`, `CLAUDE.md` agent rules (naming, knobs-not-magic-numbers, vendoring rule, experiment format, `make` targets), `docs/spec.md` and `docs/architecture.md` from this plan | – | files present; `make lint` |
| T0.2 | `pyproject.toml` (scikit-build-core stub module, uv groups: dev = pytest, ruff, numpy==2.3.4, nanobind, cibuildwheel; analysis = jax[cpu]; blender = bpy==5.2.2), `Makefile` (`env build test lint check blender-it`) | T0.1 | `make env && make build && python -c "import _painterly"` |
| T0.3 | Import smallpaint sources into `third_party/smallpaint/` and reference PPMs into `tests/data/reference/`, with sha256 provenance and the MIT notice | T0.1 | `make test` (hash test) |
| T0.4 | CI workflow (lint and unit tests on ubuntu) | T0.2 | green on push |

**M1 Ground truth** (oracle, metrics, the first five experiments)
| ID | Task | Deps | Acceptance |
|---|---|---|---|
| T1.1 | `src/app/smallpaint_oracle.cpp`: a minimal-diff copy of `smallpaint_painterly.cpp`, with `trace()` unchanged and the changes listed in `CHANGES.md`. CLI options: size, spp, refr, seed, `--chain image\|row\|lane\|omp-restart:T`, `--ghost all\|lights\|none`, `--alpha`, `--u2`, `--continue-after-emitter`. Outputs: float sums (PFM), smallpaint-mapped PPM, object-id map, K-consumption map. Deterministic jitter replaces the `rand_r` race. | T0.3 | `chain=image` at 400² is statistically indistinguishable from the reference PPM |
| T1.2 | `analysis/painterly_analysis/{io,masks,metrics}.py` (JAX) + unit tests on synthetic images | T0.2 | `make test-analysis` |
| T1.3 | `tests/core/test_oracle_reference.py`: seed-ensemble acceptance plus negative controls | T1.1, T1.2 | positive controls pass, negative controls fail |
| T1.4–T1.8 | Experiments X-oracle, X-ablation, X-lanes, X-resolution, X-ghost-lights (scripts + README drafts); parallel-safe | T1.3 | READMEs complete; Opus finalizes conclusions and sets artist defaults |

**M2 Native toolchain spike** (gate G1)
| ID | Task | Deps | Acceptance |
|---|---|---|---|
| T2.1 | CMake: nanobind `STABLE_ABI NB_STATIC NB_DOMAIN painterly`; Embree 4.4.1 via FetchContent (static, namespaced, INTERNAL tasking, triangle + instance geometry only); hidden visibility plus version script / exported-symbols list. `_painterly.selftest()` traces one triangle. | T0.2 | `make build test` |
| T2.2 | `tools/symbol_audit.py` (nm / nm -gU / dumpbin): only `PyInit__painterly` is exported; no `_ZN3ccl`, `rtc*` or `tbb` symbols | T2.1 | `make audit` |
| T2.3 | `tools/fetch_blender.py` (5.2.2 tarball into `.cache/`, outside git). X-coexist spike: inside `blender -b`, import `_painterly` and run `selftest`, alternating 20× with Cycles renders | T2.2 | experiment README; zero crashes |
| T2.4 | `cibuildwheel` config and wheels workflow (manylinux_2_28 with GCC 11, windows-2022 with MSVC 14.44, macos-14 with deployment target 11.0), plus symbol audit and the X-coexist smoke test per OS | T2.3 | CI green on 3 OSes |

**G1:** if X-coexist fails on any OS, fall back to an out-of-process render server (subprocess + shared-memory pixels) behind the same `Session` API.

**M3 Painterly CPU core with exact oracle parity**
| ID | Task | Deps | Acceptance |
|---|---|---|---|
| T3.1 | `tools/vendor_sync.py` + `third_party/cycles/VENDORED.md` (fetch at the pinned tag, verify sha256, apply patches) | T2.1 | `make vendor-check` |
| T3.2 | Vendor the `util/` subset; `src/util/{param,task,thread}.h` shims; compile under the renamed namespace | T3.1 | `make build audit` |
| T3.3 | `painterly/kernel/types.h`, `globals.h` (KernelPainterlyData {Camera, Integrator, Background}, PainterlyGlobalsCPU spans): **contract written by Opus**. Names never collide with vendored Cycles (Repository layout, "Naming") | T3.2 | compiles |
| T3.4 | `kernel/painterly/sampler.h` (§2, §3 K0) + doctest: equals smallpaint `Halton::next()` replayed for K ≤ 2^23+10 | T3.3 | `make test-cpp` |
| T3.5 | `kernel/painterly/ghost.h` (§5) + analytic sphere: zero mismatches vs smallpaint `Sphere::intersect` on 10⁵ random rays | T3.3 | `make test-cpp` |
| T3.6 | `kernel/painterly/bounce.h` (§4, mirror, glass §6) + doctest vs the oracle's functions | T3.4 | `make test-cpp` |
| T3.7 | `kernel/camera/camera.h` (raster→world from a Blender-style matrix; jitter knob) | T3.3 | unit test vs `camcr` on the square reference |
| T3.8 | `bvh/embree.{h,cpp}` (meshes + instances; closest hit with an unnormalized D, t parametric) | T3.3 | unit test |
| T3.9 | `kernel/integrator/path.h` `trace_pixel()` (§6) + `kernel/film/write.h` | T3.5–T3.8 | doctest |
| T3.10 | `util/task.h` pool + `integrator/path_trace.{h,cpp}` lane scheduler (§3; pass batches; atomic cancel) | T3.9 | bit-identical at 1, 7 and 64 threads and batch sizes 1 and 16 |
| T3.11 | `scene/` host classes with reflected sockets (`PainterlyIntegrator` holds every §8 knob) + `device_update()` | T3.10 | doctest |
| T3.12 | `session/` (render thread, state machine, `progress`, `cancel`, `copy_pixels`, passes combined / object-id / k_consumed) | T3.11 | doctest; cancel latency test |
| T3.13 | `src/blender/python.cpp` bindings (scene descriptor API, ndarray I/O, GIL released in waits, `integrator_sockets()` reflection export) | T3.12 | pytest |
| T3.14 | `tests/core/test_oracle_parity.py`: descriptor of the smallpaint scene (planes as quads, analytic painterly spheres) → **identical K maps** vs the oracle; image within the oracle's own float error | T3.13, T1.1 | pytest |
| T3.15 | X-throughput experiment | T3.14 | experiment README |

**M4 Add-on skeleton** (mirrors `intern/cycles/blender/addon`)
| ID | Task | Deps | Acceptance |
|---|---|---|---|
| T4.1 | `blender_manifest.toml`; `__init__.py` (`PainterlyRender(RenderEngine)` with `bl_use_preview`, `bl_use_eevee_viewport`, `bl_use_shading_nodes_custom=False`, `super().__init__`); `engine.py` facade | T3.13 | `blender --command extension validate` |
| T4.2 | `properties.py` (PropertyGroups generated from `integrator_sockets()`), `ui.py` (`PainterlyButtonsPanel` mixin with `COMPAT_ENGINES`, `get_panels()` exclusion list), `presets.py`, `version_update.py` | T4.1 | bpy pytest |
| T4.3 | Render loop: `begin_result` → poll `progress`/`test_break` → `rect.foreach_set(float32)` → `update_result` → `end_result`; §7 output modes | T4.2 | bpy pytest |
| T4.4 | Orientation test (gradient + one bright pixel: rect row order and lane axis) and integration test via `extension build`/`install-file` with `BLENDER_USER_RESOURCES` isolation and `-b -E PAINTERLY -f 1` | T4.3, T2.3 | `make blender-it` |

**M5 Scene sync** (Python; numpy `foreach_get` with dtype rules: `loop_triangles` → `np.uint32`, `co`/normals/uv → `np.float32`)
| ID | Task | Deps | Acceptance |
|---|---|---|---|
| T5.1 | `sync/camera.py` (`calc_matrix_camera`, shift, sensor fit, ortho) | T4.3 | matrix tests |
| T5.2 | `sync/geometry.py` (object_instances, mesh dedup, corner normals, UVs, material slots) | T4.3 | 1M-triangle export < 2 s (measured, recorded) |
| T5.3 | `sync/light.py` (point/spot ghosts with cone falloff; area quads; sun disk; `emission_scale` knob) | T4.3 | bpy pytest |
| T5.4 | `sync/world.py` (constant background first) | T4.3 | bpy pytest |
| T5.5 | `tools/make_reference_scene.py` → reference `.blend` (90° FOV, 400², meshes + point light r = 0.5, Base Color 1.2 allowed) | T5.1–T5.4 | script runs headless |
| T5.6 | End-to-end parity: the Blender render vs the oracle `--ghost lights` seed ensemble | T5.5, T1.8 | `make blender-it` |

**M6 Node-graph evaluation** (gate G2 = X-svm: if the `graph/` shim fails, keep Cycles names but write our own reduced reflection)
| ID | Task | Deps | Acceptance |
|---|---|---|---|
| T6.1 | Vendor `graph/` and the ustring/TypeDesc shim; X-svm experiment | T3.11 | builds; experiment README |
| T6.2 | `scene/shader_graph` (create_node by type name, set by socket name, connect): **contract by Opus** | T6.1 | doctest |
| T6.3 | `scene/svm` SVMCompiler subset (`add_node<T>`, `input_float`/`input_float3`, `output`, stack allocation, multi-closure emission, ported from `scene/svm.cpp`) | T6.2 | doctest |
| T6.4 | `kernel/svm/svm.h` generated switch, `tools/gen_node_registry.py`, `svm/closure_painterly.h` (Cycles closure categories → {diffuse, mirror, glass, emission, transparent}; selection with the §2 hash RNG) | T6.3 | doctest |
| T6.5 | Python `sync/shader/{flatten,node_table,export}.py` (groups, reroutes, mutes; idname → Cycles type; socket renames Shader→Closure, Mix suffixes, `_001`→`2`; enum aliases) | T6.4 | pytest |
| T6.6–T6.17 | **Node ports**, 2–4 nodes per card, parallel-safe (files only *added*). Batches: Value/RGB/Math/VectorMath · Mix/MapRange/Clamp · Invert/Gamma/BrightContrast/HSV · Separate/Combine Color & XYZ · ColorRamp/RGBCurves (sampled LUT) · TexCoord/Mapping · Noise/WhiteNoise · Voronoi · Checker/Gradient/Wave/Magic/Brick · Image Texture (+ X-colour) · Principled/Diffuse/Glossy/Glass/Refraction/Emission/Transparent · Mix/Add Shader/Background. Checklist per node: vendor evaluator → copy `NODE_DEFINE` + `compile()` → `node_table.py` row → golden test. | T6.5 | Golden test per node: a generated `.blend` with an emission plane driven by the node, rendered by Cycles at 1 spp (pixel centre, Raw, EXR) vs Painterly with knobs `max_depth=1, emission_gain=1`, with no debug code paths; equal within Cycles' own float32 spread |

**M7 Artist experience**
| ID | Task | Deps | Acceptance |
|---|---|---|---|
| T7.1 | Panel layout (Sampling / Brush / Lights / Path / Film); Light and Material overrides (ghost toggle, painterly emission) | M5, M6 | UI screenshot test in `-b` (panel registry dump) |
| T7.2 | Presets from experiment results: "Smallpaint Reference", "Showcase (approx.)", "Fine strokes", "Broad strokes" | T7.1, M1 | preset round-trip test |
| T7.3 | X-animation experiment → seed and frame policy defaults | T7.1 | README |
| T7.4 | `docs/artist-guide.md` with experiment imagery | T7.2 | Opus review |

**M8 Release**
| ID | Task | Deps | Acceptance |
|---|---|---|---|
| T8.1 | Release workflow: wheels → `extension build --split-platforms` → GitHub Release → `server-generate` `index.json` on Pages (absolute archive URLs); GPL source tarball | M4–M7 | dry-run release on a tag |
| T8.2 | Install docs: add a remote repository in Preferences; update flow | T8.1 | Opus review |

**M9 Research track** (parallel to M6–M7): X-mesh-ghost and X-open-scenes. Their conclusions feed a go/no-go on exposing painterly spheres and mesh ghosting.

**Deferred (post-v1):**
- interactive viewport (`view_update`/`view_draw`, progressive rendering);
- GPU (a probe compiling `kernel/` with nvcc/hipcc/Metal, plus one thread per (lane, pass));
- AVX2 kernel variants;
- bump/normal-map nodes;
- an OSL equivalent.

## Orchestration protocol

**Per milestone, one Workflow:**
1. Opus writes the task cards and contract headers.
2. A `pipeline` runs the cards in DAG order with `model:'haiku'`. Parallel-safe cards use `isolation:'worktree'` and are merged in ID order.
3. Each card ends by running its acceptance command and making one commit, `Tx.y: <title>`, with attribution.
4. A failing card is retried once with its logs. A second failure escalates to Opus, which fixes the card or the contract.
5. Gate: `make check` (lint, C++ and Python unit tests, symbol audit, parity tests).
6. An **Opus milestone review** checks spec conformance, naming and consistency, and whether the structure needs a reorganization pass before the next milestone. Its findings become fix-up cards.
7. Push to `claude/clever-johnson-gnso1s`.

**Further rules:**
- Every 12th card slot is an Opus code-quality audit card (TQ.n).
- Opus finalizes experiment conclusions before any defaults are changed.
- Haiku never edits `third_party/`, `docs/spec.md` or contract headers. Changes to those go through Opus.

## Verification (end to end)
- `make check`: ruff, doctest, pytest (analysis, core, oracle reference ensemble, core-vs-oracle exact K-map parity, determinism across thread counts), and the symbol audit.
- `make blender-it`:
  - fetch Blender 5.2.2;
  - build and install the extension in an isolated user directory;
  - render the reference `.blend` with `-E PAINTERLY`;
  - require the result to fall inside the oracle `--ghost lights` seed ensemble, and the negative controls to fall outside it;
  - render node golden scenes against Cycles;
  - repeat the coexistence loop with Cycles.
- CI runs the wheels and smoke renders on linux-x64, windows-x64 and macos-arm64.
- Manual check: install from the remote repository in Blender 5.2.2, open the reference scene, apply the "Smallpaint Reference" preset, and press F12. The image should look like `smallpaint_painterly.ppm`.
