#!/usr/bin/env python3
"""H3 instrument: which symbols _painterly binds to, and which of those bindings are violations.

Usage: bindings.py <ld_debug_dir> --module <path/to/_painterly*.so>

Input: the glibc ld.so debug files in <ld_debug_dir>. A process started with
LD_BIND_NOW=1 LD_DEBUG=bindings LD_DEBUG_OUTPUT=<ld_debug_dir>/ld writes one file per
process, named ld.<pid>. --module is the module whose trace this is. Its undefined dynamic
symbols (nm -D --undefined-only) are the bindings that the trace must show.

Rules (H3, amended before running; see the README's "Amendments before running (Opus)"):
- Bindings whose destination is _painterly itself are skipped (self-bindings).
- A binding made by _painterly is a violation iff either
  - its symbol version starts with GLIBC_ and its destination's basename is not libc.so.6,
    libm.so.6 or ld-linux-*.so.N (glibc's own objects); or
  - it has no GLIBC_ version and its symbol does not match ^_?Py. The Python C API must bind
    to the executable that embeds Python, which is blender.
  Paths are matched by the full regex and by basename, never by substring, because the
  repository path itself contains "blender".
- Coverage: the expected bindings are the module's undefined dynamic symbols, minus the weak
  undefined symbols that the trace does not bind (those stay unresolved, so no trace line can
  show them). The matched bindings are the expected ones that the trace binds from _painterly.
  Coverage is complete iff matched == expected and expected > 0. H3 needs complete coverage
  AND zero violations.

Outputs, written into <ld_debug_dir>:
- bindings_summary.txt: the violation count, one integer on one line.
- bindings.json: totals, coverage, per-destination counts, bound-but-not-imported symbols,
  and the violating (destination, symbol, version) triples.

Exit status is 1 when the directory has no ld.* file, when there is no binding from
_painterly, or when the module has no undefined dynamic symbols. An instrument that sees
nothing cannot show H3, so those cases must not pass silently.
"""

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

# The regex fixed by the T2.3 card, split across literals for line length. The pattern is unchanged.
BINDING = re.compile(
    r"binding file (?P<src>\S*/_painterly[^/\s]*) \[\d+\] to (?P<dst>\S+) \[\d+\]: "
    r"normal symbol `(?P<sym>[^']+)'(?: \[(?P<ver>[^\]]+)\])?"
)
GLIBC_VERSION_PREFIX = "GLIBC_"
# glibc's own objects, by basename: the only legal destinations for GLIBC_ bindings (amendment 4).
GLIBC_PROVIDER = re.compile(r"^(libc\.so\.6|libm\.so\.6|ld-linux[A-Za-z0-9_.-]*\.so\.\d+)$")
# The Python C API binds to the executable that embeds Python, so it is not a violation.
PYTHON_API = re.compile(r"^_?Py")
LD_FILE_PREFIX = "ld."
# nm -D --undefined-only marks weak undefined symbols with w (or v for weak objects).
WEAK_UNDEFINED_TYPES = ("w", "v")

# A symbol as the trace names it: (name, version); version is None when unversioned.
Key = tuple[str, str | None]


def is_violation(symbol: str, version: str | None, destination: str) -> bool:
    """H3's rule: see the module docstring."""
    if version is not None and version.startswith(GLIBC_VERSION_PREFIX):
        return not GLIBC_PROVIDER.match(Path(destination).name)
    return not PYTHON_API.match(symbol)


def undefined_symbols(module: Path) -> dict[Key, bool]:
    """Map each undefined dynamic symbol of module to whether it is weak.

    nm prints name@VERSION for a versioned symbol.
    """
    listing = subprocess.run(
        ["nm", "-D", "--undefined-only", str(module)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    symbols: dict[Key, bool] = {}
    for line in listing.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        kind, raw = fields
        name, _, version = raw.partition("@")
        symbols[(name, version.lstrip("@") or None)] = kind in WEAK_UNDEFINED_TYPES
    return symbols


def scan(ld_dir: Path, module: Path) -> dict:
    ld_files = sorted(
        p for p in ld_dir.iterdir() if p.is_file() and p.name.startswith(LD_FILE_PREFIX)
    )
    if not ld_files:
        raise SystemExit(f"bindings.py: no ld.* files in {ld_dir}; LD_DEBUG_OUTPUT was not written")
    imports = undefined_symbols(module)
    if not imports:
        raise SystemExit(f"bindings.py: nm finds no undefined dynamic symbols in {module}")

    bindings = 0
    self_bindings = 0
    per_destination = Counter()
    per_destination_violations = Counter()
    violations: set[tuple[str, str, str]] = set()
    observed: set[Key] = set()
    for path in ld_files:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = BINDING.search(line)
            if match is None:
                continue
            if match["dst"] == match["src"]:
                self_bindings += 1
                continue
            bindings += 1
            destination = match["dst"]
            symbol = match["sym"]
            version = match["ver"]
            per_destination[destination] += 1
            observed.add((symbol, version))
            if is_violation(symbol, version, destination):
                per_destination_violations[destination] += 1
                violations.add((destination, symbol, version or ""))

    if bindings == 0:
        raise SystemExit(f"bindings.py: no binding from _painterly in {ld_dir}; the trace is empty")

    unbound_weak = {key for key, weak in imports.items() if weak and key not in observed}
    expected = set(imports) - unbound_weak
    matched = expected & observed
    coverage_complete = len(expected) > 0 and matched == expected

    return {
        "ld_files": [p.name for p in ld_files],
        "module": str(module),
        "bindings_from_painterly": bindings,
        "self_bindings_skipped": self_bindings,
        "undefined_dynamic_symbols": len(imports),
        "weak_undefined_left_unbound": sorted(_text_key(key) for key in unbound_weak),
        "expected_bindings": len(expected),
        "matched_bindings": len(matched),
        "coverage_complete": coverage_complete,
        "missing_bindings": sorted(_text_key(key) for key in expected - observed),
        "bound_but_not_imported": sorted(_text_key(key) for key in observed - set(imports)),
        "violation_count": len(violations),
        "per_destination": {
            destination: {
                "bindings": per_destination[destination],
                "violations": per_destination_violations[destination],
            }
            for destination in sorted(per_destination)
        },
        "violating_symbols": [
            {"destination": dst, "symbol": sym, "version": ver or None}
            for dst, sym, ver in sorted(violations)
        ],
    }


def _text_key(key: Key) -> str:
    name, version = key
    return name if version is None else f"{name}@{version}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("ld_debug_dir", type=Path)
    parser.add_argument(
        "--module", type=Path, required=True, help="the _painterly*.so whose trace this is"
    )
    args = parser.parse_args(argv)
    ld_dir = args.ld_debug_dir.resolve()
    module = args.module.resolve()
    result = scan(ld_dir, module)
    (ld_dir / "bindings_summary.txt").write_text(f"{result['violation_count']}\n", encoding="utf-8")
    (ld_dir / "bindings.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"bindings from _painterly: {result['bindings_from_painterly']}, "
        f"self-bindings skipped: {result['self_bindings_skipped']}, "
        f"coverage: {result['matched_bindings']}/{result['expected_bindings']} "
        f"(complete: {result['coverage_complete']}), "
        f"violations: {result['violation_count']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
