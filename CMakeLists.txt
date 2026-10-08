cmake_minimum_required(VERSION 3.26)
project(painterly VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_CXX_VISIBILITY_PRESET hidden)
set(CMAKE_VISIBILITY_INLINES_HIDDEN ON)

option(PAINTERLY_BUILD_MODULE "Build the _painterly Python module" ON)
option(PAINTERLY_BUILD_TESTS "Build the doctest unit tests" ON)
option(PAINTERLY_BUILD_ORACLE "Build the smallpaint_oracle reference CLI" ON)

# SPEC §6: bit-identical oracle parity requires no FMA contraction
if(MSVC)
  add_compile_options(/fp:precise)
else()
  add_compile_options(-ffp-contract=off -fno-fast-math)
endif()

enable_testing()
add_subdirectory(src)
