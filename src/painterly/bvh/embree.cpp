/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "painterly/bvh/embree.h"

#include <algorithm>
#include <array>
#include <memory>
#include <stdexcept>
#include <string>
#include <vector>

#include <embree4/rtcore.h>

#include "painterly/util/math_double3.h"

/* Embree's API lives in the namespace painterly_embree (EMBREE_API_NAMESPACE,
 * cmake/painterly_embree.cmake). Only this file includes Embree. */
RTC_NAMESPACE_USE

CCL_NAMESPACE_BEGIN

namespace {

/* Embree's index format is unsigned int. The header's index arrays are uint32_t. */
static_assert(sizeof(unsigned int) == sizeof(uint32_t), "Embree indices must be 32-bit");

/* Device configuration. threads=1 runs builds on one thread (rtcNewDevice documentation: threads=n
 * sets the build threads, and the default is every hardware thread). Builds do not depend on the
 * host's core count this way. */
constexpr const char *device_config = "threads=1";

/* Vertices per triangle, and floats per 3D point. */
constexpr size_t verts_per_triangle = 3;
constexpr size_t floats_per_point = 3;
/* A row-major 3x4 affine transform stores four floats per row. The last of them is the
 * translation. */
constexpr int floats_per_row_3x4 = 4;

/* The process's one Embree device. The static is initialized on first use, and C++11 makes that
 * initialization thread-safe. A failed initialization throws, and the next call tries again. The
 * device is never released, so no scene can outlive it. */
RTCDevice embree_device()
{
  static RTCDevice device = [] {
    RTCDevice created = rtcNewDevice(device_config);
    if (!created) {
      throw std::runtime_error("rtcNewDevice failed, Embree error " +
                               std::to_string(rtcGetDeviceError(nullptr)));
    }
    return created;
  }();
  return device;
}

/* Throws if Embree has recorded an error since the last check. */
void check_embree(const char *what)
{
  const RTCError error = rtcGetDeviceError(embree_device());
  if (error != RTC_ERROR_NONE) {
    throw std::runtime_error(std::string(what) + ", Embree error " + std::to_string(error));
  }
}

/* Releases an Embree geometry handle when it leaves scope, so that an exception cannot leak it. An
 * attached geometry is kept alive by its scene, so the handle is released right after the attach.
 */
class GeometryHandle {
 public:
  explicit GeometryHandle(RTCGeometry geometry) : geometry_(geometry) {}
  ~GeometryHandle()
  {
    if (geometry_) {
      rtcReleaseGeometry(geometry_);
    }
  }
  GeometryHandle(const GeometryHandle &) = delete;
  GeometryHandle &operator=(const GeometryHandle &) = delete;

  RTCGeometry get() const
  {
    return geometry_;
  }

 private:
  RTCGeometry geometry_;
};

/* (A^-1)^T for the 3x3 part A of a row-major 3x4 affine transform, in double. A normal transforms
 * with it. The cofactor form (A^-1)^T = cofactor(A) / det(A) avoids forming an inverse. The result
 * is not normalized. Throws for a singular A, because a normal cannot be mapped through it. */
std::array<double, 9> inverse_transpose_3x3(const float *object_to_world)
{
  double a[3][3];
  for (int r = 0; r < 3; ++r) {
    for (int c = 0; c < 3; ++c) {
      a[r][c] = static_cast<double>(object_to_world[floats_per_row_3x4 * r + c]);
    }
  }

  /* cofactor(r, c) = (-1)^(r+c) times the minor of element (r, c). */
  const double c00 = a[1][1] * a[2][2] - a[1][2] * a[2][1];
  const double c01 = a[1][2] * a[2][0] - a[1][0] * a[2][2];
  const double c02 = a[1][0] * a[2][1] - a[1][1] * a[2][0];
  const double c10 = a[0][2] * a[2][1] - a[0][1] * a[2][2];
  const double c11 = a[0][0] * a[2][2] - a[0][2] * a[2][0];
  const double c12 = a[0][1] * a[2][0] - a[0][0] * a[2][1];
  const double c20 = a[0][1] * a[1][2] - a[0][2] * a[1][1];
  const double c21 = a[0][2] * a[1][0] - a[0][0] * a[1][2];
  const double c22 = a[0][0] * a[1][1] - a[0][1] * a[1][0];

  /* Expansion of det(A) along row 0. */
  const double det = a[0][0] * c00 + a[0][1] * c01 + a[0][2] * c02;
  if (det == 0.0) {
    throw std::invalid_argument("painterly_embree_scene_create: singular object_to_world");
  }
  return {c00 / det,
          c01 / det,
          c02 / det,
          c10 / det,
          c11 / det,
          c12 / det,
          c20 / det,
          c21 / det,
          c22 / det};
}

}  // namespace

/* The Embree objects behind a PainterlyEmbreeScene. Destroying it releases every handle it holds.
 */
