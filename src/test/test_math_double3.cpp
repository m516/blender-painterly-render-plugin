/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

// Bitwise tests of painterly/util/math_double3.h against smallpaint's Vec (T3.5), and exact tests
// of its 3x4 transform helpers and normal matrix (T3.21). No tolerance is used. The comparisons
// with smallpaint are std::memcmp of the two results, so -0.0 is distinguished from +0.0. Closed
// forms whose zeros may carry either sign are compared with ==.

#include <doctest/doctest.h>

#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <random>
#include <stdexcept>

#include "painterly/util/math_double3.h"
#include "painterly/util/types_double3.h"

#include "bitwise.h"
#include "smallpaint_ref.h"

CCL_NAMESPACE_BEGIN

namespace {

// Seed of std::mt19937_64. The C++ standard fixes the output sequence of this generator, so the
// inputs are the same on every platform. The value itself has no meaning.
constexpr std::uint64_t BITWISE_TEST_SEED = 0x5EED;
// Random input pairs per operation (T3.5 card).
constexpr int BITWISE_TEST_PAIRS = 100000;
// Exponents are drawn from [-EXPONENT_RANGE, EXPONENT_RANGE], so every component has magnitude in
// [2^-150, 2^151). Products of two components then lie in [2^-300, 2^302), and sums of three such
// products stay below 2^304. Every operation in these tests therefore stays inside double's normal
// range: none overflows, underflows or produces NaN, and the results are never subnormal.
constexpr int EXPONENT_RANGE = 150;
// Explicit fraction bits of an IEEE 754 binary64 significand (definition of the format).
constexpr int FRACTION_BITS = 52;

// Draws one nonzero double with a random sign and a magnitude spanning [2^-150, 2^151). Every step
// is exact (an integer conversion and a power-of-two scaling), so the values are the same on every
// platform.
double random_value(std::mt19937_64 &rng)
{
  const int top_bits = std::numeric_limits<std::uint64_t>::digits - FRACTION_BITS;
  const double fraction = std::ldexp(double(rng() >> top_bits), -FRACTION_BITS);
  const double mantissa = 1.0 + fraction;
  const int exponent = int(rng() % (2 * EXPONENT_RANGE + 1)) - EXPONENT_RANGE;
  const double sign = (rng() & 1) ? -1.0 : 1.0;
  return sign * std::ldexp(mantissa, exponent);
}

// Braced initialization evaluates the three draws left to right, so the sequence is fixed.
Triple draw_triple(std::mt19937_64 &rng)
{
  return {random_value(rng), random_value(rng), random_value(rng)};
}

}  // namespace

TEST_CASE("double3 +, -, scalar * and / are bitwise smallpaint Vec operators")
{
  std::mt19937_64 rng(BITWISE_TEST_SEED);
  int add_mismatches = 0;
  int sub_mismatches = 0;
  int scale_mismatches = 0;
  int div_mismatches = 0;
  for (int pair = 0; pair < BITWISE_TEST_PAIRS; pair++) {
    const Triple ta = draw_triple(rng);
    const Triple tb = draw_triple(rng);
    const double s = random_value(rng);
    const smallpaint_ref::Vec a = to_ref(ta);
    const smallpaint_ref::Vec b = to_ref(tb);
    const double3 da = to_double3(ta);
    const double3 db = to_double3(tb);
    add_mismatches += !same_bits(a + b, da + db);
    sub_mismatches += !same_bits(a - b, da - db);
    scale_mismatches += !same_bits(a * s, da * s);
    div_mismatches += !same_bits(a / s, da / s);
  }
  CHECK_EQ(add_mismatches, 0);
  CHECK_EQ(sub_mismatches, 0);
  CHECK_EQ(scale_mismatches, 0);
  CHECK_EQ(div_mismatches, 0);
}

TEST_CASE("double3 component-wise product is bitwise smallpaint Vec::mult")
{
  std::mt19937_64 rng(BITWISE_TEST_SEED);
  int mismatches = 0;
  for (int pair = 0; pair < BITWISE_TEST_PAIRS; pair++) {
    const Triple ta = draw_triple(rng);
    const Triple tb = draw_triple(rng);
    const smallpaint_ref::Vec a = to_ref(ta);
    const smallpaint_ref::Vec b = to_ref(tb);
    mismatches += !same_bits(a.mult(b), to_double3(ta) * to_double3(tb));
  }
  CHECK_EQ(mismatches, 0);
}

