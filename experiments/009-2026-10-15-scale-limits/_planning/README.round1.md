# Experiment 009: does image-locking hold above 800 px, and is the 200 px departure undersampling? (scale limits)

## Background

- `docs/plan.md`, "What makes the look":
  - item 3 (scan-line chaining): each path's counter K starts where the previous pixel's path in the same row ended, and
    only diffuse hits advance K. The chained K stream is what makes the converged texture: a per-path random start gives
    pattern correlation 0.11 against 0.63 for the row chain, "which breaks the look". Experiment 003 measured the same
    with the oracle: 0.126 for `lane:1` against 0.590 for `row`.
  - item 1 (spiral sampling): u1 = u2 = vdC(K), so the bounce direction of a diffuse event is set by K and the surface
    normal alone.
- `docs/spec.md`:
  - §2: a diffuse event does `K ← K + 1; u = vdc(K)`, where `vdc` reverses the bits of K. Only diffuse events advance K.
    Every other random decision (jitter, closure) is hashed from (seed, row, col, pass).
  - §3, `chain=row`: one chain per (row, pass), walking the columns of the row left to right from
    `K0 = rng_u32(seed, PURPOSE_LANE_K0, 0, row, 0, pass) mod 2^22`. The oracle stores pixel (row, col) at
    `sum[row, col]` (`smallpaint_oracle.cpp`, `Film`), so a chain runs along array axis 1.
    - The texture key `slag.x` pairs pixels along axis 1, i.e. along a chain.
    - `slag.y` pairs them along axis 0, i.e. across chains, whose K0 are independent.
  - §7: the Blender jitter is a fraction f of the fitted side, default 1/1400. The oracle's `--jitter` is in image-plane
    units, j = 2f, and its largest displacement is j·s/2 = f·s px at side s.
    - The smallpaint camera (`camcr`) puts pixel (row, col) of an s px render at the image-plane point
      ((2·row − s)/s, (2·col − s)/s)·tan(π/4), before jitter.
- `experiments/006-2026-10-09-jitter-units/` (final) measured with scale-equivariant metrics (Common definitions):
  - 400 and 800 px are indistinguishable on all 18 texture keys T in three families: image chain, row chain, and row
    chain with zero jitter. Every departure involves 200 px.
  - Row chain at f = 1/1400 (006 H1-row): (200, 800) rejects 1 key, `r4.slag.x`, 0.1310 ± 0.0301 vs 0.2047 ± 0.0149
    (abs −0.0737, d −3.11). It is the only one of 18 keys to reach complete separation there, so its size may be
    inflated by that selection.
  - Row chain at f = 0 (006 H4): (200, 400) rejects 5 keys and (200, 800) rejects 7: `r2.slag.y`,
    `r3.structure_std` to `r7.structure_std` (five keys) and `r6.slag.y`. (400, 800) rejects none (smallest p 9.32e-4).
  - The zero-jitter amplitude converges with size. `r4.structure_std` is 6.788, 7.176 and 7.273 at 200, 400 and 800 px:
    steps +0.388 and +0.097, a ratio of 4.0 (4.0 to 5.5 in r3, r4 and r6). `r4.slag.x` steps by +0.048 and +0.026 at
    f = 1/1400, and by +0.040 and +0.020 at f = 0.
  - The 1/1400 footprint removes 32-52% of the structure variance at every size. Removing it raises `structure_std` by
    21-44%.
  - "Hypotheses for later work" names the two questions of this experiment:
    - "Image-locking holds above 800 px": a row-chain 1600 px family at 1/1400 and 0, comparisons (400, 800),
      (800, 1600) and (400, 1600) on T at 0.01/3, and the shrinking steps as a secondary.
    - "The 200 px departure is undersampling": with f = 1/400, (200, 800) on T at 0.01 should reject 0 of 18 keys. "If
      rejections remain, the departure comes from the chain."
  - Decision 3: cross-resolution acceptance (M3 on) uses sides of at least 400 px "until the 200 px departure is
    explained".
  - Lessons, which this design follows:
    - (a) replicates must be independent: with `chain=image` and jitter 0, every seed renders the same image;
    - (b) a rule of "any rejection anywhere" does not separate competing readings, so each hypothesis gets the contrast
      that separates its readings;
    - (c) strict per-key dominance rules need a noise floor or are estimation only;
    - (d) with 8 vs 8 pairs and Holm, a rejection means complete separation, so verdicts are paired with effect statistics;
    - (e) units are named every time.
- Class departures (200 px minus 800 px) of 006's row-chain renders, with A, X and Y as defined below. Each cell gives
  the difference of means, its 95% percentile bootstrap interval (10,000 resamples, seed 0) and the exact 8-vs-8
  permutation p-value. They are computed from 006's per-pair values (Prior exposure).

  | footprint | A (log amplitude) | X (along the chain) | Y (across chains) |
  |---|---|---|---|
  | f = 0 (blocks 39 vs 41) | −0.0772 [−0.0826, −0.0714], p 1.55e-4 | −0.0455 [−0.0559, −0.0351], p 1.55e-4 | −0.0564 [−0.0637, −0.0481], p 1.55e-4 |
  | f = 1/1400 (blocks 31 vs 32) | −0.0233 [−0.0353, −0.0116], p 1.4e-3 | −0.0167 [−0.0367, +0.0029], p 0.146 | −0.0017 [−0.0308, +0.0311], p 0.93 |

  - At f = 0, A, X and Y are all lower at 200 px (p at the 8-vs-8 floor of 1.55e-4).
  - At f = 1/1400, the amplitude A is lower at 200 px. The X and Y intervals contain 0, so these class statistics do not
    show a direction for that departure. Whether a chain part concentrates in X is tested on fresh blocks (H3,
    estimation).
- `experiments/004-2026-10-08-resolution-dependence/`: filters fixed in pixels cannot separate pixel-locking from
  image-locking. This experiment therefore keeps 006's scale-equivariant metrics.
