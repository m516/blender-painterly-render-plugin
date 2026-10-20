/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "painterly/scene/device_scene.h"

#include <memory>
#include <stdexcept>
#include <vector>

#include "painterly/scene/scene.h"
#include "painterly/util/math_double3.h"
#include "util/transform.h"

CCL_NAMESPACE_BEGIN

namespace {

/* Row-major 3x3 product a * b. */
void painterly_matmul_3x3(const double a[9], const double b[9], double out[9])
{
  for (int r = 0; r < 3; r++) {
    for (int c = 0; c < 3; c++) {
      out[3 * r + c] = a[3 * r + 0] * b[0 + c] + a[3 * r + 1] * b[3 + c] + a[3 * r + 2] * b[6 + c];
    }
  }
}

/* R(e), the XYZ Euler rotation of `euler` (radians), row-major, in double. Cycles'
 * euler_to_transform evaluates cosf/sinf in float and stores the result as Transform's rows x, y,
 * z (util/transform.h), so the nine entries are the float values widened to double (SPEC §1). */
void painterly_euler_rotation(const float3 euler, double out[9])
{
  const Transform t = euler_to_transform(euler);
  out[0] = double(t.x.x);
  out[1] = double(t.x.y);
  out[2] = double(t.x.z);
  out[3] = double(t.y.x);
  out[4] = double(t.y.y);
  out[5] = double(t.y.z);
  out[6] = double(t.z.x);
  out[7] = double(t.z.y);
  out[8] = double(t.z.z);
}

/* M_s->cam, the matrix with the columns (0,-1,0), (1,0,0), (0,0,1) (SPEC §1), row-major. */
constexpr double PAINTERLY_M_S_TO_CAM[9] = {0.0, 1.0, 0.0, -1.0, 0.0, 0.0, 0.0, 0.0, 1.0};

}  // namespace

PainterlyDeviceScene::~PainterlyDeviceScene()
{
  clear_bvh();
}

void PainterlyDeviceScene::clear_bvh()
{
  if (bvh_) {
    painterly_embree_scene_free(bvh_);
    bvh_ = nullptr;
  }
  globals_.bvh = nullptr;
}

void PainterlyDeviceScene::set_bvh(PainterlyEmbreeScene *scene)
{
  clear_bvh();
  bvh_ = scene;
  globals_.bvh = bvh_;
}

void PainterlyDeviceScene::bind_globals()
{
  globals_.data = &data;
  globals_.analytic = array_or_null(analytic);
  globals_.num_analytic = int(analytic.size());
  globals_.materials = array_or_null(materials);
  globals_.num_materials = int(materials.size());
  globals_.lobes = array_or_null(lobes);
  globals_.num_lobes = int(lobes.size());
  globals_.suns = array_or_null(suns);
  globals_.objects = array_or_null(objects);
  globals_.num_objects = int(objects.size());
  globals_.meshes = array_or_null(meshes);
  globals_.num_meshes = int(meshes.size());
  globals_.tri_material = array_or_null(tri_material);
  globals_.tri_corner_normals = array_or_null(tri_corner_normals);
  globals_.bvh = bvh_;
}

PainterlyGlobalsCPU PainterlyDeviceScene::globals() const
{
  return globals_;
}

