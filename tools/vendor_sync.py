#!/usr/bin/env python3
"""Pinned, hash-checked vendoring of Cycles into third_party/cycles/ (T3.1; CLAUDE.md rule 1).

Subcommands (paths in the manifest are relative to each upstream's `root`):

  fetch                       check out every upstream at its pinned commit under .cache/vendor/
  sync                        copy each VENDORED.toml entry from its pinned commit, apply
                              patches/*.patch in lexical order, and rewrite VENDORED.toml with the
                              resulting hashes
  check [--upstream]          verify third_party/cycles against VENDORED.toml with no network;
                              with --upstream also re-derive every file from its pinned commit and
                              patches, byte for byte
  add [--upstream NAME] PATH... [--dest-prefix P]
                              vendor upstream files (dest = PATH, or P/<file name> with
                              --dest-prefix), then sync
  remove DEST...              delete the entries and their files, then sync
  closure HEADER...           print the transitive quoted-#include closure of HEADERs inside the
                              cycles root
  add-fragment [--upstream NAME] UPSTREAM_PATH KIND [ANCHOR ...] [--params TEXT]
               [--id ID --begin TEXT --end TEXT]
                              vendor verbatim extracts ("fragments") of an upstream file as
                              [[fragment]] entries, writing third_party/cycles/fragments/<name>.inc
  remove-fragment NAME...     delete these fragments' entries, their .inc files and the directories
                              left empty under fragments/
  extract [--upstream NAME] UPSTREAM_PATH KIND [ANCHOR] [--params TEXT]
          [--begin TEXT --end TEXT]
                              print one fragment's text on stdout and its line range and sha256 on
                              stderr; writes nothing
  list-anchors [--upstream NAME] UPSTREAM_PATH
                              print every anchor of a file that extract resolves, one per line

Upstream bytes come from the pinned commit's git objects (`git cat-file blob <commit>:<path>`,
file lists from `git ls-tree`), never from a checkout's working tree (T3.27, M3 review panel #0).
So a locally edited, deleted or untracked file in a checkout, or end-of-line conversion at checkout
(`core.autocrlf`, `.gitattributes`), cannot reach third_party/cycles or its hashes, and
`check --upstream` compares against the pinned bytes. Every subcommand that reads a checkout
refuses one whose HEAD is not the pinned commit.

Fragments (T6.2) are read the same way: a fragment's text is the blob of `<commit>:<path>` in the
pinned commit, so an edited, deleted or untracked checkout file, or end-of-line conversion at
checkout, changes no fragment byte and no hash either. Each fragment's text is hashed in
VENDORED.toml, so `check` and `sync` catch a changed or truncated extract.

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
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
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
# The exit status of `git rev-parse --verify --quiet` for a revision it does not resolve: a path
# that the commit does not have, or a commit that the object store does not have. Any other status
# is a git failure (git.h, `rev-parse` exits 1 for an unresolvable revision and 128 for an error).
MISSING_REVISION_STATUS = 1
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
# Fragment files of MANIFEST; the Python API uses manifest.parent / "fragments" for any manifest.
FRAGMENT_DIR = VENDOR_DIR / "fragments"
# Key order of a [[fragment]] table in VENDORED.toml; an entry has the subset its kind needs.
FRAGMENT_KEYS = (
    "name",
    "upstream",
    "upstream_path",
    "kind",
    "anchor",
    "params",
    "id",
    "begin",
    "end",
    "upstream_lines",
    "sha256",
)
# Win32 MAX_PATH (an API definition, minwindef.h): 260 characters including the terminating NUL,
# so a path has at most 259. Git for Windows (default core.longpaths=false) and MSVC's include
# lookup fail on longer paths.
WIN32_MAX_PATH = 260
# GITHUB_WORKSPACE of the windows-2022 jobs (.github/workflows/ci.yml job `windows`, wheels.yml),
# plus the separator after it: the root under which CI checks out and compiles the fragments.
WINDOWS_CI_CHECKOUT_ROOT = (
    "D:\\a\\blender-painterly-render-plugin\\blender-painterly-render-plugin\\"
)
# Longest repository-relative path "third_party/cycles/fragments/<name>.inc" (190 characters).
# Fragment names are printable ASCII, so characters, bytes and UTF-16 code units agree.
FRAGMENT_PATH_MAX = WIN32_MAX_PATH - 1 - len(WINDOWS_CI_CHECKOUT_ROOT)
# The anchor kinds of a [[fragment]] entry, and the kinds whose entries may carry `params`.
FRAGMENT_KINDS = ("svm_case", "node_define", "member", "function", "define", "span")
PARAM_KINDS = frozenset({"member", "function"})
# Valid anchor and id texts of a [[fragment]] entry ("Names and files").
IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
MEMBER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(::~?[A-Za-z_][A-Za-z0-9_]*)+")
FRAGMENT_ID_RE = re.compile(r"[A-Za-z0-9_]+")
# The declarator of a top-level line: a qualified name, then "(" or "=" (but not "==").
DECLARATOR_RE = re.compile(
    r"(~?[A-Za-z_][A-Za-z0-9_]*(?:::~?[A-Za-z_][A-Za-z0-9_]*)*)\s*(\(|=(?!=))"
)
NODE_DEFINE_RE = re.compile(r"NODE_DEFINE\(([A-Za-z_][A-Za-z0-9_]*)\)")
SVM_CASE_HEADER_RE = re.compile(r"SVM_CASE\(([A-Za-z_][A-Za-z0-9_]*)\)")
DEFINE_RE = re.compile(r"#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)\b")
# Directive lines that open a conditional, and the ones that end the extent of an svm_case.
IF_DIRECTIVE_RE = re.compile(r"#\s*(if|ifdef|ifndef)\b")
ENDIF_DIRECTIVE_RE = re.compile(r"#\s*endif\b")
CASE_STOP_DIRECTIVE_RE = re.compile(r"#\s*(if|ifdef|ifndef|elif|else|endif)\b")
# The two forms that end an svm_case without falling through into the next one.
CASE_ENDS = ("break;", "return;")
# Git must never prompt for credentials: a missing credential is an error, not a hang.
GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}


class VendorError(Exception):
    """A vendoring step cannot finish. The message names the file or upstream and what failed."""


class FragmentError(VendorError):
    """An anchor that resolves to no single well-formed fragment, or a broken fragment entry."""


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
    """The parsed VENDORED.toml: upstream pins, vendored files and fragment tables.

    `fragments` holds the `[[fragment]]` tables in file order, each the dict `tomllib` read, so
    that a rewrite of the manifest keeps every entry as it was. It defaults to empty so that a
    caller which has no fragments to pass still builds a manifest of T3.1's two fields; every
    call site of this tool passes it explicitly.
    """

    upstreams: dict[str, Upstream]
    entries: list[Entry]
    fragments: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class Fragment:
    """One extracted fragment: its text and the upstream lines it came from."""

    text: str  # The extent's lines, each ending in "\n".
    first_line: int  # 1-based, inclusive.
    last_line: int  # 1-based, inclusive.


@dataclass(frozen=True)
class Anchor:
    """One anchor that resolves to exactly one fragment in a source file."""

    kind: str
    anchor: str  # "" for span.
    params: str  # Parameter text for member/function ("" if none); "" for the other kinds.
    first_line: int
    last_line: int


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

    Hashes are not examined here; `load_manifest` checks their format. Also enforces the three
    rules of the `[[fragment]]` entries, raising FragmentError at the first violation.
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
    check_fragment_rules(manifest)


def _fragment_string(table: Mapping[str, object], key: str) -> str:
    """String value of key in a [[fragment]] table; a missing key or another type is an error."""
    value = table.get(key)
    if not isinstance(value, str):
        raise FragmentError(f"[[fragment]]: the key {key!r} must be a string")
    return value


def _fragment_keys(kind: str) -> tuple[frozenset[str], frozenset[str]]:
    """The keys a [[fragment]] entry of this kind must have, and the ones it may have."""
    base = {"name", "upstream", "upstream_path", "kind", "upstream_lines", "sha256"}
    if kind == "span":
        required = frozenset(base | {"id", "begin", "end"})
        return required, required
    # `params` is present only when the anchor was selected with it: a member or a function.
    required = frozenset(base | {"anchor"})
    return required, frozenset(required | ({"params"} if kind in PARAM_KINDS else set()))


def _printable_ascii(value: str) -> bool:
    """True when every character of value is printable ASCII (U+0020-U+007E)."""
    return all(" " <= character <= "~" for character in value)


def _fragment_lines(table: Mapping[str, object]) -> tuple[int, int]:
    """The two integers of upstream_lines, checked for type, order and booleans."""
    value = table.get("upstream_lines")
    if not isinstance(value, list) or len(value) != 2:
        raise FragmentError("[[fragment]]: upstream_lines must be a list of two integers")
    first, last = value
    for number in (first, last):
        # bool is an int subclass in Python, but `true` is not a line number.
        if not isinstance(number, int) or isinstance(number, bool):
            raise FragmentError("[[fragment]]: upstream_lines must be a list of two integers")
    if not 1 <= first <= last:
        raise FragmentError(
            f"[[fragment]]: upstream_lines [{first}, {last}] must satisfy 1 <= first <= last"
        )
    return first, last


def check_fragment_rules(manifest: Manifest) -> None:
    """Enforce rules 1-3 of the [[fragment]] entries, raising FragmentError at the first violation.

    Rule 1: each entry has a known kind, exactly that kind's keys, a pinned upstream, a canonical
    path, a valid anchor or id, an in-order line range, a SHA-256 digest, printable-ASCII strings
    and the name its fields give. Names are unique. Rule 2: the fragments of one upstream file do
    not overlap. Rule 3: no upstream file is both vendored whole and fragmented.
    """
    names: set[str] = set()
    ranges: dict[tuple[str, str], list[tuple[int, int, str]]] = {}
    whole = {(entry.upstream, entry.upstream_path) for entry in manifest.entries}
    for table in manifest.fragments:
        if not isinstance(table, dict):
            raise FragmentError("VENDORED.toml: every [[fragment]] table must be a table")
        kind = table.get("kind")
        if not isinstance(kind, str) or kind not in FRAGMENT_KINDS:
            raise FragmentError(
                f"[[fragment]]: unknown kind {kind!r}; known kinds: {list(FRAGMENT_KINDS)}"
            )
        required, allowed = _fragment_keys(kind)
        extra = sorted(set(table) - allowed)
        missing = sorted(required - set(table))
        if extra or missing:
            raise FragmentError(
                f"[[fragment]] {table.get('name')!r}: kind {kind!r} takes {sorted(required)}"
                f" and may take {sorted(allowed - required)}; missing {missing},"
                f" unexpected {extra}"
            )
        for key, value in table.items():
            if isinstance(value, str) and not _printable_ascii(value):
                raise FragmentError(
                    f"[[fragment]] {table.get('name')!r}: {key} has a character outside"
                    " printable ASCII"
                )
        name = _fragment_string(table, "name")
        upstream_name = _fragment_string(table, "upstream")
        if upstream_name not in manifest.upstreams:
            raise FragmentError(
                f"[[fragment]] {name}: upstream {upstream_name!r} is not in VENDORED.toml"
            )
        try:
            upstream_path = _rel_path(
                _fragment_string(table, "upstream_path"), f"[[fragment]] {name}: upstream_path"
            )
        except VendorError as err:
            raise FragmentError(str(err)) from err
        if kind == "span":
            fragment_id = _fragment_string(table, "id")
            if FRAGMENT_ID_RE.fullmatch(fragment_id) is None:
                raise FragmentError(f"[[fragment]] {name}: id {fragment_id!r} is not a valid id")
            anchor = None
            params = None
            for key in ("begin", "end"):
                if not _fragment_string(table, key):
                    raise FragmentError(f"[[fragment]] {name}: {key} must not be empty")
        else:
            anchor = _fragment_string(table, "anchor")
            pattern = MEMBER_RE if kind == "member" else IDENTIFIER_RE
            if pattern.fullmatch(anchor) is None:
                raise FragmentError(f"[[fragment]] {name}: anchor {anchor!r} is not a valid {kind}")
            # `params` is optional: present only when the anchor was selected with it (T6.2,
            # "Rules": "a valid anchor (with `params` a string, if present) or a valid id").
            params = (
                _fragment_string(table, "params")
                if kind in PARAM_KINDS and "params" in table
                else None
            )
            fragment_id = None
        first, last = _fragment_lines(table)
        digest = _fragment_string(table, "sha256")
        if not _is_hex(digest, SHA256_HEX_LEN):
            raise FragmentError(f"[[fragment]] {name}: {digest!r} is not a SHA-256 hex digest")
        expected = fragment_name(
            upstream_path, kind, anchor, params=params, fragment_id=fragment_id
        )
        if name != expected:
            raise FragmentError(f"[[fragment]] {name}: the name its fields give is {expected!r}")
        if name in names:
            raise FragmentError(f"[[fragment]] {name}: the name is used twice")
        names.add(name)
        if (upstream_name, upstream_path) in whole:
            raise FragmentError(
                f"[[fragment]] {name}: {upstream_name}:{upstream_path} is vendored whole and"
                " fragmented; vendor a file whole or as fragments, never both"
            )
        ranges.setdefault((upstream_name, upstream_path), []).append((first, last, name))
    for (upstream_name, upstream_path), spans in ranges.items():
        spans.sort()
        for (_, earlier_last, earlier_name), (later_first, _, later_name) in zip(
            spans, spans[1:], strict=False
        ):
            if later_first <= earlier_last:
                raise FragmentError(
                    f"[[fragment]] {later_name}: its lines {later_first}-... overlap"
                    f" {earlier_name} ({upstream_name}:{upstream_path})"
                )


def load_manifest(path: Path | None = None) -> Manifest:
    """Parse and validate VENDORED.toml, including the SHA-256 format of every recorded hash.

    path defaults to MANIFEST, looked up when the function runs (so tests can point MANIFEST at
    a temporary file). Raises VendorError when the file cannot be read, a key is missing or
    malformed, or the structure is invalid; the [[fragment]] rules raise FragmentError.
    """
    if path is None:
        path = MANIFEST
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
    manifest = Manifest(upstreams, entries, data.get("fragment", []))
    check_structure(manifest)
    for entry in entries:
        for digest in (entry.upstream_sha256, entry.sha256):
            if not _is_hex(digest, SHA256_HEX_LEN):
                raise VendorError(f"{path}: {entry.dest}: {digest!r} is not a SHA-256 hex digest")
    return manifest


def _render_fragment(table: Mapping[str, object]) -> list[str]:
    """The lines of one [[fragment]] table: `[[fragment]]`, then its keys in FRAGMENT_KEYS order."""
    lines = ["[[fragment]]"]
    for key in FRAGMENT_KEYS:
        if key not in table:
            continue
        value = table[key]
        if key == "upstream_lines":
            first, last = value
            lines.append(f"upstream_lines = [{first}, {last}]")
        else:
            lines.append(f"{key} = {_toml(value)}")
    return lines


def render_manifest(manifest: Manifest) -> str:
    """The VENDORED.toml text: the header, the upstream tables, then [[file]] and [[fragment]]s."""
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
    for table in manifest.fragments:
        lines += ["", *_render_fragment(table)]
    return "\n".join(lines) + "\n"


def _git_bytes(args: list[str], cwd: Path | None = None) -> bytes:
    """Run git with args and return its stdout exactly as git wrote it.

    A failing git command raises VendorError carrying git's own error text.
    """
    command = ["git", *args]
    try:
        result = subprocess.run(command, cwd=cwd, env=GIT_ENV, check=True, capture_output=True)
    except subprocess.CalledProcessError as err:
        stderr = err.stderr.decode("utf-8", errors="replace").strip()
        raise VendorError(f"{' '.join(command)} failed: {stderr}") from err
    except OSError as err:
        raise VendorError(f"cannot run git: {err}") from err
    return result.stdout


def _git_optional(args: list[str], cwd: Path | None = None) -> bytes | None:
    """git's stdout, or None when git reports that the requested revision or path does not exist.

    A missing entry is the exit status that `rev-parse --verify --quiet` gives for an unknown path
    in a known commit, or for an unknown commit. Every other failure (a directory that is not a
    repository, a corrupt or incomplete object store) raises VendorError carrying git's own error
    text, so a broken checkout is never reported as a missing path (TQ.3 F27).
    """
    command = ["git", *args]
    try:
        result = subprocess.run(command, cwd=cwd, env=GIT_ENV, check=False, capture_output=True)
    except OSError as err:
        raise VendorError(f"cannot run git: {err}") from err
    if result.returncode == 0:
        return result.stdout
    if result.returncode == MISSING_REVISION_STATUS:
        return None
    stderr = result.stderr.decode("utf-8", errors="replace").strip()
    raise VendorError(f"{' '.join(command)} failed: {stderr}")


def _git(args: list[str], cwd: Path | None = None) -> str:
    """Run git with args and return its stdout as UTF-8 text, stripped of surrounding whitespace.

    A failing git command raises VendorError carrying git's own error text.
    """
    return _git_bytes(args, cwd).decode("utf-8").strip()


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


def _require_pin(upstream: Upstream, checkout: Path) -> None:
    """Raise VendorError unless the checkout's HEAD is upstream's pinned commit.

    `ensure_checkout` and `_fragment_source` both read a checkout, and both refuse one that is not
    at its pin with this message, so a reader never sees another commit's bytes.
    """
    head = _git_head(checkout)
    if head != upstream.commit:
        raise VendorError(
            f"{checkout} is at {head or 'no git commit'}, not the pinned {upstream.commit}; "
            "delete it and rerun fetch"
        )


def checkout_dir(upstream: Upstream) -> Path:
    """Checkout directory of upstream, e.g. .cache/vendor/blender-v5.2.2 for cycles."""
    suffix = upstream.tag or upstream.commit[:SHORT_SHA_LEN]
    return CHECKOUT_DIR / f"{CHECKOUT_PREFIX[upstream.name]}-{suffix}"


def _object_spec(upstream: Upstream, path: str = "") -> str:
    """The git revision `<commit>:<repository path>` of a root-relative path in the pinned commit.

    The empty path names the upstream root itself: `<commit>:intern/cycles` for cycles, and the
    commit's top tree `<commit>:` when the root is the repository root.
    """
    in_repository = "/".join(part for part in (upstream.root, path) if part)
    return f"{upstream.commit}:{in_repository}"


def _object_type(checkout: Path, spec: str) -> str | None:
    """Type ("blob", "tree", ...) of the object that the revision spec names, or None if none.

    Only the object store of the checkout's own repository (its .git) is read. A revision that
    names no path in a known commit gives None. A git failure that is not a missing path — a
    directory that is not a repository, a corrupt or incomplete object store — raises VendorError
    carrying git's own error text, so it is never reported as a path that upstream lacks (TQ.3
    F27): `rev-parse --verify` tells a missing path (its status MISSING_REVISION_STATUS) from such
    a failure, and the object itself is then read from the object store.
    """
    git_dir = str(checkout / ".git")
    oid = _git_optional(["--git-dir", git_dir, "rev-parse", "--verify", "--quiet", spec])
    if oid is None:
        return None
    return _git(["--git-dir", git_dir, "cat-file", "-t", oid.decode("utf-8").strip()])


def _missing_file(upstream: Upstream, path: str) -> VendorError:
    """The error for a root-relative path that is not a file in upstream's pinned commit."""
    return VendorError(f"{path} is not a file in upstream {upstream.name} at {upstream.commit}")


