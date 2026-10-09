/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* smallpaint's constants, shared by the kernel headers. Each one names the line of
 * third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp it comes from. */

#include "util/defines.h"

CCL_NAMESPACE_BEGIN

/* smallpaint's PI macro (smallpaint_painterly.cpp:33). It is NOT M_PI: it is needed for
 * bit-identical parity. */
constexpr double SMALLPAINT_PI = 3.1415926536;

CCL_NAMESPACE_END
