// SPDX-License-Identifier: GPL-3.0-or-later
#include "selftest.h"

#include <algorithm>
#include <limits>
#include <stdexcept>

#include <embree4/rtcore.h>

// Embree's API lives in the namespace painterly_embree (EMBREE_API_NAMESPACE, see
// cmake/painterly_embree.cmake).
RTC_NAMESPACE_USE

CCL_NAMESPACE_BEGIN

namespace {

// Reads the device's Embree error, releases geom, scene and device if non-null, then throws. A
// free function rather than a lambda: [[noreturn]] appertains to the function type, which Clang
// rejects on a lambda's declarator.
[[noreturn]] void release_and_throw(RTCDevice device,
                                    RTCScene scene,
                                    RTCGeometry geom,
                                    const std::string &what)
{
  const RTCError error = rtcGetDeviceError(device);
  if (geom) {
    rtcReleaseGeometry(geom);
  }
  if (scene) {
    rtcReleaseScene(scene);
  }
  if (device) {
    rtcReleaseDevice(device);
  }
  throw std::runtime_error(what + ", Embree error " + std::to_string(error));
}

}  // namespace

SelftestResult selftest_embree()
{
  SelftestResult result{};
  result.embree_version = RTC_VERSION_STRING;

  RTCDevice device = rtcNewDevice(nullptr);
  if (!device) {
    throw std::runtime_error("rtcNewDevice failed, Embree error " +
                             std::to_string(rtcGetDeviceError(nullptr)));
  }
  // EMBREE_TASKING_SYSTEM=INTERNAL reports 0 (see RTC_DEVICE_PROPERTY_TASKING_SYSTEM).
  result.tasking_system = static_cast<int>(
      rtcGetDeviceProperty(device, RTC_DEVICE_PROPERTY_TASKING_SYSTEM));

  RTCScene scene = rtcNewScene(device);
  RTCGeometry geom = rtcNewGeometry(device, RTC_GEOMETRY_TYPE_TRIANGLE);

  // One triangle with vertices (0,0,0), (1,0,0), (0,1,0).
  float *vertices = static_cast<float *>(rtcSetNewGeometryBuffer(
      geom, RTC_BUFFER_TYPE_VERTEX, 0, RTC_FORMAT_FLOAT3, 3 * sizeof(float), 3));
  if (!vertices) {
    release_and_throw(device, scene, geom, "rtcSetNewGeometryBuffer (vertex) failed");
  }
  const float vertex_data[9] = {0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f};
  std::copy(vertex_data, vertex_data + 9, vertices);

  unsigned *indices = static_cast<unsigned *>(rtcSetNewGeometryBuffer(
      geom, RTC_BUFFER_TYPE_INDEX, 0, RTC_FORMAT_UINT3, 3 * sizeof(unsigned), 1));
  if (!indices) {
    release_and_throw(device, scene, geom, "rtcSetNewGeometryBuffer (index) failed");
  }
  indices[0] = 0;
  indices[1] = 1;
  indices[2] = 2;

  rtcCommitGeometry(geom);
  rtcAttachGeometry(scene, geom);
  rtcReleaseGeometry(geom);
  rtcCommitScene(scene);

  // The ray's direction is unnormalized on purpose: |d| = 2 (SPEC §4, §5).
  RTCRayHit rayhit{};
  rayhit.ray.org_x = 0.25f;
  rayhit.ray.org_y = 0.25f;
  rayhit.ray.org_z = 1.0f;
  rayhit.ray.dir_x = 0.0f;
  rayhit.ray.dir_y = 0.0f;
  rayhit.ray.dir_z = -2.0f;
  rayhit.ray.tnear = 0.0f;
  rayhit.ray.tfar = std::numeric_limits<float>::infinity();
  rayhit.ray.time = 0.0f;
  rayhit.ray.mask = -1;
  rayhit.ray.id = 0;
  rayhit.ray.flags = 0;
  rayhit.hit.geomID = RTC_INVALID_GEOMETRY_ID;
  rayhit.hit.primID = RTC_INVALID_GEOMETRY_ID;
  rayhit.hit.instID[0] = RTC_INVALID_GEOMETRY_ID;

  rtcIntersect1(scene, &rayhit);

  // Embree stores the parametric hit distance (SPEC §4, §5) in ray.tfar. Read the error state
  // before releasing the device.
  const RTCError error = rtcGetDeviceError(device);
  rtcReleaseScene(scene);
  rtcReleaseDevice(device);
  if (error != RTC_ERROR_NONE) {
    throw std::runtime_error("Embree intersection failed, error " + std::to_string(error));
  }

  result.hit = rayhit.hit.geomID != RTC_INVALID_GEOMETRY_ID;
  result.t = rayhit.ray.tfar;
  result.prim_id = rayhit.hit.primID;
  return result;
}

CCL_NAMESPACE_END
