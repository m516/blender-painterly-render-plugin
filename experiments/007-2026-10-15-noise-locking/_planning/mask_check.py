"""Pre-registration geometry check on the object-id maps only (no sum arrays are read)."""
import sys
import numpy as np
from pathlib import Path
from painterly_analysis import metrics, report, DIFFUSE_REGION_IDS
from painterly_analysis.experiment import load
from painterly_analysis.report import load_jobs_module

REPO = Path("/home/user/blender-painterly-render-plugin")
mod = load_jobs_module(REPO / "experiments/006-2026-10-09-jitter-units/jobs.py")
pairs, scale = int(sys.argv[1]), int(sys.argv[2])
ens = mod.build_ensembles(pairs, scale)
by_side = {}
for name, jobs in ens.items():
    side = dict(jobs[0].options)["size"]
    if side not in by_side:
        by_side[side] = np.asarray(load(jobs[0]).object_id)
LAGS = (1, 2, 3, 4, 6, 8, 12)
for side, oid in sorted(by_side.items()):
    e = side // 25
    masks = metrics.region_masks(report.diffuse_only(oid, DIFFUSE_REGION_IDS), e)
    print(f"side {side} erosion {e}: regions {sorted(masks)}")
    for r, m in sorted(masks.items()):
        m = np.asarray(m)
        n = int(m.sum())
        rows, cols = np.nonzero(m)
        nx = {L: int((m[:, :-L] & m[:, L:]).sum()) for L in LAGS if L < side}
        ny = {L: int((m[:-L] & m[L:]).sum()) for L in LAGS if L < side}
        zero = [L for L in LAGS if nx.get(L, 0) == 0 or ny.get(L, 0) == 0]
        print(f"  r{r}: N={n} bbox rows {rows.min()}-{rows.max()} cols {cols.min()}-{cols.max()} "
              f"centroid ({rows.mean():.1f}, {cols.mean():.1f}) min x-pairs {min(nx.values())} "
              f"min y-pairs {min(ny.values())} lags with no pairs {zero}")
