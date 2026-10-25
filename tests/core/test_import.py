"""The native module imports and reports the version declared in pyproject.toml."""

import os
import re
import tomllib
from pathlib import Path

import _painterly

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

# The round-off bound on the selftest's t, derived as src/test/test_bvh.cpp:50-87 derives it
# (TQ.3 F19). Embree reports t in binary32, so the bound is that format's round-off:
# u = 2^-24 is the unit round-off of IEEE binary32 with round to nearest, a definition of the
# format. Embree's reciprocal counts as RCP_ROUNDINGS = 5 roundings (its x86 estimate plus one
# Newton step, or the exact quotient on arm64; test_bvh.cpp:70-84), and t takes one reciprocal and
# one product, so its relative error is at most Higham's gamma(HIT_ROUNDINGS) with
# HIT_ROUNDINGS = RCP_ROUNDINGS + 1. The expected t of this file is exact (see the test below), and
# the reference's own binary64 round-off adds one more unit, REFERENCE_ROUNDOFF = u
# (test_bvh.cpp:88-98: the file's binary64 errors are below u, so u over-bounds them).
F32_UNIT_ROUNDOFF = 2.0**-24
RCP_ROUNDINGS = 5
HIT_ROUNDINGS = RCP_ROUNDINGS + 1
REFERENCE_ROUNDOFF = F32_UNIT_ROUNDOFF


def f32_gamma(n: int) -> float:
    """Higham's gamma(n) = n u / (1 - n u) for binary32 (test_bvh.cpp:80-83)."""
    return n * F32_UNIT_ROUNDOFF / (1.0 - n * F32_UNIT_ROUNDOFF)


#: Relative bound on Embree's t for the selftest's ray (test_bvh.cpp:86-87 and :195-198).
HIT_RELATIVE_BOUND = f32_gamma(HIT_ROUNDINGS)

# The selftest's ray (src/blender/selftest.cpp:35-43): from (0.25, 0.25, SELFTEST_ORIGIN_Z) with
# the unnormalized direction (0, 0, SELFTEST_DIRECTION_Z), on the triangle in the plane z = 0. The
# distance along the ray is SELFTEST_ORIGIN_Z, and t is parametric along |d|, so the exact answer
# is SELFTEST_ORIGIN_Z / |SELFTEST_DIRECTION_Z| (SPEC §4).
SELFTEST_ORIGIN_Z = 1.0
SELFTEST_DIRECTION_Z = -2.0
# version_info()["compiler"] is "<id> <version>", for example "GCC 13.3.0" (src/blender/python.cpp).
COMPILER_PATTERN = re.compile(r"^(GCC|Clang|AppleClang|MSVC) \d+(\.\d+)*$")


def test_version_info() -> None:
    expected_version = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    info = _painterly.version_info()
    assert info["version"] == expected_version
    assert info["stable_abi"] is True


def test_compiler_string_names_the_compiler_and_its_version() -> None:
    compiler = _painterly.version_info()["compiler"]
    assert COMPILER_PATTERN.match(compiler), compiler


def test_module_origin(build_dir: Path) -> None:
    """Installed mode (PAINTERLY_TEST_INSTALLED=1) imports the wheel's module, else the build's."""
    module_file = Path(_painterly.__file__)
    if os.environ.get("PAINTERLY_TEST_INSTALLED") == "1":
        assert "site-packages" in module_file.parts, module_file
    else:
        assert module_file.is_relative_to(build_dir), module_file


def test_selftest_embree_unnormalized_direction() -> None:
    """Embree's t is parametric along the unnormalized direction, which SPEC §4 and §5 rely on.

    The ray starts at (0.25, 0.25, 1) with d = (0, 0, -2) and meets the triangle in the plane z = 0
    after distance 1 along the ray. Since |d| = 2, the parametric t is 0.5 and the metric distance
    is 1.0. Embree's hit t depends on the runtime ISA (its AVX2 kernels use explicit FMA), so it is
    not asserted exactly: it is checked against the binary32 round-off bound that
    src/test/test_bvh.cpp derives, not against "nearer 0.5 than 1.0", which any t below 0.75
    satisfies (TQ.3 F19).
    """
    result = _painterly.selftest()
    assert result["hit"] is True
    assert result["prim_id"] == 0
    # t = distance / |d|, and both are exact here: 1.0 / 2.0 = 0.5 (SPEC §4, §5).
    t_expected = SELFTEST_ORIGIN_Z / abs(SELFTEST_DIRECTION_Z)
    assert t_expected == 0.5
    bound = (HIT_RELATIVE_BOUND + REFERENCE_ROUNDOFF) * t_expected
    assert abs(result["t"] - t_expected) <= bound, (result["t"], t_expected, bound)
    assert result["tasking_system"] == 0  # EMBREE_TASKING_SYSTEM=INTERNAL
