/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

// Tests of painterly/kernel/closure/bounce.h (T3.9, T3.19). The reference is smallpaint's code:
// Vec and hemisphere() (smallpaint_ref.h), and the three bounce blocks of trace()
// (smallpaint_painterly.cpp:203-237), copied below with their inputs turned into arguments. For
// alpha > 0 it is the oracle's --alpha lines on top of smallpaint's diffuse block, and the
// zero-length d of SPEC §4 is checked against exact constants. The comparisons are bitwise
// (std::memcmp), so they allow no tolerance and tell -0.0 from +0.0. The one comparison with a
// tolerance is the |d| = 1 check of alpha = 1, whose bound is justified where it is defined.

#include <doctest/doctest.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <random>

#include "painterly/kernel/closure/bounce.h"
#include "painterly/kernel/sample/sampler.h"

#include "bitwise.h"
#include "smallpaint_ref.h"

// smallpaint's three bounce blocks of trace(), copied from
// third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp. Each block is the original
// with its inputs turned into arguments: the Halton draws become u1 and u2, the ray direction
// becomes d, and params["refr_index"] becomes n. Nothing else changed. They call smallpaint's Vec
// and hemisphere(), which smallpaint_ref.h holds verbatim. clang-format is off, so that the copy
// keeps the source's tabs.
// clang-format off
namespace smallpaint_bounce_ref {
using smallpaint_ref::Vec;
using smallpaint_ref::hemisphere;

// trace(), type 1 (smallpaint_painterly.cpp:203-206). The Halton draws hal.get() and hal2.get() are
// the arguments u1 and u2. The original's `ray.d` is d. Returns the cost.
double diffuse_block(Vec N, Vec &d, double u1, double u2) {
	d = (N + hemisphere(u1, u2));
	double cost = d.dot(N);
	return cost;
}

// trace(), type 2 (smallpaint_painterly.cpp:215-216).
void mirror_block(Vec N, Vec &d) {
	double cost = d.dot(N);
	d = (d - N*(cost * 2)).norm();
}

// trace(), type 3 (smallpaint_painterly.cpp:224-237). n is params["refr_index"]. Returns false where
// the original reaches `else return;`, which is total internal reflection.
bool glass_block(Vec N, Vec &d, double n) {
	if (N.dot(d) > 0) {
		N = N*-1;
		n = 1 / n;
	}
	n = 1 / n;
	double cost1 = (N.dot(d))*-1;
	double cost2 = 1.0 - n*n*(1.0 - cost1*cost1);
	if (cost2 > 0) {
		d = (d*n) + (N*(n*cost1 - sqrt(cost2)));
		d = d.norm();
		return true;
	} else return false;
}
}  // namespace smallpaint_bounce_ref
// clang-format on

CCL_NAMESPACE_BEGIN

