"""THIRD_PARTY_NOTICES.md names every non-Apache licence stated under third_party/cycles.

`third_party/cycles` is vendored verbatim from Blender v5.2.2 and its files are Apache-2.0, which
notices row 6 covers for the whole tree. Five of its files state an `SPDX-License-Identifier` of
their own in their own header instead. M8-FIX-NOTICES gave each of them a notices row and the
`LICENSES/` text that row cites; these two tests keep that gap shut.

Neither test holds a list of files: the subjects come from the vendored tree and the notices, so a
new non-Apache header, or a row whose file or licence text disappears, fails here. Both read text
only and import no bpy, so they run in `CHECK`.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
NOTICES = REPO_ROOT / "THIRD_PARTY_NOTICES.md"
CYCLES = REPO_ROOT / "third_party" / "cycles"

# The licence that notices row 6 covers for the whole vendored tree; every other identifier a
# vendored file states needs a row of its own.
DEFAULT_LICENSE = "Apache-2.0"

# An SPDX licence identifier in a file header, as the vendored files write it, e.g.
# `SPDX-License-Identifier: BSD-3-Clause`. A file may state several.
SPDX_LICENSE = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9.+-]+)")

# A licence text the notices cite, relative to the repository root, e.g.
# `LICENSES/Zlib-aladdin.txt`.
LICENSE_PATH = re.compile(r"LICENSES/[A-Za-z0-9._-]+\.txt")


def _notice_lines() -> list[str]:
    """The lines of THIRD_PARTY_NOTICES.md; one table row per component."""
    return NOTICES.read_text(encoding="utf-8").splitlines()


def _states(line: str, token: str) -> bool:
    """Whether line states token itself, and not only inside a `LICENSES/<name>.txt` it cites.

    A licence text's file name contains its own identifier (`LICENSES/Zlib-aladdin.txt`), so a row
    that only cited the text would pass a plain substring test while stating no licence. The
    citations are therefore removed before the test.
    """
    return token in LICENSE_PATH.sub("", line)


def _non_default_licenses() -> list[tuple[Path, str]]:
    """Every (file, identifier) pair a file under third_party/cycles states, but Apache-2.0."""
    found = []
    for path in sorted(CYCLES.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for ident in sorted(set(SPDX_LICENSE.findall(text)) - {DEFAULT_LICENSE}):
            found.append((path, ident))
    return found


def test_every_non_apache_vendored_licence_has_a_notices_row() -> None:
    """Some notices line names both a file's name and each licence that file states."""
    lines = _notice_lines()
    missing = [
        f"{path.relative_to(REPO_ROOT).as_posix()}: {ident}"
        for path, ident in _non_default_licenses()
        if not any(_states(line, path.name) and _states(line, ident) for line in lines)
    ]
    assert not missing, "THIRD_PARTY_NOTICES.md has no row naming these vendored licences: " + (
        ", ".join(missing)
    )


def test_every_licence_text_the_notices_cite_exists() -> None:
    """Each `LICENSES/<name>.txt` path in THIRD_PARTY_NOTICES.md is a file of the repository."""
    cited = sorted(set(LICENSE_PATH.findall("\n".join(_notice_lines()))))
    assert cited, "THIRD_PARTY_NOTICES.md cites no LICENSES/*.txt text"
    missing = [name for name in cited if not (REPO_ROOT / name).is_file()]
    assert not missing, "cited in THIRD_PARTY_NOTICES.md but missing: " + ", ".join(missing)