def upstream_files(upstream: Upstream, checkout: Path) -> frozenset[str]:
    """Root-relative paths of every file under upstream's root in its pinned commit.

    The list comes from the commit's tree objects (`git ls-tree -r`), not from the working tree,
    so an untracked or deleted working-tree file changes nothing. Directories are not listed.
    """
    listing = _git_bytes(
        ["--git-dir", str(checkout / ".git"), "ls-tree", "-r", "-z", _object_spec(upstream)]
    )
    files: set[str] = set()
    for record in listing.split(b"\0"):
        if not record:
            continue
        # One record per entry: "<mode> <type> <object id>\t<path>" (git ls-tree -z).
        info, _, name = record.partition(b"\t")
        if info.split(b" ")[1] == b"blob":
            files.add(name.decode("utf-8"))
    return frozenset(files)


def upstream_blob(upstream: Upstream, checkout: Path, path: str) -> bytes:
    """Bytes of the root-relative path in upstream's pinned commit, from the checkout's git objects.

    `git cat-file blob` prints the stored object unchanged: no working-tree file is read, and no
    end-of-line conversion or other checkout filter applies. Raises VendorError when the pinned
    commit has no file at path.
    """
    spec = _object_spec(upstream, path)
    if _object_type(checkout, spec) != "blob":
        raise _missing_file(upstream, path)
    return _git_bytes(["--git-dir", str(checkout / ".git"), "cat-file", "blob", spec])


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
    checkout directory, the repository top. Callers read upstream files from its git objects
    (upstream_files, upstream_blob), never from its working tree.
    """
    target = checkout_dir(upstream)
    if target.exists():
        _require_pin(upstream, target)
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
    if upstream.root and _object_type(target, _object_spec(upstream)) != "tree":
        raise VendorError(
            f"{upstream.name}: root {upstream.root!r} is not a directory in {upstream.commit}"
        )
    return target


def source_checkouts(manifest: Manifest, names: Iterable[str]) -> dict[str, Path]:
    """Checkout directory of each named upstream, as ensure_checkout returns it.

    Checkouts that are absent are fetched first.
    """
    return {name: ensure_checkout(manifest.upstreams[name]) for name in sorted(set(names))}


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


def _derive(manifest: Manifest, checkouts: Mapping[str, Path], staging: Path) -> list[Entry]:
    """Build the vendored tree inside staging; return the entries with hashes and `patched` filled.

    checkouts maps each upstream name to its checkout (source_checkouts). Each upstream file is
    written in from its pinned commit (upstream_blob), then the patches are applied in lexical
    order. staging becomes its own git repository first. git apply run from inside this
    repository resolves patch paths against the repository top and silently skips the patches, so
    the patches must be applied in a repository of their own.
    """
    _git(["init", "--quiet", str(staging)])
    upstream_hashes: dict[str, str] = {}
    for entry in manifest.entries:
        upstream = manifest.upstreams[entry.upstream]
        data = upstream_blob(upstream, checkouts[entry.upstream], entry.upstream_path)
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
    checkouts = source_checkouts(manifest, (entry.upstream for entry in manifest.entries))
    CHECKOUT_DIR.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".sync-", dir=CHECKOUT_DIR))
    try:
        entries = _derive(manifest, checkouts, staging)
        for entry in entries:
            target = VENDOR_DIR / entry.dest
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((staging / entry.dest).read_bytes())
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    result = Manifest(manifest.upstreams, entries, manifest.fragments)
    MANIFEST.write_bytes(render_manifest(result).encode("utf-8"))
    return result


def offline_problems(manifest: Manifest) -> list[str]:
    """Differences between third_party/cycles and the manifest, found without network access.

    Covers missing and unlisted files, sha256 mismatches, `patched` flags that disagree with
    patches/, patched files without MODIFIED_NOTICE, and patches that modify unlisted files.
    Fragments are `check_fragments`' business, so files under fragments/ are skipped here.
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
        if relative in UNLISTED_FILES or relative.split("/", 1)[0] in (
            PATCH_DIR.name,
            FRAGMENT_DIR.name,
        ):
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
    """Differences found by re-deriving every entry from its pinned commit and patches.

    The comparison is byte for byte, and it covers both hashes and the `patched` flag.
    """
    checkouts = source_checkouts(manifest, (entry.upstream for entry in manifest.entries))
    CHECKOUT_DIR.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".check-", dir=CHECKOUT_DIR))
    problems: list[str] = []
    try:
        derived = _derive(manifest, checkouts, staging)
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


