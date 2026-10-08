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
and ld-linux, all allowed. The traced run wrote two `ld.<pid>` files; only `ld.28061` contains `_painterly` bindings.

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
- `run.sh` exit 0 and `bindings_summary.txt` = 0: **fail** (exit 1; `bindings_summary.txt` = 4).
- Both H3 controls show at least 1 violation: pass (5 and 122).
- `make lint`: pass (ruff check, ruff format --check, clang-format; no network line at parse time).

## Conclusion

DRAFT (Haiku) — pending Opus review.

- **H1: supported.** `_painterly` imports inside Blender 5.2.2. Its selftest equals the venv selftest exactly, in the
  plain run and the traced run, with `tasking_system` 0.
- **H2: supported.** 20 alternating Cycles renders and selftests complete in both Blender runs (exit 0). Every
  selftest equals the first.
- **H3: refuted.** The module makes 4 violating bindings, all to Blender's bundled `libtbbmalloc_proxy.so.2`: `malloc`,
  `free`, `realloc` and `posix_memalign`. Coverage is complete (249 of 249). The instrument is sensitive: C1 gives 5
  violations (applicable: Blender's process defines `__cxa_pure_virtual`) and C2 gives 122.

Coexistence works in the sense of H1 and H2: the module loads, its selftest is exact, and Cycles renders run alongside it.
The isolation claim (`docs/plan.md`, "Isolation from Blender's own libraries"; the T2.2 audit allows only glibc-versioned,
Python C-API and toolchain weak imports) is refuted on Linux for the allocator: Blender's bundled TBB malloc proxy
interposes the module's `malloc`, `free`, `realloc` and `posix_memalign`. The T2.3 card's Goal says that if coexistence
does not work, the experiment shows exactly how it fails, which triggers gate G1 in `docs/plan.md`. This run shows that
failure mode. Whether it triggers G1, and whether the allocator binding is fixed in the module or accepted, are for the
Opus review.
