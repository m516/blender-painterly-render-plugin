# Experiment 009: plan for the render and analysis card

The README (Background, Hypothesis, Method) is the specification. This plan says how to implement it. If something in
the README cannot be implemented as written, stop and report it. Opus then adds an "Amendments before analysis"
subsection. Do not change a hypothesis, a rule, a frame or a configuration.

## Files

- Create, under `experiments/009-2026-10-09-scale-limits/`:
  - `README.md` and `jobs.py`, copied unchanged from the pre-registration;
  - `analyze.py` and `test_analyze.py`;
  - `results.json` and the nine figures below, written by `analyze.py`.
- Modify:
  - `analysis/painterly_analysis/metrics.py`: add `cross_structure_correlation` (below);
  - `analysis/tests/test_scale_metrics.py`: its tests;
  - `experiments/README.md`: one index row, status `draft`:

    ```
    | 009 | 2026-10-09 | scale-limits | Does image-locking hold above 800 px, and is the 200 px departure undersampling or a chain effect? | draft | |
    ```

- No change to `third_party/`, `docs/`, `src/`, or the files of experiments 001-008. Never run `make oracle`. The oracle
  binary in `.cache/oracle-build` is the one the render cache is keyed by.

## Order of work

1. Write `analyze.py --preflight` first and run it. It renders nothing and must exit 0 before any render. It checks
   that:
   - the sha256 of `oracle.oracle_binary()` (hashlib over the file) equals the README's
     `066bb5d4247c556ad5232bfc4fff75dc5f37089840b23f1ecc8fdd9cb518828a`;
   - each of the 96 jobs of the six `REUSED` blocks has a `done` marker in
     `experiment.cache_root() / experiment.job_key(job)`;
   - the free space of `experiment.cache_root()` (`shutil.disk_usage`) is at least the bytes of the jobs not yet done,
     at `BYTES_PER_PIXEL × size²` each, summed over 009's `jobs.JOBS` and over the `JOBS` of
     `experiments/008-*/jobs.py` (7.44 GB for 009 and 0.40 GB for 008 when nothing is rendered);
   - no finished 1600 px job of 009 has `meta.json` `wall_seconds` above `CONTENTION_SECONDS` (the README's stop rule).
   If any check fails, stop and report. Do not render, and do not rebuild the oracle.
2. Add `metrics.cross_structure_correlation` and its tests. `make test` must pass.
3. Smoke run (below). It must exit 0.
4. Render with the README's command (`--budget 90 --workers 4`). Before every call, run `--preflight` again; stop if it
   fails. Repeat until the render command exits 0. Expect about 51 calls (about 3 at 200 px, 40 at 800 px, 8 at
   1600 px) and about 2.3 h of wall time. Each call stays under 10 minutes. If a call does not return within
   10 minutes, stop and report CPU contention.
5. Full analysis into the experiment directory. Then repeat it into a scratch `--out-dir` and check `results.json` and
   every figure byte for byte with `cmp`.
6. Add `## Results` (tables of numbers from the printed output) and `## Conclusion`, which starts with
   `DRAFT (Haiku) — pending Opus review.`

## Reuse (no copies)

- **006's measurement code.** 006 is final, so its `analyze.py` is frozen. Load it as 008 does, with
  `report.load_jobs_module(REPO_ROOT / "experiments/006-2026-10-09-jitter-units/analyze.py")`, and call:
  - `side_params(side, 400, scale, notes)`: σ, e, τ, the profile lags and the spectral band, with smoke rounding;
  - `_masks(object_id, radius)` and `FIXED_EROSION`, for 006's measured-region rule;
  - `_pair_values(a, b, params, measured, masks, fixed_masks)`, for the T keys, the estimation-only keys and the
    region-4 profile of a pair. It reads only `.sum` of its two arguments, so a subsampled render can be passed as an
    `io.OracleRender` built from sliced arrays;
  - `_keys(measured)`, for the key lists;
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
- `jobs.py`: `DESIGN`, `CONFIGURATIONS`, `FRAMES`, `REUSED`, `BLOCK`, `PASSES`, `REFERENCE_SIDE`, `F_DEFAULT`,
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

Constants, each with a comment that cites the README:
- `SIGNIFICANCE = 0.01`. Levels: H1 `SIGNIFICANCE` (one comparison per family); the 006 reproduction check
  `SIGNIFICANCE / 3` (006's level); H2 `SIGNIFICANCE`; H3 `SIGNIFICANCE / 3` per footprint, split into
  `SIGNIFICANCE / 6` for the departure family and `SIGNIFICANCE / 6` for the outside family when D_f is not empty, and
  `SIGNIFICANCE / 3` for the outside family (all of T) when D_f is empty;
- `BOOTSTRAP_RESAMPLES = 10_000`, `BOOTSTRAP_SEED = 0`, `CI_PERCENTILES = (2.5, 97.5)`;
- `DOMINANCE = Fraction(1, 2)`: where the two parts of Δ = c + u are equal (a definition);
- `G_SHRINK = Fraction(1, 4)`: reading G's step ratio per doubling, from σ(s) ∝ s (README, H1, a derivation);
- `ORACLE_SHA256`;
- `K_CHAIN_BOUND = 2**22` (SPEC §3);
- `BYTES_PER_PIXEL = 3 * 8 + 8 + 4 + 3`: the float64 RGB `sum`, uint64 `k_consumed`, int32 `object_id` and 8-bit RGB
  `image.ppm`;
- `CONTENTION_SECONDS = experiment.DEFAULT_BUDGET_SECONDS`: the protocol's per-call budget (README, stop rule);
- `MAX_FIGURE_BYTES = 1_000_000`, `PREVIEW_SIDE = 200`, `SMOKE_PREFIX = "SMOKE (code check only): "`;
- `D_0` and `D_1400`: the README's key tuples. At full scale they are checked to equal 006's `results.json`
  `rejected_keys` of `row_j0_s200 vs row_j0_s800` (H4) and `row_s200 vs row_s800` (H1-row), exactly.

Functions:
- `_preflight()`: as above.
- `_check_design(blocks, pairs, scale)`:
  - sides, f as a `Fraction`, blocks, seeds, options and `FRAMES` equal the README Method table, seeds are unique, and
    no fresh block is a reused, H2 or first block;
  - at full scale, `report.check_seed_reuse(blocks, {001-004, 006, 008 jobs.py}, REUSED)`;
  - at smoke scale, the reused blocks equal 006's `build_ensembles(pairs, scale)` entries.
- `_subsample(render, m)`: an `OracleRender` with `np.ascontiguousarray(x[::m, ::m])` for `sum`, `k_consumed` and
  `object_id`, and the same `meta`. The caller asserts that the subsampled `object_id` equals the native map
  (`np.array_equal`).
- `_measure(jobs, params, measured, m, keep_hp)`: per pair, 006's `_pair_values` (T and estimation-only keys and the
  profile) of the (subsampled, factor m; m = 1 for native) halves, `r{r}.k_per_sample`, and, if `keep_hp`, the two
  high-passed luminance fields for ρ. The fields are computed with the calls of `_pair_values`:
  `metrics.gaussian_highpass(metrics.luminance(smallpaint_display(sum, PASSES)), params.sigma)`.
  - Keep fields only for images that enter a pointwise contrast. Native 1600 px fields are never kept.
  - It also returns the sha256 of each render's `sum` (replicate check) and the largest row total of `k_consumed`
    (chain bound).
- `_frame(configuration, frame)`: the concatenated pair values of the frame's blocks (`jobs.FRAMES`; the 8-pair frame
  is `CONFIGURATIONS[c][:1]`, the pooled frame all of `CONFIGURATIONS[c]`).
