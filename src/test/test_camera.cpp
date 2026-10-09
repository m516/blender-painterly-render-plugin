// SPDX-License-Identifier: GPL-3.0-or-later
// Tests of painterly/kernel/camera/camera.h (T3.8). The smallpaint camera is compared bit for bit
// with the oracle's camcr() and jitter, which smallpaint_camcr_ref.cpp holds. The perspective
// camera is compared with the analytic direction of a 90 degree pinhole. Bit patterns are compared
// with std::memcmp, so the -0.0 and +0.0 cases are told apart. The only comparison with a
// tolerance is the perspective one, and its bound is justified where it is defined.

#include <doctest/doctest.h>

#include <cmath>
#include <cstdint>
#include <cstring>

#include "painterly/kernel/camera/camera.h"

// The oracle's primary ray (smallpaint_camcr_ref.cpp). It is declared here, outside the painterly
// namespace, because the oracle is a separate translation unit.
namespace smallpaint_camcr_ref {
void primary_ray(int image_width,
                 int image_height,
                 std::uint32_t seed,
                 double jitter,
                 bool jittered,
                 int row,
                 int col,
                 int pass,
                 double origin[3],
                 double direction[3]);
}  // namespace smallpaint_camcr_ref

CCL_NAMESPACE_BEGIN

namespace {

// Seed of the stateless RNG for the bitwise test. Any value works, because the kernel and the
// oracle evaluate the same hash. The T3.4 oracle checks use --seed 7 as well.
constexpr std::uint32_t BITWISE_TEST_SEED = 7;
// Image sides of the bitwise test (T3.8 card): 64 x 64 and 400 x 400.
constexpr int BITWISE_TEST_SIDE_SMALL = 64;
constexpr int BITWISE_TEST_SIDE_LARGE = 400;
// Passes 0 to 3 (T3.8 card).
constexpr int BITWISE_TEST_PASSES = 4;
// smallpaint's jitter of 1/700 image-plane units: RND / 700 (smallpaint_painterly.cpp:291-292),
// which is the oracle's --jitter default. The kernel's camera jitter takes these units (types.h).
constexpr double SMALLPAINT_JITTER = 1.0 / 700.0;
// Both values of the `jittered` flag.
constexpr bool JITTERED_CASES[] = {false, true};

// The 90 degree pinhole of the perspective test (T3.8 card). Its side is 400 px, and its half
// side, 200 px, maps the image plane z = -1 onto [-1, 1], because tan(45 degrees) = 1.
constexpr int PINHOLE_SIDE = 400;
constexpr double PINHOLE_HALF_SIDE = PINHOLE_SIDE / 2;
// Relative bound of the perspective comparison. It is the float64 round-off bound of an analytic
// identity, which CLAUDE.md allows (rule 2). The kernel stores 1/200 rounded once and normalizes
// the direction, so each component of the result carries a few roundings of relative size
// 2^-53 (about 1.1e-16). The worst of the eight pixels measures 2.2e-16 (two ulps). The bound is
// about 4500 times that. Components of magnitude 0.0025 keep the same absolute error, so their
// relative error stays below the bound too.
constexpr double FLOAT64_ROUND_OFF_RTOL = 1e-12;

// True when a and b have the same IEEE 754 bit pattern.
bool same_bits(const double a, const double b)
{
  return std::memcmp(&a, &b, sizeof(double)) == 0;
}

// True when `actual` is within FLOAT64_ROUND_OFF_RTOL of `expected`, relative to |expected|.
bool near_float64(const double actual, const double expected)
{
  return std::fabs(actual - expected) <= FLOAT64_ROUND_OFF_RTOL * std::fabs(expected);
}

// Counts the rays of one smallpaint camera, over a side x side image, for every pass and both
// jitter cases, whose origin or direction differs bitwise from the oracle's.
int count_smallpaint_mismatches(const int side)
{
  KernelPainterlyData data{};
  data.cam.type = PAINTERLY_CAMERA_SMALLPAINT;
  data.cam.width = side;
  data.cam.height = side;
  data.cam.jitter = SMALLPAINT_JITTER;
  data.integrator.seed = BITWISE_TEST_SEED;
  PainterlyGlobalsCPU kg;
  kg.data = &data;

  int mismatches = 0;
  for (int pass = 0; pass < BITWISE_TEST_PASSES; pass++) {
    for (int row = 0; row < side; row++) {
      for (int col = 0; col < side; col++) {
        for (const bool jittered : JITTERED_CASES) {
          const PainterlyRay ray = painterly_camera_generate_ray(&kg, row, col, pass, jittered);
          double origin[3];
          double direction[3];
          smallpaint_camcr_ref::primary_ray(side,
                                            side,
                                            BITWISE_TEST_SEED,
                                            SMALLPAINT_JITTER,
                                            jittered,
                                            row,
                                            col,
                                            pass,
                                            origin,
                                            direction);
          const bool same = same_bits(ray.o.x, origin[0]) && same_bits(ray.o.y, origin[1]) &&
                            same_bits(ray.o.z, origin[2]) && same_bits(ray.d.x, direction[0]) &&
                            same_bits(ray.d.y, direction[1]) && same_bits(ray.d.z, direction[2]);
          mismatches += !same;
        }
      }
    }
  }
  return mismatches;
}

// Unit direction of pixel (row, col) of the pinhole, unjittered, with camera_to_world = identity
// (T3.8 card): normalize(((col + 0.5)/200 - 1, 1 - (row + 0.5)/200, -1)). The division by the
// norm is written out, so this does not reuse the kernel's normalize().
void pinhole_expected_direction(const int row, const int col, double direction[3])
{
  const double x = (col + PAINTERLY_RASTER_PIXEL_CENTRE) / PINHOLE_HALF_SIDE - 1.0;
  const double y = 1.0 - (row + PAINTERLY_RASTER_PIXEL_CENTRE) / PINHOLE_HALF_SIDE;
  const double z = -1.0;
  const double norm = std::sqrt(x * x + y * y + z * z);
  direction[0] = x / norm;
  direction[1] = y / norm;
  direction[2] = z / norm;
}

}  // namespace

