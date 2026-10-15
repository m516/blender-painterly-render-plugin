export const meta = {
  name: 'native-first-light',
  description: 'First renders of the native C++ core: build a scratch driver, test bit-parity against cached oracle renders across chains and ingredients, diagnose any divergence, render hero images and labelled sheets, then adversarially verify every claim',
  phases: [
    { title: 'Build', detail: 'scratch copy of the tree + render driver + post-T3.4 oracle' },
    { title: 'Parity', detail: 'native vs cached oracle, byte for byte; determinism across threads and batches; timings' },
    { title: 'Diagnose and render', detail: 'localize any divergence; hero renders and labelled sheets' },
    { title: 'Verify', detail: 'two independent skeptics recompute every claim' },
  ],
}

const REPO = '/home/user/blender-painterly-render-plugin'
const SP = '/tmp/claude-0/-home-user-blender-painterly-render-plugin/98b29052-844f-5778-93d6-f67301038886/scratchpad'
const FL = `${SP}/firstlight`
const COMMIT = 'c69ee2e'

const SHARED = `Context: Painterly (${REPO}) reproduces smallpaint_painterly's look in a native C++ core (src/painterly/, M3 tasks T3.5-T3.12 landed). Its Python binding does not exist yet (T3.14/T3.15), and the end-to-end oracle parity test is T3.16 (not landed). docs/architecture.md "Determinism contract": on analytic scenes the core must equal smallpaint_oracle bit for bit, and output must be identical for any thread count and batch size. Normative behaviour: docs/spec.md (SPEC §1-§9).
HARD RULES for you:
- Never modify, add or commit anything in ${REPO} (tracked or untracked), never run git commands that change it, never build in ${REPO}/build/* and never run make there. Other agents are working in that tree right now. Everything you write goes under ${FL}/.
- Read-only use of ${REPO}/.cache/renders/<id>/ (cached oracle renders: sum.npy <f8 (H,W,3), k_consumed.npy <u8 (H,W), object_id.npy <i4 (H,W), meta.json, image.ppm) is fine.
- The machine has 4 cores shared with other agents: run every build and render under "nice -n 10". Never run more than 2 renders at once.
- Python: ${REPO}/.venv/bin/python (numpy, jax, painterly_analysis available). Sheets: system python3 with Pillow.
- Report numbers, not adjectives. If something fails, say exactly what and why; never paper over it.`

const BUILD_SCHEMA = { type: 'object', properties: {
  ok: { type: 'boolean' }, driver: { type: 'string' }, oracle: { type: 'string' }, source_commit: { type: 'string' },
  ghost_mapping: { type: 'string' }, u2_mapping: { type: 'string' }, layout: { type: 'string', description: 'how buffer layout maps to the oracle npy layout, and whether any reordering was needed' },
  unsupported_oracle_options: { type: 'array', items: { type: 'string' } }, smoke: { type: 'string' }, notes: { type: 'string' } },
  required: ['ok', 'driver', 'oracle', 'source_commit', 'ghost_mapping', 'u2_mapping', 'layout', 'unsupported_oracle_options', 'smoke', 'notes'] }

