"""Tests of the H3 instrument, bindings.py: both rules, and control-specific violations.

The traces are synthetic ld.<pid> files written into tmp_path. nm is replaced by a stub that
returns the module's undefined dynamic symbols, so no real trace or module is read. The paths
below are invented, except that the basenames are those of the recorded 2026-10-08 trace.
"""

import importlib.util
import json
from collections.abc import Callable
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "experiment_005_bindings", Path(__file__).resolve().parent / "bindings.py"
)
assert _SPEC is not None and _SPEC.loader is not None
bindings = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(bindings)

MODULE = Path("/work/build/src/blender/_painterly.abi3.so")  # not read: nm is stubbed
PAINTERLY = "/work/build/src/blender/_painterly.abi3.so"
PROXY = "/work/blender/lib/libtbbmalloc_proxy.so.2"
LIBC = "/lib/x86_64-linux-gnu/libc.so.6"
LIBPTHREAD = "/lib/x86_64-linux-gnu/libpthread.so.0"
LIBSTDCXX = "/lib/x86_64-linux-gnu/libstdc++.so.6"
GLIBC_2_2_5 = "GLIBC_2.2.5"

Imports = dict[tuple[str, str | None], bool]


def trace_line(pid: int, src: str, dst: str, symbol: str, version: str | None = None) -> str:
    """One LD_DEBUG=bindings line, in glibc's format, with the pid prefix of the recorded traces."""
    suffix = "" if version is None else f" [{version}]"
    return f"     {pid}:\tbinding file {src} [0] to {dst} [0]: normal symbol `{symbol}'{suffix}"


def write_process(ld_dir: Path, pid: int, lines: list[str]) -> None:
    """Write one process's trace as ld.<pid> in ld_dir."""
    ld_dir.mkdir(parents=True, exist_ok=True)
    (ld_dir / f"ld.{pid}").write_text("\n".join(lines) + "\n", encoding="utf-8")


def violation_triples(result: dict) -> set[tuple[str, str, str | None]]:
    """(destination, symbol, version) of each violation in a bindings.json record."""
    return {(v["destination"], v["symbol"], v["version"]) for v in result["violating_symbols"]}


# The module's allocator family and libc's, all bound to one proxy: coherent.
ALLOCATOR_IMPORTS: Imports = {
    ("malloc", GLIBC_2_2_5): False,
    ("free", GLIBC_2_2_5): False,
    ("posix_memalign", GLIBC_2_2_5): False,
}
ALLOCATOR_LINES = [
    trace_line(100, PAINTERLY, PROXY, "malloc", GLIBC_2_2_5),
    trace_line(100, PAINTERLY, PROXY, "free", GLIBC_2_2_5),
    trace_line(100, PAINTERLY, PROXY, "posix_memalign", GLIBC_2_2_5),
    trace_line(100, LIBC, PROXY, "malloc", GLIBC_2_2_5),
    trace_line(100, LIBC, PROXY, "free", GLIBC_2_2_5),
]


@pytest.fixture
def stub_nm(monkeypatch: pytest.MonkeyPatch) -> Callable[[Imports], None]:
    """Replace nm: the module's undefined dynamic symbols are the mapping the test passes in."""

    def install(imports: Imports) -> None:
        monkeypatch.setattr(bindings, "undefined_symbols", lambda module: dict(imports))

    return install


def test_coherent_allocator_family_through_one_proxy_has_no_violations(tmp_path, stub_nm) -> None:
    stub_nm(ALLOCATOR_IMPORTS)
    write_process(tmp_path, 100, ALLOCATOR_LINES)
    result = bindings.scan(tmp_path, MODULE, "coherent")
    assert result["violation_count"] == 0
    assert result["allocator"] == {
        "processes": ["ld.100"],
        "module_destinations": [PROXY],
        "libc_destinations": [PROXY],
        "coherent": True,
    }
    assert result["coverage_complete"] is True


def test_libc_self_binding_makes_the_allocator_incoherent(tmp_path, stub_nm) -> None:
    stub_nm({("malloc", GLIBC_2_2_5): False})
    write_process(
        tmp_path,
        100,
        [
            trace_line(100, PAINTERLY, PROXY, "malloc", GLIBC_2_2_5),
            trace_line(100, LIBC, LIBC, "malloc", GLIBC_2_2_5),
        ],
    )
    result = bindings.scan(tmp_path, MODULE, "coherent")
    assert result["allocator"]["coherent"] is False
    assert result["allocator"]["libc_destinations"] == [LIBC]
    assert violation_triples(result) == {(PROXY, "malloc", GLIBC_2_2_5)}


