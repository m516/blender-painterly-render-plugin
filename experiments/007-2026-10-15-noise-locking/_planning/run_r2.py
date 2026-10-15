"""Round-2 planning runner for experiment 007 (second review round, run 2026-10-15).

This is the inline runner of the round-2 verdict and mixture-sweep runs, saved as a file. It
loads ``synth1d.py`` and adds the (A') model ``ipjit_x`` at the end of ``MODELS``, so the indices of
the other models (and so their random streams) are unchanged.

Usage (the environment of the runs: OMP_NUM_THREADS=1, PYTHONDONTWRITEBYTECODE=1, ``python -I``):

    run_r2.py JOB [JOB ...]       JOB = CONTRAST:START:STOP:MODELS:W
        CONTRAST  a = (400, 800), b = (200, 400)
        START:STOP  realization seeds range(START, STOP)
        MODELS    comma-separated, empty = every model
        W         white share of the mix models (the stream key uses round(1000 W))
    run_r2.py --h4-isotropic START STOP
        H4 with the isotropic 2-D high-pass on the 400 px reference of each realization (the first
        draws of ``run_contrast`` for W = 0.5, so the same reference realizations as the verdict runs)
    run_r2.py --e1-table
        E1 (8 pairs, one realization) for the round-2 models, then the prediction table (seed 0)

Each line of output is one JSON record. Commands of the round-2 runs (4 workers):
    a:0:25::0.5 b:0:50::0.5 | a:25:50::0.5 b:50:100::0.5 | a:50:75::0.5 b:100:150::0.5 |
    a:75:100::0.5 b:150:200::0.5                                  -> r2_cover.jsonl
    a:0:20:mix_x,mix_gauss:0.1 a:0:20:mix_x,mix_gauss:0.25 |
    a:0:20:mix_x,mix_gauss:0.75 a:0:20:mix_x,mix_gauss:0.9 |
    b:0:40:mix_x,mix_gauss:0.1 b:0:40:mix_x,mix_gauss:0.25 b:0:40:mix_x,mix_gauss:0.75
    b:0:40:mix_x,mix_gauss:0.9                                    -> r2_sweep.jsonl
    --h4-isotropic 0 200                                          -> r2_h4_isotropic.jsonl
    --e1-table                                                    -> r2_table_e1.jsonl
"""

import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np

_spec = importlib.util.spec_from_file_location("s1", Path(__file__).resolve().parent / "synth1d.py")
s1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(s1)
s1.MODELS = s1.MODELS + ("ipjit_x",)
_noise = s1.noise


def noise(model, rng, n, s, jitter_px, w_white=0.5):
    """``synth1d.noise`` plus ``ipjit_x``: ``pix_x`` with sigma_n = 2 px x j / (1/700)."""
    if model == "ipjit_x":
        sig = s1.SIGMA_N_REF * (2 * jitter_px / s) / (1 / 700)
        return s1.unit(s1.circ_lowpass_x(rng.normal(size=(n, s, s)), sig / math.sqrt(2)))
    return _noise(model, rng, n, s, jitter_px, w_white)


s1.noise = noise

KEEP = (
    "H12", "H3", "H12_R", "H3_R", "D", "D_ci", "D_jit", "D_jit_ci", "Dpx", "Dip", "Djit_px",
    "h4_p", "h4_A", "h4_sd", "h5_p", "h5_Y", "h5_sd",
)


def cover(job):
    contrast, a, b, named, w = job.split(":")
    w = float(w)
    models = named.split(",") if named else list(s1.MODELS)
    for seed in range(int(a), int(b)):
        for model in models:
            rng = np.random.default_rng([seed, s1.MODELS.index(model), int(round(1000 * w))])
            res = s1.run_contrast(model, rng, contrast, w_white=w)[0]
            res.update(s1.cells_of(res))
            # The verdict runs kept every field of KEEP, the sweep runs (models named) the first 8.
            keep = {k: res[k] for k in (KEEP[:8] if named else KEEP)}
            print(json.dumps({"seed": seed, "model": model, "c": contrast, "w": w, **keep}), flush=True)


def h4_isotropic(a, b):
    for seed in range(a, b):
        for model in s1.MODELS:
            rng = np.random.default_rng([seed, s1.MODELS.index(model), 500])
            xa, xb = s1.pair_fields(model, rng, 400, s1.JP_IP[400], 8, 0.5)
            d = xa - xb
            h = s1.ghp2(d, s1.SIGMA_REF)
            lx = np.array([s1.masked_lag(h, s1.masks[400][r], 1, 2) for r in s1.REGIONS])
            ly = np.array([s1.masked_lag(h, s1.masks[400][r], 0, 2) for r in s1.REGIONS])
            A = (s1.W400[:, None] * (lx - ly)).sum(0)
            print(json.dumps({"seed": seed, "model": model, "h4_2d_p": s1.sign_flip(A),
                              "A": float(A.mean()), "sd": float(A.std(ddof=1)),
                              "r4x": float(lx[2].mean()), "r4y": float(ly[2].mean())}), flush=True)


def e1_table():
    for model in ("pix_x", "ipjit_x", "jit_x", "img_x", "mix_x", "mix_gauss"):
        print(json.dumps({"kind": "e1", "model": model, **s1.e1(model, 8, 0)}), flush=True)
    print(json.dumps({"kind": "table", "seed": 0, "table": s1.table(0)}), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "--h4-isotropic":
        h4_isotropic(int(sys.argv[2]), int(sys.argv[3]))
    elif sys.argv[1] == "--e1-table":
        e1_table()
    else:
        for job in sys.argv[1:]:
            cover(job)
