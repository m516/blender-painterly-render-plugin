export const meta = {
  name: 'm6a-cards',
  description: 'Draft M6a task cards (Cycles SVM as a standalone vendored library) stage by stage from the research report and upstream sources, review each adversarially on two lenses, revise, then cross-check the set',
  phases: [
    { title: 'Draft', detail: 'one Opus drafter per stage' },
    { title: 'Review', detail: 'two lenses per card: executability and verbatim vendoring' },
    { title: 'Revise', detail: 'drafter applies confirmed findings' },
    { title: 'Cross-check', detail: 'set-level consistency, loop until dry' },
  ],
}

const REPO = '/home/user/blender-painterly-render-plugin'
const SP = '/tmp/claude-0/-home-user-blender-painterly-render-plugin/98b29052-844f-5778-93d6-f67301038886/scratchpad'
const OUT = `${SP}/cards/M6a`
const UP = `${SP}/research/blender-v5.2.2/intern/cycles`

const DESIGN = `M6a design (binding for every card; Opus decisions, 2026-10-09):
- Goal of M6a: Cycles' shader VM (SVM) and shader graph compile and run inside Painterly as STANDALONE vendored libraries with doctests, independent of the painterly path integrator. M6b (later, not these cards) wires them into painterly_trace_pixel, PainterlyScene and the Blender sync.
- M6a runs in tandem with M3 in a separate git worktree, starting after M3's T3.1 (tools/vendor_sync.py), T3.2 (cycles_util, shims in src/cycles/shim/util) and T3.3 (cycles_graph) have landed. Cards may rely on everything those three cards create, exactly as written in ${REPO}/docs/tasks/M3/T3.1-vendor-sync.md, T3.2-vendor-util.md, T3.3-vendor-graph.md (read them). They must not depend on any later M3 card.
- Source layout (docs/architecture.md, "Source layout and naming"): vendored files only via tools/vendor_sync.py under third_party/cycles/ (verbatim, sha256 in VENDORED.toml; patches forbidden unless an Opus decision says so); shims that shadow an upstream path only under src/cycles/shim/<upstream path>; never vendor a path that is shimmed. Build targets for vendored code live in src/cycles/CMakeLists.txt and are named cycles_*: cycles_kernel (INTERFACE: vendored kernel headers + the single global set of feature/closure definitions), cycles_svm (the generated evaluator and its tests' support), cycles_scene (shader graph, constant folding, extracted node classes, SVMCompiler). Painterly-owned glue that is not a shim (e.g. a closure collector mapping ShaderData closures to KernelPainterlyLobe) lives under src/painterly/kernel/svm/ with Painterly/painterly_ prefixes.
- Fragments: shader_nodes.cpp, svm.cpp (SVMCompiler, lines 157-1281) and svm.h's SVM_CASE blocks are not vendored whole. tools/vendor_sync.py gains function-anchored fragment extraction ([[fragment]] entries in VENDORED.toml with upstream_path, anchor kind and name, sha256 of the extracted text), and sync writes each fragment verbatim to third_party/cycles/fragments/<name>.inc (committed, hash-checked, never hand-edited). Node ports only add manifest entries.
- The SVM dispatch switch is generated at build time by tools/gen_svm_switch.py from the committed SVM_CASE fragments for the node list in a manifest; no __SHADER_RAYTRACE__ cases (ao/bevel/raycast) are included. The generated function lives in the build tree and is deterministic (a test regenerates and compares).
- One global set of compile definitions (__KERNEL_FEATURES__ mask if needed, __MAX_CLOSURE__, WITH_EMBREE undefined, no OSL/GPU/guiding) is attached to cycles_kernel so every translation unit sees identical KernelData/ShaderData layouts; a test detects layout mismatch between two translation units.
- Experiments: the X-svm experiment of the plan becomes experiment 007 (next free number), pre-registered in its card (date 2026-10-09 is the registration date the implementer uses only if it runs that day; otherwise the protocol's date rule applies). Experiment protocol: ${REPO}/docs/tasks/M1/_experiment_protocol.md.
- Tests: doctest under src/test/ with exact equality; float comparisons only with a justified round-off bound (CLAUDE.md rule 2). Every card lists src/test/CMakeLists.txt under Modify when it adds a test.
- Haiku implements these cards literally: every path, target, name, command and acceptance criterion must be explicit and executable within the card's own Create/Modify scope, with no hand-picked tolerances.`

