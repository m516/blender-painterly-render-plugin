# TQ.1 — Code-quality audit: M0–M3 kernel layer

Auditor: Opus. Tree audited: `e5e46b7` (T3.12), branch `claude/clever-johnson-gnso1s`.
Card: `docs/tasks/M3/TQ.1-audit.md`.

## Scope and method

Scope: `src/**` (excluding `third_party/`), `analysis/**`, `tools/**`, `tests/**`, `Makefile`, `CMakeLists.txt`, `cmake/`.
Normative references: `docs/spec.md`, `docs/architecture.md`, `CLAUDE.md`.

Every C++ file under `src/painterly/`, `src/test/`, `src/blender/`, `src/app/` and `src/cycles/shim/` was read in full, as were
the build files, the Python tests and the analysis package. The tools were read for naming, knobs and magic numbers.
The audit also ran these checks:
- **Citations.** Every `smallpaint_painterly.cpp:N`, `painterly.cpp:N`, `smallpaint_oracle.cpp:N` and upstream Cycles line
  citation was checked against the cited file: `third_party/smallpaint/`, `src/app/`, and the pinned checkout
  `.cache/vendor/blender-v5.2.2`.
- **Layering.** Includes across `src/painterly/<layer>/` were tabulated against the dependency direction.
- **Warnings.** The project's own translation units (`src/painterly`, `src/test`, `src/blender`, `src/app`) were compiled with
  `-Wall -Wextra -Wshadow -fsyntax-only` in addition to the build flags.
- **Configure output.** A fresh configure was run in a scratch build directory to look for CMake warnings.
- **Lane overflow.** One finding (F1) was reproduced with a scratch program linked against the built libraries.

Severity scale:
- **High**: wrong output or undefined behaviour reachable through a valid knob value.
- **Medium**: an error-path defect, a gap that lets regressions through, or a reproducibility or maintainability problem with
  real cost.
- **Low**: consistency, naming or hygiene.

Line numbers refer to the tree after this audit's commit.

## Summary

| | High | Medium | Low | Total |
|---|---|---|---|---|
| Fixed in this commit (comments, renames) | 0 | 1 | 18 | 19 |
| Open, proposed as fix-up cards | 1 | 6 | 21 | 28 |

The kernel layer is in good shape:
- the dependency direction holds;
- every kernel function is `painterly_`-prefixed and every type under `src/painterly/` is `Painterly`/`KernelPainterly`-prefixed;
- the arithmetic keeps smallpaint's operation order and is tested bitwise;
- `-Wall -Wextra` finds nothing in `src/painterly/`.

The one High finding is in the lane scheduler: `lane_length` near `INT_MAX` silently renders nothing and reports success (F1).

## What was checked and found clean

- **Dependency direction.** The only include from `painterly/kernel` into a higher layer is `kernel/bvh/bvh.h` →
  `painterly/bvh/embree.h`, which is the allowed exception. `painterly/integrator` includes only `kernel`, `util` and itself. No layer
  includes `scene` or `session`, which do not exist yet.
- **Prefixes.**
  - Every kernel function is `painterly_*`, and every type under `src/painterly/` is `Painterly*` or `KernelPainterly*` (`double3`
    is the documented exception).
  - No identifier of the pinned Cycles tree uses the enumerator prefixes (`CHAIN_`, `LOBE_`, `PURPOSE_`, `SPHERE_`, `ANALYTIC_`,
    `HIT_`, `VERTEX_`, `U2_`). The only matches are `app/opengl`'s `VERTEX_SHADER`, `device/optix`'s `HIT_PROGAM_GROUP_OFFSET`
    and a comment in `scene/geometry.h`.
- **Shims.** Every file under `src/cycles/shim/` starts with `Shim: replaces Cycles <path>` and has no vendored counterpart
  (`tests/core/test_shims.py`).
- **Vocabulary.**
  - No `spp` in our code; the only uses quote smallpaint's `params["spp"]`.
  - `chain`, `lane`, `lane_in_row`, `K`, `k_consumed`, `object_id`, `ghost`/`SPHERE_GHOST` and `spiral_frame` are used
    consistently across C++, Python and the oracle.
- **Knobs.**
  - Every literal in `src/painterly/` is either a named constant with a definition comment (`PAINTERLY_VDC_BITS`,
    `PAINTERLY_LUMA_*`, `PAINTERLY_RASTER_PIXEL_CENTRE`, …) or carries a smallpaint or Cycles citation.
  - The remaining exception is the 9-float triangle stride (F23).
