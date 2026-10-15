"""Planning only (review round 2): select D_0 and D_1400 on 006's blocks by 99% intervals.

The registered procedure (README, Common definitions, "Departure sets"):
- units: the 18 keys of T and the class statistics A, X, Y (21 units);
- per footprint, native 200 px (006 block 39 or 31) against native 800 px (006 block 41 or 32),
  8 pairs each, from 006's per-pair values (pairs006.json);
- one numpy.random.default_rng(0); pair indices integers(0, 8, (10_000, 8)) drawn once per
  configuration in the order row_s200, row_s800, row_j0_s200, row_j0_s800 and shared by every unit;
- a unit is selected iff the (0.5, 99.5) percentile interval of the resampled difference of
  means (200 px minus 800 px) excludes 0.
Also prints the exact 8-vs-8 permutation p of A, X, Y (ensemble.permutation_pvalue) for the
Background table, and the selection under the 95% level and under the other draw order, for the
record.
"""

import json
from pathlib import Path

import numpy as np
from painterly_analysis import ensemble

P = json.loads((Path(__file__).parent / "pairs006.json").read_text())
REGIONS = [2, 3, 4, 5, 6, 7]
T = [f"r{r}.{k}" for r in REGIONS for k in ("structure_std", "slag.x", "slag.y")]
UNITS = [*T, "A", "X", "Y"]
B = 10_000
ORDER = ("row_s200", "row_s800", "row_j0_s200", "row_j0_s800")


def unit(name, u):
    rows = P[name]["scaled"]
    if u == "A":
        return np.mean([np.log([p[f"r{r}.structure_std"] for p in rows]) for r in REGIONS], axis=0)
    if u in ("X", "Y"):
        return np.mean([[p[f"r{r}.slag.{u.lower()}"] for p in rows] for r in REGIONS], axis=0)
    return np.array([p[u] for p in rows])


def select(order, percentiles):
    rng = np.random.default_rng(0)
    idx = {name: rng.integers(0, 8, (B, 8)) for name in order}
    out = {}
    for f, n200, n800 in (("1/1400", "row_s200", "row_s800"), ("0", "row_j0_s200", "row_j0_s800")):
        rows = []
        for u in UNITS:
            a, b = unit(n200, u), unit(n800, u)
            diff = a[idx[n200]].mean(1) - b[idx[n800]].mean(1)
            lo, hi = np.percentile(diff, percentiles)
            rows.append((u, a.mean() - b.mean(), lo, hi, not lo <= 0 <= hi))
        out[f] = rows
    return out


main = select(ORDER, (0.5, 99.5))
for f, rows in main.items():
    print(f"f = {f}: 200 - 800 px, 99% percentile intervals (registered procedure)")
    for u, d, lo, hi, sel in rows:
        print(f"  {u:18s} {d:+.4f} [{lo:+.4f}, {hi:+.4f}] {'SELECTED' if sel else ''}")
    chosen = [u for u, *_, sel in rows if sel]
    print(f"  D_{f}: {len(chosen)} units: {chosen}")
    near = sorted(rows, key=lambda r: min(abs(r[2]), abs(r[3])))[:4]
    print("  bounds closest to 0:", [(u, round(lo, 4), round(hi, 4)) for u, _, lo, hi, _ in near])

print("\nclass statistics, exact 8-vs-8 permutation p (Background table)")
for f, n200, n800 in (("0", "row_j0_s200", "row_j0_s800"), ("1/1400", "row_s200", "row_s800")):
    for u in ("A", "X", "Y"):
        p = ensemble.permutation_pvalue(unit(n200, u), unit(n800, u), "two-sided")
        print(f"  f = {f} {u}: p {p:.3g}")

for label, order, pct in (
    ("95%, registered order", ORDER, (2.5, 97.5)),
    ("99%, f = 0 configurations drawn first", ORDER[2:] + ORDER[:2], (0.5, 99.5)),
):
    alt = select(order, pct)
    print(f"\nfor the record, {label}:")
    for f, rows in alt.items():
        print(f"  D_{f}: {[u for u, *_, sel in rows if sel]}")
