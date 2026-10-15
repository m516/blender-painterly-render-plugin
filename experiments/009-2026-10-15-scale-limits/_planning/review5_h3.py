"""Planning only (review round 2): H3 classes at f = 0 and 1/1400 with the unit departure sets.

Model (fresh set, n pairs per side), keys independent and normal, from 006's per-pair values:
- native 800 px key i: N(m800_i, s800_i);
- native 200 px: N(m800_i + Delta_i, s200_i);
- sub 200 <- 800 px: N(m800_i + Delta_i - c_i, s200_i) (the native 200 px sd: same pixel count
  and passes), independent of the same render's native 800 px value (rho = 0), or correlated with
  it (rho, argv[4]);
- Delta_i is 006's 200 - 800 px departure (times SHRINK); c_i = chi_i Delta_i, the truth of a cell.
A, X and Y are computed from the simulated keys (A the mean log structure_std).
Departure family: the units of D_f (review5_select.py, 99%), Holm at 0.01/6; outside family: the
units not in D_f, Holm at 0.01/6. Monte Carlo permutation p, (k + 1) / (N + 1), N = NPERM.
chi: median over D_f of c_u / Delta_u, bootstrap of pairs within each ensemble (a render's sub and
native 800 px values share their index), (0.5, 99.5) percentile interval, B resamples; resamples
with some Delta_u exactly 0 are dropped (none occur with continuous data).
usage: review5_h3.py SEED DRAWS MODE [RHO]
"""

import json
import sys
from pathlib import Path

import numpy as np

P = json.loads((Path(__file__).parent / "pairs006.json").read_text())
R = [2, 3, 4, 5, 6, 7]
T = [f"r{r}.{k}" for r in R for k in ("structure_std", "slag.x", "slag.y")]
UNITS = [*T, "A", "X", "Y"]
D0 = ["r2.slag.x", "r2.slag.y", "r3.structure_std", "r3.slag.x", "r4.structure_std",
      "r4.slag.x", "r4.slag.y", "r5.structure_std", "r6.structure_std", "r6.slag.y",
      "r7.structure_std", "r7.slag.x", "A", "X", "Y"]
D1400 = ["r3.structure_std", "r3.slag.x", "r3.slag.y", "r4.slag.x", "r5.structure_std",
         "r6.structure_std", "r7.slag.y", "A"]
PCT = (0.5, 99.5)
NPERM = 20_000
B = 2000
rng = np.random.default_rng(int(sys.argv[1]))
SIMS = int(sys.argv[2])
MODE = sys.argv[3]
RHO = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0


def col(n, k):
    return np.array([p[k] for p in P[n]["scaled"]])


def units_of(x):  # x: draws... x n x 18 -> ... x n x 21
    a = np.log(x[..., 0::3]).mean(-1, keepdims=True)
    xx = x[..., 1::3].mean(-1, keepdims=True)
    yy = x[..., 2::3].mean(-1, keepdims=True)
    return np.concatenate([x, a, xx, yy], axis=-1)


def perm_p(x, y, perms):
    n = x.shape[0]
    pooled = np.concatenate([x, y], 0)
    total = pooled.sum(0)
    sx = pooled[perms].sum(1)
    stat = sx / n - (total - sx) / n
    obs = x.mean(0) - y.mean(0)
    tol = 16 * np.finfo(float).eps * np.abs(pooled).max(0)
    return ((np.abs(stat) >= np.abs(obs) - tol).sum(0) + 1) / (perms.shape[0] + 1)


def holm_any(p, alpha):
    return bool(np.sort(p)[0] <= alpha / len(p))


