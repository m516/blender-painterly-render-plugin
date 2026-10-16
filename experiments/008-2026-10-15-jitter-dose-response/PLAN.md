# Experiment 008: plan for the render and analysis card

> **Amendment 1 (Opus, 2026-10-15; see the README).**
> - The experiments' oracle is `.cache/oracle-build/src/app/smallpaint_oracle`, sha256 `804a2dc2…`. Every sha256 below is
>   updated to it.
> - The host makes all renders before this card runs. Skip every render and disk-preflight step and report it "done on
>   host".
> - Read the render cache read-only through `PAINTERLY_CACHE` and `PAINTERLY_BUILD_DIR`, as BACKLOG.md gives them. Never
>   render into it.
> - This card starts only after EXP-REPRO has found every committed output of 001-004 and 006 byte-identical.

The README (Background, Hypothesis, Method) is the specification. This plan says how to implement it.

## Files

- The directory is `experiments/008-2026-10-15-jitter-dose-response/`. `2026-10-15` is the date of the Opus commit that
  creates it with the pre-registration (`$(date +%F)` on that day, 2026-10-15 or later). Protocol step 1's
  `DATE=$(date +%F)` on the card's own day does not apply: the committed README's commands name this directory. Find
  it with `ls -d experiments/008-*-jitter-dose-response` and require exactly one match. Experiment 007 is committed
  before this one, so 008 is the next number. If `experiments/007-*` is absent, stop and report.
- Opus commits `README.md` (Background, Hypothesis, Method, with `2026-10-15` replaced) and `jobs.py` there as the
  pre-registration before this card runs, as for 006 (commit 15b752a). If they are absent, stop and report.
- Create there: `analyze.py`, `power.py`, `test_analyze.py`; `results.json`, `fig_dose_response.png`, `fig_crops.png`
  (written by `analyze.py`).
- Modify:
  - `README.md`: replace only the two "Pending" lines under `## Results` and `## Conclusion` (the pre-registration commit
    created both headings) and, if needed, add an "Amendments" subsection (Acceptance);
  - `experiments/README.md`: the 008 row exists (added by the pre-registration commit, status `draft`, Conclusion
    "pre-registered; analysis pending"). Replace only its Conclusion cell with a one-line summary of the verdicts.
- `jobs.py` is not changed. No change to `analysis/`, `third_party/`, `docs/` or the oracle.
- Never run `make oracle`. The binary `.cache/oracle-build/src/app/smallpaint_oracle` (sha256
  `804a2dc2722167aab472aacc2c0cce4bba53f28f155d63b7a0f2c827a0395954`) keys the render cache; a rebuild from the
  current source changes its sha256 and orphans the 32 reused renders.

## Order of work

1. Write `analyze.py --preflight` first and run it. It must exit 0 before any render. It checks that:
   - the sha256 of `oracle.oracle_binary()` (hashlib over the file) equals the README's
     `804a2dc2722167aab472aacc2c0cce4bba53f28f155d63b7a0f2c827a0395954`;
   - each of the 32 jobs of `f0` and `f1400` has a `done` marker in
     `experiment.cache_root() / experiment.job_key(job)`;
   - the free space of the cache's filesystem (`shutil.disk_usage(experiment.cache_root()).free`) is at least the
     bytes the new renders need: the number of new jobs without a `done` marker times the disk bytes of one cached
     `f1400` render (`st_blocks * 512` summed over its cache directory and the files in it, as `du -sB1` counts;
     README Method, Disk: 6,262,784 B, so 400,818,176 B for 64). It prints both numbers. This is a requirement derived
     from a cached render, not a tuned threshold.
   If it fails, stop and report. Do not render, and do not delete anything to make space: the orchestrator frees disk.
2. Render with the README's command, repeated until exit 0. 64 new renders take about 1,600 CPU-s, so one call is
   expected. A call can take up to about 570 s: run it in the background with a log file (or with a tool timeout of at
   least 600,000 ms) and poll until it exits.
3. Smoke run, then the full analysis, then a second full run into a scratch `--out-dir`, checked byte for byte with
   `cmp`. Run each in the background with a log file and poll until it exits, if it may take longer than a 10-minute
   tool call.
4. Run `power.py` (in the background, as above) and report its tables next to the README's numbers (section
   `power.py`).

## Reuse (no copies)

