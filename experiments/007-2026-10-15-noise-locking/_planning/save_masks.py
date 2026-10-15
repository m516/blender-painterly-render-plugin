"""Save the eroded region masks (e = s/25) of the cached 006 object-id maps (geometry only)."""
import numpy as np
from pathlib import Path
from painterly_analysis import metrics, report, DIFFUSE_REGION_IDS
from painterly_analysis.experiment import load
from painterly_analysis.report import load_jobs_module
OUT = Path(__file__).resolve().parent
REPO = Path("/home/user/blender-painterly-render-plugin")
ens = load_jobs_module(REPO / "experiments/006-2026-10-09-jitter-units/jobs.py").ENSEMBLES
for name, side in (("row_s200", 200), ("row_s400", 400), ("row_s800", 800)):
    oid = np.asarray(load(ens[name][0]).object_id)
    for r, m in metrics.region_masks(report.diffuse_only(oid, DIFFUSE_REGION_IDS), side // 25).items():
        np.save(OUT / f"mask_{side}_r{r}.npy", np.asarray(m))
print("ok")
