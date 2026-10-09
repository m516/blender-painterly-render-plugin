/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* Analytic primitives: ghost spheres (smallpaint's |d| = 1 quadratic), exact spheres (the correct
 * quadratic) and planes (SPEC §5, §9). Every function is a pure function of its arguments.
 *
 * The arithmetic keeps smallpaint's operand order and parenthesization, so the ghost and plane
 * results are bit-identical to smallpaint_painterly.cpp, and the exact sphere result is
 * bit-identical to the oracle's --ghost none hook (src/app/smallpaint_oracle.cpp). Never
 * "simplify" these expressions: a reordered sum or product changes the last bit.
 *
 * Literal 2 and 4 in the sphere code are the coefficients of the quadratic
 * t^2 + 2 (o - c).d t + |o - c|^2 - r^2 = 0 and of its discriminant b^2 - 4 a c. */

#include <cmath>

#include "painterly/kernel/globals.h"
#include "painterly/util/math_double3.h"

CCL_NAMESPACE_BEGIN

/* Returns smallpaint's t_sphere (smallpaint_painterly.cpp:100-109) for SPHERE_GHOST, or the exact
 * quadratic for SPHERE_EXACT (SPEC §5): (sol2 > eps) ? sol2/2 : ((sol1 > eps) ? sol1/2 : 0). The
 * near root sol2 = -b - sqrt(disc) is tried first, and the far root sol1 only when the undivided
 * near root is not beyond eps. Returns 0 on a miss. The caller accepts the hit iff the returned
 * t > eps (Scene::intersect, smallpaint_painterly.cpp:138), so a near root that passes the
 * undivided test but not the divided one is rejected without trying the far root (SPEC §5). */
ccl_device_inline double painterly_sphere_intersect(const KernelPainterlyAnalytic &sphere,
                                                    const PainterlyRay &ray,
                                                    double eps)
{
  const double3 o = ray.o;
  const double3 d = ray.d;
  const double3 c = sphere.a;
  const double r = sphere.b;

  if (sphere.intersection == SPHERE_EXACT) {
    /* SPEC §5 exact quadratic, expression for expression the oracle's intersect_exact. The
     * eps tests act on the undivided roots; the roots are then divided by 2a. */
    const double a = dot(d, d);
    const double b = dot((o - c) * 2, d);
    const double c_ = dot(o - c, o - c) - (r * r);
    double disc = b * b - 4 * a * c_;
    if (disc < 0) {
      return 0;
    }
    disc = std::sqrt(disc);
    const double sol1 = -b + disc;
    const double sol2 = -b - disc;
    return (sol2 > eps) ? sol2 / (2 * a) : ((sol1 > eps) ? sol1 / (2 * a) : 0);
  }

  /* Ghost: smallpaint_painterly.cpp:101-108. This quadratic assumes |d| = 1 (SPEC §5). Its roots
   * are halved, as in smallpaint. */
  const double b = dot((o - c) * 2, d);
  const double c_ = dot(o - c, o - c) - (r * r);
  double disc = b * b - 4 * c_;
  if (disc < 0) {
    return 0;
  }
  disc = std::sqrt(disc);
  const double sol1 = -b + disc;
  const double sol2 = -b - disc;
  return (sol2 > eps) ? sol2 / 2 : ((sol1 > eps) ? sol1 / 2 : 0);
}

/* Plane (SPEC §9, smallpaint_painterly.cpp:84-90): t = -1 * ((n.o + d) / (n.d)) when n.d != 0.
 * Returns t if t > eps, and 0 otherwise (including n.d == 0). The -1 is the sign of the root of
 * n.(o + t d) + d = 0. */
ccl_device_inline double painterly_plane_intersect(const KernelPainterlyAnalytic &plane,
                                                   const PainterlyRay &ray,
                                                   double eps)
{
  const double3 n = plane.a;
  const double d = plane.b;
  const double d0 = dot(n, ray.d);
  if (d0 != 0) {
    const double t = -1 * (((dot(n, ray.o)) + d) / d0);
    return (t > eps) ? t : 0;
  }
  return 0;
}

/* Dispatch on prim.type. Spheres take the sphere path, so a zero-initialized primitive is a ghost
 * sphere. The caller accepts the hit iff the returned t > eps. */
ccl_device_inline double painterly_analytic_intersect(const KernelPainterlyAnalytic &prim,
                                                      const PainterlyRay &ray,
                                                      double eps)
{
  if (prim.type == ANALYTIC_PLANE) {
    return painterly_plane_intersect(prim, ray, eps);
  }
  return painterly_sphere_intersect(prim, ray, eps);
}

/* SPEC §5, §9. Sphere: normalize(P - c) from the true centre (smallpaint_painterly.cpp:111-113),
 * shared by ghost and exact spheres. Plane: the unit normal n (smallpaint_painterly.cpp:91). */
ccl_device_inline double3 painterly_analytic_normal(const KernelPainterlyAnalytic &prim,
                                                    const double3 P)
{
  if (prim.type == ANALYTIC_PLANE) {
    return prim.a;
  }
  return normalize(P - prim.a);
}

CCL_NAMESPACE_END