# --- Fragments (T6.2) ------------------------------------------------------
#
# A fragment is a verbatim extract of the part of an upstream file that M6a does not vendor
# whole. An anchor locates it; line numbers are recorded but never used to find code. The
# grammar is the card's "Lexing" and "Anchor kinds" sections.


@dataclass(frozen=True)
class _Line:
    """One line of a source file, as "Lexing" reads it."""

    text: str  # The raw line, without its "\n".
    code: str  # The line with each comment and literal replaced by one space.
    preprocessor: bool  # A preprocessor line, which is not lexed further.
    directive: bool  # The first line of a run of preprocessor lines.
    starts_in_comment: bool  # The line begins inside a block comment.
    depth: int  # The brace depth before this line.
    opens: int  # The number of open preprocessor conditionals before this line.
    top_level: bool  # Depth 0, not preprocessor, not in a comment, not indented, not empty.


@dataclass(frozen=True)
class _Lexed:
    """A lexed source file: its lines, and the depth and conditional count after the last one."""

    lines: list[_Line]
    depth_end: int
    opens_end: int


class _Sources:
    """Lexed upstream files, read from their pinned commits and lexed once each per command."""

    def __init__(self, manifest: Manifest, checkouts: Mapping[str, Path]) -> None:
        self.manifest = manifest
        self.checkouts = checkouts
        self.lexed: dict[tuple[str, str], _Lexed] = {}

    def get(self, upstream: str, upstream_path: str) -> _Lexed:
        """The lexed blob of `<upstream's pinned commit>:<root>/<upstream_path>`."""
        key = (upstream, upstream_path)
        if key not in self.lexed:
            text = _fragment_source(self.manifest, self.checkouts, upstream, upstream_path)
            self.lexed[key] = _lex(text)
        return self.lexed[key]


