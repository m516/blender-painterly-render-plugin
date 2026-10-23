# Experiment 010: CPU throughput of the native core (paths/second, and the time of a 1920×1080 × 1024-pass render)

## Background

- `docs/plan.md`, "What makes the look":
  - item 4 (path model): a fixed depth of 20 bounces, no Russian roulette, no next-event estimation (NEE) and no MIS. An
    emitter hit adds `E·emission_gain`, and the light is a black diffuse object, so paths keep bouncing after hitting it.
  - item 2 (ghost spheres): a ghost sphere is intersected with the `a = 1` quadratic along the unnormalized `d`, and
    SPEC §5 gives ghosts no BVH entry, so every path tests every ghost sphere by brute force.
  - item 3 (scan-line chaining): each path's counter K starts where the previous pixel's path in the same row ended, and
    only diffuse hits advance K. The chained K stream is what makes the converged texture.
- `docs/plan.md`, "Experiments programme": the row **X-throughput** asks for "CPU paths/s on the reference scene and a
  100k-triangle mesh; time for 1920×1080 × 1024 passes (the default `passes`, `chain=row`)".
- `docs/spec.md`:
  - §3: `chain=row` (the Blender default) has one chain per (row, pass) and parallelizes over rows. `chain=lane` with
    `lane_length = 16` has one chain per (lane, pass). `chain=image` is one chain over the whole render in the order
    `for pass, for row, for col` and "is single-threaded" (`docs/spec.md` §3, `image`).
  - §3 also fixes the determinism this experiment relies on: "Output is therefore bit-identical for any thread count or
    batch size."
  - §5: the ghost spheres have no BVH, so their cost is per path and per ghost, not per pixel.
  - §9: the reference scene is smallpaint's GUI scene, the ten-object scene of `tests/core/scenes.py`; the experiments
    render it at 400 px (experiments 001-009).
- The cost model the card names: a fixed 20 bounces per path, no Russian roulette, and brute-force ghost spheres. It
  predicts that the cost of a path is set by the bounce count and by the number of ghost spheres, not by the size of the
  scene's acceleration structure.
- T3.16 gave the core exact parity with `smallpaint_oracle` on the analytic scene, and T3.17 added the triangle path
  (Opus, 2026-10-23). T3.17's statistical match with the oracle is refuted at fresh seeds. The quad scene's radiance is
  lower in `r6` (by 0.15-0.24%) and higher in `r7` (by 0.09-0.27%) under both chains (M3-FIX-T3.17b), and it draws
  0.06-0.07% fewer samples; M3-FIX-T3.17c looks for the cause. Both are far below this experiment's run-to-run spread
  (about 6%, Results), so they change no number here.
- This experiment measures speed only. It makes no image comparison and renders no figure.

## Hypothesis

### Common definitions

