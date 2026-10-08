"""The native module imports and reports the version declared in pyproject.toml."""

import tomllib
from pathlib import Path

import _painterly
import pytest

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_version_info() -> None:
    expected_version = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    info = _painterly.version_info()
    assert info["version"] == expected_version
    assert info["stable_abi"] is True


def test_selftest_embree_unnormalized_direction() -> None:
    """Embree's t is parametric along the unnormalized direction, which SPEC §4 relies on.

    The ray starts at (0.25, 0.25, 1) with d = (0, 0, -2) and meets the triangle in the
    plane z = 0 after distance 1 along the ray. Since |d| = 2, the parametric t is 0.5.
    The tolerance is float32 round-off: 2**-23 is the float32 machine epsilon, and 4 of
    its ulps cover the intersection arithmetic.
    """
    result = _painterly.selftest()
    assert result["hit"] is True
    assert result["prim_id"] == 0
    assert result["t"] == pytest.approx(0.5, rel=4 * 2**-23)
