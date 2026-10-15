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
    (abs −0.0737, d −3.11).
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
- Class summaries of 006's row-chain renders show that the two 200 px departures have different shapes. The values are
  computed from 006's per-pair values (the values behind its Table 1), with A, X and Y as defined below. For 200 minus
  800 px:
  - f = 0: A −0.0772, X −0.0455, Y −0.0564. Amplitude and both directions are lower at 200 px.
  - f = 1/1400: A −0.0233, X −0.0167, Y −0.0017. Only the along-chain direction is lower.
- `experiments/004-2026-10-08-resolution-dependence/`: filters fixed in pixels cannot separate pixel-locking from
  image-locking. This experiment therefore keeps 006's scale-equivariant metrics.
- Experiments 007 and 008 run before this one. 007 re-analyses 006's renders and renders nothing. 008 renders the
  row-chain jitter dose-response at 400 px in blocks 42-45. This experiment takes blocks 46-55.
- Geometry of coincident pixels:
  - `camcr` computes `(2·row − s)/s` in double. For integer k, pixel (k·row, k·col) of a k·s px render has numerator
    and denominator scaled by k, both exact, so the correctly rounded quotient is the same double. The two pixels have
    bit-identical unjittered rays.
  - Feasibility check, the only computation on cached renders made for this registration: the object-id maps (hits of
    the unjittered primary rays) of 006's row-chain renders satisfy `id_800[::4, ::4] == id_200`,
    `id_800[::2, ::2] == id_400` and `id_400[::2, ::2] == id_200` exactly. No texture key was computed on subsampled
    renders before this registration.

## Hypothesis

### Common definitions

- **Blocks and pairs.** A block is 16 half renders, seeds 16b to 16b + 15 for block b, i.e. 8 pairs of consecutive
  seeds (16b + 2i, 16b + 2i + 1). Every half render uses `chain=row`, P = 64 passes, `scene=gui` and `ghost=all` (the oracle defaults).
- **Configurations.** `row_sN` has f = 1/1400 at side N px, `row_j0_sN` has f = 0, and `row_f400_sN` has f = 1/400.
  - The 200 and 800 px configurations have two blocks each. The others have one block (Method table).
  - Every replicate is independent: the row chain's hashed K0 depends on the seed, also at f = 0 (006 amendment 1:
    16 distinct renders in each `row_j0_*` configuration).
- **Footprints.** Units are always named. f is a fraction of the side and j = 2f is in image-plane units.

  | footprint | f (fraction of the side) | j = 2f (image-plane units, oracle `--jitter`) | largest displacement f·s at 200 / 400 / 800 / 1600 px |
  |---|---|---|---|
  | default | 1/1400 | 1/700, the oracle default (not passed) | 1/7, 2/7, 4/7, 8/7 px |
  | zero | 0 | 0 (`jitter=0.0`) | 0 |
  | pixel-wide at 200 px | 1/400 | 1/200 (`jitter=0.005`) | 1/2 px at 200, 2 px at 800 (not rendered at 400 or 1600) |

  At f = 1/400 the footprint is a square of side 1/200 of the image, as wide as one 200 px pixel.
- **Frames.** A configuration's ensemble depends on the comparison.
  - *8-pair frame*: the first block of each configuration. It is used by H1, H2, every comparison that 006 made, and
    the estimation blocks E1 to E4.
  - *16-pair frame*: both blocks of each 200 px and 800 px configuration. It is used by H3 and E5, and by E4 for the
    three H3 contrasts.
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
  - Estimation-only keys: `r{r}.mean.{R,G,B}` and `r{r}.spectral_slope` (f_min = 2, f_max = 50 cycles per image).

  | side (px) | σ (px) | e (px) | τ (px) | profile lags k·s/200, k = 1, 2, 3 (px) |
  |---:|---:|---:|---:|---|
  | 200 | 1.2990 | 2 | 1 | 1, 2, 3 |
  | 400 | 2.5981 | 4 | 2 | 2, 4, 6 |
  | 800 | 5.1962 | 8 | 4 | 4, 8, 12 |
  | 1600 | 10.3923 | 16 | 8 | 8, 16, 24 |

