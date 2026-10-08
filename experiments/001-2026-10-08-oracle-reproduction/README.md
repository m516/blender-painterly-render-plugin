# Experiment 001: does the compiled oracle reproduce the reference, and what doesn't matter?

## Background

- `docs/plan.md` "What makes the look" (lines 22-51) records the research-phase findings: spiral sampling (u1 = u2),
  ghost spheres as the dominant light source, scan-line chaining that yields a converged texture, the path model, and
  the display mapping `min(int(sum)/s, 255)`. Thread count is listed as irrelevant. The plan's experiment table
  (line 177, X-oracle) assigns this experiment the job of re-confirming these claims with the compiled oracle.
- This experiment builds on:
  - the oracle `src/app/smallpaint_oracle.cpp` (T1.1), whose chains, Halton generator and ghost policy are SPEC §2, §3
    and §5;
  - the metrics and statistics of `analysis/painterly_analysis/{metrics,ensemble}.py` (T1.2, T1.5);
  - the contract tests and the statistical reference test (T1.3). That test uses a provisional `ENSEMBLE_PASSES = 32`
    which this experiment is meant to estimate;
  - the cached harness `painterly_analysis.experiment` (T1.4).
- SPEC §2 gives the Halton period of 2^23 and the `--halton exact` option. SPEC §3 defines the `image`, `omp-restart:T`
  and `pixel-major` chains. SPEC §7 and §9 give the display mapping and the GUI reference scene.

## Hypothesis

All ensembles are 8 pairs of half renders, size 400, with the GUI scene and `ghost=all` (the oracle defaults). The
configurations are listed in Method. The significance level is alpha = 0.01 throughout. A "pair" is two independent
half renders (seeds 2k and 2k+1 of one configuration). Metric keys are those of `metrics.measure`.

- **H1, reference match.**
  - Derived from: a research-phase Python port matched the reference region means, (96.6, 100.0, 70.9) against
    (97.0, 100.2, 71.0) (`docs/plan.md`, "What makes the look").
  - Claim: for every measurable diffuse region r (ids 2-7; see deviation D1) and every channel c, the reference's region
    mean lies inside the prediction interval of the `img256` ensemble.
  - Samples: the 16 single-render region means of `img256` (the a8 and b8 half renders of the 8 pairs, each
    `smallpaint_display(sum, 256)`), per region and channel.
  - Interval: `ensemble.prediction_interval(samples, alpha / m)`, which is the 1 - alpha/m level (Bonferroni). Here
    m = 18 = 6 regions x 3 channels.
  - Decision: supported iff all 18 reference region means lie inside their intervals. Refuted otherwise.
- **H2, threads are irrelevant.**
  - Derived from: research found the single-stream and OpenMP builds statistically identical (`docs/plan.md`, item 3).
  - Claim: `img64` versus `omp4_64`, and `img64` versus `omp16_64`, are indistinguishable on every metric key.
  - Test: `ensemble.compare_ensembles` for each comparison: two-sided permutation test per key, Holm across the keys at
    alpha = 0.01.
  - Decision: supported iff no key is rejected in either comparison. Refuted iff some key is rejected in either.
- **H3, generator wrap is irrelevant.**
  - Derived from: the incremental Halton generator is periodic mod 2^23 with error at most 7.5e-8 (SPEC §2).
  - Claim: `img64` (`halton=incremental`) and `exact64` (`halton=exact`) are indistinguishable on every metric key.
  - Test and decision: as in H2, one comparison.
- **H4, converged texture.**
  - Derived from: research found the reference to be a converged, deterministic pattern. The M1 review measured the
    seed-independent back-wall structure std at 50 passes as 5.76, against the reference's total high-pass std of 5.78.
  - Claim: `all.pattern_corr` increases with P over P in {16, 32, 64, 128, 256, 512}.
  - Test: for each adjacent step (P_lo, P_hi), `p_up = permutation_pvalue(pattern_corr at P_hi, at P_lo, "greater")`.
    Holm across the five steps at alpha = 0.01. Decision: supported iff all five are rejected. Refuted iff Holm on the
    five `"less"` p-values rejects any step. Otherwise inconclusive.
  - Effective pass count P_ref, with the fit defined in Method. Its point estimate and its bootstrap 95% interval are
    reported. No decision threshold is attached to P_ref.
- **H5, loop order matters.**
  - Derived from: research found pass-major correlates 0.51-0.63 with the reference and pixel-major 0.06-0.20.
  - Claim: `pm64` has a significantly lower `all.pattern_corr` than `img64`.
  - Test: `ensemble.permutation_pvalue(pm64, img64, "less")` at alpha = 0.01 (the `separated` test).
  - Decision: supported iff p <= 0.01. Refuted iff `permutation_pvalue(pm64, img64, "greater")` <= 0.01. Otherwise
    inconclusive.

