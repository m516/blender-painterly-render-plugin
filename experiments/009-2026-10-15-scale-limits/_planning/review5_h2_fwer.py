"""Planning only (review round 2): family-wise error of H2's Holm test (18 keys, 16 v 16, 0.01)
when the footprint removes the departure, with the stand-in sds of H2 Power (unequal at 200 and
800 px), against equal sds. Monte Carlo permutation p over 20,000 permutations; 2,000 draws."""
import json
from pathlib import Path

import numpy as np

P = json.loads((Path(__file__).parent / "pairs006.json").read_text())
R = [2, 3, 4, 5, 6, 7]
T = [f"r{r}.{k}" for r in R for k in ("structure_std", "slag.x", "slag.y")]
rng = np.random.default_rng(23)


def col(n, k):
    return np.array([p[k] for p in P[n]["scaled"]])


s8 = np.array([col("row_s800", k).std(ddof=1) for k in T])
s2px = np.array([col("row_s200_px", k).std(ddof=1) for k in T])
perms = np.argsort(rng.random((20_000, 32)), 1)[:, :16]


def holm_any(p, alpha):
    ps = np.sort(p)
    return any(ps[i] <= alpha / (len(ps) - i) for i in range(1))


for label, sd2, sd8 in (("stand-in sds, median growth", s2px * 1.12**0.807, s8 * 1.12**1.807),
                        ("stand-in sds, q75 growth", s2px * 1.41**0.807, s8 * 1.41**1.807),
                        ("equal sds", s8, s8)):
    hits, per_key = 0, np.zeros(18)
    for _ in range(2000):
        x = rng.normal(0, sd2, (16, 18))
        y = rng.normal(0, sd8, (16, 18))
        pooled = np.concatenate([x, y], 0)
        sx = pooled[perms].sum(1)
        stat = sx / 16 - (pooled.sum(0) - sx) / 16
        obs = x.mean(0) - y.mean(0)
        p = ((np.abs(stat) >= np.abs(obs)).sum(0) + 1) / (perms.shape[0] + 1)
        hits += holm_any(p, 0.01)
        per_key += p <= 0.01 / 18
    print(f"{label}: P(Holm rejects >= 1 of 18) {hits / 2000:.4f}; mean per-key rate at 0.01/18 "
          f"{per_key.mean() / 2000:.5f} (nominal {0.01 / 18:.5f}); sd ratio range "
          f"{(sd2 / sd8).min():.2f}-{(sd2 / sd8).max():.2f}", flush=True)
