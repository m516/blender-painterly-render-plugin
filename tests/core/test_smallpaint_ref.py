"""src/test/smallpaint_ref.h copies smallpaint's and the oracle's code verbatim (TQ.1 F16, T3.23).

Each block of the header between a run of ``// verbatim <file>:<first>[-<last>]`` marker lines
and the line ``// end verbatim`` must equal every range its markers cite, line for line. The one
allowed difference is the line ending: smallpaint's sources are CRLF and the header is LF, so one
trailing carriage return is removed from each source line. A block that cites two files also
pins that the two agree there, for example that the oracle's Vec is smallpaint's. When an edit
moves a cited source line, this test names the stale citation.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HEADER = REPO_ROOT / "src" / "test" / "smallpaint_ref.h"
MARKER = re.compile(r"^// verbatim (?P<path>\S+):(?P<first>\d+)(?:-(?P<last>\d+))?$")
END = "// end verbatim"


def _lines(path: Path) -> list[str]:
    """The lines of a file without terminators: split at LF, then one trailing CR removed."""
    return [line.removesuffix("\r") for line in path.read_bytes().decode("utf-8").split("\n")]


def _citations() -> list[tuple[str, int, int, tuple[str, ...]]]:
    """(file, first, last, block) for every marker line of the header, in file order."""
    citations = []
    run: list[tuple[str, int, int]] = []
    block: list[str] = []
    in_block = False
    for line in HEADER.read_text(encoding="utf-8").split("\n"):
        match = MARKER.match(line)
        if match and not block:
            first = int(match["first"])
            run.append((match["path"], first, int(match["last"] or first)))
            in_block = True
        elif line == END:
            assert in_block, "// end verbatim without a marker line"
            citations.extend((path, first, last, tuple(block)) for path, first, last in run)
            run, block, in_block = [], [], False
        elif in_block:
            block.append(line)
    assert not in_block, "a verbatim block is not closed"
    return citations


CITATIONS = _citations()


def test_header_has_verbatim_blocks_and_lf_line_endings() -> None:
    """The header cites some ranges, and every block holds code, so the parametrized test runs."""
    assert CITATIONS, f"no // verbatim markers in {HEADER}"
    assert all(block for *_, block in CITATIONS), "a verbatim block is empty"
    assert b"\r" not in HEADER.read_bytes(), "smallpaint_ref.h must use LF line endings"


@pytest.mark.parametrize(
    ("path", "first", "last", "block"),
    CITATIONS,
    ids=[f"{path}:{first}-{last}" for path, first, last, _ in CITATIONS],
)
def test_block_is_the_cited_source_range(
    path: str, first: int, last: int, block: tuple[str, ...]
) -> None:
    """The block equals source lines first..last (1-based, inclusive) of the cited file."""
    source = _lines(REPO_ROOT / path)
    assert last <= len(source), f"{path} has fewer than {last} lines"
    assert tuple(source[first - 1 : last]) == block, (
        f"smallpaint_ref.h block citing {path}:{first}-{last} differs from the source"
    )
