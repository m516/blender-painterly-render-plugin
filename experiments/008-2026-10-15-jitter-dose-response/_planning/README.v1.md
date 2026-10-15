# Experiment 008: how does the texture respond to the jitter dose? (knob range and scale for M7)

## Background

- `docs/plan.md`, "What makes the look", item 3 (scan-line chaining): the K stream gives a converged texture,
  structure std ≈ 5 grey levels. `docs/spec.md` §3: `chain=row` is the Blender default (experiment 003).
- `docs/spec.md` §7 (changed by experiment 006): the Blender knob `jitter` is a **fraction f of the camera's fitted
  image side**, default f = 1/1400. The displacement in pixels is uniform in [−f·F, +f·F] on each axis, F the fitted side in
  pixels. The oracle's `--jitter` is in **image-plane units**, j = 2f, because the image plane spans 2 units across the
  side. The oracle default is j = 1/700 (`painterly.cpp:291-292`), i.e. f = 1/1400.
- `experiments/006-2026-10-09-jitter-units/` (final):
  - With jitter fixed on the image plane, 400 and 800 px are indistinguishable on all 18 texture keys, in both chains
    and with zero jitter (H1, H4). A dose f measured at 800 px therefore predicts the same dose at 400 px. 200 px departs
    slightly (floor amplitude up to −7%), so 200 px points are used below with that caveat.
  - The jitter footprint is a stroke-softness control (Decision 2). At 400 px, row chain, f = 0 vs f = 1/1400:
    `structure_std` is higher by +0.98 to +2.74 display bytes in the six regions (rel +0.29 to +0.41, d +15 to +30),
    and the wall `slag.y` is lower: r4 0.140 vs 0.264, r5 0.167 vs 0.278, r6 0.180 vs 0.397.
  - Measured row-chain points of `r4.structure_std` (display bytes): 7.273, 5.783 and 5.284 at 800 px for f = 0, 1/2800
    and 1/1400; 6.788, 5.316 and 4.842 at 200 px for f = 0, 1/1400 and 1/700. "Most of the change is near 0": at
    800 px the first 1/2800 of the side gives 75% of the drop to 1/1400.
  - "Hypotheses for later work", jitter dose-response: `structure_std` falls strictly with jitter in every region,
    `slag.y` rises on the walls (r4, r5, r6), and the steps shrink as jitter grows. Test: row chain, 400 px, f = 0,
    1/5600, 1/2800, 1/1400, 1/700 and 1/350; adjacent pairs on T with one-sided permutation tests and Holm.
  - Its practice lessons, applied here: (a) replicates are independent (row chain: 16 distinct renders per
    configuration, also at f = 0, 006 Table 7); (b) each hypothesis gets the contrast that separates its readings;
    (c) per-key classifications use a noise floor, here one seed-to-seed sd; (d) every Holm verdict comes with an
    effect statistic; (e) every jitter value names its unit.
- `docs/plan.md`, M7: T7.1 lays out the panel (soft limits of each knob) and T7.2 builds presets ("Fine strokes",
  "Broad strokes"). This experiment supplies the measured response of the jitter knob: its range and its scale.
- What this experiment does not measure: region masks are eroded 4 px from edges, so nothing here measures edge
  aliasing, which also changes with jitter (006 Decision 2). The image chain is not used: with `chain=image` and
  f = 0 every seed renders the same image (006 amendment 1).
- Renders:
  - The oracle is the experiments' binary in `.cache/oracle-build`, the binary of experiments 001-006, with sha256
    `066bb5d4247c556ad5232bfc4fff75dc5f37089840b23f1ecc8fdd9cb518828a`. Its source has changed since (T3.4 added
    default-identical knobs), so a rebuild would change the sha256 and orphan the cache. It is not rebuilt, and no
    oracle option is added.
  - Two configurations are 006's cached ensembles (blocks 40 and 27). The four new ones take blocks 42-45, the first
    free blocks after 006's last block (41). Experiment 009 takes blocks 46-49.

## Hypothesis

### Common definitions

- **Configurations.** Six ensembles of 8 pairs. A pair is two independent half renders, seeds 2k and 2k+1 of the
  configuration's block, each with P = 64 passes, `chain=row`, side 400 px, `scene=gui` and `ghost=all` (oracle
  defaults). A configuration differs from the others only in its jitter.
