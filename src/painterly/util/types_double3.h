/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* CONTRACT: Opus-owned. Do not edit without an Opus card. */

#pragma once

/* Double-precision 3-vector for the painterly kernel.
 *
 * Cycles uses float3. The painterly kernel uses double3 so that analytic scenes reproduce
 * smallpaint_oracle bit for bit (SPEC §6 "Evaluation order"). Every operation below matches the
 * arithmetic of smallpaint's `Vec`
 * (third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp:42-54), operand order
 * included. Never "simplify" these into fused or reordered forms. */

#include "util/defines.h"

CCL_NAMESPACE_BEGIN

struct double3 {
  double x, y, z;
};

ccl_device_inline double3 make_double3(const double x, const double y, const double z)
{
  return {x, y, z};
}

ccl_device_inline double3 make_double3(const double v)
{
  return {v, v, v};
}

CCL_NAMESPACE_END
