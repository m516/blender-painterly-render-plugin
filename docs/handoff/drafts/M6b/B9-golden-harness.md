# B9 — The golden-test harness (drafted from BRIEF.md section 2, "B9")

Milestone: M6b · Depends on: B8, B5 · Parallel-safe: no

Drafted from `docs/handoff/drafts/M6b/BRIEF.md` section 2, "B9" (lines 237-255), per that brief's section 4
(lines 303-324) and the decisions of its section 1 that bind it: decision 9 (:78-79) makes the comparison a rule whose
statistic is measured from Cycles alone, and decision 8 (:75-77) forbids a new knob, so the harness sets only sockets that
already exist. Code facts are `docs/handoff/drafts/M6b/FACTS.md` §1.1 (plan.md:305 and :353), §1.3 (SPEC §8), §3.10 (the
session) and §6 gap 7 (what the golden harness left undefined), re-read at this clone's HEAD in every file cited below.
Every Cycles-side number in this card is measured by the script of step 4 on this host with Blender 5.2.2, and the card
quotes that script's command and its `lever_set.json`.

`BRIEF.md` gives B9 five scope bullets (:238-246) and the comparison rule (:247-252); this card turns them into one
scene, one measurement and one decision, and gives each its own file and its own acceptance.

## Goal

`tests/blender_it/` renders one node golden scene in both engines and decides it with a rule that was fixed before any
painterly render of it existed:

- **A generated scene per node** (BRIEF.md:239): an emission plane driven by the node, and an orthographic camera at
  pixel centres. `tests/blender_it/golden_scenes.py` builds it; `GOLDEN_SCENES` maps a node's name to its builder, so a
  node batch card adds one entry and its test (BRIEF.md:283). B9 adds one entry, `texcoord_generated`: an Emission of
  Texture Coordinate's Generated output, which is the scene `BRIEF.md:253-254` names and the three rows B8 adds
  (Material Output, Emission, Texture Coordinate) drive.
- **The two engine configurations** (BRIEF.md:240-244): Cycles at 1 sample, Raw view transform, a float32 OpenEXR, at the
  smallest pixel filter width; painterly at `max_depth=1`, `emission_gain=1`, `jitter=0`, `output_mode="scene_linear"`,
  exposure 1, one pass, and no debug path. The harness compares in painterly's output space: it applies
  `film.scene_linear` (SPEC §8, `spec.md:279`) to Cycles' float32 values with the same operations in the same order
  (BRIEF.md:243-244).
- **A per-pixel decision rule, pre-registered as experiment X-golden** (BRIEF.md:247-252), whose band is measured from
  Cycles renders alone: `experiments/NNN-<DATE>-golden/lever_set.json`'s `rule.band` is `2.0**-30`
  (`9.313225746154785e-10`), the largest per-pixel spread over the registered lever set of step 4. `golden_rule.py` holds
  that number as `BAND` and the decision as one comparison.
- **The harness in `make blender-it`** (plan.md:353): the target already collects `tests/blender_it` (`Makefile:91-92`), so
  the card adds a file, not a target, and the slow test renders both sides through the installed extension as
  `test_extension_it.py` does.

Nothing in the core changes, and no knob is added: the golden knobs are `PainterlyIntegrator` sockets
(`src/painterly/scene/integrator.cpp:41-85`), so no image, no K and no parity test moves.

## Read first

- `CLAUDE.md` rules 1, 2, 3 and 6 (scope; no magic numbers; PEP 8 with type hints and units; deterministic tests, `slow`
  above about 10 s); `AGENTS.md` "Expected values are evidence, not targets" and "Pre-registered experiments" (the rule is
  frozen at approval and is never re-fitted to painterly's output); `AGENTS.md` "Measured means reproducible" (a script
  that produces a committed number is committed next to its output, with the command that regenerates it).