- **006's measurement code.** 006 is final, so its `analyze.py` is frozen. Load it with
  `report.load_jobs_module(REPO_ROOT / "experiments/006-2026-10-09-jitter-units/analyze.py")` and call:
  - `side_params(side, 400, scale, notes)`, which gives σ, the erosion and τ, with smoke rounding;
  - `_masks(object_id, radius)` and its `FIXED_EROSION`;
  - `_measure_configuration(name, jobs, object_id, params, measured)`, which returns (scaled, fixed, profile,
    digests). Only `scaled` and `digests` are used. It checks passes = 64 and the object-id map;
  - `_keys(measured)` for the T and estimation-only key lists;
  - for the figure: `report.paint` and `report.draw_line`, which experiment 007's card adds and which runs before this
    card. If they are absent, use 006's `_paint` and `_draw_line` from the module loaded above. Do not write a third
    copy.
  `measured` uses 006's rule: the regions that are non-empty under both the scaled erosion and `FIXED_EROSION` in every
  configuration. At 400 px both are 4 px. The consistency check below catches any change in these functions.
  (These 006 functions are not lifted into `painterly_analysis`: 008 changes no library file. 007 owns the `report.py`
  additions and 009 the `metrics.py` addition.)
- `painterly_analysis.report`: `directional_pair_test` (H1, H2), `family_test` (H4, E1's gate G), `summary_table`,
  `check_seed_reuse`, `largest_abs_rel_diff`, `largest_abs_cohen_d`, `ab8_of_pair`, `write_results_json`,
  `format_number`, `format_largest`.
- `painterly_analysis.ensemble`: `holm`, `effect_summary`, `min_attainable_pvalue`, `permutation_pvalue` (H4's
  TOST and margin tests, and `power.py`'s self-check).
- `painterly_analysis.experiment`: `load`, `run_jobs` (smoke only), `job_key`, `cache_root`.
- `painterly_analysis.io.write_png`.
- `jobs.py`: `DESIGN`, `ORDER`, `REUSED`, `BLOCK`, `build_ensembles`, `image_plane_jitter`.

## New code in `analyze.py`

Constants, each with a comment that cites the README:
- `SIGNIFICANCE = 0.01`, `BOOTSTRAP_RESAMPLES = 10_000`, `BOOTSTRAP_SEED = 0`, `CI_DECISION = (0.5, 99.5)`,
  `CI_REPORT = (2.5, 97.5)`, `REFERENCE_SIDE = 400`, `ORACLE_SHA256`, `MAX_FIGURE_BYTES = 1_000_000`,
  `SMOKE_PREFIX = "SMOKE (code check only): "`;
- `DISPLAY_QUANTUM = 1`: display bytes are integers (SPEC §7), so one byte is the step between display levels. A
  definition, not a tuned value;
- `R_BOUNDARIES = (2**-0.5, 2**0.5, 2**1.5)`: the midpoints γ = −1/2, 1/2, 3/2 between the reference exponents
  −1, 0, 1, 2 of H3b's cells. Definitions;
- `CI_UNION = (100 * SIGNIFICANCE / 6, 100 * (1 - SIGNIFICANCE / 6))`: two-sided level 0.01/3 per doubling for a
  claim that holds at some doubling, Bonferroni over the three doublings (README H3, Intervals);
- `DOUBLINGS = (1, 2, 3)`: the doubling pairs of H3 (README H3, Statistics);
- `LINEAR_SLOPE_RATIO = 1` and `LINEAR_DOUBLING_RATIO = 2`: a response linear in f has slope ratio 1, so a doubling's
  step ratio is 2 (README H3a; definitions).

The class keys are A (`r{r}.structure_std`), W (`r4.slag.y`, `r5.slag.y`, `r6.slag.y`) and M (`r{r}.mean.{R,G,B}`).

- `_check_design(ensembles, pairs, scale)`:
  - doses (as `Fraction`), blocks, options and seeds equal the README table, and seeds are unique;
  - at full scale, `report.check_seed_reuse(ensembles, {001-004, 006 jobs.py}, {name: REUSED[name]})`;
  - at smoke scale, the reused configurations equal 006's `build_ensembles(pairs, scale)` entries.
- `_check_006_consistency(summary)` (full scale only): for `f0` and `f1400`, every key's mean and sd equals 006's
  `results.json` `summary` of `row_j0_s400` and `row_s400` exactly (`==`). Any mismatch raises. Do not loosen it; report
  it if it fails.
- `_steps(runs, keys)`: `ensemble.effect_summary(runs[f_{i+1}], runs[f_i], keys)` for i = 0 … 4, on T and the
  estimation-only keys.
- `_bootstrap_draws(pairs)`: one `np.random.default_rng(BOOTSTRAP_SEED)`. For each configuration in dose order (`ORDER`),
  `rng.integers(0, pairs, size=(BOOTSTRAP_RESAMPLES, pairs))`. The draws are made once and shared by H3, H4 and E1. A
  resampled pair carries all its keys. Resampled means and sample sds (ddof 1) come from the per-pair arrays
  (configuration × pair × key), vectorized.
- Power. Every family records `powered`:
  - F1, R1 (30 tests each), R2, V2 (18 each) and H4's margin family S (36): `ensemble.min_attainable_pvalue(n, n,
    alternative) <= SIGNIFICANCE / size`, with the family's one-sided alternative;
  - H4's detection family and gate G: `family_test["powered"]`;
  - TOST: `ensemble.min_attainable_pvalue(n, n, "less") <= SIGNIFICANCE`.
  - A decision that rests on an unpowered family returns `"inconclusive (underpowered)"`, checked before the class
    rules: H1 (F1 or R1), H2 (R2 or V2), H3 (F1, which gates estimability), H4 (TOST or S). `rejected_keys` None (an
    unpowered `family_test`) counts as no rejection, so E1 then lists every key as `"no resolved response"`.
- `_h1(runs)`:
  - 30 `directional_pair_test(runs[hi], runs[lo], key, SIGNIFICANCE)` calls;
  - family F1: `ensemble.holm` on the 30 `p_less` at 0.01; family R1: `ensemble.holm` on the 30 `p_greater` at 0.01;
  - `classify_cell(fall_rejected, rise_rejected)` → `"fall"`, `"rise"` or `"unresolved"`. Both True raises (it cannot
    happen, since p_less + p_greater ≥ 1);
  - `h1_decision(classes, powered)`: `"inconclusive (underpowered)"` if F1 or R1 is unpowered; else `"supported"` iff
    all are falls; `"refuted (reversal)"` iff any is a rise; otherwise `"inconclusive"`. The record lists the rises and
    the unresolved cells with Δ, d and both p.
- `_h2(runs)`:
  - family R2 (18): 3 overall tests (a) (`f350` vs `f0`, `p_greater`) and 15 step tests (s) (`p_greater`); family V2
    (18): 3 overall tests (h) (`f350` vs `f0`, `p_less`, net hardening) and the 15 step tests' `p_less` (r). Holm at
    0.01 on each;
  - `classify_cell` per step and wall, and per wall for the overall pair: `"rise"`, `"hardening"` (the overall
    `"fall"` is named so) or `"unresolved"`;
  - `h2_decision(overall_classes, step_classes, powered)`: `"inconclusive (underpowered)"` if R2 or V2 is unpowered;
    else the refutations `"refuted (reversal)"` (some (r) rejected) and `"refuted (net hardening)"` (some (h)
    rejected), both possible (a list of verdicts); else `"supported"` iff all three overall are rises, with
    `every_step = all 15 are rises`; otherwise `"inconclusive"`, with the unresolved walls' Δ and d.
- `_h3(runs, draws, h1)`:
  - class steps S_i = Σ_r Δ_i(r) over the six A regions, at the point estimate and per resample; q̃_0 = S_1/S_0 and
    ρ̃_i = S_{i+1}/S_i for i in `DOUBLINGS`;
  - `estimable[i]` (i = 0 … 3) = step i is an F1 fall in at least one A region (from `_h1`). A non-estimable ratio is
    recorded as `"denominator not resolved"` and gets no interval;
  - intervals of each estimable ratio at `CI_DECISION`, `CI_UNION` and `CI_REPORT` (`np.percentile`, default linear
    interpolation). A resample with S_i = 0 exactly is dropped from that ratio and counted;
  - `ratio_cell(lo, hi)` with `a, b, c = R_BOUNDARIES`: `hi < a` saturating; `a < lo and hi < b` logarithmic;
    `b < lo and hi < c` linear; `lo > c` accelerating; otherwise inconclusive;
  - `h3b_class(estimable, ci_decision, ci_union)`: `"saturating at doubling i"` for the first i in `DOUBLINGS` with
    `estimable[i]` and `ratio_cell` of its `CI_UNION` interval saturating; else the common cell of the three
    `CI_DECISION` intervals if all three are estimable and share logarithmic, linear or accelerating; else
    `"inconclusive"`. H3b's decision: supported iff logarithmic, refuted (class named) iff saturating, linear or
    accelerating, otherwise inconclusive;
  - `h3a0_decision(estimable0, lo, hi)` on q̃_0's `CI_DECISION` interval: supported iff estimable and
    `hi < LINEAR_SLOPE_RATIO`; refuted iff estimable and `lo > LINEAR_SLOPE_RATIO`; otherwise inconclusive;
  - `h3ad_decision(estimable, ci_decision, ci_union)`: refuted (accelerating at doubling i) iff some estimable ρ̃_i has
    its `CI_UNION` interval with `lo > LINEAR_DOUBLING_RATIO`; else supported iff all three are estimable with
    `CI_DECISION` `hi < LINEAR_DOUBLING_RATIO`; otherwise inconclusive;
  - γ_i = log2 ρ̃_i when ρ̃_i > 0;
  - estimation: the pooled R (median of the 18 per-region ratios Δ_{i+1}(r)/Δ_i(r), i in `DOUBLINGS`) and
    γ = log2 R when R > 0; per-region ratios for A and W, each reported only when its denominator step is resolved
    (A: a fall in F1; W: a rise in R2), and listed as `"denominator not resolved"` otherwise; W's class-sum ratios
    q̃_0 and ρ̃_i over the three walls, each estimable iff its denominator step is an R2 rise on at least one wall.
- `_h4(runs, draws)`, on per-pair arrays x (`f350`) and y (`f0`) of each M key:
  - TOST: `p_lo = ensemble.permutation_pvalue(x - DISPLAY_QUANTUM, y, "less")` and
    `p_hi = ensemble.permutation_pvalue(x + DISPLAY_QUANTUM, y, "greater")`;
  - margin family S: `ensemble.permutation_pvalue(x - DISPLAY_QUANTUM, y, "greater")` and
    `ensemble.permutation_pvalue(x + DISPLAY_QUANTUM, y, "less")` for every key, `ensemble.holm` over the 36 at 0.01;
  - detection: `report.family_test(runs["f350"], runs["f0"], M, SIGNIFICANCE, labels=("f350", "f0"))`;
  - size (reported only): per key the 99% and 95% bootstrap intervals of mean(`f350`) − mean(`f0`);
  - `classify_mean_key(p_lo, p_hi, supra_rejected, detected)`: `"sub-quantum (detected)"` / `"sub-quantum (not
    detected)"` iff `p_lo <= SIGNIFICANCE and p_hi <= SIGNIFICANCE`; `"supra-quantum"` iff `supra_rejected` (S rejects
    one of the key's two margin tests); both raises (it cannot happen, README H4 Key classes); otherwise
    `"unresolved"`;
  - `h4_decision(classes, powered)`: `"inconclusive (underpowered)"` if TOST or S is unpowered; else `"supported
    (tone-invariant)"` iff all are sub-quantum; `"refuted (tone-shifting)"` iff any is supra-quantum; otherwise
    `"inconclusive"`. The record lists `r2.mean.B`'s step Δ_i and d_i first, then the detected sub-quantum keys with
    abs diff, I_k and d, the unresolved keys with abs diff, I_k, d, p_lo and p_hi, and the largest |abs diff| with its
    rel diff and d;
  - estimation: each step and each dose against `f1400` on M.
