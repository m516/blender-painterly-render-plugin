# Experiment 009: plan for the render and analysis card

The README (Background, Hypothesis, Method) is the specification. This plan says how to implement it. If something in
the README cannot be implemented as written, stop and report it. Opus then adds an "Amendments before analysis"
subsection. Do not change a hypothesis, a rule, a block set or a configuration.

## Files

- The directory is `experiments/009-2026-10-15-scale-limits/`. `2026-10-15` is the date of the Opus commit that created it
  with the pre-registration (`$(date +%F)` on that day, 2026-10-15 or later). Protocol step 1's `DATE=$(date +%F)` on
  the card's own day does not apply: the committed README's commands name this directory. Find it with
  `ls -d experiments/009-*-scale-limits` and require exactly one match. Set `EXP` to it for the commands below.
- Experiments 007 and 008 are committed before this one (`experiments/007-*-noise-locking` and
  `experiments/008-*-jitter-dose-response`, one match each). If either is absent, stop and report.
- Opus commits `README.md` (Background, Hypothesis, Method, with `2026-10-15` replaced) and `jobs.py` there as the
  pre-registration before this card runs. If they are absent, stop and report.
- Create there: `analyze.py` and `test_analyze.py`; `results.json` and the nine figures below, written by `analyze.py`.
- Modify:
  - `$EXP/README.md`: replace only the two "Pending" lines under `## Results` and `## Conclusion` (the
    pre-registration commit created both headings) and, if needed, add an "Amendments" subsection (Acceptance);
  - `analysis/painterly_analysis/metrics.py`: add `cross_structure_correlation` (below);
  - `analysis/painterly_analysis/__init__.py`: import it and list it in `__all__`, as every public metrics function is;
  - `analysis/tests/test_scale_metrics.py`: its tests;
  - `experiments/README.md`: the 009 row exists (added by the pre-registration commit, status `draft`, Conclusion
    "pre-registered; analysis pending"). Replace only its Conclusion cell with a one-line summary of the verdicts.

- `jobs.py` is not changed. No change to `third_party/`, `docs/`, `src/`, or the files of experiments 001-008.
- **Never run `make oracle`.** The binary `.cache/oracle-build/src/app/smallpaint_oracle` (sha256
  `066bb5d4247c556ad5232bfc4fff75dc5f37089840b23f1ecc8fdd9cb518828a`) keys the render cache. Its source has changed
  since it was built, so a rebuild changes the sha256 and orphans the 96 reused renders.

## Order of work

0. Dispatch conditions (the orchestrator establishes them before the card starts; the card checks the first two):
   - the free space of the cache filesystem is at least the requirement of README Cost, Disk (7,997,487,936 B before
     008 renders, 7,585,884,352 B once 008 and its smoke run are done). The card frees and deletes nothing;
   - 007 and 008 are committed;
   - no other CPU-heavy session runs while the render calls of step 4 run.
