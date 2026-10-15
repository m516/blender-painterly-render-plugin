"""Second review round (2026-10-10) planning simulations for 008 (scratch; power.py reproduces them).

Rows added or changed by the second review round:
- H2: V2 with the three overall "f350 lower than f0" tests (18 tests); predicted-step power at two sd
  brackets (README: f1400's sd at every new dose; lower bracket: f0's sd at every new dose);
  V2 detection of one true reversal among 17 null tests.
- H3: class-sum per-doubling ratios rho~_1..3 and q~_0 (sums over all six A regions; a ratio is
  estimable iff its denominator step is an F1 fall in at least one A region); H3a-0, H3a-d and H3b
  classes under ten truths: four model truths, two stop truths and four boundary truths (1,000
  designs); F1/R1 joint rates; f_c estimate from q~_0.
- H4: TOST sub-quantum class and Holm over the 36 one-sided margin tests (supra-quantum); level at
  the margin; P(classes) under three dose laws applied to 006's 1/1400 shifts at 400 and 800 px.
- H4b: per-test power of one one-sided margin test at the first Holm threshold 0.01/36.
- sens (final recheck, 2026-10-15): H1/H3, H2 and H4 with the sds of f700 and f350 grown by g and
  g^2 above f1400's, g = 1.12 (006's median sd ratio per doubling of f over T) and 1.41 (upper
  quartile).

Usage: python sim2.py [h2] [h3] [h4] [h4b] [sens]. numpy default_rng(0), (1), (2), (3), (4): one stream
per part, in that order.
"""

import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import norm

HERE = Path(__file__).parent
REPO = Path("/home/user/blender-painterly-render-plugin")
RES006 = json.loads((REPO / "experiments/006-2026-10-09-jitter-units/results.json").read_text())
S = RES006["summary"]
FOOT = RES006["jitter_footprint"]["comparisons"]
PRED = json.loads((HERE / "pred.json").read_text())
REG = [2, 3, 4, 5, 6, 7]
N = 8
IDX = np.array(list(itertools.combinations(range(2 * N), N)))  # 12870 x 8, row 0 = observed split
NS = IDX.shape[0]
IND = np.zeros((NS, 2 * N))
IND[np.arange(NS)[:, None], IDX] = 1.0  # split indicator matrix
EPS = np.finfo(float).eps
SIG = 0.01


def m(c, k):
    return S[c][k]["mean"]


def sd(c, k):
    return S[c][k]["sd"]


def perm_p(x, y, chunk=1500):
    """Exact one-sided permutation p-values of mean(x) - mean(y), x and y (T, 8): (p_less, p_greater).

    Tie rule of ensemble.permutation_pvalue: tolerance (n + m) * eps * max|pooled|.
    """
    pl, pg = [], []
    for s in range(0, x.shape[0], chunk):
        pooled = np.concatenate([x[s : s + chunk], y[s : s + chunk]], axis=1)
        total = pooled.sum(1, keepdims=True)
        sx = pooled @ IND.T
        stat = sx / N - (total - sx) / N
        obs = stat[:, :1]
        tol = 2 * N * EPS * np.abs(pooled).max(1, keepdims=True)
        pl.append((stat <= obs + tol).sum(1) / NS)
        pg.append((stat >= obs - tol).sum(1) / NS)
    return np.concatenate(pl), np.concatenate(pg)


def holm(p, alpha):
    """p: (D, k). Holm rejections (D, k)."""
    order = np.argsort(p, axis=1, kind="stable")
    ps = np.take_along_axis(p, order, 1)
    thr = alpha / (p.shape[1] - np.arange(p.shape[1]))
    ok = np.cumprod(ps <= thr, axis=1).astype(bool)
    rej = np.zeros_like(ok)
    np.put_along_axis(rej, order, ok, 1)
    return rej


def model_steps(x):
    """f_c model steps (log2 units) on the grid 0, 1/5600, ..., 1/350 with x = (1/2800)/f_c."""
    u = [0, x / 2, x, 2 * x, 4 * x, 8 * x]
    L = [math.log2(1 + v) for v in u]
    return np.array([L[i + 1] - L[i] for i in range(5)]), u


