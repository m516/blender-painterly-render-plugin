include(FetchContent)

# Archive URLs are blocked in this container; FetchContent clones over git (see CLAUDE.md "Network notes").
FetchContent_Declare(
  doctest
  GIT_REPOSITORY https://github.com/doctest/doctest.git
  GIT_TAG v2.4.11
  GIT_SHALLOW TRUE)
# doctest v2.4.11 declares cmake_minimum_required(VERSION 3.0), which CMake >= 4.0 rejects unless this policy minimum
# is set. It only affects how doctest's own CMake file is interpreted; doctest is consumed as a header-only library.
set(CMAKE_POLICY_VERSION_MINIMUM 3.10)
FetchContent_MakeAvailable(doctest)

add_executable(painterly_tests test_main.cpp)
target_link_libraries(painterly_tests PRIVATE doctest::doctest)
add_test(NAME painterly_tests COMMAND painterly_tests)
