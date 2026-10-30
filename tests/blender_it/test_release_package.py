"""`tools/release.py package` end to end, with the real Blender (T8.1).

The test builds and verifies the five release assets from three synthetic wheels and the real
Blender 5.2.2, which is slow, so the whole module is marked ``slow``. It runs no network access.

``<blender>`` is the ``BLENDER`` environment variable, which the Makefile exports
(``BLENDER ?= …``, then ``export BLENDER``). The test skips only when ``BLENDER`` is unset.

The release stages into its own ``--work-dir`` and writes into its own ``--out-dir``, so it never
touches ``make extension``'s outputs: the test snapshots ``build/extension/zip_path.txt``,
``dist/`` and the staged manifest and checks that they are unchanged afterwards.
"""

import hashlib
import os
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_TOOL = REPO_ROOT / "tools" / "release.py"
# `make extension`'s outputs: its zip path, the zips themselves, and the staged manifest, whose
# bytes differ between a one-platform stage and a three-platform one.
ZIP_PATH_FILE = REPO_ROOT / "build" / "extension" / "zip_path.txt"
DIST_DIR = REPO_ROOT / "dist"
STAGED_MANIFEST = REPO_ROOT / "build" / "extension" / "painterly" / "blender_manifest.toml"

pytestmark = pytest.mark.slow

# The platform tag sets of the three release wheels (PEP 425, PEP 600): the manylinux x86_64 tag
# set that auditwheel writes on the manylinux_2_28 image, macOS arm64 at deployment target 11.0, and
# win_amd64 (pyproject.toml, [tool.cibuildwheel]).
LINUX_TAGS = "manylinux_2_27_x86_64.manylinux_2_28_x86_64"
MACOS_TAGS = "macosx_11_0_arm64"
WINDOWS_TAGS = "win_amd64"
STANDARD_TAG_SETS = (LINUX_TAGS, MACOS_TAGS, WINDOWS_TAGS)


def _load_release_tool():
    """`tools/release.py`, imported by path: `tools/` is not a package."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("release", RELEASE_TOOL)
    assert spec is not None and spec.loader is not None, f"no module spec for {RELEASE_TOOL}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


release = _load_release_tool()
VERSION = release.release_version(REPO_ROOT)
EXTENSION_ID = release.read_manifest(REPO_ROOT)["id"]
PYTHON_TAG = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"][
    "scikit-build"
]["wheel"]["py-api"]


def _require_blender() -> Path:
    """The Blender executable of ``$BLENDER``; the test skips only when it is unset."""
    value = os.environ.get("BLENDER")
    if not value:
        pytest.skip("BLENDER is unset; `make blender-it` and the Makefile export it")
    blender = Path(value)
    assert blender.is_file(), f"BLENDER names {blender}, which does not exist"
    return blender


def write_synthetic_wheel(directory: Path, platform_tags: str) -> Path:
    """Write a synthetic wheel for one platform tag set and return its path.

    Blender's build never opens a wheel, so a zip with the one ``WHEEL`` member is packed exactly
    like a real wheel.
    """
    directory.mkdir(parents=True, exist_ok=True)
    name = f"painterly_core-{VERSION}-{PYTHON_TAG}-abi3-{platform_tags}.whl"
    path = directory / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"painterly_core-{VERSION}.dist-info/WHEEL", "Wheel-Version: 1.0\n")
    return path


def standard_wheels(directory: Path) -> list[Path]:
    """The three standard synthetic wheels, in `RELEASE_PLATFORMS` order."""
    return [write_synthetic_wheel(directory, tags) for tags in STANDARD_TAG_SETS]


def run_package(blender: Path, wheel_dir: Path, out_dir: Path, notes: Path, work_dir: Path):
    """Run `tools/release.py package` from the repository root."""
    return subprocess.run(
        [
            sys.executable,
            "-I",
            str(RELEASE_TOOL),
            "package",
            "--blender",
            str(blender),
            "--wheel-dir",
            str(wheel_dir),
            "--out-dir",
            str(out_dir),
            "--notes",
            str(notes),
            "--work-dir",
            str(work_dir),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def snapshot() -> tuple[bytes | None, list[str] | None, bytes | None]:
    """`make extension`'s outputs: zip_path.txt, dist/ and the staged manifest."""
    return (
        ZIP_PATH_FILE.read_bytes() if ZIP_PATH_FILE.is_file() else None,
        sorted(os.listdir(DIST_DIR)) if DIST_DIR.is_dir() else None,
        STAGED_MANIFEST.read_bytes() if STAGED_MANIFEST.is_file() else None,
    )


def test_package_builds_and_verifies_the_five_assets(tmp_path: Path) -> None:
    blender = _require_blender()
    before = snapshot()
    wheelhouse = tmp_path / "wheelhouse"
    wheels = standard_wheels(wheelhouse)
    out_dir = tmp_path / "release"
    notes = tmp_path / "notes.md"
    work_dir = tmp_path / "work"

    proc = run_package(blender, wheelhouse, out_dir, notes, work_dir)
    assert proc.returncode == 0, proc.stderr
    names = release.asset_names(EXTENSION_ID, VERSION)
    assert proc.stdout.splitlines() == [str(out_dir / name) for name in names]
    assert sorted(os.listdir(out_dir)) == names

    checksums = (out_dir / release.CHECKSUMS_NAME).read_text(encoding="utf-8").splitlines()
    assert len(checksums) == len(names) - 1
    for line in checksums:
        digest, _, name = line.partition("  ")
        assert digest == hashlib.sha256((out_dir / name).read_bytes()).hexdigest()

    for platform, wheel in zip(release.RELEASE_PLATFORMS, wheels, strict=True):
        zip_path = out_dir / f"{EXTENSION_ID}-{VERSION}-{platform.replace('-', '_')}.zip"
        with zipfile.ZipFile(zip_path) as archive:
            packaged = [n for n in archive.namelist() if n.startswith("wheels/")]
            assert packaged == [f"wheels/{wheel.name}"]
            assert archive.read(packaged[0]) == wheel.read_bytes()
            manifest = tomllib.loads(archive.read("blender_manifest.toml").decode("utf-8"))
        assert manifest["build"]["generated"]["platforms"] == [platform]

    text = notes.read_text(encoding="utf-8")
    for platform in release.RELEASE_PLATFORMS:
        assert f"{EXTENSION_ID}-{VERSION}-{platform.replace('-', '_')}.zip" in text

    # The release path never touches `make extension`'s outputs.
    assert snapshot() == before


def test_package_refuses_an_existing_out_dir(tmp_path: Path) -> None:
    blender = _require_blender()
    wheelhouse = tmp_path / "wheelhouse"
    standard_wheels(wheelhouse)
    out_dir = tmp_path / "release"
    notes = tmp_path / "notes.md"
    work_dir = tmp_path / "work"

    first = run_package(blender, wheelhouse, out_dir, notes, work_dir)
    assert first.returncode == 0, first.stderr
    second = run_package(blender, wheelhouse, out_dir, notes, work_dir)
    assert second.returncode == 1
    assert str(out_dir) in second.stderr


def test_package_checks_the_wheels_before_it_runs_blender(tmp_path: Path) -> None:
    blender = _require_blender()
    wheelhouse = tmp_path / "wheelhouse"
    wheels = standard_wheels(wheelhouse)
    macos = next(wheel for wheel in wheels if MACOS_TAGS in wheel.name)
    macos.unlink()
    out_dir = tmp_path / "release2"

    proc = run_package(blender, wheelhouse, out_dir, tmp_path / "notes.md", tmp_path / "work")
    assert proc.returncode == 1
    assert not out_dir.exists()
