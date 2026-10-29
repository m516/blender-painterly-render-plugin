# 43-blender-smallpaint backlog (for ds-autopilot)

Read `AGENTS.md` first, especially "Expected values are evidence, not targets". Every `##` item has a machine-checkable
outcome. Items are in priority order. `Depends on:` names items (by heading id) that must be committed to integration
first.

**Shorthand and the gate.**
- `MAIN` = `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin`, the host's
  main checkout. It is read-only to you; read it only by the exact paths in AGENTS.md.
- `KNOBS` (write them out in full in every command; they exist once item BOOT-0a has landed):
  `VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest"`
- `CHECK`, the standard verify, which must exit 0:
  `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check <KNOBS>` (run from the clone root; R12)
  `Q/RULINGS.md` may extend `CHECK`, for example with a prebuilt Embree after BOOT-0b. The latest ruling wins.
- Translating a card's commands:

| The card says | Run instead |
|---|---|
| `make check` | `CHECK` |
| `make build`, `make test`, `make test-cpp`, `make test-py`, `make lint`, `make audit`, `make vendor-check` | the same target with `CMAKE_BUILD_PARALLEL_LEVEL=4` and the `KNOBS` |
| `build/dev` | `build/q` |
| `build/dev/_deps/embree-src`, `build/dev/_deps/doctest-src` | `MAIN/.cache/src/embree`, `MAIN/.cache/src/doctest` |
| `.venv/bin/<tool>` | `MAIN/.venv/bin/<tool>` |
| any Python command (pytest, an `analyze.py`, a `tools/` script) | the same, prefixed with `PYTHONPATH="$PWD/analysis"`; an explicit `PAINTERLY_BUILD_DIR` is absolute: `"$PWD/build/q"` (R12) |
| a card's `<venv>/bin/python -I …` | `PYTHONPATH="$PWD/analysis" <venv>/bin/python -P -s …` (R18) |
| a card's `.cache/oracle-build` (the experiments' oracle) | `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/oracle-build`, read-only; never `build/q` (R7, R17) |
| `make env`, `make oracle`, `make blender`, `make wheel`, the network, CI, GitHub, "the orchestrator verifies" | host-only: don't run; report "host-only, not run" |

**General rules.**
- Each item implements exactly one task card, at the path the item names. Follow the card; it is the specification. Its
  Create/Modify list is your allowedPaths. Card defects go to `report_blocked` with evidence.
- Where an item names review findings (`docs/handoff/findings/*.json`, under the given keys), check them as AGENTS.md
  says, and list each one as applied or rejected.
- Never write to `MAIN`, `.cache/oracle-build` or `.cache/renders`, and never rebuild the experiments' oracle.
- A card's "Depends on" line describes the original batch order. This backlog's `Depends on:` lines are the ones that
  count.

**DONE (do not redo or re-emit).**
- M0-M2: scaffolding, the oracle, the analysis package, the static module, the symbol audit, wheels, coexistence (G1).
- M3 run 3a: T3.1-T3.12 and TQ.1. Close-out: T2.9, T2.10, T2.11.
- Experiments 001-006: final. Experiments 007-009: pre-registered; their analysis items come later (below).

**Added on 2026-10-16, once the host had regenerated the render cache** (they were listed here as "coming later"):
EXP-REPRO (done), EXP-REPRO-HOST, M3-FIX-T3.25, M3-FIX-T3.26 and EXP-007, EXP-008, EXP-009, at the end of this file
(R17).

## BOOT-0a: offline worker builds (VENV and CMAKE_ARGS knobs; make check green on this host)
Why:
- Workers run offline in fresh clones that have no `.venv`.
- The Makefile hardcodes `.venv/` and cannot pass options to CMake, so `make check` cannot run there.
- This host's compiler is GCC 15.2. The code has only ever been built with GCC 13.3, MSVC 14.44 and AppleClang 15.
Do:
- `Makefile`: add `VENV ?= .venv` and use `$(VENV)` for every `.venv` path: the PATH export, python, ruff,
  clang-format, the symbol audit, the vendor check and `fetch_blender`.
- `Makefile`: add `CMAKE_ARGS ?=`, appended to the CMake configure commands of `build` and `oracle`.
- Comment both knobs in the Makefile's style. With the defaults, every command must stay as before, because CI uses the
  defaults.
- If `CHECK` then fails because GCC 15 rejects non-vendored code, apply the minimal fix that keeps behaviour
  bit-identical, such as a missing standard include. Make one fix per error, and list each with its compiler message.
- If vendored code (`third_party/`) or Embree fails to compile, call `report_blocked` with the errors.
Outcome:
- `CHECK` exits 0. Report the doctest case and assertion counts, the pytest pass count and the audit `RESULT:` line.
- The defaults are unchanged. These two outputs must be identical:
  `git show HEAD:Makefile > /tmp/Makefile.orig && make -n check | sed 's/ *$//'`
  and `make -n -f /tmp/Makefile.orig check | sed 's/ *$//'`
  (no knobs; trailing spaces stripped).
allowedPaths: `Makefile`; and, only for GCC 15 compile fixes, `src/painterly/**`, `src/cycles/shim/**`, `src/blender/**`, `src/app/**`, `src/test/**`.

## M3-FIX-T3.19: zero-length diffuse direction (SPEC §4, D33)
Card: `docs/handoff/drafts/M3-fixups/T3.19-zero-length-bounce.md`.
Review findings: `docs/handoff/findings/M3-fixups-reviews.json`, keys `review T3.19 executability` and
`review T3.19 correctness`.
Depends on: BOOT-0a.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M3-FIX-T3.20: scheduler robustness (TQ.1 F1-F8)
Card: `docs/handoff/drafts/M3-fixups/T3.20-scheduler-robustness.md`.
Review findings: `docs/handoff/findings/M3-fixups-reviews.json`, keys `review T3.20 executability` and
`review T3.20 correctness`.
Depends on: M3-FIX-T3.19.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M3-FIX-T3.21: contract touch-ups (one normal matrix, no dead kernel arrays, shared layout names, derived Embree bound)
Card: `docs/handoff/drafts/M3-fixups/T3.21-contract-touchups.md`.
- This card edits `CONTRACT:` headers, and only the ones it lists.
- Its design decisions (D35-D37 in `docs/handoff/decisions-M3.md`) are final; implement them exactly. If a decision
  turns out to be inconsistent with the code, call `report_blocked`.
- Opus reviews this diff before it lands in MAIN.
Review findings: `docs/handoff/findings/M3-fixups-reviews.json`, keys `review T3.21 executability` and
`review T3.21 correctness`.
Depends on: M3-FIX-T3.20.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M3-FIX-T3.21b: the smallpaint Vec copy keeps its CRLF bytes (T3.21 audit)
No card; this item is the specification.
Why:
- `src/test/test_math_double3.cpp` holds a copy of the struct `Vec` from
  `third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp` lines 43-55, and its comment says the copy stays
  "byte-identical to the source, tabs included". Those 13 source lines end in CRLF (`\r\n`).
- M3-FIX-T3.21 rewrote the 13 lines of the copy with LF endings, so the comment is now false. Its audit found this.
  clang-format is not the cause: it keeps the CR bytes, and `make lint` passes with them.
Do:
- Make the 13 lines of the copy byte-identical to lines 43-55 of the source, CR bytes included. Change nothing else in
  the file. Write the bytes with a script that reads the source in binary mode (for example Python `open(path, "rb")`).
  Do not rely on `write_file` or `edit_file` to produce CR bytes; check the result with `cmp`.
- Add `tests/core/test_verbatim_copies.py` with one test. It reads both files in binary mode and asserts that the 13
  source lines, each with its own line ending, occur in `src/test/test_math_double3.cpp` as one contiguous block. Name
  the paths and the line range as constants, and cite the comment in `test_math_double3.cpp` that states them.
Outcome:
- `cmp <(sed -n 43,55p third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp) <(sed -n 24,36p src/test/test_math_double3.cpp)`
  prints nothing and exits 0.
- `git diff --ignore-cr-at-eol -- src/test/test_math_double3.cpp` prints nothing.
- The new test passes. With the file as M3-FIX-T3.21 committed it (`git stash` your change to it, or test a copy of
  `git show HEAD:src/test/test_math_double3.cpp`), the same test fails: record that failing run in your answer.
- `CHECK` exits 0.
Depends on: M3-FIX-T3.21.
allowedPaths: `src/test/test_math_double3.cpp`, `tests/core/test_verbatim_copies.py`.

## M3-FIX-T3.22: build hygiene (TQ.1 F9-F11, F13, F15; panel #5, #6, #9, #18)
Card: `docs/handoff/drafts/M3-fixups/T3.22-build-hygiene.md`.
- BOOT-0a has added `VENV` and `CMAKE_ARGS` to the Makefile. Keep both when the card edits the Makefile.
- The card's header-only doctest change must keep working with `-DFETCHCONTENT_SOURCE_DIR_DOCTEST=...`, as `CHECK`
  passes it.
Review findings: `docs/handoff/findings/M3-fixups-reviews.json`, key `review T3.22 executability`.
Depends on: M3-FIX-T3.21.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0. The card's MSVC checks are host-only.

## M3-FIX-T3.22b: doctest includes its standard headers, so MSVC compiles test_graph.cpp (T3.22 CI)
No card; this item is the specification.
Why:
- CI run 39016333578 (commit 6806293), job `windows`: MSVC stops on `src/test/test_graph.cpp` with error C2027, "use of
  undefined type 'std::basic_ostream<char,std::char_traits<char>>'", raised in MSVC's `<__msvc_string_view.hpp>` from
  line 180, `CHECK(mode == std::string_view("mode"))`, which M3-FIX-T3.22 added. Every other source compiled.
- doctest prints the operands of a CHECK with `operator<<`. For a `std::string_view`, MSVC's `operator<<` needs the
  complete `std::ostream`. By default doctest does not include `<ostream>`; it forward-declares `std::ostream` in
  `namespace std` (`MAIN/.cache/src/doctest/doctest/doctest.h` lines 517-552, v2.4.11), and on MSVC nothing else in this
  translation unit includes `<ostream>`. GCC with libstdc++ compiles the same line, so `CHECK` cannot show the failure.
- doctest's remedy is `DOCTEST_CONFIG_USE_STD_HEADERS` (`MAIN/.cache/src/doctest/doc/markdown/configuration.md`, the
  section of that name; `doctest.h` lines 508-516): doctest then includes `<cstddef>`, `<ostream>` and `<istream>`
  instead of declaring names in `namespace std`, which the standard forbids. The documentation says "This should be
  defined globally."
Do:
- In `src/test/CMakeLists.txt`, directly after `target_include_directories(painterly_doctest ...)`, add
  `target_compile_definitions(painterly_doctest INTERFACE DOCTEST_CONFIG_USE_STD_HEADERS)` with a comment that gives the
  reasons above in a few lines and cites the CI run, `test_graph.cpp:180` and doctest's `configuration.md`. As an
  INTERFACE definition it reaches every source of every target that links `painterly_doctest`, which is what "globally"
  asks for.
- Change nothing else. In particular, `src/test/test_graph.cpp` stays as it is.
Outcome:
- In `ninja -C build/q -t commands painterly_tests`, every line matching ` -c [^ ]*/src/test/[^ ]*\.cpp` (the compile
  command of a `src/test` source) contains `-DDOCTEST_CONFIG_USE_STD_HEADERS`. Record in your answer the number of such
  lines with it, the number without it (0), and the number of sources in `add_executable(painterly_tests ...)`; the
  first and the last are equal.
- `git show --stat --format= HEAD` lists only `src/test/CMakeLists.txt`.
- `CHECK` exits 0.
- Host-only, not run by you: the CI `windows` job compiles `test_graph.cpp`. The orchestrator reads it after landing.
Depends on: M3-FIX-T3.22.
allowedPaths: `src/test/CMakeLists.txt`.

## BOOT-0b: optional prebuilt Embree, so clones don't rebuild it
Why: every clone recompiles Embree's ISA kernels (several CPU-minutes per verify). The host can build Embree once.
Do:
- One source of truth for the build configuration Embree gets, in `cmake/`. That covers:
  - the `EMBREE_*` cache options in `cmake/painterly_embree.cmake`;
  - the root `CMakeLists.txt` settings that reach Embree through FetchContent: the C++ standard, position-independent
    code, visibility presets, the MSVC runtime, and `-ffp-contract=off -fno-fast-math` / `/fp:precise`.
  Both the FetchContent path and the prebuilt path use it.
- `tools/embree_prebuilt.py` (type hints and docstrings, ruff-clean), with two subcommands:
  - `build --source DIR --prefix DIR`: configures, builds and installs Embree from DIR with exactly that configuration;
  - `compare-flags --source DIR --embree-dir PREFIX/lib/cmake/embree-4.4.1`:
    - configures the project twice into temporary directories, both with `CMAKE_EXPORT_COMPILE_COMMANDS=ON`: once by
      FetchContent from DIR, and once against the install via `embree_DIR`;
    - for every Embree translation unit, compares the compile flags with absolute paths normalised;
    - prints `EMBREE FLAGS IDENTICAL: <n> units`, or the differing units and exits 1.
  Configuring only; no build is needed for the comparison.
- `cmake/painterly_embree.cmake`: when `embree_DIR` is set, use `find_package(embree 4.4.1 EXACT CONFIG REQUIRED)` and
  print `painterly_embree: prebuilt <dir>`; otherwise keep today's FetchContent path unchanged. Every target the rest of
  the build links keeps its name and usage requirements.
Outcome:
- `MAIN/.venv/bin/python tools/embree_prebuilt.py build --source MAIN/.cache/src/embree --prefix build/embree-install`
  exits 0.
- `compare-flags` with that install prints `EMBREE FLAGS IDENTICAL`.
- `CHECK`, with `-Dembree_DIR=<clone>/build/embree-install/lib/cmake/embree-4.4.1` appended to `CMAKE_ARGS`, exits 0.
  Its configure log shows the `prebuilt` line, its build compiles no Embree source, and the symbol audit passes.
- `CHECK` without `embree_DIR` also exits 0, so the default path is unchanged.
allowedPaths: `CMakeLists.txt`, `cmake/**`, `tools/embree_prebuilt.py`, `tests/core/test_embree_prebuilt.py`, `Makefile`, `docs/architecture.md`.
Depends on: M3-FIX-T3.22.

## M3-FIX-T3.23: shared test scaffolding (TQ.1 F14, F16-F18; panel #1)
Card: `docs/handoff/drafts/M3-fixups/T3.23-shared-test-scaffolding.md`.
Depends on: M3-FIX-T3.22.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M3-FIX-T3.24: kernel test coverage (TQ.1 F19-F21; panel #10-#12)
Card: `docs/handoff/drafts/M3-fixups/T3.24-kernel-test-coverage.md`.
- Every new test must fail when its branch is deliberately broken.
- Record each mutation experiment, and its revert, in your answer.
Depends on: M3-FIX-T3.23.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M3-FIX-T3.22c: MSVC /W4 reports in our code (T3.22 A8)
No card; this item is the specification.
Why:
- M3-FIX-T3.22 compiles our targets with `/W4` on MSVC, and its card (A8) records each report in our code for a
  follow-up. CI runs 39016333578 and 39022509265 (job `windows`) and wheels run 39020555326 (job `wheels (windows-2022)`)
  report exactly these three. Line numbers are as at 7c6369b.
  1. `src/painterly/kernel/camera/camera.h:67` C4305 "truncation from 'double' to 'float'" and `:68` C4244 "conversion
     from 'double' to 'float', possible loss of data", from `const float fovx = SMALLPAINT_PI / 4;` and
     `const float fovy = (h / w) * fovx;`. The roundings are deliberate: smallpaint declares fovx and fovy float
     (smallpaint_painterly.cpp:174-175, as the comment above the two lines says).
  2. `src/blender/selftest.cpp:94` C4245 "conversion from 'int' to 'unsigned int', signed/unsigned mismatch", from
     `rayhit.ray.mask = -1;`. Embree's `RTCRay::mask` is `unsigned int`, and -1 stands for every mask bit set. Only the
     wheel build compiles this file on MSVC.
  3. `third_party/cycles/util/transform.h(526)` C4702 "unreachable code", in the translation unit of
     `src/test/test_util.cpp`. With `__KERNEL_SSE42__`, `transform_inverse_dot` (lines 518-527) returns inside its `#if`
     block, so the portable `return dot(a_, b_);` after it is unreachable. The vendored file is never edited, and C4702
     comes from the code generator. Microsoft's documentation of `/external` (section "Limitations") says: "Some warnings
     emitted by the compiler's back-end code generation aren't affected by the /external options. These warnings usually
     start with C47XX, though not all C47XX warnings are back-end warnings. You can still disable these warnings
     individually by using /wd47XX."
Do:
- 1: write both conversions explicitly, `const float fovx = float(SMALLPAINT_PI / 4);` and
  `const float fovy = float((h / w) * fovx);` (the file already writes `double(fovx)`), and extend the comment above them
  to say that the explicit `float(...)` is smallpaint's implicit conversion. The values cannot change: an explicit
  conversion to float rounds exactly as the implicit one does.
- 2: `rayhit.ray.mask = ~0u;`, with a comment that every mask bit is set, so the ray sees every geometry (Embree's own
  examples write -1).
- 3: in `cmake/painterly_warnings.cmake`, the MSVC branch becomes `/W4 /wd4702`. Add a paragraph to the file comment
  with the reason: the transform.h case, the quotation above, and that GCC's and Clang's `-Wall -Wextra` contain no
  unreachable-code warning either, so the two warning sets stay comparable.
- Change nothing else.
Outcome:
- `git diff --stat` lists exactly the three files. In `camera.h` the diff changes only the two initializers and the
  comment above them; in `selftest.cpp`, only the mask line and its comment.
- `build/q/src/test/painterly_tests`, run before your change and after it, prints identical `[doctest] test cases:` and
  `[doctest] assertions:` summary lines, with nothing failed. Record both in your answer.
- `CHECK` exits 0.
- Host-only, not run by you: the CI `windows` job and the wheels `windows-2022` job report none of the three. The
  orchestrator reads them.
Depends on: M3-FIX-T3.22b, M3-FIX-T3.24, BOOT-0b.
allowedPaths: `src/painterly/kernel/camera/camera.h`, `src/blender/selftest.cpp`, `cmake/painterly_warnings.cmake`.

## M3-FIX-T3.27: vendor_sync reads the pinned commit's git objects (panel #0)
Card: `docs/handoff/drafts/M3-fixups/T3.27-vendor-sync-pinned.md`.
- The tests use a fixture upstream repository under `tmp_path`.
- Steps that need the real Blender checkout or the network are host-only.
- The card's dependency on T3.26 is batch order only.
Depends on: M3-FIX-T3.24.
Outcome: the card's Acceptance, translated; `CHECK` exits 0; `make vendor-check` with the `KNOBS` reports every vendored
file matching.

## M3-FIX-T3.28: licences, notices, docs and the wheels path filter (panel #3, #4, #8, #13-#16)
Card: `docs/handoff/drafts/M3-fixups/T3.28-licences-notices-docs.md`.
- `make wheel` and `unzip -l dist/*.whl` are host-only.
- Instead, check the licence globs with `MAIN/.venv/bin/python -c` against `pyproject.toml`, and say so.
Depends on: M3-FIX-T3.27.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M3-FIX-NODE24: GitHub Actions on the Node.js 24 runtime
Why:
- Every CI run warns: "Node.js 20 is deprecated. The following actions target Node.js 20 but are being forced to run on
  Node.js 24: actions/cache@v4, actions/checkout@v4" (CI 39101523186 on `2c8223e`). `wheels.yml` also uses
  `actions/setup-python@v5`, `actions/upload-artifact@v4` and `actions/download-artifact@v4`, which target Node.js 20 too.
- Opus read each action's `action.yml` (`runs.using`) at the newest tag of each major on 2026-10-18 (`git ls-remote
  --tags`, raw.githubusercontent.com). The first major on `node24` is checkout v5 (v5.1.0), cache v5 (v5.1.0),
  setup-python v6 (v6.3.0), upload-artifact v6 (v6.0.0) and download-artifact v7 (v7.0.0). `astral-sh/setup-uv@v7`
  (v7.6.0) is already on `node24`.
- Their release notes list nothing that affects this repo beyond the runtime and a minimum runner of 2.327.1, which
  GitHub-hosted runners exceed. download-artifact v5 changed only downloads by artifact ID; `wheels.yml` downloads by
  name.
Do:
- In `.github/workflows/ci.yml` and `.github/workflows/wheels.yml`, change exactly these `uses:` pins and nothing else:
  `actions/checkout@v4` → `actions/checkout@v5`, `actions/cache@v4` → `actions/cache@v5`, `actions/setup-python@v5` →
  `actions/setup-python@v6`, `actions/upload-artifact@v4` → `actions/upload-artifact@v6`, `actions/download-artifact@v4`
  → `actions/download-artifact@v7`.
- This includes the `actions/setup-python@v5` step that M6a-T6.3 adds to `ci.yml`'s `windows` job, which is why this
  item waits for M6a-T6.3.
- Leave `astral-sh/setup-uv@v7` and `pypa/cibuildwheel@v4.3.0` as they are, and leave the done cards under `docs/tasks/`,
  which record what ran.
- No build is needed: the change touches no file that `CHECK` builds, tests or lints.
Outcome:
- `git diff -U0 HEAD -- .github/workflows | grep -E '^[-+][^-+]' | grep -v -E '^[-+]\s+uses: actions/(checkout|cache|setup-python|upload-artifact|download-artifact)@v[0-9]+$'`
  prints nothing.
- `diff <(git show HEAD:.github/workflows/ci.yml HEAD:.github/workflows/wheels.yml | grep -o -E 'uses: [^@]+') <(cat .github/workflows/ci.yml .github/workflows/wheels.yml | grep -o -E 'uses: [^@]+')`
  prints nothing (the same actions, in the same order).
- `git grep -n -E 'actions/(checkout|cache)@v4|actions/setup-python@v5|actions/(upload|download)-artifact@v4' -- .github`
  prints nothing.
- `MAIN/.venv/bin/python -I -c "import yaml; [yaml.safe_load(open(f)) for f in ('.github/workflows/ci.yml','.github/workflows/wheels.yml')]; print('YAML-OK')"`
  prints `YAML-OK`.
- `git status --porcelain` lists exactly the two workflow files.
- Host only, after landing (Opus): the next CI run on the branch has no "Node.js 20 is deprecated" annotation.
allowedPaths: `.github/workflows/ci.yml`, `.github/workflows/wheels.yml`
Depends on: M3-FIX-T3.28, M6a-T6.3.

## M3-FIX-TQ2-CPP: the FMA canary can fail; one make_ray; a bound comment cites a real file (TQ.2 F1, F4, F7)
Why: `docs/audits/TQ.2.md`, checked by Opus at `f7b633d`.
- F1. The canary `dot() is not contracted into fused multiply-adds (the -ffp-contract=off canary)`
  (`src/test/test_math_double3.cpp:229`) cannot fail in any build the project makes. The tests compile with at most
  `-msse4.2` (`src/cycles/CMakeLists.txt:63`), and only `transform_avx2.cpp` gets `-mfma` (`:64-65`). Without an FMA
  instruction set GCC has nothing to contract, so deleting `-ffp-contract=off` (`cmake/painterly_embree_config.cmake:40`)
  passes every test.
- F4. `src/test/test_bvh.cpp:57-58` cites `docs/tasks/M3/T3.21-contract-touchups.md, appendix A`, which does not exist;
  the appendix is in `docs/handoff/drafts/M3-fixups/T3.21-contract-touchups.md`.
- F7. `PainterlyRay make_ray(const Triple &, const Triple &)` is defined identically in `src/test/test_analytic.cpp:88`
  and `src/test/test_bounce.cpp:143`.
Do:
- Compile `src/test/test_math_double3.cpp`, and only it, with FMA enabled when the compiler is GCC or Clang on x86-64, so
  that `-ffp-contract=off` is the only thing that keeps `dot()` from contracting. Choose the mechanism (a per-source
  compile option in `src/test/CMakeLists.txt`, or a target pragma in the file) and name it. Change no flag of any other
  source. Update the canary's comment to say which builds it guards.
- Correct the citation in `test_bvh.cpp`. If the sentence at `:73` ("relative errors from 1.0 u to 1.3 u") has no
  committed script or command behind it, add the command and its output to the comment, or delete the sentence.
- Move `make_ray` into a new header `src/test/test_ray.h` and include it from both files.
Outcome:
- `CHECK` exits 0.
- The mutation, in your clone and never committed: delete `-ffp-contract=off` from
  `cmake/painterly_embree_config.cmake:40`, configure and build into a separate directory `build/qm` with the same
  knobs, and `build/qm/src/test/painterly_tests -tc='*canary*'` exits non-zero. Then restore the file with
  `git checkout -- cmake/painterly_embree_config.cmake`. The report quotes the failing check and the exit status.
- `git grep -n 'docs/tasks/M3/T3.21-contract-touchups.md' -- src` prints nothing.
- `git grep -n 'PainterlyRay make_ray(const Triple' -- src/test` prints exactly one line, in `src/test/test_ray.h`.
- `git status --porcelain` lists only allowedPaths.
allowedPaths: `src/test/test_math_double3.cpp`, `src/test/CMakeLists.txt`, `src/test/test_bvh.cpp`, `src/test/test_analytic.cpp`, `src/test/test_bounce.cpp`, `src/test/test_ray.h`
Depends on: M3-T3.14.

## M3-FIX-TQ2-PY: the prebuilt-Embree proof runs and cannot pass empty; compare_results tells booleans from numbers (TQ.2 F2, F3, F5)
Why: `docs/audits/TQ.2.md`, checked by Opus at `f7b633d`.
- F2. `tests/core/test_embree_prebuilt.py:199-212` hard-codes this machine's paths to the Embree and doctest sources and
  sets `EMBREE_INSTALL = REPO_ROOT / "build" / "embree-install"`, which nothing creates (the host's install is
  `MAIN/.cache/embree-prebuilt/install`, R11). Both slow tests therefore skip on every run (`:227`, `:253`).
- F3. `ComparisonReport.identical` (`tools/embree_prebuilt.py:132-136`) is true when neither side has a unit, so
  `compare-flags` can print "EMBREE FLAGS IDENTICAL: 0 units": the vacuous pass its docstring (`:34-37`) says it avoids.
- F5. `tools/compare_results.py:182-183` compares leaves with Python `==`, so `true` against `1` and `false` against `0`
  count as identical, although the module docstring treats a boolean as not a number.
Do:
- `test_embree_prebuilt.py`: take the three paths from the environment variables `PAINTERLY_EMBREE_SOURCE`,
  `PAINTERLY_DOCTEST_SOURCE` and `PAINTERLY_EMBREE_INSTALL`, with no default path of this machine. A test skips, naming
  the variable, only when one is unset.
- `embree_prebuilt.py`: a comparison where either side has no unit is not identical, and `compare-flags` then exits
  non-zero with a message that says so. Add a test.
- `compare_results.py`: two leaves are identical only when their JSON types match as well as their values (booleans,
  integers, floats, strings and null are distinct). Say in the docstring whether `1` and `1.0` match, and why. Add tests
  for `true` against `1`, `false` against `0`, and your choice for `1` against `1.0`.
- Do not regenerate `docs/handoff/repro/`; if the new comparison would change a committed EXP-REPRO result, say which
  leaf in your answer.
Outcome:
- `CHECK` exits 0.
- `PAINTERLY_EMBREE_SOURCE=MAIN/.cache/src/embree PAINTERLY_DOCTEST_SOURCE=MAIN/.cache/src/doctest PAINTERLY_EMBREE_INSTALL=MAIN/.cache/embree-prebuilt/install PYTHONPATH="$PWD/analysis" MAIN/.venv/bin/python -m pytest -q -rs -m slow tests/core/test_embree_prebuilt.py`
  runs both slow tests and reports them passed, none skipped.
- Each new test fails against the files at HEAD; the report names each test and its failing line.
- `git grep -n '/run/media' -- tests tools src` prints nothing.
- `git status --porcelain` lists only allowedPaths.
allowedPaths: `tests/core/test_embree_prebuilt.py`, `tools/embree_prebuilt.py`, `tools/compare_results.py`, `tests/core/test_compare_results.py`
Depends on: BOOT-0b.

## M3-PROPAGATE: carry the fix-up renames into the cards not yet run
Why: T3.19-T3.24 renamed, moved or removed names that the later cards still use. Change each card text to match the code
at integration HEAD:
- `VERTEX_PASS` → `VERTEX_TINT` (decision D14, amended);
- `KernelPainterlyObject::tfm`/`itfm` and `PainterlyGlobalsCPU::tri_vertices` are gone, and `normal_to_world` is filled
  from `painterly_normal_matrix` (T3.21, D35). T3.13's device_update text changes to match: no "vertices expanded per
  triangle" and no "itfm with transform_inverse";
- `PAINTERLY_OBJECT_ID_MISS` now lives at kernel level; there is a lane clamp `L = min(lane_length, width)`; and
  `max_depth >= 1` (T3.20);
- the target names, the header-only doctest target and `painterly_kernel` (T3.22);
- the shared test headers `src/test/bitwise.h` and `src/test/smallpaint_ref.h`, which T3.17 must use (T3.23);
- TQ.1 F12 (the selftest traced through `painterly_bvh`) moves into T3.15 (D34): add it to T3.15's Goal and Modify list.
Outcome:
- `grep -n -E 'VERTEX_PASS|tri_vertices|\bitfm\b' docs/tasks/M3/T3.1[3-8]*.md docs/tasks/M4/*.md docs/tasks/M5/*.md`
  prints nothing.
- `docs/tasks/M3/AMENDMENTS-fixups.md` lists every edit: file, old text, new text and reason (the commit or decision).
- `make lint` with the `KNOBS` passes.
allowedPaths: `docs/tasks/M3/T3.13-scene.md`, `docs/tasks/M3/T3.14-session.md`, `docs/tasks/M3/T3.15-bindings.md`, `docs/tasks/M3/T3.16-oracle-parity.md`, `docs/tasks/M3/T3.17-triangle-path.md`, `docs/tasks/M3/T3.18-exp-throughput.md`, `docs/tasks/M4/**`, `docs/tasks/M5/**`, `docs/tasks/M3/AMENDMENTS-fixups.md`.
Depends on: M3-FIX-T3.24.

## M3-PROPAGATE-b: the rest of M3-PROPAGATE (T3.17's normal orientation, and the amendments record)
Why:
- M3-PROPAGATE's task edited only T3.13, T3.14 and T3.15. It was planned while that item's allowedPaths still wrapped
  over three lines, and the queue read only the first. Its commit is `fdc6357`, subject
  `t-propagate: M3-PROPAGATE: carry the fix-up renames into the cards not yet run`. The queue counts that item as done,
  so this item carries what is left.
- Its worker grepped T3.16-T3.18, M4 and M5 for every propagated name and found one edit still due: T3.17's
  normal-orientation line.
Do:
- `docs/tasks/M3/T3.17-triangle-path.md`: apply block 1 under "**`docs/tasks/M3/T3.17-triangle-path.md`**" in the section
  "Edits for later cards" of `docs/handoff/drafts/M3-fixups/T3.21-contract-touchups.md`, verbatim. Its "old" text is one
  line, leading spaces included. Find it by its text, not its line number, and replace that line with the block's "new"
  line. Change nothing else in the card.
- Create `docs/tasks/M3/AMENDMENTS-fixups.md`, the record M3-PROPAGATE's Outcome asks for. Write one entry per edit:
  - every hunk of `git show fdc6357 -- docs/tasks`, and the T3.17 edit of this item;
  - each entry gives the file, the old text and the new text as fenced `text` blocks copied byte for byte from the diff
    (without the diff's `-`/`+` column), and the reason: the fix-up or decision the edit carries (T3.20, T3.21 and D35,
    T3.22, T3.23, D34);
  - for an edit that a fix-up card specifies verbatim (T3.21's "Edits for later cards"), name that card and block.
Outcome:
- `git status --porcelain` lists exactly `docs/tasks/M3/T3.17-triangle-path.md` (modified) and
  `docs/tasks/M3/AMENDMENTS-fixups.md` (new).
- `git diff HEAD -- docs/tasks/M3/T3.17-triangle-path.md` removes exactly one line and adds exactly one line, which are
  byte-identical to the block's old and new text.
- Every old and new text in `AMENDMENTS-fixups.md` is byte-identical to the corresponding removed and added lines of
  `git show fdc6357 -- docs/tasks` or of the T3.17 edit. Every hunk of both appears in it exactly once.
- M3-PROPAGATE's grep still prints nothing:
  `grep -n -E 'VERTEX_PASS|tri_vertices|\bitfm\b' docs/tasks/M3/T3.1[3-8]*.md docs/tasks/M4/*.md docs/tasks/M5/*.md`.
- `make lint` with the `KNOBS` passes.
allowedPaths: `docs/tasks/M3/T3.17-triangle-path.md`, `docs/tasks/M3/AMENDMENTS-fixups.md`
Depends on: M3-PROPAGATE.

## M3-T3.13: painterly/scene (host scene, reflected PainterlyIntegrator, device_update)
Card: `docs/tasks/M3/T3.13-scene.md`. Depends on: M3-PROPAGATE.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M3-T3.14: painterly/session (asynchronous, cancellable render sessions)
Card: `docs/tasks/M3/T3.14-session.md`. Depends on: M3-T3.13.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M3-FIX-T3.13a: painterly/scene follow-ups (spiral-frame and fill tests, the R(e) bound, exception safety)
Why: the landing review of t-m3-13b (`70d1e66`) found these, and Opus checked each one at that commit:
1. No test sets a nonzero `spiral_rotation` for the `camera` or `smallpaint` frame, or for `object` with a rotation other
   than the identity (`src/test/test_scene.cpp:553-632`). So reversing either product in `device_scene.cpp`, or giving
   `smallpaint` the rotation, passes every test.
2. The scene-level fill is untested. The tests read only `ds.data.integrator.spiral_frame`, and test the jitter on
   `PainterlyCamera` alone (`test_scene.cpp:634-698`). Deleting `integrator.device_update(...)`, the
   `camera.device_update(...)` call or `background.device_update(...)` in `device_scene.cpp` passes every test (the
   audit's surviving mutants).
3. The bound comment at `test_scene.cpp:76-89` miscounts. A product of three library results has three library roundings
   and two multiply roundings, not three. "Within 1 ulp" allows a relative error of 2^-23, not 2^-24. Its "0.40 of its
   bound" names no committed script.
4. `PainterlyScene::device_update` rewrites the device scene before checks that can throw (mesh index, singular
   transform, spiral object, unknown frame, Embree), and it calls `bind_globals()` only at the end. After a throw, the
   globals therefore point into reallocated arrays.
5. `material.h:36` lets a NaN weight through: `lobe.weight.x < 0.0` is false for NaN. The ior check at `:39` is NaN-safe.
   `object.h` uses `CCL_NAMESPACE_BEGIN` without including a header that defines it.
Ruling (Opus, 2026-10-18): the deviation at `device_scene.cpp:182-194` is accepted.
- An object whose mesh has no triangles cannot be hit. Its `normal_to_world` therefore stays zero, and its
  `object_to_world` is not checked for singularity.
- `painterly_embree_scene_create` skips such an object in exactly the same way.
- The card is synced below.
Do:
- `src/test/test_scene.cpp`: add tests. Each of these mutations of `src/painterly/scene/device_scene.cpp` must make at
  least one of them fail. Apply the mutations one at a time, to a scratch copy, never committed:
  - (m1) `painterly_matmul_3x3(temp, rotation, frame);` → `painterly_matmul_3x3(rotation, temp, frame);`
  - (m2) `painterly_matmul_3x3(spiral_object_rotation_, rotation, frame);` → `painterly_matmul_3x3(rotation, spiral_object_rotation_, frame);`
  - (m3) in the `SPIRAL_FRAME_SMALLPAINT` branch, `frame[i] = identity[i];` → `frame[i] = rotation[i];`
  - (m4) delete the line `integrator.device_update(ds.data.integrator);`
  - (m5) in `camera.device_update(ds.data.cam, double(integrator.get_jitter()));`, replace `double(integrator.get_jitter())` by `0.0`
  - (m6) delete the line `background.device_update(ds.data.background, ds.suns);`
  The expected values follow the card's rules: exact where the arithmetic is exact (e = 0, axis-permutation rotations),
  otherwise the float32 bound derived as below. Never compare the code with its own output.
- `PainterlyScene::device_update` gives the strong guarantee. Build the new arrays and the Embree scene in locals, and
  only once every check has passed, move them into the device scene and call `bind_globals()`. Add a test: after a
  successful `device_update`, make each throwing path throw in turn (an out-of-range mesh index; a singular
  `object_to_world` on a mesh with triangles; frame `object` with no spiral object; an unknown `spiral_frame`). Catch
  `std::invalid_argument`, then check that every array of the device scene has its earlier size and contents, the
  kernel data is unchanged, and every pointer `bind_globals()` sets still points into the device scene's own arrays.
- Rewrite the comment at `test_scene.cpp:76-89` so the bound counts every rounding that `euler_to_transform`
  (`util/transform.h:246-256`) and the reference actually perform. State the library-accuracy assumption it rests on.
  Compute the resulting factor with a command, for example exact `fractions` arithmetic, and quote the command and its
  output in the comment. Delete the "0.40 of its bound" sentence. Change `F32_SPIRAL_ENTRY_FACTOR` only to that
  derived factor.
- `src/painterly/scene/material.h`: write the weight check in the NaN-safe form of the ior check. Add a test that a NaN
  weight in any channel raises `std::invalid_argument`.
- `src/painterly/scene/object.h`: include the headers it uses, including the one that defines `CCL_NAMESPACE_BEGIN`.
- `docs/tasks/M3/T3.13-scene.md`, to sync the card with the ruling:
  - after "A singular `object_to_world` makes `device_update` throw `std::invalid_argument`", add "when its mesh has
    triangles (an object whose mesh has none cannot be hit; its `normal_to_world` stays zero and is not checked, as
    `painterly_embree_scene_create` skips it: Opus ruling, 2026-10-18)";
  - in the `src/test/test_scene.cpp` bullet, "`normal_to_world` of every object" becomes "`normal_to_world` of every
    object whose mesh has triangles";
  - record both edits in `docs/tasks/M3/AMENDMENTS-fixups.md`, in its existing entry format.
Outcome:
- `CHECK` exits 0, with R12's prefix and R11's `-Dembree_DIR`.
- For each of m1-m6, applied alone to a scratch copy of the clone and rebuilt, `build/q/src/test/painterly_tests` exits
  non-zero. The report lists each mutation with the name of a failing test case.
- `git grep -nF '0.40 of its bound' -- src/test/test_scene.cpp` prints nothing. The new bound comment quotes its
  command and that command's output.
- `git diff HEAD -- docs/tasks/M3/T3.13-scene.md` shows exactly the two edits above.
- `git status --porcelain` lists only files in allowedPaths.
allowedPaths: `src/painterly/scene/device_scene.cpp`, `src/painterly/scene/device_scene.h`, `src/painterly/scene/scene.h`, `src/painterly/scene/scene.cpp`, `src/painterly/scene/material.h`, `src/painterly/scene/object.h`, `src/test/test_scene.cpp`, `docs/tasks/M3/T3.13-scene.md`, `docs/tasks/M3/AMENDMENTS-fixups.md`
Depends on: M3-T3.13.

## M3-FIX-T3.13b: painterly/scene test strength and single definitions (TQ.2 F6, F7)
Why: `docs/audits/TQ.2.md`, checked by Opus at `f7b633d`.
- `src/test/test_scene.cpp:653` and `:655` check the same value twice: `expected = 2.0 * jitter`, with `jitter`
  `double(1.0f / 1400.0f)` (`:637`), then the literal `2.0 * double(1.0f / 1400.0f)`, which the comment calls the
  reference.
- The test at `test_scene.cpp:280-313` uses only dyadic values (0.5f, 0.25f, 8, 0.125f). Their float32 and decimal forms
  agree, so it cannot tell the card's `double(float)` widening from a decimal round trip.
- M_s->cam is defined twice, as transposes (`src/painterly/scene/camera.cpp:20`, `device_scene.cpp:45`), and the 3x3
  identity three times (`scene.h:104`, `scene.cpp:32`, `device_scene.cpp:209`). `camera.cpp:6` includes a header it does
  not use.
Do:
- Replace the second jitter check with an independent reference: the bits of `2 * double(float32(1/1400))` as a
  hex-float literal computed by a command you run (for example with Python's `struct`); put the command and its output
  in the comment.
- Add a non-dyadic value (for example `0.1f`, where `double(0.1f) != 0.1`) to the test at `:280-313`, with its expected
  bits computed the same way.
- Define M_s->cam once (derive the transpose from it, or both from one table) and the 3x3 identity once, shared by the
  three files; remove the unused include. Output stays bit-identical: every existing test passes unchanged.
Outcome:
- `CHECK` exits 0.
- The mutation, in your clone and never committed: in the conversion the `:280-313` test covers, replace `double(x)` by
  `std::stod(std::to_string(x))`, rebuild, and `build/q/src/test/painterly_tests` exits non-zero; the report names the
  failing case. Then restore the file with `git checkout --`.
- `git status --porcelain` lists only allowedPaths.
allowedPaths: `src/test/test_scene.cpp`, `src/painterly/scene/camera.cpp`, `src/painterly/scene/camera.h`, `src/painterly/scene/device_scene.cpp`, `src/painterly/scene/scene.h`, `src/painterly/scene/scene.cpp`
Depends on: M3-FIX-T3.13a.

## M3-T3.15: the _painterly Python API exactly as in _painterly.pyi
Card: `docs/tasks/M3/T3.15-bindings.md`.
- M3-FIX-T3.28 also edits `src/blender/CMakeLists.txt`, so this item waits for it.
- The card gained `src/blender/selftest.h` and `src/blender/selftest.cpp` in M3-PROPAGATE (`fdc6357`).
Outcome: the card's Acceptance, translated; `CHECK` exits 0; and the symbol audit passes.
allowedPaths: `src/blender/selftest.h`, `src/blender/selftest.cpp`, `src/blender/python.cpp`, `src/blender/CMakeLists.txt`, `tests/core/test_api_contract.py`
Depends on: M3-T3.14, M3-FIX-T3.28.

## M3-T3.16: exact parity with smallpaint_oracle, bit for bit
Card: `docs/tasks/M3/T3.16-oracle-parity.md`. Depends on: M3-T3.15.
- The oracle here is the dev build's `build/q/src/app/smallpaint_oracle` with `--halton exact` (SPEC §2).
- Never use MAIN's experiments' oracle.
Outcome: the card's Acceptance, translated; `CHECK` exits 0. The card's slow 400 px test must pass too:
`PYTHONPATH="$PWD/analysis" PAINTERLY_BUILD_DIR="$PWD/build/q" /run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -m pytest -q -m slow tests/core/test_oracle_parity.py` (R12).

## M3-T3.17: triangle path statistically matches the oracle
Card: `docs/tasks/M3/T3.17-triangle-path.md`. Depends on: M3-T3.16.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M3-T3.18: experiment, CPU throughput of the native core
Card: `docs/tasks/M3/T3.18-exp-throughput.md`. Depends on: M3-T3.17.
- The experiment takes the next free number at run time (007-009 exist) and today's date.
- It follows `docs/tasks/M1/_experiment_protocol.md`.
- The machine is shared, so report the load (`uptime`) before and after each measurement.
- Its Conclusion is a DRAFT.
Outcome: the card's Acceptance, translated; `CHECK` exits 0; and the README has exactly the five sections.

## M3-FIX-T3.17a: the triangle scene differs from the oracle in regions r6 and r7 (find the cause, fix it)
Card: `docs/tasks/M3/T3.17-triangle-path.md`; its Goal is the specification: replacing smallpaint's six planes with quads
leaves the look statistically indistinguishable from the oracle. Depends on: M3-T3.17.
Closed (Opus, 2026-10-23): t-fix317a measured the cause, and it is in the test's design (the `image` chain), so this
item's report_blocked branch applies. M3-FIX-T3.17b continues the work; don't emit another task for this item.
Evidence (Opus, 2026-10-22, a fresh clone of T3.17's commit; the card's slow test with only `SEED_BLOCK` changed, the
blocks fixed before any run):
- Block 68, the committed block, passes, but with `r6.mean.R` p = 6.2e-4 and `r7.mean.B` p = 4.7e-4 against Holm's first
  threshold 0.01/25 = 4e-4.
- Of the ten fresh blocks 69-78, seven reject: 69 (`r6.mean.R/G/B`), 70 (`r6.mean.B`), 71 (`r7.mean.G`), 73
  (`r7.mean.G/B`), 74 (`r7.mean.B`), 77 (`r3.mean.R/B`, `r6.mean.R/G/B`, `r7.mean.G/B`) and 78 (`r7.mean.G`); 72, 75
  and 76 pass. Under the card's claim a block rejects with probability at most 0.01.
- At block 70, `r6.mean.R` is 28.2922 in the triangle scene against the oracle's 28.3592 (-0.24%, Cohen's d -2.6), and
  `r7.mean.B` is 75.3262 against 75.2006 (+0.17%). The triangle scene draws 1 332 185 743 samples against the oracle's
  1 333 088 459 (-0.07%); all 11 blocks show the same shortfall, 0.06-0.07%.
Do:
- Measure before you change anything. On the same rays (same seed and jitter) in `build_smallpaint_scene` and
  `build_smallpaint_scene_triangles`, report for both scenes, per bounce: the rays that hit nothing (the box is closed,
  so the analytic scene should have none), the hits closer than `ray_epsilon`, the hits whose shading normal faces away
  from the incoming ray, the bounce at which the two scenes' paths first hit different objects, and the mean path
  length. A 64 px render is enough. Name the harness, and keep it if it becomes the test below.
- Fix the cause where it is: the core's mesh path or `build_smallpaint_scene_triangles`. Never change the card's
  decision rule, its key family, `ALPHA`, `SEED_BLOCK = 68`, `SLOW_PAIRS` or `PLANE_EXTENT`. If the cause is in the
  test's design rather than in the code it tests, call report_blocked with the numbers.
- Add a test that pins the cause: it fails at HEAD and passes after the fix. Quote both runs.
Outcome:
- `CHECK` exits 0, and the card's slow test passes at block 68.
- On your committed tree, the same slow test at blocks 69-78 rejects at most 1 of the 10: for each block change only
  `SEED_BLOCK`, in place, run the slow test, then restore the file with `git checkout -- tests/core/test_triangle_path.py`.
  Report each block's rejected keys, or "passed". These ten blocks are fixed now; don't add, drop or replace any.
allowedPaths: `src/painterly/bvh/**`, `src/painterly/kernel/**`, `src/painterly/scene/**`, `src/test/**`, `tests/core/scenes.py`, `tests/core/test_triangle_path.py`
resources: `mem=6G cpus=4 time=6h`
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest" && PYTHONPATH="$PWD/analysis" PAINTERLY_BUILD_DIR="$PWD/build/q" /run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -m pytest -q -m slow tests/core/test_triangle_path.py`

## M3-FIX-T3.17b: the triangle path's slow test runs Blender's `row` chain
Closed (Opus, 2026-10-23): t-fix317b's report_blocked holds. Under `row` on both sides, block 68 fails and 7 of blocks
69-78 reject. The quad scene's raw radiance is lower in `r6` (by 0.15-0.24%) and higher in `r7` (by 0.09-0.27%), with the
same signs in all 8 blocks measured and under both chains. The card's amendment is withdrawn, and M3-FIX-T3.17c takes
the bias.
Card: `docs/tasks/M3/T3.17-triangle-path.md`, its Goal and its Slow bullet as amended on 2026-10-23. Depends on: M3-T3.17.
Why (Opus, 2026-10-23):
- Under `image` the triangle scene is distinguishable from the oracle. Of the fixed fresh blocks 69-78, seven reject on
  `r3`, `r6` and `r7` means (M3-FIX-T3.17a's evidence; t-fix317a reproduced the list exactly).
- t-fix317a found no defect in the shading. With one chain per pixel, the two scenes' region means agree to 1e-7
  relative. The quads draw 0.06-0.07% fewer samples in every block, and `image` runs one K sequence through the whole
  render without a reset (SPEC §3), so the shortfall moves the sample window of every later pixel.
- Blender renders are meshes, and they use `row` (SPEC §3): one chain per (row, pass), with K0 drawn per row, so a
  shortfall stays inside its row. The card took `image` from T3.16, whose bit-for-bit parity needs it; T3.16's parity
  test already covers the analytic scene under `row`.
Do:
- In `tests/core/test_triangle_path.py`, run the slow ensemble with `chain="row"` on the core and `chain="row"` in the
  oracle's jobs. Change no other parameter: the key family, `ALPHA`, `SEED_BLOCK = 68`, `SLOW_PAIRS`, `PLANE_EXTENT`,
  `SLOW_SIZE`, `SLOW_PASSES`, the ghost setting and the knobs stay as they are.
- Keep printing `k_consumed` against the oracle's, without asserting it.
- Say in the module docstring and the comments why the chain is `row`, and quote the `image` result above.
Outcome:
- `CHECK` exits 0, and the slow test passes at block 68.
- On your committed tree, the slow test at blocks 69-78 rejects at most 1 of the 10. For each block change only
  `SEED_BLOCK`, in place, run the slow test, then restore the file with `git checkout -- tests/core/test_triangle_path.py`.
  Report each block's rejected keys, or "passed". These ten blocks are fixed now; don't add, drop or replace any.
- If 2 or more of the 10 reject, call report_blocked with each block's rejected keys. Don't change the chain again, or
  anything else in the test.
allowedPaths: `tests/core/test_triangle_path.py`
resources: `mem=6G cpus=4 time=6h`
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1" && PYTHONPATH="$PWD/analysis" PAINTERLY_BUILD_DIR="$PWD/build/q" /run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -m pytest -q -m slow tests/core/test_triangle_path.py`

## M3-FIX-T3.17c: find why the triangle scene draws 0.06-0.07% fewer samples, and remove the cause if it is a defect
Card: `docs/tasks/M3/T3.17-triangle-path.md`. Depends on: M3-T3.17.
Why (Opus, 2026-10-23, at Micah's request):
- In all 11 seed blocks of the steward's check, the triangle scene draws 0.06-0.07% fewer samples than the oracle under
  `image` (M3-FIX-T3.17a's evidence). This item is about the shortfall itself, so that the triangle path also matches the
  oracle in the reference mode.
- M3-FIX-T3.17b (closed) tried `row` on both sides, and the difference stayed. The quad scene's raw radiance is lower in
  `r6` (by 0.15-0.24%) and higher in `r7` (by 0.09-0.27%), with the same signs in all 8 blocks measured and under both
  chains. So the target is that radiance bias, and the sample shortfall may be one of its symptoms. The queue task no
  longer waits for T3.17b (repointed to t-fix317a).
- t-fix317a reported the following. Measure it again here; don't take it as given.
  - With one chain per pixel, the quad scene uses fewer K than the analytic scene on 1801 pixels and more on 347.
    Moving the analytic planes by 1e-5 to 1e-3 instead gives an even split.
  - The split narrows with `ghost="lights"` (154 against 135) and with `ghost="none"` (327 against 177).
  - After a quad hit, the next ray meets the same wall closer than `ray_epsilon` about 3 times as often as after an
    analytic hit (618 against 205 at bounce 1, 64 px).
  - Its explanation, untested: a float32 hit point moves the next ray's origin, and near a ghost sphere's silhouette
    that changes whether the ghost root passes `eps`.
Do:
- Measure before you change anything. Render `build_smallpaint_scene` and `build_smallpaint_scene_triangles` at 400 px,
  P = 32, seed 1088 (block 68's first), with one chain per pixel (`chain="lane"`, `lane_length=1`), so that both
  scenes start every pixel from the same K0. Report:
  - the per-pixel K difference (quad minus analytic): how many pixels lose K, gain K and are equal;
  - for the pixels that differ, where the two paths first part: the bounce, the object each scene hits, and whether a
    ghost sphere's root is what changed;
  - the signed distance of the hit points from their plane in both scenes: its mean, and the fractions in front of and
    behind the plane;
  - the same counts with the quads' `plane_extent` at 6 instead of 50, as a diagnostic only.
  Report every number with its command. Name the harness.
- If the cause is in the core's mesh path (for example, hit points that land behind the plane more often than in
  front), fix it there. Add `tests/core/test_triangle_samples.py`, marked slow, that runs the sign-flip test of the
  Outcome below. It fails at HEAD and passes after the fix; quote both runs.
- If the cause is not a defect in our code, call report_blocked with the measurements. Never change the analytic
  scene, `build_smallpaint_scene_triangles`, the oracle, `ray_epsilon`, `PLANE_EXTENT` or any test's decision rule to
  close the gap.
Outcome:
- `CHECK` exits 0, and the card's slow test passes at block 68 with the chain your tree's test file uses.
- At 400 px, P = 32, seed 1088 and one chain per pixel, the per-pixel K differences of the pixels that differ are
  centred on zero: `ensemble.sign_flip_pvalue(differences, "two-sided")` gives p >= 0.01, the card's `ALPHA`. If no
  pixel differs, the test passes and says so. Report the pixels that lose and gain K and p, before and after the fix.
- On your committed tree, the card's slow test with `chain="image"` on both sides rejects at most 1 of the fixed blocks
  69-78. For each block change only the chain (if your tree's test uses `row`) and `SEED_BLOCK`, in place, run the slow
  test, then restore the file with `git checkout -- tests/core/test_triangle_path.py`. Report each block's rejected
  keys, or "passed". If 2 or more reject, call report_blocked with the numbers.
- Report the samples drawn by the triangle scene and by the oracle at block 68 under `image`, before and after.
allowedPaths: `src/painterly/bvh/**`, `src/painterly/kernel/**`, `src/painterly/scene/**`, `src/test/**`, `tests/core/test_triangle_samples.py`
resources: `mem=6G cpus=4 time=6h`
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1" && PYTHONPATH="$PWD/analysis" PAINTERLY_BUILD_DIR="$PWD/build/q" /run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -m pytest -q -m slow tests/core/test_triangle_path.py tests/core/test_triangle_samples.py`

## M3-FIX-T3.15a: set_integrator raises ValueError for every bad knob, and a failed call sets nothing
Card: `docs/tasks/M3/T3.15-bindings.md`, the `Scene.set_integrator` bullet (lines 18-27). Depends on: M3-T3.15.
Why:
- t-m3-15c (accepted 2026-10-22) raises `TypeError` for a wrong type at seven sites on the set_integrator path of
  `src/blender/python.cpp` (`as_real`, `as_integer`, the boolean, enum and vector cases, and the default branch).
- `tests/core/test_api_contract.py` asserts `TypeError` for `chain=1`, `lane_length="16"`, `two_sided=1`, `alpha="0.5"`
  and `spiral_rotation=(0.0, 0.0)`.
- Card line 24 says set_integrator "raises `ValueError` on unknown names, wrong types, enum identifiers that are not in the
  socket's items, and values that break a kernel precondition". The CONTRACT `src/blender/_painterly.pyi:125` says
  "unknown names or bad values raise ValueError", and never names TypeError.
- set_integrator also sets each knob as it goes, so a call that raises leaves the knobs before the bad one set.
Do:
- Every failure on the set_integrator path raises `ValueError`, keeping today's messages: unknown name, wrong type,
  unknown enum identifier, out of range, and the three kernel preconditions. Don't change the array checks of the other
  Scene methods (card line 30 allows `TypeError` there).
- Look up and convert every knob before setting any, so a call that raises changes nothing.
- `tests/core/test_api_contract.py`: the five wrong-type cases expect `ValueError` (Opus ruling R44, 2026-10-22;
  provenance: card line 24 and `_painterly.pyi:125`). Add one test: a call with a good knob and then a bad one raises,
  and `get_integrator()` is unchanged.
Outcome:
- `CHECK` exits 0.
- Each changed or new test fails against HEAD; name it and quote the failure.
- In `src/blender/python.cpp`, no `nb::type_error` is reachable from set_integrator; list the remaining `type_error` lines
  and the method each belongs to.
allowedPaths: `src/blender/python.cpp`, `tests/core/test_api_contract.py`

## M3-FIX-T3.17d: the triangle tests assert only what holds on every machine, and say what was measured
Why (Sonnet landing review, 2026-10-23; Opus): this item makes T3.17a's doctest portable before it lands. Until then,
the landing of 2026-10-23 holds the doctest back.
- `src/test/test_triangle_diagnostics.cpp` (M3-FIX-T3.17a) CHECKs exact counts of a chaotic walk (about lines
  505-518: 4049, 75964 and 75966, 66503 and 66471, 29497 and 63398). These counts are driven by about 47 paths whose
  float32 hits fall on either side of an edge, and Embree's hit distance depends on the instruction set
  (`src/test/test_bvh.cpp:30-72`). CI builds on ubuntu-24.04 and under MSVC on windows-2022, so these counts need not
  hold there.
- Its header (about lines 21-33 and 477-498) calls the two scenes "the same scene". M3-FIX-T3.17b has since measured a
  radiance bias in `r6` and `r7` under both chains, and its cause is open (M3-FIX-T3.17c).
- `tests/core/test_triangle_path.py` still says the triangle path matches the oracle. The card's Status bullet
  (`docs/tasks/M3/T3.17-triangle-path.md`) records that the match is refuted at fresh seeds.
Do:
- In `src/test/test_triangle_diagnostics.cpp`:
  - turn every exact count of either walk into `MESSAGE` output: path lengths, `k_total` constants, equal-path counts and
    normal mismatch counts;
  - keep the checks that hold on any machine: `k_total` equals the kernel's own trace for both scenes, no misses at
    any bounce, and every path reaches bounces 0 and 1;
  - check the quad's shading normal against the plane's `n` by value (`==`, so -0.0 equals +0.0) on every hit, instead
    of counting bitwise mismatches;
  - fix the comment that gives +2.7e-4 for a difference the numbers put at +2.6e-5. Re-derive it with a command and
    quote that.
  - reword the header so the cause of the difference is open (M3-FIX-T3.17c), not "the same scene";
  - keep the `TEST_CASE` name: the verify finds the case by its prefix `painterly scene: the quad scene`.
- In `tests/core/test_triangle_path.py`, change no assertion, parameter or seed. The module docstring and the slow
  test's comments should say:
  - the slow test's pass at block 68 is not evidence of a match;
  - quote the card's Status numbers, and the smallest p-value and its Holm threshold from one run of the slow test at
    block 68 (quote the command and output).
- Never search for values or seeds that pass.
Outcome:
- `CHECK` exits 0.
- The doctest case still runs and passes.
- The doctest fails if a quad's shading normal is replaced by a constant. Show the mutation and its failure, then
  restore it.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1" && build/q/src/test/painterly_tests --test-case='painterly scene: the quad scene*' | grep -qE '^\[doctest\] test cases: +1 \| +1 passed \| +0 failed \|'`
allowedPaths: `src/test/test_triangle_diagnostics.cpp`, `tests/core/test_triangle_path.py`
Depends on: M3-FIX-T3.17a.

## M3-FIX-TOL-a: comments that derive two analysis-test tolerances (landing review F1)
Card: none; this item is the specification. CLAUDE.md golden rule 2 lets a unit test of numerical code use a tolerance
only with a comment that justifies it, and `experiments/007-2026-10-15-noise-locking/PLAN.md` (lines 84-85 and 119-121)
asks the same of EXP-007's library tests. Two of them have no such comment:
- `analysis/tests/test_scale_metrics.py:157-159`:
  `assert_allclose(along_columns, along_rows, rtol=1e-12, atol=1e-12 * float(np.max(np.abs(field))))`;
- `analysis/tests/test_report.py:570`: `pytest.approx(..., rel=1e-12, abs=0.0)`.
Do:
- Above each, add a comment that derives the bound as rule 2 allows: name the identity the test checks, the float64
  arithmetic the code under test does, and why that round-off stays within the bound (and its `atol` term).
- Never change a value or a line of code. If a tolerance can't be derived that way, call report_blocked and say why.
Outcome:
- `CHECK` exits 0.
- The commit adds comment lines only:
  `git diff HEAD~1 -- analysis/tests | grep -E '^[+-]' | grep -vE '^(\+\+\+|---)' | grep -vE '^\+\s*#'` prints nothing.
allowedPaths: `analysis/tests/test_scale_metrics.py`, `analysis/tests/test_report.py`

## M3-FIX-TQ2-REPRO: a committed generator rebuilds REPRO.json and REPRO.md byte for byte (TQ.2 F9)
Card: none; this item is the specification.
Why:
- TQ.2 F9 (`docs/audits/TQ.2.md`, row F9): `docs/handoff/repro/REPRO.json` and `REPRO.md` were written by a generator
  that lived in the EXP-REPRO worker's git-ignored `.tmp/`, so they cannot be regenerated, and R17's exact checks
  (RULINGS S2) rest on them.
- REPRO.md's "Largest difference" table names one path where several leaves tie: 002 `max_abs_diff` (2 leaves), 003
  `max_rel_diff` (2) and 006 `max_abs_diff` (3). The rule that picked it is written nowhere.
- The inputs are in the tree: the committed files in `experiments/<NNN>-*/`, and this machine's analysis outputs as
  R17 recorded them. Those are `docs/handoff/repro/host/<NNN>/results.json`, plus the figures, which EXP-REPRO-HOST
  found byte-identical to the committed ones.
Do:
- Write `tools/repro_report.py`, a CLI in the style of `tools/compare_results.py`. Its input is `--outputs <dir>`, with
  one directory per experiment (`<dir>/<NNN>/` holds the files an `analyze.py --out-dir` run writes). It writes
  `REPRO.json` and `REPRO.md` to `--out <dir>`:
  - per experiment and per output file, `identical`: the file equals the committed file of the same name in
    `experiments/<NNN>-*/`, byte for byte (what EXP-REPRO did with `cmp`);
  - for each `results.json` that is not identical, the report of `compare_objects` from `tools/compare_results.py`
    (import it; don't copy it) and `non_numeric_identical`;
  - `all_identical`, and REPRO.md's tables and text, in the committed files' layout.
- Name the rule for tied leaves in the docstring, choosing one that reproduces all three committed choices. If no rule
  does, call `report_blocked` with the tied paths.
- `tests/core/test_repro_report.py`, on synthetic inputs under `tmp_path`: an identical and a differing figure, a
  `results.json` with one numeric difference, two tied leaves (the named rule decides), and `all_identical` true and
  false. Each test must fail when the code it covers changes. Name one such mutation per test in your answer, for
  example the tie rule reversed.
- Never edit `docs/handoff/repro/` or `tools/compare_results.py`, and never run an analysis.
Outcome:
- `CHECK` exits 0.
- Built from the recorded inputs (each committed `fig_*.png` and the host `results.json`, copied to
  `.cache/repro-gen/in/<NNN>/`), the tool's `REPRO.json` and `REPRO.md` equal the committed files byte for byte (`cmp`).
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1" && PYTHONPATH="$PWD/analysis" /run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -m pytest -q tests/core/test_repro_report.py && rm -rf .cache/repro-gen && for n in 001 002 003 004 006; do mkdir -p .cache/repro-gen/in/$n && cp experiments/$n-*/fig_*.png docs/handoff/repro/host/$n/results.json .cache/repro-gen/in/$n/ || exit 1; done && PYTHONPATH="$PWD/analysis" /run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python tools/repro_report.py --outputs .cache/repro-gen/in --out .cache/repro-gen/out && cmp .cache/repro-gen/out/REPRO.json docs/handoff/repro/REPRO.json && cmp .cache/repro-gen/out/REPRO.md docs/handoff/repro/REPRO.md`
allowedPaths: `tools/repro_report.py`, `tests/core/test_repro_report.py`

## M3-FIX-TQ3a: the session's tests fail under the mutations that would break the add-on (TQ.3 F1-F4, F12-F15)
Why (audit TQ.3, `docs/audits/TQ.3.md`, 2026-10-24): `src/painterly/session` (T3.14) reads correctly, but its tests pass
under mutations the add-on's render loop would not survive: `wait(timeout)` returning true while a render runs (F1), a
destructor without `cancel()` (F2), an unlocked copy (F3), a restart without its join or resets (F4), and `elapsed`
growing after a render (F12). Three edge cases are open: two threads starting one Session (F13), a failed thread start
(F14) and a non-finite timeout (F15).
Do:
- In `src/test/test_session.cpp`, add test cases that fail under each mutation of `src/painterly/session/session.cpp`
  below. Show each mutation and its failure in your answer, then restore it. No case may assert a latency bound (D27).
  - `wait` returning `true` unconditionally (line 84): right after `start()` of a render with far more passes than can
    finish soon (for example a large `passes` on a small image), `wait(0.0)` returns false; then `cancel()`, and
    `wait(-1.0)` returns true.
  - No `cancel()` in the destructor (line 24): a case that sees the difference without a timing bound. If there is
    none, say why and leave this one out.
  - Restart (lines 48-50, 62, 67): after a finished render, `start()` again on the same Session with another pass
    count gives buffers equal, bit for bit, to a fresh Session's render with that pass count, with an empty error; a
    `cancel()` made between the two renders does not cancel the second.
  - The copy's lock (lines 108 and 149): while a render runs, read `buffers_copy()` and `progress()` repeatedly and
    check an invariant that a torn copy breaks; name the invariant. If none exists, say so.
  - `elapsed` (lines 99-100): after the render finishes, two `progress()` calls with a sleep between them report the
    same `elapsed`.
- In `session.cpp`: if constructing the render thread throws, restore the state the session had and rethrow (F14). A
  NaN, an infinite timeout, or one too large for the clock waits like a negative one (F15).
- In `src/painterly/session/session.h`: say that a Session and its Scene are used from one thread at a time
  (`start()` releases the GIL in the bindings, T3.15). `src/blender/_painterly.pyi` is a CONTRACT file: leave it.
- Change no existing assertion.
Outcome: `CHECK` exits 0.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `src/painterly/session/session.cpp`, `src/painterly/session/session.h`, `src/test/test_session.cpp`
Depends on: M3-T3.14.

## M3-FIX-TQ3b: the _painterly bindings are tested for their effect, not only their signature (TQ.3 F5, F17-F19, F23)
Why (audit TQ.3, `docs/audits/TQ.3.md`, 2026-10-24): `tests/core/test_api_contract.py` compares the bindings' names,
parameters and defaults with `_painterly.pyi`, and no test calls several of them for their effect: forwarding
`set_camera_orthographic` to the perspective camera, or swapping `add_sun`'s direction and radiance, passes every test
(F5). Three wrong-type sites are untested (F17), the original Python exception is discarded (F18), and the selftest's
`t` check accepts any t below 0.75 (F19).
Do:
- In `tests/core/test_api_contract.py`, test the effect of `set_camera_perspective`, `set_camera_orthographic`,
  `add_sun`, `set_spiral_object`, `Scene.clear` and `add_sphere(spot=...)`, each with a check that the mutations above
  fail, for example two tiny renders that must differ. Use at least one transform that is not the identity, so a
  shifted row in `object_to_world_from_python` fails. Show each mutation and its failure, then restore it.
- Test `lane_length=True` (TypeError: a bool is not an int), `spiral_rotation=(0, 0, "a")` (the ValueError of
  `src/blender/python.cpp:414-416`) and a negative `k0_phase_lock_bits` (ValueError).
- In `python.cpp`, keep the original Python exception as the cause (`__cause__`) of the TypeError or ValueError that
  `as_real` and `as_integer` raise (lines 290-294 and 307-311), with the message unchanged; test it with
  `alpha=10**400` and with an object whose `__float__` raises. Build the range in line 331's message from
  `PAINTERLY_K0_BITS`.
- In `tests/core/test_import.py:48`, check `t` against the bound that `src/test/test_bvh.cpp:87` derives, so that
  `SELFTEST_ORIGIN_Z = 1.4` in `src/blender/selftest.cpp` fails; show it, then restore it.
- In `test_api_contract.py`: check `keep_alive` deterministically (the Scene's reference count while a Session holds
  it); correct the module docstring's claim for lines 167-244; remove the dead branch at lines 116-117. If the GIL
  test's precondition (line 629) can fail on a fast machine, make it independent of timing, or say why it can't be.
Outcome: `CHECK` exits 0.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `src/blender/python.cpp`, `tests/core/test_api_contract.py`, `tests/core/test_import.py`
Depends on: M3-FIX-T3.15a.

## M3-FIX-TQ3c: tests that cannot fail or prove nothing, and comments that are wrong (TQ.3 F7, F16, F20, F22, F29, F34)
Why (audit TQ.3, `docs/audits/TQ.3.md`, 2026-10-24): no test regenerates the committed REPRO.json and REPRO.md, so the
generator and the files can drift apart (F7, TQ.2 F9's cost). Two device-scene checks run on an unchanged scene (F16),
an oracle check compares a path with itself (F34), the `_under` check of the prebuilt-Embree tool is untested (F22),
one test duplicates a parametrised case (F29), and three comments or helpers are wrong or doubled (F20).
Do:
- F7: in `tests/core/test_repro_report.py`, run `tools/repro_report.py` on the committed inputs, into a temporary
  directory, as M3-FIX-TQ2-REPRO's landing check did, and require REPRO.json and REPRO.md byte-identical to the
  committed files under `docs/handoff/repro/`. Show it failing after a one-character change to the generator's
  output, then restore it.
- F16: in `src/test/test_scene.cpp:989-999`, change the scene before each of the two failing `device_update` calls, so
  that a rebuilt device scene would differ from the kept one; show a mutation it now catches.
- F20: correct the comments at `test_scene.cpp:378` and `:1038` (the 52 bits of a binary64 significand are 13 hex
  digits), and let `src/test/test_bvh.cpp:167` use the shared `make_ray` (TQ.2 F7).
- F22: correct the comment at `tests/core/test_embree_prebuilt.py:63-64`, and add a unit test that fails when the
  `_under` check at `tools/embree_prebuilt.py:270` is deleted; show it.
- F29: remove `tests/core/test_compare_results.py:178-184`, after checking that the parametrised test at `:208-226`
  covers its cases.
- F34: replace `test_the_oracle_is_the_binary_of_this_build` (`tests/core/test_oracle_parity.py:160-167`) with a check
  that fails when the oracle binary is stale or belongs to another build, or remove it and say why.
Outcome: `CHECK` exits 0.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `tests/core/test_repro_report.py`, `src/test/test_scene.cpp`, `src/test/test_bvh.cpp`, `tests/core/test_embree_prebuilt.py`, `tests/core/test_compare_results.py`, `tests/core/test_oracle_parity.py`
Depends on: M3-FIX-TQ2-REPRO.

## M3-FIX-T3.17e: the triangle tests' comments say only what was measured, and two derivations are sound (TQ.3 F6, F24, F32, F33)
Why (audit TQ.3, `docs/audits/TQ.3.md`, 2026-10-24): the header of `src/test/test_triangle_diagnostics.cpp` (lines
40-46, 52-55) states an untested mechanism as fact and places the bias in per-path radiance, while its own sentence
calls the cause open and its 1e-7 one-chain-per-pixel agreement points the other way (F32).
`tests/core/test_triangle_path.py:192-196` passes on an empty interior (F6), and the module repeats
`ensemble.DEFAULT_ALPHA` and calls an "indistinguishable" verdict "equivalent" (F24). TOL-a's two derivations
(`analysis/tests/test_report.py:570-583`, `analysis/tests/test_scale_metrics.py:157-170`) reach their tolerances by
loose arguments (F33).
The landing-5 review of M3-FIX-T3.17c (Sonnet reader E, 2026-10-25; line numbers below are at integration `d78fb5e`)
adds: the report case `painterly scene: the ghost-all K differences and where the two paths first part`
(`src/test/test_triangle_diagnostics.cpp:659-809`) asserts only `k_analytic > 0` (`:809`) but adds about 63 s to every
`painterly_tests` run (1.48 s in t-fix-tq3a's log, 64.52 s in t-fix317c's); `HIT_ON_PLANE_BOUND`'s comment counts 28
roundings where the code has 29, and its 56 (`:463`) is a literal beside `PLANE_EXTENT` (`:117`); the figures of the
self-hit case disagree with each other and with the header; and comments in `embree.cpp`, `embree.h` and the selftest
still describe Embree's binary32 t.
Do:
- Start from M3-FIX-T3.17c's result: where it changed these files or found the cause, the comments follow it.
- In the diagnostics header, state as measured only what the harness measures, mark the near-hit mechanism as a
  hypothesis, and make the bias sentence agree with the open cause and the 1e-7 result (or with T3.17c's finding).
  Keep the TEST_CASE name's prefix `painterly scene: the quad scene`; the rest of the name, which says the paths
  "match", may change.
- In `test_triangle_path.py`: require a non-empty interior before comparing it, and show that an empty interior now
  fails; use `ensemble.DEFAULT_ALPHA` instead of a second 0.01; rename the tests or messages that call the verdict
  "equivalent". Say in a comment why the `sys.modules` purge at lines 84-88 is needed, or remove it if the tests pass
  without it.
- TOL-a: in `test_report.py`, the derivation covers both evaluations that are compared (JAX and numpy). In
  `test_scale_metrics.py`, count the operations of the 22-point transform the code actually runs (mixed radix 2 x 11,
  not radix 2). If both sides are bitwise equal there (they run the same code on the same values), assert that with
  `np.testing.assert_array_equal` instead, and say how you checked. No tolerance may widen.
- The ghost-all report case (`:659-809`): mark it `* doctest::skip()`, so the default run skips it, and add a
  `@pytest.mark.slow` test to `tests/core/test_triangle_samples.py` that runs it by name with `--no-skip`
  (`$PAINTERLY_BUILD_DIR/src/test/painterly_tests --no-skip --test-case='<its name>'`) and asserts exit status 0 and one
  test case run. Report the default `painterly_tests` time before and after; do not assert it.
- `HIT_ON_PLANE_BOUND` (`:445-464`): count the roundings the code performs (6 per corner coordinate, 29 in all), and
  derive the magnitude from `PLANE_EXTENT` and the box half-size the comment names instead of the literal 56. The
  charged count stays at most 64 and the bound still fails at HEAD's 1.5e-6; show both.
- The self-hit case `painterly_embree: a binary32 self-hit below the near limit is not a hit` (`:866-966`) and the
  header (`:70-71`): make each quoted figure (`:871`, `:877-878`, `:922`, `:966`) what the code computes, from a script
  whose command and output you quote, and say where the negative root comes from (the reviewer computed that the
  float32 quad lies up to 7.05e-5 off its ideal plane at |x| about 1175). Say in a comment why `SCAN_U`/`SCAN_V`
  (`:927-929`) are these nine fractions and what `REQUIRE(found)` (`:952`) means on an ISA where none qualifies.
- `src/painterly/bvh/embree.cpp:281-285` says |o| and |t| are a few units, which cannot give 1.5e-6 (that needs |P|
  about 25): correct it. `src/painterly/bvh/embree.h:29-33`, `:79-83`, `src/blender/selftest.cpp:99-100` and
  `src/blender/selftest.h:18-20` still say that Embree's float tfar is widened and narrowing is exact; since T3.17c
  the reported t is the binary64 root, and the contract's `t <= tfar` is not checked (`embree.cpp:403-412`). Correct
  the comments; for `t <= tfar`, either check it, with a doctest that fails without the check, or, if every caller
  passes an infinite tfar (`kernel/bvh/bvh.h:26`), drop the claim. Say which and why.
- `tests/core/test_triangle_samples.py:76`: use `ensemble.DEFAULT_ALPHA` instead of a third 0.01 (as F24 above).
Outcome: `CHECK` exits 0, and the quad-scene doctest case still runs and passes; the ghost-all report case is
skipped by default and passes with `--no-skip`.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1" && build/q/src/test/painterly_tests --test-case='painterly scene: the quad scene*' | grep -qE '^\[doctest\] test cases: +1 \| +1 passed \| +0 failed \|'`
allowedPaths: `src/test/test_triangle_diagnostics.cpp`, `tests/core/test_triangle_path.py`, `analysis/tests/test_report.py`, `analysis/tests/test_scale_metrics.py`, `tests/core/test_triangle_samples.py`, `src/painterly/bvh/embree.cpp`, `src/painterly/bvh/embree.h`, `src/blender/selftest.cpp`, `src/blender/selftest.h`
Depends on: M3-FIX-T3.17c.

## XCHK-M7: report-only cross-check of the five revised M7 cards
Why: `docs/handoff/queue.md` §8 cross-checks the revised M7-M9 drafts before Opus approves them and commits them to
`docs/tasks/M7/`. REVISE-M7-a..d revised T7.1-T7.5 from the checked findings, and their verifies check only the clean
`apply` fixes: "The cross-check item and Opus's approval read the rest."
Do: read the five drafts in order, `docs/handoff/drafts/M7-M9/T7.1-panels-and-overrides.md`, `T7.2-presets.md`,
`T7.3-lane-stagger.md`, `T7.4-exp-animation.md` and `T7.5-artist-guide.md`, and check them as a set.
- **Rulings applied.** Each ruling of `docs/handoff/findings/M7-M9-rulings.md` that concerns an M7 card ("How to apply
  them, per card", the cross-cutting X1, X2, C1-C4 and J1, and the M7a and M7b sections) is applied in the card it
  names. Each object of `M7-M9-panel-check-M7a.json` and `M7-M9-panel-check-M7b.json` whose `ruling` is `apply` or
  `change` is in its draft (for `change`, the object's `change` text), or a later ruling replaces it.
- **Ownership and order.** Every file, socket, property, operator, preset, test and experiment directory a card uses is
  created by that card, by an earlier M7 card (T7.1, T7.2, then T7.3 and T7.4, then T7.5), or exists on this tree now:
  cite its path and line.
- **Names and interfaces** agree across the five cards, with the code on this tree (`blender/painterly/`,
  `src/blender/python.cpp`, `src/blender/_painterly.pyi`) and with the committed M4 cards in `docs/tasks/M4/`.
- **Acceptance** is runnable inside each card's own Create/Modify scope and deterministic, with no hand-picked
  tolerance, and no step runs `make oracle`.
- **Experiments** (T7.3, T7.4) take the next free number at run time, and their pre-registered rules are as the M7b
  section of the rulings leaves them.
- Opus's landing readers found the issues below. Verify each at its line, include each real one as an object, and say
  in your answer which you dropped and why:
  - T7.2:317 and :320 still say "In case B, add jitter entries", which the card's check says to delete and its verify
    then requires.
  - T7.2:8-10 says "a later card" where ruling J1 says Opus amends.
  - T7.2:321 states "30 tests pass" from arithmetic, not from a run.
  - T7.2:155 and :653 keep a vestigial "NNN" and "each value".
  - T7.2 against the landed T4.2: the preset operator's `bl_idname` is `render.painterly_render_preset_add`
    (`blender/painterly/presets.py:41`), and T7.2:88, :93, :134 and :556 disagree with it; Step 1's grep also matches
    `presets.py:7`; `tests/blender/test_properties.py:429-438` fails under T7.2:202-208.
  - T7.3:505-508: "means ... still reported" says more than the ruling allows.
  - T7.4:260-261: "96 sequences" leaves out the smoke run.
  - T7.4:498-499: `sign_disagrees_with_r4` is one flag while d is per configuration.
  - T7.4:530 disagrees with :543-545, and :544's AGENTS.md wording with ruling X1.
  - T7.5:238, :241, :254 and :310 count the native panels and the renders as they were before Soft strokes was removed
    (C3). Recount both from the revised T7.1 and T7.2 drafts, and put the command that derives each count in
    `evidence`.
  - T7.5:205-207: "as its fixed sentence there is replaced" can be read two ways.
  - T7.5:1675: the tool's error message tells whoever runs it to run `make oracle`, which agents never run
    (Micah's rule), and an agent may follow the message.

Write `docs/handoff/findings/M7-xchk.json`: a list with one object per real issue, with exactly the keys `card` (the
draft's file name), `line` (its line number in the draft), `issue`, `evidence` (file:line, or a command and its
output) and `fix`. `fix` is `{"old": ..., "new": ...}`, where `old` is text that occurs exactly once in that draft, or
`null` when the choice is Opus's (say why in `issue`). An empty list is a valid result. Change no draft.
Outcome: the pinned verify prints `XCHK-OK <n>`. It checks that the JSON is a list, that every object has exactly the
five keys, names one of the five drafts and a line inside it, and that every non-null `fix.old` occurs exactly once in
that draft.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import json;D='docs/handoff/drafts/M7-M9/';C=['T7.1-panels-and-overrides.md','T7.2-presets.md','T7.3-lane-stagger.md','T7.4-exp-animation.md','T7.5-artist-guide.md'];T={c:open(D+c).read() for c in C};d=json.load(open('docs/handoff/findings/M7-xchk.json'));assert isinstance(d,list),'not a list';K={'card','line','issue','evidence','fix'};bad=[o for o in d if not isinstance(o,dict) or set(o)!=K or o['card'] not in T or type(o['line']) is not int or not 1<=o['line']<=len(T[o['card']].splitlines()) or not (o['fix'] is None or (isinstance(o['fix'],dict) and set(o['fix'])=={'old','new'} and T[o['card']].count(o['fix']['old'])==1))];assert not bad,bad;print('XCHK-OK',len(d))"`
allowedPaths: `docs/handoff/findings/M7-xchk.json`
Depends on: REVISE-M7-c, REVISE-M7-d.

## DRAFT-M6b-B1: draft card B1, kernel globals and the build
Why: the M6b brief (Opus, 2026-10-25) fixes M6b's cards; the queue runs nothing without a card.
Do:
- Draft `docs/handoff/drafts/M6b/B1-kernel-globals.md` from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B1", following the brief's section 4 "How the cards are drafted" and its section 1 decisions.
- Use `docs/handoff/drafts/M6b/FACTS.md` for the current code, and read every file you cite before you cite it.
Outcome: the pinned verify prints `DRAFT-OK`.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import re,sys;F=['docs/handoff/drafts/M6b/B1-kernel-globals.md'];H=['## Goal', '## Read first', '## Create', '## Modify', '## Do not touch', '## Interface', '## Steps', '## Acceptance', '## Commit', '## Open for Opus'];chk=lambda t,i:[h for h in H if not re.search('^'+re.escape(h)+r'[ \t]*(\n|\Z)',t,re.M)]+([] if t.startswith('# '+i+' ') and 'BRIEF.md' in t else ['first line or BRIEF.md']);bad=[(f,c) for f in F for c in [chk(open(f,encoding='utf-8').read(),f.rsplit('/',1)[1].split('-')[0])] if c];print('DRAFT-OK' if not bad else 'DRAFT-BAD',bad);sys.exit(1 if bad else 0)"`
allowedPaths: `docs/handoff/drafts/M6b/B1-kernel-globals.md`

## DRAFT-M6b-B2: draft card B2, the shader manager in PainterlyScene::device_update
Why: the M6b brief (Opus, 2026-10-25) fixes M6b's cards; the queue runs nothing without a card.
Do:
- Draft `docs/handoff/drafts/M6b/B2-shader-manager.md` from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B2", following the brief's section 4 "How the cards are drafted" and its section 1 decisions.
- Use `docs/handoff/drafts/M6b/FACTS.md` for the current code, and read every file you cite before you cite it.
Outcome: the pinned verify prints `DRAFT-OK`.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import re,sys;F=['docs/handoff/drafts/M6b/B2-shader-manager.md'];H=['## Goal', '## Read first', '## Create', '## Modify', '## Do not touch', '## Interface', '## Steps', '## Acceptance', '## Commit', '## Open for Opus'];chk=lambda t,i:[h for h in H if not re.search('^'+re.escape(h)+r'[ \t]*(\n|\Z)',t,re.M)]+([] if t.startswith('# '+i+' ') and 'BRIEF.md' in t else ['first line or BRIEF.md']);bad=[(f,c) for f in F for c in [chk(open(f,encoding='utf-8').read(),f.rsplit('/',1)[1].split('-')[0])] if c];print('DRAFT-OK' if not bad else 'DRAFT-BAD',bad);sys.exit(1 if bad else 0)"`
allowedPaths: `docs/handoff/drafts/M6b/B2-shader-manager.md`

## DRAFT-M6b-B3: draft card B3, ShaderData from painterly hits, and the mesh's UVs
Why: the M6b brief (Opus, 2026-10-25) fixes M6b's cards; the queue runs nothing without a card.
Do:
- Draft `docs/handoff/drafts/M6b/B3-shader-data.md` from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B3", following the brief's section 4 "How the cards are drafted" and its section 1 decisions.
- Use `docs/handoff/drafts/M6b/FACTS.md` for the current code, and read every file you cite before you cite it.
Outcome: the pinned verify prints `DRAFT-OK`.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import re,sys;F=['docs/handoff/drafts/M6b/B3-shader-data.md'];H=['## Goal', '## Read first', '## Create', '## Modify', '## Do not touch', '## Interface', '## Steps', '## Acceptance', '## Commit', '## Open for Opus'];chk=lambda t,i:[h for h in H if not re.search('^'+re.escape(h)+r'[ \t]*(\n|\Z)',t,re.M)]+([] if t.startswith('# '+i+' ') and 'BRIEF.md' in t else ['first line or BRIEF.md']);bad=[(f,c) for f in F for c in [chk(open(f,encoding='utf-8').read(),f.rsplit('/',1)[1].split('-')[0])] if c];print('DRAFT-OK' if not bad else 'DRAFT-BAD',bad);sys.exit(1 if bad else 0)"`
allowedPaths: `docs/handoff/drafts/M6b/B3-shader-data.md`

## DRAFT-M6b-B4: draft card B4, the SVM in painterly_trace_pixel
Why: the M6b brief (Opus, 2026-10-25) fixes M6b's cards; the queue runs nothing without a card.
Do:
- Draft `docs/handoff/drafts/M6b/B4-svm-trace-pixel.md` from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B4", following the brief's section 4 "How the cards are drafted" and its section 1 decisions.
- Use `docs/handoff/drafts/M6b/FACTS.md` for the current code, and read every file you cite before you cite it.
Outcome: the pinned verify prints `DRAFT-OK`.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import re,sys;F=['docs/handoff/drafts/M6b/B4-svm-trace-pixel.md'];H=['## Goal', '## Read first', '## Create', '## Modify', '## Do not touch', '## Interface', '## Steps', '## Acceptance', '## Commit', '## Open for Opus'];chk=lambda t,i:[h for h in H if not re.search('^'+re.escape(h)+r'[ \t]*(\n|\Z)',t,re.M)]+([] if t.startswith('# '+i+' ') and 'BRIEF.md' in t else ['first line or BRIEF.md']);bad=[(f,c) for f in F for c in [chk(open(f,encoding='utf-8').read(),f.rsplit('/',1)[1].split('-')[0])] if c];print('DRAFT-OK' if not bad else 'DRAFT-BAD',bad);sys.exit(1 if bad else 0)"`
allowedPaths: `docs/handoff/drafts/M6b/B4-svm-trace-pixel.md`

## DRAFT-M6b-B5: draft card B5, the world shader on misses
Why: the M6b brief (Opus, 2026-10-25) fixes M6b's cards; the queue runs nothing without a card.
Do:
- Draft `docs/handoff/drafts/M6b/B5-world-shader.md` from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B5", following the brief's section 4 "How the cards are drafted" and its section 1 decisions.
- Use `docs/handoff/drafts/M6b/FACTS.md` for the current code, and read every file you cite before you cite it.
Outcome: the pinned verify prints `DRAFT-OK`.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import re,sys;F=['docs/handoff/drafts/M6b/B5-world-shader.md'];H=['## Goal', '## Read first', '## Create', '## Modify', '## Do not touch', '## Interface', '## Steps', '## Acceptance', '## Commit', '## Open for Opus'];chk=lambda t,i:[h for h in H if not re.search('^'+re.escape(h)+r'[ \t]*(\n|\Z)',t,re.M)]+([] if t.startswith('# '+i+' ') and 'BRIEF.md' in t else ['first line or BRIEF.md']);bad=[(f,c) for f in F for c in [chk(open(f,encoding='utf-8').read(),f.rsplit('/',1)[1].split('-')[0])] if c];print('DRAFT-OK' if not bad else 'DRAFT-BAD',bad);sys.exit(1 if bad else 0)"`
allowedPaths: `docs/handoff/drafts/M6b/B5-world-shader.md`

## DRAFT-M6b-B6: draft card B6, the _painterly shader-graph API
Why: the M6b brief (Opus, 2026-10-25) fixes M6b's cards; the queue runs nothing without a card.
Do:
- Draft `docs/handoff/drafts/M6b/B6-shader-graph-api.md` from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B6", following the brief's section 4 "How the cards are drafted" and its section 1 decisions.
- Use `docs/handoff/drafts/M6b/FACTS.md` for the current code, and read every file you cite before you cite it.
Outcome: the pinned verify prints `DRAFT-OK`.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import re,sys;F=['docs/handoff/drafts/M6b/B6-shader-graph-api.md'];H=['## Goal', '## Read first', '## Create', '## Modify', '## Do not touch', '## Interface', '## Steps', '## Acceptance', '## Commit', '## Open for Opus'];chk=lambda t,i:[h for h in H if not re.search('^'+re.escape(h)+r'[ \t]*(\n|\Z)',t,re.M)]+([] if t.startswith('# '+i+' ') and 'BRIEF.md' in t else ['first line or BRIEF.md']);bad=[(f,c) for f in F for c in [chk(open(f,encoding='utf-8').read(),f.rsplit('/',1)[1].split('-')[0])] if c];print('DRAFT-OK' if not bad else 'DRAFT-BAD',bad);sys.exit(1 if bad else 0)"`
allowedPaths: `docs/handoff/drafts/M6b/B6-shader-graph-api.md`

## DRAFT-M6b-B7: draft card B7, sync/shader/flatten.py
Why: the M6b brief (Opus, 2026-10-25) fixes M6b's cards; the queue runs nothing without a card.
Do:
- Draft `docs/handoff/drafts/M6b/B7-flatten.md` from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B7", following the brief's section 4 "How the cards are drafted" and its section 1 decisions.
- Use `docs/handoff/drafts/M6b/FACTS.md` for the current code, and read every file you cite before you cite it.
Outcome: the pinned verify prints `DRAFT-OK`.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import re,sys;F=['docs/handoff/drafts/M6b/B7-flatten.md'];H=['## Goal', '## Read first', '## Create', '## Modify', '## Do not touch', '## Interface', '## Steps', '## Acceptance', '## Commit', '## Open for Opus'];chk=lambda t,i:[h for h in H if not re.search('^'+re.escape(h)+r'[ \t]*(\n|\Z)',t,re.M)]+([] if t.startswith('# '+i+' ') and 'BRIEF.md' in t else ['first line or BRIEF.md']);bad=[(f,c) for f in F for c in [chk(open(f,encoding='utf-8').read(),f.rsplit('/',1)[1].split('-')[0])] if c];print('DRAFT-OK' if not bad else 'DRAFT-BAD',bad);sys.exit(1 if bad else 0)"`
allowedPaths: `docs/handoff/drafts/M6b/B7-flatten.md`

## DRAFT-M6b-B8: draft card B8, sync/shader/node_table.py and export.py
Why: the M6b brief (Opus, 2026-10-25) fixes M6b's cards; the queue runs nothing without a card.
Do:
- Draft `docs/handoff/drafts/M6b/B8-node-table-export.md` from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B8", following the brief's section 4 "How the cards are drafted" and its section 1 decisions.
- Use `docs/handoff/drafts/M6b/FACTS.md` for the current code, and read every file you cite before you cite it.
Outcome: the pinned verify prints `DRAFT-OK`.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import re,sys;F=['docs/handoff/drafts/M6b/B8-node-table-export.md'];H=['## Goal', '## Read first', '## Create', '## Modify', '## Do not touch', '## Interface', '## Steps', '## Acceptance', '## Commit', '## Open for Opus'];chk=lambda t,i:[h for h in H if not re.search('^'+re.escape(h)+r'[ \t]*(\n|\Z)',t,re.M)]+([] if t.startswith('# '+i+' ') and 'BRIEF.md' in t else ['first line or BRIEF.md']);bad=[(f,c) for f in F for c in [chk(open(f,encoding='utf-8').read(),f.rsplit('/',1)[1].split('-')[0])] if c];print('DRAFT-OK' if not bad else 'DRAFT-BAD',bad);sys.exit(1 if bad else 0)"`
allowedPaths: `docs/handoff/drafts/M6b/B8-node-table-export.md`

## DRAFT-M6b-B9: draft card B9, the golden-test harness and its pre-registered rule
Why: the M6b brief (Opus, 2026-10-25) fixes M6b's cards; the queue runs nothing without a card.
Do:
- Draft `docs/handoff/drafts/M6b/B9-golden-harness.md` from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B9", following the brief's section 4 "How the cards are drafted" and its section 1 decisions.
- Use `docs/handoff/drafts/M6b/FACTS.md` for the current code, and read every file you cite before you cite it.
Outcome: the pinned verify prints `DRAFT-OK`.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import re,sys;F=['docs/handoff/drafts/M6b/B9-golden-harness.md'];H=['## Goal', '## Read first', '## Create', '## Modify', '## Do not touch', '## Interface', '## Steps', '## Acceptance', '## Commit', '## Open for Opus'];chk=lambda t,i:[h for h in H if not re.search('^'+re.escape(h)+r'[ \t]*(\n|\Z)',t,re.M)]+([] if t.startswith('# '+i+' ') and 'BRIEF.md' in t else ['first line or BRIEF.md']);bad=[(f,c) for f in F for c in [chk(open(f,encoding='utf-8').read(),f.rsplit('/',1)[1].split('-')[0])] if c];print('DRAFT-OK' if not bad else 'DRAFT-BAD',bad);sys.exit(1 if bad else 0)"`
allowedPaths: `docs/handoff/drafts/M6b/B9-golden-harness.md`

## DRAFT-M6b-B10: draft card B10, image export and experiment X-colour
Why: the M6b brief (Opus, 2026-10-25) fixes M6b's cards; the queue runs nothing without a card.
Do:
- Draft `docs/handoff/drafts/M6b/B10-image-export-x-colour.md` from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B10", following the brief's section 4 "How the cards are drafted" and its section 1 decisions.
- Use `docs/handoff/drafts/M6b/FACTS.md` for the current code, and read every file you cite before you cite it.
Outcome: the pinned verify prints `DRAFT-OK`.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import re,sys;F=['docs/handoff/drafts/M6b/B10-image-export-x-colour.md'];H=['## Goal', '## Read first', '## Create', '## Modify', '## Do not touch', '## Interface', '## Steps', '## Acceptance', '## Commit', '## Open for Opus'];chk=lambda t,i:[h for h in H if not re.search('^'+re.escape(h)+r'[ \t]*(\n|\Z)',t,re.M)]+([] if t.startswith('# '+i+' ') and 'BRIEF.md' in t else ['first line or BRIEF.md']);bad=[(f,c) for f in F for c in [chk(open(f,encoding='utf-8').read(),f.rsplit('/',1)[1].split('-')[0])] if c];print('DRAFT-OK' if not bad else 'DRAFT-BAD',bad);sys.exit(1 if bad else 0)"`
allowedPaths: `docs/handoff/drafts/M6b/B10-image-export-x-colour.md`

## DRAFT-M6b-B11: draft card B11, node-material parity on the reference scene
Why: the M6b brief (Opus, 2026-10-25) fixes M6b's cards; the queue runs nothing without a card.
Do:
- Draft `docs/handoff/drafts/M6b/B11-node-material-parity.md` from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B11", following the brief's section 4 "How the cards are drafted" and its section 1 decisions.
- Use `docs/handoff/drafts/M6b/FACTS.md` for the current code, and read every file you cite before you cite it.
Outcome: the pinned verify prints `DRAFT-OK`.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import re,sys;F=['docs/handoff/drafts/M6b/B11-node-material-parity.md'];H=['## Goal', '## Read first', '## Create', '## Modify', '## Do not touch', '## Interface', '## Steps', '## Acceptance', '## Commit', '## Open for Opus'];chk=lambda t,i:[h for h in H if not re.search('^'+re.escape(h)+r'[ \t]*(\n|\Z)',t,re.M)]+([] if t.startswith('# '+i+' ') and 'BRIEF.md' in t else ['first line or BRIEF.md']);bad=[(f,c) for f in F for c in [chk(open(f,encoding='utf-8').read(),f.rsplit('/',1)[1].split('-')[0])] if c];print('DRAFT-OK' if not bad else 'DRAFT-BAD',bad);sys.exit(1 if bad else 0)"`
allowedPaths: `docs/handoff/drafts/M6b/B11-node-material-parity.md`

## DRAFT-M6b-N1: draft card N1, node batch 1: Value, RGB, Math, Vector Math (the template)
Why: the M6b brief (Opus, 2026-10-25) fixes M6b's cards; the queue runs nothing without a card.
Do:
- Draft `docs/handoff/drafts/M6b/N1-batch-01-value-rgb-math.md` from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "Node batches", following the brief's section 4 "How the cards are drafted" and its section 1 decisions.
- Use `docs/handoff/drafts/M6b/FACTS.md` for the current code, and read every file you cite before you cite it.
Outcome: the pinned verify prints `DRAFT-OK`.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import re,sys;F=['docs/handoff/drafts/M6b/N1-batch-01-value-rgb-math.md'];H=['## Goal', '## Read first', '## Create', '## Modify', '## Do not touch', '## Interface', '## Steps', '## Acceptance', '## Commit', '## Open for Opus'];chk=lambda t,i:[h for h in H if not re.search('^'+re.escape(h)+r'[ \t]*(\n|\Z)',t,re.M)]+([] if t.startswith('# '+i+' ') and 'BRIEF.md' in t else ['first line or BRIEF.md']);bad=[(f,c) for f in F for c in [chk(open(f,encoding='utf-8').read(),f.rsplit('/',1)[1].split('-')[0])] if c];print('DRAFT-OK' if not bad else 'DRAFT-BAD',bad);sys.exit(1 if bad else 0)"`
allowedPaths: `docs/handoff/drafts/M6b/N1-batch-01-value-rgb-math.md`

## DRAFT-M6b-N5: draft the cards of node batches 5, 6, 10, 11 and 12 from batch 1's template
Why: decision D4 keeps these five core batches in v1, and FOLLOWUPS (2026-10-22) drafts them in one task from batch 1's card.
Do:
- Draft `docs/handoff/drafts/M6b/N5-batch-05-ramp-curves.md`, `N6-batch-06-texcoord-mapping.md`, `N10-batch-10-image-texture.md`, `N11-batch-11-bsdfs.md` and `N12-batch-12-mix-add-background.md` from the brief's "Node batches" text, in the structure of `docs/handoff/drafts/M6b/N1-batch-01-value-rgb-math.md`, following the brief's section 4.
- Each card names its host classes to extract (or says none is missing), its node-table rows and its golden tests.
Outcome: the pinned verify prints `DRAFT-OK`.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import re,sys;F=['docs/handoff/drafts/M6b/N5-batch-05-ramp-curves.md', 'docs/handoff/drafts/M6b/N6-batch-06-texcoord-mapping.md', 'docs/handoff/drafts/M6b/N10-batch-10-image-texture.md', 'docs/handoff/drafts/M6b/N11-batch-11-bsdfs.md', 'docs/handoff/drafts/M6b/N12-batch-12-mix-add-background.md'];H=['## Goal', '## Read first', '## Create', '## Modify', '## Do not touch', '## Interface', '## Steps', '## Acceptance', '## Commit', '## Open for Opus'];chk=lambda t,i:[h for h in H if not re.search('^'+re.escape(h)+r'[ \t]*(\n|\Z)',t,re.M)]+([] if t.startswith('# '+i+' ') and 'BRIEF.md' in t else ['first line or BRIEF.md']);bad=[(f,c) for f in F for c in [chk(open(f,encoding='utf-8').read(),f.rsplit('/',1)[1].split('-')[0])] if c];print('DRAFT-OK' if not bad else 'DRAFT-BAD',bad);sys.exit(1 if bad else 0)"`
allowedPaths: `docs/handoff/drafts/M6b/N5-batch-05-ramp-curves.md`, `docs/handoff/drafts/M6b/N6-batch-06-texcoord-mapping.md`, `docs/handoff/drafts/M6b/N10-batch-10-image-texture.md`, `docs/handoff/drafts/M6b/N11-batch-11-bsdfs.md`, `docs/handoff/drafts/M6b/N12-batch-12-mix-add-background.md`
Depends on: DRAFT-M6b-N1.

## REVIEW-M6b-a: report-only review of the 11 node-material infrastructure cards
Why: Micah kept M6b's card review in v1.0 (decision D8's exception, 2026-10-26): the cards are reviewed before
Opus approves them. Two drafts were accepted at their revise cap with known defects; confirm each with
evidence and give its exact fix: B2's Acceptance 7 says 53 passed where tests/core/test_shims.py collects 64
(1 + 19 + 19 + 1 + 12 + 12), and its ## Modify and step 12 disagree on which declarations change; B3's "Open for
Opus 6" figures (0 of 64, 36 of 64) have no command or inputs, and its Acceptance 8 says thirteen files where the
diff has 16. Landing 8's reader (2026-10-29) also found, to confirm and fix: B6's step 3 accepts STRING and omits
NORMAL among the socket types that take a default, though its step 1 lists NORMAL, B8 exports Normal (0, 0, 0)
for every BSDF and B11 expects it; every card carries queue text (the "queue translates them with BACKLOG.md's
table" sentence, host-only markers, ruling numbers) that belongs in BACKLOG items, not cards; B7, B8 and B11 take
expected literals from scratch prototypes that are not in the repository, so each needs a quoted command that
reproduces it.
Do: review each of `B1-kernel-globals.md`, `B2-shader-manager.md`, `B3-shader-data.md`, `B4-svm-trace-pixel.md`,
`B5-world-shader.md`, `B6-shader-graph-api.md`, `B7-flatten.md`, `B8-node-table-export.md`, `B9-golden-harness.md`,
`B10-image-export-x-colour.md`, `B11-node-material-parity.md` (all in `docs/handoff/drafts/M6b/`) on two lenses, reading
every file a finding cites at HEAD.
- **Executability.** Every file, target, binding, socket and test the card uses must be created by it or by an
  earlier card (B1-B11 in order; the node batches after B9). Every acceptance step must be runnable and
  deterministic, with no hand-picked tolerance, and every expected value must be derived from SPEC, from upstream
  code with file:line, or from a quoted script command (BRIEF.md:317-319).
- **Design.** The card must serve M6b's goal (Blender node materials render in Painterly and pass the golden tests
  against Cycles) and respect SPEC, the brief's section 1 decisions, the vendored-code rule (`third_party/` only via
  `tools/vendor_sync.py`), and Cycles' layout and naming (CLAUDE.md rule 3).
Write `docs/handoff/findings/M6b-review-a.json`: a JSON object whose keys are `review <card> <lens>` (card as in the
list:
B1, B2, B3, B4, B5, B6, B7, B8, B9, B10, B11; lens `executability` or `design`), each a list of
`{severity, issue, evidence, fix}` where evidence cites file:line or a command and its output, and fix is the
edit to the draft as exact old and new text where you can give one, else null. An empty list is valid. Change no card.
Outcome: this command prints `REVIEW-OK 22`: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import json;d=json.load(open('docs/handoff/findings/M6b-review-a.json'));C=['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10', 'B11'];K={'review '+c+' '+l for c in C for l in ('executability','design')};assert set(d)==K,sorted(set(d)^K);assert all(isinstance(v,list) and all(isinstance(f,dict) and {'severity','issue','evidence','fix'}<=set(f) for f in v) for v in d.values());print('REVIEW-OK',len(d))"`. `git status --porcelain` lists only that file.
allowedPaths: `docs/handoff/findings/M6b-review-a.json`
Depends on: DRAFT-M6b-B3.

## REVIEW-M6b-b: report-only review of the six core node-batch cards
Why: Micah kept M6b's card review in v1.0 (decision D8's exception, 2026-10-26): the cards are reviewed before
Opus approves them. The five batch cards were drafted from N1's template; also check that each follows it. Landing 8's
reader
(2026-10-29) found that N1 says B9 is not drafted and invents `assert_golden`, while the committed B9 defines
`GOLDEN_SCENES` and `meets_rule` (N1's precondition grep prints 0): check every batch card against B9 and give the
fixes. N1's expected literals come from a scratch prototype that is not in the repository: each needs a quoted
command that reproduces it. Every card's queue text (build/q, PYTHONPATH, host-only markers) belongs in BACKLOG.
Do: review each of `N1-batch-01-value-rgb-math.md`, `N5-batch-05-ramp-curves.md`, `N6-batch-06-texcoord-mapping.md`,
`N10-batch-10-image-texture.md`, `N11-batch-11-bsdfs.md`, `N12-batch-12-mix-add-background.md` (all in
`docs/handoff/drafts/M6b/`) on two lenses, reading every file a finding cites at HEAD.
- **Executability.** Every file, target, binding, socket and test the card uses must be created by it or by an
  earlier card (B1-B11 in order; the node batches after B9). Every acceptance step must be runnable and
  deterministic, with no hand-picked tolerance, and every expected value must be derived from SPEC, from upstream
  code with file:line, or from a quoted script command (BRIEF.md:317-319).
- **Design.** The card must serve M6b's goal (Blender node materials render in Painterly and pass the golden tests
  against Cycles) and respect SPEC, the brief's section 1 decisions, the vendored-code rule (`third_party/` only via
  `tools/vendor_sync.py`), and Cycles' layout and naming (CLAUDE.md rule 3).
Write `docs/handoff/findings/M6b-review-b.json`: a JSON object whose keys are `review <card> <lens>` (card as in the
list:
N1, N5, N6, N10, N11, N12; lens `executability` or `design`), each a list of
`{severity, issue, evidence, fix}` where evidence cites file:line or a command and its output, and fix is the
edit to the draft as exact old and new text where you can give one, else null. An empty list is valid. Change no card.
Outcome: this command prints `REVIEW-OK 12`: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import json;d=json.load(open('docs/handoff/findings/M6b-review-b.json'));C=['N1', 'N5', 'N6', 'N10', 'N11', 'N12'];K={'review '+c+' '+l for c in C for l in ('executability','design')};assert set(d)==K,sorted(set(d)^K);assert all(isinstance(v,list) and all(isinstance(f,dict) and {'severity','issue','evidence','fix'}<=set(f) for f in v) for v in d.values());print('REVIEW-OK',len(d))"`. `git status --porcelain` lists only that file.
allowedPaths: `docs/handoff/findings/M6b-review-b.json`
Depends on: DRAFT-M6b-N5.

## PANEL-M6b-a: check the review findings on the 11 infrastructure cards (report only)
Why: a review finding is a claim to test, not evidence. Opus reads this panel, rules wherever the verdict is not
`confirmed`, and then plans the revision of the drafts in `docs/handoff/drafts/M6b/`.
Do:
- Check, each on its own, every finding in `docs/handoff/findings/M6b-review-a.json`. Open every file it cites, at HEAD,
  and
  read the cited lines; never take its quotes or line numbers as read. Re-derive the claim from the drafts, BRIEF.md,
  FACTS.md, `docs/spec.md`, `docs/plan.md`, `docs/architecture.md`, the committed code and, for Cycles' behaviour,
  the read-only upstream checkout `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/vendor/blender-v5.2.2/intern/cycles/` (search only there outside your clone).
- Write `docs/handoff/findings/M6b-panel-a.json`: a JSON list with one object per finding, in the source's key order,
  then
  index. Fields: `source` (`M6b-review-a.json`), `key`, `index` (0-based in that key's list); `verdict`: `confirmed`
  (real as
  stated, and its fix removes it), `partly` (real, but the issue or the fix is wrong as `note` states), `disputed`
  (not a defect) or `unknown` (the tree cannot decide it); `evidence` (the spans you read and every command you ran,
  with its output quoted); `duplicate_of` (`{source, key, index}` of an earlier object stating the same defect, else
  null); `fix` (the edit to the draft as exact old and new text, the old text occurring exactly once in that draft;
  required for `confirmed`; else your corrected edit or null; do not apply it); `note` (one or two sentences).
- Change no other file.
Outcome: this command prints `PANEL-OK` and the number of objects: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import json;d='docs/handoff/findings/';c={'B5', 'B11', 'B2', 'B6', 'B1', 'B3', 'B9', 'B8', 'B4', 'B7', 'B10'};w={('M6b-review-a.json',k,i) for k,v in json.load(open(d+'M6b-review-a.json')).items() if k.split()[1] in c for i in range(len(v))};p=json.load(open(d+'M6b-panel-a.json'));g=[(o['source'],o['key'],o['index']) for o in p];assert len(g)==len(set(g)) and set(g)==w,sorted(set(g)^w);assert all(o['verdict'] in ('confirmed','partly','disputed','unknown') and o['evidence'] and o['note'] and (o['verdict']!='confirmed' or o['fix']) for o in p);print('PANEL-OK',len(p))"`. `git status --porcelain`
lists only that file.
allowedPaths: `docs/handoff/findings/M6b-panel-a.json`
Depends on: REVIEW-M6b-a.

## PANEL-M6b-b: check the review findings on the six core node-batch cards (report only)
Why: a review finding is a claim to test, not evidence. Opus reads this panel, rules wherever the verdict is not
`confirmed`, and then plans the revision of the drafts in `docs/handoff/drafts/M6b/`.
Do:
- Check, each on its own, every finding in `docs/handoff/findings/M6b-review-b.json`. Open every file it cites, at HEAD,
  and
  read the cited lines; never take its quotes or line numbers as read. Re-derive the claim from the drafts, BRIEF.md,
  FACTS.md, `docs/spec.md`, `docs/plan.md`, `docs/architecture.md`, the committed code and, for Cycles' behaviour,
  the read-only upstream checkout `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/vendor/blender-v5.2.2/intern/cycles/` (search only there outside your clone).
- Write `docs/handoff/findings/M6b-panel-b.json`: a JSON list with one object per finding, in the source's key order,
  then
  index. Fields: `source` (`M6b-review-b.json`), `key`, `index` (0-based in that key's list); `verdict`: `confirmed`
  (real as
  stated, and its fix removes it), `partly` (real, but the issue or the fix is wrong as `note` states), `disputed`
  (not a defect) or `unknown` (the tree cannot decide it); `evidence` (the spans you read and every command you ran,
  with its output quoted); `duplicate_of` (`{source, key, index}` of an earlier object stating the same defect, else
  null); `fix` (the edit to the draft as exact old and new text, the old text occurring exactly once in that draft;
  required for `confirmed`; else your corrected edit or null; do not apply it); `note` (one or two sentences).
- Change no other file.
Outcome: this command prints `PANEL-OK` and the number of objects: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import json;d='docs/handoff/findings/';c={'N11', 'N1', 'N6', 'N5', 'N10', 'N12'};w={('M6b-review-b.json',k,i) for k,v in json.load(open(d+'M6b-review-b.json')).items() if k.split()[1] in c for i in range(len(v))};p=json.load(open(d+'M6b-panel-b.json'));g=[(o['source'],o['key'],o['index']) for o in p];assert len(g)==len(set(g)) and set(g)==w,sorted(set(g)^w);assert all(o['verdict'] in ('confirmed','partly','disputed','unknown') and o['evidence'] and o['note'] and (o['verdict']!='confirmed' or o['fix']) for o in p);print('PANEL-OK',len(p))"`. `git status --porcelain`
lists only that file.
allowedPaths: `docs/handoff/findings/M6b-panel-b.json`
Depends on: REVIEW-M6b-b.

## M3-FIX-TQ3d: a session's wait never overflows the clock, and its rollback wakes waiters (landing-5 review)
Why (Sonnet reader E, landing-5 review of M3-FIX-TQ3a, 2026-10-25): `src/painterly/session/session.cpp:122-130` caps a
timeout at `max_seconds = floor(duration<double>(steady_clock::duration::max()))`, 9223372036 s, and calls it always
representable. But libstdc++ computes the deadline as `steady_clock::now() + ceil<ns>(timeout)`
(`/usr/include/c++/15/condition_variable:174-182`), which overflows int64 for every timeout within about one uptime of
the cap: the reviewer's probe on this host had 9221898996.8 s overflow and 9217479879.1 s not. So a timeout of about
292 years is still undefined behaviour. The F14 rollback (`:96-115`) restores the state but never calls
`state_changed_.notify_all()`. `src/test/test_session.cpp:15` and `:23` cite old line numbers (session.cpp:24, :108,
and :149, now :25, :159 and :200), and `:30-31` wrongly says the cases are "flaky in both directions".
Do:
- In `session.cpp`, make the deadline always representable. A timeout whose deadline from `now()` would pass
  `steady_clock::time_point::max()` waits like a negative one, with no deadline, as NaN and infinity already do. Put
  the decision in one function of (now, timeout), declared where a test can call it without waiting, and correct the
  comment.
- In `src/test/test_session.cpp`, test that function at 0, a small timeout, the old cap, the old cap minus one second,
  9.2e9 s, `DBL_MAX`, +inf, NaN and -1. Use a `now` of 0 and a `now` near `steady_clock::now()`, so that each boundary
  is computed, not hand-picked. Mutations: the old cap restored; the no-deadline branch removed. Show both failing.
- After the rollback, call `state_changed_.notify_all()`. If a test can make the thread start fail without a
  test-only branch in production code, add that test. Otherwise say why not, and add a comment saying why no waiter
  can exist (a Session is used from one thread at a time, `session.h`).
- Fix the cites at `test_session.cpp:15` and `:23`; cite by function name, which does not go stale. Correct `:30-31`.
- Change no existing assertion.
Outcome: `CHECK` exits 0.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `src/painterly/session/session.cpp`, `src/painterly/session/session.h`, `src/test/test_session.cpp`
Depends on: M3-FIX-TQ3a.

## M3-FIX-TQ3e: the GIL tests fail for a call that holds the GIL on a loaded machine, and the effect tests' survivors
Why (Opus's landing-6 review of M3-FIX-TQ3b, 2026-10-25): in `tests/core/test_api_contract.py`, the GIL tests assert
`bumps > bound`, where `_gil_held_bound` is the most counting a GIL-holding call allows on an idle machine (two switch
intervals). So the threshold is the held side's own value, with no margin below it. On a loaded machine the hand-offs
stretch. A replica of the harness on this machine, with every CPU busy and a pure-C call that holds the GIL
(`sum(range(6_000_000))`) in place of `start()`, passed in most of 40 runs. The queue's own machine is loaded, so it
can pass a binding that has stopped releasing the GIL.
The comment block calls the threshold "derived, never chosen", but `GIL_RELEASE_SHARE_FLOOR` and `GIL_RELEASE_MARGIN`
are chosen. It also gives R10 as the floor's reason, and R10 says nothing about it.
The review also found:
- three mutations that the effect tests of TQ.3 F5 let through;
- a wrong input in `SPIRAL_DIRECTION_BOUND`'s derivation;
- docstrings that call squared radii radii (lines 250-251).
Do:
- Give the GIL tests a margin on both sides of the threshold. The threshold becomes `GIL_RELEASE_MARGIN` times
  `_gil_held_bound(calibrated)`. The measured window must be long enough that, at `GIL_RELEASE_SHARE_FLOOR`, the
  released running time is `GIL_RELEASE_MARGIN` times the threshold: `GIL_RELEASE_MARGIN**2 * GIL_HELD_HANDOFFS *
  sys.getswitchinterval() / GIL_RELEASE_SHARE_FLOOR` seconds.
  - `test_start_releases_the_gil` grows its mesh until `start()` reaches that window.
  - `test_wait_releases_the_gil` waits for that window.
  - Keep the four knobs' values.
  - Rewrite the comment blocks (lines 1150-1163 and 1262-1273) so they say which numbers are derived and which are
    chosen, and drop the R10 reason.
- Show the GIL tests catching a GIL-holding binding, and passing an unmutated one, on the loaded machine:
  - Remove the GIL release from `Session.start`'s binding in `src/blender/python.cpp`, rebuild, and run
    `test_start_releases_the_gil` 10 times in a row; each run must fail.
  - Do the same for `Session.wait` and `test_wait_releases_the_gil`.
  - Restore `python.cpp`, rebuild, and run both unmutated tests 10 times in a row; each run must pass.
  - Quote every run's bumps and threshold.
  - If one mutated run passes or one unmutated run fails, change no knob and no formula. Call report_blocked with
    those numbers.
- Close the three F5 survivors. In each case build the expectation by hand from the scene's geometry, not with the
  code under test, and show the mutation failing, then restore it:
  - `Scene.clear`: set a background before `clear()`, and require a render after it to equal a new `Scene`'s render
    with the same camera and integrator. Deleting the background reset in `src/painterly/scene/scene.cpp` (lines
    21-33) must fail.
  - Camera rotation: give `camera_to_world` and `object_to_world` a rotation that is not the identity, so that a
    transposed 3x3 block fails each test.
  - Fit: a non-square image with `fit="vertical"`, so that swapping the two fits in
    `src/blender/python.cpp:579-583` fails.
- Correct `SPIRAL_DIRECTION_BOUND`'s derivation (lines 440-448). Compute `SMALLPAINT_PI - pi` with a script (the
  constant is in `src/painterly/kernel/smallpaint.h:15`), and quote the command and its output. Derive the bound
  from that figure, and from `r = sqrt(3)/2` if the derivation uses it. Set the constant to the result, rounded up at
  two significant figures.
- Docstrings:
  - Name nanobind's `keep_alive` mechanism in the keep_alive test's docstring (lines 1030-1043): nanobind 3.1.0
    adds one reference, in `keep_alive_py`, `src/nb_type.cpp:2126-2176` of the venv's nanobind.
  - Lines 250-251 call the values that `_pinhole_hit_radius` returns radii, but they are squared radii; correct
    them. Check line 591's formula against the image the test builds, and correct it if it is wrong.
Outcome: `CHECK` exits 0 (the pinned verify).
Notes:
- Show each mutation in your answer (command and output), then revert it with `git checkout -- <file>`; no mutation
  may remain in the diff.
- Scratch files go under /tmp or .ds-scratch/.
- Run the Python targets with R12's PYTHONPATH prefix and R11's prebuilt Embree; use BUILD_DIR=build/q (K1, K5).
- No test may become slower than about 10 s.
- The threshold and the window come from the formulas above. Never search a knob's value until a run passes.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `tests/core/test_api_contract.py`
Depends on: M3-FIX-TQ3b.

## M3-FIX-TQ3f: TQ3c's landing leftovers: two wrong comments, a weak device-scene check, repro line endings
Why (landing-7 review of M3-FIX-TQ3c, `docs/audits/TQ.5.md`, 2026-10-26; F48-F50, F52; line numbers are at f5d101e): the
comment that TQ3c added at `src/test/test_scene.cpp:379-381` is itself wrong, the comment it added at
`src/test/test_bvh.cpp:169-170` sits above an unrelated function, its F16 check changes the scene only where two of the
device arrays can see it, and its byte-for-byte test of the committed repro files would fail on a Windows checkout with
`core.autocrlf=true`, because `.gitattributes` does not protect them.
Do:
- TQ.5 F48, `src/test/test_scene.cpp:379-381`. The remark "(they are the top 13 of them, the rest zero)" is wrong:
  `3fb99999a0000000` is `3fb`, the sign and the 11-bit exponent (the top 3 hex digits), then `99999a0000000`, the 52
  fraction bits (the LOW 13 digits). Write "(the low 13 of them; the top 3 hold the sign and the exponent)". Run the
  command quoted at `:372-374` and quote its output and the split in your answer. Comment only: no mutation.
- TQ.5 F49, `src/test/test_bvh.cpp:169-170`. The comment about the shared `make_ray` sits above `max_abs_coordinate`
  (`:171`), which has nothing to do with rays. Move it to the `#include "test_ray.h"` at `:27` or delete it.
- TQ.5 F50, `src/test/test_scene.cpp:990-1010`. Before the two throwing `device_update` calls only `materials` (the
  emission) and `data` (the alpha) differ between the changed scene and the kept device scene; `lobes`, `analytic`,
  `meshes`, `tri_material`, `tri_corner_normals` and `objects` are rebuilt from unchanged input
  (`src/painterly/scene/device_scene.cpp:112-205`, before the spiral-frame throws at `:246` and `:252`), so an early
  commit of any one of them is not seen. Change, before each of the two calls, an input of each of those six arrays,
  with different values the second time: a lobe's weight, a field of an analytic primitive, the mesh's triangle count, a
  triangle's material index (this needs a second material), a corner normal, an object's id; choose the edits, name
  them. Keep `unchanged()` as it is. Show a mutation per array: a temporary early commit of that one array into `ds` in
  `PainterlyScene::device_update` before the spiral-frame throws (`device_scene.cpp`, not yours: undo with
  `git checkout -- <file>`) must fail the case; quote the failing check each time. The two mutations TQ3c showed
  (materials, data) must still fail.
- TQ.5 F52, `.gitattributes`. Add `docs/handoff/repro/** -text`, in the file's style (two comment lines, then the
  pattern), as for `third_party/**` and `tests/data/**`. The reason: `tests/core/test_repro_report.py:283-328` compares
  REPRO.json and REPRO.md byte for byte with the tool's output, which is LF only (`tools/repro_report.py:86`,
  `:205-210`), so an end-of-line conversion on a Windows checkout would fail it. Show `git check-attr text --
  docs/handoff/repro/REPRO.md docs/handoff/repro/REPRO.json` before ("unspecified") and after ("unset"), and `git status
  --porcelain` listing only `.gitattributes`.
Outcome: `CHECK` exits 0. `git status --porcelain` lists only allowedPaths.
Notes:
- For each expected value you add or change, write a line `Provenance: <command and output, or source file:line>`
  in your final answer (the queue's integrity check reads these lines; a value without one is escalated).
- Show each mutation in your answer (command and output), then undo it with `git checkout -- <file>`; no mutation may
  remain in the diff. Scratch files go under /tmp or .ds-scratch/. Where a bullet says "choose the edits", name your
  choice in your answer.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `src/test/test_scene.cpp`, `src/test/test_bvh.cpp`, `.gitattributes`

## M4-T4.1: extension skeleton (manifest, engine class, facade)
Card: `docs/tasks/M4/T4.1-extension-skeleton.md`. Depends on: M3-T3.17.
- Re-pointed on 2026-10-22: T4.1 needs T3.17's triangle path and nothing from experiment X-throughput.
Outcome: the card's Acceptance, translated, with Blender at the `BLENDER` path; and `CHECK` exits 0.

## M4-T4.2: properties from core reflection; panels, presets, operators
Card: `docs/tasks/M4/T4.2-properties-ui.md`. Depends on: M4-T4.1.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M4-FIX-T4.2a: the version_update handler upgrades every scene, as Cycles' does
Why (Sonnet landing review, 2026-10-23): `src/blender/addon/version_update.py` defines `do_versions(scene)`, but Blender
calls `version_update` handlers with an argument that is not a scene. Cycles' handler is `do_versions(self)` and
iterates `bpy.data.scenes` (`.cache/vendor/blender-v5.2.2/intern/cycles/blender/addon/version_update.py:66-110`). Ours
returns at once, so no upgrade would run. It's latent today, because there are no upgrade steps yet. The tests call
the handler with a scene, which hides it.
Do:
- Make `do_versions` take Blender's argument, ignore it, and upgrade `scene.painterly` for every scene in
  `bpy.data.scenes`, as Cycles does.
- In `tests/blender/test_properties.py`, call the handler as Blender does, with an argument that is not a scene. Check
  that every scene's `data_version` ends at `CURRENT_DATA_VERSION`, including a second scene. The test must fail on
  today's handler: show that before your fix.
Outcome: `CHECK` and `make test-blender` exit 0.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check test-blender VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `src/blender/addon/version_update.py`, `tests/blender/test_properties.py`
Depends on: M4-T4.2.

## M4-T4.3: render loop (session ↔ RenderResult, output modes, built-in reference scene)
Card: `docs/tasks/M4/T4.3-render-loop.md`. Depends on: M4-T4.2.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify adds the card's Blender targets to `CHECK`, whose `make check` runs no Blender test (`check: lint build test`).
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check test-blender VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`

## M4-FIX-T4.3a: T4.3's film tests pin IEC 61966-2-1 and see a flip (TQ.3 F8-F11, F30, F31)
Why (landing review and audit TQ.3, `docs/audits/TQ.3.md`, 2026-10-24): `tests/core/test_film.py` builds its expected
values from `film.py`'s own constants, so `BYTE_MAX = 100.0` or `SRGB_EXPONENT = 2.2` passes (F8). The flip test's
uniform rows can't tell a row flip from a both-axes flip or a reversed RGBA order (F9), and the monotonicity assert can't
fail (F11). The end-to-end render covers scene_linear at 100 % only (F10). film.py's values themselves are right.
Do:
- In `test_film.py`, write the standard's numbers as literals: 0.04045, 12.92, 0.055, 1.055 and 2.4 (IEC 61966-2-1),
  and 255 x passes for a full byte (SPEC §8). Compute the half-inverse point from those literals. Replace the bound at
  lines 116-127 with one that is sound for the operations used, or with `rel=1e-12` and CLAUDE.md rule 2's
  justification (F30). Show `BYTE_MAX = 100.0`, `SRGB_EXPONENT = 2.2` and a changed `SRGB_JUNCTION` each failing,
  then restore them.
- Give the flip test a distinct value in every element, so a both-axes flip and a reversed channel order fail; show
  both.
- Take the monotonicity check's differences along the sums' axis (axis 0), and show it failing for a non-monotone map.
- In `tests/blender/test_render_reference.py`, build the existing case's expectation with a hand-written row reversal
  instead of `film.to_blender_rows`. Add end-to-end cases for display_referred, for a `resolution_percentage` below
  100, and for `seed_per_frame` at a non-zero frame, each with an expectation built by hand from SPEC §8, not through
  `film`. Mark a case `slow` if it takes more than about 10 s. Show a mutation of `src/blender/addon/session.py` that
  each case catches, then restore it.
- In `src/blender/addon/film.py`, correct the two docstrings (lines 92 and 107) that name Blender's row order: those
  functions return the core's order (F31). Change no value in film.py.
Outcome: `CHECK` and `make test-blender` exit 0.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check test-blender VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `tests/core/test_film.py`, `tests/blender/test_render_reference.py`, `src/blender/addon/film.py`
Depends on: M4-T4.3.

## M4-T4.4: build, install and render the extension in real Blender 5.2.2
Card: `docs/tasks/M4/T4.4-extension-build-it.md`. Depends on: M4-T4.3.
Outcome: the card's Acceptance, translated: the extension builds and installs into a profile directory inside your
clone, and renders headless with the `BLENDER` binary. Also `CHECK` exits 0.
- The verify adds the card's Blender targets to `CHECK`, whose `make check` runs no Blender test (`check: lint build test`).
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check test-blender blender-it VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1" && /run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender --command extension validate dist/*.zip`

## M4-FIX-TQ5a: the engine registers its Combined pass, and the Film panel reaches the display settings and the presets
Why (audit TQ.5, `docs/audits/TQ.5.md`, 2026-10-26; F1, F2, F11, F12, F18, F20, F23, F25-F27, F29, F30, F38; line
numbers are at f5d101e): `engine.py:59-65` `register_passes` is only a docstring, so the engine tells Blender it has no
render passes, while Cycles registers `Combined` (`intern/cycles/blender/addon/engine.py:184`, `:275-277`). The default
output mode reproduces smallpaint only under the Standard view transform with dither 0 (SPEC §8:277-280), yet `ui.py`
draws no operator and no header preset, so `PAINTERLY_OT_apply_display_settings` and `PAINTERLY_PT_render_presets`
cannot be reached from a panel. The other bullets are Lows.
Do:
- TQ.5 F1, `engine.py:59-65`. `register_passes` registers nothing, and its docstring (:62-63) says Blender adds Combined
  itself. Call `engine.register_pass(scene, view_layer, session.COMBINED_PASS, 4, "RGBA", "COLOR")`, as Cycles does for
  `Combined` (Cycles' `engine.py:184`, `:275-277`), and fix the docstring; say in it that these are Blender's render
  passes, not the sample passes of SPEC §0:12 (TQ.5 F27; the name stays, as in Cycles). Test, in the new file: for a
  PAINTERLY scene add a
  `CompositorNodeRLayers` node (`tree = bpy.data.node_groups.new(name, "CompositorNodeTree")`,
  `scene.compositing_node_group = tree`, `tree.nodes.new(type="CompositorNodeRLayers")`, as Blender's
  `bl_operators/clip.py:708-723` does) and require its `Image` and `Alpha` outputs enabled. The expected names come from
  Blender, not from this code: the same node on a `BLENDER_EEVEE` scene, or the literals `Image` and `Alpha`; name
  which. Remove the node group and restore `compositing_node_group` and `use_compositing` afterwards (the render tests
  share the scene). Mutation: `register_passes` back to its docstring only. If the test then passes, call
  `report_blocked` with the node's outputs and do not weaken it.
- TQ.5 F2, `ui.py:96-107`. The Film panel draws its group and `reference_scene` only. Add (a)
  `layout.operator(operators.PAINTERLY_OT_apply_display_settings.bl_idname)` after the properties (as the T7.1 draft
  does, `docs/handoff/drafts/M7-M9/T7.1-panels-and-overrides.md:304-308`); (b) above it a warning row
  (`row.alert = True`, a `label` that says why) while `output_mode == "display_referred"` and any setting the operator
  would change differs from its target; (c) `draw_header_preset(self, context)` calling
  `presets.PAINTERLY_PT_render_presets.draw_panel_header(self.layout)`, as Cycles does
  (`intern/cycles/blender/addon/ui.py:219-220`). The row and `execute` call one function (F20 bullet), so the row cannot
  disagree with the button. Tests, in the new file, with a recording layout of its own (`prop`, `row`, `column`,
  `label`, `operator`, `popover`, `separator`; flags `active`, `alert`, `use_property_split`, `use_property_decorate`):
  the Film panel draws the operator's idname; the warning is drawn under `display_referred` with the AgX view transform
  or dither 1.0, and not after the operator ran or under `scene_linear`; `draw_header_preset` draws the popover of
  `PAINTERLY_PT_render_presets`. Mutations: the operator call removed; the `display_referred` condition removed;
  `draw_header_preset` removed.
- TQ.5 F20, `operators.py:16-21`, `:50-68`. The operator's list is shorter than what Blender 5.2.2 applies to the
  displayed bytes, so it can say "already match" while the output differs. Add `scene.display_settings.display_device =
  "sRGB"` (`properties_render.py:74`; it is on `display_settings`, not `view_settings`),
  `scene.view_settings.use_curve_mapping = False` (`:172`) and `use_white_balance = False` (`:209`). Sources: the sRGB
  display with the Standard view is IEC 61966-2-1's compound encoding (`datafiles/colormanagement/config.ocio:59-60`,
  `:132-145`) and Display P3 has a Standard view of its own (`:69-70`); Curves and White Balance change the displayed
  pixels. Factor the comparison of `execute` (`operators.py:52-59`) into one function of the scene that returns the
  settings that differ; `execute` and the warning row (F2) call it. Test, in the new file: set each of the three and
  each existing setting to a non-matching value ("Display P3", True, True, ...), run `execute`, and require each
  restored and named in the report; with all matching, "already match". Mutations: each of the three removed in turn.
- TQ.5 F18, `ui.py:39-40`, `:69`, `:107`. Knobs with no effect in the current mode are drawn active. Keep one activity
  table by property name and draw every property (the socket groups and `spiral_object`) through one helper that puts it
  in a sub-layout with `active` from the table (a property not in the table is active). The entries, each with its
  source, and no others: `diffuse_gain`, `emission_gain`, `ray_epsilon`, `max_depth` and `spiral_frame` are inactive
  while `reference_scene` is on (`session.py:78-89`, `sync/reference.py:72-83` overwrite them); `lane_length` is active
  only for `chain == "lane"` (`src/painterly/scene/integrator.cpp:135`, SPEC §8:287); `k0_phase_lock_bits` only for
  `row` and `lane` (SPEC §3, `integrator.cpp:206`); `exposure` only for `scene_linear` (`integrator.cpp:313`);
  `spiral_rotation` only when the effective frame is not `smallpaint` (`integrator.cpp:187`, SPEC §1); `spiral_object`
  only when it is `object` (`properties.py:167`); the effective frame is `smallpaint` while `reference_scene` is on.
  Test, in the new file: for each entry set its controlling setting both ways and require the recorded `active` flag.
  Mutations: each entry's condition inverted in turn.
- TQ.5 F12, `ui.py:50`, `:65`, `:79`, `:91`, `:103`. The draws set `use_property_split` only, so Blender draws an
  animation decorator beside each knob; Cycles switches it off (`intern/cycles/blender/addon/ui.py:229`), as does
  Blender's Color Management panel (`properties_render.py:66`). Set `layout.use_property_decorate = False` in the five
  draws. Test, in the new file: each of the five `draw`s leaves it False. Mutation: removed from one draw.
- TQ.5 F11, `presets.py:52-61` and the preset file. The preset sets `chain` and `reference_scene` and unsets
  `output_mode` and `passes`; every other knob keeps what the user set (jitter 0.5 stays 0.5), against its comment
  (`smallpaint_reference.py:3-7`); and it leaves the image size, so a default 1920x1080 scene fails
  `session.py:122-130`. Give `PAINTERLY_PT_render_presets` a `reset_cb`, a static method of exactly two parameters
  `(context, filepath)` (`bl_operators/presets.py:36-50` calls it so, `:299` before the file runs; it prints and
  swallows any exception, so test the effect) that unsets every setting of `PRESET_VALUES` on `context.scene.painterly`
  (the T7.2 draft plans it, `docs/handoff/drafts/M7-M9/T7.2-presets.md:64`, `:186-200`). Keep the preset file's two
  `property_unset` lines: `test_properties.py:452-469` runs it with `exec`, without `reset_cb`. For the size choose one,
  name it: say in the preset's comment that the size and the view settings are the user's (the T7.2 draft leaves them
  so, `T7.2-presets.md:14-17`), or set 400x400 at 100 % (SPEC §9). Make the comment true. Tests, in the new file: set
  several settings away from their defaults (jitter, seed, alpha, lane_length); run
  `bpy.ops.script.execute_preset(filepath=<the shipped preset>, menu_idname="PAINTERLY_PT_render_presets")`; require
  exactly `chain` and `reference_scene` set (`is_property_set`; `docs/tasks/M4/T4.2-properties-ui.md` states what the
  preset sets), every other setting at its reflected default (`_painterly.integrator_sockets()`, not a literal), and the
  size if you set it. Restore the menu class's `bl_label`, which the operator changes. Mutation: `reset_cb` a no-op.
- TQ.5 F23, `engine.py:30-45`. The version check runs in `init()`, after `register()` imported `properties` (which calls
  `_painterly.integrator_sockets()` at `properties.py:141`; `__init__.py:65-67`), and `session.py:19` imports
  `_painterly` as soon as `engine` imports `session`: a native module without `integrator_sockets` fails with
  AttributeError, not the ImportError of `docs/tasks/M4/T4.1-extension-skeleton.md:39-40`. Run the check when `engine`
  is imported, before `from . import session` (`__init__.py:24` imports `engine` first), and keep `init()` calling the
  same function. `make lint` must stay clean (ruff E402, I001): a `# noqa: E402` with its reason or another form; name
  it. Test, in the new file: in a child Python that loads the package as `tests/blender/conftest.py` does, with
  `_painterly.version_info` patched to report another version and `integrator_sockets` deleted from the module, loading
  the package and calling `register()` raises ImportError naming both versions. Mutation: the check back in `init()`
  only.
- TQ.5 F25 (b, c, e). `engine.py:6-7` says the module "is the only place that knows about the native module";
  `session.py:19` and `properties.py:19` import it too. `engine.py:7-8`, `:63-64` and `:69` say T4.3 will fill things in
  ("T4.3 replaces that stub"); it landed in 93ff499 and `session.render` is the loop. `ui.py:119-124` calls
  `RENDER_PT_simplify` Cycles' culling panel whose settings "do nothing"; it is Blender's generic Simplify panel
  (`properties_render.py:1079-1140`: Max Subdivision, Max Child Particles, Volume Resolution, Normals), and what Blender
  does with those settings for an engine is not shown. Correct the first two. Keep the exclusion
  (`test_properties.py:329-330` asserts it) and write its comment as a decision ("Painterly has no simplification
  stage"), not as a claim about the settings.
- TQ.5 F26, `operators.py:24-36`. `display_settings_of` has no caller in `src`, tests or tools. Delete it; the function
  of the F20 bullet takes its place.
- TQ.5 F29, `presets/painterly/render/smallpaint_reference.py:1`. The file opens with `import bpy`; the other add-on
  `.py` files open with the two SPDX lines (`film.py:1-2`). Add them (Blender runs presets with `execfile`; comments are
  harmless). Test, in the new file: its first two lines equal `film.py`'s. Mutation: the header removed.
- TQ.5 F30, `ui.py:119-124`. `DATA_PT_preview` is lent to the engine, which declares no previews (`__init__.py:35`), so
  the Light tab gets a Preview panel it cannot fill (`properties_data_light.py:45-54` lists `BLENDER_RENDER`; Cycles
  excludes it, `intern/cycles/blender/addon/ui.py:2557`). Add `"DATA_PT_preview"` to `EXCLUDE_PANELS` with that reason,
  to go when material previews exist. Test, in the new file: `"PAINTERLY"` is not in
  `bpy.types.DATA_PT_preview.COMPAT_ENGINES` and the name is in `ui.EXCLUDE_PANELS`, as a literal
  (`test_properties.py:335-338` loops over the set and cannot see a removal). Mutation: the name removed.
- TQ.5 F38, as tests in the new file, with the F11 preset test. The add-preset operator is never run: run
  `bpy.ops.render.painterly_render_preset_add(name=...)` into a temporary preset directory (monkeypatch
  `bpy.utils.user_resource`, which `AddPresetBase.execute` calls at `bl_operators/presets.py:149`; nothing may be
  written under the developer's Blender profile), read the file it wrote, set other values, execute the file through
  `script.execute_preset`, and require every setting of `PRESET_VALUES` equal to the saved one. Run the display-settings
  operator once as `bpy.ops.render.painterly_apply_display_settings()` and require `{'FINISHED'}`. Mutations: a name
  removed from `PRESET_VALUES`; `preset_defines` emptied.
- TQ.5 F38, `tests/blender/test_properties.py:287-295`, `:305-320`. Its `RecordingLayout` has only `prop`, and
  `test_drawing_a_panel_shows_its_group_in_socket_order` draws all five panels with it, so the draws of the F2 and
  F18 bullets would fail it. Extend `RecordingLayout` with what your draws call (`row`, `column`, `label`,
  `operator`, `popover`, `separator`; the flags `active`, `alert`, `use_property_decorate`), recording a `prop` drawn
  through a sub-layout in drawing order as if drawn directly, so that the test asserts exactly what it asserts today.
  Change no assertion and nothing else in the file; M4-FIX-TQ5c edits it after you. Mutation: two properties of one
  group swapped in a draw fails the test.
Outcome: `CHECK` and `make test-blender` exit 0. `git status --porcelain` lists only allowedPaths.
Notes:
- For each expected value you add or change, write a line `Provenance: <command and output, or source file:line>`
  in your final answer (the queue's integrity check reads these lines; a value without one is escalated).
- The new tests are in `tests/blender/test_ui_surface.py`, with a recording layout of their own (do not import from
  `test_properties.py`); each requests the `addon` fixture itself (M4-FIX-TQ5c makes it autouse; do not rely on that)
  and restores what it changes (scene and view settings, `COMPAT_ENGINES`, registered classes, `bl_label`). Expected
  values come from the source each bullet names, never from the output of the code under test (AGENTS.md, "Expected
  values are evidence").
- In `tests/blender/test_properties.py` change only `RecordingLayout` (the F38 bullet). If a draw cannot pass the
  unchanged assertions, say so in your answer with the output; do not bend the draws to the stand-in.
- Show each mutation in your answer (command and output), then undo it: `git checkout -- <file>` for a file you did not
  change; for one you changed, save your finished copy under `.ds-scratch/` first and copy it back (`git checkout` would
  discard your work). No mutation may remain in the diff.
- `intern/cycles/...` is under `MAIN/.cache/vendor/blender-v5.2.2/`. `properties_render.py` and
  `properties_data_light.py` are Blender 5.2.2's `scripts/startup/bl_ui/` files and `datafiles/...` is next to them
  under `5.2/` beside the `BLENDER` executable; the scripts are also in the bpy package
  (`bl_operators.presets.__file__`).
- Scratch files go under /tmp or .ds-scratch/. Run the Python targets with R12's PYTHONPATH prefix and R11's prebuilt
  Embree; use BUILD_DIR=build/q (K1, K5). No test may become slower than about 10 s. Where a bullet says "choose one",
  name your choice in your answer.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check test-blender VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `src/blender/addon/engine.py`, `src/blender/addon/ui.py`, `src/blender/addon/operators.py`, `src/blender/addon/presets.py`, `src/blender/addon/presets/painterly/render/smallpaint_reference.py`, `tests/blender/test_ui_surface.py`, `tests/blender/test_properties.py`

## M4-FIX-ENV: `make env` keeps the blender group's packages, so it never removes bpy
Why (Opus, 2026-10-26): `make env` runs `uv sync --locked --group dev --group analysis` (`Makefile:34-35`), and `uv
sync`
is exact by default: it removes every package outside the groups it is given. On a venv that `make env-blender` made,
it uninstalls bpy and its dependencies. On 2026-10-26 that happened to MAIN/.venv, which every queue verify uses:
`tests/blender/conftest.py:32-33` then skips every bpy test without a word, so `make check` ran 543 tests instead of
591, and `make test-blender` failed with "no tests ran".
Do:
- In `Makefile:34-35`, add `--inexact` to the `uv sync` of `env`. uv documents it as "Do not remove extraneous packages
  present in the environment" (`uv sync --help`), so `make env` installs the dev and analysis groups and leaves the
  blender group's packages in place. Leave `env-blender` as it is. Put a one-line comment above `env` that says why.
- New `tests/core/test_make_env.py`: run `make -n env` and `make -n env-blender` (a dry run: nothing is installed and no
  network is used) and require that the `uv sync` line of `env` has `--inexact` and that of `env-blender` is
  `uv sync --locked --group dev --group analysis --group blender`. Mutation: `--inexact` removed from `env`; show the
  test failing, then restore it.
Outcome: `CHECK` exits 0. `make -n check` is byte-identical before and after. `git status --porcelain` lists only
allowedPaths.
Notes:
- Do not run `make env` or `make env-blender` themselves: the shared venv is read-only in your sandbox, and syncing
  needs the network. The dry run is the evidence.
- For each expected value you add or change, write a line `Provenance: <command and output, or source file:line>`
  in your final answer (the queue's integrity check reads these lines; a value without one is escalated).
- Show each mutation in your answer (command and output), then undo it; no mutation may remain in the diff. Scratch
  files go under /tmp or .ds-scratch/.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `Makefile`, `tests/core/test_make_env.py`

## M4-FIX-TQ5b: the render loop reads the evaluated scene, pairs its result, writes once and reports its errors
Why (audit TQ.5, `docs/audits/TQ.5.md`, 2026-10-26; F4, F9, F12-F16, F22, F25-F27, F39, F41; line numbers are at
f5d101e): the loop re-reads `scene.painterly` from the original scene on every write (`session.py:101-102`, `:117-118`,
`:196`), begins a result at `:152` that only two exits end, and finishes with a write that repeats the last; a negative
frame raises a bare ValueError (`:73-74`) and Render Region is ignored. The scripted poll-loop tests never read what a
partial render writes, and no test pins the four reference knobs that the oracle takes as flags, because every consumer
derives them from `apply_reference_knobs()`.
Do:
- TQ.5 F12, `session.py:117-118`, `:101-102`, `:196`. The loop reads `scene.painterly` from `depsgraph.scene`, and
  `_write_result` re-reads `output_mode` and `exposure` on every write, so an edit during the render changes the final
  image while the core's knobs were fixed at `:141`. Cycles reads the evaluated scene
  (`intern/cycles/blender/session.cpp:173`; `addon/__init__.py:94`, `depsgraph.scene_eval.cycles`). Either take
  `depsgraph.scene_eval` for the settings and the frame, or read the two once before the loop and pass them down; choose
  one, name it. Test, in `tests/core/test_session_loop.py` (F4 bullet): a scripted session whose `wait()` changes
  `exposure` and `output_mode` after the first poll; every array written uses the values the render started with
  (expected by hand from SPEC §8, as `test_render_reference.py:119-123` does). Mutation: `_write_result` reads
  `settings.exposure` again.
- TQ.5 F13, `session.py:36-52`, `:152`. Render Region and Crop are ignored, although the lent Format panel offers both
  (`properties_output.py:126-129`): a full-frame result is begun. Until the Blender-scene camera exists (border support
  is for the M5 review, not here), report an error and return before any scene is built while `scene.render.use_border`
  is set: `engine.report({"ERROR"}, "Painterly: ...")` naming Render Region. Tests: a stand-in scene with
  `render.use_border = True` gets the report and no `begin_result`; in `test_render_reference.py`,
  `bpy.ops.render.render()` with it on raises RuntimeError with that message (restore it as `scene_settings` restores
  the others). Mutation: the check deleted.
- TQ.5 F14, `session.py:73-74`. `int(settings.seed) + int(scene.frame_current)` is negative at a negative frame, and
  `set_integrator` (uint check, `src/blender/python.cpp:388-394`) raises a bare ValueError out of `render()`. Choose
  one, name it: wrap the sum modulo 2**32 (`& 0xFFFFFFFF`) and say so in the docstring, or report the error through
  `engine.report`. Test, in `test_session_loop.py`: seed 0, `seed_per_frame` on, frame -1: with the wrap the knob is
  4294967295 (2**32 - 1, the stated rule); with the report, one error report and no result. Mutation: the wrap or the
  report removed.
- TQ.5 F15, `session.py:152-197`. A result is ended on the error path (`:186`) and at the end (`:197`) only;
  `_write_result`, the `update_*` calls and `combined()` run between with no `try/finally`, so an exception (a
  MemoryError at 3840x2160, say) leaves the result open and the Session running until the engine is freed. Cycles pairs
  them in C++ (`intern/cycles/blender/session.cpp:362`, `:468`). Put everything after `begin_result` in a `try/finally`:
  on an exception call `engine.end_result(result, cancel=True)` and `session.cancel()` and let it propagate; the two
  existing exits keep `end_result(result)`. Test, in `test_session_loop.py`: a scripted session whose `combined()`
  raises; the exception propagates, the stand-in engine saw `end_result(..., cancel=True)` once, the session was
  cancelled. Mutation: the `try/finally` removed.
- TQ.5 F16, `session.py:194-196`. The final write repeats the last in-loop write whenever the last poll wrote
  (`:168-179`), so a finished render ends with two full-frame conversions. Write only `if final > written:`. The
  assertion `len(written) == 2` at `test_render_reference.py:531` moves with its test (F4 bullet) and becomes 1; say so
  in your answer. Tests, in `test_session_loop.py`: one write when the last poll's reads agree; and the final write
  still happens when the loop skipped the last batch (a last poll with `p0 != p1` and `finished` true). Mutations:
  `final >= 1` restored (the first fails); the final write deleted (the second fails).
- TQ.5 F22, `session.py:101-104`. Any output mode but `scene_linear` takes the `else`, `display_referred`; a third core
  enumerator (`src/painterly/scene/integrator.cpp:34-37` has two) would go through the sRGB curve without an error. Use
  `elif settings.output_mode == "display_referred":` and `else: raise ValueError(...)` naming the mode. Test, in
  `test_session_loop.py`: a stub settings with `output_mode = "bogus"` makes `_write_result` raise ValueError; the two
  real modes still write. Mutation: `else:` restored.
- TQ.5 F4, `tests/blender/test_render_reference.py:305-554`. The three scripted poll-loop tests never read the arrays
  they record (`:531` asserts `len(written) == 2` only), and every `passes_done` in them equals `PASSES`, so `total` for
  `passes_done` at `session.py:176` or `:196`, or the first read of `passes_done` (`:168`) for `p0` at `:176`, survives.
  `session.py` needs no `bpy` (it imports `_painterly`, `numpy`, `film`, `sync`), so these tests belong in `tests/core`,
  which CI runs. New `tests/core/test_session_loop.py`: load the add-on's modules under a stub parent package of a name
  of its own (a `types.ModuleType` with `__path__ = [src/blender/addon]` in `sys.modules`, so `addon/__init__.py`, which
  imports `bpy`, never runs) and use a `SimpleNamespace` scene. Move the three scripted tests and their stand-ins there
  with assertions unchanged (F16 changes one), and delete them here. Add (a) a partial render, `passes_done = 1` of
  `passes_total = 2`, every sum 255.0: the array written is the hand-built `scene_linear` of one pass, rows reversed,
  colour 1.0 (255 / 1 / 255), not 0.5, alpha 1; (b) a poll whose first read of `passes_done` (`session.py:168`) is
  smaller than `p0 == p1`: the array divides by `p0`. Expected values from SPEC §8 (`L/255 · exposure`) by hand, not
  through `film`. Mutations: `total` for `p0` at `session.py:176`; `total` for `final` at `session.py:196`; the first
  read for `p0`.
- TQ.5 F41, `test_render_reference.py:355`, `:362`, `:404-407`, `:464`. The stand-ins record how the loop is wired and
  nothing reads it: the session's `started` pair, `engine.session`, the size given to `begin_result`;
  `Session(scene, threads)` ignores `threads`. Survivors: `start(total, 1)`, `Session(scene, 0)`,
  `begin_result(0, 0, height, width)`, `engine.session = session` removed, `cancel()` then `break` at once, `written`
  never updated. In `test_session_loop.py` assert `fake_session.started == (PASSES, settings.batch)` with a batch other
  than 1; the `threads` given to `Session` is a non-zero `settings.threads`; `engine.result_size == (width, height)` for
  a non-square size; `engine.session is fake_session`; after `test_break()` the loop polls until `wait()` reports
  finished and then writes the passes done; an unchanged `passes_done` is not written again. Add `session.resolution`
  for 7 by 5 px at 50 %: (3, 2), Blender's integer division (`intern/cycles/blender/util.h:296-304`,
  `xsch * size / 100`; `session.py:44-45`). Mutations: each survivor above; `resolution` with float division and
  rounding.
- TQ.5 F9, new `tests/core/test_reference_knobs.py`. `apply_reference_knobs()` (`sync/reference.py:72-83`) is pinned
  against no literal, and `ORACLE_EXACT_KNOBS` (`tests/core/scenes.py:67-78`) derives the oracle's flags from it, so
  `max_depth` 20 to 10 or `emission_gain` 2 to 3 moves both sides of every parity test and of the IT. Load
  `sync/reference.py` by path, as `scenes.py` does, and assert the four values as literals with their smallpaint lines
  (`third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp`, CRLF): `diffuse_gain` float32(0.1) (`*0.1`,
  :209-211), `emission_gain` 2 (`* 2`, :200), `ray_epsilon` float32(1e-4) (`const double eps = 1e-4;`, :39), `max_depth`
  20 (`depth >= 20`, :190); float32 because a float socket stores its float32 value (T3.15; `reference.py:66-68`). Also
  read the cited lines and require the literal on each, so a moved cite fails; require `spiral_frame == "smallpaint"`
  (SPEC §1) and no other key. Mutations: each of the four values changed in `reference.py`; one cited line number
  changed in the test.
- TQ.5 F25 (a, d, f). `session.py:5-6` says the module mirrors Cycles' `intern/cycles/blender/sync.py`; Cycles has
  `sync.cpp` and `session.cpp`, no `sync.py` (`ls intern/cycles/blender`): name `session.cpp` (the render loop) and
  `sync.cpp`; `sync/__init__.py:5` makes the same claim: name `sync.cpp` there. `sync/reference.py:39-46`: the
  comment and the annotation of `REFERENCE_SCENE` list four fields, the rows have five (kind, geometry, values, colour,
  material kind; `:130` unpacks five): fix both. `session.py:45-46` says
  `engine.resolution_x/_y` report the same values, which nothing here checks: delete the sentence.
- TQ.5 F26, `sync/reference.py:37`, `:109`, `:143`; `session.py:86-88`. `GLASS_IOR = 1.5` is unused by its own module,
  which repeats the literal as the default of `build_smallpaint_scene`'s `ior`: default it to `GLASS_IOR`. And
  `build_smallpaint_scene` ends with `scene.set_integrator(**apply_reference_knobs())` while `_set_integrator` applies
  the same dict again after the user's knobs. Keep or drop the first and say why in a comment; `tests/core/scenes.py`
  re-exports the function to the parity tests, which may rely on it, so drop it only if every caller under `tests/` and
  `experiments/` applies the knobs itself; choose one, name it. Test, in `test_reference_knobs.py`: `GLASS_IOR == 1.5`
  (SPEC §9: "Glass IOR is 1.5") and the default of `ior` equals `GLASS_IOR`. Mutations: `GLASS_IOR = 1.6`; the default
  changed to 1.6.
- TQ.5 F27, `session.py:31-33`, `:105`, `:154`. Comment wording only. "pass" names a Blender render pass in the first
  two (`COMBINED_PASS`) and the sample passes inside it in the third ("The passes already in the Combined pass"); SPEC
  §0:12 reserves "pass" for the sample pass. Say "render pass" for the Combined pass and "sample passes" for the count.
  Keep the name `COMBINED_PASS` (`engine.py` uses it, `test_render_reference.py:328` reads it).
- TQ.5 F39, `tests/core/test_film.py:49-51`, `:97-99`, `:108-121`. Every function gets uniform-channel buffers and
  `scene_linear` never sees a value above white, so a reversed channel order (`rgba[..., :3] = rgb[..., ::-1]`,
  `film.py:80`) or a clip before the exposure (`np.minimum(mean, 1.0) * exposure`, `film.py:111`) passes; and
  `test_film.py:97-99` promises a strict increase "in the linear segment" but asserts `mapped[-1] > mapped[0]`. Add:
  distinct R, G and B sums checked per channel in both modes; `scene_linear(_sums(2 * FULL_BYTE_SUM), PASSES, 1.0)`
  equals 2.0 in every colour channel (SPEC §8, unclipped); and a strict increase, `np.all(np.diff(mapped[:k], axis=0) >
  0)`, over the sums below white, with `k` from the grid, not from the output. Mutations: the two above, in `film.py`.
- The leftovers of 385cfb2 (FOLLOWUPS, landing 6; not audit findings). `test_film.py:69-70` and `:82` say the float32
  cast is the only rounding on either side; both sides round every float64 operation and the cast is the one extra
  rounding: say that. `test_film.py:185-186` says "seven orders of magnitude" inside the bound; about 1e-15 against
  `rel=1e-12` is three. `test_render_reference.py` has no case with `exposure != 1.0`, so a literal 1.0 for the exposure
  at `session.py:102` survives: add an end-to-end `scene_linear` case at `exposure = 2.0` (exact in float32) with
  `_scene_linear_expectation(sum, 2.0)` by hand from SPEC §8; mutation: `film.scene_linear(sums, passes_done, 1.0)`. The
  comments at `test_render_reference.py:64`, `:264` and the docstring at `session.py:65-66` cite SPEC §8 for seed +
  frame, which SPEC §8 does not state; cite the cards that define it, `docs/tasks/M3/T3.13-scene.md:23` and
  `docs/tasks/M4/T4.3-render-loop.md:55`.
Outcome: `CHECK` and `make test-blender` exit 0; the new tests under `tests/core` run in `CHECK`.
`git status --porcelain` lists only allowedPaths.
Notes:
- For each expected value you add or change, write a line `Provenance: <command and output, or source file:line>`
  in your final answer (the queue's integrity check reads these lines; a value without one is escalated).
- Expected values come from the source each bullet names, never from the output of the code under test (AGENTS.md,
  "Expected values are evidence"). If one cannot be met honestly, call `report_blocked`.
- Show each mutation in your answer (command and output), then undo it: `git checkout -- <file>` for a file you did not
  change; for one you changed (`session.py`, `sync/reference.py`), save your finished copy under `.ds-scratch/` first
  and copy it back (`git checkout` would discard your work); `film.py` is not yours, so `git checkout -- <file>` undoes
  its mutations. No mutation may remain in the diff.
- Moving the three scripted tests changes no assertion except the one in the F16 bullet; list that change in your
  answer.
- `intern/cycles/...` is under `MAIN/.cache/vendor/blender-v5.2.2/`; `properties_output.py` is Blender 5.2.2's
  `scripts/startup/bl_ui/properties_output.py` (beside the `BLENDER` executable under `5.2/`, or in the bpy package).
- Scratch files go under /tmp or .ds-scratch/. Run the Python targets with R12's PYTHONPATH prefix and R11's prebuilt
  Embree; use BUILD_DIR=build/q (K1, K5). No test may become slower than about 10 s. Where a bullet says "choose one",
  name your choice in your answer.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check test-blender VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `src/blender/addon/session.py`, `src/blender/addon/sync/reference.py`, `tests/blender/test_render_reference.py`, `tests/core/test_film.py`, `tests/core/test_session_loop.py`, `tests/core/test_reference_knobs.py`, `src/blender/addon/sync/__init__.py`

## M4-FIX-TQ5c: registration, versioning and the bpy tests' isolation
Why (audit TQ.5, `docs/audits/TQ.5.md`, 2026-10-26; F5, F6, F18, F19, F21, F24-F26, F35-F38, F40, F42, F45; line
numbers are at f5d101e): nothing asserts that `unregister()` unregisters, four tests pass only because an earlier test
registered the add-on, and `tests/blender` sets no Blender user directory. `version_update.py:44-52` writes to linked
scenes and never stamps a scene created after load, the reload block misses four modules, and the manifest, the version
check and the engine flags are covered by no test. The other bullets are Lows.
Do:
- TQ.5 F5, `tests/blender/test_registration.py:24-30`. Nothing asserts that the add-on's `unregister()` unregisters, so
  a leak passes and would break disable-then-enable in a user's Blender; and the first two tests hold once the class
  statement runs (`__init__.py:27`; `RenderEngine.__subclasses__()` lists unregistered subclasses). Add one test that
  calls `addon.unregister()` and requires: none of `PainterlyRender`, the names in `ui.classes`,
  `PAINTERLY_OT_apply_display_settings`, `PAINTERLY_OT_render_preset_add`, `PAINTERLY_PT_render_presets` in `bpy.types`;
  no `painterly` on `bpy.types.Scene`; `version_update.do_versions` and the save handler of the F19 bullet out of their
  handler lists; `scene.render.engine = "PAINTERLY"` refused. Then `addon.register()` again, in a `finally`: the names
  are back and `bpy.ops.render.painterly_apply_display_settings()` returns `{'FINISHED'}`. Make the first two tests fail
  before registration (for example `getattr(bpy.types, "PainterlyRender", None) is addon.PainterlyRender`, as
  `test_properties.py:259` does for panels). Mutations, each shown failing: `unregister_class(cls)` dropped
  (`__init__.py:85-86`); `del bpy.types.Scene.painterly` dropped (`properties.py:215`); `operators.classes = ()`
  (`operators.py:71`); `presets.classes = ()` (`presets.py:64-67`); the last two files are not yours: undo with
  `git checkout -- <file>`.
- TQ.5 F6, `tests/blender/conftest.py:62-74`. `test_properties.py:551` takes no fixture, and `fake_loop` and
  `scene_settings` (`test_render_reference.py:131-132`, `:470-471`) never request `addon`, so the tests at
  `test_render_reference.py:510`, `:537` and `:547` read `scene.painterly`, and `test_properties.py:551` reads the
  handler list, before registration: alone, with `--lf` or in another order they fail. Make `addon` autouse
  (`@pytest.fixture(scope="session", autouse=True)`). Show the four tests failing when run alone at f5d101e
  (AttributeError for the three render tests, an assertion for the fourth) and passing alone now, with commands and
  outputs. Mutation: `autouse=True` removed.
- TQ.5 F35, `tests/blender/conftest.py:21-59`. The tests set no Blender user directory, so `import bpy` and whatever the
  add-on or a preset writes may touch the developer's profile. Before the first `import bpy` (`_load_addon()` triggers
  it at `:59`), set `BLENDER_USER_RESOURCES` to a fresh temporary directory, removed at exit, after dropping
  `BLENDER_USER_CONFIG`, `BLENDER_USER_SCRIPTS`, `BLENDER_USER_EXTENSIONS` and `BLENDER_USER_DATAFILES` from the
  environment (they may override it; not checked against 5.2.2). Test, in `test_registration.py`:
  `bpy.utils.resource_path("USER")` lies under that directory, which shows that Blender honoured it; if it does not,
  call `report_blocked` with what it returns. Mutation: the assignment deleted.
- TQ.5 F36, `engine.py:30-57`, `__init__.py:35-40`, `blender_manifest.toml`. Nothing tests the version check, `free()`,
  the engine-class flags or the manifest. (a) New `tests/core/test_manifest.py` (no `bpy`; CI runs it): parse
  `src/blender/addon/blender_manifest.toml` with `tomllib`; `version` equals `[project] version` of `pyproject.toml`;
  `tagline` is at most 64 characters and ends alphanumeric (`docs/tasks/M4/T4.1-extension-skeleton.md:18`); no top-level
  `wheels` or `platforms` (`T4.1:22`; `tools/build_extension.py` writes them). Mutations: a bump of `pyproject.toml`
  alone; a 65-character tagline; a tagline ending in "."; `platforms = ["linux-x64"]` added. (b) In
  `test_registration.py`: with `_painterly.version_info` monkeypatched to another version, `engine.init()` raises
  ImportError naming both versions; `PainterlyRender.bl_use_preview is False`, `bl_use_eevee_viewport is True` and
  `bl_use_shading_nodes_custom is False` (`T4.1:28-30`); `engine.free(stand_in)` sets `stand_in.session` to None and
  does not raise for an object without the attribute. Mutations: `if found != expected` to `if False` (`engine.py:40`);
  `bl_use_preview = True`; `free` a no-op.
- TQ.5 F37, `tests/blender/test_properties.py:495-499`, `:522-526`. The two operator tests set `view_settings` and
  `render.dither_intensity` on the shared default scene and never restore them; the `settings` fixture only unsets
  `scene.painterly`, and this file sorts before `test_render_reference.py`. Save and restore every value those tests
  set, in a fixture, as `scene_settings` does (`test_render_reference.py:131-194`). Test: one that runs after both and
  requires the values captured at import time. Mutation: the restore removed.
- TQ.5 F40, `tests/blender/test_properties.py:135-153`, `:166-214`. The generated float limits are untested: `jitter`'s
  minimum 0 (`src/painterly/scene/integrator.cpp:315`), the one float socket with a limit, and the soft-limit keys have
  no assertion; `_int_property` has a builder test and `_float_property` (`properties.py:66-76`) has none. Check
  `hard_min` and `hard_max` of every float socket that reports a limit against the reflection, and add a builder test
  with a synthetic socket dict that carries soft limits, as `test_properties.py:166-214` does for ints. Mutations: `min`
  dropped from the tuple at `properties.py:73`; `soft_min` dropped.
- TQ.5 F42, `tests/blender/test_properties.py:556-589`, `version_update.py:49-52`. `upgrade()` is never shown to be
  called: deleting `upgrade(settings, from_version)` survives. Monkeypatch `version_update.upgrade` with a recorder and
  require one call `(settings, 0)` per outdated scene, the second scene included, and none for a scene at
  `CURRENT_DATA_VERSION` or newer. `test_properties.py:553` reads the private `_bpy_persistent`: keep it and say in a
  comment that it is the marker `bpy.app.handlers.persistent` sets. Mutation: the call deleted.
- TQ.5 F45, `tests/blender/test_properties.py:294`, `:378`, `:381`, `:388`. The `# noqa: ARG002` comments are inert
  (`pyproject.toml:50` selects no `ARG`). Remove them; keep "Blender's signature" as a plain comment where it helps.
- TQ.5 F19, `version_update.py:44-52`, `properties.py:178-183`. A scene created after load keeps `data_version` 0 (an
  unset value is not saved), so the next load runs `upgrade(settings, 0)` over settings in the current format: harmless
  while `upgrade` is a no-op (`version_update.py:31`), wrong for the first real step. And the handler writes to every
  scene, linked ones included; a linked scene is a read-only ID. Add a persistent `save_pre` handler that stamps
  `CURRENT_DATA_VERSION` on every local scene, so every file written carries it, registered and removed in `register()`
  and `unregister()` like the existing one, and skip `scene.library is not None` in both handlers (Cycles skips unsaved
  files and filters by library, `intern/cycles/blender/addon/version_update.py:94`, `:98-112`). Put the loop in a
  function of a list of scenes. Tests: a scene made with `bpy.data.scenes.new` is stamped by the handler; a stand-in
  scene whose `library` is set is left at 0; the handler is in `bpy.app.handlers.save_pre` after `register()` and out of
  it after `unregister()` (the F5 test). The handler's argument differs between handler lists: ignore it. Mutations: the
  library skip dropped; the `save_pre` registration dropped.
- TQ.5 F21, `__init__.py:15-20`. The reload block lists six of the package's modules;
  `addon_utils.reset_all(reload_scripts=True)` reloads only the top-level module
  (`scripts/modules/addon_utils.py:642-646`), so `importlib.reload(engine)` re-runs `from . import session`
  (`engine.py:16`) and gets the cached module: after an edit to `session.py` the old code keeps running. Reload `film`,
  `sync`, `sync.reference` and `session` before `engine`, each before the module that imports it, then the existing six
  in their order (`sync.reference` is not a name of the package namespace: reload it through `sync`). Test, in
  `test_registration.py`, without disturbing the registered add-on: in a child Python that loads the package as
  `conftest.py` does, replace a module-level name in each of the four modules with a sentinel, reload the package, and
  require the originals back (or do it in-process around `unregister()` and `register()`; choose one, name it).
  Mutation: one module removed from the block.
- TQ.5 F24, `properties.py:156-162`. `painterly.threads` duplicates Blender's `scene.render.threads_mode` and `threads`,
  which Cycles draws (`intern/cycles/blender/addon/ui.py:853-871`). `docs/tasks/M4/T4.2-properties-ui.md:23` prescribes
  the property: keep it and write the reason in its comment (the core's `Session` takes its own thread count, 0 for one
  per hardware thread).
- TQ.5 F18, `properties.py:171-176`. The description of `reference_scene` does not say that it overrides five knobs
  (`session.py:78-89`). Keep the card's sentence (`T4.2-properties-ui.md:25`) and add the five, by their `ui_name`,
  built from the keys of `apply_reference_knobs()` (`sync/reference.py:72-83`) and `SOCKETS`, or written out; choose
  one, name it. Test, in `test_properties.py`: the description contains the `ui_name` of every key of
  `apply_reference_knobs()` (names from `_painterly.integrator_sockets()`). Mutations: one name dropped; a sixth key
  added to `apply_reference_knobs()`.
- TQ.5 F26, `properties.py:218`. `classes` is never read; `register()` and `unregister()` name the class (`:225`,
  `:232`), while Cycles iterates `classes`. Use `classes` in both. The F5 test shows it: mutation `classes = ()`.
- TQ.5 F25 (c), `__init__.py:33-34`. The comment says material previews "arrive after the render loop (T4.3)"; T4.3
  landed in 93ff499 with no preview session. Say what they wait for now: a preview session and the Blender-scene sync
  (M5). Comment only: no mutation.
- TQ.5 F38 (the restating assertions), `tests/blender/test_properties.py:220`, `:223`, `:330`, `:360`, `:361`. Each
  compares a value with the code it was built from (`test_properties.py:220` and `:223` with
  `properties.py:186-198`; `test_properties.py:330` with `ui.EXCLUDE_PANELS` itself; `test_properties.py:360-361`
  with `presets.py`'s own constants), so it cannot fail. Compare each with an independent source instead: for
  `test_properties.py:223`, the property names Blender registered
  (`PainterlyRenderSettings.bl_rna.properties`, without `rna_type`); for the others, the literal names of the cards
  (`docs/tasks/M4/T4.2-properties-ui.md`) or of the shipped preset's directory (`presets/painterly/render/`). Delete
  a line only when no such source exists, and say why; name your choice per line. Mutation for each kept line: the
  constant or construction it restated changed.
Outcome: `CHECK` and `make test-blender` exit 0; the four tests of F6 each pass when run alone. `git status --porcelain`
lists only allowedPaths.
Notes:
- For each expected value you add or change, write a line `Provenance: <command and output, or source file:line>`
  in your final answer (the queue's integrity check reads these lines; a value without one is escalated).
- Expected values come from the source each bullet names, never from the output of the code under test (AGENTS.md,
  "Expected values are evidence"). If one cannot be met honestly, call `report_blocked`.
- Show each mutation in your answer (command and output), then undo it: `git checkout -- <file>` for a file you did not
  change; for one you changed, save your finished copy under `.ds-scratch/` first and copy it back (`git checkout` would
  discard your work). No mutation may remain in the diff.
- `engine.py`, `ui.py`, `operators.py` and `presets.py` are M4-FIX-TQ5a's, which is committed before this item and also
  extends `RecordingLayout` in `test_properties.py`; `session.py` is M4-FIX-TQ5b's, which may run in parallel. Mutate
  them only to show a mutation, and leave them as you found them. Line numbers are at f5d101e: where M4-FIX-TQ5a
  moved a cited line, find it by its content.
- `intern/cycles/...` is under `MAIN/.cache/vendor/blender-v5.2.2/`; `scripts/modules/addon_utils.py` is Blender 5.2.2's
  (beside the `BLENDER` executable under `5.2/`, or in the bpy package).
- Scratch files go under /tmp or .ds-scratch/. Run the Python targets with R12's PYTHONPATH prefix and R11's prebuilt
  Embree; use BUILD_DIR=build/q (K1, K5). No test may become slower than about 10 s. Where a bullet says "choose one",
  name your choice in your answer.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check test-blender VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `src/blender/addon/__init__.py`, `src/blender/addon/properties.py`, `src/blender/addon/version_update.py`, `tests/blender/conftest.py`, `tests/blender/test_registration.py`, `tests/blender/test_properties.py`, `tests/core/test_manifest.py`
Depends on: M4-FIX-TQ5a.

## M4-FIX-TQ5d: the extension build fails loudly, cleans dist/, is unit-tested, and CI runs the bpy tests
Why (audit TQ.5, `docs/audits/TQ.5.md`, 2026-10-26; F3, F7-F10, F31-F35, F43, F44, F46, F47; line numbers are at
f5d101e): CI runs none of the tests in `tests/blender` (`ci.yml:31-44` installs no `blender` group, so
`tests/blender/conftest.py:32-33` drops them all). `build_extension.py` has no test of its own; `dist/` is never
cleaned, so a second zip makes `validate dist/*.zip` exit 2 (R76); its "neither uv nor scikit-build-core" branch is
dead, because `find_spec("scikit_build_core.build")` raises when the parent is absent (`:203`): the tool exits 1 with a
traceback while four comments promise exit 0. The IT builds its expectation with the functions under test.
Do:
- TQ.5 F3, `.github/workflows/ci.yml:13-44`. CI runs none of the tests in `tests/blender`: `make env` installs no
  `blender` group (`Makefile:34-38`). Add a Linux job that installs it (`make env-blender`, that is
  `uv sync --locked --group dev --group analysis --group blender`; `bpy==5.2.2` is a pip wheel for CPython 3.13,
  `pyproject.toml:23`, `:35`) and runs `make test-blender`, with the checkout, uv and cache steps of job `linux`: a new
  job or steps appended to `linux` after "Symbol audit"; choose one, name it. The bpy module needs system libraries that
  a CI image may lack: list what `ldd` reports for the bpy extension module in the venv and install by `apt-get` what a
  stock ubuntu-24.04 image lacks; you cannot check the image, so name the packages and why. You cannot run CI either:
  show that the YAML parses (`.venv/bin/python -c 'import yaml; yaml.safe_load(open(".github/workflows/ci.yml"))'`;
  `pyyaml` is in the dev group) and that the job's commands run here (`make -n env-blender test-blender`, then the
  verify itself), and write "host-only, not run" for the CI run. Opus watches the landing push's CI. A `blender-it` job
  is not part of this item.
- TQ.5 F7, new `tests/core/test_build_extension.py`. `extension_platform` (`tools/build_extension.py:96-137`),
  `rewrite_manifest` (`:146-183`), `_is_key` (`:140-143`) and the wheel choice (`:186-193`) are pure and untested, and
  the IT's wheel is the host's `linux_x86_64` while the wheels that ship are `manylinux_2_28_x86_64`, `win_amd64` and
  `macosx_11_0_arm64` (`pyproject.toml:69-79`); a wrong platform string makes `--split-platforms` drop the wheel. Load
  the tool by path. Tests: (a) `extension_platform` on `painterly_core-0.1.0-cp312-abi3-<tag>.whl`, expected from the
  examples in the docstring of Blender 5.2.2's `blender_platforms_from_wheel_platform`
  (`scripts/addons_core/bl_pkg/cli/blender_ext.py:2163-2169`): `linux_x86_64` to `linux-x64`, `manylinux_2_28_x86_64` to
  `linux-x64`, `manylinux2014_aarch64` to `linux-arm64`, `win_amd64` to `windows-x64`, `macosx_11_0_arm64` to
  `macos-arm64`, `manylinux2014_x86_64` to `linux-x64`; and BuildError for `macosx_10_9_universal2` (two platforms,
  `:2169`; the manifest carries one), `any` (no native module) and `win32` (no machine part). (b) `rewrite_manifest` on
  a temporary copy of the real manifest: `wheels` and `platforms` land at the top level, before `[build]`; `[build]` and
  every other key are unchanged. (c) the wheel choice (F46 bullet). Mutations: `"manylinux": "linux"` changed; the
  `amd64` entry of the machine table changed; `rewrite_manifest` appending at the end of the file; `_is_key` blind to
  `platforms`.
- TQ.5 F8, `tools/build_extension.py:263-293`, `Makefile:116-117`. Nothing removes a stale zip, so after a version bump
  (or R76's `windows_x64`) `dist/` holds two and `blender --command extension validate dist/*.zip` exits 2. Blender
  replaces a zip of the same name (`blender_ext.py:4872-4874`, unlink then rename) but not one of another name. Before
  the Blender build, remove `dist/<id>-*.zip` for this extension's id (`dist/` is git-ignored) and say on stderr which
  files went; `clean` also removes `dist`. Test: a temporary `dist` with a stale zip of an older version and one of
  another platform, plus a wheel and a zip of another id: after the cleanup the first two are gone and the other two
  stay. Mutations: no removal; every `*.zip` removed.
- TQ.5 F10, `tools/build_extension.py:230-237`. The `uv` branch (`make wheel`) was never run by any check: the verify
  sandbox has no `uv`, so it always takes the backend fallback, while a developer shell has `uv`. Test it with
  `shutil.which` and `subprocess.run` monkeypatched: with `uv` found, the run is `["make", "wheel"]` with
  `cwd=REPO_ROOT`, a non-zero status raises BuildError carrying stdout and stderr, and the wheel returned is the one the
  stand-in run created; with `uv` absent the backend branch runs instead. Mutations: `["make", "extension"]`; the status
  check removed; the two branches swapped.
- TQ.5 F31, `tools/build_extension.py:203`, `:238-246`, `:317-318`.
  `importlib.util.find_spec("scikit_build_core.build")` raises ModuleNotFoundError when `scikit_build_core` is absent,
  so `return False`, the log line, the `unlink` of `zip_path.txt` and `return 0` never run: with neither tool the script
  dies with a traceback and exit 1. Call `find_spec` on the parent package, or catch the error; choose one, name it.
  Decide the contract: a missing wheel tool fails `make blender-it` with a clear message that names both tools, unless a
  named option on the command line asks for the skip (then the script removes `zip_path.txt` and exits 0, as the
  comments promise today); the Makefile's recipes do not pass it. Correct the four comments that describe the dead
  branch: `build_extension.py:19-26`, `Makefile:78-79`, `Makefile:89-90` and
  `tests/blender_it/test_extension_it.py:17-19` (and the skip text at `:91-95`). Test: with `WHEEL_TOOL` and
  `WHEEL_BACKEND_MODULE` of the loaded module set to names that do not exist (so the real `find_spec` runs),
  `main(["--blender", <an existing file>])` returns non-zero and its message names both tools; with the option it
  returns 0 and leaves no `zip_path.txt` (point `ZIP_PATH_FILE` at a temporary path). Mutation: `find_spec` on the
  dotted name again.
- TQ.5 F46, `tools/build_extension.py:186-193`, `:213`, `:230-237`, `:246`. The wheel is "the newest
  `painterly_core-*.whl` by mtime in `dist/`" and the name the backend's `build_wheel` returns (`:213`) is discarded, so
  a newer foreign wheel in `dist/` (another platform or version, say a downloaded CI artefact) would be bundled. Use the
  name `build_wheel` returns. For `make wheel`, take the wheel that run created: compare the `painterly_core-*.whl`
  files of `dist/` (name and `st_mtime_ns`) before and after, or remove them before the run (not when `--wheel` names
  one); fail when it made none or several. Choose one, name it. Test (in `test_build_extension.py`): a newer foreign
  wheel in a temporary `dist` is not returned. Mutation: `_newest_wheel` back.
- TQ.5 F32, `tests/blender_it/test_extension_it.py:205`. The IT builds its expectation with `film.scene_linear` and
  `film.to_blender_rows`, the functions under test (the zip holds the same `film.py`), so a defect inside `film.py`
  applies to both sides. Build `expected` by hand, as `tests/blender/test_render_reference.py:119-128` does: `sum /
  PASSES / 255 * EXPOSURE` in float64, cast to float32, alpha 1, rows reversed with `[::-1]` (SPEC §8, §0); drop the
  `film` load if nothing else needs it. Correct three comments: `test_extension_it.py:10-11` says the equality covers
  "the sync, the film mapping, the row orientation", but `sync.build_scene` is not called in reference mode
  (`session.py:122-133`); `test_extension_it.py:20-21` and `:203-204` say "the same core rendered both sides", but the
  other side is the oracle, a separate program (`src/app/CMakeLists.txt:3-4`), and the exactness rests on the T3.16
  parity result (the docstring of `tests/core/test_oracle_parity.py`). Mutations, after rebuilding the zip (`film.py` is
  not yours: undo with `git checkout -- <file>`): `to_blender_rows` as the identity; `BYTE_MAX = 256`. Each must now
  fail the IT.
- TQ.5 F33, `test_extension_it.py:125-140`, `run_reference.py:44-47`, `:133-145`. The IT writes socket defaults a second
  time (`alpha`, `u2`, `continue_after_emitter`, `seed`) and its render constants twice (`SIZE`, `PASSES`, `CHAIN`,
  `EXPOSURE` there and at `test_extension_it.py:43-46`), while `blender.json` records only `jitter`; a socket-default
  change fails the IT with a pixel mismatch that points at nothing. Have `run_reference.py` write every
  `scene.painterly` socket (names from `_painterly.integrator_sockets()`; vectors as lists) into `blender.json`, and
  build the oracle options from that dict (flag names differ: `u2_mode` is `u2`); `ghost` is not a socket, so it stays a
  literal with a comment naming `build_smallpaint_scene`'s default. Pass the render constants to `run_reference.py`
  (argv or a JSON file) and assert that `blender.json` echoes them. Mutations: set `settings.seed = 5` in `configure()`:
  the IT must still pass (it failed before) and `blender.json` shows 5; a wrong constant written into the echo fails the
  assertion.
- TQ.5 F9, `test_extension_it.py:190-213`. Nothing guards against an all-equal or all-zero image on both sides, and
  `blender.json` is checked for engine, shape and dtype only (`:192-194`). Require `expected[..., :3].max() > 0` (SPEC
  §9: the light's emission is 120, so the oracle image is not black) and `rendered` not constant, and that
  `blender.json` echoes `passes`, `chain`, `exposure` and `output_mode` equal to the test's constants. Mutations: both
  arrays replaced by zeros after loading; `PASSES` changed in `run_reference.py` only.
- TQ.5 F34, `test_extension_it.py:106`, `build_extension.py:232`, `:284`. No subprocess has a timeout, so one hung
  Blender hangs `make blender-it` and the verify. Give each call a named `timeout=` (a constant with a comment: more
  than the longest healthy run you measured, which you quote) and turn `subprocess.TimeoutExpired` into a failure that
  names the command. Test (in `test_build_extension.py`): `subprocess.run` monkeypatched to raise `TimeoutExpired` gives
  a BuildError that names the command. Mutation: the handler removed. For the IT's `_run`, show it once with a timeout
  of a millisecond, then restore it.
- TQ.5 F35, `test_extension_it.py:153-154`. `env = dict(os.environ)` forwards `PYTHONPATH`, `PYTHONHOME` and any
  `BLENDER_*`, so a host with `_painterly` on `PYTHONPATH` could pass with a wheel-less zip. Build the child environment
  without any `BLENDER_*` variable, `PYTHONPATH` and `PYTHONHOME`, set `PYTHONNOUSERSITE=1`, then add
  `BLENDER_USER_RESOURCES`. Have `run_reference.py` write `_painterly.__file__` into `blender.json` and require that it
  lies under the temporary profile (the installed wheel). Mutation: the wheel left out of the zip (in
  `build_extension.py`) with `PYTHONPATH` set to the build directory's `src/blender` in the parent environment: the IT
  must fail.
- TQ.5 F43, `test_extension_it.py:88-101`, `build_extension.py:244`, `:322-327`. `make test-slow` runs the IT against
  whatever zip `zip_path.txt` last named: the tool writes the file only after a successful build (`:326-327`) and
  removes it only on the no-wheel branch (`:244`), so a failed build (`:322-324`; `make wheel` failing at `:234-236`,
  say) leaves the previous run's path. Choose one, name it: compare the zip's mtime with the newest file under
  `src/blender/addon` (ignoring `__pycache__`) and with the wheel the zip bundles, and fail as stale; or store a hash of
  the staged sources in `zip_path.txt` and compare. Put the comparison in a function that `test_build_extension.py` can
  call on a temporary tree. Mutation: the comparison inverted.
- TQ.5 F44, `tools/build_extension.py:249-260`. `stage()` copies the working tree (`copytree`, ignoring only
  `__pycache__`), and the manifest's `paths_exclude_pattern` (`blender_manifest.toml:38`) replaces Blender's default
  exclusions (dot-files, `/*.zip`, `*.blend[1-9]`: `blender_ext.py:4659-4667`), so a `.DS_Store`, a swap file or an
  untracked scratch file in `src/blender/addon` ships; and nothing checks that `wheels/<wheel>` is in the zip (on a
  platform mismatch Blender drops it silently). Stage the tracked files only (`git ls-files` with a list argv) or an
  explicit list; choose one, name it. Add `".*"` to the manifest's `paths_exclude_pattern`
  (`blender_manifest.toml:38`), so a dot-file stays out as Blender's own defaults would keep it out. After the
  Blender run, read the zip's member names with `zipfile` (extract nothing) and fail naming the difference unless
  they equal the staged files plus `wheels/<wheel>`. Test (in `test_build_extension.py`): a synthetic zip with an
  extra `.DS_Store` fails, one without the wheel fails, the exact set passes. Mutation: the check removed.
- TQ.5 F47, `tools/build_extension.py:108`, `:19-20`, `:241`, `Makefile:81-82`. The literal 5 is PEP 427's minimum field
  count (`{distribution}-{version}(-{build})?-{python}-{abi}-{platform}.whl`) and is unnamed: name it, with that
  comment. The text "(BACKLOG, R1)" and "(R1)" cites R1, a queue ruling that is not in the repository: say the reason
  itself (the host has no `uv`). Test (in `test_build_extension.py`): a four-field name
  `painterly_core-0.1.0-cp312-abi3.whl` raises BuildError with "not a wheel filename". Mutation: the limit changed to 4.
Outcome: `CHECK`, `make test-blender` and `make blender-it` exit 0; `dist/` holds one zip and
`blender --command extension validate dist/*.zip` exits 0. For each of `check`, `test`, `lint`, `build` and `audit`,
`make -n <target>` is byte-identical before and after (trailing spaces stripped; the "before" is
`git show HEAD:Makefile > /tmp/Makefile.orig` and `make -n -f /tmp/Makefile.orig <target>`), and `make -n clean` differs
by `dist` only. `git status --porcelain` lists only allowedPaths.
Notes:
- For each expected value you add or change, write a line `Provenance: <command and output, or source file:line>`
  in your final answer (the queue's integrity check reads these lines; a value without one is escalated).
- Expected values come from the source each bullet names, never from the output of the code under test (AGENTS.md,
  "Expected values are evidence"). If one cannot be met honestly, call `report_blocked`.
- Show each mutation in your answer (command and output), then undo it: `git checkout -- <file>` for a file you did not
  change; for one you changed, save your finished copy under `.ds-scratch/` first and copy it back (`git checkout` would
  discard your work). No mutation may remain in the diff.
- `scripts/...` is under `5.2/` beside the `BLENDER` executable (`MAIN/.cache/blender/blender-5.2.2-linux-x64/`).
- Scratch files go under /tmp or .ds-scratch/. Run the Python targets with R12's PYTHONPATH prefix and R11's prebuilt
  Embree; use BUILD_DIR=build/q (K1, K5). No test may become slower than about 10 s. Where a bullet says "choose one",
  name your choice in your answer.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check test-blender blender-it VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1" && /run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender --command extension validate dist/*.zip`
allowedPaths: `tools/build_extension.py`, `Makefile`, `tests/blender_it/test_extension_it.py`, `tests/blender_it/run_reference.py`, `tests/core/test_build_extension.py`, `.github/workflows/ci.yml`, `src/blender/addon/blender_manifest.toml`

## M5-T5.1: camera sync
Card: `docs/tasks/M5/T5.1-sync-camera.md`. Depends on: M4-T4.4.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify adds the card's Blender targets to `CHECK`, whose `make check` runs no Blender test (`check: lint build test`).
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check test-blender VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`

## M5-T5.2: geometry sync (meshes and instances)
Card: `docs/tasks/M5/T5.2-sync-geometry.md`. Depends on: M5-T5.1.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify adds the card's Blender targets to `CHECK`, whose `make check` runs no Blender test (`check: lint build test`).
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check test-blender VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`

## M5-T5.3: lights, world and constant materials
Card: `docs/tasks/M5/T5.3-sync-lights-world-materials.md`. Depends on: M5-T5.2.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify adds the card's Blender targets to `CHECK`, whose `make check` runs no Blender test (`check: lint build test`).
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check test-blender VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`

## M5-T5.4: the smallpaint scene in Blender, and parity of the full Blender path
Card: `docs/tasks/M5/T5.4-reference-blend-parity.md`. Depends on: M5-T5.3.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify adds the card's Blender targets to `CHECK`, whose `make check` runs no Blender test (`check: lint build test`).
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check test-blender blender-it VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`

## M6a-T6.1: vendor Cycles kernel/types.h with a CPU KernelGlobals shim
Card: `docs/handoff/drafts/M6a/T6.1-vendor-kernel-types.md`. Vendoring runs only through `tools/vendor_sync.py`, as
the card says.
Depends on: M3-FIX-T3.28.
Outcome: the card's Acceptance, translated; `CHECK` exits 0; and `make vendor-check` passes.
- The verify counts the card's test cases (and assertions where the card states them), so it cannot pass with none run: doctest prints `Status: SUCCESS!` for a filter that matches nothing.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest" && build/q/src/test/painterly_tests --test-case='cycles kernel*' | grep -qE '^\[doctest\] test cases: +4 \| +4 passed \| +0 failed \|'`

## M6a-T6.2: fragment extraction and the generated SVM switch
Card: `docs/handoff/drafts/M6a/T6.2-fragment-extraction.md`. Depends on: M6a-T6.1.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The pin adds R12's PYTHONPATH and R11's prebuilt Embree to the planner's verify, as the other M6a pins have, and
  runs the card's two test files by name, so the verify fails if either is missing or collects nothing.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1" && PYTHONPATH="$PWD/analysis" PAINTERLY_BUILD_DIR="$PWD/build/q" /run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -m pytest tests/core/test_vendor_fragments.py tests/core/test_gen_svm_switch.py -q`

## M6a-T6.3: stack-only SVM evaluators and byte-code doctests
Card: `docs/handoff/drafts/M6a/T6.3-svm-stack-nodes.md`. Depends on: M6a-T6.2.
- The card's "experiment 007" (X-svm probe) is a stale number: 007 is taken.
- Create it as the next free experiment number at run time, with today's date, following
  `docs/tasks/M1/_experiment_protocol.md`. Its Conclusion is a DRAFT.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify counts the card's test cases (and assertions where the card states them), so it cannot pass with none run: doctest prints `Status: SUCCESS!` for a filter that matches nothing.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1" && build/q/src/test/painterly_tests --test-case='cycles svm stack nodes:*' | grep -qE '^\[doctest\] test cases: +7 \| +7 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles svm stack nodes:*' | grep -qE '^\[doctest\] assertions: +131 \| +131 passed \| +0 failed \|'`

## M6a-T6.4: vendored shader graph, constant folding, core shader nodes, cycles_scene
Card: `docs/handoff/drafts/M6a/T6.4-shader-graph.md`. Depends on: M6a-T6.3.
- Skip the card's decision 6 (defining `NOMINMAX`). T2.11 already defines it PUBLIC on `cycles_util`, so don't add it
  again.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify counts the card's test cases (and assertions where the card states them), so it cannot pass with none run: doctest prints `Status: SUCCESS!` for a filter that matches nothing.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1" && build/q/src/test/painterly_tests --test-case='cycles shader graph*' | grep -qE '^\[doctest\] test cases: +7 \| +7 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles shader graph: links use UI names; parameters use member names' | grep -qE '^\[doctest\] test cases: +1 \| +1 passed \| +0 failed \|'`

## M6a-T6.5: the SVM compiler, PainterlyShaderManager, graph → byte code → evaluation
Card: `docs/handoff/drafts/M6a/T6.5-svm-compiler.md`. Depends on: M6a-T6.4.
- The card's "experiment 007 part 2" (gate G2-svm) belongs to the experiment M6a-T6.3 created. Use that directory and
  number.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify counts the card's test cases (and assertions where the card states them), so it cannot pass with none run: doctest prints `Status: SUCCESS!` for a filter that matches nothing.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1" && build/q/src/test/painterly_tests --test-case='cycles svm compiler:*' | grep -qE '^\[doctest\] test cases: +6 \| +6 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles svm compiler:*' | grep -qE '^\[doctest\] assertions: +85 \| +85 passed \| +0 failed \|'`

## M6a-T6.6: texture and texture-coordinate SVM nodes
Card: `docs/handoff/drafts/M6a/T6.6-svm-textures.md`.
Review findings: `docs/handoff/findings/M6a-reviews.json`, keys `review T6.6 executability` and
`review T6.6 verbatim-vendoring`, field `latest`.
Depends on: M6a-T6.5.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify counts the card's test cases (and assertions where the card states them), so it cannot pass with none run: doctest prints `Status: SUCCESS!` for a filter that matches nothing.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1" && build/q/src/test/painterly_tests --test-case='cycles svm textures:*' | grep -qE '^\[doctest\] test cases: +12 \| +12 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles svm textures:*' | grep -qE '^\[doctest\] assertions: +36 \| +36 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles texture nodes:*' | grep -qE '^\[doctest\] test cases: +4 \| +4 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles texture nodes:*' | grep -qE '^\[doctest\] assertions: +85 \| +85 passed \| +0 failed \|'`

## M6a-T6.7: closure SVM nodes and BSDF lookup tables
Card: `docs/handoff/drafts/M6a/T6.7-svm-closures.md`.
Review findings: `docs/handoff/findings/M6a-reviews.json`, keys `review T6.7 executability` and
`review T6.7 verbatim-vendoring`, field `latest`.
Depends on: M6a-T6.6.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify counts the card's test cases (and assertions where the card states them), so it cannot pass with none run: doctest prints `Status: SUCCESS!` for a filter that matches nothing.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1" && build/q/src/test/painterly_tests --test-case='cycles svm closures:*' | grep -qE '^\[doctest\] test cases: +12 \| +12 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles svm closures:*' | grep -qE '^\[doctest\] assertions: +163 \| +163 passed \| +0 failed \|'`

## M6a-T6.8: image texture SVM nodes on the CPU and an in-memory ImageManager
Card: `docs/handoff/drafts/M6a/T6.8-svm-images.md`.
Review findings: `docs/handoff/findings/M6a-reviews.json`, keys `review T6.8 executability` and
`review T6.8 verbatim-vendoring`, field `latest`.
Depends on: M6a-T6.7.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify counts the card's test cases (and assertions where the card states them), so it cannot pass with none run: doctest prints `Status: SUCCESS!` for a filter that matches nothing.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1" && build/q/src/test/painterly_tests --test-case='cycles svm images:*' | grep -qE '^\[doctest\] test cases: +8 \| +8 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles svm images:*' | grep -qE '^\[doctest\] assertions: +122 \| +122 passed \| +0 failed \|'`

## M6a-FIX-VS1: vendor_sync reads fragments from the pinned commit, and its rules are tested on bad input
Why (Sonnet reader A and audit A, 2026-10-24/25): `tools/vendor_sync.py` says that upstream bytes come from the pinned
commit's git objects, and that every subcommand refuses a checkout whose HEAD is not the pin (docstring `:32-37`). It keeps
one exception: `_fragment_source` (`:1405-1426`) reads fragments from the checkout's working tree (`:39-42`, as card T6.2
specified). T3.27's reason for the rule applies to them too: a locally edited, deleted or untracked checkout file, or
end-of-line conversion at checkout, must not reach a hash, and VENDORED.toml hashes every fragment (A1). `_fragment_keys`
(`:315-323`) lets `params` through on `svm_case`, `node_define` and `define` entries, which cannot carry it (A2). Most
branches of `check_fragment_rules` (`:348-443`) never see bad input, and no test has a `function` entry with `params`
(A6). On Windows a text-mode write puts CRLF into the fixture source that `extract_fragment` refuses
(`tests/core/test_vendor_fragments.py:586-599`), and `cmd_extract` writes through text-mode stdout (`:1917`) while it
reports the sha256 of the LF bytes (A7). `tests/core/test_gen_fragment_units.py:448` replaces the whole environment, which
drops SYSTEMROOT on Windows (B3).
Do:
- In `tools/vendor_sync.py`, read fragments as `upstream_blob` reads whole files (`:620-630`, `git cat-file blob` of the
  pinned commit):
  - `_fragment_source` (`:1405-1426`) returns the blob of `manifest.upstreams[upstream]` at `upstream_path`, decoded as
    UTF-8, and never reads the working tree. It keeps its "not pinned" and "no checkout" errors. A `VendorError` from the
    blob read and a decode failure become `FragmentError`, with a message that names `<upstream>:<path>` and the commit.
  - Before it reads, it refuses a checkout whose HEAD (`_git_head`, `:553-565`) is not the pin, with the text that
    `ensure_checkout` gives (`:675-678`: "<dir> is at <head>, not the pinned <commit>; delete it and rerun fetch"). Put the
    comparison and the message in one helper that both call. `_fragment_source` is the only reader of fragment sources
    (`_Sources.get`, `:909-915`, and `cmd_list_anchors`, `:1932`), so this covers `add-fragment`, `extract`,
    `list-anchors` and the API functions. `_fragment_checkouts` (`:1678-1688`) stays as it is: it never fetches, and a
    missing directory is an error.
  - Rewrite the module docstring (`:32-42`): delete the exception for fragments, and say that their bytes come from the
    pinned commit too. Correct the docstrings of `_Sources` (`:902`, `:910`) and `_fragment_source` (`:1408`) the same
    way. Card T6.2 (`docs/handoff/drafts/M6a/T6.2-fragment-extraction.md:378, 470-471, 868`) names the working tree; this
    item replaces that, and the card stays as it is.
- A2: `_fragment_keys` (`:315-323`) allows `params` only for the kinds in `PARAM_KINDS` (`:125`, `member` and `function`).
  On `svm_case`, `node_define` and `define` it is an unexpected key, reported by the existing message (`:371-375`).
- A7: `cmd_extract` (`:1917-1918`) writes `fragment.text.encode("utf-8")` to `sys.stdout.buffer` and flushes, so the
  bytes on stdout are the bytes whose sha256 goes to stderr (`:1919-1920`), on every platform.
- B3: `tests/core/test_gen_fragment_units.py:448` passes `env={**os.environ, "PYTHONHASHSEED": seed}`, as
  `tests/core/test_gen_svm_switch.py:323` does (add `import os`). `tools/gen_fragment_units.py` runs no subprocess and
  reads no PATH, so the PATH override goes. Name this choice in your answer.
- Fixtures. Three files call `add_fragments` on a plain-directory checkout: `test_vendor_fragments.py` (`TEST_MANIFEST`
  `:35-48`, `_tree` `:427-441`), `test_gen_fragment_units.py` (`UPSTREAM_TABLE` `:23-28`, `_setup` `:155-194`,
  `test_registry_needs_a_node_define` `:348-377`) and `test_gen_svm_switch.py` (`TEST_UPSTREAM` `:37-43`, `_build_tree`
  `:185-220`). After the change to `_fragment_source` they need a git checkout. Each builds its checkout as a one-commit
  git repository under `tmp_path` and writes that commit's id into the `commit` line of its manifest. Run git as
  `tests/core/test_vendored.py:57-82` does (no user or system configuration, so no signing and no `core.autocrlf`; a
  fixed identity). Write and read every fixture file with `write_bytes` and `read_bytes`.
- New tests. Each fails under the mutation named after it; the mutations are made in `tools/vendor_sync.py` itself, so
  save your finished file under `.cache/` first and put it back afterwards (`git checkout` would discard your work). Show
  each mutation and its failing output in your answer.
  - The pinned commit, `test_vendor_fragments.py`. Step 6 of `test_manifest_round_trip` (`:581-599`) edited a working-tree
    line, which no longer reaches the extraction. Keep its outcomes (`sync_fragments` raises `FragmentError` naming the
    fragment and writes no byte; `check_fragments(manifest, checkouts)` names it), reached by committing the changed line
    in the fixture and pointing the temporary manifest's pin at that commit. Add: that old edit, left uncommitted, changes
    nothing (`check_fragments(manifest, checkouts) == []`, and `sync_fragments` rewrites the same bytes); the same with
    the file deleted from the working tree; a file that exists only in the working tree is refused with
    `<path> is not a file in upstream cycles at <commit>`; with `core.autocrlf true` and the file checked out again (as
    `test_vendored.py:164-174`) the working file has CRLF and the extraction still equals the LF fragment. Mutation:
    `_fragment_source` reads `<checkout>/<root>/<path>` again.
  - The pin, `test_vendor_fragments.py` and `test_vendored.py`. A checkout whose HEAD is a later commit is refused by
    `add_fragments`, `sync_fragments` and `check_fragments`, with the text above, and the manifest and the `.inc` files
    stay as they were. In `test_vendored.py`, add `add-fragment`, `extract` and `list-anchors` to the parametrization of
    `test_a_checkout_off_its_pin_is_refused` (`:237-258`), on `util/a.h` (for example `define A`). Mutation: the HEAD
    refusal deleted.
  - A2, `test_vendor_fragments.py`: for each of `svm_case`, `node_define` and `define`, a valid entry with `params = "x"`
    is refused by `check_fragment_rules` and by `load_manifest`, with "unexpected ['params']"; the same entry without
    `params` is accepted. Mutation: `_fragment_keys` allows `params` for every kind but `span`.
  - A6, `test_vendor_fragments.py`: a `function` entry with `params` is accepted by `check_fragment_rules`, by
    `load_manifest` and by the writer round trip (its name has the `-<params>` suffix, `fragment_name` `:1392-1394`).
    Mutation: `_fragment_keys` allows `params` for `member` only. Then one case for each other branch of
    `check_fragment_rules`, `_fragment_string` and `_fragment_lines` (`:307-345`, `:360-443`; a `params` that is not a
    string is tested at `:664`): not a table; an unknown kind, and a kind that is not a string; a missing key and an
    unexpected key, each for `span` and for another kind; a character outside printable ASCII; an unknown upstream; a
    non-canonical `upstream_path`; an invalid span id; an empty `begin`, an empty `end`; an invalid anchor for a `function`
    and for a `member`; `upstream_lines` that is not a list of two integers, that holds a bool, and that breaks
    `1 <= first <= last`; a sha256 that is not 64 lowercase hex digits; a name other than the one the fields give; a name
    used twice; a file that is vendored whole and fragmented; two overlapping ranges, including two that share one line,
    while `[a, b]` next to `[b + 1, c]` and equal ranges in two different files are accepted. Each case starts from an
    entry that the test has shown to pass, changes exactly one thing, and expects `FragmentError` with `match=` a phrase of
    that branch's own message. Mutation: the `raise` of that branch deleted (one run per case; a script that applies them
    in turn and prints "mutation, first failing test" is fine).
  - A7, `test_vendored.py`, on its `tree` fixture: `extract` of `util/a.h` with `sys.stdout` replaced by
    `io.TextIOWrapper(io.BytesIO(), encoding="utf-8", newline="\r\n")` (what Windows text mode does to "\n"): the bytes
    behind it equal the fragment's LF bytes, and their sha256 is the one on stderr. Mutation: `cmd_extract` writes
    `fragment.text` to `sys.stdout` again.
- TQ.3 F27 (`docs/audits/TQ.3.md`): every git failure is reported as a path that is not in upstream (`_not_in_upstream`,
  `tools/vendor_sync.py:596-597`) or a root that is not a directory (`:701`). Report a git failure that is not a missing
  path as what it is, with git's stderr, and test it on a fixture whose blob is deleted from `.git/objects`. Mutation: the
  old message back.
- Change no existing assertion. The edits to existing tests are the fixtures above, step 6 (its mechanism, not its
  outcomes), B3, and the added parametrized cases.
Outcome:
- `CHECK` exits 0.
- `git grep -n write_text -- tests/core/test_vendor_fragments.py` prints nothing.
- Host only, after landing (Opus): `python -I tools/vendor_sync.py check --upstream` exits 0 on the real checkout, so the
  pinned blobs give every recorded fragment hash and line range.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `tools/vendor_sync.py`, `tests/core/test_vendor_fragments.py`, `tests/core/test_gen_fragment_units.py`, `tests/core/test_gen_svm_switch.py`, `tests/core/test_vendored.py`

## M6a-FIX-X011: experiment 011's probes record what they measured
Why (readers A and B; Opus's Conclusion of 2026-10-25 in `experiments/011-2026-10-23-svm-probe/README.md`): three places
where the probes or their data files differ from what the README pre-registers or reports. None changes a verdict.
`probe.py:227` decides H3 by `failed == 0 and passed > 0`; the pre-registered rule (README.md:98) is "3 passed assertions
and 0 failed" for each of the five cases (A3). Both probes write the absolute build directory of the sprint clone into
their data files (`probe.py:300`, `probe_part2.py:561`; `results.json:74` and `results_part2.json:126`) (A4).
`probe_part2.py:445` looks for a line that starts with `#deps `, but `ninja -t deps` prints `<object>: #deps N, ...`, so
`instrument_m6` never finds the list and its six closure fields are 0 in `results_part2.json`, where they should say "not
measured" (M6; part 1's `_m2`, `probe.py:256-276`, skips the first line and did measure).
Do:
- `probe.py`: decide H3 as H2 is decided (`H2_CASES` `:66`, `_h2` `:208-217`): a table `H3_CASES` (`:67`) of the five names
  with the passed count 3, and `supported` only if every case reports exactly that count and 0 failed. A comment cites
  README.md:98 as the origin of the 3.
- `probe.py:300` and `probe_part2.py:561`: record the build directory relative to the repository root, as a POSIX path
  (`Path(os.path.relpath(BUILD, REPO)).as_posix()`). It is never absolute; a build directory outside the repository gives a `..` path,
  not an error. `probe.py:311` builds its output path inline: give it a module-level name, as `probe_part2.py` has `EXP`
  (`:38`), so that a test can redirect it.
- `probe_part2.py`, `instrument_m6` (`:424-484`):
  - Move the parsing of the `ninja -t deps` text (`:444-471`) into a function of that text, so that a test can call it
    without ninja and without the `os.utime` of `src/test/test_cycles_svm_compiler.cpp` (`:476`).
  - Recognise the header as ninja prints it: a first line `<object>: #deps <N>, deps mtime <T> (VALID)`, then one indented
    path per line. After `CHECK`, run
    `ninja -C build/q -t deps src/test/CMakeFiles/painterly_tests.dir/test_cycles_svm_compiler.cpp.o | head -1` and quote
    that line in your answer.
  - With no header line, the six closure fields are `None` (JSON `null`, "not measured") and not 0: `deps_total`,
    `deps_third_party_cycles`, `deps_third_party_cycles_lines`, `deps_shim`, `deps_src_painterly`, `deps_generated`
    (initialised at `:428-433`, assigned at `:458-471`). The compile times keep their code.
- The committed data. Do not run either probe. Write a throwaway script under `.cache/` (not committed: it produces no
  number, only rewrites a provenance field and six "not measured" markers, and Opus asked for its source and output in
  your answer) that:
  - loads each file with `json`, changes exactly the fields below, and writes it back as
    `json.dumps(data, indent=2, sort_keys=True) + "\n"`, which is how the probes write it; it first asserts that this
    reproduces each unchanged file byte for byte;
  - `build_dir`, in both files: asserts that the old value ends in `/build/q`, and sets `build/q` (README.md:246-248: the
    part-1 run set `PAINTERLY_BUILD_DIR=build/q`; both old values are the same path of sprint S1's clone);
  - the six M6 fields of `results_part2.json`: asserts that each is 0, and sets `null`;
  - prints, for each file, every JSON path whose value differs from `git show HEAD:<path>`.
  Run it with `MAIN/.venv/bin/python -P -s`, and put its source, the command and the output in your answer. No measured
  value may change.
- `README.md`: add one line under `## Results`, after the paragraph that ends "M6's times are measured." (`:351-354`):
  what was rewritten (the two `build_dir` values, from the absolute path of the sprint clone to `build/q`; the six M6
  closure fields, from 0 to `null`), by whom (DeepSeek, item M6a-FIX-X011) and when (the date `date -u +%F` prints), and
  that no measured value changed. Leave the Conclusion and every pre-registered section as they are.
- Tests, in a new `experiments/011-2026-10-23-svm-probe/test_probes.py` (it follows
  `experiments/005-2026-10-08-native-coexistence/test_bindings.py`: load the probes by path). Each fails under the
  mutation named after it. The mutations are made in the probes, so save your finished files under `.cache/` first and put
  them back afterwards; show each failing output in your answer.
  - H3: with `_doctest_assertions` stubbed, (3, 0) for all five cases is supported; (2, 0), (4, 0), (3, 1) and (0, 0) in
    any one case are not. Mutations: `_h3` back to `passed > 0`; `failed == 0` dropped.
  - `build_dir`: `main()` of each probe, with every instrument stubbed and the output redirected into `tmp_path`, writes
    `"build_dir": "build/q"` for `BUILD_DIR` given as `build/q` and as the absolute path `REPO/build/q`, and a `..` path
    for a directory outside `REPO`; it is never absolute. Mutation: `str(BUILD_DIR)` back in either `main`.
  - M6: the parsing function gives `None` for all six fields on an empty output and on a `<object>: deps not found` line
    (what ninja prints for a target without recorded dependencies). On a header plus indented paths that the test builds
    (under a temporary `REPO` and `BUILD`, with files under `third_party/cycles/` of known newline counts), it gives the
    counts that the construction gives, so no count is read from the code under test. Mutations: the header test back to
    `line.startswith("#deps ")`; `None` back to 0; one of the path prefixes changed.
Outcome:
- `CHECK` exits 0.
- `git diff --numstat HEAD -- experiments/011-2026-10-23-svm-probe/results.json experiments/011-2026-10-23-svm-probe/results_part2.json`
  prints one changed line for `results.json` (`build_dir`) and seven for `results_part2.json` (`build_dir` and the six M6
  fields), and the script's list in your answer shows no other path.
- `git grep -n --untracked "/run/media" -- experiments/011-2026-10-23-svm-probe` prints nothing.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `experiments/011-2026-10-23-svm-probe/probe.py`, `experiments/011-2026-10-23-svm-probe/probe_part2.py`, `experiments/011-2026-10-23-svm-probe/results.json`, `experiments/011-2026-10-23-svm-probe/results_part2.json`, `experiments/011-2026-10-23-svm-probe/README.md`, `experiments/011-2026-10-23-svm-probe/test_probes.py`

## M6a-FIX-SVMT: the SVM node doctests fail when the node they test changes
Why (reader B, reader C and audit B): mutations of the code under the T6.5-T6.8 doctests that no test notices.
B2: the shader-manager checks of `src/test/test_cycles_svm_compiler.cpp` reach 2 of the 15 flag conditions of
`PainterlyShaderManager::device_update_common` (`src/painterly/scene/svm/shader_manager.h:273-323`). Every expectation is
`default_shader_flags` (`:189-195`: SD_VOLUME_MIS and SD_USE_BUMP_MAP_CORRECTION; compared at `:319, 373, 420, 421`).
`use_volumes` and `transparent_shadows` are compared with their zero-initialised values (`:374-375`), so deleting the
writes at `shader_manager.h:119` and `:339` passes. `rgb_to_y` is compared with the manager's own member (`:378-383`),
so nothing pins its value; and the value varies with the CPU, because `transform_inverse` runs a different function on
AVX2 CPUs (FMA in `transform_inverse_cross`, `third_party/cycles/util/transform.h:500-516`; dispatch `:572-584`).
C6, as read from the tests. Textures `:515-517` and `:658-699`: the brick case has Mortar Smooth 0 and Squash 1, and the
noise case samples only points whose fractional parts are all 0.5. Closures `:332-337`: the thin-film table is compared
with another ShaderManager's table. Closures `:749-756` is the end of the policy case (Thin Wall, lobe kinds only), where
`collect.h:110-114` (the DIELECTRIC and DIELECTRIC_TINT cases of `painterly_svm_reflection_color`) has no case: no test sets
Coat Weight. Images `:501-556`: only the float pixels are tested for non-finite values. Images `:746`: `use_transform_3d`
is checked, `transform_3d` and `average_color` are not.
Do:
- For every case below:
  - Add new `TEST_CASE`s and change no existing assertion, case or line. Give each a name that does not begin with
    `cycles svm compiler:`, `cycles svm textures:`, `cycles svm closures:` or `cycles svm images:`: the verify lines of
    M6a-T6.5 to M6a-T6.8 count the cases and assertions that match those four.
  - Take every expected value from a script that you run (double precision), and paste its command and output. Choose
    inputs for which every float32 operation of the upstream formula is exact, as the header of
    `test_cycles_svm_textures.cpp` (`:4-18`) requires, so that the order of operations and FMA cannot change the result.
    Where no such input exists, do not pin the value with `==`: derive a bound in a comment (CLAUDE.md rule 2), or call
    `report_blocked` naming the value.
  - Show each mutation, its failing output, and restore it. A mutation in our code (`src/painterly/`, `src/cycles/shim/`)
    is made in the file and undone with `git checkout -- <file>`; none of those files is in allowedPaths. A mutation of a
    vendored header is never made in `third_party/`: copy the header to `.cache/mutants/active/<same relative path>`,
    change the copy, and build into `build/qm` (`make build BUILD_DIR=build/qm` with the CHECK knobs and
    `-DCMAKE_CXX_FLAGS=-iquote$PWD/.cache/mutants/active` added to `CMAKE_ARGS`; a quoted include finds an `-iquote`
    directory before the `-isystem third_party/cycles` that the tests use). `touch` the test source and rebuild after each
    change of the copy, because the dependency file lists the original path. Remove the copy afterwards.
  - Upstream files named below as `scene/shader.cpp:N`, `scene/svm.cpp:N` or `util/colorspace.cpp:N` are in
    `MAIN/.cache/vendor/blender-v5.2.2/intern/cycles/`; read them by those exact paths.
- B2, `test_cycles_svm_compiler.cpp`:
  - Flags. One case per condition of `device_update_common` (upstream `scene/shader.cpp:642-688` and `:695-697`): a shader
    where only that condition holds gets exactly its flag(s) on top of the two defaults, compared with constants written
    from the upstream lines (`SD_*` of `kernel/types.h`), never computed by the code under test. Include: `has_volume` also
    sets SD_HAS_TRANSPARENT_SHADOW (`:279-285`); each operand of the three conjunctions (`:273`, `:287`, `:290`) alone gives
    no flag; each of the three `volume_sampling_method` values (only EQUIANGULAR and MULTIPLE_IMPORTANCE give one); each of
    the three `displacement_method` values (only BUMP gives none, `:314`); both values of `use_bump_map_correction`. The
    `Shader` members are public (`src/cycles/shim/scene/shader.h:73-117`). `device_update_common` is protected and the
    class is `final` (`shader_manager.h:43`, `:154`, `:252`), so set the members on a shader with a valid graph (as
    `prepare_unfolded()` leaves one) and call `device_update_post()`. The compiler that it runs only ever sets some `has_*`
    members to true (upstream `scene/svm.cpp:578-581`, `:586-589`, `:795-804`), so a member you set stays set; check that
    every member you expect to be false is false.
  - Integrator. `use_volumes` (`:111-119`): 1 for a referenced shader whose graph links Output.Volume
    (`device_update_pre` computes `has_volume` from the link, `:88`); 0 when only an unreferenced shader has a volume
    (`reference_count()`, `:111`); 0 when none has. `transparent_shadows` (`:331`, `:339`): 1 when some shader's flags
    contain SD_HAS_TRANSPARENT_SHADOW, 0 otherwise.
  - `rgb_to_y` (`:352-353`). The shim computes it as `.y` of `transform_inverse(xyz_to_rgb)` for the Rec.709 matrix at
    `src/cycles/shim/scene/shader.cpp:60-73` (upstream `util/colorspace.cpp:687-703`, `scene/shader.cpp:1018-1019`), so a
    constant would be wrong on some CPUs. Write the matrix out in the test, call `transform_inverse` on it there, and
    compare the film's `x`, `y` and `z` bit for bit with `.y` of the result, and `w` with 1.0f
    (`make_float4(float3)`, `util/types_float4.h:89-92`). Both sides run the same function on the same bits on the same
    CPU, so the equality holds on every CPU; say so in the comment. Keep the existing comparison. If you cannot justify the
    equality, derive a bound or `report_blocked`.
  - Mutations: each `flag |= ...` of `:274-322` deleted (one run each); each condition negated; `&&` to `||` at `:273`,
    `:287`, `:290`; `shader_manager.h:119`, `:339` and `:353` deleted; the `if` of `:111` removed; `:331` deleted;
    `shader.cpp:73` `.y` to `.x`; one digit of a matrix constant at `shader.cpp:60-71`. A script that applies them in turn
    and prints "mutation, first failing check" is fine.
- C6, `test_cycles_svm_textures.cpp` (mutations in copies of the vendored headers):
  - Brick (`:501-551`). Mortar Smooth 0 (`:515`) means the smoothed mortar of `brick.h:62-65` never runs; Squash 1 (`:517`)
    means `brick.h:43` (`brick_width *= (rownum % squash_frequency) ? 1.0f : squash_amount`) and the squashed width in the
    offset (`brick.h:44`) cannot show. Survivors: `brick.h:64` `smoothstepf(min_dist / mortar_smooth)` replaced by
    `min_dist / mortar_smooth` or by `1.0f`; `brick.h:63` without `1.0f -`; `brick.h:43` with `1.0f` and `squash_amount`
    swapped, or deleted; `brick.h:44` using the unsquashed width. Add a case with a Squash other than 1 (dyadic) on a row
    where `rownum % squash_frequency == 0` and on one where it is not, and a point inside the mortar band with Mortar
    Smooth above 0 so that the mortar factor f is strictly between 0 and 1 (the colour is then
    `color1 * (1 - f) + mortar * f`, `brick.h:106`, and Fac is f).
  - Noise (`:654-704`). Scale 2 puts the point at (1.5, 1.5, 1.5) (`:658-659`) and the 1D sample at 0.5, so every
    fractional part is 0.5, `fade()` is 0.5 and every mix weight is 0.5. Survivors: `fade()` returning `t` (`noise.h:20` for
    1D; `noise.h:285-290` for the SSE 3D code that these tests compile, see the comment at `:228-231`); the y and z weights
    swapped in `tri_mix` (`shuffle<1>(f)` and `shuffle<2>(f)`, `noise.h:372-373`); the weights swapped in `perlin_1d`
    (`noise.h:41`); `sum += t * amp` without `amp` (`fractal_noise.h:23`, `:73`), because the second octave is evaluated at
    a lattice point where t is 0 (test `:694-696`). Add cases whose fractional parts differ per axis (0.25 on one axis and
    0.5 on the others, rotated over the three axes; `fade(0.25)` is 53/512 and `fade(0.75)` is 459/512), a 1D case at a
    fractional part other than 0.5, and a detail-1 case whose second octave is not at a lattice point. The inputs must
    keep every float32 operation of `perlin_3d`, `perlin_1d` and `noise_fbm` exact: show by script that each intermediate
    result has at most 24 significant bits. If a survivor above cannot be killed that way, say which and why.
- C6, `test_cycles_svm_closures.cpp`:
  - Thin film (`:329-337`). `ThinFilmProbe` (`:240-257`) is another ShaderManager, which builds its table with the same
    `compute_thin_film_table` (`shader.cpp:108-169`) as the manager under test: a change to that function changes both
    tables and passes. Only the zero imaginary DC term (`:337`) is independent. Keep those checks, and add one that
    recomputes all `6 * THIN_FILM_TABLE_SIZE` entries (`kernel/types.h:37`) in the test from the raw `table_thin_film_cmf`
    (`scene/shader.tables`, included at `:40`) and the Rec.709 matrix written out in the test, through `transform_direction`
    and the normalization by row 0, operation by operation as `shader.cpp:143-168` does, and compares bit for bit.
    `transform_direction` multiplies and adds with `madd` (`util/transform.h:157-177`, `util/math_float4.h:238-251`),
    which is fused on NEON and unfused on the x86-64 builds, so state in a comment why the equality holds on every CPU
    (the same function on the same bits, in a build where the choice is fixed), or derive a bound, or call `report_blocked`.
    Mutations (in `src/cycles/shim/scene/shader.cpp`): two of the six store indices at `:162-167` swapped;
    `* normalization.x` dropped at `:162`; `rgbImag` taken from `xyzReal` (`:153`); one digit of a matrix constant
    (`:60-71`).
  - Coat and Dielectric Tint (`collect.h:107-127`). No Principled variant sets Coat Weight (variants at `:624-647` and
    `:710-724`), so the DIELECTRIC case (`:110-111`, reached only by the coat, `closure.h:146-176`, whose call at `:169` is
    `bsdf_microfacet_setup_fresnel_dielectric`, `bsdf_microfacet.h:1038-1047`) and the DIELECTRIC_TINT case (`:112-114`) run in
    no test. DIELECTRIC_TINT is set only by `bsdf_microfacet_setup_fresnel_dielectric_tint` (`bsdf_microfacet.h:941-961`), which
    nothing calls, so reach it with a hand-made closure as the conductor is (`:776-806`, without the albedo estimate). Add
    (1) a Principled with Coat Weight and Coat IOR set so that F0 is exact (IOR 3 gives `F0_from_ior` 0.25,
    `bsdf_util.h:290-293`): check that the first lobe is a mirror lobe with weight `Coat Weight * F0` per channel, and the
    kinds of the lobes below it (their weights come through the lookup tables; check them only if you can derive them
    exactly, as `principled_reference()` does); (2) a hand-made `FresnelDielectricTint` closure with different
    reflection and transmission tints: its lobe weight is the closure weight times `F0_from_ior(ior)` times the
    reflection tint per channel. Mutations (in `src/painterly/kernel/svm/collect.h`): `:111` returning `one_spectrum()`;
    `:113-114` without `F0_from_ior`, without `reflection_tint`, and with `transmission_tint` instead.
- C6, `test_cycles_svm_images.cpp`:
  - Non-finite pixels (`:501-504`, `:552-558`; `src/cycles/shim/scene/image.cpp:80-99`). The float version of
    `zero_if_not_finite` (`:91-99`) is tested for channel x of one texel only. Add texels with a non-finite value in y, in z
    and in w, each alone (inf and NaN), sampled to zero. Mutations (in `image.cpp`): each of the `!std::isfinite` operands at
    `:93-94` deleted, one run each.
  - The half version (`:80-89`) cannot be reached through `add_image`. Halves come only from `float_to_half_image` (`:213-216`),
    which clamps to +-65504 before converting (`util/half.h:284-287`), and Cycles' `max` returns its second argument when the
    first is NaN (`util/math_base.h:173-176`, `:371-374`), so inf and NaN both come out finite. Confirm with a script that
    prints `float_to_half_image` of NaN, +-inf, 65520 and FLT_MAX, their bits, and `half_is_finite` (quote it). If it
    confirms, do not write a test for the dead branch. Pin what a converted (half) image does with those floats (the
    `converted` construction at `:494-499`, with `is_unassociated_alpha` false so that no association multiplies them): each
    of NaN, +inf and -inf in every channel samples back as the finite value that the script prints. Mutation (in a copy of
    `util/half.h`): `float_to_half_image` without its clamp, which makes inf a half infinity that `image.cpp:80-89` then
    zeroes, so the pin fails. A deletion of the body of `image.cpp:80-89` itself is an equivalent mutant while the clamp is
    there; say so.
  - Texture defaults (`:705-775`; `image.cpp:160-162`). `KernelImageTexture` starts with `transform_3d = transform_zero()`
    and `average_color = zero_float4()` (`util/types_image.h:161`, `:163`); `add_image` sets `transform_identity()` and
    zero (`image.cpp:161-162`). The test checks `use_transform_3d` only (`:746`). Add checks of `transform_3d` against
    `transform_identity()` (`operator==`, `util/transform.h:369`) and of `average_color` against zero (`util/math_float4.h:193`).
    Mutations (in `image.cpp`): `:161` deleted; `:162` assigning `one_float4()`. Deleting `:162` is an equivalent mutant
    (the member initializer is the same value); say so.
Outcome:
- `CHECK` exits 0.
- `git diff -U0 HEAD -- src/test | grep -E '^-[^-]'` prints nothing: no existing line is removed or changed. `git status
  --porcelain` lists only allowedPaths.
- Your answer has one table per file: each mutation, where it was made (file:line, or the copy), and the first failing check;
  every mutation named above appears, or is listed as an equivalent mutant with the reason.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `src/test/test_cycles_svm_compiler.cpp`, `src/test/test_cycles_svm_textures.cpp`, `src/test/test_cycles_svm_closures.cpp`, `src/test/test_cycles_svm_images.cpp`

## M8-FIX-NOTICES: THIRD_PARTY_NOTICES.md names every vendored source's licence
Why (Opus's licence check, 2026-10-24): five files of `third_party/cycles/util/` state a licence other than Cycles' default,
Apache-2.0, in their own SPDX lines, and `THIRD_PARTY_NOTICES.md` names none of them. The gap is older than M6a (M3, T3.2
and T3.3 vendored them). Their lines:
- `math_fast.h:1-22`: BSD-3-Clause; "2004 NVIDIA Corporation", "2008-2014 Larry Gritz", "2009-2014 Sony Pictures Imageworks
  Inc., et al."; "Adapted from OpenImageIO".
- `md5.cpp:1-5` and `md5.h:1-5`: Zlib; "1999, 2002 Aladdin Enterprises. All rights reserved."; "By L. Peter Deutsch
  <ghost@aladdin.com>".
- `projection_inverse.h`: Apache-2.0 for the file (`:1-3`), and BSD-3-Clause for `projection_inverse_impl` (`:14-17`),
  "Adapted from code: Copyright (c) 2002, Industrial Light & Magic, a division of Lucas Digital Ltd. LLC. All rights reserved."
- `types_float8.h:1-6`: BSD-3-Clause; "2017 Intel Corporation", "2018-2022 Blender Foundation"; "Originally by Intel
  Corporation, modified by the Blender Foundation".
`LICENSES/` has no Zlib text, and none of its BSD texts has these holders.
Do:
- In `THIRD_PARTY_NOTICES.md`, add rows after line 15, in the layout of lines 12-15 (component, licence with the file of its
  full text, where used with the file lines that state the licence, upstream URL). Quote the files' own words and add no
  holder, year or licence that a file does not state. Suggested components: "OpenImageIO and NVIDIA code in Cycles' fast
  math" (`math_fast.h`; URL https://github.com/AcademySoftwareFoundation/OpenImageIO), "Intel code in Cycles' vfloat8"
  (`types_float8.h`), "Industrial Light & Magic code in Cycles' projection_inverse" (`projection_inverse.h`: say both
  licences), "MD5 by L. Peter Deutsch in Cycles" (`md5.cpp`, `md5.h`). For a file that names no upstream project, the URL
  is the Blender tag of line 6, not a guess.
- Add the licence texts to `LICENSES/`, one file per component as the existing files are: `BSD-3-Clause-oiio.txt`,
  `BSD-3-Clause-intel.txt`, `BSD-3-Clause-ilm.txt`, `Zlib-aladdin.txt`. Each is the copyright statements of the vendored file,
  one per line, a blank line, and then the licence text, unchanged and without its title line, of
  `MAIN/.cache/vendor/blender-v5.2.2/intern/cycles/doc/license/BSD-3-Clause-license.txt` or `.../Zlib-license.txt` (Cycles' own
  copies at the pinned tag; read them by these exact paths). A statement that the header quotes as a `Copyright ...` line
  (`math_fast.h:8-9`, `:13`, `:17`; `projection_inverse.h:16-17`) is copied as it stands; one that the header gives only as an
  `SPDX-FileCopyrightText` is written `Copyright (c) <that text>`, as `BSD-3-Clause-osl.txt` writes its line. Name this
  choice in your answer. Do not touch `LICENSES/BSD-3-Clause-osl.txt`: its copyright line is the owner's call.
  `pyproject.toml:11` already ships `LICENSES/*.txt`.
- A test, `tests/core/test_third_party_notices.py`, so the gap cannot reopen: for every file under `third_party/cycles` whose
  text has `SPDX-License-Identifier: X` with X other than `Apache-2.0` (a file can have several; read all of them), some
  line of `THIRD_PARTY_NOTICES.md` contains both the file's name and X; and every `LICENSES/<name>.txt` that the notices name
  exists. The test holds no list of files. Mutations to show (save the file first and put it back): the `math_fast.h`
  mention deleted from its row; `Zlib` deleted from the row of `md5.h`; `LICENSES/Zlib-aladdin.txt` renamed.
Outcome:
- `CHECK` exits 0.
- This prints nothing (before the change it printed the five files):
  ```
  MAIN/.venv/bin/python -P -s - <<'EOF'
  import re
  from pathlib import Path

  lines = Path("THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8").splitlines()
  for path in sorted(Path("third_party/cycles").rglob("*")):
      if not path.is_file():
          continue
      text = path.read_text(encoding="utf-8", errors="replace")
      for ident in sorted(set(re.findall(r"SPDX-License-Identifier:\s*([A-Za-z0-9.+-]+)", text)) - {"Apache-2.0"}):
          if not any(path.name in line and ident in line for line in lines):
              print(path.as_posix(), ident)
  EOF
  ```
- `grep -o 'LICENSES/[A-Za-z0-9._-]*\.txt' THIRD_PARTY_NOTICES.md | sort -u | while read -r f; do test -f "$f" || echo "missing $f"; done`
  prints nothing.
- `git diff --quiet HEAD -- LICENSES/BSD-3-Clause-osl.txt` exits 0, and `git status --porcelain` lists only allowedPaths.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `THIRD_PARTY_NOTICES.md`, `LICENSES/BSD-3-Clause-oiio.txt`, `LICENSES/BSD-3-Clause-intel.txt`, `LICENSES/BSD-3-Clause-ilm.txt`, `LICENSES/Zlib-aladdin.txt`, `tests/core/test_third_party_notices.py`

## M6a-FIX-TQ4a: assertions run in the doctests, and an opcode the SVM cannot run is an error (TQ.4 F1, F2, F14)
Why (audit TQ.4, `docs/audits/TQ.4.md`, 2026-10-25; line numbers are at 846f166, and the items before this one shift lines in
`tests/core/test_gen_svm_switch.py` and in `src/test`, so find those by name):
- F1. Every build is Release, so NDEBUG removes each `assert` and `kernel_assert` (`third_party/cycles/kernel/device/cpu/compat.h:20`)
  from `painterly_tests` too. The bounds check of `kernel_array::fetch` (`src/cycles/shim/kernel/device/cpu/globals.h:34`) never
  runs, and the widths that `PainterlyShaderManager::bind_kernel_globals` sets (`src/painterly/scene/svm/shader_manager.h:146-150`)
  are dead data: `width = 0` at `:146` or `:148` passes every doctest.
- F2, F14. Vendored `compile()` code emits eight node types that the generated `svm_eval_nodes()` has no case for: NODE_LIGHT_PATH
  (Geometry with Backfacing linked), NODE_VECTOR_TRANSFORM, NODE_SET_BUMP, NODE_CLOSURE_SET_NORMAL, NODE_ENTER_BUMP_EVAL,
  NODE_LEAVE_BUMP_EVAL, NODE_SET_DISPLACEMENT and NODE_AOV_START. Such a word reaches the interpreter's `default:`, whose assert is
  gone (`third_party/cycles/fragments/kernel/svm/svm_h/span/svm_eval_nodes_tail.inc:1-3`), so evaluation returns without a
  message, no closure is allocated, and `painterly_svm_collect` falls back to a weight-0 diffuse lobe
  (`src/painterly/kernel/svm/collect.h:205-210`): a black material with every doctest green. A shader that runs out of SVM stack is
  as silent: `compile_type` clears its program (`third_party/cycles/fragments/scene/svm_cpp/member/SVMCompiler.compile_type.inc:126-130`)
  and `stack_find_offset` only prints `LOG_ERROR` (`SVMCompiler.stack_find_offset-const_int.inc:26-30`, same directory).
  `compile_failed` is a protected member that `compile_type` has reset when `compile()` returns, and `SVMCompiler::Summary` has no
  failure field (`third_party/cycles/scene/svm.h:51-77`), so the manager can see the failure only through that `LOG_ERROR`.

Measured while drafting, in a scratch copy of 846f166 (GCC 15.2, the prebuilt Embree; nothing is committed): with `-UNDEBUG` on the
test sources alone, all 146 test cases (90,633 assertions) of `painterly_tests` pass, so the first change should not fail. Then
`svm_nodes.width = 0` at `:146` aborts the run in `kernel_assert`, but `shaders.width = 0` at `:148` and `width + 1` at either line
still pass: no doctest fetches `kg->shaders` (so no change of `:148` fails), and no fetch is out of range. The binder test below covers
them. Graphs for the four node types reproduce the silent opcode, and a graph whose values are live at once reproduces the silent
overflow (a chain of 254 compiles, 255 does not; the doctest uses lengths far from that edge).

Do:
- F1, asserts. In `src/test/CMakeLists.txt`, right after `painterly_target_warnings(painterly_tests)` (`:51`), add
  `target_compile_options(painterly_tests PRIVATE ...)` with `/UNDEBUG` under `if(MSVC)` (that also covers clang-cl) and
  `-UNDEBUG` otherwise; CMake puts a target's options after the `-DNDEBUG` of the Release flags, so the `U` wins. Comment why
  (the build type is Release, `Makefile:21`) and what it reaches: the sources of `painterly_tests` and the headers they include
  (`kernel_array::fetch`, the interpreter's `default:`, `shader_manager.h`'s `assert`), not the sources of the `cycles_*` libraries,
  whose asserts (`LookupTables::~LookupTables`, `string_printf`) stay compiled out.
  - With NDEBUG undefined, the pragma at `compat.h:10-13` no longer silences GCC's `-Wmaybe-uninitialized` in the vendored kernel
    headers (about 15 warnings from `kernel/closure/bsdf_microfacet.h`, no error). For GCC only (`CMAKE_CXX_COMPILER_ID STREQUAL "GNU"`)
    add `-Wno-maybe-uninitialized` to `painterly_tests`, with a comment that cites `compat.h:10-13`. Do not edit the vendored header.
  - If an assert fires in any test with the option on, do not remove or silence it, and do not change the test to avoid it: call
    `report_blocked` with the test case's name and the assert's text.
  - `src/cycles/shim/scene/shader.cpp:140`: `assert(sizeof(table_thin_film_cmf) == 6 * THIN_FILM_TABLE_SIZE * sizeof(float))` becomes a
    `static_assert` (the table is a `float[512][6]`, `third_party/cycles/scene/shader.tables:1287`).
- F2, F14, the table. `tools/gen_svm_switch.py` writes `#include <array>` after `#pragma once` (one blank line each side) and, after the
  tail fragment, one blank line, this block, one blank line, and `CCL_NAMESPACE_END`. The `table[...] = true;` lines are the `cases`
  in the order of the switch (upstream order, as `generate` already sorts the blocks):
  ```
  /* The node types that svm_eval_nodes() has a case for: the `cases` of
   * src/cycles/svm_nodes.toml. Generated, not upstream text. */
  inline constexpr std::array<bool, NODE_NUM> painterly_svm_has_case = [] {
    std::array<bool, NODE_NUM> table{};
    table[NODE_END] = true;
    return table;
  }();
  ```
  (the `NODE_END` line stands for one line per case). Use exactly this text, so that the golden of `tests/core/test_gen_svm_switch.py` can be
  written by hand from it. Array designators (`[NODE_END] = true`) are not C++20, and MSVC rejects them. The text must not contain
  `SVM_CASE(`: `test_committed_inputs` counts that string.
- F2, F14, the manifest. `src/cycles/svm_nodes.toml` gains `unsupported`, an array of inline tables `{ node = "NODE_X", reason = "..." }`,
  one per entry the pytest below finds, with a comment that says what the list is. The reasons are factual (who emits the type):
  - NODE_LIGHT_PATH: GeometryNode::compile, for the Backfacing output
  - NODE_VECTOR_TRANSFORM: VectorTransformNode::compile
  - NODE_SET_BUMP: BumpNode::compile
  - NODE_CLOSURE_SET_NORMAL: SetNormalNode::compile
  - NODE_ENTER_BUMP_EVAL: SVMCompiler::compile_type, for the bump program of a shader whose displacement method is "both"
  - NODE_LEAVE_BUMP_EVAL: SVMCompiler::compile_type, for the same program
  - NODE_SET_DISPLACEMENT: OutputNode::compile, for the displacement program, when Output.Displacement is linked
  - NODE_AOV_START: SVMCompiler::compile_type, when the graph has AOV Output nodes; no such node type is registered

  `gen_svm_switch.py` accepts `unsupported` as an optional third key (`includes` and `cases` stay required, so the fixtures of
  `test_gen_svm_switch.py` stay valid) and exits 1 with its usual message for: a value that is not an array of tables; a table without
  exactly the keys `node` and `reason`; a `node` that does not match `NODE_[A-Z0-9_]+`; an empty or non-string `reason`; a node listed
  twice; a node that is also in `cases`. It emits nothing for the key: the header text does not depend on it. Update the module docstring and the comment at
  `tools/gen_svm_switch.py:35` ("The manifest's exactly two keys").
- F2, F14, the refusal. In `src/painterly/scene/svm/shader_manager.h`:
  - Include `<stdexcept>`, `<string>` and `"svm_eval_nodes.h"` (generated; `painterly_svm_has_case` is in it). Every target that includes
    the manager now links `cycles_svm` (`painterly_tests` does, `src/test/CMakeLists.txt:81`), and a test source that includes it must include
    `cycles_svm_test_support.h` first, as every one does now: that header redefines `kernel_data_fetch` before `svm_eval_nodes.h`.
  - Add `painterly_svm_node_name(uint type)`: the name of a node type, from a table built out of `kernel/svm/node_types_template.h` with
    `#define SHADER_NODE_TYPE(name) #name,` and `#define SHADER_NODE_TYPE_DERIVATIVE(name) #name, #name "_DERIVATIVE",` (the two macros of the enum,
    `third_party/cycles/kernel/svm/types.h:51-55`, so the order is the enum's; the template `#undef`s them itself). `static_assert` that the
    table has `NODE_NUM` entries; return "?" for a type outside it.
  - `device_update_specific` (`:156-227`): right after `device_free(device, dscene, scene)` (`:166`) set `scene->dscene.data.svm_usage = {}`. The
    compiler marks every node type it emits in that member and nothing clears it
    (`third_party/cycles/fragments/scene/svm_cpp/member/SVMCompiler.SVMCompiler.inc:13`, `third_party/cycles/scene/svm.h:105`), so a rerun would see
    the types of shaders that are gone. It is `scene->dscene`, whatever `dscene` the caller passes: that is where the compiler writes.
  - `device_update_shader` (`:230-248`): read `painterly_log_error_count()` before `compiler.compile(...)` (`:243`). After it, first, if the
    count changed, throw `std::runtime_error` with `shader "<name>": the SVM compiler ran out of stack space`; second, read `svm_usage` as the
    `NODE_NUM` ints it is (as `src/test/test_cycles_svm_compiler.cpp:287-300` does) and, for the lowest `type` with `usage[type]` and no
    `painterly_svm_has_case[type]`, throw `std::runtime_error` with `shader "<name>" uses <NODE_X>, which svm_eval_nodes() has no case for`.
    `<name>` is `shader->name.string()`. The stack check comes first, because an out-of-stack compile leaves stale marks. The throw leaves
    `dscene` as `device_free` left it (empty `svm_nodes` and `shaders`). Leave the `assert` at `:238` alone. Say in the class comment that
    the update throws and why.
- F2, F14, the count. `src/cycles/shim/util/log.h`: `LOG_ERROR` (`:22`) becomes
  `(painterly_count_log_error(), std::cerr << "Error: ")`, with `painterly_log_error_count()` (an `inline int &` over a
  function-local `static thread_local int`) and `painterly_count_log_error()` defined inside `CCL_NAMESPACE_BEGIN`, before the log levels.
  Comment why (the failure is otherwise invisible, see Why) and that the count is per thread, so an error on another thread cannot refuse
  this thread's shader. Leave the three spans that `tests/core/test_shim_upstream_copies.py` pins (the `LogLevel` enum, `LOG_IS_ON`, the
  `float3` `operator<<`) as they are.
- Tests, C++. New `src/test/test_cycles_svm_unsupported.cpp`, registered with `target_sources(painterly_tests PRIVATE ...)` in
  `src/test/CMakeLists.txt`. It opens with the two-line SPDX header that `tests/core/test_cpp_file_headers.py` requires and defines the helpers
  it needs in an unnamed namespace (the other files do; M6a-FIX-TQ4c hoists them). Name every case `cycles svm unsupported: ...` or
  `cycles svm binder: ...`: the verify lines of M6a-T6.1 to M6a-T6.8 count the cases that match `cycles kernel*`, `cycles svm stack nodes:*`,
  `cycles shader graph*`, `cycles svm compiler:*`, `cycles svm textures:*`, `cycles texture nodes:*`, `cycles svm closures:*` and `cycles svm images:*`,
  and none of those may match a new case. A scene is `Scene` with a `PainterlyShaderManager` and `painterly_cycles_shader_node_types()`
  called first; each update is `device_update_pre` then `device_update_post` (public), with a `Shader` that has a name, a graph and `reference()`.
  - A node type without a case. Four graphs, each in its own scene; the update throws `std::runtime_error`, whose message contains the shader's
    name and the node type's name, and `scene->dscene.svm_nodes.size() == 0` afterwards. The wiring (checked while drafting; `connect` inserts
    the conversions):
    - shader "backfacing", NODE_LIGHT_PATH: `geometry`.Backfacing -> `emission`.Strength; `emission`.Emission -> Output.Surface.
    - shader "vector_transform", NODE_VECTOR_TRANSFORM: `geometry`.Position -> `vector_transform`.Vector; `vector_transform`.Vector -> `emission`.Color; Emission -> Surface.
    - shader "set_normal", NODE_CLOSURE_SET_NORMAL: `geometry`.Normal -> `set_normal`.Direction; `set_normal`.Normal -> `diffuse_bsdf`.Normal; `diffuse_bsdf`.BSDF -> Surface.
    - shader "bump", NODE_SET_BUMP: `texture_coordinate`.Generated -> `vector_math`.Vector1 and `texture_coordinate`.Normal -> `vector_math`.Vector2, with the parameter `math_type` of the
      `vector_math` node set to "dot_product"; `vector_math`.Value -> `bump`.Height; `bump`.Normal -> `diffuse_bsdf`.Normal; BSDF -> Surface.
    Both dot operands are linked on purpose: with one unlinked operand the Height folds to a constant and the Bump node is never compiled.
  - A stack that overflows. `SVM_STACK_SIZE` is 255 (`third_party/cycles/kernel/svm/types.h:41`). Build `live_values(n)`: `geometry`.Position and
    .Normal -> `vector_math` "dot_product" (not constant); a chain of `n` `math` "add" nodes, each with Value1 from the previous value and
    Value2 = 1; then a second chain that sums the chain's values in reverse order (acc = last; for i = n - 2 down to 0, acc = add(acc, value i)); acc ->
    `emission`.Strength. All `n` values stay live until the second chain reaches them. `live_values(2 * SVM_STACK_SIZE)` throws, and the message
    contains the shader's name and "stack"; `live_values(SVM_STACK_SIZE / 2)` updates without a throw and leaves `svm_nodes` non-empty. Both
    lengths come from the constant, and the case does not assert where the edge lies: that depends on Cycles' scheduler (vendored).
  - Stale marks. A scene with a supported graph (`live_values(4)`), after `svm_usage[NODE_LIGHT_PATH] = 1` is written through the `int` view, updates without a throw.
  - The table. `painterly_svm_has_case` is true at NODE_END, NODE_MATH and NODE_TEX_IMAGE_BOX_DERIVATIVE and false at NODE_LIGHT_PATH, NODE_SET_BUMP and
    NODE_PAD1; `painterly_svm_node_name` gives "NODE_LIGHT_PATH" and "NODE_TEX_COORD_DERIVATIVE".
  - The binder, `cycles svm binder: ...`. Two supported shaders, one update; then `bind_kernel_globals`: `svm_nodes`, `shaders` and `lookup_table` each
    have `data` equal to the device scene's array and `width` equal to its `size()`. `REQUIRE` each width before any fetch, so that a wrong width fails
    the case and does not abort the binary; then `globals.shaders.fetch(1).flags` equals `scene->dscene.shaders[1].flags`.
- Tests, Python.
  - New `tests/core/test_svm_nodes_manifest.py`. Scan every `*.inc` under `third_party/cycles/fragments/scene/` and `third_party/cycles/scene/svm.h` for the
    regex `\badd_node\(\s*(?:[A-Za-z_][A-Za-z0-9_]*\s*,\s*)?(NODE_[A-Z0-9_]+)` (the opcode is the first or second argument: `add_node(NODE_AOV_START)`,
    `compiler.add_node(this, NODE_X, ...)`, `add_node(nullptr, NODE_X, ...)`; the definition `add_node(ShaderNodeType type)` has none). That covers the
    `*.compile-SVMCompiler*` fragments and `SVMCompiler.compile_type` named in the audit, and also `add_value_node`, `generate_multi_closure`, `compile` and
    `add_bsdf_node`. Tests: (a) every emitted type is in `cases` or in `unsupported`; (b) no `unsupported` node is also in `cases`, and each is emitted by
    a scanned file; (c) the `svm_case` fragments of VENDORED.toml (`kernel/svm/svm_h/svm_case/NODE_X`) are exactly `cases`. Your answer quotes what the scan
    finds (drafting found 231 files, 38 distinct types, 30 in `cases`, the 8 above). Mutations: an `unsupported` entry deleted (a); `NODE_MATH` added to
    `unsupported` (b); a case deleted from `cases` (c).
  - `tests/core/test_gen_svm_switch.py`: write the new `EXPECTED` by hand from the block above and set the sha256 literal of `test_golden` to the
    sha256 of that hand-written text (`hashlib`); then show that the generator reproduces it. Add a test that the committed inputs generate exactly one
    `table[NODE_X] = true;` line per case; and the `unsupported` cases above (accepted, output unchanged by it, each bad shape exits 1). Mutations: the
    generator emits only the first case's line (golden and table test fail); each validation of `unsupported` deleted (its case fails).
- Change no existing assertion, except these, which the new output and key set force:
  - `tests/core/test_gen_svm_switch.py`: `EXPECTED` and the sha256 literal in `test_golden` (the header gains the include and the table).
  - `tests/core/test_cycles_svm.py:140`: `set(manifest) == {"includes", "cases"}` gains `"unsupported"`.
- Mutations to show (first failing check each). The ones in `shader_manager.h`, `log.h` and `shader.cpp` are made in files you also changed, so save your
  finished files under `.cache/` first and put them back afterwards (`git checkout` would discard your work).
  - Asserts are live: `svm_nodes.width = 0` (`:146`) aborts `painterly_tests --test-case='cycles svm closures:*'` with the option on (`kernel_assert` on
    `index >= 0 && index < width`), and passes it with the option removed.
  - `shader_manager.h`: the has-case check deleted; the `svm_usage` reset deleted; the stack check deleted; `svm_nodes.width` and `shaders.width` each set to
    0 and to `size() + 1`.
  - `log.h`: `LOG_ERROR` without the count.
  - `shader.cpp:140`: `6` changed to `7` (the build fails).
- TQ.5 F51, the third false comment of TQ.3 F20 (`docs/audits/TQ.3.md:55`), which M3-FIX-TQ3c left because its
  allowedPaths excluded the file. In `src/test/CMakeLists.txt`, the comment block above the `-mfma` canary says "MSVC
  needs no flag: /fp:precise already forbids contraction, and there is no per-source /arch switch to pair with it." It
  was at `:59` at f5d101e; the option this item adds after `painterly_target_warnings(painterly_tests)` moves it, so
  find it by its text. The second clause is false: `src/cycles/CMakeLists.txt:67-72` sets `/arch:AVX2` on
  `transform_avx2.cpp` alone for MSVC. Rewrite that clause so that it is true and says no more than you can cite: a
  per-source `/arch:AVX2` exists (`src/cycles/CMakeLists.txt:67-72`) and `test_math_double3.cpp` takes none. Change the
  comment only; add no flag.
Outcome:
- `CHECK` exits 0, with the option on for the whole of `painterly_tests`. Your answer says how many test cases and assertions `painterly_tests` ran before
  and after (drafting: 146 cases and 90,633 assertions before).
- `build/q/src/test/painterly_tests --test-case='cycles svm unsupported:*,cycles svm binder:*'` passes, and the doctest filters of the verify lines of M6a-T6.1 to
  M6a-T6.8 still print their counts.
- `git diff -U0 HEAD -- src/test tests | grep -E '^-[^-]'` lists only lines of `EXPECTED`, the sha256 literal, `tests/core/test_cycles_svm.py:140` and the comment line of `src/test/CMakeLists.txt` that the last Do bullet rewrites;
  `git status --porcelain` lists only allowedPaths.
- Host only, after landing (Opus): the Windows job builds `painterly_tests` with `/UNDEBUG` and compiles the table with MSVC.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `src/test/CMakeLists.txt`, `src/test/test_cycles_svm_unsupported.cpp`, `src/painterly/scene/svm/shader_manager.h`, `src/cycles/shim/util/log.h`, `src/cycles/shim/scene/shader.cpp`, `tools/gen_svm_switch.py`, `src/cycles/svm_nodes.toml`, `tests/core/test_svm_nodes_manifest.py`, `tests/core/test_gen_svm_switch.py`, `tests/core/test_cycles_svm.py`
Depends on: M6a-FIX-SVMT, M6a-FIX-VS1.

## M6a-FIX-TQ4b: every wheel build compiles the vendored SVM, and the build regenerates what changed (TQ.4 F6, F13, F15, F16, F18, F26)
Why (audit TQ.4, `docs/audits/TQ.4.md`, 2026-10-25; line numbers are at 846f166, and M6a-FIX-TQ4a has since edited `tools/gen_svm_switch.py`,
`src/cycles/shim/scene/shader.cpp`, `src/test/CMakeLists.txt` and `tests/core/test_gen_svm_switch.py`, so find code in those by name):
- F13. T6.3 and T6.5 added OBJECT header checks so that the wheel builds compile the SVM headers with MSVC and Clang on macOS (`src/cycles/CMakeLists.txt:137,201`).
  T6.6 and T6.8 added 12 evaluator headers (`src/cycles/svm_nodes.toml:31-45`) and their dependencies, and only `painterly_tests` compiles
  them: GCC and MSVC in `.github/workflows/ci.yml:14-86`. The wheel builds run with tests off (`pyproject.toml:17-19`), so Clang and arm64 (NEON through sse2neon,
  `third_party/cycles/kernel/svm/noise.h:45-49`) never compile them, nor the generated switch.
- F15. The five generated units depend on the generator, the manifests and VENDORED.toml but not on the 301 `.inc` files
  (`src/cycles/CMakeLists.txt:112-113,122-124,163-165,191-193,214-216,231-233`), so an edit of an `.inc` without VENDORED.toml re-runs nothing and the sha256 check never runs. And both generators
  rewrite their output on every run (`tools/gen_svm_switch.py:180-186`, `tools/gen_fragment_units.py:219-224`), so touching VENDORED.toml, which every card does, recompiles all
  five unit objects with identical bytes.
- F16, F6(a). The five units are kept by hand in five places: `[unit.*]` in `src/cycles/fragment_units.toml`, one `foreach` and three pasted rules in `src/cycles/CMakeLists.txt`
  (`:155-169,184-196,207-219,224-236`), the `.cpp` paths of the fragments, and the freshness tests, which cover 4 of 5 units (`shader_nodes` has none).
- F6(b), (d), (e). About 1,000 lines of our own C++ in `src/cycles/` build without warning flags (`cmake/painterly_warnings.cmake:5-9`); `if(NOT MSVC)` at `src/cycles/CMakeLists.txt:146`
  also skips clang-cl, for which Blender sets the flag (`platform_win32.cmake:207`); `src/test/CMakeLists.txt:81,85,92,99` link `cycles_svm` and `cycles_scene` three times each.
- F18. The wheels PR path filter lacks the generators (`.github/workflows/wheels.yml:12-19`) that the wheel builds run, and `src/cycles/CMakeLists.txt:135-136` says they "never run the generator".
- F26. `check --upstream` runs only by hand; CI runs the offline check, whose hashes the same tool wrote.

Measured while drafting, in a scratch copy of 846f166 with the changes below (nothing is committed): `touch third_party/cycles/VENDORED.toml` re-runs six generators and recompiles the five unit objects at 846f166,
and recompiles nothing with the changes; a changed byte in an `.inc` fails the generator's sha256 check with them; `svm_eval_check.cpp` compiles with GCC 15.2 and with clang++ 21.1.8 (x86-64), with the project's flags, without a warning; with `-Wall -Wextra -Wshadow`
our ten sources give one warning, at `src/cycles/shim/scene/shader.cpp:202` (`-Wsign-compare`: `size_t` against the unnamed enum of `third_party/cycles/scene/tables.h:17`).

Do:
- F13, the build check. New `src/cycles/svm_eval_check.cpp` (the SPDX header of `svm_headers_check.cpp`; say in its comment what it is for, as that file does) that includes
  `"svm_eval_nodes.h"` and explicitly instantiates `svm_eval_nodes<KERNEL_FEATURE_NODE_MASK_SURFACE & ~KERNEL_FEATURE_NODE_RAYTRACE, SHADER_TYPE_SURFACE, std::nullptr_t>`
  with the parameter list of its definition (the instantiation of `painterly_svm_test_run`, `src/test/cycles_svm_test_support.h:335-336,350-351`; every case compiles under that mask). In `src/cycles/CMakeLists.txt`:
  `add_library(cycles_svm_eval_check OBJECT svm_eval_check.cpp)` and `target_link_libraries(cycles_svm_eval_check PRIVATE cycles_svm)`, in ALL like its two siblings. It gets no warning flags (the generated header has
  unused parameters in this instantiation). Correct the comments that this makes stale: `src/cycles/svm_headers_check.cpp:6-9` and `src/cycles/svm_closure_headers_check.cpp:7-9` say the generated switch is compiled
  only in builds with tests. Change only comments there and keep the `add_library(cycles_svm_closure_headers_check OBJECT svm_closure_headers_check.cpp)` line as it is: existing tests read the `#include` lists of both files and that line
  (`tests/core/test_cycles_svm.py:145-149`, `tests/core/test_cycles_svm_compiler.py:191-201`).
- F16, F6(a), the units. In `src/cycles/CMakeLists.txt`, one `function(painterly_fragment_unit unit)` holds the `add_custom_command` (the command, the `DEPENDS` and the `COMMENT` of today's rules) and appends the unit's
  `.cpp` to `PAINTERLY_FRAGMENT_UNIT_SOURCES` (`PARENT_SCOPE`). Call it once per line, the name alone in the parentheses: `painterly_fragment_unit(shader_nodes)`, `svm`, `time`, `transform`, `tables` (a test parses these lines). Keep each
  unit's rationale comment (T6.5 `time_dt`, T6.6 `transform_transposed_inverse`, T6.7 `LookupTables`) beside its call. `cycles_scene` takes `${PAINTERLY_FRAGMENT_UNIT_SOURCES}` (all five) and the three later `target_sources`
  of generated units go.
- F15, the dependencies. After `find_package(Python ...)` (`:114`): `file(GLOB_RECURSE PAINTERLY_FRAGMENT_INC_FILES CONFIGURE_DEPENDS ${PAINTERLY_CYCLES_VENDOR}/fragments/*.inc)`; the switch's rule and the function's rule both list
  `${PAINTERLY_FRAGMENT_INC_FILES}` in `DEPENDS`. Correct the comment at `:110-113` ("Every fragment change rewrites its sha256 in VENDORED.toml, so these DEPENDS cover the fragments too" is false for an edit or a
  revert) and the one at `:134-136` (the generator runs in the wheel builds since T6.4).
  - `tools/gen_svm_switch.py` (`_write`) and `tools/gen_fragment_units.py` (`main`) write the output only when the file is absent or its bytes differ. CMake sets `restat` on every custom command with Ninja, so an unchanged output stops
    the recompile; say so in a comment.
- F6(b), the warnings. `cmake/painterly_warnings.cmake`: one function that gives the flag list (`/W4 /wd4702` for MSVC, `-Wall -Wextra -Wshadow` otherwise), read by `painterly_target_warnings` and by a new
  `painterly_source_warnings(<source>...)` that appends it to the `COMPILE_OPTIONS` property of those sources (as `src/cycles/CMakeLists.txt:71-72` does for `transform_avx2.cpp`). Call it in `src/cycles/CMakeLists.txt` for the ten sources:
  `shim/util/{path,string,system,thread}.cpp`, `shim/scene/{attribute,shader,image}.cpp`, `shim_markers.cpp`, `svm_headers_check.cpp`, `svm_closure_headers_check.cpp`. Not for vendored sources, the generated units, or `svm_eval_check.cpp`. Update the
  comment of the file (it says the `cycles_*` targets never get the flags). Fix the one warning at `shader.cpp:202` with `size_t(TABLE_OFFSET_INVALID)`, the conversion that `:53` and `:217` apply implicitly. A line that
  `tests/core/test_shim_upstream_copies.py` pins stays byte for byte; if a flag reports one, switch that flag off for that source with a comment that names the span, and say so. MSVC's `/W4` reports are for the Windows job (host only).
- F6(d), clang-cl. New `cmake/painterly_toolchain.cmake` with `painterly_no_strict_aliasing_option(<out_var>)`, a function of `CMAKE_CXX_COMPILER_ID`, `CMAKE_CXX_COMPILER_FRONTEND_VARIANT` and `MSVC` only: `/clang:-fno-strict-aliasing` when the ID is
  "Clang" and the front end is "MSVC" (clang-cl), empty for cl.exe, `-fno-strict-aliasing` otherwise. Blender v5.2.2 sets exactly `/clang:-fno-strict-aliasing` for clang-cl at `build_files/cmake/platform/platform_win32.cmake:207`, inside `if(MSVC_CLANG)` (read at
  `raw.githubusercontent.com/blender/blender/v5.2.2/...` while drafting; the sparse `.cache/vendor` checkout has no `build_files/`). `src/cycles/CMakeLists.txt:146-148` uses it for `cycles_kernel` instead of `if(NOT MSVC)`, after `include(painterly_toolchain)` (`CMAKE_MODULE_PATH` already holds `cmake/`, `CMakeLists.txt:17`). Keep its comment (`:140-145`).
- F6(e), duplicate links. `src/test/CMakeLists.txt`: link `cycles_svm` and `cycles_scene` once each (keep `:81` and `:85`, delete the two later `target_link_libraries(painterly_tests PRIVATE cycles_svm cycles_scene)` at `:92` and `:99`; their comments stay).
- F18, the wheels filter. `.github/workflows/wheels.yml:12-19`: add `"tools/gen_fragment_units.py"` and `"tools/gen_svm_switch.py"` to `paths`, and say why in the comment at `:10-11`.
  Add too what TQ.3 F28 found missing (`docs/audits/TQ.3.md`): `tools/fetch_blender.py`, experiment 005's directory and
  `tests/core/test_import.py`, which the wheel jobs run.
- F26, CI. In `.github/workflows/ci.yml`, job `linux`, after the step "Symbol audit": a step "Check the vendored sources against the pinned upstream" that runs `.venv/bin/python -I tools/vendor_sync.py check --upstream`. It names no tag and clones nothing itself: the
  tool reads the repository, tag and commit from `[upstream.cycles]` (`third_party/cycles/VENDORED.toml:6-10`) and `ensure_checkout` (`tools/vendor_sync.py:662-703`) makes the shallow, blobless, sparse clone of that tag into `.cache/vendor/blender-<tag>`
  (`_clone_tag`, `:633-652`), refusing a checkout whose HEAD is not the pin. Say so in a comment. It needs the network, so you cannot run it: write "host-only, not run".
- Tests. New `tests/core/test_cycles_build.py` (find `ninja` and `cmake` next to `sys.executable` first, then on `PATH`; `make` puts the venv's `bin` on `PATH`). Each fails under the mutation named after it. The mutations are made in files you
  also changed, so save your finished files under `.cache/` first and put them back afterwards (`git checkout` would discard your work); show each mutation and its first failing check in your answer.
  - `test_generated_unit_is_current[unit]`, one per `[unit.*]` of `fragment_units.toml`: `build_dir/src/cycles/fragment_units/<unit>.cpp` exists and `tools/gen_fragment_units.py --unit <unit> --check` accepts it. Delete the three tests it replaces,
    `test_generated_units_are_current` (`tests/core/test_cycles_svm_compiler.py:204-227`), `test_transform_unit_is_current` (`tests/core/test_cycles_svm_textures.py:193-213`) and `test_tables_unit_is_current`
    (`tests/core/test_cycles_svm_closures.py:150-170`), and the imports that become unused. Mutation: one byte appended to the built `shader_nodes.cpp` fails that parameter only (delete the file and rebuild to restore).
  - `test_units_are_one_set`: the names in the `painterly_fragment_unit(...)` lines, the `[unit.*]` names, and the units' `upstream_path`s against the `.cpp` `upstream_path`s of VENDORED.toml's fragments are the same set; no `upstream_path` is used by
    two units; no unit is declared twice. Mutations: a sixth call; a call deleted; two units with one `upstream_path`.
  - `test_generated_files_depend_on_every_fragment_file`: `ninja -C <build_dir> -t inputs --no-shell-escape <target>` for `src/cycles/generated/svm_eval_nodes.h` and each unit lists every `*.inc` under `third_party/cycles/fragments`. (Without
    `--no-shell-escape`, ninja quotes the path of `LookupTables.~LookupTables.inc`. Compare the part of each path below `third_party/cycles/fragments/`, because ninja prints the source directory as CMake spelled it.) Mutation: `${PAINTERLY_FRAGMENT_INC_FILES}` dropped from the function's `DEPENDS`.
  - `test_svm_eval_check_is_built`: `ninja -t inputs --no-shell-escape all` lists `src/cycles/svm_eval_check.cpp`. Mutation: `EXCLUDE_FROM_ALL` on the library.
  - `test_shim_sources_have_warning_flags`: for the ten sources above (a glob of `src/cycles/shim/**/*.cpp` plus the three top-level ones), the command in `ninja -t commands all` that compiles it (match the part of the path below `src/cycles/`) contains `-Wshadow` or `/W4`. Mutation: one source dropped from the call.
  - `test_aliasing_option_per_toolchain`: `cmake -DCMAKE_CXX_COMPILER_ID=... -DCMAKE_CXX_COMPILER_FRONTEND_VARIANT=... [-DMSVC=1] -P` of a script that includes the module and prints the function's result gives, for GNU/GNU, Clang/GNU, AppleClang/GNU, MSVC/MSVC and
    Clang/MSVC, `-fno-strict-aliasing` three times, the empty string, and `/clang:-fno-strict-aliasing`. Mutation: `if(MSVC)` first in the function.
  - `test_painterly_tests_links_each_library_once`: no library appears twice in the `target_link_libraries(painterly_tests ...)` calls of `src/test/CMakeLists.txt`. Mutation: the duplicate put back.
  - `test_wheels_filter_lists_the_generators`: every `tools/<name>.py` that a `COMMAND` of `src/cycles/CMakeLists.txt` runs is in `on.pull_request.paths` of `wheels.yml`. PyYAML reads the key `on` as `True` (YAML 1.1): look up `workflow.get("on", workflow.get(True))`.
    Mutation: one path removed.
  - `test_ci_checks_the_pinned_upstream`: the `linux` job of `ci.yml` has a step whose `run` is `.venv/bin/python -I tools/vendor_sync.py check --upstream`. Mutation: the step deleted.
  - In `tests/core/test_gen_svm_switch.py` and `tests/core/test_gen_fragment_units.py`, a test that a second run of the generator on unchanged inputs leaves the output's mtime alone (`os.utime` the output to an old time, run, compare `st_mtime_ns`)
    and that a changed output is rewritten. Mutation: the unconditional write back.
- Change no existing assertion, except the deletion of the three freshness tests above (the new parametrized test covers them and `shader_nodes`).
Outcome:
- `CHECK` exits 0.
- After a full build in `build/q`, `touch third_party/cycles/VENDORED.toml` and `touch third_party/cycles/fragments/kernel/svm/svm_h/span/svm_eval_nodes_tail.inc`, each followed by `cmake --build build/q`: your answer quotes both outputs, which show
  the six `Generating` steps and no `Building CXX` line.
- A full rebuild of `cycles_util` and `cycles_scene` prints no `warning:` line for the ten sources (GCC).
- `git status --porcelain` lists only allowedPaths.
- Host only, after landing (Opus): `python -I tools/vendor_sync.py check --upstream` exits 0; the Windows and macOS jobs compile `svm_eval_check.cpp`.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `src/cycles/CMakeLists.txt`, `src/cycles/svm_eval_check.cpp`, `src/cycles/svm_headers_check.cpp`, `src/cycles/svm_closure_headers_check.cpp`, `src/cycles/shim/scene/shader.cpp`, `cmake/painterly_warnings.cmake`, `cmake/painterly_toolchain.cmake`, `src/test/CMakeLists.txt`, `tools/gen_svm_switch.py`, `tools/gen_fragment_units.py`, `tests/core/test_cycles_build.py`, `tests/core/test_gen_svm_switch.py`, `tests/core/test_gen_fragment_units.py`, `tests/core/test_cycles_svm_compiler.py`, `tests/core/test_cycles_svm_textures.py`, `tests/core/test_cycles_svm_closures.py`, `.github/workflows/wheels.yml`, `.github/workflows/ci.yml`
Depends on: M6a-FIX-TQ4a.

## M6a-FIX-TQ4c: test helpers, logs, ustring and generator hygiene (TQ.4 F7-F10, F12, F17, F21-F24)
Why (audit TQ.4, `docs/audits/TQ.4.md`, 2026-10-25): Low findings in test code, the log and `ustring` shims, the docs and the two generators, one bullet each. Line numbers
are at 846f166; M6a-FIX-SVMT, -VS1, -X011, -TQ4a and -TQ4b have edited most of these files, so find code by name.

Do:
- F7, helpers. Each of these has one definition in `src/test` and the others call it: `create_node_by_name` (with the `REQUIRE`; the copy in `test_cycles_svm_compiler.cpp:58` lacks it, so a mistyped type name is a null
  dereference that kills the binary), `make_scene`, `shader_manager`, `add_shader` (`test_cycles_svm_compiler.cpp:43,51,101`, `test_cycles_svm_closures.cpp:47,55,78`, and the copies in `test_cycles_svm_unsupported.cpp`), `new_program`
  (`test_cycles_svm_stack_nodes.cpp:51`, `test_cycles_svm_textures.cpp:46`, `test_cycles_svm_images.cpp:63`), `run_and_check`/`run_program_and_check` (`test_cycles_svm_stack_nodes.cpp:41`, `test_cycles_svm_textures.cpp:33`, `test_cycles_svm_images.cpp:50`),
  `c` and `c3` (`test_cycles_svm_stack_nodes.cpp:17,21`, `test_cycles_svm_textures.cpp:60,65`), and the `create_node_by_name` of `test_cycles_shader_graph.cpp:29` and `test_cycles_texture_nodes.cpp:27`. They go to `src/test/cycles_scene_fixture.h` and
  `src/test/cycles_svm_test_support.h`, which exists for this. The constraint is that header's include-order rule (it redefines `kernel_data_fetch` before `svm_eval_nodes.h`, which `shader_manager.h` now includes): a header that needs
  `PainterlyShaderManager` includes it after the redefinition, and `cycles_scene_fixture.h`, which two sources include without the support header, does not include it. `eval_surface` (`test_cycles_svm_compiler.cpp:170-177`) calls
  `PainterlyShaderManager::bind_kernel_globals` instead of binding by hand, so the compiler tests cover the production binder. Mutation: `svm_nodes.width = 0` in `bind_kernel_globals` now fails `cycles svm compiler:*` (it did not).
  Where the copies differ, keep the stricter one and say what differed.
- F8, docs. `docs/architecture.md`: an `src/cycles/` layout paragraph that names `shader_node_registry.h`, `fragment_units.toml`, `svm_nodes.toml`, `shim_markers.cpp`, `svm_headers_check.cpp`, `svm_closure_headers_check.cpp`, `svm_eval_check.cpp`, the generators
  `tools/gen_svm_switch.py` and `tools/gen_fragment_units.py` and the build-tree files they write, the libraries `cycles_kernel`, `cycles_svm` and `cycles_scene`, the definition-set rule (T6.1, `docs/handoff/drafts/M6a/T6.1-vendor-kernel-types.md:80-85`) and
  `src/painterly/{kernel,scene}/svm/`; "declared" versus "searched" include order at `:37-38` (declared: shim, third_party, sse2neon, src; searched: shim, src, third_party, as `:39-42` and `src/cycles/CMakeLists.txt:22-23` say). Leave `:61-63`
  to the M6b brief (TQ.4 F3 is card B1's). Rewrite the header comment of `src/cycles/CMakeLists.txt` (`:1-3`, "the static library cycles_util") to list what the file builds now.
- F9, log shim. `src/cycles/shim/util/log.h`: `LOG_ERROR`, `LOG_WARNING` and `LOG_INFO` are gated by `LOG_IS_ON(LOG_LEVEL_ERROR)`, `LOG_LEVEL_WARNING` and `LOG_LEVEL_INFO`, in the dangling-else-safe form of `LOG_DEBUG` (upstream's go through `LOG_IF(level <= LOG_LEVEL)`,
  `.cache/vendor/blender-v5.2.2/intern/cycles/util/log.h:83-97`; its default level 6 hides `LOG_INFO`, `util/log.cpp:17`). The count that M6a-FIX-TQ4a added to `LOG_ERROR` stays outside the gate: it counts at every level (the shader manager's stack check depends on it).
  Rewrite the header comment (`:6-12`) so that it says how the five relate. `src/cycles/shim/scene/image.h:171-174` justifies the error with `scene/image_cache.cpp:237-244`, which logs nothing; cite upstream's `scene/image.cpp:870` ("Failed to load N image files"). Tests in
  `src/test/test_cycles_svm_images.cpp`, named `cycles shim log: ...`, with a capture of `std::cerr` (swap its `rdbuf`, restored at the end): the invalid-image case (`wrong_size`, as at `test_cycles_svm_images.cpp:572-586`)
  logs a line that contains "Image texture" and the reason `a float or converted image needs width * height floats and no bytes` (`src/cycles/shim/scene/image.cpp:138`); with `LOG_LEVEL` set to `LOG_LEVEL_FATAL` (restored at the end), `LOG_ERROR` and
  `LOG_WARNING` write nothing and `painterly_log_error_count()` still rises; `LOG_INFO` writes nothing at the default level and writes at `LOG_LEVEL_INFO`. Mutations: the `LOG_ERROR` in `add_image` deleted; the gate of `LOG_ERROR` removed;
  the count moved inside the gate.
- F10, ustring. `src/cycles/shim/util/param.h`: `hash()` (`:73-78`) is the hash of the characters, `std::hash<std::string_view>()(string())` (or that value computed once and stored with the interned copy, as OpenImageIO does), so it does not depend on an
  address and unordered containers of ustrings iterate in the same order in every run. `intern` (`:150-159`) allocates its table with `new` and never destroys it, so a `ustring` read in a static destructor stays valid. Correct the comments at `:8-12`, `:43` and `:73-78`.
  A test case `ustring hashes its characters` in `src/test/test_graph.cpp` after `:175`: `ustring("abc").hash()` equals `std::hash<std::string_view>()("abc")`, two ustrings built from different buffers with equal characters hash equal, and `std::hash<ustring>` agrees with `hash()`. Mutation: the pointer
  hash back. No test can see the destruction order without a sanitizer: say so in your answer.
- F12, the count. `src/test/test_cycles_svm_compiler.cpp:483-491`: `CHECK(inputs.size() == 4162)` states a number that came from running the code, and it moves with `hash_uint2` (CLAUDE.md rule 2). Replace it by a comparison with
  `std::size(special) * std::size(special)` plus a count of the finite hashed pairs taken in the loop that skips the others; the case keeps its assertion count. Show that `num_hashed = 100` passes the new check (it failed the old), and that a loop
  that pushes a pair twice fails it.
- F17, pinned manifests. `tests/core/test_cycles_svm_compiler.py` (`units["time"] == {...}`), `tests/core/test_cycles_svm_textures.py` (`units["transform"] == {...}`) and `tests/core/test_cycles_svm_closures.py` (`units["tables"] == {...}` and the neighbours of
  `bsdf_microfacet.h` by position) assert `upstream_path` and `node_registry` equal and the card's headers a subset of `includes`, as `src/cycles/fragment_units.toml:3-4` says a later card may add includes. These three assertions are the ones this item changes
  in those files. Mutations: a required header removed from `includes` fails; an unrelated header added passes.
- F21, provenance text. `tools/gen_svm_switch.py:42-51` and `tools/gen_fragment_units.py:24-34` take "Blender <tag>" from `[upstream.cycles].tag` of the VENDORED.toml they read. The SPDX line becomes a constant whose comment lists the upstream files it was checked
  against (`kernel/svm/svm.h`, `scene/shader_nodes.cpp`, `scene/svm.cpp`, `util/time.cpp`, `util/transform.cpp`, `scene/tables.cpp`): read the first three lines of each in `MAIN/.cache/vendor/blender-v5.2.2/intern/cycles/` and quote them in your answer (drafting found the same three lines in all six). Tests in both generators'
  test files: a manifest with `tag = "v9.9.9"` gives a header with "Blender v9.9.9" and not "v5.2.2". The existing goldens stay as they are (their tag is v5.2.2). Mutation: the literal back.
- F22, malformed input. `gen_svm_switch.py` (`_fragments`, `:104-116`) rejects two entries of one name. `gen_fragment_units.py` checks in `_fragments` (`:127-143`) that `upstream_lines` is two integers (not bools) and that `anchor` is a string where the registry needs
  it (`kind == "node_define"`), and turns a `UnicodeDecodeError` at `:184` into its `gen_fragment_units:` message; every failure exits 1 with that prefix and no traceback. Negative tests in `tests/core/test_gen_svm_switch.py` and `tests/core/test_gen_fragment_units.py` (a hand-edited
  VENDORED.toml in the fixture, with the sha256 kept consistent so that the check under test is the one reached). Mutation: each check deleted (the case then shows a traceback or exit 0).
- F23, hygiene. Delete `SHA256_HEX_LEN` (`tools/gen_svm_switch.py:41`). `tools/vendor_sync.py:1567`: name the unused loop variable `_` and drop `del table`. Drop the `noqa` from `tools/gen_fragment_units.py:38` and keep the sentence. Rename `SVN_NODES` to `SVM_NODES` in
  `tests/core/test_cycles_svm_compiler.py:17,162`. Leave `MANIFEST_HEADER` (`tools/vendor_sync.py:89-94`) as it is: changing it rewrites `third_party/cycles/VENDORED.toml`, a
  guarded path (Opus, 2026-10-25). One-line docstrings on
  `tests/core/test_cycles_svm_images.py:45,50,57` and `tests/core/test_shim_upstream_copies.py:111,121`.
- F24, portability. `tests/core/test_cycles_svm_compiler.py:182,186,188,193,200`: `read_text(encoding="utf-8")`. At the two hash-seed runs (`tests/core/test_gen_svm_switch.py:319-342`, `tests/core/test_gen_fragment_units.py:427-452`) a comment says why the generator runs
  without `-I`: `-I` implies `-E` and drops `PYTHONHASHSEED`, while CMake runs the same tools with `-I`.
- Mutations. Those in files you changed (`log.h`, `param.h`, the generators, the tests) are made after saving your finished files under `.cache/`, and undone by putting them back (`git checkout` would discard your work). Those in
  `src/cycles/shim/scene/image.cpp`, which is not in allowedPaths, are made in the file and undone with `git checkout -- <file>`. Your answer lists each mutation and its first failing check.
- Change no existing assertion, except the three of F17 and the one of F12 (their cases keep their assertion counts), and the `eval_surface` of F7. Run the doctest filters of the verify lines of M6a-T6.1 to M6a-T6.8: each prints its counts as before,
  and no new case matches one of them (name the F10 case `ustring ...` and the F9 cases `cycles shim log: ...`).
Outcome:
- `CHECK` exits 0.
- `git grep -n -E '^(static )?[A-Za-z_][A-Za-z_:<>&* ]*[ *&](create_node_by_name|make_scene|shader_manager|add_shader|new_program|run_and_check|run_program_and_check)\(' -- src/test` prints at most one definition of each name (it prints 16 lines at 846f166; `run_program_and_check` may become `run_and_check`).
- `for n in shader_node_registry.h fragment_units.toml svm_nodes.toml shim_markers.cpp svm_headers_check.cpp svm_closure_headers_check.cpp svm_eval_check.cpp gen_svm_switch.py gen_fragment_units.py cycles_kernel cycles_svm cycles_scene; do grep -q "$n" docs/architecture.md || echo "missing $n"; done` prints nothing.
- `git diff --quiet HEAD -- third_party experiments` exits 0; `python -I tools/vendor_sync.py check` exits 0; `git status --porcelain` lists only allowedPaths.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `src/test/cycles_scene_fixture.h`, `src/test/cycles_svm_test_support.h`, `src/test/test_cycles_shader_graph.cpp`, `src/test/test_cycles_texture_nodes.cpp`, `src/test/test_cycles_svm_stack_nodes.cpp`, `src/test/test_cycles_svm_textures.cpp`, `src/test/test_cycles_svm_closures.cpp`, `src/test/test_cycles_svm_compiler.cpp`, `src/test/test_cycles_svm_images.cpp`, `src/test/test_cycles_svm_unsupported.cpp`, `src/test/test_graph.cpp`, `src/cycles/shim/util/log.h`, `src/cycles/shim/util/param.h`, `src/cycles/shim/scene/image.h`, `docs/architecture.md`, `src/cycles/CMakeLists.txt`, `tools/gen_svm_switch.py`, `tools/gen_fragment_units.py`, `tools/vendor_sync.py`, `tests/core/test_gen_svm_switch.py`, `tests/core/test_gen_fragment_units.py`, `tests/core/test_cycles_svm_compiler.py`, `tests/core/test_cycles_svm_textures.py`, `tests/core/test_cycles_svm_closures.py`, `tests/core/test_cycles_svm_images.py`, `tests/core/test_shim_upstream_copies.py`
Depends on: M6a-FIX-TQ4b, M6a-FIX-SVMT, M6a-FIX-VS1.

## REVIEW-M7-M9: report-only review of the drafted M7-M9 cards
Why: cards T7.1-T9.3 (`docs/handoff/drafts/M7-M9/`) are drafted, but only T7.1 and T7.2 have been reviewed
(`docs/handoff/findings/M7-M9-reviews.json`).
Do: review every card on two lenses.
- **Executability.** Every file, target, socket and test the card uses must be created by it or by an earlier card.
  Every acceptance step must be runnable and deterministic, with no hand-picked tolerance.
- **Design.** The card must serve the goal (keep the painterly look and make it accessible to artists) and respect SPEC,
  the single-source knob rule, layout and naming, and the experiment protocol.
Write `docs/handoff/findings/M7-M9-review-2.json`:
- one object per (card, lens);
- each object has `findings: [{severity, issue, evidence, fix}]`, where evidence cites file:line or a command and its
  output.
Change no card.
Outcome: the JSON parses, and covers each of the 10 cards on both lenses. The command
`MAIN/.venv/bin/python -c "import json;d=json.load(open('docs/handoff/findings/M7-M9-review-2.json'));print(len(d))"`
prints 20.
allowedPaths: `docs/handoff/findings/M7-M9-review-2.json`.
Depends on: BOOT-0a, so that no task is verified against `CHECK` before the knobs exist.

## PANEL-M7-M9-a: check the review findings on T7.1 (report only)
Why: `docs/handoff/queue.md` §8 revises the drafts in `docs/handoff/drafts/M7-M9/` from their review findings, and no
one has checked those findings yet. A finding is a claim to test, not evidence. Opus reads this panel, rules wherever
the verdict is not `confirmed`, and then plans the revision. The panel runs in five parts, one after another; this
part covers T7.1.
Do:
- Check, each on its own, every finding under the keys `review <card> executability` and `review <card> design` for
  T7.1, in `docs/handoff/findings/M7-M9-reviews.json` (which has only T7.1 and T7.2) and
  `docs/handoff/findings/M7-M9-review-2.json`.
  - Open every file the finding cites, at HEAD, and read the cited lines. Never take its quotes or line numbers as read.
  - Re-derive the claim from the draft, any other draft it involves, `docs/spec.md`, `docs/plan.md`,
    `docs/architecture.md` and the committed code.
  - For Blender's behaviour, read Blender 5.2.2's bundled Python. This item lets you search these three directories of
    it, and no other: `MAIN/.cache/blender/blender-5.2.2-linux-x64/5.2/scripts/startup/`, `.../scripts/modules/` and
    `.../scripts/presets/`. A read-only probe may run
    `MAIN/.cache/blender/blender-5.2.2-linux-x64/blender -b --factory-startup --python-expr '<code>'`; quote the code
    and its output.
- Write `docs/handoff/findings/M7-M9-panel-T7.1.json`: a JSON list with one object per finding, ordered by source
  (`M7-M9-reviews.json` first), then key as in the file, then index. Fields:
  - `source` (the file name), `key`, and `index` (the finding's 0-based position in that key's list);
  - `verdict`: `confirmed` (the defect is real as stated, and its fix removes it), `partly` (real, but the issue or
    the fix is wrong in a way `note` states), `disputed` (not a defect) or `unknown` (the tree cannot decide it);
  - `evidence`: the file:line spans you read and every command you ran, with its output quoted;
  - `duplicate_of`: `{source, key, index}` of an earlier object in this list that states the same defect, else `null`;
  - `fix`: the edit to the draft as exact old and new text. Required for `confirmed`; for `partly`, the corrected
    edit where you can give one; otherwise `null`. Do not apply it;
  - `note`: one or two sentences. For `disputed` it says why; for `unknown` it names what is missing.
- Change no other file.
Outcome:
- This command prints `PANEL-OK` and the number of objects:
  `MAIN/.venv/bin/python -I -c "import json;d='docs/handoff/findings/';c={'T7.1'};w={(s,k,i) for s in ('M7-M9-reviews.json','M7-M9-review-2.json') for k,v in json.load(open(d+s)).items() if k.split()[1] in c for i in range(len(v))};p=json.load(open(d+'M7-M9-panel-T7.1.json'));g=[(o['source'],o['key'],o['index']) for o in p];assert len(g)==len(set(g)) and set(g)==w,sorted(set(g)^w);assert all(o['verdict'] in ('confirmed','partly','disputed','unknown') and o['evidence'] and o['note'] and (o['verdict']!='confirmed' or o['fix']) for o in p);print('PANEL-OK',len(p))"`
- `git status --porcelain` lists only `docs/handoff/findings/M7-M9-panel-T7.1.json`.
allowedPaths: `docs/handoff/findings/M7-M9-panel-T7.1.json`
Depends on: REVIEW-M7-M9.

## PANEL-M7-M9-b: check the review findings on T7.2 (report only)
Why: `docs/handoff/queue.md` §8 revises the drafts in `docs/handoff/drafts/M7-M9/` from their review findings, and no
one has checked those findings yet. A finding is a claim to test, not evidence. Opus reads this panel, rules wherever
the verdict is not `confirmed`, and then plans the revision. The panel runs in five parts, one after another; this
part covers T7.2.
Do:
- Check, each on its own, every finding under the keys `review <card> executability` and `review <card> design` for
  T7.2, in `docs/handoff/findings/M7-M9-reviews.json` (which has only T7.1 and T7.2) and
  `docs/handoff/findings/M7-M9-review-2.json`.
  - Open every file the finding cites, at HEAD, and read the cited lines. Never take its quotes or line numbers as read.
  - Re-derive the claim from the draft, any other draft it involves, `docs/spec.md`, `docs/plan.md`,
    `docs/architecture.md` and the committed code.
  - For Blender's behaviour, read Blender 5.2.2's bundled Python. This item lets you search these three directories of
    it, and no other: `MAIN/.cache/blender/blender-5.2.2-linux-x64/5.2/scripts/startup/`, `.../scripts/modules/` and
    `.../scripts/presets/`. A read-only probe may run
    `MAIN/.cache/blender/blender-5.2.2-linux-x64/blender -b --factory-startup --python-expr '<code>'`; quote the code
    and its output.
- Write `docs/handoff/findings/M7-M9-panel-T7.2.json`: a JSON list with one object per finding, ordered by source
  (`M7-M9-reviews.json` first), then key as in the file, then index. Fields:
  - `source` (the file name), `key`, and `index` (the finding's 0-based position in that key's list);
  - `verdict`: `confirmed` (the defect is real as stated, and its fix removes it), `partly` (real, but the issue or
    the fix is wrong in a way `note` states), `disputed` (not a defect) or `unknown` (the tree cannot decide it);
  - `evidence`: the file:line spans you read and every command you ran, with its output quoted;
  - `duplicate_of`: `{source, key, index}` of an earlier object in this list that states the same defect, else `null`;
  - `fix`: the edit to the draft as exact old and new text. Required for `confirmed`; for `partly`, the corrected
    edit where you can give one; otherwise `null`. Do not apply it;
  - `note`: one or two sentences. For `disputed` it says why; for `unknown` it names what is missing.
- Change no other file.
Outcome:
- This command prints `PANEL-OK` and the number of objects:
  `MAIN/.venv/bin/python -I -c "import json;d='docs/handoff/findings/';c={'T7.2'};w={(s,k,i) for s in ('M7-M9-reviews.json','M7-M9-review-2.json') for k,v in json.load(open(d+s)).items() if k.split()[1] in c for i in range(len(v))};p=json.load(open(d+'M7-M9-panel-T7.2.json'));g=[(o['source'],o['key'],o['index']) for o in p];assert len(g)==len(set(g)) and set(g)==w,sorted(set(g)^w);assert all(o['verdict'] in ('confirmed','partly','disputed','unknown') and o['evidence'] and o['note'] and (o['verdict']!='confirmed' or o['fix']) for o in p);print('PANEL-OK',len(p))"`
- `git status --porcelain` lists only `docs/handoff/findings/M7-M9-panel-T7.2.json`.
allowedPaths: `docs/handoff/findings/M7-M9-panel-T7.2.json`
Depends on: PANEL-M7-M9-a.

## PANEL-M7-M9-c: check the review findings on T7.3, T7.4 and T7.5 (report only)
Why: `docs/handoff/queue.md` §8 revises the drafts in `docs/handoff/drafts/M7-M9/` from their review findings, and no
one has checked those findings yet. A finding is a claim to test, not evidence. Opus reads this panel, rules wherever
the verdict is not `confirmed`, and then plans the revision. The panel runs in five parts, one after another; this
part covers T7.3, T7.4 and T7.5.
Do:
- Check, each on its own, every finding under the keys `review <card> executability` and `review <card> design` for
  T7.3, T7.4 and T7.5, in `docs/handoff/findings/M7-M9-reviews.json` (which has only T7.1 and T7.2) and
  `docs/handoff/findings/M7-M9-review-2.json`.
  - Open every file the finding cites, at HEAD, and read the cited lines. Never take its quotes or line numbers as read.
  - Re-derive the claim from the draft, any other draft it involves, `docs/spec.md`, `docs/plan.md`,
    `docs/architecture.md` and the committed code.
  - For Blender's behaviour, read Blender 5.2.2's bundled Python. This item lets you search these three directories of
    it, and no other: `MAIN/.cache/blender/blender-5.2.2-linux-x64/5.2/scripts/startup/`, `.../scripts/modules/` and
    `.../scripts/presets/`. A read-only probe may run
    `MAIN/.cache/blender/blender-5.2.2-linux-x64/blender -b --factory-startup --python-expr '<code>'`; quote the code
    and its output.
- Write `docs/handoff/findings/M7-M9-panel-T7.3-T7.5.json`: a JSON list with one object per finding, ordered by source
  (`M7-M9-reviews.json` first), then key as in the file, then index. Fields:
  - `source` (the file name), `key`, and `index` (the finding's 0-based position in that key's list);
  - `verdict`: `confirmed` (the defect is real as stated, and its fix removes it), `partly` (real, but the issue or
    the fix is wrong in a way `note` states), `disputed` (not a defect) or `unknown` (the tree cannot decide it);
  - `evidence`: the file:line spans you read and every command you ran, with its output quoted;
  - `duplicate_of`: `{source, key, index}` of an earlier object in this list that states the same defect, else `null`;
  - `fix`: the edit to the draft as exact old and new text. Required for `confirmed`; for `partly`, the corrected
    edit where you can give one; otherwise `null`. Do not apply it;
  - `note`: one or two sentences. For `disputed` it says why; for `unknown` it names what is missing.
- Change no other file.
Outcome:
- This command prints `PANEL-OK` and the number of objects:
  `MAIN/.venv/bin/python -I -c "import json;d='docs/handoff/findings/';c={'T7.3','T7.4','T7.5'};w={(s,k,i) for s in ('M7-M9-reviews.json','M7-M9-review-2.json') for k,v in json.load(open(d+s)).items() if k.split()[1] in c for i in range(len(v))};p=json.load(open(d+'M7-M9-panel-T7.3-T7.5.json'));g=[(o['source'],o['key'],o['index']) for o in p];assert len(g)==len(set(g)) and set(g)==w,sorted(set(g)^w);assert all(o['verdict'] in ('confirmed','partly','disputed','unknown') and o['evidence'] and o['note'] and (o['verdict']!='confirmed' or o['fix']) for o in p);print('PANEL-OK',len(p))"`
- `git status --porcelain` lists only `docs/handoff/findings/M7-M9-panel-T7.3-T7.5.json`.
allowedPaths: `docs/handoff/findings/M7-M9-panel-T7.3-T7.5.json`
Depends on: PANEL-M7-M9-b.

## PANEL-M7-M9-d: check the review findings on T8.1 and T8.2 (report only)
Why: `docs/handoff/queue.md` §8 revises the drafts in `docs/handoff/drafts/M7-M9/` from their review findings, and no
one has checked those findings yet. A finding is a claim to test, not evidence. Opus reads this panel, rules wherever
the verdict is not `confirmed`, and then plans the revision. The panel runs in five parts, one after another; this
part covers T8.1 and T8.2.
Do:
- Check, each on its own, every finding under the keys `review <card> executability` and `review <card> design` for
  T8.1 and T8.2, in `docs/handoff/findings/M7-M9-reviews.json` (which has only T7.1 and T7.2) and
  `docs/handoff/findings/M7-M9-review-2.json`.
  - Open every file the finding cites, at HEAD, and read the cited lines. Never take its quotes or line numbers as read.
  - Re-derive the claim from the draft, any other draft it involves, `docs/spec.md`, `docs/plan.md`,
    `docs/architecture.md` and the committed code.
  - For Blender's behaviour, read Blender 5.2.2's bundled Python. This item lets you search these three directories of
    it, and no other: `MAIN/.cache/blender/blender-5.2.2-linux-x64/5.2/scripts/startup/`, `.../scripts/modules/` and
    `.../scripts/presets/`. A read-only probe may run
    `MAIN/.cache/blender/blender-5.2.2-linux-x64/blender -b --factory-startup --python-expr '<code>'`; quote the code
    and its output.
- Write `docs/handoff/findings/M7-M9-panel-M8.json`: a JSON list with one object per finding, ordered by source
  (`M7-M9-reviews.json` first), then key as in the file, then index. Fields:
  - `source` (the file name), `key`, and `index` (the finding's 0-based position in that key's list);
  - `verdict`: `confirmed` (the defect is real as stated, and its fix removes it), `partly` (real, but the issue or
    the fix is wrong in a way `note` states), `disputed` (not a defect) or `unknown` (the tree cannot decide it);
  - `evidence`: the file:line spans you read and every command you ran, with its output quoted;
  - `duplicate_of`: `{source, key, index}` of an earlier object in this list that states the same defect, else `null`;
  - `fix`: the edit to the draft as exact old and new text. Required for `confirmed`; for `partly`, the corrected
    edit where you can give one; otherwise `null`. Do not apply it;
  - `note`: one or two sentences. For `disputed` it says why; for `unknown` it names what is missing.
- Change no other file.
Outcome:
- This command prints `PANEL-OK` and the number of objects:
  `MAIN/.venv/bin/python -I -c "import json;d='docs/handoff/findings/';c={'T8.1','T8.2'};w={(s,k,i) for s in ('M7-M9-reviews.json','M7-M9-review-2.json') for k,v in json.load(open(d+s)).items() if k.split()[1] in c for i in range(len(v))};p=json.load(open(d+'M7-M9-panel-M8.json'));g=[(o['source'],o['key'],o['index']) for o in p];assert len(g)==len(set(g)) and set(g)==w,sorted(set(g)^w);assert all(o['verdict'] in ('confirmed','partly','disputed','unknown') and o['evidence'] and o['note'] and (o['verdict']!='confirmed' or o['fix']) for o in p);print('PANEL-OK',len(p))"`
- `git status --porcelain` lists only `docs/handoff/findings/M7-M9-panel-M8.json`.
allowedPaths: `docs/handoff/findings/M7-M9-panel-M8.json`
Depends on: PANEL-M7-M9-c.

## PANEL-M7-M9-e: check the review findings on T9.1, T9.2 and T9.3 (report only)
Why: `docs/handoff/queue.md` §8 revises the drafts in `docs/handoff/drafts/M7-M9/` from their review findings, and no
one has checked those findings yet. A finding is a claim to test, not evidence. Opus reads this panel, rules wherever
the verdict is not `confirmed`, and then plans the revision. The panel runs in five parts, one after another; this
part covers T9.1, T9.2 and T9.3.
Do:
- Check, each on its own, every finding under the keys `review <card> executability` and `review <card> design` for
  T9.1, T9.2 and T9.3, in `docs/handoff/findings/M7-M9-reviews.json` (which has only T7.1 and T7.2) and
  `docs/handoff/findings/M7-M9-review-2.json`.
  - Open every file the finding cites, at HEAD, and read the cited lines. Never take its quotes or line numbers as read.
  - Re-derive the claim from the draft, any other draft it involves, `docs/spec.md`, `docs/plan.md`,
    `docs/architecture.md` and the committed code.
  - For Blender's behaviour, read Blender 5.2.2's bundled Python. This item lets you search these three directories of
    it, and no other: `MAIN/.cache/blender/blender-5.2.2-linux-x64/5.2/scripts/startup/`, `.../scripts/modules/` and
    `.../scripts/presets/`. A read-only probe may run
    `MAIN/.cache/blender/blender-5.2.2-linux-x64/blender -b --factory-startup --python-expr '<code>'`; quote the code
    and its output.
- Write `docs/handoff/findings/M7-M9-panel-M9.json`: a JSON list with one object per finding, ordered by source
  (`M7-M9-reviews.json` first), then key as in the file, then index. Fields:
  - `source` (the file name), `key`, and `index` (the finding's 0-based position in that key's list);
  - `verdict`: `confirmed` (the defect is real as stated, and its fix removes it), `partly` (real, but the issue or
    the fix is wrong in a way `note` states), `disputed` (not a defect) or `unknown` (the tree cannot decide it);
  - `evidence`: the file:line spans you read and every command you ran, with its output quoted;
  - `duplicate_of`: `{source, key, index}` of an earlier object in this list that states the same defect, else `null`;
  - `fix`: the edit to the draft as exact old and new text. Required for `confirmed`; for `partly`, the corrected
    edit where you can give one; otherwise `null`. Do not apply it;
  - `note`: one or two sentences. For `disputed` it says why; for `unknown` it names what is missing.
- Change no other file.
Outcome:
- This command prints `PANEL-OK` and the number of objects:
  `MAIN/.venv/bin/python -I -c "import json;d='docs/handoff/findings/';c={'T9.1','T9.2','T9.3'};w={(s,k,i) for s in ('M7-M9-reviews.json','M7-M9-review-2.json') for k,v in json.load(open(d+s)).items() if k.split()[1] in c for i in range(len(v))};p=json.load(open(d+'M7-M9-panel-M9.json'));g=[(o['source'],o['key'],o['index']) for o in p];assert len(g)==len(set(g)) and set(g)==w,sorted(set(g)^w);assert all(o['verdict'] in ('confirmed','partly','disputed','unknown') and o['evidence'] and o['note'] and (o['verdict']!='confirmed' or o['fix']) for o in p);print('PANEL-OK',len(p))"`
- `git status --porcelain` lists only `docs/handoff/findings/M7-M9-panel-M9.json`.
allowedPaths: `docs/handoff/findings/M7-M9-panel-M9.json`
Depends on: PANEL-M7-M9-d.

## REVISE-M7-a: apply the checked review findings to the T7.1 draft
Why: `docs/handoff/queue.md` §8 revises the M7-M9 drafts from their review findings before they become cards. The
panel checked every finding, Sonnet checked the panel, and Opus ruled: `docs/handoff/findings/M7-M9-rulings.md`.
Do:
- Revise `docs/handoff/drafts/M7-M9/T7.1-panels-and-overrides.md` as `M7-M9-rulings.md` says under "How to apply them,
  per card". Use the T7.1 objects of `docs/handoff/findings/M7-M9-panel-check-M7a.json`, each with its fix in
  `M7-M9-panel-T7.1.json`. Then apply the cross-cutting rulings X1 and C4, and the M7a section. C4 is
  `RESEARCH_SOCKETS`; its mechanism is in the M9 section, under T9.1 design#0.
- Keep the draft's style and structure. Change nothing the rulings don't ask for.
- Answer with one line per panel object (source, key, index, ruling, and the draft lines you changed, or "no edit"),
  then one line per cross-cutting ruling you applied.
Outcome: the pinned verify prints `REVISE-OK 11`. It checks two things, whitespace aside:
- the new text of every `apply` fix that overlaps no other fix is in the draft;
- the draft names `RESEARCH_SOCKETS`.
The cross-check item and Opus's approval read the rest.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import json;F='docs/handoff/findings/';D='docs/handoff/drafts/M7-M9/';n=lambda s:' '.join(s.split());t=n(' '.join(open(D+f).read() for f in ['T7.1-panels-and-overrides.md']));W=[('M7-M9-panel-T7.1.json','M7-M9-reviews.json','review T7.1 executability',0),('M7-M9-panel-T7.1.json','M7-M9-reviews.json','review T7.1 executability',1),('M7-M9-panel-T7.1.json','M7-M9-reviews.json','review T7.1 executability',2),('M7-M9-panel-T7.1.json','M7-M9-reviews.json','review T7.1 executability',3),('M7-M9-panel-T7.1.json','M7-M9-reviews.json','review T7.1 design',3),('M7-M9-panel-T7.1.json','M7-M9-reviews.json','review T7.1 design',4),('M7-M9-panel-T7.1.json','M7-M9-reviews.json','review T7.1 design',5),('M7-M9-panel-T7.1.json','M7-M9-reviews.json','review T7.1 design',6),('M7-M9-panel-T7.1.json','M7-M9-reviews.json','review T7.1 design',8),('M7-M9-panel-T7.1.json','M7-M9-reviews.json','review T7.1 design',10),('M7-M9-panel-T7.1.json','M7-M9-reviews.json','review T7.1 design',11)];m=[w[1:] for w in W for o in json.load(open(F+w[0])) if (o['source'],o['key'],o['index'])==tuple(w[1:]) for e in (o['fix'] if isinstance(o['fix'],list) else [o['fix']]) if n(e['new']) not in t];assert not m,m;assert 'RESEARCH_SOCKETS' in t,'extra 0';print('REVISE-OK',len(W))"`
allowedPaths: `docs/handoff/drafts/M7-M9/T7.1-panels-and-overrides.md`
Depends on: PANEL-M7-M9-c.

## REVISE-M7-b: apply the checked review findings to the T7.2 draft
Why: as REVISE-M7-a, for T7.2.
Do:
- Revise `docs/handoff/drafts/M7-M9/T7.2-presets.md` as `docs/handoff/findings/M7-M9-rulings.md` says under "How to
  apply them, per card". Use the T7.2 objects of `M7-M9-panel-check-M7a.json`, each with its fix in
  `M7-M9-panel-T7.2.json`. Then apply the cross-cutting rulings X1 and J1, and the M7a section, which gives the
  resolutions of T7.2's eleven overlapping pairs.
- Keep the draft's style and structure. Change nothing the rulings don't ask for.
- Answer as REVISE-M7-a does.
Outcome: the pinned verify prints `REVISE-OK 2`: the new text of every `apply` fix that overlaps no other fix is in
the draft, whitespace aside.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import json;F='docs/handoff/findings/';D='docs/handoff/drafts/M7-M9/';n=lambda s:' '.join(s.split());t=n(' '.join(open(D+f).read() for f in ['T7.2-presets.md']));W=[('M7-M9-panel-T7.2.json','M7-M9-reviews.json','review T7.2 executability',3),('M7-M9-panel-T7.2.json','M7-M9-review-2.json','review T7.2 executability',2)];m=[w[1:] for w in W for o in json.load(open(F+w[0])) if (o['source'],o['key'],o['index'])==tuple(w[1:]) for e in (o['fix'] if isinstance(o['fix'],list) else [o['fix']]) if n(e['new']) not in t];assert not m,m;print('REVISE-OK',len(W))"`
allowedPaths: `docs/handoff/drafts/M7-M9/T7.2-presets.md`
Depends on: PANEL-M7-M9-c.

## REVISE-M7-c: apply the checked review findings to the T7.3 and T7.4 drafts
Why: as REVISE-M7-a, for T7.3 and T7.4.
Do:
- Revise `docs/handoff/drafts/M7-M9/T7.3-lane-stagger.md` and `T7.4-exp-animation.md` as
  `docs/handoff/findings/M7-M9-rulings.md` says under "How to apply them, per card". Use the T7.3 and T7.4 objects of
  `M7-M9-panel-check-M7b.json`, each with its fix in `M7-M9-panel-T7.3-T7.5.json`. Then apply:
  - the cross-cutting rulings X1 and X2;
  - C1 and C2, which build on T7.1's revised text: read the revised T7.1 draft for it;
  - the M7b section: T7.3's outcome bullet for a refuted H1, and T7.4's rule R(a).
- Keep the drafts' style and structure. Change nothing the rulings don't ask for. No pre-registered rule changes except
  the one the M7b section states.
- Answer as REVISE-M7-a does.
Outcome: the pinned verify prints `REVISE-OK 1`. It checks, whitespace aside:
- the one clean `apply` fix's new text is in the drafts;
- no "DRAFT (Haiku)" is left;
- "DRAFT (DeepSeek)" is present.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import json;F='docs/handoff/findings/';D='docs/handoff/drafts/M7-M9/';n=lambda s:' '.join(s.split());t=n(' '.join(open(D+f).read() for f in ['T7.3-lane-stagger.md', 'T7.4-exp-animation.md']));W=[('M7-M9-panel-T7.3-T7.5.json','M7-M9-review-2.json','review T7.4 design',2)];m=[w[1:] for w in W for o in json.load(open(F+w[0])) if (o['source'],o['key'],o['index'])==tuple(w[1:]) for e in (o['fix'] if isinstance(o['fix'],list) else [o['fix']]) if n(e['new']) not in t];assert not m,m;assert 'DRAFT (Haiku)' not in t,'extra 0';assert 'DRAFT (DeepSeek)' in t,'extra 1';print('REVISE-OK',len(W))"`
allowedPaths: `docs/handoff/drafts/M7-M9/T7.3-lane-stagger.md`, `docs/handoff/drafts/M7-M9/T7.4-exp-animation.md`
Depends on: REVISE-M7-a.

## REVISE-M7-d: apply the checked review findings to the T7.5 draft
Why: as REVISE-M7-a, for T7.5, after T7.1's and T7.2's revisions, which it follows.
Do:
- Revise `docs/handoff/drafts/M7-M9/T7.5-artist-guide.md` as `docs/handoff/findings/M7-M9-rulings.md` says under "How
  to apply them, per card". Use the T7.5 objects of `M7-M9-panel-check-M7b.json`, each with its fix in
  `M7-M9-panel-T7.3-T7.5.json`. Then apply:
  - the cross-cutting ruling X1;
  - C3: the presets as T7.2's revised draft has them, so Soft strokes is gone;
  - C4: `expected_knob_headings` exempts T7.1's `RESEARCH_SOCKETS`, named as in T7.1's revised draft.
- Keep the draft's style and structure. Change nothing the rulings don't ask for.
- Answer as REVISE-M7-a does.
Outcome: the pinned verify prints `REVISE-OK 0` (this card has no clean `apply` fix) after checking that the draft
names `RESEARCH_SOCKETS`.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import json;F='docs/handoff/findings/';D='docs/handoff/drafts/M7-M9/';n=lambda s:' '.join(s.split());t=n(' '.join(open(D+f).read() for f in ['T7.5-artist-guide.md']));W=[];m=[w[1:] for w in W for o in json.load(open(F+w[0])) if (o['source'],o['key'],o['index'])==tuple(w[1:]) for e in (o['fix'] if isinstance(o['fix'],list) else [o['fix']]) if n(e['new']) not in t];assert not m,m;assert 'RESEARCH_SOCKETS' in t,'extra 0';print('REVISE-OK',len(W))"`
allowedPaths: `docs/handoff/drafts/M7-M9/T7.5-artist-guide.md`
Depends on: REVISE-M7-a, REVISE-M7-b.

## REVISE-M8: apply the checked review findings to the T8.1 and T8.2 drafts
Why: as REVISE-M7-a, for T8.1 and T8.2.
Do:
- Revise `docs/handoff/drafts/M7-M9/T8.1-release-workflow.md` and `T8.2-repository-index-and-install-docs.md` as
  `docs/handoff/findings/M7-M9-rulings.md` says under "How to apply them, per card". Use the objects of
  `M7-M9-panel-check-M8.json`, each with its fix in `M7-M9-panel-M8.json`. Then apply the cross-cutting ruling X1 and
  the M8 section:
  - D39's `INSTALL_PLATFORMS`;
  - Step 1 keeps wheels.yml's whole `pull_request` block (read `.github/workflows/wheels.yml` at HEAD);
  - Blender comes from `$BLENDER`;
  - `.github/workflows/static.yml` is the only Pages publisher and goes under T8.2's Modify, with the actions at its
    versions;
  - no post-deploy step.
- Keep the drafts' style and structure. Change nothing the rulings don't ask for.
- Answer as REVISE-M7-a does.
Outcome: the pinned verify prints `REVISE-OK 2`. It checks, whitespace aside:
- the new text of every `apply` fix that overlaps no other fix is in the drafts;
- the drafts name `INSTALL_PLATFORMS` and `static.yml`;
- no `deploy-pages@v4` is left.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import json;F='docs/handoff/findings/';D='docs/handoff/drafts/M7-M9/';n=lambda s:' '.join(s.split());t=n(' '.join(open(D+f).read() for f in ['T8.1-release-workflow.md', 'T8.2-repository-index-and-install-docs.md']));W=[('M7-M9-panel-M8.json','M7-M9-review-2.json','review T8.1 executability',0),('M7-M9-panel-M8.json','M7-M9-review-2.json','review T8.1 design',1)];m=[w[1:] for w in W for o in json.load(open(F+w[0])) if (o['source'],o['key'],o['index'])==tuple(w[1:]) for e in (o['fix'] if isinstance(o['fix'],list) else [o['fix']]) if n(e['new']) not in t];assert not m,m;assert 'INSTALL_PLATFORMS' in t,'extra 0';assert 'deploy-pages@v4' not in t,'extra 1';assert 'static.yml' in t,'extra 2';print('REVISE-OK',len(W))"`
allowedPaths: `docs/handoff/drafts/M7-M9/T8.1-release-workflow.md`, `docs/handoff/drafts/M7-M9/T8.2-repository-index-and-install-docs.md`
Depends on: PANEL-M7-M9-d.

## REVISE-M9-a: apply the checked review findings to the T9.1 and T9.2 drafts
Why: as REVISE-M7-a, for T9.1 and T9.2.
Do:
- Revise `docs/handoff/drafts/M7-M9/T9.1-mesh-ghost-candidates.md` and `T9.2-exp-mesh-ghost.md` as
  `docs/handoff/findings/M7-M9-rulings.md` says under "How to apply them, per card". Use the T9.1 and T9.2 objects of
  `M7-M9-panel-check-M9.json`, each with its fix in `M7-M9-panel-M9.json`; those fixes name no file, so each applies to
  its finding's card. Then apply:
  - the cross-cutting rulings X1, X2 and C4 (T9.1 adds `mesh_ghost` to T7.1's `RESEARCH_SOCKETS`; take the name from
    T7.1's revised draft);
  - the M9 section: T9.1 exec#0's option B, T9.1 design#0's gate, and T9.2 design#1's cost ordering, combined with
    design#0 as the check file says.
- T9.1's Step 5, Appendices A and C and its Contract change section are rewritten against HEAD's
  `src/painterly/kernel/globals.h` and `src/painterly/scene/device_scene.cpp`. Read them, and cite file:line in the
  revised text.
- Keep the drafts' style and structure. Change nothing the rulings don't ask for.
- Answer as REVISE-M7-a does.
Outcome: the pinned verify prints `REVISE-OK 3`. It checks, whitespace aside:
- the new text of every `apply` fix that overlaps no other fix is in the drafts;
- the drafts name `RESEARCH_SOCKETS`;
- no "DRAFT (Haiku)" is left.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import json;F='docs/handoff/findings/';D='docs/handoff/drafts/M7-M9/';n=lambda s:' '.join(s.split());t=n(' '.join(open(D+f).read() for f in ['T9.1-mesh-ghost-candidates.md', 'T9.2-exp-mesh-ghost.md']));W=[('M7-M9-panel-M9.json','M7-M9-review-2.json','review T9.1 design',2),('M7-M9-panel-M9.json','M7-M9-review-2.json','review T9.1 design',3),('M7-M9-panel-M9.json','M7-M9-review-2.json','review T9.2 executability',1)];m=[w[1:] for w in W for o in json.load(open(F+w[0])) if (o['source'],o['key'],o['index'])==tuple(w[1:]) for e in (o['fix'] if isinstance(o['fix'],list) else [o['fix']]) if n(e['new']) not in t];assert not m,m;assert 'RESEARCH_SOCKETS' in t,'extra 0';assert 'DRAFT (Haiku)' not in t,'extra 1';print('REVISE-OK',len(W))"`
allowedPaths: `docs/handoff/drafts/M7-M9/T9.1-mesh-ghost-candidates.md`, `docs/handoff/drafts/M7-M9/T9.2-exp-mesh-ghost.md`
Depends on: REVISE-M7-a.

## REVISE-M9-b: apply the checked review findings to the T9.3 draft, and split off T9.3b
Why: as REVISE-M7-a, for T9.3. Opus's ruling on T9.3 exec#1 splits its Blender half into a new card.
Do:
- Revise `docs/handoff/drafts/M7-M9/T9.3-exp-open-scenes.md` as `docs/handoff/findings/M7-M9-rulings.md` says under
  "How to apply them, per card". Use the T9.3 objects of `M7-M9-panel-check-M9.json`, each with its fix in
  `M7-M9-panel-M9.json`. Then apply the cross-cutting rulings X1 and X2 and the M9 section.
- The split creates `docs/handoff/drafts/M7-M9/T9.3b-exp-open-scenes-blender.md`.
  - T9.3b holds H6, Appendices D-F, render.py's Blender hook, its own pre-registration and its own smoke run. It
    depends on T9.3, and its Appendix D reads `bl_idname` with `getattr`.
  - T9.3 keeps the native path (H1-H5, H7). H7b becomes a measurement.
- Every count or seed the split changes is recomputed with a script you run from the draft's own code (kept under
  .ds-scratch/). Quote the command and its output in your answer. Never edit a count by hand.
- Keep the drafts' style and structure. Change nothing the rulings don't ask for.
- Answer as REVISE-M7-a does, and list each count you changed with its old and new value.
Outcome: the pinned verify prints `REVISE-OK 3`. It checks, whitespace aside:
- both drafts exist;
- the new text of every `apply` fix that overlaps no other fix is in them;
- no "DRAFT (Haiku)" is left.
verify: `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -I -c "import json;F='docs/handoff/findings/';D='docs/handoff/drafts/M7-M9/';n=lambda s:' '.join(s.split());t=n(' '.join(open(D+f).read() for f in ['T9.3-exp-open-scenes.md', 'T9.3b-exp-open-scenes-blender.md']));W=[('M7-M9-panel-M9.json','M7-M9-review-2.json','review T9.3 executability',0),('M7-M9-panel-M9.json','M7-M9-review-2.json','review T9.3 executability',2),('M7-M9-panel-M9.json','M7-M9-review-2.json','review T9.3 design',2)];m=[w[1:] for w in W for o in json.load(open(F+w[0])) if (o['source'],o['key'],o['index'])==tuple(w[1:]) for e in (o['fix'] if isinstance(o['fix'],list) else [o['fix']]) if n(e['new']) not in t];assert not m,m;assert 'DRAFT (Haiku)' not in t,'extra 0';print('REVISE-OK',len(W))"`
allowedPaths: `docs/handoff/drafts/M7-M9/T9.3-exp-open-scenes.md`, `docs/handoff/drafts/M7-M9/T9.3b-exp-open-scenes-blender.md`
Depends on: PANEL-M7-M9-e.

## EXP-REPRO: the committed results of experiments 001-006 reproduce on this machine
Why:
- On 2026-10-15 the project moved from a cloud container to this machine, and the render cache did not move.
- The host regenerated every render with the experiments' oracle, rebuilt from the pre-T3.4 source; its sha256 is in
  Q/RULINGS.md.
- Every later analysis, and the designs of experiments 007-009, rest on the committed results of 001-006.
Do:
- For each of 001, 002, 003, 004 and 006, run that experiment's `analyze.py` with `--out-dir <clone>/repro/<NNN>`.
  Run it with
  `PAINTERLY_BUILD_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/oracle-build PAINTERLY_CACHE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache`.
  It must render nothing: if it reports a missing render, call `report_blocked`.
- Compare every output file with the committed file of the same name, using `cmp`.
- Write `tools/compare_results.py`, with tests in `tests/core/test_compare_results.py`. It loads two `results.json`
  files and walks every leaf.
  - For numeric leaves, it reports committed, new, the absolute difference and the relative difference.
  - For non-numeric leaves (verdicts, rejected-key lists, strings, booleans), it reports identical or not.
- Write `docs/handoff/repro/REPRO.json` with these fields:
  - per experiment and per file: `identical` (from cmp);
  - for each `results.json` that is not identical: the leaf report and `non_numeric_identical` (true or false);
  - the top-level field `"all_identical"`: true only if every file of every experiment is byte-identical.
- Write `docs/handoff/repro/REPRO.md`: a table of the same facts. Report numbers only, with no interpretation.
Outcome:
- `MAIN/.venv/bin/python -m pytest -q tests/core/test_compare_results.py` passes.
- REPRO.json parses and has entries for 001, 002, 003, 004 and 006.
- `make lint` with the KNOBS passes.
allowedPaths: `tools/compare_results.py`, `tests/core/test_compare_results.py`, `docs/handoff/repro/**`.

## EXP-REPRO-HOST: this machine's outputs of the 001-006 analyses, the reference for exact checks (R17)
Why:
- EXP-REPRO found the 24 committed figures of 001-004 and 006 byte-identical on this machine, and the five committed
  `results.json` files different in numeric leaves only, by at most 1.8e-13 relative (`docs/handoff/repro/REPRO.md`).
- Later items check analysis outputs exactly (`==`, `cmp`). On this machine they compare `results.json` with the record
  this item writes (R17).
Do:
- For each of 001, 002, 003, 004 and 006, run that experiment's `analyze.py --out-dir .cache/repro-host/<NNN>` from the
  clone root, prefixed with `PYTHONPATH="$PWD/analysis"` (R12), with
  `PAINTERLY_BUILD_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/oracle-build PAINTERLY_CACHE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache`.
  It must render nothing: if it reports a missing render, call `report_blocked`.
- `cmp` every output figure with the committed figure of the same name.
- Copy each output `results.json` byte for byte to `docs/handoff/repro/host/<NNN>/results.json`. Copy no figure.
- Write `docs/handoff/repro/host/README.md`: what these files are (R17), the commands you ran, the experiments' oracle
  sha256 (R7), the date, and the results of the Outcome checks. Numbers only.
Outcome:
- All 24 output figures are byte-identical to the committed ones.
- For each NNN, `compare_objects` from `tools/compare_results.py`, applied to the committed `results.json` and to
  `docs/handoff/repro/host/<NNN>/results.json`, returns exactly (`==` on the parsed JSON) the report stored for NNN in
  `docs/handoff/repro/REPRO.json` under `["<NNN>"]["results.json"]["leaves"]`.
- `make lint` with the KNOBS passes.
Depends on: EXP-REPRO.
allowedPaths: `docs/handoff/repro/host/**`.

## M3-FIX-T3.25: self-describing oracle renders (TQ.1 F22; panel #17)
Card: `docs/handoff/drafts/M3-fixups/T3.25-self-describing-oracle.md`.
- The card's cache checks read `PAINTERLY_CACHE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache`
  read-only.
- The card's `.cache/oracle-build` is the experiments' oracle,
  `/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/oracle-build`
  (R7, R17), never `build/q`. It never rebuilds it.
- EXP-REPRO established that the committed figures and every verdict of 001-006 reproduce on this machine, and that their
  `results.json` numbers differ in the last bits (R17). This card compares no `results.json`.
- Its `python -I` commands run as R18 says, so that `cache_keys.py` imports this clone's `painterly_analysis`.
Depends on: EXP-REPRO, M3-FIX-T3.24.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M3-FIX-T3.26: analysis constants and runner reuse (TQ.1 F27, F28)
Card: `docs/handoff/drafts/M3-fixups/T3.26-analysis-constants.md`.
- Step 2 and A6 (the reproduction check) run in your clone, against MAIN's render cache read-only, not "in the main tree
  only". Save Appendix A as printed, then change exactly these three things in it:
  - `unset PAINTERLY_CACHE` becomes
    `export PAINTERLY_CACHE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache`;
  - `PAINTERLY_BUILD_DIR=.cache/oracle-build` becomes
    `PAINTERLY_BUILD_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/oracle-build`;
  - `.venv/bin/python` becomes
    `PYTHONPATH="$PWD/analysis" /run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python`.
- On this machine `before` and `after` each print five `<n> analyze exit 0` lines, exactly five `DIFFERS:` lines (the
  five committed `results.json` files, and no figure), and `compared 29 committed files, 5 differ`. That is EXP-REPRO's
  finding (R17), not a failure. Any other output is a failure.
- A6 also requires that, for n in 001 002 003 004 006, these print nothing:
  `cmp .cache/t3.26/before/$n/results.json docs/handoff/repro/host/$n/results.json`, the same for `after`, and
  `diff -r .cache/t3.26/before/$n .cache/t3.26/after/$n`.
- The commit body's reproduction line is
  `001-004, 006: 24 committed figures byte-identical; 5 results.json byte-identical to docs/handoff/repro/host, before and after; stdout identical.`
- Scratch outputs go inside the clone, under `.cache/t3.26/` (git-ignored).
Depends on: M3-FIX-T3.25, EXP-REPRO-HOST.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## EXP-007: run the pre-registered analysis of experiment 007 (noise locking)
Card: `experiments/007-2026-10-15-noise-locking/PLAN.md`, with every amendment in its README.
- The renders are complete in MAIN's `.cache/renders`. Never render there. PLAN's smoke runs render into a scratch
  cache inside your clone, as PLAN says.
- Use `PAINTERLY_BUILD_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/oracle-build`
  and `PAINTERLY_CACHE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache`.
- The Conclusion is a DRAFT.
- Hold (Opus, 2026-10-22): plan no new task for this item. t-exp007-run's worker finished, and its proposal is kept for
  a re-audit, which waits for a ds-queue fix (50-web-framework, round 51). A new attempt would redo about 5 hours of
  runs and meet the same audit-size limit. Opus requeues t-exp007-run for the re-audit.
Depends on: M3-FIX-T3.26.
Outcome: PLAN.md's Acceptance, translated, including the second full run being byte-identical; and `make lint` with
the KNOBS passes.
allowedPaths: `experiments/007-2026-10-15-noise-locking/README.md`, `experiments/007-2026-10-15-noise-locking/analyze.py`, `experiments/007-2026-10-15-noise-locking/results.json`, `experiments/007-2026-10-15-noise-locking/synthetic.json`, `experiments/007-2026-10-15-noise-locking/fig_*.png`, `experiments/README.md`, `analysis/painterly_analysis/metrics.py`, `analysis/painterly_analysis/__init__.py`, `analysis/painterly_analysis/report.py`, `analysis/tests/test_scale_metrics.py`, `analysis/tests/test_report.py`.

## EXP-008: run the pre-registered analysis of experiment 008 (jitter dose-response)
Card: `experiments/008-2026-10-15-jitter-dose-response/PLAN.md`, with every amendment in its README. The same
environment rules as EXP-007 apply. PLAN's render step is already done on the host: skip it and report so.
Depends on: EXP-007.
Outcome: PLAN.md's Acceptance, translated; and `make lint` with the KNOBS passes.
allowedPaths: `experiments/008-2026-10-15-jitter-dose-response/README.md`, `experiments/008-2026-10-15-jitter-dose-response/analyze.py`, `experiments/008-2026-10-15-jitter-dose-response/power.py`, `experiments/008-2026-10-15-jitter-dose-response/test_analyze.py`, `experiments/008-2026-10-15-jitter-dose-response/results.json`, `experiments/008-2026-10-15-jitter-dose-response/fig_dose_response.png`, `experiments/008-2026-10-15-jitter-dose-response/fig_crops.png`, `experiments/README.md`.

## EXP-009: run the pre-registered analysis of experiment 009 (scale limits)
Card: `experiments/009-2026-10-15-scale-limits/PLAN.md`, with every amendment in its README. The same environment
rules as EXP-007 apply. PLAN's render and disk-preflight steps are already done on the host: skip them and report so.
Depends on: EXP-008.
Outcome: PLAN.md's Acceptance, translated; and `make lint` with the KNOBS passes.
allowedPaths: `experiments/009-2026-10-15-scale-limits/README.md`, `experiments/009-2026-10-15-scale-limits/analyze.py`, `experiments/009-2026-10-15-scale-limits/test_analyze.py`, `experiments/009-2026-10-15-scale-limits/results.json`, `experiments/009-2026-10-15-scale-limits/fig_*.png`, `experiments/README.md`, `analysis/painterly_analysis/metrics.py`, `analysis/painterly_analysis/__init__.py`, `analysis/tests/test_scale_metrics.py`.
