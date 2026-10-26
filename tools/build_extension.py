#!/usr/bin/env python3
"""Build the Painterly Blender extension zip (card T4.4).

Steps, each one a function below:

1. Get the painterly-core wheel: `--wheel PATH`, or else `make wheel` (Makefile), which leaves it in
   ``dist/``. The wheel bundles ``_painterly``, so the extension ships the native module.
2. Stage ``src/blender/addon/`` into ``build/extension/painterly/`` and the wheel into
   ``build/extension/painterly/wheels/``. ``build/`` is git-ignored.
3. Rewrite the staged ``blender_manifest.toml``: ``wheels = ["./wheels/<wheel>"]`` and
   ``platforms = [<platform of the wheel's platform tag>]``. The source manifest writes neither,
   because both depend on the wheel that is built.
4. ``<blender> --command extension build --source-dir build/extension/painterly --output-dir dist/
   --split-platforms``. ``--split-platforms`` names the zip after the one platform the wheel is for:
   ``dist/<id>-<version>-<platform with underscores>.zip``.
5. Print the zip path (stdout, alone on its line) and write it, alone on one line, to
   ``build/extension/zip_path.txt``, where ``tests/blender_it`` reads it.

The wheel step is `make wheel`, which runs `uv build --wheel` (BACKLOG, R1: host-only, because this
host has no `uv`). So that the acceptance can still run here, the fallback when `uv` is not on
`PATH` is the build backend `pyproject.toml` names, scikit-build-core, called in-process exactly as
`uv build` would call it: same backend, same options, same ``dist/`` output. It is the project's
own backend, not a substitute build. When neither can run (no ``uv`` and no scikit-build-core), the
script says so, removes a stale ``zip_path.txt`` and exits 0, so that ``make blender-it`` skips its
integration test instead of failing on a tool the host does not have. A ``make wheel`` that fails
with ``uv`` present is a real error and fails this script.

Usage: build_extension.py --blender PATH [--wheel PATH]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# The add-on package that becomes the extension (the manifest's `id` names it "painterly").
ADDON_DIR = REPO_ROOT / "src" / "blender" / "addon"
MANIFEST_NAME = "blender_manifest.toml"
# The staging root of the card: build/ is git-ignored, and tests/blender_it reads zip_path.txt here.
STAGE_ROOT = REPO_ROOT / "build" / "extension"
STAGE_DIR = STAGE_ROOT / "painterly"
ZIP_PATH_FILE = STAGE_ROOT / "zip_path.txt"
# Where the wheel and the zip are written: `make wheel` builds into dist/, and so does step 4.
DIST_DIR = REPO_ROOT / "dist"
WHEEL_DIR_NAME = "wheels"
# The wheel's distribution name (pyproject.toml [project] name = "painterly-core"), as the wheel
# filename spells it (PEP 427/491: runs of "-" and "_" are normalised to "_").
WHEEL_DISTRIBUTION = "painterly_core"
# The program `make wheel` runs (Makefile: `uv build --wheel --out-dir dist/`), and the build
# backend `pyproject.toml` names. Without `uv` the backend builds the same wheel in-process.
WHEEL_TOOL = "uv"
WHEEL_BACKEND_MODULE = "scikit_build_core.build"
WHEEL_BACKEND_FUNCTION = "build_wheel"

# Blender's own wheel-platform -> extension-platform rule, copied from
# blender-5.2.2/5.2/scripts/addons_core/bl_pkg/cli/blender_ext.py, functions
# `blender_platforms_from_wheel_platform`, `platform_system_replace_for_wheels` and
# `platform_machine_replace`: "manylinux_2_28_x86_64" -> "linux-x64", "win_amd64" -> "windows-x64",
# "macosx_11_0_arm64" -> "macos-arm64". The manifest must carry the name Blender itself derives,
# because `--split-platforms` filters the bundled wheels by it.
WHEEL_PLATFORM_SYSTEM = {
    "macosx": "macos",
    "manylinux": "linux",
    "musllinux": "linux",
    "win": "windows",
}
WHEEL_PLATFORM_MACHINE = {
    "x86_64": "x64",
    "amd64": "x64",
    "aarch64": "arm64",
    "aarch32": "arm32",
}
# A wheel for "any" platform bundles no native module, and a macOS universal2 wheel is for two
# platforms; the card's manifest carries exactly one platform, so neither can be staged.
WHEEL_PLATFORM_ANY = "any"
WHEEL_PLATFORM_UNIVERSAL2 = "universal2"


class BuildError(RuntimeError):
    """A step of the build failed; the message says which one and why."""


def _log(message: str) -> None:
    """Report progress on stderr, so stdout carries only the zip path."""
    print(message, file=sys.stderr, flush=True)


def extension_platform(wheel: Path) -> str:
    """The Blender platform of a wheel, e.g. ``linux-x64``.

    Args:
        wheel: the wheel file; its name is read as PEP 427
            ``{distribution}-{version}(-{build})?-{python}-{abi}-{platform}.whl``.

    Returns:
        Blender's platform name for the wheel's platform tag, as
        ``blender_platforms_from_wheel_platform`` derives it.
    """
    parts = wheel.name.removesuffix(".whl").split("-")
    if len(parts) < 5:
        raise BuildError(f"{wheel.name} is not a wheel filename (expected at least 5 fields)")
    platform_tag = parts[-1]
    if platform_tag == WHEEL_PLATFORM_ANY:
        raise BuildError(
            f"{wheel.name} is a pure-Python wheel; the extension needs the platform tag"
        )
    head, _, tail = platform_tag.partition("_")
    if not tail:
        raise BuildError(f"{wheel.name}: the platform tag {platform_tag!r} has no machine part")
    system = head
    for wheel_system, blender_system in WHEEL_PLATFORM_SYSTEM.items():
        # "manylinux2014" -> "linux", as Blender's own loop does for a numbered system prefix.
        numbered = head.startswith(wheel_system) and head[len(wheel_system) :].isdigit()
        if head == wheel_system or numbered:
            system = blender_system
            break
    # The machine is the tag's known machine suffix, so a GLIBC or macOS version in front of it is
    # dropped ("2_28_x86_64" -> "x64"); an unknown tag keeps its last component.
    machine = tail.rpartition("_")[2]
    for wheel_machine, blender_machine in WHEEL_PLATFORM_MACHINE.items():
        if tail == wheel_machine or tail.endswith(f"_{wheel_machine}"):
            machine = blender_machine
            break
    if machine == WHEEL_PLATFORM_UNIVERSAL2:
        raise BuildError(
            f"{wheel.name} is a universal2 wheel: it serves macos-x64 and macos-arm64, but the "
            "extension manifest carries one platform"
        )
    return f"{system}-{machine}"


def _is_key(line: str, keys: tuple[str, ...]) -> bool:
    """Whether ``line`` assigns one of the top-level ``keys`` of the TOML manifest."""
    text = line.split("#", 1)[0].strip()
    return any(text.startswith(f"{key} ") or text.startswith(f"{key}=") for key in keys)


def rewrite_manifest(stage: Path, wheel_name: str, platform: str) -> dict[str, object]:
    """Write ``wheels`` and ``platforms`` into the staged manifest and check the result.

    The two keys are top-level TOML keys, so they go before the first table header (the source
    manifest's ``[build]``); appending them at the end of the file would put them inside that
    table. The rewritten file is parsed again, and the two keys must be where they belong.

    Args:
        stage: the staging directory that holds the copied manifest.
        wheel_name: the wheel's filename inside ``<stage>/wheels/``.
        platform: the Blender platform of that wheel, e.g. ``linux-x64``.

    Returns:
        The parsed manifest, for the id, the version and the zip name.
    """
    manifest = stage / MANIFEST_NAME
    lines = manifest.read_text(encoding="utf-8").splitlines()
    kept = [line for line in lines if not _is_key(line, ("wheels", "platforms"))]
    first_table = next(
        (index for index, line in enumerate(kept) if line.lstrip().startswith("[")), len(kept)
    )
    written = [
        "# Written by tools/build_extension.py (T4.4) from the wheel that was built.",
        f"wheels = [{json.dumps(f'./{WHEEL_DIR_NAME}/{wheel_name}')}]",
        f"platforms = [{json.dumps(platform)}]",
        "",
    ]
    text = "\n".join([*kept[:first_table], *written, *kept[first_table:]]) + "\n"
    manifest.write_text(text, encoding="utf-8")

    parsed = tomllib.loads(text)
    expected_wheels = [f"./{WHEEL_DIR_NAME}/{wheel_name}"]
    if parsed.get("wheels") != expected_wheels or parsed.get("platforms") != [platform]:
        raise BuildError(
            f"{manifest}: the rewrite did not land at the top level (wheels "
            f"{parsed.get('wheels')!r}, platforms {parsed.get('platforms')!r})"
        )
    return parsed


def _newest_wheel(directory: Path) -> Path:
    """The newest ``painterly_core`` wheel in ``directory``."""
    wheels = sorted(
        directory.glob(f"{WHEEL_DISTRIBUTION}-*.whl"), key=lambda path: path.stat().st_mtime
    )
    if not wheels:
        raise BuildError(f"{directory} holds no {WHEEL_DISTRIBUTION} wheel; run `make wheel`")
    return wheels[-1]


def _build_wheel_with_backend() -> bool:
    """Build the wheel with the project's own backend, as ``uv build`` would.

    ``pyproject.toml``'s ``[build-system]`` names scikit-build-core, so its ``build_wheel`` is
    exactly what ``uv build --wheel --out-dir dist/`` calls. Returns False when the backend is not
    importable, which leaves the caller to report the host-only case.
    """
    if importlib.util.find_spec(WHEEL_BACKEND_MODULE) is None:
        return False
    backend = importlib.import_module(WHEEL_BACKEND_MODULE)
    _log(f"build_extension: building the wheel with {WHEEL_BACKEND_MODULE}")
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    # build_wheel takes the output directory relative to the working directory, as `uv build`'s
    # --out-dir does; the chdir keeps that the repo root.
    previous = Path.cwd()
    os.chdir(REPO_ROOT)
    try:
        getattr(backend, WHEEL_BACKEND_FUNCTION)(str(DIST_DIR))
    finally:
        os.chdir(previous)
    return True


def build_wheel(explicit: Path | None) -> Path | None:
    """The wheel to bundle: ``explicit``, or the one ``make wheel`` builds.

    Returns:
        The wheel, or ``None`` when neither ``uv`` nor the project's build backend can run: the
        host-only case of the module docstring.
    """
    if explicit is not None:
        if not explicit.is_file():
            raise BuildError(f"--wheel {explicit} does not exist")
        return explicit
    if shutil.which(WHEEL_TOOL) is not None:
        _log("build_extension: running `make wheel`")
        proc = subprocess.run(["make", "wheel"], cwd=REPO_ROOT, capture_output=True, text=True)
        if proc.returncode != 0:
            raise BuildError(
                f"`make wheel` exited with status {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
            )
        return _newest_wheel(DIST_DIR)
    if not _build_wheel_with_backend():
        _log(
            f"build_extension: neither {WHEEL_TOOL} nor {WHEEL_BACKEND_MODULE} is available, so no "
            "painterly-core wheel can be built. This is a host-only step (BACKLOG, R1): no zip is "
            "written, and tests/blender_it skips."
        )
        ZIP_PATH_FILE.unlink(missing_ok=True)
        return None
    return _newest_wheel(DIST_DIR)


def stage(wheel: Path) -> Path:
    """Copy the add-on and the wheel into ``STAGE_DIR``; return the staging directory.

    ``__pycache__`` directories are not copied: the manifest excludes them from the zip anyway.
    """
    if STAGE_ROOT.exists():
        shutil.rmtree(STAGE_ROOT)
    shutil.copytree(ADDON_DIR, STAGE_DIR, ignore=shutil.ignore_patterns("__pycache__"))
    wheels = STAGE_DIR / WHEEL_DIR_NAME
    wheels.mkdir()
    shutil.copy2(wheel, wheels / wheel.name)
    return STAGE_DIR


def run_blender_build(blender: Path, stage_dir: Path, manifest: dict[str, object]) -> Path:
    """Run ``blender --command extension build --split-platforms`` and return the zip it wrote.

    With ``--split-platforms`` Blender names the zip ``<id>-<version>-<platform>.zip``, with "-"
    in the platform replaced by "_" (``blender_ext.py``, the ``split_platforms`` branch of the
    package build).
    """
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    platform = str(manifest["platforms"][0])  # type: ignore[index]
    expected = DIST_DIR / f"{manifest['id']}-{manifest['version']}-{platform.replace('-', '_')}.zip"
    cmd = [
        str(blender),
        "--command",
        "extension",
        "build",
        "--source-dir",
        str(stage_dir),
        "--output-dir",
        str(DIST_DIR),
        "--split-platforms",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise BuildError(
            f"{' '.join(cmd)} exited with status {proc.returncode}\n{proc.stdout}\n{proc.stderr}"
        )
    if not expected.is_file():
        raise BuildError(
            f"`blender --command extension build` wrote no {expected.name}\n{proc.stdout}"
        )
    return expected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--blender", required=True, type=Path, help="the Blender 5.2 executable (`make blender`)"
    )
    parser.add_argument(
        "--wheel", type=Path, default=None, help="bundle this wheel instead of running `make wheel`"
    )
    args = parser.parse_args(argv)

    blender: Path = args.blender
    if not blender.is_file():
        print(
            f"build_extension: --blender {blender} does not exist; `make blender` fetches Blender "
            "5.2.2 into .cache/blender/",
            file=sys.stderr,
        )
        return 2

    try:
        wheel = build_wheel(args.wheel)
        if wheel is None:
            return 0
        stage_dir = stage(wheel)
        manifest = rewrite_manifest(stage_dir, wheel.name, extension_platform(wheel))
        zip_path = run_blender_build(blender, stage_dir, manifest)
    except BuildError as error:
        print(f"build_extension: {error}", file=sys.stderr)
        return 1

    ZIP_PATH_FILE.parent.mkdir(parents=True, exist_ok=True)
    ZIP_PATH_FILE.write_text(f"{zip_path}\n", encoding="utf-8")
    _log(f"build_extension: {zip_path} ({zip_path.stat().st_size} bytes)")
    print(zip_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
