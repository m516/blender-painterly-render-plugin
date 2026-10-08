// SPDX-License-Identifier: GPL-3.0-or-later
// Native core of the Painterly render engine: the nanobind module _painterly.

#include <nanobind/nanobind.h>

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

static nb::dict version_info()
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

NB_MODULE(_painterly, m)
{
  m.doc() = "Native core of the Painterly render engine (mirrors Cycles' _cycles).";
  m.def("version_info", &version_info, "Return version and build information as a dict.");
}
