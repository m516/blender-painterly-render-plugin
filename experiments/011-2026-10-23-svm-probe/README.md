# Experiment 011: do Cycles' stack-only SVM nodes run verbatim and give exactly the derived values through the generated switch? (svm-probe)

Pre-registered by Opus on 2026-10-09 in card T6.3. Run on 2026-10-23.

Part 2 pre-registered by Opus on 2026-10-09 in card T6.5. Run on 2026-10-24.

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

### Part 2: graph → byte code → evaluation (card T6.5)

- Part 1 ran Cycles' evaluators on hand-encoded byte code. M6b also needs Cycles' host compiler, which turns a shader graph
  into that byte code. `docs/plan.md` ties X-svm to gate G2 ("Experiments programme"; M6: if the `graph/` shim fails, keep
  Cycles' names but write our own reduced reflection). Card T3.3 records G2 for `graph/`; part 2 decides the same question
  for the SVM (gate G2-svm), on the results of both parts.
- `SVMCompiler` is vendored as verbatim fragments of `scene/svm.cpp`: `:172-550` by card T6.4, `:157-170` and `:552-1279` by
  card T6.5, so every definition in `:157-1279` is a fragment. Cycles' device update (`SVMShaderManager`,
  `scene/svm.cpp:33-153`, and `ShaderManager::device_update_*`, `scene/shader.cpp:520-760`) needs a Device, a TaskPool, the
  LightManager and the BSDF lookup tables; `PainterlyShaderManager` (`src/painterly/scene/svm/shader_manager.h`) adapts it.
- The test graph is Value → Math → Emission. Its result is `ShaderData::closure_emission_background`, which the closure
  evaluators write: card T6.5 vendors `kernel/svm/closure.h` whole, with the 42 other kernel headers it reaches and
  `util/progress.h` and `util/time.h` (45 files), and adds the three cases that `EmissionNode::compile` emits. `time_dt()`,
  which the compiler's timers call, is a fragment of `util/time.cpp` too.
- `ShaderGraph::finalize` (`scene/shader_graph.cpp:374-402`) folds a graph of constants into one constant emission. The
  doctests therefore compile each graph twice: as Cycles prepares it, and unfolded, with only the closure weight that
  `finalize` sets for a lone closure, so that the SVM itself evaluates Value and Math.
- An independent reference checks the stack evaluation: 16 Math operations whose float32 result IEEE 754 fixes exactly, on
  4162 input pairs, against float64 arithmetic rounded once (card T6.5, "Expected byte code").


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

### Part 2 (card T6.5)

As in part 1, every observable is a count or an exact equality: no tolerance and no statistical test.

- **H4. The SVM compiler and the emission evaluators compile from verbatim upstream text: no patch, every definition of
  `scene/svm.cpp:157-1279` a fragment, and only the shim changes that card T6.5 names.**
  - Derivation: Opus read `scene/svm.cpp:157-1279` for what it uses beyond card T6.4's shims: `scene->dscene.data.svm_usage`;
    `shader->graph`, `reference_count()`, `estimate_emission()`, `get_displacement_method()` and twelve `has_*` flags;
    `string_printf()` (`:1254-1264`); `time_dt()`, `scoped_timer`, `queue` and `LOG_DEBUG`. The shim changes of card T6.5
    provide all of these except `time_dt()`, which is the fragment `util/time_cpp/function/time_dt` (`util/time.cpp:31-35`),
    and `scoped_timer` and `queue`, which vendored headers define (`util/time.h`, `util/queue.h`). On 2026-10-09 Opus
    compiled the 44 `scene/svm.cpp` fragments, the `time` unit, the generated switch with `kernel/svm/closure.h`, and the
    doctests of cards T6.4 and T6.5 with GCC 13.3 and Clang 18.1, against the util shims of card T3.3 as committed
    (`e9688b6`) with the edits of cards T6.4 and T6.5; all built and passed. The prototype also compiled the build check
    `src/cycles/svm_closure_headers_check.cpp` (`kernel/globals.h`, then `kernel/svm/closure.h`) with both compilers,
    without a warning.
  - Observables (`probe_part2.py`):
    - (a) the files in `third_party/cycles/patches/` other than `.gitkeep`;
    - (b) the exit status of `tools/vendor_sync.py check --upstream`;
    - (c) the definitions of `scene/svm.cpp` (`vendor_sync.list_anchors`, kinds `member` and `function`) with
      `157 <= first` and `last <= 1279` that no `[[fragment]]` of `scene/svm.cpp` covers with the same line range, and the
      `[[fragment]]` ranges of `scene/svm.cpp` that match no such definition;
    - (d) against the commit of card T6.4: the files under `src/cycles/shim/` that are new, modified or deleted;
    - (e) the include closure of `kernel/svm/closure.h`, `util/progress.h` and `util/time.h`: the paths that are neither a
      `dest` in `third_party/cycles/VENDORED.toml` nor a file under `src/cycles/shim/`, and the includes it cannot resolve;
    - (f) the exit status of `cmake --build <build> --target painterly_tests cycles_svm_closure_headers_check`.
  - Decision: supported iff (a) is 0 files; (b) is 0; both lists of (c) are empty; in (d) no file is new or deleted and the
    modified files are exactly `src/cycles/shim/scene/scene.h`, `scene/shader.h`, `scene/shader.cpp`, `util/string.h`,
    `util/string.cpp` and `util/log.h`; in (e) the uncovered paths are among `util/guiding.h` and `kernel/util/nanovdb.h`,
    and the unresolved includes among `../../guardedalloc/MEM_guardedalloc.h`; and (f) is 0. The three exceptions of (e) lie
    in conditionals that the definition set never enables: `#if defined(__PATH_GUIDING__)`
    (`kernel/integrator/state.h:33-35`), `#ifdef WITH_NANOVDB` (`kernel/util/image_3d.h:12-16`) and
    `#ifdef WITH_BLENDER_GUARDEDALLOC` (`util/guarded_allocator.h:11-13`).
