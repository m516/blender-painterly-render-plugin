# Vendored Cycles (T3.2): the util/ sources under third_party/cycles and the shims under src/cycles/shim,
# built as the static library cycles_util in namespace painterly. The source lists are explicit, so a
# vendored .cpp joins the build only when a card adds it here.

set(PAINTERLY_CYCLES_VENDOR "${PROJECT_SOURCE_DIR}/third_party/cycles")

# transform.cpp and boundbox.h stay out of M3: boundbox.h qualifies calls as ccl::min/max/clamp, which
# does not compile in namespace painterly (T3.2 card, "Vendored files").
add_library(cycles_util STATIC
  ${PAINTERLY_CYCLES_VENDOR}/util/aligned_malloc.cpp
  ${PAINTERLY_CYCLES_VENDOR}/util/guarded_allocator.cpp
  ${PAINTERLY_CYCLES_VENDOR}/util/transform_avx2.cpp
  shim/util/path.cpp
  shim/util/string.cpp
  shim/util/system.cpp
  shim/util/thread.cpp)

# Shims come first, so that they shadow upstream headers of the same relative path. src lets our code
# include painterly/...; the sse2neon directory provides <sse2neon.h> on arm64.
# The two vendored directories are SYSTEM (T3.22). Compilers report no warning from a SYSTEM header, so the warning
# flags of our own targets (cmake/painterly_warnings.cmake) report only our code: vendored Cycles is not -Wshadow clean.
# GCC and Clang search -isystem directories after -I directories, so the search order is src/cycles/shim, src,
# third_party/cycles, third_party/cycles/sse2neon. src/ and third_party/cycles/ share no top-level directory
# (tests/core/test_shims.py), so every include still resolves to the same file.
target_include_directories(cycles_util PUBLIC "${CMAKE_CURRENT_SOURCE_DIR}/shim")
target_include_directories(cycles_util SYSTEM PUBLIC "${PAINTERLY_CYCLES_VENDOR}" "${PAINTERLY_CYCLES_VENDOR}/sse2neon")
target_include_directories(cycles_util PUBLIC "${PROJECT_SOURCE_DIR}/src")

# Upstream's Cycles namespace is replaced for every painterly library that links cycles_util.
target_compile_definitions(cycles_util PUBLIC
  "CCL_NAMESPACE_BEGIN=namespace painterly {"
  "CCL_NAMESPACE_END=}")

# MSVC: util/guarded_allocator.h:108-134 (#ifdef _MSC_VER) names std::_Container_proxy and std::allocator, but the
# header includes only <cstddef>, <cstdlib> and <new>. Upstream compiles Cycles with WITH_BLENDER_GUARDEDALLOC
# (Blender v5.2.2 intern/cycles/CMakeLists.txt:382), so the header's MEM_guardedalloc.h include brings in <memory>
# (MEM_guardedalloc.h:297) first. We do not link Blender's guardedalloc, so <memory> is force-included instead. The
# option is PUBLIC because any consumer may include the header before <memory>. GCC and Clang never compile the block.
if(MSVC)
  target_compile_options(cycles_util PUBLIC /FImemory)
endif()

# Windows: <windows.h> (reached through util/windows.h, e.g. from util/thread.h) defines the macros min(a,b) and max(a,b)
# unless NOMINMAX is defined, which breaks Cycles' own min/max overloads (util/math_base.h) and every std::min/max call.
# Upstream defines NOMINMAX for every Windows source (Blender v5.2.2 build_files/cmake/platform/platform_win32.cmake:133-142).
# PUBLIC, because every consumer includes these headers.
if(WIN32)
  target_compile_definitions(cycles_util PUBLIC NOMINMAX)
endif()

# arm64: upstream's Blender root CMakeLists.txt:1564-1566 defines WITH_SSE2NEON, which lets util/optimization.h
# select the Neon code path.
if(CMAKE_SYSTEM_PROCESSOR MATCHES "^(arm64|ARM64|aarch64)$")
  target_compile_definitions(cycles_util PUBLIC WITH_SSE2NEON)
endif()

