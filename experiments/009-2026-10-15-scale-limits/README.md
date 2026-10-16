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
    - (d) with 8 vs 8 pairs and Holm at 006's level 0.01/3, a rejection means complete separation (at H1's level 0.01
      it means one of the three most extreme splits, H1 Test), so verdicts are paired with effect statistics;
    - (e) units are named every time.
- Class departures (200 px minus 800 px) of 006's row-chain renders, with A, X and Y as defined below. Each cell gives
  the difference of means, its 99% percentile bootstrap interval (the draws that select H3's departure sets: 10,000
  resamples, seed 0, Common definitions) and the exact 8-vs-8 permutation p-value. They are computed from 006's
  per-pair values (Prior exposure).

  | footprint | A (log amplitude) | X (along the chain) | Y (across chains) |
  |---|---|---|---|
  | f = 0 (blocks 39 vs 41) | −0.0772 [−0.0841, −0.0699], p 1.55e-4 | −0.0455 [−0.0589, −0.0324], p 1.55e-4 | −0.0564 [−0.0652, −0.0453], p 1.55e-4 |
  | f = 1/1400 (blocks 31 vs 32) | −0.0233 [−0.0387, −0.0079], p 1.4e-3 | −0.0167 [−0.0423, +0.0088], p 0.146 | −0.0017 [−0.0384, +0.0422], p 0.93 |

  - At f = 0, A, X and Y are all lower at 200 px (p at the 8-vs-8 floor of 1.55e-4).
  - At f = 1/1400, the amplitude A is lower at 200 px. The X and Y intervals contain 0, so these class statistics do not
    show a direction for that departure. X is therefore a deciding unit of H3 at f = 0 (D_0) but not at f = 1/1400,
    where a chain part in X is reported as estimation and can raise H3's flag.
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
  4. The 99% percentile intervals of the 200 − 800 px departure of the 21 units (the 18 keys of T and A, X, Y) on 006's
     blocks, which select D_0 and D_1400 (Common definitions, "Departure sets"; planning script `review5_select.py`,
     second review). The table above comes from the same draws.
  No texture key was computed on subsampled renders. Blocks 46-67 do not exist yet.
  - Selection. D_0 and D_1400 (H3) were selected on 006's blocks 39 vs 41 and 31 vs 32, by the intervals of item 4. The
    shape summaries above use the same blocks. Their selection noise would bias a contrast computed on them toward the
    chain reading (H3), so H3 decides on blocks that selected nothing (fresh set). The 006 blocks enter H3 only as
    estimation.

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
- **Block sets.** Each comparison uses a named set of blocks (`jobs.BLOCK_SETS`; Method table):
  - *8-pair set*: the first block of each configuration. It is used by H1, the reproduction of 006, E1 to E3 and the
    profile.
  - *H2 set*: blocks 48 + 50 (`row_f400_s200`) and 49 + 51 (`row_f400_s800`), 16 pairs per side. It is used by H2, and
    D_400 is located on it.
  - *Fresh set*: blocks that selected no departure set. It is used by H3, by the 1/1400 reference departure of H2,
    and by E4 (H3's contrasts) and E5:
    - f = 1/1400: blocks 52, 56, 58, 60 (`row_s200`) and 53, 57, 59, 61 (`row_s800`), 32 pairs per side;
    - f = 0: blocks 54, 62 (`row_j0_s200`) and 55, 63 (`row_j0_s800`), 16 pairs per side;
    - f = 1/400: blocks 64, 66 (`row_f400_s200`) and 65, 67 (`row_f400_s800`), 16 pairs per side.
  - *Pooled set*: every block of a configuration. Estimation only (E5), because it contains the selection blocks.
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
- **Units.** The 18 keys of T and the class statistics A, X and Y: 21 units. H3's departure sets, tests and
  decomposition are over units.
- **Decomposition at footprint f** (fresh set). For each unit i, with M_i(·) the ensemble mean of unit i:
  - the departure Δ_i = M_i(native 200) − M_i(native 800), each measured at its own side;
  - the chain part c_i = M_i(native 200) − M_i(sub 200 ← 800);
  - the sampling part u_i = M_i(sub 200 ← 800) − M_i(native 800).
  - This is exact: Δ_i = c_i + u_i.
  - The chain share χ(f) is the median over the departure set D_f of c_i / Δ_i. χ = 0 means the departure is all
    sampling, and χ = 1 that it is all chain.
- **Departure sets.** D_f is the set of units on which a departure at footprint f is shown, on blocks outside the fresh
  set:
  - D_0 and D_1400: the units whose 200 − 800 px departure on 006's blocks (39 vs 41 at f = 0, 31 vs 32 at
    f = 1/1400, 8 vs 8 pairs) has a 99% percentile interval that excludes 0. The intervals use 10,000 resamples from one
    `numpy.random.default_rng(0)` of their own. Pair indices `integers(0, 8, (10_000, 8))` are drawn once per
    configuration, in the order `row_s200`, `row_s800`, `row_j0_s200`, `row_j0_s800`, and shared by every unit. This
    gives (Prior exposure, item 4):
    - D_1400, 8 units: A, `r3.structure_std`, `r3.slag.x`, `r3.slag.y`, `r4.slag.x`, `r5.structure_std`,
      `r6.structure_std` and `r7.slag.y`;
    - D_0, 15 units: A, X, Y, `r2.slag.x`, `r2.slag.y`, `r3.structure_std`, `r3.slag.x`, `r4.structure_std`,
      `r4.slag.x`, `r4.slag.y`, `r5.structure_std`, `r6.structure_std`, `r6.slag.y`, `r7.structure_std` and
      `r7.slag.x`.
    - Each contains the keys that 006 rejected (H4 at f = 0, 7 keys; H1-row at f = 1/1400, `r4.slag.x`): a complete
      separation puts every resampled difference on one side of 0. The sets are the same with the f = 0
      configurations drawn first, and the same at the 95% level except that D_0 then also holds `r3.slag.y`.
    - Why intervals, not 006's Holm decisions: at 006's 8-vs-8 floor Holm admitted only complete separations. The
      first draft's D_0 therefore left out X (p 1.55e-4 as a class statistic) and every `slag.x` key, and its D_1400
      left out A (p 1.4e-3). A chain part located there could not decide the class (second review).
    - A unit with no true departure can be selected: a 99% percentile interval excludes 0 for such a unit with
      probability 0.036 at 8 vs 8 (Bootstrap). χ is a median over 8 or 15 units, so a few such units move it little
      (H3 Power, robustness).
  - D_400 is located on the H2 set (blocks 48-51, disjoint from the fresh blocks 64-67), after H2:
    - if H2 reads supported (removed), D_400 is empty and the footprint has **no departure**;
    - otherwise D_400 is the keys that H2 rejects plus each of A, X, Y and `r4.slag.x` whose Δ_400 interval (H2 set)
      excludes 0. If that is empty, the footprint's departure is **not located**;
    - if H2 is underpowered (smoke scale only), the footprint is **inconclusive (underpowered)**.
    - Only these four candidates are located by their intervals, besides H2's Holm rejections. At 16 vs 16 a 99%
      percentile interval excludes 0 for a unit with no departure with probability 0.024 (Bootstrap), so an interval
      selection over the 18 keys would pick at least one such key in about 0.35 of draws, and over these four in
      about 0.09.
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
- **K stride** `r{r}.k_per_pass`, estimation only: the region mean of (k_a + k_b) / (2P), where k is `k_consumed` and
  P = 64 the pass count, in diffuse draws per pixel per pass (007's name).
- **Significance.** Each hypothesis has family-wise level 0.01 (`SIGNIFICANCE`; it is not the oracle option `alpha`).
  How it is divided is stated in each hypothesis.
  - Every p-value is a two-sided permutation p-value from `ensemble.permutation_pvalue`.
    - At 8 vs 8 it is exact over the C(16, 8) = 12,870 splits; the smallest attainable p is 2/12,870 = 1.55e-4.
    - At 16 vs 16 and larger (H2, H3, E5) the number of splits exceeds `PERMUTATION_MAX_EXACT`, so it uses 100,000
      random permutations with `jax.random.PRNGKey(0)`, as the function defines. The smallest attainable p is
      1/100,001.
  - Holm (`ensemble.holm`, through `report.family_test`) runs across the keys or units of each family. The power guard
    is `report.family_test`'s.
- **Bootstrap.** Intervals enter the decisions of H1 (readings), H2 (removal conditions), H3 (χ) and the departure sets
  (D_0 and D_1400 are selected, and D_400 is located, by them).
  - 10,000 resamples from one `numpy.random.default_rng(0)`, 99% percentile intervals (`CI_DECISION = (0.5, 99.5)`).
    The level 0.01 is `SIGNIFICANCE`, the level of each hypothesis. Every interval of this experiment, decision or
    estimation, uses it.
  - Percentile intervals undercover at these sizes. For a difference of means with no true difference, a 99% interval
    excludes 0 with probability 0.036 at 8 vs 8 and 0.024 at 16 vs 16 (normal data, 4,000 draws;
    planning script `review5_falsesel.py`). The error rates in the Power bullets are simulated with these intervals.
  - Pairs are resampled within each configuration and block set, and one draw of pair indices per (configuration,
    block set) is shared by every statistic of that block set. The selection of D_0 and D_1400 has its own generator
    (Departure sets).
  - The measurements of one render at its own side and after subsampling are resampled together.
  - Interval relations: an interval [lo, hi] *contains* x iff lo ≤ x ≤ hi, and otherwise *excludes* it; it *lies
    below* x iff hi < x and *above* x iff lo > x. It lies on a *side* of 0 iff it lies above or below 0.
- **Estimation.** Every comparison reports:
  - `ensemble.effect_summary` for T and the estimation-only keys;
  - the largest |rel| (with its abs diff) and the largest |d|, over T and over all keys;
  - `min_attainable_p` and the first Holm threshold.
  "Indistinguishable" is written only together with those numbers.

### H1: image-locking holds above 800 px

- Derived from 006: (400, 800) rejects 0 of 18 in three families, and Blender renders are usually larger than 800 px.
  If the converged texture is a field on the image plane, renders at 800 and 1600 px sample one field, and the
  scale-equivariant metrics agree.
- Two families, each on the 8-pair set:
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
    - The premise holds where the jitter footprint is narrower than a pixel. Its full width 2f·s is 0 in the zero
      family, and 2/7, 4/7, 8/7 and 16/7 px at 200, 400, 800 and 1600 px in the default family. From s = 700 px the
      default footprint averages each pixel's paths over more than one pixel pitch, so a part finer than the footprint
      is removed before it is sampled, and what remains is not pixel-white. In the default family g is therefore an
      upper bound on the residual step, and F or I is expected.
    - In the default family the 400 → 800 A step is −0.0043 (z −1.87), so G predicts a step near 0 there, as I does.
  - **N, new size dependence.** A step from 800 to 1600 px that G does not predict: not shown smaller than the
    400 → 800 step, or of the opposite sign.
  - **S, converging slower than 1/s²** (named so that it is not read as N): a step of the same sign as the 400 → 800
    step, larger than G predicts and shown smaller than the 400 → 800 step.
  - **F, converging faster than 1/s²**: a step of the same sign as the 400 → 800 step, shown non-zero and shown smaller
    than G predicts.
- **Test**: in each family, (800, 1600) on T, Holm across the 18 keys at 0.01 (one comparison per family).
  - The first Holm threshold is 0.01/18 = 5.56e-4. Exact two-sided 8-vs-8 p-values are multiples of 2/12,870, so it
    admits p = 2k/12,870 for k ≤ 3 (1.55e-4, 3.11e-4 and 4.66e-4; 8/12,870 = 6.22e-4 is not admitted).
  - The splits come in mirror pairs, so k is the rank of the observed split among the splits that shift the means in
    its direction. A rejection therefore means complete separation (k = 1), or the second or third most extreme split
    (k = 2, 3). Each of those differs from complete separation by one exchange of one value of each ensemble, both
    within two ranks of the boundary between them.
- Not part of the decision:
  - (400, 800) is the **reproduction check**. It uses 006's renders at 006's level 0.01/3 and must reproduce 006's
    p-values and its 0 rejections exactly (design check).
  - (400, 1600) is estimation only (E1). It spans two doublings and reuses 006's 400 px blocks, so it also detects the
    known 400 → 800 step against a sharper reference: with no change above 800 px, simulated from 006's per-pair means
    and sds, it rejects at least one key at 0.01/3 with probability 0.87 (sd at 1600 px = sd at 800 px) or 0.97
    (half of it) in the zero family, and 0.20 or 0.50 in the default family.
- **Reading rule**, for each family and each unit Z (class statistic or key), on the 8-pair set:
  - s2 = Z(800) − Z(400), s3 = Z(1600) − Z(800), from the same bootstrap; g = s2/4 is G's prediction (the 4-fold
    shrink per doubling derived above).
  - **If the interval of s2 contains 0**, the 400 → 800 step is not shown, its direction σ is not defined, and g
    cannot be told from 0:
    - **N** iff the intervals of s3 and of s3 − s2 lie on the same side of 0: the step from 800 to 1600 px is shown
      non-zero and shown larger than the step before it, in its own direction;
    - **not separated** otherwise.
  - **If the interval of s2 excludes 0**, σ is the side of 0 on which it lies, and:
    - **I** iff the interval of s3 contains 0 and the interval of s3 − g excludes 0;
    - **G** iff the interval of s3 excludes 0 and the interval of s3 − g contains 0;
    - **I or G** (not separated) iff both intervals contain 0;
    - otherwise both exclude 0:
      - **F** iff the interval of s3 lies on σ's side and the interval of s3 − g on the opposite side;
      - **S** iff the intervals of s3 and of s3 − g lie on σ's side and the interval of s3 − s2 on the opposite side;
      - **N** otherwise: the interval of s3 lies on the opposite side (a reversal), or the interval of s3 − g lies on
        σ's side and the interval of s3 − s2 does not lie on the opposite side.
  - **Reading of a rejected key**: the reading of its class (`structure_std` keys belong to A, `slag.x` keys to X,
    `slag.y` keys to Y) when the class's s2 interval excludes 0; otherwise the key's own reading, by the same rule on
    the key's own intervals.
    - Why: in the default family the per-key 400 → 800 steps of `structure_std` (−0.055, +0.028, −0.072, +0.014,
      −0.026 and −0.032 in r2-r7) partly cancel in A (s2 −0.0043), so a class with no shown step says nothing about one
      key's convergence.
