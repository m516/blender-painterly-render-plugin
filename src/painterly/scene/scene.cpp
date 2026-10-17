/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "painterly/scene/scene.h"

#include <stdexcept>

#include "painterly/scene/device_scene.h"

CCL_NAMESPACE_BEGIN

/* SPEC §9: object_id < 0 means auto, the running count of add_sphere/add_plane/add_object calls.
 */
static int painterly_resolve_object_id(const int requested, int &next_object_id)
{
  const int object_id = (requested < 0) ? next_object_id : requested;
  next_object_id++;
  return object_id;
}

void PainterlyScene::clear()
{
  materials.clear();
  analytic.clear();
  meshes.clear();
  objects.clear();
  camera = PainterlyCamera();
  background = PainterlyBackground();
  integrator = PainterlyIntegrator();
  next_object_id_ = 0;
  has_spiral_object_ = false;
  const double identity[9] = {1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0};
  for (int i = 0; i < 9; i++) {
    spiral_object_rotation_[i] = identity[i];
  }
}

int PainterlyScene::add_material(const std::vector<KernelPainterlyLobe> &lobes,
                                 const double3 emission)
{
  PainterlyMaterial material;
  material.lobes = lobes;
  material.emission = emission;
  material.validate();
  materials.push_back(material);
  return int(materials.size()) - 1;
}

int PainterlyScene::add_sphere(const double3 center,
                               const double radius,
                               const int material,
                               const PainterlySphereIntersection intersection,
                               const int object_id,
                               const KernelPainterlySpotProfile *spot)
{
  PainterlyAnalyticPrimitive prim;
  prim.type = ANALYTIC_SPHERE;
  prim.intersection = intersection;
  prim.material = material;
  prim.object_id = painterly_resolve_object_id(object_id, next_object_id_);
  prim.a = center;
  prim.b = radius;
  if (spot != nullptr) {
    prim.spot = *spot;
  }
  analytic.push_back(prim);
  return int(analytic.size()) - 1;
}

int PainterlyScene::add_plane(const double3 normal,
                              const double d,
                              const int material,
                              const int object_id)
{
  PainterlyAnalyticPrimitive prim;
  prim.type = ANALYTIC_PLANE;
  prim.material = material;
  prim.object_id = painterly_resolve_object_id(object_id, next_object_id_);
  prim.a = normal;
  prim.b = d;
  analytic.push_back(prim);
  return int(analytic.size()) - 1;
}

int PainterlyScene::add_mesh(const std::vector<float> &vertices,
                             const std::vector<uint32_t> &triangles,
                             const std::vector<int> &tri_material,
                             const std::vector<float> &corner_normals)
{
  PainterlyMesh mesh;
  mesh.vertices = vertices;
  mesh.triangles = triangles;
  mesh.tri_material = tri_material;
  mesh.corner_normals = corner_normals;
  mesh.validate();
  meshes.push_back(std::move(mesh));
  return int(meshes.size()) - 1;
}

int PainterlyScene::add_object(const int mesh,
                               const float object_to_world[12],
                               const int object_id)
{
  if (mesh < 0 || size_t(mesh) >= meshes.size()) {
    throw std::invalid_argument("PainterlyScene::add_object: mesh index out of range");
  }
  PainterlyObject object;
  object.mesh = mesh;
  for (int i = 0; i < 12; i++) {
    object.object_to_world[i] = object_to_world[i];
  }
  object.object_id = painterly_resolve_object_id(object_id, next_object_id_);
  objects.push_back(object);
  return int(objects.size()) - 1;
}

void PainterlyScene::set_camera_smallpaint(const int width, const int height)
{
  camera.set_smallpaint(width, height);
}

void PainterlyScene::set_camera_perspective(const int width,
                                            const int height,
                                            const double raster_to_camera[16],
                                            const double camera_to_world[12],
                                            const PainterlyCameraFit fit)
{
  camera.set_projective(
      PAINTERLY_CAMERA_PERSPECTIVE, width, height, raster_to_camera, camera_to_world, fit);
}

void PainterlyScene::set_camera_orthographic(const int width,
                                             const int height,
                                             const double raster_to_camera[16],
                                             const double camera_to_world[12],
                                             const PainterlyCameraFit fit)
{
  camera.set_projective(
      PAINTERLY_CAMERA_ORTHOGRAPHIC, width, height, raster_to_camera, camera_to_world, fit);
}

void PainterlyScene::set_background(const double3 radiance)
{
  background.radiance = radiance;
}

int PainterlyScene::add_sun(const double3 direction, const double angle, const double3 radiance)
{
  background.add_sun(direction, angle, radiance);
  return int(background.suns.size()) - 1;
}

void PainterlyScene::set_spiral_object(const double rotation[9])
{
  for (int i = 0; i < 9; i++) {
    spiral_object_rotation_[i] = rotation[i];
  }
  has_spiral_object_ = true;
}

CCL_NAMESPACE_END