# x86-64: upstream's CYCLES_SSE42_FLAGS (intern/cycles/CMakeLists.txt:97) and CYCLES_AVX2_FLAGS (:82, :99).
# util/optimization.h defines __KERNEL_SSE42__ on x86-64, and GCC and Clang do not inline its SSE4.1 intrinsics
# without these flags. MSVC x64 needs no SSE flags. None of the flags enables FMA contraction for the
# SSE code, and -ffp-contract=off (root CMakeLists.txt) stays in force for every source.
if(CMAKE_SYSTEM_PROCESSOR MATCHES "^(x86_64|AMD64|amd64)$")
  if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
    target_compile_options(cycles_util PUBLIC -msse -msse2 -msse3 -mssse3 -msse4.1 -msse4.2)
    set(PAINTERLY_AVX2_FLAGS -msse -msse2 -msse3 -mssse3 -msse4.1 -msse4.2
        -mavx -mavx2 -mfma -mlzcnt -mbmi -mbmi2 -mf16c)
  elseif(MSVC)
    set(PAINTERLY_AVX2_FLAGS /arch:AVX2)
  endif()
  # Upstream's util/CMakeLists.txt:155-156: transform_avx2.cpp alone is compiled with the AVX2 flags.
  if(PAINTERLY_AVX2_FLAGS)
    set_property(SOURCE ${PAINTERLY_CYCLES_VENDOR}/util/transform_avx2.cpp
                 APPEND PROPERTY COMPILE_OPTIONS ${PAINTERLY_AVX2_FLAGS})
  endif()
endif()

# cycles_graph (T3.3): Cycles' node reflection (graph/node.cpp, graph/node_type.cpp) and its MD5 helper
# (util/md5.cpp), compiled unmodified. util/md5.cpp calls path_fopen from shim/util/path.cpp, so cycles_graph links
# cycles_util, and the static-library order follows from that link.
add_library(cycles_graph STATIC
  ${PAINTERLY_CYCLES_VENDOR}/graph/node.cpp
  ${PAINTERLY_CYCLES_VENDOR}/graph/node_type.cpp
  ${PAINTERLY_CYCLES_VENDOR}/util/md5.cpp)
target_link_libraries(cycles_graph PUBLIC cycles_util)

# Every node type's SOCKET_* macros call offsetof (graph/node_type.h), and a node derives from the polymorphic Node, so
# GCC reports -Winvalid-offsetof: the standard leaves offsetof conditionally supported for such types. Upstream relies on
# this for every node, and the code is vendored unmodified, so the warning is silenced for every consumer of cycles_graph.
if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  target_compile_options(cycles_graph PUBLIC -Wno-invalid-offsetof)
endif()

# T6.1: vendored Cycles kernel headers and the one kernel definition set. Every target whose sources include a kernel/
# header must link cycles_kernel, so that all its translation units compile one KernelData and ShaderData layout. Only
# the shim kernel/device/cpu/globals.h #errors without __MAX_CLOSURE__; kernel/types.h alone falls back to 64.
# __KERNEL_FEATURES__, WITH_EMBREE, WITH_OSL and WITH_PATH_GUIDING stay undefined (T6.1 "Definition set").
set(PAINTERLY_MAX_CLOSURE 64 CACHE STRING
    "Cycles __MAX_CLOSURE__, the closure slots per ShaderData; 64 is Cycles' value when it is undefined (kernel/types.h:829-830)")
if(NOT PAINTERLY_MAX_CLOSURE MATCHES "^[1-9][0-9]*$")
  message(FATAL_ERROR "PAINTERLY_MAX_CLOSURE must be a positive integer, got '${PAINTERLY_MAX_CLOSURE}'")
endif()
add_library(cycles_kernel INTERFACE)
target_link_libraries(cycles_kernel INTERFACE cycles_util)
target_compile_definitions(cycles_kernel INTERFACE __MAX_CLOSURE__=${PAINTERLY_MAX_CLOSURE})

# T6.1: every shim header is reached through its upstream path (shim_markers.cpp). An OBJECT library in ALL, so the
# wheel builds, which build no tests, compile it with MSVC, Clang and GCC.
add_library(cycles_shim_markers OBJECT shim_markers.cpp)
target_link_libraries(cycles_shim_markers PRIVATE cycles_kernel cycles_graph)

# T6.3: Cycles' SVM interpreter. tools/gen_svm_switch.py (T6.2) assembles svm_eval_nodes() from the verbatim fragments
# that src/cycles/svm_nodes.toml lists, into the build tree. cycles_svm is header-only: a consumer includes
# "svm_eval_nodes.h" and gets the kernel definition set through cycles_kernel. Every fragment change rewrites its sha256
# in VENDORED.toml, so these DEPENDS cover the fragments too.
find_package(Python 3.12 REQUIRED COMPONENTS Interpreter)
set(PAINTERLY_SVM_GENERATED_DIR ${CMAKE_CURRENT_BINARY_DIR}/generated)
add_custom_command(
  OUTPUT ${PAINTERLY_SVM_GENERATED_DIR}/svm_eval_nodes.h
  COMMAND ${Python_EXECUTABLE} -I ${PROJECT_SOURCE_DIR}/tools/gen_svm_switch.py
          --manifest ${CMAKE_CURRENT_SOURCE_DIR}/svm_nodes.toml
          --vendored ${PROJECT_SOURCE_DIR}/third_party/cycles/VENDORED.toml
          --output ${PAINTERLY_SVM_GENERATED_DIR}/svm_eval_nodes.h
  DEPENDS ${PROJECT_SOURCE_DIR}/tools/gen_svm_switch.py
          ${CMAKE_CURRENT_SOURCE_DIR}/svm_nodes.toml
          ${PROJECT_SOURCE_DIR}/third_party/cycles/VENDORED.toml
  COMMENT "Generating svm_eval_nodes.h with tools/gen_svm_switch.py"
  VERBATIM)
