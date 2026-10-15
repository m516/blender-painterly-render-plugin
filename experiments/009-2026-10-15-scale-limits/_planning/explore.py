import json, math
import numpy as np
P = json.load(open('/tmp/claude-0/-home-user-blender-painterly-render-plugin/98b29052-844f-5778-93d6-f67301038886/scratchpad/prereg/009/_planning/pairs006.json'))
R = json.load(open('/home/user/blender-painterly-render-plugin/experiments/006-2026-10-09-jitter-units/results.json'))
regions = [2,3,4,5,6,7]
T = [f"r{r}.{k}" for r in regions for k in ("structure_std","slag.x","slag.y")]
def col(name, key): return np.array([p[key] for p in P[name]["scaled"]])
# consistency with 006 summary
bad = 0
for name in P:
    for key in T:
        m = R["summary"][name][key]["mean"]; s = R["summary"][name][key]["sd"]
        v = col(name,key)
        if v.mean() != m or v.std(ddof=1) != s: bad += 1
print("summary mismatches", bad)
def amp(name):
    return np.mean([np.log(col(name, f"r{r}.structure_std")) for r in regions], axis=0)
for name in sorted(P):
    a = amp(name)
    print(f"{name:14s} A mean {a.mean():.5f} sd {a.std(ddof=1):.5f}")
def d(a,b):
    sp = math.sqrt(((len(a)-1)*a.var(ddof=1)+(len(b)-1)*b.var(ddof=1))/(len(a)+len(b)-2))
    return (a.mean()-b.mean())/sp
for fam in ("row_s","row_j0_s"):
    a2,a4,a8 = amp(fam+"200"),amp(fam+"400"),amp(fam+"800")
    print(fam, "A steps 200->400 %.4f (d %.2f), 400->800 %.4f (d %.2f)" % (a4.mean()-a2.mean(), d(a4,a2), a8.mean()-a4.mean(), d(a8,a4)))
# correlation among regions within config (log ss)
for name in ("row_s400","row_j0_s400","row_s800","row_j0_s800"):
    M = np.array([np.log(col(name, f"r{r}.structure_std")) for r in regions])
    C = np.corrcoef(M)
    print(name, "mean offdiag corr %.2f" % ((C.sum()-6)/30))
