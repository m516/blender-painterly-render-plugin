"""Cycles' SVM interpreter as the build generates and compiles it (card T6.3).

The generated switch and the 22 vendored headers are build inputs, so these tests read the build
tree and the committed manifest rather than compiling anything themselves. The doctests that run
the switch are src/test/test_cycles_svm_stack_nodes.cpp; `make check` runs them through ctest.
"""

import re
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDORED = REPO_ROOT / "third_party" / "cycles" / "VENDORED.toml"
MANIFEST = REPO_ROOT / "src" / "cycles" / "svm_nodes.toml"
HEADERS_CHECK = REPO_ROOT / "src" / "cycles" / "svm_headers_check.cpp"
GENERATED_HEADER = Path("src/cycles/generated/svm_eval_nodes.h")

# The 22 headers card T6.3 vendors, relative to intern/cycles ("Vendored files").
VENDORED_HEADERS = [
    "kernel/svm/util.h",
    "kernel/svm/node_types.h",
    "kernel/svm/value.h",
    "kernel/svm/math.h",
    "kernel/svm/math_util.h",
    "kernel/svm/mix.h",
    "kernel/svm/color_util.h",
    "kernel/svm/map_range.h",
    "kernel/svm/clamp.h",
    "kernel/svm/invert.h",
    "kernel/svm/gamma.h",
    "kernel/svm/brightness.h",
    "kernel/svm/hsv.h",
    "kernel/svm/sepcomb_color.h",
    "kernel/svm/sepcomb_vector.h",
    "kernel/svm/convert.h",
    "kernel/svm/ramp.h",
    "kernel/svm/ramp_util.h",
    "kernel/svm/mapping.h",
    "kernel/svm/mapping_util.h",
    "kernel/tables.h",
    "kernel/util/colorspace.h",
]

# The 39 cases of src/cycles/svm_nodes.toml: T6.2's four control-flow cases and T6.3's 35.
STACK_CASES = [
    "NODE_END",
    "NODE_SHADER_JUMP",
    "NODE_JUMP_IF_ZERO",
    "NODE_JUMP_IF_ONE",
    "NODE_CONVERT",
    "NODE_CONVERT_DERIVATIVE",
    "NODE_VALUE_F",
    "NODE_VALUE_F_DERIVATIVE",
    "NODE_VALUE_V",
    "NODE_VALUE_V_DERIVATIVE",
    "NODE_HSV",
    "NODE_MATH",
    "NODE_VECTOR_MATH",
    "NODE_VECTOR_MATH_DERIVATIVE",
    "NODE_RGB_RAMP",
    "NODE_GAMMA",
    "NODE_BRIGHTCONTRAST",
    "NODE_TEXTURE_MAPPING",
    "NODE_TEXTURE_MAPPING_DERIVATIVE",
    "NODE_MAPPING",
    "NODE_MAPPING_DERIVATIVE",
    "NODE_MIN_MAX",
    "NODE_CURVES",
    "NODE_INVERT",
    "NODE_MIX",
    "NODE_SEPARATE_COLOR",
    "NODE_COMBINE_COLOR",
    "NODE_SEPARATE_VECTOR",
    "NODE_SEPARATE_VECTOR_DERIVATIVE",
    "NODE_COMBINE_VECTOR",
    "NODE_COMBINE_VECTOR_DERIVATIVE",
    "NODE_MAP_RANGE",
    "NODE_VECTOR_MAP_RANGE",
    "NODE_CLAMP",
    "NODE_FLOAT_CURVE",
    "NODE_MIX_COLOR",
    "NODE_MIX_FLOAT",
    "NODE_MIX_VECTOR",
    "NODE_MIX_VECTOR_NON_UNIFORM",
]

# The 19 includes: T6.2's five, then the 14 evaluator headers, in the order of svm.h:36-80.
INCLUDES = [
    "kernel/globals.h",
    "kernel/types.h",
    "kernel/svm/types.h",
    "kernel/svm/util.h",
    "kernel/svm/node_types.h",
    "kernel/svm/brightness.h",
    "kernel/svm/clamp.h",
    "kernel/svm/convert.h",
    "kernel/svm/gamma.h",
    "kernel/svm/hsv.h",
    "kernel/svm/invert.h",
    "kernel/svm/map_range.h",
    "kernel/svm/mapping.h",
    "kernel/svm/math.h",
    "kernel/svm/mix.h",
    "kernel/svm/ramp.h",
    "kernel/svm/sepcomb_color.h",
    "kernel/svm/sepcomb_vector.h",
    "kernel/svm/value.h",
]


def test_generated_header_is_current(build_dir: Path) -> None:
    """The header the build generated equals what the committed inputs generate now."""
    header = build_dir / GENERATED_HEADER
    assert header.is_file(), f"{header} is missing; build painterly_tests first"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/gen_svm_switch.py",
            "--manifest",
            "src/cycles/svm_nodes.toml",
            "--vendored",
            "third_party/cycles/VENDORED.toml",
            "--check",
            str(header),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_manifest_lists_stack_nodes() -> None:
    """The manifest lists every case and include this card adds. Later cards may append more."""
    with MANIFEST.open("rb") as handle:
        manifest = tomllib.load(handle)
    assert set(manifest) == {"includes", "cases"}
    assert set(STACK_CASES) <= set(manifest["cases"])
    assert set(INCLUDES) <= set(manifest["includes"])


def test_headers_check_includes_vendored_headers() -> None:
    """The build check includes kernel/globals.h first, then the 22 headers clang-format sorts."""
    text = HEADERS_CHECK.read_text(encoding="utf-8")
    includes = re.findall(r'^#include "([^"]+)"', text, re.MULTILINE)
    assert includes == ["kernel/globals.h", *sorted(VENDORED_HEADERS)]


def test_stack_node_sources_vendored() -> None:
    """The 22 headers are vendored whole, and each of the 39 cases has its svm_case fragment."""
    with VENDORED.open("rb") as handle:
        vendored = tomllib.load(handle)
    dests = {entry["dest"] for entry in vendored["file"]}
    missing = sorted(set(VENDORED_HEADERS) - dests)
    assert missing == []
    names = {entry["name"] for entry in vendored["fragment"]}
    absent = [case for case in STACK_CASES if f"kernel/svm/svm_h/svm_case/{case}" not in names]
    assert absent == []


def test_no_generated_header_in_repository() -> None:
    """The generated header lives only in the build tree, never at a repository path."""
    found = [
        str(path.relative_to(REPO_ROOT))
        for root in (REPO_ROOT / "src", REPO_ROOT / "third_party")
        for path in root.rglob("svm_eval_nodes.h")
    ]
    assert found == []
