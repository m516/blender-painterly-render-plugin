"""The build requirements of pyproject.toml pin the exact versions that uv.lock resolved (T2.7)."""

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = REPO_ROOT / "pyproject.toml"
UV_LOCK = REPO_ROOT / "uv.lock"
# The packages named in [build-system] requires. Each one must appear there as name==version.
BUILD_PACKAGES = ("scikit-build-core", "nanobind")


def _locked_version(lock: dict, name: str) -> str:
    """The one version that uv.lock locks for package name."""
    versions = [package["version"] for package in lock["package"] if package["name"] == name]
    assert len(versions) == 1, f"uv.lock must lock exactly one {name}, found {versions}"
    return versions[0]


def test_build_system_requires_pin_the_locked_versions() -> None:
    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    lock = tomllib.loads(UV_LOCK.read_text(encoding="utf-8"))
    expected = sorted(f"{name}=={_locked_version(lock, name)}" for name in BUILD_PACKAGES)
    assert sorted(pyproject["build-system"]["requires"]) == expected
