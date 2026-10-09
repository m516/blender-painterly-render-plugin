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
target_include_directories(cycles_util PUBLIC
  "${CMAKE_CURRENT_SOURCE_DIR}/shim"
  "${PAINTERLY_CYCLES_VENDOR}"
  "${PAINTERLY_CYCLES_VENDOR}/sse2neon"
  "${PROJECT_SOURCE_DIR}/src")

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
