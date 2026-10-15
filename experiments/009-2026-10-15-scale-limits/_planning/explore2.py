import json, math, itertools
import numpy as np
from painterly_analysis import ensemble
P = json.load(open('/tmp/claude-0/-home-user-blender-painterly-render-plugin/98b29052-844f-5778-93d6-f67301038886/scratchpad/prereg/009/_planning/pairs006.json'))
regions = [2,3,4,5,6,7]
T = [f"r{r}.{k}" for r in regions for k in ("structure_std","slag.x","slag.y")]
def col(name, key): return np.array([p[key] for p in P[name]["scaled"]])
def amp(name): return np.mean([np.log(col(name, f"r{r}.structure_std")) for r in regions], axis=0)
for a,b in [("row_j0_s400","row_j0_s800"),("row_s400","row_s800"),("row_j0_s200","row_j0_s800"),("row_s200","row_s800"),("row_j0_s200","row_j0_s400"),("row_s200","row_s400")]:
    print(a,b,"A p=%.3g"%ensemble.permutation_pvalue(amp(a),amp(b)))
# sd ratio per doubling of f
r200 = [col("row_s200_px",k).std(ddof=1)/col("row_s200",k).std(ddof=1) for k in T]
r800 = [col("row_s800",k).std(ddof=1)/col("row_s800_px",k).std(ddof=1) for k in T]
allr = np.array(r200+r800)
print("sd ratio per doubling: 200px median %.3f, 800px median %.3f, pooled median %.3f, q75 %.3f, q90 %.3f" % (np.median(r200), np.median(r800), np.median(allr), np.quantile(allr,0.75), np.quantile(allr,0.9)))
print("geo mean pooled %.3f" % np.exp(np.mean(np.log(allr))))
# per-key deltas 200 vs 800
print("key  delta0  delta1400  se1400  phi(1400/0)")
for k in T:
    d0 = col("row_j0_s200",k).mean()-col("row_j0_s800",k).mean()
    d1 = col("row_s200",k).mean()-col("row_s800",k).mean()
    se1 = math.sqrt(col("row_s200",k).var(ddof=1)/8+col("row_s800",k).var(ddof=1)/8)
    se0 = math.sqrt(col("row_j0_s200",k).var(ddof=1)/8+col("row_j0_s800",k).var(ddof=1)/8)
    print(f"{k:20s} {d0:+.4f}({se0:.4f}) {d1:+.4f}({se1:.4f}) z1={d1/se1:+.2f}")
# x vs y