def run(label, n200, n800, D, n, chi_of, shrink=1.0, zero=()):
    m8 = np.array([col(n800, k).mean() for k in T])
    s8 = np.array([col(n800, k).std(ddof=1) for k in T])
    s2 = np.array([col(n200, k).std(ddof=1) for k in T])
    delta = shrink * np.array([col(n200, k).mean() - col(n800, k).mean() for k in T])
    delta[[T.index(k) for k in zero]] = 0.0
    chi = np.array([chi_of(k) for k in T])
    di = [UNITS.index(u) for u in D]
    oi = [i for i, u in enumerate(UNITS) if u not in D]
    perms = np.argsort(rng.random((NPERM, 2 * n)), 1)[:, :n]
    out, chis = {}, []
    for _ in range(SIMS):
        z1 = rng.normal(size=(n, 18))
        z2 = rng.normal(size=(n, 18))
        nat2 = units_of(rng.normal(m8 + delta, s2, (n, 18)))
        nat8 = units_of(m8 + s8 * z1)
        sub = units_of(m8 + (1 - chi) * delta + s2 * (RHO * z1 + np.sqrt(1 - RHO**2) * z2))
        p = perm_p(nat2, sub, perms)
        rej = holm_any(p[di], 0.01 / 6)
        flag = holm_any(p[oi], 0.01 / 6)
        i = rng.integers(0, n, (B, n))
        j = rng.integers(0, n, (B, n))
        mn2, ms, m8b = nat2[i].mean(1), sub[j].mean(1), nat8[j].mean(1)
        ratio = (mn2[:, di] - ms[:, di]) / (mn2[:, di] - m8b[:, di])
        med = np.median(ratio, 1)
        lo, hi = np.percentile(med, PCT)
        chis.append(np.median((nat2[:, di].mean(0) - sub[:, di].mean(0))
                              / (nat2[:, di].mean(0) - nat8[:, di].mean(0))))
        if rej:
            c = "chain" if lo > 0.5 else "mixed" if hi < 0.5 else "unresolved"
        else:
            c = "undersampling" if hi < 0.5 else "inconclusive"
        if flag:
            c += "+flag"
        out[c] = out.get(c, 0) + 1
    print(label, {k: round(v / SIMS, 3) for k, v in sorted(out.items())},
          f"| chi point median {np.median(chis):.3f}", flush=True)


F1400 = ("row_s200", "row_s800", D1400, 32)
F0 = ("row_j0_s200", "row_j0_s800", D0, 16)
const = lambda c: (lambda k: c)  # noqa: E731
if MODE == "chi":
    for shrink in (1.0, 0.5):
        for chi in (0.0, 0.25, 0.5, 0.75, 1.0):
            run(f"f=1/1400 n=32 Delta x{shrink} rho={RHO} chi={chi}", *F1400, const(chi), shrink)
        for chi in (0.0, 0.25, 0.5, 0.75, 1.0):
            run(f"f=0 n=16 Delta x{shrink} rho={RHO} chi={chi}", *F0, const(chi), shrink)
elif MODE == "adversarial":
    run("f=0 n=16 chain only in X (c = Delta on the slag.x keys, 0 elsewhere)", *F0,
        lambda k: 1.0 if k.endswith("slag.x") else 0.0)
    run("f=1/1400 n=32 chain on every key except r4.slag.x", *F1400,
        lambda k: 0.0 if k == "r4.slag.x" else 1.0)
    run("f=1/1400 n=32 chain only in r4.slag.x", *F1400, lambda k: 1.0 if k == "r4.slag.x" else 0.0)
    run("f=1/1400 n=32 chain only in the structure_std keys", *F1400,
        lambda k: 1.0 if k.endswith("structure_std") else 0.0)
    run("f=1/1400 n=32 chain only in the slag.x keys", *F1400,
        lambda k: 1.0 if k.endswith("slag.x") else 0.0)
elif MODE == "robust":
    # the two selected units of each set whose 99% bounds lie closest to 0 have no true departure
    for chi in (0.0, 0.5, 1.0):
        run(f"f=1/1400 n=32 chi={chi}, Delta 0 for r7.slag.y and r3.slag.y", *F1400, const(chi),
            1.0, ("r7.slag.y", "r3.slag.y"))
        run(f"f=0 n=16 chi={chi}, Delta 0 for r4.slag.y and r3.slag.x", *F0, const(chi),
            1.0, ("r4.slag.y", "r3.slag.x"))
elif MODE == "pairs":
    # sample size at f = 1/1400: 16 and 24 fresh pairs per side
    for n in (16, 24):
        for shrink in (1.0, 0.5):
            for chi in (0.0, 0.5, 1.0):
                run(f"f=1/1400 n={n} Delta x{shrink} chi={chi}", "row_s200", "row_s800", D1400, n,
                    const(chi), shrink)
    for shrink in (1.0, 0.5):
        for chi in (0.0, 0.5, 1.0):
            run(f"f=0 n=8 Delta x{shrink} chi={chi}", "row_j0_s200", "row_j0_s800", D0, 8,
                const(chi), shrink)
