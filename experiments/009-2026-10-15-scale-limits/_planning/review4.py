"""Planning only (review round 1): power of the revised H1 reading rule, H2 rule and H3 classes.

Normal per-pair data with 006's means and sds (pairs006.json). Bootstrap: 95% percentile
intervals, pairs resampled within each ensemble. Permutation p-values: Monte Carlo, as in
ensemble.permutation_pvalue ((k + 1) / (N + 1)), except where noted.
"""

import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy import stats

P = json.loads((Path(__file__).parent / "pairs006.json").read_text())
REGIONS = [2, 3, 4, 5, 6, 7]
SIMS = int(sys.argv[1]) if len(sys.argv) > 1 else 400
B = 1000
rng = np.random.default_rng(11)


def col(name, key):
    return np.array([p[key] for p in P[name]["scaled"]])


def cls(name, c):
    if c == "A":
        return np.mean([np.log(col(name, f"r{r}.structure_std")) for r in REGIONS], axis=0)
    if c in "XY":
        return np.mean([col(name, f"r{r}.slag.{c.lower()}") for r in REGIONS], axis=0)
    return col(name, c)


def ci(x):
    return np.percentile(x, [2.5, 97.5])


def contains0(lohi):
    return lohi[0] <= 0 <= lohi[1]


def boot_mean(x):
    return x[rng.integers(0, x.size, (B, x.size))].mean(1)


# (a) H1 reading rule on a class statistic, 8-pair frames at 400, 800, 1600 px
def h1_reading(fam, c, q, sdf):
    a4, a8 = cls(fam + "400", c), cls(fam + "800", c)
    m4, s4, m8, s8 = a4.mean(), a4.std(ddof=1), a8.mean(), a8.std(ddof=1)
    s2_true = m8 - m4
    counts = {}
    for _ in range(SIMS):
        x4 = rng.normal(m4, s4, 8)
        x8 = rng.normal(m8, s8, 8)
        x16 = rng.normal(m8 + q * s2_true, s8 * sdf, 8)
        b4, b8, b16 = boot_mean(x4), boot_mean(x8), boot_mean(x16)
        s3, s2 = b16 - b8, b8 - b4
        c3, cg, cn = ci(s3), ci(s3 - s2 / 4), ci(s3 - s2)
        sgn = np.sign(np.median(s2))
        if contains0(c3) and not contains0(cg):
            r = "I"
        elif not contains0(c3) and contains0(cg):
            r = "G"
        elif contains0(c3) and contains0(cg):
            r = "I or G"
        elif sgn * c3[1] < 0 if sgn > 0 else sgn * c3[0] < 0:
            r = "N (reversal)"
        elif (sgn * cg > 0).all() and not (sgn * cn < 0).all():
            r = "N"
        else:
            r = "between G and N"
        counts[r] = counts.get(r, 0) + 1
    return {k: round(v / SIMS, 2) for k, v in sorted(counts.items())}


for fam in ("row_j0_s", "row_s"):
    for c in "AXY":
        for q, lab in ((0.0, "I"), (0.25, "G"), (1.0, "N")):
            for sdf in (1.0, 0.5):
                print(f"H1 {fam} {c} truth {lab} sd1600={sdf}sd800: {h1_reading(fam, c, q, sdf)}",
                      flush=True)


# (b) H2: 16 v 16 at f = 1/400 (stand-in sds), reference departure at 1/1400 on 32 v 32 fresh pairs
def h2_rule(truth, growth, shrink):
    out = 0
    for _ in range(SIMS):
        ok = True
        for key in ("A", "r4.slag.x"):
            n2, n8 = cls("row_s200", key), cls("row_s800", key)
            d1400 = shrink * (n2.mean() - n8.mean())
            sd2_400 = cls("row_s200_px", key).std(ddof=1) * growth ** 0.807
            sd8_400 = n8.std(ddof=1) * growth ** 1.807
            d400 = {"removed": 0.0, "halved": d1400 / 2, "unchanged": d1400}[truth]
            y2 = rng.normal(n8.mean() + d400, sd2_400, 16)
            y8 = rng.normal(n8.mean(), sd8_400, 16)
            r2 = rng.normal(n8.mean() + d1400, n2.std(ddof=1), 32)
            r8 = rng.normal(n8.mean(), n8.std(ddof=1), 32)
            b400 = boot_mean(y2) - boot_mean(y8)
            b1400 = boot_mean(r2) - boot_mean(r8)
            if not (contains0(ci(b400)) and not contains0(ci(b400 - b1400))):
                ok = False
        out += ok
    return round(out / SIMS, 2)


for growth, lab in ((1.12, "median"), (1.41, "q75")):
    for shrink in (1.0, 0.5):
        r = {t: h2_rule(t, growth, shrink) for t in ("removed", "halved", "unchanged")}
        print(f"H2 interval conditions, sd growth {lab}, Delta_1400 x{shrink}: {r}", flush=True)

# H2 refutation power for one key, 16 v 16, first Holm threshold 0.01/18 (noncentral t)
for key in ("r4.slag.x",):
    n2, n8 = cls("row_s200", key), cls("row_s800", key)
    delta = abs(n2.mean() - n8.mean())
    for lab, sd2, sd8 in (
        ("median growth", n2.std(ddof=1) * 1.12 ** 1.807, n8.std(ddof=1) * 1.12 ** 1.807),
        ("1/700 sd at 200 px", cls("row_s200_px", key).std(ddof=1) * 1.12 ** 0.807,
         n8.std(ddof=1) * 1.12 ** 1.807),
    ):
        d = delta / math.sqrt((sd2**2 + sd8**2) / 2)
        for n in (8, 16):
            df = 2 * n - 2
            tc = stats.t.isf(0.01 / 18 / 2, df)
            ncp = d * math.sqrt(n / 2)
            pw = stats.nct.sf(tc, df, ncp) + stats.nct.cdf(-tc, df, ncp)
            print(f"H2 {key} {lab}: d {d:.2f}, n={n} power(t approx) {pw:.2f}")
for d in (1.44, 1.55, 2.0, 2.5):
    df = 30
    tc = stats.t.isf(0.01 / 18 / 2, df)
    print(f"16v16 d={d}: {stats.nct.sf(tc, df, d * math.sqrt(8)):.2f}")