- `_e1(runs, draws, h3)`:
  - gate G: `report.family_test(runs["f350"], runs["f0"], T, SIGNIFICANCE, labels=("f350", "f0"))`; responding keys
    = its `rejected_keys`, or none when that is None (unpowered);
  - the registered M7 input: n_k(f_k) per responding key, N_C(f_k) for C = A, W and T over the responding keys of C
    (None and the key list `"no resolved response"` when C has none), Δ_i(k) for every A and W key, Δ̃_i(A) and
    Δ̃_i(W), all with 95% and 99% intervals; the scale class (from H3b) and N_A(1/1400);
  - `fc_from_ratio(q, xtol=1e-12)`: x solving log((1 + 2x)/(1 + x)) / log(1 + x) = q for 0 < q < 1. The left side
    falls from 1 (x → 0) to 0 (x → ∞). Start the bracket at [1, 1], halve lo and double hi until the left side minus q
    changes sign, then bisect to `xtol` (the bisection's convergence parameter). f̂_c = (1/5600)/x. It returns None with
    the reason (`"q >= 1: no curvature at the first dose"`, `"q <= 0: reversal"`) otherwise. f̂_c of the class comes
    from q̃_0 (H3) when it is estimable, and its 95% and 99% intervals are the images of q̃_0's intervals (an end ≥ 1
    maps to `"inf"`, an end ≤ 0 to 0). Per A region, f̂_c(r) from Δ_1(r)/Δ_0(r) when step 0 is an F1 fall there;
  - the scale mapping (README E1): logarithmic → `"linear in log2(1 + f/f_c)"` with f̂_c; linear → `"linear in f"`;
    any other class, or f̂_c None → `"measured N_A table"`;
  - the P = 64 group: D_i, D0_k, S_C, `f_hi(D)` and `f_lo(D0)` as pure functions of the arrays, returning a grid
    value or the string `"at or above 1/350"` / `"below 1/5600"`; bootstrap counts of each value. A resample whose
    pooled sd is 0 for a key makes d undefined. It is dropped from the d-based statistics and counted.