const PARITY_SCHEMA = { type: 'object', properties: {
  configs: { type: 'array', items: { type: 'object', properties: {
    name: { type: 'string' }, cache_id: { type: 'string' }, knobs: { type: 'string' }, native_dir: { type: 'string' },
    sum_equal: { type: 'boolean' }, k_consumed_equal: { type: 'boolean' }, object_id_equal: { type: 'boolean' },
    n_values_differing: { type: 'integer' }, max_abs_diff: { type: 'number' }, first_diff: { type: 'string' },
    native_seconds: { type: 'number' }, native_threads: { type: 'integer' }, oracle_seconds: { type: 'number' }, oracle_threads: { type: 'integer' },
    reference: { type: 'string', description: 'the bitwise reference the *_equal fields compare against: "cache <id> (halton incremental, max K per chain < 2^23)", "cache <id> (halton exact)" or "fresh oracle --halton exact <dir>"' },
    vs_cached_incremental: { type: 'string', description: 'image chain only: native vs the cached incremental render (equal flags, counts); "n/a" otherwise' },
    control: { type: 'string', description: 'image chain only: fresh oracle-exact vs cached incremental, and whether its difference arrays equal native-vs-cached exactly; "n/a" otherwise' } },
    required: ['name', 'cache_id', 'knobs', 'native_dir', 'sum_equal', 'k_consumed_equal', 'object_id_equal', 'n_values_differing', 'max_abs_diff', 'first_diff', 'native_seconds', 'native_threads', 'oracle_seconds', 'oracle_threads', 'reference', 'vs_cached_incremental', 'control'] } },
  determinism: { type: 'array', items: { type: 'object', properties: { variant: { type: 'string' }, sha256_sum: { type: 'string' }, equal_to_reference: { type: 'boolean' } }, required: ['variant', 'sha256_sum', 'equal_to_reference'] } },
  timing: { type: 'array', items: { type: 'object', properties: { program: { type: 'string' }, config: { type: 'string' }, threads: { type: 'integer' }, seconds: { type: 'array', items: { type: 'number' } }, median_seconds: { type: 'number' }, load_before_after: { type: 'string' } }, required: ['program', 'config', 'threads', 'seconds', 'median_seconds', 'load_before_after'] } },
  load_average: { type: 'string' }, skipped: { type: 'array', items: { type: 'string' } }, notes: { type: 'string' } },
  required: ['configs', 'determinism', 'timing', 'load_average', 'skipped', 'notes'] }

const RENDER_SCHEMA = { type: 'object', properties: {
  sheets: { type: 'array', items: { type: 'object', properties: { path: { type: 'string' }, bytes: { type: 'integer' }, content: { type: 'string' } }, required: ['path', 'bytes', 'content'] } },
  heroes: { type: 'array', items: { type: 'object', properties: { name: { type: 'string' }, knobs: { type: 'string' }, seconds: { type: 'number' }, threads: { type: 'integer' }, parity: { type: 'string' } }, required: ['name', 'knobs', 'seconds', 'threads', 'parity'] } },
  notes: { type: 'string' } }, required: ['sheets', 'heroes', 'notes'] }

const DIAG_SCHEMA = { type: 'object', properties: {
  root_causes: { type: 'array', items: { type: 'object', properties: { configs: { type: 'string' }, file_line: { type: 'string' }, cause: { type: 'string' }, evidence: { type: 'string' }, proposed_fix: { type: 'string' }, confirmed_by_experiment: { type: 'boolean' } }, required: ['configs', 'file_line', 'cause', 'evidence', 'proposed_fix', 'confirmed_by_experiment'] } },
  notes: { type: 'string' } }, required: ['root_causes', 'notes'] }

const VERIFY_SCHEMA = { type: 'object', properties: {
  claims: { type: 'array', items: { type: 'object', properties: { claim: { type: 'string' }, confirmed: { type: 'boolean' }, evidence: { type: 'string' } }, required: ['claim', 'confirmed', 'evidence'] } },
  problems: { type: 'array', items: { type: 'string' } } }, required: ['claims', 'problems'] }

