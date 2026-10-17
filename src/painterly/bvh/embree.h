/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* Triangle BVH over instanced meshes, built on Embree 4 (T3.10). The convention is SPEC §4 and §5
 * (unnormalized rays: t is parametric along ray.d). The hit record is PainterlyIntersection
 * (painterly/kernel/globals.h). Embree stays out of this header: only embree.cpp includes it.
 *
 * Structure. One RTCScene per mesh holds one triangle geometry. A top-level scene holds one
 * instance per object, with the object's transform. A hit reports the object index (the position
 * of the object in the objects array), the triangle within its mesh, and the barycentrics of
 * Embree's convention: p = (1 - u - v) v0 + u v1 + v v2.
 *
 * Normals. Embree returns the geometric normal of an instance hit in object space: (v1 - v0) x
 * (v2 - v0) for the corners in index order (Embree 4.4.1
 * kernels/geometry/triangle_intersector_pluecker.h:87-89 and 105, common/math/vec3.h:210-222), so
 * it points to the side from which v0, v1, v2 appear counter-clockwise. Ng is returned in world
 * space, mapped by the object's normal matrix from painterly_normal_matrix
 * (painterly/util/math_double3.h), which the scene also stores as
 * KernelPainterlyObject::normal_to_world, and it is not normalized. Normals keep their side of the
 * surface: n_world . (A d) = n_object . d for every direction d, so an outward normal stays
 * outward under a mirroring transform.
 *
 * Watertightness. Every RTCScene has RTC_SCENE_FLAG_ROBUST: a ray through an edge shared by two
 * triangles hits one of them. T3.17 and T5.4 compare object ids on interior pixels, so this
 * matters there.
 *
 * Determinism scope. On one machine and one ISA, Embree's triangle hits are deterministic. They
 * are not identical across ISAs: Embree's AVX2 kernels use explicit FMA, which -ffp-contract=off
 * cannot affect. M2's selftest gave t = 0.49999997 for an exact 0.5. Bit-parity with
 * smallpaint_oracle is therefore defined on analytic scenes only (T3.16). Triangle scenes are
 * checked statistically (T3.17), and M3 does not test their thread or batch invariance.
 *
 * Threads. The Embree device is process-wide, created on first use, with threads=1 (builds run on
 * one thread). Embree's tasking runs only builds. Concurrent calls to
 * painterly_embree_intersect_closest on one scene are allowed.
 *
 * Ownership. painterly_embree_scene_create copies the vertices, the indices and the transforms
 * into Embree-owned buffers. The returned scene keeps no pointer into the caller's arrays. */

#include <cstddef>
#include <cstdint>

#include "painterly/kernel/globals.h"

CCL_NAMESPACE_BEGIN

struct PainterlyEmbreeScene; /* Opaque. Destroy with painterly_embree_scene_free. */

/* One triangle mesh in object space. */
struct PainterlyEmbreeMeshInput {
  const float *vertices; /* PAINTERLY_POINT_FLOATS floats (x, y, z) per vertex. */
  size_t num_vertices;
  const uint32_t *triangles; /* PAINTERLY_TRIANGLE_CORNERS vertex indices per triangle. */
  size_t num_triangles;
};

/* One object: an instance of a mesh. */
struct PainterlyEmbreeObjectInput {
  int mesh; /* Index into the meshes array. */
  const float
      *object_to_world; /* 12 floats, row-major 3x4 affine: the last column is the translation. */
};

/* Builds the scene. An object whose mesh has no triangles is skipped: it cannot be hit. Throws
 * std::invalid_argument for malformed input (a null array with a nonzero count, an index outside
 * its mesh, a mesh index outside the meshes array, a singular object_to_world of an object whose
 * mesh has triangles), and std::runtime_error when Embree fails. Free the result with
 * painterly_embree_scene_free. */
PainterlyEmbreeScene *painterly_embree_scene_create(const PainterlyEmbreeMeshInput *meshes,
                                                    size_t num_meshes,
                                                    const PainterlyEmbreeObjectInput *objects,
                                                    size_t num_objects);

/* Releases the scene. A null pointer is allowed. */
void painterly_embree_scene_free(PainterlyEmbreeScene *scene);

/* Closest hit with tnear <= t <= tfar, where t is parametric along the unnormalized ray.d (SPEC
 * §4). Returns true and fills *isect with kind HIT_TRIANGLE, index = object, prim, u, v and the
 * world Ng. Returns false, with *isect reset to HIT_NONE, on a miss or when bvh is null. Pass
 * tnear = ray_epsilon (smallpaint's eps, 1e-4) to exclude the surface a path starts on (SPEC §6).
 */
bool painterly_embree_intersect_closest(const void *bvh,
                                        const PainterlyRay &ray,
                                        double tnear,
                                        double tfar,
                                        PainterlyIntersection *isect);

CCL_NAMESPACE_END
