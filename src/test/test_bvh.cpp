/* SPDX-FileCopyrightText: 2026 The Painterly Authors
 * SPDX-License-Identifier: GPL-3.0-or-later */

// Tests of painterly/bvh/embree.h (T3.10). The scene is the unit quad of the card (two triangles
// sharing the diagonal from (0,0,0) to (1,1,0)), instanced twice. Object 0 is an axis permutation
// with a power-of-two scale and an integer translation, so its transform is exact. Object 1 is a
// shear with dyadic entries, so its normals are not axis-aligned. Every ray is exact in binary32,
// and every expected hit is known in closed form. The only comparisons with a tolerance are those
// of t, u and v, which pass through Embree's reciprocal; HIT_RELATIVE_BOUND derives their bound.
// The others are exact. The last test case checks that Ng and the corner normals of
// painterly_triangle_shading_normal go through one normal matrix (T3.21).

#include <doctest/doctest.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <memory>
#include <stdexcept>
#include <vector>

#include "painterly/bvh/embree.h"
#include "painterly/kernel/geom/triangle.h"
#include "painterly/util/math_double3.h"

CCL_NAMESPACE_BEGIN

namespace {

// Round-off bounds of Embree's binary32 hits (CLAUDE.md rule 2: float32 round-off where the
// computation is float32, with the bound derived here). Notation of Higham, "Accuracy and
// Stability of Numerical Algorithms", 2nd ed., SIAM 2002, section 2.2 and Lemmas 3.1 and 3.3: a
// correctly rounded operation returns (x op y)(1 + d) with |d| <= u, and a product of n factors
// 1 + d_i with |d_i| <= u is 1 + theta with |theta| <= gamma(n) = n u / (1 - n u). u = 2^-24 is
// the unit round-off of IEEE binary32 with round to nearest (a definition of the format).
//
// The operations are counted in the Embree 4.4.1 source (build/dev/_deps/embree-src):
// 1. RTC_SCENE_FLAG_ROBUST selects the Triangle4v BVH and the Pluecker intersector
//    (kernels/common/scene.cpp:160-189; kernels/bvh/bvh4_factory.cpp:581-586;
//    kernels/bvh/bvh8_factory.cpp:530-537, where ENABLE_WOOP_TEST is 0;
//    kernels/geometry/trianglev_intersector.h:127-137).
// 2. An instance hit moves the world ray to object space
//    (kernels/geometry/instance_intersector.cpp:27-31). world2local = rcp(object_to_world) is
//    formed once: its 3x3 part by cross products, a dot product and IEEE divisions
//    (kernels/common/scene_instance.cpp:153, common/math/affinespace.h:83,
//    common/math/linearspace3.h:45-51, 114 and 153, common/math/vec3fa.h:585 and 695-711), and its
//    translation -(A^-1 p) by multiply-adds (common/math/affinespace.h:83,
//    common/math/linearspace3.h:150). The ray then goes through multiply-adds
//    (common/math/affinespace.h:102-103, common/math/linearspace3.h:160).
// 3. The Pluecker test (kernels/geometry/triangle_intersector_pluecker.h:80-109) forms the
//    vertices relative to the origin, the edges, the edge functions U, V and W, Ng
//    (common/math/vec3.h:204-222), den and T, with +, -, * and multiply-adds only.
// 4. t = rcp(den) * T (:110), and u = min(U * rcp(U + V + W), 1), v likewise (:30-36).
// Every transform, vertex and ray of this file is a dyadic rational with few significant bits,
// and every operation of steps 2 and 3 has an exactly representable result on them (checked
// operation by operation in exact rational arithmetic: docs/tasks/M3/T3.21-contract-touchups.md,
// appendix A). A correctly rounded operation whose result is representable returns it exactly,
// on every ISA and whether or not it is fused into an FMA: d = 0. Ng is therefore exact.
// The reciprocal is the one operation whose result depends on the ISA:
// - arm64: the IEEE quotient 1 / x (common/simd/vfloat4_sse2.h:306-307, vfloat8_avx.h:256-261),
//   |d| <= u.
// - x86-64: one Newton step r0 + r0 (1 - x r0) on the estimate r0 = (1 / x)(1 + e) of RCPPS,
//   |e| <= 1.5 * 2^-12 (Intel SDM vol. 2, RCPPS) (vfloat4_sse2.h:313-319,
//   vfloat8_avx.h:267-276). Without FMA, 1 - fl(x r0) is exact (Sterbenz) and the three other
//   operations round once each: |d| <= E (1 + u) + u with E = e^2 + u (1 + e)^2 +
//   (1 + e)(e + u (1 + e)) u, which is below 4.26 u since e^2 = 2.25 u. With FMA, two roundings:
//   E = e^2 + e u (1 + e), and |d| < 3.26 u.
// So |d| < 5 u <= gamma(5) for every reciprocal: it counts as RCP_ROUNDINGS = 5 roundings. t, u
// and v each take one reciprocal and one product, so their relative error is at most gamma(6)
// (HIT_ROUNDINGS). The clamp min(., 1) only moves a value above 1 towards the exact value, which
// is at most 1. As a check: with each of Embree's isa=sse2, sse4.2, avx and avx2, the hits of
// this file had relative errors from 1.0 u to 1.3 u (T3.21), and M2's selftest gave
// t = 0.49999997 for an exact 0.5, a relative error of u.
constexpr double F32_UNIT_ROUNDOFF = 0x1p-24;
constexpr int RCP_ROUNDINGS = 5;
constexpr int HIT_ROUNDINGS = RCP_ROUNDINGS + 1;

// Higham's gamma(n) for binary32.
constexpr double f32_gamma(const int n)
{
  return n * F32_UNIT_ROUNDOFF / (1.0 - n * F32_UNIT_ROUNDOFF);
}

// Relative bound on Embree's t, u and v for the inputs of this file.
constexpr double HIT_RELATIVE_BOUND = f32_gamma(HIT_ROUNDINGS);

// The binary64 round-off of this file's own reference values, counted the same way with
// u64 = 2^-53. t_expected = len(point - ray.o) / len(ray.d) takes two square roots and one
// quotient, at most gamma64(3) = 3 u64 relative to the operands. One coordinate of the
// barycentric point takes three products and two sums (gamma64(5) = 5 u64), the same coordinate
// of o + t d one product and one sum (gamma64(2) = 2 u64), and their difference one more
// rounding: at most 8 u64 relative to the largest coordinate the rounding acts on. The 3, the 5
// and the 2 are counts of those operations, derived from the expressions of check_hit, not
// measurements. They total at most 11 * 2^-53 < 2^-24 = u, so the single binary32 unit round-off
// bounds them: charging u is an over-bound, and it keeps one term instead of two.
constexpr double REFERENCE_ROUNDOFF = F32_UNIT_ROUNDOFF;

// smallpaint's eps (third_party/smallpaint/smallpaint_painterly/smallpaint_painterly.cpp:39), the
// ray_epsilon knob (SPEC §6).
constexpr double RAY_EPSILON = 1e-4;

constexpr double INFINITE_DISTANCE = std::numeric_limits<double>::infinity();

// The unit quad: vertices 0 (0,0,0), 1 (1,0,0), 2 (1,1,0), 3 (0,1,0). Triangle 0 is (0,1,2),
// triangle 1 is (0,2,3), so the shared edge runs from (0,0,0) to (1,1,0). Both triangles have
// object-space normal (0,0,1).
const float QUAD_VERTICES[12] = {
    0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 1.0f, 1.0f, 0.0f, 0.0f, 1.0f, 0.0f};
const uint32_t QUAD_TRIANGLES[6] = {0, 1, 2, 0, 2, 3};

// Object 0: world = (y, x, 2z + 5). The swap of x and y keeps the diagonal x = y, the scale on z
// is a power of two, and the translation is an integer. The quad lies in the plane z = 5.
const float OBJECT0_TO_WORLD[12] = {
    0.0f, 1.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 2.0f, 5.0f};
// Object 1: world = A (x, y, z) + (1, 2, -3) with A = [[2,0,0],[0,2,0],[0.5,0,1]]. A shear with
// dyadic entries. The quad maps to the points (1,2,-3), (3,2,-2.5), (3,4,-2.5), (1,4,-3). Its
// world normal is (T1 x T2) = (-1, 0, 4), which is parallel to inv(A)^T (0,0,1) = (-0.25, 0, 1),
// the normal that a direction transform would get wrong.
const float OBJECT1_TO_WORLD[12] = {
    2.0f, 0.0f, 0.0f, 1.0f, 0.0f, 2.0f, 0.0f, 2.0f, 0.5f, 0.0f, 1.0f, -3.0f};

using SceneHandle = std::unique_ptr<PainterlyEmbreeScene, void (*)(PainterlyEmbreeScene *)>;

// The quad mesh, instanced as object 0 and object 1, built from the given arrays.
SceneHandle build_scene(const float *vertices,
                        const uint32_t *triangles,
                        const float *object0,
                        const float *object1)
{
  const PainterlyEmbreeMeshInput mesh = {vertices, 4, triangles, 2};
  const PainterlyEmbreeObjectInput objects[2] = {{0, object0}, {0, object1}};
  return SceneHandle(painterly_embree_scene_create(&mesh, 1, objects, 2),
                     painterly_embree_scene_free);
}

SceneHandle build_quad_scene()
{
  return build_scene(QUAD_VERTICES, QUAD_TRIANGLES, OBJECT0_TO_WORLD, OBJECT1_TO_WORLD);
}

// Object-space corner of the quad.
double3 quad_vertex(const uint32_t index)
{
  return make_double3(
      QUAD_VERTICES[3 * index], QUAD_VERTICES[3 * index + 1], QUAD_VERTICES[3 * index + 2]);
}

// Object -> world for a point (the last column is added) and for a direction (it is not), in
// double. The transforms of this file have dyadic entries, so the products are exact for the
// points and directions used here.
double3 to_world_point(const float *tfm, const double3 p)
{
  return make_double3(tfm[0] * p.x + tfm[1] * p.y + tfm[2] * p.z + tfm[3],
                      tfm[4] * p.x + tfm[5] * p.y + tfm[6] * p.z + tfm[7],
                      tfm[8] * p.x + tfm[9] * p.y + tfm[10] * p.z + tfm[11]);
}

double3 to_world_direction(const float *tfm, const double3 d)
{
  return make_double3(tfm[0] * d.x + tfm[1] * d.y + tfm[2] * d.z,
                      tfm[4] * d.x + tfm[5] * d.y + tfm[6] * d.z,
                      tfm[8] * d.x + tfm[9] * d.y + tfm[10] * d.z);
}

PainterlyRay make_ray(const double3 origin, const double3 direction)
{
  PainterlyRay ray;
  ray.o = origin;
  ray.d = direction;
  return ray;
}

double max_abs_coordinate(const double3 p)
{
  return std::max({std::abs(p.x), std::abs(p.y), std::abs(p.z)});
}

// Checks a hit against its closed-form answer: the object index, t against distance / |d|, the
// barycentric point against o + t d, and the world Ng against the world normal of the reported
// triangle. `point` is the world hit point. `tfm` is the transform of the expected object. The
// caller checks the triangle index (hit.prim) itself, because it depends on the point.
void check_hit(const PainterlyIntersection &hit,
               const PainterlyRay &ray,
               const double3 point,
               const int object,
               const float *tfm)
{
  REQUIRE(hit.kind == HIT_TRIANGLE);
  CHECK(hit.index == object);
  REQUIRE(hit.prim >= 0);
  REQUIRE(hit.prim < 2);  // The quad has two triangles.

  // t is parametric along the unnormalized d, so t = distance / |d| (SPEC §4). Bound:
  // HIT_RELATIVE_BOUND relative to t, plus the binary64 round-off of t_expected.
  const double t_expected = len(point - ray.o) / len(ray.d);
  CHECK(std::abs(hit.t - t_expected) <= (HIT_RELATIVE_BOUND + REFERENCE_ROUNDOFF) * t_expected);

  // The triangle's world corners.
  const uint32_t *tri = QUAD_TRIANGLES + 3 * hit.prim;
  const double3 w0 = to_world_point(tfm, quad_vertex(tri[0]));
  const double3 w1 = to_world_point(tfm, quad_vertex(tri[1]));
  const double3 w2 = to_world_point(tfm, quad_vertex(tri[2]));

  // Embree's barycentrics: p = (1 - u - v) v0 + u v1 + v v2 must equal o + t d. The exact u*, v*
  // and t* satisfy it exactly. p is linear in u and v, so their relative errors (at most
  // HIT_RELATIVE_BOUND) move it by at most HIT_RELATIVE_BOUND (u* + v*) max|wi - w0|, which is at
  // most 2 HIT_RELATIVE_BOUND S with S = max|wi| (u*, v* >= 0 and u* + v* <= 1: the hit is in the
  // triangle). The error of t moves o + t d by at most HIT_RELATIVE_BOUND |p - o|, which is at
  // most HIT_RELATIVE_BOUND (S + |o|). S and |o| are at most `scale`, so the two sides differ by
  // at most 4 HIT_RELATIVE_BOUND scale, plus the binary64 round-off of this function.
  const double u = hit.u;
  const double v = hit.v;
  const double3 barycentric = w0 * (1.0 - u - v) + w1 * u + w2 * v;
  const double3 on_ray = ray.o + ray.d * hit.t;
  const double scale = std::max({max_abs_coordinate(ray.o),
                                 max_abs_coordinate(on_ray),
                                 max_abs_coordinate(w0),
                                 max_abs_coordinate(w1),
                                 max_abs_coordinate(w2)});
  const double point_bound = (4.0 * HIT_RELATIVE_BOUND + REFERENCE_ROUNDOFF) * scale;
  CHECK(std::abs(barycentric.x - on_ray.x) <= point_bound);
  CHECK(std::abs(barycentric.y - on_ray.y) <= point_bound);
  CHECK(std::abs(barycentric.z - on_ray.z) <= point_bound);

  // The world normal of the triangle is the cross product of its world edges. Ng is parallel to
  // it, and its sign may differ (a mirroring transform flips the winding, but not the side of the
  // surface). Embree's object-space Ng is exact (no reciprocal on its path, see
  // HIT_RELATIVE_BOUND), and the normal matrix and the world corners of this file are dyadic, so
  // binary64 forms the world Ng, the edges and both cross products exactly: the result is zero.
  const double3 parallel = cross(hit.Ng, cross(w1 - w0, w2 - w0));
  CHECK(parallel.x == 0.0);
  CHECK(parallel.y == 0.0);
  CHECK(parallel.z == 0.0);
}

}  // namespace

