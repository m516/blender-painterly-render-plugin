"""Planning only (review round 2): H2's per-Z interval conditions alone (no Holm test), 99%.

Same model as review5_h2.py (keys independent and normal, A from the simulated keys, stand-in sds
grown by g per doubling of f). For Z in (A, r4.slag.x) it counts the joint states under the
first draft's rule (reduction = shift alone) and under the registered rule (removed / reduced /
reversed), to show the reversed case: Delta_400 = -1.5 Delta_1400 on every key.
usage: review5_h2_states.py SEED DRAWS
"""

import json
import sys
from pathlib import Path

import numpy as np

P = json.loads((Path(__file__).parent / "pairs006.json").read_text())
R = [2, 3, 4, 5, 6, 7]
T = [f"r{r}.{k}" for r in R for k in ("structure_std", "slag.x", "slag.y")]
UNITS = [*T, "A", "X", "Y"]
PCT = (0.5, 99.5)
B = 2000
rng = np.random.default_rng(int(sys.argv[1]))
SIMS = int(sys.argv[2])


def col(n, k):
    return np.array([p[k] for p in P[n]["scaled"]])


def units_of(x):
    a = np.log(x[..., 0::3]).mean(-1, keepdims=True)
    return np.concatenate([x, a, x[..., 1::3].mean(-1, keepdims=True),
                           x[..., 2::3].mean(-1, keepdims=True)], axis=-1)


def boot(x):
    return x[rng.integers(0, x.shape[0], (B, x.shape[0]))].mean(1)


m8 = np.array([col("row_s800", k).mean() for k in T])
s8 = np.array([col("row_s800", k).std(ddof=1) for k in T])
s2 = np.array([col("row_s200", k).std(ddof=1) for k in T])
s2px = np.array([col("row_s200_px", k).std(ddof=1) for k in T])
d006 = np.array([col("row_s200", k).mean() - col("row_s800", k).mean() for k in T])

for g in (1.12, 1.41):
    for truth in (0.0, -1.5):
        old, new = {}, {}
        for _ in range(SIMS):
            y2 = units_of(rng.normal(m8 + truth * d006, s2px * g**0.807, (16, 18)))
            y8 = units_of(rng.normal(m8, s8 * g**1.807, (16, 18)))
            r2 = units_of(rng.normal(m8 + d006, s2, (32, 18)))
            r8 = units_of(rng.normal(m8, s8, (32, 18)))
            b4, b14 = boot(y2) - boot(y8), boot(r2) - boot(r8)
            lo4, hi4 = np.percentile(b4, PCT, axis=0)
            los, his = np.percentile(b4 - b14, PCT, axis=0)
            p14 = r2.mean(0) - r8.mean(0)
            o, n = [], []
            for z in ("A", "r4.slag.x"):
                u = UNITS.index(z)
                sgn = np.sign(p14[u]) or 1.0
                shift = (los[u] > 0) if sgn < 0 else (his[u] < 0)
                nodep = lo4[u] <= 0 <= hi4[u]
                on_side = (lo4[u] > 0) if sgn > 0 else (hi4[u] < 0)
                opposite = (hi4[u] < 0) if sgn > 0 else (lo4[u] > 0)
                o.append("removed" if nodep and shift else "reduced" if shift else "none")
                n.append("removed" if nodep and shift else "reduced" if on_side and shift
                         else "reversed" if opposite else "none")
            ov = ("supported" if all(s == "removed" for s in o) else "reduced"
                  if all(s != "none" for s in o) else "not shown")
            nv = ("supported" if all(s == "removed" for s in n) else "reduced"
                  if all(s in ("removed", "reduced") for s in n) else "reversed"
                  if "reversed" in n else "not shown")
            old[ov] = old.get(ov, 0) + 1
            new[nv] = new.get(nv, 0) + 1
        print(f"growth {g}, Delta_400 = {truth} x Delta_1400 (no Holm): first-draft rule",
              {k: round(v / SIMS, 3) for k, v in sorted(old.items())}, "| registered rule",
              {k: round(v / SIMS, 3) for k, v in sorted(new.items())}, flush=True)
