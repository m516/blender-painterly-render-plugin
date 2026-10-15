import itertools, math, json
import numpy as np
from scipy.stats import norm
P = json.load(open('/tmp/claude-0/-home-user-blender-painterly-render-plugin/98b29052-844f-5778-93d6-f67301038886/scratchpad/prereg/009/_planning/pairs006.json'))
def col(name, key): return np.array([p[key] for p in P[name]["scaled"]])
X = ["r3.slag.x", "r4.slag.x"]
rng = np.random.default_rng(1)
idx = np.array(list(itertools.combinations(range(16), 8)))
def exact_p(x, y):
    pooled = np.concatenate([x, y], axis=1); total = pooled.sum(1, keepdims=True)
    sx = pooled[:, idx].sum(-1); stat = sx/8 - (total-sx)/8; obs = stat[:, :1]
    tol = 16*np.finfo(float).eps*np.abs(pooled).max(1, keepdims=True)
    return (np.abs(stat) >= np.abs(obs)-tol).sum(1)/idx.shape[0]
def approx_p(x, y):
    n, m = x.shape[1], y.shape[1]
    se = np.sqrt(x.var(1, ddof=1)/n + y.var(1, ddof=1)/m)
    return 2*norm.sf(np.abs(x.mean(1)-y.mean(1))/se)
den200 = np.stack([col("row_s200", k) for k in X], 1)  # 8 x 2
den800 = np.stack([col("row_s800", k) for k in X], 1)
dX = (den200.mean(0) - den800.mean(0))  # per key
print("delta(1/1400) per key", dX, "sum", dX.sum())
sd200 = den200.std(0, ddof=1); sd800 = den800.std(0, ddof=1)
B = 2000; sims = 400
for factor_name, factor in [("typical x1.23", 1.12**1.807), ("pessimistic x1.86", 1.41**1.807)]:
    for npairs in (8, 16):
        for phi in (0.0, 0.5, 1.0):
            classes = {"removed":0, "reduced":0, "unchanged":0, "grows":0, "reversed":0, "inconclusive":0}
            rej = 0
            for s in range(sims):
                mu800 = den800.mean(0)
                y800 = rng.normal(mu800, sd800*factor, (npairs, 2))
                y200 = rng.normal(mu800 + phi*dX, sd200*factor, (npairs, 2))
                # H3 rejection for X keys at first Holm threshold 0.01/18
                if npairs == 8:
                    p = exact_p(y200.T, y800.T)
                else:
                    p = approx_p(y200.T, y800.T)
                if p.min() <= 0.01/18: rej += 1
                # bootstrap phi
                i1 = rng.integers(0, npairs, (B, npairs)); i2 = rng.integers(0, npairs, (B, npairs))
                j1 = rng.integers(0, 8, (B, 8)); j2 = rng.integers(0, 8, (B, 8))
                num = (y200[i1].mean(1) - y800[i2].mean(1)).sum(-1)
                den = (den200[j1].mean(1) - den800[j2].mean(1)).sum(-1)
                ph = num/den
                lo, hi = np.percentile(ph, [0.5, 99.5])
                if hi < 0: c = "reversed"
                elif lo > 1: c = "grows"
                elif hi < 1 and lo <= 0: c = "removed"
                elif hi < 1 and lo > 0: c = "reduced"
                elif lo > 0 and hi >= 1: c = "unchanged"
                else: c = "inconclusive"
                classes[c] += 1
            print(factor_name, "pairs", npairs, "phi", phi, "H3 P(reject a X key)=%.2f" % (rej/sims), {k: round(v/sims, 3) for k, v in classes.items() if v})