TEST_CASE("double3 dot, len and normalize are bitwise smallpaint dot, length and norm")
{
  std::mt19937_64 rng(BITWISE_TEST_SEED);
  int dot_mismatches = 0;
  int length_mismatches = 0;
  int norm_mismatches = 0;
  for (int pair = 0; pair < BITWISE_TEST_PAIRS; pair++) {
    const Triple ta = draw_triple(rng);
    const Triple tb = draw_triple(rng);
    const double3 da = to_double3(ta);
    const double3 db = to_double3(tb);
    // length() is not const in smallpaint, so a is not const. norm() also mutates its operand, so
    // it works on a fresh copy.
    smallpaint_ref::Vec a = to_ref(ta);
    const smallpaint_ref::Vec b = to_ref(tb);
    dot_mismatches += !same_bits(a.dot(b), dot(da, db));
    length_mismatches += !same_bits(a.length(), len(da));
    smallpaint_ref::Vec normalized = to_ref(ta);
    normalized.norm();
    norm_mismatches += !same_bits(normalized, normalize(da));
  }
  CHECK_EQ(dot_mismatches, 0);
  CHECK_EQ(length_mismatches, 0);
  CHECK_EQ(norm_mismatches, 0);
}

TEST_CASE("double3 cross product is bitwise smallpaint Vec operator%")
{
  std::mt19937_64 rng(BITWISE_TEST_SEED);
  int mismatches = 0;
  for (int pair = 0; pair < BITWISE_TEST_PAIRS; pair++) {
    const Triple ta = draw_triple(rng);
    const Triple tb = draw_triple(rng);
    // operator% takes its right operand by non-const reference, so b is not const.
    smallpaint_ref::Vec a = to_ref(ta);
    smallpaint_ref::Vec b = to_ref(tb);
    mismatches += !same_bits(a % b, cross(to_double3(ta), to_double3(tb)));
  }
  CHECK_EQ(mismatches, 0);
}

TEST_CASE("3x4 transform helpers are bitwise the row-by-row expressions of a row-major [A | t]")
{
  // camera.h's former hand-indexed reads: R v row by row from m[0..2], m[4..6] and m[8..10], and
  // t = (m[3], m[7], m[11]). The helpers must keep that operation order, so that camera rays keep
  // their bits.
  std::mt19937_64 rng(BITWISE_TEST_SEED);
  int direction_mismatches = 0;
  int translation_mismatches = 0;
  for (int pair = 0; pair < BITWISE_TEST_PAIRS; pair++) {
    double m[12];
    for (double &entry : m) {
      entry = random_value(rng);
    }
    const double3 v = to_double3(draw_triple(rng));
    const double3 got = painterly_transform_direction_3x4(m, v);
    direction_mismatches += !(same_bits(got.x, m[0] * v.x + m[1] * v.y + m[2] * v.z) &&
                              same_bits(got.y, m[4] * v.x + m[5] * v.y + m[6] * v.z) &&
                              same_bits(got.z, m[8] * v.x + m[9] * v.y + m[10] * v.z));
    const double3 t = painterly_transform_translation_3x4(m);
    translation_mismatches += !(same_bits(t.x, m[3]) && same_bits(t.y, m[7]) &&
                                same_bits(t.z, m[11]));
  }
  CHECK_EQ(direction_mismatches, 0);
  CHECK_EQ(translation_mismatches, 0);
}