- **Upstream citations.**
  - `math_base.h:499-509`, `kernel/light/spot.h:28-31`, `scene/light.cpp:177-178`, `string.cpp` lines 244-250 and `system.cpp`
    lines 53-71 and 145-244 all match `.cache/vendor/blender-v5.2.2`.
  - The smallpaint citations that were wrong are listed below and fixed.
- **Test tolerances.**
  - Analysis tests use only the bisection `xtol` or float64 round-off with a comment.
  - C++ tests are bitwise except `test_analytic` (float64, justified), `test_camera` (float64, justified), `test_bounce` (float64,
    justified) and `test_bvh` (binary32, see F24).
- **Test registration.** ctest registers `painterly_tests` once, and pytest collects each file once. The doubled `make check` steps
  are F15.

## Fixed in this commit

All are comment fixes or trivial renames. No behaviour changed. `make check` passes.

| # | Sev. | File:line | Issue | Fix applied |
|---|---|---|---|---|
| X1 | Medium | `src/painterly/kernel/geom/analytic.h:24-29` | The comment said the **far** root is tried first, and the near root only when the far one fails. `sol2 = -b - sqrt(disc)` is the **near** root: the code (and SPEC §5) tries the near root first and never falls back to the far root when the divided near root fails `t > eps`. This is misleading in a bit-parity-critical function. | Rewrote the comment: near root first, far root only when the undivided near root is not beyond eps, and no far-root retry after the caller's `t > eps`. |
| X2 | Low | `src/painterly/kernel/bvh/bvh.h:22` | Cites `inf = 1e9` at `smallpaint_painterly.cpp:35`. Line 35 is `#define MAX`. | `:38`. |
| X3 | Low | `src/painterly/kernel/camera/camera.h:73` | Cites `d = normalize(cam - o)` with o = 0 as `(:292-293)`. The origin is set at :289 and d at :293. | `(:289, :293)`. |
| X4 | Low | `src/painterly/kernel/camera/camera.h:83` | Cites fovx/fovy at `:173-174`. They are at :174-175. | `:174-175`. |
| X5 | Low | `src/painterly/kernel/camera/camera.h:100` | Cites the origin at `:292`. It is at :289. | `:289`. |
| X6 | Low | `src/painterly/kernel/film/write.h:13` | Cites `sum += L` at `:287-289` (the `Vec c; Ray ray; ray.o` lines). The accumulation is at :295-297. | `:295-297`. |
| X7 | Low | `src/painterly/kernel/integrator/path.h:151` | Cites the tint adds at `(:220, :238)`, which are closing braces. They are at :219 and :236. | `(:219, :236)`. |
| X8 | Low | `src/test/test_bounce.cpp:61` | The mirror block is cited as `:216-217`. It is :215-216. | `:215-216`. |
| X9 | Low | `src/test/smallpaint_camcr_ref.cpp:4, 68, 69` | Oracle citations are off by one: the jitter lines are 365-366, take_sample's camera is 363-367, and compute_object_ids's camera is 383-385. | Corrected all three. |
| X10 | Low | `src/painterly/kernel/integrator/path.h:33` (+5 uses) | `VERTEX_PASS` uses "pass", which is reserved project vocabulary (SPEC §0, CLAUDE.md rule 3) for a sample pass. The enumerator means a tinted pass-through vertex. | Renamed `VERTEX_PASS` → `VERTEX_TINT`, matching its comment and SPEC §6 ("the weight tints the child radiance"). No test referenced it. The T3.11 card's interface block still shows the old name (historical record, not edited). |
| X11 | Low | `src/painterly/kernel/integrator/path.h:7, 30` | "backward pass" overloads "pass". | "backward evaluation", the term the code already uses at :149. |
| X12 | Low | `src/painterly/kernel/integrator/path.h:172` | Cites `SPEC §7; the object-id pass` for object ids. SPEC §7 says nothing about object ids; they are SPEC §9's list positions. | `SPEC §9 object ids; the object_id buffer`. |
| X13 | Low | `src/painterly/kernel/camera/camera.h:106, 130-131` | (a) "the object-id pass" overloads "pass". (b) The perspective comment said `R * normalize(Pc)`, but the code applies a second normalize. | (a) "the object_id buffer (painterly_primary_object_id)". (b) The comment now states the outer normalize and why. |
| X14 | Low | `src/painterly/bvh/embree.h:6-8` | "SPEC §5 (the hit record)": SPEC §5 defines no hit record. | The hit record is `PainterlyIntersection` (globals.h), and the SPEC §4/§5 citation is kept for parametric t. |
| X15 | Low | `src/painterly/integrator/path_trace.cpp:152` | "(SPEC §3 unit)": SPEC §3 does not define units. The cancellation points come from the T3.12 card. | "(T3.12 card)". |
| X16 | Low | `src/painterly/integrator/path_trace.h:25-26`; `src/painterly/util/thread_pool.h:7-9` | (a) The lifetime note omitted `kg`, which the object keeps a pointer to. (b) "every lane its own … scratch": scratch is per worker. | Both corrected. |
| X17 | Low | `CMakeLists.txt:18`; `src/painterly/util/CMakeLists.txt:1-2` | (a) `-ffp-contract=off` was attributed to SPEC §6, which does not mention it; architecture.md "Determinism contract" does. (b) "2 MB stacks" holds only on macOS and non-glibc Linux (`shim/util/thread.cpp:23-30`). | Both corrected. |
| X18 | Low | `src/painterly/kernel/closure/bounce.h:25-26, 50`; `src/test/smallpaint_scene_fixture.h:29, 43` | Mixed citation forms (`painterly.cpp:N` and `smallpaint_painterly.cpp:N`) in one file. | Normalised these files to the long form of CLAUDE.md rule 2. Both forms remain valid per SPEC's preamble. |
| X19 | Low | `src/test/test_util.cpp:16-21`; `src/app/CHANGES.md:103`; `tests/core/test_shims.py:41` | (a) The oracle hash was included as `"../app/…"` into `painterly::oracle`, while the other tests use `"app/…"` in `::smallpaint_oracle`. (b) CHANGES.md claimed meta.json "is the same for every render", which is false (`wall_seconds`, `seed`, …). (c) A stale docstring listed three T3.2 shims. | (a) Same path and namespace as `test_sampler.cpp`. (b) "its fields are the same as before T3.4". (c) Docstring states what the test checks. |

