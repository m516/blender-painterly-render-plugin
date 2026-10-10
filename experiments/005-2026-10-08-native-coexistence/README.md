# Experiment 005: do `_painterly` and Blender's own Cycles coexist in one process? (native-coexistence)

## Background

- `docs/plan.md`, "Isolation from Blender's own libraries": Embree 4.4.1 is linked static, with
  `EMBREE_API_NAMESPACE=painterly_embree` and INTERNAL tasking (no TBB). There is no OIIO, OCIO or TBB. Everything
  compiles with hidden visibility and a version script, so only `PyInit__painterly` is exported. The module is built
  against manylinux_2_28 with a static libstdc++ and libgcc. The plan says that Blender's macOS executable exports
  5,720 `ccl::` symbols. The T2.3 card records that Blender links `libembree4.so.4` and `libtbb.so.12` dynamically.
- `docs/plan.md`, milestone M2, T2.3 and gate G1: if X-coexist fails on any OS, the fallback is an out-of-process
  render server.
- `docs/tasks/M2/T2.2-symbol-audit.md` and `T2.5-isolation-fixups.md`: the audit allows only glibc-versioned,
  Python C-API and toolchain weak imports. T2.5 added `-Wl,-u,__cxa_pure_virtual` so that the module links its own
  copy of `__cxa_pure_virtual` and does not bind to the host libstdc++. The `nm -D --undefined-only` count for that
  symbol is 0 in the T2.5 build.
- Blender 5.2.2 is the target host. Its standalone Linux build is fetched by `tools/fetch_blender.py` into `.cache/`.
  This experiment uses that build's own Python and its own Cycles, so the Python C API binds to the `blender`
  executable, as it would in any Blender process.
- Earlier experiments 001-004 are about the look of the oracle and do not touch the native module. This is the first
  experiment that runs the native module inside a host process.

## Hypothesis

Each hypothesis is pre-registered before any run. The decision rules are exact: there are no tolerances and no
statistical tests, because every observable is an equality or a count.

- **H1. `_painterly` imports inside Blender 5.2.2, and its `selftest()` there returns a dict exactly equal to
  `selftest()` run in the project venv on the same machine from the same build, with `tasking_system == 0`.**
  Derivation: the module carries its own static, namespaced Embree with INTERNAL tasking (plan, "Isolation"). Its
  selftest creates its own device and scene and calls no Blender code, so the host process should not change its
  result. Observable: the two dicts (`embree_version`, `tasking_system`, `hit`, `t`, `prim_id`) and the module import.
  Decision: H1 is supported iff the import succeeds, the plain run's selftest and the traced run's selftest each `==`
  the venv selftest (floats compared exactly, no tolerance), and `tasking_system == 0`. Otherwise it is refuted.
- **H2. 20 alternating Cycles renders and `_painterly.selftest()` calls complete with exit code 0, and every selftest
  equals the first one.**
  Derivation: Cycles and the module share no state (separate nanobind domain `painterly`, separate namespace, and
  static Embree), so a render cannot change the selftest result. Observable: the exit status of each Blender run, and
  each of the 20 selftest dicts compared with the first. Decision: H2 is supported iff both Blender runs (plain and
  traced) exit 0, all 20 iterations complete, and all 20 selftests `==` the first. Otherwise it is refuted.
- **H3. The module makes zero violating bindings.** A binding is a violation iff its symbol version does not start
  with `GLIBC_` and its symbol does not match `^_?Py`. Derivation: the plan allows only glibc-versioned imports, the
  Python C API (bound to the `blender` executable), and nothing from Blender's own libraries. A leak would appear as
  a binding to `libembree4.so.4`, `libtbb.so.12`, a `ccl::` symbol, or the host libstdc++. Observable: the count of
  violating bindings in `bindings.py`'s trace of the traced run. Decision: H3 is supported iff that count is exactly 0.
  H3 is also only meaningful if its instrument is sensitive, so two controls must each show at least one violation:
  - **C1.** The module relinked without `-Wl,-u,__cxa_pure_virtual` (the T2.2 negative build). The weak import then
    binds to the host's libstdc++, which is a violation.
  - **C2.** The module relinked against the dynamic libstdc++ (no `-static-libstdc++ -static-libgcc`). Its libstdc++
    bindings should number many; the card's pass threshold is at least one.

## Method

Everything runs from the repository root through `experiments/005-2026-10-08-native-coexistence/run.sh`.

