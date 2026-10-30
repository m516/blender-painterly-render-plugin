"""`tools/release.py`: versions, tags, wheel checks, the source tarball and the checksums (T8.1).

The tool is imported by file path, as `tests/core/test_symbol_audit_parsers.py` imports
`tools/symbol_audit.py`: `tools/` is not a package. Nothing here runs Blender, so the tests are
fast; `tests/blender_it/test_release_package.py` runs the real package step. git is required.

Every comparison is exact: a byte differs or it does not.
"""

import hashlib
import importlib.util
import io
import subprocess
import sys
import tarfile
import tomllib
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
RELEASE_TOOL = REPO_ROOT / "tools" / "release.py"

# The platform tag sets of the three release wheels (PEP 425, PEP 600): the manylinux x86_64 tag
# set that auditwheel writes on the manylinux_2_28 image, macOS arm64 at deployment target 11.0, and
# win_amd64 (pyproject.toml, [tool.cibuildwheel]).
LINUX_TAGS = "manylinux_2_27_x86_64.manylinux_2_28_x86_64"
MACOS_TAGS = "macosx_11_0_arm64"
WINDOWS_TAGS = "win_amd64"
STANDARD_TAG_SETS = (LINUX_TAGS, MACOS_TAGS, WINDOWS_TAGS)


