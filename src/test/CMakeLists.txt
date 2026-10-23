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
# doctest prints the operands of a CHECK with operator<<. Without this definition doctest forward-declares
# std::ostream in namespace std (doctest.h v2.4.11 lines 517-552) and MSVC then fails on a std::string_view
# operand: CI run 39016333578 (commit 6806293), job windows, error C2027 in MSVC's <__msvc_string_view.hpp>
# from src/test/test_graph.cpp:180 CHECK(mode == std::string_view("mode")). GCC with libstdc++ compiles it.
# DOCTEST_CONFIG_USE_STD_HEADERS makes doctest include <cstddef>, <ostream> and <istream> instead
# (doctest.h lines 508-516; doc/markdown/configuration.md, section "DOCTEST_CONFIG_USE_STD_HEADERS", which
# says it "should be defined globally"). INTERFACE reaches every source of every target that links
# painterly_doctest, which is what "globally" asks for.
target_compile_definitions(painterly_doctest INTERFACE DOCTEST_CONFIG_USE_STD_HEADERS)

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
  test_scene.cpp
  test_session.cpp
  smallpaint_camcr_ref.cpp)
target_link_libraries(painterly_tests PRIVATE
  painterly_doctest cycles_util cycles_graph painterly_kernel painterly_bvh painterly_integrator
  painterly_scene painterly_session)
painterly_target_warnings(painterly_tests)

# The -ffp-contract=off canary of test_math_double3.cpp must be able to fail (TQ.2 F1). GCC and Clang contract a
# product into the addition that uses it only when the target has an FMA instruction (GCC: -ffp-contract=fast, its
# default for C++, and Clang: -ffp-contract=on), and the rest of painterly_tests is compiled with at most -msse4.2
# (src/cycles/CMakeLists.txt:63), which has none. So this one source alone is compiled with an FMA instruction set,
# and -ffp-contract=off (cmake/painterly_embree_config.cmake) is then the only thing that keeps dot() uncontracted.
# -mfma implies AVX and SSE4.2 on x86-64, and the source is an ordinary host test with no SIMD requirement of its own.
# MSVC needs no flag: /fp:precise already forbids contraction, and there is no per-source /arch switch to pair with it.
# No other source gets an FMA flag, so no other test's arithmetic can change.
if(CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|AMD64|amd64)$" AND CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  set_source_files_properties(test_math_double3.cpp PROPERTIES COMPILE_OPTIONS "-mfma")
endif()

add_test(NAME painterly_tests COMMAND painterly_tests)

# T6.1: Cycles kernel types. The layout probe is its own library, so the layout test compares two targets that each get
# the definition set only through their own link to cycles_kernel.
option(PAINTERLY_TEST_LAYOUT_SKEW
       "Test only: compile the kernel layout probe with __KERNEL_FEATURES__=0, so the kernel layout test must fail" OFF)
add_library(painterly_test_kernel_layout_probe STATIC cycles_kernel_layout_probe.cpp)
target_link_libraries(painterly_test_kernel_layout_probe PRIVATE cycles_kernel)
if(PAINTERLY_TEST_LAYOUT_SKEW)
  target_compile_definitions(painterly_test_kernel_layout_probe PRIVATE __KERNEL_FEATURES__=0)
endif()
target_sources(painterly_tests PRIVATE test_cycles_kernel_layout.cpp test_cycles_kernel_types.cpp)
target_link_libraries(painterly_tests PRIVATE cycles_kernel painterly_test_kernel_layout_probe)