## Open findings

| ID | Sev. | File:line | Issue | Proposed fix | Card |
|---|---|---|---|---|---|
| F1 | **High** | `src/painterly/integrator/path_trace.cpp:24` | `lanes_per_row` computes `(width + lane_length - 1) / lane_length` in `int`. For `lane_length > INT_MAX - width + 1` this overflows (UB). In practice `per_row` becomes 0, `parallel_for(0)` renders nothing, and `render_passes` returns **true** with `passes_done` advanced: a black image reported as complete. The T3.13 socket is "int, min 1" with no maximum, and T3.15 rejects only `< 1`. **Reproduced:** 32×32 fixture, `CHAIN_LANE`, `lane_length = INT_MAX` gave `ok=1 passes_done=1 total_k=0`, against `total_k=16631` for `CHAIN_ROW`. The oracle clamps (`smallpaint_oracle.cpp:471`), and its contract test covers `lane:2147483647` (`tests/oracle/test_oracle_contract.py:18`); the core does not. | Clamp `L = min(lane_length, width)` before use (exact by SPEC §3: L ≥ width is one lane per row, lane_in_row 0), or compute in `int64_t`. Add a doctest: `lane:INT_MAX` and `lane:W` equal `row` bitwise. | TQ.1-1 |
| F2 | Medium | `src/painterly/util/thread_pool.cpp:29-33`; `thread_pool.h:49-63` | If creating worker k throws, the catch calls `request_stop()` and rethrows. The destructor body does not run, and members are destroyed in reverse declaration order, so `mutex_` and both condition variables die **before** `workers_` joins the already-started threads. Those threads may still be waking inside `work_ready_.wait`: undefined behaviour on the error path. | In the catch: `request_stop(); workers_.clear(); throw;`. Alternatively, declare `workers_` after the synchronisation members, or both. | TQ.1-1 |
| F3 | Medium | `src/test/test_path_trace.cpp` (whole file) | No test covers: cancellation (`render_passes` → false, `passes_done` unchanged); `pass_begin != passes_done` → `invalid_argument`; constructor validation; or `render_object_id` (never called by any C++ test). T3.14 covers cancel only indirectly through the session. | Add doctests: a pre-set `cancel` returns false with `passes_done` unchanged for image and lane chains; the batch-order and size checks throw; `render_object_id()` equals `painterly_primary_object_id` per pixel at 1 and 7 threads. | TQ.1-1 |
| F4 | Low | `src/painterly/kernel/sample/sampler.h:90`; `path_trace.cpp:52-61` | `1u << k0_phase_lock_bits` is UB for q < 0 or q ≥ 32. `PainterlyPathTrace` validates chain, lane_length and max_depth but not q. The Python boundary validates it (T3.15); C++ callers such as `PainterlySession` tests do not. | Validate `0 <= k0_phase_lock_bits <= PAINTERLY_K0_BITS` in the `PainterlyPathTrace` constructor, next to `lane_length`. | TQ.1-1 |
| F5 | Low | `src/painterly/kernel/bvh/bvh.h:42-50` | When an analytic primitive beats a triangle hit, `isect->prim`, `u`, `v` and `Ng` keep the triangle's values under `kind = HIT_ANALYTIC`. No reader uses them today, but the record is inconsistent. | On an analytic win, assign `*isect = PainterlyIntersection{}` and then set t, kind and index. This is bitwise neutral. | TQ.1-1 |
| F6 | Low | `src/painterly/kernel/integrator/path.h:113-143` | An unknown `lobe.kind` matches no case. No vertex is recorded and the hit's emission is silently lost. | Kernel: add `default:` that records `VERTEX_END` with `e_term` (fail-safe). Host: reject unknown kinds in `PainterlyScene::device_update` (T3.13's validation list). | TQ.1-1 |
| F7 | Low | `src/painterly/kernel/integrator/path.h:179`; `src/painterly/integrator/buffers.h:19` | The miss id is the literal `-1` in the kernel and `PAINTERLY_OBJECT_ID_MISS` in the integrator ("as painterly_primary_object_id returns it"). | Define `PAINTERLY_OBJECT_ID_MISS` once at kernel level (path.h), use it in `painterly_primary_object_id`, and have buffers.h include it. | TQ.1-1 |
| F8 | Low | `path_trace.cpp:59`; `src/app/smallpaint_oracle.cpp:721` | The domain of `max_depth` differs: the core accepts 0, while the oracle (`--max-depth N >= 1`) and the T3.13 socket ("int, min 1") do not. | Require `max_depth >= 1` in `PainterlyPathTrace`, as the oracle and the socket do. | TQ.1-1 |
| F9 | Medium | `CMakeLists.txt:18-23` | No target enables compiler warnings, so the "no warnings-as-noise" check is vacuous. With `-Wall -Wextra`, `src/painterly/**` and every test except one are clean today. The exception is `-Wunused-parameter` in the verbatim smallpaint copy in `test_analytic.cpp:74`; the oracle is a separate target. Nothing stops new warnings from accumulating. | `target_compile_options(... PRIVATE -Wall -Wextra)` (MSVC `/W4`) on `painterly_util`, `painterly_bvh`, `painterly_integrator`, `painterly_tests` and `_painterly`'s own sources, not on `cycles_*`, doctest, Embree or the oracle. Add `set_source_files_properties(test_analytic.cpp PROPERTIES COMPILE_OPTIONS -Wno-unused-parameter)` with a "verbatim smallpaint copy" comment. Optionally add `-Werror` in CI only. | TQ.1-2 |
| F10 | Low | `src/test/CMakeLists.txt:11-12` | Every configure prints two doctest warnings: a CMake deprecation warning (`cmake_minimum_required(VERSION 3.0)`) and a CMP0063 developer warning for `doctest_with_main`. This is noise in every build log. | doctest is header-only. Fetch it without running its CMakeLists (`FetchContent_Declare(... SOURCE_SUBDIR <none>)` / `FetchContent_Populate`), then define `add_library(painterly_doctest INTERFACE)` with the include directory. | TQ.1-2 |
| F11 | Low | `cmake/painterly_embree.cmake:28, 73-76` | The INTERFACE target `painterly_embree` has the same name as Embree's library file (`EMBREE_LIBRARY_NAME painterly_embree` → `libpainterly_embree.a`, CMake target `embree`). It is also the only target with a `painterly::` alias. | Rename the interface target (for example `painterly_embree_interface`) and keep `painterly::embree` as its alias, or drop the alias and link `painterly_embree` everywhere. Use one convention. | TQ.1-2 |
| F12 | Low | `src/blender/selftest.cpp:41-114`; `src/blender/CMakeLists.txt:12` | `_painterly.selftest()` builds its own Embree device (default config: all hardware threads), scene and ray. This duplicates `painterly_bvh` (`threads=1`, robust flags) and uses another mask spelling (`mask = -1` vs `0xFFFFFFFFu`). The module links `painterly::embree` directly. | Once T3.15 links the engine layers, trace the selftest ray with `painterly_embree_scene_create` + `painterly_embree_intersect_closest`. Keep the `RTC_DEVICE_PROPERTY_TASKING_SYSTEM` probe, for example via a small `painterly_embree_device_info()` in embree.h. Keep the Python result keys. Or record in selftest.h why it must stay independent of `painterly_bvh`. | TQ.1-2 |
| F13 | Low | `src/painterly/` (no target) | The header-only kernel has no CMake target. Its link dependency on `painterly_bvh`, which `kernel/bvh/bvh.h` needs, is implicit. | `add_library(painterly_kernel INTERFACE)` linking `painterly_bvh cycles_util`, and consumers link `painterly_kernel`. | TQ.1-2 |
| F14 | Low | `src/blender/*.{h,cpp}`; `src/test/*.cpp` | Header style is split. `src/painterly/**` and the fixture use `/* SPDX-FileCopyrightText: 2026 The Painterly Authors … */`. The M2 and test sources use `// SPDX-License-Identifier` with no copyright line, and `//` comments where Cycles style is `/* */`. | Give every non-vendored C++ file the `/* SPDX-FileCopyrightText … SPDX-License-Identifier … */` header. Converting body comments is optional. | TQ.1-3 |
| F15 | Low | `Makefile:61`; `tests/core/test_symbol_audit.py:14`; `tests/core/test_vendored.py:11` | `make check` runs the symbol audit twice (in `test-py` via `test_symbol_audit.py`, then `audit`) and the vendor check twice (`test_vendored.py`, then `vendor-check`). | Keep the pytest wrappers, since cibuildwheel and CI rely on pytest, and make `check: lint build test`. Keep `audit` and `vendor-check` as standalone targets. Or the reverse: one registration each. | TQ.1-2 |
| F16 | Medium | `src/test/test_{math_double3,analytic,bounce,sampler,camera}.cpp`; `smallpaint_camcr_ref.cpp` | Test scaffolding is copied 2–5 times: `same_bits` ×5 (test_analytic:262, test_bounce:147, test_camera:62, test_math_double3:89, test_sampler:78); smallpaint's `Vec` ×4 (test_math_double3:21, test_analytic:26, test_bounce:32, camcr_ref:38); `unit_double`/`uniform`/`uniform_triple` ×2; `draw_index` ×2; `Triple`, `to_double3`, `to_ref` and `random_unit_normal`; the oracle hash included in three different namespaces. A fix to the reference copy (for example the X8 citation) must be repeated by hand. | Add `src/test/bitwise.h` (`same_bits`, the mt19937_64 draw helpers, `Triple`) and `src/test/smallpaint_ref.h`. The latter is **one** verbatim copy, clang-format off, of smallpaint's Vec, Ray, Obj, Plane, Sphere, Halton, hemisphere, PI and eps, plus the oracle's `intersect_exact` and `camcr`, each with its line citation. Include them everywhere. The tests' inputs and assertions stay byte-identical. | TQ.1-3 |
| F17 | Low | `src/test/test_path.cpp:107-280`; `src/test/smallpaint_scene_fixture.h:56-78` | `GlassSlabScene` repeats the fixture's "own vectors, point `PainterlyGlobalsCPU` at them" code. | After T3.13, build both through `PainterlyScene` + `device_update` (T3.14 already does this for its session test); until then, factor a small `KernelSceneStorage` helper in the fixture header. | TQ.1-3 |
| F18 | Low | `src/test/test_main.cpp:7-10`; `src/test/test_path.cpp:542` | `TEST_CASE("doctest runs") { CHECK(true); }` tests nothing. `painterly_primary_object_id(kg, 16, 16)` uses a magic pixel. | Delete the trivial case (the entry point stays). Use `Fixture::HEIGHT / 2, Fixture::WIDTH / 2`. | TQ.1-3 |
| F19 | Medium | `src/test/test_camera.cpp:138`; `src/painterly/kernel/camera/camera.h:136-141` | The orthographic branch of `painterly_camera_generate_ray` has no test. The perspective test uses an identity `camera_to_world` with zero jitter, so rotation, translation and raster jitter are untested. T5.1 will feed both branches from Blender. | Add doctests with exact dyadic matrices. Orthographic: a pixel's origin and direction in closed form, under an axis-permutation `camera_to_world` with an integer translation. Perspective: the same permutation and translation, plus jittered rays equal to the unjittered ray at raster `+ jx, + jy` from `painterly_rng_signed`. | TQ.1-4 |
| F20 | Low | `src/test/test_bounce.cpp:232` | Every diffuse test uses F = I. `transform_direction_3x3` with a non-identity spiral frame (SPEC §1 `camera`/`world` frames) is not tested. | Add a case with F an axis permutation with signs (exact in double): `d = N + F s` equals the reference built from the permuted s, bitwise. | TQ.1-4 |
| F21 | Low | `src/painterly/kernel/geom/triangle.h:49-56` | The corner-normal transform by a non-identity `itfm` (scale, shear, mirror) is untested. `GlassSlabScene` uses identity transforms only. | Doctest with a dyadic shear or mirror object: the shading normal equals the closed-form inverse-transpose normal, bitwise where exact. | TQ.1-4 |
| F22 | Medium | `src/app/smallpaint_oracle.cpp:561-584`; `src/app/CHANGES.md:103`; `analysis/painterly_analysis/experiment.py:34` | `meta.json` omits the T3.4 knobs `diffuse_gain`, `emission_gain`, `ray_epsilon` and `max_depth`, so a render directory does not describe itself. T3.16 passes all four on every parity run. The experiment cache stays correct, because its key hashes the options, but a render inspected later cannot be identified. | Record the four values (`%.17g` / `%d`) and bump `oracle_version` to `"2"` in `write_meta` and in `experiment.ORACLE_VERSION`. Update CHANGES.md item 21 and keep `sum.npy` byte-identical (`test_new_knobs_default_identity`). Cost: the rebuild invalidates `.cache/renders` (as any oracle rebuild does); finished experiments are not re-run. | TQ.1-5 |
| F23 | Low | `src/painterly/kernel/geom/triangle.h:41`; `src/painterly/kernel/globals.h:51-52` (contract) | The triangle stride `9 *` is a literal. globals.h documents "9 floats". | Add `PAINTERLY_TRIANGLE_FLOATS = 9` (3 corners × 3 coordinates, a layout definition) in globals.h (contract), used by triangle.h and the future T3.13 export. | TQ.1-6 |
| F24 | Low | `src/test/test_bvh.cpp:26-36` | The binary32 tolerance `F32_STEPS = 4` counts roundings informally ("not a measurement of Embree's source"). CLAUDE.md rule 2 allows a convergence parameter or float64 round-off; a binary32 bound for an external kernel is neither. The bound has held so far (M2: 6e-8 against 2.4e-7) but is not derived. | Opus decision: either accept "binary32 round-off of a derived operation count" as a rule-2 justification and derive the count with Higham's γ_n for Embree's instance transform plus its Plücker/Möller test, or restrict the exact-valued asserts to exactly representable cases and keep only the closed-form point and normal checks. | TQ.1-6 |
| F25 | Low | `src/painterly/bvh/embree.cpp:92-126, 341`; `src/painterly/kernel/geom/triangle.h:49-56`; `camera.h:28-35`; `math_double3.h:77` | Normals reach world space by two routes: Embree's `Ng` through a double cofactor `(A^-1)^T` computed from the float `object_to_world`, and corner normals through the transpose of the scene-provided float `itfm`. The two can differ in the last bits, and on which side a mirrored object's normals land if `itfm` is computed differently. 3×4 direction transforms are also hand-written in three places. | Opus decision (touches the contract `math_double3.h`/`globals.h`): one source for the normal matrix, either the BVH reads `itfm` or the scene stops exporting it, plus shared `painterly_transform_direction_3x4` / `_transposed_3x4` helpers. | TQ.1-6 |
| F26 | Low | `src/painterly/kernel/types.h:83`, `globals.h:22` (contracts); `docs/spec.md` §8 | "pass" also names output layers ("object-id pass", SPEC §8 "Combined pass"), next to SPEC §0's sample pass. The audit fixed the non-contract comments (X11-X13). | Opus: say "object_id buffer"/"render pass" in the contracts. Optionally add a SPEC §0 note: "pass" alone always means a sample pass, and Blender output layers are "render passes". | TQ.1-6 |
| F27 | Low | `analysis/painterly_analysis/metrics.py:232, 309, 278`; `ensemble.py:117, 278, 364`; `tests/oracle/test_oracle_reference.py:34` | Default values are repeated as literals: `block=25` ×2, `alpha=0.01` ×2 (plus the test's own `ALPHA = 0.01`) and `n_resamples=100_000` (the same value as `PERMUTATION_RESAMPLES`). `f_max = min(h, w) // 4` has no stated reason. | Add named module constants `BLOCK_RMSE_SIZE = 25` ("the plan's acceptance metrics"), `DEFAULT_ALPHA = 0.01` (the module docstring's convention, used by the test too) and `SIGN_FLIP_RESAMPLES`. Document or name the `f_max` divisor, or make it an explicit knob default with its rationale. | TQ.1-7 |
| F28 | Low | `analysis/painterly_analysis/experiment.py:31, 131-145` | `experiment` imports the private `oracle._option_flags`, and `_render` repeats `run_oracle`'s command assembly and error message. | Make `option_flags` public. Factor `oracle.run_oracle_process(out_dir, options) -> None`, used by both `run_oracle` (then `read_oracle`) and `experiment._render`. | TQ.1-7 |

Informational, no action:
- **Thread shim.** `src/cycles/shim/util/thread.cpp:30` ignores `pthread_create`'s return value on macOS and musl. This is upstream Cycles' code, copied unchanged; a failure there surfaces later as a bad join. Keep it as upstream.
- **`K` naming.** `K` / `K_start` / `image_chain_K_` use capital K against Cycles' snake_case, deliberately: `K` is the SPEC §2 term, and CLAUDE.md rule 3 lists it.

## Proposed fix-up cards

Card IDs are placeholders for the orchestrator. Each card follows `docs/tasks/README.md` and ends with `make check`.
None touches `third_party/`, `docs/spec.md` or `docs/plan.md`. Only TQ.1-6 touches `CONTRACT:` headers, so it is Opus-only.

### TQ.1-1 — Lane scheduler and thread-pool robustness (F1–F8)
Milestone M3 · Depends on: T3.12 · **Run before T3.13** (T3.13–T3.16 build on `PainterlyPathTrace`) · Agent: Haiku · Parallel-safe: no.
- **Modify:**
  - `src/painterly/integrator/path_trace.cpp`:
    - clamp the lane length to the width (F1);
    - validate `k0_phase_lock_bits ∈ [0, PAINTERLY_K0_BITS]` (F4);
    - require `max_depth >= 1` (F8), and update the header comment.
  - `src/painterly/util/thread_pool.{h,cpp}`: join the started workers before rethrowing, or move `workers_` last (F2).
  - `src/painterly/kernel/bvh/bvh.h`: reset the record on an analytic win (F5).
  - `src/painterly/kernel/integrator/path.h`:
    - add a `default:` case that ends the path with `e_term` (F6);
    - add the kernel-level `PAINTERLY_OBJECT_ID_MISS` (F7).
  - `src/painterly/integrator/buffers.h`: use the kernel constant (F7).
  - `src/test/test_path_trace.cpp`: the tests below (F1, F3).
- **Tests (doctest, bitwise, on the 32×32 fixture):**
  - `lane:INT_MAX`, `lane:32` and `lane:33` each equal `row` bitwise (combined, k_consumed). This fails before the F1 fix.
  - A pre-set cancel returns false with `passes_done == 0`, for `image` and `lane:5`.
  - `render_passes(1, 2)` on fresh buffers throws `std::invalid_argument`.
  - `PainterlyPathTrace` throws for `k0_phase_lock_bits ∈ {-1, 23}` and `max_depth = 0`.
  - `render_object_id()` equals `painterly_primary_object_id` per pixel, at 1 and 7 threads.
- **Acceptance:**
  - `make build test lint`.
  - The existing determinism test is unchanged and passes.
  - `test_path.cpp` passes unchanged (F5–F7 are bitwise neutral on valid data).
- **Commit:** `TQ.1-1: lane scheduler and thread-pool robustness`.

### TQ.1-2 — Build hygiene (F9–F13, F15)
Milestone M3 · Depends on: T3.12 (F12 after T3.15) · Agent: Haiku.
- **Modify:**
  - root `CMakeLists.txt` or each `src/painterly/*/CMakeLists.txt`:
    - `-Wall -Wextra` (MSVC `/W4`) on our targets only (F9);
    - an optional `painterly_kernel` INTERFACE target (F13).
  - `src/test/CMakeLists.txt`:
    - consume doctest header-only, with no configure warnings (F10);
    - `-Wno-unused-parameter` on the verbatim copy in `test_analytic.cpp` only (F9).
  - `cmake/painterly_embree.cmake`: one target-naming convention (F11).
  - `Makefile`: `check` registers each audit once (F15).
  - `src/blender/selftest.{h,cpp}` and `src/blender/CMakeLists.txt`: F12, after T3.15.
- **Acceptance:**
  - a fresh configure in an empty build directory prints no `CMake Warning` or `CMake Deprecation Warning`;
  - `make check` prints no compiler warning for `src/painterly`, `src/test` or `src/blender`;
  - `make check` runs `symbol_audit.py` and `vendor_sync.py check` once each.

### TQ.1-3 — Shared test scaffolding and file headers (F14, F16–F18)
Milestone M3 · Depends on: TQ.1-1 (same test files) · **Run before T3.17** (which adds triangle tests) · Agent: Haiku.
- **Create:** `src/test/bitwise.h` and `src/test/smallpaint_ref.h`.
  - `smallpaint_ref.h` is clang-format off and byte-identical to the cited source lines, apart from CRLF→LF.
  - It holds one namespace `smallpaint_ref`, plus `smallpaint_oracle` for the oracle hash, `intersect_exact` and `camcr`.
- **Modify:**
  - `src/test/test_{math_double3,analytic,bounce,sampler,camera,util}.cpp` and `smallpaint_camcr_ref.cpp`: delete the local
    copies and include the shared headers;
  - `test_main.cpp`, `test_path.cpp` (F18);
  - the file headers of `src/test/*.cpp` and `src/blender/*.{h,cpp}` (F14).
- **Rule:** no test input, seed, draw order or assertion may change, and the mismatch counts stay 0. Check this by running
  `painterly_tests` before and after: the doctest assertion count may drop only by the deleted trivial case.
- **Acceptance:** `make build test lint`; `grep -c "struct Vec {" src/test/*.cpp` is 0.

### TQ.1-4 — Kernel test coverage: cameras, spiral frame, transformed normals (F19–F21)
Milestone M3 · Depends on: TQ.1-3 · Agent: Haiku.
- **Modify:** `src/test/test_camera.cpp`, `src/test/test_bounce.cpp`, `src/test/test_path.cpp`.
- **Constraints:** every matrix is dyadic (an axis permutation, power-of-two scales, integer translations), so each expectation is
  exact. Where a normalize makes a value inexact, use only the float64 round-off bound of CLAUDE.md rule 2 (`rtol = 1e-12`, with
  its comment).
- **Acceptance:**
  - `make build test lint`;
  - each new test fails when the branch under test is deliberately broken. Record the experiment in the commit body, for example
    swap the orthographic origin's x and y.

### TQ.1-5 — Self-describing oracle renders (F22)
Milestone M3 · Depends on: none · Agent: Haiku · **Do not run while an experiment is rendering**: the oracle's sha256 changes.
- **Modify:**
  - `src/app/smallpaint_oracle.cpp` `write_meta`: the four knobs, and `oracle_version` `"2"`;
  - `src/app/CHANGES.md` item 17 and item 21;
  - `analysis/painterly_analysis/experiment.py` `ORACLE_VERSION`;
  - `tests/oracle/test_oracle_contract.py`: assert that the four keys round-trip their CLI values.
- **Acceptance:**
  - `make build test lint`;
  - `test_new_knobs_default_identity` still passes;
  - `sum.npy` for `--size 64 --passes 2 --seed 7` is byte-identical to the build before the card.

### TQ.1-6 — Contract touch-ups (Opus only; F23–F26)
- Edit the `CONTRACT:` headers `painterly/kernel/globals.h`, `painterly/kernel/types.h` and `painterly/util/math_double3.h`.
- Decide F24 (the binary32 tolerance rule) and F25 (one normal matrix).
- Decide whether SPEC §0 gets the "render pass" note (F26).

### TQ.1-7 — Analysis constants and runner reuse (F27, F28)
Milestone M3 · Depends on: none · Agent: Haiku · Parallel-safe: yes.
- **Modify:**
  - `analysis/painterly_analysis/{metrics,ensemble,oracle,experiment}.py` and `__init__.py` (export the new names);
  - `tests/oracle/test_oracle_reference.py` (use `ensemble.DEFAULT_ALPHA`);
  - `analysis/tests/` where the defaults are asserted.
- **Rule:** no default value changes. The experiments' recorded `results.json` must reproduce unchanged.
- **Acceptance:** `make test lint`; `pytest analysis/tests -q`.

## Notes for the orchestrator

- The audit card has no Acceptance section. This commit was gated on `make check`: lint, build, ctest (44 doctest cases),
  pytest (202 passed, 1 slow deselected), symbol audit and vendor check. All passed.
- F1 is the only finding that changes rendered output, and only for `lane_length > INT_MAX - width + 1`. All other open findings
  are bitwise neutral on valid inputs.
- TQ.1-1 should land before T3.13, because T3.13–T3.16 build on `PainterlyPathTrace`. TQ.1-3 should land before T3.17 adds more
  copied scaffolding.