- `docs/handoff/drafts/M6b/BRIEF.md` lines 237-255 (this card's mandate: the scene, the two configurations, the rule),
  :221-235 (B8, whose three node-table rows the scene uses), :78-79 (decision 9) and :303-324 (how this card was drafted).
- `docs/handoff/drafts/M6b/FACTS.md` §1.1 (`plan.md:305`'s golden-test sentence, verbatim, and `:353`'s `make blender-it`
  list), §1.3 (the knob table's film and path rows, `spec.md:287-291`) and §3.12 (the add-on's modules, with the session's
  render loop and `film.py`), and §6 gap 7 (the golden harness's undefined points: the pixel centre, how the spread is
  measured, the filter, constant folding).
- `docs/plan.md:305` (the acceptance sentence: "a generated `.blend` with an emission plane driven by the node, rendered
  by Cycles at 1 spp (pixel centre, Raw, EXR) vs Painterly with knobs `max_depth=1, emission_gain=1`, with no debug code
  paths; equal within Cycles' own float32 spread") and `:348-354` ("render node golden scenes against Cycles").
- `docs/spec.md:277-280` (`scene_linear` is `L/255 · exposure`; the engine never changes the view transform) and `:287-291`
  (the knob table's film and path rows). `docs/spec.md:168-171` (a hit adds `E·emission_gain` first, then the lobe) and
  `:244-250` (`jitter` is a fraction of the fitted side, so `jitter=0` puts the ray on the pixel centre).
- `src/blender/addon/film.py`: `BYTE_MAX` `:43`, `scene_linear` `:99-112` (`:111` is the operation order this card
  copies), `to_blender_rows` `:115-128` (row 0 is the top in the core and the bottom in Blender).
- `src/blender/addon/session.py`: `_write_result` `:91-107` (`:101-102` the `scene_linear` branch, `:106` the row flip into
  the Render Result), `render` `:110-197` (the render loop the extension runs).
- `src/painterly/kernel/camera/camera.h`: `PAINTERLY_RASTER_PIXEL_CENTRE` `:25`, the orthographic ray `:110-131` (`:110-111`
  `col + 0.5 + jx`, `:127-130` the origin at `(Pc.x, Pc.y, 0)` and the direction along camera -Z). With `jitter=0` both
  jitters are zero, so the ray goes through the exact pixel centre.
- `src/painterly/kernel/integrator/path.h`: `painterly_trace_pixel` `:64-179`, `:75-105` (`depth >= max_depth` returns 0
  before intersecting, then the emission term; so `max_depth=1` gives one hit's emission and nothing else) and
  `painterly_emission_term` `:49-52` (`0.0 + E * gain`).
- `src/painterly/scene/integrator.cpp:41-85` (every socket the golden render sets already exists, with its default and the
  comment that gives its source).
- `tests/blender_it/test_extension_it.py`: `REPO_ROOT` `:36`, `RUN_REFERENCE` `:37`, `ZIP_PATH_FILE` `:39`, `_load_by_path`
  `:53-64`, `blender_executable` `:71-73`, `_require_blender` `:76-85`, `_require_zip` `:88-101`, `_run` `:104-112`, the
  isolated profile `:149-170`, and the exact-comparison comments `:203-213`. This card's test copies their skips and their
  isolated-profile pattern.
- `tests/blender_it/run_reference.py`: `EXTENSION_MODULE` `:37`, `ENGINE_ID` `:40`, `EXR_COLOR_DEPTH` `:51`,
  `enable_extension` `:68-82`, `configure` `:85-101`, `render_pixels` `:104-117` (the save-then-reload read-back),
  `main` `:120-147`, and the `--` argument rule `:150-153`. `render_golden.py` follows it.
- `Makefile:91-92` (`blender-it: extension build`, then `pytest tests/blender_it -m slow -q`), `Makefile:73-74`
  (`test-blender`), `Makefile:110` (`check`), `pyproject.toml:38` (`testpaths` includes `tests`), `:40` (`slow`),
  `:43-44` (ruff `line-length = 100`, `target-version = "py312"`), `tests/conftest.py:21-28` (`PAINTERLY_BUILD_DIR`).
- `tests/blender/test_render_reference.py:41-72` (the constants of the sibling render test, `BYTE_MAX` at `:54`) and
  `:119-123` (`_scene_linear_expectation`, SPEC §8 built by hand), `:197-212` (`_render_result_pixels`: the same
  save-then-reload read-back).
- `experiments/README.md:6-20` (the index this card adds a row to) and `:60-64` (the five README sections and the
  `out/` rule). `experiments/011-2026-10-23-svm-probe/` is the shape of an experiment directory (`README.md`, `probe.py`,
  `results.json`).
- The measurement this card's band comes from, quoted in full in step 4: `lever_set.json`, written by
  `experiments/NNN-<DATE>-golden/measure_levers.py` and reproduced on this host in 1.7 s.

## Create

- `tests/blender_it/golden_scenes.py`
- `tests/blender_it/golden_rule.py`
- `tests/blender_it/render_golden.py`
- `tests/blender_it/test_golden.py`
- `tests/blender_it/test_golden_rule.py`
- `experiments/NNN-<DATE>-golden/README.md`
- `experiments/NNN-<DATE>-golden/measure_levers.py`
- `experiments/NNN-<DATE>-golden/lever_set.json`

`NNN` and `<DATE>` follow `CLAUDE.md:108`'s rule — numbered and dated in the order they run — so the card names the
pattern and step 4 picks the next free number at run time (`## Open for Opus` 1). `lever_set.json` is the committed
output of `measure_levers.py`, and the script sits next to it (AGENTS.md, "Measured means reproducible").

## Modify

- `experiments/README.md`: one row in the index table (`:8-20`), status `draft`, its Conclusion "DRAFT (DeepSeek) —
  pending Opus review" when B9 lands (`CLAUDE.md:108`, `AGENTS.md` "Pre-registered experiments").

## Do not touch

- `src/blender/addon/sync/shader/node_table.py`, `export.py`, `flatten.py`: B7's and B8's. The golden scene uses B8's
  three rows (Material Output, Emission, Texture Coordinate, `BRIEF.md:224-226`); it adds no row.
- `src/painterly/**`, `src/cycles/**`, `third_party/cycles/**`: nothing in the core changes. `src/painterly/kernel/types.h`
  and `globals.h` are B1's and B2's CONTRACTs; `src/blender/_painterly.pyi` is B6's, B8's and B10's.
- `src/blender/addon/session.py`, `film.py`, `properties.py`: the render loop and the film are read, never changed. The
  harness sets existing sockets; it does not add one (BRIEF.md:75-77).
- `tests/blender_it/test_extension_it.py`, `tests/blender_it/run_reference.py`: T4.4's integration test and its script.
  They must pass unchanged; this card adds files beside them.
- `tests/blender/test_render_reference.py`, `test_properties.py`, `test_registration.py`, `test_ui_surface.py`,
  `tests/blender/conftest.py`, `tests/conftest.py`: T4.2's, T4.3's and T4.4's tests and the fixtures.
- `Makefile`, `pyproject.toml`, `.github/workflows/**`: no new target, no new lint setting. `blender-it` already collects
  `tests/blender_it` (`Makefile:91-92`), and `pyproject.toml:38` already collects `tests`.
- `tests/core/test_oracle_parity.py`, `tests/core/test_triangle_path.py`: unchanged, so the parity tests stay the
  oracle's business and the golden rule stays the harness's.
- `make oracle`: never run (R7; `experiments/README.md:27-29`). The golden scene renders through Blender's Cycles and
  painterly, never the oracle.

## Interface

No CONTRACT change: no C++, no binding and no pyi. The names below are the harness's public surface, and the node batch
cards use exactly them (BRIEF.md:283).

`tests/blender_it/golden_scenes.py` (needs `bpy`; it runs inside Blender, never under pytest):

    SIZE = 64                       # px, square; a power of two so Generated's ramp is exact
    PASSES = 1                      # film.py:111's `passes`, the film's own unit
    EXPOSURE = 1.0                  # film.py:111's `exposure`
    RGBA_CHANNELS = 4               # a float32 OpenEXR written with color_mode RGBA
    ORTHO_SCALE = 2.0               # world units across the image; the plane's side
    FILTER_WIDTH = 0.01             # Cycles' smallest pixel filter width, in pixels

    def build(**variant: object) -> bpy.types.Scene: ...
        """The golden scene of Texture Coordinate's Generated output, with one registered variant applied."""

    GOLDEN_SCENES: dict[str, Callable[[], bpy.types.Scene]]   # node name -> its scene builder
    LEVERS: dict[str, dict[str, object]]          # the 10 registered float32-level variants (step 4)
    NOT_LEVERS: dict[str, dict[str, object]]      # the 5 registered non-levers: the rule must reject them
    FILTER_CONTROL: dict[str, dict[str, object]]  # the filter-type control (1 entry), measured, not required
    STAND_INS: dict[str, dict[str, object]]       # the 4 stand-ins the rule must reject

`tests/blender_it/golden_rule.py` (pure numpy; `bpy`-free, so `make check` runs it):

    BAND = 2.0**-30                 # X-golden's band: lever_set.json's rule.band
    PASSES = 1
    EXPOSURE = 1.0
    BYTE_MAX = 255.0                # film.py:43

    def scene_linear(cycles_rgb: np.ndarray) -> np.ndarray: ...
        """(H, W, 3) float32 Cycles radiance -> painterly's output space, float32."""
    def max_abs_difference(painterly: np.ndarray, cycles: np.ndarray) -> float: ...
    def meets_rule(painterly: np.ndarray, cycles: np.ndarray) -> bool: ...
        """True iff max |P - C| <= BAND over every pixel and colour channel."""

`tests/blender_it/render_golden.py` (the in-Blender renderer, run as a subprocess):

    PAINTERLY_KNOBS: dict[str, object]    # the integrator sockets of BRIEF.md:242-244 and their values
    # <blender> -b --factory-startup --python-exit-code 1 --python render_golden.py -- <scene> <out_dir>
    # writes <out_dir>/{cycles.npy, painterly.npy, golden.json, <scene>.blend}

`experiments/NNN-<DATE>-golden/measure_levers.py` (the measurement, run as a subprocess):

    # <blender> -b --factory-startup --python-exit-code 1 --python measure_levers.py -- --out <path>/lever_set.json
    # writes and prints lever_set.json; byte-identical on every run

The two subprocesses print nothing the tests parse: the tests read `golden.json` and `lever_set.json`.

## Steps

1. Preconditions. Each must hold; otherwise stop, commit nothing and report what you saw.
   - The golden harness does not exist yet: this prints nothing and exits 1.
     ```
     ls tests/blender_it/golden_scenes.py
     ```
   - `blender-it` collects the directory already, so no Makefile change is needed. Each prints `1`:
     ```
     grep -c 'blender-it: extension build' Makefile
     grep -c 'pytest tests/blender_it -m slow -q' Makefile
     ```
   - B8 has landed with its three rows (`BRIEF.md:224-226`). This prints `1`:
     ```
     grep -c 'ShaderNodeTexCoord' src/blender/addon/sync/shader/node_table.py
     ```
   - The film the rule compares in: each prints `1`.
     ```
     grep -c 'BYTE_MAX = 255.0' src/blender/addon/film.py
     grep -c 'output_mode == "scene_linear"' src/blender/addon/session.py
     ```
   - `plan.md:305`'s "no debug code paths" holds for the core and the add-on: this prints nothing.
     ```
     grep -rn 'debug' src/painterly src/blender
     ```
     (Measured at this HEAD: nothing under either directory. The only `debug` tokens under `src/` are the shim
     logger's level names, `src/cycles/shim/util/log.h:32-40`, and no kernel or add-on path reads one.)
   - `bpy` is importable and is 5.2.2, and Blender's own executable is the one `$BLENDER` names:
     ```
     .venv/bin/python -c "import bpy; print(bpy.app.version_string)"
     ```
     prints `5.2.2 LTS`.
   - The next free experiment number is 012 (`experiments/` ends at `011-2026-10-23-svm-probe`):
     ```
     ls -d experiments/[0-9][0-9][0-9]-* | tail -1
     ```
     Step 4 fixes `NNN` and `<DATE>` from it at run time, not here.
2. `tests/blender_it/golden_scenes.py`: the scene, the four variant sets and the constants of `## Interface`.
   - `build(...)` builds it in this order: `bpy.ops.wm.read_factory_settings(use_empty=True)`; a mesh from `PLANE` and
     `TRIANGLES` (a quad as two triangles — the node reads Generated, which Cycles derives from the mesh's texture space,
     so painterly needs the attribute B3 adds to `add_mesh`, `BRIEF.md:144-149`); an object at `LOCATION = (0.3, -0.7,
     0.5)`; a material whose tree is `ShaderNodeOutputMaterial` ← `ShaderNodeEmission` ← `ShaderNodeTexCoord`'s
     `Generated` output, with the Emission's `Strength` at its default 1.0; an `ORTHO` camera of `ORTHO_SCALE` at
     `LOCATION + (0, 0, 5.5)` looking down -Z; then the render settings:
     `engine = "CYCLES"`, `resolution_x = resolution_y = 64`, `resolution_percentage = 100`,
     `image_settings.file_format = "OPEN_EXR"`, `color_depth = "32"`, `color_mode = "RGBA"`,
     `cycles.device = "CPU"`, `cycles.samples = 1`, `cycles.use_denoising = False`, `cycles.seed = SEED`,
     `cycles.filter_width = FILTER_WIDTH`, `view_settings.view_transform = "Raw"`, `look = "None"`,
     `exposure = 0.0`, `gamma = 1.0`.
   - `cycles.pixel_filter_type` is left at Cycles' default, `BLACKMAN_HARRIS` (measured, step 4's `scene` block), because
     at `filter_width` 0.01 the type is a delta: GAUSSIAN is bit-identical to the default (0 of 12288 values differ,
     step 4's `filter_control`) and BOX differs by 32 band units (its `N5`). `## Open for Opus` 3 names the choice.
   - The variants are `build`'s keyword arguments, and each is one entry of `LEVERS`, `NOT_LEVERS`, `FILTER_CONTROL` or
     `STAND_INS`:
     `baked` (the object's transform written into the vertices, so the plane is in the same world position and the
     object transform is the identity), `seed`, `camera_dx`/`camera_dy` (world units added to the camera's location),
     `camera_dx_ulp`/`camera_dy_ulp` (the camera moved by that many float32 ulps of its coordinate), `vertex_ulp` (every
     vertex's x moved by that many float32 ulps), `filter_type`, `socket` (which Texture Coordinate output drives the
     Emission's Color) and `constant` (a constant Emission Color instead).
   - `moved(value, steps)` is the ulp arithmetic: bpy stores a transform in float32, so one ulp is one step of
     `np.nextafter(np.float32(value), ±inf)`. It is a definition, not a tolerance: "one float32 ulp" is the smallest
     change a float32 transform can carry.
   - `GOLDEN_SCENES = {"texcoord_generated": build}`. A batch card adds `"<node>": <its builder>` and nothing else in this
     file.
   - Every comment that states a fact names its source: `film.py:111` for the two film arguments, `spec.md:279` for
     `scene_linear`, `camera.h:110-111` for the pixel centre, `path.h:75-105` for `max_depth=1`.
3. `tests/blender_it/render_golden.py`: the renderer, run inside Blender with the `--` argument rule of
   `run_reference.py:150-153`.
   - It loads `golden_scenes.py` from its own directory by path (`test_extension_it.py:53-64`'s pattern), because
     `blender --python <file>` puts neither the script's directory nor the cwd on `sys.path`.
   - It builds the scene, saves it as `<out_dir>/<scene>.blend` (`bpy.ops.wm.save_as_mainfile`), renders Cycles
     (`render.engine = "CYCLES"`, `bpy.ops.render.render(write_still=True)`), and reads the result back with
     `save_render` → `read_exr`: `bpy.data.images["Render Result"].save_render(path, scene=scene)`, then
     `bpy.data.images.load(path)`, `pixels.foreach_get` into float32, reshape to `(H, W, 4)`. That is
     `run_reference.py:104-117`'s read-back, and it is exact: the file stores float32 unchanged
     (`test_extension_it.py:203-213`).
   - It then re-opens the saved `.blend` (`bpy.ops.wm.open_mainfile`) and renders painterly from it, so the two engines
     see the same file and differ only in the engine and in `PAINTERLY_KNOBS`. (Measured at drafting: a save and re-open
     of this scene changes no rendered value — 0 of 12288 — and keeps `samples`, `filter_width`, the filter type, the Raw
     view transform, `ortho_scale` and the engine.)
   - `enable_extension()` is `run_reference.py:68-82`'s: `addon_utils.enable("bl_ext.user_default.painterly")`, then a
     check that `"PAINTERLY"` is a registered `bpy.types.RenderEngine` `bl_idname`.
   - `PAINTERLY_KNOBS` is the whole socket list with the golden values, so the render does not inherit a default that
     differs from the brief's (BRIEF.md:242-244):
     `chain="row"`, `passes=1`, `max_depth=1`, `emission_gain=1.0`, `jitter=0.0`, `output_mode="scene_linear"`,
     `exposure=1.0`, `seed=0`, `diffuse_gain=1.0`, `two_sided=True`, `continue_after_emitter=True`,
     `ray_epsilon=1e-4`, `ghost_lights=True`, `emission_scale=1.0`, `spiral_frame="camera"`,
     `spiral_rotation=(0.0, 0.0, 0.0)`, `u2_mode="same"`, `k0_phase_lock_bits=0`, `lane_length=16`,
     `seed_per_frame=False`, `alpha=0.0`. Each is a socket of `src/painterly/scene/integrator.cpp:41-85`; none is new
     (BRIEF.md:75-77). `settings.reference_scene = False`, because the golden scene is a Blender scene and not SPEC §9.
   - `golden.json` records `scene`, `size`, `passes`, `exposure`, the two engine ids, `painterly_knobs`, and the
     Cycles-side facts the rule's derivation names: `cycles_samples`, `cycles_filter_type`, `cycles_filter_width`,
     `cycles_filter_width_hard_min`, `cycles_view_transform`, `ortho_scale`, `alpha_values`. It is written right after
     the Cycles render and before the painterly one, so a host without the installed extension still records the Cycles
     half (acceptance 7).
4. `experiments/NNN-<DATE>-golden/measure_levers.py`: the measurement, and `lever_set.json` its output.
   - It loads `tests/blender_it/golden_scenes.py` by path from `REPO_ROOT` (`Path(__file__).resolve().parents[2]`), so the
     scene and the lever set have one definition and the experiment adds none.
   - It renders `R the reference` and every entry of `LEVERS`, `NOT_LEVERS` and `FILTER_CONTROL` — 17 renders in all —
     maps each to painterly's output space with `film` (`sum / PASSES / 255 * EXPOSURE` in float64, then one float32
     cast, which is `film.py:111` with its two identity arguments), and writes, in this order: `scene`,
     `reference_render`, `levers`, `not_levers`, `filter_control`, `rule`, `stand_ins`, `pixel_centre`.
   - `rule.band` is `max` over the lever set, all 12288 values, of the per-pixel spread (max minus min over the levers)
     in that space. It is a measurement of Cycles' own float32 spread: no painterly render exists when it is taken
     (BRIEF.md:248-252).
   - Run it with Blender's own executable, from the repository root:
     ```
     $BLENDER -b --factory-startup --python-exit-code 1 \
       --python experiments/NNN-<DATE>-golden/measure_levers.py -- --out experiments/NNN-<DATE>-golden/lever_set.json
     ```
   - Its output, measured on this host (Blender 5.2.2, 1.7 s, and byte-identical when re-run under
     `.venv/bin/python` and under `$BLENDER`):
     - `scene`: `size_px` 64, `passes` 1, `exposure` 1.0, `samples` 1, `pixel_filter_type` `BLACKMAN_HARRIS`,
       `filter_width_set` 0.01, `filter_width_stored` `0.009999999776482582` (= the property's `hard_min`),
       `view_transform` `Raw`, `ortho_scale` 2.0, `world_units_per_pixel` `0.03125`.
     - `reference_render`: `min` `3.063748590648174e-05`, `max` `0.0038909316062927246`, `mean_per_channel`
       `0.001960784662514925`, `0.001960784662514925`, `0.0019607841968536377`, `distinct_values_per_channel` 146, 113, 2,
       `zeros` 0, `nans` 0, `alpha_values` `1.0`, and the first four R values of row 0
       `3.063748954446055e-05`, `9.191199933411554e-05`, `0.00015318651276174933`, `0.0002144610189134255`.
     - `levers` (each against the reference; 12288 values compared): L1 `baked` 1537 changed, max `2.3283064365386963e-10`;
       L2-L4 `seed 1`, `2`, `3` 0 changed, max `0.0`; L5/L6 `vertex x ± 1 ulp` 5190/4993 changed, max
       `4.656612873077393e-10`; L7/L8 `camera x ± 1 ulp` 2540/3455 changed, max `4.656612873077393e-10`; L9 `camera y + 1
       ulp` 3567 changed, max `4.656612873077393e-10`; L10 `camera y - 1 ulp` 4865 changed, max `5.820766091346741e-10`.
     - `not_levers`: N1-N3 `camera ± filter_width/2` on one axis (in world units, `0.01 / 2 * 0.03125`) 5759, 4592 and
       5845 values changed, max `3.066379576921463e-07`; N4 the same on y, 6276 changed, max `3.0687078833580017e-07`;
       N5 `filter type BOX` 8343 changed, max `2.9802322387695312e-08`.
     - `filter_control`: F1 `filter type GAUSSIAN` 0 of 12288 values changed, max `0.0` — at this width the filter is a
       delta, so the type cannot matter.
     - `rule`: `band` `9.313225746154785e-10` (= `2.0**-30`; `band_is_a_power_of_two` true), 8881 of 12288 values have a
       spread above zero, `band_over_max` `2.39357234477211e-07`, `float32_spacing_at_max` `2.3283064365386963e-10`,
       `band_in_float32_ulps_at_max` 4.0, `float32_spacing_at_min` `3.637978807091713e-12`,
       `band_in_float32_ulps_at_min` 256.0.
     - `stand_ins`: C1 `constant 0.5 grey` max `0.0019301471766084433` (2 072 479.75 band units), C2 `TexCoord UV` and C4
       `camera + 1 px` max `0.0038909316062927246` (4 177 856 band units), C3 `TexCoord Object` max
       `0.003890931147907395`.
     - `pixel_centre`: Cycles' one sample sits at `sample_offset_x_px` `2.4413748178631067e-06` and
       `sample_offset_y_px` `3.415567334741354e-06` from the pixel centre (recovered from Generated's ramp), and the exact
       pixel-centre ramp differs from the reference render by at most `5.820766091346741e-10`, 0.625 band units.
   - Commit `lever_set.json` beside the script. Its check is a re-run and `cmp`: the file is byte-identical.
5. `tests/blender_it/golden_rule.py`: `BAND`, `scene_linear`, `max_abs_difference`, `meets_rule` (`## Interface`).
   - **The decision rule, pre-registered and frozen at approval** (BRIEF.md:247-252; AGENTS.md "Expected values are
     evidence"). For a golden scene, with `P` painterly's render and `C` Cycles', both in painterly's output space:

         the scene meets X-golden's rule   iff   max |P - C| <= BAND

     over every pixel and every colour channel, with the shape, the dtype and the alpha channel checked separately.
     `BAND = 2.0**-30 = 9.313225746154785e-10` is step 4's `rule.band`, measured from Cycles renders alone. It is
     written as a power of two because the measurement lands on one, so the literal is exact.
   - The rule is a decision, not a target: if painterly's render of a golden scene exceeds `BAND`, the scene fails and the
     failure is the result. The band is never widened, the lever set is never trimmed, and a scene is never re-measured to
     fit its own output (AGENTS.md, "Never move an expected value").
   - `scene_linear(cycles_rgb)` applies `film.py:111`'s operations in its order — `/ PASSES`, `/ BYTE_MAX`, `* EXPOSURE`,
     all in float64, then one float32 cast — to Cycles' float32 values (BRIEF.md:243-244). Dividing a float32 value by
     255 in float64 and casting once gives the same float32 as dividing it in float32 (measured at drafting for the
     reference's `min`, two interior values and `max`: all four equal), so the harness's map and painterly's own film
     agree bit for bit.
   - `max_abs_difference` raises `ValueError` for a shape mismatch or a non-RGBA array, so a wrong read fails loudly
     instead of comparing the wrong slice.
   - No tolerance appears anywhere else: `BAND` is the only number, and it comes from the committed JSON.
6. `tests/blender_it/test_golden.py`: the harness's slow test, `test_texcoord_generated_meets_the_rule`.
   - It is `@pytest.mark.slow` (CLAUDE.md rule 6: it renders twice inside Blender), so `make test-py` (`-m "not slow"`)
     deselects it and `make check`'s pass count does not move for it. It imports no `bpy`: it drives Blender as a
     subprocess, so `make check` can collect it on a machine without Blender's Python.
   - It skips exactly as `test_extension_it.py:76-101` does and for the same two reasons: `BLENDER` unset or not a file;
     no `build/extension/zip_path.txt` or no zip at the path it names (`Makefile:79`: without a wheel builder no zip is
     written and the test skips). The skips carry those reasons as their messages.
   - It creates one isolated profile (`tmp_path / "blender-user"`, `BLENDER_USER_RESOURCES`, as
     `test_extension_it.py:149-154`), installs the zip (`--command extension install-file -r user_default -e <zip>`),
     and runs `render_golden.py` with `-b --factory-startup --python-exit-code 1 --python <script> -- texcoord_generated
     <out_dir>` through `subprocess.run` with `capture_output=True`, failing with the process's stdout and stderr when it
     exits non-zero (the shape of `test_extension_it.py:104-112`).
   - It loads `golden_rule.py` by path (`_load_by_path`, `test_extension_it.py:53-64`), reads
     `cycles.npy`/`painterly.npy`/`golden.json`, and asserts, in this order:
     - `golden.json`'s `size` is 64, its two engine ids are `CYCLES` and `PAINTERLY`, and `cycles_filter_width` equals
       `cycles_filter_width_hard_min` — the premise "the smallest filter width" (BRIEF.md:241), so a Blender that widens
       the minimum fails here instead of silently widening the filter;
     - `golden.json`'s `alpha_values` is `[1.0]`, and both arrays are `(64, 64, 4)` float32;
     - `golden_rule.meets_rule(painterly, cycles)` is true, with `max_abs_difference` in the failure message.
   - Nothing in the test re-derives the band: it reads `golden_rule.BAND`, which is the committed measurement.
7. `tests/blender_it/test_golden_rule.py`: five fast tests over `golden_rule` and the committed `lever_set.json`, no
   `bpy` and no Blender, so they run in `make check`. They load `golden_rule` and the JSON by path, relative to
   `Path(__file__).resolve().parents[2]`.
   - `test_a_matching_render_meets_the_rule`: `cycles` is a small literal ramp in painterly's output space, `painterly`
     is `golden_rule.scene_linear(cycles)`; `max_abs_difference` is exactly `0.0` and `meets_rule` is true.
   - `test_a_difference_of_exactly_the_band_meets_the_rule`: `cycles` is all zeros, so its film map is all zeros, and one
     pixel of `painterly` is `BAND`. `2.0**-30` is a float32 value and `0.0 + BAND` is exact, so the difference is
     exactly `BAND`: `max_abs_difference == BAND` and `meets_rule` is true. This is what pins the decision's `<=`
     (step 5) — with `<` this test fails, and no other fixture of the card lands on the boundary.
   - `test_a_difference_above_the_band_fails_the_rule`: the same arrays with `2 * BAND`; `meets_rule` is false.
   - `test_a_constant_stand_in_fails_the_rule`: a constant array against the ramp; `meets_rule` is false.
   - `test_the_committed_lever_set_agrees_with_the_rule`: finds the file with
     `next((REPO_ROOT / "experiments").glob("*-golden/lever_set.json"))` (the directory's number is chosen at run time,
     `## Open for Opus` 1) and asserts `rule.band == repr(BAND)`, that every lever's `max_abs_difference` is at most
     `BAND`, and that every `not_levers` entry and every `stand_ins` entry is strictly above it. So the committed
     measurement and the code cannot drift apart, and the rule cannot pass a stand-in.
8. `experiments/NNN-<DATE>-golden/README.md`, with exactly the five sections of `experiments/README.md:62-63`.
   - `## Background`: the golden test of `plan.md:305`, and that `ShaderGraph::finalize` folds a graph of constants
     (`T6.5:163-168`), which is why the scene drives the node from Texture Coordinate (BRIEF.md:245-246).
   - `## Hypothesis`: the scene meets the rule of step 5, with the band of step 4's measurement — `max |P - C| <= BAND`,
     `BAND = 2.0**-30`. **Frozen at approval** (`AGENTS.md`, "Pre-registered experiments"): this section and `## Method`
     are not edited after the run starts.
   - `## Method`: steps 2-5's commands, the lever set as registered, and the decision rule verbatim.
   - `## Results`: filled by the run, numbers only.
   - `## Conclusion`: `DRAFT (DeepSeek) — pending Opus review.`
9. `experiments/README.md`: the new row in the index table (`:8-20`), status `draft`.
10. `.venv/bin/ruff format` on the five new test files and the experiment script, `.venv/bin/ruff check .`, then every
    acceptance command.

## Acceptance

Run every command from the repository root; the queue translates them with BACKLOG.md's table (`make check` → `CHECK`,
`make test-blender` → the same target with `KNOBS`, `build/dev` → `build/q`, `.venv/bin/<tool>` → `MAIN/.venv/bin/<tool>`,
any Python command prefixed with `PYTHONPATH="$PWD/analysis"`, `$BLENDER` → `KNOBS`' `BLENDER`).
1. `make check` exits 0. Report the doctest test-case and assertion counts, the pytest pass count and the audit's
   `RESULT: PASS` line. This card adds no C++, so the doctest counts are T-fix-TQ5a's and must not move. The pytest count
   grows by exactly the five fast tests of step 7 — `test_golden.py`'s slow test is deselected by `-m "not slow"`
   (`Makefile:63-64`). The count is the number of test names step 7 lists; if the run prints another number, the card's
   count is wrong and that is a finding, not a tolerance.
2. `make audit` prints `RESULT: PASS`: no new exported symbol and no new dependency (no CMake file changes, no binding).
3. `make test-blender` exits 0. Report its last line: `tests/blender_it` is not in `tests/blender`, so its count is
   T4.2's and T4.3's and must not move.
4. `.venv/bin/python -m pytest -q tests/blender_it/test_golden_rule.py` prints `5 passed` — step 7's five tests.
   Report its duration: pure numpy, well under a second.
5. The measurement reproduces byte for byte, from the committed script, with no painterly render involved:
   ```
   $BLENDER -b --factory-startup --python-exit-code 1 \
     --python experiments/NNN-<DATE>-golden/measure_levers.py -- --out /tmp/lever_set.json
   cmp /tmp/lever_set.json experiments/NNN-<DATE>-golden/lever_set.json
   ```
   `cmp` prints nothing and exits 0, and the script's own output has `rule.band` `9.313225746154785e-10` and 12288
   `values_compared` per lever. (Measured at drafting: 1.7 s, and byte-identical to the committed file.)
6. `.venv/bin/python -m pytest -q tests/blender_it -m slow` prints `2 passed`: `test_extension_it.py`'s
   `test_the_extension_renders_the_reference_scene_bit_for_bit` and this card's
   `test_texcoord_generated_meets_the_rule`. The count is the two files' own slow tests. If no zip can be built on the
   host (`Makefile:79`), both skip instead; report the skip reasons and mark this command "host-only, not run" (R1), then
   run command 7 instead.
7. The golden scene's Cycles half, without the extension: `render_golden.py` cannot run painterly without the installed
   extension, so this checks the Cycles side and the read-back on its own. It writes `cycles.npy` and `golden.json` and
   fails before the painterly render:
   ```
   $BLENDER -b --factory-startup --python-exit-code 1 \
     --python tests/blender_it/render_golden.py -- texcoord_generated /tmp/golden
   ```
   exits non-zero in `enable_extension` (measured: status 1, `RuntimeError: addon_utils.enable(
   'bl_ext.user_default.painterly') returned None` on a host with no installed extension), after `cycles.npy` and
   `golden.json` exist; `python -c` on that file prints `cycles_filter_width == cycles_filter_width_hard_min` true,
   `cycles_filter_type` `BLACKMAN_HARRIS`, `size` 64 and `alpha_values` `[1.0]` (measured). Report that, and report the
   exit status and the message.
8. `.venv/bin/ruff check .` and `.venv/bin/ruff format --check .` are clean (the two `lint` lines of `CHECK`).
9. `git status --porcelain` lists only the eight Create paths and the one Modify path above, and no `experiments/*/out/`
   file (`.gitignore:12`).

Each check can fail, and these mutations show it (make them in your clone and put the file back):
- `BAND = 2.0**-29` in `golden_rule.py` → acceptance 4 fails on `test_the_committed_lever_set_agrees_with_the_rule`
  (the JSON's `rule.band` no longer equals `repr(BAND)`), and acceptance 6 fails on `meets_rule`;
- `BAND = 0.0` → acceptance 4 fails on the same test for the same reason; whether acceptance 6 also fails is a
  measurement, not a claim of this card (painterly's golden render does not exist yet);
- compare without the film map (`painterly[..., :3]` against `cycles[..., :3]`) → acceptance 4 fails on
  `test_a_matching_render_meets_the_rule`, whose two sides then differ by the ramp's own 255x;
- remove the `cycles_filter_width == hard_min` assertion → acceptance 6 still passes, which is why the mutation that
  matters is the scene's: set `FILTER_WIDTH = 0.02` in `golden_scenes.py` and the assertion fails;
- change the Emission's link to `coords.outputs["UV"]` in `build` → acceptance 6 fails with a difference of
  `0.0038909316062927246`, 4 177 856 band units (step 4's `stand_ins` C2), because the mesh has no UV map and Generated
  is what the scene means;
- set `max_depth = 2` in `PAINTERLY_KNOBS` → acceptance 6 still passes, and that is a fact about the scene, not a gap in
  the harness: the Emission node collects no closure, so the collector gives one diffuse lobe of weight 0
  (`collect.h:205-210`), the bounce adds `weight * L = 0`, and the pixel keeps the first hit's emission. The knob's own
  effect is B4's;
- `<=` → `<` in `meets_rule` → acceptance 4 fails on `test_a_difference_of_exactly_the_band_meets_the_rule`, whose
  difference is exactly `BAND`.

Report: the doctest and pytest counts, the audit line, the five fast tests' duration, `lever_set.json`'s `rule` block and
`pixel_centre` block, acceptance 6's or 7's outcome with its output, and every mutation you ran with its first failing
check.

## Commit

`B9: the golden-test harness: one scene, Cycles' own float32 spread, and the pre-registered rule`

## Open for Opus

1. **The experiment number and date are chosen at run time.** `CLAUDE.md:108` numbers and dates experiments in the order
   they run, so this draft writes `experiments/NNN-<DATE>-golden/` and step 4 fixes the number (the next free one is 012)
   and the day of the run. The alternative — naming 012 and a date now — would be wrong if another experiment runs first.
   This card takes the pattern, as B10's draft does for X-colour.
2. **The band is written as a power of two.** The measurement is `9.313225746154785e-10`, which is exactly `2.0**-30`
   (step 4's `band_is_a_power_of_two`). The card writes `BAND = 2.0**-30` so the literal is exact, and the JSON keeps the
   decimal `repr`. The alternative is the decimal literal in both places; the value and every acceptance are identical.
   Opus may prefer that, since it reads as a measured number rather than a chosen one.
3. **The scene leaves Cycles' pixel filter type at its default.** `BRIEF.md:241` says "the smallest filter width" and
   names no type, and `plan.md:305` says only "1 spp (pixel centre, Raw, EXR)". At `filter_width` 0.01 the type does not
   matter: GAUSSIAN is bit-identical to the default BLACKMAN_HARRIS (0 of 12288 values differ, step 4's
   `filter_control`) and BOX differs by 32 band units (`N5`). The options: (a) leave the default (this card); (b) pin
   `BOX`, the smallest support of the three, which makes the type a registered non-lever with a 32-band-unit effect and
   removes any dependence on Cycles' default. (b) is the more explicit scene and changes only `build` and one
   `NOT_LEVERS` entry's measured value.
4. **The brief's seed example does not move the sample at this filter width.** `BRIEF.md:249-250` names "seeds that move
   the sample inside the smallest filter" as one way to get a float32-level difference. Measured: with
   `filter_width` 0.01, seeds 0, 1, 2 and 3 give bit-identical renders (0 of 12288 values differ, step 4's L2-L4), and the
   sample's offset from the pixel centre is the same `2.4413748178631067e-06` px in x and `3.415567334741354e-06` px in y
   for the default filter and for GAUSSIAN (step 4's `pixel_centre`, `filter_control`). The card keeps those three seeds
   as registered levers, so the fact is measured and committed rather than asserted, and takes the spread from the
   geometry and camera levers (L1, L5-L10), which do move it. A Blender that changed the fact would change
   `lever_set.json`, and acceptance 5's `cmp` fails on it — the committed measurement is the check, so the seeds are
   evidence here and not a tolerance. The alternatives: (a) keep them (this card); (b) drop them and cite the
   0-difference result in the README only. Opus may also want `BRIEF.md:249-250`'s example corrected in the brief.
5. **`make blender-it` needs the extension zip, which needs a wheel builder.** The golden test renders painterly through
   the installed extension, as `test_extension_it.py` does, so it skips when `build/extension/zip_path.txt` is absent
   (`Makefile:79`) — on this host `make wheel` is host-only (R1). The options: (a) keep one path, the extension's (this
   card), and accept that the golden scene's painterly side runs only where a wheel can be built; (b) add a second path
   that renders painterly in-process from the built `_painterly` module (`tests/blender/conftest.py`'s `MODULE_DIR`
   pattern, `:26-29`), which needs no zip but enters through `session.py` rather than the extension's `engine.py`. (b)
   would make the golden scene runnable in `make test-blender`, which is the wider net; it is a second entry point to
   keep in step with `render_golden.py`.
6. **One band for every golden scene, or one per scene?** The brief pre-registers "a per-pixel decision rule" once
   (:251-252) and says the node batches pass it (:283). This card measures the band on the Texture Coordinate scene and
   applies it to every scene in `GOLDEN_SCENES`, because the lever set is a property of Cycles' arithmetic at a fixed
   pixel filter, not of one node. A later scene whose radiance range is much wider (an Image Texture's, batch 10) has a
   larger float32 spacing, so the same absolute band is looser for it — 256 float32 steps at this scene's darkest pixel
   and 4 at its brightest (step 4's `rule`). The options: (a) one band (this card); (b) a per-scene band, each measured by
   the same script on that scene's own levers, which needs a second `lever_set.json` per scene and makes "the rule" a
   family. (b) is the more honest for batch 10 and is a decision for Opus, not for this draft.
7. **What this card does not decide.** Per `BRIEF.md:295-301`: light node graphs stay out of v1, so no golden scene has a
   light; whether a node material's emission is scaled by `emission_scale` is open, and the golden scene's emission is the
   node's own with `emission_gain=1`, so no scaling appears either way; and Bump, Normal Map and the Attribute node are out.
   The golden scene's `max_depth=1` is the brief's knob, not a claim about deeper paths: at `max_depth=1` the path returns
   the first hit's emission and never samples a lobe (`path.h:75-105`), which is what a node whose output is a colour needs.
8. **The band's provenance file.** `lever_set.json` is committed next to its script (step 4), and `BAND` in
   `golden_rule.py` is the same number written as a power of two, so the number appears twice in the diff. The
   alternative is to read the JSON at import time, which makes `golden_rule` depend on a file path and lets a re-run
   change the band silently. This card keeps the literal and pins the two together with
   `test_the_committed_lever_set_agrees_with_the_rule` (step 7).
