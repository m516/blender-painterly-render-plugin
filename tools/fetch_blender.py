#!/usr/bin/env python3
"""Fetch a verified Blender release into .cache/ and print the path of its executable.

Usage: fetch_blender.py [--version 5.2.2] [--platform linux-x64] [--print-path-only]

Steps. Each step is skipped when its work is already done, so a second run downloads nothing:

1. Download https://download.blender.org/release/Blender{major.minor}/
   blender-{v}-{platform}.tar.xz into .cache/blender/, together with blender-{v}.sha256
   from the same release directory.
2. Verify the tarball's sha256 against its line in blender-{v}.sha256. A mismatch
   deletes the download and fails.
3. Extract to .cache/blender/blender-{v}-{platform}/ through a new empty staging
   directory.
4. Print the absolute path of the blender executable.

Status messages go to stderr, so make shows download progress. The path goes to stdout:
as "Blender {v} executable: <path>", or as "<path>" alone with --print-path-only. That flag
performs no network access and no file I/O: it prints where the executable is or will be.
Exit status is 0 on success and 1 on failure.

Every request carries USER_AGENT. download.blender.org's CDN answers 403 to Python's default
urllib User-Agent (CLAUDE.md, "Network notes").
"""

import argparse
import hashlib
import re
import shutil
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
# Downloads live under .cache/ (git-ignored, CLAUDE.md rule 4).
CACHE_DIR = REPO_ROOT / ".cache" / "blender"
RELEASE_URL = "https://download.blender.org/release"
DEFAULT_VERSION = "5.2.2"
DEFAULT_PLATFORM = "linux-x64"
# Tarball builds only. The Windows and macOS releases are not .tar.xz archives.
PLATFORMS = ("linux-x64",)
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
    """Stream url into dest. The file appears under its final name only once it is complete."""
    _log(f"downloading {url}")
    partial = dest.with_name(dest.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with (
        urllib.request.urlopen(request, timeout=NETWORK_TIMEOUT_S) as response,
        partial.open("wb") as out,
    ):
        while chunk := response.read(IO_CHUNK_BYTES):
            out.write(chunk)
    partial.replace(dest)


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


def _extract(tarball: Path, install_name: str) -> None:
    """Extract tarball to CACHE_DIR/install_name, staging in a new empty directory first."""
    _log(f"extracting {tarball.name}")
    staging = Path(tempfile.mkdtemp(prefix="extract-", dir=CACHE_DIR))
    try:
        # filter="data" refuses absolute paths, links that leave the directory and device files.
        with tarfile.open(tarball, mode="r:xz") as archive:
            archive.extractall(staging, filter="data")
        extracted = staging / install_name
        if not (extracted / "blender").is_file():
            raise FetchError(f"{tarball.name} does not contain {install_name}/blender")
        target = CACHE_DIR / install_name
        if target.exists():
            shutil.rmtree(target)
        extracted.rename(target)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _check_version(version: str) -> None:
    if not SEMVER.match(version):
        raise FetchError(f"version must look like 5.2.2, not {version!r}")


def executable_path(version: str, platform: str) -> Path:
    """Where fetch() installs the executable. It does no I/O, so --print-path-only is offline."""
    _check_version(version)
    return CACHE_DIR / f"blender-{version}-{platform}" / "blender"


def fetch(version: str, platform: str) -> Path:
    """Ensure the release is downloaded, verified and extracted; return the executable path."""
    _check_version(version)
    major_minor = ".".join(version.split(".")[:2])
    release_dir = f"{RELEASE_URL}/Blender{major_minor}"
    install_name = f"blender-{version}-{platform}"
    tarball_name = f"{install_name}.tar.xz"
    sha_name = f"blender-{version}.sha256"

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tarball = CACHE_DIR / tarball_name
    sha_file = CACHE_DIR / sha_name

    already_verified = (
        tarball.is_file()
        and sha_file.is_file()
        and _listed_sha256(sha_file, tarball_name) == _sha256(tarball)
    )
    if already_verified:
        _log(f"{tarball_name} is present and verified")
    else:
        tarball.unlink(missing_ok=True)
        _download(f"{release_dir}/{sha_name}", sha_file)
        expected = _listed_sha256(sha_file, tarball_name)
        if expected is None:
            raise FetchError(f"{sha_name} does not list {tarball_name}")
        _download(f"{release_dir}/{tarball_name}", tarball)
        actual = _sha256(tarball)
        if actual != expected:
            tarball.unlink()
            raise FetchError(
                f"sha256 mismatch for {tarball_name}: expected {expected}, got {actual}"
            )
        _log(f"{tarball_name} verified (sha256 {actual})")

    executable = executable_path(version, platform)
    if not executable.is_file():
        _extract(tarball, install_name)
    return executable


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--version", default=DEFAULT_VERSION, help="Blender version (default: %(default)s)"
    )
    parser.add_argument("--platform", default=DEFAULT_PLATFORM, choices=PLATFORMS)
    parser.add_argument(
        "--print-path-only",
        action="store_true",
        help="stdout carries only the executable path (for Makefile $(shell ...))",
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
    except (FetchError, OSError) as error:
        print(f"fetch_blender: {error}", file=sys.stderr)
        return 1
    print(f"Blender {args.version} executable: {executable}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
