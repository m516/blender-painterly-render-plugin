# First light: the native C++ core vs smallpaint_oracle

Scratch work, outside the repository. Nothing in `/home/user/blender-painterly-render-plugin` was modified; cached oracle renders under its `.cache/renders/` were read only.

## What was built

- Source: `git archive` of commit `c69ee2e8041513aeec613ecfae55aea22010840e` exported to `src/` (M3 tasks T3.5-T3.12 landed; no Python binding, T3.16 not landed).
- Driver `build/src/firstlight/painterly_render` from `src/src/firstlight/render.cpp` (627 lines) and `src/src/firstlight/CMakeLists.txt`. `add_subdirectory(firstlight)` sits after `add_subdirectory(test)` inside the `PAINTERLY_BUILD_TESTS` block of the copy's `src/CMakeLists.txt`, so it compiles with C++20, `-O3 -ffp-contract=off -fno-fast-math`. It links `painterly_integrator` (with `painterly_util`, `painterly_bvh`, `cycles_util`) and includes `src/test` for `SmallpaintSceneFixture`.
- The driver builds `SmallpaintSceneFixture(chain, lane_length)` and overrides the image size, the camera jitter, every integrator knob (chain, lane_length, seed, u2_mode, k0_phase_lock_bits = 0, alpha, max_depth, diffuse_gain, emission_gain, continue_after_emitter, ray_epsilon), the ior of every LOBE_GLASS lobe and the intersection mode of every sphere. Defaults are the oracle's double literals (meta.json of a default run: jitter 0.0014285714285714286, diffuse_gain 0.10000000000000001, ray_epsilon 0.0001, emission_gain 2).
- Outputs per render: `sum.npy` (<f8, H x W x 3), `k_consumed.npy` (<u8), `object_id.npy` (<i4) via a byte-for-byte copy of the oracle's `write_npy`; `image.ppm` via the oracle's `write_ppm` mapping; `meta.json` with every knob, threads, batch, batch_calls, wall_seconds (render_passes calls only), object_id_seconds, total_k_consumed, image_chain_final_k, image_chain_reached_vdc_period, source_commit.
- Rejected with exit 2 (the core does not implement them): `--scene standalone`, `--chain omp-restart:T | pixel-major | pixel-major-omp:T`, `--halton incremental`, `--u2 base3`.
- Scratch oracle `build/src/app/smallpaint_oracle` built from the same export (post-T3.4).
- Build check: `painterly_tests` 44 test cases, 24667 assertions, 0 failed (`tests.log`).
- Option-mapping matrix (`matrix.sh`, 32 px, 2 passes, seed 7, oracle `--halton exact`): 22 of 22 cases bit-identical, whole .npy files included.

## Parity (bit for bit, sum viewed as uint64)

18 configurations tested, 18 bit-identical to their bitwise reference: values differing 0, max |diff| 0. 1 configuration skipped. Image chains run past K = 2^23, where the cache's `--halton incremental` differs from vdc(K) (SPEC §2), so their bitwise reference is a fresh scratch-oracle `--halton exact --threads 1` render. Row and lane chains restart K per (row, pass) or (lane, pass); their caches are valid references because the bound (2^22 - 1) + max over chains of the all-pass k_consumed sum stays below 2^23.

