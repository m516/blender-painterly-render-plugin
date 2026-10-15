# Opus decisions for the M3-M5 card fixes (read together with m3_sweep.md)

Every item of `m3_sweep.md` is to be applied as the sweep proposes, **except** where a decision below says otherwise or
fixes a choice the sweep left open. Cross-file names here are binding, so all editors use the same words.

## Layout and build
- D1. Shims are never wrappers: delete the sentence "`third_party` lets a shim wrap the real header as `#include "cycles/<path>"`"
  and drop `<third_party>` from every include-order list. The public include order of `cycles_util` is exactly:
  `src/cycles/shim`, `third_party/cycles`, `third_party/cycles/sse2neon`, `src`.
  docs/architecture.md must state the same four.
- D2. sse2neon is vendored by `tools/vendor_sync.py add extern/sse2neon/sse2neon.h --dest-prefix sse2neon`, to
  `third_party/cycles/sse2neon/sse2neon.h`. T3.2 also adds an sse2neon (MIT) row to THIRD_PARTY_NOTICES.md (T3.2 Modify).
- D3. `PainterlyRenderBuffers` lives in `src/painterly/integrator/buffers.h/.cpp`, not in session/. Every mention follows
  (T3.12, T3.14, architecture.md).
- D4. Library targets:
  - `painterly_util` is our own code (thread pool; T3.12 creates `src/painterly/util/CMakeLists.txt`).
  - `painterly_bvh` comes from T3.10.
  - `painterly_integrator` (path_trace + buffers) comes from T3.12 in `src/painterly/integrator/CMakeLists.txt` and links
    `painterly_util` and `painterly_bvh`.
  - `painterly_scene` comes from T3.13 and links `cycles_graph`, `painterly_bvh`.
  - `painterly_session` comes from T3.14 and links `painterly_integrator`, `painterly_scene`.
  - `src/painterly/CMakeLists.txt` is created by T3.10. Each later card that adds a layer appends its `add_subdirectory`
    in dependency order: util, bvh, integrator, scene, session.
  - The vendored-code targets are `cycles_util` (T3.2; also compiles the shim sources `src/cycles/shim/util/*.cpp` that
    T3.3 adds) and `cycles_graph` (T3.3, under Modify of `src/cycles/CMakeLists.txt`).
- D5. Embree is configured when `PAINTERLY_BUILD_MODULE OR PAINTERLY_BUILD_TESTS`. `src/CMakeLists.txt` adds
  `cycles` and `painterly` under the same condition, so `make oracle` (module and tests OFF) still configures. This goes
  in T3.10 (Modify root `CMakeLists.txt` and `src/CMakeLists.txt`).
- D6. Every card that creates a C++ test lists `src/test/CMakeLists.txt` under Modify: "add <files>; link <targets>"
  (the list in sweep 5.1).
- D7. T3.2 also modifies the `Makefile` lint/format rules to cover untracked files:
  `git ls-files --cached --others --exclude-standard 'src/*.cpp' 'src/*.h'`.
- D8. `tools/vendor_sync.py` gets a `remove <dest>` subcommand (T3.1). T3.3 uses it if T3.2's closure vendored a header
  that T3.3 must shim.
- D9. The kernel's Embree call is the one allowed downward exception. `painterly/kernel/bvh/bvh.h` calls
  `painterly/bvh/embree.h`, as Cycles' `kernel/device/cpu/bvh.h` calls Embree. docs/architecture.md states this exception
  explicitly in "Dependency direction".
- D10. The smallpaint test scene shared by T3.11 and T3.12 is `src/test/smallpaint_scene_fixture.h` (created by T3.11).
- D11. `SMALLPAINT_PI` moves into a shared kernel header created by T3.8: `src/painterly/kernel/smallpaint.h`, which holds
  smallpaint's constants, each with its line citation. T3.9 includes it.

