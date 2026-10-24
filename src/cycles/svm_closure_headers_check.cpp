/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* Build check for the closure evaluators that card T6.5 vendors: kernel/svm/closure.h and the
 * 42 other kernel headers it reaches compile verbatim in namespace painterly with cycles_kernel's
 * definition set. It is an OBJECT library in ALL (target cycles_svm_closure_headers_check), so
 * make build and every wheel build compile it with GCC, Clang (macOS arm64, through sse2neon) and
 * MSVC. The doctests compile these headers through the generated svm_eval_nodes.h (target
 * cycles_svm) only in builds with tests, and the wheel builds have none. It defines nothing. */

#include "kernel/globals.h"

#include "kernel/svm/closure.h"