TEST_CASE(
    "painterly_embree: instance hits give unnormalized t, object, triangle, barycentrics and Ng")
{
  const SceneHandle scene = build_quad_scene();
  REQUIRE(scene != nullptr);

  // |d| = 0.5, 1, 2 (SPEC §4). Each direction is an integer or dyadic multiple of a fixed vector,
  // so its binary32 value is exact.
  for (const double s : {0.5, 1.0, 2.0}) {
    INFO("|d| scale s = " << s);

    // Object 0: from (0.25, 0.25, 6) along s (0.5, 0.25, -1). It meets z = 5 at t = 1/s, at (0.75,
    // 0.5, 5). In object space that is (0.5, 0.75): above the diagonal, so triangle 1.
    const PainterlyRay ray0 = make_ray(make_double3(0.25, 0.25, 6.0),
                                       make_double3(0.5 * s, 0.25 * s, -1.0 * s));
    PainterlyIntersection hit0;
    REQUIRE(painterly_embree_intersect_closest(scene.get(), ray0, 0.0, INFINITE_DISTANCE, &hit0));
    CHECK(hit0.prim == 1);
    check_hit(hit0, ray0, make_double3(0.75, 0.5, 5.0), 0, OBJECT0_TO_WORLD);
    // Object 0's inverse transpose is [[0,1,0],[1,0,0],[0,0,1/2]], and the object normal is
    // (0,0,+-1). Both are exact in binary32 and in double, so Ng is exactly (0, 0, +-1/2):
    // unnormalized, and scaled by the transform.
    CHECK(hit0.Ng.x == 0.0);
    CHECK(hit0.Ng.y == 0.0);
    CHECK(std::abs(hit0.Ng.z) == 0.5);

    // Object 1: straight down from (2.5, 3, 10), so |d| = s. The hit is (2.5, 3, -2.625), at t
    // = 12.625 / s. In object space that is (0.75, 0.5): below the diagonal, so triangle 0.
    const PainterlyRay ray1 = make_ray(make_double3(2.5, 3.0, 10.0), make_double3(0.0, 0.0, -s));
    PainterlyIntersection hit1;
    REQUIRE(painterly_embree_intersect_closest(scene.get(), ray1, 0.0, INFINITE_DISTANCE, &hit1));
    CHECK(hit1.prim == 0);
    check_hit(hit1, ray1, make_double3(2.5, 3.0, -2.625), 1, OBJECT1_TO_WORLD);
  }
}

