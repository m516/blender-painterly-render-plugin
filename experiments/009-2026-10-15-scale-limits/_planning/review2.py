"""Planning only (review round 1): H1 simulations from 006's per-pair means and sds.

Normal data per key with 006's 8-pair means and sds; exact 8 v 8 two-sided permutation p-values
(all C(16, 8) splits), Holm across the 18 T keys.
"""

import itertools
import json
from pathlib import Path

import numpy as np

P = json.loads((Path(__file__).parent / "pairs006.json").read_text())
REGIONS = [2, 3, 4, 5, 6, 7]
T = [f"r{r}.{k}" for r in REGIONS for k in ("structure_std", "slag.x", "slag.y")]
IDX = np.array(list(itertools.combinations(range(16), 8)))


def col(name, key):
    return np.array([p[key] for p in P[name]["scaled"]])


def exact_p(x, y):  # x, y: keys x 8
    pooled = np.concatenate([x, y], axis=1)
    total = pooled.sum(1, keepdims=True)
    sx = pooled[:, IDX].sum(-1)
    stat = sx / 8 - (total - sx) / 8
    tol = 16 * np.finfo(float).eps * np.abs(pooled).max(1, keepdims=True)
    return (np.abs(stat) >= np.abs(stat[:, :1]) - tol).sum(1) / IDX.shape[0]


def n_holm(p, alpha):
    ps = np.sort(p)
    thr = alpha / (len(ps) - np.arange(len(ps)))
    ok = ps <= thr
    return len(ps) if ok.all() else int(np.argmin(ok))


rng = np.random.default_rng(3)
SIMS = 400
for fam in ("row_s", "row_j0_s"):
    m4 = np.array([col(fam + "400", k).mean() for k in T])
    s4 = np.array([col(fam + "400", k).std(ddof=1) for k in T])
    m8 = np.array([col(fam + "800", k).mean() for k in T])
    s8 = np.array([col(fam + "800", k).std(ddof=1) for k in T])
    for label, q in (("no change above 800 (mu1600 = mu800)", 0.0), ("G: step 800->1600 = step 400->800 / 4", 0.25)):
        for sdf in (1.0, 0.5):
            m16 = m8 + q * (m8 - m4)
            s16 = s8 * sdf
            r_bc = {a: 0 for a in ("0.01/3", "0.01")}
            r_c = 0
            for _ in range(SIMS):
                x4 = rng.normal(m4, s4, (8, 18)).T
                x8 = rng.normal(m8, s8, (8, 18)).T
                x16 = rng.normal(m16, s16, (8, 18)).T
                pb = exact_p(x8, x16)
                pc = exact_p(x4, x16)
                r_bc["0.01/3"] += n_holm(pb, 0.01 / 3) > 0
                r_bc["0.01"] += n_holm(pb, 0.01) > 0
                r_c += n_holm(pc, 0.01 / 3) > 0
            print(f"{fam:9s} {label}, sd1600 = {sdf} sd800: P(>=1 rej) (800,1600) at 0.01/3 "
                  f"{r_bc['0.01/3'] / SIMS:.2f}, at 0.01 {r_bc['0.01'] / SIMS:.2f}; "
                  f"(400,1600) at 0.01/3 {r_c / SIMS:.2f}", flush=True)

# exact 8 v 8 power for a single key at the first Holm thresholds 0.01/18 and 0.01/3/18
for d in (1.4, 1.55, 1.7, 2.0, 2.5, 3.0, 3.1, 3.5, 4.0):
    x = rng.normal(d, 1, (2000, 8))
    y = rng.normal(0, 1, (2000, 8))
    p = exact_p(x, y)
    print(f"8v8 d={d}: P(p<=5.56e-4) {np.mean(p <= 0.01 / 18):.2f}, P(p<=1.85e-4) {np.mean(p <= 0.01 / 54):.2f}")
