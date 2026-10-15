export const meta = {
  name: 'm7-m9-cards',
  description: 'Draft M7 (artist experience), M8 (release) and M9 (research) task cards against the committed contracts and M3-M5 cards, review each adversarially, revise, cross-check the set',
  phases: [
    { title: 'Draft', detail: 'one Opus drafter per card' },
    { title: 'Review', detail: 'executability and design lenses' },
    { title: 'Revise', detail: 'drafter applies confirmed findings' },
    { title: 'Cross-check', detail: 'set-level consistency' },
  ],
}

const REPO = '/home/user/blender-painterly-render-plugin'
const SP = '/tmp/claude-0/-home-user-blender-painterly-render-plugin/98b29052-844f-5778-93d6-f67301038886/scratchpad'
const OUT = `${SP}/cards/M7-M9`

const COMMON = `Repository: ${REPO} (read-only for you; write only under ${OUT}/). Read: CLAUDE.md, docs/architecture.md, docs/spec.md, docs/plan.md (M7, M8, M9 rows and the experiments programme), docs/tasks/README.md (card template), all cards in docs/tasks/M3, M4 and M5 (the add-on, properties generated from integrator_sockets(), presets, sync), the contracts src/painterly/kernel/types.h and globals.h and src/blender/_painterly.pyi, experiments/README.md and the final Conclusions of experiments 002, 003 and 006. Write cards in the voice and precision of docs/tasks/M3/T3.13-scene.md and M4/T4.2-properties-ui.md. Cards are executed literally by Haiku agents after M3, M4 and M5 have landed exactly as their cards describe: every path, target, name, socket, command and acceptance criterion must be explicit, executable within the card's own Create/Modify scope, and free of hand-picked tolerances (CLAUDE.md rule 2). Every knob default is a PainterlyIntegrator socket (single source of truth); presets and operators never change scene lights or the view transform implicitly (SPEC §6, §8). Experiments follow docs/tasks/M1/_experiment_protocol.md; their numbers are assigned at run time as the next free number (never hard-code one), and their hypotheses must respect the lessons of 006's final Conclusion (independent replicates, separating contrasts, noise floors, effect statistics alongside complete-separation tests, units named).`

const CARDS = [
  { id: 'T7.1', slug: 'panels-and-overrides', brief: 'Artist UI: regroup the generated panels into Sampling / Brush / Lights / Path / Film with clear labels and descriptions from the socket UI info; light overrides (light.painterly: ghost toggle per light, honoured by T5.3 as `settings.ghost_lights and light.painterly.ghost`) and material/world painterly panels where they exist; a panel-registry test in blender -b.' },
  { id: 'T7.2', slug: 'presets', brief: 'Presets: "Smallpaint Reference" (exists from T4.2; verify), "Showcase (approx.)", "Fine strokes", "Broad strokes", "Soft strokes". Every preset value is cited to an experiment result (002 alpha and emitter continuation, 003 lane length, 006/008 jitter: read experiments/README.md and, for 008, its Conclusion when it exists; if 008 is not final when the card runs, the card says which values stay at defaults). Presets set only integrator sockets (and reference_scene where documented); a round-trip test.' },
  { id: 'T7.3', slug: 'lane-stagger', brief: 'A `lane_stagger` knob proposed by SPEC §3 and 003: a deterministic per-row offset of the lane grid that breaks the aligned seam columns of chain=lane. Opus decision for the card: offset_row = (row * lane_stagger) mod lane_length, integer socket default 0 (current behaviour, bit-identical), kernel change in painterly/kernel/sample/sampler.h chain mapping and the scheduler (painterly/integrator), oracle parity untouched for lane_stagger = 0, determinism across threads/batches kept; an SPEC §3 amendment drafted for Opus (write the proposed text in the card under "SPEC change (Opus)", do not edit the SPEC). Plus a pre-registered experiment card section (number at run time) measuring seam-column amplitude with and without stagger using the native core via _painterly.Session.' },
  { id: 'T7.4', slug: 'exp-animation', brief: 'Pre-registered experiment (number at run time): the look under camera motion. Policies: seed_per_frame on/off x spiral_frame camera/world. Observable: temporal stability of the converged texture on static surfaces (frame-to-frame structure correlation of reprojected static regions) and flicker; renders through Blender (M4/M5) of a generated animation of the reference scene with a slowly moving camera. Decide the defaults of seed_per_frame and spiral_frame for animation from the result; state how the decision maps to defaults without hand-picked thresholds.' },
  { id: 'T7.5', slug: 'artist-guide', brief: 'docs/artist-guide.md: what each knob does, with imagery generated from experiment renders and the native core (a script that regenerates every figure deterministically, figures <= 1 MB), the units (jitter as a fraction of the image side), the Blender-default-light warning (1000 W clips), presets, and the known limits (200 px previews, edge aliasing at small jitter). Opus reviews the prose; the card defines structure, figure list and generation script.' },
  { id: 'T8.1', slug: 'release-workflow', brief: 'Release on a tag v*: build the three wheels (wheels.yml reuse via workflow_call or artifacts), `blender --command extension build --split-platforms` with the wheels listed in blender_manifest.toml, upload per-platform extension zips and a GPL source tarball (the exact tree including third_party/ and LICENSES/) to a GitHub Release, and a dry-run mode for a non-release tag. Read the Blender 5.2 extension docs (manifest wheels, platforms) from the GitHub mirror or docs.blender.org if reachable; verify names.' },
  { id: 'T8.2', slug: 'repository-index-and-install-docs', brief: 'Self-hosted remote repository: `blender --command extension server-generate` producing index.json with absolute archive URLs to the GitHub Release assets, published on GitHub Pages by a workflow; docs/install.md (add the remote repository in Preferences, update flow, platform notes); a test that the generated index.json validates and lists every platform zip.' },
  { id: 'T9.1', slug: 'mesh-ghost-candidates', brief: 'Research support in the native core: an enum socket `mesh_ghost` {off (default, bit-identical), bounding_sphere, homothety, angular_dilation, sdf_step} implementing the four candidate generalizations of ghosting to triangle meshes from docs/plan.md (X-mesh-ghost): bounding-sphere proxy of each mesh object with the a=1 quadratic; L^2-homothety of hit points about the ray origin; angular dilation of the hit cone by acos(1/L); unnormalized SDF stepping. Define each mathematically from SPEC §5 (ghost sphere centre o + L^2(c - o), radius L*sqrt((L^2-1)|o-c|^2 + r^2)), kernel placement (painterly/kernel/geom/), tests that on an analytic sphere the definition of each candidate reduces to the analytic ghost where it should (exact or with a derived round-off bound), and no effect when off.' },
  { id: 'T9.2', slug: 'exp-mesh-ghost', brief: 'Pre-registered experiment (number at run time): score the four mesh-ghost candidates against analytic ghost spheres on UV-sphere meshes in the reference scene (native core, _painterly.Session), on realization_free_key_family plus region means, with the analytic-ghost ensemble as the reference and the no-ghost mesh as a negative control; decide which candidate (if any) becomes an artist option (go/no-go rule stated in advance, effect-size based, no hand-picked threshold).' },
  { id: 'T9.3', slug: 'exp-open-scenes', brief: 'Pre-registered experiment (number at run time): the look outside the closed box: misses to the world (constant background), mesh-only scenes with lights-only ghosting, and a large scene; questions: does the texture survive when many paths escape (K consumption per pixel drops), how does the back-wall-like amplification depend on enclosure; measured with the native core and Blender scenes generated by a script; outputs inform the artist guide and defaults.' },
]
const REVIEW_SCHEMA = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: { severity: { type: 'string', enum: ['blocker', 'major', 'minor'] }, issue: { type: 'string' }, evidence: { type: 'string' }, fix: { type: 'string' } }, required: ['severity', 'issue', 'evidence', 'fix'] } } }, required: ['findings'] }
const ISSUES = { type: 'object', properties: { issues: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, problem: { type: 'string' }, fix: { type: 'string' } }, required: ['file', 'problem', 'fix'] } } }, required: ['issues'] }
const LENSES = [
  { key: 'executability', ask: 'As a literal-minded Haiku implementer running after M3-M5 landed as their cards describe: is every file, target, socket, property, operator, workflow job and test this card uses created by it or by an earlier card? Is every acceptance criterion executable within scope, deterministic, free of hand-picked tolerances? Are external facts (Blender extension CLI, manifest fields, GitHub Actions syntax) stated precisely and verifiable?' },
  { key: 'design', ask: 'Does the card serve the project goal (preserve the painterly look and make it accessible to artists) and respect SPEC, the single-source knob rule, the layout and naming rules, and (for experiments) the protocol and 006 lessons? Are kernel changes bit-identical when off? Are units and decision rules explicit? Flag scope creep and missing pieces.' },
]