- `_class_stats(pair_values, measured)`: A, X and Y per pair.
- `_compare(runs_a, runs_b, level, keys)`: `report.family_test` on a key family, plus effect summaries and maxima, as
  006's `_compare` (with the T-only maxima).
- `_bootstrap(...)`: one `np.random.default_rng(BOOTSTRAP_SEED)`.
  - Pair indices are drawn once per (configuration, frame), in `CONFIGURATIONS` order and then frame order (8-pair, H2,
    fresh, pooled), and shared by every statistic of that frame.
  - A render's native and subsampled values share its indices.
  - It gives the intervals of every step (s2, s3, s3 − s2/4, s3 − s2), departure, reduction (Δ_400 − Δ_1400), c, u and
    χ. A resample in which some Δ_i is exactly 0 is dropped from χ and counted.
- `_decomposition(native200, sub200, native800, keys, departure_keys)`: Δ_i, c_i and u_i per key and for A, X and Y,
  and χ, on the fresh frame (and on the pooled frame for E5, estimation only).
- `_xcorr(native_fields, sub_fields, masks, measured)`: ρ_x for pair i with pair i, and ρ_self for pairs (2i, 2i + 1)
  of each ensemble, per region, with means and sds (ddof 1). There is no bootstrap: a resample can pair a pair with
  itself.
