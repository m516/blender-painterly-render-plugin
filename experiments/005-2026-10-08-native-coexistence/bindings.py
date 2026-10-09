#!/usr/bin/env python3
"""H3 instrument: which symbols _painterly binds to, and which of those bindings are violations.

Usage: bindings.py <ld_debug_dir> --module <path/to/_painterly*.so> [--rule {registered,coherent}]
                   [--baseline <main bindings.json>]

Input: the glibc ld.so debug files in <ld_debug_dir>. A process started with
LD_BIND_NOW=1 LD_DEBUG=bindings LD_DEBUG_OUTPUT=<ld_debug_dir>/ld writes one file per
process, named ld.<pid>. --module is the module whose trace this is. Its undefined dynamic
symbols (nm -D --undefined-only) are the bindings that the trace must show.

Two rules classify the bindings that _painterly makes. --rule picks one; coherent is the default.
The rules are in the README's "Amendments before running (Opus)" (registered) and "Amendment for
later runs (Opus, 2026-10-09, after the 2026-10-08 run)" (coherent).

- registered: H3 as recorded on 2026-10-08, unchanged. A binding made by _painterly is a violation
  iff either
  - its symbol version starts with GLIBC_ and its destination's basename is not matched by
    GLIBC_PROVIDER_REGISTERED (libc.so.6, libm.so.6, ld-linux-*.so.N); or
  - it has no GLIBC_ version and its symbol does not match ^_?Py. The Python C API must bind to
    the executable that embeds Python, which is blender.
- coherent: the same rule, with two changes.
  - GLIBC_PROVIDER also accepts libpthread.so.0, libdl.so.2, librt.so.1, libutil.so.1 and
    libresolv.so.2, which are separate glibc objects before glibc 2.34.
  - The allocator family is judged as a whole, per process. An allocator-family binding is a
    GLIBC_-versioned binding of a name in ALLOCATOR_FAMILY (glibc manual §3.2.5). Only ld.<pid>
    files that contain a binding made by _painterly contribute, so a child process such as sh does
    not. Let D be the union of the destinations of the module's allocator-family bindings and of
    libc.so.6's allocator-family bindings in the contributing files, self-bindings included. If
    |D| == 1, every allocator-family binding of the module is allowed. Otherwise every one of them
    is a violation. Every other binding follows the registered rule, with GLIBC_PROVIDER.

Both rules skip self-bindings (destination == source). Paths are matched by the full regex and by
basename, never by substring, because the repository path itself contains "blender".

- Coverage: the expected bindings are the module's undefined dynamic symbols, minus the weak
  undefined symbols that the trace does not bind (those stay unresolved, so no trace line can
  show them). The matched bindings are the expected ones that the trace binds from _painterly.
  Coverage is complete iff matched == expected and expected > 0. H3 needs complete coverage
  AND zero violations.
- Control sensitivity: --baseline <main bindings.json> adds control_specific_violations, the
  violations of this run minus those of the baseline, compared by (symbol, version, basename of
  destination). A control is sensitive when it has at least one of them.

Outputs, written into <ld_debug_dir>:
- bindings_summary.txt: the violation count under the chosen rule, one integer on one line.
- bindings.json: rule, totals, coverage, per-destination counts, bound-but-not-imported symbols,
  the allocator record (contributing processes, module and libc destinations, coherent), the
  violating (destination, symbol, version) triples, and control_specific_violations when given.
  The allocator record is computed under both rules; only the coherent rule uses it for verdicts.

Exit status is 1 when the directory has no ld.* file, when there is no binding from _painterly,
or when the module has no undefined dynamic symbols. An instrument that sees nothing cannot show
H3, so those cases must not pass silently.
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
# BINDING with any source object. The source is then matched by basename, never by substring.
ANY_BINDING = re.compile(
    r"binding file (?P<src>\S+) \[\d+\] to (?P<dst>\S+) \[\d+\]: "
    r"normal symbol `(?P<sym>[^']+)'(?: \[(?P<ver>[^\]]+)\])?"
)
LIBC_NAME = "libc.so.6"
GLIBC_VERSION_PREFIX = "GLIBC_"
# glibc's own objects, by basename, for the registered rule (amendment 4 of the 2026-10-08 run).
# Unchanged, so that --rule registered reproduces 2026-10-08.
GLIBC_PROVIDER_REGISTERED = re.compile(
    r"^(libc\.so\.6|libm\.so\.6|ld-linux[A-Za-z0-9_.-]*\.so\.\d+)$"
)
# glibc's objects for the coherent rule: the registered ones, and five more that are separate
# objects before glibc 2.34 (amendment "glibc objects" of the 2026-10-09 amendment).
GLIBC_PROVIDER = re.compile(
    r"^(libc\.so\.6|libm\.so\.6|ld-linux[A-Za-z0-9_.-]*\.so\.\d+"
    r"|libpthread\.so\.0|libdl\.so\.2|librt\.so\.1|libutil\.so\.1|libresolv\.so\.2)$"
)
# The names that glibc lets a replacement allocator interpose (glibc manual §3.2.5, "Replacing
# malloc"). The coherent rule judges their GLIBC_-versioned bindings as one family.
ALLOCATOR_FAMILY = frozenset(
    {
        "malloc",
        "free",
        "calloc",
        "realloc",
        "aligned_alloc",
        "malloc_usable_size",
        "memalign",
        "posix_memalign",
        "pvalloc",
        "valloc",
    }
)
# The Python C API binds to the executable that embeds Python, so it is not a violation.
PYTHON_API = re.compile(r"^_?Py")
LD_FILE_PREFIX = "ld."
# nm -D --undefined-only marks weak undefined symbols with w (or v for weak objects).
WEAK_UNDEFINED_TYPES = ("w", "v")
RULES = ("registered", "coherent")
DEFAULT_RULE = "coherent"

# A symbol as the trace names it: (name, version); version is None when unversioned.
Key = tuple[str, str | None]
# A binding made by _painterly, as the trace names it: (destination, symbol, version).
Binding = tuple[str, str, str | None]


def is_violation(
    symbol: str,
    version: str | None,
    destination: str,
    glibc_provider: re.Pattern[str] = GLIBC_PROVIDER_REGISTERED,
) -> bool:
    """The registered rule for one binding. glibc_provider lists the glibc objects it accepts."""
    if version is not None and version.startswith(GLIBC_VERSION_PREFIX):
        return not glibc_provider.match(Path(destination).name)
    return not PYTHON_API.match(symbol)


def is_allocator_binding(symbol: str, version: str | None) -> bool:
    """True for a GLIBC_-versioned binding of a name in ALLOCATOR_FAMILY.

    This is the unit that the coherent rule judges as one family. It applies to the module's
    bindings and to libc.so.6's bindings alike.
    """
    return (
        symbol in ALLOCATOR_FAMILY
        and version is not None
        and version.startswith(GLIBC_VERSION_PREFIX)
    )


def is_violation_under(
    rule: str, symbol: str, version: str | None, destination: str, allocator_coherent: bool
) -> bool:
    """Classify one binding made by _painterly under rule.

    allocator_coherent only matters to the coherent rule, for an allocator-family binding.
    """
    if rule == "registered":
        return is_violation(symbol, version, destination)
    if is_allocator_binding(symbol, version):
        return not allocator_coherent
    return is_violation(symbol, version, destination, GLIBC_PROVIDER)


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


def scan(ld_dir: Path, module: Path, rule: str = DEFAULT_RULE) -> dict:
    """Read the traces in ld_dir and classify the bindings made by _painterly under rule.

    Returns the bindings.json record, without control_specific_violations. Raises SystemExit when
    the trace or the module cannot show H3.
    """
    if rule not in RULES:
        raise ValueError(f"unknown rule {rule!r}; expected one of {RULES}")
    ld_files = sorted(
        p for p in ld_dir.iterdir() if p.is_file() and p.name.startswith(LD_FILE_PREFIX)
    )
    if not ld_files:
        raise SystemExit(f"bindings.py: no ld.* files in {ld_dir}; LD_DEBUG_OUTPUT was not written")
    imports = undefined_symbols(module)
    if not imports:
        raise SystemExit(f"bindings.py: nm finds no undefined dynamic symbols in {module}")

    # Pass 1: read every process. Per file, keep its non-self bindings made by _painterly, the
    # destinations of libc.so.6's allocator-family bindings (self-bindings included), and whether
    # the file holds any binding made by _painterly, which makes it a contributing process.
    self_bindings = 0
    module_bindings: dict[str, list[Binding]] = {}
    libc_destinations: dict[str, set[str]] = {}
    contributing: list[str] = []
    for path in ld_files:
        name = path.name
        module_bindings[name] = []
        libc_destinations[name] = set()
        binds_module = False
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = BINDING.search(line)
            if match is not None:
                binds_module = True
                if match["dst"] == match["src"]:
                    self_bindings += 1
                else:
                    module_bindings[name].append((match["dst"], match["sym"], match["ver"]))
                continue
            match = ANY_BINDING.search(line)
            if (
                match is not None
                and Path(match["src"]).name == LIBC_NAME
                and is_allocator_binding(match["sym"], match["ver"])
            ):
                libc_destinations[name].add(match["dst"])
        if binds_module:
            contributing.append(name)

    # The allocator record. D is the union over the contributing processes, so a process without a
    # binding from _painterly (such as a child sh) takes no part.
    module_allocator_destinations = {
        destination
        for name in contributing
        for destination, symbol, version in module_bindings[name]
        if is_allocator_binding(symbol, version)
    }
    libc_allocator_destinations = set().union(*(libc_destinations[name] for name in contributing))
    allocator_coherent = len(module_allocator_destinations | libc_allocator_destinations) == 1

    # Pass 2: classify. Coverage counts every non-self binding, in every process.
    bindings = 0
    per_destination = Counter()
    per_destination_violations = Counter()
    violations: set[tuple[str, str, str]] = set()
    observed: set[Key] = set()
    for file_bindings in module_bindings.values():
        for destination, symbol, version in file_bindings:
            bindings += 1
            per_destination[destination] += 1
            observed.add((symbol, version))
            if is_violation_under(rule, symbol, version, destination, allocator_coherent):
                per_destination_violations[destination] += 1
                violations.add((destination, symbol, version or ""))

    if bindings == 0:
        raise SystemExit(f"bindings.py: no binding from _painterly in {ld_dir}; the trace is empty")

    unbound_weak = {key for key, weak in imports.items() if weak and key not in observed}
    expected = set(imports) - unbound_weak
    matched = expected & observed
    coverage_complete = len(expected) > 0 and matched == expected

    return {
        "rule": rule,
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
        "allocator": {
            "processes": contributing,
            "module_destinations": sorted(module_allocator_destinations),
            "libc_destinations": sorted(libc_allocator_destinations),
            "coherent": allocator_coherent,
        },
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


def violation_key(entry: dict) -> tuple[str, str, str]:
    """(symbol, version, basename of destination) of one violating_symbols entry.

    The version is "" when the symbol is unversioned.
    """
    return (entry["symbol"], entry["version"] or "", Path(entry["destination"]).name)


def control_specific_violations(result: dict, baseline: dict) -> dict:
    """The violations of result that baseline does not have, as a count and a list.

    Violations are compared by violation_key. The list's destination is a basename.
    """
    baseline_keys = {violation_key(entry) for entry in baseline["violating_symbols"]}
    specific = sorted(
        {violation_key(entry) for entry in result["violating_symbols"]} - baseline_keys
    )
    return {
        "count": len(specific),
        "violations": [
            {"symbol": symbol, "version": version or None, "destination": destination}
            for symbol, version, destination in specific
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
    parser.add_argument(
        "--rule",
        choices=RULES,
        default=DEFAULT_RULE,
        help="registered (the 2026-10-08 rule) or coherent (later runs); default: coherent",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="the main run's bindings.json; adds control_specific_violations (control runs)",
    )
    args = parser.parse_args(argv)
    ld_dir = args.ld_debug_dir.resolve()
    module = args.module.resolve()
    baseline = None
    if args.baseline is not None:
        if not args.baseline.is_file():
            raise SystemExit(f"bindings.py: baseline {args.baseline} does not exist")
        baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    result = scan(ld_dir, module, args.rule)
    if baseline is not None:
        result["control_specific_violations"] = control_specific_violations(result, baseline)
    (ld_dir / "bindings_summary.txt").write_text(f"{result['violation_count']}\n", encoding="utf-8")
    (ld_dir / "bindings.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    line = (
        f"rule: {result['rule']}; "
        f"bindings from _painterly: {result['bindings_from_painterly']}, "
        f"self-bindings skipped: {result['self_bindings_skipped']}, "
        f"coverage: {result['matched_bindings']}/{result['expected_bindings']} "
        f"(complete: {result['coverage_complete']}), "
        f"violations: {result['violation_count']}"
    )
    if baseline is not None:
        line += f", control-specific violations: {result['control_specific_violations']['count']}"
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
