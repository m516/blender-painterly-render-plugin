#!/usr/bin/env python3
"""Fetch a verified Blender release into .cache/ and print the path of its executable.

Usage: fetch_blender.py [--version 5.2.2] [--platform PLATFORM] [--print-path-only]
PLATFORM is linux-x64, macos-arm64 or windows-x64.

Steps. Each step is skipped when its work is already done, so a second run downloads nothing:

1. Download https://download.blender.org/release/Blender{major.minor}/
   blender-{v}-{platform}{archive} into .cache/blender/, together with blender-{v}.sha256
   from the same release directory. The archive is .tar.xz (linux-x64), .dmg (macos-arm64)
   or .zip (windows-x64).
2. Verify the archive's sha256 against its line in blender-{v}.sha256. A mismatch
   deletes the download and fails.
3. Install to .cache/blender/blender-{v}-{platform}/ through a new empty staging directory:
   extract the tarball or the zip, or copy Blender.app out of the mounted disk image.
4. Windows only: report where python3.dll sits (see _report_python3_dll). Nothing here fails
   the fetch: the import in the coexistence run decides whether the module loads.
5. Print the absolute path of the Blender executable.

Status messages go to stderr, so make shows download progress. The path goes to stdout:
as "Blender {v} executable: <path>", or as "<path>" alone with --print-path-only. That flag
performs no network access and no file I/O: it prints where the executable is or will be.
Exit status is 0 on success and 1 on failure.

Every request carries USER_AGENT. download.blender.org's CDN answers 403 to Python's default
urllib User-Agent (CLAUDE.md, "Network notes").
"""

import argparse
import hashlib
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# Downloads live under .cache/ (git-ignored, CLAUDE.md rule 4).
CACHE_DIR = REPO_ROOT / ".cache" / "blender"
RELEASE_URL = "https://download.blender.org/release"
DEFAULT_VERSION = "5.2.2"
PLATFORMS = ("linux-x64", "macos-arm64", "windows-x64")
# The release platform of each host, keyed by (sys.platform, platform.machine().lower()).
# A host that is not listed has no default platform, so --platform is required there.
HOST_PLATFORMS = {
    ("linux", "x86_64"): "linux-x64",
    ("darwin", "arm64"): "macos-arm64",
    ("win32", "amd64"): "windows-x64",
}
# The release archive of each platform, as a suffix of blender-{v}-{platform}.
ARCHIVE_SUFFIX = {"linux-x64": ".tar.xz", "macos-arm64": ".dmg", "windows-x64": ".zip"}
# Where the executable sits inside the install directory blender-{v}-{platform}/.
EXECUTABLE_IN_INSTALL = {
    "linux-x64": Path("blender"),
    "macos-arm64": Path("Blender.app") / "Contents" / "MacOS" / "Blender",
    "windows-x64": Path("blender.exe"),
}
# The macOS bundle name on the disk image.
MACOS_APP_NAME = "Blender.app"
# Windows: the stable-ABI DLL that an abi3 module imports, and the version-specific
# DLLs (python312.dll, ...).
PYTHON3_DLL = "python3.dll"
PYTHON3_VERSIONED_DLL = "python3??.dll"
# Windows: name prefix of the Blender shared library. python3.dll is reported in its directory.
BLENDER_SHARED_PREFIX = "blender.shared"
# Socket timeout in seconds for each network read. It does not change any downloaded byte.
NETWORK_TIMEOUT_S = 120
# I/O buffer in bytes for downloads and hashing. It does not change any downloaded byte.
IO_CHUNK_BYTES = 1 << 20
# Honest tool identification: it names this tool and this repository and impersonates no client.
# CLAUDE.md, "Network notes", records that the CDN rejects the default Python User-Agent.
USER_AGENT = (
    "painterly-fetch-blender/0.1 (+https://github.com/m516/blender-painterly-render-plugin)"
)
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class FetchError(RuntimeError):
    """A download, verification or extraction step failed."""


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