TEST_CASE("smallpaint camera rays are bitwise the oracle's camcr() and jitter, passes 0-3")
{
  CHECK_EQ(count_smallpaint_mismatches(BITWISE_TEST_SIDE_SMALL), 0);
  CHECK_EQ(count_smallpaint_mismatches(BITWISE_TEST_SIDE_LARGE), 0);
}

TEST_CASE(
    "perspective camera matches the analytic 90 degree pinhole at the corner and centre pixels")
{
  // raster_to_camera maps the raster point (X, Y) to (X/200 - 1, 1 - Y/200, -1): X grows to the
  // right (camera +X), and Y grows downward (camera -Y), as the raster and camera axes of T5.1.
  // Row-major 4x4 with w = 1 (types.h).
  const double inv_half_side = 1.0 / PINHOLE_HALF_SIDE;
  const double raster_to_camera[4][4] = {
      {inv_half_side, 0.0, 0.0, -1.0},
      {0.0, -inv_half_side, 0.0, 1.0},
      {0.0, 0.0, 0.0, -1.0},
      {0.0, 0.0, 0.0, 1.0},
  };
  // Identity camera_to_world, row-major 3x4: R = I and t = 0.
  const double camera_to_world[3][4] = {
      {1.0, 0.0, 0.0, 0.0},
      {0.0, 1.0, 0.0, 0.0},
      {0.0, 0.0, 1.0, 0.0},
  };

  KernelPainterlyData data{};
  data.cam.type = PAINTERLY_CAMERA_PERSPECTIVE;
  data.cam.width = PINHOLE_SIDE;
  data.cam.height = PINHOLE_SIDE;
  data.cam.jitter = 0.0;
  std::memcpy(data.cam.raster_to_camera, raster_to_camera, sizeof(raster_to_camera));
  std::memcpy(data.cam.camera_to_world, camera_to_world, sizeof(camera_to_world));
  PainterlyGlobalsCPU kg;
  kg.data = &data;

  // Corner pixels (tangents +-0.9975) and the four pixels around the centre (tangents +-0.0025).
  const int last = PINHOLE_SIDE - 1;
  const int mid = PINHOLE_SIDE / 2;
  const int pixels[][2] = {{0, 0},
                           {0, last},
                           {last, 0},
                           {last, last},
                           {mid - 1, mid - 1},
                           {mid - 1, mid},
                           {mid, mid - 1},
                           {mid, mid}};
  for (const auto &pixel : pixels) {
    const int row = pixel[0];
    const int col = pixel[1];
    const PainterlyRay ray = painterly_camera_generate_ray(&kg, row, col, 0, false);
    double expected[3];
    pinhole_expected_direction(row, col, expected);
    CHECK_EQ(ray.o.x, 0.0);
    CHECK_EQ(ray.o.y, 0.0);
    CHECK_EQ(ray.o.z, 0.0);
    CHECK(near_float64(ray.d.x, expected[0]));
    CHECK(near_float64(ray.d.y, expected[1]));
    CHECK(near_float64(ray.d.z, expected[2]));
  }
}

CCL_NAMESPACE_END
