# Experiment 006: which jitter unit makes the look independent of resolution? (scale-equivariant analysis)

## Background

- `docs/spec.md` §7: the Blender camera's jitter is defined in **pixels**, default 2/7 px. That is smallpaint's 1/700
  image-plane units at the 400 px reference. The reason given is that "pixels keep the stroke scale tied to the image".
  The camera maps a pixel to image-plane coordinates with a pixel size of 2/W units, so an image-plane jitter `j` is a
  maximum displacement of `j·W/2` pixels.
- `experiments/004-2026-10-08-resolution-dependence/`, pre-registered analysis, run with the same filters in **pixels**
  at every size (a 9-px box high-pass, 4-px erosion, lag 1):
  - H1a, H1b and H1d refuted: the structure lag-1 differs across 200, 400 and 800 px.
  - H2 supported: at 800 px the jitter unit changes the texture, with `r4.structure_std` 4.14 ± 0.02 (jitter 1/700) vs
    4.79 ± 0.03 (1/1400).
  - Opus limitation note: a fixed pixel filter covers half the image-plane footprint at 800 px that it covers at 400 px,
    so those verdicts do not separate texture locked to the pixel grid from texture locked to the image.
- The milestone review's exploratory re-analysis of 004 (not pre-registered) scaled the high-pass, erosion and lag with
  the image side.
  - With image-plane jitter (1/700 at every size), the texture agreed across sizes for both chains: 0-1 of 12
    structure-lag keys rejected, amplitude relative differences −0.007 to +0.063, region luma within 0.2%.
  - With pixel jitter (2/7 px at 800 px, i.e. 1/1400), amplitude differed by +5 to +9% (10 of 12 rejected).
  - That analysis used odd box sizes (17 or 19 for "18"), so the scaling was approximate. It suggests that image-plane
    jitter, not pixel jitter, gives a resolution-independent look, the opposite of SPEC §7's reasoning.
- The review recommends jitter as a fraction of the camera's fitted image dimension, default 1/1400 of it (2/7 px at
  400 px). It asks for this pre-registered confirmation before SPEC §7 changes.
- `experiments/003-2026-10-08-lane-length/`: `chain=row` is the artist default (SPEC §3, 003 H3: row ≈ image, 0 of 46
  keys rejected). The SPEC decision below is therefore made on the row chain. Lane length is in pixels too. Whether it
  should become relative to the image is out of scope here and is left for M7.
- Mechanism, open. The K stream advances per pixel, so it lives on the pixel grid, while the scene lives in world units.
  004's exploratory result means that something maps the converged texture onto the image plane. The jitter footprint is
  one candidate: each pixel averages its paths over an image-plane disk of half-width `j`. A zero-jitter family tests
  whether the image-locking survives without that footprint (H4).
- Renders: seven of the thirteen configurations below have exactly the option sets of 004's configurations and reuse their
  cached seed blocks (28, 0, 29, 30, 31, 27, 32). The six new configurations take blocks 33-38, the first free blocks
  after 004's last block (32).

## Hypothesis

### Common definitions

- **Configurations.** Each configuration is an ensemble of 8 pairs. A pair is two independent half renders, seeds 2k and
  2k+1 of the configuration's block, each with P = 64 passes, `scene=gui` and `ghost=all` (the oracle defaults). The
  chain is `image` unless the name starts with `row_`, in which case it is `row`.
- **Jitter units.** Every configuration's oracle `--jitter` is in image-plane units.
  - *image-plane family*: 1/700 at every size (`s200`, `s400`, `s800`, and `row_` likewise).
  - *pixel family*: 2/7 px at every size, i.e. 1/350 at 200 px and 1/1400 at 800 px (`s200_px`, `s800_px`, `row_s200_px`,
    `row_s800_px`). The 400 px member is `s400` (or `row_s400`), where both units coincide.
  - *zero family*: jitter 0 (`j0_s200`, `j0_s400`, `j0_s800`). Both units coincide there at every size.
- **Scale-equivariant metrics.** Every quantity is defined in image-plane units and evaluated at the configuration's own
  side `s`. The reference side is s₀ = 400, where the plan's acceptance metrics are defined (a 9×9-box high-pass with a
  4-px erosion).
  - *High-pass*: `hp = x − G_σ * x`, where x is the luminance of a half render's display bytes (`metrics.luminance`) and
    `G_σ` is a Gaussian with `σ(s) = (9/√12)·s/s₀` px. That σ matches the variance of the plan's 9-px box at s₀.
    - Implementation: in the frequency domain on the half-sample-symmetric extension of x to 2s × 2s (x followed by its
      mirror image on each axis), with transfer function `exp(−2π²σ²(f_x² + f_y²))` (f in cycles per pixel of the
      extended grid), then cropped back to s × s.
    - Why a Gaussian, not a box: a centred box cannot be scaled by 2 and stay odd. The Gaussian is the scale-space
      kernel, so `σ ∝ s` scales exactly, and the mirror extension avoids wrap-around at the image border.
  - *Regions*: SPEC §9 ids 2-8 (the light, id 9, is excluded), eroded with radius `e(s) = 4·s/s₀` px: 2, 4 and 8 px.
    The measured regions must be the same in every configuration. A region that is empty after erosion in any
    configuration is excluded everywhere, and the excluded ids are reported.
  - *Lag*: `τ(s) = s/200` px, i.e. 1, 2 and 4 px. That is 1/200 of the image side, the pixel pitch of the smallest size.
  - Per measured region r and per pair (a, b): `r{r}.structure_std = sqrt(cov₀)`, `r{r}.slag.x = cov_τ,x / cov₀` and
    `r{r}.slag.y = cov_τ,y / cov₀`.
    - `cov₀` is the population covariance of `hp_a` and `hp_b` over the region mask.
    - `cov_τ,x` is the population covariance of `hp_a[p]` and `hp_b[p + τ·x̂]` over the pixel pairs with both pixels in
      the mask, each side centred by its own masked mean. `cov_τ,y` likewise along rows.
    - The halves share the structure and have independent noise, so `cov₀` estimates the structure variance and the
      ratio is the structure's autocorrelation at image-plane lag 1/200, as in 004's `slag1` (README, Analysis).
  - **Texture family T**: the 18 keys `r{r}.structure_std`, `r{r}.slag.x` and `r{r}.slag.y` over the 6 measured regions.
  - *Estimation-only keys* (effect summaries, no verdicts): `r{r}.mean.{R,G,B}` on the eroded masks, and
    `r{r}.spectral_slope`. The slope is `metrics.radial_spectral_slope` of `hp` over the region mask with `f_min = 2`
    and `f_max = 50` at every size. Its bins count cycles per image, so this is the same image-plane band at every size:
    the function's default band at 200 px.
- **Significance.** The family-wise level of each hypothesis is 0.01 (`SIGNIFICANCE`; not the oracle option `alpha`).
  - Every p-value is an exact two-sided permutation p-value (`ensemble.permutation_pvalue`), with Holm (`ensemble.holm`)
    across the 18 keys of each comparison.
  - A hypothesis with c comparisons runs each at 0.01/c.
  - **Power.** With 8 vs 8 pairs the smallest attainable two-sided p is 2/C(16, 8) = 1.55e-4. With c = 3 the first Holm
    threshold is (0.01/3)/18 = 1.85e-4, and with c = 2 it is 2.78e-4. Both are at least 1.55e-4, so every comparison
    below is powered.
- **Estimation.** Every comparison reports `ensemble.effect_summary` for the 18 T keys, the estimation-only keys,
  `report.largest_abs_rel_diff`, `report.largest_abs_cohen_d` and `min_attainable_p`. "Indistinguishable" is written
  only together with those numbers.

### H1: under image-plane jitter, the texture does not depend on resolution

- Derived from: 004's exploratory image-scaled re-analysis (Background). If the converged texture is a field on the image
  plane, renders at 200, 400 and 800 px with the same image-plane jitter sample one field, and the scale-equivariant
  metrics agree.
- **H1-image** (`s200`, `s400`, `s800`) and **H1-row** (`row_s200`, `row_s400`, `row_s800`). Each has the comparisons
  (200, 400), (400, 800) and (200, 800) on T at 0.01/3.
