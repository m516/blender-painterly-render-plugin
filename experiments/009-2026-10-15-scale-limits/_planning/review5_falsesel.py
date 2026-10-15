"""Planning only (review round 2): how often a (0.5, 99.5) percentile bootstrap interval of a
difference of means excludes 0 when there is no difference (normal data, equal sds), per unit and
for at least one of k independent units. B = 2000 resamples, 4000 draws, seed 3."""
import numpy as np

rng = np.random.default_rng(3)
B, DRAWS = 2000, 4000
for n in (8, 16):
    x = rng.normal(size=(DRAWS, n))
    y = rng.normal(size=(DRAWS, n))
    out = np.empty(DRAWS, bool)
    for d in range(DRAWS):
        bx = x[d][rng.integers(0, n, (B, n))].mean(1)
        diff = bx - y[d][rng.integers(0, n, (B, n))].mean(1)
        lo, hi = np.percentile(diff, (0.5, 99.5))
        out[d] = not lo <= 0 <= hi
    p = out.mean()
    se = np.sqrt(p * (1 - p) / DRAWS)
    print(f"n = {n} per side: per-unit false exclusion {p:.4f} (se {se:.4f});"
          f" at least one of 4: {1 - (1 - p) ** 4:.3f}, of 18: {1 - (1 - p) ** 18:.3f}")
