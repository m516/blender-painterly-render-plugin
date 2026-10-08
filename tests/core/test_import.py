"""The native module imports and reports its version information."""

import _painterly


def test_version_info() -> None:
    info = _painterly.version_info()
    assert info["version"] == "0.1.0"
    assert info["stable_abi"] is True