- Experiments 007 and 008 run before this one. 007 re-analyses 006's renders and renders nothing. 008 renders the
  row-chain jitter dose-response at 400 px in blocks 42-45. This experiment takes blocks 46-67 (seeds 736-1087), not the
  four blocks 46-49 first allocated to it, because H2 and H3 need 16 to 32 new pairs per side (Method, "Block
  allocation").
- Geometry of coincident pixels:
  - `camcr` computes `(2·row − s)/s` in double. For an integer factor m, pixel (m·row, m·col) of an m·s px render has
    numerator and denominator scaled by m, both exact, so the correctly rounded quotient is the same double. The two
    pixels have bit-identical unjittered rays.
- **Prior exposure.** Computations on cached renders made for this registration:
  1. 006's per-pair values of eight row-chain configurations (`row_s200`, `row_s400`, `row_s800`, `row_j0_s200`,
     `row_j0_s400`, `row_j0_s800`, `row_s200_px`, `row_s800_px`), recomputed from the cache with 006's frozen
     `_measure_configuration`. They equal 006's `results.json` `summary` exactly (336 key means and sds, 0 mismatches).
     The class departures above, every step and z-value quoted in H1, and every power number below come from them.
  2. The object-id maps (hits of the unjittered primary rays) of 006's row-chain renders satisfy
     `id_800[::4, ::4] == id_200`, `id_800[::2, ::2] == id_400` and `id_400[::2, ::2] == id_200` exactly.
  3. The largest row total of `k_consumed` over the 48 cached 800 px row-chain renders (Method, Cost).
  No texture key was computed on subsampled renders. Blocks 46-67 do not exist yet.
  - Selection. D_0 and D_1400 (H3) were selected by 006's tests on blocks 39 vs 41 and 31 vs 32. The shape summaries
    above use the same blocks. Their selection noise would bias a contrast computed on them toward the chain reading
    (H3), so H3 decides on blocks that selected nothing (fresh frame). The 006 blocks enter H3 only as estimation.

## Hypothesis

### Common definitions

- **Blocks and pairs.** A block is 16 half renders, seeds 16b to 16b + 15 for block b, i.e. 8 pairs of consecutive
  seeds (16b + 2i, 16b + 2i + 1). Every half render uses `chain=row`, P = 64 passes, `scene=gui` and `ghost=all` (the
  oracle defaults).
- **Configurations.** `row_sN` has f = 1/1400 at side N px, `row_j0_sN` has f = 0, and `row_f400_sN` has f = 1/400.
  - Every replicate is independent: the row chain's hashed K0 depends on the seed, also at f = 0 (006 amendment 1:
    16 distinct renders in each `row_j0_*` configuration). The design check verifies it for every block.
- **Footprints.** Units are always named. f is a fraction of the side and j = 2f is in image-plane units.

  | footprint | f (fraction of the side) | j = 2f (image-plane units, oracle `--jitter`) | largest displacement f·s at 200 / 400 / 800 / 1600 px |
  |---|---|---|---|
  | default | 1/1400 | 1/700, the oracle default (not passed) | 1/7, 2/7, 4/7, 8/7 px |
  | zero | 0 | 0 (`jitter=0.0`) | 0 |
  | pixel-wide at 200 px | 1/400 | 1/200 (`jitter=0.005`) | 1/2 px at 200, 2 px at 800 (not rendered at 400 or 1600) |

  At f = 1/400 the footprint is a square of side 1/200 of the image, as wide as one 200 px pixel.
- **Frames.** Each comparison uses a named set of blocks (`jobs.FRAMES`; Method table):
  - *8-pair frame*: the first block of each configuration. It is used by H1, the reproduction of 006, E1 to E3 and
    the profile.
  - *H2 frame*: blocks 48 + 50 (`row_f400_s200`) and 49 + 51 (`row_f400_s800`), 16 pairs per side. It is used by H2,
    which also selects D_400 on it.
  - *Fresh frame*: blocks that selected no departure set. It is used by H3, by the 1/1400 reference departure of H2,
    and by E4 (H3's contrasts) and E5:
    - f = 1/1400: blocks 52, 56, 58, 60 (`row_s200`) and 53, 57, 59, 61 (`row_s800`), 32 pairs per side;
    - f = 0: blocks 54, 62 (`row_j0_s200`) and 55, 63 (`row_j0_s800`), 16 pairs per side;
    - f = 1/400: blocks 64, 66 (`row_f400_s200`) and 65, 67 (`row_f400_s800`), 16 pairs per side.
  - *Pooled frame*: every block of a configuration. Estimation only (E5), because it contains the selection blocks.
- **Scale-equivariant metrics**, as in 006 and unchanged. Each is evaluated at the side s of the measured image, with
  reference side s₀ = 400.
  - High-pass: `metrics.gaussian_highpass` of the luminance of a half render's display bytes, with
    σ(s) = (9/√12)·s/s₀ px, on the half-sample-symmetric extension.
  - Regions: SPEC §9 ids 2-8 (not the light, id 9), eroded with radius e(s) = 4·s/s₀ px. Regions are measured by 006's
    rule: a region counts only if it is non-empty in every measured image, after both the scaled erosion and 006's fixed
    4 px erosion. 006 measured regions 2-7; region 8 is behind the camera.
  - Lag: τ(s) = s/200 px.
  - For each measured region r and pair (a, b): `r{r}.structure_std = sqrt(cov₀(hp_a, hp_b))`, and `r{r}.slag.x` and
    `r{r}.slag.y` from `metrics.noise_corrected_lag` at lag τ(s) along axis 1 and axis 0.
  - **T** is the 18 keys `r{r}.structure_std`, `r{r}.slag.x` and `r{r}.slag.y` of the six measured regions.
  - Estimation-only keys: `r{r}.mean.{R,G,B}` and `r{r}.spectral_slope` (frequency band 2 to 50 cycles per image).

  | side (px) | σ (px) | e (px) | τ (px) | profile lags ℓ·s/200, ℓ = 1, 2, 3 (px) |
  |---:|---:|---:|---:|---|
  | 200 | 1.2990 | 2 | 1 | 1, 2, 3 |
  | 400 | 2.5981 | 4 | 2 | 2, 4, 6 |
  | 800 | 5.1962 | 8 | 4 | 4, 8, 12 |
  | 1600 | 10.3923 | 16 | 8 | 8, 16, 24 |

- **Subsampled render.** `sub(R, m)` keeps the rows and columns ≡ 0 (mod m) of a render R's `sum`, `k_consumed` and
  `object_id` arrays, for an integer factor m. For R at side m·s, it holds exactly the image-plane points of an s px
  render (Background, Geometry). It is written `s ← m·s` and is always measured with the side-s parameters and the
  side-s masks.
  - The design check requires its object-id map to equal the native s px map exactly.
- **Pointwise contrast PC(s ← m·s, f).** The native s px configuration at footprint f (pairs (a, b)) against
  `sub(·, m)` of the m·s px configuration at the same f (pairs (c, d)), on a family of T keys.
  - Each native pixel and its coincident pixel have:
    - the same unjittered ray, bit for bit;
    - the same jitter distribution, uniform in ±j image-plane units (±f·s px at side s) on each axis around the
      pixel's point, hashed from different (row, col), so independent but identically distributed;
    - the same distribution of the hashed closure choices and of their row's K0;
    - the same passes, the same metric parameters and the same mask.
  - Only the chain differs. In the s px render the pixel's predecessors in its row are 1/s of the side apart. In the
    m·s px render they are 1/(m·s) apart, and there are m times as many.
  - Each pixel's whole path finishes before the next starts (SPEC §3), and every chain stays below 2^22 draws (design
    check), so both renders use the exact vdc range.
