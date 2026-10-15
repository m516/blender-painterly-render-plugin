"""H1 alternative: one Holm family of 60 (30 'lower' + 30 'higher'), all 30 falls at d = 4: P(all 30 falls rejected)."""
import numpy as np
from sim import perm_counts, holm_all_rejected, NS, N
rng = np.random.default_rng(1)
D = 1000
for d in (3.5, 4.0):
    x = rng.normal(-d, 1, (D * 30, N)); y = rng.normal(0, 1, (D * 30, N))
    l, g = perm_counts(x, y)
    p = np.concatenate([(l / NS).reshape(D, 30), (g / NS).reshape(D, 30)], axis=1)
    rej = holm_all_rejected(p, 0.01)
    print(f"d={d}: 60-family P(all 30 falls) {rej[:, :30].all(1).mean():.3f}; 30-family {holm_all_rejected(p[:, :30], 0.01).all(1).mean():.3f}")
