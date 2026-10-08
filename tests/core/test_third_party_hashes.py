"""Every file listed in tests/data/MANIFEST.sha256 exists and matches its pinned sha256.

The manifest covers the imported smallpaint sources and the reference images (CLAUDE.md rule 1).
Hashes are compared exactly; there is no tolerance.
"""

import hashlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "tests" / "data" / "MANIFEST.sha256"


def _read_manifest() -> list[tuple[str, str]]:
    """Return (sha256 hex digest, repo-relative path) pairs from MANIFEST.sha256.

    The file uses the `sha256sum` format: one `<64 hex digits>  <path>` line per file, with
    paths relative to the repository root.
    """
    entries = []
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        digest, path = line.split("  ", 1)
        entries.append((digest, path))
    return entries


ENTRIES = _read_manifest()


@pytest.mark.parametrize(("digest", "path"), ENTRIES, ids=[path for _, path in ENTRIES])
def test_file_matches_manifest(digest: str, path: str) -> None:
    file = REPO_ROOT / path
    assert file.is_file(), f"listed in MANIFEST.sha256 but missing: {path}"
    assert hashlib.sha256(file.read_bytes()).hexdigest() == digest, f"sha256 mismatch: {path}"


THIRD_PARTY_TREE = REPO_ROOT / "third_party" / "smallpaint"
REFERENCE_TREE = REPO_ROOT / "tests" / "data" / "reference"
# The two README.md files document the pinned trees; they are not pinned themselves.
UNPINNED_READMES = {THIRD_PARTY_TREE / "README.md", REFERENCE_TREE / "README.md"}


def test_manifest_covers_tree() -> None:
    """The manifest lists exactly the files under the pinned trees, minus their README.md files."""
    tree_paths = {
        path.relative_to(REPO_ROOT).as_posix()
        for root in (THIRD_PARTY_TREE, REFERENCE_TREE)
        for path in root.rglob("*")
        if path.is_file() and path not in UNPINNED_READMES
    }
    manifest_paths = {path for _, path in ENTRIES}
    not_in_manifest = sorted(tree_paths - manifest_paths)
    not_in_tree = sorted(manifest_paths - tree_paths)
    assert not not_in_manifest, f"not listed in MANIFEST.sha256: {not_in_manifest}"
    assert not not_in_tree, f"listed in MANIFEST.sha256 but not in the pinned trees: {not_in_tree}"
