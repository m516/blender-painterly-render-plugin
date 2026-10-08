# Reference images

Reference images for the smallpaint look. Their sha256 values are pinned in `tests/data/MANIFEST.sha256`.

## Provenance

- `smallpaint_painterly.ppm` and `smallpaint_fixed.ppm` are copied byte-for-byte from `Smallpaint/test_images/` in the 2018 GUI archive. Archive: `smallpaint_gui.zip`, sha256 `263e8a5df3a6a9b20151467628d34ea36254a5e5803902137858fc2374fe6d68`. See `third_party/smallpaint/README.md`.
- Fetched 2026-10-08.
- Format: 400×400 P6 (binary PPM). The header is the 15 bytes `P6\n400 400\n255\n`, followed by 480 000 bytes of pixel data.
- These images were rendered by the 2017 GUI build (dated 2017-03-22).
- `smallpaint_painterly.ppm` is the golden reference (SPEC §0).
- `smallpaint_bvh.ppm` and `smallpaint_pssmlt.ppm` in the archive are byte-identical copies of `smallpaint_fixed.ppm`. They are deliberately not imported.
