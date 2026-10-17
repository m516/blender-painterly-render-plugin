include(FetchContent)

# Archive URLs are blocked in this container; FetchContent clones over git (see CLAUDE.md "Network notes").
# doctest is consumed header-only (TQ.1 F10). SOURCE_SUBDIR names a directory that doctest does not have, so
# FetchContent_MakeAvailable only populates the source and never runs doctest's CMakeLists.txt. That file declares
# cmake_minimum_required(VERSION 3.0) and a doctest_with_main library: CMake 3.28, the declared minimum, printed a
# CMake Deprecation Warning and a CMP0063 developer warning for them, and CMake >= 4.0 rejected the file unless
# CMAKE_POLICY_VERSION_MINIMUM was set.
FetchContent_Declare(
  doctest
  GIT_REPOSITORY https://github.com/doctest/doctest.git
  GIT_TAG v2.4.11
  GIT_SHALLOW TRUE
  SOURCE_SUBDIR painterly-header-only)
FetchContent_MakeAvailable(doctest)

# The header-only interface: the directory that holds doctest/doctest.h, as in doctest's own doctest::doctest. SYSTEM,
# so the warning flags of painterly_tests do not apply to doctest's header.
add_library(painterly_doctest INTERFACE)
target_include_directories(painterly_doctest SYSTEM INTERFACE "${doctest_SOURCE_DIR}")

add_executable(painterly_tests
  test_main.cpp
  test_util.cpp
  test_graph.cpp
  test_math_double3.cpp
  test_kernel_headers.cpp
  test_sampler.cpp
  test_analytic.cpp
  test_camera.cpp
  test_bounce.cpp
  test_bvh.cpp
  test_path.cpp
  test_path_trace.cpp
  smallpaint_camcr_ref.cpp)
target_link_libraries(painterly_tests PRIVATE
  painterly_doctest cycles_util cycles_graph painterly_kernel painterly_bvh painterly_integrator)
painterly_target_warnings(painterly_tests)
# test_analytic.cpp holds a byte-identical copy of smallpaint's Plane, whose normal(const Vec& p0) does not use p0
# (smallpaint_painterly.cpp:91). The copy stays verbatim, so the unused-parameter warning is off for this file only
# (TQ.1 F9). MSVC's /W4 reports it as C4100.
if(MSVC)
  set_source_files_properties(test_analytic.cpp PROPERTIES COMPILE_OPTIONS /wd4100)
else()
  set_source_files_properties(test_analytic.cpp PROPERTIES COMPILE_OPTIONS -Wno-unused-parameter)
endif()
add_test(NAME painterly_tests COMMAND painterly_tests)
