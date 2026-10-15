# Scratch native-core render driver ("firstlight"). It lives only in this exported copy of the tree, never in the
# repository. It is added inside the PAINTERLY_BUILD_TESTS block of src/CMakeLists.txt, so it inherits the root's
# C++20 and -ffp-contract=off -fno-fast-math flags exactly like the painterly libraries and painterly_tests.

# The commit the source tree was exported from (git archive c69ee2e). The copy has no .git, so it is a cache value.
set(FIRSTLIGHT_SOURCE_COMMIT "c69ee2e8041513aeec613ecfae55aea22010840e" CACHE STRING
    "Commit the exported source tree came from, written to meta.json")

add_executable(painterly_render render.cpp)
# smallpaint_scene_fixture.h (the SPEC §9 reference scene as kernel data) lives with the doctest tests.
target_include_directories(painterly_render PRIVATE "${PROJECT_SOURCE_DIR}/src/test")
target_link_libraries(painterly_render PRIVATE painterly_integrator)
target_compile_definitions(painterly_render PRIVATE FIRSTLIGHT_SOURCE_COMMIT="${FIRSTLIGHT_SOURCE_COMMIT}")