def g(x):
    """Slope ratio Delta_1/Delta_0 of the f_c model, x = (1/5600)/f_c: falls from 1 (x->0) to 0."""
    return math.log((1 + 2 * x) / (1 + x)) / math.log(1 + x)


def g_inv(ratio, xtol=1e-12):
    """x with g(x) = ratio; 0 for ratio >= 1 (f_c infinite), inf for ratio <= 0 (f_c = 0)."""
    if not ratio < 1:
        return 0.0
    if not ratio > 0:
        return math.inf
    lo = hi = 1.0
    while g(lo) < ratio:
        lo /= 2
    while g(hi) > ratio:
        hi *= 2
    while hi - lo > xtol:
        mid = (lo + hi) / 2
        if g(mid) > ratio:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


X_FIT = PRED["x_fit"]
ST, U = model_steps(X_FIT)
MEAN23 = (ST[2] + ST[3]) / 2
which = sys.argv[1:] or ["h2", "h3", "h4", "h4b", "sens"]

# ---------------------------------------------------------------- H2
if "h2" in which:
    rng = np.random.default_rng(0)
    print("H2 walls slag.y, 2000 designs; R2 = 3 overall rise + 15 step rise; V2 = 15 step lower + 3 overall lower")
    walls = [4, 5, 6]
    w01 = ST[0] / (ST[0] + ST[1])
    steps = {}
    for r in walls:
        k = f"r{r}.slag.y"
        r01 = m("row_s800_px", k) - m("row_j0_s800", k)
        r2 = m("row_s800", k) - m("row_s800_px", k)
        r3 = m("row_s200_px", k) - m("row_s200", k)
        steps[r] = [w01 * r01, (1 - w01) * r01, r2, r3, r3]
    brackets = {
        "README (f1400's sd at every new dose)": lambda k: [sd("row_j0_s400", k)] + [sd("row_s400", k)] * 5,
        "lower (f0's sd at every new dose)": lambda k: [sd("row_j0_s400", k)] * 3
        + [sd("row_s400", k)]
        + [sd("row_j0_s400", k)] * 2,
    }
    D = 2000
    for bname, sdf in brackets.items():
        means = np.array([np.concatenate([[0.0], np.cumsum(steps[r])]) for r in walls]).T  # (6, 3)
        sds = np.array([sdf(f"r{r}.slag.y") for r in walls]).T
        print(f"  bracket: {bname}")
        for j, r in enumerate(walls):
            s = sds[:, j]
            dd = [steps[r][i] / math.sqrt((s[i] ** 2 + s[i + 1] ** 2) / 2) for i in range(5)]
            print(f"    r{r} sds {np.round(s, 4).tolist()} pred d {[round(v, 1) for v in dd]}")
        X = rng.normal(means[None, :, :, None], sds[None, :, :, None], (D, 6, 3, N))
        pg_, pl_, overall_less = [], [], []
        for j in range(3):
            l, gg = perm_p(X[:, 5, j], X[:, 0, j])
            pg_.append(gg)
            overall_less.append(l)
        for j in range(3):
            for i in range(5):
                l, gg = perm_p(X[:, i + 1, j], X[:, i, j])
                pg_.append(gg)
                pl_.append(l)
        pl_ += overall_less
        R2 = holm(np.array(pg_).T, SIG)
        V2 = holm(np.array(pl_).T, SIG)
        rise = R2[:, 3:].reshape(D, 3, 5)
        rev = V2[:, :15].reshape(D, 3, 5)
        hard = V2[:, 15:]
        for j, r in enumerate(walls):
            print(f"    r{r} P(step rise) {np.round(rise[:, j].mean(0), 3).tolist()}")
        allA = R2[:, :3].all(1)
        anyrev = rev.any((1, 2))
        anyhard = hard.any(1)
        sup = allA & ~anyrev & ~anyhard
        print(f"    P(all three (a)) {allA.mean():.3f}; P(all 15 rises) {rise.all((1, 2)).mean():.3f}; "
              f"P(any reversal) {anyrev.mean():.3f}; P(any net hardening) {anyhard.mean():.3f}; "
              f"P(supported) {sup.mean():.3f}")
    print("  V2 (18 tests): one true reversal step of d among 17 null tests")
    for d in [1.5, 2.0, 3.0, 3.5]:
        a = rng.normal(0, 1, (D, 18, N))
        a[:, 0, :] -= d
        b = rng.normal(0, 1, (D, 18, N))
        l, _ = perm_p(a.reshape(-1, N), b.reshape(-1, N))
        rej = holm(l.reshape(D, 18), SIG)
        print(f"    d={d}: detected {rej[:, 0].mean():.3f}")