- **Dose.** f_0 … f_5 = 0, 1/5600, 1/2800, 1/1400, 1/700, 1/350 of the side. Configuration `fN` has f = 1/N; `f0` has
  f = 0. In image-plane units (oracle `--jitter`) j = 2f = 0, 1/2800, 1/1400, 1/700, 1/350, 1/175. At 400 px the maximum
  displacement f·400 is 0, 1/14, 1/7, 2/7, 4/7 and 8/7 px.
- **Steps.** Step i goes from f_i to f_{i+1}, i = 0 … 4. Steps 1-4 are doublings of f. Step 0 starts at 0 and has the
  same width in f as step 1 (1/5600 of the side).
- **Metrics.** Exactly 006's scale-equivariant definitions (006 README, Common definitions) at s = s₀ = 400 px, where
  they need no scaling:
  - high-pass `hp = x − G_σ * x` of the luminance of a half render's display bytes, σ = (9/√12)·s/400 = 2.598 px,
    on the half-sample-symmetric extension (`metrics.gaussian_highpass`);
  - regions: SPEC §9 ids 2-8 eroded by 4·s/400 = 4 px; regions empty in any configuration are excluded everywhere and
    reported (006 measured 2-7; 8 is absent from the object-id map);
  - lag τ = s/200 = 2 px;
  - per region r and pair (a, b): `r{r}.structure_std = sqrt(cov₀)` in display bytes, and `r{r}.slag.x`, `r{r}.slag.y`
    = cov_τ / cov₀ (`metrics.noise_corrected_lag`), dimensionless. They measure the structure that independent seeds
    share, i.e. the converged look.
  - **T** = the 18 keys `structure_std`, `slag.x`, `slag.y` over the six measured regions. Estimation-only keys:
    `r{r}.mean.{R,G,B}` of the summed display image `ab8` on the eroded masks (display bytes) and `r{r}.spectral_slope`
    (f_min = 2, f_max = 50 cycles per image).
  - The object-id map comes from the unjittered primary ray, so the masks are identical in every configuration.
  - Consistency: `f0` and `f1400` are 006's `row_j0_s400` and `row_s400` (same renders, same definitions), so their
    values must equal 006's `results.json` `summary` exactly.
- **Key classes.** A = the six `structure_std` keys (stroke contrast). W = `r4.slag.y`, `r5.slag.y`, `r6.slag.y` (wall
  stroke softness). M = the 18 region-mean keys.
- **Step effects.** For key k and step i: Δ_i(k) = mean_k(f_{i+1}) − mean_k(f_i), and d_i(k) = Cohen's d of f_{i+1}
  vs f_i (`ensemble.effect_summary`, pooled sd s_p of the two configurations).
- **Seed-to-seed sd.** s_p is the sample sd over 8 independently seeded pairs, pooled over the two configurations. A
  step with |d| < 1 changes the key by less than independently seeded pairs differ from each other. This is the noise
  floor of every per-key classification below. It is measured, not chosen. It belongs to this design: P = 64 per half,
  400 px, regions eroded by 4 px. More passes or larger regions give a smaller sd.
- **Significance.** The family-wise level of each hypothesis is 0.01 (`SIGNIFICANCE`; not the oracle option `alpha`).
  Every p-value is an exact permutation p-value (`ensemble.permutation_pvalue`), one-sided where the hypothesis has a
  direction. Holm (`ensemble.holm`) runs over the family stated in each hypothesis.
- **Power.** With 8 vs 8 pairs, the smallest attainable p is 1/C(16, 8) = 7.77e-5 one-sided and 1.55e-4 two-sided. At
  the first Holm thresholds below, a rejection needs complete or near-complete separation of the two ensembles, so every
  verdict is reported with d (lesson d). A family whose smallest attainable p exceeds its first Holm threshold is
  reported as inconclusive (underpowered). Only the smoke run can be in that state.
- **Bootstrap.** Pairs are resampled with replacement within each configuration, `BOOTSTRAP_RESAMPLES = 10_000`, numpy
  `default_rng(0)`, as in 006. Decisions use the 99% percentile interval (level 0.01, matching `SIGNIFICANCE`); the 95%
  interval is also reported. The resample count sets only the Monte Carlo precision.

### H1: structure amplitude falls strictly with f in every region

