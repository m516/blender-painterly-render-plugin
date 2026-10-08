# Painterly specification (normative)

Status: v1, 2026-10-08. Owner: Opus (only Opus edits this file). Cite sections as `SPEC §n`.

Line numbers like `painterly.cpp:262` refer to `third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp`
(the 2018 GUI-archive version, which produced `tests/data/reference/smallpaint_painterly.ppm`).

## §0 Terms

| Term | Meaning |
|---|---|
| **pass** | One sample per pixel over the whole image. smallpaint's GUI port loops passes outermost (`painterly.cpp:282`). |
| **row / col** | Displayed image coordinates. `row` 0 is the top. smallpaint's loop index `i` is the row and `j` is the column: `pix[j][i]` is displayed at `(col=j,row=i)` (`painterly.cpp:295`, `mainrenderdistributor.cpp:71`). |
| **K** | The painterly sequence counter (§2). |
| **chain** | The set of pixel samples that share one running K (§3). |
| **lane** | L consecutive pixels of one row (§3). |
| **ghost sphere** | A sphere intersected with smallpaint's unit-direction assumption (§5). |
| **spiral frame** | The 3×3 rotation F that orients the spiral (§1, §4). |
| **reference scene** | The GUI scene (§9). |
| **reference image** | `tests/data/reference/smallpaint_painterly.ppm` (P6, 400×400). |

## §1 Frames

smallpaint coordinates are (x, y, z) = (image down, image right, toward the camera). The camera sits at the origin
looking down −z (`camcr`, `painterly.cpp:171-179`).

In Blender camera space (+X right, +Y up, −Z forward) the smallpaint axes are
`x̂_s = −Y_cam`, `ŷ_s = +X_cam`, `ẑ_s = +Z_cam`. Write this as `M_s→cam`, the matrix with columns (0,−1,0), (1,0,0), (0,0,1).

The spiral frame F maps spiral-local coordinates to world coordinates. It is chosen by the knob `spiral_frame`:
- `camera` (Blender default): `F = R_cam→world · M_s→cam · R(spiral_rotation)`.
- `world`: `F = R(spiral_rotation)`.
- `object`: `F = R_obj→world · R(spiral_rotation)`, where R_obj is the orthonormalized rotation of the chosen object.
- `smallpaint` (reference scenes, which are authored in smallpaint coordinates): `F = I`.

`spiral_rotation` is an XYZ Euler rotation in radians. It defaults to (0,0,0).

## §2 Sequence counter and random numbers

**Painterly value.** `vdc(K) = bitrev23(K mod 2^23) · 2^-23`, where `bitrev23` reverses the low 23 bits.
- 2^23 is not a tuning constant. It is the period of smallpaint's incremental `Halton::next()` in IEEE double.
  - next() equals vdc(K) bit for bit for K < 2^23.
  - From K = 2^23 on it differs at *every* draw: |error| < 1e-7 (max 9.31e-8 over 200 periods), and values can be slightly
    negative (min −7.45e-8). This is the "1e-7" guard in `Halton::next()` misfiring once the step is smaller than the guard.
- The oracle keeps the original incremental generator by default (`--halton incremental`) or uses `vdc` (`--halton exact`).
  - Reference-mode image chains run almost entirely past 2^23.
  - **Bit-parity tests therefore always run the oracle with `--halton exact`.** Statistical tests may use either.

**Draw.** A diffuse event does `K ← K + 1; u = vdc(K)`, so the increment comes *before* use (`painterly.cpp:203-205`).
- Both spiral dimensions use u: `u1 = u2 = u`, because both Halton objects are base 2 and advance in lockstep (`painterly.cpp:276-278`).
- Only diffuse events advance K. Mirror, glass, emission, misses and depth termination never advance K.

**Stateless RNG.** Every other random decision uses Cycles' `hash_uint4` and `hash_uint3`
(Blender v5.2.2 `intern/cycles/util/hash.h`, vendored verbatim):
```
rng_u32(seed, purpose, depth, a, b, c) = hash_uint4(hash_uint3(seed, purpose, depth), a, b, c)
rng_unit(...)   = (double)rng_u32(...) * 0x1p-32  ∈ [0, 1)      # evaluated in double, always
rng_signed(...) = 2 * rng_unit(...) - 1            ∈ [−1, 1)
```
Both are evaluated in **double**: in float32, `u32 · 2^-32` rounds to 1.0 for the top 128 values.
Purposes:
- `PURPOSE_JITTER_X = 0`, `PURPOSE_JITTER_Y = 1`: (a,b,c) = (row, col, pass), depth 0.
- `PURPOSE_U2 = 2`: only when `u2_mode = independent`. (a,b,c) = (row, col, pass), depth = bounce depth.
- `PURPOSE_CLOSURE = 3`: closure selection. (a,b,c) = (row, col, pass), depth = bounce depth.
- `PURPOSE_LANE_K0 = 4`: (a,b,c) = (row, lane_in_row, pass), depth 0.

