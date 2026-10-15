"""Planning only (review round 1): class departures, steps and their SEs from 006's per-pair values."""

import json
import math
from pathlib import Path

import numpy as np

from painterly_analysis import ensemble

P = json.loads((Path(__file__).parent / "pairs006.json").read_text())
REGIONS = [2, 3, 4, 5, 6, 7]


def col(name, key):
    return np.array([p[key] for p in P[name]["scaled"]])


def cls(name, c):
    if c == "A":
        return np.mean([np.log(col(name, f"r{r}.structure_std")) for r in REGIONS], axis=0)
    axis = {"X": "x", "Y": "y"}[c]
    return np.mean([col(name, f"r{r}.slag.{axis}") for r in REGIONS], axis=0)


def se(a, b):
    return math.sqrt(a.var(ddof=1) / a.size + b.var(ddof=1) / b.size)


print("departures 200 - 800 px (8 v 8, exact permutation p)")
for fam in ("row_s", "row_j0_s"):
    for c in "AXY":
        a, b = cls(fam + "200", c), cls(fam + "800", c)
        dd = a.mean() - b.mean()
        print(f"  {fam:9s} {c} {dd:+.4f} se {se(a, b):.4f} z {dd / se(a, b):+.2f} "
              f"p {ensemble.permutation_pvalue(a, b):.3g}")
print("steps 400 -> 800 px")
for fam in ("row_s", "row_j0_s"):
    for c in "AXY":
        a, b = cls(fam + "800", c), cls(fam + "400", c)
        dd = a.mean() - b.mean()
        print(f"  {fam:9s} {c} s2 {dd:+.5f} se {se(a, b):.5f} z {dd / se(a, b):+.2f}; "
              f"sd400 {b.std(ddof=1):.5f} sd800 {a.std(ddof=1):.5f}; "
              f"se(s3) sd1600=sd800 {a.std(ddof=1) * math.sqrt(2 / 8):.5f}, "
              f"=sd800/2 {a.std(ddof=1) * math.sqrt(1.25 / 8):.5f}; "
              f"se(s3 - s2/4) {math.sqrt(a.var(ddof=1) / 8 + 25 / 16 * a.var(ddof=1) / 8 + b.var(ddof=1) / 128):.5f} "
              f"/ {math.sqrt(a.var(ddof=1) / 32 + 25 / 16 * a.var(ddof=1) / 8 + b.var(ddof=1) / 128):.5f}")
print("structure_std 400->800 per key, zero family: step, d")
for r in REGIONS:
    k = f"r{r}.structure_std"
    a, b = col("row_j0_s800", k), col("row_j0_s400", k)
    sp = math.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    print(f"  {k} {a.mean() - b.mean():+.4f} d {(a.mean() - b.mean()) / sp:+.2f}")
for k in ("r4.slag.x",):
    for name in ("row_s200", "row_s200_px", "row_s800", "row_s800_px", "row_j0_s200", "row_j0_s800"):
        print(f"  {name:12s} {k} mean {col(name, k).mean():.4f} sd {col(name, k).std(ddof=1):.4f}")

print("class departures 200 - 800 px with 95% percentile bootstrap intervals (10,000, seed 0)")
rng = np.random.default_rng(0)
for fam in ("row_s", "row_j0_s"):
    for c in "AXY":
        a, b = cls(fam + "200", c), cls(fam + "800", c)
        ia = rng.integers(0, 8, (10_000, 8))
        ib = rng.integers(0, 8, (10_000, 8))
        bd = a[ia].mean(1) - b[ib].mean(1)
        lo, hi = np.percentile(bd, [2.5, 97.5])
        print(f"  {fam:9s} {c} {a.mean() - b.mean():+.4f} [{lo:+.4f}, {hi:+.4f}]")
