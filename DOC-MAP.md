# DOC-MAP: every doc in 43, who reads it, and what to cut

Pick the next doc to cut from **Order** below, then read its row: the reader, what they must do after reading, and
whether a hash, test or tool reads it (that text stays exempt and changes only together with its reader).

## Status (2026-10-18)

- Mapped: all 134 tracked `.md` files outside `third_party/` (this one included), the 5 `LICENSES/` texts, and the live
  `.tmp/ds-queue/RULINGS.md`. Read-only Sonnet readers wrote the rows; Opus checked the claims used in Order.
- Cut so far: **RULINGS.md consolidated** (2026-10-18). One standing ruling, machine R35, now carries every standing
  rule outside the preamble, and machine R1-R34 are superseded. The live rulings in each prompt fell from 44,533 to
  12,281 bytes (-72%). A fresh reader answered the RULINGS quiz from the result before any supersede was applied.
  Old ids map through R35's brackets: `S1 [R11 now active]`, `S2 [R17]`, `S3 [R18]`; R16 is AGENTS.md's scratch rule; R19
  is spent.
- Next: the other docs, by DeepSeek (halve, quiz, grade) once the DeepSeek credit is back.
- Quizzes: `~/.claude/doc-quizzes/43-<doc>.json`, outside the tree the DeepSeek sandbox can read.
- CLAUDE.md is cut only on Micah's direct word in a 43 session.

## Order (most-read first)

1. **RULINGS.md** (44,533 B, in every DeepSeek prompt): consolidate the standing rulings into one standing ruling,
   then `ruling supersede` the rest. Never edit the file by hand. Counted by Opus: 34 machine blocks (`## Ruling R1`-`R34`)
   and 20 hand-written ones (`**R1.**`-`**R19.**` plus "R11, now active"), so numbers 1-19 exist twice. A reader judged
   17 of the 54 standing; the consolidation re-derives that list.
2. **AGENTS.md**, then **CLAUDE.md**: a direct harness run on a disposable clone, proven by a quiz keyed from the old
   file (kept outside the tree) plus one past task replayed. The mandated lines and the expected-values section stay
   verbatim.
3. **Handoff guides**, the **card template** (`docs/tasks/README.md`), then **README.md** last, as a thin router.
4. **Code comments** last of all.

## Exempt (a hash, test or tool reads it)

- Vendored files under `third_party/`, `MANIFEST.sha256`, `third_party/cycles/VENDORED.toml`.
- `CONTRACT:` headers and the 2-line SPDX headers that tests check; `Shim: replaces Cycles <path>` first lines.
- The 12 `// verbatim <file>:<a>-<b>` ranges cited from `src/test/smallpaint_ref.h`: never shift lines in cited files.
- `tests/data/**`, the `LICENSES/` texts (globbed by `pyproject.toml:11`), `THIRD_PARTY_NOTICES.md` rows that pending
  cards edit by quoted substring.
- BACKLOG.md's done and live items (the queue parses `## ID:`, `Card:`, `Depends on:`, one-line `allowedPaths:`).
- Experiments 001-006; any experiment's pre-registered Hypothesis and Method keep their content (format may change if
  no checker reads them byte for byte).
- Numbered references other files cite (`CLAUDE.md` "rule 2" and "rule 7", `src/app/CHANGES.md` item numbers): keep
  the numbers, even as stubs.

## Map: root and core

