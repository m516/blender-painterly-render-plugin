"""Planning simulations for 008 (scratch; power.py in the experiment reproduces them in JAX)."""

import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
S = json.loads((HERE / "summary006.json").read_text())
PRED = json.loads((HERE / "pred.json").read_text())
REG = [2, 3, 4, 5, 6, 7]
N = 8
IDX = np.array(list(itertools.combinations(range(2 * N), N)))  # 12870 x 8, row 0 = observed split
NS = IDX.shape[0]
EPS = np.finfo(float).eps


def m(c, k):
    return S[c][k]["mean"]


def sd(c, k):
    return S[c][k]["sd"]


def perm_counts(x, y, chunk=400):
    """Counts of splits with stat <= obs (less) and >= obs (greater), one-sided; x, y: (D, 8)."""
    out_l, out_g = [], []
    for s in range(0, x.shape[0], chunk):
        pooled = np.concatenate([x[s : s + chunk], y[s : s + chunk]], axis=1)
        total = pooled.sum(1, keepdims=True)
        sx = pooled[:, IDX].sum(-1)
        stat = sx / N - (total - sx) / N
        obs = stat[:, :1]
        tol = 2 * N * EPS * np.abs(pooled).max(1, keepdims=True)
        out_l.append((stat <= obs + tol).sum(1))
        out_g.append((stat >= obs - tol).sum(1))
    return np.concatenate(out_l), np.concatenate(out_g)


def holm_all_rejected(p, alpha):
    """p: (D, m). Returns bool (D, m) of Holm rejections."""
    D, mm = p.shape
    order = np.argsort(p, axis=1, kind="stable")
    ps = np.take_along_axis(p, order, 1)
    thr = alpha / (mm - np.arange(mm))
    ok = np.cumprod(ps <= thr, axis=1).astype(bool)
    rej = np.zeros_like(ok)
    np.put_along_axis(rej, order, ok, 1)
    return rej


rng = np.random.default_rng(0)
which = sys.argv[1:] or ["s1", "s2", "s3", "s4", "s5", "s6"]

if "s1" in which:
    print("S1 per-test power, one-sided exact permutation, 4000 designs")
    thr = {"0.01/30": 0.01 / 30, "0.01/18": 0.01 / 18, "0.01/15": 0.01 / 15, "0.01/33": 0.01 / 33}
    for d in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]:
        x = rng.normal(d, 1, (4000, N))
        y = rng.normal(0, 1, (4000, N))
        _, g = perm_counts(x, y)
        p = g / NS
        # two-sided: |stat| >= |obs|; for 8 v 8 the mirror split doubles the one-sided count when p small
        print(f"d={d}: " + "; ".join(f"{k}: {np.mean(p <= t):.3f}" for k, t in thr.items())
              + f"; two-sided 0.01/18: {np.mean(np.minimum(1, 2 * p) <= 0.01/18):.3f}")

