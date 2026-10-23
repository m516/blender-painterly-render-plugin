/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* Build check for the SVM headers that card T6.3 vendors: each one compiles verbatim in
 * namespace painterly with cycles_kernel's definition set. It is an OBJECT library in ALL
 * (target cycles_svm_headers_check), so make build and every wheel build compile it with GCC,
 * Clang (macOS arm64, through sse2neon) and MSVC. The doctests compile these headers through the
 * generated svm_eval_nodes.h (target cycles_svm) only in builds with tests, and the wheel builds
 * have none. It defines nothing. */

#include "kernel/globals.h"

#include "kernel/svm/brightness.h"
#include "kernel/svm/clamp.h"
#include "kernel/svm/color_util.h"
#include "kernel/svm/convert.h"
#include "kernel/svm/gamma.h"
#include "kernel/svm/hsv.h"
#include "kernel/svm/invert.h"
#include "kernel/svm/map_range.h"
#include "kernel/svm/mapping.h"
#include "kernel/svm/mapping_util.h"
#include "kernel/svm/math.h"
#include "kernel/svm/math_util.h"
#include "kernel/svm/mix.h"
#include "kernel/svm/node_types.h"
#include "kernel/svm/ramp.h"
#include "kernel/svm/ramp_util.h"
#include "kernel/svm/sepcomb_color.h"
#include "kernel/svm/sepcomb_vector.h"
#include "kernel/svm/util.h"
#include "kernel/svm/value.h"
#include "kernel/tables.h"
#include "kernel/util/colorspace.h"
