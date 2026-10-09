# Experiments

Experiments are numbered and dated in the order they run. Each lives in `experiments/NNN-YYYY-MM-DD-slug/`.
The rules are in `CLAUDE.md`, section "Experiments".

## Index

| # | Date | Slug | Question | Status | Conclusion |
|---|------|------|----------|--------|------------|
| 001 | 2026-10-08 | oracle-reproduction | Does the compiled oracle reproduce the reference, and what doesn't matter? | final | Oracle reproduces the reference (means 18/18, texture ρ≈0.99); reference is effectively converged; loop order matters; per-thread restarts change texture slightly |
| 002 | 2026-10-08 | ingredient-ablation | Which smallpaint ingredients are necessary for the look? | draft | H1-H4 supported (back wall needs ghosts and unnormalized bounce; spiral and chaining needed for texture; alpha monotone; stop-at-emitter changes means and texture); H5 distinguishable (lights-only ghosting: 45 of 46 keys, back wall 191.5 vs 144.4, pattern_corr 0.005 vs 0.589) |
| 003 | 2026-10-08 | lane-length | How long must a chain be? (artist-mode lane length) | draft | H1 supported (all.pattern_corr rises at 7 of 7 steps, p_greater 7.77e-05 each); H2 refuted (L* = none: all 8 lane lengths Holm-rejected vs row); H3 supported (0 of 46 keys rejected, min_attainable_p 1.55e-04) |
| 004 | 2026-10-08 | resolution-dependence | Is the texture pixel-locked (lag-1 across 200/400/800 px, downsampling, jitter units)? | draft | H1 refuted (H1a: 3, 12 and 12 of 12 noise-corrected lag-1 keys rejected for 200/400, 400/800, 200/800 px; H1b one-sided: 12 greater, 0 less); H1d refuted (row chain: 2, 11, 11 of 12); H2 supported (jitter 1/700 vs 1/1400 at 800 px: 23 of 30 keys) |
| 005 | 2026-10-08 | native-coexistence | Do the native `_painterly` module and Blender 5.2.2's own Cycles coexist in one `blender -b` process, with no foreign bindings? | final | Linux: coexists (H1, H2 supported); H3 refuted as registered by 4 allocator bindings to Blender's process-wide TBB malloc proxy, shared coherently with libc; G1 not triggered on Linux, open for macOS/Windows until CI |
| 006 | 2026-10-09 | jitter-units | Which jitter unit (image-plane or pixel) makes the look independent of resolution, measured with scale-equivariant metrics? | draft | pre-registered; renders running |

## How to run

Experiments use their own oracle, built into `.cache/oracle-build`. `make clean` does not touch that directory, so the
renders in `.cache/renders` stay valid. Build it with `make oracle`, and again after any change to the oracle source:

```
make oracle
```

An experiment declares its renders in `experiments/NNN-…/jobs.py` as `JOBS: list[Job]`, where `Job` comes from
`painterly_analysis.experiment`. For example, eight pairs of renders:

```python
from painterly_analysis.experiment import ensemble_jobs

JOBS = ensemble_jobs("positive", 8, chain="image", size=400, passes=64)
```

Renders are cached in `.cache/renders/<key>/` (or `$PAINTERLY_CACHE/renders/`), so a run can stop and resume. Run the
command below, and repeat it until its exit code is 0. Exit code 3 means jobs remain, and it is not an error.

```
PAINTERLY_BUILD_DIR=.cache/oracle-build python -m painterly_analysis.experiment run experiments/NNN-…/jobs.py --budget 540
```

Run it from the repository root with the project environment active (`make env`), or with `.venv/bin/python` in place of
`python`. `PAINTERLY_BUILD_DIR=.cache/oracle-build` makes the run use the experiment oracle. The budget is in seconds. No
new job starts after it has elapsed, so one command stays near nine minutes. The command prints `completed=… remaining=…`.

Cache keys include the oracle binary's sha256 (`job_key` in `analysis/painterly_analysis/experiment.py`). A deterministic
rebuild of the same source gives the same keys, which was verified when an M2 `make clean` interrupted the 002–004
renders.

## Layout rules

Each experiment directory has a `README.md` with exactly these sections: `## Background`, `## Hypothesis`,
`## Method`, `## Results`, `## Conclusion`. Scripts, `results.json` and PNG previews of at most 1 MB sit beside it.
Large outputs go to `out/`, which git ignores. Every experiment is listed in the index above.
