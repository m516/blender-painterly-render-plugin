# Handoff: Painterly, state on 2026-10-15

This directory lets an agent continue the project without the original conversation. Read in this order:
1. this file;
2. `queue.md`: the ordered work, each item with its gate and recommended model tier;
3. `decisions.md` and `decisions-M3.md`: binding decisions (D1-D39) that cards and reviews must follow;
4. `conversation.md`: what the owner asked for and decided, and what we learned;
5. the project's own rules: `CLAUDE.md`, `docs/spec.md` (normative), `docs/plan.md`, `docs/architecture.md` and
   `docs/tasks/README.md` (card template).

## Where the project stands

**Branch.** All work is on `claude/clever-johnson-gnso1s`. At handoff the head was `696dc0c`, plus the commit that adds
this bundle. The project has no PR. CI (`ci.yml`: Linux and Windows/MSVC) and `wheels.yml` (three OS) are green.

| Milestone | State |
|---|---|
| M0-M1: scaffolding, oracle, analysis package, experiments 001-006 | done. All six experiments have final Conclusions |
| M2: static module, symbol audit, wheels, coexistence (gate G1) | done. G1 is not triggered on Linux, macOS or Windows (experiment 005, "Later runs") |
| M3 run 3a: T3.1-T3.12 (vendoring, kernel, Embree BVH, path, lane scheduler), TQ.1 audit | done and reviewed. The 20 confirmed findings are planned into the fix-up batch |
| M3 fix-up batch T3.19-T3.28 | cards drafted, not yet reviewed (`drafts/M3-fixups/`, see `drafts/STATUS.md`) |
| M3 run 3b: T3.13-T3.18 (scene, session, bindings, oracle parity, triangle path, throughput) | cards committed in `docs/tasks/M3/`. They need the fix-up renames propagated first (queue item 1) |
| M4 (add-on skeleton), M5 (scene sync) | cards committed in `docs/tasks/M4`, `M5`, not run |
| M6a (Cycles SVM as a vendored library) | cards T6.1-T6.8 drafted and revised once. T6.6-T6.8 have second-round findings to apply (`drafts/M6a/`) |
| M6b (SVM inside the painterly kernel) | not drafted. Input: `research/cycles_svm_report.md` |
| M7 (artist UX, presets), M8 (release), M9 (research) | cards drafted; only T7.1 and T7.2 are reviewed so far (`drafts/M7-M9/`) |
| Experiments 007-009 (noise locking, jitter dose-response, scale limits) | pre-registered and committed (`experiments/00{7,8,9}-2026-10-15-*`); renders and analysis pending (queue item 4) |

**First light of the native core** (`firstlight/README.md`). A scratch driver (`firstlight/render.cpp`) rendered the
reference scene through `PainterlyPathTrace`.
- 18 of 18 configurations equal `smallpaint_oracle` bit for bit: chains, ghost modes, alpha, u2 mode, emitter
  continuation, 200-800 px, up to 512 passes. The reference rule is SPEC §2: bit parity uses `--halton exact`.
- The output is identical for any thread count and batch size.
- The native core takes 0.84× the oracle's time per thread.
- The run found the NaN case now fixed in SPEC §4 (D33). Card T3.19 implements it.

## How work is done here (the process that produced the results)

- **Cards.** Every change is a task card (`docs/tasks/M*/T*.md`, template `docs/tasks/README.md`). A card states Goal,
  Read first, Create/Modify (exact paths), Acceptance (runnable commands, no hand-picked tolerances) and Commit. An agent
  touches only the files its card lists (CLAUDE.md rule 1).
- **Implementation driver.** `workflows/milestone-panel.js` (Claude Code Workflow tool). For each card:
  - a cheap implementer (Haiku) and an independent gate agent that re-runs the acceptance commands; one retry, and a
    `card_defect` flag when the card itself is wrong;
  - then a review panel of strong-model lenses (spec and parity, layout and naming, build and portability), each finding
    checked by two skeptics. Confirmed findings become fix-up cards.
  - Args: `{milestone, base_commit, cards: [{id, path, note?, model?, continue_on_fail?}], lenses, review_context}`.