- Decision for each: supported iff no key is Holm-rejected in any of its three comparisons; refuted iff some key is.

### H2: under pixel jitter, the texture depends on resolution

- Derived from: 004 H2 (the jitter unit changes the texture at 800 px) and H1. If the texture lives on the image plane
  and depends on the image-plane jitter, then a jitter fixed in pixels, which is a different image-plane jitter at each
  size, changes the texture with size.
- **H2-image** (`s200_px` vs `s400`, `s800_px` vs `s400`) and **H2-row** (`row_s200_px` vs `row_s400`, `row_s800_px` vs
  `row_s400`). Each has two comparisons on T at 0.01/2.
- Decision for each: supported iff each of its two comparisons Holm-rejects at least one key. Refuted iff neither rejects
  any key. Otherwise partially supported, and the result is reported per comparison.

### H3: the jitter unit decides resolution independence on the artist chain (decision statistic)

- Derived from: H1 and H2 together. Both tests are very powerful (sd across seeds is small), so a tiny but systematic
  difference can reject in either family. The SPEC choice therefore uses a comparative effect statistic, not rejection
  counts.
- Statistic, for a unit u ∈ {image-plane, pixel} and a chain:
  - `Δ_u` is the median, over the 18 T keys and the two adjacent size pairs of that unit's family, of
    `|effect_summary rel_diff|`;
  - the adjacent pairs are (`s200_u`, `s400`) and (`s400`, `s800_u`), and for the image-plane unit `s200_u` is `s200`.
- Decision (row chain): **H3 supported iff Δ_image-plane < Δ_pixel**. Then SPEC §7 changes to image-plane units: jitter
  is a fraction of the camera's fitted image dimension, default 1/1400, which is 2/7 px at 400 px. Otherwise H3 is
  refuted and SPEC §7 keeps pixels.
- The same statistic is reported for the image chain, without a decision.
- Estimation only: 95% percentile bootstrap intervals for `Δ_u` and for `Δ_pixel − Δ_image-plane`. Pairs are resampled
  within each configuration, with `BOOTSTRAP_RESAMPLES = 10_000` and seed 0. The resample count sets only the Monte
  Carlo precision of the interval. No decision depends on the intervals, but the Conclusion must say whether the
  interval of the difference excludes 0.

### H4: with zero jitter, the texture still does not depend on resolution (mechanism)

- Derived from: the open mechanism (Background).
  - If the image-locking is a property of the chain and the scene, it survives without the jitter footprint, and the zero
    family agrees across sizes.
  - If the jitter footprint produces it, the zero family differs with size.
- Comparisons (`j0_s200`, `j0_s400`), (`j0_s400`, `j0_s800`) and (`j0_s200`, `j0_s800`) on T, each at 0.01/3.
- Decision: supported (intrinsic image-locking) iff no key is Holm-rejected in any comparison. Refuted (the jitter
  footprint is needed) iff some key is.

### H5: the erosion, not the renderer, explains 004's region-mean trend

- Derived from: 004's `r4.mean.G`, which fell from 153.94 at 200 px to 145.83 at 800 px under a fixed 4-px erosion.
  A fixed pixel erosion keeps a band near region edges whose image-plane width halves with each doubling of the side.
  With e(s) ∝ s the review measured r4 luma 144.25 at 800 px vs 144.38 at 400 px.
- Observable: the 18 keys `r{r}.mean.{R,G,B}` of the image-plane family (`s200`, `s400`, `s800`). Each is computed twice:
  with the scaled erosion e(s), and with 004's fixed 4-px erosion at every size.
- Decision: no p-values; a comparison of effect sizes. H5 is supported iff, for every one of the 18 keys and both
  adjacent pairs (200, 400) and (400, 800), `|rel_diff|` with the scaled erosion is smaller than with the fixed
  erosion. It is refuted otherwise, and the keys where it fails are listed.

## Method

### Configurations

| name | size | chain | jitter (image-plane) | jitter (px) | block (seeds) | source |
|---|---|---|---|---|---|---|
| `s200` | 200 | image | 1/700 | 1/7 | 28 (448-463) | 004 `s200` (cache) |
| `s400` | 400 | image | 1/700 | 2/7 | 0 (0-15) | 001 `img64`, 004 `s400` (cache) |
| `s800` | 800 | image | 1/700 | 4/7 | 29 (464-479) | 004 `s800` (cache) |
| `s200_px` | 200 | image | 1/350 | 2/7 | 33 (528-543) | new |
| `s800_px` | 800 | image | 1/1400 | 2/7 | 30 (480-495) | 004 `s800_j1400` (cache) |
| `row_s200` | 200 | row | 1/700 | 1/7 | 31 (496-511) | 004 `row_s200` (cache) |
| `row_s400` | 400 | row | 1/700 | 2/7 | 27 (432-447) | 003 `row`, 004 `row_s400` (cache) |
| `row_s800` | 800 | row | 1/700 | 4/7 | 32 (512-527) | 004 `row_s800` (cache) |
| `row_s200_px` | 200 | row | 1/350 | 2/7 | 34 (544-559) | new |
| `row_s800_px` | 800 | row | 1/1400 | 2/7 | 35 (560-575) | new |
| `j0_s200` | 200 | image | 0 | 0 | 36 (576-591) | new |
| `j0_s400` | 400 | image | 0 | 0 | 37 (592-607) | new |
| `j0_s800` | 800 | image | 0 | 0 | 38 (608-623) | new |

- New renders: 96 (16 per new configuration). Estimated oracle time from the cache's `wall_seconds`: 200 px ≈ 6 s,
  400 px ≈ 37 s, 800 px ≈ 98 s per render, so about 4,000 s of CPU in total.
- A reused configuration must have exactly the cached option set. `jobs.py` passes jitter only where it differs from the
  oracle default 1/700, as 004 does, so the cache keys are identical. `analyze.py`'s design check verifies this against
  004's `jobs.py` and fails otherwise.

### Commands

```
make oracle
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python -m painterly_analysis.experiment run experiments/006-2026-10-09-jitter-units/jobs.py --budget 540   # repeat until exit 0
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/006-2026-10-09-jitter-units/analyze.py
```

`analyze.py --pairs 2 --scale 4` with a scratch `PAINTERLY_CACHE` is the smoke run (sizes 50, 100, 200; lag and
erosion then use `s/200` and `4·s/400` with the scaled `s`, so at smoke scale they are not integers). The smoke run is
only a code check. It rounds τ and e to the nearest integer ≥ 1 and says so in its output. It never writes the
committed outputs.

### Analysis

- `analysis/painterly_analysis/metrics.py` gains `gaussian_highpass(x, sigma)` (as defined above) and
  `noise_corrected_lag(hp_a, hp_b, mask, axis, lag)`. The second generalizes 004's `_noise_corrected_lag1`, and
  `lag=1` reproduces it exactly. Both get unit tests:
  - a constant field has zero high-pass;
  - the Gaussian transfer at f = 0 is 1;
  - a pure sinusoid of frequency f passes with gain `1 − exp(−2π²σ²f²)`;
  - `noise_corrected_lag(x, x, mask, axis, lag)` equals the masked lag-τ autocorrelation of x computed directly, up to
    float64 round-off. With identical halves the estimator reduces to the plain autocorrelation.
- **Design check**: blocks, options and seeds as in the table, with every reused option set equal to 004's.
- **Outputs**:
  - `results.json`: every comparison's effect summary, p-values, Holm decisions and min_attainable_p; Δ_u per unit and
    chain with bootstrap intervals; the decision table.
  - `fig_grid.png`: pair 0 of each configuration, box-downsampled for display only to 200 px per tile, in the layout
    image family / pixel family / row image-plane / row pixel / zero family.
  - `fig_slag_profile.png`: the structure autocorrelation `slag` against image-plane lag (1/200, 2/200 and 3/200 of the
    side) per family and chain, for region r4 (the back wall), means ± sd over pairs.

### Amendments before analysis (Opus, 2026-10-09)