1. Write `analyze.py --preflight` first and run it. It renders nothing and must exit 0 before any render. It checks
   that:
   - the sha256 of `oracle.oracle_binary()` (hashlib over the file) equals the README's
     `066bb5d4247c556ad5232bfc4fff75dc5f37089840b23f1ecc8fdd9cb518828a`;
   - each of the 96 jobs of the six `REUSED` blocks has a `done` marker in
     `experiment.cache_root() / experiment.job_key(job)`;
   - the free space of `experiment.cache_root()` (`shutil.disk_usage(...).free`) is at least the bytes of the jobs not
     yet done. A job's bytes are `BYTES_PER_PIXEL × size² + RENDER_OVERHEAD_BLOCKS × os.statvfs(root).f_frsize`. The
     sum runs over:
     - 009's `jobs.JOBS`;
     - the `JOBS` of the one `jobs.py` matching `experiments/*-jitter-dose-response/jobs.py` (assert exactly one
       match), loaded with `report.load_jobs_module`;
     - with `--smoke-cache DIR`: the jobs of `jobs.build_ensembles(2, 4)` without a `done` marker under
       `DIR/renders/<job_key>`, when DIR (or its nearest existing parent) has the `st_dev` of the cache root.
     It prints the requirement and the free space, both in bytes;
   - with `--since STATE` (a JSON list of job keys; a missing file is the empty list): no 1600 px job of 009 that is
     done and not listed in STATE has `meta.json` `wall_seconds` above `CONTENTION_SECONDS` (the README's stop rule).
     When every check passes, it rewrites STATE with all done 1600 px job keys; when a check fails, STATE is left
     unchanged.
   If any check fails, stop and report. Do not render, do not delete anything, and do not rebuild the oracle.
2. Add `metrics.cross_structure_correlation` and its tests. `make test` must pass.
3. Smoke run (below), with `run_in_background` and a log file; wait for its exit status. It must exit 0.
4. Render. Repeat, until a render call exits 0:
   - run `--preflight --since <scratch>/preflight-1600.json --smoke-cache <scratch>/cache` in the foreground; stop if
     it fails;
   - run, in the foreground with the Bash tool's `timeout` set to 600000 ms:

     ```
     timeout -k 10 590 env PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python -m painterly_analysis.experiment run "$EXP/jobs.py" --budget 90 --workers 4
     ```

   - exit 0: rendering is complete. Exit 3: jobs remain; loop. Exit 124 or 137 (the call did not return within
     10 minutes) or any other status: stop and report (CPU contention for 124 and 137, README stop rule).
   Expect about 51 calls (about 3 at 200 px, 40 at 800 px, 8 at 1600 px) and about 2.3 h of wall time. Never retry a
   killed call with a longer timeout: a 1600 px call that does not fit in 590 s will not fit on a retry either.
5. Full analysis into `$EXP`, with `run_in_background` and a log file; wait for its exit status. Then repeat it into a
   scratch `--out-dir` the same way, and check `results.json` and every figure byte for byte with `cmp`.
6. Replace the "Pending" lines under `## Results` (tables of numbers from the printed output) and `## Conclusion`; the
   Conclusion starts with
   `DRAFT (Haiku) — pending Opus review.` The H2 verdict states the family-wise error caveat of README H2 Power.

## Reuse (no copies)

- **006's measurement code.** 006 is final, so its `analyze.py` is frozen. Load it as 008 does, with
  `report.load_jobs_module(REPO_ROOT / "experiments/006-2026-10-09-jitter-units/analyze.py")`, and call:
  - `side_params(side, 400, scale, notes)`: σ, e, τ, the profile lags and the spectral band, with smoke rounding;
  - `_masks(object_id, radius)` and `FIXED_EROSION`, for 006's measured-region rule;
  - `_pair_values(a, b, params, measured, masks, fixed_masks)`, for the T keys, the estimation-only keys and the
    region-4 profile of a pair. It reads only `.sum` of its two arguments, so a subsampled render can be passed as an
    `io.OracleRender` built from sliced arrays;
  - `_keys(measured)`, for the key lists;
  - `_preview(img8)`, for every 200 px tile. It box-averages a side that is a multiple of 200 (`report.block_preview`
    by s/200) and repeats a side that divides 200 (smoke scale), so the same call works at both scales;
  - `PROFILE_REGION`, `PROFILE_LAGS`, `LAG_UNIT_SIDE`, and the panel constants of `fig_slag_profile.png`.
  The 006 consistency check below catches any change in these functions.
- **Drawing.** Use `report.draw_line` and `report.paint`, which experiment 007's card adds and which runs before this
  card. If they are absent, load 006's `_draw_line` and `_paint` the same way. Do not write a third copy.
- `painterly_analysis.report`: `family_test` (with `labels`), `summary_table`, `check_seed_reuse`,
  `largest_abs_rel_diff`, `largest_abs_cohen_d`, `format_largest`, `write_results_json`, `block_preview`, `mosaic`,
  `ab8_of_pair`, `load_jobs_module`.
- `painterly_analysis.ensemble`: `effect_summary`, `holm`, `min_attainable_pvalue`, `permutation_pvalue`.
- `painterly_analysis.metrics`: `luminance`, `gaussian_highpass`, `DIFFUSE_REGION_IDS`, `HIGHPASS_SIZE`, and the new
  `cross_structure_correlation`.
- `painterly_analysis.experiment`: `load`, `run_jobs` (smoke only), `job_key`, `cache_root`, `DEFAULT_BUDGET_SECONDS`.
- `painterly_analysis.io`: `OracleRender`, `smallpaint_display`, `write_png`.
- `jobs.py`: `DESIGN`, `CONFIGURATIONS`, `BLOCK_SETS`, `REUSED`, `BLOCK`, `PASSES`, `REFERENCE_SIDE`, `F_DEFAULT`,
  `F_ZERO`, `F_PIXEL_200`, `image_plane_jitter`, `build_ensembles`.

## Add to `metrics.py`, with unit tests

`cross_structure_correlation(hp_a, hp_b, hp_c, hp_d, mask) -> Array`, dimensionless. It returns
`[cov(a, c) + cov(a, d) + cov(b, c) + cov(b, d)] / 4 / sqrt(cov(a, b) · cov(c, d))`, where each `cov` is `_masked_cov`
over `mask` (population form, each field centred by its own masked mean). It raises ValueError if `cov(a, b) <= 0` or
`cov(c, d) <= 0`, since the correlation is then undefined, and on an empty mask (`_count`). The docstring states the
README's reading: with independent noise in all four fields, it estimates the correlation of the two shared textures at
the same points.

Tests in `analysis/tests/test_scale_metrics.py`:
- `a = b = c = d = x` (non-constant on the mask) gives 1, at `rtol=1e-12`. This is an analytic identity in float64:
  the numerator is `4·cov / 4` (exact), and `sqrt(cov²)` differs from `cov` by about one ulp.
- `c = d = 2x + 3` gives 1 at the same tolerance (scale and offset invariance). `c = d = −x` gives −1.
- Exact zero: on a 2 × 2 mask, `x = [[1, −1], [1, −1]]` and `y = [[1, 1], [−1, −1]]`, with `a = b = x` and `c = d = y`,
  give exactly 0.
- Values outside the mask do not change the result (set them to 1e6): exact equality.
- `b = −a` raises ValueError, and so does an empty mask.

## New code in `analyze.py`

No import-time side effects other than loading 006's `analyze.py` and this experiment's `jobs.py`.

Constants, each with a comment that cites the README:
- `SIGNIFICANCE = 0.01`. Levels: H1 `SIGNIFICANCE` (one comparison per family); the 006 reproduction check
  `SIGNIFICANCE / 3` (006's level); H2 `SIGNIFICANCE`; H3 `SIGNIFICANCE / 3` per footprint, split into
  `SIGNIFICANCE / 6` for the departure family and `SIGNIFICANCE / 6` for the outside family when D_f is not empty, and
  `SIGNIFICANCE / 3` for the outside family (all 21 units) when D_f is empty;
- `BOOTSTRAP_RESAMPLES = 10_000`, `BOOTSTRAP_SEED = 0`, `CI_DECISION = (0.5, 99.5)` (the 99% interval: level
  0.01 = `SIGNIFICANCE`; README, Bootstrap);
- `DOMINANCE = Fraction(1, 2)`: where the two parts of Δ = c + u are equal (a definition);
- `G_SHRINK = Fraction(1, 4)`: reading G's step ratio per doubling, from σ(s) ∝ s (README, H1, a derivation);
- `ORACLE_SHA256`;
- `K_CHAIN_BOUND = 2**22` (SPEC §3);
- `BYTES_PER_PIXEL = 3 * 8 + 8 + 4 + 3`: the float64 RGB `sum`, uint64 `k_consumed`, int32 `object_id` and 8-bit RGB
  `image.ppm`;
- `RENDER_OVERHEAD_BLOCKS = 8`: a bound on a render's disk use beyond `BYTES_PER_PIXEL` per pixel, in filesystem
  blocks: the rounding of its six files (four arrays, `meta.json`, `done`) to whole blocks, which also holds the array
  headers and the two small files, plus its directory (README, Cost, Disk);
- `CONTENTION_SECONDS = experiment.DEFAULT_BUDGET_SECONDS`: the protocol's per-call budget (README, stop rule);
- `MAX_FIGURE_BYTES = 1_000_000`, `PREVIEW_SIDE = 200`, `SMOKE_PREFIX = "SMOKE (code check only): "`;
- `CLASS_UNITS = ("A", "X", "Y")`; `D400_CANDIDATES = ("A", "X", "Y", "r4.slag.x")` (README, Departure sets);
- `SELECTION_ORDER = ("row_s200", "row_s800", "row_j0_s200", "row_j0_s800")`: the configurations whose pair indices
  the selection of D_0 and D_1400 draws, in this order;
- `D_0` and `D_1400`: the README's unit tuples (15 and 8 units). At full scale they are checked to equal the output
  of `_select_departures` on the 8-pair-set values of `SELECTION_ORDER`, and to contain 006's `results.json`
  `rejected_keys` of `row_j0_s200 vs row_j0_s800` (H4) and `row_s200 vs row_s800` (H1-row), exactly.

Functions:
- `_preflight(since, smoke_cache)`: as in Order of work, step 1.
- `_check_design(blocks, pairs, scale)`:
  - sides, f as a `Fraction`, blocks, seeds, options and `BLOCK_SETS` equal the README Method table, seeds are unique,
    and no fresh block is a reused, H2 or first block;
  - at full scale, `report.check_seed_reuse(blocks, earlier, REUSED)`, where `earlier` holds the `jobs.py` files of
    001-004 and 006, and the jitter-dose-response `jobs.py` found by its slug, each keyed by the three-digit number
    read from its directory name;
  - at smoke scale, the reused blocks equal 006's `build_ensembles(pairs, scale)` entries.
- `_subsample(render, m)`: an `OracleRender` with `np.ascontiguousarray(x[::m, ::m])` for `sum`, `k_consumed` and
  `object_id`, and the same `meta`. The caller asserts that the subsampled `object_id` equals the native map
  (`np.array_equal`).
- `_measure(jobs, params, measured, m, keep_hp)`: per pair, 006's `_pair_values` (T and estimation-only keys and the
  profile) of the (subsampled, factor m; m = 1 for native) halves, `r{r}.k_per_pass`, and, if `keep_hp`, the two
  high-passed luminance fields for ρ. The fields are computed with the calls of `_pair_values`:
  `metrics.gaussian_highpass(metrics.luminance(smallpaint_display(sum, PASSES)), params.sigma)`.
  - Keep fields only for images that enter a pointwise contrast. Native 1600 px fields are never kept.
  - It also returns the sha256 of each render's `sum` (replicate check) and the largest row total of `k_consumed`
    (chain bound).
- `_block_set(configuration, name)`: the concatenated pair values of the named block set's blocks (`jobs.BLOCK_SETS`;
  the 8-pair set is `CONFIGURATIONS[c][:1]`, the pooled set all of `CONFIGURATIONS[c]`).