phase('Build')
const build = await agent(`${SHARED}

TASK: build a scratch native-core render driver.
1. Export the tree of commit ${COMMIT} (not the working tree, which another agent is editing): mkdir -p ${FL}/src && git -C ${REPO} archive ${COMMIT} | tar -x -C ${FL}/src. Record git -C ${REPO} rev-parse ${COMMIT}.
2. Read in that copy: docs/spec.md (§1-§9, esp. §3 chains, §5 ghost spheres, §7 camera/jitter/film), docs/architecture.md, src/painterly/kernel/types.h and globals.h, src/painterly/integrator/{path_trace,buffers}.h/.cpp, src/painterly/util/thread_pool.h, src/test/smallpaint_scene_fixture.h, src/test/test_path_trace.cpp, and the oracle src/app/smallpaint_oracle.cpp (its option parsing, its ghost/u2/chain/alpha/continue options, its film layout and write_npy/meta.json).
3. Write ${FL}/src/src/firstlight/render.cpp and ${FL}/src/src/firstlight/CMakeLists.txt, and append "add_subdirectory(firstlight)" inside the "if(PAINTERLY_BUILD_TESTS)" block of the COPY's src/CMakeLists.txt (so the driver inherits the root's C++20 and -ffp-contract=off -fno-fast-math flags exactly like the libraries). Executable name: painterly_render, linking painterly_integrator (and whatever else it needs), include dir ${FL}/src/src/test for the fixture.
   The driver renders the SPEC §9 smallpaint reference scene by constructing SmallpaintSceneFixture(chain, lane_length) and then overriding fields of its public data/analytic arrays: data.cam.width/height = --size, the integrator knobs and the camera jitter. CLI = the oracle's for the options the core supports, with the ORACLE's defaults (double literals: --jitter 1/700 image-plane units, --diffuse-gain 0.1, --emission-gain 2, --ray-epsilon 1e-4, --max-depth 20, --alpha 0, --u2 same, --ghost all, --continue-after-emitter yes, --chain image, --seed 0, --size 400, --passes 50), plus --threads N (default hardware concurrency) and --batch N (passes per render_passes call; default all passes in one call), and --out DIR. Parse numbers with strtod/strtoull so a Python repr() round-trips exactly. The fixture's own float32-rounded constants (double(0.1f) etc.) must be overridden by the CLI values, so a default driver run uses exactly the oracle's default doubles.
   Map --ghost all|lights|none and --u2 same|independent|base3 to the kernel's enums exactly as the oracle defines those options (read the oracle; document the mapping). Reject (exit 2, message) any oracle option value the core does not implement (e.g. omp-restart, pixel-major, halton exact if the core has no such knob) and list them.
   Output: sum.npy (<f8, shape (H,W,3)), k_consumed.npy (<u8, (H,W)), object_id.npy (<i4, (H,W)) in exactly the oracle's array layout and row order (read SPEC §7 and both film layouts; if PainterlyRenderBuffers stores rows in a different order or layout than the oracle's files, convert when writing and say so in "layout"), and meta.json (every knob, size, passes, threads, batch, wall_seconds of the render calls only, total_k_consumed, source commit). Also call render_object_id(). Use the oracle's own .npy header format.
4. Configure and build: cmake -S ${FL}/src -B ${FL}/build -G Ninja -DCMAKE_BUILD_TYPE=Release -DPAINTERLY_BUILD_MODULE=OFF -DPAINTERLY_BUILD_TESTS=ON -DPAINTERLY_BUILD_ORACLE=ON -DFETCHCONTENT_SOURCE_DIR_EMBREE=${REPO}/build/dev/_deps/embree-src -DFETCHCONTENT_SOURCE_DIR_DOCTEST=${REPO}/build/dev/_deps/doctest-src (if a _deps source dir is missing, let FetchContent clone it into ${FL}/build). Ninja: use ${REPO}/.venv/bin/ninja if ninja is not on PATH (pass -DCMAKE_MAKE_PROGRAM). Build with: nice -n 10 cmake --build ${FL}/build -j 3. Then run ${FL}/build/src/test/painterly_tests (must pass) — the copy's unit tests.
5. Smoke: run the driver and the scratch-built oracle (${FL}/build/src/app/smallpaint_oracle) at --size 32 --passes 2 --seed 7 with defaults, compare the three arrays with numpy (array_equal) and report the result in "smoke" (pass or the exact difference: count, max abs, first index). Do not try to fix kernel code; if they differ, report it — a later stage diagnoses.
Return the structured result.`, { label: 'build driver', phase: 'Build', schema: BUILD_SCHEMA })

if (!build || !build.ok) {
  return { stage: 'build', build }
}
log(`build ok; smoke: ${build.smoke}`)

