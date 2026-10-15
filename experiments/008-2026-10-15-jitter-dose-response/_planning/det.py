"""Deterministic planning numbers for 008: f_c fit, model steps, q, rho, delta-method sds."""

import json
import math
from pathlib import Path

S = json.loads((Path(__file__).parent / "summary006.json").read_text())
REG = [2, 3, 4, 5, 6, 7]


def m(c, k):
    return S[c][k]["mean"]


def sd(c, k):
    return S[c][k]["sd"]


# (a) fit m = m0 - b log2(1 + f/f_c) to r4 at 800 px: f = 0, 1/2800, 1/1400 of the side.
y0, y1, y2 = (m(c, "r4.structure_std") for c in ("row_j0_s800", "row_s800_px", "row_s800"))
ratio = (y1 - y2) / (y0 - y1)


def g(x):  # x = (1/2800)/f_c
    return math.log((1 + 2 * x) / (1 + x)) / math.log(1 + x) - ratio


lo, hi = 0.01, 1000.0
for _ in range(200):
    mid = math.sqrt(lo * hi)
    if g(mid) > 0:  # ratio decreasing in x
        lo = mid
    else:
        hi = mid
x = math.sqrt(lo * hi)
fc = (1 / 2800) / x
b = (y0 - y1) / math.log2(1 + x)
print(f"r4 800px: {y0:.4f} {y1:.4f} {y2:.4f}; slope ratio {ratio:.4f}; x={x:.4f}; f_c = 1/{1/fc:.0f}; b={b:.4f}")
for xx, name in ((x, "fit"), (5.0, "f_c=1/14000")):
    u = [0, xx / 2, xx, 2 * xx, 4 * xx, 8 * xx]  # f/f_c on the grid 0,1/5600,...,1/350
    L = [math.log2(1 + v) for v in u]
    st = [L[i + 1] - L[i] for i in range(5)]
    q = [st[1] / st[0]] + [st[i + 1] / (2 * st[i]) for i in (1, 2, 3)]
    rho = [st[i + 1] / st[i] for i in (1, 2, 3)]
    mean23 = (st[2] + st[3]) / 2
    print(name, "grid f/f_c", [round(v, 3) for v in u[1:]])
    print("  steps", [round(v, 4) for v in st], "step/mean(step2,3)", [round(v / mean23, 4) for v in st])
    print("  q", [round(v, 4) for v in q], "rho", [round(v, 4) for v in rho], "median rho", round(sorted(rho)[1], 4))

# H1 table: per-doubling falls and 400 px sds; predicted d
print("\nH1 table")
dr = {}
for r in REG:
    k = f"r{r}.structure_std"
    f800 = m("row_s800", k) - m("row_s800_px", k)
    f200 = m("row_s200_px", k) - m("row_s200", k)
    s0, s1 = sd("row_j0_s400", k), sd("row_s400", k)
    d = ((f800 + f200) / 2) / ((s0 + s1) / 2)
    dr[r] = d
    print(r, round(f800, 3), round(f200, 3), round(s0, 3), round(s1, 3), "d", round(abs(d), 1),
          "800px 0->1/2800", round(m("row_s800_px", k) - m("row_j0_s800", k), 3))
json.dump({"d_r": {r: abs(v) for r, v in dr.items()}, "x_fit": x}, open(Path(__file__).parent / "pred.json", "w"))

# (b) delta method for rho_i with model steps scaled per region; sds: f0 -> sd(f0), others -> sd(f1400)
print("\nDelta method sd of rho_i (model f_c fit, steps scaled so mean(step2,3) = table mean fall)")
u = [0, x / 2, x, 2 * x, 4 * x, 8 * x]
L = [math.log2(1 + v) for v in u]
st_model = [L[i + 1] - L[i] for i in range(5)]
mean23 = (st_model[2] + st_model[3]) / 2
for r in REG:
    k = f"r{r}.structure_std"
    f800 = m("row_s800", k) - m("row_s800_px", k)
    f200 = m("row_s200_px", k) - m("row_s200", k)
    scale = ((f800 + f200) / 2) / mean23
    D = [scale * s for s in st_model]
    s_conf = [sd("row_j0_s400", k)] + [sd("row_s400", k)] * 5
    v = [c * c / 8 for c in s_conf]
    out = []
    for i in (1, 2, 3):
        rho = D[i + 1] / D[i]
        var_num = v[i + 2] + v[i + 1]
        var_den = v[i + 1] + v[i]
        cov = -v[i + 1]
        var = (var_num + rho * rho * var_den - 2 * rho * cov) / D[i] ** 2
        out.append(f"rho{i}={rho:.3f} sd {math.sqrt(var):.3f}")
    print(r, "; ".join(out))

# H4: margin half-widths, normal approx with percentile-bootstrap shrink sqrt(7/8)
print("\nH4 margin (sd f0, sd f1400 as proxy for f350)")
z995, z99 = 2.5758, 2.3263
rows = []
for r in REG:
    for c in "RGB":
        k = f"r{r}.mean.{c}"
        s0, s1 = sd("row_j0_s400", k), sd("row_s400", k)
        se = math.sqrt((s0**2 + s1**2) / 8)
        h = z995 * math.sqrt(7 / 8) * se
        dmax = 1 - h - z99 * se
        sp = math.sqrt((s0**2 + s1**2) / 2)
        rows.append((k, sp, se, h, dmax))
for k, sp, se, h, dmax in sorted(rows, key=lambda t: t[1]):
    print(f"{k}: pooled sd {sp:.3f} se {se:.4f} 99% half-width {h:.3f} max true shift for P(inside)>=0.99 {dmax:.3f}  |d|=4 shift {4*sp:.3f}")
