# Opus's rulings on the M7-M9 panels (2026-10-23)

The REVISE-M7-a, -b, -c, REVISE-M8 and REVISE-M9 items of BACKLOG.md apply these rulings to the drafts in
`docs/handoff/drafts/M7-M9/`.

Inputs, all in `docs/handoff/findings/`:
- the five panel files `M7-M9-panel-{T7.1,T7.2,T7.3-T7.5,M8,M9}.json` (89 verdicts, each with its `fix`);
- Sonnet's checks of them, `M7-M9-panel-check-{M7a,M7b,M8,M9}.json`: one object per panel object, in the panel files'
  order, with `check`, `ruling` (apply | change | none | opus), `change` (prose) and `reason`;
- this file.

## How to apply them, per card
1. `apply`: the panel object's `fix` as written (old text to new text). M9's fixes name no file; the file is the
   finding's card.
2. `change`: the edit that the check's `change` describes. It replaces the panel's fix; write the text yourself.
3. `none`: no edit.
4. `opus`: the ruling in this file.
5. A duplicate is applied once. Where the check resolves an overlap between two edits, follow it.
6. Then the cross-cutting rulings and the card's own section below.
Nothing else changes. If a ruling contradicts the draft in a way this file doesn't settle, call report_blocked and
name both.

## Cross-cutting
- **X1. Card text stays queue-agnostic.** A card names the repository's own targets and paths (`build/dev`, `make
  check`, MAIN's tools). The queue's translation (`build/q`, `PYTHONPATH`, R-numbers, "host-only", AGENTS.md
  procedure) lives in BACKLOG items and RULINGS (R2, R12), never in a card. A panel fix whose only change is that
  translation is not applied; where a fix also corrects a real defect, only that part is applied. Found by Sonnet in
  six M7b fixes (T7.3 exec#0, #1; T7.4 exec#0, #2; T7.5 exec#1, #2), and the same pattern is in the T7.1, M8 and M9
  panels.
- **X2. "DRAFT (Haiku)" becomes "DRAFT (DeepSeek) — pending Opus review."** AGENTS.md:131 sets the wording since
  2026-10-15. Six places: T7.3 (1), T7.4 (2), T9.2 (1), T9.3 (2). Not a panel object; a mechanical edit in each
  revision item.
- **J1. Jitter's soft limits and the presets' jitter.** EXP-008 (`experiments/008-2026-10-15-jitter-dose-response`,
  README :472) hands both choices to T7.1 and T7.2 and sets neither. T7.1 defers the range (draft :90-91), and T7.2's
  Case B becomes a stop (T7.2 exec#1). So Opus chooses both from 008's tables when finalizing its Conclusion (plan row
  X.concl), and amends T7.2 before it runs; T7.2 then owns both. Until then the revised T7.1 keeps the range deferred,
  and the revised T7.2 keeps jitter at its socket default.
- **Cross-card ripples** (each goes into the later card's revision):
  - C1. T7.1 design#11 rewrites `lane_length`'s tooltip; T7.3 inserts "unless Lane Stagger shifts them" into the new
    text instead of appending it (T7.3:180, :183-184, :1113-1117).
  - C2. T7.1 exec#4: T7.1's "Rule for later cards" names `EXPECTED_UI_TEXT`; T7.3 updates it for its new socket.
  - C3. T7.2 drops the Soft strokes preset (design#1); T7.5 follows (T7.5:230-231, :2167, :2275-2278).
  - C4. The M9 ruling on T9.1 design#0 adds `RESEARCH_SOCKETS` to T7.1 and its exemption to T7.5.
  - Already applied to the live cards on 2026-10-23 (cfa8556): T4.4 reads `bl_idname` with `getattr` (T7.1 exec#3's
    probe), and T5.3 reads `get_output_node('CYCLES')` (T7.1 design#6's probe).

## M7a (T7.1, T7.2): Sonnet 39 objects, apply 14, change 18, none 7, opus 0
- No opus items. Apply the check file as it stands, and C4 to T7.1.
- T7.2's eleven overlapping pairs: the check's resolutions hold (exec#1 wins over exec#0's template lines and part of
  design#2; design#0 over review-2 design#0; design#1 over design#7's Soft comment; exec#2 over review-2 exec#0 with
  four paths; design#6 and review-2 design#2 merge into one sentence).

## M7b (T7.3-T7.5): Sonnet 16 objects, apply 1, change 6, none 8, opus 1
- **T7.3 design#1 (opus): a refuted H1.** Sonnet's option 2. If H1 is refuted, H2 and H3 are inconclusive: both are
  read on R1, the regions where H1 rejects (T7.3:452-458, :474-476), and on H1's statistic. The report then says that
  003's seam-column finding did not replicate on the native path. H4 stays as registered, because it has its own
  positive control (`lane16_s0` against `row` on T, T7.3:491-494). Add this as one outcome bullet under "What each
  outcome means"; no other rule changes. This is an R4 amendment of a pre-registration that has not run.
- **T7.4 design#2 (apply): rule R(a) stays as pre-registered.** Its bootstrap is fully specified (99% percentile,
  `BOOTSTRAP_RESAMPLES = 10_000`, `jax.random.PRNGKey(0)` folded with the configuration's index, T7.4:210-212). It can
  only make the decision stricter than the Holm tests of (b) and (c). ensemble.py's having no bootstrap procedure is not
  a defect: the card's own analyze.py implements it (T7.4:371-372).

## M8 (T8.1, T8.2): Sonnet 14 objects, apply 3, change 8, opus 3
- **T8.1 design#0 (opus): D39, the `install` job's macos-14 leg.** Option 1: drop the leg. The macOS zip is still
  built and byte-verified in `package`. The matrix test compares against a named `INSTALL_PLATFORMS` subset (linux,
  windows), not `set(RELEASE_PLATFORMS)`. The CI block says install is green on Linux and Windows. Also:
  - No heading edit for the CI block (X1). T8.1:742 already says the orchestrator runs it.
  - T8.1's local Blender bullets (:725-730, :700-701) follow the T8.2 exec#1 ruling below. The substitute named for a
    run without Blender is the three fast test files (:723-724) and the fast command-line block (:732-739).
  - NEW (Sonnet): Step 1 (:199-211) is stale. wheels.yml has seven `pull_request.paths` and a comment since 84fced7
    (T3.28). Step 1 replaces only the `push: tags: ["v*"]` trigger with `workflow_call:` and leaves `workflow_dispatch`
    and the whole `pull_request` block byte for byte. Step 5's trigger-set test still holds.
- **T8.2 exec#1 (opus): where the slow tests find Blender.** Option A. The slow tests of T8.2
  (`test_repo_index_client.py`) and T8.1 (`test_release_package.py`) take Blender from the `BLENDER` environment
  variable (the Makefile exports it, Makefile:12-13), and skip only when it is unset. The pytest bullets run without
  `make blender &&`, and "none skipped" stays checkable; the queue's verify sets BLENDER (f3f82c2). Per X1, no
  "host-only" marker. The panel's substitute bullet is wrong under either option: `tests/core/test_repo_index.py` never
  runs `server-generate` (T8.2:757-764), so the card must not say it exercises `generate` without Blender.
- **T8.2 design#0 (opus): static.yml and the release's Pages job.**
  - The problem (Sonnet, new): `.github/workflows/static.yml` (8c91752, the owner's, 2026-10-22) deploys the repo root
    to the same Pages site on every branch push, in the same `pages` concurrency group, so either deployment wipes the
    other's files (index.json would 404 until the next release).
  - Ruling: option (b), with static.yml as the only Pages publisher. T8.2 lists static.yml under Modify. static.yml
    gains `workflow_call:` and the release workflow calls it after the release's assets are uploaded, instead of
    deploying a Pages job of its own. Every deployment, from a branch push or from a release, carries the repository
    tree plus the latest release's index and archives, fetched with the workflow's own token. Before the first release
    there are none, and that is not an error. static.yml keeps serving the repo tree, which the owner uses for figure links. The actions are
    pinned to static.yml's versions (`deploy-pages@v5`, `configure-pages@v5`), and Step 3's test pins the same.
  - Not (a): it removes the owner's workflow. Not (c): it changes docs/plan.md's Distribution.
  - T8.2 exec#3 (apply) keeps its owner-setting bullets; its "`pages` run" becomes the Pages deployment run that the
    release starts through static.yml.
  - The post-deploy check: option (i), no new step. The owner's `curl` equality check (T8.2:906-908) stays the
    evidence, and M8.12 installs from the Pages URL. The panel's step has a `set -e` bug and hand-picked attempts and
    sleep.

## M9 (T9.1-T9.3): Sonnet 20 objects, apply 6, change 9, opus 5
- **T9.1 exec#0 (opus): how the kernel gets world triangles again.** Option B. D35 stands: no `tfm`, `itfm` or
  object-space `tri_vertices` come back. `device_update` builds one array of world-space triangles (9 doubles per
  triangle, since decision 7 makes both candidates double precision; indexed `tri_offset + prim`) from `PainterlyMesh` and
  `PainterlyObject::object_to_world`, only when `mesh_ghost` is `angular_dilation` or `sdf_step`, so `off` keeps HEAD's
  layout and memory. The bounding spheres are computed on the host from the vertices the triangles reference.
  - Not A: it reverses D35 for every scene.
  - Not C: `painterly/bvh/` is on the card's do-not-touch list, and kernel Embree calls belong in kernel/bvh/bvh.h only.
  - The panel's guard idea carries over: both Step 5 loops guarded by `mesh.num_tris > 0`. A triangle-free object
    keeps the empty sphere (centre 0, radius 0). The blocks are written against HEAD's `device_update`: they work on
    the `new_*` locals after `integrator.device_update(new_data.integrator)` and before the single commit.
  - The card's "Contract change (Opus, before dispatch)" section is rewritten to match. Under today's rules a DeepSeek
    item applies it, with the BACKLOG item naming the contract file; Opus reviews it.
- **T9.1 design#0 (opus): showing the research socket.** Option 2, gate it.
  - plan.md (M9) puts exposing mesh ghosting after the experiments' go/no-go.
  - The pilot cost of `angular_dilation` (55 min per 400 px x 64-pass render on 4 threads, T9.2:31-32) would be a trap
    in an artist's dropdown.
  - The mechanism: T7.1 defines a named tuple `RESEARCH_SOCKETS`, empty, of sockets the panels don't draw, with a test;
    T7.5's `expected_knob_headings` exempts the same tuple; T9.1 adds `mesh_ghost` to it.
  - T4.2 still generates the Blender property, so the experiments and scripts set it. T9.1's Goal (:18-19), decision 8,
    Step 9, Appendix E and the Acceptance change to match. T9.2's decision 6 stands: a later card exposes it.
- **T9.2 design#1 (opus): cost in the decision.** Options 1 and 3, with no threshold:
  - "What each outcome means" says that `go` means the candidate reproduces the ghost within the meshing floor, not
    that it is affordable, and the measured cost ratio is quoted for every go candidate.
  - Among go candidates whose pairwise rho-difference interval contains 0 (:380-383), the cheaper one is recommended.
  - Not option 2: no budget in the tree has a source.
  - Combined with design#0 as Sonnet says: the shape bullet goes first, and the ordering bullet follows the go bullet.
- **T9.3 exec#1 (opus): the Blender half.** Option A, split.
  - T9.3 keeps the native path: H1-H5 and H7. The four `blender_*` configurations are the last four of DESIGN, so no
    other seed moves. The counts and `check_jobs`' seeds are recomputed by the script, not by hand.
  - A new card T9.3b holds H6: Appendices D-F, render.py's Blender hook, its own pre-registration and smoke run. It
    depends on T9.3.
  - In T9.3b, Appendix D's engine set reads `getattr(cls, "bl_idname", None)` and skips classes without one. Sonnet's
    probe on Blender 5.2.2 shows `HydraRenderEngine` has no `bl_idname`, so the current line raises.
  - The panel's one-sentence edit is not applied alone.
  - New plan row and BACKLOG item for T9.3b.
- **T9.3 design#1 (opus): H7b.** Option 1, a measurement with no reading and no threshold. It reports r4.luma and
  r3.luma per unit world and the matching world with its 99% interval (Appendix G :2628-2642). The Conclusion quotes
  them, and the guide row (:523) gives the numbers. Whether the world needs a scale is a separate product decision
  (Opus, later). The panel's circular reading and "far from 1" are dropped.