namespace {

// Seed of std::mt19937_64. The C++ standard fixes its output sequence, so the inputs are the same
// on every platform. The value itself has no meaning.
constexpr std::uint64_t BOUNCE_TEST_SEED = 0xB0CE;
// Random inputs per check (T3.9 card: 10^5).
constexpr int BITWISE_TEST_DRAWS = 100000;
// K is drawn from [0, 2^22) (T3.9 card). K + 1 is then below 2^23, the period of vdc (SPEC §2), so
// every reference draw is an ordinary vdc value, and no chain reaches the wrap (SPEC §3).
constexpr std::uint64_t K_DRAW_LIMIT = std::uint64_t(1) << PAINTERLY_K0_BITS;
// The incoming d is drawn from [-DIRECTION_BOUND, DIRECTION_BOUND)^3, so it is unnormalized (SPEC
// §6), with length at most sqrt(3). Both signs of dot(N, d) occur, so the flip of the glass lobe
// is tested.
constexpr double DIRECTION_BOUND = 1.0;
// Origins are drawn from [-ORIGIN_BOUND, ORIGIN_BOUND)^3. The bounces must leave them unchanged.
constexpr double ORIGIN_BOUND = 1.0;
// Refractive index of the glass test, drawn from [GLASS_IOR_MIN, GLASS_IOR_MAX). The lower end is
// air and the upper end is above the index of common glass. Both total internal reflection and
// refraction occur in this range, and the test checks that both were drawn.
constexpr double GLASS_IOR_MIN = 1.0;
constexpr double GLASS_IOR_MAX = 2.0;
// Seed of the stateless RNG in the independent-u2 test. Any value works: the kernel and the oracle
// evaluate the same hash.
constexpr std::uint32_t U2_TEST_SEED = 7;
// Bound on | |d| - 1 | with alpha = 1. The identity |d| * |d|^-1 = 1 holds up to the round-off of
// sqrt, pow and the product, each a few units of 2^-52 (about 2.2e-16). 1e-12 is the float64
// round-off bound that CLAUDE.md allows for an analytic identity, so it is not a hand-picked
// tolerance.
constexpr double FLOAT64_ROUND_OFF_RTOL = 1e-12;
// alpha > 0 values of the bitwise test against the oracle's --alpha lines: the alphas of the
// first-light renders alpha_025, alpha_05 and alpha_1. alpha = 0 is the smallpaint test above.
constexpr double ORACLE_ALPHAS[] = {0.25, 0.5, 1.0};
// K before the zero draw of the zero-length test (T3.19). The draw is vdc(2^23) = vdc(0) = 0
// (SPEC §2), so u1 = u2 = 0 and s = (1, 0, 0).
constexpr std::uint64_t ZERO_DRAW_K0 = (std::uint64_t(1) << PAINTERLY_VDC_BITS) - 1;
// alpha values of the zero-length test: 0 (the default, where the rule changes nothing) and the
// three alphas of ORACLE_ALPHAS, whose first-light renders held NaN pixels before the rule.
constexpr double ZERO_LENGTH_ALPHAS[] = {0.0, 0.25, 0.5, 1.0};
// The spiral frame of the permuted-frame test (TQ.1 F20), row-major: the signed axis permutation
// with rows (0, 0, -1), (1, 0, 0) and (0, -1, 0). It is a rotation (det 1), as every spiral frame
// of SPEC §1 is. It moves every axis and is not symmetric, so an ignored, transposed or
// misindexed F changes the result. Its entries are exact, so F s is exact (see the test).
constexpr double PERMUTED_SPIRAL_FRAME[9] = {0.0, 0.0, -1.0, 1.0, 0.0, 0.0, 0.0, -1.0, 0.0};

// One random input of a bounce: a unit normal N, an origin, an unnormalized incoming direction,
// the sequence counter K0 before the draw, and the indices of the stateless RNG.
struct BounceCase {
  Triple normal;
  Triple origin;
  Triple incoming;
  std::uint64_t K0;
  int row, col, pass, depth;
};

// One random bounce input. The draws happen in a fixed order, so the sequence is the same on every
// platform.
BounceCase draw_case(std::mt19937_64 &rng)
{
  BounceCase c{};
  c.normal = random_unit_normal(rng);
  c.origin = uniform_triple(rng, -ORIGIN_BOUND, ORIGIN_BOUND);
  c.incoming = uniform_triple(rng, -DIRECTION_BOUND, DIRECTION_BOUND);
  c.K0 = rng() & (K_DRAW_LIMIT - 1);
  c.row = draw_index(rng);
  c.col = draw_index(rng);
  c.pass = draw_index(rng);
  c.depth = draw_index(rng);
  return c;
}

PainterlyRay make_ray(const Triple &origin, const Triple &direction)
{
  return PainterlyRay{to_double3(origin), to_double3(direction)};
}

// The identity spiral frame (SPEC §1). The other entries are already zero, because the caller
// value-initializes the integrator.
void set_identity_frame(KernelPainterlyIntegrator &p)
{
  p.spiral_frame[0] = 1.0;
  p.spiral_frame[4] = 1.0;
  p.spiral_frame[8] = 1.0;
}

// The oracle's diffuse lines with --alpha (trace() in src/app/smallpaint_oracle.cpp, items 13 and
// 22 of src/app/CHANGES.md): smallpaint's d = N + hemisphere(u1, u2), then d * |d|^-alpha, which
// is skipped for d = 0 (SPEC §4), then the cost of the rescaled d. Returns the cost.
double oracle_alpha_block(const smallpaint_bounce_ref::Vec &N,
                          smallpaint_bounce_ref::Vec &d,
                          const double u1,
                          const double u2,
                          const double alpha)
{
  d = (N + smallpaint_bounce_ref::hemisphere(u1, u2));
  if (d.x != 0 || d.y != 0 || d.z != 0) {
    d = d * std::pow(d.length(), -alpha);
  }
  return d.dot(N);
}

}  // namespace