- Pure decision functions, tested in `test_analyze.py`. Each takes the intervals as `(lo, hi)` tuples and returns a
  string from a fixed tuple of names:
  - `h1_reading(s3, s3_minus_g, s3_minus_s2, s2_point)` returns `I`, `G`, `I or G`, `F`, `S` or `N` (README, reading
    rule; σ = +1 when `s2_point == 0`);
  - `h1_decision(rejected_keys, reading_by_class, powered)` returns `supported`, `partially supported (G)`,
    `refuted (<reading>)`, `inconclusive` or `inconclusive (underpowered)`. A key's class is `A` for `structure_std`,
    `X` for `slag.x`, `Y` for `slag.y`;
  - `h2_decision(rejected_keys, dep400_by_z, reduction_by_z, dep1400_point_by_z, powered)` over Z ∈ {A, `r4.slag.x`},
    returning `supported (removed)`, `partially supported (reduced)`, `refuted`, `not shown` or
    `inconclusive (underpowered)`;
  - `h3_classify(departure_rejected, chi_interval, has_departure, powered)` returns `undersampling`, `chain`, `mixed`,
    `chain part detected, share unresolved`, `inconclusive`, `no departure` or `inconclusive (underpowered)`.
    "Lies below 1/2" is `hi < DOMINANCE`, "above" is `lo > DOMINANCE`, "contains" is `lo <= DOMINANCE <= hi`;
  - `h3_flag(outside_rejected, powered)` returns True, False or None (underpowered);
  - `h3_footprint_verdict(cls, flag)` and `h3_decision(verdicts)`: the README's mapping, and the lowest verdict in the
    order refuted < inconclusive < partially supported < supported. A footprint whose class or flag is underpowered is
    `inconclusive (underpowered)`, ranked with inconclusive.
  An underpowered comparison, which happens only at smoke scale, makes the decision that depends on it
  `inconclusive (underpowered)`, as in 006.
- `_h1`, `_h2`, `_h3`, `_e1` … `_e5`, the profile, the figures, and `main` with `--preflight`, `--out-dir`, `--pairs`
  (pairs per block, default 8) and `--scale` (default 1). A smoke run must not write into the experiment directory,
  sets `"smoke": true`, and prefixes every printed line with `SMOKE_PREFIX`, as in 006.

Design checks, each of which stops the run (README, Analysis):
- the design, frame and seed-reuse checks;
- P = 64 for every render;
- one object-id map per side, and every subsampled map equal to the native one;
- 16 distinct `sum` digests per block;
- every row total of `k_consumed` below `K_CHAIN_BOUND`;
- consistency with 006, at full scale:
  - the 8-pair-frame `report.summary_table` of the six reused configurations equals 006's `results.json` `summary` for
    every key, mean and sd, exactly (`==`);
  - `row_s400 vs row_s800` and `row_j0_s400 vs row_j0_s800` give the same p-values and rejected keys as 006's H1-row and
    H4 records;
  - `D_0` and `D_1400` equal 006's rejected keys.
  Any mismatch raises. Do not loosen a check to a tolerance; report the failure.

## Outputs