- `_class_stats(pair_values, measured)`: adds A, X and Y to each pair's record, so that every pair holds the 21 units
  (README, Units).
- `_select_departures(values, measured)`: the README's procedure (Departure sets), with its own
  `np.random.default_rng(BOOTSTRAP_SEED)` and `integers(0, n, (BOOTSTRAP_RESAMPLES, n))` drawn per configuration in
  `SELECTION_ORDER`. It returns, per footprint, the selected units in `UNITS` order and every unit's interval. At
  smoke scale it runs on the smoke values as a code check, is recorded, and does not decide anything: H3 then uses
  `D_0` and `D_1400` intersected with the measured units, and records the dropped units.
- `_compare(runs_a, runs_b, level, keys)`: `report.family_test` on a key or unit family, plus effect summaries and
  maxima, as 006's `_compare` (with the T-only maxima).
- `_bootstrap(...)`: one `np.random.default_rng(BOOTSTRAP_SEED)`.
  - Pair indices are drawn once per (configuration, block set), configuration-major: the outer loop is the
    configurations in `CONFIGURATIONS` order, the inner loop the block sets in the order 8-pair, H2, fresh, pooled. The
    indices are shared by every statistic of that block set.
  - A render's native and subsampled values share its indices.
  - Intervals are `np.percentile(resampled, CI_DECISION)` with numpy's default (linear) method, as in the
    planning scripts and in `_select_departures`.
  - It gives the intervals (`CI_DECISION`) of every step (s2, s3, s3 − s2/4, s3 − s2) of every unit, every
    departure, Δ_400 − Δ_1400, c, u and χ. A resample in which some Δ_i is exactly 0 is dropped from χ and counted.
