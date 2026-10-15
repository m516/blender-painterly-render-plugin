# PLAN: analysis card for experiment 007 (noise locking)

The pre-registration is `README.md` (Background, Hypothesis and Method). This card implements its Method. It does not
change the hypotheses or rules. If something in them cannot be implemented as written, stop and report it. Opus then
adds an "Amendments before analysis" subsection.

## Directory and date

- The directory `experiments/007-2026-10-15-noise-locking/` already exists. The Opus commit that created it with the
  pre-registration (`README.md`) and the index row fixed `2026-10-15`: `date +%F` on that commit's day, 2026-10-15 or
  later. Experiments 007, 008 and 009 are numbered and dated in the order they run.
- Find it with `ls -d experiments/007-*-noise-locking` from the repository root, and stop if that does not print
  exactly one directory. It is written `EXP` below. In every command below, put that literal path where `EXP` (or the
  README's `experiments/007-2026-10-15-noise-locking`) stands. Do not create or rename a directory.

## Files

- In `EXP`:
  - `README.md` exists. Replace only the two "Pending" lines under `## Results` and `## Conclusion` (step 7). Do not
    change Background, Hypothesis or Method;
  - create `analyze.py`, `results.json`, `synthetic.json` and the five figures.
- Modify:
  - `experiments/README.md`: the 007 row exists (pre-registration commit, as for 006). Keep its status `draft` and
    replace only its Conclusion cell with a one-line summary of the verdicts (step 7). The pre-registration commit
    adds it as

    ```
    | 007 | 2026-10-15 | noise-locking | Is the seed-dependent texture pixel-locked, and how much does the low-pass look depend on resolution? | draft | pre-registered; analysis pending |
    ```

  - `analysis/painterly_analysis/metrics.py`: `gaussian_highpass_axis`, below. Experiment 009's card, which runs after
    this one, adds another function to the same file;
  - `analysis/painterly_analysis/__init__.py`: export `gaussian_highpass_axis` (import list and `__all__`);
  - `analysis/tests/test_scale_metrics.py`: its tests;
  - `analysis/painterly_analysis/report.py`: four helpers, below;
  - `analysis/tests/test_report.py`: their tests.
- No `jobs.py`. Nothing is rendered. The jobs come from `experiments/006-2026-10-09-jitter-units/jobs.py` through
  `report.load_jobs_module`, with `build_ensembles(pairs, scale)`.
- No change to `third_party/`, `docs/`, `src/` or the oracle. **Never run `make oracle`**: the render cache is keyed
  by the binary `.cache/oracle-build/src/app/smallpaint_oracle`, sha256
  `066bb5d4247c556ad5232bfc4fff75dc5f37089840b23f1ecc8fdd9cb518828a`, which experiments 006, 008 and 009 also use. A
  rebuild changes that sha256 and orphans every cached render. `experiments/README.md` ("How to run") says the same.

## Reuse (no copies)

- `io`: `smallpaint_display`, `write_png`.
- `metrics`: `luminance`, `gaussian_highpass_axis` (new, the frames' along-row high-pass), `gaussian_highpass` (H4's
  isotropic keys, the estimation keys `iso_nlag` and E1), `noise_corrected_lag` (with identical arguments it is the
  masked autocorrelation, already unit-tested), `structure_std` (with identical arguments the masked population sd),
  `region_masks`, `DIFFUSE_REGION_IDS`, `HIGHPASS_SIZE`.
- `report`: `diffuse_only`, `family_test` (with `labels`), `summary_table`, `largest_abs_rel_diff`,
  `largest_abs_cohen_d`, `format_largest`, `write_results_json`, `block_preview`, `mosaic`, `load_jobs_module`,
  `check_seed_reuse` (full scale only), and the new `box_downsample_sum`, `largest_abs_diff`, `draw_line`, `paint` and
  `bootstrap_cohen_d`.
- `ensemble`: `effect_summary` (its `cohen_d` is the point value of the effect statistic), `permutation_pvalue`
  (through `family_test`), `sign_flip_pvalue` (H4, H5), `holm`.
- `experiment`: `load`, `job_key`, `cache_root` (the smoke-cache count of step 0). No `run_jobs`: neither the full run
  nor the smoke run renders.

## Add to `metrics.py`, with unit tests in `test_scale_metrics.py`

`gaussian_highpass_axis(x, sigma, axis)`: `x − G_σ * x` along one axis of a 2-D field (H, W). `axis=1` blurs each row
(x), `axis=0` each column (y). The blur acts on the half-sample-symmetric extension along that axis only (for `axis=1`,
each row followed by its mirror image, 2W points), so no wrap-around enters at the border; the result is cropped back
to (H, W). Its transfer at frequency ν (cycles per pixel of the extended axis) is `exp(−2π²σ²ν²)`, the Fourier
transform of a Gaussian of sd σ (a definition, as in `gaussian_highpass`). Units of `x`. Raises ValueError for a field
that is not 2-D, for `sigma < 0`, or for an `axis` other than 0 or 1. JAX (`jnp.fft.rfft`/`irfft` along the axis), like
the rest of `metrics`. Tests (tolerances as in the existing `gaussian_highpass` tests, each justified in a comment as
float64 FFT round-off):
- a constant field has zero high-pass;
- for each axis, `cos(2πν(n + 1/2))` with `ν = k/(2L)` along that axis (L samples) passes with gain
  `1 − exp(−2π²σ²ν²)`;
- a field that is constant along the axis has zero high-pass, whatever it does across the axis;
- a field that varies only along the axis gives `gaussian_highpass`'s result (the 2-D transfer at zero frequency across
  the axis is the 1-D one);
