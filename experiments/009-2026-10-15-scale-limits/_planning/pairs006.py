"""Planning only: per-pair 006 metrics of the cached row-chain configurations (no new renders)."""

import importlib.util
import json
import sys
import time
from pathlib import Path

REPO = Path("/home/user/blender-painterly-render-plugin")
EXP = REPO / "experiments" / "006-2026-10-09-jitter-units"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


an = load(EXP / "analyze.py", "a006")
jobs = load(EXP / "jobs.py", "j006")
ens = jobs.build_ensembles(8, 1)
names = sys.argv[1:]
from painterly_analysis.experiment import load as load_render  # noqa: E402

out = {}
measured = [2, 3, 4, 5, 6, 7]
for name in names:
    t = time.time()
    side = an.TABLE[name][0]
    notes = []
    params = an.side_params(side, 400, 1, notes)
    oid = load_render(ens[name][0]).object_id
    scaled, fixed, profile, digests = an._measure_configuration(name, ens[name], oid, params, measured)
    out[name] = {"scaled": scaled, "profile": profile}
    print(name, round(time.time() - t, 1), flush=True)
dst = Path(__file__).parent / "pairs006.json"
old = json.loads(dst.read_text()) if dst.exists() else {}
old.update(out)
dst.write_text(json.dumps(old, indent=1))