TEST_CASE("painterly_embree: a ray through the shared diagonal of an instance hits it")
{
  const SceneHandle scene = build_quad_scene();
  REQUIRE(scene != nullptr);

  // Object-space ray o = (0.25, 0.25, 1), d = (0, 0, -1). It crosses the diagonal from (0,0,0) to
  // (1,1,0) at (0.25, 0.25, 0). Object 0's transform is exact, so the world ray is exact too: o =
  // (0.25, 0.25, 7), d = (0, 0, -2). The world edge runs from (0, 0, 5) to (1, 1, 5), and the
  // crossing point (0.25, 0.25, 5) lies on it exactly.
  const double3 origin = to_world_point(OBJECT0_TO_WORLD, make_double3(0.25, 0.25, 1.0));
  const double3 direction = to_world_direction(OBJECT0_TO_WORLD, make_double3(0.0, 0.0, -1.0));
  for (const double c : {origin.x, origin.y, origin.z, direction.x, direction.y, direction.z}) {
    CHECK(static_cast<double>(static_cast<float>(c)) == c);
  }

  const PainterlyRay ray = make_ray(origin, direction);
  PainterlyIntersection hit;
  REQUIRE(painterly_embree_intersect_closest(scene.get(), ray, 0.0, INFINITE_DISTANCE, &hit));
  CHECK(hit.index == 0);
  CHECK((hit.prim == 0 ||
         hit.prim == 1));  // Either triangle may take a crossing on their shared edge.
  check_hit(hit, ray, make_double3(0.25, 0.25, 5.0), 0, OBJECT0_TO_WORLD);
}

