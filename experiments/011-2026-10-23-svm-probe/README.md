# Experiment 011: do Cycles' stack-only SVM nodes run verbatim and give exactly the derived values through the generated switch? (svm-probe)

Pre-registered by Opus on 2026-10-09 in card T6.3. Run on 2026-10-23.

## Background

- `docs/plan.md`, "Experiments programme": X-svm asks whether vendored `graph/` and the SVM work with the shims, and what a
  node port costs (gate G2). Card T3.3 records the `graph/` half of G2. This experiment probes the SVM half on the first node
  set of milestone M6a: 35 node cases whose evaluators read only the stack, plus `kernel_data.film.rgb_to_y`
  (`NODE_CONVERT`, `NODE_CONVERT_DERIVATIVE`) or a table stored in the byte code (`NODE_RGB_RAMP`, `NODE_CURVES`,
  `NODE_FLOAT_CURVE`).
- M6a design (Opus decision, 2026-10-09; cards T6.1-T6.3): Cycles' SVM headers are vendored verbatim by
  `tools/vendor_sync.py`, with no patches; shims live only under `src/cycles/shim/`; `svm_eval_nodes()` is generated from
  verbatim `SVM_CASE` fragments by `tools/gen_svm_switch.py`; one kernel definition set is attached to `cycles_kernel`.
- `svm_eval_nodes()` keeps its stack local (`kernel/svm/svm.h:109`). The probe observes the interpreter through the indices of
  the `svm_nodes` words it fetches (`src/test/cycles_svm_test_support.h`). `NODE_JUMP_IF_ZERO` turns a stack value into such a
  fetch.
- The fragments' text is pinned by sha256 (card T6.2). H2 therefore tests the interpreter frame and every case's word
  accounting, and H3 tests the values of six node types (`NODE_MATH`, `NODE_MIX`, `NODE_MIX_FLOAT`, `NODE_MAP_RANGE`,
  `NODE_RGB_RAMP`, `NODE_CONVERT`) and of `NODE_VALUE_F` and `NODE_VALUE_V`, which write their inputs.
- This experiment observes one compiler, the one of `make build` (`results.json`, `compiler`). Card T6.3 also adds
  `src/cycles/svm_headers_check.cpp` (OBJECT library `cycles_svm_headers_check`, in `ALL`), so that the wheel builds compile
  the 22 headers with MSVC and with Clang on macOS arm64. Where the branch has the MSVC `windows` job of
  `.github/workflows/ci.yml` (card T2.10), that job also runs the generator and these doctests. Those results come from CI
  once the M6a branch is pushed, outside this experiment.
- Blender compiles Cycles with `-fno-strict-aliasing` (v5.2.2 `build_files/cmake/platform/platform_unix.cmake:898`, `:970`;
  `platform_apple.cmake:161`), and `svm_node_get<T>` reads typed node structs through a cast of the `uint` byte code
  (`kernel/svm/util.h:204-213`). Card T6.3 attaches the same flag to `cycles_kernel` for GCC and Clang, so the probe
  compiles that read as upstream does.
- Experiments 001-006 concern the look and the native module's isolation. None touches the SVM.

## Hypothesis

Every observable is a count or an exact equality, so the decision rules have no tolerance and no statistical test, as in
experiment 005.

