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
function(painterly_target_warnings target)
  if(MSVC)
    target_compile_options(${target} PRIVATE /W4)
  else()
    target_compile_options(${target} PRIVATE -Wall -Wextra -Wshadow)
  endif()
endfunction()
