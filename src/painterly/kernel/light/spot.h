/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* Blender's spot cone falloff for a ghost sphere made from a spot light (SPEC §5). The function is
 * a pure function of its arguments. */

#include "painterly/kernel/types.h"
#include "painterly/util/math_double3.h"

CCL_NAMESPACE_BEGIN

/* Cubic smoothstep, clamped to [0, 1]: 3 f^2 - 2 f^3 is the Hermite cubic with zero slope at both
 * ends. This is Cycles' smoothstepf (third_party/cycles/util/math_base.h:499-509), evaluated in
 * double. The 0 and 1 are the clamp bounds, and the 3 and 2 are the coefficients of the cubic. */
ccl_device_inline double painterly_smoothstep(const double f)
{
  if (f <= 0.0) {
    return 0.0;
  }
  if (f >= 1.0) {
    return 1.0;
  }
  const double ff = f * f;
  return 3.0 * ff - 2.0 * ff * f;
}

/* SPEC §5: the cone falloff at direction `dir` (unit, from the true centre towards the hit point).
 * Returns 1 when !spot.enabled. Otherwise it is smoothstep(f) with
 * f = (dot(dir, spot.direction) - cos_half_angle) / ((1 - cos_half_angle) * blend), which is 0 at
 * the cone edge and 1 where the blend region ends (Cycles v5.2.2 kernel/light/spot.h:28-31 and
 * scene/light.cpp:177-178). blend == 0 is a hard edge, where f would divide by zero: the result is
 * 1 iff dot > cos_half_angle. */
ccl_device_inline double painterly_spot_attenuation(const KernelPainterlySpotProfile &spot,
                                                    const double3 dir)
{
  if (!spot.enabled) {
    return 1.0;
  }
  const double cos_angle = dot(dir, spot.direction);
  if (spot.blend == 0.0) {
    return (cos_angle > spot.cos_half_angle) ? 1.0 : 0.0;
  }
  const double f = (cos_angle - spot.cos_half_angle) / ((1.0 - spot.cos_half_angle) * spot.blend);
  return painterly_smoothstep(f);
}

CCL_NAMESPACE_END
