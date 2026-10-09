# Experiment 003: how long must a chain be? (Choosing the artist-mode lane length)

## Background

- `docs/plan.md`, "What makes the look", item 3 (scan-line chaining): each path's counter K starts where the previous
  pixel's path in the same row ended. This gives a converged texture. The research port reports pattern correlation
  with the reference of 0.63 for the row chain, 0.55 for 16-pixel lanes, and 0.11 for a per-path random start, which
  "breaks the look".
- `docs/spec.md` §3 defines the chains this experiment compares:
  - `row`: one chain per (row, pass), with K0 = rng_u32(seed, PURPOSE_LANE_K0, 0, row, 0, pass) mod 2^22;
  - `lane:L` (artist mode, knob `lane_length`, default 16): each row is split into lanes of L consecutive pixels. There
    is one chain per (lane, pass), with its own hashed K0. The last lane in a row may be shorter.
  - The oracle's `run_chain` (`src/app/smallpaint_oracle.cpp`) clamps L to the image width. With L at least the width,
    `lane:L` runs the same chain as `row`: the same K0 and the same pixel order. At 400 px, `lane:128` is therefore a
    different chain from `row`.
- `experiments/001-2026-10-08-oracle-reproduction/`, H2: restarting K at 0 for each pass (`omp4_64`) lowers
  `all.pattern_corr` significantly against `img64` (0.5809 vs 0.5889, p = 1.55e-4). Its `img64` is `chain=image`,
  P = 64, block 0 (seeds 0-15). Its `all.pattern_corr` is 0.588908 (sd 0.001582). Its `pm64` gives 0.2947. This
  experiment's positive control `image` is that ensemble: the same option set, so the same 16 renders from the cache.
- `experiments/002-2026-10-08-ingredient-ablation/` takes seed blocks 10-18. This experiment reuses block 17 (`lane_1`) and
  block 0 (`image`), takes new blocks 20-27, and leaves block 19 unused.
- Pilot values from the T1.8 card. They are not evidence: row against image gives 0.588 vs 0.589 pattern correlation;
  `r4.lag1.x` is 0.156 at L = 16 against 0.204 for row. The plan's 0.63 for the row chain is a research-port number
  and is not directly comparable with 001's 0.589 from the compiled oracle. The tests below use only the compiled oracle.

## Hypothesis

### Common definitions

- A configuration is an ensemble of 8 pairs. A pair is two independent half renders (seeds 2k and 2k+1 of one
  configuration), each with P = 64 passes at 400 px, `scene=gui` and `ghost=all` (the oracle defaults).
- Metrics are those of `metrics.measure`, over the diffuse regions only (as in experiment 002, D5). The key family is
  `metrics.diffuse_key_family(keys)`, which has 46 keys. Every `compare_ensembles` call uses it, never all keys.
- Curve keys, for H2: `all.pattern_corr`, `r4.structure_std`, `r4.lag1.x` and `r4.lag1.y`. Region 4 is the back plane
  (SPEC §9).
- The significance level is alpha = 0.01 (written `SIGNIFICANCE` in the code). It is not the oracle option `alpha`.
  Every p-value is an exact permutation p-value (`ensemble.permutation_pvalue`). Where several tests share a decision,
  Holm (`ensemble.holm`) is applied at alpha = 0.01 across those tests.
- Power, for 8 vs 8 pairs: the smallest attainable p-value is 1 / C(16, 8) = 7.77e-5 one-sided, and 2 / C(16, 8) =
  1.55e-4 two-sided. A test family is powered only if that minimum is at most alpha divided by the number of tests. The
  families are: H1, 7 steps, threshold 1.43e-3 (powered); H2, 8 lane lengths, threshold 1.25e-3 (powered); H3, 46 keys,
  threshold 2.17e-4 (powered, since 1.55e-4 is at most 2.17e-4). An underpowered comparison is reported as
  `inconclusive`, never as `supported` or `refuted`.
