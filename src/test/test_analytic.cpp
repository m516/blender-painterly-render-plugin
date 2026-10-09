// SPDX-License-Identifier: GPL-3.0-or-later
// Tests of painterly/kernel/geom/analytic.h (T3.7). The bitwise tests compare the kernel with
// smallpaint's Sphere::intersect, Plane::intersect and Sphere::normal, and with the oracle's exact
// quadratic hook. They compare bit patterns with std::memcmp, so they allow no tolerance and tell
// -0.0 from +0.0. The geometric check of SPEC §5 is the only comparison with a tolerance. Its
// bound is justified where it is defined.

#include <doctest/doctest.h>

#include <cmath>
#include <cstdint>
#include <cstring>
#include <limits>
#include <random>

#include "painterly/kernel/geom/analytic.h"

// smallpaint's eps, Vec, Ray, Obj, Plane and Sphere, copied from
// third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp: eps at :39, and Vec
// through Sphere at :43-114. The copy is byte-identical to the source except for the line endings,
// which are LF here. Obj is copied too, because Plane and Sphere derive from it. clang-format is
// off, so that the copy keeps the source's tabs.
// clang-format off
namespace smallpaint_ref {
const double eps = 1e-4;
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

// Rays have origin and direction.
// The direction vector should always be normalized.
struct Ray {
	Vec o, d;
	Ray(Vec o0 = 0, Vec d0 = 0) { o = o0, d = d0.norm(); }
};

// Objects have color, emission, type (diffuse, specular, refractive)
// All object should be intersectable and should be able to compute their surface normals.
class Obj {
public:
	Vec cl;
	double emission;
	int type;
	void setMat(Vec cl_ = 0, double emission_ = 0, int type_ = 0) { cl = cl_; emission = emission_; type = type_; }
	virtual double intersect(const Ray&) const = 0;
	virtual Vec normal(const Vec&) const = 0;
};

class Plane : public Obj {
public:
	Vec n;
	double d;
	Plane(double d_ = 0, Vec n_ = 0) {
		d = d_;
		n = n_;
	}
	double intersect(const Ray& ray) const {
		double d0 = n.dot(ray.d);
		if (d0 != 0) {
			double t = -1 * (((n.dot(ray.o)) + d) / d0);
			return (t > eps) ? t : 0;
		} else return 0;
	}
	Vec normal(const Vec& p0) const { return n; }
};

class Sphere : public Obj {
public:
	Vec c;
	double r;

	Sphere(double r_ = 0, Vec c_ = 0) { c = c_; r = r_; }
	double intersect(const Ray& ray) const {
		double b = ((ray.o - c) * 2).dot(ray.d);
		double c_ = (ray.o - c).dot((ray.o - c)) - (r*r);
		double disc = b*b - 4 * c_;
		if (disc < 0) return 0;
		else disc = sqrt(disc);
		double sol1 = -b + disc;
		double sol2 = -b - disc;
		return (sol2 > eps) ? sol2 / 2 : ((sol1 > eps) ? sol1 / 2 : 0);
	}

	Vec normal(const Vec& p0) const {
		return (p0 - c).norm();
	}
};
}  // namespace smallpaint_ref
// clang-format on

// The oracle's exact quadratic hook, copied from src/app/smallpaint_oracle.cpp:138-148
// (Sphere::intersect_exact, SPEC §5). The oracle reads its global eps, which is smallpaint's 1e-4
// (smallpaint_painterly.cpp:39): the same value as smallpaint_ref::eps.
// clang-format off
namespace oracle_ref {
using smallpaint_ref::Ray;
using smallpaint_ref::Vec;
using smallpaint_ref::eps;

struct Sphere {
	Vec c;
	double r;
	double intersect_exact(const Ray& ray) const {
		double a = ray.d.dot(ray.d);
		double b = ((ray.o - c) * 2).dot(ray.d);
		double c_ = (ray.o - c).dot((ray.o - c)) - (r*r);
		double disc = b*b - 4 * a * c_;
		if (disc < 0) return 0;
		else disc = sqrt(disc);
		double sol1 = -b + disc;
		double sol2 = -b - disc;
		return (sol2 > eps) ? sol2 / (2 * a) : ((sol1 > eps) ? sol1 / (2 * a) : 0);
	}
};
}  // namespace oracle_ref
// clang-format on

