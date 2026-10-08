"""The native module imports and reports the version declared in pyproject.toml."""

import tomllib
from pathlib import Path

import _painterly

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_version_info() -> None:
    expected_version = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    info = _painterly.version_info()
    assert info["version"] == expected_version
    assert info["stable_abi"] is True
