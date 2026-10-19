# Instructions for coding agents (DeepSeek via the ollama harness)

This file is loaded into every harness call whose `--root` is this repository. It holds the standing procedure, so a
task prompt only needs the task. It goes to a cloud model: never put secrets or private data in it.

## The project in brief
Painterly is a Blender 5.2 render-engine extension. It reproduces, and makes controllable, the painterly look of
Károly Zsolnai-Fehér's `smallpaint_painterly`, a look that comes from a Halton-sequence bug.
- **The native core** is C++20, laid out and named like Cycles: `src/painterly/<layer>/`. Reusable Cycles source is
  vendored verbatim into `third_party/cycles/`, and shims live in `src/cycles/shim/`.
- **Python:**
  - `analysis/painterly_analysis/` holds the statistics and image metrics, with JAX for compute-heavy work;
  - `src/blender/` holds the bindings (nanobind module `_painterly`);
  - `tests/` holds pytest; C++ unit tests are doctest in `src/test/`.
- **`src/app/smallpaint_oracle.cpp`** is the reference renderer. On analytic scenes the core must equal it bit for bit
  (`--halton exact`), for any thread count and batch size.
- **Normative documents.** Read only what your task needs:
  - `docs/spec.md` defines behaviour; cite it as `SPEC §n`;
  - `docs/architecture.md` covers layout, naming, the determinism contract and isolation;
  - `CLAUDE.md` holds the project's golden rules. They bind you too, except its "Finish protocol" (see Rules).
- **Work arrives as a task card** (`docs/tasks/M*/T*.md`, or a path the backlog item names). The card is the
  specification:
  - Goal;
  - Read first;
  - Create/Modify: the only files you may touch;
  - Acceptance: commands that must pass;
  - Commit: the subject line.
  An experiment's `PLAN.md` is its analysis card.

## Environment (known; don't spend steps diagnosing)
- **Offline.** There is no network, and installing anything fails by design (`uv sync`, `pip`). Never run `make env`,
  `make blender`, `make oracle` or `make wheel`.
- **Prepared on the host.** These paths in the main checkout
  `MAIN = /run/media/zeta/scratch/little-puzzles/43-blender-smallpaint/blender-painterly-render-plugin` are prepared on
  the host. READ them by these exact paths only; never write to them and never search them:
  - `MAIN/.venv/`: the Python 3.13 project environment (ruff, clang-format, pytest, nanobind, JAX). Python is
    `MAIN/.venv/bin/python`.
  - `MAIN/.cache/src/embree/` and `MAIN/.cache/src/doctest/`: dependency sources (Embree v4.4.1, doctest v2.4.11).
  - `MAIN/.cache/blender/blender-5.2.2-linux-x64/blender`: Blender 5.2.2, headless with `-b`.
  - `MAIN/.cache/oracle-build/src/app/smallpaint_oracle`: the experiments' oracle binary.
  - `MAIN/.cache/renders/`: the experiments' render cache, made on the host.
  - Other paths, only where `BACKLOG.md` or the task names them.
- **The gate.** `BACKLOG.md` defines `CHECK`, the exact offline `make check` command, with knobs that point at those paths.
  - Wherever a card says `make check`, `make build`, `make test`, `make lint` or `make audit`, run it with the same
    knobs (see the BACKLOG translation table).
  - Wherever a card says `build/dev`, use your own build directory.
  - Use the BACKLOG knobs for parallelism; the machine is shared.
- **Long runs.** Background jobs die when the bash call that started them returns. Run long work in the foreground, in
  chunks that finish well inside one bash call (30 min). Write one result file per item and skip items already done,
  so rerunning the same command continues where it stopped.

## Rules
- **Stay inside your working directory** (the clone you start in). Read, list, search and write only there. The one
  exception: READ the `MAIN` paths above by exact path. Never search (grep/find/rg/ls -R) outside your root; the shared
  tree is huge and on a slow drive.
- **The queue's own files are not inputs.** Never read `MAIN/.tmp/`: other tasks' proposals and diffs, audit prompts,
  the mailbox and the integration clone. Work from your card, your task and your clone. When a task may reuse an earlier
  attempt's work, it names the exact file.
- **Scratch files never enter the diff (R16).** Write temporary files under `/tmp` or a git-ignored path of your clone
  (`.cache/`, `build/`, `.tmp/`). Any other untracked file fails the whole task. Before your final answer,
  `git status --porcelain` must list only files inside allowedPaths.
- **No host paths in committed code or tests.** Never write an absolute path of this machine (`/run/media/...`, the
  `MAIN` paths) into committed code or tests. Take it from a knob (an environment variable or an option with a
  documented default) that the verify sets; a test skips with a reason only when the knob is unset.
- **Scope.** Touch only the files your card and task allow: the card's Create/Modify list, which the task's
  allowedPaths enforce.
  - Never hand-edit `third_party/`. Only `tools/vendor_sync.py` writes it, and only when the card says so.
  - Never edit `docs/spec.md`, `docs/plan.md`, `CLAUDE.md`, `AGENTS.md`, `BACKLOG.md`, `docs/handoff/`, or any file
    whose first lines contain `CONTRACT:`, unless your card lists that exact file under Create/Modify.
- **The card is the specification.** If the card is wrong or impossible, or contradicts the code (a symbol, a line, a
  command), call `report_blocked` with the evidence: the command and its output, or file:line. Don't improvise around it.