The T1.13 smoke run found a design defect in H4 before any full-scale analysis. The milestone reviewer then ran the
original design once at full scale, exploratorily. These amendments were written after that run:
- they do not change the rules or verdicts of H1, H2, H3 or H5;
- H4's replacement family below had not been rendered when they were written.

1. **H4 is decided on a row-chain zero family.**
   - With `chain=image` and `u2=same`, the seed enters a render only through the jitter (SPEC §2, `PURPOSE_JITTER_*`;
     the image chain starts at K = 0). With jitter 0, every seed therefore renders the same image. The reviewer's run
     found 1 distinct render among 16 for each `j0_*` configuration.
   - The two halves of a pair are then identical, so `cov₀` is the plain variance and no noise is separated. Every
     permutation test also reaches its floor, so H4 as registered is not interpretable.
   - H4 uses three new configurations instead: `row_j0_s200`, `row_j0_s400` and `row_j0_s800` (`chain=row`, `jitter=0`,
     blocks 39, 40 and 41, seeds 624-671).
     - The row chain's `K0 = rng_u32(seed, PURPOSE_LANE_K0, 0, row, 0, pass) mod 2^22` (SPEC §3) makes replicates
       independent with no jitter.
     - Comparisons and rule as registered: (200, 400), (400, 800) and (200, 800) on T, each at 0.01/3.
   - The image-chain `j0_*` family stays in the design, estimation only. Report its number of distinct renders, and the
     metrics of its single deterministic render at each size with no noise correction.
   - Estimation only, no verdict: `row_j0_sN` vs `row_sN` at each size, i.e. the effect of the jitter footprint at a fixed
     chain and size.
   - A consequence for reading H1-image and H2-image, and every image-chain ensemble in 001-004: their seed-to-seed
     "noise" is entirely the variation between jitter realizations. Their "structure" is the part of the texture that all
     jitter realizations share.
2. **Figures.** The 5 × 3 grid at 200 px per tile is 1.49 MB, over the 1 MB limit. It becomes one file per family row, three
   200 px tiles each:
   - `fig_grid_image_plane.png`
   - `fig_grid_pixel.png`
   - `fig_grid_row_image_plane.png`
   - `fig_grid_row_pixel.png`
   - `fig_grid_zero.png` (image-chain `j0_*`)
   - `fig_grid_row_zero.png`
   The layout is recorded in `results.json`.
3. **Smoke runs.** At `--scale > 1`, every decision line printed is prefixed `SMOKE (code check only): `, and `results.json`
   holds `"smoke": true`.
4. **Added estimation, decisions unchanged.**
   - Every comparison also reports `largest_abs_rel_diff_texture` and `largest_abs_cohen_d_texture` over the 18 T keys
     only, because near-zero spectral slopes dominate the all-key maxima.
   - H3 also reports Δ_u by key class (`structure_std` keys only and `slag` keys only), as `delta_by_class`.
5. **Wording.** `σ(s₀) = 9/√12 = 2.598 px` is the standard deviation of a *continuous* 9-px box. A discrete 9-tap box has
   2.582 px. The definition `σ(s) = (9/√12)·s/s₀` stands as registered.

| name | size | chain | jitter (image-plane) | block (seeds) | source |
|---|---|---|---|---|---|
| `row_j0_s200` | 200 | row | 0 | 39 (624-639) | new (amendment 1) |
| `row_j0_s400` | 400 | row | 0 | 40 (640-655) | new (amendment 1) |
| `row_j0_s800` | 800 | row | 0 | 41 (656-671) | new (amendment 1) |

## Results

Source: `results.json`, written by `analyze.py` from the 256 cached renders of `jobs.py`: 16 configurations, 8 pairs each,
P = 64 passes, full scale (`"smoke": false`). A second run into a scratch `--out-dir` reproduces all eight outputs
(`results.json` and the seven figures) byte for byte (`cmp`).

Conventions and notes:
- Means ± sd are over the 8 pairs (sample sd, ddof 1). The texture family T has 18 keys: `r{r}.structure_std`,
  `r{r}.slag.x` and `r{r}.slag.y` for the six measured regions 2 to 7. Region 8 is empty after erosion at every side
  (`regions.absent`).
- For a comparison "a vs b": `rel. diff` = (mean a − mean b)/|mean b|, `abs. diff` = mean a − mean b, and Cohen's d =
  (mean a − mean b)/pooled sd (`ensemble.effect_summary`).
- σ is the standard deviation of a continuous 9-px box (the discrete 9-tap box has 2.582 px). At 400 px it is the
  reference σ = 2.598 px.
- Near-zero means: a relative difference is not a meaningful effect size for a key whose mean is near zero. Examples at
  400 px: `r6.slag.x` = 0.0101 ± 0.0297 (Table 1), and `r2.spectral_slope` = −0.0606 ± 0.0491 (`summary` in `results.json`). Wherever a
  relative difference is reported (Tables 2 to 4), the absolute difference is reported beside it.
- Table 1, zero-jitter image-chain columns: sd is 0.0000 because all 16 renders of each are one render (Table 7). Those
  columns are not replicates and no verdict uses them.
- Decisions follow the README: exact two-sided permutation tests, Holm across the 18 keys of each comparison, and α per
  comparison as registered (Table 2).


**Table 0. Scale-equivariant parameters per side (`parameters`, `regions`)**

| side (px) | σ of the Gaussian high-pass (px) | erosion e(s) (px) | structure lag τ(s) (px) | profile lags k·s/200 (px) |
|---:|---:|---:|---:|---|
| 200 | 1.2990 | 2 | 1 | 1, 2, 3 |
| 400 | 2.5981 | 4 | 2 | 2, 4, 6 |
| 800 | 5.1962 | 8 | 4 | 4, 8, 12 |

Measured regions: [2, 3, 4, 5, 6, 7]; absent from the object-id map: [8]; dropped: []. Fixed erosion (H5 control): 4 px at every side. Spectral band: f_min = 2, f_max = 50 cycles per image.

**Table 1 (image chain). Texture keys, mean ± sd over 8 pairs**