1. **Blender.** `make blender` runs `tools/fetch_blender.py`. It downloads
   `https://download.blender.org/release/Blender5.2/blender-5.2.2-linux-x64.tar.xz` and
   `blender-5.2.2.sha256` into `.cache/blender/`. The tarball's sha256 must equal its line in the release's `.sha256`
   file, and the tarball is extracted to `.cache/blender/blender-5.2.2-linux-x64/`.
2. **Module.** `make build` builds `build/dev/src/blender/_painterly.abi3.so` with the T2.5 link flags.
3. **Blender runs.** `$BLENDER -b --factory-startup --python-exit-code 1 --python coexist.py -- build/dev`, twice:
   - plainly;
   - with `LD_DEBUG=bindings LD_DEBUG_OUTPUT=out/ld`, which writes the dynamic linker's binding trace to `out/ld.<pid>`.
   Each run sets the scene to Cycles on the CPU device, 64 x 64 pixels, 4 samples. It then repeats 20 times: a render
   with `write_still=False`, saved to `out/cycles_NN.png`, followed by `_painterly.selftest()`. It writes
   `out/coexist.json` (renamed to `coexist_plain.json` or `coexist_traced.json`).
4. **H1 reference.** `.venv/bin/python` imports `build/dev/src/blender/_painterly.abi3.so` and writes its selftest to
   `out/venv_selftest.json`. The comparison is made inline in `run.sh`, and its output is in `out/run.log`.
5. **H3 instrument.** `.venv/bin/python experiments/005-…/bindings.py out/` parses every `out/ld.*` file with the regex
   fixed in the T2.3 card, skips self-bindings, and writes `out/bindings_summary.txt` (the violation count) and
   `out/bindings.json` (totals, per destination, and violating symbols). Paths are matched by the full regex, never
   by substring, because the repository path contains "blender".
6. **Controls C1 and C2.** `run.sh` takes the link command from `ninja -t commands` and produces two relinks with
   `sed`, in `out/controls/no_cxa/` and `out/controls/dyn_libstdc/`. Each drops `--dependency-file`, so the build's
   `link.d` is untouched. Each control module is loaded in Blender with `LD_DEBUG`, and calls `selftest()` so that
   the lazily bound calls are traced too. `bindings.py` then runs on each control directory.
7. **Pass rule.** `run.sh` exits 0 only when H1 and H2 hold, H3's count is 0, and both controls show at least one
   violation. Its outputs are written either way.

Limitations: without eager binding, LD_DEBUG reports a lazily bound import only when it is first called. Amendment 1
below removes that limitation for every traced run.

System libraries: if `ldd` on the Blender binary reports missing libraries, the packages installed for it are listed
here, and in `tools/blender_system_deps.txt`. The `ldd` check is reported in Results.

### Amendments before running (Opus)

These amendments were made after the hypotheses above were pre-registered and before any Blender run. They are in
`run.sh` and `bindings.py`. Where an amendment conflicts with a sentence above, the amendment applies.

1. **Traced runs set `LD_BIND_NOW=1`.** The H3 trace of the traced run and both control runs use
   `LD_BIND_NOW=1 LD_DEBUG=bindings LD_DEBUG_OUTPUT=…`. Eager binding resolves every non-weak import when the module
   loads, so the trace shows each import whether or not it is ever called. This replaces the lazy-binding limitation
   above.
2. **`bindings.py` takes `--module <path>`.** The path is the `_painterly*.so` whose trace is read. `nm -D
   --undefined-only` on that file gives the module's undefined dynamic symbols, with their versions.
   - Expected bindings: the undefined dynamic symbols, minus the weak undefined symbols that the trace does not bind.
     A weak import that stays unresolved produces no trace line, so it cannot be expected.
   - Matched bindings: the expected symbols that the trace binds from `_painterly`, matched by symbol name and version.
     A trace binding that nm does not list is reported as `bound_but_not_imported` in `bindings.json`.
   - Coverage = matched / expected. Coverage is complete iff matched == expected and expected > 0.
3. **H3's decision rule.** H3 is supported iff coverage is complete AND the violation count is 0. This replaces the
   rule in the Hypothesis section, which counted violations alone.
4. **GLIBC-versioned bindings.** A binding whose version starts with `GLIBC_` is a violation unless its destination's
   basename is `libc.so.6`, `libm.so.6`, or `ld-linux-*.so.N`. Any other destination for such a binding is a
   violation. Every other binding keeps the H3 rule: it is a violation unless its symbol matches `^_?Py`.