- **Subsampled render.** `sub(R, k)` keeps the rows and columns ≡ 0 (mod k) of a render R's `sum`, `k_consumed` and
  `object_id` arrays. For R at side k·s, it holds exactly the image-plane points of an s px render (Background,
  geometry). It is written `s ← k·s` and is always measured with the side-s parameters and the side-s masks.
  - The design check requires its object-id map to equal the native s px map exactly.
- **Pointwise contrast P(s ← k·s, f).** The native s px configuration at footprint f (pairs (a, b)) against
  `sub(·, k)` of the k·s px configuration at the same f (pairs (c, d)), on T.
  - Each native pixel and its coincident pixel have:
    - the same unjittered ray, bit for bit;
    - the same jitter distribution, uniform in ±j image-plane units on each axis (hashed from different (row, col),
      so independent but identically distributed);
    - the same distribution of the hashed closure choices and of their row's K0;
    - the same passes, the same metric parameters and the same mask.
  - Only the chain differs. In the s px render the pixel's predecessors in its row are 1/s of the side apart. In the
    k·s px render they are 1/(k·s) apart, and there are k times as many.
  - Each pixel's whole path finishes before the next starts (SPEC §3), and every chain stays below 2^22 draws (design
    check), so both renders use the exact vdc range.
- **Class statistics, per pair.** Means over the measured regions R:
  - A = mean over r of ln(`r{r}.structure_std`), the log amplitude;
  - X = mean over r of `r{r}.slag.x`, along the chain;
  - Y = mean over r of `r{r}.slag.y`, across chains.
  - A step or a departure is a difference of ensemble means, e.g. A(800 px) − A(400 px).
- **Decomposition at footprint f** (16-pair frame). For each key k of T, with ensemble means m:
  - the departure Δ_k = m_k(native 200) − m_k(native 800), each measured at its own side;
  - the chain part c_k = m_k(native 200) − m_k(sub 200 ← 800);
  - the sampling part u_k = m_k(sub 200 ← 800) − m_k(native 800).
  - This is exact: Δ_k = c_k + u_k. The same holds for A, X and Y.
  - The chain share χ(f) is the median over the departure set D_f of c_k / Δ_k. χ = 0 means the departure is all
    sampling, and χ = 1 that it is all chain.
  - D_0 is the 7 keys that 006 H4 rejected at (200, 800): `r2.slag.y`, `r3.structure_std`, `r4.structure_std`,
    `r5.structure_std`, `r6.structure_std`, `r6.slag.y` and `r7.structure_std`. D_1400 is `r4.slag.x`, which 006 H1-row
    rejected. D_400 is the set of keys that H2 rejects. D_0 and D_1400 are fixed by 006. D_400 is fixed by H2, which
    does not use the subsampled renders.
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
  `k_consumed`. It is the number of diffuse draws per pixel per pass.
- **Significance.** Each hypothesis has family-wise level 0.01 (`SIGNIFICANCE`; it is not the oracle option `alpha`).
  - Every p-value is a two-sided permutation p-value from `ensemble.permutation_pvalue`.
    - At 8 vs 8 it is exact over the C(16, 8) = 12,870 splits.
    - At 16 vs 16, C(32, 16) exceeds `PERMUTATION_MAX_EXACT`, so it uses 100,000 random permutations with
      `jax.random.PRNGKey(0)`, as the function defines.
  - Holm (`ensemble.holm`) runs across the 18 keys of T in each comparison. A hypothesis with c comparisons runs each at
    0.01/c. The power guard is `report.family_test`'s.
- **Bootstrap** (estimation; no decision uses an interval):
  - 10,000 resamples from `numpy.random.default_rng(0)`, 95% percentile intervals;
  - pairs are resampled within each ensemble;
  - the measurements of one render at its own side and after subsampling are resampled together.
- **Estimation.** Every comparison reports:
  - `ensemble.effect_summary` for T and the estimation-only keys;
  - the largest |rel| (with its abs diff) and the largest |d|, over T and over all keys;
  - `min_attainable_p` and the first Holm threshold.
  "Indistinguishable" is written only together with those numbers.

