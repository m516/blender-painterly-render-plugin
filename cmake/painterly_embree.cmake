# SPDX-License-Identifier: GPL-3.0-or-later
#
# Static, namespaced Embree 4.4.1 for painterly_bvh (src/painterly/bvh/embree.cpp) and for the _painterly module, whose
# selftest (src/blender/selftest.cpp) calls Embree directly (docs/plan.md "Isolation from Blender's own libraries").
#
# Blender 5.2 already has Cycles, Embree 4.4.1 and oneTBB in its process, so we link a private copy that exports
# nothing: a static library, API symbols in the namespace painterly_embree, INTERNAL tasking (no TBB), and only
# triangle and instance geometry.
#
# Provides the INTERFACE target painterly_embree: Embree's include directory (SYSTEM), the Embree library and its internal
# static libraries. painterly_bvh (PRIVATE) and _painterly link it.
#
# Two ways to get that Embree, both configured by cmake/painterly_embree_config.cmake, the one source of truth for how
# Embree is compiled (the C++ standard, position-independent code, the visibility presets, the MSVC runtime, the
# floating-point flags and every EMBREE_* cache option):
#   - embree_DIR unset (the default): FetchContent clones Embree v4.4.1 and builds it in this tree;
#   - embree_DIR set to an Embree install's lib/cmake/embree-4.4.1 (tools/embree_prebuilt.py build makes one):
#     find_package imports the install, so no Embree source is compiled at all.

# The shared configuration. The root CMakeLists.txt includes it first, so this include is a no-op there; it matters for
# any consumer of this file that did not (and it keeps the two paths on one definition).
include(${CMAKE_CURRENT_LIST_DIR}/painterly_embree_config.cmake)

if(embree_DIR)
  # The prebuilt path. EXACT: the install must be Embree 4.4.1, the version this project's shim and the oracle parity
  # tests are written against.
  find_package(embree 4.4.1 EXACT CONFIG REQUIRED)
  message(STATUS "painterly_embree: prebuilt ${embree_DIR}")

  add_library(painterly_embree INTERFACE)
  target_include_directories(painterly_embree SYSTEM INTERFACE "${EMBREE_INCLUDE_DIRS}")
  target_link_libraries(painterly_embree INTERFACE embree)
  return()
endif()

include(FetchContent)

# EXCLUDE_FROM_ALL: Embree's targets are built only as dependencies of painterly_embree's consumers, painterly_bvh and
# _painterly.
FetchContent_Declare(
  embree
  GIT_REPOSITORY https://github.com/RenderKit/embree.git
  GIT_TAG v4.4.1
  GIT_SHALLOW TRUE
  EXCLUDE_FROM_ALL)
FetchContent_MakeAvailable(embree)

# The interface target. Embree's static target `embree` carries its internal libraries as dependencies. Every target of
# this project has a plain name and no namespaced alias (TQ.1 F11): consumers link painterly_embree, the name of our
# private Embree everywhere (this file, EMBREE_API_NAMESPACE and EMBREE_LIBRARY_NAME). Embree's include directory is
# SYSTEM, both here and in the interface of `embree` (its SYSTEM target property), so the warning flags of our targets
# (cmake/painterly_warnings.cmake) report nothing from Embree's headers. Neither changes how Embree itself is compiled.
set_target_properties(embree PROPERTIES SYSTEM TRUE)
add_library(painterly_embree INTERFACE)
target_include_directories(painterly_embree SYSTEM INTERFACE "${embree_SOURCE_DIR}/include")
target_link_libraries(painterly_embree INTERFACE embree)