def _source_lines(text: str) -> list[str]:
    """The pieces of text.split("\\n"), without the empty piece after a final "\\n"."""
    pieces = text.split("\n")
    if pieces and pieces[-1] == "":
        pieces.pop()
    return pieces


def _strip_comments(text: str, in_block: bool) -> tuple[str, bool]:
    """text with each comment and literal replaced by one space, and the block-comment state after.

    One left-to-right scan, so a `//` inside a literal and a quote inside a comment are ordinary
    characters: upstream comments contain apostrophes, which a literals-first pass would read as
    the start of a character literal. A literal that does not close on its line raises
    FragmentError.
    """
    pieces: list[str] = []
    index = 0
    length = len(text)
    if in_block:
        pieces.append(" ")  # The part of the block comment that is on this line.
    while index < length:
        if in_block:
            end = text.find("*/", index)
            if end < 0:
                return "".join(pieces), True
            index = end + 2
            in_block = False
            continue
        if text.startswith("/*", index):
            pieces.append(" ")
            index += 2
            in_block = True
            continue
        if text.startswith("//", index):
            pieces.append(" ")
            break
        character = text[index]
        if character in "\"'":
            pieces.append(" ")
            index += 1
            closed = False
            while index < length:
                if text[index] == "\\":
                    index += 2
                    continue
                if text[index] == character:
                    index += 1
                    closed = True
                    break
                index += 1
            if not closed:
                raise FragmentError(
                    f"a string or character literal does not close on its line: {text!r}"
                )
            continue
        pieces.append(character)
        index += 1
    return "".join(pieces), in_block


def _lex(text: str) -> _Lexed:
    """Lex text as "Lexing" describes. A "\\r" anywhere in text is an error."""
    if "\r" in text:
        raise FragmentError("the source contains a carriage return; only LF line endings are read")
    lines: list[_Line] = []
    depth = 0
    opens = 0
    in_block = False
    continued = False  # The previous line is a preprocessor line ending in "\".
    for line in _source_lines(text):
        starts_in_comment = in_block
        stripped = line.lstrip()
        preprocessor = not starts_in_comment and (stripped.startswith("#") or continued)
        directive = preprocessor and not continued
        code = ""
        if not preprocessor:
            code, in_block = _strip_comments(line, in_block)
        top_level = (
            not preprocessor
            and not starts_in_comment
            and depth == 0
            and code.strip() != ""
            and line[:1] not in (" ", "\t")
        )
        lines.append(
            _Line(line, code, preprocessor, directive, starts_in_comment, depth, opens, top_level)
        )
        if directive:
            if IF_DIRECTIVE_RE.match(stripped):
                opens += 1
            elif ENDIF_DIRECTIVE_RE.match(stripped):
                opens -= 1
        depth += code.count("{") - code.count("}")
        continued = preprocessor and line.endswith("\\")
    return _Lexed(lines, depth, opens)


def _depth_after(source: _Lexed, line: int) -> int:
    """The brace depth at the start of the line after `line` (1-based)."""
    return source.lines[line].depth if line < len(source.lines) else source.depth_end


def _opens_after(source: _Lexed, line: int) -> int:
    """The number of open preprocessor conditionals at the start of the line after `line`."""
    return source.lines[line].opens if line < len(source.lines) else source.opens_end


def _fragment(source: _Lexed, first: int, last: int, what: str) -> Fragment:
    """Lines first..last as a Fragment, after the preprocessor-conditional check."""
    if source.lines[first - 1].opens != 0 or _opens_after(source, last) != 0:
        raise FragmentError(f"{what} lies inside a preprocessor conditional")
    text = "".join(f"{line.text}\n" for line in source.lines[first - 1 : last])
    return Fragment(text, first, last)


def _declarator_match(line: _Line) -> re.Match[str] | None:
    """The declarator of a top-level line, as "Lexing" defines it, or None."""
    if not line.top_level or NODE_DEFINE_RE.fullmatch(line.text.rstrip()):
        return None
    return DECLARATOR_RE.search(line.code)


def _parameter_text(source: _Lexed, header: int, open_index: int) -> str:
    """The parameter text of the "(" at open_index in the code of line header, possibly multi-line.

    Comments are already spaces, so `void BsdfNode::compile(SVMCompiler & /*compiler*/)` gives
    `SVMCompiler &`. Every whitespace run becomes one space and the ends are stripped.
    """
    pieces = [source.lines[header - 1].code[open_index + 1 :]]
    depth = 1
    number = header
    while True:
        text = pieces[-1]
        for index, character in enumerate(text):
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0:
                    pieces[-1] = text[:index]
                    return " ".join("\n".join(pieces).split())
        number += 1
        if number > len(source.lines):
            raise FragmentError(f"the parameter list at line {header} does not close")
        pieces.append(source.lines[number - 1].code)


def _definition_start(source: _Lexed, header: int) -> int:
    """The first line of the definition at header: header, or its `template` line."""
    if header > 1:
        previous = source.lines[header - 2]
        if previous.top_level and previous.code.startswith("template"):
            return header - 1
    return header


def _definition_extent(source: _Lexed, header: int) -> int:
    """The last line of the definition that starts at header, by "Definition extent"."""
    parens = 0
    braces = 0
    opened = False
    for number in range(header, len(source.lines) + 1):
        for character in source.lines[number - 1].code:
            if opened:
                if character == "{":
                    braces += 1
                elif character == "}":
                    braces -= 1
                    if braces == 0:
                        return number
            elif character == "(":
                parens += 1
            elif character == ")":
                parens -= 1
            elif character == "{" and parens == 0:
                opened = True
                braces = 1
            elif character == ";" and parens == 0:
                return number
    raise FragmentError(f"the definition at line {header} does not end")


def _one_header(numbers: list[int], what: str, headers: str) -> int:
    """The single line number, or FragmentError naming what and how many headers there were."""
    if len(numbers) != 1:
        raise FragmentError(f"{what}: {len(numbers)} {headers}; exactly one is needed")
    return numbers[0]


