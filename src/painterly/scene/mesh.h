/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* PainterlyMesh: an indexed triangle mesh in object space, with an optional per-triangle corner
 * normal block. It is the host form of the arrays that PainterlyScene::device_update hands to
 * Embree (the vertices and the indices) and to the device scene (tri_material and
 * tri_corner_normals, painterly/kernel/globals.h). */

#include <cstdint>
#include <stdexcept>
#include <vector>

#include "painterly/kernel/globals.h"

CCL_NAMESPACE_BEGIN

class PainterlyMesh {
 public:
  /* PAINTERLY_POINT_FLOATS floats (x, y, z) per vertex, object space. */
  std::vector<float> vertices;
  /* PAINTERLY_TRIANGLE_CORNERS vertex indices per triangle, in the order of Embree's barycentrics
   * (painterly/bvh/embree.h): the geometric normal is (v1 - v0) x (v2 - v0). */
  std::vector<uint32_t> triangles;
  /* One scene material index per triangle. */
  std::vector<int> tri_material;
  /* PAINTERLY_TRIANGLE_CORNERS * PAINTERLY_POINT_FLOATS floats per triangle (n0, n1, n2), object
   * space, or empty for flat shading from the geometric normal. */
  std::vector<float> corner_normals;

  int num_vertices() const
  {
    return int(vertices.size() / size_t(PAINTERLY_POINT_FLOATS));
  }
  int num_triangles() const
  {
    return int(triangles.size() / size_t(PAINTERLY_TRIANGLE_CORNERS));
  }
  bool has_corner_normals() const
  {
    return !corner_normals.empty();
  }

  /* Checks the shapes and the index bounds, and throws std::invalid_argument with the reason
   * otherwise. Called by PainterlyScene::add_mesh and by PainterlyScene::device_update, so a mesh
   * filled directly is checked too. */
  void validate() const;
};

CCL_NAMESPACE_END