- **Decision**, per family:
  - **supported** iff (800, 1600) rejects 0 of 18 keys;
  - **partially supported (G)** iff it rejects at least 1 key and every rejected key reads G or F: the residual shrinks
    at least 4-fold per doubling, as the 1/s² tail of the metric does;
  - **refuted** iff it rejects at least 1 key and some rejected key reads N, S or I. The verdict names the reading. Only
    N is "new size dependence"; I means a key-level change that its class statistic does not show;
  - **inconclusive** otherwise: some rejected key reads "I or G" or "not separated", and none reads N, S or I.
- Paired effect statistics (E1): s2 and s3 of A, X, Y and of every `structure_std` key and `r4.slag.x`, with intervals.
  A step ratio s3/s2 is reported only where the interval of s2 excludes 0; otherwise the steps alone are reported.
- Power:
  - (800, 1600), 8 vs 8 at 5.56e-4, exact permutation p-values on normal data (planning simulation, 2,000 draws):
    rejection probability 0.31 at d = 2, 0.59 at d = 2.5, 0.81 at d = 3, 0.94 at d = 3.5 and 0.99 at d = 4. (The second
    review reproduced 0.30, 0.57, 0.80, 0.94 and 0.99; p = 6/12,870 occurs in 0.05-0.09 of draws at d = 2 to 3.5.)
  - The detectable effect at 0.94 is 3.5·sd(800 px), if the 1600 px sd is not larger (more pixels per region). From
    006's 800 px sds:
    - f = 1/1400: `structure_std` 0.066-0.324 bytes (rel 0.010-0.069), `slag` 0.029-0.144;
    - f = 0: `structure_std` 0.086-0.212 bytes (rel 0.013-0.029), `slag` 0.020-0.069.
  - Departures of the size seen at 200 px (f = 0: `r3.structure_std` −0.94 bytes, `r2.slag.y` −0.18; f = 1/1400:
    `r4.slag.x` −0.074) would be detected.
  - The whole rule, simulated from 006's per-pair means and sds (planning script `review5_h1.py`, second review:
    400 draws, keys independent, A, X and Y computed from the simulated keys, 2,000 bootstrap resamples, 99% intervals;
    sd at 1600 px = sd at 800 px, or half of it):
    - truth I (no change above 800 px): (800, 1600) rejects at least one key with probability 0.010-0.017 in both
      families; the verdict is supported in 0.985-0.988 (zero) and 0.983-0.990 (default);
    - truth G on every key (s3 = s2/4): it rejects with probability 0.015-0.052 in the default family, and 0.22 (sd at
      1600 px = sd at 800 px) or 0.50 (half of it) in the zero family. Zero-family verdicts: supported 0.78 / 0.51,
      partially supported (G) 0.15 / 0.37, inconclusive 0.06 / 0.11, refuted 0.018 / 0.022. A zero-family rejection
      is therefore not N by itself, and the reading rule decides;
    - truth N on every key (s3 = s2): zero family refuted 1.00; default family refuted 0.38 / 0.69, inconclusive
      0.31 / 0.26, supported 0.31 / 0.04, partially supported (G) 0.007 / 0.013. The default family's 400 → 800 steps
      are small, so its N steps are small too, and most rejected keys are read by their own intervals.
    - The first draft's rule (95% intervals, class readings only, σ from the point estimate of s2) gave, under default
      N, refuted 0.18 / 0.49 and partially supported (G) 0.05 / 0.05 (second review).
  - Class readings, zero family A: truth I reads I in 0.79 / 0.91 ("I or G" 0.17 / 0.06, G 0.02 / 0.01, N 0.02);
    truth G reads G in 0.93 / 0.95 (S or F 0.01-0.04, "I or G" 0.06 / 0.00); truth N reads N in 0.98 (S 0.02).
    SE(s3) is 0.0010-0.0013, so G's +0.0053 is 4-5 SE from I's 0. A reading only matters together with a rejection,
    which under I has probability 0.010-0.017.
  - Where the interval of s2 usually contains 0 (z of s2: default A −1.87, X +0.95, Y −0.20; zero Y +0.49), the class
    reads "not separated" in 0.78-0.81 (default A), 0.89-0.90 (default X), 0.94-0.96 (default Y) and 0.93-0.98 (zero Y)
    of draws under I, G or N. Zero-family X (z +2.47) reads "not separated" in 0.33-0.38 and "I or G" in 0.46-0.55
    under I or G.
  - 8 pairs are kept. G's `r4.structure_std` step (+0.024, d ≈ 0.9 at the 800 px sd) would need far more pairs to be
    detected by a rejection; the interval rule on A separates G from I without that.

