# smallpaint_oracle: changes relative to the original

Base: `third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp` (306 lines, CRLF). Line numbers below are
the original's. "new" means code with no original line. `trace()`, `Vec`, `Ray`, `Obj`, `Plane`, `hemisphere()` and the
glass and mirror branches are unchanged except where listed.

1. **Line endings.** CRLF converted to LF for the whole file (original lines 1-306). Original tabs kept.
2. **Header.** Original lines 1-8 (MIT header comment) unchanged. New line after them:
   `// Modified by the Painterly project: headless reference oracle (see src/app/CHANGES.md).`
3. **Includes.** Removed `#include <ctime>` (line 14, `time()` is no longer used) and `#include "../src_gui/main.h"`
   (line 18, GUI). Added the standard headers `<algorithm> <atomic> <cerrno> <chrono> <cmath> <cstdint> <filesystem>
   <thread>` and `"smallpaint_oracle_hash.h"`. New `// clang-format off` before the includes; it is closed at the end of
   the file (the whole file is excluded from clang-format so that the original formatting is kept).
4. **Random seed and RND macros removed.** Original lines 22-31: `unsigned int seed = time(NULL);`, `RND` and `RND2`
   (`rand_r` on Linux, `rand` on Windows). Jitter uses the stateless RNG instead (item 14). `srand(time(NULL))` in
   `render()` (line 242) is removed too (item 13).
5. **Kept.** `PI`, `MIN`, `MAX`, `width`/`height`, `inf`, `eps`, `using namespace std`, `pl` (original lines 33-41).
6. **Knob globals.** New after line 41: `GhostPolicy`, `U2Mode`, `SceneKind`, `ChainKind` enums; `g_halton_exact`,
   `g_ghost`, `g_alpha`, `g_u2`, `g_continue_after_emitter`, `g_scene`, `g_jitter` (default `1.0 / 700.0`, the original
   `RND / 700` of lines 291-292); `PathContext` and `thread_local g_path` (item 4 of the card). All are set once in `main`
   before any thread starts.
7. **Vec, Ray, Obj, Plane** (original lines 43-92). Unchanged.
8. **Sphere::intersect** (lines 100-109). The original body (lines 101-108) is now the branch taken for `--ghost all`
   and for `--ghost lights` on emitters (`emission > 0`). Otherwise the new `intersect_exact()` runs: the SPEC §5 exact
   quadratic, with eps tests on the undivided roots and division by `2a`. The new `intersect_exact()` has no original
   line.
9. **Sphere::normal** (lines 111-113). GUI formula `(p0 - c).norm()` unchanged. With `--scene standalone` it returns
   `(P - c) / r` (standalone source lines 107-111).
10. **Scene::index_of** (new, after line 144). Scene-list index of an object, used for `object_id.npy` (SPEC §9).
11. **Halton** (lines 147-169).
    - New `halton_vdc2()` before line 147: SPEC §2 `vdc(K) = bitrev23(K mod 2^23) * 2^-23`, bit-reversal loop.
    - New members `int base_` and `uint64_t index` (the K counter). `number(i, base)` sets `index = i`, `next()` does
      `index++`.
    - Exact branch (`g_halton_exact` and base 2) in `number()`, after original line 152, and in `next()`, after
      `index++` and before original line 160. Incremental mode runs the original lines 150-167 unchanged.
12. **camcr** (lines 171-179). `tan(fovx)` (line 176) becomes `tan((double)fovx)`, and `tan(fovy)` (line 177) becomes
    `tan((double)fovy)`. The shipped GCC 5.4 binary evaluated tan in double. Current libstdc++ resolves `tan(float)` to
    the float overload, which folds to exactly 1.0f for pi/4 (SPEC §7).