if "s2" in which:
    print("\nS2 H1 fall family: P(all 30 Holm-rejected), independent cells, same d, 1000 designs")
    for d in [2.0, 2.5, 3.0, 3.5, 4.0]:
        D = 1000
        x = rng.normal(-d, 1, (D * 30, N))
        y = rng.normal(0, 1, (D * 30, N))
        l, _ = perm_counts(x, y)
        p = (l / NS).reshape(D, 30)
        rej = holm_all_rejected(p, 0.01)
        print(f"d={d}: all30 {np.mean(rej.all(1)):.3f}")
    # predicted vector, independent cells: d_step0 = 2.0 d_r, d_step1 = 0.86 d_r, steps 2-4 = d_r
    D = 1000
    dv = []
    for r in REG:
        dr = PRED["d_r"][str(r)]
        dv += [2.0 * dr, 0.86 * dr, dr, dr, dr]
    dv = np.array(dv)
    x = rng.normal(-dv[None, :, None], 1, (D, 30, N)).reshape(D * 30, N)
    y = rng.normal(0, 1, (D * 30, N))
    l, g = perm_counts(x, y)
    p = (l / NS).reshape(D, 30)
    pg = (g / NS).reshape(D, 30)
    print(f"predicted vector (min d {dv.min():.2f}): all30 {np.mean(holm_all_rejected(p, 0.01).all(1)):.3f}; "
          f"any rise rejected {np.mean(holm_all_rejected(pg, 0.01).any(1)):.3f}")
    # one true rise cell of d among 29 null (d=0) cells in the rise family
    for d in [2.0, 3.0, 3.5, 4.0]:
        x = rng.normal(0, 1, (D, 30, N)); x[:, 0, :] += d
        y = rng.normal(0, 1, (D, 30, N))
        _, g = perm_counts(x.reshape(-1, N), y.reshape(-1, N))
        rej = holm_all_rejected((g / NS).reshape(D, 30), 0.01)
        print(f"rise family: one true rise d={d}: detected {np.mean(rej[:, 0]):.3f}")


def boot_d_interval(x, y, B, lohi=(0.5, 99.5)):
    """x, y: (D, 8). Percentile interval of Cohen's d (pooled ddof-1 sd) over B resamples."""
    D = x.shape[0]
    ix = rng.integers(0, N, (D, B, N))
    iy = rng.integers(0, N, (D, B, N))
    xb = np.take_along_axis(np.broadcast_to(x[:, None, :], (D, B, N)), ix, 2)
    yb = np.take_along_axis(np.broadcast_to(y[:, None, :], (D, B, N)), iy, 2)
    sp = np.sqrt((xb.var(2, ddof=1) + yb.var(2, ddof=1)) / 2)
    dd = (xb.mean(2) - yb.mean(2)) / sp
    return np.percentile(dd, lohi, axis=1)


if "s3" in which:
    print("\nS3 'below the P = 64 seed sd' class: P(99% bootstrap interval of d inside (-1, 1)), B=2000, 1000 designs")
    for d in [0.0, 0.5]:
        x = rng.normal(d, 1, (1000, N))
        y = rng.normal(0, 1, (1000, N))
        lo, hi = boot_d_interval(x, y, 2000)
        print(f"d={d}: inside {np.mean((lo > -1) & (hi < 1)):.4f}; median half-width {np.median((hi - lo) / 2):.3f}")


def configs_sim(means, sds, D):
    """means, sds: (6 configs, R regions). Returns (D, 6, R, 8)."""
    means = np.asarray(means); sds = np.asarray(sds)
    return rng.normal(means[None, :, :, None], sds[None, :, :, None], (D,) + means.shape + (N,))