- Decision records follow 006: each hypothesis has `decision` and its numbers. A configuration whose 16 renders are not
  16 distinct `sum` arrays marks the decisions that use it in `decisions_not_interpretable`.
- `--preflight`, `--out-dir`, `--pairs` (default 8), `--scale` (default 1). A smoke run must not write into the
  experiment directory, as in 006.

## Outputs

- `results.json` (`report.write_results_json`). Top-level keys: `experiment`, `smoke`, `scale`, `pairs`, `passes`,
  `side`, `oracle_sha256`, `configurations` (f and j as strings such as `"1/5600"`, options, seeds, max displacement in
  px), `parameters` (including `display_quantum`, `r_boundaries`, `ci_decision`, `ci_union` and `ci_report`),
  `regions`, `replicates`, `consistency_006`, `key_classes`, `summary` (`report.summary_table`), `steps`,
  `hypotheses` (H1-H4, with each family's p-values, Holm decisions, first threshold and `powered`), `decisions`,
  `decisions_not_interpretable`, `E1` (`gate`, `m7_input` with `fc`, `p64`), `bootstrap` (resamples, seed,
  percentiles), `figures`.
- Printed tables, one per README item: the T keys and estimation-only keys per dose (mean ± sd); the 30 H1 cells (Δ, d,
  `p_less`, `p_greater`, F1 and R1 decisions, class); the H2 overall tests and the 15 steps per wall (Δ, d, both p, R2
  and V2 decisions, class, and the overall class per wall); H3 (S_i, q̃_0 and ρ̃_1 … ρ̃_3 with estimability, 95%, 99%
  and `CI_UNION` intervals, γ_i, the cells, the H3a-0, H3a-d and H3b decisions, the pooled R and γ, per-region ratios
  or "denominator not resolved"); H4 (`r2.mean.B`'s steps first, then the 18 keys of `f350` vs `f0`: abs diff, rel
  diff, d, p_lo, p_hi, the two margin p and their S decisions, detection p and Holm, 99% and 95% intervals, class); E1
  (gate G, N with intervals, Δ and Δ̃ with intervals, the scale class, f̂_c with intervals and per region, N_A(1/1400),
  then the P = 64 group under its label). Every line of a smoke run is prefixed with `SMOKE_PREFIX`.
- Figures, drawn with numpy and `io.write_png`, with no text. Encodings are recorded in `results.json` `figures`:
  - `fig_dose_response.png`: two panels, about 300 × 200 px each. Left: A, one series per region. Right: W. x position 0
    is f0 and k + 0.5 is f_k (k = 1 … 5), so the gap after f0 marks that it is off the log₂ axis. Each point is mean ± sd
    with caps. Solid lines join f_1 … f_5, and a dashed line joins f0 to f_1. Each panel has its own y range: data range
    padded by 5% (the `Y_PAD` of 006). Region colours: r2 (31,119,180), r3 (255,127,14), r4 (44,160,44),
    r5 (214,39,40), r6 (148,103,189), r7 (140,86,75). W uses the colours of r4-r6.
  - `fig_crops.png`: pair 0's `report.ab8_of_pair`, cropped with no resampling. The README windows are `Fraction`s of
    the side, asserted to give integer pixels (at 400 px: rows 120-216 × columns 240-336, and rows 0-96 × columns
    304-400). 2 rows × 6 columns in dose order: 576 × 192 px at 400 px, under 0.35 MB raw.
  - Assert each file is at most `MAX_FIGURE_BYTES`.

## `power.py`

It reproduces every power number of the README, so they can be audited. It prints each table with the README value
beside the reproduced one and writes nothing. Simulations use JAX with `jax.random.PRNGKey(0)` (split per table).
Agreement follows README Method, Analysis, "Power numbers":
- deterministic numbers agree to the printed digits;
- a simulated number is an independent second estimate. `power.py` counts the m simulated rows it compares and prints
  z = z_{1−0.01/(2m)} (Bonferroni at 0.01 over the m rows). A proportion agrees iff |p_a − p_b| ≤
  z·√(p̄(1 − p̄)(1/n_a + 1/n_b)), with p̄ the pooled proportion. A median or half-width agrees iff the difference is at
  most z·√2·sd, where sd is the bootstrap-over-designs sd of `power.py`'s own estimate (designs resampled with
  replacement, `jax.random`, 1,000 resamples), printed beside it;