### H2: a footprint as wide as a 200 px pixel removes the 200 px departure (footprint test)

- Derived from 006's later-work hypothesis.
  - If the 200 px departure is a sampling effect, content finer than the 200 px pitch causes it.
  - A footprint of f = 1/400 averages each pixel over a square 1/200 of the side wide: the whole 200 px pixel. That is
    12.25 = (700/200)² times the area of the 1/1400 footprint, which already removes 32-52% of the structure variance.
  - Its box transfer is sinc(ν/200) at ν cycles per side. That is 2/π = 0.64 at the 200 px Nyquist frequency (100) and
    0 at 200 cycles per side.
- Observable: T, `row_f400_s200` vs `row_f400_s800` on the H2 set (16 vs 16 pairs), Holm across the 18 keys at 0.01.
  The first Holm threshold is 5.56e-4. 006's counts at the same pair of sizes are 7 (f = 0) and 1 (f = 1/1400), on
  8 vs 8.
- Removal conditions, for each of Z ∈ {A, `r4.slag.x`}:
  - Δ_400(Z) is the 200 − 800 px departure on the H2 set. Δ_1400(Z) is the 1/1400 departure on the fresh set
    (32 vs 32 pairs, blocks that selected nothing, so it is free of 006's selection). σ_Z is the sign of the point
    estimate of Δ_1400(Z) (+1 if it is 0).
  - *shift*: the interval of Δ_400(Z) − Δ_1400(Z) lies on the side of 0 opposite to σ_Z: Δ_400 is shown to lie on the
    zero side of Δ_1400;
  - *removed*: the interval of Δ_400(Z) contains 0, and shift;
  - *reduced*: the interval of Δ_400(Z) lies on σ_Z's side of 0, and shift. Together they show 0 < |Δ_400| < |Δ_1400|;
  - *reversed*: the interval of Δ_400(Z) lies on the side opposite to σ_Z. Shift alone would read a reversed departure
    larger than the 1/1400 one as a reduction (second review).
  - *Removed* asks only that no departure be shown and that Δ_400 be shown to lie on the zero side of Δ_1400. A Δ_400
    whose interval contains 0 is not a shown reversal, and a shown one reads *reversed*.
  - Why A and `r4.slag.x`: A is the class statistic whose 1/1400 departure 006 established (p 1.4e-3, Background), and
    `r4.slag.x` is the key 006 rejected. X's 1/1400 departure was not established (p 0.146), so its reduction could
    not be shown with useful power.
- Decision:
  - **supported (removed)** iff 0 keys are Holm-rejected and both Z read *removed*;
  - **partially supported (reduced)** iff 0 keys are rejected, each Z reads *removed* or *reduced*, and at least one
    reads *reduced*;
  - **refuted** iff at least 1 key is Holm-rejected;
  - **not shown (reversed)** iff 0 keys are rejected and some Z reads *reversed*;
  - **not shown** otherwise.
- What it answers. H2 is the practical question for previews: does a pixel-wide footprint make 200 px match 800 px?
  Lesson (b) applies, so H2 is not the mechanism test:
  - a box is not an ideal low-pass. Under the sampling reading it reduces the departure but need not remove it, so a
    refutation does not refute that reading;
  - a footprint also moves hit points, and so K consumption. It may weaken a chain effect too, so a support does not
    exclude the chain reading.
  H3 separates the two readings. H3's f = 1/400 footprint has "no departure" only when H2 reads supported (removed)
  (Common definitions, Departure sets).
- Paired effect statistics: the 200 − 800 px departures of A, X and Y at f = 0, 1/1400 and 1/400 with intervals
  (fresh set for 0 and 1/1400, H2 set for 1/400), beside the rejection counts.
- Power. Footprints change the seed-to-seed sd (006: the median sd ratio per doubling of f over T is 1.12, the upper
  quartile 1.41), so the f = 1/1400 sds understate it at f = 1/400, 1.81 doublings larger. The stand-in sds are:
  - 200 px: `row_s200_px` (f = 1/700, the measured footprint nearest 1/400 at 200 px) times 1.12^0.81 or 1.41^0.81
    (1/700 → 1/400 is 0.81 doublings). `r4.slag.x` has sd 0.0767 or 0.0923 there, against 0.0301 at 1/1400;
  - 800 px: `row_s800` (f = 1/1400) times 1.12^1.81 = 1.23, or 1.41^1.81 = 1.86 (upper quartile). (006's
    `row_s800_px` has f = 1/2800, below 1/1400, so it cannot stand in.)
  - 16 vs 16 at 5.56e-4 (t approximation): rejection probability 0.59 at d = 1.44, 0.69 at d = 1.55, 0.95 at d = 2.0
    and above 0.99 at d = 2.5. 8 vs 8 (exact) would give 0.14 at d = 1.55, so the 16 new pairs are used.
  - A `r4.slag.x` departure as large as 006's at 1/1400 (−0.0737) has d = 1.32 with the median-grown sds (0.0767 and
    0.0183) and d = 1.08 with the upper-quartile ones (0.0923 and 0.0277): power 0.47 or 0.25 to reject that key
    alone. The first draft's 0.59 to above 0.99 left the 200 px stand-in ungrown (d 1.44) or grew the 1/1400 sd at
    200 px instead (d 2.5); the growth model applies to both sides (second review).
  - The whole rule (planning script `review5_h2.py`, second review: 300 draws; keys independent and normal with the
    stand-in sds, A from the simulated keys; Δ_1400 on 32 vs 32 with 006's 1/1400 sds; 20,000 Monte Carlo
    permutations; 2,000 bootstrap resamples, 99% intervals). Median / upper-quartile sd growth:
    - if the footprint removes the departure and the true 1/1400 departure equals 006's on every key: supported
      (removed) 0.72 / 0.49, not shown 0.22 / 0.45, not shown (reversed) 0.04 / 0.03, refuted 0.013 / 0.027. If the true
      1/1400 departure is half of 006's: supported 0.08 / 0.03, not shown 0.88 / 0.93. (First draft, 95%: 0.80 / 0.71
      and 0.24 / 0.18.)
    - if the footprint halves the departure: refuted 0.89 / 0.62, supported 0.01 / 0.02;
    - if it leaves the departure unchanged: refuted 1.00 / 1.00 (0.90 / 0.61 if the departure is half of 006's);
    - if it reverses it (Δ_400 = −1.5·Δ_1400): refuted 1.00 / 1.00. The interval conditions alone, without the Holm
      test, read this case *reversed* in 1.00 of draws, where the first draft's shift-only rule read "reduced" in 1.00
      (planning script `review5_h2_states.py`, 600 draws).
    - Under removal the Holm test rejected in 0.013-0.027 of these draws, above its nominal 0.01. The permutation test
      assumes that the pairs are exchangeable when there is no difference. The stand-in sds are 1.8-13.4 times larger
      at 200 px than at 800 px, so they are not, and the tail of the difference of means is then not exact at
      16 vs 16: the family-wise error is 0.028 (median growth) and 0.020 (upper quartile), against 0.010 with equal
      sds (planning script `review5_h2_fwer.py`, 2,000 draws). A refutation of H2 therefore carries an error rate of
      about 0.02-0.03, not 0.01, if the 1/400 sds differ as the stand-ins do. The registered test is kept
      (`ensemble.permutation_pvalue` has no studentized form), and the Conclusion states this rate with the verdict.

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
      interval contains 0). X decides at f = 0 (D_0); at f = 1/1400 its c is estimation, and a chain difference in it
      raises the flag.
