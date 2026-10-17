/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* Triangle hits (SPEC §6): the material and the shading normal. Corner normals and the object's
 * normal matrix are read from the device scene (painterly/kernel/globals.h). Every function is a
 * pure function of its arguments. */

#include "painterly/kernel/globals.h"
#include "painterly/util/math_double3.h"

CCL_NAMESPACE_BEGIN

/* Material of a triangle hit: tri_material[mesh.tri_offset + prim] (globals.h). */
ccl_device_inline int painterly_triangle_material(PainterlyGlobals kg,
                                                  const PainterlyIntersection &isect)
{
  const KernelPainterlyMesh &mesh = kg->meshes[kg->objects[isect.index].mesh];
  return kg->tri_material[mesh.tri_offset + isect.prim];
}

/* Shading normal at a triangle hit, unit length, in world space (SPEC §6).
 *   With corner normals: n = (1 - u - v) n0 + u n1 + v n2 in object space, with the weights of the
 *   Embree convention (painterly/bvh/embree.h: p = (1 - u - v) v0 + u v1 + v v2). It is mapped to
 *   world space by the object's normal_to_world, the matrix that also maps isect.Ng (both come
 *   from painterly_normal_matrix), so the two routes agree on a flat triangle.
 *   Otherwise: the geometric normal isect.Ng, which the BVH returns in world space.
 * If two_sided, the normal is flipped to face the incoming ray: dot(N, ray.d) > 0 -> N = -N
 * (SPEC §6). The glass lobe calls this with two_sided = false, so it always gets the unflipped
 * normal. */
ccl_device_inline double3 painterly_triangle_shading_normal(PainterlyGlobals kg,
                                                            const PainterlyIntersection &isect,
                                                            const PainterlyRay &ray,
                                                            bool two_sided)
{
  const KernelPainterlyObject &object = kg->objects[isect.index];
  const KernelPainterlyMesh &mesh = kg->meshes[object.mesh];
  double3 N;
  if (mesh.has_corner_normals) {
    const float *n0 = kg->tri_corner_normals + PAINTERLY_TRIANGLE_CORNERS *
                                                   PAINTERLY_POINT_FLOATS *
                                                   (mesh.tri_offset + isect.prim);
    const float *n1 = n0 + PAINTERLY_POINT_FLOATS;
    const float *n2 = n1 + PAINTERLY_POINT_FLOATS;
    const double w1 = double(isect.u);
    const double w2 = double(isect.v);
    const double w0 = 1.0 - w1 - w2;
    const double3 n_object = make_double3(w0 * n0[0] + w1 * n1[0] + w2 * n2[0],
                                          w0 * n0[1] + w1 * n1[1] + w2 * n2[1],
                                          w0 * n0[2] + w1 * n1[2] + w2 * n2[2]);
    N = transform_direction_3x3(object.normal_to_world, n_object);
  }
  else {
    N = isect.Ng;
  }
  N = normalize(N);

  if (two_sided && dot(N, ray.d) > 0) {
    N = N * -1.0;
  }
  return N;
}

CCL_NAMESPACE_END