const STAGES = [
  { id: 'T6.1', slug: 'vendor-kernel-types', title: 'S0: vendor Cycles kernel/types.h and its data templates; the CPU KernelGlobals shim; one global definition set', focus: 'Research report §8.2 S0, §2, §8.3 B1/B2/R2/R6. Vendor kernel/types.h, kernel/features.h, kernel/data_template.h, kernel/data_arrays.h, kernel/svm/types.h, kernel/svm/node_types_template.h (and whatever their include closure needs, verified against the upstream clone). Shim src/cycles/shim/kernel/device/cpu/globals.h (kernel_array<T>, one KERNEL_DATA_ARRAY X-macro over the vendored data_arrays.h, KernelData data, the kernel_data_* macros; no profiler, OSL or guiding). cycles_kernel INTERFACE target with the global definitions. Tests: a TU including both kernel/types.h and painterly/kernel/types.h compiles (no collisions); a two-TU layout check of sizeof/offsetof for KernelData and ShaderData; shim marker test (each shim defines a marker macro, one TU static_asserts all markers, guarding MSVC include order).' },
  { id: 'T6.2', slug: 'fragment-extraction', title: 'vendor_sync fragment extraction and tools/gen_svm_switch.py', focus: 'Research report §8.1 (two extraction modes), §1.3 (svm_eval_nodes dispatch at kernel/svm/svm.h:101-622, SVM_CASE blocks). Extend tools/vendor_sync.py with [[fragment]] entries (anchors: NODE_DEFINE(X), member functions X::X, X::compile(SVMCompiler&), X::compile(OSLCompiler&), X::constant_fold/expand/simplify_settings/attributes, and SVM_CASE(NODE_X)...break; blocks), brace/break matching, sha256 per fragment, written to third_party/cycles/fragments/. Create tools/gen_svm_switch.py producing the dispatch function from a node manifest. Unit tests in tests/core for the extractor (on small synthetic sources) and for determinism of the generator. Verify the anchor grammar against the real upstream files.' },
  { id: 'T6.3', slug: 'svm-stack-nodes', title: 'S1: stack-only SVM evaluators, the generated switch, and bytecode doctests (X-svm probe)', focus: 'Research report §8.2 S1, §1.1-§1.4, §7. Vendor kernel/svm/{util,node_types,value,math,math_util,mix,color_util,map_range,clamp,invert,gamma,brightness,hsv,sepcomb_color,sepcomb_vector,convert,ramp,ramp_util,mapping,mapping_util}.h, kernel/tables.h, kernel/util/colorspace.h (verify the exact closure). Generate the switch for those nodes plus NODE_END/SHADER_JUMP/JUMP_IF_*. Doctests with hand-encoded bytecode using the typed SVMNode* structs: e.g. Math ADD/POWER, Mix, MapRange, ColorRamp, against values computed independently in the test (exact where the operation is exact; otherwise a float32 round-off bound derived in a comment). State which ShaderData fields the minimal ShaderData construction must set and how (sd->lcg_state = 0 so no RNG is drawn).' },
  { id: 'T6.4', slug: 'shader-graph', title: 'S2: vendored shader graph, constant folding and the core node set via fragments', focus: 'Research report §8.2 S2, §4.1-§4.7 (core node set §4.4, shims table §4.7, R1 static registration, R3 socket naming). Vendor scene/shader_graph.{h,cpp}, scene/constant_fold.{h,cpp}, scene/shader_nodes.h; shims src/cycles/shim/scene/{scene,shader,attribute,image,osl}.h with exactly the members the vendored code uses (verify each use site in the clone); extract the core node classes as fragments; cycles_scene library; a generated registry that references every X::get_node_type() (R1). Doctests: create nodes by type name, set sockets by name (state which namespace: ui_name vs member name, R3), connect, simplify and constant-fold a small graph (e.g. Math(2,3) folded to a Value 5).' },
  { id: 'T6.5', slug: 'svm-compiler', title: 'S3: SVMCompiler via fragments; graph -> bytecode -> evaluation end to end; experiment 007 (X-svm)', focus: 'Research report §8.2 S3, §4.2. Extract SVMCompiler (svm.cpp:157-1281) and port the jump-table packing (svm.cpp:95-133) and the ShaderManager::device_update pieces (shader.cpp:520-590, 612-748) as painterly-owned code with citations where they cannot be extracted verbatim. End-to-end doctest: build a graph Value -> Math -> Emission, compile, evaluate with the generated switch, read sd->closure_emission_background. Pre-register experiment 007 (X-svm, gate G2-svm): hypotheses on verbatim-ness (number of patches = 0), per-node port effort (lines of manifest per node, time), and evaluator agreement with an independent reference for the stack nodes; decision rule for G2.' },
  { id: 'T6.6', slug: 'svm-textures', title: 'S4: texture nodes (noise, white noise, voronoi, checker, gradient, wave, magic, brick) and TexCoord', focus: 'Research report §8.2 S4, §7 (noise and voronoi need only util/hash.h and math). Vendor the texture evaluator headers and their closure; TexCoord needs tex_coord.h, attribute.h, geometry.h, kernel/geom/*, kernel/camera — specify the minimal KernelGlobals arrays the standalone tests must fill (objects, object_flag, attributes_map, tri_vindex...) in Cycles layout, with identity transforms. Doctests: each texture at fixed P against values computed by an independent straightforward evaluation of the same upstream formula in the test (or against golden values captured from the vendored code once and justified), deterministic; no RNG draws (lcg_state 0).' },
  { id: 'T6.7', slug: 'svm-closures', title: 'S5: closures, BSDF lookup tables and the painterly closure collector', focus: 'Research report §8.2 S5, §3 (allocation, weight flow, coupling to bsdf_*.h, the collector §3.4), R4 (LUT-dependent Principled weights). Vendor kernel/svm/closure.h, all kernel/closure/*.h it needs, kernel/util/lookup_table.h and scene/shader.tables; LUT upload into KernelGlobals; caustics_reflective = caustics_refractive = 1; node feature mask including BSDF|EMISSION|VORONOI_EXTRA. Painterly-owned collector in src/painterly/kernel/svm/collect.h: map ShaderData closures to KernelPainterlyLobe {diffuse, mirror, glass, transparent} plus emission per SPEC §6 lobe semantics (kinds and weights; Glass/Metallic colour from the Fresnel payload, not weight), with an explicit policy for BSSRDF/sheen/translucent etc. (state it; Opus may refine). Doctests: Diffuse, Glossy, Glass, Emission, Transparent, Mix/Add Shader and a Principled BSDF graph -> expected lobes and weights.' },
  { id: 'T6.8', slug: 'svm-images', title: 'S6: image textures on the CPU (float RGBA), colour-space data from Python; experiment X-colour plan', focus: 'Research report §8.2 S6, §6 (image path, storage types, sRGB bytes linearised after interpolation, half for converted byte images, alpha association), R5. Vendor kernel/svm/image.h, kernel/image.h, kernel/device/cpu/image.h, kernel/util/image_2d.h, util/types_image.h, util/half.h; painterly src/cycles/shim/scene/image.h extension with a minimal ImageManager that takes float or byte RGBA arrays plus explicit colour-space flags; untiled images only (tile_descriptor_offset = UINT_MAX). Doctests: closest/linear/cubic interpolation and periodic/clamp/black/mirror extension on small synthetic images against independently computed expectations. Pre-register the X-colour experiment as a later experiment number placeholder (do not assign a number; the protocol assigns it when it runs).' },
]