if "s4" in which:
    print("\nS4 H2 walls slag.y, configuration-level sim, 2000 designs")
    walls = [4, 5, 6]
    x = PRED["x_fit"]
    u = [0, x / 2, x, 2 * x, 4 * x, 8 * x]
    L = [math.log2(1 + v) for v in u]
    st = [L[i + 1] - L[i] for i in range(5)]
    w01 = st[0] / (st[0] + st[1])
    means, sds = [], []
    steps_pred = {}
    for r in walls:
        k = f"r{r}.slag.y"
        r01 = m("row_s800_px", k) - m("row_j0_s800", k)
        r2 = m("row_s800", k) - m("row_s800_px", k)
        r3 = m("row_s200_px", k) - m("row_s200", k)
        stp = [w01 * r01, (1 - w01) * r01, r2, r3, r3]
        steps_pred[r] = stp
        mu = np.concatenate([[0.0], np.cumsum(stp)])
        means.append(mu)
        sds.append([sd("row_j0_s400", k)] + [sd("row_s400", k)] * 5)
    means = np.array(means).T; sds = np.array(sds).T
    for r in walls:
        s = sds[:, walls.index(r)]
        print(r, "pred steps", [round(v, 3) for v in steps_pred[r]], "pred d",
              [round(steps_pred[r][i] / math.sqrt((s[i] ** 2 + s[i + 1] ** 2) / 2), 2) for i in range(5)])
    D = 2000
    X = configs_sim(means, sds, D)  # D, 6, 3, 8
    pg, pl, names = [], [], []
    for j, r in enumerate(walls):
        _, g = perm_counts(X[:, 5, j], X[:, 0, j]); pg.append(g / NS); names.append(f"a r{r}")
    for j, r in enumerate(walls):
        for i in range(5):
            l, g = perm_counts(X[:, i + 1, j], X[:, i, j])
            pg.append(g / NS); pl.append(l / NS); names.append(f"rise r{r} s{i}")
    pg = np.array(pg).T; pl = np.array(pl).T
    rise = holm_all_rejected(pg, 0.01)
    rev = holm_all_rejected(pl, 0.01)
    print("P(rejected) rise family:", "; ".join(f"{n} {v:.3f}" for n, v in zip(names, rise.mean(0))))
    print(f"P(all 3 (a)) {rise[:, :3].all(1).mean():.3f}; P(all 15 steps rise) {rise[:, 3:].all(1).mean():.4f}; "
          f"P(any reversal) {rev.any(1).mean():.4f}")
    print("reversal family: one true reversal step of d among 14 null steps, 2000 designs")
    for d in [1.5, 2.0, 3.0, 3.5]:
        a = rng.normal(0, 1, (D, 15, N)); a[:, 0, :] -= d
        b = rng.normal(0, 1, (D, 15, N))
        l, _ = perm_counts(a.reshape(-1, N), b.reshape(-1, N))
        rej = holm_all_rejected((l / NS).reshape(D, 15), 0.01)
        print(f"  d={d}: detected {rej[:, 0].mean():.3f}")


def h3_stats(Xm):
    """Xm: (..., 6 configs, 6 regions) means. Returns Q, R medians."""
    Dl = np.diff(Xm, axis=-2)  # (..., 5 steps, 6 regions)
    q0 = Dl[..., 1, :] / Dl[..., 0, :]
    q = [q0] + [Dl[..., i + 1, :] / (2 * Dl[..., i, :]) for i in (1, 2, 3)]
    rho = [Dl[..., i + 1, :] / Dl[..., i, :] for i in (1, 2, 3)]
    Q = np.median(np.concatenate(q, axis=-1), axis=-1)
    R = np.median(np.concatenate(rho, axis=-1), axis=-1)
    return Q, R


def classify_r(lo, hi):
    a, b, c = 2 ** -0.5, 2 ** 0.5, 2 ** 1.5
    if hi < a:
        return "saturating"
    if lo > a and hi < b:
        return "logarithmic"
    if lo > b and hi < c:
        return "linear"
    if lo > c:
        return "accelerating"
    return "inconclusive"


