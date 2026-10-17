# SPDX-License-Identifier: GPL-3.0-or-later
#
# Compiler warnings for the project's own targets (TQ.1 F9, M3 review panel #6).
#
# painterly_target_warnings(<target>) adds the warning flags to the target's own sources. They are PRIVATE, so they never
# reach a consumer. The callers are painterly_util, painterly_bvh, painterly_integrator, painterly_tests and _painterly,
# and every later painterly_* library calls it too. The vendored Cycles libraries (cycles_*), Embree, doctest, nanobind
# and the oracle (smallpaint_oracle) never call it. Their headers reach our sources through SYSTEM include directories,
# and compilers report no warning from those, so the flags report our code only.
#
# -Wshadow: vendored Cycles and our code share namespace painterly (docs/architecture.md, "Source layout and naming"), so
# a local named like a vendored namespace-scope variable (True, False, zero, one, neg_inf, inf, pos_inf, step;
# util/simd.h:67-126) silently hides it. MSVC: /W4 is the counterpart of -Wall -Wextra, and its level 4 includes the
# declaration-hides warnings C4456-C4459.
#
# /W4 /wd4702: C4702 ("unreachable code") is the one report that comes from vendored code rather than ours, so it
# cannot be fixed here. third_party/cycles/util/transform.h(526) is reported in the translation unit of
# src/test/test_util.cpp: with __KERNEL_SSE42__, transform_inverse_dot (lines 518-527) returns inside its #if block,
# so the portable `return dot(a_, b_);` after it is unreachable. The vendored file is never edited (CLAUDE.md rule 1),
# and C4702 comes from the compiler's code generator, not from the source. Microsoft's /external documentation, section
# "Limitations": "Some warnings emitted by the compiler's back-end code generation aren't affected by the /external
# options. These warnings usually start with C47XX, though not all C47XX warnings are back-end warnings. You can still
# disable these warnings individually by using /wd47XX." GCC's and Clang's -Wall -Wextra contain no unreachable-code
# warning either, so /W4 /wd4702 and -Wall -Wextra -Wshadow stay comparable.
function(painterly_target_warnings target)
  if(MSVC)
    target_compile_options(${target} PRIVATE /W4 /wd4702)
  else()
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wshadow)
  endif()
endfunction()