- `_decomposition(native200, sub200, native800, units, departure_units)`: Δ_i, c_i and u_i per unit, and χ, on the
  fresh set (and on the pooled set for E5, estimation only).
- `_xcorr(native_fields, sub_fields, masks, measured)`: ρ_x for pair i with pair i, and ρ_self for pairs (2i, 2i + 1)
  of each ensemble, per region, with means and sds (ddof 1). An sd of fewer than two values is recorded as None and
  printed `n/a` (at smoke scale an 8-pair-set block has 2 pairs, so one ρ_self value). There is no bootstrap: a
  resample can pair a pair with itself.
- Pure decision functions, tested in `test_analyze.py`. Each takes the intervals as `(lo, hi)` tuples and returns a
  string from a fixed tuple of names:
  - `h1_reading(s2, s3, s3_minus_g, s3_minus_s2)` returns `I`, `G`, `I or G`, `F`, `S`, `N` or `not separated`
    (README, Reading rule). If `s2` contains 0: `N` iff `s3` and `s3_minus_s2` lie on the same side of 0, otherwise
    `not separated`. Otherwise σ is the side of 0 on which `s2` lies, and the registered I … N rule follows;
  - `h1_key_reading(key, reading_by_unit, s2_by_unit)`: the reading of the key's class when the class's `s2` interval
    excludes 0, otherwise the key's own reading. A key's class is `A` for `structure_std`, `X` for `slag.x`, `Y` for
    `slag.y`;
  - `h1_decision(rejected_keys, reading_by_key, powered)` returns `supported`, `partially supported (G)`,
    `refuted (<reading>)`, `inconclusive` or `inconclusive (underpowered)`;
  - `h2_z_state(dep400, shift, dep1400_point)` returns `removed`, `reduced`, `reversed` or `none` (README, Removal
    conditions; σ_Z = +1 when `dep1400_point == 0`), where `shift` is the interval of Δ_400 − Δ_1400;
  - `h2_decision(rejected_keys, state_by_z, powered)` over Z ∈ {A, `r4.slag.x`}, returning `supported (removed)`,
    `partially supported (reduced)`, `refuted`, `not shown (reversed)`, `not shown` or `inconclusive (underpowered)`;
  - `h3_departure_set_400(h2_verdict, rejected_keys, dep400_by_candidate)` returns `("no departure", ())` when H2 reads
    supported (removed), `("inconclusive (underpowered)", ())` when H2 is underpowered (its `rejected_keys` is None),
    and otherwise `("units", units)` with H2's rejected keys plus each of `D400_CANDIDATES` whose interval excludes 0,
    in `UNITS` order, or `("departure not located", ())` when that is empty;
  - `h3_classify(departure_rejected, chi_interval, state, powered)` returns `undersampling`, `chain`, `mixed`,
    `chain part detected, share unresolved`, `inconclusive`, `no departure`, `departure not located` or
    `inconclusive (underpowered)`. "Lies below 1/2" is `hi < DOMINANCE`, "above" is `lo > DOMINANCE`, "contains" is
    `lo <= DOMINANCE <= hi`;
  - `h3_flag(outside_rejected, powered)` returns True, False or None (underpowered);
  - `h3_footprint_verdict(cls, flag)` and `h3_decision(verdicts)`: the README's mapping (`no departure` and
    `departure not located` → supported), and the lowest verdict in the order refuted < inconclusive < partially
    supported < supported. A footprint whose class or flag is underpowered is `inconclusive (underpowered)`, ranked
    with inconclusive.
  An underpowered comparison, which happens only at smoke scale, makes the decision that depends on it
  `inconclusive (underpowered)`, as in 006. A `rejected_keys` of None is never iterated.