def _extract_svm_case(source: _Lexed, anchor: str, what: str) -> Fragment:
    """The extent of `SVM_CASE(anchor)`, which must not fall through into the next case."""
    wanted = f"SVM_CASE({anchor})"
    header = _one_header(
        [
            number
            for number, line in enumerate(source.lines, start=1)
            if not line.preprocessor and line.text.strip() == wanted
        ],
        what,
        f"lines are {wanted}",
    )
    depth = source.lines[header - 1].depth
    last = len(source.lines)
    for number in range(header + 1, len(source.lines) + 1):
        line = source.lines[number - 1]
        stripped = line.text.strip()
        if (
            line.depth < depth
            or (line.depth == depth and not line.preprocessor and stripped.startswith("SVM_CASE("))
            or (line.depth == depth and not line.preprocessor and stripped.startswith("default:"))
            or (line.depth == depth and line.directive and CASE_STOP_DIRECTIVE_RE.match(stripped))
        ):
            last = number - 1
            break
    while last > header and source.lines[last - 1].text.strip() == "":
        last -= 1
    end = source.lines[last - 1].text.strip()
    nested = (
        last > header
        and source.lines[header].text.strip() == "{"
        and all(
            source.lines[number - 1].depth >= depth + 1 for number in range(header + 2, last + 1)
        )
        and end == "}"
        and _depth_after(source, last) == depth
        and source.lines[last - 2].text.strip() in CASE_ENDS
    )
    if end not in CASE_ENDS and not nested:
        raise FragmentError(
            f"{what} falls through into the next case: line {last} is {end!r}, not one of"
            f" {list(CASE_ENDS)}, and the case is not the NODE_SHADER_JUMP form"
        )
    if (
        header > 1
        and source.lines[header - 2].directive
        and IF_DIRECTIVE_RE.match(source.lines[header - 2].text.lstrip())
        and last < len(source.lines)
        and source.lines[last].directive
        and source.lines[last].depth == depth
        and ENDIF_DIRECTIVE_RE.match(source.lines[last].text.lstrip())
    ):
        header -= 1
        last += 1
    return _fragment(source, header, last, what)


def _extract_node_define(source: _Lexed, anchor: str, what: str) -> Fragment:
    """The definition extent of the top-level `NODE_DEFINE(anchor)`."""
    header = _one_header(
        [
            number
            for number, line in enumerate(source.lines, start=1)
            if line.top_level and line.text.rstrip() == f"NODE_DEFINE({anchor})"
        ],
        what,
        f"top-level lines are NODE_DEFINE({anchor})",
    )
    return _fragment(
        source,
        _definition_start(source, header),
        _definition_extent(source, header),
        what,
    )


def _extract_define(source: _Lexed, anchor: str, what: str) -> Fragment:
    """The directive line of the macro anchor and its continuation lines."""
    header = _one_header(
        [
            number
            for number, line in enumerate(source.lines, start=1)
            if line.directive
            and line.depth == 0
            and (match := DEFINE_RE.match(line.text.lstrip()))
            and match.group(1) == anchor
        ],
        what,
        f"directive lines at depth 0 define {anchor}",
    )
    last = header
    while last < len(source.lines) and source.lines[last - 1].text.endswith("\\"):
        last += 1
    return _fragment(source, header, last, what)


def _extract_span(source: _Lexed, begin: str, end: str, what: str) -> Fragment:
    """The line whose whole text is begin, through the first line at or after it equal to end."""
    header = _one_header(
        [number for number, line in enumerate(source.lines, start=1) if line.text == begin],
        what,
        f"lines equal {begin!r}",
    )
    for number in range(header, len(source.lines) + 1):
        if source.lines[number - 1].text == end:
            return _fragment(source, header, number, what)
    raise FragmentError(f"{what}: no line at or after {header} equals {end!r}")


def _starts_with_params(text: str, params: str) -> bool:
    """True when text starts with params, followed by its end or a non-identifier character."""
    return (
        text.startswith(params)
        and len(text) > len(params)
        and text[len(params)]
        not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_"
    ) or text == params


def _extract_member(source: _Lexed, anchor: str, params: str | None, what: str) -> Fragment:
    """The one definition whose declarator is anchor, selected by params when one is given."""
    candidates: list[tuple[int, str | None]] = []
    for number, line in enumerate(source.lines, start=1):
        match = _declarator_match(line)
        if match is None or match.group(1) != anchor:
            continue
        text = _parameter_text(source, number, match.end(2) - 1) if match.group(2) == "(" else None
        candidates.append((number, text))

    def listing() -> str:
        return "; ".join(
            f"line {number}: {text!r}" if text is not None else f"line {number}: no parameter text"
            for number, text in candidates
        )

    if params is None:
        if len(candidates) != 1:
            raise FragmentError(
                f"{what}: {len(candidates)} definitions; exactly one is needed"
                + (f" ({listing()})" if candidates else "")
            )
        header = candidates[0][0]
    else:
        exact = [candidate for candidate in candidates if candidate[1] == params]
        if len(exact) == 1:
            header = exact[0][0]
        elif exact:
            raise FragmentError(
                f"{what}: {len(exact)} definitions have the parameter text {params!r};"
                f" exactly one is needed ({listing()})"
            )
        elif not params:
            raise FragmentError(f"{what}: no definition has the empty parameter text ({listing()})")
        else:
            prefix = [
                candidate
                for candidate in candidates
                if candidate[1] is not None and _starts_with_params(candidate[1], params)
            ]
            if len(prefix) != 1:
                raise FragmentError(
                    f"{what}: {len(prefix)} definitions start with the parameter text"
                    f" {params!r}; exactly one is needed ({listing()})"
                )
            header = prefix[0][0]
    return _fragment(
        source,
        _definition_start(source, header),
        _definition_extent(source, header),
        what,
    )


def _extract(
    source: _Lexed,
    kind: str,
    anchor: str | None = None,
    *,
    params: str | None = None,
    begin: str | None = None,
    end: str | None = None,
    fragment_id: str | None = None,
) -> Fragment:
    """Dispatch on kind ("Anchor kinds"); every failure raises FragmentError naming the anchor."""
    if kind not in FRAGMENT_KINDS:
        raise FragmentError(f"unknown kind {kind!r}; known kinds: {list(FRAGMENT_KINDS)}")
    if kind == "span":
        what = f"span {fragment_id}" if fragment_id else f"span {begin!r}..{end!r}"
        if begin is None or end is None:
            raise FragmentError(f"{what}: a span needs begin and end")
        return _extract_span(source, begin, end, what)
    if not anchor:
        raise FragmentError(f"{kind}: an anchor is needed")
    what = f"{kind} {anchor}"
    if params is not None and kind not in PARAM_KINDS:
        raise FragmentError(f"{what}: params is only for member and function, not {kind}")
    if kind == "svm_case":
        return _extract_svm_case(source, anchor, what)
    if kind == "node_define":
        return _extract_node_define(source, anchor, what)
    if kind == "define":
        return _extract_define(source, anchor, what)
    return _extract_member(source, anchor, params, what)


def extract_fragment(
    source: str,
    kind: str,
    anchor: str | None = None,
    *,
    params: str | None = None,
    begin: str | None = None,
    end: str | None = None,
) -> Fragment:
    """The one fragment of source that the anchor names ("Anchor kinds").

    source is the decoded file text; a "\\r" in it raises FragmentError.
    """
    return _extract(_lex(source), kind, anchor, params=params, begin=begin, end=end)


