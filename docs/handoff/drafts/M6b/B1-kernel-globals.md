# B1 — Kernel globals and the build
Milestone: M6b · Depends on: T6.8 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B1" (lines 87-112) and its section 1 decisions 1 and 2
(lines 17-29), per that brief's section 4 (lines 303-324). Code facts are `docs/handoff/drafts/M6b/FACTS.md` §3,
re-read at this clone's HEAD in the files cited below.

## Goal
`PainterlyGlobalsCPU` carries Cycles' globals, and the build enforces the one kernel definition set:
- `PainterlyDeviceScene` owns a `KernelGlobalsCPU` (`src/cycles/shim/kernel/device/cpu/globals.h:49-57`), bound empty:
  zero shaders, zero objects, every one of the 53 arrays of `kernel/data_arrays.h` with width 0 and a null pointer, and
  `kernel_data.max_closures = MAX_CLOSURE` (BRIEF.md:89-90).
- `PainterlyGlobalsCPU::cycles` (CONTRACT `src/painterly/kernel/globals.h`) points at it, so the kernel passes
  `kg->cycles` wherever Cycles code takes `KernelGlobals` (BRIEF.md:17-22). The session's by-value snapshot of
  `globals()` copies only the pointer, and it stays valid because the device scene is never updated during a render
  (`src/painterly/session/session.cpp:55` updates on the caller thread, `:166` takes the snapshot).
- `painterly_kernel` links `cycles_svm`, and `painterly_scene` links `cycles_scene` (BRIEF.md:23-29), so every target
  whose sources include a Cycles `kernel/` header gets `cycles_kernel`'s definition set and its INTERFACE
  `-fno-strict-aliasing` (`src/cycles/CMakeLists.txt:101-103,146-148`).
- The first production consumer adds the layout record that T6.1:599-600 provides for: one function in `painterly_scene`
  returning `painterly_kernel_layout_record()` (`src/test/cycles_kernel_layout_probe.h:46-144`), and one comparison in
  `src/test/test_cycles_kernel_layout.cpp`.
- TQ.4 F3 (`docs/audits/TQ.4.md:45`): `__MAX_CLOSURE__` moves from `cycles_kernel` to `cycles_util`, the target that
  puts `third_party/cycles` on every include path, so seeing `kernel/types.h` implies the one value; the layout-skew
  canary becomes a `WILL_FAIL` ctest.
- TQ.4 F6(c) (`docs/audits/TQ.4.md:48`): `ccl=painterly` stops being PUBLIC on `cycles_scene`
  (`src/cycles/CMakeLists.txt:179`) and is defined only for the targets whose sources include the one file that needs
  the bare token, `third_party/cycles/scene/shader_nodes.h:992`.
- TQ.4 F11 (`docs/audits/TQ.4.md:53`): the module calls `painterly_cycles_shader_node_types()` once under
  `std::call_once` before any `NodeType::find`, and the registry header says what that call does.

Nothing renders differently: the new member is a pointer into the device scene, the empty `KernelGlobalsCPU` is read by
nothing yet, and the build changes add no library to the module's link line. T3.16's bit-identical parity is the check.

## Read first
- `CLAUDE.md` rules 1, 2 and 3; `AGENTS.md` "Expected values are evidence"; `docs/architecture.md:57-70` ("Dependency
  direction": `painterly_kernel` is the INTERFACE target every consumer of `painterly/kernel/` links, and
  `PainterlyScene::device_update()` is the only bridge).