phase('Draft')
const cards = await pipeline(
  CARDS,
  c => agent(`${COMMON}

You are the Opus author of card ${c.id}. Brief: ${c.brief}
Write ${OUT}/${c.id}-${c.slug}.md following the card template. Return a summary: what it creates and the interfaces later cards rely on.`, { label: `draft ${c.id}`, phase: 'Draft' }),
  (s, c) => parallel(LENSES.map(l => () => agent(`${COMMON}

Read-only adversarial reviewer of ${OUT}/${c.id}-${c.slug}.md. Lens: ${l.key}. ${l.ask} Report only real problems with concrete fixes.`, { label: `review ${c.id} ${l.key}`, phase: 'Review', schema: REVIEW_SCHEMA }))).then(rs => ({ c, findings: rs.filter(Boolean).flatMap(r => r.findings) })),
  r => agent(`${COMMON}

You are the author of ${OUT}/${r.c.id}-${r.c.slug}.md. Reviewers found: ${JSON.stringify(r.findings)}. Verify each; apply the correct ones; give a one-line reason for each rejected one. Rewrite the card in place. Return applied/rejected and the final interface summary.`, { label: `revise ${r.c.id}`, phase: 'Revise' }).then(rev => ({ id: r.c.id, n_findings: r.findings.length, revision: rev })),
)

phase('Cross-check')
let residual = []
for (let round = 1; round <= 3; round++) {
  const res = await agent(`${COMMON}

Read-only cross-checker, round ${round}. Read all cards in ${OUT}/ in order (${CARDS.map(c => c.id).join(', ')}). Check cross-card consistency (names, sockets, files, workflows, ownership, ordering), consistency with M3-M5 cards and contracts, and the experiment rules. Report only real issues with the card file and replacement text.`, { label: `cross-check ${round}`, phase: 'Cross-check', schema: ISSUES })
  residual = (res && res.issues) || []
  log(`cross-check round ${round}: ${residual.length}`)
  if (residual.length === 0) break
  await agent(`${COMMON}

You are the M7-M9 card editor. Fix exactly these issues in ${OUT}/: ${JSON.stringify(residual)}. Report what changed.`, { label: `cross-fix ${round}`, phase: 'Cross-check' })
}
return { cards, residual_after_loop: residual }
