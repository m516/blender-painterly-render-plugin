// SPDX-License-Identifier: GPL-3.0-or-later
// Unit tests for the vendored Cycles util/ (T3.2): hash_uint4 against the oracle's copy, exact
// inverse transforms, and the float3 helpers. Every comparison is exact; there is no tolerance.

#include <doctest/doctest.h>

#include <cstdint>
#include <limits>
#include <random>

#include "util/hash.h"
#include "util/math.h"
#include "util/transform.h"
#include "util/types.h"

// The oracle's copy of the hash functions (src/app/smallpaint_oracle_hash.h), in its own namespace
// so that both copies compile in this translation unit, as test_sampler.cpp does. <cstdint> is
// already included above, so the header adds no standard-library declarations inside the
// namespace.
namespace smallpaint_oracle {
#include "app/smallpaint_oracle_hash.h"
}  // namespace smallpaint_oracle

CCL_NAMESPACE_BEGIN

namespace {

// Seed of std::mt19937. The raw generator output is specified exactly by the C++ standard, so the
// test inputs are the same on every platform. The value itself has no meaning.
constexpr std::uint32_t HASH_TEST_SEED = 0x5EED;
// Random hash_uint4 inputs compared with the oracle (T3.2 card).
constexpr int HASH_TEST_SAMPLES = 10000;

// Checks that t equals transform_identity() component by component under float ==. Comparison is
// not memcmp: a negative scale can give -0.0 entries, and IEEE 754 defines -0.0 == +0.0.
void check_equals_identity(const Transform &t)
{
  const Transform identity = transform_identity();
  const float4 rows[3] = {t.x, t.y, t.z};
  const float4 expected[3] = {identity.x, identity.y, identity.z};
  for (int row = 0; row < 3; row++) {
    for (int col = 0; col < 4; col++) {
      CHECK(rows[row][col] == expected[row][col]);
    }
  }
}

}  // namespace

TEST_CASE("hash_uint4 equals the oracle copy on fixed and random inputs")
{
  // Fixed corner inputs first, then HASH_TEST_SAMPLES draws from the seeded generator.
  const std::uint32_t max = std::numeric_limits<std::uint32_t>::max();
  const std::uint32_t corners[2][4] = {{0, 0, 0, 0}, {max, max, max, max}};
  int mismatches = 0;
  for (const auto &corner : corners) {
    mismatches += hash_uint4(corner[0], corner[1], corner[2], corner[3]) !=
                  smallpaint_oracle::hash_uint4(corner[0], corner[1], corner[2], corner[3]);
  }

  std::mt19937 generator(HASH_TEST_SEED);
  for (int sample = 0; sample < HASH_TEST_SAMPLES; sample++) {
    const std::uint32_t kx = generator();
    const std::uint32_t ky = generator();
    const std::uint32_t kz = generator();
    const std::uint32_t kw = generator();
    mismatches += hash_uint4(kx, ky, kz, kw) != smallpaint_oracle::hash_uint4(kx, ky, kz, kw);
  }
  CHECK(mismatches == 0);
}

TEST_CASE("transform_inverse is exact for invertible matrices with power-of-two entries")
{
  // diag(-1, 1, 1) with translation (-3, 0, 0): its inverse has -0.0 entries.
  Transform sign_flip;
  sign_flip.x = make_float4(-1.0f, 0.0f, 0.0f, -3.0f);
  sign_flip.y = make_float4(0.0f, 1.0f, 0.0f, 0.0f);
  sign_flip.z = make_float4(0.0f, 0.0f, 1.0f, 0.0f);

  // An axis permutation with power-of-two scales of either sign, and an integer translation.
  // Its 3x3 part has determinant -4.
  Transform permuted;
  permuted.x = make_float4(0.0f, -2.0f, 0.0f, -3.0f);
  permuted.y = make_float4(4.0f, 0.0f, 0.0f, 5.0f);
  permuted.z = make_float4(0.0f, 0.0f, -0.5f, 7.0f);

  // Non-uniform scales of either sign and a translation.
  Transform scaled;
  scaled.x = make_float4(2.0f, 0.0f, 0.0f, 0.5f);
  scaled.y = make_float4(0.0f, -4.0f, 0.0f, -1.0f);
  scaled.z = make_float4(0.0f, 0.0f, 0.25f, 2.0f);

  for (const Transform &m : {sign_flip, permuted, scaled}) {
    check_equals_identity(transform_inverse(m) * m);
  }
}

TEST_CASE("float3 helpers: make_float3, dot and normalize")
{
  const float3 a = make_float3(1.0f, 2.0f, 3.0f);
  CHECK(a.x == 1.0f);
  CHECK(a.y == 2.0f);
  CHECK(a.z == 3.0f);
  CHECK(dot(a, make_float3(4.0f, 5.0f, 6.0f)) == 32.0f);
  CHECK(dot(make_float3(1.0f, 0.0f, 0.0f), make_float3(0.0f, 1.0f, 0.0f)) == 0.0f);

  // |(0, 0, 2)| = 2 is exact in float, so the normalized vector is exact too.
  const float3 n = normalize(make_float3(0.0f, 0.0f, 2.0f));
  CHECK(n.x == 0.0f);
  CHECK(n.y == 0.0f);
  CHECK(n.z == 1.0f);
}

CCL_NAMESPACE_END