TEST_CASE("painterly_embree: tnear excludes the surface a ray starts on, and tfar bounds the hit")
{
  const SceneHandle scene = build_quad_scene();
  REQUIRE(scene != nullptr);

  // A point on object 0's quad, off the diagonal and inside triangle 1: (0.75, 0.5, 5). A ray that
  // starts on the surface must not re-hit it (SPEC §6): with tnear = RAY_EPSILON, both directions
  // miss.
  const double3 start = make_double3(0.75, 0.5, 5.0);
  const PainterlyRay up = make_ray(start, make_double3(0.0, 0.0, 1.0));
  const PainterlyRay down = make_ray(start, make_double3(0.0, 0.0, -1.0));
  PainterlyIntersection miss;
  miss.kind = HIT_TRIANGLE;
  CHECK_FALSE(
      painterly_embree_intersect_closest(scene.get(), up, RAY_EPSILON, INFINITE_DISTANCE, &miss));
  CHECK(miss.kind == HIT_NONE);
  CHECK_FALSE(painterly_embree_intersect_closest(
      scene.get(), down, RAY_EPSILON, INFINITE_DISTANCE, &miss));
  CHECK(miss.kind == HIT_NONE);

  // Control: the re-hit that the exclusion prevents. A ray that starts a binary32-exact distance
  // below the surface, going up, is hit at t = delta without tnear, and is missed with tnear =
  // RAY_EPSILON. delta = 2^-20 is exact at z = 5 (the binary32 spacing there is 2^-21), and it is
  // far below RAY_EPSILON.
  const double delta = 0x1p-20;
  const PainterlyRay below = make_ray(make_double3(0.75, 0.5, 5.0 - delta),
                                      make_double3(0.0, 0.0, 1.0));
  PainterlyIntersection self;
  REQUIRE(painterly_embree_intersect_closest(scene.get(), below, 0.0, INFINITE_DISTANCE, &self));
  CHECK(self.index == 0);
  CHECK(std::abs(self.t - delta) <= HIT_RELATIVE_BOUND * delta);
  CHECK_FALSE(painterly_embree_intersect_closest(
      scene.get(), below, RAY_EPSILON, INFINITE_DISTANCE, &miss));
  CHECK(miss.kind == HIT_NONE);

  // tfar: the hit of the ray from (0.25, 0.25, 7) along (0, 0, -2) is at t = 1. tfar = 0.5 misses,
  // tfar = 2 hits.
  const PainterlyRay down_far = make_ray(make_double3(0.25, 0.25, 7.0),
                                         make_double3(0.0, 0.0, -2.0));
  CHECK_FALSE(painterly_embree_intersect_closest(scene.get(), down_far, 0.0, 0.5, &miss));
  REQUIRE(painterly_embree_intersect_closest(scene.get(), down_far, 0.0, 2.0, &self));
  CHECK(self.index == 0);
}

