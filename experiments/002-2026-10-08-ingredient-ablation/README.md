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
- Key family: `metrics.DIFFUSE_KEY_FAMILY(keys)`, which has 46 keys for the GUI scene. Every `compare_ensembles` call
  uses it, never all keys.
- Power: the smallest attainable p-value of 8 vs 8 pairs is 2 / C(16, 8) = 1.55e-4 two-sided, and 1 / C(16, 8) =
  7.77e-5 one-sided. A family comparison is powered only if that minimum is at most alpha / 46 = 2.17e-4, which holds.
  An underpowered comparison has no decision of "indistinguishable" or "refuted". It is reported as underpowered.
- Estimation over verdicts: for every variant, the effect size against the positive control is reported for each key:
  `ensemble.effect_summary` (mean +- sd, relative difference, Cohen's d = (mean_v - mean_pos) / pooled sd). Any
  "indistinguishable" verdict is reported with `min_attainable_p` and the largest observed |relative difference|.

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
- Test: `ensemble.compare_ensembles(stop_at_emitter, positive, DIFFUSE_KEY_FAMILY(keys), alpha = 0.01)`, Holm over the
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
- Test: `ensemble.compare_ensembles(ghost_lights, positive, DIFFUSE_KEY_FAMILY(keys), alpha = 0.01)`. Also the ratio of
  the ensemble means `ghost_lights / positive` for `all.pattern_corr` and for each region-mean key of the family.
- Verdict: "distinguishable" if at least one family key is rejected. "indistinguishable" if none is rejected and the
  comparison is powered. "underpowered" otherwise. Distinguishable is the expected result. The card gives no numeric
  threshold for "most", so the verdict covers only the comparison. How much of the look remains is read from the
  ratios and the effect sizes, and the Conclusion will report them without a threshold.

## Method

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
