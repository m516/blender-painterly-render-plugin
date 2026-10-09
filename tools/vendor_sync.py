#!/usr/bin/env python3
"""Pinned, hash-checked vendoring of Cycles into third_party/cycles/ (T3.1; CLAUDE.md rule 1).

Subcommands (paths in the manifest are relative to each upstream's `root`):

  fetch                       check out every upstream at its pinned commit under .cache/vendor/
  sync                        copy each VENDORED.toml entry from its checkout, apply patches/*.patch
                              in lexical order, and rewrite VENDORED.toml with the resulting hashes
  check [--upstream]          verify third_party/cycles against VENDORED.toml with no network;
                              with --upstream also re-derive every file from its checkout and
                              patches, byte for byte
  add [--upstream NAME] PATH... [--dest-prefix P]
                              vendor upstream files (dest = PATH, or P/<file name> with
                              --dest-prefix), then sync
  remove DEST...              delete the entries and their files, then sync
  closure HEADER...           print the transitive quoted-#include closure of HEADERs inside the
                              cycles root

Exit status: 0 on success, 1 on a failed check or an error, 2 on a usage error. Only the standard
library and the git CLI are used. Upstream checkouts are read as data and never executed (CLAUDE.md
rule 5): run this tool with `python -I` when it reads them.
"""

import argparse
import hashlib
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from collections import deque
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VENDOR_DIR = REPO_ROOT / "third_party" / "cycles"
MANIFEST = VENDOR_DIR / "VENDORED.toml"
PATCH_DIR = VENDOR_DIR / "patches"
PATCH_GLOB = "*.patch"
# Files directly under VENDOR_DIR that document or describe the tree, not vendored entries.
UNLISTED_FILES = frozenset({"VENDORED.toml", "README.md"})
# Upstream checkouts live under .cache/ (git-ignored, CLAUDE.md rule 4).
CHECKOUT_DIR = REPO_ROOT / ".cache" / "vendor"
# Checkout directory prefix per upstream. Blender's repository is the upstream of Cycles.
CHECKOUT_PREFIX = {"cycles": "blender", "sse2neon": "sse2neon"}
# A checkout directory is named by its tag, or else by the first SHORT_SHA_LEN hex digits of its
# commit, as in the T3.1 card (.cache/vendor/blender-v5.2.2, .cache/vendor/sse2neon-227cc413).
SHORT_SHA_LEN = 8
SHA1_HEX_LEN = 40  # git commit ids in the default SHA-1 object format
# Shallow clones and fetches take one commit: the pinned one, with no history behind it.
SHALLOW_DEPTH = "1"
SHA256_HEX_LEN = 64  # hex digits of a SHA-256 digest (FIPS 180-4)
CYCLES = "cycles"
DEFAULT_UPSTREAM = CYCLES
# Text that every patched vendored file carries (third_party/cycles/README.md).
MODIFIED_NOTICE = "Modified by the Painterly project"
# A quoted include. Angle-bracket includes name system or external headers, outside the closure.
INCLUDE_RE = re.compile(r'^[ \t]*#[ \t]*include[ \t]*"([^"]+)"', re.MULTILINE)
MANIFEST_HEADER = (
    "# Pinned upstream sources of third_party/cycles (CLAUDE.md rule 1, docs/architecture.md).",
    "# Written by tools/vendor_sync.py (fetch, sync, add, remove); do not edit by hand.",
    "# upstream_sha256 hashes the upstream file; sha256 hashes the vendored file after",
    "# patches/ is applied.",
)
# Git must never prompt for credentials: a missing credential is an error, not a hang.
GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


class VendorError(Exception):
    """A vendoring step cannot finish. The message names the file or upstream and what failed."""


@dataclass(frozen=True)
class Upstream:
    """A pinned upstream repository.

    `tag` is empty when the pin is a bare commit; `root` is empty when the upstream root is the
    repository root.
    """

    name: str
    repo: str
    commit: str
    root: str
    tag: str = ""


@dataclass(frozen=True)
class Entry:
    """One vendored file.

    `dest` is relative to third_party/cycles. Both hashes are lowercase hex SHA-256 digests; they
    are empty only transiently, while `add` builds the new entries before `sync` fills them in.
    """

    upstream: str
    upstream_path: str
    dest: str
    upstream_sha256: str = ""
    sha256: str = ""
    patched: bool = False