def _load_by_path(name: str, path: Path) -> ModuleType:
    """Import a tool by file path; `tools/` is not a package."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"no module spec for {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


release = _load_by_path("release", RELEASE_TOOL)

VERSION = release.release_version(REPO_ROOT)
EXTENSION_ID = release.read_manifest(REPO_ROOT)["id"]
PYPROJECT = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
PYTHON_TAG = PYPROJECT["tool"]["scikit-build"]["wheel"]["py-api"]


def standard_wheel_name(version: str, platform_tags: str) -> str:
    """The wheel file name of one platform tag set, PEP 427."""
    return f"painterly_core-{version}-{PYTHON_TAG}-abi3-{platform_tags}.whl"


def write_synthetic_wheel(directory: Path, name: str) -> Path:
    """Write a synthetic wheel named ``name`` into ``directory`` and return its path.

    Blender's build never opens a wheel, so a zip with the one ``WHEEL`` member is packed exactly
    like a real wheel.
    """
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"painterly_core-{VERSION}.dist-info/WHEEL", "Wheel-Version: 1.0\n")
    return path


def standard_wheels(directory: Path, version: str = VERSION) -> list[Path]:
    """The three standard synthetic wheels, in `RELEASE_PLATFORMS` order."""
    return [
        write_synthetic_wheel(directory, standard_wheel_name(version, tags))
        for tags in STANDARD_TAG_SETS
    ]


def test_source_versions_names_the_three_sources_and_they_agree() -> None:
    versions = release.source_versions(REPO_ROOT)
    assert tuple(versions) == release.VERSION_SOURCES
    assert set(versions.values()) == {VERSION}


def _write_version_sources(root: Path, *, manifest: str, pyproject: str, cmake: str) -> None:
    """Write the three version sources under ``root``."""
    addon = root / "src" / "blender" / "addon"
    addon.mkdir(parents=True, exist_ok=True)
    (addon / "blender_manifest.toml").write_text(manifest, encoding="utf-8")
    (root / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    (root / "CMakeLists.txt").write_text(cmake, encoding="utf-8")


def test_release_version_names_every_source_when_they_disagree(tmp_path: Path) -> None:
    _write_version_sources(
        tmp_path,
        manifest='id = "painterly"\nversion = "0.1.0"\n',
        pyproject='[project]\nname = "painterly-core"\nversion = "0.1.1"\n',
        cmake="project(painterly VERSION 0.1.0 LANGUAGES C CXX)\n",
    )
    with pytest.raises(release.ReleaseError) as raised:
        release.release_version(tmp_path)
    message = str(raised.value)
    for name in release.VERSION_SOURCES:
        assert name in message
    assert "0.1.0" in message
    assert "0.1.1" in message


@pytest.mark.parametrize(
    ("cmake", "manifest", "pyproject", "expected"),
    [
        # No VERSION at all.
        (
            "project(painterly LANGUAGES C CXX)\n",
            'version = "0.1.0"\n',
            '[project]\nversion = "0.1.0"\n',
            "CMakeLists.txt",
        ),
        # A four-component version is no `project(painterly VERSION X.Y.Z` line.
        (
            "project(painterly VERSION 0.1.0.1)\n",
            'version = "0.1.0"\n',
            '[project]\nversion = "0.1.0"\n',
            "CMakeLists.txt",
        ),
        # The manifest has no version key.
        (
            "project(painterly VERSION 0.1.0)\n",
            'id = "painterly"\n',
            '[project]\nversion = "0.1.0"\n',
            "blender_manifest.toml",
        ),
        # pyproject is not valid TOML.
        (
            "project(painterly VERSION 0.1.0)\n",
            'version = "0.1.0"\n',
            "[project\n",
            "pyproject.toml",
        ),
    ],
    ids=["cmake-no-version", "cmake-four-components", "manifest-no-version", "pyproject-bad-toml"],
)
def test_release_version_names_the_offending_file(
    tmp_path: Path, cmake: str, manifest: str, pyproject: str, expected: str
) -> None:
    _write_version_sources(tmp_path, manifest=manifest, pyproject=pyproject, cmake=cmake)
    with pytest.raises(release.ReleaseError) as raised:
        release.release_version(tmp_path)
    assert expected in str(raised.value)


@pytest.mark.parametrize(("tag", "expected"), [("v0.1.0", "release")])
def test_classify_tag_reads_a_release_tag(tag: str, expected: str) -> None:
    assert release.classify_tag(tag, "0.1.0") == expected


@pytest.mark.parametrize("tag", ["v0.1.0-dryrun.1", "v0.1.0-dryrun.12"])
def test_classify_tag_reads_a_dry_run_tag(tag: str) -> None:
    assert release.classify_tag(tag, "0.1.0") == "dry-run"


@pytest.mark.parametrize(
    "tag",
    [
        "v0.2.0",
        "v0.2.0-dryrun.1",
        "v0.1.0-rc.1",
        "v0.1",
        "0.1.0",
        "v0.1.0-dryrun.",
        "v0.1.0-dryrun.1x",
        "v0.1.0-dryrun",
        "refs/tags/v0.1.0",
    ],
)
def test_classify_tag_refuses_another_tag(tag: str) -> None:
    with pytest.raises(release.ReleaseError):
        release.classify_tag(tag, "0.1.0")


def _run_release(*args: str) -> subprocess.CompletedProcess[str]:
    """Run `tools/release.py` under `-I` from the repository root."""
    return subprocess.run(
        [sys.executable, "-I", str(RELEASE_TOOL), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_plan_reads_a_release_tag() -> None:
    proc = _run_release("plan", "--tag", f"v{VERSION}")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == f"mode=release\nversion={VERSION}\n"


@pytest.mark.parametrize("args", [("--tag", f"v{VERSION}-dryrun.3"), ("--dispatch",)])
def test_plan_reads_a_dry_run(args: tuple[str, ...]) -> None:
    proc = _run_release("plan", *args)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == f"mode=dry-run\nversion={VERSION}\n"


def test_plan_fails_without_output_for_another_tag() -> None:
    proc = _run_release("plan", "--tag", f"v{VERSION}-rc.1")
    assert proc.returncode == 1
    assert proc.stdout == ""
    assert f"v{VERSION}-rc.1" in proc.stderr


def test_zip_name_prints_the_zip_of_a_platform() -> None:
    proc = _run_release("zip-name", "--platform", "windows-x64")
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout == f"{EXTENSION_ID}-{VERSION}-windows_x64.zip\n"


def test_asset_names_are_sorted_and_number_five() -> None:
    assert release.asset_names("painterly", "0.1.0") == [
        "SHA256SUMS",
        "painterly-0.1.0-linux_x64.zip",
        "painterly-0.1.0-macos_arm64.zip",
        "painterly-0.1.0-source.tar.gz",
        "painterly-0.1.0-windows_x64.zip",
    ]


def test_check_wheels_maps_each_platform_to_its_wheel(tmp_path: Path) -> None:
    wheels = standard_wheels(tmp_path)
    assert release.check_wheels(tmp_path, REPO_ROOT) == {
        platform: wheel for platform, wheel in zip(release.RELEASE_PLATFORMS, wheels, strict=True)
    }


def _bumped(version: str) -> str:
    """``version`` with its last component incremented by one."""
    *head, last = version.split(".")
    return ".".join([*head, str(int(last) + 1)])


@pytest.mark.parametrize(
    "damage",
    [
        "macos-missing",
        "extra-manylinux",
        "unrepaired-linux",
        "bumped-version",
        "cp313-wheel",
        "foreign-distribution",
        "extra-file",
    ],
)
def test_check_wheels_refuses_another_wheel_set(tmp_path: Path, damage: str) -> None:
    wheels = standard_wheels(tmp_path)
    linux, macos, windows = wheels
    if damage == "macos-missing":
        macos.unlink()
    elif damage == "extra-manylinux":
        write_synthetic_wheel(tmp_path, standard_wheel_name(VERSION, "manylinux_2_28_x86_64"))
    elif damage == "unrepaired-linux":
        linux.unlink()
        write_synthetic_wheel(tmp_path, standard_wheel_name(VERSION, "linux_x86_64"))
    elif damage == "bumped-version":
        macos.unlink()
        write_synthetic_wheel(tmp_path, standard_wheel_name(_bumped(VERSION), MACOS_TAGS))
    elif damage == "cp313-wheel":
        windows.unlink()
        write_synthetic_wheel(tmp_path, f"painterly_core-{VERSION}-cp313-cp313-win_amd64.whl")
    elif damage == "foreign-distribution":
        windows.unlink()
        write_synthetic_wheel(tmp_path, f"other_pkg-{VERSION}-{PYTHON_TAG}-abi3-win_amd64.whl")
    else:
        (tmp_path / "notes.txt").write_text("not a wheel\n", encoding="utf-8")
    with pytest.raises(release.ReleaseError):
        release.check_wheels(tmp_path, REPO_ROOT)


@pytest.fixture(scope="module")
def source_tarball(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """`git archive` of HEAD, written once for the tarball tests."""
    out_dir = tmp_path_factory.mktemp("tarball")
    return release.write_source_tarball(REPO_ROOT, out_dir)


def test_source_tarball_is_the_tracked_tree(source_tarball: Path) -> None:
    assert source_tarball.name == release.source_tarball_name(EXTENSION_ID, VERSION)
    release.verify_source_tarball(source_tarball, REPO_ROOT)
    with tarfile.open(source_tarball, "r:gz") as archive:
        regular = [member for member in archive.getmembers() if member.isreg()]
    assert len(regular) == len(release.git_tree(REPO_ROOT))


def _rebuild(
    source: Path,
    target: Path,
    *,
    append: bytes | None = None,
    drop: str | None = None,
    extra: bool = False,
    comment: str | None = None,
) -> None:
    """Copy ``source`` to ``target`` with one tampering applied.

    ``tarfile`` writes the global pax headers when the archive is opened, so the ``comment``
    variant sets them in the ``pax_headers`` argument, before any member is added.
    """
    prefix = f"{EXTENSION_ID}-{VERSION}/"
    with tarfile.open(source, "r:gz") as tin:
        pax = dict(tin.pax_headers)
    if comment is not None:
        pax["comment"] = comment
    with (
        tarfile.open(source, "r:gz") as tin,
        tarfile.open(target, "w:gz", format=tarfile.PAX_FORMAT, pax_headers=pax) as tout,
    ):
        for member in tin.getmembers():
            if member.name == f"{prefix}LICENSE" and drop is not None:
                continue
            if not member.isreg():
                tout.addfile(member)
                continue
            data = tin.extractfile(member)
            assert data is not None
            contents = data.read()
            if member.name == f"{prefix}LICENSE" and append is not None:
                contents += append
            info = tarfile.TarInfo(member.name)
            info.mode = member.mode
            info.mtime = member.mtime
            info.size = len(contents)
            tout.addfile(info, io.BytesIO(contents))
        if extra:
            contents = b"not a tracked file\n"
            info = tarfile.TarInfo(f"{prefix}EXTRA")
            info.mode = 0o644
            info.size = len(contents)
            tout.addfile(info, io.BytesIO(contents))


def test_verify_source_tarball_refuses_a_changed_file(source_tarball: Path, tmp_path: Path) -> None:
    tampered = tmp_path / "changed.tar.gz"
    _rebuild(source_tarball, tampered, append=b"\n")
    with pytest.raises(release.ReleaseError, match="LICENSE"):
        release.verify_source_tarball(tampered, REPO_ROOT)


def test_verify_source_tarball_refuses_a_missing_file(source_tarball: Path, tmp_path: Path) -> None:
    tampered = tmp_path / "dropped.tar.gz"
    _rebuild(source_tarball, tampered, drop="LICENSE")
    with pytest.raises(release.ReleaseError, match="LICENSE"):
        release.verify_source_tarball(tampered, REPO_ROOT)


def test_verify_source_tarball_refuses_an_extra_file(source_tarball: Path, tmp_path: Path) -> None:
    tampered = tmp_path / "extra.tar.gz"
    _rebuild(source_tarball, tampered, extra=True)
    with pytest.raises(release.ReleaseError, match="EXTRA"):
        release.verify_source_tarball(tampered, REPO_ROOT)


def test_verify_source_tarball_refuses_another_commit(source_tarball: Path, tmp_path: Path) -> None:
    tampered = tmp_path / "other-commit.tar.gz"
    _rebuild(source_tarball, tampered, comment="0" * 40)
    head = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    with pytest.raises(release.ReleaseError) as raised:
        release.verify_source_tarball(tampered, REPO_ROOT)
    assert head in str(raised.value)


def test_git_tree_refuses_a_non_sha1_repository(tmp_path: Path) -> None:
    subprocess.run(
        ["git", "init", "--object-format=sha256", str(tmp_path)],
        capture_output=True,
        text=True,
        check=True,
    )
    with pytest.raises(release.ReleaseError) as raised:
        release.git_tree(tmp_path)
    message = str(raised.value)
    assert "sha256" in message
    assert str(tmp_path) in message


def test_write_sha256sums_hashes_every_other_file(tmp_path: Path) -> None:
    (tmp_path / "b.zip").write_bytes(b"b")
    (tmp_path / "a.tar.gz").write_bytes(b"a")
    path = release.write_sha256sums(tmp_path)
    expected = "".join(
        f"{hashlib.sha256(data).hexdigest()}  {name}\n"
        for name, data in [("a.tar.gz", b"a"), ("b.zip", b"b")]
    )
    assert path.read_bytes() == expected.encode("utf-8")
    # SHA256SUMS never hashes itself, so a second run gives the same bytes.
    assert release.write_sha256sums(tmp_path).read_bytes() == expected.encode("utf-8")


def test_write_notes_lists_every_hashed_file(tmp_path: Path) -> None:
    (tmp_path / "b.zip").write_bytes(b"b")
    (tmp_path / "a.tar.gz").write_bytes(b"a")
    release.write_sha256sums(tmp_path)
    notes = tmp_path / "notes.md"
    release.write_notes(notes, tmp_path, REPO_ROOT)
    text = notes.read_text(encoding="utf-8")
    rows = [
        f"| `{name}` | {(tmp_path / name).stat().st_size} | `{hashlib.sha256(data).hexdigest()}` |"
        for name, data in [("a.tar.gz", b"a"), ("b.zip", b"b")]
    ]
    positions = [text.index(row) for row in rows]
    assert positions == sorted(positions)
    head = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert head in text
