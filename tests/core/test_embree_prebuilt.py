"""tools/embree_prebuilt.py: the prebuilt-Embree helper of BOOT-0b.

The unit tests here run without cmake, without a compiler and without an Embree source tree: they
exercise the tool's pure functions on canned ``compile_commands.json`` entries in the exact shape
CMake writes (a ``directory`` and one ``command`` string). The two tests that do configure are
marked slow and take their prepared inputs from the environment variables
``PAINTERLY_EMBREE_SOURCE``, ``PAINTERLY_DOCTEST_SOURCE`` and ``PAINTERLY_EMBREE_INSTALL``; each
skips, naming the unset variable, only when one of them is unset, so `make check` stays offline and
quick on a machine without them. No path of any one machine is written here.
"""

import importlib.util
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL = REPO_ROOT / "tools" / "embree_prebuilt.py"


def _load_tool() -> ModuleType:
    """tools/embree_prebuilt.py, imported by path (tools/ is not a package)."""
    spec = importlib.util.spec_from_file_location("embree_prebuilt", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


embree_prebuilt = _load_tool()


def _entry(directory: str, command: str) -> dict[str, str]:
    """One compile_commands.json entry, as CMake writes it."""
    return {"directory": directory, "command": command, "file": "", "output": ""}


def test_embree_units_are_keyed_by_source_and_build_directories(tmp_path: Path) -> None:
    """An Embree unit is keyed by its source path and an outside unit is dropped."""
    source = tmp_path / "embree"
    build = tmp_path / "build"
    # Embree's CMakeLists.txt writes the per-ISA sources into the build directory's own
    # subdirectories (kernels/CMakeLists.txt:225,
    # SET(dst_file "${CMAKE_BINARY_DIR}/${src}.${isa}.cpp")).
    generated = build / "geometry"
    entries = [
        _entry(
            str(build),
            f"/usr/bin/c++ -O3 -o common/sys/CMakeFiles/sys.dir/sysinfo.cpp.o "
            f"-c {source}/common/sys/sysinfo.cpp",
        ),
        _entry(
            str(build),
            f"/usr/bin/c++ -O3 -o kernels/CMakeFiles/embree_avx2.dir/x.o "
            f"-c {generated}/bvh.cpp.avx2.cpp",
        ),
        # A translation unit of our own project, compiled in the same build directory: its object
        # is not under the Embree build directory, so it is not an Embree unit.
        _entry(
            str(build),
            f"/usr/bin/c++ -O3 -o src/painterly/CMakeFiles/x.dir/a.o -c {tmp_path}/src/a.cpp",
        ),
    ]
    units = embree_prebuilt.embree_units(entries, [source], build, build)
    assert sorted(units) == ["gen/geometry/bvh.cpp.avx2.cpp", "src/common/sys/sysinfo.cpp"]


def test_embree_units_normalise_the_source_and_build_paths(tmp_path: Path) -> None:
    """The -I of Embree's build directory becomes the build placeholder, not an absolute path."""
    source = tmp_path / "embree"
    build = tmp_path / "build"
    entries = [
        _entry(
            str(build),
            f"/usr/bin/c++ -I{build} -I{source}/include -o common/sys/sys.o -c "
            f"{source}/common/sys/sysinfo.cpp",
        )
    ]
    units = embree_prebuilt.embree_units(entries, [source], build, build)
    flags = units["src/common/sys/sysinfo.cpp"]
    assert f"-I{embree_prebuilt.BUILD_PLACEHOLDER}" in flags
    assert f"-I{embree_prebuilt.SRC_PLACEHOLDER}/include" in flags
    # The object and the source file arguments are removed: they are per-unit paths, not flags.
    assert "-o" not in flags
    assert "-c" not in flags


def test_a_nested_path_is_not_rewritten_by_its_parent(tmp_path: Path) -> None:
    """The source tree inside the build directory is the source placeholder, not the build one."""
    build = tmp_path / "build"
    source = build / "src"
    entries = [
        _entry(
            str(build),
            f"/usr/bin/c++ -I{build} -I{source} -o common/sys/sys.o -c {source}/common/sys.cpp",
        )
    ]
    units = embree_prebuilt.embree_units(entries, [source], build, build)
    assert units["src/common/sys.cpp"].count(f"-I{embree_prebuilt.SRC_PLACEHOLDER}") == 1


def test_compare_units_accepts_identical_maps(tmp_path: Path) -> None:
    """Equal flags for equal units: identical, and the count is the shared unit count."""
    units = {"src/a.cpp": ("-O3", "-fPIC"), "gen/b.cpp": ("-O3", "-mavx2")}
    comparison = embree_prebuilt.compare_units(units, dict(units))
    assert comparison.identical
    assert comparison.n_units == 2
    assert embree_prebuilt.render_report(comparison) == "EMBREE FLAGS IDENTICAL: 2 units\n"


def test_compare_units_reports_a_differing_flag() -> None:
    """One differing flag makes the comparison fail, and the report names the unit."""
    fetch = {"src/a.cpp": ("-O3", "-msse2")}
    install = {"src/a.cpp": ("-O3", "-msse4.2")}
    comparison = embree_prebuilt.compare_units(fetch, install)
    assert not comparison.identical
    assert comparison.differing == ["src/a.cpp"]
    report = embree_prebuilt.render_report(comparison)
    assert "src/a.cpp" in report
    assert "-msse2" in report
    assert "-msse4.2" in report


def test_compare_units_reports_a_unit_only_one_side_compiles() -> None:
    """A unit missing from one side fails the comparison, so a dropped unit cannot pass."""
    comparison = embree_prebuilt.compare_units({"src/a.cpp": ("-O3",)}, {})
    assert not comparison.identical
    assert comparison.only_fetch == ["src/a.cpp"]
    assert embree_prebuilt.render_report(comparison).startswith("EMBREE FLAGS DIFFER")


@pytest.mark.parametrize(
    ("units_fetch", "units_install"),
    [({}, {}), ({}, {"src/a.cpp": ("-O3",)}), ({"src/a.cpp": ("-O3",)}, {})],
    ids=["neither-side-has-a-unit", "only-the-install-has-a-unit", "only-fetch-has-a-unit"],
)
def test_a_comparison_with_no_unit_on_a_side_is_not_identical(
    units_fetch: dict[str, tuple[str, ...]], units_install: dict[str, tuple[str, ...]]
) -> None:
    """TQ.2 F3: "EMBREE FLAGS IDENTICAL: 0 units" cannot be printed - an empty side never passes."""
    comparison = embree_prebuilt.compare_units(units_fetch, units_install)
    assert not comparison.identical
    report = embree_prebuilt.render_report(comparison)
    assert report.startswith("EMBREE FLAGS DIFFER")
    assert "IDENTICAL" not in report
    # The report names how many units each side had, so the empty side is visible.
    assert f"compiled {len(units_fetch)} units" in report
    assert f"configure {len(units_install)}" in report


def test_compare_flags_exits_non_zero_when_no_side_has_a_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """TQ.2 F3: compare-flags on an empty comparison exits 1 and says the empty side proves nothing.

    The three configures are stubbed out (``configure`` does nothing, ``compile_commands`` returns
    no entry), which is exactly what a configure that compiles no Embree source leaves behind, so
    the test needs no cmake and no compiler. The inputs it does need are a source tree and an
    install directory with the two files the subcommand checks for.
    """
    source = tmp_path / "embree"
    source.mkdir()
    (source / "CMakeLists.txt").write_text("", encoding="utf-8")
    embree_dir = tmp_path / "install" / "lib" / f"cmake/embree-{embree_prebuilt.EMBREE_VERSION}"
    embree_dir.mkdir(parents=True)
    (embree_dir / "embree-config.cmake").write_text("", encoding="utf-8")
    monkeypatch.setattr(embree_prebuilt, "configure", lambda *args, **kwargs: None)
    monkeypatch.setattr(embree_prebuilt, "compile_commands", lambda build_dir: [])
    result = embree_prebuilt.main(
        [
            "compare-flags",
            "--source",
            str(source),
            "--embree-dir",
            str(embree_dir),
            "--keep",
            str(tmp_path / "configure"),
        ]
    )
    printed = capsys.readouterr().out
    assert result == 1
    assert "EMBREE FLAGS IDENTICAL" not in printed
    assert "EMBREE FLAGS DIFFER: 0 units compared" in printed
    assert "compiled 0 units" in printed
    assert "not identical" in printed


def test_config_file_holds_every_embree_option_and_the_shared_settings() -> None:
    """The shared file is the one source of truth: the options and the settings are in it."""
    text = embree_prebuilt.CONFIG_FILE.read_text(encoding="utf-8")
    # Every EMBREE_* option cmake/painterly_embree.cmake set before BOOT-0b, with its value.
    for option in (
        "EMBREE_STATIC_LIB ON",
        "EMBREE_API_NAMESPACE painterly_embree",
        "EMBREE_LIBRARY_NAME painterly_embree",
        "EMBREE_TASKING_SYSTEM INTERNAL",
        "EMBREE_ISPC_SUPPORT OFF",
        "EMBREE_TUTORIALS OFF",
        "EMBREE_GEOMETRY_TRIANGLE ON",
        "EMBREE_GEOMETRY_INSTANCE ON",
        "EMBREE_GEOMETRY_QUAD OFF",
        "EMBREE_GEOMETRY_CURVE OFF",
        "EMBREE_GEOMETRY_SUBDIVISION OFF",
        "EMBREE_GEOMETRY_USER OFF",
        "EMBREE_GEOMETRY_INSTANCE_ARRAY OFF",
        "EMBREE_GEOMETRY_GRID OFF",
        "EMBREE_GEOMETRY_POINT OFF",
        "EMBREE_RAY_MASK ON",
        "EMBREE_BACKFACE_CULLING OFF",
        "EMBREE_STAT_COUNTERS OFF",
        "EMBREE_INSTALL_DEPENDENCIES OFF",
        "EMBREE_ZIP_MODE OFF",
    ):
        assert option in text, f"{option} is not in {embree_prebuilt.CONFIG_FILE}"
    # The project settings that reach Embree through FetchContent (BOOT-0b's list).
    for setting in (
        "CMAKE_CXX_STANDARD 20",
        "CMAKE_POSITION_INDEPENDENT_CODE ON",
        "CMAKE_CXX_VISIBILITY_PRESET hidden",
        "CMAKE_VISIBILITY_INLINES_HIDDEN ON",
        "CMAKE_MSVC_RUNTIME_LIBRARY",
        "-ffp-contract=off -fno-fast-math",
        "/fp:precise",
    ):
        assert setting in text, f"{setting} is not in {embree_prebuilt.CONFIG_FILE}"


def test_root_and_embree_module_include_the_shared_config() -> None:
    """Both the root CMakeLists.txt and cmake/painterly_embree.cmake include the shared file."""
    root = (REPO_ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    embree = (REPO_ROOT / "cmake" / "painterly_embree.cmake").read_text(encoding="utf-8")
    assert "painterly_embree_config.cmake" in root
    assert "painterly_embree_config.cmake" in embree


def test_embree_module_uses_find_package_for_a_prebuilt_install() -> None:
    """embree_DIR takes the prebuilt path and prints the prebuilt line; unset takes FetchContent."""
    embree = (REPO_ROOT / "cmake" / "painterly_embree.cmake").read_text(encoding="utf-8")
    assert "find_package(embree 4.4.1 EXACT CONFIG REQUIRED)" in embree
    assert "painterly_embree: prebuilt" in embree
    assert "FetchContent_Declare(" in embree
    # The interface target keeps its name on both paths.
    assert embree.count("add_library(painterly_embree INTERFACE)") == 2
    assert embree.count("target_link_libraries(painterly_embree INTERFACE embree)") == 2


def test_embree_install_prefix_is_git_ignored() -> None:
    """build/ is git-ignored, so build/embree-install is too (the item's Outcome)."""
    gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "build/" in gitignore


# The prepared inputs of the two configure tests, as environment variables: this file holds no path
# of any one machine (AGENTS.md "Environment"; RULINGS S1). The first is the Embree v4.4.1 source
# tree, the second the doctest source tree (the configure is offline, so FetchContent reads both
# from disk), and the third is an install prefix made by `build` - the directory whose
# lib/cmake/embree-4.4.1 an embree_DIR takes.
EMBREE_SOURCE_VARIABLE = "PAINTERLY_EMBREE_SOURCE"
DOCTEST_SOURCE_VARIABLE = "PAINTERLY_DOCTEST_SOURCE"
EMBREE_INSTALL_VARIABLE = "PAINTERLY_EMBREE_INSTALL"
PREPARED_INPUT_VARIABLES = (
    EMBREE_SOURCE_VARIABLE,
    DOCTEST_SOURCE_VARIABLE,
    EMBREE_INSTALL_VARIABLE,
)


@dataclass(frozen=True)
class PreparedInputs:
    """The prepared directories the two configure tests take, as absolute paths."""

    embree_source: Path
    doctest_source: Path
    embree_install: Path

    @property
    def embree_dir(self) -> Path:
        """The install's CMake package directory: the value ``embree_DIR`` takes."""
        return self.embree_install / "lib" / f"cmake/embree-{embree_prebuilt.EMBREE_VERSION}"

    @property
    def fetchcontent_source_dirs(self) -> dict[str, Path]:
        """FETCHCONTENT_SOURCE_DIR_<name> for both dependency source trees, names as CMake uses."""
        return {"EMBREE": self.embree_source, "DOCTEST": self.doctest_source}


def _prepared_inputs(environ: Mapping[str, str] | None = None) -> PreparedInputs:
    """The prepared inputs named by the environment variables, or a skip naming the unset ones.

    A variable that is set is taken as it is: the test then fails on a wrong directory rather than
    skipping, so a mistyped path cannot turn the proof into a silent pass.
    """
    source = os.environ if environ is None else environ
    unset = [name for name in PREPARED_INPUT_VARIABLES if not source.get(name)]
    if unset:
        pytest.skip(f"{' and '.join(unset)} unset: no prepared Embree inputs on this machine")
    return PreparedInputs(
        embree_source=Path(source[EMBREE_SOURCE_VARIABLE]),
        doctest_source=Path(source[DOCTEST_SOURCE_VARIABLE]),
        embree_install=Path(source[EMBREE_INSTALL_VARIABLE]),
    )


@pytest.mark.slow
def test_prebuilt_install_is_not_rebuilt_by_the_project(tmp_path: Path) -> None:
    """A project configure with embree_DIR compiles no Embree source at all."""
    prepared = _prepared_inputs()
    build_dir = tmp_path / "prebuilt"
    definitions = {
        "PAINTERLY_BUILD_MODULE": "ON",
        "PAINTERLY_BUILD_TESTS": "OFF",
        "PAINTERLY_BUILD_ORACLE": "OFF",
        "CMAKE_BUILD_TYPE": "Release",
        "CMAKE_EXPORT_COMPILE_COMMANDS": "ON",
        "Python_EXECUTABLE": sys.executable,
        "FETCHCONTENT_FULLY_DISCONNECTED": "ON",
        "embree_DIR": str(prepared.embree_dir),
    }
    for name, path in prepared.fetchcontent_source_dirs.items():
        definitions[f"FETCHCONTENT_SOURCE_DIR_{name}"] = str(path)
    embree_prebuilt.configure(build_dir, REPO_ROOT, definitions)
    entries = embree_prebuilt.compile_commands(build_dir)
    units = embree_prebuilt.embree_units(
        entries, [prepared.embree_source], build_dir / "_deps" / "embree-build", build_dir
    )
    assert units == {}


@pytest.mark.slow
def test_compare_flags_reports_identical_flags(tmp_path: Path) -> None:
    """compare-flags, run against the built install, prints EMBREE FLAGS IDENTICAL and exits 0."""
    prepared = _prepared_inputs()
    result = embree_prebuilt.main(
        [
            "compare-flags",
            "--source",
            str(prepared.embree_source),
            "--embree-dir",
            str(prepared.embree_dir),
            "--keep",
            str(tmp_path / "configure"),
        ]
    )
    assert result == 0


def test_the_report_line_is_exactly_the_items_format() -> None:
    """The line the item names, with n = the number of shared units."""
    comparison = embree_prebuilt.compare_units({"src/a.cpp": ("-O3",)}, {"src/a.cpp": ("-O3",)})
    assert embree_prebuilt.render_report(comparison).strip() == "EMBREE FLAGS IDENTICAL: 1 units"