def _download(url: str, dest: Path) -> None:
    """Stream url into dest. The file appears under its final name only once it is complete.

    Whatever raises, the partial file is removed before the exception goes on.
    """
    _log(f"downloading {url}")
    partial = dest.with_name(dest.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with (
            urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_S) as response,
            partial.open("wb") as out,
        ):
            while chunk := response.read(IO_CHUNK_BYTES):
                out.write(chunk)
        partial.replace(dest)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(IO_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def _listed_sha256(sha_file: Path, filename: str) -> str | None:
    """Return the sha256 that sha_file lists for filename, or None when it does not list it.

    The format is "<hex>  <name>" per line. A leading "*" on the name marks binary mode.
    """
    for line in sha_file.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1].lstrip("*") == filename:
            digest = fields[0].lower()
            if not SHA256_HEX.match(digest):
                raise FetchError(f"{sha_file.name}: malformed sha256 for {filename}")
            return digest
    return None


def _extract_tarball(archive: Path, staging: Path) -> None:
    """Extract a .tar.xz archive into staging."""
    _log(f"extracting {archive.name}")
    # filter="data" refuses absolute paths, links that leave the directory and device files.
    with tarfile.open(archive, mode="r:xz") as tar:
        tar.extractall(staging, filter="data")


def _extract_zip(archive: Path, staging: Path) -> None:
    """Extract a .zip archive into staging. ZipFile drops absolute paths and ".." members."""
    _log(f"extracting {archive.name}")
    with zipfile.ZipFile(archive) as zipped:
        zipped.extractall(staging)


def _copy_app_from_dmg(image: Path, app_dir: Path) -> None:
    """Copy Blender.app from the disk image into app_dir, which must not exist yet.

    The image is attached read-only without a Finder window, and it is always detached again.
    """
    _log(f"attaching {image.name}")
    attached = subprocess.run(
        ["hdiutil", "attach", "-nobrowse", "-readonly", "-plist", str(image)],
        capture_output=True,
        check=False,
    )
    if attached.returncode != 0:
        detail = attached.stderr.decode("utf-8", errors="replace").strip()
        raise FetchError(f"hdiutil attach {image.name} failed: {detail}")
    mount_points = [
        entity["mount-point"]
        for entity in plistlib.loads(attached.stdout).get("system-entities", [])
        if "mount-point" in entity
    ]
    if not mount_points:
        raise FetchError(f"hdiutil attach {image.name} mounted no volume")
    mount = Path(mount_points[0])
    try:
        source = mount / MACOS_APP_NAME
        if not source.is_dir():
            raise FetchError(f"{image.name} does not contain {MACOS_APP_NAME}")
        shutil.copytree(source, app_dir, symlinks=True)
    finally:
        detached = subprocess.run(
            ["hdiutil", "detach", str(mount)], capture_output=True, check=False
        )
        if detached.returncode != 0:
            _log(f"warning: hdiutil detach {mount} failed; the volume stays mounted")


def _check_version(version: str) -> None:
    if not SEMVER.match(version):
        raise FetchError(f"version must look like 5.2.2, not {version!r}")


def _report_python3_dll(install_dir: Path, executable: Path) -> None:
    """Report where python3.dll sits in a Windows install. Lines go to stderr, into fetch.log.

    An abi3 module imports python3.dll. Blender's process (blender.exe) loads _painterly, so the DLL
    search directories of blender.exe matter, not those of python.exe. The report prints one line
    per python3.dll and python3??.dll under the install, with its path relative to the install. Then
    it prints exactly one verdict line:

    - if the install has a blender.shared* file: `python3.dll in blender.shared: yes|no`, whether
      python3.dll sits in the directory of such a file;
    - otherwise: `python3.dll next to blender.exe: yes|no`.

    The verdict only describes the install. Whether the module loads is decided by the import in the
    coexistence run, so no line here fails the fetch.
    """
    for dll in sorted({*install_dir.rglob(PYTHON3_DLL), *install_dir.rglob(PYTHON3_VERSIONED_DLL)}):
        _log(f"found {dll.relative_to(install_dir)}")
    shared = sorted(
        path for path in install_dir.rglob(f"{BLENDER_SHARED_PREFIX}*") if path.is_file()
    )
    if shared:
        present = any((path.parent / PYTHON3_DLL).is_file() for path in shared)
        _log(f"python3.dll in blender.shared: {'yes' if present else 'no'}")
    else:
        present = (executable.parent / PYTHON3_DLL).is_file()
        _log(f"python3.dll next to blender.exe: {'yes' if present else 'no'}")