## Method

### Configurations

Each configuration is `ensemble_jobs(name, 8, base_seed=16*block, size=400, **options)` in `jobs.py`.
The scene (`gui`) and ghost (`all`) are the oracle defaults and are not passed, so the cache keys match the README
example of `experiments/README.md`.

| name | oracle options (besides size 400) | P | seeds (block) | used by |
|---|---|---|---|---|
| img16 | chain=image | 16 | 16-31 (1) | H4 |
| img32 | chain=image | 32 | 32-47 (2) | H4 |
| img64 | chain=image | 64 | 0-15 (0) | H2, H3, H4, H5, positive control |
| img128 | chain=image | 128 | 48-63 (3) | H4 |
| img256 | chain=image | 256 | 64-79 (4) | H1, H4 |
| img512 | chain=image | 512 | 80-95 (5) | H4, figures |
| omp4_64 | chain=omp-restart:4 | 64 | 96-111 (6) | H2 |
| omp16_64 | chain=omp-restart:16 | 64 | 112-127 (7) | H2 |
| exact64 | chain=image, halton=exact | 64 | 128-143 (8) | H3 |
| pm64 | chain=pixel-major | 64 | 144-159 (9) | H5 |

Total: 160 renders.

### Commands

1. Render until the harness exits 0 (exit 3 means jobs remain):
   `.venv/bin/python -m painterly_analysis.experiment run experiments/001-2026-10-08-oracle-reproduction/jobs.py --budget 540`
2. Analysis, after all renders exist: `.venv/bin/python experiments/001-2026-10-08-oracle-reproduction/analyze.py`
   (it writes `results.json` and the `fig_*.png` previews and prints the tables).

### Analysis

- Metrics: `experiment.measure_ensemble` per configuration, which calls `metrics.measure` on each pair against
  `tests/data/reference/smallpaint_painterly.ppm`. The object-id map is taken from the first render of each
  configuration. The analysis asserts that it is identical across configurations.
