#!/usr/bin/env python3
"""Experiment 011 (X-svm, the SVM half): do Cycles' stack-only SVM nodes run verbatim?

Run from the repository root:  python -I experiments/011-2026-10-23-svm-probe/probe.py

It reads PAINTERLY_BUILD_DIR (default build/dev, the protocol's default) and runs the instruments
of card T6.3's H1-H3 and M1-M3. It writes results.json next to itself, prints a summary, and exits
0 iff the gate passes (H1, H2 and H3 all supported). Standard library only; it reads the downloaded
upstream checkout, so run it with `python -I` (CLAUDE.md rule 5).

The only non-deterministic output is M3's compile times.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BUILD_DIR = Path(os.environ.get("PAINTERLY_BUILD_DIR", "build/dev"))
BUILD = (REPO / BUILD_DIR).resolve()
UPSTREAM = REPO / ".cache" / "vendor" / "blender-v5.2.2" / "intern" / "cycles"
SHIM = REPO / "src" / "cycles" / "shim"
VENDORED = REPO / "third_party" / "cycles" / "VENDORED.toml"
MANIFEST = REPO / "src" / "cycles" / "svm_nodes.toml"
GENERATED = BUILD / "src" / "cycles" / "generated" / "svm_eval_nodes.h"
PATCHES = REPO / "third_party" / "cycles" / "patches"
TEST_BINARY = BUILD / "src" / "test" / "painterly_tests"
TEST_OBJECT = "src/test/CMakeFiles/painterly_tests.dir/test_cycles_svm_stack_nodes.cpp.o"

# The 22 headers card T6.3 vendors, relative to intern/cycles.
HEADERS = [
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

# The doctest test cases of H2 and H3, with the passed assertions the card expects.
H2_CASES = {"control flow": 11, "every stack node case dispatches": 105}
H3_CASES = ("math", "mix", "map range", "color ramp", "convert")
# doctest pads each count to the width of the largest one (doctest.h:6264-6285), so the line has
# no fixed text. The card's Method step 4 gives this pattern.
ASSERTIONS_RE = re.compile(
    r"^\[doctest\] assertions:\s+(\d+) \|\s+(\d+) passed \|\s+(\d+) failed", re.MULTILINE
)
INCLUDE_RE = re.compile(r'^\s*#\s*include\s+"([^"]+)"', re.MULTILINE)
COMPILE_RUNS = 3
SECONDS_DECIMALS = 2


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a command from the repository root with .venv/bin first on PATH."""
    environment = dict(os.environ)
    environment["PATH"] = f"{REPO / '.venv' / 'bin'}{os.pathsep}{environment.get('PATH', '')}"
    return subprocess.run(
        args, cwd=REPO, capture_output=True, text=True, check=False, env=environment
    )


def _count_lines(path: Path) -> int:
    """The number of newline bytes in path, as wc -l counts them."""
    return path.read_bytes().count(b"\n")


def _load_toml(path: Path) -> dict:
    """The parsed TOML of path."""
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _compiler_line() -> str:
    """The first line of the configured C++ compiler's --version."""
    cache = BUILD / "CMakeCache.txt"
    compiler = ""
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("CMAKE_CXX_COMPILER:"):
            compiler = line.split("=", 1)[1].strip()
            break
    if not compiler:
        return "unknown (CMAKE_CXX_COMPILER not in CMakeCache.txt)"
    completed = _run([compiler, "--version"])
    return completed.stdout.splitlines()[0] if completed.stdout else "unknown"


def _doctest_assertions(name: str) -> tuple[int, int]:
    """(passed, failed) of one doctest test case; (0, 0) when its line is missing."""
    completed = _run([str(TEST_BINARY), f"--test-case=cycles svm stack nodes: {name}"])
    match = ASSERTIONS_RE.search(completed.stdout)
    if match is None:
        return 0, 0
    return int(match.group(2)), int(match.group(3))


def _resolve_include(includer: str, include: str) -> str | None:
    """Resolve one quoted include to a shim or upstream path, or None if it is unresolved.

    The card's order: the shim path, then the checkout root, then the includer's directory.
    """
    candidates = [include, (Path(includer).parent / include).as_posix()]
    for candidate in candidates:
        normal = os.path.normpath(candidate).replace(os.sep, "/")
        if normal == ".." or normal.startswith("../"):
            continue
        if (SHIM / normal).is_file() or (UPSTREAM / normal).is_file():
            return normal
    return None


def _closure() -> tuple[set[str], set[str], set[str]]:
    """Walk the include closure of the 22 headers.

    Returns (all paths, shim paths reached, unresolved includes). A path that is a file under
    src/cycles/shim/ is read from there; any other from the upstream checkout.
    """
    seen: set[str] = set()
    shims: set[str] = set()
    unresolved: set[str] = set()
    pending = list(HEADERS)
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        if (SHIM / current).is_file():
            path = SHIM / current
            shims.add(current)
        else:
            path = UPSTREAM / current
        if not path.is_file():
            unresolved.add(f"{current} (missing)")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for include in INCLUDE_RE.findall(text):
            found = _resolve_include(current, include)
            if found is None:
                unresolved.add(f'#include "{include}" in {current}')
            elif found not in seen:
                pending.append(found)
    return seen, shims, unresolved