@dataclass(frozen=True)
class Manifest:
    """The parsed VENDORED.toml: upstream pins and the ordered list of vendored files."""

    upstreams: dict[str, Upstream]
    entries: list[Entry]


def _report(message: str) -> None:
    """Print a status line for the operator on stderr, so that stdout carries only results."""
    print(message, file=sys.stderr)


def _sha256(data: bytes) -> str:
    """Lowercase hex SHA-256 digest of data."""
    return hashlib.sha256(data).hexdigest()


def _is_hex(text: str, length: int) -> bool:
    """True when text is exactly `length` lowercase hex digits."""
    return re.fullmatch(f"[0-9a-f]{{{length}}}", text) is not None


def _rel_path(text: str, what: str) -> str:
    """Return text when it is a canonical POSIX path relative to its root, else raise VendorError.

    Canonical means `posixpath.normpath(text) == text`; absolute paths, `..` escapes and backslashes
    are refused. `what` names the field in the error message.
    """
    canonical = posixpath.normpath(text) if text else "."
    escapes = canonical == ".." or canonical.startswith(("../", "/"))
    if not text or canonical == "." or canonical != text or escapes or "\\" in text:
        raise VendorError(f"{what}: expected a canonical relative path, got {text!r}")
    return text


def _toml(text: str) -> str:
    """TOML basic string for text. JSON string escaping is valid TOML basic-string escaping here."""
    return json.dumps(text)


def _text(table: Mapping[str, object], key: str, path: Path, required: bool = True) -> str:
    """String value of key in a parsed TOML table.

    A missing required key or a non-string value raises VendorError. A missing optional key gives
    the empty string.
    """
    if key not in table:
        if required:
            raise VendorError(f"{path}: a table lacks the key {key!r}")
        return ""
    value = table[key]
    if not isinstance(value, str):
        raise VendorError(f"{path}: the key {key!r} must be a string")
    return value


def _flag(table: Mapping[str, object], key: str, path: Path) -> bool:
    """Boolean value of key in a parsed TOML table; anything else raises VendorError."""
    value = table.get(key)
    if not isinstance(value, bool):
        raise VendorError(f"{path}: the key {key!r} must be true or false")
    return value


def check_structure(manifest: Manifest) -> None:
    """Reject an unknown upstream, a malformed commit, a non-canonical path or a duplicate dest.

    Hashes are not examined here; `load_manifest` checks their format.
    """
    for upstream in manifest.upstreams.values():
        if upstream.name not in CHECKOUT_PREFIX:
            raise VendorError(
                f"unknown upstream {upstream.name!r}; known upstreams: {sorted(CHECKOUT_PREFIX)}"
            )
        if not _is_hex(upstream.commit, SHA1_HEX_LEN):
            raise VendorError(
                f"[upstream.{upstream.name}]: commit must be {SHA1_HEX_LEN} lowercase hex digits"
            )
        if upstream.root:
            _rel_path(upstream.root, f"[upstream.{upstream.name}] root")
    dests: set[str] = set()
    for entry in manifest.entries:
        if entry.upstream not in manifest.upstreams:
            raise VendorError(f"{entry.dest}: upstream {entry.upstream!r} is not in VENDORED.toml")
        _rel_path(entry.upstream_path, f"{entry.dest}: upstream_path")
        _rel_path(entry.dest, "dest")
        if entry.dest in dests:
            raise VendorError(f"{entry.dest} is listed twice in VENDORED.toml")
        dests.add(entry.dest)