- `docs/handoff/drafts/M6b/BRIEF.md` lines 15-29 (decisions 1 and 2) and 87-112 (this card's mandate).
- The CONTRACT header `src/painterly/kernel/globals.h` (read it, never edit it: `:4` is `CONTRACT: Opus-owned`):
  `PainterlyGlobalsCPU` `:40-68`, `using PainterlyGlobals` `:70`.
- The shim `src/cycles/shim/kernel/device/cpu/globals.h`: `kernel_array` `:31-45`, `KernelGlobalsCPU` `:49-57`,
  `KernelGlobals` `:59`, the `#error` `:24-26`, the `kernel_data_*` macros `:62-65`.
- `third_party/cycles/kernel/data_arrays.h` (53 `KERNEL_DATA_ARRAY*` invocations; `:99-100` undefine both macros) and
  `third_party/cycles/kernel/types.h:829-833` (`MAX_CLOSURE` falls back to 64 without `__MAX_CLOSURE__`).
- `src/painterly/scene/device_scene.h` (`:23-67`) and `src/painterly/scene/device_scene.cpp` (`:68-85` `bind_globals`,
  `:87-90` `globals()`, `:92-304` `device_update` with the strong guarantee `:94-97` and the commit `:289-303`).
- `src/painterly/kernel/CMakeLists.txt` (`:7-8`), `src/painterly/scene/CMakeLists.txt` (`:6-14`),
  `src/painterly/bvh/CMakeLists.txt` (`:3-5`: `painterly_bvh` links `cycles_util` PUBLIC and `painterly_embree` PRIVATE).
- `src/cycles/CMakeLists.txt`: `cycles_util` `:9-16` and its PUBLIC definitions `:30-32`; the `PAINTERLY_MAX_CLOSURE`
  cache knob and `cycles_kernel` `:92-103`; the aliasing flag `:146-148`; `cycles_svm` `:128-132`; `cycles_scene`
  `:170-176` and `ccl=painterly` `:179`.
- `src/test/CMakeLists.txt` (`:65` `add_test`, `:67-77` the layout probe and its option), `src/test/test_cycles_kernel_layout.cpp`,
  `src/test/cycles_kernel_layout_probe.h:146-147`.
- `src/blender/python.cpp` (includes `:11-38`, `bind_module` `:682`, `NB_MODULE` `:1001`) and
  `src/cycles/shader_node_registry.h:6-13,24`; `third_party/cycles/graph/node_type.h:157-176` and
  `graph/node_type.cpp:245-259` (why the call is needed and why it races on a concurrent first call).
- `src/painterly/scene/svm/shader_manager.h:31` (it includes `scene/shader_nodes.h`) and `src/cycles/shim/scene/shader.cpp:18`
  (a `cycles_scene` source that does), with `third_party/cycles/scene/shader_nodes.h:992` (the one `ccl::` token).
- `docs/handoff/drafts/M6a/T6.1-vendor-kernel-types.md`: "Definition set" `:60-86` (the table `:68-73`, and "Nothing enforces
  this rule" `:80`), the measured sizes and the skewed build `:87-91`, and `:599-600` (the layout record a later library may add).
  `T6.3-svm-stack-nodes.md:1559-1560` (`-fno-strict-aliasing` is INTERFACE on `cycles_kernel`).
- `docs/audits/TQ.4.md` findings F3 `:45`, F6(c) `:48` and F11 `:53`, with their `Evidence` columns.
- The two parity tests this card must keep green unchanged: `tests/core/test_oracle_parity.py` and
  `tests/core/test_triangle_path.py`.

## Create
- `src/painterly/scene/kernel_layout.h`
- `src/painterly/scene/kernel_layout.cpp`
- `src/test/test_cycles_globals.cpp`
- `tests/core/test_cycles_globals_build.py`

## Modify
- `src/painterly/scene/device_scene.h`: include `kernel/globals.h`; the member `KernelGlobalsCPU cycles_`; the accessor
  `const KernelGlobalsCPU &cycles_globals() const`; the constructor that binds the device scene empty; the class comment.
- `src/painterly/scene/device_scene.cpp`: define the constructor; keep `bind_globals()` as it is (it already stores
  `globals_.data` and the arrays; the `cycles` pointer is set once, in the constructor).
- `src/painterly/scene/CMakeLists.txt`: `kernel_layout.cpp` in the sources; link `cycles_scene`; define `ccl=painterly`
  PRIVATE; add `${PROJECT_SOURCE_DIR}/src/test` PRIVATE for the layout probe header; the comment.
- `src/painterly/kernel/CMakeLists.txt`: `target_link_libraries(painterly_kernel INTERFACE painterly_bvh cycles_util
  cycles_svm)` and the comment that says why (BRIEF.md:23-29).
- `src/cycles/CMakeLists.txt`: move the `PAINTERLY_MAX_CLOSURE` cache knob above `cycles_util` and add
  `__MAX_CLOSURE__=${PAINTERLY_MAX_CLOSURE}` to `cycles_util`'s PUBLIC definitions (`:30-32`); drop it from
  `cycles_kernel` (`:103`) and say so in that block's comment; make `ccl=painterly` PRIVATE on `cycles_scene` (`:179`).
- `src/cycles/shader_node_registry.h`: reword the header comment `:6-13` (TQ.4 F11).
- `src/test/CMakeLists.txt`: `test_cycles_globals.cpp` in `painterly_tests`; `ccl=painterly` PRIVATE on
  `painterly_tests`; the `WILL_FAIL` ctest under the existing `PAINTERLY_TEST_LAYOUT_SKEW` option (`:69-75`).
- `src/test/test_cycles_kernel_layout.cpp`: include `painterly/scene/kernel_layout.h` and add one comparison.
- `src/blender/python.cpp`: `#include <mutex>`, `#include "cycles/shader_node_registry.h"`, and the `std::call_once`
  call at the top of `bind_module` (`:682`).

## Do not touch
- `src/painterly/kernel/globals.h` (CONTRACT, `:4`): the member is Opus's and arrives before dispatch (see `## Interface`).
  `src/painterly/kernel/types.h` and `src/blender/_painterly.pyi` are CONTRACT files of B2, B3, B4 and B6.
- `third_party/cycles/**` (vendored; `tools/vendor_sync.py` only) and `src/cycles/shim/**`. TQ.4 F3's alternative of
  shimming `kernel/device/cpu/compat.h` is not taken here.
- `src/test/cycles_kernel_layout_probe.h`, `src/test/cycles_kernel_layout_probe.cpp` (T6.1's; the record is used as it is).
- `src/painterly/scene/svm/shader_manager.h` (B2 moves it into `painterly_scene`), `src/cycles/svm_nodes.toml`,
  `src/cycles/fragment_units.toml`.
- `tests/core/test_oracle_parity.py`, `tests/core/test_triangle_path.py`: they must pass unchanged, so not one line of
  either may move.
- `docs/architecture.md` (TQ.4 F8 is M6a-FIX-TQ4c's), `Makefile`, `pyproject.toml`, `.github/workflows/**`.

## Interface
CONTRACT (Opus writes this before dispatch): `src/painterly/kernel/globals.h` gains one member of `PainterlyGlobalsCPU`,
exactly as BRIEF.md:104 gives it:

    const KernelGlobalsCPU *PainterlyGlobalsCPU::cycles

The member is a pointer, so the header needs `KernelGlobalsCPU` declared and not defined: a forward declaration is
enough, and `#include "kernel/globals.h"` also works. Which one, the default and the comment are Opus's; this card's code
works with either, because `PainterlyDeviceScene` writes the pointer itself and `globals_{}` value-initialises it.
If the CONTRACT header does include `kernel/globals.h`, then every translation unit that includes
`painterly/kernel/globals.h` reaches the shim `#error` — among them `src/painterly/bvh/embree.h:45`, which
`painterly_bvh`'s `embree.cpp` includes, and `_painterly` through `src/blender/selftest.cpp:12-13`. Step 7 is what gives
those targets `__MAX_CLOSURE__` (TQ.4 F3, `docs/audits/TQ.4.md:45`).

Not a CONTRACT: `src/painterly/scene/device_scene.h` gains

    /* The Cycles globals this device scene owns and binds empty (BRIEF.md section 1, decision 1). Valid while this
     * object lives; the arrays it points at are the device scene's own (empty until B2 and B3 fill them). */
    const KernelGlobalsCPU &cycles_globals() const;

and `src/painterly/scene/kernel_layout.h` declares

    /* The kernel layout that this library's translation units compile (T6.1, "Definition set"): the second record
     * that test_cycles_kernel_layout.cpp compares with painterly_tests' own. */
    PainterlyKernelLayout painterly_scene_kernel_layout();

Both are new names; no other card depends on more than these two.

## Steps
1. Preconditions. Each must hold; otherwise stop, commit nothing and report what you saw.
   - The tree is the one this card was written against: `grep -c 'target_compile_definitions(cycles_scene PUBLIC ccl=painterly)' src/cycles/CMakeLists.txt` prints `1`, and `grep -c 'target_compile_definitions(cycles_kernel INTERFACE __MAX_CLOSURE__=${PAINTERLY_MAX_CLOSURE})' src/cycles/CMakeLists.txt` prints `1`.
   - No production target links Cycles' scene or SVM libraries yet. `grep -c 'cycles_svm' src/painterly/kernel/CMakeLists.txt` prints `0`, and `grep -c 'cycles_scene' src/painterly/scene/CMakeLists.txt` prints `0`.
   - `grep -c 'add_test' src/test/CMakeLists.txt` prints `1` (only `painterly_tests`, `:65`), so the skew test this card
     registers is the second ctest test and only under the option.
   - The array count the doctest walks: this prints `53` (51 `KERNEL_DATA_ARRAY` and 2 `KERNEL_DATA_ARRAY_WRITABLE`
     invocations of `kernel/data_arrays.h`):
     ```
     grep -cE '^KERNEL_DATA_ARRAY(_WRITABLE)?\(' third_party/cycles/kernel/data_arrays.h
     ```
   - The CONTRACT member of `## Interface` is present. This prints `1`:
     ```
     grep -c 'KernelGlobalsCPU \*cycles' src/painterly/kernel/globals.h
     ```
     If it prints `0`, the contract has not arrived: stop and report (CLAUDE.md rule 1; the member is Opus's).
2. `src/painterly/scene/device_scene.h`: add `#include "kernel/globals.h"` after the two painterly includes, and in
   `PainterlyDeviceScene`:
   - the public accessor of `## Interface`;
   - replace `PainterlyDeviceScene() = default;` (`:25`) with a declaration, `PainterlyDeviceScene();`;
   - the private member `KernelGlobalsCPU cycles_{};` next to `globals_` (`:66`), with the comment that this object owns
     it and every array it will point at;
   - extend the class comment (`:6-10`) with the `KernelGlobalsCPU` it now owns.
3. `src/painterly/scene/device_scene.cpp`, next to `~PainterlyDeviceScene` (`:47-50`):
   ```cpp
   /* Binds the device scene empty (BRIEF.md section 2, "B1"): zero shaders and zero objects, so every array of
    * kernel/data_arrays.h has width 0 and a null pointer (KernelGlobalsCPU's kernel_array defaults,
    * src/cycles/shim/kernel/device/cpu/globals.h:31-45), and KernelData has Cycles' closure budget. B2 and B3 fill the
    * arrays; the pointer never changes, so a device_update that throws cannot leave it dangling. */
   PainterlyDeviceScene::PainterlyDeviceScene()
   {
     cycles_.data.max_closures = MAX_CLOSURE;
     globals_.cycles = &cycles_;
   }
   ```
   `MAX_CLOSURE` is `kernel/types.h:829-833`, i.e. `__MAX_CLOSURE__`, the same value `collect.h:17-18` tells the caller to
   start `num_closure_left` from. Leave `bind_globals()` (`:68-85`) unchanged; it does not touch `cycles`.
   `const KernelGlobalsCPU &PainterlyDeviceScene::cycles_globals() const` returns `cycles_` and goes beside `globals()`
   (`:87-90`).
4. `src/painterly/scene/kernel_layout.h` and `kernel_layout.cpp` (the SPDX header of `src/test/test_cpp_file_headers.py`
   requires it in `src/test/` and `src/blender/` only, but every file in `src/painterly/` has it too):
   ```cpp
   /* kernel_layout.cpp */
   #include "painterly/scene/kernel_layout.h"

   /* T6.1:599-600: a library that compiles kernel headers may add one function returning
    * painterly_kernel_layout_record(), so that test_cycles_kernel_layout.cpp compares this library's translation units
    * with painterly_tests' own. The header is under src/test/ and is included by path, as T6.1 wrote it. */
   #include "cycles_kernel_layout_probe.h"

   CCL_NAMESPACE_BEGIN

   PainterlyKernelLayout painterly_scene_kernel_layout()
   {
     return painterly_kernel_layout_record();
   }

   CCL_NAMESPACE_END
   ```
   `painterly_kernel_layout_record()` is `static inline` on purpose (`cycles_kernel_layout_probe.h:43-46`): this
   translation unit records its own layout, which is the point of the comparison.
5. `src/painterly/scene/CMakeLists.txt`: add `kernel_layout.cpp` to `add_library(painterly_scene STATIC ...)` (`:6-12`);
   `target_link_libraries(painterly_scene PUBLIC cycles_graph cycles_scene painterly_kernel painterly_bvh)`; and, with a
   comment that names T6.1:599-600,
   `target_include_directories(painterly_scene PRIVATE ${PROJECT_SOURCE_DIR}/src/test)`.
   - `cycles_graph` stays: `cycles_scene` links it PUBLIC too, and a repeated static archive on a link line resolves
     nothing new on the second scan.
   - `ccl=painterly` PRIVATE on `painterly_scene` (step 8's F6(c) work): its `svm/shader_manager.h:31` includes
     `scene/shader_nodes.h`, and B2 makes that header a source of this library.
   - `kernel_layout.cpp` includes `kernel/globals.h` and `kernel/types.h` through the probe header, so it needs the
     definition set: it gets it through `painterly_kernel` → `cycles_svm` → `cycles_kernel` (step 6) and `cycles_util`
     (step 7). Build only after both, or the shim's `#error` at
     `src/cycles/shim/kernel/device/cpu/globals.h:24-26` stops the compile — which is the rule working.
6. `src/painterly/kernel/CMakeLists.txt`: `target_link_libraries(painterly_kernel INTERFACE painterly_bvh cycles_util
   cycles_svm)`, and extend the comment with BRIEF.md:23-29: `cycles_svm` links `cycles_kernel`, so every consumer of
   `painterly/kernel/` now gets the definition set and the INTERFACE `-fno-strict-aliasing` (`src/cycles/CMakeLists.txt:132,146-148`).
   - `cycles_svm` is INTERFACE and header-only, so the module's link line gains no library; it does gain the generated
     `svm_eval_nodes.h` include directory and the generator's build order (`src/cycles/CMakeLists.txt:116-132`).
7. `src/cycles/CMakeLists.txt`, TQ.4 F3 (`docs/audits/TQ.4.md:45`): take its first option.
   - Move the `PAINTERLY_MAX_CLOSURE` cache knob with its validation and comment (`:92-100`) above the `cycles_util`
     block (`:9`), and add `"__MAX_CLOSURE__=${PAINTERLY_MAX_CLOSURE}"` to `cycles_util`'s `target_compile_definitions(... PUBLIC ...)`
     (`:30-32`). That target is what puts `third_party/cycles` on every include path (`:25-27`), so a source that can see
     `kernel/types.h` now always sees the same value; without this, `kernel/types.h:829-830` silently falls back to 64,
     which is the second `ShaderData` T6.1:80-85 describes.
   - Delete the definition from `cycles_kernel` (`:103`) and say in that block's comment that the definition set now comes
     through `cycles_util`, which `cycles_kernel` links (`:102`). `-fno-strict-aliasing` (`:146-148`) stays on
     `cycles_kernel`.
   - Nothing else in the definition set moves: `__KERNEL_FEATURES__`, `WITH_EMBREE`, `WITH_OSL` and `WITH_PATH_GUIDING`
     stay undefined (T6.1 "Definition set").
8. `src/cycles/CMakeLists.txt:177-179`, TQ.4 F6(c): `target_compile_definitions(cycles_scene PRIVATE ccl=painterly)`.
   The only file that needs the token is `third_party/cycles/scene/shader_nodes.h:992` (`ccl::BsdfBaseNode`), and of the
   seven files that include it — `third_party/cycles/scene/shader_graph.cpp:10` and `src/cycles/shim/scene/shader.cpp:18`
   (both `cycles_scene` sources), `src/painterly/scene/svm/shader_manager.h:31`, and the four test sources of
   `src/test/CMakeLists.txt:84,88,91,95` — the two `cycles_scene` ones are covered PRIVATE here, `painterly_scene` and
   `painterly_tests` by steps 5 and 9. `_painterly` includes none of them and inherits nothing.
9. `src/test/CMakeLists.txt`:
   - `target_sources(painterly_tests PRIVATE test_cycles_globals.cpp)` beside the T6.1 block (`:76`);
   - `target_compile_definitions(painterly_tests PRIVATE ccl=painterly)` with a comment naming step 8 (four of its
     sources include `scene/shader_nodes.h`);
   - inside the existing `if(PAINTERLY_TEST_LAYOUT_SKEW)` (`:73-75`):
     ```cmake
     # TQ.4 F3: the skew canary must be able to fail, so it is a ctest test that must fail. With
     # __KERNEL_FEATURES__=0 the probe's ShaderData is 6384 bytes against 6480 (T6.1:87-91), so the doctest exits 1 and
     # WILL_FAIL turns that into a pass; a neutered comparison would make this ctest fail.
     add_test(NAME painterly_layout_skew
              COMMAND painterly_tests "--test-case=cycles kernel layout: two translation units agree")
     set_tests_properties(painterly_layout_skew PROPERTIES WILL_FAIL TRUE)
     ```
10. `src/test/test_cycles_kernel_layout.cpp`: `#include "painterly/scene/kernel_layout.h"` and, at the end of the first
    test case after `CHECK(here == probe);` (`:39`), one line:
    `CHECK(here == painterly_scene_kernel_layout());` — the same record, from a translation unit of `painterly_scene`.
11. `src/test/test_cycles_globals.cpp`, the doctest `## Acceptance` counts:
    ```cpp
    /* SPDX-FileCopyrightText: 2026 The Painterly Authors
     * SPDX-License-Identifier: GPL-3.0-or-later */

    // B1: the empty Cycles KernelGlobalsCPU that PainterlyDeviceScene owns, and the pointer to it that
    // PainterlyGlobalsCPU carries (BRIEF.md section 2, "B1"; docs/audits/TQ.4.md F3).

    #include "painterly/scene/device_scene.h"
    #include "painterly/scene/scene.h"

    #include <doctest/doctest.h>

    CCL_NAMESPACE_BEGIN

    namespace {

    /* True when the globals are bound empty: every array of kernel/data_arrays.h with width 0 and no data. */
    void check_arrays_are_empty(const KernelGlobalsCPU &cycles)
    {
    #define KERNEL_DATA_ARRAY(type, name)      \
      CHECK(cycles.name.width == 0);           \
      CHECK(cycles.name.data == nullptr);
    #define KERNEL_DATA_ARRAY_WRITABLE(type, name) KERNEL_DATA_ARRAY(type, name)
    #include "kernel/data_arrays.h"
    }

    }  // namespace

    TEST_CASE("cycles kernel globals: a fresh device scene is bound empty")
    {
      PainterlyDeviceScene ds;
      const PainterlyGlobalsCPU globals = ds.globals();

      CHECK(globals.cycles == &ds.cycles_globals());
      CHECK(ds.cycles_globals().data.max_closures == MAX_CLOSURE);
      check_arrays_are_empty(ds.cycles_globals());
    }

    TEST_CASE("cycles kernel globals: a device-updated scene keeps the binding")
    {
      PainterlyScene scene;
      KernelPainterlyLobe lobe{};
      lobe.kind = LOBE_DIFFUSE;
      lobe.weight = make_double3(1.0);
      const int material = scene.add_material({lobe}, make_double3(0.0));
      scene.add_plane(make_double3(0.0, 0.0, 1.0), 1.0, material, -1);

      PainterlyDeviceScene ds;
      scene.device_update(ds);
      const PainterlyGlobalsCPU globals = ds.globals();

      /* Decision 1: the pointer into the device scene survives the by-value snapshot the session takes. */
      CHECK(globals.cycles == &ds.cycles_globals());
      CHECK(globals.cycles->data.max_closures == MAX_CLOSURE);
      CHECK(globals.data == &ds.data);
      check_arrays_are_empty(ds.cycles_globals());
    }

    CCL_NAMESPACE_END
    ```
    The `#include "kernel/data_arrays.h"` inside the function is the pattern `src/test/test_cycles_kernel_types.cpp:25-30`
    uses, and the header undefines both macros itself (`:99-100`). `make_double3` is `painterly/util/types_double3.h`,
    reached through `painterly/kernel/types.h`.
12. `src/blender/python.cpp`, TQ.4 F11:
    - `#include <mutex>` in the standard block (`:18-28`) and `#include "cycles/shader_node_registry.h"` after the
      painterly includes (`:30-38`);
    - at the top of `bind_module` (`:682`), before the first `m.def`:
      ```cpp
      /* Cycles' shader node registry (TQ.4 F11): built once, on the importing thread, before any NodeType::find. The
       * vendored getter reads its cache outside its lock (graph/node_type.h:166-175), so a concurrent first call is a
       * race; this call is the one that fills it. */
      static std::once_flag cycles_shader_node_types_once;
      std::call_once(cycles_shader_node_types_once, [] { painterly_cycles_shader_node_types(); });
      ```
      `_painterly` reaches the symbol through `painterly_session` → `painterly_scene` → `cycles_scene` (step 5), and the
      include directory `src` through `cycles_util` (`src/cycles/CMakeLists.txt:27`).
13. `src/cycles/shader_node_registry.h:6-13`: reword the comment to what the call does. It must say that `NODE_DEFINE`
    only queues `X::get_node_type` with `NodeType::register_on_init` (`graph/node_type.h:157-176`,
    `graph/node_type.cpp:245-259`), that types are built lazily at the first `NodeType::find`, and that calling this
    function does two things: it keeps the `shader_nodes` unit in the static library, and it builds every type eagerly,
    once, which is why the module calls it under `std::call_once` before its first `NodeType::find`. Keep the declaration
    (`:24`) and the function's own comment unchanged.
14. `tests/core/test_cycles_globals_build.py`, two tests over `ninja -t commands`, with the `build_dir` fixture
    (`tests/conftest.py:31-34`) and `ninja` found next to `sys.executable` first and then on `PATH` (`make` puts the
    venv's `bin` there, `Makefile:10`):
    - `test_max_closure_reaches_a_cycles_util_consumer_without_cycles_kernel`: the command that compiles
      `src/painterly/bvh/CMakeFiles/painterly_bvh.dir/embree.cpp.o` contains `-D__MAX_CLOSURE__=64` and does not contain
      `-fno-strict-aliasing`. `painterly_bvh` links `cycles_util` only (`src/painterly/bvh/CMakeLists.txt:4`), so the
      definition can only come from `cycles_util` — the F3 rule made observable. The `64` is the knob's default
      (`src/cycles/CMakeLists.txt:96-97`), not a value of the test's: read it from `cmake -LA -N <build_dir>`'s
      `PAINTERLY_MAX_CLOSURE` entry, or build the expected string as `f"-D__MAX_CLOSURE__={knob}"`, so a build that sets
      the knob still passes.
    - `test_the_module_does_not_inherit_the_ccl_macro`: the command that compiles
      `src/blender/CMakeFiles/_painterly.dir/python.cpp.o` does not contain `-Dccl=painterly`, and the one for
      `src/painterly/scene/CMakeFiles/painterly_scene.dir/device_scene.cpp.o` does.
    Both assert the `ninja -t commands` output is non-empty first, so a renamed object path fails instead of passing
    vacuously.
15. `make format`, then every acceptance command.

## Acceptance
Run every command from the repository root; the queue translates them with BACKLOG.md's table (`make check` → `CHECK`,
`build/dev` → `build/q`, `.venv/bin/<tool>` → `MAIN/.venv/bin/<tool>`, `python -I` → `PYTHONPATH="$PWD/analysis" … -P -s`).
1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and the audit's
   `RESULT: PASS` line.
2. `make audit` prints `RESULT: PASS`: no new exported symbol and no new dependency (BRIEF.md:29). The two new libraries
   reach the module as static archives behind `-Wl,--version-script` (`src/blender/CMakeLists.txt:23-30`).
3. `build/dev/src/test/painterly_tests --test-case='cycles kernel globals*'` exits 0 and prints
   `test cases: 2 | 2 passed | 0 failed` — the two cases of step 11.
4. `build/dev/src/test/painterly_tests --test-case='cycles kernel layout*'` exits 0 and prints
   `test cases: 2 | 2 passed | 0 failed`: T6.1's two cases, with the added `painterly_scene_kernel_layout()` comparison.
5. `build/dev/src/test/painterly_tests --test-case='painterly scene: device_update keeps the device scene on every throwing path'`
   exits 0 and prints `test cases: 1 | 1 passed | 0 failed`: the strong guarantee of `device_scene.cpp:94-97` still holds
   with the new member.
6. The skew canary, as a `WILL_FAIL` ctest, exits 0 and prints `100% tests passed, 0 tests failed out of 1`:
   ```
   (
     set -e
     export PATH="$PWD/.venv/bin:$PATH"
     # CMAKE_ARGS holds exactly the string the CHECK run gave make's CMAKE_ARGS knob, so the configure finds the same
     # Embree and doctest sources (and the same prebuilt Embree) and needs no network. The Makefile stages a read-only
     # source tree itself, so point the two -DFETCHCONTENT_SOURCE_DIR_* options at the staged copies under
     # build/q/_deps-src/ when the knob named a read-only directory (`Makefile:28-30`, `:46`).
     cmake -S . -B build/skew -G Ninja -DCMAKE_BUILD_TYPE=Release -DPython_EXECUTABLE="$PWD/.venv/bin/python" \
       -DPAINTERLY_BUILD_MODULE=OFF -DPAINTERLY_BUILD_ORACLE=OFF -DPAINTERLY_TEST_LAYOUT_SKEW=ON $CMAKE_ARGS
     cmake --build build/skew --target painterly_tests
     ctest --test-dir build/skew -R '^painterly_layout_skew$' --output-on-failure
     rm -rf build/skew
   )
   ```
   - `PAINTERLY_BUILD_MODULE=OFF` and `PAINTERLY_BUILD_ORACLE=OFF` keep the second configure to `painterly_tests` and its
     dependencies; the skew is a property of the probe library (`src/test/CMakeLists.txt:73-75`), which only the tests link.
   - `WILL_FAIL` means ctest passes only when the doctest exits non-zero. T6.1 measured the skew: `ShaderData` 6384 bytes
     against 6480, `features` 4576 against 511 (`docs/handoff/drafts/M6a/T6.1-vendor-kernel-types.md:87-91`), so the
     `shader_data_size` and `features` checks fail.
   - In the normal build the option is OFF, so `ctest --test-dir build/q` still prints `out of 1` (only
     `painterly_tests`, `src/test/CMakeLists.txt:65`).
7. `build/dev/src/test/painterly_tests --test-case='cycles kernel types*'` exits 0 with `test cases: 2 | 2 passed | 0 failed`:
   the 53-array `static_assert` of `src/test/test_cycles_kernel_types.cpp:25-30` still holds, so the shim still declares
   every array.
8. `.venv/bin/python -m pytest -q tests/core/test_cycles_globals_build.py` prints `2 passed`.
9. `.venv/bin/python -m pytest -q -m slow tests/core/test_oracle_parity.py tests/core/test_triangle_path.py` prints
   `2 passed, 53 deselected`: the two slow tests, unchanged. The counts are the files' own:
   `test_oracle_parity.py` holds 3 unparametrized tests (`:125`, `:138`, `:162`), the 12 `DESIGN` entries (`:74-87`) ×
   the 4 `CORE_CONFIGS` (`:91-96`) = 48 parametrized items, and 1 slow test (`:366-367`), so 52 items;
   `test_triangle_path.py` holds `:156`, `:183` and the slow `:272-273`, so 3. 52 + 3 = 55 items, of which 2 are
   `slow`, so the `-m slow` run selects 2 and reports `55 - 2 = 53` deselected.
10. `git status --porcelain` lists only the four Create paths and the nine Modify paths above.

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- delete `globals_.cycles = &cycles_;` → acceptance 3 fails;
- `cycles_.data.max_closures = 0` → acceptance 3 fails on the `max_closures` CHECK;
- `PUBLIC ccl=painterly` on `cycles_scene` again → `test_the_module_does_not_inherit_the_ccl_macro` fails;
- `__MAX_CLOSURE__` back on `cycles_kernel` only → `test_max_closure_reaches_a_cycles_util_consumer_without_cycles_kernel`
  fails;
- drop `WILL_FAIL` from the ctest properties → acceptance 6 fails (`100% tests passed` becomes `0% tests passed`);
- neuter the added comparison in `test_cycles_kernel_layout.cpp` (`CHECK(true)`) → the skew ctest fails, which is
  exactly what F3 says the canary is for.

Report: the doctest and pytest counts, the audit line, the skew ctest's output, and every mutation you ran with its
first failing check.

## Commit
`B1: kernel globals and the build`

## Open for Opus
1. **The layout record makes a production library include a test header.** T6.1:599-600 put
   `painterly_kernel_layout_record()` in `src/test/cycles_kernel_layout_probe.h`, and this card's step 4 includes it from
   `src/painterly/scene/kernel_layout.cpp` with `src/test` as a PRIVATE include directory. The options: (a) keep it (the
   wheel builds compile the header, which exists in the source tree); (b) move the probe header and its `.cpp` under
   `src/painterly/kernel/` in a later card, which changes two of T6.1's files and `test_cycles_kernel_layout.cpp`'s
   include. This card takes (a) and names it.
2. **`__MAX_CLOSURE__` moves off `cycles_kernel`.** T6.1's "Definition set" table (`T6.1:65-73`) attaches the whole set to
   `cycles_kernel`, and step 7 leaves one macro of it on `cycles_util`, as TQ.4 F3's first option says
   (`docs/audits/TQ.4.md:45`). Consumers see no difference (`cycles_kernel` links `cycles_util` INTERFACE), and T6.1's
   prose then needs the correction. The alternative is to *add* the definition on `cycles_util` and keep the one on
   `cycles_kernel`: two identical `-D` flags, and T6.1's text stays true. This card takes the single definition.
3. **F3's residual hole.** With the definition on `cycles_util`, the rule holds for every target that reaches
   `third_party/cycles` through it, which is every target today (`tests/core/test_shims.py:79-82` keeps `src/` and
   `third_party/cycles/` free of a shared top-level directory). A future target that adds
   `${PAINTERLY_CYCLES_VENDOR}` to its own include path would escape it. TQ.4's second option — a check that every object
   whose depfile names `kernel/types.h` carries one `-D__MAX_CLOSURE__` — would close that; it needs
   `CMAKE_EXPORT_COMPILE_COMMANDS` or `ninja -t deps` and is not this card's.
4. **`max_closures` has two writers.** This card sets it once, in `PainterlyDeviceScene`'s constructor, as the "bound
   empty" invariant of BRIEF.md:89-90. B2's TQ.4 F4 work writes it again in `device_update_common`
   (`docs/handoff/drafts/M6b/BRIEF.md:123-126`), from the same `MAX_CLOSURE`. Both are idempotent; if Opus prefers one
   writer, the constructor's line goes and this card's doctest then reads the value after a `device_update`.
5. **Two line numbers of the brief are stale at this clone.** BRIEF.md:22 cites "session.cpp:54, :114" for the two
   places where the device scene is written and read; at this HEAD the calls are `src/painterly/session/session.cpp:55`
   (`scene_->device_update(device_scene_)`) and `:166` (`const PainterlyGlobalsCPU kg = device_scene_.globals();`), and
   `:114` is the `throw;` that closes `start()`'s rollback. `FACTS.md` §3.10 repeats the stale pair. The behaviour the
   brief states is unchanged (a device update on the caller thread, then one snapshot per `render()`), so this card
   cites the lines it read and changes no step.
6. **F11 has no test at B1.** Nothing in the module calls `NodeType::find` yet, so the `std::call_once` call is checked by
   its source line, by `make audit` and by the module importing cleanly (`tests/core/test_api_contract.py`). B6, the first
   Python path to a node graph, is where it becomes observable.