- **Class statistics, per pair.** Means over the measured regions:
  - A = mean over r of ln(`r{r}.structure_std`), the log amplitude;
  - X = mean over r of `r{r}.slag.x`, along the chain;
  - Y = mean over r of `r{r}.slag.y`, across chains.
  - A step or a departure is a difference of ensemble means, e.g. A(800 px) − A(400 px).
- **Decomposition at footprint f** (fresh frame). For each key i of T, with M_i(·) the ensemble mean of key i:
  - the departure Δ_i = M_i(native 200) − M_i(native 800), each measured at its own side;
  - the chain part c_i = M_i(native 200) − M_i(sub 200 ← 800);
  - the sampling part u_i = M_i(sub 200 ← 800) − M_i(native 800).
  - This is exact: Δ_i = c_i + u_i. The same holds for A, X and Y.
  - The chain share χ(f) is the median over the departure set D_f of c_i / Δ_i. χ = 0 means the departure is all
    sampling, and χ = 1 that it is all chain.
  - D_0 is the 7 keys that 006 H4 rejected at (200, 800): `r2.slag.y`, `r3.structure_std`, `r4.structure_std`,
    `r5.structure_std`, `r6.structure_std`, `r6.slag.y` and `r7.structure_std`. D_1400 is `r4.slag.x`, which 006 H1-row
    rejected. D_400 is the set of keys that H2 rejects on the H2 frame (empty unless H2 is refuted).
  - Every D_f was selected on blocks outside the fresh frame (Background, Prior exposure).
- **Cross-size structure correlation** `r{r}.xcorr`, estimation only.
  - For a native pair (a, b) and a subsampled pair (c, d) on the same mask:
    ρ_x = [cov(a, c) + cov(a, d) + cov(b, c) + cov(b, d)] / 4 / sqrt(cov(a, b) · cov(c, d)).
    The fields are high-passed, and each covariance is the population form, centred by its own masked mean.
  - The noise of independent renders drops out of every covariance in it, so ρ_x estimates the correlation, at the same
    image-plane points, of the textures shared by the two configurations. It is 1 iff one is a positive multiple of the
    other.
  - It is computed for pair i of the native ensemble with pair i of the subsampled ensemble.
  - The reference ρ_self uses the same formula between two different pairs of one ensemble: pairs 2i and 2i + 1, the
    same texture, so it estimates 1. It is computed for both ensembles of a contrast.
- **Draws per sample** `r{r}.k_per_sample`, estimation only: the region mean of (k_a + k_b) / (2P), where k is
  `k_consumed` and P = 64 the pass count. It is the number of diffuse draws per pixel per pass.
- **Significance.** Each hypothesis has family-wise level 0.01 (`SIGNIFICANCE`; it is not the oracle option `alpha`).
  How it is divided is stated in each hypothesis.
  - Every p-value is a two-sided permutation p-value from `ensemble.permutation_pvalue`.
    - At 8 vs 8 it is exact over the C(16, 8) = 12,870 splits; the smallest attainable p is 2/12,870 = 1.55e-4.
    - At 16 vs 16 and larger (H2, H3, E5) the number of splits exceeds `PERMUTATION_MAX_EXACT`, so it uses 100,000
      random permutations with `jax.random.PRNGKey(0)`, as the function defines. The smallest attainable p is
      1/100,001.
  - Holm (`ensemble.holm`, through `report.family_test`) runs across the keys of each family. The power guard is
    `report.family_test`'s.
- **Bootstrap.** Intervals enter the decisions of H1 (readings), H2 (removal) and H3 (χ).
  - 10,000 resamples from one `numpy.random.default_rng(0)`, 95% percentile intervals (`CI_PERCENTILES = (2.5, 97.5)`,
    the conventional level, not tuned);
  - pairs are resampled within each configuration and frame, and one draw of pair indices per (configuration, frame)
    is shared by every statistic of that frame;
  - the measurements of one render at its own side and after subsampling are resampled together.
  - Interval relations: an interval [lo, hi] *contains* x iff lo ≤ x ≤ hi, and otherwise *excludes* it; it *lies
    below* x iff hi < x and *above* x iff lo > x.
- **Estimation.** Every comparison reports:
  - `ensemble.effect_summary` for T and the estimation-only keys;
  - the largest |rel| (with its abs diff) and the largest |d|, over T and over all keys;
  - `min_attainable_p` and the first Holm threshold.
  "Indistinguishable" is written only together with those numbers.

### H1: image-locking holds above 800 px

- Derived from 006: (400, 800) rejects 0 of 18 in three families, and Blender renders are usually larger than 800 px.
  If the converged texture is a field on the image plane, renders at 800 and 1600 px sample one field, and the
  scale-equivariant metrics agree.
- Two families, each on the 8-pair frame:
  - **H1-default**: `row_s400`, `row_s800`, `row_s1600` (f = 1/1400);
  - **H1-zero**: `row_j0_s400`, `row_j0_s800`, `row_j0_s1600` (f = 0).