### H1: image-locking holds above 800 px

- Derived from 006: (400, 800) rejects 0 of 18 in three families, and Blender renders are usually larger than 800 px.
  If the converged texture is a field on the image plane, renders at 400, 800 and 1600 px sample one field, and the
  scale-equivariant metrics agree.
- Two families, each on the 8-pair frame:
  - **H1-default**: `row_s400`, `row_s800`, `row_s1600` (f = 1/1400);
  - **H1-zero**: `row_j0_s400`, `row_j0_s800`, `row_j0_s1600` (f = 0).
- Readings:
  - **I, converged.** The texture does not change above 400 px. The steps from 800 to 1600 px are 0.
  - **G, converging as 1/s².** Take a part of the texture that is uncorrelated from pixel to pixel at every side, i.e.
    finer than 1/1600 of the side.
    - Its point samples have the same variance at every side. The high-pass keeps the fraction
      R(s) = mean over the 2s × 2s frequency grid of (1 − exp(−2π²σ(s)²|f|²))².
    - 1 − R(s) is 0.1415, 0.0354, 0.0088 and 0.0022 at 200, 400, 800 and 1600 px. It falls exactly 4-fold per
      doubling, because σ(s) in pixels doubles.
    - So every amplitude step from such a part shrinks 4-fold per doubling. 006's zero-jitter `r4.structure_std` steps
      have ratio 4.0.
    - G predicts a zero-family A step from 800 to 1600 px of about a quarter of the 400 → 800 step (+0.0210 / 4 =
      +0.0053; a fully white texture would give +0.0033), and a `r4.structure_std` step of about +0.024.
    - In the default family the 400 → 800 A step is already −0.0043, so I and G both predict a step near 0 there.
  - **N, new size dependence.** (800, 1600) departs, with a step at least as large as the 400 → 800 step.
- Tests: in each family, (400, 800), (800, 1600) and (400, 1600) on T, each at 0.01/3.
  - (400, 800) uses 006's renders. It must reproduce 006's p-values and its 0 rejections exactly (design check). It
    stays in the family so that every comparison has the level 0.01/3 that 006 registered.
- Decision, per family:
  - **supported** iff (800, 1600) and (400, 1600) reject 0 keys;
  - **partially supported (drift accumulates over two doublings)** iff (800, 1600) rejects 0 and (400, 1600) rejects at
    least 1;
  - **refuted** iff (800, 1600) rejects at least 1 key.
- Paired effect statistics (estimation, E1): the A, X and Y steps per doubling with intervals, their ratios, and per
  rejected key both steps and their ratio. The Conclusion says which reading (I, G or N) the intervals fit. Rejection
  counts cannot separate I from G, because G's step is below the detectable effect (Power).
- Power:
  - 8 vs 8: the smallest attainable p is 2/12,870 = 1.55e-4, and the first Holm threshold is (0.01/3)/18 = 1.85e-4. A
    rejection therefore needs complete separation.
  - Simulated (planning): the probability of complete separation is 0.58 at d = 3, 0.91 at d = 4 and 0.99 at d = 5.
  - The detectable effect at 0.91 is at most 4·sd(800 px), if the 1600 px sd is not larger (more pixels per region).
    From 006's 800 px sds:
    - f = 1/1400: `structure_std` 0.076-0.370 bytes (rel 0.011-0.079), `slag` 0.033-0.165;
    - f = 0: `structure_std` 0.098-0.242 bytes (rel 0.015-0.034), `slag` 0.023-0.079.
  - Departures of the size seen at 200 px (f = 0: `r3.structure_std` −0.94 bytes, `r2.slag.y` −0.18; f = 1/1400:
    `r4.slag.x` −0.074) would be detected.
  - G's `r4.structure_std` step (+0.024, d ≈ 0.9 at the 800 px sd) would not be detected with 8, 16 or 24 pairs (the
    detectable d at 0.9 power is about 4, 2.1 and 1.6). 8 pairs are kept. 16 pairs per side would cost about
    6,600 CPU-s more per family (8 more pairs at 400 and 1600 px) and still not detect it. E1 estimates it instead.

