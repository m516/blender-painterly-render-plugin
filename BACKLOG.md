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

**Coming later; do not plan these yet.**
Claude adds these items once the host has regenerated the render cache. Until then they can't run, because they read
`MAIN/.cache/renders` and need every render to be present:
- M3-FIX-T3.25 (self-describing oracle renders) and M3-FIX-T3.26 (analysis constants);
- EXP-REPRO (experiments 001-006 reproduce on this machine);
- EXP-007, EXP-008 and EXP-009 (the pre-registered analyses).

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

## M3-FIX-T3.22: build hygiene (TQ.1 F9-F11, F13, F15; panel #5, #6, #9, #18)
Card: `docs/handoff/drafts/M3-fixups/T3.22-build-hygiene.md`.
- BOOT-0a has added `VENV` and `CMAKE_ARGS` to the Makefile. Keep both when the card edits the Makefile.
- The card's header-only doctest change must keep working with `-DFETCHCONTENT_SOURCE_DIR_DOCTEST=...`, as `CHECK`
  passes it.
Review findings: `docs/handoff/findings/M3-fixups-reviews.json`, key `review T3.22 executability`.
Depends on: M3-FIX-T3.21.
Outcome: the card's Acceptance, translated; and `CHECK` exits 0. The card's MSVC checks are host-only.

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