- Derived from: 006. The footprint averages each pixel's paths over an image-plane square of half-width f·side, which
  removes part of the structure (006 Conclusion, point 2). Every measured dose pair in 006 shows a fall (Background).
  The per-doubling falls are −0.27 to −0.76 display bytes:

  | region | 800 px, f 1/2800 → 1/1400 | 200 px, f 1/1400 → 1/700 | 400 px sd (`f0`, `f1400`) | predicted d per doubling at 400 px |
  |---|---:|---:|---|---:|
  | r2 | −0.535 | −0.574 | 0.119, 0.110 | 4.8 |
  | r3 | −0.502 | −0.589 | 0.081, 0.037 | 9.3 |
  | r4 | −0.499 | −0.473 | 0.077, 0.089 | 5.9 |
  | r5 | −0.338 | −0.268 | 0.073, 0.054 | 4.8 |
  | r6 | −0.667 | −0.764 | 0.073, 0.117 | 7.5 |
  | r7 | −0.573 | −0.654 | 0.131, 0.115 | 5.0 |

  (predicted d = mean of the two falls / mean of the two 400 px sds). Step 0 has no 006 point below 1/2800; at 800 px
  the step 0 → 1/2800 falls by 0.78 to 2.19 display bytes. A fit of m(f) = m₀ − b·log₂(1 + f/f_c) to 006's 800 px
  r4 points (f_c ≈ 1/14000 of the side; it reproduces their slope ratio, 0.34) predicts step 0 at 2.0 times and
  step 1 at 0.86 times the mean of the two doubling steps in the table.
- Readings: (i) **monotone**: the knob acts over the whole range; (ii) **saturation**: it stops acting above some f,
  which then bounds the knob; (iii) **reversal**: the amplitude rises again, and the knob is not monotone.
- Observable: class A at the six doses, 30 cells (6 regions × 5 steps).
- Test: per cell, the one-sided exact permutation test "f_{i+1} lower than f_i". Holm over the 30 cells at 0.01. First
  threshold 0.01/30 = 3.33e-4 ≥ 7.77e-5: powered. The one-sided p of "f_{i+1} higher" is reported for each cell,
  uncorrected (estimation).
- Classification of each cell that Holm does not reject, by its d: d ≤ −1 *unresolved fall*; |d| < 1 *flat* (below one
  seed-to-seed sd); d ≥ +1 *rise*.
- Decision: **supported** iff all 30 cells are Holm-rejected falls. **Refuted** iff some cell is *flat* (saturation) or
  *rise* (reversal); the Conclusion names the reading and the cells. **Inconclusive** iff every non-rejected cell is an
  *unresolved fall*.
- Power check (simulation: two normal samples of 8 shifted by d sd, exact one-sided permutation p on the mean
  difference, Holm over 30 cells, 1,000 simulated designs per row; Monte Carlo sd ≤ 0.016): probability that all 30
  cells are rejected when every cell has the same d: d = 2.0: 0.002; 2.5: 0.43; 3.0: 0.96; 3.5: 0.998; 4.0: 1.0. With
  the predicted d of the table (step 0 at 2.0 and step 1 at 0.84 times it): 1.0. Putting the 30 "higher" tests into
  the same Holm family would lower the probability to 0.77 at d = 4 (400 simulated designs), which is why rises are
  classified by d instead.

### H2: the short-lag autocorrelation `slag.y` rises with f on the walls

- Derived from: 006. Wall `slag.y` rises with f at every measured dose pair: 400 px f 0 → 1/1400: r4 0.140 → 0.264,
  r5 0.167 → 0.278, r6 0.180 → 0.397 (d 7.9, 2.9, 12.9); 800 px f 0 → 1/2800 → 1/1400: r4 0.130 → 0.207 → 0.248, r5
  0.159 → 0.235 → 0.280, r6 0.190 → 0.323 → 0.380; 200 px f 1/1400 → 1/700: r4 0.251 → 0.336, r5 0.251 → 0.334, r6
  0.389 → 0.496. A wider footprint mixes neighbouring image-plane positions into each pixel, so the structure stays
  correlated over a longer distance: softer strokes. On the sphere (r2), the floor (r3) and the ceiling (r7) `slag.y`
  lies between −0.14 and +0.15 at every 006 row-chain dose and size, with no consistent direction, so no direction is
  predicted there.
- Readings: (i) **monotone softening**: "jitter softens strokes" holds over the whole range; (ii) **non-monotone**: the
  softening reverses somewhere, and the knob description needs a range.
- Observable: class W at the six doses.
- Tests, one family of 18, Holm at 0.01 (first threshold 5.56e-4 ≥ 7.77e-5: powered):
  - (a) overall rise: `f350` vs `f0`, one-sided "higher", for each wall (3 tests);
  - (b) reversal: each step, one-sided "f_{i+1} lower than f_i", for each wall (15 tests).
