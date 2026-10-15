# Experiment 008: how does the texture respond to the jitter dose? (knob range and scale for M7)

## Background

- `docs/plan.md`, "What makes the look", item 3 (scan-line chaining): the K stream gives a converged texture,
  structure std ≈ 5 grey levels. `docs/spec.md` §3: `chain=row` is the Blender default (experiment 003).
- `docs/spec.md` §7 (changed by experiment 006): the Blender knob `jitter` is a **fraction f of the camera's fitted
  image side**, default f = 1/1400. The displacement in pixels is uniform in [−f·F, +f·F] on each axis, F the fitted side in
  pixels. The oracle's `--jitter` is in **image-plane units**, j = 2f, because the image plane spans 2 units across the
  side. The oracle default is j = 1/700 (`painterly.cpp:291-292`), i.e. f = 1/1400. Display bytes are integers:
  `byte = min((int)sum / s, 255)`.
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
  - Its practice lessons, applied here:
    - (a) replicates are independent: row chain, 16 distinct renders per configuration, also at f = 0 (006 Table 7);
    - (b) each hypothesis gets the contrast that separates its readings;
    - (c) no class rests on a point estimate: every class is a Holm verdict or a 99% interval against a margin that is
      a definition (the display quantum, or reference exponents);
    - (d) every Holm verdict comes with an effect statistic;
    - (e) every jitter value names its unit.
- `docs/plan.md`, M7: T7.1 lays out the panel (soft limits of each knob) and T7.2 builds presets ("Fine strokes",
  "Broad strokes"). This experiment supplies the measured response of the jitter knob, its scale and its default
  position. It does not set the soft limits (E1).
- What this experiment does not measure: region masks are eroded 4 px from edges, so nothing here measures edge
  aliasing, which also changes with jitter (006 Decision 2). The image chain is not used: with `chain=image` and
  f = 0 every seed renders the same image (006 amendment 1).
- Renders:
  - The oracle is the experiments' binary in `.cache/oracle-build`, the binary of experiments 001-006, with sha256
    `066bb5d4247c556ad5232bfc4fff75dc5f37089840b23f1ecc8fdd9cb518828a`. Its source has changed since (T3.4 added
    default-identical knobs), so a rebuild would change the sha256 and orphan the cache. It is not rebuilt, and no
    oracle option is added.
  - Two configurations are 006's cached ensembles (blocks 40 and 27). The four new ones take blocks 42-45, the first
    free blocks after 006's last block (41). Experiment 009 takes blocks 46-67 (seeds 736-1087).

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
    share, i.e. the converged look. The noise of the two halves is independent, so what they estimate (the structure
    variance and its autocorrelation) does not depend on P; only their sampling noise does.
  - **T** = the 18 keys `structure_std`, `slag.x`, `slag.y` over the six measured regions. Estimation-only keys:
    `r{r}.mean.{R,G,B}` of the summed display image `ab8` (both halves, 128 passes) on the eroded masks, in display
    bytes, and `r{r}.spectral_slope` (frequency band 2 to 50 cycles per image, the `f_min` and `f_max` arguments of
    `metrics.radial_spectral_slope`, as in 006).
  - The object-id map comes from the unjittered primary ray, so the masks are identical in every configuration.
  - Consistency: `f0` and `f1400` are 006's `row_j0_s400` and `row_s400` (same renders, same definitions), so their
    values must equal 006's `results.json` `summary` exactly.
- **Key classes.** A = the six `structure_std` keys (stroke contrast, display bytes). W = `r4.slag.y`, `r5.slag.y`,
  `r6.slag.y` (wall stroke softness, dimensionless). M = the 18 region-mean keys (display bytes).
- **Step effects.** For key k and step i: Δ_i(k) = mean_k(f_{i+1}) − mean_k(f_i), in the key's unit, and d_i(k) =
  Cohen's d of f_{i+1} vs f_i (`ensemble.effect_summary`, pooled sd s_p of the two configurations).
- **Seed-to-seed sd.** s_p is the sample sd over 8 independently seeded pairs, pooled over the two configurations. It
  belongs to this design (P = 64 per half, 400 px, regions eroded by 4 px): more passes or larger regions give a smaller
  sd. Quantities in units of s_p (d, and E1's D) are therefore properties of the design, not of the knob, and no
  statement about the knob is decided by them.
- **Display quantum.** One display byte: the step between adjacent display levels (SPEC §7 display bytes are
  integers). It is a definition, not a tuned value. It is the margin of H4.
- **Significance.** The family-wise level of each test family is 0.01 (`SIGNIFICANCE`; not the oracle option
  `alpha`). Every p-value is an exact permutation p-value (`ensemble.permutation_pvalue`), one-sided where the
  hypothesis has a direction. Holm (`ensemble.holm`) runs over the family stated in each hypothesis. H1 and H2 have a
  family per direction. Their verdicts are disjoint, and each verdict rests on one family, so the error rate of each
  verdict is at most 0.01. H4's equivalence tests need no correction, because its claim is an intersection-union
  statement (H4, Levels).
- **Resolved.** A cell, step or contrast is *resolved* in a direction when Holm rejects it in that direction's family.
  A non-rejected one is *unresolved*. It is never called flat: with 8 vs 8 pairs, the 99% bootstrap interval of d has
  a median half-width of 1.57 at d = 0, and it lay inside (−1, 1) in 0 of 1,000 simulated designs at d = 0 and at
  d = 0.5 (planning simulation, 2,000 resamples). Equivalence to zero within one seed sd cannot be shown with this
  design.
- **Power.** With 8 vs 8 pairs, the smallest attainable p is 1/C(16, 8) = 7.77e-5 one-sided and 1.55e-4 two-sided. At
  the first Holm thresholds below, a rejection needs complete or near-complete separation of the two ensembles, so every
  verdict is reported with Δ and d (lesson d). A family whose smallest attainable p exceeds its first Holm threshold is
  reported as inconclusive (underpowered). Only the smoke run can be in that state.
- **Bootstrap.** Pairs are resampled with replacement within each configuration, `BOOTSTRAP_RESAMPLES = 10_000`, numpy
  `default_rng(0)`, as in 006. A resampled pair carries all its keys. A decision that uses an interval (H3) uses the
  99% percentile interval (level 0.01, matching `SIGNIFICANCE`), or, for H3's claims that hold at some doubling, the
  interval at level 0.01/3 (Bonferroni over the three doublings, derived in H3); the 95% interval is also reported.
  The resample count sets only the Monte Carlo precision. With 8 pairs the percentile interval undercovers: for a mean difference whose true value equals a margin,
  the 99% interval lies entirely on the wrong side of the margin in 0.016-0.018 of designs, not 0.005 (planning
  simulation, 20,000 designs with equal sds and with 006's `r2.mean.B` and `r6.mean.B` sds; a 4,000-design rerun gave
  0.014-0.016). Decisions about a mean difference against a margin therefore use exact permutation tests (H4). H3's
  ratio decisions have no exact test, so their error rates at the class boundaries are simulated and stated in its
  power check.
- **Power numbers.** Unless stated otherwise they come from planning simulations (rows marked "review 2" from a second
  one, with its own seeds) with normal pair values, 006's 400 px sds (`f0`'s sd at f = 0, `f1400`'s at every jittered
  dose) and exact one-sided permutation p-values. A proportion estimated from n simulated designs has Monte Carlo sd at
  most 0.5/√n: 0.016 at 1,000 designs, 0.011 at 2,000, 0.008 at 4,000, 0.035 at 200. `power.py` reproduces them
  (PLAN.md), with the agreement criterion of Method, Analysis.
