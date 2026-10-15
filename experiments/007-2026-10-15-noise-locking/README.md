# Experiment 007: is the seed-dependent texture pixel-locked? (noise locking)

## Background

- `docs/plan.md`, "What makes the look":
  - item 3 (scan-line chaining): K starts where the previous pixel's path in the same row ended, and only diffuse hits
    advance it. The chained K stream gives a deterministic, converged texture.
  - item 5 (display): the texture appears only once converged, at about 250 passes or more.
- `docs/spec.md`:
  - §2: every random decision that differs between seeds is hashed per pixel and pass. The jitter and the closure
    choice use (row, col, pass), and the lane K0 uses (row, lane_in_row, pass).
  - §3: `chain=image` runs one K stream from K = 0 over `for pass, for row, for col` and never resets it.
    `chain=row` starts each (row, pass) at `K0 = rng_u32(seed, PURPOSE_LANE_K0, 0, row, 0, pass) mod 2^22`.
  - §7: jitter is a fraction f of the fitted image side, default f = 1/1400. The oracle's `--jitter` is in image-plane
    units, j = 2f. Its maximum displacement is f·s px at side s.
- `experiments/001-2026-10-08-oracle-reproduction/`, H4 (image chain, back wall, 9 px box high-pass, 400 px):
  - the high-pass variance follows `v(P) = σ_s² + σ_n²/P`, with σ_s² = 33.07 and σ_n² = 5573.6 (display bytes²);
  - the noise-to-structure variance ratio is 168.5/P: 2.63 at P = 64 and 3.4 at the GUI default of 50 passes. The
    seed-dependent part has the larger variance below P = 168.5;
  - the "Smallpaint Reference" preset uses 1024 passes (ratio 0.16).
- `experiments/004-2026-10-08-resolution-dependence/`:
  - amendments, H1d: in image mode the rows are coupled by a K offset of about W × 16.3 draws, i.e. K advances by about
    16.3 draws per pixel per pass;
  - D7 (8-pair smoke at 100 px, image chain, 9 px box high-pass): 2 × 2 box-downsampling of the 200 px sums lowers the
    noise sd from 7.6 to 3.8 display bytes, a variance ratio of 4.0 = 2². Box averaging also changes the structure with
    no noise at all (lag-1 0.473 natively, 0.671 after box-downsampling, smoke scale).
- `experiments/006-2026-10-09-jitter-units/` (final):
  - the shared structure is image-locked. With high-pass σ, erosion and lag all proportional to the side, 400 and 800 px
    reject 0 of 18 texture keys in three families (image chain, row chain, row chain with zero jitter). Every departure
    involves 200 px.
  - Its texture keys are noise-corrected, so the seed-dependent part was removed by design and not tested (Conclusion,
    "What is covered").
  - "Hypotheses for later work" names this experiment: "The seed-dependent texture is pixel-locked. Derived from: the K
    stride is per pixel, while the shared structure is image-locked. Test: re-analyse 006's cached renders … hp_a − hp_b
    … at fixed pixel lags and at lags proportional to the side, across 200, 400 and 800 px."
  - Amendment 1: with `chain=image` the seed enters a render only through the jitter. Image-chain noise is therefore
    entirely the variation between jitter realizations, and `chain=image` with jitter 0 renders one image for every
    seed. Row-chain noise also contains the K0 variation.
  - Conclusion, point 2: a sub-pixel footprint (±2/7 px at 400 px) removes 44% of the back wall's structure variance,
    so the structure has energy at sub-pixel scales.
  - Decision 1: units are always named; in SPEC §7, "1/1400" is a fraction of the side.
  - Analysis practice adopted there: complete-separation tests are paired with an effect statistic, strict per-key
    dominance needs a noise floor, and a hypothesis gets the contrast that separates its readings.
- **Prior exposure: noise-bearing summaries of these renders are already published.** The binding constraint of this
  experiment (re-analyse 006's cache, no new renders) rules out fresh replicates, so H1-H5 and the common-side
  estimation (E1) re-analyse renders whose noise-bearing summaries are in earlier results files:
  - 004 `results.json`, `summary` and `raw_lag1_effects`: the raw lag-1 of the high-passed summed pair `ab8`
    (9 px box, lag 1 px, fixed pixel units, P = 128, so a noise-to-structure ratio near 168.5/128 = 1.3 at 400 px) for
    `s200`, `s400`, `s800`, `s800_px` (004 `s800_j1400`), `row_s200`, `row_s400` and `row_s800`. For example
    `r4.lag1.x` is 0.203 ± 0.009 (`s400`) vs 0.146 ± 0.004 (`s800`), d 8.2.
  - 004 `downsample_effects` (`s800` box-downsampled to 400 px vs `s400`): `r4.lag1.x` 0.445 vs 0.203, d 35.
  - 006 `results.json`: `r{r}.spectral_slope` of the high-passed summed pair, for all 16 configurations.
  - These are close relatives of the `px`-frame keys of H1 and H2 and of E1. They mix structure and noise in fixed
    pixel units, the confound that 004's Limitation and 006 describe, so they are not evidence for either reading.
  - The readings, frames and masks were set in the first draft of this pre-registration. While revising its decision
    rules after a design review, the author read the 004 numbers above to check one review comment. No knob,
    direction or decision boundary was set from them. In particular H4 is two-sided because mechanism items 2-3 do not
    fix the sign of an along-row correlation, not because of 004's values (`r4.lag1.y` > `r4.lag1.x` at every side, a
    mixture whose structure part also has y > x: 006 Table 1, `r4.slag.y` 0.264 vs `r4.slag.x` 0.179 for
    `row_s400`).
- **Mechanism, and the readings this experiment separates.**
  1. A seed changes the render only through per-pixel hashes: the jitter of each (row, col, pass), and for the row
     chain the K0 of each (row, pass). The closure choice is hashed per (row, col, pass) too, but every material of the
     reference scene has one lobe, so that choice never depends on the seed (SPEC §6).
  2. Along a row, the K offset between two pixels is the sum of `k_consumed` over the pixels between them. That is a
     count of pixels, not an image-plane distance. So any noise correlation the chain creates along a row should be
     fixed in pixels.
  3. Different rows have unrelated K.
     - The row chain draws its K0 per (row, pass), and its other hashes are keyed by (row, col, pass) (SPEC §2-3).
       A row of a row-chain render is therefore a function of that row's hashes alone. With the hash acting as a
       random function of its arguments, the row chain's noise is independent across rows, at every side and under
       every reading below.
     - The image chain offsets consecutive rows by a whole row's consumption, which differs between jitter
       realizations. Its rows should therefore be uncorrelated at any lag of 1 px or more, but nothing makes them
       independent. H5 tests both chains.
     - Items 2 and 3 together predict that the noise is anisotropic in the pixel frame (H4). They do not fix the sign
       of the along-row correlation.
  4. The structure is the expectation over K of each pixel's value, a function of the hit point and therefore of the
     image-plane position. That is consistent with 006's image-locking.
  5. Readings of the noise (`n`, the seed-dependent part), for its statistics along a row:
     - **(A) pixel-locked**: fixed on the pixel grid, whatever the jitter.
     - **(A′) pixel-locked at a fixed image-plane jitter**: fixed on the pixel grid as long as the jitter's fraction of
       the side f is fixed, but following f. A possible source: in the image chain, the probability that a jittered ray
       changes a path's `k_consumed`, and so desynchronises the chain, is set by the jitter's world-space size. The
       image-plane jitter families hold f fixed, so there (A′) behaves as (A). Only the pixel-jitter family, whose f
       differs between sides, separates them.
     - **(B) set by the jitter's pixel displacement**: pixel-locked at a fixed jitter in px, but its statistics follow
       the jitter's displacement in pixels, f·s. With image-plane jitter that displacement doubles with the side (1/7,
       2/7 and 4/7 px at 200, 400 and 800 px), so in the image-plane jitter families (B) changes in pixels as (C)
       does. Only a family whose jitter is fixed in pixels separates (B) from (C).
     - **(C) image-locked**: a random field on the image plane, whose correlation length along a row scales with `s`.
     - **(D) mixed**, e.g. geometry-modulated pixel locking: the chain couples pixels n px apart, but how strongly
       depends on how similar their geometry is, an image-plane property. Both frames then change with `s`.
  6. **Consequence for the keys.** Row-chain noise is independent across rows (item 3), so it is white along y at
     every side, whatever it does along a row. A 2-D high-pass passes that y-white part with a gain set by its σ in
     pixels, which is pixel-locked by construction. With 2-D keys, row-chain noise that is image-locked along rows
     would still change the image-plane keys between sides, and reading (C) could not be reached. In the second review
     round an image-locked, row-independent synthetic noise read as inconclusive or partially refuted in every run
     with the first draft's 2-D keys, never as (C). The locking keys are therefore taken along rows (Common
     definitions, "Two frames"), and the across-row behaviour is tested separately (H5).
- **Why it matters.** If the noise is pixel-locked and the structure image-locked, then at a fixed pass count a render
  shown at a fixed display size has less noise relative to its strokes when rendered larger. Low-pass-count renders
  would then depend on resolution even though the converged look does not. Pass presets (001: 1024 passes at 400 px)
  and any low-pass acceptance test would need to name the side they hold for. E1 estimates by how much.
- **Renders.** None. Every configuration is a cached ensemble of 006 (Method), rendered by the 006 oracle binary
  `.cache/oracle-build/src/app/smallpaint_oracle`, sha256
  `066bb5d4247c556ad5232bfc4fff75dc5f37089840b23f1ecc8fdd9cb518828a`. That sha256 is part of every cache key. Never
  run `make oracle`: a rebuilt binary has another sha256, and the renders that 006, 007, 008 and 009 use would no
  longer be found in the cache. This experiment uses no seed block. Experiment 008 takes blocks 42-45 (seeds 672-735)
  and experiment 009 blocks 46-67 (seeds 736-1087).

## Hypothesis

### Common definitions

