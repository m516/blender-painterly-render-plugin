export const meta = {
  name: 'prereg-007-009-verify',
  description: 'Second-round adversarial verification of the revised 007-009 pre-registrations (design validity and executability, two skeptics each), a cross-experiment consistency check, then a fix pass until dry',
  phases: [
    { title: 'Verify', detail: 'two skeptics per experiment' },
    { title: 'Cross-check', detail: 'blocks, cache, oracle, numbering, shared code' },
    { title: 'Fix', detail: 'author applies verified findings; loop until dry' },
  ],
}

const REPO = '/home/user/blender-painterly-render-plugin'
const SP = '/tmp/claude-0/-home-user-blender-painterly-render-plugin/98b29052-844f-5778-93d6-f67301038886/scratchpad'
const PR = `${SP}/prereg`
const EXPS = ['007', '008', '009']

const COMMON = `Painterly project at ${REPO} (read-only for you). Pre-registration drafts for experiments 007-009 live in ${PR}/<nnn>/ (README.md with Background, Hypothesis, Method filled and Results/Conclusion pending; PLAN.md, the analysis/render plan the Haiku card will follow; jobs.py where renders are needed; _planning/ with power and synthetic computations). They are oracle-only follow-ups of experiment 006 (${REPO}/experiments/006-2026-10-09-jitter-units/README.md: read its final Conclusion and the binding lessons it states). Protocol: ${REPO}/docs/tasks/M1/_experiment_protocol.md, ${REPO}/experiments/README.md, CLAUDE.md "Experiments" and rule 2 (no hand-picked thresholds; statistics only via analysis/painterly_analysis/ensemble.py criteria or explicitly derived rules). Renders use the experiments' oracle in .cache/oracle-build (pre-T3.4 binary, sha256 066bb5d4...; its render cache under .cache/renders is keyed by it; NEVER run make oracle), PAINTERLY_BUILD_DIR=.cache/oracle-build. Experiments are numbered and dated in the order they run. Write nothing in ${REPO}; you may run read-only commands and small computations in ${SP}/prereg-verify/.`

const VERDICT = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: { severity: { type: 'string', enum: ['blocker', 'major', 'minor'] }, section: { type: 'string' }, issue: { type: 'string' }, evidence: { type: 'string' }, fix: { type: 'string' } }, required: ['severity', 'section', 'issue', 'evidence', 'fix'] } } }, required: ['findings'] }
const ISSUES = { type: 'object', properties: { issues: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, problem: { type: 'string' }, fix: { type: 'string' } }, required: ['file', 'problem', 'fix'] } } }, required: ['issues'] }

const LENSES = [
  { key: 'design-validity', ask: 'Design validity. For every hypothesis: is its derivation stated; does each decision rule separate the competing readings it claims to separate (simulate the readings through the exact pipeline where the README gives synthetic models — do not trust its numbers, recompute at least the key ones); is every outcome reachable; are effect statistics used alongside complete-separation tests; are noise floors handled; are the replicates independent (seeds, blocks, no reuse that creates dependence between compared ensembles); are units named; any degenerate contrast of the kind 006 amendment 1 fixed (e.g. deterministic renders treated as replicates)? Also: is anything decided by a hand-picked threshold?' },
  { key: 'executability', ask: 'Executability. Could a literal Haiku agent run PLAN.md exactly: every path, function (check analysis/painterly_analysis for each name used), CLI flag of the oracle in .cache/oracle-build (pre-T3.4: it has NO --diffuse-gain/--emission-gain/--ray-epsilon/--max-depth; check with its usage text), job definition (run jobs.py imports read-only to list ensembles where possible), budget and disk numbers, smoke command, and acceptance check? Are the CPU estimates consistent with cached meta.json wall_seconds? Are reused cached renders really present (done markers) and keyed as claimed?' },
]