- **H1. The 22 vendored headers compile verbatim in namespace `painterly` with the compiler of `make build`, with no patch
  and no new shim.**
  - Derivation: the M6 research found that these evaluators read no `ShaderData` field, and besides the stack only
    `kernel_data.film.rgb_to_y` and `svm_nodes`. Opus's text-level scan of Blender v5.2.2 (every `#if` branch; a quoted
    include resolves against `intern/cycles`, then the includer's directory) gives the include closure of the 22 headers,
    followed through the shim `kernel/device/cpu/globals.h` instead of upstream's: 78 paths, i.e. the shim and 77 upstream
    files of 16,446 lines, with no unresolved include, and no file outside the sets of cards T3.2, T3.3 and T6.1 besides the
    22.
  - Observables (`probe.py`):
    - (a) the files in `third_party/cycles/patches/` other than `.gitkeep`;
    - (b) the exit status of `.venv/bin/python -I tools/vendor_sync.py check --upstream`;
    - (c) the output lines of `git status --porcelain --untracked-files=all -- src/cycles/shim`;
    - (d) the closure paths that are neither a `dest` in `third_party/cycles/VENDORED.toml` nor a file under
      `src/cycles/shim/`, and the unresolved includes;
    - (e) the exit status of `cmake --build <build>`. Its default target `all` builds `painterly_tests` (the generated
      switch and the doctests) and `cycles_svm_headers_check` (the 22 headers).
  - Decision: supported iff (a) is 0 files, (b) is 0, (c) is 0 lines, (d) are both empty and (e) is 0.
- **H2. The generated `svm_eval_nodes()` runs the frame as upstream and consumes exactly each case's words.**
  - Derivation: the loop fetches each type word (`kernel/svm/svm.h:115`); `svm_node_get<T>` fetches the first word of
    struct `T` and advances by `sizeof(T)/4` (`kernel/svm/util.h:204-213`); the table nodes fetch table words and skip their
    tables (`kernel/svm/ramp.h:14-154`); `NODE_SHADER_JUMP` selects an offset by shader type (`svm.h:120-136`), and
    `NODE_JUMP_IF_*` add `jump_offset` after their struct (`svm.h:177-192`). The fetch trace of each program is therefore
    fully determined by its layout.
  - Observables: the doctest test cases `cycles svm stack nodes: control flow` (11 assertions: 5 shader-jump runs and 6
    conditional-jump runs) and `cycles svm stack nodes: every stack node case dispatches` (105 assertions: 3 for each of 35
    cases).
  - Decision: supported iff they report 11 and 105 passed assertions and 0 failed.
- **H3. The nodes compute exactly the values derived in card T6.3 (IEEE `==`).**
  - Derivation: the inputs are dyadic rationals chosen so that every float32 operation on the evaluated path is exact, and
    `-ffp-contract=off` forbids fused operations, so each value equals its derivation exactly. Two kinds of reference are
    not dyadic: the C library's `powf` on the same float bits, which `compatible_powf` calls (`util/math_base.h:582`); and the
    host lookups of `kernel/svm/ramp_util.h`, which perform the same float32 operations in the same order as
    `kernel/svm/ramp.h`. The byte code is read as upstream compiles it, with `-fno-strict-aliasing` (Background). An in-VM
    check subtracts the expected value, which gives 0 iff the values are equal for finite floats. That is IEEE `==`:
    identical bits for a nonzero expected value, while `+0` and `-0` compare equal. Five expected values are zeros.
  - Observables: the test cases `math` (9 checks), `mix` (8), `map range` (4), `color ramp` (24) and `convert` (4), each
    named `cycles svm stack nodes: <name>`. Each has 3 assertions: the trace equals the expected trace, no other kernel array
    was fetched, and no check failed.
  - Decision: supported iff each of the five reports 3 passed assertions and 0 failed.
- **Measurements (no decision rule).**
  - M1, port cost: the manifest's cases and includes; the `svm_case` fragments and their total upstream lines; the vendored
    headers; the generated header's lines and sha256. Opus's prediction: 39 cases, 19 includes, 39 fragments of 174 lines,
    22 headers, 284 lines, sha256 `b86aad32d05591ea9b980f494465137ceb7eafe0f5b4c0172c47ed16b087d7d2`. Outside `src/test/`,
    card T6.3 adds only one C++ file, `src/cycles/svm_headers_check.cpp`, which includes the 22 headers and defines nothing.
    The repository records no wall-clock time per port, so the plan's "hours per node port" is reported as these counts.
  - M2, compile closure: the headers the compiler read for `test_cycles_svm_stack_nodes.cpp.o` (`ninja -t deps`): in total,
    under `third_party/cycles/` (count and lines), under `src/cycles/shim/`, and generated.
  - M3, compile time: the wall-clock seconds to rebuild that object, three times, and their median, with the compiler's
    version line.
