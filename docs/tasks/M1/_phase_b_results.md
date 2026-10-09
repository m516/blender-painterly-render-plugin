# Phase B of T1.7, T1.8 and T1.9: results and draft conclusions for experiments 002, 003 and 004
Milestone: M1 · Depends on: T1.11 and the completed renders (`--budget 0` reports remaining=0 for all three) · Parallel-safe: no

The orchestrator runs this card three times, once per experiment, in the order 002, 003, 004. Each run does only
the section its note names and makes one commit. Read `docs/tasks/M1/_experiment_protocol.md` items 5 to 9 first.

## Rules for every section
- **Never edit** `jobs.py`, the `## Background`, `## Hypothesis` or `## Method` sections, or any pre-registered text.
  Phase B only *adds* `## Results` and `## Conclusion`, and updates the experiment's row in `experiments/README.md`.
  One exception: 004's D6 continuation line ("At full scale, …") starts at column 0 in the middle of a bullet. Indent it
  so that it continues its bullet. Change nothing else in it.
- Run the analysis with the experiment oracle and the default out-dir:
  `PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python experiments/00N-*/analyze.py`.
  Before the run, check that `PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python -m painterly_analysis.experiment run experiments/00N-*/jobs.py --budget 0`
  prints `remaining=0`. If it does not, stop and report: never render in this card.
- The analysis is deterministic. Run it a second time into a scratch `--out-dir` and `cmp` every output file against the
  first run. Report the result.
- Commit `results.json` and every `fig_*.png` it writes. Each figure must be ≤ 1 MB. Never commit `.cache/` or `out/`.
- `## Results` holds tables of numbers taken from `results.json`, with no adjectives that lack a number:
  - means ± sd per configuration;
  - p-values and Holm decisions;
  - `min_attainable_p` next to every "indistinguishable" or "not rejected";
  - `largest_abs_rel_diff` and `largest_abs_cohen_d` for every comparison.
  Add a footnote wherever a relative difference is reported for a key whose mean is near zero, because the ratio there
  is not a meaningful effect size. Those keys are `all.spectral_slope` (mean about −0.044) and `all.block_rmse` (mean
  about 0.38 in units of the reference spread). Give the absolute difference for them instead.
  Cohen's d values in the thousands only reflect the tiny seed-to-seed sd. Say so once, and use the relative difference
  as the effect size elsewhere.
- `## Conclusion` starts with the line `DRAFT (Haiku) — pending Opus review.`. Then, for each hypothesis: supported,
  refuted or inconclusive, with the deciding numbers. Opus finalizes it later.
- `experiments/README.md`: set the row's Conclusion cell to a one-line summary of the decisions. The Status stays `draft`.
- Every number you write must be present in `results.json` or be computed from it. The numbers below come from the
  milestone review's independent run. They are what you should find. If yours differ, report the difference and keep
  your own number.

## Section 002 (card T1.7). Commit `T1.7: experiment — ingredient ablation results`
Expected decisions: H1 supported, H2 supported, H3 supported, H4 supported, H5 distinguishable (45 of 46 keys).
Include these tables:
1. `r4.luma`, `all.pattern_corr` and `r4.structure_std` for all ten configurations, as mean ± sd.
2. K draws per pixel per pass (the mean of `k_consumed / passes`) for every configuration. Review values: positive
   16.274, ghost_none 18.682, ghost_lights 19.210, stop_at_emitter 5.056.
3. The decision table, with one row per hypothesis.
4. H4's and H5's numbers of rejected keys out of 46, the keys that are *not* rejected with their p-values, and the
   clip fractions (H5: 0.0712 vs 0.0043).
Results note: ghost_lights has `all.pattern_corr` 0.005 because its K consumption differs (19.21 vs 16.27 draws per
pixel per pass). Its texture amplitude is kept: `r4.structure_std` 5.38 vs 5.74. The pattern correlation measures
agreement with one specific *realization* of the texture, so it collapses whenever K consumption changes.

## Section 003 (card T1.8). Commit `T1.8: experiment — lane length results`
Expected decisions: H1 supported (all 7 steps are significant increases), H2 refuted (no L ≤ 128 matches row, so L* = none),
H3 supported (0 of 46 keys rejected, min_attainable_p 1.55e-4).
Include these tables:
1. pattern_corr, `r4.structure_std`, `r4.lag1.x` and `r4.lag1.y` for each L, for row and for image.
2. Chains per pass at 1920×1080, from `results.json` if it is there. Otherwise compute it from the chain definitions
   in SPEC §3 and say so.