TEST_CASE("painterly_embree: the scene keeps no pointer into the caller's arrays")
{
  std::vector<float> vertices(QUAD_VERTICES, QUAD_VERTICES + 12);
  std::vector<uint32_t> triangles(QUAD_TRIANGLES, QUAD_TRIANGLES + 6);
  std::vector<float> object0(OBJECT0_TO_WORLD, OBJECT0_TO_WORLD + 12);
  std::vector<float> object1(OBJECT1_TO_WORLD, OBJECT1_TO_WORLD + 12);
  const SceneHandle scene = build_scene(
      vertices.data(), triangles.data(), object0.data(), object1.data());
  REQUIRE(scene != nullptr);

  // Overwrite every array the scene was built from. A scene that kept a pointer would miss, or
  // would read NaN.
  std::fill(vertices.begin(), vertices.end(), std::numeric_limits<float>::quiet_NaN());
  std::fill(triangles.begin(), triangles.end(), 0u);
  std::fill(object0.begin(), object0.end(), std::numeric_limits<float>::quiet_NaN());
  std::fill(object1.begin(), object1.end(), std::numeric_limits<float>::quiet_NaN());

  const PainterlyRay ray = make_ray(make_double3(0.25, 0.25, 7.0), make_double3(0.0, 0.0, -2.0));
  PainterlyIntersection hit;
  REQUIRE(painterly_embree_intersect_closest(scene.get(), ray, 0.0, INFINITE_DISTANCE, &hit));
  check_hit(hit, ray, make_double3(0.25, 0.25, 5.0), 0, OBJECT0_TO_WORLD);
}