- `_h1`, `_h2`, `_h3`, `_e1` … `_e5`, the profile, the figures, and `main` with `--preflight`, `--since`,
  `--smoke-cache`, `--out-dir`, `--pairs` (pairs per block, default 8) and `--scale` (default 1). A smoke run must not
  write into the experiment directory, sets `"smoke": true`, and prefixes every printed line with `SMOKE_PREFIX`, as
  in 006.

Design checks, each of which stops the run (README, Analysis):
- the design, block-set and seed-reuse checks;
- P = 64 for every render;
- one object-id map per side, and every subsampled map equal to the native one;
- `2 * args.pairs` distinct `sum` digests per block (16 at full scale);
- every row total of `k_consumed` below `K_CHAIN_BOUND`;
- consistency with 006, at full scale:
  - the 8-pair-set `report.summary_table` of the six reused configurations equals 006's `results.json` `summary` for
    every key, mean and sd, exactly (`==`);
  - `row_s400 vs row_s800` and `row_j0_s400 vs row_j0_s800` give the same p-values and rejected keys as 006's H1-row and
    H4 records;
  - `_select_departures` returns `D_1400` and `D_0` exactly, and each contains 006's rejected keys.
  Any mismatch raises. Do not loosen a check to a tolerance; report the failure.

## Outputs

