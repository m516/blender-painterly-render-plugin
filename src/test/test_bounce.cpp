// SPDX-License-Identifier: GPL-3.0-or-later
// Tests of painterly/kernel/closure/bounce.h (T3.9). The reference is smallpaint's own code: Vec,
// hemisphere() and the three bounce blocks of trace() (smallpaint_painterly.cpp:183-238), copied
// below with their inputs turned into arguments. The comparisons are bitwise (std::memcmp), so
// they allow no tolerance and tell -0.0 from +0.0. The one comparison with a tolerance is the |d|
// = 1 check of alpha = 1, whose bound is justified where it is defined.

#include <doctest/doctest.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <random>

#include "painterly/kernel/closure/bounce.h"
#include "painterly/kernel/sample/sampler.h"

// smallpaint's Vec, hemisphere() and the bounce blocks, copied from
// third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp. Each block is the original
// with its inputs turned into arguments: the Halton draws become u1 and u2, the ray direction
// becomes d, and params["refr_index"] becomes n. Nothing else changed. The namespace is unique to
// this file, because the other test files define their own smallpaint_ref. clang-format is off, so
// that the copy keeps the source's tabs.
// clang-format off
namespace smallpaint_bounce_ref {
// smallpaint's PI macro (smallpaint_painterly.cpp:33). It is a macro in the original and a constant here.
constexpr double PI = 3.1415926536;

// smallpaint_painterly.cpp:43-55.
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

// smallpaint_painterly.cpp:183-187.
Vec hemisphere(double u1, double u2) {
	const double r = sqrt(1.0 - u1*u1);
	const double phi = 2 * PI*u2;
	return Vec(cos(phi)*r, sin(phi)*r, u1);
}

// trace(), type 1 (smallpaint_painterly.cpp:203-206). The Halton draws hal.get() and hal2.get() are
// the arguments u1 and u2. The original's `ray.d` is d. Returns the cost.
double diffuse_block(Vec N, Vec &d, double u1, double u2) {
	d = (N + hemisphere(u1, u2));
	double cost = d.dot(N);
	return cost;
}

// trace(), type 2 (smallpaint_painterly.cpp:216-217).
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

// The oracle's hash helpers (rng_u32, rng_unit), as in test_sampler.cpp. The header defines them
// as inline functions in their own namespace.
namespace smallpaint_oracle {
#include "app/smallpaint_oracle_hash.h"
}  // namespace smallpaint_oracle

CCL_NAMESPACE_BEGIN

namespace {

// Seed of std::mt19937_64. The C++ standard fixes its output sequence, so the inputs are the same
// on every platform. The value itself has no meaning.
constexpr std::uint64_t BOUNCE_TEST_SEED = 0xB0CE;
// Random inputs per check (T3.9 card: 10^5).
constexpr int BITWISE_TEST_DRAWS = 100000;
// Significand precision of binary64 (53 bits, the definition of the format). unit_double() draws
// the top 53 bits of one 64-bit output and scales them by a power of two, so every draw is exact.
constexpr int DOUBLE_SIGNIFICAND_BITS = 53;
// Indices row, col, pass and depth are drawn from [0, INDEX_LIMIT), so they are non-negative ints.
constexpr std::uint64_t INDEX_LIMIT = std::uint64_t(1) << 31;
// K is drawn from [0, 2^22) (T3.9 card). K + 1 is then below 2^23, the period of vdc (SPEC §2), so
// every reference draw is an ordinary vdc value, and no chain reaches the wrap (SPEC §3).
constexpr std::uint64_t K_DRAW_LIMIT = std::uint64_t(1) << PAINTERLY_K0_BITS;
// Unit normals are drawn from the box [-NORMAL_BOUND, NORMAL_BOUND)^3 and then normalized.
constexpr double NORMAL_BOUND = 1.0;
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

struct Triple {
  double x, y, z;
};

// One random input of a bounce: a unit normal N, an origin, an unnormalized incoming direction,
// the sequence counter K0 before the draw, and the indices of the stateless RNG.
struct BounceCase {
  Triple normal;
  Triple origin;
  Triple incoming;
  std::uint64_t K0;
  int row, col, pass, depth;
};

// True when a and b have the same IEEE 754 bit pattern. This is memcmp, not ==, so that -0.0 and
// +0.0 differ.
bool same_bits(const double a, const double b)
{
  return std::memcmp(&a, &b, sizeof(double)) == 0;
}

// True when every component of a and b has the same bit pattern.
bool same_vec(const double3 a, const double3 b)
{
  return same_bits(a.x, b.x) && same_bits(a.y, b.y) && same_bits(a.z, b.z);
}

// Uniform in [0, 1). The top DOUBLE_SIGNIFICAND_BITS bits of one 64-bit draw, scaled by a power of
// two, so the value is exact on every platform.
double unit_double(std::mt19937_64 &rng)
{
  constexpr int dropped_bits = std::numeric_limits<std::uint64_t>::digits -
                               DOUBLE_SIGNIFICAND_BITS;
  return std::ldexp(double(rng() >> dropped_bits), -DOUBLE_SIGNIFICAND_BITS);
}

// lo + (hi - lo) * u with u in [0, 1). Plain IEEE arithmetic, so the same on every platform.
double uniform(std::mt19937_64 &rng, const double lo, const double hi)
{
  return lo + (hi - lo) * unit_double(rng);
}

// Braced initialization evaluates the three draws left to right, so the sequence is fixed.
Triple uniform_triple(std::mt19937_64 &rng, const double lo, const double hi)
{
  return {uniform(rng, lo, hi), uniform(rng, lo, hi), uniform(rng, lo, hi)};
}

int draw_index(std::mt19937_64 &rng)
{
  return int(rng() & (INDEX_LIMIT - 1));
}

smallpaint_bounce_ref::Vec to_ref(const Triple &t)
{
  return smallpaint_bounce_ref::Vec(t.x, t.y, t.z);
}

double3 to_double3(const Triple &t)
{
  return make_double3(t.x, t.y, t.z);
}

double3 to_double3(const smallpaint_bounce_ref::Vec &v)
{
  return make_double3(v.x, v.y, v.z);
}

// A unit normal, normalized with smallpaint's Vec::norm() so that it is exactly the vector
// smallpaint would use. The zero draw has probability 2^-159, and it would give NaN in both
// implementations.
Triple random_unit_normal(std::mt19937_64 &rng)
{
  smallpaint_bounce_ref::Vec n = to_ref(uniform_triple(rng, -NORMAL_BOUND, NORMAL_BOUND));
  n.norm();
  return {n.x, n.y, n.z};
}

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

CCL_NAMESPACE_END
