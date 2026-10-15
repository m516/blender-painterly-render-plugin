"""Planning only: power of the two-sided permutation test, n vs n pairs, at a Holm first threshold.

Monte Carlo permutation p-values as in ensemble.permutation_pvalue ((k + 1) / (N + 1)), normal data
with equal sd, shift d in sd units.
"""
import numpy as np

rng = np.random.default_rng(0)
N_PERM = 20_000
SIMS = 300


def power(n, d, thr):
    hits = 0
    perms = np.argsort(rng.random((N_PERM, 2 * n)), axis=1)[:, :n]
    for _ in range(SIMS):
        x = rng.normal(d, 1.0, n)
        y = rng.normal(0.0, 1.0, n)
        pooled = np.concatenate([x, y])
        total = pooled.sum()
        sx = pooled[perms].sum(axis=1)
        stat = sx / n - (total - sx) / n
        obs = x.mean() - y.mean()
        k = np.count_nonzero(np.abs(stat) >= abs(obs))
        p = (k + 1) / (N_PERM + 1)
        hits += p <= thr
    return hits / SIMS


for thr_name, thr in (("0.01/3/18", 0.01 / 3 / 18), ("0.01/18", 0.01 / 18)):
    for n in (12, 16, 24):
        row = [f"d={d}: {power(n, d, thr):.2f}" for d in (1.0, 1.25, 1.5, 1.78, 2.0, 2.45, 3.0)]
        print(thr_name, f"n={n}", "; ".join(row), flush=True)