TEST_CASE(
    "diffuse bounce is bitwise smallpaint's hemisphere block: spiral identity, alpha 0, u2 = u1")
{
  std::mt19937_64 rng(BOUNCE_TEST_SEED);
  KernelPainterlyIntegrator p{};
  p.u2_mode = U2_SAME;
  p.alpha = 0.0;
  set_identity_frame(p);

  int mismatches = 0;
  for (int draw = 0; draw < BITWISE_TEST_DRAWS; draw++) {
    const BounceCase c = draw_case(rng);
    PainterlyRay ray = make_ray(c.origin, c.incoming);
    std::uint64_t K = c.K0;
    const double cost = painterly_diffuse_bounce(
        p, to_double3(c.normal), &K, c.row, c.col, c.pass, c.depth, &ray);

    // The original draws u1 = u2 = vdc after K <- K + 1 (SPEC §4). vdc equals smallpaint's
    // Halton::next() bit for bit for K < 2^23, which test_sampler.cpp checks (T3.6), so the
    // reference takes the value as its input.
    const double u = painterly_vdc(c.K0 + 1);
    smallpaint_bounce_ref::Vec d_ref;
    const double cost_ref = smallpaint_bounce_ref::diffuse_block(to_ref(c.normal), d_ref, u, u);

    const bool same = K == c.K0 + 1 && same_bits(cost, cost_ref) &&
                      same_vec(ray.d, to_double3(d_ref)) && same_vec(ray.o, to_double3(c.origin));
    mismatches += !same;
  }
  CHECK_EQ(mismatches, 0);
}

TEST_CASE(
    "independent u2 is the second draw rng_unit(PURPOSE_U2, depth, row, col, pass) (SPEC §2, §4)")
{
  std::mt19937_64 rng(BOUNCE_TEST_SEED);
  KernelPainterlyIntegrator p{};
  p.u2_mode = U2_INDEPENDENT;
  p.seed = U2_TEST_SEED;
  p.alpha = 0.0;
  set_identity_frame(p);

  int mismatches = 0;
  for (int draw = 0; draw < BITWISE_TEST_DRAWS; draw++) {
    const BounceCase c = draw_case(rng);
    PainterlyRay ray = make_ray(c.origin, c.incoming);
    std::uint64_t K = c.K0;
    const double cost = painterly_diffuse_bounce(
        p, to_double3(c.normal), &K, c.row, c.col, c.pass, c.depth, &ray);

    // u1 is the vdc draw as before. u2 is the oracle's rng_unit, the hash that SPEC §2 defines.
    const double u1 = painterly_vdc(c.K0 + 1);
    const double u2 = smallpaint_oracle::rng_unit(U2_TEST_SEED,
                                                  std::uint32_t(PURPOSE_U2),
                                                  std::uint32_t(c.depth),
                                                  std::uint32_t(c.row),
                                                  std::uint32_t(c.col),
                                                  std::uint32_t(c.pass));
    smallpaint_bounce_ref::Vec d_ref;
    const double cost_ref = smallpaint_bounce_ref::diffuse_block(to_ref(c.normal), d_ref, u1, u2);

    const bool same = K == c.K0 + 1 && same_bits(cost, cost_ref) &&
                      same_vec(ray.d, to_double3(d_ref)) && same_vec(ray.o, to_double3(c.origin));
    mismatches += !same;
  }
  CHECK_EQ(mismatches, 0);
}

TEST_CASE("diffuse bounce with alpha = 1 gives |d| = 1 within float64 round-off")
{
  std::mt19937_64 rng(BOUNCE_TEST_SEED);
  KernelPainterlyIntegrator p{};
  p.u2_mode = U2_SAME;
  p.alpha = 1.0;
  set_identity_frame(p);

  double worst = 0.0;
  for (int draw = 0; draw < BITWISE_TEST_DRAWS; draw++) {
    const BounceCase c = draw_case(rng);
    PainterlyRay ray = make_ray(c.origin, c.incoming);
    std::uint64_t K = c.K0;
    painterly_diffuse_bounce(p, to_double3(c.normal), &K, c.row, c.col, c.pass, c.depth, &ray);
    // The expected length is 1, so the relative and absolute bounds coincide.
    worst = std::max(worst, std::fabs(len(ray.d) - 1.0));
  }
  CHECK(worst <= FLOAT64_ROUND_OFF_RTOL);
}

