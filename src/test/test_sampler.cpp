// SPDX-License-Identifier: GPL-3.0-or-later
// Tests of painterly/kernel/sample/sampler.h (T3.6). The sequence counter is compared bit for bit
// with smallpaint's incremental Halton class, the stateless RNG with the oracle's helpers, and the
// chain starts with SPEC §3. Every comparison is bitwise (std::memcmp for doubles) or exact
// integer equality, so no tolerance is used.

#include <doctest/doctest.h>

#include <cmath>
#include <cstdint>
#include <cstring>
#include <random>

#include "painterly/kernel/sample/sampler.h"

// smallpaint's Halton class, copied verbatim from
// third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp:147-169. clang-format is
// off so that the copy stays byte-identical to the source, tabs included.
// clang-format off
namespace smallpaint_ref {
class Halton {
	double value, inv_base;
public:
	void number(int i, int base) {
		double f = inv_base = 1.0 / base;
		value = 0.0;
		while (i > 0) {
			value += f*(double)(i%base);
			i /= base;
			f *= inv_base;
		}
	}
	void next() {
		double r = 1.0 - value - 0.0000001;
		if (inv_base < r) value += inv_base;
		else {
			double h = inv_base, hh;
			do { hh = h; h *= inv_base; } while (h >= r);
			value += hh + h - 1.0;
		}
	}
	double get() { return value; }
};
}  // namespace smallpaint_ref
// clang-format on

// The oracle's hash helpers (rng_u32, rng_unit, rng_signed). The header defines them as global
// functions, so it is included in its own namespace and cannot collide with painterly's names.
namespace smallpaint_oracle {
#include "app/smallpaint_oracle_hash.h"
}  // namespace smallpaint_oracle

CCL_NAMESPACE_BEGIN

namespace {

// Seed of std::mt19937_64. The C++ standard fixes the output sequence of this generator, so the
// inputs are the same on every platform. The value itself has no meaning.
constexpr std::uint64_t BITWISE_TEST_SEED = 0x5EED;
// Random inputs per check (T3.6 card: 10^5 random tuples).
constexpr int BITWISE_TEST_DRAWS = 100000;
// Period of the sequence counter in K: 2^23 (SPEC §2).
constexpr std::uint64_t VDC_PERIOD = std::uint64_t(1) << PAINTERLY_VDC_BITS;
// Guard of smallpaint's Halton::next() (smallpaint_painterly.cpp:160). It is smallpaint's own
// constant, not a tolerance chosen for the test: SPEC §2 documents that the original's error at
// the wrap is below this value.
constexpr double SMALLPAINT_HALTON_GUARD = 0.0000001;
// Rows, lanes and passes are drawn from [0, INDEX_LIMIT). They are non-negative ints.
constexpr std::uint64_t INDEX_LIMIT = std::uint64_t(1) << 31;
// Phase locks (SPEC §8, k0_phase_lock_bits): off, a short lock, and the full width, which clears
// all of K0.
constexpr int PHASE_LOCK_OFF = 0;
constexpr int PHASE_LOCK_SHORT = 3;
constexpr int PHASE_LOCK_FULL = PAINTERLY_K0_BITS;

// True when a and b have the same IEEE 754 bit pattern. This is memcmp, not ==, so that -0.0 and
// +0.0 differ.
bool same_bits(const double a, const double b)
{
  return std::memcmp(&a, &b, sizeof(double)) == 0;
}

// The six arguments of the stateless RNG (SPEC §2).
struct RngArgs {
  std::uint32_t seed, purpose, depth, a, b, c;
};

// Braced initialization evaluates the draws left to right, so the sequence is fixed.
RngArgs draw_rng_args(std::mt19937_64 &rng)
{
  return {std::uint32_t(rng()),
          std::uint32_t(rng()),
          std::uint32_t(rng()),
          std::uint32_t(rng()),
          std::uint32_t(rng()),
          std::uint32_t(rng())};
}

int draw_index(std::mt19937_64 &rng)
{
  return int(rng() & (INDEX_LIMIT - 1));
}

}  // namespace

TEST_CASE(
    "painterly_vdc is bitwise smallpaint's Halton::next() for K = 1 ... 2^23, including the wrap")
{
  // number(0, 2) starts the original at K = 0. Each next() is one diffuse draw, K <- K + 1 (SPEC
  // §2).
  smallpaint_ref::Halton halton;
  halton.number(0, 2);
  int mismatches = 0;
  for (std::uint64_t K = 1; K < VDC_PERIOD; K++) {
    halton.next();
    mismatches += !same_bits(halton.get(), painterly_vdc(K));
  }
  CHECK_EQ(mismatches, 0);

  // K = 2^23 is the wrap. vdc(2^23) = bitrev23(0) * 2^-23 = 0. The original's step is then smaller
  // than the guard in next(), so its value is no longer vdc: it is about -7.45e-8 (SPEC §2). Its
  // distance to 0 is below the guard.
  halton.next();
  CHECK(!same_bits(halton.get(), painterly_vdc(VDC_PERIOD)));
  CHECK(std::fabs(halton.get() - painterly_vdc(VDC_PERIOD)) < SMALLPAINT_HALTON_GUARD);
}