- Decision: **supported** iff all three (a) are rejected and no (b) is. **Refuted (reversal)** iff some (b) is rejected.
  **Refuted (no rise)** iff some (a) is not rejected; its d is reported. Both may apply.
- Estimation: per step and wall the one-sided p of "higher" (uncorrected) and d; `slag.x` in every region and `slag.y`
  on r2, r3 and r7.
- Power check: the f 0 → 1/1400 rise alone has d 2.9 to 12.9 at 400 px. Adding 006's 200 px step (f 1/1400 → 1/700)
  gives rises of +0.20 to +0.32 to f = 1/700, d ≥ 5 with 006's sds; (b) tests whether anything is lost above that.
  Simulated as for H1 (4,000 designs per d), one one-sided test at the first threshold 5.56e-4 rejects with probability
  0.92 at d = 3, 0.98 at d = 3.5 and 0.998 at d = 4.

### H3: the response has diminishing returns (effect statistics)

The step ratios below use class A. They are effect statistics with bootstrap intervals; no permutation p-value enters.

- **H3a: diminishing returns in f.**
  - Derived from: 006's "the steps shrink as jitter grows". At 800 px the two equal halves of [0, 1/1400] give slope
    ratios (second half / first half) of 0.37, 0.34, 0.34, 0.44, 0.31 and 0.36 in r2-r7 (median 0.35).
  - Statistic: the slope of step i is Δ_i / w_i, with widths w_i = 1/5600, 1/5600, 1/2800, 1/1400, 1/700 of the side.
    The slope ratio of consecutive steps is q_0 = Δ_1/Δ_0 and q_i = Δ_{i+1}/(2Δ_i) for i = 1, 2, 3. Q is the median of
    q over the 6 regions × 4 ratios.
  - Decision: **supported** iff the 99% interval of Q lies below 1. **Refuted** (accelerating) iff it lies above 1.
    Otherwise **inconclusive**.
- **H3b: the response per doubling is logarithmic in f (scale of the M7 control).**
  - Derived from: the per-doubling falls in H1's table. The 200 px fall (f 1/1400 → 1/700) divided by the 800 px fall
    (f 1/2800 → 1/1400) is 1.07, 1.17, 0.95, 0.79, 1.15 and 1.14 in r2-r7 (median 1.11): a constant change per doubling,
    i.e. m(f) = a + b·log₂ f. This crosses two sides, and 200 px departs slightly (006 H1), hence a test.
  - Statistic: R is the median of ρ_i = Δ_{i+1}/Δ_i over the 6 regions × the three doubling pairs i = 1, 2, 3 (f from
    1/5600 to 1/350). For m = a + b·f^γ, ρ = 2^γ; for m = a + b·log₂ f, ρ = 1. The reference values are definitions:
    R = 1 is logarithmic, R = 2 is linear in f, R < 1 saturates faster than logarithmic. γ = log₂ R is reported when
    R > 0.
  - Classification by the 99% interval I_R: below 1 → *saturating*; contains 1 but not 2 → *logarithmic*; inside
    (1, 2) → *power law with 0 < γ < 1*; contains 2 but not 1 → *linear*; above 2 → *accelerating*; contains both →
    *inconclusive*.
  - Decision: **supported** iff *logarithmic*. Otherwise refuted with the class named, or inconclusive.
- Power check (delta method with 006's 400 px sds and the steps of H1's table; consecutive steps share a
  configuration, which adds their covariance): the sd of one ρ is 0.10-0.18, and the 99% half-width of their median R
  is about 0.15. That separates 1 from 2. For H3a the log fit predicts q_0 ≈ 0.43 and q_1…q_3 ≈ 0.5-0.55, with a
  half-width of the same order, so 1 is far outside. The bootstrap gives the actual widths.
- Estimation only: Q and R for class W, and per-region ratios for A and W. A ratio whose denominator step has the sign
  opposite to its class's median step is counted and reported.

### H4: region means do not depend on f

- Derived from: the eroded masks keep only pixels at least 4 px from a region edge, while the largest footprint reaches
  8/7 px, so no footprint of a measured pixel leaves its region. Averaging a smooth radiance field over a small
  symmetric square leaves its mean unchanged to first order. In 006 at 400 px, f 0 vs f 1/1400, the 18 means differ by
  at most 0.239 display bytes (`r2.mean.B`, rel −0.0017), with |d| ≤ 1.85 (`r3.mean.B`).
- Readings: (i) **tone-invariant**: the knob changes texture only; (ii) **tone-shifting**: the knob also moves region
  colour, which the knob description must then state.