| group | name | cache id | seed | size | passes | chain | ghost | alpha | u2 | continue | jitter | bitwise reference | sum equal | k_consumed equal | object_id equal | values differing | NaN values: native = ref (cached) | native s (threads) | ref oracle s (threads) | native vs cached incremental |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | image_400 | `fa9e006e98071374` | 0 | 400 | 64 | image | all | 0 | same | yes | 0.0014285714285714286 | fresh oracle --halton exact (`oracle/image_400`) | yes | yes | yes | 0 | 0 = 0 (cached 0) | 40.02 (1) | 52.09 (1) | differs: sum 467280/480000, k_consumed 157987/160000, object_id 0; control: oracle-exact minus cached equals native minus cached (yes sum, yes k) |
| B | image_400_j0 | `9d5f69f73689e231` | 592 | 400 | 64 | image | all | 0 | same | yes | 0 | fresh oracle --halton exact (`oracle/image_400_j0`) | yes | yes | yes | 0 | 0 = 0 (cached 0) | 36.38 (1) | 64.40 (1) | differs: sum 467061/480000, k_consumed 158750/160000, object_id 0; control: oracle-exact minus cached equals native minus cached (yes sum, yes k) |
| C | row_400 | `dc8239bbab49d3b5` | 432 | 400 | 64 | row | all | 0 | same | yes | 0.0014285714285714286 | cache (incremental; max K <= 4638050 < 2^23 = 8388608) | yes | yes | yes | 0 | 0 = 0 (cached 0) | 8.15 (4) | 24.97 (1, cached) | n/a (the cache is the bitwise reference) |
| D | row_400_j0 | `b4d97ce3e41923b0` | 640 | 400 | 64 | row | all | 0 | same | yes | 0 | cache (incremental; max K <= 4637924 < 2^23 = 8388608) | yes | yes | yes | 0 | 0 = 0 (cached 0) | 11.70 (4) | 23.45 (1, cached) | n/a (the cache is the bitwise reference) |
| E | lane1_400 | `047a84e598573f94` | 272 | 400 | 64 | lane:1 | all | 0 | same | yes | 0.0014285714285714286 | cache (incremental; max K <= 4195522 < 2^23 = 8388608) | yes | yes | yes | 0 | 0 = 0 (cached 0) | 11.20 (4) | 49.92 (1, cached) | n/a (the cache is the bitwise reference) |
| E | lane16_400 | `347716def38a11dd` | 368 | 400 | 64 | lane:16 | all | 0 | same | yes | 0.0014285714285714286 | cache (incremental; max K <= 4213038 < 2^23 = 8388608) | yes | yes | yes | 0 | 0 = 0 (cached 0) | 9.57 (4) | 23.46 (1, cached) | n/a (the cache is the bitwise reference) |
| E | lane128_400 | `b9e931e61bd2f713` | 416 | 400 | 64 | lane:128 | all | 0 | same | yes | 0.0014285714285714286 | cache (incremental; max K <= 4339353 < 2^23 = 8388608) | yes | yes | yes | 0 | 0 = 0 (cached 0) | 9.82 (4) | 24.45 (1, cached) | n/a (the cache is the bitwise reference) |
| F | ghost_lights | `89e5f9e67b341714` | 176 | 400 | 64 | image | lights | 0 | same | yes | 0.0014285714285714286 | fresh oracle --halton exact (`oracle/ghost_lights`) | yes | yes | yes | 0 | 0 = 0 (cached 0) | 28.16 (1) | 61.63 (1) | differs: sum 467280/480000, k_consumed 155921/160000, object_id 0; control: oracle-exact minus cached equals native minus cached (yes sum, yes k) |
| F | ghost_none | `0f334687af63fd84` | 160 | 400 | 64 | image | none | 0 | same | yes | 0.0014285714285714286 | fresh oracle --halton exact (`oracle/ghost_none`) | yes | yes | yes | 0 | 0 = 0 (cached 0) | 22.52 (1) | 46.50 (1) | differs: sum 441309/480000, k_consumed 157058/160000, object_id 0; control: oracle-exact minus cached equals native minus cached (yes sum, yes k) |
| G | alpha_025 | `bc0fe2be3492187b` | 192 | 400 | 64 | image | all | 0.25 | same | yes | 0.0014285714285714286 | fresh oracle --halton exact (`oracle/alpha_025`) | yes | yes | yes | 0 | 9 = 9 (cached 0) | 40.33 (1) | 44.01 (1) | differs: sum 467277/480000, k_consumed 158129/160000, object_id 0; control: oracle-exact minus cached equals native minus cached (yes sum, yes k) |
| G | alpha_05 | `b2adaebfad77845f` | 208 | 400 | 64 | image | all | 0.5 | same | yes | 0.0014285714285714286 | fresh oracle --halton exact (`oracle/alpha_05`) | yes | yes | yes | 0 | 21 = 21 (cached 0) | 34.97 (1) | 40.42 (1) | differs: sum 467280/480000, k_consumed 158530/160000, object_id 0; control: oracle-exact minus cached equals native minus cached (yes sum, yes k) |
| G | alpha_1 | `65e6b82c516c5b87` | 224 | 400 | 64 | image | all | 1 | same | yes | 0.0014285714285714286 | fresh oracle --halton exact (`oracle/alpha_1`) | yes | yes | yes | 0 | 15 = 15 (cached 0) | 33.06 (1) | 38.61 (1) | differs: sum 445759/480000, k_consumed 153996/160000, object_id 0; control: oracle-exact minus cached equals native minus cached (yes sum, yes k) |
| H | u2_independent | `d06bf4f80005ed49` | 240 | 400 | 64 | image | all | 0 | independent | yes | 0.0014285714285714286 | fresh oracle --halton exact (`oracle/u2_independent`) | yes | yes | yes | 0 | 0 = 0 (cached 0) | 36.68 (1) | 48.02 (1) | differs: sum 467274/480000, k_consumed 154971/160000, object_id 0; control: oracle-exact minus cached equals native minus cached (yes sum, yes k) |
| I | stop_at_emitter | `d4807562c617e6ac` | 288 | 400 | 64 | image | all | 0 | same | no | 0.0014285714285714286 | fresh oracle --halton exact (`oracle/stop_at_emitter`) | yes | yes | yes | 0 | 0 = 0 (cached 0) | 9.51 (1) | 12.54 (1) | differs: sum 467280/480000, k_consumed 153126/160000, object_id 0; control: oracle-exact minus cached equals native minus cached (yes sum, yes k) |
| J | image_200_j350 | `e75f5b398bdecd29` | 528 | 200 | 64 | image | all | 0 | same | yes | 0.002857142857142857 | fresh oracle --halton exact (`oracle/image_200_j350`) | yes | yes | yes | 0 | 0 = 0 (cached 0) | 8.69 (1) | 5.83 (1) | differs: sum 116886/120000, k_consumed 39514/40000, object_id 0; control: oracle-exact minus cached equals native minus cached (yes sum, yes k) |
| J | row_800 | `e6ca24f79749ff7c` | 512 | 800 | 64 | row | all | 0 | same | yes | 0.0014285714285714286 | cache (incremental; max K <= 5081928 < 2^23 = 8388608) | yes | yes | yes | 0 | 0 = 0 (cached 0) | 34.74 (4) | 98.93 (1, cached) | n/a (the cache is the bitwise reference) |
| K | image_400_512 | `b16ec132b6daf368` | 80 | 400 | 512 | image | all | 0 | same | yes | 0.0014285714285714286 | fresh oracle --halton exact (`oracle/image_400_512`) | yes | yes | yes | 0 | 0 = 0 (cached 0) | 332.66 (1) | 414.29 (1) | differs: sum 467304/480000, k_consumed 159485/160000, object_id 0; control: oracle-exact minus cached equals native minus cached (yes sum, yes k) |
| L | image_400_exact | `273ef70076614c1b` | 128 | 400 | 64 | image | all | 0 | same | yes | 0.0014285714285714286 | cache (halton exact) | yes | yes | yes | 0 | 0 = 0 (cached 0) | 32.21 (1) | 31.72 (1, cached) | n/a (the cache is the bitwise reference) |
| H | u2_base3 | `a072d4631751491c` | 256 | 400 | 64 | image | all | 0 | base3 | yes | 0.0014285714285714286 | skipped | - | - | - | - | - | - | - | u2_base3 (cache a072d4631751491c, seed 256): driver rejects --u2 base3 (exit 2): the core has no base-3 Halton (PainterlyU2Mode has only SAME and INDEPENDENT) |