- **Gate (X-svm, stack nodes).** It passes iff H1, H2 and H3 are supported. It covers the compiler of `make build` only;
  MSVC and macOS arm64 are CI's (Background).

## Method

1. `make env`, `.venv/bin/python -I tools/vendor_sync.py fetch`, then `make build` (CMake Release, Ninja, `build/q`).
2. From the repository root: `.venv/bin/python -I experiments/011-2026-10-23-svm-probe/probe.py`. It reads `PAINTERLY_BUILD_DIR`
   (default `build/q`), runs every instrument below, writes `results.json` next to itself, prints a summary, and exits 0
   iff the gate passes. It uses the standard library only. Its output is deterministic except the M3 times.
3. H1: (a)-(c) and (e) as stated; (b) runs `[sys.executable, "-I", "tools/vendor_sync.py", "check", "--upstream"]` from the
   repository root, because it reads the downloaded checkout (CLAUDE.md rule 5). (d) walks the closure of the 22 headers.
   A path that is a file under `src/cycles/shim/` is read from there; any other path is read from the upstream checkout
   `.cache/vendor/blender-v5.2.2/intern/cycles/`. Every line matching `^\s*#\s*include\s+"([^"]+)"` is followed; the include resolves to a shim path, then a path under the
   checkout root, then a path relative to the including file's directory; otherwise it is unresolved.
4. H2 and H3: `<build>/src/test/painterly_tests --test-case=<name>` once per test case, reading P and F (groups 2 and 3) with
   `re.search(r"^\[doctest\] assertions:\s+(\d+) \|\s+(\d+) passed \|\s+(\d+) failed", stdout, re.MULTILINE)`. doctest
   pads each count to the width of the largest one (`doctest.h:6264-6285`), so the line has no fixed text. A test case
   whose line is missing records P = 0 and F = 0, which fails its decision rule.
5. M1 from `src/cycles/svm_nodes.toml`, `third_party/cycles/VENDORED.toml` and `<build>/src/cycles/generated/svm_eval_nodes.h`.
   M2 from `ninja -C <build> -t deps src/test/CMakeFiles/painterly_tests.dir/test_cycles_svm_stack_nodes.cpp.o`, which lists
   one absolute path per line after its `#deps N` line. M2 counts every listed path, the source file, system headers and
   doctest included; the three subsets are the paths that start with `<repo>/third_party/cycles/`, with
   `<repo>/src/cycles/shim/` and with `<build>/src/cycles/generated/`, with `<repo>` and `<build>` absolute and resolved.
   M3 touches `src/test/test_cycles_svm_stack_nodes.cpp` and runs `ninja -C <build>` on that object, three times. The
   compiler is `CMAKE_CXX_COMPILER` from `<build>/CMakeCache.txt`; its version line is the first line of `--version`.

## Results

Every number below is from `results.json`, written by the one run of `probe.py` on 2026-10-23
(`"run_date": "2026-10-23"`), with `PAINTERLY_BUILD_DIR=build/q`. The compiler was
`c++ (Ubuntu 15.2.0-16ubuntu1) 15.2.0`.

**H1 — the 22 headers compile verbatim.**

| observable | value |
|---|---|
| (a) `patches` | 0 files |
| (b) `vendor_check_upstream_exit` | 0 |
| (c) `shim_status_lines` | 0 lines |
| (d) `closure_uncovered` | `[]` (0 paths) |
| (d) `closure_unresolved` | `[]` (0 includes) |
| (e) `build_exit` | 0 |
| `closure_paths` | 78 |
| `closure_upstream_lines` | 16,446 |
| `closure_shims_reached` | 1 path: `kernel/device/cpu/globals.h` |

H1 is supported: all six conditions of the decision rule hold. `closure_paths` is 78 and
`closure_upstream_lines` is 16,446, which equal Opus's predictions.

