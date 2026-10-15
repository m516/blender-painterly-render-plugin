"""Planning only (review round 2): H2 with the revised conditions and 99% intervals, and the
f = 1/400 footprint of H3 that follows from it.

Model, keys independent and normal (006's per-pair values, pairs006.json):
- f = 1/400, H2 set (16 v 16) and H3 fresh set (16 v 16): 800 px sd = row_s800 sd x g^1.807,
  200 px sd = row_s200_px (f = 1/700) sd x g^0.807, g = 1.12 (median sd growth per doubling of f)
  or 1.41 (upper quartile); 200 - 800 px departure Delta_400 = TRUTH x Delta_1400 per key;
- f = 1/1400 reference, fresh set (32 v 32): row_s200 and row_s800 sds, departure Delta_1400 =
  SHRINK x 006's per-key departure.
A, X and Y are computed from the simulated keys.
H2: Holm at 0.01 across the 18 keys (Monte Carlo permutation p); per Z in (A, r4.slag.x), with
(0.5, 99.5) percentile intervals: removed = Delta_400 contains 0 and shift; reduced = Delta_400
on Delta_1400's side and shift; reversed = Delta_400 on the opposite side; shift = the interval of
Delta_400 - Delta_1400 lies on the opposite side of 0 from the point estimate of Delta_1400.
H3 at 1/400: "no departure" iff H2 reads supported (removed); otherwise D_400 = H2's rejected keys
plus each of A, X, Y, r4.slag.x whose Delta_400 interval (H2 set) excludes 0; empty -> "not
located"; else the classes on the fresh 1/400 set with chain share CHI (sub mean = 800 px mean +
(1 - CHI) Delta_400), departure family at 0.01/6, outside family (the units not in D_400) at
0.01/6; "no departure": all 21 units at 0.01/3 as the outside family.
usage: review5_h2.py SEED DRAWS
"""

import json
import sys
from pathlib import Path

import numpy as np

P = json.loads((Path(__file__).parent / "pairs006.json").read_text())
R = [2, 3, 4, 5, 6, 7]
T = [f"r{r}.{k}" for r in R for k in ("structure_std", "slag.x", "slag.y")]
UNITS = [*T, "A", "X", "Y"]
ZS = ("A", "r4.slag.x")
LOCATE = ("A", "X", "Y", "r4.slag.x")
PCT = (0.5, 99.5)
NPERM = 20_000
B = 2000
rng = np.random.default_rng(int(sys.argv[1]))
SIMS = int(sys.argv[2])


def col(n, k):
    return np.array([p[k] for p in P[n]["scaled"]])


def units_of(x):
    a = np.log(x[..., 0::3]).mean(-1, keepdims=True)
    return np.concatenate([x, a, x[..., 1::3].mean(-1, keepdims=True),
                           x[..., 2::3].mean(-1, keepdims=True)], axis=-1)


def perm_p(x, y, perms):
    n = x.shape[0]
    pooled = np.concatenate([x, y], 0)
    total = pooled.sum(0)
    sx = pooled[perms].sum(1)
    stat = sx / n - (total - sx) / n
    obs = x.mean(0) - y.mean(0)
    tol = 16 * np.finfo(float).eps * np.abs(pooled).max(0)
    return ((np.abs(stat) >= np.abs(obs) - tol).sum(0) + 1) / (perms.shape[0] + 1)


def holm(p, alpha):
    order = np.argsort(p)
    rej = np.zeros(len(p), bool)
    for i, j in enumerate(order):
        if p[j] <= alpha / (len(p) - i):
            rej[j] = True
        else:
            break
    return rej


def boot(x, b=B):
    return x[rng.integers(0, x.shape[0], (b, x.shape[0]))].mean(1)


m8 = np.array([col("row_s800", k).mean() for k in T])
s8 = np.array([col("row_s800", k).std(ddof=1) for k in T])
s2 = np.array([col("row_s200", k).std(ddof=1) for k in T])
s2px = np.array([col("row_s200_px", k).std(ddof=1) for k in T])
d006 = np.array([col("row_s200", k).mean() - col("row_s800", k).mean() for k in T])
perm16 = np.argsort(rng.random((NPERM, 32)), 1)[:, :16]


