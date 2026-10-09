# Experiment 002: which smallpaint ingredients are necessary for the look?

## Background

- `docs/plan.md`, "What makes the look", items 1-5, gives the research-phase findings this experiment tests:
  - Item 1 (spiral sampling): both Halton dimensions are base 2 and advance in lockstep, so u1 = u2 and the bounce
    direction is a 1-D spiral.
  - Item 2 (ghost spheres): they are the dominant light source. Normalizing d drops the back wall from 193 to 13 grey
    levels. The 193 is the `ghost=lights` value (T1.7 card), not the full ghost policy.
  - Item 3 (scan-line chaining): it gives a converged texture. Pattern correlation with the reference is 0.63 for the
    row chain, 0.55 for 16-pixel lanes and 0.11 for a per-path random start, which "breaks the look".
  - Item 4 (path model): no Russian roulette, no next-event estimation. The light is a black diffuse surface, so paths
    keep bouncing after an emitter hit and keep consuming K.
  - The plan's experiment table lists this experiment as X-ablation (M1): each ingredient is necessary.
- `experiments/001-2026-10-08-oracle-reproduction/` established with the compiled oracle that the reference is
  reproduced (its H1) and that pixel-major loop order lowers the pattern correlation (its H5). Its `img64` ensemble
  (block 0, seeds 0-15, `chain=image`, P = 64) is this experiment's positive control. Its H4 table gives
  `all.pattern_corr` = 0.588908 (sd 0.001582) at P = 64. Recomputed from that cache, the back-wall (region 4)
  luminance of `img64` is 144.38 (sd 0.04 over 8 pairs). The card's value of 144.4 agrees.
- The ingredients are oracle options, defined in `docs/spec.md`:
  - `ghost` (SPEC §5): `all`, `lights` or `none`;
  - `alpha` (SPEC §4): the power `d <- d * |d|^(-alpha)` applied to each diffuse bounce direction;
  - `u2` (SPEC §4): `same`, `independent` or `base3`;
  - `chain` (SPEC §3): `image` or `lane:L`, where L is the lane length;
  - `continue_after_emitter` (SPEC §6).
- This experiment is the first ablation: every variant changes exactly one option of the positive control.

## Hypothesis

### Common definitions

- A configuration is an ensemble of 8 pairs. A pair is two independent half renders (seeds 2k and 2k+1 of one
  configuration), each with P = 64 passes at 400 px. Metric keys are those of `metrics.measure`, over the diffuse
  regions only (deviation D5).
- Back-wall luminance `r4.luma` is the Rec.709 luminance of the region-4 mean RGB, `0.2126 R + 0.7152 G + 0.0722 B`,
  over the eroded back-plane mask. It is a derived key, added in `analyze.py`.
- The significance level is alpha = 0.01 (written SIGNIFICANCE in the code). It is not the oracle option `alpha`.
  Every p-value is an exact permutation p-value (`ensemble.permutation_pvalue`). Where several tests share a decision,
  Holm (`ensemble.holm`) is applied at alpha = 0.01.
- Key family: `metrics.diffuse_key_family(keys)`, which has 46 keys for the GUI scene. Every `compare_ensembles` call
  uses it, never all keys.
- Power: the smallest attainable p-value of 8 vs 8 pairs is 2 / C(16, 8) = 1.55e-4 two-sided, and 1 / C(16, 8) =
  7.77e-5 one-sided. A family comparison is powered only if that minimum is at most alpha / 46 = 2.17e-4, which holds.
  An underpowered comparison has no decision of "indistinguishable" or "refuted". It is reported as underpowered.
