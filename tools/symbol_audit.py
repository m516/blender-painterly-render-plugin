#!/usr/bin/env python3
"""Fail if _painterly leaks symbols or imports anything that could clash with Blender's process.

Usage: symbol_audit.py <path-to-module-or-wheel> [--report {text,json}]

The rules follow the binary's own file format, so a module is audited the same way on any host:

- ELF (Linux): `nm`, `readelf`.
- Mach-O (macOS): `nm`, `otool`.
- PE (Windows): `dumpbin`, or `llvm-objdump` when dumpbin is absent.

A wheel (.whl) may be given instead of a module: its single `_painterly*` file is extracted into a
temporary directory and audited there. Exit status is 0 when every check passes and 1 otherwise. A
check that cannot run is a failure.
"""

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

# The one symbol the module may export. Mach-O C symbols carry a leading underscore.
MODULE_SYMBOL = "PyInit__painterly"
# Wheels are extracted into a new empty directory under the repository's .cache/ (CLAUDE.md rule 5).
CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"
MACOS_MODULE_SYMBOL = "_PyInit__painterly"

# glibc is the manylinux_2_28 baseline Blender itself requires. The module links libstdc++ and
# libgcc statically, so neither may appear as a dependency.
ALLOWED_NEEDED_LINUX = frozenset(
    {
        "libc.so.6",
        "libm.so.6",
        "libpthread.so.0",
        "libdl.so.2",
        "librt.so.1",
        "ld-linux-x86-64.so.2",
        "ld-linux-aarch64.so.1",
    }
)

# Imported Linux symbols with these substrings belong to Blender's libraries (Embree tasking,
# oneTBB, OpenImageIO, OpenColorIO). A C++ mangled name (prefix `_Z`) means a C++ library is
# imported and is refused for the same reason.
CXX_MANGLED_PREFIX = "_Z"
FORBIDDEN_IMPORT_SUBSTRINGS_LINUX = ("rtc", "tbb", "OIIO", "OCIO")

# Mach-O dependencies: the C library and the C++ runtime that the module links.
ALLOWED_DYLIBS_MACOS = frozenset({"/usr/lib/libSystem.B.dylib", "/usr/lib/libc++.1.dylib"})

# PE import names are case-insensitive, so they are compared in lower case.
# python3.dll is the stable-ABI import library's DLL. kernel32.dll is the Windows base library.
# api-ms-win-crt-*.dll are the Universal CRT forwarders that ship with Windows. They are allowed
# only because the static CRT (/MT) may still import them. They are OS components, not Blender's.
ALLOWED_DLLS_WINDOWS = frozenset({"python3.dll", "kernel32.dll"})
ALLOWED_DLL_PATTERNS_WINDOWS = ("api-ms-win-crt-*.dll",)

ELF_MAGIC = b"\x7fELF"
# Mach-O 64-bit headers in little- and big-endian byte order, and the fat (universal) header.
MACHO_MAGICS = (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe")
PE_MAGIC = b"MZ"

NEEDED_PATTERN = re.compile(r"\(NEEDED\)\s+Shared library: \[(?P<name>[^\]]+)\]")
# One dumpbin /exports row: ordinal, hint, RVA, then the name (or [NONAME]).
DUMPBIN_EXPORT_PATTERN = re.compile(r"^\s*\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+(?P<name>\S+)\s*$")
OBJDUMP_EXPORT_PATTERN = re.compile(r"^\s*\d+\s+0x[0-9A-Fa-f]+\s+(?P<name>\S+)\s*$")
OBJDUMP_DLL_PATTERN = re.compile(r"DLL Name:\s*(?P<name>\S+)")


class AuditError(Exception):
    """A check could not run. The audit fails rather than passing unchecked."""


@dataclass
class Check:
    name: str
    rule: str
    violations: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations


@dataclass
class AuditResult:
    module: str
    file_format: str
    checks: list[Check]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)


def _run(command: list[str]) -> str:
    """Run a binutils-style tool and return stdout; raise AuditError if it is missing or fails."""
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, errors="replace", check=False
        )
    except FileNotFoundError as err:
        raise AuditError(f"tool not found: {command[0]}") from err
    if completed.returncode != 0:
        raise AuditError(f"{command[0]} exited {completed.returncode}: {completed.stderr.strip()}")
    return completed.stdout


def _parse_nm(output: str) -> list[tuple[str, str]]:
    """(type, name) per nm line. The name is the last field, minus any @version suffix."""
    symbols = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 2:
            symbols.append((fields[-2], fields[-1].partition("@")[0]))
    return symbols


