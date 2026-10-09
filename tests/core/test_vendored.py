"""third_party/cycles matches its manifest (T3.1): `tools/vendor_sync.py check` exits 0 offline."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_TOOL = REPO_ROOT / "tools" / "vendor_sync.py"


def test_vendored_tree_matches_manifest() -> None:
    """The offline check (no network, no checkouts) reports no difference from VENDORED.toml."""
    result = subprocess.run(
        [sys.executable, str(VENDOR_TOOL), "check"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"vendor_sync check failed:\n{result.stderr}{result.stdout}"