add_custom_target(cycles_svm_generate DEPENDS ${PAINTERLY_SVM_GENERATED_DIR}/svm_eval_nodes.h)
add_library(cycles_svm INTERFACE)
# Consumers build after the generator: CMake follows an INTERFACE library's dependencies transitively.
add_dependencies(cycles_svm cycles_svm_generate)
target_include_directories(cycles_svm INTERFACE ${PAINTERLY_SVM_GENERATED_DIR})
target_link_libraries(cycles_svm INTERFACE cycles_kernel)

# T6.3: the 22 SVM headers that T6.3 vendors compile verbatim with the kernel definition set (svm_headers_check.cpp). An
# OBJECT library in ALL, like cycles_shim_markers, so the wheel builds, which build no tests and never run the generator,
# compile them with MSVC, Clang and GCC.
add_library(cycles_svm_headers_check OBJECT svm_headers_check.cpp)
target_link_libraries(cycles_svm_headers_check PRIVATE cycles_kernel)

# T6.3: Blender compiles all of Cycles with -fno-strict-aliasing (v5.2.2 build_files/cmake/platform/
# platform_unix.cmake:898 for GCC, :970 for Clang; platform_apple.cmake:161; platform_win32.cmake:207 for clang-cl).
# svm_node_get<T> (kernel/svm/util.h:204-213) reads typed node structs through a reinterpret_cast of the uint byte code,
# and SVMCompiler writes them as int words (scene/svm.h:104). INTERFACE on cycles_kernel, so every target that compiles
# a kernel/ header gets it. MSVC does no type-based alias analysis. The flag changes no layout and no floating-point
# result.
if(NOT MSVC)
  target_compile_options(cycles_kernel INTERFACE -fno-strict-aliasing)
endif()

# T6.4: vendored shader graph, constant folding and the core shader nodes. tools/gen_fragment_units.py
# assembles one translation unit per fragmented upstream file (src/cycles/fragment_units.toml); the
# shader_nodes unit also defines the node type registry (shader_node_registry.h).
set(PAINTERLY_FRAGMENT_UNITS_DIR ${CMAKE_CURRENT_BINARY_DIR}/fragment_units)
set(PAINTERLY_FRAGMENT_UNIT_SOURCES)
foreach(unit shader_nodes svm)
  add_custom_command(
    OUTPUT ${PAINTERLY_FRAGMENT_UNITS_DIR}/${unit}.cpp
    COMMAND ${Python_EXECUTABLE} -I ${PROJECT_SOURCE_DIR}/tools/gen_fragment_units.py
            --manifest ${CMAKE_CURRENT_SOURCE_DIR}/fragment_units.toml
            --vendored ${PROJECT_SOURCE_DIR}/third_party/cycles/VENDORED.toml
            --unit ${unit}
            --output ${PAINTERLY_FRAGMENT_UNITS_DIR}/${unit}.cpp
    DEPENDS ${PROJECT_SOURCE_DIR}/tools/gen_fragment_units.py
            ${CMAKE_CURRENT_SOURCE_DIR}/fragment_units.toml
            ${PROJECT_SOURCE_DIR}/third_party/cycles/VENDORED.toml
    COMMENT "Generating Cycles fragment unit ${unit}.cpp"
    VERBATIM)
  list(APPEND PAINTERLY_FRAGMENT_UNIT_SOURCES ${PAINTERLY_FRAGMENT_UNITS_DIR}/${unit}.cpp)
endforeach()
add_library(cycles_scene STATIC
  ${PROJECT_SOURCE_DIR}/third_party/cycles/scene/constant_fold.cpp
  ${PROJECT_SOURCE_DIR}/third_party/cycles/scene/shader_graph.cpp
  shim/scene/attribute.cpp
  shim/scene/shader.cpp
  ${PAINTERLY_FRAGMENT_UNIT_SOURCES})
target_link_libraries(cycles_scene PUBLIC cycles_graph cycles_kernel)
# Opus decision (T6.4): upstream names its namespace through the CCL_NAMESPACE_* macros and, at
# scene/shader_nodes.h:992, through the bare token ccl. This maps the token to painterly too.
target_compile_definitions(cycles_scene PUBLIC ccl=painterly)