TEST_CASE("diffuse bounce with alpha > 0 is bitwise the oracle's --alpha lines")
{
  for (const double alpha : ORACLE_ALPHAS) {
    CAPTURE(alpha);
    std::mt19937_64 rng(BOUNCE_TEST_SEED);
    KernelPainterlyIntegrator p{};
    p.u2_mode = U2_SAME;
    p.alpha = alpha;
    set_identity_frame(p);

    int mismatches = 0;
    for (int draw = 0; draw < BITWISE_TEST_DRAWS; draw++) {
      const BounceCase c = draw_case(rng);
      PainterlyRay ray = make_ray(c.origin, c.incoming);
      std::uint64_t K = c.K0;
      const double cost = painterly_diffuse_bounce(
          p, to_double3(c.normal), &K, c.row, c.col, c.pass, c.depth, &ray);

      const double u = painterly_vdc(c.K0 + 1);
      smallpaint_bounce_ref::Vec d_ref;
      const double cost_ref = oracle_alpha_block(to_ref(c.normal), d_ref, u, u, alpha);

      const bool same = K == c.K0 + 1 && same_bits(cost, cost_ref) &&
                        same_vec(ray.d, to_double3(d_ref)) &&
                        same_vec(ray.o, to_double3(c.origin));
      mismatches += !same;
    }
    CHECK_EQ(mismatches, 0);
  }
}

TEST_CASE("zero-length diffuse d stays 0 with cost +0.0 for every alpha (SPEC §4)")
{
  // F = I and N = (-1, 0, 0), the normal of smallpaint's bottom plane (SPEC §9). The draw after
  // ZERO_DRAW_K0 is 0, so s = (1, 0, 0) and d = N + F s = (+0, +0, +0) exactly. The origin is a
  // point of the bottom plane, x = 2.5; the bounce must leave it unchanged. The incoming direction
  // is overwritten.
  const double3 N = make_double3(-1.0, 0.0, 0.0);
  const double3 origin = make_double3(2.5, 0.0, -3.0);
  const double3 incoming = make_double3(1.0, 0.0, 0.0);
  const double3 zero_direction = make_double3(0.0, 0.0, 0.0);
  REQUIRE(same_bits(painterly_vdc(ZERO_DRAW_K0 + 1), 0.0));

  for (const double alpha : ZERO_LENGTH_ALPHAS) {
    CAPTURE(alpha);
    KernelPainterlyIntegrator p{};
    p.u2_mode = U2_SAME;
    p.alpha = alpha;
    set_identity_frame(p);
    PainterlyRay ray{origin, incoming};
    std::uint64_t K = ZERO_DRAW_K0;
    const double cost = painterly_diffuse_bounce(p, N, &K, 0, 0, 0, 0, &ray);

    CHECK_EQ(K, ZERO_DRAW_K0 + 1);
    CHECK(same_vec(ray.d, zero_direction));
    CHECK(same_bits(cost, 0.0));
    CHECK(same_vec(ray.o, origin));
  }

  // The expression before the rule, d * pow(|d|, -alpha), on the same d. For alpha = 0 (-alpha is
  // -0.0) it is d * pow(0, -0) = d * 1 = d, the result checked above, so the rule changes nothing
  // there. For alpha > 0 it is 0 * inf = NaN in every component: the case that the rule removes.
  const double3 d_before_rule = zero_direction * std::pow(len(zero_direction), -0.0);
  CHECK(same_vec(d_before_rule, zero_direction));
  for (const double alpha : ORACLE_ALPHAS) {
    CAPTURE(alpha);
    const double3 d_literal = zero_direction * std::pow(len(zero_direction), -alpha);
    CHECK((std::isnan(d_literal.x) && std::isnan(d_literal.y) && std::isnan(d_literal.z)));
  }
}

TEST_CASE("mirror bounce is bitwise smallpaint's mirror block for unnormalized incoming d")
{
  std::mt19937_64 rng(BOUNCE_TEST_SEED);
  int mismatches = 0;
  for (int draw = 0; draw < BITWISE_TEST_DRAWS; draw++) {
    const BounceCase c = draw_case(rng);
    PainterlyRay ray = make_ray(c.origin, c.incoming);
    painterly_mirror_bounce(to_double3(c.normal), &ray);

    smallpaint_bounce_ref::Vec d_ref = to_ref(c.incoming);
    smallpaint_bounce_ref::mirror_block(to_ref(c.normal), d_ref);

    const bool same = same_vec(ray.d, to_double3(d_ref)) && same_vec(ray.o, to_double3(c.origin));
    mismatches += !same;
  }
  CHECK_EQ(mismatches, 0);
}

