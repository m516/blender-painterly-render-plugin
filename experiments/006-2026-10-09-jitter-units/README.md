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
