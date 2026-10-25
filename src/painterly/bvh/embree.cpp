/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "painterly/bvh/embree.h"

#include <algorithm>
#include <array>
#include <cmath>
#include <limits>
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
class PainterlyEmbreeGeometryHandle {
 public:
  explicit PainterlyEmbreeGeometryHandle(RTCGeometry geometry) : geometry_(geometry) {}
  ~PainterlyEmbreeGeometryHandle()
  {
    if (geometry_) {
      rtcReleaseGeometry(geometry_);
    }
  }
  PainterlyEmbreeGeometryHandle(const PainterlyEmbreeGeometryHandle &) = delete;
  PainterlyEmbreeGeometryHandle &operator=(const PainterlyEmbreeGeometryHandle &) = delete;

  RTCGeometry get() const
  {
    return geometry_;
  }

 private:
  RTCGeometry geometry_;
};

}  // namespace

/* The Embree objects behind a PainterlyEmbreeScene. Destroying it releases every handle it holds.
 */
struct PainterlyEmbreeScene {
  /* One scene per mesh with triangles. nullptr for a mesh without triangles, which no object can
   * hit. */
  std::vector<RTCScene> meshes;
  /* A copy of each mesh's object-space vertices (PAINTERLY_POINT_FLOATS per vertex) and triangle
   * corner indices (PAINTERLY_TRIANGLE_CORNERS per triangle), both empty for a mesh without
   * triangles. painterly_embree_intersect_closest reads the reported triangle's corners from them
   * to refine t, so no query into Embree's buffers is needed and the copy stays valid for the
   * scene's lifetime. */
  std::vector<std::vector<float>> mesh_vertices;
  std::vector<std::vector<uint32_t>> mesh_triangles;
  /* Top-level scene: one instance per object whose mesh has triangles. */
  RTCScene top = nullptr;
  /* Indexed by the instance geometry ID that a hit reports in hit.instID[0]: the object index, and
   * the object's normal matrix (A^-1)^T from painterly_normal_matrix. */
  std::vector<int> object;
  std::vector<std::array<double, 9>> normal_to_world;
  /* Indexed by the object index: the mesh the object instances (-1 for a mesh without triangles,
   * which cannot be hit), and the object's object_to_world widened to binary64. The refine of a
   * hit's t maps the reported triangle's object-space corners to world space in binary64, so the
   * transform is kept at that precision. */
  std::vector<int> object_mesh;
  std::vector<std::array<double, 12>> object_to_world;

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
  scene->mesh_vertices.resize(num_meshes);
  scene->mesh_triangles.resize(num_meshes);

