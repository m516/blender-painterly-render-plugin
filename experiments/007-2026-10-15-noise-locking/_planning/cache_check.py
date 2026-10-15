"""Pre-registration design check: cache completeness and wall_seconds (no noise data is read)."""
import json, os, sys
from pathlib import Path
from painterly_analysis.experiment import job_key, cache_root, _oracle_sha256
from painterly_analysis.report import load_jobs_module

REPO = Path("/home/user/blender-painterly-render-plugin")
mod = load_jobs_module(REPO / "experiments/006-2026-10-09-jitter-units/jobs.py")
pairs, scale = int(sys.argv[1]), int(sys.argv[2])
ens = mod.build_ensembles(pairs, scale)
print("oracle sha", _oracle_sha256()[:16], "cache", cache_root())
done = 0; total = 0; wall = {}
for name, jobs in ens.items():
    for job in jobs:
        total += 1
        d = cache_root() / job_key(job)
        if (d / "done").is_file():
            done += 1
            meta = json.loads((d / "meta.json").read_text())
            side = dict(job.options)["size"]
            wall.setdefault(side, []).append(float(meta.get("wall_seconds", float("nan"))))
print(f"done {done} of {total}")
tot = 0.0
for side in sorted(wall):
    w = wall[side]; tot += sum(w)
    print(side, len(w), f"mean {sum(w)/len(w):.2f} s total {sum(w):.1f} s")
print(f"total wall {tot:.1f} s")
