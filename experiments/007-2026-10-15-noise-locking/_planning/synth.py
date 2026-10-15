"""Pre-registration computation for experiment 007: synthetic noise models through the revised
decision pipeline (no render sum arrays are read; only the cached object-id maps, for the masks).

A fast numpy re-implementation of the README's definitions, for planning only. The analysis card
implements the same definitions with the library functions.

Usage: synth.py MODE [args]
  table SEED                 prediction table, one seed, 8 pairs
  cover CONTRAST R START     verdicts for R seeds from START at contrast "a" (400,800) or "b" (200,400)
  beta NPAIRS R START        E1 white-model beta through the display path
"""

import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
from numpy.fft import fftfreq, irfft2, rfft2, rfftfreq
from scipy.signal import lfilter

OUT = Path(__file__).resolve().parent
P = 64
SIGMA_REF = 9 / math.sqrt(12)
REF = 400
NOISE_SD = math.sqrt(5573.6 / 64)  # 001 H4, sigma_n^2 / P, display bytes
STRUCT_SD = math.sqrt(33.07)  # 001 H4, sigma_s
PHI = 0.6
SIGMA_N_REF = 2.0
ALPHA = 0.01
B = int(__import__("os").environ.get("BOOT", "20000"))
REGIONS = (2, 3, 4, 5, 6, 7)
MODELS = ("white", "white_drift", "ar1", "pix_gauss", "jit_gauss", "img_gauss", "mix")

masks = {s: {r: np.load(OUT / f"mask_{s}_r{r}.npy") for r in REGIONS} for s in (200, 400, 800)}
SPLITS = np.array(list(itertools.combinations(range(16), 8)))  # 12870 x 8
ONEHOT = np.zeros((len(SPLITS), 16))
ONEHOT[np.arange(len(SPLITS))[:, None], SPLITS] = 1.0
PATTERNS = 1 - 2 * ((np.arange(256)[:, None] >> np.arange(8)) & 1)