- Readings of the step from 800 to 1600 px:
  - **I, converged.** The texture does not change above 400 px. Every step from 800 to 1600 px is 0.
  - **G, converging as 1/s².** Take a part of the texture that is uncorrelated from pixel to pixel at every side, i.e.
    finer than 1/1600 of the side.
    - Its point samples have the same variance at every side. The high-pass keeps the fraction
      R(s) = mean over the 2s × 2s frequency grid of (1 − exp(−2π²σ(s)²|ν|²))², with ν in cycles per pixel of the
      extended grid.
    - 1 − R(s) is 0.1415, 0.0354, 0.0088 and 0.0022 at 200, 400, 800 and 1600 px. It falls exactly 4-fold per
      doubling, because σ(s) in pixels doubles.
    - Its high-passed lag-τ correlation likewise scales as 1/σ²: −0.118 at 200 px and −0.0064 at 800 px (simulated
      white noise through `metrics.gaussian_highpass` and `metrics.noise_corrected_lag`).
    - So every step of A, X and Y from such a part shrinks 4-fold per doubling. 006's zero-jitter `r4.structure_std`
      steps have ratio 4.0.
    - G predicts a step from 800 to 1600 px of a quarter of the step from 400 to 800 px. In the zero family that is
      +0.0210 / 4 = +0.0053 for A (a fully white texture would give +0.0033) and about +0.024 for `r4.structure_std`.
    - In the default family the 400 → 800 A step is −0.0043 (z −1.87), so G predicts a step near 0 there, as I does.
  - **N, new size dependence.** A step from 800 to 1600 px that G does not predict: not shown smaller than the
    400 → 800 step, or of the opposite sign.
  - **S, converging slower than 1/s²** (named so that it is not read as N): a step of the same sign as the 400 → 800
    step, larger than G predicts and shown smaller than the 400 → 800 step.
  - **F, converging faster than 1/s²**: a step of the same sign as the 400 → 800 step, shown non-zero and shown smaller
    than G predicts.
- **Test**: in each family, (800, 1600) on T, Holm across the 18 keys at 0.01 (one comparison per family). The first
  Holm threshold is 0.01/18 = 5.56e-4, which admits p = 1.55e-4 and 3.11e-4.
- Not part of the decision:
  - (400, 800) is the **reproduction check**. It uses 006's renders at 006's level 0.01/3 and must reproduce 006's
    p-values and its 0 rejections exactly (design check).
  - (400, 1600) is estimation only (E1). It spans two doublings and reuses 006's 400 px blocks, so it also detects the
    known 400 → 800 step against a sharper reference: with no change above 800 px, simulated from 006's per-pair means
    and sds, it rejects at least one key at 0.01/3 with probability 0.87 (sd at 1600 px = sd at 800 px) or 0.97
    (half of it) in the zero family, and 0.20 or 0.50 in the default family.
- **Reading rule**, for each family and class statistic Z ∈ {A, X, Y}, on the 8-pair frame:
  - s2 = Z(800) − Z(400), s3 = Z(1600) − Z(800), from the same bootstrap; g = s2/4 is G's prediction (the 4-fold
    shrink per doubling derived above).
  - **I** iff the interval of s3 contains 0 and the interval of s3 − g excludes 0;
  - **G** iff the interval of s3 excludes 0 and the interval of s3 − g contains 0;
  - **I or G** (not separated) iff both intervals contain 0;
  - otherwise both exclude 0. With σ the sign of the point estimate of s2 (+1 if it is 0), "σ's side" of 0 is the
    side of the 400 → 800 step:
    - **F** iff the interval of s3 lies on σ's side and the interval of s3 − g on the opposite side;
    - **S** iff the intervals of s3 and of s3 − g lie on σ's side and the interval of s3 − s2 on the opposite side;
    - **N** otherwise: the interval of s3 lies on the opposite side (a reversal), or the interval of s3 − g lies on
      σ's side and the interval of s3 − s2 does not lie on the opposite side.
  - The reading of a rejected key is the reading of its class: `structure_std` keys belong to A, `slag.x` keys to X and
    `slag.y` keys to Y.
- **Decision**, per family:
  - **supported** iff (800, 1600) rejects 0 of 18 keys;
  - **partially supported (G)** iff it rejects at least 1 key and the class of every rejected key reads G or F: the
    residual shrinks at least 4-fold per doubling, as the 1/s² tail of the metric does;
  - **refuted** iff it rejects at least 1 key and the class of some rejected key reads N, S or I. The verdict names the
    reading. Only N is "new size dependence"; I means a key-level change that its class statistic does not show;
  - **inconclusive** otherwise: a rejection whose class reads "I or G", and none reads N, S or I.
- Paired effect statistics (E1): s2 and s3 of A, X, Y and of every `structure_std` key and `r4.slag.x`, with intervals.
  A step ratio s3/s2 is reported only where the interval of s2 excludes 0; otherwise the steps alone are reported.
- Power:
  - (800, 1600), 8 vs 8 at 5.56e-4, exact permutation p-values on normal data (planning simulation, 2,000 draws):
    rejection probability 0.31 at d = 2, 0.59 at d = 2.5, 0.81 at d = 3, 0.94 at d = 3.5 and 0.99 at d = 4.
  - The detectable effect at 0.94 is 3.5·sd(800 px), if the 1600 px sd is not larger (more pixels per region). From
    006's 800 px sds:
    - f = 1/1400: `structure_std` 0.066-0.324 bytes (rel 0.010-0.069), `slag` 0.029-0.144;
    - f = 0: `structure_std` 0.086-0.212 bytes (rel 0.013-0.029), `slag` 0.020-0.069.
  - Departures of the size seen at 200 px (f = 0: `r3.structure_std` −0.94 bytes, `r2.slag.y` −0.18; f = 1/1400:
    `r4.slag.x` −0.074) would be detected.
  - Simulated from 006's per-pair means and sds (400 draws):
    - with no change above 800 px, (800, 1600) rejects at least one key with probability 0.00-0.02 in both families;
    - under G on every T key (s3 = s2/4), it does so with probability 0.02-0.03 in the default family, and 0.21 (sd at
      1600 px = sd at 800 px) or 0.51 (half of it) in the zero family. A zero-family rejection is therefore not N by
      itself, and the reading rule decides.
  - Reading rule, zero family A (planning simulation, 400 draws, 1,000 bootstrap resamples, sd at 1600 px = sd at 800 px
    or half of it): truth I reads I in 0.86-0.89 (G 0.01-0.03, N 0.04-0.06); truth G reads G in 0.90-0.92 (S or F
    0.08-0.10, N 0); truth N (s3 = s2) reads N in 0.95-0.97. SE(s3) is 0.0010-0.0013, so G's +0.0053 is 4-5 SE from
    I's 0. A reading only matters together with a rejection, which under I has probability 0.00-0.02.
  - Where the interval of s2 contains 0 (z of s2: default A −1.87, X +0.95, Y −0.20; zero Y +0.49), G's prediction is
    near 0 and the rule reads "I or G" in 0.76-0.90 of draws under I or G. Zero-family X (z +2.47) reads "I or G" in
    0.45-0.68.
  - 8 pairs are kept. G's `r4.structure_std` step (+0.024, d ≈ 0.9 at the 800 px sd) would need far more pairs to be
    detected by a rejection; the interval rule on A separates G from I without that.

