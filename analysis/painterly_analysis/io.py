"""Image and oracle-output I/O for the analysis package.

Display bytes follow SPEC §7: each channel is ``min((int)sum / passes, 255)``. Images are
(H, W, 3) arrays with (row, col) = (y, x), as in the oracle's ``image.ppm``.
"""

import json
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# One PPM header token: skips whitespace and '#' comments, then captures the token.
_PPM_TOKEN = re.compile(rb"\s*(?:#[^\r\n]*\s*)*([^\s#]+)")
_PPM_COMMENT = re.compile(rb"#[^\r\n]*")

# PNG format constants (PNG specification, ISO/IEC 15948): the file signature, bit depth 8 for the
# uint8 display bytes, colour type 2 for truecolour RGB, and scanline filter type 0 (None).
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_PNG_BIT_DEPTH = 8
_PNG_COLOR_TYPE_RGB = 2
_PNG_FILTER_NONE = 0


def _ppm_token(data: bytes, pos: int) -> tuple[bytes, int]:
    match = _PPM_TOKEN.match(data, pos)
    if match is None:
        raise ValueError("truncated PPM header")
    return match.group(1), match.end()


def read_ppm(path: str | Path) -> np.ndarray:
    """Read a P6 or P3 PPM with maxval 255. Returns uint8 display bytes, shape (H, W, 3)."""
    data = Path(path).read_bytes()
    magic, pos = _ppm_token(data, 0)
    if magic not in (b"P3", b"P6"):
        raise ValueError(f"{path}: not a P3 or P6 PPM (magic {magic!r})")
    width_tok, pos = _ppm_token(data, pos)
    height_tok, pos = _ppm_token(data, pos)
    maxval_tok, pos = _ppm_token(data, pos)
    width, height, maxval = int(width_tok), int(height_tok), int(maxval_tok)
    if maxval != 255:
        raise ValueError(f"{path}: only maxval 255 is supported, got {maxval}")
    count = width * height * 3
    if magic == b"P6":
        # Exactly one whitespace byte separates maxval from the raster.
        if not data[pos : pos + 1].isspace():
            raise ValueError(f"{path}: missing whitespace before the P6 raster")
        raster = data[pos + 1 : pos + 1 + count]
        if len(raster) != count:
            raise ValueError(f"{path}: raster has {len(raster)} bytes, expected {count}")
        img = np.frombuffer(raster, dtype=np.uint8).copy()
    else:
        tokens = _PPM_COMMENT.sub(b" ", data[pos:]).split()
        if len(tokens) < count:
            raise ValueError(f"{path}: raster has {len(tokens)} samples, expected {count}")
        img = np.array([int(t) for t in tokens[:count]], dtype=np.int64)
        if img.min() < 0 or img.max() > 255:
            raise ValueError(f"{path}: sample outside 0..255")
        img = img.astype(np.uint8)
    return img.reshape(height, width, 3)


def write_ppm(path: str | Path, img8: np.ndarray) -> None:
    """Write uint8 display bytes of shape (H, W, 3) as a binary P6 PPM with maxval 255."""
    img = np.asarray(img8)
    if img.dtype != np.uint8 or img.ndim != 3 or img.shape[2] != 3:
        raise ValueError("img8 must be uint8 with shape (H, W, 3)")
    height, width = img.shape[:2]
    header = f"P6\n{width} {height}\n255\n".encode("ascii")
    Path(path).write_bytes(header + img.tobytes(order="C"))


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    """One PNG chunk: big-endian length, type, data, then the CRC-32 of type and data."""
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def write_png(path: str | Path, img8: np.ndarray) -> None:
    """Write uint8 display bytes of shape (H, W, 3) as an 8-bit RGB PNG (standard library only).

    Every scanline gets filter type 0 (None). The raster is one zlib-compressed IDAT chunk.
    """
    img = np.asarray(img8)
    if img.dtype != np.uint8 or img.ndim != 3 or img.shape[2] != 3:
        raise ValueError("img8 must be uint8 with shape (H, W, 3)")
    height, width = img.shape[:2]
    if height < 1 or width < 1:
        raise ValueError("img8 must not be empty")
    # IHDR: width, height, bit depth, colour type, then compression method 0, filter method 0 and
    # interlace method 0, the only values the PNG specification defines for those fields.
    ihdr = struct.pack(">IIBBBBB", width, height, _PNG_BIT_DEPTH, _PNG_COLOR_TYPE_RGB, 0, 0, 0)
    scanlines = np.empty((height, 1 + 3 * width), dtype=np.uint8)
    scanlines[:, 0] = _PNG_FILTER_NONE
    scanlines[:, 1:] = img.reshape(height, 3 * width)
    Path(path).write_bytes(
        _PNG_SIGNATURE
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(scanlines.tobytes()))
        + _png_chunk(b"IEND", b"")
    )


def smallpaint_display(sum_: np.ndarray, passes: int) -> np.ndarray:
    """SPEC §7 display mapping: ``byte = min((int)sum / passes, 255)`` per channel.

    ``sum_`` holds the per-channel sum over passes (float64). The sums are non-negative, so
    ``np.floor`` followed by the int64 cast equals the C++ truncation of ``(int)sum``.
    ``passes`` is the number of completed passes ``s`` of SPEC §7 and must be at least 1.
    """
    if passes < 1:
        raise ValueError("passes must be >= 1")
    whole = np.floor(np.asarray(sum_, dtype=np.float64)).astype(np.int64)
    return np.minimum(whole // passes, 255).astype(np.uint8)


@dataclass(frozen=True)
class OracleRender:
    """The contents of one oracle output directory (T1.1 ``--out DIR``).

    ``sum``: float64 (H, W, 3), per-pixel sum over passes of the trace colour.
    ``k_consumed``: uint64 (H, W), diffuse draws consumed per pixel over all passes.
    ``object_id``: int32 (H, W), SPEC §9 id of the unjittered primary hit, or -1.
    ``meta``: the parsed ``meta.json`` (resolved options, ``passes``, ``width``, ``height``, ...).
    """

    sum: np.ndarray
    k_consumed: np.ndarray
    object_id: np.ndarray
    meta: dict

    @property
    def passes(self) -> int:
        """Number of passes rendered, from ``meta.json``."""
        return int(self.meta["passes"])


def read_oracle(out_dir: str | Path) -> OracleRender:
    """Load ``sum.npy``, ``k_consumed.npy``, ``object_id.npy`` and ``meta.json`` in ``out_dir``."""
    root = Path(out_dir)
    meta = json.loads((root / "meta.json").read_text(encoding="utf-8"))
    return OracleRender(
        sum=np.load(root / "sum.npy"),
        k_consumed=np.load(root / "k_consumed.npy"),
        object_id=np.load(root / "object_id.npy"),
        meta=meta,
    )
