// SPDX-License-Identifier: GPL-3.0-or-later
// Bitwise tests of painterly/util/math_double3.h against smallpaint's Vec (T3.5). Every comparison
// is std::memcmp of the two results, so no tolerance is used and -0.0 is distinguished from +0.0.

#include <doctest/doctest.h>

#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <random>

#include "painterly/util/math_double3.h"
#include "painterly/util/types_double3.h"

// smallpaint's Vec, copied verbatim from
// third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp:43-55. clang-format is off
// so that the copy stays byte-identical to the source, tabs included.
// clang-format off
namespace smallpaint_ref {
struct Vec {
	double x, y, z;
	Vec(double x0 = 0, double y0 = 0, double z0 = 0) { x = x0; y = y0; z = z0; }
	Vec operator+(const Vec &b) const { return Vec(x + b.x, y + b.y, z + b.z); }
	Vec operator-(const Vec &b) const { return Vec(x - b.x, y - b.y, z - b.z); }
	Vec operator*(double b) const { return Vec(x*b, y*b, z*b); }
	Vec operator/(double b) const { return Vec(x / b, y / b, z / b); }
	Vec mult(const Vec &b) const { return Vec(x*b.x, y*b.y, z*b.z); }
	Vec& norm() { return *this = *this * (1 / sqrt(x*x + y*y + z*z)); }
	double length() { return sqrt(x*x + y*y + z*z); }
	double dot(const Vec &b) const { return x*b.x + y*b.y + z*b.z; }
	Vec operator%(Vec &b) { return Vec(y*b.z - z*b.y, z*b.x - x*b.z, x*b.y - y*b.x); }
};
}  // namespace smallpaint_ref
// clang-format on

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

struct Triple {
  double x, y, z;
};

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

smallpaint_ref::Vec to_ref(const Triple &t)
{
  return smallpaint_ref::Vec(t.x, t.y, t.z);
}

double3 to_double3(const Triple &t)
{
  return make_double3(t.x, t.y, t.z);
}

// True when a and b have the same IEEE 754 bit pattern. This is memcmp, not ==, because == treats
// -0.0 and +0.0 as equal.
bool same_bits(const double a, const double b)
{
  return std::memcmp(&a, &b, sizeof(double)) == 0;
}

bool same_bits(const smallpaint_ref::Vec &ref, const double3 &got)
{
  return same_bits(ref.x, got.x) && same_bits(ref.y, got.y) && same_bits(ref.z, got.z);
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

CCL_NAMESPACE_END
