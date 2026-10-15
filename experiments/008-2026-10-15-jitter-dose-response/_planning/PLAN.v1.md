# Experiment 008: plan for the render and analysis card

The README (Background, Hypothesis, Method) is the specification. This plan says how to implement it.

## Files

- Create, under `experiments/008-2026-10-09-jitter-dose-response/`:
  - `README.md` and `jobs.py`, copied unchanged from the pre-registration;
  - `analyze.py`, `power.py`, `test_analyze.py`;
  - `results.json`, `fig_dose_response.png`, `fig_crops.png` (written by `analyze.py`).
- Modify: `experiments/README.md`, one index row with status `draft`.
- No change to `analysis/`, `third_party/`, `docs/` or the oracle. Never run `make oracle`.

## Order of work

1. Write `analyze.py --preflight` first and run it. It must exit 0 before any render. It checks that:
   - the sha256 of `oracle.oracle_binary()` (hashlib over the file) equals the README's
     `066bb5d4247c556ad5232bfc4fff75dc5f37089840b23f1ecc8fdd9cb518828a`;
   - each of the 32 jobs of `f0` and `f1400` has a `done` marker in
     `experiment.cache_root() / experiment.job_key(job)`.
   If it fails, stop and report. Do not render.
2. Render with the README's command, repeated until exit 0. 64 new renders take about 1,600 CPU-s, so one call is
   expected.
3. Smoke run, then the full analysis, then a second full run into a scratch `--out-dir`, checked byte for byte with `cmp`.

## Reuse (no copies)

- **006's measurement code.** 006 is final, so its `analyze.py` is frozen. Load it with
  `report.load_jobs_module(REPO_ROOT / "experiments/006-2026-10-09-jitter-units/analyze.py")` and call:
  - `side_params(side, 400, scale, notes)`, which gives σ, the erosion and τ, with smoke rounding;
  - `_masks(object_id, radius)` and its `FIXED_EROSION`;
  - `_measure_configuration(name, jobs, object_id, params, measured)`, which returns (scaled, fixed, profile,
    digests). Only `scaled` and `digests` are used. It checks passes = 64 and the object-id map;
  - `_keys(measured)` for the T and estimation-only key lists;
  - `_paint` and `_draw_line` for the figure.
  `measured` uses 006's rule: the regions that are non-empty under both the scaled erosion and `FIXED_EROSION` in every
  configuration. At 400 px both are 4 px. The consistency check below catches any change in these functions.
  (The alternative is to lift them into `painterly_analysis`. It is not done here, because the 007 and 009 cards could
  touch the same module at the same time.)
- `painterly_analysis.report`: `directional_pair_test` (H1, H2), `family_test` (H4), `summary_table`,
  `check_seed_reuse`, `largest_abs_rel_diff`, `largest_abs_cohen_d`, `ab8_of_pair`, `write_results_json`,
  `format_number`, `format_largest`.
- `painterly_analysis.ensemble`: `holm`, `effect_summary`, `min_attainable_pvalue`.
- `painterly_analysis.experiment`: `load`, `run_jobs` (smoke only), `job_key`, `cache_root`.
- `painterly_analysis.io.write_png`.
- `jobs.py`: `DESIGN`, `ORDER`, `REUSED`, `BLOCK`, `build_ensembles`, `image_plane_jitter`.

## New code in `analyze.py`

Constants: `SIGNIFICANCE = 0.01`, `BOOTSTRAP_RESAMPLES = 10_000`, `BOOTSTRAP_SEED = 0`,
`CI_DECISION = (0.5, 99.5)`, `CI_REPORT = (2.5, 97.5)`, `REFERENCE_SIDE = 400`, `ORACLE_SHA256`,
`MAX_FIGURE_BYTES = 1_000_000`, `SMOKE_PREFIX = "SMOKE (code check only): "`. Each gets a comment that cites the README.
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
- `_h1(runs)`:
  - 30 `directional_pair_test(runs[hi], runs[lo], key, SIGNIFICANCE)` calls;
  - `ensemble.holm` on the 30 `p_less` values at 0.01;
  - `classify_cell(d)` for non-rejected cells: `d <= -1` unresolved fall; `-1 < d < 1` flat; `d >= 1` rise;
  - `h1_decision(...)`.
- `_h2(runs)`: 3 overall tests (`f350` vs `f0`, `p_greater`) and 15 reversal tests (`p_less`) in one Holm family of 18.
  Then `h2_decision`.
- `_bootstrap_draws(pairs)`: one `np.random.default_rng(BOOTSTRAP_SEED)`. For each configuration in dose order (`ORDER`),
  `rng.integers(0, pairs, size=(BOOTSTRAP_RESAMPLES, pairs))`. The draws are made once and shared by H3 and E1.
  Resampled means and sample sds (ddof 1) come from the per-pair arrays (configuration × pair × key), vectorized.
- `_h3(...)`:
  - Q (H3a) and R (H3b) as the medians defined in the README, at the point estimate and per resample;
  - percentile intervals at `CI_DECISION` and `CI_REPORT` (`np.percentile`, default linear interpolation);
  - `classify_q(lo, hi)`: `hi < 1` supported; `lo > 1` refuted; otherwise inconclusive;
  - `classify_r(lo, hi)`: `hi < 1` saturating; `lo <= 1 <= hi` and `hi < 2` logarithmic; `1 < lo` and `hi < 2` power
    law; `lo <= 2 <= hi` and `lo > 1` linear; `lo > 2` accelerating; `lo <= 1` and `hi >= 2` inconclusive;
  - γ = log2 R when R > 0;
  - per-region ratios for A and W, W's Q and R (estimation), and the count of ratios whose denominator step has the sign
    opposite to the class's median step.
