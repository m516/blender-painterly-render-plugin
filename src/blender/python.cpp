// SPDX-License-Identifier: GPL-3.0-or-later
// Native core of the Painterly render engine: the nanobind module _painterly.

#include <nanobind/nanobind.h>
// std::string <-> Python str. Without this caster nanobind raises std::bad_cast
// when the dict is filled.
#include <nanobind/stl/string.h>

#include "selftest.h"

namespace nb = nanobind;

#define PAINTERLY_STR_(x) #x
#define PAINTERLY_STR(x) PAINTERLY_STR_(x)

// __VERSION__ is defined by GCC and Clang; MSVC defines _MSC_FULL_VER instead.
#if defined(__VERSION__)
#  define PAINTERLY_COMPILER __VERSION__
#else
#  define PAINTERLY_COMPILER PAINTERLY_STR(_MSC_FULL_VER)
#endif

// NDEBUG is the standard C/C++ switch for optimised builds (CMake Release sets it).
#if defined(NDEBUG)
#  define PAINTERLY_BUILD_TYPE "Release"
#else
#  define PAINTERLY_BUILD_TYPE "Debug"
#endif

CCL_NAMESPACE_BEGIN

namespace {

nb::dict version_info()
{
  // Py_LIMITED_API is defined by nanobind's STABLE_ABI option.
#if defined(Py_LIMITED_API)
  const bool stable_abi = true;
#else
  const bool stable_abi = false;
#endif

  nb::dict info;
  info["version"] = PAINTERLY_VERSION;
  info["compiler"] = PAINTERLY_COMPILER;
  info["build_type"] = PAINTERLY_BUILD_TYPE;
  info["stable_abi"] = stable_abi;
  return info;
}

nb::dict selftest()
{
  const painterly::SelftestResult result = painterly::selftest_embree();
  nb::dict info;
  info["embree_version"] = result.embree_version;
  info["tasking_system"] = result.tasking_system;
  info["hit"] = result.hit;
  info["t"] = result.t;
  info["prim_id"] = result.prim_id;
  return info;
}

}  // namespace

CCL_NAMESPACE_END

NB_MODULE(_painterly, m)
{
  m.doc() = "Native core of the Painterly render engine (mirrors Cycles' _cycles).";
  m.def(
      "version_info", &painterly::version_info, "Return version and build information as a dict.");
  m.def("selftest",
        &painterly::selftest,
        "Trace one triangle with the statically linked Embree. Return a dict with embree_version, "
        "tasking_system, hit, t and prim_id.");
}
