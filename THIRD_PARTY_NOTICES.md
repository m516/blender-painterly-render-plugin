# Third-party notices

| Component | Licence | Where used | Upstream URL |
|---|---|---|---|
| smallpaint | MIT | `third_party/smallpaint`, `src/app/smallpaint_oracle.cpp`; from M3 also `src/test/`, where the bitwise reference tests copy smallpaint code verbatim (`Vec`, T3.5; `Halton`, T3.6; `Sphere::intersect`/`Plane::intersect`, T3.7; `camcr()` via the oracle in `smallpaint_camcr_ref.cpp`, T3.8; `hemisphere()` and the bounce blocks, T3.9) | https://users.cg.tuwien.ac.at/zsolnai/gfx/smallpaint/ |
| Cycles | Apache-2.0 | `third_party/cycles` (except `sse2neon/`), vendored verbatim, pinned to Blender v5.2.2 `intern/cycles`; `src/cycles/shim/` files that copy upstream code and keep its SPDX lines (`util/system.cpp`: CPU-capability code from `intern/cycles/util/system.cpp`; `util/stats.h`: class `Stats` from `intern/cycles/util/stats.h`); modified files carry a "Modified by the Painterly project" notice; `src/app/smallpaint_oracle_hash.h` (hash functions copied from `intern/cycles/util/hash.h`) | https://projects.blender.org/blender/blender/src/tag/v5.2.2/intern/cycles |
| sse2neon | MIT (full text `LICENSES/MIT-sse2neon.txt`) | `third_party/cycles/sse2neon`, vendored verbatim, pinned to commit `227cc413fb2d50b2a10073087be96b59d5364aea` (the commit Blender v5.2.2 pins); compiled into arm64 builds (`WITH_SSE2NEON`) | https://github.com/DLTcollab/sse2neon |
| Embree 4.4.1 | Apache-2.0 (full text `LICENSES/Apache-2.0-embree.txt`) | Fetched at build time, linked statically into `_painterly` through `cmake/painterly_embree.cmake` (used by `src/blender/selftest.cpp`; from T3.10 also by `src/painterly/bvh/embree.{h,cpp}`). Embree's `third-party-programs*.txt` files cover TBB, OIDN and DPC++, components we do not build, so they are not copied. | https://github.com/RenderKit/embree |
| nanobind | BSD-3-Clause (full text `LICENSES/BSD-3-Clause-nanobind.txt`) | `src/blender/python.cpp` (nanobind module `_painterly`) | https://github.com/wjakob/nanobind |
| doctest | MIT | `src/test/` (C++ unit tests) | https://github.com/doctest/doctest |

The combined work is distributed under GPL-3.0-or-later (see LICENSE).