if "s5" in which:
    print("\nS5 H3 parametric bootstrap: 6 configs x 6 regions x 8 pairs, B=2000, 200 designs")
    x = PRED["x_fit"]
    u = [0, x / 2, x, 2 * x, 4 * x, 8 * x]
    L = [math.log2(1 + v) for v in u]
    st = np.array([L[i + 1] - L[i] for i in range(5)])
    mean23 = (st[2] + st[3]) / 2
    scale, sds = [], []
    for r in REG:
        k = f"r{r}.structure_std"
        f800 = m("row_s800", k) - m("row_s800_px", k)
        f200 = m("row_s200_px", k) - m("row_s200", k)
        scale.append(-((f800 + f200) / 2) / mean23)  # positive fall magnitude per unit step
        sds.append([sd("row_j0_s400", k)] + [sd("row_s400", k)] * 5)
    scale = np.array(scale); sds = np.array(sds).T
    truths = {
        "f_c model (rho 1.12, 1.07, 1.03)": st,
        "pure log (rho = 1)": np.array([st[0], st[2], st[2], st[2], st[2]]),
        "saturating (rho = 1/2)": np.array([st[0], st[2] * 2, st[2], st[2] / 2, st[2] / 4]),
        "linear in f (rho = 2)": np.array([st[0], st[2] / 2, st[2], st[2] * 2, st[2] * 4]),
    }
    D, B = 200, 2000
    for name, steps in truths.items():
        mu = 7.0 - np.concatenate([[0.0], np.cumsum(steps)])[:, None] * scale[None, :]  # (6, 6)
        X = configs_sim(mu, sds, D)  # D, 6, 6, 8
        Qb, Rb = [], []
        for c0 in range(0, D, 5):
            Xc = X[c0 : c0 + 5]
            dc = Xc.shape[0]
            ib = rng.integers(0, N, (dc, B, 6, 1, N))  # pairs resampled within each configuration
            ib = np.broadcast_to(ib, (dc, B, 6, 6, N))  # a pair carries all its regions
            Xb = np.take_along_axis(np.broadcast_to(Xc[:, None], (dc, B, 6, 6, N)), ib, -1).mean(-1)
            q, r_ = h3_stats(Xb)
            Qb.append(q); Rb.append(r_)
        Qb = np.concatenate(Qb); Rb = np.concatenate(Rb)
        Q0, R0 = h3_stats(X.mean(-1))
        qlo, qhi = np.percentile(Qb, (0.5, 99.5), axis=1)
        rlo, rhi = np.percentile(Rb, (0.5, 99.5), axis=1)
        cls = [classify_r(a, b) for a, b in zip(rlo, rhi)]
        counts = {c: cls.count(c) / D for c in sorted(set(cls))}
        print(f"{name}: R median {np.median(R0):.3f}, median 99% half-width {np.median((rhi - rlo) / 2):.3f}, "
              f"classes {counts}; Q median {np.median(Q0):.3f}, half-width {np.median((qhi - qlo) / 2):.3f}, "
              f"P(Q interval < 1) {np.mean(qhi < 1):.3f}, P(R interval excludes 1) {np.mean((rlo > 1) | (rhi < 1)):.3f}")

if "s6" in which:
    print("\nS6 H4 margin: P(99% bootstrap interval of mean diff inside (-1, 1)), B=2000, 1000 designs")
    D, B = 1000, 2000
    keys = [f"r{r}.mean.{c}" for r in REG for c in "RGB"]
    inside0 = np.ones(D, bool)
    res = []
    for k in keys:
        s0, s1 = sd("row_j0_s400", k), sd("row_s400", k)
        se = math.sqrt((s0**2 + s1**2) / 8)
        hw = 2.5758 * math.sqrt(7 / 8) * se
        dmax = 1 - hw - 2.3263 * se
        for delta, tag in ((0.0, "0"), (dmax, "dmax")):
            a = rng.normal(delta, s1, (D, N)); b = rng.normal(0, s0, (D, N))
            ia = rng.integers(0, N, (D, B, N)); ib = rng.integers(0, N, (D, B, N))
            diff = np.take_along_axis(np.broadcast_to(a[:, None], (D, B, N)), ia, 2).mean(2) - \
                np.take_along_axis(np.broadcast_to(b[:, None], (D, B, N)), ib, 2).mean(2)
            lo, hi = np.percentile(diff, (0.5, 99.5), axis=1)
            ins = (lo > -1) & (hi < 1)
            if tag == "0":
                inside0 &= ins
                hw_sim = np.median((hi - lo) / 2)
            else:
                res.append((k, dmax, ins.mean(), hw_sim))
    for k, dmax, p, hw in res:
        print(f"{k}: sim 99% half-width {hw:.3f}; at true shift {dmax:.3f} P(inside) {p:.3f}")
    print(f"all 18 inside at zero shift: {inside0.mean():.4f}")