- a row outside its bound is reported in the card, and the README is not edited.

Shared pieces:
- the exact one-sided permutation p on the mean difference for 8 vs 8: the C(16, 8) = 12,870 splits enumerated once as
  an index matrix, counted with the tie rule of `ensemble.permutation_pvalue` (tolerance 16·eps·max|pooled|). A
  self-check compares 20 simulated designs against `ensemble.permutation_pvalue` exactly, for both alternatives and
  for shifted samples (x − 1, x + 1) as H4 uses them;
- a vectorized Holm (sort, compare with α/(m − rank), cumulative product);
- 006's sds read from `experiments/006-2026-10-09-jitter-units/results.json` `summary`: `row_j0_s400` for f = 0 and
  `row_s400` for every jittered dose; the 800 px and 200 px means from `row_j0_s800`, `row_s800_px`, `row_s800`,
  `row_s200` and `row_s200_px`; 006's f 1/1400 − f 0 shifts of M from `jitter_footprint` `comparisons` (`"400"`,
  `"800"`, `effect_summary`, minus `diff`);
- `GROWTH = (1.12, 1.41)`: the median and upper quartile of 006's 36 sd ratios across one doubling of f over T (README
  Common definitions, Seed-sd growth). `power.py` recomputes them from the `summary` (800 px `row_s800_px` →
  `row_s800`, 200 px `row_s200` → `row_s200_px`) and prints them with the quartiles (0.79, 1.41) and the M-key median
  (0.81).

