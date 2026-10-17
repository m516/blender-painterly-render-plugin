"""Copies of smallpaint source must keep the source's bytes, line endings included.

The comment at `src/test/test_math_double3.cpp:16-18` names the source file and its lines 43-55,
says its `smallpaint_ref::Vec` is copied verbatim and "byte-identical to the source, tabs
included", and turns clang-format off around the copy. Those 13 source lines end in CRLF, so the
copy stays byte-identical only while it keeps its CR bytes. A rewrite that drops them changes no
C++ the compiler sees, so only a byte comparison catches it; that is this test.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

SOURCE_PATH = (
    REPO_ROOT / "third_party" / "smallpaint" / "smallpaint_painterly" / "smallpaint_painterly.cpp"
)
SOURCE_LINE_RANGE = (43, 55)
COPY_PATH = REPO_ROOT / "src" / "test" / "test_math_double3.cpp"
# The copy's own lines, pinned by BACKLOG item M3-FIX-T3.21b and confirmed by
# `grep -n 'struct Vec {' src/test/test_math_double3.cpp`.
COPY_LINE_RANGE = (24, 36)


def _split_lines(data: bytes) -> list[bytes]:
    """Split *data* on LF, keeping each line's own ending (LF, CRLF, or none for a last line)."""
    parts = data.split(b"\n")
    lines = [part + b"\n" for part in parts[:-1]]
    if parts[-1]:
        lines.append(parts[-1])
    return lines


def _block(data: bytes, line_range: tuple[int, int]) -> bytes:
    """Return the bytes of the inclusive 1-based *line_range* of *data*, endings included."""
    first, last = line_range
    return b"".join(_split_lines(data)[first - 1 : last])


def test_smallpaint_vec_copy_is_byte_identical_to_its_source() -> None:
    """The 13-line Vec copy occurs in test_math_double3.cpp as one contiguous block of source bytes.

    Both files are read in binary mode, so the comparison is on exact bytes and a CRLF line that
    lost its CR fails it.
    """
    source_bytes = SOURCE_PATH.read_bytes()
    copy_bytes = COPY_PATH.read_bytes()
    block = _block(source_bytes, SOURCE_LINE_RANGE)

    assert block in copy_bytes, (
        f"{COPY_PATH.relative_to(REPO_ROOT)} does not contain lines "
        f"{SOURCE_LINE_RANGE[0]}-{SOURCE_LINE_RANGE[1]} of "
        f"{SOURCE_PATH.relative_to(REPO_ROOT)} as one contiguous byte block"
    )
    assert _block(copy_bytes, COPY_LINE_RANGE) == block, (
        f"{COPY_PATH.relative_to(REPO_ROOT)} lines {COPY_LINE_RANGE[0]}-{COPY_LINE_RANGE[1]} "
        f"differ from {SOURCE_PATH.relative_to(REPO_ROOT)} lines "
        f"{SOURCE_LINE_RANGE[0]}-{SOURCE_LINE_RANGE[1]}"
    )
