#!/usr/bin/env python3
"""Fail if _painterly leaks symbols or imports anything that could clash with Blender's process.

Usage: symbol_audit.py <path-to-module-or-wheel> [--report {text,json}]

The rules follow the binary's own file format. Each format needs its platform tools, or
`llvm-objdump` for PE when dumpbin is absent:

- ELF (Linux): `nm`, `readelf`.
- Mach-O (macOS): `nm`, `otool`.
- PE (Windows): `dumpbin`, or `llvm-objdump` when dumpbin is absent.

A wheel (.whl) may be given instead of a module: its single `_painterly*` file is extracted into a
temporary directory and audited there. Exit status is 0 when every check passes and 1 otherwise. A
check that cannot run is a failure.
"""

import argparse
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
MACOS_MODULE_SYMBOL = "_PyInit__painterly"
# Wheels are extracted into a new empty directory under the repository's .cache/ (CLAUDE.md rule 5).
CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache"

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

# ELF imports are allowed only if they are glibc-versioned, a Python C-API symbol (resolved from the
# interpreter), or a toolchain weak hook. Anything else would bind into Blender's own libraries.
GLIBC_VERSION_PREFIX = "GLIBC_"
PYTHON_API_PATTERN_LINUX = re.compile(r"^_?Py")
# The toolchain's standard weak hooks: weak undefined references that every module carries.
CRT_WEAK_HOOKS_LINUX = frozenset(
    {
        "__gmon_start__",
        "_ITM_deregisterTMCloneTable",
        "_ITM_registerTMCloneTable",
        "__cxa_finalize",
    }
)

# Mach-O dependencies: the C library and the C++ runtime that the module links.
ALLOWED_DYLIBS_MACOS = frozenset({"/usr/lib/libSystem.B.dylib", "/usr/lib/libc++.1.dylib"})
# Mach-O imports: `nm -m` marks a flat-namespace lookup "(dynamically looked up)". Such a name binds
# to the first image in the process that defines it, so only Python C-API names (from the
# interpreter) may be looked up that way.
MACHO_DYNAMIC_PATTERN = re.compile(r"\s(?P<name>\S+) \(dynamically looked up\)")
MACHO_PYTHON_API_PATTERN = re.compile(r"^_+Py")

# PE import names are case-insensitive, so they are compared in lower case.
# python3.dll is the stable-ABI import library's DLL. kernel32.dll is the Windows base library.
# advapi32.dll: Embree enables SeLockMemoryPrivilege for huge pages (embree common/sys/alloc.cpp,
# called from kernels/common/device.cpp); a Windows system DLL, not one Blender ships.
ALLOWED_DLLS_WINDOWS = frozenset({"python3.dll", "kernel32.dll", "advapi32.dll"})

