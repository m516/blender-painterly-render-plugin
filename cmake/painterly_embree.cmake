# SPDX-License-Identifier: GPL-3.0-or-later
#
# Static, namespaced Embree 4.4.1 for the _painterly module (docs/plan.md "Isolation from Blender's own libraries").
#
# Blender 5.2 already has Cycles, Embree 4.4.1 and oneTBB in its process, so we link a private copy that exports
# nothing: a static library, API symbols in the namespace painterly_embree, INTERNAL tasking (no TBB), and only
# triangle and instance geometry.
#
# Provides the interface target painterly::embree (include dirs, the Embree library and its internal static libraries).

include(FetchContent)

# Knob: the highest ISA Embree compiles in. Embree's runtime dispatch covers the ISAs below it on x86_64.
if(CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|AMD64|amd64)$")
  set(_painterly_embree_isa_default AVX2)
elseif(CMAKE_SYSTEM_PROCESSOR MATCHES "^(arm64|ARM64|aarch64)$")
  set(_painterly_embree_isa_default NEON2X)
else()
  message(FATAL_ERROR "painterly_embree: no default PAINTERLY_EMBREE_MAX_ISA for ${CMAKE_SYSTEM_PROCESSOR}")
endif()
# Not FORCE: a value the user chose on the command line survives reconfiguration.
set(PAINTERLY_EMBREE_MAX_ISA "${_painterly_embree_isa_default}" CACHE STRING
    "Highest ISA Embree builds: AVX2 on x86_64, NEON2X on arm64")

# Embree cache options. FORCE overrides values cached by an earlier configure.
set(EMBREE_STATIC_LIB ON CACHE BOOL "Build Embree as a static library" FORCE)
set(EMBREE_API_NAMESPACE painterly_embree CACHE STRING "C++ namespace for Embree API symbols" FORCE)
set(EMBREE_LIBRARY_NAME painterly_embree CACHE STRING "Embree library file name" FORCE)
set(EMBREE_TASKING_SYSTEM INTERNAL CACHE STRING "Selects tasking system" FORCE)
# arm64: EMBREE_MAX_ISA=NEON2X would enable both NEON and NEON2X, which AppleClang refuses in a static build
# (embree CMakeLists.txt:494-520). So EMBREE_MAX_ISA is NONE and exactly one of the two NEON flags is ON.
if(CMAKE_SYSTEM_PROCESSOR MATCHES "^(arm64|ARM64|aarch64)$")
  set(EMBREE_MAX_ISA NONE CACHE STRING "Selects highest ISA to support" FORCE)
  if(PAINTERLY_EMBREE_MAX_ISA STREQUAL "NEON2X")
    set(EMBREE_ISA_NEON OFF CACHE BOOL "Enables NEON ISA." FORCE)
    set(EMBREE_ISA_NEON2X ON CACHE BOOL "Enables NEON ISA double pumped." FORCE)
  elseif(PAINTERLY_EMBREE_MAX_ISA STREQUAL "NEON")
    set(EMBREE_ISA_NEON ON CACHE BOOL "Enables NEON ISA." FORCE)
    set(EMBREE_ISA_NEON2X OFF CACHE BOOL "Enables NEON ISA double pumped." FORCE)
  else()
    message(FATAL_ERROR "painterly_embree: PAINTERLY_EMBREE_MAX_ISA must be NEON or NEON2X on arm64, not ${PAINTERLY_EMBREE_MAX_ISA}")
  endif()
else()
  set(EMBREE_MAX_ISA ${PAINTERLY_EMBREE_MAX_ISA} CACHE STRING "Selects highest ISA to support" FORCE)
endif()
set(EMBREE_ISPC_SUPPORT OFF CACHE BOOL "Build Embree with ISPC support" FORCE)
set(EMBREE_TUTORIALS OFF CACHE BOOL "Build Embree tutorials" FORCE)
set(EMBREE_GEOMETRY_TRIANGLE ON CACHE BOOL "Enables triangle geometries" FORCE)
set(EMBREE_GEOMETRY_INSTANCE ON CACHE BOOL "Enables instances" FORCE)
set(EMBREE_GEOMETRY_QUAD OFF CACHE BOOL "Enables quad geometries" FORCE)
set(EMBREE_GEOMETRY_CURVE OFF CACHE BOOL "Enables curve geometries" FORCE)
set(EMBREE_GEOMETRY_SUBDIVISION OFF CACHE BOOL "Enables subdivision geometries" FORCE)
set(EMBREE_GEOMETRY_USER OFF CACHE BOOL "Enables user geometries" FORCE)
set(EMBREE_GEOMETRY_INSTANCE_ARRAY OFF CACHE BOOL "Enables instance arrays" FORCE)
set(EMBREE_GEOMETRY_GRID OFF CACHE BOOL "Enables grid geometries" FORCE)
set(EMBREE_GEOMETRY_POINT OFF CACHE BOOL "Enables point geometries" FORCE)
set(EMBREE_RAY_MASK ON CACHE BOOL "Enables ray mask support" FORCE)
set(EMBREE_BACKFACE_CULLING OFF CACHE BOOL "Enables backface culling" FORCE)
set(EMBREE_STAT_COUNTERS OFF CACHE BOOL "Enables statistic counters" FORCE)
set(EMBREE_INSTALL_DEPENDENCIES OFF CACHE BOOL "Install Embree dependencies" FORCE)
set(EMBREE_ZIP_MODE OFF CACHE BOOL "Create Embree ZIP package" FORCE)

# EXCLUDE_FROM_ALL: Embree's targets are built only as dependencies of _painterly.
FetchContent_Declare(
  embree
  GIT_REPOSITORY https://github.com/RenderKit/embree.git
  GIT_TAG v4.4.1
  GIT_SHALLOW TRUE
  EXCLUDE_FROM_ALL)
FetchContent_MakeAvailable(embree)

# Interface target. Embree's static target carries its internal libraries as dependencies.
add_library(painterly_embree INTERFACE)
target_include_directories(painterly_embree INTERFACE "${embree_SOURCE_DIR}/include")
target_link_libraries(painterly_embree INTERFACE embree)
add_library(painterly::embree ALIAS painterly_embree)