- `results.json` (`report.write_results_json`). Top-level keys:
  - `experiment`, `smoke`, `scale`, `pairs`, `passes`, `oracle_sha256`;
  - `configurations`: side, f and j as strings such as `"1/400"`, the largest displacement in px, options, blocks,
    seeds, and the frame of each block;
  - `parameters`, `regions`, `replicates`, `chain_bound`, `consistency_006`, `key_families` (T, D_0, D_1400, D_400,
    and at smoke scale the D_f keys dropped with their regions);
  - `summary` for the 8-pair, H2, fresh and pooled frames;
  - `hypotheses`: H1-default, H1-zero, H2 and H3, with every comparison, the readings with their intervals, the H2
    conditions, the decompositions, χ, the classes and flags, the ρ table and every effect statistic;
  - `decisions`;
  - `estimation`: E1 to E5 and the profile;
  - `bootstrap`: resamples, seed, percentiles and dropped resamples;
  - `figures`: the encodings.
- Printed tables, one per planned Results table:
  - 0, parameters per side;
  - 1, T keys per configuration (8-pair frame) and the fresh-frame means of the six H3 configurations;
  - 2, H1: the (800, 1600) comparisons and the (400, 800) reproduction check;
  - 3, H1 readings: s2, s3, s3 − s2/4 and s3 − s2 of A, X and Y with intervals, beside G's predicted numbers (E1);
  - 4, H2: the comparison, the removal conditions for A and `r4.slag.x`, and the A, X and Y departures at the three
    footprints;
  - 5, H3: per footprint the rejected keys of both families, Δ, c and u per key of D_f, χ with its interval, the class
    and the flag;
  - 6, ρ_x and ρ_self;
  - 7, E2 pointwise contrasts;
  - 8, E3 footprint effects;
  - 9, E4 draws per sample;
  - 10, E5 (fresh and pooled frames);
  - 11, replicates and the chain bound.

## Figures

All are drawn with numpy and `io.write_png`, without text. Encodings go in `results.json` `figures`. Assert that each
file is at most `MAX_FIGURE_BYTES`.