| path | lines | reader(s) | after reading, the reader must... | verdict | status | note |
|---|---|---|---|---|---|---|
| `README.md` | 45 | owner; Blender users | know what Painterly is, that it is pre-alpha, the `make` commands, credits, licence | cut | editable | Layout (9-29, 47%) is wrong: it lists 10 untracked paths. Keep `## Status` and a one-line `## Layout`: drafts T7.5:86 and T8.2:117 insert text between them, and T8.2:785 checks a link to `docs/install.md`. |
| `AGENTS.md` | 144 | DeepSeek workers (every call), planner, auditors | know the offline environment, scope, git and answer format, expected-values rules | cut | guarded; tool-read (the harness loads it from `--root` on every call) | 79-84 and 87-91 restate CLAUDE.md rules 2-3 on purpose. `(R16)` at :59 is ambiguous (two R16s). |
| `CLAUDE.md` | 112 | Claude steward (auto-loaded); workers via AGENTS.md:20 | apply golden rules 1-6; know DeepSeek implements and Claude specifies, reviews, lands; find commands | cut (on Micah's word) | guarded | Cut the Finish protocol (66-79, replaced by AGENTS.md) and Network notes (81-91, the old container) except the User-Agent row (`tools/fetch_blender.py:80`). Keep numbered rule stubs: "rule 2" is cited 12 times in code, "rule 7" in 14 drafts and `experiments/007…/PLAN.md:316`. Fix :103 (`make check` is `lint build test`, `Makefile:87`). |
| `BACKLOG.md` | 922 | ds-queue planner, workers (their item), steward | choose the item; run CHECK with KNOBS; obey Depends on and allowedPaths | keep items; cut preamble | guarded; tool-read (ds-queue) | 55 items: 18 done, 37 live, 46 lines of preamble. The preamble is stale: KNOBS lacks R11's `-Dembree_DIR`, `Q/` is undefined, the DONE list stops at M3 run 3a. PANEL-a..e are 175 near-identical lines (live, so frozen until they land). |
| `THIRD_PARTY_NOTICES.md` | 12 | packagers, legal, owner | know each bundled component, its licence and upstream | keep until M6a lands | tool-read (`pyproject.toml:11` license-files) | Pending T3.28, T4.2, T6.1, T6.4-T6.8 and T8.1 edit rows by quoted substring. |
| `docs/spec.md` | 320 | everyone | know the normative behaviour | keep | guarded; cited | `SPEC §n` occurs 1,118 times (300 lines in `src/`). |
| `docs/plan.md` | 356 | steward, owner, experiment READMEs | know decisions, milestones, experiments | keep | guarded; cited | 116 cite lines in 56 files; `experiments/001…/README.md` cites "lines 22-51". 144-183 is a self-declared historical copy of the spec (Micah's call). |
| `docs/architecture.md` | 109 | workers (when the task needs it), steward | know layers, prefixes, dependency direction, determinism, isolation | cut | editable; T3.28 pending | Cut 72-86 "Why not fork Cycles?" (cited nowhere; duplicates `plan.md:68-84`). Keep Distribution, Source layout and naming, Dependency direction, Determinism contract (13 cites in code and cmake). |
| `docs/audits/TQ.1.md` | 247 | steward; live cards T3.15, T3.26 | look up finding F<n> | cut | editable | Keep the F1-F28 rows (104-139) and §TQ.1-7 (231-238, read by `T3.26:57`). Cut 46-102, 141-230 (proposed cards, all landed as T3.20-T3.25) and 240-247: -155 lines. |
| `docs/audits/TQ.2.md` | 50 | steward, queue | find F1-F9 and its BACKLOG item | keep | editable | Cited by live BACKLOG items; retire when they land. |
| `docs/tasks/README.md` | 31 | steward (card writer) | write a card in the template | cut | editable | Keep the template (7-21). Cut 3-5 and 23-31: "Haiku agents implement them" is stale since 2026-10-15. Say the queue writes the commit subject. |
| `src/app/CHANGES.md` | 138 | workers and steward editing the oracle | know each deviation from smallpaint | keep | editable; items cited by number | Items 3, 7, 8, 12, 17, 22, 23 are cited 14 times: never renumber. Optional: item 22's "Cause" (109-118) repeats SPEC §4. |
| `tests/data/reference/README.md` | 12 | humans; workers needing provenance | know the reference PPM's source, hash and format | keep | guarded; tool-read (`tests/core/test_third_party_hashes.py:41-46`) | |
| `LICENSES/*.txt` (5) | 475 | packagers, legal | have each licence's full text | keep | exempt (`pyproject.toml:11`) | `Apache-2.0.txt` and `Apache-2.0-embree.txt` are byte-identical; T3.28 keeps both. |
| `.tmp/ds-queue/RULINGS.md` | 430 (44,533 B) | every DeepSeek planner, worker and auditor prompt; steward | follow the standing rulings | consolidate | untracked; tool-read (prepended whole to each prompt, about 11k tokens) | 54 blocks: 20 hand-written (11,136 B) and 34 machine (33,381 B). 17 standing, all hand-written. 37 one-off or spent: all 34 machine blocks plus hand R8, the old R11 and R19. Keep machine R13, R14 and R18-R20 until their tasks land. About 14 KB after consolidation (-68%). Numbers 1-19 exist in both styles. |

Stale statements found in this group (fix while cutting):
1. `README.md:12-28`: 10 listed paths are untracked (`git ls-files` prints nothing). The real ones are
   `src/painterly/<layer>`, `third_party/cycles/VENDORED.toml` and `tests/oracle`.
2. `docs/architecture.md:97`: "exports exactly one symbol". Windows also exports nanobind's exception classes
   (`tools/symbol_audit.py:471`; the fix is queued in T3.28). `:92` cites `tests/core/test_oracle_parity.py`, which T3.16
   creates.
3. `THIRD_PARTY_NOTICES.md:8`: says Embree's third-party files cover only components "we do not build", but SSE2NEON and
   Syrah are compiled in (the fix is queued in T3.28).
4. Ruling numbers: `AGENTS.md:59` "(R16)", `tools/embree_prebuilt.py:158` "(RULINGS R10)" (a tracked file citing an
   untracked one), and the 20 BACKLOG cites each match two RULINGS entries. The consolidated ruling ends this.

## Map: handoff and experiments

No tool or test in the repo parses an experiment README, the experiments index or a handoff doc:
`git grep -n -E 'docs/handoff|experiments/README|## Background|## Conclusion|_planning' -- tests tools analysis src cmake Makefile CMakeLists.txt pyproject.toml .github`
prints only `pyproject.toml:48` (a ruff exclude). The narrative handoff docs were last edited at `c686671`
(2026-10-15), 34 commits ago.

| path | lines | reader(s) | after reading, the reader must... | verdict | status | note |
|---|---|---|---|---|---|---|
| `docs/handoff/README.md` | 102 | steward | find the live sources (BACKLOG, AGENTS.md, RULINGS) and the pitfalls still in force | cut to about 35 | editable | Keep the pointers (3-9), "no `make oracle`", build dirs, D39 and the contents list. Drop the old state (24-43), the Haiku process (45-64) and the container pitfalls (73-87). |
| `docs/handoff/queue.md` | 100 | steward; BACKLOG PANEL items cite §8; TQ.2 cites the chores | know what is still unplanned (M6b, the M7-M9 revisions) and the standing chores | cut to 3-5 plus 88-100 | editable | §1-6 are now BACKLOG items. |
| `docs/handoff/conversation.md` | 61 | none | - | retire | editable | History; its facts live in `docs/plan.md`, the experiments index, T2.11 and firstlight. |
| `docs/handoff/decisions.md` | 30 | steward | apply the owner's scope and preferences | cut to about 15 | editable | Drop rows that repeat `docs/plan.md:11-19`; fix :16 "use Haiku". |
| `docs/handoff/decisions-M3.md` | 166 | steward; workers via code comments | resolve a cited D<n> | cut to about 75 | editable | Keep D14 (amended), D15-17, D19, D33-37, D39 (cited from `src/painterly/scene/`, `test_scene.cpp`, BACKLOG, AMENDMENTS-fixups.md, T3.15); drop the 28 uncited. |
| `docs/handoff/drafts/STATUS.md` | 44 | steward | - | retire | editable | Its one live line ("M6b not drafted") is `queue.md` §7. |
| `docs/handoff/firstlight/README.md` | 110 | steward | cite first light: 18/18 bit-identical, thread and batch invariant, NaN to D33 | cut to about 25 | editable | Names 3 files of a tree that is not committed. T3.16 supersedes it. |
| `docs/handoff/repro/REPRO.md` | 55 | Opus; frozen Amendment 2 of 007-009 | read the five non-identical results | keep | exempt (named by frozen amendments) | Generated; TQ.2 F9 (generator not committed). |
| `docs/handoff/repro/host/README.md` | 91 | steward; workers (R17) | use the host results for exact checks; know the oracle sha | cut §3 (84-91) | editable | |
| `docs/handoff/research/cycles_svm_report.md` | 893 | Opus drafting M6b | extract the SVM and closure facts and the staged plan | keep until M6b is drafted | editable | Then cut §1.1 (68-135) and §4.1-4.7 (423-599), about 245 lines. |
| `docs/handoff/drafts/M3-fixups/T3.19`-`T3.25` (7) | 5,695 | workers (BACKLOG `Card:`) | implement; run Acceptance | keep | live spec (landed) | Landed as `092ff38`, `7fd429a`, `e7166f6`, `1dfd779`, `7c6369b`, `05f5dd8`, `5ba050e`. T3.21's appendix A is cited (`test_bvh.cpp:57`, at a wrong path: TQ.2 F4). |
| `docs/handoff/drafts/M3-fixups/T3.26`-`T3.28` (3) | 2,607 | workers | implement; run Acceptance | keep | live spec (not landed) | Cut only between tasks, never under a running one. |
| `docs/handoff/drafts/M6a/T6.1`-`T6.8` (8) | 14,847 | workers | implement; run Acceptance | keep | live spec (not started) | BACKLOG already notes stale "experiment 007" mentions (T6.3, T6.5). |
| `docs/handoff/drafts/M7-M9/` (10) | 15,191 | PANEL-M7-M9 workers; steward revises | check each finding; edit nothing | keep | under review | Revised after the panel (`docs/handoff/queue.md` §8). |
| `docs/handoff/findings/*.json` (6) | 1,823 | workers (keys BACKLOG names) | check the named keys | keep 4; retire `M3-run3a-panel-disputed.json` | tool-read (the PANEL check commands parse the M7-M9 files) | `panel-confirmed` is read only by `queue.md:18`: retire after T3.27 and T3.28 land. |
| `docs/handoff/workflows/*.js` (6), `firstlight/{render.cpp,CMakeLists.txt}` | 1,213 | none | - | retire | editable | Historical Workflow scripts and an unbuilt scratch driver; nothing references them. |
| `docs/handoff/repro/REPRO.json`, `host/*/results.json` (6) | 238,568 | worker gates; 008 and 009 analyses | compare against them | keep | exempt (compared with `==` and `cmp`) | |
| `docs/handoff/research/*.txt`, `nodes_index.json` (5) | 4,759 | Opus | evidence for the SVM report | keep; retire `case_func.txt` (uncited) | editable | Their generators are not committed. |
| `experiments/README.md` (index) | 62 | Opus; workers add rows | add or update one index row | cut to the table | editable; read by planned T7.5 and T6.3 | Keep the 6 columns (T7.5's `experiment_index()` needs >= 6 cells, cell 0 `\d{3}`; T6.3 inserts after row 006). "How to run" (20-56) repeats `docs/tasks/M1/_experiment_protocol.md` and tells a fresh checkout to `make oracle`, which AGENTS.md forbids. |
| `experiments/001`-`006` READMEs (6) | 2,257 | Opus; tests and spec cite them | cite each final Conclusion | keep | guarded by the queue (`config.json` guardPaths) | All final ("Final (Opus)"). |
| `experiments/007`-`009` READMEs (3) | 2,484 | workers write Results and the DRAFT Conclusion; Opus | implement the Method; edit only Results and Conclusion | keep content; reformat only | pre-registered | Hypothesis and Method keep their content. |
| `experiments/007`-`009` PLAN.md (3) | 1,109 | workers (BACKLOG `Card:`) | implement the helpers and `analyze.py`; run Acceptance | cut about 67 | live spec | Amendment 3 (Opus, 2026-10-18) now overrides their "DRAFT (Haiku)" prefix and background runs. The render and disk steps are moot (done on the host). |
| `experiments/*/_planning/` (7) | 2,021 | Opus (audit trail) | check "first draft" claims the READMEs cite | keep 3 (cited); retire `008/_planning/PLAN.v1.md`, `009/_planning/PLAN.round0.md`; cut `007/_planning/OMITTED.md` to 5 lines | editable | `README.v1.md`, `PLAN.round1.md`, `README.round0.md` and `README.round1.md` are cited by line from the READMEs. |

Stale statements found in this group:
1. `docs/handoff/README.md:29,98`, `drafts/STATUS.md:3-19` and `queue.md:15-44` say the fix-up cards are "drafted, not yet
   reviewed" and "not executable until moved". BACKLOG names them as cards in place, and T3.19-T3.25 have landed.
2. `docs/handoff/README.md:34`, `drafts/STATUS.md:32-43` and `queue.md:92-93` say only T7.1 and T7.2 are reviewed;
   `findings/M7-M9-review-2.json` (`fa06a25`) reviews all ten cards.
3. The oracle sha: `docs/handoff/README.md:69` and `experiments/README.md:25` give `066bb5d4…`. Amendment 1 of 007
   and `repro/host/README.md:14` give `804a2dc2…`.
4. `experiments/00[789]/PLAN.md` ordered "DRAFT (Haiku)" and background runs. Fixed by Amendment 3 on 2026-10-18.

## Map: task cards (docs/tasks/)

63 files, 4,066 lines: 46 done cards (2,971 lines), 13 live cards (754 lines) and 4 notes. Done cards are records: an
auditor tracing a landed commit reads them, and code, experiments and later cards cite many of them by line as the
source of a constant. Live cards are the specification a pending task builds from.

| path | lines | reader(s) | after reading, the reader must... | verdict | status | note |
|---|---|---|---|---|---|---|
| `docs/tasks/README.md` | 31 | steward (card writer) | write a card in the 9-section template | cut 3-4 and 23-31 | editable | Haiku, Workflow and gate-agent text is dead since 2026-10-15. `findings/M3-fixups-reviews.json:74` cites :29 (the text is at 27-28). |
| `M0/` (5), `M1/T1.1`-`T1.16` (16), `M2/` (11), `M3/T3.1`-`T3.13`, `M3/TQ.1-audit.md` (14) | 2,971 | auditors; code and experiment comments | know what a landed commit was specified to do | keep | frozen records | Cited by line as constant sources: `T1.4:25`, `T1.7:22` (the "193" of experiment 002), `T1.8:21`, `T1.2:41-47` and `:79-81`, `T2.4:32`, `T2.9:7,35,76-94` (a test fixture), `T2.10:99`, `T3.2:15-20`. M6a and t-fix327b read `T2.11` and `T3.1`-`T3.3` as rules. `T3.13` is also an edit target of t-fix313a. Uncited: `T1.14`, `T2.6`. |
| `M3/T3.14`-`T3.18`, `M4/T4.1`-`T4.4`, `M5/T5.1`-`T5.4` (13) | 754 | workers, planner, auditors | build exactly the listed files and pass Acceptance | keep; cut each trailing `## Commit` block (3 lines; the queue writes the subject) | live spec (t-m3-14b, t-m3-15b, t-m3-16 to t-m3-18, t-m4-1 to t-m4-4, t-m5-1 to t-m5-4) | Never shift `T3.15:15`, `T4.1:23` or `T4.4:12-16` (cited by line). |
| `M1/_experiment_protocol.md` | 20 | workers (t-m3-18, t-m6a-3), card writers | run an experiment by items 1-9 | keep | live spec; items cited by number | Items 7 and 9 now say "DRAFT (DeepSeek)" and "the queue makes the commit" (2026-10-18). Never renumber. |
| `M1/_phase_b_results.md` | 107 | auditors | know the phase-B results of 002-004 and 006 | keep | frozen record | Only `T1.12:2` cites it. |
| `M3/AMENDMENTS-fixups.md` | 184 | workers, auditors | append an entry per card edit, in its format | keep | live (t-fix313a appends entries 10-11) | Its header (":5 Two sources", ":12 Entry 6 ... only such hunk") turns false when t-fix313a appends: check at landing. |

Problems found in this group:
1. `M1/_experiment_protocol.md` items 7 and 9 said "DRAFT (Haiku)" and "Commit ...". Fixed on 2026-10-18.
2. `M4/T4.1:57` and `M4/T4.4:42` gave Makefile recipes with a literal `.venv/bin/python`; the Makefile uses `$(VENV)` since
   BOOT-0a. Fixed on 2026-10-18 (no line shifted).
3. `M3/T3.17:24` says "shared cache", which R7 and R12 forbid; only t-m3-17's body corrects it.
4. `M3/T3.11:30` (a done record) still says `VERTEX_PASS`; the code has `VERTEX_TINT` (`kernel/integrator/path.h:33`).