struct PainterlyEmbreeScene {
  /* One scene per mesh with triangles. nullptr for a mesh without triangles, which no object can
   * hit. */
  std::vector<RTCScene> meshes;
  /* Top-level scene: one instance per object whose mesh has triangles. */
  RTCScene top = nullptr;
  /* Indexed by the instance geometry ID that a hit reports in hit.instID[0]: the object index, and
   * (A^-1)^T of the object's transform. */
  std::vector<int> object;
  std::vector<std::array<double, 9>> normal_to_world;

  PainterlyEmbreeScene() = default;
  PainterlyEmbreeScene(const PainterlyEmbreeScene &) = delete;
  PainterlyEmbreeScene &operator=(const PainterlyEmbreeScene &) = delete;

  ~PainterlyEmbreeScene()
  {
    /* The top-level scene goes first: its instances hold references to the mesh scenes. */
    if (top) {
      rtcReleaseScene(top);
    }
    for (RTCScene mesh : meshes) {
      if (mesh) {
        rtcReleaseScene(mesh);
      }
    }
  }
};

PainterlyEmbreeScene *painterly_embree_scene_create(const PainterlyEmbreeMeshInput *meshes,
                                                    size_t num_meshes,
                                                    const PainterlyEmbreeObjectInput *objects,
                                                    size_t num_objects)
{
  if (num_meshes > 0 && !meshes) {
    throw std::invalid_argument("painterly_embree_scene_create: meshes is null");
  }
  if (num_objects > 0 && !objects) {
    throw std::invalid_argument("painterly_embree_scene_create: objects is null");
  }

  const RTCDevice device = embree_device();
  /* From here on the unique_ptr owns the Embree handles: an exception releases them in the
   * destructor. */
  std::unique_ptr<PainterlyEmbreeScene> scene = std::make_unique<PainterlyEmbreeScene>();
  scene->meshes.assign(num_meshes, nullptr);

  for (size_t m = 0; m < num_meshes; ++m) {
    const PainterlyEmbreeMeshInput &mesh = meshes[m];
    if (mesh.num_triangles == 0) {
      continue; /* Stays nullptr. */
    }
    if (!mesh.vertices || !mesh.triangles) {
      throw std::invalid_argument("painterly_embree_scene_create: mesh arrays are null");
    }
    for (size_t i = 0; i < verts_per_triangle * mesh.num_triangles; ++i) {
      if (mesh.triangles[i] >= mesh.num_vertices) {
        throw std::invalid_argument("painterly_embree_scene_create: triangle index out of range");
      }
    }

    RTCScene mesh_scene = rtcNewScene(device);
    if (!mesh_scene) {
      check_embree("painterly_embree_scene_create: rtcNewScene (mesh)");
      throw std::runtime_error("painterly_embree_scene_create: rtcNewScene failed");
    }
    scene->meshes[m] = mesh_scene;
    rtcSetSceneFlags(mesh_scene, RTC_SCENE_FLAG_ROBUST);
    rtcSetSceneBuildQuality(mesh_scene, RTC_BUILD_QUALITY_HIGH);

    GeometryHandle geometry(rtcNewGeometry(device, RTC_GEOMETRY_TYPE_TRIANGLE));
    if (!geometry.get()) {
      check_embree("painterly_embree_scene_create: rtcNewGeometry (triangle)");
      throw std::runtime_error("painterly_embree_scene_create: rtcNewGeometry failed");
    }
    float *vertex_buffer = static_cast<float *>(
        rtcSetNewGeometryBuffer(geometry.get(),
                                RTC_BUFFER_TYPE_VERTEX,
                                0,
                                RTC_FORMAT_FLOAT3,
                                floats_per_point * sizeof(float),
                                mesh.num_vertices));
    if (!vertex_buffer) {
      check_embree("painterly_embree_scene_create: vertex buffer");
      throw std::runtime_error("painterly_embree_scene_create: vertex buffer allocation failed");
    }
    std::copy(mesh.vertices, mesh.vertices + floats_per_point * mesh.num_vertices, vertex_buffer);

    unsigned int *index_buffer = static_cast<unsigned int *>(
        rtcSetNewGeometryBuffer(geometry.get(),
                                RTC_BUFFER_TYPE_INDEX,
                                0,
                                RTC_FORMAT_UINT3,
                                verts_per_triangle * sizeof(unsigned int),
                                mesh.num_triangles));
    if (!index_buffer) {
      check_embree("painterly_embree_scene_create: index buffer");
      throw std::runtime_error("painterly_embree_scene_create: index buffer allocation failed");
    }
    std::copy(
        mesh.triangles, mesh.triangles + verts_per_triangle * mesh.num_triangles, index_buffer);

    rtcCommitGeometry(geometry.get());
    rtcAttachGeometry(mesh_scene, geometry.get());
    rtcCommitScene(mesh_scene);
    check_embree("painterly_embree_scene_create: mesh scene");
  }

  scene->top = rtcNewScene(device);
  if (!scene->top) {
    check_embree("painterly_embree_scene_create: rtcNewScene (top level)");
    throw std::runtime_error("painterly_embree_scene_create: rtcNewScene failed");
  }
  rtcSetSceneFlags(scene->top, RTC_SCENE_FLAG_ROBUST);
  rtcSetSceneBuildQuality(scene->top, RTC_BUILD_QUALITY_HIGH);

  for (size_t o = 0; o < num_objects; ++o) {
    const PainterlyEmbreeObjectInput &object = objects[o];
    if (object.mesh < 0 || static_cast<size_t>(object.mesh) >= num_meshes) {
      throw std::invalid_argument("painterly_embree_scene_create: object mesh index out of range");
    }
    if (!object.object_to_world) {
      throw std::invalid_argument("painterly_embree_scene_create: object_to_world is null");
    }
    const RTCScene mesh_scene = scene->meshes[object.mesh];
    if (!mesh_scene) {
      continue; /* A mesh without triangles cannot be hit. */
    }
    const std::array<double, 9> normal_matrix = inverse_transpose_3x3(object.object_to_world);

    GeometryHandle instance(rtcNewGeometry(device, RTC_GEOMETRY_TYPE_INSTANCE));
    if (!instance.get()) {
      check_embree("painterly_embree_scene_create: rtcNewGeometry (instance)");
      throw std::runtime_error("painterly_embree_scene_create: rtcNewGeometry failed");
    }
    rtcSetGeometryInstancedScene(instance.get(), mesh_scene);
    rtcSetGeometryTransform(
        instance.get(), 0, RTC_FORMAT_FLOAT3X4_ROW_MAJOR, object.object_to_world);
    rtcCommitGeometry(instance.get());
    /* Instance IDs are the positions in scene->object, so a hit's instID[0] indexes scene->object.
     */
    rtcAttachGeometryByID(
        scene->top, instance.get(), static_cast<unsigned int>(scene->object.size()));
    scene->object.push_back(static_cast<int>(o));
    scene->normal_to_world.push_back(normal_matrix);
  }

  rtcCommitScene(scene->top);
  check_embree("painterly_embree_scene_create: top-level scene");
  return scene.release();
}