phase('Parity')
const parity = await agent(`${SHARED}

Driver (built from commit ${build.source_commit}): ${build.driver}. Scratch-built post-T3.4 oracle: ${build.oracle}. Builder notes — ghost mapping: ${build.ghost_mapping}; u2 mapping: ${build.u2_mapping}; layout: ${build.layout}; unsupported: ${JSON.stringify(build.unsupported_oracle_options)}; smoke: ${build.smoke}.

TASK: test the hypothesis "the native core equals smallpaint_oracle bit for bit" (docs/architecture.md "Determinism contract"), plus determinism across threads/batches, plus a controlled timing comparison.

THIS IS A RESUMED RUN. A previous parity agent was interrupted by a container restart. Its runner ${FL}/fl2/run_all.py, index ${FL}/fl2/index.json, log ${FL}/fl2/run.log and partial results ${FL}/fl2/results.json survive, and so do its finished renders: every directory under ${FL}/renders/ and ${FL}/determinism/ that contains meta.json is complete — reuse it, never re-render it. A directory without meta.json is incomplete: delete and re-render it. You may reuse or adapt run_all.py.

REFERENCE RULE (SPEC §2, binding): the core implements vdc(K), which is the oracle's --halton exact. The oracle's default --halton incremental equals vdc bit for bit only while K < 2^23 and differs at every draw from K = 2^23 on; SPEC §2 says "Bit-parity tests therefore always run the oracle with --halton exact". The cache was rendered with incremental (except one configuration).
- Row and lane chains restart K per row or lane. Their cached incremental renders are valid bitwise references only if every chain's final K < 2^23: verify that per configuration (for row chains the maximum over rows of the row's k_consumed sum is an upper bound of the chain's final K, or compute it exactly from the K0 rule of SPEC §3) and state it in "reference". If a chain could reach 2^23, use a fresh oracle --halton exact render instead.
- Image chains (one chain over the whole image) run far past 2^23, so their cached incremental renders are NOT valid bitwise references. For every image-chain configuration, render the scratch-built oracle (${build.oracle}) with exactly the cached meta's knobs plus --halton exact --threads 1 into ${FL}/oracle/<name>/ (reuse it if meta.json exists), and set the *_equal fields from native vs that fresh oracle render. Configuration image_400_exact (the one cached configuration rendered with --halton exact) is compared with its cached render directly.
- Control test of the explanation, for every image-chain configuration: compare the fresh oracle-exact render with the cached incremental one. Prediction: oracle-exact differs from cached-incremental, and its difference arrays (sum and k_consumed, element by element) equal the native-vs-cached-incremental difference arrays exactly. Report the outcome in "control", and native vs cached in "vs_cached_incremental".

1. Index ${REPO}/.cache/renders/*/meta.json. For each configuration below, take the cached render with the smallest seed among those matching (scene gui, halton incremental unless stated) and record its id. The cached renders were made by an older oracle binary whose defaults are identical (T3.4 kept default renders byte-identical); their knobs are in meta.json.
   Configurations (size/passes/chain/ghost/alpha/u2/continue/jitter), all others at oracle defaults:
   A image_400: 400/64/image/all/0/same/yes/0.0014285714285714286
   B image_400_j0: same as A with jitter 0
   C row_400: 400/64/row, jitter 0.0014285714285714286
   D row_400_j0: row, jitter 0
   E lane1_400, lane16_400, lane128_400: chains lane:1, lane:16, lane:128
   F ghost_lights, ghost_none: image chain, ghost lights / none
   G alpha_025, alpha_05, alpha_1: image chain, alpha 0.25 / 0.5 / 1
   H u2_independent, u2_base3: image chain
   I stop_at_emitter: image chain, continue no
   J image_200_j350: 200 px image chain jitter 0.002857142857142857; row_800: 800 px row jitter 0.0014285714285714286
   K image_400_512: 400 px image chain, 512 passes (the largest single image-chain render in the cache)
   L image_400_exact: as A, but the cached render with halton exact (compared with the cache directly)
   Skip (and list in "skipped") any configuration whose option the driver rejects (u2 base3: the core has no base-3 Halton).
2. For each: run the driver with exactly the cached meta's knobs (pass jitter, alpha etc. as repr of the meta values; seed = the meta seed; --threads 1 for the image chain, --threads 4 otherwise), output ${FL}/renders/<name>/. Compare sum.npy, k_consumed.npy, object_id.npy with numpy: array_equal, number of differing values, max |diff|, first differing index, and whether k_consumed differs (k_consumed differing means the sample sequence diverged, not just float round-off). Record native wall_seconds (from meta) and the cached oracle wall_seconds and threads.
   Run at most 2 renders concurrently, all under nice -n 10. Record "uptime" load averages before and after in load_average (timings are under contention; state that).
3. Determinism: at 200 px, 64 passes, row chain, jitter 0.0014285714285714286, seed = the smallest cached seed of the 200 px row jitter-1/700 configuration: render with (threads 1, batch 64), (threads 2, batch 64), (threads 4, batch 64), (threads 4, batch 8 = eight calls of 8 passes), (threads 4, batch 1). sha256 each sum.npy; equal_to_reference compares with the first variant; also compare the first variant with that cached oracle render and report it as an extra determinism entry named "vs cached oracle".
4. Controlled timing (after all renders above, so nothing else of yours runs concurrently). Hypothesis to test, with its origin: the interrupted run measured native image_400 at 40.0 s on 1 thread against the cached oracle's 25.2 s on 1 thread, which suggests the native core is slower per thread; but the native render ran next to a 4-thread render under load average ~6, and the oracle time came from a different day, so contention alone could explain it. Test: for (image chain, 400 px, 64 passes, seed 0, jitter 1/700) and (row chain, 400 px, 64 passes, seed 0, jitter 1/700), run native --threads 1 and oracle (--halton exact) --threads 1 back to back, alternating native, oracle, native, oracle, native, oracle (3 repeats each), one process at a time, under nice -n 10, into ${FL}/timing/. Then native row at --threads 4, 3 repeats. Record the wall_seconds from each meta.json, the medians and uptime load averages before and after each pair. Report the native/oracle median ratio per configuration as a number; no threshold. State that other agents share the machine.
5. If any configuration differs from its bitwise reference, do NOT try to fix it; describe precisely in notes (which arrays, how many values, magnitude, first index, whether K diverged). A diagnose stage follows.
Return the structured result.`, { label: 'parity matrix', phase: 'Parity', schema: PARITY_SCHEMA })

