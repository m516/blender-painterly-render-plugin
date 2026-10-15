"""Timing of the library functions the analysis card will call, on random fields (no render data)."""
import time
import numpy as np
from painterly_analysis import metrics, ensemble

rng = np.random.default_rng(0)
for side in (200, 400, 800):
    x = rng.normal(size=(side, side))
    mask = np.zeros((side, side), bool); mask[side//4:3*side//4, side//4:3*side//4] = True
    metrics.gaussian_highpass(x, 2.0).block_until_ready()
    metrics.noise_corrected_lag(x, x, mask, 1, 2).block_until_ready()
    t = time.perf_counter()
    for _ in range(5):
        h = metrics.gaussian_highpass(x, 2.598).block_until_ready()
    t_hp = (time.perf_counter() - t) / 5
    t = time.perf_counter()
    for _ in range(5):
        metrics.noise_corrected_lag(h, h, mask, 1, 2).block_until_ready()
    t_lag = (time.perf_counter() - t) / 5
    t = time.perf_counter()
    for _ in range(5):
        metrics.structure_std(h, h, mask).block_until_ready()
    t_std = (time.perf_counter() - t) / 5
    print(f"side {side}: highpass {t_hp*1e3:.1f} ms, noise_corrected_lag {t_lag*1e3:.1f} ms, structure_std {t_std*1e3:.1f} ms")
t = time.perf_counter()
for _ in range(5):
    ensemble.permutation_pvalue(rng.normal(size=8), rng.normal(size=8))
print(f"permutation_pvalue {(time.perf_counter()-t)/5*1e3:.1f} ms")
t = time.perf_counter()
for _ in range(5):
    ensemble.sign_flip_pvalue(rng.normal(size=8), "two-sided")
print(f"sign_flip_pvalue {(time.perf_counter()-t)/5*1e3:.1f} ms")