5. **Control C1 is "not applicable" if Blender's process does not define `__cxa_pure_virtual`.** The process is the
   `blender` executable plus the libraries that `ldd` lists for it. `run.sh` looks for a defined symbol in each one's
   dynamic symbol table, with `nm -D --defined-only`. If none defines it, C1's weak import stays unbound, so no trace
   can show it, and C1 is reported as "not applicable". In that case the pass rule requires only C2. If it does define
   it, C1 must show at least one violation, as before.
6. **The controls use the same settings.** Both control runs use `LD_BIND_NOW=1`, and `bindings.py --module` reads each
   control's own module (`out/controls/<name>/_painterly.abi3.so`).
7. **`tools/fetch_blender.py --print-path-only` does no I/O.** It prints the executable's expected path without network
   access, so `run.sh` and the Makefile's `BLENDER` default never download. Only `make blender` downloads, and it sends
   the honest tool User-Agent required by CLAUDE.md, "Network notes".

### Amendment for later runs (Opus, 2026-10-09, after the 2026-10-08 run)

This amendment does not change the verdicts of the 2026-10-08 run recorded below. It replaces Amendment 4 for every
later run: the CI coexist job (`.github/workflows/wheels.yml`) and any rerun of `run.sh`.

- **Allocator family.** `ALLOCATOR_FAMILY` is the set of names that glibc lets a replacement allocator interpose
  (glibc manual, §3.2.5 "Replacing malloc"): `malloc`, `free`, `calloc`, `realloc`, `aligned_alloc`,
  `malloc_usable_size`, `memalign`, `posix_memalign`, `pvalloc`, `valloc`.
