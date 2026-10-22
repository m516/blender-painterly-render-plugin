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

## M4-T4.1: extension skeleton (manifest, engine class, facade)
Card: `docs/tasks/M4/T4.1-extension-skeleton.md`. Depends on: M3-T3.17.
- Re-pointed on 2026-10-22: T4.1 needs T3.17's triangle path and nothing from experiment X-throughput.
Outcome: the card's Acceptance, translated, with Blender at the `BLENDER` path; and `CHECK` exits 0.

## M4-T4.2: properties from core reflection; panels, presets, operators
Card: `docs/tasks/M4/T4.2-properties-ui.md`. Depends on: M4-T4.1.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M4-T4.3: render loop (session ↔ RenderResult, output modes, built-in reference scene)
Card: `docs/tasks/M4/T4.3-render-loop.md`. Depends on: M4-T4.2.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M4-T4.4: build, install and render the extension in real Blender 5.2.2
Card: `docs/tasks/M4/T4.4-extension-build-it.md`. Depends on: M4-T4.3.
Outcome: the card's Acceptance, translated: the extension builds and installs into a profile directory inside your
clone, and renders headless with the `BLENDER` binary. Also `CHECK` exits 0.

## M5-T5.1: camera sync
Card: `docs/tasks/M5/T5.1-sync-camera.md`. Depends on: M4-T4.4.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M5-T5.2: geometry sync (meshes and instances)
Card: `docs/tasks/M5/T5.2-sync-geometry.md`. Depends on: M5-T5.1.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M5-T5.3: lights, world and constant materials
Card: `docs/tasks/M5/T5.3-sync-lights-world-materials.md`. Depends on: M5-T5.2.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M5-T5.4: the smallpaint scene in Blender, and parity of the full Blender path
Card: `docs/tasks/M5/T5.4-reference-blend-parity.md`. Depends on: M5-T5.3.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

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

## M6a-T6.3: stack-only SVM evaluators and byte-code doctests
Card: `docs/handoff/drafts/M6a/T6.3-svm-stack-nodes.md`. Depends on: M6a-T6.2.
- The card's "experiment 007" (X-svm probe) is a stale number: 007 is taken.
- Create it as the next free experiment number at run time, with today's date, following
  `docs/tasks/M1/_experiment_protocol.md`. Its Conclusion is a DRAFT.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify counts the card's test cases (and assertions where the card states them), so it cannot pass with none run: doctest prints `Status: SUCCESS!` for a filter that matches nothing.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest" && build/q/src/test/painterly_tests --test-case='cycles svm stack nodes:*' | grep -qE '^\[doctest\] test cases: +7 \| +7 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles svm stack nodes:*' | grep -qE '^\[doctest\] assertions: +131 \| +131 passed \| +0 failed \|'`

## M6a-T6.4: vendored shader graph, constant folding, core shader nodes, cycles_scene
Card: `docs/handoff/drafts/M6a/T6.4-shader-graph.md`. Depends on: M6a-T6.3.
- Skip the card's decision 6 (defining `NOMINMAX`). T2.11 already defines it PUBLIC on `cycles_util`, so don't add it
  again.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify counts the card's test cases (and assertions where the card states them), so it cannot pass with none run: doctest prints `Status: SUCCESS!` for a filter that matches nothing.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest" && build/q/src/test/painterly_tests --test-case='cycles shader graph*' | grep -qE '^\[doctest\] test cases: +7 \| +7 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles shader graph: links use UI names; parameters use member names' | grep -qE '^\[doctest\] test cases: +1 \| +1 passed \| +0 failed \|'`

## M6a-T6.5: the SVM compiler, PainterlyShaderManager, graph → byte code → evaluation
Card: `docs/handoff/drafts/M6a/T6.5-svm-compiler.md`. Depends on: M6a-T6.4.
- The card's "experiment 007 part 2" (gate G2-svm) belongs to the experiment M6a-T6.3 created. Use that directory and
  number.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify counts the card's test cases (and assertions where the card states them), so it cannot pass with none run: doctest prints `Status: SUCCESS!` for a filter that matches nothing.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest" && build/q/src/test/painterly_tests --test-case='cycles svm compiler:*' | grep -qE '^\[doctest\] test cases: +6 \| +6 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles svm compiler:*' | grep -qE '^\[doctest\] assertions: +85 \| +85 passed \| +0 failed \|'`

## M6a-T6.6: texture and texture-coordinate SVM nodes
Card: `docs/handoff/drafts/M6a/T6.6-svm-textures.md`.
Review findings: `docs/handoff/findings/M6a-reviews.json`, keys `review T6.6 executability` and
`review T6.6 verbatim-vendoring`, field `latest`.
Depends on: M6a-T6.5.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify counts the card's test cases (and assertions where the card states them), so it cannot pass with none run: doctest prints `Status: SUCCESS!` for a filter that matches nothing.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest" && build/q/src/test/painterly_tests --test-case='cycles svm textures:*' | grep -qE '^\[doctest\] test cases: +12 \| +12 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles svm textures:*' | grep -qE '^\[doctest\] assertions: +36 \| +36 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles texture nodes:*' | grep -qE '^\[doctest\] test cases: +4 \| +4 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles texture nodes:*' | grep -qE '^\[doctest\] assertions: +85 \| +85 passed \| +0 failed \|'`

## M6a-T6.7: closure SVM nodes and BSDF lookup tables
Card: `docs/handoff/drafts/M6a/T6.7-svm-closures.md`.
Review findings: `docs/handoff/findings/M6a-reviews.json`, keys `review T6.7 executability` and
`review T6.7 verbatim-vendoring`, field `latest`.
Depends on: M6a-T6.6.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify counts the card's test cases (and assertions where the card states them), so it cannot pass with none run: doctest prints `Status: SUCCESS!` for a filter that matches nothing.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest" && build/q/src/test/painterly_tests --test-case='cycles svm closures:*' | grep -qE '^\[doctest\] test cases: +12 \| +12 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles svm closures:*' | grep -qE '^\[doctest\] assertions: +163 \| +163 passed \| +0 failed \|'`

## M6a-T6.8: image texture SVM nodes on the CPU and an in-memory ImageManager
Card: `docs/handoff/drafts/M6a/T6.8-svm-images.md`.
Review findings: `docs/handoff/findings/M6a-reviews.json`, keys `review T6.8 executability` and
`review T6.8 verbatim-vendoring`, field `latest`.
Depends on: M6a-T6.7.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.
- The verify counts the card's test cases (and assertions where the card states them), so it cannot pass with none run: doctest prints `Status: SUCCESS!` for a filter that matches nothing.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest" && build/q/src/test/painterly_tests --test-case='cycles svm images:*' | grep -qE '^\[doctest\] test cases: +8 \| +8 passed \| +0 failed \|' && build/q/src/test/painterly_tests --test-case='cycles svm images:*' | grep -qE '^\[doctest\] assertions: +122 \| +122 passed \| +0 failed \|'`

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