void painterly_embree_scene_free(PainterlyEmbreeScene *scene)
{
  delete scene;
}

bool painterly_embree_intersect_closest(const void *bvh,
                                        const PainterlyRay &ray,
                                        double tnear,
                                        double tfar,
                                        PainterlyIntersection *isect)
{
  const PainterlyEmbreeScene *scene = static_cast<const PainterlyEmbreeScene *>(bvh);
  if (!scene) {
    *isect = PainterlyIntersection{};
    return false;
  }

  /* Embree takes binary32 rays. The direction is passed unnormalized (SPEC §4): t is parametric
   * along ray.d. */
  RTCRayHit rayhit{};
  rayhit.ray.org_x = static_cast<float>(ray.o.x);
  rayhit.ray.org_y = static_cast<float>(ray.o.y);
  rayhit.ray.org_z = static_cast<float>(ray.o.z);
  rayhit.ray.dir_x = static_cast<float>(ray.d.x);
  rayhit.ray.dir_y = static_cast<float>(ray.d.y);
  rayhit.ray.dir_z = static_cast<float>(ray.d.z);
  rayhit.ray.tnear = static_cast<float>(tnear);
  rayhit.ray.tfar = static_cast<float>(tfar);
  rayhit.ray.time = 0.0f;
  rayhit.ray.mask = 0xFFFFFFFFu; /* Every bit set: the ray is not masked. */
  rayhit.ray.id = 0;
  rayhit.ray.flags = 0;
  rayhit.hit.geomID = RTC_INVALID_GEOMETRY_ID;
  rayhit.hit.primID = RTC_INVALID_GEOMETRY_ID;
  rayhit.hit.instID[0] = RTC_INVALID_GEOMETRY_ID;

  rtcIntersect1(scene->top, &rayhit);

  if (rayhit.hit.geomID == RTC_INVALID_GEOMETRY_ID) {
    *isect = PainterlyIntersection{};
    return false;
  }

  /* An instance hit: the top-level scene holds only instances, so instID[0] names the object. The
   * normal is in object space and goes to world space through the object's inverse transpose. */
  const unsigned int instance = rayhit.hit.instID[0];
  const std::array<double, 9> &normal_matrix = scene->normal_to_world[instance];
  const double3 ng_object = make_double3(static_cast<double>(rayhit.hit.Ng_x),
                                         static_cast<double>(rayhit.hit.Ng_y),
                                         static_cast<double>(rayhit.hit.Ng_z));

  isect->t = static_cast<double>(rayhit.ray.tfar);
  isect->kind = HIT_TRIANGLE;
  isect->index = scene->object[instance];
  isect->prim = static_cast<int>(rayhit.hit.primID);
  isect->u = rayhit.hit.u;
  isect->v = rayhit.hit.v;
  isect->Ng = transform_direction_3x3(normal_matrix.data(), ng_object);
  return true;
}

CCL_NAMESPACE_END
