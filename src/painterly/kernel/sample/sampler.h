/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

#pragma once

/* The sequence counter K, the stateless random numbers and the chain starts (SPEC §2, §3).
 * Every function is a pure function of its arguments. Nothing is stored between calls, so lanes,
 * rows and passes can be evaluated in any order and on any thread. */

#include <cstdint>

#include "painterly/kernel/types.h"
#include "util/hash.h"

CCL_NAMESPACE_BEGIN

/* SPEC §2. vdc(K) depends only on K mod 2^PAINTERLY_VDC_BITS: 2^23 is the period of smallpaint's
 * incremental Halton::next() in IEEE double (smallpaint_painterly.cpp:147-169). */
constexpr int PAINTERLY_VDC_BITS = 23;
/* SPEC §3. K0 is the low 22 bits of a hash. A chain that consumes fewer than 2^22 draws never
 * reaches the 2^23 wrap. */
constexpr int PAINTERLY_K0_BITS = 22;
/* 2^-23 is the mathematical definition of the van der Corput scale. bitrev23 is an integer in
 * [0, 2^23), so bitrev23 * 2^-23 lies in [0, 1). */
constexpr double PAINTERLY_VDC_SCALE = 0x1p-23;
/* 2^-32 is the mathematical definition of the u32 scale: it maps [0, 2^32) onto [0, 1) (SPEC §2).
 */
constexpr double PAINTERLY_RNG_U32_SCALE = 0x1p-32;

/* Reverse the low PAINTERLY_VDC_BITS bits of k. Bit i of k moves to bit (PAINTERLY_VDC_BITS - 1 -
 * i). Bits above PAINTERLY_VDC_BITS are ignored. SPEC §2. */
ccl_device_inline uint painterly_bitrev23(uint k)
{
  uint reversed = 0;
  for (int bit = 0; bit < PAINTERLY_VDC_BITS; bit++) {
    reversed = (reversed << 1) | ((k >> bit) & 1u);
  }
  return reversed;
}

/* vdc(K) = bitrev23(K mod 2^23) * 2^-23; exact in double. SPEC §2. */
ccl_device_inline double painterly_vdc(uint64_t K)
{
  const uint64_t period_mask = (uint64_t(1) << PAINTERLY_VDC_BITS) - 1;
  return double(painterly_bitrev23(uint(K & period_mask))) * PAINTERLY_VDC_SCALE;
}

/* SPEC §2: rng_u32(seed, purpose, depth, a, b, c) = hash_uint4(hash_uint3(seed, purpose, depth),
 * a, b, c), with Cycles' hash functions (util/hash.h, vendored verbatim). */
ccl_device_inline uint
painterly_rng_u32(uint seed, uint purpose, uint depth, uint a, uint b, uint c)
{
  return hash_uint4(hash_uint3(seed, purpose, depth), a, b, c);
}

/* SPEC §2: rng_unit = (double)rng_u32 * 2^-32, in [0, 1). Evaluated in double, because in float32
 * the top 128 values round to 1.0. */
ccl_device_inline double painterly_rng_unit(
    uint seed, uint purpose, uint depth, uint a, uint b, uint c)
{
  return double(painterly_rng_u32(seed, purpose, depth, a, b, c)) * PAINTERLY_RNG_U32_SCALE;
}

/* SPEC §2: rng_signed = 2 * rng_unit - 1, in [-1, 1). The 2 and the 1 map [0, 1) affinely onto
 * [-1, 1). */
ccl_device_inline double painterly_rng_signed(
    uint seed, uint purpose, uint depth, uint a, uint b, uint c)
{
  return 2.0 * painterly_rng_unit(seed, purpose, depth, a, b, c) - 1.0;
}

/* K0 of the chain that starts at (row, lane_in_row, pass), after the phase lock (SPEC §3, §8).
 *   CHAIN_ROW:   K0 = rng_u32(seed, PURPOSE_LANE_K0, 0, row, 0, pass) mod 2^22.
 *   CHAIN_LANE:  K0 = rng_u32(seed, PURPOSE_LANE_K0, 0, row, lane_in_row, pass) mod 2^22.
 *   Then K0 &= ~((1 << q) - 1) with q = k0_phase_lock_bits, in the range 0 to PAINTERLY_K0_BITS.
 * A row chain is lane 0 of its row, so CHAIN_ROW ignores lane_in_row and uses the lane-0 hash.
 * CHAIN_IMAGE has no per-pass start: K starts at 0 for the whole render and is never reset (SPEC
 * §3). It returns 0, the render-start value. The caller must not reset K between passes. */
ccl_device_inline uint64_t painterly_chain_start(const KernelPainterlyIntegrator &p,
                                                 int row,
                                                 int lane_in_row,
                                                 int pass)
{
  if (p.chain == CHAIN_IMAGE) {
    return 0;
  }
  const uint lane = (p.chain == CHAIN_ROW) ? 0u : uint(lane_in_row);
  const uint hash = painterly_rng_u32(p.seed, PURPOSE_LANE_K0, 0, uint(row), lane, uint(pass));
  const uint k0_mask = (1u << PAINTERLY_K0_BITS) - 1u;
  const uint phase_lock_mask = (1u << p.k0_phase_lock_bits) - 1u;
  return uint64_t((hash & k0_mask) & ~phase_lock_mask);
}

CCL_NAMESPACE_END