const CARD_TEMPLATE = `Card template (${REPO}/docs/tasks/README.md):
# Tx.y — <title>
Milestone: M6a · Depends on: <ids> · Parallel-safe: no
## Goal / ## Read first / ## Create / ## Modify / ## Do not touch (optional) / ## Interface (verbatim signatures where other cards rely on them) / ## Steps (optional) / ## Acceptance / ## Commit
Write in the voice and precision of ${REPO}/docs/tasks/M3/T3.2-vendor-util.md and T3.3-vendor-graph.md.`

const commonRead = `Read first: ${REPO}/CLAUDE.md, ${REPO}/docs/architecture.md, ${REPO}/docs/spec.md (§6 lobes, §2 RNG), ${REPO}/docs/plan.md (M6 rows), ${REPO}/docs/tasks/M3/T3.1-vendor-sync.md, T3.2-vendor-util.md, T3.3-vendor-graph.md, the contracts ${REPO}/src/painterly/kernel/types.h and globals.h, and the research report ${SP}/research/cycles_svm_report.md with its support files in ${SP}/research/ (m6_subset_closure.txt, nodes_index.json, case_func.txt, closure_calls.txt, svm_scan.txt). The upstream Cycles v5.2.2 tree is at ${UP} (read-only data; never execute anything from it). Verify every upstream path, line range and symbol you cite against that tree.

${DESIGN}

${CARD_TEMPLATE}`