### H2: a footprint as wide as a 200 px pixel removes the 200 px departure (footprint test)

- Derived from 006's later-work hypothesis.
  - If the 200 px departure is a sampling effect, content finer than the 200 px pitch causes it.
  - A footprint of f = 1/400 averages each pixel over a square 1/200 of the side wide: the whole 200 px pixel. That is
    12.25 = (700/200)² times the area of the 1/1400 footprint, which already removes 32-52% of the structure variance.
  - Its box transfer is sinc(ν/200) at ν cycles per side. That is 2/π = 0.64 at the 200 px Nyquist frequency (100) and
    0 at 200 cycles per side.
- Observable: T, `row_f400_s200` vs `row_f400_s800` (8-pair frame, blocks 48 and 49), at 0.01. 006's counts at the same
  pair of sizes are 7 (f = 0) and 1 (f = 1/1400).
- Decision: **supported** iff 0 of 18 keys are Holm-rejected; **refuted** otherwise.
- What it answers. H2 is the practical question for previews: does a pixel-wide footprint make 200 px match 800 px?
  Lesson (b) applies, so H2 is not the mechanism test:
  - a box is not an ideal low-pass. Under the sampling reading it reduces the departure but need not remove it, so a
    refutation does not refute that reading;
  - a footprint also moves hit points, and so K consumption. It may weaken a chain effect too, so a support does not
    exclude the chain reading.
  H3 separates the two readings.
- Paired effect statistics: the 200 − 800 px departures of A, X and Y at f = 0, 1/1400 and 1/400 (8-pair frame) with
  intervals, beside the three rejection counts.
- Power: 8 vs 8, first Holm threshold 0.01/18 = 5.56e-4, smallest attainable p 1.55e-4. Simulated power is 0.80 at
  d = 3 and 0.94 at d = 3.5.
  - With 006's f = 1/1400 sds standing in for f = 1/400, the detectable effect at 0.94 is `structure_std` 0.16-0.75
    bytes (rel 0.034-0.16) and `slag` 0.073-0.39. The noisiest are region r2's lags at 200 px (sd 0.14-0.15).
  - A departure as large as 006's at f = 1/1400 (`r4.slag.x`, d −3.1) would be detected with probability about 0.83.

### H3: the 200 px departure is undersampling, not a chain effect (mechanism)

- Readings:
  - **U, undersampling.** The 200 px render samples the same image-plane texture as the 800 px render. The departure
    arises in the measurement, because the 200 px grid aliases content finer than its pitch, or retains less of it
    (R(s) in H1).
    - Derived from 006's Conclusion, point 3, and from the shape of the f = 0 departure: A, X and Y are all lower at
      200 px. That is the signature of a pixel-white part, whose high-passed lag-τ covariance is −0.0996 of its variance
      at 200 px and −0.0062 at 800 px.
  - **C, chain effect.** The texture itself differs at 200 px, because the chain step is 1/200 of the side.
    - Derived from plan item 3 and SPEC §2-§3. A pixel's K start is K0 plus the draws of its predecessors in the row.
      A path's draw count depends on its geometry and on its own u values, i.e. on the low bits of K. So the low bits
      at a pixel's start depend on the paths of the pixels before it. The texture that seeds share is built from this
      dependence: without it (per-path start) the look breaks.
    - A memory of m chain steps spans m/s of the side, 4 times more at 200 px than at 800 px. It acts along the chain.
      This fits the shape of the f = 1/1400 departure: X lower, Y unchanged.
- Contrast that separates them: P(200 ← 800, f) for f ∈ {0, 1/1400, 1/400}, 16-pair frame:
  - f = 0: `row_j0_s200` vs `sub(row_j0_s800, 4)`;
  - f = 1/1400: `row_s200` vs `sub(row_s800, 4)`;
  - f = 1/400: `row_f400_s200` vs `sub(row_f400_s800, 4)`.
  - U predicts no difference at any footprint: the same points, the same footprint, the same metric. C predicts a
    difference wherever its departure has a chain part, with c ≈ Δ for a pure chain effect.
