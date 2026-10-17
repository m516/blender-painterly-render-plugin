# SPDX-License-Identifier: GPL-3.0-or-later
#
# The one source of truth for how Embree 4.4.1 is compiled for painterly. It holds two things:
#   - the painterly project settings that reach Embree through FetchContent: the C++ standard, position-independent
#     code, the visibility presets, the MSVC runtime and the floating-point flags;
#   - every EMBREE_* cache option, including the ISA knob PAINTERLY_EMBREE_MAX_ISA.
# Its three callers are the three places that decide Embree's build:
#   - the root CMakeLists.txt includes it, so the same settings also apply to painterly's own targets (they always
#     did; they live here now so that no second copy can drift);
#   - cmake/painterly_embree.cmake includes it before FetchContent_MakeAvailable(embree), the FetchContent path;
#   - tools/embree_prebuilt.py build passes it to Embree's own configure as -DCMAKE_PROJECT_INCLUDE=<this file>, the
#     prebuilt path, so a prebuilt install is compiled with exactly these settings.
# The guard matters: the root CMakeLists.txt and painterly_embree.cmake both include this file in one CMake run, and
# the floating-point flags below must be added once, or the two paths' command lines would differ.
include_guard(GLOBAL)

# --- Painterly's own settings, inherited by Embree through FetchContent ------------------------------

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_CXX_VISIBILITY_PRESET hidden)
set(CMAKE_VISIBILITY_INLINES_HIDDEN ON)

# static CRT: never bind to Blender's MSVC runtime
set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")
# CMP0091 must be NEW for CMAKE_MSVC_RUNTIME_LIBRARY to reach the targets. painterly gets that from its
# cmake_minimum_required(3.28); Embree's CMakeLists.txt declares 3.10, so the prebuilt configure needs it here.
if(POLICY CMP0091)
  cmake_policy(SET CMP0091 NEW)
endif()

# Bit-identical oracle parity requires no FMA contraction (docs/architecture.md, "Determinism contract").
# add_compile_options and not CMAKE_CXX_FLAGS: Embree's common/cmake/gnu.cmake empties CMAKE_CXX_FLAGS
# (EMBREE_IGNORE_CMAKE_CXX_FLAGS, embree CMakeLists.txt:83), which would drop the flags from the prebuilt build.
if(MSVC)
  add_compile_options(/fp:precise)
else()
  add_compile_options(-ffp-contract=off -fno-fast-math)
endif()

# --- Embree's own cache options ----------------------------------------------------------------------

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