ELF_MAGIC = b"\x7fELF"
# Mach-O 64-bit headers in little- and big-endian byte order, and the fat (universal) header.
MACHO_MAGICS = (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe")
PE_MAGIC = b"MZ"

NEEDED_PATTERN = re.compile(r"\(NEEDED\)\s+Shared library: \[(?P<name>[^\]]+)\]")
# One dumpbin /exports row: ordinal, hint, RVA, then the name. A [NONAME] export has no name, so it
# does not match and the export table fails closed.
DUMPBIN_EXPORT_PATTERN = re.compile(
    r"^\s*\d+\s+[0-9A-Fa-f]+\s+[0-9A-Fa-f]+\s+(?P<name>[^\[\s]\S*)\s*$"
)
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


def _parse_undefined_elf(output: str) -> list[tuple[str, str]]:
    """(name, version) per undefined symbol of `nm -D --undefined-only`.

    `memcpy@GLIBC_2.14` splits at the first '@'. A second leading '@' (`memcpy@@GLIBC_2.14`) is
    dropped.
    An unversioned name has an empty version.
    """
    imports = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 2:
            name, _, rest = fields[-1].partition("@")
            imports.append((name, rest.removeprefix("@")))
    return imports


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


def _elf_import_violations(imports: list[tuple[str, str]]) -> list[str]:
    """Every undefined ELF symbol that the allowlist refuses.

    The allowlist: glibc-versioned, a Python C-API symbol, or a toolchain weak hook.
    """
    violations = []
    for name, version in sorted(set(imports)):
        if (
            version.startswith(GLIBC_VERSION_PREFIX)
            or PYTHON_API_PATTERN_LINUX.match(name)
            or name in CRT_WEAK_HOOKS_LINUX
        ):
            continue
        label = f"{name}@{version}" if version else name
        violations.append(
            f"{label}: not glibc-versioned, a Python C-API symbol or a toolchain weak hook"
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
    dependency_check = Check(
        "dependencies",
        "dependencies must be glibc only (manylinux_2_28 baseline)",
        [f"{lib} is not allowed" for lib in needed if lib not in ALLOWED_NEEDED_LINUX],
    )

    imports = _parse_undefined_elf(_run(["nm", "-D", "--undefined-only", str(path)]))
    import_check = Check(
        "imports",
        "imports: only glibc-versioned, Python C-API or toolchain weak hooks",
        _elf_import_violations(imports),
    )
    return [export_check, dependency_check, import_check]


def _otool_dylibs(output: str) -> list[str]:
    """Install names from `otool -L`.

    The first line names the file. Each later line is '<install name> (...)' for one dependency.
    """
    dylib_lines = output.splitlines()[1:]
    return [line.strip().partition(" (")[0] for line in dylib_lines if line.strip()]


def _macho_import_violations(output: str) -> list[str]:
    """Violations in `nm -m -u` output.

    Every dynamically looked-up symbol must be a Python C-API symbol.
    """
    names = sorted({match.group("name") for match in MACHO_DYNAMIC_PATTERN.finditer(output)})
    return [
        f"{name}: flat-namespace lookup would bind into the host process"
        for name in names
        if not MACHO_PYTHON_API_PATTERN.match(name)
    ]


def _audit_macho(path: Path) -> list[Check]:
    exports = _parse_nm(_run(["nm", "-gU", str(path)]))
    defined = {name for _, name in exports}
    export_check = Check(
        "exports",
        f"all {len(defined)} defined external symbols must be exactly {MACOS_MODULE_SYMBOL}",
        _export_violations(exports, MACOS_MODULE_SYMBOL),
    )

    dylibs = _otool_dylibs(_run(["otool", "-L", str(path)]))
    dependency_check = Check(
        "dependencies",
        "dependencies must be libSystem and libc++ only",
        [f"{dylib} is not allowed" for dylib in dylibs if dylib not in ALLOWED_DYLIBS_MACOS],
    )

    import_check = Check(
        "imports",
        "imports: dynamically looked-up symbols must be Python C-API symbols",
        _macho_import_violations(_run(["nm", "-m", "-u", str(path)])),
    )
    return [export_check, dependency_check, import_check]


def _dumpbin_exports(output: str) -> list[str]:
    """Export names from `dumpbin /exports`: the rows after the 'ordinal hint RVA' header.

    A non-empty row in the table that does not parse, such as a [NONAME] export, raises AuditError:
    its name cannot be checked, so the audit fails rather than passing it.
    """
    names = []
    in_table = False
    for line in output.splitlines():
        stripped = line.strip()
        if "ordinal hint RVA" in stripped:
            in_table = True
        elif stripped.startswith("Summary"):
            in_table = False
        elif in_table and stripped:
            match = DUMPBIN_EXPORT_PATTERN.match(line)
            if match is None:
                raise AuditError(f"cannot parse dumpbin export row: {stripped}")
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
    """Export names from `llvm-objdump --private-headers`.

    The rows follow the 'Ordinal RVA Name' header. The table ends at a blank line or at the end of
    the output. A non-empty row in the table that does not parse raises AuditError.
    """
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
            if match is None:
                raise AuditError(f"cannot parse llvm-objdump export row: {stripped}")
            names.append(match.group("name"))
    return names


def _objdump_dlls(output: str) -> list[str]:
    """DLL names from `llvm-objdump --private-headers` output, used when dumpbin is absent."""
    return OBJDUMP_DLL_PATTERN.findall(output)


def _dll_allowed(name: str) -> bool:
    return name.lower() in ALLOWED_DLLS_WINDOWS


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
        _export_violations([("export", name) for name in exports], MODULE_SYMBOL),
    )
    dependency_check = Check(
        "dependencies",
        "imported DLLs must be python3.dll, kernel32.dll or advapi32.dll",
        [f"{dll} is not allowed" for dll in sorted(set(dlls)) if not _dll_allowed(dll)],
    )
    return [export_check, dependency_check]


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
        "file_format": result.file_format,
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