## Names
- D12. Embree wrapper functions: `painterly_embree_scene_create`, `painterly_embree_scene_free`,
  `painterly_embree_intersect_closest`.
- D13. `enum class PainterlySessionState { STATE_IDLE, STATE_RENDERING, STATE_DONE, STATE_CANCELLED, STATE_ERROR }`.
  The Python strings stay 'idle', 'rendering', 'done', 'cancelled', 'error'.
- D14. `enum PainterlyPathVertexKind : int { VERTEX_DIFFUSE = 0, VERTEX_PASS = 1, VERTEX_END = 2 }`.
- D15. NodeType names: `NODE_DEFINE(PainterlyIntegrator)` registers `"painterly_integrator"`, never `"integrator"`.
- D16. In `painterly/scene/integrator.h`:
  - `enum PainterlySpiralFrame : int { SPIRAL_FRAME_CAMERA = 0, SPIRAL_FRAME_WORLD = 1, SPIRAL_FRAME_OBJECT = 2, SPIRAL_FRAME_SMALLPAINT = 3 }`;
  - `enum PainterlyOutputMode : int { OUTPUT_DISPLAY_REFERRED = 0, OUTPUT_SCENE_LINEAR = 1 }`.
  The pyi says "identifiers in C++ enum value order".
- D17. `PainterlySocketUIInfo` uses `std::optional<double>` for min/max/soft_min/soft_max. nullopt maps to Python None.
- D18. The oracle flag is `--ray-epsilon`, renamed from `--eps` (T3.4). T3.16's `ORACLE_EXACT_KNOBS` and T4.4 use it.

## Behaviour and SPEC
- D19. The smallpaint camera stores `camera_to_world` = the rotation `M_s→camᵀ`, with translation 0. Then
  `spiral_frame = camera` gives F = R(e), which is F = I at the defaults, the same as `smallpaint`. T3.13 tests this.
- D20. `emission_scale` applies to lights only (SPEC §6, §8). Material emission is `Emission Color · Emission Strength`
  (T5.3).
- D21. The "Smallpaint Reference" preset touches no lights. It renders the built-in reference scene
  (`reference_scene = True`), which carries smallpaint's own emission. Only `tools/make_reference_scene.py` sets
  120 W, r = 0.5. Correct the SPEC §6 sentence that says the preset sets 120 W.
- D22. Spot axis: the caller normalizes it. The pyi comment on `add_sphere(spot=...)` says "axis: unit vector"; T5.3
  normalizes.
- D23. `material_index` → `np.int32`, reshaped to the pyi shapes (V,3), (T,3), (T,3,3) (sweep 3.6, 3.7). Fix plan.md
  as well.
- D24. One source of reference knobs:
  - `apply_reference_knobs()` returns the cited dict of smallpaint-unit knobs (`diffuse_gain` float32(0.1),
    `emission_gain` 2, `ray_epsilon` float32(1e-4), `max_depth` 20, `spiral_frame` "smallpaint"). It is defined in M3 in
    `tests/core/scenes.py` and moves to `addon/sync/reference.py` in T4.3.
  - `build_smallpaint_scene` calls it, and `ORACLE_EXACT_KNOBS` derives from it.
  - `jitter` stays at the socket default, and the oracle gets `--jitter repr(2 * float(np.float32(jitter)))`.
- D25. T3.17 compares the triangle scene with the analytic scene on
  `metrics.realization_free_key_family(metrics.diffuse_key_family(keys))`. Embree's float32 hits can shift K, and
  `k_consumed` equality is reported, not asserted.
- D26. T3.18 (throughput):
  - H1 uses `chain=row` (the default) and also reports `lane:16`.
  - Pre-registered rule: throughput at T threads is greater than at T/2 in all 3 repeats (T = 2, 4). The speedups are
    reported, with no threshold.
  - H3 projects 1920×1080 × 1024 passes (the default `passes`) with `chain=row` and 4 threads.