### H2: a footprint as wide as a 200 px pixel removes the 200 px departure (footprint test)

- Derived from 006's later-work hypothesis.
  - If the 200 px departure is a sampling effect, content finer than the 200 px pitch causes it.
  - A footprint of f = 1/400 averages each pixel over a square 1/200 of the side wide: the whole 200 px pixel. That is
    12.25 = (700/200)² times the area of the 1/1400 footprint, which already removes 32-52% of the structure variance.
  - Its box transfer is sinc(ν/200) at ν cycles per side. That is 2/π = 0.64 at the 200 px Nyquist frequency (100) and
    0 at 200 cycles per side.
- Observable: T, `row_f400_s200` vs `row_f400_s800` on the H2 frame (16 vs 16 pairs), Holm across the 18 keys at 0.01.
  The first Holm threshold is 5.56e-4. 006's counts at the same pair of sizes are 7 (f = 0) and 1 (f = 1/1400), on
  8 vs 8.
- Removal conditions, for each of Z ∈ {A, `r4.slag.x`}:
  - Δ_400(Z) is the 200 − 800 px departure on the H2 frame. Δ_1400(Z) is the 1/1400 departure on the fresh frame
    (32 vs 32 pairs, blocks that selected nothing, so it is free of 006's selection).
  - *no departure*: the interval of Δ_400(Z) contains 0;
  - *reduction*: the interval of Δ_400(Z) − Δ_1400(Z) excludes 0 and lies on the opposite side of 0 from the point
    estimate of Δ_1400(Z).
  - Why A and `r4.slag.x`: A is the class statistic whose 1/1400 departure 006 established (p 1.4e-3, Background), and
    `r4.slag.x` is the key 006 rejected. X's 1/1400 departure was not established (p 0.146), so its reduction could
    not be shown with useful power.
- Decision:
  - **supported (removed)** iff 0 keys are Holm-rejected and, for both A and `r4.slag.x`, no departure and reduction
    hold;
  - **partially supported (reduced)** iff 0 keys are rejected, reduction holds for both, and the interval of Δ_400
    excludes 0 for at least one of them;
  - **refuted** iff at least 1 key is Holm-rejected;
  - **not shown** otherwise.
- What it answers. H2 is the practical question for previews: does a pixel-wide footprint make 200 px match 800 px?
  Lesson (b) applies, so H2 is not the mechanism test:
  - a box is not an ideal low-pass. Under the sampling reading it reduces the departure but need not remove it, so a
    refutation does not refute that reading;
  - a footprint also moves hit points, and so K consumption. It may weaken a chain effect too, so a support does not
    exclude the chain reading.
  H3 separates the two readings.
- Paired effect statistics: the 200 − 800 px departures of A, X and Y at f = 0, 1/1400 and 1/400 with intervals
  (fresh frame for 0 and 1/1400, H2 frame for 1/400), beside the rejection counts.
- Power. Footprints change the seed-to-seed sd (006: the median sd ratio per doubling of f over T is 1.12, the upper
  quartile 1.41), so the f = 1/1400 sds understate it at f = 1/400, 1.81 doublings larger. The stand-in sds are:
  - 200 px: `row_s200_px` (f = 1/700, the measured footprint nearest 1/400 at 200 px). `r4.slag.x` has sd 0.0700
    there, against 0.0301 at 1/1400;
  - 800 px: `row_s800` (f = 1/1400) times 1.12^1.81 = 1.23, or 1.41^1.81 = 1.86 (upper quartile). (006's
    `row_s800_px` has f = 1/2800, below 1/1400, so it cannot stand in.)
  - 16 vs 16 at 5.56e-4 (t approximation): rejection probability 0.59 at d = 1.44, 0.69 at d = 1.55, 0.95 at d = 2.0
    and above 0.99 at d = 2.5. 8 vs 8 (exact) would give 0.14 at d = 1.55, so the 16 new pairs are used.
  - A `r4.slag.x` departure as large as 006's at 1/1400 (−0.0737) has d = 1.44 with the 1/700 sd at 200 px, and
    d = 2.5 with both sds grown by the median factor: refutation power 0.59 to above 0.99.
  - Removal conditions (planning simulation, 400 draws, 1,000 bootstrap resamples, Δ_1400 on 32 vs 32): if the
    footprint removes the departure, P(supported) is 0.80 (median sd growth) or 0.71 (upper quartile) when the true
    1/1400 departure equals 006's, and 0.24 or 0.18 when it is half of 006's. If the footprint halves the departure,
    P(supported) is 0.04-0.11; if it leaves it unchanged, 0.00.

### H3: the 200 px departure is undersampling, not a chain effect (mechanism)

- Readings:
  - **U, undersampling.** The 200 px render samples the same image-plane texture as the 800 px render. The departure
    arises in the measurement, because the 200 px grid aliases content finer than its pitch, or retains less of it
    (R(s) in H1).
    - Derived from 006's Conclusion, point 3, and from the shape of the f = 0 departure: A, X and Y are all lower at
      200 px (Background). That is the signature of a pixel-white part, whose high-passed lag-τ correlation is −0.118 at
      200 px and −0.0064 at 800 px (H1, G).
  - **C, chain effect.** The texture itself differs at 200 px, because the chain step is 1/200 of the side.
    - Derived from plan item 3 and SPEC §2-§3. A pixel's K start is K0 plus the draws of its predecessors in the row.
      A path's draw count depends on its geometry and on its own u values, i.e. on the low bits of K. So the low bits
      at a pixel's start depend on the paths of the pixels before it. The texture that seeds share is built from this
      dependence: without it (per-path start) the look breaks.
    - A memory of q chain steps spans q/s of the side, 4 times more at 200 px than at 800 px. It acts along the chain,
      so C predicts a chain part concentrated in X. That prediction is not derived from 006's 1/1400 shape (whose X
      interval contains 0) and is tested as estimation on the fresh frame.
