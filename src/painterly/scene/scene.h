/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* PainterlyScene: the host scene, the counterpart of Cycles' Scene at painterly scale (T3.13).
 * It owns the materials, the analytic primitives, the meshes, the objects, the camera, the
 * background and the integrator; PainterlyScene::device_update (device_scene.cpp) is the only
 * bridge to the kernel (docs/architecture.md, "Dependency direction"). The methods mirror the
 * _painterly.pyi Scene API, so the bindings (T3.15) are a thin conversion layer. */

#include <array>
#include <cstdint>
#include <vector>

#include "painterly/scene/analytic.h"
#include "painterly/scene/background.h"
#include "painterly/scene/camera.h"
#include "painterly/scene/integrator.h"
#include "painterly/scene/material.h"
#include "painterly/scene/mesh.h"
#include "painterly/scene/object.h"

CCL_NAMESPACE_BEGIN

/* The 3x3 identity, row-major. Its single definition: the spiral object's rotation starts here
 * (spiral_object_rotation_), and the spiral frame `smallpaint` is F = I (SPEC §1). The 3x3
 * identity is a mathematical definition (delta(r, c)), not a tuned value. */
constexpr std::array<double, 9> PAINTERLY_IDENTITY_3X3 = {
    1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0};

class PainterlyDeviceScene;

class PainterlyScene {
 public:
  std::vector<PainterlyMaterial> materials;
  std::vector<PainterlyAnalyticPrimitive> analytic;
  std::vector<PainterlyMesh> meshes;
  std::vector<PainterlyObject> objects;
  PainterlyCamera camera;
  PainterlyBackground background;
  PainterlyIntegrator integrator;

  PainterlyScene() = default;

  /* Empties every list and resets the camera, the background, the integrator, the spiral object
   * and the automatic object-id counter. */
  void clear();

  /* A material with at least one lobe (SPEC §6). Validated by PainterlyMaterial::validate().
   * Returns its index. */
  int add_material(const std::vector<KernelPainterlyLobe> &lobes, const double3 emission);

  /* A sphere (SPEC §5, §9). `intersection` selects smallpaint's ghost quadratic or the exact one.
   * `spot` is nullopt for isotropic emission. Returns the primitive's index. */
  int add_sphere(const double3 center,
                 double radius,
                 int material,
                 PainterlySphereIntersection intersection,
                 int object_id,
                 const KernelPainterlySpotProfile *spot);
  /* A plane n.p + d = 0 (SPEC §9). Returns the primitive's index. */
  int add_plane(const double3 normal, double d, int material, int object_id);

  /* A triangle mesh (see PainterlyMesh for the layouts). Validated by
   * PainterlyMesh::validate(). Returns its index. */
  int add_mesh(const std::vector<float> &vertices,
               const std::vector<uint32_t> &triangles,
               const std::vector<int> &tri_material,
               const std::vector<float> &corner_normals);
  /* An instance of `mesh`: a row-major 3x4 affine object_to_world of 12 floats, exactly as
   * Blender exports it and as Embree receives it (painterly/bvh/embree.h). Returns its index. */
  int add_object(int mesh, const float object_to_world[12], int object_id);

  /* SPEC §7 cameras. The smallpaint camera has no fit and no matrices (D19). */
  void set_camera_smallpaint(int width, int height);
  void set_camera_perspective(int width,
                              int height,
                              const double raster_to_camera[16],
                              const double camera_to_world[12],
                              PainterlyCameraFit fit);
  void set_camera_orthographic(int width,
                               int height,
                               const double raster_to_camera[16],
                               const double camera_to_world[12],
                               PainterlyCameraFit fit);

  /* The constant world radiance seen on a miss (SPEC §6). */
  void set_background(const double3 radiance);
  /* A sun: `direction` toward the sun, normalized here; `angle` the angular diameter in radians
   * (SPEC §6). Returns its index. */
  int add_sun(const double3 direction, double angle, const double3 radiance);

  /* SPEC §1: the rotation R_obj of spiral_frame `object`, row-major 3x3, double. The caller
   * passes an orthonormal rotation (Blender's matrix_world.to_quaternion().to_matrix(), M5); the
   * core never orthonormalizes. */
  void set_spiral_object(const double rotation[9]);

  /* Writes every kernel-consumed field into ds and rebuilds the Embree scene when the scene has
   * triangles (device_scene.h). Throws std::invalid_argument for a mesh that does not validate, a
   * material index out of range, a singular object transform of an object with triangles, or
   * spiral_frame `object` with no spiral object set. */
  void device_update(PainterlyDeviceScene &ds) const;

 private:
  /* SPEC §9 object ids: the running count of add_sphere/add_plane/add_object calls, used when the
   * caller passes object_id < 0. */
  int next_object_id_ = 0;
  bool has_spiral_object_ = false;
  /* Row-major 3x3, the identity until set_spiral_object is called. */
  std::array<double, 9> spiral_object_rotation_ = PAINTERLY_IDENTITY_3X3;
};

CCL_NAMESPACE_END
