export const meta = {
  name: 'milestone-panel',
  description: 'Implement task cards sequentially (Haiku implementer + independent Haiku gate, one retry; Opus cards supported), then a multi-lens Opus review panel with adversarial verification of every finding',
  phases: [
    { title: 'Implement', detail: 'one implementer per card, sequential in the main tree' },
    { title: 'Gate', detail: 'independent gate re-runs the acceptance commands' },
    { title: 'Review panel', detail: 'parallel Opus lenses' },
    { title: 'Verify findings', detail: 'two skeptics per finding; majority keeps it' },
  ],
}

// args: { milestone, base_commit, cards: [{id, path, note?, model?, continue_on_fail?}], skip?: [ids already done],
//         lenses: [{key, focus}], review_context }
const REPO = '/home/user/blender-painterly-render-plugin'
const CARDS = args.cards
const SKIP = new Set(args.skip || [])

const GATE_SCHEMA = {
  type: 'object',
  properties: {
    passed: { type: 'boolean', description: 'true only if a commit for the card exists, the tree is clean, every acceptance command passed, and no out-of-scope files were changed' },
    commits: { type: 'array', items: { type: 'string' } },
    tree_clean: { type: 'boolean' },
    acceptance: { type: 'array', items: { type: 'object', properties: { command: { type: 'string' }, passed: { type: 'boolean' }, key_output: { type: 'string' } }, required: ['command', 'passed', 'key_output'] } },
    out_of_scope_files: { type: 'array', items: { type: 'string' } },
    reported_values: { type: 'string' },
    problems: { type: 'array', items: { type: 'string' } },
    card_defect: { type: 'boolean', description: 'true if the failure is caused by the card itself (an acceptance criterion that cannot pass within the card scope, or a contradiction), not by the implementation' },
  },
  required: ['passed', 'commits', 'tree_clean', 'acceptance', 'out_of_scope_files', 'reported_values', 'problems', 'card_defect'],
}
const FINDINGS_SCHEMA = {
  type: 'object',
  properties: {
    findings: { type: 'array', items: { type: 'object', properties: {
      severity: { type: 'string', enum: ['blocker', 'major', 'minor', 'nit'] },
      file: { type: 'string' }, line: { type: 'string' }, issue: { type: 'string' }, evidence: { type: 'string' },
      fix: { type: 'string', description: 'concrete fix, precise enough to become a Haiku fix-up card' } },
      required: ['severity', 'file', 'line', 'issue', 'evidence', 'fix'] } },
    observed_numbers: { type: 'string' },
  },
  required: ['findings', 'observed_numbers'],
}
const VERDICT_SCHEMA = { type: 'object', properties: { refuted: { type: 'boolean' }, reason: { type: 'string' } }, required: ['refuted', 'reason'] }

function implPrompt(card, attempt, feedback) {
  let p = `You are an implementation agent on the Painterly project. Repository: ${REPO} (git, branch claude/clever-johnson-gnso1s). Work only inside the repository (plus .cache/ inside it for downloads).

Your task card: ${REPO}/${card.path}
${card.note ? '\nORCHESTRATOR NOTE FOR THIS RUN (overrides the card where they conflict):\n' + card.note + '\n' : ''}
Procedure:
0. Run git status first: uncommitted files for this card may exist from an interrupted earlier attempt — inspect them and complete/correct them rather than starting over. If a commit whose subject starts with "${card.id}:" already exists after ${args.base_commit}, verify it against the card instead of redoing it, and fix forward if needed.
1. Read ${REPO}/CLAUDE.md (binding rules, including "Network notes" and the source layout and naming rules), then ${REPO}/docs/architecture.md, then your task card, then every file the card lists under "Read first". docs/spec.md is normative.
2. Implement exactly what the card specifies — no more, no less. Keep names, paths, CLI flags and signatures exactly as written.
3. Run every command in the card's "Acceptance" section from the repo root and iterate until all pass. Never weaken a test or acceptance criterion to make it pass; if the card is wrong or impossible, stop and explain in your report.
4. Commit per CLAUDE.md "Finish protocol" (subject "${card.id}: <card title>", body, and the trailer lines; name the model you actually run as). git add only the files your card covers. NEVER run git push or any other remote-changing command.
5. Final message = report: files changed, each acceptance command with pass/fail and key output lines, all values the card asks you to report, and any deviation from the card.`
  if (attempt > 1) {
    p += `

THIS IS A RETRY. An independent gate checked the previous attempt and it FAILED. Gate report (JSON):
${feedback}

Inspect the current state first (git log --oneline -8, git status). Fix every problem the gate reported. If a commit for ${card.id} already exists, fix forward with an additional commit whose subject is "${card.id}: fix gate findings". Then re-run all acceptance commands.`
  }
  return p
}