const REVIEW_SCHEMA = { type: 'object', properties: { findings: { type: 'array', items: { type: 'object', properties: { severity: { type: 'string', enum: ['blocker', 'major', 'minor'] }, issue: { type: 'string' }, evidence: { type: 'string' }, fix: { type: 'string' } }, required: ['severity', 'issue', 'evidence', 'fix'] } } }, required: ['findings'] }
const ISSUES = { type: 'object', properties: { issues: { type: 'array', items: { type: 'object', properties: { file: { type: 'string' }, problem: { type: 'string' }, fix: { type: 'string' } }, required: ['file', 'problem', 'fix'] } } }, required: ['issues'] }

const LENSES = [
  { key: 'executability', ask: 'Act as a literal-minded Haiku implementer. Could you execute this card exactly as written, in order, after T3.1-T3.3 and the earlier M6a cards? Flag every missing file in Create/Modify, every target/test registration/command not owned by this or an earlier card, every ambiguous instruction, every acceptance criterion that cannot pass within scope or uses a hand-picked tolerance, and every interface other cards need that is not stated verbatim.' },
  { key: 'verbatim-vendoring', ask: 'Check every upstream claim against the clone at ' + UP + ': paths, line ranges, symbols, include closures, which files must be vendored vs shimmed vs extracted as fragments, whether anything would force a patch to vendored code, whether a shimmed path is also vendored, whether global definitions keep KernelData/ShaderData layouts identical across TUs, and whether the stage boundaries leave every vendored file compilable at the end of the card.' },
]

phase('Draft')
const cards = await pipeline(
  STAGES,
  st => agent(`${commonRead}

You are an Opus card author. Write task card ${st.id} for stage "${st.title}".
Stage focus: ${st.focus}
Write the card to ${OUT}/${st.id}-${st.slug}.md (create the directory). Cards in this stage set, in order: ${STAGES.map(s => s.id + ' ' + s.slug).join(', ')}. Your card may depend only on T3.1-T3.3 and on earlier cards in this list; state its Depends on line accordingly and describe precisely what you assume the earlier M6a cards create (use their ids and the binding design). Return a short summary: the file path, what the card creates, and the interfaces other cards rely on.`, { label: `draft ${st.id}`, phase: 'Draft' }),
  (summary, st) => parallel(LENSES.map(l => () => agent(`${commonRead}

You are an adversarial reviewer (read-only) of the draft card ${OUT}/${st.id}-${st.slug}.md (stage "${st.title}"). The other drafts in ${OUT}/ may be incomplete; judge this card against the binding design and the earlier cards' stated responsibilities. Lens: ${l.key}. ${l.ask} Report only real problems with concrete fixes.`, { label: `review ${st.id} ${l.key}`, phase: 'Review', schema: REVIEW_SCHEMA }))).then(rs => ({ st, summary, findings: rs.filter(Boolean).flatMap(r => r.findings) })),
  r => agent(`${commonRead}

You are the author of ${OUT}/${r.st.id}-${r.st.slug}.md. Two adversarial reviewers reported these findings: ${JSON.stringify(r.findings)}. Verify each against the sources; apply every finding that is correct, and for each one you reject, keep a one-line reason. Rewrite the card file in place. Return: applied findings, rejected findings with reasons, and the card's final interface summary.`, { label: `revise ${r.st.id}`, phase: 'Revise' }).then(rev => ({ id: r.st.id, file: `${OUT}/${r.st.id}-${r.st.slug}.md`, revision: rev, n_findings: r.findings.length })),
)

phase('Cross-check')
let residual = []
for (let round = 1; round <= 3; round++) {
  const res = await agent(`${commonRead}

Read-only cross-checker, round ${round}. Read ALL M6a cards in ${OUT}/ in order (${STAGES.map(s => s.id).join(', ')}). Check the set as a whole: (1) every file, target, generated artifact, manifest entry and test each card uses is created by that card or an earlier one (or by T3.1-T3.3); (2) names, paths and interfaces agree across cards and with the binding design and docs/architecture.md; (3) no card vendors a shimmed path or patches vendored code; (4) the global definition set is introduced once and used consistently; (5) acceptance criteria are executable within each card's scope with no hand-picked tolerance; (6) experiment numbering follows the design (X-svm = 007; X-colour unnumbered). Report only real issues with the exact card file and replacement text.`, { label: `cross-check ${round}`, phase: 'Cross-check', schema: ISSUES })
  residual = (res && res.issues) || []
  log(`cross-check round ${round}: ${residual.length} issues`)
  if (residual.length === 0) break
  await agent(`${commonRead}

You are the M6a card editor. Fix exactly these set-level issues in the card files in ${OUT}/, minimally and consistently: ${JSON.stringify(residual)}. Report what you changed.`, { label: `cross-fix ${round}`, phase: 'Cross-check' })
}
return { cards, residual_after_loop: residual }