| key | s200 | s200_px | s400 | s800 | s800_px | j0_s200 | j0_s400 | j0_s800 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| r2.structure_std | 4.8538 ± 0.3404 | 3.9968 ± 0.2391 | 4.7705 ± 0.1767 | 4.6738 ± 0.0731 | 5.2461 ± 0.0845 | 10.0079 ± 0.0000 | 10.5206 ± 0.0000 | 10.9097 ± 0.0000 |
| r2.slag.x | 0.1153 ± 0.1393 | 0.2895 ± 0.1389 | 0.1347 ± 0.0664 | 0.1487 ± 0.0269 | 0.1231 ± 0.0254 | -0.0233 ± 0.0000 | 0.0016 ± 0.0000 | 0.0142 ± 0.0000 |
| r2.slag.y | 0.0377 ± 0.1298 | 0.0665 ± 0.1012 | 0.0921 ± 0.0699 | 0.1059 ± 0.0205 | 0.0855 ± 0.0279 | -0.0707 ± 0.0000 | -0.0121 ± 0.0000 | 0.0096 ± 0.0000 |
| r3.structure_std | 6.0151 ± 0.0997 | 5.4284 ± 0.2160 | 6.4925 ± 0.1182 | 6.4945 ± 0.0338 | 7.0576 ± 0.0531 | 13.1157 ± 0.0000 | 13.8243 ± 0.0000 | 14.3714 ± 0.0000 |
| r3.slag.x | 0.5248 ± 0.0756 | 0.6427 ± 0.0703 | 0.5674 ± 0.0225 | 0.5597 ± 0.0110 | 0.4882 ± 0.0139 | 0.0324 ± 0.0000 | 0.0678 ± 0.0000 | 0.1098 ± 0.0000 |
| r3.slag.y | 0.0873 ± 0.0384 | 0.2073 ± 0.0794 | 0.0377 ± 0.0204 | 0.0438 ± 0.0063 | 0.0247 ± 0.0163 | -0.0686 ± 0.0000 | -0.0034 ± 0.0000 | 0.0010 ± 0.0000 |
| r4.structure_std | 5.3600 ± 0.0873 | 4.6651 ± 0.1396 | 5.3556 ± 0.0677 | 5.2599 ± 0.0262 | 5.8029 ± 0.0187 | 11.2356 ± 0.0000 | 11.7444 ± 0.0000 | 12.1687 ± 0.0000 |
| r4.slag.x | 0.1132 ± 0.0472 | 0.2175 ± 0.0486 | 0.1893 ± 0.0159 | 0.2056 ± 0.0117 | 0.1672 ± 0.0099 | -0.0722 ± 0.0000 | 0.0117 ± 0.0000 | 0.0334 ± 0.0000 |
| r4.slag.y | 0.2408 ± 0.0538 | 0.3257 ± 0.0301 | 0.2551 ± 0.0184 | 0.2556 ± 0.0085 | 0.2059 ± 0.0111 | -0.0487 ± 0.0000 | 0.0330 ± 0.0000 | 0.0391 ± 0.0000 |
| r5.structure_std | 3.3156 ± 0.1050 | 2.9200 ± 0.1091 | 3.3203 ± 0.0758 | 3.3305 ± 0.0191 | 3.6764 ± 0.0331 | 8.3317 ± 0.0000 | 8.7335 ± 0.0000 | 8.9859 ± 0.0000 |
| r5.slag.x | 0.0388 ± 0.0708 | 0.0649 ± 0.1182 | 0.0406 ± 0.0667 | 0.0288 ± 0.0248 | 0.0106 ± 0.0117 | -0.0565 ± 0.0000 | -0.0312 ± 0.0000 | -0.0060 ± 0.0000 |
| r5.slag.y | 0.3140 ± 0.0681 | 0.3864 ± 0.1032 | 0.2787 ± 0.0389 | 0.2687 ± 0.0202 | 0.2112 ± 0.0168 | -0.0773 ± 0.0000 | 0.0194 ± 0.0000 | 0.0268 ± 0.0000 |
| r6.structure_std | 6.5893 ± 0.1412 | 5.6291 ± 0.1011 | 6.7271 ± 0.1120 | 6.6667 ± 0.0828 | 7.3109 ± 0.0491 | 15.6174 ± 0.0000 | 16.4122 ± 0.0000 | 16.9009 ± 0.0000 |
| r6.slag.x | 0.0047 ± 0.0540 | 0.0938 ± 0.1032 | 0.0101 ± 0.0297 | -0.0083 ± 0.0146 | -0.0070 ± 0.0182 | -0.0749 ± 0.0000 | -0.0296 ± 0.0000 | -0.0086 ± 0.0000 |
| r6.slag.y | 0.3673 ± 0.0439 | 0.4636 ± 0.0487 | 0.4010 ± 0.0337 | 0.3853 ± 0.0216 | 0.3302 ± 0.0158 | -0.0362 ± 0.0000 | 0.0426 ± 0.0000 | 0.0560 ± 0.0000 |
| r7.structure_std | 5.2467 ± 0.1339 | 4.5188 ± 0.2836 | 5.2320 ± 0.1137 | 5.1274 ± 0.0427 | 5.7625 ± 0.0323 | 13.1133 ± 0.0000 | 13.7189 ± 0.0000 | 13.8283 ± 0.0000 |
| r7.slag.x | 0.0841 ± 0.0790 | 0.2121 ± 0.1262 | 0.1483 ± 0.0381 | 0.1875 ± 0.0267 | 0.1352 ± 0.0171 | -0.0833 ± 0.0000 | -0.0161 ± 0.0000 | 0.0132 ± 0.0000 |
| r7.slag.y | 0.0060 ± 0.0823 | 0.1750 ± 0.0955 | 0.0891 ± 0.0344 | 0.0848 ± 0.0181 | 0.0585 ± 0.0240 | -0.0894 ± 0.0000 | 0.0002 ± 0.0000 | 0.0031 ± 0.0000 |

**Table 1 (row chain). Texture keys, mean ± sd over 8 pairs**

| key | row_s200 | row_s200_px | row_s400 | row_s800 | row_s800_px | row_j0_s200 | row_j0_s400 | row_j0_s800 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| r2.structure_std | 4.6068 ± 0.2869 | 4.0327 ± 0.3862 | 4.7529 ± 0.1104 | 4.6984 ± 0.0925 | 5.2330 ± 0.0484 | 6.6361 ± 0.2080 | 6.5329 ± 0.1192 | 6.6721 ± 0.0558 |
| r2.slag.x | 0.1987 ± 0.1366 | 0.1311 ± 0.1079 | 0.1967 ± 0.0759 | 0.1575 ± 0.0302 | 0.1137 ± 0.0264 | 0.0049 ± 0.0464 | 0.0876 ± 0.0475 | 0.0732 ± 0.0196 |
| r2.slag.y | 0.1419 ± 0.1538 | 0.0591 ± 0.1088 | 0.0587 ± 0.0319 | 0.1064 ± 0.0413 | 0.0967 ± 0.0236 | -0.1382 ± 0.0330 | 0.0334 ± 0.0283 | 0.0450 ± 0.0119 |
| r3.structure_std | 6.1787 ± 0.2243 | 5.5896 ± 0.1154 | 6.4828 ± 0.0370 | 6.5110 ± 0.0424 | 7.0131 ± 0.0414 | 7.5687 ± 0.1279 | 8.3539 ± 0.0808 | 8.5070 ± 0.0486 |
| r3.slag.x | 0.4895 ± 0.0468 | 0.6419 ± 0.0735 | 0.5515 ± 0.0275 | 0.5657 ± 0.0111 | 0.4909 ± 0.0144 | 0.2974 ± 0.0351 | 0.3194 ± 0.0196 | 0.3427 ± 0.0057 |
| r3.slag.y | 0.0884 ± 0.0561 | 0.1317 ± 0.0597 | 0.0454 ± 0.0259 | 0.0273 ± 0.0176 | 0.0211 ± 0.0082 | -0.0016 ± 0.0242 | 0.0271 ± 0.0187 | 0.0171 ± 0.0068 |
| r4.structure_std | 5.3155 ± 0.0572 | 4.8421 ± 0.1211 | 5.3561 ± 0.0891 | 5.2840 ± 0.0433 | 5.7833 ± 0.0420 | 6.7878 ± 0.1602 | 7.1760 ± 0.0767 | 7.2730 ± 0.0266 |
| r4.slag.x | 0.1310 ± 0.0301 | 0.1834 ± 0.0700 | 0.1787 ± 0.0270 | 0.2047 ± 0.0149 | 0.1671 ± 0.0119 | 0.0407 ± 0.0315 | 0.0803 ± 0.0178 | 0.1001 ± 0.0065 |
| r4.slag.y | 0.2510 ± 0.0400 | 0.3363 ± 0.0427 | 0.2639 ± 0.0134 | 0.2483 ± 0.0082 | 0.2072 ± 0.0105 | 0.0942 ± 0.0346 | 0.1395 ± 0.0178 | 0.1302 ± 0.0096 |
| r5.structure_std | 3.1620 ± 0.0527 | 2.8945 ± 0.1435 | 3.2754 ± 0.0540 | 3.2898 ± 0.0360 | 3.6275 ± 0.0307 | 3.8348 ± 0.0883 | 4.2566 ± 0.0729 | 4.4032 ± 0.0245 |
| r5.slag.x | 0.0194 ± 0.0601 | 0.0869 ± 0.0747 | 0.0217 ± 0.0320 | 0.0296 ± 0.0183 | 0.0213 ± 0.0137 | -0.0083 ± 0.0597 | 0.0007 ± 0.0289 | 0.0082 ± 0.0112 |
| r5.slag.y | 0.2507 ± 0.0818 | 0.3344 ± 0.1453 | 0.2781 ± 0.0515 | 0.2795 ± 0.0097 | 0.2349 ± 0.0163 | 0.1604 ± 0.0436 | 0.1670 ± 0.0187 | 0.1585 ± 0.0085 |
| r6.structure_std | 6.4256 ± 0.1530 | 5.6615 ± 0.1674 | 6.6669 ± 0.1169 | 6.6410 ± 0.0189 | 7.3078 ± 0.0755 | 8.8815 ± 0.1063 | 9.4018 ± 0.0732 | 9.4969 ± 0.0413 |
| r6.slag.x | 0.0107 ± 0.0242 | 0.0825 ± 0.0900 | 0.0117 ± 0.0222 | 0.0052 ± 0.0171 | 0.0025 ± 0.0125 | -0.0029 ± 0.0372 | -0.0109 ± 0.0183 | 0.0011 ± 0.0143 |
| r6.slag.y | 0.3888 ± 0.0894 | 0.4957 ± 0.0912 | 0.3970 ± 0.0163 | 0.3799 ± 0.0110 | 0.3231 ± 0.0198 | 0.1302 ± 0.0296 | 0.1797 ± 0.0175 | 0.1899 ± 0.0082 |
| r7.structure_std | 5.1760 ± 0.2338 | 4.5220 ± 0.1677 | 5.1966 ± 0.1148 | 5.1647 ± 0.0668 | 5.7377 ± 0.0792 | 6.8727 ± 0.1302 | 7.1274 ± 0.1309 | 7.3371 ± 0.0605 |
| r7.slag.x | 0.1762 ± 0.1269 | 0.2618 ± 0.0646 | 0.1340 ± 0.0227 | 0.1632 ± 0.0220 | 0.1345 ± 0.0177 | -0.0023 ± 0.0483 | 0.0542 ± 0.0228 | 0.0772 ± 0.0141 |
| r7.slag.y | -0.0124 ± 0.0899 | 0.1447 ± 0.0770 | 0.0814 ± 0.0444 | 0.0773 ± 0.0217 | 0.0535 ± 0.0173 | -0.0115 ± 0.0728 | 0.0190 ± 0.0296 | 0.0311 ± 0.0111 |