CCL_NAMESPACE_BEGIN

namespace {

// Seed of std::mt19937_64. The C++ standard fixes its output sequence, so the inputs are the same
// on every platform. The value itself has no meaning.
constexpr std::uint64_t ANALYTIC_TEST_SEED = 0x7A3C;
// Random rays per bitwise check (T3.7 card: 10^5).
constexpr int BITWISE_TEST_RAYS = 100000;
// Random rays with a zero direction, the lower end of the |d| range in the bitwise test.
constexpr int ZERO_DIRECTION_RAYS = 1000;
// Random rays of the geometric check (T3.7 card: 10^5).
constexpr int GEOMETRY_TEST_RAYS = 100000;
// Significand precision of binary64 (53 bits, the definition of the format). unit_double() draws
// the top 53 bits of one 64-bit output and scales them by a power of two, so every draw is exact.
constexpr int DOUBLE_SIGNIFICAND_BITS = 53;
// |d| is drawn from [0, 2]. 2 is the largest unnormalized direction a diffuse bounce produces:
// |N + s| <= |N| + |s| = 2 for unit N and s (SPEC §4).
constexpr double DIRECTION_LENGTH_MAX = 2.0;
// Origins, sphere centres and plane offsets are drawn from [-SCENE_EXTENT, SCENE_EXTENT]. The
// walls of the reference scene lie at most 5.5 from the origin (SPEC §9), and 6 covers them.
constexpr double SCENE_EXTENT = 6.0;
// Sphere radii are drawn from [0, SCENE_RADIUS_MAX). The reference spheres have r <= 1.05 (SPEC
// §9). r = 0 is allowed (SPEC §5), and the draw can produce it only with probability 2^-53.
constexpr double SCENE_RADIUS_MAX = 2.0;

// Geometric check (SPEC §5): |d| = L is drawn from [GHOST_LENGTH_MIN, DIRECTION_LENGTH_MAX), that
// is, from L >= 1 up to 2. L > 1 is where the ghost test differs from the exact quadratic. The
// draw returns exactly 1 with probability 2^-53, and there the two tests agree.
constexpr double GHOST_LENGTH_MIN = 1.0;
// Origins and centres are drawn from [-GEOMETRY_EXTENT, GEOMETRY_EXTENT]. Radii are drawn from
// [GEOMETRY_RADIUS_MIN, GEOMETRY_RADIUS_MAX). The round-off bound at GHOST_GEOMETRY_RTOL uses
// these ranges: the radius floor keeps the bound independent of L.
constexpr double GEOMETRY_EXTENT = 1.0;
constexpr double GEOMETRY_RADIUS_MIN = 0.5;
constexpr double GEOMETRY_RADIUS_MAX = 1.0;
// Bound on |dist - R| / R for the ghost hit point. Its justification is at the geometric check.
constexpr double GHOST_GEOMETRY_RTOL = 1e-12;

struct Triple {
  double x, y, z;
};

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

// A direction of the given length: a random point of [-1, 1]^3, rescaled. A zero point has no
// direction, so the zero vector is returned for it. The probability of that draw is 2^-159.
Triple random_direction(std::mt19937_64 &rng, const double length)
{
  const Triple v = uniform_triple(rng, -1.0, 1.0);
  const double norm = std::sqrt(v.x * v.x + v.y * v.y + v.z * v.z);
  if (norm == 0.0) {
    return {0.0, 0.0, 0.0};
  }
  const double scale = length / norm;
  return {v.x * scale, v.y * scale, v.z * scale};
}

smallpaint_ref::Vec to_ref(const Triple &t)
{
  return smallpaint_ref::Vec(t.x, t.y, t.z);
}

double3 to_double3(const Triple &t)
{
  return make_double3(t.x, t.y, t.z);
}

// A unit normal, normalized with smallpaint's Vec::norm() so that it is exactly the vector
// smallpaint would use.
Triple random_unit_normal(std::mt19937_64 &rng)
{
  smallpaint_ref::Vec n = to_ref(uniform_triple(rng, -1.0, 1.0));
  n.norm();
  return {n.x, n.y, n.z};
}

// smallpaint's Ray normalizes its direction in its constructor. That is not wanted here, so the
// fields are set directly and |d| is kept.
smallpaint_ref::Ray make_ref_ray(const Triple &origin, const Triple &direction)
{
  smallpaint_ref::Ray ray;
  ray.o = to_ref(origin);
  ray.d = to_ref(direction);
  return ray;
}

PainterlyRay make_ray(const Triple &origin, const Triple &direction)
{
  return PainterlyRay{to_double3(origin), to_double3(direction)};
}

KernelPainterlyAnalytic make_sphere(const Triple &centre,
                                    const double radius,
                                    const int intersection)
{
  KernelPainterlyAnalytic sphere{};
  sphere.type = ANALYTIC_SPHERE;
  sphere.intersection = intersection;
  sphere.a = to_double3(centre);
  sphere.b = radius;
  return sphere;
}

KernelPainterlyAnalytic make_plane(const Triple &normal, const double offset)
{
  KernelPainterlyAnalytic plane{};
  plane.type = ANALYTIC_PLANE;
  plane.a = to_double3(normal);
  plane.b = offset;
  return plane;
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

// A hit is a t accepted by Scene::intersect: t > eps (smallpaint_painterly.cpp:138).
bool is_hit(const double t)
{
  return t > smallpaint_ref::eps;
}

// Mismatch counts of the bitwise checks, and how often each primitive is hit.
struct BitwiseCounts {
  int ghost_mismatches = 0;
  int exact_mismatches = 0;
  int plane_mismatches = 0;
  int dispatch_mismatches = 0;
  int normal_mismatches = 0;
  int ghost_hits = 0;
  int exact_hits = 0;
  int plane_hits = 0;
  // Rays on which the ghost and exact sphere results differ. The branch choice matters there.
  int branches_differ = 0;
};

// Compares one ray against one sphere (centre, radius), one plane (unit normal, offset) and one
// surface point, with the reference and the kernel results both computed.
void compare_ray(const Triple &origin,
                 const Triple &direction,
                 const Triple &centre,
                 const double radius,
                 const Triple &unit_normal,
                 const double offset,
                 const Triple &surface,
                 BitwiseCounts &counts)
{
  const double eps = smallpaint_ref::eps;
  const smallpaint_ref::Ray ref_ray = make_ref_ray(origin, direction);
  const PainterlyRay ray = make_ray(origin, direction);
  const smallpaint_ref::Vec ref_centre = to_ref(centre);
  const smallpaint_ref::Vec ref_normal = to_ref(unit_normal);
  const smallpaint_ref::Vec ref_surface = to_ref(surface);
  const smallpaint_ref::Sphere ref_sphere(radius, ref_centre);
  const smallpaint_ref::Plane ref_plane(offset, ref_normal);
  const KernelPainterlyAnalytic ghost = make_sphere(centre, radius, SPHERE_GHOST);
  const KernelPainterlyAnalytic exact = make_sphere(centre, radius, SPHERE_EXACT);
  const KernelPainterlyAnalytic plane = make_plane(unit_normal, offset);
  const double3 P = to_double3(surface);

  const double ref_t_ghost = ref_sphere.intersect(ref_ray);
  const double ref_t_exact = oracle_ref::Sphere{ref_centre, radius}.intersect_exact(ref_ray);
  const double ref_t_plane = ref_plane.intersect(ref_ray);

  const double kernel_t_ghost = painterly_sphere_intersect(ghost, ray, eps);
  const double kernel_t_exact = painterly_sphere_intersect(exact, ray, eps);
  const double kernel_t_plane = painterly_plane_intersect(plane, ray, eps);

  counts.ghost_mismatches += !same_bits(ref_t_ghost, kernel_t_ghost);
  counts.exact_mismatches += !same_bits(ref_t_exact, kernel_t_exact);
  counts.plane_mismatches += !same_bits(ref_t_plane, kernel_t_plane);
  counts.dispatch_mismatches += !same_bits(painterly_analytic_intersect(ghost, ray, eps),
                                           kernel_t_ghost);
  counts.dispatch_mismatches += !same_bits(painterly_analytic_intersect(exact, ray, eps),
                                           kernel_t_exact);
  counts.dispatch_mismatches += !same_bits(painterly_analytic_intersect(plane, ray, eps),
                                           kernel_t_plane);
  counts.normal_mismatches += !same_bits(ref_sphere.normal(ref_surface),
                                         painterly_analytic_normal(ghost, P));
  counts.normal_mismatches += !same_bits(ref_plane.normal(ref_surface),
                                         painterly_analytic_normal(plane, P));
  counts.ghost_hits += is_hit(kernel_t_ghost);
  counts.exact_hits += is_hit(kernel_t_exact);
  counts.plane_hits += is_hit(kernel_t_plane);
  counts.branches_differ += !same_bits(kernel_t_ghost, kernel_t_exact);
}

}  // namespace

TEST_CASE("ghost spheres, exact spheres and planes are bitwise smallpaint's and the oracle's")
{
  std::mt19937_64 rng(ANALYTIC_TEST_SEED);
  BitwiseCounts counts;
  for (int ray_index = 0; ray_index < BITWISE_TEST_RAYS; ray_index++) {
    const Triple origin = uniform_triple(rng, -SCENE_EXTENT, SCENE_EXTENT);
    const Triple centre = uniform_triple(rng, -SCENE_EXTENT, SCENE_EXTENT);
    const double radius = uniform(rng, 0.0, SCENE_RADIUS_MAX);
    const double length = DIRECTION_LENGTH_MAX * unit_double(rng);
    const Triple direction = random_direction(rng, length);
    const Triple surface = uniform_triple(rng, -SCENE_EXTENT, SCENE_EXTENT);
    const Triple unit_normal = random_unit_normal(rng);
    const double offset = uniform(rng, -SCENE_EXTENT, SCENE_EXTENT);
    compare_ray(origin, direction, centre, radius, unit_normal, offset, surface, counts);
  }
  CHECK_EQ(counts.ghost_mismatches, 0);
  CHECK_EQ(counts.exact_mismatches, 0);
  CHECK_EQ(counts.plane_mismatches, 0);
  CHECK_EQ(counts.dispatch_mismatches, 0);
  CHECK_EQ(counts.normal_mismatches, 0);
  // Coverage: each primitive is hit by some rays, and the two sphere branches disagree on some.
  CHECK_GT(counts.ghost_hits, 0);
  CHECK_GT(counts.exact_hits, 0);
  CHECK_GT(counts.plane_hits, 0);
  CHECK_GT(counts.branches_differ, 0);
}

TEST_CASE("a zero direction gives smallpaint's result bit for bit")
{
  std::mt19937_64 rng(ANALYTIC_TEST_SEED + 1);
  BitwiseCounts counts;
  const Triple zero{0.0, 0.0, 0.0};
  for (int ray_index = 0; ray_index < ZERO_DIRECTION_RAYS; ray_index++) {
    const Triple origin = uniform_triple(rng, -SCENE_EXTENT, SCENE_EXTENT);
    const Triple centre = uniform_triple(rng, -SCENE_EXTENT, SCENE_EXTENT);
    const double radius = uniform(rng, 0.0, SCENE_RADIUS_MAX);
    const Triple surface = uniform_triple(rng, -SCENE_EXTENT, SCENE_EXTENT);
    const Triple unit_normal = random_unit_normal(rng);
    const double offset = uniform(rng, -SCENE_EXTENT, SCENE_EXTENT);
    compare_ray(origin, zero, centre, radius, unit_normal, offset, surface, counts);
  }
  CHECK_EQ(counts.ghost_mismatches, 0);
  CHECK_EQ(counts.exact_mismatches, 0);
  CHECK_EQ(counts.plane_mismatches, 0);
  CHECK_EQ(counts.dispatch_mismatches, 0);
  CHECK_EQ(counts.normal_mismatches, 0);
}

TEST_CASE("ghost hit points lie on the sphere of SPEC §5 for |d| > 1")
{
  // Tolerance. GHOST_GEOMETRY_RTOL = 1e-12 is the float64 round-off allowance for an analytic
  // identity (CLAUDE.md, rule 2). The identity is exact in real arithmetic, so the check measures
  // round-off only. eps below is DBL_EPSILON = 2^-52. Over the sampling domain (|o|, |c| <=
  // sqrt(3), |o - c| <= 2 sqrt(3), 1 <= L <= 2, 1/2 <= r < 1), round-off enters in two places:
  //  (a) The computed root t has an absolute error of order eps |b|, from the cancellation in
  //      -b +- sqrt(disc). The residual F(t) = t^2 + b t + c' is then wrong by about
  //      eps (b^2 + 4 |c'|). Here b^2 = 4((o - c).d)^2 <= 4 L^2 |o - c|^2 <= 192, 4 |c'| <= 48,
  //      and the denominator 2((L^2 - 1)|o - c|^2 + r^2) of |dist - R| / R is at least 2 r^2 =
  //      1/2. So (a) is at most about 480 eps.
  //  (b) The arithmetic of P, C' and R has error of order eps (|o| + |C'|) / R, with
  //      |C'| <= 16 and R >= L r >= 1/2. That is at most about 40 eps.
  // The estimate totals about 520 eps = 1.2e-13, which is 8 times below the bound. The maximum
  // measured over the 10^5 rays of this test is 5.7 eps.
  std::mt19937_64 rng(ANALYTIC_TEST_SEED + 2);
  int violations = 0;
  int hits = 0;
  for (int ray_index = 0; ray_index < GEOMETRY_TEST_RAYS; ray_index++) {
    const Triple origin = uniform_triple(rng, -GEOMETRY_EXTENT, GEOMETRY_EXTENT);
    const Triple centre = uniform_triple(rng, -GEOMETRY_EXTENT, GEOMETRY_EXTENT);
    const double radius = uniform(rng, GEOMETRY_RADIUS_MIN, GEOMETRY_RADIUS_MAX);
    const double length = uniform(rng, GHOST_LENGTH_MIN, DIRECTION_LENGTH_MAX);
    const Triple direction = random_direction(rng, length);

    const PainterlyRay ray = make_ray(origin, direction);
    const KernelPainterlyAnalytic ghost = make_sphere(centre, radius, SPHERE_GHOST);
    const double t = painterly_sphere_intersect(ghost, ray, smallpaint_ref::eps);
    if (!is_hit(t)) {
      continue;
    }
    hits++;

    // SPEC §5: for |d| = L, the ghost test hits the sphere with centre o + L^2 (c - o) and radius
    // R = L sqrt((L^2 - 1) |o - c|^2 + r^2). Here L^2 = d.d and the hit point is P = o + t d.
    const double3 o = ray.o;
    const double3 c = ghost.a;
    const double3 P = o + ray.d * t;
    const double L2 = dot(ray.d, ray.d);
    const double L = std::sqrt(L2);
    const double3 u = o - c;
    const double3 centre_prime = o + (c - o) * L2;
    const double R = L * std::sqrt((L2 - 1) * dot(u, u) + radius * radius);
    const double relative_error = std::fabs(len(P - centre_prime) - R) / R;
    // Written as a negated <=, so that a NaN counts as a violation.
    violations += !(relative_error <= GHOST_GEOMETRY_RTOL);
  }
  CHECK_GT(hits, 0);
  CHECK_EQ(violations, 0);
}

CCL_NAMESPACE_END
