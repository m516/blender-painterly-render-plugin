// SPDX-License-Identifier: GPL-3.0-or-later
// Compile check of the kernel data layout (T3.5). The two kernel headers are the first includes of
// this translation unit, so a header that is not self-contained fails here. Every kernel struct is
// plain-old-data ("Plain-old-data only", painterly/kernel/types.h): standard layout and trivially
// copyable. Sizes are deliberately not asserted.

#include "painterly/kernel/types.h"

#include "painterly/kernel/globals.h"

#include <doctest/doctest.h>

#include <cstring>
#include <type_traits>

CCL_NAMESPACE_BEGIN

// painterly/util/types_double3.h
static_assert(std::is_standard_layout_v<double3>);
static_assert(std::is_trivially_copyable_v<double3>);

// painterly/kernel/types.h
static_assert(std::is_standard_layout_v<KernelPainterlySpotProfile>);
static_assert(std::is_trivially_copyable_v<KernelPainterlySpotProfile>);
static_assert(std::is_standard_layout_v<KernelPainterlyAnalytic>);
static_assert(std::is_trivially_copyable_v<KernelPainterlyAnalytic>);
static_assert(std::is_standard_layout_v<KernelPainterlyLobe>);
static_assert(std::is_trivially_copyable_v<KernelPainterlyLobe>);
static_assert(std::is_standard_layout_v<KernelPainterlyMaterial>);
static_assert(std::is_trivially_copyable_v<KernelPainterlyMaterial>);
static_assert(std::is_standard_layout_v<KernelPainterlyCamera>);
static_assert(std::is_trivially_copyable_v<KernelPainterlyCamera>);
static_assert(std::is_standard_layout_v<KernelPainterlyIntegrator>);
static_assert(std::is_trivially_copyable_v<KernelPainterlyIntegrator>);
static_assert(std::is_standard_layout_v<KernelPainterlySun>);
static_assert(std::is_trivially_copyable_v<KernelPainterlySun>);
static_assert(std::is_standard_layout_v<KernelPainterlyBackground>);
static_assert(std::is_trivially_copyable_v<KernelPainterlyBackground>);
static_assert(std::is_standard_layout_v<KernelPainterlyData>);
static_assert(std::is_trivially_copyable_v<KernelPainterlyData>);
static_assert(std::is_standard_layout_v<PainterlyPathResult>);
static_assert(std::is_trivially_copyable_v<PainterlyPathResult>);

// painterly/kernel/globals.h
static_assert(std::is_standard_layout_v<KernelPainterlyObject>);
static_assert(std::is_trivially_copyable_v<KernelPainterlyObject>);
static_assert(std::is_standard_layout_v<KernelPainterlyMesh>);
static_assert(std::is_trivially_copyable_v<KernelPainterlyMesh>);
static_assert(std::is_standard_layout_v<PainterlyGlobalsCPU>);
static_assert(std::is_trivially_copyable_v<PainterlyGlobalsCPU>);
static_assert(std::is_standard_layout_v<PainterlyRay>);
static_assert(std::is_trivially_copyable_v<PainterlyRay>);
static_assert(std::is_standard_layout_v<PainterlyIntersection>);
static_assert(std::is_trivially_copyable_v<PainterlyIntersection>);

TEST_CASE("kernel data survives a byte copy")
{
  // A trivially copyable struct keeps every field through memcpy, the way device data is
  // transferred.
  KernelPainterlyData original{};
  original.cam.width = 640;
  original.cam.height = 480;
  original.integrator.chain = CHAIN_LANE;
  original.integrator.lane_length = 4;
  original.background.num_suns = 1;

  KernelPainterlyData copy{};
  std::memcpy(&copy, &original, sizeof(KernelPainterlyData));
  CHECK_EQ(copy.cam.width, 640);
  CHECK_EQ(copy.cam.height, 480);
  CHECK(copy.integrator.chain == CHAIN_LANE);
  CHECK_EQ(copy.integrator.lane_length, 4);
  CHECK_EQ(copy.background.num_suns, 1);
}

CCL_NAMESPACE_END
