"""Planning only (review round 1): H3 classification on fresh blocks, simulated.

Model per key i of D_f, n fresh pairs per side, normal per-pair values:
- native 800 px: mean m800_i (006), sd s800_i (006);
- native 200 px: mean m800_i + Delta_i, sd s200_i (006);
- sub 200 <- 800 px: mean m800_i + (1 - chi) Delta_i, sd s200_i (assumption: the native 200 px sd), and
  correlation rho with the same render's native 800 px value (unknown; 0 and 0.5 are tried).
Delta_i is 006's departure (an upper bound if 006's selection inflated it; a "shrunk" run halves it).
Test: two-sided permutation p, native 200 vs sub, Holm across D_f at ALPHA (argv[2]: 0.01/argv[2]),
Monte Carlo permutations. chi = median_i of c_i / Delta_i, 95% percentile bootstrap, pairs resampled within each
ensemble, a render's sub and native 800 px values sharing their index.
"""

import json
import sys
from pathlib import Path

import numpy as np

P = json.loads((Path(__file__).parent / "pairs006.json").read_text())
D0 = ["r2.slag.y", "r3.structure_std", "r4.structure_std", "r5.structure_std",
      "r6.structure_std", "r6.slag.y", "r7.structure_std"]
D1400 = ["r4.slag.x"]
SIMS = int(sys.argv[1]) if len(sys.argv) > 1 else 300
# per-footprint level of the D_f family: 0.01/3 (first draft) or 0.01/6 (revised: the footprint's
# 0.01/3 split between D_f and the keys outside it)
ALPHA = 0.01 / float(sys.argv[2]) if len(sys.argv) > 2 else 0.01 / 3
FINAL = len(sys.argv) > 3 and sys.argv[3] == "final"
N_PERM = 10_000
B = 1000
rng = np.random.default_rng(7)


def col(name, key):
    return np.array([p[key] for p in P[name]["scaled"]])


def holm_any(p, alpha):
    ps = np.sort(p)
    return bool(ps[0] <= alpha / len(ps))


def perm_p(x, y, perms):
    # x, y: n x k; perms: N x 2n indices of the first group
    n = x.shape[0]
    pooled = np.concatenate([x, y], axis=0)  # 2n x k
    total = pooled.sum(0)
    sx = pooled[perms].sum(1)  # N x k
    stat = sx / n - (total - sx) / n
    obs = x.mean(0) - y.mean(0)
    k = (np.abs(stat) >= np.abs(obs)).sum(0)
    return (k + 1) / (perms.shape[0] + 1)


def simulate(keys, n200, n800, n, chi, rho, shrink):
    m8 = np.array([col(n800, k).mean() for k in keys])
    s8 = np.array([col(n800, k).std(ddof=1) for k in keys])
    s2 = np.array([col(n200, k).std(ddof=1) for k in keys])
    delta = shrink * np.array([col(n200, k).mean() - col(n800, k).mean() for k in keys])
    perms = np.argsort(rng.random((N_PERM, 2 * n)), axis=1)[:, :n]
    counts = {}
    for _ in range(SIMS):
        nat2 = rng.normal(m8 + delta, s2, (n, len(keys)))
        z1 = rng.normal(size=(n, len(keys)))
        z2 = rng.normal(size=(n, len(keys)))
        nat8 = m8 + s8 * z1
        sub = m8 + (1 - chi) * delta + s2 * (rho * z1 + np.sqrt(1 - rho**2) * z2)
        rejected = holm_any(perm_p(nat2, sub, perms), ALPHA)
        i = rng.integers(0, n, (B, n))
        j = rng.integers(0, n, (B, n))
        mn2 = nat2[i].mean(1)
        msub = sub[j].mean(1)
        mn8 = nat8[j].mean(1)
        ratio = (mn2 - msub) / (mn2 - mn8)
        chis = np.median(ratio, axis=1)
        lo, hi = np.percentile(chis, [2.5, 97.5])
        if rejected:
            c = "chain" if lo > 0.5 else "mixed" if hi < 0.5 else "unresolved"
        else:
            c = "undersampling" if hi < 0.5 else "inconclusive"
        counts[c] = counts.get(c, 0) + 1
    return {k: round(v / SIMS, 3) for k, v in sorted(counts.items())}


DESIGNS = (
    ("f=1/1400 D={r4.slag.x}", D1400, "row_s200", "row_s800", (32,) if FINAL else (16, 24, 32)),
    ("f=0 D_0 (7 keys)", D0, "row_j0_s200", "row_j0_s800", (16,) if FINAL else (8, 16)),
)
for label, keys, n200, n800, ns in DESIGNS:
    for n in ns:
        for shrink in (1.0, 0.5):
            for rho in (0.0, 0.5):
                for chi in (0.0, 0.25, 0.5, 0.6, 0.75, 1.0):
                    if FINAL and rho == 0.5:
                        continue
                    r = simulate(keys, n200, n800, n, chi, rho, shrink)
                    print(f"{label} n={n} Delta x{shrink} rho={rho} chi={chi}: {r}", flush=True)