- **H5. Graph → byte code → evaluation reproduces upstream exactly.**
  - Derivation: card T6.5, "Expected byte code", derives from upstream code every word that `SVMCompiler` emits for the test
    graphs, folded and unfolded, the jump table that `PainterlyShaderManager` packs for two shaders, the `KernelShader` flags
    that its port of `device_update_common` computes (upstream's emission flags are left out with `estimate_emission()`),
    the emission (0.75, 1.5, 3) and (1, 2, 4), exact in float, and the fetch trace of each evaluation.
  - Observables: the doctest test cases `cycles svm compiler: the node types and parameters of these tests are registered`
    (6 assertions), `...: Value -> Math -> Emission compiles to the derived byte code` (4), `...: the unfolded program
    evaluates to its emission` (9), `...: device_update_pre folds the graph and the folded program agrees` (21) and
    `...: two shaders share one jump table` (12).
  - Decision: supported iff each reports exactly these passed assertions and 0 failed.
- **H6. Compiled and evaluated by Cycles, 16 Math operations equal an independent float64 reference.**
  - Derivation: for +, −, ×, ÷ and √ of float32 operands, IEEE 754 makes the float32 result the correctly rounded exact
    value, and rounding a float64 result again gives the same float because 53 ≥ 2 · 24 + 2 (Figueroa 1995); fraction is a
    float subtraction; abs, floor, ceil, trunc, fmod, min, max, less than, greater than and sign are exact. Cycles' values at
    0 (division and modulo by 0, sqrt of x ≤ 0, sign of 0) are part of each definition. The reference shares no code with
    Cycles. Inputs: all 100 pairs of 10 special floats and the 4062 finite pairs of 4096 hashed bit patterns. Each pair is
    compiled twice: unfolded, so that the SVM computes the operation, and through `device_update_pre`, so that
    `MathNode::constant_fold` computes it on the host.
  - Observable: the test case `cycles svm compiler: Math through compiler and SVM equals an independent reference`: one
    assertion that 4162 pairs were built, and per operation one assertion each that the unfolded and the folded mismatch
    counts are 0.
  - Decision: supported iff it reports 33 passed assertions and 0 failed.
- **Measurements (no decision rule).** The plan asks for the effort of a node port; it informs the size of later port cards,
  not the gate.
  - M4, port size per node class of the test graph (`ValueNode`, `MathNode`, `EmissionNode`, `OutputNode`): its host
    fragments (`node_define` and `member` entries of `scene/shader_nodes.cpp`), its kernel cases (the SVM node types its
    `compile(SVMCompiler &)` emits on a surface: `NODE_VALUE_F` and `NODE_VALUE_F_DERIVATIVE`; `NODE_MATH`;
    `NODE_EMISSION_WEIGHT`, `NODE_CLOSURE_SET_WEIGHT` and `NODE_CLOSURE_EMISSION`; none for `OutputNode`), its manifest lines
    (the lines of those `[[fragment]]` entries in `VENDORED.toml`, each counted as its keys plus 2 for the
    `[[fragment]]` line and the blank line before it, plus one `svm_nodes.toml` line per kernel case) and its verbatim
    upstream lines. Opus's prediction: Value 5, 2, 67, 32; Math 7, 1, 75, 122; Emission 5, 3, 77, 73; Output 4, 0, 38, 39.
    No node needs a hand-written line of C++.
  - M5, time: the minutes between the `start` and `end` timestamps that the implementer of card T6.5 records in
    `port_log_part2.txt` (the whole card: vendoring, fragments, shims, port, tests).
  - M6, compile closure and time of `test_cycles_svm_compiler.cpp.o`, as M2 and M3 of part 1.
  - M7, sizes. Opus's prediction: 44 `scene/svm.cpp` fragments of 1076 upstream lines; 42 `svm_case` fragments of 192 lines;
    173 fragments in all; 45 files added by card T6.5, 12,956 lines; the generated header 306 lines, sha256
    `9b576212bf4eaeb8c3457f2b529091cd271b265b0172bfe9f16777254e83e9db`; the generated `svm` unit 1190 lines, sha256
    `d748be2c8fb3c1f9c848bc5a1bc2447107f69c8e5e3089c953756de919dd82ad`; the generated `time` unit 22 lines, sha256
    `145c1c19124d24519188b58d571eb53d5c778956291bbfca52b4ebee2d5506ff`; the closure of (e) 113 paths (110 upstream, 3 shims)
    and 29,367 upstream lines. (e)'s decision uses only its two lists.
- **Gate G2-svm (X-svm).** It passes iff H1, H2 and H3 (part 1) and H4, H5 and H6 (part 2) are all supported.
  - Pass: the vendored route stands. M6a continues with its remaining cards as written (evaluators vendored verbatim, nodes
    ported by fragments and manifest entries, no patches), and M6b builds on `cycles_svm`, `cycles_scene` and
    `PainterlyShaderManager`.
  - Fail: the M6a track stops after card T6.5, and Opus decides by the refuted hypothesis. H1 or H4 (vendored code needs a
    change): a patch in `third_party/cycles/patches/`, or vendoring `scene/svm.cpp` whole with the larger shim set of the M6
    research (§4.7), or the plan's G2 fallback, a painterly-written reduced compiler that keeps Cycles' names. H2, H3, H5 or
    H6 (behaviour differs): a fix-up card that finds the cause in the shims, the port or the tests before any further node
    port.


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

### Part 2 (card T6.5)

1. Card T6.5's Step 1 appends `start <UTC time>` to `port_log_part2.txt`; Step 11 appends `end <UTC time>` just before the
   probe runs. Both use `date -u +%FT%TZ`.
2. From the repository root: `.venv/bin/python -I experiments/007-<DATE>-svm-probe/probe_part2.py`. It reads
   `PAINTERLY_BUILD_DIR` (default `build/dev`), runs every instrument below, writes `results_part2.json` next to itself,
   prints a summary, and exits 0 iff gate G2-svm passes. It uses the standard library and `tools/vendor_sync.py`, loaded by
   path. Its output is deterministic except M6's times and the run date.
3. H4: (a), (b) and (f) as stated. (c) runs `vendor_sync.list_anchors()` on the checkout's
   `.cache/vendor/blender-v5.2.2/intern/cycles/scene/svm.cpp`. (d) compares the working tree with the newest commit whose
   subject matches `^([^ ]+: M6a-(FIX-)?)?T6\.4[a-z]?[ :]`, T6.4's commit in the queue's `<task id>: <item heading>` form
   (`git diff --name-status`, plus untracked files). (e) follows every line matching
   `^\s*#\s*include\s+"([^"]+)"` from the three seeds: an include resolves to a file under `src/cycles/shim/` (read from
   there), then to a path under the checkout root, then to a path relative to the includer's directory. Each candidate is
   normalized first (`os.path.normpath`), and one that starts with `..` never resolves; an include with no candidate is
   unresolved.
4. H5 and H6: `<build>/src/test/painterly_tests --test-case=<name>` once per test case, reading its line
   `[doctest] assertions: N | P passed | F failed`.
5. M4 and M7 from `third_party/cycles/VENDORED.toml`, `src/cycles/svm_nodes.toml`, the 45 vendored files and the three
   generated files under `<build>/src/cycles/` (`generated/svm_eval_nodes.h`, `fragment_units/svm.cpp`,
   `fragment_units/time.cpp`). M5 from `port_log_part2.txt`. M6 as part 1's M2 and M3, for
   `src/test/CMakeFiles/painterly_tests.dir/test_cycles_svm_compiler.cpp.o`. Part 1's gate is `results.json`'s `gate`.


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

### Part 2 (card T6.5)

Run on 2026-10-24. Every number below is from `results_part2.json` of that run.

| Hypothesis | Deciding numbers | Outcome |
|---|---|---|
| H4 verbatim compile | patches 0; `vendor_sync check --upstream` exit 0; `scene/svm.cpp` definitions 44, fragments 44, uncovered 0, extra 0; shim new 0, deleted 0, modified 6 (the six of card T6.5); closure 113 paths (110 upstream, 3 shims), 29,367 upstream lines, uncovered 0, unresolved 0; `cmake --build` exit 0 | supported |
| H5 byte code and evaluation | registered 6/0; byte code 4/0; unfolded evaluation 9/0; folded evaluation 21/0; two shaders 12/0 (passed/failed) | supported |
| H6 Math reference | 4162 pairs; 33 passed, 0 failed | supported |

| Measurement | Value |
|---|---|
| M4 ValueNode (host fragments, kernel cases, manifest lines, upstream lines) | 5, 2, 49, 23 |
| M4 MathNode | 7, 1, 66, 119 |
| M4 EmissionNode | 5, 3, 50, 55 |
| M4 OutputNode | 4, 0, 38, 39 |
| M5 card minutes (`port_log_part2.txt`) | 514.3 |
| M6 compile seconds (three runs, median) | 18.42, 18.51, 9.44; median 18.42 |
| M7 `scene/svm.cpp` fragments, lines | 44, 1076 |
| M7 `svm_case` fragments, lines | 42, 192 |
| M7 fragments in all | 173 |
| M7 files added by card T6.5, lines | 45, 12956 |
| M7 generated header lines, sha256 | 306, `9b576212bf4eaeb8c3457f2b529091cd271b265b0172bfe9f16777254e83e9db` |
| M7 generated `svm` unit lines, sha256 | 1190, `d748be2c8fb3c1f9c848bc5a1bc2447107f69c8e5e3089c953756de919dd82ad` |
| M7 generated `time` unit lines, sha256 | 22, `145c1c19124d24519188b58d571eb53d5c778956291bbfca52b4ebee2d5506ff` |

M6's closure counts (`deps_total`, `deps_third_party_cycles`, `deps_shim`, `deps_src_painterly`,
`deps_generated`) are 0: `ninja -t deps` printed no `#deps` line for the object in this build, so the
closure was not measured. M6's times are measured.

