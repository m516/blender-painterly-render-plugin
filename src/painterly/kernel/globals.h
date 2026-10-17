/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* CONTRACT: Opus-owned. Do not edit without an Opus card. */

#pragma once

/* Read-only view of the device scene for one render, the counterpart of Cycles'
 * KernelGlobalsCPU. Built by painterly/scene/ (PainterlyDeviceScene) and passed by const
 * reference/pointer. */

#include "painterly/kernel/types.h"

CCL_NAMESPACE_BEGIN

/* Layout definitions of the triangle arrays. A point or a normal is PAINTERLY_POINT_FLOATS floats
 * (x, y, z), and a triangle has PAINTERLY_TRIANGLE_CORNERS corners (v0, v1, v2, in the order of
 * Embree's barycentrics, painterly/bvh/embree.h). The corner normals of one triangle are
 * PAINTERLY_TRIANGLE_CORNERS * PAINTERLY_POINT_FLOATS floats. */
constexpr int PAINTERLY_POINT_FLOATS = 3;
constexpr int PAINTERLY_TRIANGLE_CORNERS = 3;

/* Instance of a triangle mesh. Its object_to_world (row-major 3x4 affine, float, as exported by
 * Blender) goes to the BVH only (painterly/bvh/embree.h), which keeps its own copy. */
struct KernelPainterlyObject {
  /* (A^-1)^T of the 3x3 part A of object_to_world, row-major, in double: maps object-space corner
   * normals to world space. painterly_normal_matrix (painterly/util/math_double3.h) computes it,
   * and the BVH maps Embree's Ng with the same function (TQ.1 F25). */
  double normal_to_world[9];
  int mesh;      /* Index into meshes. */
  int object_id; /* Value written to the object_id buffer. */
};

struct KernelPainterlyMesh {
  int tri_offset; /* First triangle of this mesh in the global tri_* arrays. */
  int num_tris;
  int has_corner_normals; /* 0: flat shading from the geometric normal. */
};

struct PainterlyGlobalsCPU {
  const KernelPainterlyData *data = nullptr;

  const KernelPainterlyAnalytic *analytic = nullptr; /* Scene-list order (SPEC §9, §5). */
  int num_analytic = 0;

  const KernelPainterlyMaterial *materials = nullptr;
  int num_materials = 0;
  const KernelPainterlyLobe *lobes = nullptr; /* Constant lobes of all materials. */
  int num_lobes = 0;

  const KernelPainterlySun *suns = nullptr; /* data->background.num_suns entries. */

  const KernelPainterlyObject *objects = nullptr;
  int num_objects = 0;
  const KernelPainterlyMesh *meshes = nullptr;
  int num_meshes = 0;

  /* Per triangle of every mesh, indexed by mesh.tri_offset + prim (the triangle in its mesh). The
   * vertices are not here: only the BVH reads them, from its own copy (painterly/bvh/embree.h). */
  const int *tri_material = nullptr; /* Material index. */
  /* PAINTERLY_TRIANGLE_CORNERS * PAINTERLY_POINT_FLOATS floats per triangle: n0, n1, n2 in object
   * space. Read only for meshes with has_corner_normals. Null when no mesh has corner normals. */
  const float *tri_corner_normals = nullptr;

  /* Opaque triangle BVH (painterly/bvh/embree.h PainterlyEmbreeScene). Null when the scene has no
   * triangles. */
  const void *bvh = nullptr;
};

using PainterlyGlobals = const PainterlyGlobalsCPU *;

/* PainterlyRay with an unnormalized direction (SPEC §4): t is parametric along d. */
struct PainterlyRay {
  double3 o;
  double3 d;
};

enum PainterlyHitKind : int {
  HIT_NONE = 0,
  HIT_ANALYTIC = 1,
  HIT_TRIANGLE = 2,
};

struct PainterlyIntersection {
  double t = 0.0;               /* Parametric distance along the (unnormalized) ray direction. */
  int kind = HIT_NONE;          /* PainterlyHitKind */
  int index = -1;               /* HIT_ANALYTIC: analytic index. HIT_TRIANGLE: object index. */
  int prim = -1;                /* HIT_TRIANGLE: triangle index within the mesh. */
  float u = 0.0f, v = 0.0f;     /* HIT_TRIANGLE: barycentrics (Embree convention). */
  double3 Ng = {0.0, 0.0, 0.0}; /* HIT_TRIANGLE: unnormalized world geometric normal. */
};

CCL_NAMESPACE_END