3. The decision table.

## Section 004 (card T1.9). Commit `T1.9: experiment — resolution dependence results`
Expected decisions (pre-registered rules): H1a refuted (3, 12 and 12 of 12 keys), H1b refuted under the one-sided rule
(12 "greater", 0 "less"), H1d refuted (2, 11 and 11 of 12), H2 supported (23 of 30; `r4.structure_std` 4.14 ± 0.02 vs 4.79 ± 0.03).
Include these tables:
1. The 12 `slag1` keys and `r4.structure_std` per configuration (all seven).
2. The decision table for H1a, H1b, H1d and H2.
3. Region means `r4.mean.G` by size.
Add these two paragraphs verbatim at the end of Results:

> **Limitation (Opus).** H1a, H1b and H1d compare the sizes in fixed pixel units: a 9-px high-pass, a 4-px erosion and
> lag 1 at every size. At 800 px those filters cover half the image-plane footprint they cover at 400 px. H1b's sign rule
> also assumes an exponential correlation. The measured 800 px correlation in x is not exponential: lag 1 0.638, lag 2
> 0.231 (an exponential would give 0.407), lag 3 0.027. The pre-registered verdicts therefore do not decide whether the
> texture is locked to the pixel grid or to the image. Experiment 006 asks that question with filters, erosion and lag
> scaled with the image side.

> **Region means and erosion.** The trend of `r4.mean.G` with size comes from the fixed 4-px erosion, which keeps a
> wider band near region edges at 200 px than at 800 px. It is not a property of the renderer.

## Acceptance (per run)
- The section's `analyze.py` exits 0. A second run into a scratch out-dir is byte-identical (`cmp` on every output).
- README has all five sections. `## Conclusion`'s first line is `DRAFT (Haiku) — pending Opus review.`.
- `git diff HEAD~1 -- experiments/00N-*/jobs.py` is empty. `git diff HEAD~1 -- experiments/00N-*/README.md` only adds
  lines after `## Method`'s last line, except 004's D6 re-indentation.
- Each figure is ≤ 1 MB (`find experiments/00N-* -name 'fig_*.png' -size +1M` prints nothing).
- `make lint` passes.

## Section 006 (card T1.13). Commit `T1.13: experiment — jitter units results`
Run after T1.14, and only when `--budget 0` prints `remaining=0` for `experiments/006-*/jobs.py`, which now has 256 jobs.
The README's "Amendments before analysis" apply. Never edit them or any pre-registered text.

Expected decisions, from the milestone review's exploratory run of the original design. H4 is new data, so no value is
expected for it:
- H1-image refuted: 1, 0 and 2 of 18 keys for (200, 400), (400, 800) and (200, 800).
- H1-row refuted: 0, 0 and 1 of 18.
- H2-image supported: 7 and 9 of 18. H2-row supported: 9 and 9 of 18.
- H3 supported, row chain: Δ_image-plane 0.0513 [0.0460, 0.1127] vs Δ_pixel 0.1578 [0.1412, 0.2281]. The difference is
  0.1064 [0.0489, 0.1632], whose interval excludes 0.
- H5 refuted: 1 of 36 rows fails (s400 vs s800 `r5.mean.R`).
- H4 on `row_j0_*`: report whatever the rule gives.

Include these tables:
1. Δ_u per unit and chain, with the bootstrap intervals and `delta_by_class`.
2. For every comparison: the rejected keys out of 18, `min_attainable_p`, and the texture-only largest |rel| and |d|.
3. The rejected keys of H1-image and H1-row, each with its relative difference. They concentrate on `r4.slag.x`, the
   back wall's along-row lag.
4. H5 rows: scaled vs fixed |rel_diff| for every region-mean key and both pairs.
5. `distinct_renders` of the image-chain `j0_*` family, and the `jitter_footprint` effects (`row_j0_sN` vs `row_sN`).
Describe σ as "the standard deviation of a continuous 9-px box (the discrete 9-tap box has 2.582 px)".
Figures: the six `fig_grid_*.png` files and `fig_slag_profile.png`.