| Gate | Value |
|---|---|
| part 1 (`results.json`) | true |
| part 2 (H4 and H5 and H6) | true |
| G2-svm | true |

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

### Part 2 (card T6.5)

DRAFT (DeepSeek) — pending Opus review.

- H4 supported: 0 patches, `check --upstream` exit 0, 44 of 44 definitions of `scene/svm.cpp:157-1279`
  covered with no extra range, exactly the six shim files of card T6.5 modified (none new or deleted), the
  113-path closure uncovered and unresolved 0, and the build exit 0.
- H5 supported: the five test cases report 6, 4, 9, 21 and 12 passed assertions and 0 failed.
- H6 supported: 4162 pairs, 33 passed assertions, 0 failed.
- M4 against Opus's predictions (host fragments, kernel cases, manifest lines, upstream lines): Value
  measured 5, 2, 49, 23 against 5, 2, 67, 32; Math 7, 1, 66, 119 against 7, 1, 75, 122; Emission 5, 3, 50, 55
  against 5, 3, 77, 73; Output 4, 0, 38, 39 against 4, 0, 38, 39. Host fragments and kernel cases match
  everywhere; manifest and upstream line counts are lower for Value, Math and Emission.
- M5 514.3 minutes; M6 median 18.42 s (closure counts not measured); M7 matches Opus's prediction on every
  value: 44 fragments of 1076 lines, 42 `svm_case` of 192 lines, 173 fragments, 45 files of 12,956 lines,
  the three generated files at 306, 1190 and 22 lines with the predicted sha256s.
- Gate G2-svm passes: part 1's gate and part 2's three hypotheses are all supported. Per "Gate G2-svm", the
  vendored route stands and M6a continues with its remaining cards as written.
