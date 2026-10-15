"""Planning only (review round 2): H1 pipeline with the revised reading rule and 99% intervals.

Model: normal per-pair values with 006's per-key means and sds at 400 and 800 px (pairs006.json),
keys independent; the 1600 px mean is m800 + q (m800 - m400) per key (truth I: q = 0, G: q = 1/4,
N: q = 1), with sd = sd800 or sd800 / 2. A, X and Y are computed from the simulated keys.
Test: exact 8-vs-8 two-sided permutation p-values over the 12,870 splits, Holm at 0.01 across
the 18 keys of T. Readings: bootstrap of pairs within each ensemble (indices shared by every
statistic of an ensemble), (0.5, 99.5) percentile intervals, B resamples (argv[3]).
Rule (README, H1, Reading rule): if the interval of s2 contains 0, N iff the intervals of s3 and
s3 - s2 lie on the same side of 0, otherwise "not separated"; else sigma is the side of s2's
interval, and I, G, "I or G", F, S, N as registered. A rejected key is read by its class if the
class's s2 interval excludes 0, otherwise by its own intervals.
usage: review5_h1.py SEED DRAWS B
"""

import itertools
import json
import sys
from pathlib import Path

import numpy as np

P = json.loads((Path(__file__).parent / "pairs006.json").read_text())
R = [2, 3, 4, 5, 6, 7]
T = [f"r{r}.{k}" for r in R for k in ("structure_std", "slag.x", "slag.y")]
CLS = {k: "A" if k.endswith("structure_std") else "X" if k.endswith("slag.x") else "Y" for k in T}
IDX = np.array(list(itertools.combinations(range(16), 8)))
PCT = (0.5, 99.5)
rng = np.random.default_rng(int(sys.argv[1]) if len(sys.argv) > 1 else 5)
SIMS = int(sys.argv[2]) if len(sys.argv) > 2 else 300
B = int(sys.argv[3]) if len(sys.argv) > 3 else 1000


def col(n, k):
    return np.array([p[k] for p in P[n]["scaled"]])


def exact_p(x, y):  # keys x 8 each
    pooled = np.concatenate([x, y], axis=1)
    total = pooled.sum(1, keepdims=True)
    sx = pooled[:, IDX].sum(-1)
    stat = sx / 8 - (total - sx) / 8
    tol = 16 * np.finfo(float).eps * np.abs(pooled).max(1, keepdims=True)
    return (np.abs(stat) >= np.abs(stat[:, :1]) - tol).sum(1) / IDX.shape[0]


def holm(p, alpha):
    order = np.argsort(p)
    m = len(p)
    rej = np.zeros(m, bool)
    for i, j in enumerate(order):
        if p[j] <= alpha / (m - i):
            rej[j] = True
        else:
            break
    return rej


def stats_of(x):  # x: 18 keys x n pairs -> dict of unit -> n values
    out = {k: x[i] for i, k in enumerate(T)}
    out["A"] = np.log(x[0::3]).mean(0)
    out["X"] = x[1::3].mean(0)
    out["Y"] = x[2::3].mean(0)
    return out


def ci(v):
    return np.percentile(v, PCT)


def contains(iv):
    return iv[0] <= 0 <= iv[1]


def above(iv):
    return iv[0] > 0


def below(iv):
    return iv[1] < 0


def reading(s2, s3, s3g, s3s2):
    if contains(s2):
        if (above(s3) and above(s3s2)) or (below(s3) and below(s3s2)):
            return "N"
        return "not separated"
    side, opp = (above, below) if above(s2) else (below, above)
    c3, cg = contains(s3), contains(s3g)
    if c3 and not cg:
        return "I"
    if not c3 and cg:
        return "G"
    if c3 and cg:
        return "I or G"
    if side(s3) and opp(s3g):
        return "F"
    if side(s3) and side(s3g) and opp(s3s2):
        return "S"
    return "N"


def decision(rej, rd_key):
    if not rej.any():
        return "supported"
    reads = {rd_key[T[i]] for i in np.flatnonzero(rej)}
    if reads & {"N", "S", "I"}:
        return "refuted"
    if reads <= {"G", "F"}:
        return "partial(G)"
    return "inconclusive"


for fam in ("row_j0_s", "row_s"):
    m4 = np.array([col(fam + "400", k).mean() for k in T])
    s4 = np.array([col(fam + "400", k).std(ddof=1) for k in T])
    m8 = np.array([col(fam + "800", k).mean() for k in T])
    s8 = np.array([col(fam + "800", k).std(ddof=1) for k in T])
    for truth, q in (("I", 0.0), ("G", 0.25), ("N", 1.0)):
        for sdf in (1.0, 0.5):
            dec, cond, cls_read = {}, {}, {}
            for _ in range(SIMS):
                x4 = rng.normal(m4[:, None], s4[:, None], (18, 8))
                x8 = rng.normal(m8[:, None], s8[:, None], (18, 8))
                x16 = rng.normal((m8 + q * (m8 - m4))[:, None], (s8 * sdf)[:, None], (18, 8))
                rej = holm(exact_p(x8, x16), 0.01)
                u4, u8, u16 = stats_of(x4), stats_of(x8), stats_of(x16)
                i4, i8, i16 = (rng.integers(0, 8, (B, 8)) for _ in range(3))
                rd, s2ci = {}, {}
                for u in [*T, "A", "X", "Y"]:
                    b4, b8, b16 = u4[u][i4].mean(1), u8[u][i8].mean(1), u16[u][i16].mean(1)
                    s2, s3 = b8 - b4, b16 - b8
                    s2ci[u] = ci(s2)
                    rd[u] = reading(s2ci[u], ci(s3), ci(s3 - s2 / 4), ci(s3 - s2))
                for c in "AXY":
                    cls_read[(c, rd[c])] = cls_read.get((c, rd[c]), 0) + 1
                rd_key = {k: rd[CLS[k]] if not contains(s2ci[CLS[k]]) else rd[k] for k in T}
                d = decision(rej, rd_key)
                dec[d] = dec.get(d, 0) + 1
                for i in np.flatnonzero(rej):
                    key = (CLS[T[i]], rd_key[T[i]])
                    cond[key] = cond.get(key, 0) + 1
            print(
                fam, "truth", truth, "sd1600/sd800", sdf,
                {k: round(v / SIMS, 3) for k, v in sorted(dec.items())},
                "| class readings:",
                {f"{c}:{r}": round(v / SIMS, 3) for (c, r), v in sorted(cls_read.items())},
                "| rejected-key readings:", {f"{c}:{r}": v for (c, r), v in sorted(cond.items())},
                flush=True,
            )
