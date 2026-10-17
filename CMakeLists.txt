cmake_minimum_required(VERSION 3.28)
project(painterly VERSION 0.1.0 LANGUAGES C CXX)

# Painterly's build settings live in one place, cmake/painterly_embree_config.cmake: the C++ standard,
# position-independent code, the visibility presets, the MSVC runtime and the floating-point flags. The same file is
# what Embree gets, both through FetchContent (this configure) and in a prebuilt install (tools/embree_prebuilt.py
# passes it as CMAKE_PROJECT_INCLUDE). It must come after project(), because it sets CMAKE_MSVC_RUNTIME_LIBRARY and
# adds compile options.
include(${CMAKE_CURRENT_SOURCE_DIR}/cmake/painterly_embree_config.cmake)

option(PAINTERLY_BUILD_MODULE "Build the _painterly Python module" ON)
option(PAINTERLY_BUILD_TESTS "Build the doctest unit tests" ON)
option(PAINTERLY_BUILD_ORACLE "Build the smallpaint_oracle reference CLI" ON)

enable_testing()

list(APPEND CMAKE_MODULE_PATH ${PROJECT_SOURCE_DIR}/cmake)
include(painterly_warnings)
if(PAINTERLY_BUILD_MODULE OR PAINTERLY_BUILD_TESTS)
  include(painterly_embree)
endif()

add_subdirectory(src)