def list_anchors(source: str) -> list[Anchor]:
    """Every anchor of source that resolves, sorted by first line, then kind, then anchor.

    Tries every SVM_CASE(...) header, every top-level NODE_DEFINE(...) line, every directive line
    at depth 0 that defines a macro, and every top-level line with a declarator. A declarator
    containing "::" is tried as member and any other as function, each with its full parameter
    text, so overloads get one line each.
    """
    lexed = _lex(source)
    anchors: list[Anchor] = []
    attempts: list[tuple[str, str, str | None]] = []
    for number, line in enumerate(lexed.lines, start=1):
        stripped = line.text.strip()
        case = SVM_CASE_HEADER_RE.fullmatch(stripped) if not line.preprocessor else None
        if case is not None:
            attempts.append(("svm_case", case.group(1), None))
        define = NODE_DEFINE_RE.fullmatch(line.text.rstrip()) if line.top_level else None
        if define is not None:
            attempts.append(("node_define", define.group(1), None))
        if line.directive and line.depth == 0:
            match = DEFINE_RE.match(line.text.lstrip())
            if match is not None:
                attempts.append(("define", match.group(1), None))
        match = _declarator_match(line)
        if match is None:
            continue
        kind = "member" if "::" in match.group(1) else "function"
        try:
            params = (
                _parameter_text(lexed, number, match.end(2) - 1) if match.group(2) == "(" else None
            )
        except FragmentError:
            continue
        attempts.append((kind, match.group(1), params))
    for kind, anchor, params in attempts:
        try:
            fragment = _extract(lexed, kind, anchor, params=params)
        except FragmentError:
            continue
        anchors.append(Anchor(kind, anchor, params or "", fragment.first_line, fragment.last_line))
    anchors.sort(key=lambda found: (found.first_line, found.kind, found.anchor))
    return anchors


def fragment_name(
    upstream_path: str,
    kind: str,
    anchor: str | None = None,
    *,
    params: str | None = None,
    fragment_id: str | None = None,
) -> str:
    """The name of a fragment: `<upstream_path with . -> _>/<kind>/<id>` ("Names and files")."""
    if kind not in FRAGMENT_KINDS:
        raise FragmentError(f"unknown kind {kind!r}; known kinds: {list(FRAGMENT_KINDS)}")
    if kind == "span":
        if fragment_id is None:
            raise FragmentError("a span fragment needs an id")
        ident = fragment_id
    else:
        if anchor is None:
            raise FragmentError(f"a {kind} fragment needs an anchor")
        ident = anchor.replace("::", ".") if kind == "member" else anchor
        if kind in PARAM_KINDS and params is not None:
            suffix = re.sub(r"[^A-Za-z0-9_]+", "_", params).strip("_")
            ident = f"{ident}-{suffix or 'void'}"
    name = f"{upstream_path.replace('.', '_')}/{kind}/{ident}"
    path = f"third_party/cycles/fragments/{name}.inc"
    if len(path) > FRAGMENT_PATH_MAX:
        raise FragmentError(
            f"the fragment path {path!r} is {len(path)} characters; the limit is"
            f" {FRAGMENT_PATH_MAX}. Pass a shorter --params or --id."
        )
    return name


def _fragment_source(
    manifest: Manifest, checkouts: Mapping[str, Path], upstream: str, upstream_path: str
) -> str:
    """The UTF-8 text of upstream_path in upstream's pinned commit.

    The bytes are the commit's blob (`upstream_blob`), never the checkout's working-tree file, so
    an edited, deleted or untracked checkout file, or end-of-line conversion at checkout, changes
    no fragment. Raises FragmentError when the upstream is not pinned, has no checkout, or has no
    readable UTF-8 file at that path; a checkout whose HEAD is not the pin is refused by
    `_require_pin` with `ensure_checkout`'s message.
    """
    if upstream not in manifest.upstreams:
        raise FragmentError(f"upstream {upstream!r} is not pinned in VENDORED.toml")
    if upstream not in checkouts:
        raise FragmentError(
            f"upstream {upstream!r} has no checkout; run tools/vendor_sync.py fetch"
        )
    pinned = manifest.upstreams[upstream]
    checkout = checkouts[upstream]
    # The same refusal, and the same text, that ensure_checkout gives a checkout off its pin.
    try:
        _require_pin(pinned, checkout)
    except VendorError as err:
        raise FragmentError(str(err)) from err
    try:
        data = upstream_blob(pinned, checkout, upstream_path)
    except VendorError as err:
        raise FragmentError(f"{upstream}:{upstream_path} at {pinned.commit}: {err}") from err
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as err:
        raise FragmentError(
            f"{upstream}:{upstream_path} at {pinned.commit} is not UTF-8: {err}"
        ) from err


def _load_fragments_manifest(manifest: Path) -> Manifest:
    """load_manifest, with T3.1's VendorError re-raised as FragmentError (same message)."""
    try:
        return load_manifest(manifest)
    except FragmentError:
        raise
    except VendorError as err:
        raise FragmentError(str(err)) from err


def _fragment_table(
    name: str,
    upstream: str,
    upstream_path: str,
    kind: str,
    fragment: Fragment,
    *,
    anchor: str | None = None,
    params: str | None = None,
    fragment_id: str | None = None,
    begin: str | None = None,
    end: str | None = None,
) -> dict[str, object]:
    """The [[fragment]] table of one extracted fragment, its keys in FRAGMENT_KEYS order."""
    table: dict[str, object] = {
        "name": name,
        "upstream": upstream,
        "upstream_path": upstream_path,
        "kind": kind,
    }
    if kind == "span":
        table.update({"id": fragment_id, "begin": begin, "end": end})
    else:
        table["anchor"] = anchor
        if kind in PARAM_KINDS and params is not None:
            table["params"] = params
    table["upstream_lines"] = [fragment.first_line, fragment.last_line]
    table["sha256"] = _sha256(fragment.text.encode("utf-8"))
    return table


def _entry_fragment(sources: _Sources, table: Mapping[str, object]) -> Fragment:
    """Re-extract the fragment that a [[fragment]] table records, from its checkout."""
    return _extract(
        sources.get(str(table["upstream"]), str(table["upstream_path"])),
        str(table["kind"]),
        table.get("anchor") if isinstance(table.get("anchor"), str) else None,
        params=table.get("params") if isinstance(table.get("params"), str) else None,
        begin=table.get("begin") if isinstance(table.get("begin"), str) else None,
        end=table.get("end") if isinstance(table.get("end"), str) else None,
        fragment_id=table.get("id") if isinstance(table.get("id"), str) else None,
    )


def add_fragments(
    manifest: Path,
    checkouts: Mapping[str, Path],
    upstream: str,
    upstream_path: str,
    kind: str,
    anchors: Sequence[str] = (),
    *,
    params: str | None = None,
    fragment_id: str | None = None,
    begin: str | None = None,
    end: str | None = None,
) -> list[str]:
    """Append one [[fragment]] entry per anchor, write their .inc files; returns their names.

    All or nothing: every name, extraction and rule is checked before anything is written.
    """
    current = _load_fragments_manifest(manifest)
    try:
        upstream_path = _rel_path(upstream_path, "upstream_path")
    except VendorError as err:
        raise FragmentError(str(err)) from err
    if kind == "span":
        if anchors:
            raise FragmentError("span takes no ANCHOR; it needs --id, --begin and --end")
        if fragment_id is None or begin is None or end is None:
            raise FragmentError("span needs --id, --begin and --end")
    else:
        if fragment_id is not None or begin is not None or end is not None:
            raise FragmentError(f"{kind} takes ANCHORs; --id, --begin and --end are only for span")
        if not anchors:
            raise FragmentError(f"{kind} needs at least one ANCHOR")
    if params is not None and kind not in PARAM_KINDS:
        raise FragmentError(f"params is only for member and function, not {kind}")
    sources = _Sources(current, checkouts)
    lexed = sources.get(upstream, upstream_path)
    added: list[tuple[str, dict[str, object], Fragment]] = []
    if kind == "span":
        fragment = _extract(lexed, kind, None, begin=begin, end=end, fragment_id=fragment_id)
        name = fragment_name(upstream_path, kind, fragment_id=fragment_id)
        added.append(
            (
                name,
                _fragment_table(
                    name,
                    upstream,
                    upstream_path,
                    kind,
                    fragment,
                    fragment_id=fragment_id,
                    begin=begin,
                    end=end,
                ),
                fragment,
            )
        )
    else:
        for anchor in anchors:
            fragment = _extract(lexed, kind, anchor, params=params)
            name = fragment_name(upstream_path, kind, anchor, params=params)
            added.append(
                (
                    name,
                    _fragment_table(
                        name,
                        upstream,
                        upstream_path,
                        kind,
                        fragment,
                        anchor=anchor,
                        params=params,
                    ),
                    fragment,
                )
            )
    updated = Manifest(
        current.upstreams, current.entries, [*current.fragments, *(table for _, table, _ in added)]
    )
    check_structure(updated)
    directory = manifest.parent / "fragments"
    for name, table, fragment in added:
        path = directory / f"{name}.inc"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fragment.text.encode("utf-8"))
        del table
    manifest.write_bytes(render_manifest(updated).encode("utf-8"))
    return [name for name, _, _ in added]