const mismatches = (parity && parity.configs || []).filter(c => !(c.sum_equal && c.k_consumed_equal && c.object_id_equal))
log(`parity: ${(parity && parity.configs || []).length} configs, ${mismatches.length} mismatching`)

phase('Diagnose and render')
const diagThunk = () => mismatches.length === 0 ? Promise.resolve(null) : agent(`${SHARED}

The native core differs from the oracle in these configurations (driver ${build.driver}, oracle ${build.oracle}, scratch source copy ${FL}/src, renders under ${FL}/renders/ and ${REPO}/.cache/renders/): ${JSON.stringify(mismatches)}
Builder notes: ghost mapping ${build.ghost_mapping}; u2 ${build.u2_mapping}; layout ${build.layout}.
TASK: localize the root cause of each divergence. Work in a SECOND scratch copy (cp -r ${FL}/src ${FL}/diag-src, build in ${FL}/diag-build) so the parity renders stay reproducible. Method: find the first differing pixel/pass; render a tiny image (e.g. 8 px, 1 pass, or a single pixel) in both programs with temporary instrumentation (printf of K, u1/u2, ray origin/direction, t, throughput per vertex) in the diag copies; find the first vertex where they diverge; trace it to a file:line in the native core (src/painterly/...) or in the driver itself (a driver knob/mapping error is a valid root cause — say so). Confirm the cause by an experiment (patch the diag copy, rebuild, show the arrays become equal) where possible, and set confirmed_by_experiment accordingly. Propose the fix as precisely as a task card would. Never edit ${REPO}.
Return the structured result.`, { label: 'diagnose divergence', phase: 'Diagnose and render', schema: DIAG_SCHEMA })

