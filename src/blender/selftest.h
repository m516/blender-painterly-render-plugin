// SPDX-License-Identifier: GPL-3.0-or-later
// Embree self-test for the _painterly module: proves that the static, namespaced Embree works.
#pragma once

#include <string>

// Until the Cycles util/ headers are vendored (M3), these macros are defined here.
#ifndef CCL_NAMESPACE_BEGIN
#  define CCL_NAMESPACE_BEGIN namespace painterly {
#  define CCL_NAMESPACE_END }
#endif

CCL_NAMESPACE_BEGIN

struct SelftestResult {
  std::string embree_version;
  // RTC_DEVICE_PROPERTY_TASKING_SYSTEM: 0 internal, 1 TBB, 2 PPL.
  int tasking_system;
  bool hit;
  float t;
  unsigned prim_id;
};

// Traces one ray from (0.25, 0.25, 1) with the unnormalized direction (0, 0, -2) at one triangle
// in the plane z = 0. t is parametric along the unnormalized direction (SPEC §4, §5), so the
// expected hit has t = 0.5.
SelftestResult selftest_embree();

CCL_NAMESPACE_END