def _export_violations(exports: list[tuple[str, str]], expected: str) -> list[str]:
    """Every export other than `expected`, plus an error if `expected` itself is missing."""
    violations = [
        f"{kind} {name}"
        for kind, name in sorted(set(exports), key=lambda s: s[1])
        if name != expected
    ]
    if expected not in {name for _, name in exports}:
        violations.append(f"{expected} is not exported")
    return violations


def _import_violations(imports: list[str]) -> list[str]:
    violations = []
    for name in sorted(set(imports)):
        if name.startswith(CXX_MANGLED_PREFIX):
            violations.append(f"{name}: C++ mangled name")
        violations.extend(
            f"{name}: contains '{token}'"
            for token in FORBIDDEN_IMPORT_SUBSTRINGS_LINUX
            if token in name
        )
    return violations


def _audit_elf(path: Path) -> list[Check]:
    exports = _parse_nm(_run(["nm", "-D", "--defined-only", str(path)]))
    defined = {name for _, name in exports}
    export_check = Check(
        "exports",
        f"all {len(defined)} defined dynamic symbols must be exactly {MODULE_SYMBOL}",
        _export_violations(exports, MODULE_SYMBOL),
    )

    needed = NEEDED_PATTERN.findall(_run(["readelf", "-d", str(path)]))
    needed_check = Check(
        "NEEDED",
        "dependencies must be glibc only (manylinux_2_28 baseline)",
        [f"{lib} is not allowed" for lib in needed if lib not in ALLOWED_NEEDED_LINUX],
    )

    imports = [name for _, name in _parse_nm(_run(["nm", "-D", "--undefined-only", str(path)]))]
    import_check = Check(
        "imports",
        f"{len(set(imports))} undefined symbols, none C++ mangled or from Blender's libraries",
        _import_violations(imports),
    )
    return [export_check, needed_check, import_check]


def _audit_macho(path: Path) -> list[Check]:
    exports = _parse_nm(_run(["nm", "-gU", str(path)]))
    defined = {name for _, name in exports}
    export_check = Check(
        "exports",
        f"all {len(defined)} defined external symbols must be exactly {MACOS_MODULE_SYMBOL}",
        _export_violations(exports, MACOS_MODULE_SYMBOL),
    )

    # otool -L: first the file name, then one '<install name> (...)' line per dependency.
    dylib_lines = _run(["otool", "-L", str(path)]).splitlines()[1:]
    dylibs = [line.strip().partition(" (")[0] for line in dylib_lines if line.strip()]
    dylib_check = Check(
        "dylibs",
        "dependencies must be libSystem and libc++ only",
        [f"{dylib} is not allowed" for dylib in dylibs if dylib not in ALLOWED_DYLIBS_MACOS],
    )
    return [export_check, dylib_check]


def _dumpbin_exports(output: str) -> list[str]:
    """Export names from `dumpbin /exports` output: the rows after the 'ordinal hint RVA' header."""
    names = []
    in_table = False
    for line in output.splitlines():
        stripped = line.strip()
        if "ordinal hint RVA" in stripped:
            in_table = True
        elif stripped.startswith("Summary"):
            in_table = False
        elif in_table:
            match = DUMPBIN_EXPORT_PATTERN.match(line)
            if match:
                names.append(match.group("name"))
    return names


def _dumpbin_dependents(output: str) -> list[str]:
    """DLL names from `dumpbin /dependents`: the regular and the delay-load dependency lists."""
    dlls = []
    in_list = False
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("Image has the following"):
            in_list = True
        elif stripped.startswith("Summary"):
            in_list = False
        elif in_list and stripped.lower().endswith(".dll"):
            dlls.append(stripped)
    return dlls


def _objdump_exports(output: str) -> list[str]:
    """Export names from llvm-objdump --private-headers: the 'Ordinal RVA Name' table rows."""
    names = []
    in_table = False
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("Ordinal") and "RVA" in stripped:
            in_table = True
        elif not stripped:
            in_table = False
        elif in_table:
            match = OBJDUMP_EXPORT_PATTERN.match(line)
            if match:
                names.append(match.group("name"))
    return names


def _objdump_dlls(output: str) -> list[str]:
    """DLL names from `llvm-objdump --private-headers` output, used when dumpbin is absent."""
    return OBJDUMP_DLL_PATTERN.findall(output)


def _dll_allowed(name: str) -> bool:
    lowered = name.lower()
    return lowered in ALLOWED_DLLS_WINDOWS or any(
        fnmatch.fnmatch(lowered, pattern) for pattern in ALLOWED_DLL_PATTERNS_WINDOWS
    )


