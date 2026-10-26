"""The extension end to end: the built zip, installed in Blender, equals the oracle (T4.4).

``make blender-it`` builds the extension zip and then runs this test. The test installs the zip into
an isolated Blender user directory, renders SPEC §9 through the installed extension with
``run_reference.py``, renders the same configuration with the smallpaint oracle, and compares the
two images bit for bit::

    blender.npy == to_blender_rows(scene_linear(oracle.sum, 4, 1))

That one equality covers the extension, the bundled wheel, the sync, the film mapping, the row
orientation and the core.

The test is slow and skips when its inputs are missing, so ``make test-slow`` and ``make check``
stay green on a machine without them:

- no executable at ``$BLENDER`` (the Makefile exports it; ``make blender`` fetches Blender);
- no ``build/extension/zip_path.txt`` (``make blender-it``'s extension step writes it, and it
  writes no zip when no wheel can be built: no ``uv`` and no build backend).

Nothing here is a tolerance: the same core rendered both sides, and the EXR round trip stores
float32 unchanged.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
from pathlib import Path
from types import ModuleType

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RUN_REFERENCE = Path(__file__).with_name("run_reference.py")
# `make extension` writes the zip path here (tools/build_extension.py, card step 5).
ZIP_PATH_FILE = REPO_ROOT / "build" / "extension" / "zip_path.txt"

# The card's render configuration, which run_reference.py sets inside Blender: a 64 px square
# image, 4 passes, the image chain, the scene_linear output mode at exposure 1.
SIZE = 64
PASSES = 4
CHAIN = "image"
EXPOSURE = 1.0

# SPEC §2: a bit-parity test runs the oracle with the exact generator. It is one of
# scenes.ORACLE_EXACT_KNOBS; the check below catches a change that drops it.
HALTON_EXACT = "exact"


def _load_by_path(name: str, path: Path) -> ModuleType:
    """Import a module by file path, as tests/core/test_film.py loads the add-on's film module.

    Importing ``tests/core/scenes.py`` or ``src/blender/addon/film.py`` through their packages would
    run ``addon/__init__.py``, which imports ``bpy``: the tests must not need Blender's Python.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None, f"no module spec for {path}"
    assert spec.loader is not None, f"no loader for {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scenes = _load_by_path("scenes", REPO_ROOT / "tests" / "core" / "scenes.py")
film = _load_by_path("painterly_film", REPO_ROOT / "src" / "blender" / "addon" / "film.py")


def blender_executable() -> Path:
    """The Blender executable of ``$BLENDER``; ``make`` exports it."""
    return Path(os.environ.get("BLENDER", ""))


def _require_blender() -> Path:
    """The Blender executable, or skip when it is not there."""
    blender = blender_executable()
    if not os.environ.get("BLENDER"):
        pytest.skip(
            "BLENDER is unset; `make blender` fetches Blender 5.2.2 and the Makefile exports it"
        )
    if not blender.is_file():
        pytest.skip(f"no Blender executable at {blender}; run `make blender`")
    return blender


def _require_zip() -> Path:
    """The zip that ``make extension`` built, or skip when there is none."""
    if not ZIP_PATH_FILE.is_file():
        pytest.skip(
            f"no {ZIP_PATH_FILE.relative_to(REPO_ROOT)}; run `make blender-it`, which builds the "
            "extension (when no painterly-core wheel can be built, it writes no zip and this "
            "test skips)"
        )
    zip_path = Path(ZIP_PATH_FILE.read_text(encoding="utf-8").strip())
    if not zip_path.is_file():
        pytest.skip(
            f"{ZIP_PATH_FILE.name} names {zip_path}, which does not exist; rerun `make extension`"
        )
    return zip_path