- Estimation over verdicts: for every variant, the effect size against the positive control is reported for each key:
  `ensemble.effect_summary` (mean +- sd, relative difference, Cohen's d = (mean_v - mean_pos) / pooled sd). Any
  "indistinguishable" verdict is reported with `min_attainable_p` and the largest observed |relative difference| and
  the largest |Cohen's d|.

### H1: the back wall needs the ghost spheres and the unnormalized bounce

- Derived from: plan item 2. `ghost=none` replaces every ghost test by the exact quadratic (SPEC §5). The light is a
  sphere, so it no longer ghosts. `alpha=1` is the normalization d / |d|, which the plan reports drops the back wall
  from 193 to 13. Card pilot (2 pairs): ghost_none 12.9, alpha_1 5.5, against 144.4 for the positive control.
- Claim: the back-wall luminance `r4.luma` of `ghost_none` and of `alpha_1` is far below that of the positive control.
- Test: for each of the two variants, a one-sided permutation test (less) of `r4.luma` against the positive control.
  Each test is equivalent to `ensemble.separated(variant, positive, "less", alpha = 0.01)`. The two tests are not
  corrected for each other (deviation D3).
- Decision: supported iff both variants are separated "less". Refuted iff either is separated "greater". Otherwise
  inconclusive.

### H2: the spiral and the chaining are necessary for the texture

- Derived from: plan items 1 and 3. `u2=independent` replaces the second Halton coordinate by a stateless draw
  (SPEC §4), so the spiral breaks. `u2=base3` advances the second coordinate in base 3, so the two coordinates no longer
  advance in lockstep. `chain=lane:1` restarts the counter K for every pixel's path (SPEC §3), so the scan-line chain
  breaks. The research pattern correlation of these three is about 0 to 0.11, against 0.47 to 0.63 for the look.
  The positive control measures 0.589 in experiment 001.
- Claim: each of the three variants lowers `all.pattern_corr` relative to the positive control.
- Test: for each variant, a one-sided permutation test (less) of `all.pattern_corr` against the positive control, with
  Holm across the three at alpha = 0.01.
- Decision: supported iff all three are rejected "less". Refuted iff Holm over the three "greater" p-values rejects any.
  Otherwise inconclusive.

### H3: alpha is a continuous control of the back wall

- Derived from: SPEC §4, `d <- d * |d|^(-alpha)`. The factor rescales d without changing its direction, so alpha changes
  each diffuse bounce's cost (cost = d . N is multiplied by the same factor) and the ghost test, which depends on |d|
  (SPEC §5). Since |N| = |s| = 1, |d|^2 = 2 + 2 N . s, so |d| > 1 whenever N . s > -1/2, and the factor is below 1 there.
  This gives the expected direction of the back wall as alpha rises, not its magnitude.
- Claim: `r4.luma` decreases monotonically over alpha in {0, 0.25, 0.5, 1}.
- Test: for each adjacent step (0 -> 0.25, 0.25 -> 0.5, 0.5 -> 1), a one-sided permutation test (less) of `r4.luma`
  of the higher alpha against the lower, with Holm across the three at alpha = 0.01.
- Decision: supported iff all three are rejected "less". Refuted iff Holm over the three "greater" p-values rejects
  any. Otherwise inconclusive.

### H4: continuing after an emitter hit changes both the region means and the texture

- Derived from: SPEC §6 and plan item 4. The light is a black diffuse surface. Continuing after its emission consumes
  K draws with zero throughput. That changes the K stride between neighbouring pixels in the chain (SPEC §3), which sets
  both the deterministic pattern and the region means. Card pilot: K draws per pixel per pass about 16.3 when continuing
  and about 5.1 when stopping.
- Claim: `continue_after_emitter=False` (`stop_at_emitter`) changes both the region means and the texture.
- Test: `ensemble.compare_ensembles(stop_at_emitter, positive, diffuse_key_family(keys), alpha = 0.01)`, Holm over the
  46 keys. The rejected keys are sorted into region-mean keys (containing `.mean.`) and texture keys (containing
  `structure_std`, `pattern_corr`, `lag1` or `spectral_slope`).
- Decision: supported iff at least one region-mean key and at least one texture key are rejected. Refuted iff the
  comparison is powered and no key is rejected. Otherwise inconclusive. The K draws per pixel per pass of both
  configurations are reported: `mean over pixels of k_consumed / P`, mean +- sd over the 16 renders of each configuration.

### H5: lights-only ghosting keeps most of the look

- Derived from: plan item 2 and the card. `ghost=lights` is what Blender can do by default: only emissive spheres ghost
  (SPEC §5). The research port gives a back-wall value of 193 under `ghost=lights` (T1.7 card), against 144.4 under the
  full policy (experiment 001).
- Claim: lights-only ghosting reproduces most of the look. The size of the gap is the deliverable, since it is the
  parity target for Blender scenes.
- Test: `ensemble.compare_ensembles(ghost_lights, positive, diffuse_key_family(keys), alpha = 0.01)`. Also the ratio of
  the ensemble means `ghost_lights / positive` for `all.pattern_corr` and for each region-mean key of the family.
- Verdict: "distinguishable" if at least one family key is rejected. "indistinguishable" if none is rejected and the
  comparison is powered. "underpowered" otherwise. Distinguishable is the expected result. The card gives no numeric
  threshold for "most", so the verdict covers only the comparison. How much of the look remains is read from the
  ratios and the effect sizes, and the Conclusion will report them without a threshold.

## Method

Pilots seen before pre-registration: 8 pairs, 128 px, all ten configurations, scratch cache.

### Configurations

Every configuration uses `size=400`, `passes=64` and 8 pairs. No configuration passes `scene`, because the oracle
default is `scene=gui`. `ghost` is passed only by the two ghost variants, where it differs from the default `ghost=all`.
The positive control's option set is exactly that of experiment 001's `img64`, so its 16 renders come from the cache.

| name | oracle options (besides size 400, passes 64) | seed block | seeds | used by |
|---|---|---|---|---|
| positive | `chain=image` | 0 (001's img64) | 0-15 | all (cache from 001) |
| ghost_none | `chain=image, ghost=none` | 10 | 160-175 | H1 |
| ghost_lights | `chain=image, ghost=lights` | 11 | 176-191 | H5 |
| alpha_025 | `chain=image, alpha=0.25` | 12 | 192-207 | H3 |
| alpha_05 | `chain=image, alpha=0.5` | 13 | 208-223 | H3 |
| alpha_1 | `chain=image, alpha=1.0` | 14 | 224-239 | H1, H3 |
| u2_independent | `chain=image, u2=independent` | 15 | 240-255 | H2 |
| u2_base3 | `chain=image, u2=base3` | 16 | 256-271 | H2 |
| per_path_start | `chain=lane:1` | 17 | 272-287 | H2 |
| stop_at_emitter | `chain=image, continue_after_emitter=False` | 18 | 288-303 | H4 |

The base seed of each configuration is 16 times its block. Block 0 is shared with experiment 001. The variants take
blocks 10-18, the first free blocks after 001's block 9. New renders: 144 (9 configurations x 16). Reused: 16.

### Commands

1. Render until the harness exits 0 (exit 3 means jobs remain):
   `.venv/bin/python -m painterly_analysis.experiment run experiments/002-2026-10-08-ingredient-ablation/jobs.py --budget 540`
2. Analysis, after all renders exist:
   `.venv/bin/python experiments/002-2026-10-08-ingredient-ablation/analyze.py`
   It writes `results.json` and the `fig_*.png` previews next to this file, and prints the tables. It re-runs from the
   cache and is deterministic. The options `--jobs`, `--reference` and `--out-dir` exist only to validate the script
   on a smaller subset. They are not part of the experiment.

### Analysis

- Metrics: `experiment.measure_ensemble` per configuration, which calls `metrics.measure` on each pair against the
  400 px GUI reference `tests/data/reference/smallpaint_painterly.ppm`, with the diffuse-only id map of D5. The
  object-id map of the first render of each configuration is asserted to be identical across configurations.
- Tests, decision rules and effect sizes are as in Hypothesis, over the keys named there.
- K draws: `k_consumed` of each render, averaged over pixels and divided by P.
- Figures (`io.write_png`):
  - `fig_positive.png` and `fig_<variant>.png` for each of the nine variants: `ab8` of pair 0, where
    `ab8 = smallpaint_display(sum_a + sum_b, 2P)`.
  - `fig_grid.png`: a 3 x 4 mosaic of quarter-size previews (4 x 4 block means), in row-major order: positive,
    ghost_none, ghost_lights, alpha_025 / alpha_05, alpha_1, u2_independent, u2_base3 / per_path_start,
    stop_at_emitter, reference, and an empty cell. The layout is also written to `results.json`.

### Deviations from the card, decided before the analysis

- **D1 (H5 keys).** The card's H5 says "compare_ensembles on all keys". The card's design rule says the diffuse family
  for every comparison, and this experiment follows the design rule. With all 67 keys that `metrics.measure` returns
  at 400 px (46 diffuse, plus 21 of regions 0, 1 and 9; counted from one pair of experiment 001's `img64`), the
  smallest attainable p-value, 2 / C(16, 8) = 1.55e-4, exceeds the first Holm threshold 0.01 / 67 = 1.49e-4, so
  `compare_ensembles` would raise and no key could be rejected.
- **D2 (positive control options).** The card writes the positive control as `chain=image, ghost=all` on `scene=gui`.
  Both are oracle defaults, and the explicit options would change the cache key. The option set is therefore left as in
  experiment 001 (`chain=image`, `size=400`, `passes=64`). Behaviour is identical, and the 16 renders are reused.
- **D3 (H1 correction).** The card names `separated` for H1 with no correction. The two H1 tests are reported
  separately, each at alpha = 0.01, so the family-wise error over the pair of tests is at most 0.02. The exact p-values
  are reported so that a reader can apply any correction.
- **D4 (H4 and H5 wording).** The card does not define "changes both region means and texture" or "keeps most of the
  look" as decisions. H4 uses the key classes defined above. H5 has no numeric threshold, so its verdict is the
  comparison outcome, and the gap is reported through the ratios and effect sizes.
- **D5 (measured regions).** `analyze.py` measures the diffuse regions only. Before `metrics.measure`, every non-diffuse
  id (0 mirror sphere, 1 glass sphere and 9 light, SPEC §9) is set to -1 (`_diffuse_only`), so `region_masks` skips it.
  Without this, the light has one eroded pixel at 64 px, so it has no lag-1 pairs, and `metrics.measure` raises. The
  non-diffuse keys (21 at 400 px) enter no test, table or decision here. A diffuse mask is `erode(object_id == r)`, and
  the `all.*` keys use the union of the diffuse masks, so the pixels set to -1 change no value that is used. Checked on
  the 2-pair smoke at 128 px: the figures are byte-identical, and `results.json` differs from the unrestricted version
  only in `metric_keys` (67 measured keys before, 46 now).

### Amendments (T1.12)

- Metrics are computed by report.ensemble_metrics (T1.11), the same metrics.measure call that the Analysis section names as experiment.measure_ensemble.

## Results

Source: `results.json` and the `fig_*.png` previews, written by `analyze.py` from the render cache (160 renders: 144 new,
16 reused from experiment 001). Every number below is in `results.json` or is computed from it.

Set-up, as recorded in `results.json`: 8 pairs per configuration, size 400 px, P = 64 passes, 46 keys in the diffuse
family, significance 0.01. The smallest attainable p is 1.55e-4 (two-sided) and 7.77e-5 (one-sided). The first Holm
threshold is 2.17e-4, so every family comparison is powered. Means ± sd are over the 8 pairs (sample sd). The relative
difference is (mean a − mean b) / |mean b|. Cohen's d uses the pooled sd. A second run of `analyze.py` into a scratch
out-dir reproduced `results.json` and all 11 `fig_*.png` byte for byte (`cmp`). The largest figure is 403,833 bytes.

Footnote on Cohen's d: the values in the thousands (for example −4409 in H1) reflect the seed-to-seed sd. That sd is
0.02 to 0.06 grey levels for `r4.luma` in every configuration (table 1). They are not large standardized effects, so
the text uses the relative difference as the effect size.

### 1. `r4.luma`, `all.pattern_corr` and `r4.structure_std`, mean ± sd over 8 pairs

All rows use size 400 and passes 64. The positive control uses the oracle defaults apart from `chain=image`.

| configuration | option | r4.luma | all.pattern_corr | r4.structure_std |
|---|---|---|---|---|
| positive | chain=image | 144.375 ± 0.038 | 0.5889 ± 0.0016 | 5.738 ± 0.071 |
| ghost_none | ghost=none | 12.935 ± 0.019 | 0.00047 ± 0.00155 | 3.575 ± 0.074 |
| ghost_lights | ghost=lights | 191.517 ± 0.064 | 0.00491 ± 0.00336 | 5.384 ± 0.073 |
| alpha_025 | alpha=0.25 | 118.061 ± 0.036 | 0.0798 ± 0.0025 | 4.833 ± 0.046 |
| alpha_05 | alpha=0.5 | 94.137 ± 0.025 | 0.0339 ± 0.0026 | 4.275 ± 0.066 |
| alpha_1 | alpha=1.0 | 5.507 ± 0.017 | −0.00249 ± 0.00238 | 1.699 ± 0.042 |
| u2_independent | u2=independent | 125.989 ± 0.035 | 0.0113 ± 0.0041 | 0.022 ± 0.063 |
| u2_base3 | u2=base3 | 140.360 ± 0.052 | 0.00950 ± 0.00355 | 1.110 ± 0.542 |
| per_path_start | chain=lane:1 | 141.631 ± 0.051 | 0.1260 ± 0.0026 | 2.562 ± 0.121 |
| stop_at_emitter | continue_after_emitter=False | 126.795 ± 0.023 | 0.0964 ± 0.0016 | 9.942 ± 0.071 |

### 2. K draws per pixel per pass

Mean over pixels of `k_consumed / P`, mean ± sd over the 16 renders of each configuration.

| configuration | K per pixel per pass | K minus positive |
|---|---|---|
| positive | 16.274 ± 0.0009 | 0 |
| ghost_none | 18.682 ± 0.0008 | +2.408 |
| ghost_lights | 19.210 ± 0.0009 | +2.936 |
| alpha_025 | 15.958 ± 0.0012 | −0.316 |
| alpha_05 | 15.990 ± 0.0010 | −0.284 |
| alpha_1 | 19.187 ± 0.0006 | +2.913 |
| u2_independent | 17.736 ± 0.0012 | +1.462 |
| u2_base3 | 17.333 ± 0.0013 | +1.059 |
| per_path_start | 16.213 ± 0.0015 | −0.061 |
| stop_at_emitter | 5.056 ± 0.0013 | −11.218 |

### 3. Decision table, one row per hypothesis

| H | comparison | test, alpha = 0.01 | deciding numbers | decision |
|---|---|---|---|---|
| H1 | ghost_none vs positive; alpha_1 vs positive; r4.luma | one-sided "less" each, not corrected across the two (D3) | p_less = 7.77e-5 for both (min attainable 7.77e-5); p_greater = 1 for both | supported |
| H2 | u2_independent, u2_base3, per_path_start vs positive; all.pattern_corr | one-sided "less", Holm over 3 | p_less = 7.77e-5 for all three, all Holm-rejected; no "greater" rejected | supported |
| H3 | positive, alpha_025, alpha_05, alpha_1; r4.luma, three adjacent steps | one-sided "less" per step, Holm over 3 | p_less = 7.77e-5 for all three steps, all Holm-rejected; no "greater" rejected | supported |
| H4 | stop_at_emitter vs positive; diffuse family, 46 keys | Holm over 46, two-sided permutation | 44 of 46 rejected; 18 of 18 region-mean keys; 24 of 26 texture keys; min attainable p 1.55e-4 < 2.17e-4 | supported |
| H5 | ghost_lights vs positive; diffuse family, 46 keys | Holm over 46, two-sided permutation | 45 of 46 rejected; min attainable p 1.55e-4 < 2.17e-4 | distinguishable |

### 4. H1 to H3: effect sizes per comparison

Each comparison has one key, so its relative difference and Cohen's d are the largest |rel| and largest |d| of that
comparison. Each H1 and H2 "less" test has p_greater = 1, and each H3 "greater" p is 1.

| H | a vs b | key | mean a ± sd | mean b ± sd | rel. diff | Cohen d | p_less | min attainable p |
|---|---|---|---|---|---|---|---|---|
| H1 | ghost_none vs positive | r4.luma | 12.935 ± 0.019 | 144.375 ± 0.038 | −0.910 | −4409 | 7.77e-5 | 7.77e-5 |
| H1 | alpha_1 vs positive | r4.luma | 5.507 ± 0.017 | 144.375 ± 0.038 | −0.962 | −4756 | 7.77e-5 | 7.77e-5 |
| H2 | u2_independent vs positive | all.pattern_corr | 0.0113 ± 0.0041 | 0.5889 ± 0.0016 | −0.981 | −186 | 7.77e-5 | 7.77e-5 |
| H2 | u2_base3 vs positive | all.pattern_corr | 0.00950 ± 0.00355 | 0.5889 ± 0.0016 | −0.984 | −211 | 7.77e-5 | 7.77e-5 |
| H2 | per_path_start vs positive | all.pattern_corr | 0.1260 ± 0.0026 | 0.5889 ± 0.0016 | −0.786 | −213 | 7.77e-5 | 7.77e-5 |
| H3 | alpha_025 vs positive | r4.luma | 118.061 ± 0.036 | 144.375 ± 0.038 | −0.182 | −710 | 7.77e-5 | 7.77e-5 |
| H3 | alpha_05 vs alpha_025 | r4.luma | 94.137 ± 0.025 | 118.061 ± 0.036 | −0.203 | −762 | 7.77e-5 | 7.77e-5 |
| H3 | alpha_1 vs alpha_05 | r4.luma | 5.507 ± 0.017 | 94.137 ± 0.025 | −0.942 | −4113 | 7.77e-5 | 7.77e-5 |

### 5. H4 and H5: rejected keys over the diffuse family

| H | comparison | rejected (Holm, alpha = 0.01) | min attainable p | first Holm threshold | largest abs rel. diff (key) | largest abs Cohen d (key) |
|---|---|---|---|---|---|---|
| H4 | stop_at_emitter vs positive | 44 of 46 | 1.55e-4 | 2.17e-4 | 69.02 (all.block_rmse) † | 1621 (all.block_rmse) |
| H5 | ghost_lights vs positive | 45 of 46 | 1.55e-4 | 2.17e-4 | 130.8 (all.block_rmse) † | 1275 (all.block_rmse) |

† `all.block_rmse` has a near-zero positive mean (0.381), so its relative difference is not an effect size. Its absolute
differences are: H4 +26.27 (26.652 ± 0.012 against 0.381 ± 0.019); H5 +49.80 (50.180 ± 0.052 against 0.381 ± 0.019).
`all.spectral_slope` has a near-zero mean (−0.044), so its absolute differences are given instead: H4 +0.00037
(−0.04399 ± 0.00847 against −0.04436 ± 0.00916); H5 −0.381 (−0.425 ± 0.010 against −0.044 ± 0.009).

Keys not rejected. The p-values are raw two-sided permutation p-values. Each has min attainable p 1.55e-4.

| H | key | p | mean a ± sd | mean b ± sd | rel. diff | Cohen d |
|---|---|---|---|---|---|---|
| H4 | all.spectral_slope | 0.932 | −0.04399 ± 0.00847 | −0.04436 ± 0.00916 | (absolute diff +0.00037) | 0.042 |
| H4 | r3.lag1.y | 0.752 | 0.1893 ± 0.0058 | 0.1902 ± 0.0063 | −0.005 | −0.16 |
| H5 | r5.structure_std | 0.172 | 3.622 ± 0.139 | 3.542 ± 0.069 | +0.023 | 0.73 |

Clip fraction (`all.clip_fraction`): H5 0.07115 ± 0.00074 (ghost_lights) against 0.004338 ± 0.000108 (positive), relative
difference +15.40. H4 0.01175 ± 0.00014 (stop_at_emitter), relative difference +1.71.

### 6. H5: ratios of ensemble means, ghost_lights / positive

| region | mean R | mean G | mean B |
|---|---|---|---|
| 2 | 1.369 | 1.440 | 1.201 |
| 3 | 1.923 | 1.957 | 1.814 |
| 4 | 1.296 | 1.332 | 1.356 |
| 5 | 1.293 | 1.315 | 1.348 |
| 6 | 1.190 | 1.204 | 1.225 |
| 7 | 0.786 | 0.728 | 0.718 |

`all.pattern_corr` ratio: 0.0083 (0.00491 / 0.5889). `r4.luma` ratio: 1.327 (191.517 / 144.375).

### 7. Notes

- **ghost_lights and the pattern correlation.** `all.pattern_corr` is 0.00491 ± 0.00336 and `r4.structure_std` is
  5.384 ± 0.073 against 5.738 ± 0.071 (ratio 0.938). K consumption is 19.210 against 16.274 (+2.936). The card's
  reading is that the pattern correlation measures agreement with one realization of the texture, so it collapses
  whenever K consumption changes. Table 2 does not establish this as the general rule. `per_path_start` changes K by
  −0.061 and still has `all.pattern_corr` 0.1260. `alpha_025` and `alpha_05` change K by −0.316 and −0.284 and have
  0.0798 and 0.0339. `alpha_1` changes K by +2.913 and has −0.00249. Across the nine variants, `all.pattern_corr` lies
  between −0.00249 and 0.1260. The K explanation is therefore not tested by these configurations.
- **Differences from the Hypothesis text.** The Hypothesis cites 193 for the `ghost=lights` back wall (T1.7 card). The
  measured `r4.luma` is 191.517 ± 0.064, which is 1.483 lower. The Hypothesis cites a research-phase pattern correlation
  of about 0 to 0.11 for the three H2 variants. The measured `per_path_start` value is 0.1260 ± 0.0026. The measured
  values are used throughout.

## Conclusion

Final (Opus, 2026-10-09). The Haiku draft is superseded. The numbers are those in Results.

**Every ingredient the plan named is necessary, and each controls a different part of the look.**

- **H1 supported: the back wall is lit by the ghost spheres through the unnormalized bounce.**
  - `r4.luma` is 12.94 ± 0.02 without ghosts and 5.51 ± 0.02 with a normalized bounce (α = 1), against 144.38 ± 0.04.
  - Both "less" tests are at the smallest attainable p (7.77e-5).
- **H2 supported: the lockstep u1 = u2 *is* the texture.**
  - With an independent u2 the texture amplitude `r4.structure_std` falls from 5.74 to 0.02. With a base-3 u2 it falls to
    1.11. The pattern correlation falls to 0.011 and 0.010.
  - Per-path random starts (`lane:1`) keep the spiral but break the chain. Amplitude halves (2.56) and the pattern
    correlation falls to 0.126.
- **H3 supported: α is a continuous but strongly nonlinear control.**
  - The back wall goes 144.4 → 118.1 → 94.1 → 5.5 for α = 0, 0.25, 0.5, 1.
  - Any α > 0 already changes the texture's realization (pattern correlation 0.080 at α = 0.25) while most of its amplitude
    stays (4.83). α is a stylization knob that trades back-wall brightness for realization. It is not a fidelity knob, and
    its default stays 0.
- **H4 supported: the zero-throughput continuation after an emitter hit is part of the look.**
  - It consumes 11.2 of the 16.3 draws per pixel per pass.
  - Stopping at the emitter changes 44 of 46 keys. The texture amplitude rises by 73% (9.94) and the back wall dims by 12%.
  - `continue_after_emitter` stays true by default, and it is a strong contrast control for artists.
- **H5: lights-only ghosting is distinguishable from the reference look (45 of 46 keys).**
  - The back wall is 33% brighter (191.5), the clip fraction is 16× (0.071), and the realization is lost (pattern
    correlation 0.005).
  - The texture amplitude is close: 5.38 against 5.74 (−6%).
  - Lights-only ghosting is what a Blender scene gives (meshes are never ghosts), so it is the Blender look. It is a
    different look, not a degraded copy.

**On the pattern correlation.** It measures agreement with one specific realization of the texture. Every variant here
that loses that realization also changes K consumption. K consumption is not the whole story, though: per-path starts
leave consumption almost unchanged (−0.06 draws) and still fall to 0.126, because each pixel then sees a different K
sequence. The K explanation is therefore *consistent with these configurations, not isolated by them*. The Haiku draft was
right to say so.

**Decisions.**
1. M5 T5.4: Blender parity is judged against the oracle's `--ghost lights` ensemble, on `metrics.realization_free_key_family`.
   Pattern correlation against the GUI reference image is never a parity criterion for Blender scenes.
2. SPEC defaults confirmed: `u2_mode = same`, `alpha = 0`, `continue_after_emitter = true`, and ghosts for every analytic
   sphere in reference mode.

**Hypothesis for later work.** The realization is a function of the K sequence each pixel sees. A test: an oracle knob that
adds a fixed number of extra draws per diffuse event changes only K, not geometry or sampling. The pattern correlation
should then fall with the number of extra draws, while amplitude and region means stay.