def load_manifest(path: Path = MANIFEST) -> Manifest:
    """Parse and validate VENDORED.toml, including the SHA-256 format of every recorded hash.

    Raises VendorError when the file cannot be read, a key is missing or malformed, or the
    structure is invalid.
    """
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as err:
        raise VendorError(f"cannot read {path}: {err}") from err
    upstreams = {
        name: Upstream(
            name=name,
            repo=_text(table, "repo", path),
            commit=_text(table, "commit", path),
            root=_text(table, "root", path),
            tag=_text(table, "tag", path, required=False),
        )
        for name, table in data.get("upstream", {}).items()
    }
    entries = [
        Entry(
            upstream=_text(table, "upstream", path),
            upstream_path=_text(table, "upstream_path", path),
            dest=_text(table, "dest", path),
            upstream_sha256=_text(table, "upstream_sha256", path),
            sha256=_text(table, "sha256", path),
            patched=_flag(table, "patched", path),
        )
        for table in data.get("file", [])
    ]
    manifest = Manifest(upstreams, entries)
    check_structure(manifest)
    for entry in entries:
        for digest in (entry.upstream_sha256, entry.sha256):
            if not _is_hex(digest, SHA256_HEX_LEN):
                raise VendorError(f"{path}: {entry.dest}: {digest!r} is not a SHA-256 hex digest")
    return manifest


def render_manifest(manifest: Manifest) -> str:
    """The VENDORED.toml text: the fixed header, the upstream tables, then the [[file]] entries."""
    lines = list(MANIFEST_HEADER)
    for upstream in manifest.upstreams.values():
        lines += ["", f"[upstream.{upstream.name}]", f"repo = {_toml(upstream.repo)}"]
        if upstream.tag:
            lines.append(f"tag = {_toml(upstream.tag)}")
        lines += [f"commit = {_toml(upstream.commit)}", f"root = {_toml(upstream.root)}"]
    for entry in manifest.entries:
        lines += [
            "",
            "[[file]]",
            f"upstream = {_toml(entry.upstream)}",
            f"upstream_path = {_toml(entry.upstream_path)}",
            f"dest = {_toml(entry.dest)}",
            f"upstream_sha256 = {_toml(entry.upstream_sha256)}",
            f"sha256 = {_toml(entry.sha256)}",
            f"patched = {str(entry.patched).lower()}",
        ]
    return "\n".join(lines) + "\n"


def _git(args: list[str], cwd: Path | None = None) -> str:
    """Run git with args and return its stdout without the trailing newline.

    A failing git command raises VendorError carrying git's own error text.
    """
    command = ["git", *args]
    try:
        result = subprocess.run(
            command, cwd=cwd, env=GIT_ENV, check=True, capture_output=True, text=True
        )
    except subprocess.CalledProcessError as err:
        raise VendorError(f"{' '.join(command)} failed: {err.stderr.strip()}") from err
    except OSError as err:
        raise VendorError(f"cannot run git: {err}") from err
    return result.stdout.strip()


def _git_head(repo: Path) -> str | None:
    """Commit that HEAD names in the repository at repo, or None if repo is not a git repository.

    --git-dir is explicit, so a directory without its own .git is never mistaken for part of this
    repository.
    """
    git_dir = repo / ".git"
    if not git_dir.exists():
        return None
    try:
        return _git(["--git-dir", str(git_dir), "rev-parse", "HEAD"])
    except VendorError:
        return None


def checkout_dir(upstream: Upstream) -> Path:
    """Checkout directory of upstream, e.g. .cache/vendor/blender-v5.2.2 for cycles."""
    suffix = upstream.tag or upstream.commit[:SHORT_SHA_LEN]
    return CHECKOUT_DIR / f"{CHECKOUT_PREFIX[upstream.name]}-{suffix}"


def _clone_tag(upstream: Upstream, dest: Path) -> None:
    """Shallow, blobless, sparse clone of a tag into the empty directory dest.

    The sparse set is the upstream root, so only that part of the repository is materialised.
    """
    _git(
        [
            "clone",
            "--depth",
            SHALLOW_DEPTH,
            "--branch",
            upstream.tag,
            "--filter=blob:none",
            "--sparse",
            upstream.repo,
            str(dest),
        ]
    )
    if upstream.root:
        _git(["sparse-checkout", "set", upstream.root], cwd=dest)


def _fetch_commit(upstream: Upstream, dest: Path) -> None:
    """Shallow fetch of a bare commit into a new repository at dest, checked out detached."""
    _git(["init", "--quiet", str(dest)])
    _git(["fetch", "--depth", SHALLOW_DEPTH, upstream.repo, upstream.commit], cwd=dest)
    _git(["checkout", "--quiet", "--detach", "FETCH_HEAD"], cwd=dest)