- D27. The remaining thresholds:
  - cancel latency (T3.14): record, no threshold;
  - mesh export time (T5.2): record and report, assert only the triangle count;
  - T5.1 corner rays: within float32 round-off of `view_frame`, with the bound derived in a comment.
- D28. docs/plan.md:
  - add one line under "Milestones and Haiku task DAG": "Card IDs and contents in `docs/tasks/` supersede these tables
    (2026-10-09)";
  - fix the stale paths and names the sweep lists (2.11, 3.23, 1.6).
- D29. CLAUDE.md rule 3: "`ccl_device*` qualifiers in `src/painterly/kernel/`".

## Added after the first pass (2026-10-09)
- D30. docs/plan.md experiments table, X-throughput: "time for 1080p × 256 spp" becomes "time for 1920×1080 × 1024 passes
  (the default `passes`, `chain=row`)". This matches D26.
- D31. THIRD_PARTY_NOTICES.md Embree row: "linked statically into `_painterly` through `cmake/painterly_embree.cmake`
  (used by `src/blender/selftest.cpp`; from T3.10 also by `src/painterly/bvh/embree.{h,cpp}`)". The current tree has no
  `src/painterly/bvh/` yet.
- D32. Full licence texts of statically linked or vendored components live in `LICENSES/`, which the wheel ships through
  `license-files = ["LICENSE", "THIRD_PARTY_NOTICES.md", "LICENSES/*.txt"]` (fix-up card T2.9 creates the directory with
  nanobind's BSD-3-Clause and Embree's Apache-2.0 texts).
  - T3.2, which vendors sse2neon, also adds `LICENSES/MIT-sse2neon.txt`, the upstream licence text verbatim, and its
    THIRD_PARTY_NOTICES row.
  - The Cycles row says that `third_party/cycles/sse2neon/` is MIT, not Apache-2.0.

## Added after native first light (2026-10-10)
- D33. Zero-length diffuse direction (found by the first-light parity run, confirmed by two independent instrumented probes).
  - Mechanism: vdc(K) = 0 exactly at K ≡ 0 mod 2^23, so u1 = u2 = 0 and s = F·(1,0,0). On a surface with N = −F·(1,0,0)
    exactly, d = N + F·s = 0, and the SPEC §4 rescale d·|d|^(−α) is 0·inf = NaN for α > 0.
  - Seen in alpha_025/05/1 image-chain renders: 3/7/5 NaN pixels, identical bits in the core and `oracle --halton exact`.
    Cached incremental renders have none, because incremental never returns exactly 0 (SPEC §2).
  - Production reach: a row chain crosses multiples of 2^23 once width × passes × mean diffuse depth exceeds about 2^22
    (for example 1920 px × 1024 passes). With spiral_frame=world, a wall whose normal is exactly (−1,0,0) triggers it.
  - Decision: the rescale of the zero vector is the zero vector. SPEC §4 gains "if d = 0, d stays 0 (pow is not
    evaluated); then cost = 0 and the bounce contributes nothing; the path continues as for α = 0". α = 0 is
    bit-identical everywhere (pow(0, −0) = 1 already), and only the NaN events change.
  - Rejected alternative: ending the path at d = 0. It changes K consumption for every α = 0 exact render and
    invalidates existing parity references, for no visible gain.
  - Applies to the core (painterly_diffuse_bounce) and to the oracle in both Halton modes (CHANGES.md entry). Acceptance:
    - cached incremental renders stay byte-identical;
    - alpha_025/05/1 image chains at 400 px have 0 NaN and native == oracle-exact bit for bit;
    - a unit test at K = 2^23 − 1, N = (−1,0,0), F = I, α ∈ {0, 0.25, 0.5, 1} returns d = 0 and cost 0.
- D14 (amended 2026-10-10). The vertex kinds are `VERTEX_DIFFUSE = 0, VERTEX_TINT = 1, VERTEX_END = 2`. TQ.1 renamed
  VERTEX_PASS, because "pass" is reserved vocabulary (SPEC §0). The T3.11 card keeps the old name as a historical record.
