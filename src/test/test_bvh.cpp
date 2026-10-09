// SPDX-License-Identifier: GPL-3.0-or-later
// Tests of painterly/bvh/embree.h (T3.10). The scene is the unit quad of the card (two triangles
// sharing the diagonal from (0,0,0) to (1,1,0)), instanced twice. Object 0 is an axis permutation
// with a power-of-two scale and an integer translation, so its transform is exact. Object 1 is a
// shear with dyadic entries, so its normals are not axis-aligned. Every ray is exact in binary32,
// and every expected hit is known in closed form. The only comparisons with a tolerance are the
// binary32 round-off bounds of the hit, derived where they are defined. The others are exact.

#include <doctest/doctest.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <limits>
#include <memory>
#include <stdexcept>
#include <vector>

#include "painterly/bvh/embree.h"
#include "painterly/util/math_double3.h"

CCL_NAMESPACE_BEGIN

namespace {

// Round-off of binary32, which Embree computes the hit in. u = 2^-24 is the unit round-off of IEEE
// binary32 with round to nearest (a definition of the format). A hit reaches the caller through at
// most F32_STEPS = 4 roundings: the transform of the origin into object space, the transform of
// the direction, the edge functions (products and sums), and the division T / det that gives t.
// Each rounding has relative error at most u, so to first order the relative error of t is at most
// 4u. The same count bounds the point and the normal below, which are formed from the same
// products. The 4 is a count of the steps on that path, not a measurement of Embree's source. As a
// check, M2's selftest gave t = 0.49999997 for an exact 0.5: a relative error of 6e-8, which lies
// inside 4u = 2^-22 (about 2.4e-7).
constexpr double F32_UNIT_ROUNDOFF = 0x1p-24;
constexpr double F32_STEPS = 4.0;

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

  // t is parametric along the unnormalized d, so t = distance / |d| (SPEC §4). Bound: 4u relative
  // to t (see F32_STEPS).
  const double t_expected = len(point - ray.o) / len(ray.d);
  CHECK(std::abs(hit.t - t_expected) <= F32_STEPS * F32_UNIT_ROUNDOFF * t_expected);

  // The triangle's world corners.
  const uint32_t *tri = QUAD_TRIANGLES + 3 * hit.prim;
  const double3 w0 = to_world_point(tfm, quad_vertex(tri[0]));
  const double3 w1 = to_world_point(tfm, quad_vertex(tri[1]));
  const double3 w2 = to_world_point(tfm, quad_vertex(tri[2]));

  // Embree's barycentrics: p = (1 - u - v) v0 + u v1 + v v2 must equal o + t d. Bound: 4u times
  // the largest coordinate the rounding acts on, which is at most the largest of the origin, the
  // hit and the corners.
  const double u = hit.u;
  const double v = hit.v;
  const double3 barycentric = w0 * (1.0 - u - v) + w1 * u + w2 * v;
  const double3 on_ray = ray.o + ray.d * hit.t;
  const double scale = std::max({max_abs_coordinate(ray.o),
                                 max_abs_coordinate(on_ray),
                                 max_abs_coordinate(w0),
                                 max_abs_coordinate(w1),
                                 max_abs_coordinate(w2)});
  const double point_bound = F32_STEPS * F32_UNIT_ROUNDOFF * scale;
  CHECK(std::abs(barycentric.x - on_ray.x) <= point_bound);
  CHECK(std::abs(barycentric.y - on_ray.y) <= point_bound);
  CHECK(std::abs(barycentric.z - on_ray.z) <= point_bound);

  // The world normal of the triangle is the cross product of its world edges. Ng is parallel to
  // it, and its sign may differ (a mirroring transform flips the winding, but not the side of the
  // surface). |cross(Ng, n)| = |Ng| |n| sin(angle), and sin(angle) is bounded by 4u as above.
  const double3 normal = cross(w1 - w0, w2 - w0);
  const double3 ng = hit.Ng;
  CHECK(len(cross(ng, normal)) <= F32_STEPS * F32_UNIT_ROUNDOFF * len(ng) * len(normal));
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
  CHECK(std::abs(self.t - delta) <= F32_STEPS * F32_UNIT_ROUNDOFF * delta);
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

CCL_NAMESPACE_END