def ensure_checkout(upstream: Upstream) -> Path:
    """Checkout of upstream at its pinned commit, fetched when absent.

    A checkout already at the pin is left alone. A new checkout is built in a scratch directory and
    renamed into place, so an interrupted fetch leaves no partial checkout. A directory at the
    checkout path that is not at the pin raises VendorError and is never overwritten. Returns the
    checkout directory; the upstream root is `root` inside it.
    """
    target = checkout_dir(upstream)
    if target.exists():
        head = _git_head(target)
        if head != upstream.commit:
            raise VendorError(
                f"{target} is at {head or 'no git commit'}, not the pinned {upstream.commit}; "
                "delete it and rerun fetch"
            )
        _report(f"{upstream.name}: {target.name} already at {upstream.commit}")
    else:
        CHECKOUT_DIR.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".{target.name}-", dir=CHECKOUT_DIR))
        try:
            if upstream.tag:
                _clone_tag(upstream, staging)
            else:
                _fetch_commit(upstream, staging)
            head = _git_head(staging)
            if head != upstream.commit:
                raise VendorError(
                    f"{upstream.name}: fetched HEAD {head or 'none'} differs from the pin "
                    f"{upstream.commit}"
                )
            os.replace(staging, target)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        _report(f"{upstream.name}: fetched {target.name} at {upstream.commit}")
    if upstream.root and not (target / upstream.root).is_dir():
        raise VendorError(f"{upstream.name}: root {upstream.root!r} is missing from {target}")
    return target


def source_roots(manifest: Manifest, names: Iterable[str]) -> dict[str, Path]:
    """Root directory of each named upstream (its checkout plus `root`).

    Checkouts that are absent are fetched first.
    """
    roots: dict[str, Path] = {}
    for name in sorted(set(names)):
        upstream = manifest.upstreams[name]
        checkout = ensure_checkout(upstream)
        roots[name] = checkout / upstream.root if upstream.root else checkout
    return roots


def patch_files() -> list[Path]:
    """The patches in patches/, in lexical order, which is the order that sync applies them."""
    return sorted(PATCH_DIR.glob(PATCH_GLOB))


def patch_targets(patches: Iterable[Path]) -> set[str]:
    """Vendor-relative paths that the patches modify, from their `--- a/` and `+++ b/` headers."""
    targets: set[str] = set()
    for patch in patches:
        for line in patch.read_text(encoding="utf-8").splitlines():
            if line.startswith(("--- a/", "+++ b/")):
                targets.add(line.split("/", 1)[1].split("\t", 1)[0])
    return targets


def _derive(manifest: Manifest, roots: Mapping[str, Path], staging: Path) -> list[Entry]:
    """Build the vendored tree inside staging; return the entries with hashes and `patched` filled.

    Each upstream file is copied in, then the patches are applied in lexical order. staging becomes
    its own git repository first. git apply run from inside this repository resolves patch paths
    against the repository top and silently skips the patches, so the patches must be applied in a
    repository of their own.
    """
    _git(["init", "--quiet", str(staging)])
    upstream_hashes: dict[str, str] = {}
    for entry in manifest.entries:
        root = roots[entry.upstream]
        source = root / entry.upstream_path
        if not source.is_file():
            raise VendorError(
                f"{entry.upstream_path} is not a file in upstream {entry.upstream} ({root})"
            )
        data = source.read_bytes()
        target = staging / entry.dest
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        upstream_hashes[entry.dest] = _sha256(data)
    patches = patch_files()
    targets = patch_targets(patches)
    unlisted = targets - {entry.dest for entry in manifest.entries}
    if unlisted:
        raise VendorError(f"patches/ modify files that are not vendored: {sorted(unlisted)}")
    for patch in patches:
        _git(["apply", str(patch)], cwd=staging)
    return [
        Entry(
            upstream=entry.upstream,
            upstream_path=entry.upstream_path,
            dest=entry.dest,
            upstream_sha256=upstream_hashes[entry.dest],
            sha256=_sha256((staging / entry.dest).read_bytes()),
            patched=entry.dest in targets,
        )
        for entry in manifest.entries
    ]