TEST_CASE("painterly_normal_matrix is (A^-1)^T, keeps a mirrored normal's side, rejects det 0")
{
  // A = [[2, 0, 0], [0, -2, 0], [0.5, 0.5, 1]] with translation (1, 2, -3): an axis mirror
  // (det(A) = -4), a power-of-two scale and a dyadic shear. A^-1 = [[0.5, 0, 0], [0, -0.5, 0],
  // [-0.25, 0.25, 1]], so (A^-1)^T = [[0.5, 0, -0.25], [0, -0.5, 0.25], [0, 0, 1]]. Every
  // cofactor, det(A) and quotient is a dyadic rational with few bits, so binary64 forms each one
  // exactly.
  const float mirrored[12] = {
      2.0f, 0.0f, 0.0f, 1.0f, 0.0f, -2.0f, 0.0f, 2.0f, 0.5f, 0.5f, 1.0f, -3.0f};
  const double expected[9] = {0.5, 0.0, -0.25, 0.0, -0.5, 0.25, 0.0, 0.0, 1.0};
  double normal_matrix[9];
  painterly_normal_matrix(mirrored, normal_matrix);
  for (int i = 0; i < 9; i++) {
    CHECK(normal_matrix[i] == expected[i]);
  }

  // dot(N n, A d) = dot(n, d) for the object normal n = (0, 0, 1) and the three axes d: the mapped
  // normal stays on its side of the surface although A mirrors. Every value is exact.
  double a[12];
  for (int i = 0; i < 12; i++) {
    a[i] = mirrored[i];
  }
  const double3 n = make_double3(0.0, 0.0, 1.0);
  const double3 n_world = transform_direction_3x3(normal_matrix, n);
  for (const double3 d :
       {make_double3(1.0, 0.0, 0.0), make_double3(0.0, 1.0, 0.0), make_double3(0.0, 0.0, 1.0)})
  {
    CHECK(dot(n_world, painterly_transform_direction_3x4(a, d)) == dot(n, d));
  }

  // The identity maps to the identity, with +0.0 off the diagonal: the same bits as the float
  // identity matrix that transformed the corner normals before T3.21, so GlassSlabScene in
  // test_path.cpp keeps its results.
  const float identity[12] = {1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0};
  const double identity_3x3[9] = {1, 0, 0, 0, 1, 0, 0, 0, 1};
  painterly_normal_matrix(identity, normal_matrix);
  for (int i = 0; i < 9; i++) {
    CHECK(same_bits(normal_matrix[i], identity_3x3[i]));
  }

  // The y column is zero: A is singular and no normal matrix exists.
  const float singular[12] = {1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0};
  CHECK_THROWS_AS(painterly_normal_matrix(singular, normal_matrix), std::invalid_argument);
}

namespace {

// The offset e of the contraction canary: e = 2^-27, so e^2 = 2^-54 is half a unit in the last
// place of binary64 just below 1 (the spacing of [1/2, 1) is 2^-53).
constexpr double FMA_CANARY_OFFSET = 0x1p-27;

// dot() in a function of its own. ccl_never_inline (util/defines.h: noinline, __declspec(noinline)
// on MSVC) keeps it out of the test body, so it is compiled from its arguments, as kernel code is.
ccl_never_inline double fma_canary_dot(const double3 a, const double3 b)
{
  return dot(a, b);
}

}  // namespace

TEST_CASE("dot() is not contracted into fused multiply-adds (the -ffp-contract=off canary)")
{
  // docs/architecture.md, "Determinism contract": every build uses -ffp-contract=off, because a
  // fused multiply-add rounds once where smallpaint's expressions round twice. The bitwise tests
  // above cannot see a lost flag: smallpaint's Vec is compiled in this file with the same flags as
  // the kernel, so both sides would be contracted alike (M3 review panel #10). This test compares
  // dot() with a value derived by hand instead.
  //
  // With e = FMA_CANARY_OFFSET, a = (1 + e, 1 + e, 0) and b = (1 - e, -(1 - e), 0). Each component
  // is exact in binary64. dot(a, b) = a.x b.x + a.y b.y + a.z b.z, which C++ evaluates as
  // (a.x b.x + a.y b.y) + a.z b.z.
  // - Without contraction every product is rounded on its own. a.x b.x = 1 - e^2 = 1 - 2^-54 lies
  //   halfway between the neighbours 1 - 2^-53 and 1, and round-half-to-even gives 1. Likewise
  //   a.y b.y rounds to -1, and a.z b.z = +0. Then 1 + (-1) = +0 and +0 + +0 = +0.
  // - A contraction fuses a product into the sum that uses it. The inner sum then becomes
  //   fma(a.x, b.x, -1) = -2^-54 or fma(a.y, b.y, 1) = +2^-54, both exact. Fusing a.z b.z into the
  //   outer sum adds an exact 0 and changes nothing. The result is -2^-54 or +2^-54.
  // Measured on x86-64 for T3.24: GCC 13 (-ffp-contract=fast -mfma) and Clang 18
  // (-ffp-contract=on -mfma) both give -0x1p-54.
  //
  // The inputs are read through volatile, so the compiler cannot evaluate the products at compile
  // time (constant folding rounds each product, as uncontracted code does), and cannot see that
  // a.y b.y is -(a.x b.x) and cancel the two products before it fuses them.
  volatile double a_in[3] = {1.0 + FMA_CANARY_OFFSET, 1.0 + FMA_CANARY_OFFSET, 0.0};
  volatile double b_in[3] = {1.0 - FMA_CANARY_OFFSET, -(1.0 - FMA_CANARY_OFFSET), 0.0};
  const double3 a = make_double3(a_in[0], a_in[1], a_in[2]);
  const double3 b = make_double3(b_in[0], b_in[1], b_in[2]);
  CHECK(same_bits(fma_canary_dot(a, b), 0.0));
}

CCL_NAMESPACE_END
