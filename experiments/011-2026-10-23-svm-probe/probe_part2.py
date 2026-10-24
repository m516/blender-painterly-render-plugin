#!/usr/bin/env python3
"""Experiment 011 part 2 (X-svm, gate G2-svm): graph -> byte code -> evaluation, verbatim?

Run from the repository root:
    python -I experiments/011-2026-10-23-svm-probe/probe_part2.py

It reads PAINTERLY_BUILD_DIR (default build/dev, the protocol's default) and runs the instruments
of card T6.5's H4-H6 and M4-M7. It writes results_part2.json next to itself, prints a summary, and
exits 0 iff gate G2-svm passes (part 1's gate and H4, H5 and H6 all supported). Standard library
only, plus tools/vendor_sync.py loaded by path; it reads the downloaded upstream checkout, so run
it with `python -I` (CLAUDE.md rule 5).

Its output is deterministic except M6's compile times and the run date.
"""

from __future__ import annotations

import datetime
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[2]
BUILD_DIR = Path(os.environ.get("PAINTERLY_BUILD_DIR", "build/dev"))
BUILD = (REPO / BUILD_DIR).resolve()
UPSTREAM = REPO / ".cache" / "vendor" / "blender-v5.2.2" / "intern" / "cycles"
MANIFEST = REPO / "third_party" / "cycles" / "VENDORED.toml"
SVN_NODES = REPO / "src" / "cycles" / "svm_nodes.toml"
PROBE = Path(__file__).resolve()
EXP = PROBE.parent
TESTS = BUILD / "src" / "test" / "painterly_tests"
# The newest commit whose subject is card T6.4's, in the queue's "<task id>: <item heading>" form.
T64_SUBJECT_RE = re.compile(r"^([^ ]+: M6a-(FIX-)?)?T6\.4[a-z]?[ :]")
# The includes of "Method" step 3: a quoted include, optionally indented.
INCLUDE_RE = re.compile(r'^\s*#\s*include\s+"([^"]+)"', re.MULTILINE)
ASSERTIONS_RE = re.compile(
    r"\[doctest\] assertions:\s*(\d+)\s*\|\s*(\d+) passed\s*\|\s*(\d+) failed"
)
# The three seeds of H4 (e), and the two exceptions that no definition set enables.
CLOSURE_SEEDS = ("kernel/svm/closure.h", "util/progress.h", "util/time.h")
CLOSURE_ALLOWED = ("util/guiding.h", "kernel/util/nanovdb.h")
UNRESOLVED_ALLOWED = ("../../guardedalloc/MEM_guardedalloc.h",)
# H4 (d): the shim files that card T6.5 modifies against card T6.4's commit.
SHIM_MODIFIED = [
    "src/cycles/shim/scene/scene.h",
    "src/cycles/shim/scene/shader.h",
    "src/cycles/shim/scene/shader.cpp",
    "src/cycles/shim/util/string.h",
    "src/cycles/shim/util/string.cpp",
    "src/cycles/shim/util/log.h",
]
# The five H5 test cases, in the card's order, and H6's.
H5_CASES = (
    "cycles svm compiler: the node types and parameters of these tests are registered",
    "cycles svm compiler: Value -> Math -> Emission compiles to the derived byte code",
    "cycles svm compiler: the unfolded program evaluates to its emission",
    "cycles svm compiler: device_update_pre folds the graph and the folded program agrees",
    "cycles svm compiler: two shaders share one jump table",
)
H5_KEYS = ("registered", "byte code", "unfolded evaluation", "folded evaluation", "two shaders")
H6_CASE = "cycles svm compiler: Math through compiler and SVM equals an independent reference"
# M4: each class of the test graph, with the kernel cases its compile(SVMCompiler &) emits.
M4_CLASSES = {
    "ValueNode": ["NODE_VALUE_F", "NODE_VALUE_F_DERIVATIVE"],
    "MathNode": ["NODE_MATH"],
    "EmissionNode": ["NODE_CLOSURE_EMISSION", "NODE_CLOSURE_SET_WEIGHT", "NODE_EMISSION_WEIGHT"],
    "OutputNode": [],
}
# The 45 files of card T6.5's "Vendored files", item 1.
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


