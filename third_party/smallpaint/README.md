# smallpaint: imported sources

These are the smallpaint sources that Painterly reproduces (SPEC §9). They are vendored, never edited, and pinned by sha256.

## Provenance

| Archive | Origin | Archive sha256 | Fetched |
|---|---|---|---|
| GUI, 2018 (`smallpaint_gui.zip`) | Supplied as an uploaded file, `/root/.claude/uploads/98b29052-844f-5778-93d6-f67301038886/50e77c20-smallpaint.zip`, copied to `.cache/downloads/smallpaint_gui.zip`. No upstream URL was given. | `263e8a5df3a6a9b20151467628d34ea36254a5e5803902137858fc2374fe6d68` | 2026-10-08 |
| Standalone, 2016 (`smallpaint_old.zip`) | https://users.cg.tuwien.ac.at/zsolnai/wp/wp-content/uploads/2014/02/smallpaint_old.zip, copied to `.cache/downloads/smallpaint_old.zip` | `8ecbd48d4f34b6fd1bb70e7c9009ad6015e6795f4b2dfddf65b66c9ca20797d2` | 2026-10-08 |

Upstream project: smallpaint by Károly Zsolnai-Fehér, https://users.cg.tuwien.ac.at/zsolnai/gfx/smallpaint/. The GUI port is by Michael Oppitz.

Both archives were extracted into new empty directories under `.cache/extract/` and only the files listed below were copied. Nothing from the archives was executed.

## Licence

MIT. See `LICENSES/MIT-smallpaint.txt`. The author relicensed smallpaint under MIT on 2020-02-26.

## Scope

Only the files in the table below are imported. Binaries, Qt and DLL dependencies, the other GUI renderers, and the GUI `test_images` are not imported. The two reference images are in `tests/data/reference/`. The standalone archive's `.hpp` headers are imported with its `.cpp` sources, because `standalone/with_bvh/smallpaint.cpp` includes them.

Files are byte-identical to the archives (line endings untouched). Never edit; see CLAUDE.md rule 1.

## Imported files