## §3 Chains

The knob `chain` selects how K is carried between samples:

- **`image`** (reference mode).
  - One chain covers the whole render in the order `for pass, for row, for col` (`painterly.cpp:282-301`). It is single-threaded.
  - K starts at 0 at the beginning of the render and is never reset, including across passes.
  - This is the semantics of the shipped Linux GUI binary, whose `-openmp` flag disabled OpenMP.
- **`row`.** One chain per (row, pass), walking columns left to right. `K0 = rng_u32(seed, PURPOSE_LANE_K0, 0, row, 0, pass) mod 2^22`.
- **`lane`** (artist mode; knob `lane_length` = L ≥ 1, default 16).
  - Each row is split into lanes `[j0, j0+L)` with `j0 = L·lane_in_row` in *global* image coordinates; the last lane may be shorter.
  - One chain per (lane, pass), walking columns left to right. `K0 = rng_u32(seed, PURPOSE_LANE_K0, 0, row, lane_in_row, pass) mod 2^22`.
- **`omp-restart:T`** (oracle only, for experiments). This deterministically emulates the Windows OpenMP build:
  - T virtual threads; row i belongs to thread `i mod T`.
  - Each thread walks its rows in increasing order with its own K.
  - Every thread resets K to 0 at the start of each pass.
- **`pixel-major`** (oracle only). The standalone 2016 program's loop order (`for row, for col, for pass`) as one chain from K = 0.
  This is the non-OpenMP semantics.
- **`pixel-major-omp:T`** (oracle only). The standalone as distributed: it was built with `-fopenmp`.
  - T virtual threads; row i belongs to thread `i mod T`.
  - Each thread walks its rows in increasing order (`for col, for pass`) with one K that starts at 0 and is never reset.

Notes:
- 2^22 bounds K0 so that a chain consuming fewer than 2^22 draws never reaches the 2^23 wrap. That keeps every value in
  the original generator's exact range and representable exactly in float32.
- A chain processes its pixels strictly in order, and each pixel's whole path finishes before the next pixel starts.
- Lanes are independent of each other and of thread scheduling. Output is therefore bit-identical for any thread count or
  batch size.

## §4 Diffuse bounce (smallpaint type 1)

At hit point P with shading normal N (unit), where smallpaint's diffuse `cl` = `color`:
```
K ← K + 1;  u = vdc(K);  u1 = u;  u2 = (u2_mode == same) ? u : rng_unit(PURPOSE_U2 …)
s = ( cos(2π·u2)·sqrt(1 − u1²),  sin(2π·u2)·sqrt(1 − u1²),  u1 )        # hemisphere(), painterly.cpp:183-187
d = N + F·s                                                               # painterly.cpp:205 — NOT rotated into N's frame
d ← d · |d|^(−α)                                                          # knob alpha, default 0 (exact no-op: pow(L,−0)=1)
cost = d·N                                                                # painterly.cpp:206, uses the unnormalized d
```
- The new ray is `(P, d)` and d is **not normalized**.
- The child radiance contributes per channel as `L += (cost · (L_child · color)) · diffuse_gain`, in exactly this order
  (`painterly.cpp:209-211`).
- `cost ∈ [0, 2]` when α = 0.
- `u2_mode` is a knob: `same` (default) or `independent`. The oracle also offers `base3`, a second Halton sequence in base 3.
- **Reference values:** `color = cl` (0…12) and `diffuse_gain = 0.1`.
- **Blender values:** `color` = closure albedo (≈0…1) and `diffuse_gain = 1.0` (the knob default).

## §5 Ghost spheres