- `gaussian_highpass_axis(x, σ, 1)` equals `gaussian_highpass_axis(x.T, σ, 0).T`;
- changing one row of `x` leaves every other row of the `axis=1` high-pass bitwise unchanged (`np.array_equal`): each
  row is filtered from that row alone.

## Add to `report.py`, with unit tests

1. `box_downsample_sum(sum_, factor)`. Each `factor × factor` block of an (H, W, C) sum array is replaced by its mean.
   This is 004's `_box_down` generalised; 004 is final, so it keeps its copy. Tests:
   - a constant array stays constant;
   - one block's mean is exact on integer-valued input;
   - a side that is not a multiple of `factor` raises ValueError;
   - `factor = 1` is the identity.
2. `largest_abs_diff(summary)`. The same as `largest_abs_rel_diff`, on the field `diff`. It serves the `nlag.x` keys,
   whose means can be near 0.
3. `draw_line(canvas, x0, y0, x1, y1, color, dashed=False, dash_period=10, dash_on=6)` and
   `paint(canvas, xs, ys, color)`. The defaults are 006's `DASH_PERIOD_PX` and `DASH_ON_PX`, and the stroke is 006's
   2-px stroke (offsets (0, 0), (1, 0), (0, 1)). For the same arguments, `report.draw_line` paints exactly the pixels of
   006's `_draw_line`. Tests: one solid and one dashed line equal 006's `_draw_line` output exactly (`np.array_equal`;
   006's `analyze.py` is loaded with `report.load_jobs_module`, which works: it has a `__main__` guard and no
   `from __future__ import annotations`); out-of-canvas points are skipped. 006 keeps its local copies, because its
   outputs are final. Experiments 008 and 009 call these helpers.
4. `bootstrap_cohen_d(a, b, draws_a, draws_b)`. `a` is an (n_a, k) matrix of per-pair key values, `b` an (n_b, k)
   matrix, `draws_a` an (R, n_a) and `draws_b` an (R, n_b) integer index matrix. It returns the (R, k) matrix of Cohen's
   d of every resample at once, `(mean_a − mean_b)/s_p` with `ensemble.effect_summary`'s pooled sd
   `s_p = sqrt(((n_a − 1) sd_a² + (n_b − 1) sd_b²)/(n_a + n_b − 2))` (sample sds, ddof 1). It is vectorised with
   `jax.numpy` (no Python loop over resamples) and raises ValueError if any resample has `s_p = 0` for any key. It is
   the bootstrap form of `effect_summary`'s formula and is tested against it, so it is not a forbidden copy. Tests:
   - on the identity draw (one row, `arange(n)`) it equals `effect_summary`'s `cohen_d` for every key (float64
     round-off of the same formula: `rtol=1e-12`, justified in a comment);
   - every row of two random draws equals `effect_summary` on the resampled runs (same tolerance);
   - a draw that repeats one pair in both groups (`s_p = 0`) raises.

