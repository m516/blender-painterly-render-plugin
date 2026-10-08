## Experiment protocol (applies to every experiment card)
1. **Number and date.** `NNN` = 1 + the highest number already in `experiments/`, starting at 001. Use three digits. `DATE=$(date +%F)`.
   The directory is `experiments/NNN-DATE-<slug>/`.
2. **Pre-register** before running anything. Write `README.md` with `## Background`, `## Hypothesis` and `## Method`:
   - Background cites `docs/plan.md` "What makes the look" and any earlier experiment it builds on.
   - Each hypothesis is numbered (H1, H2, …). It states *how it was derived*, the observable, and the exact statistical decision rule (test, α, correction).
   - Method lists the exact job configurations, the commands, and the analysis.
3. **`jobs.py`** declares `JOBS` with `painterly_analysis.experiment.ensemble_jobs(...)`.
   - Reuse identical option sets across experiments; the cache shares them.
4. **Render.** Run `.venv/bin/python -m painterly_analysis.experiment run experiments/NNN-…/jobs.py --budget 540` repeatedly until it exits 0. Each call stays under 10 minutes.
5. **`analyze.py`** loads the cache and computes the metrics and tests with `painterly_analysis`. It writes:
   - `results.json` (machine-readable: every number in the Results section);
   - `fig_*.png`: small previews, ≤ 1 MB each, made with `io.write_png`;
   - the printed result tables.
   It must be re-runnable and deterministic.
6. **`## Results`.** Tables of numbers (means ± sd, p-values, Holm decisions). No adjectives without numbers.
7. **`## Conclusion`.** Start with the line `DRAFT (Haiku) — pending Opus review.`, then for each hypothesis: supported / refuted / inconclusive, with the deciding numbers. Opus finalizes it.
8. **Index.** Add a row to `experiments/README.md` with status `draft`.
9. **Commit** README.md, jobs.py, analyze.py, results.json and the figures. Never commit `.cache/`.
