/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* Closest hit of a path ray over the whole scene (SPEC §4, §5, §6): the triangles through the
 * Embree BVH, then the analytic primitives. Calling painterly/bvh/embree.h from the kernel is the
 * one allowed exception to the dependency direction (docs/architecture.md), as Cycles'
 * kernel/device/cpu/bvh.h calls Embree. */

#include <limits>

#include "painterly/bvh/embree.h"
#include "painterly/kernel/geom/analytic.h"
#include "painterly/kernel/globals.h"

CCL_NAMESPACE_BEGIN

/* Closest hit over triangles (Embree, tnear = ray_epsilon), then the analytic primitives in list
 * order with smallpaint's acceptance t > eps && t < best.t (smallpaint_painterly.cpp:136-141). A
 * tie resolves to the earlier primitive, and a triangle beats an analytic primitive at equal t.
 * The initial best.t is +infinity. smallpaint uses inf = 1e9 (smallpaint_painterly.cpp:38). No
 * reference ray reaches 1e9, so the two agree on every reference scene. Returns false on a miss,
 * with isect reset to HIT_NONE. */
ccl_device_inline bool painterly_scene_intersect(PainterlyGlobals kg,
                                                 const PainterlyRay &ray,
                                                 PainterlyIntersection *isect)
{
  const double eps = kg->data->integrator.ray_epsilon;
  const double infinity = std::numeric_limits<double>::infinity();
  *isect = PainterlyIntersection{};
  double best_t = infinity;

  if (kg->bvh) {
    PainterlyIntersection triangle;
    if (painterly_embree_intersect_closest(kg->bvh, ray, eps, infinity, &triangle)) {
      *isect = triangle;
      best_t = triangle.t;
    }
  }

  for (int i = 0; i < kg->num_analytic; i++) {
    const double t = painterly_analytic_intersect(kg->analytic[i], ray, eps);
    if (t > eps && t < best_t) {
      best_t = t;
      isect->t = t;
      isect->kind = HIT_ANALYTIC;
      isect->index = i;
    }
  }

  return isect->kind != HIT_NONE;
}

CCL_NAMESPACE_END