smallpaint's sphere test (`painterly.cpp:100-109`) assumes |d| = 1:
```
b = dot((o − c)·2, d);   c' = dot(o − c, o − c) − r²;   disc = b² − 4c'
if disc < 0: miss;  q = sqrt(disc);  sol1 = −b + q;  sol2 = −b − q
t_sphere = (sol2 > eps) ? sol2/2 : ((sol1 > eps) ? sol1/2 : 0)
hit iff t_sphere > eps                       # Scene::intersect, painterly.cpp:138 — the far root is NOT tried
```
- `eps = 1e-4` (`painterly.cpp:39`).
- The hit point is `o + t·d` with t parametric along the unnormalized d.
- The normal is `normalize(P − c)` from the **true** centre (`painterly.cpp:112`).
- **Geometric meaning.** For |d| = L the test hits the sphere centred at `o + L²(c − o)` with radius `L·sqrt((L²−1)|o−c|² + r²)`.
  For r → 0 that is a cone of half-angle `acos(1/L)`.
- **Ghost policy** (oracle knob `--ghost`):
  - `all`: the original behaviour.
  - `lights`: only emissive spheres are ghosts; other spheres use the exact quadratic (below).
  - `none`: every sphere uses the exact quadratic.
- **Exact quadratic** (non-ghost spheres):
  ```
  a = dot(d,d);  b = dot((o − c)·2, d);  c' = dot(o − c, o − c) − r²;  disc = b² − 4·a·c'
  if disc < 0: miss;  q = sqrt(disc);  sol1 = −b + q;  sol2 = −b − q
  t = (sol2 > eps) ? sol2/(2a) : ((sol1 > eps) ? sol1/(2a) : 0)
  hit iff t > eps
  ```
  - The eps comparison acts on the *undivided* roots, exactly as in the ghost branch.
  - With a == 1 the expression equals the original bit for bit, apart from `/(2a)` vs `/2`, which agree when a = 1.
- **Blender.**
  - Point and spot lights are ghost spheres with `r = shadow_soft_size`; r = 0 is allowed and still produces the cone.
  - Spot lights multiply their emission by Blender's spot cone falloff, evaluated at the direction from the centre to the
    *true* hit direction.
  - Ghost spheres are intersected by brute force outside any BVH, because ghost radii are unbounded.

## §6 Path

The path follows `trace()` (`painterly.cpp:189-239`).

**Termination and hits.**
- `if depth ≥ max_depth: return 0` *before* intersecting. `max_depth` is a knob, reference value 20.
- A miss returns the world/background radiance. The reference scene is closed and never misses.
- On a hit the path first adds emission, `L = 0 + (E·emission_gain)` per channel, with reference `emission_gain = 2`
  (`painterly.cpp:200`). Then it continues by the material type:
  - **Diffuse:** §4.
  - **Mirror:** `cost = dot(d, N); d ← normalize(d − N·(2·cost))`; then `L += L_child` (`painterly.cpp:213-219`).
  - **Glass** (`painterly.cpp:221-238`).
    - `n = ior`. If `dot(N, d) > 0`, then `N ← −N` and `n ← 1/n`. Then `n ← 1/n` unconditionally.
    - `cost1 = −dot(N, d); cost2 = 1 − n²(1 − cost1²)`.
    - If `cost2 > 0`: `d ← normalize(d·n + N·(n·cost1 − sqrt(cost2)))` and `L += L_child`.
    - Otherwise this is total internal reflection (TIR): **return L** (emission only).
    - The *incoming* d may be unnormalized after a diffuse bounce, and smallpaint uses it as-is. Reference mode does the same.
- **Emitters are surfaces.** In smallpaint the light is a type-1 diffuse sphere with `cl = 0` (`painterly.cpp:262`).
  - After its emission the path keeps bouncing with zero throughput and keeps consuming K.
  - The knob `continue_after_emitter` (default true) controls this.
- **No Russian roulette, no next-event estimation, no MIS, no clamping, no adaptive sampling.**

**Evaluation order.** The recursion `L_d = E_d·g + f(L_{d+1})` may be implemented iteratively. To stay bit-identical
with the oracle, record the per-depth terms and evaluate them backward with the same operation order.

**Blender extras** (absent from smallpaint):
- Area lights are emissive quads (no ghosting).
- The sun is an angular disk seen by escaping rays.
- The world shader is evaluated on a miss and scaled by `emission_gain`.

## §7 Camera, jitter, film

**smallpaint camera** (camera type `smallpaint`, reference scenes only; `painterly.cpp:171-179, 289-293`):
```
fovx = float(PI/4);  fovy = float((h/w)·fovx)          # PI = 3.1415926536, smallpaint's macro (painterly.cpp:33)
cam  = ( ((2·row − w)/w)·tan((double)fovx) + jx,  ((2·col − h)/h)·tan((double)fovy) + jy,  −1 )
ray  = (origin 0, normalize(cam))
jx = rng_signed(seed, PURPOSE_JITTER_X, 0, row, col, pass) · jitter;  jy likewise with PURPOSE_JITTER_Y
```
- `tan` is evaluated in **double** on the float-rounded angle, as in the shipped GCC 5.4 binary that rendered the reference.
  Current libstdc++ would resolve `tan(float)` to the float overload and fold it to exactly 1.0f. The oracle and the core
  both write `tan((double)fovx)` explicitly.