- `results.json` (`report.write_results_json`). Top-level keys:
  - `experiment`, `smoke`, `scale`, `pairs`, `passes`, `oracle_sha256`;
  - `configurations`: side, f and j as strings such as `"1/400"`, the largest displacement in px, options, blocks,
    seeds, and the block set of each block;
  - `parameters`, `regions`, `replicates`, `chain_bound`, `consistency_006`, `key_families` (T, the units, D_0 and
    D_1400 with their selection intervals, D_400 with its state, and at smoke scale the dropped units with their
    regions);
  - `summary` for the 8-pair, H2, fresh and pooled sets;
  - `hypotheses`: H1-default, H1-zero, H2 and H3, with every comparison, the readings with their intervals, the H2
    conditions, the decompositions, χ, the classes and flags, the ρ table and every effect statistic;
  - `decisions`;
  - `estimation`: E1 to E5 and the profile;
  - `bootstrap`: resamples, seed, percentiles and dropped resamples;
  - `figures`: the encodings.
- Printed tables, one per planned Results table:
  - 0, parameters per side;
  - 1, T keys per configuration (8-pair set) and the fresh-set means of the six H3 configurations;
  - 2, H1: the (800, 1600) comparisons and the (400, 800) reproduction check;
  - 3, H1 readings: s2, s3, s3 − s2/4 and s3 − s2 of A, X and Y and of every rejected key, with intervals, beside G's
    predicted numbers (E1);
  - 4, H2: the comparison, the removal conditions for A and `r4.slag.x`, and the A, X and Y departures at the three
    footprints;
  - 5, H3: per footprint the departure set and its state, the rejected units of both families, Δ, c and u per unit of
    D_f, χ with its interval, the class and the flag;
  - 6, ρ_x and ρ_self;
  - 7, E2 pointwise contrasts;
  - 8, E3 footprint effects;
  - 9, E4 K stride;
  - 10, E5 (fresh and pooled sets);
  - 11, replicates and the chain bound.

## Figures

All are drawn with numpy and `io.write_png`, without text. Encodings go in `results.json` `figures`. Assert that each
file is at most `MAX_FIGURE_BYTES`. Every 200 px tile is made with 006's `_preview` (Reuse).