**H2 — the frame and each case's word accounting.**

| test case | passed | failed |
|---|---|---|
| `control flow` | 11 | 0 |
| `every stack node case dispatches` | 105 | 0 |

H2 is supported: 11 and 105 passed assertions, 0 failed.

**H3 — the derived values (IEEE `==`).**

| test case | passed | failed |
|---|---|---|
| `math` | 3 | 0 |
| `mix` | 3 | 0 |
| `map range` | 3 | 0 |
| `color ramp` | 3 | 0 |
| `convert` | 3 | 0 |

H3 is supported: each of the five reports 3 passed assertions and 0 failed.

**M1 — port cost.**

| measurement | value |
|---|---|
| `manifest_cases` | 39 |
| `manifest_includes` | 19 |
| `svm_case_fragments` | 39 |
| `svm_case_fragment_lines` | 174 |
| `vendored_headers` | 22 |
| `generated_header_lines` | 284 |
| `generated_header_sha256` | `b86aad32d05591ea9b980f494465137ceb7eafe0f5b4c0172c47ed16b087d7d2` |

All seven equal Opus's predictions for M1. Outside `src/test/`, the card adds one C++ file,
`src/cycles/svm_headers_check.cpp`, which includes the 22 headers and defines nothing.

**M2 — compile closure** of `test_cycles_svm_stack_nodes.cpp.o` (`ninja -t deps`).

| measurement | value |
|---|---|
| `deps_total` | 492 |
| `deps_third_party_cycles` | 74 |
| `deps_third_party_cycles_lines` | 16,154 |
| `deps_shim` | 1 |
| `deps_generated` | 1 |

**M3 — compile time** of that object, three rebuilds.

| run | seconds |
|---|---|
| 1 | 6.78 |
| 2 | 6.12 |
| 3 | 6.92 |
| median | 6.78 |

**Gate (X-svm, stack nodes).** `"gate": true`: H1, H2 and H3 are all supported. It covers the
compiler of `make build` only.

## Conclusion

DRAFT (DeepSeek) — pending Opus review.

- **H1: supported.** The 22 vendored headers compile verbatim in namespace `painterly` with
  `c++ (Ubuntu 15.2.0-16ubuntu1) 15.2.0`: `patches` is 0, `check --upstream` exits 0, the shim
  status has 0 lines, the closure has 0 uncovered and 0 unresolved paths, and the build exits 0.
  The deciding numbers are `closure_uncovered: []` and `closure_unresolved: []`; the closure is 78
  paths of 16,446 upstream lines, and it reaches exactly one shim, `kernel/device/cpu/globals.h`.
- **H2: supported.** `control flow` reports 11 passed and 0 failed, and
  `every stack node case dispatches` 105 passed and 0 failed. The generated interpreter therefore
  runs upstream's frame and consumes exactly each case's words.
- **H3: supported.** `math`, `mix`, `map range`, `color ramp` and `convert` each report 3 passed
  and 0 failed: the nodes compute exactly the values card T6.3 derives, under IEEE `==`.
- **Measurements.** Port cost (M1): 39 cases, 19 includes, 39 `svm_case` fragments of 174 upstream
  lines, 22 vendored headers, a generated header of 284 lines with sha256
  `b86aad32d05591ea9b980f494465137ceb7eafe0f5b4c0172c47ed16b087d7d2`. Compile closure (M2): 492
  dependencies, 74 of them under `third_party/cycles/` (16,154 lines), 1 shim and 1 generated
  header. Compile time (M3): 6.78 s, 6.12 s and 6.92 s, median 6.78 s.
- **Gate: passed** on the compiler of `make build` (`c++ (Ubuntu 15.2.0-16ubuntu1) 15.2.0`).
  MSVC and macOS arm64 compile the 22 headers only in CI (the wheel builds, and the MSVC windows
  job of .github/workflows/ci.yml where the branch has one), which this experiment does not
  observe.