def sync_manifest(manifest: Manifest) -> Manifest:
    """Re-derive every entry, copy the results into third_party/cycles/, rewrite VENDORED.toml.

    Nothing under third_party/cycles/ changes unless every entry derives cleanly. Files on disk that
    no entry lists are left alone; `check` reports them.
    """
    check_structure(manifest)
    roots = source_roots(manifest, (entry.upstream for entry in manifest.entries))
    CHECKOUT_DIR.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".sync-", dir=CHECKOUT_DIR))
    try:
        entries = _derive(manifest, roots, staging)
        for entry in entries:
            target = VENDOR_DIR / entry.dest
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((staging / entry.dest).read_bytes())
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    result = Manifest(manifest.upstreams, entries)
    MANIFEST.write_bytes(render_manifest(result).encode("utf-8"))
    return result


def offline_problems(manifest: Manifest) -> list[str]:
    """Differences between third_party/cycles and the manifest, found without network access.

    Covers missing and unlisted files, sha256 mismatches, `patched` flags that disagree with
    patches/, patched files without MODIFIED_NOTICE, and patches that modify unlisted files.
    """
    problems: list[str] = []
    listed = {entry.dest for entry in manifest.entries}
    for entry in manifest.entries:
        path = VENDOR_DIR / entry.dest
        if not path.is_file():
            problems.append(f"{entry.dest}: listed in VENDORED.toml but missing")
            continue
        data = path.read_bytes()
        if _sha256(data) != entry.sha256:
            problems.append(
                f"{entry.dest}: sha256 {_sha256(data)} differs from VENDORED.toml {entry.sha256}"
            )
        if entry.patched and MODIFIED_NOTICE.encode("utf-8") not in data:
            problems.append(f"{entry.dest}: patched but lacks the notice {MODIFIED_NOTICE!r}")
    for path in sorted(VENDOR_DIR.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(VENDOR_DIR).as_posix()
        if relative in UNLISTED_FILES or relative.split("/", 1)[0] == PATCH_DIR.name:
            continue
        if relative not in listed:
            problems.append(f"{relative}: on disk but not listed in VENDORED.toml")
    targets = patch_targets(patch_files())
    for entry in manifest.entries:
        if (entry.dest in targets) != entry.patched:
            problems.append(
                f"{entry.dest}: patched={str(entry.patched).lower()} in VENDORED.toml, "
                "but patches/ say otherwise"
            )
    for dest in sorted(targets - listed):
        problems.append(f"patches/ modify {dest}, which is not listed in VENDORED.toml")
    return problems


def upstream_problems(manifest: Manifest) -> list[str]:
    """Differences found by re-deriving every entry from its upstream checkout and patches.

    The comparison is byte for byte, and it covers both hashes and the `patched` flag.
    """
    roots = source_roots(manifest, (entry.upstream for entry in manifest.entries))
    CHECKOUT_DIR.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".check-", dir=CHECKOUT_DIR))
    problems: list[str] = []
    try:
        derived = _derive(manifest, roots, staging)
        for recorded, fresh in zip(manifest.entries, derived, strict=True):
            if fresh.upstream_sha256 != recorded.upstream_sha256:
                problems.append(
                    f"{recorded.dest}: upstream sha256 {fresh.upstream_sha256} differs from "
                    f"VENDORED.toml {recorded.upstream_sha256}"
                )
            if fresh.sha256 != recorded.sha256:
                problems.append(
                    f"{recorded.dest}: re-derived sha256 {fresh.sha256} differs from "
                    f"VENDORED.toml {recorded.sha256}"
                )
            if fresh.patched != recorded.patched:
                problems.append(
                    f"{recorded.dest}: re-derived patched flag differs from VENDORED.toml"
                )
            vendored = VENDOR_DIR / recorded.dest
            if (
                vendored.is_file()
                and vendored.read_bytes() != (staging / recorded.dest).read_bytes()
            ):
                problems.append(f"{recorded.dest}: bytes differ from the re-derivation")
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    return problems


def _resolve_include(root: Path, including: str, include: str) -> str | None:
    """Root-relative path that `#include "include"` in the file `including` resolves to, or None.

    The C preprocessor searches the including file's own directory first, then the include path,
    which here is root.
    """
    for candidate in (posixpath.join(posixpath.dirname(including), include), include):
        normal = posixpath.normpath(candidate)
        if normal == ".." or normal.startswith(("../", "/")):
            continue
        if (root / normal).is_file():
            return normal
    return None