- **Coherence rule.** A `GLIBC_`-versioned binding of a name in `ALLOCATOR_FAMILY` is allowed wherever it goes iff the
  allocator is *coherent*. Coherent means that the union of two destination sets has exactly one element:
  - the destinations of the module's allocator-family bindings;
  - the destinations of `libc.so.6`'s own allocator-family bindings in the same process's trace (the `ld.<pid>` file that
    holds the module's bindings), self-bindings included. Other processes in the run, such as a child `sh`, have their
    own allocators and do not take part.
  Memory then has one owner, whichever object allocates or frees it. An incoherent allocator makes every
  allocator-family binding of the module a violation.
  - Why libc's binding set, not a symbol-by-symbol match: in the 2026-10-08 trace `libc.so.6` binds `malloc`, `free`,
    `calloc` and `realloc` to the proxy, but has no binding of `posix_memalign` at all. A symbol-by-symbol rule would
    therefore flag the module's `posix_memalign`, even though its memory is released by the module's `free`, which goes
    to the same proxy.
- **glibc objects.** `GLIBC_PROVIDER` also accepts `libpthread.so.0`, `libdl.so.2`, `librt.so.1`, `libutil.so.1` and
  `libresolv.so.2`. These are separate glibc objects on hosts with glibc older than 2.34.
- **Control sensitivity.** `bindings.json` reports `control_specific_violations`: the control's violations minus the
  main run's, compared by (symbol, version, destination basename). `run.sh` requires at least one for each applicable
  control. A control that only repeats the main run's violations then no longer counts as sensitive.
- **Check of the rule (T2.8, 2026-10-09).** `bindings.py` implements both rules (`--rule registered|coherent`). On a
  copy of the 2026-10-08 `out/`:
  - `--rule registered` reproduces the recorded run: 4 violations, coverage 249/249.
  - `--rule coherent` gives 0 violations, coverage 249/249, `allocator.coherent` true and `allocator.processes`
    `["ld.30094"]`.
  - With `--baseline`: C1 has 1 control-specific violation (`__cxa_pure_virtual` → `libstdc++.so.6`) and C2 has 119.
  This is a check of the rule, as the Conclusion's decision 3 announced. It is not a re-scoring of the 2026-10-08 run.

## Results

Run with `experiments/005-2026-10-08-native-coexistence/run.sh` on this machine. `run.sh` exited 1, because H3 is
refuted (see below). The raw outputs are in `out/` (git-ignored): `run.log`, `coexist_plain.json`,
`coexist_traced.json`, `venv_selftest.json`, `bindings.json`, `bindings_summary.txt`, `controls/*/bindings.json`,
and `cycles_00.png` to `cycles_19.png`.

Blender: 5.2.2 LTS, build hash `d13f752e3b9c`, platform Linux, Release. Module: `build/dev/src/blender/_painterly.abi3.so`
(T2.5 link flags), `version_info` `{version 0.1.0, compiler 13.3.0, build_type Release, stable_abi True}`.

**Start-up and system libraries.** `ldd` on the Blender executable reports 0 missing libraries, and
`blender -b --factory-startup --version` exits 0. No system packages were installed, so
`tools/blender_system_deps.txt` was not created.

**H1 (import and exact selftest equality): supported.**

| run | selftest | equal to the venv selftest |
|---|---|---|
| venv (`.venv/bin/python`) | `embree_version` 4.4.1, `tasking_system` 0, `hit` True, `prim_id` 0, `t` 0.4999999701976776 | reference |
| Blender, plain | same dict | True |
| Blender, traced (`LD_BIND_NOW=1`) | same dict | True |

The import succeeded in both Blender runs.

**H2 (20 alternating Cycles renders and selftests): supported.**

| run | Blender exit | iterations | every selftest equal to the first | mean render (s) | mean selftest (ms) |
|---|---|---|---|---|---|
| plain | 0 | 20 | True | 0.1058 | 0.94 |
| traced | 0 | 20 | True | 0.0948 | 1.07 |

**H3 (violating bindings from `_painterly`, traced run): refuted.**

- The module has 252 undefined dynamic symbols (`nm -D --undefined-only`: 247 `U`, 5 `w`). Three weak symbols were
  left unbound by the trace (`_ITM_deregisterTMCloneTable`, `_ITM_registerTMCloneTable`, `__gmon_start__`), so the
  expected bindings are 249.
- Coverage: 249 of 249 expected bindings matched (complete). No trace binding is missing from `nm`, and no
  expected binding is missing from the trace. One self-binding was skipped.
- Violations: 4.

| destination | bindings | violations |
|---|---|---|
| `blender` executable | 101 | 0 |
| `lib/libtbbmalloc_proxy.so.2` (Blender's bundled library) | 4 | 4 |
| `libc.so.6` | 136 | 0 |
| `libm.so.6` | 7 | 0 |
| `ld-linux-x86-64.so.2` | 1 | 0 |

The four violations are `malloc`, `free`, `realloc` and `posix_memalign`, each `GLIBC_2.2.5`, each bound from
`_painterly.abi3.so` to `lib/libtbbmalloc_proxy.so.2`. The cause is in the Blender executable, not in the module:
`libtbbmalloc_proxy.so.2` is a direct `NEEDED` entry of `blender` (`readelf -d`), and it exports those four names
(`nm -D --defined-only`). It therefore sits in the global lookup scope and interposes glibc's allocator for the
module's glibc-versioned imports. The module's other 245 bindings are to the Python C API (in `blender`), glibc, libm
and ld-linux, all allowed. The traced run wrote two `ld.<pid>` files; only the larger one (85 MB, the render process)
contains `_painterly` bindings. `bindings.py` reads both.

**Scope of the allocator binding (post-run observation; the verdict above is unchanged).** The same trace shows that
the proxy is the process allocator, not a symbol that the module chose. Its 383 bindings to `libtbbmalloc_proxy.so.2`
come from 85 objects in the traced process, `_painterly` included: the Blender executable (20 bindings),
`libstdc++.so.6` (10), `libembree4.so.4` (7), `libc.so.6` (4), and 80 other objects, mostly Blender's libraries.
They bind `malloc`, `free`, `calloc`, `realloc`, `posix_memalign`, `memalign`, `aligned_alloc`, `mallinfo`,
`malloc_usable_size`, and the `operator new` and `operator delete` family. The four `_painterly` violations are one
instance of that mechanism. Amendment 4 counts them as violations, and this run does not change that rule.

**Controls (instrument sensitivity).**

- **C1, relink without `-Wl,-u,__cxa_pure_virtual`: applicable, and it shows violations.** Blender's process defines
  `__cxa_pure_virtual` (through `libstdc++.so.6`, which `blender` links dynamically), so C1 is not "not applicable".
  Relink exit 0. The traced run exits 0 with coverage 250 of 250 (complete). It shows 5 violations: the same four
  allocator bindings, plus unversioned `__cxa_pure_virtual` bound to `/lib/x86_64-linux-gnu/libstdc++.so.6`. Of the
  five, only the last is specific to C1.
- **C2, relink against the dynamic libstdc++: shows violations.** Relink exit 0. The traced run exits 0 with coverage
  294 of 294 (complete). It shows 122 violations: 107 to `libstdc++.so.6`, 7 to `libtbbmalloc_proxy.so.2`, 5 to
  `libceres.so.4`, 2 to `libusd_ms.so`, and 1 to `libgcc_s.so.1`.

Both controls show at least one violation, so the instrument is sensitive. H3's count of 4 is not an artefact of a
trace that missed bindings: coverage is complete in the main run and in both controls.

**Acceptance checks (card).**

- `make blender`: first run downloaded, verified the sha256 (`84098912789dc450e95697c4184fb8a90acbe5111c2ba4aede3fecb57806a168`)
  and extracted, then printed `Blender 5.2.2 executable: …/.cache/blender/blender-5.2.2-linux-x64/blender`. A second
  run printed the same path with `present and verified`, and took 0.44 s with no download. Pass.
- `run.sh` exit 0 and `bindings_summary.txt` = 0: **fail** (exit 1; `bindings_summary.txt` = 4). The card's Goal treats
  a refuted H3 as a valid outcome that triggers G1, while its Acceptance line requires 0. Both cannot hold, so this
  line is not met. The rule, the module and `run.sh` were not changed to meet it. Re-run on the committed tree gave the
  same numbers (summary 4, controls 5 and 122, H1 and H2 unchanged).
- Both H3 controls show at least 1 violation: pass (5 and 122).
- `make lint`: pass (ruff check, ruff format --check, clang-format; no network line at parse time).

### Later runs (CI coexist job, 2026-10-09 to 2026-10-10)

These runs used `.github/workflows/wheels.yml` and the allocator-coherence rule of "Amendment for later runs", which was
fixed before any of them. Each OS runs the experiment in Blender 5.2.2 with the wheel built on that OS. The binding trace
runs on Linux only (the job's "Trace the coexistence run and scan its bindings (Linux)" step).

| Run | Commit | Linux | macOS (arm64) | Windows (x64) |
|---|---|---|---|---|
| 37935120179 | `c3e7566` | wheel built | wheel built | wheel failed the symbol audit: 19 nanobind `NB_EXPORT` exports (fixed by T2.9). `coexist` was skipped on every OS |
| 37984431443 | `d2259e7` | coexist passed | coexist passed: 20 of 20 iterations equal to the first, every selftest `hit` | wheel did not compile: vendored `util/guarded_allocator.h` without `<memory>` (fixed by T2.10) |
| 38003053457 | `f052211` | wheel built | wheel built | wheel did not compile: 148 errors, all from `<windows.h>`'s `min`/`max` macros (fixed by T2.11) |
| 38013859281 | `6abe417` | coexist passed | coexist passed | coexist passed |

Run 38013859281 in detail, all three OS:

| | Linux | macOS | Windows |
|---|---|---|---|
| Compiler (`version_info`) | GCC 14.2.1 | AppleClang 15.0.0 | MSVC 194435229 |
| Iterations, equal to the first | 20 of 20 (plain), 20 of 20 (traced) | 20 of 20 | 20 of 20 |
| Selftest | Embree 4.4.1, `tasking_system` 0, `hit`, `t` 0.4999999701976776 | Embree 4.4.1, `tasking_system` 0, `hit`, `t` 0.5 | Embree 4.4.1, `tasking_system` 0, `hit`, `t` 0.4999999701976776 |
| `error` | none | none | none |
| Symbol audit of the wheel's module | PASS | PASS (exports `_PyInit__painterly` only; libSystem and libc++ only) | PASS (exports `PyInit__painterly` and nanobind's exception classes only) |

- **Linux bindings (coherence rule).** 0 violations. Coverage is complete: 244 of 244 expected bindings matched. The
  traced process is `ld.2613`. The module's allocator-family bindings and libc's both go to Blender's
  `lib/libtbbmalloc_proxy.so.2`, so `allocator.coherent` is true.
- **Windows imports.** `llvm-objdump --private-headers` of the wheel's `_painterly.pyd` lists `python3.dll`,
  `KERNEL32.dll` and `ADVAPI32.dll`. The `ADVAPI32.dll` imports are `OpenProcessToken`, `LookupPrivilegeValueW` and
  `AdjustTokenPrivileges`: Embree's huge-page code, which the audit's allowlist already names (`tools/symbol_audit.py:88`).
- **macOS bindings.** Not traced: the job has no Mach-O binding trace.
- **The `t` values differ by platform** (0.5 on macOS arm64, 0.4999999701976776 on x86-64). Embree computes in float32,
  with ISA-dependent code paths. Each value is equal across that OS's 20 iterations and to its own venv selftest (H1 on CI).

## Conclusion

Final (Opus, 2026-10-09). The Haiku draft is superseded. The numbers are those in Results.

**`_painterly` coexists with Blender 5.2.2's Cycles on Linux. Gate G1 is not triggered there, and the module stays
in-process.**

- **H1 supported.** The module imports in Blender, and its selftest equals the venv selftest exactly, in both the plain
  and the traced run (`tasking_system` 0, `t` 0.4999999701976776).
- **H2 supported.** 20 of 20 alternating Cycles renders and selftests complete in both runs, every selftest equals the
  first, and both runs exit 0.
- **H3 refuted as registered.** There are 4 violating bindings, with coverage 249 of 249: `malloc`, `free`, `realloc`
  and `posix_memalign` @GLIBC_2.2.5, all bound to `lib/libtbbmalloc_proxy.so.2`. The pre-registered rule counts
  those as violations, and the verdict stands.

**What the refutation means.** The four bindings are glibc's supported allocator replacement (glibc manual §3.2.5).
They are not a leak of Blender's C++ or Cycles state:
- The proxy is a `NEEDED` entry of the `blender` executable, so it interposes the allocator for the whole process.
  `libc.so.6` itself binds `malloc`, `free`, `calloc` and `realloc` to it, as do 84 other objects.
- I re-read the trace for this conclusion. The module's four allocator bindings and libc's four go to one destination,
  in the main run and in both controls. Memory therefore has one owner, wherever it is allocated or freed. The
  module's `strdup` goes to libc, which allocates through the same proxy.
- The plan's isolation threats are absent. The module makes no binding to `libembree4`, `libtbb`, `libstdc++` or any
  `ccl::` symbol. The instrument would see such a binding: C1 adds exactly one (`__cxa_pure_virtual` to
  `libstdc++.so.6`), and C2 adds 119 by the per-key comparison of the later-runs amendment.

**What G1 means.** G1 asks whether the module can run inside Blender's process. H1 and H2 say it can. The only bindings
outside the allowed set are to an allocator the whole process already shares, so an out-of-process render server would
remove no risk that in-process rendering carries.

**Decisions.**
1. G1 for Linux: not triggered.
2. G1 for macOS and Windows: open until the CI coexist job (T2.4, T2.7) passes on those runners.
3. Later runs use the allocator-coherence rule ("Amendment for later runs"), which was fixed before any later run.
   T2.8 tests the expectation that the rule counts the 2026-10-08 trace as 0 violations. That is a check of the rule,
   not a re-scoring of this run.
4. The audit (`tools/symbol_audit.py`) keeps treating `malloc` and friends as plain glibc imports. Interposition is a
   property of the host process, and only a binding trace can see it.

**Hypothesis for later work.** Blender's macOS build has no ELF interposition. Two-level namespaces bind each import
to the library it was linked against. The CI run should therefore show 0 allocator violations there, without the
coherence rule. The Windows module, linked with the static CRT (`/MT`), imports only from `python3.dll` and `kernel32.dll`. That is the audit's allowlist, so the allocator question does not arise there.

**Addendum: G1 on macOS and Windows (Opus, 2026-10-10).** The numbers are in Results, "Later runs".
- **G1 is not triggered on any OS.** On Linux, macOS and Windows, H1 and H2 hold on CI. Each OS gives 20 of 20 Blender
  renders with selftests equal to the first, and its selftest equals that OS's venv selftest. The Linux trace has 0
  violations under the coherence rule fixed before the run, with complete coverage (244 of 244). `_painterly` stays
  in-process on every platform, and no out-of-process render server is needed. M2's gate is closed.
- **The hypothesis for later work, checked.**
  - macOS: untested. The CI job traces bindings only on Linux, so the claim of 0 allocator violations without the
    coherence rule has no data. H1 and H2 do not depend on it.
  - Windows: refuted as stated, though not in substance. The module imports `ADVAPI32.dll` as well: three privilege
    functions of Embree's huge-page allocator. The audit's allowlist already names it. With the static CRT the allocator
    question still does not arise, since `ADVAPI32.dll` exports no allocator.
- Reaching green on Windows needed two build fixes in vendored Cycles' include environment, and neither changes code
  under test:
  - T2.10: force-include `<memory>`, which upstream gets from `MEM_guardedalloc.h`;
  - T2.11: `NOMINMAX`, which upstream defines for every Windows source.
  The CI `windows` job (T2.10) now builds and unit-tests the C++ libraries with MSVC on every push.
