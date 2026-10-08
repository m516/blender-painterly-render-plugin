# smallpaint: imported sources

These are the smallpaint sources that Painterly reproduces (SPEC §9). They are vendored, never edited, and pinned by sha256.

## Provenance

| Archive | Origin | Archive sha256 | Fetched |
|---|---|---|---|
| GUI, 2018 (`smallpaint_gui.zip`) | Supplied by the project owner as smallpaint.zip, copied to `.cache/downloads/smallpaint_gui.zip`. No upstream URL was given. | `263e8a5df3a6a9b20151467628d34ea36254a5e5803902137858fc2374fe6d68` | 2026-10-08 |
| Standalone, 2016 (`smallpaint_old.zip`) | https://users.cg.tuwien.ac.at/zsolnai/wp/wp-content/uploads/2014/02/smallpaint_old.zip, copied to `.cache/downloads/smallpaint_old.zip` | `8ecbd48d4f34b6fd1bb70e7c9009ad6015e6795f4b2dfddf65b66c9ca20797d2` | 2026-10-08 |

Upstream project: smallpaint by Károly Zsolnai-Fehér, https://users.cg.tuwien.ac.at/zsolnai/gfx/smallpaint/. The GUI port is by Michael Oppitz.

Both archives were extracted into new empty directories under `.cache/extract/` and only the files listed below were copied. Nothing from the archives was executed.

## Licence

MIT. See `LICENSES/MIT-smallpaint.txt`. The author relicensed smallpaint under MIT on 2020-02-26.

## Scope

Only the files in the table below are imported. Binaries, Qt and DLL dependencies, the other GUI renderers, and the GUI `test_images` are not imported. The two reference images are in `tests/data/reference/`. The standalone archive's `.hpp` headers that the imported `.cpp` files include are imported too: `with_bvh/{AABB,Ray,Vec,constants}.hpp` and `with_volumetric_pt/smallmedia.hpp` (T0.5 card, step 1).

Files are byte-identical to the archives (line endings untouched). Never edit; see CLAUDE.md rule 1.

## Imported files

| File (under `third_party/smallpaint/`) | Path in archive |
|---|---|
| `HOWTOAddYourOwnRenderer.txt` | GUI archive `Smallpaint/HOWTOAddYourOwnRenderer.txt` |
| `README.txt` | GUI archive `Smallpaint/README.txt` |
| `smallpaint_bvh/AABB.hpp` | GUI archive `Smallpaint/smallpaint_bvh/AABB.hpp` |
| `smallpaint_bvh/Ray.hpp` | GUI archive `Smallpaint/smallpaint_bvh/Ray.hpp` |
| `smallpaint_bvh/Vec.hpp` | GUI archive `Smallpaint/smallpaint_bvh/Vec.hpp` |
| `smallpaint_bvh/constants.cpp` | GUI archive `Smallpaint/smallpaint_bvh/constants.cpp` |
| `smallpaint_bvh/constants.hpp` | GUI archive `Smallpaint/smallpaint_bvh/constants.hpp` |
| `smallpaint_bvh/smallpaint_bvh.cpp` | GUI archive `Smallpaint/smallpaint_bvh/smallpaint_bvh.cpp` |
| `smallpaint_fixed/smallpaint_fixed.cpp` | GUI archive `Smallpaint/smallpaint_fixed/smallpaint_fixed.cpp` |
| `smallpaint_painterly/smallpaint_painterly.cpp` | GUI archive `Smallpaint/smallpaint_painterly/smallpaint_painterly.cpp` |
| `src_gui/Smallpaint.pro` | GUI archive `Smallpaint/src_gui/Smallpaint.pro` |
| `src_gui/helperfunctions.cpp` | GUI archive `Smallpaint/src_gui/helperfunctions.cpp` |
| `src_gui/main.h` | GUI archive `Smallpaint/src_gui/main.h` |
| `src_gui/mainrenderdistributor.cpp` | GUI archive `Smallpaint/src_gui/mainrenderdistributor.cpp` |
| `src_gui/sceneGeometries.h` | GUI archive `Smallpaint/src_gui/sceneGeometries.h` |
| `standalone/smallmis/smallMIS_1d.cpp` | standalone archive `smallmis/smallMIS_1d.cpp` |
| `standalone/smallpaint_fixed.cpp` | standalone archive `smallpaint_fixed.cpp` |
| `standalone/smallpaint_painterly.cpp` | standalone archive `smallpaint_painterly.cpp` |
| `standalone/with_bvh/AABB.hpp` | standalone archive `with_bvh/AABB.hpp` |
| `standalone/with_bvh/Ray.hpp` | standalone archive `with_bvh/Ray.hpp` |
| `standalone/with_bvh/Vec.hpp` | standalone archive `with_bvh/Vec.hpp` |
| `standalone/with_bvh/constants.cpp` | standalone archive `with_bvh/constants.cpp` |
| `standalone/with_bvh/constants.hpp` | standalone archive `with_bvh/constants.hpp` |
| `standalone/with_bvh/smallpaint.cpp` | standalone archive `with_bvh/smallpaint.cpp` |
| `standalone/with_mlt/smallpaint_pssmlt.cpp` | standalone archive `with_mlt/smallpaint_pssmlt.cpp` |
| `standalone/with_volumetric_pt/smallmedia.cpp` | standalone archive `with_volumetric_pt/smallmedia.cpp` |
| `standalone/with_volumetric_pt/smallmedia.hpp` | standalone archive `with_volumetric_pt/smallmedia.hpp` |

Hashes: see tests/data/MANIFEST.sha256 (verified by tests/core/test_third_party_hashes.py).