TEST_CASE("stateless RNG is bitwise the oracle's rng_u32, rng_unit and rng_signed")
{
  std::mt19937_64 rng(BITWISE_TEST_SEED);
  int u32_mismatches = 0;
  int unit_mismatches = 0;
  int signed_mismatches = 0;
  for (int draw = 0; draw < BITWISE_TEST_DRAWS; draw++) {
    const RngArgs t = draw_rng_args(rng);
    u32_mismatches += painterly_rng_u32(t.seed, t.purpose, t.depth, t.a, t.b, t.c) !=
                      smallpaint_oracle::rng_u32(t.seed, t.purpose, t.depth, t.a, t.b, t.c);
    unit_mismatches += !same_bits(
        painterly_rng_unit(t.seed, t.purpose, t.depth, t.a, t.b, t.c),
        smallpaint_oracle::rng_unit(t.seed, t.purpose, t.depth, t.a, t.b, t.c));
    signed_mismatches += !same_bits(
        painterly_rng_signed(t.seed, t.purpose, t.depth, t.a, t.b, t.c),
        smallpaint_oracle::rng_signed(t.seed, t.purpose, t.depth, t.a, t.b, t.c));
  }
  CHECK_EQ(u32_mismatches, 0);
  CHECK_EQ(unit_mismatches, 0);
  CHECK_EQ(signed_mismatches, 0);
}

TEST_CASE(
    "chain starts: low q bits are zero, q = 0 is the raw masked hash, values stay below 2^22")
{
  std::mt19937_64 rng(BITWISE_TEST_SEED);
  const PainterlyChain chains[] = {CHAIN_ROW, CHAIN_LANE};
  const int phase_locks[] = {PHASE_LOCK_OFF, PHASE_LOCK_SHORT, PHASE_LOCK_FULL};
  const std::uint64_t k0_limit = std::uint64_t(1) << PAINTERLY_K0_BITS;
  const std::uint32_t k0_mask = (1u << PAINTERLY_K0_BITS) - 1u;

  int low_bit_violations = 0;
  int unmasked_mismatches = 0;
  int phase_lock_mismatches = 0;
  int range_violations = 0;
  for (const PainterlyChain chain : chains) {
    for (const int q : phase_locks) {
      KernelPainterlyIntegrator p{};
      p.chain = chain;
      p.seed = std::uint32_t(rng());
      p.k0_phase_lock_bits = q;
      const std::uint32_t low_mask = (1u << q) - 1u;
      for (int draw = 0; draw < BITWISE_TEST_DRAWS; draw++) {
        const int row = draw_index(rng);
        const int lane = draw_index(rng);
        const int pass = draw_index(rng);
        const std::uint64_t k0 = painterly_chain_start(p, row, lane, pass);
        // CHAIN_ROW is lane 0 of its row, whatever lane_in_row the caller passes (SPEC §3).
        const std::uint32_t lane_in_hash = (chain == CHAIN_ROW) ? 0u : std::uint32_t(lane);
        const std::uint32_t raw = smallpaint_oracle::rng_u32(p.seed,
                                                             PURPOSE_LANE_K0,
                                                             0,
                                                             std::uint32_t(row),
                                                             lane_in_hash,
                                                             std::uint32_t(pass)) &
                                  k0_mask;
        low_bit_violations += (k0 & low_mask) != 0;
        phase_lock_mismatches += k0 != (raw & ~low_mask);
        if (q == PHASE_LOCK_OFF) {
          unmasked_mismatches += k0 != raw;
        }
        range_violations += k0 >= k0_limit;
      }
    }
  }
  CHECK_EQ(low_bit_violations, 0);
  CHECK_EQ(unmasked_mismatches, 0);
  CHECK_EQ(phase_lock_mismatches, 0);
  CHECK_EQ(range_violations, 0);
}

TEST_CASE("chain start of CHAIN_IMAGE is the render-start value 0")
{
  std::mt19937_64 rng(BITWISE_TEST_SEED);
  KernelPainterlyIntegrator p{};
  p.chain = CHAIN_IMAGE;
  p.seed = std::uint32_t(rng());
  int nonzero = 0;
  for (int draw = 0; draw < BITWISE_TEST_DRAWS; draw++) {
    nonzero += painterly_chain_start(p, draw_index(rng), draw_index(rng), draw_index(rng)) != 0;
  }
  CHECK_EQ(nonzero, 0);
}

CCL_NAMESPACE_END
