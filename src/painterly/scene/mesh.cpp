/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "painterly/scene/mesh.h"

CCL_NAMESPACE_BEGIN

void PainterlyMesh::validate() const
{
  if (vertices.size() % size_t(PAINTERLY_POINT_FLOATS) != 0) {
    throw std::invalid_argument("PainterlyMesh: vertices must be 3 floats per vertex");
  }
  if (triangles.size() % size_t(PAINTERLY_TRIANGLE_CORNERS) != 0) {
    throw std::invalid_argument("PainterlyMesh: triangles must be 3 indices per triangle");
  }
  const size_t num_tris = triangles.size() / size_t(PAINTERLY_TRIANGLE_CORNERS);
  if (tri_material.size() != num_tris) {
    throw std::invalid_argument("PainterlyMesh: tri_material must have one entry per triangle");
  }
  if (!corner_normals.empty() && corner_normals.size() != num_tris *
                                                              size_t(PAINTERLY_TRIANGLE_CORNERS) *
                                                              size_t(PAINTERLY_POINT_FLOATS))
  {
    throw std::invalid_argument("PainterlyMesh: corner_normals must have 9 floats per triangle");
  }
  const uint32_t num_verts = uint32_t(num_vertices());
  for (const uint32_t index : triangles) {
    if (index >= num_verts) {
      throw std::invalid_argument("PainterlyMesh: triangle index out of range");
    }
  }
}

CCL_NAMESPACE_END
