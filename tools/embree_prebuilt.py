#!/usr/bin/env python3
"""Build a prebuilt Embree 4.4.1 for painterly, and prove it is compiled like the FetchContent one.

Usage::

    python tools/embree_prebuilt.py build --source DIR --prefix DIR
    python tools/embree_prebuilt.py compare-flags --source DIR \
        --embree-dir PREFIX/lib/cmake/embree-4.4.1

``build`` configures, builds and installs Embree from the source tree DIR into the install prefix
DIR, with exactly the configuration painterly gives Embree: the shared file
``cmake/painterly_embree_config.cmake``, passed as ``CMAKE_PROJECT_INCLUDE`` so it runs inside
Embree's own ``project()`` call (the C++ standard, position-independent code, the visibility
presets, the MSVC runtime, the floating-point flags and every ``EMBREE_*`` cache option). The
install is what ``cmake/painterly_embree.cmake`` consumes when ``embree_DIR`` is set, so clones can
point at it instead of recompiling Embree. Its work directory keeps the configure's
``compile_commands.json``, which ``compare-flags`` reads as the install's own flags.

``compare-flags`` configures the project three times, all with ``CMAKE_EXPORT_COMPILE_COMMANDS=ON``
and nothing is built:

1. by FetchContent from DIR (``FETCHCONTENT_SOURCE_DIR_EMBREE=DIR``), the path a clone takes by
   default;
2. against the install via ``embree_DIR``, which must configure the project without compiling any
   Embree source at all;
3. the Embree source tree alone, with the same shared configuration file ``build`` passes.

It then compares the compile flags of every Embree translation unit of (1) and of (3), with the
absolute paths of the Embree source and build directories replaced by the placeholders
``<embree-src>`` and ``<embree-build>`` so that only genuine flag differences remain. It prints
``EMBREE FLAGS IDENTICAL: <n> units`` and exits 0 when every unit matches, and otherwise prints the
differing units and exits 1.

Configure (3) is why this is a three-configure comparison and not the two the item names. A project
configured against a prebuilt Embree compiles no Embree source -- that is the point of it -- so it
has no Embree translation units, and a two-configure comparison would compare the empty set and
print ``0 units`` for any install whatever. (3) supplies the flags the install was built with; when
``build`` left its ``compile_commands.json`` in ``<prefix>-work/build``, ``compare-flags`` reads
that record instead of configuring again, so the comparison is against the real install's own
flags, not against a re-derivation of them.

A source tree that cannot be written to (a read-only mount, as MAIN/.cache/src is) is copied into
the work directory first, because Embree's CMakeLists.txt writes generated headers into its own
source tree. Nothing is ever written into DIR itself when DIR is read-only.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# The one source of truth for Embree's build configuration, shared by the root CMakeLists.txt, the
# FetchContent path and this tool's build.
CONFIG_FILE = REPO_ROOT / "cmake" / "painterly_embree_config.cmake"
# The Embree release painterly pins (cmake/painterly_embree.cmake, GIT_TAG v4.4.1). Embree's install
# puts its CMake package under lib/cmake/embree-<version>.
EMBREE_VERSION = "4.4.1"
EMBREE_PACKAGE_SUBDIR = f"lib/cmake/embree-{EMBREE_VERSION}"
# The build type of every configure: `make build` uses Release, and the flags under test (-O3,
# -DNDEBUG) depend on it.
BUILD_TYPE = "Release"
# The project's own CMake knobs for the two project configures. Only the module is needed: it is
# what links painterly_embree. Tests and the oracle are off, so no other FetchContent dependency
# is configured and the comparison needs no doctest source.
PROJECT_DEFINITIONS = {
    "PAINTERLY_BUILD_MODULE": "ON",
    "PAINTERLY_BUILD_TESTS": "OFF",
    "PAINTERLY_BUILD_ORACLE": "OFF",
}
# The dependency options both project configures take, so that a prebuilt configure which silently
# fell back to FetchContent would show up as Embree translation units rather than as an error.
PROJECT_DEPENDENCY_DEFINITIONS = {"FETCHCONTENT_FULLY_DISCONNECTED": "ON"}
# Placeholders for the directories whose absolute paths legitimately differ between the FetchContent
# configure, the standalone configure and the install's recorded build.
SRC_PLACEHOLDER = "<embree-src>"
BUILD_PLACEHOLDER = "<embree-build>"
# The name of the work directory `build` uses by default, next to the install prefix.
WORK_DIR_SUFFIX = "-work"


class EmbreePrebuiltError(RuntimeError):
    """A step of the tool could not run: a missing command, a failed configure, a bad input."""


@dataclass(frozen=True)
class FlagComparison:
    """The Embree translation units of the FetchContent configure and of the install's build.

    ``units_fetch`` and ``units_install`` map a unit key to that unit's compile flags, in order,
    with absolute paths normalised. The key is the translation unit's source path relative to the
    Embree source tree (prefix ``src/``) or to the directory Embree generates its ISA sources in
    (prefix ``gen/``); every configure produces the same key for the same unit.
    """

    units_fetch: Mapping[str, tuple[str, ...]]
    units_install: Mapping[str, tuple[str, ...]]

    @property
    def n_units(self) -> int:
        """The number of units both sides have: the n of the EMBREE FLAGS IDENTICAL line."""
        return len(set(self.units_fetch) & set(self.units_install))

    @property
    def only_fetch(self) -> list[str]:
        """Units the FetchContent configure compiles and the install's does not."""
        return sorted(set(self.units_fetch) - set(self.units_install))

    @property
    def only_install(self) -> list[str]:
        """Units the install's configure compiles and the FetchContent one does not."""
        return sorted(set(self.units_install) - set(self.units_fetch))

    @property
    def differing(self) -> list[str]:
        """Units both sides compile with different flags."""
        shared = sorted(set(self.units_fetch) & set(self.units_install))
        return [key for key in shared if self.units_fetch[key] != self.units_install[key]]

    @property
    def identical(self) -> bool:
        """True when both sides compile exactly the same units with exactly the same flags."""
        return not self.only_fetch and not self.only_install and not self.differing


