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
- Change no existing assertion. The edits to existing tests are the fixtures above, step 6 (its mechanism, not its
  outcomes), B3, and the added parametrized cases.
Outcome:
- `CHECK` exits 0.
- `git grep -n write_text -- tests/core/test_vendor_fragments.py` prints nothing.
- Host only, after landing (Opus): `python -I tools/vendor_sync.py check --upstream` exits 0 on the real checkout, so the
  pinned blobs give every recorded fragment hash and line range.
verify: `PYTHONPATH="$PWD/analysis" CMAKE_BUILD_PARALLEL_LEVEL=4 make check VENV=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv BUILD_DIR=build/q BLENDER=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/blender/blender-5.2.2-linux-x64/blender CMAKE_ARGS="-DFETCHCONTENT_FULLY_DISCONNECTED=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/embree -DFETCHCONTENT_SOURCE_DIR_DOCTEST=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/src/doctest -Dembree_DIR=/run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.cache/embree-prebuilt/install/lib/cmake/embree-4.4.1"`
allowedPaths: `tools/vendor_sync.py`, `tests/core/test_vendor_fragments.py`, `tests/core/test_gen_fragment_units.py`, `tests/core/test_gen_svm_switch.py`, `tests/core/test_vendored.py`
Depends on: M6a-T6.8.

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
Depends on: M6a-T6.8.

## M6a-FIX-SVMT: the SVM node doctests fail when the node they test changes
Why (reader B, reader C and audit B): mutations of the code under the T6.5-T6.8 doctests that no test notices.
B2: the shader-manager checks of `src/test/test_cycles_svm_compiler.cpp` reach 2 of the 15 flag conditions of
`PainterlyShaderManager::device_update_common` (`src/painterly/scene/svm/shader_manager.h:273-323`). Every expectation is
`default_shader_flags` (`:189-195`: SD_VOLUME_MIS and SD_USE_BUMP_MAP_CORRECTION; compared at `:319, 373, 420, 421`).
`use_volumes` and `transparent_shadows` are compared with their zero-initialised values (`:374-375`), so deleting the
writes at `shader_manager.h:119` and `:339` passes. `rgb_to_y` is compared with the manager's own member (`:378-383`),
so nothing pins its value; and the value depends on the CPU, because `transform_inverse` runs a different function on
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
Depends on: M6a-T6.8.

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
Depends on: M6a-T6.8.

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
