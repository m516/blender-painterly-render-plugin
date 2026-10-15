# Status of drafted cards (2026-10-15)

These drafts are **not executable** until they are reviewed, revised and cross-checked (`queue.md`), then moved to
`docs/tasks/M*/`. They follow the template in `docs/tasks/README.md`.

## M3 fix-ups (`M3-fixups/`): cards T3.19-T3.28, run before M3 run 3b (D34)
| Card | Source findings | Drafted | Reviewed (lenses) | Revised |
|---|---|---|---|---|
| T3.19 zero-length bounce | D33 | yes | executability, correctness (`findings/M3-fixups-reviews.json`) | no |
| T3.20 scheduler robustness | TQ.1-1 (F1-F8) | yes | both | no |
| T3.21 contract touch-ups (strong model) | TQ.1-6, D35-D37, panel #7, #19 | yes | both | no |
| T3.22 build hygiene | TQ.1-2 without F12, panel #5, #6, #9, #18 | yes | executability only | no |
| T3.23 shared test scaffolding | TQ.1-3, panel #1 | yes | no | no |
| T3.24 kernel test coverage | TQ.1-4, panel #10, #11, #12 | yes | no | no |
| T3.25 self-describing oracle | TQ.1-5, panel #17 | yes (its 10-10 drafter hit the usage limit; check the card is complete) | no | no |
| T3.26 analysis constants | TQ.1-7 | yes | no | no |
| T3.27 vendor_sync from pinned blobs | panel #0 | **no**: brief in `workflows/m3-fixup-cards.js` | — | — |
| T3.28 licences, notices, docs, wheels path filter | panel #3, #4, #8/#15, #13, #14, #16 | **no**: brief in `workflows/m3-fixup-cards.js` | — | — |
| ~~T3.29 macOS CI job~~ | panel #2 | withdrawn (D39) | — | — |

## M6a (`M6a/`): Cycles SVM as a standalone vendored library
- T6.1-T6.5 are drafted, reviewed twice and revised twice.
  - T6.1's last revision dry-ran every acceptance command in a scratch clone.
- T6.6-T6.8 are drafted and revised once. Their second-round findings are in `findings/M6a-reviews.json` (key `latest`)
  and still need applying.
- No set-level cross-check has run yet.
- Known fixes:
  - T6.4 "decision 6" duplicates T2.11's NOMINMAX;
  - T6.5 must not hard-code an experiment number.

## M7-M9 (`M7-M9/`)
- **T7.1 panels and overrides; T7.2 presets.** Drafted and reviewed (17 and 13 findings in `findings/M7-M9-reviews.json`);
  not revised.
- **T7.3-T9.2.** Drafted; not reviewed:
  - T7.3 lane stagger;
  - T7.4 animation experiment;
  - T7.5 artist guide;
  - T8.1 release workflow;
  - T8.2 repository index and install docs;
  - T9.1 mesh-ghost candidates;
  - T9.2 mesh-ghost experiment.
- **T9.3 open-scenes experiment.** The file exists, but its drafter hit the usage limit. Check that it is complete, and
  re-draft it if not.
- M6b is not drafted (`research/cycles_svm_report.md`).