## `analyze.py` structure (local functions)

- Named constants, each with its origin in a comment:
  - `SIGNIFICANCE = 0.01`; `LEVEL_WITH_JIT = SIGNIFICANCE / 3` (H1, H2); `LEVEL_NO_JIT = SIGNIFICANCE / 2` (H3);
    `MECHANISM_LEVEL = SIGNIFICANCE` (H4, H5);
  - `REFERENCE_SIDE` and `REFERENCE_JITTER`, read from 006's `jobs.py` (`REFERENCE_JITTER = Fraction(1, 700)` is j,
    in image-plane units), `SIGMA_REF = HIGHPASS_SIZE / sqrt(12)`, `LAG_UNIT_SIDE = 200`,
    `PX_LAG = REFERENCE_SIDE // LAG_UNIT_SIDE`;
  - `EROSION_DIVISOR = 25`; `ROW_CORR_LAG = 1` (H5: adjacent rows, a definition);
  - `PROFILE_PX_LAGS = (1, 2, 3, 4, 6, 8, 12)`, `PROFILE_IP_K = (1, 2, 3)`, `PROFILE_REGION = 4`;
  - `BOOTSTRAP_RESAMPLES = 100_000`, `BOOTSTRAP_SEED = 0`, `CI_DECISION = (0.5, 99.5)` (level 0.01 = `SIGNIFICANCE`,
    the level of a hypothesis). 007 uses this level for every interval, including those that are only reported
    (E1's β_S and β_q), so it has no `CI_REPORT`;
  - `DETECTION_POWER = 0.95` (H4, H5 detection limits, `Φ⁻¹(DETECTION_POWER^(1/pairs))·sd`, 2.49·sd at 8 pairs);
  - `DOWNSAMPLE_FACTOR = 2`; `ROUNDING_VARIANCE = 1 / 12` (variance of the display's rounding, a definition);
  - `CROP_PX = 100`, `COMMON_CROP_PX = 200`, `CROP_FRACTION = Fraction(1, 4)`, `NOISE_DISPLAY_OFFSET = 128` (mid-grey
    of the byte range, a definition), `MAX_FIGURE_BYTES = 1_000_000`;
  - `ORACLE_SHA256 = "066bb5d4247c556ad5232bfc4fff75dc5f37089840b23f1ecc8fdd9cb518828a"`; at start-up the script
    computes the binary's sha256 and raises if it differs;
  - the synthetic knobs (README Method, "Synthetic validation"): `SYNTH_SEED = 0`, `SYNTH_REPLICATES = 10`,
    `SYNTH_E1_PAIRS = 64`, `SYNTH_STRUCTURE_TERMS = 16`, `SYNTH_STRUCTURE_BAND = (2, 50)` (cycles per image, 006),
    `SYNTH_STRUCTURE_SD = sqrt(33.07)` and `SYNTH_NOISE_SD = sqrt(5573.6 / 64)` (001 H4), `SYNTH_AR_PHI = 0.6`,
    `SYNTH_SIGMA_N_REF_PX = 2.0`, `SYNTH_DRIFT_VAR_PER_DOUBLING = 2`, `SYNTH_IMAGE_NU_MAX = 99` (cycles per image,
    below the 200 px Nyquist frequency), `SYNTH_WHITE_SHARE = 0.5` (the `mix_*` models);
  - `SYNTH_MODELS = ("white", "white_drift", "ar1", "pix_x", "pix_gauss", "ipjit_x", "jit_x", "jit_gauss", "img_x",
    "img_gauss", "mix_x", "mix_gauss")`; a model's position is its `model_index`;
  - `SYNTH_CONFIGS = ("ref@200-400", "ip200", "px200", "ref@400-800", "ip800", "px800", "e1_native200",
    "e1_down400", "e1_native400", "e1_down800")`; a configuration's position is its `configuration_index`.
- `TABLE`: the 13 configurations of the README Method table, as name → (native side, chain, f as a `Fraction`
  (checked against 006's `--jitter` = 2f), block, role). At full scale, check it against 006 `DESIGN` and `ENSEMBLES`,
  including the reuse of 006's option sets and seeds. At smoke scale, check the jobs against 006's
  `build_ensembles(pairs, scale)` only.
- `frame_params(native_side, scale)` returns σ and τ of both frames, `e(s)` of the rendered side `s = native/scale`, and
  the profile lags.
  - σ and τ are those of the native side at every scale (README, Smoke run): `σ_px = SIGMA_REF`, `τ_px = PX_LAG`,
    `σ_ip = SIGMA_REF * (native / REFERENCE_SIDE)`, `τ_ip = native // LAG_UNIT_SIDE`. So `σ_ip` is bitwise equal to
    `σ_px` at native 400, and every lag is an exact integer. Assert both.
  - `e(s) = s // EROSION_DIVISOR`, asserted exact at full scale.
- `pair_keys(a8, b8, params, masks, smoke, *, estimation, profiles)`:
  - always: N_px and N_ip (`noise_frac`, `nlag.x`) from `h_F = metrics.gaussian_highpass_axis(δ, σ_F, 1)`;
  - always at native 400 px: H4's `px.r{r}.iso_nlag.x` and `px.r{r}.iso_nlag.y` (lag τ_px along x and along y of the
    isotropic `h_px^iso = metrics.gaussian_highpass(δ, σ_px)`) and H5's `raw.r{r}.row_corr`;
  - `estimation=True`: `noise_std`, `structure_std` (along-row high-pass of each half), `F.r{r}.iso_nlag.x`,
    `F.r{r}.iso_nlag.y` and `F.r{r}.aniso` in both frames, and `raw.r{r}.row_corr`, at every side;
  - `profiles=True`: the profiles of `h_px`, `h_ip` and unfiltered δ, along x and y.
  - The analysis passes `estimation=True, profiles=True`; `synthetic` passes both False. At native 400 px, assert that
    the `px` and `ip` keys are equal. A profile lag with no pixel pair in a mask is `None` at smoke scale and raises at
    full scale.
- `row_corr(delta, mask)` (H5): the mean of `δ(i, j)·δ(i + 1, j)` over the pixel pairs whose two pixels are in the
  mask, divided by the mean of `δ²` over the mask. Uncentred (δ has zero expectation at every pixel). Raises if a mask
  has no such pair.
- `common_side_keys(native_pair, double_pair, params, masks)` returns `c.r.noise_var` and `c.r.structure_cov` for the
  native and downsampled variants (`box_downsample_sum`, then `smallpaint_display`), with the 2-D
  `metrics.gaussian_highpass` at σ_ip of the common side (E1 measures the displayed 2-D look, not locking).
- `k_per_pass(render, masks)`.
- `distinct_renders(jobs, pairs)`: sha256 of each `sum`. It raises if fewer than `2 * pairs` are distinct or a pair has
  `δ ≡ 0`.
- `comparison(runs, a, b, frame, level)`: `report.family_test` on the 12 keys of N_frame, then replace its
  `largest_abs_rel_diff` with the per-class maxima (`noise_frac` and `noise_std` by |relative difference|, `nlag.x` by
  `largest_abs_diff`, every class by |Cohen's d|), and add the effect summary of the `noise_std` estimation keys.
- `delta_stats(runs, hypothesis, smoke)`: Δ per frame and class from the point `|cohen_d|` of `effect_summary`, D and
  D_jit, and at full scale their `CI_DECISION` percentile intervals (`np.percentile`, default linear interpolation).
  - Per hypothesis, `rng = numpy.random.default_rng(BOOTSTRAP_SEED)` is created once and draws
    `rng.integers(0, pairs, (BOOTSTRAP_RESAMPLES, pairs))` for the configurations in the order reference, sN, sN_px
    (H3: reference, sN). Δ_px, Δ_ip, D and D_jit all use these matrices; the reference's matrix serves `C_px`, `C_ip`
    and `C_jit`.
  - The per-resample d come from `report.bootstrap_cohen_d`; Δ of a resample is the median over the 12 keys of |d|.
  - A point `cohen_d` of None (pooled sd 0) raises at full scale.
  - At smoke scale no interval is computed: the intervals of D and D_jit are recorded as `null`.
- `verdict(R_px, R_ip, R_jit, D_ci, D_jit_ci, powered)` implements the README table (cells 1-7); `R_jit = None` for
  H3. "D > 0" is `D_ci[0] > 0`, "D < 0" is `D_ci[1] < 0`, likewise for D_jit; an interval containing 0 satisfies
  neither. Unpowered comparisons or a `null` interval give cell 7. It returns the cell number, the verdict and the
  reading.
- `mechanism(runs, name)` (H4) and `row_independence(runs, name)` (H5): the per-pair statistic (A or Y),
  `ensemble.sign_flip_pvalue(·, "two-sided")`, the decision at `MECHANISM_LEVEL`, mean ± sd and the detection limit.
  Each is "inconclusive" when the smallest attainable p, `2 / 2**pairs`, exceeds the level (smoke scale).
- `e1(native, down, smoke)` returns β, β_S, β_q per region and as medians, and P_eq; at full scale also their
  `CI_DECISION` intervals (one `default_rng(BOOTSTRAP_SEED)` per contrast and family, drawing native then down). At full
  scale it raises if a mean `structure_cov` ≤ 0. At smoke scale such a region's β_S and β_q are `null`, the medians are
  over the other regions (`null` if none), and no interval is computed.
- Estimation blocks: the chain contrast `row_sN` vs `sN` and the jitter footprint `row_sN` vs `row_j0_sN` (both on
  N_px), the pixel-jitter families on N_ip, and E1 for the three families.
- Summaries: a key whose per-pair values are all `None` (a profile lag at smoke scale) is recorded as `null` and not
  passed to `report.summary_table`.
- `synthetic(...)`, behind `--synthetic`, runs the same `pair_keys` (with `estimation=False, profiles=False`),
  comparison, `delta_stats`, verdict, mechanism, row-independence and E1 functions on synthetic sums.
  - Each half is a sum, `P * (128 + m + n)` on 3 channels, generated in display bytes at the README's scale, so it
    passes through `smallpaint_display` exactly as a render does.
  - Models: `SYNTH_MODELS` (README, Method). The row-wise fields (`ar1` via `jax.lax.scan`; `pix_x`, `ipjit_x` and
    `jit_x` by FFT along axis 1 of each row; `img_x` by inverse FFT along axis 1 of integer-frequency coefficients with
    the half-pixel phase) and the isotropic ones (`pix_gauss` and `jit_gauss` by 2-D FFT on the pixel grid,
    `img_gauss` by 2-D inverse FFT with the half-pixel phase). `mix_*` combine `white` and `img_*` with weights
    `sqrt(SYNTH_WHITE_SHARE)` and `sqrt(1 − SYNTH_WHITE_SHARE)`. Each noise field is scaled to unit sample variance over
    the image before `SYNTH_NOISE_SD` (and, for `white_drift`, `sqrt(s / 400)`) is applied. JAX for the field
    arithmetic (CLAUDE.md rule 4).
  - Random streams: the halves of configuration c of model m in replicate i come from
    `numpy.random.default_rng((SYNTH_SEED, i, model_index(m), configuration_index(c)))`. Each contrast has its own
    400 px reference (`ref@200-400`, `ref@400-800`). Every replicate-contrast's bootstrap uses
    `default_rng(BOOTSTRAP_SEED)` as in `delta_stats`.
  - Replicates `0 … SYNTH_REPLICATES − 1` per model and contrast, `--pairs` pairs per configuration. E1 uses replicate 0
    with the `e1_*` configurations and `SYNTH_E1_PAIRS` pairs each, for every model. The prediction table is replicate
    0 (its 400 px column from `ref@200-400`).
  - The masks are those of the cached object-id maps.
  - At smoke scale: one replicate, `--pairs` (2) pairs for every configuration including E1, the side-dependent
    parameters of the native side, and the image-locked frequency limit `min(side) // 2 − 1` (24 at 50 px).
  - It writes `synthetic.json` (`report.write_results_json`) into `--out-dir`: the prediction table, the verdict counts
    (every cell, per model, contrast and hypothesis type), the H4 and H5 rejection counts, E1 for every model, and each
    requirement with its numbers and pass/fail. It then enforces the README's requirements and exits non-zero on a
    failure (after writing the file). At smoke scale it checks no requirement.
- Figures, drawn without text, with their encodings and crop bounds in `results.json`:
  - `fig_nlag_profile_{row,image,row_zero}.png`: 2 × 2 panels, uses `report.draw_line`;
  - `fig_noise_crops.png`: 2 × 3 tiles of 100 px, centred on the region-4 mask centroid of each side (`np.rint`);
  - `fig_common_scale.png`: 2 tiles of 200 px, rows 76-275 and cols 111-310 at 400 px.
  - At smoke scale every tile and crop is divided by `scale`, with nearest-neighbour resampling where a factor is not
    an integer (README, Smoke run).
  - Each is checked to be at most `MAX_FIGURE_BYTES`.
- CLI: `--out-dir`, `--pairs` (default 8), `--scale` (default 1) and `--synthetic`. A smoke run (`--scale > 1`) must not
  write into the experiment directory. Prefix its printed lines with `SMOKE (code check only): ` and set
  `"smoke": true` in its output file, as 006 does.

## Outputs

- `results.json` (the real renders only) holds every number Results cites, under these headings:
  - parameters and mask sizes per side;
  - the replicate check;
  - per-configuration means ± sd of every key;
  - each comparison: p-values, Holm decisions, effect summaries, per-class maxima and `min_attainable_p`;
  - Δ per frame and class, D and D_jit with intervals, the cells, verdicts, readings and mechanism labels;
  - H4 and H5;
  - E1;
  - estimation blocks;
  - profiles;
  - figure encodings and crop bounds.
- `synthetic.json` (from `--synthetic` only): the prediction table, verdict counts, H4 and H5 counts, E1 per model and
  the gate. The analysis run reads nothing from it, and the synthetic run reads no render `sum`.
- Printed tables mirror the planned Results tables:
  - 0, parameters;
  - 1, noise keys per configuration and frame;
  - 2, H1-H3: R_px, R_ip, R_jit, D, D_jit, cell, verdict and reading;
  - 3, rejected keys by class;
  - 4, H4 and H5;
  - 5, E1;
  - 6, estimation;
  - 7, synthetic predictions, verdict counts and gate (synthetic run);
  - 8, distinct renders.

## Long runs

The synthetic run (about 85 CPU-min) and each full analysis run (about 10 CPU-min) exceed the 10-minute limit of a
foreground command. Run each detached (Bash `run_in_background`, stdout and stderr to a log file in the scratch
directory), wait for its completion notice, and read the exit status and the log. A non-zero exit or a timeout is a
failure to report, not a reason to rerun with other parameters. The outputs do not depend on the machine's load, but
the run time does: start the synthetic and full runs when no other CPU-bound job of the session is running, and record
`uptime` before each in the report.

## Disk

Nothing is rendered, so the cache does not grow. The outputs are at most about 15 MB in all: `results.json` and
`synthetic.json` (about 1 MB at most each), five figures of at most 1 MB, their scratch copies, the smoke outputs and
the logs. The README records the free space measured at pre-registration (4,059,512,832 B on 2026-10-15); it is not a
requirement.

## Order of work

0. Before any other step, run and record these three commands (from the repository root):

   ```
   sha256sum .cache/oracle-build/src/app/smallpaint_oracle
   PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python -m painterly_analysis.experiment run experiments/006-2026-10-09-jitter-units/jobs.py --budget 0
   PAINTERLY_CACHE=.cache/006-smoke-cache PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python -c "from pathlib import Path; from painterly_analysis import experiment as e; m = e.load_jobs_module(Path('experiments/006-2026-10-09-jitter-units/jobs.py')); jobs = [j for js in m.build_ensembles(2, 4).values() for j in js]; print(sum((e.cache_root() / e.job_key(j) / 'done').is_file() for j in jobs), len(jobs))"
   ```

   They must print `066bb5d4247c556ad5232bfc4fff75dc5f37089840b23f1ecc8fdd9cb518828a`, then `completed=256 remaining=0`
   (exit 0), then `64 64` (all three verified on 2026-10-15). Any other output means the oracle binary or a cache
   changed: stop and report. Do not run `make oracle`.
1. Write the library helpers and their tests. `make test` must pass.
2. Write `EXP/analyze.py`.
3. Smoke run. It renders nothing. Both commands must exit 0, with every verdict inconclusive (not powered):

   ```
   PAINTERLY_CACHE=.cache/006-smoke-cache PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python EXP/analyze.py --pairs 2 --scale 4 --out-dir <scratch>/smoke
   PAINTERLY_CACHE=.cache/006-smoke-cache PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python EXP/analyze.py --synthetic --pairs 2 --scale 4 --out-dir <scratch>/smoke-synthetic
   ```

4. Synthetic validation at full sides, detached (Long runs):
   `PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python EXP/analyze.py --synthetic --out-dir EXP`. It must exit 0.
   If it fails, stop and report the failing requirement with its numbers. Do not tune the rules, and do not rerun with
   another seed. Then repeat it into `--out-dir <scratch>/synthetic` (detached) and `cmp` the two `synthetic.json`
   files.
5. Full run, detached: `PAINTERLY_BUILD_DIR=.cache/oracle-build .venv/bin/python EXP/analyze.py` (into `EXP`). Then
   repeat it with `--out-dir <scratch>/full` (detached) and `cmp` `results.json` and every figure byte for byte.
6. Repeat the three commands of step 0. Their output must be identical to step 0's.
7. Results and Conclusion in `EXP/README.md`:
   - Results: tables of numbers, from `results.json` and `synthetic.json`.
   - Conclusion: starts with `DRAFT (Haiku) — pending Opus review.`, then each hypothesis with its verdict and the
     deciding numbers. Name the reading of every decided cell, not only the verdict word (cells 1 and 2 are both
     "supported"). Report a cell-4 verdict at (400, 800) only together with the (200, 400) cell of the same family
     (README, verdict table).
   - The Conclusion cell of the 007 row in `experiments/README.md`: a one-line summary of the verdicts.
8. Finish protocol (CLAUDE.md rule 7): run the acceptance checks below, `git add` only the files listed under Files,
   and commit once.

## Acceptance

- `ruff check` and `ruff format --check` are clean (line length 100) on `analyze.py`, `metrics.py`, `report.py`,
  `__init__.py` and the tests. `make test` passes.
- The design check passes: configurations, seeds, 16 distinct renders each, bitwise-equal frames at 400 px, measured
  regions 2-7.
- The synthetic validation passes, and its second run's `synthetic.json` is byte-identical. The full run exits 0, and
  its second run is byte-identical.
- Every figure is at most 1 MB.
- No render was made and the oracle was not rebuilt: the three commands of step 0 print the same before (step 0) and
  after (step 6).
- `README.md` keeps exactly the five sections `## Background`, `## Hypothesis`, `## Method`, `## Results` and
  `## Conclusion`, and Background, Hypothesis and Method are unchanged (`git diff` shows changes under Results and
  Conclusion only).
- Estimated CPU, measured at pre-registration (README, Estimated cost): about 85 minutes per synthetic run (two
  runs), about 10 minutes per full analysis run (two runs), and under 1 minute for each smoke command. No oracle
  time.