- **Contracts.** If a card asks for the contract's signature or behaviour and the contract does not state it, call
  `report_blocked`; never write the contract yourself in a docstring.
- **Review findings.** Some backlog items name a JSON file of review findings about their card. Check each against the
  code. Apply the ones that are correct and stay within the card's files. In your answer, list each one as applied or
  rejected, with a one-line reason.
- **Writing a review.** An empty findings list is a valid result: never add a finding to fill one. Quote only text you
  read at the file:line you cite, and name the file the text is in.
- **No magic numbers** (CLAUDE.md rule 2).
  - Every tunable value is a named knob with a documented default.
  - A constant that reproduces smallpaint cites its source line. A mathematical constant says what it is.
  - Tests use exact equality, or the statistical criteria in `analysis/painterly_analysis/ensemble.py`.
  - A tolerance appears only with its bound derived in a comment (float64 round-off, or float32 where the computation
    is float32).
- **Bit-exactness.** Parity and determinism tests compare bit patterns (exact equality or memcmp). Never weaken one.
  Changes that should not affect output must keep output bit-identical, and the card's tests prove it.
- **Naming and style.** Follow CLAUDE.md rule 3:
  - Cycles style, `CCL_NAMESPACE_BEGIN/END`, the `Painterly`/`KernelPainterly`/`painterly_` prefixes, clang-format;
  - Python: PEP 8, ruff-clean, type hints, docstrings that state units.
  - The same word for the same concept everywhere: `chain`, `lane`, `pass`/`passes` (never "spp"), `K`,
    `k_consumed`, `object_id`, `ghost sphere`, `spiral frame`.
- **Tests.** Tests are deterministic. Mark any test slower than about 10 s with `@pytest.mark.slow`.
- **Git.** Never run `git commit`, `push`, `rebase` or `reset`. The queue turns your diff into the commit. Its subject
  is `<task id>: <backlog item id>: <item title>` (for example `t-fix325: M3-FIX-T3.25: ...`), not your card's Commit
  line, so find an earlier card's commit by its backlog item id (`M3-FIX-T3.25:`), never by a pattern anchored at the
  subject's start. CLAUDE.md's "Finish protocol" is for Claude agents; your final answer replaces
  it. The answer must contain:
  - the files changed;
  - every acceptance command, with pass or fail and its key output lines;
  - every value the card asks you to report;
  - your deviations, each with its reason (and the finding id it answers);
  - any acceptance step you could not run because it needs the host, CI or the network, marked "host-only, not run".
- **Acceptance commands run as written.** Run each acceptance command exactly as the card gives it, translated only by
  the BACKLOG table. An output that differs from what the card says is a fail, even when you can explain it: report
  both, and call `report_blocked` when no honest reading of the card passes. Never report another command's result as
  the card's.
- Where a card asks for text "in the commit body", put that text in your answer under the heading `## Commit body`.
- Where a detail isn't specified, make a sensible choice, name it in your answer, and don't search for a spec that
  isn't given.
- Never end with an empty reply; if you are blocked, say so and name the blocker.
- Run only your task's own tests and the verify; if a wider regression run seems warranted, say so instead of running
  it.
- **Reuse your build.** Configure once, with the `CHECK` knobs, into your build directory; after that
  `cmake --build <dir>` is incremental. While iterating, run only the cases you changed
  (`<dir>/src/test/painterly_tests -tc='<case>'`, `pytest <file>::<test>`), and run the full `CHECK` once, at the end.
  Delete the build directory only when a configure error requires it, and say so.
- If three different code approaches fail on the same check, stop and call `report_blocked` with that check's output.
- If a limit makes you split one change into several commits, make each one pass its own test, or say in the first
  commit's body that its test fails until the next. Never quote a Verified line you did not get at that exact commit.

## Expected values are evidence, not targets
- **Never move an expected value.** Don't edit, widen, loosen or re-pin an expected value, threshold, tolerance,
  decision rule, band or reference number to match what the code outputs. A check that fails is a finding: report it,
  don't adjust the check.
- **Never search until a check passes.** Don't try different parameters, seeds, seed windows, budgets, constants or
  thresholds because an earlier choice failed. Choose by a rule you state first, and report every setting you tried.
- **Pre-registered experiments.** An experiment README's Hypothesis and Method are frozen.
  - Implement the analysis exactly as its PLAN.md and amendments say. Never change a decision rule, level, key list,
    exclusion or seed after seeing data.
  - Results report numbers, not adjectives.
  - A Conclusion you write starts with "DRAFT (DeepSeek) — pending Opus review."
- **Measured means reproducible.** Every number you report comes from a committed script, or from an exact command you
  give, on named inputs. Never compute an expected value by hand: compute it with a script you run, and paste the
  command and its output next to the value. A script that produces a committed number, table or report is committed
  in the same diff, next to its output, with the command that regenerates it; if allowedPaths has no place for it,
  call `report_blocked`.
- **Reproduce first.** Before analysing anything new, reproduce the stored number your task names exactly. If it
  doesn't reproduce, stop and report.
- If an expected value can't be met honestly, call `report_blocked`.

## Pace
- Read what the card points to, then start: build early, test on a small case, then scale up.
- Stop exploring once the acceptance checks pass. Further observations go in a short section of your answer, not into
  more runs.
