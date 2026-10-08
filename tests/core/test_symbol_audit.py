"""The built _painterly module passes tools/symbol_audit.py, the isolation audit of `make check`."""

import subprocess
import sys
from pathlib import Path

import _painterly
import pytest

AUDIT_TOOL = Path(__file__).resolve().parents[2] / "tools" / "symbol_audit.py"
AUDITED_PLATFORMS = ("linux", "darwin", "win32")


def test_built_module_passes_symbol_audit() -> None:
    if sys.platform not in AUDITED_PLATFORMS:
        pytest.skip(f"symbol_audit.py has no audit implementation for {sys.platform}")
    completed = subprocess.run(
        [sys.executable, str(AUDIT_TOOL), _painterly.__file__],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
