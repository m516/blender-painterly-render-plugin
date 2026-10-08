# Experiments

Experiments are numbered and dated in the order they run. Each lives in `experiments/NNN-YYYY-MM-DD-slug/`.
The rules are in `CLAUDE.md`, section "Experiments".

## Index

| # | Date | Slug | Question | Status | Conclusion |
|---|------|------|----------|--------|------------|

No experiments yet.

## How to run

An experiment declares its renders in `experiments/NNN-…/jobs.py` as `JOBS: list[Job]`, where `Job` comes from
`painterly_analysis.experiment`. For example, eight pairs of renders:

```python
from painterly_analysis.experiment import ensemble_jobs

JOBS = ensemble_jobs("positive", 8, chain="image", size=400, passes=64)
```

Renders are cached in `.cache/renders/<key>/` (or `$PAINTERLY_CACHE/renders/`), so
a run can stop and resume. Run the command below, and repeat it until its exit code is 0. Exit code 3 means jobs
remain, and it is not an error.

```
python -m painterly_analysis.experiment run experiments/NNN-…/jobs.py --budget 540
```

Run it from the repository root with the project environment active (`make env`), or with `.venv/bin/python` in
place of `python`. The budget is in seconds. No new job starts after it has elapsed, so one command stays near nine
minutes. The command prints `completed=… remaining=…`.

## Layout rules

Each experiment directory has a `README.md` with exactly these sections: `## Background`, `## Hypothesis`,
`## Method`, `## Results`, `## Conclusion`. Scripts, `results.json` and PNG previews of at most 1 MB sit beside it.
Large outputs go to `out/`, which git ignores. Every experiment is listed in the index above.