TEST_CASE("painterly_embree: malformed input is rejected with std::invalid_argument")
{
  const PainterlyEmbreeMeshInput good_mesh = {QUAD_VERTICES, 4, QUAD_TRIANGLES, 2};
  const PainterlyEmbreeObjectInput good_object[1] = {{0, OBJECT0_TO_WORLD}};

  // Vertex index 4 does not exist in a mesh of four vertices.
  const uint32_t bad_triangles[3] = {0, 1, 4};
  const PainterlyEmbreeMeshInput bad_mesh = {QUAD_VERTICES, 4, bad_triangles, 1};
  CHECK_THROWS_AS(painterly_embree_scene_create(&bad_mesh, 1, good_object, 1),
                  std::invalid_argument);

  // Mesh index 1 does not exist.
  const PainterlyEmbreeObjectInput bad_object[1] = {{1, OBJECT0_TO_WORLD}};
  CHECK_THROWS_AS(painterly_embree_scene_create(&good_mesh, 1, bad_object, 1),
                  std::invalid_argument);

  // The y column is zero, so the transform is singular and its normals cannot be mapped.
  const float singular[12] = {
      1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f};
  const PainterlyEmbreeObjectInput singular_object[1] = {{0, singular}};
  CHECK_THROWS_AS(painterly_embree_scene_create(&good_mesh, 1, singular_object, 1),
                  std::invalid_argument);
}