# ---------------------------------------------------------------- H3
# Second review round (README H3): per-doubling ratios of class sums. S_i = sum over the six A
# regions of Delta_i; q~_0 = S_1 / S_0 and rho~_i = S_{i+1} / S_i (i = 1, 2, 3). A ratio is
# estimable iff its denominator step i is an F1 fall in at least one A region. Union claims
# (saturating at some doubling; H3a-d refuted: accelerating at some doubling) use intervals at
# two-sided level 0.01/3 per doubling (Bonferroni over the three). Claims about every doubling
# (logarithmic, linear, accelerating; H3a-d supported) use 99% intervals (intersection-union).
A_RHO = 2**-0.5
B_RHO = 2**0.5
C_RHO = 2**1.5
CI99 = (0.5, 99.5)
CI_UNION = (100 * SIG / 6, 100 * (1 - SIG / 6))
DOUBLINGS = (1, 2, 3)
CELL_NAMES = {"log": "logarithmic", "lin": "linear", "acc": "accelerating"}


def cell(lo, hi):
    if hi < A_RHO:
        return "sat"
    if A_RHO < lo and hi < B_RHO:
        return "log"
    if B_RHO < lo and hi < C_RHO:
        return "lin"
    if lo > C_RHO:
        return "acc"
    return "inc"


def h3_decisions(est, l99, h99, lu, hu):
    """est (4,) bool, ratio i estimable; bounds (4,) of q~_0, rho~_1..3 (99% and union level)."""
    sat = [i for i in DOUBLINGS if est[i] and hu[i] < A_RHO]
    if sat:
        h3b = f"saturating@{sat[0]}"
    else:
        cells = [cell(l99[i], h99[i]) if est[i] else None for i in DOUBLINGS]
        same = all(c is not None for c in cells) and len(set(cells)) == 1
        h3b = CELL_NAMES.get(cells[0], "inconclusive") if same else "inconclusive"
    if not est[0]:
        a0 = "inc"
    elif h99[0] < 1:
        a0 = "sup"
    elif l99[0] > 1:
        a0 = "ref"
    else:
        a0 = "inc"
    if any(est[i] and lu[i] > 2 for i in DOUBLINGS):
        ad = "ref"
    elif all(est[i] and h99[i] < 2 for i in DOUBLINGS):
        ad = "sup"
    else:
        ad = "inc"
    return h3b, a0, ad


def a_class_setup():
    """Per-region scale s_r and the (6 conf, 6 reg) sds of class A (README H3 power check)."""
    scale, sds = [], []
    for r in REG:
        k = f"r{r}.structure_std"
        f800 = m("row_s800", k) - m("row_s800_px", k)
        f200 = m("row_s200_px", k) - m("row_s200", k)
        scale.append(-((f800 + f200) / 2) / MEAN23)
        sds.append([sd("row_j0_s400", k)] + [sd("row_s400", k)] * 5)
    return np.array(scale), np.array(sds).T