Deterministic functions:
- `fc_fit()`: solves m = m₀ − b·log₂(1 + f/f_c) through the three 800 px `r4.structure_std` means (f = 0, 1/2800,
  1/1400 of the side) by bisection on x = (1/2800)/f_c in the slope-ratio equation
  log((1 + 2x)/(1 + x)) / log(1 + x) = (m(1/2800) − m(1/1400)) / (m(0) − m(1/2800)). The left side falls from 1
  (x → 0) to 0 (x → ∞): start the bracket at [1, 1], halve lo and double hi until the left side minus the ratio changes
  sign, then bisect to `xtol = 1e-12` (the bisection's convergence parameter). Prints the slope ratio (0.3352), f_c
  (1/14386), the grid's f/f_c, the five model steps and each divided by the mean of steps 2 and 3 (2.03, 0.86, 0.97,
  1.03, 1.07), q̃_0 (0.43), the doubling slope ratios ρ̃_i/2 (0.56, 0.53, 0.52), ρ̃_1 … ρ̃_3 (1.12, 1.07, 1.03), the
  pooled R (1.07), N_A = log₂(1 + f/f_c)/log₂(1 + f350/f_c) (0.34, 0.49, 0.65, 0.82, 1), and f̂_c from q̃_0 = 0.426
  through `fc_from_ratio`'s map with the grid's x = (1/5600)/f_c (1/14386). Also at f_c = 1/14000 (2.00, 0.86 for
  steps 0 and 1).
- `h1_table()`: the README's H1 table (falls, sds, d_r).
- `rho_delta_method()`: per region, the model steps scaled so that the mean of steps 2 and 3 equals the table's mean
  doubling fall; var(Δ_i) = (s_i² + s_{i+1}²)/8 and cov(Δ_i, Δ_{i+1}) = −s_{i+1}²/8; prints the sd of ρ_1 … ρ_3
  (r3 0.058-0.072, the others 0.140-0.212).
- `h2_predicted_d()`: the README H2 table's d per step in both brackets (first: `f1400`'s sd at the new doses; second:
  `f0`'s sd at the new doses, `f1400` its own), d = Δ/√((s_i² + s_{i+1}²)/2) (r4 3.4, 1.7, 3.1, 6.3, 6.3 and 3.0,
  1.3, 2.6, 5.4, 4.8 …). `power.py` reads no render cache: the per-pair `r5.slag.y` values in the README's H2 remark
  are not a power number, and `analyze.py`'s `summary` holds the sds.
- `h4_normal_limits()`: per M key, se = √((s_a² + s_b²)/8), s_p, 1 − (z_0.99 + z_0.95)·se (0.577 for `r2.mean.B`,
  0.742-0.958 for the others) and 1 + 4·s_p (1.85 for `r2.mean.B`, 1.09 for `r6.mean.B`); the four dose laws'
  `r2.mean.B` shifts (0.24-0.29, 0.37-0.45, 0.96-1.16, 3.8-4.6).