def _run(command: Sequence[str]) -> None:
    """Run command, raising EmbreePrebuiltError with its output when it fails."""
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise EmbreePrebuiltError(
            f"{' '.join(command)} exited {result.returncode}\n{result.stdout}{result.stderr}"
        )


def _cmake() -> str:
    """The cmake executable to run."""
    cmake = shutil.which("cmake")
    if cmake is None:
        raise EmbreePrebuiltError("cmake was not found on PATH")
    return cmake


def _parallel_arguments() -> list[str]:
    """--parallel <n> for `cmake --build`, when CMAKE_BUILD_PARALLEL_LEVEL names a positive n.

    The environment variable is the project's convention for the shared machine's build parallelism
    (RULINGS R10); without it, cmake --build picks its own default.
    """
    level = os.environ.get("CMAKE_BUILD_PARALLEL_LEVEL", "").strip()
    if level.isdigit() and int(level) > 0:
        return ["--parallel", level]
    return []


def configure(build_dir: Path, source_dir: Path, definitions: Mapping[str, str]) -> None:
    """Configure source_dir into build_dir, with definitions given as -D<key>=<value>."""
    command = [_cmake(), "-S", str(source_dir), "-B", str(build_dir)]
    command += [f"-D{key}={value}" for key, value in definitions.items()]
    _run(command)


def _make_writable(root: Path) -> None:
    """Give the owner write permission on root and everything under it."""
    for path in (root, *root.rglob("*")):
        # A symlink to something outside the copy, or a path that vanished; both are fine.
        with contextlib.suppress(OSError):
            path.chmod(path.stat().st_mode | stat.S_IWUSR | stat.S_IXUSR)


