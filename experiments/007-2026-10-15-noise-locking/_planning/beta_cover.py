"""Coverage of the E1 white-model beta interval against the display-corrected prediction."""
import glob, json, math
from pathlib import Path
HERE = Path(__file__).resolve().parent
sd2 = 5573.6 / 64
pred = math.log2((sd2 + 1 / 12) / (sd2 / 4 + 1 / 12))
print("prediction", pred)
for c in ("b", "a"):
    n = hit = 0
    pts = []
    for f in glob.glob(str(HERE / "beta64_*.jsonl")):
        for line in open(f):
            d = json.loads(line)
            if d["model"] != "white":
                continue
            p, lo, hi = d[c]["beta"]
            n += 1; hit += lo <= pred <= hi; pts.append(p)
    if n:
        m = sum(pts) / n
        sd = (sum((x - m) ** 2 for x in pts) / (n - 1)) ** 0.5 if n > 1 else float("nan")
        print(c, f"seeds {n} covered {hit} ({hit / n:.3f}) mean beta {m:.4f} sd {sd:.4f}")
