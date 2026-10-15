import itertools, json, math
import numpy as np
P = json.load(open('/tmp/claude-0/-home-user-blender-painterly-render-plugin/98b29052-844f-5778-93d6-f67301038886/scratchpad/prereg/009/_planning/pairs006.json'))
regions = [2,3,4,5,6,7]
T = [f"r{r}.{k}" for r in regions for k in ("structure_std","slag.x","slag.y")]
def col(name, key): return np.array([p[key] for p in P[name]["scaled"]])
idx = np.array(list(itertools.combinations(range(16), 8)))
def exact_p(x, y):
    pooled = np.concatenate([x, y], axis=1); total = pooled.sum(1, keepdims=True)
    sx = pooled[:, idx].sum(-1); stat = sx/8 - (total-sx)/8; obs = stat[:, :1]
    tol = 16*np.finfo(float).eps*np.abs(pooled).max(1, keepdims=True)
    return (np.abs(stat) >= np.abs(obs)-tol).sum(1)/idx.shape[0]
def holm_any(pmat, alpha):  # pmat sims x keys
    ps = np.sort(pmat, 1); m = ps.shape[1]
    thr = alpha / (m - np.arange(m))
    ok = ps <= thr
    # number rejected = first failure index
    first_fail = np.where(~ok, np.arange(m), m).min(1)
    return first_fail
rng = np.random.default_rng(2)
# MDE table
print("MDE (4 x sd800) per key, jit / zero:")
for k in T:
    print(f"  {k:18s} jit {4*col('row_s800',k).std(ddof=1):.4f} (mean {col('row_s800',k).mean():.4f})  zero {4*col('row_j0_s800',k).std(ddof=1):.4f} (mean {col('row_j0_s800',k).mean():.4f})")
sims = 300
for fam in ("row_s", "row_j0_s"):
    m4 = np.array([col(fam+"400",k).mean() for k in T]); s4 = np.array([col(fam+"400",k).std(ddof=1) for k in T])
    m8 = np.array([col(fam+"800",k).mean() for k in T]); s8 = np.array([col(fam+"800",k).std(ddof=1) for k in T])
    for Q in (0.0, 0.37, 1.0):
        for sdf_name, sdf in (("sd1600=sd800", 1.0), ("sd1600=sd800/2", 0.5)):
            m16 = m8 + Q*(m8-m4); s16 = s8*sdf
            nb = []; nc = []
            for s in range(sims):
                x4 = rng.normal(m4, s4, (8, 18)); x8 = rng.normal(m8, s8, (8, 18)); x16 = rng.normal(m16, s16, (8, 18))
                pb = exact_p(x8.T, x16.T); pc = exact_p(x4.T, x16.T)
                nb.append(holm_any(pb[None], 0.01/3)[0]); nc.append(holm_any(pc[None], 0.01/3)[0])
            nb = np.array(nb); nc = np.array(nc)
            print(f"{fam} Q={Q} {sdf_name}: P(C_B>=1)={np.mean(nb>0):.2f} mean {nb.mean():.2f}; P(C_C>=1)={np.mean(nc>0):.2f} mean {nc.mean():.2f}")