- `_h4(runs)`: `report.family_test(runs["f350"], runs["f0"], M, 0.01, labels=("f350", "f0"))`, plus the largest |abs diff|
  with its rel diff and d. Estimation: each step and each dose against `f1400` on M.
- `_e1(...)`: per class A, W and T:
  - D_i, D0_k, N_C(f_k) and S_C(f_k);
  - `f_hi(D)` and `f_lo(D0)` as pure functions of the arrays, returning a grid value or the string `"at or above 1/350"`
    / `"below 1/5600"`;
  - bootstrap: counts of each f_hi and f_lo value, and N intervals. A resample whose pooled sd is 0 for a key makes d
    undefined. It is dropped from the d-based statistics and counted;
  - the recommendation fields: soft range, scale class (from H3b), and N_A(1/1400).
- Decision records follow 006: each hypothesis has `decision` and its numbers. A configuration whose 16 renders are not
  16 distinct `sum` arrays marks the decisions that use it in `decisions_not_interpretable`.
- `--preflight`, `--out-dir`, `--pairs` (default 8), `--scale` (default 1). A smoke run must not write into the
  experiment directory, as in 006.

## Outputs

- `results.json` (`report.write_results_json`). Top-level keys: `experiment`, `smoke`, `scale`, `pairs`, `passes`,
  `side`, `oracle_sha256`, `configurations` (f and j as strings such as `"1/5600"`, options, seeds, max displacement in
  px), `parameters`, `regions`, `replicates`, `consistency_006`, `key_classes`, `summary` (`report.summary_table`),
  `steps`, `hypotheses` (H1-H4), `decisions`, `decisions_not_interpretable`, `E1`, `bootstrap` (resamples, seed,
  percentiles), `figures`.
- Printed tables, one per README item: the T keys and estimation-only keys per dose (mean ± sd); the 30 H1 cells (Δ, d,
  `p_less`, `p_greater`, Holm, class); the 18 H2 tests; H3 (Q, R, 95% and 99% intervals, γ, class, per-region ratios);
  H4 (the 18 keys of `f350` vs `f0`); E1 (D, D0, N with intervals, S, f_hi and f_lo with bootstrap counts, the
  recommendation). Every line of a smoke run is prefixed with `SMOKE_PREFIX`.
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

It reproduces the README's power numbers in JAX, so they can be audited. Two normal samples of 8, shifted by d,
`jax.random.PRNGKey(0)`. Exact one-sided permutation p on the mean difference: enumerate the C(16, 8) = 12,870 splits
once as a 0/1 matrix, and count with the same tie rule as `ensemble.permutation_pvalue`. Then Holm.
- Tables: H1 joint power (30 cells, d = 2.0 … 4.0, and the predicted vector, 1,000 designs); the version with 60
  tests at d = 4 (400 designs); the per-test power at one-sided thresholds 0.01/18 and 0.01/36 for d = 3, 3.5 and 4
  (4,000 designs).
- It prints the tables and writes nothing. The card reports them next to the README's numbers, which are Monte Carlo
  estimates (sd ≤ 0.016) and stay unchanged.

## `test_analyze.py` (fast, deterministic; collected by `make test`)

The pure rule functions at their boundaries:
- `classify_cell` at d = −1, −1 + ε, 1 − ε and 1;
- `classify_q` and `classify_r` for intervals that touch 1 and 2 exactly;
- `f_hi` and `f_lo` when every step is above one sd, when the limit is inside the grid, and when k = 0;
- `h1_decision` and `h2_decision` for each outcome class.
Here ε is `math.ulp` of the boundary, an exact float neighbour, not a tolerance. No test reads the render cache.

## Smoke run (code check only)

```
PAINTERLY_CACHE=<scratch>/cache PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python \
  experiments/008-2026-10-09-jitter-dose-response/analyze.py --pairs 2 --scale 4 --out-dir <scratch>/out
```

- It renders 24 jobs at 100 px, about 1.5 s each.
- It prints the smoke roundings (τ = 0.5 → 1 px, erosion 1 px; σ = 0.65 px).
- It skips `check_seed_reuse` and the 006 consistency check.
- With 2 pairs, every Holm family is underpowered (min one-sided p = 1/6). Decisions read `inconclusive (underpowered)`,
  and nothing may crash.
- The crop windows give rows 30-54 × columns 60-84 and rows 0-24 × columns 76-100.

## Acceptance for the card

- The preflight exits 0. The render command exits 0 with `remaining=0`.
- The analysis exits 0, with the design, replicate and 006 consistency checks passing.
- A second run reproduces `results.json` and both figures byte for byte.
- `ruff check` and `ruff format --check` pass on the new Python files. `pytest experiments/008-*` passes.
- Each figure is at most 1 MB.
- README gains `## Results` (tables from the printed output, numbers only) and `## Conclusion`, which starts with
  `DRAFT (Haiku) — pending Opus review.`. Hypotheses, rules and the Method stay unchanged. Any deviation goes in an
  "Amendments" subsection with its reason, as in 006.
