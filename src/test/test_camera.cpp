/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

// Tests of painterly/kernel/camera/camera.h (T3.8, T3.24). The smallpaint camera is compared bit
// for bit with the oracle's camcr() and jitter, through smallpaint_camcr_ref.cpp, on square and
// non-square images. The perspective camera is compared with the analytic direction of a 90
// degree pinhole. Under a permuted, scaled and translated camera_to_world, the orthographic and
// perspective rays are compared exactly with values derived by hand, unjittered and jittered.
// Bit patterns are compared with std::memcmp, so the -0.0 and +0.0 cases are told apart, except
// where a comment says why == is used. The only comparison with a tolerance is the pinhole one,
// and its bound is justified where it is defined.

#include <doctest/doctest.h>

#include <cmath>
#include <cstdint>
#include <cstring>

#include "painterly/kernel/camera/camera.h"

#include "bitwise.h"

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
// Non-square images of the bitwise test, NON_SQUARE_LONG_SIDE x NON_SQUARE_SHORT_SIDE and its
// transpose (M3 review panel #12). In smallpaint's camera w (width) scales the row term and h
// (height) the column term, and fovy = (h / w) fovx (SPEC §7). On a square image w = h and
// fovy = fovx, so a camera that swapped the two roles would still pass the square cases.
constexpr int NON_SQUARE_LONG_SIDE = 64;
constexpr int NON_SQUARE_SHORT_SIDE = 32;

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

// True when `actual` is within FLOAT64_ROUND_OFF_RTOL of `expected`, relative to |expected|.
bool near_float64(const double actual, const double expected)
{
  return std::fabs(actual - expected) <= FLOAT64_ROUND_OFF_RTOL * std::fabs(expected);
}