- **Seed-sd growth (sensitivity).** The seed sd changes with f. In 006, over the 18 T keys, the sd ratio across one
  doubling of f (800 px 1/2800 → 1/1400 and 200 px 1/1400 → 1/700: 36 ratios) has median 1.12 and quartiles 0.79 and
  1.41. `f700` and `f350` are one and two doublings above `f1400`, so giving them `f1400`'s sd may overstate the power.
  H1, H2, H3 and H4 therefore each have a sensitivity row (review 2) in which the sds of `f700` and `f350` are
  `f1400`'s times g and g², with g = 1.12 (median) and 1.41 (upper quartile); `f5600` and `f2800` keep `f1400`'s sd.
  For the 18 M keys the same 36 ratios have median 0.81 (quartiles 0.65 and 1.03), so the growth rows are pessimistic
  for H4.

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
  the step 0 → 1/2800 falls by 0.78 to 2.19 display bytes.
- The f_c model. m(f) = m₀ − b·log₂(1 + f/f_c), fitted exactly (three points, three parameters) to 006's three 800 px
  `r4.structure_std` points (f = 0, 1/2800, 1/1400 of the side), gives f_c = 1/14386 of the side (≈ 1/14000) and
  reproduces their slope ratio 0.335. On this grid it predicts step 0 at 2.0 times and step 1 at 0.86 times the mean of
  the two doubling steps of the table (2.03 and 0.86 at the fitted f_c; 2.00 and 0.86 at f_c = 1/14000). H3 uses the
  same model. `power.py` (`fc_fit`) prints these numbers.
- Readings:
  - (i) **monotone**: the amplitude falls at every step;
  - (ii) **saturation**: the knob stops acting above some f. H1 does not decide it: an unresolved step at P = 64 is a
    property of this design's seed noise, not of the knob. H3b decides it per doubling with the P-independent class
    ratios ρ̃_i (class *saturating at doubling i*), so a stop confined to one doubling is seen (H3 power check: a stop
    at 1/700 or at 1/1400 of the side is classed saturating in 1.000 of designs);
  - (iii) **reversal**: the amplitude rises again at some step, and the knob is not monotone.
- Observable: class A at the six doses, 30 cells (6 regions × 5 steps).
- Tests, two Holm families at 0.01, each with first threshold 0.01/30 = 3.33e-4 ≥ 7.77e-5 (powered):
  - fall family F1: per cell, the one-sided exact permutation test "f_{i+1} lower than f_i" (30 tests);
  - rise family R1: per cell, "f_{i+1} higher than f_i" (30 tests).
  - The families are separate because the verdicts they guard are disjoint. One family of 60 would lower the
    probability that all 30 falls are rejected at d = 4 from 0.999 to 0.758 (1,000 designs).
- Cell classes: *fall* (rejected in F1), *rise* (rejected in R1), *unresolved* (neither).
- Decision:
  - **supported** iff all 30 cells are falls;
  - **refuted (reversal)** iff some cell is a rise; the Conclusion names those cells with Δ (display bytes), d and p;
  - **inconclusive** otherwise. The Conclusion lists the unresolved cells with Δ, d and `p_less`, and refers the
    saturation reading to H3b.
- Power check (1,000 designs per row):
  - F1, all 30 cells at the same d (independent cells): probability that all 30 are rejected 0.000 at d = 2.0, 0.447 at
    2.5, 0.961 at 3.0, 0.999 at 3.5, 1.000 at 4.0.
  - F1 at the predicted vector: per region r, d_step0 = 2.0·d_r, d_step1 = 0.86·d_r and d_step2…4 = d_r, with d_r from
    the table (smallest 4.10, r5 step 1): 1.000. No R1 test was rejected in any design.
  - R1, one true rise of d among 29 null cells: detected with probability 0.338 at d = 2, 0.876 at 3, 0.954 at 3.5 and
    0.995 at 4. A reversal smaller than about 3.5 seed sd at one step (detection below 0.95) may therefore go
    undetected, and "no reversal" is written with that limit.
  - Seed-sd growth (review 2; `power.py` `sd_growth`, 200 designs per row): class A in display bytes, the f_c model's
    steps scaled per region as in the H3 power check. All 30 cells are falls with probability 1.000 at g = 1, 1.12 and
    1.41, and no R1 test was rejected (0.000).

### H2: the short-lag autocorrelation `slag.y` rises with f on the walls

- Derived from: 006. Wall `slag.y` rises with f at every measured dose pair: 400 px f 0 → 1/1400: r4 0.140 → 0.264,
  r5 0.167 → 0.278, r6 0.180 → 0.397 (d 7.9, 2.9, 12.9); 800 px f 0 → 1/2800 → 1/1400: r4 0.130 → 0.207 → 0.248, r5
  0.159 → 0.235 → 0.280, r6 0.190 → 0.323 → 0.380; 200 px f 1/1400 → 1/700: r4 0.251 → 0.336, r5 0.251 → 0.334, r6
  0.389 → 0.496. A wider footprint mixes neighbouring image-plane positions into each pixel, so the structure stays
  correlated over a longer distance: softer strokes. On the sphere (r2), the floor (r3) and the ceiling (r7) `slag.y`
  also rises from f = 0 to 1/1400 in 8 of the 9 (region, size) cells of 006 (d +0.76 to +2.68; r7 at 200 px:
  Δ −0.001, d −0.01). They stay out of W because the effect is small for this design, not for lack of a direction: at
  400 px the whole rise 0 → 1/1400 has d +0.84 (r2), +0.81 (r3) and +1.65 (r7). It spans three steps, so no single step
  is expected near d = 3, where one step test is rejected in R2 with probability about 0.98 (power check, r4 step 2).
  A rise is predicted there too and reported (estimation).
- Readings:
  - (i) **net softening**: wall `slag.y` is higher at 1/350 than at 0 of the side, with no resolved reversal step.
    Reversal steps smaller than about 3 seed sd may go undetected (power check), so this reading is "net softening
    from 0 to 1/350 with no reversal step larger than about 3 seed sd". "Softening at every step of the grid" is
    written only if every step on every wall is a resolved rise;
  - (ii) **non-monotone**: some step is a resolved reversal, and the knob description needs a range.
- Observable: class W at the six doses.
- Tests, two Holm families at 0.01:
  - rise family R2, 18 tests (first threshold 5.56e-4 ≥ 7.77e-5: powered):
    - (a) overall rise: `f350` vs `f0`, one-sided "higher", per wall (3 tests);
    - (s) step rise: each step, one-sided "f_{i+1} higher than f_i", per wall (15 tests);
  - reversal family V2, 18 tests (first threshold 5.56e-4 ≥ 7.77e-5: powered):
    - (h) net hardening: `f350` vs `f0`, one-sided "lower", per wall (3 tests);
    - (r) step reversal: each step, one-sided "f_{i+1} lower than f_i", per wall (15 tests).