- D34. M3 fix-up batch, before run 3b. Cards T3.19-T3.29 run in this order, all sequential in the main tree:
  - T3.19 zero-length diffuse direction (D33);
  - T3.20 scheduler robustness (TQ.1-1);
  - T3.21 contract touch-ups (Opus; TQ.1-6, D35, D36);
  - T3.22 build hygiene (TQ.1-2 without F12);
  - T3.23 shared test scaffolding (TQ.1-3);
  - T3.24 kernel test coverage (TQ.1-4);
  - T3.25 self-describing oracle renders (TQ.1-5);
  - T3.26 analysis constants (TQ.1-7);
  - T3.27 vendor_sync from pinned git objects;
  - T3.28 licences, notices and docs;
  - T3.29 CI macOS C++ job.
  F12 (the selftest through painterly_bvh) moves into T3.15, which first links the engine layers into _painterly.
- D35. One normal matrix (TQ.1 F25), and no dead device data (panel #7).
  - `painterly/util/math_double3.h` (contract) gains `painterly_normal_matrix(const float object_to_world[12], double
    out[9])`: the double cofactor form of (A^-1)^T that embree.cpp computes today. It throws std::invalid_argument for
    det == 0; host code only, not ccl_device.
  - `KernelPainterlyObject` drops `float tfm[12]` and `float itfm[12]`, and gains `double normal_to_world[9]`, filled by
    the scene from painterly_normal_matrix.
  - embree.cpp uses the same function for Ng. triangle.h transforms corner normals with
    transform_direction_3x3(normal_to_world, n). Ng and the corner normals then use one bit-identical matrix.
  - `PainterlyGlobalsCPU::tri_vertices` is dropped. Embree keeps its own vertex copy, and no kernel code reads it.
  - T3.13's device_update text changes accordingly. No more "vertices expanded per triangle: 9 floats", and no "itfm with
    transform_inverse".
  - Layout constants are defined once in globals.h: `PAINTERLY_POINT_FLOATS = 3` (x, y, z) and
    `PAINTERLY_TRIANGLE_CORNERS = 3`. The corner-normal stride is their product. embree.cpp's private constants and
    triangle.h's literal 9 use them. camera.h's hand-indexed 3x4 reads use the shared 3x4 helpers in math_double3.h.
- D36. The Embree tolerance in test_bvh.cpp (TQ.1 F24). CLAUDE.md rule 2 (re-read 2026-10-10) allows float32 round-off
  "where the computation is float32 (Embree hits ...), with the bound derived in the comment".
  - F32_STEPS becomes a derived bound: Higham's γ_n for the float32 operations of Embree's robust (watertight, Woop et al.
    2013) ray-triangle test plus the float32 instance transform, citing the Embree 4.4.1 source lines counted.
  - Exactly representable dyadic cases are rejected as the sole basis: Embree's reciprocal paths differ by ISA (SSE, AVX2,
    NEON), so exactness would not be portable.
- D37. "pass" vocabulary (TQ.1 F26). The contracts say "object_id buffer" and "render pass" for output layers. SPEC §0
  gets the note: "pass alone always means a sample pass; Blender output layers are render passes".
- D38. Windows exports. architecture.md and plan.md state the per-OS rule: on Windows `_painterly` also exports the
  members of nanobind's two NB_EXPORT exception classes (T2.9).
- D39 (owner, 2026-10-10). macOS support is low priority. No new macOS-specific work: no macOS CI test job, and no
  macOS-only experiments or fixes.
  - The existing macOS wheel and coexist jobs in wheels.yml stay as they are, while they stay green.
  - A failure that occurs only on macOS is reported to the owner and does not block a milestone.
  - Card T3.29 therefore drops the ci.yml `macos` job (panel #2 is not taken up) and keeps only panel #4, the wheels.yml
    pull_request path filter. Its title and Goal change accordingly.