- Test: the extreme contrast `f350` vs `f0`, two-sided exact permutation tests on the 18 keys of M, Holm at 0.01. First
  threshold 5.56e-4 ≥ 1.55e-4: powered.
- Decision: **supported** iff no key is rejected; **refuted** iff some key is. Reported with the verdict: the largest
  |abs diff| in display bytes with its rel diff and d, and every rejected key's abs diff.
- Power check: the two-sided first threshold 5.56e-4 is a one-sided 2.78e-4. Simulated as for H1 (4,000 designs per
  d), a key is rejected there with probability 0.94 at |d| = 3.5 and 0.99 at |d| = 4. With 006's pooled 400 px sds, |d|
  = 4 is a shift of 0.084 (`r6.mean.B`) to 0.85 (`r2.mean.B`) display bytes. Smaller shifts may go undetected, so
  "supported" is written with these limits.
- Estimation: effect summaries of every step on M, and of each dose against the SPEC default `f1400`.

### E1: knob range and scale for M7 (estimation; the rule is registered)

- Derived from: the M7 need for soft limits and spacing, without invented thresholds. The unit is the seed-to-seed sd
  (Common definitions). The steps of this design are doublings of f, the natural unit of a logarithmic control.
- Statistics, for a class C ∈ {A, W} (T is also reported):
  - D_i(C) = median over C of |d_i|, the size of step i in seed-to-seed sds (steps 1-4 are doublings);
  - D0_k(C) = median over C of |d| of `f_k` vs `f0`, k = 1 … 5;
  - **upper limit f_hi(C)**: the smallest f_k, k = 0 … 4, with D_i(C) < 1 for every i ≥ k. Above f_hi every further
    step (a doubling of f) changes the class by less than one seed-to-seed sd. If D_4(C) ≥ 1, f_hi(C) is "at or above
    1/350" (not reached);
  - **lower limit f_lo(C)**: the largest f_k, k = 1 … 5, with D0_j(C) < 1 for every j ≤ k. Up to f_lo the class is
    within one seed-to-seed sd of zero jitter. If D0_1(C) ≥ 1, f_lo(C) is "below 1/5600" (not resolved);
  - **normalized response** N_C(f_k) = median over C of (mean(f_k) − mean(f0)) / (mean(f350) − mean(f0)): 0 at f = 0,
    1 at f = 1/350. It uses means only, so it does not depend on P;
  - **cumulative sd units** S_C(f_k) = Σ_{i<k} D_i(C).
  - Bootstrap (as above): the fraction of resamples giving each grid value of f_hi and f_lo, and the 95% and 99%
    intervals of N_C(f_k).
- Registered recommendation for M7, written in the Conclusion from these numbers only:
  - soft range = [min(f_lo(A), f_lo(W)), max(f_hi(A), f_hi(W))]: the range where at least one visible property still
    responds by at least one seed-to-seed sd. 0 stays selectable as "off". An unresolved end is stated as a bound;
  - scale = H3b's class: *logarithmic* → a control linear in log₂ f; *linear* → linear in f; any other class → the
    measured N_A table, piecewise linear in log₂ f between grid points;
  - default position = N_A(1/1400), where the SPEC default sits on the measured response;
  - presets (T7.2) are not decided here. The A and W tables per dose are their input.
- Caveat: D, f_hi and f_lo are P = 64 quantities. More passes shrink the sd, raise every d, and can only widen
  [f_lo, f_hi]. N does not depend on P.
- Expectation, from 006's numbers: per-doubling D(A) ≈ 5-9 and step 0 even larger. Then neither limit is reached
  inside this grid, and the result is a bound: the knob acts over at least the factor 16 from 1/5600 to 1/350 of the
  side. The limits themselves then become a hypothesis for later work, with doses below 1/5600 and above 1/350.

## Method

### Configurations

| name | f (fraction of side) | j (image-plane, oracle `--jitter`) | max displacement at 400 px | block (seeds) | source |
|---|---|---|---|---|---|
| `f0` | 0 | 0 (passed as `0.0`) | 0 px | 40 (640-655) | 006 `row_j0_s400` (cache) |
| `f5600` | 1/5600 | 1/2800 | 1/14 px | 42 (672-687) | new |
| `f2800` | 1/2800 | 1/1400 | 1/7 px | 43 (688-703) | new |
| `f1400` | 1/1400 (SPEC §7 default) | 1/700 (oracle default, not passed) | 2/7 px | 27 (432-447) | 006 `row_s400` = 004 `row_s400` = 003 `row` (cache) |
| `f700` | 1/700 | 1/350 | 4/7 px | 44 (704-719) | new |
| `f350` | 1/350 | 1/175 | 8/7 px | 45 (720-735) | new |