- Step classes per wall: *rise* ((s) rejected in R2), *reversal* ((r) rejected in V2), *unresolved* (neither).
- Overall class per wall: *rise* ((a) rejected in R2), *hardening* ((h) rejected in V2), *unresolved* (neither).
- Decision:
  - **supported** iff all three (a) are rejected and nothing in V2 is rejected. The Conclusion adds "at every step" iff
    all 15 steps are rises, and otherwise lists the unresolved steps with Δ and d;
  - **refuted (reversal)** iff some (r) is rejected; the Conclusion names the steps with Δ, d and p;
  - **refuted (net hardening)** iff some (h) is rejected: that wall's `slag.y` is lower at 1/350 than at 0 of the side.
    Both refutations may apply;
  - **inconclusive** otherwise (some wall's overall change is unresolved in both directions). The Conclusion lists those
    walls with Δ and d of `f350` vs `f0`. An unresolved (a) is never read as "no net rise" (Common definitions,
    Resolved).
- Estimation: per step and wall Δ, d and both one-sided p-values; `slag.x` in every region and `slag.y` on r2, r3 and
  r7.
- Power check (2,000 designs; the six configurations are simulated, so adjacent steps share their middle
  configuration):
  - Predicted steps (dimensionless): the 800 px rise 0 → 1/2800 is split between steps 0 and 1 in the f_c model's
    proportion 0.70 : 0.30; step 2 is the 800 px rise 1/2800 → 1/1400; steps 3 and 4 are both set to the 200 px rise
    1/1400 → 1/700, because 006 has no point above 1/700.

    Two sd brackets for the new doses: the first gives them `f1400`'s sd (first draft's simulation); the second gives
    them `f0`'s sd, while `f1400` keeps its measured sd (review 2):

    | wall | Δ per step 0 … 4 | d per step, `f1400`'s sd | P(step is a rise in R2), `f1400`'s sd | d per step, `f0`'s sd | P(step is a rise in R2), `f0`'s sd |
    |---|---|---|---|---|---|
    | r4 | +0.054, +0.023, +0.041, +0.085, +0.085 | 3.4, 1.7, 3.1, 6.3, 6.3 | 0.995, 0.507, 0.982, 1.000, 1.000 | 3.0, 1.3, 2.6, 5.4, 4.8 | 0.988, 0.330, 0.952, 1.000, 1.000 |
    | r5 | +0.054, +0.023, +0.045, +0.084, +0.084 | 1.4, 0.4, 0.9, 1.6, 1.6 | 0.384, 0.015, 0.090, 0.441, 0.467 | 2.9, 1.2, 1.2, 2.2, 4.5 | 0.978, 0.296, 0.297, 0.844, 1.000 |
    | r6 | +0.093, +0.040, +0.057, +0.107, +0.107 | 5.5, 2.4, 3.5, 6.6, 6.6 | 1.000, 0.896, 0.999, 1.000, 1.000 | 5.3, 2.3, 3.4, 6.3, 6.1 | 1.000, 0.860, 0.998, 1.000, 1.000 |

    r5's d are small in the first bracket because its `f1400` sd, 0.0515, comes from one pair: per pair, `r5.slag.y`
    in `f1400` is 0.263, 0.271, 0.252, 0.278, 0.300, 0.391, 0.217 and 0.253 (sd 0.0259 without the sixth pair). `f0`'s
    sd is 0.0187, and r4 and r6 have 0.013-0.018 in both configurations. The second bracket uses `f0`'s sd, a measured
    quantity, rather than excluding a pair. (r4 steps 3-4 at 6.3 and r6 step 1 at 2.4 correct two roundings of the first
    draft: the values are 6.346 and 2.449, written there as 6.4 and 2.5.)
  - All three (a) rejected: 1.000 in both brackets. All 15 steps rises: 0.000 and 0.053. Any V2 rejection (reversal or
    net hardening): 0.000 in both. The expected outcome is therefore "supported" without "at every step". The steps
    least likely to be resolved are step 1 (P(rise) 0.015-0.896 in the first bracket, 0.296-0.860 in the second) and
    r5's step 2 (0.090 and 0.297).
  - Seed-sd growth (review 2; first bracket with the sds of `f700` and `f350` times g and g², 2,000 designs): all three
    (a) rejected 1.000 (g = 1.12) and 0.999 (g = 1.41); any V2 rejection 0.000; supported 1.000 and 0.999. The
    largest changes are in r5's steps 3 and 4: P(rise) 0.441 and 0.467 at g = 1, 0.384 and 0.296 at g = 1.12, 0.256 and
    0.108 at g = 1.41. Steps 3 and 4 of r4 and r6 stay at 1.000. Steps 0-2 keep their sds, and their P(rise) agree
    with the first bracket within 0.04 (Monte Carlo noise of independent runs).
  - V2 (18 tests), one true reversal step among 17 null tests: detected with probability 0.189 at d = 1.5, 0.472 at 2,
    0.918 at 3 and 0.984 at 3.5 (review 2; the first draft's 15-test V2 gave 0.202, 0.480, 0.925 and 0.984).

### H3: the response has diminishing returns (effect statistics)

The step ratios below are effect statistics with bootstrap intervals; no permutation p-value enters.

- Observable: class A means at the six doses.
- Statistics (review 2). The class step S_i = Σ_r Δ_i(r) over the six A regions, in display bytes. The ratios are
  q̃_0 = S_1/S_0 and, for the three doubling pairs, ρ̃_i = S_{i+1}/S_i, i = 1, 2, 3 (f from 1/5600 to 1/350). They are
  taken per doubling, not pooled, so a change confined to one doubling is seen.
  - A ratio is *estimable* iff its denominator step i is a fall in F1 (H1) in at least one A region. Otherwise it is
    reported as "denominator not resolved" (the onset of a possible stop) and enters no decision: a ratio of two
    unresolved steps is unbounded.
  - The sums run over all six regions, not only the resolved ones: selecting regions by their own denominator biases the
    ratio downward (a planning variant that did so called a truth linear from f = 0 diminishing in 0.075 of designs).
- Intervals. A claim about every doubling (*logarithmic*, *linear*, *accelerating*; H3a-d supported) is an
  intersection-union statement, so it uses the 99% interval of each ratio (`CI_DECISION`). A claim that holds at some
  doubling (*saturating at doubling i*; H3a-d refuted) is a union over the three doublings, so it uses each ratio's
  interval at two-sided level 0.01/3 (percentiles 0.1667 and 99.8333; Bonferroni over the three doublings,
  `CI_UNION`). Each sub-hypothesis (H3a-0, H3a-d, H3b) is decided on its own at nominal level 0.01. The percentile
  intervals undercover with 8 pairs (Common definitions, Bootstrap), so the simulated error rates at the class
  boundaries are stated in the power check.
- **H3a: diminishing returns in f.**
  - Derived from: 006's "the steps shrink as jitter grows". At 800 px the two equal halves of [0, 1/1400] give slope
    ratios (second half / first half) of 0.37, 0.34, 0.34, 0.44, 0.31 and 0.36 in r2-r7 (median 0.35).
  - Slopes: the slope of step i is Δ_i / w_i, with widths w_i = 1/5600, 1/5600, 1/2800, 1/1400, 1/700 of the side.
    Steps 0 and 1 have equal widths, so their slope ratio is q̃_0. A doubling's slope ratio is ρ̃_i/2. A slope ratio of 1
    is a response linear in f (a definition).
  - The first dose and the doublings are decided separately. Step 0 starts at f = 0 and carries the f_c model's large
    first step, so a median pooled over both mixes two quantities: under the first draft's pooled rule, a truth linear
    in f above 1/5600 has pooled slope ratio exactly 1, yet was called diminishing in about half of the simulated
    designs (0.49-0.56).
  - **H3a-0 (first dose):** supported iff q̃_0 is estimable and its 99% interval lies below 1. Refuted (accelerating)
    iff it lies above 1. Otherwise inconclusive.
  - **H3a-d (doublings):** supported iff every ρ̃_i is estimable and its 99% interval lies below 2. Refuted
    (accelerating at doubling i) iff some estimable ρ̃_i has its 0.01/3 interval above 2. Otherwise inconclusive.
  - Prediction (f_c model, `power.py` `fc_fit`): q̃_0 = 0.43; ρ̃_1, ρ̃_2, ρ̃_3 = 1.12, 1.07, 1.03 (doubling slope ratios
    0.56, 0.53, 0.52). Both supported.
- **H3b: the response per doubling is logarithmic in f (scale of the M7 control).**
  - Derived from: the per-doubling falls in H1's table. The 200 px fall (f 1/1400 → 1/700) divided by the 800 px fall
    (f 1/2800 → 1/1400) is 1.07, 1.17, 0.95, 0.79, 1.15 and 1.14 in r2-r7 (median 1.11): about a constant change per
    doubling, i.e. m(f) ≈ a + b·log₂ f. This crosses two sides, and 200 px departs slightly (006 H1), hence a test.
  - Statistic: ρ̃_1, ρ̃_2, ρ̃_3. For m = a + b·f^γ, ρ = 2^γ; γ_i = log₂ ρ̃_i is reported when ρ̃_i > 0. The pooled R
    (the median of the 18 per-region ratios Δ_{i+1}(r)/Δ_i(r), i = 1, 2, 3) and γ = log₂ R are reported as estimation
    only: they pool the three doublings and cannot see a stop confined to one of them.
  - Reference exponents (definitions): γ = −1 (each doubling changes the class half as much as the previous one, so
    the response converges: *saturating*), γ = 0 (equal change per doubling: *logarithmic*), γ = 1 (*linear* in f),
    γ = 2 (*accelerating*). The class boundaries are the midpoints γ = −1/2, 1/2 and 3/2, i.e. ρ = 2^−1/2 = 0.7071,
    2^1/2 = 1.4142 and 2^3/2 = 2.8284: midpoints between definitions, not tuned values.
  - Cell of one ratio by an interval [lo, hi]:
    - hi < 2^−1/2 → *saturating* (it includes ρ̃ < 0, a reversal);
    - 2^−1/2 < lo and hi < 2^1/2 → *logarithmic*;
    - 2^1/2 < lo and hi < 2^3/2 → *linear*;
    - lo > 2^3/2 → *accelerating*;
    - an interval that contains a boundary → *inconclusive*.
  - Class:
    - *saturating at doubling i* iff i is the first doubling whose ρ̃_i is estimable and has its 0.01/3 interval in
      the saturating cell: the step from f_{i+1} to f_{i+2} is less than 2^−1/2 of the step before it. This is H1's
      saturation reading. A stop at 1/700 of the side is saturating at doubling 3, a stop at 1/1400 at doubling 2;
    - otherwise *logarithmic*, *linear* or *accelerating* iff all three ρ̃_i are estimable and their 99% intervals lie
      in that same cell;
    - otherwise *inconclusive*. The Conclusion lists the three cells and the onset, if any.
  - Why the reference is a cell, not ρ = 1 exactly: the f_c model is logarithmic-type, yet on this grid it gives
    ρ_1, ρ_2, ρ_3 = 1.12, 1.07, 1.03 (pooled R = 1.07, γ = 0.09), and ρ reaches 1 only for f ≫ f_c. A rule "the
    interval contains 1" would reject the logarithmic reading of the model that predicts it (first draft: the pooled
    R's interval excluded 1 in 0.355 of designs under the f_c model).
  - Decision: **supported** iff *logarithmic*. **Refuted** iff *saturating at doubling i*, *linear* or *accelerating*,
    with the class named. Otherwise **inconclusive**.
- Power check:
  - Delta method (`power.py` `rho_delta_method`; per-region ratios ρ_i(r), estimation): the f_c model's steps scaled
    per region to the table's mean doubling fall, 006's 400 px sds as in Common definitions, and the covariance −sd²/8
    of two steps that share a configuration. The sd of one ρ_i(r) is 0.058-0.072 (r3) and 0.140-0.212 in the other
    regions.
  - Parametric bootstrap (`power.py` `h3_parametric_bootstrap`, review 2): normal pair values for 6
    configurations × 6 regions × 8 pairs, regions independent, pairs resampled within configurations (a resampled pair
    carries all its regions), 2,000 resamples. Each truth is a vector of five steps in the f_c model's log₂ units.
    Region r's steps are those times s_r = |mean of the region's two H1-table falls| / ((model step 2 + model step 3)/2),
    and the configuration means are their cumulative sums from a common origin. F1 runs on every design and gates
    estimability. 200 designs per truth (Monte Carlo sd ≤ 0.035); 1,000 for the four boundary truths (sd 0.003 at a
    rate of 0.01). Step 0 is the f_c model's in every truth except "linear from 0".

    | truth (designs) | true ρ̃_1, ρ̃_2, ρ̃_3 | true q̃_0 | median 99% half-width of ρ̃_1, ρ̃_2, ρ̃_3 | H3b class (fraction of designs) | H3a-0 supported | H3a-d supported / refuted |
    |---|---|---:|---|---|---:|---|
    | f_c model (200) | 1.12, 1.07, 1.03 | 0.43 | 0.173, 0.150, 0.135 | logarithmic 0.845, inconclusive 0.155 | 1.000 | 1.000 / 0.000 |
    | logarithmic, ρ = 1 (200) | 1, 1, 1 | 0.48 | 0.145, 0.146, 0.144 | logarithmic 0.970, inconclusive 0.030 | 1.000 | 1.000 / 0.000 |
    | saturating, ρ = 1/2 (200) | 0.5, 0.5, 0.5 | 0.96 | 0.056, 0.111, 0.220 | saturating at 1: 1.000 | 0.195 | 1.000 / 0.000 |
    | f_c model, ρ_3 = 1/2 (200) | 1.12, 1.07, 0.50 | 0.43 | 0.172, 0.148, 0.101 | saturating at 3: 0.915, inconclusive 0.085 | 1.000 | 1.000 / 0.000 |
    | stop at 1/700: step 4 = 0 (200) | 1.12, 1.07, 0 | 0.43 | 0.177, 0.151, 0.082 | saturating at 3: 1.000 | 1.000 | 1.000 / 0.000 |
    | stop at 1/1400: steps 3, 4 = 0 (200) | 1.12, 0, 0/0 | 0.43 | 0.172, 0.086, not estimable (1.000) | saturating at 2: 1.000 | 1.000 | 0.000 / 0.000 |
    | boundary: f_c model, ρ_3 = 2^−1/2 (1,000) | 1.12, 1.07, 0.71 | 0.43 | 0.170, 0.150, 0.117 | inconclusive 0.978, logarithmic 0.011, saturating at 3: 0.011 | 1.000 | 1.000 / 0.000 |
    | boundary: f_c model, ρ_3 = 2^1/2 (1,000) | 1.12, 1.07, 1.41 | 0.43 | 0.174, 0.150, 0.163 | inconclusive 0.989, logarithmic 0.011 | 1.000 | 0.999 / 0.000 |
    | boundary: kink then linear, ρ = 2 (1,000) | 2, 2, 2 | 0.24 | 0.460, 0.222, 0.111 | linear 0.729, inconclusive 0.271 | 1.000 | 0.000 / 0.030 |
    | boundary: linear from 0, q_0 = 1 (1,000) | 2, 2, 2 | 1.00 | 0.676, 0.323, 0.162 | linear 0.205, inconclusive 0.795 | 0.020 (refuted 0.017) | 0.000 / 0.031 |
    | seed-sd growth g = 1.12, f_c model (200) | 1.12, 1.07, 1.03 | 0.43 | 0.170, 0.155, 0.161 | logarithmic 0.865, inconclusive 0.135 | 1.000 | 1.000 / 0.000 |
    | seed-sd growth g = 1.41, f_c model (200) | 1.12, 1.07, 1.03 | 0.43 | 0.178, 0.168, 0.205 | logarithmic 0.690, inconclusive 0.310 | 1.000 | 1.000 / 0.000 |

  - Levels at the boundaries (a claim's truth exactly on its boundary): logarithmic 0.011 at ρ_3 = 2^−1/2 and at
    2^1/2; saturating at 3 0.011 at ρ_3 = 2^−1/2; H3a-0 supported 0.020 and refuted 0.017 at q_0 = 1; H3a-d refuted
    0.030 and 0.031 at ρ = 2 (Monte Carlo sd 0.003-0.005). They exceed the nominal 0.01 by up to a factor of 3. These
    are the error rates of the registered rules, stated rather than assumed.
  - Under a stop at 1/1400, H3a-d is inconclusive (ρ̃_3 not estimable), while H3b names the stop.
  - The pooled R (estimation) has median 1.074 under the f_c model and 0.080 under a stop at 1/1400.
  - The expected outcome is H3a-0 and H3a-d supported (1.000 in every row with the f_c model, including the sd-growth
    rows) and H3b logarithmic (0.845; 0.690-0.865 with sd growth). An inconclusive H3b under the f_c model comes from
    interval width, not from a wrong class: no f_c-model design was classed saturating, linear or accelerating.
- Estimation only:
  - q̃_0 and ρ̃_i for class W (sums over the three walls), each estimable iff its denominator step is an R2 rise on at
    least one wall;
  - per-region ratios for A and W. A ratio is reported only when its denominator step is resolved (A: a fall in F1;
    W: a rise in R2). The others are listed as "denominator not resolved", because a ratio of two small steps is
    unbounded.

### H4: region means do not depend on f, at the display quantum

- Derived from (review 2):
  - Geometry: the eroded masks keep only pixels at least 4 px from a region edge, while the largest footprint reaches
    8/7 px, so no footprint of a measured pixel leaves its region.
  - If jitter acted only by averaging a smooth radiance field over a small symmetric square, a region mean would be
    unchanged to first order. That premise is the pure-footprint reading, which 006 left open ("Jitter acts only by
    averaging over its footprint", Hypotheses for later work: jitter may also act through the chain), so it does not
    set the prediction.
  - 006's shifts: at 400 px, mean(f 1/1400) − mean(f 0) of the 18 keys is −0.130 to +0.239 display bytes
    (`r5.mean.R`, `r2.mean.B`; rel −0.0009 and +0.0017), with |d| ≤ 1.85 (`r3.mean.B`). One key shifts at every size:
    `r2.mean.B` (sphere, blue) by +0.870 at 200 px (d 2.42), +0.239 at 400 px (d 1.12) and +0.289 at 800 px (d 4.02).
  - Its dose response in 006 stops after the first dose: at 800 px +0.278 from f = 0 to 1/2800 (d 2.69), then +0.010
    to 1/1400 (d 0.12); at 200 px +0.870 from 0 to 1/1400 (d 2.42), then −0.120 to 1/700 (d −0.28).
  - The 400 px `f350` − `f0` shift of `r2.mean.B`, extrapolated from the 400 and 800 px shifts at 1/1400 under four
    dose laws: no growth after the first dose (the 006 dose points), 0.24-0.29 bytes; the class-A shape (÷ N_A(1/1400)
    = 0.648, E1), 0.37-0.45; linear in f (×4), 0.96-1.16; f² (×16), 3.8-4.6. The 006 dose points do not fit the last
    two: under them the 800 px shift would have grown by 100% or 300% from 1/2800 to 1/1400, while it grew by 4% (0.010
    of 0.278).
  - Prediction: every key sub-quantum (supported). The `r2.mean.B` steps (Δ_i and d_i, Estimation) tell the dose laws
    apart and are reported first.
- Readings:
  - (i) **tone-invariant**: every region mean moves by less than one display byte, the display quantum;
  - (ii) **tone-shifting**: some region mean moves by at least one display byte, and the knob description must state
    it.
  - A Holm rejection alone does not separate them. With 8 vs 8 pairs a rejection needs only a consistent shift. With
    006's pooled sds of 0.021 (`r6.mean.B`) to 0.213 (`r2.mean.B`) display bytes, |d| = 4 is a shift of only 0.084 to
    0.85 bytes (lessons b, c).
- Observable: the 18 keys of M, `f350` vs `f0`, in display bytes.
- Margin: one display byte (Common definitions).
- Tests (exact permutation tests, `ensemble.permutation_pvalue`, on the per-pair values; `f350 − 1` subtracts the margin
  from every pair value of `f350`):
  - equivalence, per key (two one-sided tests, TOST): p_lo = `permutation_pvalue(f350 − 1, f0, "less")`, the shift is
    below +1, and p_hi = `permutation_pvalue(f350 + 1, f0, "greater")`, the shift is above −1. Each at 0.01, with no
    correction (Levels);
  - margin family S, per key: `permutation_pvalue(f350 − 1, f0, "greater")`, the shift exceeds +1, and
    `permutation_pvalue(f350 + 1, f0, "less")`, it is below −1. Holm at 0.01 over the 36 tests (first threshold
    2.78e-4 ≥ 7.77e-5: powered);
  - detection: the two-sided test per key at shift 0, Holm at 0.01 over the 18 keys (`report.family_test`; first
    threshold 5.56e-4 ≥ 1.55e-4: powered). It only labels sub-quantum keys;
  - size (reported, not a decision): per key, the 99% and 95% bootstrap intervals I_k of mean(`f350`) − mean(`f0`), in
    display bytes.
- Key classes:
  - *sub-quantum* iff p_lo ≤ 0.01 and p_hi ≤ 0.01. It is *detected* if the detection family rejects the key, *not
    detected* otherwise;
  - *supra-quantum* iff S rejects one of the key's two margin tests;
  - *unresolved* otherwise. No key is both sub- and supra-quantum: for one shifted comparison p_less + p_greater ≥ 1,
    so p_lo ≤ 0.01 excludes a rejection of "the shift exceeds +1" at a threshold ≤ 0.01, and likewise at −1.
- Decision:
  - **supported (tone-invariant)** iff every key is sub-quantum. The Conclusion lists the detected sub-quantum keys
    with abs diff (display bytes), I_k and d;
  - **refuted (tone-shifting)** iff some key is supra-quantum. The Conclusion gives each such key's abs diff, I_k, d
    and p;
  - **inconclusive** otherwise, listing the unresolved keys with abs diff, I_k, d, p_lo and p_hi.
- Levels: "every key sub-quantum" is an intersection-union statement over the 36 equivalence tests, so it has level at
  most 0.01 with no correction. Each test is exact under a location shift. One test rejects at a true shift of exactly
  +1 in 0.0092-0.0094 of designs (equal sds, `r2.mean.B` sds and `r6.mean.B` sds; 10,000 designs, Monte Carlo sd
  0.001; review 2). "Some key supra-quantum" is a union, controlled by Holm over S at 0.01. (The first draft decided
  both classes with I_k. Its error rate at the margin is 0.014-0.018, not 0.005 (Common definitions, Bootstrap), and a
  Holm rejection at shift 0 says nothing about the margin, so I_k is now only reported.)
- Power check (`power.py` `h4_margin`; 006's 400 px sds, `f1400`'s standing in for `f350`; 1,000 designs per row unless
  stated; review 2):
  - No true shift: all 18 keys sub-quantum in 1.000 of designs, and no key supra-quantum (0.000).
  - A key with a true shift of 1 − (z_0.99 + z_0.95)·se (0.58 bytes for `r2.mean.B`, 0.74-0.96 for the others; se the
    standard error of the difference) is sub-quantum with probability 0.871-0.902; normal theory gives 0.95.
  - Supra-quantum: one key with (|shift| − 1)/s_p = 3, 3.5, 4, 4.5 and 5 is rejected at S's first threshold with
    probability 0.816, 0.935, 0.985, 0.998 and 1.000 (4,000 designs). At 4, the shift is 1.85 bytes for `r2.mean.B`
    (s_p 0.213) and 1.09 for `r6.mean.B` (s_p 0.0215).
  - The four dose laws of Derived from, applied to all 18 keys (006's f 1/1400 shifts at 400 or 800 px times the law's
    factor):

    | law | `r2.mean.B` shift (400 / 800 px basis) | supported | refuted | inconclusive |
    |---|---|---|---|---|
    | class-A shape (÷ 0.648) | 0.37 / 0.45 | 0.999 / 0.986 | 0.000 / 0.000 | 0.001 / 0.014 |
    | linear in f (×4) | 0.96 / 1.15 | 0.035 / 0.000 | 0.000 / 0.010 | 0.965 / 0.990 |
    | f² (×16) | 3.83 / 4.62 | 0.000 / 0.000 | 1.000 / 1.000 | 0.000 / 0.000 |

    No growth after the first dose gives smaller shifts than the class-A row.
  - Seed-sd growth (`power.py` `sd_growth`; `f350`'s sd = `f1400`'s × g²): with no shift, all 18 keys sub-quantum in 1.000
    (g = 1.12) and 0.999 (g = 1.41), no key supra-quantum (0.000). Under the class-A dose law, supported 0.996 / 0.966
    (g = 1.12, 400 / 800 px basis) and 0.921 / 0.810 (g = 1.41), never refuted (0.000).
  - The reported 99% half-width of I_k is 0.024 (`r6.mean.B`) to 0.245 (`r2.mean.B`) bytes (first draft's simulation,
    2,000 resamples).
- Estimation: effect summaries of every step on M, `r2.mean.B` first (it separates the dose laws in Derived from), and
  of each dose against the SPEC default `f1400`.

### E1: the knob's response for M7 (estimation; the registered output uses means only)

- Derived from: T7.1 needs soft limits, a scale and a default position for each knob, and T7.2 needs preset inputs.
  A limit defined by "a step smaller than one seed sd" is not a property of the knob. It moves with P and the ensemble
  size (the lower limit goes to 0 as P grows), and at P = 64 it is not expected inside this grid (Expectation below).
  The registered output therefore uses means only, of keys whose target does not depend on P (Common definitions).
- Gate family G: `f350` vs `f0` on T, two-sided exact permutation tests, Holm at 0.01 over the 18 keys
  (`report.family_test`; first threshold 5.56e-4 ≥ 1.55e-4). A key is *responding* iff G rejects it. G decides only
  which keys enter N.
- **Registered input for M7:**
  - normalized response: for a responding key k, n_k(f) = (mean_k(f) − mean_k(f0)) / (mean_k(f350) − mean_k(f0)), 0
    at f = 0 and 1 at f = 1/350. N_C(f_k) is the median of n_k over the responding keys of class C, for C = A, W and
    T. Each table lists the keys used. A non-responding key is listed as "no resolved response" and does not enter;
  - per-step change: Δ_i(k), i = 0 … 4, of every A key in display bytes and of every W key (dimensionless), and the
    class medians Δ̃_i(A) and Δ̃_i(W). Steps 1-4 are doublings of f;
  - intervals: 95% and 99% bootstrap intervals of every N_C(f_k), Δ_i(k) and Δ̃_i(C);
  - scale: H3b's class. *logarithmic* → a control linear in log₂(1 + f/f̂_c), with f̂_c below: it puts f = 0 at 0 and
    is linear in log₂ f for f ≫ f̂_c, while a control linear in log₂ f cannot reach f = 0, which holds about a third of
    the response (N_A(1/5600) = 0.34 expected); *linear* → linear in f; any other class, or f̂_c undefined → the
    measured N_A table at the six doses, piecewise linear in log₂ f between the jittered grid points;
  - f_c estimate (review 2): f̂_c = (1/5600)/x, with x solving log((1 + 2x)/(1 + x)) / log(1 + x) = q̃_0 (H3a-0), the
    slope ratio of steps 0 and 1 under m = m₀ − b·log₂(1 + f/f_c), x = (1/5600)/f_c. The left side falls from 1
    (x → 0) to 0 (x → ∞), so x exists iff 0 < q̃_0 < 1; otherwise f̂_c is undefined and reported as such (q̃_0 ≥ 1: no
    curvature at the first dose; q̃_0 ≤ 0: a reversal), and also when q̃_0 is not estimable (H3). Its 95% and 99%
    intervals are the images of q̃_0's intervals, because the map is monotone in q̃_0 (a larger q̃_0 gives a smaller x,
    so a larger f̂_c); an interval end at or above 1 maps to f̂_c = ∞ and one at or below 0 to f̂_c = 0, reported as
    such. Per A region, f̂_c(r) comes from Δ_1(r)/Δ_0(r) and is reported only when step 0 is an F1 fall there;
  - default position: N_A(1/1400), where the SPEC default sits on the measured response.
  - T7.1 chooses the soft limits from these tables, and T7.2 chooses presets from them. This experiment sets neither.
- **Estimation labelled "doses resolvable at P = 64 with 8 pairs"** (properties of this design, not knob limits), for
  C = A and W:
  - D_i(C) = median over C of |d_i|, the size of step i in seed-to-seed sds;
  - D0_k(C) = median over C of |d| of `f_k` vs `f0`, k = 1 … 5;
  - S_C(f_k) = Σ_{i<k} D_i(C);
  - f_hi(C): the smallest f_k, k = 0 … 4, with D_i(C) < 1 for every i ≥ k, or "at or above 1/350" if D_4(C) ≥ 1;
  - f_lo(C): the largest f_k, k = 1 … 5, with D0_j(C) < 1 for every j ≤ k, or "below 1/5600" if D0_1(C) ≥ 1;
  - bootstrap fractions of each grid value of f_hi and f_lo. A resample whose pooled sd is 0 for a key makes d
    undefined; it is dropped from these statistics and counted.
- Range of this measurement: the grid ends at 1/350 of the side. One more doubling (1/175, 16/7 px at 400 px) would
  still keep every footprint inside its region, because the nearest pixel of another region is at Chebyshev distance
  at least 5 from a measured pixel (`metrics.erode`, radius 4), so the region edge is at least 4.5 px away. At 1/87.5
  (32/7 = 4.57 px) a footprint can cross it, and H4's premise fails. A measured upper limit of the knob therefore needs
  a mask design with an erosion larger than f·side. That is out of scope here.
- Expectation, from 006's numbers: under the f_c model N_A = 0.34, 0.49, 0.65, 0.82 and 1 at 1/5600 … 1/350, so the
  SPEC default sits at about 0.65 of the response to 1/350. Δ̃_i(A) per doubling is about −0.3 to −0.8 display bytes
  (H1 table). D(A) per doubling is about 5-9, so f_hi(A) = "at or above 1/350" and f_lo(A) = "below 1/5600" are
  expected. f̂_c ≈ 1/14,000 of the side: under the f_c model the planning median of 1/f̂_c is 14,245 (true 14,386),
  with median 99% interval [10,202, 20,469] (review 2, H3 power check).

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
  as 006 does, so `f0` and `f1400` have exactly 006's option sets and seeds, and their 32 renders are cached. This was
  checked while this README was written: `experiment.job_key` of each of the 32 jobs, with the registered oracle, has
  a `done` marker, and none of the 64 new jobs has one.
- New renders: 64 (16 per new configuration). Estimated oracle time from the cache's `wall_seconds` for row-chain
  400 px renders: 23.97 s at f = 0 and 25.36 s at f = 1/1400 (means of 16), so about 1,600 s of CPU. `run_jobs` runs
  one single-threaded render per core, so this is about 7 minutes on this container's 4 cores: one `--budget 540` call
  in expectation.
- Disk: one cached 400 px render takes 6,262,784 B of disk blocks (`du`; files 6,240,893 B: `sum.npy` 3,840,128,
  `k_consumed.npy` 1,280,128, `object_id.npy` 640,128, `image.ppm` 480,015, `meta.json` and `done` 494). The 64 new
  renders therefore need 400,818,176 B (0.40 GB) on the filesystem of `.cache`. Free space is recorded only as a dated
  measurement: on 2026-10-15 at 18:04 UTC, `df -B1 .cache` showed 4,060,082,176 B available on that filesystem, which
  009's renders share. The orchestrator frees disk before rendering, and the preflight compares the free space at that
  time with the requirement (Commands).
- Sample size: 8 pairs and P = 64, as in 006. The power checks show that this suffices for every decision: H1's F1
  (joint power 1.000 at the predicted d), H2's (a) (1.000), H3a-0 and H3a-d (1.000 under the f_c model), H3b
  (logarithmic in 0.845 of designs under the f_c model, 0.970 at ρ = 1) and H4 (1.000 at no shift). Deciding H3b per
  doubling costs power against the first draft's pooled ratio (1.00), which could not see a stop confined to one
  doubling; an f_c-model design that is not classed logarithmic is inconclusive, never misclassed. With the seed sd
  grown by 1.12 or 1.41 per doubling above 1/1400 (Common definitions), these become 1.000 (H1 F1), 1.000-0.999 (H2
  (a)), 1.000 (H3a-0, H3a-d), 0.865-0.690 (H3b) and 1.000-0.999 (H4 at no shift; 0.996-0.810 under the class-A dose
  law). Two statements are not expected to be reachable, and neither is a decision: H2's "at every step" (probability
  0.000-0.053, H2 power check) and equivalence within one seed sd (Common definitions). Doubling the ensemble to 16
  pairs would cost 96 more renders (64 at the new doses, 32 at the reused ones, on new blocks), about 2,400 CPU-s. It
  would reach neither: step 1 has predicted d 0.4-2.4, and the 99% half-width of d shrinks only by about √2, to about
  1.1.

### Commands

The directory is `experiments/008-2026-10-15-jitter-dose-response/`. Its date is that of the Opus commit that creates it
with this pre-registration (README.md and jobs.py): `$(date +%F)` on that day, 2026-10-15 or later and not earlier
than 007's date (experiments are numbered and dated in the order they run: 007, 008, 009). The commands below name
that directory.

The preflight runs first and stops unless the oracle binary has the registered sha256, all 32 reused renders are in
the cache, and the filesystem of the cache has at least the bytes the 64 new renders need (Configurations, Disk).
Without it, a different binary would re-render the reused configurations. `make oracle` is never run: the binary in
`.cache/oracle-build` keys the render cache, and its source has changed since it was built (Background).

```
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/008-2026-10-15-jitter-dose-response/analyze.py --preflight
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python -m painterly_analysis.experiment run experiments/008-2026-10-15-jitter-dose-response/jobs.py --budget 540   # repeat until exit 0
PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/008-2026-10-15-jitter-dose-response/analyze.py
.venv/bin/python experiments/008-2026-10-15-jitter-dose-response/power.py
```

Smoke run (code check only): `analyze.py --pairs 2 --scale 4 --out-dir <scratch>/008-smoke/out` with
`PAINTERLY_CACHE=<scratch>/008-smoke/cache`. It renders its own 100 px jobs. Every dose is kept, because f is a
fraction of the side. As in 006, a lag or erosion that is not an integer number of pixels is rounded to the nearest
integer ≥ 1 and the rounding is printed (at 100 px, τ = 0.5 → 1 px). Every printed line starts with
`SMOKE (code check only): `, `results.json` holds `"smoke": true`, and the committed outputs are never written. With
2 pairs every test family is underpowered, so every decision reads `inconclusive (underpowered)`.

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
- **Power numbers.** The numbers in the power checks come from planning simulations in numpy: the first draft's
  (`default_rng(0)`) and, for the review-2 rows, a second one (`default_rng(0)`, `(1)`, `(2)`, `(3)` and `(4)` for
  H2, H3, H4, the H4 margin-test power and the seed-sd growth rows). `power.py` reproduces them in JAX (`jax.random.PRNGKey(0)`) and
  prints them next to the README values. Deterministic numbers (f_c fit, step ratios, q, ρ, delta-method sds,
  normal-theory shifts) agree to the printed digits. A simulated number is an independent second estimate, so agreement
  is a two-sample criterion, Bonferroni at 0.01 over the m simulated rows compared (`power.py` counts m and prints
  z = z_{1−0.01/(2m)}):
  - a proportion agrees iff |p_a − p_b| ≤ z·√(p̄(1 − p̄)(1/n_a + 1/n_b)), with p̄ the pooled proportion and n_a, n_b the
    two design counts;
  - a median or half-width agrees iff the difference is at most z·√2·sd, with sd the bootstrap-over-designs sd of
    `power.py`'s own estimate.
  - A row outside its bound is reported in the card. The README numbers are not changed by it.
- **Outputs.**
  - `results.json`: configurations (f, j, options, seeds), the oracle sha256, parameters and regions, replicate
    counts, `summary`, every step's effect summary on T and the estimation-only keys, the H1-H4 records (families,
    p-values, Holm decisions, Δ, d, intervals, classes and decisions), H3's statistics with intervals, E1's gate family,
    tables and bootstrap distributions, the M7 input fields, and the figure encodings.
  - `fig_dose_response.png`: mean ± sd over pairs against dose. Left panel: class A, one series per region. Right panel:
    class W. The doses 1/5600 … 1/350 sit at equal spacing (log₂ f), and f = 0 sits 1.5 spacings left of 1/5600, joined
    by a dashed line, because it is off the log axis. No text is drawn; the encoding is recorded in `results.json`.
  - `fig_crops.png`: pair 0's `ab8` at native resolution, no resampling, 2 rows × 6 columns (doses in order). Row 1 is
    the window rows [0.30, 0.54) × columns [0.60, 0.84) of the side (back wall and its edge with the right wall). Row 2
    is rows [0, 0.24) × columns [0.76, 1.0) (the diagonal ceiling/right-wall edge). The edges are shown, not measured.
  - Each figure is at most 1 MB; the analysis fails otherwise.

