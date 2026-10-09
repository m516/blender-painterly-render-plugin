# Experiments

Experiments are numbered and dated in the order they run. Each lives in `experiments/NNN-YYYY-MM-DD-slug/`.
The rules are in `CLAUDE.md`, section "Experiments".

## Index

| # | Date | Slug | Question | Status | Conclusion |
|---|------|------|----------|--------|------------|
| 001 | 2026-10-08 | oracle-reproduction | Does the compiled oracle reproduce the reference, and what doesn't matter? | final | Oracle reproduces the reference (means 18/18, texture ρ≈0.99); reference is effectively converged; loop order matters; per-thread restarts change texture slightly |
| 002 | 2026-10-08 | ingredient-ablation | Which smallpaint ingredients are necessary for the look? | draft | results pending |
| 003 | 2026-10-08 | lane-length | How long must a chain be? (artist-mode lane length) | draft | results pending |
| 004 | 2026-10-08 | resolution-dependence | Is the texture pixel-locked (lag-1 across 200/400/800 px, downsampling, jitter units)? | draft | not yet (pre-registration only; renders not run) |
| 005 | 2026-10-08 | native-coexistence | Do the native `_painterly` module and Blender 5.2.2's own Cycles coexist in one `blender -b` process, with no foreign bindings? | draft | H1 and H2 supported (exact selftest in Blender, 20/20 renders equal). H3 refuted: 4 violating bindings, all allocator symbols (`malloc`, `free`, `realloc`, `posix_memalign`) bound to Blender's bundled `libtbbmalloc_proxy.so.2`; coverage 249/249; controls 5 and 122 violations |

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