- `fig_grid_row.png`, `fig_grid_row_zero.png` and `fig_grid_row_f400.png`: `report.ab8_of_pair` of pair 0 of each
  configuration in a family (8-pair frame), `report.block_preview` to 200 px (factor s/200), in side order. They have 4,
  4 and 2 tiles: about 0.4, 0.4 and 0.2 MB (006's three-tile rows were 0.30 MB).
- `fig_points_default.png`, `fig_points_zero.png` and `fig_points_f400.png`: three 200 px tiles each, from pair 0 of the
  fresh frame:
  - native 200 px pair 0;
  - `smallpaint_display` of the summed subsampled 800 px pair 0 (the coincident points, not averaged);
  - `block_preview` of the 800 px pair 0 by 4.
  About 0.3 MB each.
- `fig_slag_profile.png`: 006's layout with four columns (200, 400, 800, 1600 px). Rows are `slag.x` and `slag.y` of
  region 4 against ℓ = 1, 2, 3 (lags ℓ·s/200 px). Series, mean ± sd over the 8-pair frame:
  - f = 1/1400, blue (31, 119, 180), solid;
  - f = 0, green (44, 160, 44), dashed;
  - f = 1/400, orange (255, 127, 14), solid, at 200 and 800 px only.
- `fig_steps.png`: three panels (A, X, Y) against log₂(s/200) = 0 … 3, with the same series and colours, mean ± sd
  (8-pair frame).
- `fig_decomposition.png`: one row per footprint with a departure. For each key of D_f there is a group of three bars:
  Δ (grey (128, 128, 128)), c (red (214, 39, 40)) and u (blue (31, 119, 180)), each divided by |Δ_i| so that Δ is ±1.
  Each bar has whiskers at its 95% bootstrap interval, and there is a zero line (fresh frame).

## `test_analyze.py` (fast, deterministic; collected by `make test`)

Intervals in these tests are given as exact `(lo, hi)` tuples of binary fractions (for example s2 = 0.25, so g = 0.0625
exactly), so every boundary case is exact.
- `h1_reading`: I (s3 = (0, 0), s3 − g = (−0.0625, −0.0625)); G (s3 − g contains 0, s3 excludes it); I or G; F
  (s3 = 0.03125); S (s3 = 0.125); N for s3 = 0.25 (s3 − s2 = (0, 0) does not lie on the opposite side) and for a
  reversal (s3 = −0.125); the same cases with s2 negative; and `s2_point == 0`.
- `h1_decision`: no rejection; rejections whose classes read G, F, G and F, N, S, I, "I or G", G with "I or G", and
  N with G; unpowered.
- `h2_decision`: 0 rejections with both conditions for both Z (supported); reduction for both but a departure interval
  excluding 0 for one (partially supported); a reduction interval on the wrong side of 0; 1 rejection (refuted);
  neither condition (not shown); unpowered.
- `h3_classify`:
  - no rejection with `hi = math.nextafter(0.5, 0)` gives undersampling, and with `hi = 0.5` inconclusive;
  - a rejection with `lo = math.nextafter(0.5, 1)` gives chain, with `lo = 0.5` share unresolved, with
    `hi = math.nextafter(0.5, 0)` mixed;
  - no departure, and unpowered.
- `h3_flag` and `h3_footprint_verdict` for every class with flag True, False and None.
- `h3_decision` for each combination of two footprint verdicts, including a flagged "no departure".
- χ on toy means, with an exact expected median.
- `_subsample` on a small integer array: it keeps exactly the rows and columns ≡ 0 (mod m), for m = 2 and 4.
`math.nextafter` gives an exact float neighbour, not a tolerance. No test reads the render cache.

## Smoke run (code check only)

```
PAINTERLY_CACHE=<scratch>/cache PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python \
  experiments/009-2026-10-09-scale-limits/analyze.py --pairs 2 --scale 4 --out-dir <scratch>/out
```

- Sides 50, 100, 200 and 400. It renders 112 jobs (28 blocks × 4), about 620 CPU-s (48 at 50 px, 8 at 100 px, 48 at
  200 px, 8 at 400 px), about 3 minutes with 4 workers.
- It prints the smoke roundings, for example τ = 1/4 px → 1 px and e = 1/2 px → 1 px at 50 px.
- The subsampling factors are 2 and 4 (E2: 2, 2, 2 and 4; H3: 4), and the object-id identity still holds and is
  checked.
- Regions. At smoke scale 006 dropped region 2 (`regions.dropped_at_this_scale_or_erosion`). Each D_f is intersected
  with the measured T keys, the dropped keys are recorded in `results.json` `key_families`, and an empty intersection is
  classified `no departure`. At full scale the exact equality check against 006 applies instead.
- It skips `check_seed_reuse` and the 006 consistency check.
- Power at 2 pairs per block: 2 vs 2 (H1, smallest p 1/3) and 4 vs 4 (H2, H3 at f = 0 and 1/400, smallest p 2/70) are
  underpowered and read `inconclusive (underpowered)`. H3 at f = 1/1400 has 8 vs 8 (four fresh blocks), so its departure
  family (one key at 0.01/6) is powered and gives a SMOKE decision, which means nothing; its outside family (17 keys) is
  not. Nothing may crash.

## Acceptance for the card

- The preflight exits 0. The render command exits 0 with `completed=448 remaining=0`.
- The analysis exits 0, with every design check passing, including the 006 consistency check.
- A second run reproduces `results.json` and all nine figures byte for byte.
- `ruff check` and `ruff format --check` pass (line length 100) on the new and changed Python files. `make test`
  passes, including the new metric tests and `pytest experiments/009-*`.
- Each figure is at most 1 MB.
- The README gains `## Results` (numbers only) and `## Conclusion` (starting with the DRAFT line). Hypothesis and
  Method stay unchanged, and any deviation goes in an "Amendments" subsection with its reason.
- Estimated cost:
  - renders, about 29,300 CPU-s (352 new renders);
  - analysis, several minutes, mostly the Monte Carlo permutation tests (H2: 18 keys; H3: 3 footprints × 18 keys;
    E5: 2 frames × 3 footprints × 18 keys; 100,000 permutations each);
  - smoke, about 620 CPU-s.