def executable_path(version: str, platform: str) -> Path:
    """Where fetch() installs the executable. It does no I/O, so --print-path-only is offline."""
    _check_version(version)
    return CACHE_DIR / f"blender-{version}-{platform}" / EXECUTABLE_IN_INSTALL[platform]


def _install(archive: Path, platform: str, install_name: str) -> None:
    """Install archive as CACHE_DIR/install_name, staging in a new empty directory first."""
    staging = Path(tempfile.mkdtemp(prefix="extract-", dir=CACHE_DIR))
    try:
        if platform == "linux-x64":
            _extract_tarball(archive, staging)
        elif platform == "windows-x64":
            _extract_zip(archive, staging)
        else:
            (staging / install_name).mkdir()
            _copy_app_from_dmg(archive, staging / install_name / MACOS_APP_NAME)
        extracted = staging / install_name
        executable = extracted / EXECUTABLE_IN_INSTALL[platform]
        if not executable.is_file():
            raise FetchError(
                f"{archive.name} does not contain {install_name}/{EXECUTABLE_IN_INSTALL[platform]}"
            )
        target = CACHE_DIR / install_name
        if target.exists():
            shutil.rmtree(target)
        extracted.rename(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def fetch(version: str, platform: str) -> Path:
    """Ensure the release is downloaded, verified and installed; return the executable path."""
    _check_version(version)
    major_minor = ".".join(version.split(".")[:2])
    release_dir = f"{RELEASE_URL}/Blender{major_minor}"
    install_name = f"blender-{version}-{platform}"
    archive_name = f"{install_name}{ARCHIVE_SUFFIX[platform]}"
    sha_name = f"blender-{version}.sha256"

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    archive = CACHE_DIR / archive_name
    sha_file = CACHE_DIR / sha_name

    already_verified = (
        archive.is_file()
        and sha_file.is_file()
        and _listed_sha256(sha_file, archive_name) == _sha256(archive)
    )
    if already_verified:
        _log(f"{archive_name} is present and verified")
    else:
        archive.unlink(missing_ok=True)
        _download(f"{release_dir}/{sha_name}", sha_file)
        expected = _listed_sha256(sha_file, archive_name)
        if expected is None:
            raise FetchError(f"{sha_name} does not list {archive_name}")
        _download(f"{release_dir}/{archive_name}", archive)
        actual = _sha256(archive)
        if actual != expected:
            archive.unlink()
            raise FetchError(
                f"sha256 mismatch for {archive_name}: expected {expected}, got {actual}"
            )
        _log(f"{archive_name} verified (sha256 {actual})")

    executable = executable_path(version, platform)
    if not executable.is_file():
        _install(archive, platform, install_name)
    if platform == "windows-x64":
        _report_python3_dll(executable.parent, executable)
    return executable


def main(argv: list[str] | None = None) -> int:
    host = HOST_PLATFORMS.get((sys.platform, platform.machine().lower()))
    platform_help = "release platform: " + ", ".join(PLATFORMS)
    if host is None:
        platform_help += " (required: this host has no default platform)"
    else:
        platform_help += " (default: %(default)s, the host platform)"
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--version", default=DEFAULT_VERSION, help="Blender version (default: %(default)s)"
    )
    parser.add_argument(
        "--platform", default=host, choices=PLATFORMS, required=host is None, help=platform_help
    )
    parser.add_argument(
        "--print-path-only",
        action="store_true",
        help=(
            "stdout carries only the executable path, with no network or file access "
            "(used by run.sh)"
        ),
    )
    args = parser.parse_args(argv)
    if args.print_path_only:
        try:
            print(executable_path(args.version, args.platform))
        except FetchError as error:
            print(f"fetch_blender: {error}", file=sys.stderr)
            return 1
        return 0
    try:
        executable = fetch(args.version, args.platform)
    except (FetchError, OSError, subprocess.SubprocessError) as error:
        print(f"fetch_blender: {error}", file=sys.stderr)
        return 1
    print(f"Blender {args.version} executable: {executable}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