Simulations (designs per row in brackets):
- `per_test_power()` [4,000]: one test at the one-sided thresholds 0.01/30, 0.01/18, 0.01/15, 0.01/36, and two-sided
  0.01/18, for d = 1.0 … 5.0 in steps of 0.5 (README H4: 0.981 two-sided at d = 4; 0.816, 0.935, 0.985, 0.998, 1.000
  one-sided at 0.01/36 for d = 3 … 5).
- `h1_power()` [1,000]: F1 with all 30 cells at d = 2.0 … 4.0 (0.000, 0.447, 0.961, 0.999, 1.000); F1 at the
  predicted vector, defined exactly as per region r: d_step0 = 2.0·d_r, d_step1 = 0.86·d_r, d_step2 = d_step3 =
  d_step4 = d_r, with d_r from `h1_table()` (1.000; any R1 rejection 0.000); one family of 60 at d = 4 (0.758);
  R1 with one true rise among 29 null cells at d = 2, 3, 3.5, 4 (0.338, 0.876, 0.954, 0.995).
- `d_interval_attainability()` [1,000; 2,000 resamples]: the 99% percentile bootstrap interval of Cohen's d (pooled
  ddof-1 sd of the resampled pairs) for 8 vs 8 pairs at d = 0 and 0.5: fraction inside (−1, 1) (0.000) and median
  half-width (1.57).
- `bootstrap_undercoverage()` [20,000; 2,000 resamples]: 8 vs 8 normal pairs with a true shift of +1; the fraction of
  designs whose 99% percentile interval of the mean difference has its upper end below 1, for equal sds and for 006's
  `r2.mean.B` and `r6.mean.B` sds (0.016-0.018; README Common definitions, Bootstrap).
- `h2_power()` [2,000]: the six configurations of the three walls simulated with the README's predicted steps (the 800 px
  rise 0 → 1/2800 split 0.70 : 0.30 by the f_c model, step 2 from 800 px, steps 3 and 4 from the 200 px rise
  1/1400 → 1/700), in both sd brackets; R2 (18) and V2 (18, with the three net-hardening tests) as registered: the
  per-step rise probabilities of the README table, all (a) (1.000), all 15 rises (0.000; 0.053), any V2 rejection
  (0.000), P(supported); V2 with one true reversal among 17 null tests at d = 1.5, 2, 3, 3.5 (0.189, 0.472, 0.918,
  0.984).
- `h3_parametric_bootstrap()` [200, or 1,000 for the four boundary truths; 2,000 resamples]: 6 configurations × 6
  regions × 8 normal pairs, regions independent, pairs resampled within configurations (a resampled pair carries all
  its regions). Each truth is a vector of five steps in the f_c model's log₂ units (README H3 table). For region r,
  multiply every truth's steps by s_r = |mean of the region's two H1-table falls| / ((model step 2 + model step 3)/2);
  the configuration means are cumulative sums from a common origin; sds as in Shared pieces. F1 (Holm over 30) runs on
  every design and gates estimability. Prints per truth the true ratios, P(estimable), the median 99% half-widths of
  ρ̃_1 … ρ̃_3, the H3b class fractions, H3a-0 supported (and refuted), H3a-d supported / refuted, the median pooled R
  (1.074 under the f_c model, 0.080 under a stop at 1/1400) and, under the f_c model, the median 1/f̂_c and its median
  99% interval (14,245; [10,202, 20,469]).
- `h4_margin()` [1,000; 10,000 for the level rows]: per M key, normal pairs with `f0`'s sd and `f1400`'s sd (standing
  in for `f350`); TOST and the margin family S as registered; P(all 18 sub-quantum) and P(any supra-quantum) at no shift
  (1.000, 0.000); P(sub-quantum) per key at the shift 1 − (z_0.99 + z_0.95)·se (0.871 … 0.902); the level of one
  equivalence test at a true shift of exactly +1 for equal, `r2.mean.B` and `r6.mean.B` sds (0.0092-0.0094); the
  dose-law table (class-A shape, linear, f², on the 400 and 800 px shifts); and, with 2,000 resamples, the median 99%
  bootstrap half-width per key (0.024 … 0.245).
- `sd_growth()` [200 for H1/H3, 2,000 for H2, 1,000 for H4]: the sds of `f700` and `f350` are `f1400`'s times g and
  g² for g in `GROWTH`, the other doses as above. Prints, under the f_c model, F1 all 30 falls (1.000), any R1 (0.000),
  the H3 row of the README table (logarithmic 0.865 and 0.690); H2's first bracket: all (a) (1.000, 0.999), any V2
  (0.000), supported (1.000, 0.999), the r5 step 3 and 4 rise probabilities; H4: all sub-quantum at no shift (1.000,
  0.999) and under the class-A dose law on the 400 and 800 px shifts (0.996 / 0.966, 0.921 / 0.810), any supra (0.000).

