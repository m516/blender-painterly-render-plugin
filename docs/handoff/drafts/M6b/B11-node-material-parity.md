# B11 — Node-material parity on the reference scene (drafted from BRIEF.md section 2, "B11")

Milestone: M6b · Depends on: B8, N11, N12, M5-T5.4 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B11" (lines 267-272) and its section 1 decisions 3, 6
and 9 (lines 30-37, 58-66, 78-79), per that brief's section 4 (lines 303-324). Code facts are
`docs/handoff/drafts/M6b/FACTS.md` §3.8, §3.12, §3.13 and §6 gaps 2 and 6, re-read at this clone's HEAD in every
file cited below. The bpy facts and the float32 literals are measured on this host with the project's `bpy` 5.2.2 by
the scripts in steps 1, 5 and 6, each quoted with its command and its output.

`BRIEF.md` gives B11 three things: a scope (the reference `.blend` of T5.4 with node materials — Principled, Diffuse,
Emission — against the oracle ensemble, through the SVM path), an acceptance (T5.4's statistical test from
`analysis/painterly_analysis/ensemble.py`, unchanged, on the ensemble's own band) and a `Needs` line (:272). This card
turns them into one generator change, one exact test file and one acceptance that runs T5.4's test untouched. Where
the brief and the code disagree — its `Needs` line, and the Emission node on a scene whose only emitter is a light —
the disagreement is in `## Open for Opus`, with the evidence, and the steps are written for the code as it is.

## Goal

The reference scene that T5.4 authors as a `.blend` reaches the oracle ensemble through Cycles' own SVM, and its
materials are the node graphs of B8's export, not M5's constant mapping:

- **The `.blend`'s surface materials are node graphs the SVM can evaluate** (BRIEF.md:267-269). `tools/make_reference_scene.py`
  (M5 T5.4's file) authors each SPEC §9 object's material as a node tree: a Principled BSDF for the mirror sphere
  (`Metallic` 1) and the glass sphere (`Transmission Weight` 1, `IOR` 1.5), and a Diffuse BSDF for the seven diffuse
  objects. Every colour is SPEC §9's `cl/10` (T5.4:20-24). The point light stays a point light: SPEC §5 makes it a
  ghost sphere with a constant material (SPEC §5, `docs/spec.md:158`, `:212`; T5.3:8-16), and BRIEF.md:297-298 keeps
  light node graphs out of v1.
- **Why the diffuse objects get a Diffuse BSDF and not a Principled BSDF.** Under M5's constant mapping the two are
  the same material — T5.3:35-40 maps Principled's `Base Color` × (1 − Metallic) × (1 − Transmission) and Diffuse
  BSDF's `Color` to the same diffuse lobe. Under the SVM they are not: a Principled BSDF whose `Specular IOR Level` is
  Blender's default 0.5 allocates a specular layer of `f0 = F0_from_ior(1.5) = 0.04000000283122063` and attenuates
  the diffuse layer by (1 − F) (step 5's derivation; `third_party/cycles/kernel/svm/closure.h:426-470`), while a
  Diffuse BSDF allocates one diffuse closure of `Color` (`:524-540`). The reference look has no specular layer on its
  diffuse surfaces (SPEC §6, `docs/spec.md:190-196`: a material is its lobes, and §9 gives the planes one diffuse
  lobe), so the generator writes the node whose lobe list is that one lobe.
- **The reference scene's node materials render bit for bit like M5's constant mapping of the same materials.** Both
  sides read the same bpy socket, so both hold the same float32 value: the constant path through T5.3's mapping and
  the node path through B8's export give the same lobes, the same emission, the same K and the same image. Step 6's
  seven tests are that claim, exactly.
- **T5.4's statistical test decides the parity, unchanged** (BRIEF.md:270-271). `tests/blender_it/test_reference_blend.py`
  calls `ensemble.compare_ensembles` on `metrics.realization_free_key_family(metrics.diffuse_key_family(keys))` at
  `ensemble.DEFAULT_ALPHA`; this card changes no line of it, no key, no alpha, no pair count, no seed block and no
  mask, and the band it applies is the ensemble's own (46 diffuse keys, 26 in the realization-free family, 20 of them
  the hard-asserted `r3`-`r7` keys — step 1's derivation). The node path is never measured against a band derived from
  the node path's own output.

Nothing in the core changes. B11 adds no library, no knob (BRIEF.md:75-77) and no CONTRACT line: it changes what one
Blender scene's materials are, and adds the tests that say the two material paths of that scene agree.

## Read first

- `CLAUDE.md` rules 1, 2, 3 and 6; `AGENTS.md` "Expected values are evidence, not targets"; SPEC §5
  (`docs/spec.md:158`: point and spot lights are ghost spheres), §6 (`:190-207`: a material is its lobes plus an
  emission colour, the closure policy's inputs, `two_sided`), §9 (`:299-308`: the reference table, and `:169` "The
  reference scene is closed and never misses") and §7 (`:282-291`: the knobs and their defaults).
- `docs/handoff/drafts/M6b/BRIEF.md` lines 267-272 (this card's mandate), 30-37 (decision 3: a material is constant
  or a node material), 58-66 (decision 6: the `ShaderData` of a painterly hit), 75-79 (no new knob; expected values
  are evidence) and 295-301 (the open questions this card must not decide, `:297-298` among them).
- `docs/handoff/drafts/M6b/FACTS.md` §3.8 (`painterly_trace_pixel` reads `kg->materials[...]`), §3.12 (the add-on as
  it is: `sync/` holds only `__init__.py` and `reference.py`), §3.13 (what Cycles-side code exists per node batch),
  §5 rows R4 and R8, and §6 gaps 2 (SPEC is silent on node materials) and 6 (M5's sync is card text only).
- `docs/tasks/M5/T5.4-reference-blend-parity.md` in full: the generator `:9-30`, the material values `:20-24`, the
  light `:25`, the knob assertion `:26-28`, the camera `:17-19`, the runner `:34-45`, the statistical test `:47-62`
  (the `compare_ensembles` call `:51-53`, the family and the hard assertion `:68-71`), the primary-hit check `:72-80`,
  the `Makefile` targets `:83-87`, and the seed sentence `:49-50`.
- `docs/tasks/M5/T5.3-sync-lights-world-materials.md`: `sync_lights` `:8-16` (a point light becomes a ghost sphere
  with `add_material([("diffuse", (0.0, 0.0, 0.0), 0.0)], emission = color·energy·emission_scale)`), `sync_world`
  `:27-31`, and `MaterialTable`'s constant mapping `:32-42` (Principled `:35-38`, Diffuse BSDF and Emission `:39-40`,
  "Anything else → diffuse(0.8 grey), with a one-time warning naming the node" `:41`).
- `docs/handoff/drafts/M6b/B8-node-table-export.md`: the interface this card consumes — `export_graph` /
  `export_material` / `export_world` (`:215-222`), `MaterialTable.__init__(scene_core, stats=None)` and
  `material_index_of` (`:232-236`), `SyncStats.warnings` (`:226-228`), the fallback and its one warning (`:535-551`),
  and the test device this card reuses to force the constant path: `monkeypatch.setattr(material_module,
  "export_material", _raise_unknown)` (B8's E12, `:684-686`).
- `docs/handoff/drafts/M6b/B6-shader-graph-api.md` `## Interface`: `Scene.add_shader(nodes, links) -> int` and
  `Scene.add_node_material(shader: int) -> int`, and the node form "one node is (Cycles type name, parameters by
  member name, linkable input defaults by UI name); one link is (from node, output UI name, to node, input UI name);
  to-node -1 is the graph's output".
- `src/blender/addon/sync/reference.py` in full: `REFERENCE_SCENE` `:46-57` (the ten rows, in object-id order),
  `GHOST_POLICIES` `:60`, `apply_reference_knobs` `:63-83` (`diffuse_gain` `np.float32(0.1)`, `emission_gain` 2,
  `ray_epsilon` `np.float32(1e-4)`, `max_depth` 20, `spiral_frame` `"smallpaint"`), `material_of` `:86-105` and
  `build_smallpaint_scene` `:108-143` (the constant scene this card's exact test compares against).
- `src/blender/addon/sync/__init__.py:15-30` (`build_scene`'s M5 stub, which T5.1-T5.3 replace and B8 extends with
  `stats`) and `src/blender/addon/session.py:121-139` (reference mode or `sync.build_scene`).
- `src/blender/addon/properties.py:169-176` (`reference_scene`, the BoolProperty that chooses the reference scene) and
  `:5-13` (the module docstring: the knobs come from the core, so `diffuse_gain` is a socket, not a literal).
- The vendored node definitions whose sockets the export names, each read in full:
  `third_party/cycles/fragments/scene/shader_nodes_cpp/node_define/PrincipledBsdfNode.inc` (`principled_bsdf` `:3`,
  `Base Color` `:21`, `Metallic` `:22`, `Roughness` `:23`, `IOR` `:24`, `Specular IOR Level` `:38`,
  `Transmission Weight` `:44`, `Emission Color` `:56`, `SurfaceMixWeight` `:62`, the two `SOCKET_ENUM` parameters
  `:5-19`), `DiffuseBsdfNode.inc` (`diffuse_bsdf` `:3`, `Color` `:5`, `Normal` `:6`, `SurfaceMixWeight` `:7`,
  `Roughness` `:8`, `BSDF` `:10`), `EmissionNode.inc` (`emission` `:3`, `Color` `:5`, `Strength` `:6`, `Emission`
  `:10`) and `OutputNode.inc` (`output` `:3`, `Surface` `:5`, `Volume` `:6`, `Displacement` `:7`, `Normal` `:8`).
- `third_party/cycles/kernel/svm/closure.h`: the Principled layer order and weights `:100-120` (Alpha's transparent
  closure), `:320-352` (Metallic: an F82 conductor of `weight = metallic × weight`, then `weight *= 1 - metallic`),
  `:362-410` (Transmission: a GGX glass of `transmission_weight × weight`, `bsdf->ior` from `IOR`, then
  `weight *= 1 - transmission_weight`), `:425-435` (`Specular IOR Level`: `f0 = F0_from_ior(ior)`, then
  `f0 *= 2 × level` and `eta = ior_from_F0(f0)` when the level is not 0.5), `:437-472` (the specular layer and
  `closure_layering_weight`), `:474-521` (the diffuse layer, `diffuse_weight = base_color × (1 - subsurface_weight) ×
  weight`), `:524-540` (`CLOSURE_BSDF_DIFFUSE_ID`: `bsdf_diffuse_setup(sd, N, closure_weight × mix_weight)`),
  `:1406-1428` (`svm_node_closure_emission`) and `:1499-1515` (`svm_node_mix_closure`).
- `third_party/cycles/kernel/closure/bsdf_util.h:284-293` (`ior_from_F0`, `F0_from_ior`), `:440-444`
  (`closure_layering_weight`); `third_party/cycles/kernel/closure/emissive.h:16-38` (`background_setup`,
  `emission_setup`); `third_party/cycles/kernel/closure/alloc.h:55-93` (`closure_sample_weight`, `bsdf_alloc`, and
  `CLOSURE_WEIGHT_CUTOFF` = `1e-5f`, `svm/types.h:576`); `third_party/cycles/kernel/closure/bsdf_diffuse.h:25-35`
  (`bsdf_diffuse_setup`).
- `third_party/cycles/fragments/scene/shader_nodes_cpp/member/`: `BsdfNode.compile-SVMCompiler_compiler.inc:1-26` (a
  BSDF node's `Color` becomes `NODE_CLOSURE_SET_WEIGHT` when unlinked), `DiffuseBsdfNode.compile-SVMCompiler.inc`
  (the four `SVMNodeDiffuseBsdfData` members), `EmissionNode.compile-SVMCompiler.inc:14-27` (the constant branch
  `color × strength` and `NODE_CLOSURE_EMISSION`), `PrincipledBsdfNode.compile-SVMCompiler.inc:1-58` (every input by
  its member name), and `EmissionNode.constant_fold.inc:1-9` (an Emission of colour 0 or strength 0 folds away — the
  reason step 6's emission test uses 120, not 0).
- `src/painterly/kernel/svm/collect.h` in full: the evaluation contract `:11-23`, the two feature masks `:34-48`,
  `PainterlySvmMaterial` `:52-60`, `painterly_svm_reflection_color` `:107-127` (F82_TINT: the payload's `f0`),
  `painterly_svm_transmission_color` `:133-142`, `painterly_svm_lobe_weight` `:147-152`, `painterly_svm_collect`
  `:165-211` and its zero-closure fallback `:205-210`.
- `src/test/test_cycles_svm_closures.cpp:619-705` (`Principled BSDF layers and the lookup tables`): the six variants
  whose expected lobe lists this card's derivations reuse — `:655-661` (the default `Specular IOR Level` 0.5: a mirror
  lobe of `f0` and a diffuse lobe of `Base Color × (1 - F)`), `:664-669` (`Specular IOR Level` 0: one diffuse lobe of
  `Base Color`, no table read), `:671-676` (Metallic 1: one mirror lobe of `Base Color`), `:679-682` (Transmission 1:
  one glass lobe of `sqrt(Base Color)` and `IOR`), and `:359-384` (Diffuse BSDF: one diffuse lobe of `Color`).
- `src/test/cycles_kernel_layout_probe.h:93` (`ShaderData` 6480 B) and `src/test/bitwise.h:42-50` (`same_bits`);
  `src/painterly/session/session.cpp:55` and `:166` (the device update on the caller thread, then one `globals()`
  snapshot per render), which is why two sessions of the same scene start from the same device scene.
- The render-on-a-pool pattern and its `memcmp` helper: `src/test/test_path_trace.cpp:79-105`; the Python-side
  equivalent this card's Blender tests use is `_painterly.Session` (`src/blender/_painterly.pyi`, `Session.combined`
  and `Session.k_consumed`).
- `tests/blender/conftest.py:22-33` (`ADDON_DIR`, `HAS_BPY`, `collect_ignore_glob`), `:44-53` (the add-on loaded as
  the package `painterly`, so a test imports `painterly.sync.shader.export`) and `:62-73` (the `addon` fixture);
  `tests/blender_it/test_extension_it.py:36-51` (the repo root, `ZIP_PATH_FILE`, `SIZE`, `PASSES`, `CHAIN`,
  `EXPOSURE`, `HALTON_EXACT`), `:76-102` (`_require_blender`, `_require_zip`: the two skips) and `:143-213` (the
  render-and-compare shape).
- `analysis/painterly_analysis/ensemble.py:283-323` (`compare_ensembles`, its power guard `:312-318` and
  `:238-262` `min_attainable_pvalue`), `:170-185` (`holm`), `:34-35` (`DEFAULT_ALPHA = 0.01`), and
  `analysis/painterly_analysis/metrics.py:342-413` (`measure`'s 7 keys per region plus 4 `all.*` keys), `:416-432`
  (`diffuse_key_family`) and `:440-457` (`realization_free_key_family`).
- `pyproject.toml:38-40` (`testpaths`, `--import-mode=importlib`, the `slow` marker) and `Makefile:73-74`
  (`test-blender`), `:91-92` (`blender-it`), `:94-97` (`lint`).

## Create

- `tests/blender/test_reference_node_materials.py`

## Modify

- `tools/make_reference_scene.py` (M5 T5.4's generator): the material authoring of step 5 — a Diffuse BSDF for the
  seven diffuse objects, and the comment that cites the two closure lines which make that the node with the
  reference look.

## Do not touch

- `tests/blender_it/test_reference_blend.py`, `tests/blender_it/run_reference_blend.py` and
  `tests/core/test_reference_scene_math.py`: T5.4's files. The statistical test is B11's acceptance *because* it does
  not change (BRIEF.md:270-271): not one line of its decision, its family, its alpha, its pairs, its seed block or
  its masks may move, and its `reference_camera_rotation` test is T5.4's.
- `tests/blender_it/` beyond those two files: the golden harness is B9's (BRIEF.md:237-255).
- `src/blender/addon/sync/**`: `sync/geometry.py`, `sync/material.py`, `sync/world.py` and `sync/shader/*` are M5
  T5.1-T5.3's and B7's and B8's. This card consumes them and changes no line.
- `src/blender/addon/sync/reference.py`: the constant reference scene of SPEC §9. It is the *other* side of step 6's
  exact comparison, so it must not move — its `material_of` (`:86-105`) is M5's mapping as a constant scene.
- `src/painterly/**`, `src/cycles/**`, `src/blender/python.cpp`, `src/blender/_painterly.pyi` (CONTRACT, `:4`): the
  SVM path, the shader manager, the bindings and the world's binding are B1-B8's. B11 adds no kernel line, no
  binding and no CONTRACT text.
- `third_party/cycles/**`: vendored; `tools/vendor_sync.py` alone writes it, and this card vendors nothing (every
  evaluator it needs is vendored, `src/cycles/svm_nodes.toml`).
- `Makefile`, `pyproject.toml`, `src/blender/CMakeLists.txt`: T5.4 owns the `reference-blend` and `blender-it`
  targets (`T5.4:83-87`), and this card adds no test dependency the Blender suite does not already have.
- `tests/core/test_api_contract.py`, `tests/core/test_oracle_parity.py`, `tests/core/test_triangle_path.py`: they must
  pass unchanged, at their own counts, because B11 changes no core and no binding.
- `NODE_TABLE` and the export machinery (`src/blender/addon/sync/shader/node_table.py`, `export.py`): B8's, and the
  batch cards' rows are N1, N5, N6, N10, N11 and N12's (BRIEF.md:274-292).

## Interface

No CONTRACT change. B11 declares nothing and Opus writes no header for it. It consumes these interfaces, copied
exactly from the cards that own them:

    /* B2's, called by B8 and by this card's step 6 */
    int PainterlyScene::add_shader(std::unique_ptr<ShaderGraph> graph);   /* shader index, dense from 0 */
    int PainterlyScene::add_node_material(int shader);                    /* material index, dense from 0 */

`src/blender/_painterly.pyi`, B6's (BRIEF.md:200-203):

    # One node is (Cycles type name, parameters by member name, linkable input defaults by UI name).
    # One link is (from node, output UI name, to node, input UI name); to-node -1 is the graph's output.
    def add_shader(
        self,
        nodes: list[tuple[str, dict[str, object], dict[str, object]]],
        links: list[tuple[int, str, int, str]],
    ) -> int: ...
    def add_node_material(self, shader: int) -> int: ...

B8's (`B8-node-table-export.md:215-217`, `:232-236`), which this card's tests import:

    def export_graph(tree: FlattenedTree) -> tuple[list[NodeSpec], list[LinkSpec]]: ...
    def export_material(scene_core: Scene, tree: FlattenedTree) -> int: ...
    class MaterialTable:
        def __init__(self, scene_core: Scene, stats: SyncStats | None = None) -> None: ...
        def material_index_of(self, material: bpy.types.Material | None) -> int: ...

and `SyncStats.warnings: list[str]` (`B8-node-table-export.md:226-228`, over T5.2's `SyncStats`).

T5.4's, unchanged and called as it is (`T5.4:83-87`): the target `reference-blend`, the runner
`tests/blender_it/run_reference_blend.py` and the statistical test `tests/blender_it/test_reference_blend.py`.

## Steps

1. Preconditions. Each must hold; otherwise stop, commit nothing and report what you saw.
   - T5.4 landed: the generator, the runner and the statistical test exist, so each of these prints a count of at
     least `1`:
     ```
     grep -c 'def main' tools/make_reference_scene.py
     grep -c 'def main' tests/blender_it/run_reference_blend.py
     grep -c 'compare_ensembles' tests/blender_it/test_reference_blend.py
     grep -c 'reference-blend' Makefile
     ```
   - B8 landed: the export machinery and the fallback exist, so each of these prints `1`:
     ```
     grep -c 'def export_material' src/blender/addon/sync/shader/export.py
     grep -c 'warnings' src/blender/addon/sync/geometry.py
     grep -c 'export_material' src/blender/addon/sync/material.py
     ```
   - N11 and N12 landed: the Principled, Diffuse and Emission rows and the Background row are in the table. Each of
     these prints `1`:
     ```
     grep -c '"ShaderNodeBsdfPrincipled"' src/blender/addon/sync/shader/node_table.py
     grep -c '"ShaderNodeBsdfDiffuse"' src/blender/addon/sync/shader/node_table.py
     grep -c '"ShaderNodeEmission"' src/blender/addon/sync/shader/node_table.py
     grep -c '"ShaderNodeBackground"' src/blender/addon/sync/shader/node_table.py
     ```
     A `0` means that row is missing: stop and report, because the sync would fall back with a warning and step 6's
     no-warning test would fail for a reason outside this card.
   - The reference scene's ten rows and their material kinds are the ones this card counts. This prints `10`, and the
     material kinds are `mirror`, `glass`, `diffuse` × 7 and `light` (`docs/spec.md:299-308`, `reference.py:46-57`):
     ```
     grep -c '^    ("' src/blender/addon/sync/reference.py
     ```
   - `bpy` is importable and is 5.2.2: this prints `5.2.2 LTS`.
     ```
     .venv/bin/python -c "import bpy; print(bpy.app.version_string)"
     ```
   - The ensemble's band, which is the acceptance's band and not this card's. Save this script under `/tmp` and run
     it with `PYTHONPATH="$PWD/analysis" .venv/bin/python -P -s <file>`; it must print exactly the lines quoted after
     it:
     ```python
     S = ("mean.R", "mean.G", "mean.B", "structure_std", "pattern_corr", "lag1.x", "lag1.y")
     from painterly_analysis import ensemble as e, metrics
     keys = [f"r{r}.{s}" for r in (0, 1, 2, 3, 4, 5, 6, 7, 9) for s in S] + [
         "all.pattern_corr", "all.block_rmse", "all.clip_fraction", "all.spectral_slope"]
     d = metrics.diffuse_key_family(keys)
     f = metrics.realization_free_key_family(d)
     print("diffuse", len(d), "realization_free", len(f),
           "r3-r7", len([k for k in f if k.split(".")[0] in {"r3", "r4", "r5", "r6", "r7"}]))
     print("min_attainable", repr(e.min_attainable_pvalue(8, 8, "two-sided")),
           "alpha/26", repr(e.DEFAULT_ALPHA / 26), "alpha/20", repr(e.DEFAULT_ALPHA / 20))
     ```
     ```
     diffuse 46 realization_free 26 r3-r7 20
     min_attainable 0.0001554001554001554 alpha/26 0.0003846153846153846 alpha/20 0.0005
     ```
     The regions are the nine SPEC §9 ids the camera sees — every id except the light (9), which
     `diffuse_key_family` drops anyway, and the front plane (8), which is behind the camera (`T5.4:68`); each region
     carries `measure`'s seven keys and `measure` adds four `all.*` keys (`metrics.py:394-412`), so the measured map
     holds `9 × 7 + 4 = 67` keys. `diffuse_key_family` keeps ids 2-8 (`metrics.py:30`, `:416-432`) = `6 × 7 + 4 = 46`,
     and `realization_free_key_family` keeps `.mean.R`, `.mean.G`, `.mean.B`, `.structure_std` and
     `all.clip_fraction` (`metrics.py:436-457`) = `6 × 4 + 2 = 26`, of which the `r3`-`r7` regions give `5 × 4 = 20`.
     - The power guard of `compare_ensembles` (`ensemble.py:312-318`) compares the smallest attainable p-value of
       two 8-run ensembles, `0.0001554001554001554` = `2 / C(16,8)`, with the first Holm threshold
       `0.01 / 26 = 0.0003846153846153846`: it passes, so the call runs. The hard assertion of `T5.4:68-71` covers the
       20 `r3`-`r7` keys, whose own first threshold is `0.01 / 20 = 0.0005`.
     - These are the band's numbers, not B11's: this card changes none of them, and a run that rejects a key is a
       finding to report, never a reason to re-derive the band (BRIEF.md:270-271, `AGENTS.md`).
2. Read T5.4's three files and confirm the two facts the rest of this card rests on: the generator authors every
   material with `material.use_nodes = True` and one shader node linked to the Material Output (so the `.blend`
   already carries node trees, and what B11 changes is which nodes they hold), and the light is a
   `bpy.data.lights.new(..., type="POINT")`, not a material. If either is not so, stop and report: the card's
   premise is T5.4's `.blend`.
3. Confirm the three node types' sockets against the vendored definitions, because step 5 writes them and step 6
   pins them. The three rows, as B8's table will hold them:
   ```
   principled_bsdf: in Base Color, Metallic, Roughness, IOR, Alpha, Thin Wall, Normal, Diffuse Roughness,
                    Subsurface Weight, Subsurface Radius, Subsurface Scale, Subsurface IOR,
                    Subsurface Anisotropy, Specular IOR Level, Specular Tint, Anisotropic,
                    Anisotropic Rotation, Tangent, Transmission Weight, Coat Weight, Coat Roughness,
                    Coat IOR, Coat Tint, Coat Normal, Sheen Weight, Sheen Roughness, Sheen Tint,
                    Emission Color, Emission Strength, Thin Film Thickness, Thin Film IOR,
                    SurfaceMixWeight (SVM_INTERNAL); out BSDF
   diffuse_bsdf:    in Color, Normal, SurfaceMixWeight (SVM_INTERNAL), Roughness; out BSDF
   emission:        in Color, Strength, SurfaceMixWeight, VolumeMixWeight (SVM_INTERNAL); out Emission
   ```
   (`PrincipledBsdfNode.inc:21-62`, `DiffuseBsdfNode.inc:5-10`, `EmissionNode.inc:5-10`.) The `SVM_INTERNAL` inputs
   are set by the compiler and never exported (`B8-node-table-export.md:377-380`, `:584-589`).
4. Measure the two bpy facts step 5 and step 6 rest on, with this probe (save it under `/tmp` and run it with
   `.venv/bin/python <file>`; it must print exactly the lines quoted after it — this card's measurement on bpy
   5.2.2):
   ```python
   import bpy

   def principled(name, base, **values):
       material = bpy.data.materials.new(name)
       tree = material.node_tree
       tree.nodes.clear()
       output = tree.nodes.new("ShaderNodeOutputMaterial")
       output.name = "output"
       node = tree.nodes.new("ShaderNodeBsdfPrincipled")
       node.name = "shader"
       node.inputs["Base Color"].default_value = (*base, 1.0)
       for key, value in values.items():
           node.inputs[key].default_value = value
       tree.links.new(node.outputs["BSDF"], output.inputs["Surface"])
       return material, node

   material, node = principled("probe", (1.0, 1.0, 1.0), Metallic=1.0, Roughness=0.0)
   print("mirror Base Color:", tuple(node.inputs["Base Color"].default_value))
   print("Specular IOR Level:", node.inputs["Specular IOR Level"].default_value)
   print("distribution:", node.distribution, "| subsurface_method:", node.subsurface_method)
   print("enum ids:", [i.identifier for i in node.bl_rna.properties["distribution"].enum_items],
         [i.identifier for i in node.bl_rna.properties["subsurface_method"].enum_items])

   material, node = principled("probe2", (6.0 / 10, 6.0 / 10, 6.0 / 10), Roughness=0.0)
   print("a plane's Base Color:", tuple(node.inputs["Base Color"].default_value))

   diffuse = bpy.data.materials.new("probe3")
   tree = diffuse.node_tree
   tree.nodes.clear()
   tree.nodes.new("ShaderNodeOutputMaterial")
   shader = tree.nodes.new("ShaderNodeBsdfDiffuse")
   shader.inputs["Color"].default_value = (4.0 / 10, 4.0 / 10, 12.0 / 10, 1.0)
   print("a diffuse Color:", tuple(shader.inputs["Color"].default_value),
         "| Roughness:", shader.inputs["Roughness"].default_value)
   print("diffuse inputs:", [(s.identifier, s.type, s.is_unavailable) for s in shader.inputs])

   emission = bpy.data.materials.new("probe4")
   tree = emission.node_tree
   tree.nodes.clear()
   tree.nodes.new("ShaderNodeOutputMaterial")
   shader = tree.nodes.new("ShaderNodeEmission")
   shader.inputs["Strength"].default_value = 120.0
   print("an emission Strength:", shader.inputs["Strength"].default_value,
         "| Color:", tuple(shader.inputs["Color"].default_value))
   print("emission inputs:", [(s.identifier, s.type, s.is_unavailable) for s in shader.inputs])

   light = bpy.data.lights.new("probe light", type="POINT")
   print("a point light has node_tree:", hasattr(light, "node_tree"),
         "| material slots:", hasattr(light, "material_slots"))
   ```
   ```
   mirror Base Color: (1.0, 1.0, 1.0, 1.0)
   Specular IOR Level: 0.5
   distribution: MULTI_GGX | subsurface_method: RANDOM_WALK
   enum ids: ['GGX', 'MULTI_GGX'] ['BURLEY', 'RANDOM_WALK', 'RANDOM_WALK_SKIN', 'RANDOM_WALK_LEGACY']
   a plane's Base Color: (0.6000000238418579, 0.6000000238418579, 0.6000000238418579, 1.0)
   a diffuse Color: (0.4000000059604645, 0.4000000059604645, 1.2000000476837158, 1.0) | Roughness: 0.0
   diffuse inputs: [('Color', 'RGBA', False), ('Roughness', 'VALUE', False), ('Normal', 'VECTOR', False), ('Weight', 'VALUE', True)]
   an emission Strength: 120.0 | Color: (1.0, 1.0, 1.0, 1.0)
   emission inputs: [('Color', 'RGBA', False), ('Strength', 'VALUE', False), ('Weight', 'VALUE', True)]
   a point light has node_tree: True | material slots: False
   ```
   What each line fixes:
   - A socket stores float32: `cl/10` written as a Python double reads back widened, `0.6 -> 0.6000000238418579`,
     `1.2 -> 1.2000000476837158`. Both material paths read this same value, which is why step 6's comparison is
     exact (step 5's derivation of the two paths' lobes).
   - `Specular IOR Level` defaults to 0.5, so a Principled BSDF written without it is *not* a bare diffuse lobe
     (step 5's derivation); `Weight` is `is_unavailable` on all three nodes and is never exported.
   - `distribution` is `MULTI_GGX` and `subsurface_method` is `RANDOM_WALK`, so B8's parameter export carries
     `{"distribution": "multi_ggx", "subsurface_method": "random_walk"}` (`PrincipledBsdfNode.inc:5-19`; the two
     enum names are the lowercase `NodeEnum` names, B8's rule 3).
   - A point light has a node tree but no material slot, so the reference scene's light has no material to author
     and stays the constant ghost material `sync_lights` builds (`T5.3:8-16`).
5. `tools/make_reference_scene.py`, the material authoring. Give each SPEC §9 object the node whose lobe list is the
   reference's, and derive each from the closure code:
   - **Mirror sphere, object 0** (`docs/spec.md:299`, `reference.py:47`): `ShaderNodeBsdfPrincipled` with
     `Base Color` = (1, 1, 1), `Metallic` 1, `Roughness` 0. Derivation: the Metallic layer allocates an F82
     conductor of `weight = metallic × weight = 1` and its payload `f0 = clamped_base_color` (`closure.h:320-352`);
     `painterly_svm_reflection_color` returns that `f0` for `F82_TINT` (`collect.h:107-127`), so the mirror lobe is
     `1 × (1,1,1)` — smallpaint's mirror, which adds the child radiance unchanged (SPEC §6; `T5.4:22-23`). Pinned by
     `test_cycles_svm_closures.cpp:671-676`.
   - **Glass sphere, object 1** (`docs/spec.md:300`, `reference.py:48`): `ShaderNodeBsdfPrincipled` with
     `Base Color` = (1, 1, 1), `Transmission Weight` 1, `IOR` 1.5, `Roughness` 0. Derivation: the transmission layer
     allocates a GGX glass of `weight = 1` whose `bsdf->ior` is `IOR` and whose transmission tint is
     `sqrt(clamped_base_color)` (`closure.h:362-410`); `painterly_svm_transmission_color` returns that tint
     (`collect.h:133-142`), so the glass lobe is weight `1 × 1 = 1` with `ior = double(1.5f)` = 1.5. Pinned by
     `test_cycles_svm_closures.cpp:679-682`.
   - **The seven diffuse objects, objects 2-8** (`docs/spec.md:301-307`, `reference.py:49-55`):
     `ShaderNodeBsdfDiffuse` with `Color` = `cl/10` and `Roughness` 0. Derivation: `CLOSURE_BSDF_DIFFUSE_ID`
     allocates one diffuse closure of `closure_weight × mix_weight` (`closure.h:524-540`), the node's unlinked `Color`
     becomes `NODE_CLOSURE_SET_WEIGHT` (`BsdfNode.compile-SVMCompiler_compiler.inc:12-18`), and the collector's
     diffuse lobe takes the closure weight (`collect.h:200-202`), so the lobe is `cl/10` as the float32 socket —
     `0.4, 0.4, 1.2` for the blue sphere (step 4). Pinned by `test_cycles_svm_closures.cpp:359-384`.
     - **This is the change T5.4's generator needs, and its reason.** T5.4 authors these objects as Principled BSDFs
       (`T5.4:20`). Under the SVM that node is not a bare diffuse lobe: with `Specular IOR Level` at its default 0.5,
       `f0 = F0_from_ior(1.5)` (no scaling, because the level *is* 0.5, `closure.h:426-435`), the specular layer is
       allocated whenever `eta != 1` (`:438`), and the diffuse layer is attenuated by `closure_layering_weight` =
       `1 - F` (`:468-470`, `bsdf_util.h:440-444`). Step 5's derivation script measures that `f0`:
       ```
       $ .venv/bin/python -c 'import numpy as np; f=np.float32(1.5); f0=np.float32(((f-np.float32(1))/(f+np.float32(1)))**2); print(repr(float(f0)))'
       0.04000000283122063
       ```
       So a Principled diffuse surface would gain a mirror lobe of `0.04000000283122063` and lose 4% of its diffuse
       weight — a different look from SPEC §9's single diffuse lobe, and a *different* lobe list from M5's constant
       mapping, which is what step 6 compares. `Specular IOR Level` 0 would also work (`f0 = 0`, `eta =
       ior_from_F0(0) = 1`, no specular layer: `closure.h:429-438`, pinned by
       `test_cycles_svm_closures.cpp:664-669`); the Diffuse BSDF is chosen because BRIEF.md:267-269 names it and
       because it has no second layer to keep at zero.
   - **The light, object 9** (`docs/spec.md:308`, `reference.py:56`): no material authoring. It is a point light,
     `sync_lights` makes it a ghost sphere with `add_material([("diffuse", (0.0, 0.0, 0.0), 0.0)], emission =
     color·energy·emission_scale)` (`T5.3:8-16`), and BRIEF.md:297-298 keeps light node graphs out of v1. The
     Emission node's equivalence to that constant material is step 6's seventh test, on a scene this card builds
     itself; `## Open for Opus` 2 names what putting it in the `.blend` would take.
   - Every other value T5.4's generator writes stays: the geometry, the camera, the knobs and the
     generation-time assertion (`T5.4:17-30`), and `Roughness` 0 on every node (`T5.4:22`). The materials' names are
     unchanged, so `stats.object_ids` and T5.4's object-id check (`:72-80`) see the same objects.
   - No new knob (BRIEF.md:75-77): the node values are SPEC §9's `cl/10`, which T5.4 already writes, and no socket of
     `PainterlyIntegrator` is added or changed.
6. `tests/blender/test_reference_node_materials.py`, seven tests. It runs under `make test-blender`, so `bpy` is
   present and `_painterly` is built; it imports the add-on as the package `painterly`
   (`tests/blender/conftest.py:44-53`). The three export tests build their material in memory and need no `.blend`;
   the three `build_scene` tests open the generated scene (below). Every comparison is exact (`==` on tuples and
   dicts, `memcmp` on the images); no tolerance appears anywhere.
   - **The three export tests** — `test_the_mirror_material_exports_one_principled_node`,
     `test_the_glass_material_exports_one_principled_node`, `test_the_diffuse_material_exports_one_diffuse_node`.
     Each builds step 5's node for that kind, calls `export_graph(flatten_tree(tree))` (B8's functions) and compares
     with a literal. The values below were produced by a prototype of B8's step 6 rules against bpy 5.2.2 (this
     card's measurement; the prototype applies B8's row, default and link rules, and its output is quoted in full for
     the three cases):
     ```
     mirror, principled_bsdf:
       params {'distribution': 'multi_ggx', 'subsurface_method': 'random_walk'}
       defaults (30) Base Color (1.0, 1.0, 1.0) | Metallic 1.0 | Roughness 0.0 | IOR 1.5 | Alpha 1.0
                     Thin Wall False | Normal (0.0, 0.0, 0.0) | Diffuse Roughness 0.0
                     Subsurface Weight 0.0 | Subsurface Radius (1.0, 0.20000000298023224, 0.10000000149011612)
                     Subsurface Scale 0.004999999888241291 | Subsurface Anisotropy 0.0
                     Specular IOR Level 0.5 | Specular Tint (1.0, 1.0, 1.0) | Anisotropic 0.0
                     Anisotropic Rotation 0.0 | Tangent (0.0, 0.0, 0.0) | Transmission Weight 0.0
                     Coat Weight 0.0 | Coat Roughness 0.029999999329447746 | Coat IOR 1.5
                     Coat Tint (1.0, 1.0, 1.0) | Coat Normal (0.0, 0.0, 0.0) | Sheen Weight 0.0
                     Sheen Roughness 0.5 | Sheen Tint (1.0, 1.0, 1.0) | Emission Color (1.0, 1.0, 1.0)
                     Emission Strength 0.0 | Thin Film Thickness 0.0 | Thin Film IOR 1.3300000429153442
       links [(0, 'BSDF', -1, 'Surface')]
     glass, principled_bsdf: the same 30 keys, with Transmission Weight 1.0 and Metallic 0.0
       links [(0, 'BSDF', -1, 'Surface')]
     diffuse, diffuse_bsdf:
       params {}
       defaults (3) Color (0.4000000059604645, 0.4000000059604645, 1.2000000476837158) | Roughness 0.0
                    Normal (0.0, 0.0, 0.0)
       links [(0, 'BSDF', -1, 'Surface')]
     ```
     The test asserts three things per case, each exact: the Cycles type name, the parameter dict, and the number of
     exported defaults (`30` for Principled, `3` for Diffuse — so a row that gains or loses a socket fails), plus the
     values of the keys the lobes depend on — `Base Color`, `Metallic`, `Roughness`, `IOR`, `Alpha`, `Thin Wall`,
     `Specular IOR Level`, `Transmission Weight` for Principled and `Color`, `Roughness` for Diffuse — and the link
     list. The other Principled defaults are B8's export machinery's business and are pinned by B8's own tests on
     small trees; this card pins the count and the lobe-relevant values.
     - `Thin Wall` is `False`: Blender's socket is `BOOLEAN` and B8's `_default_of` maps `BOOLEAN` to `bool`
       (`B8-node-table-export.md:501`), so the test writes `False`. (`False == 0` in Python, so a `0` would compare
       equal; the literal states the type the row's mapping gives.)
     - `Roughness` 0.0 on the mirror and glass: T5.4's generator already writes it (`T5.4:22`), and it keeps the GGX
       albedo estimate at the smooth end so the lobe weight is the payload's `f0` unchanged.
   - **`test_the_node_material_scene_renders_bit_for_bit_like_the_constant_mapping`.** The scene is T5.4's own
     `.blend`, so the test opens it with `bpy.ops.wm.open_mainfile(filepath=...)` on `build/scenes/smallpaint_reference.blend`
     and takes the depsgraph with `bpy.context.evaluated_depsgraph_get()`. When that file is missing the test skips
     with the reason "run `make reference-blend`", exactly as `test_extension_it.py:88-102` skips without its zip;
     acceptance 2 produces it, so the card's own run never skips. `build_scene`'s `stats` out-parameter is T5.2's
     (`docs/tasks/M5/T5.2-sync-geometry.md:48-55`), and B8 passes it to `MaterialTable` and `sync_world`
     (`B8-node-table-export.md:567-570`). Then:
     1. `stats = SyncStats()`; `core_node = sync.build_scene(depsgraph, scene.painterly, SIZE, SIZE, stats=stats)`
        with B8's node path live — the material graphs of step 5 exported through `export_material`;
     2. `core_constant = sync.build_scene(...)` with the constant path forced by B8's own device,
        `monkeypatch.setattr(material_module, "export_material", _raise_unknown)` (B8's E12,
        `B8-node-table-export.md:684-686`), so every material falls back to T5.3's constant mapping;
     3. render both with `_painterly.Session(core, 1)`, `start(PASSES, 1)`, `wait()`, `combined()` and
        `k_consumed()`, at `SIZE = 100` and `PASSES = 4` — BRIEF.md:174 fixes 100 px and 4 passes for an exact
        comparison, and one thread because `Session(core, 1)` is one sequence (SPEC §3);
     4. `CHECK` that both `combined()` arrays are non-zero (so a scene that renders nothing cannot pass), that their
        `tobytes()` are equal, and that their `k_consumed()` bit patterns are equal.
     Why it is exact: both sides read the same bpy sockets (step 4), and the derivations of step 5 give both sides the
     same lobe list, the same emission and the same lobe kinds — so the two device scenes hold the same
     `KernelPainterlyMaterial` arrays and the two renders are the same sequence of the same arithmetic.
   - **`test_the_node_path_reports_no_fallback_warning`.** A second `build_scene` call on the same opened scene
     (step 1's), with a fresh `SyncStats()`, and
     `stats.warnings == []`. This is what makes the parity a node-material parity: a missing row (N11, N12) or an
     unsupported node would fall back to M5's constant mapping with a warning (`B8-node-table-export.md:535-551`),
     the render would still be exact (the constant mapping gives the same lobes for these materials), and the
     statistical test would pass while testing nothing new. The two tests together cannot pass vacuously: the warning
     list is empty only on the node path, and nine on the constant path (next test).
   - **`test_the_constant_path_warns_once_per_material`.** A third `build_scene` call with B8's patch of 2 gives
     exactly nine material warnings: the entries that end in `uses the constant mapping`
     (`B8-node-table-export.md:543-548`) number `9`, and their material names are the nine names the test's fixture
     authors, in object order, each exactly once. SPEC §9 has ten rows and the tenth is the light, whose material
     `sync_lights` builds with `add_material` and never through `MaterialTable` (`T5.3:8-16`, `docs/spec.md:299-308`),
     so no warning names it.
     - Why nine and not ten: the world is a separate entry point, `sync_world` (`T5.3:27-31`), and B8 gives its
       fallback its own message, `f"{error}; {world.name} uses world.color"`
       (`B8-node-table-export.md:558`). A `.blend` whose world has a node tree therefore adds one warning that is
       not a material's; the test counts only the nine material ones and asserts nothing about the world's, because
       T5.4's card does not fix whether the reference scene has a world (SPEC §9's scene is closed and never misses,
       `docs/spec.md:169`). `## Open for Opus` 6 names it.
   - **`test_the_light_is_an_emission_node_material_with_the_constant_light_lobe_list`.** The reference scene's only
     emitter, built without Blender. Build SPEC §9 twice at 100 px by walking `reference.REFERENCE_SCENE`
     (`reference.py:46-57`) exactly as `reference.build_smallpaint_scene` does (`:130-138`): `material_of` for objects
     0-8 and the same `add_sphere`/`add_plane` calls with the same object ids, the ghost policy `"all"`
     (`:124-128`), `set_camera_smallpaint(100, 100)` and `set_integrator(**reference.apply_reference_knobs())`
     (`:141`, `:143`). The two scenes differ in object 9 only:
     - scene A, the constant light, is `add_material(lobes=[("diffuse", (0.0, 0.0, 0.0), 0.0)],
       emission=LIGHT_EMISSION)` — `material_of`'s `"light"` branch (`reference.py:99-105`), with
       `LIGHT_EMISSION = (120.0, 120.0, 120.0)` (`:34`) and `docs/spec.md:308`;
     - scene B's object 9 is `scene.add_node_material(scene.add_shader(nodes, links))` with B6's lists for an
       Emission node, `[("emission", {}, {"Color": (1.0, 1.0, 1.0), "Strength": 120.0})]` and
       `[(0, "Emission", -1, "Surface")]`.
     Render both with `_painterly.Session(scene, 1)` at `PASSES = 4` and compare `combined()` and `k_consumed()`
     bit for bit, after `CHECK`ing that `combined()` holds a non-zero value. Why the two agree: the node's emission
     is `Color × Strength = (120, 120, 120)` (`EmissionNode.compile-SVMCompiler.inc:14-27`, the constant branch) and
     it allocates no closure, so `painterly_svm_collect`'s zero-closure fallback gives one black diffuse lobe
     (`collect.h:205-210`) — exactly scene A's material. `test_cycles_svm_closures.cpp:536-542` pins the same
     equality for the node alone (`num_closure == 0`, one diffuse lobe of weight 0, emission `(1, 2, 4)` for its
     `Color × Strength`). `Strength` 120 rather than 0 matters: an Emission of strength 0 is constant-folded away
     (`EmissionNode.constant_fold.inc:1-9`), and the graph would then be a different one.
     - Why not `build_smallpaint_scene` itself: it fixes every material through `material_of` (`:131`) and has no
       way to substitute one, and this card may not change `reference.py` (`## Do not touch`). The walk above is its
       body, so the two scenes are the reference scene's by construction; the test's docstring says so and cites the
       lines it copies.
   - The file's header comment states, as `test_path_trace.cpp:4-12` does, that every comparison is exact
     (`memcmp` on the images, `==` on the exported lists) and that no tolerance appears.
   - The two image tests are fast: 100 × 100 × 4 paths per render, four renders in all (two per test), at
     `max_depth` 20; if the file's duration exceeds about 10 s, mark the two image tests `@pytest.mark.slow`
     (CLAUDE.md rule 6) and say so in the answer. The export tests need no marker.
7. Run `.venv/bin/ruff format` on the new test file and `tools/make_reference_scene.py`, then `.venv/bin/ruff check .`,
   then every acceptance command.

## Acceptance

Run every command from the repository root; the queue translates them with BACKLOG.md's table (`make check` →
`CHECK`, `make test-blender` → the same target with `KNOBS`, `build/dev` → `build/q`, `.venv/bin/<tool>` →
`MAIN/.venv/bin/<tool>`, `make reference-blend` and `make blender-it` → the same targets with `KNOBS` and `BLENDER`).
1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and the audit's
   `RESULT: PASS` line. B11 adds no doctest and no core line, so the doctest counts are the tree's and must not move;
   if they do, the diff has touched something outside `## Create` and `## Modify`.
2. `make reference-blend` exits 0 and writes `build/scenes/smallpaint_reference.blend`. Report the file's size and
   the generation-time socket assertion's silence (`T5.4:26-28`: `integrator_sockets()` gives 1.0, 1.0 and
   `"camera"`). If the target does not exist, T5.4 has not landed: report that instead of running anything else.
3. `.venv/bin/python -m pytest -q tests/blender/test_reference_node_materials.py` prints `7 passed`: step 6's three
   export tests, its three `build_scene` tests (the exact image comparison, the no-warning test and the warning
   count) and its one light test, `3 + 3 + 1 = 7`. The count is the number of test functions step 6 lists, and the run
   must print it; if it prints another count, the card's count is wrong and that is a finding, not a tolerance.
   Report the duration and whether the two image tests needed `@pytest.mark.slow`.
4. `make test-blender` exits 0. Report its last line: T5.4's Blender tests, M5's and B7's and B8's all still pass,
   and the new file is collected.
5. `make blender-it` — **host-only, not run**: it needs the extension zip, which `make wheel` builds (`uv`, absent
   offline), and it renders 16 half renders at 400 px × 32 passes plus the oracle ensemble. When it runs, report:
   - its last line, and that `tests/blender_it/test_reference_blend.py` passed **unchanged** — the acceptance of
     BRIEF.md:270-271;
   - the per-key table's key count and the smallest p-value, with the first Holm threshold it is compared with
     (`0.01 / 26 = 0.0003846153846153846` for the call's 26-key family, step 1), and whether any `r3`-`r7` key was
     rejected (`T5.4:68-71`: none may be);
   - the duration, measured, not estimated.
   A rejection is reported as a finding. Nothing in this card may be changed to make it pass: the band is the
   ensemble's, and re-deriving it from the node path's output is exactly what BRIEF.md:270-271 forbids.
6. `git status --porcelain` lists only the one Create path and the one Modify path above.

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- author the diffuse objects as Principled BSDFs with `Specular IOR Level` left at 0.5 → the node path gains a
  mirror lobe of `0.04000000283122063` and attenuates the diffuse lobe to `Base Color × (1 - F)`, so acceptance 3
  fails on `test_the_node_material_scene_renders_bit_for_bit_like_the_constant_mapping` and on the diffuse export
  test (`principled_bsdf`, not `diffuse_bsdf`);
- set `Metallic` 1 on a diffuse object → one mirror lobe instead of one diffuse lobe, so the same two tests fail and
  `k_consumed()` differs (a mirror bounce draws no K, SPEC §2, `docs/spec.md:51`);
- set the mirror sphere's `Metallic` to 0 → a specular layer of `f0` plus a diffuse layer, so the mirror export test
  fails on `Metallic` and the image test fails;
- give the Emission graph `Strength` 119.0 → `test_the_light_is_an_emission_node_material_with_the_constant_light_lobe_list`
  fails on the emission `(119, 119, 119)` against `LIGHT_EMISSION`'s `(120, 120, 120)`;
- delete the `ShaderNodeBsdfDiffuse` row from `node_table.py` → the sync falls back with a warning, so
  `test_the_node_path_reports_no_fallback_warning` fails and the constant-path warning count becomes 9 while the
  "node" scene is the constant one;
- let the constant path run unpatched → `test_the_node_path_reports_no_fallback_warning` fails on nine warnings, and
  the image test compares a scene with itself, so it cannot tell the two paths apart; that is why the three
  `build_scene` tests are one card.

Report: acceptance 1's four counts and the audit line, acceptance 2's file size, acceptance 3's duration and
marker decision, acceptance 4's last line, acceptance 5 as "host-only, not run", and every mutation you ran with its
first failing check.

## Commit

`B11: node-material parity on the reference scene: the .blend's materials as Principled, Diffuse and Emission graphs`

## Open for Opus

1. **The brief's `Needs` line is one line, and the card needs four.** BRIEF.md:272 says "Needs: batches 11 and 12, M5
   T5.4". The parity is a *node-material* parity, so it also needs B8: without the export (`export_material`,
   `MaterialTable`'s node path, `SyncStats.warnings`) the sync has no node path at all, and B8 is in turn
   `Depends on: B5, B6, B7` (`BRIEF.md:235`), which reaches B1-B4. This card's `Depends on:` line names B8, N11, N12
   and M5-T5.4 — B8 transitively covers B1-B7, and M5-T5.4 covers M5 T5.1-T5.3. Option (b) is to keep the brief's
   three and let B11's preconditions discover B8; that is what an unlisted dependency looks like when it lands late,
   so this card names it. Nothing else changes either way.
2. **The brief asks for an Emission node material on a scene whose only emitter is a light.** BRIEF.md:267-269 names
   Principled, Diffuse *and* Emission; BRIEF.md:297-298 keeps light node graphs out of v1 ("lights stay ghost spheres
   with constant emission"), and SPEC §5 makes the reference scene's only emitter a point light
   (`docs/spec.md:158`, `:212`, `:308`), which `sync_lights` builds with a constant material (`T5.3:8-16`). So the
   reference `.blend` cannot carry an Emission node material without deciding :297-298. This card's step 6 exercises
   the Emission node on the same scene's light, built through B6's Python API, and proves it bit-identical to the
   constant light material. The options:
   - (a) keep this card's reading — the `.blend` has Principled and Diffuse node materials, and Emission is proved
     equivalent in the exact test;
   - (b) rule that a light's node tree is exported: then `sync_lights` gains a node path (a card of its own, because
     `sync_lights` is T5.3's and outside B11's files), and the `.blend`'s light carries an Emission node whose
     `Color × Strength` is `color·energy·emission_scale`;
   - (c) add an emissive object to the reference scene so an Emission node material is in the parity. This card does
     not take (c): it changes SPEC §9's ten objects, and the oracle ensemble renders those ten
     (`src/app/smallpaint_oracle.cpp`'s GUI scene), so the parity would no longer compare the same scene.
3. **The seed block of the statistical test is T5.4's, and a fresh one would be 79.** T5.4:49-50 fixes "8 pairs (seeds
   via `seed`)" and leaves the block to its implementation; B11 does not move it (BRIEF.md:270-271: the test is
   unchanged). If Opus wants a fresh block for the node-material run — the stronger evidence, since a spent block has
   been seen — the rule gives 79: the blocks a committed test or experiment already spends are 46-67
   (`experiments/009-2026-10-15-scale-limits/README.md:69`), 68 (`tests/core/test_triangle_path.py:116`, `SEED_BLOCK
   = 68`) and 69-78 (`tests/core/test_triangle_path.py:23`, M3-FIX-T3.17a's fixed fresh set), so the first free block
   is 79 and the base seed is `16 × 79 = 1264` (`SEEDS_PER_BLOCK = 16`, `test_triangle_path.py:117`). That is one
   constant in T5.4's file plus a second ensemble run of 16 renders at 400 px × 32 passes; it is not this card's to
   make, and it changes no decision rule.
4. **Two of the three node types' lobe lists depend on inputs this card must keep at a value.** The mirror's lobe is
   the Metallic layer's payload `f0 = Base Color` and the glass's is `sqrt(Base Color) × Transmission Weight`
   (`closure.h:320-352`, `:362-410`), so `Base Color` (1, 1, 1) is what makes them smallpaint's unit tints. The
   diffuse objects' Diffuse BSDF has no second layer, which is why step 5 moves them off Principled; `Specular IOR
   Level` 0 would reach the same lobe list on a Principled node (`closure.h:426-438`,
   `test_cycles_svm_closures.cpp:664-669`). Option (b) keeps Principled everywhere with the level at 0; it changes one
   node type in the `.blend` and two expected values in step 6's export tests, and nothing else. This card takes the
   Diffuse BSDF because BRIEF.md:267-269 names it and because it has no layer to keep at zero.
5. **The world of the reference `.blend`.** T5.4's card fixes the camera, the objects, the lights and the scene
   settings, and says nothing about the world; SPEC §9's scene is closed and never misses (`docs/spec.md:169`), so the
   world contributes no radiance either way. B5 and B8 give a world with a Background node a node path and a constant
   world a fallback (`B8-node-table-export.md:552-559`), and this card's step 6 counts only the nine material warnings
   for that reason. If Opus wants the world pinned — "the generator clears the world, so `sync_world` takes T5.3's
   `world.color` branch with no warning", or "the generator writes a Background node of colour (0, 0, 0)" — it is one
   line in `tools/make_reference_scene.py` and one assertion in step 6's third test. It changes nothing about the
   parity, because no ray misses.
6. **What this card cannot show about the SVM path itself.** Step 6's exact comparison proves that the two material
   paths of the reference scene agree; it cannot prove that either equals Cycles' own shading of the same graph — that
   is B4's per-lobe work and, for the images, B9's golden harness (BRIEF.md:237-255). The statistical test proves the
   reference look against the oracle, on the ensemble's band, and nothing about a node outside these three. The
   card says so in the test file's header comment rather than implying more.