- **Scene.** `tests/core/scenes.py` builds every scene, so the scene setup is the single source the parity tests use.
  - *analytic*: `build_smallpaint_scene(size=400)`, SPEC §9 with the six planes analytic (0 triangles).
  - *triangles*: `build_smallpaint_scene_triangles(size=400)`, the same SPEC §9 scene with each plane a quad of 2
    triangles (12 triangles).
  - *triangles+icosphere*: *triangles* plus one subdivided icosphere, level 6 (20·4⁶ = 81,920 triangles, the level nearest
    the plan's 100k-triangle mesh), as a `_painterly` mesh with a diffuse grey material (smallpaint's `cl` = 6, the
    walls' colour), inside the box and not occluding the light. The exact triangle count of the scene is reported.
- **Measurement.** One timed render is `TIMED_PASSES = 16` passes of a 400 px image, i.e. 16 × 160,000 = 2,560,000 paths,
  timed from the `Session.start()` call to the return of `Session.wait()`.
  - `paths/s` of one timed render is `400·400·16 / elapsed`.
  - The fixed cost inside that interval is the scene snapshot (`start()` runs `Scene.device_update`) and the object-id
    pass (one primary hit per pixel, `PainterlyPathTrace::render_object_id`), i.e. at most one pass of work. At 16 passes
    it is at most 1/16 = 6.25% of the interval, and it is a property of every configuration alike.
  - Each configuration is timed 3 times, and the **median** of the three is reported (the card's Method). The repeats
    are interleaved: repeat *i* times all eleven configurations in the table's order, so the three repeats of one
    configuration are spread over the run and share the machine's drift with every other configuration. Repeats are
    paired by their index.
  - The machine is shared, so the load average that `uptime` prints (`os.getloadavg()`, the same numbers from
    `/proc/loadavg`) is recorded immediately before and immediately after every timed render, and reported.
- **Threads.** `_painterly.Session(scene, threads)` with `threads` = 1, 2, 4. `threads = 0` would mean
  `std::thread::hardware_concurrency()` (`src/painterly/util/thread_pool.cpp`); this experiment sets the count
  explicitly so the speedups are between named counts.
- **Determinism.** Wall-clock times vary from run to run, so §5's determinism covers the scene setup and the numbers
  derived from the recorded times, not the times themselves (the card's Method). To make that checkable, every
  configuration also renders 1 pass at 1 thread, and the SHA-256 of the `combined`, `k_consumed` and `object_id` buffers
  of that render is recorded. SPEC §3 makes those buffers independent of the thread count and the batch size, so the
  digests must be identical between two runs of `analyze.py`, while the times are not.

### H1: paths/second grows with the thread count on the `row` chain (the only hypothesis with a decision rule)

- Derived from: SPEC §3. `chain=row` has one chain per (row, pass), and the rows of one pass are independent, so the
  paths of one pass are spread over the threads. The fixed cost of a path (20 bounces, no Russian roulette, brute-force
  ghosts) does not depend on the thread count, so the throughput should grow with T.
- Observable: `paths/s` of the analytic reference scene at 400 px, `chain=row`, T ∈ {1, 2, 4}, 3 repeats each.
- **Pre-registered decision rule (the card's):** throughput at T threads is greater than at T/2 in all 3 repeats, for
  T = 2 and T = 4. Repeats are paired by their index (repeat *i* at T against repeat *i* at T/2). H1 is supported iff
  both T = 2 and T = 4 satisfy that; otherwise it is refuted.
- Report the speedups (median at T divided by median at T/2) with no threshold.
- `chain=lane:16` is reported too: the same T, the same rule's outcome, with no verdict (SPEC §3 gives lanes one chain
  per (lane, pass), so growth is expected but is not the registered hypothesis).
- `chain=image` is reported too: SPEC §3 makes it a single chain, so its throughput must not grow with T. It is reported
  with no verdict.

### H2 (measurement, no decision rule): how the cost per path depends on the scene size

- Derived from: the cost model. The bounce count, not the scene size, sets the cost of a path, and the ghost spheres are
  brute force, so the acceleration structure should not matter much. This is reported, not tested (the card's explicit
  exception to protocol §2 and §7).
- Observable: `paths/s` at `chain=row` and 4 threads of the three scenes of the Common definitions, 3 repeats each,
  median. Report the three values, the ratio *triangles / analytic* and the ratio *triangles+icosphere / triangles*, with
  no threshold, and the exact triangle counts.
- The analytic reference scene at 4 threads is the same measurement as H1's row/4 configuration; it is measured once.

### H3 (projection, no decision rule): the time of 1920×1080 × 1024 passes on this machine

- Derived from: the plan's X-throughput row, which names 1920×1080 and the default `passes` = 1024
  (`src/painterly/scene/integrator.cpp`, `SOCKET_INT(passes, "Passes", 1024)`), `chain=row` and 4 threads.
- Observable: the median `paths/s` of H1's row/4 analytic configuration (the reference scene at 4 threads, the
  configuration the card names). The projection is `1920·1080·1024 / paths_per_s` seconds, reported in hours and
  minutes. No decision rule; the number is a projection from a 400 px measurement, not a render.
- The same projection from the *triangles* and *triangles+icosphere* medians is reported as estimation only.

## Method

### Configurations

Eleven configurations, each 3 timed repeats of 16 passes at 400 px, plus one 1-pass digest render:

| # | Scene | `chain` | `threads` | Serves |
|---|---|---|---|---|
| 1 | analytic | `row` | 1 | H1, H1 base for T = 2 |
| 2 | analytic | `row` | 2 | H1 |
| 3 | analytic | `row` | 4 | H1, H2 (analytic), H3 |
| 4 | analytic | `lane` (length 16) | 1 | H1 (reported) |
| 5 | analytic | `lane` (length 16) | 2 | H1 (reported) |
| 6 | analytic | `lane` (length 16) | 4 | H1 (reported) |
| 7 | analytic | `image` | 1 | H1 (reported, single-threaded) |
| 8 | analytic | `image` | 2 | H1 (reported) |
| 9 | analytic | `image` | 4 | H1 (reported) |
| 10 | triangles | `row` | 4 | H2 |
| 11 | triangles+icosphere | `row` | 4 | H2 |

The integrator knobs are the reference ones of `tests/core/scenes.py` (`apply_reference_knobs`: `max_depth` 20,
`diffuse_gain` 0.1, `emission_gain` 2, `ray_epsilon` 1e-4, `spiral_frame` smallpaint) plus the `chain` (and
`lane_length` 16 for the lane configurations). `batch` is 1.

### The icosphere

- Built in `analyze.py` (`icosphere`): the regular icosahedron's 12 vertices and 20 faces, and every triangle split into
  four by its edge midpoints projected onto the unit sphere, six times. Level *s* has 20·4^s triangles and 10·4^s + 2
  vertices, so level 6 is 81,920 triangles and 40,962 vertices.
- Placed at the centre (0.0, 1.2, −3.5) with radius 1.0 in smallpaint units, and given object id 10.
  - Inside the box: SPEC §9's planes put the box at x ∈ [−3.0, 2.5], y ∈ [−2.75, 2.75], z ∈ [−5.5, 0.5], so the sphere's
    x ∈ [−1, 1], y ∈ [0.2, 2.2], z ∈ [−4.5, −2.5] lies inside it.
  - Not occluding the light: the light is the sphere at (−1.9, 0, −3.0) with radius 0.5, at a distance of 2.30 units from
    the icosphere's centre, so the two do not intersect, and `analyze.py` asserts that the set of pixels whose
    `object_id` is the light (9) is exactly the same as in the *triangles* scene.
  - Diffuse grey: one material with one diffuse lobe of weight (6, 6, 6), smallpaint's `cl` of the box's walls.

### Machine record

- The CPU model is `lscpu`'s output. `lscpu` reads `/sys`, and the worker sandbox that ran this experiment has no
  `/sys`, so there the model name is taken from `/proc/cpuinfo`'s `model name` line instead, and both the `lscpu`
  output and its error are recorded. The thread count is `os.cpu_count()` and `len(os.sched_getaffinity(0))`; the
  latter is the count the scheduler may use.
- The load is `os.getloadavg()`'s three averages, immediately before `Session.start()` and immediately after
  `Session.wait()` of every timed render. They are the numbers `uptime` prints (the same three fields of
  `/proc/loadavg`).

### Commands

```
make build
PYTHONPATH="$PWD/analysis" PAINTERLY_BUILD_DIR="$PWD/build/q" .venv/bin/python experiments/010-2026-10-22-cpu-throughput/analyze.py
```

`analyze.py` puts `$PAINTERLY_BUILD_DIR/src/blender` first on `sys.path` before `import _painterly` (the default is
`build/dev`, resolved against the repository root as `tests/conftest.py` does), and loads `tests/core/scenes.py` by file
path with `importlib.util.spec_from_file_location`, because a script run puts neither directory on `sys.path`.

### Analysis

`analyze.py` writes `results.json` (through `painterly_analysis.report.write_results_json`, so every number in it is
finite and its key order is deterministic) and prints the tables of `## Results`. It is re-runnable: it renders no file
and reads no cache, so two runs differ only in the times, the derived rates and the load averages. Every recorded
number comes from this script.

### Pre-registration note

The configurations, the decision rule, the scenes and the thread counts are the card's. The image side (400 px) is the
experiments' reference side, and the icosphere's level, placement and colour are derived above from SPEC §9 and the
card.

Before this pre-registration was written, the harness was smoke-tested at 400 px with the same scenes and chains at 1,
2, 4, 8, 12, 16 and 32 passes, to check that the module imports, that the lane and image chains run, that a repeated
`Session.start()` on one session is allowed, and that the output buffers are independent of the thread count. Those
runs' timings were used for one design choice only: `TIMED_PASSES = 16` makes a timed render take about 1.8-6 s, long
enough that the snapshot and object-id overhead stays below 6.25% and short enough that all 33 timed renders finish in
minutes. No timing from them is reported as a result, and the decision rule, the hypotheses and the configuration list
were not changed after the recorded run.

## Results

Run of `analyze.py` on 2026-10-22, in the worker clone, against `build/q` (`make build` with the offline knobs,
2026-10-22). Every number below is in `results.json`; the command that regenerates it is in Method.

### Machine and load

- CPU: `AMD Ryzen 5 5600H with Radeon Graphics` (from `/proc/cpuinfo`; `lscpu` could not run, see below).
- Threads: `os.cpu_count()` = 12, `len(os.sched_getaffinity(0))` = 12. A `threads = 0` session takes
  `std::thread::hardware_concurrency()` (`src/painterly/util/thread_pool.cpp`); this experiment sets the count
  explicitly (1, 2, 4) instead, so no reported number depends on that fallback.
- `lscpu` failed in the worker sandbox: `lscpu: failed to determine number of CPUs: /sys/devices/system/cpu/possible:
  No such file or directory` (the sandbox has no `/sys`). The model name is therefore `/proc/cpuinfo`'s, and the full
  `lscpu` output and this error are in `results.json` under `machine`.
- Load average (`uptime`, the three numbers of `/proc/loadavg`) before the run:
  `16.15, 17.44, 16.40`; after it: `16.67, 17.10, 16.41`. The machine is shared and its load is around 16 on 12
  CPUs throughout, so every timing below was taken on a loaded machine. The per-render loads are in the table.

### Timed renders

400 px, 16 passes = 2,560,000 paths per timed render, 3 repeats each, repeats interleaved (Method). "Load" is the
1-minute average from `uptime` immediately before and after each timed render.

| configuration | elapsed (s), 3 repeats | paths/s, 3 repeats | median paths/s | load before → after (3 repeats) |
|---|---|---|---|---|
| `analytic-row-t1` | 4.964, 5.247, 5.407 | 515,709, 487,929, 473,493 | 487,929 | 15.82 → 15.44; 16.28 → 16.50; 15.82 → 16.08 |
| `analytic-row-t2` | 3.001, 2.975, 2.882 | 852,975, 860,571, 888,344 | 860,571 | 15.44 → 15.96; 16.50 → 16.46; 16.08 → 16.15 |
| `analytic-row-t4` | 1.790, 1.763, 1.764 | 1,430,312, 1,451,981, 1,450,840 | 1,450,840 | 15.96 → 15.96; 16.46 → 16.46; 16.15 → 16.15 |
| `analytic-lane16-t1` | 5.578, 5.150, 5.587 | 458,947, 497,104, 458,197 | 458,947 | 15.96 → 16.29; 16.46 → 15.94; 16.15 → 16.94 |
| `analytic-lane16-t2` | 3.080, 2.727, 3.194 | 831,039, 938,752, 801,465 | 831,039 | 16.29 → 16.10; 15.94 → 15.94; 16.94 → 16.86 |
| `analytic-lane16-t4` | 1.863, 1.698, 1.751 | 1,374,330, 1,507,629, 1,462,164 | 1,462,164 | 16.10 → 16.10; 15.94 → 16.18; 16.86 → 16.86 |
| `analytic-image-t1` | 5.932, 5.467, 5.332 | 431,587, 468,249, 480,138 | 468,249 | 16.10 → 16.01; 16.18 → 15.93; 16.86 → 16.50 |
| `analytic-image-t2` | 5.639, 5.114, 5.303 | 453,964, 500,587, 482,701 | 482,701 | 16.01 → 16.33; 15.93 → 15.61; 16.50 → 16.78 |
| `analytic-image-t4` | 5.669, 5.457, 5.355 | 451,601, 469,118, 478,076 | 469,118 | 16.33 → 16.13; 15.61 → 15.81; 16.78 → 16.55 |
| `triangles-row-t4` | 3.026, 3.056, 2.934 | 845,959, 837,828, 872,405 | 845,959 | 16.13 → 16.13; 15.81 → 15.82; 16.55 → 16.55 |
| `triangles+icosphere-row-t4` | 3.452, 3.490, 3.256 | 741,658, 733,598, 786,257 | 741,658 | 16.13 → 16.28; 15.82 → 15.82; 16.55 → 16.67 |

### H1: the throughput grows with the thread count on `row`

The card's rule: throughput at T threads greater than at T/2 in all 3 repeats, for T = 2 and T = 4. Repeats are paired
by index.

| chain | T | greater than T/2 in repeats 1, 2, 3 | all 3 | median speedup (T / (T/2)) |
|---|---|---|---|---|
| `row` | 2 | yes, yes, yes | yes | 1.764 |
| `row` | 4 | yes, yes, yes | yes | 1.686 |
| `lane:16` (reported) | 2 | yes, yes, yes | yes | 1.811 |
| `lane:16` (reported) | 4 | yes, yes, yes | yes | 1.759 |
| `image` (reported) | 2 | yes, yes, yes | yes | 1.031 |
| `image` (reported) | 4 | no, no, no | no | 0.972 |

H1's verdict: **supported** — the rule holds for both T = 2 and T = 4 on `chain=row`.

### H2: the cost per path against the scene size

`chain=row`, 4 threads, 3 repeats, median. The triangle counts are the scene's own.

| scene | triangles | median paths/s | ratio to the previous row |
|---|---|---|---|
| analytic (SPEC §9 planes) | 0 | 1,450,840 | — |
| triangles (SPEC §9 quads) | 12 | 845,959 | triangles / analytic = 0.5831 |
| triangles + icosphere (level 6) | 81,932 | 741,658 | (triangles + icosphere) / triangles = 0.8767 |

The icosphere is 81,920 triangles of the 81,932 (the six quads add 12). Its 40,962 vertices and 81,920 triangles are
recorded in `results.json`. The light's pixel count is 4,266 in both the `triangles` and the `triangles+icosphere`
scene, so the icosphere does not occlude the light (`analyze.py` raises if it did).

### H3: the projection for 1920×1080 × 1024 passes

`chain=row`, 4 threads, from H2's analytic median (the same configuration as `analytic-row-t4`):
2,123,366,400 paths at 1,450,840 paths/s = 1,463.5 s = **0.407 h ≈ 24.4 min** (0 h 24 min, truncated).

Estimation only, from the other two medians: 2,510.0 s = 0.697 h ≈ 41.8 min (0 h 41 min) for the triangle scene, and
2,863.0 s = 0.795 h ≈ 47.7 min (0 h 47 min) for the triangle scene with the icosphere.

### Determinism

The 1-pass, 1-thread digest of every configuration's `combined`, `k_consumed` and `object_id` buffers was recorded in
`results.json`. Two runs of `analyze.py` (this one and an earlier one a few minutes before it) produced identical digests
for all 11 configurations, e.g. `analytic-row-t1`: `combined`
`9fcbcf96139e7886df6217dd73f4814d17105851c7a11c8bff71bc009283246c`, `k_consumed`
`fec56d4a063a91ca3cb63b26f5e7dbbd891963d9eb9eb6b8c2437d3ff85c6a41`, `object_id`
`84154c75160d97719bf91ddfe81921d79f98e09ba6f9c6f05ff43451be4d512d`. The times, as the card says, do not reproduce.

### The spread between runs

An earlier run of the same command a few minutes before this one, also on 2026-10-22, measured the same eleven
configurations on the same machine: `row` medians 460,888 / 831,109 / 1,420,533 paths/s at 1 / 2 / 4 threads, the same
H1 verdict on all three chains, the H2 ratios 0.5995 and 0.9116, and 1,494.8 s for H3. Against this run those are
+5.9%, +3.5% and +2.1% for the three `row` medians, −2.7% and −3.8% for the two H2 ratios, and −2.1% for H3, so the
run-to-run spread of a reported number is at most about 6% on this loaded machine. That spread, not a threshold, is the
precision of every number above. The earlier run's `results.json` was overwritten by this one (the card commits one
results file), so its numbers are quoted from the table that run printed; the command is the one in Method.

## Conclusion

Final (Opus, 2026-10-23). Every number below was re-derived from `results.json`: the 11 medians from the recorded
elapsed times, the speedups, the ratios and the projection.

- **H1: supported.** On `chain=row`, the analytic reference scene at 400 px went from a median 487,929 paths/s at 1
  thread to 860,571 at 2 (×1.764) and 1,450,840 at 4 (×1.686). Each of the 3 paired repeats was faster at T than at T/2
  for both T = 2 and T = 4, so the card's rule holds.
  - The rule alone is weak. If the thread count had no effect and the noise were symmetric, three paired repeats would
    all come out faster with probability 1/8, and `chain=image`, a single chain (SPEC §3), passed it at T = 2 with a
    median ×1.031.
  - The `row` support also rests on the size: ×1.764 and ×1.686 are far outside the run-to-run spread of about 6%.
  - `chain=lane:16` grows like `row` (458,947 / 831,039 / 1,462,164 paths/s, ×1.811 and ×1.759), as SPEC §3's one chain
    per (lane, pass) predicts. `chain=image` does not grow (468,249 / 482,701 / 469,118 paths/s, ×1.031 and ×0.972), as
    its single chain requires.
- **H2: measurement.** 1,450,840 paths/s with no triangles, 845,959 with the 12 triangles of the quads (×0.583), and
  741,658 with the 81,932 triangles of the quads and the level-6 icosphere (×0.877 against the triangle scene).
  Replacing the six analytic planes by 12 triangles costs 41.7% of the throughput, and adding 81,920 more triangles
  costs 12.3%: the step from analytic planes to the triangle path is the large one, not the triangle count. This is one
  mesh at one size, with no threshold attached.
- **H3: projection.** 1920×1080 × 1024 passes at `chain=row`, 4 threads, from the analytic median: **0.407 h, about
  24.4 min** (2,123,366,400 paths at 1,450,840 paths/s = 1,463.5 s). Blender scenes are meshes, so a Blender render goes
  through the triangle path. The same projection gives 41.8 min from the triangle scene and 47.7 min with the
  icosphere (estimation only, as pre-registered). A guide (T7.5) should quote the triangle number next to the
  registered one, with this machine and its load.
- **Caveats.**
  - The machine was shared and loaded: the 1-minute load average was 15.4-16.9 on 12 CPUs before and after every
    render. No idle-machine number was measured, so these are loaded-machine numbers, not a bound.
  - H1's support depends on that load. The audit's own rerun, at a 1-minute load of 24-34, measured `row`'s 4-thread
    speedup at ×1.14, and the rule failed there (audit of t-m3-18, 2026-10-22). So the registered verdict holds for
    this run only. Thread scaling on a busier machine is not established.
  - Two runs a few minutes apart differ by up to about 6% in the medians. That estimate comes from one earlier run whose
    `results.json` was overwritten, so its numbers are quoted from the table it printed.
  - The timed interval includes the scene snapshot and the object-id pass, at most 1/16 of it (Method).
