"""Cycles' SVM compiler end to end: fragments, manifests, shims and generated units (card T6.5).

The committed inputs are checked here: every definition of scene/svm.cpp:157-1279 is a fragment,
the 45 files and 19 fragments of the card are vendored, both manifests carry the card's entries,
the util shims declare what the new code calls, and the build's generated units are current. No
test needs the network or the upstream checkout.
"""

import re
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDORED = REPO_ROOT / "third_party" / "cycles" / "VENDORED.toml"
SVN_NODES = REPO_ROOT / "src" / "cycles" / "svm_nodes.toml"
FRAGMENT_UNITS = REPO_ROOT / "src" / "cycles" / "fragment_units.toml"

# The 45 paths of "Vendored files", item 1: the include closure of kernel/svm/closure.h,
# util/progress.h and util/time.h that T3.2-T6.4 did not vendor.
T65_PATHS = [
    "kernel/bvh/util.h",
    "kernel/camera/projection.h",
    "kernel/closure/alloc.h",
    "kernel/closure/bsdf.h",
    "kernel/closure/bsdf_ashikhmin_shirley.h",
    "kernel/closure/bsdf_ashikhmin_velvet.h",
    "kernel/closure/bsdf_burley.h",
    "kernel/closure/bsdf_diffuse.h",
    "kernel/closure/bsdf_diffuse_ramp.h",
    "kernel/closure/bsdf_hair.h",
    "kernel/closure/bsdf_microfacet.h",
    "kernel/closure/bsdf_oren_nayar.h",
    "kernel/closure/bsdf_phong_ramp.h",
    "kernel/closure/bsdf_principled_hair_chiang.h",
    "kernel/closure/bsdf_principled_hair_huang.h",
    "kernel/closure/bsdf_ray_portal.h",
    "kernel/closure/bsdf_sheen.h",
    "kernel/closure/bsdf_toon.h",
    "kernel/closure/bsdf_transparent.h",
    "kernel/closure/bsdf_util.h",
    "kernel/closure/bssrdf.h",
    "kernel/closure/emissive.h",
    "kernel/closure/volume.h",
    "kernel/closure/volume_draine.h",
    "kernel/closure/volume_fournier_forand.h",
    "kernel/closure/volume_henyey_greenstein.h",
    "kernel/closure/volume_rayleigh.h",
    "kernel/closure/volume_util.h",
    "kernel/geom/attribute.h",
    "kernel/geom/curve.h",
    "kernel/geom/motion_curve.h",
    "kernel/geom/motion_point.h",
    "kernel/geom/object.h",
    "kernel/geom/point.h",
    "kernel/geom/primitive.h",
    "kernel/geom/triangle.h",
    "kernel/geom/volume.h",
    "kernel/integrator/state.h",
    "kernel/sample/lcg.h",
    "kernel/sample/mapping.h",
    "kernel/svm/closure.h",
    "kernel/util/image_3d.h",
    "kernel/util/lookup_table.h",
    "util/progress.h",
    "util/time.h",
]

# The cases that EmissionNode::compile emits (scene/shader_nodes.cpp:3077-3098).
T65_CASES = ["NODE_CLOSURE_EMISSION", "NODE_CLOSURE_SET_WEIGHT", "NODE_EMISSION_WEIGHT"]

EXPECTED_SVM_CPP_LINES = [
    (157, 170),
    (172, 196),
    (198, 204),
    (206, 238),
    (240, 243),
    (245, 252),
    (254, 288),
    (290, 298),
    (300, 308),
    (310, 322),
    (324, 341),
    (343, 346),
    (348, 358),
    (360, 364),
    (366, 369),
    (371, 384),
    (386, 400),
    (402, 422),
    (424, 432),
    (434, 438),
    (440, 453),
    (455, 465),
    (467, 473),
    (475, 478),
    (480, 490),
    (492, 502),
    (504, 534),
    (536, 539),
    (541, 544),
    (546, 550),
    (552, 565),
    (567, 592),
    (594, 604),
    (606, 756),
    (758, 807),
    (809, 824),
    (826, 843),
    (845, 997),
    (999, 1034),
    (1036, 1172),
    (1174, 1236),
    (1240, 1249),
    (1251, 1267),
    (1271, 1279),
]