# T6.5: time_dt() of util/time.cpp, which SVMCompiler::compile (scene/svm.cpp:1184, 1229), util/time.h's scoped_timer and
# util/progress.h call. Card T6.5 takes this one function as a fragment, assembled into the generated unit "time"
# (src/cycles/fragment_units.toml) and compiled into cycles_scene; util/time.cpp is not vendored whole.
add_custom_command(
  OUTPUT ${PAINTERLY_FRAGMENT_UNITS_DIR}/time.cpp
  COMMAND ${Python_EXECUTABLE} -I ${PROJECT_SOURCE_DIR}/tools/gen_fragment_units.py
          --manifest ${CMAKE_CURRENT_SOURCE_DIR}/fragment_units.toml
          --vendored ${PROJECT_SOURCE_DIR}/third_party/cycles/VENDORED.toml
          --unit time
          --output ${PAINTERLY_FRAGMENT_UNITS_DIR}/time.cpp
  DEPENDS ${PROJECT_SOURCE_DIR}/tools/gen_fragment_units.py
          ${CMAKE_CURRENT_SOURCE_DIR}/fragment_units.toml
          ${PROJECT_SOURCE_DIR}/third_party/cycles/VENDORED.toml
  COMMENT "Generating Cycles fragment unit time.cpp"
  VERBATIM)
target_sources(cycles_scene PRIVATE ${PAINTERLY_FRAGMENT_UNITS_DIR}/time.cpp)

# T6.5: kernel/svm/closure.h and the kernel headers it reaches compile verbatim with the kernel definition set
# (svm_closure_headers_check.cpp). An OBJECT library in ALL, like cycles_svm_headers_check (T6.3), so the wheel builds,
# which build no tests, compile them with MSVC, Clang and GCC.
add_library(cycles_svm_closure_headers_check OBJECT svm_closure_headers_check.cpp)
target_link_libraries(cycles_svm_closure_headers_check PRIVATE cycles_kernel)

# T6.6: transform_transposed_inverse() of util/transform.cpp, which TextureMapping::compute_transform() calls. Card T3.2
# left util/transform.cpp unvendored; Opus decided (T6.6) to take this one function as a fragment, assembled into the
# generated unit "transform" (src/cycles/fragment_units.toml) and compiled into cycles_scene.
add_custom_command(
  OUTPUT ${PAINTERLY_FRAGMENT_UNITS_DIR}/transform.cpp
  COMMAND ${Python_EXECUTABLE} -I ${PROJECT_SOURCE_DIR}/tools/gen_fragment_units.py
          --manifest ${CMAKE_CURRENT_SOURCE_DIR}/fragment_units.toml
          --vendored ${PROJECT_SOURCE_DIR}/third_party/cycles/VENDORED.toml
          --unit transform
          --output ${PAINTERLY_FRAGMENT_UNITS_DIR}/transform.cpp
  DEPENDS ${PROJECT_SOURCE_DIR}/tools/gen_fragment_units.py
          ${CMAKE_CURRENT_SOURCE_DIR}/fragment_units.toml
          ${PROJECT_SOURCE_DIR}/third_party/cycles/VENDORED.toml
  COMMENT "Generating Cycles fragment unit transform.cpp"
  VERBATIM)
target_sources(cycles_scene PRIVATE ${PAINTERLY_FRAGMENT_UNITS_DIR}/transform.cpp)

# T6.7: LookupTables of scene/tables.cpp (the BSDF lookup tables), without device_update() and device_free(), which need a
# Device. Assembled from fragments into the generated unit "tables" (src/cycles/fragment_units.toml) and compiled into
# cycles_scene. The shim scene/shader.cpp, already a cycles_scene source, includes the vendored scene/shader.tables.
add_custom_command(
  OUTPUT ${PAINTERLY_FRAGMENT_UNITS_DIR}/tables.cpp
  COMMAND ${Python_EXECUTABLE} -I ${PROJECT_SOURCE_DIR}/tools/gen_fragment_units.py
          --manifest ${CMAKE_CURRENT_SOURCE_DIR}/fragment_units.toml
          --vendored ${PROJECT_SOURCE_DIR}/third_party/cycles/VENDORED.toml
          --unit tables
          --output ${PAINTERLY_FRAGMENT_UNITS_DIR}/tables.cpp
  DEPENDS ${PROJECT_SOURCE_DIR}/tools/gen_fragment_units.py
          ${CMAKE_CURRENT_SOURCE_DIR}/fragment_units.toml
          ${PROJECT_SOURCE_DIR}/third_party/cycles/VENDORED.toml
  COMMENT "Generating Cycles fragment unit tables.cpp"
  VERBATIM)
target_sources(cycles_scene PRIVATE ${PAINTERLY_FRAGMENT_UNITS_DIR}/tables.cpp)

# T6.8: the in-memory ImageManager of the shim scene/image.h (images given by the caller, conformed as Cycles conforms them,
# untiled, without OIIO, OCIO or the texture cache). The kernel image path is header-only, in cycles_svm.
target_sources(cycles_scene PRIVATE shim/scene/image.cpp)
