#!/usr/bin/env python3
"""Build the Painterly Blender extension zips: `make extension` (T4.4) and a release (T8.1).

Two entry points share the functions below:

- ``main()`` is ``make extension``: get the painterly-core wheel (``--wheel PATH``, or else
  ``make wheel``), stage ``src/blender/addon/`` with that one wheel, let Blender write the zip into
  ``dist/``, print its path and write it to ``build/extension/zip_path.txt``.
- ``build_extension()`` is ``tools/release.py package``: stage one wheel per platform, let Blender
  write one zip per platform with ``--split-platforms``, and return their paths.

Staging, in both cases:

1. Empty the staging directory. Blender packs every file under the source directory that the
   manifest does not exclude into **every** zip (``blender_ext.py`` v5.2.2,
   ``subcmd_author.build``), so a wheel left by an earlier run would ship in all of them.
2. Copy the add-on directory (``__pycache__`` excepted, as the manifest excludes it).
3. Copy the licence texts: ``LICENSE`` and ``THIRD_PARTY_NOTICES.md``, and every file of
   ``LICENSES/``. The zip carries the add-on's own GPL licence, and the Apache-2.0 texts that
   ``get_panels()`` (copied from Cycles, T4.2) and the statically linked Embree require.
4. Copy each wheel to ``<staging>/wheels/``.
5. Rewrite the staged ``blender_manifest.toml``: ``platforms = [...]`` and ``wheels = [...]``. Both
   depend on the wheels that were built, so the source manifest writes neither. They are top-level
   TOML keys, so they go before the first table header.

Blender then writes ``<id>-<version>-<platform with "-" -> "_">.zip`` per platform under
``--split-platforms`` (``blender_ext.py``, the ``split_platforms`` branch of
``subcmd_author.build``).

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
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

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
# The two top-level notices of the repository. Every regular file of LICENSES/ is staged as well
# (the SPDX spelling); only these constant names keep the British "LICENCE" spelling.
LICENCE_FILES: tuple[str, ...] = ("LICENSE", "THIRD_PARTY_NOTICES.md")
LICENCE_DIR = "LICENSES"
# The wheel's distribution name (pyproject.toml [project] name = "painterly-core"), as the wheel
# filename spells it (PEP 427/491: runs of "-" and "_" are normalised to "_").
WHEEL_DISTRIBUTION = "painterly_core"
# The program `make wheel` runs (Makefile: `uv build --wheel --out-dir dist/`), and the build
# backend `pyproject.toml` names. Without `uv` the backend builds the same wheel in-process.
WHEEL_TOOL = "uv"
WHEEL_BACKEND_MODULE = "scikit_build_core.build"
WHEEL_BACKEND_FUNCTION = "build_wheel"
# PEP 427: `{distribution}-{version}(-{build tag})?-{python tag}-{abi tag}-{platform tag}.whl`, so
# a name without a build tag has five dash-separated fields and one with it has six.
WHEEL_SUFFIX = ".whl"
WHEEL_FIELDS_WITHOUT_BUILD = 5
WHEEL_FIELDS_WITH_BUILD = 6

# Blender platform of each element of a PEP 425 platform tag set. Blender's own, wider rule is
# blender_platforms_from_wheel_platform() in scripts/addons_core/bl_pkg/cli/blender_ext.py (v5.2.2).
# This table admits only the three v1 platforms (docs/plan.md, Owner decisions: Platforms) and the
# tags our wheels carry: linux_x86_64 from a local `uv build` (T2.4), manylinux_X_Y_x86_64 and the
# PEP 600 legacy aliases from auditwheel, macosx_X_Y_arm64 (T2.4: deployment target 11.0) and
# win_amd64.
WHEEL_PLATFORM_TAGS = (
    (
        re.compile(r"linux_x86_64|manylinux_[0-9]+_[0-9]+_x86_64|manylinux(?:1|2010|2014)_x86_64"),
        "linux-x64",
    ),
    (re.compile(r"macosx_[0-9]+_[0-9]+_arm64"), "macos-arm64"),
    (re.compile(r"win_amd64"), "windows-x64"),
)


class WheelName(NamedTuple):
    """The fields of a wheel filename, PEP 427."""

    distribution: str
    version: str
    build: str | None
    python: str
    abi: str
    platform: str  # the whole tag set, e.g. "manylinux_2_27_x86_64.manylinux_2_28_x86_64"


class BuildError(RuntimeError):
    """A step of the build failed; the message says which one and why."""


def _log(message: str) -> None:
    """Report progress on stderr, so stdout carries only the zip paths."""
    print(message, file=sys.stderr, flush=True)


def parse_wheel_filename(name: str) -> WheelName:
    """Split a wheel filename into its PEP 427 fields.

    Args:
        name: the wheel's file name, ``.whl`` included.

    Returns:
        Its fields; ``build`` is ``None`` when the name has no build tag.

    Raises:
        ValueError: if ``name`` does not end in ``.whl``, or has neither five nor six dash-separated
            fields.
    """
    if not name.endswith(WHEEL_SUFFIX):
        raise ValueError(f"{name} is not a wheel filename (it does not end in {WHEEL_SUFFIX})")
    fields = name.removesuffix(WHEEL_SUFFIX).split("-")
    if len(fields) == WHEEL_FIELDS_WITHOUT_BUILD:
        distribution, version, python, abi, platform = fields
        build = None
    elif len(fields) == WHEEL_FIELDS_WITH_BUILD:
        distribution, version, build, python, abi, platform = fields
    else:
        raise ValueError(
            f"{name} is not a wheel filename: expected "
            f"{WHEEL_FIELDS_WITHOUT_BUILD} or {WHEEL_FIELDS_WITH_BUILD} dash-separated fields, "
            f"found {len(fields)}"
        )
    return WheelName(distribution, version, build, python, abi, platform)


def blender_platform_from_wheel(wheel: Path) -> str:
    """The Blender platform of a wheel, e.g. ``linux-x64``.

    Args:
        wheel: the wheel file; its name is read as PEP 427.

    Returns:
        The Blender platform of its platform tag set, from ``WHEEL_PLATFORM_TAGS``.

    Raises:
        ValueError: if an element of the tag set matches no row of the table, or the elements name
            different platforms.
    """
    parsed = parse_wheel_filename(wheel.name)
    platforms = set()
    for element in parsed.platform.split("."):
        matched = [
            platform for pattern, platform in WHEEL_PLATFORM_TAGS if pattern.fullmatch(element)
        ]
        if len(matched) != 1:
            raise ValueError(
                f"{wheel.name}: the platform tag element {element!r} is none of the platforms this "
                "tool knows (see WHEEL_PLATFORM_TAGS)"
            )
        platforms.add(matched[0])
    if len(platforms) != 1:
        raise ValueError(
            f"{wheel.name}: the platform tag {parsed.platform!r} names several platforms "
            f"({sorted(platforms)}), but a wheel serves one"
        )
    return platforms.pop()


def extension_zip_name(extension_id: str, version: str, platform: str) -> str:
    """The zip name of one platform, as Blender's ``--split-platforms`` writes it.

    ``blender_ext.py`` v5.2.2, ``subcmd_author.build``: ``<id>-<version>-<platform>.zip`` with
    "-" in the platform replaced by "_".
    """
    return f"{extension_id}-{version}-{platform.replace('-', '_')}.zip"


def _is_key(line: str, keys: tuple[str, ...]) -> bool:
    """Whether ``line`` assigns one of the top-level ``keys`` of the TOML manifest."""
    text = line.split("#", 1)[0].strip()
    return any(text.startswith(f"{key} ") or text.startswith(f"{key}=") for key in keys)


def _write_manifest_platforms(
    manifest: Path, platforms: Sequence[str], wheel_names: Sequence[str]
) -> dict[str, object]:
    """Write ``platforms`` and ``wheels`` into the staged manifest and check the result.

    The two keys are top-level TOML keys, so they go before the first table header (the source
    manifest's ``[build]``); appending them at the end of the file would put them inside that
    table. ``json.dumps`` of a list of ASCII strings is a valid TOML array. The rewritten file is
    parsed again, and the two keys must be where they belong.

    Args:
        manifest: the staged ``blender_manifest.toml``.
        platforms: the Blender platforms, in the order the wheels are listed.
        wheel_names: the wheel file names inside ``<staging>/wheels/``, same order.

    Returns:
        The parsed manifest, for the id and the version.

    Raises:
        ValueError: if the source manifest already sets ``platforms`` or ``wheels`` (a duplicate
            TOML key), or the rewrite does not land at the top level.
    """
    lines = manifest.read_text(encoding="utf-8").splitlines()
    for key in ("platforms", "wheels"):
        if any(_is_key(line, (key,)) for line in lines):
            raise ValueError(
                f"{manifest}: the source manifest already sets {key}; tools/build_extension.py "
                "writes it from the wheels that were built"
            )
    first_table = next(
        (index for index, line in enumerate(lines) if line.lstrip().startswith("[")), len(lines)
    )
    written = [
        f"platforms = {json.dumps(list(platforms))}",
        f"wheels = {json.dumps([f'./{WHEEL_DIR_NAME}/{name}' for name in wheel_names])}",
        "",
    ]
    text = "\n".join([*lines[:first_table], *written, *lines[first_table:]]) + "\n"
    manifest.write_text(text, encoding="utf-8")

    parsed = tomllib.loads(text)
    expected_wheels = [f"./{WHEEL_DIR_NAME}/{name}" for name in wheel_names]
    if parsed.get("wheels") != expected_wheels or parsed.get("platforms") != list(platforms):
        raise BuildError(
            f"{manifest}: the rewrite did not land at the top level (wheels "
            f"{parsed.get('wheels')!r}, platforms {parsed.get('platforms')!r})"
        )
    return parsed


def _stage_licence(source: Path, staged: Path) -> None:
    """Copy one licence text to ``staged``, never over an add-on file.

    Raises:
        FileExistsError: if the add-on copy already put a file at ``staged``.
    """
    if staged.exists():
        raise FileExistsError(
            f"{staged} already exists; the licence text {source} never overwrites an add-on file"
        )
    staged.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, staged)


def stage_extension(
    wheels: Sequence[Path],
    staging_dir: Path,
    *,
    addon_dir: Path = ADDON_DIR,
    root: Path = REPO_ROOT,
) -> list[str]:
    """Stage the add-on, the licence texts and one wheel per platform into ``staging_dir``.

    The staging directory is emptied first: Blender packs every file under the source directory
    that the manifest does not exclude into every zip (fact 3 of T8.1), so a stale wheel would ship
    in all of them.

    Args:
        wheels: the wheels to bundle, one per platform, in any order.
        staging_dir: the directory to stage into; it is replaced.
        addon_dir: the add-on package, ``src/blender/addon/`` by default.
        root: the repository root that holds ``LICENSE``, ``THIRD_PARTY_NOTICES.md`` and
            ``LICENSES/``.

    Returns:
        The platforms, sorted. The wheels are listed in that same order.

    Raises:
        ValueError: for no wheel, for two wheels of one platform, or for a wheel whose name is not
            a supported wheel name.
        FileExistsError: if a licence text would overwrite an add-on file.
    """
    if not wheels:
        raise ValueError("no wheel to stage: the extension needs one wheel per platform")
    by_platform: dict[str, Path] = {}
    for wheel in wheels:
        platform = blender_platform_from_wheel(wheel)
        if platform in by_platform:
            raise ValueError(
                f"{by_platform[platform].name} and {wheel.name} are both wheels for {platform}"
            )
        by_platform[platform] = wheel
    platforms = sorted(by_platform)

    if staging_dir.exists():
        shutil.rmtree(staging_dir)
    shutil.copytree(addon_dir, staging_dir, ignore=shutil.ignore_patterns("__pycache__"))

    for name in LICENCE_FILES:
        _stage_licence(root / name, staging_dir / name)
    licence_dir = root / LICENCE_DIR
    for licence in sorted(entry for entry in licence_dir.iterdir() if entry.is_file()):
        _stage_licence(licence, staging_dir / LICENCE_DIR / licence.name)

    wheels_dir = staging_dir / WHEEL_DIR_NAME
    wheels_dir.mkdir()
    for platform in platforms:
        wheel = by_platform[platform]
        shutil.copyfile(wheel, wheels_dir / wheel.name)

    _write_manifest_platforms(
        staging_dir / MANIFEST_NAME, platforms, [by_platform[p].name for p in platforms]
    )
    return platforms


def build_extension(
    blender: Path,
    wheels: Sequence[Path],
    staging_dir: Path,
    output_dir: Path,
    *,
    addon_dir: Path = ADDON_DIR,
    root: Path = REPO_ROOT,
) -> list[Path]:
    """Stage the extension, build one zip per platform, and return their paths.

    Blender's progress lines go to stderr, so the stdout of ``tools/release.py package`` carries
    only asset paths. Blender prints ``created: "<path>"`` for the last zip only, so the paths are
    derived from the staged manifest instead of parsed.

    Args:
        blender: the Blender executable.
        wheels: the wheels to bundle, one per platform, in any order.
        staging_dir: the directory to stage into; it is replaced.
        output_dir: where Blender writes the zips; it is created if missing.
        addon_dir: the add-on package, ``src/blender/addon/`` by default.
        root: the repository root of the licence texts.

    Returns:
        The zips, in platform order.

    Raises:
        ValueError: see ``stage_extension``.
        FileNotFoundError: if Blender wrote no zip for one of the platforms.
    """
    platforms = stage_extension(wheels, staging_dir, addon_dir=addon_dir, root=root)
    output_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            str(blender),
            "--command",
            "extension",
            "build",
            "--source-dir",
            str(staging_dir),
            "--output-dir",
            str(output_dir),
            "--split-platforms",
        ],
        check=True,
        stdout=sys.stderr,
    )
    manifest = tomllib.loads((staging_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    zips = [
        output_dir / extension_zip_name(str(manifest["id"]), str(manifest["version"]), platform)
        for platform in platforms
    ]
    missing = [zip_path for zip_path in zips if not zip_path.is_file()]
    if missing:
        raise FileNotFoundError(
            "`blender --command extension build` wrote no "
            + ", ".join(zip_path.name for zip_path in missing)
        )
    return zips


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
        zip_paths = build_extension(blender, [wheel], STAGE_DIR, DIST_DIR)
    except (BuildError, ValueError, FileNotFoundError, subprocess.CalledProcessError) as error:
        print(f"build_extension: {error}", file=sys.stderr)
        return 1

    zip_path = zip_paths[0]
    ZIP_PATH_FILE.parent.mkdir(parents=True, exist_ok=True)
    ZIP_PATH_FILE.write_text(f"{zip_path}\n", encoding="utf-8")
    _log(f"build_extension: {zip_path} ({zip_path.stat().st_size} bytes)")
    print(zip_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