def _h1() -> dict:
    """H1: the 22 headers compile verbatim, with no patch and no new shim."""
    patches = sorted(
        path.name for path in PATCHES.glob("*") if path.is_file() and path.name != ".gitkeep"
    )
    vendor_check = _run([sys.executable, "-I", "tools/vendor_sync.py", "check", "--upstream"])
    shim_status = _run(
        ["git", "status", "--porcelain", "--untracked-files=all", "--", "src/cycles/shim"]
    )
    shim_lines = [line for line in shim_status.stdout.splitlines() if line.strip()]
    paths, shims, unresolved = _closure()
    dests = {entry["dest"] for entry in _load_toml(VENDORED)["file"]}
    uncovered = sorted(path for path in paths if path not in dests and not (SHIM / path).is_file())
    upstream_lines = sum(
        _count_lines(UPSTREAM / path) for path in paths if not (SHIM / path).is_file()
    )
    build = _run(["cmake", "--build", str(BUILD)])
    supported = (
        not patches
        and vendor_check.returncode == 0
        and not shim_lines
        and not uncovered
        and not unresolved
        and build.returncode == 0
    )
    return {
        "patches": len(patches),
        "vendor_check_upstream_exit": vendor_check.returncode,
        "shim_status_lines": shim_lines,
        "closure_paths": len(paths),
        "closure_upstream_lines": upstream_lines,
        "closure_shims_reached": sorted(shims),
        "closure_uncovered": uncovered,
        "closure_unresolved": sorted(unresolved),
        "build_exit": build.returncode,
        "supported": supported,
    }


def _h2() -> dict:
    """H2: the frame runs as upstream and every case consumes exactly its words."""
    result: dict[str, object] = {}
    supported = True
    for name, expected in H2_CASES.items():
        passed, failed = _doctest_assertions(name)
        result[name] = {"passed": passed, "failed": failed}
        supported = supported and failed == 0 and passed == expected
    result["supported"] = supported
    return result


def _h3() -> dict:
    """H3: the nodes compute exactly the values card T6.3 derives (IEEE ==)."""
    result: dict[str, object] = {}
    supported = True
    for name in H3_CASES:
        passed, failed = _doctest_assertions(name)
        result[name] = {"passed": passed, "failed": failed}
        supported = supported and failed == 0 and passed > 0
    result["supported"] = supported
    return result


def _m1() -> dict:
    """M1: the port cost, as counts."""
    manifest = _load_toml(MANIFEST)
    vendored = _load_toml(VENDORED)
    fragments = [
        entry
        for entry in vendored["fragment"]
        if entry.get("kind") == "svm_case" and entry.get("upstream_path") == "kernel/svm/svm.h"
    ]
    dests = {entry["dest"] for entry in vendored["file"]}
    data = GENERATED.read_bytes()
    return {
        "manifest_cases": len(manifest["cases"]),
        "manifest_includes": len(manifest["includes"]),
        "svm_case_fragments": len(fragments),
        "svm_case_fragment_lines": sum(
            entry["upstream_lines"][1] - entry["upstream_lines"][0] + 1 for entry in fragments
        ),
        "vendored_headers": sum(1 for header in HEADERS if header in dests),
        "generated_header_lines": _count_lines(GENERATED),
        "generated_header_sha256": hashlib.sha256(data).hexdigest(),
    }


def _m2() -> dict:
    """M2: the headers the compiler read for the doctest object, and their lines."""
    completed = _run(["ninja", "-C", str(BUILD), "-t", "deps", TEST_OBJECT])
    paths = [
        line.strip()
        for line in completed.stdout.splitlines()[1:]
        if line.startswith(" ") and line.strip()
    ]
    third_party_prefix = str(REPO) + "/third_party/cycles/"
    shim_prefix = str(REPO) + "/src/cycles/shim/"
    generated_prefix = str(BUILD) + "/src/cycles/generated/"
    third_party = [path for path in paths if path.startswith(third_party_prefix)]
    return {
        "deps_total": len(paths),
        "deps_third_party_cycles": len(third_party),
        "deps_third_party_cycles_lines": sum(
            _count_lines(Path(path)) for path in third_party if Path(path).is_file()
        ),
        "deps_shim": sum(1 for path in paths if path.startswith(shim_prefix)),
        "deps_generated": sum(1 for path in paths if path.startswith(generated_prefix)),
    }


def _m3() -> dict:
    """M3: the wall-clock seconds to rebuild the doctest object, three times, and their median."""
    source = REPO / "src" / "test" / "test_cycles_svm_stack_nodes.cpp"
    object_path = BUILD / TEST_OBJECT
    seconds: list[float] = []
    for _ in range(COMPILE_RUNS):
        source.touch()
        if object_path.exists():
            object_path.unlink()
        start = time.monotonic()
        _run(["ninja", "-C", str(BUILD), TEST_OBJECT])
        seconds.append(round(time.monotonic() - start, SECONDS_DECIMALS))
    median = sorted(seconds)[len(seconds) // 2]
    return {"compile_seconds": seconds, "compile_seconds_median": median}


def main() -> int:
    """Run every instrument, write results.json and print a summary."""
    results: dict[str, object] = {
        "registration": "2026-10-09, card T6.3 (Opus)",
        "run_date": datetime.date.today().isoformat(),
        "build_dir": str(BUILD_DIR),
        "compiler": _compiler_line(),
        "H1": _h1(),
        "H2": _h2(),
        "H3": _h3(),
        "M1": _m1(),
        "M2": _m2(),
        "M3": _m3(),
    }
    h1, h2, h3 = results["H1"], results["H2"], results["H3"]
    results["gate"] = bool(h1["supported"] and h2["supported"] and h3["supported"])
    output = Path(__file__).resolve().parent / "results.json"
    output.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for key, block in (("H1", h1), ("H2", h2), ("H3", h3)):
        print(f"{key}: supported={block['supported']}")
    print(f"M1: {json.dumps(results['M1'], sort_keys=True)}")
    print(f"gate: {results['gate']}")
    return 0 if results["gate"] else 1


if __name__ == "__main__":
    sys.exit(main())