def h3_run(rng, name, steps_, D, scale, sds, B=2000):
    """Simulate D designs of class A for one truth; print the H3 rows and F1/R1 summaries."""
    mu = 7.0 - np.concatenate([[0.0], np.cumsum(steps_)])[:, None] * scale[None, :]  # (6, 6)
    tS = np.diff(mu, axis=0).sum(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        true_r = tS[1:] / tS[:-1]
    X = rng.normal(mu[None, :, :, None], sds[None, :, :, None], (D, 6, 6, N))
    pl, pg = perm_p(X[:, 1:].reshape(D * 30, N), X[:, :-1].reshape(D * 30, N))
    F1 = holm(pl.reshape(D, 30), SIG).reshape(D, 5, 6)
    R1 = holm(pg.reshape(D, 30), SIG)
    h3b, a0, ad, pts, hw99, hwu, Rpt, xs, ests = [], [], [], [], [], [], [], [], []
    for d in range(D):
        est = F1[d, :4].any(1)
        Spt = np.diff(X[d].mean(-1), axis=0).sum(1)
        pt = Spt[1:] / Spt[:-1]
        ib = np.broadcast_to(rng.integers(0, N, (B, 6, 1, N)), (B, 6, 6, N))
        Xb = np.take_along_axis(np.broadcast_to(X[d][None], (B, 6, 6, N)), ib, -1).mean(-1)
        Sb = np.diff(Xb, axis=1).sum(2)
        rb = Sb[:, 1:] / Sb[:, :-1]  # (B, 4)
        l99, h99 = np.percentile(rb, CI99, axis=0)
        lu, hu = np.percentile(rb, CI_UNION, axis=0)
        c3b, c0, cd = h3_decisions(est, l99, h99, lu, hu)
        h3b.append(c3b)
        a0.append(c0)
        ad.append(cd)
        pts.append(np.where(est, pt, np.nan))
        hw99.append(np.where(est, (h99 - l99) / 2, np.nan))
        hwu.append(np.where(est, (hu - lu) / 2, np.nan))
        Dr = np.diff(X[d].mean(-1), axis=0)
        Rpt.append(np.median(np.concatenate([Dr[i + 1] / Dr[i] for i in DOUBLINGS])))
        ests.append(est)
        if est[0]:
            xs.append((g_inv(pt[0]), g_inv(h99[0]), g_inv(l99[0])))
    pts, hw99, hwu, ests = map(np.array, (pts, hw99, hwu, ests))
    cc = {c: round(h3b.count(c) / D, 3) for c in sorted(set(h3b))}
    print(f"  {name} [{D} designs]: true q~0 {true_r[0]:.3f}, rho~ {np.round(true_r[1:], 3).tolist()}")
    print(f"    F1 all 30 falls {F1.all((1, 2)).mean():.3f}; any R1 rejection {R1.any(1).mean():.3f}")
    print(f"    P(estimable) {np.round(ests.mean(0), 3).tolist()}; median point {np.round(np.nanmedian(pts, 0), 3).tolist()}")
    print(
        f"    median 99% half-widths {np.round(np.nanmedian(hw99, 0), 3).tolist()}; "
        f"median union half-widths (rho) {np.round(np.nanmedian(hwu, 0)[1:], 3).tolist()}"
    )
    print(f"    H3b {cc}")
    print(
        f"    H3a-0 sup {a0.count('sup') / D:.3f} ref {a0.count('ref') / D:.3f}; "
        f"H3a-d sup {ad.count('sup') / D:.3f} ref {ad.count('ref') / D:.3f}; median pooled R {np.median(Rpt):.3f}"
    )
    if xs:
        xs = np.array(xs)
        print(
            f"    1/f_c = 5600 x: median point {5600 * np.median(xs[:, 0]):.0f}; median 99% interval "
            f"[{5600 * np.median(xs[:, 1]):.0f}, {5600 * np.median(xs[:, 2]):.0f}]"
        )
    sys.stdout.flush()


if "h3" in which:
    rng = np.random.default_rng(1)
    print("\nH3: 6 conf x 6 regions x 8 pairs, B = 2000; F1 Holm over 30 gates estimability")
    scale, sds = a_class_setup()
    st = ST
    truths = {  # name: (steps in log2 units of the f_c model, designs)
        "f_c model (rho 1.12, 1.07, 1.03)": (st, 200),
        "logarithmic (rho = 1)": (np.array([st[0], st[2], st[2], st[2], st[2]]), 200),
        "saturating (rho = 1/2)": (np.array([st[0], st[2] * 2, st[2], st[2] / 2, st[2] / 4]), 200),
        "f_c model, rho_3 = 1/2": (np.array([st[0], st[1], st[2], st[3], st[3] / 2]), 200),
        "stop at 1/700 (step 4 = 0)": (np.array([st[0], st[1], st[2], st[3], 0.0]), 200),
        "stop at 1/1400 (steps 3, 4 = 0)": (np.array([st[0], st[1], st[2], 0.0, 0.0]), 200),
        "boundary: f_c model, rho_3 = 2^-1/2": (np.array([st[0], st[1], st[2], st[3], st[3] * 2**-0.5]), 1000),
        "boundary: f_c model, rho_3 = 2^1/2": (np.array([st[0], st[1], st[2], st[3], st[3] * 2**0.5]), 1000),
        "boundary: kink then linear (step 0 f_c, then rho = 2)": (
            np.array([st[0], st[2] / 2, st[2], st[2] * 2, st[2] * 4]),
            1000,
        ),
        "boundary: linear from 0 (q_0 = 1, rho = 2)": (np.array([1, 1, 2, 4, 8]) * MEAN23 / 3, 1000),
    }
    for name, (steps_, D) in truths.items():
        h3_run(rng, name, steps_, D, scale, sds)

# ---------------------------------------------------------------- H4B
if "h4b" in which:
    rng = np.random.default_rng(3)
    print("\nH4b: one one-sided margin test at the first Holm threshold 0.01/36 (supra-quantum), 4,000 designs")
    for c in (3.0, 3.5, 4.0, 4.5, 5.0):
        x = rng.normal(c, 1, (4000, N))
        y = rng.normal(0, 1, (4000, N))
        _, gg = perm_p(x, y)
        print(f"  (|shift| - 1) / s_p = {c}: P(rejected) {np.mean(gg <= SIG / 36):.3f}")

# ---------------------------------------------------------------- H4
if "h4" in which:
    rng = np.random.default_rng(2)
    keys = [f"r{r}.mean.{c}" for r in REG for c in "RGB"]
    sd0 = np.array([sd("row_j0_s400", k) for k in keys])
    sd1 = np.array([sd("row_s400", k) for k in keys])  # stands in for f350
    shift400 = np.array([-FOOT["400"]["effect_summary"][k]["diff"] for k in keys])  # f1400 - f0
    shift800 = np.array([-FOOT["800"]["effect_summary"][k]["diff"] for k in keys])
    fc = (1 / 2800) / X_FIT
    NA1400 = math.log2(1 + (1 / 1400) / fc) / math.log2(1 + (1 / 350) / fc)
    print(f"\nH4: N_A(1/1400) = {NA1400:.4f}")
    print("  006 shift f1400 - f0 (bytes), 400 px:", dict(zip(keys, np.round(shift400, 3).tolist())))
    print("  006 shift f1400 - f0 (bytes), 800 px:", dict(zip(keys, np.round(shift800, 3).tolist())))

    def classify(shift, D):
        """shift (18,) true shift of f350 - f0. Returns (D, 18) class codes: 0 sub, 1 supra, 2 unresolved."""
        a = rng.normal(shift[None, :, None], sd1[None, :, None], (D, 18, N)).reshape(-1, N)
        b = rng.normal(0, sd0[None, :, None], (D, 18, N)).reshape(-1, N)
        lm, gm = perm_p(a - 1, b)  # vs +1 margin
        lp, gp = perm_p(a + 1, b)  # vs -1 margin
        sub = (np.maximum(lm, gp) <= SIG).reshape(D, 18)
        supra_p = np.concatenate([gm.reshape(D, 18), lp.reshape(D, 18)], 1)
        sr = holm(supra_p, SIG)
        supra = sr[:, :18] | sr[:, 18:]
        return np.where(sub, 0, np.where(supra, 1, 2))

    D = 1000
    c = classify(np.zeros(18), D)
    print(f"  no shift: P(all 18 sub-quantum) {(c == 0).all(1).mean():.3f}; P(any supra) {(c == 1).any(1).mean():.3f}")
    se = np.sqrt((sd0**2 + sd1**2) / 8)
    z99, z95 = norm.ppf(0.99), norm.ppf(0.95)
    d95 = 1 - (z99 + z95) * se
    c = classify(d95, D)
    print("  P(sub-quantum) per key at shift 1 - (z_0.99 + z_0.95) se:",
          {k: (round(float(v), 3), round(float(p), 3)) for k, v, p in zip(keys, d95, (c == 0).mean(0))})
    print("  level at the margin (TOST, shift = +1 exactly), 10,000 designs:")
    for tag, s_a, s_b in (("equal sds 1", 1.0, 1.0), ("r2.mean.B sds", sd1[2], sd0[2]), ("r6.mean.B sds", sd1[14], sd0[14])):
        a = rng.normal(1.0, s_a, (10000, N))
        b = rng.normal(0.0, s_b, (10000, N))
        lm, _ = perm_p(a - 1, b)
        p = np.mean(lm <= SIG)
        print(f"    {tag} ({s_a:.3f}, {s_b:.3f}): P(p_less(f350 - 1, f0) <= 0.01) {p:.4f} (MC sd {math.sqrt(p * (1 - p) / 10000):.4f})")
    print("  dose laws applied to 006's f1400 - f0 shifts, all 18 keys, 1000 designs:")
    for size, sh in (("400", shift400), ("800", shift800)):
        for law, fac in (("A-shaped (/N_A(1/1400))", 1 / NA1400), ("linear (x4)", 4.0), ("f^2 (x16)", 16.0)):
            shift = sh * fac
            c = classify(shift, D)
            dec = np.where((c == 1).any(1), "refuted", np.where((c == 0).all(1), "supported", "inconclusive"))
            i2b = keys.index("r2.mean.B")
            big = [(k, round(float(v), 2)) for k, v in zip(keys, shift) if abs(v) >= 0.5]
            print(f"    {size} px, {law}: r2.mean.B shift {shift[i2b]:.2f}: P(sub) {(c[:, i2b] == 0).mean():.3f} "
                  f"P(supra) {(c[:, i2b] == 1).mean():.3f} P(unres) {(c[:, i2b] == 2).mean():.3f}; "
                  f"H4 supported {(dec == 'supported').mean():.3f} refuted {(dec == 'refuted').mean():.3f} "
                  f"inconclusive {(dec == 'inconclusive').mean():.3f}; keys with |shift| >= 0.5: {big}")
            sys.stdout.flush()
    print("  supra power, one key shifted by 1 + (z_{1-0.01/36} + z_0.95) se, others 0:")
    z36 = norm.ppf(1 - SIG / 36)
    for k in ("r2.mean.B", "r6.mean.B"):
        i = keys.index(k)
        shift = np.zeros(18)
        shift[i] = 1 + (z36 + z95) * se[i]
        c = classify(shift, D)
        print(f"    {k}: shift {shift[i]:.3f}: P(supra) {(c[:, i] == 1).mean():.3f}")

# ---------------------------------------------------------------- SENS
# Final recheck (2026-10-15): seed sd growing with f. 006's median sd ratio per doubling of f over T
# is 1.12 (upper quartile 1.41; 36 ratios: 800 px 1/2800 -> 1/1400, 200 px 1/1400 -> 1/700). The
# sds of f700 and f350 are f1400's times g and g^2 (k doublings above 1/1400); f5600 and f2800 keep
# f1400's sd, as in the registered checks.
GROWTH = (1.12, 1.41)

if "sens" in which:
    rng = np.random.default_rng(4)
    print("\nSENS: sds of f700 and f350 = f1400's x g, x g^2")
    # H1 (F1, R1) and H3 under the f_c model, class A, raw units (as the H3 power check)
    scale, sds_a = a_class_setup()
    for gr in GROWTH:
        s = sds_a.copy()
        s[4] *= gr
        s[5] *= gr**2
        h3_run(rng, f"H1/H3, f_c model, g = {gr}", ST, 200, scale, s)
    # H2, walls, README bracket (f1400's sd at every new dose) grown above 1/1400
    walls = [4, 5, 6]
    w01 = ST[0] / (ST[0] + ST[1])
    steps = {}
    for r in walls:
        k = f"r{r}.slag.y"
        r01 = m("row_s800_px", k) - m("row_j0_s800", k)
        r2 = m("row_s800", k) - m("row_s800_px", k)
        r3 = m("row_s200_px", k) - m("row_s200", k)
        steps[r] = [w01 * r01, (1 - w01) * r01, r2, r3, r3]
    D = 2000
    means = np.array([np.concatenate([[0.0], np.cumsum(steps[r])]) for r in walls]).T  # (6, 3)
    for gr in GROWTH:
        sds = np.array(
            [[sd("row_j0_s400", f"r{r}.slag.y")] + [sd("row_s400", f"r{r}.slag.y")] * 3
             + [sd("row_s400", f"r{r}.slag.y") * gr, sd("row_s400", f"r{r}.slag.y") * gr**2] for r in walls]
        ).T
        X = rng.normal(means[None, :, :, None], sds[None, :, :, None], (D, 6, 3, N))
        pg_, pl_, overall_less = [], [], []
        for j in range(3):
            lo_, gg = perm_p(X[:, 5, j], X[:, 0, j])
            pg_.append(gg)
            overall_less.append(lo_)
        for j in range(3):
            for i in range(5):
                lo_, gg = perm_p(X[:, i + 1, j], X[:, i, j])
                pg_.append(gg)
                pl_.append(lo_)
        pl_ += overall_less
        R2 = holm(np.array(pg_).T, SIG)
        V2 = holm(np.array(pl_).T, SIG)
        rise = R2[:, 3:].reshape(D, 3, 5)
        allA = R2[:, :3].all(1)
        anyV = V2.any(1)
        print(f"  H2, g = {gr} [{D} designs]:")
        for j, r in enumerate(walls):
            print(f"    r{r} P(step rise) {np.round(rise[:, j].mean(0), 3).tolist()}")
        print(f"    P(all three (a)) {allA.mean():.3f}; P(any V2 rejection) {anyV.mean():.3f}; "
              f"P(supported) {(allA & ~anyV).mean():.3f}; P(all 15 rises) {rise.all((1, 2)).mean():.3f}")
        sys.stdout.flush()
    # H4, f350's sd = f1400's x g^2
    keys = [f"r{r}.mean.{c}" for r in REG for c in "RGB"]
    sd0 = np.array([sd("row_j0_s400", k) for k in keys])
    sd1 = np.array([sd("row_s400", k) for k in keys])
    shift400 = np.array([-FOOT["400"]["effect_summary"][k]["diff"] for k in keys])
    shift800 = np.array([-FOOT["800"]["effect_summary"][k]["diff"] for k in keys])
    fc = (1 / 2800) / X_FIT
    NA1400 = math.log2(1 + (1 / 1400) / fc) / math.log2(1 + (1 / 350) / fc)

    def classify_g(shift, D, s_a):
        a = rng.normal(shift[None, :, None], s_a[None, :, None], (D, 18, N)).reshape(-1, N)
        b = rng.normal(0, sd0[None, :, None], (D, 18, N)).reshape(-1, N)
        lm, gm = perm_p(a - 1, b)
        lp, gp = perm_p(a + 1, b)
        sub = (np.maximum(lm, gp) <= SIG).reshape(D, 18)
        sr = holm(np.concatenate([gm.reshape(D, 18), lp.reshape(D, 18)], 1), SIG)
        supra = sr[:, :18] | sr[:, 18:]
        return np.where(sub, 0, np.where(supra, 1, 2))

    D = 1000
    for gr in GROWTH:
        s_a = sd1 * gr**2
        for label, shift in (("no shift", np.zeros(18)), ("class-A shape, 400 px basis", shift400 / NA1400),
                             ("class-A shape, 800 px basis", shift800 / NA1400)):
            c = classify_g(shift, D, s_a)
            print(f"  H4, g = {gr}, {label} [{D} designs]: P(all 18 sub-quantum) {(c == 0).all(1).mean():.3f}; "
                  f"P(any supra) {(c == 1).any(1).mean():.3f}")
            sys.stdout.flush()