- Contrast that separates them: PC(200 ← 800, f) for f ∈ {0, 1/1400, 1/400}, on the fresh frame:
  - f = 0: `row_j0_s200` vs `sub(row_j0_s800, 4)`;
  - f = 1/1400: `row_s200` vs `sub(row_s800, 4)`;
  - f = 1/400: `row_f400_s200` vs `sub(row_f400_s800, 4)`.
  - U predicts no difference at any footprint: the same points, the same footprint, the same metric, so c_i = 0 for
    every key. C predicts c_i ≈ χ·Δ_i with χ > 0 wherever the departure has a chain part.
- Tests at footprint f, level 0.01/3 per footprint (Bonferroni over the three footprints):
  - when D_f is not empty, the footprint's 0.01/3 is split in two halves, which keeps H3's family-wise level at
    3 × 2 × 0.01/6 = 0.01:
    - *departure family*: the keys of D_f, Holm across |D_f| at 0.01/6. It decides the class;
    - *outside family*: the keys of T not in D_f, Holm at 0.01/6. A rejection there is a chain difference without a
      departure, which U excludes;
  - when D_f is empty: all of T, Holm at 0.01/3, as the outside family.
- χ(f) and its interval are computed on the fresh frame (Common definitions, Decomposition).
- Classes at footprint f, when D_f is not empty:
  - **undersampling** iff no key of D_f is rejected and the interval of χ(f) lies below 1/2;
  - **chain** iff a key of D_f is rejected and the interval of χ(f) lies above 1/2;
  - **mixed** iff a key of D_f is rejected and the interval of χ(f) lies below 1/2. A chain part is detected, and the
    sampling part is the larger;
  - **chain part detected, share unresolved** iff a key of D_f is rejected and the interval of χ(f) contains 1/2;
  - **inconclusive** iff no key of D_f is rejected and the interval of χ(f) does not lie below 1/2.
  - 1/2 (`DOMINANCE`) is where the two parts of the exact decomposition Δ = c + u are equal. It defines which part
    dominates; it is not a tuned value. Using the interval, not the point estimate, gives the split a noise floor
    (lesson c).
  - When D_f is empty (possible only for f = 1/400): **no departure**.
  - Any footprint is also flagged **chain difference without a departure** if its outside family rejects a key.
  - What "undersampling" means: no chain part is detected and the chain share is shown to be below 1/2. It does not
    exclude a small chain part (with χ = 1/4, f = 1/1400 reads undersampling with probability 0.78, Power).
  - If the fresh frame does not reproduce a departure (Δ_i near 0), the interval of χ is wide and the footprint reads
    inconclusive or share unresolved. E5 reports the fresh departures with their intervals.
  - Each footprint is classified on its own. Jitter moves hit points and so K consumption, so a chain part may differ
    between footprints.
- Footprint verdicts for H3: chain → refuted; share unresolved → inconclusive; inconclusive → inconclusive; mixed →
  partially supported; undersampling → supported; no departure → supported. A flagged footprint's verdict is then
  lowered to partially supported if it was higher.
- **Decision**: H3's verdict is the lowest footprint verdict in the order refuted < inconclusive < partially supported
  < supported. Hence:
  - **supported** iff the footprints with a departure (f = 0 and 1/1400, and 1/400 if D_400 is not empty) all read
    undersampling and no footprint, 1/400 included, shows a chain difference without a departure;
  - **refuted** iff some footprint reads chain.
  The class and flags are reported per footprint.
- Paired effect statistics, per footprint (fresh frame):
  - χ(f) with its interval;
  - c and u for A, X and Y with intervals (C predicts c concentrated in X; U predicts c ≈ 0);
  - ρ_x per region beside ρ_self (U predicts ρ_x ≈ ρ_self ≈ 1);
  - every rejected key with its effect, in both families.
- Power (planning simulation, 400 draws per cell; normal per-pair values with 006's means and sds; the subsampled keys
  have the native 200 px sd (the same pixel count and passes); correlation 0 between a render's subsampled and native
  800 px values; 10,000 Monte Carlo permutations; 1,000 bootstrap resamples; D_f family at 0.01/6):
  - f = 1/1400, 32 vs 32, D_1400 = {`r4.slag.x`}, Δ = 006's −0.0737 (d = 2.45 for c = Δ):
    - χ = 0: undersampling 1.00;
    - χ = 1/4: undersampling 0.78, a chain part detected 0.19;
    - χ = 1/2: a chain part detected 0.92 (share unresolved 0.87, chain 0.035, mixed 0.013), undersampling 0.033;
    - χ = 0.6: chain 0.21, share unresolved 0.79, undersampling 0.00;
    - χ = 1: chain 1.00.
    - If the true departure is half of 006's: undersampling 0.86 at χ = 0, chain 0.83 at χ = 1, undersampling 0.03 at
      χ = 1/2.
  - f = 0, 16 vs 16, D_0 (7 keys, d = 2.0 to 7.3 for c = Δ): undersampling 1.00 at χ = 0; mixed 0.98 at χ = 1/4; a
    chain part detected 0.99 at χ = 1/2; chain 1.00 at χ = 1. Half of 006's departure: 1.00, 0.16 (undersampling
    0.84), 0.98 and 1.00.
  - Why 32 pairs at f = 1/1400. For the single key of D_1400 at χ = 1/2 (d = 1.225), 0.9 power at 0.01/6 needs
    29 pairs per side (t approximation; 0.52 at 16, 0.81 at 24 and 0.94 at 32 pairs). With 16 fresh pairs and a
    departure half of 006's (it was selected as the only complete separation among 18 keys), χ = 0 and χ = 1 would be
    classified correctly with probability 0.65 and 0.55 only (simulation at 0.01/3). Undersampling at χ ≥ 1/2 stays at
    most 0.04 at every size tried: that is the interval's error rate, not the test's.
  - With the 18 keys of T as the deciding family (first Holm threshold (0.01/3)/18), 0.9 power at χ = 1/2 would need
    38 pairs per side, which is why D_f decides and T \ D_f only flags.
  - At f = 1/400, D_400 is unknown before H2. The outside family on all of T at 0.01/3 with 16 vs 16 has a first Holm
    threshold of 1.85e-4, above the smallest attainable p (1.0e-5).

### Estimation without verdicts