def sim(truth, g, shrink, chi):
    d14 = shrink * d006
    d4 = truth * d14
    sd2, sd8 = s2px * g**0.807, s8 * g**1.807
    out = {}
    for _ in range(SIMS):
        y2 = units_of(rng.normal(m8 + d4, sd2, (16, 18)))
        y8 = units_of(rng.normal(m8, sd8, (16, 18)))
        r2 = units_of(rng.normal(m8 + d14, s2, (32, 18)))
        r8 = units_of(rng.normal(m8, s8, (32, 18)))
        rej = holm(perm_p(y2[:, :18], y8[:, :18], perm16), 0.01)
        b4 = boot(y2) - boot(y8)
        b14 = boot(r2) - boot(r8)
        lo4, hi4 = np.percentile(b4, PCT, axis=0)
        los, his = np.percentile(b4 - b14, PCT, axis=0)
        p14 = r2.mean(0) - r8.mean(0)
        state = {}
        for z in ZS:
            u = UNITS.index(z)
            sgn = np.sign(p14[u]) or 1.0
            shift = (los[u] > 0) if sgn < 0 else (his[u] < 0)
            on_side = (lo4[u] > 0) if sgn > 0 else (hi4[u] < 0)
            opposite = (hi4[u] < 0) if sgn > 0 else (lo4[u] > 0)
            nodep = lo4[u] <= 0 <= hi4[u]
            state[z] = ("removed" if nodep and shift else "reduced" if on_side and shift
                        else "reversed" if opposite else "none")
        if rej.any():
            h2 = "refuted"
        elif all(s == "removed" for s in state.values()):
            h2 = "supported"
        elif all(s in ("removed", "reduced") for s in state.values()):
            h2 = "reduced"
        elif any(s == "reversed" for s in state.values()):
            h2 = "reversed"
        else:
            h2 = "not shown"
        # H3 at f = 1/400
        if h2 == "supported":
            d400 = []
        else:
            located = {z for z in LOCATE if not lo4[UNITS.index(z)] <= 0 <= hi4[UNITS.index(z)]}
            d400 = sorted({T[i] for i in np.flatnonzero(rej)} | located)
        if h2 != "supported" and not d400:
            h3 = "not located"
        else:
            z1 = rng.normal(size=(16, 18))
            n2 = units_of(rng.normal(m8 + d4, sd2, (16, 18)))
            n8 = units_of(m8 + sd8 * z1)
            sb = units_of(rng.normal(m8 + (1 - chi) * d4, sd2, (16, 18)))
            p = perm_p(n2, sb, perm16)
            if not d400:
                h3 = "no departure" + ("+flag" if holm(p, 0.01 / 3).any() else "")
            else:
                di = [UNITS.index(u) for u in d400]
                oi = [i for i, u in enumerate(UNITS) if u not in d400]
                rej3 = holm(p[di], 0.01 / 6).any()
                flag = bool(oi) and holm(p[oi], 0.01 / 6).any()
                i = rng.integers(0, 16, (B, 16))
                j = rng.integers(0, 16, (B, 16))
                ratio = (n2[i].mean(1)[:, di] - sb[j].mean(1)[:, di]) / (
                    n2[i].mean(1)[:, di] - n8[j].mean(1)[:, di])
                lo, hi = np.percentile(np.median(ratio, 1), PCT)
                if rej3:
                    h3 = "chain" if lo > 0.5 else "mixed" if hi < 0.5 else "unresolved"
                else:
                    h3 = "undersampling" if hi < 0.5 else "inconclusive"
                h3 += "+flag" if flag else ""
        key = f"H2 {h2} / H3 {h3}"
        out[key] = out.get(key, 0) + 1
    return out


for g, glab in ((1.12, "median"), (1.41, "q75")):
    for shrink in (1.0, 0.5):
        for truth, tlab in ((0.0, "removed"), (0.5, "halved"), (1.0, "unchanged"),
                            (-1.5, "reversed x1.5")):
            for chi in ((0.0, 0.5, 1.0) if truth == 1.0 else (0.0,)):
                out = sim(truth, g, shrink, chi)
                h2 = {}
                for k, v in out.items():
                    h2[k.split(" / ")[0]] = h2.get(k.split(" / ")[0], 0) + v
                print(f"growth {glab}, Delta_1400 x{shrink}, Delta_400 {tlab}, chi_400 {chi}:",
                      {k: round(v / SIMS, 3) for k, v in sorted(h2.items())}, "|",
                      {k: round(v / SIMS, 3) for k, v in sorted(out.items())}, flush=True)
