/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* The painterly path (SPEC §6): one sample of one pixel. The forward walk records one vertex per
 * hit, and the backward evaluation visits the vertices in reverse. This replaces smallpaint's
 * recursion trace() (smallpaint_painterly.cpp:189-239) with the same operations in the same order,
 * so the result is bit-identical to the recursion (SPEC §6 "Evaluation order").
 *
 * The caller owns the sequence counter K (SPEC §2) and the scratch array. Every function is a pure
 * function of its arguments, apart from *K and scratch. */

#include <cstdint>

#include "painterly/kernel/bvh/bvh.h"
#include "painterly/kernel/camera/camera.h"
#include "painterly/kernel/closure/bounce.h"
#include "painterly/kernel/closure/lobe.h"
#include "painterly/kernel/geom/analytic.h"
#include "painterly/kernel/geom/triangle.h"
#include "painterly/kernel/globals.h"
#include "painterly/kernel/light/background.h"
#include "painterly/kernel/light/spot.h"
#include "painterly/kernel/types.h"
#include "painterly/util/math_double3.h"

CCL_NAMESPACE_BEGIN

/* What a recorded vertex contributes to the backward evaluation (SPEC §6). */
enum PainterlyPathVertexKind : int {
  VERTEX_DIFFUSE = 0, /* Spiral diffuse bounce: Li = Li + cost * (L * color) * diffuse_gain. */
  VERTEX_TINT = 1,    /* Tint (mirror, glass, transparent): Li = Li + L * color. */
  VERTEX_END = 2,     /* The path ends here: Li = emission_term. */
};

/* One recorded hit. emission_term is 0.0 + (E * emission_gain) per channel, where E is the
 * emission of the hit, or the background on a miss (SPEC §6). cost and color are read by
 * VERTEX_DIFFUSE and VERTEX_TINT. */
struct PainterlyPathVertex {
  int kind; /* PainterlyPathVertexKind */
  double3 emission_term;
  double cost;
  double3 color;
};

/* 0.0 + (E * gain) per channel, the form of smallpaint_painterly.cpp:200 (clr + emission * 2). The
 * 0.0 + turns a -0.0 into +0.0, as smallpaint's sum does. */
ccl_device_inline double3 painterly_emission_term(const double3 E, const double gain)
{
  return make_double3(0.0 + (E.x * gain), 0.0 + (E.y * gain), 0.0 + (E.z * gain));
}

/* SPEC §6: the emitter test, emission.x > 0 || emission.y > 0 || emission.z > 0. */
ccl_device_inline bool painterly_is_emitter(const double3 E)
{
  return E.x > 0 || E.y > 0 || E.z > 0;
}

/* One painterly path for pixel (row, col) of `pass`, continuing the sequence counter *K (SPEC §2,
 * §6). scratch holds at least max_depth vertices: a path records at most one vertex per depth.
 * Returns the radiance and the number of K draws consumed, which equals the number of
 * VERTEX_DIFFUSE vertices recorded. */
