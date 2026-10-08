# Experiment 004: is the texture pixel-locked? (Resolution and jitter units)

## Background

- `docs/plan.md`, "What makes the look", item 3 (scan-line chaining): each path's counter K starts where the previous
  pixel's path in the same row ended, which gives a converged texture. The research port reports pattern correlation
  with the reference of 0.63 for the row chain. Item 1 (spiral sampling) fixes the bounce geometry, so the texture
  statistics come from the K-driven sample sequence.
- `docs/spec.md` §3: `chain=image` is one chain over the whole render, in the order `for pass, for row, for col`. K is
  never reset. The K stream therefore couples neighbouring pixels in raster order, and that coupling lives on the pixel
  grid. The scene itself (SPEC §9) is defined in world units, so only the sampling grid changes with the image side.
- `docs/spec.md` §7: the camera maps a pixel to image-plane coordinates with a pixel size of 2/W units (tan(π/4) = 1).
  The jitter `j` is in image-plane units, and `rng_signed` lies in [−1, 1) (SPEC §2), so the maximum displacement is
  `j·W/2` pixels. The reference jitter 1/700 is therefore W/1400 pixels: 0.29 px at 400 px. At 800 px, 1/700 is 0.57 px
  and 1/1400 is 0.29 px. SPEC §7 says the Blender jitter is "a knob in pixels whose default comes from the
  X-resolution experiment", so this experiment fixes that default.
- `experiments/001-2026-10-08-oracle-reproduction/`: the compiled oracle reproduces the reference. Its `img64` ensemble
  (block 0, seeds 0-15, `chain=image`, P = 64, size 400, default jitter) is this experiment's positive control `s400`.
  Its `all.pattern_corr` at P = 64 is 0.588908 (sd 0.001582).
- `experiments/002-2026-10-08-ingredient-ablation/` uses blocks 10-18 and `experiments/003-2026-10-08-lane-length/` uses
  blocks 19-27. This experiment starts at block 28.
- Two readings of the look are possible. In the **pixel-locked** reading, the texture's correlation length is fixed in
  pixels, so it is the same at 200, 400 and 800 px. In the **world-locked** reading, the correlation length is fixed in
  world units, so it doubles in pixels from 400 to 800 px. The two readings make opposite predictions on the tests
  below, which is why both are run.

## Hypothesis

### Common definitions

- A configuration is an ensemble of 8 pairs. A pair is two independent half renders (seeds 2k and 2k+1 of one
  configuration), each with P = 64 passes, `chain=image`, `scene=gui` and `ghost=all` (the oracle defaults). The jitter
  is the oracle default 1/700 unless a configuration says otherwise.
- **Reference-free metrics.** `metrics.measure` needs the reference image. Size comparisons therefore use the
  reference-free metrics that `analyze.py` computes from the same definitions as `metrics.measure`, per pair and at the
  configuration's own size, with the configuration's own object id map:
  - `r{r}.mean.{R,G,B}`: region mean of `ab8`;
  - `r{r}.structure_std`: `metrics.structure_std` of the high-passed luminance of `a8` and `b8`;
  - `r{r}.lag1.x`, `r{r}.lag1.y`: raw lag-1 autocorrelation of the high-passed luminance of `ab8`, along columns (x) and
    rows (y);
  - `r{r}.slag1.x`, `r{r}.slag1.y`: **noise-corrected** lag-1 of the structure, defined in the Method;
  - `r{r}.spectral_slope`: `metrics.radial_spectral_slope` of the high-passed `ab8` over the region mask;
  - `all.clip_fraction`, `all.spectral_slope`: as in `metrics.measure`.
  - Here `r` runs over the measured diffuse regions (SPEC §9 ids 2-8, eroded as in `metrics.measure`). The light (id 9)
    is excluded.
- **Key families.** Every `compare_ensembles` call uses `metrics.DIFFUSE_KEY_FAMILY(keys)` for its key list, or a subset
  named in the hypothesis. It never uses all keys. The reference-free dictionary has 56 keys (6 measured regions with 9
  keys each, plus 2 `all.*` keys), not the 46 of `metrics.measure`, because it has no `pattern_corr` or `block_rmse`.
  H1b's subset is the 12 noise-corrected lag-1 keys (D7).
- **Significance.** The family-wise level is alpha = 0.01 (written `SIGNIFICANCE` in the code). It is not the oracle
  option `alpha`. Every p-value is an exact two-sided permutation p-value (`ensemble.permutation_pvalue`). Holm
  (`ensemble.holm`) is applied across the keys of each comparison. Where one hypothesis contains several comparisons,
  the level of each comparison is divided by their number, as stated in its test.