- Test: each contrast on T at 0.01/3, Holm across the 18 keys.
- Classification at footprint f, when D_f is not empty:
  - **undersampling** iff P(200 ← 800, f) rejects no key;
  - **chain** iff it rejects at least 1 key and χ(f) > 1/2;
  - **mixed** iff it rejects at least 1 key and χ(f) ≤ 1/2. A chain part is detectable, but the sampling part is the
    larger.
  - 1/2 is where the two parts of the exact decomposition Δ = c + u are equal. It defines which part dominates; it is
    not a tuned value.
  - If D_400 is empty, f = 1/400 has no departure to apportion. Its contrast is still run and reported. A rejection
    there is reported as a chain difference that the native comparison does not show.
  - Each footprint is classified on its own. Jitter moves hit points and so K consumption, so a chain part may differ
    between footprints.
- Decision:
  - **supported** iff every footprint with a departure (f = 0 and 1/1400, and 1/400 if D_400 is not empty) is classified
    undersampling;
  - **refuted** iff some footprint is classified chain;
  - **partially supported** otherwise. The verdict is reported per footprint.
- Paired effect statistics, per footprint:
  - χ(f) with its interval (the Conclusion says whether it excludes 1/2);
  - c and u for A, X and Y with intervals (C predicts c concentrated in X; U predicts c ≈ 0);
  - ρ_x per region beside ρ_self (U predicts ρ_x ≈ ρ_self ≈ 1);
  - the rejected keys with their effects.
- Power:
  - 16 vs 16: the smallest attainable p is 1/100,001 = 1.0e-5, below the first Holm threshold (0.01/3)/18 = 1.85e-4.
  - Simulated (planning, normal data, the same Monte Carlo rule): power 0.68 at d = 1.78, 0.86 at d = 2.0, 0.98 at
    d = 2.45 and 1.00 at d = 3.
  - Assumption: the subsampled keys have the native 200 px sd (the same pixel count and passes). Under C with c = Δ,
    d is 2.45 for `r4.slag.x` at f = 1/1400, and 2.0 to 7.3 for the seven keys of D_0.
  - 8 vs 8 is underpowered for f = 1/1400: power about 0.35 at d = 2.45. Hence the second blocks 50-55, at a cost of
    96 renders and about 5,050 CPU-s.
  - Standard error of χ: about 0.14 at f = 1/1400 (one key), and 0.05-0.18 per key at f = 0.

### Estimation without verdicts

- **E1, convergence pattern** (8-pair frame, both families, 200 → 400 → 800 → 1600 px):
  - the steps of every `structure_std` key (r2-r7), of `r4.slag.x`, and of A, X and Y, with intervals;
  - the ratio of each step to the next (006's secondary: the 800 → 1600 step of `structure_std` is smaller than the
    400 → 800 step in r3-r7, and likewise for `r4.slag.x`). Per lesson (c) these are not decided key by key;
  - the readings I, G and N of H1, with G's predicted numbers.
- **E2, pointwise image-locking** (8-pair frame): P(200 ← 400, f), P(400 ← 800, f), P(800 ← 1600, f) and
  P(400 ← 1600, f) for f ∈ {1/1400, 0}.
  - Each reports effect summaries, p-values and Holm decisions at 0.01, for reference only, with no verdict. It also
    reports ρ_x, ρ_self, and the chain part c of A, X and Y.
  - If the texture is a field on the image plane, every contrast shows no difference and ρ_x ≈ ρ_self.
