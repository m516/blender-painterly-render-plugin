"""tools/vendor_sync.py (T3.1, T3.27).

test_vendored_tree_matches_manifest runs `check` offline on the real third_party/cycles. Every
other test runs the tool on a temporary repository whose upstream is a git repository that the
test commits itself, so it needs no network and no .cache/vendor checkout. Those tests check that
upstream bytes come from the pinned commit's git objects, never from the checkout's working tree
(T3.27, M3 review panel #0).
"""

import hashlib
import importlib.util
import io
import os
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_TOOL = REPO_ROOT / "tools" / "vendor_sync.py"


def test_vendored_tree_matches_manifest() -> None:
    """The offline check (no network, no checkouts) reports no difference from VENDORED.toml."""
    result = subprocess.run(
        [sys.executable, str(VENDOR_TOOL), "check"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, f"vendor_sync check failed:\n{result.stderr}{result.stdout}"


def _load_vendor_tool() -> ModuleType:
    """tools/vendor_sync.py, loaded by path as test_symbol_audit_parsers.py loads its tool."""
    spec = importlib.util.spec_from_file_location("vendor_sync", VENDOR_TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


vs = _load_vendor_tool()

# The fixture upstream's files at its pinned commit, relative to the repository top. ROOT is the
# upstream root, as intern/cycles is Blender's; README lies outside it.
ROOT = "intern/cycles"
A_H = b'#include "util/b.h"\n#define A 1\n'
B_H = b"#define B 1\n"
C_H = b"#define C 1\n"
COMMITTED = {f"{ROOT}/util/a.h": A_H, f"{ROOT}/util/b.h": B_H, "README": b"fixture upstream\n"}
TAMPER = b"/* tampered */\n"
# The fixture's own git commands: no GIT_* variable of the caller, no user or system git
# configuration (so no commit signing and no core.autocrlf), and a fixed identity and date, so
# every run makes the same commits.
FIXTURE_GIT_ENV = {
    **{key: value for key, value in os.environ.items() if not key.startswith("GIT_")},
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_AUTHOR_NAME": "Painterly tests",
    "GIT_AUTHOR_EMAIL": "tests@painterly.invalid",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00+00:00",
    "GIT_COMMITTER_NAME": "Painterly tests",
    "GIT_COMMITTER_EMAIL": "tests@painterly.invalid",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00+00:00",
}


def _fixture_git(repo: Path, *args: str) -> str:
    """Run git in the fixture repository repo; return its stdout without surrounding whitespace."""
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        env=FIXTURE_GIT_ENV,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _no_fetch(*args: object) -> None:
    """Replaces _clone_tag and _fetch_commit: the fixture checkout exists, so nothing is fetched."""
    raise AssertionError("the fixture checkout is at its pin, so nothing may be fetched")


@dataclass(frozen=True)
class Tree:
    """The temporary repository of one test: its upstream checkout and its third_party/cycles."""

    checkout: Path
    upstream: vs.Upstream
    vendor_dir: Path


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Tree:
    """A repository whose VENDORED.toml vendors util/a.h and util/b.h from the fixture upstream.

    The tool's path constants point into tmp_path / "repo" for the test, and its two fetch
    functions fail the test. The upstream is tagged "v0", so its checkout directory is
    .cache/vendor/blender-v0 (vs.checkout_dir), which the fixture commits at the pin.
    """
    repo = tmp_path / "repo"
    vendor_dir = repo / "third_party" / "cycles"
    (vendor_dir / "patches").mkdir(parents=True)
    monkeypatch.setattr(vs, "REPO_ROOT", repo)
    monkeypatch.setattr(vs, "VENDOR_DIR", vendor_dir)
    monkeypatch.setattr(vs, "MANIFEST", vendor_dir / "VENDORED.toml")
    monkeypatch.setattr(vs, "PATCH_DIR", vendor_dir / "patches")
    monkeypatch.setattr(vs, "CHECKOUT_DIR", repo / ".cache" / "vendor")
    monkeypatch.setattr(vs, "_clone_tag", _no_fetch)
    monkeypatch.setattr(vs, "_fetch_commit", _no_fetch)
    checkout = repo / ".cache" / "vendor" / "blender-v0"
    for path, data in COMMITTED.items():
        (checkout / path).parent.mkdir(parents=True, exist_ok=True)
        (checkout / path).write_bytes(data)
    _fixture_git(checkout, "init", "--quiet")
    _fixture_git(checkout, "add", "--all")
    _fixture_git(checkout, "commit", "--quiet", "--message", "fixture upstream")
    upstream = vs.Upstream(
        name="cycles",
        repo=str(tmp_path / "no-such-remote"),
        commit=_fixture_git(checkout, "rev-parse", "HEAD"),
        root=ROOT,
        tag="v0",
    )
    assert vs.checkout_dir(upstream) == checkout
    empty = vs.Manifest({"cycles": upstream}, [])
    vs.MANIFEST.write_bytes(vs.render_manifest(empty).encode("utf-8"))
    assert vs.main(["add", "util/a.h", "util/b.h"]) == 0
    return Tree(checkout, upstream, vendor_dir)


def _problems(capsys: pytest.CaptureFixture[str]) -> list[str]:
    """The `vendor-check:` lines on stderr since the last read."""
    lines = capsys.readouterr().err.splitlines()
    return [line for line in lines if line.startswith("vendor-check:")]


def _sha256(data: bytes) -> str:
    """Lowercase hex SHA-256 digest of data, as VENDORED.toml records it."""
    return hashlib.sha256(data).hexdigest()


def test_sync_reads_the_pinned_commit_not_the_working_tree(tree: Tree) -> None:
    """An edited and a deleted checkout file change no vendored byte and no recorded hash."""
    recorded = {entry.dest: entry.upstream_sha256 for entry in vs.load_manifest().entries}
    assert recorded == {"util/a.h": _sha256(A_H), "util/b.h": _sha256(B_H)}
    manifest_before = vs.MANIFEST.read_bytes()
    (tree.checkout / ROOT / "util" / "a.h").write_bytes(A_H + TAMPER)
    (tree.checkout / ROOT / "util" / "b.h").unlink()
    assert vs.upstream_blob(tree.upstream, tree.checkout, "util/a.h") == A_H
    assert vs.main(["sync"]) == 0
    assert (tree.vendor_dir / "util" / "a.h").read_bytes() == A_H
    assert (tree.vendor_dir / "util" / "b.h").read_bytes() == B_H
    assert vs.MANIFEST.read_bytes() == manifest_before
    assert vs.main(["check", "--upstream"]) == 0


def test_crlf_checkout_changes_no_vendored_byte(tree: Tree) -> None:
    """core.autocrlf=true puts CRLF in the working tree; the blob and the vendored file stay LF."""
    worktree_file = tree.checkout / ROOT / "util" / "a.h"
    _fixture_git(tree.checkout, "config", "core.autocrlf", "true")
    worktree_file.unlink()
    _fixture_git(tree.checkout, "checkout", "--", f"{ROOT}/util/a.h")
    assert worktree_file.read_bytes() == A_H.replace(b"\n", b"\r\n")
    assert vs.upstream_blob(tree.upstream, tree.checkout, "util/a.h") == A_H
    assert vs.main(["check", "--upstream"]) == 0
    assert vs.main(["sync"]) == 0
    assert (tree.vendor_dir / "util" / "a.h").read_bytes() == A_H


def test_check_upstream_detects_a_vendored_file_that_differs_from_the_pinned_commit(
    tree: Tree, capsys: pytest.CaptureFixture[str]
) -> None:
    """The state that reading an edited working tree produced before T3.27 (panel #0).

    The vendored util/a.h and both of its hashes match the edited checkout file, so the offline
    check passes. check --upstream compares with the pinned blob and names the file.
    """
    tampered = A_H + TAMPER
    (tree.checkout / ROOT / "util" / "a.h").write_bytes(tampered)
    (tree.vendor_dir / "util" / "a.h").write_bytes(tampered)
    manifest = vs.load_manifest()
    entries = [
        replace(entry, upstream_sha256=_sha256(tampered), sha256=_sha256(tampered))
        if entry.dest == "util/a.h"
        else entry
        for entry in manifest.entries
    ]
    rendered = vs.render_manifest(vs.Manifest(manifest.upstreams, entries))
    vs.MANIFEST.write_bytes(rendered.encode("utf-8"))
    capsys.readouterr()
    assert vs.main(["check"]) == 0
    assert vs.main(["check", "--upstream"]) == 1
    pinned, recorded = _sha256(A_H), _sha256(tampered)
    assert _problems(capsys) == [
        f"vendor-check: util/a.h: upstream sha256 {pinned} differs from VENDORED.toml {recorded}",
        f"vendor-check: util/a.h: re-derived sha256 {pinned} differs from VENDORED.toml {recorded}",
        "vendor-check: util/a.h: bytes differ from the re-derivation",
    ]


def test_add_refuses_a_file_that_is_only_in_the_working_tree(
    tree: Tree, capsys: pytest.CaptureFixture[str]
) -> None:
    """An untracked checkout file is not in the pinned commit: add refuses it and writes nothing."""
    (tree.checkout / ROOT / "util" / "c.h").write_bytes(C_H)
    manifest_before = vs.MANIFEST.read_bytes()
    capsys.readouterr()
    assert vs.main(["add", "util/c.h"]) == 1
    assert capsys.readouterr().err.splitlines()[-1] == (
        f"vendor_sync: error: util/c.h is not a file in upstream cycles at {tree.upstream.commit}"
    )
    assert vs.MANIFEST.read_bytes() == manifest_before
    assert not (tree.vendor_dir / "util" / "c.h").exists()


def test_closure_follows_the_pinned_commit(tree: Tree, capsys: pytest.CaptureFixture[str]) -> None:
    """An include line added in the working tree, and the untracked header it names, are unseen."""
    (tree.checkout / ROOT / "util" / "a.h").write_bytes(A_H + b'#include "util/c.h"\n')
    (tree.checkout / ROOT / "util" / "c.h").write_bytes(C_H)
    capsys.readouterr()
    assert vs.main(["closure", "util/a.h"]) == 0
    assert capsys.readouterr().out.splitlines() == [
        "# closure: 2 files under intern/cycles",
        "util/a.h",
        "util/b.h",
        "# missing: 0",
    ]


@pytest.mark.parametrize(
    "command",
    [
        ["sync"],
        ["check", "--upstream"],
        ["add", "util/c.h"],
        ["closure", "util/a.h"],
        # The fragment subcommands read a file of the checkout, so they refuse a checkout off its
        # pin as well (M6a-FIX-VS1).
        ["add-fragment", "util/a.h", "define", "A"],
        ["extract", "util/a.h", "define", "A"],
        ["list-anchors", "util/a.h"],
    ],
    ids=["sync", "check-upstream", "add", "closure", "add-fragment", "extract", "list-anchors"],
)
def test_a_checkout_off_its_pin_is_refused(
    tree: Tree, capsys: pytest.CaptureFixture[str], command: list[str]
) -> None:
    """A checkout whose HEAD is a later commit (it adds util/c.h) is refused; nothing is written."""
    (tree.checkout / ROOT / "util" / "c.h").write_bytes(C_H)
    _fixture_git(tree.checkout, "add", "--all")
    _fixture_git(tree.checkout, "commit", "--quiet", "--message", "off the pin")
    head = _fixture_git(tree.checkout, "rev-parse", "HEAD")
    manifest_before = vs.MANIFEST.read_bytes()
    capsys.readouterr()
    assert vs.main(command) == 1
    assert capsys.readouterr().err.splitlines()[-1] == (
        f"vendor_sync: error: {tree.checkout} is at {head}, not the pinned "
        f"{tree.upstream.commit}; delete it and rerun fetch"
    )
    assert vs.MANIFEST.read_bytes() == manifest_before
    assert not (tree.vendor_dir / "util" / "c.h").exists()


def test_extract_writes_the_bytes_it_hashes(
    tree: Tree, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """extract writes the fragment's LF bytes to stdout.buffer, whatever the text mode would do.

    A text-mode stdout with newline="\r\n" is what Windows does to "\n". The bytes behind it are
    the fragment's own LF bytes, and their sha256 is the one extract prints on stderr (A7).
    """
    del tree
    buffer = io.BytesIO()
    stdout = io.TextIOWrapper(buffer, encoding="utf-8", newline="\r\n")
    monkeypatch.setattr(sys, "stdout", stdout)
    assert vs.main(["extract", "util/a.h", "define", "A"]) == 0
    stdout.flush()
    # `#define A 1\n` is the whole of util/a.h's define A.
    expected = b"#define A 1\n"
    assert buffer.getvalue() == expected
    assert capsys.readouterr().err.splitlines() == [f"util/a.h:2-2 sha256={_sha256(expected)}"]


def test_object_paths_with_a_root_and_at_the_repository_top(tree: Tree) -> None:
    """Paths are relative to the upstream root; root "" (sse2neon's) is the repository top."""
    top = replace(tree.upstream, root="")
    assert vs.upstream_files(tree.upstream, tree.checkout) == {"util/a.h", "util/b.h"}
    assert vs.upstream_files(top, tree.checkout) == set(COMMITTED)
    assert vs.upstream_blob(top, tree.checkout, f"{ROOT}/util/b.h") == B_H
    with pytest.raises(vs.VendorError) as directory:
        vs.upstream_blob(tree.upstream, tree.checkout, "util")
    commit = tree.upstream.commit
    assert str(directory.value) == f"util is not a file in upstream cycles at {commit}"
