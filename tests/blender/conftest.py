"""Pytest configuration for the Blender add-on tests (``make test-blender``).

``make env-blender`` installs ``bpy==5.2.2`` into the project environment. Without it
(``make env``, as in CI) nothing under ``tests/blender`` is collected, so ``make test``
stays green on a machine that has no Blender Python. The add-on is imported from
``src/blender/addon`` as the package ``painterly``, which is the name Blender gives it once
it is installed as an extension.

The package module is created here, at collection time, so that a test module can import
``painterly.properties`` and its siblings at module level; the ``addon`` fixture registers it.
"""

import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ADDON_DIR = REPO_ROOT / "src" / "blender" / "addon"

# PAINTERLY_BUILD_DIR is exported by the Makefile; a relative value is resolved against the repo
# root, as tests/conftest.py does. Its src/blender directory holds the built _painterly module.
BUILD_DIR = Path(os.environ.get("PAINTERLY_BUILD_DIR", "build/dev"))
if not BUILD_DIR.is_absolute():
    BUILD_DIR = REPO_ROOT / BUILD_DIR
MODULE_DIR = BUILD_DIR / "src" / "blender"

# bpy is Blender's own Python module; only `make env-blender` provides it.
HAS_BPY = importlib.util.find_spec("bpy") is not None
collect_ignore_glob = [] if HAS_BPY else ["test_*.py"]


def _load_addon() -> ModuleType | None:
    """Import the add-on package as ``painterly`` without registering it.

    Returns:
        The package module, or ``None`` when bpy is not installed.
    """
    if not HAS_BPY:
        return None

    if str(MODULE_DIR) not in sys.path:
        sys.path.insert(0, str(MODULE_DIR))

    spec = importlib.util.spec_from_file_location(
        "painterly", ADDON_DIR / "__init__.py", submodule_search_locations=[str(ADDON_DIR)]
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load the add-on package from {ADDON_DIR}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["painterly"] = module
    spec.loader.exec_module(module)
    return module


ADDON = _load_addon()


@pytest.fixture(scope="session")
def addon() -> ModuleType:
    """The registered add-on, imported from ``src/blender/addon`` as the package ``painterly``.

    Registering once per session mirrors Blender, which loads the add-on once; ``unregister()`` runs
    on teardown so a later test process starts clean.
    """
    if ADDON is None:
        pytest.skip("bpy is not importable; run `make env-blender` (bpy==5.2.2) to test the add-on")

    ADDON.register()
    yield ADDON
    ADDON.unregister()
