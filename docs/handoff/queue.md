# Work queue (ordered)

Model tiers:
- **strong** (Opus-class): judgment calls, experiment design and conclusions, contract changes, review panels.
- **mid** (Sonnet-class): card review and revision, cross-checks.
- **cheap** (Haiku-class): card implementation and acceptance gates.

Every item ends with a machine-checkable gate. Items 1-3 are the critical path. Items 5-8 can run alongside it in a
separate git worktree, except where noted.

## 1. Finish the M3 fix-up cards T3.19-T3.28 (mid; T3.21 review strong)
Inputs:
- `drafts/M3-fixups/`: T3.19-T3.26 drafted. T3.27 and T3.28 still have to be drafted from their briefs in
  `workflows/m3-fixup-cards.js` (`CARDS`).
- The sources the cards cite: `findings/M3-run3a-panel-confirmed.json` (#0-#19), `docs/audits/TQ.1.md` (F1-F28) and
  `decisions-M3.md` (D33-D39).
- Review results already computed (`findings/M3-fixups-reviews.json`): T3.19, T3.20 and T3.21 on both lenses, T3.22 on
  executability only.

Steps:
1. Draft T3.27 (vendor_sync reads pinned git blobs, panel #0) and T3.28 (licences, notices, docs, and the wheels.yml path
   filter; panel #3, #4, #8/#15, #13, #14, #16).
2. Review every card that has no review yet, on both lenses: T3.22 correctness, T3.23-T3.28 both.
3. Revise each card with its findings. Verify each finding against the code first.
4. Propagate renames into the not-yet-run cards `docs/tasks/M3/T3.13-T3.18`, `M4`, `M5` and `src/blender/_painterly.pyi`:
   - VERTEX_PASS becomes VERTEX_TINT (D14);
   - `KernelPainterlyObject.tfm/itfm` and `tri_vertices` give way to `normal_to_world` (D35);
   - `PAINTERLY_OBJECT_ID_MISS` moves to the kernel;
   - the lane clamp and `max_depth >= 1` (T3.20);
   - the target names from T3.22;
   - F12 (the selftest through painterly_bvh) moves into T3.15 (D34);
   - `meta.json` v2 (T3.25).
5. Run the cross-check loop until a round reports 0 issues. It checks names, file ownership and order, D33-D39
   consistency, and that every panel finding and TQ.1 F-number has exactly one card. T3.29 is withdrawn (D39).

Gate: the cross-check reports 0 issues, and the cards and amendments are committed to `docs/tasks/M3/` in one commit.

## 2. Implement the fix-up batch (cheap; T3.21 strong)
- Driver: `workflows/milestone-panel.js`, with args `cards` = T3.19..T3.28 in order (T3.21 with `model: 'opus'`).
  - `note`: "never run make oracle; use BUILD_DIR=build/<card> if another workflow builds".
  - `lenses`: the three run-3a lenses (spec-and-parity, layout-naming-quality, build-portability-isolation).
- Gate: every card passes its gate, and the panel's confirmed findings are fixed or carded. `make check` passes. After the
  push, CI is green, including the `windows` MSVC job.

## 3. M3 run 3b: T3.13-T3.18 (cheap; panel strong)
- Same driver and lenses.
- T3.18 (throughput experiment) needs a strong model for its pre-registration check and its Conclusion.
- Gate (the M3 exit criteria in `docs/plan.md`):
  - `tests/core/test_oracle_parity.py` is bit-exact against `oracle --halton exact`;
  - output is identical across thread counts and batch sizes;
  - `make check` passes and the symbol audit passes;
  - CI is green.
- Then regenerate the owner's gallery sheets from the native core next to the oracle. `firstlight/` shows how; the
  bitwise difference must be 0.

## 4. Experiments 007-009 (strong for the pre-registration review and conclusions; cheap for renders and analysis)
- **State at handoff.**
  - The drafts are in the session scratch (`scratchpad/prereg/00{7,8,9}/`).
  - A writable second-round fix pass was running when this bundle was made.
  - Its inputs, the second-round findings and the read-only proposals, are summarized in `conversation.md`.
  - If this bundle's commit also contains `experiments/007-*` and the others, the pre-registrations are final. Otherwise
    the drafts must be recovered and the fix pass re-run.
- **Rules.**
  - The directory date is the date of the commit that creates the directory, numbered in run order 007, 008, 009.
  - Every decision interval is 99%.
  - Never `make oracle`.
  - Free disk first: about 7.8 GB is needed against about 4 GB free.
- **Renders.** `nice -n 19`, `PAINTERLY_BUILD_DIR=.cache/oracle-build`, budget calls as each PLAN.md states, 008 before 009.
- **Gate.** Each analysis exits 0 and its outputs reproduce byte for byte. A strong model writes the Conclusion.

## 5. M6a cards (mid), then the M6a run (cheap; panel strong)
- Apply the second-round findings for T6.6, T6.7 and T6.8 (`findings/M6a-reviews.json`, key `latest` of the
  `review T6.x ...` entries). T6.1-T6.5 already include theirs.
- Known fixes:
  - T6.4's "decision 6" duplicates T2.11's `NOMINMAX` (already PUBLIC on cycles_util), so drop it;
  - T6.5 must not hard-code an experiment number ("next free number at run time").
- Cross-check the set (the prompt is in `workflows/m6a-cards.js`) until dry. Then commit to `docs/tasks/M6a/`.
- Run in a git worktree from the latest main-line commit. M6a depends only on T3.1-T3.3. Merge back at checkpoints.
- Gate: each card's acceptance passes, plus the panel.

## 6. M4 and M5 (cheap; panel strong)
- Cards are committed. Apply the item-1 amendments first.
- Gate: per `docs/plan.md`. T5.4 parity against the ghost=lights oracle on the realization-free key family.

## 7. M6b cards (strong drafting, mid review)
Not drafted. Write them from `research/cycles_svm_report.md` (stages S0-S7) after M6a lands, then run them as above.

## 8. M7-M9 cards (mid), then runs
- Apply the reviews of T7.1 and T7.2 (`findings/M7-M9-reviews.json`).
- Review T7.3-T9.3 on both lenses (executability, design), revise, and cross-check.
- D39 applies to T8.1: keep the existing macOS wheel and add nothing macOS-specific.
- Experiments inside these cards (T7.3, T7.4, T9.2, T9.3) take the next free number at run time.

## Standing chores
- Spend one turn in about twelve on a code-quality audit (owner preference). TQ.1 is the model: an audit file, trivial
  fixes in one commit, and proposed cards for the rest.
- Keep `experiments/README.md` (the index) in step with every experiment.