### Pre-registration review

- Second review round (2026-10-10): applied 23, rejected 0. The 23 are the 15 skeptic findings, the 4
  cross-experiment checks and the 4 final-recheck issues that touch this experiment (R4, R5, R7, R8; R4, R5 and R7
  repeat (9), (14) and (X1)). The edits were made on 2026-10-15, before any render of this experiment; the review-2
  numbers come from planning simulations run on 2026-10-10 (H2, H4; rerun byte for byte on 2026-10-15) and 2026-10-15
  (H3, H4 margin-test power, seed-sd growth).
  - Skeptic findings:
    - (1) H3b decided saturation through the pooled R, which cannot see a stop confined to one doubling. Now per
      doubling with class-sum ratios ρ̃_i, estimable iff the denominator step is an F1 fall in at least one region;
      the union claim *saturating at doubling i* uses Bonferroni 0.01/3 intervals, the other classes 99% intervals.
      Stop truths at 1/700 and 1/1400 added to the power table (saturating 1.000 at doublings 3 and 2). Modified from
      the proposed fix: Bonferroni for the union claim instead of a plain 99% interval per doubling, and sums over all
      six regions instead of the resolved ones (selection bias, H3 Statistics).
    - (2) H3a's pooled Q mixed the first dose with the doublings and was biased at Q = 1. Split into H3a-0 (q̃_0) and
      H3a-d (ρ̃_i against 2), with four boundary truths and their simulated error rates (0.011-0.031). Modified from
      the proposed fix: H3a-d uses the per-doubling ρ̃_i, not "I_R below 2", because R pools the three doublings.
    - (3) H4's derivation assumed pure footprint averaging. It now cites 006's `r2.mean.B` shifts at all three sizes
      and their dose points, and gives the `f350` shift under four dose laws with power rows.
    - (4) H2 declared a refutation from a non-rejection. V2 gains the three net-hardening tests (18 tests), and H2
      gains an inconclusive outcome.
    - (5) H4's bootstrap-interval level was 0.014-0.018, not 0.01. Sub-quantum is now a TOST with exact permutation
      tests (level 0.0092-0.0094 at the margin). Extended: supra-quantum is now a Holm family of 36 one-sided margin
      tests, because a Holm rejection at shift 0 says nothing about the margin.
    - (6) E1 mapped *logarithmic* to a control linear in log₂ f, which cannot reach f = 0. Now f̂_c is estimated from
      q̃_0 and the control is linear in log₂(1 + f/f̂_c).
    - (7) r5's `f1400` sd comes from one pair. The H2 power table gains a second bracket with `f0`'s sd at the new
      doses; two roundings were corrected.
    - (8) The reason for keeping r2, r3 and r7 out of W was wrong: their `slag.y` rises in 8 of 9 cells of 006. They
      stay out for lack of power, and a rise is predicted there.
    - (9, 15) The block note for 009 now reads blocks 46-67 (seeds 736-1087).
    - (10) The rule for comparing `power.py` with these numbers is now a two-sample criterion, Bonferroni over the rows
      compared, in place of one Monte Carlo sd.
    - (11) PLAN: every family records `powered`, decisions have an `inconclusive (underpowered)` branch, and
      `rejected_keys` None counts as no rejection.
    - (12) PLAN: `test_analyze.py` loads `analyze.py` with `report.load_jobs_module`; `analyze.py` has no import-time
      side effects and does not combine `from __future__ import annotations` with dataclasses.
    - (13) PLAN: `h3_parametric_bootstrap` states the per-region scaling, and `fc_fit` its bisection bracket.
    - (14) PLAN and Commands: Opus commits README.md and jobs.py in the experiment directory before the card runs, as
      for 006. Changed per Opus's date rule: the directory and the commands carry the date of that commit, not
      2026-10-09.
  - Cross-experiment checks: (X1) the figure uses `report.paint` and `report.draw_line` (added by 007's card),
    falling back to 006's functions; (X2) the spectral band is worded "frequency band 2 to 50 cycles per image";
    (X3) the smoke run uses `<scratch>/008-smoke/cache` and `<scratch>/008-smoke/out`; (X4) the PLAN gives the index
    row's text, with the directory's date.
  - Final recheck: (R5) dates, as in (14); (R8) seed-sd growth: sensitivity rows with the sds of `f700` and `f350`
    grown by 1.12 and 1.41 per doubling above 1/1400 in H1, H2, H3 and H4, and the sample-size claim stated over that
    range.
  - Opus rules for this pass: dated directory placeholder (as in (14)); the disk requirement stated in bytes and the
    free space recorded as a dated measurement (Configurations, Disk; the preflight checks it); every interval that
    enters a decision is 99%, except H3's union intervals at 0.01/3, derived above; `make oracle` is never run
    (Commands).

## Results

Pending: the analysis card fills this in.

## Conclusion

Pending: written after the analysis (DRAFT by the card, final by a strong model).
