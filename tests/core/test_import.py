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


def test_selftest_embree_unnormalized_direction() -> None:
    """Embree's t is parametric along the unnormalized direction, which SPEC §4 and §5 rely on.

    The ray starts at (0.25, 0.25, 1) with d = (0, 0, -2) and meets the triangle in the plane z = 0
    after distance 1 along the ray. Since |d| = 2, the parametric t is 0.5 and the metric distance
    is 1.0. Embree's hit t depends on the runtime ISA (its AVX2 kernels use explicit FMA), so no
    exact value is asserted.
    """
    result = _painterly.selftest()
    assert result["hit"] is True
    assert result["prim_id"] == 0
    # parametric (0.5) vs metric (1.0) distance along |d| = 2 (SPEC §4, §5)
    assert abs(result["t"] - 0.5) < abs(result["t"] - 1.0)
    assert result["tasking_system"] == 0  # EMBREE_TASKING_SYSTEM=INTERNAL