def _toml(path: Path) -> dict:
    """The TOML table of path, read as bytes."""
    with path.open("rb") as handle:
        return tomllib.load(handle)


def test_svm_cpp_compiler_fully_fragmented() -> None:
    """Every definition of scene/svm.cpp:157-1279 is a fragment; the file is not vendored whole."""
    data = _toml(VENDORED)
    ranges = sorted(
        tuple(fragment["upstream_lines"])
        for fragment in data.get("fragment", [])
        if fragment["upstream_path"] == "scene/svm.cpp"
    )
    assert ranges == EXPECTED_SVM_CPP_LINES
    assert not [
        entry for entry in data.get("file", []) if entry["upstream_path"] == "scene/svm.cpp"
    ]


def test_t65_vendored_files() -> None:
    """The 45 files are vendored; the never-vendored paths are not; time_dt() is a fragment."""
    data = _toml(VENDORED)
    dests = {entry["dest"] for entry in data.get("file", [])}
    missing = [path for path in T65_PATHS if path not in dests]
    assert missing == []
    for path in (
        "util/time.cpp",
        "util/guiding.h",
        "kernel/util/nanovdb.h",
        "kernel/device/cpu/globals.h",
        "kernel/svm/svm.h",
    ):
        assert path not in dests, path
    names = {fragment["name"] for fragment in data.get("fragment", [])}
    assert "util/time_cpp/function/time_dt" in names
    assert not (REPO_ROOT / "src/cycles/shim/util/time.cpp").exists()


def test_t65_manifests() -> None:
    """svm_nodes.toml gains closure.h and the three cases; the time unit is added."""
    nodes = _toml(SVN_NODES)
    assert "kernel/svm/closure.h" in nodes["includes"]
    assert set(T65_CASES) <= set(nodes["cases"])
    names = {fragment["name"] for fragment in _toml(VENDORED).get("fragment", [])}
    for case in T65_CASES:
        assert f"kernel/svm/svm_h/svm_case/{case}" in names, case

    units = _toml(FRAGMENT_UNITS)["unit"]
    assert {"util/progress.h", "util/queue.h"} <= set(units["svm"]["includes"])
    assert units["time"] == {
        "upstream_path": "util/time.cpp",
        "includes": ["util/time.h", "<chrono>"],
        "node_registry": False,
    }


def test_t65_util_shims() -> None:
    """The util shims declare string_printf and define LOG_DEBUG."""
    assert (
        "string string_printf(const char *format, ...) PRINTF_ATTRIBUTE;"
        in (REPO_ROOT / "src/cycles/shim/util/string.h").read_text()
    )
    assert (
        "string string_printf(const char *format, ...)"
        in (REPO_ROOT / "src/cycles/shim/util/string.cpp").read_text()
    )
    assert "#define LOG_DEBUG" in (REPO_ROOT / "src/cycles/shim/util/log.h").read_text()


def test_closure_headers_check() -> None:
    """The closure headers check includes globals.h and closure.h, and is an OBJECT library."""
    text = (REPO_ROOT / "src/cycles/svm_closure_headers_check.cpp").read_text()
    assert re.findall(r'^#include "([^"]+)"', text, flags=re.MULTILINE) == [
        "kernel/globals.h",
        "kernel/svm/closure.h",
    ]
    assert (
        "add_library(cycles_svm_closure_headers_check OBJECT svm_closure_headers_check.cpp)"
        in (REPO_ROOT / "src/cycles/CMakeLists.txt").read_text()
    )


def test_generated_units_are_current(build_dir: Path) -> None:
    """The build's svm and time units are what the generator produces from the committed inputs."""
    for unit in ("svm", "time"):
        generated = build_dir / "src/cycles/fragment_units" / f"{unit}.cpp"
        assert generated.exists(), generated
        result = subprocess.run(
            [
                sys.executable,
                "tools/gen_fragment_units.py",
                "--manifest",
                "src/cycles/fragment_units.toml",
                "--vendored",
                "third_party/cycles/VENDORED.toml",
                "--unit",
                unit,
                "--check",
                str(generated),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (unit, result.stderr)
