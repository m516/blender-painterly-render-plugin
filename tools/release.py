#!/usr/bin/env python3
"""Build and verify the assets of a Painterly release, and decide what a tag means (card T8.1).

Usage::

    release.py plan (--tag TAG | --dispatch)
    release.py zip-name --platform {linux-x64,macos-arm64,windows-x64}
    release.py package --blender PATH --wheel-dir DIR
            [--out-dir dist/release] [--notes dist/release-notes.md] [--work-dir build/release]

The five assets of a release, written into ``--out-dir``:

- ``painterly-<version>-linux_x64.zip``, ``-macos_arm64.zip``, ``-windows_x64.zip``: one extension
  zip per platform, each with exactly that platform's wheel, built by Blender with
  ``--split-platforms`` (``tools/build_extension.py``);
- ``painterly-<version>-source.tar.gz``: ``git archive`` of the tagged commit, prefix
  ``painterly-<version>/``, so it holds every tracked file byte for byte;
- ``SHA256SUMS``: ``<64 lowercase hex>  <name>\\n`` per asset above, sorted by name.

Every check in this module is an exact equality, never a tolerance: a byte differs or it does not.
Standard library only, because the release workflow runs this tool under ``actions/setup-python``
without the project venv.

``plan`` prints exactly ``mode=<release|dry-run>\\nversion=<X.Y.Z>\\n``, the format of
``$GITHUB_OUTPUT``, and nothing when it fails (``release: <reason>`` on stderr, exit 1), so a
failing run leaves ``$GITHUB_OUTPUT`` untouched.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import re
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# The three version sources, in the order the error messages list them.
VERSION_SOURCES: tuple[str, ...] = (
    "src/blender/addon/blender_manifest.toml",
    "pyproject.toml",
    "CMakeLists.txt",
)
RELEASE_PLATFORMS: tuple[str, ...] = (
    "linux-x64",
    "macos-arm64",
    "windows-x64",
)
INSTALL_PLATFORMS: tuple[str, ...] = (
    "linux-x64",
    "windows-x64",
)
CHECKSUMS_NAME = "SHA256SUMS"
MANIFEST_NAME = "blender_manifest.toml"
ADDON_DIR = Path("src") / "blender" / "addon"
LICENCE_FILES: tuple[str, ...] = ("LICENSE", "THIRD_PARTY_NOTICES.md")
LICENCE_DIR = "LICENSES"
# The source tarball's prefix is `<id>-<version>/`; the extension id comes from the manifest.
SOURCE_TARBALL_SUFFIX = "-source.tar.gz"
WHEELS_DIR = "wheels"

# The tag forms of a release and of a dry run (this card). [0-9], not \d: \d also matches non-ASCII
# digits.
RELEASE_TAG = re.compile(r"v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)")
DRY_RUN_TAG = re.compile(r"v(?P<version>[0-9]+\.[0-9]+\.[0-9]+)-dryrun\.[0-9]+")
# CMakeLists.txt's project() line; its VERSION becomes _painterly.version_info()["version"]
# (src/blender/CMakeLists.txt). The lookahead ends the match after X.Y.Z: a four-component
# VERSION is no match, so it raises instead of reading 0.1.0 out of 0.1.0.1, which
# PAINTERLY_VERSION would then carry and engine.init() would refuse (T4.1).
CMAKE_PROJECT_VERSION = re.compile(
    r"^project\(painterly VERSION ([0-9]+\.[0-9]+\.[0-9]+)(?=[\s)])", re.MULTILINE
)
# scikit-build-core's wheel.py-api = "cpXY" builds a stable-ABI wheel, whose ABI tag is abi3
# (PEP 384, PEP 425).
STABLE_ABI_TAG = "abi3"
# PEP 427's wheel-name normalization: runs of "-", "_" and "." become "_", and the name is
# lowercased.
WHEEL_NAME_SEPARATORS = re.compile(r"[-_.]+")
# A release ships only auditwheel-repaired manylinux wheels; the glibc baseline that T2.9 enforces.
UNREPAIRED_LINUX_TAG_PREFIX = "linux_"
# The member paths of a source tarball carry the archive prefix; tarfile names a directory member
# without the trailing "/".
PAX_COMMENT = "comment"


class ReleaseError(Exception):
    """A precondition or a verification failed; the message names what and where."""


def _load_build_extension() -> object:
    """Import ``tools/build_extension.py`` by path.

    Under ``python -I`` (and under ``-P``) the script's directory is not on ``sys.path``, so the
    sibling tool is loaded by file path, as the tests load these tools.
    """
    path = Path(__file__).resolve().parent / "build_extension.py"
    spec = importlib.util.spec_from_file_location("build_extension", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"no module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build_extension = _load_build_extension()


def _read_toml(path: Path) -> dict:
    """``tomllib`` of ``path``, with a parse failure named as a ``ReleaseError``."""
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ReleaseError(f"{path}: invalid TOML: {error}") from error


def source_versions(root: Path) -> dict[str, str]:
    """The version each of the three ``VERSION_SOURCES`` states, keyed in that order.

    Args:
        root: the repository root.

    Returns:
        The manifest's ``version``, pyproject's ``[project] version`` and the first
        ``project(painterly VERSION X.Y.Z`` line of ``CMakeLists.txt``.

    Raises:
        ReleaseError: if a file is missing, its TOML is invalid, a key is absent, or
            ``CMakeLists.txt`` has no such line.
    """
    versions: dict[str, str] = {}

    manifest_path = root / VERSION_SOURCES[0]
    manifest = _read_toml(manifest_path)
    if "version" not in manifest:
        raise ReleaseError(f"{manifest_path}: no top-level 'version' key")
    versions[VERSION_SOURCES[0]] = str(manifest["version"])

    pyproject_path = root / VERSION_SOURCES[1]
    pyproject = _read_toml(pyproject_path)
    project = pyproject.get("project")
    if not isinstance(project, dict) or "version" not in project:
        raise ReleaseError(f"{pyproject_path}: no '[project] version' key")
    versions[VERSION_SOURCES[1]] = str(project["version"])

    cmake_path = root / VERSION_SOURCES[2]
    cmake_text = cmake_path.read_text(encoding="utf-8")
    match = CMAKE_PROJECT_VERSION.search(cmake_text)
    if match is None:
        raise ReleaseError(f"{cmake_path}: no 'project(painterly VERSION X.Y.Z' line")
    versions[VERSION_SOURCES[2]] = match.group(1)
    return versions


def release_version(root: Path) -> str:
    """The one version all three sources share.

    Raises:
        ReleaseError: if they disagree, naming every source with its version.
    """
    versions = source_versions(root)
    distinct = set(versions.values())
    if len(distinct) != 1:
        listed = ", ".join(f"{source} {versions[source]}" for source in VERSION_SOURCES)
        raise ReleaseError(f"version sources disagree: {listed}")
    return versions[VERSION_SOURCES[0]]


def read_manifest(root: Path) -> dict:
    """``tomllib`` of the add-on's ``blender_manifest.toml``."""
    return _read_toml(root / ADDON_DIR / MANIFEST_NAME)


def classify_tag(tag: str, version: str) -> str:
    """``"release"`` for ``v<version>``, ``"dry-run"`` for ``v<version>-dryrun.<n>``.

    Args:
        tag: the pushed tag, without ``refs/tags/``.
        version: the value ``release_version`` returns.

    Raises:
        ReleaseError: if the tag matches neither form, or matches one but names another version.
    """
    for pattern, mode in ((RELEASE_TAG, "release"), (DRY_RUN_TAG, "dry-run")):
        match = pattern.fullmatch(tag)
        if match is None:
            continue
        found = match.group("version")
        if found != version:
            raise ReleaseError(
                f"tag {tag} names version {found}, but the version sources say {version}"
            )
        return mode
    raise ReleaseError(
        f"tag {tag} is neither v{version} (release) nor v{version}-dryrun.<n> (dry run)"
    )


def source_tarball_name(extension_id: str, version: str) -> str:
    """``<id>-<version>-source.tar.gz``, the name of the source asset."""
    return f"{extension_id}-{version}{SOURCE_TARBALL_SUFFIX}"


def asset_names(extension_id: str, version: str) -> list[str]:
    """The five asset names, sorted."""
    zips = [
        build_extension.extension_zip_name(extension_id, version, platform)
        for platform in RELEASE_PLATFORMS
    ]
    return sorted([*zips, source_tarball_name(extension_id, version), CHECKSUMS_NAME])


def _pyproject_wheel_settings(root: Path) -> tuple[str, str]:
    """``[tool.scikit-build] wheel.py-api`` and the wheel-name form of ``[project] name``."""
    path = root / VERSION_SOURCES[1]
    pyproject = _read_toml(path)
    project = pyproject.get("project")
    if not isinstance(project, dict) or "name" not in project:
        raise ReleaseError(f"{path}: no '[project] name' key")
    distribution = WHEEL_NAME_SEPARATORS.sub("_", str(project["name"])).lower()
    scikit_build = pyproject.get("tool", {}).get("scikit-build", {})
    wheel = scikit_build.get("wheel", {})
    if "py-api" not in wheel:
        raise ReleaseError(f"{path}: no '[tool.scikit-build] wheel.py-api' key")
    return distribution, str(wheel["py-api"])


def check_wheels(wheel_dir: Path, root: Path) -> dict[str, Path]:
    """Check the wheel directory of a release and map each platform to its wheel.

    Args:
        wheel_dir: the directory the workflow downloaded the three wheels into.
        root: the repository root, for the version and pyproject's wheel settings.

    Returns:
        ``{platform: wheel}`` in ``RELEASE_PLATFORMS`` order.

    Raises:
        ReleaseError: for a file that is not a wheel, a wheel name this release cannot ship, or a
            platform set other than the three release platforms.
    """
    version = release_version(root)
    distribution, python_tag = _pyproject_wheel_settings(root)
    by_platform: dict[str, Path] = {}
    platforms: list[str] = []
    for entry in sorted(wheel_dir.iterdir()):
        if not entry.is_file() or not entry.name.endswith(".whl"):
            raise ReleaseError(f"{entry}: not a wheel: the wheel directory holds only .whl files")
        try:
            parsed = build_extension.parse_wheel_filename(entry.name)
            platform = build_extension.blender_platform_from_wheel(entry)
        except ValueError as error:
            raise ReleaseError(str(error)) from error
        if parsed.distribution != distribution:
            raise ReleaseError(
                f"{entry.name}: the distribution is {parsed.distribution}, not {distribution}"
            )
        if parsed.version != version:
            raise ReleaseError(f"{entry.name}: the version is {parsed.version}, not {version}")
        if parsed.build is not None:
            raise ReleaseError(f"{entry.name}: a build tag ({parsed.build}) is not expected")
        if parsed.python != python_tag:
            raise ReleaseError(f"{entry.name}: the python tag is {parsed.python}, not {python_tag}")
        if parsed.abi != STABLE_ABI_TAG:
            raise ReleaseError(f"{entry.name}: the abi tag is {parsed.abi}, not {STABLE_ABI_TAG}")
        unrepaired = [
            element
            for element in parsed.platform.split(".")
            if element.startswith(UNREPAIRED_LINUX_TAG_PREFIX)
        ]
        if unrepaired:
            raise ReleaseError(
                f"{entry.name}: {unrepaired[0]} is not a manylinux tag: a release ships only "
                "auditwheel-repaired wheels"
            )
        platforms.append(platform)
        by_platform[platform] = entry

    duplicates = sorted({platform for platform in platforms if platforms.count(platform) > 1})
    missing = sorted(set(RELEASE_PLATFORMS) - set(platforms))
    extra = sorted(set(platforms) - set(RELEASE_PLATFORMS))
    if duplicates or missing or extra:
        raise ReleaseError(
            f"{wheel_dir}: the wheel platforms are not exactly {list(RELEASE_PLATFORMS)} "
            f"(duplicates {duplicates}, missing {missing}, extra {extra})"
        )
    return {platform: by_platform[platform] for platform in RELEASE_PLATFORMS}


def _git(root: Path, *args: str) -> str:
    """Run git in ``root`` and return its stdout, or raise ``ReleaseError`` with its stderr."""
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise ReleaseError(f"git -C {root} {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


def git_tree(root: Path, rev: str = "HEAD") -> dict[str, tuple[str, str]]:
    """The tracked tree of ``rev``: path -> (mode, blob id).

    Raises:
        ReleaseError: if the repository's object format is not ``sha1`` (the format
            ``git_blob_id`` defines), or a tree entry is not a blob (a submodule, which
            ``git archive`` omits).
    """
    object_format = _git(root, "rev-parse", "--show-object-format").strip()
    if object_format != "sha1":
        raise ReleaseError(
            f"{root}: the repository's object format is {object_format}, not sha1: "
            "git_blob_id defines sha1"
        )
    tree: dict[str, tuple[str, str]] = {}
    for record in _git(root, "ls-tree", "-r", "-z", "--full-tree", rev).split("\0"):
        if not record:
            continue
        meta, _, path = record.partition("\t")
        mode, kind, oid = meta.split(" ")
        if kind != "blob":
            raise ReleaseError(
                f"{root}: {path} of {rev} is a {kind}, not a blob: git archive omits a submodule"
            )
        tree[path] = (mode, oid)
    return tree


def git_blob_id(data: bytes) -> str:
    """Git's object id of a blob holding ``data``.

    This is git's own definition (git-hash-object(1), object format sha1: ``blob <len>\\0`` then the
    bytes), not a checksum this tool chose.
    """
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _head_commit(root: Path) -> str:
    """The full id of ``HEAD``."""
    return _git(root, "rev-parse", "HEAD").strip()


def write_source_tarball(root: Path, out_dir: Path) -> Path:
    """Write ``git archive`` of ``HEAD`` into ``out_dir`` and return its path.

    ``-o`` is an absolute path: ``git -C <root>`` would resolve a relative one against ``root``.
    """
    extension_id = str(read_manifest(root)["id"])
    version = release_version(root)
    tarball = (out_dir / source_tarball_name(extension_id, version)).resolve()
    _git(
        root,
        "archive",
        "--format=tar.gz",
        f"--prefix={extension_id}-{version}/",
        "-o",
        str(tarball),
        "HEAD",
    )
    return tarball


def verify_source_tarball(tarball: Path, root: Path) -> None:
    """Check that ``tarball`` is exactly the tracked tree of ``HEAD``.

    The checks, in order, each raising on its first failure:

    1. its pax global ``comment`` header is the id of ``HEAD`` (git-archive(1), "ATTRIBUTES");
    2. every member is the prefix directory or is named ``<prefix><path>``;
    3. every regular file's git blob id equals its recorded blob id, a symlink is ``120000`` with
       its target's blob id, and any other member type is refused;
    4. that mapping equals ``git_tree(root, "HEAD")``;
    5. it holds ``LICENSE``, ``THIRD_PARTY_NOTICES.md``, one path under ``LICENSES/`` and one under
       ``third_party/``.
    """
    extension_id = str(read_manifest(root)["id"])
    version = release_version(root)
    prefix = f"{extension_id}-{version}/"
    head = _head_commit(root)
    found: dict[str, tuple[str, str]] = {}
    with tarfile.open(tarball, "r:gz") as archive:
        comment = archive.pax_headers.get(PAX_COMMENT)
        if comment != head:
            raise ReleaseError(
                f"{tarball.name}: archived from commit {comment}, not from HEAD {head}"
            )
        for member in archive.getmembers():
            if member.name == prefix.rstrip("/"):
                continue
            if not member.name.startswith(prefix):
                raise ReleaseError(f"{tarball.name}: {member.name} is outside {prefix}")
            path = member.name[len(prefix) :]
            if member.isdir():
                continue
            if member.isreg():
                data = archive.extractfile(member)
                assert data is not None
                contents = data.read()
                mode = "100755" if member.mode & 0o100 else "100644"
                found[path] = (mode, git_blob_id(contents))
            elif member.issym():
                found[path] = ("120000", git_blob_id(member.linkname.encode()))
            else:
                raise ReleaseError(f"{tarball.name}: {member.name} is not a file or a symlink")

    tree = git_tree(root, "HEAD")
    missing = sorted(set(tree) - set(found))
    extra = sorted(set(found) - set(tree))
    changed = sorted(path for path in set(tree) & set(found) if tree[path] != found[path])
    if missing or extra or changed:
        raise ReleaseError(
            f"{tarball.name}: not the tracked tree of HEAD {head} (missing {missing}, "
            f"extra {extra}, changed {changed})"
        )
    for name in (*LICENCE_FILES, f"{LICENCE_DIR}/", "third_party/"):
        if name.endswith("/"):
            if not any(path.startswith(name) for path in found):
                raise ReleaseError(f"{tarball.name}: no path under {name}")
        elif name not in found:
            raise ReleaseError(f"{tarball.name}: no {name}")


def _zip_member_names(archive: zipfile.ZipFile) -> list[str]:
    """The archive's member names that are files."""
    return [name for name in archive.namelist() if not name.endswith("/")]


def verify_extension_zip(
    zip_path: Path, platform: str, wheels: dict[str, Path], root: Path, blender: Path
) -> None:
    """Check one extension zip byte for byte against its wheel set and the add-on.

    The checks, each raising on its first failure:

    1. every CRC matches (``testzip`` is ``None``);
    2. the packaged manifest is the staged one plus Blender's generated table;
    3. ``wheels/`` holds exactly this platform's wheel, byte-equal to the file;
    4. ``LICENSE``, ``THIRD_PARTY_NOTICES.md`` and every file of ``LICENSES/`` are present, each
       byte-equal to the repository's copy;
    5. every other member is an add-on file with equal bytes, and ``__init__.py`` is there (a
       subset check: ``paths_exclude_pattern`` may leave add-on files out, never add foreign ones);
    6. ``blender --command extension validate`` exits 0. A zip without its wheel validates, which
       is why checks 3 to 5 exist.
    """
    source = read_manifest(root)
    addon_dir = root / ADDON_DIR
    licence_members = list(LICENCE_FILES)
    licence_members += [
        f"{LICENCE_DIR}/{entry.name}"
        for entry in sorted((root / LICENCE_DIR).iterdir())
        if entry.is_file()
    ]
    with zipfile.ZipFile(zip_path) as archive:
        broken = archive.testzip()
        if broken is not None:
            raise ReleaseError(f"{zip_path.name}: member {broken} fails its CRC")
        names = _zip_member_names(archive)

        if MANIFEST_NAME not in names:
            raise ReleaseError(f"{zip_path.name}: no {MANIFEST_NAME}")
        manifest = tomllib.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        expected_keys = set(source) | {"platforms", "wheels", "build"}
        if set(manifest) != expected_keys:
            raise ReleaseError(
                f"{zip_path.name}: {MANIFEST_NAME} has the keys {sorted(manifest)}, not "
                f"{sorted(expected_keys)}"
            )
        for key in set(source) - {"build"}:
            if manifest[key] != source[key]:
                raise ReleaseError(
                    f"{zip_path.name}: {MANIFEST_NAME} key {key} is {manifest[key]!r}, not "
                    f"{source[key]!r}"
                )
        if manifest["platforms"] != list(RELEASE_PLATFORMS):
            raise ReleaseError(
                f"{zip_path.name}: platforms is {manifest['platforms']!r}, not "
                f"{list(RELEASE_PLATFORMS)!r}"
            )
        wheel_members = [f"./{WHEELS_DIR}/{wheels[p].name}" for p in RELEASE_PLATFORMS]
        if manifest["wheels"] != wheel_members:
            raise ReleaseError(
                f"{zip_path.name}: wheels is {manifest['wheels']!r}, not {wheel_members!r}"
            )
        generated = {
            "platforms": [platform],
            "wheels": [f"./{WHEELS_DIR}/{wheels[platform].name}"],
        }
        expected_build = {**source.get("build", {}), "generated": generated}
        if manifest["build"] != expected_build:
            raise ReleaseError(
                f"{zip_path.name}: build is {manifest['build']!r}, not {expected_build!r}"
            )

        wheel_member = f"{WHEELS_DIR}/{wheels[platform].name}"
        packaged_wheels = [name for name in names if name.startswith(f"{WHEELS_DIR}/")]
        if packaged_wheels != [wheel_member]:
            raise ReleaseError(
                f"{zip_path.name}: the wheels are {packaged_wheels}, not [{wheel_member!r}]"
            )
        if archive.read(wheel_member) != wheels[platform].read_bytes():
            raise ReleaseError(f"{zip_path.name}: {wheel_member} differs from {wheels[platform]}")

        for member in licence_members:
            if member not in names:
                raise ReleaseError(f"{zip_path.name}: no {member}")
            if archive.read(member) != (root / member).read_bytes():
                raise ReleaseError(f"{zip_path.name}: {member} differs from {root / member}")

        for member in names:
            if member in licence_members or member in (MANIFEST_NAME, wheel_member):
                continue
            source_file = addon_dir / member
            if not source_file.is_file():
                raise ReleaseError(f"{zip_path.name}: {member} is not an add-on file")
            if archive.read(member) != source_file.read_bytes():
                raise ReleaseError(f"{zip_path.name}: {member} differs from {source_file}")
        if "__init__.py" not in names:
            raise ReleaseError(f"{zip_path.name}: no __init__.py")

    proc = subprocess.run(
        [str(blender), "--command", "extension", "validate", str(zip_path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise ReleaseError(
            f"{zip_path.name}: `blender --command extension validate` exited with status "
            f"{proc.returncode}\n{proc.stdout}\n{proc.stderr}"
        )


def write_sha256sums(out_dir: Path) -> Path:
    """Write ``SHA256SUMS`` over every regular file of ``out_dir`` except itself; return its path.

    The format is ``sha256sum -c``'s: ``<64 lowercase hex>``, two spaces, the file's name.
    """
    path = out_dir / CHECKSUMS_NAME
    lines = []
    for entry in sorted(out_dir.iterdir(), key=lambda item: item.name):
        if entry.name == CHECKSUMS_NAME or not entry.is_file():
            continue
        digest = hashlib.sha256(entry.read_bytes()).hexdigest()
        lines.append(f"{digest}  {entry.name}\n")
    path.write_bytes("".join(lines).encode("utf-8"))
    return path


def write_notes(notes: Path, out_dir: Path, root: Path) -> None:
    """Write the release notes, with one row per ``SHA256SUMS`` line.

    The rows are read back from ``SHA256SUMS`` in its order, so the notes and the checksums cannot
    disagree. ``<licence>`` is the manifest's ``license`` list with each ``SPDX:`` prefix removed.
    """
    manifest = read_manifest(root)
    version = release_version(root)
    extension_id = str(manifest["id"])
    commit = _head_commit(root)
    licences = ", ".join(str(item).removeprefix("SPDX:") for item in manifest["license"])
    rows = []
    for line in (out_dir / CHECKSUMS_NAME).read_text(encoding="utf-8").splitlines():
        digest, _, name = line.partition("  ")
        rows.append(f"| `{name}` | {(out_dir / name).stat().st_size} | `{digest}` |")
    source = source_tarball_name(extension_id, version)
    text = (
        f"Painterly {version} for Blender {manifest['blender_version_min']} or later, built from "
        f"commit {commit}.\n"
        "\n"
        "Download the zip for your platform and install it with **Install from Disk** in Blender's "
        "Get Extensions preferences.\n"
        "\n"
        "| Asset | Bytes | SHA-256 |\n"
        "|---|---|---|\n" + "".join(f"{row}\n" for row in rows) + "\n"
        f"`{source}` is the source of this release: the exact tracked tree of commit {commit}, "
        "including\n"
        "`third_party/` and `LICENSES/`. Painterly is licensed "
        f"{licences}. `THIRD_PARTY_NOTICES.md` lists the licences of the code\n"
        "it includes, and the build fetches Embree and nanobind at the versions pinned in "
        "`cmake/painterly_embree.cmake` and\n"
        "`pyproject.toml`.\n"
    )
    notes.parent.mkdir(parents=True, exist_ok=True)
    notes.write_text(text, encoding="utf-8")


def package(
    root: Path, blender: Path, wheel_dir: Path, out_dir: Path, notes: Path, work_dir: Path
) -> list[Path]:
    """Build and verify the five release assets into ``out_dir``; return their paths.

    Args:
        root: the repository root.
        blender: the Blender executable that builds and validates the zips.
        wheel_dir: the three wheels, one per ``RELEASE_PLATFORMS`` platform.
        out_dir: the directory the assets are written into; it must not exist yet.
        notes: where the release notes are written.
        work_dir: where the extension is staged, under ``<work_dir>/extension/<id>``.

    Raises:
        ReleaseError: if a check fails, or ``out_dir`` already exists.
    """
    version = release_version(root)
    extension_id = str(read_manifest(root)["id"])
    wheels = check_wheels(wheel_dir, root)
    if not blender.is_file():
        raise ReleaseError(f"{blender} does not exist")
    if out_dir.exists():
        raise ReleaseError(
            f"{out_dir} exists; remove it first: a release never mixes the assets of two runs"
        )
    out_dir.mkdir(parents=True)

    staging_dir = work_dir / "extension" / extension_id
    zips = build_extension.build_extension(
        blender,
        [wheels[platform] for platform in RELEASE_PLATFORMS],
        staging_dir,
        out_dir,
        addon_dir=root / ADDON_DIR,
        root=root,
    )
    expected_zips = [
        out_dir / build_extension.extension_zip_name(extension_id, version, platform)
        for platform in RELEASE_PLATFORMS
    ]
    if zips != expected_zips:
        raise ReleaseError(
            f"the extension zips are {[str(zip_path) for zip_path in zips]}, not "
            f"{[str(zip_path) for zip_path in expected_zips]}"
        )

    member_sets = []
    for platform, zip_path in zip(RELEASE_PLATFORMS, zips, strict=True):
        verify_extension_zip(zip_path, platform, wheels, root, blender)
        with zipfile.ZipFile(zip_path) as archive:
            member_sets.append(
                {
                    name
                    for name in _zip_member_names(archive)
                    if not name.startswith(f"{WHEELS_DIR}/")
                }
            )
    if any(members != member_sets[0] for members in member_sets[1:]):
        raise ReleaseError(f"the zips of {list(RELEASE_PLATFORMS)} do not hold the same members")

    tarball = write_source_tarball(root, out_dir)
    verify_source_tarball(tarball, root)
    write_sha256sums(out_dir)

    names = sorted(entry.name for entry in out_dir.iterdir())
    expected_names = asset_names(extension_id, version)
    if names != expected_names:
        raise ReleaseError(f"{out_dir} holds {names}, not {expected_names}")
    write_notes(notes, out_dir, root)
    return [out_dir / name for name in expected_names]


def _plan(args: argparse.Namespace) -> int:
    """Print the two ``$GITHUB_OUTPUT`` lines of ``plan``, or nothing at all."""
    root = Path.cwd()
    version = release_version(root)
    mode = "dry-run" if args.dispatch else classify_tag(args.tag, version)
    sys.stdout.write(f"mode={mode}\nversion={version}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    commands = parser.add_subparsers(dest="command", required=True)

    plan = commands.add_parser("plan", help="classify the run and print $GITHUB_OUTPUT lines")
    source = plan.add_mutually_exclusive_group(required=True)
    source.add_argument("--tag", help="the pushed tag, e.g. v0.1.0 or v0.1.0-dryrun.1")
    source.add_argument("--dispatch", action="store_true", help="a workflow_dispatch run")

    zip_name = commands.add_parser("zip-name", help="print the extension zip name of a platform")
    zip_name.add_argument("--platform", required=True, choices=RELEASE_PLATFORMS)

    package_parser = commands.add_parser("package", help="build and verify the release assets")
    package_parser.add_argument("--blender", required=True, type=Path)
    package_parser.add_argument("--wheel-dir", required=True, type=Path)
    package_parser.add_argument("--out-dir", type=Path, default=Path("dist") / "release")
    package_parser.add_argument("--notes", type=Path, default=Path("dist") / "release-notes.md")
    package_parser.add_argument("--work-dir", type=Path, default=Path("build") / "release")

    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            return _plan(args)
        if args.command == "zip-name":
            root = Path.cwd()
            manifest = read_manifest(root)
            print(
                build_extension.extension_zip_name(
                    str(manifest["id"]), release_version(root), args.platform
                )
            )
            return 0
        out_dir: Path = args.out_dir
        if args.work_dir.resolve() == (Path.cwd() / "build").resolve():
            raise ReleaseError(
                f"--work-dir {args.work_dir} would stage into build/extension/painterly, the "
                "directory `make extension` stages into; use the default build/release"
            )
        paths = package(
            Path.cwd(), args.blender, args.wheel_dir, out_dir, args.notes, args.work_dir
        )
    except ReleaseError as error:
        print(f"release: {error}", file=sys.stderr)
        return 1
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
