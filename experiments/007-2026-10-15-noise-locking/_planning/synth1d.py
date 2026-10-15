"""Second-round pre-registration computation for experiment 007: synthetic noise models through
the revised (along-row) decision pipeline. Only the cached object-id maps are read, for the masks.

Changes against synth.py (first round), after the second review round:
- the locking keys are along rows: a 1-D Gaussian high-pass along x (mirror-extended on axis 1),
  `noise_frac` and `nlag.x` per region and frame, 12 keys per frame;
- H4 uses `nlag.x` of that family and `nlag.y` of the 1-D high-pass along y, at 400 px;
- H5 (row independence): the uncentered across-row lag-1 statistic of the unfiltered delta;
- row-independent models `pix_x`, `jit_x`, `img_x`, `mix_x` next to the isotropic ones;
- verdict cells 1-7 (cell 1 split by J);
- one bootstrap rng per hypothesis, configurations drawn in the order reference, sN, sN_px.

Usage: synth1d.py MODE [args]
  table SEED                       prediction table (replicate SEED), 8 pairs
  cover CONTRAST R START [MODELS] [W]  verdicts for R seeds; W = white share of the mix models
  e1 NPAIRS R START [MODELS]       E1 through the display path (2-D ip high-pass, unchanged)
"""

import itertools
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
from numpy.fft import fftfreq, irfft, irfft2, rfft, rfft2, rfftfreq
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
B = int(os.environ.get("BOOT", "20000"))
REGIONS = (2, 3, 4, 5, 6, 7)
MODELS = (
    "white", "white_drift", "ar1", "pix_x", "pix_gauss", "jit_x", "jit_gauss", "img_x",
    "img_gauss", "mix_x", "mix_gauss",
)
JP_IP = {200: 1 / 7, 400: 2 / 7, 800: 4 / 7}

masks = {s: {r: np.load(OUT / f"mask_{s}_r{r}.npy") for r in REGIONS} for s in (200, 400, 800)}
W400 = np.array([masks[400][r].sum() for r in REGIONS], float)
W400 /= W400.sum()
SPLITS = np.array(list(itertools.combinations(range(16), 8)))  # 12870 x 8
ONEHOT = np.zeros((len(SPLITS), 16))
ONEHOT[np.arange(len(SPLITS))[:, None], SPLITS] = 1.0
PATTERNS = 1 - 2 * ((np.arange(256)[:, None] >> np.arange(8)) & 1)