  for (size_t m = 0; m < num_meshes; ++m) {
    const PainterlyEmbreeMeshInput &mesh = meshes[m];
    if (mesh.num_triangles == 0) {
      continue; /* Stays nullptr. */
    }
    if (!mesh.vertices || !mesh.triangles) {
      throw std::invalid_argument("painterly_embree_scene_create: mesh arrays are null");
    }
    for (size_t i = 0; i < PAINTERLY_TRIANGLE_CORNERS * mesh.num_triangles; ++i) {
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

    PainterlyEmbreeGeometryHandle geometry(rtcNewGeometry(device, RTC_GEOMETRY_TYPE_TRIANGLE));
    if (!geometry.get()) {
      check_embree("painterly_embree_scene_create: rtcNewGeometry (triangle)");
      throw std::runtime_error("painterly_embree_scene_create: rtcNewGeometry failed");
    }
    float *vertex_buffer = static_cast<float *>(
        rtcSetNewGeometryBuffer(geometry.get(),
                                RTC_BUFFER_TYPE_VERTEX,
                                0,
                                RTC_FORMAT_FLOAT3,
                                PAINTERLY_POINT_FLOATS * sizeof(float),
                                mesh.num_vertices));
    if (!vertex_buffer) {
      check_embree("painterly_embree_scene_create: vertex buffer");
      throw std::runtime_error("painterly_embree_scene_create: vertex buffer allocation failed");
    }
    std::copy(
        mesh.vertices, mesh.vertices + PAINTERLY_POINT_FLOATS * mesh.num_vertices, vertex_buffer);
    /* The scene's own copy, for the binary64 refine of a hit's t (see refine_triangle_t). */
    scene->mesh_vertices[m].assign(mesh.vertices,
                                   mesh.vertices + PAINTERLY_POINT_FLOATS * mesh.num_vertices);

    unsigned int *index_buffer = static_cast<unsigned int *>(
        rtcSetNewGeometryBuffer(geometry.get(),
                                RTC_BUFFER_TYPE_INDEX,
                                0,
                                RTC_FORMAT_UINT3,
                                PAINTERLY_TRIANGLE_CORNERS * sizeof(unsigned int),
                                mesh.num_triangles));
    if (!index_buffer) {
      check_embree("painterly_embree_scene_create: index buffer");
      throw std::runtime_error("painterly_embree_scene_create: index buffer allocation failed");
    }
    std::copy(mesh.triangles,
              mesh.triangles + PAINTERLY_TRIANGLE_CORNERS * mesh.num_triangles,
              index_buffer);
    scene->mesh_triangles[m].assign(
        mesh.triangles, mesh.triangles + PAINTERLY_TRIANGLE_CORNERS * mesh.num_triangles);

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

  /* Indexed by the object index: -1 until an instance is attached. */
  scene->object_mesh.assign(num_objects, -1);
  scene->object_to_world.resize(num_objects);
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
    std::array<double, 9> normal_matrix;
    painterly_normal_matrix(object.object_to_world, normal_matrix.data());

    PainterlyEmbreeGeometryHandle instance(rtcNewGeometry(device, RTC_GEOMETRY_TYPE_INSTANCE));
    if (!instance.get()) {
      check_embree("painterly_embree_scene_create: rtcNewGeometry (instance)");
      throw std::runtime_error("painterly_embree_scene_create: rtcNewGeometry failed");
    }
    rtcSetGeometryInstancedScene(instance.get(), mesh_scene);
    rtcSetGeometryTransform(
        instance.get(), 0, RTC_FORMAT_FLOAT3X4_ROW_MAJOR, object.object_to_world);
    /* The mesh and the transform, widened to binary64, for the refine of a hit's t. The widening
     * is exact: every binary32 value is a binary64 value. */
    scene->object_mesh[o] = object.mesh;
    for (int i = 0; i < 12; ++i) {
      scene->object_to_world[o][size_t(i)] = static_cast<double>(object.object_to_world[i]);
    }
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

namespace {

/* The binary64 root of the plane of one triangle, along `ray`, in world space.
 *
 * Why. Embree reports t as binary32 (rtcore_ray.h, RTCRay::tfar), so a hit point o + t d is a
 * binary32-rounded distance along the ray and does not lie on the triangle's plane: on the
 * reference box, where |o| and |t| are a few units, it misses by up to about |o + t d| 2^-24,
 * which is 1.5e-6. The path then starts its next ray from that point, and with ray_epsilon = 1e-4
 * a grazing bounce re-hits the wall it just left whenever |n.d| < 1.5e-6 / 1e-4 = 1.5e-2. The
 * analytic scene's root for a ray that starts on a plane is exactly 0, so the quad scene drew one
 * diffuse sample fewer there (M3-FIX-T3.17c).
 *
 * The refine. The reported triangle's three object-space corners, mapped to world space by
 * object_to_world in binary64, define the triangle's plane; its root along the ray is
 * t = dot(normal, v0 - o) / dot(normal, d) with normal = (v1 - v0) x (v2 - v0). The object, the
 * triangle, the barycentrics and Ng stay Embree's, so an edge still resolves to the triangle
 * Embree chose. The root is the binary64 root of the plane through the world corners; the
 * round-off bound that a doctest checks against is derived in
 * src/test/test_triangle_diagnostics.cpp.
 *
 * Returns `reported_t` unchanged when the denominator is 0 (the ray runs in the plane) or the root
 * is not finite.
 *
 * The caller must reject a root below the ray's near limit: a root below tnear means Embree
 * reported the surface the ray starts on (a binary32 self-hit, possible on a plane that is not
 * axis-aligned), which is not a hit. */
double refine_triangle_t(const PainterlyEmbreeScene &scene,
                         const unsigned int object,
                         const unsigned int prim,
                         const PainterlyRay &ray,
                         const double reported_t)
{
  const int mesh = scene.object_mesh[object];
  if (mesh < 0) {
    return reported_t;
  }
  const std::vector<uint32_t> &triangles = scene.mesh_triangles[size_t(mesh)];
  const std::vector<float> &vertices = scene.mesh_vertices[size_t(mesh)];
  const std::array<double, 12> &tfm = scene.object_to_world[object];
  const size_t first = size_t(prim) * PAINTERLY_TRIANGLE_CORNERS;
  if (first + PAINTERLY_TRIANGLE_CORNERS > triangles.size()) {
    return reported_t;
  }
  /* The world corners: r0 x + r1 y + r2 z + r3 per row, in binary64 (painterly_transform_*_3x4's
   * row-major 3x4 layout, the one object_to_world uses). */
  double3 corner[3];
  for (int c = 0; c < PAINTERLY_TRIANGLE_CORNERS; c++) {
    const size_t v = size_t(triangles[first + size_t(c)]) * PAINTERLY_POINT_FLOATS;
    if (v + PAINTERLY_POINT_FLOATS > vertices.size()) {
      return reported_t;
    }
    const double3 p_object = make_double3(static_cast<double>(vertices[v]),
                                          static_cast<double>(vertices[v + 1]),
                                          static_cast<double>(vertices[v + 2]));
    corner[c] = painterly_transform_direction_3x4(tfm.data(), p_object) +
                painterly_transform_translation_3x4(tfm.data());
  }
  const double3 normal = cross(corner[1] - corner[0], corner[2] - corner[0]);
  const double denominator = dot(normal, ray.d);
  if (denominator == 0.0) {
    return reported_t;
  }
  const double t = dot(normal, corner[0] - ray.o) / denominator;
  return std::isfinite(t) ? t : reported_t;
}

}  // namespace

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
  rayhit.ray.time = 0.0f;
  rayhit.ray.mask = 0xFFFFFFFFu; /* Every bit set: the ray is not masked. */
  rayhit.ray.id = 0;
  rayhit.ray.flags = 0;
  /* The near limit of the search, in binary32 because Embree's is: the argument's tnear, or, after
   * a self-hit, one binary32 step past the surface that was reported. */
  float near_limit = static_cast<float>(tnear);
  const float far_limit = static_cast<float>(tfar);

  /* The self-hit guard. A refined root below the near limit means Embree reported the surface the
   * ray starts on: a binary32 self-hit, which a plane that is not axis-aligned can produce (the
   * binary32 ray origin and direction put that plane a binary32 rounding from the origin, and
   * Embree's own near test is binary32 too). That is not a hit, so the search continues beyond it,
   * with a near limit one binary32 step above the reported t. The loop terminates: every round
   * strictly raises near_limit, so the binary32 values between near_limit and far_limit bound the
   * number of rounds, and in practice one round per triangle of the surface the ray starts on
   * suffices. */
  for (;;) {
    rayhit.ray.tnear = near_limit;
    rayhit.ray.tfar = far_limit;
    rayhit.hit.geomID = RTC_INVALID_GEOMETRY_ID;
    rayhit.hit.primID = RTC_INVALID_GEOMETRY_ID;
    rayhit.hit.instID[0] = RTC_INVALID_GEOMETRY_ID;

    rtcIntersect1(scene->top, &rayhit);

    if (rayhit.hit.geomID == RTC_INVALID_GEOMETRY_ID) {
      *isect = PainterlyIntersection{};
      return false;
    }

    /* instID[0] indexes scene->object, whose entry is the object index that names the mesh and the
     * transform. */
    const unsigned int instance = rayhit.hit.instID[0];
    const double reported_t = static_cast<double>(rayhit.ray.tfar);
    const double t = refine_triangle_t(
        *scene, unsigned(scene->object[instance]), rayhit.hit.primID, ray, reported_t);
    if (t >= tnear) {
      /* An instance hit: the top-level scene holds only instances, so instID[0] names the object.
       * The normal is in object space and goes to world space through the object's normal matrix,
       * the matrix that the scene stores as KernelPainterlyObject::normal_to_world. */
      const std::array<double, 9> &normal_matrix = scene->normal_to_world[instance];
      const double3 ng_object = make_double3(static_cast<double>(rayhit.hit.Ng_x),
                                             static_cast<double>(rayhit.hit.Ng_y),
                                             static_cast<double>(rayhit.hit.Ng_z));

      isect->t = t;
      isect->kind = HIT_TRIANGLE;
      isect->index = scene->object[instance];
      isect->prim = static_cast<int>(rayhit.hit.primID);
      isect->u = rayhit.hit.u;
      isect->v = rayhit.hit.v;
      isect->Ng = transform_direction_3x3(normal_matrix.data(), ng_object);
      return true;
    }

    /* The reported surface is behind the near limit: skip it. The next round starts one binary32
     * step above the reported t, because Embree's near test is binary32 and would otherwise admit
     * the same t again. A step that leaves no range misses. */
    const float next = std::nextafter(rayhit.ray.tfar, std::numeric_limits<float>::infinity());
    if (!(next > near_limit) || !(next <= far_limit)) {
      *isect = PainterlyIntersection{};
      return false;
    }
    near_limit = next;
  }
}

CCL_NAMESPACE_END