- **Power.** For 8 vs 8 pairs, the smallest attainable two-sided p-value is 2 / C(16, 8) = 1.55e-4. A comparison of n
  keys at level a is powered iff 1.55e-4 <= a / n. An underpowered comparison is reported as `inconclusive`, never as
  `supported` or `refuted`, and it is not passed to `compare_ensembles`.
- **Estimation over verdicts.** Every comparison reports `ensemble.effect_summary` (mean ± sd, relative difference,
  Cohen's d). "Indistinguishable" is only written together with `min_attainable_p` and the largest observed |relative
  difference|.

### H1: the texture is pixel-locked

- Derived from: plan item 3 and SPEC §3. The image chain runs one K stream over pixels in raster order, so the coupling
  between neighbouring pixels is set by the pixel grid. The scene is in world units. If the coupling is pixel-locked,
  the lag-1 correlation of the texture in pixels does not depend on the image side. The correlation length in pixels
  does not either.
- Observable: the noise-corrected lag-1 `r{r}.slag1.x` and `r{r}.slag1.y`. Noise-corrected means that the lag-1
  autocorrelation of the structure is separated from the noise-to-structure ratio, which changes with resolution at
  fixed P. The raw lag-1 is reported alongside it, with effect summaries and no verdict.
- **H1a (sizes).** Predicted by H1: the noise-corrected lag-1 keys are indistinguishable across 200, 400 and 800 px.
  - Tests: for each size pair in {(200, 400), (400, 800), (200, 800)}, `compare_ensembles` on the 12 `slag1` keys of the
    measured regions, at alpha = 0.01 / 3 (the three pairs share the level).
  - Decision: refuted iff some key is Holm-rejected in any size pair. Supported iff no key is rejected and all three pairs
    are powered (threshold (0.01/3)/12 = 2.8e-4, which is at least 1.55e-4). Otherwise inconclusive.
- **H1b (downsample).** Predicted by H1: the 800 px render, box-downsampled to 400 px, is distinguishable from native
  400 px. If the texture is pixel-locked, the 800 px texture has a correlation length of ℓ pixels. After 2 x 2
  downsampling it has ℓ/2 pixels at 400 px, while the native 400 px texture has ℓ pixels. The two therefore differ on
  the noise-corrected lag-1 keys.
  - Tests: `compare_ensembles` between the downsampled 800 px ensemble and the native 400 px ensemble on the 12 `slag1`
    keys of the measured regions, at alpha = 0.01. Their values on the downsampled ensemble use the native 400 px object
    id map (`_reference_free_downsampled`). The other keys of the downsample comparison, the 45 keys of
    `metrics.DIFFUSE_KEY_FAMILY(keys)` for `metrics.measure` without `all.block_rmse` (raw lag-1, `structure_std`,
    `pattern_corr` against the reference, and the rest), get `ensemble.effect_summary` only, with no p-value and no
    verdict (D7).
  - Decision: supported iff the comparison is powered (threshold 0.01/12 = 8.3e-4, which is at least 1.55e-4) and at least
    one key is Holm-rejected. Refuted iff it is powered and no key is rejected. Otherwise inconclusive.
  - Limitation (D7). Box averaging changes the lag-1 of the structure even without noise, under both readings. So a
    "distinguishable" result here does not by itself favour the pixel-locked reading. This is open for Opus before Phase B.
- **H1 (overall).** Supported iff H1a and H1b are both supported. Refuted iff either is refuted. Otherwise inconclusive.
  The world-locked reading predicts that H1a is refuted (the noise-corrected lag-1 keys rise with the side) and that H1b
  is not distinguishable. The second prediction ignores the box filter (D7).

### H2: jitter units do not matter for the look

- Derived from: SPEC §7. The image-plane jitter corresponds to a blur that scales with the side length in pixels. At
  800 px, 1/700 displaces by up to 0.57 px and 1/1400 by up to 0.29 px. If the jitter changes the texture, the two differ.
  If the look is insensitive to jitter units, they agree.
- Test: `compare_ensembles(s800, s800_j1400, F2, alpha = 0.01)`, where F2 has 30 keys: the raw lag-1 keys (12), the
  noise-corrected lag-1 keys (12) and `r{r}.structure_std` (6). The family is powered (threshold 0.01/30 = 3.3e-4, which
  is at least 1.55e-4).
- Decision: supported (the jitter units matter) iff the comparison is powered and at least one key of F2 is
  Holm-rejected ("distinguishable"). Refuted (jitter units do not matter for the look at 800 px) iff it is powered and no
  key is rejected. Otherwise inconclusive.

## Method

### Configurations

All configurations: P = 64, `chain=image`, 8 pairs. The scene and ghost are the oracle defaults and are left implicit, as
in experiments 001-003. The jitter default 1/700 is left implicit too, so the option sets of the 1/700 configurations
hold no jitter key. Only `s800_j1400` passes `jitter`, with the value `1.0 / 1400.0`.

| name | size | oracle options (besides `passes=64`, `chain=image`) | seed block | seeds | renders |
|---|---|---|---|---|---|
| s200 | 200 | `size=200` | 28 | 448-463 | 16 new |
| s400 | 400 | `size=400` | 0 | 0-15 | 16, reused (experiment 001's `img64`) |
| s800 | 800 | `size=800` | 29 | 464-479 | 16 new |
| s800_j1400 | 800 | `size=800`, `jitter=1/1400` | 30 | 480-495 | 16 new |

The base seed of each configuration is 16 times its block. Block 0 is shared with experiment 001 on purpose: `s400` has
the same options as `img64`, so its 16 renders come from the cache. New renders: 48 (3 x 16). Reused: 16.

### Downsample

The 800 px ensemble is downsampled to 400 px by the 2 x 2 box mean of the per-pixel sums of each half render:
`sum400[i, j] = (sum800[2i, 2j] + sum800[2i+1, 2j] + sum800[2i, 2j+1] + sum800[2i+1, 2j+1]) / 4`. Each downsampled half
render is then displayed with `smallpaint_display` at P = 64, as native renders are. The object id map used for the
masks is the native 400 px map, so that both sides of the comparison use the same regions.

### Commands

1. Render until the harness exits 0 (exit code 3 means jobs remain):
   `.venv/bin/python -m painterly_analysis.experiment run experiments/004-2026-10-08-resolution-dependence/jobs.py --budget 540`
2. Analysis, once all renders exist:
   `.venv/bin/python experiments/004-2026-10-08-resolution-dependence/analyze.py`
   It writes `results.json` and `fig_grid.png` next to this file and prints the tables. It re-runs from the cache and is
   deterministic, since every test is an exact permutation test.

The options `--pairs`, `--scale`, `--reference` and `--out-dir` exist only to validate `analyze.py` on a smaller subset in
a scratch `PAINTERLY_CACHE` (D6): `--pairs 2 --scale 4` (sizes 50, 100 and 200) and `--pairs 2 --scale 2` (sizes 100, 200
and 400), each with `--reference` at the scaled size. They are not part of the experiment. The defaults are the experiment.

### Analysis

- **Design check.** Each configuration must have the options and seed block above, consecutive seeds, and no seed of
  experiments 001-003 except the positive control `s400`. If the control is run at full scale, its options must equal
  those of experiment 001's `img64`. The object id map of each configuration is checked against the others of the same
  size. The diffuse regions measured must be the same in every configuration (the analysis stops otherwise, since the
  keys could not be compared). At `--scale 1` this is strict. At smoke scale only, the comparisons use the regions
  measured in every configuration (D6).
- **Noise-corrected lag-1.** For two independent half renders with high-passed luminance `a` and `b`, a region mask `M`,
  and an axis (x or y): `cov_1` is the covariance of `a[p]` and `b[p + 1]` over the pairs `(p, p + 1)` with both pixels
  in `M`, and `cov_0` is the covariance of `a` and `b` over `M`. Both covariances are the population form, each centred
  by its own masked mean. `slag1 = cov_1 / cov_0`. The halves share the structure and have independent noise, so `cov_0`
  estimates the structure variance and `cov_1` its lag-1 covariance. Their ratio is the structure's lag-1 autocorrelation.
  The display of SPEC §7 is `min(floor(sum) / P, 255)`, linear in the sum up to byte quantization and clipping, so the
  noise term cancels in expectation at any P and after box downsampling. Quantization and clipping make this approximate.
- **Tests and decisions.** As in the Hypothesis section, on the keys named there.
- **Outputs.** `results.json` holds every number in the tables: for each comparison, the effect summary, p-values,
  power limit, rejected keys and decision, and the descriptive `downsample_effects` (D7). `fig_grid.png` is a mosaic of
  pair 0's display images at 200 px per tile, in the layout `(s200, s400, s800)`, `(s800_j1400, downsampled 800,
  reference)`.

### Deviations and decisions made before the analysis

- **D1 (seed blocks).** The card's first new block is 10. Experiments 002 and 003 have taken blocks 10-27, so the new
  blocks here are 28-30, the first free blocks after experiment 003's block 27, as the orchestrator directed. Seeds stay
  globally unique.
- **D2 (noise-corrected keys in H1a).** The card asks for the lag-1 keys across sizes. A test on the 24 raw and
  noise-corrected lag-1 keys across three size pairs at alpha = 0.01 / 3 has threshold 1.4e-4, below the minimum attainable
  p of 1.55e-4, so it could never reject. H1a therefore tests the 12 noise-corrected keys, which measure the correlation
  length. The raw keys are reported with effect summaries only. H2 is a single comparison, so it tests both.
- **D3 (downsample family).** The card's "reference-free keys plus `pattern_corr`" is the 45 keys of `metrics.measure`
  without `all.block_rmse`. Its verdict is replaced by the 12 noise-corrected keys (D7). The 45 keys are reported with
  effect summaries only.
- **D4 (spectral slope).** The card lists `radial_spectral_slope` among the per-region metrics. It is computed per
  region and reported, but it is not tested, because the card's tests name lag-1 and structure keys only. `all.spectral_slope`
  is the union-mask slope of `metrics.measure`.
- **D5 (scale of the design check).** The design check asserts the expected options at the requested scale. Under
  `--scale s`, only the sizes differ from the experiment's option sets. The experiment itself runs at `--scale 1`.
- **D6 (smoke scale).** The orchestrator's smoke subset is 2 pairs at sizes 50, 100 and 200 (`--pairs 2 --scale 4`).
  At size 50, diffuse region 2 (left sphere) erodes away (erosion radius 4 px), so the six regions differ between sizes.
  At `--scale` above 1, the comparisons therefore use the regions measured in every configuration (3-7 at this scale;
  region 2 is listed as `dropped_at_this_scale`). At `--scale 1` the rule is strict and stops the analysis. The smoke at
  `--scale 2` (sizes 100, 200 and 400) measures all six regions at every size and runs the strict rule. At full scale,
  the 1-pass object-id maps at 200, 400 and 800 px (and 800 px with jitter 1/1400) measure regions 2-7 and no region 8.
  The maps are identical across seeds and jitter, since the id is that of the unjittered primary hit (SPEC §9, `io.py`).
  The 2-pair smoke runs no comparison (its smallest attainable p is 0.333), so the decision path is also run in a scratch
  check with 8 pairs at `--scale 4`. That run is not part of the record.
- **D7 (noise and filter in the downsample test).** Found before any render of the real jobs, on the scratch smoke
  renders and a synthetic check. Two effects, with a decision for each.
  1. *Noise (decided: the verdict uses the noise-corrected keys).* 2 x 2 box averaging of the sums halves the per-pixel
     noise sd, and the structure is unchanged. On the 8-pair smoke at 100 px, the noise sd is 7.6 for native 400 px and
     3.8 for the box-downsampled 800 px, and the noise-to-structure variance ratio is 0.66 and 0.22. The raw lag-1 and
     `structure_std` depend on that ratio, so a first draft of H1b on the 45 keys would be expected to reject even for a
     world-locked texture. The noise-corrected lag-1 cancels the ratio. On a synthetic AR(1) structure with lag-1 0.6, `slag1` is
     0.602, 0.603 and 0.600 at noise sd 0, 0.5 and 2 times the structure sd. The raw lag-1 of the sum falls from 0.60 to
     0.53 and 0.20 over the same noise levels. H1b is therefore restricted to the `slag1` keys.
  2. *Filter (open, for Opus before Phase B).* Box averaging changes the lag-1 of the structure with no noise at all. For
     an AR(1) structure with lag-1 0.8 at 800 px, the world-locked prediction at 400 px is 0.64 (= 0.8²). The box average
     has lag-1 0.72 (= 0.8 (1 + 0.8) / 2; measured 0.7196). Under the pixel-locked reading, native 400 px has lag-1 0.80
     and its box average is again 0.72. Both readings therefore predict a difference of 0.08 on the H1b keys, so H1b as
     specified cannot tell them apart. On the smoke renders the effect is large: the structure's lag-1 at 100 px is 0.473
     natively and 0.671 after box-downsampling from 200 px (8 pairs, scratch). A filter-free comparison of the same world
     distance is available from the existing renders: native 800 px lag-2 against native 400 px lag-1. The card specifies
     the downsample test, so it is not substituted here. Opus decides whether H1b is kept as written, supplemented by that
     comparison, or replaced. No result has been computed on the real renders.
