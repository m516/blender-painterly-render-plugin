/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* Triangle BVH over instanced meshes, built on Embree 4 (T3.10). The conventions are SPEC §4
 * (unnormalized rays: t is parametric along ray.d) and SPEC §5 (the hit record). Embree stays out
 * of this header: only embree.cpp includes it.
 *
 * Structure. One RTCScene per mesh holds one triangle geometry. A top-level scene holds one
 * instance per object, with the object's transform. A hit reports the object index (the position
 * of the object in the objects array), the triangle within its mesh, and the barycentrics of
 * Embree's convention: p = (1 - u - v) v0 + u v1 + v v2.
 *
 * Normals. Embree returns the geometric normal of an instance hit in object space. Ng is returned
 * in world space, transformed by the inverse transpose of the object's transform, computed in
 * double, and not normalized. Normals keep their side of the surface: n_world . (A d) = n_object .
 * d for every direction d, so an outward normal stays outward under a mirroring transform.
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
  const float *vertices; /* 3 floats per vertex (x, y, z): num_vertices * 3 floats. */
  size_t num_vertices;
  const uint32_t *triangles; /* 3 vertex indices per triangle: num_triangles * 3 indices. */
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
 * its mesh, a mesh index outside the meshes array, a singular object_to_world), and
 * std::runtime_error when Embree fails. Free the result with painterly_embree_scene_free.
 */
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
