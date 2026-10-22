/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#include "selftest.h"

#include <limits>
#include <memory>
#include <stdexcept>

#include <embree4/rtcore.h>

#include "painterly/bvh/embree.h"
#include "painterly/kernel/globals.h"
#include "painterly/util/types_double3.h"

// Embree's API lives in the namespace painterly_embree (EMBREE_API_NAMESPACE, see
// cmake/painterly_embree.cmake). The BVH's own ray does not include Embree; only the
// RTC_DEVICE_PROPERTY_TASKING_SYSTEM probe below and RTC_VERSION_STRING do.
RTC_NAMESPACE_USE

CCL_NAMESPACE_BEGIN

namespace {

// The one triangle of the self-test, in the plane z = 0: (0,0,0), (1,0,0), (0,1,0). The corners
// are in Embree's barycentric order (painterly/bvh/embree.h), and the ray's origin (0.25, 0.25, 1)
// lies inside it.
constexpr float SELFTEST_VERTICES[9] = {0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f};
constexpr uint32_t SELFTEST_TRIANGLES[3] = {0u, 1u, 2u};

// The object's transform: the 3x4 affine identity, row-major (painterly/bvh/embree.h).
constexpr float SELFTEST_OBJECT_TO_WORLD[12] = {
    1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f};

// The ray: from (0.25, 0.25, 1) with the unnormalized direction (0, 0, -2) (SPEC §4, §5). It
// meets the triangle after the distance 1 along the ray, which is t = 0.5 parametric along |d|
// = 2.
constexpr double SELFTEST_ORIGIN_X = 0.25;
constexpr double SELFTEST_ORIGIN_Y = 0.25;
constexpr double SELFTEST_ORIGIN_Z = 1.0;
constexpr double SELFTEST_DIRECTION_Z = -2.0;
// tnear = 0 includes the origin itself; tfar = infinity takes the whole ray.
constexpr double SELFTEST_TNEAR = 0.0;

}  // namespace

SelftestResult selftest_embree()
{
  SelftestResult result{};
  result.embree_version = RTC_VERSION_STRING;

  // The probe: the device's tasking system, which must be INTERNAL (0, see
  // RTC_DEVICE_PROPERTY_TASKING_SYSTEM). EMBREE_TASKING_SYSTEM=INTERNAL reports 0. This is the
  // only rtcNewDevice of this file, and it asks a question about the device itself, so it stays
  // outside painterly_bvh (selftest.h).
  {
    RTCDevice device = rtcNewDevice(nullptr);
    if (!device) {
      throw std::runtime_error("rtcNewDevice failed, Embree error " +
                               std::to_string(rtcGetDeviceError(nullptr)));
    }
    result.tasking_system = static_cast<int>(
        rtcGetDeviceProperty(device, RTC_DEVICE_PROPERTY_TASKING_SYSTEM));
    rtcReleaseDevice(device);
  }

  // The triangle goes through the BVH, exactly as a scene's meshes and objects do
  // (painterly/bvh/embree.h). One mesh, one object, and the mesh's only triangle is its prim 0.
  PainterlyEmbreeMeshInput mesh{};
  mesh.vertices = SELFTEST_VERTICES;
  mesh.num_vertices = 3;
  mesh.triangles = SELFTEST_TRIANGLES;
  mesh.num_triangles = 1;

  PainterlyEmbreeObjectInput object{};
  object.mesh = 0;
  object.object_to_world = SELFTEST_OBJECT_TO_WORLD;

  // Owns the scene until it is released, so a throw after the build cannot leak it.
  const std::unique_ptr<PainterlyEmbreeScene, void (*)(PainterlyEmbreeScene *)> scene(
      painterly_embree_scene_create(&mesh, 1, &object, 1), painterly_embree_scene_free);

  PainterlyRay ray;
  ray.o = make_double3(SELFTEST_ORIGIN_X, SELFTEST_ORIGIN_Y, SELFTEST_ORIGIN_Z);
  ray.d = make_double3(0.0, 0.0, SELFTEST_DIRECTION_Z);

  PainterlyIntersection isect;
  result.hit = painterly_embree_intersect_closest(
      scene.get(), ray, SELFTEST_TNEAR, std::numeric_limits<double>::infinity(), &isect);
  if (!result.hit) {
    // The scene has exactly one triangle under the ray, so a miss is a failure of the BVH or of
    // Embree, never an expected outcome. t and prim_id stay at their zero initialization.
    return result;
  }
  if (isect.kind != HIT_TRIANGLE) {
    throw std::runtime_error("selftest: the BVH returned kind " + std::to_string(isect.kind) +
                             ", not HIT_TRIANGLE");
  }
  // painterly_embree_intersect_closest widens Embree's float tfar to double, so the narrowing
  // here is exact.
  result.t = static_cast<float>(isect.t);
  result.prim_id = static_cast<unsigned>(isect.prim);
  return result;
}

CCL_NAMESPACE_END
