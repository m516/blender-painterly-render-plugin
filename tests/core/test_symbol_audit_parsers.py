"""Parsers and rules of tools/symbol_audit.py, checked on canned tool output.

These tests need no platform tools. The canned text is what `dumpbin`, `llvm-objdump`, `otool`,
`nm -m -u` and `nm -D --undefined-only` print. The samples are hand-written in each tool's output
format; they are not captured from a particular binary.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

AUDIT_TOOL = Path(__file__).resolve().parents[2] / "tools" / "symbol_audit.py"

DUMPBIN_EXPORTS = """\
Microsoft (R) COFF/PE Dumper Version 14.44.35207.0
Copyright (C) Microsoft Corporation.  All rights reserved.


Dump of file _painterly.pyd

File Type: DLL

  Section contains the following exports for _painterly.pyd

    00000000 characteristics
    00000000 time date stamp
    0.00 version
       1 ordinal base
       2 number of functions
       2 number of names

    ordinal hint RVA      name

          1    0 00001000 PyInit__painterly
          2    1 00001010 helper_export

  Summary

        1000 .data
"""

DUMPBIN_NONAME_EXPORTS = DUMPBIN_EXPORTS.replace(
    "          2    1 00001010 helper_export",
    "          2    1 00001010 [NONAME]",
)

DUMPBIN_DEPENDENTS = """\
Microsoft (R) COFF/PE Dumper Version 14.44.35207.0
Copyright (C) Microsoft Corporation.  All rights reserved.


Dump of file _painterly.pyd

File Type: DLL

  Image has the following dependencies:

    python3.dll
    KERNEL32.dll
    advapi32.dll
    api-ms-win-crt-runtime-l1-1-0.dll

  Image has the following delay load dependencies:

    VCRUNTIME140.dll

  Summary

        1000 .data
"""

# Shaped like `llvm-objdump --private-headers` output for a two-export DLL (no dumpbin needed).
OBJDUMP_PRIVATE_HEADERS = """\
The Import Tables:
  lookup 00002090 time 00000000 fwd 00000000 name 000020c6 addr 000020a0

    DLL Name: kernel32.dll
    Hint/Ord  Name
           0  GetCurrentProcessId

Export Table:
 DLL name: fake2.dll
 Ordinal base: 1
 Ordinal      RVA  Name
       1   0x1000  PyInit__painterly
       2   0x1010  helper_export
"""

# `otool -L` names the file on its first line, then one indented '<install name> (...)' line per
# dependency.
OTOOL_DYLIBS = """\
/path/to/_painterly.cpython-313-darwin.so:
\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1351.0.0)
\t/usr/lib/libc++.1.dylib (compatibility version 1.0.0, current version 1900.178.0)
\t/opt/local/lib/libembree4.4.dylib (compatibility version 4.0.0, current version 4.4.1)
"""

# `nm -m -u`: a flat-namespace lookup is marked "(dynamically looked up)"; a two-level import
# names its library.
NM_M_U = """\
                 (undefined) external _PyLong_FromLong (dynamically looked up)
                 (undefined) external _rtcNewDevice (dynamically looked up)
                 (undefined) external _malloc (from libSystem)
"""

# `nm -D --undefined-only` on a Linux module: versioned names carry the glibc version after '@'.
NM_UNDEFINED_ELF = """\
                 U PyLong_FromLong
                 w _ITM_deregisterTMCloneTable
                 w _ITM_registerTMCloneTable
                 w __cxa_finalize@GLIBC_2.2.5
                 U __cxa_pure_virtual
                 w __gmon_start__
                 U memcpy@GLIBC_2.14
"""


def _load_audit_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("symbol_audit", AUDIT_TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


audit = _load_audit_tool()


def test_dumpbin_exports_lists_named_rows() -> None:
    assert audit._dumpbin_exports(DUMPBIN_EXPORTS) == ["PyInit__painterly", "helper_export"]


def test_dumpbin_noname_row_fails_closed() -> None:
    with pytest.raises(audit.AuditError, match=r"\[NONAME\]"):
        audit._dumpbin_exports(DUMPBIN_NONAME_EXPORTS)


def test_dumpbin_dependents_includes_delay_load_and_refuses_crt_forwarders() -> None:
    dlls = audit._dumpbin_dependents(DUMPBIN_DEPENDENTS)
    assert dlls == [
        "python3.dll",
        "KERNEL32.dll",
        "advapi32.dll",
        "api-ms-win-crt-runtime-l1-1-0.dll",
        "VCRUNTIME140.dll",
    ]
    assert [dll for dll in dlls if not audit._dll_allowed(dll)] == [
        "api-ms-win-crt-runtime-l1-1-0.dll",
        "VCRUNTIME140.dll",
    ]


def test_objdump_exports_and_dlls() -> None:
    assert audit._objdump_exports(OBJDUMP_PRIVATE_HEADERS) == ["PyInit__painterly", "helper_export"]
    assert audit._objdump_dlls(OBJDUMP_PRIVATE_HEADERS) == ["kernel32.dll"]


def test_objdump_unparseable_export_row_fails_closed() -> None:
    malformed = OBJDUMP_PRIVATE_HEADERS.replace(
        "       2   0x1010  helper_export", "       2  helper_export"
    )
    with pytest.raises(audit.AuditError, match="helper_export"):
        audit._objdump_exports(malformed)


def test_otool_dylibs_refuses_a_non_system_library() -> None:
    dylibs = audit._otool_dylibs(OTOOL_DYLIBS)
    assert dylibs == [
        "/usr/lib/libSystem.B.dylib",
        "/usr/lib/libc++.1.dylib",
        "/opt/local/lib/libembree4.4.dylib",
    ]
    assert [dylib for dylib in dylibs if dylib not in audit.ALLOWED_DYLIBS_MACOS] == [
        "/opt/local/lib/libembree4.4.dylib"
    ]


def test_macho_python_symbol_passes_and_rtc_symbol_fails() -> None:
    assert audit._macho_import_violations(NM_M_U) == [
        "_rtcNewDevice: flat-namespace lookup would bind into the host process"
    ]


def test_elf_undefined_symbols_keep_their_versions() -> None:
    imports = audit._nm_undefined_elf(NM_UNDEFINED_ELF)
    assert ("memcpy", "GLIBC_2.14") in imports
    assert ("PyLong_FromLong", "") in imports
    assert ("__cxa_pure_virtual", "") in imports
    assert audit._nm_undefined_elf("                 U memcpy@@GLIBC_2.14\n") == [
        ("memcpy", "GLIBC_2.14")
    ]


def test_elf_imports_allow_glibc_python_and_weak_hooks_only() -> None:
    violations = audit._elf_import_violations(audit._nm_undefined_elf(NM_UNDEFINED_ELF))
    assert violations == [
        "__cxa_pure_virtual: not glibc-versioned, a Python C-API symbol or a toolchain weak hook"
    ]


def test_elf_import_with_a_non_glibc_version_fails() -> None:
    violations = audit._elf_import_violations(
        audit._nm_undefined_elf("                 U _Znwm@GLIBCXX_3.4\n")
    )
    assert violations == [
        "_Znwm@GLIBCXX_3.4: not glibc-versioned, a Python C-API symbol or a toolchain weak hook"
    ]
