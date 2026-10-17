/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* Shared helpers of the bitwise tests (TQ.1 F16): bit-pattern comparison, and draws from
 * std::mt19937_64 that are the same on every platform. The C++ standard fixes the output sequence
 * of std::mt19937_64, and each helper turns that output into a value with exact steps only (masks,
 * integer conversions and power-of-two scaling), so a seed gives the same inputs everywhere.
 *
 * Several test files of the one painterly_tests executable include this header. Everything in it
 * lives in an unnamed namespace, so each translation unit gets its own copy with internal linkage,
 * like the reference code of smallpaint_ref.h, whose Vec the overloads there convert. The
 * functions are inline, so a file that does not call one gets no unused-function warning. */

#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <random>

#include "painterly/util/types_double3.h"

CCL_NAMESPACE_BEGIN

namespace {

/* Significand precision of binary64 (53 bits, the definition of the format). unit_double()
 * draws the top 53 bits of one 64-bit output and scales them by a power of two, so every draw is
 * exact. */
constexpr int DOUBLE_SIGNIFICAND_BITS = 53;
/* draw_index() draws from [0, INDEX_LIMIT), so every index is a non-negative int. */
constexpr std::uint64_t INDEX_LIMIT = std::uint64_t(1) << 31;

/* Three doubles: a vector of the tests before it becomes a double3 or a smallpaint Vec. */
struct Triple {
  double x, y, z;
};

/* True when a and b have the same IEEE 754 bit pattern. This is memcmp, not ==, because == treats
 * -0.0 and +0.0 as equal. */
inline bool same_bits(const double a, const double b)
{
  return std::memcmp(&a, &b, sizeof(double)) == 0;
}

/* True when every component of a and b has the same bit pattern. */
inline bool same_vec(const double3 a, const double3 b)
{
  return same_bits(a.x, b.x) && same_bits(a.y, b.y) && same_bits(a.z, b.z);
}

/* Uniform in [0, 1). The top DOUBLE_SIGNIFICAND_BITS bits of one 64-bit draw, scaled by a power of
 * two, so the value is exact on every platform. */
inline double unit_double(std::mt19937_64 &rng)
{
  constexpr int dropped_bits = std::numeric_limits<std::uint64_t>::digits -
                               DOUBLE_SIGNIFICAND_BITS;
  return std::ldexp(double(rng() >> dropped_bits), -DOUBLE_SIGNIFICAND_BITS);
}

/* lo + (hi - lo) * u with u in [0, 1). Plain IEEE arithmetic, so the same on every platform. */
inline double uniform(std::mt19937_64 &rng, const double lo, const double hi)
{
  return lo + (hi - lo) * unit_double(rng);
}

/* Braced initialization evaluates the three draws left to right, so the sequence is fixed. */
inline Triple uniform_triple(std::mt19937_64 &rng, const double lo, const double hi)
{
  return {uniform(rng, lo, hi), uniform(rng, lo, hi), uniform(rng, lo, hi)};
}

/* An index in [0, INDEX_LIMIT): the low 31 bits of one 64-bit draw. */
inline int draw_index(std::mt19937_64 &rng)
{
  return int(rng() & (INDEX_LIMIT - 1));
}

inline double3 to_double3(const Triple &t)
{
  return make_double3(t.x, t.y, t.z);
}

}  // namespace

CCL_NAMESPACE_END