- **E3, footprint effects at a fixed side** (8-pair frame): `row_f400_s200` vs `row_s200` and `row_f400_s800` vs
  `row_s800` (f = 1/400 against 1/1400), and `row_j0_s1600` vs `row_s1600` (006's footprint rows extended to 1600 px).
- **E4, draws per sample**: `r{r}.k_per_sample` per configuration, and native against subsampled in every pointwise
  contrast, in that contrast's frame. Under U the path statistics depend only on the image-plane point.
- **E5, the 16-pair departure**: `row_*_s200` vs `row_*_s800` at each footprint on the 16-pair frame. These are the
  Δ_k of the decomposition, with Holm counts at 0.01 for reference.
- **Profile**: `r4.slag.x` and `r4.slag.y` at image-plane lags k/200 of the side (k = 1, 2, 3) per side and footprint,
  as 006's `fig_slag_profile.png`, now with 1600 px.

## Method

### Configurations

| configuration | side (px) | f (fraction of the side) | oracle options besides `chain=row`, `passes=64`, `size` | blocks (seeds) | source |
|---|---:|---|---|---|---|
| `row_s200` | 200 | 1/1400 | none (default jitter) | 31 (496-511), 52 (832-847) | 006 `row_s200` (cache); new |
| `row_s400` | 400 | 1/1400 | none | 27 (432-447) | 006 `row_s400` = 004 `row_s400` = 003 `row` (cache) |
| `row_s800` | 800 | 1/1400 | none | 32 (512-527), 53 (848-863) | 006 `row_s800` (cache); new |
| `row_s1600` | 1600 | 1/1400 | none | 46 (736-751) | new |
| `row_j0_s200` | 200 | 0 | `jitter=0.0` | 39 (624-639), 54 (864-879) | 006 `row_j0_s200` (cache); new |
| `row_j0_s400` | 400 | 0 | `jitter=0.0` | 40 (640-655) | 006 `row_j0_s400` (cache) |
| `row_j0_s800` | 800 | 0 | `jitter=0.0` | 41 (656-671), 55 (880-895) | 006 `row_j0_s800` (cache); new |
| `row_j0_s1600` | 1600 | 0 | `jitter=0.0` | 47 (752-767) | new |
| `row_f400_s200` | 200 | 1/400 | `jitter=0.005` | 48 (768-783), 50 (800-815) | new |
| `row_f400_s800` | 800 | 1/400 | `jitter=0.005` | 49 (784-799), 51 (816-831) | new |

- `jobs.py` declares each block as its own ensemble (`DESIGN`, 16 entries) and lists the blocks of each configuration
  (`CONFIGURATIONS`). The first block listed is the 8-pair frame.
- Reused blocks: the six 006 blocks have exactly 006's option sets, so their cache keys are 006's.
  `report.check_seed_reuse` against experiments 001-004, 006 and 008 passes on the planned `jobs.py`.
- Block allocation. Blocks 46-49, after 008's blocks 42-45, were allocated to the four new configurations. H3 needs
  16 pairs per side (H3, Power), so blocks 50-55 are added as second blocks of the six 200 px and 800 px
  configurations.
- The oracle binary is `.cache/oracle-build/src/app/smallpaint_oracle`, the binary of experiments 001-006, sha256
  `066bb5d4247c556ad5232bfc4fff75dc5f37089840b23f1ecc8fdd9cb518828a`. It is not rebuilt, and no oracle option is added.
- New renders: 160 (10 new blocks × 16): 64 at 200 px, 64 at 800 px and 32 at 1600 px. 96 reused renders are cached.

### Cost

- CPU per render, from the cache's `wall_seconds` (single-threaded oracle):
  - 200 px row chain: 6.0-6.1 s (means of `row_s200`, `row_j0_s200`, `row_s200_px`);
  - 800 px: 96.3-103.2 s (`row_j0_s800`, `row_s800`, `row_s800_px`; 99 s is used);
  - 1600 px: 4 × 97 ≈ 390 s, since the cost scales with the pixel count (×4.2 from 200 to 400 px, ×3.8 from 400 to
    800 px).
- Total: 64 × 6.1 + 64 × 99 + 32 × 390 ≈ 19,200 CPU-s, i.e. 5.3 CPU-hours, about 1.4 h wall with 4 workers.
  - Of this, the 1600 px renders take 12,480 s, the first blocks of the f = 1/400 configurations 1,680 s, and the six
    second blocks 5,050 s.
  - That is 22% of the one-day limit, so neither passes nor pairs are reduced.
- Disk: 39 bytes per pixel per render (`sum` 24, `k_consumed` 8, `object_id` 4, `image.ppm` 3), i.e. 4.9 GB for the
  new renders. 11 GB were free when this was written.
- Memory per render: under 150 MB at 1600 px.
- Every row chain at 1600 px stays below 2^22 draws. A cached 800 px row-chain render consumed at most 887,625 draws in
  one row over all 64 passes, so one (row, pass) chain at 1600 px is near 26,000 draws. K therefore stays below 2^23,
  the generator's exact range (SPEC §3). The analysis checks the bound on every render.

### Commands

```
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/009-2026-10-09-scale-limits/analyze.py --preflight
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python -m painterly_analysis.experiment run experiments/009-2026-10-09-scale-limits/jobs.py --budget 120   # repeat until exit 0
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/009-2026-10-09-scale-limits/analyze.py
```

- `--preflight` renders nothing. It checks the oracle sha256 above, the cache markers of the 96 reused renders, and
  the free disk space against the 4.9 GB estimate. It exits non-zero on any failure, and then nothing is rendered.
- Budget 120 s, not the protocol's 540 s. A 1600 px render takes about 390 s. The slowest cached 800 px row render took
  117 s, so a slow 1600 px render may take 4 × 117 = 470 s. No job starts after the budget, so a call ends within about
  120 + 470 = 590 s, under the protocol's 10 minutes. About 17 calls are needed.
- Smoke run (code check only), with a scratch `PAINTERLY_CACHE` and `--out-dir`:
  `analyze.py --pairs 2 --scale 4`, sides 50, 100, 200 and 400. It rounds τ and e to the nearest integer of at least
  1 px, as 006 did, and says so. It never writes the committed outputs.

### Analysis

- `analyze.py` loads the cache and implements the Common definitions, H1-H3 and E1-E5. It reuses 006's measurement
  functions unchanged (PLAN.md). New code: `metrics.cross_structure_correlation` (ρ_x) with unit tests, and the
  subsampling, decomposition, class statistics and bootstrap in `analyze.py`.
- **Design checks**, each of which stops the analysis on failure:
  - `jobs.DESIGN` and `CONFIGURATIONS` match the Method table (sides, f as a `Fraction`, blocks, seeds, options);
  - seeds are unique, and `report.check_seed_reuse` passes against experiments 001-004, 006 and 008;
  - every render has P = 64. All renders of one side share one object-id map;
  - `sub(·, k)`'s object-id map equals the native map for every pointwise contrast;
  - every block has 16 distinct `sum` arrays (sha256), so no replicate repeats a render;
  - every render has at most 2^22 − 1 draws in each row over all passes, which bounds each (row, pass) chain;
  - consistency with 006: the 8-pair-frame values of the six reused configurations equal 006's `results.json` `summary`
    (mean and sd of every T and estimation-only key) exactly (`==`), and the two (400, 800) comparisons reproduce 006's
    p-values and rejections exactly.
- **Outputs**:
  - `results.json`: parameters, regions, replicate counts, the chain bound, every comparison (effect summary,
    p-values, Holm decisions, `min_attainable_p`), the decompositions, χ, ρ_x and ρ_self, class statistics with
    intervals, k_per_sample, the decision records, and the figure encodings;
  - printed tables, one per hypothesis and estimation block;
  - figures, each at most 1 MB, drawn without text, with their encodings in `results.json` (PLAN.md):
    - `fig_grid_row.png`, `fig_grid_row_zero.png` and `fig_grid_row_f400.png`: pair 0 of each side, box-downsampled to
      200 px tiles;
    - `fig_points_default.png`, `fig_points_zero.png` and `fig_points_f400.png`: native 200 px, 800 px subsampled to
      the same points, and 800 px box-downsampled, as 200 px tiles;
    - `fig_slag_profile.png`, `fig_steps.png` (A, X and Y against side), and `fig_decomposition.png` (Δ, c and u per
      key of D_f).
- Deterministic: exact or fixed-key permutation p-values and seed-0 bootstraps. A second run into a scratch
  `--out-dir` must reproduce every output byte for byte.