def load_vendor_sync() -> ModuleType:
    """tools/vendor_sync.py, loaded by path for list_anchors."""
    path = REPO / "tools" / "vendor_sync.py"
    spec = importlib.util.spec_from_file_location("vendor_sync_probe_part2", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def env() -> dict[str, str]:
    """The environment for subprocesses: the venv's bin first on PATH."""
    result = dict(os.environ)
    result["PATH"] = f"{REPO / '.venv' / 'bin'}{os.pathsep}{result.get('PATH', '')}"
    return result


def manifest() -> dict:
    """third_party/cycles/VENDORED.toml."""
    with MANIFEST.open("rb") as handle:
        return tomllib.load(handle)


def newline_count(path: Path) -> int:
    """How many b"\\n" bytes path holds, which is what wc -l counts."""
    return path.read_bytes().count(b"\n")


def instrument_h4(vs: ModuleType) -> dict:
    """H4: verbatim fragments, unchanged shims, resolved closure, and a clean build."""
    data = manifest()
    fragments = [
        fragment
        for fragment in data.get("fragment", [])
        if fragment["upstream_path"] == "scene/svm.cpp"
    ]
    definitions = [
        anchor
        for anchor in vs.list_anchors((UPSTREAM / "scene" / "svm.cpp").read_text())
        if anchor.kind in ("member", "function")
        and 157 <= anchor.first_line <= anchor.last_line <= 1279
    ]
    definition_ranges = {(anchor.first_line, anchor.last_line) for anchor in definitions}
    fragment_ranges = {tuple(fragment["upstream_lines"]) for fragment in fragments}
    uncovered = sorted(
        f"{anchor.first_line}-{anchor.last_line} {anchor.kind} {anchor.anchor}"
        for anchor in definitions
        if (anchor.first_line, anchor.last_line) not in fragment_ranges
    )
    extra = sorted(
        f"{fragment['upstream_lines'][0]}-{fragment['upstream_lines'][1]} {fragment['name']}"
        for fragment in fragments
        if tuple(fragment["upstream_lines"]) not in definition_ranges
    )

    base = ""
    log = subprocess.run(
        ["git", "log", "--format=%H%x09%s"], cwd=REPO, capture_output=True, text=True, check=True
    )
    for line in log.stdout.splitlines():
        commit, _, subject = line.partition("\t")
        if T64_SUBJECT_RE.match(subject):
            base = commit
            break
    diff = subprocess.run(
        ["git", "diff", "--name-status", base, "--", "src/cycles/shim"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    shim_new, shim_modified, shim_deleted = [], [], []
    for line in diff.stdout.splitlines():
        status, _, path = line.partition("\t")
        {"A": shim_new, "M": shim_modified, "D": shim_deleted}.get(status, []).append(path)
    others = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "--", "src/cycles/shim"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    shim_new = sorted([*shim_new, *others.stdout.split()])

    closure = instrument_closure(data)
    build_exit = subprocess.run(
        [
            "cmake",
            "--build",
            str(BUILD),
            "--target",
            "painterly_tests",
            "cycles_svm_closure_headers_check",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
        env=env(),
    ).returncode

    supported = (
        len(patches()) == 0
        and closure["vendor_check_upstream_exit"] == 0
        and not uncovered
        and not extra
        and not shim_new
        and not shim_deleted
        and sorted(shim_modified) == sorted(SHIM_MODIFIED)
        and set(closure["closure_uncovered"]) <= set(CLOSURE_ALLOWED)
        and set(closure["closure_unresolved"]) <= set(UNRESOLVED_ALLOWED)
        and build_exit == 0
    )
    return {
        "patches": len(patches()),
        "vendor_check_upstream_exit": closure["vendor_check_upstream_exit"],
        "svm_cpp_definitions": len(definitions),
        "svm_cpp_fragments": len(fragments),
        "svm_cpp_uncovered": uncovered,
        "svm_cpp_extra": extra,
        "shim_new": shim_new,
        "shim_modified": shim_modified,
        "shim_deleted": shim_deleted,
        "closure_paths": closure["closure_paths"],
        "closure_upstream_lines": closure["closure_upstream_lines"],
        "closure_shims_reached": closure["closure_shims_reached"],
        "closure_uncovered": closure["closure_uncovered"],
        "closure_unresolved": closure["closure_unresolved"],
        "build_exit": build_exit,
        "supported": supported,
    }


def patches() -> list[str]:
    """The files in third_party/cycles/patches/ other than .gitkeep."""
    directory = REPO / "third_party" / "cycles" / "patches"
    if not directory.is_dir():
        return []
    return sorted(path.name for path in directory.iterdir() if path.name != ".gitkeep")


def resolve_include(include: str, includer: Path, data: dict) -> tuple[Path | None, bool]:
    """The file an include resolves to, and whether it resolved at all.

    The order is the card's: src/cycles/shim/, then the checkout root, then the includer's
    directory. A candidate is normalized first, and one that starts with ".." never resolves.
    """
    candidates = [
        REPO / "src" / "cycles" / "shim" / include,
        UPSTREAM / include,
        includer.parent / include,
    ]
    for candidate in candidates:
        normalized = os.path.normpath(candidate)
        if normalized.startswith(".."):
            continue
        if Path(normalized).is_file():
            return Path(normalized), True
    return None, False


def instrument_closure(data: dict) -> dict:
    """H4 (e): the include closure of the three seeds, and the check of the vendored files."""
    dests = {entry["dest"] for entry in data.get("file", [])}
    shim_root = REPO / "src" / "cycles" / "shim"
    seen: set[Path] = set()
    unresolved: set[str] = set()
    queue = [UPSTREAM / seed for seed in CLOSURE_SEEDS]
    while queue:
        path = queue.pop()
        if path in seen:
            continue
        seen.add(path)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for include in INCLUDE_RE.findall(text):
            resolved, ok = resolve_include(include, path, data)
            if not ok:
                unresolved.add(include)
            elif resolved is not None and resolved not in seen:
                queue.append(resolved)

    shims = sorted(path for path in seen if str(path).startswith(str(shim_root) + os.sep))
    upstream = sorted(path for path in seen if path not in set(shims))
    uncovered = sorted(
        str(path.relative_to(UPSTREAM))
        for path in upstream
        if str(path.relative_to(UPSTREAM)) not in dests
    )
    check = subprocess.run(
        [sys.executable, "-I", "tools/vendor_sync.py", "check", "--upstream"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "vendor_check_upstream_exit": check.returncode,
        "closure_paths": len(seen),
        "closure_upstream_lines": sum(newline_count(path) for path in upstream),
        "closure_shims_reached": sorted(str(path.relative_to(REPO)) for path in shims),
        "closure_uncovered": uncovered,
        "closure_unresolved": sorted(unresolved),
    }


def assertions(case: str) -> dict[str, int]:
    """The passed and failed assertion counts of one doctest test case."""
    result = subprocess.run(
        [str(TESTS), f"--test-case={case}"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
        env=env(),
    )
    match = ASSERTIONS_RE.search(result.stdout)
    if match is None:
        return {"passed": 0, "failed": 0}
    return {"passed": int(match.group(2)), "failed": int(match.group(3))}


def instrument_h5() -> dict:
    """H5: the five end-to-end test cases, each with its passed and failed assertions."""
    result: dict[str, object] = {
        key: assertions(case) for key, case in zip(H5_KEYS, H5_CASES, strict=True)
    }
    result["supported"] = all(
        result[key] == {"passed": p, "failed": 0}
        for key, p in zip(H5_KEYS, (6, 4, 9, 21, 12), strict=True)
    )
    return result


def instrument_h6() -> dict:
    """H6: the Math test case, which compares 4162 pairs with an independent float64 reference."""
    counts = assertions(H6_CASE)
    return {
        "independent reference": counts,
        "supported": counts == {"passed": 33, "failed": 0},
    }


def instrument_m4(data: dict) -> dict:
    """M4: port size per node class of the test graph."""
    entries = data.get("fragment", [])
    result = {}
    for cls, cases in M4_CLASSES.items():
        host = [
            entry
            for entry in entries
            if entry["upstream_path"] == "scene/shader_nodes.cpp"
            and (
                (entry["kind"] == "node_define" and entry["anchor"] == cls)
                or (entry["kind"] == "member" and entry["anchor"].startswith(cls + "::"))
            )
        ]
        names = {entry["name"] for entry in entries}
        kernel = [case for case in cases if f"kernel/svm/svm_h/svm_case/{case}" in names]
        result[cls] = {
            "host_fragments": len(host),
            "kernel_cases": len(kernel),
            "manifest_lines": sum(len(entry) + 2 for entry in host) + len(kernel),
            "upstream_lines": sum(
                entry["upstream_lines"][1] - entry["upstream_lines"][0] + 1 for entry in host
            ),
        }
    return result


def instrument_m5() -> dict:
    """M5: the card's start and end timestamps, and the minutes between them."""
    log = EXP / "port_log_part2.txt"
    start = end = ""
    if log.is_file():
        for line in log.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition(" ")
            if key == "start":
                start = value
            elif key == "end":
                end = value

    def parse(value: str) -> datetime.datetime | None:
        if not value:
            return None
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))

    first, last = parse(start), parse(end)
    minutes = 0.0
    if first is not None and last is not None:
        minutes = round((last - first).total_seconds() / 60.0, 1)
    return {"start": start, "end": end, "card_minutes": minutes}


def instrument_m6() -> dict:
    """M6: the compile closure and the compile time of the doctest object."""
    target = "src/test/CMakeFiles/painterly_tests.dir/test_cycles_svm_compiler.cpp.o"
    result: dict[str, object] = {
        "deps_total": 0,
        "deps_third_party_cycles": 0,
        "deps_third_party_cycles_lines": 0,
        "deps_shim": 0,
        "deps_src_painterly": 0,
        "deps_generated": 0,
        "compile_seconds": [],
        "compile_seconds_median": 0.0,
    }
    deps = subprocess.run(
        ["ninja", "-C", str(BUILD), "-t", "deps", target],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
    lines = deps.stdout.splitlines()
    header = next((n for n, line in enumerate(lines) if line.startswith("#deps ")), None)
    paths: list[Path] = []
    if header is not None:
        for line in lines[header + 1 :]:
            if not line.startswith(" ") or not line.strip():
                break
            path = Path(line.strip())
            if not path.is_absolute():
                path = BUILD / path
            paths.append(Path(os.path.normpath(path)))
    third_party = [
        p for p in paths if str(p).startswith(str(REPO / "third_party" / "cycles") + os.sep)
    ]
    result["deps_total"] = len(paths)
    result["deps_third_party_cycles"] = len(third_party)
    result["deps_third_party_cycles_lines"] = sum(
        newline_count(p) for p in third_party if p.is_file()
    )
    result["deps_shim"] = sum(
        1 for p in paths if str(p).startswith(str(REPO / "src" / "cycles" / "shim") + os.sep)
    )
    result["deps_src_painterly"] = sum(
        1 for p in paths if str(p).startswith(str(REPO / "src" / "painterly") + os.sep)
    )
    result["deps_generated"] = sum(
        1 for p in paths if str(p).startswith(str(BUILD / "src" / "cycles" / "generated") + os.sep)
    )

    source = REPO / "src" / "test" / "test_cycles_svm_compiler.cpp"
    times = []
    for _ in range(3):
        os.utime(source, None)
        began = time.perf_counter()
        subprocess.run(
            ["ninja", "-C", str(BUILD), target], cwd=REPO, capture_output=True, check=False
        )
        times.append(round(time.perf_counter() - began, 2))
    result["compile_seconds"] = times
    result["compile_seconds_median"] = sorted(times)[1] if len(times) == 3 else 0.0
    return result


def instrument_m7(data: dict) -> dict:
    """M7: the sizes of the fragments, the 45 files and the three generated files."""
    fragments = data.get("fragment", [])
    svm_cpp = [f for f in fragments if f["upstream_path"] == "scene/svm.cpp"]
    svm_case = [f for f in fragments if f["kind"] == "svm_case"]

    def lines(entries: list[dict]) -> int:
        return sum(entry["upstream_lines"][1] - entry["upstream_lines"][0] + 1 for entry in entries)

    dests = {entry["dest"] for entry in data.get("file", [])}
    added = [path for path in T65_PATHS if path in dests]
    header = BUILD / "src" / "cycles" / "generated" / "svm_eval_nodes.h"
    svm_unit = BUILD / "src" / "cycles" / "fragment_units" / "svm.cpp"
    time_unit = BUILD / "src" / "cycles" / "fragment_units" / "time.cpp"
    return {
        "svm_cpp_fragments": len(svm_cpp),
        "svm_cpp_fragment_lines": lines(svm_cpp),
        "svm_case_fragments": len(svm_case),
        "svm_case_fragment_lines": lines(svm_case),
        "fragments_total": len(fragments),
        "vendored_files_added": len(added),
        "vendored_lines_added": sum(
            newline_count(REPO / "third_party" / "cycles" / path) for path in added
        ),
        "generated_header_lines": newline_count(header) if header.is_file() else 0,
        "generated_header_sha256": sha256(header),
        "svm_unit_lines": newline_count(svm_unit) if svm_unit.is_file() else 0,
        "svm_unit_sha256": sha256(svm_unit),
        "time_unit_lines": newline_count(time_unit) if time_unit.is_file() else 0,
        "time_unit_sha256": sha256(time_unit),
    }


def sha256(path: Path) -> str:
    """The SHA-256 hex digest of path, or the empty string when it does not exist."""
    if not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compiler_line() -> str:
    """The first line of <CMAKE_CXX_COMPILER> --version, read from the build's CMakeCache.txt."""
    cache = BUILD / "CMakeCache.txt"
    compiler = ""
    if cache.is_file():
        for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("CMAKE_CXX_COMPILER:"):
                compiler = line.partition("=")[2]
                break
    if not compiler:
        return ""
    result = subprocess.run([compiler, "--version"], capture_output=True, text=True, check=False)
    return result.stdout.splitlines()[0] if result.stdout else ""


def part1_gate() -> bool:
    """Part 1's gate, from results.json next to this probe."""
    path = EXP / "results.json"
    if not path.is_file():
        return False
    with path.open("rb") as handle:
        return json.load(handle).get("gate") is True


def main() -> int:
    """Run every instrument, write results_part2.json, print a summary; 0 iff gate G2-svm passes."""
    vs = load_vendor_sync()
    data = manifest()
    h4 = instrument_h4(vs)
    h5 = instrument_h5()
    h6 = instrument_h6()
    results = {
        "registration": "2026-10-09, card T6.5 (Opus)",
        "run_date": datetime.date.today().isoformat(),
        "build_dir": str(BUILD_DIR),
        "compiler": compiler_line(),
        "H4": h4,
        "H5": h5,
        "H6": h6,
        "M4": instrument_m4(data),
        "M5": instrument_m5(),
        "M6": instrument_m6(),
        "M7": instrument_m7(data),
        "part1_gate": part1_gate(),
    }
    results["gate_part2"] = h4["supported"] and h5["supported"] and h6["supported"]
    results["gate_G2_svm"] = results["part1_gate"] and results["gate_part2"]

    out = EXP / "results_part2.json"
    out.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    print(
        f"H4 supported={h4['supported']} patches={h4['patches']} "
        f"uncovered={len(h4['svm_cpp_uncovered'])} extra={len(h4['svm_cpp_extra'])} "
        f"build_exit={h4['build_exit']}"
    )
    print(f"H5 supported={h5['supported']}")
    for key in H5_KEYS:
        print(f"  {key}: {h5[key]}")
    print(f"H6 supported={h6['supported']} {h6['independent reference']}")
    print(
        f"part1_gate={results['part1_gate']} gate_part2={results['gate_part2']} "
        f"gate_G2_svm={results['gate_G2_svm']}"
    )
    print(f"wrote {out}")
    return 0 if results["gate_G2_svm"] else 1


if __name__ == "__main__":
    sys.exit(main())
