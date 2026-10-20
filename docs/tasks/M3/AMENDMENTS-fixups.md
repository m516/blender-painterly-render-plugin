# M3 fix-up amendments: the edits M3-PROPAGATE carried into the later cards

This file is the record M3-PROPAGATE's Outcome asks for: one entry per edit that carries a T3.19-T3.24 fix-up into a card that had not run yet. Each entry names the file, the old text and the new text, copied byte for byte from the diff that made the edit (the diff's `-`/`+` column removed), and the reason: the fix-up or decision the edit carries.

Three sources, and every hunk of each appears here exactly once:

- `git show fdc6357 -- docs/tasks` (M3-PROPAGATE, commit `fdc6357`, subject `t-propagate: M3-PROPAGATE: carry the fix-up renames into the cards not yet run`): T3.13, T3.14 and T3.15. Every entry below quotes the removed and added lines of that diff.
- This item's T3.17 edit (entry 9): the normal-orientation line, applied by M3-PROPAGATE-b. Its old and new text are T3.21's "Edits for later cards" block 1, verbatim.
- The Opus ruling of 2026-10-18 on M3-FIX-T3.13a (entries 10 and 11): the singular-`object_to_world` line and the `src/test/test_scene.cpp` bullet of T3.13.

Where a fix-up card specifies an edit verbatim, the entry names that card and block: T3.21's "Edits for later cards" covers T3.13's read-first line, `device_update` and `test_scene.cpp` (blocks 1-3) and this item's T3.17 edit (block 1 under the T3.17 heading).

A hunk that only adds or only removes lines has an empty block on the other side; the empty fenced block is kept, so that every hunk has exactly one old and one new entry. Entry 6 (T3.15) is the only such hunk: it removes no line.

