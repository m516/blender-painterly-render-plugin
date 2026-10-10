# Experiments

Experiments are numbered and dated in the order they run. Each lives in `experiments/NNN-YYYY-MM-DD-slug/`.
The rules are in `CLAUDE.md`, section "Experiments".

## Index

| # | Date | Slug | Question | Status | Conclusion |
|---|------|------|----------|--------|------------|
| 001 | 2026-10-08 | oracle-reproduction | Does the compiled oracle reproduce the reference, and what doesn't matter? | final | Oracle reproduces the reference (means 18/18, texture ρ≈0.99); reference is effectively converged; loop order matters; per-thread restarts change texture slightly |
| 002 | 2026-10-08 | ingredient-ablation | Which smallpaint ingredients are necessary for the look? | final | All necessary: ghosts+unnormalized bounce light the back wall (144 vs 13/5.5); lockstep u1=u2 is the texture (amplitude 5.74→0.02); alpha nonlinear stylization knob; emitter continuation consumes 11 of 16 draws (stopping: +73% amplitude); lights-only ghosting is a distinct Blender look (back wall +33%, realization lost) → parity on realization-free keys |
| 003 | 2026-10-08 | lane-length | How long must a chain be? (artist-mode lane length) | final | row ≡ image (0/46 keys) → `chain=row` default; fidelity rises with L (0.13…0.57 at L=1…128 vs 0.59) but no lane matches row; lanes are a stroke-shape knob (anisotropy, seam columns) |
| 004 | 2026-10-08 | resolution-dependence | Is the texture pixel-locked (lag-1 across 200/400/800 px, downsampling, jitter units)? | final | H1/H1d refuted, H2 supported (jitter units matter), but fixed-pixel filters cannot separate pixel- from image-locking; region-mean trend is an erosion artefact; question answered by 006 |
| 005 | 2026-10-08 | native-coexistence | Do the native `_painterly` module and Blender 5.2.2's own Cycles coexist in one `blender -b` process, with no foreign bindings? | final | Linux: coexists (H1, H2 supported); H3 refuted as registered by 4 allocator bindings to Blender's process-wide TBB malloc proxy, shared coherently with libc; G1 not triggered on Linux; later CI runs (2026-10-10): coexists on Linux, macOS and Windows (20/20 each, Linux trace 0 violations under the coherence rule), G1 not triggered on any OS |
| 006 | 2026-10-09 | jitter-units | Which jitter unit (image-plane or pixel) makes the look independent of resolution, measured with scale-equivariant metrics? | final | Image-plane jitter: 400 ≡ 800 px on all 18 texture keys (both chains, also with zero jitter); pixel jitter changes 9 of 18; every H1/H4 rejection involves 200 px; H3 Δ 0.051 vs 0.158 confirms SPEC §7 (jitter = 1/1400 of the fitted side); the jitter footprint softens strokes (zero jitter: structure +34%) without locking them |

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