def _run(cmd: list[str], env: dict[str, str], what: str) -> subprocess.CompletedProcess[str]:
    """Run ``cmd`` and fail with its output when it exits non-zero."""
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(
            f"{what} failed with status {proc.returncode}: {' '.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def oracle_options(*, jitter: float) -> dict[str, object]:
    """The oracle's options for the extension render.

    The reference knobs come from ``scenes.ORACLE_EXACT_KNOBS`` (the T3.16 float32 values, derived
    from ``apply_reference_knobs()``), so the oracle and the core get the same numbers, and the
    generator is the exact one (SPEC §2). The other options are the extension's own settings: the
    reference scene at 64 px, 4 passes, the image chain, the default ghost policy, alpha, u2, seed
    and continue_after_emitter, one thread, and the image-plane jitter the core derives from the
    integrator socket ``jitter`` (SPEC §7: twice the socket value, T3.13).
    """
    return {
        "size": SIZE,
        "passes": PASSES,
        "chain": CHAIN,
        "ghost": "all",
        "alpha": scenes.oracle_float(0.0),
        "u2": "same",
        "continue_after_emitter": True,
        "seed": 0,
        # The card's `--jitter repr(2 * float(np.float32(jitter)))`: the double that prints
        # round-trips exactly, so the oracle gets the core's image-plane jitter bit for bit.
        "jitter": repr(2 * float(np.float32(jitter))),
        # The oracle renders on one thread, so the reference is one deterministic sequence.
        "threads": 1,
        **scenes.ORACLE_EXACT_KNOBS,
    }


@pytest.mark.slow
def test_the_extension_renders_the_reference_scene_bit_for_bit(tmp_path: Path) -> None:
    """Install the built zip in Blender, render it, and compare with the oracle bit for bit."""
    blender = _require_blender()
    zip_path = _require_zip()

    # One isolated Blender profile per test, so the install touches no user directory. Every Blender
    # run below gets it, and `--factory-startup` then reads exactly the preferences installed here.
    user_resources = tmp_path / "blender-user"
    user_resources.mkdir()
    env = dict(os.environ)
    env["BLENDER_USER_RESOURCES"] = str(user_resources)

    # Step 2: install the zip into the user_default repository and enable it (-e).
    _run(
        [
            str(blender),
            "--command",
            "extension",
            "install-file",
            "-r",
            "user_default",
            "-e",
            str(zip_path),
        ],
        env,
        "extension install-file",
    )

    # Step 3: render the reference scene through the installed extension.
    out_dir = tmp_path / "render"
    _run(
        [
            str(blender),
            "-b",
            "--factory-startup",
            "--python-exit-code",
            "1",
            "--python",
            str(RUN_REFERENCE),
            "--",
            str(out_dir),
        ],
        env,
        "run_reference.py",
    )

    rendered = np.load(out_dir / "blender.npy")
    meta = json.loads((out_dir / "blender.json").read_text(encoding="utf-8"))
    assert meta["engine"] == "PAINTERLY"
    assert meta["shape"] == [SIZE, SIZE, film.RGBA_CHANNELS]
    assert meta["dtype"] == "float32"

    # Step 4: the oracle, with the same configuration and the jitter the render passed to the core.
    options = oracle_options(jitter=meta["jitter"])
    assert options["halton"] == HALTON_EXACT, "SPEC §2: a bit-parity test uses the exact generator"
    from painterly_analysis import oracle as oracle_module

    render = oracle_module.run_oracle(tmp_path / "oracle", **options)

    # Step 5: exact equality. The same core rendered both sides, and the EXR round trip stores
    # float32 unchanged, so a difference of one ulp is a defect, not a rounding to allow for.
    expected = film.to_blender_rows(film.scene_linear(render.sum, PASSES, EXPOSURE))
    assert rendered.shape == expected.shape
    assert rendered.dtype == expected.dtype
    assert np.array_equal(rendered, expected), (
        f"the extension's render differs from the oracle at "
        f"{np.argwhere(rendered != expected)[:1].tolist()}"
    )
    # And the bit patterns, which np.array_equal does not see (a signed zero, a NaN payload).
    assert rendered.tobytes() == expected.tobytes()