def sync_fragments(manifest: Path, checkouts: Mapping[str, Path]) -> None:
    """Re-extract every fragment and write its .inc file; a mismatch names it and writes nothing."""
    current = _load_fragments_manifest(manifest)
    sources = _Sources(current, checkouts)
    extracted: list[tuple[str, Fragment]] = []
    for table in current.fragments:
        name = str(table["name"])
        fragment = _entry_fragment(sources, table)
        lines = [fragment.first_line, fragment.last_line]
        if (
            lines != table["upstream_lines"]
            or _sha256(fragment.text.encode("utf-8")) != (table["sha256"])
        ):
            raise FragmentError(
                f"{name}: the extraction gives lines {lines} and sha256"
                f" {_sha256(fragment.text.encode('utf-8'))}, but VENDORED.toml records"
                f" {table['upstream_lines']} and {table['sha256']}"
            )
        extracted.append((name, fragment))
    directory = manifest.parent / "fragments"
    for name, fragment in extracted:
        path = directory / f"{name}.inc"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(fragment.text.encode("utf-8"))


def check_fragments(manifest: Path, checkouts: Mapping[str, Path] | None = None) -> list[str]:
    """Problems with the fragment files, one message each; empty when all is well.

    Offline, it compares every .inc file with its entry's sha256 and reports files under
    fragments/ that no entry lists. With checkouts, it also re-extracts every fragment and
    compares its bytes and upstream_lines.
    """
    current = _load_fragments_manifest(manifest)
    directory = manifest.parent / "fragments"
    problems: list[str] = []
    listed: set[str] = set()
    for table in current.fragments:
        name = str(table["name"])
        listed.add(name)
        path = directory / f"{name}.inc"
        if not path.is_file():
            problems.append(f"{name}: listed in VENDORED.toml but fragments/{name}.inc is missing")
            continue
        digest = _sha256(path.read_bytes())
        if digest != table["sha256"]:
            problems.append(f"{name}: sha256 {digest} differs from VENDORED.toml {table['sha256']}")
    if directory.is_dir():
        for path in sorted(directory.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(directory).as_posix()
            name = relative[: -len(".inc")] if relative.endswith(".inc") else None
            if name is not None and name in listed:
                continue
            problems.append(f"fragments/{relative}: on disk but not listed in VENDORED.toml")
    if checkouts is None:
        return problems
    sources = _Sources(current, checkouts)
    for table in current.fragments:
        name = str(table["name"])
        try:
            fragment = _entry_fragment(sources, table)
        except FragmentError as err:
            problems.append(f"{name}: {err}")
            continue
        lines = [fragment.first_line, fragment.last_line]
        if lines != table["upstream_lines"]:
            problems.append(
                f"{name}: re-extracted lines {lines} differ from VENDORED.toml"
                f" {table['upstream_lines']}"
            )
        path = directory / f"{name}.inc"
        if path.is_file() and path.read_bytes() != fragment.text.encode("utf-8"):
            problems.append(f"{name}: bytes differ from the re-extraction")
    return problems


def remove_fragments(manifest: Path, names: Sequence[str]) -> None:
    """Delete these fragments' entries and .inc files, and the directories they leave empty."""
    current = _load_fragments_manifest(manifest)
    listed = {str(table["name"]) for table in current.fragments}
    wanted: list[str] = []
    for name in names:
        if name not in listed:
            raise FragmentError(f"{name} is not a fragment in VENDORED.toml")
        wanted.append(name)
    drop = set(wanted)
    kept = [table for table in current.fragments if str(table["name"]) not in drop]
    manifest.write_bytes(
        render_manifest(Manifest(current.upstreams, current.entries, kept)).encode("utf-8")
    )
    directory = manifest.parent / "fragments"
    for name in wanted:
        path = directory / f"{name}.inc"
        path.unlink(missing_ok=True)
        _prune_fragment_dirs(path.parent, directory)


def _prune_fragment_dirs(directory: Path, base: Path) -> None:
    """Remove directory and its empty ancestors, stopping at the fragments directory."""
    while directory != base and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent


def _fragment_checkouts(manifest: Manifest) -> dict[str, Path]:
    """checkout_dir of every upstream; a missing checkout is an error that names fetch."""
    checkouts: dict[str, Path] = {}
    for name, upstream in manifest.upstreams.items():
        path = checkout_dir(upstream)
        if not path.is_dir():
            raise FragmentError(
                f"upstream {name!r} has no checkout at {path}; run tools/vendor_sync.py fetch"
            )
        checkouts[name] = path
    return checkouts


def _fragment_sync_checkouts(manifest: Manifest) -> dict[str, Path]:
    """ensure_checkout of every upstream a fragment uses, as T3.1's sync and check do."""
    return source_checkouts(manifest, (str(table["upstream"]) for table in manifest.fragments))


def _resolve_include(present: frozenset[str], including: str, include: str) -> str | None:
    """Root-relative path that `#include "include"` in the file `including` resolves to, or None.

    The C preprocessor searches the including file's own directory first, then the include path,
    which here is the root. present holds the root-relative paths of the files under the root.
    """
    for candidate in (posixpath.join(posixpath.dirname(including), include), include):
        normal = posixpath.normpath(candidate)
        if normal == ".." or normal.startswith(("../", "/")):
            continue
        if normal in present:
            return normal
    return None


def include_closure(
    upstream: Upstream, checkout: Path, seeds: Iterable[str]
) -> tuple[set[str], set[tuple[str, str]]]:
    """Transitive closure of the quoted #include lines reachable from seeds under upstream's root.

    Files and their text come from the pinned commit (upstream_files, upstream_blob), never from
    the working tree of checkout. Returns (files, missing). files are root-relative POSIX paths,
    seeds included. missing holds (include text, including file) pairs for quoted includes that
    resolve to no file under the root, and (seed, "command line") for seeds that are absent. These
    are the shim candidates. Conditional blocks are not evaluated, so every #include line counts.
    """
    present = upstream_files(upstream, checkout)
    files: set[str] = set()
    missing: set[tuple[str, str]] = set()
    pending: deque[str] = deque()
    for seed in seeds:
        relative = _rel_path(seed, "header")
        if relative in present:
            if relative not in files:
                files.add(relative)
                pending.append(relative)
        else:
            missing.add((relative, "command line"))
    while pending:
        current = pending.popleft()
        text = upstream_blob(upstream, checkout, current).decode("utf-8", errors="replace")
        for match in INCLUDE_RE.finditer(text):
            include = match.group(1)
            found = _resolve_include(present, current, include)
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
    source_checkouts(manifest, manifest.upstreams)
    return 0


def cmd_sync() -> int:
    """Regenerate third_party/cycles from the pinned commits and patches; rewrite VENDORED.toml."""
    manifest = load_manifest()
    sync_fragments(MANIFEST, _fragment_sync_checkouts(manifest))
    manifest = sync_manifest(manifest)
    print(f"synced {len(manifest.entries)} vendored files; rewrote {_shown(MANIFEST)}")
    print(f"synced {len(manifest.fragments)} fragments")
    return 0


def cmd_check(upstream: bool) -> int:
    """Verify the tree against the manifest; with upstream, also re-derive every file."""
    manifest = load_manifest()
    problems = offline_problems(manifest)
    if upstream:
        problems += upstream_problems(manifest)
        problems += check_fragments(MANIFEST, _fragment_sync_checkouts(manifest))
    else:
        problems += check_fragments(MANIFEST)
    for problem in problems:
        print(f"vendor-check: {problem}", file=sys.stderr)
    if problems:
        return 1
    scope = " and re-derivation from upstream" if upstream else ""
    print(f"vendor-check: {len(manifest.entries)} vendored files match {_shown(MANIFEST)}{scope}")
    fragments = len(manifest.fragments)
    extra = " and re-extraction from upstream" if upstream else ""
    print(f"vendor-check: {fragments} fragments match {_shown(MANIFEST)}{extra}")
    return 0


def cmd_add(upstream: str, upstream_paths: list[str], dest_prefix: str | None) -> int:
    """Append entries for upstream_paths to VENDORED.toml, then sync.

    Every file is checked before anything is written.
    """
    manifest = load_manifest()
    _require(manifest, upstream)
    prefix = None if dest_prefix is None else _rel_path(dest_prefix, "--dest-prefix")
    checkout = source_checkouts(manifest, [upstream])[upstream]
    present = upstream_files(manifest.upstreams[upstream], checkout)
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
        if upstream_path not in present:
            raise _missing_file(manifest.upstreams[upstream], upstream_path)
        taken.add(dest)
        added.append(Entry(upstream=upstream, upstream_path=upstream_path, dest=dest))
    manifest = sync_manifest(
        Manifest(manifest.upstreams, [*manifest.entries, *added], manifest.fragments)
    )
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
    manifest = sync_manifest(Manifest(manifest.upstreams, kept, manifest.fragments))
    for dest in sorted(wanted):
        path = VENDOR_DIR / dest
        path.unlink(missing_ok=True)
        _prune_empty_dirs(path.parent)
        print(f"removed {dest}")
    print(f"synced {len(manifest.entries)} vendored files; rewrote {_shown(MANIFEST)}")
    return 0


def cmd_add_fragment(
    upstream: str,
    upstream_path: str,
    kind: str,
    anchors: list[str],
    params: str | None,
    fragment_id: str | None,
    begin: str | None,
    end: str | None,
) -> int:
    """Append a [[fragment]] entry per anchor, write their .inc files and print their names."""
    try:
        current = load_manifest()
    except VendorError as err:
        raise FragmentError(str(err)) from err
    checkouts = _fragment_checkouts(current)
    names = add_fragments(
        MANIFEST,
        checkouts,
        upstream,
        upstream_path,
        kind,
        anchors,
        params=params,
        fragment_id=fragment_id,
        begin=begin,
        end=end,
    )
    for name in names:
        print(name)
    return 0


def cmd_remove_fragment(names: list[str]) -> int:
    """Delete these fragments' entries and .inc files."""
    remove_fragments(MANIFEST, names)
    for name in names:
        print(f"removed {name}")
    return 0


def cmd_extract(
    upstream: str,
    upstream_path: str,
    kind: str,
    anchor: str | None,
    params: str | None,
    begin: str | None,
    end: str | None,
) -> int:
    """Print one fragment's text on stdout, and its line range and sha256 on stderr."""
    current = load_manifest()
    checkouts = _fragment_checkouts(current)
    try:
        upstream_path = _rel_path(upstream_path, "upstream_path")
    except VendorError as err:
        raise FragmentError(str(err)) from err
    lexed = _Sources(current, checkouts).get(upstream, upstream_path)
    fragment = _extract(lexed, kind, anchor, params=params, begin=begin, end=end)
    # The bytes on stdout are the bytes whose sha256 goes to stderr, on every platform: writing
    # text to sys.stdout would translate "\n" to os.linesep (CRLF under Windows text mode).
    data = fragment.text.encode("utf-8")
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()
    _report(f"{upstream_path}:{fragment.first_line}-{fragment.last_line} sha256={_sha256(data)}")
    return 0


def cmd_list_anchors(upstream: str, upstream_path: str) -> int:
    """Print every anchor of a file that extract resolves, one per line."""
    current = load_manifest()
    checkouts = _fragment_checkouts(current)
    try:
        upstream_path = _rel_path(upstream_path, "upstream_path")
    except VendorError as err:
        raise FragmentError(str(err)) from err
    text = _fragment_source(current, checkouts, upstream, upstream_path)
    for anchor in list_anchors(text):
        print(
            "\t".join(
                [
                    anchor.kind,
                    anchor.anchor,
                    anchor.params,
                    str(anchor.first_line),
                    str(anchor.last_line),
                ]
            )
        )
    return 0


def cmd_closure(seeds: list[str]) -> int:
    """Print the #include closure of seeds inside the cycles root.

    stdout: a `# closure:` line, one root-relative path per file, then `# missing:` lines. Missing
    headers are not an error (they are shim candidates), so the exit status is 0 whenever the
    closure could be computed.
    """
    manifest = load_manifest()
    _require(manifest, CYCLES)
    upstream = manifest.upstreams[CYCLES]
    checkout = source_checkouts(manifest, [CYCLES])[CYCLES]
    files, missing = include_closure(upstream, checkout, seeds)
    print(f"# closure: {len(files)} files under {upstream.root}")
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
        "sync", help="regenerate third_party/cycles from the pinned commits and patches/"
    )
    check = commands.add_parser("check", help="verify third_party/cycles against VENDORED.toml")
    check.add_argument(
        "--upstream",
        action="store_true",
        help="also re-derive every file from its pinned commit and patches (needs the checkouts)",
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
    add_fragment = commands.add_parser(
        "add-fragment", help="vendor verbatim extracts of an upstream file"
    )
    _add_fragment_arguments(add_fragment)
    add_fragment.add_argument(
        "anchors",
        nargs="*",
        metavar="ANCHOR",
        help="the anchor of each fragment; none for a span, which takes --id, --begin and --end",
    )
    remove_fragment = commands.add_parser(
        "remove-fragment", help="delete fragments' entries and their .inc files"
    )
    remove_fragment.add_argument("names", nargs="+", metavar="NAME", help="fragment name")
    extract = commands.add_parser(
        "extract", help="print one fragment's text, its line range and its sha256"
    )
    _add_fragment_arguments(extract)
    extract.add_argument("anchor", nargs="?", metavar="ANCHOR", help="the anchor; none for a span")
    list_anchors_command = commands.add_parser(
        "list-anchors", help="print every anchor of an upstream file that extract resolves"
    )
    _add_fragment_arguments(list_anchors_command, anchor=False)
    return parser


def _add_fragment_arguments(parser: argparse.ArgumentParser, anchor: bool = True) -> None:
    """The arguments that add-fragment and extract share: the source, kind and span text."""
    parser.add_argument(
        "--upstream", default=DEFAULT_UPSTREAM, help=f"upstream name (default: {DEFAULT_UPSTREAM})"
    )
    parser.add_argument("upstream_path", metavar="UPSTREAM_PATH", help="path in the upstream root")
    if anchor:
        parser.add_argument("kind", metavar="KIND", help=f"one of {', '.join(FRAGMENT_KINDS)}")
    parser.add_argument(
        "--params",
        metavar="TEXT",
        help="parameter text that selects a member or function; '' selects the empty text",
    )
    parser.add_argument("--id", metavar="ID", dest="fragment_id", help="the id of a span")
    parser.add_argument("--begin", metavar="TEXT", help="the first line of a span, whole")
    parser.add_argument("--end", metavar="TEXT", help="the last line of a span, whole")


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
        if args.command == "add-fragment":
            return cmd_add_fragment(
                args.upstream,
                args.upstream_path,
                args.kind,
                args.anchors,
                args.params,
                args.fragment_id,
                args.begin,
                args.end,
            )
        if args.command == "remove-fragment":
            return cmd_remove_fragment(args.names)
        if args.command == "extract":
            return cmd_extract(
                args.upstream,
                args.upstream_path,
                args.kind,
                args.anchor,
                args.params,
                args.begin,
                args.end,
            )
        if args.command == "list-anchors":
            return cmd_list_anchors(args.upstream, args.upstream_path)
        return cmd_closure(args.seeds)
    except VendorError as err:
        print(f"vendor_sync: error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