const renderThunk = () => agent(`${SHARED}

Driver: ${build.driver}. Parity results: ${JSON.stringify(parity)}.
TASK: hero renders and labelled comparison sheets for the project owner, who has seen these earlier oracle sheets: ${SP}/gallery/{1_the_look,2_close_up,3_ingredients,4_lanes,5_resolution}.png (made by ${SP}/gallery/sheets.py from ${SP}/gallery/export.py output; reuse its layout, fonts, colours and its display transform painterly_analysis.io.smallpaint_display(sum, passes)).
1. Hero renders with the native core (nice -n 10, --threads 4 except the image chain, which is single-threaded by design), output ${FL}/renders/hero_*:
   - hero_row_400: 400 px, row chain (the new default), 1024 passes, seed 0, defaults otherwise.
   - hero_row_800: 800 px, row chain, 512 passes, seed 0, jitter 0.0014285714285714286 (image-plane units keep the look across sizes, experiment 006).
   - hero_image_400: reuse the parity render K (image chain, 400 px, 512 passes) — do not re-render it.
   Record seconds and threads; "parity" = the parity status of the matching configuration ("bit-identical to cached oracle <id>" / "differs: ..." / "no cached oracle at these knobs").
2. Sheets (PNG, under ${FL}/sheets/, each <= 1.5 MB, 400 px tiles like the gallery; captions state numbers, not adjectives):
   - 6_first_light.png: "First light: the native C++ core vs the oracle". Rows for image chain (A), row chain (C), lane:16 (E): [oracle (the bitwise reference the parity result names: fresh --halton exact for the image chain, the cache for row and lane) | native core | difference]. The difference tile is a mask of the pixels where any channel of sum differs bitwise (no threshold, no amplification): black = identical, white = differs; caption "N of M values differ" with the exact count from the parity result.
   - 7_native_core.png: the hero renders, captions with size, chain, passes, seconds and threads.
   - 8_native_ingredients.png: native renders of the ingredient configurations F, G (alpha 1), H (independent), I, each captioned with its parity status, in the layout of the earlier 3_ingredients.png.
   - 9_speed.png is NOT needed; put timings in the result instead.
3. Write ${FL}/README.md: what was built (commit, driver), the parity table (all configs), determinism table, timings with the load caveat, and the sheet list. Numbers only.
Return the structured result.`, { label: 'heroes and sheets', phase: 'Diagnose and render', schema: RENDER_SCHEMA })

const [diag, render] = await parallel([diagThunk, renderThunk])

phase('Verify')
const claimsText = JSON.stringify({ parity, render: render && { heroes: render.heroes, sheets: render.sheets }, diag })
const skeptics = await parallel([0, 1].map(k => () => agent(`${SHARED}

You are independent skeptic #${k + 1}. Another agent claims the following about the native core's first renders (driver ${build.driver}, built from a scratch copy ${FL}/src of commit ${build.source_commit}; oracle ${build.oracle}; renders ${FL}/renders/; cache ${REPO}/.cache/renders/): ${claimsText}
Try to REFUTE every claim. Do not trust the reports; recompute.
1. For every parity configuration: load the native arrays and the arrays of the reference it names (the cache, or a fresh --halton exact oracle render under ${FL}/oracle/; SPEC §2 requires --halton exact for bit parity, and a cached incremental render is a valid reference only while every chain's K < 2^23 — check that claim) yourself and recompute equality, counts and max diff, and recompute the image-chain control test. Compare the two meta.json files knob by knob (size, passes, seed, chain, ghost, alpha, u2, continue, jitter, gains, epsilon, depth) — a parity claim with mismatched knobs is refuted.
2. Read ${FL}/src/src/firstlight/render.cpp and its CMakeLists: confirm it never reads oracle outputs or ${REPO}/.cache, really renders through PainterlyPathTrace, and that its defaults and enum mappings match the oracle's (read ${FL}/src/src/app/smallpaint_oracle.cpp). Confirm the driver target is compiled with the root's -ffp-contract=off flags (inspect ${FL}/build/build.ninja or compile_commands).
3. Independent of the cache: render one fresh small configuration ${k === 0 ? '(row chain, 120 px, 16 passes, seed 3, defaults otherwise)' : '(lane:16 chain, 96 px, 24 passes, seed 11, ghost lights, alpha 0.5)'} with BOTH the driver and the scratch-built oracle into ${FL}/verify${k + 1}/ (nice -n 10) and compare all three arrays.
4. Check the determinism entries by recomputing the sha256 values. Check every number in the sheets' captions against the arrays (open the PNGs and read them; captions must match the counts).
5. If a diagnosis is present, check its evidence and whether its experiment really made the arrays equal.
Return each claim with confirmed true/false and your evidence, plus any problems found.`, { label: `skeptic ${k + 1}`, phase: 'Verify', schema: VERIFY_SCHEMA })))

return { build, parity, diag, render, skeptics }