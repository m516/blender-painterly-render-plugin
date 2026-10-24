"""Upstream lines that the shims of card T6.4 copy stay byte for byte upstream's.

Four shims under src/cycles/shim/ hold verbatim lines of upstream Cycles (Blender v5.2.2, the
[upstream.cycles] pin of third_party/cycles/VENDORED.toml), copied from the checkout.
tools/vendor_sync.py check covers only [[file]] and [[fragment]] entries, so this test covers the
copies: for each upstream span below, exactly one run of consecutive lines of the shim has the
span's sha256. A span's sha256 is over its lines, each followed by a newline. Opus computed the
values from the pinned checkout, so the test needs neither the network nor the checkout. Later
cards that replace one of these shims keep the spans.
"""

import hashlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SHIM_DIR = REPO_ROOT / "src" / "cycles" / "shim"

# (shim path under src/cycles/shim/, upstream path under intern/cycles/, first line, last line,
# sha256 of the upstream lines first..last).
SPANS = [
    (
        "scene/attribute.cpp",
        "scene/attribute.cpp",
        453,
        543,
        "3a0396320c7135b7ec8bd32a545bb855b8923f05310cd02378fafcd68c19a162",
    ),
    (
        "scene/attribute.cpp",
        "scene/attribute.cpp",
        1190,
        1210,
        "d249c7fa36f9ed92ae0e8e8221030dc25b759cb0e7103817218d9eefa5a02665",
    ),
    (
        "scene/attribute.cpp",
        "scene/attribute.cpp",
        1224,
        1238,
        "79d2b18e543313cc5eea42ea8588559b20afe64ee534c956c6a3fd90332940a2",
    ),
    (
        "scene/shader.cpp",
        "scene/shader.cpp",
        483,
        502,
        "a14b0c2dbddf520adf49bd165d22a51c0ddfe299cf1bd0a10405b2d129a569e5",
    ),
    (
        "scene/shader.cpp",
        "scene/shader.cpp",
        894,
        897,
        "d182426222e2abf0c7221e17d9fdf5b559c2d407af28499310aa120e683cd09d",
    ),
    (
        "util/string.cpp",
        "util/string.cpp",
        120,
        135,
        "5013e2042ded50ef4f93507c4008b52a3f97e9732d99dc48fee3f02f689a5221",
    ),
    (
        "util/string.cpp",
        "util/string.cpp",
        244,
        250,
        "d856cb37ad37b3c62d9e28d85df96eafd86b12d1cd9df4c00dade3fc6e75cae0",
    ),
    (
        "util/log.h",
        "util/log.h",
        17,
        29,
        "090e987fa942ffe8a95f3810e0284acfa16890499e73f8ac6c32b6cf4f64dc26",
    ),
    (
        "util/log.h",
        "util/log.h",
        110,
        113,
        "3c0f96080e1c9eaeb364de6c4b053497fe6f027d9b9538d68db6108bcbf47434",
    ),
    (
        "util/log.h",
        "util/log.cpp",
        138,
        141,
        "2accbb43ec0a0c551e38dd199caa3d20d14b4b63feb95fb30260c2b92d761c67",
    ),
]


def _runs_with_sha256(lines: list[str], length: int, sha256: str) -> int:
    """How many runs of `length` consecutive lines, each followed by a newline, have `sha256`."""
    count = 0
    for start in range(len(lines) - length + 1):
        text = "".join(line + "\n" for line in lines[start : start + length])
        if hashlib.sha256(text.encode("utf-8")).hexdigest() == sha256:
            count += 1
    return count


@pytest.mark.parametrize(
    ("shim", "upstream_path", "first", "last", "sha256"),
    SPANS,
    ids=[f"{span[0]}={span[1]}:{span[2]}-{span[3]}" for span in SPANS],
)
def test_shim_holds_upstream_span_once(
    shim: str, upstream_path: str, first: int, last: int, sha256: str
) -> None:
    lines = (SHIM_DIR / shim).read_text(encoding="utf-8").splitlines()
    found = _runs_with_sha256(lines, last - first + 1, sha256)
    assert found == 1, (
        f"src/cycles/shim/{shim}: {upstream_path}:{first}-{last} occurs {found} times"
    )


def test_spans_are_distinct() -> None:
    assert len({span[4] for span in SPANS}) == len(SPANS)
