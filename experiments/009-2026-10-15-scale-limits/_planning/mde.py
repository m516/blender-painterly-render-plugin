"""Planning only: minimum detectable effects from 006's per-pair values (pairs006.json)."""
import json
import math

import numpy as np

P = json.load(open(__file__.rsplit("/", 1)[0] + "/pairs006.json"))
regions = [2, 3, 4, 5, 6, 7]
T = [f"r{r}.{k}" for r in regions for k in ("structure_std", "slag.x", "slag.y")]


def col(name, key):
    return np.array([p[key] for p in P[name]["scaled"]])


def sd(name, key):
    return col(name, key).std(ddof=1)


D_H1 = 4.0  # 8 v 8 at 1.85e-4: power 0.91 (power.py)
for fam in ("row_s", "row_j0_s"):
    ss = [D_H1 * sd(fam + "800", f"r{r}.structure_std") for r in regions]
    ssrel = [D_H1 * sd(fam + "800", f"r{r}.structure_std") / col(fam + "800", f"r{r}.structure_std").mean() for r in regions]
    sl = [D_H1 * sd(fam + "800", f"r{r}.slag.{a}") for r in regions for a in "xy"]
    print(fam, "H1 MDE (4 sd800): structure_std %.3f-%.3f bytes (rel %.4f-%.4f), slag %.4f-%.4f" % (min(ss), max(ss), min(ssrel), max(ssrel), min(sl), max(sl)))
# H2: 8v8 at 5.56e-4, d=3.5 power 0.94
D_H2 = 3.5
pooled = {k: math.sqrt((sd("row_s200", k) ** 2 + sd("row_s800", k) ** 2) / 2) for k in T}
ss = [D_H2 * pooled[f"r{r}.structure_std"] for r in regions]
ssrel = [D_H2 * pooled[f"r{r}.structure_std"] / col("row_s800", f"r{r}.structure_std").mean() for r in regions]
sl = [D_H2 * pooled[f"r{r}.slag.{a}"] for r in regions for a in "xy"]
print("H2 MDE (3.5 pooled sd of row_s200/row_s800): structure_std %.3f-%.3f (rel %.4f-%.4f), slag %.4f-%.4f" % (min(ss), max(ss), min(ssrel), max(ssrel), min(sl), max(sl)))
# H3: 16 v 16 at 1.85e-4: d=2.45 power 0.98, d=2.1 ~0.9 ; 8v8 d=4
D0 = ["r2.slag.y", "r3.structure_std", "r4.structure_std", "r5.structure_std", "r6.structure_std", "r6.slag.y", "r7.structure_std"]
for f, n200, n800, keys in (("0", "row_j0_s200", "row_j0_s800", D0), ("1/1400", "row_s200", "row_s800", ["r4.slag.x"])):
    for key in keys:
        delta = col(n200, key).mean() - col(n800, key).mean()
        s = sd(n200, key)
        d16 = abs(delta) / s
        se16 = s * math.sqrt(2 / 16)
        se8 = s * math.sqrt(2 / 8)
        print(f"f={f} {key:18s} Delta {delta:+.4f} sd200 {s:.4f} d(c=Delta) {d16:.2f}  MDE16(2.1sd) {2.1*s:.4f}  MDE8(4sd) {4*s:.4f}  se(chi) 16p {se16/abs(delta):.3f} 8p {se8/abs(delta):.3f}")
# A steps and sd
def A(name):
    return np.mean([np.log(col(name, f"r{r}.structure_std")) for r in regions], axis=0)
for fam in ("row_s", "row_j0_s"):
    a = {s: A(fam + str(s)) for s in (200, 400, 800)}
    print(fam, "A means", {s: round(float(v.mean()), 5) for s, v in a.items()}, "sd", {s: round(float(v.std(ddof=1)), 5) for s, v in a.items()})
    for axis in "xy":
        m = {s: np.mean([col(fam + str(s), f"r{r}.slag.{axis}") for r in regions], axis=0) for s in (200, 400, 800)}
        print("   ", axis, {s: (round(float(v.mean()), 4), round(float(v.std(ddof=1)), 4)) for s, v in m.items()})