function gatePrompt(card) {
  return `You are an independent GATE agent for the Painterly project at ${REPO}. You verify; you never modify, create or delete tracked files (running builds/tests that write into build/, .venv/ or .cache/ is fine).

Task card under verification: ${REPO}/${card.path} (id ${card.id}). Rules: ${REPO}/CLAUDE.md and ${REPO}/docs/architecture.md.${card.note ? '\n\nORCHESTRATOR NOTE FOR THIS RUN (defines what to verify where it conflicts with the card):\n' + card.note : ''}

Steps:
1. git -C ${REPO} log --format='%h %s' ${args.base_commit}..HEAD — identify the commit(s) whose subject starts with "${card.id}:".
2. git -C ${REPO} status --porcelain — the tree must be clean (ignored files are fine).
3. Run every command in the card's "Acceptance" section exactly, from the repo root. For items that ask the implementer to "report" values, measure them yourself and put them in reported_values.
4. Scope check: list files changed by this card's commits (git show --stat --format= <hash>) and flag any not covered by the card's Create/Modify lists (uv.lock and files the card explicitly allows are fine).
5. Also check the layout and naming rules (src/painterly/<layer>/, shims only in src/cycles/shim/, Painterly/KernelPainterly/painterly_ prefixes) for the files this card created.
6. Return the structured result. passed=true only if a commit exists, the tree is clean, every acceptance command passed, and there are no out-of-scope files. Set card_defect=true when the failure is the card's fault, not the implementation's.`
}

const results = []
let stopped = false
for (const card of CARDS) {
  if (SKIP.has(card.id)) { log(`${card.id}: skipped (already done)`); continue }
  let feedback = ''
  let outcome = null
  for (let attempt = 1; attempt <= 2; attempt++) {
    const implOpts = card.model === 'opus'
      ? { label: `${card.id} impl#${attempt}`, phase: 'Implement' }
      : { label: `${card.id} impl#${attempt}`, phase: 'Implement', model: 'haiku' }
    const impl = await agent(implPrompt(card, attempt, feedback), implOpts)
    const gate = await agent(gatePrompt(card), { label: `${card.id} gate#${attempt}`, phase: 'Gate', model: 'haiku', schema: GATE_SCHEMA })
    outcome = { card: card.id, attempts: attempt, passed: !!(gate && gate.passed), gate, impl_report: typeof impl === 'string' ? impl.slice(0, 6000) : impl }
    if (outcome.passed) break
    if (gate && gate.card_defect) { log(`${card.id}: gate reports a card defect; not retrying`); break }
    feedback = JSON.stringify(gate)
  }
  results.push(outcome)
  log(`${card.id}: ${outcome.passed ? 'passed' : 'FAILED'} after ${outcome.attempts} attempt(s)`)
  if (!outcome.passed && !card.continue_on_fail) { log(`Stopping at ${card.id}; escalating to Opus.`); stopped = true; break }
}

phase('Review panel')
const lensBase = `You are an Opus reviewer of milestone ${args.milestone} of the Painterly project at ${REPO}. Read CLAUDE.md, docs/architecture.md, docs/spec.md and the cards. Review every commit after ${args.base_commit} (git log, git show) with a critical eye. Do not modify tracked files; scratch outputs go under /tmp/claude-0/-home-user-blender-painterly-render-plugin/98b29052-844f-5778-93d6-f67301038886/scratchpad/review/. Run the commands you need (make check, tests, builds into scratch dirs). Report only findings you can evidence with file:line and observed output.

Context: ${args.review_context}
Cards: ${JSON.stringify(CARDS.map(c => ({ id: c.id, path: c.path })))}
Gate results: ${JSON.stringify(results.map(r => ({ card: r.card, passed: r.passed, attempts: r.attempts, problems: r.gate && r.gate.problems })))}`
const lensResults = await parallel(args.lenses.map(l => () =>
  agent(`${lensBase}

YOUR LENS: ${l.key}. ${l.focus}`, { label: `lens ${l.key}`, phase: 'Review panel', schema: FINDINGS_SCHEMA }).then(r => ({ lens: l.key, ...r }))))

phase('Verify findings')
const all = lensResults.filter(Boolean).flatMap(r => r.findings.map(f => ({ ...f, lens: r.lens })))
const verified = await parallel(all.map((f, i) => () =>
  parallel([0, 1].map(k => () => agent(`Adversarial verifier for a code-review finding on the Painterly project at ${REPO} (read-only; you may run builds/tests into scratch directories). Try to REFUTE this finding by checking the actual code, docs and command output. Finding: ${JSON.stringify(f)}. refuted=true if the claim is false, already fixed at HEAD, or not a real problem; refuted=false only if you reproduced or directly confirmed it. Skeptic #${k + 1}.`, { label: `verify#${i}.${k}`, phase: 'Verify findings', schema: VERDICT_SCHEMA })))
    .then(vs => ({ ...f, votes: vs.filter(Boolean), confirmed: vs.filter(Boolean).filter(v => !v.refuted).length === 2 }))))
const confirmed = verified.filter(Boolean).filter(f => f.confirmed)
const disputed = verified.filter(Boolean).filter(f => !f.confirmed)
log(`review panel: ${all.length} findings, ${confirmed.length} confirmed by both skeptics, ${disputed.length} disputed or refuted`)

return {
  stopped,
  results: results.map(r => ({ card: r.card, passed: r.passed, attempts: r.attempts, gate: r.gate, impl_report: r.impl_report })),
  confirmed,
  disputed: disputed.map(f => ({ severity: f.severity, lens: f.lens, file: f.file, line: f.line, issue: f.issue, votes: f.votes })),
  observed: lensResults.filter(Boolean).map(r => ({ lens: r.lens, observed_numbers: r.observed_numbers })),
}
