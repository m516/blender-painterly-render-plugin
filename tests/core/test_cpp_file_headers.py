"""Every C++ file under src/test/ and src/blender/ opens with the project's SPDX header (TQ.1 F14).

The header is the block comment that src/painterly/ uses (Cycles style), as the file's first two
lines:

    /* SPDX-FileCopyrightText: 2026 The Painterly Authors
     * SPDX-License-Identifier: GPL-3.0-or-later */

Third-party code copied into these files is listed in THIRD_PARTY_NOTICES.md.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
DIRECTORIES = ("src/test", "src/blender")
SUFFIXES = (".cpp", ".h")
HEADER = (
    "/* SPDX-FileCopyrightText: 2026 The Painterly Authors",
    " * SPDX-License-Identifier: GPL-3.0-or-later */",
)

FILES = sorted(
    path
    for directory in DIRECTORIES
    for path in (REPO_ROOT / directory).rglob("*")
    if path.is_file() and path.suffix in SUFFIXES
)


def test_there_are_files_to_check() -> None:
    """Both directories hold C++ files, so the parametrized test runs."""
    for directory in DIRECTORIES:
        assert any(path.is_relative_to(REPO_ROOT / directory) for path in FILES), directory


@pytest.mark.parametrize("path", FILES, ids=[p.relative_to(REPO_ROOT).as_posix() for p in FILES])
def test_file_opens_with_the_spdx_header(path: Path) -> None:
    """The first two lines are the project's SPDX block comment."""
    first_lines = tuple(path.read_text(encoding="utf-8").split("\n")[: len(HEADER)])
    assert first_lines == HEADER, f"{path.relative_to(REPO_ROOT)} must start with {HEADER}"
