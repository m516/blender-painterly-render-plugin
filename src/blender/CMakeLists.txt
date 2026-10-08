# Development.SABIModule is required for nanobind's STABLE_ABI option: without it nanobind silently builds a non-stable-ABI module.
find_package(Python 3.12 REQUIRED COMPONENTS Interpreter Development.Module Development.SABIModule)

execute_process(
  COMMAND "${Python_EXECUTABLE}" -m nanobind --cmake_dir
  OUTPUT_STRIP_TRAILING_WHITESPACE OUTPUT_VARIABLE nanobind_ROOT)
find_package(nanobind CONFIG REQUIRED)

# NOMINSIZE: without it nanobind adds -Os to the module target, which would slow the kernel code compiled into it.
nanobind_add_module(_painterly STABLE_ABI NB_STATIC NB_DOMAIN painterly NOMINSIZE python.cpp selftest.cpp)
target_compile_definitions(_painterly PRIVATE PAINTERLY_VERSION="${PROJECT_VERSION}")
target_link_libraries(_painterly PRIVATE painterly::embree)

# Only PyInit__painterly is exported. Hidden visibility (root CMakeLists) covers everything else.
if(CMAKE_SYSTEM_NAME STREQUAL "Linux")
  # Embree's vtables reference __cxa_pure_virtual only weakly, so the static libstdc++ member would not be linked and the
  # weak import would bind to the host process's libstdc++. A strong reference links our own copy (made local by --exclude-libs).
  target_link_options(_painterly PRIVATE
    -static-libstdc++ -static-libgcc
    -Wl,--exclude-libs,ALL
    -Wl,-u,__cxa_pure_virtual
    -Wl,--version-script=${CMAKE_CURRENT_SOURCE_DIR}/exports.map)
elseif(APPLE)
  target_link_options(_painterly PRIVATE
    -Wl,-exported_symbols_list,${CMAKE_CURRENT_SOURCE_DIR}/exports_macos.txt)
endif()
# Windows: nanobind already exports only PyInit, so no .def file is needed.

install(TARGETS _painterly LIBRARY DESTINATION .)