phase('Verify')
const verified = await pipeline(
  EXPS,
  n => parallel(LENSES.map(l => () => agent(`${COMMON}

Independent skeptic for experiment ${n} (${PR}/${n}/). Lens: ${l.key}. ${l.ask} Report only real problems with evidence and a concrete fix. A finding that the previous review round already raised and the revision fixed is not a finding.`, { label: `verify ${n} ${l.key}`, phase: 'Verify', schema: VERDICT }))).then(rs => ({ n, findings: rs.filter(Boolean).flatMap(r => r.findings) })),
)

phase('Cross-check')
const cross = await agent(`${COMMON}

Cross-experiment checker. Read all three drafts. Check: disjoint seed blocks and render directories between 008 and 009 and against every block used by experiments 001-006 (read their jobs.py); identical oracle binary and cache usage; consistent numbering assumptions (007 re-analysis runs first? state the run order the drafts assume and whether dates/numbers follow "numbered and dated in the order they run"); shared code they each plan to add to analysis/painterly_analysis (no conflicting definitions of the same function/constant; one owner); consistent vocabulary (chain, lane, pass, K, f as jitter fraction of the image side, px/ip frames); combined CPU and disk budget on this 4-core machine. Report issues with file and replacement text.`, { label: 'cross-check', phase: 'Cross-check', schema: ISSUES })

phase('Fix')
const all = verified.filter(Boolean)
const fixed = await parallel(all.map(v => () => (v.findings.length === 0 && !(cross && cross.issues.some(i => i.file.includes(`/${v.n}/`)))) ? Promise.resolve({ n: v.n, report: 'no findings' }) :
  agent(`${COMMON}

Files are writable in this run (2026-10-15): edit them. An earlier pass of this stage ran read-only by mistake and only proposed edits; its proposals (readonly_fix_proposals, entry n = ${v.n}) and the read-only final recheck's issues (readonly_final_recheck_issues; apply those that touch your experiment) are in ${SP}/prereg-verify/readonly-pass.json. Reuse them after re-verifying. Opus rules for this pass: (1) DATES: an experiment directory takes the date of the Opus commit that creates it with the pre-registration; write directory names, command paths and index rows with the placeholder <DATE> (= $(date +%F) on that commit day, 2026-10-15 or later) instead of 2026-10-09; numbers follow run order 007, 008, 009. (2) DISK: the orchestrator frees disk before rendering; state required bytes and record free space only as a measurement with its date. (3) Every interval that enters a decision is 99% (CI (0.5, 99.5)) unless the README derives otherwise. (4) Never run make oracle; say so in PLAN and README Method if missing.

You are the author of experiment ${v.n}'s pre-registration (${PR}/${v.n}/). Second-round skeptics found: ${JSON.stringify(v.findings)}. Cross-experiment issues touching your files: ${JSON.stringify((cross && cross.issues || []).filter(i => i.file.includes(`/${v.n}/`)))}. Verify each by recomputation or by reading the code; apply the correct ones to README.md / PLAN.md / jobs.py / _planning; reject wrong ones with a one-line reason. Keep the README's five-section structure (Results and Conclusion pending). Record in the README's Method, under the existing amendments/review notes, a dated line "Second review round (2026-10-10): applied N, rejected M" with the list. Return applied/rejected.`, { label: `fix ${v.n}`, phase: 'Fix' }).then(r => ({ n: v.n, report: r }))))

const recheck = await agent(`${COMMON}

Final read-only check after the (writable, 2026-10-15) fix pass. For each of 007, 008, 009: list any remaining blocker or major problem (design validity or executability), with evidence. Also confirm that each README keeps exactly the sections Background, Hypothesis, Method, Results, Conclusion, that hypotheses state how they were derived, and that the three drafts are mutually consistent (blocks, oracle, code ownership).`, { label: 'final recheck', phase: 'Fix', schema: ISSUES })

return { verified: all.map(v => ({ n: v.n, n_findings: v.findings.length, findings: v.findings })), cross, fixed, recheck }