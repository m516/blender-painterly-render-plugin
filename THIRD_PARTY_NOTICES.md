# Third-party notices

| Component | Licence | Where used | Upstream URL |
|---|---|---|---|
| smallpaint | MIT | `third_party/smallpaint`, `src/app/smallpaint_oracle.cpp` | https://users.cg.tuwien.ac.at/zsolnai/gfx/smallpaint/ |
| Cycles | Apache-2.0 | `third_party/cycles`, vendored verbatim, pinned to Blender v5.2.2 `intern/cycles`; modified files carry a "Modified by the Painterly project" notice; `src/app/smallpaint_oracle_hash.h` (hash functions copied from `intern/cycles/util/hash.h`) | https://projects.blender.org/blender/blender/src/tag/v5.2.2/intern/cycles |
| Embree 4.4.1 | Apache-2.0 | Fetched at build time, statically linked (`src/bvh/embree.{h,cpp}`) | https://github.com/RenderKit/embree |
| nanobind | BSD-3-Clause | `src/blender/python.cpp` (nanobind module `_painterly`) | https://github.com/wjakob/nanobind |
| doctest | MIT | `src/test/` (C++ unit tests) | https://github.com/doctest/doctest |

The combined work is distributed under GPL-3.0-or-later (see LICENSE).