void PainterlyScene::device_update(PainterlyDeviceScene &ds) const
{
  /* The strong guarantee: every array and the Embree scene are built in locals below, and `ds` is
   * written only by the commit at the end, after every check has passed. A throw therefore leaves
   * the device scene exactly as it was: its arrays, its kernel data, the BVH and the pointers that
   * bind_globals() set (they would otherwise dangle after a reallocation). */
  std::vector<KernelPainterlyMaterial> new_materials;
  std::vector<KernelPainterlyLobe> new_lobes;
  std::vector<KernelPainterlyAnalytic> new_analytic;
  std::vector<KernelPainterlyMesh> new_meshes;
  std::vector<int> new_tri_material;
  std::vector<float> new_tri_corner_normals;
  std::vector<KernelPainterlyObject> new_objects;
  std::vector<KernelPainterlySun> new_suns;
  KernelPainterlyData new_data{};
  /* Owns the new Embree scene until the device scene takes it, so a throw after the build frees
   * it. */
  std::unique_ptr<PainterlyEmbreeScene, decltype(&painterly_embree_scene_free)> new_bvh(
      nullptr, painterly_embree_scene_free);

  /* --- Materials: flatten the lobes (SPEC §6). --- */
  for (const PainterlyMaterial &material : materials) {
    material.validate();
    KernelPainterlyMaterial kernel_material{};
    kernel_material.lobe_offset = int(new_lobes.size());
    kernel_material.num_lobes = int(material.lobes.size());
    kernel_material.emission = material.emission;
    /* Constant lobes: no SVM program overrides them (painterly/kernel/types.h). */
    kernel_material.svm_offset = -1;
    new_lobes.insert(new_lobes.end(), material.lobes.begin(), material.lobes.end());
    new_materials.push_back(kernel_material);
  }

  /* --- Analytic primitives, in scene-list order (SPEC §5, §9). --- */
  new_analytic.reserve(analytic.size());
  for (const PainterlyAnalyticPrimitive &prim : analytic) {
    if (prim.material < 0 || size_t(prim.material) >= materials.size()) {
      throw std::invalid_argument("PainterlyScene::device_update: material index out of range");
    }
    KernelPainterlyAnalytic kernel_prim{};
    kernel_prim.type = prim.type;
    kernel_prim.intersection = prim.intersection;
    kernel_prim.material = prim.material;
    kernel_prim.object_id = prim.object_id;
    kernel_prim.a = prim.a;
    kernel_prim.b = prim.b;
    kernel_prim.spot = prim.spot;
    new_analytic.push_back(kernel_prim);
  }

  /* --- Meshes: the triangle arrays the kernel reads. The vertices and the indices go to Embree
   * only, which copies them: the device scene keeps no vertex array (T3.21, D35). --- */
  bool any_corner_normals = false;
  for (const PainterlyMesh &mesh : meshes) {
    mesh.validate();
    any_corner_normals = any_corner_normals || mesh.has_corner_normals();
  }
  new_meshes.reserve(meshes.size());
  int tri_offset = 0;
  for (const PainterlyMesh &mesh : meshes) {
    const int num_tris = mesh.num_triangles();
    for (const int material : mesh.tri_material) {
      if (material < 0 || size_t(material) >= materials.size()) {
        throw std::invalid_argument("PainterlyScene::device_update: material index out of range");
      }
    }
    KernelPainterlyMesh kernel_mesh{};
    kernel_mesh.tri_offset = tri_offset;
    kernel_mesh.num_tris = num_tris;
    kernel_mesh.has_corner_normals = mesh.has_corner_normals() ? 1 : 0;
    new_meshes.push_back(kernel_mesh);
    new_tri_material.insert(
        new_tri_material.end(), mesh.tri_material.begin(), mesh.tri_material.end());
    if (any_corner_normals) {
      /* One block of PAINTERLY_TRIANGLE_CORNERS * PAINTERLY_POINT_FLOATS floats per triangle of
       * every mesh, zeros for a mesh without corner normals (painterly/kernel/globals.h). */
      const size_t block = size_t(num_tris) * size_t(PAINTERLY_TRIANGLE_CORNERS) *
                           size_t(PAINTERLY_POINT_FLOATS);
      if (mesh.has_corner_normals()) {
        new_tri_corner_normals.insert(
            new_tri_corner_normals.end(), mesh.corner_normals.begin(), mesh.corner_normals.end());
      }
      else {
        new_tri_corner_normals.insert(new_tri_corner_normals.end(), block, 0.0f);
      }
    }
    tri_offset += num_tris;
  }

  /* --- Objects: the mesh index, the object id and the normal matrix. Embree's Ng goes through the
   * same painterly_normal_matrix, so Ng and the corner normals share one matrix (T3.21). --- */
  new_objects.reserve(objects.size());
  for (const PainterlyObject &object : objects) {
    if (object.mesh < 0 || size_t(object.mesh) >= meshes.size()) {
      throw std::invalid_argument("PainterlyScene::device_update: object mesh index out of range");
    }
    KernelPainterlyObject kernel_object{};
    kernel_object.mesh = object.mesh;
    kernel_object.object_id = object.object_id;
    if (meshes[size_t(object.mesh)].num_triangles() > 0) {
      /* Throws std::invalid_argument when the 3x3 part is singular, as
       * painterly_embree_scene_create does for an object whose mesh has triangles. */
      painterly_normal_matrix(object.object_to_world, kernel_object.normal_to_world);
    }
    else {
      /* A mesh without triangles cannot be hit, so the kernel never reads this matrix; it stays
       * zero, exactly as painterly_embree_scene_create skips such an object before computing its
       * own (T3.13 review finding, M3-fixups-reviews.json; Opus ruling, 2026-10-18). */
      for (double &entry : kernel_object.normal_to_world) {
        entry = 0.0;
      }
    }
    new_objects.push_back(kernel_object);
  }

  /* --- Camera and integrator. --- */
  integrator.device_update(new_data.integrator);
  camera.device_update(new_data.cam, double(integrator.get_jitter()));

  /* --- The spiral frame F (SPEC §1). --- */
  double rotation[9];
  painterly_euler_rotation(integrator.get_spiral_rotation(), rotation);
  double frame[9];
  const int spiral_frame = integrator.get_spiral_frame();
  if (spiral_frame == SPIRAL_FRAME_SMALLPAINT) {
    /* SPEC §1: reference scenes are authored in smallpaint coordinates, so F = I. */
    const double identity[9] = {1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0};
    for (int i = 0; i < 9; i++) {
      frame[i] = identity[i];
    }
  }
  else if (spiral_frame == SPIRAL_FRAME_WORLD) {
    for (int i = 0; i < 9; i++) {
      frame[i] = rotation[i];
    }
  }
  else if (spiral_frame == SPIRAL_FRAME_CAMERA) {
    /* F = R_cam->world * M_s->cam * R(e). R_cam->world is the 3x3 part of the camera's
     * camera_to_world (row-major 3x4: the first three entries of each row). */
    double r_cam_to_world[9];
    for (int r = 0; r < 3; r++) {
      for (int c = 0; c < 3; c++) {
        r_cam_to_world[3 * r + c] =
            camera.camera_to_world[PAINTERLY_TRANSFORM_3X4_ROW_STRIDE * r + c];
      }
    }
    double temp[9];
    painterly_matmul_3x3(r_cam_to_world, PAINTERLY_M_S_TO_CAM, temp);
    painterly_matmul_3x3(temp, rotation, frame);
  }
  else if (spiral_frame == SPIRAL_FRAME_OBJECT) {
    /* F = R_obj * R(e), with R_obj the caller's orthonormalized rotation. The core never
     * orthonormalizes it (SPEC §1). */
    if (!has_spiral_object_) {
      throw std::invalid_argument(
          "PainterlyScene::device_update: spiral_frame is object but no spiral object is set");
    }
    painterly_matmul_3x3(spiral_object_rotation_, rotation, frame);
  }
  else {
    throw std::invalid_argument("PainterlyScene::device_update: unknown spiral_frame");
  }
  for (int i = 0; i < 9; i++) {
    new_data.integrator.spiral_frame[i] = frame[i];
  }

  /* --- Background and suns. --- */
  background.device_update(new_data.background, new_suns);

  /* --- Embree, only when there are triangles. --- */
  int total_tris = 0;
  for (const PainterlyMesh &mesh : meshes) {
    total_tris += mesh.num_triangles();
  }
  if (total_tris != 0) {
    std::vector<PainterlyEmbreeMeshInput> mesh_inputs;
    mesh_inputs.reserve(meshes.size());
    for (const PainterlyMesh &mesh : meshes) {
      PainterlyEmbreeMeshInput input{};
      input.vertices = mesh.vertices.empty() ? nullptr : mesh.vertices.data();
      input.num_vertices = size_t(mesh.num_vertices());
      input.triangles = mesh.triangles.empty() ? nullptr : mesh.triangles.data();
      input.num_triangles = size_t(mesh.num_triangles());
      mesh_inputs.push_back(input);
    }
    std::vector<PainterlyEmbreeObjectInput> object_inputs;
    object_inputs.reserve(objects.size());
    for (const PainterlyObject &object : objects) {
      PainterlyEmbreeObjectInput input{};
      input.mesh = object.mesh;
      input.object_to_world = object.object_to_world;
      object_inputs.push_back(input);
    }
    new_bvh.reset(painterly_embree_scene_create(
        mesh_inputs.data(), mesh_inputs.size(), object_inputs.data(), object_inputs.size()));
  }

  /* --- Commit. Nothing below throws: a vector move assignment is noexcept, set_bvh only swaps
   * pointers and bind_globals only stores pointers and sizes. --- */
  ds.materials = std::move(new_materials);
  ds.lobes = std::move(new_lobes);
  ds.analytic = std::move(new_analytic);
  ds.meshes = std::move(new_meshes);
  ds.tri_material = std::move(new_tri_material);
  ds.tri_corner_normals = std::move(new_tri_corner_normals);
  ds.objects = std::move(new_objects);
  ds.suns = std::move(new_suns);
  ds.data = new_data;
  /* Takes ownership of the new Embree scene; releases the previous one, or none when the scene has
   * no triangles. */
  ds.set_bvh(new_bvh.release());
  ds.bind_globals();
}

CCL_NAMESPACE_END