- **E1, convergence pattern** (8-pair frame, both families, 200 → 400 → 800 → 1600 px):
  - the steps of every `structure_std` key (r2-r7), of `r4.slag.x`, and of A, X and Y, with intervals;
  - the ratio of each step to the next where the denominator step's interval excludes 0 (006's secondary: the 800 → 1600
    step of `structure_std` is smaller than the 400 → 800 step in r3-r7, and likewise for `r4.slag.x`). Per lesson (c)
    these are not decided key by key;
  - the H1 readings of A, X and Y with G's predicted numbers;
  - (400, 1600) on T, with Holm counts at 0.01/3 for reference only.
- **E2, pointwise image-locking** (8-pair frame): PC(200 ← 400, f), PC(400 ← 800, f), PC(800 ← 1600, f) and
  PC(400 ← 1600, f) for f ∈ {1/1400, 0}, i.e. factors m = 2, 2, 2 and 4.
  - Each reports effect summaries, p-values and Holm decisions on T at 0.01, for reference only, with no verdict. It
    also reports ρ_x, ρ_self, and the chain part c of A, X and Y.
  - If the texture is a field on the image plane, every contrast shows no difference and ρ_x ≈ ρ_self.
- **E3, footprint effects at a fixed side** (8-pair frame): `row_f400_s200` vs `row_s200` and `row_f400_s800` vs
  `row_s800` (f = 1/400 against 1/1400), and `row_j0_s1600` vs `row_s1600` (006's footprint rows extended to 1600 px).
- **E4, draws per sample**: `r{r}.k_per_sample` per configuration (8-pair frame), and native against subsampled in every
  pointwise contrast, in that contrast's frame. Under U the path statistics depend only on the image-plane point.
- **E5, the departures**: native 200 vs native 800 px at each footprint, on the fresh frame (these are the Δ_i of the
  decomposition, with intervals: whether the fresh blocks reproduce 006's departures) and on the pooled frame (40, 24 and
  32 pairs per side at 1/1400, 0 and 1/400). The pooled frame also repeats the decomposition and χ, as estimation only,
  because it contains the blocks that selected D_f. Holm counts at 0.01 for reference.
- **Profile**: `r4.slag.x` and `r4.slag.y` at image-plane lags ℓ/200 of the side (ℓ = 1, 2, 3) per side and footprint,
  as 006's `fig_slag_profile.png`, now with 1600 px (8-pair frame).

## Method

### Configurations

| configuration | side (px) | f (fraction of the side) | oracle options besides `chain=row`, `passes=64`, `size` | blocks (seeds) and frames | source |
|---|---:|---|---|---|---|
| `row_s200` | 200 | 1/1400 | none (default jitter) | 31 (496-511), 8-pair; fresh 52 (832-847), 56 (896-911), 58 (928-943), 60 (960-975) | 006 `row_s200` (cache); new |
| `row_s400` | 400 | 1/1400 | none | 27 (432-447), 8-pair | 006 `row_s400` = 004 `row_s400` = 003 `row` (cache) |
| `row_s800` | 800 | 1/1400 | none | 32 (512-527), 8-pair; fresh 53 (848-863), 57 (912-927), 59 (944-959), 61 (976-991) | 006 `row_s800` (cache); new |
| `row_s1600` | 1600 | 1/1400 | none | 46 (736-751), 8-pair | new |
| `row_j0_s200` | 200 | 0 | `jitter=0.0` | 39 (624-639), 8-pair; fresh 54 (864-879), 62 (992-1007) | 006 `row_j0_s200` (cache); new |
| `row_j0_s400` | 400 | 0 | `jitter=0.0` | 40 (640-655), 8-pair | 006 `row_j0_s400` (cache) |
| `row_j0_s800` | 800 | 0 | `jitter=0.0` | 41 (656-671), 8-pair; fresh 55 (880-895), 63 (1008-1023) | 006 `row_j0_s800` (cache); new |
| `row_j0_s1600` | 1600 | 0 | `jitter=0.0` | 47 (752-767), 8-pair | new |
| `row_f400_s200` | 200 | 1/400 | `jitter=0.005` | 48 (768-783), 8-pair and H2; 50 (800-815), H2; fresh 64 (1024-1039), 66 (1056-1071) | new |
| `row_f400_s800` | 800 | 1/400 | `jitter=0.005` | 49 (784-799), 8-pair and H2; 51 (816-831), H2; fresh 65 (1040-1055), 67 (1072-1087) | new |

- `jobs.py` declares each block as its own ensemble (`DESIGN`, 28 entries), the blocks of each configuration
  (`CONFIGURATIONS`, first block first: the 8-pair frame), and the H2 and fresh frames (`FRAMES`).
- Reused blocks: the six 006 blocks have exactly 006's option sets, so their cache keys are 006's.
  `report.check_seed_reuse` against experiments 001-004, 006 and 008 passes on this `jobs.py` (checked at
  registration, with 008's pre-registered `jobs.py`).
- **Block allocation.** The constraint allocated blocks 46-49 to this experiment. The design needs 22 new blocks:
  - 46-47: the two 1600 px configurations (H1);
  - 48-51: the H2 frame (16 pairs per side at f = 1/400, H2 Power);
  - 52-67: the fresh frame of H3, 32 pairs per side at f = 1/1400 and 16 at f = 0 and 1/400 (H3 Power). These blocks
    must be disjoint from 006's selection blocks and from the H2 frame, which selects D_400.
  Seeds 736-1087 are used by no earlier experiment (the highest seed used by 001-008 is 735, 008's block 45).
- The oracle binary is `.cache/oracle-build/src/app/smallpaint_oracle`, the binary of experiments 001-006, sha256
  `066bb5d4247c556ad5232bfc4fff75dc5f37089840b23f1ecc8fdd9cb518828a`. It is not rebuilt, and no oracle option is added.
- New renders: 352 (22 new blocks × 16): 160 at 200 px, 160 at 800 px and 32 at 1600 px. 96 reused renders are cached.
  `jobs.JOBS` has 448 jobs.

### Cost

- CPU per render, from the cache's `wall_seconds` (single-threaded oracle):
  - 200 px row chain: 6.0-6.1 s (means of `row_s200`, `row_j0_s200`, `row_s200_px`);
  - 800 px: 96.3-103.2 s (means of `row_j0_s800`, `row_s800`, `row_s800_px`; 99 s is used). The fastest of the 48
    renders took 95.06 s and the slowest 117.45 s;
  - 1600 px: 4 × 97 ≈ 390 s, since the cost scales with the pixel count (×4.2 from 200 to 400 px, ×3.8 from 400 to
    800 px).
- Total: 160 × 6.1 + 160 × 99 + 32 × 390 ≈ 29,300 CPU-s, i.e. 8.1 CPU-hours, about 2.0 h wall with 4 workers on an
  otherwise idle machine.
  - Of this, the 1600 px renders take 12,480 s, the H2 frame 3,360 s (2 block pairs of one 200 px and one 800 px
    block, 1,682 s each) and the fresh frame 13,460 s (8 block pairs). The fresh frame's blocks 56-67 add 10,100 s to
    the first draft's 19,200 s.
  - That is 34% of the one-day limit (86,400 CPU-s), so neither passes nor pairs are reduced.
- Disk: 39 bytes per pixel per render (`sum` 24, `k_consumed` 8, `object_id` 4, `image.ppm` 3), i.e. 7.44 GB (10^9
  bytes) for the new renders: 0.25 GB at 200 px, 3.99 GB at 800 px and 3.19 GB at 1600 px.
  - Free space on the cache filesystem at registration (2026-10-10, `df -B1 .cache`): 9,309,274,112 bytes (9.31 GB).
  - 008 runs first and needs 64 × 400² × 39 = 0.40 GB, which leaves 8.91 GB for 009: a margin of 1.47 GB. Other work
    shares the filesystem, so the preflight checks the space again before every render call (Commands).
- Memory per render: under 150 MB at 1600 px.
- Every row chain at 1600 px stays below 2^22 draws. The cached 800 px row-chain renders consumed at most 887,851 draws in
  one row over all 64 passes (`row_s800`, block 32, seed 518), i.e. about 13,900 per (row, pass) chain. A 1600 px row
  has twice the pixels, so about 27,700 draws per (row, pass) chain and about 1.78 M per row over all passes, below
  2^22 − 1 = 4,194,303. K therefore stays below 2^23, the generator's exact range (SPEC §3). The analysis checks the
  bound on every render.

### Commands

```
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/009-2026-10-09-scale-limits/analyze.py --preflight
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python -m painterly_analysis.experiment run experiments/009-2026-10-09-scale-limits/jobs.py --budget 90 --workers 4   # preflight, then this, repeated until exit 0
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/009-2026-10-09-scale-limits/analyze.py
```

- `--preflight` renders nothing. It checks the oracle sha256 above, the cache markers of the 96 reused renders, and the
  free disk space against the bytes of every job of 009 not yet done plus every job of 008's `jobs.py` not yet done. It
  exits non-zero on any failure, and then nothing is rendered. It is run again before every render call, so a
  shrinking disk stops the loop before a 100 MB 1600 px render fails partway through writing.
- `--budget 90`, not the protocol's 540 s, and `--workers 4` explicitly (`nproc` is 4).
  - 90 s is below the fastest cached 800 px row render (95.06 s), and the jobs run smallest side first. A job starts
    only when a slot frees before 90 s, which only a 200 px job does. So a 1600 px job starts only at the beginning of
    a call, and a call lasts at most one 1600 px render (about 390-470 s, the upper value 4 × 117 s).
  - About 51 calls are needed (about 3 at 200 px, 40 at 800 px with one wave of four renders each, and 8 at 1600 px),
    about 2.3 h of wall time.
- Stop rule for CPU contention: if any finished 1600 px render's `meta.json` `wall_seconds` exceeds 540 s (the
  protocol's per-call budget, `experiment.DEFAULT_BUDGET_SECONDS`), or if a render call does not return within
  10 minutes, stop and report CPU contention instead of calling again.
- Smoke run (code check only), with a scratch `PAINTERLY_CACHE` and `--out-dir`:
  `analyze.py --pairs 2 --scale 4`, sides 50, 100, 200 and 400. It rounds τ and e to the nearest integer of at least
  1 px, as 006 did, and says so. It never writes the committed outputs.

### Analysis

- `analyze.py` loads the cache and implements the Common definitions, H1-H3 and E1-E5. It reuses 006's measurement
  functions unchanged (PLAN.md). New code: `metrics.cross_structure_correlation` (ρ_x) with unit tests, and the
  subsampling, decomposition, class statistics, readings and bootstrap in `analyze.py`.
- **Design checks**, each of which stops the analysis on failure:
  - `jobs.DESIGN`, `CONFIGURATIONS` and `FRAMES` match the Method table (sides, f as a `Fraction`, blocks, seeds,
    options, frames), and no fresh block is a reused, H2 or first block;
  - seeds are unique, and `report.check_seed_reuse` passes against experiments 001-004, 006 and 008;
  - every render has P = 64. All renders of one side share one object-id map;
  - `sub(·, m)`'s object-id map equals the native map for every pointwise contrast;
  - every block has 16 distinct `sum` arrays (sha256), so no replicate repeats a render;
  - every render has at most 2^22 − 1 draws in each row over all passes, which bounds each (row, pass) chain;
  - consistency with 006: the 8-pair-frame values of the six reused configurations equal 006's `results.json` `summary`
    (mean and sd of every T and estimation-only key) exactly (`==`), the two (400, 800) comparisons reproduce 006's
    p-values and rejections exactly, and D_0 and D_1400 equal 006's rejected keys.
- **Outputs**:
  - `results.json`: parameters, regions, replicate counts, the chain bound, every comparison (effect summary,
    p-values, Holm decisions, `min_attainable_p`), the H1 readings, the H2 conditions, the decompositions, χ, the H3
    classes and flags, ρ_x and ρ_self, class statistics with intervals, k_per_sample, the decision records, and the
    figure encodings;
  - printed tables, one per hypothesis and estimation block;
  - figures, each at most 1 MB, drawn without text, with their encodings in `results.json` (PLAN.md):
    - `fig_grid_row.png`, `fig_grid_row_zero.png` and `fig_grid_row_f400.png`: pair 0 of each side (8-pair frame),
      box-downsampled to 200 px tiles;
    - `fig_points_default.png`, `fig_points_zero.png` and `fig_points_f400.png`: native 200 px, 800 px subsampled to
      the same points, and 800 px box-downsampled, as 200 px tiles (pair 0 of the fresh frame);
    - `fig_slag_profile.png`, `fig_steps.png` (A, X and Y against side), and `fig_decomposition.png` (Δ, c and u per
      key of D_f, fresh frame).
- Deterministic: exact or fixed-key permutation p-values and seed-0 bootstraps. A second run into a scratch
  `--out-dir` must reproduce every output byte for byte.