- **Configurations.** Each configuration is a cached 006 ensemble of 8 pairs. A pair is two independent half renders,
  seeds 2k and 2k + 1 of the configuration's block, each with P = 64 passes, `scene=gui` and `ghost=all`.
  - Image-plane jitter families: `s200`, `s400`, `s800` (`chain=image`) and `row_s200`, `row_s400`, `row_s800`
    (`chain=row`). The jitter is the oracle default, f = 1/1400 of the side (j = 1/700 image-plane units): 1/7, 2/7 and
    4/7 px.
  - Pixel-jitter families: `s200_px`, `s800_px` (`chain=image`) and `row_s200_px`, `row_s800_px` (`chain=row`). Their
    jitter is 2/7 px at every side: f = 1/700 (j = 1/350) at 200 px and f = 1/2800 (j = 1/1400) at 800 px. Their
    400 px member is `s400` (or `row_s400`), where both units coincide. Their `px`-frame comparison (`C_jit`) is part
    of H1 and H2. It separates reading (B) from reading (C), and (A′) from (A).
  - Zero-jitter row family: `row_j0_s200`, `row_j0_s400`, `row_j0_s800` (`chain=row`, jitter 0).
  - Excluded: the image-chain zero-jitter family `j0_s*`. It has one distinct render among 16 (006 Table 7), so its
    noise is identically zero.
