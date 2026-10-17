# painterly_kernel: the header-only kernel as an INTERFACE target, so that its link dependencies are explicit (TQ.1 F13).
# The kernel headers include vendored Cycles util headers (cycles_util), and painterly/kernel/bvh/bvh.h calls
# painterly/bvh/embree.h (painterly_bvh), the one allowed exception to the dependency direction (docs/architecture.md).
# Every target whose code includes painterly/kernel/ links painterly_kernel. painterly_bvh itself includes
# painterly/kernel/globals.h (the hit record) and does not link painterly_kernel, which would be a cycle. An INTERFACE
# target has no sources, so it takes no warning flags.
add_library(painterly_kernel INTERFACE)
target_link_libraries(painterly_kernel INTERFACE painterly_bvh cycles_util)