ccl_device PainterlyPathResult painterly_trace_pixel(
    PainterlyGlobals kg, int row, int col, int pass, uint64_t *K, PainterlyPathVertex *scratch)
{
  const KernelPainterlyIntegrator &p = kg->data->integrator;
  const uint64_t K_start = *K;
  const double3 zero = make_double3(0.0);
  PainterlyRay ray = painterly_camera_generate_ray(kg, row, col, pass, true);
  int n = 0;

  /* Forward walk. depth >= max_depth returns 0 before intersecting (SPEC §6;
   * smallpaint_painterly.cpp:190), so the loop bound is max_depth. */
  for (int depth = 0; depth < p.max_depth; depth++) {
    PainterlyIntersection isect;
    if (!painterly_scene_intersect(kg, ray, &isect)) {
      /* A miss: the background, scaled by emission_gain (SPEC §6). */
      const double3 background = painterly_background_radiance(kg, ray.d);
      scratch[n++] = PainterlyPathVertex{
          VERTEX_END, painterly_emission_term(background, p.emission_gain), 0.0, zero};
      break;
    }

    const bool triangle = isect.kind == HIT_TRIANGLE;
    const KernelPainterlyAnalytic *prim = triangle ? nullptr : &kg->analytic[isect.index];
    const double3 P = ray.o + ray.d * isect.t;
    /* Triangles use the normal flipped to face the ray when two_sided (SPEC §6). Analytic
     * primitives keep smallpaint's normals. */
    const double3 N = triangle ?
                          painterly_triangle_shading_normal(kg, isect, ray, p.two_sided != 0) :
                          painterly_analytic_normal(*prim, P);
    ray.o = P;

    const int material_index = triangle ? painterly_triangle_material(kg, isect) : prim->material;
    const KernelPainterlyMaterial &mat = kg->materials[material_index];

    /* Emission. A spot ghost sphere scales it by the cone falloff at its normal (SPEC §5). */
    double3 E = mat.emission;
    if (prim != nullptr && prim->spot.enabled) {
      E = E * painterly_spot_attenuation(prim->spot, N);
    }
    const double3 e_term = painterly_emission_term(E, p.emission_gain);

    if (!p.continue_after_emitter && painterly_is_emitter(mat.emission)) {
      /* The emitter absorbs the path (SPEC §6, knob continue_after_emitter). */
      scratch[n++] = PainterlyPathVertex{VERTEX_END, e_term, 0.0, zero};
      break;
    }

    const KernelPainterlyLobe lobe = painterly_select_lobe(kg, mat, row, col, pass, depth);
    bool path_ends = false;
    switch (lobe.kind) {
      case LOBE_DIFFUSE: {
        /* Spiral diffuse (SPEC §4). This is the only vertex that draws from K. */
        const double cost = painterly_diffuse_bounce(p, N, K, row, col, pass, depth, &ray);
        scratch[n++] = PainterlyPathVertex{VERTEX_DIFFUSE, e_term, cost, lobe.weight};
        break;
      }
      case LOBE_MIRROR:
        painterly_mirror_bounce(N, &ray);
        scratch[n++] = PainterlyPathVertex{VERTEX_TINT, e_term, 0.0, lobe.weight};
        break;
      case LOBE_GLASS: {
        /* The glass lobe always gets the unflipped normal (SPEC §6). */
        const double3 N_glass = triangle ?
                                    painterly_triangle_shading_normal(kg, isect, ray, false) :
                                    N;
        if (painterly_glass_bounce(N_glass, lobe.ior, &ray)) {
          scratch[n++] = PainterlyPathVertex{VERTEX_TINT, e_term, 0.0, lobe.weight};
        }
        else {
          /* Total internal reflection: the path ends with its emission (SPEC §6). */
          scratch[n++] = PainterlyPathVertex{VERTEX_END, e_term, 0.0, zero};
          path_ends = true;
        }
        break;
      }
      case LOBE_TRANSPARENT:
        /* Straight continuation: ray.d is unchanged (SPEC §6). */
        scratch[n++] = PainterlyPathVertex{VERTEX_TINT, e_term, 0.0, lobe.weight};
        break;
    }
    if (path_ends) {
      break;
    }
  }

  /* Backward evaluation (SPEC §6), last vertex first. Each operation matches smallpaint's order:
   * the diffuse term is cost * (L * color) * diffuse_gain (smallpaint_painterly.cpp:209-211), and
   * the tint adds L * color (:219, :236). */
  double3 L = zero;
  for (int i = n - 1; i >= 0; i--) {
    const PainterlyPathVertex &v = scratch[i];
    double3 Li = v.emission_term;
    if (v.kind == VERTEX_DIFFUSE) {
      Li.x = Li.x + v.cost * (L.x * v.color.x) * p.diffuse_gain;
      Li.y = Li.y + v.cost * (L.y * v.color.y) * p.diffuse_gain;
      Li.z = Li.z + v.cost * (L.z * v.color.z) * p.diffuse_gain;
    }
    else if (v.kind == VERTEX_TINT) {
      Li.x = Li.x + L.x * v.color.x;
      Li.y = Li.y + L.y * v.color.y;
      Li.z = Li.z + L.z * v.color.z;
    }
    L = Li;
  }

  return PainterlyPathResult{L, *K - K_start};
}

/* Object id of the unjittered primary hit, or -1 on a miss (SPEC §9 object ids; the object_id
 * buffer). The unjittered ray does not depend on the pass, so pass 0 is used. */
ccl_device int painterly_primary_object_id(PainterlyGlobals kg, int row, int col)
{
  const PainterlyRay ray = painterly_camera_generate_ray(kg, row, col, 0, false);
  PainterlyIntersection isect;
  if (!painterly_scene_intersect(kg, ray, &isect)) {
    return -1;
  }
  if (isect.kind == HIT_TRIANGLE) {
    return kg->objects[isect.index].object_id;
  }
  return kg->analytic[isect.index].object_id;
}

CCL_NAMESPACE_END