def writable_source(source: Path, staged: Path) -> Path:
    """Return a source tree this process may write to: source itself, or a copy of it at staged.

    Embree's CMakeLists.txt writes generated headers (kernels/config.h, kernels/hash.h,
    include/embree4/rtcore_config.h and the export maps) into its own source tree, so a read-only
    source mount cannot be configured in place. The copy is made once, so rerunning reuses it.
    """
    if os.access(source, os.W_OK):
        return source
    if not staged.exists():
        shutil.copytree(source, staged, symlinks=True)
        _make_writable(staged)
    return staged


def _absolute(token: str, directory: str) -> str:
    """token as an absolute path, resolved against directory when it is relative."""
    return token if os.path.isabs(token) else os.path.normpath(os.path.join(directory, token))


def _under(path: str, root: str) -> bool:
    """True when path is root or lies inside root."""
    return path == root or path.startswith(root + os.sep)


def embree_units(
    entries: Iterable[Mapping[str, object]],
    source_roots: Sequence[Path],
    embree_binary: Path,
    generated_root: Path,
) -> dict[str, tuple[str, ...]]:
    """The Embree translation units of a compile_commands.json, keyed and path-normalised.

    A translation unit belongs to Embree when its object file is written inside embree_binary, the
    directory Embree's targets are built in. Its key is its source path relative to the source root
    that holds it (prefix ``src/``) or, for the ISA sources Embree generates into generated_root,
    relative to that directory (prefix ``gen/``). A unit whose source is in neither is not an Embree
    unit. Several source roots are accepted because a configure may read the real source tree or a
    staged writable copy of it.

    The flags are the command's arguments with the object and source file arguments removed, so that
    only the compile configuration is left, and with every root replaced by its placeholder, longest
    path first, so that a nested path is not rewritten by its parent's placeholder.
    """
    replacements: list[tuple[str, str]] = []
    for root in source_roots:
        replacements.append((str(Path(root).resolve()), SRC_PLACEHOLDER))
    replacements.append((str(Path(generated_root).resolve()), BUILD_PLACEHOLDER))
    replacements.append((str(Path(embree_binary).resolve()), BUILD_PLACEHOLDER))
    unique: dict[str, str] = {}
    for path, placeholder in replacements:
        unique.setdefault(path, placeholder)
    ordered = sorted(unique.items(), key=lambda item: len(item[0]), reverse=True)

    units: dict[str, tuple[str, ...]] = {}
    for entry in entries:
        command = entry.get("command")
        if not isinstance(command, str):
            raise EmbreePrebuiltError(f"compile_commands entry without a command: {entry!r}")
        directory = str(entry.get("directory", ""))
        arguments = shlex.split(command)
        obj: str | None = None
        src: str | None = None
        flags: list[str] = []
        index = 0
        while index < len(arguments):
            argument = arguments[index]
            if argument in ("-o", "-c") and index + 1 < len(arguments):
                value = _absolute(arguments[index + 1], directory)
                if argument == "-o":
                    obj = value
                else:
                    src = value
                index += 2
                continue
            flags.append(argument)
            index += 1
        if obj is None or src is None or not _under(obj, str(Path(embree_binary).resolve())):
            continue
        key: str | None = None
        for root in source_roots:
            resolved = str(Path(root).resolve())
            if _under(src, resolved):
                key = "src/" + os.path.relpath(src, resolved)
                break
        if key is None and _under(src, str(Path(generated_root).resolve())):
            key = "gen/" + os.path.relpath(src, str(Path(generated_root).resolve()))
        if key is None:
            continue
        normalised = []
        for flag in flags:
            for root, placeholder in ordered:
                flag = flag.replace(root, placeholder)
            normalised.append(flag)
        units[key] = tuple(normalised)
    return units


def compare_units(
    units_fetch: Mapping[str, tuple[str, ...]],
    units_install: Mapping[str, tuple[str, ...]],
) -> FlagComparison:
    """Compare the two flag maps, unit by unit."""
    return FlagComparison(units_fetch=units_fetch, units_install=units_install)