Runtime: the planning simulations took about 6 minutes (first draft) and about 10 minutes (review 2, parts run in
parallel on 4 cores). `power.py` is not part of `make test`. Run it in the background with a log file and poll until
it exits: a foreground tool call is stopped after 10 minutes.

## `test_analyze.py` (fast, deterministic; collected by `make test`)

Loading: `analyze = report.load_jobs_module(Path(__file__).with_name("analyze.py"))`, as 005's `test_bindings.py`
loads its module with `importlib.util`. The repo runs pytest with `--import-mode=importlib` and the experiment
directory is not a package, so `from analyze import …` fails at collection. Hence:
- `analyze.py` has no import-time side effects other than loading 006's `analyze.py` and its own `jobs.py`: no
  `job_key`, no oracle sha256, no cache access at import;
- `analyze.py` does not combine `from __future__ import annotations` with `dataclasses`: a module loaded by
  `load_jobs_module` is not in `sys.modules`, and `@dataclass` then raises `AttributeError`.

The pure rule functions at their boundaries:
- `classify_cell` for (True, False), (False, True), (False, False), and that (True, True) raises;
- `h1_decision` and `h2_decision` for each outcome class, including both H2 refutations together, H2's inconclusive
  outcome (an overall test unresolved in both directions), and `every_step`;
- `ratio_cell` at intervals that touch each of `R_BOUNDARIES` exactly (inconclusive), and just inside each cell;
  `h3b_class` (the first saturating doubling wins; a non-estimable ratio blocks logarithmic, linear and accelerating);
  `h3a0_decision` at intervals that touch 1 exactly and when q̃_0 is not estimable; `h3ad_decision` at intervals that
  touch 2 exactly, with a non-estimable ratio, and refuted from a `CI_UNION` interval;
- `classify_mean_key` with p_lo or p_hi equal to `SIGNIFICANCE` exactly (sub-quantum) and at its float neighbour above
  (unresolved), supra-quantum, and that sub- and supra-quantum together raise; `h4_decision`;
- every decision's `"inconclusive (underpowered)"` branch, and `rejected_keys` None in H4's detection family and in E1
  (every key listed as `"no resolved response"`);
- `fc_from_ratio`: the round trip q = g(x) → x within `xtol` (the bisection's convergence parameter) at x = 0.5, 1 and
  5; None at q = 1, q > 1, q = 0 and q < 0;
- `f_hi` and `f_lo` when every step is above one sd, when the limit is inside the grid, and when k = 0;
- N's key selection: a non-responding key is excluded and listed.
Here "just inside" and "float neighbour" are `math.nextafter` of the boundary, an exact float neighbour, not a
tolerance. No test reads the render cache.

## Smoke run (code check only)

```
PAINTERLY_CACHE=<scratch>/008-smoke/cache PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python \
  experiments/008-2026-10-15-jitter-dose-response/analyze.py --pairs 2 --scale 4 --out-dir <scratch>/008-smoke/out
```

- It renders 24 jobs at 100 px, about 1.5 s each.
- It prints the smoke roundings (τ = 0.5 → 1 px, erosion 1 px; σ = 0.65 px).
- It skips `check_seed_reuse` and the 006 consistency check.
- With 2 pairs every family is underpowered (min one-sided p = 1/6, two-sided 1/3). Every decision reads
  `inconclusive (underpowered)` (each decision checks its families' `powered`, New code), and nothing may crash. The
  bootstrap intervals still run.
- The crop windows give rows 30-54 × columns 60-84 and rows 0-24 × columns 76-100.

## Acceptance for the card

- The preflight exits 0. The render command exits 0 with `remaining=0`.
- The analysis exits 0, with the design, replicate and 006 consistency checks passing.
- A second run reproduces `results.json` and both figures byte for byte.
- `power.py` exits 0 and its self-check against `ensemble.permutation_pvalue` passes. Its tables are reported in the card
  next to the README numbers.
- `ruff check` and `ruff format --check` pass on the new Python files. `pytest experiments/008-*` passes.
- Each figure is at most 1 MB.
- README gains `## Results` (tables from the printed output, numbers only) and `## Conclusion`, which starts with
  `DRAFT (Haiku) — pending Opus review.`. Hypotheses, rules and the Method stay unchanged. Any deviation goes in an
  "Amendments" subsection with its reason, as in 006.