- **Card writing.** Drafter, two review lenses (executability; correctness or design), revision, then a cross-check
  loop over the whole set until it is dry. Examples: `workflows/m3-fixup-cards.js`, `m6a-cards.js`, `m7-m9-cards.js`.
- **Experiments.** Follow `docs/tasks/M1/_experiment_protocol.md` and CLAUDE.md "Experiments":
  - the README has exactly Background, Hypothesis, Method, Results and Conclusion;
  - numbered and dated in run order;
  - a pre-registration is committed before any render;
  - the final Conclusion is written by a strong model.
- **Decisions.** When a card or review needs a judgment call, record it as `D<n>` in `decisions-M3.md` with its reason, and
  cite it in the card.

## Hard rules and pitfalls (each one has cost us before)

- **Never run `make oracle`.** The experiments' render cache (`.cache/renders`, 658+ renders) is keyed by the sha256 of
  `.cache/oracle-build/src/app/smallpaint_oracle` (`066bb5d4247c556ad5232bfc4fff75dc5f37089840b23f1ecc8fdd9cb518828a`, the
  pre-T3.4 binary). Experiments run with `PAINTERLY_BUILD_DIR=.cache/oracle-build`. Dev work uses `build/dev`.
- **Parallel builds.** Two agents building in one tree must use separate build directories:
  `make check BUILD_DIR=build/<name>`. The Makefile exports `PAINTERLY_BUILD_DIR` from it.
- **Plan mode is inherited by subagents.** If the session is in plan mode, every workflow agent runs read-only and
  silently "proposes" instead of editing. On 2026-10-15 this cost one full pass. Check file mtimes after write stages.
- **Workflow resume replays only the unchanged prefix of agent calls in start order.** Changing one early prompt re-runs
  everything after it. When only a later stage failed, prefer a small new "finish" workflow fed with the cached findings
  (`findings/*.json`).
- **Container restarts and weekly limits.** Scratch space is not durable, so commit anything worth keeping. After a
  restart the Workflow tool accepts only readable script paths: copy scripts next to the work.
- **Disk.** About 4 GB was free on 2026-10-15. Experiments 008 and 009 need about 7.8 GB of new renders, so free space first
  (scratch build directories only; never `.cache/renders` or `.cache/oracle-build`).
- **CI timing.** The MSVC `windows` job takes about 35 min and `wheels (windows-2022)` about 45 min. `ci.yml` builds with
  `ninja -k 0`, so one run lists every failing translation unit.
- **macOS is low priority (D39).** Keep the existing macOS wheel and coexist jobs. Add nothing macOS-specific, and report
  macOS-only failures instead of blocking on them.
- **External LLM providers.** A peer session suggested handing work to DeepSeek through a "ds-autopilot" adapter. This
  container has no such adapter, and sending the repository to an outside provider needs the owner's explicit approval.

## Contents of this directory

| Path | What |
|---|---|
| `queue.md` | ordered work queue with gates and model tiers |
| `decisions.md` | owner decisions (scope, platforms, fidelity) |
| `decisions-M3.md` | engineering decisions D1-D39, binding |
| `conversation.md` | condensed history of the owner conversation and lessons |
| `drafts/STATUS.md` | per-card status of every drafted card |
| `drafts/M3-fixups/`, `drafts/M6a/`, `drafts/M7-M9/` | drafted cards (not executable until reviewed and moved to `docs/tasks/`) |
| `findings/*.json` | review findings computed but not yet applied, and the M3 run-3a panel results |
| `workflows/*.js` | the Workflow scripts. They hold absolute scratch paths, so adapt `SP`/`OUT` before reuse |
| `firstlight/` | the first-light report and the scratch render driver (a starting point for T3.16 checks) |
| `research/` | the Cycles SVM vendoring study (`cycles_svm_report.md`, stages S0-S7) that M6 is built on |