Native and fresh-oracle seconds of this table were measured under contention (2 renders at once, image chains on 1 thread, row and lane on 4; other agents' nice-0 Embree compiles running; render phase load average 12.70, 6.88, 2.82 before (01:33:32), 15.03, 16.27, 10.82 after (01:44:54), peak 22.03, 17.57, 9.46 at 01:40:56). Cached seconds come from another day and an older oracle binary. They are not a speed comparison; see Timing.

NaN: alpha_025, alpha_05 and alpha_1 hold 9, 21 and 15 NaN values (3, 7 and 5 pixels, all three channels), bits 0xfff8000000000000, at the same positions in native and fresh oracle-exact renders; their cached incremental renders hold 0. `np.array_equal` is False for these three only because NaN != NaN; the bytes are equal. Unverified hypothesis from the parity stage: vdc(K) = 0 at K = multiples of 2^23 (image chains only), so d = N + s = 0 on the bottom plane and d * |d|^-alpha = 0 * inf for alpha > 0. The SPEC §7 display mapping (`smallpaint_display`, and the driver's image.ppm) shows these pixels as (0, 0, 0).

## Determinism

200 px, 64 passes, row chain, jitter 1/700, seed 496 (cache `159cd99dcf9062a1`, the smallest cached seed). All 5 variants and the cached oracle render have identical sha256 for all three arrays.

| variant | threads | batch | calls | wall s | sha256 sum.npy | sha256 k_consumed.npy | sha256 object_id.npy | equal to first variant |
|---|---|---|---|---|---|---|---|---|
| threads 1, batch 64 | 1 | 64 | 1 | 5.919231 | `1f4182b4d631db5d` | `f57a665aeb34000b` | `326c3b4449ce7e58` | yes |
| threads 2, batch 64 | 2 | 64 | 1 | 2.946942 | `1f4182b4d631db5d` | `f57a665aeb34000b` | `326c3b4449ce7e58` | yes |
| threads 4, batch 64 | 4 | 64 | 1 | 2.00013 | `1f4182b4d631db5d` | `f57a665aeb34000b` | `326c3b4449ce7e58` | yes |
| threads 4, batch 8 | 4 | 8 | 8 | 2.631524 | `1f4182b4d631db5d` | `f57a665aeb34000b` | `326c3b4449ce7e58` | yes |
| threads 4, batch 1 | 4 | 1 | 64 | 2.712426 | `1f4182b4d631db5d` | `f57a665aeb34000b` | `326c3b4449ce7e58` | yes |
| vs cached oracle | - | - | - | - | `1f4182b4d631db5d` | `f57a665aeb34000b` | `326c3b4449ce7e58` | yes |

Also bitwise equal among themselves: 3 native 1-thread, 3 oracle-exact 1-thread and 3 native 4-thread timing renders of row seed 0; 3 native 1-thread and 3 oracle-exact 1-thread renders of image seed 0.

## Timing

Interleaved native, oracle, native, oracle, ... one process at a time, `nice -n 10`, 400 px, 64 passes, seed 0, jitter 1/700, oracle `--halton exact`. wall_seconds covers the render loop only (object-id pass excluded) in both programs; CPU time was not recorded.

| program | config | threads | wall s (r1, r2, r3) | median s |
|---|---|---|---|---|
| native painterly_render | image chain, 400 px, 64 passes, seed 0, jitter 1/700 | 1 | 20.72, 25.18, 21.43 | 21.43 |
| smallpaint_oracle --halton exact | image chain, 400 px, 64 passes, seed 0, jitter 1/700 | 1 | 25.49, 27.76, 24.97 | 25.49 |
| native painterly_render | row chain, 400 px, 64 passes, seed 0, jitter 1/700 | 1 | 20.49, 22.43, 20.18 | 20.49 |
| smallpaint_oracle --halton exact | row chain, 400 px, 64 passes, seed 0, jitter 1/700 | 1 | 24.89, 24.39, 24.46 | 24.46 |
| native painterly_render | row chain, 400 px, 64 passes, seed 0, jitter 1/700 | 4 | 14.91, 11.98, 10.95 | 11.98 |

- Median ratio native / oracle, 1 thread: image chain 0.841, row chain 0.838.
- Native row chain, 4 threads vs 1 thread: 1.71x (11.98 s vs 20.49 s).
- Spread: native image 1-thread runs ranged 20.72-25.18 s; with n = 3 per arm under shifting load the ratios carry about +-10 % run-to-run spread.
- Load caveat: 4 cores shared with other agents compiling Embree (gcc and clang, nice 0). Load average at timing start `01:46:36 up 19 min,  0 user,  load average: 13.21, 15.30, 11.03`, at end `01:51:57 up 25 min,  0 user,  load average: 11.04, 13.27, 11.51`. Image chain, per pair (native then oracle): r1: 13.21, 15.30, 11.03 -> 15.04, 15.43, 11.30; r2: 15.04, 15.43, 11.30 -> 16.62, 15.83, 11.66; r3: 16.62, 15.83, 11.66 -> 13.69, 15.19, 11.64. Row chain, per pair (native then oracle): r1: 13.69, 15.19, 11.64 -> 12.18, 14.54, 11.60; r2: 12.18, 14.54, 11.60 -> 11.51, 14.04, 11.58; r3: 11.51, 14.04, 11.58 -> 10.79, 13.49, 11.50. Row chain 4 threads: r1: 10.79, 13.49, 11.50 -> 11.28, 13.46, 11.53; r2: 11.28, 13.46, 11.53 -> 11.23, 13.38, 11.52; r3: 11.23, 13.38, 11.52 -> 11.04, 13.27, 11.51.

## Hero renders (native core)

| hero | dir | size | chain | passes | seed | jitter | threads | wall s | object_id s | total K | parity |
|---|---|---|---|---|---|---|---|---|---|---|---|
| hero_image_400 | `image_400_512` | 400 | image | 512 | 80 | 0.0014285714285714286 | 1 | 332.66 | 0.0222 | 1333254657 | bit-identical to a fresh oracle --halton exact render (`oracle/image_400_512`, 1 thread, 414.29 s): sum 0/480000, k_consumed 0/160000, object_id 0/160000 differ, array data byte-identical; differs from cached oracle b16ec132b6daf368 (halton incremental) at 467304 of 480000 sum values, because the image chain passes K = 2^23 (final K 1333254657), where incremental != vdc (SPEC §2) |
| hero_row_400 | `hero_row_400` | 400 | row | 1024 | 0 | 0.0014285714285714286 | 4 | 91.90 | 0.0041 | 2666362239 | no cached oracle at these knobs; bit-identical to a fresh oracle --halton exact render (`oracle/hero_row_400`, 2 threads, 400.12 s): sum 0/480000, k_consumed 0/160000, object_id 0/160000 differ, array data byte-identical |
| hero_row_800 | `hero_row_800` | 800 | row | 512 | 0 | 0.0014285714285714286 | 4 | 257.90 | 0.0127 | 5333083504 | no cached oracle at these knobs; bit-identical to a fresh oracle --halton exact render (`oracle/hero_row_800`, 2 threads, 574.20 s): sum 0/1920000, k_consumed 0/640000, object_id 0/640000 differ, array data byte-identical |

Hero log (`hero/run.log`, load averages before and after each render):

```
01:58:53 native hero_row_400 START uptime:  01:58:53 up 32 min,  0 user,  load average: 4.13, 7.49, 9.41
02:00:25 native hero_row_400 END rc=0 uptime:  02:00:25 up 33 min,  0 user,  load average: 4.48, 6.71, 8.94
02:00:25 native hero_row_800 START uptime:  02:00:25 up 33 min,  0 user,  load average: 4.48, 6.71, 8.94
02:04:43 native hero_row_800 END rc=0 uptime:  02:04:43 up 37 min,  0 user,  load average: 7.29, 6.87, 8.43
02:04:43 oracle hero_row_400 START uptime:  02:04:43 up 37 min,  0 user,  load average: 7.29, 6.87, 8.43
02:04:43 oracle hero_row_800 START uptime:  02:04:43 up 37 min,  0 user,  load average: 7.29, 6.87, 8.43
02:11:23 oracle hero_row_400 END rc=0 uptime:  02:11:23 up 44 min,  0 user,  load average: 8.33, 7.79, 8.27
02:14:17 oracle hero_row_800 END rc=0 uptime:  02:14:17 up 47 min,  0 user,  load average: 2.66, 5.62, 7.37
02:14:17 DONE
```

hero_row_400 and hero_row_800 ran one at a time on 4 threads (load average 4.13 to 7.29 around them, other agents' processes included); the two oracle references then ran together on 2 threads each (the oracle's row chain writes disjoint rows, each summed in pass order, so its output does not depend on the thread count, SPEC §3). hero_image_400 is the parity render K (`renders/image_400_512`, seed 80), reused, not re-rendered; it ran on 1 thread next to another render.

## Sheets

Built by `sheets_src/export_tiles.py` (project venv; display bytes from `painterly_analysis.io.smallpaint_display(sum, passes)`, SPEC §7) and `sheets_src/sheets.py` (system Python, Pillow; layout, fonts and colours of `scratchpad/gallery/sheets.py`). Bitwise counts on the sheets are recomputed from the arrays and asserted equal to the parity result.

| sheet | bytes | content |
|---|---|---|
| `sheets/6_first_light.png` | 1129062 | rows A image_400 (ref: fresh oracle exact, seed 0), C row_400 (ref: cache dc8239bbab49d3b5, seed 432), E lane16_400 (ref: cache 347716def38a11dd, seed 368): oracle, native, sum bitwise-difference mask; 0 of 480000 values differ in each |
| `sheets/7_native_core.png` | 1372382 | hero_image_400, hero_row_400, hero_row_800 (800 px box-filtered to 400); second row: the same image-plane region, 200 x 200 px of the 400 px renders at 2x nearest and 400 x 400 px of the 800 px render at 1:1 |
| `sheets/8_native_ingredients.png` | 1375065 | F ghost_none, G alpha_1, H u2_independent / F ghost_lights, I stop_at_emitter, in the positions of gallery/3_ingredients.png; sixth slot empty (a sixth tile made the sheet 1707189 bytes) |