**Table 2. Every comparison: Holm rejections of 18 texture keys and effect maxima**

| hypothesis | chain | comparison | α (per comparison) | rejected of 18 | min_attainable_p | first Holm threshold | largest \|rel\| texture (abs. diff) | largest \|d\| texture | largest \|rel\| all keys (abs. diff) | largest \|d\| all keys |
|---|---|---|---:|---:|---:|---:|---|---|---|---|
| H1 | image | s200 vs s400 | 0.003333 | 1 | 1.55e-04 | 1.85e-04 | r3.slag.y +1.314 (+0.04958) | r3.structure_std +4.365 | r7.spectral_slope +13.21 (+0.1863) | r4.spectral_slope +7.805 |
| H1 | image | s400 vs s800 | 0.003333 | 0 | 1.55e-04 | 1.85e-04 | r6.slag.x +2.217 (+0.01843) | r4.structure_std +1.865 | r6.slag.x +2.217 (+0.01843) | r4.mean.B +9.944 |
| H1 | image | s200 vs s800 | 0.003333 | 2 | 1.55e-04 | 1.85e-04 | r6.slag.x +1.563 (+0.01299) | r3.structure_std +6.439 | r7.spectral_slope +2.831 (+0.2662) | r4.spectral_slope +12.54 |
| H1 | row | row_s200 vs row_s400 | 0.003333 | 0 | 1.55e-04 | 1.85e-04 | r2.slag.y +1.417 (+0.08322) | r5.structure_std +2.124 | r2.spectral_slope +5.44 (+0.2363) | r4.spectral_slope +6.028 |
| H1 | row | row_s400 vs row_s800 | 0.003333 | 0 | 1.55e-04 | 1.85e-04 | r6.slag.x +1.27 (+0.006557) | r4.slag.y +1.399 | r6.slag.x +1.27 (+0.006557) | r4.mean.G +7.157 |
| H1 | row | row_s200 vs row_s800 | 0.003333 | 1 | 1.55e-04 | 1.85e-04 | r3.slag.y +2.242 (+0.06111) | r4.slag.x +3.106 | r7.spectral_slope +3.185 (+0.2763) | r4.spectral_slope +12.14 |
| H2 | image | s200_px vs s400 | 0.005 | 7 | 1.55e-04 | 2.78e-04 | r6.slag.x +8.269 (+0.08369) | r6.structure_std +10.29 | r7.spectral_slope +8.858 (+0.1249) | r6.structure_std +10.29 |
| H2 | image | s800_px vs s400 | 0.005 | 9 | 1.55e-04 | 2.78e-04 | r6.slag.x +1.689 (-0.01709) | r4.structure_std +9.006 | r7.spectral_slope +5.238 (-0.07384) | r4.structure_std +9.006 |
| H2 | row | row_s200_px vs row_s400 | 0.005 | 9 | 1.55e-04 | 2.78e-04 | r6.slag.x +6.041 (+0.07079) | r3.structure_std +10.42 | r6.slag.x +6.041 (+0.07079) | r3.structure_std +10.42 |
| H2 | row | row_s800_px vs row_s400 | 0.005 | 9 | 1.55e-04 | 2.78e-04 | r6.slag.x +0.7856 (-0.009206) | r3.structure_std +13.5 | r2.spectral_slope +1.805 (-0.07839) | r3.structure_std +13.5 |
| H4 | row | row_j0_s200 vs row_j0_s400 | 0.003333 | 5 | 1.55e-04 | 1.85e-04 | r5.slag.x +13.34 (-0.008989) | r3.structure_std +7.339 | r2.spectral_slope +32.77 (+0.2554) | r4.spectral_slope +8.995 |
| H4 | row | row_j0_s400 vs row_j0_s800 | 0.003333 | 0 | 1.55e-04 | 1.85e-04 | r6.slag.x +10.67 (-0.01205) | r5.structure_std +2.695 | r6.slag.x +10.67 (-0.01205) | r3.mean.R +8.73 |
| H4 | row | row_j0_s200 vs row_j0_s800 | 0.003333 | 7 | 1.55e-04 | 1.85e-04 | r2.slag.y +4.069 (-0.1833) | r3.structure_std +9.699 | r2.slag.y +4.069 (-0.1833) | r4.spectral_slope +14.22 |
| footprint | row | row_j0_s200 vs row_s200 | none (estimation) | none (estimation) | none | none | r2.slag.y +1.974 (-0.2802) | r6.structure_std +18.64 | r2.slag.y +1.974 (-0.2802) | r6.structure_std +18.64 |
| footprint | row | row_j0_s400 vs row_s400 | none (estimation) | none (estimation) | none | none | r6.slag.x +1.932 (-0.02264) | r3.structure_std +29.76 | r6.slag.x +1.932 (-0.02264) | r3.structure_std +29.76 |
| footprint | row | row_j0_s800 vs row_s800 | none (estimation) | none (estimation) | none | none | r6.slag.x +0.7813 (-0.004032) | r6.structure_std +88.98 | r6.slag.x +0.7813 (-0.004032) | r6.structure_std +88.98 |

**Table 3. Rejected keys of H1 (image plane and row), with the relative difference and p-value**

| hypothesis | comparison | key | rel. diff | abs. diff (a − b) | Cohen's d | p (exact permutation) | first Holm threshold | mean a ± sd | mean b ± sd |
|---|---|---|---:|---:|---:|---:|---:|---|---|
| H1-image | s200 vs s400 | r3.structure_std | -0.07354 | -0.4775 | -4.365 | 1.55e-04 | 1.85e-04 | 6.0151 ± 0.0997 | 6.4925 ± 0.1182 |
| H1-image | s200 vs s800 | r3.structure_std | -0.07383 | -0.4795 | -6.439 | 1.55e-04 | 1.85e-04 | 6.0151 ± 0.0997 | 6.4945 ± 0.0338 |
| H1-image | s200 vs s800 | r4.slag.x | -0.4494 | -0.0924 | -2.686 | 1.55e-04 | 1.85e-04 | 0.1132 ± 0.0472 | 0.2056 ± 0.0117 |
| H1-row | row_s200 vs row_s800 | r4.slag.x | -0.3601 | -0.07373 | -3.106 | 1.55e-04 | 1.85e-04 | 0.1310 ± 0.0301 | 0.2047 ± 0.0149 |

**Table 4. Rejected keys of H2 and H4 (relative difference, absolute difference a − b, p-value)**

