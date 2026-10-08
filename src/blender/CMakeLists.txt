# Development.SABIModule is required for nanobind's STABLE_ABI option: without it nanobind silently builds a non-stable-ABI module.
find_package(Python 3.12 REQUIRED COMPONENTS Interpreter Development.Module Development.SABIModule)

execute_process(
  COMMAND "${Python_EXECUTABLE}" -m nanobind --cmake_dir
  OUTPUT_STRIP_TRAILING_WHITESPACE OUTPUT_VARIABLE nanobind_ROOT)
find_package(nanobind CONFIG REQUIRED)

nanobind_add_module(_painterly STABLE_ABI NB_STATIC NB_DOMAIN painterly python.cpp)
target_compile_definitions(_painterly PRIVATE PAINTERLY_VERSION="${PROJECT_VERSION}")
install(TARGETS _painterly LIBRARY DESTINATION .)