| File (under `third_party/smallpaint/`) | Path in archive | sha256 |
|---|---|---|
| `HOWTOAddYourOwnRenderer.txt` | GUI archive `Smallpaint/HOWTOAddYourOwnRenderer.txt` | `cda1e961d5836ce135922b8ee9f853e72519b77c742bcbbb0d60f3ae909d48ec` |
| `README.txt` | GUI archive `Smallpaint/README.txt` | `04cfbcd358cdf07597898994414230638afbffda3e3bed5f4ea82f9cc0b7a1df` |
| `smallpaint_bvh/AABB.hpp` | GUI archive `Smallpaint/smallpaint_bvh/AABB.hpp` | `ca98394b1ad6bb932cc9b33e4461ab1e1b3d226ae429678cd19a5f238ea1168a` |
| `smallpaint_bvh/Ray.hpp` | GUI archive `Smallpaint/smallpaint_bvh/Ray.hpp` | `5b183c8733dcacc269c335b4f382302515ee92072228ce652f896e779d92b2ed` |
| `smallpaint_bvh/Vec.hpp` | GUI archive `Smallpaint/smallpaint_bvh/Vec.hpp` | `74c8ce79788e13c0d9a9e0afa306460e03f5008568751b92c4bf15d3cd2c43b6` |
| `smallpaint_bvh/constants.cpp` | GUI archive `Smallpaint/smallpaint_bvh/constants.cpp` | `4348f75a1ddca9a05c2452afb968922ef5727079854df4f1d82948fd1d6cbd82` |
| `smallpaint_bvh/constants.hpp` | GUI archive `Smallpaint/smallpaint_bvh/constants.hpp` | `00463a66bbf9864f44ff995c84def96166b9bc2143ec712b8f9c319b70c9f8f6` |
| `smallpaint_bvh/smallpaint_bvh.cpp` | GUI archive `Smallpaint/smallpaint_bvh/smallpaint_bvh.cpp` | `0bff984fde669c6685895bfdebe12a531089185755663c0125eddf667fba188d` |
| `smallpaint_fixed/smallpaint_fixed.cpp` | GUI archive `Smallpaint/smallpaint_fixed/smallpaint_fixed.cpp` | `d2d533ac1c7f6e09574bf19db28bcf796def3e5ff1e94d4b4820b48c0d326e8d` |
| `smallpaint_painterly/smallpaint_painterly.cpp` | GUI archive `Smallpaint/smallpaint_painterly/smallpaint_painterly.cpp` | `760222119339a7ee74593459ee34b779c409bd682d44855b87792b6a2848c78c` |
| `src_gui/Smallpaint.pro` | GUI archive `Smallpaint/src_gui/Smallpaint.pro` | `8087bf0b956ce34db8b1858f0d10491518a259d4190fa0af0414d8e8091db59b` |
| `src_gui/helperfunctions.cpp` | GUI archive `Smallpaint/src_gui/helperfunctions.cpp` | `6fa62554112ee8cc664019e274d63f3678019da647a3676cdfdcd058d813f47a` |
| `src_gui/main.h` | GUI archive `Smallpaint/src_gui/main.h` | `89b5e1d28bd62fd3005df73e532d285725f01a45bb9d8f7605e8ec3440a81174` |
| `src_gui/mainrenderdistributor.cpp` | GUI archive `Smallpaint/src_gui/mainrenderdistributor.cpp` | `b4b6184e859242cf212b9e66e23c7a7dd6d524a1086c40ae0537d5abf63677c3` |
| `src_gui/sceneGeometries.h` | GUI archive `Smallpaint/src_gui/sceneGeometries.h` | `b0863b6a867b5e8bbba7c8ff18d38ac6b1c1f278c4c223d1f221db68073e46fc` |
| `standalone/smallmis/smallMIS_1d.cpp` | standalone archive `smallmis/smallMIS_1d.cpp` | `d7677c5116eb653e34190bb3c5c2a917ccba1e7e71e2b451dc121cd7eafdb061` |
| `standalone/smallpaint_fixed.cpp` | standalone archive `smallpaint_fixed.cpp` | `ea36afe9f67104bab1d255bb842fe9ca835200f97ddc3e415dd6cc5fb61c8caf` |
| `standalone/smallpaint_painterly.cpp` | standalone archive `smallpaint_painterly.cpp` | `41b8b5b26d04d4179ed936e1132b9e2977b8003744c4c2518053e6bc67aedd05` |
| `standalone/with_bvh/AABB.hpp` | standalone archive `with_bvh/AABB.hpp` | `4e1f5ff10a45665d4ddf6140d868b4911781ed3f54ba130682c08dde047b2a01` |
| `standalone/with_bvh/Ray.hpp` | standalone archive `with_bvh/Ray.hpp` | `8317d648c150ed2be7994a01c7d35d0b3f19d4fb01d2710cf19b3ad10d5c3bad` |
| `standalone/with_bvh/Vec.hpp` | standalone archive `with_bvh/Vec.hpp` | `aa40eeef4a864f7aaf83f8cae695a732532d6d25b6e957f6fc3d1a50b0fce223` |
| `standalone/with_bvh/constants.cpp` | standalone archive `with_bvh/constants.cpp` | `ed84e701abef0264c426cf3acc08c89ef3864b17aacc0f373ebf5e5ed3a12e77` |
| `standalone/with_bvh/constants.hpp` | standalone archive `with_bvh/constants.hpp` | `138e4dabc9e8819844bb7fd0f2a0b0b6cf30873a8bb654a342a9d7e8d1db9b9d` |
| `standalone/with_bvh/smallpaint.cpp` | standalone archive `with_bvh/smallpaint.cpp` | `d71c967c2667795e2204b395dd9be3c21baf3deed341a4e6cbbe0ea712b71d38` |
| `standalone/with_mlt/smallpaint_pssmlt.cpp` | standalone archive `with_mlt/smallpaint_pssmlt.cpp` | `2c8318eb1e10775b8d6986a537d944ad26ea1a82b8405ccb3d4ab386529137fb` |
| `standalone/with_volumetric_pt/smallmedia.cpp` | standalone archive `with_volumetric_pt/smallmedia.cpp` | `41fac6491335239ba12a39b70eff46410762c582bcecf8b68abfdb96122a5a3e` |
| `standalone/with_volumetric_pt/smallmedia.hpp` | standalone archive `with_volumetric_pt/smallmedia.hpp` | `5773d58fdb26011def4599924d2bc10465b8d72a9aac6d766d6edd2e56da78d6` |

Checked by `tests/core/test_third_party_hashes.py` against `tests/data/MANIFEST.sha256`.
