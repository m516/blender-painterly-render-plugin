/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* The three bounces of the path: spiral diffuse (SPEC §4), mirror and Snell-only glass (SPEC §6).
 * Every function is a pure function of its arguments. The caller passes in the sequence counter K
 * (SPEC §2) and the indices of the stateless RNG, so nothing is stored between calls.
 *
 * The arithmetic keeps smallpaint's operand order and parenthesization (trace(),
 * smallpaint_painterly.cpp:189-239), so the results are bit-identical to the oracle. Never
 * "simplify" these expressions: a reordered sum or product changes the last bit. */

#include <cmath>
#include <cstdint>

#include "painterly/kernel/globals.h"
#include "painterly/kernel/sample/sampler.h"
#include "painterly/kernel/smallpaint.h"
#include "painterly/util/math_double3.h"

CCL_NAMESPACE_BEGIN

/* SPEC §4. ray->o is already the hit point. Advances *K by one, and the increment comes before the
 * draw (smallpaint_painterly.cpp:203-205). Writes the new unnormalized direction into ray->d and
 * returns cost = dot(d, N). The cost uses the unnormalized d (smallpaint_painterly.cpp:206). */
ccl_device_inline double painterly_diffuse_bounce(const KernelPainterlyIntegrator &p,
                                                  double3 N,
                                                  uint64_t *K,
                                                  int row,
                                                  int col,
                                                  int pass,
                                                  int depth,
                                                  PainterlyRay *ray)
{
  *K += 1;
  const double u1 = painterly_vdc(*K);
  /* Both spiral dimensions use u (SPEC §2), so u2 = u1 unless u2_mode is independent. */
  const double u2 = (p.u2_mode == U2_SAME) ?
                        u1 :
                        painterly_rng_unit(
                            p.seed, PURPOSE_U2, uint(depth), uint(row), uint(col), uint(pass));

  /* hemisphere() (smallpaint_painterly.cpp:183-187). The angle is 2 pi u2 (SPEC §4), with
   * smallpaint's PI. */
  const double r = std::sqrt(1.0 - u1 * u1);
  const double phi = 2 * SMALLPAINT_PI * u2;
  const double3 s = make_double3(std::cos(phi) * r, std::sin(phi) * r, u1);

  /* d = N + F s (smallpaint_painterly.cpp:205). The spiral is not rotated into N's frame
   * (SPEC §4). */
  double3 d = N + transform_direction_3x3(p.spiral_frame, s);
  /* Normalization blend (SPEC §4). For alpha = 0, pow(|d|, -0) = 1 exactly, so d is unchanged. */
  d = d * std::pow(len(d), -p.alpha);

  ray->d = d;
  return dot(d, N);
}

/* smallpaint_painterly.cpp:214-220 (SPEC §6). d <- normalize(d - N (2 cost)), with cost = dot(d,
 * N) and normalize as smallpaint's norm(). The factor 2 is the reflection coefficient. The origin
 * is unchanged. */
ccl_device_inline void painterly_mirror_bounce(double3 N, PainterlyRay *ray)
{
  const double cost = dot(ray->d, N);
  ray->d = normalize(ray->d - N * (cost * 2));
}

/* smallpaint_painterly.cpp:222-238 (SPEC §6). ior is the index of the medium (smallpaint's
 * refr_index). When dot(N, d) > 0 the ray leaves the medium: N is flipped and n is inverted. Then
 * n is inverted again, unconditionally. The two inversions are applied in this order, because 1 /
 * (1 / x) is not always x in float64. Returns false on total internal reflection: the path ends
 * and ray is unchanged. The incoming d may be unnormalized (SPEC §6). The caller passes the
 * unflipped normal, since the glass lobe is never two-sided (SPEC §6). */
ccl_device_inline bool painterly_glass_bounce(double3 N, double ior, PainterlyRay *ray)
{
  double n = ior;
  if (dot(N, ray->d) > 0) {
    N = N * -1.0;
    n = 1.0 / n;
  }
  n = 1.0 / n;

  const double cost1 = dot(N, ray->d) * -1.0;
  const double cost2 = 1.0 - n * n * (1.0 - cost1 * cost1);
  if (cost2 > 0) {
    ray->d = (ray->d * n) + (N * (n * cost1 - std::sqrt(cost2)));
    ray->d = normalize(ray->d);
    return true;
  }
  return false;
}

CCL_NAMESPACE_END
