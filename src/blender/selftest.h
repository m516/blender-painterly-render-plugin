/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

// Embree self-test for the _painterly module: proves that the static, namespaced Embree works, and
// that the triangle path of painterly_bvh (painterly_embree_scene_create +
// painterly_embree_intersect_closest) returns the hit the kernel relies on (TQ.1 F12, D34).
#pragma once

#include <string>

CCL_NAMESPACE_BEGIN

struct SelftestResult {
  std::string embree_version;
  // RTC_DEVICE_PROPERTY_TASKING_SYSTEM: 0 internal, 1 TBB, 2 PPL.
  int tasking_system;
  bool hit;
  // The parametric distance along the unnormalized direction (SPEC §4, §5). Embree stores it in
  // RTCRayHit::ray.tfar, a float, and painterly_embree_intersect_closest widens it to double, so
  // narrowing it back to float here is exact.
  float t;
  unsigned prim_id;
};

// Traces one ray from (0.25, 0.25, 1) with the unnormalized direction (0, 0, -2) at one triangle
// in the plane z = 0, through painterly/bvh/embree.h: the mesh and the object go to
// painterly_embree_scene_create, and the ray to painterly_embree_intersect_closest. t is
// parametric along the unnormalized direction (SPEC §4, §5), so the expected hit has t = 0.5.
//
// The RTC_DEVICE_PROPERTY_TASKING_SYSTEM probe keeps its own rtcNewDevice(nullptr): it asks a
// question about the device itself, and painterly/bvh/embree.h exposes no device handle (its
// device is private to embree.cpp, which is not in this card's files). The probe therefore stays
// independent of painterly_bvh, and only the ray goes through it.
SelftestResult selftest_embree();

CCL_NAMESPACE_END
