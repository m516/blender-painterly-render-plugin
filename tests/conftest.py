"""Pytest configuration: make the freshly built _painterly module importable.

Two environment variables choose which _painterly the tests import:

- PAINTERLY_BUILD_DIR (default build/dev, exported by the Makefile) names the CMake build
  directory. A relative value is resolved against the repo root. Its src/blender directory goes
  first on sys.path.
- PAINTERLY_TEST_INSTALLED=1 (set by [tool.cibuildwheel] test-environment) keeps the build
  directory off sys.path, so the tests import the module of the installed wheel.
  tests/core/test_import.py checks the origin either way.
"""

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# PAINTERLY_BUILD_DIR is exported by the Makefile. A relative value is resolved
# against the repo root.
BUILD_DIR = Path(os.environ.get("PAINTERLY_BUILD_DIR", "build/dev"))
if not BUILD_DIR.is_absolute():
    BUILD_DIR = REPO_ROOT / BUILD_DIR

if os.environ.get("PAINTERLY_TEST_INSTALLED") != "1":
    sys.path.insert(0, str(BUILD_DIR / "src" / "blender"))


@pytest.fixture(scope="session")
def build_dir() -> Path:
    """BUILD_DIR, for tests that check where _painterly was imported from."""
    return BUILD_DIR