// Counts the rays of one smallpaint camera, over a width x height image, for every pass and both
// jitter cases, whose origin or direction differs bitwise from the oracle's. Rows run over the
// height and columns over the width (SPEC §0).
int count_smallpaint_mismatches(const int width, const int height)
{
  KernelPainterlyData data{};
  data.cam.type = PAINTERLY_CAMERA_SMALLPAINT;
  data.cam.width = width;
  data.cam.height = height;
  data.cam.jitter = SMALLPAINT_JITTER;
  data.integrator.seed = BITWISE_TEST_SEED;
  PainterlyGlobalsCPU kg;
  kg.data = &data;

  int mismatches = 0;
  for (int pass = 0; pass < BITWISE_TEST_PASSES; pass++) {
    for (int row = 0; row < height; row++) {
      for (int col = 0; col < width; col++) {
        for (const bool jittered : JITTERED_CASES) {
          const PainterlyRay ray = painterly_camera_generate_ray(&kg, row, col, pass, jittered);
          double origin[3];
          double direction[3];
          smallpaint_camcr_ref::primary_ray(width,
                                            height,
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

// The permuted camera of the orthographic and perspective tests (TQ.1 F19). Every matrix entry is
// dyadic: the expected rays below are derived by hand and are exact.
// An image of PERMUTED_WIDTH x PERMUTED_HEIGHT pixels, PERMUTED_PIXEL_SIZE camera units each,
// centred on the camera axis: raster_to_camera maps the raster point (X, Y) to
// Pc = (PERMUTED_PIXEL_SIZE X - PERMUTED_HALF_WIDTH, PERMUTED_HALF_HEIGHT - PERMUTED_PIXEL_SIZE Y,
// -1). Not square, so that a swap of the raster axes changes the rays.
constexpr int PERMUTED_WIDTH = 8;
constexpr int PERMUTED_HEIGHT = 4;
constexpr double PERMUTED_PIXEL_SIZE = 0.25;
constexpr double PERMUTED_HALF_WIDTH = PERMUTED_PIXEL_SIZE * PERMUTED_WIDTH / 2;
constexpr double PERMUTED_HALF_HEIGHT = PERMUTED_PIXEL_SIZE * PERMUTED_HEIGHT / 2;
// camera_to_world = [PERMUTED_CAMERA_SCALE * P | PERMUTED_TRANSLATION]. P is the signed axis
// permutation with rows (0, 0, -1), (1, 0, 0) and (0, -1, 0): camera +X goes to world +Y, +Y to
// world -Z, and the forward axis -Z to world +X. It is a rotation (det P = 1) that moves every
// axis, and P is not symmetric, so a skipped, transposed or misindexed rotation changes the rays.
// The scale 2 is a power of two, which normalize() divides out exactly: a missing normalize leaves
// |d| = 2. The translation is integer.
constexpr double PERMUTED_CAMERA_SCALE = 2.0;
constexpr double PERMUTED_TRANSLATION[3] = {3.0, -5.0, 2.0};
// Jitter in raster pixels (types.h). A power of two, so rng_signed * jitter is exact.
constexpr double PERMUTED_JITTER = 0.25;

// The device data of the permuted camera of the given type.
KernelPainterlyData permuted_camera(const int type)
{
  const double s = PERMUTED_PIXEL_SIZE;
  const double raster_to_camera[4][4] = {
      {s, 0.0, 0.0, -PERMUTED_HALF_WIDTH},
      {0.0, -s, 0.0, PERMUTED_HALF_HEIGHT},
      {0.0, 0.0, 0.0, -1.0},
      {0.0, 0.0, 0.0, 1.0},
  };
  const double k = PERMUTED_CAMERA_SCALE;
  const double *t = PERMUTED_TRANSLATION;
  const double camera_to_world[3][4] = {
      {0.0, 0.0, -k, t[0]},
      {k, 0.0, 0.0, t[1]},
      {0.0, -k, 0.0, t[2]},
  };

  KernelPainterlyData data{};
  data.cam.type = type;
  data.cam.width = PERMUTED_WIDTH;
  data.cam.height = PERMUTED_HEIGHT;
  data.cam.jitter = PERMUTED_JITTER;
  data.integrator.seed = BITWISE_TEST_SEED;
  std::memcpy(data.cam.raster_to_camera, raster_to_camera, sizeof(raster_to_camera));
  std::memcpy(data.cam.camera_to_world, camera_to_world, sizeof(camera_to_world));
  return data;
}

// The ray of the permuted camera through the raster point (X, Y), derived by hand. X and Y lie
// within PERMUTED_JITTER of a pixel centre k + 0.5, so X > 0, Y > 0, and Pc has no zero
// component: Pc.x = 0 would need X = 4, and Pc.y = 0 would need Y = 2.
// - Pc. The kernel forms px = s X + 0 Y - PERMUTED_HALF_WIDTH. s X is exact (s is a power of two)
//   and 0 Y = +0 adds nothing to it, so px is s X - PERMUTED_HALF_WIDTH rounded once, as below;
//   py likewise. pz = -1 and pw = 1, so the division changes nothing. At the unjittered raster
//   points (col + 0.5, row + 0.5) every value is exact.
// - P v for a vector v without zero components: each row of P has one nonzero entry, so the other
//   two products are zeros, and adding a zero to a nonzero value leaves it unchanged. P v is
//   (-v.z, v.x, -v.y) exactly, and the scale 2 multiplies it exactly.
// - Perspective: the origin is t, and the direction is normalize(2 P normalize(Pc)), which equals
//   normalize(P normalize(Pc)) bit for bit: the factor 2 scales the sum of squares by 4 and its
//   square root by 2, exactly, so the reciprocal halves and the products are unchanged.
// - Orthographic: the origin is 2 P (Pc.x, Pc.y, 0) + t = (t.x, t.y + 2 Pc.x, t.z - 2 Pc.y), whose
//   first component adds only zeros to t.x, and the direction is normalize(2 P (0, 0, -1)) =
//   normalize((2, 0, 0)) = (1, 0, 0). The kernel's zero components of that direction are sums of
//   zero products and may be -0.0, so the callers compare with ==.
PainterlyRay permuted_expected_ray(const int type, const double X, const double Y)
{
  const double3 point_cam = make_double3(PERMUTED_PIXEL_SIZE * X - PERMUTED_HALF_WIDTH,
                                         PERMUTED_HALF_HEIGHT - PERMUTED_PIXEL_SIZE * Y,
                                         -1.0);
  const double k = PERMUTED_CAMERA_SCALE;
  const double *t = PERMUTED_TRANSLATION;
  if (type == PAINTERLY_CAMERA_PERSPECTIVE) {
    const double3 v = normalize(point_cam);
    return PainterlyRay{make_double3(t[0], t[1], t[2]), normalize(make_double3(-v.z, v.x, -v.y))};
  }
  return PainterlyRay{make_double3(t[0], t[1] + k * point_cam.x, t[2] - k * point_cam.y),
                      make_double3(1.0, 0.0, 0.0)};
}

// Counts the rays of the permuted camera of the given type, over every pixel, passes 0 to 3 and
// both jitter cases, that differ from permuted_expected_ray. A jittered ray must be the ray
// through the raster point (col + 0.5 + jx, row + 0.5 + jy), summed in the kernel's order. jx is
// rng_signed(seed, PURPOSE_JITTER_X, 0, row, col, pass) times the jitter, and jy likewise with
// PURPOSE_JITTER_Y (SPEC §2, §7). Components are compared with ==, so a NaN counts as a mismatch
// and the sign of a zero does not (see permuted_expected_ray).
int count_permuted_mismatches(const int type)
{
  KernelPainterlyData data = permuted_camera(type);
  PainterlyGlobalsCPU kg;
  kg.data = &data;

  int mismatches = 0;
  for (int pass = 0; pass < BITWISE_TEST_PASSES; pass++) {
    for (int row = 0; row < PERMUTED_HEIGHT; row++) {
      for (int col = 0; col < PERMUTED_WIDTH; col++) {
        for (const bool jittered : JITTERED_CASES) {
          double jx = 0.0;
          double jy = 0.0;
          if (jittered) {
            jx = painterly_rng_signed(
                     BITWISE_TEST_SEED, PURPOSE_JITTER_X, 0, uint(row), uint(col), uint(pass)) *
                 PERMUTED_JITTER;
            jy = painterly_rng_signed(
                     BITWISE_TEST_SEED, PURPOSE_JITTER_Y, 0, uint(row), uint(col), uint(pass)) *
                 PERMUTED_JITTER;
          }
          const PainterlyRay expected = permuted_expected_ray(
              type,
              col + PAINTERLY_RASTER_PIXEL_CENTRE + jx,
              row + PAINTERLY_RASTER_PIXEL_CENTRE + jy);
          const PainterlyRay ray = painterly_camera_generate_ray(&kg, row, col, pass, jittered);
          const bool same = ray.o.x == expected.o.x && ray.o.y == expected.o.y &&
                            ray.o.z == expected.o.z && ray.d.x == expected.d.x &&
                            ray.d.y == expected.d.y && ray.d.z == expected.d.z;
          mismatches += !same;
        }
      }
    }
  }
  return mismatches;
}

}  // namespace

TEST_CASE("smallpaint camera rays are bitwise the oracle's camcr() and jitter, passes 0-3")
{
  CHECK_EQ(count_smallpaint_mismatches(BITWISE_TEST_SIDE_SMALL, BITWISE_TEST_SIDE_SMALL), 0);
  CHECK_EQ(count_smallpaint_mismatches(BITWISE_TEST_SIDE_LARGE, BITWISE_TEST_SIDE_LARGE), 0);
  CHECK_EQ(count_smallpaint_mismatches(NON_SQUARE_LONG_SIDE, NON_SQUARE_SHORT_SIDE), 0);
  CHECK_EQ(count_smallpaint_mismatches(NON_SQUARE_SHORT_SIDE, NON_SQUARE_LONG_SIDE), 0);
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

TEST_CASE("orthographic camera rays under a permuted, scaled, translated camera_to_world")
{
  CHECK_EQ(count_permuted_mismatches(PAINTERLY_CAMERA_ORTHOGRAPHIC), 0);
}

TEST_CASE("perspective camera rays under a permuted, scaled, translated camera_to_world")
{
  CHECK_EQ(count_permuted_mismatches(PAINTERLY_CAMERA_PERSPECTIVE), 0);
}

CCL_NAMESPACE_END
