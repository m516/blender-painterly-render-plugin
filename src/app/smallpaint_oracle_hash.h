/* SPDX-FileCopyrightText: 2011-2022 Blender Foundation
 *
 * SPDX-License-Identifier: Apache-2.0 */

// Modified by the Painterly project: standalone copy for the oracle.
// Source: Blender v5.2.2 intern/cycles/util/hash.h, the lookup3 macros and hash_uint2..4.
// Only ccl_device_inline -> inline and uint -> uint32_t were changed (hash_uint is not copied).

#pragma once

#include <cstdint>

// clang-format off
/* ***** Jenkins Lookup3 Hash Functions ***** */

/* Source: http://burtleburtle.net/bob/c/lookup3.c */

#define rot(x, k) (((x) << (k)) | ((x) >> (32 - (k))))

#define mix(a, b, c) \
  { \
    a -= c; \
    a ^= rot(c, 4); \
    c += b; \
    b -= a; \
    b ^= rot(a, 6); \
    a += c; \
    c -= b; \
    c ^= rot(b, 8); \
    b += a; \
    a -= c; \
    a ^= rot(c, 16); \
    c += b; \
    b -= a; \
    b ^= rot(a, 19); \
    a += c; \
    c -= b; \
    c ^= rot(b, 4); \
    b += a; \
  } \
  ((void)0)

#define final(a, b, c) \
  { \
    c ^= b; \
    c -= rot(b, 14); \
    a ^= c; \
    a -= rot(c, 11); \
    b ^= a; \
    b -= rot(a, 25); \
    c ^= b; \
    c -= rot(b, 16); \
    a ^= c; \
    a -= rot(c, 4); \
    b ^= a; \
    b -= rot(a, 14); \
    c ^= b; \
    c -= rot(b, 24); \
  } \
  ((void)0)

inline uint32_t hash_uint2(const uint32_t kx, const uint32_t ky)
{
  uint32_t a;
  uint32_t b;
  uint32_t c;
  a = b = c = 0xdeadbeef + (2 << 2) + 13;

  b += ky;
  a += kx;
  final(a, b, c);

  return c;
}

inline uint32_t hash_uint3(const uint32_t kx, const uint32_t ky, const uint32_t kz)
{
  uint32_t a;
  uint32_t b;
  uint32_t c;
  a = b = c = 0xdeadbeef + (3 << 2) + 13;

  c += kz;
  b += ky;
  a += kx;
  final(a, b, c);

  return c;
}

inline uint32_t hash_uint4(const uint32_t kx, const uint32_t ky, const uint32_t kz, const uint32_t kw)
{
  uint32_t a;
  uint32_t b;
  uint32_t c;
  a = b = c = 0xdeadbeef + (4 << 2) + 13;

  a += kx;
  b += ky;
  c += kz;
  mix(a, b, c);

  a += kw;
  final(a, b, c);

  return c;
}

#undef rot
#undef final
#undef mix
// clang-format on

// SPEC §2 stateless random numbers. Evaluated in double: in float32,
// u32 * 2^-32 rounds to 1.0 for the top 128 values.

// rng_u32(seed, purpose, depth, a, b, c) = hash_uint4(hash_uint3(seed, purpose, depth), a, b, c).
inline uint32_t rng_u32(const uint32_t seed,
                        const uint32_t purpose,
                        const uint32_t depth,
                        const uint32_t a,
                        const uint32_t b,
                        const uint32_t c)
{
  return hash_uint4(hash_uint3(seed, purpose, depth), a, b, c);
}

// rng_unit = (double)rng_u32(...) * 2^-32, in [0, 1).
// 2^-32 is the mathematical definition of the u32 scale.
inline double rng_unit(const uint32_t seed,
                       const uint32_t purpose,
                       const uint32_t depth,
                       const uint32_t a,
                       const uint32_t b,
                       const uint32_t c)
{
  return (double)rng_u32(seed, purpose, depth, a, b, c) * 0x1p-32;
}

// rng_signed = 2 * rng_unit - 1, in [-1, 1).
// The 2 and the 1 are the affine map from [0, 1) onto [-1, 1).
inline double rng_signed(const uint32_t seed,
                         const uint32_t purpose,
                         const uint32_t depth,
                         const uint32_t a,
                         const uint32_t b,
                         const uint32_t c)
{
  return 2.0 * rng_unit(seed, purpose, depth, a, b, c) - 1.0;
}

// Purpose values for rng_u32 (SPEC §2).
// JITTER_X, JITTER_Y: (row, col, pass), depth 0.
// U2: only with u2_mode independent; (row, col, pass), depth = bounce depth.
// CLOSURE: (row, col, pass), depth = bounce depth.
// LANE_K0: (row, lane_in_row, pass), depth 0.
constexpr uint32_t PURPOSE_JITTER_X = 0;
constexpr uint32_t PURPOSE_JITTER_Y = 1;
constexpr uint32_t PURPOSE_U2 = 2;
constexpr uint32_t PURPOSE_CLOSURE = 3;
constexpr uint32_t PURPOSE_LANE_K0 = 4;
