/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

/* CONTRACT: Opus-owned. Do not edit without an Opus card. */

#pragma once

/* Read-only view of the device scene for one render, the counterpart of Cycles'
 * PainterlyGlobalsCPU. Built by scene/ (PainterlyDeviceScene) and passed by const
 * reference/pointer. */

#include "painterly/kernel/types.h"

CCL_NAMESPACE_BEGIN

/* Instance of a triangle mesh. Transforms are row-major 3x4 affine (float, as exported by
 * Blender). */
struct KernelPainterlyObject {
  float tfm[12];  /* object -> world */
  float itfm[12]; /* world -> object (its 3x3 transpose transforms normals object -> world) */
  int mesh;       /* Index into meshes. */
  int object_id;  /* Value written to the object-id pass. */
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

  /* Per triangle, indexed by mesh.tri_offset + prim_id. */
  const int *tri_material = nullptr;         /* Material index. */
  const float *tri_vertices = nullptr;       /* 9 floats: v0, v1, v2 in object space. */
  const float *tri_corner_normals = nullptr; /* 9 floats: n0, n1, n2 in object space, or null. */

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