- Contrast that separates them: PC(200 ← 800, f) for f ∈ {0, 1/1400, 1/400}, on the fresh set:
  - f = 0: `row_j0_s200` vs `sub(row_j0_s800, 4)`;
  - f = 1/1400: `row_s200` vs `sub(row_s800, 4)`;
  - f = 1/400: `row_f400_s200` vs `sub(row_f400_s800, 4)`.
  - U predicts no difference at any footprint: the same points, the same footprint, the same metric, so c_i = 0 for
    every unit. C predicts c_i ≈ χ·Δ_i with χ > 0 wherever the departure has a chain part.
- Tests at footprint f, level 0.01/3 per footprint (Bonferroni over the three footprints):
  - when D_f is not empty, the footprint's 0.01/3 is split in two halves, which keeps H3's family-wise level at
    3 × 2 × 0.01/6 = 0.01:
    - *departure family*: the units of D_f, Holm across |D_f| at 0.01/6, on their per-pair values. It decides the
      class;
    - *outside family*: the units not in D_f, Holm at 0.01/6. No departure was shown on them (at f = 0 and 1/1400
      their 99% interval on 006's blocks contains 0), so a rejection there is a **chain difference outside the
      departure set**, which U excludes;
  - when D_f is empty (f = 1/400 only: no departure, or departure not located): all 21 units, Holm at 0.01/3, as the
    outside family.
- χ(f) and its interval are computed on the fresh set (Common definitions, Decomposition).
- Classes at footprint f, when D_f is not empty:
  - **undersampling** iff no unit of D_f is rejected and the interval of χ(f) lies below 1/2;
  - **chain** iff a unit of D_f is rejected and the interval of χ(f) lies above 1/2;
  - **mixed** iff a unit of D_f is rejected and the interval of χ(f) lies below 1/2. A chain part is detected, and the
    sampling part is the larger;
  - **chain part detected, share unresolved** iff a unit of D_f is rejected and the interval of χ(f) contains 1/2;
  - **inconclusive** iff no unit of D_f is rejected and the interval of χ(f) does not lie below 1/2.
  - 1/2 (`DOMINANCE`) is where the two parts of the exact decomposition Δ = c + u are equal. It defines which part
    dominates; it is not a tuned value. Using the interval, not the point estimate, gives the split a noise floor
    (lesson c).
  - When D_f is empty (f = 1/400 only): **no departure** (H2 reads supported (removed)) or **departure not located**.
  - Any footprint is also flagged **chain difference outside the departure set** if its outside family rejects a unit.
  - What "undersampling" means: no chain part is detected and the chain share is shown to be below 1/2. It does not
    exclude a small chain part (with χ = 1/4, f = 1/1400 reads undersampling with probability 0.83, Power).
  - If the fresh set does not reproduce a departure (Δ_i near 0), the interval of χ is wide and the footprint reads
    inconclusive or share unresolved. E5 reports the fresh departures with their intervals.
  - Each footprint is classified on its own. Jitter moves hit points and so K consumption, so a chain part may differ
    between footprints.
- Footprint verdicts for H3: chain → refuted; share unresolved → inconclusive; inconclusive → inconclusive; mixed →
  partially supported; undersampling → supported; no departure → supported; departure not located → supported. A
  flagged footprint's verdict is then lowered to partially supported if it was higher.
  - A footprint with no departure, or with a departure that is not located, has nothing to apportion; its outside
    family on all 21 units still tests U's prediction c = 0. Reading "not located" as inconclusive would tie H3 to H2's
    removal power: when the footprint removes the departure and the true 1/1400 departure is half of 006's, H2 shows
    the removal in only 0.08 / 0.03 of draws and the departure is not located in 0.82 / 0.85 (H2 Power), so H3 would be
    inconclusive in most such draws whatever f = 0 and 1/1400 show. A departure that persists at 1/400 is located: in
    1.00 of draws at 006's size and 0.95-0.97 / 0.82 at half of it (Power).
- **Decision**: H3's verdict is the lowest footprint verdict in the order refuted < inconclusive < partially supported
  < supported. Hence:
  - **supported** iff f = 0 and 1/1400 read undersampling, f = 1/400 reads undersampling, no departure or departure
    not located, and no footprint is flagged;
  - **refuted** iff some footprint reads chain.
  The class, the state of D_400 and the flags are reported per footprint.
- Paired effect statistics, per footprint (fresh set):
  - χ(f) with its interval;
  - c and u for A, X and Y with intervals (C predicts c concentrated in X; U predicts c ≈ 0);
  - ρ_x per region beside ρ_self (U predicts ρ_x ≈ ρ_self ≈ 1);
  - every rejected unit with its effect, in both families.
- Power (planning script `review5_h3.py`, second review: 400 draws per cell, 300 for the robustness and sample-size
  cells; normal per-pair values with 006's per-key means and sds, keys independent, A, X and Y computed from the
  simulated keys; the subsampled keys have the native 200 px sd (the same pixel count and passes) and correlation 0
  with the same render's native 800 px value; 20,000 Monte Carlo permutations; 2,000 bootstrap resamples, 99%
  intervals; the truth is c_i = χ·Δ_i on every unit, with Δ_i 006's departure):
  - Model check: independent keys give class-statistic sds of 0.80-1.63 times the observed ones (A at 200 px,
    f = 1/1400: 0.0151 against 0.0180 observed).
  - f = 1/1400, 32 vs 32, D_1400 (8 units):
    - χ = 0: undersampling 1.00;
    - χ = 1/4: undersampling 0.83, mixed 0.13;
    - χ = 1/2: a chain part detected 0.98 (share unresolved 0.97), inconclusive 0.025, undersampling 0.00;
    - χ = 3/4: chain 0.95, share unresolved 0.06;
    - χ = 1: chain 1.00, flagged in 0.09 (the outside units' own 006 departures, times χ, are chain parts too).
    - If the true departure is half of 006's: undersampling 0.93 at χ = 0 (inconclusive 0.07), 0.26 at χ = 1/4
      (inconclusive 0.71), 0.003 at χ = 1/2 (inconclusive 0.81, share unresolved 0.19); chain 0.26 at χ = 3/4 and 0.92
      at χ = 1.
  - f = 0, 16 vs 16, D_0 (15 units): undersampling 0.99 at χ = 0; mixed 0.99 at χ = 1/4; share unresolved 0.99 at
    χ = 1/2; chain 1.00 at χ = 3/4 and at χ = 1. Half of 006's departure: undersampling 1.00 at χ = 0 and 0.70 at
    χ = 1/4 (mixed 0.15, inconclusive 0.11), share unresolved 0.98 at χ = 1/2, chain 0.92 at χ = 3/4 and 1.00 at χ = 1.
  - A chain part on some units only:
    - f = 0, c = Δ on the six `slag.x` keys only (C's chain part along the chain): mixed 0.995. The first draft's D_0
      (7 keys, no `slag.x` key) read undersampling + flag in 0.98 of draws (second review);
    - f = 1/1400, c = Δ on every key except `r4.slag.x`: chain 1.00 (flagged 0.025). The first draft read partially
      supported (undersampling + flag) in 0.99;
    - f = 1/1400, c = Δ on `r4.slag.x` only: mixed 1.00; on the six `slag.x` keys only: mixed 0.99 (flagged 0.035);
      on the six `structure_std` keys only: share unresolved 0.99.
  - Robustness to selected units with no true departure: with Δ = 0 for the two selected units of each set whose 99%
    bounds lie closest to 0 (`r7.slag.y` and `r3.slag.y` in D_1400; `r4.slag.y` and `r3.slag.x` in D_0),
    undersampling 1.00 / 0.99 at χ = 0, share unresolved 0.98 / 1.00 at χ = 1/2, chain 1.00 / 1.00 at χ = 1
    (f = 1/1400 / f = 0).
  - Why 32 pairs at f = 1/1400 (second review, 99% intervals). The selected units' 006 departures may be inflated by
    the selection. With a true departure half of 006's, χ = 0 reads undersampling and χ = 1 reads chain in 0.44 and
    0.40 with 16 pairs per side, 0.83 and 0.76 with 24, and 0.93 and 0.92 with 32. With 006's departure, χ = 1/2 is
    detected as a chain part in 0.53 (16 pairs), 0.90 (24) and 0.98 (32).
  - Why 16 pairs at f = 0. With 8 pairs per side the departure family cannot reject: its first Holm threshold
    0.01/6/15 = 1.11e-4 is below the smallest attainable 8-vs-8 p (1.55e-4), and χ = 1/2 and χ = 1 read inconclusive
    in 0.99-1.00 of draws.
  - f = 1/400, 16 vs 16 after H2 (planning script `review5_h2.py`; median / upper-quartile sd growth): if 006's 1/1400
    departure persists unchanged, H2 is refuted and D_400 is located in 1.00 of draws; χ = 0 then reads undersampling
    in 0.84 / 0.58 (inconclusive otherwise), and χ = 1 reads chain in 0.85 / 0.55 (share unresolved 0.15 / 0.42). If
    it persists at half of 006's size, the departure is not located in 0.03-0.05 / 0.18. If the footprint removes the
    departure, the footprint reads no departure in 0.72 / 0.49 and departure not located in 0.21 / 0.41.
  - At f = 1/400, D_400 is unknown before H2. When it is empty, the outside family on all 21 units at 0.01/3 with
    16 vs 16 has a first Holm threshold of 1.59e-4, above the smallest attainable p (1.0e-5).

### Estimation without verdicts

- **E1, convergence pattern** (8-pair set, both families, 200 → 400 → 800 → 1600 px):
  - the steps of every `structure_std` key (r2-r7), of `r4.slag.x`, and of A, X and Y, with intervals;
  - the ratio of each step to the next where the denominator step's interval excludes 0 (006's secondary: the 800 → 1600
    step of `structure_std` is smaller than the 400 → 800 step in r3-r7, and likewise for `r4.slag.x`). Per lesson (c)
    these are not decided key by key;
  - the H1 readings of A, X and Y with G's predicted numbers, and the own readings of every key;
  - (400, 1600) on T, with Holm counts at 0.01/3 for reference only.
- **E2, pointwise image-locking** (8-pair set): PC(200 ← 400, f), PC(400 ← 800, f), PC(800 ← 1600, f) and
  PC(400 ← 1600, f) for f ∈ {1/1400, 0}, i.e. factors m = 2, 2, 2 and 4.
  - Each reports effect summaries, p-values and Holm decisions on T at 0.01, for reference only, with no verdict. It
    also reports ρ_x, ρ_self, and the chain part c of A, X and Y.
  - If the texture is a field on the image plane, every contrast shows no difference and ρ_x ≈ ρ_self.
- **E3, footprint effects at a fixed side** (8-pair set): `row_f400_s200` vs `row_s200` and `row_f400_s800` vs
  `row_s800` (f = 1/400 against 1/1400), and `row_j0_s1600` vs `row_s1600` (006's footprint rows extended to 1600 px).
- **E4, K stride**: `r{r}.k_per_pass` per configuration (8-pair set), and native against subsampled in every pointwise
  contrast, in that contrast's block set. Under U the path statistics depend only on the image-plane point.
- **E5, the departures**: native 200 vs native 800 px at each footprint, on the fresh set (these are the Δ_i of the
  decomposition, with intervals: whether the fresh blocks reproduce 006's departures) and on the pooled set (40, 24 and
  32 pairs per side at 1/1400, 0 and 1/400). The pooled set also repeats the decomposition and χ, as estimation only,
  because it contains the blocks that selected D_f. Holm counts at 0.01 for reference.
- **Profile**: `r4.slag.x` and `r4.slag.y` at image-plane lags ℓ/200 of the side (ℓ = 1, 2, 3) per side and footprint,
  as 006's `fig_slag_profile.png`, now with 1600 px (8-pair set).

## Method

### Configurations

| configuration | side (px) | f (fraction of the side) | oracle options besides `chain=row`, `passes=64`, `size` | blocks (seeds) and block sets | source |
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
  (`CONFIGURATIONS`, first block first: the 8-pair set), and the H2 and fresh block sets (`BLOCK_SETS`).
- Reused blocks: the six 006 blocks have exactly 006's option sets, so their cache keys are 006's.
  `report.check_seed_reuse` against experiments 001-004, 006 and 008 passes on this `jobs.py` (checked at
  registration, with 008's pre-registered `jobs.py`).
- **Block allocation.** The constraint allocated blocks 46-49 to this experiment. The design needs 22 new blocks:
  - 46-47: the two 1600 px configurations (H1);
  - 48-51: the H2 set (16 pairs per side at f = 1/400, H2 Power);
  - 52-67: the fresh set of H3, 32 pairs per side at f = 1/1400 and 16 at f = 0 and 1/400 (H3 Power). These blocks
    must be disjoint from 006's selection blocks and from the H2 set, on which D_400 is located.
  Seeds 736-1087 are used by no earlier experiment (the highest seed used by 001-008 is 735, 008's block 45).
- The oracle binary is `.cache/oracle-build/src/app/smallpaint_oracle`, the binary of experiments 001-006, sha256
  `066bb5d4247c556ad5232bfc4fff75dc5f37089840b23f1ecc8fdd9cb518828a`. It is not rebuilt, and no oracle option is added.
  Never run `make oracle`: its source has changed since the binary was built (T3.4, TQ.1), a rebuild changes the
  sha256 that keys the render cache, and the 96 reused renders would be orphaned.
- New renders: 352 (22 new blocks × 16): 160 at 200 px, 160 at 800 px and 32 at 1600 px. 96 reused renders are cached.
  `jobs.JOBS` has 448 jobs.

### Cost

- CPU per render, from the cache's `wall_seconds` (single-threaded oracle):
  - 200 px row chain: 6.0-6.1 s (means of `row_s200`, `row_j0_s200`, `row_s200_px`);
  - 800 px: 96.3-103.2 s (means of `row_j0_s800`, `row_s800`, `row_s800_px`; 99 s is used). The fastest of the 48
    renders took 95.06 s and the slowest 117.45 s;
  - 1600 px: 4 × 97 ≈ 390 s, since the cost scales with the pixel count (×4.2 from 200 to 400 px, ×3.8 from 400 to
    800 px).
- Renders: 160 × 6.1 + 160 × 99 + 32 × 390 ≈ 29,300 CPU-s, i.e. 8.1 CPU-hours, about 2.0 h wall with 4 workers on an
  otherwise idle machine (about 2.3 h with the render calls of Commands).
  - Of this, the 1600 px renders take 12,480 s, the H2 set 3,360 s (2 block pairs of one 200 px and one 800 px
    block, 1,682 s each) and the fresh set 13,460 s (8 block pairs). The fresh set's blocks 56-67 add 10,100 s to
    the first draft's 19,200 s.
  - The sample sizes follow from the power analyses (H1-H3); neither passes nor pairs are reduced for cost.
- Analysis, timed on this machine on 2026-10-15 (other planning computations running): 006's `_pair_values` takes
  0.19, 1.04 and 8.3 s per pair at 200, 800 and 1600 px (the 1600 px pair synthesised by doubling a cached 800 px
  pair; peak RSS 1.26 GB), and `ensemble.permutation_pvalue` 0.64-0.85 s per Monte Carlo call (16 or 32 pairs per
  side) and 0.008 s per exact 8-vs-8 call. One run measures about 96 native pairs at 200 px, 16 at 400 px, 96 at
  800 px, 16 at 1600 px and about 160 subsampled pairs (about 5 min), and makes about 200 Monte Carlo and 300 exact
  calls and the bootstraps (about 3-5 min), besides reading about 8 GB of renders: about 8-10 min per run. The card
  runs it twice (byte-for-byte check).
- Smoke run: 112 renders, about 620 CPU-s, about 3 min with 4 workers, plus its analysis.
- 009 in all: about 31,000 CPU-s (8.6 CPU-hours) and about 2.8 h of wall time.
- Combined with 007 and 008, from their drafts of 2026-10-15: 007 renders nothing and estimates about 2 × 10 + 2 × 85
  CPU-min of analysis (about 11,400 CPU-s); 008 estimates about 1,600 CPU-s of renders, and its analysis and `power.py`
  take minutes (at most about 2,400 CPU-s more, from its planning run of about 10 min on 4 cores). The three cards
  need about 44,500-46,500 CPU-s (12.4-12.9 CPU-hours), run one at a time in the order 007, 008, 009 on 4 otherwise
  idle cores.
- Disk. A render's files take 39 bytes per pixel (`sum` 24, `k_consumed` 8, `object_id` 4, `image.ppm` 3), plus at
  most 8 filesystem blocks (32,768 B with 4,096 B blocks) for the array headers (399 B), `meta.json` and `done`
  (under 500 B), the rounding of its six files to whole blocks and its directory. `du` measured 25,152 and 25,600 B
  beyond 39 bytes per pixel on cached 200 and 800 px renders.
  - The new renders of 009 need 7,438,080,000 + 352 × 32,768 = 7,449,614,336 B (GB = 10^9 B: 0.25 GB at 200 px,
    3.99 GB at 800 px and 3.19 GB at 1600 px).
  - 008 runs first on the same filesystem: 64 renders at 400 px, 401,457,152 B by the same bound (008's own figure,
    from `du`, is 400,818,176 B).
  - The smoke caches: 009's 112 jobs need 136,270,016 B; 008's 24 jobs need 10,146,432 B.
  - Together: 7,997,487,936 B before 008 starts.
  - Free space is recorded only as a dated measurement: `df -B1 .cache` showed 4,054,224,896 B available at 18:25 UTC
    on 2026-10-15. The filesystem also holds `/tmp` and the session scratchpads. The orchestrator frees disk before
    the cards render; the cards delete nothing. The preflight compares the free space with the remaining requirement
    before every render call (Commands).
- Memory per render: under 150 MB at 1600 px. The analysis measures one pair at a time.
- Every row chain at 1600 px stays below 2^22 draws. The cached 800 px row-chain renders consumed at most 887,851 draws in
  one row over all 64 passes (`row_s800`, block 32, seed 518), i.e. about 13,900 per (row, pass) chain. A 1600 px row
  has twice the pixels, so about 27,700 draws per (row, pass) chain and about 1.78 M per row over all passes, below
  2^22 − 1 = 4,194,303. K therefore stays below 2^23, the generator's exact range (SPEC §3). The analysis checks the
  bound on every render.

### Commands

The directory is `experiments/009-2026-10-15-scale-limits/`. `2026-10-15` is the date of the Opus commit that creates it with
this pre-registration (README.md and jobs.py): `$(date +%F)` on that day, 2026-10-15 or later and not earlier than
008's date (experiments are numbered and dated in the order they run: 007, 008, 009). The commands below name that
directory.

Dispatch conditions, which the orchestrator establishes before the card starts:
- the cache filesystem has at least the remaining requirement free (Cost, Disk);
- no other CPU-heavy session runs during the render calls (the stop rule below assumes an idle machine).

```
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/009-2026-10-15-scale-limits/analyze.py --preflight --since <scratch>/preflight-1600.json --smoke-cache <scratch>/cache
timeout -k 10 590 env PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python -m painterly_analysis.experiment run experiments/009-2026-10-15-scale-limits/jobs.py --budget 90 --workers 4   # after a passing preflight; both repeated until this exits 0
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/009-2026-10-15-scale-limits/analyze.py
```

- `--preflight` renders nothing. It exits non-zero on any failure, and then nothing is rendered. It checks:
  - the oracle sha256 above;
  - the `done` markers of the 96 reused renders;
  - the free space of the cache filesystem against the bytes (Cost, Disk) of every job not yet done: 009's, those of
    the jitter-dose-response experiment's `jobs.py` (008, found by its slug), and, with `--smoke-cache DIR`, the
    smoke run's in DIR when DIR lies on the same filesystem;
  - with `--since STATE`, the `wall_seconds` of every 1600 px render finished since the previous preflight (the done
    1600 px jobs not listed in STATE). STATE is rewritten only when every check passes.
  It runs before every render call, so a shrinking disk stops the loop before a 100 MB 1600 px render fails partway
  through writing.
- `--budget 90`, not the protocol's 540 s, and `--workers 4` explicitly (`nproc` is 4).
  - 90 s is below the fastest cached 800 px row render (95.06 s), and the jobs run smallest side first. A job starts
    only when a slot frees before 90 s, which only a 200 px job does. So a 1600 px job starts only at the beginning of
    a call, and a call lasts at most one 1600 px render (about 390-470 s, the upper value 4 × 117 s).
  - About 51 calls are needed (about 3 at 200 px, 40 at 800 px with one wave of four renders each, and 8 at 1600 px),
    about 2.3 h of wall time.
  - `timeout -k 10 590` keeps each call under the protocol's 10 minutes. Without `--foreground`, GNU `timeout` signals
    the whole process group, so the oracle processes stop too. A killed render has no `done` marker and is rendered
    again by a later call.
- Stop rule for CPU contention: if a 1600 px render checked by the preflight has `meta.json` `wall_seconds` above 540 s
  (the protocol's per-call budget, `experiment.DEFAULT_BUDGET_SECONDS`), or if a render call does not return within
  10 minutes (`timeout` exits 124, or 137 after the kill), stop and report CPU contention instead of calling again.
  - A render that tripped the rule is kept: the oracle is deterministic, so its output does not depend on its wall
    time.
  - Resuming is Opus's decision. Opus checks that nothing else loads the machine, records an amendment, and adds the
    tripped render's key to STATE, so that the next preflight checks only renders finished after it.
- Smoke run (code check only), with a scratch `PAINTERLY_CACHE` and `--out-dir`:
  `analyze.py --pairs 2 --scale 4`, sides 50, 100, 200 and 400. It rounds τ and e to the nearest integer of at least
  1 px, as 006 did, and says so. It never writes the committed outputs.
- The smoke run and both full analyses take longer than a foreground tool call may run, so the card runs them in the
  background and waits for their exit status (Cost).

### Analysis

- `analyze.py` loads the cache and implements the Common definitions, H1-H3 and E1-E5. It reuses 006's measurement
  functions unchanged (PLAN.md). New code: `metrics.cross_structure_correlation` (ρ_x) with unit tests, and the
  subsampling, departure sets, decomposition, class statistics, readings and bootstrap in `analyze.py`.
- **Design checks**, each of which stops the analysis on failure:
  - `jobs.DESIGN`, `CONFIGURATIONS` and `BLOCK_SETS` match the Method table (sides, f as a `Fraction`, blocks, seeds,
    options, block sets), and no fresh block is a reused, H2 or first block;
  - seeds are unique, and `report.check_seed_reuse` passes against experiments 001-004, 006 and 008;
  - every render has P = 64. All renders of one side share one object-id map;
  - `sub(·, m)`'s object-id map equals the native map for every pointwise contrast;
  - every block has 2 × pairs distinct `sum` arrays (sha256; 16 at full scale), so no replicate repeats a render;
  - every render has at most 2^22 − 1 draws in each row over all passes, which bounds each (row, pass) chain;
  - consistency with 006: the 8-pair-set values of the six reused configurations equal 006's `results.json` `summary`
    (mean and sd of every T and estimation-only key) exactly (`==`); the two (400, 800) comparisons reproduce 006's
    p-values and rejections exactly; the selection procedure (Departure sets) reproduces D_0 and D_1400 exactly; and
    each contains 006's rejected keys.
- **Outputs**:
  - `results.json`: parameters, regions, replicate counts, the chain bound, every comparison (effect summary,
    p-values, Holm decisions, `min_attainable_p`), the H1 readings, the H2 conditions, the departure sets with their
    selection intervals and the state of D_400, the decompositions per unit, χ, the H3 classes and flags, ρ_x and
    ρ_self, class statistics with intervals, `k_per_pass`, the decision records, and the figure encodings;
  - printed tables, one per hypothesis and estimation block;
  - figures, each at most 1 MB, drawn without text, with their encodings in `results.json` (PLAN.md):
    - `fig_grid_row.png`, `fig_grid_row_zero.png` and `fig_grid_row_f400.png`: pair 0 of each side (8-pair set),
      box-downsampled to 200 px tiles;
    - `fig_points_default.png`, `fig_points_zero.png` and `fig_points_f400.png`: native 200 px, 800 px subsampled to
      the same points, and 800 px box-downsampled, as 200 px tiles (pair 0 of the fresh set);
    - `fig_slag_profile.png`, `fig_steps.png` (A, X and Y against side), and `fig_decomposition.png` (Δ, c and u per
      unit of D_f, fresh set).
- Deterministic: exact or fixed-key permutation p-values and seed-0 bootstraps. A second run into a scratch
  `--out-dir` must reproduce every output byte for byte.

### Pre-registration review

- Second review round (2026-10-10): applied 19, rejected 0. The findings are dated 2026-10-10; the edits were made
  and the planning recomputed on 2026-10-15, before any render of this experiment (planning scripts `review5_*.py` in
  the pre-registration's `_planning/`, each with its `_out.txt`; the round-1 texts are kept there as
  `README.round1.md` and `PLAN.round1.md`). The 19 are the 11 skeptic findings, the 5 cross-experiment findings and
  the 3 final-recheck issues that touch this draft.
  - Skeptic findings:
    - (S1, major) H3 decided only on the keys at 006's complete-separation floor, so established departures (X at
      f = 0, A at f = 1/1400) could not decide a class. Applied with 99% intervals: D_0 (15 units) and D_1400
      (8 units) are selected by intervals on 006's blocks and include the class statistics; their c enters χ; the flag
      is renamed "chain difference outside the departure set"; D_400 is H2's rejections plus A, X, Y and `r4.slag.x`
      by interval. Modified: the outside family also holds the class statistics not in D_f (X and Y at f = 1/1400),
      and D_400's interval candidates are limited to these four, because an interval selection over the 18 keys picks
      a key with no departure in about 0.35 of draws.
    - (S2, major) H1 read G, F or S from s2 intervals that contain 0. Applied: σ only from an s2 interval that
      excludes 0, otherwise N (without σ) or "not separated", which makes a family inconclusive; a rejected key is read
      by its own intervals when its class's s2 interval contains 0; the default family's rates under truth N are in
      H1 Power (refuted 0.38 / 0.69, partially supported (G) 0.007 / 0.013).
    - (S3, minor) H2's "reduction" was a signed shift, so a larger reversed departure read as reduced. Applied as a
      variant: *reduced* needs Δ_400 on Δ_1400's side as well as the shift; a Δ_400 on the other side reads
      *reversed*, and H2 "not shown (reversed)"; *removed* keeps the shift alone.
    - (S4, minor) H2's refutation power ignored the sd growth, and an empty D_400 read "no departure". Applied: power
      0.47 / 0.25 for `r4.slag.x` alone; f = 1/400 has "no departure" only if H2 reads supported (removed), and
      otherwise D_400 is located (S1). Modified: a departure that is not located does not lower H3's verdict, because
      reading it inconclusive would tie H3 to H2's removal power (H3, Footprint verdicts).
    - (S5, minor) The Holm text at 0.01/18 omitted 6/12,870. Applied, with what such a rejection means.
    - (S6, blocker) Disk. Applied under Opus's rule: the requirement in bytes (now with a per-render block bound), the
      free space as a dated measurement, and the orchestrator frees disk before rendering (Cost, Commands).
    - (S7, major) Tool-call limits. Applied: `timeout -k 10 590` around each render call, and the smoke run and both
      analyses in the background (PLAN). The analysis was re-timed: 8-10 min per run; an exact 8-vs-8 call takes
      0.008 s here, not the finding's 0.42 s, so the tests take about 3-5 min, not 4-5.
    - (S8, major) Smoke-scale crashes. Applied in PLAN: the sd of fewer than two values is None, every tile goes
      through 006's `_preview`, the digest check counts 2 × pairs, and an underpowered H2 makes f = 1/400
      inconclusive (underpowered).
    - (S9, minor) The contention stop rule could never clear. Applied: `--since STATE`, a dispatch condition, and
      resumption by an Opus amendment (Commands).
    - (S10, minor) The test import. Applied in PLAN (`report.load_jobs_module`).
    - (S11, minor) The directory date. Applied under Opus's rule (`2026-10-15`, the date of the Opus pre-registration
      commit; Commands).
  - Cross-experiment findings:
    - (C1) Disk, merged with S6; the smoke caches are counted.
    - (C2) `k_per_sample` is renamed `k_per_pass`, and "draws per sample" "K stride", as in 007.
    - (C3) "Frame" for a set of blocks is renamed "block set" (`BLOCK_SETS`, `_FRESH_SET`, `_block_set`).
    - (C4) The 86,400 CPU-s limit has no source in the repository and is deleted. The combined estimate is added
      with 007's current figure (about 11,400 CPU-s of analysis, not the finding's 3,700).
    - (C5) 008's `jobs.py` is found by its slug.
  - Final-recheck issues: (R1) disk, as S6; (R2) every interval that enters a decision is 99%, with the planning
    recomputed and the sample sizes rechecked (H3 Power: 32 pairs at f = 1/1400 and 16 at f = 0 remain needed);
    (R6) dates, as S11, except its advice to keep the `experiments/008-*` globs, which C5's slug lookup replaces.
    (R11 needed no action.)
  - Opus rules for this pass: the dated directory placeholder (Commands); the disk requirement in bytes with the free
    space recorded as a dated measurement (Cost); every interval 99% (Bootstrap); never run `make oracle`
    (Configurations, PLAN).
  - Found while recomputing: H2's Holm test is not exact when the 200 and 800 px sds differ as the stand-ins do
    (family-wise error 0.020-0.028; H2 Power). It is stated, not changed.

### Amendment 1 (Opus, 2026-10-15, before any render or analysis of this experiment): a new machine

On 2026-10-15 the project moved from a cloud container to the owner's machine. The render cache and the experiments'
oracle binary (`066bb5d4…`) did not move. Nothing of this experiment had been rendered or analysed.
- **The oracle** is rebuilt on the new host from the source tree of commit `d2259e7^`, the last commit before T3.4
  changed `src/app/`.
  - `src/app/` there is unchanged since `b390efa`, so this is the source of `066bb5d4…`.
  - Build: `-DCMAKE_BUILD_TYPE=Release -DPAINTERLY_BUILD_MODULE=OFF -DPAINTERLY_BUILD_TESTS=OFF`, GCC 15.2.0.
  - Its sha256 is `804a2dc2722167aab472aacc2c0cce4bba53f28f155d63b7a0f2c827a0395954`. It replaces `066bb5d4…` wherever this README names the binary, and `PLAN.md` is updated to
    match.
  - "Never rebuild it" now applies to this binary.
- **The renders.** Every render this experiment uses, whether Method calls it reused or new, is regenerated on the host
  with unchanged job definitions: jobs, seeds, blocks and options. The analysis reads the cache read-only and renders
  nothing. The host does Method's render and disk steps before the analysis starts.
- **Reproduction first.** The analysis starts only after a separate check (backlog item EXP-REPRO) has re-run the
  analyses of experiments 001-004 and 006 on the regenerated renders and found every committed output byte-identical.
  If any output differs, this analysis does not start, and Opus decides by a further amendment before any of this
  experiment's data is examined.
- **Unchanged:** Background, Hypothesis, and every decision rule, level, key list, exclusion, seed and block in Method.

## Results

Pending: the analysis card fills this in.

## Conclusion

Pending: written after the analysis (DRAFT by the card, final by a strong model).