13. **trace** (lines 189-239).
    - New `--continue-after-emitter no` return after the emission line 200. The return fires when `emission > 0`.
    - Line 205, `ray.d = (N + hemisphere(hal.get(), hal2.get()));`, becomes:
      - `u2` selection: `hal2.get()` for `same` and `base3`; `rng_unit(seed, PURPOSE_U2, depth, row, col, pass)` for
        `independent`. `hal.next()` and `hal2.next()` (lines 203-204) are unchanged.
      - The same line with `hemisphere(hal.get(), u2)`.
      - New line `ray.d = ray.d * pow(ray.d.length(), -g_alpha);` (`--alpha`; exact no-op at 0).
    - The remaining lines (depth limit 190, intersection 192-200, diffuse gain 209-211, mirror 214-220, glass 222-238)
      are unchanged.
14. **render()** (lines 240-305) is replaced by the functions below. Its statements map as follows:
    - Lines 243-262, scene construction: `build_scene()`. GUI values unchanged. The right sphere (line 253, GUI
      r 0.5 and c (2.05, 2.0, -3.7)) and the light radius (line 262, GUI r 0.5) differ from standalone (source lines 224,
      234: r 0.45 at (2.05, 0.8, -3.7), and r = eps for the light). Both are selected by `--scene`.
    - Lines 264-265, `params["refr_index"]` and `params["spp"]`: kept, in `oracle_main()`.
    - Lines 267-268, `width`/`height`: set in `oracle_main()` from `--size`.
    - Lines 270-273, `pix` allocation: replaced by `Film` (see item 16).
    - Lines 275-278, `hal`/`hal2` creation: replaced by the chain drivers `run_chain()`.
    - Line 280, `running`, and line 298, `smallpaint::isRunning`: removed (GUI).
    - Line 283, `#pragma omp parallel for`: replaced by `run_units()` (`std::thread` workers, `--threads`).
    - Lines 289-293, the camera: the jitter `cam.x = cam.x + RND / 700` (lines 291-292) becomes
      `cam.x + rng_signed(seed, PURPOSE_JITTER_X, 0, row, col, pass) * g_jitter`, and y likewise with `PURPOSE_JITTER_Y`.
    - Line 294, `trace(...)`: called from `take_sample()`, after `g_path` is set.
    - Lines 295-297, `pix[j][i] += c`: `film.sum` at `[row][col] = [i][j]` (item 15). The sum is taken per pass in
      increasing pass order.
    - film: standalone accumulates `pix += c·(1/spp)` and writes `min((int)pix,255)`; for power-of-two passes (default 8)
      this equals the GUI mapping bit for bit (SPEC §9).
    - Lines 302-303, `imageOutput`: removed (GUI). The outputs are written by the functions in item 17.
15. **Image index order.** `pix[j][i]` (original lines 295-297) is stored as `[row][col] = [i][j]` in `film.sum`, `film.k_consumed`
    and `film.object_id`, with `row = i` and `col = j` (`camcr(i, j)` gives `row = i`, as in the original).
16. **Film** (new). `sum` (float64, three per pixel), `k_consumed` (uint64, the `hal.index` deltas over all passes) and
    `object_id` (int32, from the unjittered primary ray, `compute_object_ids()`).
17. **Outputs** (new). `write_npy()` (NumPy v1.0, header padded to 64 bytes), `write_ppm()` (`min((int)sum / passes, 255)`,
    SPEC §7), `write_meta()` (`meta.json`, `oracle_version` "1").
18. **Chains** (new, `take_sample()`, `run_chain()`; SPEC §3). `image`, `row`, `lane:L`, `omp-restart:T`, `pixel-major`
    and `pixel-major-omp:T`. Each unit is one chain. Units run on `--threads` workers with `run_units()`, and each worker
    has its own copy of `params`.
19. **CLI and main** (new). `oracle_main()` parses the options and rejects unknown flags with status 2 and usage text.
    Scene defaults (SPEC §9): gui 400 / 50 / 1.5 with `--chain image`; standalone 900 / 8 / 1.9 with `--chain pixel-major`.
    Each applies unless given. `--out DIR` is required. `int main()` (global scope) calls `oracle_main()`.
20. **Thread-safety.** `trace()` uses `params["refr_index"]`, and `unordered_map::operator[]` is not safe to share. Each
    worker copies `params` (item 18). The knobs in item 6 are read-only once the workers start.