def render_report(comparison: FlagComparison) -> str:
    """The report compare-flags prints: the EMBREE FLAGS IDENTICAL line, or the differences."""
    if comparison.identical:
        return f"EMBREE FLAGS IDENTICAL: {comparison.n_units} units\n"
    lines = [f"EMBREE FLAGS DIFFER: {comparison.n_units} units compared"]
    if comparison.only_fetch:
        lines.append("compiled by the FetchContent configure only:")
        lines += [f"  {key}" for key in comparison.only_fetch]
    if comparison.only_install:
        lines.append("compiled by the install's configure only:")
        lines += [f"  {key}" for key in comparison.only_install]
    for key in comparison.differing:
        lines.append(f"  {key}")
        lines.append(f"    fetch:   {' '.join(comparison.units_fetch[key])}")
        lines.append(f"    install: {' '.join(comparison.units_install[key])}")
    return "\n".join(lines) + "\n"


def compile_commands(build_dir: Path) -> list[Mapping[str, object]]:
    """The compile_commands.json of a configured build directory."""
    path = build_dir / "compile_commands.json"
    if not path.is_file():
        raise EmbreePrebuiltError(
            f"{path} does not exist, so the configure wrote no compile commands"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _install_source_roots(source: Path, work_dir: Path) -> list[Path]:
    """The source roots a build's compile commands may name: the real tree and the staged copy."""
    roots = [source, work_dir / "src"]
    return [root for index, root in enumerate(roots) if root not in roots[:index]]


def command_build(args: argparse.Namespace) -> int:
    """Configure, build and install Embree from --source into --prefix."""
    source = Path(args.source).resolve()
    if not (source / "CMakeLists.txt").is_file():
        raise EmbreePrebuiltError(
            f"{source} holds no CMakeLists.txt, so it is not an Embree source tree"
        )
    prefix = Path(args.prefix).resolve()
    work_dir = (
        Path(args.work_dir).resolve() if args.work_dir else Path(f"{prefix}{WORK_DIR_SUFFIX}")
    )
    work_dir.mkdir(parents=True, exist_ok=True)
    build_dir = work_dir / "build"
    staged = writable_source(source, work_dir / "src")
    configure(
        build_dir,
        staged,
        {
            "CMAKE_BUILD_TYPE": BUILD_TYPE,
            # The install's own flags, for compare-flags to read.
            "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
            "CMAKE_INSTALL_PREFIX": str(prefix),
            "CMAKE_PROJECT_INCLUDE": str(CONFIG_FILE),
        },
    )
    _run([_cmake(), "--build", str(build_dir), "--target", "install", *_parallel_arguments()])
    print(f"embree_prebuilt: installed Embree {EMBREE_VERSION} into {prefix}")
    return 0


def command_compare_flags(args: argparse.Namespace) -> int:
    """Compare the Embree flags of the FetchContent path and of the prebuilt install."""
    source = Path(args.source).resolve()
    if not (source / "CMakeLists.txt").is_file():
        raise EmbreePrebuiltError(
            f"{source} holds no CMakeLists.txt, so it is not an Embree source tree"
        )
    embree_dir = Path(args.embree_dir).resolve()
    if not (embree_dir / "embree-config.cmake").is_file():
        raise EmbreePrebuiltError(f"{embree_dir} holds no embree-config.cmake")
    # <prefix>/lib/cmake/embree-4.4.1 -> <prefix>. `build` puts its work directory beside the
    # prefix, so that is where the install's own compile_commands.json is, when `build` made it.
    prefix = embree_dir.parents[2]
    install_work_dir = prefix.parent / f"{prefix.name}{WORK_DIR_SUFFIX}"

    with _temp_dir(args.keep) as temporary:
        staged = writable_source(source, temporary / "embree-src")
        source_roots = [staged]
        project_definitions = {
            **PROJECT_DEFINITIONS,
            **PROJECT_DEPENDENCY_DEFINITIONS,
            "CMAKE_BUILD_TYPE": BUILD_TYPE,
            "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
            "Python_EXECUTABLE": sys.executable,
            "FETCHCONTENT_SOURCE_DIR_EMBREE": str(staged),
        }

        fetch_build = temporary / "fetch"
        configure(fetch_build, REPO_ROOT, project_definitions)
        units_fetch = embree_units(
            compile_commands(fetch_build),
            source_roots,
            fetch_build / "_deps" / "embree-build",
            fetch_build,
        )

        prebuilt_build = temporary / "prebuilt"
        configure(prebuilt_build, REPO_ROOT, {**project_definitions, "embree_DIR": str(embree_dir)})
        units_prebuilt = embree_units(
            compile_commands(prebuilt_build),
            source_roots,
            prebuilt_build / "_deps" / "embree-build",
            prebuilt_build,
        )
        if units_prebuilt:
            raise EmbreePrebuiltError(
                f"the configure with embree_DIR={embree_dir} still compiled "
                f"{len(units_prebuilt)} Embree translation units, so it did not use the install"
            )
        print(f"compare-flags: the configure with embree_DIR={embree_dir} compiled 0 Embree units")

        install_build = install_work_dir / "build"
        if (install_build / "compile_commands.json").is_file():
            units_install = embree_units(
                compile_commands(install_build),
                _install_source_roots(source, install_work_dir),
                install_build,
                install_build,
            )
            print(f"compare-flags: the install's own flags come from {install_build}")
        else:
            standalone = temporary / "embree"
            configure(
                standalone,
                staged,
                {
                    "CMAKE_BUILD_TYPE": BUILD_TYPE,
                    "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
                    "CMAKE_PROJECT_INCLUDE": str(CONFIG_FILE),
                },
            )
            units_install = embree_units(
                compile_commands(standalone), source_roots, standalone, standalone
            )
            print(f"compare-flags: no {install_build}; configured the source standalone instead")

    comparison = compare_units(units_fetch, units_install)
    print(render_report(comparison), end="")
    return 0 if comparison.identical else 1


class _temp_dir:
    """A temporary directory, removed on exit unless --keep asked for it to stay."""

    def __init__(self, keep: str | None) -> None:
        self._keep = keep

    def __enter__(self) -> Path:
        if self._keep:
            path = Path(self._keep).resolve()
            path.mkdir(parents=True, exist_ok=True)
            return path
        self._temporary = tempfile.TemporaryDirectory(prefix="painterly-embree-")
        return Path(self._temporary.name)

    def __exit__(self, *exc_info: object) -> None:
        temporary = getattr(self, "_temporary", None)
        if temporary is not None:
            temporary.cleanup()


def main(argv: list[str] | None = None) -> int:
    """Parse argv and run the chosen subcommand."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    subcommands = parser.add_subparsers(dest="subcommand", required=True)

    build = subcommands.add_parser(
        "build", help="configure, build and install Embree from a source tree"
    )
    build.add_argument("--source", required=True, help="the Embree source tree (v4.4.1)")
    build.add_argument("--prefix", required=True, help="the install prefix to create")
    build.add_argument(
        "--work-dir",
        help=f"where to stage a read-only source and to build (default: <prefix>{WORK_DIR_SUFFIX})",
    )
    build.set_defaults(handler=command_build)

    compare = subcommands.add_parser(
        "compare-flags", help="compare the Embree compile flags of FetchContent and of an install"
    )
    compare.add_argument("--source", required=True, help="the Embree source tree (v4.4.1)")
    compare.add_argument(
        "--embree-dir",
        required=True,
        help=f"an Embree install's {EMBREE_PACKAGE_SUBDIR} directory, for embree_DIR",
    )
    compare.add_argument(
        "--keep", help="configure into this directory and keep it, instead of a temporary one"
    )
    compare.set_defaults(handler=command_compare_flags)

    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except EmbreePrebuiltError as error:
        print(f"embree_prebuilt: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