def frames(s):
    return {"px": (SIGMA_REF, 2), "ip": (SIGMA_REF * s / REF, s // 200)}


def ghp(x, sigma):
    h, w = x.shape[-2:]
    ext = np.concatenate([x, x[..., :, ::-1]], axis=-1)
    ext = np.concatenate([ext, ext[..., ::-1, :]], axis=-2)
    fy = fftfreq(2 * h)
    fx = rfftfreq(2 * w)
    t = np.exp(-2 * np.pi**2 * sigma**2 * (fy[:, None] ** 2 + fx[None, :] ** 2))
    low = irfft2(rfft2(ext) * t, s=(2 * h, 2 * w))[..., :h, :w]
    return x - low


def unit(x):
    x = x - x.mean(axis=(-2, -1), keepdims=True)
    return x / x.std(axis=(-2, -1), keepdims=True)


def circ_lowpass(e, kernel_sd):
    s = e.shape[-1]
    fy = fftfreq(s)
    fx = rfftfreq(s)
    t = np.exp(-2 * np.pi**2 * kernel_sd**2 * (fy[:, None] ** 2 + fx[None, :] ** 2))
    return irfft2(rfft2(e) * t, s=(s, s))


FMAX = 99  # below the 200 px Nyquist (100 cycles per image)
_f = np.arange(-FMAX, FMAX + 1)


def image_locked(rng, n, s, ell_img):
    fy, fx = np.meshgrid(_f, _f, indexing="ij")
    spec = np.exp(-2 * np.pi**2 * ell_img**2 * (fx**2 + fy**2))
    c = (rng.normal(size=(n,) + fy.shape) + 1j * rng.normal(size=(n,) + fy.shape)) * np.sqrt(spec)
    c = c * np.exp(1j * np.pi * (fx + fy) / s)
    a = np.zeros((n, s, s), complex)
    a[:, fy % s, fx % s] = c
    return unit(np.real(np.fft.ifft2(a)) * s * s)


def noise(model, rng, n, s, jitter_px):
    """n unit-variance fields of side s (times the amplitude factor), for one configuration."""
    if model in ("white", "white_drift"):
        z = rng.normal(size=(n, s, s))
        z = unit(z)
        return z * (math.sqrt(s / REF) if model == "white_drift" else 1.0)
    if model == "ar1":
        e = rng.normal(size=(n, s, s))
        y0 = rng.normal(size=(n, s, 1))
        y = lfilter([math.sqrt(1 - PHI**2)], [1, -PHI], e, axis=-1, zi=PHI * y0)[0]
        return unit(y)
    if model == "pix_gauss":
        return unit(circ_lowpass(rng.normal(size=(n, s, s)), SIGMA_N_REF / math.sqrt(2)))
    if model == "jit_gauss":
        sig = SIGMA_N_REF * jitter_px / (2 / 7)
        return unit(circ_lowpass(rng.normal(size=(n, s, s)), sig / math.sqrt(2)))
    if model == "img_gauss":
        return image_locked(rng, n, s, SIGMA_N_REF / REF)
    if model == "mix":
        return unit(rng.normal(size=(n, s, s)) + image_locked(rng, n, s, SIGMA_N_REF / REF))
    raise ValueError(model)


# The shared structure: 16 sinusoids, radii uniform in [2, 50] cycles per image, fixed seed.
_rs = np.random.default_rng(12345)
SIN_R = _rs.uniform(2, 50, 16)
SIN_T = _rs.uniform(0, 2 * np.pi, 16)
SIN_P = _rs.uniform(0, 2 * np.pi, 16)


def structure(s):
    u = (np.arange(s) + 0.5) / s
    out = np.zeros((s, s))
    for r, t, p in zip(SIN_R, SIN_T, SIN_P):
        out += np.cos(2 * np.pi * r * (np.cos(t) * u[None, :] + np.sin(t) * u[:, None]) + p)
    u4 = (np.arange(REF) + 0.5) / REF
    ref = np.zeros((REF, REF))
    for r, t, p in zip(SIN_R, SIN_T, SIN_P):
        ref += np.cos(2 * np.pi * r * (np.cos(t) * u4[None, :] + np.sin(t) * u4[:, None]) + p)
    return out / ref.std() * STRUCT_SD


STRUCT = {s: structure(s) for s in (200, 400, 800)}


def display(v):
    return np.clip(np.floor(v), 0, 255)


def pair_fields(model, rng, s, jitter_px, npairs):
    m = STRUCT[s]
    na = noise(model, rng, npairs, s, jitter_px) * NOISE_SD
    nb = noise(model, rng, npairs, s, jitter_px) * NOISE_SD
    return display(128 + m + na), display(128 + m + nb)


def masked_var(h, m):
    v = h[:, m]
    return v.var(axis=1)


def masked_lag(h, m, axis, lag):
    if axis == 1:
        a, b, pm = h[:, :, :-lag], h[:, :, lag:], m[:, :-lag] & m[:, lag:]
    else:
        a, b, pm = h[:, :-lag], h[:, lag:], m[:-lag] & m[lag:]
    av, bv = a[:, pm], b[:, pm]
    cov = ((av - av.mean(1, keepdims=True)) * (bv - bv.mean(1, keepdims=True))).mean(1)
    return cov / masked_var(h, m)


def keys(xa, xb, s):
    d = xa - xb
    out = {}
    for f, (sig, tau) in frames(s).items():
        h = ghp(d, sig)
        for r in REGIONS:
            m = masks[s][r]
            vd = masked_var(d, m)
            vh = masked_var(h, m)
            out[f"{f}.r{r}.noise_frac"] = np.sqrt(vh / vd)
            out[f"{f}.r{r}.noise_std"] = np.sqrt(vh / 2)
            out[f"{f}.r{r}.nlag.x"] = masked_lag(h, m, 1, tau)
            out[f"{f}.r{r}.nlag.y"] = masked_lag(h, m, 0, tau)
    return out


def family(frame):
    return [f"{frame}.r{r}.{k}" for r in REGIONS for k in ("noise_frac", "nlag.x", "nlag.y")]


def perm_p(x, y):
    pooled = np.concatenate([x, y])
    sx = ONEHOT @ pooled
    stat = sx / 8 - (pooled.sum() - sx) / 8
    tol = 16 * np.finfo(float).eps * np.abs(pooled).max()
    return np.count_nonzero(np.abs(stat) >= abs(stat[0]) - tol) / len(stat)


def holm_count(ps, alpha):
    ps = sorted(ps)
    m = len(ps)
    k = 0
    for i, p in enumerate(ps):
        if p <= alpha / (m - i):
            k += 1
        else:
            break
    return k


def cohen(xa, xb):
    """|d| per key along the last axis; xa, xb (..., 8)."""
    ma, mb = xa.mean(-1), xb.mean(-1)
    va, vb = xa.var(-1, ddof=1), xb.var(-1, ddof=1)
    sp = np.sqrt((va + vb) / 2)
    return np.abs(ma - mb) / sp


def delta_boot(a_arr, b_arr, draws_a, draws_b):
    """Median over keys of |d|: point and bootstrap. a_arr (keys, 8)."""
    point = np.median(cohen(a_arr, b_arr))
    ra = a_arr[:, draws_a]  # keys, B, 8
    rb = b_arr[:, draws_b]
    boot = np.median(cohen(ra, rb), axis=0)
    return point, boot


def verdict(rp, ri, rj, dci, djci):
    p, i, j = rp >= 1, ri >= 1, (rj >= 1) if rj is not None else None
    dpos, dneg = dci[0] > 0, dci[1] < 0
    if not p and i and dpos:
        return "supported"
    if j is not None and p and not j and djci[0] > 0:
        return "refuted_jitter_px"
    if p and not i and (j is None or j) and dneg:
        return "refuted_image"
    if p and i and (j is None or j) and dpos:
        return "partially_supported"
    if p and i and (j is None or j) and dneg:
        return "partially_refuted"
    return "inconclusive"


def run_contrast(model, rng, contrast, npairs=8, with_jit=True):
    s_ref = 400
    s_other = 800 if contrast == "a" else 200
    jp_ip = {200: 1 / 7, 400: 2 / 7, 800: 4 / 7}
    k_ref = keys(*pair_fields(model, rng, s_ref, jp_ip[s_ref], npairs), s_ref)
    k_oth = keys(*pair_fields(model, rng, s_other, jp_ip[s_other], npairs), s_other)
    k_jit = keys(*pair_fields(model, rng, s_other, 2 / 7, npairs), s_other) if with_jit else None
    level = ALPHA / (3 if with_jit else 2)
    res = {}
    arr = {}
    for f in ("px", "ip"):
        fam = family(f)
        a = np.array([k_oth[k] for k in fam])
        b = np.array([k_ref[k] for k in fam])
        arr[f] = (a, b)
        ps = [perm_p(a[i], b[i]) for i in range(len(fam))]
        res[f"p_{f}"] = ps
        res[f"R_{f}"] = holm_count(ps, level)
    if with_jit:
        fam = family("px")
        aj = np.array([k_jit[k] for k in fam])
        arr["jit"] = (aj, arr["px"][1])
        ps = [perm_p(aj[i], arr["px"][1][i]) for i in range(len(fam))]
        res["p_jit"] = ps
        res["R_jit"] = holm_count(ps, level)
    brng = np.random.default_rng(0)
    da = brng.integers(0, npairs, (B, npairs))
    db = brng.integers(0, npairs, (B, npairs))
    dj = brng.integers(0, npairs, (B, npairs))
    pt = {}
    bt = {}
    for f in ("px", "ip"):
        pt[f], bt[f] = delta_boot(arr[f][0], arr[f][1], da, db)
    D = pt["ip"] - pt["px"]
    Dci = np.percentile(bt["ip"] - bt["px"], (0.5, 99.5))
    res["D"], res["D_ci"] = float(D), [float(v) for v in Dci]
    if with_jit:
        ptj, btj = delta_boot(arr["jit"][0], arr["jit"][1], dj, db)
        res["D_jit"] = float(pt["px"] - ptj)
        res["D_jit_ci"] = [float(v) for v in np.percentile(bt["px"] - btj, (0.5, 99.5))]
    res["verdict"] = verdict(
        res["R_px"], res["R_ip"], res.get("R_jit"), res["D_ci"], res.get("D_jit_ci")
    )
    # mechanism check at 400 px (px frame = ip frame there)
    w = np.array([masks[400][r].sum() for r in REGIONS], float)
    w /= w.sum()
    A = sum(
        w[i] * (k_ref[f"px.r{r}.nlag.x"] - k_ref[f"px.r{r}.nlag.y"]) for i, r in enumerate(REGIONS)
    )
    stats = PATTERNS @ A / 8
    tol = 8 * np.finfo(float).eps * np.abs(A).max()
    res["mech_p"] = float(np.count_nonzero(np.abs(stats) >= abs(A.mean()) - tol) / 256)
    res["mech_A"] = float(A.mean())
    return res, k_ref, k_oth, k_jit


def table(seed):
    rng = np.random.default_rng(seed)
    out = {}
    for model in MODELS:
        rows = {}
        jp = {200: 1 / 7, 400: 2 / 7, 800: 4 / 7}
        for s in (200, 400, 800):
            k = keys(*pair_fields(model, rng, s, jp[s], 8), s)
            rows[str(s)] = {key: float(np.mean(v)) for key, v in k.items()}
        for s in (200, 800):
            k = keys(*pair_fields(model, rng, s, 2 / 7, 8), s)
            rows[f"{s}_px"] = {key: float(np.mean(v)) for key, v in k.items()}
        out[model] = rows
    return out


def beta(npairs, seed):
    rng = np.random.default_rng(seed)
    out = {}
    for contrast, s in (("b", 200), ("a", 400)):
        xa, xb = pair_fields("white", rng, s, 0, npairs)
        m2 = STRUCT[2 * s]
        na = unit(rng.normal(size=(npairs, 2 * s, 2 * s))) * NOISE_SD
        nb = unit(rng.normal(size=(npairs, 2 * s, 2 * s))) * NOISE_SD

        def down(v):
            return v.reshape(npairs, s, 2, s, 2).mean(axis=(2, 4))

        ya = display(down(128 + m2 + na))
        yb = display(down(128 + m2 + nb))
        sig = SIGMA_REF * s / REF
        nv = {}
        for name, (a, b) in (("native", (xa, xb)), ("down", (ya, yb))):
            ha, hb = ghp(a, sig), ghp(b, sig)
            nv[name] = np.array([masked_var(ha - hb, masks[s][r]) / 2 for r in REGIONS])
        brng = np.random.default_rng(0)
        d1 = brng.integers(0, npairs, (B, npairs))
        d2 = brng.integers(0, npairs, (B, npairs))
        point = np.median(np.log2(nv["native"].mean(1) / nv["down"].mean(1)))
        boot = np.median(
            np.log2(nv["native"][:, d1].mean(-1) / nv["down"][:, d2].mean(-1)), axis=0
        )
        ci = np.percentile(boot, (0.5, 99.5))
        out[contrast] = [float(point), float(ci[0]), float(ci[1])]
    return out


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "table":
        print(json.dumps(table(int(sys.argv[2]))))
    elif mode == "cover":
        contrast, r, start = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
        models = sys.argv[5].split(",") if len(sys.argv) > 5 else [
            "white", "white_drift", "ar1", "pix_gauss", "jit_gauss", "img_gauss", "mix"]
        for seed in range(start, start + r):
            for model in models:
                rng = np.random.default_rng([seed, MODELS.index(model)])
                res = run_contrast(model, rng, contrast)[0]
                # H3-type (no jitter family) on the same draws is not separate here
                print(json.dumps({"seed": seed, "model": model, "contrast": contrast, **res}),
                      flush=True)
    elif mode == "beta":
        npairs, r, start = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
        for seed in range(start, start + r):
            print(json.dumps({"seed": seed, **beta(npairs, seed)}), flush=True)


def e1(model, npairs, seed, chunk=8):
    """E1 common-side keys through the display path: beta, beta_S, beta_q medians and 99% CIs."""
    rng = np.random.default_rng([seed, MODELS.index(model), 77])
    jp = {200: 1 / 7, 400: 2 / 7, 800: 4 / 7}
    out = {}
    for contrast, s in (("b", 200), ("a", 400)):
        sig = SIGMA_REF * s / REF
        acc = {"native": ([], []), "down": ([], [])}
        for start in range(0, npairs, chunk):
            k = min(chunk, npairs - start)
            xa, xb = pair_fields(model, rng, s, jp[s], k)
            m2 = STRUCT[2 * s]
            na = noise(model, rng, k, 2 * s, jp[2 * s]) * NOISE_SD
            nb = noise(model, rng, k, 2 * s, jp[2 * s]) * NOISE_SD

            def down(v):
                return v.reshape(k, s, 2, s, 2).mean(axis=(2, 4))

            ya = display(down(128 + m2 + na))
            yb = display(down(128 + m2 + nb))
            for name, (a, b) in (("native", (xa, xb)), ("down", (ya, yb))):
                ha, hb = ghp(a, sig), ghp(b, sig)
                nvs, scs = [], []
                for r in REGIONS:
                    msk = masks[s][r]
                    nvs.append(masked_var(ha - hb, msk) / 2)
                    av, bv = ha[:, msk], hb[:, msk]
                    scs.append(((av - av.mean(1, keepdims=True)) * (bv - bv.mean(1, keepdims=True))).mean(1))
                acc[name][0].append(np.array(nvs))
                acc[name][1].append(np.array(scs))
        nv = {n: np.concatenate(acc[n][0], axis=1) for n in acc}
        sc = {n: np.concatenate(acc[n][1], axis=1) for n in acc}
        brng = np.random.default_rng(0)
        d1 = brng.integers(0, npairs, (B, npairs))
        d2 = brng.integers(0, npairs, (B, npairs))
        res = {}
        for label, field in (("beta", nv), ("beta_S", sc)):
            pt = np.median(np.log2(field["native"].mean(1) / field["down"].mean(1)))
            bt = np.median(np.log2(field["native"][:, d1].mean(-1) / field["down"][:, d2].mean(-1)), axis=0)
            res[label] = [float(pt), *[float(v) for v in np.percentile(bt, (0.5, 99.5))]]
        q = lambda n, s_, i=None: (n if i is None else n[:, i]).mean(-1) / (s_ if i is None else s_[:, i]).mean(-1)
        ptq = np.median(np.log2(q(nv["native"], sc["native"]) / q(nv["down"], sc["down"])))
        btq = np.median(np.log2((nv["native"][:, d1].mean(-1) / sc["native"][:, d1].mean(-1))
                                / (nv["down"][:, d2].mean(-1) / sc["down"][:, d2].mean(-1))), axis=0)
        res["beta_q"] = [float(ptq), *[float(v) for v in np.percentile(btq, (0.5, 99.5))]]
        out[contrast] = res
    return out


if __name__ == "__main__" and sys.argv[1] == "e1":
    npairs, r, start = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    models = sys.argv[5].split(",") if len(sys.argv) > 5 else list(MODELS)
    for seed in range(start, start + r):
        for model in models:
            print(json.dumps({"seed": seed, "model": model, **e1(model, npairs, seed)}), flush=True)
