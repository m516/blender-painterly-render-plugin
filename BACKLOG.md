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

## M3-T3.13: painterly/scene (host scene, reflected PainterlyIntegrator, device_update)
Card: `docs/tasks/M3/T3.13-scene.md`. Depends on: M3-PROPAGATE.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M3-T3.14: painterly/session (asynchronous, cancellable render sessions)
Card: `docs/tasks/M3/T3.14-session.md`. Depends on: M3-T3.13.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M3-T3.15: the _painterly Python API exactly as in _painterly.pyi
Card: `docs/tasks/M3/T3.15-bindings.md`. Depends on: M3-T3.14.
Outcome: the card's Acceptance, translated; `CHECK` exits 0; and the symbol audit passes.

## M3-T3.16: exact parity with smallpaint_oracle, bit for bit
Card: `docs/tasks/M3/T3.16-oracle-parity.md`. Depends on: M3-T3.15.
- The oracle here is the dev build's `build/q/src/app/smallpaint_oracle` with `--halton exact` (SPEC §2).
- Never use MAIN's experiments' oracle.
Outcome: the card's Acceptance, translated; `CHECK` exits 0. The card's slow 400 px test must pass too:
`PAINTERLY_BUILD_DIR=build/q /run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin/.venv/bin/python -m pytest -q -m slow tests/core/test_oracle_parity.py`.

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

## M4-T4.1: extension skeleton (manifest, engine class, facade)
Card: `docs/tasks/M4/T4.1-extension-skeleton.md`. Depends on: M3-T3.18.
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

## M6a-T6.2: fragment extraction and the generated SVM switch
Card: `docs/handoff/drafts/M6a/T6.2-fragment-extraction.md`. Depends on: M6a-T6.1.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M6a-T6.3: stack-only SVM evaluators and byte-code doctests
Card: `docs/handoff/drafts/M6a/T6.3-svm-stack-nodes.md`. Depends on: M6a-T6.2.
- The card's "experiment 007" (X-svm probe) is a stale number: 007 is taken.
- Create it as the next free experiment number at run time, with today's date, following
  `docs/tasks/M1/_experiment_protocol.md`. Its Conclusion is a DRAFT.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M6a-T6.4: vendored shader graph, constant folding, core shader nodes, cycles_scene
Card: `docs/handoff/drafts/M6a/T6.4-shader-graph.md`. Depends on: M6a-T6.3.
- Skip the card's decision 6 (defining `NOMINMAX`). T2.11 already defines it PUBLIC on `cycles_util`, so don't add it
  again.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M6a-T6.5: the SVM compiler, PainterlyShaderManager, graph → byte code → evaluation
Card: `docs/handoff/drafts/M6a/T6.5-svm-compiler.md`. Depends on: M6a-T6.4.
- The card's "experiment 007 part 2" (gate G2-svm) belongs to the experiment M6a-T6.3 created. Use that directory and
  number.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M6a-T6.6: texture and texture-coordinate SVM nodes
Card: `docs/handoff/drafts/M6a/T6.6-svm-textures.md`.
Review findings: `docs/handoff/findings/M6a-reviews.json`, keys `review T6.6 executability` and
`review T6.6 verbatim-vendoring`, field `latest`.
Depends on: M6a-T6.5.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M6a-T6.7: closure SVM nodes and BSDF lookup tables
Card: `docs/handoff/drafts/M6a/T6.7-svm-closures.md`.
Review findings: `docs/handoff/findings/M6a-reviews.json`, keys `review T6.7 executability` and
`review T6.7 verbatim-vendoring`, field `latest`.
Depends on: M6a-T6.6.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

## M6a-T6.8: image texture SVM nodes on the CPU and an in-memory ImageManager
Card: `docs/handoff/drafts/M6a/T6.8-svm-images.md`.
Review findings: `docs/handoff/findings/M6a-reviews.json`, keys `review T6.8 executability` and
`review T6.8 verbatim-vendoring`, field `latest`.
Depends on: M6a-T6.7.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0.

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