- `fig_grid_row.png`, `fig_grid_row_zero.png` and `fig_grid_row_f400.png`: `_preview(report.ab8_of_pair(...))` of
  pair 0 of each configuration in a family (8-pair set), in side order. They have 4, 4 and 2 tiles: about 0.4, 0.4 and
  0.2 MB (006's three-tile rows were 0.30 MB).
- `fig_points_default.png`, `fig_points_zero.png` and `fig_points_f400.png`: three 200 px tiles each, from pair 0 of the
  fresh set:
  - `_preview` of the native 200 px pair 0;
  - `_preview` of `smallpaint_display` of the summed subsampled 800 px pair 0 (the coincident points, not averaged);
  - `_preview(report.block_preview(img800, 4))` of the 800 px pair 0.
  About 0.3 MB each.
- `fig_slag_profile.png`: 006's layout with four columns (200, 400, 800, 1600 px). Rows are `slag.x` and `slag.y` of
  region 4 against ℓ = 1, 2, 3 (lags ℓ·s/200 px). Series, mean ± sd over the 8-pair set:
  - f = 1/1400, blue (31, 119, 180), solid;
  - f = 0, green (44, 160, 44), dashed;
  - f = 1/400, orange (255, 127, 14), solid, at 200 and 800 px only.
- `fig_steps.png`: three panels (A, X, Y) against log₂(s/200) = 0 … 3, with the same series and colours, mean ± sd
  (8-pair set).
- `fig_decomposition.png`: one row per footprint with a non-empty D_f. For each unit of D_f there is a group of three
  bars: Δ (grey (128, 128, 128)), c (red (214, 39, 40)) and u (blue (31, 119, 180)), each divided by |Δ_i| so that Δ is
  ±1. Each bar has whiskers at its 99% bootstrap interval, and there is a zero line (fresh set).

## `test_analyze.py` (fast, deterministic; collected by `make test`)

Loading: `analyze = report.load_jobs_module(Path(__file__).resolve().parent / "analyze.py")`. It names the module after
its directory and does not touch `sys.path` or `sys.modules`. Never use a bare `import analyze`: pytest runs with
`--import-mode=importlib` and `experiments/` in `testpaths`, so 008's and 009's `analyze` modules would collide.

Intervals in these tests are given as exact `(lo, hi)` tuples of binary fractions (for example s2 = 0.25, so g = 0.0625
exactly), so every boundary case is exact.
- `h1_reading`, with `s2` excluding 0: I (s3 = (0, 0), s3 − g = (−0.0625, −0.0625)); G (s3 − g contains 0, s3
  excludes it); I or G; F (s3 = 0.03125); S (s3 = 0.125); N for s3 = 0.25 (s3 − s2 = (0, 0) does not lie on the
  opposite side) and for a reversal (s3 = −0.125); the same cases with s2 negative.
- `h1_reading`, with `s2` containing 0 (for example (−0.25, 0.25), and (0, 0.25) at the boundary): N when s3 and
  s3 − s2 both lie above 0, and both below; `not separated` when s3 contains 0, and when s3 − s2 lies on the other side.
- `h1_key_reading`: the class's reading when the class's s2 excludes 0, and the key's own when it contains 0.
- `h1_decision`: no rejection; rejections whose keys read G, F, G and F, N, S, I, "I or G", "not separated", G with
  "I or G", and N with G; unpowered.
- `h2_z_state` and `h2_decision`: removed for both Z (supported); reduced for one and removed for the other (partially
  supported); a Δ_400 on the far side (not shown (reversed)), including a reversed Δ_400 whose shift interval lies on
  the zero side, which the first draft's rule read as a reduction; a shift interval that contains 0 (not shown);
  1 rejection (refuted); σ_Z with `dep1400_point == 0`; unpowered.
- `h3_departure_set_400`: H2 supported (removed) → no departure; refuted with rejected keys → those keys plus the
  candidates whose interval excludes 0, in `UNITS` order; not shown with no candidate excluding 0 → departure not
  located; `rejected_keys` None → inconclusive (underpowered).
- `h3_classify`:
  - no rejection with `hi = math.nextafter(0.5, 0)` gives undersampling, and with `hi = 0.5` inconclusive;
  - a rejection with `lo = math.nextafter(0.5, 1)` gives chain, with `lo = 0.5` share unresolved, with
    `hi = math.nextafter(0.5, 0)` mixed;
  - no departure, departure not located, and unpowered.
- `h3_flag` and `h3_footprint_verdict` for every class with flag True, False and None.
- `h3_decision` for each combination of two footprint verdicts, including a flagged "no departure" and a flagged
  "departure not located".
- `_select_departures` on toy values: a unit with complete separation is selected, a unit with identical values in both
  configurations is not.
- χ on toy means, with an exact expected median.
- `_subsample` on a small integer array: it keeps exactly the rows and columns ≡ 0 (mod m), for m = 2 and 4.
- `_xcorr`'s sd helper: one value gives None, two give the ddof-1 sd.
- 006's `_preview` at the smoke sides 50 and 100 (repeated) and 400 (box-averaged) gives a 200 × 200 tile.
`math.nextafter` gives an exact float neighbour, not a tolerance. No test reads the render cache.

## Smoke run (code check only)

```
PAINTERLY_CACHE=<scratch>/cache PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python \
  "$EXP/analyze.py" --pairs 2 --scale 4 --out-dir <scratch>/out
```

- Run it with `run_in_background` and a log file, and wait for its exit status.
- Sides 50, 100, 200 and 400. It renders 112 jobs (28 blocks × 4), about 620 CPU-s (48 at 50 px, 8 at 100 px, 48 at
  200 px, 8 at 400 px), about 3 minutes with 4 workers. Its cache takes about 136 MB (README, Cost, Disk).
- It prints the smoke roundings, for example τ = 1/4 px → 1 px and e = 1/2 px → 1 px at 50 px.
- The subsampling factors are 2 and 4 (E2: 2, 2, 2 and 4; H3: 4), and the object-id identity still holds and is
  checked.
- Regions. At smoke scale 006 dropped region 2 (`regions.dropped_at_this_scale_or_erosion`). H3 uses `D_0` and `D_1400`
  intersected with the measured units (D_0 loses `r2.slag.x` and `r2.slag.y`; D_1400 loses nothing), and the dropped
  units are recorded in `results.json` `key_families`. At full scale the exact equality check against 006 applies
  instead.
- It skips `check_seed_reuse` and the 006 consistency check; `_select_departures` runs on the smoke values as a code
  check.
- Every tile is made with 006's `_preview`, and ρ_self's sd is None (one value per block).
- Power at 2 pairs per block: 2 vs 2 (H1, smallest p 1/3) and 4 vs 4 (H2, H3 at f = 0 and 1/400, smallest p 2/70) are
  underpowered and read `inconclusive (underpowered)`; an underpowered H2 makes the f = 1/400 footprint
  `inconclusive (underpowered)`. H3 at f = 1/1400 has 8 vs 8 (four fresh blocks, smallest p 1.55e-4). Its departure
  family (D_1400's 8 units, first threshold 0.01/6/8 = 2.08e-4) and its outside family (the other 10 measured units,
  0.01/6/10 = 1.67e-4) are both powered and give SMOKE decisions, which mean nothing. Nothing may crash.

## Acceptance for the card

- The preflight exits 0. The render command exits 0 with `completed=448 remaining=0`.
- The analysis exits 0, with every design check passing, including the 006 consistency check.
- A second run reproduces `results.json` and all nine figures byte for byte.
- `ruff check` and `ruff format --check` pass (line length 100) on the new and changed Python files. `make test`
  passes, including the new metric tests and `pytest experiments/009-*`.
- Each figure is at most 1 MB.
- The README's `## Results` (numbers only) and `## Conclusion` (starting with the DRAFT line) replace the Pending lines. Hypothesis and
  Method stay unchanged, and any deviation goes in an "Amendments" subsection with its reason.
- Estimated cost:
  - renders, about 29,300 CPU-s (352 new renders), about 2.3 h of wall time in about 51 calls;
  - analysis, about 8-10 min per run on an idle machine (about 5 min of measurement, 3-5 min of Monte Carlo
    permutation tests and bootstraps), two runs, each in the background;
  - smoke, about 620 CPU-s of renders, plus its analysis.