- Reference `jitter = 1/700` image-plane units (`painterly.cpp:291-292`).
- Note the GUI quirk: `w` (width) scales the *row* term. The reference image is square, so this is harmless.

**Perspective camera** (Blender): built from `calc_matrix_camera` and `matrix_world`. Jitter is a knob in pixels whose
default comes from the X-resolution experiment.

**Film.**
- The film accumulates `sum += L` per pixel in pass order.
- `chain` and `lane` determine the order *within* a pass, but each pixel's sum is always taken in increasing pass order.

**Display mapping (smallpaint).**
- `byte = min((int)sum / s, 255)` per channel: C++ truncation, then integer division by the number of completed passes
  `s` (`mainrenderdistributor.cpp:71`).
- No gamma is applied.

## §8 Output and knobs

**Output mode** (knob `output_mode`):
- `display_referred` (default): write `srgb_to_linear(min(L/255, 1))` into the Combined pass. Under Blender's
  *Standard* view transform with dither 0, this reproduces smallpaint's bytes up to rounding.
- `scene_linear`: write `L/255 · exposure`.
- The engine never changes the scene's view transform by itself. A preset or operator does that.

**Knobs** live on `PainterlyIntegrator` (C++ reflection). Blender properties are generated from them, and every default
equals the reference behaviour unless noted:

| Group | Knobs |
|---|---|
| Sampling | `chain`, `lane_length` (16), `seed`, `seed_per_frame` (false), `passes` |
| Brush | `spiral_frame`, `spiral_rotation`, `u2_mode`, `k0_phase_lock_bits` (0; when q > 0, K0 ← K0 with its low q bits cleared) |
| Path | `alpha` (0), `max_depth` (20), `diffuse_gain` (Blender 1.0), `emission_gain` (2), `continue_after_emitter` (true) |
| Lights | `emission_scale` (calibrated by X-ghost-lights), `ghost_lights` (true) |
| Film | `output_mode`, `exposure`, `jitter` |

## §9 Reference scene (GUI)

Objects in list order; the order is the object id used by masks (`painterly.cpp:252-262`):

| id | object | geometry | `cl` | emission | type |
|---|---|---|---|---|---|
| 0 | middle sphere | r 1.05, c (1.45, −0.75, −4.4) | (4, 8, 4) | 0 | mirror |
| 1 | right sphere | r 0.5, c (2.05, 2.0, −3.7) | (10, 10, 1) | 0 | glass |
| 2 | left sphere | r 0.6, c (1.95, −1.75, −3.1) | (4, 4, 12) | 0 | diffuse |
| 3 | bottom plane | d 2.5, n (−1, 0, 0) | (6, 6, 6) | 0 | diffuse |
| 4 | back plane | d 5.5, n (0, 0, 1) | (6, 6, 6) | 0 | diffuse |
| 5 | left plane | d 2.75, n (0, 1, 0) | (10, 2, 2) | 0 | diffuse |
| 6 | right plane | d 2.75, n (0, −1, 0) | (2, 10, 2) | 0 | diffuse |
| 7 | ceiling plane | d 3.0, n (1, 0, 0) | (6, 6, 6) | 0 | diffuse |
| 8 | front plane | d 0.5, n (0, 0, −1) | (6, 6, 6) | 0 | diffuse |
| 9 | light | r 0.5, c (−1.9, 0, −3) | (0, 0, 0) | 120 | diffuse |

- **Planes** satisfy `n·p + d = 0`, intersected as `t = −(n·o + d)/(n·d)` and accepted when `t > eps` (`painterly.cpp:84-90`).
- **Spheres** take their normal from the true centre.
- **Glass** IOR is 1.5 (GUI default; `refr_index`). The GUI defaults are 512² and 50 spp. The reference image is 400².

**Standalone 2016 scene** (`--scene standalone`, for the showcase preset experiment only). It differs as follows:
- size 900², 8 spp, IOR 1.9;
- right sphere r 0.45 at (2.05, 0.8, −3.7);
- light radius `eps` (1e-4);
- sphere normal `(P − c)/r` (unnormalized);
- loop order `pixel-major`.
