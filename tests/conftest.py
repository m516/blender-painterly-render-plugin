"""Pytest configuration: make the freshly built _painterly module importable."""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# PAINTERLY_BUILD_DIR is exported by the Makefile. A relative value is resolved
# against the repo root.
build_dir = Path(os.environ.get("PAINTERLY_BUILD_DIR", "build/dev"))
if not build_dir.is_absolute():
    build_dir = REPO_ROOT / build_dir

sys.path.insert(0, str(build_dir / "src" / "blender"))
