import itertools, math, json
import numpy as np
rng = np.random.default_rng(0)
# exact two-sided permutation p for 8 v 8, vectorized over sims
n = 8
idx = np.array(list(itertools.combinations(range(2*n), n)))  # 12870 x 8
def exact_p(x, y):
    pooled = np.concatenate([x, y], axis=1)  # sims x 16
    total = pooled.sum(1, keepdims=True)
    sx = pooled[:, idx].sum(-1)  # sims x 12870
    stat = sx / n - (total - sx) / n
    obs = stat[:, :1]
    tol = 16 * np.finfo(float).eps * np.abs(pooled).max(1, keepdims=True)
    return (np.abs(stat) >= np.abs(obs) - tol).sum(1) / idx.shape[0]
# P(p <= thr) for shift d, equal sd
for thr_name, thr in [("first Holm 0.01/3/18", 0.01/3/18), ("first Holm 0.01/18", 0.01/18)]:
    out = []
    for d in [1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6]:
        sims = 2000
        x = rng.normal(d, 1, (sims, n)); y = rng.normal(0, 1, (sims, n))
        p = exact_p(x, y)
        out.append(f"d={d}: {np.mean(p <= thr):.3f}")
    print(thr_name, "; ".join(out))
