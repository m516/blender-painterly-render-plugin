"""I/O and the SPEC §7 display mapping (T1.2)."""

from pathlib import Path

import numpy as np
from painterly_analysis import read_ppm, smallpaint_display, write_ppm

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE = REPO_ROOT / "tests" / "data" / "reference" / "smallpaint_painterly.ppm"


def test_p6_round_trip(tmp_path: Path) -> None:
    img = np.random.default_rng(0).integers(0, 256, size=(7, 5, 3), dtype=np.uint8)
    path = tmp_path / "round_trip.ppm"
    write_ppm(path, img)
    assert path.read_bytes().startswith(b"P6\n5 7\n255\n")
    back = read_ppm(path)
    assert back.dtype == np.uint8
    assert back.shape == (7, 5, 3)
    assert np.array_equal(back, img)


def test_p3_ascii_with_comment(tmp_path: Path) -> None:
    path = tmp_path / "ascii.ppm"
    path.write_bytes(b"P3\n# a comment\n2 1\n255\n0 1 2  255 254 253\n")
    img = read_ppm(path)
    assert img.dtype == np.uint8
    assert np.array_equal(img, np.array([[[0, 1, 2], [255, 254, 253]]], dtype=np.uint8))


def test_smallpaint_display_hand_computed() -> None:
    # SPEC §7: byte = min((int)sum / passes, 255).
    # 511.9 -> 511 / 2 = 255 (capped); 7.99 -> 7 / 2 = 3.
    out = smallpaint_display(np.array([511.9, 7.99]), passes=2)
    assert out.dtype == np.uint8
    assert out.tolist() == [255, 3]


def test_read_reference_ppm() -> None:
    img = read_ppm(REFERENCE)
    assert img.shape == (400, 400, 3)
    assert img.dtype == np.uint8