| hypothesis | comparison | rejected of 18 | rejected keys: rel. diff; p |
|---|---|---:|---|
| H2-image | s200_px vs s400 | 7 | r2.structure_std (rel -0.1622; abs -0.7737; p 1.55e-04); r3.structure_std (rel -0.1639; abs -1.064; p 1.55e-04); r3.slag.y (rel +4.495; abs +0.1696; p 1.55e-04); r4.structure_std (rel -0.1289; abs -0.6906; p 1.55e-04); r5.structure_std (rel -0.1206; abs -0.4003; p 1.55e-04); r6.structure_std (rel -0.1632; abs -1.098; p 1.55e-04); r7.structure_std (rel -0.1363; abs -0.7133; p 1.55e-04) |
| H2-image | s800_px vs s400 | 9 | r2.structure_std (rel +0.09968; abs +0.4755; p 1.55e-04); r3.structure_std (rel +0.08703; abs +0.5651; p 1.55e-04); r3.slag.x (rel -0.1396; abs -0.0792; p 1.55e-04); r4.structure_std (rel +0.08351; abs +0.4472; p 1.55e-04); r4.slag.y (rel -0.1932; abs -0.04929; p 1.55e-04); r5.structure_std (rel +0.1072; abs +0.3561; p 1.55e-04); r6.structure_std (rel +0.08678; abs +0.5837; p 1.55e-04); r6.slag.y (rel -0.1766; abs -0.07083; p 3.11e-04); r7.structure_std (rel +0.1014; abs +0.5305; p 1.55e-04) |
| H2-row | row_s200_px vs row_s400 | 9 | r2.structure_std (rel -0.1515; abs -0.7202; p 1.55e-04); r3.structure_std (rel -0.1378; abs -0.8931; p 1.55e-04); r3.slag.y (rel +1.902; abs +0.08629; p 1.55e-04); r4.structure_std (rel -0.09597; abs -0.514; p 1.55e-04); r4.slag.y (rel +0.2743; abs +0.07239; p 4.66e-04); r5.structure_std (rel -0.1163; abs -0.3809; p 1.55e-04); r6.structure_std (rel -0.1508; abs -1.005; p 1.55e-04); r7.structure_std (rel -0.1298; abs -0.6746; p 1.55e-04); r7.slag.x (rel +0.9538; abs +0.1278; p 1.55e-04) |
| H2-row | row_s800_px vs row_s400 | 9 | r2.structure_std (rel +0.101; abs +0.48; p 1.55e-04); r3.structure_std (rel +0.08181; abs +0.5304; p 1.55e-04); r3.slag.x (rel -0.1098; abs -0.06057; p 3.11e-04); r4.structure_std (rel +0.07976; abs +0.4272; p 1.55e-04); r4.slag.y (rel -0.2147; abs -0.05667; p 1.55e-04); r5.structure_std (rel +0.1075; abs +0.3521; p 1.55e-04); r6.structure_std (rel +0.09613; abs +0.6409; p 1.55e-04); r6.slag.y (rel -0.1862; abs -0.07392; p 1.55e-04); r7.structure_std (rel +0.1041; abs +0.5411; p 1.55e-04) |
| H4-row | row_j0_s200 vs row_j0_s400 | 5 | r2.slag.y (rel -5.136; abs -0.1716; p 1.55e-04); r3.structure_std (rel -0.094; abs -0.7853; p 1.55e-04); r4.structure_std (rel -0.0541; abs -0.3882; p 1.55e-04); r5.structure_std (rel -0.09908; abs -0.4217; p 1.55e-04); r6.structure_std (rel -0.05535; abs -0.5203; p 1.55e-04) |
| H4-row | row_j0_s400 vs row_j0_s800 | 0 | none |
| H4-row | row_j0_s200 vs row_j0_s800 | 7 | r2.slag.y (rel -4.069; abs -0.1833; p 1.55e-04); r3.structure_std (rel -0.1103; abs -0.9383; p 1.55e-04); r4.structure_std (rel -0.06671; abs -0.4852; p 1.55e-04); r5.structure_std (rel -0.1291; abs -0.5684; p 1.55e-04); r6.structure_std (rel -0.0648; abs -0.6154; p 1.55e-04); r6.slag.y (rel -0.314; abs -0.05962; p 1.55e-04); r7.structure_std (rel -0.0633; abs -0.4645; p 1.55e-04) |

**Table 5. H3: Δ_u per unit and chain (median over 18 texture keys × 2 pairs of |rel. diff|), 95% percentile bootstrap intervals**

| chain | unit | Δ_u | 95% CI | per-pair median \|rel\| | Δ by class: structure_std | Δ by class: slag |
|---|---|---:|---|---|---:|---:|
| image | image-plane | 0.0648 | [0.0378, 0.0967] | s200 vs s400: 0.0795; s400 vs s800: 0.0389 | 0.0133 | 0.1284 |
| image | pixel | 0.1627 | [0.1532, 0.2156] | s200_px vs s400: 0.2202; s400 vs s800_px: 0.1143 | 0.1087 | 0.2986 |
| row | image-plane | 0.0513 | [0.0460, 0.1127] | row_s200 vs row_s400: 0.0700; row_s400 vs row_s800: 0.0494 | 0.0096 | 0.1199 |
| row | pixel | 0.1578 | [0.1412, 0.2281] | row_s200_px vs row_s400: 0.1831; row_s400 vs row_s800_px: 0.1102 | 0.0965 | 0.2739 |

| chain | difference pixel − image-plane | 95% CI | CI excludes 0 | bootstrap fraction > 0 | H3 decision |
|---|---:|---|---|---:|---|
| image | 0.0979 | [0.0703, 0.1560] | True | 1.0 | no decision (image chain) |
| row | 0.1064 | [0.0489, 0.1632] | True | 1.0 | supported |

**Table 6. H5: |rel. diff| of the region-mean keys, scaled erosion e(s) vs fixed 4-px erosion**

| key | 200 vs 400 scaled | 200 vs 400 fixed | 400 vs 800 scaled | 400 vs 800 fixed |
|---|---:|---:|---:|---:|
| r2.mean.B | 0.002961 | 0.01286 | 0.0008662 | 0.0123 |
| r2.mean.G | 0.002643 | 0.01502 | 0.001193 | 0.0137 |
| r2.mean.R | 0.001222 | 0.06473 | 0.000462 | 0.02748 |
| r3.mean.B | 8.752e-05 | 0.06875 | 0.001201 | 0.02623 |
| r3.mean.G | 0.001295 | 0.05407 | 0.000919 | 0.02125 |
| r3.mean.R | 0.001859 | 0.03933 | 0.001879 | 0.0118 |
| r4.mean.B | 0.0005237 | 0.04296 | 0.001609 | 0.02366 |
| r4.mean.G | 0.0001992 | 0.03535 | 0.0009486 | 0.01955 |
| r4.mean.R | 0.001639 | 0.02401 | 0.0004071 | 0.01435 |
| r5.mean.B | 0.0004267 | 0.01096 | 0.001321 | 0.007098 |
| r5.mean.G | 8.143e-05 | 0.02126 | 0.001408 | 0.0116 |
| r5.mean.R | 5.222e-05 | 0.00214 | 0.001257 (fails) | 0.000829 |
| r6.mean.B | 0.0004359 | 0.02651 | 0.001363 | 0.01278 |
| r6.mean.G | 0.0006543 | 0.01949 | 0.001283 | 0.0101 |
| r6.mean.R | 0.0001064 | 0.02872 | 0.0003601 | 0.01193 |
| r7.mean.B | 0.0001605 | 0.01577 | 0.0005019 | 0.0105 |
| r7.mean.G | 0.0002656 | 0.0112 | 0.0002166 | 0.009516 |
| r7.mean.R | 0.0007339 | 0.00744 | 0.0003593 | 0.002772 |

H5 rows where the scaled |rel. diff| is smaller: 35 of 36

**Table 7. Distinct renders among the 16 renders of each configuration (sum.npy equality)**