- **Units.** The side `s` is in pixels (px). Jitter is given as f, the fraction of the fitted side (SPEC §7, the Blender
  knob, as in 008 and 009), with j = 2f in image-plane units (the oracle's `--jitter`) and f·s in px where useful. In
  configuration names the suffix `_px` is 006's name for jitter fixed in pixels. In key names the prefix `px.` is the
  pixel frame, and the two are unrelated. Spatial frequencies are written ν. Noise keys are dimensionless unless they
  say "display bytes".
- **The noise field.** For a pair (a, b) at side `s`:
  - `x_a = metrics.luminance(smallpaint_display(a.sum, P))`, in display bytes, and `x_b` likewise;
  - `δ = x_a − x_b`.
  - Write `x = m + n`, where `m` is the expectation of `x` over seeds (the structure and the shading) and `n` is the
    seed-dependent part. Then `δ = n_a − n_b` exactly, because `m` cancels.
  - `n_a` and `n_b` come from two seeds of one configuration, so they are independent and identically distributed.
    Hence `var(δ) = 2·var(n)`, and the autocorrelation of `δ` at any lag equals that of `n`.
  - This needs genuinely independent replicates (006 lesson). The design check requires `2·pairs` distinct renders per
    configuration (16 at full scale) and no pair with `δ ≡ 0`.
- **Two frames.** Each frame fixes a Gaussian high-pass σ and a lag τ.
  - The locking keys use the along-row high-pass `h_F = metrics.gaussian_highpass_axis(δ, σ_F(s), axis=1)`: δ minus its
    Gaussian blur along x only, on the half-sample-symmetric extension of each row (the extension that
    `metrics.gaussian_highpass` uses, on axis 1 only; Method). Each row is filtered from that row alone. By linearity
    `h_F` is the difference of the halves' along-row high-passes.
  - The isotropic high-pass `h_F^iso = metrics.gaussian_highpass(δ, σ_F(s))` (the first draft's) serves H4 and the
    estimation keys only. H4 compares x with y at one side, so it needs a filter that treats them alike. The along-row
    filter does not: it removes most of an along-row AR(1)'s lag-2 correlation (φ = 0.6: −0.174 after the along-row
    high-pass at σ = 2.598 px, against −0.168 for white noise; analytic, from the spectra), and in the planning H4 with
    along-row and along-column filters rejected `ar1` in 36 of 200 references, against 200 of 200 with the isotropic
    filter.
  - Why along rows: Background, mechanism item 6.

  | frame | σ_F(s) (px) | τ_F(s) (px) | at 200 px | at 400 px | at 800 px |
  |---|---|---|---|---|---|
  | pixel (`px`) | 9/√12 = 2.598 | 2 | σ 2.598, τ 2 | σ 2.598, τ 2 | σ 2.598, τ 2 |
  | image-plane (`ip`, 006's) | (9/√12)·s/400 | s/200 | σ 1.299, τ 1 | σ 2.598, τ 2 | σ 5.196, τ 4 |

  - The `ip` frame is 006's scale-equivariant definition of σ and τ (006 filtered in 2-D).
  - The `px` frame is the `ip` frame frozen at the reference side s₀ = 400. So the two frames coincide exactly at 400
    px, and the 400 px configuration is the common reference of every contrast.
- **Common mask.** The SPEC §9 regions 2-8, eroded with `e(s) = s/25` px (8, 16 and 32 px), give the masks `M_r` of both
  frames.
  - Same mask in both frames. If the erosion differed between frames, a frame difference could come from region
    selection instead of locking. 004's region-mean trend came from exactly that (006 H5). So the erosion selects the
    same image-plane area at every side.
  - Why `s/25` and not 006's `4·s/400`. The mask must keep both frames' filters inside one region. `e(s)` is at least
    3.08 σ of either filter at every side (the minimum is the `px` filter at 200 px: 8/2.598). Less than Φ(−3.08) = 0.1%
    of the filter weight then reaches across a region boundary. Region noise levels differ, and edge pixels carry the
    jitter's edge aliasing, so leakage that changed with `s` would mimic a size effect.
  - Mask sizes (design check on the 006 object-id maps; geometry only): from 426 px (r2) to 4,712 px (r4) at 200 px,
    from 1,697 to 18,980 px at 400 px, and from 6,785 to 76,104 px at 800 px. Region 8 is absent at every side (006).
    Every lag used here has pixel pairs in every mask at full scale: the fewest are 135 x-pairs and 143 y-pairs (r2,
    200 px, lag 12 px).
  - A region that is empty after erosion at any side is dropped everywhere and reported. None is expected.
- **Noise family N_F** (along-row shape keys only), per measured region r and frame F:
  - `F.r{r}.noise_frac = metrics.structure_std(h_F, h_F, M_r) / metrics.structure_std(δ, δ, M_r)`: the fraction of the
    noise sd that passes the frame's along-row high-pass (dimensionless, in (0, 1]);
  - `F.r{r}.nlag.x = metrics.noise_corrected_lag(h_F, h_F, M_r, axis=1, lag=τ_F(s))`: the noise autocorrelation along
    a row (x).
  - With identical arguments, `noise_corrected_lag` is the plain masked lag-τ autocorrelation
    (`test_noise_corrected_lag_of_identical_halves_is_the_masked_autocorrelation`, added for 006), and
    `structure_std(x, x, M)` is the masked population sd.
  - N_F is these 12 keys (6 regions × 2). Both are invariant to a change of the noise amplitude, so a per-pixel noise
    variance that differs between sides cannot reject a key. Possible sources of such a drift are the image chain's
    per-pass K advance (about 16.3·s² draws) against the 2^23 period (SPEC §2), and 006's 200 px undersampling.
  - No across-row key enters N_F. For the row chain it would be the key of noise that is white across rows under every
    reading (mechanism item 3). H5 tests the across-row independence of every chain.
- **Estimation-only keys** (effect summaries, no verdicts):
  - `F.r{r}.noise_std = metrics.structure_std(h_F, h_F, M_r)/√2`, the noise sd of one half render in display bytes;
  - `F.r{r}.structure_std = metrics.structure_std(hp_F(x_a), hp_F(x_b), M_r)`, with the frame's along-row high-pass
    `hp_F`;
  - the noise-to-structure variance ratio `F.r{r}.q = noise_std² / structure_std²` per configuration;
  - `F.r{r}.iso_nlag.x` and `F.r{r}.iso_nlag.y = metrics.noise_corrected_lag(h_F^iso, h_F^iso, M_r, axis, τ_F(s))`
    with `axis=1` and `axis=0`, and `F.r{r}.aniso = iso_nlag.x − iso_nlag.y` (H4 uses the `px` values at 400 px);
  - `raw.r{r}.row_corr`, H5's per-region statistic, at every side.
- **Contrasts.** (400, 800), written "`…s800` vs `…s400`" (hypotheses H*a), and (200, 400), written "`…s200` vs
  `…s400`" (H*b). The 400 px configuration is the reference `b` of every effect summary, since the frames coincide
  there.
- **Comparisons** of a hypothesis on family prefix `p` (`row_`, empty or `row_j0_`) at contrast (N, 400):
  - `C_px`: `{p}sN` vs `{p}s400` on N_px;
  - `C_ip`: `{p}sN` vs `{p}s400` on N_ip;
  - `C_jit` (H1 and H2 only): `{p}sN_px` vs `{p}s400` on N_px.
  - `R_px`, `R_ip` and `R_jit` are their numbers of Holm-rejected keys (of 12).
- **Significance.** Each hypothesis (H1a, H1b, H2a, …) has family-wise level 0.01 (`SIGNIFICANCE`, not the oracle
  option `alpha`).
  - H1 and H2 have three comparisons (`C_px`, `C_ip`, `C_jit`), each at 0.01/3. H3 has two (`C_px`, `C_ip`), each at
    0.005.
  - Every p-value of a comparison is an exact two-sided permutation p-value (`ensemble.permutation_pvalue`), with Holm
    (`ensemble.holm`) across its 12 keys.
  - H4 and H5 are one exact two-sided sign-flip test each (`ensemble.sign_flip_pvalue`) at 0.01.
- **Power.**
  - With 8 vs 8 pairs, the smallest attainable p is 2/C(16, 8) = 1.55e-4, and the next is 4/C(16, 8) = 3.11e-4. The
    first Holm threshold is (0.01/3)/12 = 2.78e-4 for H1 and H2 and 0.005/12 = 4.17e-4 for H3, so every comparison is
    powered. For H1 and H2, ranks 1-2 reject only at p = 1.55e-4, which means that all 8 pairs of one configuration lie
    beyond all 8 of the other (complete separation); from rank 3 ((0.01/3)/10 = 3.33e-4) the next split is admitted.
    For H3 the first rank already admits p = 3.11e-4.
  - Sensitivity of one key, for normal samples shifted by d pooled sd (simulation, 200,000 draws, seed 0): the
    probability of complete separation is 0.16 at d = 2, 0.59 at 3, 0.78 at 3.5, 0.91 at 4 and 0.99 at 5.
  - The pixel-locked case hardest to separate with the first draft's 2-D keys, pixel-white noise at (400, 800), is no
    longer marginal.
    - The along-row high-pass passes 0.894 of white noise's sd at 400 px and 0.949 at 800 px, and `nlag.x` moves from
      −0.171 to −0.073 (r4, replicate 0 of the table below). In that realization the regions have d = 5.0 (r2
      `nlag.x`) to 39.4 (r5 `noise_frac`) on the `ip` keys. The first draft's 2-D keys moved only 0.982 → 0.995 in
      `noise_frac` (r4), with d of about 1.0 to 3.4.
    - The synthetic verdict runs below give the power of the whole rule, including the effect statistic.
  - H4 and H5 reject only if all 8 pairs share a sign: p = 2/256 = 0.0078 ≤ 0.01, and one pair of the other sign gives
    p ≥ 4/256 = 0.0156. For normal per-pair values with mean μ and sd σ_A, the power is
    Φ(μ/σ_A)^8 + Φ(−μ/σ_A)^8: 0.95 at |μ|/σ_A = 2.49.
- **Effect statistics** (006 lesson: a complete-separation verdict is paired with an effect size, and magnitudes
  compared across frames need a common noise floor):
  - `d_F,k` is the `ensemble.effect_summary` Cohen's d of key k of N_F, (mean_a − mean_b)/pooled sd.
  - `Δ_F` is the median over the 12 keys of N_F of `|d_F,k|`.
  - Why |d|. If a frame's key has the same distribution at both sides, `|d|` has the same null distribution whatever
    the key's units or sampling sd: for normal samples `d = t₁₄/2`, median `|d|` 0.346. So two frames that do not
    change have equal Δ in expectation. Raw differences would not: the frames' filters differ, so their sampling sds
    and noise floors differ, and `noise_frac` and `nlag` have no common unit.
  - **`D = Δ_ip − Δ_px`** (`C_ip` and `C_px`, same pairs). It is positive when the pixel frame holds the noise more
    nearly constant than the image-plane frame.
  - **`D_jit = Δ_px(C_px) − Δ_px(C_jit)`** (H1, H2). It is positive when the `px` keys move more with image-plane
    jitter than with jitter fixed in pixels, and negative when they move more with jitter fixed in pixels.
  - Intervals: 99% percentile bootstrap (`CI_DECISION = (0.5, 99.5)`, level 0.01 = `SIGNIFICANCE`, the level of the
    hypothesis). Pairs are resampled within each configuration, with `BOOTSTRAP_RESAMPLES = 100_000` resamples. Per
    hypothesis, one `numpy.random.default_rng(0)` draws `integers(0, pairs, (BOOTSTRAP_RESAMPLES, pairs))` for the
    configurations in the order reference, sN, sN_px (H3: reference, sN). Δ_px, Δ_ip, D and D_jit all use these
    matrices, so the reference's draw serves `C_px`, `C_ip` and `C_jit`. The resample count sets only the Monte Carlo
    precision of the 0.5% tails.
  - The interval level is **nominal**. A percentile bootstrap over 8 pairs undercovers (a review simulation of a nominal
    99% interval of a log ratio gave 0.972 coverage at n = 8). Its use in each verdict is bounded below.
  - `Δ_F` is also reported per key class (`noise_frac` only, `nlag.x` only), and for the estimation key `noise_std`.
- **Verdict of a locking hypothesis.** D enters every decided cell, so no verdict rests on rejection counts alone. P, I
  and J abbreviate `R_px ≥ 1`, `R_ip ≥ 1` and `R_jit ≥ 1`. "D > 0" means that the 99% interval of D lies above 0, and
  "D < 0" that it lies below 0; "D_jit > 0" and "D_jit < 0" are defined likewise by the interval of D_jit. An interval
  that contains 0 satisfies neither.

  | cell | condition | verdict | reading |
  |---|---|---|---|
  | 1 | not P, not J (H3: no J condition), I, D > 0 | **supported** | (A) pixel-locked, whatever the jitter |
  | 2 | not P, J, I, D > 0, D_jit < 0 (H1, H2 only) | **supported** | (A′) pixel-locked at a fixed image-plane jitter; its pixel statistics follow the jitter's fraction of the side |
  | 3 | P, not J, D_jit > 0 (H1, H2 only) | **refuted** | (B) set by the jitter's pixel displacement |
  | 4 | P, not I, J (H3: no J condition), D < 0 | **refuted** | (C) image-locked. At (400, 800), for noise correlated across rows, a pixel-white share of about 0.1 of the noise variance is not excluded (Readings, mixtures) |
  | 5 | P, I, J (H3: no J condition), D > 0 | **partially supported** | (D) both frames change, the `px` frame less |
  | 6 | P, I, J (H3: no J condition), D < 0 | **partially refuted** | (D) both frames change, the `ip` frame less |
  | 7 | anything else | **inconclusive** | the R pattern and the intervals do not agree, or an interval contains 0 |

  - The cells are mutually exclusive: cells 1-2 need not P and the others P; cell 1 needs not J and cell 2 J; cell 3
    needs not J and cells 4-6 J; cell 4 needs not I and cells 5-6 I; cell 5 needs D > 0 and cell 6 D < 0.
  - Cells 1 and 2 both support H1 or H2, which are about image-plane jitter. Every report names the reading as well as
    the verdict.
  - "Image-locked" (cell 4) is read only when the pixel-jitter family also changes in the `px` frame (J). Without J,
    a change in the `px` frame may be set by the jitter's displacement in pixels (cell 3), or the reading is not
    separated (cell 7).
  - At (400, 800), cell 4 does not separate (C) from (C) with a small pixel-white component when the noise is
    correlated across rows. In the planning, the isotropic mixture `mix_gauss` with white share 0.1 read as cell 4 in
    14 of 20 H1/H2-type and 10 of 20 H3-type runs. With independent rows (`mix_x`, the only kind the row chain
    produces) the same share read as cell 6 in 20 of 20 runs of each type. Shares of 0.25 or more never read as cell
    4 (0 of 640 runs at (400, 800): w = 0.25, 0.5, 0.75 and 0.9, both mixtures, both types), and at (200, 400) a share
    of 0.1 read as cell 6 in every run (160 of 160). The Conclusion therefore reports a cell-4 verdict at (400, 800)
    only together with the (200, 400) cell of the same family.
  - Every verdict reports R_px, R_ip, R_jit, D and D_jit with their intervals, and the rejected keys of each
    comparison by class. Geometry-modulated pixel locking predicts `px` rejections concentrated in `nlag.x` and at
    (200, 400).
  - Error control under a pure reading. Under (A) the `px` keys do not change in either family; under (A′) they do not
    change in the image-plane family; under (C) the `ip` keys do not change; under (B) the image-plane family behaves
    like (C) and the pixel-jitter family does not change in `px`. A decided cell other than the predicted one therefore
    needs a comparison to reject that the reading predicts not to change:
    - an **opposite-direction verdict** (cells 3, 4 or 6 under (A) or (A′); cells 1, 2 or 5 under (B) or (C)) needs
      such a rejection *and* an interval of D or D_jit on the side the reading predicts against. It was never observed
      in the planning runs below;
    - a **same-direction misreading** needs one such rejection only: cell 2 or 5 under (A) needs J or P, cell 5 under
      (A′) needs P, cell 4 under (B) needs J, cell 6 under (C) needs I. Each has probability at most the comparison's
      Holm level, 0.01/3 (H1, H2) or 0.005 (H3), whatever the bootstrap's coverage. The exceptions need a comparison
      to miss a change, a power failure estimated by the planning runs: (A′) read as (A) (cell 1, `C_jit` misses) and
      (C) read as (B) (cell 3, `C_jit` misses);
    - outside the pure readings, cells 5 and 6 rest on the sign of D and carry its nominal level.
  - A comparison that is not powered (only at smoke scale) makes the verdict **inconclusive**.
- **Mechanism labels.** A supported or partially supported verdict is labelled with H4 and H5 of the same family:
  "anisotropic (the chain's signature)" if H4 rejects, "isotropic at τ = 2 px" if it does not; "rows correlated" if H5
  rejects, "rows independent within the detection limit" if it does not. A pixel-locked verdict on noise that is white
  at 1 px is weak evidence on its own: image-locked noise whose correlation length is below one pixel at 800 px would
  also be white in pixels at every side.
- **Attribution, one factor at a time.** H1 against H3 (row chain, f = 1/1400 vs 0) isolates the jitter. H1 against H2
  (f = 1/1400, row vs image chain) isolates the chain. No verdict compares H2 with H3, which differ in both.

### Readings and their predictions (derivation)

Pre-registration computation on synthetic noise, through the same pipeline: same keys, same masks (the 006 object-id
maps), same frames and the same verdict rule. `analyze.py --synthetic` recomputes it with the library functions
(Method, "Synthetic validation") and writes it to `synthetic.json`; Results reports that version. No decision threshold
depends on these numbers. They state what each reading predicts and estimate the power of the rule.

Models (exact definitions in Method; every field is in display bytes and goes through `smallpaint_display`). Models
named `_x` are correlated along rows only, with independent rows, like every noise the row chain can produce (mechanism
item 3); `white`, `white_drift` and `ar1` have independent rows too. Models named `_gauss` are isotropic, which only a
chain that couples rows (the image chain, if H5 rejects) can produce. Both kinds gate every hypothesis type, because
the keys are the same.
- (A) `white`: pixel-white noise. `white_drift`: the same with a noise variance that doubles at each doubling of the
  side (sd 6.60, 9.33 and 13.20 bytes at 200, 400 and 800 px), which the amplitude-free keys must ignore. `ar1`: an
  along-row AR(1) with lag-1 φ = 0.6 per px. `pix_x`: Gaussian correlation along rows with sd σ_n = 2 px.
  `pix_gauss`: isotropic Gaussian correlation with sd σ_n = 2 px.
- (A′) `ipjit_x`: as `pix_x`, with σ_n = 2 px × j/(1/700) for the configuration's image-plane jitter j: 2 px in the
  image-plane jitter family, 4 px at 200 px and 1 px at 800 px in the pixel-jitter family.
- (B) `jit_x` (along rows) and `jit_gauss` (isotropic): Gaussian correlation whose sd in px follows the jitter's
  displacement in px, σ_n = 2 px × (f·s)/(2/7 px): 1, 2 and 4 px in the image-plane jitter family, 2 px in the
  pixel-jitter family.
- (C) `img_x`: an independent image-plane field along each row, with correlation sd 2/400 of the side, sampled at the
  pixel centres. `img_gauss`: the isotropic image-plane Gaussian random field with the same correlation sd.
- (D) `mix_x` = `white` + `img_x` and `mix_gauss` = `white` + `img_gauss`, with white share w = 0.5 of the variance.
  They have no predicted cell; they show how the rule treats a noise in which both frames change. The planning also
  swept w (below).
- φ, σ_n, the drift factor and the mixing weight are knobs chosen to bracket the readings (white to strongly
  correlated, a correlation length equal to the 400 px lag), not derived from the mechanism or from data.

Region 4 key means, one realization of 8 pairs per configuration (second-round planning, replicate 0): `noise_frac`,
`nlag.x`. The 400 px column is shared by both families, and there the frames coincide.

| model | frame | 200 px | 400 px | 800 px | 200 px, pixel jitter | 800 px, pixel jitter |
|---|---|---|---|---|---|---|
| `white` | px | 0.896, −0.162 | 0.894, −0.171 | 0.895, −0.168 | 0.893, −0.170 | 0.894, −0.168 |
| | ip | 0.779, −0.452 | (as px) | 0.949, −0.073 | 0.774, −0.443 | 0.948, −0.076 |
| `white_drift` | px | 0.893, −0.168 | 0.894, −0.169 | 0.895, −0.168 | 0.892, −0.173 | 0.895, −0.168 |
| | ip | 0.775, −0.447 | (as px) | 0.949, −0.071 | 0.775, −0.447 | 0.949, −0.074 |
| `ar1` | px | 0.666, −0.173 | 0.669, −0.175 | 0.668, −0.175 | 0.667, −0.174 | 0.667, −0.174 |
| | ip | 0.494, −0.209 | (as px) | 0.808, −0.188 | 0.491, −0.194 | 0.808, −0.190 |
| `pix_x` | px | 0.505, 0.065 | 0.511, 0.080 | 0.508, 0.078 | 0.513, 0.072 | 0.510, 0.077 |
| | ip | 0.245, 0.567 | (as px) | 0.738, −0.350 | 0.247, 0.575 | 0.739, −0.353 |
| `pix_gauss` | px | 0.521, 0.077 | 0.518, 0.077 | 0.508, 0.078 | 0.502, 0.083 | 0.508, 0.077 |
| | ip | 0.250, 0.576 | (as px) | 0.738, −0.351 | 0.240, 0.576 | 0.737, −0.351 |
| `ipjit_x` | px | 0.512, 0.078 | 0.506, 0.077 | 0.508, 0.078 | 0.243, 0.578 | 0.736, −0.355 |
| | ip | 0.245, 0.578 | (as px) | 0.738, −0.349 | 0.083, 0.759 | 0.868, −0.218 |
| `jit_x` | px | 0.735, −0.350 | 0.511, 0.077 | 0.244, 0.575 | 0.502, 0.078 | 0.507, 0.078 |
| | ip | 0.506, 0.078 | (as px) | 0.509, 0.080 | 0.241, 0.572 | 0.737, −0.350 |
| `jit_gauss` | px | 0.738, −0.361 | 0.513, 0.068 | 0.243, 0.573 | 0.506, 0.073 | 0.508, 0.079 |
| | ip | 0.509, 0.079 | (as px) | 0.505, 0.075 | 0.244, 0.573 | 0.737, −0.351 |
| `img_x` | px | 0.736, −0.353 | 0.508, 0.079 | 0.241, 0.593 | 0.737, −0.355 | 0.242, 0.592 |
| | ip | 0.507, 0.079 | (as px) | 0.507, 0.086 | 0.505, 0.088 | 0.508, 0.084 |
| `img_gauss` | px | 0.731, −0.353 | 0.511, 0.080 | 0.242, 0.592 | 0.739, −0.358 | 0.245, 0.591 |
| | ip | 0.504, 0.075 | (as px) | 0.507, 0.085 | 0.509, 0.085 | 0.511, 0.075 |
| `mix_x` | px | 0.824, −0.244 | 0.729, −0.106 | 0.655, −0.117 | 0.822, −0.239 | 0.656, −0.114 |
| | ip | 0.659, −0.287 | (as px) | 0.760, −0.040 | 0.660, −0.295 | 0.761, −0.043 |
| `mix_gauss` | px | 0.820, −0.246 | 0.729, −0.109 | 0.658, −0.116 | 0.818, −0.242 | 0.655, −0.117 |
| | ip | 0.655, −0.285 | (as px) | 0.762, −0.041 | 0.652, −0.284 | 0.760, −0.038 |

- (A) keeps every `px` key constant in both families (all five columns within 0.019 in `noise_frac` and 0.014 in
  `nlag.x`, the realization noise), and `white_drift` matches `white` although its amplitude changes by a factor √2
  per doubling. The `ip` keys change, even for pixel-white noise, because σ_ip and τ_ip scale: white noise's along-row
  high-pass passes 0.779, 0.894 and 0.949 of its sd at 200, 400 and 800 px (analytic, for an infinite row: 0.777,
  0.895 and 0.949).
- (A′) is (A) in the image-plane jitter family and changes in `px` only in the pixel-jitter family.
- (C) does the reverse of (A): the `ip` keys are constant, and the `px` keys change in both families.
- (B) equals (C) in the image-plane jitter family. Only its pixel-jitter family, constant in `px`, tells them apart.
- (D) changes in both frames.
- The `_x` and `_gauss` versions of each reading have the same along-row keys within the realization noise: the
  along-row filter does not see the across-row correlation, which is what makes (C) reachable for the row chain.

E1 on the same models (one realization, 8 pairs per configuration; median over regions with its 99% interval). E1 keeps
the 2-D high-pass (Estimation). The rows of `white`, `white_drift`, `ar1`, `pix_gauss`, `jit_gauss` and `img_gauss`
are the first draft's planning realizations; the `_x` rows and `mix_gauss` are from the second round.

| model | β, 200 → 400 at 200 px | β_S | β_q | β, 400 → 800 at 400 px | β_S | β_q |
|---|---|---|---|---|---|---|
| `white` | 1.99 [1.96, 2.02] | 0.14 [−0.01, 0.30] | 1.85 [1.67, 2.02] | 2.00 [1.99, 2.01] | 0.01 [−0.03, 0.08] | 1.99 [1.91, 2.04] |
| `white_drift` | 0.99 [0.96, 1.02] | 0.12 [0.07, 0.21] | 0.88 [0.77, 0.94] | 1.00 [0.99, 1.01] | 0.01 [−0.05, 0.10] | 0.99 [0.89, 1.05] |
| `ar1` | 1.24 [1.22, 1.27] | 0.15 [0.00, 0.28] | 1.08 [0.95, 1.26] | 1.28 [1.27, 1.29] | 0.08 [−0.05, 0.15] | 1.21 [1.13, 1.33] |
| `pix_x` | 0.94 [0.90, 0.98] | 0.12 [−0.15, 0.30] | 0.82 [0.61, 1.12] | 1.00 [0.98, 1.02] | 0.11 [0.01, 0.17] | 0.90 [0.81, 1.00] |
| `pix_gauss` | −1.51 [−1.57, −1.47] | 0.10 [0.02, 0.24] | −1.62 [−1.81, −1.50] | −0.53 [−0.57, −0.50] | 0.07 [−0.05, 0.14] | −0.59 [−0.70, −0.46] |
| `ipjit_x` | 0.95 [0.89, 0.99] | 0.06 [−0.18, 0.28] | 0.87 [0.62, 1.17] | 1.01 [0.99, 1.04] | −0.02 [−0.20, 0.13] | 1.03 [0.86, 1.24] |
| `jit_x` | 1.12 [1.09, 1.13] | 0.10 [−0.01, 0.26] | 1.03 [0.84, 1.14] | 1.01 [0.99, 1.04] | 0.08 [−0.05, 0.16] | 0.93 [0.84, 1.09] |
| `jit_gauss` | 0.28 [0.25, 0.31] | 0.08 [−0.04, 0.24] | 0.18 [0.03, 0.34] | 0.06 [0.03, 0.09] | 0.07 [−0.04, 0.19] | −0.02 [−0.16, 0.12] |
| `img_x` | 1.09 [1.07, 1.12] | 0.15 [0.05, 0.29] | 0.93 [0.77, 1.06] | 1.01 [0.98, 1.03] | 0.08 [−0.08, 0.19] | 0.93 [0.80, 1.09] |
| `img_gauss` | 0.27 [0.24, 0.32] | 0.16 [0.01, 0.29] | 0.12 [−0.04, 0.31] | 0.06 [0.04, 0.09] | −0.01 [−0.11, 0.15] | 0.07 [−0.10, 0.19] |
| `mix_x` | 1.51 [1.48, 1.53] | 0.13 [0.02, 0.26] | 1.41 [1.24, 1.50] | 1.45 [1.44, 1.47] | 0.03 [−0.04, 0.12] | 1.42 [1.33, 1.50] |
| `mix_gauss` | 1.11 [1.10, 1.14] | 0.16 [0.06, 0.27] | 0.96 [0.83, 1.07] | 1.03 [1.02, 1.05] | 0.04 [−0.06, 0.12] | 1.01 [0.92, 1.11] |

- This is why E1 is estimation only. Pixel-locked models span β from −1.5 to 2.0 with their spectrum, an amplitude
  drift alone moves β by 1 (`white_drift` has the shape keys of `white`), and the image-locked models' β is not 0:
  0.27 and 0.06 for `img_gauss`, because the box removes the field's sub-pixel content, and 1.09 and 1.01 for `img_x`,
  whose rows are independent, so the 2 × 2 box averages two independent rows. Even the synthetic structure's β_S is not
  0 at (200, 400): its band reaches 50 cycles per image, 1/4 cycle per pixel at 200 px.
- `white` matches the display-corrected reference β_white = 1.996 at both contrasts.

Verdicts of the rule on these models (second-round planning computation, 2026-10-15: an independent numpy
implementation of these definitions through the display path, with 20,000 bootstrap resamples per interval; it agrees
with `metrics.gaussian_highpass`, `noise_corrected_lag` and `structure_std` to 7e-15 on fields of sd 9). There are 200
independent realizations per model at (200, 400) and 100 at (400, 800), 8 pairs per configuration each. H3-type
verdicts use the same draws without `C_jit`, at 0.005. Entries are "cell: count", with cells as in the verdict table.
In the planning code the 400 px reference of realization k is shared by both contrasts, so H4 and H5 are counted over
the 200 distinct references (the card's synthetic validation draws one reference per contrast).

| model | reading | predicted cell | (200, 400), H1/H2-type | (200, 400), H3-type | (400, 800), H1/H2-type | (400, 800), H3-type | H4 rejections | H5 rejections |
|---|---|---|---|---|---|---|---|---|
| `white` | (A) | 1 | 1: 200 | 1: 199, 5: 1 | 1: 99, 7: 1 | 1: 98, 5: 2 | 2 of 200 | 0 of 200 |
| `white_drift` | (A) | 1 | 1: 200 | 1: 198, 5: 2 | 1: 100 | 1: 100 | 1 of 200 | 2 of 200 |
| `ar1` | (A) | 1 | 1: 200 | 1: 199, 5: 1 | 1: 100 | 1: 100 | 200 of 200 | 0 of 200 |
| `pix_x` | (A) | 1 | 1: 198, 7: 2 | 1: 198, 5: 2 | 1: 99, 7: 1 | 1: 100 | 200 of 200 | 0 of 200 |
| `pix_gauss` | (A) | 1 | 1: 199, 7: 1 | 1: 199, 5: 1 | 1: 99, 7: 1 | 1: 99, 5: 1 | 0 of 200 | 200 of 200 |
| `ipjit_x` | (A′) | 2 | 2: 199, 5: 1 | (1: 198, 5: 2) | 2: 100 | (1: 100) | 200 of 200 | 2 of 200 |
| `jit_x` | (B) | 3 | 3: 199, 4: 1 | (4: 191, 6: 9) | 3: 100 | (4: 100) | 200 of 200 | 2 of 200 |
| `jit_gauss` | (B) | 3 | 3: 200 | (4: 198, 6: 2) | 3: 100 | (4: 100) | 1 of 200 | 200 of 200 |
| `img_x` | (C) | 4 | 4: 200 | 4: 199, 6: 1 | 4: 100 | 4: 100 | 200 of 200 | 2 of 200 |
| `img_gauss` | (C) | 4 | 4: 200 | 4: 200 | 4: 100 | 4: 100 | 1 of 200 | 200 of 200 |
| `mix_x` | (D) | none | 7: 200 | 7: 200 | 5: 72, 7: 28 | 5: 72, 7: 28 | 200 of 200 | 1 of 200 |
| `mix_gauss` | (D) | none | 5: 1, 7: 199 | 5: 1, 7: 199 | 5: 79, 7: 21 | 5: 79, 7: 21 | 0 of 200 | 200 of 200 |

H3-type entries in parentheses are not predictions: H3 has no jitter, so (A′) and (B) do not apply to it.

- **Opposite-direction verdicts: 0 of 5,100 runs** (3,400 at (200, 400), 1,700 at (400, 800); every run of a model with
  a predicted reading, in every hypothesis type it applies to). Over all runs of these models, D's bound nearest 0
  stayed at least 2.35 (|d| units, `ar1` at (200, 400)) on the predicted side, D_jit's lower bound for the (B) models
  at least 13.8 (`jit_gauss`, (200, 400)), and D_jit's upper bound for `ipjit_x` at most −27.1.
- **Same-direction misreadings: 13.** Under (A) they are cell 5 in H3-type runs, a chance `px` rejection: 10 of 1,500
  H3-type runs of the (A) models, against the comparison's level 0.005. In H1/H2-type runs the same chance rejections
  give cell 7 (6 runs), because cells 2 and 5 also need J. The other three are one chance rejection each: `ipjit_x` as
  cell 5 (P), `jit_x` as cell 4 (J) and `img_x` as cell 6 (I).
- **Power**: every model reached its predicted cell in at least 0.98 of its runs at both contrasts and in every
  hypothesis type it applies to (lowest: `white`, H3-type at (400, 800), 98 of 100). (C) was never read as (B), and
  (A′) never as (A).
- **H4** (isotropic high-pass) rejected in every reference of `ar1` and of every `_x` model, and in 0 to 2 of 200
  references of each isotropic model (5 of 1,200; expected 1,200 × 2/256 = 9.4).
- **H5** rejected in every reference of every `_gauss` model, and in 0 to 2 of 200 references of each row-independent
  model (9 of 1,600; expected 12.5).
- **Mixtures.** Cells by white share w, H1/H2-type (H3-type identical except where noted); 40 realizations at
  (200, 400) and 20 at (400, 800) per entry, and the w = 0.5 runs above:

  | w | (200, 400), `mix_x` | (200, 400), `mix_gauss` | (400, 800), `mix_x` | (400, 800), `mix_gauss` |
  |---|---|---|---|---|
  | 0.1 | 6: 40 | 6: 40 | 6: 20 | 4: 14, 6: 6 (H3-type 4: 10, 6: 10) |
  | 0.25 | 6: 40 | 6: 40 | 6: 11, 7: 9 | 6: 10, 7: 10 |
  | 0.5 | 7: 200 | 5: 1, 7: 199 | 5: 72, 7: 28 | 5: 79, 7: 21 |
  | 0.75 | 5: 40 | 5: 40 | 5: 20 | 5: 20 |
  | 0.9 | 5: 40 | 5: 40 | 5: 20 | 5: 20 |

  - The along-row keys see a pixel-white component far better than the first draft's 2-D keys. White noise's r4 `ip`
    `noise_frac` moves 0.894 → 0.949 between 400 and 800 px, against 0.982 → 0.995 with the 2-D keys. A half-white
    mixture therefore no longer reads as image-locked (first draft: cell "image-locked" in 181 of 243 runs at (400,
    800)).
  - At (400, 800) only a small white share in noise correlated across rows is not separated: `mix_gauss` with w = 0.1
    read as cell 4 in 14 of 20 runs (verdict table, cell 4).

### H1: the noise is pixel-locked on the artist chain (row chain, image-plane jitter)

- Derived from: mechanism items 1-3 and 006's hypothesis for later work. Its noise has two sources: K0 per (row, pass)
  and the jitter per (row, col, pass). Both are hashed per pixel, and the K offset along a row counts pixels. Its
  noise is independent across rows (item 3), so its locking is a property of the along-row statistics.
- **H1a**: (400, 800): `C_px` and `C_ip` on `row_s800` vs `row_s400`, `C_jit` on `row_s800_px` vs `row_s400`.
  **H1b**: (200, 400): the same with `row_s200` and `row_s200_px`.
- Observable: the noise families N_px and N_ip (12 along-row shape keys each) of these configurations.
- Test, level and correction: three comparisons, each with exact two-sided permutation p-values and Holm over its 12
  keys at 0.01/3. Family-wise 0.01 per hypothesis.
- Effect statistics: D and D_jit with their 99% (nominal) bootstrap intervals.
- Power: first Holm threshold 2.78e-4 ≥ 1.55e-4. The rule's power on the synthetic models is in the table above.
- Decision: the verdict table. Pixel-locking predicts **supported** at both contrasts: cell 1 (A), or cell 2 (A′).
  Mechanism labels: H4a, H5a.
- The two contrasts are separate hypotheses. 006 found that 200 px departs for the structure. Geometry-modulated
  pixel locking predicts that (200, 400) is where the noise departs too. No overall verdict combines H1a and H1b.

### H2: the noise is pixel-locked on the reference chain (image chain, image-plane jitter)

- Derived from: 006 amendment 1. Here the noise is only the variation between jitter realizations.
  - A jittered primary ray can change a path's `k_consumed`. That shifts K for the rest of the chain, so every later
    pixel is desynchronised. Mechanism items 2-3 then apply as for the row chain.
  - A separate hypothesis is warranted because the noise source is the jitter alone, so readings (B) and (A′) are a
    priori more plausible here than in H1. `C_jit` separates them: the pixel-jitter family holds the displacement at
    2/7 px and changes f.
  - Its rows may be coupled (item 3). H2 still uses the along-row keys of H1, so that the two chains are compared on
    the same keys (Attribution). That is why the synthetic gate includes the isotropic models for every hypothesis
    type. H5b reports whether the rows are coupled, and the estimation keys `iso_nlag.y` and `aniso` record the
    across-row behaviour at every side.
- **H2a**: `C_px`, `C_ip` on `s800` vs `s400`, `C_jit` on `s800_px` vs `s400`. **H2b**: the same with `s200` and
  `s200_px`.
- Observable, test, level, correction, effect statistics, power and decision as in H1, on these configurations.
  Mechanism labels: H4b, H5b.

### H3: the K chain alone gives pixel-locked noise (mechanism; row chain, zero jitter)

- Derived from: SPEC §3. With jitter 0 the primary hits do not depend on the seed. The only seed-dependent input is K0
  per (row, pass) (mechanism item 1), so this family isolates mechanism items 2-3 from the jitter. Readings (A′) and
  (B) do not apply.
- **H3a**: `C_px` and `C_ip` on `row_j0_s800` vs `row_j0_s400`. **H3b**: the same with `row_j0_s200`.
- Test, level and correction: two comparisons at 0.005 each, Holm over 12 keys. Family-wise 0.01 per hypothesis.
- Effect statistic: D with its 99% (nominal) bootstrap interval. Power: first Holm threshold 4.17e-4 ≥ 1.55e-4.
- Decision: the verdict table without the J conditions (cells 1, 4, 5, 6 and 7). Mechanism labels: H4c, H5c.
- With H1 it attributes the noise's locking to the jitter (Attribution above).

### H4: in the pixel frame the noise is anisotropic (mechanism items 2-3)

- Derived from: mechanism items 2-3. The chain couples pixels along a row by their K offset and leaves rows unrelated,
  so the noise's autocorrelation at a lag of τ px should differ between x and y. An isotropic noise (white, or any
  image-plane field with isotropic correlation) has equal expectations in x and y.
- **H4a** `row_s400`, **H4b** `s400`, **H4c** `row_j0_s400`: the 400 px member of each family, where the `px` and `ip`
  frames coincide (τ = 2 px, σ = 2.598 px), so H4 does not depend on the frame.
- Observable, per pair: `A = Σ_r w_r (px.r{r}.iso_nlag.x − px.r{r}.iso_nlag.y)` over the measured regions, with
  `w_r = |M_r| / Σ_r |M_r|` (mask-pixel weights). The keys are the lag-2 autocorrelations along x and along y of the
  isotropic high-pass `h_px^iso` (Two frames; the first draft's H4, unchanged). Dimensionless. For the row chain the y
  key is that of noise independent across rows (item 3), so H4a and H4c test whether the noise is correlated along
  rows.
- Test: exact two-sided sign-flip test of mean A = 0 over the 8 pairs (`ensemble.sign_flip_pvalue(A, "two-sided")`),
  level 0.01, no correction (one test per hypothesis). Two-sided because items 2-3 do not fix the sign.
- Power: rejection needs all 8 pairs to share a sign (Common definitions, Power). The detection limit is reported as
  2.49·sd(A).
- Decision: **supported** (anisotropic) iff p ≤ 0.01; **refuted** (no anisotropy detected, with the detection limit)
  otherwise.
- Estimation: `F.r{r}.aniso = iso_nlag.x − iso_nlag.y` per region, mean ± sd, at every side and in both frames.

### H5: across rows the noise is independent (mechanism item 3)

- Derived from: mechanism item 3. For the row chain it follows from SPEC §2-3, so a rejection there would contradict
  the SPEC or the analysis. For the image chain it is item 3's argument (the row offset differs between jitter
  realizations), not a consequence of the SPEC.
- **H5a** `row_s400`, **H5b** `s400`, **H5c** `row_j0_s400` (the 400 px member of each family, as H4).
- Observable, per pair: `Y = Σ_r w_r raw.r{r}.row_corr`, with the H4 weights and
  `raw.r{r}.row_corr = mean over (i, j) with (i, j) and (i + 1, j) in M_r of δ(i, j)·δ(i + 1, j)`, divided by the mean
  of δ² over M_r. It is uncentred, because δ has zero expectation at every pixel. Dimensionless.
- Test: exact two-sided sign-flip test of mean Y = 0 over the 8 pairs at 0.01. It is exact under independent rows:
  each row of δ = n_a − n_b is symmetric in distribution, so flipping the sign of every other row leaves the joint
  law of δ unchanged. That negates the numerator of every `row_corr` and leaves its denominator unchanged, so Y is
  symmetric about 0.
- Power: as H4; detection limit 2.49·sd(Y).
- Decision: **refuted** (rows correlated) iff p ≤ 0.01. Otherwise **not refuted**, reported with the detection limit:
  no across-row correlation of δ at 1 px larger than that limit was detected.
- H5 changes no H1-H3 verdict: their keys are along rows whatever the rows do. A refuted H5a or H5c is reported as a
  conflict with SPEC §2-3.
- Estimation: `raw.r{r}.row_corr`, mean ± sd, at every side.

### Estimation without verdicts

- **E1: the low-pass look at a common display side.** Not a hypothesis: no reading gives a prediction that the
  contrast can separate. A box downsample filters the structure as well as the noise (004 D7; 006's sub-pixel
  structure energy), so the structure term β_S is not 0, and β_q = β − β_S is non-zero under every reading unless the
  noise and structure spectra match. E1 estimates the size of the effect for pass presets.
  - Show a render of side 2s at side s, which averages 2 × 2 pixels per display pixel. Pixel-white noise loses a factor
    2² of its variance; 004 D7 measured that factor on smoke renders.
  - Keys, for the contrast (s, 2s) at the common side s:
    - *native*: the side-s pair as above;
    - *down*: each half render of the side-2s pair box-downsampled 2 × 2 on its `sum` (004's definition: the mean of
      each 2 × 2 block of per-pixel sums), then displayed with `smallpaint_display(·, P)`;
    - for both: the `ip` high-pass at side s (σ_ip(s)), the mask `M_r` of the side-s object-id map, `c.r{r}.noise_var
      = var_M(h_a − h_b)/2` and `c.r{r}.structure_cov = cov_M(h_a, h_b)`, both in display bytes², population form.
    - E1 uses the 2-D `metrics.gaussian_highpass`, not the frames' along-row filter: it measures the displayed 2-D
      noise-to-structure ratio, not locking.
  - `q_r = mean_pairs(noise_var) / mean_pairs(structure_cov)` per variant. A mean `structure_cov` ≤ 0 makes `q`
    undefined. At full scale the analysis then stops and reports it (smoke scale: Method, "Smoke run").
  - `β_r = log2` of the native/down noise-variance ratio, `β_S,r = log2` of the native/down structure ratio and
    `β_q,r = β_r − β_S,r = log2(q_r(native)/q_r(down))`. β, β_S and β_q are their medians over the measured regions,
    each with a 99% percentile bootstrap interval (`CI_DECISION`; pairs resampled within each configuration, 100,000
    resamples, one `default_rng(0)` per contrast and family, drawing native then down).
  - `P_eq = P·2^β_q`: the pass count per half render at which a native side-s render has the noise-to-structure ratio
    that the 2s render has at P = 64 when shown at side s. It assumes 001's `v(P) = σ_s² + σ_n²/P`.
  - For the row chain, the image chain and the zero-jitter row chain, at (200, 400) shown at 200 px and (400, 800)
    shown at 400 px.
  - Reference value: pixel-white noise of per-pixel sd σ through the display has
    `β_white = log2((σ² + 1/12)/(σ²/4 + 1/12))`, where 1/12 is the variance of the display's rounding to an integer
    (a definition). With σ = √(σ_n²/P) = 9.33 bytes (001 H4) it is 1.996.
- **Chain contrast** `row_sN` vs `sN` (N = 200, 400, 800) on N_px: whether K0 adds noise structure beyond the jitter's
  desynchronisation of the image chain.
- **Jitter footprint** `row_sN` vs `row_j0_sN` on N_px: the noise the jitter adds to K0 alone.
- **Pixel-jitter families in the `ip` frame**: `{p}sN_px` vs `{p}s400` on N_ip, with Δ_ip.
- **Noise profiles**, all regions, for the figure and the record: the autocorrelation of `h_px` (along-row high-pass)
  at the `px` lags 1, 2, 3, 4, 6, 8 and 12 px; of `h_ip` at the `ip` lags k·s/200, k = 1, 2, 3 (as 006's profile); and
  of the unfiltered δ at the `px` lags. All are taken along x and y; the y profiles show the across-row behaviour at
  more lags than H5.
- **K stride**: `r{r}.k_per_pass`, the mask mean of `k_consumed / P` over the 16 renders of a configuration, in draws
  per pixel per pass. Mechanism item 2 predicts the same value at every side.
- Every comparison reports the effect summary of all 12 keys and of `noise_std`, and per class: the largest
  |relative difference| of `noise_frac` and of `noise_std`, the largest |absolute difference| of `nlag.x`, the largest
  |Cohen's d|, and `min_attainable_p`. No all-key relative maximum is recorded, because the `nlag.x` means can be near 0.

## Method

### Configurations

All renders are 006's cached ensembles: 8 pairs, P = 64, `scene=gui`, `ghost=all`. The option sets and seeds are those
of 006's `jobs.py` (`ENSEMBLES[name]`), unchanged. No new render and no new seed block.

| name | side (px) | chain | f (fraction of side) | j = 2f (image-plane units) | f·s (px) | block (seeds) | role |
|---|---:|---|---|---|---|---|---|
| `row_s200` | 200 | row | 1/1400 | 1/700 | 1/7 | 31 (496-511) | H1b |
| `row_s400` | 400 | row | 1/1400 | 1/700 | 2/7 | 27 (432-447) | H1a, H1b, H4a, H5a, E1 |
| `row_s800` | 800 | row | 1/1400 | 1/700 | 4/7 | 32 (512-527) | H1a, E1 |
| `row_s200_px` | 200 | row | 1/700 | 1/350 | 2/7 | 34 (544-559) | H1b (`C_jit`) |
| `row_s800_px` | 800 | row | 1/2800 | 1/1400 | 2/7 | 35 (560-575) | H1a (`C_jit`) |
| `s200` | 200 | image | 1/1400 | 1/700 | 1/7 | 28 (448-463) | H2b |
| `s400` | 400 | image | 1/1400 | 1/700 | 2/7 | 0 (0-15) | H2a, H2b, H4b, H5b, E1 |
| `s800` | 800 | image | 1/1400 | 1/700 | 4/7 | 29 (464-479) | H2a, E1 |
| `s200_px` | 200 | image | 1/700 | 1/350 | 2/7 | 33 (528-543) | H2b (`C_jit`) |
| `s800_px` | 800 | image | 1/2800 | 1/1400 | 2/7 | 30 (480-495) | H2a (`C_jit`) |
| `row_j0_s200` | 200 | row | 0 | 0 | 0 | 39 (624-639) | H3b |
| `row_j0_s400` | 400 | row | 0 | 0 | 0 | 40 (640-655) | H3a, H3b, H4c, H5c, E1 |
| `row_j0_s800` | 800 | row | 0 | 0 | 0 | 41 (656-671) | H3a, E1 |

- 13 configurations, 208 cached renders. 006's `j0_*` configurations are not analysed (Common definitions).
- There is no `jobs.py`, because nothing is rendered. `analyze.py` takes its jobs from 006's `jobs.py`
  (`report.load_jobs_module`). At full scale its design check compares each configuration with the table above: side,
  chain, jitter (006's `--jitter` = j = 2f), block, the option set, and seeds `16·block … 16·block + 15`.

### Commands

`2026-10-15` is the date of the Opus commit that creates `experiments/007-2026-10-15-noise-locking/` with this
pre-registration: `date +%F` on that day, 2026-10-15 or later. Experiments 007, 008 and 009 are numbered and dated in
the order they run. The card finds the directory by its slug (PLAN.md). **Never run `make oracle`**: the render cache is
keyed by the binary's sha256 (Background, "Renders"). The synthetic and full runs are long and run detached (PLAN.md,
"Long runs").

```
sha256sum .cache/oracle-build/src/app/smallpaint_oracle
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python -m painterly_analysis.experiment run experiments/006-2026-10-09-jitter-units/jobs.py --budget 0
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/007-2026-10-15-noise-locking/analyze.py --synthetic --out-dir experiments/007-2026-10-15-noise-locking
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/007-2026-10-15-noise-locking/analyze.py
```

1. The checksum must be `066bb5d4247c556ad5232bfc4fff75dc5f37089840b23f1ecc8fdd9cb518828a`, and the budget-0 run must
   print `completed=256 remaining=0` (both verified on 2026-10-15). The budget-0 run starts no render. The smoke cache
   is checked by counting the `done` markers of 006's `build_ensembles(2, 4)` jobs (PLAN.md, step 0: 64 of 64, verified
   on 2026-10-15). Any other output means the oracle binary or a cache changed, and the analysis must not run. All
   three checks run before and after the card's work, with identical output.
2. `--synthetic` is the validation of the decision code (below). It writes `synthetic.json` and must pass before step
   3. It reads only the object-id maps of the cached renders.
3. Step 3 is the analysis. It writes `results.json` and the figures, re-runs from the cache and is deterministic:
   every test is exact, and every bootstrap draws from `numpy.random.default_rng(0)`.
4. Steps 2 and 3 are each run a second time into a scratch `--out-dir`, and their outputs must be byte-identical.

**Smoke run** (a code check only):

```
PAINTERLY_CACHE=.cache/006-smoke-cache PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/007-2026-10-15-noise-locking/analyze.py --pairs 2 --scale 4 --out-dir <scratch>
PAINTERLY_CACHE=.cache/006-smoke-cache PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/007-2026-10-15-noise-locking/analyze.py --synthetic --pairs 2 --scale 4 --out-dir <scratch>
```

- `.cache/006-smoke-cache` already holds exactly 006's `build_ensembles(2, 4)` (sides 50, 100 and 200), rendered by the
  same oracle binary: 64 of 64 jobs are done. The smoke run therefore renders nothing. Re-rendering them would cost
  184 CPU-s (the `wall_seconds` of their `meta.json`: 0.4 s at 50 px, 1.55 s at 100 px and 6.2 s at 200 px).
- Every printed line is prefixed `SMOKE (code check only): `, and the output files hold `"smoke": true`. With 2 pairs
  no comparison is powered (smallest p 2/C(4, 2) = 0.33; H4's and H5's 2/2² = 0.5), so every verdict is
  "inconclusive". A smoke run never writes into the experiment directory.
- At smoke scale (`--scale > 1`):
  - the distinct-render requirement is `2·pairs` (4);
  - the frame parameters (σ_F, τ_F and the profile lags) are those of the native side `s·scale`, in pixels: σ_px =
    2.598 px and τ_px = 2 px at every side, and σ_ip, τ_ip as at native 200, 400 and 800 px. Every lag is then an
    integer and nothing is rounded. The frames coincide at native 400 px (smoke side 100 px), so the bitwise-equality
    assertion of the frames runs in the smoke run too. Only the erosion follows the rendered side, `e = s/25` (2, 4
    and 8 px);
  - a profile lag with no pixel pair inside a region's mask is recorded as `null` and skipped. This occurs only at
    smoke scale (at 50 px: r2 at 6, 8 and 12 px, r3 and r5 at 12 px, r6 and r7 at 8 and 12 px; at 100 px: r2 at 12 px).
    At full scale every lag has pixel pairs in every mask, and a missing pair raises. A key whose per-pair values are
    all `null` is summarised as `null`; it is not averaged;
  - no bootstrap interval is computed: the intervals of D, D_jit and E1's β, β_S and β_q are recorded as `null`. The
    verdicts are inconclusive anyway, because no comparison is powered. (With 2 pairs, a resample repeats one pair with
    probability 1/2 per configuration, so both groups of a comparison are constant, with a pooled sd of 0, in about a
    quarter of the resamples.)
  - a `None` Cohen's d (pooled sd 0) and a mean `structure_cov` ≤ 0 raise at full scale only. At smoke scale such an
    E1 region's β_S and β_q are `null`, and the medians are over the other regions (`null` if none);
  - figure crops are divided by `scale` (25 px and 50 px tiles), the image-plane square of side s/4 is rounded to an
    integer side, and a crop that is not an integer multiple of its tile is resampled by nearest neighbour (display
    only). At full scale every crop side and factor is asserted to be an integer;
  - the configuration check runs against 006's `build_ensembles(pairs, scale)`. The README table and the seed reuse
    (`report.check_seed_reuse`) are checked at full scale only, as that function documents.
- The second smoke command runs `--synthetic` at smoke scale: 2 pairs, one replicate, sides 50, 100 and 200 px, the
  smoke object-id maps. The side-dependent model parameters (the drift factor, the σ_n of `jit_*` and `ipjit_x`) use
  the native side, and the image-locked fields' frequency limit becomes 24 cycles per image (below the 50 px Nyquist
  frequency, 25). It checks that the code runs, not the requirements, and prints no requirement verdict.

### Analysis

1. **Design check**:
   - the configurations, options and seeds above (full scale), or 006's `build_ensembles(pairs, scale)` (smoke);
   - `2·pairs` distinct `sum` arrays per configuration (sha256), and no pair with `δ ≡ 0`;
   - one object-id map per side, equal across the configurations of that side;
   - the measured regions: non-empty after `e(s)` at every side;
   - the frames coincide at native 400 px. σ is computed as `σ_ref·(native/400)`, so `px` and `ip` keys at 400 px
     are bitwise equal, and this is asserted.
2. **Per pair**: δ, `h_px` and `h_ip` (along-row) and `h_F^iso`; the noise keys, the estimation keys, H4's A and H5's Y
   at 400 px, the profiles and the common-side keys (E1). Per render: `k_per_pass`.
3. **H1-H3**:
   - `report.family_test(a, b, keys, level, labels=(a, b))` for each comparison, with level 0.01/3 (H1, H2) or 0.005
     (H3), on the 12 keys of the frame's N_F;
   - Δ per frame and class, D and D_jit with their intervals;
   - the verdict table, and the rejected keys by class.
4. **H4 and H5**: A and Y per pair, the sign-flip p-values, the decisions, the detection limits, and `aniso` and
   `row_corr` per region.
5. **Estimation**: as listed, including E1.
6. **Synthetic validation** (`--synthetic`), the gate:
   - Each synthetic half is a `sum`, `sum = P·(128 + m + n)` replicated on 3 channels, with P = 64. 128 is mid-grey of
     the byte range (a definition). Every synthetic key then goes through the same `smallpaint_display`, `luminance`
     and, for E1, `box_downsample_sum` path as the renders, with no wrap-around (the values stay far inside 0-255).
   - `m`, the shared image-locked structure: a fixed sum of `SYNTH_STRUCTURE_TERMS = 16` sinusoids whose radii are
     uniform in [2, 50] cycles per image (006's spectral band), with uniform directions and phases, drawn once from
     `default_rng(SYNTH_SEED)` and evaluated at each side's pixel centres `(i + 0.5)/s`. One factor scales it to a
     population sd of σ_s = √33.07 = 5.75 bytes over the 400 px image (001 H4).
   - `n`, drawn per half: a model field `z` scaled to unit sample variance over the whole image, times
     `SYNTH_NOISE_SD = √(σ_n²/P) = √(5573.6/64) = 9.33` bytes (001 H4: the noise variance passing the 9 px high-pass at
     P = 64). `white_drift` multiplies by a further `√(s/400)`.
   - Model fields `z` (`SYNTH_MODELS`, in this order; a model's position is its index):
     - `white`, `white_drift`: independent N(0, 1) per pixel;
     - `ar1`: `z[i, j] = φ z[i, j−1] + √(1 − φ²) ε[i, j]`, with `z[i, −1] ~ N(0, 1)` independent per row, φ =
       `SYNTH_AR_PHI = 0.6`, via `jax.lax.scan` along the columns;
     - `pix_x`: white noise low-passed along each row by circular convolution of length s with a Gaussian kernel of sd
       σ_n/√2 (transfer `exp(−2π²(σ_n²/2)ν_x²)`, ν in cycles per pixel), so the along-row correlation is Gaussian with
       sd σ_n = `SYNTH_SIGMA_N_REF_PX = 2` px and the rows are independent;
     - `pix_gauss`: the same filter on the s × s grid in 2-D (transfer `exp(−2π²(σ_n²/2)|ν|²)`), isotropic;
     - `ipjit_x`: as `pix_x` with σ_n = 2 px × j/`REFERENCE_JITTER` for the configuration's image-plane jitter j
       (`REFERENCE_JITTER` = 1/700, 006's);
     - `jit_x`, `jit_gauss`: as `pix_x`, `pix_gauss` with σ_n = 2 px × (configuration jitter f·s in px)/(2/7 px);
     - `img_x`: in each row independently, `Re Σ_ν c_ν exp(2πi ν u)` over integer frequencies `|ν| ≤ 99` cycles per
       image (`SYNTH_IMAGE_NU_MAX`, below the 200 px Nyquist frequency, 100), with independent complex normal `c_ν` of
       variance `exp(−2π²ℓ²ν²)`, where ℓ = `SYNTH_SIGMA_N_REF_PX`/400 = 1/200 of the side (2·s/400 px). It is
       evaluated at the pixel centres `u = (j + 0.5)/s` by an inverse FFT along the row;
     - `img_gauss`: `Re Σ_ν c_ν exp(2πi ν·u)` over `|ν_x|, |ν_y| ≤ 99`, variance `exp(−2π²ℓ²|ν|²)`, at
       `u = ((j + 0.5)/s, (i + 0.5)/s)` by a 2-D inverse FFT. The same continuous field model is sampled at every side,
       so both image-locked models are exactly image-locked and free of aliasing;
     - `mix_x`, `mix_gauss`: `√w · white + √(1 − w) · img_x` (or `img_gauss`), each part of unit variance, w =
       `SYNTH_WHITE_SHARE = 0.5`, rescaled to unit variance.
   - Configurations, in the order `SYNTH_CONFIGS` (a configuration's position is its index): per contrast its own
     400 px reference (`ref@200-400`, `ref@400-800`), the image-plane jitter configuration (`ip200`, `ip800`) and the
     pixel-jitter configuration (`px200`, `px800`); for E1 `e1_native200`, `e1_down400`, `e1_native400` and
     `e1_down800`. They use the 006 object-id maps of their sides, so the masks are the experiment's. H3-type verdicts
     use the same draws without `C_jit`, at 0.005.
   - Random streams: the halves of configuration c of model m in replicate i come from
     `numpy.random.default_rng((SYNTH_SEED, i, model_index, configuration_index))` with `SYNTH_SEED = 0` (fixed before
     any run; its value is arbitrary). Every replicate is independent and reproducible. Each replicate-contrast's
     bootstrap uses `default_rng(0)` exactly as the analysis does.
   - Replicates: `SYNTH_REPLICATES = 10` per model and contrast, 8 pairs each. E1 uses replicate 0 with
     `SYNTH_E1_PAIRS = 64` pairs per E1 configuration, for every model. The prediction table is replicate 0 (its 400 px
     column from `ref@200-400`).
   - Required (a failure means the design or the code is defective; the card stops and reports the failing
     requirement with its numbers, the real renders are not analysed, no rule is tuned, and no other seed is tried):
     1. no opposite-direction verdict in any replicate (Common definitions, "Error control"): for `white`,
        `white_drift`, `ar1`, `pix_x`, `pix_gauss` and `ipjit_x` no cell 3, 4 or 6; for `jit_x`, `jit_gauss`, `img_x`
        and `img_gauss` no cell 1, 2 or 5;
     2. the predicted cell (1 for (A), 2 for (A′), 3 for (B), 4 for (C)) in at least one replicate of each model,
        contrast and hypothesis type (`ipjit_x`, `jit_x` and `jit_gauss` are H1/H2-type only), so the decision path
        reaches every decided reading;
     3. H4 rejects in at least one `ar1` replicate, and H5 in at least one `pix_gauss` replicate;
     4. E1 code check, `white` at both contrasts: the 99% interval of β contains β_white = 1.996 (above).
   - Expected false-failure rate of a correct design, from the planning runs (Hypothesis, "Readings"):
     - requirement 1: negligible. An opposite-direction verdict needs D's interval on the far side of 0. It occurred
       in 0 of 5,100 second-round planning runs, and in every run of a model with a predicted reading the bound
       nearest 0 stayed at least 2.35 (|d| units) on the predicted side;
     - requirements 2 and 3: below 10⁻¹⁶. Every model reached its predicted cell in at least 0.98 of the planning
       runs, so missing it in all 10 replicates has probability at most 0.02¹⁰; H4 rejected in every `ar1` reference
       and H5 in every `pix_gauss` reference (200 of 200 each);
     - requirement 4: about 1.2% per contrast, 2.4% for both. The percentile interval undercovers slightly even at 64
       pairs (review simulation: coverage 0.988). In the first-draft planning runs it covered β_white in 60 of 60 seeds
       per contrast, with mean β 1.9960 and 1.9957 against 1.9959 predicted.
   - Any failed requirement stops the card, requirement 4 included; there is no exception and no re-run. Opus then
     decides as an amendment before analysis, with the failing numbers on record. A correct design is stopped this way
     with probability about 0.024, a cost accepted in exchange for a gate with no post-hoc route around it.
   - Reported, no requirement: the verdict counts of every model including `mix_x` and `mix_gauss`, the same-direction
     misreadings with their bound, H4's and H5's rejection counts for the models that predict none (expected 2/256 per
     reference), and E1 for every model.
   - It writes `synthetic.json` (prediction table, verdict counts, H4 and H5 counts, E1, the requirements with their
     numbers) into its `--out-dir`; Results reports that file.
7. **Outputs**:
   - `results.json` (real renders only): every number in Results; the design-check record, mask sizes and parameters
     per side; per configuration means ± sd of every key; every comparison with p-values, Holm decisions, effect
     summaries and per-class maxima (the `largest_abs_rel_diff` that `report.family_test` computes over all keys is
     replaced by the per-class maxima); Δ by frame and class, D and D_jit with intervals; verdicts, readings and
     labels; H4; H5; E1; the estimation blocks; the figure encodings and crop bounds;
   - `synthetic.json`: from `--synthetic` (above);
   - `fig_nlag_profile_row.png`, `fig_nlag_profile_image.png` and `fig_nlag_profile_row_zero.png`. Each plots the
     region-4 autocorrelation of the along-row high-passed noise, mean ± sd over pairs, for one family. Top row x,
     bottom row y; left column the `px` frame against the lag in px (1-12); right column the `ip` frame against
     k = lag/(s/200). There is one series per side. Pixel-locking predicts coinciding series in the top left panel;
   - `fig_noise_crops.png`. The row chain's δ of pair 0, displayed as `clip(128 + δ, 0, 255)`: δ in display bytes at
     gain 1, offset at mid-grey 128. Every crop is centred on the region-4 mask centroid of that side's object-id map,
     rounded with `np.rint`: (88, 106) at 200 px, (176, 211) at 400 px, (352, 422) at 800 px (row, col). Top row: a
     100 × 100 px crop at 200, 400 and 800 px. Bottom row: the image-plane square of side s/4 (50, 100 and 200 px) at
     the same centre, shown at 100 px (pixel-repeated at 200 px, identity at 400 px, box-downsampled at 800 px);
   - `fig_common_scale.png`: a 200 × 200 px back-wall crop at the common side 400, rows 76-275 and cols 111-310 (centred
     on the 400 px region-4 centroid (176, 211)). Left, a native `row_s400` half render; right, a `row_s800` half render
     box-downsampled to 400 px (as in E1), with the same crop. Both have P = 64;
   - every figure is at most 1 MB, draws no text, and has its encoding and crop bounds recorded in `results.json`.

### Estimated cost

- Rendering: none (0 oracle CPU-s). The budget-0 check reads the cache only. For the record, the cached renders took
  11,725 CPU-s (the `wall_seconds` of the 256 006 renders: 6.4 s at 200 px, 25.1 s at 400 px and 99.0 s at 800 px per
  render).
- Disk: no render, so the cache does not grow. Each run writes `results.json` or `synthetic.json` (about 1 MB at most)
  and at most five figures of at most 1 MB, and every run is repeated into a scratch directory, so the card needs at
  most about 15 MB including the smoke outputs and logs. Free space on the root filesystem, measured on 2026-10-15 at
  18:07 UTC (a measurement, not a requirement): 4,059,512,832 B.
- Analysis, from timings of the library calls on this machine (2026-10-15, load average 0.5-1.4 on 4 cores):
  `gaussian_highpass` 6.4, 34.6 and 123 ms at 200, 400 and 800 px; an along-row Gaussian high-pass written with
  `jnp.fft`, as `gaussian_highpass_axis` will be, 1.9, 5.7 and 13.0 ms; `noise_corrected_lag` 2.3, 4.6 and 17.1 ms;
  `structure_std` 2.0, 3.3 and 6.9 ms; `permutation_pvalue` 5.3 ms per key (8 vs 8, once compiled); the vectorised
  bootstrap of one hypothesis (three 100,000 × 8 index matrices, 36 keys) 0.67 s:
  - real renders: 104 pairs, about 1.5, 2.6 and 7.0 s per pair at 200, 400 and 800 px with every key and the 204
    profile lags (the profiles are about two thirds of it), 26 comparisons × 12 permutation p-values, 12 bootstrap
    blocks (6 hypotheses, 6 E1 contrasts), E1 and the figures. About 10 CPU-min per run, two runs;
  - `--synthetic`: 12 models × 10 replicates × 2 contrasts × 24 pairs with the estimation keys and profiles off
    (about 0.22, 0.56 and 0.94 s per pair at 200, 400 and 800 px including the field generation; the 400 px pairs
    include H4's and H5's keys), plus 36 p-values and one bootstrap per replicate-contrast: about 25 s per replicate at
    (400, 800) and 11 s at (200, 400), 72 min; E1 for every model at 64 pairs, about 11 min (the planning code took
    14-18 s per model). About 85 CPU-min per run, two runs. A machine shared with other CPU-bound jobs took up to twice
    as long in the planning, so the card runs it with nothing else running;
  - smoke run: 0 renders, under 1 CPU-min per command.
- Pre-registration planning computation (not part of the card; the object-id maps only):
  - first draft: about 6.4 CPU-h with 4 processes on 4 cores. The verdict runs took about 1.4 s per model and
    realization at (200, 400) (50 CPU-min for 299 realizations) and about 10.6 s at (400, 800) (5.0 CPU-h for 243); the
    E1 coverage runs (60 seeds, 64 pairs) 30 CPU-min; the prediction tables 3 CPU-min;
  - second round (2026-10-15): about 6 CPU-h, 4 to 5 processes on 4 cores for about 1.4 h: 12 models at 200
    realizations for (200, 400) and 100 for (400, 800), the isotropic H4 on 200 references, the mixture sweep, the
    prediction table and E1;
  - inside the card, 300 replicates per model and contrast (the rule-of-three size for a 0.01 bound) would cost about
    18 CPU-h with per-pair library calls. That is why the card's gate uses 10 replicates, and the calibration is this
    pre-registration computation.

### Pre-registration review

- Second review round (2026-10-10): applied 18, rejected 0. The findings are dated 2026-10-10; the edits were applied
  and the planning recomputed on 2026-10-15. Twelve findings on this draft (S1-S12) and six cross-experiment findings
  (X1-X6). The final read-only recheck raised four issues on this draft, each the same as one below and applied with
  it: the `make oracle` guard (X3), the block allocation (X1), the directory date (S12) and the detached long runs (S8).
  - S1 (blocker): the locking keys are taken along rows (`metrics.gaussian_highpass_axis`, 12 keys per frame, Holm
    over 12), and `nlag.y` leaves N_F. H4 keeps the first draft's isotropic high-pass as its own keys. H5 tests row
    independence. Row-independent synthetic models (`_x`) gate every hypothesis type next to the isotropic ones. The
    predictions and the power were re-derived (second-round planning). Verified from SPEC §2-3 and by simulation: with
    the 2-D keys a row-independent image-locked model never read as image-locked; with the along-row keys it read as
    cell 4 in every run but one.
  - S2: the cell-4 reading at (400, 800) states the pixel-white share it cannot separate, from the second-round
    mixture sweep, and the Conclusion reports cell 4 at (400, 800) only with the (200, 400) cell.
  - S3: "D < 0", "D_jit > 0" and "D_jit < 0" are defined by the interval bounds.
  - S4: cell 1 is split into (A), "not P, not J", and (A′), "not P, J, D_jit < 0", with the synthetic model `ipjit_x`.
  - S5: requirement 4's escape clause is removed; any failed requirement stops the card.
  - S6 (blocker): smoke rules: no bootstrap intervals, the raises at full scale only, and keys that are all `null` are
    not averaged.
  - S7, X6: `--synthetic` writes `synthetic.json`; `results.json` holds the real renders only.
  - S8, X6: `pair_keys` switches, a vectorised and tested `report.bootstrap_cohen_d`, re-measured costs, detached long
    runs.
  - S9: one bootstrap rng per hypothesis, drawing the configurations in the order reference, sN, sN_px.
  - S10: `SYNTH_CONFIGS`; one reference per contrast; E1 and the prediction table from replicate 0.
  - S11: step 0 records the oracle checksum, the budget-0 count of the full cache and the done-marker count of the
    smoke cache, and repeats them at the end.
  - S12: the directory is dated by the Opus pre-registration commit (`2026-10-15`), as Opus decided for 007-009, instead of
    either option of the finding.
  - X1: the seed blocks of 008 (42-45) and 009 (46-67).
  - X2: `report.draw_line` has 006's dash defaults and stroke.
  - X3: the full oracle sha256, and never run `make oracle`.
  - X4: jitter is given as f (j = 2f), frequencies as ν, and the `_px` suffix is told apart from the `px.` prefix.
  - X5: `CI_DECISION = (0.5, 99.5)`.

## Results

Pending: written by the analysis card (PLAN.md, Order of work, step 7).

## Conclusion

Pending: drafted by the analysis card (`DRAFT (Haiku) — pending Opus review.`), then finalized by Opus.