def _audit_pe(path: Path) -> list[Check]:
    if shutil.which("dumpbin"):
        exports = _dumpbin_exports(_run(["dumpbin", "/exports", str(path)]))
        dlls = _dumpbin_dependents(_run(["dumpbin", "/dependents", str(path)]))
    else:
        objdump = _run(["llvm-objdump", "--private-headers", str(path)])
        exports = _objdump_exports(objdump)
        dlls = _objdump_dlls(objdump)

    export_check = Check(
        "exports",
        f"all {len(set(exports))} exported symbols must be exactly {MODULE_SYMBOL}",
        [f"export {name}" for name in sorted(set(exports)) if name != MODULE_SYMBOL]
        + ([f"{MODULE_SYMBOL} is not exported"] if MODULE_SYMBOL not in exports else []),
    )
    dll_check = Check(
        "dependents",
        "imported DLLs must be python3.dll, KERNEL32.dll or api-ms-win-crt-*.dll",
        [f"{dll} is not allowed" for dll in sorted(set(dlls)) if not _dll_allowed(dll)],
    )
    return [export_check, dll_check]


def _audit_module(path: Path, label: str) -> AuditResult:
    """Audit one module, choosing the rules from its own file format."""
    if not path.is_file():
        raise AuditError(f"{label} does not exist")
    with path.open("rb") as handle:
        magic = handle.read(4)
    if magic == ELF_MAGIC:
        return AuditResult(label, "ELF", _audit_elf(path))
    if magic in MACHO_MAGICS:
        return AuditResult(label, "Mach-O", _audit_macho(path))
    if magic[:2] == PE_MAGIC:
        return AuditResult(label, "PE", _audit_pe(path))
    raise AuditError(f"{label} is not an ELF, Mach-O or PE file")


def _is_module_name(name: str) -> bool:
    """True for a `_painterly*` extension module: .so on Linux and macOS, .pyd on Windows."""
    return name.startswith("_painterly") and name.endswith((".so", ".pyd"))


def _extract_module(wheel: Path, destination: Path) -> Path:
    """Extract the single `_painterly*` extension module of a wheel and return its new path."""
    try:
        with zipfile.ZipFile(wheel) as archive:
            members = [
                info
                for info in archive.infolist()
                if not info.is_dir() and _is_module_name(PurePosixPath(info.filename).name)
            ]
            if len(members) != 1:
                raise AuditError(
                    f"{wheel.name} must contain exactly one _painterly* extension module,"
                    f" found {len(members)}"
                )
            name = PurePosixPath(members[0].filename).name
            target = destination / name
            target.write_bytes(archive.read(members[0]))
    except zipfile.BadZipFile as err:
        raise AuditError(f"{wheel} is not a valid wheel: {err}") from err
    return target


def _audit_input(path: Path) -> AuditResult:
    if path.suffix.lower() == ".whl":
        CACHE_DIR.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="symbol_audit-", dir=CACHE_DIR) as extract_dir:
            module = _extract_module(path, Path(extract_dir))
            return _audit_module(module, f"{path}:{module.name}")
    return _audit_module(path, str(path))


def _render_text(result: AuditResult) -> str:
    lines = [f"symbol audit of {result.module} ({result.file_format})"]
    for check in result.checks:
        status = "PASS" if check.passed else "FAIL"
        lines.append(f"[{status}] {check.name}: {check.rule}")
        lines.extend(f"    - {violation}" for violation in check.violations)
    if result.passed:
        lines.append("RESULT: PASS")
    else:
        count = sum(len(check.violations) for check in result.checks)
        lines.append(f"RESULT: FAIL ({count} violation(s))")
    return "\n".join(lines)


def _render_json(result: AuditResult) -> str:
    report = {
        "module": result.module,
        "format": result.file_format,
        "passed": result.passed,
        "checks": [
            {
                "name": check.name,
                "rule": check.rule,
                "passed": check.passed,
                "violations": check.violations,
            }
            for check in result.checks
        ],
    }
    return json.dumps(report, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit a _painterly module or a wheel for isolation."
    )
    parser.add_argument(
        "path", type=Path, help="built _painterly* module, or a painterly-core wheel"
    )
    parser.add_argument(
        "--report", choices=("text", "json"), default="text", help="report format (default: text)"
    )
    args = parser.parse_args(argv)

    try:
        result = _audit_input(args.path)
    except (AuditError, OSError) as err:
        result = AuditResult(
            str(args.path), "unknown", [Check("run", "the audit must be able to run", [str(err)])]
        )

    print(_render_json(result) if args.report == "json" else _render_text(result))
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