def include_closure(root: Path, seeds: Iterable[str]) -> tuple[set[str], set[tuple[str, str]]]:
    """Transitive closure of the quoted #include lines reachable from seeds inside root.

    Returns (files, missing). files are root-relative POSIX paths, seeds included. missing holds
    (include text, including file) pairs for quoted includes that resolve to no file under root,
    and (seed, "command line") for seeds that are absent. These are the shim candidates.
    Conditional blocks are not evaluated, so every #include line counts.
    """
    files: set[str] = set()
    missing: set[tuple[str, str]] = set()
    pending: deque[str] = deque()
    for seed in seeds:
        relative = _rel_path(seed, "header")
        if (root / relative).is_file():
            if relative not in files:
                files.add(relative)
                pending.append(relative)
        else:
            missing.add((relative, "command line"))
    while pending:
        current = pending.popleft()
        text = (root / current).read_bytes().decode("utf-8", errors="replace")
        for match in INCLUDE_RE.finditer(text):
            include = match.group(1)
            found = _resolve_include(root, current, include)
            if found is None:
                missing.add((include, current))
            elif found not in files:
                files.add(found)
                pending.append(found)
    return files, missing


def _require(manifest: Manifest, name: str) -> None:
    """Raise VendorError unless the upstream name is pinned in VENDORED.toml."""
    if name not in manifest.upstreams:
        raise VendorError(f"upstream {name!r} is not pinned in VENDORED.toml")


def _prune_empty_dirs(directory: Path) -> None:
    """Remove directory and its empty ancestors, stopping at VENDOR_DIR."""
    while directory != VENDOR_DIR and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent


def cmd_fetch() -> int:
    """Check out every pinned upstream; a checkout already at its pin is left alone."""
    manifest = load_manifest()
    source_roots(manifest, manifest.upstreams)
    return 0


def cmd_sync() -> int:
    """Regenerate third_party/cycles from the checkouts and patches, then rewrite VENDORED.toml."""
    manifest = sync_manifest(load_manifest())
    print(f"synced {len(manifest.entries)} vendored files; rewrote {_shown(MANIFEST)}")
    return 0


def cmd_check(upstream: bool) -> int:
    """Verify the tree against the manifest; with upstream, also re-derive every file."""
    manifest = load_manifest()
    problems = offline_problems(manifest)
    if upstream:
        problems += upstream_problems(manifest)
    for problem in problems:
        print(f"vendor-check: {problem}", file=sys.stderr)
    if problems:
        return 1
    scope = " and re-derivation from upstream" if upstream else ""
    print(f"vendor-check: {len(manifest.entries)} vendored files match {_shown(MANIFEST)}{scope}")
    return 0


def cmd_add(upstream: str, upstream_paths: list[str], dest_prefix: str | None) -> int:
    """Append entries for upstream_paths to VENDORED.toml, then sync.

    Every file is checked before anything is written.
    """
    manifest = load_manifest()
    _require(manifest, upstream)
    prefix = None if dest_prefix is None else _rel_path(dest_prefix, "--dest-prefix")
    roots = source_roots(manifest, [upstream])
    taken = {entry.dest for entry in manifest.entries}
    added: list[Entry] = []
    for path in upstream_paths:
        upstream_path = _rel_path(path, "upstream_path")
        name = posixpath.basename(upstream_path)
        dest = upstream_path if prefix is None else f"{prefix}/{name}"
        if dest in taken:
            raise VendorError(f"{dest} is already vendored")
        if (VENDOR_DIR / dest).exists():
            raise VendorError(f"{dest} exists under third_party/cycles/ but is not vendored")
        if not (roots[upstream] / upstream_path).is_file():
            raise VendorError(
                f"{upstream_path} is not a file in upstream {upstream} ({roots[upstream]})"
            )
        taken.add(dest)
        added.append(Entry(upstream=upstream, upstream_path=upstream_path, dest=dest))
    manifest = sync_manifest(Manifest(manifest.upstreams, [*manifest.entries, *added]))
    for entry in added:
        print(f"added {entry.dest} (from {entry.upstream}:{entry.upstream_path})")
    print(f"synced {len(manifest.entries)} vendored files; rewrote {_shown(MANIFEST)}")
    return 0