T3.23 carries no edit in either source. Its shared test headers `src/test/bitwise.h` and `src/test/smallpaint_ref.h` are included by the C++ test files that already exist; T3.17 adds a Python test, and no other card in T3.13-T3.18, M4 or M5 names them (M3-PROPAGATE's worker verified this by grep). Nothing in those cards is due an edit for T3.23, so no entry here carries it. T3.19 and T3.24 likewise carry no edit into these cards: no line of either source answers them.

## 1. `docs/tasks/M3/T3.13-scene.md` — `@@ -3,12 +3,12 @@`

Reason: T3.21 (D35) and T3.22. The read-first line gains `painterly_normal_matrix`, which T3.21 added to `src/painterly/util/math_double3.h`; the `## Create` heading and the `CMakeLists.txt` bullet gain `painterly_kernel` (TQ.1 F13) and `painterly_target_warnings(painterly_scene)` (TQ.1 F9). The read-first line is T3.21's "Edits for later cards" block 1, verbatim.

Old text:

```text
- `src/painterly/kernel/{types,globals}.h`, `src/painterly/bvh/embree.h`
## Create `src/painterly/scene/` (static lib `painterly_scene`; links `cycles_graph` and `painterly_bvh`)
- `CMakeLists.txt`: the `painterly_scene` target.
```

New text:

```text
- `src/painterly/kernel/{types,globals}.h`, `src/painterly/bvh/embree.h`, and `painterly_normal_matrix` in `src/painterly/util/math_double3.h` (T3.21)
## Create `src/painterly/scene/` (static lib `painterly_scene`; links `cycles_graph` and `painterly_kernel`, the header-only kernel INTERFACE target of TQ.1 F13, which links `painterly_bvh` and `cycles_util`; T3.22)
- `CMakeLists.txt`: the `painterly_scene` target, with `painterly_target_warnings(painterly_scene)` (T3.22).
```

## 2. `docs/tasks/M3/T3.13-scene.md` — `@@ -52,7 +52,8 @@`

Reason: T3.20: `set_integrator` rejects three kernel preconditions (`max_depth < 1` is new), and the kernel clamps the lane length, `L = min(lane_length, width)`.

Old text:

```text
    - Ranges are UI limits, not behaviour, except the two kernel preconditions that `set_integrator` rejects (T3.15).
```

New text:

```text
    - Ranges are UI limits, not behaviour, except the three kernel preconditions that `set_integrator` rejects (T3.15, T3.20): `lane_length < 1`, `k0_phase_lock_bits` outside 0…22, `max_depth < 1`.
    - `lane_length` itself is clamped by the kernel: `L = min(lane_length, width)` (T3.20), so a value at least the width renders exactly like `row`.
```

## 3. `docs/tasks/M3/T3.13-scene.md` — `@@ -73,8 +74,16 @@`

Reason: T3.21 (D35): `KernelPainterlyObject::itfm` and `PainterlyGlobalsCPU::tri_vertices` are gone. `device_update` fills `tri_material`/`tri_corner_normals`, sends the vertices only to `painterly_embree_scene_create`, and fills `normal_to_world` from `painterly_normal_matrix`. T3.21's "Edits for later cards" block 2, verbatim.

Old text:

```text
    - flatten meshes into the tri_* arrays (vertices expanded per triangle: 9 floats);
    - compute `itfm` with Cycles' `transform_inverse`;
```

New text:

```text
    - flatten meshes into `tri_material` (one int per triangle) and, when at least one mesh has corner normals,
      `tri_corner_normals` (`PAINTERLY_TRIANGLE_CORNERS * PAINTERLY_POINT_FLOATS` floats per triangle of every mesh, zeros for
      a mesh without corner normals), both indexed by `mesh.tri_offset + prim` (`painterly/kernel/globals.h`). The vertices
      and vertex indices go only to `painterly_embree_scene_create` (`PainterlyEmbreeMeshInput`), which copies them: the
      device scene keeps no vertex array;
    - fill each `KernelPainterlyObject` with `mesh`, `object_id` and
      `painterly_normal_matrix(object.object_to_world, kernel_object.normal_to_world)` (`painterly/util/math_double3.h`), and
      pass the same float `object_to_world` to Embree (`PainterlyEmbreeObjectInput`). Embree's Ng goes through the same
      function, so Ng and the corner normals share one matrix (T3.21). A singular `object_to_world` makes `device_update`
      throw `std::invalid_argument`;
```

## 4. `docs/tasks/M3/T3.13-scene.md` — `@@ -98,7 +107,7 @@`

Reason: T3.21 (D35): `test_scene.cpp` checks the new array sizes, `normal_to_world` against `painterly_normal_matrix`, and the singular-transform rejection. T3.21's "Edits for later cards" block 3, verbatim.

Old text:

```text
- `src/test/test_scene.cpp`: socket defaults, the set/get round trip, the UI-info name-set equality, object-id auto-assignment, `device_update` array sizes and `svm_offset == -1` for every material, and invalid-mesh rejection.
```

New text:

```text
- `src/test/test_scene.cpp`: socket defaults, the set/get round trip, the UI-info name-set equality, object-id auto-assignment, `device_update` array sizes (`tri_corner_normals`: `PAINTERLY_TRIANGLE_CORNERS * PAINTERLY_POINT_FLOATS` floats per triangle), `svm_offset == -1` for every material, `normal_to_world` of every object bitwise equal to `painterly_normal_matrix` of its `object_to_world`, invalid-mesh rejection, and a singular `object_to_world` rejected with `std::invalid_argument`.
```

## 5. `docs/tasks/M3/T3.14-session.md` — `@@ -5,7 +5,7 @@`

Reason: T3.22 (TQ.1 F9): every later `painterly_*` target calls `painterly_target_warnings`.

Old text:

```text
## Create `src/painterly/session/session.h/.cpp` and `src/painterly/session/CMakeLists.txt` (static lib `painterly_session`; links `painterly_integrator` and `painterly_scene`)
```

New text:

```text
## Create `src/painterly/session/session.h/.cpp` and `src/painterly/session/CMakeLists.txt` (static lib `painterly_session`; links `painterly_integrator` and `painterly_scene`, and calls `painterly_target_warnings(painterly_session)`; T3.22)
```

## 6. `docs/tasks/M3/T3.15-bindings.md` — `@@ -1,11 +1,18 @@`

Reason: D34 (TQ.1 F12): T3.15 gains the `## Goal` section and the `src/blender/selftest.h`/`.cpp` bullet; the selftest ray moves to `painterly_bvh` and `selftest.cpp` becomes its own translation unit.

Old text:

```text

```

New text:

```text
## Goal
`_painterly` exports exactly the `_painterly.pyi` API, and `_painterly.selftest()` traces its ray through `painterly_bvh`
with `painterly_embree_scene_create` + `painterly_embree_intersect_closest` instead of building its own Embree device,
keeping the `RTC_DEVICE_PROPERTY_TASKING_SYSTEM` probe and the Python result keys (TQ.1 F12, moved here by D34 once this
card links the engine layers).

- `src/blender/selftest.h` and `src/blender/selftest.cpp`: TQ.1 F12 (D34). `selftest_embree()` traces its ray with `painterly_embree_scene_create` (`PainterlyEmbreeMeshInput` / `PainterlyEmbreeObjectInput`) and `painterly_embree_intersect_closest` (T3.10) instead of building its own Embree device, scene, geometry and ray. It keeps the `RTC_DEVICE_PROPERTY_TASKING_SYSTEM` probe (`selftest.h`'s `tasking_system` field) and every Python result key (`embree_version`, `tasking_system`, `hit`, `t`, `prim_id`). The probe keeps its own `rtcNewDevice(nullptr)` for `rtcGetDeviceProperty` alone: `painterly/bvh/embree.h` is not in this card's list and exposes no device handle, so `selftest.h` says why the probe stays independent of `painterly_bvh`.
```

## 7. `docs/tasks/M3/T3.15-bindings.md` — `@@ -15,8 +22,9 @@`

Reason: T3.20: `set_integrator` also rejects `max_depth < 1` (the oracle's `--max-depth` is `N >= 1`).

Old text:

```text
      break a kernel precondition of `painterly/kernel/types.h`: `lane_length < 1`, or `k0_phase_lock_bits` outside 0…22
      (SPEC §3: K0 has 22 bits; `1u << q` is undefined from q = 32). These are the pyi's "bad values"; every other range is a
```

New text:

```text
      break a kernel precondition of `painterly/kernel/types.h`: `lane_length < 1`, `k0_phase_lock_bits` outside 0…22
      (SPEC §3: K0 has 22 bits; `1u << q` is undefined from q = 32), or `max_depth < 1` (T3.20: the oracle's `--max-depth`
      is `N >= 1`, and `PainterlyPathTrace` throws below it). These are the pyi's "bad values"; every other range is a
```

## 8. `docs/tasks/M3/T3.15-bindings.md` — `@@ -28,8 +36,8 @@`

Reason: T3.20 and T3.22 (TQ.1 F11/F13): the `max_depth=0` rejection test, T3.22's plain target names (no `painterly::embree` alias) and the post-D34 link list.

Old text:

```text
  - `set_integrator(lane_length=0)` and `set_integrator(k0_phase_lock_bits=23)` raise ValueError.
- `src/blender/CMakeLists.txt`: link `painterly_session` etc. Keep the export map and static runtime flags.
```

New text:

```text
  - `set_integrator(lane_length=0)`, `set_integrator(k0_phase_lock_bits=23)` and `set_integrator(max_depth=0)` raise ValueError.
- `src/blender/CMakeLists.txt`: link `painterly_session` etc. Keep the export map and static runtime flags. T3.22's plain target names apply (TQ.1 F11: no `painterly::embree` alias). After F12 the ray goes through `painterly_bvh` (via `painterly_kernel`, T3.22), so `painterly_kernel` is linked for the ray; the `RTC_DEVICE_PROPERTY_TASKING_SYSTEM` probe keeps its one `rtcNewDevice(nullptr)`, so `painterly_embree` stays linked for it.
```

## 9. `docs/tasks/M3/T3.17-triangle-path.md` — `this item's T3.17 edit (T3.21, "Edits for later cards", block 1)`

Reason: T3.21 (D35): T3.17's normal-orientation line. T3.21's "Edits for later cards" block 1 under **`docs/tasks/M3/T3.17-triangle-path.md`**, verbatim. This is this item's edit.

Old text:

```text
  - Normal orientation: the winding gives normals equal to smallpaint's `n`, and `two_sided = False` keeps smallpaint's plane normal semantics exactly.
```

New text:

```text
  - Normal orientation: Embree's object-space Ng is `(v1 − v0) × (v2 − v0)` for the corners in index order (`painterly/bvh/embree.h`, T3.21). Order each triangle's corners counter-clockwise as seen from the side that smallpaint's `n` points to, so that Ng has the direction and sign of `n`. With no corner normals the shading normal is `normalize(Ng)`, and `two_sided = False` keeps smallpaint's plane normal semantics exactly.
```

## 10. `docs/tasks/M3/T3.13-scene.md` — the singular-transform line, T3.21's `device_update` bullet

Reason: the Opus ruling of 2026-10-18 on M3-FIX-T3.13a. An object whose mesh has no triangles cannot be hit, so its `normal_to_world` stays zero and its `object_to_world` is not checked for singularity; `painterly_embree_scene_create` skips such an object in exactly the same way. The edit records the ruling in the card the code was written from.

Old text:

```text
      function, so Ng and the corner normals share one matrix (T3.21). A singular `object_to_world` makes `device_update`
      throw `std::invalid_argument`;
```

New text:

```text
      function, so Ng and the corner normals share one matrix (T3.21). A singular `object_to_world` makes `device_update`
      throw `std::invalid_argument` when its mesh has triangles (an object whose mesh has none cannot be hit; its
      `normal_to_world` stays zero and is not checked, as `painterly_embree_scene_create` skips it: Opus ruling,
      2026-10-18);
```

## 11. `docs/tasks/M3/T3.13-scene.md` — `@@ -107,7 +109,7 @@`, the `src/test/test_scene.cpp` bullet

Reason: the same Opus ruling of 2026-10-18. The test compares `normal_to_world` with `painterly_normal_matrix` only for an object whose mesh has triangles; an object on a mesh without triangles keeps a zero matrix by the ruling, so the unqualified phrase would demand a comparison the ruling rules out.

Old text:

```text
- `src/test/test_scene.cpp`: socket defaults, the set/get round trip, the UI-info name-set equality, object-id auto-assignment, `device_update` array sizes (`tri_corner_normals`: `PAINTERLY_TRIANGLE_CORNERS * PAINTERLY_POINT_FLOATS` floats per triangle), `svm_offset == -1` for every material, `normal_to_world` of every object bitwise equal to `painterly_normal_matrix` of its `object_to_world`, invalid-mesh rejection, and a singular `object_to_world` rejected with `std::invalid_argument`.
```

New text:

```text
- `src/test/test_scene.cpp`: socket defaults, the set/get round trip, the UI-info name-set equality, object-id auto-assignment, `device_update` array sizes (`tri_corner_normals`: `PAINTERLY_TRIANGLE_CORNERS * PAINTERLY_POINT_FLOATS` floats per triangle), `svm_offset == -1` for every material, `normal_to_world` of every object whose mesh has triangles bitwise equal to `painterly_normal_matrix` of its `object_to_world`, invalid-mesh rejection, and a singular `object_to_world` rejected with `std::invalid_argument`.
```