def frames(s):
    return {"px": (SIGMA_REF, 2), "ip": (SIGMA_REF * s / REF, s // 200)}


def ghp2(x, sigma):
    h, w = x.shape[-2:]
    ext = np.concatenate([x, x[..., :, ::-1]], axis=-1)
    ext = np.concatenate([ext, ext[..., ::-1, :]], axis=-2)
    fy, fx = fftfreq(2 * h), rfftfreq(2 * w)
    t = np.exp(-2 * np.pi**2 * sigma**2 * (fy[:, None] ** 2 + fx[None, :] ** 2))
    return x - irfft2(rfft2(ext) * t, s=(2 * h, 2 * w))[..., :h, :w]


def ghp_x(x, sigma):
    """1-D Gaussian high-pass along axis -1 (x), half-sample-symmetric extension on that axis."""
    w = x.shape[-1]
    ext = np.concatenate([x, x[..., ::-1]], axis=-1)
    t = np.exp(-2 * np.pi**2 * sigma**2 * rfftfreq(2 * w) ** 2)
    return x - irfft(rfft(ext, axis=-1) * t, n=2 * w, axis=-1)[..., :w]


def ghp_y(x, sigma):
    return np.swapaxes(ghp_x(np.swapaxes(x, -1, -2), sigma), -1, -2)


def unit(x):
    x = x - x.mean(axis=(-2, -1), keepdims=True)
    return x / x.std(axis=(-2, -1), keepdims=True)


def circ_lowpass(e, kernel_sd):
    s = e.shape[-1]
    fy, fx = fftfreq(s), rfftfreq(s)
    t = np.exp(-2 * np.pi**2 * kernel_sd**2 * (fy[:, None] ** 2 + fx[None, :] ** 2))
    return irfft2(rfft2(e) * t, s=(s, s))


def circ_lowpass_x(e, kernel_sd):
    s = e.shape[-1]
    t = np.exp(-2 * np.pi**2 * kernel_sd**2 * rfftfreq(s) ** 2)
    return irfft(rfft(e, axis=-1) * t, n=s, axis=-1)


FMAX = 99  # below the 200 px Nyquist (100 cycles per image)
_nu = np.arange(-FMAX, FMAX + 1)


def image_locked(rng, n, s, ell_img):
    ny, nx = np.meshgrid(_nu, _nu, indexing="ij")
    spec = np.exp(-2 * np.pi**2 * ell_img**2 * (nx**2 + ny**2))
    c = (rng.normal(size=(n,) + ny.shape) + 1j * rng.normal(size=(n,) + ny.shape)) * np.sqrt(spec)
    c = c * np.exp(1j * np.pi * (nx + ny) / s)
    a = np.zeros((n, s, s), complex)
    a[:, ny % s, nx % s] = c
    return unit(np.real(np.fft.ifft2(a)) * s * s)


def image_locked_x(rng, n, s, ell_img):
    """Image-locked along rows only: an independent 1-D band-limited field in each row."""
    spec = np.exp(-2 * np.pi**2 * ell_img**2 * _nu**2)
    c = (rng.normal(size=(n, s, _nu.size)) + 1j * rng.normal(size=(n, s, _nu.size))) * np.sqrt(spec)
    c = c * np.exp(1j * np.pi * _nu / s)
    a = np.zeros((n, s, s), complex)
    a[:, :, _nu % s] = c
    return unit(np.real(np.fft.ifft(a, axis=-1)) * s)


def noise(model, rng, n, s, jitter_px, w_white=0.5):
    """n unit-variance fields of side s (times the amplitude factor), for one configuration."""
    if model in ("white", "white_drift"):
        z = unit(rng.normal(size=(n, s, s)))
        return z * (math.sqrt(s / REF) if model == "white_drift" else 1.0)
    if model == "ar1":
        e = rng.normal(size=(n, s, s))
        y0 = rng.normal(size=(n, s, 1))
        y = lfilter([math.sqrt(1 - PHI**2)], [1, -PHI], e, axis=-1, zi=PHI * y0)[0]
        return unit(y)
    if model == "pix_x":
        return unit(circ_lowpass_x(rng.normal(size=(n, s, s)), SIGMA_N_REF / math.sqrt(2)))
    if model == "pix_gauss":
        return unit(circ_lowpass(rng.normal(size=(n, s, s)), SIGMA_N_REF / math.sqrt(2)))
    if model == "jit_x":
        sig = SIGMA_N_REF * jitter_px / (2 / 7)
        return unit(circ_lowpass_x(rng.normal(size=(n, s, s)), sig / math.sqrt(2)))
    if model == "jit_gauss":
        sig = SIGMA_N_REF * jitter_px / (2 / 7)
        return unit(circ_lowpass(rng.normal(size=(n, s, s)), sig / math.sqrt(2)))
    if model == "img_x":
        return image_locked_x(rng, n, s, SIGMA_N_REF / REF)
    if model == "img_gauss":
        return image_locked(rng, n, s, SIGMA_N_REF / REF)
    if model in ("mix_x", "mix_gauss"):
        field = image_locked_x if model == "mix_x" else image_locked
        wz = unit(rng.normal(size=(n, s, s)))
        iz = field(rng, n, s, SIGMA_N_REF / REF)
        return unit(math.sqrt(w_white) * wz + math.sqrt(1 - w_white) * iz)
    raise ValueError(model)


# The shared structure: 16 sinusoids, radii uniform in [2, 50] cycles per image, fixed seed.
_rs = np.random.default_rng(12345)
SIN_R = _rs.uniform(2, 50, 16)
SIN_T = _rs.uniform(0, 2 * np.pi, 16)
SIN_P = _rs.uniform(0, 2 * np.pi, 16)


def _raw_structure(s):
    u = (np.arange(s) + 0.5) / s
    out = np.zeros((s, s))
    for r, t, p in zip(SIN_R, SIN_T, SIN_P):
        out += np.cos(2 * np.pi * r * (np.cos(t) * u[None, :] + np.sin(t) * u[:, None]) + p)
    return out


_REF_SD = _raw_structure(REF).std()
STRUCT = {s: _raw_structure(s) / _REF_SD * STRUCT_SD for s in (200, 400, 800)}


def display(v):
    return np.clip(np.floor(v), 0, 255)


def pair_fields(model, rng, s, jitter_px, npairs, w_white=0.5):
    m = STRUCT[s]
    na = noise(model, rng, npairs, s, jitter_px, w_white) * NOISE_SD
    nb = noise(model, rng, npairs, s, jitter_px, w_white) * NOISE_SD
    return display(128 + m + na), display(128 + m + nb)


def masked_var(h, m):
    return h[:, m].var(axis=1)


def masked_lag(h, m, axis, lag):
    if axis == 1:
        a, b, pm = h[:, :, :-lag], h[:, :, lag:], m[:, :-lag] & m[:, lag:]
    else:
        a, b, pm = h[:, :-lag], h[:, lag:], m[:-lag] & m[lag:]
    av, bv = a[:, pm], b[:, pm]
    cov = ((av - av.mean(1, keepdims=True)) * (bv - bv.mean(1, keepdims=True))).mean(1)
    return cov / masked_var(h, m)


def rho_y(d, m):
    """Uncentered across-row lag-1 statistic of the unfiltered delta (H5)."""
    pm = m[:-1] & m[1:]
    num = (d[:, :-1][:, pm] * d[:, 1:][:, pm]).mean(1)
    den = (d[:, m] ** 2).mean(1)
    return num / den


def keys(xa, xb, s, mech=False):
    d = xa - xb
    out = {}
    for f, (sig, tau) in frames(s).items():
        h = ghp_x(d, sig)
        for r in REGIONS:
            m = masks[s][r]
            out[f"{f}.r{r}.noise_frac"] = np.sqrt(masked_var(h, m) / masked_var(d, m))
            out[f"{f}.r{r}.nlag.x"] = masked_lag(h, m, 1, tau)
    if mech:
        sig, tau = frames(s)["px"]
        hy = ghp_y(d, sig)
        for r in REGIONS:
            m = masks[s][r]
            out[f"px.r{r}.nlag.y"] = masked_lag(hy, m, 0, tau)
            out[f"raw.r{r}.rho_y"] = rho_y(d, m)
    return out


def family(frame):
    return [f"{frame}.r{r}.{k}" for r in REGIONS for k in ("noise_frac", "nlag.x")]


def perm_p(x, y):
    pooled = np.concatenate([x, y])
    sx = ONEHOT @ pooled
    stat = sx / 8 - (pooled.sum() - sx) / 8
    tol = 16 * np.finfo(float).eps * np.abs(pooled).max()
    return np.count_nonzero(np.abs(stat) >= abs(stat[0]) - tol) / len(stat)


def holm_count(ps, alpha):
    k = 0
    for i, p in enumerate(sorted(ps)):
        if p <= alpha / (len(ps) - i):
            k += 1
        else:
            break
    return k


def cohen(xa, xb):
    ma, mb = xa.mean(-1), xb.mean(-1)
    sp = np.sqrt((xa.var(-1, ddof=1) + xb.var(-1, ddof=1)) / 2)
    return np.abs(ma - mb) / sp


def delta_boot(a_arr, b_arr, draws_a, draws_b):
    point = np.median(cohen(a_arr, b_arr))
    boot = np.median(cohen(a_arr[:, draws_a], b_arr[:, draws_b]), axis=0)
    return point, boot


def verdict(rp, ri, rj, dci, djci):
    """Cells 1-7 of the revised verdict table. rj None: H3-type (no J condition)."""
    p, i = rp >= 1, ri >= 1
    j = None if rj is None else rj >= 1
    d_pos, d_neg = dci[0] > 0, dci[1] < 0
    if not p and i and d_pos and not j:  # j is None or False
        return 1
    if j is not None and not p and j and i and d_pos and djci[1] < 0:
        return 2
    if j is not None and p and not j and djci[0] > 0:
        return 3
    if p and not i and (j is None or j) and d_neg:
        return 4
    if p and i and (j is None or j) and d_pos:
        return 5
    if p and i and (j is None or j) and d_neg:
        return 6
    return 7


def sign_flip(v):
    stats = PATTERNS @ v / 8
    tol = 8 * np.finfo(float).eps * np.abs(v).max()
    return float(np.count_nonzero(np.abs(stats) >= abs(v.mean()) - tol) / 256)


def run_contrast(model, rng, contrast, npairs=8, w_white=0.5):
    s_other = 800 if contrast == "a" else 200
    k_ref = keys(*pair_fields(model, rng, REF, JP_IP[REF], npairs, w_white), REF, mech=True)
    k_oth = keys(*pair_fields(model, rng, s_other, JP_IP[s_other], npairs, w_white), s_other)
    k_jit = keys(*pair_fields(model, rng, s_other, 2 / 7, npairs, w_white), s_other)
    res = {}
    arr = {}
    for name, f, kk in (("px", "px", k_oth), ("ip", "ip", k_oth), ("jit", "px", k_jit)):
        fam = family(f)
        a = np.array([kk[k] for k in fam])
        b = np.array([k_ref[k] for k in fam])
        arr[name] = (a, b)
        res[f"p_{name}"] = [perm_p(a[i], b[i]) for i in range(len(fam))]
    # One bootstrap rng per hypothesis: reference, sN, sN_px.
    brng = np.random.default_rng(0)
    dr = brng.integers(0, npairs, (B, npairs))
    do = brng.integers(0, npairs, (B, npairs))
    dj = brng.integers(0, npairs, (B, npairs))
    pt, bt = {}, {}
    for name, dd in (("px", do), ("ip", do), ("jit", dj)):
        pt[name], bt[name] = delta_boot(arr[name][0], arr[name][1], dd, dr)
    res["Dpx"], res["Dip"], res["Djit_px"] = pt["px"], pt["ip"], pt["jit"]
    res["D"] = float(pt["ip"] - pt["px"])
    res["D_ci"] = [float(v) for v in np.percentile(bt["ip"] - bt["px"], (0.5, 99.5))]
    res["D_jit"] = float(pt["px"] - pt["jit"])
    res["D_jit_ci"] = [float(v) for v in np.percentile(bt["px"] - bt["jit"], (0.5, 99.5))]
    A = sum(W400[i] * (k_ref[f"px.r{r}.nlag.x"] - k_ref[f"px.r{r}.nlag.y"]) for i, r in enumerate(REGIONS))
    Y = sum(W400[i] * k_ref[f"raw.r{r}.rho_y"] for i, r in enumerate(REGIONS))
    res["h4_p"], res["h4_A"], res["h4_sd"] = sign_flip(A), float(A.mean()), float(A.std(ddof=1))
    res["h5_p"], res["h5_Y"], res["h5_sd"] = sign_flip(Y), float(Y.mean()), float(Y.std(ddof=1))
    return res, k_ref, k_oth, k_jit


def cells_of(res):
    out = {}
    for typ, level, with_j in (("H12", ALPHA / 3, True), ("H3", ALPHA / 2, False)):
        rp = holm_count(res["p_px"], level)
        ri = holm_count(res["p_ip"], level)
        rj = holm_count(res["p_jit"], level) if with_j else None
        out[typ] = verdict(rp, ri, rj, res["D_ci"], res["D_jit_ci"] if with_j else None)
        out[f"{typ}_R"] = [rp, ri, rj]
    return out


def table(seed):
    out = {}
    for model in MODELS:
        rng = np.random.default_rng([seed, MODELS.index(model), 5])
        rows = {}
        for s in (200, 400, 800):
            k = keys(*pair_fields(model, rng, s, JP_IP[s], 8), s, mech=(s == REF))
            rows[str(s)] = {key: [float(np.mean(v)), float(np.std(v, ddof=1))] for key, v in k.items()}
        for s in (200, 800):
            k = keys(*pair_fields(model, rng, s, 2 / 7, 8), s)
            rows[f"{s}_px"] = {key: [float(np.mean(v)), float(np.std(v, ddof=1))] for key, v in k.items()}
        out[model] = rows
    return out


def e1(model, npairs, seed, chunk=8):
    """E1 common-side keys through the display path (2-D ip high-pass, as in round 1)."""
    rng = np.random.default_rng([seed, MODELS.index(model), 77])
    out = {}
    for contrast, s in (("b", 200), ("a", 400)):
        sig = SIGMA_REF * s / REF
        acc = {"native": ([], []), "down": ([], [])}
        for start in range(0, npairs, chunk):
            k = min(chunk, npairs - start)
            xa, xb = pair_fields(model, rng, s, JP_IP[s], k)
            m2 = STRUCT[2 * s]
            na = noise(model, rng, k, 2 * s, JP_IP[2 * s]) * NOISE_SD
            nb = noise(model, rng, k, 2 * s, JP_IP[2 * s]) * NOISE_SD

            def down(v):
                return v.reshape(k, s, 2, s, 2).mean(axis=(2, 4))

            ya, yb = display(down(128 + m2 + na)), display(down(128 + m2 + nb))
            for name, (a, b) in (("native", (xa, xb)), ("down", (ya, yb))):
                ha, hb = ghp2(a, sig), ghp2(b, sig)
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
            ptv = np.median(np.log2(field["native"].mean(1) / field["down"].mean(1)))
            btv = np.median(np.log2(field["native"][:, d1].mean(-1) / field["down"][:, d2].mean(-1)), axis=0)
            res[label] = [float(ptv), *[float(v) for v in np.percentile(btv, (0.5, 99.5))]]
        ptq = np.median(np.log2((nv["native"].mean(1) / sc["native"].mean(1)) / (nv["down"].mean(1) / sc["down"].mean(1))))
        btq = np.median(np.log2((nv["native"][:, d1].mean(-1) / sc["native"][:, d1].mean(-1))
                                / (nv["down"][:, d2].mean(-1) / sc["down"][:, d2].mean(-1))), axis=0)
        res["beta_q"] = [float(ptq), *[float(v) for v in np.percentile(btq, (0.5, 99.5))]]
        out[contrast] = res
    return out


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "table":
        print(json.dumps(table(int(sys.argv[2]))))
    elif mode == "cover":
        contrast, r, start = sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
        models = sys.argv[5].split(",") if len(sys.argv) > 5 and sys.argv[5] else list(MODELS)
        w = float(sys.argv[6]) if len(sys.argv) > 6 else 0.5
        for seed in range(start, start + r):
            for model in models:
                rng = np.random.default_rng([seed, MODELS.index(model), int(round(1000 * w))])
                res = run_contrast(model, rng, contrast, w_white=w)[0]
                res.update(cells_of(res))
                print(json.dumps({"seed": seed, "model": model, "contrast": contrast, "w": w, **res}), flush=True)
    elif mode == "e1":
        npairs, r, start = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
        models = sys.argv[5].split(",") if len(sys.argv) > 5 else list(MODELS)
        for seed in range(start, start + r):
            for model in models:
                print(json.dumps({"seed": seed, "model": model, **e1(model, npairs, seed)}), flush=True)