- Estimation over verdicts: for every comparison, `ensemble.effect_summary` is reported (mean +- sd, relative
  difference, Cohen's d). A verdict of "indistinguishable" is always reported together with `min_attainable_p` and the
  largest observed |relative difference| and the largest |Cohen's d|.

### H1: the pattern correlation does not fall as the lane gets longer

- Derived from: plan item 3 (the look needs a continuous scan-line chain, so chains that restart more often should lose
  pattern correlation), and SPEC §3 (`lane:L` restarts K every L pixels). This predicts that `all.pattern_corr` is
  non-decreasing in L.
- Observable: `all.pattern_corr` of each `lane_L`, for L in {1, 2, 4, 8, 16, 32, 64, 128}.
- Test: for each adjacent step (shorter L, longer L), two one-sided permutation tests on `all.pattern_corr`:
  `p_less = permutation_pvalue(longer, shorter, "less")` and `p_greater = permutation_pvalue(longer, shorter, "greater")`.
  Holm over the 7 steps is applied to the `p_less` values, and separately to the `p_greater` values, at alpha = 0.01.
- Decision: refuted iff any step is Holm-rejected in the `less` direction (a significant decrease). Supported iff no
  step is Holm-rejected in the `less` direction and every step is powered. Otherwise inconclusive. The steps that are
  Holm-rejected in the `greater` direction (significant increases) are listed. They do not change the verdict.

### H2: a finite lane length matches row (L*)

- Derived from: the deliverable. The default lane length must be the shortest chain that keeps the look of the row
  chain. The pilot anisotropy (`r4.lag1.x` 0.156 at L = 16 against 0.204 for row) suggests that anisotropy depends on L.
- Definition: L* is the smallest L in {1, 2, 4, 8, 16, 32, 64, 128} such that `lane_L` is not Holm-rejected in the
  `less` direction against row on `all.pattern_corr`. The eight tests are `permutation_pvalue(lane_L, row, "less")`, with
  Holm across all eight at alpha = 0.01.
- Curve: the full curve is reported for the four curve keys. For each configuration this is the mean +- sd, the relative
  difference against row, and Cohen's d against row. The card gives no test for the anisotropy claim, so
  `r4.lag1.x` and `r4.lag1.y` are reported as effect sizes only, with no verdict.
- Decision: supported iff L* exists and all eight tests are powered. Refuted iff all eight tests are powered and every
  lane length is Holm-rejected (no lane length in the design is shown to match row). Otherwise inconclusive.

### H3: restarting each pass at a hashed K0 does not change the texture

- Derived from: SPEC §3 (`row` restarts each pass at a hashed K0, unlike 001's `omp4_64`, which restarts at 0), and
  the card's research finding that the start-index distribution reaches stationarity within about one pixel. So the
  hashed restart should match the continuous chain. The pilot gives 0.588 vs 0.589.
- Claim: `row` is indistinguishable from `image` on the diffuse family.
- Test: `ensemble.compare_ensembles(row, image, diffuse_key_family(keys), alpha = 0.01)`. This is a two-sided permutation
  test on each key, with Holm over 46 keys. The effect summary of the family is reported with `min_attainable_p`, the
  largest |relative difference| and the largest |Cohen's d|.
- Decision: supported iff the comparison is powered and no key is rejected ("indistinguishable"). Refuted iff any key is
  rejected. Inconclusive if underpowered.

## Method

### Amendments before rendering (Opus, cb52945)

- `lane_1` has exactly the option set of experiment 002's `per_path_start`, so it reuses that experiment's block 17
  (seeds 272-287). Its 16 renders come from the cache.
- Block 19 is unused.
- There are 128 new renders: 8 configurations x 16 seeds (`lane_2` to `lane_128`, and `row`). Reused: 32 (`image`
  from experiment 001's block 0, and `lane_1` from experiment 002's block 17).
- D1 is superseded by this amendment: the new blocks are 20-27, and block 19 is unused.

### Configurations

All configurations use `size=400`, `passes=64` and 8 pairs. No configuration passes `scene` or `ghost`, because the
oracle defaults are `scene=gui` and `ghost=all`. Passing them would change the cache key. The `image` option set is
exactly that of experiment 001's `img64`, so its 16 renders come from the cache.

| name | oracle options (besides size 400, passes 64) | seed block | seeds | renders |
|---|---|---|---|---|
| image | `chain=image` | 0 (001's img64) | 0-15 | 16, reused |
| lane_1 | `chain=lane:1` | 17 (002's per_path_start) | 272-287 | 16, reused |
| lane_2 | `chain=lane:2` | 20 | 320-335 | 16 new |
| lane_4 | `chain=lane:4` | 21 | 336-351 | 16 new |
| lane_8 | `chain=lane:8` | 22 | 352-367 | 16 new |
| lane_16 | `chain=lane:16` | 23 | 368-383 | 16 new |
| lane_32 | `chain=lane:32` | 24 | 384-399 | 16 new |
| lane_64 | `chain=lane:64` | 25 | 400-415 | 16 new |
| lane_128 | `chain=lane:128` | 26 | 416-431 | 16 new |
| row | `chain=row` | 27 | 432-447 | 16 new |

The base seed of each configuration is 16 times its block. Block 0 is shared with experiment 001. The other
configurations take blocks 20-27, the first free blocks after experiment 002's block 18, and block 19 is unused.
`lane_1` has the option set of experiment 002's `per_path_start`, so it reuses that block 17 (seeds 272-287). New
renders: 128 (8 configurations x 16). Reused: 32 (`image` from block 0, `lane_1` from block 17).

### Commands

1. Render until the harness exits 0 (exit code 3 means jobs remain):
   `.venv/bin/python -m painterly_analysis.experiment run experiments/003-2026-10-08-lane-length/jobs.py --budget 540`
2. Analysis, once all renders exist:
   `.venv/bin/python experiments/003-2026-10-08-lane-length/analyze.py`
   It writes `results.json` and `fig_grid.png` next to this file and prints the tables. It re-runs from the cache and is
   deterministic. The options `--jobs`, `--reference` and `--out-dir` exist only to validate the script on a smaller
   subset. They are not part of the experiment.

### Analysis

- Metrics: `experiment.measure_ensemble` for each configuration. It calls `metrics.measure` on each pair against the
  400 px GUI reference `tests/data/reference/smallpaint_painterly.ppm`, using the diffuse-only object-id map. The
  object-id map of the first render of each configuration is asserted to be identical across configurations.
- Tests, decision rules and effect sizes are as in Hypothesis, on the keys named there.
- Chains per pass at 1920 x 1080 (the deliverable's resolution), from SPEC §3. `image` has 1 chain. `row` has one chain
  per row, so H = 1080. `lane:L` has one chain per (row, lane), so H * ceil(W / L), with W = 1920. The values are:
  `lane_1` 2,073,600; `lane_2` 1,036,800; `lane_4` 518,400; `lane_8` 259,200; `lane_16` 129,600; `lane_32` 64,800;
  `lane_64` 32,400; `lane_128` 16,200; `row` 1,080.
- Figures: `fig_grid.png`, a 3 x 4 mosaic of quarter-size previews (4 x 4 block means) in the layout written to
  `results.json`. The cells are `image`, `row`, `lane_1` and `lane_2` in the first row; `lane_4`, `lane_8`, `lane_16`
  and `lane_32` in the second; `lane_64`, `lane_128` and the reference in the third. The last cell is empty.

### Deviations from the card, decided before the analysis

- **D1 (seed blocks).** The card starts the new blocks at 10. Experiment 002 has taken blocks 10-18, so the blocks
  here start at 19, as the orchestrator directed. Seeds stay globally unique.
- **D2 (diffuse-only measurement).** Measurement is restricted to the diffuse regions, as in experiment 002 (D5). This
  keeps the family at 46 keys, and it lets the 64 px smoke run work, where the light has no lag-1 pairs.
- **D3 (decision rules not stated on the card).** The card says "refuted iff" for H1 and gives no rule for "supported".
  The rules above are fixed here. H2 has no card rule either: it is decided by L* and the power of its tests.
- **D4 (anisotropy).** The card's H2 anisotropy claim has no test, so it has no verdict (see H2).

### Amendments (T1.12)

- Metrics are computed by report.ensemble_metrics (T1.11), the same metrics.measure call that the Analysis section names as experiment.measure_ensemble.

## Results

Source: `results.json`, written by `analyze.py` from the render cache (160 renders, `jobs.py`). Each configuration is 8 pairs at 400 px with P = 64 passes, measured over the 46 diffuse keys. Means ± sd are over the 8 pairs (sample sd, ddof 1). `rel. diff` = (mean − row mean) / |row mean|, and `Cohen's d` = (mean − row mean) / pooled sd. The figure is `fig_grid.png` (273,274 bytes).

**Table 1a. all.pattern_corr and r4.structure_std, mean ± sd over 8 pairs**

| configuration | chains per pass (1920×1080) | all.pattern_corr | rel. diff vs row | Cohen's d vs row | r4.structure_std | rel. diff vs row | Cohen's d vs row |
|---|---:|---:|---:|---:|---:|---:|---:|
| image | 1 | 0.5889 ± 0.0016 | -0.001731 | -0.5974 | 5.738 ± 0.071 | -4.579e-06 | -0.0003171 |
| row | 1,080 | 0.5899 ± 0.0018 | 0 (reference) | 0 (reference) | 5.738 ± 0.093 | 0 (reference) | 0 (reference) |
| lane_1 | 2,073,600 | 0.1260 ± 0.0026 | -0.7863 | -204.2 | 2.562 ± 0.121 | -0.5535 | -29.46 |
| lane_2 | 1,036,800 | 0.2101 ± 0.0020 | -0.6439 | -198 | 5.615 ± 0.060 | -0.02146 | -1.569 |
| lane_4 | 518,400 | 0.3266 ± 0.0027 | -0.4464 | -115.2 | 5.771 ± 0.065 | +0.005816 | +0.4148 |
| lane_8 | 259,200 | 0.4266 ± 0.0020 | -0.2769 | -84.67 | 5.869 ± 0.070 | +0.0228 | +1.589 |
| lane_16 | 129,600 | 0.5002 ± 0.0021 | -0.1521 | -45.52 | 5.777 ± 0.112 | +0.006801 | +0.3787 |
| lane_32 | 64,800 | 0.5415 ± 0.0022 | -0.08204 | -23.62 | 5.729 ± 0.087 | -0.001652 | -0.105 |
| lane_64 | 32,400 | 0.5637 ± 0.0008 | -0.04444 | -18.41 | 5.714 ± 0.064 | -0.004121 | -0.2951 |
| lane_128 | 16,200 | 0.5732 ± 0.0022 | -0.02832 | -8.352 | 5.689 ± 0.039 | -0.008477 | -0.6809 |

**Table 1b. r4.lag1.x and r4.lag1.y, mean ± sd over 8 pairs**

| configuration | r4.lag1.x | rel. diff vs row | Cohen's d vs row | r4.lag1.y | rel. diff vs row | Cohen's d vs row |
|---|---:|---:|---:|---:|---:|---:|
| image | 0.2033 ± 0.0091 | +0.006081 | +0.175 | 0.2412 ± 0.0073 | +0.005246 | +0.1942 |
| row | 0.2020 ± 0.0040 | 0 (reference) | 0 (reference) | 0.2399 ± 0.0056 | 0 (reference) | 0 (reference) |
| lane_1 | 0.0907 ± 0.0066 | -0.5512 | -20.42 | 0.0859 ± 0.0085 | -0.642 | -21.42 |
| lane_2 | -0.1888 ± 0.0053 | -1.935 | -83.56 | 0.3550 ± 0.0033 | +0.4793 | +25.16 |
| lane_4 | 0.0382 ± 0.0030 | -0.811 | -46.1 | 0.3413 ± 0.0068 | +0.4225 | +16.38 |
| lane_8 | 0.1267 ± 0.0046 | -0.3729 | -17.52 | 0.3179 ± 0.0068 | +0.325 | +12.57 |
| lane_16 | 0.1554 ± 0.0071 | -0.2306 | -8.08 | 0.2812 ± 0.0059 | +0.1721 | +7.195 |
| lane_32 | 0.1755 ± 0.0043 | -0.1314 | -6.362 | 0.2619 ± 0.0045 | +0.09142 | +4.33 |
| lane_64 | 0.1916 ± 0.0047 | -0.05175 | -2.406 | 0.2505 ± 0.0059 | +0.04388 | +1.843 |
| lane_128 | 0.1902 ± 0.0042 | -0.05862 | -2.873 | 0.2553 ± 0.0051 | +0.06381 | +2.877 |

**Table 2. Chains per pass at 1920 × 1080**

| configuration | chains per pass |
|---|---:|
| image | 1 |
| row | 1,080 |
| lane_1 | 2,073,600 |
| lane_2 | 1,036,800 |
| lane_4 | 518,400 |
| lane_8 | 259,200 |
| lane_16 | 129,600 |
| lane_32 | 64,800 |
| lane_64 | 32,400 |
| lane_128 | 16,200 |

The chains are read from `results.json` (`chains_per_pass_1920x1080`). They were not recomputed from SPEC §3, because the file holds them.

**Table 3a. H1, adjacent steps of all.pattern_corr (Holm over 7 steps at α = 0.01)**

| step (shorter → longer) | mean ± sd (longer) | p_less | p_greater | Holm (greater) | Holm (less) | min_attainable_p | rel. diff | Cohen's d | diff |
|---|---:|---:|---:|---|---|---:|---:|---:|---:|
| lane_1->lane_2 | 0.2101 ± 0.0020 | 1.000 | 7.77e-05 | rejected | not rejected | 7.77e-05 | +0.6666 | +35.81 | +0.08402 |
| lane_2->lane_4 | 0.3266 ± 0.0027 | 1.000 | 7.77e-05 | rejected | not rejected | 7.77e-05 | +0.5548 | +49.38 | +0.1165 |
| lane_4->lane_8 | 0.4266 ± 0.0020 | 1.000 | 7.77e-05 | rejected | not rejected | 7.77e-05 | +0.3061 | +42.21 | +0.09998 |
| lane_8->lane_16 | 0.5002 ± 0.0021 | 1.000 | 7.77e-05 | rejected | not rejected | 7.77e-05 | +0.1726 | +35.65 | +0.07364 |
| lane_16->lane_32 | 0.5415 ± 0.0022 | 1.000 | 7.77e-05 | rejected | not rejected | 7.77e-05 | +0.0826 | +18.98 | +0.04132 |
| lane_32->lane_64 | 0.5637 ± 0.0008 | 1.000 | 7.77e-05 | rejected | not rejected | 7.77e-05 | +0.04096 | +13.06 | +0.02218 |
| lane_64->lane_128 | 0.5732 ± 0.0022 | 1.000 | 7.77e-05 | rejected | not rejected | 7.77e-05 | +0.01687 | +5.8 | +0.009511 |

H1 `p_less` is the one-sided p-value for a decrease, and `p_greater` for an increase. `Holm` is applied at α = 0.01 over the 7 steps, separately to each direction.

**Table 3b. H2, each lane length against row on all.pattern_corr (Holm over 8 at α = 0.01)**

| L | mean ± sd | p_less (lane_L vs row) | Holm rejected (less) | min_attainable_p | rel. diff vs row | Cohen's d vs row |
|---:|---:|---:|---|---:|---:|---:|
| 1 | 0.1260 ± 0.0026 | 7.77e-05 | rejected | 7.77e-05 | -0.7863 | -204.2 |
| 2 | 0.2101 ± 0.0020 | 7.77e-05 | rejected | 7.77e-05 | -0.6439 | -198 |
| 4 | 0.3266 ± 0.0027 | 7.77e-05 | rejected | 7.77e-05 | -0.4464 | -115.2 |
| 8 | 0.4266 ± 0.0020 | 7.77e-05 | rejected | 7.77e-05 | -0.2769 | -84.67 |
| 16 | 0.5002 ± 0.0021 | 7.77e-05 | rejected | 7.77e-05 | -0.1521 | -45.52 |
| 32 | 0.5415 ± 0.0022 | 7.77e-05 | rejected | 7.77e-05 | -0.08204 | -23.62 |
| 64 | 0.5637 ± 0.0008 | 7.77e-05 | rejected | 7.77e-05 | -0.04444 | -18.41 |
| 128 | 0.5732 ± 0.0022 | 7.77e-05 | rejected | 7.77e-05 | -0.02832 | -8.352 |

H2 is decided by L* and by the power of its tests. Powered threshold: 0.01 / 8 = 1.25e-03.

**Table 3c. H3, row against image on the 46-key diffuse family (Holm at α = 0.01)**

| comparison | keys | rejected | min_attainable_p | Holm first threshold | smallest observed p (key) | largest \|rel. diff\| (key) | largest \|Cohen's d\| (key) | powered |
|---|---:|---:|---:|---:|---|---|---|---|
| row vs image | 46 | 0 | 1.55e-04 | 2.17e-04 | 0.0202 (r5.pattern_corr) | 0.06908 (all.spectral_slope, see footnote) | 1.344 (r5.pattern_corr) | True |

^a `all.spectral_slope` has a near-zero mean (row -0.04743 ± 0.01059, image -0.04436 ± 0.00916), so its relative difference (-0.06908) is not a meaningful effect size. Its absolute difference, row minus image, is -0.003064, with Cohen's d -0.3095.

**Table 4. Decision table (one row per hypothesis)**

| hypothesis | claim | decision | deciding numbers (results.json) |
|---|---|---|---|
| H1 | `all.pattern_corr` does not fall as L grows (7 adjacent steps, Holm at α = 0.01) | supported | significant increases 7 of 7 (p_greater 7.77e-05 each); significant decreases 0 of 7 (p_less 1.000 each); powered: min_attainable_p 7.77e-05 ≤ 0.01 / 7 = 1.43e-03; largest \|rel. diff\| 0.6666 (lane_1->lane_2); largest \|d\| 49.38 (lane_2->lane_4) |
| H2 | some lane length matches row on `all.pattern_corr`; L* = smallest such L | refuted (L* = none) | 8 of 8 lane lengths Holm-rejected against row in the less direction (p_less 7.77e-05 each); powered: min_attainable_p 7.77e-05 ≤ 0.01 / 8 = 1.25e-03; closest, L = 128: rel. diff -0.02832, d -8.352 |
| H3 | row is indistinguishable from image on the 46-key diffuse family | supported | 0 of 46 keys rejected; min_attainable_p 1.55e-04 ≤ Holm threshold 2.17e-04 (powered); smallest observed p 0.0202 (r5.pattern_corr); largest \|d\| 1.344 (r5.pattern_corr); largest \|rel. diff\| 0.06908 (all.spectral_slope, footnote a; absolute diff -0.003064) |

**Notes (Opus, 2026-10-09).**
- In Table 3a, the relative difference is (longer − shorter)/|shorter|, not the row-based definition in the Results
  introduction.
- In Table 2, `image` has one chain for the whole render, all passes included, not one per pass.

## Conclusion

Final (Opus, 2026-10-09). The Haiku draft is superseded. The numbers are those in Results.

**A per-row chain is as good as the reference chain. A finite lane is a stylization knob, not a fidelity knob.**

- **H1 supported.** Fidelity rises monotonically with lane length. Pattern correlation is 0.126, 0.210, 0.327, 0.427,
  0.500, 0.542, 0.564 and 0.573 for L = 1, 2, …, 128. All 7 steps are significant increases (p = 7.77e-5).
- **H2 refuted.** No L ≤ 128 matches `row` (L* = none). The closest, L = 128, is 2.8% below row (0.573 vs 0.590,
  d = −8.4). Lanes cannot replace the row chain at equal fidelity.
- **H3 supported.** `row` and `image` are indistinguishable: 0 of 46 keys rejected, in a powered family
  (min_attainable_p 1.55e-4 against a first Holm threshold of 2.17e-4). The smallest p is 0.020, the largest |d| is 1.34,
  and pattern correlation is 0.5899 vs 0.5889. Restarting each (row, pass) at a hashed K0 costs nothing measurable.

**What lanes change instead.**
- Texture amplitude is flat from L = 2 on: `r4.structure_std` 5.61-5.87 against row's 5.74.
- Anisotropy changes. At L = 16, `r4.lag1.x` is −23% and `r4.lag1.y` +17% relative to row.
- An exploratory per-offset analysis by the milestone review found a seam column at each lane start: about +50%
  amplitude, aligned across rows. SPEC §3 now says so.

**Decisions.**
1. `chain = row` is the Blender default (SPEC §3, §8). It parallelizes over rows (1,080 chains per pass at 1080p) with no
   loss of fidelity.
2. `lane_length = 16` stays the default of the `lane` chain, as a stroke-shape control.
3. A deterministic per-row lane offset (`lane_stagger`) is a candidate knob for an M7 experiment.