TEST_CASE(
    "glass bounce is bitwise smallpaint's glass block; total internal reflection leaves the ray "
    "unchanged")
{
  std::mt19937_64 rng(BOUNCE_TEST_SEED);
  int mismatches = 0;
  int refracted = 0;
  int total_internal_reflection = 0;
  for (int draw = 0; draw < BITWISE_TEST_DRAWS; draw++) {
    const BounceCase c = draw_case(rng);
    const double ior = uniform(rng, GLASS_IOR_MIN, GLASS_IOR_MAX);
    PainterlyRay ray = make_ray(c.origin, c.incoming);
    const bool refracts = painterly_glass_bounce(to_double3(c.normal), ior, &ray);

    smallpaint_bounce_ref::Vec d_ref = to_ref(c.incoming);
    const bool refracts_ref = smallpaint_bounce_ref::glass_block(to_ref(c.normal), d_ref, ior);

    // On total internal reflection the original returns before it touches d, so d_ref is still the
    // incoming direction, and the comparison of ray.d checks that the kernel left it unchanged
    // too.
    bool same = refracts == refracts_ref && same_vec(ray.o, to_double3(c.origin)) &&
                same_vec(ray.d, to_double3(d_ref));
    mismatches += !same;
    refracted += refracts;
    total_internal_reflection += !refracts;
  }
  CHECK_EQ(mismatches, 0);
  CHECK_GT(refracted, 0);
  CHECK_GT(total_internal_reflection, 0);
}

TEST_CASE("diffuse bounce with a permuted spiral frame is bitwise smallpaint's N + F s (SPEC §1)")
{
  // F = PERMUTED_SPIRAL_FRAME. Each row of F has one nonzero entry, +1 or -1, so each component
  // of F s is one component of s, maybe negated: F s = (-s.z, s.x, -s.y). The other two products
  // of a row are zeros, and adding a zero to a nonzero value leaves it unchanged. s has no zero
  // component: s.z = u1 = vdc(K0 + 1) lies in (0, 1) for K0 + 1 in [1, 2^22], so r > 0, and the
  // angle 2 PI u1 is a nonzero double below 2 pi, whose sine and cosine are never 0. The reference
  // is smallpaint's diffuse block with s replaced by that permutation of hemisphere(u, u):
  // d = N + s' and cost = d.N (smallpaint_painterly.cpp:205-206), bit for bit.
  std::mt19937_64 rng(BOUNCE_TEST_SEED);
  KernelPainterlyIntegrator p{};
  p.u2_mode = U2_SAME;
  p.alpha = 0.0;
  std::copy(PERMUTED_SPIRAL_FRAME, PERMUTED_SPIRAL_FRAME + 9, p.spiral_frame);

  int mismatches = 0;
  for (int draw = 0; draw < BITWISE_TEST_DRAWS; draw++) {
    const BounceCase c = draw_case(rng);
    PainterlyRay ray = make_ray(c.origin, c.incoming);
    std::uint64_t K = c.K0;
    const double cost = painterly_diffuse_bounce(
        p, to_double3(c.normal), &K, c.row, c.col, c.pass, c.depth, &ray);

    const double u = painterly_vdc(c.K0 + 1);
    const smallpaint_bounce_ref::Vec s = smallpaint_bounce_ref::hemisphere(u, u);
    const smallpaint_bounce_ref::Vec N_ref = to_ref(c.normal);
    const smallpaint_bounce_ref::Vec d_ref = N_ref + smallpaint_bounce_ref::Vec(-s.z, s.x, -s.y);
    const double cost_ref = d_ref.dot(N_ref);

    const bool same = K == c.K0 + 1 && same_bits(cost, cost_ref) &&
                      same_vec(ray.d, to_double3(d_ref)) && same_vec(ray.o, to_double3(c.origin));
    mismatches += !same;
  }
  CHECK_EQ(mismatches, 0);
}

CCL_NAMESPACE_END