Every configuration: `chain=row`, `size=400`, `passes=64`, 8 pairs (16 seeds).

- `jobs.py` declares these with `ensemble_jobs`. It passes `jitter` only where j differs from the oracle default 1/700,
  as 006 does, so `f0` and `f1400` have exactly 006's option sets and seeds, and their 32 renders are cached.
- New renders: 64 (16 per new configuration). Estimated oracle time from the cache's `wall_seconds` for row-chain
  400 px renders: 24.0 s at f = 0 and 25.4 s at f = 1/1400 (means of 16), so about 1,600 s of CPU, about 7 minutes on
  this container's 4 cores: one `--budget 540` call in expectation.
- Sample size: 8 pairs and P = 64, as in 006. The power checks above show this suffices for H1, H2, H3 and H4 at the
  effects 006 predicts. A larger ensemble would not move E1's limits into the grid, because they are set by the doses.

### Commands

The preflight runs first and stops unless the oracle binary has the registered sha256 and all 32 reused renders are in
the cache. Without it, a different binary would re-render the reused configurations. `make oracle` is never run.

```
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/008-2026-10-09-jitter-dose-response/analyze.py --preflight
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python -m painterly_analysis.experiment run experiments/008-2026-10-09-jitter-dose-response/jobs.py --budget 540   # repeat until exit 0
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/008-2026-10-09-jitter-dose-response/analyze.py
```

Smoke run (code check only): `analyze.py --pairs 2 --scale 4 --out-dir <scratch>` with a scratch `PAINTERLY_CACHE`.
It renders its own 100 px jobs. Every dose is kept, because f is a fraction of the side. As in 006, a lag or erosion
that is not an integer number of pixels is rounded to the nearest integer ≥ 1 and the rounding is printed (at 100 px,
τ = 0.5 → 1 px). Every printed line starts with `SMOKE (code check only): `, `results.json` holds `"smoke": true`, and
the committed outputs are never written.

### Analysis

- **Design check.** `jobs.DESIGN` matches the table above (doses, blocks, options, seeds). Seeds are unique across
  configurations. At full scale, `report.check_seed_reuse` against the `jobs.py` of 001-004 and 006 accepts exactly the
  two declared reuses. The replicate check counts distinct `sum` arrays: 16 of 16 per configuration is expected, and a
  configuration with fewer marks every decision that uses it as not interpretable (as in 006).
- **Consistency check (full scale).** The `summary` (mean and sd of every T and estimation-only key) of `f0` and `f1400`
  equals 006's `results.json` `summary` of `row_j0_s400` and `row_s400`, exactly. A mismatch stops the analysis. It was
  run once while this README was written, on the cached renders only: 0 mismatches over the 42 keys of each, and 16
  distinct renders in each. No new render existed then.
- **Metrics.** 006's own code computes them (`PLAN.md`), so the definitions are identical.
- **Power numbers.** `power.py` re-runs the simulations of the power checks in JAX and prints them. The numbers above
  are Monte Carlo estimates and are not changed by it.
- **Outputs.**
  - `results.json`: configurations (f, j, options, seeds), the oracle sha256, parameters and regions, replicate
    counts, `summary`, every step's effect summary on T and the estimation-only keys, H1-H4 records (p-values, Holm
    decisions, d, classifications, decisions), H3's statistics with intervals, E1's tables and bootstrap
    distributions, the recommendation fields, and the figure encodings.
  - `fig_dose_response.png`: mean ± sd over pairs against dose. Left panel: class A, one series per region. Right panel:
    class W. The doses 1/5600 … 1/350 sit at equal spacing (log₂ f), and f = 0 sits 1.5 spacings left of 1/5600, joined
    by a dashed line, because it is off the log axis. No text is drawn; the encoding is recorded in `results.json`.
  - `fig_crops.png`: pair 0's `ab8` at native resolution, no resampling, 2 rows × 6 columns (doses in order). Row 1 is
    the window rows [0.30, 0.54) × columns [0.60, 0.84) of the side (back wall and its edge with the right wall). Row 2
    is rows [0, 0.24) × columns [0.76, 1.0) (the diagonal ceiling/right-wall edge). The edges are shown, not measured.
  - Each figure is at most 1 MB; the analysis fails otherwise.
