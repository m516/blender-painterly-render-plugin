"""Rerun 2026-10-15 of the skeptic check (20,000 designs) with 4,000 designs. Level of H4's 'sub-quantum' class at the margin: P(99% percentile interval upper bound < margin | true shift = margin)."""
import numpy as np
rng = np.random.default_rng(7)
N, D, B = 8, 4000, 2000
for sa, sb in ((1.0, 1.0), (0.187, 0.237), (0.022, 0.021)):
    a = rng.normal(1.0, sa, (D, N)); b = rng.normal(0.0, sb, (D, N))
    his = []
    for s in range(0, D, 500):
        ia = rng.integers(0, N, (500, B, N)); ib = rng.integers(0, N, (500, B, N))
        diff = np.take_along_axis(np.broadcast_to(a[s:s+500, None], (500, B, N)), ia, 2).mean(2) - \
               np.take_along_axis(np.broadcast_to(b[s:s+500, None], (500, B, N)), ib, 2).mean(2)
        his.append(np.percentile(diff, 99.5, axis=1))
    hi = np.concatenate(his)
    p = np.mean(hi < 1.0)
    print(f"sd_a={sa} sd_b={sb}: P(hi < margin | shift = margin) = {p:.4f} (MC sd {np.sqrt(p*(1-p)/D):.4f}); nominal 0.005")