- H1: region masks from `metrics.region_masks(object_id, 4)` (erosion radius 4 = highpass 9 // 2, as in `measure`).
  Region means use `metrics.region_mean_rgb`. The reference is `ref8`.
- H4 convergence fit:
  - For each P and each of the 16 single renders (`smallpaint_display(sum, P)`), take the population variance (ddof 0)
    of `metrics.highpass(metrics.luminance(·), 9)` over the eroded region-4 mask. Average over the 16 renders to get
    v(P).
  - Ordinary least squares of v(P) on x = 1/P over the six P values gives the intercept σs² and the slope σn².
  - `var_ref` is the same population variance for the reference.
  - Solve v(P_ref) = var_ref, so P_ref = σn² / (var_ref - σs²). It is defined when var_ref > σs² and σn² > 0.
  - Bootstrap: 1000 resamples of the 8 pairs with replacement, indices `jax.random.randint(jax.random.PRNGKey(0),
    (1000, 8), 0, 8)`. Each resample refits and recomputes P_ref. The 95% interval is the 2.5 and 97.5 percentiles
    (`np.percentile`, linear) over the defined resamples. The number of undefined resamples is reported.
- Deliverable (decided before the renders): the recommended `ENSEMBLE_PASSES` for `tests/oracle/test_oracle_reference.py`
  and the default `passes` of the Blender "Smallpaint Reference" preset are both `round(P_ref)`. The reason is that a single
  render with P passes has the variance v(P) that `P_ref` is defined by. If the interval leaves [16, 512], the
  recommendation is marked as an extrapolation.
- The figures use `io.write_png`:
  - `fig_reference.png`: the reference.
  - `fig_image_P512.png`: `ab8` of pair 0 of `img512`, where `ab8 = smallpaint_display(sum_a + sum_b, 1024)`.
  - `fig_pixel_major_P64.png`: `ab8` of pair 0 of `pm64`.
  - `fig_absdiff_P512.png`: `clip(4 * |ab8 - ref8|, 0, 255)` for pair 0 of `img512`.
- Effect size per metric key: (mean_a - mean_b) / pooled sd, with pooled sd = sqrt((sd_a^2 + sd_b^2) / 2), ddof 1.
- `results.json` holds every number in Results. It is written with sorted keys, and the analysis is deterministic.

### Deviations from the card, decided before analysis

- **D1, region 8 is absent.** In the 2-pass probe render, object id 8 (front plane) has no pixels in any eroded mask. The
  H1 claim is therefore over the six measurable diffuse regions, 2-7, and m = 18 region-channel pairs, not 21. The
  analysis asserts that region 8 has no pixels in any configuration, and it reports this.
- **D2, seeds.** The card does not fix seeds. Each configuration has its own disjoint seed block, so samples are
  independent and the passes of different P do not nest. This is the only way to keep the H3 and H4 tests free of
  seed pairing. The positive control keeps seeds 0-15, so the cache matches T1.7.

### Amendments (T1.10)

The first attempt of `analyze.py` stopped at line 184 (`point_defined[0]` on a 0-d array) before it printed or wrote
anything, so no number from it exists. The changes below were made before the analysis was completed. Background,
Hypothesis, configurations, seeds and decision rules stand as written, except for the points listed here.

1. **Undefined point estimate is reported, not raised.** `P_ref = 1/q` with `q = (var_ref - sigma_s^2) / sigma_n^2`.
   When `q <= 0`, `P_ref = inf` and `P_ref_finite` is false. The line-184 check now only prints a note. The
   bootstrap keeps all 1000 resamples and takes percentiles of `q`, which are then mapped to `P`. A non-positive
   `q` bound maps to inf, so the interval is `[1/q_hi, 1/q_lo]` with inf for any non-positive bound. The pre-registered
   rule took percentiles over the defined resamples only. Here 3 of 1000 resamples have `q <= 0`.
2. **Comparison family.** Every `compare_ensembles` call (H2 and H3) uses `metrics.DIFFUSE_KEY_FAMILY`: the 46 keys
   of diffuse regions 2-7 and of `all.*`. The 21 keys of regions 0, 1 and 9 are dropped, because those ids are not in
   `DIFFUSE_REGION_IDS` (SPEC §9: 9 is the light). With all 67 keys the smallest attainable p,
   2/C(16,8) = 1.554e-4, exceeds the first Holm threshold 0.01/67 = 1.49e-4. The power guard in
   `compare_ensembles` would then refuse the comparison, so no key could be rejected.
3. **Effect sizes and NaN.** These come from `ensemble.effect_summary`. Cohen's d uses the pooled sd
   `sqrt(((n_a - 1) sd_a^2 + (n_b - 1) sd_b^2) / (n_a + n_b - 2))`. With 8 vs 8 pairs this equals the pre-registered
   `sqrt((sd_a^2 + sd_b^2) / 2)`. Undefined values are `None` and never NaN. `analyze.py` also refuses to write a
   `results.json` that contains `NaN`. In the JSON, infinity is written as the string `"inf"`.
4. **Sensitivity fits and two added analyses** (T1.10 items 4 and 5). The sensitivity fits are WLS with weights
   1/var of the per-P mean, and OLS over P >= 32. The added analyses are the ratio `sigma_n^2 / (sigma_s^2 P)` for
   each P, and the noise-corrected structure correlation for P >= 64. The correction is defined under Results. It uses
   `r4.pattern_corr`, the back wall that the variance fit uses, and not `all.pattern_corr`. None of these sets a
   decision.
5. **Statistics library** (`analysis/painterly_analysis/ensemble.py`, T1.10). The tie tolerance is
   `(n + m) eps max|pooled|` for permutation tests and `n eps max|x|` for sign flips. It replaces
   `64 eps max|statistic|`. The old tolerance scaled with the statistic. On data with a large offset it could drop a
   mirror split, which halves an extreme two-sided p-value. The test `test_two_sided_exact_counts_mirror_split`
   covers that case. The power guard, `Comparison.min_attainable_p`, `effect_summary` and `DIFFUSE_KEY_FAMILY` are the
   other library changes.

## Results

Source: `results.json`, written by `analyze.py` from the cache (160 renders). The run takes about 35 s,
and a second run reproduces `results.json` and the four `fig_*.png` byte for byte. There are no NaN values.
Metric keys: 67 in all, 46 in the diffuse family
(regions 2-7 and `all.*`). Object ids present: 0, 1, 2, 3, 4, 5, 6, 7, 9. Region 8 has no pixels after erosion (D1). The light (id 9) and ids 0 and 1 are outside the family.

### H1, reference match

m = 18 region-channel pairs. Each interval is `prediction_interval` of the 16 single renders of `img256` at level 1 - alpha/m = 1 - 0.000556. Inside: 18/18.

| region | ch | mean | sd | lo | hi | reference | inside |
|---|---|---|---|---|---|---|---|
| 2 | R | 56.047 | 0.048 | 55.831 | 56.264 | 56.033 | True |
| 2 | G | 49.705 | 0.044 | 49.505 | 49.904 | 49.677 | True |
| 2 | B | 139.607 | 0.145 | 138.954 | 140.260 | 139.801 | True |
| 3 | R | 78.517 | 0.031 | 78.377 | 78.658 | 78.526 | True |
| 3 | G | 84.828 | 0.028 | 84.700 | 84.956 | 84.837 | True |
| 3 | B | 80.423 | 0.029 | 80.291 | 80.555 | 80.425 | True |
| 4 | R | 137.372 | 0.037 | 137.205 | 137.539 | 137.379 | True |
| 4 | G | 148.695 | 0.024 | 148.588 | 148.802 | 148.702 | True |
| 4 | B | 122.415 | 0.024 | 122.306 | 122.524 | 122.407 | True |
| 5 | R | 151.357 | 0.082 | 150.987 | 151.728 | 151.361 | True |
| 5 | G | 28.215 | 0.013 | 28.156 | 28.274 | 28.217 | True |
| 5 | B | 27.776 | 0.014 | 27.713 | 27.839 | 27.784 | True |
| 6 | R | 28.348 | 0.013 | 28.289 | 28.408 | 28.347 | True |
| 6 | G | 146.526 | 0.066 | 146.229 | 146.822 | 146.536 | True |
| 6 | B | 27.436 | 0.015 | 27.371 | 27.502 | 27.436 | True |
| 7 | R | 91.423 | 0.037 | 91.255 | 91.590 | 91.407 | True |
| 7 | G | 106.736 | 0.035 | 106.579 | 106.894 | 106.737 | True |
| 7 | B | 75.196 | 0.036 | 75.036 | 75.357 | 75.188 | True |

### H2 and H3, key comparisons

Two-sided permutation test per key (8 vs 8 pairs), Holm at alpha = 0.01 over the 46 family keys. The smallest attainable p is 2/C(16,8) = 0.0001554, which is above the first Holm threshold for 67 keys and below it for 46.

| comparison | rejected keys | smallest p | largest abs Cohen d (key) | decision |
|---|---|---|---|---|
| img64 vs omp4_64 | 4 | 0.0001554 | 9.089 (r7.structure_std) | refuted |
| img64 vs omp16_64 | 9 | 0.0001554 | 24.635 (r7.structure_std) | refuted |
| img64 vs exact64 | 0 | 0.03201 | 1.184 (r2.mean.G) | supported |

Rejected keys (mean of img64 and of the other ensemble, Cohen d):

| comparison | key | mean img64 | mean other | d | p |
|---|---|---|---|---|---|
| omp4_64 | all.pattern_corr | 0.5889 | 0.5809 | 4.897 | 0.0001554 |
| omp4_64 | r5.structure_std | 3.5421 | 3.7423 | -2.979 | 0.0001554 |
| omp4_64 | r7.pattern_corr | 0.4582 | 0.4333 | 4.244 | 0.0001554 |
| omp4_64 | r7.structure_std | 5.5181 | 6.5000 | -9.089 | 0.0001554 |
| omp16_64 | all.clip_fraction | 0.0043 | 0.0050 | -6.205 | 0.0001554 |
| omp16_64 | all.pattern_corr | 0.5889 | 0.5760 | 8.528 | 0.0001554 |
| omp16_64 | r3.structure_std | 7.0387 | 7.2667 | -2.596 | 0.0001554 |
| omp16_64 | r5.lag1.x | 0.1355 | 0.1174 | 2.763 | 0.0001554 |
| omp16_64 | r5.pattern_corr | 0.5243 | 0.5122 | 2.801 | 0.0001554 |
| omp16_64 | r5.structure_std | 3.5421 | 4.1996 | -11.962 | 0.0001554 |
| omp16_64 | r6.pattern_corr | 0.5824 | 0.5651 | 5.043 | 0.0001554 |
| omp16_64 | r6.structure_std | 7.2339 | 7.9216 | -6.877 | 0.0001554 |
| omp16_64 | r7.structure_std | 5.5181 | 8.3597 | -24.635 | 0.0001554 |

### H4, convergence in passes

`all.pattern_corr` by P (mean +- sd over the 8 pairs of each configuration):

| P | mean | sd |
|---|---|---|
| 16 | 0.350116 | 0.002066 |
| 32 | 0.463643 | 0.001434 |
| 64 | 0.588908 | 0.001582 |
| 128 | 0.708128 | 0.001896 |
| 256 | 0.802712 | 0.000760 |
| 512 | 0.867623 | 0.000379 |

Adjacent steps, one-sided permutation tests (exact, 8 vs 8: smallest one-sided p = 1/C(16,8) = 7.77e-05). Holm at 0.01 rejects every 'greater' step: decision **supported**.

| step | p greater | p less | Holm rejects greater |
|---|---|---|---|
| 16->32 | 7.77e-05 | 1 | True |
| 32->64 | 7.77e-05 | 1 | True |
| 64->128 | 7.77e-05 | 1 | True |
| 128->256 | 7.77e-05 | 1 | True |
| 256->512 | 7.77e-05 | 1 | True |

Back-wall fit (region 4, erosion 4). v(P) is the mean over the 16 single renders of the population variance of the high-pass luminance.

| P | v(P) | noise/structure ratio sigma_n^2/(sigma_s^2 P) | structure corr. r_obs (r4) | rel. render | rel. reference | rho corrected |
|---|---|---|---|---|---|---|
| 16 | 381.410 | 10.5338 | - | - | - | - |
| 32 | 207.180 | 5.2669 | - | - | - | - |
| 64 | 120.311 | 2.6334 | 0.645869 | 0.4316 | 0.9891 | 0.988483 |
| 128 | 76.671 | 1.3167 | 0.764716 | 0.6030 | 0.9891 | 0.990210 |
| 256 | 54.885 | 0.6584 | 0.855482 | 0.7523 | 0.9891 | 0.991723 |
| 512 | 43.776 | 0.3292 | 0.914876 | 0.8587 | 0.9891 | 0.992742 |

var_ref = 33.4354, sigma_s^2 = 33.0698, sigma_n^2 = 5573.60.

| fit | P_ref | 95% interval | sigma_s^2 | sigma_n^2 |
|---|---|---|---|---|
| primary, OLS on all six P, 8 pairs | 15244 | [8865, 69266] (bootstrap, 1000 resamples) | 33.0698 | 5573.60 |
| sensitivity, WLS on six P (weights 1/var of per-P mean) | 10912 | none | 32.9237 | 5584.04 |
| sensitivity, OLS on P >= 32 | 14882 | none | 33.0608 | 5574.51 |

Bootstrap resamples with q <= 0 (P_ref = inf): 3 of 1000. Resamples with sigma_n^2 <= 0: 0. Recommended passes round(P_ref) = 15244. Interval outside the tested range [16, 512]: True, so the recommendation is an extrapolation.

### H5, loop order

| configuration | mean all.pattern_corr | p less | p greater | decision |
|---|---|---|---|---|
| pm64 vs img64 | 0.294717 vs 0.588908 | 7.77e-05 | 1 | supported |

### Figures

- `fig_absdiff_P512.png`: 187314 bytes
- `fig_image_P512.png`: 388894 bytes
- `fig_pixel_major_P64.png`: 401642 bytes
- `fig_reference.png`: 385551 bytes

## Conclusion

DRAFT (Haiku) — pending Opus review.

- H1 (reference match): supported. 18/18 reference region means lie inside their 1 - 0.01/18 prediction intervals of the 16 `img256` single renders.
- H2 (threads are irrelevant): refuted. img64 vs omp4_64 rejects 4 of 46 keys (smallest p 1.55e-4, largest |d| 9.09 on `r7.structure_std`). img64 vs omp16_64 rejects 9 of 46 keys (largest |d| 24.6 on `r7.structure_std`).
- H3 (generator wrap is irrelevant): supported. img64 vs exact64 rejects 0 of 46 keys; the smallest p is 0.0320, above the first Holm threshold 0.01/46 = 2.17e-4.
- H4 (converged texture): supported. All five adjacent steps of `all.pattern_corr` increase (one-sided p = 7.77e-5 each, Holm at 0.01 rejects all five, no step is rejected in the "less" direction). P_ref = 15244 passes (95% bootstrap [8865, 69266]; WLS 10912; OLS over P >= 32 14882). This is outside the tested range [16, 512], so the recommended passes of 15244 is an extrapolation.
- H5 (loop order matters): supported. pm64 has a lower `all.pattern_corr` than img64 (0.2947 vs 0.5889), with p_less = 7.77e-5 <= 0.01.

Notes for Opus review:
- H4: var_ref - sigma_s^2 = 0.37 (sigma_s^2 = 33.07, var_ref = 33.44), so P_ref rests on a small margin over the variance floor. Three bootstrap resamples have q <= 0.
- H2: omp-restart chains change the chain as well as the thread count. No configuration in this experiment isolates the thread count alone, so the refutation concerns the omp-restart chains.
