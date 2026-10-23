"""Shims under src/cycles/shim/ (T3.2) shadow upstream Cycles paths, never vendored files.

Each shim file (a) starts with the comment ``Shim: replaces Cycles <path> ...``, where ``<path>`` is
the file's own path relative to src/cycles/shim/, which is the upstream path it shadows, and (b) has
no vendored counterpart: that path is neither a ``dest`` in third_party/cycles/VENDORED.toml nor a
file under third_party/cycles/. A file vendored and shimmed at once would put two copies on the
include path (docs/architecture.md, "Source layout and naming").

src/ and third_party/cycles/ also share no top-level directory (T3.22). Both are include
directories of cycles_util, and compilers search the SYSTEM directory third_party/cycles/ after
src/, so a shared name could let a file under src/ shadow a vendored header.

Each shim header also defines its marker macro and is asserted in
src/cycles/shim_markers.cpp (T6.1, "Shim markers").
"""

import re
import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
SHIM_DIR = REPO_ROOT / "src" / "cycles" / "shim"
VENDOR_DIR = REPO_ROOT / "third_party" / "cycles"
MANIFEST = VENDOR_DIR / "VENDORED.toml"
# A shim's first line opens with one of these C or C++ comment forms, then the marker.
COMMENT_OPENERS = ("/* ", "// ")
MARKER = "Shim: replaces Cycles "


def _relative(path: Path) -> str:
    """Path of a shim file relative to SHIM_DIR, in POSIX form: the upstream path it shadows."""
    return path.relative_to(SHIM_DIR).as_posix()


def _vendored_dests() -> set[str]:
    """The dest of every [[file]] entry in VENDORED.toml, relative to third_party/cycles/."""
    with MANIFEST.open("rb") as handle:
        data = tomllib.load(handle)
    return {entry["dest"] for entry in data.get("file", [])}


SHIM_FILES = sorted(path for path in SHIM_DIR.rglob("*") if path.is_file())
SHIM_IDS = [_relative(path) for path in SHIM_FILES]


def test_shim_directory_is_not_empty() -> None:
    """The shim directory holds files (T3.2, T3.3), so the parametrized tests below run."""
    assert SHIM_FILES, f"no shim files under {SHIM_DIR}"


@pytest.mark.parametrize("shim", SHIM_FILES, ids=SHIM_IDS)
def test_shim_names_the_upstream_path_it_replaces(shim: Path) -> None:
    """The first line is `/* Shim: replaces Cycles <path> ...` (or `//`), naming the shim's path."""
    first_line = shim.read_text(encoding="utf-8").splitlines()[0]
    expected = MARKER + _relative(shim) + " "
    prefixes = tuple(opener + expected for opener in COMMENT_OPENERS)
    assert first_line.startswith(prefixes), (
        f"{_relative(shim)}: the first line must start with a comment opener and {expected!r}"
    )


@pytest.mark.parametrize("shim", SHIM_FILES, ids=SHIM_IDS)
def test_shim_has_no_vendored_counterpart(shim: Path) -> None:
    """The shim's path is no dest in VENDORED.toml, and no file of that path is vendored."""
    relative = _relative(shim)
    assert relative not in _vendored_dests(), (
        f"{relative} is shimmed but also listed in VENDORED.toml"
    )
    assert not (VENDOR_DIR / relative).exists(), (
        f"{relative} is shimmed but also exists under third_party/cycles/"
    )


def test_src_and_vendored_tree_share_no_top_level_directory() -> None:
    """No directory directly under src/ has the name of one directly under third_party/cycles/."""
    src_names = {path.name for path in SRC_DIR.iterdir() if path.is_dir()}
    vendored_names = {path.name for path in VENDOR_DIR.iterdir() if path.is_dir()}
    shared = sorted(src_names & vendored_names)
    assert not shared, f"src/ and third_party/cycles/ share the top-level directories {shared}"


SHIM_MARKERS_CPP = REPO_ROOT / "src" / "cycles" / "shim_markers.cpp"
SHIM_HEADERS = [path for path in SHIM_FILES if path.suffix == ".h"]
SHIM_HEADER_IDS = [_relative(path) for path in SHIM_HEADERS]


def shim_marker(relpath: str) -> str:
    """Marker macro of the shim header at relpath (POSIX, relative to src/cycles/shim/).

    T6.1 "Shim markers": PAINTERLY_SHIM_ and relpath upper-cased, with "/" and "." replaced by "_".
    """
    return "PAINTERLY_SHIM_" + relpath.upper().replace("/", "_").replace(".", "_")


@pytest.mark.parametrize("shim", SHIM_HEADERS, ids=SHIM_HEADER_IDS)
def test_every_shim_header_defines_its_marker(shim: Path) -> None:
    """The header has a line that reads `#define <marker> 1` after strip()."""
    expected = f"#define {shim_marker(_relative(shim))} 1"
    lines = [line.strip() for line in shim.read_text(encoding="utf-8").splitlines()]
    assert expected in lines, f"{_relative(shim)}: no line {expected!r}"


@pytest.mark.parametrize("shim", SHIM_HEADERS, ids=SHIM_HEADER_IDS)
def test_shim_markers_cpp_asserts_every_marker(shim: Path) -> None:
    """shim_markers.cpp has `static_assert(<marker> == 1,`, with any whitespace.

    clang-format may wrap a static_assert directly after its opening parenthesis.
    """
    marker = shim_marker(_relative(shim))
    text = SHIM_MARKERS_CPP.read_text(encoding="utf-8")
    pattern = rf"static_assert\(\s*{re.escape(marker)}\s*==\s*1\s*,"
    assert re.search(pattern, text), f"src/cycles/shim_markers.cpp asserts no {marker} == 1"