def cmd_remove(dests: list[str]) -> int:
    """Drop the entries for dests, sync the rest, then delete the removed files.

    A file that a patch modifies is refused; delete that patch first.
    """
    manifest = load_manifest()
    wanted = {_rel_path(dest, "dest") for dest in dests}
    listed = {entry.dest for entry in manifest.entries}
    for dest in sorted(wanted):
        if dest not in listed:
            raise VendorError(f"{dest} is not vendored")
    touched = patch_targets(patch_files())
    for dest in sorted(wanted):
        if dest in touched:
            raise VendorError(f"patches/ modify {dest}; delete that patch before removing it")
    kept = [entry for entry in manifest.entries if entry.dest not in wanted]
    manifest = sync_manifest(Manifest(manifest.upstreams, kept))
    for dest in sorted(wanted):
        path = VENDOR_DIR / dest
        path.unlink(missing_ok=True)
        _prune_empty_dirs(path.parent)
        print(f"removed {dest}")
    print(f"synced {len(manifest.entries)} vendored files; rewrote {_shown(MANIFEST)}")
    return 0


def cmd_closure(seeds: list[str]) -> int:
    """Print the #include closure of seeds inside the cycles root.

    stdout: a `# closure:` line, one root-relative path per file, then `# missing:` lines. Missing
    headers are not an error (they are shim candidates), so the exit status is 0 whenever the
    closure could be computed.
    """
    manifest = load_manifest()
    _require(manifest, CYCLES)
    root = source_roots(manifest, [CYCLES])[CYCLES]
    files, missing = include_closure(root, seeds)
    print(f"# closure: {len(files)} files under {manifest.upstreams[CYCLES].root}")
    for relative in sorted(files):
        print(relative)
    print(f"# missing: {len(missing)}")
    for include, source in sorted(missing):
        print(f'#   #include "{include}" in {source}')
    return 0


def _shown(path: Path) -> str:
    """Path of a file relative to the repository root, for messages."""
    return path.relative_to(REPO_ROOT).as_posix()


def build_parser() -> argparse.ArgumentParser:
    """The command-line interface. The module docstring says what each subcommand does."""
    parser = argparse.ArgumentParser(
        prog="vendor_sync.py",
        description="Pinned, hash-checked vendoring of Cycles sources into third_party/cycles/.",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    commands.add_parser(
        "fetch", help="check out each upstream at its pinned commit under .cache/vendor/"
    )
    commands.add_parser(
        "sync", help="regenerate third_party/cycles from the checkouts and patches/"
    )
    check = commands.add_parser("check", help="verify third_party/cycles against VENDORED.toml")
    check.add_argument(
        "--upstream",
        action="store_true",
        help="also re-derive every file from its checkout and patches (needs the checkouts)",
    )
    add = commands.add_parser("add", help="vendor upstream files, then sync")
    add.add_argument(
        "--upstream", default=DEFAULT_UPSTREAM, help=f"upstream name (default: {DEFAULT_UPSTREAM})"
    )
    add.add_argument("--dest-prefix", metavar="P", help="vendor each file as P/<file name>")
    add.add_argument(
        "upstream_paths",
        nargs="+",
        metavar="upstream_path",
        help="path relative to the upstream root",
    )
    remove = commands.add_parser(
        "remove", help="delete vendored files and their entries, then sync"
    )
    remove.add_argument(
        "dests", nargs="+", metavar="dest", help="vendored path relative to third_party/cycles/"
    )
    closure = commands.add_parser(
        "closure", help="print the #include closure of headers in the cycles root"
    )
    closure.add_argument(
        "seeds", nargs="+", metavar="header", help="root-relative header, e.g. util/hash.h"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one subcommand and return its exit status."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "fetch":
            return cmd_fetch()
        if args.command == "sync":
            return cmd_sync()
        if args.command == "check":
            return cmd_check(args.upstream)
        if args.command == "add":
            return cmd_add(args.upstream, args.upstream_paths, args.dest_prefix)
        if args.command == "remove":
            return cmd_remove(args.dests)
        return cmd_closure(args.seeds)
    except VendorError as err:
        print(f"vendor_sync: error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