def test_module_free_to_libc_makes_the_allocator_incoherent(tmp_path, stub_nm) -> None:
    stub_nm({("malloc", GLIBC_2_2_5): False, ("free", GLIBC_2_2_5): False})
    write_process(
        tmp_path,
        100,
        [
            trace_line(100, PAINTERLY, PROXY, "malloc", GLIBC_2_2_5),
            trace_line(100, PAINTERLY, LIBC, "free", GLIBC_2_2_5),
        ],
    )
    result = bindings.scan(tmp_path, MODULE, "coherent")
    assert result["allocator"]["coherent"] is False
    assert result["violation_count"] == 2
    assert violation_triples(result) == {
        (PROXY, "malloc", GLIBC_2_2_5),
        (LIBC, "free", GLIBC_2_2_5),
    }


def test_pthread_create_from_libpthread_is_allowed_only_by_the_coherent_rule(
    tmp_path, stub_nm
) -> None:
    stub_nm({("pthread_create", GLIBC_2_2_5): False})
    write_process(
        tmp_path, 100, [trace_line(100, PAINTERLY, LIBPTHREAD, "pthread_create", GLIBC_2_2_5)]
    )
    assert bindings.scan(tmp_path, MODULE, "coherent")["violation_count"] == 0
    assert bindings.scan(tmp_path, MODULE, "registered")["violation_count"] == 1


def test_cxa_pure_virtual_from_libstdcxx_is_a_violation_under_both_rules(tmp_path, stub_nm) -> None:
    stub_nm({("__cxa_pure_virtual", None): False})
    write_process(tmp_path, 100, [trace_line(100, PAINTERLY, LIBSTDCXX, "__cxa_pure_virtual")])
    assert bindings.scan(tmp_path, MODULE, "coherent")["violation_count"] == 1
    assert bindings.scan(tmp_path, MODULE, "registered")["violation_count"] == 1


def test_control_specific_violations_subtract_the_baseline(tmp_path, stub_nm) -> None:
    # The control has A and B; the baseline has A, in another directory. The comparison is by
    # basename, so A is subtracted and only B remains.
    stub_nm({("__cxa_pure_virtual", None): False, ("_Znwm", None): False})
    main_dir = tmp_path / "main"
    control_dir = tmp_path / "control"
    write_process(main_dir, 100, [trace_line(100, PAINTERLY, LIBSTDCXX, "__cxa_pure_virtual")])
    write_process(
        control_dir,
        100,
        [
            trace_line(100, PAINTERLY, "/usr/lib/libstdc++.so.6", "__cxa_pure_virtual"),
            trace_line(100, PAINTERLY, "/usr/lib/libstdc++.so.6", "_Znwm"),
        ],
    )
    assert bindings.main(["--module", str(MODULE), str(main_dir)]) == 0
    baseline = main_dir / "bindings.json"
    assert (
        bindings.main([str(control_dir), "--module", str(MODULE), "--baseline", str(baseline)]) == 0
    )
    result = json.loads((control_dir / "bindings.json").read_text(encoding="utf-8"))
    specific = result["control_specific_violations"]
    assert specific["count"] == 1
    assert [v["symbol"] for v in specific["violations"]] == ["_Znwm"]
    assert result["rule"] == "coherent"


def test_a_process_without_a_module_binding_takes_no_part(tmp_path, stub_nm) -> None:
    # The second process is a child whose libc binds malloc to itself, with no binding from
    # _painterly. It must not add a destination to D, so the allocator stays coherent.
    stub_nm(ALLOCATOR_IMPORTS)
    write_process(tmp_path, 100, ALLOCATOR_LINES)
    write_process(tmp_path, 200, [trace_line(200, LIBC, LIBC, "malloc", GLIBC_2_2_5)])
    result = bindings.scan(tmp_path, MODULE, "coherent")
    assert result["allocator"]["processes"] == ["ld.100"]
    assert result["allocator"]["coherent"] is True
    assert result["violation_count"] == 0
