# TQ.2 — Code-quality audit: the queue's first 19 commits

Auditors: read-only Sonnet readers, with every finding below checked by Opus. Tree audited: `f7b633d`, branch
`claude/clever-johnson-gnso1s`. Scope: the code that DeepSeek workers landed through ds-queue, i.e. the commits whose
subject starts with `t-` (`d62559c` to `70d1e66`). This is the standing chore of `docs/handoff/queue.md` ("one turn in
about twelve"), run on 2026-10-18 as part of the friction review Micah asked for while the DeepSeek credit was refilled.

## Method

- Every `t-` commit was read with `git show`, tests first, then `src/`, `analysis/` and `tools/`. Reading was static,
  plus read-only Python on committed JSON and tools.
- Searched for: tests that cannot fail, stubs, dead or duplicated code, swallowed errors, numbers in comments that do
  not match the code, and CLAUDE.md rule 2 violations.
- Opus re-checked each finding at the cited lines before recording it. A reader's claim that did not survive is listed
  under "Rejected".

Severity scale as in TQ.1. **Medium**: a gap that lets regressions through, or a reproducibility problem with real
cost. **Low**: consistency or hygiene.

## Findings

| # | Sev. | Finding | Evidence | Status |
|---|---|---|---|---|
| F1 | Medium | The `-ffp-contract=off` canary cannot fail in any build the project makes: the tests compile with at most `-msse4.2`, and only `transform_avx2.cpp` gets `-mfma`, so GCC has nothing to contract. Deleting the flag passes every test. | `src/test/test_math_double3.cpp:229`; `src/cycles/CMakeLists.txt:63-65`; `cmake/painterly_embree_config.cmake:40`; t-fix324's mutation M1 compiled by hand with `-mfma -mavx2` | BACKLOG M3-FIX-TQ2-CPP |
| F2 | Medium | The prebuilt-Embree proof tests never run: they hard-code this machine's source paths and look for an install at `build/embree-install`, which nothing creates, so both slow tests always skip. | `tests/core/test_embree_prebuilt.py:199-212`, `:227`, `:253` | BACKLOG M3-FIX-TQ2-PY |
| F3 | Medium | `ComparisonReport.identical` is true when neither side has a unit, so `compare-flags` can print "EMBREE FLAGS IDENTICAL: 0 units", the vacuous pass its docstring says it avoids. R11's "149 units" is correct (a reader recounted `compile_commands.json`). | `tools/embree_prebuilt.py:132-136`, docstring `:34-37` | BACKLOG M3-FIX-TQ2-PY |
| F4 | Low | A bound derivation cites `docs/tasks/M3/T3.21-contract-touchups.md, appendix A`, which does not exist (the appendix is in `docs/handoff/drafts/M3-fixups/`). The sentence "relative errors from 1.0 u to 1.3 u" names no command. | `src/test/test_bvh.cpp:57-58`, `:73` | BACKLOG M3-FIX-TQ2-CPP |
| F5 | Medium | `compare_results` compares leaves with Python `==`, so `true` against `1` counts as identical, although its docstring says a boolean is not a number. A type change in a results file is invisible to EXP-REPRO's `non_numeric_identical`. | `tools/compare_results.py:182-183` | BACKLOG M3-FIX-TQ2-PY |
| F6 | Medium | Two scene tests cannot see what they claim: `:653` and `:655` compute the same expression (the second is labelled "reference"), and `:280-313` uses only dyadic values, which cannot tell `double(float)` from a decimal round trip. | `src/test/test_scene.cpp:637`, `:653-655`, `:280-313` | BACKLOG M3-FIX-T3.13b |
| F7 | Low | Duplicates: `make_ray` (identical in two test files), M_s->cam (twice, as transposes), the 3x3 identity (three times). One unused include. | `src/test/test_analytic.cpp:88`, `src/test/test_bounce.cpp:143`; `src/painterly/scene/camera.cpp:6`, `:20`, `device_scene.cpp:45`, `:209`, `scene.h:104`, `scene.cpp:32` | M3-FIX-TQ2-CPP (`make_ray`), M3-FIX-T3.13b (the rest) |
| F8 | Low | Since BOOT-0b (`9c4b68b`) the root `CMakeLists.txt` includes the Embree configuration unconditionally, so its `FATAL_ERROR` for a CPU other than x86_64 or arm64 now also stops an oracle-only build. Before, it ran only for module or test builds. | `CMakeLists.txt:9`; `cmake/painterly_embree_config.cmake:46-52` | Noted; no card (no such build exists today) |
| F9 | Medium | EXP-REPRO's `REPRO.json` and `REPRO.md` come from a generator that lived in the worker's git-ignored `.tmp/`, so they cannot be regenerated. A reader recomputed every count and maximum from `REPRO.json`, and they match. The max-difference path picks the first of tied leaves by an unstated rule (002 max_abs: 2 tied, 003 max_rel: 2, 006 max_abs: 3). | `docs/handoff/repro/`; `t-exprepro-repro/answer.md:9` | Noted; an item follows once EXP-007's plan is settled, since R17 uses these files |

## Rejected

- "`compare_results.main` exits 0 on a difference and `EXIT_USAGE` is never used": by design. The module documents
  exit 0 for a completed comparison (the result is in the report), and `EXIT_USAGE` names argparse's own status
  (`tools/compare_results.py:70-74`).

## Clean

Re-checked and correct:
- the quotes in `AMENDMENTS-fixups.md` against `fdc6357`;
- the sha256 values in `docs/handoff/repro/host/README.md`;
- the normal-matrix numbers in `test_path.cpp` and `test_bvh.cpp`;
- the Newton-step bounds (4.26u and 3.26u);
- the Embree and smallpaint line citations.

No TODOs, stubs, bare `except` or unchecked `subprocess` calls were found. The one `contextlib.suppress(OSError)`
(`tools/embree_prebuilt.py:177`) is justified in its comment.