| configuration | distinct renders | renders |
|---|---:|---:|
| s200 | 16 | 16 |
| s200_px | 16 | 16 |
| s400 | 16 | 16 |
| s800 | 16 | 16 |
| s800_px | 16 | 16 |
| row_s200 | 16 | 16 |
| row_s200_px | 16 | 16 |
| row_s400 | 16 | 16 |
| row_s800 | 16 | 16 |
| row_s800_px | 16 | 16 |
| j0_s200 | 1 | 16 |
| j0_s400 | 1 | 16 |
| j0_s800 | 1 | 16 |
| row_j0_s200 | 16 | 16 |
| row_j0_s400 | 16 | 16 |
| row_j0_s800 | 16 | 16 |

Figures (each ≤ 1 MB; the figures draw no text, and their encodings are recorded in `results.json` under `figures`):
- `fig_grid_image_plane.png` (297,996 bytes), `fig_grid_pixel.png` (297,893), `fig_grid_row_image_plane.png` (298,080),
  `fig_grid_row_pixel.png` (297,606), `fig_grid_zero.png` (303,285), `fig_grid_row_zero.png` (299,275). Each has three
  200-px tiles, pair 0 of the configurations of its row, in the order 200, 400, 800 px.
- `fig_slag_profile.png` (8,757 bytes): the region-4 structure autocorrelation `slag` against image-plane lag k/200 of the
  side (k = 1, 2, 3), mean ± sd over the pairs, for `slag.x` (top row) and `slag.y` (bottom row).

## Conclusion

Final (Opus, 2026-10-09). The Haiku draft is superseded. The numbers are those in Results. Ranges marked "(Table 1)" are
computed from its means.

**The converged texture lives on the image plane, so jitter must be defined there too. With image-plane jitter, 400 and
800 px are indistinguishable on all 18 texture keys in both chains. Jitter fixed in pixels changes 9 of 18 between the
same sizes. Every departure from resolution independence involves the 200 px renders.**

**Verdicts**
- **H1 refuted as registered** (image chain 1, 0 and 2 of 18 keys; row chain 0, 0 and 1). **Every rejection involves 200 px.**
  - (400, 800) rejects 0 of 18 in both chains.
    - The smallest p is 0.00264 (image, `r4.structure_std`) and 0.0124 (row), against a first Holm threshold of 1.85e-4.
    - The six `structure_std` keys differ by −0.0030 to +0.0207 (image) and −0.0044 to +0.0137 (row) (Table 1).
    - The largest |d| on T is 1.87 (image) and 1.40 (row).
  - The rejected keys are:
    - the floor's amplitude at 200 px, image chain: `r3.structure_std` rel −0.0735 vs 400 px and −0.0738 vs 800 px,
      d −4.37 and −6.44;
    - the back wall's along-row autocorrelation, 200 vs 800 px: `r4.slag.x` abs −0.0924 (image) and −0.0737 (row). The
      relative values, −0.449 and −0.360, are fractions of a small autocorrelation (0.21 at 800 px).
  - Every key rejected at (200, 400) is rejected again at (200, 800).
  - How to read a rejection. With three comparisons, the first Holm threshold (1.85e-4) admits only the smallest attainable
    p (1.55e-4). A key is therefore rejected only when all 8 pairs at one size lie beyond all 8 at the other. The test
    flags any consistent shift, however small, and the effect sizes say how large it is.
  - The one key still trending between 400 and 800 px is `r4.slag.x`: +0.026 (row), +0.016 (image) and +0.020 (zero
    jitter), none rejected. From 200 to 400 px the steps were +0.048, +0.076 and +0.040, so each doubling shrinks the
    step by a factor of 1.8 to 4.6 (Table 1).
- **H2 supported** (image 7 and 9 of 18, row 9 and 9).
  - The deciding contrast is at 800 px, which is free of the 200 px issue.
    - Jitter fixed in pixels is 1/2800 of the side there. Against 400 px, every `structure_std` key rises by +0.0798 to
      +0.1075 (row; image +0.0835 to +0.1072), and 9 of 18 keys reject in both chains.
    - With image-plane jitter, the same size pair rejects 0.
  - At 200 px, pixel jitter is 1/700 of the side and lowers `structure_std` by 0.0960 to 0.1515 (row).
- **H3 supported** (the decision statistic, row chain).
  - Δ_image-plane = 0.0513 [0.0460, 0.1127] and Δ_pixel = 0.1578 [0.1412, 0.2281].
  - The difference is 0.1064 [0.0489, 0.1632]: it excludes 0, and its bootstrap fraction above 0 is 1.0.
  - By key class: amplitude alone 0.0096 vs 0.0965; autocorrelation 0.1199 vs 0.2739.
  - Image chain (no decision): 0.0648 vs 0.1627, difference 0.0979 [0.0703, 0.1560].
  - Key by key, image-plane jitter gives the smaller |rel| in 29 of 36 key × size-pair cells for the row chain (image
    chain 30 of 36), including all 12 `structure_std` cells.
    - `r4.slag.x` is the exception in both row size pairs. The pixel-unit footprint is larger at 200 px and smaller at
      800 px, so it moves this key against its rise with size: 0.1834 vs 0.1310 at 200 px, and 0.1671 vs 0.2047 at 800 px.
  - The percentile intervals of a median of |rel| are skewed upward: resampling adds noise to every difference before the
    absolute value is taken. That does not affect the sign of the difference.
- **H4 refuted as registered** (row chain, zero jitter: 5, 0 and 7 of 18), **but not for the registered reason.**
  - The registered reading of a refutation was "the jitter footprint is needed for image-locking". The rejections do not
    show that. They have H1's signature: all 12 involve 200 px.
  - (400, 800) rejects 0 of 18: smallest p 9.32e-4, largest |d| 2.69. Without a footprint, 400 and 800 px are still
    indistinguishable.
  - What zero jitter changes about the size dependence:
    - **A larger 200 px departure.** It has 12 rejections, against 1 for the jittered row family. `structure_std` at
      200 vs 400 px is −0.0357 to −0.0991 in five regions, against −0.0040 to −0.0469 with jitter (Table 1).
    - **A small amplitude drift between 400 and 800 px.** `structure_std` is lower at 400 px in all six regions (rel −0.0100
      to −0.0333), none rejected. The drift shrinks with size: `r4.structure_std` goes 6.788 → 7.176 → 7.273 (+0.388, then
      +0.097). The step ratio is 4.0 to 5.5 in r3, r4 and r6.
  - The footprint's own effect is large at every size (footprint rows of Table 2, and Table 1).
    - Removing it raises `structure_std` by +0.213 to +0.440 (d 7.6 to 89.0). The 1/1400 footprint therefore removes 32-52%
      of the structure variance.
    - It also lowers the short-lag autocorrelation. At 400 px, `r4.structure_std` is 7.176 ± 0.077 vs 5.356 ± 0.089,
      `r4.slag.x` 0.080 vs 0.179 and `r6.slag.y` 0.180 vs 0.397.
- **H5 refuted as registered, by one row of 36. The erosion still explains 004's trend.**
  - Every region-mean key agrees within |rel| 0.0030 across sizes with e(s) ∝ s (largest `r2.mean.B`, (200, 400)). With
    004's fixed 4 px erosion, |rel| reaches 0.0688 (`r3.mean.B`).
  - The failing row is `r5.mean.R` (red wall, red channel) at (400, 800).
    - Scaled 0.00126 vs fixed 0.00083: 0.19 vs 0.13 grey levels on a mean of 151 (d 2.60 vs 1.74).
    - The fixed value is the smallest of all 36 fixed values (the next is 0.00214). This key has no erosion trend to
      remove, so the rule compared two residuals of under a fifth of a grey level. It is not evidence against the erosion
      explanation.
  - A real residual remains with the scaled erosion, up to |d| 9.94 between 400 and 800 px (`r4.mean.B`). It is a rel
    difference of 0.0016.
- **Estimation.**
  - The image chain with zero jitter is one deterministic render per size (1 distinct render of 16, Table 7). That chain
    takes its seed only through the jitter, so it has no noise to separate and gets no verdict.
  - With jitter, the image and row chains have the same structure amplitude at 400 px (`r4.structure_std` 5.3556 vs
    5.3561), consistent with 003's row ≈ image.

