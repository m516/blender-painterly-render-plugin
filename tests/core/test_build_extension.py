"""`tools/build_extension.py`: wheel names, platforms, zip names and staging (T8.1).

The tool is imported by file path, as `tests/core/test_symbol_audit_parsers.py` imports
`tools/symbol_audit.py`: `tools/` is not a package. Nothing here runs Blender, so the tests are
fast; `tests/blender_it/test_release_package.py` runs the real build.

A synthetic wheel is a zip with one member, `painterly_core-<version>.dist-info/WHEEL`, holding
`Wheel-Version: 1.0\\n`. Blender's build never opens a wheel, so a synthetic wheel is packed exactly
like a real one.
"""

import importlib.util
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
BUILD_TOOL = REPO_ROOT / "tools" / "build_extension.py"
RELEASE_TOOL = REPO_ROOT / "tools" / "release.py"


def _load_by_path(name: str, path: Path) -> ModuleType:
    """Import a tool by file path; `tools/` is not a package."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None, f"no module spec for {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


build_extension = _load_by_path("build_extension", BUILD_TOOL)
release = _load_by_path("release", RELEASE_TOOL)

VERSION = release.release_version(REPO_ROOT)
# The stable-ABI python tag of the wheels: pyproject.toml [tool.scikit-build] wheel.py-api.
PYTHON_TAG = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"][
    "scikit-build"
]["wheel"]["py-api"]

# The platform tag sets of the three release wheels (PEP 425, PEP 600): the manylinux x86_64 tag
# set that auditwheel writes on the manylinux_2_28 image, macOS arm64 at deployment target 11.0, and
# win_amd64 (pyproject.toml, [tool.cibuildwheel]).
LINUX_TAGS = "manylinux_2_27_x86_64.manylinux_2_28_x86_64"
MACOS_TAGS = "macosx_11_0_arm64"
WINDOWS_TAGS = "win_amd64"
STANDARD_TAG_SETS = (LINUX_TAGS, MACOS_TAGS, WINDOWS_TAGS)


def standard_wheel_name(platform_tags: str) -> str:
    """The wheel file name of one platform tag set, PEP 427."""
    return f"painterly_core-{VERSION}-{PYTHON_TAG}-abi3-{platform_tags}.whl"


def write_synthetic_wheel(directory: Path, name: str) -> Path:
    """Write a synthetic wheel named ``name`` into ``directory`` and return its path."""
    path = directory / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"painterly_core-{VERSION}.dist-info/WHEEL", "Wheel-Version: 1.0\n")
    return path


def standard_wheels(directory: Path) -> list[Path]:
    """The three standard synthetic wheels, in `RELEASE_PLATFORMS` order."""
    return [
        write_synthetic_wheel(directory, standard_wheel_name(tags)) for tags in STANDARD_TAG_SETS
    ]


def test_parse_wheel_filename_reads_the_pep_427_fields() -> None:
    assert build_extension.parse_wheel_filename(standard_wheel_name(LINUX_TAGS)) == (
        build_extension.WheelName("painterly_core", VERSION, None, PYTHON_TAG, "abi3", LINUX_TAGS)
    )
    assert build_extension.parse_wheel_filename(standard_wheel_name(MACOS_TAGS)).platform == (
        MACOS_TAGS
    )
    assert build_extension.parse_wheel_filename(standard_wheel_name(WINDOWS_TAGS)).platform == (
        WINDOWS_TAGS
    )


def test_parse_wheel_filename_reads_a_build_tag() -> None:
    parsed = build_extension.parse_wheel_filename(
        f"painterly_core-0.1.0-1-{PYTHON_TAG}-abi3-win_amd64.whl"
    )
    assert parsed.build == "1"
    assert parsed.platform == WINDOWS_TAGS


@pytest.mark.parametrize(
    "name",
    [
        "x-1.0-py3-none.whl",  # four dash-separated fields
        "a-b-c-d-e-f-g.whl",  # seven
        f"painterly_core-{VERSION}-{PYTHON_TAG}-abi3-win_amd64.zip",  # not a wheel
    ],
)
def test_parse_wheel_filename_refuses_a_non_wheel_name(name: str) -> None:
    with pytest.raises(ValueError):
        build_extension.parse_wheel_filename(name)


@pytest.mark.parametrize(
    ("platform_tags", "expected"),
    [
        ("linux_x86_64", "linux-x64"),
        ("manylinux_2_28_x86_64", "linux-x64"),
        (LINUX_TAGS, "linux-x64"),
        ("manylinux_2_17_x86_64.manylinux2014_x86_64", "linux-x64"),
        (MACOS_TAGS, "macos-arm64"),
        (WINDOWS_TAGS, "windows-x64"),
    ],
)
def test_blender_platform_from_wheel(tmp_path: Path, platform_tags: str, expected: str) -> None:
    wheel = write_synthetic_wheel(tmp_path, standard_wheel_name(platform_tags))
    assert build_extension.blender_platform_from_wheel(wheel) == expected


@pytest.mark.parametrize(
    "platform_tags",
    [
        "macosx_11_0_x86_64",
        "macosx_10_9_universal2",
        "win32",
        "win_arm64",
        "musllinux_1_2_x86_64",
        "manylinux_2_28_aarch64",
        "any",
        f"{LINUX_TAGS}.{WINDOWS_TAGS}",
    ],
)
def test_blender_platform_from_wheel_refuses_another_platform(
    tmp_path: Path, platform_tags: str
) -> None:
    wheel = write_synthetic_wheel(tmp_path, standard_wheel_name(platform_tags))
    with pytest.raises(ValueError):
        build_extension.blender_platform_from_wheel(wheel)


def test_extension_zip_name_matches_blender_split_platforms() -> None:
    assert build_extension.extension_zip_name("painterly", "0.1.0", "linux-x64") == (
        "painterly-0.1.0-linux_x64.zip"
    )
    assert build_extension.extension_zip_name("painterly", "0.1.0", "macos-arm64") == (
        "painterly-0.1.0-macos_arm64.zip"
    )
    assert build_extension.extension_zip_name("painterly", "0.1.0", "windows-x64") == (
        "painterly-0.1.0-windows_x64.zip"
    )


def _addon_files(addon_dir: Path) -> list[Path]:
    """Every file of the add-on package, outside ``__pycache__/`` and the manifest."""
    return sorted(
        path
        for path in addon_dir.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.name != "blender_manifest.toml"
    )


def test_stage_extension_empties_the_directory_and_stages_every_file(tmp_path: Path) -> None:
    wheels = standard_wheels(tmp_path / "wheelhouse")
    staging = tmp_path / "staging"
    stale = staging / "wheels" / "stale-0.0.1-py3-none-any.whl"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"a wheel of an earlier run\n")

    platforms = build_extension.stage_extension(wheels, staging)

    # A stale wheel would ship in every zip: Blender packs every unlisted file under the source dir.
    assert not stale.exists()
    assert platforms == list(release.RELEASE_PLATFORMS)
    manifest = tomllib.loads((staging / "blender_manifest.toml").read_text(encoding="utf-8"))
    source = release.read_manifest(REPO_ROOT)
    assert manifest["platforms"] == list(release.RELEASE_PLATFORMS)
    assert manifest["wheels"] == [f"./wheels/{wheel.name}" for wheel in wheels]
    assert {
        key: value for key, value in manifest.items() if key not in ("platforms", "wheels")
    } == (source)

    for wheel in wheels:
        assert (staging / "wheels" / wheel.name).read_bytes() == wheel.read_bytes()
    for name in (*build_extension.LICENCE_FILES,):
        assert (staging / name).read_bytes() == (REPO_ROOT / name).read_bytes()
    for licence in sorted((REPO_ROOT / build_extension.LICENCE_DIR).iterdir()):
        if licence.is_file():
            staged = staging / build_extension.LICENCE_DIR / licence.name
            assert staged.read_bytes() == licence.read_bytes()
    for path in _addon_files(build_extension.ADDON_DIR):
        relative = path.relative_to(build_extension.ADDON_DIR)
        assert (staging / relative).read_bytes() == path.read_bytes()


def test_stage_extension_refuses_two_wheels_of_one_platform(tmp_path: Path) -> None:
    wheels = [
        write_synthetic_wheel(tmp_path, standard_wheel_name("manylinux_2_28_x86_64")),
        write_synthetic_wheel(tmp_path, standard_wheel_name("linux_x86_64")),
    ]
    with pytest.raises(ValueError):
        build_extension.stage_extension(wheels, tmp_path / "staging")


def test_stage_extension_refuses_no_wheel(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        build_extension.stage_extension([], tmp_path / "staging")


def test_stage_extension_never_overwrites_an_add_on_file(tmp_path: Path) -> None:
    addon_dir = tmp_path / "addon"
    shutil.copytree(
        build_extension.ADDON_DIR, addon_dir, ignore=shutil.ignore_patterns("__pycache__")
    )
    (addon_dir / "LICENSE").write_text("an add-on file named LICENSE\n", encoding="utf-8")
    wheels = standard_wheels(tmp_path / "wheelhouse")
    with pytest.raises(FileExistsError):
        build_extension.stage_extension(wheels, tmp_path / "staging", addon_dir=addon_dir)


@pytest.mark.parametrize("tool", [BUILD_TOOL, RELEASE_TOOL], ids=["build_extension", "release"])
def test_the_tools_are_standard_library_only(tool: Path) -> None:
    # -S removes site-packages, so a non-stdlib import fails; run_name is not __main__, so main()
    # does not run.
    proc = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-c",
            "import runpy, sys; runpy.run_path(sys.argv[1], run_name='stdlib_check')",
            str(tool),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr
