/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* Triangle hits (SPEC §6): the material and the shading normal. Corner normals and the object's
 * transform are read from the device scene (painterly/kernel/globals.h). Every function is a pure
 * function of its arguments. */

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
 *   world space by the inverse transpose of the object's transform, which is the transpose of the
 *   3x3 part of itfm, computed in double.
 *   Otherwise: the geometric normal isect.Ng, which Embree returns in world space.
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
    const float *c = kg->tri_corner_normals + 9 * (mesh.tri_offset + isect.prim);
    const double w1 = double(isect.u);
    const double w2 = double(isect.v);
    const double w0 = 1.0 - w1 - w2;
    const double3 n_object = make_double3(w0 * c[0] + w1 * c[3] + w2 * c[6],
                                          w0 * c[1] + w1 * c[4] + w2 * c[7],
                                          w0 * c[2] + w1 * c[5] + w2 * c[8]);
    /* Column i of the inverse transpose: itfm[4 j + i] for row j (row-major 3x4 affine). */
    const float *m = object.itfm;
    N = make_double3(
        double(m[0]) * n_object.x + double(m[4]) * n_object.y + double(m[8]) * n_object.z,
        double(m[1]) * n_object.x + double(m[5]) * n_object.y + double(m[9]) * n_object.z,
        double(m[2]) * n_object.x + double(m[6]) * n_object.y + double(m[10]) * n_object.z);
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