**What they mean together**
1. **The image plane sets the stroke scale, not the K stride.**
   - The K stream advances once per pixel, so going from 400 to 800 px doubles the K steps per unit of image.
   - If the K stride set the stroke scale, the autocorrelation at a fixed fraction of the side would fall when the side
     doubles. It does not: between 400 and 800 px, 0 of 18 keys change in all three families.
   - With a fixed camera, image-plane locking and scene locking are the same thing. This experiment does not separate them.
2. **The jitter footprint shapes the texture but does not lock it.**
   - The footprint averages each pixel's paths over an image-plane square of half-width jitter × side. It lowers the
     amplitude and raises the short-range correlation, so the strokes get softer.
   - Its effect (d up to 89) is far larger than anything resolution does between 400 and 800 px.
   - A footprint fixed in pixels is a different softening at every size (H2). A footprint fixed on the image plane is the
     same softening at every size (H3).
   - A sub-pixel footprint (±2/7 px at 400 px) removes 44% of the back wall's structure variance. So either most of the
     zero-jitter texture sits at sub-pixel scales, or jitter also acts through the chain, since moved hit points change K
     consumption. This experiment cannot tell which (hypotheses below).
3. **200 px is too coarse for this scene.**
   - All 16 rejections in H1 and H4 involve 200 px.
     - With jitter (H1), the keys concerned belong to the floor and the back wall. The back wall is the farthest surface
       and the floor is foreshortened, so their texture should be the finest on the image plane.
     - Without jitter (H4), the departure is larger and reaches the amplitude of up to five of the six regions. The
       zero-jitter amplitude also converges with size.
   - Both observations fit undersampling. At 200 px the pixel pitch equals the lag, so the grid is coarse for sub-pixel
     texture, and the footprint removes some of that detail before it is sampled. This is a hypothesis, tested below.
4. **What is covered.**
   - Every texture key is noise-corrected. It measures the part of the texture that independent seeds share, i.e. the
     converged look.
   - The seed-dependent part was removed by design and was not tested. 001 found that part dominates the visible texture
     at low pass counts.

**Decisions**
1. **SPEC §7 is confirmed.**
   - Jitter is a fraction of the camera's fitted image side, default 1/1400. That is smallpaint's 1/700 image-plane units,
     2/7 px at 400 px.
   - The deciding numbers are H3 (row Δ 0.0513 vs 0.1578, difference interval [0.0489, 0.1632]) and the 800 px contrast
     (0 of 18 keys with image-plane jitter vs 9 of 18 with pixel jitter, in both chains).
   - One passage of §7 is replaced. It reads "Neither unit is exactly invariant (006 H1). The back wall's along-row
     structure lag differs by up to 36-45% between 200 and 800 px." It becomes: "With image-plane jitter, 400 and 800 px
     are indistinguishable (0 of 18 texture keys, both chains). Departures appear only against 200 px: the floor's
     amplitude (up to −7%) and the back wall's along-row autocorrelation (−0.07 to −0.09)."
   - Always name the unit. In SPEC §7, "1/1400" is a fraction of the side. 004's `s800_j1400` and 006's `s800_px` use
     1/1400 *image-plane units*, which is 1/2800 of the side. The oracle's `--jitter` stays in image-plane units
     (SPEC §7, `2·jitter`).
2. **Jitter is documented as an artist knob for stroke softness (M7).**
   - Measured points, row chain, `r4.structure_std`:
     - 7.273, 5.783 and 5.284 at 800 px, for 0, 1/2800 and 1/1400 of the side;
     - 6.788, 5.316 and 4.842 at 200 px, for 0, 1/1400 and 1/700.
   - Most of the change is near 0. At 800 px, the first 1/2800 of the side gives 75% of the drop to 1/1400.
   - Resolution independence holds at both jitter values tested between 400 and 800 px (0 and 1/1400). Changing the knob
     changes the look without making it depend on size.
   - The dose-response experiment below sets the knob's range and scale, not this one.
   - Two cautions go into the knob's description:
     - with `chain=image`, jitter 0 makes `seed` irrelevant (Table 7);
     - the region masks are eroded away from edges, so these metrics say nothing about edge aliasing at small jitter.
3. **Cross-resolution acceptance** (M3 on) uses scale-equivariant metrics, with high-pass σ, erosion and lag all
   proportional to the side, and sides of at least 400 px. This holds until the 200 px departure is explained. Expect
   200 px previews to show a slightly different floor and back wall.
4. **Analysis practice.**
   - Region means compared across sizes use the scaled erosion e(s) = 4·s/400.
   - Pre-registrations do not decide on strict per-key dominance (H5's rule) without a noise floor.
   - Complete-separation tests are paired with an effect statistic, as H3 was.
   - A mechanism hypothesis gets the contrast that separates its readings. Here that was (400, 800) on its own, or the
     zero-jitter family against the jittered one. A rule of "any rejection anywhere" does not separate them.

**Hypotheses for later work**
- **Image-locking holds above 800 px.**
  - Derived from: 400 vs 800 rejects 0 of 18 in three families, and Blender renders are usually larger than 800 px.
  - Test: a row-chain 1600 px family, 8 pairs per configuration, at jitter 1/1400 and at 0. At 1600 px, σ = 10.39 px,
    e = 16 px and τ = 8 px.
  - Comparisons (400, 800), (800, 1600) and (400, 1600) on T at 0.01/3 per family. Supported iff no key is rejected.
  - Secondary, zero family: the 800 → 1600 step of `structure_std` is smaller than the 400 → 800 step in each of r3-r7,
    as it was one doubling earlier. Likewise for the `r4.slag.x` step in both families.
- **The 200 px departure is undersampling.**
  - If it is, a footprint as wide as a 200 px pixel removes it.
  - Test: row chain, jitter 1/400 of the side (±0.5 px at 200 px, ±2 px at 800 px), (200, 800) on T at 0.01. Supported
    iff 0 of 18 keys are rejected. 006 rejects 1 at 1/1400 and 7 at 0.
  - If rejections remain, the departure comes from the chain. An oracle-only chain that walks columns then shows whether
    the `r4.slag.x` deficit follows the chain's direction or the scene's.
- **Jitter acts only by averaging over its footprint.**
  - If so, a 400 px render at jitter 1/800 of the side (±0.5 px, the whole pixel) has the same texture as a zero-jitter
    1600 px render averaged over 4×4 blocks.
  - Test: T at 0.01, supported iff 0 of 18 keys are rejected. A lower native amplitude would mean jitter also mixes the K
    state, so the knob is not a pure blur.
  - The test needs an oracle option that draws the 400 px jitter from the same 16 sub-pixel offsets. The two sides then
    differ only in the chain.
- **Jitter dose-response, for the M7 knob range.**
  - Prediction from 006: `structure_std` falls strictly with jitter in every region, `slag.y` rises on the walls (r4, r5
    and r6), and the steps shrink as jitter grows.
  - Test: row chain, 400 px, jitter 0, 1/5600, 1/2800, 1/1400, 1/700 and 1/350 of the side. Compare adjacent pairs on T
    with one-sided permutation tests, Holm across keys and pairs.
- **The seed-dependent texture is pixel-locked.**
  - Derived from: the K stride is per pixel, while the shared structure is image-locked (point 1 above).
  - Test: re-analyse 006's cached renders, with no new renders. The difference of two half renders, hp_a − hp_b, is pure
    noise. Compare its autocorrelation at fixed pixel lags and at lags proportional to the side, across 200, 400 and 800 px.
  - Pixel-locked iff the fixed-pixel lags agree (0 rejections) and the proportional lags do not. That decides whether
    low-pass-count renders depend on resolution even though the converged look does not.
- **Lane length belongs on the image plane too (M7).**
  - `lane_length` is in pixels, so `chain=lane` places its seam columns L px apart. On the image plane that spacing halves
    at every doubling of the side.
  - Test: an H3-style Δ comparison, L fixed in pixels vs L ∝ side, at 200, 400 and 800 px, with the seam-column amplitude
    as a key.