TEST_CASE("triangle normals: Ng and the corner normals of a flat triangle share one matrix")
{
  // world = A (x, y, z) + (1, 2, -3) with A = [[2, 0, 0], [0, -2, 0], [0.5, 0.5, 1]]: an axis
  // mirror (det(A) = -4), a power-of-two scale and a dyadic shear. Its normal matrix (A^-1)^T is
  // [[0.5, 0, -0.25], [0, -0.5, 0.25], [0, 0, 1]], so the quad's object normal (0, 0, 1) maps to
  // (-0.25, 0.25, 1), whose components are all nonzero.
  const float object_to_world[12] = {
      2.0f, 0.0f, 0.0f, 1.0f, 0.0f, -2.0f, 0.0f, 2.0f, 0.5f, 0.5f, 1.0f, -3.0f};
  const PainterlyEmbreeMeshInput mesh_input = {QUAD_VERTICES, 4, QUAD_TRIANGLES, 2};
  const PainterlyEmbreeObjectInput object_input = {0, object_to_world};
  const SceneHandle scene(painterly_embree_scene_create(&mesh_input, 1, &object_input, 1),
                          painterly_embree_scene_free);
  REQUIRE(scene != nullptr);

  // The kernel's device scene: one object with its normal matrix, and the quad's corner normals,
  // (0, 0, 1) at every corner of both triangles (flat triangles).
  KernelPainterlyObject object{};
  painterly_normal_matrix(object_to_world, object.normal_to_world);
  object.mesh = 0;
  object.object_id = 0;
  KernelPainterlyMesh mesh{};
  mesh.tri_offset = 0;
  mesh.num_tris = 2;
  const float corner_normal[PAINTERLY_POINT_FLOATS] = {0.0f, 0.0f, 1.0f};
  std::vector<float> corner_normals;
  for (int corner = 0; corner < mesh.num_tris * PAINTERLY_TRIANGLE_CORNERS; ++corner) {
    corner_normals.insert(
        corner_normals.end(), corner_normal, corner_normal + PAINTERLY_POINT_FLOATS);
  }
  PainterlyGlobalsCPU globals{};
  globals.objects = &object;
  globals.num_objects = 1;
  globals.meshes = &mesh;
  globals.num_meshes = 1;
  globals.tri_corner_normals = corner_normals.data();
  globals.bvh = scene.get();

  // Straight down onto the object-space point (0.75, 0.5) of triangle 0, the world point
  // (2.5, 1, -2.375).
  const PainterlyRay ray = make_ray(make_double3(2.5, 1.0, 10.0), make_double3(0.0, 0.0, -1.0));
  PainterlyIntersection hit;
  REQUIRE(painterly_embree_intersect_closest(scene.get(), ray, 0.0, INFINITE_DISTANCE, &hit));
  CHECK(hit.index == 0);
  CHECK(hit.prim == 0);

  // Embree's object-space Ng of triangle 0 is (v1 - v0) x (v2 - v0) = (0, 0, 1), exactly (see
  // HIT_RELATIVE_BOUND), so the world Ng is the closed form exactly.
  CHECK(hit.Ng.x == -0.25);
  CHECK(hit.Ng.y == 0.25);
  CHECK(hit.Ng.z == 1.0);

  // The corner normals interpolate to (0, 0, 1) exactly: u and v are binary32 values near 1/4 and
  // 1/2, so the weights 1 - u - v, u and v and their sum are exact in binary64. Both routes then
  // normalize the same vector and agree exactly.
  mesh.has_corner_normals = 1;
  const double3 n_corner = painterly_triangle_shading_normal(&globals, hit, ray, false);
  mesh.has_corner_normals = 0;
  const double3 n_flat = painterly_triangle_shading_normal(&globals, hit, ray, false);
  const double3 n_expected = normalize(make_double3(-0.25, 0.25, 1.0));
  CHECK(n_corner.x == n_flat.x);
  CHECK(n_corner.y == n_flat.y);
  CHECK(n_corner.z == n_flat.z);
  CHECK(n_flat.x == n_expected.x);
  CHECK(n_flat.y == n_expected.y);
  CHECK(n_flat.z == n_expected.z);
}

CCL_NAMESPACE_END
